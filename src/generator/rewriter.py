"""Rewrite step: ensure stitched SAPIC+ compiles and follows syntax rules."""

from __future__ import annotations

from pathlib import Path

from src.generator.class_lookup import ClassLibrary
from src.generator.combinator import CombinedDraft
from src.generator.syntax_validator import ValidationResult, validate_sapic
from src.llm.openai_client import OpenAIClient
from src.llm.prompt_templates import REWRITE_SYSTEM, rewrite_user_prompt
from src.utils.file_io import read_text
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _local_normalize(source: str, theory_name: str) -> str:
    """Lightweight deterministic cleanup when LLM rewrite is unavailable."""
    text = source.strip()
    # Ensure theory name
    if not text.startswith("theory "):
        text = f"theory {theory_name}\nbegin\n\n{text}\nend\n"
    # Strip markdown fences if an LLM left them
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Ensure trailing end
    if not text.rstrip().endswith("end"):
        text = text.rstrip() + "\n\nend\n"
    # Remove any lemmas that slipped through
    from src.generator.class_lookup import strip_lemmas

    text = strip_lemmas(text)
    return text if text.endswith("\n") else text + "\n"


def rewrite_combined(
    draft: CombinedDraft,
    library: ClassLibrary,
    english_description: str,
    syntax_instructions_path: Path | str,
    rewrite_instructions_path: Path | str | None = None,
    client: OpenAIClient | None = None,
    use_llm: bool = True,
    max_attempts: int = 2,
) -> tuple[str, ValidationResult]:
    """
    Rewrite a combined draft so it adheres to SAPIC+ syntax.

    For direct (single-class) lookups, only local normalization + validation
    runs. For combinations, an LLM rewrite is preferred; otherwise the
    deterministic stitch is normalized locally.
    """
    instructions = read_text(syntax_instructions_path)
    rewrite_instructions = (
        read_text(rewrite_instructions_path) if rewrite_instructions_path else None
    )
    source = _local_normalize(draft.source, draft.theory_name)
    result = validate_sapic(source)

    if not draft.needs_rewrite:
        return source, result

    if not (use_llm and client is not None and client.is_available):
        logger.info("LLM rewrite unavailable; using local normalization only.")
        return source, result

    fragments = []
    for cid in draft.class_ids:
        rec = library.get(cid)
        fragments.append(
            {
                "id": rec.id,
                "phase": rec.phase,
                "source": rec.body_without_lemmas(),
            }
        )

    errors = list(result.errors)
    for attempt in range(1, max_attempts + 1):
        logger.info("LLM rewrite attempt %d/%d", attempt, max_attempts)
        user = rewrite_user_prompt(
            protocol_name=draft.theory_name,
            english_description=english_description,
            class_ids=draft.class_ids,
            fragments=fragments,
            syntax_instructions=instructions,
            rewrite_instructions=rewrite_instructions,
            validation_errors=errors or None,
        )
        try:
            rewritten = client.chat(REWRITE_SYSTEM, user, temperature=0.15)
            source = _local_normalize(rewritten, draft.theory_name)
            result = validate_sapic(source)
            if result.ok:
                return source, result
            errors = list(result.errors)
            logger.warning("Rewrite still has issues: %s", errors)
        except Exception as exc:  # noqa: BLE001
            logger.error("Rewrite failed: %s", exc)
            break

    return source, result
