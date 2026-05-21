"""Per-repo config: .contx/config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from contx.paths import CTX_DIR
from contx.repo import ensure_contx_dir

Granularity = Literal["file", "symbol", "both"]
_VALID_GRANULARITY = {"file", "symbol", "both"}

CONFIG_FILENAME = "config.json"

DEFAULT_LANGUAGES = ["py", "ts", "tsx", "js", "jsx", "go", "java", "kt", "rs", "rb", "php", "swift"]
DEFAULT_IGNORE = [
    "**/node_modules/**",
    "**/__tests__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/build/**",
]


@dataclass(frozen=True)
class Config:
    granularity: Granularity
    languages: list[str]
    ignore: list[str]
    require_rationale_on_create: bool
    extract_rationale_on_modify: bool

    def __post_init__(self) -> None:
        if self.granularity not in _VALID_GRANULARITY:
            raise ValueError(
                f"granularity must be one of {_VALID_GRANULARITY}, got {self.granularity!r}"
            )


def default_config() -> Config:
    return Config(
        granularity="both",
        languages=list(DEFAULT_LANGUAGES),
        ignore=list(DEFAULT_IGNORE),
        require_rationale_on_create=True,
        extract_rationale_on_modify=True,
    )


def _config_path(repo_root: Path) -> Path:
    return repo_root / CTX_DIR / CONFIG_FILENAME


def save_config(repo_root: Path, cfg: Config) -> None:
    ensure_contx_dir(repo_root)
    _config_path(repo_root).write_text(json.dumps(asdict(cfg), indent=2) + "\n")


def load_config(repo_root: Path) -> Config:
    p = _config_path(repo_root)
    if not p.is_file():
        raise FileNotFoundError(f"No contx config at {p}. Run `contx init` first.")
    data = json.loads(p.read_text())
    return Config(
        granularity=data["granularity"],
        languages=list(data["languages"]),
        ignore=list(data["ignore"]),
        require_rationale_on_create=bool(data["require_rationale_on_create"]),
        extract_rationale_on_modify=bool(data["extract_rationale_on_modify"]),
    )
