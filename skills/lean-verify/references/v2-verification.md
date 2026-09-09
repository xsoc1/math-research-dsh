# Local Lean verification and feedback

These tools check a requested Lean scope. They do not establish correspondence
with an informal mathematical problem merely because Lean accepted a file.
Run them with the project's pinned toolchain. No cloud account, extra database,
or second proof checker is required.

## Exact statement checks

From the plugin directory:

```bash
python scripts/verify_lean_project.py --project /path/to/lean-project \
  --target-file Main.lean --declaration MyNamespace.result \
  --expected-type 'True' --output /path/to/evidence
```

Replace `True` with the complete intended Lean type, including the original
mathematical assumptions. For a universe-polymorphic type, add
`--universes u,v`. Explicit, implicit, and instance binders are visible in the
elaborated type and checked during comparison. A theorem of type `H -> T`
does not discharge an expected type `T`.

A reusable JSON contract is accepted by `--contract contract.json`:

```json
{
  "file": "Main.lean",
  "declaration": "MyNamespace.result",
  "expected_type": "True",
  "universes": []
}
```

A contract may also pin `definition_hashes`, `type_sha256`,
`environment_sha256`, or `semantic_sha256` from an earlier extraction.
`--expect-manifest previous/run-manifest.json` binds an observed statement
version, including its definitions and environment. This provides mechanical
identity, not a new human judgment about its meaning. Definitions with the same
name but changed bodies invalidate the relevant identities. Mathematically
equivalent types that are not definitionally equal need an explicit Lean bridge
that yields the expected type.

The verifier compiles the current target and project-local imports into the
output directory. It does not overwrite the project's existing `.olean` files.
Lean's own header parser discovers imports, including quoted identifiers and
multiline imports. Each local dependency must resolve to its fresh output
artifact before the importing source is compiled. An unsupported header or
ambiguous source/artifact binding fails closed with retained diagnostic logs.
Prepared external modules may contain only compiled artifacts.
It then extracts the actual fully qualified declaration, elaborated type,
universe parameters, type/proof dependencies, definition closure, and Lean's
transitive axiom set. Imported theorem proofs and proofs used inside definitions
or types participate in this inspection. `propext`, `Classical.choice`, and
`Quot.sound` are allowed as a subset. `sorryAx`, additional axioms, unknown
constants, and unsafe dependencies keep the root open. A source-scan whitelist
cannot relax that root policy.

Freshness binds every module actually loaded during inspection, including
notation, macro and elaboration providers that disappear from the final type.
The inventory count must match the loaded environment. Semantic review identity
still uses the smaller type/definition dependency set; a fresh machine check
can retain a supplied review when the elaborated mathematical meaning is unchanged.
Full module hashing can be substantial for large imported environments. The
complete inventory stays in the evidence files; CLI output remains compact.

`target.expected_statement` separately records the elaborated expected type,
its transitive dependencies, axioms, definitions, modules, and semantic identity.
These are bound even when the actual type reduces to `True` and does not name
the expected definition. Its closure contributes to the imported artifact
inventory and reusable statement identity. The synthetic comparison axiom
itself is excluded; axioms reached through the expected type remain checked.

## Reading the result

`run-manifest.json` is the latest report. Its immutable per-run copy and full
stdout/stderr are under `lean-verification-runs/<run-id>/`. The output JSON
schema is `scripts/run_manifest.schema.json`. The existing
`assets/verification_output.schema.json` entry contains the identical v2 schema.
The unchanged legacy human audit schema is identifiable as
`assets/verification_output.v1.schema.json`; its verdict labels do not imply a
v2 root pass.

| Field | Meaning |
| --- | --- |
| `machine.status` / `build.commands` | Actual completed, failed, missing, unavailable, timed-out, or unknown execution |
| `machine_verification_passed` | Requested machine scope completed on current inputs; declaration mode includes successful extraction |
| `target` | Actual type, expected-type comparison, dependency and axiom facts, semantic and environment identities |
| `exact_root_passed` / `root_closure` | The specified expected type has a checked root with no disallowed dependencies and matching frozen identities |
| `semantic` | Separately recorded correspondence review, not invented by compilation |
| `evidence` | Input/configuration/tool hashes, source freshness, contract and log locations |

In declaration mode a compiler-accepted proof may depend on `sorryAx`. Its
machine execution can succeed while `exact_root_passed` is false. An axiom-free
checked declaration with no expected type is `declaration_closed_uncompared`.
A checked `H -> T` with expected `T` is `target_mismatch`. Neither is an exact
root pass. Unrelated open or failed routes do not block a root that actually
uses a complete proof. `lean_routes.py` optionally calculates AND/OR route
readiness; a graph's readiness cannot replace root materialization and checking.

