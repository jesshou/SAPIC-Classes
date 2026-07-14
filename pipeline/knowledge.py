"""Loads the SAPIC+ knowledge base: ProtocolBits building blocks and
Benchmark ground-truth (English description, SAPIC+ code) example pairs."""

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class ProtocolBit:
    phase: str      # e.g. "1) Startup"
    name: str       # e.g. "nonce"
    code: str


@dataclass
class BenchmarkExample:
    name: str
    description: str
    code: str


def load_protocol_bits() -> list[ProtocolBit]:
    """Load every building-block .spthy under ProtocolBits, grouped by phase folder."""
    bits = []
    for phase_dir in sorted(config.PROTOCOL_BITS_DIR.iterdir()):
        if not phase_dir.is_dir():
            continue
        for spthy in sorted(phase_dir.glob("*.spthy")):
            bits.append(ProtocolBit(
                phase=phase_dir.name,
                name=spthy.stem,
                code=spthy.read_text(encoding="utf-8", errors="replace"),
            ))
    return bits


def _find_spthy_for(txt_path: Path) -> Path | None:
    """Find the ground-truth <name>-P.spthy that pairs with a description .txt.

    Handles naming drift like "Kao-Chow v1.txt" -> "Kao-Chow-P.spthy" and
    "CCITT-X509-1.txt" -> "CCITT-X509-P.spthy".
    """
    stem = txt_path.stem
    candidates = [stem, stem.split(" ")[0], stem.rsplit("-", 1)[0]]
    for cand in candidates:
        p = txt_path.parent / f"{cand}-P.spthy"
        if p.exists():
            return p
    return None


def load_benchmark_examples(names: list[str] | None = None) -> list[BenchmarkExample]:
    """Load (description, code) pairs from the Benchmark folder.

    If names is given, only those protocols are loaded, in the given order;
    otherwise every pair found is returned.
    """
    examples = []
    txt_files = {p.stem: p for p in config.BENCHMARK_DIR.glob("*.txt")}
    wanted = names if names is not None else sorted(txt_files)
    for name in wanted:
        txt = txt_files.get(name)
        if txt is None:
            continue
        spthy = _find_spthy_for(txt)
        if spthy is None:
            continue
        examples.append(BenchmarkExample(
            name=name,
            description=txt.read_text(encoding="utf-8", errors="replace"),
            code=spthy.read_text(encoding="utf-8", errors="replace"),
        ))
    return examples
