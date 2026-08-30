#!/usr/bin/env python3
"""Smoke test for self-contained scoped pipeline validation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def packet(source_path: str = "baseline.txt", source_hash: str = "") -> str:
    source_row = ""
    if source_hash:
        source_row = (
            "| baseline | 1.0 | "
            f"{source_path} | {source_hash} | source | checked |\n"
        )
    return (
        "# Research task packet\n\n"
        "- **Task ID:** `Q-20260830-scope-AB12CD34`\n"
        "- **Project ID:** `SCOPED-DEMO`\n"
        "- **Task type:** solve\n"
        "- **Task state:** `READY`\n\n"
        "## Source bundle\n\n"
        "| Item | Stable ID / version | Path or URL | Hash | Role | Verification note |\n"
        "|---|---|---|---|---|---|\n"
        f"{source_row}\n"
        "## Novelty preflight (B0)\n\n"
        "- **Openness verdict:** OPEN (checked 2026-08-30)\n"
        "- **Novelty audit path:** refs/novelty.md\n"
        "- **Snapshot hash:** `sha256:scoped-fixture`\n\n"
        "## Required run location\n\n"
        "`runs/rigorous-open-math-research/R-SCOPED`\n\n"
        "## Upstream invocation\n\n"
        "Use `$rigorous-open-math-research`.\n"
    )


def run(project: Path, scope: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--project", str(project)]
    if scope is not None:
        command.extend(["--scope", scope])
    return subprocess.run(command, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        write(
            project / "agenda" / "task-packets" / "Q-broken.md",
            "# Broken legacy packet\n",
        )

        good_scope = project / "runs" / "new-scope" / "workspace"
        write(good_scope / "project.json", json.dumps({"project_id": "SCOPED-DEMO"}))
        write(
            good_scope / "agenda" / "task-packets" / "Q-scoped.md",
            packet(),
        )

        whole = run(project)
        if whole.returncode == 0:
            print("whole-project validation unexpectedly ignored the broken legacy packet")
            return 1

        scope_value = "runs/new-scope/workspace"
        scoped = run(project, scope_value)
        if scoped.returncode != 0:
            print("valid self-contained scope unexpectedly failed")
            print(scoped.stdout)
            print(scoped.stderr)
            return 1
        required_output = (
            "scoped logical project root",
            "not a whole-project PASS",
            "scoped result: 0 problem(s)",
        )
        if any(text not in scoped.stdout for text in required_output):
            print("scoped result did not carry the required non-global disclosure")
            print(scoped.stdout)
            return 1

        outside = project / "runs" / "new-scope" / "outside.txt"
        write(outside, "outside scope\n")
        outside_hash = hashlib.sha256(outside.read_bytes()).hexdigest().upper()
        escape_scope = project / "runs" / "new-scope" / "escape"
        write(escape_scope / "project.json", json.dumps({"project_id": "ESCAPE"}))
        write(
            escape_scope / "agenda" / "task-packets" / "Q-escape.md",
            packet("../outside.txt", outside_hash),
        )
        escaped = run(project, "runs/new-scope/escape")
        if escaped.returncode == 0 or "escapes the validation root" not in escaped.stdout:
            print("scoped validation did not reject an escaping source binding")
            print(escaped.stdout)
            return 1

        markerless = project / "runs" / "new-scope" / "markerless"
        markerless.mkdir(parents=True)
        missing_marker = run(project, "runs/new-scope/markerless")
        if missing_marker.returncode != 2 or "has no project.json" not in missing_marker.stdout:
            print("markerless scope was not rejected before validation")
            print(missing_marker.stdout)
            return 1

        outside_root = run(project, "..")
        if outside_root.returncode != 2 or "escapes the project root" not in outside_root.stdout:
            print("scope path outside the project was not rejected")
            print(outside_root.stdout)
            return 1

    print("scoped pipeline smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
