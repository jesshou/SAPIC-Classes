"""Static checks that generated SAPIC+ adheres to core syntax rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Outcome of syntax validation."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.ok:
            parts.append("OK")
        else:
            parts.append("FAILED")
        for e in self.errors:
            parts.append(f"ERROR: {e}")
        for w in self.warnings:
            parts.append(f"WARNING: {w}")
        return "\n".join(parts)


def validate_sapic(source: str) -> ValidationResult:
    """
    Check structural / notation adherence without running tamarin-prover.

    Covers the rules emphasized in general_SAPIC+_instruction:
    theory wrapper, begin/end, let roles, process block, no lemmas,
    and basic shared-parameter hygiene warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []
    text = source.strip()

    if not text:
        return ValidationResult(ok=False, errors=["Empty source"])

    if not re.search(r"(?m)^theory\s+\w+", text):
        errors.append("Missing `theory <Name>` header")

    if not re.search(r"(?m)^begin\s*$", text):
        errors.append("Missing `begin`")

    if not re.search(r"(?m)^end\s*$", text):
        errors.append("Missing `end`")

    if not re.search(r"(?m)^process:\s*", text):
        errors.append("Missing `process:` block")

    has_client = re.search(r"(?m)^let\s+Client\b", text) is not None
    has_server = re.search(r"(?m)^let\s+Server\b", text) is not None
    if not has_client and not has_server:
        errors.append("No `let Client` or `let Server` role definitions found")
    elif not has_client:
        warnings.append("No `let Client` role (Server-only model)")
    elif not has_server:
        warnings.append("No `let Server` role (Client-only model)")

    # Lemmas are intentionally deferred
    lemma_hits = re.findall(r"(?m)^lemma\s+(\w+)", text)
    if lemma_hits:
        errors.append(
            "Lemmas must not be included yet; found: " + ", ".join(lemma_hits)
        )

    # Unbalanced parentheses (rough)
    if text.count("(") != text.count(")"):
        errors.append("Unbalanced parentheses")

    # Shared `new` in process should be passed as parameters (instruction rule)
    process_m = re.search(
        r"process:\s*((?:.|\n)*?)(?=\nlemma\s|\nend\s*$)", text
    )
    if process_m:
        process_block = process_m.group(1)
        news = re.findall(r"new\s+(~?\w+)\s*;", process_block)
        # Find Client/Server parameter lists
        client_params = _let_params(text, "Client")
        server_params = _let_params(text, "Server")
        for n in news:
            bare = n.lstrip("~")
            # Skip channel-like single-use if never referenced — warn only
            in_client = bare in client_params or n in client_params
            in_server = bare in server_params or n in server_params
            if not in_client and not in_server:
                # Check if used in process call args
                if not re.search(rf"Client\([^)]*\b{re.escape(bare)}\b", process_block):
                    warnings.append(
                        f"`new {n}` in process: is not passed into Client/Server "
                        f"(let macros cannot see enclosing process names)"
                    )

    # Fresh-sort hint: variables bound by new ideally use ~
    role_news = re.findall(r"new\s+(\w+)\s*;", text)
    for n in role_news:
        if not n.startswith("~") and n not in {"c"}:  # c often a channel
            warnings.append(
                f"`new {n}` does not use fresh-sort marker `~` "
                f"(prefer `new ~{n}` per general instructions)"
            )

    # builtins line format
    for m in re.finditer(r"(?m)^builtins:\s*(.+)$", text):
        if not m.group(1).strip():
            errors.append("`builtins:` line is empty")

    ok = len(errors) == 0
    return ValidationResult(ok=ok, errors=errors, warnings=warnings)


def _let_params(source: str, role: str) -> list[str]:
    m = re.search(rf"(?m)^let\s+{role}\s*\(([^)]*)\)\s*=", source)
    if not m:
        # Parameterless let Role = or let Role() =
        if re.search(rf"(?m)^let\s+{role}\b", source):
            return []
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]
