from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OrphanNote:
    id: str
    title: str
    path: str


def get_orphans(db_path: Path) -> list[OrphanNote]:
    """Notes with no resolved incoming or outgoing links - islands in the
    link graph. A dangling wikilink to a target that doesn't exist leaves
    target_id NULL, so it doesn't count as an outgoing link here; the note
    still isn't actually connected to anything in the vault."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, title, path
            FROM notes
            WHERE id NOT IN (
                SELECT source_id FROM links WHERE target_id IS NOT NULL
            )
            AND id NOT IN (
                SELECT target_id FROM links WHERE target_id IS NOT NULL
            )
            ORDER BY id
            """
        ).fetchall()
    finally:
        conn.close()

    return [OrphanNote(id=row[0], title=row[1], path=row[2]) for row in rows]
