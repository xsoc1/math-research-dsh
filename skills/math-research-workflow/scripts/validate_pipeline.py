#!/usr/bin/env python3
"""Deterministic gate checks for a math-research pipeline project.

This script validates the mechanical parts of the manage -> research -> verify
handoff without making any mathematical judgment. It does not replace the
solver, audit, or verifier agents; it only rejects states that can be decided
from files and hashes.

Checks:
  - task packets in agenda/task-packets/*.md have the required fields and do
    not leak unfilled template placeholders; solve/disprove/construct packets
    must carry a completed Novelty preflight section (workflow B0 gate);
  - source-bundle hashes, task-packet hashes in run manifests, and lean-proof
    input hashes match the files they reference;
  - run manifests under runs/** and lean-proof/run-manifest.json parse;
  - interruption handoff records (runs/**/handoff-interrupted-*.md) carry
    the required fields/sections so a successor agent can resume work; new
    quota handoffs bind a structured state and a checkpoint that verifies
    READY before any resumed model call;
  - stage B solver runs started on or after the whiteboard cutover date carry
    runs/<run_id>/whiteboard.md, and every whiteboard found carries the
    required fields/sections of the OpenProver-style solve-loop memory;
  - closure gates created after the fast-close cutover carry completion
    certificate fields; STOP requires a hash-bound frozen completion manifest,
    a distinct fresh independent structured PASS audit, closed root obligations,
    and zero load-bearing gaps; an optional frontier upgrade is a separate,
    single-use, hash-bound, positively budgeted record;
  - completed manager runs carry a non-empty upstream status, and statuses
    outside the formalization gate are reported;
  - a run that claims a gate status (CANDIDATE_COMPLETE_PROOF / \u5df2\u8bc1)
    must carry candidate_proof.md or audit_report.md in the same run directory;
  - a run that claims a gate status must also record its formalization
    decision (run-manifest formalization: requested | not_requested | skipped
    | scaffold). requested requires a formalization_manifest file and
    lean-proof/verification.json; skipped requires a non-placeholder
    formalization_reason; scaffold requires a formalization_manifest pointing
    to a scaffold file. A silently skipped lean-verify step is therefore
    rejected instead of passing unnoticed. Runs started on/after 2026-08-16
    with material progress must record formalization: scaffold or requested;
  - numerical-evidence labels must never be mixed with a strong claim
    (\u5df2\u89e3\u51b3 / \u5b9a\u7406\u5df2\u8bc1 / CANDIDATE_COMPLETE_PROOF /
    FORMALLY_VERIFIED) unless a strict-evidence label is present in the same
    block or file (anti-abuse guard for numerical results masquerading as
    proofs);
  - lean-proof/verification.json with verdict FORMALLY_VERIFIED requires
    machine.build_passed == true and zero sorry/axiom hits;
  - lean-proof/STATUS.md must not claim FORMALLY_VERIFIED without a
    verification.json present;
  - optionally, the git working tree is clean at a stage boundary.

Usage:
  python validate_pipeline.py --project ROOT [--check-git] [--allow-dirty]
      [--gate-status STATUS,STATUS...]

Exit code 0 when all hard checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from checkpoint_resume import CheckpointError, verify_checkpoint


PACKET_GLOB = "agenda/task-packets/*.md"
MANAGER_MANIFEST_GLOB = "runs/**/run-manifest.json"
LEAN_MANIFEST = "lean-proof/run-manifest.json"
LEAN_VERDICT = "lean-proof/verification.json"
LEAN_STATUS = "lean-proof/STATUS.md"
WHITEBOARD_GLOB = "runs/**/whiteboard.md"
WHITEBOARD_CUTOVER = 20260814
CLOSURE_GATE_GLOB = "runs/**/closure_gate.md"
FAST_CLOSE_CUTOVER = 20260829
QUOTA_CHECKPOINT_CUTOVER = 20260829
FORMALIZATION_SCAFFOLD_CUTOVER = 20260816
FORMALIZATION_ALLOWED = ("requested", "not_requested", "skipped", "scaffold")

PLACEHOLDER_VALUES = {"TASK-ID", "PROJECT-ID", "PROBLEM-ID", "RUN_ROOT"}
ALLOWED_TASK_TYPES = {"solve", "disprove", "construct", "formalize", "rigorously audit"}
SOLVER_TASK_TYPES = {"solve", "disprove", "construct"}
NOVELTY_HEADING = "Novelty preflight (B0)"
HANDOFF_GLOB = "**/handoff-interrupted-*.md"


def is_in_nested_repo(root: Path, path: Path) -> bool:
    """True if path sits under a nested git repository (e.g. a cloned plugin
    repo inside the project). Such paths belong to another repo and must not be
    validated as part of this project."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    cur = root
    for part in rel.parts[:-1]:
        cur = cur / part
        if (cur / ".git").exists():
            return True
    return False
REQUIRED_HANDOFF_FIELDS = (
    "Run ID",
    "Task packet ID",
    "Date",
    "Interrupt reason",
    "Task state",
)
REQUIRED_HANDOFF_HEADINGS = {
    "Completed work progress",
    "Completed obligations",
    "Tools and methods tried",
    "Open obligations",
    "Attempted routes",
    "Next actions",
}
REQUIRED_WHITEBOARD_FIELDS = ("Run ID", "Task packet ID")
REQUIRED_WHITEBOARD_HEADINGS = {
    "Current plan",
    "Route history",
    "Ideas to return to",
    "Open obligations",
    "Key artifacts",
}
HANDOFF_STATE_VALUES = {"IN_PROGRESS", "BLOCKED"}
HANDOFF_ROUTE_RESULT_RE = re.compile(
    r"\[(FAILED|BLOCKED|PARTIAL|SUCCEEDED)\]",
    re.IGNORECASE,
)
RUN_DATE_RE = re.compile(r"R-(\d{8})T")
DEFAULT_GATE_STATUSES = {"\u5df2\u8bc1", "CANDIDATE_COMPLETE_PROOF"}
FAST_CLOSE_DECISIONS = {
    "NOT_READY",
    "CONTINUE_REQUIRED",
    "REPAIR",
    "STOP",
}
ROOT_OBLIGATION_STATES = {"OPEN", "CLOSED"}
GATE_DECISIONS = {"CLOSED", "FALSIFIED", "OPEN_EXACT_GAP", "ESCALATE", "REPAIR_CONTRACT"}
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
FRONTIER_AUTHORIZATION_TYPES = {"user_request", "pre_existing_frontier"}
FRONTIER_BUDGET_UNITS = {"model_responses", "tool_calls", "wall_minutes", "tokens"}
REQUIRED_CLOSURE_FIELDS = (
    "Gate decision",
    "Root obligations",
    "Completion manifest",
    "Fresh package audit",
    "Load-bearing gaps",
    "Fast-close decision",
    "Frontier upgrade",
)

