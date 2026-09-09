# DSH 2.0 release validation

DSH 2.0.0 is synchronized from published parent main commit
`72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803`. The coordinator confirmed that
origin/main, fork/main and both v2.0.0 tags match, and
[parent CI 34336134215](https://github.com/xsoc1/rigorous-open-math-research/actions/runs/34336134215)
passed all five jobs, including all 15 real Lean controls. DSH publication and
its own CI verification are authorized. This release preserves the existing
installation method and does not restart DSH or edit auth/profile.

## Source and adaptation

Formal synchronization requires a clean canonical parent and its complete SHA:

```sh
python scripts/sync-from-parent.py --upstream <canonical-parent> --expect-commit 72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803
python scripts/sync-from-parent.py --upstream <canonical-parent> --expect-commit 72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803 --check
python scripts/validate_all.py .
python scripts/dsh-check-bundle.py
```

The local canonical path is
`~/.dsh/_math-research-upstream/rigorous-open-math-research`. It was absent in
the resumed environment and was recreated from official published main. Its
clean HEAD, origin/main and v2.0.0 were verified before actual synchronization.
The resulting lock covers 140 skill files. The 221 code, test, configuration
and bundle input files match the isolated exact-candidate preview byte for
byte, including all three Lean fixture files. Local acceptance runs against
the actual synchronized DSH checkout.

The four short guides retain parent research choices. DSH adds loading notes,
portable paths and optional execution tools. Historical phases, roles and
quota procedures remain compatibility references, not 2.0 research gates.
Only declared layout rewrites, DSH-owned helpers and generated inventories
differ from the parent. Never hand-edit synchronized content.

## Current checkout acceptance

Install `pyyaml` and `jsonschema` in the test environment. Node.js is used by
the optional task-template test. Run these checks in the DSH checkout:

```sh
python tests/test_sync_from_parent.py -v
python tests/test_research_state.py -v
python -m unittest discover -s skills/manage-math-research-program/scripts/tests -p 'test_*.py' -v
python -m unittest discover -s skills/lean-verify/scripts/tests -p 'test_*.py' -v
```

Run every `tests/smoke_*.py` individually. Both README indexes enumerate all
21 root smoke scripts and both unit-test filenames; the validator checks this
index. The 1.x tests exercise retained compatibility helpers. Their success
does not impose the historical pipeline on new research.

The root unit suite contains nine DSH adaptation controls and 27 recovery
controls. Two recovery controls require native Windows and explicitly skip
on Linux. CI runs portable controls on both platforms.

## Optional Q9 evidence

The bundled Q9 test retains the parent's ancestor search for
`benchmarks/codex-20260908-q9/evidence`. If those optional original inputs are
absent, unittest reports SKIP. Direct invocation with `--output` fails with a
clear missing-fixture error before creating replay output. A skip is not a
successful replay. No special DSH repository-root rewrite is needed.

CI sync-check checks out the lock's exact parent commit, checks adaptation
parity, then requires original-source replay and retains the output:

```sh
python <frozen-parent>/plugins/manage-math-research-program/skills/manage-math-research-program/scripts/tests/test_library_q9_reuse.py --output <new-external-output>
```

This reuses existing evidence deterministically. It makes no new mathematical
discovery, agent-performance or complete-Q9-formalization claim.

## Real Lean acceptance

Portable Lean controls run without a compiler. All 15 real compiler controls
explicitly SKIP unless `LEAN_VERIFY_REAL_LEAN` is set. For actual verification,
set it to the pinned Lean executable and optionally set `LEAN_VERIFY_REAL_LAKE`.
Use native Windows Python and Lean.exe for local Windows SDK verification.

Set `LEAN_VERIFY_TEST_TMPDIR` to external storage, `LEAN_VERIFY_TEST_REPORT`
to an external report path and `LEAN_VERIFY_KEEP_TEST_ARTIFACTS=1` to retain
actual compiler evidence. From `tests/fixtures/lean-v2-runtime`, run discovery
with an absolute path to the synchronized suite:

```sh
python -m unittest discover -s <absolute-dsh-checkout>/skills/lean-verify/scripts/tests -p 'test_v2_lean_real.py' -v
```

The fixture pins Lean 4.31.0 and includes `lean-toolchain`, `lakefile.toml` and
the actual parent-generated `lake-manifest.json`. Sync requires all three
before changing a destination and excludes `.lake/` caches. The dedicated CI
job installs jsonschema and uses `leanprover/lean-action@v1` with this fixture
as `lake-package-directory`, even when automatic build/test/lint are disabled.
It starts Python tests in that pinned directory and retains actual reports
and artifacts. Helper subprocesses also carry their own project toolchain
context. Elan needs no global default; never invoke Lean at an unpinned root.

## Evidence and release publication

Keep test logs, the input inventory and exact executable/environment metadata
together. Preview behavior results may be reused only when the applicable
actual inputs match byte for byte. Any changed input requires affected checks
to run again. Proof receipts remain bound to their original project paths and
environment; copying a receipt never establishes current proof evidence at a
new path. This release runs local actual compiler tests against the live DSH
code and retains their disposable projects at their original external paths.

After local checks, review the final diff, ensure the package version and both
README release statements agree, and commit/push to origin. Verify the DSH CI
run for that exact commit, including sync-check, version-bump, structure/smoke,
Windows/Linux portable controls and the dedicated real Lean job. The external
`dsh-prep-report.md` records the DSH commit, CI link and final validation counts;
historical dirty-source previews are not release evidence.
