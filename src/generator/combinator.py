"""Combine multiple SAPIC+ class fragments into a draft theory."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.generator.class_lookup import ClassLibrary, ClassRecord, strip_lemmas
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Preferred intra-phase order for realistic protocol flow
_DATATRANSFER_ORDER = [
    "client_hello",
    "server_hello",
    "diffie_hellman_ephemeral",
    "diffie_hellman_static",
    "key_transport",
    "asymmetric_encryption_decryption",
    "HKDF",
    "handshake_finished",
    "signature_generation_verification",
    "hashing",
    "symmetric_encryption_decryption",
    "application_data_exchange",
]
_STARTUP_ORDER = [
    "setup",
    "asymmetric_key_generation",
    "symmetric_key_generation",
    "nonce",
    "sessionID",
]
_CLEANUP_ORDER = ["closing"]


def class_sort_key(class_id: str, phase: str) -> tuple[int, int, str]:
    phase_rank = {"Startup": 0, "DataTransfer": 1, "Cleanup": 2}
    order = {
        "Startup": _STARTUP_ORDER,
        "DataTransfer": _DATATRANSFER_ORDER,
        "Cleanup": _CLEANUP_ORDER,
    }.get(phase, [])
    try:
        idx = order.index(class_id)
    except ValueError:
        idx = 99
    return (phase_rank.get(phase, 9), idx, class_id)


@dataclass
class CombinedDraft:
    """Intermediate stitched SAPIC+ theory before rewrite/validation."""

    theory_name: str
    class_ids: list[str]
    builtins: list[str] = field(default_factory=list)
    functions_block: str = ""
    client_steps: list[str] = field(default_factory=list)
    server_steps: list[str] = field(default_factory=list)
    process_news: list[str] = field(default_factory=list)
    process_params: list[str] = field(default_factory=list)
    source: str = ""
    needs_rewrite: bool = True
    notes: list[str] = field(default_factory=list)


def _extract_builtins(source: str) -> list[str]:
    m = re.search(r"builtins:\s*([^\n]+)", source)
    if not m:
        return []
    return [b.strip() for b in m.group(1).split(",") if b.strip()]


def _extract_functions(source: str) -> str:
    m = re.search(r"functions:\s*((?:.|\n)*?)(?=\n\s*let\s|\nprocess:)", source)
    if not m:
        return ""
    return m.group(0).strip()


def _extract_let_body(source: str, role: str) -> str | None:
    """Extract the body of `let Role(...) = ...` up to the next top-level let/process."""
    # Match let Client / let Client() / let Client(psk) etc.
    pattern = re.compile(
        rf"let\s+{role}\s*(?:\([^)]*\))?\s*=\s*",
        re.IGNORECASE,
    )
    m = pattern.search(source)
    if not m:
        return None
    start = m.end()
    rest = source[start:]
    # End at next `let ` at beginning of line or `process:` or `lemma`
    end_m = re.search(r"(?m)^(let\s+\w+|process:|lemma\s)", rest)
    body = rest[: end_m.start()] if end_m else rest
    body = body.strip()
    # Drop trailing 0-only placeholders when empty-ish
    return body


def _extract_process_news(source: str) -> list[str]:
    m = re.search(r"process:\s*((?:.|\n)*?)(?=\nlemma\s|\nend\s*$)", source)
    if not m:
        return []
    block = m.group(1)
    news = re.findall(r"new\s+(~?\w+)\s*;", block)
    return news


def _normalize_role_params(records: list[ClassRecord]) -> list[str]:
    """Union of parameters that should be threaded into Client/Server."""
    params: list[str] = []
    for rec in records:
        for p in rec.parameters:
            if p not in params:
                params.append(p)
    # Also promote shared process-level news commonly used as params
    shared_candidates = {"psk", "~psk"}
    for rec in records:
        for n in _extract_process_news(rec.source):
            bare = n.lstrip("~")
            if bare == "psk" and "psk" not in params:
                params.append("psk")
            elif n in shared_candidates and "psk" not in params:
                params.append("psk")
    return params


def _sequence_bodies(bodies: list[str]) -> str:
    """Join role step bodies with `;`, dropping trailing lone `0` placeholders."""
    cleaned: list[str] = []
    for body in bodies:
        if body is None:
            continue
        b = body.strip().rstrip(";")
        if not b or b == "0" or re.fullmatch(r"0\s*//.*", b):
            continue
        # Remove a trailing standalone 0 line (placeholder)
        b = re.sub(r"(?m);\s*\n\s*0\s*(//.*)?\s*$", "", b)
        b = re.sub(r"(?m)^\s*0\s*(//.*)?\s*$", "", b).strip().rstrip(";")
        if b:
            cleaned.append(b)
    if not cleaned:
        return "0"
    return ";\n    ".join(cleaned)


def _deterministic_combine(
    theory_name: str,
    records: list[ClassRecord],
) -> CombinedDraft:
    """
    Heuristic stitch: merge builtins, concatenate role bodies in phase order,
    thread shared parameters from process-level `new`s.
    """
    ordered = sorted(
        records,
        key=lambda r: class_sort_key(r.id, r.phase),
    )
    builtins: list[str] = []
    functions_parts: list[str] = []
    client_bodies: list[str] = []
    server_bodies: list[str] = []
    process_news: list[str] = []
    notes: list[str] = []

    for rec in ordered:
        src = strip_lemmas(rec.source)
        for b in _extract_builtins(src):
            if b not in builtins:
                builtins.append(b)
        fn = _extract_functions(src)
        if fn and fn not in functions_parts:
            functions_parts.append(fn)

        c_body = _extract_let_body(src, "Client")
        s_body = _extract_let_body(src, "Server")
        if c_body:
            client_bodies.append(c_body)
        if s_body:
            server_bodies.append(s_body)

        for n in _extract_process_news(src):
            bare = n.lstrip("~")
            existing_bares = {x.lstrip("~") for x in process_news}
            if bare not in existing_bares:
                process_news.append(n)

        notes.append(f"Included class `{rec.id}` ({rec.phase})")

    params = _normalize_role_params(ordered)
    # Ensure process news covers params (prefer ~psk style)
    existing_bares = {n.lstrip("~") for n in process_news}
    for p in params:
        if p.lstrip("~") not in existing_bares:
            process_news.append(f"~{p}" if not p.startswith("~") else p)
            existing_bares.add(p.lstrip("~"))

    param_sig = ", ".join(params)
    client_body = _sequence_bodies(client_bodies)
    server_body = _sequence_bodies(server_bodies)

    client_let = (
        f"let Client({param_sig}) =\n    {client_body}"
        if params
        else f"let Client() =\n    {client_body}"
    )
    server_let = (
        f"let Server({param_sig}) =\n    {server_body}"
        if params
        else f"let Server() =\n    {server_body}"
    )

    news_lines = "".join(f"new {n};\n" for n in process_news)
    if params:
        call = ", ".join(p if p in process_news else (
            next((n for n in process_news if n.lstrip("~") == p), p)
        ) for p in params)
        process_block = f"{news_lines}( !Client({call}) | !Server({call}) )"
    else:
        process_block = f"{news_lines}( !Client() | !Server() )"

    builtins_line = f"builtins: {', '.join(builtins)}\n\n" if builtins else ""
    functions_block = ""
    if functions_parts:
        # Prefer a single merged functions: block
        funcs = []
        for part in functions_parts:
            inner = re.sub(r"^functions:\s*", "", part.strip())
            for line in inner.splitlines():
                line = line.strip().rstrip(",")
                if line and line not in funcs:
                    funcs.append(line)
            functions_block = "functions:\n    " + ",\n    ".join(funcs) + "\n\n"

    source = (
        f"theory {theory_name}\n"
        f"begin\n\n"
        f"/* Combined from: {', '.join(r.id for r in ordered)} */\n"
        f"/* NOTE: deterministic stitch — rewrite step should normalize binding/scope. */\n\n"
        f"{builtins_line}"
        f"{functions_block}"
        f"{client_let}\n\n"
        f"{server_let}\n\n"
        f"process:\n"
        f"{process_block}\n\n"
        f"end\n"
    )

    return CombinedDraft(
        theory_name=theory_name,
        class_ids=[r.id for r in ordered],
        builtins=builtins,
        functions_block=functions_block,
        client_steps=client_bodies,
        server_steps=server_bodies,
        process_news=process_news,
        process_params=params,
        source=source,
        needs_rewrite=True,
        notes=notes,
    )


def combine_classes(
    library: ClassLibrary,
    class_ids: list[str],
    theory_name: str = "CombinedProtocol",
) -> CombinedDraft:
    """
    Combine multiple class IDs into a draft SAPIC+ theory.

    Single-class requests return the class source (lemmas stripped) and
    mark needs_rewrite=False. Multi-class requests always need rewrite.
    """
    # Preserve order but drop duplicates
    seen: set[str] = set()
    unique_ids: list[str] = []
    for cid in class_ids:
        if cid not in seen:
            seen.add(cid)
            unique_ids.append(cid)

    records = library.get_many(unique_ids)

    if len(records) == 1:
        rec = records[0]
        src = strip_lemmas(rec.source)
        # Rename theory to requested name
        src = re.sub(
            r"^theory\s+\w+",
            f"theory {theory_name}",
            src,
            count=1,
            flags=re.MULTILINE,
        )
        return CombinedDraft(
            theory_name=theory_name,
            class_ids=[rec.id],
            builtins=_extract_builtins(src),
            source=src,
            needs_rewrite=False,
            notes=[f"Direct 1-to-1 lookup of `{rec.id}`"],
        )

    logger.info("Combining classes: %s", ", ".join(unique_ids))
    return _deterministic_combine(theory_name, records)
