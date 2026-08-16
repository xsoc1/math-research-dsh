#!/usr/bin/env python3
"""Check that content-affecting changes in a git range also bump package.json.

Used by CI on pull requests (base = merge base with the target branch) and on
push to main (base = HEAD^) so a commit that edits skills/ or scripts/ without
touching package.json fails the build.

Usage:
    python scripts/check_version_bump.py --base <ref> [--repo <path>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

CONTENT_PREFIXES = ("skills/",)
CONTENT_FILES = {"index.mjs", "cordis.patch.yml"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="base ref to diff against (e.g. origin/main, HEAD^)")
    parser.add_argument("--repo", default=".", help="path to the git repository (default: current directory)")
    args = parser.parse_args()

    proc = subprocess.run(
        ["git", "-C", args.repo, "diff", "--name-only", args.base, "HEAD"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        print(f"FAIL: could not diff {args.base}..HEAD: {proc.stderr.strip()}")
        return 1

    changed = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    content_changed = any(
        p.startswith(CONTENT_PREFIXES) or p in CONTENT_FILES for p in changed
    )
    pkg_changed = "package.json" in changed

    if content_changed and not pkg_changed:
        changed_content = [
            p for p in changed if p.startswith(CONTENT_PREFIXES) or p in CONTENT_FILES
        ]
        print(
            "FAIL: skills/ or bundle entry files changed without a package.json version bump.\n"
            f"  changed content files: {', '.join(changed_content)}\n"
            "  fix: bump the version field in package.json (see README maintenance rule 5)."
        )
        return 1

    print(
        "OK: version-bump rule satisfied"
        if content_changed
        else "OK: no skills/scripts content changes in range"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
