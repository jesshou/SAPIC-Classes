"""Pipeline entry point.

Usage:
    python -m pipeline.main Input/myprotocol.txt      # one description file
    python -m pipeline.main --all                     # every .txt in Input/
    python -m pipeline.main --text "Alice sends..."   # inline description
    python -m pipeline.main --dry-run Input/x.txt     # print prompts, no LLM call

Outputs, per protocol, into Output/:
    <name>-P.spthy       the validated SAPIC+ theory
    <name>-log.json      attempt-by-attempt record (responses, tamarin output)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .extractor import extract_spthy
from .llm_client import LLMSession
from .prompt_builder import build_repair_prompt, build_system_prompt, build_user_prompt
from .validator import validate_spthy


def run_pipeline(name: str, description: str) -> bool:
    """English description -> prompt -> LLM -> extract -> validate -> Output/.

    Returns True if a validated theory was written.
    """
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    log = {
        "protocol": name,
        "model": config.OPENAI_MODEL,
        "started": datetime.now(timezone.utc).isoformat(),
        "attempts": [],
    }

    session = LLMSession(build_system_prompt())
    prompt = build_user_prompt(description)
    code = None
    success = False

    for attempt in range(1, config.MAX_REPAIR_ATTEMPTS + 2):
        print(f"[{name}] attempt {attempt}: querying {config.OPENAI_MODEL}...")
        response = session.send(prompt)
        code = extract_spthy(response)
        record = {"attempt": attempt, "response": response}

        if code is None:
            record["error"] = "no SAPIC+ code block found in response"
            log["attempts"].append(record)
            prompt = (
                "Your reply contained no SAPIC+ code. Output the complete theory "
                "in a single ```spthy fenced code block."
            )
            continue

        print(f"[{name}] attempt {attempt}: validating with tamarin-prover...")
        result = validate_spthy(code)
        record["code"] = code
        record["valid"] = result.ok
        if not result.ok:
            record["tamarin_output"] = result.output
        log["attempts"].append(record)

        if result.ok:
            success = True
            break
        print(f"[{name}] attempt {attempt}: parse failed, asking model to repair...")
        prompt = build_repair_prompt(result.output)

    log["succeeded"] = success
    log_path = config.OUTPUT_DIR / f"{name}-log.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    if success:
        out_path = config.OUTPUT_DIR / f"{name}-P.spthy"
        out_path.write_text(code, encoding="utf-8")
        print(f"[{name}] SUCCESS -> {out_path}")
    else:
        # Keep the best (last) attempt around for inspection, clearly marked.
        if code is not None:
            fail_path = config.OUTPUT_DIR / f"{name}-P.failed.spthy"
            fail_path.write_text(code, encoding="utf-8")
        print(f"[{name}] FAILED after {len(log['attempts'])} attempts; see {log_path}")
    return success


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate validated SAPIC+ from English protocol descriptions."
    )
    parser.add_argument("input", nargs="?", help="path to a .txt protocol description")
    parser.add_argument("--all", action="store_true", help="process every .txt in Input/")
    parser.add_argument("--text", help="inline English description (name it with --name)")
    parser.add_argument("--name", default="protocol", help="protocol name for --text mode")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts that would be sent, without calling the LLM")
    args = parser.parse_args()

    jobs: list[tuple[str, str]] = []
    if args.all:
        config.INPUT_DIR.mkdir(exist_ok=True)
        for txt in sorted(config.INPUT_DIR.glob("*.txt")):
            jobs.append((txt.stem, txt.read_text(encoding="utf-8")))
        if not jobs:
            print(f"No .txt files found in {config.INPUT_DIR}", file=sys.stderr)
            return 1
    elif args.text:
        jobs.append((args.name, args.text))
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Input file not found: {path}", file=sys.stderr)
            return 1
        jobs.append((path.stem, path.read_text(encoding="utf-8")))
    else:
        parser.print_help()
        return 1

    if args.dry_run:
        print("=== SYSTEM PROMPT ===\n")
        print(build_system_prompt())
        for name, description in jobs:
            print(f"\n=== USER PROMPT ({name}) ===\n")
            print(build_user_prompt(description))
        return 0

    failures = sum(0 if run_pipeline(name, desc) else 1 for name, desc in jobs)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
