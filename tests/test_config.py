from pathlib import Path

import pytest

from contx.config import Config, load_config, save_config, default_config


def test_default_config_values():
    cfg = default_config()
    assert cfg.granularity == "both"
    assert "py" in cfg.languages
    assert cfg.require_rationale_on_create is True
    assert cfg.extract_rationale_on_modify is True


def test_save_then_load_roundtrip(tmp_repo: Path):
    cfg = Config(
        granularity="symbol",
        languages=["py", "ts"],
        ignore=["**/__tests__/**"],
        require_rationale_on_create=False,
        extract_rationale_on_modify=True,
    )
    save_config(tmp_repo, cfg)
    loaded = load_config(tmp_repo)
    assert loaded == cfg


def test_load_config_missing_raises(tmp_repo: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_repo)


def test_save_config_creates_contx_dir(tmp_repo: Path):
    cfg = default_config()
    save_config(tmp_repo, cfg)
    assert (tmp_repo / ".contx" / "config.json").is_file()


def test_config_rejects_invalid_granularity():
    with pytest.raises(ValueError, match="granularity"):
        Config(
            granularity="weekly",
            languages=["py"],
            ignore=[],
            require_rationale_on_create=True,
            extract_rationale_on_modify=True,
        )


def test_default_config_requires_context_on_commit():
    cfg = default_config()
    assert cfg.require_context_on_commit is True


def test_config_can_disable_commit_enforcement(tmp_repo: Path):
    cfg = Config(
        granularity="both",
        languages=["py"],
        ignore=[],
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
        require_context_on_commit=False,
    )
    save_config(tmp_repo, cfg)
    loaded = load_config(tmp_repo)
    assert loaded.require_context_on_commit is False
