#!/usr/bin/env python3
"""Smoke test for the lean-verify scanner (no Lean toolchain required)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "lean-verify" / "scripts" / "verify_lean_project.py"
FIXTURE = ROOT / "tests" / "fixtures" / "lean-minimal"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(FIXTURE), "--output", tmp],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            return 1
        manifest = json.loads((Path(tmp) / "run-manifest.json").read_text(encoding="utf-8"))

    kinds = {hit["kind"] for hit in manifest["sorry_axiom_hits"]}
    assert "sorry" in kinds, "expected a sorry hit"
    assert "axiom" in kinds, "expected an axiom hit"
    assert manifest["machine_verification_passed"] is False, "build was not requested"
    print("lean-verify scanner smoke passed:", len(manifest["sorry_axiom_hits"]), "hits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
