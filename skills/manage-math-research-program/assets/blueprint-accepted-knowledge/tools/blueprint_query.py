#!/usr/bin/env python3
"""Deterministically query a Blueprint v2.2 canonical snapshot.

The program is a read-only gateway for research Agents. It resolves canonical
paths from .blueprint/config.json, binds every result to the Blueprint and
inventory file hashes, and never reads submissions or writes an index.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from blueprint_common import semantic_node_hash, sha256_bytes, sha256_file
from math_blueprint import (
    MathBlueprintError,
    compute_frontier,
    compute_trusted_closure,
    contexts as math_contexts,
    math_enabled,
    math_node_semantics,
    trusted_math_node_ids,
)


SCHEMA_VERSION = "blueprint-query/v2"
DEFAULT_POLICY = {
    "default_limit": 10,
    "max_limit": 50,
    "default_depth": 1,
    "max_depth": 5,
    "default_max_nodes": 30,
    "max_nodes": 100,
    "exclude_archived_by_default": True,
}
ARCHIVED_TYPES = {"superseded"}
ARCHIVED_GRADES = {"X"}
ARCHIVED_MAINLINES = {"archive"}
TYPED_INPUT_FIELDS = (
    "assumptions",
    "theory_inputs",
    "method_inputs",
    "numerical_inputs",
    "premise_inputs",
    "definition_inputs",
    "inference_inputs",
    "refutation_inputs",
    "target_inputs",
)


class QueryFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 2,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def read_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise QueryFailure(
            "CANONICAL_READ_FAILED",
            f"Could not read {label}: {path}",
            exit_code=3,
            details={"path": str(path), "error": str(exc)},
        ) from exc


def resolve_statistics_root(requested: Path | None) -> Path:
    candidates: list[Path] = []
    if requested is not None:
        candidates.append(requested.expanduser().resolve())
    else:
        cwd = Path.cwd().resolve()
        candidates.extend((cwd, cwd / "statistics", Path(__file__).resolve().parents[1]))

    checked: list[str] = []
    for candidate in candidates:
        variants = (candidate / "statistics", candidate)
        for root in variants:
            root = root.resolve()
            marker = root / ".blueprint" / "config.json"
            checked.append(str(marker))
            if marker.is_file():
                return root

    raise QueryFailure(
        "CONFIG_NOT_FOUND",
        "Could not locate statistics/.blueprint/config.json.",
        exit_code=3,
        details={"checked": sorted(set(checked))},
    )


def load_json_bytes(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QueryFailure(
            "INVALID_JSON",
            f"Invalid JSON in {path}",
            exit_code=3,
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise QueryFailure(
            "INVALID_JSON",
            f"Expected a JSON object in {path}",
            exit_code=3,
            details={"path": str(path)},
        )
    return value


def load_inventory_bytes(payload: bytes, path: Path) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise QueryFailure(
            "INVALID_INVENTORY",
            f"Inventory is not valid UTF-8: {path}",
            exit_code=3,
            details={"path": str(path), "error": str(exc)},
        ) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise QueryFailure(
            "INVALID_INVENTORY",
            f"Inventory has no header: {path}",
            exit_code=3,
            details={"path": str(path)},
        )
    return [{key: value or "" for key, value in row.items()} for row in reader]


def load_consistent_pair(
    blueprint_path: Path,
    inventory_path: Path,
    attempts: int = 3,
) -> tuple[bytes, bytes]:
    """Read a stable canonical pair without taking the receiver's write lock."""

    last_hashes: dict[str, str] = {}
    for _ in range(attempts):
        blueprint_first = read_bytes(blueprint_path, "canonical Blueprint")
        inventory_first = read_bytes(inventory_path, "evidence inventory")
        blueprint_second = read_bytes(blueprint_path, "canonical Blueprint")
        inventory_second = read_bytes(inventory_path, "evidence inventory")
        last_hashes = {
            "blueprint_first": sha256_bytes(blueprint_first),
            "blueprint_second": sha256_bytes(blueprint_second),
            "inventory_first": sha256_bytes(inventory_first),
            "inventory_second": sha256_bytes(inventory_second),
        }
        if (
            last_hashes["blueprint_first"] == last_hashes["blueprint_second"]
            and last_hashes["inventory_first"] == last_hashes["inventory_second"]
        ):
            return blueprint_second, inventory_second

    raise QueryFailure(
        "SNAPSHOT_CHANGED_DURING_READ",
        "Canonical files changed repeatedly while the query snapshot was read.",
        exit_code=5,
        details=last_hashes,
    )