To consume saved evidence without recompiling:

```bash
python scripts/lean_evidence.py --manifest /path/to/evidence/run-manifest.json
python scripts/lean_routes.py --graph /path/to/routes.json --root goal \
  --root-manifest /path/to/evidence/run-manifest.json
```

Both entry points recheck current sources, the complete recorded verifier and
runtime identities, configuration, imported and compiled artifacts, generated
inspection sources, extraction, execution jobs and full logs. The input
snapshot binds the expected contract, and derived statement, definition, axiom
policy and root-closure fields are recomputed. Empty or partial inventories,
changed contracts, changed hashes and stale success flags cannot establish
closure. The preserved per-run report must agree with the consumed report.
Reports predating these receipts require a new run; their original bytes need
not be modified. Add `--replay --output /path/to/new-evidence` to
`lean_evidence.py` for an actual new Lean check of the recorded target version.

Before accepting a saved receipt, the checker also invokes the recorded Lean
runtime with `--deps` to resolve every inventoried module in the current search
context. A newly added higher-priority `.olean` invalidates the receipt even if
the old artifacts and `LEAN_PATH` are unchanged. Missing runtime, failed
resolution, or changed resolved paths cannot establish current closure.
Resolution logs are retained separately under
`lean-verification-runs/rechecks/<check-id>/`; original run files are preserved.

A route graph has a `nodes` array. Each node has a unique nonempty `id` and a
64-character `semantic_sha256` from its checked statement. Optional `evidence`
contains a manifest path and its file `sha256`. Each item of `routes` has an
`id`, the current `statement_sha256`, and a nonempty `dependencies` array of
node IDs. Dependencies within a route are AND; alternative routes are OR.
Missing leaves and cycles remain open. A complete alternative makes the root
`ready_to_materialize`; only current evidence for the exact root can make it
`closed`. Unrelated open nodes may remain in the graph.

These local receipts check consistency and freshness, not publisher identity.
Someone able to replace all sources, logs, artifacts and receipts is outside
this trust boundary. Rechecking does not replay the proof in the Lean kernel and does not
renew an informal semantic audit. Apply the audit during a fresh verification
to test its current mathematical-source and semantic bindings.

Existing flags `--lean-files`, `--build`, `--build-targets`, `--use-cache`,
`--build-timeout`, `--whitelist`, and `--output` remain available. Without a build
or exact declaration request, the tool scans source only, launches no compiler,
and reports `machine_verification_passed=false`. Full `lake build` and cache
fetches remain explicit operations. With only file checks, no exact root pass
is inferred. Default exit 0 means a report was written, including a negative
report. Add `--strict-exit` when a command runner should fail on an incomplete
requested verification. Invalid invocation or an unwritable report returns 2.

The scanner understands Lean nested `/- ... -/` comments, line comments,
strings, raw strings, and quoted identifiers. It is a location aid rather than
an extensible Lean parser. The final axiom evidence comes from Lean itself.

## Reusable feedback

```bash
python scripts/lean_feedback.py --project /path/to/lean-project \
  --output /path/to/feedback-logs
```

Keep this process open and send one JSON request per line. It emits one response
per line. Positions are zero-based LSP lines and UTF-16 character offsets.

```json
{"action":"goals","file":"Main.lean","line":10,"character":2}
{"action":"diagnostics","file":"Main.lean"}
{"action":"hover","file":"Main.lean","line":8,"character":12}
{"action":"definition","file":"Main.lean","line":8,"character":12}
{"action":"symbols","file":"Main.lean","query":"lemma"}
{"action":"restart"}
{"action":"close"}
```

A request may include `text` for an unsaved trial buffer. It does not edit the
file. A one-shot caller can pass `--request '<JSON>'`. `symbols` searches the
current document's declarations, not the entire Mathlib library. Goal and term
goal responses may be null when the cursor is not at a corresponding location.

The LSP session waits for diagnostics for the requested document version and
binds responses to text and dependency identities. Source changes use
`didChange`; dependency/configuration changes restart the process. Never reuse
an old response as evidence for a new buffer. Protocol and stderr logs remain
available. Editor feedback always reports `exact_root_passed=false`.

