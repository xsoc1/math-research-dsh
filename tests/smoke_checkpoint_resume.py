#!/usr/bin/env python3
"""Adversarial smoke test for interruption checkpoint and resume semantics."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "math-research-workflow" / "scripts" / "checkpoint_resume.py"
PIPELINE = ROOT / "skills" / "math-research-workflow" / "scripts" / "validate_pipeline.py"
WORKFLOW = ROOT / "skills" / "math-research-workflow"
WORKFLOW_SKILL = WORKFLOW
FULL_FLOW = ROOT / "docs" / "pipeline-full-flow.md"


def sha256(path: Path) -> str:
	digest = hashlib.sha256()
	digest.update(path.read_bytes())
	return digest.hexdigest()


def binding(project: Path, path: Path) -> dict[str, str]:
	return {"path": path.relative_to(project).as_posix(), "sha256": sha256(path)}


def write_json(path: Path, value: object) -> None:
	path.write_text(
		json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
		encoding="utf-8",
		newline="\n",
	)


def run(*args: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args],
		capture_output=True,
		text=True,
	)


def run_pipeline(project: Path) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(PIPELINE), "--project", str(project)],
		capture_output=True,
		text=True,
	)


def load_checkpoint_module():
	spec = importlib.util.spec_from_file_location("checkpoint_resume_smoke", SCRIPT)
	if spec is None or spec.loader is None:
		raise AssertionError("cannot load checkpoint_resume module")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def fixture(root: Path) -> tuple[Path, Path, Path]:
	project = root / "project"
	run_dir = project / "runs" / "R-20260829T120000Z-quota"
	run_dir.mkdir(parents=True)
	files = {
		"task": run_dir / "task.md",
		"whiteboard": run_dir / "whiteboard.md",
		"proof": run_dir / "partial_proof.md",
		"audit": run_dir / "audit_report.md",
		"prompt": run_dir / "prompt.md",
		"harness": run_dir / "run.ps1",
		"source": run_dir / "source-manifest.json",
	}
	for name, path in files.items():
		path.write_text(f"{name} fixture\n", encoding="utf-8", newline="\n")
	files["whiteboard"].write_text(
		"""# Whiteboard

- **Run ID:** `R-20260829T120000Z-quota`
- **Task packet ID:** `Q-checkpoint-smoke`

## Current plan

Continue O2 after resume.

## Route history

- route-a `[PARTIAL]`: O1 closed, O2 remains.

## Ideas to return to

None.

## Open obligations

- O2.

## Key artifacts

