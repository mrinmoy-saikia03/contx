"""Entry dataclass — one append-only record in a contx sidecar."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

EntryKind = Literal["file", "symbol"]
EntryEvent = Literal[
    "created",
    "modified",
    "renamed_in",
    "renamed_out",
    "moved_in",
    "moved_out",
    "deleted",
]
EntryAgent = Literal["claude-code", "cursor", "human-cli", "audit"]

_VALID_KINDS = {"file", "symbol"}
_VALID_EVENTS = {
    "created", "modified", "renamed_in", "renamed_out",
    "moved_in", "moved_out", "deleted",
}


@dataclass(frozen=True)
class Entry:
    """A single append-only context entry. Immutable by design."""

    id: str
    kind: EntryKind
    symbol: str | None
    event: EntryEvent
    rationale: str
    tags: list[str]
    author: str
    timestamp: datetime
    agent: EntryAgent
    related: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"kind must be one of {_VALID_KINDS}, got {self.kind!r}")
        if self.event not in _VALID_EVENTS:
            raise ValueError(f"event must be one of {_VALID_EVENTS}, got {self.event!r}")
        if self.kind == "symbol" and not self.symbol:
            raise ValueError("symbol is required when kind == 'symbol'")
        if not self.rationale or not self.rationale.strip():
            raise ValueError("rationale must be a non-empty string")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "symbol": self.symbol,
            "event": self.event,
            "rationale": self.rationale,
            "tags": list(self.tags),
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "related": list(self.related),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Entry:
        return cls(
            id=d["id"],
            kind=d["kind"],
            symbol=d.get("symbol"),
            event=d["event"],
            rationale=d["rationale"],
            tags=list(d.get("tags", [])),
            author=d["author"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            agent=d["agent"],
            related=list(d.get("related", [])),
        )

    def to_jsonl_line(self) -> str:
        """Serialize as one line of JSON, no trailing newline."""
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_jsonl_line(cls, line: str) -> Entry:
        return cls.from_dict(json.loads(line))
