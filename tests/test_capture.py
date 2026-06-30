from datetime import datetime
from pathlib import Path

import pytest

from brain.capture import create_note, existing_note_ids, generate_id, slugify
from brain.note import Note


def make_vault(tmp_path: Path) -> Path:
    for folder in ("inbox", "projects", "areas", "resources", "archives"):
        (tmp_path / folder).mkdir()
    return tmp_path


@pytest.mark.parametrize(
    "title, expected",
    [
        ("My Cool Note", "my-cool-note"),
        ("  leading and trailing  ", "leading-and-trailing"),
        ("Weird!!  Punctuation??", "weird-punctuation"),
        ("日本語", "note"),  # no ascii alnum chars -> fall back to "note"
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_generate_id_with_no_collisions():
    now = datetime(2026, 1, 15, 12, 30)
    assert generate_id(existing_ids=set(), now=now) == "202601151230"


def test_generate_id_bumps_forward_on_collision():
    now = datetime(2026, 1, 15, 12, 30)
    taken = {"202601151230", "202601151231"}
    assert generate_id(existing_ids=taken, now=now) == "202601151232"


def test_existing_note_ids_scans_all_para_folders(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "inbox" / "202601010000-a.md").write_text("a")
    (vault / "projects" / "202601020000-b.md").write_text("b")

    assert existing_note_ids(vault) == {"202601010000", "202601020000"}


def test_existing_note_ids_ignores_hidden_dirs(tmp_path):
    vault = make_vault(tmp_path)
    hidden = vault / ".brain"
    hidden.mkdir()
    (hidden / "202601010000-cached.md").write_text("cached")

    assert existing_note_ids(vault) == set()


def test_create_note_writes_file_in_inbox(tmp_path):
    vault = make_vault(tmp_path)

    note_path = create_note("My Cool Note", vault)

    assert note_path.parent == vault / "inbox"
    assert note_path.name.endswith("-my-cool-note.md")
    assert note_path.exists()


def test_create_note_output_parses_back_into_a_valid_note(tmp_path):
    vault = make_vault(tmp_path)

    note_path = create_note("Round trip note", vault)
    note = Note.from_file(note_path)

    assert note.id == note_path.name.split("-", 1)[0]
    assert note.title == "Round trip note"
    assert note.tags == []


def test_create_note_rejects_blank_title(tmp_path):
    vault = make_vault(tmp_path)

    with pytest.raises(ValueError, match="title must not be empty"):
        create_note("   ", vault)


def test_create_note_avoids_id_collision(tmp_path):
    vault = make_vault(tmp_path)
    first = create_note("First note", vault)
    second = create_note("Second note", vault)

    first_id = first.name.split("-", 1)[0]
    second_id = second.name.split("-", 1)[0]
    assert first_id != second_id
