"""Translates a user's English protocol description into LLM prompts.

Builds three things:
  - a system prompt embedding the ProtocolBits library and few-shot
    benchmark examples,
  - the initial user prompt from the English description,
  - repair prompts that feed tamarin-prover errors back for another attempt.
"""

from . import config
from .knowledge import load_benchmark_examples, load_protocol_bits

SYSTEM_HEADER = """\
You are an expert in formal verification of security protocols using the
Tamarin prover's SAPIC+ process calculus. Your task: translate an English
description of a security protocol into a complete, syntactically valid
SAPIC+ theory (.spthy file) that parses with `tamarin-prover --parse-only`.

Requirements for every theory you produce:
- Start with `theory <name>` / `begin` and finish with `end`.
- Declare needed `builtins:` (e.g. symmetric-encryption, asymmetric-encryption,
  signing, hashing, diffie-hellman) and any custom `functions:`.
- Model each role as a `let <Role>(...) = ...` process using new/in/out/let/event.
- Compose roles under `process:` (e.g. `new k; (!A(k) | !B(k))`).
- Emit `event` actions at protocol milestones so lemmas can reference them.
- Include at least one `exists-trace` executability lemma, plus secrecy or
  authentication lemmas appropriate to the description's security goals.
- Output the theory inside a single ```spthy fenced code block and nothing
  else outside it besides brief notes.

Below is a library of reusable SAPIC+ "building blocks" covering common
protocol phases. Reuse their patterns (adapted to the protocol at hand)
whenever they fit.
"""


def _format_bits() -> str:
    parts = []
    current_phase = None
    for bit in load_protocol_bits():
        if bit.phase != current_phase:
            parts.append(f"\n## Phase: {bit.phase}\n")
            current_phase = bit.phase
        parts.append(f"### Building block: {bit.name}\n```spthy\n{bit.code.strip()}\n```\n")
    return "".join(parts)


def _format_examples() -> str:
    parts = ["\nHere are complete worked examples of the translation task:\n"]
    for ex in load_benchmark_examples(config.FEW_SHOT_EXAMPLES):
        parts.append(
            f"\n## Example: {ex.name}\n"
            f"English description:\n\"\"\"\n{ex.description.strip()}\n\"\"\"\n"
            f"SAPIC+ translation:\n```spthy\n{ex.code.strip()}\n```\n"
        )
    return "".join(parts)


def build_system_prompt() -> str:
    return SYSTEM_HEADER + _format_bits() + _format_examples()


def build_user_prompt(description: str) -> str:
    return (
        "Translate the following English protocol description into a SAPIC+ "
        "theory. Identify the roles, the messages exchanged, the cryptographic "
        "primitives used, and the intended security goals, then produce the "
        "complete .spthy file.\n\n"
        f"Protocol description:\n\"\"\"\n{description.strip()}\n\"\"\""
    )


def build_repair_prompt(error_output: str) -> str:
    return (
        "The SAPIC+ theory you produced failed to parse. "
        "`tamarin-prover --parse-only` reported:\n\n"
        f"```\n{error_output.strip()}\n```\n\n"
        "Fix the error and output the full corrected theory in a single "
        "```spthy fenced code block. Do not omit any part of the theory."
    )
