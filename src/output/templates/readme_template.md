# {{protocol_name}}

Generated SAPIC+ model from an English protocol description.

## Source description

{{english_description}}

## Mapped SAPIC+ classes

{{class_mapping}}

## Pipeline notes

- Sentences were parsed and classified against the pre-existing SAPIC+ class library.
- Direct 1-to-1 matches use the library fragment as-is (lemmas stripped).
- Combinations are stitched, then rewritten to adhere to SAPIC+ syntax.
- **Lemmas are intentionally omitted** (see `protocol-executability-lemmas/`).

## Validation

{{validation_summary}}

## Files

| Path | Purpose |
|------|---------|
| `protocol.spthy` | Combined SAPIC+ theory (no lemmas) |
| `protocol-executability-lemmas/` | Placeholder for future executability lemmas |
| `general_SAPIC+_syntax_instructions` | Syntax rules used during generation |
| `ReadMe` | This file |

## Running with Tamarin

```bash
tamarin-prover protocol.spthy
# or interactively:
tamarin-prover interactive protocol.spthy
```