REQUIRED_PACKET_HEADINGS = {
    "Source bundle",
    "Required run location",
    "Upstream invocation",
}

NUMERICAL_LABEL_RE = re.compile(
    r"\u6570\u503c\u8bc1\u636e|\u6570\u503c\u9a8c\u8bc1|\u6570\u503c\u68c0\u9a8c"
    r"|\u6570\u503c\u5b9e\u9a8c|EVIDENCE|numerical evidence|numerical verification",
    re.IGNORECASE,
)
STRONG_CLAIM_RE = re.compile(
    r"\u5df2\u89e3\u51b3|\u5b9a\u7406\u5df2\u8bc1|CANDIDATE_COMPLETE_PROOF|FORMALLY_VERIFIED"
)
STRICT_EVIDENCE_RE = re.compile(
    r"\u4e25\u683c\u8bc1\u660e|\u5b9a\u7406\u5df2\u8bc1|\bSTRICT\b|FORMALLY_VERIFIED"
    r"|\u673a\u5668\u9a8c\u8bc1|\u5f62\u5f0f\u5316\u9a8c\u8bc1",
    re.IGNORECASE,
)
NUMERICAL_DOWNGRADE_RE = re.compile(
    r"not constitute proof|evidence only|evidence, not proof|evidence is not proof|cross-check only|no .{0,60}evidence.{0,60}used as"
    r"|\u4e0d\u6784\u6210\u8bc1\u660e|\u4ec5\u4e3a\u8bc1\u636e|\u4ec5\u4f5c\u8bc1\u636e"
    r"|\u4ec5\u662f\u8bc1\u636e|\u4e0d\u4f5c\u4e3a\u8bc1\u660e|\u4f50\u8bc1",
    re.IGNORECASE,
)
CLAIM_FILE_GLOBS = ("docs/**/*.md", "runs/**/*.md")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks = 0

    def ok(self, message: str) -> None:
        self.checks += 1
        print(f"ok: {message}")

    def bad(self, message: str) -> None:
        self.checks += 1
        self.errors.append(message)
        print(f"FAIL: {message}")

    def warn(self, message: str) -> None:
        self.checks += 1
        self.warnings.append(message)
        print(f"warn: {message}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_json(path: Path, report: Report) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.bad(f"missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        report.bad(f"invalid JSON in {path}: {exc}")
    except OSError as exc:
        report.bad(f"cannot read {path}: {exc}")
    return None


def strip_inline_code(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].strip()
    return value


def parse_packet(path: Path) -> tuple[dict[str, str], set[str], str]:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            headings.add(stripped[3:].strip())
            continue
        match = re.match(r"-\s+\*\*([^*]+)\*\*\s*(.*)$", stripped)
        if match:
            key = match.group(1).rstrip(":").strip()
            fields[key] = match.group(2).strip()
    return fields, headings, text


def parse_plain_fields(text: str) -> dict[str, str]:
    """Parse unbolded Markdown list fields of the form ``- Key: value``."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\s*-\s+([^:]+):\s*(.*)$", line)
        if match:
            fields[match.group(1).strip()] = strip_inline_code(match.group(2))
    return fields


def parse_semicolon_fields(value: str) -> dict[str, str]:
    """Parse a compact ``key=value; key=value`` certificate field."""
    parsed: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        key, item = part.split("=", 1)
        parsed[key.strip().lower()] = item.strip()
    return parsed


def parse_source_bundle(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_table = stripped[3:].strip() == "Source bundle"
            continue
        if in_table and stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
    return rows


def check_task_packet(path: Path, root: Path, report: Report) -> None:
    fields, headings, text = parse_packet(path)
    rel = path.relative_to(root)

    for key in ("Task ID", "Project ID", "Task type", "Task state"):
        if key not in fields:
            report.bad(f"{rel}: missing required field {key!r}")
            continue
        value = strip_inline_code(fields[key])
        if not value:
            report.bad(f"{rel}: {key} is empty")

    task_id = strip_inline_code(fields.get("Task ID", ""))
    project_id = strip_inline_code(fields.get("Project ID", ""))
    if task_id in PLACEHOLDER_VALUES:
        report.bad(f"{rel}: Task ID still contains placeholder {task_id!r}")
    if project_id in PLACEHOLDER_VALUES:
        report.bad(f"{rel}: Project ID still contains placeholder {project_id!r}")
    if task_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,}", task_id):
        report.warn(f"{rel}: Task ID {task_id!r} does not look like an ID")

    task_type = fields.get("Task type", "")
    if "|" in task_type:
        report.bad(f"{rel}: Task type still contains the template choices")
    elif task_type not in ALLOWED_TASK_TYPES:
        report.bad(f"{rel}: unknown Task type {task_type!r}")

    for heading in REQUIRED_PACKET_HEADINGS:
        if heading not in headings:
            report.bad(f"{rel}: missing required section {heading!r}")

    check_novelty_preflight(fields, headings, rel, report)

    run_location = fields.get("Required run location", "")
    if run_location and strip_inline_code(run_location) in PLACEHOLDER_VALUES:
        report.bad(f"{rel}: Required run location still contains {run_location!r}")

    for row in parse_source_bundle(text):
        if not row or row[0] in {"Item", ""}:
            continue
        if len(row) < 4:
            continue
        source = row[2]
        expected = row[3]
        if not expected or not source:
            continue
        if re.match(r"^(https?|doi|arxiv)://|^10\.", source, re.IGNORECASE):
            continue
        check_referenced_hash(root, source, expected, report, f"{rel}: source bundle")


def check_novelty_preflight(
    fields: dict[str, str], headings: set[str], rel: Path, report: Report
) -> None:
    """B0 gate: solve/disprove/construct packets need a completed preflight.

    The section is produced by the workflow stage B0 (openness check,
    divergent novelty audit, snapshot backfill). A missing or placeholder
    preflight is a hard FAIL so a solver is never dispatched blind.
    """
    if fields.get("Task type", "") not in SOLVER_TASK_TYPES:
        return
    if NOVELTY_HEADING not in headings:
        report.bad(f"{rel}: missing required section {NOVELTY_HEADING!r} (B0 gate)")
        return
    verdict = strip_inline_code(fields.get("Openness verdict", ""))
    if not verdict:
        report.bad(f"{rel}: Novelty preflight has no Openness verdict (B0 gate)")
    elif "|" in verdict or "YYYY-MM-DD" in verdict:
        report.bad(f"{rel}: Openness verdict still contains the template placeholder (B0 gate)")
    audit = fields.get("Novelty audit path", "").strip()
    if not audit:
        report.bad(f"{rel}: Novelty preflight has no audit path or skip record (B0 gate)")
    elif audit.startswith("`RUN_ROOT") or "`skip" in audit or "or `skip" in audit:
        report.bad(f"{rel}: Novelty audit path still contains the template placeholder (B0 gate)")
    snapshot = strip_inline_code(fields.get("Snapshot hash", ""))
    if not snapshot:
        report.bad(f"{rel}: Novelty preflight has no snapshot hash (B0 gate)")
    elif "<snapshot-hash>" in snapshot or snapshot in {"sha256:...", "sha256:<snapshot-hash>"}:
        report.bad(f"{rel}: Snapshot hash still contains the template placeholder (B0 gate)")


def check_referenced_hash(
    root: Path, rel_path: str, expected: str, report: Report, context: str
) -> None:
    # Windows-style separators in manifests are normalized so that
    # lean-proof/run-manifest.json entries like "SL\\BalancedPhase.lean"
    # resolve on any platform.
    parts = [part for part in rel_path.replace("\\", "/").split("/") if part]
    if not parts:
        report.bad(f"{context}: empty referenced path")
        return
    target = root.joinpath(*parts)
    if not target.is_file():
        report.bad(f"{context}: referenced file missing: {rel_path}")
        return
    actual = sha256_file(target)
    if actual != expected.strip().upper():
        report.bad(f"{context}: hash mismatch for {rel_path}: {actual} != {expected.strip().upper()}")


def check_manager_manifest(
    path: Path, root: Path, report: Report, gate_statuses: set[str]
) -> None:
    data = load_json(path, report)
    if not isinstance(data, dict):
        if data is not None:
            report.bad(f"{path.relative_to(root)}: run manifest is not a JSON object")
        return

    rel = path.relative_to(root)
    packet_path = data.get("task_packet_path")
    packet_hash = data.get("task_packet_sha256")
    if packet_path and packet_hash:
        check_referenced_hash(
            root, packet_path, str(packet_hash), report, f"{rel}: task packet"
        )

    if data.get("completed_at") and not data.get("upstream_status_verbatim"):
        report.bad(
            f"{rel}: completed_at is set but upstream_status_verbatim is empty"
        )

    status = data.get("upstream_status_verbatim")
    if status and gate_statuses and status not in gate_statuses:
        report.warn(
            f"{rel}: status {status!r} is outside the formalization gate "
            f"{sorted(gate_statuses)}"
        )

    if status and status in gate_statuses:
        run_dir = path.parent
        has_proof = (run_dir / "candidate_proof.md").is_file() or (
            run_dir / "audit_report.md"
        ).is_file()
        if not has_proof:
            report.bad(
                f"{rel}: gate status {status!r} without candidate_proof.md or "
                "audit_report.md in the run directory"
            )

    # Formalization decision (lean-verify step): a run that claims a
    # completion status must record whether Lean verification was requested,
    # skipped (with a reason), scaffolded (partial-result skeleton), or out of
    # scope. Without this, a silently skipped lean-verify step is
    # indistinguishable from a deliberate pipeline decision and passes every
    # check. Since 2026-08-16, any run with material progress must scaffold a
    # Lean file (formalization: scaffold) even when the result is only
    # RIGOROUS_PARTIAL_RESULT.
    formalization = data.get("formalization")
    if status and status in gate_statuses:
        if formalization not in FORMALIZATION_ALLOWED:
            report.bad(
                f"{rel}: gate status {status!r} without a formalization decision "
                "(run-manifest formalization: requested | not_requested | skipped | scaffold)"
            )
        elif formalization == "requested":
            fm = data.get("formalization_manifest")
            fm_path = root.joinpath(fm) if isinstance(fm, str) and fm else None
            if fm_path is None or not fm_path.is_file():
                report.bad(
                    f"{rel}: formalization requested but formalization_manifest "
                    "does not point to an existing file"
                )
            if not (root / LEAN_VERDICT).is_file():
                report.bad(
                    f"{rel}: formalization requested but {LEAN_VERDICT} is missing"
                )
        elif formalization == "skipped":
            reason = str(data.get("formalization_reason") or "").strip()
            if not reason or "{{" in reason:
                report.bad(
                    f"{rel}: formalization skipped but formalization_reason is "
                    "empty or a placeholder"
                )
        elif formalization == "scaffold":
            fm = data.get("formalization_manifest")
            fm_path = root.joinpath(fm) if isinstance(fm, str) and fm else None
            if fm_path is None or not fm_path.is_file():
                report.bad(
                    f"{rel}: formalization scaffold but formalization_manifest "
                    "does not point to an existing scaffold file"
                )

    # New runs with material progress must scaffold a Lean file even when the
    # result is partial (RIGOROUS_PARTIAL_RESULT and similar). This turns the
    # user requirement "every new result gets a formalization scaffold" into a
    # mechanical gate for runs started after the cutover.
    if (
        status
        and status not in gate_statuses
        and "NO_MATERIAL_PROGRESS" not in status
        and formalization not in ("scaffold", "requested")
    ):
        start = run_start_date(path.parent)
        if start is not None and start >= FORMALIZATION_SCAFFOLD_CUTOVER:
            report.bad(
                f"{rel}: run started {start} has material progress but no Lean "
                "formalization scaffold "
                "(run-manifest formalization: scaffold | requested required since "
                f"{FORMALIZATION_SCAFFOLD_CUTOVER})"
            )


def check_lean_manifest(path: Path, root: Path, report: Report) -> None:
    data = load_json(path, report)
    if not isinstance(data, dict):
        if data is not None:
            report.bad(f"{path.relative_to(root)}: lean manifest is not a JSON object")
        return
    input_hashes = data.get("input_hashes")
    if isinstance(input_hashes, dict):
        # input_hashes are relative to the manifest directory (lean-proof/),
        # not to the project root.
        base = path.parent
        for rel_path, expected in input_hashes.items():
            check_referenced_hash(
                base, rel_path, str(expected), report, f"{path.relative_to(root)}: input hash"
            )
    else:
        report.warn(f"{path.relative_to(root)}: no input_hashes map to verify")


def check_lean_verdict(path: Path, root: Path, report: Report) -> None:
    data = load_json(path, report)
    if not isinstance(data, dict):
        if data is not None:
            report.bad(f"{path.relative_to(root)}: verification.json is not a JSON object")
        return
    verdict = data.get("verdict")
    if verdict != "FORMALLY_VERIFIED":
        return
    machine = data.get("machine")
    rel = path.relative_to(root)
    if not isinstance(machine, dict) or machine.get("build_passed") is not True:
        report.bad(
            f"{rel}: verdict FORMALLY_VERIFIED without machine.build_passed == true"
        )
    hits = machine.get("sorry_axiom_hits") if isinstance(machine, dict) else None
    if hits:
        report.bad(f"{rel}: verdict FORMALLY_VERIFIED but sorry/axiom hits present: {hits}")


def check_status_declaration(root: Path, report: Report) -> None:
    status = root / LEAN_STATUS
    verdict = root / LEAN_VERDICT
    if not status.is_file():
        return
    text = status.read_text(encoding="utf-8", errors="replace")
    if "FORMALLY_VERIFIED" not in text:
        return
    if not verdict.is_file():
        report.bad(
            f"{LEAN_STATUS} claims FORMALLY_VERIFIED but {LEAN_VERDICT} is missing"
        )


def iter_claim_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in CLAIM_FILE_GLOBS:
        files.extend(sorted(root.glob(pattern)))
    for extra in ("README.md", LEAN_STATUS):
        path = root / extra
        if path.is_file():
            files.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def check_numerical_abuse(path: Path, root: Path, report: Report) -> None:
    """Reject numerical-evidence labels mixed with strong claims.

    A block (blank-line separated) that carries a numerical-evidence label and
    a strong claim must also carry a strict-evidence label; otherwise the text
    reads as a numerical result promoted to a proof, which is the exact abuse
    this gate blocks. A file that uses numerical labels and strong claims but
    has no strict-evidence label anywhere is rejected outright.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(root)
    if not NUMERICAL_LABEL_RE.search(text) or not STRONG_CLAIM_RE.search(text):
        return
    if not STRICT_EVIDENCE_RE.search(text):
        claim = STRONG_CLAIM_RE.search(text).group(0)
        if NUMERICAL_DOWNGRADE_RE.search(text):
            report.warn(
                f"{rel}: numerical labels are explicitly downgraded "
                "(evidence-only / not-a-proof) but no strict-evidence label is "
                "present; add a strict label to the proof claim"
            )
        else:
            report.bad(
                f"{rel}: uses numerical-evidence labels and claims {claim!r} but has "
                "no strict-evidence label (严格证明/定理已证/STRICT/FORMALLY_VERIFIED/"
                "机器验证/形式化验证) anywhere in the file"
            )
            return
    for index, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        if not NUMERICAL_LABEL_RE.search(block) or not STRONG_CLAIM_RE.search(block):
            continue
        if STRICT_EVIDENCE_RE.search(block) or NUMERICAL_DOWNGRADE_RE.search(block):
            continue
        claim = STRONG_CLAIM_RE.search(block).group(0)
        report.bad(
            f"{rel}: block {index} mixes numerical-evidence labels with claim "
            f"{claim!r} and has no strict-evidence label in the block"
        )


def check_claim_evidence(root: Path, report: Report) -> None:
    """Warn when strong claims exist without any project-level evidence anchor."""
    evidence_anchors = [p for p in root.glob("runs/**/run-manifest.json") if not is_in_nested_repo(root, p)]
    evidence_anchors.extend(p for p in root.glob("lean-proof/verification.json") if not is_in_nested_repo(root, p))
    evidence_anchors.extend(p for p in root.glob("**/candidate_proof.md") if not is_in_nested_repo(root, p))
    evidence_anchors.extend(p for p in root.glob("**/audit_report.md") if not is_in_nested_repo(root, p))
    if evidence_anchors:
        return
    for path in iter_claim_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        if STRONG_CLAIM_RE.search(text):
            report.warn(
                f"{path.relative_to(root)}: strong claim present but no evidence "
                "anchors (run manifests / verification.json / candidate_proof.md / "
                "audit_report.md) found anywhere in the project"
            )
            return


def check_interruption_handoffs(root: Path, report: Report) -> None:
    """Validate interruption handoff records (workflow interruption protocol).

    A handoff must identify the run and packet, say why work stopped, list
    completed/open obligations, and - critically - record the routes already
    tried with outcome markers plus the exact next actions. Missing sections
    are hard FAILs so a successor agent never resumes blind.
    """
    files = sorted(p for p in root.glob(HANDOFF_GLOB) if not is_in_nested_repo(root, p))
    if files:
        report.ok(f"found {len(files)} interruption handoff record(s)")
    for path in files:
        rel = path.relative_to(root)
        fields, headings, text = parse_packet(path)
        for key in REQUIRED_HANDOFF_FIELDS:
            value = strip_inline_code(fields.get(key, ""))
            if not value:
                report.bad(f"{rel}: missing required field {key!r} (interruption handoff)")
            elif key == "Interrupt reason" and "|" in value:
                report.bad(f"{rel}: Interrupt reason still contains the template choices (interruption handoff)")
            elif key == "Task state":
                if "|" in value:
                    report.bad(f"{rel}: Task state still contains the template choices (interruption handoff)")
                elif not (value.startswith("IN_PROGRESS") or value.startswith("BLOCKED")):
                    report.warn(f"{rel}: unexpected Task state {value!r} (expected IN_PROGRESS or BLOCKED)")
        for heading in REQUIRED_HANDOFF_HEADINGS:
            if heading not in headings:
                report.bad(f"{rel}: missing required section {heading!r} (interruption handoff)")
                continue
            body = extract_section(text, heading)
            if heading in {"Completed work progress", "Tools and methods tried", "Attempted routes", "Next actions"} and not body.strip():
                report.bad(f"{rel}: section {heading!r} is empty (interruption handoff)")
        routes = extract_section(text, "Attempted routes")
        unmarked = [ln.strip() for ln in routes.splitlines() if ln.strip().startswith("-") and not HANDOFF_ROUTE_RESULT_RE.search(ln)]
        if unmarked:
            report.warn(
                f"{rel}: {len(unmarked)} route line(s) without a "
                "[FAILED|BLOCKED|PARTIAL|SUCCEEDED] outcome marker"
            )
        start = run_start_date(path.parent)
        reason = strip_inline_code(fields.get("Interrupt reason", "")).upper()
        quota_boundary = "RESOURCE_BOUND" in reason or "QUOTA" in reason
        if start is None or start < QUOTA_CHECKPOINT_CUTOVER or not quota_boundary:
            continue
        state_binding = parse_semicolon_fields(
            strip_inline_code(fields.get("Interruption state", ""))
        )
        checkpoint_binding = parse_semicolon_fields(
            strip_inline_code(fields.get("Interruption checkpoint", ""))
        )
        state_path = check_bound_artifact(
            root, path, "Interruption state", state_binding, report
        )
        checkpoint_path = check_bound_artifact(
            root, path, "Interruption checkpoint", checkpoint_binding, report
        )
        if state_path is None or checkpoint_path is None:
            continue
        if state_path.parent != path.parent or checkpoint_path.parent != path.parent:
            report.bad(f"{rel}: quota state and checkpoint must be siblings of the handoff")
            continue
        try:
            verification = verify_checkpoint(root, checkpoint_path)
        except CheckpointError as exc:
            report.bad(f"{rel}: interruption checkpoint is STALE: {exc}")
            continue
        checkpoint_data = load_json(checkpoint_path, report)
        checkpoint_state = None
        if isinstance(checkpoint_data, dict):
            state_record = checkpoint_data.get("state")
            if isinstance(state_record, dict) and isinstance(state_record.get("path"), str):
                checkpoint_state = (root / state_record["path"]).resolve()
        if checkpoint_state != state_path.resolve():
            report.bad(
                f"{rel}: handoff state binding does not match the checkpoint state"
            )
        elif verification["run_id"] != strip_inline_code(fields.get("Run ID", "")):
            report.bad(f"{rel}: handoff Run ID does not match the checkpoint")
        elif verification["task_packet_id"] != strip_inline_code(
            fields.get("Task packet ID", "")
        ):
            report.bad(f"{rel}: handoff Task packet ID does not match the checkpoint")
        else:
            report.ok(
                f"{rel}: quota checkpoint {verification['checkpoint_id']} is READY"
            )


def run_start_date(run_dir: Path) -> int | None:
    """Parse the R-YYYYMMDD start date embedded in a run directory name."""
    match = RUN_DATE_RE.search(run_dir.name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def check_whiteboards(root: Path, report: Report) -> None:
    """Validate the whiteboard memory protocol (OpenProver-style solve loop).

    Stage B solver runs (identified by research_ledger.md) that start on or
    after the whiteboard cutover date must carry runs/<run_id>/whiteboard.md;
    historical runs are not retrofitted. Every whiteboard found must carry the
    required fields and sections so the solve-run lead and any successor can
    resume from it, and route lines should carry outcome markers.
    """
    whiteboards = sorted(p for p in root.glob(WHITEBOARD_GLOB) if not is_in_nested_repo(root, p))
    if whiteboards:
        report.ok(f"found {len(whiteboards)} run whiteboard(s)")
    seen_dirs = {path.parent for path in whiteboards}
    for path in whiteboards:
        rel = path.relative_to(root)
        fields, headings, text = parse_packet(path)
        for key in REQUIRED_WHITEBOARD_FIELDS:
            if not strip_inline_code(fields.get(key, "")):
                report.bad(f"{rel}: missing required field {key!r} (whiteboard)")
        for heading in REQUIRED_WHITEBOARD_HEADINGS:
            if heading not in headings:
                report.bad(f"{rel}: missing required section {heading!r} (whiteboard)")
        routes = extract_section(text, "Route history")
        unmarked = [
            line.strip()
            for line in routes.splitlines()
            if line.strip().startswith("-") and not HANDOFF_ROUTE_RESULT_RE.search(line)
        ]
        if unmarked:
            report.warn(
                f"{rel}: {len(unmarked)} route line(s) without a "
                "[FAILED|BLOCKED|PARTIAL|SUCCEEDED] outcome marker"
            )
    for run_dir in sorted(p for p in root.glob("runs/**") if not is_in_nested_repo(root, p)):
        if not run_dir.is_dir() or run_dir in seen_dirs:
            continue
        if not (run_dir / "research_ledger.md").is_file():
            continue
        start = run_start_date(run_dir)
        rel = run_dir.relative_to(root)
        if start is None:
            report.warn(
                f"{rel}: solver run without a parseable start date; "
                "cannot enforce the whiteboard cutover"
            )
            continue
        if start >= WHITEBOARD_CUTOVER:
            report.bad(
                f"{rel}: solver run started {start} has no whiteboard.md "
                f"(whiteboard protocol since {WHITEBOARD_CUTOVER})"
            )


def check_bound_artifact(
    root: Path,
    gate_path: Path,
    field_name: str,
    values: dict[str, str],
    report: Report,
) -> Path | None:
    """Verify a path and SHA-256 binding relative to the closure-gate directory."""
    rel = gate_path.relative_to(root)
    artifact_value = values.get("path", "")
    expected_hash = values.get("sha256", "")
    if not artifact_value:
        report.bad(f"{rel}: {field_name} has no path")
        return None
    if not SHA256_RE.fullmatch(expected_hash):
        report.bad(f"{rel}: {field_name} has no valid SHA-256")
        return None
    artifact = (gate_path.parent / artifact_value).resolve()
    try:
        artifact.relative_to(root)
    except ValueError:
        report.bad(f"{rel}: {field_name} path escapes the project root: {artifact_value}")
        return None
    if not artifact.is_file():
        report.bad(f"{rel}: {field_name} artifact is missing: {artifact_value}")
        return None
    actual_hash = sha256_file(artifact)
    if actual_hash != expected_hash.upper():
        report.bad(
            f"{rel}: {field_name} hash mismatch for {artifact_value}: "
            f"{actual_hash} != {expected_hash.upper()}"
        )
        return None
    return artifact


def parse_certificate_time(value: object, context: str, report: Report) -> datetime | None:
    """Parse an ISO-8601 certificate timestamp and require an explicit timezone."""
    if not isinstance(value, str) or not value.strip():
        report.bad(f"{context}: missing ISO-8601 timestamp")
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        report.bad(f"{context}: invalid ISO-8601 timestamp {value!r}")
        return None
    if parsed.tzinfo is None:
        report.bad(f"{context}: timestamp must include a timezone")
        return None
    return parsed


def markdown_anchors(path: Path) -> set[str]:
    """Return explicit HTML IDs and deterministic heading slugs from Markdown."""
    text = path.read_text(encoding="utf-8")
    anchors = set(re.findall(r"\bid=[\"']([^\"']+)[\"']", text, re.IGNORECASE))
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        heading = re.sub(r"<[^>]+>", "", match.group(1)).lower()
        slug = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug.strip())
        if not slug:
            continue
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def normalize_root_obligations(
    value: object,
    context: str,
    report: Report,
    require_closed: bool,
) -> dict[str, tuple[str, str]]:
    """Validate and normalize a structured root-obligation array."""
    normalized: dict[str, tuple[str, str]] = {}
    if not isinstance(value, list) or not value:
        report.bad(f"{context}: needs at least one root obligation")
        return normalized
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            report.bad(f"{context}: root obligation {index} must be a JSON object")
            continue
        obligation_id = item.get("id", "")
        if not isinstance(obligation_id, str) or not obligation_id.strip():
            report.bad(f"{context}: root obligation {index} has no id")
            continue
        obligation_id = obligation_id.strip()
        if obligation_id in normalized:
            report.bad(f"{context}: duplicate root obligation id {obligation_id!r}")
            continue
        status = item.get("status", "")
        if status not in ROOT_OBLIGATION_STATES:
            report.bad(f"{context}: root obligation {obligation_id!r} has invalid status")
        if require_closed and status != "CLOSED":
            report.bad(f"{context}: root obligation {obligation_id!r} is not CLOSED")
        anchor = item.get("proof_anchor", "")
        if not isinstance(anchor, str):
            report.bad(f"{context}: root obligation {obligation_id!r} has invalid proof_anchor")
            anchor = ""
        if status == "CLOSED" and not anchor.strip():
            report.bad(f"{context}: root obligation {obligation_id!r} has no proof_anchor")
        normalized[obligation_id] = (str(status), anchor.strip())
    return normalized


def validate_completion_manifest(
    root: Path,
    gate_path: Path,
    manifest_path: Path,
    report: Report,
) -> tuple[str, datetime | None, Path | None]:
    """Validate the frozen contract, obligation graph, proof, and root closure."""
    rel = manifest_path.relative_to(root)
    data = load_json(manifest_path, report)
    if not isinstance(data, dict):
        report.bad(f"{rel}: completion manifest must be a JSON object")
        return "", None, None
    if data.get("schema_version") != 1:
        report.bad(f"{rel}: completion manifest schema_version must be 1")
    author = data.get("candidate_author_id", "")
    if not isinstance(author, str) or not author.strip():
        report.bad(f"{rel}: completion manifest has no candidate_author_id")
        author = ""
    frozen_at = parse_certificate_time(data.get("frozen_at"), f"{rel}: frozen_at", report)

    bound_paths: dict[str, Path] = {}
    for key in ("contract", "obligation_graph", "candidate_proof"):
        binding = data.get(key)
        if not isinstance(binding, dict):
            report.bad(f"{rel}: completion manifest field {key!r} must be a path/hash object")
            continue
        values = {str(name).lower(): str(value) for name, value in binding.items()}
        target = check_bound_artifact(root, gate_path, f"completion manifest {key}", values, report)
        if target is not None:
            bound_paths[key] = target
    if len(set(bound_paths.values())) != len(bound_paths):
        report.bad(f"{rel}: contract, obligation graph, and candidate proof must be distinct files")

    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list):
        report.bad(f"{rel}: completion manifest dependencies must be a JSON array")
    else:
        for index, binding in enumerate(dependencies):
            if not isinstance(binding, dict):
                report.bad(f"{rel}: dependency {index} must be a path/hash object")
                continue
            values = {str(name).lower(): str(value) for name, value in binding.items()}
            check_bound_artifact(root, gate_path, f"completion dependency {index}", values, report)

    obligations = normalize_root_obligations(
        data.get("root_obligations"), str(rel), report, require_closed=True
    )
    graph_obligations: dict[str, tuple[str, str]] = {}
    graph_path = bound_paths.get("obligation_graph")
    if graph_path is not None:
        graph_rel = graph_path.relative_to(root)
        graph_data = load_json(graph_path, report)
        if not isinstance(graph_data, dict):
            report.bad(f"{graph_rel}: canonical obligation graph must be a JSON object")
        else:
            if graph_data.get("schema_version") != 1:
                report.bad(f"{graph_rel}: obligation graph schema_version must be 1")
            graph_obligations = normalize_root_obligations(
                graph_data.get("root_obligations"), str(graph_rel), report, require_closed=False
            )
    if obligations != graph_obligations:
        report.bad(
            f"{rel}: completion manifest root obligations do not exactly match "
            "the canonical obligation graph"
        )

    proof_binding = data.get("candidate_proof")
    proof_reference = ""
    if isinstance(proof_binding, dict):
        proof_reference = str(proof_binding.get("path", "")).replace("\\", "/")
    proof_path = bound_paths.get("candidate_proof")
    anchors = markdown_anchors(proof_path) if proof_path is not None else set()
    for obligation_id, (_, anchor) in obligations.items():
        normalized_anchor = anchor.replace("\\", "/")
        prefix = f"{proof_reference}#"
        if not proof_reference or not normalized_anchor.startswith(prefix):
            report.bad(
                f"{rel}: root obligation {obligation_id!r} proof_anchor "
                "must point into the bound candidate proof"
            )
            continue
        fragment = normalized_anchor[len(prefix):]
        if not fragment or fragment not in anchors:
            report.bad(
                f"{rel}: root obligation {obligation_id!r} proof_anchor fragment "
                f"{fragment!r} does not exist in the candidate proof"
            )
    return author.strip(), frozen_at, proof_path


