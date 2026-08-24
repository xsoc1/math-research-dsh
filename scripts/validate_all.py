#!/usr/bin/env python3
"""Validate the math-research-dsh repository (DSH skill adaptation).

Checks (stdlib only, no network):
  1. skills/ contains exactly the four expected skill bundles, each with a
     SKILL.md whose frontmatter declares a matching name, a description, and
     the DSH runtime notes block.
  2. The manage-math-research-program MANIFEST.sha256 matches every file in
     that bundle (LF-normalized, CRLF worktrees allowed).
  3. upstream.lock.json exists, and every file under skills/ matches its
     locked hash in both directions (catches unsynced hand edits).
  4. Text files are UTF-8 without BOM and use LF line endings.
  5. Every .py file parses (py_compile).
  6. Strict parse: JSON parses after masking {{...}} template tokens; YAML
     parses when PyYAML is installed (CI installs it; locally the check is
     skipped with a note when PyYAML is missing).

Usage:
    python scripts/validate_all.py [repo-root]

Exit code 0 when all checks pass, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import py_compile
import re
import subprocess
import sys

EXPECTED_SKILLS = (
    "rigorous-open-math-research",
    "manage-math-research-program",
    "math-research-workflow",
    "lean-verify",
)


def is_transient(path: pathlib.Path) -> bool:
    """Execution artifacts (bytecode caches, dsh_run logs), not repo content."""
    return (
        "__pycache__" in path.parts
        or path.suffix == ".pyc"
        or ".dsh_run.log" in path.name
    )

RUNTIME_NOTES_MARKER = "## DSH runtime notes (DSH adaptation)"
CHANGELOG_POINTER_MARKER = "Release history, method provenance, and source links live in"

TEXT_SUFFIXES = frozenset(
    {".md", ".json", ".yaml", ".yml", ".txt", ".tex", ".lean", ".py", ".csv", ".svg", ".mmd"}
)
TEMPLATE_TOKEN_RE = re.compile(r"\{\{[^{}]+\}\}")


def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


class Validator:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.checks = 0

    def ok(self, message: str) -> None:
        self.checks += 1
        print(f"ok: {message}")

    def bad(self, message: str) -> None:
        self.checks += 1
        self.errors.append(message)
        print(f"FAIL: {message}")

    def check(self, condition: bool, message: str) -> None:
        if condition:
            self.ok(message)
        else:
            self.bad(message)

    def check_bundles(self) -> None:
        skills_root = self.root / "skills"
        self.check(skills_root.is_dir(), "skills/ directory exists")
        if not skills_root.is_dir():
            return
        present = [p.name for p in skills_root.iterdir() if p.is_dir()]
        self.check(
            sorted(present) == sorted(EXPECTED_SKILLS),
            f"skills/ contains exactly the expected bundles (found: {sorted(present)})",
        )
        for name in EXPECTED_SKILLS:
            skill_dir = skills_root / name
            skill_md = skill_dir / "SKILL.md"
            self.check(skill_md.is_file(), f"skill '{name}' has SKILL.md")
            if not skill_md.is_file():
                continue
            lines = norm(skill_md.read_bytes()).decode("utf-8").splitlines()
            self.check(
                len(lines) >= 3 and lines[0].strip() == "---",
                f"skill '{name}' frontmatter opens with ---",
            )
            fm: list[str] = []
            closed = False
            for line in lines[1:]:
                if line.strip() == "---":
                    closed = True
                    break
                fm.append(line)
            if not closed:
                self.bad(f"skill '{name}' frontmatter never closes")
                continue
            joined = "\n".join(fm)
            self.check(
                any(line.startswith("name:") for line in fm),
                f"skill '{name}' frontmatter has a name",
            )
            self.check(
                f"name: {name}" in joined,
                f"skill '{name}' frontmatter name matches the bundle directory",
            )
            self.check("description:" in joined, f"skill '{name}' frontmatter has a description")
            self.check(
                RUNTIME_NOTES_MARKER in joined or RUNTIME_NOTES_MARKER in "\n".join(lines),
                f"skill '{name}' carries the DSH runtime notes block",
            )
            body_lines = "\n".join(lines)
            self.check(
                CHANGELOG_POINTER_MARKER in body_lines,
                f"skill '{name}' SKILL.md points to the relocated changelog",
            )
            self.check(
                not any(line.startswith("## Changelog (") for line in lines),
                f"skill '{name}' has no un-relocated changelog headings in the body",
            )
            changelog_ref = skill_dir / "references" / "changelog.md"
            self.check(
                changelog_ref.is_file(),
                f"skill '{name}' has references/changelog.md",
            )

    def check_manifest(self) -> None:
        skill_dir = self.root / "skills" / "manage-math-research-program"
        manifest = skill_dir / "MANIFEST.sha256"
        self.check(manifest.is_file(), "manage bundle has MANIFEST.sha256")
        if not manifest.is_file():
            return
        listed: dict[str, str] = {}
        bad = 0
        for line in norm(manifest.read_bytes()).decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            hexdigest, rel = line.split("  ", 1)
            listed[rel] = hexdigest
            target = skill_dir / rel
            actual = hashlib.sha256(norm(target.read_bytes())).hexdigest() if target.is_file() else ""
            if not target.is_file() or actual != hexdigest:
                bad += 1
                self.bad(f"manage MANIFEST.sha256 mismatch: {rel}")
        on_disk = {
            "./" + p.relative_to(skill_dir).as_posix()
            for p in skill_dir.rglob("*")
            if p.is_file() and p.name != "MANIFEST.sha256" and not is_transient(p)
        }
        for rel in sorted(set(listed) ^ on_disk):
            bad += 1
            self.bad(f"manage MANIFEST.sha256 coverage mismatch: {rel}")
        if bad == 0:
            self.ok("manage MANIFEST.sha256 matches and covers the bundle")

    def check_lock(self) -> None:
        lock_path = self.root / "upstream.lock.json"
        self.check(lock_path.is_file(), "upstream.lock.json exists")
        if not lock_path.is_file():
            return
        lock = json.loads(norm(lock_path.read_bytes()).decode("utf-8"))
        self.check(bool(lock.get("upstream_commit")), "lock records the upstream commit")
        locked = lock.get("files", {})
        self.check(isinstance(locked, dict) and len(locked) > 0, "lock lists at least one file")
        on_disk: dict[str, str] = {}
        for p in (self.root / "skills").rglob("*"):
            if p.is_file() and not is_transient(p):
                on_disk[p.relative_to(self.root / "skills").as_posix()] = hashlib.sha256(
                    norm(p.read_bytes())
                ).hexdigest()
        bad = 0
        for rel in sorted(set(locked) | set(on_disk)):
            if locked.get(rel) != on_disk.get(rel):
                bad += 1
                self.bad(f"upstream.lock.json mismatch: {rel}")
        if bad == 0:
            self.ok(f"upstream.lock.json matches every file under skills/ ({len(on_disk)} files)")

    def check_text(self) -> None:
        bad = 0
        for p in self.root.rglob("*"):
            if not p.is_file() or ".git" in p.parts:
                continue
            if p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            raw = p.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                bad += 1
                self.bad(f"file has UTF-8 BOM: {p.relative_to(self.root)}")
                continue
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                bad += 1
                self.bad(f"file is not valid UTF-8: {p.relative_to(self.root)}")
                continue
            if b"\r\n" in raw:
                bad += 1
                self.bad(f"file has CRLF line endings: {p.relative_to(self.root)}")
        if bad == 0:
            self.ok("all text files are UTF-8 without BOM and use LF")

    def check_python(self) -> None:
        bad = 0
        compiled = 0
        for p in self.root.rglob("*.py"):
            if ".git" in p.parts:
                continue
            compiled += 1
            try:
                py_compile.compile(str(p), doraise=True)
            except py_compile.PyCompileError as exc:
                bad += 1
                self.bad(f"python syntax error: {p.relative_to(self.root)}: {exc}")
        if bad == 0:
            self.ok(f"all python files compile ({compiled} files)")

    def check_structured(self) -> None:
        try:
            import yaml
        except ImportError:
            yaml = None
        bad_json = 0
        bad_yaml = 0
        json_checked = 0
        yaml_checked = 0
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or ".git" in p.parts:
                continue
            suffix = p.suffix.lower()
            if suffix == ".json":
                json_checked += 1
                text = norm(p.read_bytes()).decode("utf-8")
                masked = TEMPLATE_TOKEN_RE.sub("0", text)
                try:
                    json.loads(masked)
                except json.JSONDecodeError as exc:
                    bad_json += 1
                    self.bad(f"JSON parse error (after masking {{{{...}}}} templates): {p.relative_to(self.root)}: {exc}")
            elif suffix in (".yaml", ".yml") and yaml is not None:
                yaml_checked += 1
                try:
                    yaml.safe_load(norm(p.read_bytes()).decode("utf-8"))
                except Exception as exc:
                    bad_yaml += 1
                    self.bad(f"YAML parse error: {p.relative_to(self.root)}: {exc}")
        if yaml is None:
            print("note: PyYAML not installed; strict YAML parse skipped")
        if bad_json == 0:
            self.ok(f"all JSON files parse after masking {{{{...}}}} templates ({json_checked} files)")
        if yaml is not None and bad_yaml == 0:
            self.ok(f"all YAML files parse ({yaml_checked} files)")

    def check_readme_smoke_parity(self) -> None:
        tests_dir = self.root / "tests"
        if not tests_dir.is_dir():
            self.bad("tests/ directory missing; cannot check README smoke parity")
            return
        smoke_files = sorted(p.name for p in tests_dir.glob("smoke_*.py"))
        for readme_name in ("README.md", "README_EN.md"):
            readme = self.root / readme_name
            if not readme.is_file():
                self.bad(f"{readme_name} missing; cannot check smoke parity")
                continue
            text = norm(readme.read_bytes()).decode("utf-8")
            missing = [name for name in smoke_files if name not in text]
            self.check(
                not missing,
                f"{readme_name} lists every smoke test"
                + (f" (missing: {', '.join(missing)})" if missing else ""),
            )

    def check_worktree_version_bump(self) -> None:
        """Local guard: uncommitted content changes must also touch package.json.

        CI enforces the same rule across PR/push diffs via scripts/check_version_bump.py;
        this catches the common local workflow of editing skills/ and forgetting to bump.
        """
        git_dir = self.root / ".git"
        if not git_dir.exists():
            self.ok("not a git worktree; skipping local version-bump guard")
            return
        proc = subprocess.run(
            ["git", "-C", str(self.root), "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if proc.returncode != 0:
            self.ok("git diff unavailable; skipping local version-bump guard")
            return
        changed = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        content_changed = any(
            p.startswith("skills/") or p in ("index.mjs", "cordis.patch.yml")
            for p in changed
        )
        pkg_changed = "package.json" in changed
        if content_changed and not pkg_changed:
            self.bad(
                "package.json version must be bumped when skills/ or bundle entry files change "
                "(uncommitted worktree changes detected without a package.json change)"
            )
        elif content_changed and pkg_changed:
            self.ok("package.json version bump present for worktree content changes")
        else:
            self.ok("no uncommitted skills/bundle content changes requiring a version bump")

    def run(self) -> int:
        print(f"Validating repository: {self.root}")
        self.check_bundles()
        self.check_manifest()
        self.check_lock()
        self.check_text()
        self.check_python()
        self.check_structured()
        self.check_readme_smoke_parity()
        self.check_worktree_version_bump()
        if self.errors:
            print(f"\n{len(self.errors)} problem(s) found.")
            return 1
        print(f"\nAll checks passed ({self.checks} checks).")
        return 0


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    return Validator(root).run()


if __name__ == "__main__":
    sys.exit(main())
