import pytest

from contx.summarizers import SummaryEntry
from contx.summarizers.registry import (
    get_summarizer,
    list_summarizers,
    register_summarizer,
)


def test_register_and_get():
    def fake(content: str, file_path: str) -> list[SummaryEntry]:
        return [SummaryEntry(symbol=None, rationale="x", tags=["test"])]

    register_summarizer("fake", fake)
    s = get_summarizer("fake")
    out = s("hi", "k8s/a.yaml")
    assert len(out) == 1
    assert out[0].rationale == "x"


def test_get_unknown_returns_none():
    assert get_summarizer("does-not-exist") is None


def test_list_summarizers_includes_registered():
    register_summarizer("listed", lambda c, f: [])
    assert "listed" in list_summarizers()


def test_summary_entry_immutable():
    e = SummaryEntry(symbol="foo", rationale="r", tags=["t"])
    import dataclasses
    assert dataclasses.is_dataclass(e) and e.__dataclass_params__.frozen