def validate_completion_audit(
    root: Path,
    gate_path: Path,
    audit_path: Path,
    expected_manifest_hash: str,
    candidate_author: str,
    frozen_at: datetime | None,
    report: Report,
) -> dict[str, Any]:
    """Validate a fresh independent zero-gap audit bound to the frozen manifest."""
    rel = audit_path.relative_to(root)
    data = load_json(audit_path, report)
    if not isinstance(data, dict):
        report.bad(f"{rel}: completion audit must be a JSON object")
        return {}
    if data.get("schema_version") != 1:
        report.bad(f"{rel}: completion audit schema_version must be 1")
    if data.get("review_type") != "fresh_independent_package":
        report.bad(f"{rel}: completion audit review_type must be fresh_independent_package")
    if str(data.get("audited_manifest_sha256", "")).upper() != expected_manifest_hash.upper():
        report.bad(f"{rel}: completion audit is not bound to the frozen manifest hash")
    if data.get("candidate_author_id") != candidate_author:
        report.bad(f"{rel}: completion audit candidate_author_id does not match the manifest")
    reviewer = data.get("reviewer_id", "")
    if not isinstance(reviewer, str) or not reviewer.strip():
        report.bad(f"{rel}: completion audit has no reviewer_id")
    elif reviewer.strip() == candidate_author:
        report.bad(f"{rel}: completion audit reviewer must differ from the candidate author")
    reviewed_at = parse_certificate_time(data.get("reviewed_at"), f"{rel}: reviewed_at", report)
    if frozen_at is not None and reviewed_at is not None and reviewed_at < frozen_at:
        report.bad(f"{rel}: completion audit predates the frozen completion manifest")
    if data.get("verdict") != "PASS":
        report.bad(f"{rel}: completion audit verdict must be PASS")
    gaps = data.get("load_bearing_gaps")
    if gaps != []:
        report.bad(f"{rel}: completion audit load_bearing_gaps must be an empty array")
    return data


