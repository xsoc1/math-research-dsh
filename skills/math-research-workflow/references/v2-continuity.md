# Continue from durable research state

Use the existing progress file, in any useful format. The helper selects
`state/RESUME.md`, `RESUME.md`, `whiteboard.md`, then `research_map.md`, or accepts
`--progress`. It reads current state and never restores an older snapshot over it.
Useful contents are a goal, findings with pointers, remaining uncertainty and
next ideas. There is no required heading, budget field, or sealed checkpoint.

`<workflow>` below is the installed plugin directory, two parents above this
skill directory. Check commands with `--help` in that installed copy.

```text
python <workflow>/scripts/research_state.py inspect --project <project>
python <workflow>/scripts/research_state.py checkpoint --project <project> --input proof.md
python <workflow>/scripts/research_state.py save --project <project> --text-file merged-notes.md --expected-sha256 <current-hash>
```

`save` is optional: ordinary direct edits remain valid. Use `missing` for a new
file. The helper hashes and archives a single read, serializes cooperating saves,
and checks the expected bytes again before replacement. A stale-write conflict
means merge the actual notes, not ask for another research approval. An editor
that ignores this lock can still write in the final comparison/replacement
window: this is not universal filesystem compare-and-swap. Avoid simultaneously
editing that same page while saving through the helper.

Previous contents and selected input hashes are kept under `.research-state/`.
File locks are released by the operating system when a writer dies. Atomic
replacement prevents partial JSON from becoming current; short persistence
conflicts, including Windows reader sharing, are retried without redispatching
the command. Preserve this directory with the project when carrying it to
another machine, along with the progress page and referenced artifacts. This
has been tested for process interruption, not power loss or storage failure.

## Local work that outlives a client

```text
python <workflow>/scripts/research_state.py start --project <project> --job-id check-lemma-v1 --cwd lean-proof --input lean-proof/SL/Lemma.lean --input lean-proof/lean-toolchain --input lean-proof/lake-manifest.json -- lake env lean SL/Lemma.lean
python <workflow>/scripts/research_state.py status --project <project> --job-id check-lemma-v1
```

Choose an ID for the logical action. Retrying `start` with the same ID and
request returns the existing job and performs no second dispatch. Different
inputs or commands with that ID are rejected. A deliberate new attempt uses a
new ID. Include the relevant inputs; the generic job helper cannot discover all
dependencies of arbitrary commands. For theorem verification, let the Lean
verifier bind its full source and environment as well.

A detached supervisor saves the command, actual child and supervisor identities,
complete stdout/stderr, exit status and timestamps. Process creation identity
prevents PID reuse from appearing to be the old job on Linux and Windows. On an
unsupported process platform, liveness stays unknown. A missing supervisor or
lost response is not success and never triggers automatic resubmission.

There is no default timeout. An explicit `--timeout` is a local process limit;
its deadline starts at child creation and a separate watcher enforces it while
metadata writes retry. On expiry the immediate child is killed and the record warns that descendants
may remain. Reconcile them before repeating work. Exit 0 says the command
finished successfully; it is not itself a mathematical verdict. Results from
older declared inputs or changed logs are marked as inapplicable. Build caches
and interactive Lean sessions can be recreated; their state is not the durable
record.

The worker checks declared inputs before launching the child and observes them
again at completion. A pre-launch change gives `INPUTS_CHANGED` with no child;
an observed change stays recorded even if files are later restored. A bookkeeping
failure after launch is `UNKNOWN`, with child identity and recovery logs when
available. `FAILED_TO_START` is reserved for a confirmed child-creation failure.

`recorded_inputs_match_current` describes the recorded hashes and observed
execution boundaries. Arbitrary commands can read mutable or undeclared inputs;
the helper cannot rule out a temporary change between observations. Consequently,
`result_applies_to_current_inputs` is `null`, not a certificate of applicability.
Use the specific verifier's immutable source/environment evidence before reusing
a mathematical or build result. External receipts carry the same limitation:
recording a provider response does not verify what inputs that provider used.

## External work

```text
python <workflow>/scripts/research_state.py register-external --project <project> --job-id remote-check-v1 --provider example --request-key <original-request-key> --input proof.lean
python <workflow>/scripts/research_state.py register-external --project <project> --job-id remote-check-v1 --provider example --request-key <original-request-key> --input proof.lean --external-id <returned-job-id>
python <workflow>/scripts/research_state.py record-result --project <project> --job-id remote-check-v1 --state SUCCEEDED --result-file retrieved-result.json
```

These commands record observations; they never call a cloud provider. Preserve
the original request identity before submission when possible. If the response
is lost, query that identity with the actual provider or inspect its dashboard.
An unknown outcome is not permission to submit again. Only the provider's real
idempotency contract could justify exactly-once claims. Result bytes are copied
to a content-addressed local record, separate from later edits to transport files.
No production Fuse or Prove2Me integration is implied by this generic interface.

## Data health and historical runs

`validate_pipeline.py --project <project> [--scope <directory>]` checks current
continuity data. It does not impose a research sequence or certify mathematics.
Add `--archives` to this command or to `research_state.py inspect` to check saved
checkpoint, history and observation identities without restoring anything. A
damaged record is reported locally while other current progress stays readable.
For old sealed contracts use the explicit
[1.x compatibility mode](v1-compatibility.md). Historical failed routes, budget
seals and proof identities keep their original meaning; they are not default
instructions for new work. No command queries quota or redeems credits.
