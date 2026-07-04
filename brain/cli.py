from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from brain.backlinks import get_backlinks
from brain.capture import create_note
from brain.indexer import build_index
from brain.orphans import get_orphans
from brain.resurface import get_resurface_candidates
from brain.search import search_notes

_QUERY_FAILED = object()


def _query_index(label: str, fn, *args):
    """Run a read-only query against the index, turning a missing/corrupt
    .brain/index.db into a friendly hint instead of a raw traceback. Returns
    the sentinel _QUERY_FAILED on failure - not None, since some queries
    (e.g. get_backlinks) use None themselves for a legitimate "not found"."""
    try:
        return fn(*args)
    except sqlite3.OperationalError as exc:
        print(f"{label} failed: {exc}. Have you run `brain index` yet?", file=sys.stderr)
        return _QUERY_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="capture a new note")
    new_parser.add_argument("title", help="title of the new note")

    subparsers.add_parser("index", help="rebuild the SQLite index from markdown")

    search_parser = subparsers.add_parser("search", help="full-text search across notes")
    search_parser.add_argument("query", help="FTS5 query, e.g. foo, \"exact phrase\", foo*, foo AND bar")

    backlinks_parser = subparsers.add_parser(
        "backlinks", help="show notes that link to a given note id"
    )
    backlinks_parser.add_argument("id", help="zettelkasten id (YYYYMMDDHHMM)")

    subparsers.add_parser(
        "orphans", help="show notes with no incoming or outgoing links"
    )

    resurface_parser = subparsers.add_parser(
        "resurface", help="show random notes to revisit, favoring poorly-linked ones"
    )
    resurface_parser.add_argument(
        "-n", "--count", type=int, default=5, help="number of notes to show (default: 5)"
    )

    args = parser.parse_args(argv)

    vault_root = Path.cwd()
    db_path = vault_root / ".brain" / "index.db"

    if args.command == "new":
        note_path = create_note(args.title, vault_root)
        print(note_path)

    elif args.command == "index":
        result = build_index(vault_root, db_path)
        print(f"Indexed {result.indexed} notes.")
        for path, error in result.errors:
            print(f"  SKIPPED {path}: {error}", file=sys.stderr)
        if result.errors:
            return 1

    elif args.command == "search":
        results = _query_index("Search", search_notes, db_path, args.query)
        if results is _QUERY_FAILED:
            return 1

        if not results:
            print("No matches.")
        for result in results:
            print(f"{result.id}  {result.title}  ({result.path})")
            print(f"    {result.snippet}")

    elif args.command == "backlinks":
        backlinks = _query_index("Backlinks lookup", get_backlinks, db_path, args.id)
        if backlinks is _QUERY_FAILED:
            return 1

        if backlinks is None:
            print(f"No note with id {args.id} found in the index.", file=sys.stderr)
            return 1

        if not backlinks:
            print(f"No notes link to {args.id}.")
        for backlink in backlinks:
            print(f"{backlink.id}  {backlink.title}  ({backlink.path})")

    elif args.command == "orphans":
        orphans = _query_index("Orphans lookup", get_orphans, db_path)
        if orphans is _QUERY_FAILED:
            return 1

        if not orphans:
            print("No orphan notes.")
        for orphan in orphans:
            print(f"{orphan.id}  {orphan.title}  ({orphan.path})")

    elif args.command == "resurface":
        notes = _query_index("Resurface", get_resurface_candidates, db_path, args.count)
        if notes is _QUERY_FAILED:
            return 1

        if not notes:
            print("No notes to resurface yet.")
        for note in notes:
            print(f"{note.id}  {note.title}  ({note.path})  [{note.link_count} links]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
