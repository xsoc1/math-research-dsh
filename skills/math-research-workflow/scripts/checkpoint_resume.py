#!/usr/bin/env python3
"""Seal and verify low-overhead interruption checkpoints.

The state file is semantic: it names completed and open obligations, in-flight
work, actions that must not be repeated, experiment bindings, cumulative
metrics, and the first resume action. The checkpoint is an immutable,
hash-bound envelope over that state and its referenced artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
REASONS = {"QUOTA_BOUNDARY", "USER_INTERRUPT", "INFRA_FAILURE", "OTHER"}
INFLIGHT_STATES = {"RUNNING", "UNKNOWN", "INTERRUPTED", "COMPLETED_UNINGESTED"}
UNRESOLVED_INFLIGHT = {"RUNNING", "UNKNOWN", "COMPLETED_UNINGESTED"}
RECONCILIATION_OUTCOMES = {"INGESTED", "INTERRUPTED", "NO_RETURN"}
FIRST_ACTIONS = {
    "RECONCILE_INFLIGHT",
    "CONTINUE_OBLIGATION",
    "FINALIZE_BOUNDARY",
    "AWAIT_INPUT",
}
BUDGET_UNITS = {"model_responses", "tool_calls", "wall_minutes", "tokens"}
CHECKPOINT_OVERHEAD_POLICIES = {"separate_unscored", "included_in_scored_metrics"}
RESULT_STATUSES = {
    "FORMALLY_VERIFIED_PROOF",
    "INDEPENDENTLY_AUDITED_PROOF",
    "CANDIDATE_COMPLETE_PROOF",
    "RIGOROUS_PARTIAL_RESULT",
    "VERIFIED_GENERAL_CONSTRUCTION",
    "FINITE_COMPUTATIONAL_RESULT",
    "NUMERICAL_EVIDENCE",
    "COUNTEREXAMPLE_CANDIDATE",
    "BLOCKED_REDUCTION",
    "NO_MATERIAL_PROGRESS",
    "PAUSED_BUDGET",
    "INTERRUPTED",
    "BLOCKED",
}
REQUIRED_METRICS = {
    "model_responses",
    "tool_calls",
    "uncached_input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "wall_seconds",
    "cost_usd",
}
COMPLETE_RESULT_STATUSES = {
    "FORMALLY_VERIFIED_PROOF",
    "INDEPENDENTLY_AUDITED_PROOF",
    "CANDIDATE_COMPLETE_PROOF",
}
FORBIDDEN_READ_SET_TOKENS = {
    "transcript",
    "conversation",
    "chat_history",
    "chat-history",
    "planner_history",
    "session_log",
    "session-log",
    "raw_response",
    "raw-response",
}
MAX_MINIMAL_READ_SET = 12


class CheckpointError(RuntimeError):
    """Raised when an interruption state or checkpoint is unsafe to resume."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reject_nonstandard_json(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r}")


