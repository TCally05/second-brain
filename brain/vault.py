from __future__ import annotations

from pathlib import Path
from typing import Iterator

PARA_FOLDERS = ("inbox", "projects", "areas", "resources", "archives")


def iter_markdown_files(vault_root: Path) -> Iterator[Path]:
    """Yield every .md file inside the PARA folders, skipping hidden
    directories (e.g. a stray .trash). Root-level files like CLAUDE.md or
    README.md are project files, not notes, so they're deliberately out
    of scope."""
    for folder in PARA_FOLDERS:
        for md_path in (vault_root / folder).rglob("*.md"):
            relative_parts = md_path.relative_to(vault_root / folder).parts
            if any(part.startswith(".") for part in relative_parts):
                continue
            yield md_path
