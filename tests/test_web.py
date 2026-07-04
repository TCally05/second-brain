import io
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


def write_note_in(vault: Path, folder: str, id_: str, title: str, body: str = "") -> Path:
    text = f"---\nid: {id_!r}\ntitle: {title}\ntags: []\n---\n\n{body}"
    path = vault / folder / f"{id_}-{slugify(title)}.md"
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


def test_note_detail_handles_file_deleted_after_indexing(tmp_path):
    vault = make_vault(tmp_path)
    note_path = write_note(vault, "202601151230", "Will vanish")
    client = client_for(vault)
    note_path.unlink()

    resp = client.get("/notes/202601151230")

    assert resp.status_code == 500
    assert b"brain index" in resp.data


def test_note_detail_handles_file_corrupted_after_indexing(tmp_path):
    vault = make_vault(tmp_path)
    note_path = write_note(vault, "202601151230", "Will be corrupted")
    client = client_for(vault)
    note_path.write_text("no frontmatter anymore", encoding="utf-8")

    resp = client.get("/notes/202601151230")

    assert resp.status_code == 500
    assert b"brain index" in resp.data


def test_edit_note_get_handles_file_deleted_after_indexing(tmp_path):
    vault = make_vault(tmp_path)
    note_path = write_note(vault, "202601151230", "Will vanish")
    client = client_for(vault)
    note_path.unlink()

    resp = client.get("/notes/202601151230/edit")

    assert resp.status_code == 500
    assert b"brain index" in resp.data


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