class BlueprintStore:
    def __init__(self, statistics_root: Path) -> None:
        self.statistics_root = statistics_root
        config_path = statistics_root / ".blueprint" / "config.json"
        self.config = load_json_bytes(read_bytes(config_path, "Blueprint configuration"), config_path)

        canonical_name = self.config.get("canonical_blueprint", "blueprint.json")
        inventory_name = self.config.get("evidence_inventory", "evidence_inventory.csv")
        self.blueprint_path = (statistics_root / canonical_name).resolve()
        self.inventory_path = (statistics_root / inventory_name).resolve()
        blueprint_bytes, inventory_bytes = load_consistent_pair(
            self.blueprint_path,
            self.inventory_path,
        )
        self.snapshot = {
            "blueprint_sha256": sha256_bytes(blueprint_bytes),
            "inventory_sha256": sha256_bytes(inventory_bytes),
        }
        self.blueprint = load_json_bytes(blueprint_bytes, self.blueprint_path)
        self.inventory = load_inventory_bytes(inventory_bytes, self.inventory_path)
        self.policy = dict(DEFAULT_POLICY)
        configured_policy = self.config.get("retrieval_policy", {})
        if isinstance(configured_policy, dict):
            self.policy.update(configured_policy)
        self.warnings: list[dict[str, Any]] = []
        self._trusted_math_cache: dict[str, set[str]] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        nodes = self.blueprint.get("nodes", [])
        edges = self.blueprint.get("edges", [])
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise QueryFailure(
                "INVALID_BLUEPRINT",
                "Blueprint nodes and edges must be lists.",
                exit_code=3,
            )

        self.by_id: dict[str, dict[str, Any]] = {}
        for position, node in enumerate(nodes):
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                raise QueryFailure(
                    "INVALID_BLUEPRINT",
                    f"Node #{position} is not an object with a string id.",
                    exit_code=3,
                )
            node_id = node["id"]
            if node_id in self.by_id:
                raise QueryFailure(
                    "INVALID_BLUEPRINT",
                    f"Duplicate node id: {node_id}",
                    exit_code=3,
                )
            self.by_id[node_id] = node

        self.incoming: dict[str, set[str]] = defaultdict(set)
        self.outgoing: dict[str, set[str]] = defaultdict(set)
        self.edges: list[tuple[str, str]] = []
        self.edge_records: list[dict[str, Any]] = []
        for position, edge in enumerate(edges):
            if isinstance(edge, list) and len(edge) == 2:
                source, target = edge
            elif isinstance(edge, dict) and edge.get("source") and edge.get("target"):
                source, target = edge["source"], edge["target"]
            else:
                raise QueryFailure(
                    "INVALID_BLUEPRINT",
                    f"Edge #{position} is not [source, target] or an edge object.",
                    exit_code=3,
                )
            if source not in self.by_id or target not in self.by_id:
                raise QueryFailure(
                    "INVALID_BLUEPRINT",
                    f"Edge #{position} references an unknown node.",
                    exit_code=3,
                    details={"edge": edge},
                )
            self.incoming[target].add(source)
            self.outgoing[source].add(target)
            self.edges.append((source, target))
            self.edge_records.append(
                {
                    "source": source,
                    "target": target,
                    "role": edge.get("role") if isinstance(edge, dict) else None,
                    "legacy_pair": isinstance(edge, list),
                }
            )

        self.inventory_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row_number, row in enumerate(self.inventory, start=2):
            node_id = row.get("blueprint_node_id", "")
            if node_id and node_id not in self.by_id:
                raise QueryFailure(
                    "INVALID_INVENTORY",
                    f"Inventory row {row_number} references unknown node {node_id}.",
                    exit_code=3,
                )
            if node_id:
                self.inventory_by_node[node_id].append(row)

    def trusted_math_ids(self, context_id: str | None = None) -> set[str]:
        if not math_enabled(self.blueprint):
            return set()
        key = context_id or "__default__"
        if key not in self._trusted_math_cache:
            try:
                self._trusted_math_cache[key] = trusted_math_node_ids(
                    self.blueprint, context_id
                )
            except MathBlueprintError as exc:
                raise QueryFailure(
                    "INVALID_MATH_PROFILE",
                    str(exc),
                    exit_code=3,
                ) from exc
        return self._trusted_math_cache[key]

    def ensure_expected_snapshot(
        self,
        expected_blueprint: str | None,
        expected_inventory: str | None,
    ) -> None:
        mismatches: dict[str, dict[str, str]] = {}
        if expected_blueprint and expected_blueprint != self.snapshot["blueprint_sha256"]:
            mismatches["blueprint_sha256"] = {
                "expected": expected_blueprint,
                "actual": self.snapshot["blueprint_sha256"],
            }
        if expected_inventory and expected_inventory != self.snapshot["inventory_sha256"]:
            mismatches["inventory_sha256"] = {
                "expected": expected_inventory,
                "actual": self.snapshot["inventory_sha256"],
            }
        if mismatches:
            raise QueryFailure(
                "SNAPSHOT_MISMATCH",
                "The canonical snapshot no longer matches the caller's expected hashes.",
                exit_code=5,
                details={"mismatches": mismatches},
            )

    @staticmethod
    def is_archived(node: dict[str, Any]) -> bool:
        return (
            node.get("epistemic_type") in ARCHIVED_TYPES
            or node.get("grade") in ARCHIVED_GRADES
            or node.get("mainline") in ARCHIVED_MAINLINES
        )

    def artifact_records(self, node_id: str, verify_hash: bool = False) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for row in self.inventory_by_node.get(node_id, []):
            locator = row.get("primary_artifact", "").strip()
            if not locator:
                continue
            raw_path = Path(locator).expanduser()
            resolved = raw_path.resolve() if raw_path.is_absolute() else (self.statistics_root / raw_path).resolve()
            exists = resolved.is_file()
            record: dict[str, Any] = {
                "result_id": row.get("result_id", ""),
                "locator": locator,
                "resolved_path": str(resolved),
                "external_to_statistics_root": not resolved.is_relative_to(self.statistics_root),
                "exists": exists,
            }
            if exists:
                try:
                    record["size_bytes"] = resolved.stat().st_size
                    if verify_hash:
                        record["sha256"] = sha256_file(resolved)
                except OSError as exc:
                    record["read_error"] = str(exc)
            else:
                record["warning"] = "BROKEN_ARTIFACT_PATH"
            records.append(record)
        return records

    def node_payload(self, node_id: str) -> dict[str, Any]:
        node = self.by_id[node_id]
        incoming = sorted(self.incoming.get(node_id, set()))
        evidence = sorted(
            self.inventory_by_node.get(node_id, []),
            key=lambda row: row.get("result_id", ""),
        )
        payload = {
            "canonical_node": node,
            "direct_inputs": incoming,
            "direct_dependents": sorted(self.outgoing.get(node_id, set())),
            "direct_input_edges": sorted(
                (
                    record
                    for record in self.edge_records
                    if record["target"] == node_id
                ),
                key=lambda record: (
                    record["source"],
                    record["target"],
                    record.get("role") or "",
                ),
            ),
            "direct_dependent_edges": sorted(
                (
                    record
                    for record in self.edge_records
                    if record["source"] == node_id
                ),
                key=lambda record: (
                    record["source"],
                    record["target"],
                    record.get("role") or "",
                ),
            ),
            "typed_inputs": {
                field: node[field]
                for field in TYPED_INPUT_FIELDS
                if field in node
            },
            "semantic_sha256": semantic_node_hash(node, incoming),
            "linked_result_ids": [row.get("result_id", "") for row in evidence],
            "evidence": evidence,
            "artifacts": self.artifact_records(node_id),
            "historical_or_noncurrent": self.is_archived(node),
        }
        if math_enabled(self.blueprint):
            try:
                semantics = math_node_semantics(self.blueprint, node_id)
            except MathBlueprintError as exc:
                semantics = {"error": str(exc)}
            if semantics is not None:
                payload["math_semantics"] = semantics
        return payload

    def payload_warnings(self, payloads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for payload in payloads:
            node_id = payload["canonical_node"]["id"]
            if payload["historical_or_noncurrent"]:
                warnings.append(
                    {
                        "code": "HISTORICAL_OR_NONCURRENT_NODE",
                        "node_id": node_id,
                    }
                )
            for artifact in payload["artifacts"]:
                if not artifact["exists"]:
                    warnings.append(
                        {
                            "code": "BROKEN_ARTIFACT_PATH",
                            "node_id": node_id,
                            "locator": artifact["locator"],
                        }
                    )
                elif artifact.get("read_error"):
                    warnings.append(
                        {
                            "code": "ARTIFACT_READ_ERROR",
                            "node_id": node_id,
                            "locator": artifact["locator"],
                            "error": artifact["read_error"],
                        }
                    )
        return warnings

    def filter_node(self, node: dict[str, Any], args: argparse.Namespace) -> bool:
        include_archived = getattr(args, "include_archived", False)
        exclude_archived = bool(self.policy.get("exclude_archived_by_default", True))
        if exclude_archived and not include_archived and self.is_archived(node):
            return False
        for argument, field in (
            ("mainline", "mainline"),
            ("epistemic_type", "epistemic_type"),
            ("status", "status"),
            ("grade", "grade"),
        ):
            expected = getattr(args, argument, None)
            if expected and node.get(field) != expected:
                return False
        math_view = getattr(args, "math_view", None) or self.policy.get(
            "default_math_view", "all"
        )
        if math_view != "all" and math_enabled(self.blueprint):
            trusted = self.trusted_math_ids(getattr(args, "context", None))
            is_math = math_node_semantics(
                self.blueprint,
                str(node.get("id", "")),
                getattr(args, "context", None),
            ) is not None
            if math_view == "trusted" and is_math and node.get("id") not in trusted:
                return False
            if math_view == "research" and (not is_math or node.get("id") in trusted):
                return False
        return True

    def search_score(self, node: dict[str, Any], query: str) -> tuple[int, list[str]]:
        normalized_query = normalize_text(query)
        tokens = [part for part in re.split(r"[^\w]+", normalized_query) if part]
        if not tokens:
            tokens = [normalized_query]

        node_id = normalize_text(str(node.get("id", "")))
        title = normalize_text(str(node.get("title", "")))
        statement = normalize_text(str(node.get("statement", "")))
        metadata = normalize_text(" ".join(iter_strings(node)))
        evidence = self.inventory_by_node.get(str(node.get("id", "")), [])
        evidence_text = normalize_text(" ".join(iter_strings(evidence)))
        fields = {
            "id": (node_id, 500),
            "title": (title, 220),
            "statement": (statement, 120),
            "metadata": (metadata, 50),
            "evidence": (evidence_text, 80),
        }

        score = 0
        matches: list[str] = []
        for name, (text_value, weight) in fields.items():
            if not text_value:
                continue
            field_score = 0
            if normalized_query == text_value:
                field_score = weight * 5
            elif normalized_query and normalized_query in text_value:
                field_score = weight * 3
            else:
                hits = sum(1 for token in tokens if token in text_value)
                if hits:
                    field_score = weight * hits // len(tokens)
            if field_score:
                score += field_score
                matches.append(name)

        if normalized_query == node_id:
            score += 5000
        elif node_id.startswith(normalized_query):
            score += 1000
        return score, matches


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mainline")
    parser.add_argument("--epistemic-type", dest="epistemic_type")
    parser.add_argument("--status")
    parser.add_argument("--grade")
    parser.add_argument("--context", help="Mathematics context for trusted/research views.")
    parser.add_argument(
        "--math-view",
        choices=("all", "trusted", "research"),
        default=None,
        help="Filter mathematics records by computed proof eligibility.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archive-mainline, superseded, and grade-X nodes.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--statistics-root",
        type=Path,
        help="Statistics directory or project root. Auto-detected when omitted.",
    )
    parser.add_argument("--expected-blueprint-sha256")
    parser.add_argument("--expected-inventory-sha256")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    subparsers.add_parser("snapshot", help="Return canonical snapshot hashes and counts.")

    get_parser = subparsers.add_parser("get", help="Get one or more exact node IDs.")
    get_parser.add_argument("--id", action="append", required=True, dest="ids")

    find_parser = subparsers.add_parser("find", help="Search canonical node and evidence text.")
    find_parser.add_argument("--text", required=True)
    find_parser.add_argument("--limit", type=int)
    add_filter_arguments(find_parser)

    graph_parser = subparsers.add_parser("graph", help="Expand a bounded dependency subgraph.")
    graph_parser.add_argument("--id", required=True, dest="node_id")
    graph_parser.add_argument(
        "--direction",
        choices=("incoming", "outgoing", "both"),
        default="incoming",
    )
    graph_parser.add_argument("--depth", type=int)
    graph_parser.add_argument("--max-nodes", type=int)
    graph_parser.add_argument("--include-archived", action="store_true")

    evidence_parser = subparsers.add_parser("evidence", help="Get inventory rows for a node.")
    evidence_parser.add_argument("--node", required=True, dest="node_id")

    artifact_parser = subparsers.add_parser(
        "artifact-meta",
        help="Inspect metadata for artifacts registered to a node without reading content.",
    )
    artifact_parser.add_argument("--node", required=True, dest="node_id")
    artifact_parser.add_argument("--verify-sha256", action="store_true")

    closure_parser = subparsers.add_parser(
        "math-closure",
        help="Compute the trusted mathematical claim closure for a context.",
    )
    closure_parser.add_argument("--context")

    frontier_parser = subparsers.add_parser(
        "math-frontier",
        help="Return open, blocked, candidate, and refuted inference steps for a goal.",
    )
    frontier_parser.add_argument("--goal", required=True, dest="goal_or_claim_id")
    frontier_parser.add_argument("--context")

    goals_parser = subparsers.add_parser(
        "math-goals",
        help="List mathematics research goals and computed availability.",
    )
    goals_parser.add_argument("--context")
    return parser


def bounded_integer(
    requested: int | None,
    default_value: int,
    maximum: int,
    label: str,
) -> int:
    value = default_value if requested is None else requested
    if value < 0 or value > maximum:
        raise QueryFailure(
            "INVALID_BOUND",
            f"{label} must be between 0 and {maximum}.",
            details={"requested": value, "maximum": maximum},
        )
    return value


def execute(store: BlueprintStore, args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation == "snapshot":
        result = {
            "node_count": len(store.by_id),
            "edge_count": len(store.edges),
            "inventory_row_count": len(store.inventory),
            "canonical_blueprint": str(store.blueprint_path),
            "evidence_inventory": str(store.inventory_path),
        }
        if math_enabled(store.blueprint):
            try:
                result["mathematics"] = {
                    "enabled": True,
                    "contexts": sorted(math_contexts(store.blueprint)),
                }
            except MathBlueprintError as exc:
                raise QueryFailure(
                    "INVALID_MATH_PROFILE", str(exc), exit_code=3
                ) from exc
        else:
            result["mathematics"] = {"enabled": False, "contexts": []}
        return result

    if operation == "math-closure":
        if not math_enabled(store.blueprint):
            raise QueryFailure(
                "MATH_PROFILE_DISABLED",
                "This Blueprint does not enable the mathematics profile.",
                exit_code=4,
            )
        try:
            return compute_trusted_closure(store.blueprint, args.context)
        except MathBlueprintError as exc:
            raise QueryFailure("INVALID_MATH_QUERY", str(exc), exit_code=4) from exc

    if operation == "math-frontier":
        if not math_enabled(store.blueprint):
            raise QueryFailure(
                "MATH_PROFILE_DISABLED",
                "This Blueprint does not enable the mathematics profile.",
                exit_code=4,
            )
        try:
            return compute_frontier(
                store.blueprint, args.goal_or_claim_id, args.context
            )
        except MathBlueprintError as exc:
            raise QueryFailure("INVALID_MATH_QUERY", str(exc), exit_code=4) from exc

    if operation == "math-goals":
        if not math_enabled(store.blueprint):
            raise QueryFailure(
                "MATH_PROFILE_DISABLED",
                "This Blueprint does not enable the mathematics profile.",
                exit_code=4,
            )
        try:
            closure = compute_trusted_closure(store.blueprint, args.context)
            available = set(closure["available_claim_ids"])
            selected_context = closure["context_id"]
            goals = []
            for node in store.by_id.values():
                if node.get("epistemic_type") != "research_goal":
                    continue
                if node.get("context_id", "global") not in {"global", selected_context}:
                    continue
                frontier = compute_frontier(
                    store.blueprint, node["id"], selected_context
                )
                goals.append(
                    {
                        "goal": store.node_payload(node["id"]),
                        "target_claim_id": node.get("target_claim"),
                        "target_available": node.get("target_claim") in available,
                        "negation_claim_id": node.get("negation_claim"),
                        "negation_available": node.get("negation_claim") in available,
                        "research_outcome": frontier["research_outcome"],
                        "goal_resolved": frontier["goal_resolved"],
                        "requested_mode_satisfied": frontier[
                            "requested_mode_satisfied"
                        ],
                        "assignment_ready_inference_ids": [
                            item["inference_id"]
                            for item in frontier["frontier"]
                            if item["assignment_ready"]
                        ],
                    }
                )
            goals.sort(key=lambda item: item["goal"]["canonical_node"]["id"])
            return {"context_id": selected_context, "goals": goals}
        except MathBlueprintError as exc:
            raise QueryFailure("INVALID_MATH_QUERY", str(exc), exit_code=4) from exc

    if operation == "get":
        missing = sorted(node_id for node_id in args.ids if node_id not in store.by_id)
        found_ids = sorted(set(args.ids) - set(missing))
        nodes = [store.node_payload(node_id) for node_id in found_ids]
        warnings = store.payload_warnings(nodes)
        if missing:
            warnings.append({"code": "NODE_NOT_FOUND", "node_ids": missing})
        return {"nodes": nodes, "missing_ids": missing, "warnings": warnings}

    if operation == "find":
        max_limit = int(store.policy.get("max_limit", DEFAULT_POLICY["max_limit"]))
        limit = bounded_integer(
            args.limit,
            int(store.policy.get("default_limit", DEFAULT_POLICY["default_limit"])),
            max_limit,
            "limit",
        )
        ranked: list[tuple[int, str, list[str]]] = []
        for node_id, node in store.by_id.items():
            if not store.filter_node(node, args):
                continue
            score, matches = store.search_score(node, args.text)
            if score:
                ranked.append((score, node_id, matches))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        selected = ranked[:limit]
        nodes = [
            {
                **store.node_payload(node_id),
                "retrieval": {"score": score, "matched_fields": matches},
            }
            for score, node_id, matches in selected
        ]
        return {
            "query": args.text,
            "nodes": nodes,
            "match_count": len(ranked),
            "returned_count": len(selected),
            "truncated": len(ranked) > len(selected),
            "warnings": store.payload_warnings(nodes),
        }

    if operation == "graph":
        if args.node_id not in store.by_id:
            raise QueryFailure(
                "NODE_NOT_FOUND",
                f"Unknown node id: {args.node_id}",
                exit_code=4,
                details={"node_id": args.node_id},
            )
        depth = bounded_integer(
            args.depth,
            int(store.policy.get("default_depth", DEFAULT_POLICY["default_depth"])),
            int(store.policy.get("max_depth", DEFAULT_POLICY["max_depth"])),
            "depth",
        )
        max_nodes = bounded_integer(
            args.max_nodes,
            int(store.policy.get("default_max_nodes", DEFAULT_POLICY["default_max_nodes"])),
            int(store.policy.get("max_nodes", DEFAULT_POLICY["max_nodes"])),
            "max_nodes",
        )
        if max_nodes < 1:
            raise QueryFailure("INVALID_BOUND", "max_nodes must be at least 1.")

        selected = {args.node_id}
        depth_by_id = {args.node_id: 0}
        queue: deque[str] = deque([args.node_id])
        truncated = False
        while queue:
            current = queue.popleft()
            current_depth = depth_by_id[current]
            if current_depth >= depth:
                continue
            neighbours: set[str] = set()
            if args.direction in {"incoming", "both"}:
                neighbours.update(store.incoming.get(current, set()))
            if args.direction in {"outgoing", "both"}:
                neighbours.update(store.outgoing.get(current, set()))
            for neighbour in sorted(neighbours):
                if neighbour in selected:
                    continue
                exclude_archived = bool(
                    store.policy.get("exclude_archived_by_default", True)
                )
                if exclude_archived and not args.include_archived and store.is_archived(
                    store.by_id[neighbour]
                ):
                    continue
                if len(selected) >= max_nodes:
                    truncated = True
                    break
                selected.add(neighbour)
                depth_by_id[neighbour] = current_depth + 1
                queue.append(neighbour)
            if truncated:
                break

        ordered_ids = sorted(selected, key=lambda node_id: (depth_by_id[node_id], node_id))
        selected_edges = [
            record
            for record in store.edge_records
            if record["source"] in selected and record["target"] in selected
        ]
        selected_edges.sort(
            key=lambda record: (
                record["source"],
                record["target"],
                record.get("role") or "",
            )
        )
        nodes = [store.node_payload(node_id) for node_id in ordered_ids]
        warnings = store.payload_warnings(nodes)
        if truncated:
            warnings.append(
                {
                    "code": "GRAPH_TRUNCATED",
                    "max_nodes": max_nodes,
                    "requested_depth": depth,
                }
            )
        return {
            "root_id": args.node_id,
            "direction": args.direction,
            "requested_depth": depth,
            "depth_by_id": {node_id: depth_by_id[node_id] for node_id in ordered_ids},
            "nodes": nodes,
            "edges": selected_edges,
            "truncated": truncated,
            "warnings": warnings,
        }

    if operation in {"evidence", "artifact-meta"}:
        if args.node_id not in store.by_id:
            raise QueryFailure(
                "NODE_NOT_FOUND",
                f"Unknown node id: {args.node_id}",
                exit_code=4,
                details={"node_id": args.node_id},
            )
        evidence = sorted(
            store.inventory_by_node.get(args.node_id, []),
            key=lambda row: row.get("result_id", ""),
        )
        artifacts = store.artifact_records(
            args.node_id,
            verify_hash=bool(getattr(args, "verify_sha256", False)),
        )
        warnings = [
            {
                "code": "BROKEN_ARTIFACT_PATH",
                "node_id": args.node_id,
                "locator": artifact["locator"],
            }
            for artifact in artifacts
            if not artifact["exists"]
        ]
        node_payload = store.node_payload(args.node_id)
        warnings.extend(store.payload_warnings([node_payload]))
        result: dict[str, Any] = {
            "node": node_payload,
            "artifacts": artifacts,
            "warnings": warnings,
        }
        if operation == "evidence":
            result["evidence"] = evidence
        return result

    raise QueryFailure("UNKNOWN_OPERATION", f"Unsupported operation: {operation}")


def response_envelope(
    *,
    ok: bool,
    operation: str | None,
    statistics_root: Path | None = None,
    snapshot: dict[str, str] | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "operation": operation,
    }
    if statistics_root is not None:
        response["statistics_root"] = str(statistics_root)
    if snapshot is not None:
        response["snapshot"] = snapshot
    if result is not None:
        warnings: list[dict[str, Any]] = []
        seen_warnings: set[str] = set()
        for warning in result.pop("warnings", []):
            key = json.dumps(warning, ensure_ascii=False, sort_keys=True)
            if key in seen_warnings:
                continue
            seen_warnings.add(key)
            warnings.append(warning)
        response["result"] = result
        response["warnings"] = warnings
    if error is not None:
        response["error"] = error
    return response


def emit(value: dict[str, Any], compact: bool = False) -> None:
    if compact:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root: Path | None = None
    store: BlueprintStore | None = None
    try:
        root = resolve_statistics_root(args.statistics_root)
        store = BlueprintStore(root)
        store.ensure_expected_snapshot(
            args.expected_blueprint_sha256,
            args.expected_inventory_sha256,
        )
        result = execute(store, args)
        emit(
            response_envelope(
                ok=True,
                operation=args.operation,
                statistics_root=root,
                snapshot=store.snapshot,
                result=result,
            ),
            compact=args.compact,
        )
        return 0
    except QueryFailure as exc:
        emit(
            response_envelope(
                ok=False,
                operation=getattr(args, "operation", None),
                statistics_root=root,
                snapshot=store.snapshot if store is not None else None,
                error={
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            ),
            compact=getattr(args, "compact", False),
        )
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
