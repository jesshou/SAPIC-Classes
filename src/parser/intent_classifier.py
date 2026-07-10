"""Map English sentences to SAPIC+ class library entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.llm.openai_client import OpenAIClient
from src.llm.prompt_templates import CLASSIFY_SYSTEM, classify_user_prompt
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassMatch:
    """One sentence mapped to one or more SAPIC+ classes."""

    sentence: str
    class_ids: list[str]
    phase: str
    confidence: float = 1.0
    rationale: str = ""
    is_combination: bool = False


@dataclass
class ClassificationResult:
    """Full classification of a protocol description."""

    matches: list[ClassMatch] = field(default_factory=list)
    protocol_name: str = "protocol"
    used_llm: bool = False


def _keyword_score(sentence: str, keywords: list[str]) -> float:
    """
    Score keyword overlap, weighting longer (more specific) phrases higher.

    A hit on a multi-word keyword contributes more than a short generic one,
    so "symmetric encryption" outranks bare "symmetric key".
    """
    lower = sentence.lower()
    if not keywords:
        return 0.0
    score = 0.0
    for kw in keywords:
        k = kw.lower()
        if k in lower:
            # Longer phrases are more discriminative
            score += 1.0 + 0.35 * max(0, len(k.split()) - 1)
    return score


def _heuristic_classify(
    sentences: list[str],
    library: dict[str, Any],
) -> list[ClassMatch]:
    """Fallback classifier using keyword overlap against the class library."""
    classes = library.get("classes", [])
    matches: list[ClassMatch] = []

    for sentence in sentences:
        scored: list[tuple[float, dict[str, Any]]] = []
        for cls in classes:
            score = _keyword_score(sentence, cls.get("keywords", []))
            # Boost exact id / name mentions
            lower = sentence.lower()
            if cls["id"].replace("_", " ") in lower or cls["id"] in lower:
                score += 0.5
            if score > 0:
                scored.append((score, cls))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            # Default to setup for unrecognized startup-ish text
            matches.append(
                ClassMatch(
                    sentence=sentence,
                    class_ids=["setup"],
                    phase="Startup",
                    confidence=0.2,
                    rationale="No keyword match; defaulted to setup skeleton.",
                    is_combination=False,
                )
            )
            continue

        # Keep top matches above a relative threshold (combination if >1)
        top_score = scored[0][0]
        selected = [c for s, c in scored if s >= max(0.15, top_score * 0.6)][:3]
        class_ids = [c["id"] for c in selected]
        # Phase = latest protocol phase among selected classes (not the top keyword hit)
        phase_rank = {"Startup": 0, "DataTransfer": 1, "Cleanup": 2}
        phase = max(selected, key=lambda c: phase_rank.get(c["phase"], 0))["phase"]
        matches.append(
            ClassMatch(
                sentence=sentence,
                class_ids=class_ids,
                phase=phase,
                confidence=min(1.0, top_score),
                rationale=f"Keyword match against {', '.join(class_ids)}",
                is_combination=len(class_ids) > 1,
            )
        )

    return matches


def _parse_llm_classification(
    data: dict[str, Any],
    sentences: list[str],
    valid_ids: set[str],
    id_to_phase: dict[str, str] | None = None,
) -> tuple[str, list[ClassMatch]]:
    protocol_name = str(data.get("protocol_name", "protocol")).strip() or "protocol"
    raw_matches = data.get("matches", [])
    matches: list[ClassMatch] = []
    phase_rank = {"Startup": 0, "DataTransfer": 1, "Cleanup": 2}
    id_to_phase = id_to_phase or {}

    for i, item in enumerate(raw_matches):
        sentence = item.get("sentence") or (sentences[i] if i < len(sentences) else "")
        class_ids = [
            cid for cid in item.get("class_ids", []) if cid in valid_ids
        ]
        if not class_ids:
            class_ids = ["setup"]
        phases = [
            id_to_phase.get(cid, item.get("phase", "DataTransfer"))
            for cid in class_ids
        ]
        phase = max(phases, key=lambda p: phase_rank.get(p, 0))
        matches.append(
            ClassMatch(
                sentence=sentence,
                class_ids=class_ids,
                phase=phase,
                confidence=float(item.get("confidence", 0.8)),
                rationale=item.get("rationale", ""),
                is_combination=len(class_ids) > 1,
            )
        )

    # Ensure every input sentence has a match
    if len(matches) < len(sentences):
        for sentence in sentences[len(matches) :]:
            matches.append(
                ClassMatch(
                    sentence=sentence,
                    class_ids=["setup"],
                    phase="Startup",
                    confidence=0.3,
                    rationale="LLM omitted sentence; defaulted to setup.",
                    is_combination=False,
                )
            )

    return protocol_name, matches


def classify_sentences(
    sentences: list[str],
    library: dict[str, Any],
    client: OpenAIClient | None = None,
    use_llm: bool = True,
) -> ClassificationResult:
    """
    Map each sentence to one or more SAPIC+ class IDs.

    Uses the OpenAI client when available; falls back to keyword heuristics.
    """
    if not sentences:
        return ClassificationResult()

    valid_ids = {c["id"] for c in library.get("classes", [])}

    if use_llm and client is not None and client.is_available:
        try:
            class_summaries = [
                {
                    "id": c["id"],
                    "phase": c["phase"],
                    "description": c["description"],
                    "keywords": c.get("keywords", []),
                }
                for c in library.get("classes", [])
            ]
            user_prompt = classify_user_prompt(sentences, class_summaries)
            data = client.chat_json(CLASSIFY_SYSTEM, user_prompt)
            id_to_phase = {
                c["id"]: c["phase"] for c in library.get("classes", [])
            }
            protocol_name, matches = _parse_llm_classification(
                data, sentences, valid_ids, id_to_phase=id_to_phase
            )
            # Mark combinations
            for m in matches:
                m.is_combination = len(m.class_ids) > 1
            return ClassificationResult(
                matches=matches,
                protocol_name=protocol_name,
                used_llm=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM classification failed (%s); using heuristics.", exc)

    matches = _heuristic_classify(sentences, library)
    return ClassificationResult(
        matches=matches,
        protocol_name="protocol",
        used_llm=False,
    )
