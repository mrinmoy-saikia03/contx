from pathlib import Path

from contx.paths import (
    sidecar_path_for_source,
    source_path_for_sidecar,
    parse_symbol_ref,
)


def test_sidecar_path_for_source_basic():
    repo = Path("/r")
    src = Path("/r/src/auth/login.py")
    assert sidecar_path_for_source(repo, src) == Path("/r/.contx/src/auth/login.py.jsonl")


def test_sidecar_path_for_source_at_root():
    repo = Path("/r")
    src = Path("/r/main.py")
    assert sidecar_path_for_source(repo, src) == Path("/r/.contx/main.py.jsonl")


def test_sidecar_path_rejects_path_outside_repo():
    import pytest
    repo = Path("/r")
    src = Path("/elsewhere/main.py")
    with pytest.raises(ValueError, match="outside the repo"):
        sidecar_path_for_source(repo, src)


def test_source_path_for_sidecar_basic():
    repo = Path("/r")
    sc = Path("/r/.contx/src/auth/login.py.jsonl")
    assert source_path_for_sidecar(repo, sc) == Path("/r/src/auth/login.py")


def test_source_path_rejects_non_sidecar():
    import pytest
    repo = Path("/r")
    sc = Path("/r/src/auth/login.py")
    with pytest.raises(ValueError, match="not a contx sidecar"):
        source_path_for_sidecar(repo, sc)


def test_parse_symbol_ref_file_only():
    assert parse_symbol_ref("src/auth/login.py") == ("src/auth/login.py", None)


def test_parse_symbol_ref_with_symbol():
    assert parse_symbol_ref("src/auth/login.py::User.authenticate") == (
        "src/auth/login.py",
        "User.authenticate",
    )


def test_parse_symbol_ref_rejects_double_separator():
    import pytest
    with pytest.raises(ValueError, match="only one"):
        parse_symbol_ref("a::b::c")