def validate_frontier_upgrade(
    root: Path,
    gate_path: Path,
    upgrade_path: Path,
    manifest_hash: str,
    audit_hash: str,
    report: Report,
) -> tuple[str, str] | None:
    """Validate the single bounded transition allowed after certified STOP."""
    rel = upgrade_path.relative_to(root)
    data = load_json(upgrade_path, report)
    if not isinstance(data, dict):
        report.bad(f"{rel}: frontier upgrade record must be a JSON object")
        return None
    if data.get("schema_version") != 1 or data.get("sequence") != 1:
        report.bad(f"{rel}: frontier upgrade must use schema_version=1 and sequence=1")
    if str(data.get("base_completion_manifest_sha256", "")).upper() != manifest_hash.upper():
        report.bad(f"{rel}: frontier upgrade is not bound to the completion manifest")
    if str(data.get("base_audit_sha256", "")).upper() != audit_hash.upper():
        report.bad(f"{rel}: frontier upgrade is not bound to the completion audit")
    obligation_id = data.get("obligation_id", "")
    if not isinstance(obligation_id, str) or not obligation_id.strip():
        report.bad(f"{rel}: frontier upgrade has no obligation_id")
    authorization = data.get("authorization")
    if not isinstance(authorization, dict):
        report.bad(f"{rel}: frontier upgrade authorization must be a JSON object")
    else:
        if authorization.get("type") not in FRONTIER_AUTHORIZATION_TYPES:
            report.bad(f"{rel}: frontier upgrade has an invalid authorization type")
        values = {
            str(name).lower(): str(value)
            for name, value in authorization.items()
            if name in {"path", "sha256"}
        }
        authorization_path = check_bound_artifact(
            root, gate_path, "frontier authorization", values, report
        )
        locator = authorization.get("locator", "")
        if not isinstance(locator, str) or not locator.strip():
            report.bad(f"{rel}: frontier upgrade authorization has no locator")
        elif authorization_path is not None:
            if authorization_path.suffix.lower() != ".md":
                report.bad(f"{rel}: frontier authorization must be a Markdown record")
                authorization_path = None
        if isinstance(locator, str) and locator.strip() and authorization_path is not None:
            fragment = locator.strip().lstrip("#")
            if fragment not in markdown_anchors(authorization_path):
                report.bad(
                    f"{rel}: frontier authorization locator {locator!r} "
                    "does not exist in the bound record"
                )
    budget = data.get("budget")
    if not isinstance(budget, dict):
        report.bad(f"{rel}: frontier upgrade budget must be a JSON object")
    else:
        limit = budget.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            report.bad(f"{rel}: frontier upgrade budget limit must be a positive integer")
        if budget.get("unit") not in FRONTIER_BUDGET_UNITS:
            report.bad(f"{rel}: frontier upgrade budget has an invalid unit")
    stop_condition = data.get("stop_condition", "")
    if not isinstance(stop_condition, str) or not stop_condition.strip():
        report.bad(f"{rel}: frontier upgrade has no stop_condition")
    elif stop_condition.strip().lower() in {"never", "none", "unbounded", "no limit"}:
        report.bad(f"{rel}: frontier upgrade stop_condition is not bounded")
    if SHA256_RE.fullmatch(manifest_hash) and SHA256_RE.fullmatch(audit_hash):
        return manifest_hash.upper(), audit_hash.upper()
    return None


