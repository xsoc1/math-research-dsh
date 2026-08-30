#!/usr/bin/env python3
"""Adversarial smoke test for the plugin-owned Blueprint v2.2 gateway."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATEWAY = (
    ROOT
    / "skills" / "manage-math-research-program" / "runtime"
    / "blueprintctl.py"
)
ASSET_ROOT = (
    ROOT
    / "skills" / "manage-math-research-program"
    / "assets"
    / "blueprint-accepted-knowledge"
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATEWAY), *arguments],
        capture_output=True,
        text=True,
    )


def seed_blueprint() -> dict[str, object]:
    template = (ASSET_ROOT / "blueprint.json").read_text(encoding="utf-8")
    rendered = (
        template.replace("{{PROJECT_ID}}", "P-BLUEPRINT-GATEWAY")
        .replace("{{PROJECT_NAME_JSON}}", json.dumps("Blueprint gateway fixture"))
        .replace("{{CREATED_AT}}", "2026-08-31T00:00:00Z")
    )
    blueprint = json.loads(rendered)
    node = {
        "id": "DEF-GATEWAY-ARTIFACT",
        "type": "definition",
        "title": "Gateway artifact root contract",
        "statement": "Relative evidence locators resolve from the configured artifact root.",
        "status": "active",
        "grade": "A",
        "mainline": "support",
        "epistemic_type": "definition_contract",
        "context_id": "CTX-DEFAULT",
        "truth_bearing": False,
        "source_kind": "project",
    }
    blueprint["nodes"] = [node]
    blueprint["math_profile"]["contexts"][0]["definitions"] = [node["id"]]
    return blueprint


def seed_project(project: Path) -> None:
    marker = {
        "schema_version": "blueprint-project-layout/v1",
        "project_id": "P-BLUEPRINT-GATEWAY",
        "blueprint_schema": "2.2",
        "runtime_api": "blueprint-runtime/v1",
        "paths": {
            "blueprint_root": "blueprint",
            "research_root": "research",
            "artifact_root": "research",
            "work_root": "research/work",
        },
    }
    write_json(project / "blueprint-project.json", marker)
    config = json.loads(
        (ASSET_ROOT / ".blueprint" / "config.json").read_text(encoding="utf-8")
    )
    config.update(
        {
            "request_log": ".blueprint/audit/events.jsonl",
            "merge_lock": "../research/work/runtime/locks/merge.lock",
            "transactions_dir": "../research/work/runtime/transactions",
            "artifact_root": "../research",
            "validation_work_dir": "../research/work/runtime/validation",
        }
    )
    write_json(project / "blueprint" / ".blueprint" / "config.json", config)
    write_json(project / "blueprint" / "blueprint.json", seed_blueprint())
    write(
        project / "blueprint" / "evidence_inventory.csv",
        "result_id,title,mainline,epistemic_type,blueprint_node_id,grade,status,"
        "headline_value,scope,primary_artifact,main_limitation\n"
        "EV-GATEWAY,Gateway artifact,support,definition_contract,"
        "DEF-GATEWAY-ARTIFACT,A,active,fixture,fixture,artifacts/proof.md,none\n",
    )
    write(project / "research" / "artifacts" / "proof.md", "# Bound artifact\n")
    write(
        project / "blueprint" / "tools" / "validate_blueprint.py",
        "raise SystemExit(99)\n",
    )


def parse_output(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(completed.stdout or completed.stderr)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir) / "project"
        seed_project(project)

        premature = run("query", "--project", str(project), "snapshot")
        if premature.returncode == 0 or "ENSURE_REQUIRED" not in premature.stderr:
            print("query did not fail closed before ensure")
            print(premature.stdout)
            print(premature.stderr)
            return 1

        first = run("ensure", "--project", str(project))
        if first.returncode != 0 or parse_output(first).get("status") != "READY":
            print("first ensure did not produce READY")
            print(first.stdout)
            print(first.stderr)
            return 1
        state = project / "research" / "work" / "runtime" / "blueprint-gateway.json"
        first_state_hash = sha256(state)
        second = run("ensure", "--project", str(project))
        if second.returncode != 0 or parse_output(second).get("status") != "ALREADY_READY":
            print("second ensure was not idempotent")
            print(second.stdout)
            return 1
        if sha256(state) != first_state_hash:
            print("idempotent ensure rewrote its runtime state")
            return 1

        validation = run("validate", "--project", str(project))
        if validation.returncode != 0 or '"inventory_links_valid": true' not in validation.stdout:
            print("plugin-owned validation failed")
            print(validation.stdout)
            print(validation.stderr)
            return 1

        artifact = run(
            "query",
            "--project",
            str(project),
            "artifact-meta",
            "--node",
            "DEF-GATEWAY-ARTIFACT",
            "--verify-sha256",
        )
        artifact_payload = parse_output(artifact)
        records = artifact_payload.get("result", {}).get("artifacts", [])
        if (
            artifact.returncode != 0
            or len(records) != 1
            or records[0].get("exists") is not True
            or records[0].get("external_to_artifact_root") is not False
            or Path(records[0]["resolved_path"]) != project / "research" / "artifacts" / "proof.md"
        ):
            print("query did not honor the external artifact root")
            print(artifact.stdout)
            print(artifact.stderr)
            return 1

        submission = project / "blueprint" / "submissions" / "SUB-GATEWAY-NOOP"
        proposal = {
            "schema_version": "2.2",
            "submission_id": submission.name,
            "author_agent_id": "gateway-smoke-author",
            "created_at": "2026-08-31T00:00:00Z",
            "base_blueprint_hash": sha256(project / "blueprint" / "blueprint.json"),
            "base_inventory_hash": sha256(project / "blueprint" / "evidence_inventory.csv"),
            "operations": [],
            "inventory_operations": [],
            "write_set": {
                "existing_nodes": {},
                "new_node_ids": [],
                "inventory_rows": {},
            },
            "read_set": {"upstream_nodes": {}},
            "review_evidence": {},
        }
        write_json(submission / "proposal.json", proposal)
        proposal_validation = run(
            "validate-submission",
            "--project",
            str(project),
            "--submission",
            "submissions/SUB-GATEWAY-NOOP",
            "--actor-agent-id",
            "gateway-smoke-validator",
        )
        if proposal_validation.returncode != 0:
            print("gateway proposal validation failed")
            print(proposal_validation.stdout)
            print(proposal_validation.stderr)
            return 1
        validation_record = json.loads(
            (submission / "validation.json").read_text(encoding="utf-8")
        )
        if validation_record.get("valid") is not True:
            print("no-op proposal did not reach the plugin-owned validator")
            print(proposal_validation.stdout)
            return 1

        config_path = project / "blueprint" / ".blueprint" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["fixture_revision"] = 1
        write_json(config_path, config)
        stale_binding = run("query", "--project", str(project), "snapshot")
        if stale_binding.returncode == 0 or "REENSURE_REQUIRED" not in stale_binding.stderr:
            print("configuration drift did not invalidate the ensure binding")
            print(stale_binding.stdout)
            print(stale_binding.stderr)
            return 1
        refreshed = run("ensure", "--project", str(project))
        if refreshed.returncode != 0 or parse_output(refreshed).get("status") != "REFRESHED":
            print("changed configuration did not refresh the runtime binding")
            print(refreshed.stdout)
            print(refreshed.stderr)
            return 1

        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["artifact_root"] = "../escaped-artifacts"
        write_json(config_path, config)
        mismatch = run("ensure", "--project", str(project))
        if mismatch.returncode == 0 or "ARTIFACT_ROOT_MISMATCH" not in mismatch.stderr:
            print("layout and config artifact-root mismatch was accepted")
            print(mismatch.stdout)
            print(mismatch.stderr)
            return 1

        marker_path = project / "blueprint-project.json"
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["paths"]["work_root"] = "../../escaped-work"
        write_json(marker_path, marker)
        escaped = run("ensure", "--project", str(project))
        if escaped.returncode == 0 or "LAYOUT_PATH_ESCAPE" not in escaped.stderr:
            print("escaping layout path was accepted")
            print(escaped.stdout)
            print(escaped.stderr)
            return 1

    print("blueprint gateway smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
