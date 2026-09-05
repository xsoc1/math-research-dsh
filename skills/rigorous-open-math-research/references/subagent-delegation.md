# Sub-agent delegation

Conventions for splitting a rigorous mathematics run into parallel, well-bounded sub-agents
(Coordinator + sub-agents) and merging their audited results. Read this when a run has several
independent routes, obligations, or verification targets and the runtime can spawn sub-agents.

## When to delegate

Delegate only subtasks that are all of:

- parallelizable: no circular dependency on another in-flight subtask;
- well-bounded: a single claim, route, obligation, or retrieval topic with a clear deliverable;
- minimally coupled: the sub-agent needs a small, hashable context slice, not the whole project.
- closure-relevant: the coordinator has recorded the direct attempt and cheapest falsification
  probe, and the return can change a named decision in `closure_gate.md`.

Do not delegate:

- the problem contract (owned by the coordinator, audited once);
- resource allocation and stopping decisions;
- global synthesis (Phase 7) and final completion labeling;
- any step whose result decides the polarity of the whole problem without a second pass.

## Standard split targets

| Target | Input slice | Deliverable | Status labels |
|---|---|---|---|
| Route explorer (Phase 4) | route card + contract slice + falsification tests | lemma/construction/counterexample + exact gap | PROVED, PARTIAL, BLOCKED, REFUTED |
| Obligation prover (Phase 3/5) | obligation ID + statement + dependent proved facts | proof draft or precise obstruction | PROVED, PARTIAL, BLOCKED |
| Counterexample hunter | exact claim to attack + search budget | minimal counterexample or tested domain | FALSIFIED, NONE_FOUND |
| Literature auditor (Phase 2/11) | query set + citation list | verified statements + source links + novelty notes | DONE, UNVERIFIED |
| Proof verifier (Phase 8) | candidate proof + contract | verdict + exact gap list | PASS, REPAIRABLE_GAP, FATAL_GAP |

## Subtask packet

Every spawned sub-agent receives a packet with these fields (template in
`assets/subtask-packet.template.md`):

- `subtask_id`: stable ID bound to the obligation/route (e.g. `SUB-O2-routeC`).
- `claim`: the exact statement attacked, verbatim from the contract or route card.
- `direct_attempt` and `falsification_probe`: the coordinator-owned preflight artifacts and
  outcomes, or an explicit reason why a direct attempt is inadmissible.
- `decision_to_change`: the named closure-gate decision plus explicit success, failure, and
  budget-stop conditions.
- `inputs`: exact file paths plus sha256 hashes; never the whole repository.
- `context_slice`: only the definitions, lemmas, and sources the sub-agent may rely on.
- `deliverable`: the artifact to return and where to write it (own paths only).
- `status_labels`: allowed output labels (see table above).
- `constraints`: no global completion claims; no mutation of shared artifacts; no repeating a
  recorded failure without new evidence; no fabrication of run data.
- `budget`: effort cap and deadline; what to return if the budget is exhausted.
- `decision_delta`: the durable state change required in the return; exposition alone is not a
  delta.

## Scheduling

1. Run the coordinator pass first: contract audit, shortest obligation chain, closure-first
   direct attempt, and cheapest falsification probe.
2. Launch sub-agents only after a recorded spawn trigger. Use the smallest batch that can change
   the gate decision; launch parallel work only for currently independent targets. Keep explorers
   uncorrelated (do not broadcast the fashionable route).
3. Cap concurrency and total budget; do not exceed the configured limits.
4. Collect results as they arrive; do not wait on correlated duplicates.
5. Re-delegate only after a sub-agent returns a precise mechanism-level failure and a materially
   new idea exists; otherwise record and move on.
6. Keep adversarial checking as a responsibility throughout. Dispatch a fresh verifier for a
   concrete candidate proposed as a load-bearing dependency or reusable result, and for the
   final frozen candidate. Do not keep an idle verifier running or repeatedly review unchanged
   artifacts. Empty or duplicate returns use the coordinator's deterministic rejection gate.
7. Require a `decision_delta` from every worker. A return that only restates context or reproduces
   an existing partial bound does not justify another round.

## Isolation and decorrelation

- Each sub-agent writes only to its own artifact paths; the coordinator owns shared files.
- Different sub-agents should use different mechanisms or adversarial perspectives.
- A sub-agent may read shared inputs but must not silently overwrite them.
- Results that depend on unshared context must say so; the coordinator resolves against the
  audited contract.

## Merging

Merge only audited modules:

0. Verify every artifact by path and recomputed sha256 against the sub-agent's returned `artifact_sha256`; a mismatch means the artifact was not what the sub-agent reported.
1. Check the Phase 7 interface rules for every transition (domains, notation, constants,
   simultaneous choices, gluing, interchange of limits).
2. Resolve conflicts against the audited problem contract; a sub-agent cannot override it.
3. Record every outcome in the ledger and approach registry: `PROVED`, `PARTIAL`, `BLOCKED`,
   `REFUTED`, `FALSIFIED`, `NONE_FOUND`, `UNVERIFIED`.
4. A sub-agent's `PROVED` is a candidate, not a completion; the completion gate still applies.

## Failure handling

- `BLOCKED`/`REFUTED`/`FALSIFIED` outcomes with a precise mechanism are research results; record
  them with the mechanism and the tested domain.
- Do not silently retry; do not start a near-duplicate exploration until the previous failure
  is recorded.
- If a sub-agent returns noise, an empty artifact, or an unsupported claim, record it and
  redirect resources rather than merging it.

## Runtime examples

Codex multi-agent spawn (when the `spawn_agent` capability is available): pass the subtask
packet as the initial prompt, keep the sub-agent's context limited to its slice, wait for its
final status, then verify its artifacts by path and recomputed sha256 (sub-agents return raw JSON, no code fence, including `artifact_sha256`) before merging.

Sequential fallback: when spawn capability is unavailable, execute the same packets one at a
time in the same session, writing each artifact before switching roles, and perform the verifier
pass with a fresh context or a deliberately adversarial prompt.

## Relationship to the manager skill

Task packets originate in `$manage-math-research-program`; the concrete split into sub-agents
happens inside `$rigorous-open-math-research`. Returned sub-agent artifacts are bound by hash in
the run manifest so the manager can ingest them without re-reading the whole run.
