#!/usr/bin/env python3
"""Replay the DSH layout layer over the four parent plugin bundles.

Formal sync requires a clean parent; --expect-commit can bind a frozen HEAD.
--check compares bundles, root smoke/unit tests, fixtures and selected docs.
--preview NEW_EXTERNAL_DIR accepts a working source without changing this
checkout and marks its output as an unreleased preview.

Allowed differences are runtime/changelog notes, DSH execution references and
an optional task template, declared bundle/test/doc path rewrites, the relocated
manage runtime, the DSH doctor replacement and generated hashes. Research
policy and mathematical implementations remain upstream-owned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
    "manage-math-research-program": ("runtime",),
    "math-research-workflow": ("assets", "scripts"),
    "lean-verify": ("assets", "scripts"),
}

# files excluded from a plugin-level copy
EXTRA_EXCLUDES = {
    "math-research-workflow/scripts/doctor.py",
    "lean-verify/scripts/tests/_probe",
}
COPY_IGNORES = shutil.ignore_patterns("__pycache__", "*.pyc", ".lake", ".git", "*.dsh_run.log")

TEXT_SUFFIXES = frozenset(
    {".md", ".json", ".yaml", ".yml", ".txt", ".tex", ".lean", ".py", ".csv", ".svg", ".mmd", ".js", ".mjs", ".template"}
)

RUNTIME_NOTES_MARKER = "## DSH runtime notes (DSH adaptation)"
CHANGELOG_POINTER_MARKER = "Release history, method provenance, and source links live in"

CHANGELOG_POINTER = """## History

Release history, method provenance, and source links live in
`references/changelog.md`. Read it only when auditing provenance or preparing
a release.
"""

RUNTIME_COMMON = """## DSH runtime notes (DSH adaptation)

Load a relevant `$skill-name` with DSH's `skill` tool using its exact name.
Resolve bundled files from the returned `resourceBase`. Run Python helpers
with a local interpreter (`PYTHONUTF8=1` on Windows).
"""

RUNTIME_DETAILS = {
	"rigorous-open-math-research": """
Research methods and evidence rules come from the parent skill below.
""",
	"manage-math-research-program": """
This bundle includes `scripts/`, `assets/` and `runtime/`. For Blueprint,
`<manage-plugin>` and `<active-manage-plugin>` mean this `resourceBase`;
the gateway is `runtime/blueprintctl.py`.
""",
	"math-research-workflow": """
Plugin-level helpers are merged into this bundle's `scripts/`, including
`research_state.py`, `validate_pipeline.py` and `legacy_pipeline.py`.
Blueprint uses the manage skill's `resourceBase/runtime/blueprintctl.py`.
""",
	"lean-verify": """
Plugin-level Lean helpers, templates and tests live in this bundle's
`scripts/` and `assets/`. Resolve the Lean toolchain for the actual project.
""",
}

RUNTIME_NOTES = {
	Name: RUNTIME_COMMON + Details + "\n[DSH execution options](references/dsh-execution.md).\n"
	for Name, Details in RUNTIME_DETAILS.items()
}

DSH_CHANGELOGS = {
	Name: """## Changelog (2026-09-09, DSH 2.0 adaptation)

- Short runtime notes describe skill loading and bundled paths. Research
  choices remain with the parent 2.0 guidance and the user's project.
- Background jobs and task fan-out are optional execution tools; the layer
  adds no prescribed research roles, stage sequence or quota procedure.
- Sync carries root smoke/unit tests, plugin-level helpers and v2 guides.
  Only declared layout rewrites and DSH-owned files differ from the parent.
"""
	for Name in SKILL_NAMES
}

WORKFLOW_DOCTOR_STEP_OLD = """3. Run the environment preflight (`scripts/doctor.py`). On a hard `FAIL`,
   apply the printed repair command (usually `codex plugin add
   math-research-workflow@math-research`) before any dispatch; the desktop app
   may rewrite `config.toml` and drop plugin-enable entries between sessions.
   If same-name skill copies are suspected, add `--source-inventory --json`.
   Resolve the loaded `SKILL.md` path; inventory hashes do not identify which
   copy the model loaded and do not authorize deleting another installation.
