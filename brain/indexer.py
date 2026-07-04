from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from brain.db import connect, reset_schema
from brain.links import parse_wikilinks
from brain.note import ID_PATTERN, Note, NoteParseError
from brain.vault import iter_markdown_files


@dataclass
class IndexResult:
    indexed: int
    errors: list[tuple[Path, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def slug_from_path(path: Path) -> str | None:
    _, _, slug = path.stem.partition("-")
    return slug or None


def build_index(vault_root: Path, db_path: Path) -> IndexResult:
    parsed: list[Note] = []
    errors: list[tuple[Path, str]] = []

    for md_path in iter_markdown_files(vault_root):
        try:
            parsed.append(Note.from_file(md_path))
        except NoteParseError as exc:
            errors.append((md_path, str(exc)))

    # A shared id would violate notes.id's PRIMARY KEY constraint and crash
    # the insert below, taking the whole index down with it (reset_schema
    # has already committed the DROP/CREATE by that point). Catch the
    # conflict here instead and report it the same way a NoteParseError is
    # reported, so the rest of the vault still indexes cleanly.
    notes_by_id: dict[str, list[Note]] = defaultdict(list)
    for note in parsed:
        notes_by_id[note.id].append(note)

    notes: list[Note] = []
    for note_id, group in notes_by_id.items():
        if len(group) == 1:
            notes.append(group[0])
            continue
        for note in group:
            others = ", ".join(str(n.path) for n in group if n is not note)
            errors.append((note.path, f"duplicate id {note_id!r} (also used by {others})"))

    id_to_note = {note.id: note for note in notes}

    # Two different notes can slugify to the same thing (e.g. two notes
    # both titled "Meeting Notes") - unlike a shared id, that's not a hard
    # conflict, but silently picking whichever was indexed last would mean
    # a [[slug]]-style link points at a different note depending on
    # filesystem walk order. Treat it as unresolved instead and warn, same
    # as an unresolved id-style link, rather than guessing.
    slug_to_notes: dict[str, list[Note]] = defaultdict(list)
    for note in notes:
        slug = slug_from_path(note.path)
        if slug is not None:
            slug_to_notes[slug].append(note)

    slug_to_id: dict[str, str] = {}
    ambiguous_slugs: set[str] = set()
    warnings: list[str] = []
    for slug, slug_notes in slug_to_notes.items():
        if len(slug_notes) > 1:
            ambiguous_slugs.add(slug)
            others = ", ".join(str(n.path) for n in slug_notes)
            warnings.append(
                f"slug {slug!r} is ambiguous between {others} "
                "- [[links]] to it will not resolve until you disambiguate "
                "(e.g. link by id instead)"
            )
        else:
            slug_to_id[slug] = slug_notes[0].id

    conn = connect(db_path)
    try:
        reset_schema(conn)
        with conn:
            for note in notes:
                conn.execute(
                    "INSERT INTO notes (id, title, path, tags) VALUES (?, ?, ?, ?)",
                    (
                        note.id,
                        note.title,
                        str(note.path.relative_to(vault_root)),
                        json.dumps(note.tags),
                    ),
                )
                conn.execute(
                    "INSERT INTO notes_fts (id, title, body) VALUES (?, ?, ?)",
                    (note.id, note.title, note.body),
                )
            for note in notes:
                for target in parse_wikilinks(note.body):
                    target_id = _resolve_target(target, id_to_note, slug_to_id, ambiguous_slugs)
                    conn.execute(
                        "INSERT OR IGNORE INTO links (source_id, target, target_id) "
                        "VALUES (?, ?, ?)",
                        (note.id, target, target_id),
                    )
    finally:
        conn.close()

    return IndexResult(indexed=len(notes), errors=errors, warnings=warnings)


def _resolve_target(
    target: str,
    id_to_note: dict[str, Note],
    slug_to_id: dict[str, str],
    ambiguous_slugs: set[str],
) -> str | None:
    if ID_PATTERN.match(target) and target in id_to_note:
        return target
    if target in ambiguous_slugs:
        return None
    return slug_to_id.get(target)
