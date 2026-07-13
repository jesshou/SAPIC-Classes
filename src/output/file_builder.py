"""Assemble the per-protocol output directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.generator.syntax_validator import ValidationResult
from src.parser.intent_classifier import ClassMatch
from src.utils.file_io import ensure_dir, read_text, write_text


@dataclass
class OutputPaths:
    """Paths written for one protocol run."""

    root: Path
    protocol_spthy: Path
    lemmas_dir: Path
    readme: Path


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "protocol"


def _render_class_mapping(matches: list[ClassMatch]) -> str:
    lines = []
    for i, m in enumerate(matches, 1):
        combo = " (combination)" if m.is_combination else ""
        lines.append(
            f"{i}. **{m.phase}**{combo}: `{', '.join(m.class_ids)}`\n"
            f"   - \"{m.sentence}\"\n"
            f"   - {m.rationale or 'n/a'}"
        )
    return "\n".join(lines) if lines else "_No mappings._"


def build_output(
    *,
    outputs_dir: Path | str,
    protocol_name: str,
    english_description: str,
    sapic_source: str,
    matches: list[ClassMatch],
    validation: ValidationResult,
    readme_template_src: Path | str | None = None,
) -> OutputPaths:
    """
    Write:

        outputs/<protocol_name>/
          protocol.spthy
          protocol-executability-lemmas/   (placeholder)
          ReadMe
    """
    root = ensure_dir(Path(outputs_dir) / _slugify(protocol_name))
    lemmas_dir = ensure_dir(root / "protocol-executability-lemmas")
    write_text(
        lemmas_dir / "README.md",
        (
            "# protocol-executability-lemmas\n\n"
            "Placeholder for shared/reusable executability lemmas.\n"
            "Lemmas are not generated yet.\n"
        ),
    )

    protocol_spthy = write_text(root / "protocol.spthy", sapic_source)

    template_path = (
        Path(readme_template_src)
        if readme_template_src
        else Path(__file__).parent / "templates" / "readme_template.md"
    )
    template = read_text(template_path)
    readme_body = (
        template.replace("{{protocol_name}}", protocol_name)
        .replace("{{english_description}}", english_description.strip())
        .replace("{{class_mapping}}", _render_class_mapping(matches))
        .replace("{{validation_summary}}", validation.summary())
    )
    # User-requested filename is `ReadMe` (no extension)
    readme = write_text(root / "ReadMe", readme_body)

    return OutputPaths(
        root=root,
        protocol_spthy=protocol_spthy,
        lemmas_dir=lemmas_dir,
        readme=readme,
    )
