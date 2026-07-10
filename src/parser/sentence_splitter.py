"""Split English protocol descriptions into sentences."""

from __future__ import annotations

import re


_ABBREVIATIONS = {
    "e.g.",
    "i.e.",
    "vs.",
    "etc.",
    "Dr.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "Prof.",
    "Inc.",
    "Ltd.",
    "TLS.",
}


def split_sentences(text: str) -> list[str]:
    """
    Break a protocol description into ordered sentences.

    Handles common abbreviations and keeps numbered steps as separate units
    when they appear on their own lines.
    """
    if not text or not text.strip():
        return []

    normalized = text.replace("\r\n", "\n").strip()

    # Prefer explicit line-based steps (1. ..., 2) ..., - ...)
    lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
    step_pattern = re.compile(r"^(?:\d+[\.\)]\s+|[-*]\s+)")
    if len(lines) > 1 and sum(1 for ln in lines if step_pattern.match(ln)) >= 2:
        return [step_pattern.sub("", ln).strip() for ln in lines if ln]

    # Protect abbreviations from being treated as sentence ends
    protected = normalized
    placeholders: dict[str, str] = {}
    for i, abbr in enumerate(_ABBREVIATIONS):
        token = f"__ABBR{i}__"
        placeholders[token] = abbr
        protected = protected.replace(abbr, token)

    # Split on sentence-ending punctuation followed by whitespace + capital
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", protected)

    sentences: list[str] = []
    for part in parts:
        restored = part
        for token, abbr in placeholders.items():
            restored = restored.replace(token, abbr)
        cleaned = restored.strip()
        if cleaned:
            sentences.append(cleaned)

    return sentences
