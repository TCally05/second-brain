import json
import sqlite3
from pathlib import Path

import pytest

from brain.indexer import build_index, slug_from_path


def make_vault(tmp_path: Path) -> Path:
    for folder in ("inbox", "projects", "areas", "resources", "archives"):
        (tmp_path / folder).mkdir()
    return tmp_path


def write_note(vault: Path, folder: str, filename: str, id_: str, title: str, body: str = "") -> Path:
    text = f"---\nid: {id_!r}\ntitle: {title}\ntags: []\n---\n\n{body}"
    path = vault / folder / filename
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("202601151230-my-cool-note", "my-cool-note"),
        ("202601151230", None),
        ("202601151230-", None),
    ],
)
def test_slug_from_path(stem, expected):
    assert slug_from_path(Path(f"{stem}.md")) == expected


def test_build_index_creates_target_id_index_on_links(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    conn = sqlite3.connect(db_path)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'links'"
        )
    }
    conn.close()
    assert "idx_links_target_id" in names


def test_build_index_counts_notes_and_skips_no_errors(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A")
    write_note(vault, "projects", "202601151231-b.md", "202601151231", "Note B")

    result = build_index(vault, vault / ".brain" / "index.db")

    assert result.indexed == 2
    assert result.errors == []


def test_build_index_inserts_note_rows(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id, title, path, tags FROM notes").fetchone()
    conn.close()

    assert row[0] == "202601151230"
    assert row[1] == "Note A"
    assert row[2] == "inbox/202601151230-a.md"
    assert json.loads(row[3]) == []


def test_build_index_resolves_link_by_id(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A", "Links to [[202601151231]].")
    write_note(vault, "inbox", "202601151231-b.md", "202601151231", "Note B")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT source_id, target, target_id FROM links").fetchone()
    conn.close()

    assert row == ("202601151230", "202601151231", "202601151231")


def test_build_index_resolves_link_by_slug(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A", "Links to [[note-b]].")
    write_note(vault, "inbox", "202601151231-note-b.md", "202601151231", "Note B")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT source_id, target, target_id FROM links").fetchone()
    conn.close()

    assert row == ("202601151230", "note-b", "202601151231")


def test_build_index_warns_on_ambiguous_slug_and_leaves_link_unresolved(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-meeting-notes.md", "202601151230", "Meeting notes", "First one.")
    write_note(vault, "inbox", "202601151231-meeting-notes.md", "202601151231", "Meeting notes", "Second one.")
    write_note(
        vault, "inbox", "202601151232-linker.md", "202601151232", "Linker",
        "Links to [[meeting-notes]].",
    )

    db_path = vault / ".brain" / "index.db"
    result = build_index(vault, db_path)

    assert result.errors == []
    assert result.indexed == 3
    assert len(result.warnings) == 1
    assert "meeting-notes" in result.warnings[0]
    assert "ambiguous" in result.warnings[0]

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT target_id FROM links WHERE source_id = '202601151232'"
    ).fetchone()
    conn.close()
    assert row == (None,)


def test_build_index_unresolved_link_has_null_target_id(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A", "Links to [[nope]].")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT source_id, target, target_id FROM links").fetchone()
    conn.close()

    assert row == ("202601151230", "nope", None)


def test_build_index_collects_parse_errors_without_dropping_valid_notes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A")
    bad_path = vault / "inbox" / "broken.md"
    bad_path.write_text("no frontmatter here\n", encoding="utf-8")

    db_path = vault / ".brain" / "index.db"
    result = build_index(vault, db_path)

    assert result.indexed == 1
    assert len(result.errors) == 1
    assert result.errors[0][0] == bad_path
    assert "no frontmatter" in result.errors[0][1]

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    conn.close()
    assert count == 1


def test_build_index_reports_duplicate_ids_without_crashing_or_wiping_others(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "inbox", "202601151230-good.md", "202601151230", "Good note")
    dup_a = write_note(vault, "inbox", "202601151231-dup-a.md", "202601151231", "Dup A")
    dup_b = write_note(vault, "inbox", "202601151231-dup-b.md", "202601151231", "Dup B")

    db_path = vault / ".brain" / "index.db"
    result = build_index(vault, db_path)

    assert result.indexed == 1
    error_paths = {path for path, _ in result.errors}
    assert error_paths == {dup_a, dup_b}
    assert all("duplicate id" in msg for _, msg in result.errors)

    conn = sqlite3.connect(db_path)
    ids = {row[0] for row in conn.execute("SELECT id FROM notes")}
    conn.close()
    assert ids == {"202601151230"}


def test_build_index_is_a_full_rebuild_not_incremental(tmp_path):
    vault = make_vault(tmp_path)
    first_path = write_note(vault, "inbox", "202601151230-a.md", "202601151230", "Note A")
    write_note(vault, "inbox", "202601151231-b.md", "202601151231", "Note B")

    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)

    first_path.unlink()
    result = build_index(vault, db_path)

    assert result.indexed == 1
    conn = sqlite3.connect(db_path)
    ids = {row[0] for row in conn.execute("SELECT id FROM notes")}
    conn.close()
    assert ids == {"202601151231"}
