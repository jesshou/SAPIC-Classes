"""Extracts SAPIC+ code from an LLM response."""

import re

_FENCE_RE = re.compile(r"```(?:spthy)?\s*\n(.*?)```", re.DOTALL)


def extract_spthy(response_text: str) -> str | None:
    """Return the SAPIC+ theory from a response, or None if none is found.

    Prefers a fenced code block containing `theory`; falls back to the raw
    response if it itself looks like a bare theory.
    """
    blocks = _FENCE_RE.findall(response_text)
    for block in blocks:
        if "theory" in block and "begin" in block:
            return block.strip() + "\n"
    if blocks:
        return blocks[-1].strip() + "\n"
    stripped = response_text.strip()
    if stripped.startswith("theory") and stripped.endswith("end"):
        return stripped + "\n"
    return None
