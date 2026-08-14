# Accepted Knowledge Base (Blueprint v2.2 mathematics profile)

This directory is the canonical accepted-knowledge subsystem of a
`manage-math-research-program` project. It reuses the Blueprint v2.2
mathematics machinery so that reusable mathematical knowledge enters the
program only through a hash-bound, independently reviewed, receiver-verified
transaction.

## What lives here

- `blueprint.json` — canonical graph of claims, first-class inferences,
  research goals, obligations, and attempts, plus their accepted statuses.
- `evidence_inventory.csv` — canonical evidence index bound to graph nodes.
- `blueprint_update_requests.jsonl` — append-only event log for the pipeline.
- `submissions/` — immutable proposals, validations, reviews, receipts.
- `backups/` — optional verified canonical backups.
- `artifacts/` — content-hashed proof and refutation packages (register paths
  in proposals and inventory rows; never edit them after binding).
- `tools/` — deterministic validator, query gateway, receiver, viewer server.
- `viewer/` — offline read-only graph explorer.

## Two meanings of acceptance

Canonical presence certifies that a record and its status passed the update
process. It does not mean every stored proposition is true. For proof reuse,
only the deterministic trusted closure is authoritative:

- problem hypotheses, source-verified imported theorems, and accepted verified
  counterexamples may seed a context;
- only `mathematical_inference` nodes with `proof_status: proved` propagate
  their conclusions;
- open, candidate, blocked, invalid, refuted, contested, and superseded
  records never propagate truth.

## Invariants

- `blueprint.json` and `evidence_inventory.csv` are canonical and read-only.
  They change only through `tools/receive_blueprint.py` after an independently
  approved review. Never edit them by hand.
- A submission becomes accepted only when its `receipt.json` says `merged`.
  A merged partial lemma means the transaction succeeded, not that the goal is
  solved: keep `research_status` (e.g. `partial_progress`) separate.
- Proposals are immutable. Fix a rejected proposal with a new submission whose
  `supersedes` points to the old one.
- A proved inference must bind a content-hashed proof package with
  `unresolved_obligations: []`; a refutation binds a refutation package; a
  verified counterexample binds a certificate.
- Every task packet and research sub-agent is bound to a snapshot of this
  store (`blueprint_query.py snapshot`); on `SNAPSHOT_MISMATCH`, stop and
  re-fetch.

## Deterministic commands (run from this directory)

```powershell
python tools/blueprint_query.py snapshot
python tools/blueprint_query.py math-closure --context CTX-DEFAULT
python tools/blueprint_query.py math-frontier --goal <GOAL-OR-CLAIM-ID> --context CTX-DEFAULT
python tools/blueprint_query.py math-goals --context CTX-DEFAULT
python tools/blueprint_query.py find --text <QUERY> --math-view trusted
python tools/blueprint_query.py get --id <NODE_ID>
python tools/validate_blueprint.py
python tools/receive_blueprint.py --submission submissions/<SUB-ID> --validate-only --actor-agent-id <AGENT>
python tools/receive_blueprint.py --submission submissions/<SUB-ID> --integrator-agent-id <AGENT>
python tools/serve_blueprint_viewer.py
```

Run the receiver from the project root as
`python knowledge/tools/receive_blueprint.py --blueprint-root knowledge --submission submissions/<SUB-ID> ...`.

## Mathematics node classes

- `problem_hypothesis` — context-local given premise.
- `definition_contract` — definition or convention; `truth_bearing: false`.
- `external_mathematical_result` — source-verified literature theorem with
  citation, locator, hypotheses, notation map, and verification.
- `mathematical_claim` — lemma, theorem, conjecture, equivalence, negation,
  or no-go claim with a `truth_status`.
- `mathematical_inference` — first-class entailment with `proof_status`;
  only `proved` propagates.
- `verified_counterexample` — certificate-bound object refuting named claims.
- `research_goal` — prove, refute, or prove-or-refute contract with
  completion criteria and non-completion conditions.
- `proof_obligation` — exact unresolved gap with discharge criteria.
- `research_attempt` — candidate route or audited failure with first failing
  step, precise gap, and restart conditions.

Generic v2.1 roles (basic assumptions, numerical methods and results,
experiment designs, theory from numerics) remain valid and extend the graph.

See `references/accepted-knowledge-pipeline.md` in the skill package for the
full submission, review, and integration contract.