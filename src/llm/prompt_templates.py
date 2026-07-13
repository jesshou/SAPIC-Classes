"""Prompt templates for classification and SAPIC+ rewriting."""

from __future__ import annotations

import json
from typing import Any


CLASSIFY_SYSTEM = """You are an expert in SAPIC+ (the process calculus front-end of the Tamarin prover).
Your job is to map each English sentence describing a security protocol into one or more
pre-existing SAPIC+ class IDs from a fixed library.

Rules:
- Choose ONLY class IDs from the provided library.
- Prefer a single class when the sentence matches one building block directly.
- Use multiple class IDs (a combination) when the sentence clearly requires stitching
  several building blocks (e.g. "ephemeral DH then encrypt application data").
- Assign each match a phase: Startup, DataTransfer, or Cleanup.
- Also propose a short snake_case protocol_name.
- Return STRICT JSON only, no markdown commentary.
"""


REWRITE_SYSTEM = """You are an expert SAPIC+ / Tamarin model author.
You receive several SAPIC+ class fragments that must be stitched into ONE well-formed
theory that compiles under Tamarin's SAPIC+ front-end.

Hard requirements (from general SAPIC+ instructions):
1. Output a single theory: `theory <Name> begin ... end`
2. Merge builtins uniquely (comma-separated).
3. Merge functions: blocks if present.
4. Roles are `let Client(...) = ...` and `let Server(...) = ...` processes.
5. `let ROLE(...)` macros do NOT see names from the enclosing `process:` block.
   Shared values (keys, channels) must be created with `new` in `process:` and
   passed as explicit parameters.
6. Private long-term secrets may be `new` inside a role's own `let`.
7. Always use `~` on variables bound to `new` when they are fresh-sorted
   (e.g. `~ltkA`, `~n`, `~ek`) following the library naming conventions.
8. Sequence actions with `;`. Parallel composition with `|`. Replication with `!`.
9. DO NOT include any lemmas. Lemmas are intentionally omitted.
10. Follow naming conventions: pKc/pKs, ltKc/ltKs, psk, eKc/eKs, ePKc/ePKs, dhZ,
    n, m/mC/mS, xencC/xencS.
11. Preserve protocol intent from the English description and the selected classes.
12. If a fragment's role parameter (e.g. `Server(psk)`) is a value shared by both
    Client and Server, keep it as a parameter on both merged roles and hoist its
    `new` into the combined theory's single `process:` block. Never `new` it
    inside only one role — the other role's use of it will be unbound.
13. Preserve every `event Name(...)` fact's name and argument order exactly as
    written in each source fragment — do not rename or reshape them. Each
    fragment's own executability lemmas (kept separately, not shown here) refer
    to these events by name; renaming one silently breaks that lemma.
14. Return ONLY the SAPIC+ theory source, no markdown fences or commentary.
"""


def classify_user_prompt(
    sentences: list[str],
    class_summaries: list[dict[str, Any]],
) -> str:
    payload = {
        "sentences": sentences,
        "library": class_summaries,
        "output_schema": {
            "protocol_name": "snake_case_name",
            "matches": [
                {
                    "sentence": "...",
                    "class_ids": ["id1", "id2"],
                    "phase": "Startup|DataTransfer|Cleanup",
                    "confidence": 0.0,
                    "rationale": "short reason",
                }
            ],
        },
    }
    return (
        "Classify each sentence into SAPIC+ class IDs.\n\n"
        + json.dumps(payload, indent=2)
    )


def rewrite_user_prompt(
    protocol_name: str,
    english_description: str,
    class_ids: list[str],
    fragments: list[dict[str, str]],
    syntax_instructions: str,
    rewrite_instructions: str | None = None,
    validation_errors: list[str] | None = None,
) -> str:
    parts = [
        f"Protocol name: {protocol_name}",
        "",
        "English description:",
        english_description.strip(),
        "",
        f"Selected class IDs (in order): {', '.join(class_ids)}",
        "",
        "General SAPIC+ syntax instructions:",
        syntax_instructions.strip(),
    ]
    if rewrite_instructions:
        parts += [
            "",
            "Class-combining instructions:",
            rewrite_instructions.strip(),
        ]
    parts += [
        "",
        "Class fragments to stitch:",
    ]
    for frag in fragments:
        parts.append(f"\n--- class: {frag['id']} ({frag.get('phase', '')}) ---")
        parts.append(frag["source"])

    if validation_errors:
        parts.append("\nPrevious validation errors to fix:")
        for err in validation_errors:
            parts.append(f"- {err}")

    parts.append(
        "\nProduce one combined SAPIC+ theory with NO lemmas."
    )
    return "\n".join(parts)
