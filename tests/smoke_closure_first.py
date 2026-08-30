#!/usr/bin/env python3
import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RIGOROUS = ROOT / "skills" / "rigorous-open-math-research"
WORKFLOW = ROOT / "skills" / "math-research-workflow"
FULL_FLOW = ROOT / "docs" / "pipeline-full-flow.md"
PIPELINE_VALIDATOR = WORKFLOW / "scripts" / "validate_pipeline.py"
FAST_CLOSE_GOOD = ROOT / "tests" / "fixtures" / "pipeline-fast-close-good"
FAST_CLOSE_BAD = ROOT / "tests" / "fixtures" / "pipeline-fast-close-bad"


def require(path: Path, markers: tuple[str, ...]) -> None:
	text = path.read_text(encoding="utf-8")
	missing = [marker for marker in markers if marker not in text]
	if missing:
		raise AssertionError(f"{path.relative_to(ROOT)} missing markers: {missing}")


def validate_fixture(path: Path) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(PIPELINE_VALIDATOR), "--project", str(path)],
		capture_output=True,
		text=True,
	)


def file_hash(path: Path) -> str:
	return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write_json(path: Path, data: dict[str, object]) -> None:
	path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def set_gate_field(path: Path, key: str, value: str) -> None:
	prefix = f"- {key}:"
	lines = path.read_text(encoding="utf-8").splitlines()
	updated = [f"{prefix} {value}" if line.startswith(prefix) else line for line in lines]
	path.write_text("\n".join(updated) + "\n", encoding="utf-8", newline="\n")


def refresh_certificate(run_dir: Path) -> tuple[str, str]:
	manifest_path = run_dir / "completion_manifest.json"
	audit_path = run_dir / "completion_audit.json"
	gate_path = run_dir / "closure_gate.md"
	manifest_hash = file_hash(manifest_path)
	audit = json.loads(audit_path.read_text(encoding="utf-8"))
	audit["audited_manifest_sha256"] = manifest_hash
	write_json(audit_path, audit)
	audit_hash = file_hash(audit_path)
	set_gate_field(
		gate_path,
		"Completion manifest",
		f"path=completion_manifest.json; sha256={manifest_hash}",
	)
	set_gate_field(
		gate_path,
		"Fresh package audit",
		f"path=completion_audit.json; sha256={audit_hash}",
	)
	return manifest_hash, audit_hash


def require_failure(target: Path, marker: str) -> None:
	result = validate_fixture(target)
	if result.returncode == 0 or marker not in result.stdout:
		raise AssertionError(f"fixture missed {marker!r}:\n{result.stdout}\n{result.stderr}")


def copy_good(temp_root: Path) -> tuple[Path, Path]:
	project = temp_root / "project"
	shutil.copytree(FAST_CLOSE_GOOD, project)
	run_dir = project / "runs" / "R-20260829T000000Z-fast-close"
	return project, run_dir


