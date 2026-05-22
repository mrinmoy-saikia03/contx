import subprocess
from pathlib import Path

import pytest

from contx.config import default_config, save_config
from contx.staging import (
    Drift,
    compute_drift,
    list_staged_paths,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _write_and_stage(repo: Path, rel_path: str, content: str) -> None:
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", rel_path)


def test_list_staged_paths_returns_added_files(tmp_repo: Path):
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    paths = list_staged_paths(tmp_repo)
    assert "src/foo.py" in paths


def test_list_staged_paths_includes_contx_dir(tmp_repo: Path):
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    paths = list_staged_paths(tmp_repo)
    assert ".contx/src/foo.py.jsonl" in paths


def test_compute_drift_clean_when_both_staged(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    drift = compute_drift(tmp_repo)
    assert drift.missing == []


def test_compute_drift_flags_code_without_context(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    drift = compute_drift(tmp_repo)
    assert "src/foo.py" in drift.missing


def test_compute_drift_respects_ignore_patterns(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, "node_modules/lib.js", "x")
    drift = compute_drift(tmp_repo)
    assert "node_modules/lib.js" not in drift.missing


def test_compute_drift_respects_language_filter(tmp_repo: Path):
    cfg = default_config()
    save_config(tmp_repo, cfg)
    _write_and_stage(tmp_repo, "README.md", "# hi")
    drift = compute_drift(tmp_repo)
    assert "README.md" not in drift.missing


def test_compute_drift_uninitialized_returns_clean(tmp_repo: Path):
    _write_and_stage(tmp_repo, "src/foo.py", "x = 1\n")
    drift = compute_drift(tmp_repo)
    assert drift.missing == []
    assert drift.uninitialized is True


def test_compute_drift_pairs_sidecar_to_source(tmp_repo: Path):
    save_config(tmp_repo, default_config())
    _write_and_stage(tmp_repo, ".contx/src/foo.py.jsonl", '{"id":"x"}\n')
    drift = compute_drift(tmp_repo)
    assert drift.missing == []


def test_compute_drift_respects_contxignore(tmp_repo: Path):
    from contx.ignore import CONTXIGNORE_FILENAME
    save_config(tmp_repo, default_config())
    (tmp_repo / CONTXIGNORE_FILENAME).write_text("vendor/**\n")
    _write_and_stage(tmp_repo, "vendor/lib.py", "x = 1\n")
    drift = compute_drift(tmp_repo)
    assert "vendor/lib.py" not in drift.missing
