#!/usr/bin/env python3
"""Seal and verify an exact-copy formalization handoff across logical roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
HANDOFF_ID_RE = re.compile(r"^FH-[A-Za-z0-9][A-Za-z0-9._-]{7,}$")
PROJECT_MARKERS = ("blueprint-project.json", "project.json")
FORMALIZATION_STATES = {"scaffold"}


class HandoffError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path, context: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"{context} is not readable JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HandoffError(f"{context} must be a JSON object")
    return data


def portable_path(value: str, context: str) -> str:
    normalized = value.replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise HandoffError(f"{context} must be a non-empty relative path")
    return normalized


def resolve_inside(root: Path, value: str, context: str) -> Path:
    normalized = portable_path(value, context)
    target = root.joinpath(*[part for part in normalized.split("/") if part]).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise HandoffError(f"{context} escapes its logical root: {value}") from exc
    return target


def resolve_file(root: Path, value: str, context: str) -> Path:
    target = resolve_inside(root, value, context)
    if not target.is_file():
        raise HandoffError(f"{context} is missing: {value}")
    return target


def nested_git_root(project_root: Path, logical_root: Path) -> Path | None:
    current = logical_root
    while current != project_root:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def resolve_logical_root(project_root: Path, value: str, context: str) -> Path:
    logical_root = resolve_inside(project_root, value, context)
    if not logical_root.is_dir():
        raise HandoffError(f"{context} is not a directory: {value}")
    nested = nested_git_root(project_root, logical_root)
    if nested is not None:
        raise HandoffError(
            f"{context} enters nested git repository: {nested.relative_to(project_root)}"
        )
    return logical_root


def root_relative(project_root: Path, logical_root: Path) -> str:
    relative = logical_root.relative_to(project_root)
    return relative.as_posix() if relative.parts else "."


def file_binding(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def project_marker(root: Path) -> tuple[Path, str]:
    for name in PROJECT_MARKERS:
        path = root / name
        if not path.is_file():
            continue
        data = load_json(path, f"project marker {name}")
        project_id = data.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            raise HandoffError(f"project marker {name} has no project_id")
        return path, project_id.strip()
    joined = " or ".join(PROJECT_MARKERS)
    raise HandoffError(f"logical project root has no {joined}")


def marker_record(root: Path) -> dict[str, str]:
    path, project_id = project_marker(root)
    record = file_binding(root, path)
    record["project_id"] = project_id
    return record


def verify_binding(root: Path, binding: Any, context: str) -> Path:
    if not isinstance(binding, dict):
        raise HandoffError(f"{context} must be a path/hash object")
    path_value = binding.get("path")
    expected = binding.get("sha256")
    if not isinstance(path_value, str):
        raise HandoffError(f"{context} has no path")
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise HandoffError(f"{context} has no valid SHA-256")
    path = resolve_file(root, path_value, context)
    actual = sha256_file(path)
    if actual != expected.upper():
        raise HandoffError(
            f"{context} hash mismatch: {actual} != {expected.upper()}"
        )
    return path


def verify_marker(root: Path, record: Any, context: str) -> None:
    path = verify_binding(root, record, context)
    data = load_json(path, context)
    project_id = data.get("project_id")
    if not isinstance(record, dict) or project_id != record.get("project_id"):
        raise HandoffError(f"{context} project_id does not match the marker")


def manifest_artifact(
    manifest: dict[str, Any], path_value: str, expected_hash: str, context: str
) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise HandoffError("source run manifest has no artifacts array")
    normalized = path_value.replace("\\", "/")
    matches = [
        item
        for item in artifacts
        if isinstance(item, dict)
        and str(item.get("artifact_path", "")).replace("\\", "/") == normalized
    ]
    if len(matches) != 1:
        raise HandoffError(f"{context} must appear exactly once in manifest artifacts")
    recorded_hash = str(matches[0].get("sha256", ""))
    if recorded_hash.upper() != expected_hash.upper():
        raise HandoffError(f"{context} hash disagrees with the source run manifest")


def canonical_timestamp(value: str | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        normalized = re.sub(r"(\.\d{6})\d+(?=[+-]\d{2}:\d{2}$)", r"\1", normalized)
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise HandoffError(f"created_at is not an ISO-8601 timestamp: {value}") from exc
        if parsed.tzinfo is None:
            raise HandoffError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def parse_registration(value: str) -> tuple[str, str]:
    if "::" not in value:
        raise HandoffError("registration must use PATH::ANCHOR")
    path_value, anchor = value.split("::", 1)
    if not path_value.strip() or not anchor.strip():
        raise HandoffError("registration PATH and ANCHOR must be non-empty")
    return path_value.strip(), anchor.strip()


def registration_record(root: Path, value: str) -> dict[str, str]:
    path_value, anchor = parse_registration(value)
    path = resolve_file(root, path_value, "destination registration")
    text = path.read_text(encoding="utf-8", errors="replace")
    if anchor not in text:
        raise HandoffError(
            f"destination registration anchor is absent from {path_value}: {anchor}"
        )
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256_at_seal": sha256_file(path),
        "required_anchor": anchor,
    }


def verify_registration(root: Path, record: Any, context: str) -> None:
    if not isinstance(record, dict):
        raise HandoffError(f"{context} must be an object")
    path_value = record.get("path")
    anchor = record.get("required_anchor")
    sealed_hash = record.get("sha256_at_seal")
    if not isinstance(path_value, str) or not isinstance(anchor, str) or not anchor:
        raise HandoffError(f"{context} has no path or required_anchor")
    if not isinstance(sealed_hash, str) or not SHA256_RE.fullmatch(sealed_hash):
        raise HandoffError(f"{context} has no valid sha256_at_seal")
    path = resolve_file(root, path_value, context)
    if anchor not in path.read_text(encoding="utf-8", errors="replace"):
        raise HandoffError(f"{context} required anchor is missing: {anchor}")


def git_head(project_root: Path) -> str | None:
    process = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if process.returncode != 0:
        return None
    value = process.stdout.strip()
    return value if re.fullmatch(r"[0-9A-Fa-f]{40}", value) else None


def build_record(args: argparse.Namespace, project_root: Path) -> dict[str, Any]:
    if not HANDOFF_ID_RE.fullmatch(args.handoff_id):
        raise HandoffError("handoff_id must match FH- plus at least eight ID characters")
    source_root = resolve_logical_root(
        project_root, args.source_root, "source logical root"
    )
    destination_root = resolve_logical_root(
        project_root, args.destination_root, "destination logical root"
    )
    if source_root == destination_root:
        raise HandoffError("source and destination logical roots must differ")

    manifest_path = resolve_file(
        source_root, args.source_manifest, "source run manifest"
    )
    manifest = load_json(manifest_path, "source run manifest")
    status = manifest.get("formalization")
    if status not in FORMALIZATION_STATES:
        raise HandoffError(
            "source run manifest formalization must be scaffold"
        )
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise HandoffError("source run manifest has no run_id")
    artifact_value = manifest.get("formalization_manifest")
    if not isinstance(artifact_value, str) or not artifact_value.strip():
        raise HandoffError("source run manifest has no formalization_manifest")
    source_artifact = resolve_file(
        source_root, artifact_value, "source formalization artifact"
    )
    source_artifact_hash = sha256_file(source_artifact)
    manifest_artifact(
        manifest,
        source_artifact.relative_to(source_root).as_posix(),
        source_artifact_hash,
        "source formalization artifact",
    )

    source_proof = resolve_file(source_root, args.source_proof, "source proof")
    source_proof_hash = sha256_file(source_proof)
    manifest_artifact(
        manifest,
        source_proof.relative_to(source_root).as_posix(),
        source_proof_hash,
        "source proof",
    )

    destination_artifact = resolve_file(
        destination_root, args.destination_artifact, "destination formalization artifact"
    )
    destination_hash = sha256_file(destination_artifact)
    if destination_hash != source_artifact_hash:
        raise HandoffError(
            "exact-copy handoff requires identical source and destination artifact hashes"
        )
    registrations = [
        registration_record(destination_root, item) for item in args.registration
    ]
    if not registrations:
        raise HandoffError("at least one destination registration is required")

    record: dict[str, Any] = {
        "schema_version": 1,
        "handoff_id": args.handoff_id,
        "created_at": canonical_timestamp(args.created_at),
        "copy_mode": "exact",
        "source": {
            "logical_root": root_relative(project_root, source_root),
            "project_marker": marker_record(source_root),
            "run_id": run_id.strip(),
            "run_manifest": file_binding(source_root, manifest_path),
            "formalization_status": status,
            "proof": file_binding(source_root, source_proof),
            "formalization_artifact": file_binding(source_root, source_artifact),
        },
        "destination": {
            "logical_root": root_relative(project_root, destination_root),
            "project_marker": marker_record(destination_root),
            "formalization_artifact": file_binding(
                destination_root, destination_artifact
            ),
            "registrations": registrations,
        },
    }
    head = git_head(project_root)
    if head is not None:
        record["repository_head_at_seal"] = head
    return record


def verify_record(project_root: Path, record: dict[str, Any]) -> None:
    if record.get("schema_version") != 1:
        raise HandoffError("schema_version must be 1")
    handoff_id = record.get("handoff_id")
    if not isinstance(handoff_id, str) or not HANDOFF_ID_RE.fullmatch(handoff_id):
        raise HandoffError("handoff_id is invalid")
    canonical_timestamp(str(record.get("created_at", "")))
    if record.get("copy_mode") != "exact":
        raise HandoffError("only copy_mode exact is supported")
    source = record.get("source")
    destination = record.get("destination")
    if not isinstance(source, dict) or not isinstance(destination, dict):
        raise HandoffError("source and destination must be objects")
    source_value = source.get("logical_root")
    destination_value = destination.get("logical_root")
    if not isinstance(source_value, str) or not isinstance(destination_value, str):
        raise HandoffError("source and destination logical roots are missing")
    source_root = resolve_logical_root(project_root, source_value, "source logical root")
    destination_root = resolve_logical_root(
        project_root, destination_value, "destination logical root"
    )
    if source_root == destination_root:
        raise HandoffError("source and destination logical roots must differ")
    verify_marker(source_root, source.get("project_marker"), "source project marker")
    verify_marker(
        destination_root,
        destination.get("project_marker"),
        "destination project marker",
    )
    manifest_path = verify_binding(
        source_root, source.get("run_manifest"), "source run manifest"
    )
    manifest = load_json(manifest_path, "source run manifest")
    status = source.get("formalization_status")
    if status not in FORMALIZATION_STATES or manifest.get("formalization") != status:
        raise HandoffError("formalization status does not match the source run manifest")
    if manifest.get("run_id") != source.get("run_id"):
        raise HandoffError("run_id does not match the source run manifest")
    source_artifact = verify_binding(
        source_root,
        source.get("formalization_artifact"),
        "source formalization artifact",
    )
    source_proof = verify_binding(source_root, source.get("proof"), "source proof")
    artifact_relative = source_artifact.relative_to(source_root).as_posix()
    if str(manifest.get("formalization_manifest", "")).replace("\\", "/") != artifact_relative:
        raise HandoffError(
            "source formalization artifact does not match formalization_manifest"
        )
    manifest_artifact(
        manifest,
        artifact_relative,
        sha256_file(source_artifact),
        "source formalization artifact",
    )
    manifest_artifact(
        manifest,
        source_proof.relative_to(source_root).as_posix(),
        sha256_file(source_proof),
        "source proof",
    )
    destination_artifact = verify_binding(
        destination_root,
        destination.get("formalization_artifact"),
        "destination formalization artifact",
    )
    if sha256_file(source_artifact) != sha256_file(destination_artifact):
        raise HandoffError(
            "exact-copy handoff source and destination artifact hashes differ"
        )
    registrations = destination.get("registrations")
    if not isinstance(registrations, list) or not registrations:
        raise HandoffError("destination registrations must be a non-empty array")
    seen: set[str] = set()
    for index, registration in enumerate(registrations):
        verify_registration(
            destination_root, registration, f"destination registration {index}"
        )
        path_value = str(registration.get("path"))
        if path_value in seen:
            raise HandoffError(f"duplicate destination registration path: {path_value}")
        seen.add(path_value)


def seal(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        raise HandoffError(f"project directory not found: {project_root}")
    output = resolve_inside(project_root, args.output, "handoff output")
    if output.suffix.lower() != ".json":
        raise HandoffError("handoff output must be a JSON file")
    if output.exists():
        raise HandoffError(f"immutable handoff output already exists: {args.output}")
    record = build_record(args, project_root)
    verify_record(project_root, record)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"SEALED: {record['handoff_id']}")
    print(f"path: {output.relative_to(project_root).as_posix()}")
    print(f"sha256: {sha256_file(output)}")
    return 0


def verify(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        raise HandoffError(f"project directory not found: {project_root}")
    handoff_path = resolve_file(project_root, args.handoff, "formalization handoff")
    record = load_json(handoff_path, "formalization handoff")
    verify_record(project_root, record)
    print(f"READY: {record['handoff_id']}")
    print(f"sha256: {sha256_file(handoff_path)}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Seal or verify an exact-copy formalization handoff"
    )
    subparsers = root.add_subparsers(dest="command", required=True)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("--project", required=True)
    seal_parser.add_argument("--handoff-id", required=True)
    seal_parser.add_argument("--source-root", required=True)
    seal_parser.add_argument("--source-manifest", required=True)
    seal_parser.add_argument("--source-proof", required=True)
    seal_parser.add_argument("--destination-root", required=True)
    seal_parser.add_argument("--destination-artifact", required=True)
    seal_parser.add_argument(
        "--registration",
        action="append",
        default=[],
        metavar="PATH::ANCHOR",
    )
    seal_parser.add_argument("--output", required=True)
    seal_parser.add_argument("--created-at")
    seal_parser.set_defaults(handler=seal)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project", required=True)
    verify_parser.add_argument("--handoff", required=True)
    verify_parser.set_defaults(handler=verify)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except HandoffError as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
