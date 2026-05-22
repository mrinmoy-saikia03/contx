from pathlib import Path

from contx.ignore import (
    CONTXIGNORE_FILENAME,
    load_contxignore_patterns,
    load_effective_ignore_patterns,
    matches_any_pattern,
)
from contx.config import default_config, save_config


def test_load_contxignore_missing_returns_empty(tmp_path: Path):
    assert load_contxignore_patterns(tmp_path) == []


def test_load_contxignore_strips_comments_and_blanks(tmp_path: Path):
    (tmp_path / CONTXIGNORE_FILENAME).write_text(
        "# a comment\n\nvendor/**\n  # indented comment\n*.generated.py\n"
    )
    patterns = load_contxignore_patterns(tmp_path)
    assert patterns == ["vendor/**", "*.generated.py"]


def test_load_effective_merges_config_then_contxignore(tmp_path: Path):
    cfg = default_config()
    # default_config includes node_modules/** and similar in ignore
    save_config(tmp_path, cfg)
    (tmp_path / CONTXIGNORE_FILENAME).write_text("vendor/**\n")
    effective = load_effective_ignore_patterns(tmp_path)
    # config patterns come first
    assert effective.index("vendor/**") > len(cfg.ignore) - 1
    assert "vendor/**" in effective


def test_load_effective_without_config_falls_back_to_contxignore_only(tmp_path: Path):
    # No config.json — only the .contxignore should contribute.
    (tmp_path / CONTXIGNORE_FILENAME).write_text("only/**\n")
    effective = load_effective_ignore_patterns(tmp_path)
    assert effective == ["only/**"]


def test_matches_any_pattern_simple_glob():
    assert matches_any_pattern("vendor/foo.py", ["vendor/**"])
    assert not matches_any_pattern("src/foo.py", ["vendor/**"])


def test_matches_any_pattern_double_star_anywhere():
    assert matches_any_pattern("a/b/node_modules/x.js", ["**/node_modules/**"])


def test_matches_any_pattern_extension():
    assert matches_any_pattern("a/b.generated.py", ["**/*.generated.py"])
