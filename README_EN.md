# math-research-dsh

[中文](README.md)

A DSH (DeepSeek Harness) skill bundle for long-term mathematics research.
It adapts the four [math-research parent plugins](https://github.com/xsoc1/rigorous-open-math-research)
in one direction, supporting source reading, annotatable tools and research experience,
session continuity, and Lean verification when useful.

The current version is **2.0.0**, synchronized from published parent main commit
[`72a1cc17`](https://github.com/xsoc1/rigorous-open-math-research/commit/72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803).
[upstream.lock.json](upstream.lock.json) records the complete parent commit and bundled file hashes.

## Choose an entry

| Skill | Work it supports |
| --- | --- |
| `math-research-workflow` | Choose research tools, maintain current progress, resume sessions and actual jobs |
| `manage-math-research-program` | Literature, tool cards and annotations, experience comparisons, human editable understanding, accepted Blueprint knowledge |
| `rigorous-open-math-research` | Develop proofs or counterexamples, understand successful and failed routes, review arguments as useful |
| `lean-verify` | Compiler feedback, exact targets and transitive axioms, semantic review and reproducible evidence |

2.0 supplies methods and executable tools. Researchers and agents choose the methods,
collaboration and verification scope for each problem. Compatibility helpers retain
old sealed checkpoints and pipelines; the old full validator requires `--legacy-v1`.
Historical stage, role and quota rules belong to their original records.

The DSH `skill` tool loads a skill by its exact name and returns its text and
`resourceBase`. Resolve packaged files and Python helpers there. Parent `$skill-name`
references map to this tool; `/skill-name` on the first line of a user message is
also supported.

## Install

Choose one installation method to avoid registering the same skills twice.

**Bundle installation**:

```sh
dsh plugin --profile web add github:xsoc1/math-research-dsh
```

`package.json`, `cordis.patch.yml` and `index.mjs` register packaged skill roots
using DSH's `FileSystemSkillProvider`. Activate a new installation through the
profile reload procedure for your DSH deployment.

**Local development and junction installation**:

```powershell
if($env:DSH_HOME)
{
	$DshHomePath = $env:DSH_HOME
}
else
{
	$DshHomePath = Join-Path $HOME '.dsh'
}
$DshRepoPath = Join-Path $DshHomePath 'math-research-dsh'
git clone https://github.com/xsoc1/math-research-dsh.git $DshRepoPath
powershell -ExecutionPolicy Bypass -File (Join-Path $DshRepoPath 'install.ps1')
python (Join-Path $DshRepoPath 'scripts/dsh-doctor.py')
```

`install.ps1` links all four directories into the user skill root. Project installs
can use `.dsh/skills` or `.agents/skills`. Replacing an ordinary directory copy
requires explicitly selecting `install.ps1 -Force`. Checkout helpers include
`dsh_run.py` for full logs and `context-audit.py` for inspecting context size;
they are not included in the npm `skills/` bundle.

## One-way synchronization and maintenance

The parent owns research guidance and mathematical implementations. This repository
owns DSH loading, layout mapping, packaging and test adaptation. Change upstream
content in the parent, then replay
[scripts/sync-from-parent.py](scripts/sync-from-parent.py).

The synchronizer copies all four skills, merges plugin-level workflow/Lean
`scripts/` and `assets/`, relocates manage `runtime/` into its skill root, carries
root smoke/unit tests and fixtures, and rewrites 2.0 guide links. Q9 tests retain
the parent's ancestor-based evidence discovery; benchmarks are not bundled.
Formal sync regenerates manage `MANIFEST.sha256` and
`upstream.lock.json`, bound to the parent commit.

```sh
python scripts/sync-from-parent.py --upstream <clean-parent-clone> --expect-commit <full-parent-commit>
python scripts/sync-from-parent.py --upstream <clean-parent-clone> --expect-commit <full-parent-commit> --check
python scripts/validate_all.py .
python scripts/dsh-check-bundle.py
```

Use `--preview <new-external-directory>` to trial an in-progress parent without
changing the official tree. The preview contains `PREVIEW.json` and is not a
release from a frozen commit. Commands and evidence boundaries are in
[2.0 release validation](docs/v2-release-validation.md).

Maintenance rules:

1. Run repository validation and relevant behavior tests after changes. Check bundle packaging and sync before committing.
2. Do not hand-edit synchronized `skills/`, tests or docs. Replay DSH differences through layer constants and explicit path rewrites in the sync script.
3. Keep both READMEs linked and their test indexes aligned. Use UTF-8 without BOM, LF and English punctuation.
4. Bump `package.json` for content changes. After committing, push in `project.json`'s `git_sync.push_order`.
5. Use the canonical clone's published main for formal sync; working sources and unpublished candidates are external-preview inputs only.
6. Adaptation does not modify the harness, profile or auth. Installation and process operations belong to the actual deployment task.

## Test index

The 21 root smoke tests run individually with `python tests/<filename>`. The 1.x tests
cover compatibility code, not required 2.0 research behavior. Run root unit tests
with `python -m unittest discover -s tests -p 'test_*.py' -v`.
Install `pyyaml` and `jsonschema` in the test environment. The optional task
template's behavior test uses Node.js.

| Scope | Root test files |
| --- | --- |
| DSH adaptation and packaging | `test_sync_from_parent.py`, `smoke_doctor.py`, `smoke_dsh_run.py`, `smoke_context_audit.py`, `smoke_version_bump.py` |
| 2.0 continuity | `test_research_state.py`, `smoke_recovery_status.py` |
| Literature and observation | `smoke_research_library.py`, `smoke_performance_metrics.py`, `smoke_skill_sources.py` |
| Blueprint and Git | `smoke_blueprint_gateway.py`, `smoke_sync_remotes.py` |
| Lean compatibility | `smoke_lean_verify.py`, `smoke_lake_build_guard.py` |
| 1.x pipeline compatibility | `smoke_pipeline_gate.py`, `smoke_scoped_pipeline.py`, `smoke_nested_repo.py`, `smoke_closure_first.py` |
| 1.x state and handoff compatibility | `smoke_handoff.py`, `smoke_checkpoint_resume.py`, `smoke_formalization.py`, `smoke_formalization_handoff.py`, `smoke_whiteboard.py` |

Bundled plugin tests:

- `skills/manage-math-research-program/scripts/tests/`: `test_research_experience.py`,
  `test_research_library_v2.py`, `test_library_q9_reuse.py`.
- `skills/lean-verify/scripts/tests/`: `test_v2_verifier.py`, `test_v2_lean_real.py`.

Q9 tests look for `benchmarks/codex-20260908-q9/evidence` in ancestor directories.
An installed bundle without that evidence reports an explicit SKIP. Directly
requesting replay with `--output` then fails with a missing-evidence explanation.
Real Lean tests use `LEAN_VERIFY_REAL_LEAN` for a pinned executable and optionally
`LEAN_VERIFY_REAL_LAKE`. An unconfigured compiler is reported as skipped, not as
successful compiler verification. `LEAN_VERIFY_TEST_TMPDIR` can select external
test storage; otherwise tests use the system temporary directory. CI runs portable
tests on Windows/Linux and explicitly enables real Lean tests in a dedicated job,
using `leanprover/lean-action@v1` and the fixture's pinned 4.31.0 toolchain.
Its package directory is `tests/fixtures/lean-v2-runtime`. Sync preserves
`lean-toolchain`, `lakefile.toml` and the parent's generated `lake-manifest.json`,
excluding `.lake/` build caches. CI starts the tests in this pinned directory;
helpers execute Lean in their individual temporary projects with toolchain pins.
The sync-check job checks synchronization and replays original Q9 evidence from
the parent commit recorded by the lock, retaining the resulting evidence.

## Files and history

- `skills/`: synchronized skills, helpers, runtime, references and templates.
- `scripts/`, `tests/`: DSH maintenance tools and behavior tests.
- `docs/`: synchronized guides and DSH release validation notes.
- [AGENTS.md](AGENTS.md): working methods and current maintenance notes.
- [AGENTS_HISTORY.md](AGENTS_HISTORY.md): older maintenance, failures and method provenance; skill histories live in `references/changelog.md`.

License: [MIT](LICENSE).