"""

WORKFLOW_DOCTOR_STEP_NEW = """3. If installation diagnostics are needed, run the checkout's
   `scripts/dsh-doctor.py`. Add `--require-lean` when diagnosing Lean.
"""

WORKFLOW_REFERENCE_OLD = """- `scripts/doctor.py` -- environment preflight for the plugin, its dependency
  skills, the marketplace, the `config.toml` enable entry and optional physical
  skill-source hashes (`--source-inventory`).
"""

WORKFLOW_REFERENCE_NEW = """- Repository-level `scripts/dsh-doctor.py` -- optional DSH installation
  diagnostics, available in a repository checkout.
"""

DSH_EXECUTION_MD = """# DSH execution options

This reference describes runtime tools. Choose them when they help the current
work. The parent skill and the user's project determine research and review.

## Files and long-running work

Load a skill by its exact name with `skill`; use the returned `resourceBase`
for its references and helpers. The four skills can be used independently.
Plugin-level helpers are merged into the corresponding DSH skill's `scripts/`;
the manage Blueprint gateway is `<resourceBase>/runtime/blueprintctl.py`.

For long shell work, DSH can return a background job ID with
`run_in_background: true`. Keep the actual job ID and input identity with the
project's current progress. Collect results with `job_output`; `job_kill` can
stop a job when authorized. Reconcile a job of unknown status before
redispatching that action. Process completion alone is not mathematical proof.
The workflow skill's `references/v2-continuity.md` documents durable helpers.

For truncated output, save full logs and read the relevant ranges. A repository
checkout additionally provides `scripts/dsh_run.py` for complete logs and a
compact verdict, `scripts/dsh-doctor.py` for installation diagnostics and
`scripts/context-audit.py` for inspecting context size. These checkout helpers
are optional and are not included in the npm skill bundle.

## Optional collaboration

When collaboration is useful and authorized, `subagent` starts from the supplied
prompt; `subagent_fork` carries the conversation. Supply the relevant artifacts
and describe the scope of the review or task. Choose the number of agents and
result format for the work at hand. A fresh agent adds a separate perspective;
its verdict still needs identifiable evidence.

For a batch of independent tasks, the workflow bundle retains
`assets/dsh-solve-audit-workflow.js` as a compatibility filename. Its 2.0 body
runs explicit task prompts with optional dependencies. It assigns no research
roles, infers no proof status and creates no subsequent verification stage.
Dependent tasks run after their dependencies finish; cycles and missing task
IDs are rejected before dispatch. A completion is an execution result, not an
accepted mathematical claim.

## Source reading

Use bounded source reads and keep raw input, version and locators. A parser or
vision tool can help transcribe a difficult page; compare mathematical content
with the original before relying on it. Optional capabilities are described in
`dsh-optional-capabilities.md` in the rigorous and manage bundles.
"""

WORKFLOW_TEMPLATE_JS = """// Optional DSH task fan-out. Compatibility filename, template version 3.
// args.tasks: [{id, prompt, deps?: [id], model?}]. Results are execution output.
// Supply each task's artifact paths in its prompt. No filesystem access here.

const Tasks = args.tasks || []
const ById = new Map()
for(const Task of Tasks)
{
	if(!Task.id || ById.has(Task.id) || typeof Task.prompt !== "string")
	{
		throw new Error("Each task needs a unique id and a prompt")
	}
	ById.set(Task.id, Task)
}
for(const Task of Tasks)
{
	if(Task.deps !== undefined && !Array.isArray(Task.deps))
	{
		throw new Error("deps must be an array: " + Task.id)
	}
	for(const Dependency of Task.deps || [])
	{
		if(!ById.has(Dependency))
		{
			throw new Error("Unknown dependency: " + Dependency)
		}
	}
}
const Planned = new Set()
const Waves = []
while(Planned.size < Tasks.length)
{
	const Wave = Tasks.filter(Task => !Planned.has(Task.id)
		&& (Task.deps || []).every(Id => Planned.has(Id)))
	if(Wave.length === 0)
	{
		throw new Error("Task dependencies contain a cycle")
	}
	Waves.push(Wave)
	Wave.forEach(Task => Planned.add(Task.id))
}

