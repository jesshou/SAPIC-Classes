#!/usr/bin/env python3
"""CLI: translate an English protocol description into SAPIC+."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow `python -m src.main` and `python src/main.py` from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generator.class_lookup import load_library  # noqa: E402
from src.generator.combinator import combine_classes, class_sort_key  # noqa: E402
from src.generator.rewriter import rewrite_combined  # noqa: E402
from src.llm.openai_client import OpenAIClient  # noqa: E402
from src.output.file_builder import build_output  # noqa: E402
from src.parser.intent_classifier import classify_sentences  # noqa: E402
from src.parser.sentence_splitter import split_sentences  # noqa: E402
from src.utils.logging import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)

DATA_DIR = PROJECT_ROOT / "data"
LIBRARY_DIR = DATA_DIR / "sapic_classes"
SYNTAX_DOC = DATA_DIR / "general_SAPIC+_instruction.md"
DEFAULT_OUTPUTS = PROJECT_ROOT / "outputs"


def _read_input(args: argparse.Namespace) -> str:
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    if args.description:
        return args.description
    print("Enter / paste the English protocol description.")
    print("Finish with an empty line (or Ctrl-D):")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="englishto-sapic",
        description=(
            "Translate an English security-protocol description into a "
            "SAPIC+ theory by mapping sentences onto the class library."
        ),
    )
    p.add_argument(
        "-d",
        "--description",
        help="English protocol description (inline).",
    )
    p.add_argument(
        "-f",
        "--input-file",
        help="Path to a text file containing the English description.",
    )
    p.add_argument(
        "-n",
        "--name",
        help="Override protocol / theory name (snake_case).",
    )
    p.add_argument(
        "-o",
        "--outputs-dir",
        default=str(DEFAULT_OUTPUTS),
        help=f"Output root directory (default: {DEFAULT_OUTPUTS})",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable OpenAI calls; use keyword heuristics + local stitch only.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="OpenAI model name (overrides OPENAI_MODEL).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging.",
    )
    return p


def run(args: argparse.Namespace) -> int:
    setup_logging("DEBUG" if args.verbose else "INFO")
    load_dotenv(PROJECT_ROOT / ".env")

    english = _read_input(args)
    if not english:
        logger.error("No English description provided.")
        return 1

    library = load_library(LIBRARY_DIR)
    client = None if args.no_llm else OpenAIClient(model=args.model)

    sentences = split_sentences(english)
    logger.info("Split into %d sentence(s).", len(sentences))
    for i, s in enumerate(sentences, 1):
        logger.debug("  [%d] %s", i, s)

    classification = classify_sentences(
        sentences,
        library.raw,
        client=client,
        use_llm=not args.no_llm,
    )
    protocol_name = args.name or classification.protocol_name or "protocol"
    # Sanitize theory name for SAPIC+
    theory_name = "".join(
        ch if ch.isalnum() or ch == "_" else "_" for ch in protocol_name
    )
    if theory_name and theory_name[0].isdigit():
        theory_name = "P_" + theory_name

    logger.info(
        "Protocol=%s  LLM=%s",
        theory_name,
        classification.used_llm,
    )

    # Collect ordered unique class IDs across all sentences (library phase order)
    ordered_ids: list[str] = []
    seen: set[str] = set()
    phase_by_id = {c["id"]: c["phase"] for c in library.raw.get("classes", [])}
    collected: list[str] = []
    for m in classification.matches:
        logger.info(
            "Sentence -> %s %s",
            m.class_ids,
            "(combo)" if m.is_combination else "",
        )
        for cid in m.class_ids:
            if cid not in seen:
                seen.add(cid)
                collected.append(cid)

    ordered_ids = sorted(
        collected,
        key=lambda cid: class_sort_key(cid, phase_by_id.get(cid, "DataTransfer")),
    )

    if not ordered_ids:
        ordered_ids = ["setup"]

    draft = combine_classes(library, ordered_ids, theory_name=theory_name)
    for note in draft.notes:
        logger.debug("%s", note)

    source, validation = rewrite_combined(
        draft,
        library,
        english_description=english,
        syntax_instructions_path=SYNTAX_DOC,
        client=client,
        use_llm=not args.no_llm and draft.needs_rewrite,
    )

    if not validation.ok:
        logger.warning("Validation issues:\n%s", validation.summary())
    else:
        logger.info("Syntax validation passed.")
        for w in validation.warnings:
            logger.warning("%s", w)

    paths = build_output(
        outputs_dir=args.outputs_dir,
        protocol_name=theory_name,
        english_description=english,
        sapic_source=source,
        matches=classification.matches,
        validation=validation,
        syntax_instructions_src=SYNTAX_DOC,
    )

    print(f"\nWrote SAPIC+ model to: {paths.root}")
    print(f"  protocol.spthy")
    print(f"  protocol-executability-lemmas/  (placeholder, no lemmas yet)")
    print(f"  ReadMe")
    print(f"  general_SAPIC+_syntax_instructions")
    return 0 if validation.ok else 2


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
