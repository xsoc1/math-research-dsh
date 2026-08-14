"""Deterministic mathematics profile for Blueprint v2.2.

The profile stores propositions and research records in one canonical graph.
Mathematical entailment is represented by first-class inference nodes:

    premise claim(s) -> inference -> conclusion claim

Only inferences with ``proof_status == "proved"`` propagate truth.  Open,
blocked, candidate, and refuted inferences remain queryable research memory but
never enter the trusted closure.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from blueprint_common import sha256_file


MATH_PROFILE_SCHEMA = "math-proof/v1"

CLAIM_TYPES = {
    "problem_hypothesis",
    "external_mathematical_result",
    "mathematical_claim",
    "verified_counterexample",
}
INFERENCE_TYPE = "mathematical_inference"
DEFINITION_TYPE = "definition_contract"
GOAL_TYPE = "research_goal"
OBLIGATION_TYPE = "proof_obligation"
ATTEMPT_TYPE = "research_attempt"
MATH_TYPES = CLAIM_TYPES | {
    INFERENCE_TYPE,
    DEFINITION_TYPE,
    GOAL_TYPE,
    OBLIGATION_TYPE,
    ATTEMPT_TYPE,
}

CLAIM_STATUSES = {
    "given",
    "imported_verified",
    "open",
    "candidate_supported",
    "established",
    "refuted",
    "contested",
    "target",
    "superseded",
}
INFERENCE_STATUSES = {
    "proposed",
    "open",
    "assigned",
    "candidate_proof",
    "proved",
    "refuted",
    "blocked",
    "invalid",
    "superseded",
}
GOAL_STATUSES = {"open", "partial_progress", "solved", "refuted", "blocked", "superseded"}
OBLIGATION_STATUSES = {"open", "assigned", "candidate_proof", "proved", "refuted", "blocked", "superseded"}
ATTEMPT_STATUSES = {
    "proposed",
    "active",
    "promising",
    "partial",
    "blocked",
    "refuted",
    "merged",
    "produced_candidate",
    "audited_failure",
    "proved",
    "formalized",
    "superseded",
}
OBLIGATION_STRENGTHS = {
    "strictly_weaker",
    "equivalent",
    "near_equivalent",
    "stronger",
    "unknown",
}
GOAL_OUTCOMES = {"proof", "refutation", "independence"}

TRUSTED_CLAIM_STATUSES = {"given", "imported_verified", "established"}
NONTRUSTED_CLAIM_STATUSES = {
    "open",
    "candidate_supported",
    "refuted",
    "contested",
    "target",
    "superseded",
}

CLAIM_KINDS = {
    "hypothesis",
    "proposition",
    "conjecture",
    "lemma",
    "theorem",
    "counterexample",
    "no_go",
    "equivalence",
    "classification",
    "negation",
}
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


class MathBlueprintError(ValueError):
    """A deterministic mathematics-profile contract violation."""


def _require_status_sync(node: dict[str, Any], field: str) -> None:
    if node.get("status") != node.get(field):
        raise MathBlueprintError(
            f"{node['id']}.status must equal {field} ({node.get(field)!r})"
        )


def _as_string_list(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise MathBlueprintError(f"{label} must be a list of non-empty node IDs")
    if nonempty and not value:
        raise MathBlueprintError(f"{label} must be non-empty")
    if len(value) != len(set(value)):
        raise MathBlueprintError(f"{label} contains duplicate node IDs")
    return value


def _profile(data: dict[str, Any]) -> dict[str, Any] | None:
    profile = data.get("math_profile")
    if profile is None:
        return None
    if not isinstance(profile, dict):
        raise MathBlueprintError("math_profile must be an object")
    if profile.get("schema_version") != MATH_PROFILE_SCHEMA:
        raise MathBlueprintError(
            f"math_profile.schema_version must be {MATH_PROFILE_SCHEMA!r}"
        )
    if profile.get("enabled") is not True:
        raise MathBlueprintError("math_profile.enabled must be true when the profile is present")
    return profile


def math_enabled(data: dict[str, Any]) -> bool:
    profile = data.get("math_profile")
    return isinstance(profile, dict) and profile.get("enabled") is True


def index_nodes(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        raise MathBlueprintError("nodes must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise MathBlueprintError("every node must be an object with a string id")
        if node["id"] in by_id:
            raise MathBlueprintError(f"duplicate node id {node['id']}")
        by_id[node["id"]] = node
    return by_id


def edge_contracts(data: dict[str, Any]) -> dict[tuple[str, str], str | None]:
    contracts: dict[tuple[str, str], str | None] = {}
    for index, edge in enumerate(data.get("edges", [])):
        if isinstance(edge, list) and len(edge) == 2:
            source, target = edge
            role_field = None
        elif isinstance(edge, dict) and edge.get("source") and edge.get("target"):
            source, target = edge["source"], edge["target"]
            role = edge.get("role")
            if role not in EDGE_ROLE_TO_FIELD:
                raise MathBlueprintError(
                    f"edge #{index} has unknown or missing role {role!r}"
                )
            role_field = EDGE_ROLE_TO_FIELD[role]
        else:
            raise MathBlueprintError(f"edge #{index} must be [source, target] or an edge object")
        if not isinstance(source, str) or not isinstance(target, str):
            raise MathBlueprintError(f"edge #{index} endpoints must be strings")
        pair = (source, target)
        if pair in contracts:
            raise MathBlueprintError(f"duplicate edge {source!r} -> {target!r}")
        contracts[pair] = role_field
    return contracts


def edge_pairs(data: dict[str, Any]) -> set[tuple[str, str]]:
    return set(edge_contracts(data))


def contexts(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profile = _profile(data)
    if profile is None:
        return {}
    raw_contexts = profile.get("contexts", [])
    if not isinstance(raw_contexts, list):
        raise MathBlueprintError("math_profile.contexts must be a list")
    result: dict[str, dict[str, Any]] = {}
    for raw in raw_contexts:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise MathBlueprintError("every mathematics context must have a non-empty string id")
        if raw["id"] in result:
            raise MathBlueprintError(f"duplicate mathematics context id {raw['id']}")
        result[raw["id"]] = raw
    default = profile.get("default_context")
    if default is not None and default not in result:
        raise MathBlueprintError(f"unknown math_profile.default_context {default!r}")
    return result


def resolve_context_id(data: dict[str, Any], requested: str | None = None) -> str:
    available = contexts(data)
    if requested:
        if requested not in available:
            raise MathBlueprintError(f"unknown mathematics context {requested!r}")
        return requested
    profile = _profile(data)
    if profile is None:
        raise MathBlueprintError("mathematics profile is not enabled")
    default = profile.get("default_context")
    if isinstance(default, str) and default:
        return default
    if len(available) == 1:
        return next(iter(available))
    raise MathBlueprintError("a mathematics context must be specified")


def _require_refs(
    node: dict[str, Any],
    field: str,
    by_id: dict[str, dict[str, Any]],
    edges: set[tuple[str, str]],
    allowed_types: set[str],
    *,
    nonempty: bool = False,
) -> list[str]:
    refs = _as_string_list(node.get(field, []), f"{node['id']}.{field}", nonempty=nonempty)
    for ref in refs:
        if ref not in by_id:
            raise MathBlueprintError(f"{node['id']}.{field} references unknown node {ref!r}")
        ref_type = by_id[ref].get("epistemic_type")
        if ref_type not in allowed_types:
            raise MathBlueprintError(
                f"{node['id']}.{field} references {ref} of type {ref_type!r}; "
                f"expected one of {sorted(allowed_types)}"
            )
        if (ref, node["id"]) not in edges:
            raise MathBlueprintError(
                f"missing edge [{ref!r}, {node['id']!r}] for {node['id']}.{field}"
            )
    return refs


def _artifact_contract(
    node: dict[str, Any], field: str, artifact_root: Path | None
) -> dict[str, Any]:
    contract = node.get(field)
    if not isinstance(contract, dict):
        raise MathBlueprintError(f"{node['id']}.{field} must be an artifact contract object")
    path_value = contract.get("path")
    expected_hash = contract.get("sha256")
    if not isinstance(path_value, str) or not path_value:
        raise MathBlueprintError(f"{node['id']}.{field}.path is required")
    if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        raise MathBlueprintError(f"{node['id']}.{field}.sha256 is required")
    if artifact_root is not None:
        raw_path = Path(path_value).expanduser()
        resolved = raw_path.resolve() if raw_path.is_absolute() else (artifact_root / raw_path).resolve()
        if not resolved.is_file():
            raise MathBlueprintError(f"{node['id']}.{field} artifact does not exist: {path_value}")
        actual_hash = sha256_file(resolved)
        if actual_hash != expected_hash:
            raise MathBlueprintError(
                f"{node['id']}.{field} hash mismatch: expected {expected_hash}, actual {actual_hash}"
            )
    return contract


def _source_contract(node: dict[str, Any]) -> None:
    contract = node.get("source_contract")
    if not isinstance(contract, dict):
        raise MathBlueprintError(f"{node['id']}.source_contract must be an object")
    required = {"citation", "stable_identifier", "locator", "supported_statement", "verified_against_source"}
    missing = sorted(key for key in required if not contract.get(key))
    if missing:
        raise MathBlueprintError(f"{node['id']}.source_contract lacks {missing}")
    if contract.get("verified_against_source") is not True:
        raise MathBlueprintError(f"{node['id']}.source_contract must be source-verified")
    hypotheses = contract.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        raise MathBlueprintError(f"{node['id']}.source_contract.hypotheses must be a list")
    notation_mapping = contract.get("notation_mapping", {})
    if not isinstance(notation_mapping, dict):
        raise MathBlueprintError(f"{node['id']}.source_contract.notation_mapping must be an object")


def _validate_contexts(
    data: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    result = contexts(data)
    if not result:
        raise MathBlueprintError("an enabled math_profile requires at least one context")
    for context_id, context in result.items():
        assumptions = _as_string_list(context.get("assumptions", []), f"context {context_id}.assumptions")
        definitions = _as_string_list(context.get("definitions", []), f"context {context_id}.definitions")
        available_results = _as_string_list(
            context.get("available_results", []), f"context {context_id}.available_results"
        )
        goals = _as_string_list(context.get("goals", []), f"context {context_id}.goals")
        for node_id in assumptions:
            if node_id not in by_id or by_id[node_id].get("epistemic_type") != "problem_hypothesis":
                raise MathBlueprintError(
                    f"context {context_id}.assumptions must reference problem_hypothesis nodes; got {node_id}"
                )
        for node_id in definitions:
            if node_id not in by_id or by_id[node_id].get("epistemic_type") != DEFINITION_TYPE:
                raise MathBlueprintError(
                    f"context {context_id}.definitions must reference definition_contract nodes; got {node_id}"
                )
        for node_id in available_results:
            if node_id not in by_id or by_id[node_id].get("epistemic_type") not in CLAIM_TYPES:
                raise MathBlueprintError(
                    f"context {context_id}.available_results must reference mathematical claim nodes; got {node_id}"
                )
            if by_id[node_id].get("truth_status") not in TRUSTED_CLAIM_STATUSES:
                raise MathBlueprintError(
                    f"context {context_id}.available_results contains non-trusted claim {node_id}"
                )
        for node_id in goals:
            if node_id not in by_id or by_id[node_id].get("epistemic_type") != GOAL_TYPE:
                raise MathBlueprintError(f"context {context_id}.goals references non-goal node {node_id}")
    return result


def validate_math_blueprint(
    data: dict[str, Any], *, artifact_root: Path | None = None
) -> dict[str, Any]:
    """Validate the mathematics profile and return a deterministic summary."""

    profile = _profile(data)
    if profile is None:
        return {
            "enabled": False,
            "contexts": 0,
            "claims": 0,
            "inferences": 0,
            "open_inferences": 0,
            "proved_inferences": 0,
            "goals": 0,
        }

    by_id = index_nodes(data)
    edge_fields = edge_contracts(data)
    edges = set(edge_fields)
    for (source, target), role_field in sorted(edge_fields.items()):
        if source not in by_id or target not in by_id:
            raise MathBlueprintError(
                f"edge {source!r} -> {target!r} references an unknown node"
            )
        if role_field is not None:
            refs = by_id[target].get(role_field)
            if not isinstance(refs, list) or source not in refs:
                raise MathBlueprintError(
                    f"edge {source!r} -> {target!r} declares {role_field}, "
                    f"but {target}.{role_field} does not include {source}"
                )
    context_map = _validate_contexts(data, by_id)

    counts: dict[str, int] = defaultdict(int)
    inference_conclusions: dict[str, list[str]] = defaultdict(list)

    for node in by_id.values():
        epistemic_type = node.get("epistemic_type")
        if epistemic_type not in MATH_TYPES:
            continue
        context_id = node.get("context_id", "global")
        if context_id != "global" and context_id not in context_map:
            raise MathBlueprintError(f"{node['id']} references unknown context_id {context_id!r}")

        if epistemic_type in CLAIM_TYPES:
            counts["claims"] += 1
            truth_status = node.get("truth_status")
            if truth_status not in CLAIM_STATUSES:
                raise MathBlueprintError(f"{node['id']} has invalid truth_status {truth_status!r}")
            _require_status_sync(node, "truth_status")
            claim_kind = node.get("claim_kind")
            if claim_kind not in CLAIM_KINDS:
                raise MathBlueprintError(f"{node['id']} has invalid claim_kind {claim_kind!r}")
            if epistemic_type == "problem_hypothesis" and truth_status != "given":
                raise MathBlueprintError(f"{node['id']}: a problem hypothesis must have truth_status 'given'")
            if epistemic_type == "external_mathematical_result":
                if truth_status != "imported_verified":
                    raise MathBlueprintError(
                        f"{node['id']}: an external mathematical result must be imported_verified"
                    )
                _source_contract(node)
            if epistemic_type == "verified_counterexample":
                if truth_status != "established" or claim_kind != "counterexample":
                    raise MathBlueprintError(
                        f"{node['id']}: a verified counterexample must be an established counterexample claim"
                    )
                _artifact_contract(node, "certificate", artifact_root)
                refutes = _as_string_list(node.get("refutes", []), f"{node['id']}.refutes", nonempty=True)
                for target_id in refutes:
                    if target_id not in by_id or by_id[target_id].get("epistemic_type") not in CLAIM_TYPES:
                        raise MathBlueprintError(f"{node['id']}.refutes references non-claim {target_id}")
                    target_refutations = by_id[target_id].get("refutation_inputs", [])
                    if node["id"] not in target_refutations:
                        raise MathBlueprintError(
                            f"{target_id}.refutation_inputs must include counterexample {node['id']}"
                        )
                    if (node["id"], target_id) not in edges:
                        raise MathBlueprintError(
                            f"missing refutation edge {node['id']!r} -> {target_id!r}"
                        )
            if truth_status in {"given", "imported_verified", "established"} and node.get("grade") in {"D", "X"}:
                raise MathBlueprintError(f"{node['id']}: trusted claim cannot have grade {node.get('grade')}")
            if truth_status in {"open", "candidate_supported", "target"} and node.get("grade") != "D":
                raise MathBlueprintError(f"{node['id']}: open/candidate/target claims must have grade D")
            if truth_status in {"refuted", "contested", "superseded"} and node.get("grade") != "X":
                raise MathBlueprintError(f"{node['id']}: refuted/contested/superseded claims must have grade X")
            inference_inputs = _require_refs(
                node,
                "inference_inputs",
                by_id,
                edges,
                {INFERENCE_TYPE},
            )
            refutation_inputs = _require_refs(
                node,
                "refutation_inputs",
                by_id,
                edges,
                {"verified_counterexample", "mathematical_claim"},
            )
            if truth_status == "refuted" and not refutation_inputs and not node.get("negation_claim"):
                raise MathBlueprintError(
                    f"{node['id']}: a refuted claim requires refutation_inputs or negation_claim"
                )
            negation = node.get("negation_claim")
            if negation is not None and (
                negation not in by_id or by_id[negation].get("epistemic_type") not in CLAIM_TYPES
            ):
                raise MathBlueprintError(f"{node['id']}.negation_claim must reference a claim")
            if inference_inputs:
                counts["claims_with_inferences"] += 1

        elif epistemic_type == DEFINITION_TYPE:
            counts["definitions"] += 1
            if node.get("truth_bearing") is not False:
                raise MathBlueprintError(f"{node['id']}: a definition must set truth_bearing to false")
            source_kind = node.get("source_kind")
            if source_kind not in {"project", "problem", "literature"}:
                raise MathBlueprintError(f"{node['id']} has invalid definition source_kind {source_kind!r}")
            if source_kind == "literature":
                _source_contract(node)

        elif epistemic_type == INFERENCE_TYPE:
            counts["inferences"] += 1
            proof_status = node.get("proof_status")
            if proof_status not in INFERENCE_STATUSES:
                raise MathBlueprintError(f"{node['id']} has invalid proof_status {proof_status!r}")
            _require_status_sync(node, "proof_status")
            premises = _require_refs(
                node,
                "premise_inputs",
                by_id,
                edges,
                CLAIM_TYPES,
                nonempty=not bool(node.get("allows_empty_premises")),
            )
            _require_refs(
                node,
                "definition_inputs",
                by_id,
                edges,
                {DEFINITION_TYPE},
            )
            conclusion = node.get("conclusion")
            if conclusion not in by_id or by_id[conclusion].get("epistemic_type") not in CLAIM_TYPES:
                raise MathBlueprintError(f"{node['id']}.conclusion must reference a mathematical claim")
            if (node["id"], conclusion) not in edges:
                raise MathBlueprintError(
                    f"missing conclusion edge [{node['id']!r}, {conclusion!r}]"
                )
            if node["id"] not in by_id[conclusion].get("inference_inputs", []):
                raise MathBlueprintError(
                    f"{conclusion}.inference_inputs must include concluding inference {node['id']}"
                )
            inference_conclusions[conclusion].append(node["id"])
            if proof_status == "proved":
                counts["proved_inferences"] += 1
                _artifact_contract(node, "proof_package", artifact_root)
                if node.get("unresolved_obligations") != []:
                    raise MathBlueprintError(
                        f"{node['id']}: a proved inference must have unresolved_obligations == []"
                    )
                if node.get("grade") in {"D", "X"}:
                    raise MathBlueprintError(f"{node['id']}: a proved inference cannot have grade {node.get('grade')}")
            elif proof_status == "refuted":
                counts["refuted_inferences"] += 1
                _artifact_contract(node, "refutation_package", artifact_root)
                if node.get("grade") != "X":
                    raise MathBlueprintError(f"{node['id']}: a refuted inference must have grade X")
            elif proof_status == "blocked":
                counts["blocked_inferences"] += 1
                gap = node.get("precise_gap")
                if not isinstance(gap, str) or not gap.strip():
                    raise MathBlueprintError(f"{node['id']}: a blocked inference requires precise_gap")
                if not isinstance(node.get("resume_conditions"), list):
                    raise MathBlueprintError(f"{node['id']}: a blocked inference requires resume_conditions")
            else:
                counts["open_inferences"] += 1
            if proof_status in {"proposed", "open", "assigned", "candidate_proof", "blocked"}:
                if node.get("grade") != "D":
                    raise MathBlueprintError(
                        f"{node['id']}: unresolved inference status {proof_status!r} requires grade D"
                    )
            if proof_status in {"invalid", "superseded"} and node.get("grade") != "X":
                raise MathBlueprintError(
                    f"{node['id']}: {proof_status} inference must have grade X"
                )
            if proof_status != "proved" and node.get("proof_input_eligible") is True:
                raise MathBlueprintError(f"{node['id']}: an unproved inference cannot be proof-input eligible")
            if any(by_id[premise].get("truth_status") == "contested" for premise in premises):
                raise MathBlueprintError(f"{node['id']}: an inference cannot rely on a contested premise")

        elif epistemic_type == GOAL_TYPE:
            counts["goals"] += 1
            target = node.get("target_claim")
            if target not in by_id or by_id[target].get("epistemic_type") not in CLAIM_TYPES:
                raise MathBlueprintError(f"{node['id']}.target_claim must reference a mathematical claim")
            if node.get("mode") not in {"prove", "refute", "prove_or_refute"}:
                raise MathBlueprintError(f"{node['id']} has invalid goal mode")
            if node.get("goal_status") not in GOAL_STATUSES:
                raise MathBlueprintError(f"{node['id']} has invalid goal_status")
            _require_status_sync(node, "goal_status")
            if not isinstance(node.get("contract_version"), str) or not node["contract_version"].strip():
                raise MathBlueprintError(f"{node['id']} requires contract_version")
            if not isinstance(node.get("quantifier_contract"), str) or not node["quantifier_contract"].strip():
                raise MathBlueprintError(f"{node['id']} requires quantifier_contract")
            for field in ("boundary_cases", "completion_criteria", "non_completion_conditions"):
                values = node.get(field)
                if (
                    not isinstance(values, list)
                    or not values
                    or any(not isinstance(value, str) or not value.strip() for value in values)
                ):
                    raise MathBlueprintError(
                        f"{node['id']}.{field} must be a non-empty list of explicit statements"
                    )
            permitted_outcomes = node.get("permitted_outcomes")
            if (
                not isinstance(permitted_outcomes, list)
                or not permitted_outcomes
                or not set(permitted_outcomes).issubset(GOAL_OUTCOMES)
            ):
                raise MathBlueprintError(
                    f"{node['id']}.permitted_outcomes must use {sorted(GOAL_OUTCOMES)}"
                )
            required_outcome = {
                "prove": "proof",
                "refute": "refutation",
            }.get(node.get("mode"))
            if required_outcome and required_outcome not in permitted_outcomes:
                raise MathBlueprintError(
                    f"{node['id']}.permitted_outcomes must include {required_outcome!r}"
                )
            if node.get("mode") == "prove_or_refute" and not {
                "proof",
                "refutation",
            }.issubset(set(permitted_outcomes)):
                raise MathBlueprintError(
                    f"{node['id']} prove_or_refute mode requires proof and refutation outcomes"
                )
            if not isinstance(node.get("tool_constraints"), dict):
                raise MathBlueprintError(f"{node['id']}.tool_constraints must be an object")
            _require_refs(node, "target_inputs", by_id, edges, CLAIM_TYPES, nonempty=True)
            if target not in node.get("target_inputs", []):
                raise MathBlueprintError(f"{node['id']}.target_inputs must include target_claim")
            negation = node.get("negation_claim")
            if negation is not None and (
                negation not in by_id or by_id[negation].get("epistemic_type") not in CLAIM_TYPES
            ):
                raise MathBlueprintError(f"{node['id']}.negation_claim must reference a claim")

        elif epistemic_type == OBLIGATION_TYPE:
            counts["obligations"] += 1
            if node.get("obligation_status") not in OBLIGATION_STATUSES:
                raise MathBlueprintError(f"{node['id']} has invalid obligation_status")
            _require_status_sync(node, "obligation_status")
            if not isinstance(node.get("formal_statement"), str) or not node["formal_statement"].strip():
                raise MathBlueprintError(f"{node['id']} requires a formal_statement")
            discharge = node.get("discharge_criteria")
            if (
                not isinstance(discharge, list)
                or not discharge
                or any(not isinstance(item, str) or not item.strip() for item in discharge)
            ):
                raise MathBlueprintError(
                    f"{node['id']}.discharge_criteria must be a non-empty list"
                )
            strength = node.get("strength_relative_to_target")
            if strength not in OBLIGATION_STRENGTHS:
                raise MathBlueprintError(
                    f"{node['id']} has invalid strength_relative_to_target {strength!r}"
                )
            if strength in {"equivalent", "near_equivalent", "stronger"} and node.get(
                "obligation_status"
            ) not in {"blocked", "refuted", "superseded"}:
                raise MathBlueprintError(
                    f"{node['id']}: theorem-strength obligation must be blocked or retired"
                )
            if node.get("obligation_status") == "blocked":
                if not isinstance(node.get("precise_gap"), str) or not node["precise_gap"].strip():
                    raise MathBlueprintError(f"{node['id']}: blocked obligation requires precise_gap")
                if not isinstance(node.get("resume_conditions"), list):
                    raise MathBlueprintError(
                        f"{node['id']}: blocked obligation requires resume_conditions"
                    )
            _require_refs(
                node,
                "target_inputs",
                by_id,
                edges,
                {INFERENCE_TYPE, GOAL_TYPE, OBLIGATION_TYPE},
                nonempty=True,
            )

        elif epistemic_type == ATTEMPT_TYPE:
            counts["attempts"] += 1
            attempt_status = node.get("attempt_status")
            if attempt_status not in ATTEMPT_STATUSES:
                raise MathBlueprintError(f"{node['id']} has invalid attempt_status")
            _require_status_sync(node, "attempt_status")
            _require_refs(
                node,
                "target_inputs",
                by_id,
                edges,
                {INFERENCE_TYPE, GOAL_TYPE, OBLIGATION_TYPE},
                nonempty=True,
            )
            if not isinstance(node.get("method_family"), str) or not node["method_family"].strip():
                raise MathBlueprintError(f"{node['id']} requires method_family")
            for field in ("route_key", "deliverable_contract", "expected_bottleneck"):
                if not isinstance(node.get(field), str) or not node[field].strip():
                    raise MathBlueprintError(f"{node['id']} requires {field}")
            falsification_tests = node.get("falsification_tests")
            if (
                not isinstance(falsification_tests, list)
                or not falsification_tests
                or any(not isinstance(item, str) or not item.strip() for item in falsification_tests)
            ):
                raise MathBlueprintError(
                    f"{node['id']}.falsification_tests must be a non-empty list"
                )
            if not isinstance(node.get("provenance"), dict):
                raise MathBlueprintError(f"{node['id']}.provenance must be an object")
            if attempt_status in {"blocked", "refuted"}:
                if not isinstance(node.get("precise_gap"), str) or not node["precise_gap"].strip():
                    raise MathBlueprintError(f"{node['id']}: {attempt_status} route requires precise_gap")
                if not isinstance(node.get("resume_conditions"), list):
                    raise MathBlueprintError(
                        f"{node['id']}: {attempt_status} route requires resume_conditions"
                    )
            if attempt_status == "audited_failure":
                if not isinstance(node.get("first_failing_step"), str) or not node["first_failing_step"].strip():
                    raise MathBlueprintError(f"{node['id']}: audited_failure requires first_failing_step")
                if not isinstance(node.get("resume_conditions"), list):
                    raise MathBlueprintError(f"{node['id']}: audited_failure requires resume_conditions")

    for target, node in by_id.items():
        if node.get("epistemic_type") not in MATH_TYPES:
            continue
        for field in set(EDGE_ROLE_TO_FIELD.values()):
            refs = node.get(field)
            if refs is None:
                continue
            if not isinstance(refs, list):
                raise MathBlueprintError(f"{target}.{field} must be a list")
            for source in refs:
                pair = (source, target)
                if pair not in edge_fields:
                    raise MathBlueprintError(
                        f"missing edge {source!r} -> {target!r} for {target}.{field}"
                    )
                edge_field = edge_fields[pair]
                if edge_field is not None and edge_field != field:
                    raise MathBlueprintError(
                        f"edge {source!r} -> {target!r} declares {edge_field}, "
                        f"but {target} lists it under {field}"
                    )
                owner_context = node.get("context_id", "global")
                source_context = by_id[source].get("context_id", "global")
                if source_context != "global" and source_context != owner_context:
                    raise MathBlueprintError(
                        f"{target}.{field} cannot use {source} from context {source_context!r}; "
                        f"target context is {owner_context!r}"
                    )

    closure_summaries: dict[str, dict[str, Any]] = {}
    for context_id in context_map:
        closure = compute_trusted_closure(data, context_id)
        closure_summaries[context_id] = {
            "available_claim_ids": closure["available_claim_ids"],
            "used_inference_ids": closure["used_inference_ids"],
            "contradictions": closure["contradictions"],
        }
        available = set(closure["available_claim_ids"])
        for node in by_id.values():
            if node.get("context_id", "global") not in {"global", context_id}:
                continue
            if node.get("epistemic_type") not in CLAIM_TYPES:
                continue
            truth_status = node.get("truth_status")
            if truth_status == "established" and node["id"] not in available:
                raise MathBlueprintError(
                    f"{node['id']} is marked established but is not in the trusted closure of {context_id}"
                )
            if truth_status in {"open", "candidate_supported", "target"} and node["id"] in available:
                raise MathBlueprintError(
                    f"{node['id']} is available in {context_id} but still marked {truth_status}"
                )
        refuted = set(closure["refuted_claim_ids"])
        for node_id in sorted(refuted):
            node = by_id.get(node_id)
            if not node or node.get("context_id", "global") not in {"global", context_id}:
                continue
            if node.get("truth_status") not in {"refuted", "contested", "superseded"}:
                raise MathBlueprintError(
                    f"{node_id} has a trusted refutation in {context_id} but truth_status is "
                    f"{node.get('truth_status')!r}"
                )
        for node in by_id.values():
            if node.get("epistemic_type") not in CLAIM_TYPES:
                continue
            if node.get("context_id", "global") not in {"global", context_id}:
                continue
            if node.get("truth_status") != "refuted":
                continue
            witnesses = set(node.get("refutation_inputs", []))
            if node.get("negation_claim"):
                witnesses.add(node["negation_claim"])
            if not witnesses.intersection(available):
                raise MathBlueprintError(
                    f"{node['id']} is refuted without a trusted counterexample or negation in {context_id}"
                )
        for node in by_id.values():
            if node.get("epistemic_type") != GOAL_TYPE:
                continue
            if node.get("context_id", "global") not in {"global", context_id}:
                continue
            target = node.get("target_claim")
            negation = node.get("negation_claim")
            goal_status = node.get("goal_status")
            target_proved = target in available
            target_refuted = target in refuted or negation in available
            if goal_status == "solved" and not target_proved:
                raise MathBlueprintError(
                    f"{node['id']} is solved but target {target} is outside the trusted closure"
                )
            if goal_status == "refuted" and not target_refuted:
                raise MathBlueprintError(
                    f"{node['id']} is refuted without a trusted negation or verified refutation"
                )
            if target_proved and goal_status != "solved":
                raise MathBlueprintError(
                    f"{node['id']} target is proved but goal_status is {goal_status!r}"
                )
            if target_refuted and not target_proved and goal_status != "refuted":
                raise MathBlueprintError(
                    f"{node['id']} target is refuted but goal_status is {goal_status!r}"
                )

    return {
        "enabled": True,
        "schema_version": MATH_PROFILE_SCHEMA,
        "contexts": len(context_map),
        "claims": counts["claims"],
        "definitions": counts["definitions"],
        "inferences": counts["inferences"],
        "open_inferences": counts["open_inferences"],
        "proved_inferences": counts["proved_inferences"],
        "refuted_inferences": counts["refuted_inferences"],
        "blocked_inferences": counts["blocked_inferences"],
        "obligations": counts["obligations"],
        "attempts": counts["attempts"],
        "goals": counts["goals"],
        "closure_by_context": closure_summaries,
    }


def _context_nodes(
    data: dict[str, Any], context_id: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_id = index_nodes(data)
    context_map = contexts(data)
    if context_id not in context_map:
        raise MathBlueprintError(f"unknown mathematics context {context_id!r}")
    return by_id, context_map[context_id]


def compute_trusted_closure(data: dict[str, Any], context_id: str | None = None) -> dict[str, Any]:
    """Compute the trusted claim closure for one mathematics context."""

    resolved_context = resolve_context_id(data, context_id)
    by_id, context = _context_nodes(data, resolved_context)
    seeds = set(context.get("assumptions", [])) | set(context.get("available_results", []))
    seeds.update(
        node_id
        for node_id, node in by_id.items()
        if node.get("context_id", "global") in {"global", resolved_context}
        and (
            node.get("epistemic_type") == "problem_hypothesis"
            or node.get("epistemic_type") == "external_mathematical_result"
            or node.get("epistemic_type") == "verified_counterexample"
        )
    )
    available = {
        node_id
        for node_id in seeds
        if node_id in by_id and by_id[node_id].get("truth_status") in TRUSTED_CLAIM_STATUSES
    }
    proved_inferences = [
        node
        for node in by_id.values()
        if node.get("epistemic_type") == INFERENCE_TYPE
        and node.get("proof_status") == "proved"
        and node.get("context_id", "global") in {"global", resolved_context}
    ]
    used: set[str] = set()
    changed = True
    while changed:
        changed = False
        for inference in sorted(proved_inferences, key=lambda node: node["id"]):
            conclusion = inference.get("conclusion")
            premises = set(inference.get("premise_inputs", []))
            if conclusion in available or not premises.issubset(available):
                continue
            conclusion_node = by_id.get(conclusion)
            if not conclusion_node or conclusion_node.get("truth_status") in {"refuted", "contested", "superseded"}:
                continue
            available.add(conclusion)
            used.add(inference["id"])
            changed = True

    refuted: set[str] = set()
    for node in by_id.values():
        if node.get("epistemic_type") == "verified_counterexample" and node["id"] in available:
            refuted.update(node.get("refutes", []))
        if (
            node.get("epistemic_type") in CLAIM_TYPES
            and node.get("truth_status") == "refuted"
            and node.get("context_id", "global") in {"global", resolved_context}
        ):
            refuted.add(node["id"])
    contradictions = sorted(available & refuted)
    available -= refuted
    return {
        "context_id": resolved_context,
        "seed_claim_ids": sorted(seeds),
        "available_claim_ids": sorted(available),
        "used_inference_ids": sorted(used),
        "refuted_claim_ids": sorted(refuted),
        "contradictions": contradictions,
    }


def _goal_target(
    by_id: dict[str, dict[str, Any]], goal_or_claim_id: str
) -> tuple[str, str | None]:
    node = by_id.get(goal_or_claim_id)
    if node is None:
        raise MathBlueprintError(f"unknown goal or claim {goal_or_claim_id!r}")
    if node.get("epistemic_type") == GOAL_TYPE:
        return node["target_claim"], node["id"]
    if node.get("epistemic_type") in CLAIM_TYPES:
        return node["id"], None
    raise MathBlueprintError(f"{goal_or_claim_id} is not a research goal or mathematical claim")


def compute_frontier(
    data: dict[str, Any], goal_or_claim_id: str, context_id: str | None = None
) -> dict[str, Any]:
    """Return the backward proof slice and open inference frontier for a goal."""

    resolved_context = resolve_context_id(data, context_id)
    by_id, _ = _context_nodes(data, resolved_context)
    target_claim, goal_id = _goal_target(by_id, goal_or_claim_id)
    closure = compute_trusted_closure(data, resolved_context)
    available = set(closure["available_claim_ids"])
    refuted_claims = set(closure["refuted_claim_ids"])
    goal_node = by_id.get(goal_id) if goal_id else None
    goal_mode = goal_node.get("mode") if goal_node else "prove"
    if target_claim in available:
        research_outcome = "proved"
    elif target_claim in refuted_claims or (
        goal_node is not None and goal_node.get("negation_claim") in available
    ):
        research_outcome = "refuted"
    else:
        research_outcome = "open"
    goal_resolved = research_outcome != "open"
    requested_mode_satisfied = (
        research_outcome == "proved" and goal_mode in {"prove", "prove_or_refute"}
    ) or (
        research_outcome == "refuted" and goal_mode in {"refute", "prove_or_refute"}
    )

    by_conclusion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in by_id.values():
        if (
            node.get("epistemic_type") == INFERENCE_TYPE
            and node.get("context_id", "global") in {"global", resolved_context}
        ):
            by_conclusion[node.get("conclusion")].append(node)

    inference_ids: set[str] = set()
    claim_ids: set[str] = {target_claim}
    missing_routes: set[str] = set()
    distance_to_goal: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(target_claim, 0)])
    visited_claims: set[str] = set()
    while queue:
        claim_id, distance = queue.popleft()
        if claim_id in visited_claims:
            continue
        visited_claims.add(claim_id)
        routes = sorted(by_conclusion.get(claim_id, []), key=lambda node: node["id"])
        if not routes and claim_id not in available and claim_id not in refuted_claims:
            missing_routes.add(claim_id)
        for inference in routes:
            inference_ids.add(inference["id"])
            distance_to_goal[inference["id"]] = min(
                distance_to_goal.get(inference["id"], distance), distance
            )
            for premise in inference.get("premise_inputs", []):
                claim_ids.add(premise)
                if premise not in available:
                    queue.append((premise, distance + 1))

    frontier: list[dict[str, Any]] = []
    proved: list[str] = []
    refuted: list[str] = []
    for inference_id in sorted(inference_ids):
        node = by_id[inference_id]
        status = node.get("proof_status")
        premises = set(node.get("premise_inputs", []))
        if status == "proved":
            proved.append(inference_id)
            continue
        if status == "refuted":
            refuted.append(inference_id)
        frontier.append(
            {
                "inference_id": inference_id,
                "statement": node.get("statement", ""),
                "proof_status": status,
                "premise_ids": sorted(premises),
                "conclusion_id": node.get("conclusion"),
                "premises_available": premises.issubset(available),
                "ready_for_propagation": premises.issubset(available),
                "truth_propagating_now": False,
                "conditional_researchable": status
                in {"proposed", "open", "assigned", "candidate_proof"},
                "assignment_ready": (
                    not goal_resolved
                    and premises.issubset(available)
                    and status in {"proposed", "open", "candidate_proof"}
                ),
                "needed_for_current_goal": not goal_resolved,
                "distance_to_goal": distance_to_goal.get(inference_id, 0),
                "precise_gap": node.get("precise_gap"),
                "resume_conditions": node.get("resume_conditions", []),
            }
        )
    status_order = {
        "candidate_proof": 0,
        "open": 1,
        "proposed": 2,
        "assigned": 3,
        "blocked": 4,
        "refuted": 5,
        "invalid": 6,
        "superseded": 7,
    }
    frontier.sort(
        key=lambda item: (
            0 if item["ready_for_propagation"] else 1,
            status_order.get(item["proof_status"], 99),
            item["distance_to_goal"],
            item["inference_id"],
        )
    )
    return {
        "context_id": resolved_context,
        "goal_id": goal_id,
        "goal_mode": goal_mode,
        "target_claim_id": target_claim,
        "target_available": target_claim in available,
        "research_outcome": research_outcome,
        "goal_resolved": goal_resolved,
        "requested_mode_satisfied": requested_mode_satisfied,
        "trusted_closure": closure,
        "claim_ids": sorted(claim_ids),
        "inference_ids": sorted(inference_ids),
        "proved_inference_ids": proved,
        "refuted_inference_ids": refuted,
        "missing_route_claim_ids": sorted(missing_routes),
        "frontier": frontier,
    }


def math_node_semantics(
    data: dict[str, Any], node_id: str, context_id: str | None = None
) -> dict[str, Any] | None:
    """Return computed trust semantics for one mathematics node."""

    by_id = index_nodes(data)
    node = by_id.get(node_id)
    if node is None or node.get("epistemic_type") not in MATH_TYPES:
        return None
    resolved_context = resolve_context_id(data, context_id)
    closure = compute_trusted_closure(data, resolved_context)
    available = set(closure["available_claim_ids"])
    epistemic_type = node.get("epistemic_type")
    if epistemic_type in CLAIM_TYPES:
        return {
            "context_id": resolved_context,
            "record_kind": "claim",
            "truth_status": node.get("truth_status"),
            "proof_input_eligible": node_id in available,
            "refuted_in_context": node_id in set(closure["refuted_claim_ids"]),
        }
    if epistemic_type == DEFINITION_TYPE:
        context = contexts(data)[resolved_context]
        eligible_definitions = set(context.get("definitions", [])) | {
            candidate_id
            for candidate_id, candidate in by_id.items()
            if candidate.get("epistemic_type") == DEFINITION_TYPE
            and candidate.get("context_id", "global") in {"global", resolved_context}
        }
        return {
            "context_id": resolved_context,
            "record_kind": "definition",
            "truth_bearing": False,
            "definition_input_eligible": node_id in eligible_definitions,
        }
    if epistemic_type == INFERENCE_TYPE:
        return {
            "context_id": resolved_context,
            "record_kind": "inference",
            "proof_status": node.get("proof_status"),
            "truth_propagating": node.get("proof_status") == "proved",
        }
    return {
        "context_id": resolved_context,
        "record_kind": node.get("type", epistemic_type),
        "proof_input_eligible": False,
    }


def trusted_math_node_ids(data: dict[str, Any], context_id: str | None = None) -> set[str]:
    """Return claim, definition, and proved-inference IDs safe for proof retrieval."""

    resolved_context = resolve_context_id(data, context_id)
    by_id, context = _context_nodes(data, resolved_context)
    closure = compute_trusted_closure(data, resolved_context)
    trusted = set(closure["available_claim_ids"]) | set(context.get("definitions", []))
    trusted.update(
        node_id
        for node_id, node in by_id.items()
        if node.get("epistemic_type") == DEFINITION_TYPE
        and node.get("context_id", "global") in {"global", resolved_context}
    )
    trusted.update(
        node_id
        for node_id, node in by_id.items()
        if node.get("epistemic_type") == INFERENCE_TYPE
        and node.get("proof_status") == "proved"
        and node.get("context_id", "global") in {"global", resolved_context}
    )
    return trusted


def iter_math_nodes(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for node in data.get("nodes", []):
        if isinstance(node, dict) and node.get("epistemic_type") in MATH_TYPES:
            yield node
