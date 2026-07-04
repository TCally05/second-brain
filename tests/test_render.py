from brain.render import render_body


def test_plain_text_is_html_escaped():
    assert render_body("<script>alert(1)</script>", {}) == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_resolved_link_becomes_anchor():
    out = render_body("See [[202601151230]].", {"202601151230": "202601151230"})
    assert '<a href="/notes/202601151230">202601151230</a>' in out


def test_unresolved_link_becomes_dangling_span():
    out = render_body("See [[nope]].", {"nope": None})
    assert '<span class="dangling-link">nope</span>' in out


def test_target_absent_from_resolved_map_also_becomes_dangling_span():
    out = render_body("See [[nope]].", {})
    assert '<span class="dangling-link">nope</span>' in out


def test_alias_is_used_as_display_text():
    out = render_body("See [[202601151230|my note]].", {"202601151230": "202601151230"})
    assert '<a href="/notes/202601151230">my note</a>' in out


def test_alias_text_is_escaped():
    out = render_body("See [[202601151230|<b>bold</b>]].", {"202601151230": "202601151230"})
    assert "&lt;b&gt;bold&lt;/b&gt;" in out
    assert "<b>bold</b>" not in out


def test_surrounding_text_is_preserved():
    out = render_body("before [[a]] after", {"a": None})
    assert out.startswith("before ")
    assert out.endswith(" after")


def test_multiple_links_all_rendered():
    out = render_body("[[a]] and [[b]]", {"a": "111111111111", "b": None})
    assert '<a href="/notes/111111111111">a</a>' in out
    assert '<span class="dangling-link">b</span>' in out


def test_markdown_link_becomes_anchor():
    out = render_body("[report.pdf](attachments/202601151230-report.pdf)", {})
    assert '<a href="attachments/202601151230-report.pdf">report.pdf</a>' in out


def test_markdown_link_text_and_url_are_escaped():
    out = render_body('[<b>x</b>](attachments/a&b.pdf)', {})
    assert "&lt;b&gt;x&lt;/b&gt;" in out
    assert "<b>x</b>" not in out
    assert 'href="attachments/a&amp;b.pdf"' in out


def test_markdown_link_javascript_scheme_is_neutralized():
    # A URL containing parens (e.g. "alert(1)") doesn't match the link
    # pattern at all - () is the markdown link's own delimiter - so it's
    # just left as inert escaped text, which is also safe. Use a
    # paren-free payload to exercise the scheme check itself.
    out = render_body("[click me](javascript:document.cookie)", {})
    assert '<span class="dangling-link">click me</span>' in out
    assert "<a href" not in out


def test_wikilink_and_markdown_link_do_not_interfere():
    out = render_body("See [[202601151230]] and [report.pdf](attachments/x.pdf).", {"202601151230": "202601151230"})
    assert '<a href="/notes/202601151230">202601151230</a>' in out
    assert '<a href="attachments/x.pdf">report.pdf</a>' in out
