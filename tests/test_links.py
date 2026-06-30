from brain.links import parse_wikilinks


def test_no_links_returns_empty_list():
    assert parse_wikilinks("Just plain text, no links here.") == []


def test_single_id_link():
    assert parse_wikilinks("See [[202601151230]] for context.") == ["202601151230"]


def test_single_slug_link():
    assert parse_wikilinks("See [[my-cool-note]] for context.") == ["my-cool-note"]


def test_multiple_distinct_links_preserve_first_seen_order():
    body = "Links to [[202601151230]], then [[my-cool-note]], then [[202601151231]]."
    assert parse_wikilinks(body) == ["202601151230", "my-cool-note", "202601151231"]


def test_duplicate_links_are_deduped():
    body = "[[202601151230]] mentioned twice: [[202601151230]]."
    assert parse_wikilinks(body) == ["202601151230"]


def test_aliased_link_extracts_target_only():
    body = "See [[202601151230|a much nicer display title]]."
    assert parse_wikilinks(body) == ["202601151230"]


def test_aliased_link_with_empty_alias():
    assert parse_wikilinks("[[202601151230|]]") == ["202601151230"]


def test_whitespace_inside_brackets_is_stripped():
    assert parse_wikilinks("[[  202601151230  ]]") == ["202601151230"]


def test_empty_brackets_produce_no_link():
    assert parse_wikilinks("[[]]") == []


def test_single_brackets_are_not_links():
    assert parse_wikilinks("This is [not a link] and neither is [single].") == []


def test_unterminated_brackets_are_ignored():
    assert parse_wikilinks("[[202601151230 never closes") == []


def test_links_inside_code_span_are_still_parsed_known_limitation():
    # Documents current behaviour: we don't special-case markdown code
    # spans/blocks, so a link-looking string inside backticks is still
    # extracted. Revisit if this causes real false positives.
    assert parse_wikilinks("`[[202601151230]]`") == ["202601151230"]
