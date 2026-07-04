import random
from pathlib import Path

from brain.capture import slugify
from brain.indexer import build_index
from brain.resurface import get_resurface_candidates


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


def test_empty_vault_returns_empty_list(tmp_path):
    vault = make_vault(tmp_path)
    db_path = build(vault)

    assert get_resurface_candidates(db_path, count=5) == []


def test_returns_at_most_count_notes_without_duplicates(tmp_path):
    vault = make_vault(tmp_path)
    for i in range(3):
        write_note(vault, f"20260115123{i}", f"Note {i}")
    db_path = build(vault)

    picked = get_resurface_candidates(db_path, count=2, rng=random.Random(1))

    assert len(picked) == 2
    assert len(set(n.id for n in picked)) == 2


def test_returns_all_notes_when_count_exceeds_total(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "A")
    write_note(vault, "202601151231", "B")
    db_path = build(vault)

    picked = get_resurface_candidates(db_path, count=10, rng=random.Random(1))

    assert sorted(n.id for n in picked) == ["202601151230", "202601151231"]


def test_link_count_reflects_both_incoming_and_outgoing(tmp_path):
    vault = make_vault(tmp_path)
    # Mutual link: each note has one outgoing edge and one incoming edge,
    # so link_count (edges touching the note, either direction) is 2 each.
    write_note(vault, "202601151230", "Hub", "See [[202601151231]].")
    write_note(vault, "202601151231", "Linked back", "See [[202601151230]].")
    write_note(vault, "202601151232", "Isolated")
    db_path = build(vault)

    picked = {n.id: n for n in get_resurface_candidates(db_path, count=10, rng=random.Random(1))}

    assert picked["202601151230"].link_count == 2
    assert picked["202601151231"].link_count == 2
    assert picked["202601151232"].link_count == 0


def test_dangling_link_does_not_count(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Has dangling link", "See [[doesnotexist]].")
    db_path = build(vault)

    picked = get_resurface_candidates(db_path, count=1, rng=random.Random(1))

    assert picked[0].link_count == 0


def test_weighting_favors_less_connected_notes(tmp_path):
    # random.choices assigns each item probability weight_i / sum(weights),
    # so the ratio between any two specific items' pick odds equals the
    # ratio of their weights, regardless of what else is in the pool. Here
    # isolated has weight 1/(0+1)=1 and popular has weight 1/(10+1)=1/11,
    # so isolated should be chosen ~11x as often as popular head-to-head.
    vault = make_vault(tmp_path)
    write_note(vault, "202601151230", "Isolated")
    write_note(vault, "202601151231", "Popular")
    for i in range(10):
        write_note(vault, f"20260115124{i}", f"Linker {i}", "See [[202601151231]].")
    db_path = build(vault)

    rng = random.Random(42)
    isolated_wins = 0
    popular_wins = 0
    for _ in range(1000):
        picked = get_resurface_candidates(db_path, count=1, rng=rng)[0].id
        if picked == "202601151230":
            isolated_wins += 1
        elif picked == "202601151231":
            popular_wins += 1

    assert isolated_wins > popular_wins * 3
