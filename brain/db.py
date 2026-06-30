from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT NOT NULL,
    tags TEXT NOT NULL
);

CREATE TABLE links (
    source_id TEXT NOT NULL REFERENCES notes(id),
    target TEXT NOT NULL,
    target_id TEXT REFERENCES notes(id),
    PRIMARY KEY (source_id, target)
);

CREATE VIRTUAL TABLE notes_fts USING fts5(id UNINDEXED, title, body);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def reset_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate every table. The index is fully derived from the
    markdown corpus, so there's no migration story to preserve - each
    `brain index` run starts from a clean schema."""
    conn.executescript(
        "DROP TABLE IF EXISTS notes_fts;"
        "DROP TABLE IF EXISTS links;"
        "DROP TABLE IF EXISTS notes;"
    )
    conn.executescript(SCHEMA)
