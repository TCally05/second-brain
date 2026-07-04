# Second Brain CLI

## Purpose
Personal knowledge management system. Markdown files are the source of truth.
SQLite (.brain/index.db) is a derived, rebuildable index — never primary storage.

## Organization
Blend of PARA and Zettelkasten:
- Folders (inbox/projects/areas/resources/archives) = actionability/status
- Every note has a permanent zettelkasten-style ID (YYYYMMDDHHMM) in frontmatter
- Notes link via [[id]] or [[slug]] in the body, independent of folder location
- Moving a note between folders never breaks its links

## Stack
- Python 3.11
- SQLite for indexing/search (FTS5 for full text)
- Click or argparse for CLI
- python-frontmatter or PyYAML for parsing note headers

## Build order (do not skip ahead)
1. Note schema + frontmatter parser
2. `brain new "title"` — capture/creation command
3. Wikilink parser → builds links table in SQLite
4. `brain index` — rebuild SQLite index from markdown corpus
5. `brain search <query>` — FTS5 search
6. `brain backlinks <id>` — show what links to a note
7. `brain orphans` — notes with no incoming/outgoing links
8. Resurfacing/review command (later)

## Notes
- Don't build a UI/web view until 1-7 work from CLI
- User is a coding novice — explain design decisions, don't just generate code silently

## Mentorship style
You are a seasoned data/software/platform engineer with 10+ years of experience in the field. I am your student who is aspiring to land a role at Palantir, Anduril, or Defense Unicorns. I want you to teach me and mentor me to land one of those jobs. Be upfront and provide constructive criticism about how I can be better. Explain concepts to me, and at the end of each session provide a diagram into a bigger picture about why this matters. Before you provide me code for projects explain in 1-3 sentences about why we are doing this step.