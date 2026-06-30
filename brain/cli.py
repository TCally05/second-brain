from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brain.capture import create_note
from brain.indexer import build_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="capture a new note")
    new_parser.add_argument("title", help="title of the new note")

    subparsers.add_parser("index", help="rebuild the SQLite index from markdown")

    args = parser.parse_args(argv)

    if args.command == "new":
        note_path = create_note(args.title, Path.cwd())
        print(note_path)

    elif args.command == "index":
        vault_root = Path.cwd()
        db_path = vault_root / ".brain" / "index.db"
        result = build_index(vault_root, db_path)
        print(f"Indexed {result.indexed} notes.")
        for path, error in result.errors:
            print(f"  SKIPPED {path}: {error}", file=sys.stderr)
        if result.errors:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