const Results = []
phase("tasks")
for(const Wave of Waves)
{
	const Completed = await pipeline(Wave, async (Task) =>
	{
		const Options = { label: Task.id }
		if(Task.model)
		{
			Options.model = Task.model
		}
		const Result = await agent(Task.prompt, Options)
		return { id: Task.id, result: Result }
	})
	Results.push(...Completed)
}
return { results: Results }
"""

OPTIONAL_CAPABILITIES_MD = """# Optional source-reading capabilities

DSH deployments may provide document parsing, OCR or vision tools. Inspect the
available tool descriptions and local deployment documentation before use;
the research bundle does not install providers or change profile/auth settings.

Use an existing text layer for readable PDFs. For scanned or layout-heavy
sources, preserve the raw file, parser name/version, extracted text and page or
region locators. Check formulas, hypotheses and cited statements against the
original page when using them in an argument. OCR is transcription evidence,
not proof or a substitute for reading the source.

Capture the obtained material with the manage bundle's
`scripts/research_library.py`. Keep capture, actual reading, interpretation and
verified mathematical use distinct. Save large outputs to files and read
bounded ranges; attach agent annotations to the version actually consulted.
"""

# DSH-layer-owned files added to bundles (relative path -> content)
LAYER_FILES = {
	Name: {"references/dsh-execution.md": DSH_EXECUTION_MD}
	for Name in SKILL_NAMES
}
for Name in ("rigorous-open-math-research", "manage-math-research-program"):
	LAYER_FILES[Name]["references/dsh-optional-capabilities.md"] = OPTIONAL_CAPABILITIES_MD
LAYER_FILES["math-research-workflow"]["assets/dsh-solve-audit-workflow.js"] = WORKFLOW_TEMPLATE_JS

# Parent layout changes are replayed only by this adaptation layer.
BUNDLE_PATH_REWRITES = {
	"manage-math-research-program": (
		("In a Codex plugin install, the gateway is", "In this DSH bundle, the gateway is"),
		("../../runtime/", "runtime/"),
	),
}
BUNDLE_FILE_REWRITES = {
	("lean-verify", "scripts/tests/test_v2_verifier.py"): (
		('dir=Path(__file__).parent', 'dir=os.environ.get("LEAN_VERIFY_TEST_TMPDIR")'),
	),
	("lean-verify", "scripts/tests/test_v2_lean_real.py"): (
		('dir=os.environ.get("LEAN_VERIFY_TEST_TMPDIR", Path(__file__).parent)',
		 'dir=os.environ.get("LEAN_VERIFY_TEST_TMPDIR")'),
	),
}
DOC_SOURCES = ("docs/pipeline-full-flow.md", "docs/v2.0-guide.md")
LEAN_RUNTIME_FIXTURE = "tests/fixtures/lean-v2-runtime"
LEAN_RUNTIME_PACKAGE_FILES = ("lean-toolchain", "lakefile.toml", "lake-manifest.json")
DSH_TEST_FILES = {
	"smoke_doctor.py", "smoke_dsh_run.py", "smoke_context_audit.py",
	"smoke_version_bump.py", "test_sync_from_parent.py",
}
ROOT_TEST_PATH_REWRITES = {
	"test_research_state.py": (
		('state.inspect_project(self.Project)["progress"].endswith("state/RESUME.md")',
		 'Path(state.inspect_project(self.Project)["progress"]).as_posix().endswith("state/RESUME.md")'),
	),
}



def rewrite_parent_paths(Text: str) -> str:
	for Name, Source in BUNDLE_SOURCES.items():
		Text = Text.replace(Source, f"skills/{Name}")
		for Extra in EXTRA_SOURCES.get(Name, ()):
			Text = Text.replace(f"plugins/{Name}/{Extra}", f"skills/{Name}/{Extra}")
		Prefix = rf'''["']plugins["']\s*/\s*["']{re.escape(Name)}["']'''
		SkillSuffix = rf'''\s*/\s*["']skills["']\s*/\s*["']{re.escape(Name)}["']'''
		Text = re.sub(Prefix + SkillSuffix, f'"skills" / "{Name}"', Text)
		Text = re.sub(Prefix, f'"skills" / "{Name}"', Text)
	return Text


def rewrite_smoke_paths(text: str) -> str:
    """Rewrite upstream smoke-test bundle paths to the DSH layout.

    Upstream tests run against the Codex plugin layout
    (plugins/<plugin>/skills/<plugin>/...), while DSH bundles live under
    skills/<plugin>/... . The rewrites handle both one-line and multi-line
    path expressions; smoke_doctor.py is not synced (replaced by the DSH
    doctor smoke for scripts/dsh-doctor.py).
    """
    bundle_version = json.loads((REPO / "package.json").read_text(encoding="utf-8"))["version"]
    text = rewrite_parent_paths(text)
    if "closure-first smoke passed" in text:
        text = text.replace(
            '\trigorous_skill = RIGOROUS / "skills" / "rigorous-open-math-research"',
            "\trigorous_skill = RIGOROUS",
        )
        text = text.replace(
            '\tworkflow_skill = WORKFLOW / "skills" / "math-research-workflow"',
            "\tworkflow_skill = WORKFLOW",
        )
        text = re.sub(
            r'\tfor plugin in \(RIGOROUS, WORKFLOW\):\n'
            r'\t\tmanifest = json\.loads\(\(plugin / "\.codex-plugin" / "plugin\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
            r'\t\tif manifest\["version"\] != "(?P<version>\d+\.\d+\.\d+)":\n'
            r'\t\t\traise AssertionError\(f"\{manifest\[\'name\'\]\} version is not (?P=version)"\)',
            lambda match: (
                '\tpackage = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))\n'
                f'\tif package["version"] != "{bundle_version}":\n'
                f'\t\traise AssertionError("DSH package version is not {bundle_version}")'
            ),
            text,
        )
        text = re.sub(
            r'\texpected_versions = \{RIGOROUS: "\d+\.\d+\.\d+", WORKFLOW: "(?P<version>\d+\.\d+\.\d+)"\}\n'
            r'\tfor plugin, expected_version in expected_versions\.items\(\):\n'
            r'\t\tmanifest = json\.loads\(\(plugin / "\.codex-plugin" / "plugin\.json"\)\.read_text\(encoding="utf-8"\)\)\n'
            r'\t\tif manifest\["version"\] != expected_version:\n'
            r'\t\t\traise AssertionError\(\n'
            r'\t\t\t\tf"\{manifest\[\'name\'\]\} version is not \{expected_version\}"\n'
            r'\t\t\t\)',
            lambda match: (
                '\tpackage = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))\n'
                f'\tif package["version"] != "{bundle_version}":\n'
                f'\t\traise AssertionError("DSH package version is not {bundle_version}")'
            ),
            text,
        )
    if "checkpoint resume smoke passed" in text:
        text = text.replace(
            'WORKFLOW_SKILL = WORKFLOW / "skills" / "math-research-workflow"',
            "WORKFLOW_SKILL = WORKFLOW",
        )
    return text


def expected_tests(Upstream: Path) -> dict[str, str]:
	"""Carry root smoke/unit tests and fixtures, preserving DSH-owned tests."""
	LeanFixture = Upstream / LEAN_RUNTIME_FIXTURE
	if(LeanFixture.exists()):
		Missing = [Name for Name in LEAN_RUNTIME_PACKAGE_FILES if not (LeanFixture / Name).is_file()]
		if(Missing):
			raise ValueError(f"incomplete {LEAN_RUNTIME_FIXTURE}: missing {', '.join(Missing)}")
	Output: dict[str, str] = {}
	TestsRoot = Upstream / "tests"
	TestFiles = set(TestsRoot.glob("smoke_*.py")) | set(TestsRoot.glob("test_*.py"))
	for Test in sorted(TestFiles):
		if(Test.name in DSH_TEST_FILES):
			continue
		Content = rewrite_smoke_paths(read_norm(Test))
		for Before, After in ROOT_TEST_PATH_REWRITES.get(Test.name, ()):
			Content = Content.replace(Before, After)
		Output[f"tests/{Test.name}"] = Content
	FixturesRoot = TestsRoot / "fixtures"
	for Fixture in sorted(FixturesRoot.rglob("*")):
		if(Fixture.is_file() and not is_transient(Fixture)):
			Relative = Fixture.relative_to(FixturesRoot).as_posix()
			Output[f"tests/fixtures/{Relative}"] = read_norm(Fixture)
	return Output


def sync_tests(upstream: Path, Destination: Path | None = None) -> None:
    for rel, content in expected_tests(upstream).items():
        write_norm((Destination or REPO) / rel, content)


def expected_docs(upstream: Path) -> dict[str, str]:
	Output = {}
	Commit = upstream_head(upstream)
	for Relative in DOC_SOURCES:
		Source = upstream / Relative
		if(not Source.is_file()):
			continue
		Text = rewrite_parent_paths(read_norm(Source))
		Text = Text.replace(
			"Same-name skill copies can be diagnosed with `doctor.py --source-inventory\n--json`; resolve the loaded path before executing helpers.",
			"For DSH installation diagnostics use repository `scripts/dsh-doctor.py`;\nresolve the loaded skill path before executing helpers.",
		)
		def rewrite_link(Match):
			Target = Match.group(2)
			if("://" in Target or Target.startswith(("#", "/"))):
				return Match.group(0)
			FilePart, Separator, Anchor = Target.partition("#")
			Resolved = (Source.parent / FilePart).resolve()
			try:
				ParentPath = Resolved.relative_to(upstream.resolve()).as_posix()
			except ValueError:
				return Match.group(0)
			if(ParentPath in DOC_SOURCES or ParentPath.startswith("skills/") or not Resolved.is_file()):
				return Match.group(0)
			Url = f"https://github.com/xsoc1/rigorous-open-math-research/blob/{Commit}/{ParentPath}"
			return Match.group(1) + Url + Separator + Anchor + ")"
		Text = re.sub(r"(\[[^\]]+\]\()([^\s)]+)\)", rewrite_link, Text)
		Output[Relative] = Text
	return Output


def sync_docs(upstream: Path, Destination: Path | None = None) -> None:
    for rel, content in expected_docs(upstream).items():
        write_norm((Destination or REPO) / rel, content)


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


def is_transient(path: Path) -> bool:
    """Execution artifacts (bytecode caches, dsh_run logs), not repo content."""
    return (
        "__pycache__" in path.parts
        or ".lake" in path.parts
        or path.suffix == ".pyc"
        or ".dsh_run.log" in path.name
    )


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


def split_changelog(text: str) -> tuple[str, str]:
    """Split at the first '## Changelog' heading; returns (body, changelog)."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("## Changelog"):
            return "\n".join(lines[:idx]).rstrip("\n") + "\n", "\n".join(lines[idx:]) + "\n"
    return text, ""


