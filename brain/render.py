from __future__ import annotations

import html
import re

# Same shape as links.WIKILINK_PATTERN, but also captures the alias so it
# can be shown as display text - links.py only needs the target, so it
# doesn't bother.
WIKILINK_RENDER_PATTERN = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")


def render_body(body: str, resolved: dict[str, str | None]) -> str:
    """Turn a note's raw markdown body into safe HTML for the web UI.

    `resolved` maps a wikilink target (as extracted by links.parse_wikilinks)
    to the note id it resolves to, exactly as already computed and stored by
    `brain index` - so this doesn't re-derive link resolution, just renders
    it. A target with no entry (or a None value) becomes a "dangling-link"
    span instead of an anchor. Everything else is HTML-escaped; no other
    markdown formatting (bold, headers, etc.) is applied yet.
    """
    parts: list[str] = []
    pos = 0
    for match in WIKILINK_RENDER_PATTERN.finditer(body):
        parts.append(html.escape(body[pos : match.start()]))

        target = match.group(1).strip()
        alias = match.group(2)
        display = html.escape((alias if alias is not None else target).strip())

        target_id = resolved.get(target)
        if target_id:
            parts.append(f'<a href="/notes/{target_id}">{display}</a>')
        else:
            parts.append(f'<span class="dangling-link">{display}</span>')

        pos = match.end()

    parts.append(html.escape(body[pos:]))
    return "".join(parts)
