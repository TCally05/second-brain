from pathlib import Path

from brain.capture import slugify
from brain.indexer import build_index
from brain.orphans import get_orphans


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


def test_note_with_no_links_at_all_is_an_orphan(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Lonely note")
    db_path = build(vault)

    orphans = get_orphans(db_path)

    assert [o.id for o in orphans] == ["202601151230"]
    assert orphans[0].title == "Lonely note"


def test_note_with_only_incoming_link_is_not_an_orphan(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Linker", "See [[202601151230]].")
    db_path = build(vault)

    orphan_ids = [o.id for o in get_orphans(db_path)]

    assert "202601151230" not in orphan_ids


def test_note_with_only_outgoing_link_is_not_an_orphan(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Linker", "See [[202601151230]].")
    db_path = build(vault)

    orphan_ids = [o.id for o in get_orphans(db_path)]

    assert "202601151231" not in orphan_ids


def test_note_with_only_a_dangling_link_is_still_an_orphan(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Linker", "See [[doesnotexist]].")
    db_path = build(vault)

    assert [o.id for o in get_orphans(db_path)] == ["202601151230"]


def test_no_orphans_returns_empty_list(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "A", "See [[202601151231]].")
    write_note(vault, "202601151231", "B", "See [[202601151230]].")
    db_path = build(vault)

    assert get_orphans(db_path) == []


def test_orphans_ordered_by_id(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151232", "Later orphan")
    write_note(vault, "202601151230", "Earlier orphan")
    db_path = build(vault)

    assert [o.id for o in get_orphans(db_path)] == ["202601151230", "202601151232"]
