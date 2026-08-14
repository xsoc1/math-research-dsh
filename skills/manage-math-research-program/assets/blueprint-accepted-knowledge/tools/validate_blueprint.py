"""Validate a Blueprint v2.2 project, including its mathematics proof profile."""

from __future__ import annotations

import csv
import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

from math_blueprint import MathBlueprintError, validate_math_blueprint


ROOT = Path(__file__).resolve().parents[1]
EDGE_ROLE_TO_FIELD = {
    "assumption": "assumptions",
    "theory_input": "theory_inputs",
    "method_input": "method_inputs",
    "numerical_input": "numerical_inputs",
    "premise_input": "premise_inputs",
    "definition_input": "definition_inputs",
    "inference_input": "inference_inputs",
    "refutation_input": "refutation_inputs",
    "target_input": "target_inputs",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_refs(
    node: dict,
    field: str,
    by_id: dict[str, dict],
    edge_set: set[tuple[str, str]],
    allowed_types: set[str],
    *,
    nonempty: bool = False,
) -> list[str]:
    """Validate a typed dependency list and its corresponding graph edges."""

    refs = node.get(field)
    if refs is None:
        if nonempty:
            fail(f"{node['id']} must declare non-empty {field}")
        return []
    if not isinstance(refs, list):
        fail(f"{node['id']}.{field} must be a list")
    if nonempty and not refs:
        fail(f"{node['id']} must declare non-empty {field}")
    if len(refs) != len(set(refs)):
        fail(f"{node['id']}.{field} contains duplicate references")

    for ref in refs:
        if ref not in by_id:
            fail(f"{node['id']}.{field} references unknown node {ref!r}")
        ref_type = by_id[ref]["epistemic_type"]
        if ref_type not in allowed_types:
            fail(
                f"{node['id']}.{field} references {ref} of type {ref_type!r}; "
                f"expected one of {sorted(allowed_types)}"
            )
        if (ref, node["id"]) not in edge_set:
            fail(f"missing dependency edge [{ref!r}, {node['id']!r}] for {field}")
    return refs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=ROOT / "blueprint.json")
    parser.add_argument("--inventory", type=Path, default=ROOT / "evidence_inventory.csv")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ROOT,
        help="Resolve relative artifact paths from this directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    blueprint = args.blueprint.resolve()
    inventory_path = args.inventory.resolve()
    artifact_root = args.artifact_root.resolve()

    data = json.loads(blueprint.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        fail("nodes and edges must both be lists")

    mainlines = set(data.get("taxonomy", {}).get("mainlines", {}))
    epistemic_types = set(data.get("taxonomy", {}).get("epistemic_types", {}))
    if not mainlines or not epistemic_types:
        fail("taxonomy.mainlines and taxonomy.epistemic_types must be non-empty")

    required = {
        "id",
        "type",
        "title",
        "statement",
        "status",
        "grade",
        "mainline",
        "epistemic_type",
    }
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            fail(f"node #{index} must be an object")
        missing = required - set(node)
        if missing:
            fail(f"node #{index} is missing fields: {sorted(missing)}")

    ids = [node["id"] for node in nodes]
    if any(not isinstance(node_id, str) or not node_id for node_id in ids):
        fail("every node must have a non-empty string id")
    duplicates = [node_id for node_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        fail(f"duplicate node ids: {duplicates}")

    by_id = {node["id"]: node for node in nodes}
    known = set(ids)
    graph: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in ids}
    edge_set: set[tuple[str, str]] = set()
    edge_role_fields: dict[tuple[str, str], str | None] = {}

    for index, edge in enumerate(edges):
        if isinstance(edge, list) and len(edge) == 2:
            source, target = edge
            role_field = None
        elif isinstance(edge, dict) and edge.get("source") and edge.get("target"):
            source, target = edge["source"], edge["target"]
            role = edge.get("role")
            if role not in EDGE_ROLE_TO_FIELD:
                fail(
                    f"edge #{index} has unknown or missing role {role!r}; "
                    f"expected one of {sorted(EDGE_ROLE_TO_FIELD)}"
                )
            role_field = EDGE_ROLE_TO_FIELD[role]
        else:
            fail(f"edge #{index} must be [source, target] or an edge object")
        if source not in known or target not in known:
            fail(f"edge #{index} references unknown node: {edge}")
        pair = (source, target)
        if pair in edge_set:
            fail(f"duplicate edge #{index}: {edge}")
        edge_set.add(pair)
        edge_role_fields[pair] = role_field
        graph[source].append(target)
        indegree[target] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    while queue:
        node_id = queue.popleft()
        visited.append(node_id)
        for target in graph[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(visited) != len(ids):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        fail(f"dependency graph contains a cycle involving: {cyclic}")

    grades = set(data.get("evidence_grades", {}))
    for node in nodes:
        node_id = node["id"]
        if node["grade"] not in grades:
            fail(f"{node_id} has unknown evidence grade {node['grade']!r}")
        if node["mainline"] not in mainlines:
            fail(f"{node_id} has unknown mainline {node['mainline']!r}")
        if node["epistemic_type"] not in epistemic_types:
            fail(f"{node_id} has unknown epistemic_type {node['epistemic_type']!r}")

        epistemic_type = node["epistemic_type"]
        if epistemic_type == "basic_assumption" and node["mainline"] != "theory":
            fail(f"{node_id}: a basic assumption must be on the theory mainline")
        if epistemic_type == "theory_from_assumptions":
            if "assumptions" not in node:
                fail(f"{node_id} must explicitly declare assumptions (use [] for identities)")
            require_refs(
                node,
                "assumptions",
                by_id,
                edge_set,
                {"basic_assumption"},
            )
            require_refs(
                node,
                "theory_inputs",
                by_id,
                edge_set,
                {"theory_from_assumptions"},
            )
        elif epistemic_type in {"numerical_result", "numerical_experiment_design"}:
            require_refs(
                node,
                "method_inputs",
                by_id,
                edge_set,
                {"numerical_method"},
                nonempty=True,
            )
        elif epistemic_type == "theory_from_numerics":
            require_refs(
                node,
                "theory_inputs",
                by_id,
                edge_set,
                {"theory_from_assumptions", "theory_from_numerics"},
                nonempty=True,
            )
            require_refs(
                node,
                "numerical_inputs",
                by_id,
                edge_set,
                {"numerical_result", "theory_from_numerics"},
                nonempty=True,
            )

    for (source, target), role_field in sorted(edge_role_fields.items()):
        if role_field is None:
            continue
        refs = by_id[target].get(role_field)
        if not isinstance(refs, list) or source not in refs:
            fail(
                f"typed edge {source!r} -> {target!r} declares role for "
                f"{role_field}, but {target}.{role_field} does not include {source}"
            )

    typed_fields = set(EDGE_ROLE_TO_FIELD.values())
    for target, node in by_id.items():
        for field in typed_fields:
            refs = node.get(field)
            if refs is None:
                continue
            if not isinstance(refs, list):
                fail(f"{target}.{field} must be a list")
            for source in refs:
                pair = (source, target)
                if pair not in edge_role_fields:
                    fail(f"missing edge {source!r} -> {target!r} for {target}.{field}")
                edge_field = edge_role_fields[pair]
                if edge_field is not None and edge_field != field:
                    fail(
                        f"edge {source!r} -> {target!r} has role for {edge_field}, "
                        f"but the node declares it in {field}"
                    )
    by_type = Counter(node["type"] for node in nodes)
    by_mainline = Counter(node["mainline"] for node in nodes)
    by_epistemic_type = Counter(node["epistemic_type"] for node in nodes)
    by_grade = Counter(node["grade"] for node in nodes)

    with inventory_path.open(encoding="utf-8", newline="") as handle:
        inventory = list(csv.DictReader(handle))
    inventory_required = {
        "result_id",
        "mainline",
        "epistemic_type",
        "blueprint_node_id",
        "grade",
        "primary_artifact",
    }
    if inventory and not inventory_required.issubset(inventory[0]):
        fail(
            "evidence_inventory.csv is missing columns: "
            f"{sorted(inventory_required - set(inventory[0]))}"
        )
    seen_result_ids: set[str] = set()
    for row_index, row in enumerate(inventory, start=2):
        result_id = row["result_id"]
        if not result_id or result_id in seen_result_ids:
            fail(f"inventory row {row_index} has empty or duplicate result_id {result_id!r}")
        seen_result_ids.add(result_id)
        node_id = row["blueprint_node_id"]
        if node_id not in by_id:
            fail(f"inventory row {row_index} references unknown node {node_id!r}")
        node = by_id[node_id]
        for field in ("mainline", "epistemic_type", "grade"):
            if row[field] != node[field]:
                fail(
                    f"inventory row {row_index} {field}={row[field]!r} disagrees with "
                    f"{node_id} ({node[field]!r})"
                )
        artifact = row["primary_artifact"]
        artifact_path = Path(artifact)
        if artifact and not (artifact_path if artifact_path.is_absolute() else artifact_root / artifact_path).exists():
            fail(f"inventory row {row_index} artifact does not exist: {artifact}")

    try:
        mathematics = validate_math_blueprint(data, artifact_root=artifact_root)
    except MathBlueprintError as exc:
        fail(f"mathematics profile: {exc}")

    print(
        json.dumps(
            {
                "blueprint": str(blueprint),
                "inventory": str(inventory_path),
                "version": data.get("project", {}).get("version"),
                "nodes": len(nodes),
                "edges": len(edges),
                "acyclic": True,
                "typed_dependencies_valid": True,
                "inventory_rows": len(inventory),
                "inventory_links_valid": True,
                "mathematics": mathematics,
                "by_mainline": dict(sorted(by_mainline.items())),
                "by_epistemic_type": dict(sorted(by_epistemic_type.items())),
                "by_type": dict(sorted(by_type.items())),
                "by_grade": dict(sorted(by_grade.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
