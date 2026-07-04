from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from brain.backlinks import get_backlinks
from brain.capture import create_note, update_note
from brain.indexer import build_index
from brain.note import Note, NoteParseError
from brain.orphans import get_orphans
from brain.render import render_body
from brain.resurface import get_resurface_candidates
from brain.search import search_notes
from brain.vault import PARA_FOLDERS


def create_app(vault_root: Path) -> Flask:
    app = Flask(__name__)
    db_path = vault_root / ".brain" / "index.db"

    def query(fn, *args):
        """Run a read query against the index, turning a missing/corrupt
        .brain/index.db into a friendly message instead of a 500 with a
        raw traceback - the same job _query_index does for the CLI."""
        try:
            return fn(*args), None
        except sqlite3.OperationalError as exc:
            return None, f"{exc} — have you run `brain index` yet?"

    def read_note(note_path: Path):
        """Read a note straight off disk, the same live-from-source-of-truth
        read note_detail/edit rely on. The DB only caches a note's path and
        can go stale the moment a file is deleted, moved, or hand-edited
        into something unparsable outside the tool - turn that into a
        friendly message instead of a 500 with a raw traceback."""
        try:
            return Note.from_file(note_path), None
        except (FileNotFoundError, NoteParseError) as exc:
            return None, f"Couldn't read {note_path}: {exc}. Try running `brain index` to refresh the index."

    def get_all_notes():
        """_list_notes result, cached on flask.g so the sidebar (rendered
        on every page via the context processor below) and a route that
        also needs the full note list (home) don't each query it separately
        within the same request."""
        if not hasattr(g, "_all_notes"):
            g._all_notes = query(_list_notes, db_path)
        return g._all_notes

    @app.context_processor
    def inject_sidebar():
        notes, error = get_all_notes()
        return {"sidebar_tree": _group_by_folder(notes or []), "sidebar_error": error}

    @app.route("/")
    def home():
        notes, error = get_all_notes()
        return render_template("home.html", notes=notes, error=error)

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        results, error = (None, None)
        if q:
            results, error = query(search_notes, db_path, q)
        return render_template("search_results.html", query=q, results=results, error=error)

    @app.route("/notes/new", methods=["GET", "POST"])
    def new_note():
        all_tags, _ = query(_list_all_tags, db_path)

        if request.method == "GET":
            return render_template(
                "note_form.html", heading="New note", note_id=None,
                title="", body="", error=None,
                all_tags=all_tags or [], selected_tags=[], new_tags_value="",
            )

        title = request.form.get("title", "")
        body = request.form.get("body", "")
        tags = _collect_tags(request.form)

        try:
            note_path = create_note(title, vault_root, tags=tags, body=body)
        except ValueError as exc:
            return render_template(
                "note_form.html", heading="New note", note_id=None,
                title=title, body=body, error=str(exc),
                all_tags=all_tags or [], selected_tags=request.form.getlist("tags"),
                new_tags_value=request.form.get("new_tags", ""),
            ), 400

        new_id = note_path.stem.split("-", 1)[0]

        attachment = request.files.get("attachment")
        if attachment and attachment.filename:
            note = Note.from_file(note_path)
            link = _attach_file(vault_root, new_id, attachment)
            update_note(note_path, new_id, note.title, note.tags, note.body + link)

        build_index(vault_root, db_path)
        return redirect(url_for("note_detail", note_id=new_id))

    @app.route("/notes/<note_id>/edit", methods=["GET", "POST"])
    def edit_note(note_id):
        record, error = query(_get_note_record, db_path, note_id)
        if error:
            return render_template("error.html", message=error), 500
        if record is None:
            abort(404)

        db_title, path, _tags_json, _resolved = record
        note_path = vault_root / path
        all_tags, _ = query(_list_all_tags, db_path)

        if request.method == "GET":
            note, note_error = read_note(note_path)
            if note_error:
                return render_template("error.html", message=note_error), 500
            return render_template(
                "note_form.html", heading=f"Edit: {db_title}", note_id=note_id,
                title=note.title, body=note.body, error=None,
                all_tags=all_tags or [], selected_tags=note.tags, new_tags_value="",
            )

        title = request.form.get("title", "")
        body = request.form.get("body", "")
        tags = _collect_tags(request.form)

        attachment = request.files.get("attachment")
        if attachment and attachment.filename:
            body += _attach_file(vault_root, note_id, attachment)

        try:
            update_note(note_path, note_id, title, tags, body)
        except ValueError as exc:
            return render_template(
                "note_form.html", heading=f"Edit: {db_title}", note_id=note_id,
                title=title, body=body, error=str(exc),
                all_tags=all_tags or [], selected_tags=request.form.getlist("tags"),
                new_tags_value=request.form.get("new_tags", ""),
            ), 400
        except FileNotFoundError as exc:
            return render_template(
                "error.html",
                message=f"Couldn't save {note_path}: {exc}. Try running `brain index` to refresh the index.",
            ), 500

        build_index(vault_root, db_path)
        return redirect(url_for("note_detail", note_id=note_id))

    @app.route("/notes/<note_id>")
    def note_detail(note_id):
        record, error = query(_get_note_record, db_path, note_id)
        if error:
            return render_template("error.html", message=error), 500
        if record is None:
            abort(404)

        title, path, tags_json, resolved = record
        note, note_error = read_note(vault_root / path)
        if note_error:
            return render_template("error.html", message=note_error), 500
        body_html = render_body(note.body, resolved)
        backlinks, _ = query(get_backlinks, db_path, note_id)

        return render_template(
            "note_detail.html",
            note_id=note_id,
            title=title,
            tags=json.loads(tags_json),
            path=path,
            body_html=body_html,
            backlinks=backlinks or [],
        )

    @app.route("/attachments/<path:filename>")
    def attachment(filename):
        return send_from_directory(vault_root / "attachments", filename)

    @app.route("/graph")
    def graph():
        return render_template("graph.html")

    @app.route("/graph-data")
    def graph_data():
        notes, error = get_all_notes()
        if error:
            return jsonify(error=error), 500

        links, link_error = query(_list_resolved_links, db_path)
        if link_error:
            return jsonify(error=link_error), 500

        nodes = [
            {"id": note_id, "title": title, "group": path.split("/", 1)[0]}
            for note_id, title, _tags, path in (notes or [])
        ]
        return jsonify(nodes=nodes, links=links or [])

    @app.route("/orphans")
    def orphans():
        notes, error = query(get_orphans, db_path)
        return render_template("orphans.html", notes=notes, error=error)

    @app.route("/resurface")
    def resurface():
        count = request.args.get("count", 5, type=int)
        notes, error = query(get_resurface_candidates, db_path, count)
        return render_template("resurface.html", notes=notes, error=error, count=count)

    return app