def main() -> None:
	rigorous_skill = RIGOROUS
	workflow_skill = WORKFLOW
	require(
		rigorous_skill / "references" / "closure-first-protocol.md",
		(
			"OPEN_EXACT_GAP",
			"decision_delta",
			"Difficulty alone is not a spawn",
			"Completion certificate and fast close",
		),
	)
	require(
		rigorous_skill / "assets" / "closure-gate.template.md",
		(
			"First open load-bearing claim",
			"Coordinator direct attempt",
			"Completion manifest",
			"Fast-close decision",
		),
	)
	require(
		rigorous_skill / "SKILL.md",
		("references/closure-first-protocol.md", "closure_gate.md"),
	)
	require(
		rigorous_skill / "assets" / "subtask-packet.template.md",
		("Decision to change", "decision_delta"),
	)
	require(
		workflow_skill / "SKILL.md",
		("Closure-first gate", "no-`decision_delta` returns", "Fast-close exit"),
	)
	require(
		FULL_FLOW,
		("completion_manifest.json", "Fast-close STOP", "frontier_upgrade.json"),
	)
	package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
	if package["version"] != "1.11.0":
		raise AssertionError("DSH package version is not 1.11.0")

	good = validate_fixture(FAST_CLOSE_GOOD)
	if good.returncode != 0:
		raise AssertionError(f"valid fast-close certificate failed:\n{good.stdout}\n{good.stderr}")
	bad = validate_fixture(FAST_CLOSE_BAD)
	if bad.returncode == 0:
		raise AssertionError("invalid fast-close certificate unexpectedly passed")
	if "completion audit verdict must be PASS" not in bad.stdout:
		raise AssertionError(f"invalid certificate missed the audit-content check:\n{bad.stdout}")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		(run_dir / "problem_contract.md").unlink()
		require_failure(project, "completion manifest contract artifact is missing")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		manifest_path = run_dir / "completion_manifest.json"
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["root_obligations"][0]["status"] = "OPEN"
		write_json(manifest_path, manifest)
		refresh_certificate(run_dir)
		require_failure(project, "root obligation 'O1' is not CLOSED")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		graph_path = run_dir / "obligation_graph.json"
		graph = json.loads(graph_path.read_text(encoding="utf-8"))
		graph["root_obligations"].append(
			{"id": "O2", "status": "OPEN", "proof_anchor": ""}
		)
		write_json(graph_path, graph)
		manifest_path = run_dir / "completion_manifest.json"
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["obligation_graph"]["sha256"] = file_hash(graph_path)
		write_json(manifest_path, manifest)
		refresh_certificate(run_dir)
		require_failure(project, "do not exactly match the canonical obligation graph")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		graph_path = run_dir / "obligation_graph.json"
		graph = json.loads(graph_path.read_text(encoding="utf-8"))
		graph["root_obligations"][0]["proof_anchor"] = "candidate_proof.md#missing"
		write_json(graph_path, graph)
		manifest_path = run_dir / "completion_manifest.json"
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["root_obligations"][0]["proof_anchor"] = "candidate_proof.md#missing"
		manifest["obligation_graph"]["sha256"] = file_hash(graph_path)
		write_json(manifest_path, manifest)
		refresh_certificate(run_dir)
		require_failure(project, "does not exist in the candidate proof")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		manifest_path = run_dir / "completion_manifest.json"
		manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
		manifest["contract"]["path"] = "../../../outside.md"
		write_json(manifest_path, manifest)
		refresh_certificate(run_dir)
		require_failure(project, "path escapes the project root")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		candidate_hash = file_hash(run_dir / "candidate_proof.md")
		set_gate_field(
			run_dir / "closure_gate.md",
			"Fresh package audit",
			f"path=candidate_proof.md; sha256={candidate_hash}",
		)
		require_failure(project, "completion audit must be distinct")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		audit_path = run_dir / "completion_audit.json"
		audit = json.loads(audit_path.read_text(encoding="utf-8"))
		audit["reviewer_id"] = "solver-fixture"
		write_json(audit_path, audit)
		set_gate_field(
			run_dir / "closure_gate.md",
			"Fresh package audit",
			f"path=completion_audit.json; sha256={file_hash(audit_path)}",
		)
		require_failure(project, "reviewer must differ from the candidate author")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		manifest_hash, audit_hash = refresh_certificate(run_dir)
		authorization_path = run_dir / "frontier_authorization.md"
		authorization_path.write_text(
			"# User request\n\nAuthorize frontier F1.\n",
			encoding="utf-8",
			newline="\n",
		)
		upgrade_path = run_dir / "frontier_upgrade.json"
		upgrade = {
			"schema_version": 1,
			"sequence": 1,
			"base_completion_manifest_sha256": manifest_hash,
			"base_audit_sha256": audit_hash,
			"authorization": {
				"type": "user_request",
				"path": "frontier_authorization.md",
				"sha256": file_hash(authorization_path),
				"locator": "user-request",
			},
			"obligation_id": "F1",
			"budget": {"unit": "model_responses", "limit": 1},
			"stop_condition": "Stop after one model response.",
		}
		write_json(upgrade_path, upgrade)
		set_gate_field(
			run_dir / "closure_gate.md",
			"Frontier upgrade",
			f"path=frontier_upgrade.json; sha256={file_hash(upgrade_path)}",
		)
		frontier_good = validate_fixture(project)
		if frontier_good.returncode != 0:
			raise AssertionError(f"valid frontier upgrade failed:\n{frontier_good.stdout}")
		upgrade["authorization"]["locator"] = "missing-authorization-section"
		write_json(upgrade_path, upgrade)
		set_gate_field(
			run_dir / "closure_gate.md",
			"Frontier upgrade",
			f"path=frontier_upgrade.json; sha256={file_hash(upgrade_path)}",
		)
		require_failure(project, "does not exist in the bound record")
		upgrade["authorization"]["locator"] = "user-request"
		upgrade["budget"]["limit"] = 0
		write_json(upgrade_path, upgrade)
		set_gate_field(
			run_dir / "closure_gate.md",
			"Frontier upgrade",
			f"path=frontier_upgrade.json; sha256={file_hash(upgrade_path)}",
		)
		require_failure(project, "budget limit must be a positive integer")

	with tempfile.TemporaryDirectory() as temp:
		project = Path(temp) / "project"
		post = project / "runs" / "R-20260829T010000Z-missing-gate"
		post.mkdir(parents=True)
		(post / "final_report.md").write_text("# Final report\n", encoding="utf-8")
		require_failure(project, "has no closure_gate.md")

	with tempfile.TemporaryDirectory() as temp:
		project = Path(temp) / "project"
		pre = project / "runs" / "R-20260828T230000Z-legacy"
		pre.mkdir(parents=True)
		(pre / "final_report.md").write_text("# Final report\n", encoding="utf-8")
		legacy = validate_fixture(project)
		if legacy.returncode != 0:
			raise AssertionError(f"pre-cutover run failed compatibility:\n{legacy.stdout}")

	with tempfile.TemporaryDirectory() as temp:
		project, run_dir = copy_good(Path(temp))
		duplicate = project / "runs" / "archived-duplicate-audit"
		duplicate.mkdir(parents=True)
		shutil.copy2(run_dir / "completion_audit.json", duplicate / "audit-second.json")
		require_failure(project, "has more than one completion audit")
	print("closure-first smoke passed")


if __name__ == "__main__":
	main()
