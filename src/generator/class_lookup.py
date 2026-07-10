"""Direct 1-to-1 lookup from SAPIC+ class IDs to source fragments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.file_io import load_json, read_text


@dataclass
class ClassRecord:
    """Metadata + source for one library class."""

    id: str
    name: str
    phase: str
    file: str
    builtins: list[str]
    parameters: list[str]
    keywords: list[str]
    description: str
    combinable: bool
    provides: list[str]
    requires: list[str]
    source: str

    def body_without_lemmas(self) -> str:
        """Return theory source with lemma blocks stripped."""
        return strip_lemmas(self.source)


@dataclass
class ClassLibrary:
    """In-memory index of the SAPIC+ class library."""

    root: Path
    raw: dict[str, Any]
    by_id: dict[str, ClassRecord]

    def get(self, class_id: str) -> ClassRecord:
        if class_id not in self.by_id:
            raise KeyError(f"Unknown SAPIC+ class id: {class_id}")
        return self.by_id[class_id]

    def get_many(self, class_ids: list[str]) -> list[ClassRecord]:
        return [self.get(cid) for cid in class_ids]

    def all_ids(self) -> list[str]:
        return list(self.by_id.keys())


_LEMMA_RE = re.compile(
    r"(?m)^lemma\s+\w+\s*:[\s\S]*?(?=^lemma\s|\ZEND\s*$)",
)


def strip_lemmas(source: str) -> str:
    """Remove lemma declarations from a .spthy fragment (lemmas deferred)."""
    # Remove lemma ... blocks up to next lemma or end
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if re.match(r"^lemma\s+\w+", line):
            skipping = True
            continue
        if skipping:
            # lemmas end when we hit a blank-line-followed-by-non-lemma top-level
            # or the final `end`
            if re.match(r"^end\s*$", line):
                skipping = False
                out.append(line)
                continue
            if re.match(r"^lemma\s+\w+", line):
                continue
            # stay in skip until we see a line that looks like top-level theory end
            # or another construct; lemma bodies are quoted strings / exists-trace
            if line.strip() == "" and out and out[-1].strip() == "":
                continue
            # If we see process: after lemmas were already past, stop skipping
            # (some files put process after lemmas, e.g. HKDF)
            if re.match(r"^(process:|functions:|builtins:|let\s)", line):
                skipping = False
                out.append(line)
                continue
            continue
        out.append(line)

    text = "".join(out)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def load_library(library_dir: Path | str) -> ClassLibrary:
    """Load class_library.json and all referenced .spthy sources."""
    root = Path(library_dir)
    raw = load_json(root / "class_library.json")
    by_id: dict[str, ClassRecord] = {}

    for entry in raw.get("classes", []):
        rel = entry["file"]
        source_path = root / rel
        source = read_text(source_path)
        rec = ClassRecord(
            id=entry["id"],
            name=entry["name"],
            phase=entry["phase"],
            file=rel,
            builtins=list(entry.get("builtins", [])),
            parameters=list(entry.get("parameters", [])),
            keywords=list(entry.get("keywords", [])),
            description=entry.get("description", ""),
            combinable=bool(entry.get("combinable", True)),
            provides=list(entry.get("provides", [])),
            requires=list(entry.get("requires", [])),
            source=source,
        )
        by_id[rec.id] = rec

    return ClassLibrary(root=root, raw=raw, by_id=by_id)


def lookup_direct(library: ClassLibrary, class_id: str) -> str:
    """
    Direct 1-to-1 class -> SAPIC+ code (lemmas stripped).

    Used when a sentence maps to exactly one library class.
    """
    return library.get(class_id).body_without_lemmas()