def _attach_file(vault_root: Path, note_id: str, uploaded) -> str:
    """Save an uploaded file into vault_root/attachments and return a
    markdown link to append to the note body. Never overwrites an existing
    attachment - if the sanitized filename collides with one already on
    disk (e.g. the same note gets a second "report.pdf"), a numeric suffix
    is added instead, the same "disambiguate rather than clobber" instinct
    generate_id already applies to id collisions."""
    safe_name = secure_filename(uploaded.filename) or "attachment"
    attachments_dir = vault_root / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    filename = f"{note_id}-{safe_name}"
    n = 1
    while (attachments_dir / filename).exists():
        filename = f"{note_id}-{stem}-{n}{suffix}"
        n += 1

    uploaded.save(attachments_dir / filename)
    rel_url = quote(f"attachments/{filename}")
    return f"\n\n📎 [{uploaded.filename}]({rel_url})"


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _collect_tags(form) -> list[str]:
    """Combine the checked existing-tag checkboxes with whatever was typed
    into the free-text "new tags" field, deduped in the order encountered
    - checkboxes give a dropdown-style pick list of tags already used
    elsewhere in the vault, without closing off adding a brand new one."""
    combined = form.getlist("tags") + _parse_tags(form.get("new_tags", ""))
    seen: set[str] = set()
    result: list[str] = []
    for t in combined:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _list_all_tags(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT tags FROM notes").fetchall()
    finally:
        conn.close()
    tags: set[str] = set()
    for (tags_json,) in rows:
        tags.update(json.loads(tags_json))
    return sorted(tags)


def _list_notes(db_path: Path) -> list[tuple[str, str, list[str], str]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, title, tags, path FROM notes ORDER BY title COLLATE NOCASE"
        ).fetchall()
    finally:
        conn.close()
    return [(row[0], row[1], json.loads(row[2]), row[3]) for row in rows]


def _group_by_folder(
    notes: list[tuple[str, str, list[str], str]],
) -> dict[str, list[tuple[str, str]]]:
    """Group notes by their top-level PARA folder for the sidebar's file
    tree, in the vault's canonical folder order (vault.PARA_FOLDERS) -
    every folder is shown even if empty, matching a real file explorer."""
    tree: dict[str, list[tuple[str, str]]] = {folder: [] for folder in PARA_FOLDERS}
    for note_id, title, _tags, path in notes:
        folder = path.split("/", 1)[0]
        tree.setdefault(folder, []).append((note_id, title))
    return tree


def _list_resolved_links(db_path: Path) -> list[dict[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT source_id, target_id FROM links WHERE target_id IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    return [{"source": row[0], "target": row[1]} for row in rows]


def _get_note_record(db_path: Path, note_id: str):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT title, path, tags FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None

        resolved = dict(
            conn.execute(
                "SELECT target, target_id FROM links WHERE source_id = ?", (note_id,)
            ).fetchall()
        )
    finally:
        conn.close()
    return (row[0], row[1], row[2], resolved)
