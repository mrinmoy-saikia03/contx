"""Template format for `contx draft` — build + parse."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DraftedEntry:
    file: str
    symbol: str | None
    event: str
    rationale: str
    tags: list[str]
    skip: bool


TEMPLATE_HEADER = (
    "# contx draft — fill in a rationale for each file, then save & edit.\n"
    "# Lines starting with # are ignored. Blank rationales are skipped.\n\n"
)


def build_template(missing_files: list[str], *, prefilled: dict[str, str] | None = None) -> str:
    prefilled = prefilled or {}
    parts: list[str] = [TEMPLATE_HEADER]
    for f in missing_files:
        rationale = prefilled.get(f, "")
        parts.append(f"## {f}\n")
        parts.append("event: modified\n")
        parts.append(f"rationale: {rationale}\n")
        parts.append("tags:\n\n")
    return "".join(parts)


def _parse_tags(line: str) -> list[str]:
    raw = line.split(":", 1)[1].strip() if ":" in line else ""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def parse_template(text: str) -> list[DraftedEntry]:
    entries: list[DraftedEntry] = []
    current_header: str | None = None
    current: dict[str, object] = {}

    def _flush() -> None:
        nonlocal current_header, current
        if current_header is None:
            return
        file, _, symbol_part = current_header.partition("::")
        rationale = str(current.get("rationale", "")).strip()
        entries.append(
            DraftedEntry(
                file=file,
                symbol=symbol_part or None,
                event=str(current.get("event", "modified")).strip() or "modified",
                rationale=rationale,
                tags=list(current.get("tags", [])),  # type: ignore[arg-type]
                skip=not rationale,
            )
        )

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            _flush()
            current_header = line[3:].strip()
            current = {}
            continue
        if current_header is None:
            continue
        if line.lstrip().startswith("#") or not line.strip():
            continue
        low = line.lower()
        if low.startswith("event:"):
            current["event"] = line.split(":", 1)[1].strip()
        elif low.startswith("rationale:"):
            current["rationale"] = line.split(":", 1)[1].strip()
        elif low.startswith("tags:"):
            current["tags"] = _parse_tags(line)
    _flush()
    return entries
