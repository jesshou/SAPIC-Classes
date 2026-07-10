# English → SAPIC+

Translate an English-language security protocol description into a SAPIC+ theory for [Tamarin](https://tamarin-prover.com/), by mapping each sentence onto a pre-existing library of SAPIC+ building-block classes and stitching them together.

Lemmas are **not** generated yet (see `protocol-executability-lemmas/` placeholders).

## Pipeline

```
English description
        │
        ▼
 sentence_splitter   → ordered sentences
        │
        ▼
 intent_classifier   → class ID(s) per sentence  (OpenAI, with keyword fallback)
        │
        ├── 1 class  → class_lookup (direct copy, lemmas stripped)
        │
        └── N classes → combinator (deterministic stitch)
                              │
                              ▼
                         rewriter (LLM rewrite for syntax / binding)
                              │
                              ▼
                     syntax_validator
                              │
                              ▼
                     outputs/<protocol>/protocol.spthy
```

## Project layout

```
EnglishtoSAPIC+/
|-- README.md
|-- requirements.txt
|-- .env.example
|-- data/
|   |-- sapic_classes/
|   |   |-- class_library.json
|   |   |-- startup_classes.spthy
|   |   |-- datatransfer_classes.spthy
|   |   |-- cleanup_classes.spthy
|   |   `-- classes/                 # individual .spthy fragments
|   `-- general_SAPIC+_instruction.md
|-- src/
|   |-- main.py
|   |-- parser/
|   |-- llm/
|   |-- generator/
|   |-- output/
|   `-- utils/
|-- tests/
`-- outputs/
```

Class sources mirror the `SAPIC+ Classes` library:

| Phase | Classes |
|-------|---------|
| Startup | setup, asymmetric_key_generation, symmetric_key_generation, nonce, sessionID |
| DataTransfer | client_hello, server_hello, diffie_hellman_ephemeral/static, key_transport, HKDF, signature_*, asymmetric_encryption_decryption, hashing, handshake_finished, symmetric_encryption_decryption, application_data_exchange |
| Cleanup | closing |

## Setup

```bash
cd EnglishtoSAPIC+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

## Usage

```bash
# Inline description
python -m src.main -d "The client and server generate asymmetric key pairs. \
They perform an ephemeral Diffie-Hellman exchange. \
Then they exchange application data under the derived key. \
Finally the session is closed."

# From a file
python -m src.main -f tests/sample_inputs/simple_dh.txt -n ephemeral_dh_app

# Heuristic-only (no OpenAI calls)
python -m src.main --no-llm -f tests/sample_inputs/simple_dh.txt
```

### CLI flags

| Flag | Meaning |
|------|---------|
| `-d` / `--description` | Inline English text |
| `-f` / `--input-file` | Path to description file |
| `-n` / `--name` | Override protocol / theory name |
| `-o` / `--outputs-dir` | Output root (default `outputs/`) |
| `--no-llm` | Keyword classifier + local stitch only |
| `--model` | Override `OPENAI_MODEL` |
| `-v` | Debug logging |

## Output

Each run writes:

```
outputs/<protocol_name>/
  protocol.spthy                         # combined SAPIC+ (no lemmas)
  protocol-executability-lemmas/         # placeholder
  ReadMe
  general_SAPIC+_syntax_instructions
```

## Tests

```bash
pytest -q
```

## Notes on combinations

When a sentence (or the full protocol) maps to **multiple** classes, the combinator merges builtins, concatenates `Client`/`Server` bodies in phase order, and threads shared `process:` values as role parameters. The rewriter then normalizes the stitch against `general_SAPIC+_instruction.md` (especially `new` scope vs `let` macro parameters) so the result is well-formed SAPIC+.
