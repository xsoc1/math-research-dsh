#!/usr/bin/env python3
"""Adversarial smoke test for cross-root formalization handoffs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills" / "math-research-workflow"
    / "scripts"
    / "formalization_handoff.py"
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        write(
            project / "blueprint-project.json",
            json.dumps({"project_id": "PARENT", "schema_version": "fixture"}),
        )
        source_root = project / "runs" / "isolation" / "workspace"
        write(
            source_root / "project.json",
            json.dumps({"project_id": "SCOPED", "schema_version": 1}),
        )
        proof = source_root / "runs" / "R-DEMO" / "candidate_proof.md"
        source_artifact = source_root / "lean-proof" / "SL" / "Scaffold.lean"
        destination_artifact = project / "lean-proof" / "SL" / "Scaffold.lean"
        write(proof, "# STRICT partial theorem\n")
        scaffold_text = "-- SCAFFOLD\ntheorem demo : True := by\n\tsorry\n"
        write(source_artifact, scaffold_text)
        write(destination_artifact, scaffold_text)
        status_path = project / "lean-proof" / "STATUS.md"
        write(
            status_path,
            "- `SL/Scaffold.lean` | RIGOROUS_PARTIAL_RESULT | R-DEMO\n",
        )
        manifest = {
            "schema_version": 1,
            "run_id": "R-DEMO",
            "formalization": "scaffold",
            "formalization_manifest": "lean-proof/SL/Scaffold.lean",
            "artifacts": [
                {
                    "artifact_path": "runs/R-DEMO/candidate_proof.md",
                    "sha256": sha256(proof),
                },
                {
                    "artifact_path": "lean-proof/SL/Scaffold.lean",
                    "sha256": sha256(source_artifact),
                },
            ],
        }
        manifest_path = source_root / "runs" / "R-DEMO" / "run-manifest.json"
        write(manifest_path, json.dumps(manifest, indent=2) + "\n")
        output = "research/formalization-handoffs/FH-20260830-demo.json"
        seal_arguments = (
            "seal",
            "--project",
            str(project),
            "--handoff-id",
            "FH-20260830-demo",
            "--source-root",
            "runs/isolation/workspace",
            "--source-manifest",
            "runs/R-DEMO/run-manifest.json",
            "--source-proof",
            "runs/R-DEMO/candidate_proof.md",
            "--destination-root",
            ".",
            "--destination-artifact",
            "lean-proof/SL/Scaffold.lean",
            "--registration",
            "lean-proof/STATUS.md::SL/Scaffold.lean",
            "--output",
            output,
            "--created-at",
            "2026-08-30T20:00:00.1234567+08:00",
        )
        seal = run(*seal_arguments)
        if seal.returncode != 0 or "SEALED: FH-20260830-demo" not in seal.stdout:
            print("valid formalization handoff did not seal")
            print(seal.stdout)
            print(seal.stderr)
            return 1

        verify = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if verify.returncode != 0 or "READY: FH-20260830-demo" not in verify.stdout:
            print("sealed formalization handoff did not verify")
            print(verify.stdout)
            print(verify.stderr)
            return 1

        duplicate = run(*seal_arguments)
        if duplicate.returncode == 0 or "already exists" not in duplicate.stdout:
            print("immutable handoff output was overwritten")
            print(duplicate.stdout)
            return 1

        write(destination_artifact, scaffold_text + "-- changed\n")
        changed_copy = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if changed_copy.returncode == 0 or "hash mismatch" not in changed_copy.stdout:
            print("changed destination artifact did not invalidate the handoff")
            print(changed_copy.stdout)
            return 1
        write(destination_artifact, scaffold_text)

        write(
            status_path,
            status_path.read_text(encoding="utf-8") + "- unrelated later entry\n",
        )
        evolved_index = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if evolved_index.returncode != 0:
            print("append-only registration evolution invalidated its durable anchor")
            print(evolved_index.stdout)
            return 1
        write(status_path, "- unrelated later entry\n")
        missing_anchor = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if (
            missing_anchor.returncode == 0
            or "required anchor is missing" not in missing_anchor.stdout
        ):
            print("missing destination registration anchor was not detected")
            print(missing_anchor.stdout)
            return 1

        handoff_path = project / output
        record = json.loads(handoff_path.read_text(encoding="utf-8"))
        record["destination"]["logical_root"] = ".."
        write(handoff_path, json.dumps(record, indent=2) + "\n")
        escaped = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if escaped.returncode == 0 or "escapes its logical root" not in escaped.stdout:
            print("escaping logical root in the handoff record was not rejected")
            print(escaped.stdout)
            return 1

    print("formalization handoff smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