def load_json(path: Path, context: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_nonstandard_json,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CheckpointError(f"{context} is not readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CheckpointError(f"{context} must be a JSON object")
    return value


def inside_project(project: Path, path: Path, context: str, *, must_exist: bool) -> Path:
    project = project.resolve()
    candidate = path if path.is_absolute() else project / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(project)
    except ValueError as exc:
        raise CheckpointError(f"{context} escapes the project root") from exc
    if must_exist and not candidate.is_file():
        raise CheckpointError(f"{context} is missing: {candidate}")
    return candidate


def nonempty(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointError(f"{context} must be a non-empty string")
    return value.strip()


def parse_time(value: Any, context: str) -> str:
    text = nonempty(value, context)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckpointError(f"{context} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CheckpointError(f"{context} must include a timezone")
    return text


def time_value(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_binding(
    project: Path,
    value: Any,
    context: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise CheckpointError(f"{context} must be a path/hash object")
    raw_path = nonempty(value.get("path"), f"{context}.path").replace("\\", "/")
    expected = nonempty(value.get("sha256"), f"{context}.sha256").lower()
    if not SHA256_RE.fullmatch(expected):
        raise CheckpointError(f"{context}.sha256 must be 64 hexadecimal characters")
    target = inside_project(project, Path(raw_path), context, must_exist=True)
    actual = file_hash(target)
    if actual != expected:
        raise CheckpointError(
            f"{context} hash mismatch: expected {expected}, found {actual}"
        )
    relative = target.relative_to(project.resolve()).as_posix()
    return {"path": relative, "sha256": actual}


def validate_bindings_list(
    project: Path,
    value: Any,
    context: str,
    *,
    require_nonempty: bool,
) -> list[dict[str, str]]:
    if not isinstance(value, list) or (require_nonempty and not value):
        suffix = " and non-empty" if require_nonempty else ""
        raise CheckpointError(f"{context} must be a JSON array{suffix}")
    return [
        validate_binding(project, item, f"{context}[{index}]")
        for index, item in enumerate(value)
    ]


def register_binding(
    table: dict[str, str],
    binding: dict[str, str],
    context: str,
) -> None:
    path = binding["path"]
    previous = table.get(path)
    if previous is not None and previous != binding["sha256"]:
        raise CheckpointError(f"{context} gives conflicting hashes for {path}")
    table[path] = binding["sha256"]


def validate_state(
    project: Path,
    state_path: Path,
    state: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rendered_state = json.dumps(state, ensure_ascii=False)
    if "{{" in rendered_state:
        raise CheckpointError("interruption state still contains template placeholders")
    if state.get("schema_version") != 1:
        raise CheckpointError("interruption state schema_version must be 1")
    checkpoint_sequence = state.get("checkpoint_sequence")
    if (
        not isinstance(checkpoint_sequence, int)
        or isinstance(checkpoint_sequence, bool)
        or checkpoint_sequence < 0
    ):
        raise CheckpointError("checkpoint_sequence must be a non-negative integer")
    expected_state_name = f"interruption_state-{checkpoint_sequence:02d}.json"
    if state_path.name != expected_state_name:
        raise CheckpointError(
            f"interruption state must be named {expected_state_name}"
        )
    run_id = nonempty(state.get("run_id"), "run_id")
    packet_id = nonempty(state.get("task_packet_id"), "task_packet_id")
    reason = nonempty(state.get("reason"), "reason")
    if reason not in REASONS:
        raise CheckpointError(f"reason must be one of {sorted(REASONS)}")
    created_at = parse_time(state.get("created_at"), "created_at")
    source_commit = nonempty(state.get("source_commit"), "source_commit")
    if not COMMIT_RE.fullmatch(source_commit):
        raise CheckpointError("source_commit must be a 40- or 64-hex commit id")

    binding_table: dict[str, str] = {}
    task_contract = validate_binding(project, state.get("task_contract"), "task_contract")
    register_binding(binding_table, task_contract, "task_contract")
    optional_bindings: dict[str, dict[str, str] | None] = {}
    for key in ("closure_gate", "whiteboard", "latest_audit"):
        value = state.get(key)
        if value is None:
            optional_bindings[key] = None
            continue
        binding = validate_binding(project, value, key)
        register_binding(binding_table, binding, key)
        optional_bindings[key] = binding

    completed_value = state.get("completed_obligations")
    if not isinstance(completed_value, list):
        raise CheckpointError("completed_obligations must be a JSON array")
    completed_ids: set[str] = set()
    completed_evidence_paths: set[str] = set()
    for index, item in enumerate(completed_value):
        if not isinstance(item, dict):
            raise CheckpointError(f"completed_obligations[{index}] must be an object")
        obligation_id = nonempty(item.get("id"), f"completed_obligations[{index}].id")
        if obligation_id in completed_ids:
            raise CheckpointError(f"duplicate completed obligation {obligation_id!r}")
        completed_ids.add(obligation_id)
        evidence = validate_binding(
            project,
            item.get("evidence"),
            f"completed_obligations[{index}].evidence",
        )
        register_binding(binding_table, evidence, f"completed obligation {obligation_id}")
        completed_evidence_paths.add(evidence["path"])

    open_value = state.get("open_obligations")
    if not isinstance(open_value, list):
        raise CheckpointError("open_obligations must be a JSON array")
    open_ids: set[str] = set()
    open_inputs: dict[str, set[str]] = {}
    open_action_ids: dict[str, str] = {}
    live_action_ids: set[str] = set()
    for index, item in enumerate(open_value):
        if not isinstance(item, dict):
            raise CheckpointError(f"open_obligations[{index}] must be an object")
        obligation_id = nonempty(item.get("id"), f"open_obligations[{index}].id")
        if obligation_id in open_ids:
            raise CheckpointError(f"duplicate open obligation {obligation_id!r}")
        open_ids.add(obligation_id)
        nonempty(item.get("exact_gap"), f"open_obligations[{index}].exact_gap")
        next_action = item.get("next_action")
        if not isinstance(next_action, dict):
            raise CheckpointError(
                f"open_obligations[{index}].next_action must be an object"
            )
        next_action_id = nonempty(
            next_action.get("action_id"),
            f"open_obligations[{index}].next_action.action_id",
        )
        if next_action_id in live_action_ids:
            raise CheckpointError(f"duplicate live next action {next_action_id!r}")
        live_action_ids.add(next_action_id)
        open_action_ids[obligation_id] = next_action_id
        nonempty(
            next_action.get("description"),
            f"open_obligations[{index}].next_action.description",
        )
        inputs = validate_bindings_list(
            project,
            item.get("required_inputs"),
            f"open_obligations[{index}].required_inputs",
            require_nonempty=True,
        )
        open_inputs[obligation_id] = {binding["path"] for binding in inputs}
        for binding in inputs:
            register_binding(binding_table, binding, f"open obligation {obligation_id}")
    overlap = completed_ids & open_ids
    if overlap:
        raise CheckpointError(f"obligations cannot be both completed and open: {sorted(overlap)}")

    inflight_value = state.get("inflight_work")
    if not isinstance(inflight_value, list):
        raise CheckpointError("inflight_work must be a JSON array")
    inflight_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    inflight_artifact_paths: dict[str, str] = {}
    for index, item in enumerate(inflight_value):
        if not isinstance(item, dict):
            raise CheckpointError(f"inflight_work[{index}] must be an object")
        worker_id = nonempty(item.get("worker_id"), f"inflight_work[{index}].worker_id")
        nonempty(item.get("session_id"), f"inflight_work[{index}].session_id")
        if worker_id in inflight_ids:
            raise CheckpointError(f"duplicate in-flight worker {worker_id!r}")
        inflight_ids.add(worker_id)
        status = nonempty(item.get("status"), f"inflight_work[{index}].status")
        if status not in INFLIGHT_STATES:
            raise CheckpointError(f"inflight_work[{index}].status is invalid")
        if status in UNRESOLVED_INFLIGHT:
            unresolved_ids.add(worker_id)
        artifact = item.get("artifact")
        if status == "COMPLETED_UNINGESTED" and artifact is None:
            raise CheckpointError(
                f"inflight worker {worker_id!r} is completed but has no artifact"
            )
        if artifact is not None:
            binding = validate_binding(project, artifact, f"inflight_work[{index}].artifact")
            register_binding(binding_table, binding, f"in-flight worker {worker_id}")
            inflight_artifact_paths[worker_id] = binding["path"]

    reconciliation_value = state.get("inflight_reconciliation")
    if not isinstance(reconciliation_value, list):
        raise CheckpointError("inflight_reconciliation must be a JSON array")
    reconciled_workers: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(reconciliation_value):
        if not isinstance(item, dict):
            raise CheckpointError(f"inflight_reconciliation[{index}] must be an object")
        worker_id = nonempty(
            item.get("worker_id"),
            f"inflight_reconciliation[{index}].worker_id",
        )
        nonempty(item.get("session_id"), f"inflight_reconciliation[{index}].session_id")
        if worker_id in reconciled_workers:
            raise CheckpointError(f"duplicate in-flight reconciliation {worker_id!r}")
        outcome = nonempty(
            item.get("outcome"),
            f"inflight_reconciliation[{index}].outcome",
        )
        if outcome not in RECONCILIATION_OUTCOMES:
            raise CheckpointError(
                f"inflight_reconciliation[{index}].outcome is invalid"
            )
        evidence = validate_binding(
            project,
            item.get("evidence"),
            f"inflight_reconciliation[{index}].evidence",
        )
        register_binding(binding_table, evidence, f"in-flight reconciliation {worker_id}")
        reconciled_workers[worker_id] = item

    do_not_repeat_value = state.get("do_not_repeat")
    if not isinstance(do_not_repeat_value, list):
        raise CheckpointError("do_not_repeat must be a JSON array")
    blocked_actions: set[str] = set()
    for index, item in enumerate(do_not_repeat_value):
        if not isinstance(item, dict):
            raise CheckpointError(f"do_not_repeat[{index}] must be an object")
        action_id = nonempty(item.get("action_id"), f"do_not_repeat[{index}].action_id")
        nonempty(item.get("reason"), f"do_not_repeat[{index}].reason")
        if action_id in blocked_actions:
            raise CheckpointError(f"duplicate do-not-repeat action {action_id!r}")
        blocked_actions.add(action_id)
        evidence = validate_binding(project, item.get("evidence"), f"do_not_repeat[{index}].evidence")
        register_binding(binding_table, evidence, f"do-not-repeat action {action_id}")
    conflicting_open_actions = set(open_action_ids.values()) & blocked_actions
    if conflicting_open_actions:
        raise CheckpointError(
            "open obligations select do-not-repeat actions: "
            f"{sorted(conflicting_open_actions)}"
        )

    result_status = nonempty(state.get("result_status"), "result_status")
    if result_status not in RESULT_STATUSES:
        raise CheckpointError(f"result_status must be one of {sorted(RESULT_STATUSES)}")
    if result_status in COMPLETE_RESULT_STATUSES and open_ids:
        raise CheckpointError(
            f"result_status {result_status} cannot retain open obligations"
        )

    experiment = state.get("experiment_integrity")
    if not isinstance(experiment, dict) or not isinstance(experiment.get("enabled"), bool):
        raise CheckpointError("experiment_integrity.enabled must be boolean")
    if experiment["enabled"]:
        for key in ("arm_id", "task_id", "workspace_id"):
            nonempty(experiment.get(key), f"experiment_integrity.{key}")
        for key in ("prompt", "harness", "source_snapshot"):
            binding = validate_binding(project, experiment.get(key), f"experiment_integrity.{key}")
            register_binding(binding_table, binding, f"experiment {key}")
        if experiment.get("hidden_gold_state") not in {"SEALED", "NOT_APPLICABLE"}:
            raise CheckpointError(
                "experiment_integrity.hidden_gold_state must be SEALED or NOT_APPLICABLE"
            )
        if experiment.get("metrics_scope") != "cumulative_pre_checkpoint":
            raise CheckpointError(
                "experiment_integrity.metrics_scope must be cumulative_pre_checkpoint"
            )
        if experiment.get("checkpoint_overhead_policy") not in CHECKPOINT_OVERHEAD_POLICIES:
            raise CheckpointError(
                "experiment_integrity.checkpoint_overhead_policy must be "
                f"one of {sorted(CHECKPOINT_OVERHEAD_POLICIES)}"
            )
        segment_index = experiment.get("segment_index")
        if not isinstance(segment_index, int) or isinstance(segment_index, bool) or segment_index < 0:
            raise CheckpointError("experiment_integrity.segment_index must be a non-negative integer")
        if segment_index != checkpoint_sequence:
            raise CheckpointError(
                "experiment_integrity.segment_index must equal checkpoint_sequence"
            )
        cost_status = experiment.get("cost_status")
        if cost_status not in {"MEASURED", "NOT_AVAILABLE"}:
            raise CheckpointError(
                "experiment_integrity.cost_status must be MEASURED or NOT_AVAILABLE"
            )
        metrics = experiment.get("cumulative_metrics")
        if not isinstance(metrics, dict) or not REQUIRED_METRICS.issubset(metrics):
            raise CheckpointError(
                "experiment_integrity.cumulative_metrics is missing required counters"
            )
        for key, value in metrics.items():
            if key == "cost_usd" and value is None and cost_status == "NOT_AVAILABLE":
                continue
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or value < 0
            ):
                raise CheckpointError(
                    f"cumulative metric {key!r} must be finite and non-negative"
                )
        if cost_status == "MEASURED" and metrics.get("cost_usd") is None:
            raise CheckpointError("MEASURED cost requires cumulative_metrics.cost_usd")
        if cost_status == "NOT_AVAILABLE" and metrics.get("cost_usd") is not None:
            raise CheckpointError("NOT_AVAILABLE cost requires cost_usd=null")

    resume = state.get("resume")
    if not isinstance(resume, dict):
        raise CheckpointError("resume must be a JSON object")
    action = resume.get("first_action")
    if not isinstance(action, dict):
        raise CheckpointError("resume.first_action must be an object")
    action_kind = nonempty(action.get("kind"), "resume.first_action.kind")
    action_id = nonempty(action.get("action_id"), "resume.first_action.action_id")
    if action_kind not in FIRST_ACTIONS:
        raise CheckpointError(f"resume.first_action.kind must be one of {sorted(FIRST_ACTIONS)}")
    target_id = str(action.get("target_id", "")).strip()
    if action_kind in {"RECONCILE_INFLIGHT", "CONTINUE_OBLIGATION"} and not target_id:
        raise CheckpointError("resume.first_action.target_id is required for this action")
    if unresolved_ids and action_kind != "RECONCILE_INFLIGHT":
        raise CheckpointError(
            "unresolved in-flight work requires RECONCILE_INFLIGHT before any new work"
        )
    if action_kind == "RECONCILE_INFLIGHT" and target_id not in unresolved_ids:
        raise CheckpointError("resume first action does not target unresolved in-flight work")
    if action_kind == "CONTINUE_OBLIGATION" and target_id not in open_ids:
        raise CheckpointError("resume first action does not target an open obligation")
    if (
        action_kind == "CONTINUE_OBLIGATION"
        and action_id != open_action_ids[target_id]
    ):
        raise CheckpointError(
            "resume first action must match the open obligation next_action.action_id"
        )
    if target_id in completed_ids or action_id in blocked_actions:
        raise CheckpointError("resume first action targets completed or do-not-repeat work")

    read_set = validate_bindings_list(
        project,
        resume.get("minimal_read_set"),
        "resume.minimal_read_set",
        require_nonempty=True,
    )
    if len(read_set) > MAX_MINIMAL_READ_SET:
        raise CheckpointError(
            f"resume.minimal_read_set exceeds {MAX_MINIMAL_READ_SET} artifacts"
        )
    read_paths = {binding["path"] for binding in read_set}
    forbidden_reads = sorted(
        path for path in read_paths
        if any(token in path.lower() for token in FORBIDDEN_READ_SET_TOKENS)
    )
    if forbidden_reads:
        raise CheckpointError(
            "resume.minimal_read_set contains transcript/history artifacts: "
            f"{forbidden_reads}"
        )
    whiteboard = optional_bindings["whiteboard"]
    allowed_read_paths = {task_contract["path"]}
    if whiteboard is not None:
        allowed_read_paths.add(whiteboard["path"])
    if action_kind == "CONTINUE_OBLIGATION":
        allowed_read_paths.update(open_inputs[target_id])
    elif action_kind == "RECONCILE_INFLIGHT":
        artifact_path = inflight_artifact_paths.get(target_id)
        if artifact_path is not None:
            allowed_read_paths.add(artifact_path)
    else:
        for key in ("closure_gate", "latest_audit"):
            binding = optional_bindings[key]
            if binding is not None:
                allowed_read_paths.add(binding["path"])
        allowed_read_paths.update(completed_evidence_paths)
    unexpected_reads = sorted(read_paths - allowed_read_paths)
    if unexpected_reads:
        raise CheckpointError(
            "resume.minimal_read_set contains artifacts outside the action-scoped read set: "
            f"{unexpected_reads}"
        )
    for binding in read_set:
        register_binding(binding_table, binding, "resume minimal read set")
    if task_contract["path"] not in read_paths:
        raise CheckpointError("resume.minimal_read_set must include task_contract")
    if whiteboard is not None and whiteboard["path"] not in read_paths:
        raise CheckpointError("resume.minimal_read_set must include whiteboard when present")
    if action_kind == "CONTINUE_OBLIGATION":
        missing = open_inputs[target_id] - read_paths
        if missing:
            raise CheckpointError(
                f"resume.minimal_read_set misses required inputs for {target_id}: {sorted(missing)}"
            )
    elif action_kind == "RECONCILE_INFLIGHT":
        artifact_path = inflight_artifact_paths.get(target_id)
        if artifact_path is not None and artifact_path not in read_paths:
            raise CheckpointError(
                f"resume.minimal_read_set misses in-flight artifact for {target_id}"
            )

    budget = resume.get("budget")
    if not isinstance(budget, dict) or budget.get("unit") not in BUDGET_UNITS:
        raise CheckpointError(f"resume.budget.unit must be one of {sorted(BUDGET_UNITS)}")
    limit = budget.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise CheckpointError("resume.budget.limit must be a positive integer")
    nonempty(resume.get("stop_condition"), "resume.stop_condition")

    predecessor = state.get("predecessor")
    status_transition = state.get("status_transition")
    ancestor_bound_artifacts: set[tuple[str, str]] = set()
    if checkpoint_sequence == 0:
        if predecessor is not None:
            raise CheckpointError("checkpoint_sequence 0 must have predecessor=null")
        if status_transition is not None:
            raise CheckpointError("checkpoint_sequence 0 must have status_transition=null")
        if reconciled_workers:
            raise CheckpointError("checkpoint_sequence 0 must have empty inflight_reconciliation")
    else:
        if not isinstance(predecessor, dict):
            raise CheckpointError("checkpoint_sequence > 0 requires predecessor bindings")
        predecessor_checkpoint = validate_binding(
            project,
            predecessor.get("checkpoint"),
            "predecessor.checkpoint",
        )
        predecessor_receipt = validate_binding(
            project,
            predecessor.get("resume_receipt"),
            "predecessor.resume_receipt",
        )
        for context, binding in (
            ("predecessor checkpoint", predecessor_checkpoint),
            ("predecessor receipt", predecessor_receipt),
        ):
            register_binding(binding_table, binding, context)
        previous_sequence = checkpoint_sequence - 1
        expected_checkpoint_name = f"interruption_checkpoint-{previous_sequence:02d}.json"
        expected_receipt_name = f"resume_receipt-{previous_sequence:02d}.json"
        predecessor_checkpoint_path = inside_project(
            project,
            Path(predecessor_checkpoint["path"]),
            "predecessor checkpoint",
            must_exist=True,
        )
        predecessor_receipt_path = inside_project(
            project,
            Path(predecessor_receipt["path"]),
            "predecessor resume receipt",
            must_exist=True,
        )
        if (
            predecessor_checkpoint_path.parent != state_path.parent
            or predecessor_receipt_path.parent != state_path.parent
            or predecessor_checkpoint_path.name != expected_checkpoint_name
            or predecessor_receipt_path.name != expected_receipt_name
        ):
            raise CheckpointError(
                "predecessor checkpoint and receipt must be the canonical previous pair"
            )
        previous_snapshot = _verify_checkpoint_snapshot(project, predecessor_checkpoint_path)
        previous_verification = previous_snapshot["verification"]
        ancestor_bound_artifacts = set(previous_snapshot["lineage_bound_artifacts"])
        if previous_verification["checkpoint_sequence"] != previous_sequence:
            raise CheckpointError("predecessor checkpoint sequence is not contiguous")
        previous_receipt = validate_resume_receipt(
            project,
            predecessor_checkpoint_path,
            predecessor_receipt_path,
            snapshot=previous_snapshot,
        )
        if time_value(created_at) < time_value(previous_receipt["resumed_at"]):
            raise CheckpointError("current created_at precedes predecessor resume time")
        previous_checkpoint_data = load_json(
            predecessor_checkpoint_path,
            "predecessor checkpoint",
        )
        previous_state_path = inside_project(
            project,
            Path(previous_checkpoint_data["state"]["path"]),
            "predecessor state",
            must_exist=True,
        )
        previous_state = load_json(previous_state_path, "predecessor state")
        if run_id != previous_state.get("run_id") or packet_id != previous_state.get("task_packet_id"):
            raise CheckpointError("run_id and task_packet_id must remain fixed across segments")
        if source_commit.lower() != str(previous_state.get("source_commit", "")).lower():
            raise CheckpointError("source_commit must remain fixed across segments")
        previous_contract = validate_binding(
            project,
            previous_state.get("task_contract"),
            "predecessor task_contract",
        )
        if task_contract != previous_contract:
            raise CheckpointError("task_contract must remain fixed across segments")
        previous_completed = {
            str(item.get("id", "")) for item in previous_state.get("completed_obligations", [])
            if isinstance(item, dict)
        }
        if not previous_completed.issubset(completed_ids):
            raise CheckpointError("completed obligations cannot disappear across segments")
        previous_open_items = [
            item for item in previous_state.get("open_obligations", [])
            if isinstance(item, dict)
        ]
        previous_open = {str(item.get("id", "")) for item in previous_open_items}
        if not previous_open.issubset(open_ids | completed_ids):
            raise CheckpointError("open obligations cannot disappear without completion")
        previous_blocked = {
            str(item.get("action_id", "")) for item in previous_state.get("do_not_repeat", [])
            if isinstance(item, dict)
        }
        if not previous_blocked.issubset(blocked_actions):
            raise CheckpointError("do-not-repeat actions cannot disappear across segments")
        previous_open_actions = {
            str(item.get("id", "")): str(item.get("next_action", {}).get("action_id", ""))
            for item in previous_open_items
            if isinstance(item.get("next_action"), dict)
        }
        retired_actions = {
            previous_action
            for obligation_id, previous_action in previous_open_actions.items()
            if open_action_ids.get(obligation_id) != previous_action
        }
        missing_retired_actions = retired_actions - blocked_actions
        if missing_retired_actions:
            raise CheckpointError(
                "completed or replaced next actions must enter do_not_repeat: "
                f"{sorted(missing_retired_actions)}"
            )
        previous_unresolved = {
            str(item.get("worker_id", "")): str(item.get("session_id", ""))
            for item in previous_state.get("inflight_work", [])
            if isinstance(item, dict) and item.get("status") in UNRESOLVED_INFLIGHT
        }
        current_unresolved = {
            str(item.get("worker_id", "")): str(item.get("session_id", ""))
            for item in inflight_value
            if isinstance(item, dict) and item.get("status") in UNRESOLVED_INFLIGHT
        }
        for worker_id, session_id in previous_unresolved.items():
            if worker_id in current_unresolved:
                if current_unresolved[worker_id] != session_id:
                    raise CheckpointError(
                        f"in-flight session changed without reconciliation for {worker_id!r}"
                    )
                if worker_id in reconciled_workers:
                    raise CheckpointError(
                        f"worker {worker_id!r} cannot be both unresolved and reconciled"
                    )
                continue
            record = reconciled_workers.get(worker_id)
            if record is None:
                raise CheckpointError(
                    f"predecessor worker {worker_id!r} disappeared without reconciliation"
                )
            if record.get("session_id") != session_id:
                raise CheckpointError(
                    f"in-flight reconciliation session mismatch for {worker_id!r}"
                )
        unexpected_reconciliations = set(reconciled_workers) - set(previous_unresolved)
        if unexpected_reconciliations:
            raise CheckpointError(
                "inflight_reconciliation names workers not unresolved in the predecessor: "
                f"{sorted(unexpected_reconciliations)}"
            )
        previous_experiment = previous_state.get("experiment_integrity")
        if not isinstance(previous_experiment, dict):
            raise CheckpointError("predecessor experiment_integrity is invalid")
        if experiment.get("enabled") != previous_experiment.get("enabled"):
            raise CheckpointError("experiment mode cannot change across segments")
        if experiment["enabled"]:
            for key in (
                "arm_id",
                "task_id",
                "workspace_id",
                "hidden_gold_state",
                "metrics_scope",
                "checkpoint_overhead_policy",
                "cost_status",
            ):
                if experiment.get(key) != previous_experiment.get(key):
                    raise CheckpointError(
                        f"experiment_integrity.{key} must remain fixed across segments"
                    )
            for key in ("prompt", "harness", "source_snapshot"):
                current_binding = validate_binding(
                    project,
                    experiment.get(key),
                    f"experiment_integrity.{key}",
                )
                previous_binding = validate_binding(
                    project,
                    previous_experiment.get(key),
                    f"predecessor experiment_integrity.{key}",
                )
                if current_binding != previous_binding:
                    raise CheckpointError(
                        f"experiment_integrity.{key} must remain fixed across segments"
                    )
            current_metrics = experiment["cumulative_metrics"]
            previous_metrics = previous_experiment.get("cumulative_metrics")
            if not isinstance(previous_metrics, dict) or set(current_metrics) != set(previous_metrics):
                raise CheckpointError("cumulative metric keys must remain fixed across segments")
            for key, previous_value in previous_metrics.items():
                current_value = current_metrics[key]
                if previous_value is None and current_value is None:
                    continue
                if not isinstance(previous_value, (int, float)) or isinstance(previous_value, bool):
                    raise CheckpointError(f"predecessor cumulative metric {key!r} is invalid")
                if current_value < previous_value:
                    raise CheckpointError(
                        f"cumulative metric {key!r} cannot decrease across segments"
                    )

        previous_status = nonempty(previous_state.get("result_status"), "predecessor result_status")
        if result_status == previous_status:
            if status_transition is not None:
                raise CheckpointError("unchanged result_status requires status_transition=null")
        else:
            if not isinstance(status_transition, dict):
                raise CheckpointError("result_status change requires status_transition")
            if status_transition.get("from") != previous_status or status_transition.get("to") != result_status:
                raise CheckpointError("status_transition endpoints do not match the states")
            changed_at = parse_time(status_transition.get("changed_at"), "status_transition.changed_at")
            if time_value(changed_at) < time_value(previous_receipt["resumed_at"]):
                raise CheckpointError("status transition precedes the predecessor resume")
            if time_value(changed_at) > time_value(created_at):
                raise CheckpointError("status transition follows current created_at")
            transition_evidence = validate_binding(
                project,
                status_transition.get("evidence"),
                "status_transition.evidence",
            )
            transition_audit = validate_binding(
                project,
                status_transition.get("audit"),
                "status_transition.audit",
            )
            register_binding(binding_table, transition_evidence, "status transition evidence")
            register_binding(binding_table, transition_audit, "status transition audit")
            if optional_bindings["latest_audit"] != transition_audit:
                raise CheckpointError(
                    "status_transition.audit must match latest_audit"
                )
            if (
                transition_evidence["path"] == transition_audit["path"]
                or transition_evidence["sha256"] == transition_audit["sha256"]
            ):
                raise CheckpointError(
                    "status transition evidence and audit must be distinct artifacts"
                )
            ancestor_hashes = {sha256 for _path, sha256 in ancestor_bound_artifacts}
            if transition_evidence["sha256"] in ancestor_hashes:
                raise CheckpointError("status transition evidence must be new to the full lineage")
            if transition_audit["sha256"] in ancestor_hashes:
                raise CheckpointError("status transition audit must be new to the full lineage")

    bindings = [
        {"path": path, "sha256": binding_table[path]}
        for path in sorted(binding_table)
    ]
    summary = {
        "run_id": run_id,
        "checkpoint_sequence": checkpoint_sequence,
        "task_packet_id": packet_id,
        "reason": reason,
        "created_at": created_at,
        "source_commit": source_commit.lower(),
        "result_status": result_status,
        "resume": resume,
        "experiment_integrity": experiment,
        "_ancestor_bound_artifacts": sorted(ancestor_bound_artifacts),
    }
    return summary, bindings


def _build_checkpoint_parts(
    project: Path,
    state_path: Path,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary, bindings = validate_state(project, state_path, state)
    state_relative = state_path.resolve().relative_to(project.resolve()).as_posix()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "sealed_at": summary["created_at"],
        "run_id": summary["run_id"],
        "checkpoint_sequence": summary["checkpoint_sequence"],
        "task_packet_id": summary["task_packet_id"],
        "reason": summary["reason"],
        "source_commit": summary["source_commit"],
        "result_status": summary["result_status"],
        "state": {"path": state_relative, "sha256": file_hash(state_path)},
        "bound_artifacts": bindings,
        "resume_contract_sha256": object_hash(summary["resume"]),
        "experiment_integrity_sha256": object_hash(summary["experiment_integrity"]),
    }
    payload["checkpoint_id"] = f"sha256:{object_hash(payload)}"
    return payload, summary


def build_checkpoint(
    project: Path,
    state_path: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    checkpoint, _summary = _build_checkpoint_parts(project, state_path, state)
    return checkpoint


def write_immutable(path: Path, value: dict[str, Any], context: str) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    except FileExistsError:
        existing = path.read_text(encoding="utf-8")
        if existing != rendered:
            raise CheckpointError(
                f"existing {context} differs; create the next canonical segment"
            )


def seal_checkpoint(project: Path, state_path: Path, output_path: Path) -> dict[str, Any]:
    project = project.resolve()
    state_path = inside_project(project, state_path, "interruption state", must_exist=True)
    output_path = inside_project(project, output_path, "checkpoint output", must_exist=False)
    if state_path == output_path:
        raise CheckpointError("checkpoint output must differ from interruption state")
    state = load_json(state_path, "interruption state")
    checkpoint = build_checkpoint(project, state_path, state)
    expected_output = state_path.with_name(
        f"interruption_checkpoint-{checkpoint['checkpoint_sequence']:02d}.json"
    )
    if output_path != expected_output:
        raise CheckpointError(f"checkpoint output must be {expected_output.name}")
    write_immutable(output_path, checkpoint, "checkpoint")
    return checkpoint


def _verify_checkpoint_snapshot(
    project: Path,
    checkpoint_path: Path,
) -> dict[str, Any]:
    project = project.resolve()
    checkpoint_path = inside_project(project, checkpoint_path, "checkpoint", must_exist=True)
    checkpoint = load_json(checkpoint_path, "checkpoint")
    state_binding = checkpoint.get("state")
    state = validate_binding(project, state_binding, "checkpoint.state")
    state_path = inside_project(project, Path(state["path"]), "checkpoint state", must_exist=True)
    state_data = load_json(state_path, "interruption state")
    expected, summary = _build_checkpoint_parts(project, state_path, state_data)
    if checkpoint != expected:
        raise CheckpointError("checkpoint envelope does not match the current state and bindings")
    expected_path = state_path.with_name(
        f"interruption_checkpoint-{checkpoint['checkpoint_sequence']:02d}.json"
    )
    if checkpoint_path != expected_path:
        raise CheckpointError(f"checkpoint must be named {expected_path.name}")
    verification = {
        "verdict": "READY",
        "checkpoint_id": checkpoint["checkpoint_id"],
        "checkpoint_sha256": file_hash(checkpoint_path),
        "run_id": checkpoint["run_id"],
        "checkpoint_sequence": checkpoint["checkpoint_sequence"],
        "task_packet_id": checkpoint["task_packet_id"],
        "checked_artifacts": len(checkpoint["bound_artifacts"]),
    }
    current_bound = {
        (str(item["path"]), str(item["sha256"]).lower())
        for item in checkpoint["bound_artifacts"]
    }
    lineage_bound = set(summary["_ancestor_bound_artifacts"]) | current_bound
    return {
        "verification": verification,
        "checkpoint": checkpoint,
        "state": state_data,
        "lineage_bound_artifacts": frozenset(lineage_bound),
    }


def verify_checkpoint(project: Path, checkpoint_path: Path) -> dict[str, Any]:
    return _verify_checkpoint_snapshot(project, checkpoint_path)["verification"]


def build_resume_receipt(
    project: Path,
    checkpoint_path: Path,
    resumed_at: str,
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    resumed_at = parse_time(resumed_at, "resumed_at")
    checkpoint_path = inside_project(project, checkpoint_path, "checkpoint", must_exist=True)
    if snapshot is None:
        snapshot = _verify_checkpoint_snapshot(project, checkpoint_path)
    verification = snapshot["verification"]
    checkpoint = snapshot["checkpoint"]
    if time_value(resumed_at) < time_value(checkpoint["sealed_at"]):
        raise CheckpointError("resumed_at cannot precede checkpoint sealed_at")
    state = snapshot["state"]
    experiment = state["experiment_integrity"]
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "checkpoint_id": verification["checkpoint_id"],
        "checkpoint_sha256": verification["checkpoint_sha256"],
        "resumed_at": resumed_at,
        "run_id": verification["run_id"],
        "checkpoint_sequence": verification["checkpoint_sequence"],
        "next_checkpoint_sequence": verification["checkpoint_sequence"] + 1,
        "task_packet_id": verification["task_packet_id"],
        "result_status": state["result_status"],
        "completed_obligation_ids": [
            item["id"] for item in state["completed_obligations"]
        ],
        "open_obligation_ids": [item["id"] for item in state["open_obligations"]],
        "unresolved_inflight_work": [
            item for item in state["inflight_work"]
            if item["status"] in UNRESOLVED_INFLIGHT
        ],
        "do_not_repeat_action_ids": [
            item["action_id"] for item in state["do_not_repeat"]
        ],
        "first_action": state["resume"]["first_action"],
        "minimal_read_set": state["resume"]["minimal_read_set"],
        "resume_budget": state["resume"]["budget"],
        "stop_condition": state["resume"]["stop_condition"],
    }
    if experiment["enabled"]:
        receipt["experiment_integrity"] = {
            "arm_id": experiment["arm_id"],
            "task_id": experiment["task_id"],
            "workspace_id": experiment["workspace_id"],
            "next_segment_index": experiment["segment_index"] + 1,
            "cumulative_metrics": experiment["cumulative_metrics"],
            "checkpoint_overhead_policy": experiment["checkpoint_overhead_policy"],
        }
    return receipt


def validate_resume_receipt(
    project: Path,
    checkpoint_path: Path,
    receipt_path: Path,
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    checkpoint_path = inside_project(project, checkpoint_path, "checkpoint", must_exist=True)
    receipt_path = inside_project(project, receipt_path, "resume receipt", must_exist=True)
    if snapshot is None:
        snapshot = _verify_checkpoint_snapshot(project, checkpoint_path)
    verification = snapshot["verification"]
    expected_path = checkpoint_path.with_name(
        f"resume_receipt-{verification['checkpoint_sequence']:02d}.json"
    )
    if receipt_path != expected_path:
        raise CheckpointError(f"resume receipt must be named {expected_path.name}")
    receipt = load_json(receipt_path, "resume receipt")
    resumed_at = parse_time(receipt.get("resumed_at"), "resume receipt resumed_at")
    expected = build_resume_receipt(
        project,
        checkpoint_path,
        resumed_at,
        snapshot=snapshot,
    )
    if receipt != expected:
        raise CheckpointError("resume receipt does not match its checkpoint")
    return receipt


def write_resume_receipt(
    project: Path,
    checkpoint_path: Path,
    receipt_path: Path,
    resumed_at: str,
) -> dict[str, Any]:
    project = project.resolve()
    checkpoint_path = inside_project(project, checkpoint_path, "checkpoint", must_exist=True)
    receipt_path = inside_project(project, receipt_path, "resume receipt", must_exist=False)
    snapshot = _verify_checkpoint_snapshot(project, checkpoint_path)
    verification = snapshot["verification"]
    expected_path = checkpoint_path.with_name(
        f"resume_receipt-{verification['checkpoint_sequence']:02d}.json"
    )
    if receipt_path != expected_path:
        raise CheckpointError(f"resume receipt must be {expected_path.name}")
    receipt = build_resume_receipt(
        project,
        checkpoint_path,
        resumed_at,
        snapshot=snapshot,
    )
    write_immutable(receipt_path, receipt, "resume receipt")
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    seal = subparsers.add_parser("seal", help="validate state and write an immutable checkpoint")
    seal.add_argument("--project", required=True, type=Path)
    seal.add_argument("--state", required=True, type=Path)
    seal.add_argument("--output", required=True, type=Path)
    verify = subparsers.add_parser("verify", help="verify a checkpoint before any model call")
    verify.add_argument("--project", required=True, type=Path)
    verify.add_argument("--checkpoint", required=True, type=Path)
    resume = subparsers.add_parser("resume", help="verify and write an immutable resume receipt")
    resume.add_argument("--project", required=True, type=Path)
    resume.add_argument("--checkpoint", required=True, type=Path)
    resume.add_argument("--receipt", required=True, type=Path)
    resume.add_argument("--resumed-at", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "seal":
            checkpoint = seal_checkpoint(args.project, args.state, args.output)
            result = {
                "verdict": "SEALED",
                "checkpoint_id": checkpoint["checkpoint_id"],
                "run_id": checkpoint["run_id"],
                "checked_artifacts": len(checkpoint["bound_artifacts"]),
            }
        elif args.command == "verify":
            result = verify_checkpoint(args.project, args.checkpoint)
        else:
            receipt = write_resume_receipt(
                args.project,
                args.checkpoint,
                args.receipt,
                args.resumed_at,
            )
            result = {
                "verdict": "RESUME_READY",
                "checkpoint_id": receipt["checkpoint_id"],
                "run_id": receipt["run_id"],
                "first_action": receipt["first_action"],
            }
    except CheckpointError as exc:
        print(json.dumps({"verdict": "STALE", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
