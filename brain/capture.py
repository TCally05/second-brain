from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from brain.vault import iter_markdown_files

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = SLUG_PATTERN.sub("-", title.lower()).strip("-")
    return slug or "note"


def existing_note_ids(vault_root: Path) -> set[str]:
    return {md_path.stem.split("-", 1)[0] for md_path in iter_markdown_files(vault_root)}


def generate_id(existing_ids: set[str], now: datetime | None = None) -> str:
    now = now or datetime.now()
    candidate = now.strftime("%Y%m%d%H%M")
    while candidate in existing_ids:
        now += timedelta(minutes=1)
        candidate = now.strftime("%Y%m%d%H%M")
    return candidate


def serialize_note(note_id: str, title: str, tags: list[str], body: str) -> str:
    frontmatter = yaml.safe_dump(
        {"id": note_id, "title": title, "tags": tags},
        sort_keys=False,
    )
    body = body.strip()
    return f"---\n{frontmatter}---\n\n{body}\n" if body else f"---\n{frontmatter}---\n\n"


def create_note(
    title: str,
    vault_root: Path,
    inbox_dirname: str = "inbox",
    tags: list[str] | None = None,
    body: str = "",
) -> Path:
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")

    note_id = generate_id(existing_note_ids(vault_root))
    filename = f"{note_id}-{slugify(title)}.md"

    inbox = vault_root / inbox_dirname
    inbox.mkdir(parents=True, exist_ok=True)
    note_path = inbox / filename
    note_path.write_text(serialize_note(note_id, title, tags or [], body), encoding="utf-8")
    return note_path


def update_note(path: Path, note_id: str, title: str, tags: list[str], body: str) -> None:
    """Rewrite an existing note's frontmatter and body in place, preserving
    its id and file location. The filename (and therefore its slug, per
    indexer.slug_from_path) is deliberately never changed here - renaming
    it on every title edit would break any [[slug]]-style link pointing at
    the old name, the same "moving/editing a note never breaks its links"
    guarantee the folder structure already gives you."""
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")

    path.write_text(serialize_note(note_id, title, tags, body), encoding="utf-8")
