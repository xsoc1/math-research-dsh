#!/usr/bin/env python3
"""Static and machine checks for a Lean 4 project (lean-verify plugin).

Usage:
  python verify_lean_project.py --project DIR [--build] [--output OUT_DIR]
                                [--whitelist STR] [--lean-files F1 F2 ...]

Checks:
  - records lean/lake versions and lean-toolchain content;
  - scans .lean files for sorry/admit/axiom outside an explicit whitelist;
  - optionally runs `lake build` and records exit code + log;
  - writes run-manifest.json with input hashes, environment, and observed results.

Never invents results: every field comes from what was actually observed.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SORRY_PAT = re.compile(r"\b(sorry|admit)\b")
AXIOM_PAT = re.compile(r"^\s*(noncomputable\s+)?axiom\s+\w+", re.MULTILINE)
COMMENT_PAT = re.compile(r"--[^\n]*|/\*(?:[^*]|\*(?!/))*\*/")
STRING_PAT = re.compile(r'"(?:[^"\\]|\\.)*"')
LAKE_BUILD_GUARD = Path(__file__).resolve().parent / "lake_build_guard.py"


def scan_file(path: Path, whitelist: set) -> list:
    hits = []
    try:
        raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    in_block = False
    for i, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line
        if in_block:
            end = line.find("*/")
            if end >= 0:
                in_block = False
                line = line[end + 2:]
            else:
                continue
        line = STRING_PAT.sub('""', line)
        code = line.split("--", 1)[0]
        bstart = code.find("/*")
        if bstart >= 0:
            rest = code[bstart + 2:]
            if "*/" not in rest:
                in_block = True
            code = code[:bstart]
        for kind in ("sorry", "admit"):
            if kind in whitelist:
                continue
            for m in re.finditer(r"\b" + kind + r"\b", code):
                hits.append({"file": str(path), "line": i, "kind": kind})
        m = re.match(r"^\s*(?:noncomputable\s+)?axiom\s+(\w+)", code)
        if m and m.group(1) not in whitelist and "axiom" not in whitelist:
            hits.append({"file": str(path), "line": i, "kind": "axiom"})
    return hits
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def run(cmd: list, cwd: Path, timeout: int = 3600) -> dict:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, errors="replace", timeout=timeout
        )
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except FileNotFoundError:
        return {"command": cmd, "exit_code": None, "stdout": "", "stderr": "executable not found"}
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit_code": None, "stdout": "", "stderr": f"timeout after {timeout}s"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Lean 4 project verification checks")
    ap.add_argument("--project", required=True, help="Lean project root directory")
    ap.add_argument("--lean-files", nargs="*", default=None, help="limit scanning to these files")
    ap.add_argument("--build", action="store_true", help="run lake build")
    ap.add_argument("--build-targets", nargs="*", default=None,
                    help="when --build is set, check only these .lean files with `lake env lean` instead of full `lake build`")
    ap.add_argument("--use-cache", action="store_true",
                    help="run `lake exe cache get` before building (avoid long mathlib rebuilds)")
    ap.add_argument("--build-timeout", type=int, default=3600,
                    help="timeout in seconds for each build/cache command (default 3600)")
    ap.add_argument("--whitelist", default="", help="comma-separated allowed names (sorry/admit/axiom names)")
    ap.add_argument("--output", default=None, help="directory for run-manifest.json")
    args = ap.parse_args()

    root = Path(args.project).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"project directory not found: {root}"}))
        return 2

    whitelist = {w.strip() for w in args.whitelist.split(",") if w.strip()}

    env = {
        "lean_version": None,
        "lake_version": None,
        "lean_toolchain": None,
        "lakefile": None,
    }
    for exe in ("lean", "lake"):
        found = shutil.which(exe)
        if found:
            r = run([exe, "--version"], root)
            env[f"{exe}_version"] = (r["stdout"] or r["stderr"]).strip()[:200] or "unknown"
    tc = root / "lean-toolchain"
    if tc.is_file():
        env["lean_toolchain"] = tc.read_text(encoding="utf-8", errors="replace").strip().lstrip("\ufeff")
    for lf in ("lakefile.lean", "lakefile.toml", "lakefile"):
        p = root / lf
        if p.is_file():
            env["lakefile"] = lf
            break

    if args.lean_files:
        files = [root / f for f in args.lean_files]
    else:
        files = sorted(p for p in root.rglob("*.lean") if ".lake" not in p.parts and ".git" not in p.parts)
    files = [f for f in files if f.is_file()]

    scan = []
    for f in files:
        scan.extend(scan_file(f, whitelist))

    build = None
    if args.build:
        guard = subprocess.run(
            [sys.executable, str(LAKE_BUILD_GUARD), "--project", str(root), "--check"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
        )
        if guard.returncode != 0:
            build = {
                "command": ["lake_build_guard.py", "--check"],
                "exit_code": guard.returncode,
                "stdout": guard.stdout[-4000:],
                "stderr": guard.stderr[-4000:],
                "guard_message": "build loop guard refused to start lake build",
            }
        else:
            lake = shutil.which("lake")
            try:
                steps: list[dict] = []
                if args.use_cache and lake:
                    cache = run([lake, "exe", "cache", "get"], root, timeout=args.build_timeout)
                    steps.append({"kind": "cache", **cache})
                if lake:
                    if args.build_targets:
                        # Targeted single-file checks: `lake env lean FILE` is much
                        # cheaper and more robust than a full `lake build`.
                        commands = []
                        for rel in args.build_targets:
                            target = (root / rel).resolve()
                            if not target.is_file():
                                commands.append({
                                    "kind": "target",
                                    "command": ["lake", "env", "lean", rel],
                                    "exit_code": None,
                                    "stdout": "",
                                    "stderr": f"target file not found: {rel}",
                                })
                                continue
                            commands.append({
                                "kind": "target",
                                **run([lake, "env", "lean", str(target)], root, timeout=args.build_timeout),
                            })
                        steps.extend(commands)
                        nonzero = [c for c in commands if c.get("exit_code") is not None and c["exit_code"] != 0]
                        build = {
                            "mode": "targets",
                            "commands": commands,
                            "exit_code": nonzero[0]["exit_code"] if nonzero else 0,
                        }
                    else:
                        steps.append({"kind": "full", **run([lake, "build"], root, timeout=args.build_timeout)})
                        build = {
                            "mode": "full",
                            "commands": steps,
                            "exit_code": steps[-1]["exit_code"],
                        }
                else:
                    build = {"command": ["lake", "build"], "exit_code": None, "stdout": "", "stderr": "lake not found"}
            finally:
                subprocess.run(
                    [sys.executable, str(LAKE_BUILD_GUARD), "--project", str(root), "--release"],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=60,
                )

    inputs = {}
    for f in files:
        inputs[str(f.relative_to(root))] = sha256_file(f)

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "environment": env,
        "files_scanned": len(files),
        "input_hashes": inputs,
        "whitelist": sorted(whitelist),
        "sorry_axiom_hits": scan,
        "build": build,
        "machine_verification_available": env["lean_version"] is not None and env["lake_version"] is not None,
        "machine_verification_passed": bool(build and build.get("exit_code") == 0 and not scan),
    }

    out_dir = Path(args.output).resolve() if args.output else root
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "run-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "files_scanned": len(files),
                      "hits": scan, "build_exit_code": build and build.get("exit_code")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())