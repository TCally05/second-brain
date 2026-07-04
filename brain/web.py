from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for

from brain.backlinks import get_backlinks
from brain.capture import create_note, update_note
from brain.indexer import build_index
from brain.note import Note, NoteParseError
from brain.orphans import get_orphans
from brain.render import render_body
from brain.resurface import get_resurface_candidates
from brain.search import search_notes


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

    @app.route("/")
    def home():
        notes, error = query(_list_notes, db_path)
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
        if request.method == "GET":
            return render_template(
                "note_form.html", heading="New note", note_id=None,
                title="", tags="", body="", error=None,
            )

        title = request.form.get("title", "")
        tags_raw = request.form.get("tags", "")
        body = request.form.get("body", "")

        try:
            note_path = create_note(title, vault_root, tags=_parse_tags(tags_raw), body=body)
        except ValueError as exc:
            return render_template(
                "note_form.html", heading="New note", note_id=None,
                title=title, tags=tags_raw, body=body, error=str(exc),
            ), 400

        build_index(vault_root, db_path)
        new_id = note_path.stem.split("-", 1)[0]
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

        if request.method == "GET":
            note, note_error = read_note(note_path)
            if note_error:
                return render_template("error.html", message=note_error), 500
            return render_template(
                "note_form.html", heading=f"Edit: {db_title}", note_id=note_id,
                title=note.title, tags=", ".join(note.tags), body=note.body, error=None,
            )

        title = request.form.get("title", "")
        tags_raw = request.form.get("tags", "")
        body = request.form.get("body", "")

        try:
            update_note(note_path, note_id, title, _parse_tags(tags_raw), body)
        except ValueError as exc:
            return render_template(
                "note_form.html", heading=f"Edit: {db_title}", note_id=note_id,
                title=title, tags=tags_raw, body=body, error=str(exc),
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


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _list_notes(db_path: Path) -> list[tuple[str, str, list[str]]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, title, tags FROM notes ORDER BY id DESC").fetchall()
    finally:
        conn.close()
    return [(row[0], row[1], json.loads(row[2])) for row in rows]


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
