from __future__ import annotations

import re

# Matches [[target]] or [[target|alias]]. The target can't itself contain
# brackets or a pipe; the alias (if present) can't contain brackets.
WIKILINK_PATTERN = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]*)?\]\]")


def parse_wikilinks(body: str) -> list[str]:
    """Extract link targets (ids or slugs) from [[target]] / [[target|alias]]
    references in a note body, in first-seen order with duplicates removed.

    Does not distinguish id-style vs slug-style targets, and does not
    exclude links inside code blocks/inline code - that's left to the
    caller (the eventual `brain index` step) which has the full corpus
    needed to resolve a target into an actual note.
    """
    seen: dict[str, None] = {}
    for match in WIKILINK_PATTERN.finditer(body):
        target = match.group(1).strip()
        if target:
            seen.setdefault(target, None)
    return list(seen)
