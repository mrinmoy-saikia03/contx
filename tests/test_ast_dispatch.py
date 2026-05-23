from pathlib import Path

from contx.bootstrap.ast_dispatch import bootstrap_file


def test_dispatch_python_file(tmp_path: Path):
    p = tmp_path / "foo.py"
    p.write_text('"""mod"""\ndef hi():\n    """h"""\n    pass\n')
    result = bootstrap_file(p)
    assert result is not None
    assert result.file_doc == "mod"
    assert any(s.symbol == "hi" for s in result.symbols)


def test_dispatch_unknown_language_returns_none(tmp_path: Path):
    p = tmp_path / "foo.unknownlang"
    p.write_text("whatever")
    assert bootstrap_file(p) is None


def test_dispatch_unsupported_typescript_returns_none(tmp_path: Path):
    p = tmp_path / "foo.ts"
    p.write_text("export const x = 1;")
    # TS stubbed for now; should return None until implemented.
    assert bootstrap_file(p) is None


def test_dispatch_missing_file_returns_none(tmp_path: Path):
    assert bootstrap_file(tmp_path / "nope.py") is None
