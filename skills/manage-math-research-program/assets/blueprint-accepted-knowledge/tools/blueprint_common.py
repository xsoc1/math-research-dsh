"""Shared deterministic primitives for the local Blueprint v2.2 workflow."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRESENTATION_ONLY_NODE_FIELDS = {
    "title",
    "display_label",
    "display_notes",
    "layout",
    "ui",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes, prefix: str = "sha256") -> str:
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_node_hash(
    node: dict[str, Any], incoming_dependencies: list[str] | set[str] | None = None
) -> str:
    semantic = {
        key: value
        for key, value in node.items()
        if key not in PRESENTATION_ONLY_NODE_FIELDS
    }
    payload = {
        "node": semantic,
        "incoming_dependencies": sorted(set(incoming_dependencies or [])),
    }
    return sha256_bytes(canonical_json_bytes(payload), prefix="semantic-sha256")


def semantic_row_hash(row: dict[str, str]) -> str:
    return sha256_bytes(canonical_json_bytes(row), prefix="semantic-sha256")


def atomic_write_json(path: Path, value: Any, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and path.exists():
        raise FileExistsError(f"immutable file already exists: {path}")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # A hard-link creation is atomic and fails if the immutable target exists.
            os.link(temporary, path)
            temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


class FileLock:
    """Cross-platform advisory lock held by the process, not by file existence."""

    def __init__(self, path: Path, timeout: float = 0.0) -> None:
        self.path = path
        self.timeout = timeout
        self.handle = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
            os.fsync(self.handle.fileno())

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise TimeoutError(f"lock is busy: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def normalize_reasons(reasons: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for reason in reasons or []:
        item = dict(reason)
        item.setdefault("code", "UNSPECIFIED")
        item.setdefault("message", "No reason supplied")
        normalized.append(item)
    return normalized


def append_event(
    root: Path,
    *,
    event: str,
    result: str,
    agent_id: str,
    submission_id: str | None = None,
    proposal_hash: str | None = None,
    reasons: list[dict[str, Any]] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = json.loads((root / ".blueprint" / "config.json").read_text(encoding="utf-8"))
    log_path = root / config.get("request_log", "blueprint_update_requests.jsonl")
    record = {
        "timestamp_utc": utc_now(),
        "event_id": str(uuid.uuid4()),
        "event": event,
        "result": result,
        "agent_id": agent_id,
        "submission_id": submission_id,
        "proposal_hash": proposal_hash,
        "reasons": normalize_reasons(reasons),
        "details": details or {},
    }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    with FileLock(log_path.with_suffix(log_path.suffix + ".lock"), timeout=30.0):
        with log_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    return record


def is_protected_node(node: dict[str, Any], policy: dict[str, Any]) -> bool:
    if any(node.get(field) is True for field in policy.get("explicit_boolean_fields", [])):
        return True
    status = node.get("status")
    if status in set(policy.get("explicit_statuses", [])):
        return True
    return (
        node.get("grade") in set(policy.get("reliable_grades", []))
        and status in set(policy.get("reliable_terminal_statuses", []))
    )
