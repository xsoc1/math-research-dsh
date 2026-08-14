#!/usr/bin/env python3
"""Sync the DSH skill bundles from the parent Codex marketplace repository.

Copies the four plugin skill directories (plus the workflow and lean-verify
plugin-level scripts and assets) from the parent repository, re-applies the
DSH adaptation layer, regenerates the manage-skill MANIFEST.sha256, and writes
upstream.lock.json.

Usage:
    python scripts/sync-from-parent.py [--upstream PATH] [--check]

Options:
    --upstream PATH   local clone of xsoc1/rigorous-open-math-research.
                      Default: $DSH_HOME/_math-research-upstream/rigorous-open-math-research
                      (DSH_HOME defaults to ~/.dsh).
    --check           no writes: recompute the synced state in a temporary
                      directory and compare it with the current skills/ tree
                      and upstream.lock.json. Exit 1 when the parent has
                      changes the current sync state does not reflect.

The DSH layer is the only allowed divergence from upstream content:
   1. a DSH runtime notes block inserted after each SKILL.md frontmatter;
   2. a DSH changelog block appended (workflow: inserted after the reference
      file list) to each SKILL.md;
   3. the workflow SKILL.md doctor passages rewritten for scripts/dsh-doctor.py;
   4. the Codex scripts/doctor.py dropped from the workflow bundle.
Everything else is byte-identical (LF-normalized) to the parent.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SKILL_NAMES = (
    "rigorous-open-math-research",
    "manage-math-research-program",
    "math-research-workflow",
    "lean-verify",
)

# (upstream plugin dir -> local bundle dir)
BUNDLE_SOURCES = {
    "rigorous-open-math-research": "plugins/rigorous-open-math-research/skills/rigorous-open-math-research",
    "manage-math-research-program": "plugins/manage-math-research-program/skills/manage-math-research-program",
    "math-research-workflow": "plugins/math-research-workflow/skills/math-research-workflow",
    "lean-verify": "plugins/lean-verify/skills/lean-verify",
}

# plugin-level dirs merged into the corresponding bundle
EXTRA_SOURCES = {
    "math-research-workflow": ("assets", "scripts"),
    "lean-verify": ("assets", "scripts"),
}

# files excluded from a plugin-level copy
EXTRA_EXCLUDES = {"math-research-workflow/scripts/doctor.py"}

RUNTIME_NOTES_MARKER = "## DSH runtime notes (DSH adaptation)"
DSH_CHANGELOG_MARKER = "## Changelog (2026-08-14, DSH adaptation)"

RUNTIME_NOTES = {
    "rigorous-open-math-research": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `rigorous-open-math-research`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`manage-math-research-program`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- Reference files under `references/` and `assets/` are read with the read tool
  using the `resourceBase` directory path reported by the skill load result.
- Bundled scripts (of the sibling skills) run with a local Python interpreter via
  the shell: `python <script> ...`, with `PYTHONUTF8=1` on Windows. Prefer writing
  a temporary .py file over PowerShell one-line `-c` calls.
- The DSH adaptation keeps every upstream file byte-identical except this block;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.
""",
    "manage-math-research-program": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `manage-math-research-program`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`rigorous-open-math-research`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- `scripts/` (init_project.py, validate_project.py, sync_remotes.py), the
  `assets/` templates, and the blueprint-accepted-knowledge tools under
  `assets/blueprint-accepted-knowledge/tools/` live inside this bundle; run them
  with a local Python interpreter via the shell using the `resourceBase`
  directory path reported by the skill load result, with `PYTHONUTF8=1` on
  Windows. Prefer writing a temporary .py file over PowerShell one-line `-c`
  calls.
- `MANIFEST.sha256` is re-verified by the repository `scripts/validate_all.py`.
- The DSH adaptation keeps every upstream file byte-identical except this block;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.
""",
    "math-research-workflow": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `math-research-workflow`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message
whose first line is `/skill-name` also loads it). The sibling skills ship beside
this bundle under the same skill roots.

- `scripts/validate_pipeline.py` and the `assets/` templates live inside this
  bundle; run them with a local Python interpreter via the shell using the
  `resourceBase` directory path reported by the skill load result, with
  `PYTHONUTF8=1` on Windows. Prefer writing a temporary .py file over PowerShell
  one-line `-c` calls.
- The DSH environment preflight is `scripts/dsh-doctor.py` in the
  `math-research-dsh` repository checkout (when installed by the repository
  `install.ps1`, the checkout lives at `$DSH_HOME/math-research-dsh`).
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the doctor-related passages rewritten for DSH; the synced upstream commit
  is recorded in the repository `upstream.lock.json`.
""",
    "lean-verify": """## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `lean-verify`. In this
runtime, every reference written as `$skill-name` means: load the skill named
`skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`manage-math-research-program`, `math-research-workflow`, and
`rigorous-open-math-research` ship beside this bundle under the same skill roots.

- `scripts/verify_lean_project.py` and the `assets/` templates live inside this
  bundle; run them with a local Python interpreter via the shell using the
  `resourceBase` directory path reported by the skill load result, with
  `PYTHONUTF8=1` on Windows. The Lean toolchain (`lake` from Lean 4) must be
  available when a build is requested.
- The DSH adaptation keeps every upstream file byte-identical except this block;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.
""",
}

