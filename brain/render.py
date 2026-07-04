from __future__ import annotations

import html
import re

# Two link shapes, matched in one pass so position order is preserved:
#  - [[target]] / [[target|alias]] - a wikilink between notes.
#  - [text](url) - a plain markdown link, used for attachments
#    (e.g. "[report.pdf](attachments/202601151230-report.pdf)").
# The wikilink's double brackets structurally can't be mistaken for the
# markdown form, since the latter requires "(" immediately after "]".
LINK_PATTERN = re.compile(
    r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]"
    r"|\[([^\[\]]+)\]\(([^()]+)\)"
)

# Schemes that could execute script/inline content if used as a href - a
# note is normally only ever written by the note's own owner, but there's
# no reason to let a copy-pasted markdown link turn into a live foot-gun.
_UNSAFE_URL_SCHEMES = ("javascript:", "data:", "vbscript:")


def render_body(body: str, resolved: dict[str, str | None]) -> str:
    """Turn a note's raw markdown body into safe HTML for the web UI.

    `resolved` maps a wikilink target (as extracted by links.parse_wikilinks)
    to the note id it resolves to, exactly as already computed and stored by
    `brain index` - so this doesn't re-derive link resolution, just renders
    it. A target with no entry (or a None value) becomes a "dangling-link"
    span instead of an anchor. A plain markdown link renders as a normal
    anchor to its url as-is (used for attachments, but works for any link).
    Everything else is HTML-escaped; no other markdown formatting (bold,
    headers, etc.) is applied yet.
    """
    parts: list[str] = []
    pos = 0
    for match in LINK_PATTERN.finditer(body):
        parts.append(html.escape(body[pos : match.start()]))

        if match.group(1) is not None:
            target = match.group(1).strip()
            alias = match.group(2)
            display = html.escape((alias if alias is not None else target).strip())

            target_id = resolved.get(target)
            if target_id:
                parts.append(f'<a href="/notes/{target_id}">{display}</a>')
            else:
                parts.append(f'<span class="dangling-link">{display}</span>')
        else:
            text = html.escape(match.group(3).strip())
            url = match.group(4).strip()
            if url.lower().startswith(_UNSAFE_URL_SCHEMES):
                parts.append(f'<span class="dangling-link">{text}</span>')
            else:
                parts.append(f'<a href="{html.escape(url, quote=True)}">{text}</a>')

        pos = match.end()

    parts.append(html.escape(body[pos:]))
    return "".join(parts)
