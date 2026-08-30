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

        unbound_registration = run(
            "consume",
            "--project",
            str(project),
            "--handoff",
            output,
            "--stage-c-registration",
            "lean-proof/STATUS.md::R-DEMO",
        )
        if (
            unbound_registration.returncode == 0
            or "must exactly match one handoff registration"
            not in unbound_registration.stdout
        ):
            print("unbound Stage C registration was accepted")
            print(unbound_registration.stdout)
            return 1

        consume_arguments = (
            "consume",
            "--project",
            str(project),
            "--handoff",
            output,
            "--stage-c-registration",
            "lean-proof/STATUS.md::SL/Scaffold.lean",
            "--consumed-at",
            "2026-08-30T21:00:00.1234567+08:00",
        )
        consume = run(*consume_arguments)
        consumption = "research/formalization-handoffs/FHC-20260830-demo.json"
        if consume.returncode != 0 or "CONSUMED: FHC-20260830-demo" not in consume.stdout:
            print("valid Stage C consumption did not record")
            print(consume.stdout)
            print(consume.stderr)
            return 1
        consumption_verify = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if (
            consumption_verify.returncode != 0
            or "CONSUMED_READY: FHC-20260830-demo" not in consumption_verify.stdout
        ):
            print("valid Stage C consumption did not verify")
            print(consumption_verify.stdout)
            return 1

        write(destination_artifact, scaffold_text + "-- Stage C evolution\n")
        evolved_destination_receipt = run(
            "verify", "--project", str(project), "--handoff", output
        )
        if (
            evolved_destination_receipt.returncode == 0
            or "hash mismatch" not in evolved_destination_receipt.stdout
        ):
            print("evolved destination unexpectedly preserved pre-consumption READY")
            print(evolved_destination_receipt.stdout)
            return 1
        evolved_destination_consumption = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if evolved_destination_consumption.returncode != 0:
            print("legitimate Stage C evolution invalidated consumption history")
            print(evolved_destination_consumption.stdout)
            return 1
        write(destination_artifact, scaffold_text)

        duplicate_consumption = run(*consume_arguments)
        if (
            duplicate_consumption.returncode == 0
            or "already exists" not in duplicate_consumption.stdout
        ):
            print("duplicate Stage C consumption was accepted")
            print(duplicate_consumption.stdout)
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
        evolved_consumption = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if evolved_consumption.returncode != 0:
            print("append-only index evolution invalidated Stage C consumption")
            print(evolved_consumption.stdout)
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
        missing_consumption_anchor = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if (
            missing_consumption_anchor.returncode == 0
            or "required anchor is missing" not in missing_consumption_anchor.stdout
        ):
            print("missing Stage C consumption anchor was not detected")
            print(missing_consumption_anchor.stdout)
            return 1

        write(
            status_path,
            "- `SL/Scaffold.lean` | RIGOROUS_PARTIAL_RESULT | R-DEMO\n",
        )
        consumption_path = project / consumption
        consumption_record = json.loads(consumption_path.read_text(encoding="utf-8"))
        original_consumption = json.dumps(consumption_record, indent=2) + "\n"
        consumption_record["effects"]["verification_status"] = "FORMALLY_VERIFIED"
        write(consumption_path, json.dumps(consumption_record, indent=2) + "\n")
        promoted = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if promoted.returncode == 0 or "must leave" not in promoted.stdout:
            print("consumption record promoted formal verification status")
            print(promoted.stdout)
            return 1
        write(consumption_path, original_consumption)

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
        stale_consumption = run(
            "verify-consumption",
            "--project",
            str(project),
            "--consumption",
            consumption,
        )
        if stale_consumption.returncode == 0 or "hash mismatch" not in stale_consumption.stdout:
            print("changed handoff did not invalidate its consumption record")
            print(stale_consumption.stdout)
            return 1

    print("formalization handoff smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
