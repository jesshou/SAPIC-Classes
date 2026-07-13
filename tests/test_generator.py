"""Tests for class lookup, combinator, validator, and end-to-end --no-llm run."""

from __future__ import annotations

from pathlib import Path

from src.generator.class_lookup import load_library, lookup_direct, strip_lemmas
from src.generator.combinator import combine_classes
from src.generator.syntax_validator import validate_sapic
from src.output.file_builder import build_output
from src.parser.intent_classifier import ClassMatch, classify_sentences
from src.parser.sentence_splitter import split_sentences

PROJECT = Path(__file__).resolve().parents[1]
LIBRARY = load_library(PROJECT / "data" / "sapic_classes")


def test_strip_lemmas_removes_lemma_blocks():
    # Lemmas now live in data/sapic_classes/lemmas/, pulled in via #include;
    # strip_lemmas must drop that #include too so generated output doesn't
    # carry a path that's only valid relative to the library, not outputs/.
    src = LIBRARY.get("diffie_hellman_ephemeral").source
    assert "#include" in src
    assert "lemma " not in src
    stripped = strip_lemmas(src)
    assert "lemma " not in stripped
    assert "#include" not in stripped
    assert "let Client" in stripped
    assert "process:" in stripped
    assert stripped.strip().endswith("end")


def test_direct_lookup():
    src = lookup_direct(LIBRARY, "client_hello")
    assert "theory" in src
    assert "lemma " not in src
    assert "ClientHello" in src or "Client" in src


def test_combine_single_no_rewrite_flag():
    draft = combine_classes(LIBRARY, ["nonce"], theory_name="JustNonce")
    assert draft.needs_rewrite is False
    assert draft.theory_name == "JustNonce"
    assert "lemma " not in draft.source
    result = validate_sapic(draft.source)
    assert result.ok, result.summary()


def test_combine_multiple_needs_rewrite():
    draft = combine_classes(
        LIBRARY,
        ["symmetric_key_generation", "symmetric_encryption_decryption", "closing"],
        theory_name="SymEncClose",
    )
    assert draft.needs_rewrite is True
    assert "symmetric-encryption" in draft.builtins or "symmetric-encryption" in draft.source
    assert "let Client" in draft.source
    assert "process:" in draft.source
    result = validate_sapic(draft.source)
    # Deterministic stitch should at least be structurally valid
    assert result.ok, result.summary()


def test_validator_rejects_lemmas():
    bad = """theory Bad
begin
let Client() = 0
process:
( !Client() )
lemma foo: exists-trace \"Ex #i. True\"
end
"""
    result = validate_sapic(bad)
    assert not result.ok
    assert any("Lemma" in e or "lemma" in e.lower() for e in result.errors)


def test_end_to_end_no_llm(tmp_path: Path):
    text = (PROJECT / "tests" / "sample_inputs" / "symmetric_transport.txt").read_text()
    sentences = split_sentences(text)
    classification = classify_sentences(
        sentences, LIBRARY.raw, client=None, use_llm=False
    )
    ids: list[str] = []
    seen: set[str] = set()
    for m in classification.matches:
        for cid in m.class_ids:
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
    draft = combine_classes(LIBRARY, ids, theory_name="sym_transport")
    result = validate_sapic(draft.source)
    paths = build_output(
        outputs_dir=tmp_path,
        protocol_name="sym_transport",
        english_description=text,
        sapic_source=draft.source,
        matches=classification.matches,
        validation=result,
    )
    assert paths.protocol_spthy.exists()
    assert paths.readme.exists()
    assert (paths.lemmas_dir / "README.md").exists()
    content = paths.protocol_spthy.read_text()
    assert "lemma " not in content
