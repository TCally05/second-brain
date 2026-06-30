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


def create_note(title: str, vault_root: Path, inbox_dirname: str = "inbox") -> Path:
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")

    note_id = generate_id(existing_note_ids(vault_root))
    filename = f"{note_id}-{slugify(title)}.md"

    frontmatter = yaml.safe_dump(
        {"id": note_id, "title": title, "tags": []},
        sort_keys=False,
    )
    content = f"---\n{frontmatter}---\n\n"

    inbox = vault_root / inbox_dirname
    inbox.mkdir(parents=True, exist_ok=True)
    note_path = inbox / filename
    note_path.write_text(content, encoding="utf-8")
    return note_path
