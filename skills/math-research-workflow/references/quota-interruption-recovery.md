# Quota interruption and exact resume

Read this reference when a run approaches a five-hour or weekly quota boundary,
when the service interrupts a model call, or when a scored experiment must
continue across sessions. The protocol preserves mathematical and experimental
state without replaying the transcript.

## Artifact contract

For checkpoint segment `NN`, keep three immutable files in the run directory:

- `interruption_state-NN.json`, created from
  `assets/interruption-state.template.json`;
- `interruption_checkpoint-NN.json`, produced by the deterministic sealer;
- `resume_receipt-NN.json`, produced only after the checkpoint verifies.

Names are canonical and single-use. Segment `00` has `predecessor=null`.
Every later state binds the immediately previous checkpoint and its canonical
receipt by path/hash; sequence numbers must be contiguous. The validator then
rechecks the full predecessor chain before sealing the new state.

The semantic state binds the task contract, current whiteboard, latest audit,
and closure gate,
completed/open obligations, in-flight workers, do-not-repeat actions, exact
first action, minimal read set, bounded resume budget, and stop condition. In a
benchmark it also binds the arm, task, workspace, prompt, harness, source
snapshot, hidden-gold state, segment number, and cumulative metrics.
For a non-experimental run, replace the complete `experiment_integrity` object
with `{"enabled": false}`. The sealer rejects every unfilled template token.

## Safe interruption boundary

At every expensive model-call boundary, first merge the returned artifact and
update the whiteboard. When a quota warning appears or the next call may cross
the available window:

1. Freeze new dispatch. Reconcile model calls that have already returned; list
   every still-running or unknown worker in `inflight_work`.
2. Write a new numbered interruption state. Every completed claim needs a
   hash-bound evidence file; every open claim needs an exact gap, next action,
   and required inputs. Each live next action has a unique, stable `action_id`;
   the resume first action must match it. Put completed, replaced, failed, and
   duplicate action IDs in `do_not_repeat`.
3. Keep `resume.minimal_read_set` limited to the task contract, current
   whiteboard when present, and the inputs required by the first action. Do not
   add the transcript or all phase documents.
4. Seal the state with no research-model call:

   ```text
   python scripts/checkpoint_resume.py seal --project <project-root> \
     --state <run>/interruption_state-NN.json \
     --output <run>/interruption_checkpoint-NN.json
   ```

5. Hash-bind the state and checkpoint in the Markdown interruption handoff.
   After `SEALED`, the segment is closed: perform no further research-model
   work in it. Deterministic copy, hash, metric, and repository operations may
   finish the boundary.

The sealer is idempotent. A second seal succeeds only when it would produce the
same bytes. A changed state receives a new segment number rather than
overwriting a sealed checkpoint. This protocol needs no reserved model quota;
the boundary work is local and deterministic.

If the service cuts off before a new seal, resume from the latest earlier
`READY` checkpoint. Preserve any later raw output as unscored, unmerged
evidence until it is reconciled; never infer completion from an interrupted
call.

## Resume gate

Before the first model call in a resumed segment, run:

```text
python scripts/checkpoint_resume.py verify --project <project-root> \
  --checkpoint <run>/interruption_checkpoint-NN.json
```

`READY` means every bound file and the checkpoint envelope still match.
`STALE` is a hard stop: reconcile the changed files deterministically, write a
new state/checkpoint pair, and verify that pair. Do not reload context or start
a replacement route while the gate is stale.

Then create the resume receipt:

```text
python scripts/checkpoint_resume.py resume --project <project-root> \
  --checkpoint <run>/interruption_checkpoint-NN.json \
  --receipt <run>/resume_receipt-NN.json
```

Omitting `--resumed-at` uses a canonical second-precision UTC timestamp. For an
initial state or an externally recorded boundary, obtain the same format with
`checkpoint_resume.py timestamp`. Explicit ISO-8601 input remains supported,
including PowerShell timestamps with seven fractional-second digits.

Before editing the checkpoint-bound whiteboard or closure gate, create the next
segment draft:

```text
python scripts/checkpoint_resume.py advance --project <project-root> \
  --checkpoint <run>/interruption_checkpoint-NN.json \
  --receipt <run>/resume_receipt-NN.json \
  --output <run>/interruption_state-(NN+1).json
```

