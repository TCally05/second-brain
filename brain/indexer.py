from __future__ import annotations

import json
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


def slug_from_path(path: Path) -> str | None:
    _, _, slug = path.stem.partition("-")
    return slug or None


def build_index(vault_root: Path, db_path: Path) -> IndexResult:
    notes: list[Note] = []
    errors: list[tuple[Path, str]] = []

    for md_path in iter_markdown_files(vault_root):
        try:
            notes.append(Note.from_file(md_path))
        except NoteParseError as exc:
            errors.append((md_path, str(exc)))

    id_to_note = {note.id: note for note in notes}
    slug_to_id: dict[str, str] = {}
    for note in notes:
        slug = slug_from_path(note.path)
        if slug is not None:
            slug_to_id[slug] = note.id

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
            for note in notes:
                for target in parse_wikilinks(note.body):
                    target_id = _resolve_target(target, id_to_note, slug_to_id)
                    conn.execute(
                        "INSERT OR IGNORE INTO links (source_id, target, target_id) "
                        "VALUES (?, ?, ?)",
                        (note.id, target, target_id),
                    )
    finally:
        conn.close()

    return IndexResult(indexed=len(notes), errors=errors)


def _resolve_target(
    target: str, id_to_note: dict[str, Note], slug_to_id: dict[str, str]
) -> str | None:
    if ID_PATTERN.match(target) and target in id_to_note:
        return target
    return slug_to_id.get(target)
