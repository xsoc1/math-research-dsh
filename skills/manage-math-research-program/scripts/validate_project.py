#!/usr/bin/env python3
"""Validate a manage-math-research-program repository using the standard library."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FILES = [
    "project.json",
    "PROJECT.md",
    "state/current.json",
    "state/RESUME.md",
    "state/activity.jsonl",
    "index/papers.json",
    "index/paper-relations.json",
    "index/open-problems.json",
    "index/tools.json",
    "index/task-packets.json",
    "index/runs.json",
    "index/artifacts.json",
    "literature/maps/PAPER_MAP.md",
    "literature/maps/FRONTIER.md",
    "agenda/DIRECTIONS.md",
    "agenda/PRIORITIES.md",
    "knowledge/GLOSSARY.md",
    "knowledge/FAILURE_PATTERNS.md",
    "knowledge/.blueprint/config.json",
    "knowledge/blueprint.json",
    "knowledge/evidence_inventory.csv",
    "knowledge/blueprint_update_requests.jsonl",
]

REQUIRED_DIRECTORIES = [
    "state/checkpoints",
    "state/stage-summaries",
    "literature/search-log",
    "literature/papers",
    "agenda/problems",
    "agenda/task-packets",
    "knowledge/tools",
    "knowledge/submissions",
    "knowledge/backups",
    "knowledge/viewer",
    "knowledge/artifacts",
    "runs/rigorous-open-math-research",
    "reports",
    "archive/superseded",
    "archive/rejected-duplicates",
]

INDEX_ID_FIELDS = {
    "papers.json": "paper_id",
    "paper-relations.json": "relation_id",
    "open-problems.json": "problem_id",
    "tools.json": "tool_id",
    "task-packets.json": "task_id",
    "runs.json": "run_id",
    "artifacts.json": "artifact_id",
}

PROTECTED_UPSTREAM_FILENAMES = {
    "problem_contract.md",
    "repro_manifest.md",
    "status_and_literature.md",
    "obligation_graph.md",
    "approach_registry.md",
    "research_ledger.md",
    "counterexample_log.md",
    "candidate_proof.md",
    "audit_report.md",
}

PATH_KEYS = {
    "record_path",
    "analysis_path",
    "task_packet_path",
    "run_root",
    "manifest_path",
    "artifact_path",
    "local_path",
    "proof_path",
    "audit_path",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.info.append(message)


def load_json(path: Path, report: Report) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.error(f"Missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        report.error(f"Invalid JSON in {path}: {exc}")
    except OSError as exc:
        report.error(f"Cannot read {path}: {exc}")
    return None


def normalize_doi(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    return value


def normalize_arxiv(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^arxiv:\s*", "", value)
    value = re.sub(r"v\d+$", "", value)
    return value


def iter_path_values(obj: Any) -> Iterable[tuple[str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in PATH_KEYS and isinstance(value, str) and value:
                yield key, value
            elif key == "artifacts" and isinstance(value, list):
                for item in value:
                    yield from iter_path_values(item)
            else:
                yield from iter_path_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_path_values(item)


def looks_external(value: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.I)) or value.startswith("external:")


def resolve_project_path(root: Path, value: str) -> Path:
    candidate = Path(os.path.expanduser(value))
    return candidate if candidate.is_absolute() else root / candidate


def validate_index(path: Path, report: Report) -> list[dict[str, Any]]:
    data = load_json(path, report)
    if data is None:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        report.error(f"Index must contain an items array: {path}")
        return []

    items = [item for item in data["items"] if isinstance(item, dict)]
    if len(items) != len(data["items"]):
        report.error(f"Every item must be an object: {path}")

    id_field = INDEX_ID_FIELDS[path.name]
    seen: dict[str, int] = {}
    for position, item in enumerate(items):
        identifier = item.get(id_field)
        if not isinstance(identifier, str) or not identifier.strip():
            report.error(f"{path}: item {position} lacks nonempty {id_field}")
            continue
        if identifier in seen:
            report.error(f"{path}: duplicate {id_field} {identifier!r} at items {seen[identifier]} and {position}")
        seen[identifier] = position
    return items



def hydrate_json_record(root: Path, item: dict[str, Any], report: Report) -> dict[str, Any]:
    """Merge a JSON record referenced by record_path into its index item.

    Index values take precedence so that current lifecycle fields in the index are not
    overwritten by a stale detailed record. Missing or non-JSON records are reported
    elsewhere as path warnings and are left untouched here.
    """
    record_path = item.get("record_path")
    if not isinstance(record_path, str) or not record_path or looks_external(record_path):
        return item
    resolved = resolve_project_path(root, record_path)
    if not resolved.is_file() or resolved.suffix.lower() != ".json":
        return item
    data = load_json(resolved, report)
    if not isinstance(data, dict):
        return item
    merged = dict(data)
    merged.update(item)
    return merged

def validate_paper_duplicates(items: list[dict[str, Any]], report: Report) -> None:
    seen: dict[tuple[str, str], str] = {}
    hashes: dict[str, str] = {}
    for item in items:
        paper_id = str(item.get("paper_id", "<unknown>"))
        identifiers = item.get("identifiers") or {}
        candidates = []
        if isinstance(identifiers, dict):
            doi = identifiers.get("doi")
            arxiv = identifiers.get("arxiv_work_id")
            mr = identifiers.get("mr")
            zb = identifiers.get("zbmath")
            if isinstance(doi, str) and doi.strip():
                candidates.append(("doi", normalize_doi(doi)))
            if isinstance(arxiv, str) and arxiv.strip():
                candidates.append(("arxiv", normalize_arxiv(arxiv)))
            if isinstance(mr, str) and mr.strip():
                candidates.append(("mr", mr.strip().lower()))
            if isinstance(zb, str) and zb.strip():
                candidates.append(("zbmath", zb.strip().lower()))
        canonical = item.get("canonical_identity")
        if isinstance(canonical, dict) and canonical.get("kind") and canonical.get("value"):
            candidates.append((str(canonical["kind"]).lower(), str(canonical["value"]).strip().lower()))
        for key in candidates:
            if key in seen and seen[key] != paper_id:
                report.error(f"Duplicate paper identity {key[0]}={key[1]!r}: {seen[key]} and {paper_id}")
            seen[key] = paper_id

        for version in item.get("versions") or []:
            if not isinstance(version, dict):
                continue
            digest = version.get("sha256")
            if isinstance(digest, str) and digest:
                digest = digest.lower()
                if digest in hashes and hashes[digest] != paper_id:
                    report.warn(f"Identical paper source hash appears under {hashes[digest]} and {paper_id}: {digest}")
                hashes[digest] = paper_id


def validate_tool_duplicates(items: list[dict[str, Any]], report: Report) -> None:
    seen: dict[str, str] = {}
    for item in items:
        tool_id = str(item.get("tool_id", "<unknown>"))
        key = item.get("canonical_key")
        if not isinstance(key, str) or not key.strip():
            report.warn(f"Tool {tool_id} has no canonical_key; deduplication is weakened")
            continue
        normalized = re.sub(r"\s+", " ", key.strip().lower())
        if normalized in seen and seen[normalized] != tool_id:
            report.error(f"Duplicate tool canonical_key for {seen[normalized]} and {tool_id}: {key!r}")
        seen[normalized] = tool_id


def validate_paths(root: Path, index_items: dict[str, list[dict[str, Any]]], report: Report) -> None:
    for index_name, items in index_items.items():
        for item in items:
            identifier = next((str(item.get(field)) for field in INDEX_ID_FIELDS.values() if item.get(field)), "<unknown>")
            for key, value in iter_path_values(item):
                if looks_external(value):
                    continue
                resolved = resolve_project_path(root, value)
                if not resolved.exists():
                    report.warn(f"{index_name}:{identifier} has unresolved {key}: {value}")


def validate_protected_names(root: Path, report: Report) -> None:
    allowed_root = (root / "runs/rigorous-open-math-research").resolve()
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in PROTECTED_UPSTREAM_FILENAMES:
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(allowed_root)
        except ValueError:
            report.error(f"Protected upstream artifact appears outside registered upstream run area: {path}")


def validate_activity_log(path: Path, report: Report) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.error(f"Cannot read activity log {path}: {exc}")
        return
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            report.error(f"Invalid JSONL at {path}:{lineno}: {exc}")
            continue
        minutes = item.get("effective_minutes") if isinstance(item, dict) else None
        if minutes is not None and (not isinstance(minutes, (int, float)) or minutes < 0):
            report.error(f"Invalid effective_minutes at {path}:{lineno}")



KNOWLEDGE_TOOL_FILES = [
    "blueprint_common.py",
    "blueprint_query.py",
    "math_blueprint.py",
    "receive_blueprint.py",
    "validate_blueprint.py",
]


def validate_knowledge_base(root: Path, report: Report) -> None:
    knowledge_root = root / "knowledge"
    config = load_json(knowledge_root / ".blueprint" / "config.json", report)
    if not isinstance(config, dict):
        return
    canonical_name = config.get("canonical_blueprint")
    inventory_name = config.get("evidence_inventory")
    if not isinstance(canonical_name, str) or not (knowledge_root / canonical_name).is_file():
        report.error(f"knowledge config canonical_blueprint does not resolve: {canonical_name!r}")
    if not isinstance(inventory_name, str) or not (knowledge_root / inventory_name).is_file():
        report.error(f"knowledge config evidence_inventory does not resolve: {inventory_name!r}")
    for tool in KNOWLEDGE_TOOL_FILES:
        if not (knowledge_root / "tools" / tool).is_file():
            report.error(f"Missing knowledge tool: knowledge/tools/{tool}")
    if not isinstance(canonical_name, str) or not isinstance(inventory_name, str):
        return
    validator = knowledge_root / "tools" / "validate_blueprint.py"
    command = [
        sys.executable,
        str(validator),
        "--blueprint", str(knowledge_root / canonical_name),
        "--inventory", str(knowledge_root / inventory_name),
        "--artifact-root", str(knowledge_root),
    ]
    try:
        completed = subprocess.run(
            command, cwd=knowledge_root, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        report.error(f"Cannot run knowledge validator: {exc}")
        return
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        report.error("Knowledge base validation failed: " + (detail[-1] if detail else "unknown"))
    else:
        try:
            summary = json.loads(completed.stdout.strip())
            report.note(
                f"Knowledge base consistent: {summary.get('nodes')} nodes, "
                f"{summary.get('edges')} edges, {summary.get('inventory_rows')} inventory rows"
            )
        except (json.JSONDecodeError, TypeError):
            pass


def validate_knowledge_event_log(path: Path, report: Report) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.error(f"Cannot read knowledge event log {path}: {exc}")
        return
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            report.error(f"Invalid JSONL at {path}:{lineno}: {exc}")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output")
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    report = Report()
    if not root.is_dir():
        report.error(f"Project root is not a directory: {root}")
    else:
        for relative in REQUIRED_FILES:
            if not (root / relative).is_file():
                report.error(f"Missing required file: {relative}")
        for relative in REQUIRED_DIRECTORIES:
            if not (root / relative).is_dir():
                report.error(f"Missing required directory: {relative}")

        project = load_json(root / "project.json", report)
        current = load_json(root / "state/current.json", report)
        if isinstance(project, dict) and isinstance(current, dict):
            if project.get("project_id") != current.get("project_id"):
                report.error("project.json and state/current.json have different project_id values")
            target = (project.get("research_budget") or {}).get("target_hours")
            if target == 8 and (project.get("research_budget") or {}).get("configured_by") in {None, "unset", "default"}:
                report.warn("An 8-hour target exists without explicit configuration provenance; verify it is project-specific")

        index_items: dict[str, list[dict[str, Any]]] = {}
        for name in INDEX_ID_FIELDS:
            index_items[name] = validate_index(root / "index" / name, report)

        hydrated_papers = [
            hydrate_json_record(root, item, report) for item in index_items["papers.json"]
        ]
        validate_paper_duplicates(hydrated_papers, report)
        validate_tool_duplicates(index_items["tools.json"], report)
        validate_paths(root, index_items, report)
        validate_protected_names(root, report)
        validate_activity_log(root / "state/activity.jsonl", report)
        validate_knowledge_base(root, report)
        validate_knowledge_event_log(root / "knowledge/blueprint_update_requests.jsonl", report)

        resume_text = ""
        try:
            resume_text = (root / "state/RESUME.md").read_text(encoding="utf-8")
        except OSError:
            pass
        if isinstance(current, dict):
            checkpoint = current.get("latest_checkpoint_path")
            if isinstance(checkpoint, str) and checkpoint and checkpoint not in resume_text:
                report.warn("Latest checkpoint path from state/current.json is not mentioned in state/RESUME.md")

    payload = {
        "project_root": str(root),
        "valid": not report.errors,
        "errors": report.errors,
        "warnings": report.warnings,
        "info": report.info,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Project: {root}")
        print(f"Status: {'VALID' if not report.errors else 'INVALID'}")
        for message in report.errors:
            print(f"ERROR: {message}")
        for message in report.warnings:
            print(f"WARNING: {message}")
        if not report.errors and not report.warnings:
            print("No integrity or boundary issues found.")

    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