- partial_proof.md.
""",
		encoding="utf-8",
		newline="\n",
	)
	state = {
		"schema_version": 1,
		"checkpoint_sequence": 0,
		"predecessor": None,
		"run_id": "R-20260829T120000Z-quota",
		"task_packet_id": "Q-checkpoint-smoke",
		"reason": "QUOTA_BOUNDARY",
		"created_at": "2026-08-29T12:30:00Z",
		"source_commit": "1" * 40,
		"task_contract": binding(project, files["task"]),
		"closure_gate": None,
		"whiteboard": binding(project, files["whiteboard"]),
		"latest_audit": binding(project, files["audit"]),
		"completed_obligations": [
			{"id": "O1", "evidence": binding(project, files["proof"])}
		],
		"open_obligations": [
			{
				"id": "O2",
				"exact_gap": "Prove the endpoint estimate.",
				"next_action": {
					"action_id": "continue-o2",
					"description": "Check the prepared endpoint lemma.",
				},
				"required_inputs": [binding(project, files["proof"])],
			}
		],
		"inflight_work": [],
		"inflight_reconciliation": [],
		"do_not_repeat": [
			{
				"action_id": "route-failed",
				"reason": "Exact counterexample already recorded.",
				"evidence": binding(project, files["proof"]),
			}
		],
		"result_status": "RIGOROUS_PARTIAL_RESULT",
		"status_transition": None,
		"experiment_integrity": {
			"enabled": True,
			"arm_id": "A-plugin",
			"task_id": "U2",
			"workspace_id": "workspace-a",
			"prompt": binding(project, files["prompt"]),
			"harness": binding(project, files["harness"]),
			"source_snapshot": binding(project, files["source"]),
			"hidden_gold_state": "SEALED",
			"metrics_scope": "cumulative_pre_checkpoint",
			"checkpoint_overhead_policy": "separate_unscored",
			"cost_status": "MEASURED",
			"segment_index": 0,
			"cumulative_metrics": {
				"model_responses": 72,
				"tool_calls": 58,
				"uncached_input_tokens": 338812,
				"cached_input_tokens": 1000,
				"output_tokens": 125692,
				"wall_seconds": 1881.05,
				"cost_usd": 5.183904,
			},
		},
		"resume": {
			"first_action": {
				"kind": "CONTINUE_OBLIGATION",
				"action_id": "continue-o2",
				"target_id": "O2",
			},
			"minimal_read_set": [
				binding(project, files["task"]),
				binding(project, files["whiteboard"]),
				binding(project, files["proof"]),
			],
			"budget": {"unit": "wall_minutes", "limit": 30},
			"stop_condition": "Stop after O2 closes or the 30-minute segment ends.",
		},
	}
	state_path = run_dir / "interruption_state-00.json"
	checkpoint_path = run_dir / "interruption_checkpoint-00.json"
	write_json(state_path, state)
	return project, state_path, checkpoint_path


def seal_and_resume(
	project: Path,
	state_path: Path,
	checkpoint_path: Path,
	*,
	resumed_at: str = "2026-08-29T13:00:00Z",
) -> Path:
	sealed = run(
		"seal", "--project", str(project), "--state", str(state_path),
		"--output", str(checkpoint_path),
	)
	if sealed.returncode != 0:
		raise AssertionError(f"initial seal failed:\n{sealed.stdout}\n{sealed.stderr}")
	receipt_path = checkpoint_path.with_name("resume_receipt-00.json")
	resumed = run(
		"resume", "--project", str(project), "--checkpoint", str(checkpoint_path),
		"--receipt", str(receipt_path), "--resumed-at", resumed_at,
	)
	if resumed.returncode != 0:
		raise AssertionError(f"initial resume failed:\n{resumed.stdout}\n{resumed.stderr}")
	return receipt_path


def next_state(
	project: Path,
	state_path: Path,
	checkpoint_path: Path,
	receipt_path: Path,
) -> tuple[Path, Path, dict[str, object]]:
	state = json.loads(state_path.read_text(encoding="utf-8"))
	state["checkpoint_sequence"] = 1
	state["predecessor"] = {
		"checkpoint": binding(project, checkpoint_path),
		"resume_receipt": binding(project, receipt_path),
	}
	state["created_at"] = "2026-08-29T14:00:00Z"
	state["experiment_integrity"]["segment_index"] = 1
	metrics = state["experiment_integrity"]["cumulative_metrics"]
	metrics["model_responses"] += 1
	metrics["tool_calls"] += 1
	metrics["uncached_input_tokens"] += 100
	metrics["cached_input_tokens"] += 200
	metrics["output_tokens"] += 50
	metrics["wall_seconds"] += 10
	metrics["cost_usd"] += 0.1
	next_state_path = state_path.with_name("interruption_state-01.json")
	next_checkpoint_path = checkpoint_path.with_name("interruption_checkpoint-01.json")
	write_json(next_state_path, state)
	return next_state_path, next_checkpoint_path, state


def expect_failure(result: subprocess.CompletedProcess[str], marker: str) -> None:
	if result.returncode == 0 or marker not in result.stdout:
		raise AssertionError(f"expected failure containing {marker!r}:\n{result.stdout}\n{result.stderr}")


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
	text = path.read_text(encoding="utf-8")
	missing = [marker for marker in markers if marker not in text]
	if missing:
		raise AssertionError(f"{path} misses checkpoint markers: {missing}")


def write_handoff(
	project: Path,
	state_path: Path,
	checkpoint_path: Path,
	*,
	include_checkpoint: bool,
) -> Path:
	run_dir = state_path.parent
	checkpoint_line = (
		f"- **Interruption checkpoint:** `path={checkpoint_path.name}; sha256={sha256(checkpoint_path)}`\n"
		if include_checkpoint else ""
	)
	path = run_dir / "handoff-interrupted-20260829T123000Z.md"
	path.write_text(
		f"""# Interruption handoff

