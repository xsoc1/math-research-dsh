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
  --receipt <run>/resume_receipt-NN.json \
  --resumed-at <ISO-8601-time-with-timezone>
```

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
