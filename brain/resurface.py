from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResurfacedNote:
    id: str
    title: str
    path: str
    link_count: int


def get_resurface_candidates(
    db_path: Path, count: int = 5, rng: random.Random | None = None
) -> list[ResurfacedNote]:
    """Pick up to `count` notes at random, weighted toward ones with fewer
    links. The point of resurfacing isn't just "remind me this exists" -
    it's nudging you back to the notes that are least woven into the
    Zettelkasten yet, since those are the ones still waiting to be
    connected. Every note has some chance of being picked regardless of
    link_count, so well-connected notes still show up occasionally."""
    rng = rng or random.Random()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT notes.id, notes.title, notes.path,
                   (SELECT COUNT(*) FROM links
                    WHERE links.target_id IS NOT NULL
                      AND (links.source_id = notes.id OR links.target_id = notes.id))
            FROM notes
            """
        ).fetchall()
    finally:
        conn.close()

    remaining = [
        ResurfacedNote(id=row[0], title=row[1], path=row[2], link_count=row[3])
        for row in rows
    ]

    picked: list[ResurfacedNote] = []
    for _ in range(min(count, len(remaining))):
        weights = [1 / (note.link_count + 1) for note in remaining]
        choice = rng.choices(remaining, weights=weights, k=1)[0]
        picked.append(choice)
        remaining.remove(choice)

    return picked