DSH_CHANGELOGS = {
    "rigorous-open-math-research": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block; all upstream content is byte-identical
  otherwise (see `upstream.lock.json`). This bundle is the DSH counterpart of
  the Codex plugin `rigorous-open-math-research` in the math-research
  marketplace repository (https://github.com/xsoc1/rigorous-open-math-research).
""",
    "manage-math-research-program": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block; all upstream content is byte-identical
  otherwise (see `upstream.lock.json`). This bundle is the DSH counterpart of
  the Codex plugin `manage-math-research-program` in the math-research
  marketplace repository (https://github.com/xsoc1/rigorous-open-math-research).
""",
    "lean-verify": """## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block; all upstream content is byte-identical
  otherwise (see `upstream.lock.json`). This bundle is the DSH counterpart of
  the Codex plugin `lean-verify` in the math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
""",
}

WORKFLOW_DOCTOR_STEP_OLD = """2. Run the environment preflight (`scripts/doctor.py`). On a hard `FAIL`,
   apply the printed repair command (usually `codex plugin add
   math-research-workflow@math-research`) before any dispatch; the desktop app
   may rewrite `config.toml` and drop plugin-enable entries between sessions.
"""

WORKFLOW_DOCTOR_STEP_NEW = """2. Run the DSH environment preflight (`scripts/dsh-doctor.py` in the
   math-research-dsh repository checkout, installed under
   `$DSH_HOME/math-research-dsh`). On a hard `FAIL`, apply the printed repair
   command before any dispatch. It verifies that all four skill bundles are
   mounted under the DSH skill roots (`$DSH_HOME/skills` or the project
   `.dsh/skills`), that a Python interpreter is available, and that the Lean
   toolchain exists when stage C is planned.
"""

WORKFLOW_REFERENCE_OLD = """- `scripts/doctor.py` -- environment preflight for the plugin, its dependency
  skills, the marketplace, and the `config.toml` enable entry.
"""

WORKFLOW_REFERENCE_NEW = """- Repository-level `scripts/dsh-doctor.py` -- DSH environment preflight: the
  four skill bundles under the DSH skill roots, a Python interpreter, and the
  Lean toolchain for stage C.

## Changelog (2026-08-14, DSH adaptation)

- DSH adaptation layer: this bundle now ships as a DeepSeek Harness skill.
  Added the DSH runtime notes block; the Codex environment preflight
  (`scripts/doctor.py`) is replaced by the repository-level `scripts/dsh-doctor.py`
  (DSH skill roots, Python interpreter, Lean toolchain); Stage A step 2 and the
  reference-file list were rewritten accordingly. Upstream content is otherwise
  byte-identical (see `upstream.lock.json`).
"""


def default_upstream() -> Path:
    dsh_home = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
    return dsh_home / "_math-research-upstream" / "rigorous-open-math-research"


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def read_norm(path: Path) -> str:
    return normalize(path.read_bytes()).decode("utf-8")


def write_norm(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def sha256_norm(path: Path) -> str:
    return hashlib.sha256(normalize(path.read_bytes())).hexdigest()


def insert_after_frontmatter(text: str, block: str) -> str:
    """Insert block (plus a separating blank line) after the frontmatter close.

    Frontmatter: first line is '---' and a later '---' line closes it.
    Idempotent: no-op when the block's marker is already present.
    """
    marker = block.strip().splitlines()[0]
    if marker in text:
        return text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md does not open with frontmatter")
    close = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            close = idx
            break
    if close is None:
        raise ValueError("SKILL.md frontmatter never closes")
    out = lines[: close + 1]
    out.append("")
    out.extend(block.rstrip("\n").splitlines())
    rest = lines[close + 1 :]
    while rest and rest[0].strip() == "":
        rest.pop(0)
    out.append("")
    out.extend(rest)
    return "\n".join(out) + "\n"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise ValueError("replacement anchor not found")
    return text.replace(old, new, 1)


def apply_dsh_layer(bundle: Path, name: str) -> None:
    skill_md = bundle / "SKILL.md"
    text = read_norm(skill_md)
    text = insert_after_frontmatter(text, RUNTIME_NOTES[name])
    if name == "math-research-workflow":
        text = replace_once(text, WORKFLOW_DOCTOR_STEP_OLD, WORKFLOW_DOCTOR_STEP_NEW)
        text = replace_once(text, WORKFLOW_REFERENCE_OLD, WORKFLOW_REFERENCE_NEW)
    else:
        if DSH_CHANGELOG_MARKER not in text:
            text = text.rstrip("\n") + "\n" + DSH_CHANGELOGS[name]
    write_norm(skill_md, text)


def copy_bundles(upstream: Path, dest_root: Path) -> None:
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)
    for name in SKILL_NAMES:
        src = upstream / BUNDLE_SOURCES[name]
        dst = dest_root / name
        shutil.copytree(src, dst)
        for extra in EXTRA_SOURCES.get(name, ()):
            extra_src = upstream / "plugins" / name / extra
            extra_dst = dst / extra
            if not extra_src.is_dir():
                raise FileNotFoundError(f"missing plugin-level dir: {extra_src}")
            shutil.copytree(extra_src, extra_dst, dirs_exist_ok=True)
            for rel in EXTRA_EXCLUDES:
                if rel.startswith(f"{name}/"):
                    victim = dst / rel.split("/", 1)[1]
                    if victim.exists():
                        victim.unlink()
        apply_dsh_layer(dst, name)


def is_transient(path: Path) -> bool:
    """Python bytecode caches are execution artifacts, not repository content."""
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def regen_manifest(bundle: Path) -> None:
    entries = []
    for p in sorted(p for p in bundle.rglob("*") if p.is_file()):
        if p.name == "MANIFEST.sha256" or is_transient(p):
            continue
        rel = "./" + p.relative_to(bundle).as_posix()
        entries.append(f"{sha256_norm(p)}  {rel}")
    write_norm(bundle / "MANIFEST.sha256", "\n".join(entries) + "\n")


def upstream_head(upstream: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cannot read upstream HEAD: {proc.stderr.strip()}")
    return proc.stdout.strip()


def build_lock(skills_root: Path, upstream_commit: str) -> dict:
    files = {}
    for p in sorted(skills_root.rglob("*")):
        if p.is_file() and not is_transient(p):
            files[p.relative_to(skills_root).as_posix()] = sha256_norm(p)
    return {"upstream_commit": upstream_commit, "files": files}


def current_state(skills_root: Path) -> dict:
    state = {}
    for p in sorted(skills_root.rglob("*")):
        if p.is_file() and not is_transient(p):
            state[p.relative_to(skills_root).as_posix()] = sha256_norm(p)
    return state


def main() -> int:
    args = sys.argv[1:]
    upstream_arg = None
    check = False
    it = iter(args)
    for arg in it:
        if arg == "--upstream":
            upstream_arg = next(it)
        elif arg == "--check":
            check = True
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return 2
    upstream = Path(upstream_arg).resolve() if upstream_arg else default_upstream()
    if not upstream.is_dir():
        print(f"upstream clone not found: {upstream}", file=sys.stderr)
        return 1
    if check:
        return run_check(upstream)
    commit = upstream_head(upstream)
    copy_bundles(upstream, REPO / "skills")
    regen_manifest(REPO / "skills" / "manage-math-research-program")
    lock = build_lock(REPO / "skills", commit)
    write_norm(
        REPO / "upstream.lock.json",
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
    )
    print(f"synced from upstream {commit}")
    print(f"locked {len(lock['files'])} files in upstream.lock.json")
    return 0


def run_check(upstream: Path) -> int:
    commit = upstream_head(upstream)
    lock_path = REPO / "upstream.lock.json"
    if not lock_path.is_file():
        print("FAIL: upstream.lock.json missing; run without --check first")
        return 1
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems = []
    if lock.get("upstream_commit") != commit:
        problems.append(f"upstream commit moved: {lock.get('upstream_commit')} -> {commit}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "skills"
        copy_bundles(upstream, tmp_root)
        regen_manifest(tmp_root / "manage-math-research-program")
        expected = build_lock(tmp_root, commit)
        current = current_state(REPO / "skills")
        for rel in sorted(set(expected["files"]) | set(current)):
            exp = expected["files"].get(rel)
            cur = current.get(rel)
            if exp != cur:
                problems.append(f"drift in {rel}")
                print(f"  drift detail {rel}: expected={exp} current={cur}")
                exp_path = tmp_root / rel
                cur_path = REPO / "skills" / rel
                if exp_path.is_file() and cur_path.is_file():
                    exp_lines = normalize(exp_path.read_bytes()).decode("utf-8", "replace").splitlines()
                    cur_lines = normalize(cur_path.read_bytes()).decode("utf-8", "replace").splitlines()
                    if len(exp_lines) != len(cur_lines):
                        print(f"    line count: expected={len(exp_lines)} current={len(cur_lines)}")
                    for idx, (a, b) in enumerate(zip(exp_lines, cur_lines)):
                        if a != b:
                            print(f"    first diff at line {idx + 1}:")
                            print(f"      expected: {a[:160]!r}")
                            print(f"      current:  {b[:160]!r}")
                            break
    if problems:
        print("FAIL: sync check found drift:")
        for line in problems:
            print("  " + line)
        return 1
    print(f"sync check clean (upstream {commit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