`advance` verifies the predecessor pair, copies mutable bindings to canonical
numbered paths such as `whiteboard-01.md` and `closure_gate-01.md`, rewrites
their exact bindings in the next state, and leaves the sealed predecessor
bytes untouched. It accepts either project-relative paths or unambiguous
cwd-relative paths already prefixed by the project directory. The generated
state has `advance_draft=true`; execute the receipt's exact first action, update
the numbered artifacts and semantic delta, then remove the draft flag before
sealing. The sealer rejects unfinished advance drafts and differing existing
versioned files.

At a pipeline boundary, `validate_pipeline.py` verifies the latest sealed
checkpoint and validates the whiteboard and closure gate selected by that
checkpoint's state. Earlier unnumbered or numbered records remain immutable
lineage artifacts and are not reinterpreted as the current run state. A stale
latest checkpoint is a hard failure; the validator never falls back to an
older record. Before sealing an advance draft, bring the new numbered records
up to the current whiteboard and closure-gate schemas.

The successor reads only the receipt's `minimal_read_set` and executes exactly
its `first_action`. Unresolved in-flight work forces
`RECONCILE_INFLIGHT`; no new worker can be dispatched first. A completed or
do-not-repeat action makes sealing fail. Transcript, conversation, planner
history, session log, and raw-response files are forbidden in the minimal read
set; renaming such a file does not help because every entry must also belong to
the action-scoped semantic bindings. The set is capped at twelve artifacts.

On the next checkpoint, every worker that was unresolved in the predecessor
must either remain in `inflight_work` with the same worker/session IDs or appear
once in `inflight_reconciliation` with those same IDs, a hash-bound evidence
artifact, and outcome `INGESTED`, `INTERRUPTED`, or `NO_RETURN`.

The receipt name is derived from the checkpoint sequence, so one checkpoint
cannot create two successor receipts. Its resume time cannot precede the seal.
A receipt is built only from the in-memory state snapshot that passed `verify`;
later file replacement cannot inject a new action or read set into that receipt.
A later checkpoint must bind that receipt, retain all completed and
do-not-repeat IDs, and preserve run, packet, source commit, and task contract.
When a newly isolated exact gap replaces an earlier open obligation, attach a
typed lineage record to the new open item:

```json
"lineage": {
  "relation": "REFINES",
  "predecessor_id": "OLD-OBLIGATION-ID",
  "evidence": {"path": "...", "sha256": "..."}
}
```

`REFINES` records a strictly sharper residual gap; `SUPERSEDES` records a
corrected replacement. The evidence must be new to the full checkpoint
lineage. The predecessor action is retired automatically and propagated in
resume receipts, so the old ID need not remain open and no duplicate
`do_not_repeat` repair is required.
Changing a result status requires new hash-bound evidence and a new audit plus
an explicit timed `status_transition`. Evidence and audit must be new to the
complete predecessor lineage, not merely absent from the immediately previous
segment. Freshness is content-hash based, so renaming old bytes does not make
them new; proof evidence and audit must also have distinct paths and hashes. A
completion status cannot retain open obligations.

## Experiment integrity

For a scored arm, keep `experiment_integrity.enabled=true` and preserve these
invariants across every segment:

- the arm, task, workspace, prompt, harness, source snapshot, and hidden-gold
  state stay fixed;
- counters are cumulative from the original start; resume never resets wall,
  response, tool, token, or cost totals. Every numeric counter is finite and
  non-negative; cost is explicitly `MEASURED` or `NOT_AVAILABLE`;
- checkpoint/verification overhead is recorded separately as unscored local
  boundary work unless the preregistration explicitly chose another policy;
- completed obligations, completed arms, audits, failed routes, and
  infrastructure-invalid attempts are not rerun merely because quota reset;
- use the same run/workspace/session when the system supports it. A replacement
  run requires the preregistered infrastructure-invalid rule and a fresh
  workspace; never mix its metrics or artifacts silently with the scored run;
- hidden gold remains sealed until the preregistered reveal point.

An interruption cannot upgrade a mathematical status. A result changes only
when new proof artifacts change and receive the audit required by the normal
pipeline. No fresh audit is purchased solely because a segment boundary
occurred.

## Completion criterion

Recovery is complete only when `verify` returns `READY`, the immutable resume
receipt exists, unresolved workers have been reconciled, cumulative metrics
dominate the previous segment, predecessor lineage is contiguous, and the first
action is neither completed nor on the do-not-repeat list.
