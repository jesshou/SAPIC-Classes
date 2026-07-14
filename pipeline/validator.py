"""Validates SAPIC+ code by parsing it with tamarin-prover."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class ValidationResult:
    ok: bool
    output: str  # tamarin's stdout+stderr (the error message on failure)


def validate_spthy(code: str) -> ValidationResult:
    """Run `tamarin-prover --parse-only` on the code and report success/errors."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".spthy", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = Path(f.name)
    try:
        proc = subprocess.run(
            [config.TAMARIN_BINARY, "--parse-only", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=config.TAMARIN_TIMEOUT_SECONDS,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        # Hide the throwaway temp path so repair prompts stay clean.
        output = output.replace(str(tmp_path), "<theory.spthy>")
        return ValidationResult(ok=proc.returncode == 0, output=output)
    except subprocess.TimeoutExpired:
        return ValidationResult(ok=False, output="tamarin-prover timed out during parsing")
    except FileNotFoundError:
        return ValidationResult(
            ok=False,
            output=f"tamarin-prover binary not found: {config.TAMARIN_BINARY}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
