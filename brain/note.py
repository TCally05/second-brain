from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

ID_PATTERN = re.compile(r"^\d{12}$")  # YYYYMMDDHHMM


class NoteParseError(ValueError):
    """Raised when a markdown file can't be parsed into a valid Note."""


@dataclass
class Note:
    id: str
    title: str
    tags: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None

    @property
    def created(self) -> datetime:
        return datetime.strptime(self.id, "%Y%m%d%H%M")

    @classmethod
    def from_file(cls, path: Path) -> Note:
        text = path.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(text, path)
        return cls.from_frontmatter(meta, body, path)

    @classmethod
    def from_frontmatter(cls, meta: dict, body: str, path: Path | None = None) -> Note:
        note_id = meta.get("id")
        if not note_id or not ID_PATTERN.match(str(note_id)):
            raise NoteParseError(
                f"missing or malformed id in {path}: expected YYYYMMDDHHMM, got {note_id!r}"
            )

        title = meta.get("title")
        if not title:
            raise NoteParseError(f"missing title in {path}")

        tags = meta.get("tags") or []
        if not isinstance(tags, list):
            raise NoteParseError(
                f"tags must be a list in {path}, got {type(tags).__name__}"
            )

        return cls(
            id=str(note_id),
            title=str(title),
            tags=[str(t) for t in tags],
            body=body,
            path=path,
        )


def _split_frontmatter(text: str, path: Path | None = None) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise NoteParseError(f"no frontmatter found in {path}")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise NoteParseError(f"malformed frontmatter block in {path}")

    _, raw_meta, body = parts
    meta = yaml.safe_load(raw_meta) or {}
    if not isinstance(meta, dict):
        raise NoteParseError(f"frontmatter must be a YAML mapping in {path}")

    return meta, body.lstrip("\n")