def test_new_note_get_shows_empty_form(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/notes/new")

    assert resp.status_code == 200
    assert b"New note" in resp.data


def test_new_note_post_creates_note_and_is_findable_without_manual_reindex(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.post(
        "/notes/new",
        data={"title": "Created via UI", "new_tags": "web, ui", "body": "Some body text."},
    )

    assert resp.status_code == 302
    created = list((vault / "inbox").glob("*.md"))
    assert len(created) == 1

    home_resp = client.get("/")
    assert b"Created via UI" in home_resp.data

    search_resp = client.get("/search?q=body")
    assert b"Created via UI" in search_resp.data


def test_new_note_post_blank_title_shows_error_and_no_file_created(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.post("/notes/new", data={"title": "   ", "body": ""})

    assert resp.status_code == 400
    assert b"title must not be empty" in resp.data
    assert list((vault / "inbox").glob("*.md")) == []


def test_edit_note_get_shows_prefilled_form(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Original title", "Original body.")
    client = client_for(vault)

    resp = client.get("/notes/202601151230/edit")

    assert resp.status_code == 200
    assert b"Original title" in resp.data
    assert b"Original body." in resp.data


def test_edit_note_unknown_id_returns_404(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/notes/999999999999/edit")

    assert resp.status_code == 404


def test_edit_note_post_updates_content_and_is_reflected_without_manual_reindex(tmp_path):
    vault = make_vault(tmp_path)
    note_path = write_note(vault, "202601151230", "Original title", "Original body.")
    client = client_for(vault)

    resp = client.post(
        "/notes/202601151230/edit",
        data={"title": "Updated title", "new_tags": "edited", "body": "Updated body."},
    )

    assert resp.status_code == 302
    assert note_path.exists()  # filename/id are never changed by an edit

    detail_resp = client.get("/notes/202601151230")
    assert b"Updated title" in detail_resp.data
    assert b"Updated body." in detail_resp.data
    assert b"Original body." not in detail_resp.data


def test_edit_note_post_blank_title_shows_error_and_does_not_overwrite(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Original title", "Original body.")
    client = client_for(vault)

    resp = client.post(
        "/notes/202601151230/edit",
        data={"title": "   ", "body": "Attempted overwrite."},
    )

    assert resp.status_code == 400
    assert b"title must not be empty" in resp.data

    detail_resp = client.get("/notes/202601151230")
    assert b"Original title" in detail_resp.data


def test_graph_page_renders(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Some note")
    client = client_for(vault)

    resp = client.get("/graph")

    assert resp.status_code == 200
    assert b"graph-canvas" in resp.data


def test_graph_data_reflects_notes_and_resolved_links(tmp_path):
    vault = make_vault(tmp_path)
    write_note_in(vault, "inbox", "202601151230", "Target note")
    write_note_in(vault, "projects", "202601151231", "Linker note", "See [[202601151230]].")
    client = client_for(vault)

    resp = client.get("/graph-data")

    assert resp.status_code == 200
    data = resp.get_json()
    nodes_by_id = {n["id"]: n for n in data["nodes"]}
    assert nodes_by_id["202601151230"]["group"] == "inbox"
    assert nodes_by_id["202601151231"]["group"] == "projects"
    assert {"source": "202601151231", "target": "202601151230"} in data["links"]


def test_graph_data_excludes_dangling_links(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Has dangling link", "See [[doesnotexist]].")
    client = client_for(vault)

    resp = client.get("/graph-data")

    assert resp.status_code == 200
    assert resp.get_json()["links"] == []


def test_graph_data_empty_vault(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/graph-data")

    assert resp.status_code == 200
    assert resp.get_json() == {"nodes": [], "links": []}


def test_graph_data_without_index_returns_json_error(tmp_path):
    vault = make_vault(tmp_path)
    app = create_app(vault)
    app.testing = True

    resp = app.test_client().get("/graph-data")

    assert resp.status_code == 500
    assert "brain index" in resp.get_json()["error"]


def test_new_note_with_attachment_saves_file_and_links_it(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.post(
        "/notes/new",
        data={
            "title": "Note with attachment",
            "body": "See the attached report.",
            "attachment": (io.BytesIO(b"%PDF-1.4 fake pdf content"), "report.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 302
    saved = list((vault / "attachments").glob("*report.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"%PDF-1.4 fake pdf content"

    new_id = resp.location.rsplit("/", 1)[-1]
    detail_resp = client.get(f"/notes/{new_id}")
    assert b"report.pdf" in detail_resp.data
    assert b'href="attachments/' in detail_resp.data


def test_edit_note_with_attachment_appends_link_and_keeps_existing_body(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Existing note", "Original text.")
    client = client_for(vault)

    resp = client.post(
        "/notes/202601151230/edit",
        data={
            "title": "Existing note",
            "body": "Original text.",
            "attachment": (io.BytesIO(b"fake spreadsheet"), "budget.xlsx"),
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 302
    detail_resp = client.get("/notes/202601151230")
    assert b"Original text." in detail_resp.data
    assert b"budget.xlsx" in detail_resp.data


def test_attachment_is_served_and_downloadable(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    client.post(
        "/notes/new",
        data={
            "title": "Has a file",
            "body": "",
            "attachment": (io.BytesIO(b"hello world"), "notes.docx"),
        },
        content_type="multipart/form-data",
    )
    saved = list((vault / "attachments").glob("*notes.docx"))[0]

    resp = client.get(f"/attachments/{saved.name}")

    assert resp.status_code == 200
    assert resp.data == b"hello world"


def test_attachment_upload_does_not_overwrite_existing_file(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Note A")
    write_note(vault, "202601151231", "Note B")
    client = client_for(vault)

    for note_id in ("202601151230", "202601151231"):
        client.post(
            f"/notes/{note_id}/edit",
            data={
                "title": "Note",
                    "body": "",
                "attachment": (io.BytesIO(f"content for {note_id}".encode()), "same-name.txt"),
            },
            content_type="multipart/form-data",
        )

    saved = sorted((vault / "attachments").glob("*same-name*"))
    assert len(saved) == 2
    assert saved[0].read_bytes() != saved[1].read_bytes()


def test_unknown_attachment_returns_404(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/attachments/does-not-exist.pdf")

    assert resp.status_code == 404


def test_new_note_form_offers_existing_tags_as_checkboxes(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Tagged note", "")
    client = client_for(vault)
    client.post(
        "/notes/202601151230/edit",
        data={"title": "Tagged note", "new_tags": "work, urgent", "body": ""},
    )

    resp = client.get("/notes/new")

    assert resp.status_code == 200
    assert b'value="work"' in resp.data
    assert b'value="urgent"' in resp.data


def test_new_note_with_no_existing_tags_shows_empty_state(tmp_path):
    vault = make_vault(tmp_path)
    client = client_for(vault)

    resp = client.get("/notes/new")

    assert resp.status_code == 200
    assert b"No existing tags yet" in resp.data


def test_new_note_post_combines_checked_tags_and_new_tags(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Existing tagger", "")
    client = client_for(vault)
    client.post(
        "/notes/202601151230/edit",
        data={"title": "Existing tagger", "new_tags": "work", "body": ""},
    )

    resp = client.post(
        "/notes/new",
        data={"title": "New tagged note", "tags": ["work"], "new_tags": "fresh", "body": ""},
    )

    assert resp.status_code == 302
    new_id = resp.location.rsplit("/", 1)[-1]
    created = [p for p in (vault / "inbox").glob("*.md") if p.stem.startswith(new_id)][0]
    text = created.read_text()
    assert "work" in text
    assert "fresh" in text


def test_edit_note_get_checks_the_notes_current_tags(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Has tags", "")
    client = client_for(vault)
    client.post(
        "/notes/202601151230/edit",
        data={"title": "Has tags", "new_tags": "alpha, beta", "body": ""},
    )

    resp = client.get("/notes/202601151230/edit")

    assert b'value="alpha" checked' in resp.data
    assert b'value="beta" checked' in resp.data


def test_edit_note_can_uncheck_a_tag_to_remove_it(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Has tags", "")
    client = client_for(vault)
    client.post(
        "/notes/202601151230/edit",
        data={"title": "Has tags", "new_tags": "alpha, beta", "body": ""},
    )

    # Resubmit with only "beta" checked (as if "alpha" was unchecked in the browser).
    resp = client.post(
        "/notes/202601151230/edit",
        data={"title": "Has tags", "tags": ["beta"], "new_tags": "", "body": ""},
    )

    assert resp.status_code == 302
    detail_resp = client.get("/notes/202601151230")
    assert b"beta" in detail_resp.data
    assert b">alpha<" not in detail_resp.data