def apply_dsh_layer(bundle: Path, name: str) -> None:
    skill_md = bundle / "SKILL.md"
    text = read_norm(skill_md)
    text = insert_after_frontmatter(text, RUNTIME_NOTES[name])
    if name == "math-research-workflow":
        if WORKFLOW_DOCTOR_STEP_OLD in text:
            text = replace_once(text, WORKFLOW_DOCTOR_STEP_OLD, WORKFLOW_DOCTOR_STEP_NEW)
        if WORKFLOW_REFERENCE_OLD in text:
            text = replace_once(text, WORKFLOW_REFERENCE_OLD, WORKFLOW_REFERENCE_NEW)
    body, changelog = split_changelog(text)
    history_path = bundle / "references" / "changelog.md"
    if history_path.is_file():
        history = read_norm(history_path).rstrip() + "\n"
    elif changelog:
        history = "# Release history\n\n" + changelog.rstrip() + "\n"
    else:
        history = ""
    if changelog and CHANGELOG_POINTER_MARKER not in body:
        body = body.rstrip("\n") + "\n\n" + CHANGELOG_POINTER + "\n"
    if DSH_CHANGELOGS.get(name):
        history = history.rstrip() + "\n\n" + DSH_CHANGELOGS[name].rstrip() + "\n"
    if history:
        write_norm(history_path, history)
    write_norm(skill_md, body)
    for rel, content in LAYER_FILES.get(name, {}).items():
        write_norm(bundle / rel, content)
    for Document in bundle.rglob("*.md"):
        Original = read_norm(Document)
        Rewritten = Original
        for Before, After in BUNDLE_PATH_REWRITES.get(name, ()):
            Rewritten = Rewritten.replace(Before, After)
        if Rewritten != Original:
            write_norm(Document, Rewritten)
    for (Name, Relative), Replacements in BUNDLE_FILE_REWRITES.items():
        Target = bundle / Relative
        if Name == name and Target.is_file():
            Original = read_norm(Target)
            Rewritten = Original
            for Before, After in Replacements:
                Rewritten = Rewritten.replace(Before, After)
            if Rewritten != Original:
                write_norm(Target, Rewritten)


