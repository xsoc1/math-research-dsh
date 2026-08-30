#!/usr/bin/env python3
"""Plugin-owned gateway for Blueprint v2.2 project operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_API = "blueprint-runtime/v1"
RUNTIME_VERSION = "manage-math-research-program/1.7.0"
RESPONSE_SCHEMA = "blueprint-runtime-response/v1"
LAYOUT_SCHEMA = "blueprint-project-layout/v1"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT_CANDIDATES = (
	PLUGIN_ROOT
	/ "skills"
	/ "manage-math-research-program"
	/ "assets"
	/ "blueprint-accepted-knowledge"
	/ "tools",
	PLUGIN_ROOT / "assets" / "blueprint-accepted-knowledge" / "tools",
)
TOOLS_ROOT = next(
	(Candidate for Candidate in TOOLS_ROOT_CANDIDATES if Candidate.is_dir()),
	TOOLS_ROOT_CANDIDATES[0],
)
REQUIRED_TOOLS = {
	"query": "blueprint_query.py",
	"receiver": "receive_blueprint.py",
	"validator": "validate_blueprint.py",
}


class GatewayError(RuntimeError):
	def __init__(
		self,
		code: str,
		message: str,
		*,
		details: dict[str, Any] | None = None,
		exit_code: int = 2,
	) -> None:
		super().__init__(message)
		self.code = code
		self.message = message
		self.details = details or {}
		self.exit_code = exit_code


def sha256_file(path: Path) -> str:
	return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_sha256() -> str:
	digest = hashlib.sha256()
	files = [Path(__file__).resolve(), *sorted(TOOLS_ROOT.glob("*.py"))]
	for path in files:
		relative_name = path.name if path.parent == TOOLS_ROOT else f"runtime/{path.name}"
		digest.update(relative_name.encode("utf-8"))
		digest.update(b"\0")
		digest.update(path.read_bytes())
		digest.update(b"\0")
	return "sha256:" + digest.hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
	try:
		value = json.loads(path.read_text(encoding="utf-8-sig"))
	except OSError as exc:
		raise GatewayError(
			"READ_FAILED",
			f"Could not read {label}: {path}",
			details={"path": str(path), "error": str(exc)},
		) from exc
	except json.JSONDecodeError as exc:
		raise GatewayError(
			"INVALID_JSON",
			f"Invalid JSON in {label}: {path}",
			details={"path": str(path), "error": str(exc)},
		) from exc
	if not isinstance(value, dict):
		raise GatewayError(
			"INVALID_JSON",
			f"Expected a JSON object in {label}: {path}",
			details={"path": str(path)},
		)
	return value


def emit(value: dict[str, Any], *, stream: Any = sys.stdout) -> None:
	print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), file=stream)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
	fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
	temporary = Path(temporary_name)
	try:
		with os.fdopen(fd, "wb") as handle:
			handle.write(payload)
			handle.flush()
			os.fsync(handle.fileno())
		os.replace(temporary, path)
	finally:
		if temporary.exists():
			temporary.unlink()


def resolve_project(requested: Path) -> Path:
	project = requested.expanduser().resolve()
	if not project.is_dir():
		raise GatewayError(
			"PROJECT_NOT_FOUND",
			f"Project root is not a directory: {project}",
			details={"project": str(project)},
		)
	marker = project / "blueprint-project.json"
	if not marker.is_file():
		raise GatewayError(
			"LAYOUT_MARKER_NOT_FOUND",
			f"Missing blueprint-project.json at project root: {project}",
			details={"project": str(project)},
		)
	return project


def resolve_project_path(project: Path, raw: Any, label: str) -> Path:
	if not isinstance(raw, str) or not raw.strip():
		raise GatewayError(
			"INVALID_LAYOUT_PATH",
			f"{label} must be a non-empty relative path.",
			details={"label": label, "value": raw},
		)
	candidate = Path(raw)
	if candidate.is_absolute():
		raise GatewayError(
			"ABSOLUTE_LAYOUT_PATH",
			f"{label} must be relative to the project root.",
			details={"label": label, "value": raw},
		)
	resolved = (project / candidate).resolve()
	if not resolved.is_relative_to(project):
		raise GatewayError(
			"LAYOUT_PATH_ESCAPE",
			f"{label} escapes the project root.",
			details={"label": label, "value": raw, "resolved": str(resolved)},
		)
	return resolved


def resolve_blueprint_path(
	project: Path,
	blueprint_root: Path,
	raw: Any,
	label: str,
	*,
	require_within_blueprint: bool,
) -> Path:
	if not isinstance(raw, str) or not raw.strip():
		raise GatewayError(
			"INVALID_CONFIG_PATH",
			f"{label} must be a non-empty path.",
			details={"label": label, "value": raw},
		)
	candidate = Path(raw).expanduser()
	resolved = candidate.resolve() if candidate.is_absolute() else (blueprint_root / candidate).resolve()
	if not resolved.is_relative_to(project):
		raise GatewayError(
			"CONFIG_PATH_ESCAPE",
			f"{label} escapes the project root.",
			details={"label": label, "value": raw, "resolved": str(resolved)},
		)
	if require_within_blueprint and not resolved.is_relative_to(blueprint_root):
		raise GatewayError(
			"BLUEPRINT_PATH_ESCAPE",
			f"{label} must remain under the Blueprint root.",
			details={"label": label, "value": raw, "resolved": str(resolved)},
		)
	return resolved


def require_file(path: Path, label: str) -> None:
	if not path.is_file():
		raise GatewayError(
			"REQUIRED_FILE_MISSING",
			f"Missing {label}: {path}",
			details={"label": label, "path": str(path)},
		)


def relative(project: Path, path: Path) -> str:
	return path.relative_to(project).as_posix()


def inspect_layout(project: Path, *, create_runtime_paths: bool) -> dict[str, Any]:
	marker_path = project / "blueprint-project.json"
	marker = load_json(marker_path, "Blueprint project layout marker")
	if marker.get("schema_version") != LAYOUT_SCHEMA:
		raise GatewayError(
			"UNSUPPORTED_LAYOUT_SCHEMA",
			f"Expected {LAYOUT_SCHEMA}.",
			details={"actual": marker.get("schema_version")},
		)
	if marker.get("blueprint_schema") != "2.2":
		raise GatewayError(
			"UNSUPPORTED_BLUEPRINT_SCHEMA",
			"The active gateway supports Blueprint schema 2.2 only.",
			details={"actual": marker.get("blueprint_schema")},
		)
	if marker.get("runtime_api") != RUNTIME_API:
		raise GatewayError(
			"UNSUPPORTED_RUNTIME_API",
			f"Expected runtime API {RUNTIME_API}.",
			details={"actual": marker.get("runtime_api")},
		)
	project_id = marker.get("project_id")
	if not isinstance(project_id, str) or not project_id.strip():
		raise GatewayError("INVALID_LAYOUT", "blueprint-project.json project_id must be non-empty.")
	paths = marker.get("paths")
	if not isinstance(paths, dict):
		raise GatewayError("INVALID_LAYOUT", "blueprint-project.json paths must be an object.")
	resolved_paths = {
		name: resolve_project_path(project, paths.get(name), f"paths.{name}")
		for name in ("blueprint_root", "research_root", "artifact_root", "work_root")
	}
	blueprint_root = resolved_paths["blueprint_root"]
	research_root = resolved_paths["research_root"]
	artifact_root = resolved_paths["artifact_root"]
	work_root = resolved_paths["work_root"]
	if not work_root.is_relative_to(research_root):
		raise GatewayError("INVALID_LAYOUT", "paths.work_root must remain under paths.research_root.")
	if not artifact_root.is_relative_to(research_root):
		raise GatewayError("INVALID_LAYOUT", "paths.artifact_root must remain under paths.research_root.")
	config_path = blueprint_root / ".blueprint" / "config.json"
	require_file(config_path, "Blueprint configuration")
	config = load_json(config_path, "Blueprint configuration")
	if str(config.get("schema_version")) != str(marker.get("blueprint_schema")):
		raise GatewayError(
			"SCHEMA_MISMATCH",
			"Blueprint configuration schema does not match blueprint-project.json.",
			details={
				"layout": marker.get("blueprint_schema"),
				"config": config.get("schema_version"),
			},
		)
	canonical = resolve_blueprint_path(
		project,
		blueprint_root,
		config.get("canonical_blueprint", "blueprint.json"),
		"canonical_blueprint",
		require_within_blueprint=True,
	)
	inventory = resolve_blueprint_path(
		project,
		blueprint_root,
		config.get("evidence_inventory", "evidence_inventory.csv"),
		"evidence_inventory",
		require_within_blueprint=True,
	)
	submissions = resolve_blueprint_path(
		project,
		blueprint_root,
		config.get("submissions_dir", "submissions"),
		"submissions_dir",
		require_within_blueprint=True,
	)
	request_log = resolve_blueprint_path(
		project,
		blueprint_root,
		config.get("request_log", ".blueprint/audit/events.jsonl"),
		"request_log",
		require_within_blueprint=True,
	)
	configured_artifact_root = artifact_root
	if "artifact_root" in config:
		configured_artifact_root = resolve_blueprint_path(
			project,
			blueprint_root,
			config["artifact_root"],
			"artifact_root",
			require_within_blueprint=False,
		)
	if configured_artifact_root != artifact_root:
		raise GatewayError(
			"ARTIFACT_ROOT_MISMATCH",
			"Blueprint configuration artifact_root does not match blueprint-project.json.",
			details={
				"layout": str(artifact_root),
				"config": str(configured_artifact_root),
			},
		)
	require_file(canonical, "canonical Blueprint graph")
	require_file(inventory, "canonical evidence inventory")
	operational_paths = [
		blueprint_root,
		research_root,
		artifact_root,
		work_root,
		submissions,
		request_log.parent,
	]
	for label, default in (
		("merge_lock", "../research/work/runtime/locks/merge.lock"),
		("transactions_dir", "../research/work/runtime/transactions"),
		("validation_work_dir", "../research/work/runtime/validation"),
	):
		configured = config.get(label)
		if configured is None:
			continue
		resolved = resolve_blueprint_path(
			project,
			blueprint_root,
			configured or default,
			label,
			require_within_blueprint=False,
		)
		operational_paths.append(resolved.parent if label == "merge_lock" else resolved)
	for policy_name, key in (
		("review_optimization", "work_dir"),
		("cleanup_policy", "cleanup_receipts_dir"),
	):
		policy = config.get(policy_name, {})
		if isinstance(policy, dict) and policy.get(key):
			operational_paths.append(
				resolve_blueprint_path(
					project,
					blueprint_root,
					policy[key],
					f"{policy_name}.{key}",
					require_within_blueprint=False,
				)
			)
	changes: list[str] = []
	if create_runtime_paths:
		for path in operational_paths:
			if not path.exists():
				path.mkdir(parents=True, exist_ok=True)
				changes.append(f"created-directory:{relative(project, path)}")
		if not request_log.exists():
			request_log.touch(exist_ok=False)
			changes.append(f"created-file:{relative(project, request_log)}")
	for key, filename in REQUIRED_TOOLS.items():
		require_file(TOOLS_ROOT / filename, f"plugin-owned Blueprint {key} tool")
	return {
		"project": project,
		"marker_path": marker_path,
		"marker": marker,
		"config_path": config_path,
		"config": config,
		"blueprint_root": blueprint_root,
		"research_root": research_root,
		"artifact_root": artifact_root,
		"work_root": work_root,
		"canonical": canonical,
		"inventory": inventory,
		"submissions": submissions,
		"request_log": request_log,
		"changes": changes,
	}


def runtime_fingerprint(layout: dict[str, Any]) -> dict[str, str]:
	return {
		"runtime_api": RUNTIME_API,
		"runtime_version": RUNTIME_VERSION,
		"runtime_sha256": runtime_sha256(),
		"project_id": layout["marker"]["project_id"],
		"project_root": str(layout["project"]),
		"layout_sha256": sha256_file(layout["marker_path"]),
		"config_sha256": sha256_file(layout["config_path"]),
	}


def state_path(layout: dict[str, Any]) -> Path:
	return layout["work_root"] / "runtime" / "blueprint-gateway.json"


def ensure(project: Path) -> int:
	layout = inspect_layout(project, create_runtime_paths=True)
	require_file(layout["request_log"], "Blueprint audit event log")
	fingerprint = runtime_fingerprint(layout)
	path = state_path(layout)
	status = "READY"
	if path.is_file():
		existing = load_json(path, "Blueprint gateway state")
		if all(existing.get(key) == value for key, value in fingerprint.items()):
			status = "ALREADY_READY"
		else:
			status = "REFRESHED"
	if status != "ALREADY_READY":
		state = {
			"schema_version": "blueprint-runtime-state/v1",
			**fingerprint,
			"project_id": layout["marker"].get("project_id"),
			"project_root": str(project),
			"ensured_at": datetime.now(timezone.utc).isoformat(),
		}
		atomic_write_json(path, state)
		layout["changes"].append(f"wrote-state:{relative(project, path)}")
	emit(
		{
			"schema_version": RESPONSE_SCHEMA,
			"ok": True,
			"operation": "ensure",
			"status": status,
			"runtime_api": RUNTIME_API,
			"runtime_version": RUNTIME_VERSION,
			"project_id": layout["marker"].get("project_id"),
			"project_root": str(project),
			"paths": {
				name: relative(project, layout[name])
				for name in (
					"blueprint_root",
					"research_root",
					"artifact_root",
					"work_root",
					"canonical",
					"inventory",
					"submissions",
					"request_log",
				)
			},
			"snapshot": {
				"blueprint_sha256": sha256_file(layout["canonical"]),
				"inventory_sha256": sha256_file(layout["inventory"]),
			},
			"changes": layout["changes"],
		}
	)
	return 0


def require_ensured(project: Path) -> dict[str, Any]:
	layout = inspect_layout(project, create_runtime_paths=False)
	path = state_path(layout)
	if not path.is_file():
		raise GatewayError(
			"ENSURE_REQUIRED",
			"Run blueprintctl.py ensure once with the active plugin before other operations.",
			details={"state_path": str(path)},
		)
	require_file(layout["request_log"], "Blueprint audit event log")
	state = load_json(path, "Blueprint gateway state")
	fingerprint = runtime_fingerprint(layout)
	mismatches = {
		key: {"expected": value, "actual": state.get(key)}
		for key, value in fingerprint.items()
		if state.get(key) != value
	}
	if mismatches:
		raise GatewayError(
			"REENSURE_REQUIRED",
			"The plugin runtime or Blueprint layout changed. Run ensure once again.",
			details={"mismatches": mismatches},
		)
	return layout


def run_tool(tool: str, arguments: list[str], *, cwd: Path) -> int:
	command = [sys.executable, str(TOOLS_ROOT / REQUIRED_TOOLS[tool]), *arguments]
	completed = subprocess.run(command, cwd=cwd, text=True)
	return completed.returncode


def validate(project: Path) -> int:
	layout = require_ensured(project)
	return run_tool(
		"validator",
		[
			"--blueprint",
			str(layout["canonical"]),
			"--inventory",
			str(layout["inventory"]),
			"--artifact-root",
			str(layout["artifact_root"]),
		],
		cwd=layout["blueprint_root"],
	)


def query(project: Path, arguments: list[str]) -> int:
	if not arguments:
		raise GatewayError("QUERY_REQUIRED", "A Blueprint query operation is required.")
	layout = require_ensured(project)
	return run_tool(
		"query",
		["--statistics-root", str(layout["blueprint_root"]), *arguments],
		cwd=layout["blueprint_root"],
	)


def resolve_submission(layout: dict[str, Any], supplied: Path) -> Path:
	if supplied.is_absolute():
		resolved = supplied.resolve()
	else:
		project_candidate = (layout["project"] / supplied).resolve()
		blueprint_candidate = (layout["blueprint_root"] / supplied).resolve()
		resolved = project_candidate if project_candidate.is_relative_to(layout["submissions"]) else blueprint_candidate
	if not resolved.is_relative_to(layout["submissions"]) or resolved.parent != layout["submissions"]:
		raise GatewayError(
			"INVALID_SUBMISSION_PATH",
			"A submission must be one direct child of the configured submissions directory.",
			details={"submission": str(resolved)},
		)
	return resolved


def receive(
	project: Path,
	submission: Path,
	*,
	validate_only: bool,
	agent_id: str,
) -> int:
	layout = require_ensured(project)
	resolved = resolve_submission(layout, submission)
	arguments = [
		"--blueprint-root",
		str(layout["blueprint_root"]),
		"--submission",
		str(resolved),
	]
	if validate_only:
		arguments.extend(["--validate-only", "--actor-agent-id", agent_id])
	else:
		arguments.extend(["--integrator-agent-id", agent_id])
	return run_tool("receiver", arguments, cwd=layout["blueprint_root"])


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description=__doc__)
	subparsers = parser.add_subparsers(dest="operation", required=True)
	subparsers.add_parser("version", help="Print the active Blueprint runtime version.")
	for operation, help_text in (
		("ensure", "Validate and bind the active runtime to a Blueprint v2.2 layout."),
		("validate", "Validate the canonical graph and evidence inventory."),
	):
		child = subparsers.add_parser(operation, help=help_text)
		child.add_argument("--project", type=Path, default=Path.cwd())
	query_parser = subparsers.add_parser("query", help="Run a canonical Blueprint query.")
	query_parser.add_argument("--project", type=Path, default=Path.cwd())
	query_parser.add_argument("query_arguments", nargs=argparse.REMAINDER)
	validate_parser = subparsers.add_parser(
		"validate-submission",
		help="Deterministically validate one immutable proposal.",
	)
	validate_parser.add_argument("--project", type=Path, default=Path.cwd())
	validate_parser.add_argument("--submission", type=Path, required=True)
	validate_parser.add_argument("--actor-agent-id", default="blueprint-validator")
	integrate_parser = subparsers.add_parser(
		"integrate",
		help="Deterministically integrate one independently approved proposal.",
	)
	integrate_parser.add_argument("--project", type=Path, default=Path.cwd())
	integrate_parser.add_argument("--submission", type=Path, required=True)
	integrate_parser.add_argument("--integrator-agent-id", default="blueprint-integrator")
	return parser


def main() -> int:
	args = build_parser().parse_args()
	if args.operation == "version":
		emit(
			{
				"schema_version": RESPONSE_SCHEMA,
				"ok": True,
				"operation": "version",
				"runtime_api": RUNTIME_API,
				"runtime_version": RUNTIME_VERSION,
				"tools_root": str(TOOLS_ROOT),
			}
		)
		return 0
	project = resolve_project(args.project)
	if args.operation == "ensure":
		return ensure(project)
	if args.operation == "validate":
		return validate(project)
	if args.operation == "query":
		return query(project, args.query_arguments)
	if args.operation == "validate-submission":
		return receive(
			project,
			args.submission,
			validate_only=True,
			agent_id=args.actor_agent_id,
		)
	if args.operation == "integrate":
		return receive(
			project,
			args.submission,
			validate_only=False,
			agent_id=args.integrator_agent_id,
		)
	raise GatewayError("UNKNOWN_OPERATION", f"Unsupported operation: {args.operation}")


if __name__ == "__main__":
	try:
		raise SystemExit(main())
	except GatewayError as exc:
		emit(
			{
				"schema_version": RESPONSE_SCHEMA,
				"ok": False,
				"error": {
					"code": exc.code,
					"message": exc.message,
					"details": exc.details,
				},
			},
			stream=sys.stderr,
		)
		raise SystemExit(exc.exit_code)
