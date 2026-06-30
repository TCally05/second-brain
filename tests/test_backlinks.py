from pathlib import Path

from brain.backlinks import get_backlinks
from brain.capture import slugify
from brain.indexer import build_index


def make_vault(tmp_path: Path) -> Path:
    for folder in ("inbox", "projects", "areas", "resources", "archives"):
        (tmp_path / folder).mkdir()
    return tmp_path


def write_note(vault: Path, id_: str, title: str, body: str = "") -> Path:
    text = f"---\nid: {id_!r}\ntitle: {title}\ntags: []\n---\n\n{body}"
    path = vault / "inbox" / f"{id_}-{slugify(title)}.md"
    path.write_text(text, encoding="utf-8")
    return path


def build(vault: Path) -> Path:
    db_path = vault / ".brain" / "index.db"
    build_index(vault, db_path)
    return db_path


def test_backlinks_returns_notes_that_link_to_target(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Linker A", "See [[202601151230]].")
    write_note(vault, "202601151232", "Linker B", "Also see [[202601151230]].")
    db_path = build(vault)

    backlinks = get_backlinks(db_path, "202601151230")

    assert [bl.id for bl in backlinks] == ["202601151231", "202601151232"]
    assert backlinks[0].title == "Linker A"


def test_backlinks_resolves_slug_style_links(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")  # slug: "target-note"
    write_note(vault, "202601151231", "Linker", "See [[target-note]].")
    db_path = build(vault)

    backlinks = get_backlinks(db_path, "202601151230")

    assert [bl.id for bl in backlinks] == ["202601151231"]


def test_backlinks_excludes_unrelated_links(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Other note")
    write_note(vault, "202601151232", "Linker", "See [[202601151231]].")
    db_path = build(vault)

    assert get_backlinks(db_path, "202601151230") == []


def test_backlinks_for_note_with_no_incoming_links_is_empty_list(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Lonely note")
    db_path = build(vault)

    assert get_backlinks(db_path, "202601151230") == []


def test_backlinks_for_unknown_id_returns_none(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Some note")
    db_path = build(vault)

    assert get_backlinks(db_path, "999999999999") is None


def test_backlinks_ignores_unresolved_link_targets(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Linker", "See [[doesnotexist]].")
    db_path = build(vault)

    assert get_backlinks(db_path, "202601151230") == []
