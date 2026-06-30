import sqlite3
from pathlib import Path

import pytest

from brain.indexer import build_index
from brain.search import search_notes


def make_vault(tmp_path: Path) -> Path:
    for folder in ("inbox", "projects", "areas", "resources", "archives"):
        (tmp_path / folder).mkdir()
    return tmp_path


def write_note(vault: Path, id_: str, title: str, body: str = "") -> Path:
    text = f"---\nid: {id_!r}\ntitle: {title}\ntags: []\n---\n\n{body}"
    path = vault / "inbox" / f"{id_}-note.md"
    path.write_text(text, encoding="utf-8")
    return path


def build(vault: Path) -> Path:
    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)
    return db_path


def test_search_matches_title(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Zettelkasten basics", "An intro to the method.")
    db_path = build(vault)

    results = search_notes(db_path, "zettelkasten")

    assert [r.id for r in results] == ["202601151230"]
    assert results[0].title == "Zettelkasten basics"


def test_search_matches_body(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "Mentions sourdough baking.")
    db_path = build(vault)

    results = search_notes(db_path, "sourdough")

    assert [r.id for r in results] == ["202601151230"]


def test_search_no_match_returns_empty(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "Nothing relevant here.")
    db_path = build(vault)

    assert search_notes(db_path, "nonexistentterm") == []


def test_search_implicit_and_requires_all_terms(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Apples and oranges", "Just apples.")
    write_note(vault, "202601151231", "Oranges only", "Just oranges.")
    db_path = build(vault)

    results = search_notes(db_path, "apples oranges")

    assert [r.id for r in results] == ["202601151230"]


def test_search_phrase_query(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "the quick brown fox")
    write_note(vault, "202601151231", "Note B", "quick, then later, brown")
    db_path = build(vault)

    results = search_notes(db_path, '"quick brown"')

    assert [r.id for r in results] == ["202601151230"]


def test_search_prefix_query(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "indexing and searching")
    db_path = build(vault)

    results = search_notes(db_path, "index*")

    assert [r.id for r in results] == ["202601151230"]


def test_search_snippet_highlights_match(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "Some text about zettelkasten methods.")
    db_path = build(vault)

    results = search_notes(db_path, "zettelkasten")

    assert "[" in results[0].snippet and "]" in results[0].snippet


def test_search_ranks_denser_match_higher(tmp_path):
    vault = make_vault(tmp_path)
    write_note(
        vault,
        "202601151230",
        "Zettelkasten note",
        "zettelkasten zettelkasten zettelkasten",
    )
    filler = " ".join(["filler"] * 200)
    write_note(
        vault,
        "202601151231",
        "Long unrelated note",
        f"{filler} zettelkasten {filler}",
    )
    db_path = build(vault)

    results = search_notes(db_path, "zettelkasten")

    assert [r.id for r in results] == ["202601151230", "202601151231"]


def test_search_respects_limit(tmp_path):
    vault = make_vault(tmp_path)
    for i in range(5):
        write_note(vault, f"20260115123{i}", f"Note {i}", "shared term")
    db_path = build(vault)

    results = search_notes(db_path, "shared", limit=2)

    assert len(results) == 2


def test_malformed_query_raises_operational_error(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A", "body")
    db_path = build(vault)

    with pytest.raises(sqlite3.OperationalError):
        search_notes(db_path, '"unterminated phrase')
