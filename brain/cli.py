from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from brain.backlinks import get_backlinks
from brain.capture import create_note
from brain.indexer import build_index
from brain.search import search_notes


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
        try:
            results = search_notes(db_path, args.query)
        except sqlite3.OperationalError as exc:
            print(
                f"Search failed: {exc}. Have you run `brain index` yet?",
                file=sys.stderr,
            )
            return 1

        if not results:
            print("No matches.")
        for result in results:
            print(f"{result.id}  {result.title}  ({result.path})")
            print(f"    {result.snippet}")

    elif args.command == "backlinks":
        try:
            backlinks = get_backlinks(db_path, args.id)
        except sqlite3.OperationalError as exc:
            print(
                f"Backlinks lookup failed: {exc}. Have you run `brain index` yet?",
                file=sys.stderr,
            )
            return 1

        if backlinks is None:
            print(f"No note with id {args.id} found in the index.", file=sys.stderr)
            return 1

        if not backlinks:
            print(f"No notes link to {args.id}.")
        for backlink in backlinks:
            print(f"{backlink.id}  {backlink.title}  ({backlink.path})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
