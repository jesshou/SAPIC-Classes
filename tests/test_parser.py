"""Tests for sentence splitting and intent classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.generator.class_lookup import load_library
from src.parser.intent_classifier import classify_sentences
from src.parser.sentence_splitter import split_sentences

PROJECT = Path(__file__).resolve().parents[1]
LIBRARY = load_library(PROJECT / "data" / "sapic_classes")


def test_split_basic_sentences():
    text = (
        "The client generates a nonce. "
        "The server sends a ServerHello. "
        "They close the session."
    )
    sents = split_sentences(text)
    assert len(sents) == 3
    assert "nonce" in sents[0].lower()
    assert "ServerHello" in sents[1] or "server" in sents[1].lower()
    assert "close" in sents[2].lower()


def test_split_numbered_steps():
    text = (
        "1. Generate asymmetric keys.\n"
        "2. Perform ephemeral Diffie-Hellman.\n"
        "3. Exchange application data."
    )
    sents = split_sentences(text)
    assert len(sents) == 3
    assert "asymmetric" in sents[0].lower()
    assert "diffie" in sents[1].lower()


def test_heuristic_maps_dh():
    sents = [
        "They perform an ephemeral Diffie-Hellman key exchange.",
    ]
    result = classify_sentences(sents, LIBRARY.raw, client=None, use_llm=False)
    assert result.matches
    assert "diffie_hellman_ephemeral" in result.matches[0].class_ids


def test_heuristic_maps_symmetric_enc():
    sents = [
        "The client encrypts a message with a shared symmetric key and the server decrypts it.",
    ]
    result = classify_sentences(sents, LIBRARY.raw, client=None, use_llm=False)
    ids = result.matches[0].class_ids
    assert "symmetric_encryption_decryption" in ids


def test_empty_input():
    assert split_sentences("") == []
    result = classify_sentences([], LIBRARY.raw, use_llm=False)
    assert result.matches == []