def check_closure_gates(root: Path, report: Report) -> None:
    """Validate deterministic completion certificates at the fast-close boundary."""
    gates = sorted(p for p in root.glob(CLOSURE_GATE_GLOB) if not is_in_nested_repo(root, p))
    if gates:
        report.ok(f"found {len(gates)} closure gate(s)")
    upgrade_bases: dict[tuple[str, str], Path] = {}
    for path in gates:
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        fields = parse_plain_fields(text)
        start = run_start_date(path.parent)
        has_fast_close = "Completion manifest" in fields or "Fast-close decision" in fields
        if not has_fast_close and (start is None or start < FAST_CLOSE_CUTOVER):
            continue
        for key in REQUIRED_CLOSURE_FIELDS:
            if not fields.get(key, "").strip():
                report.bad(f"{rel}: missing required field {key!r} (fast-close certificate)")

        root_state = fields.get("Root obligations", "")
        if root_state not in ROOT_OBLIGATION_STATES:
            report.bad(f"{rel}: invalid Root obligations value {root_state!r}")
        gate_decision = fields.get("Gate decision", "")
        if gate_decision not in GATE_DECISIONS:
            report.bad(f"{rel}: invalid Gate decision {gate_decision!r}")
        decision = fields.get("Fast-close decision", "")
        if decision not in FAST_CLOSE_DECISIONS:
            report.bad(f"{rel}: invalid Fast-close decision {decision!r}")
            continue

        if gate_decision == "CLOSED" and decision in {"NOT_READY", "CONTINUE_REQUIRED"}:
            report.bad(
                f"{rel}: CLOSED gate cannot use Fast-close decision {decision}"
            )
        if decision != "STOP":
            continue

        if gate_decision != "CLOSED":
            report.bad(f"{rel}: STOP requires Gate decision CLOSED")
        if root_state != "CLOSED":
            report.bad(f"{rel}: STOP requires Root obligations CLOSED")

        manifest_binding = parse_semicolon_fields(fields.get("Completion manifest", ""))
        manifest_path = check_bound_artifact(
            root, path, "Completion manifest", manifest_binding, report
        )
        candidate_author = ""
        frozen_at: datetime | None = None
        candidate_path: Path | None = None
        if manifest_path is not None:
            if manifest_path.name != "completion_manifest.json":
                report.bad(f"{rel}: completion manifest file must be named completion_manifest.json")
            if manifest_path.parent != path.parent:
                report.bad(f"{rel}: completion manifest must be a sibling of closure_gate.md")
            candidate_author, frozen_at, candidate_path = validate_completion_manifest(
                root, path, manifest_path, report
            )

        audit_binding = parse_semicolon_fields(fields.get("Fresh package audit", ""))
        audit_path = check_bound_artifact(root, path, "Fresh package audit", audit_binding, report)
        if audit_path is not None and manifest_path is not None:
            if audit_path.name != "completion_audit.json":
                report.bad(f"{rel}: completion audit file must be named completion_audit.json")
            if audit_path.parent != path.parent:
                report.bad(f"{rel}: completion audit must be a sibling of closure_gate.md")
            if audit_path in {manifest_path, candidate_path}:
                report.bad(f"{rel}: completion audit must be distinct from manifest and proof files")
            validate_completion_audit(
                root,
                path,
                audit_path,
                manifest_binding.get("sha256", ""),
                candidate_author,
                frozen_at,
                report,
            )

        gaps = fields.get("Load-bearing gaps", "")
        if gaps != "0":
            report.bad(f"{rel}: STOP requires Load-bearing gaps 0")

        frontier = fields.get("Frontier upgrade", "")
        if frontier.lower() != "none":
            frontier_binding = parse_semicolon_fields(frontier)
            frontier_path = check_bound_artifact(
                root, path, "Frontier upgrade", frontier_binding, report
            )
            if frontier_path is not None and audit_path is not None and manifest_path is not None:
                if frontier_path.name != "frontier_upgrade.json":
                    report.bad(f"{rel}: frontier record file must be named frontier_upgrade.json")
                if frontier_path.parent != path.parent:
                    report.bad(f"{rel}: frontier record must be a sibling of closure_gate.md")
                if frontier_path in {audit_path, manifest_path, candidate_path}:
                    report.bad(f"{rel}: frontier upgrade record must be a distinct file")
                base = validate_frontier_upgrade(
                    root,
                    path,
                    frontier_path,
                    manifest_binding.get("sha256", ""),
                    audit_binding.get("sha256", ""),
                    report,
                )
                if base is not None:
                    previous = upgrade_bases.get(base)
                    if previous is not None:
                        report.bad(
                            f"{rel}: duplicate frontier upgrade for the same STOP "
                            f"certificate (already used by {previous.relative_to(root)})"
                        )
                    else:
                        upgrade_bases[base] = frontier_path

    seen_dirs = {path.parent for path in gates}
    run_markers: set[Path] = set()
    for marker_name in (
        "research_ledger.md",
        "candidate_proof.md",
        "final_report.md",
        "completion_manifest.json",
        "completion_audit.json",
    ):
        run_markers.update(
            path.parent
            for path in root.glob(f"runs/**/{marker_name}")
            if not is_in_nested_repo(root, path)
        )
    for run_dir in sorted(run_markers):
        start = run_start_date(run_dir)
        if start is not None and start >= FAST_CLOSE_CUTOVER and run_dir not in seen_dirs:
            report.bad(
                f"{run_dir.relative_to(root)}: solver run started {start} has no closure_gate.md "
                f"(fast-close protocol since {FAST_CLOSE_CUTOVER})"
            )
    for manifest in sorted(p for p in root.glob("runs/**/completion_manifest.json") if not is_in_nested_repo(root, p)):
        if manifest.parent not in seen_dirs:
            report.bad(
                f"{manifest.relative_to(root)}: completion manifest has no sibling closure_gate.md"
            )

    audits_by_manifest: dict[str, list[Path]] = {}
    for audit_path in sorted(
        p for p in root.glob("runs/**/*.json") if not is_in_nested_repo(root, p)
    ):
        try:
            audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(audit_data, dict) or (
            audit_data.get("review_type") != "fresh_independent_package"
        ):
            continue
        manifest_hash = str(audit_data.get("audited_manifest_sha256", "")).upper()
        if not SHA256_RE.fullmatch(manifest_hash):
            report.bad(
                f"{audit_path.relative_to(root)}: completion audit has no valid "
                "audited_manifest_sha256"
            )
            continue
        audits_by_manifest.setdefault(manifest_hash, []).append(audit_path)
    for manifest_hash, audit_paths in audits_by_manifest.items():
        if len(audit_paths) > 1:
            joined = ", ".join(str(path.relative_to(root)) for path in audit_paths)
            report.bad(
                f"completion manifest {manifest_hash} has more than one completion audit: {joined}"
            )


def extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    parts = text.split(marker, 1)
    if len(parts) < 2:
        return ""
    body = parts[1].split("\n## ", 1)[0]
    return body


def check_git(root: Path, report: Report, allow_dirty: bool) -> None:
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        report.warn(f"cannot run git status: {proc.stderr.strip()}")
        return
    if proc.stdout.strip():
        message = "working tree is dirty: run git status --porcelain"
        if allow_dirty:
            report.warn(message)
        else:
            report.bad(message)
    else:
        report.ok("git working tree is clean")


def iter_packet_files(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.glob(PACKET_GLOB) if not is_in_nested_repo(root, p))


def iter_manager_manifests(root: Path) -> Iterable[Path]:
    return sorted(p for p in root.glob(MANAGER_MANIFEST_GLOB) if not is_in_nested_repo(root, p))


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic pipeline gate checks")
    parser.add_argument("--project", required=True, help="math project root directory")
    parser.add_argument("--check-git", action="store_true", help="require a clean git tree")
    parser.add_argument("--allow-dirty", action="store_true", help="warn instead of fail on dirty tree")
    parser.add_argument(
        "--gate-status",
        default=",".join(sorted(DEFAULT_GATE_STATUSES)),
        help="comma-separated statuses allowed into formalization (stage C)",
    )
    args = parser.parse_args()

    root = Path(args.project).resolve()
    if not root.is_dir():
        print(f"FAIL: project directory not found: {root}")
        return 2

    gate_statuses = {s.strip() for s in args.gate_status.split(",") if s.strip()}
    report = Report()

    packets = list(iter_packet_files(root))
    report.ok(f"found {len(packets)} task packet(s)")
    for packet in packets:
        check_task_packet(packet, root, report)

    manifests = list(iter_manager_manifests(root))
    report.ok(f"found {len(manifests)} manager run manifest(s)")
    for manifest in manifests:
        check_manager_manifest(manifest, root, report, gate_statuses)

    lean_manifest = root / LEAN_MANIFEST
    if lean_manifest.is_file():
        check_lean_manifest(lean_manifest, root, report)
    else:
        report.warn(f"no lean manifest at {LEAN_MANIFEST}")

    verdict = root / LEAN_VERDICT
    if verdict.is_file():
        check_lean_verdict(verdict, root, report)

    check_status_declaration(root, report)
    check_interruption_handoffs(root, report)
    check_whiteboards(root, report)
    check_closure_gates(root, report)

    claim_files = iter_claim_files(root)
    report.ok(f"found {len(claim_files)} claim-bearing markdown file(s)")
    for path in claim_files:
        check_numerical_abuse(path, root, report)
    check_claim_evidence(root, report)

    if args.check_git:
        check_git(root, report, args.allow_dirty)

    problem_count = len(report.errors)
    print(
        f"{problem_count} problem(s) found, {len(report.warnings)} warning(s), "
        f"{report.checks} check(s)."
    )
    return 1 if problem_count else 0


if __name__ == "__main__":
    sys.exit(main())
