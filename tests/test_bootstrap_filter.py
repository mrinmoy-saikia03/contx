from contx.bootstrap.bootstrap_filter import is_noisy_commit, NOISY_PREFIXES


def test_is_noisy_commit_wip_prefix():
    assert is_noisy_commit("wip: more work", diff_lines=100) is True


def test_is_noisy_commit_typo():
    assert is_noisy_commit("fix typo in docs", diff_lines=100) is True


def test_is_noisy_commit_format():
    assert is_noisy_commit("format(black): apply", diff_lines=100) is True


def test_is_noisy_commit_lint():
    assert is_noisy_commit("lint: fix ruff", diff_lines=100) is True


def test_is_noisy_commit_merge():
    assert is_noisy_commit("Merge branch 'main' into feature", diff_lines=0) is True


def test_is_noisy_commit_bump():
    assert is_noisy_commit("bump deps", diff_lines=200) is True


def test_is_noisy_commit_chore_deps():
    assert is_noisy_commit("chore(deps): bump pytest from 8.0 to 8.1", diff_lines=10) is True


def test_is_noisy_commit_small_diff():
    assert is_noisy_commit("real change", diff_lines=3) is True


def test_is_noisy_commit_real_change():
    assert is_noisy_commit("Switch retry to linear for May incident", diff_lines=42) is False


def test_is_noisy_commit_case_insensitive_prefix():
    assert is_noisy_commit("WIP try X", diff_lines=100) is True


def test_noisy_prefixes_constant_has_expected_entries():
    for needle in ("wip", "typo", "fix typo", "format", "fmt", "lint", "merge", "bump", "chore(deps)", "version"):
        assert needle in NOISY_PREFIXES, f"missing prefix {needle}"


def test_is_noisy_commit_respects_threshold():
    # diff_lines below the default threshold (5) is noisy regardless of subject
    assert is_noisy_commit("Switch retry to linear", diff_lines=4) is True
    assert is_noisy_commit("Switch retry to linear", diff_lines=5) is False
