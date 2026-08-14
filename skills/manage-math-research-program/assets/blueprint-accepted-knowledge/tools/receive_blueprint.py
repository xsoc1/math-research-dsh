#!/usr/bin/env python3
"""Validate or deterministically receive one immutable Blueprint v2.2 proposal."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from blueprint_common import (
    FileLock,
    append_event,
    atomic_write_json,
    is_protected_node,
    normalize_reasons,
    semantic_node_hash,
    semantic_row_hash,
    sha256_bytes,
    sha256_file,
    utc_now,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "2.2"
DEPENDENCY_FIELDS = {
    "assumptions",
    "theory_inputs",
    "method_inputs",
    "numerical_inputs",
    "premise_inputs",
    "definition_inputs",
    "inference_inputs",
    "refutation_inputs",
    "target_inputs",
}
ROLE_ALIASES = {
    "assumption": "assumptions",
    "assumptions": "assumptions",
    "theory_input": "theory_inputs",
    "theory_inputs": "theory_inputs",
    "method_input": "method_inputs",
    "method_inputs": "method_inputs",
    "numerical_input": "numerical_inputs",
    "numerical_inputs": "numerical_inputs",
    "premise_input": "premise_inputs",
    "premise_inputs": "premise_inputs",
    "definition_input": "definition_inputs",
    "definition_inputs": "definition_inputs",
    "inference_input": "inference_inputs",
    "inference_inputs": "inference_inputs",
    "refutation_input": "refutation_inputs",
    "refutation_inputs": "refutation_inputs",
    "target_input": "target_inputs",
    "target_inputs": "target_inputs",
}
CANONICAL_EDGE_ROLE_BY_FIELD = {
    "assumptions": "assumption",
    "theory_inputs": "theory_input",
    "method_inputs": "method_input",
    "numerical_inputs": "numerical_input",
    "premise_inputs": "premise_input",
    "definition_inputs": "definition_input",
    "inference_inputs": "inference_input",
    "refutation_inputs": "refutation_input",
    "target_inputs": "target_input",
}
STRUCTURAL_REFERENCE_FIELDS = DEPENDENCY_FIELDS | {
    "conclusion",
    "target_claim",
    "negation_claim",
    "refutes",
}
BLUEPRINT_OPS = {"add_node", "update_node", "add_edge", "remove_edge"}
INVENTORY_OPS = {"add_inventory_row", "update_inventory_row"}


class ProposalError(Exception):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        super().__init__(message)
        self.reason = {"code": code, "message": message, **context}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProposalError("INVALID_JSON_OBJECT", f"{path.name} must contain one JSON object")
    return value


def load_json_and_hash(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ProposalError("INVALID_JSON_OBJECT", f"{path.name} must contain one JSON object")
    return value, sha256_bytes(payload)


def read_inventory(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ProposalError("INVALID_INVENTORY", "evidence inventory has no header")
        return list(reader.fieldnames), list(reader)


def write_inventory(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def node_maps(blueprint: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    nodes = blueprint.get("nodes", [])
    edges = blueprint.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProposalError("INVALID_BLUEPRINT", "nodes and edges must be lists")
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ProposalError("INVALID_BLUEPRINT", "every node must be an object with a string id")
        if node["id"] in by_id:
            raise ProposalError("DUPLICATE_NODE", f"duplicate node id {node['id']}", node_id=node["id"])
        by_id[node["id"]] = node
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if isinstance(edge, list) and len(edge) == 2:
            source, target = edge
        elif isinstance(edge, dict) and edge.get("source") and edge.get("target"):
            source, target = edge["source"], edge["target"]
        else:
            raise ProposalError("INVALID_EDGE", f"invalid edge {edge!r}")
        incoming[target].add(source)
    return by_id, incoming


def semantic_hashes(blueprint: dict[str, Any]) -> dict[str, str]:
    by_id, incoming = node_maps(blueprint)
    return {
        node_id: semantic_node_hash(node, incoming.get(node_id, set()))
        for node_id, node in by_id.items()
    }


def normalize_role(role: Any) -> str:
    if role not in ROLE_ALIASES:
        raise ProposalError("INVALID_EDGE_ROLE", f"unsupported dependency role {role!r}")
    return ROLE_ALIASES[role]


def edge_endpoints(edge: Any) -> tuple[str, str] | None:
    if isinstance(edge, list) and len(edge) == 2 and all(isinstance(item, str) for item in edge):
        return edge[0], edge[1]
    if (
        isinstance(edge, dict)
        and isinstance(edge.get("source"), str)
        and isinstance(edge.get("target"), str)
    ):
        return edge["source"], edge["target"]
    return None


def replace_endpoint_edge(
    edges: list[Any], source: str, target: str, replacement: Any | None
) -> None:
    indexes = [
        index
        for index, edge in enumerate(edges)
        if edge_endpoints(edge) == (source, target)
    ]
    if len(indexes) > 1:
        raise ProposalError(
            "DUPLICATE_EDGE",
            f"multiple canonical edges exist for {source!r} -> {target!r}",
        )
    if indexes:
        index = indexes[0]
        if replacement is None:
            del edges[index]
        else:
            edges[index] = replacement
    elif replacement is not None:
        edges.append(replacement)


def split_operations(proposal: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    operations = proposal.get("operations", [])
    inventory_operations = proposal.get("inventory_operations", [])
    if not isinstance(operations, list) or not isinstance(inventory_operations, list):
        raise ProposalError("INVALID_OPERATIONS", "operations and inventory_operations must be lists")
    embedded_inventory = [op for op in operations if isinstance(op, dict) and op.get("op") in INVENTORY_OPS]
    if embedded_inventory and inventory_operations:
        raise ProposalError(
            "AMBIGUOUS_INVENTORY_OPERATIONS",
            "place inventory operations in inventory_operations only; do not duplicate them in operations",
        )
    blueprint_operations = [op for op in operations if not isinstance(op, dict) or op.get("op") not in INVENTORY_OPS]
    return blueprint_operations, inventory_operations or embedded_inventory


def actual_write_set(
    proposal: dict[str, Any], current_ids: set[str]
) -> tuple[set[str], set[str], set[str]]:
    blueprint_ops, inventory_ops = split_operations(proposal)
    existing_nodes: set[str] = set()
    new_nodes: set[str] = set()
    inventory_rows: set[str] = set()
    for operation in blueprint_ops:
        if not isinstance(operation, dict):
            raise ProposalError("INVALID_OPERATION", "each operation must be an object")
        op = operation.get("op")
        if op == "add_node":
            node = operation.get("node")
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                raise ProposalError("INVALID_ADD_NODE", "add_node requires node.id")
            new_nodes.add(node["id"])
        elif op == "update_node":
            node_id = operation.get("node_id")
            if not isinstance(node_id, str):
                raise ProposalError("INVALID_UPDATE_NODE", "update_node requires node_id")
            existing_nodes.add(node_id)
        elif op in {"add_edge", "remove_edge"}:
            target = operation.get("target")
            if not isinstance(target, str):
                raise ProposalError("INVALID_EDGE", f"{op} requires target")
            if target in current_ids:
                existing_nodes.add(target)
        elif op not in BLUEPRINT_OPS:
            raise ProposalError("UNKNOWN_OPERATION", f"unsupported operation {op!r}")
    for operation in inventory_ops:
        if not isinstance(operation, dict) or operation.get("op") not in INVENTORY_OPS:
            raise ProposalError("UNKNOWN_INVENTORY_OPERATION", f"unsupported inventory operation {operation!r}")
        if operation["op"] == "add_inventory_row":
            row = operation.get("row")
            result_id = row.get("result_id") if isinstance(row, dict) else None
        else:
            result_id = operation.get("result_id")
        if not isinstance(result_id, str) or not result_id:
            raise ProposalError("INVALID_INVENTORY_OPERATION", "inventory operation requires result_id")
        inventory_rows.add(result_id)
    return existing_nodes, new_nodes, inventory_rows


def validate_write_set(proposal: dict[str, Any], current: dict[str, Any]) -> None:
    current_by_id, _ = node_maps(current)
    actual_existing, actual_new, actual_inventory = actual_write_set(proposal, set(current_by_id))
    write_set = proposal.get("write_set")
    if not isinstance(write_set, dict):
        raise ProposalError("MISSING_WRITE_SET", "proposal.write_set is required")
    declared_existing = write_set.get("existing_nodes", {})
    declared_new = write_set.get("new_node_ids", [])
    declared_inventory = write_set.get("inventory_rows", {})
    if not isinstance(declared_existing, dict) or not isinstance(declared_new, list):
        raise ProposalError("INVALID_WRITE_SET", "write_set existing_nodes/new_node_ids have invalid types")
    if not isinstance(declared_inventory, dict):
        raise ProposalError("INVALID_WRITE_SET", "write_set.inventory_rows must be an object")
    if set(declared_existing) != actual_existing:
        raise ProposalError(
            "WRITE_SET_MISMATCH",
            "declared existing node write set does not match operations",
            declared=sorted(declared_existing),
            actual=sorted(actual_existing),
        )
    if set(declared_new) != actual_new:
        raise ProposalError(
            "WRITE_SET_MISMATCH",
            "declared new node IDs do not match operations",
            declared=sorted(declared_new),
            actual=sorted(actual_new),
        )
    if set(declared_inventory) != actual_inventory:
        raise ProposalError(
            "WRITE_SET_MISMATCH",
            "declared inventory row write set does not match inventory operations",
            declared=sorted(declared_inventory),
            actual=sorted(actual_inventory),
        )


def apply_blueprint_operations(
    current: dict[str, Any], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    candidate = json.loads(json.dumps(current, ensure_ascii=False))
    nodes = candidate["nodes"]
    edges = candidate["edges"]
    by_id = {node["id"]: node for node in nodes}
    for operation in operations:
        op = operation.get("op")
        if op == "add_node":
            node = json.loads(json.dumps(operation["node"], ensure_ascii=False))
            node_id = node["id"]
            if node_id in by_id:
                raise ProposalError("NEW_NODE_ID_OCCUPIED", f"new node ID {node_id} already exists", node_id=node_id)
            nodes.append(node)
            by_id[node_id] = node
        elif op == "update_node":
            node_id = operation["node_id"]
            if node_id not in by_id:
                raise ProposalError("UNKNOWN_NODE", f"cannot update missing node {node_id}", node_id=node_id)
            changes = operation.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise ProposalError("INVALID_UPDATE_NODE", f"update_node {node_id} requires non-empty changes")
            forbidden = STRUCTURAL_REFERENCE_FIELDS & set(changes)
            if "id" in changes:
                forbidden.add("id")
            if forbidden:
                raise ProposalError(
                    "DEPENDENCY_UPDATE_REQUIRES_EDGE_OPERATION",
                    f"update_node cannot change {sorted(forbidden)}; use add_edge/remove_edge",
                    node_id=node_id,
                )
            by_id[node_id].update(json.loads(json.dumps(changes, ensure_ascii=False)))
        elif op == "add_edge":
            source = operation.get("source")
            target = operation.get("target")
            role = normalize_role(operation.get("role"))
            if source not in by_id or target not in by_id:
                raise ProposalError(
                    "UNKNOWN_EDGE_ENDPOINT",
                    f"edge {source!r} -> {target!r} has an unknown endpoint",
                    edge={"source": source, "target": target},
                )
            canonical_edge = {
                "source": source,
                "target": target,
                "role": CANONICAL_EDGE_ROLE_BY_FIELD[role],
            }
            existing_edges = [
                edge for edge in edges if edge_endpoints(edge) == (source, target)
            ]
            if existing_edges:
                existing = existing_edges[0]
                if len(existing_edges) > 1:
                    raise ProposalError(
                        "DUPLICATE_EDGE",
                        f"multiple canonical edges exist for {source!r} -> {target!r}",
                    )
                if isinstance(existing, dict) and existing.get("role") is not None:
                    existing_field = normalize_role(existing.get("role"))
                    if existing_field != role:
                        raise ProposalError(
                            "EDGE_ROLE_CONFLICT",
                            f"edge {source!r} -> {target!r} already has role "
                            f"{existing.get('role')!r}, not {canonical_edge['role']!r}",
                        )
                replace_endpoint_edge(edges, source, target, canonical_edge)
            else:
                edges.append(canonical_edge)
            refs = by_id[target].setdefault(role, [])
            if not isinstance(refs, list):
                raise ProposalError("INVALID_TYPED_INPUT", f"{target}.{role} must be a list", node_id=target)
            if source not in refs:
                refs.append(source)
        elif op == "remove_edge":
            source = operation.get("source")
            target = operation.get("target")
            if source not in by_id or target not in by_id:
                raise ProposalError("UNKNOWN_EDGE_ENDPOINT", f"edge {source!r} -> {target!r} has an unknown endpoint")
            roles = [normalize_role(operation["role"])] if operation.get("role") is not None else [
                field for field in DEPENDENCY_FIELDS if source in by_id[target].get(field, [])
            ]
            for role in roles:
                refs = by_id[target].get(role, [])
                if source in refs:
                    refs.remove(source)
            remaining_roles = sorted(
                field
                for field in DEPENDENCY_FIELDS
                if source in by_id[target].get(field, [])
            )
            if not remaining_roles:
                replace_endpoint_edge(edges, source, target, None)
            elif len(remaining_roles) == 1:
                remaining = remaining_roles[0]
                replace_endpoint_edge(
                    edges,
                    source,
                    target,
                    {
                        "source": source,
                        "target": target,
                        "role": CANONICAL_EDGE_ROLE_BY_FIELD[remaining],
                    },
                )
            else:
                # A legacy pair is the only lossless representation of one endpoint
                # pair serving several dependency fields. New v2.2 operations reject
                # this ambiguity when adding a role.
                replace_endpoint_edge(edges, source, target, [source, target])
        else:
            raise ProposalError("UNKNOWN_OPERATION", f"unsupported operation {op!r}")
    return candidate


def apply_inventory_operations(
    fieldnames: list[str], rows: list[dict[str, str]], operations: list[dict[str, Any]]
) -> list[dict[str, str]]:
    candidate = [dict(row) for row in rows]
    by_result = {row.get("result_id", ""): row for row in candidate}
    for operation in operations:
        op = operation["op"]
        if op == "add_inventory_row":
            supplied = operation.get("row")
            if not isinstance(supplied, dict):
                raise ProposalError("INVALID_INVENTORY_ROW", "add_inventory_row requires row")
            result_id = supplied.get("result_id")
            if result_id in by_result:
                raise ProposalError(
                    "INVENTORY_ROW_CONFLICT",
                    f"inventory result_id {result_id!r} already exists",
                    result_id=result_id,
                )
            unknown = set(supplied) - set(fieldnames)
            if unknown:
                raise ProposalError("INVENTORY_COLUMNS", f"unknown inventory columns: {sorted(unknown)}")
            row = {field: str(supplied.get(field, "")) for field in fieldnames}
            candidate.append(row)
            by_result[result_id] = row
        elif op == "update_inventory_row":
            result_id = operation.get("result_id")
            if result_id not in by_result:
                raise ProposalError("UNKNOWN_INVENTORY_ROW", f"missing inventory row {result_id!r}")
            expected = operation.get("expected_row_hash")
            actual = semantic_row_hash(by_result[result_id])
            if not isinstance(expected, str) or expected != actual:
                raise ProposalError(
                    "INVENTORY_ROW_CONFLICT",
                    f"inventory row {result_id} changed since proposal creation",
                    result_id=result_id,
                    expected=expected,
                    actual=actual,
                )
            changes = operation.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise ProposalError("INVALID_INVENTORY_ROW", "update_inventory_row requires changes")
            if "result_id" in changes:
                raise ProposalError("INVENTORY_ID_IMMUTABLE", "result_id cannot be changed")
            unknown = set(changes) - set(fieldnames)
            if unknown:
                raise ProposalError("INVENTORY_COLUMNS", f"unknown inventory columns: {sorted(unknown)}")
            by_result[result_id].update({key: str(value) for key, value in changes.items()})
    return candidate


def incoming_closure(blueprint: dict[str, Any], targets: set[str]) -> set[str]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in blueprint.get("edges", []):
        if isinstance(edge, list) and len(edge) == 2:
            source, target = edge
        elif isinstance(edge, dict) and edge.get("source") and edge.get("target"):
            source, target = edge["source"], edge["target"]
        else:
            raise ProposalError("INVALID_EDGE", f"invalid edge {edge!r}")
        reverse[target].add(source)
    visited: set[str] = set()
    stack = list(targets)
    while stack:
        node_id = stack.pop()
        for source in reverse.get(node_id, set()):
            if source not in visited:
                visited.add(source)
                stack.append(source)
    return visited


def validate_read_set(
    proposal: dict[str, Any], current: dict[str, Any], candidate: dict[str, Any]
) -> None:
    current_by_id, _ = node_maps(current)
    writes, new_nodes, _ = actual_write_set(proposal, set(current_by_id))
    affected = writes | new_nodes
    actual = incoming_closure(candidate, affected) - writes - new_nodes
    declared = proposal.get("read_set", {}).get("upstream_nodes")
    if not isinstance(declared, dict):
        raise ProposalError("MISSING_READ_SET", "read_set.upstream_nodes must be an object")
    if set(declared) != actual:
        raise ProposalError(
            "READ_SET_MISMATCH",
            "declared upstream closure does not match the candidate dependency graph",
            declared=sorted(declared),
            actual=sorted(actual),
        )


def check_expected_hashes(
    proposal: dict[str, Any], current: dict[str, Any], inventory_rows: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hashes = semantic_hashes(current)
    write_conflicts: list[dict[str, Any]] = []
    stale_upstream: list[dict[str, Any]] = []
    write_nodes = proposal.get("write_set", {}).get("existing_nodes", {})
    read_nodes = proposal.get("read_set", {}).get("upstream_nodes", {})
    for node_id, expected in write_nodes.items():
        actual = hashes.get(node_id)
        if actual != expected:
            write_conflicts.append(
                {"code": "WRITE_CONFLICT", "message": f"write target {node_id} changed", "node_id": node_id, "expected": expected, "actual": actual}
            )
    for node_id, expected in read_nodes.items():
        actual = hashes.get(node_id)
        if actual != expected:
            stale_upstream.append(
                {"code": "STALE_UPSTREAM", "message": f"upstream node {node_id} changed", "node_id": node_id, "expected": expected, "actual": actual}
            )
    row_map = {row.get("result_id", ""): row for row in inventory_rows}
    for result_id, expected in proposal.get("write_set", {}).get("inventory_rows", {}).items():
        actual = semantic_row_hash(row_map[result_id]) if result_id in row_map else None
        if expected is None:
            if actual is not None:
                write_conflicts.append(
                    {"code": "INVENTORY_ROW_CONFLICT", "message": f"new inventory result_id {result_id} is occupied", "result_id": result_id, "actual": actual}
                )
        elif actual != expected:
            write_conflicts.append(
                {"code": "INVENTORY_ROW_CONFLICT", "message": f"inventory row {result_id} changed", "result_id": result_id, "expected": expected, "actual": actual}
            )
    return write_conflicts, stale_upstream


def check_protection(
    before: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    before_by_id, before_incoming = node_maps(before)
    candidate_by_id, candidate_incoming = node_maps(candidate)
    reasons = []
    for node_id, node in before_by_id.items():
        if not is_protected_node(node, policy):
            continue
        new_node = candidate_by_id.get(node_id)
        if new_node is None:
            reasons.append({"code": "PROTECTED_NODE", "message": f"protected node {node_id} was deleted", "node_id": node_id})
            continue
        before_hash = semantic_node_hash(node, before_incoming.get(node_id, set()))
        after_hash = semantic_node_hash(new_node, candidate_incoming.get(node_id, set()))
        if before_hash != after_hash:
            math_claim_types = {
                "problem_hypothesis",
                "external_mathematical_result",
                "mathematical_claim",
                "verified_counterexample",
            }
            if node.get("epistemic_type") in math_claim_types:
                before_without_proofs = {
                    key: value for key, value in node.items() if key != "inference_inputs"
                }
                after_without_proofs = {
                    key: value for key, value in new_node.items() if key != "inference_inputs"
                }
                before_proofs = set(node.get("inference_inputs", []))
                after_proofs = set(new_node.get("inference_inputs", []))
                added_proofs = after_proofs - before_proofs
                only_adds_alternative_proofs = (
                    before_without_proofs == after_without_proofs
                    and before_proofs.issubset(after_proofs)
                    and candidate_incoming.get(node_id, set())
                    == before_incoming.get(node_id, set()) | added_proofs
                    and all(
                        candidate_by_id.get(proof_id, {}).get("epistemic_type")
                        == "mathematical_inference"
                        and candidate_by_id[proof_id].get("conclusion") == node_id
                        for proof_id in added_proofs
                    )
                )
                if only_adds_alternative_proofs:
                    continue
            reasons.append(
                {"code": "PROTECTED_NODE", "message": f"protected node {node_id} or its incoming dependencies changed", "node_id": node_id, "expected": before_hash, "actual": after_hash}
            )
    return reasons


def check_manual_only(proposal: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    manual = set(config.get("manual_only_operations", []))
    reasons = []
    for operation in proposal.get("operations", []):
        if isinstance(operation, dict) and operation.get("op") in manual:
            reasons.append(
                {"code": "MANUAL_ONLY", "message": f"operation {operation.get('op')} requires manual processing", "operation": operation.get("op")}
            )
    return reasons


def check_artifact_refs(proposal: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    reasons = []
    evidence = proposal.get("review_evidence", {})
    for method_match in evidence.get("method_matches", []) if isinstance(evidence, dict) else []:
        for artifact in method_match.get("artifacts", []) if isinstance(method_match, dict) else []:
            raw_path = artifact.get("path") if isinstance(artifact, dict) else None
            if not raw_path:
                reasons.append({"code": "MISSING_ARTIFACT_PATH", "message": "method artifact path is missing"})
                continue
            path = Path(raw_path)
            resolved = path if path.is_absolute() else root / path
            if not resolved.exists():
                reasons.append({"code": "MISSING_ARTIFACT", "message": f"artifact does not exist: {raw_path}", "path": raw_path})
    return reasons


def check_review_evidence_structure(
    proposal: dict[str, Any], current: dict[str, Any], candidate: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    reasons = []
    current_ids = set(node_maps(current)[0])
    writes, new_nodes, _ = actual_write_set(proposal, current_ids)
    affected = writes | new_nodes
    candidate_by_id, _ = node_maps(candidate)
    evidence = proposal.get("review_evidence")
    if not isinstance(evidence, dict):
        return [{"code": "MISSING_REVIEW_EVIDENCE", "message": "review_evidence must be an object"}]
    logic = {item.get("node_id"): item for item in evidence.get("logic_justifications", []) if isinstance(item, dict)}
    methods = {item.get("node_id"): item for item in evidence.get("method_matches", []) if isinstance(item, dict)}
    sources = {item.get("node_id"): item for item in evidence.get("literature_sources", []) if isinstance(item, dict)}
    math_premises = {
        item.get("node_id"): item
        for item in evidence.get("math_premise_contracts", [])
        if isinstance(item, dict)
    }
    math_proofs = {
        item.get("node_id"): item
        for item in evidence.get("math_proof_justifications", [])
        if isinstance(item, dict)
    }
    math_refutations = {
        item.get("node_id"): item
        for item in evidence.get("math_refutations", [])
        if isinstance(item, dict)
    }
    math_research = {
        item.get("node_id"): item
        for item in evidence.get("math_research_state_records", [])
        if isinstance(item, dict)
    }
    assumption_policy = config.get("basic_assumption_policy", {})
    for node_id in sorted(affected):
        node = candidate_by_id.get(node_id)
        if node is None:
            continue
        epistemic_type = node.get("epistemic_type")
        if epistemic_type == "theory_from_assumptions":
            item = logic.get(node_id)
            if not item:
                reasons.append({"code": "MISSING_LOGIC_JUSTIFICATION", "message": f"T1 node {node_id} lacks logic_justification", "node_id": node_id})
            elif not isinstance(item.get("derivation_steps"), list) or not item["derivation_steps"]:
                reasons.append({"code": "MISSING_DERIVATION", "message": f"T1 node {node_id} lacks ordered derivation steps", "node_id": node_id})
            elif item.get("unstated_assumptions") != []:
                reasons.append({"code": "UNSTATED_ASSUMPTIONS", "message": f"T1 node {node_id} has unstated assumptions", "node_id": node_id})
        elif epistemic_type == "numerical_result":
            item = methods.get(node_id)
            required = {"method_node_ids", "measured_quantity", "estimator", "contracts", "artifacts", "match_explanation"}
            if not item:
                reasons.append({"code": "MISSING_METHOD_MATCH", "message": f"numerical result {node_id} lacks method_match", "node_id": node_id})
            else:
                missing = sorted(key for key in required if not item.get(key))
                if missing:
                    reasons.append({"code": "INCOMPLETE_METHOD_MATCH", "message": f"numerical result {node_id} method_match lacks {missing}", "node_id": node_id})
        elif epistemic_type == "basic_assumption":
            item = sources.get(node_id)
            literature = item.get("literature_sources", []) if item else []
            if not item or not item.get("consensus_explanation") or not isinstance(literature, list):
                reasons.append({"code": "ASSUMPTION_SOURCE", "message": f"basic assumption {node_id} lacks sources or consensus explanation", "node_id": node_id})
                continue
            complete = [
                source for source in literature
                if isinstance(source, dict)
                and source.get("source_type")
                and source.get("citation")
                and source.get("doi_isbn_or_stable_url")
                and source.get("locator")
                and source.get("supported_claim")
            ]
            authoritative = [source for source in complete if source["source_type"] in {"peer_reviewed_review", "standard_reference", "recognized_textbook"}]
            primary_ids = {
                source["doi_isbn_or_stable_url"]
                for source in complete
                if source["source_type"] == "peer_reviewed_primary"
            }
            if not authoritative and len(primary_ids) < 2:
                reasons.append({"code": "ASSUMPTION_SOURCE", "message": f"basic assumption {node_id} does not satisfy the configured source-set minimum", "node_id": node_id})
            if assumption_policy.get("require_exact_locator") and len(complete) != len(literature):
                reasons.append({"code": "ASSUMPTION_SOURCE", "message": f"basic assumption {node_id} has an incomplete citation or locator", "node_id": node_id})
        elif epistemic_type in {
            "problem_hypothesis",
            "external_mathematical_result",
        } or (epistemic_type == "definition_contract" and node.get("context_id") is not None):
            item = math_premises.get(node_id)
            required = {"premise_kind", "scope", "contract_explanation"}
            if not item:
                reasons.append(
                    {
                        "code": "MISSING_MATH_PREMISE_CONTRACT",
                        "message": f"mathematics premise {node_id} lacks a premise contract",
                        "node_id": node_id,
                    }
                )
            else:
                missing = sorted(key for key in required if not item.get(key))
                if missing:
                    reasons.append(
                        {
                            "code": "INCOMPLETE_MATH_PREMISE_CONTRACT",
                            "message": f"mathematics premise {node_id} lacks {missing}",
                            "node_id": node_id,
                        }
                    )
                if epistemic_type == "external_mathematical_result" and not item.get("source_verified"):
                    reasons.append(
                        {
                            "code": "MATH_SOURCE_NOT_VERIFIED",
                            "message": f"external theorem {node_id} was not source-verified",
                            "node_id": node_id,
                        }
                    )
        elif epistemic_type == "mathematical_inference":
            proof_status = node.get("proof_status")
            if proof_status == "proved":
                item = math_proofs.get(node_id)
                required = {"ordered_steps", "boundary_cases", "external_results", "proof_package_sha256"}
                if not item:
                    reasons.append(
                        {
                            "code": "MISSING_MATH_PROOF_JUSTIFICATION",
                            "message": f"proved inference {node_id} lacks math proof justification",
                            "node_id": node_id,
                        }
                    )
                else:
                    missing = sorted(
                        key
                        for key in required
                        if key not in item or item.get(key) is None or item.get(key) == ""
                    )
                    if missing:
                        reasons.append(
                            {
                                "code": "INCOMPLETE_MATH_PROOF_JUSTIFICATION",
                                "message": f"proved inference {node_id} lacks {missing}",
                                "node_id": node_id,
                            }
                        )
                    if not isinstance(item.get("ordered_steps"), list) or not item.get("ordered_steps"):
                        reasons.append(
                            {
                                "code": "MISSING_MATH_DERIVATION",
                                "message": f"proved inference {node_id} lacks ordered proof steps",
                                "node_id": node_id,
                            }
                        )
                    if item.get("unresolved_obligations") != []:
                        reasons.append(
                            {
                                "code": "OPEN_MATH_OBLIGATIONS",
                                "message": f"proved inference {node_id} still has unresolved obligations",
                                "node_id": node_id,
                            }
                        )
                    expected = node.get("proof_package", {}).get("sha256")
                    if item.get("proof_package_sha256") != expected:
                        reasons.append(
                            {
                                "code": "MATH_PROOF_PACKAGE_MISMATCH",
                                "message": f"proof evidence for {node_id} does not bind its proof package",
                                "node_id": node_id,
                                "expected": expected,
                                "actual": item.get("proof_package_sha256"),
                            }
                        )
            elif proof_status == "refuted":
                item = math_refutations.get(node_id)
                expected = node.get("refutation_package", {}).get("sha256")
                if not item or not item.get("refutation_type") or not item.get("verified_conditions"):
                    reasons.append(
                        {
                            "code": "MISSING_MATH_REFUTATION",
                            "message": f"refuted inference {node_id} lacks a complete refutation record",
                            "node_id": node_id,
                        }
                    )
                elif item.get("refutation_package_sha256") != expected:
                    reasons.append(
                        {
                            "code": "MATH_REFUTATION_PACKAGE_MISMATCH",
                            "message": f"refutation evidence for {node_id} does not bind its package",
                            "node_id": node_id,
                            "expected": expected,
                            "actual": item.get("refutation_package_sha256"),
                        }
                    )
            else:
                item = math_research.get(node_id)
                if not item or not item.get("record_kind") or not item.get("status_justification"):
                    reasons.append(
                        {
                            "code": "MISSING_MATH_RESEARCH_STATE",
                            "message": f"unproved inference {node_id} lacks a research-state record",
                            "node_id": node_id,
                        }
                    )
        elif epistemic_type == "verified_counterexample":
            item = math_refutations.get(node_id)
            expected = node.get("certificate", {}).get("sha256")
            if not item or not item.get("verified_conditions"):
                reasons.append(
                    {
                        "code": "MISSING_MATH_REFUTATION",
                        "message": f"verified counterexample {node_id} lacks a refutation record",
                        "node_id": node_id,
                    }
                )
            elif item.get("refutation_package_sha256") != expected:
                reasons.append(
                    {
                        "code": "MATH_REFUTATION_PACKAGE_MISMATCH",
                        "message": f"counterexample evidence for {node_id} does not bind its certificate",
                        "node_id": node_id,
                        "expected": expected,
                        "actual": item.get("refutation_package_sha256"),
                    }
                )
        elif epistemic_type == "mathematical_claim" and node.get("truth_status") == "refuted":
            item = math_refutations.get(node_id)
            if (
                not item
                or not item.get("refutation_type")
                or not item.get("verified_conditions")
                or not item.get("witness_node_ids")
            ):
                reasons.append(
                    {
                        "code": "MISSING_MATH_REFUTATION",
                        "message": f"refuted claim {node_id} lacks verified witness evidence",
                        "node_id": node_id,
                    }
                )
            else:
                declared_witnesses = set(item.get("witness_node_ids", []))
                canonical_witnesses = set(node.get("refutation_inputs", []))
                if node.get("negation_claim"):
                    canonical_witnesses.add(node["negation_claim"])
                if not declared_witnesses or not declared_witnesses.issubset(canonical_witnesses):
                    reasons.append(
                        {
                            "code": "MATH_REFUTATION_WITNESS_MISMATCH",
                            "message": f"refutation evidence for {node_id} does not bind canonical witnesses",
                            "node_id": node_id,
                            "expected": sorted(canonical_witnesses),
                            "actual": sorted(declared_witnesses),
                        }
                    )
        elif epistemic_type in {
            "research_goal",
            "proof_obligation",
            "research_attempt",
        } or (
            epistemic_type == "mathematical_claim"
            and node.get("truth_status") in {"open", "candidate_supported", "target", "contested"}
        ):
            item = math_research.get(node_id)
            if not item or not item.get("record_kind") or not item.get("status_justification"):
                reasons.append(
                    {
                        "code": "MISSING_MATH_RESEARCH_STATE",
                        "message": f"mathematics research node {node_id} lacks a research-state record",
                        "node_id": node_id,
                    }
                )
    return reasons


def run_validator(blueprint: Path, inventory: Path, root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(root / "tools" / "validate_blueprint.py"),
        "--blueprint",
        str(blueprint),
        "--inventory",
        str(inventory),
        "--artifact-root",
        str(root),
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
    output: Any = completed.stdout.strip()
    if output:
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            pass
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "output": output,
        "stderr": completed.stderr.strip(),
    }


def write_candidate_files(
    directory: Path,
    blueprint: dict[str, Any],
    inventory_fields: list[str],
    inventory_rows: list[dict[str, str]],
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    blueprint_path = directory / "blueprint.json"
    inventory_path = directory / "evidence_inventory.csv"
    atomic_write_json(blueprint_path, blueprint)
    write_inventory(inventory_path, inventory_fields, inventory_rows)
    return blueprint_path, inventory_path


def build_candidate(
    proposal: dict[str, Any], current: dict[str, Any], inventory_path: Path
) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    validate_write_set(proposal, current)
    blueprint_ops, inventory_ops = split_operations(proposal)
    fields, rows = read_inventory(inventory_path)
    candidate = apply_blueprint_operations(current, blueprint_ops)
    candidate_rows = apply_inventory_operations(fields, rows, inventory_ops)
    validate_read_set(proposal, current, candidate)
    return candidate, fields, candidate_rows


def proposal_contract_reasons(
    proposal: dict[str, Any], current: dict[str, Any], inventory_path: Path, config: dict[str, Any]
) -> list[dict[str, Any]]:
    reasons = []
    required = {
        "schema_version",
        "submission_id",
        "author_agent_id",
        "created_at",
        "base_blueprint_hash",
        "base_inventory_hash",
        "operations",
        "write_set",
        "read_set",
    }
    missing = sorted(required - set(proposal))
    if missing:
        reasons.append({"code": "PROPOSAL_CONTRACT", "message": f"proposal is missing fields: {missing}"})
    if proposal.get("schema_version") != SCHEMA_VERSION:
        reasons.append({"code": "SCHEMA_VERSION", "message": f"proposal.schema_version must be {SCHEMA_VERSION}"})
    reasons.extend(check_manual_only(proposal, config))
    candidate = None
    try:
        validate_write_set(proposal, current)
        blueprint_ops, inventory_ops = split_operations(proposal)
        candidate = apply_blueprint_operations(current, blueprint_ops)
        reasons.extend(check_protection(current, candidate, config.get("protected_node_policy", {})))
        reasons.extend(check_review_evidence_structure(proposal, current, candidate, config))
        try:
            validate_read_set(proposal, current, candidate)
        except ProposalError as exc:
            reasons.append(exc.reason)
        try:
            fields, rows = read_inventory(inventory_path)
            apply_inventory_operations(fields, rows, inventory_ops)
        except ProposalError as exc:
            reasons.append(exc.reason)
    except ProposalError as exc:
        reasons.append(exc.reason)
    return reasons


def validate_submission(root: Path, submission: Path, actor_agent_id: str) -> dict[str, Any]:
    proposal_path = submission / "proposal.json"
    if not proposal_path.is_file():
        raise ProposalError("MISSING_PROPOSAL", f"missing proposal: {proposal_path}")
    proposal, proposal_hash = load_json_and_hash(proposal_path)
    validation_path = submission / "validation.json"
    if validation_path.exists():
        existing = load_json(validation_path)
        if existing.get("proposal_hash") != proposal_hash:
            raise ProposalError("IMMUTABLE_CONFLICT", "existing validation.json binds a different proposal hash")
        append_event(
            root,
            event="validation",
            result="valid" if existing.get("valid") else "rejected",
            agent_id=actor_agent_id,
            submission_id=proposal.get("submission_id", submission.name),
            proposal_hash=proposal_hash,
            reasons=existing.get("feedback", {}).get("reasons", []),
            details={"existing_report": True, "validation_path": str(validation_path)},
        )
        return existing

    config = load_json(root / ".blueprint" / "config.json")
    blueprint_path = root / config.get("canonical_blueprint", "blueprint.json")
    inventory_path = root / config.get("evidence_inventory", "evidence_inventory.csv")
    current = load_json(blueprint_path)
    reasons = proposal_contract_reasons(proposal, current, inventory_path, config)
    if proposal.get("submission_id") != submission.name:
        reasons.append({"code": "SUBMISSION_ID_MISMATCH", "message": "proposal submission_id must equal its directory name"})
    if proposal.get("base_blueprint_hash") != sha256_file(blueprint_path):
        reasons.append({"code": "BASE_CHANGED", "message": "canonical Blueprint changed before proposal validation"})
    if proposal.get("base_inventory_hash") != sha256_file(inventory_path):
        reasons.append({"code": "BASE_INVENTORY_CHANGED", "message": "evidence inventory changed before proposal validation"})

    validator = {"passed": False, "output": None, "stderr": "candidate was not built"}
    candidate_hashes: dict[str, str | None] = {"blueprint": None, "evidence_inventory": None}
    if not reasons:
        try:
            candidate, fields, rows = build_candidate(proposal, current, inventory_path)
            reasons.extend(check_artifact_refs(proposal, root))
            with tempfile.TemporaryDirectory(prefix="validate-", dir=root / ".blueprint") as temp:
                candidate_blueprint, candidate_inventory = write_candidate_files(Path(temp), candidate, fields, rows)
                validator = run_validator(candidate_blueprint, candidate_inventory, root)
                candidate_hashes = {
                    "blueprint": sha256_file(candidate_blueprint),
                    "evidence_inventory": sha256_file(candidate_inventory),
                }
            if not validator["passed"]:
                reasons.append(
                    {"code": "BLUEPRINT_VALIDATION", "message": validator["stderr"] or "candidate validation failed"}
                )
        except ProposalError as exc:
            reasons.append(exc.reason)

    report = {
        "schema_version": SCHEMA_VERSION,
        "submission_id": proposal.get("submission_id", submission.name),
        "proposal_hash": proposal_hash,
        "base_blueprint_hash": proposal.get("base_blueprint_hash"),
        "base_inventory_hash": proposal.get("base_inventory_hash"),
        "validated_at": utc_now(),
        "validator_agent_id": actor_agent_id,
        "valid": not reasons and validator.get("passed") is True,
        "candidate_hashes": candidate_hashes,
        "protected_node_check": {
            "passed": not any(reason["code"] == "PROTECTED_NODE" for reason in reasons),
        },
        "proposal_contract_check": {
            "passed": not reasons,
            "errors": reasons,
        },
        "blueprint_validator": validator,
        "feedback": {
            "stage": "validation",
            "reasons": normalize_reasons(reasons),
            "required_actions": ["Create a new proposal that resolves every listed reason."] if reasons else [],
        },
    }
    if sha256_file(proposal_path) != proposal_hash:
        raise ProposalError("IMMUTABLE_FILE_CHANGED", "proposal.json changed during validation")
    atomic_write_json(validation_path, report, overwrite=False)
    append_event(
        root,
        event="validation",
        result="valid" if report["valid"] else "rejected",
        agent_id=actor_agent_id,
        submission_id=report["submission_id"],
        proposal_hash=proposal_hash,
        reasons=reasons,
        details={"validation_path": str(validation_path)},
    )
    return report


def review_reasons(review: dict[str, Any]) -> list[dict[str, Any]]:
    reasons = []
    for finding in review.get("findings", []):
        if not isinstance(finding, dict):
            continue
        reasons.append(
            {
                "code": finding.get("rule", "REVIEW_FINDING"),
                "message": finding.get("explanation", "Review did not provide an explanation"),
                "node_id": finding.get("node_id"),
                "edge": finding.get("edge"),
                "required_fix": finding.get("required_fix"),
            }
        )
    if not reasons and review.get("verdict") != "approve":
        reasons.append({"code": "REVIEW_REJECTED", "message": review.get("decision_summary") or "review did not approve proposal"})
    return reasons


def validation_contract_reasons(
    validation: dict[str, Any], proposal: dict[str, Any], proposal_hash: str
) -> list[dict[str, Any]]:
    reasons = []
    if validation.get("schema_version") != SCHEMA_VERSION:
        reasons.append({"code": "VALIDATION_CONTRACT", "message": f"validation schema_version must be {SCHEMA_VERSION}"})
    if validation.get("submission_id") != proposal.get("submission_id"):
        reasons.append({"code": "VALIDATION_CONTRACT", "message": "validation submission_id does not match proposal"})
    if validation.get("proposal_hash") != proposal_hash:
        reasons.append({"code": "VALIDATION_HASH_MISMATCH", "message": "validation does not bind the current proposal hash"})
    required_passes = {
        "protected_node_check": validation.get("protected_node_check", {}).get("passed"),
        "proposal_contract_check": validation.get("proposal_contract_check", {}).get("passed"),
        "blueprint_validator": validation.get("blueprint_validator", {}).get("passed"),
    }
    failed = sorted(name for name, passed in required_passes.items() if passed is not True)
    if validation.get("valid") is True and failed:
        reasons.append(
            {
                "code": "VALIDATION_CONTRACT",
                "message": f"validation.valid is true but required checks are not passing: {failed}",
            }
        )
    candidate_hashes = validation.get("candidate_hashes")
    if validation.get("valid") is True and (
        not isinstance(candidate_hashes, dict)
        or not candidate_hashes.get("blueprint")
        or not candidate_hashes.get("evidence_inventory")
    ):
        reasons.append({"code": "VALIDATION_CONTRACT", "message": "passing validation lacks candidate file hashes"})
    return reasons


def review_contract_reasons(
    review: dict[str, Any], proposal: dict[str, Any], proposal_hash: str, validation_hash: str
) -> list[dict[str, Any]]:
    reasons = []
    required = {
        "schema_version",
        "review_id",
        "submission_id",
        "proposal_hash",
        "validation_hash",
        "reviewer_agent_id",
        "reviewed_at",
        "verdict",
        "decision_summary",
        "protected_node_check",
        "basic_assumption_checks",
        "logical_relation_checks",
        "method_result_checks",
        "math_premise_checks",
        "math_proof_checks",
        "math_refutation_checks",
        "math_research_state_checks",
        "graph_checks",
        "findings",
        "required_actions",
    }
    missing = sorted(required - set(review))
    if missing:
        reasons.append({"code": "REVIEW_CONTRACT", "message": f"review is missing fields: {missing}"})
    if review.get("schema_version") != SCHEMA_VERSION:
        reasons.append({"code": "REVIEW_CONTRACT", "message": f"review schema_version must be {SCHEMA_VERSION}"})
    if review.get("submission_id") != proposal.get("submission_id"):
        reasons.append({"code": "REVIEW_CONTRACT", "message": "review submission_id does not match proposal"})
    if review.get("proposal_hash") != proposal_hash:
        reasons.append({"code": "REVIEW_HASH_MISMATCH", "message": "review does not bind the current proposal hash"})
    if review.get("validation_hash") != validation_hash:
        reasons.append({"code": "VALIDATION_BINDING_MISMATCH", "message": "review does not bind the current validation hash"})
    if review.get("verdict") not in {"approve", "changes_requested", "reject"}:
        reasons.append({"code": "REVIEW_CONTRACT", "message": "review verdict is invalid"})
    list_fields = (
        "basic_assumption_checks",
        "logical_relation_checks",
        "method_result_checks",
        "math_premise_checks",
        "math_proof_checks",
        "math_refutation_checks",
        "math_research_state_checks",
        "findings",
        "required_actions",
    )
    for field in list_fields:
        if field in review and not isinstance(review[field], list):
            reasons.append({"code": "REVIEW_CONTRACT", "message": f"review.{field} must be a list"})

    proposal_evidence = proposal.get("review_evidence", {})
    coverage_pairs = (
        ("math_premise_contracts", "math_premise_checks", "valid"),
        ("math_proof_justifications", "math_proof_checks", "valid"),
        ("math_refutations", "math_refutation_checks", "valid"),
        ("math_research_state_records", "math_research_state_checks", "accurate"),
    )
    if isinstance(proposal_evidence, dict):
        for evidence_field, review_field, passing_result in coverage_pairs:
            required_ids = {
                item.get("node_id")
                for item in proposal_evidence.get(evidence_field, [])
                if isinstance(item, dict) and item.get("node_id")
            }
            checks = {
                item.get("node_id"): item
                for item in review.get(review_field, [])
                if isinstance(item, dict) and item.get("node_id")
            }
            missing_ids = sorted(required_ids - set(checks))
            if missing_ids:
                reasons.append(
                    {
                        "code": "MATH_REVIEW_COVERAGE",
                        "message": f"review.{review_field} does not cover {missing_ids}",
                        "node_ids": missing_ids,
                    }
                )
            if review.get("verdict") == "approve":
                failing = sorted(
                    node_id
                    for node_id in required_ids & set(checks)
                    if checks[node_id].get("result") != passing_result
                )
                if failing:
                    reasons.append(
                        {
                            "code": "MATH_REVIEW_NOT_PASSING",
                            "message": f"approved review has non-passing {review_field} entries for {failing}",
                            "node_ids": failing,
                        }
                    )

    if review.get("verdict") == "approve":
        proof_evidence = {
            item.get("node_id"): item
            for item in proposal_evidence.get("math_proof_justifications", [])
            if isinstance(item, dict) and item.get("node_id")
        } if isinstance(proposal_evidence, dict) else {}
        for check in review.get("math_proof_checks", []):
            if not isinstance(check, dict):
                continue
            node_id = check.get("node_id")
            expected_package = proof_evidence.get(node_id, {}).get(
                "proof_package_sha256"
            )
            if not expected_package or check.get("proof_package_sha256") != expected_package:
                reasons.append(
                    {
                        "code": "MATH_PROOF_REVIEW_BINDING",
                        "message": f"proof check for {node_id} does not bind the reviewed proof package",
                        "node_id": node_id,
                        "expected": expected_package,
                        "actual": check.get("proof_package_sha256"),
                    }
                )
            missing_audits = [
                audit
                for audit in (
                    "definition_audit",
                    "logic_audit",
                    "boundary_audit",
                    "adversarial_audit",
                )
                if check.get(audit, {}).get("passed") is not True
            ]
            if missing_audits:
                reasons.append(
                    {
                        "code": "MATH_PROOF_AUDIT",
                        "message": f"proof check for {check.get('node_id')} lacks passing audits {missing_audits}",
                        "node_id": check.get("node_id"),
                    }
                )
    if review.get("verdict") == "approve":
        if review.get("protected_node_check", {}).get("passed") is not True:
            reasons.append({"code": "REVIEW_CONTRACT", "message": "approved review lacks a passing protected-node check"})
        graph_checks = review.get("graph_checks")
        if not isinstance(graph_checks, dict):
            reasons.append({"code": "REVIEW_CONTRACT", "message": "approved review lacks graph checks"})
        elif any(graph_checks.get(field) for field in ("unknown_references", "cycles", "invalid_typed_edges")):
            reasons.append({"code": "REVIEW_CONTRACT", "message": "approved review contains blocking graph findings"})
        if any(
            isinstance(finding, dict) and finding.get("severity") in {"blocking", "major"}
            for finding in review.get("findings", [])
        ):
            reasons.append({"code": "REVIEW_CONTRACT", "message": "approved review still contains blocking or major findings"})
    elif not review.get("findings"):
        reasons.append({"code": "REVIEW_CONTRACT", "message": "non-approved review must contain actionable findings"})
    return reasons


def immutable_receipt(
    path: Path,
    *,
    proposal: dict[str, Any],
    proposal_hash: str,
    validation_hash: str | None,
    review_hash: str | None,
    status: str,
    integrator_agent_id: str,
    base_blueprint_hash: str | None,
    result_blueprint_hash: str | None,
    base_inventory_hash: str | None,
    result_inventory_hash: str | None,
    reasons: list[dict[str, Any]],
    retryable: bool = False,
) -> dict[str, Any]:
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "submission_id": proposal.get("submission_id", path.parent.name),
        "proposal_hash": proposal_hash,
        "validation_hash": validation_hash,
        "review_hash": review_hash,
        "status": status,
        "base_blueprint_hash": proposal.get("base_blueprint_hash"),
        "premerge_blueprint_hash": base_blueprint_hash,
        "result_blueprint_hash": result_blueprint_hash,
        "base_inventory_hash": proposal.get("base_inventory_hash"),
        "premerge_inventory_hash": base_inventory_hash,
        "result_inventory_hash": result_inventory_hash,
        "integrator_agent_id": integrator_agent_id,
        "received_at": utc_now(),
        "feedback": {
            "stage": "integration",
            "retryable": retryable,
            "reasons": normalize_reasons(reasons),
        },
    }
    atomic_write_json(path, receipt, overwrite=False)
    return receipt


def replace_from(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def complete_recovered_receipt(
    root: Path, state: dict[str, Any], integrator_agent_id: str
) -> None:
    submission_id = state.get("submission_id")
    if not isinstance(submission_id, str):
        return
    config = load_json(root / ".blueprint" / "config.json")
    submission = root / config.get("submissions_dir", "submissions") / submission_id
    receipt_path = submission / "receipt.json"
    if receipt_path.exists():
        return
    proposal_path = submission / "proposal.json"
    validation_path = submission / "validation.json"
    review_path = submission / "review.json"
    if not all(path.is_file() for path in (proposal_path, validation_path, review_path)):
        return
    proposal, proposal_hash = load_json_and_hash(proposal_path)
    if state.get("proposal_hash") != proposal_hash:
        raise RuntimeError(
            f"cannot complete receipt for {submission_id}: proposal hash differs from transaction"
        )
    before_hashes = state.get("before_hashes", {})
    candidate_hashes = state.get("candidate_hashes", {})
    immutable_receipt(
        receipt_path,
        proposal=proposal,
        proposal_hash=proposal_hash,
        validation_hash=sha256_file(validation_path),
        review_hash=sha256_file(review_path),
        status="merged",
        integrator_agent_id=integrator_agent_id,
        base_blueprint_hash=before_hashes.get("blueprint"),
        result_blueprint_hash=candidate_hashes.get("blueprint"),
        base_inventory_hash=before_hashes.get("evidence_inventory"),
        result_inventory_hash=candidate_hashes.get("evidence_inventory"),
        reasons=[],
    )


def recover_transactions(root: Path, config: dict[str, Any], integrator_agent_id: str) -> None:
    transactions = root / config.get("transactions_dir", ".blueprint/transactions")
    transactions.mkdir(parents=True, exist_ok=True)
    canonical_blueprint = root / config.get("canonical_blueprint", "blueprint.json")
    canonical_inventory = root / config.get("evidence_inventory", "evidence_inventory.csv")
    for state_path in sorted(transactions.glob("*/state.json")):
        state = load_json(state_path)
        phase = state.get("phase")
        if phase == "merged":
            complete_recovered_receipt(root, state, integrator_agent_id)
            continue
        if phase not in {"prepared", "committing"}:
            continue
        transaction = state_path.parent
        before_blueprint = transaction / "before" / "blueprint.json"
        before_inventory = transaction / "before" / "evidence_inventory.csv"
        candidate_blueprint = transaction / "candidate" / "blueprint.json"
        candidate_inventory = transaction / "candidate" / "evidence_inventory.csv"
        current_hashes = (sha256_file(canonical_blueprint), sha256_file(canonical_inventory))
        before_hashes = (sha256_file(before_blueprint), sha256_file(before_inventory))
        candidate_hashes = (sha256_file(candidate_blueprint), sha256_file(candidate_inventory))
        if phase == "prepared" and current_hashes == before_hashes:
            state["phase"] = "aborted"
            state["recovered_at"] = utc_now()
            atomic_write_json(state_path, state)
            continue
        if current_hashes[0] not in {before_hashes[0], candidate_hashes[0]} or current_hashes[1] not in {before_hashes[1], candidate_hashes[1]}:
            raise RuntimeError(f"cannot safely recover transaction {transaction.name}: canonical hashes are unexpected")
        state["phase"] = "committing"
        atomic_write_json(state_path, state)
        if current_hashes[0] != candidate_hashes[0]:
            replace_from(candidate_blueprint, canonical_blueprint)
        if current_hashes[1] != candidate_hashes[1]:
            replace_from(candidate_inventory, canonical_inventory)
        validator = run_validator(canonical_blueprint, canonical_inventory, root)
        if not validator["passed"]:
            replace_from(before_blueprint, canonical_blueprint)
            replace_from(before_inventory, canonical_inventory)
            state["phase"] = "rolled_back"
            state["recovered_at"] = utc_now()
            state["recovery_error"] = validator
            atomic_write_json(state_path, state)
            raise RuntimeError(f"recovered transaction {transaction.name} failed validation and was rolled back")
        state["phase"] = "merged"
        state["recovered_at"] = utc_now()
        atomic_write_json(state_path, state)
        complete_recovered_receipt(root, state, integrator_agent_id)
        append_event(
            root,
            event="recovery",
            result="merged",
            agent_id=integrator_agent_id,
            submission_id=state.get("submission_id"),
            proposal_hash=state.get("proposal_hash"),
            details={"transaction": transaction.name},
        )


def receive_submission(root: Path, submission: Path, integrator_agent_id: str) -> dict[str, Any]:
    config = load_json(root / ".blueprint" / "config.json")
    receipt_path = submission / "receipt.json"
    if receipt_path.exists():
        receipt = load_json(receipt_path)
        append_event(
            root,
            event="integration",
            result=receipt.get("status", "unknown"),
            agent_id=integrator_agent_id,
            submission_id=receipt.get("submission_id", submission.name),
            proposal_hash=receipt.get("proposal_hash"),
            reasons=receipt.get("feedback", {}).get("reasons", []),
            details={"existing_receipt": True, "receipt_path": str(receipt_path)},
        )
        return receipt
    proposal_path = submission / "proposal.json"
    if not proposal_path.is_file():
        raise ProposalError("MISSING_PROPOSAL", f"missing proposal: {proposal_path}")
    proposal = load_json(proposal_path)
    proposal_hash = sha256_file(proposal_path)
    validation_path = submission / "validation.json"
    review_path = submission / "review.json"

    lock_path = root / config.get("merge_lock", ".blueprint/merge.lock")
    try:
        lock = FileLock(lock_path, timeout=0.0)
        lock.__enter__()
    except TimeoutError:
        reasons = [{"code": "MERGE_BUSY", "message": "another receiver holds the merge lock"}]
        append_event(
            root,
            event="integration",
            result="busy",
            agent_id=integrator_agent_id,
            submission_id=proposal.get("submission_id", submission.name),
            proposal_hash=proposal_hash,
            reasons=reasons,
        )
        return {"status": "busy", "receipt": None, "feedback": {"stage": "integration", "retryable": True, "reasons": reasons}}

    try:
        recover_transactions(root, config, integrator_agent_id)
        if receipt_path.exists():
            receipt = load_json(receipt_path)
            append_event(
                root,
                event="integration",
                result=receipt.get("status", "unknown"),
                agent_id=integrator_agent_id,
                submission_id=receipt.get("submission_id", submission.name),
                proposal_hash=receipt.get("proposal_hash"),
                reasons=receipt.get("feedback", {}).get("reasons", []),
                details={"existing_receipt": True, "receipt_path": str(receipt_path)},
            )
            return receipt
        if not validation_path.is_file() or not review_path.is_file():
            missing = [name for name, path in (("validation.json", validation_path), ("review.json", review_path)) if not path.is_file()]
            reasons = [{"code": "MISSING_STAGE_OUTPUT", "message": f"missing required files: {missing}"}]
            append_event(
                root,
                event="integration",
                result="rejected",
                agent_id=integrator_agent_id,
                submission_id=proposal.get("submission_id", submission.name),
                proposal_hash=proposal_hash,
                reasons=reasons,
                details={"retryable": True},
            )
            return {"status": "rejected", "receipt": None, "feedback": {"stage": "integration", "retryable": True, "reasons": reasons}}

        validation, validation_hash = load_json_and_hash(validation_path)
        review, review_hash = load_json_and_hash(review_path)
        reasons = validation_contract_reasons(validation, proposal, proposal_hash)
        reasons.extend(review_contract_reasons(review, proposal, proposal_hash, validation_hash))
        if proposal.get("author_agent_id") == review.get("reviewer_agent_id"):
            reasons.append({"code": "REVIEWER_NOT_INDEPENDENT", "message": "author and reviewer Agent IDs must differ"})
        reasons.extend(check_manual_only(proposal, config))
        if not validation.get("valid"):
            reasons.extend(validation.get("feedback", {}).get("reasons", []))
        if review.get("verdict") != "approve":
            reasons.extend(review_reasons(review))
        if reasons:
            receipt = immutable_receipt(
                receipt_path,
                proposal=proposal,
                proposal_hash=proposal_hash,
                validation_hash=validation_hash,
                review_hash=review_hash,
                status="rejected",
                integrator_agent_id=integrator_agent_id,
                base_blueprint_hash=proposal.get("base_blueprint_hash"),
                result_blueprint_hash=None,
                base_inventory_hash=proposal.get("base_inventory_hash"),
                result_inventory_hash=None,
                reasons=reasons,
            )
            append_event(root, event="integration", result="rejected", agent_id=integrator_agent_id, submission_id=proposal.get("submission_id"), proposal_hash=proposal_hash, reasons=reasons, details={"receipt_path": str(receipt_path)})
            return receipt

        blueprint_path = root / config.get("canonical_blueprint", "blueprint.json")
        inventory_path = root / config.get("evidence_inventory", "evidence_inventory.csv")
        current = load_json(blueprint_path)
        inventory_fields, inventory_rows = read_inventory(inventory_path)
        write_conflicts, stale = check_expected_hashes(proposal, current, inventory_rows)
        current_ids = set(node_maps(current)[0])
        declared_new = set(proposal.get("write_set", {}).get("new_node_ids", []))
        for node_id in sorted(declared_new & current_ids):
            write_conflicts.append({"code": "NEW_NODE_ID_OCCUPIED", "message": f"new node ID {node_id} is occupied", "node_id": node_id})
        if write_conflicts or stale:
            status = "conflict" if write_conflicts else "stale_upstream"
            conflict_reasons = write_conflicts + stale
            receipt = immutable_receipt(
                receipt_path,
                proposal=proposal,
                proposal_hash=proposal_hash,
                validation_hash=validation_hash,
                review_hash=review_hash,
                status=status,
                integrator_agent_id=integrator_agent_id,
                base_blueprint_hash=sha256_file(blueprint_path),
                result_blueprint_hash=None,
                base_inventory_hash=sha256_file(inventory_path),
                result_inventory_hash=None,
                reasons=conflict_reasons,
            )
            append_event(root, event="integration", result=status, agent_id=integrator_agent_id, submission_id=proposal.get("submission_id"), proposal_hash=proposal_hash, reasons=conflict_reasons, details={"receipt_path": str(receipt_path)})
            return receipt

        try:
            candidate, inventory_fields, candidate_rows = build_candidate(proposal, current, inventory_path)
            candidate_reasons = check_protection(current, candidate, config.get("protected_node_policy", {}))
            candidate_reasons.extend(check_artifact_refs(proposal, root))
        except ProposalError as exc:
            candidate = current
            candidate_rows = inventory_rows
            candidate_reasons = [exc.reason]
        merge_id = f"merge-{utc_now().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        transaction = root / config.get("transactions_dir", ".blueprint/transactions") / merge_id
        before_dir = transaction / "before"
        candidate_dir = transaction / "candidate"
        before_dir.mkdir(parents=True, exist_ok=False)
        shutil.copy2(blueprint_path, before_dir / "blueprint.json")
        shutil.copy2(inventory_path, before_dir / "evidence_inventory.csv")
        candidate_blueprint, candidate_inventory = write_candidate_files(candidate_dir, candidate, inventory_fields, candidate_rows)
        validator = run_validator(candidate_blueprint, candidate_inventory, root)
        if not validator["passed"]:
            candidate_reasons.append({"code": "BLUEPRINT_VALIDATION", "message": validator["stderr"] or "candidate validation failed"})
        if candidate_reasons:
            state = {"schema_version": SCHEMA_VERSION, "merge_id": merge_id, "submission_id": proposal.get("submission_id"), "proposal_hash": proposal_hash, "phase": "aborted", "created_at": utc_now(), "reasons": candidate_reasons}
            atomic_write_json(transaction / "state.json", state)
            receipt = immutable_receipt(
                receipt_path,
                proposal=proposal,
                proposal_hash=proposal_hash,
                validation_hash=validation_hash,
                review_hash=review_hash,
                status="validation_failed",
                integrator_agent_id=integrator_agent_id,
                base_blueprint_hash=sha256_file(blueprint_path),
                result_blueprint_hash=None,
                base_inventory_hash=sha256_file(inventory_path),
                result_inventory_hash=None,
                reasons=candidate_reasons,
            )
            append_event(root, event="integration", result="validation_failed", agent_id=integrator_agent_id, submission_id=proposal.get("submission_id"), proposal_hash=proposal_hash, reasons=candidate_reasons, details={"transaction": merge_id, "receipt_path": str(receipt_path)})
            return receipt

        immutable_files = {
            proposal_path: proposal_hash,
            validation_path: validation_hash,
            review_path: review_hash,
        }
        changed_files = [path.name for path, expected in immutable_files.items() if sha256_file(path) != expected]
        if changed_files:
            tamper_reasons = [
                {
                    "code": "IMMUTABLE_FILE_CHANGED",
                    "message": f"immutable stage files changed during integration: {changed_files}",
                }
            ]
            append_event(
                root,
                event="integration",
                result="rejected",
                agent_id=integrator_agent_id,
                submission_id=proposal.get("submission_id"),
                proposal_hash=proposal_hash,
                reasons=tamper_reasons,
                details={"retryable": False},
            )
            atomic_write_json(
                transaction / "state.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "merge_id": merge_id,
                    "submission_id": proposal.get("submission_id"),
                    "proposal_hash": proposal_hash,
                    "phase": "aborted",
                    "created_at": utc_now(),
                    "reasons": tamper_reasons,
                },
            )
            return {
                "status": "rejected",
                "receipt": None,
                "feedback": {"stage": "integration", "retryable": False, "reasons": tamper_reasons},
            }

        state_path = transaction / "state.json"
        state = {
            "schema_version": SCHEMA_VERSION,
            "merge_id": merge_id,
            "submission_id": proposal.get("submission_id"),
            "proposal_hash": proposal_hash,
            "phase": "prepared",
            "created_at": utc_now(),
            "before_hashes": {"blueprint": sha256_file(blueprint_path), "evidence_inventory": sha256_file(inventory_path)},
            "candidate_hashes": {"blueprint": sha256_file(candidate_blueprint), "evidence_inventory": sha256_file(candidate_inventory)},
        }
        atomic_write_json(state_path, state)
        state["phase"] = "committing"
        atomic_write_json(state_path, state)
        replace_from(candidate_blueprint, blueprint_path)
        replace_from(candidate_inventory, inventory_path)
        live_validator = run_validator(blueprint_path, inventory_path, root)
        if not live_validator["passed"]:
            replace_from(before_dir / "blueprint.json", blueprint_path)
            replace_from(before_dir / "evidence_inventory.csv", inventory_path)
            state["phase"] = "rolled_back"
            state["error"] = live_validator
            atomic_write_json(state_path, state)
            failure = [{"code": "LIVE_VALIDATION_FAILED", "message": live_validator["stderr"] or "live validation failed; transaction rolled back"}]
            receipt = immutable_receipt(
                receipt_path,
                proposal=proposal,
                proposal_hash=proposal_hash,
                validation_hash=validation_hash,
                review_hash=review_hash,
                status="validation_failed",
                integrator_agent_id=integrator_agent_id,
                base_blueprint_hash=state["before_hashes"]["blueprint"],
                result_blueprint_hash=None,
                base_inventory_hash=state["before_hashes"]["evidence_inventory"],
                result_inventory_hash=None,
                reasons=failure,
            )
            append_event(root, event="integration", result="validation_failed", agent_id=integrator_agent_id, submission_id=proposal.get("submission_id"), proposal_hash=proposal_hash, reasons=failure, details={"transaction": merge_id, "rolled_back": True})
            return receipt

        state["phase"] = "merged"
        state["merged_at"] = utc_now()
        atomic_write_json(state_path, state)
        receipt = immutable_receipt(
            receipt_path,
            proposal=proposal,
            proposal_hash=proposal_hash,
            validation_hash=validation_hash,
            review_hash=review_hash,
            status="merged",
            integrator_agent_id=integrator_agent_id,
            base_blueprint_hash=state["before_hashes"]["blueprint"],
            result_blueprint_hash=sha256_file(blueprint_path),
            base_inventory_hash=state["before_hashes"]["evidence_inventory"],
            result_inventory_hash=sha256_file(inventory_path),
            reasons=[],
        )
        append_event(root, event="integration", result="merged", agent_id=integrator_agent_id, submission_id=proposal.get("submission_id"), proposal_hash=proposal_hash, details={"transaction": merge_id, "receipt_path": str(receipt_path)})
        return receipt
    finally:
        lock.__exit__(None, None, None)


def resolve_submission(root: Path, supplied: Path) -> Path:
    path = supplied if supplied.is_absolute() else root / supplied
    path = path.resolve()
    config = load_json(root / ".blueprint" / "config.json")
    submissions_root = (root / config.get("submissions_dir", "submissions")).resolve()
    if not path.is_relative_to(submissions_root) or path.parent != submissions_root:
        raise ProposalError("INVALID_SUBMISSION_PATH", "submission must be one direct child of submissions/")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint-root", type=Path, default=ROOT)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--actor-agent-id", default="blueprint-validator")
    parser.add_argument("--integrator-agent-id", default="blueprint-integrator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.blueprint_root.resolve()
    submission = resolve_submission(root, args.submission)
    if args.validate_only:
        result = validate_submission(root, submission, args.actor_agent_id)
    else:
        result = receive_submission(root, submission, args.integrator_agent_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProposalError as exc:
        print(json.dumps({"status": "rejected", "feedback": {"reasons": [exc.reason]}}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({"status": "error", "feedback": {"reasons": [{"code": "INTERNAL_ERROR", "message": str(exc)}]}}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)
