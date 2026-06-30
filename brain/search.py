from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchResult:
    id: str
    title: str
    path: str
    snippet: str


def search_notes(db_path: Path, query: str, limit: int = 20) -> list[SearchResult]:
    """Full-text search over note titles/bodies. `query` is passed straight
    to FTS5's MATCH, so callers get its native syntax for free ("phrase",
    prefix*, foo AND bar, foo NOT bar) - and a malformed query raises
    sqlite3.OperationalError, which callers should handle."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT notes.id, notes.title, notes.path,
                   snippet(notes_fts, -1, '[', ']', '...', 8)
            FROM notes_fts
            JOIN notes ON notes.id = notes_fts.id
            WHERE notes_fts MATCH ?
            ORDER BY notes_fts.rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        SearchResult(id=row[0], title=row[1], path=row[2], snippet=row[3])
        for row in rows
    ]
