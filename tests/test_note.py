from datetime import datetime
from pathlib import Path

import pytest

from brain.note import Note, NoteParseError

VALID_NOTE = """---
id: 202601151230
title: A test note
tags: [zettelkasten, testing]
---

This is the body of the note. It links to [[202601151231]].
"""


def write_note(tmp_path: Path, text: str, name: str = "note.md") -> Path:
    note_path = tmp_path / name
    note_path.write_text(text, encoding="utf-8")
    return note_path


def test_parses_valid_note(tmp_path):
    path = write_note(tmp_path, VALID_NOTE)

    note = Note.from_file(path)

    assert note.id == "202601151230"
    assert note.title == "A test note"
    assert note.tags == ["zettelkasten", "testing"]
    assert "links to [[202601151231]]" in note.body
    assert note.path == path


def test_created_is_derived_from_id(tmp_path):
    path = write_note(tmp_path, VALID_NOTE)

    note = Note.from_file(path)

    assert note.created == datetime(2026, 1, 15, 12, 30)


def test_tags_default_to_empty_list(tmp_path):
    text = """---
id: 202601151230
title: No tags here
---

Body text.
"""
    note = Note.from_file(write_note(tmp_path, text))

    assert note.tags == []


def test_missing_frontmatter_raises(tmp_path):
    path = write_note(tmp_path, "Just a plain markdown file, no frontmatter.\n")

    with pytest.raises(NoteParseError, match="no frontmatter"):
        Note.from_file(path)


def test_malformed_frontmatter_block_raises(tmp_path):
    # Only one '---' delimiter, never closed.
    path = write_note(tmp_path, "---\nid: 202601151230\ntitle: Broken\n")

    with pytest.raises(NoteParseError, match="malformed frontmatter"):
        Note.from_file(path)


def test_missing_id_raises(tmp_path):
    text = """---
title: No id field
---

Body.
"""
    with pytest.raises(NoteParseError, match="missing or malformed id"):
        Note.from_file(write_note(tmp_path, text))


@pytest.mark.parametrize(
    "bad_id",
    [
        "abc",  # not digits
        "2026011512",  # too short
        "20260115123000",  # too long
    ],
)
def test_malformed_id_raises(tmp_path, bad_id):
    text = f"""---
id: {bad_id!r}
title: Bad id
---

Body.
"""
    with pytest.raises(NoteParseError, match="missing or malformed id"):
        Note.from_file(write_note(tmp_path, text))


def test_missing_title_raises(tmp_path):
    text = """---
id: 202601151230
---

Body.
"""
    with pytest.raises(NoteParseError, match="missing title"):
        Note.from_file(write_note(tmp_path, text))


def test_non_list_tags_raises(tmp_path):
    text = """---
id: 202601151230
title: Bad tags
tags: not-a-list
---

Body.
"""
    with pytest.raises(NoteParseError, match="tags must be a list"):
        Note.from_file(write_note(tmp_path, text))


def test_body_with_horizontal_rule_is_not_truncated(tmp_path):
    # A '---' inside the body (e.g. a markdown horizontal rule) must not be
    # mistaken for another frontmatter delimiter.
    text = """---
id: 202601151230
title: Has a rule
---

Above the rule.

---

Below the rule.
"""
    note = Note.from_file(write_note(tmp_path, text))

    assert "Above the rule." in note.body
    assert "Below the rule." in note.body