`--backend auto` prefers LSP and falls back to a fresh Lean CLI check when the
server or protocol is unavailable. CLI provides actual compiler diagnostics;
it explicitly reports goals/hover/navigation as unsupported instead of
fabricating them. Use `--backend cli` directly when that is more convenient.
`--backend lsp` reports unsupported/unavailable states without fallback.

A disposable hash cache accelerates feedback on a trusted local filesystem;
file replacement, size, modification-time or change-time changes invalidate its
entries. Final root checks freshly hash their relevant imported artifacts.
Use `restart` after externally replacing a runtime or when cache identity is
uncertain. Windows mounted filesystems can impose substantial metadata-reading
cost, so reuse alone is not a measured performance claim.

## Semantic reviews and continuity

A review file records `result` (`faithful` to accept), `reviewer`, meaningful
`notes`, `independence`, and a `binding` to the extracted `declaration`,
`semantic_sha256`, and environment identity. Optional `source_hashes` map actual
informal-source paths to SHA-256 values. Their changes invalidate reuse too.
Use `--semantic-audit review.json` to apply it. A generated or self-authored
review must describe that provenance; do not label it an independent blind
readback. No review is synthesized when the file is absent.

The binding includes both the actual and expected statements and their reachable
definitions. Proof edits need
new machine checks, while an unchanged semantic binding can reuse its review.
A changed statement, important definition, source contract, or environment is
reported as stale. An old result or legacy label is not automatically rewritten
as a new verification.

For interruption recovery, launch long Lean checks through the workflow
plugin's `scripts/research_state.py` local-job interface. Supply the real input
files and retain its job ID. Its status/record-result mechanisms handle durable
jobs and external operations; this plugin supplies the compiler logs, run ID,
input snapshot, and final verification manifest. Process completion and a
reporter's exit 0 are not mathematical success. Choose `--strict-exit` or
inspect the manifest when integrating results.

`lake_build_guard.py` protects full project builds by live process identity and
an ownership token. It has no default attempt-count or time-window limit.
`--max-attempts`, `--window-minutes`, and `--lock-minutes` remain accepted legacy
arguments without imposing the old cap. Unknown legacy locks require owner
inspection; a live lock is never discarded just because it is old.

## Runtime and scope boundaries

`--lean EXE`, `--lake EXE`, and `--direct` select local executables. Direct mode
uses existing project and package build directories plus `LEAN_PATH`, with no
package download. Projects with custom Lake targets, custom package search
paths, or generated modules may need their normal Lake preparation first.
The tools do not silently replace a pinned environment or rebuild all Mathlib.
Windows executables launched from WSL receive converted filesystem paths.

The maintained Lean probe is a tab-indented `.lean.template`; generation
expands tabs because Lean rejects tab tokens. Generated Lean source is retained
with the verification evidence. The local compiler and imported artifacts are
a trust boundary. This is not a sandbox for malicious Lean plugins, elaborators,
or arbitrary untrusted code, and it does not claim an independent second
kernel replay. A timeout when WSL launches Windows subprocesses explicitly
records unconfirmed child cleanup if process-group termination cannot establish
that every Windows descendant stopped.

## Reproducible tests

The verifier itself uses the Python standard library. The test suite also uses
`jsonschema` to validate positive and negative manifests against the published
schema. From the marketplace root, run:

```bash
python3 -m unittest discover -s plugins/lean-verify/scripts/tests -p test_v2_verifier.py -v
python3 tests/smoke_lean_verify.py
```

The actual compiler controls are opt-in. Set `LEAN_VERIFY_REAL_LEAN` and
`LEAN_VERIFY_REAL_LAKE` to existing Lean 4.31.0 executables, then run the same
discovery command with `-p test_v2_lean_real.py`. The fixture pins
`leanprover/lean4:v4.31.0` and checks the actual reported version. These controls
exercise compilation success/failure, target mismatch and missing targets,
universe and instance hypotheses, transitive axioms through imported definitions,
semantic review reuse/invalidation, saved-evidence tampering and staleness,
expected-only external definitions and axioms, stale quoted local imports,
new module shadows with unchanged old artifacts, AND/OR routes,
LSP versions/goals/hover/symbols and actual CLI fallback.

Set `LEAN_VERIFY_TEST_TMPDIR` to an external temporary directory,
`LEAN_VERIFY_TEST_REPORT` to an external JSON report path, and
`LEAN_VERIFY_KEEP_TEST_ARTIFACTS=1` to preserve compiler logs and fixtures.
Check for matching active jobs before restarting interrupted tests. These small
controls do not replace a full Mathlib build or establish mathematical novelty.
