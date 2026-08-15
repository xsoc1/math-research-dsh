#!/usr/bin/env python3
"""Mechanical gate for the DSH bundle packaging of this repository.

Checks that the repo root is a valid DSH bundle skill pack:

1. package.json parses, carries a lowercase npm-valid name, a semver
   version, and a dsh.bundle.patch pointing at ./cordis.patch.yml;
2. cordis.patch.yml is a YAML insert array whose single entry's `id`
   equals `export const name` in index.mjs and whose `name` equals the
   package name;
3. index.mjs imports @deepseek-ai/dsh-skill-filesystem, registers a
   provider, and every directory in its SKILL_DIRS list exists under
   skills/ with a SKILL.md whose frontmatter `name` equals the directory
   name;
4. package.json exports and files cover the entry and the patch;
5. the four packaging files are UTF-8 without BOM with LF endings.

Usage:
    python scripts/dsh-check-bundle.py

Exits 0 with a BUNDLE OK verdict when every check passes.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PACKAGING_FILES = [
    "package.json",
    "index.mjs",
    "cordis.patch.yml",
]

failures = []


def check(cond, message):
    if not cond:
        failures.append(message)


def read_text(path):
    return path.read_text(encoding="utf-8")


def main():
    pkg_path = ROOT / "package.json"
    check(pkg_path.is_file(), f"missing {pkg_path.name}")
    if not pkg_path.is_file():
        report()
        return 1

    pkg = json.loads(read_text(pkg_path))
    name = pkg.get("name")
    check(
        isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name or ""),
        f"package.json name must be a lowercase npm name, got {name!r}",
    )
    version = pkg.get("version")
    check(
        isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version or ""),
        f"package.json version must be semver, got {version!r}",
    )

    bundle = pkg.get("dsh", {}).get("bundle", {})
    patch_ref = bundle.get("patch")
    check(patch_ref == "./cordis.patch.yml", f"dsh.bundle.patch must be ./cordis.patch.yml, got {patch_ref!r}")
    exports = pkg.get("exports", {})
    check(exports.get(".") == "./index.mjs", f"exports['.'] must be ./index.mjs, got {exports.get('.')!r}")
    check(exports.get("./cordis.patch.yml") == "./cordis.patch.yml", "exports['./cordis.patch.yml'] missing")
    files = pkg.get("files", [])
    for required in ("index.mjs", "cordis.patch.yml", "skills"):
        check(required in files, f"files must include {required}")

    patch_path = ROOT / "cordis.patch.yml"
    check(patch_path.is_file(), "missing cordis.patch.yml")
    entry = None
    if patch_path.is_file():
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - CI installs PyYAML
            failures.append(f"PyYAML required to parse cordis.patch.yml: {exc}")
        else:
            try:
                doc = yaml.safe_load(read_text(patch_path))
                inserts = doc[0].get("insert", []) if isinstance(doc, list) and doc else []
                if len(inserts) != 1:
                    failures.append(f"cordis.patch.yml must have exactly one insert entry, got {len(inserts)}")
                else:
                    entry = inserts[0]
            except Exception as exc:  # noqa: BLE001
                failures.append(f"cordis.patch.yml is not valid YAML: {exc}")

    entry_path = ROOT / "index.mjs"
    check(entry_path.is_file(), "missing index.mjs")
    entry_src = read_text(entry_path) if entry_path.is_file() else ""
    m = re.search(r"export const name = '([^']+)'", entry_src)
    entry_name = m.group(1) if m else None
    check(entry_name is not None, "index.mjs must export const name")
    check("FileSystemSkillProvider" in entry_src, "index.mjs must import FileSystemSkillProvider")
    check("registerProvider" in entry_src, "index.mjs must call ctx.skills.registerProvider")
    if entry is not None:
        check(
            entry.get("id") == entry_name,
            f"cordis.patch.yml id {entry.get('id')!r} must equal index.mjs name {entry_name!r}",
        )
        check(entry.get("name") == name, f"cordis.patch.yml name {entry.get('name')!r} must equal package name {name!r}")

    skill_dirs = re.findall(r"'([a-z0-9-]+)'", re.search(r"SKILL_DIRS = \[(.*?)\]", entry_src, re.S).group(1)) if re.search(r"SKILL_DIRS = \[(.*?)\]", entry_src, re.S) else []
    check(len(skill_dirs) >= 1, "index.mjs SKILL_DIRS must list at least one skill directory")
    for skill in skill_dirs:
        skill_md = ROOT / "skills" / skill / "SKILL.md"
        check(skill_md.is_file(), f"skills/{skill}/SKILL.md missing")
        if skill_md.is_file():
            text = read_text(skill_md)
            fm = text.split("---", 2)
            if len(fm) < 3 or not fm[1].strip():
                check(False, f"skills/{skill}/SKILL.md has no YAML frontmatter")
                continue
            try:
                import yaml  # noqa: F811

                meta = yaml.safe_load(fm[1])
                check(
                    meta.get("name") == skill,
                    f"skills/{skill}/SKILL.md frontmatter name {meta.get('name')!r} must equal directory name {skill!r}",
                )
                check(isinstance(meta.get("description"), str) and meta["description"].strip(), f"skills/{skill}/SKILL.md needs a description")
            except ImportError:  # pragma: no cover
                check(False, "PyYAML required to parse SKILL.md frontmatter")
            except Exception as exc:  # noqa: BLE001
                check(False, f"skills/{skill}/SKILL.md frontmatter invalid: {exc}")

    for rel in PACKAGING_FILES:
        raw = (ROOT / rel).read_bytes()
        check(not raw.startswith(b"\xef\xbb\xbf"), f"{rel} must be UTF-8 without BOM")
        check(b"\r\n" not in raw, f"{rel} must use LF line endings")

    report()
    return 1 if failures else 0


def report():
    if failures:
        print("BUNDLE FAIL")
        for message in failures:
            print(f"- {message}")
    else:
        print("BUNDLE OK")


if __name__ == "__main__":
    sys.exit(main())