- **Run ID:** `R-20260829T120000Z-quota`
- **Task packet ID:** `Q-checkpoint-smoke`
- **Date:** `2026-08-29T12:30:00Z`
- **Interrupt reason:** `RESOURCE_BOUND`
- **Task state:** `IN_PROGRESS`
- **Interruption state:** `path={state_path.name}; sha256={sha256(state_path)}`
{checkpoint_line}
## Completed work progress

O1 is preserved as a strict partial result.

## Completed obligations

- O1.

## Tools and methods tried

- direct route `[PARTIAL]`: O1 closed; O2 remains.

## Open obligations

- O2 endpoint estimate.

## Attempted routes

- route-a `[PARTIAL]`: evidence in partial_proof.md.

## Next actions

Verify the checkpoint, then continue O2.
""",
		encoding="utf-8",
		newline="\n",
	)
	return path


def main() -> None:
	require_markers(
		WORKFLOW_SKILL / "SKILL.md",
		("checkpoint_resume.py", "quota-interruption-recovery.md", "minimal_read_set"),
	)
	require_markers(
		WORKFLOW_SKILL / "references" / "quota-interruption-recovery.md",
		("RECONCILE_INFLIGHT", "cumulative metrics", "hidden-gold"),
	)
	require_markers(
		FULL_FLOW,
		("interruption_state-NN.json", "resume_receipt-NN.json", "RECONCILE_INFLIGHT"),
	)
	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0 or '"verdict": "SEALED"' not in sealed.stdout:
			raise AssertionError(f"valid seal failed:\n{sealed.stdout}\n{sealed.stderr}")
		second = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if second.returncode != 0:
			raise AssertionError(f"idempotent seal failed:\n{second.stdout}")
		verified = run("verify", "--project", str(project), "--checkpoint", str(checkpoint_path))
		if verified.returncode != 0 or '"verdict": "READY"' not in verified.stdout:
			raise AssertionError(f"valid checkpoint failed verification:\n{verified.stdout}")
		receipt_path = checkpoint_path.with_name("resume_receipt-00.json")
		resumed = run(
			"resume", "--project", str(project), "--checkpoint", str(checkpoint_path),
			"--receipt", str(receipt_path), "--resumed-at", "2026-08-29T13:00:00Z",
		)
		if resumed.returncode != 0:
			raise AssertionError(f"valid resume failed:\n{resumed.stdout}")
		receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		if receipt["experiment_integrity"]["cumulative_metrics"] != state["experiment_integrity"]["cumulative_metrics"]:
			raise AssertionError("resume receipt reset cumulative metrics")
		if receipt["experiment_integrity"]["next_segment_index"] != 1:
			raise AssertionError("resume receipt did not advance the segment index")
		if receipt["result_status"] != state["result_status"]:
			raise AssertionError("resume receipt changed the mathematical result status")
		if receipt["completed_obligation_ids"] != ["O1"] or receipt["open_obligation_ids"] != ["O2"]:
			raise AssertionError("resume receipt lost the obligation frontier")
		next_state_path, next_checkpoint_path, _ = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		next_seal = run(
			"seal", "--project", str(project), "--state", str(next_state_path),
			"--output", str(next_checkpoint_path),
		)
		if next_seal.returncode != 0:
			raise AssertionError(f"valid predecessor lineage failed:\n{next_seal.stdout}")
		next_verify = run(
			"verify", "--project", str(project), "--checkpoint", str(next_checkpoint_path)
		)
		if next_verify.returncode != 0:
			raise AssertionError(f"next checkpoint did not verify:\n{next_verify.stdout}")
		write_handoff(
			project, state_path, checkpoint_path, include_checkpoint=True
		)
		gate = run_pipeline(project)
		if gate.returncode != 0 or "quota checkpoint" not in gate.stdout:
			raise AssertionError(f"pipeline rejected a ready quota checkpoint:\n{gate.stdout}\n{gate.stderr}")
		(project / "runs" / "R-20260829T120000Z-quota" / "partial_proof.md").write_text(
			"tampered\n", encoding="utf-8", newline="\n"
		)
		expect_failure(
			run("verify", "--project", str(project), "--checkpoint", str(checkpoint_path)),
			"hash mismatch",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0:
			raise AssertionError(sealed.stdout)
		write_handoff(
			project, state_path, checkpoint_path, include_checkpoint=False
		)
		expect_failure(run_pipeline(project), "Interruption checkpoint has no path")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0:
			raise AssertionError(sealed.stdout)
		handoff = write_handoff(
			project, state_path, checkpoint_path, include_checkpoint=True
		)
		handoff.write_text(
			handoff.read_text(encoding="utf-8").replace(
				"R-20260829T120000Z-quota", "R-20260829T120000Z-other", 1
			),
			encoding="utf-8",
			newline="\n",
		)
		expect_failure(run_pipeline(project), "Run ID does not match the checkpoint")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["resume"]["stop_condition"] = "{{fill me}}"
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"template placeholders",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["resume"]["first_action"]["target_id"] = "O1"
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"does not target an open obligation",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["inflight_work"] = [
			{"worker_id": "worker-1", "session_id": "session-1", "status": "UNKNOWN", "artifact": None}
		]
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"requires RECONCILE_INFLIGHT",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["inflight_work"] = [
			{"worker_id": "worker-1", "session_id": "session-1", "status": "UNKNOWN", "artifact": None}
		]
		state["resume"]["first_action"] = {
			"kind": "RECONCILE_INFLIGHT",
			"action_id": "reconcile-worker-1",
			"target_id": "worker-1",
		}
		state["resume"]["minimal_read_set"] = state["resume"]["minimal_read_set"][:2]
		write_json(state_path, state)
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
		if receipt["unresolved_inflight_work"][0]["worker_id"] != "worker-1":
			raise AssertionError("receipt lost unresolved worker reconciliation")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["open_obligations"][0]["next_action"]["action_id"] = "route-failed"
		state["resume"]["first_action"]["action_id"] = "route-failed"
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"open obligations select do-not-repeat actions",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		transcript = state_path.parent / "full-transcript.md"
		transcript.write_text("private replay\n", encoding="utf-8", newline="\n")
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["resume"]["minimal_read_set"].append(binding(project, transcript))
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"transcript/history artifacts",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		disguised_transcript = state_path.parent / "notes.md"
		disguised_transcript.write_text("full copied conversation\n", encoding="utf-8", newline="\n")
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["resume"]["minimal_read_set"].append(binding(project, disguised_transcript))
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"outside the action-scoped read set",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		duplicate = json.loads(json.dumps(state["open_obligations"][0]))
		duplicate["id"] = "O3"
		state["open_obligations"].append(duplicate)
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"duplicate live next action",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		del state["experiment_integrity"]["prompt"]
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"experiment_integrity.prompt",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["resume"]["budget"]["limit"] = 0
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"positive integer",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		del state["experiment_integrity"]["cumulative_metrics"]["cost_usd"]
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"missing required counters",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["experiment_integrity"]["cumulative_metrics"]["wall_seconds"] = float("nan")
		write_json(state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state_path), "--output", str(checkpoint_path)),
			"non-standard JSON constant",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0:
			raise AssertionError(sealed.stdout)
		expect_failure(
			run(
				"resume", "--project", str(project), "--checkpoint", str(checkpoint_path),
				"--receipt", str(checkpoint_path.with_name("resume_receipt-00.json")),
				"--resumed-at", "2026-08-29T11:00:00Z",
			),
			"cannot precede checkpoint sealed_at",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		expect_failure(
			run(
				"resume", "--project", str(project), "--checkpoint", str(checkpoint_path),
				"--receipt", str(checkpoint_path.with_name("resume-other.json")),
				"--resumed-at", "2026-08-29T13:00:00Z",
			),
			"must be resume_receipt-00.json",
		)
		expect_failure(
			run(
				"resume", "--project", str(project), "--checkpoint", str(checkpoint_path),
				"--receipt", str(receipt_path),
				"--resumed-at", "2026-08-29T13:01:00Z",
			),
			"existing resume receipt differs",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		for key in state["experiment_integrity"]["cumulative_metrics"]:
			if key == "cost_usd":
				state["experiment_integrity"]["cumulative_metrics"][key] = 0.0
			else:
				state["experiment_integrity"]["cumulative_metrics"][key] = 0
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"cannot decrease across segments",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		state["experiment_integrity"]["arm_id"] = "B-blank"
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"arm_id must remain fixed",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		state["open_obligations"] = []
		state["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY",
			"action_id": "finalize-partial",
			"target_id": "",
		}
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"open obligations cannot disappear without completion",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["inflight_work"] = [
			{"worker_id": "worker-1", "session_id": "session-1", "status": "UNKNOWN", "artifact": None}
		]
		state["resume"]["first_action"] = {
			"kind": "RECONCILE_INFLIGHT",
			"action_id": "reconcile-worker-1",
			"target_id": "worker-1",
		}
		state["resume"]["minimal_read_set"] = state["resume"]["minimal_read_set"][:2]
		write_json(state_path, state)
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, next_value = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		next_value["inflight_work"] = []
		next_value["resume"]["first_action"] = {
			"kind": "CONTINUE_OBLIGATION",
			"action_id": "continue-o2",
			"target_id": "O2",
		}
		next_value["resume"]["minimal_read_set"].append(
			next_value["open_obligations"][0]["required_inputs"][0]
		)
		write_json(next_state_path, next_value)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"disappeared without reconciliation",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["inflight_work"] = [
			{"worker_id": "worker-1", "session_id": "session-1", "status": "UNKNOWN", "artifact": None}
		]
		state["resume"]["first_action"] = {
			"kind": "RECONCILE_INFLIGHT",
			"action_id": "reconcile-worker-1",
			"target_id": "worker-1",
		}
		state["resume"]["minimal_read_set"] = state["resume"]["minimal_read_set"][:2]
		write_json(state_path, state)
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, next_value = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		reconciliation = state_path.parent / "worker-1-reconciliation.md"
		reconciliation.write_text("worker returned no artifact\n", encoding="utf-8", newline="\n")
		next_value["inflight_work"] = []
		next_value["inflight_reconciliation"] = [
			{
				"worker_id": "worker-1",
				"session_id": "session-1",
				"outcome": "NO_RETURN",
				"evidence": binding(project, reconciliation),
			}
		]
		next_value["resume"]["first_action"] = {
			"kind": "CONTINUE_OBLIGATION",
			"action_id": "continue-o2",
			"target_id": "O2",
		}
		next_value["resume"]["minimal_read_set"].append(
			next_value["open_obligations"][0]["required_inputs"][0]
		)
		write_json(next_state_path, next_value)
		reconciled = run(
			"seal", "--project", str(project), "--state", str(next_state_path),
			"--output", str(next_checkpoint_path),
		)
		if reconciled.returncode != 0:
			raise AssertionError(f"valid worker reconciliation failed:\n{reconciled.stdout}")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["inflight_work"] = [
			{"worker_id": "worker-1", "session_id": "session-1", "status": "UNKNOWN", "artifact": None}
		]
		state["resume"]["first_action"] = {
			"kind": "RECONCILE_INFLIGHT",
			"action_id": "reconcile-worker-1",
			"target_id": "worker-1",
		}
		state["resume"]["minimal_read_set"] = state["resume"]["minimal_read_set"][:2]
		write_json(state_path, state)
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, next_value = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		next_value["inflight_work"][0]["session_id"] = "session-2"
		write_json(next_state_path, next_value)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"session changed without reconciliation",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		state["result_status"] = "CANDIDATE_COMPLETE_PROOF"
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"cannot retain open obligations",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		state = json.loads(state_path.read_text(encoding="utf-8"))
		state["checkpoint_sequence"] = 1
		state["experiment_integrity"]["segment_index"] = 1
		state["created_at"] = "2026-08-29T14:00:00Z"
		next_state_path = state_path.with_name("interruption_state-01.json")
		next_checkpoint_path = checkpoint_path.with_name("interruption_checkpoint-01.json")
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"requires predecessor bindings",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		proof_v2 = state_path.parent / "proof-v2.md"
		proof_v2.write_text("closed O2\n", encoding="utf-8", newline="\n")
		state["completed_obligations"].append({"id": "O2", "evidence": binding(project, proof_v2)})
		state["open_obligations"] = []
		state["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY",
			"action_id": "finalize-candidate",
			"target_id": "",
		}
		state["resume"]["minimal_read_set"] = [
			state["task_contract"], state["whiteboard"], binding(project, proof_v2)
		]
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"must enter do_not_repeat",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		initial_state = json.loads(state_path.read_text(encoding="utf-8"))
		old_proof = project / initial_state["completed_obligations"][0]["evidence"]["path"]
		old_audit = project / initial_state["latest_audit"]["path"]
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		renamed_proof = state_path.parent / "renamed-old-proof.md"
		renamed_audit = state_path.parent / "renamed-old-audit.md"
		renamed_proof.write_bytes(old_proof.read_bytes())
		renamed_audit.write_bytes(old_audit.read_bytes())
		proof_binding = binding(project, renamed_proof)
		audit_binding = binding(project, renamed_audit)
		state["completed_obligations"].append({"id": "O2", "evidence": proof_binding})
		state["open_obligations"] = []
		state["do_not_repeat"].append({
			"action_id": "continue-o2",
			"reason": "O2 is claimed closed.",
			"evidence": proof_binding,
		})
		state["result_status"] = "CANDIDATE_COMPLETE_PROOF"
		state["latest_audit"] = audit_binding
		state["status_transition"] = {
			"from": "RIGOROUS_PARTIAL_RESULT",
			"to": "CANDIDATE_COMPLETE_PROOF",
			"changed_at": "2026-08-29T13:30:00Z",
			"evidence": proof_binding,
			"audit": audit_binding,
		}
		state["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY", "action_id": "finalize-alias", "target_id": ""
		}
		state["resume"]["minimal_read_set"] = [
			state["task_contract"], state["whiteboard"], proof_binding, audit_binding
		]
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"must be new to the full lineage",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		combined = state_path.parent / "proof-and-audit.md"
		combined.write_text("claimed proof and audit\n", encoding="utf-8", newline="\n")
		combined_binding = binding(project, combined)
		state["completed_obligations"].append({"id": "O2", "evidence": combined_binding})
		state["open_obligations"] = []
		state["do_not_repeat"].append({
			"action_id": "continue-o2",
			"reason": "O2 is claimed closed.",
			"evidence": combined_binding,
		})
		state["result_status"] = "CANDIDATE_COMPLETE_PROOF"
		state["latest_audit"] = combined_binding
		state["status_transition"] = {
			"from": "RIGOROUS_PARTIAL_RESULT",
			"to": "CANDIDATE_COMPLETE_PROOF",
			"changed_at": "2026-08-29T13:30:00Z",
			"evidence": combined_binding,
			"audit": combined_binding,
		}
		state["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY", "action_id": "finalize-alias", "target_id": ""
		}
		state["resume"]["minimal_read_set"] = [
			state["task_contract"], state["whiteboard"], combined_binding
		]
		write_json(next_state_path, state)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(next_state_path), "--output", str(next_checkpoint_path)),
			"evidence and audit must be distinct artifacts",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		next_state_path, next_checkpoint_path, state = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		proof_v2 = state_path.parent / "proof-v2.md"
		audit_v2 = state_path.parent / "audit-v2.md"
		proof_v2.write_text("closed O2\n", encoding="utf-8", newline="\n")
		audit_v2.write_text("independent PASS\n", encoding="utf-8", newline="\n")
		state["completed_obligations"].append({"id": "O2", "evidence": binding(project, proof_v2)})
		state["open_obligations"] = []
		state["result_status"] = "CANDIDATE_COMPLETE_PROOF"
		state["latest_audit"] = binding(project, audit_v2)
		state["status_transition"] = {
			"from": "RIGOROUS_PARTIAL_RESULT",
			"to": "CANDIDATE_COMPLETE_PROOF",
			"changed_at": "2026-08-29T13:30:00Z",
			"evidence": binding(project, proof_v2),
			"audit": binding(project, audit_v2),
		}
		state["do_not_repeat"].append({
			"action_id": "continue-o2",
			"reason": "O2 is closed by the audited proof.",
			"evidence": binding(project, proof_v2),
		})
		state["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY",
			"action_id": "finalize-candidate",
			"target_id": "",
		}
		state["resume"]["minimal_read_set"] = [
			state["task_contract"], state["whiteboard"],
			binding(project, proof_v2), binding(project, audit_v2),
		]
		write_json(next_state_path, state)
		closed = run(
			"seal", "--project", str(project), "--state", str(next_state_path),
			"--output", str(next_checkpoint_path),
		)
		if closed.returncode != 0:
			raise AssertionError(f"audited status transition failed:\n{closed.stdout}")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		initial_state = json.loads(state_path.read_text(encoding="utf-8"))
		old_proof = project / initial_state["completed_obligations"][0]["evidence"]["path"]
		old_audit = project / initial_state["latest_audit"]["path"]
		receipt_path = seal_and_resume(project, state_path, checkpoint_path)
		state1_path, checkpoint1_path, state1 = next_state(
			project, state_path, checkpoint_path, receipt_path
		)
		proof1 = state_path.parent / "segment1-proof.md"
		proof1.write_text("replacement segment evidence\n", encoding="utf-8", newline="\n")
		proof1_binding = binding(project, proof1)
		state1["completed_obligations"][0]["evidence"] = proof1_binding
		state1["open_obligations"][0]["required_inputs"] = [proof1_binding]
		state1["do_not_repeat"][0]["evidence"] = proof1_binding
		state1["latest_audit"] = None
		state1["resume"]["minimal_read_set"] = [
			state1["task_contract"], state1["whiteboard"], proof1_binding
		]
		write_json(state1_path, state1)
		sealed1 = run(
			"seal", "--project", str(project), "--state", str(state1_path),
			"--output", str(checkpoint1_path),
		)
		if sealed1.returncode != 0:
			raise AssertionError(f"segment 1 seal failed:\n{sealed1.stdout}")
		receipt1_path = checkpoint1_path.with_name("resume_receipt-01.json")
		resumed1 = run(
			"resume", "--project", str(project), "--checkpoint", str(checkpoint1_path),
			"--receipt", str(receipt1_path), "--resumed-at", "2026-08-29T15:00:00Z",
		)
		if resumed1.returncode != 0:
			raise AssertionError(f"segment 1 resume failed:\n{resumed1.stdout}")
		state2 = json.loads(state1_path.read_text(encoding="utf-8"))
		state2["checkpoint_sequence"] = 2
		state2["predecessor"] = {
			"checkpoint": binding(project, checkpoint1_path),
			"resume_receipt": binding(project, receipt1_path),
		}
		state2["created_at"] = "2026-08-29T16:00:00Z"
		state2["experiment_integrity"]["segment_index"] = 2
		state2["experiment_integrity"]["cumulative_metrics"]["wall_seconds"] += 10
		state2["completed_obligations"].append({"id": "O2", "evidence": binding(project, old_proof)})
		state2["open_obligations"] = []
		state2["do_not_repeat"].append({
			"action_id": "continue-o2",
			"reason": "O2 is claimed closed.",
			"evidence": binding(project, old_proof),
		})
		state2["result_status"] = "CANDIDATE_COMPLETE_PROOF"
		state2["latest_audit"] = binding(project, old_audit)
		state2["status_transition"] = {
			"from": "RIGOROUS_PARTIAL_RESULT",
			"to": "CANDIDATE_COMPLETE_PROOF",
			"changed_at": "2026-08-29T15:30:00Z",
			"evidence": binding(project, old_proof),
			"audit": binding(project, old_audit),
		}
		state2["resume"]["first_action"] = {
			"kind": "FINALIZE_BOUNDARY",
			"action_id": "finalize-replayed-proof",
			"target_id": "",
		}
		state2["resume"]["minimal_read_set"] = [
			state2["task_contract"], state2["whiteboard"],
			binding(project, old_proof), binding(project, old_audit),
		]
		state2_path = state1_path.with_name("interruption_state-02.json")
		checkpoint2_path = checkpoint1_path.with_name("interruption_checkpoint-02.json")
		write_json(state2_path, state2)
		expect_failure(
			run("seal", "--project", str(project), "--state", str(state2_path), "--output", str(checkpoint2_path)),
			"must be new to the full lineage",
		)

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0:
			raise AssertionError(sealed.stdout)
		notes = state_path.parent / "notes.md"
		notes.write_text("unverified replacement state input\n", encoding="utf-8", newline="\n")
		module = load_checkpoint_module()
		original_verify = module._verify_checkpoint_snapshot

		def mutate_after_verify(project_arg, checkpoint_arg):
			snapshot = original_verify(project_arg, checkpoint_arg)
			mutated = json.loads(state_path.read_text(encoding="utf-8"))
			mutated["completed_obligations"].append({
				"id": "O999", "evidence": binding(project, notes)
			})
			mutated["resume"]["first_action"] = {
				"kind": "AWAIT_INPUT", "action_id": "unbound-action", "target_id": ""
			}
			mutated["resume"]["minimal_read_set"].append(binding(project, notes))
			write_json(state_path, mutated)
			return snapshot

		module._verify_checkpoint_snapshot = mutate_after_verify
		receipt = module.write_resume_receipt(
			project,
			checkpoint_path,
			checkpoint_path.with_name("resume_receipt-00.json"),
			"2026-08-29T13:00:00Z",
		)
		if "O999" in receipt["completed_obligation_ids"]:
			raise AssertionError("resume receipt consumed state changed after verification")
		if receipt["first_action"]["action_id"] != "continue-o2":
			raise AssertionError("resume receipt did not use the verified first action")
		if any(item["path"].endswith("notes.md") for item in receipt["minimal_read_set"]):
			raise AssertionError("resume receipt consumed an unverified read-set entry")
		try:
			original_verify(project, checkpoint_path)
		except module.CheckpointError:
			pass
		else:
			raise AssertionError("mutated checkpoint state should verify STALE")

	with tempfile.TemporaryDirectory() as temp:
		project, state_path, checkpoint_path = fixture(Path(temp))
		sealed = run(
			"seal", "--project", str(project), "--state", str(state_path),
			"--output", str(checkpoint_path),
		)
		if sealed.returncode != 0:
			raise AssertionError(sealed.stdout)
		checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
		checkpoint["reason"] = "OTHER"
		write_json(checkpoint_path, checkpoint)
		expect_failure(
			run("verify", "--project", str(project), "--checkpoint", str(checkpoint_path)),
			"envelope does not match",
		)

	print("checkpoint resume smoke passed")


if __name__ == "__main__":
	main()
