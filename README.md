# Second Brain

A command-line personal knowledge management system. Markdown files are the
source of truth; a SQLite index (`.brain/index.db`) is derived from them and
can always be rebuilt from scratch.

Organization blends PARA and Zettelkasten:

- Folders (`inbox/`, `projects/`, `areas/`, `resources/`, `archives/`) track
  actionability/status.
- Every note has a permanent id (`YYYYMMDDHHMM`) in its frontmatter.
- Notes link to each other via `[[id]]` or `[[slug]]` in the body, so moving
  a note between folders never breaks a link.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run commands from the root of your vault (the directory containing
`inbox/`, `projects/`, etc.) — `brain` always treats the current working
directory as the vault root.

## Commands

### `brain new` — capture a note

Creates a new note in `inbox/` with a generated id and empty frontmatter,
and prints the path to the file.

```
$ brain new "Zettelkasten linking strategy"
/home/you/vault/inbox/202601151230-zettelkasten-linking-strategy.md
```

### `brain index` — rebuild the SQLite index

Walks every markdown file under the PARA folders, parses its frontmatter,
and rebuilds `.brain/index.db` from scratch (full text, tags, and the link
graph). Run this after adding or editing notes and before `search`,
`backlinks`, `orphans`, or `resurface`.

```
$ brain index
Indexed 42 notes.
```

Notes that fail to parse (bad or missing id, missing title, two notes
sharing an id, etc.) are skipped and reported, and the command exits
non-zero:

```
$ brain index
Indexed 41 notes.
  SKIPPED inbox/broken-note.md: missing or malformed id in inbox/broken-note.md: expected YYYYMMDDHHMM, got None
```

Two different notes that slugify to the same thing (e.g. both titled
"Meeting Notes") don't get skipped, but any `[[slug]]`-style link to that
slug is left unresolved rather than guessing which note you meant — link
by id instead, or rename one of them:

```
$ brain index
Indexed 42 notes.
  WARNING: slug 'meeting-notes' is ambiguous between inbox/202601151230-meeting-notes.md, inbox/202601151231-meeting-notes.md - [[links]] to it will not resolve until you disambiguate (e.g. link by id instead)
```

### `brain search` — full-text search

Searches note titles and bodies via SQLite FTS5. The query is passed
straight to FTS5, so its syntax works directly: `foo`, `"exact phrase"`,
`foo*` (prefix), `foo AND bar`, `foo NOT bar`.

```
$ brain search zettelkasten
202601151230  Zettelkasten linking strategy  (inbox/202601151230-zettelkasten-linking-strategy.md)
    ...ideas about [zettelkasten] linking that connect notes...
```

```
$ brain search nonsense
No matches.
```

### `brain backlinks <id>` — what links to this note

Shows every note that links to the given id, ordered by id.

```
$ brain backlinks 202601151230
202601151231  A note that references it  (inbox/202601151231-a-note-that-references-it.md)
```

```
$ brain backlinks 202601151230
No notes link to 202601151230.
```

If the id isn't in the index at all (likely a typo), it errors instead of
returning an empty list:

```
$ brain backlinks 999999999999
No note with id 999999999999 found in the index.
```

### `brain orphans` — notes with no links

Lists notes that have neither incoming nor outgoing resolved links — the
loose ends of your Zettelkasten worth connecting up or archiving.

```
$ brain orphans
202601151232  A note nobody links to and that links nowhere  (inbox/202601151232-...md)
```

```
$ brain orphans
No orphan notes.
```

### `brain resurface` — revisit old or under-linked notes

Picks a random sample of notes to review, weighted toward ones with fewer
links — the idea being that poorly-connected notes are the ones most worth
another look. Every note has some chance of coming up regardless of how
well-linked it already is.

```
$ brain resurface
202601151232  A note nobody links to and that links nowhere  (inbox/202601151232-...md)  [0 links]
202601151230  Zettelkasten linking strategy  (inbox/202601151230-zettelkasten-linking-strategy.md)  [2 links]
```

Control how many notes come back with `-n`/`--count` (default 5):

```
$ brain resurface --count 10
```

### `brain serve` — browse and edit the vault in a browser

Runs a local web UI: browse all notes, search, view a note with its
`[[wikilinks]]` rendered as clickable links, see its backlinks, browse
`orphans`/`resurface`, and create or edit notes with "New note" and "Edit".
Saving re-runs the index automatically, so changes show up immediately —
no need to run `brain index` by hand. Editing a note never renames its
file, so any `[[slug]]`-style links pointing at it keep working.

```
$ brain serve
 * Running on http://127.0.0.1:5000
```

Then open `http://127.0.0.1:5000` in a browser. Change the port with
`--port`, or pass `--debug` for the Flask auto-reloading dev server.

## Development

```
pytest
```