def normalize_tree(root: Path) -> None:
    """Rewrite text files with LF endings: upstream working trees checked out
    on Windows may carry CRLF, while this repository commits LF only."""
    for p in root.rglob("*"):
        if (
            p.is_file()
            and not is_transient(p)
            and p.suffix.lower() in TEXT_SUFFIXES
        ):
            p.write_bytes(normalize(p.read_bytes()))


def copy_bundles(upstream: Path, dest_root: Path) -> None:
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)
    for name in SKILL_NAMES:
        src = upstream / BUNDLE_SOURCES[name]
        dst = dest_root / name
        shutil.copytree(src, dst, ignore=copy_ignores)
        for extra in EXTRA_SOURCES.get(name, ()):
            extra_src = upstream / "plugins" / name / extra
            extra_dst = dst / extra
            if not extra_src.is_dir():
                raise FileNotFoundError(f"missing plugin-level dir: {extra_src}")
            shutil.copytree(extra_src, extra_dst, dirs_exist_ok=True, ignore=copy_ignores)
            for rel in EXTRA_EXCLUDES:
                if rel.startswith(f"{name}/"):
                    victim = dst / rel.split("/", 1)[1]
                    if victim.is_dir():
                        shutil.rmtree(victim)
                    elif victim.exists():
                        victim.unlink()
        normalize_tree(dst)
        apply_dsh_layer(dst, name)


