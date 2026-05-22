from contx.drafting import DraftedEntry, build_template, parse_template


def test_build_template_one_file():
    text = build_template(["src/foo.py"], prefilled={})
    assert "src/foo.py" in text
    assert "event: modified" in text
    assert "rationale:" in text


def test_build_template_uses_prefilled_rationale():
    text = build_template(["src/foo.py"], prefilled={"src/foo.py": "bumped retry to linear"})
    assert "bumped retry to linear" in text


def test_parse_template_extracts_one_entry():
    text = """\
# contx draft — fill in a rationale for each file, then save & exit.

## src/foo.py
event: modified
rationale: switched to linear retry
tags: incident
"""
    entries = parse_template(text)
    assert len(entries) == 1
    e = entries[0]
    assert e.file == "src/foo.py"
    assert e.event == "modified"
    assert e.rationale == "switched to linear retry"
    assert e.tags == ["incident"]
    assert e.skip is False


def test_parse_template_skips_empty_rationale():
    text = """\
## src/foo.py
event: modified
rationale:
tags:
"""
    entries = parse_template(text)
    assert len(entries) == 1
    assert entries[0].skip is True


def test_parse_template_handles_multiple_files():
    text = """\
## src/a.py
event: modified
rationale: A reason
tags: tag-a

## src/b.py
event: created
rationale: B reason
tags: tag-b1, tag-b2
"""
    entries = parse_template(text)
    assert {e.file for e in entries} == {"src/a.py", "src/b.py"}
    b = next(e for e in entries if e.file == "src/b.py")
    assert b.event == "created"
    assert b.tags == ["tag-b1", "tag-b2"]


def test_parse_template_ignores_comments():
    text = """\
# top-level comment
## src/foo.py
# inline comment
event: modified
rationale: x
tags:
"""
    entries = parse_template(text)
    assert entries[0].rationale == "x"


def test_parse_template_supports_symbol_in_filename_header():
    text = """\
## src/foo.py::Class.method
event: modified
rationale: bar
tags:
"""
    entries = parse_template(text)
    assert entries[0].file == "src/foo.py"
    assert entries[0].symbol == "Class.method"
