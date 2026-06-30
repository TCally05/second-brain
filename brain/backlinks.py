from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Backlink:
    id: str
    title: str
    path: str


def get_backlinks(db_path: Path, note_id: str) -> list[Backlink] | None:
    """Notes that link to note_id, ordered by id. Returns None if note_id
    isn't in the index at all (likely a typo), as opposed to an empty
    list, which means the note exists but nothing links to it."""
    conn = sqlite3.connect(db_path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if exists is None:
            return None

        rows = conn.execute(
            """
            SELECT notes.id, notes.title, notes.path
            FROM links
            JOIN notes ON notes.id = links.source_id
            WHERE links.target_id = ?
            ORDER BY notes.id
            """,
            (note_id,),
        ).fetchall()
    finally:
        conn.close()

    return [Backlink(id=row[0], title=row[1], path=row[2]) for row in rows]