def copy_ignores(Directory: str, Names: list[str]) -> set[str]:
	Ignored = COPY_IGNORES(Directory, Names)
	if(Path(Directory).name == "tests"):
		Ignored.update(Name for Name in Names if Name == "_probe" or Name.startswith(("unit-", "real-")))
	return Ignored


def regen_manifest(bundle: Path) -> None:
    # Sort by the POSIX-style relative path STRING: Path objects compare
    # case-insensitively on Windows (pathlib normcase) but case-sensitively
    # on POSIX, which would make the generated MANIFEST content differ
    # between platforms. Plain str comparison is code-point based everywhere.
    files = [
        p
        for p in bundle.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256" and not is_transient(p)
    ]
    entries = []
    for p in sorted(files, key=lambda path: path.relative_to(bundle).as_posix()):
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


def upstream_dirty(Upstream: Path) -> bool:
	Result = subprocess.run(
		["git", "-C", str(Upstream), "status", "--porcelain", "--untracked-files=all"],
		capture_output=True, text=True, errors="replace", check=True,
	)
	return bool(Result.stdout.strip())


def write_snapshot(Upstream: Path, Destination: Path, Commit: str) -> dict:
	Tests = expected_tests(Upstream)
	copy_bundles(Upstream, Destination / "skills")
	regen_manifest(Destination / "skills/manage-math-research-program")
	for Relative, Content in Tests.items():
		write_norm(Destination / Relative, Content)
	sync_docs(Upstream, Destination)
	Lock = build_lock(Destination / "skills", Commit)
	write_norm(Destination / "upstream.lock.json", json.dumps(Lock, indent=2, sort_keys=True) + "\n")
	return Lock


