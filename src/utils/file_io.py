"""Small filesystem helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_dir(path: Path | str) -> Path:
    """Create a directory (and parents) if missing; return the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_text(path: Path | str) -> str:
    """Read a UTF-8 text file."""
    return Path(path).read_text(encoding="utf-8")


def write_text(path: Path | str, content: str) -> Path:
    """Write UTF-8 text, creating parent directories as needed."""
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(content, encoding="utf-8")
    return p


def load_json(path: Path | str) -> Any:
    """Load a JSON file."""
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)
