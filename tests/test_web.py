from pathlib import Path

from brain.capture import slugify
from brain.indexer import build_index
from brain.web import create_app


def make_vault(tmp_path: Path) -> Path:
    for folder in ("inbox", "projects", "areas", "resources", "archives"):
        (tmp_path / folder).mkdir()
    return tmp_path


def write_note(vault: Path, id_: str, title: str, body: str = "") -> Path:
    text = f"---\nid: {id_!r}\ntitle: {title}\ntags: []\n---\n\n{body}"
    path = vault / "inbox" / f"{id_}-{slugify(title)}.md"
    path.write_text(text, encoding="utf-8")
    return path


def client_for(vault: Path):
    build_index(vault, vault / ".brain" / "index.db")
    app = create_app(vault)
    app.testing = True
    return app.test_client()


def test_home_lists_notes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A")

    resp = client_for(vault).get("/")

    assert resp.status_code == 200
    assert b"Note A" in resp.data


def test_home_without_index_shows_friendly_message(tmp_path):
    vault = make_vault(tmp_path)
    app = create_app(vault)
    app.testing = True

    resp = app.test_client().get("/")

    assert resp.status_code == 200
    assert b"brain index" in resp.data


def test_note_detail_renders_body_with_resolved_wikilink(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note", "Nothing here.")
    write_note(vault, "202601151231", "Linker note", "See [[202601151230]].")
    client = client_for(vault)

    resp = client.get("/notes/202601151231")

    assert resp.status_code == 200
    assert b"Linker note" in resp.data
    assert b'href="/notes/202601151230"' in resp.data


def test_note_detail_shows_backlinks(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Target note")
    write_note(vault, "202601151231", "Linker note", "See [[202601151230]].")
    client = client_for(vault)

    resp = client.get("/notes/202601151230")

    assert resp.status_code == 200
    assert b"Linker note" in resp.data


def test_unknown_note_returns_404(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/notes/999999999999")

    assert resp.status_code == 404


def test_search_returns_matching_notes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Zettelkasten strategy")
    client = client_for(vault)

    resp = client.get("/search?q=zettelkasten")

    assert resp.status_code == 200
    assert b"Zettelkasten strategy" in resp.data


def test_search_without_query_shows_hint(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/search")

    assert resp.status_code == 200
    assert b"Type a search term" in resp.data


def test_orphans_page_lists_unlinked_notes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Lonely note")
    client = client_for(vault)

    resp = client.get("/orphans")

    assert resp.status_code == 200
    assert b"Lonely note" in resp.data


def test_resurface_page_lists_notes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Some note")
    client = client_for(vault)

    resp = client.get("/resurface")

    assert resp.status_code == 200
    assert b"Some note" in resp.data