def write_preview(Upstream: Path, Destination: Path, Commit: str) -> dict:
	Destination = Destination.resolve()
	if(Destination.is_relative_to(REPO.resolve()) or Destination.is_relative_to(Upstream.resolve())):
		raise ValueError("preview must be outside both the DSH repository and the parent source")
	Destination.mkdir(parents=True, exist_ok=False)
	for Name in ("scripts", "tests", "docs", ".github"):
		if((REPO / Name).is_dir()):
			shutil.copytree(REPO / Name, Destination / Name, ignore=COPY_IGNORES)
	for Name in ("package.json", "index.mjs", "cordis.patch.yml", "README.md", "README_EN.md", "AGENTS.md", "AGENTS_HISTORY.md", "LICENSE"):
		shutil.copyfile(REPO / Name, Destination / Name)
	Lock = write_snapshot(Upstream, Destination, Commit)
	write_norm(Destination / "PREVIEW.json", json.dumps({
		"release_ready": False, "source": str(Upstream), "source_head": Commit,
		"source_dirty": upstream_dirty(Upstream),
		"note": "Unpublished preview only. Confirm the published parent before live synchronization.",
	}, indent=2) + "\n")
	return Lock


def main() -> int:
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--upstream", type=Path)
	Modes = Parser.add_mutually_exclusive_group()
	Modes.add_argument("--check", action="store_true")
	Modes.add_argument("--preview", type=Path, help="prepare an external, new directory without changing this checkout")
	Parser.add_argument("--expect-commit", help="require this exact frozen parent HEAD")
	Args = Parser.parse_args()
	Upstream = (Args.upstream or default_upstream()).resolve()
	try:
		if(not Upstream.is_dir()):
			raise ValueError(f"upstream clone not found: {Upstream}")
		Commit = upstream_head(Upstream)
		if(Args.expect_commit and Args.expect_commit != Commit):
			raise ValueError(f"parent HEAD differs from --expect-commit: {Commit}")
		if(Args.preview):
			Lock = write_preview(Upstream, Args.preview, Commit)
			print(f"PREVIEW ONLY: {Args.preview.resolve()} ({len(Lock['files'])} bundled files)")
			print("Official skills/ and upstream.lock.json were not changed.")
			return 0
		if(upstream_dirty(Upstream)):
			raise ValueError("parent has uncommitted files; freeze it or use --preview outside both repositories")
		if(Args.check):
			return run_check(Upstream)
		Lock = write_snapshot(Upstream, REPO, Commit)
		print(f"synced from upstream {Commit}")
		print(f"locked {len(Lock['files'])} files in upstream.lock.json")
		return 0
	except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as Error:
		print(f"FAIL: {Error}", file=sys.stderr)
		return 1


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
        # tests tree parity: upstream smokes (path-rewritten) + fixtures must
        # match the repository copy exactly, so upstream test additions can
        # never be forgotten again
        for rel, expected_text in sorted(expected_tests(upstream).items()):
            cur_path = REPO / rel
            cur_text = read_norm(cur_path) if cur_path.is_file() else None
            if cur_text != expected_text:
                problems.append(f"drift in {rel}")
        for rel, expected_text in sorted(expected_docs(upstream).items()):
            cur_path = REPO / rel
            cur_text = read_norm(cur_path) if cur_path.is_file() else None
            if cur_text != expected_text:
                problems.append(f"drift in {rel}")
    if problems:
        print("FAIL: sync check found drift:")
        for line in problems:
            print("  " + line)
        return 1
    print(f"sync check clean (upstream {commit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
