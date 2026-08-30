# Math Research Workflow -- design notes

## 1. Roles and ownership

| Role | Owns | Produces |
| --- | --- | --- |
| Manager (stage A) | program context, task packets, tool library, accepted knowledge, git sync | `state/current.json`, task packets, project index |
| Solve-run lead / Planner (stage B) | whiteboard, plan, route portfolio, repository index | `whiteboard.md`, worker spawns, merge decisions |
| Worker agents (stage B) | one deliverable each: a route, lemma, counterexample, simplified variant, or formalization | route artifacts under `runs/<run_id>/<slug>` |
| Verifier / Audit agent (stage B) | independent re-derivation, adversarial review of finished Worker outputs | `audit_report.md`, F-xxx findings, structured feedback |
| Formalizer agent (stage C) | Lean declarations, obligation map | `lean-proof/SL/*.lean` |
| Verifier agent (stage C) | machine checks, manifests, verdicts | `run-manifest.json`, `verification.json` |

Independence rule: the audit agent and the verifier agent never reuse the
solver's / formalizer's reasoning as authority; they re-derive from the
source documents. Workers never observe other Workers' reasoning traces or the
Planner's chain of thought. Artifacts (not conversations) are the only
interface.

## 2. Task packet schema (stage A -> B)

```text
id:           <Q-YYYYMMDD-<tag>-<hash8>>
contract:     <exact normalized statement + completion criteria>
source_docs:  <paths to docs/SL_*.tex or papers/, with DOIs/URLs>
obligations:  <O1..On list with source sections>
verification: <criteria: strict proof required, numerical evidence excluded>
fork_sync:    <parent repo -> child fork direction, if any>
```

## 3. Handoff contract B -> C (formalization gate)

Complete verification accepts these labels:

- `已证` / `CANDIDATE_COMPLETE_PROOF` with all obligations closed;
- `STRICT` results from source documents.

Excluded: `数值证据`, `EVIDENCE`, `猜想`, `开放` (record them in STATUS.md
as not formalized). The gate is checked by the manager at the stage boundary,
not by the formalizer.

`RIGOROUS_PARTIAL_RESULT` does not enter full verification, but it does enter
Tier 0 scaffold registration. If Stage B and Stage C have different logical
project roots, `formalization_handoff.py` must seal an exact-copy receipt that
binds the source manifest/proof/scaffold to the destination scaffold and its
registration anchors. Stage C verifies `READY`, writes the single canonical
consumption record, and only then changes the copy. The consumption event keeps
mathematical and verification status unchanged; later destination evolution is
tracked by Stage C rather than by mutating the receipt.

## 4. Parallelism

- Stage B: solver opens route n+1 while audit agent reviews route n; bounded
  alternation (2 loops by default, expandable on user request).
- Stage C: verifier runs `lake env lean` on each file as it is written;
  full `verify_lean_project.py` run at the end.
- Serial points: contract freeze (A), result label freeze (B->C), verdict
  freeze (C). Nothing is committed to the accepted-knowledge base before the
  verdict.

## 5. Failure handling

- F-xxx finding in source document: fix in place, record the correction and
  the counterexample/justification in the audit report; the formal statement
  always uses the corrected hypothesis.
- Numerical-evidence substitution: if a deliverable promotes numerical checks
  to a proof without a strict label or an explicit downgrade statement, the
  gate fails it; the manager returns the packet with the exact missing labels
  or obligations. The status is never silently promoted.
- Machine verification failure: no verdict; iterate formalizer/verifier loop
  (bounded 5-15 rounds per file, then report the exact obstacle).
- Git conflict or fork divergence: stop, record state, do not overwrite
  uncommitted artifacts.

## 5.1 Interruption handoff and resume

Any stage that stops before completion writes an interruption handoff
(`runs/<run_id>/handoff-interrupted-<ts>.md`, template
`assets/interruption-handoff.template.md`) before returning control. A
quota/resource boundary first writes `interruption_state-NN.json` and seals
`interruption_checkpoint-NN.json` with `scripts/checkpoint_resume.py`. The
state binds completed/open obligations, in-flight workers, do-not-repeat
actions, exact first action, minimal read set, resume budget, and stop
condition. Scored experiments additionally bind the arm, prompt, harness,
source snapshot, hidden-gold state, workspace, segment, and cumulative
metrics.

Segment `00` is the trust root. Every later segment hash-binds the immediately
previous checkpoint and its unique canonical receipt. The gate enforces
contiguous lineage, non-decreasing finite metrics (including explicit cost),
fixed experiment identity, persistent completed/do-not-repeat sets, structured
action identity, and new evidence plus audit for any result-status change.

The handoff binds both files by path and hash. The successor runs deterministic
`verify` before any model call; `STALE` stops recovery, while `READY` permits an
immutable resume receipt. It reads only the receipt's minimal set and executes
its first action. Unresolved workers force reconciliation before dispatch, and
completed or audited-failed work is not replayed. `validate_pipeline.py`
hard-fails new quota handoffs without a ready checkpoint. Full mechanics and
experiment replacement rules live in
`references/quota-interruption-recovery.md`.

## 6. Efficiency checklist

- [ ] Environment preflight (scripts/doctor.py) passed before dispatch
- [ ] Tool library and STATUS.md consulted before new work
- [ ] Task packet hash-bound before delegation
- [ ] No duplicate artifact locations
- [ ] Latest quota checkpoint verifies `READY`; resume metrics are cumulative
- [ ] Git synced after every stage (parent first, fork second)
- [ ] AGENTS.md session log appended with the stage summary

## 7. OpenProver-style solve loop (distilled 2026-08-14)

Source: OpenProver (arXiv:2607.09217, CICM 2026, Kripner & Straka;
github.com/kripner/OpenProver). Distilled as protocol, not code: the workflow
orchestrator stays prompt/artifact-driven.

### 7.1 Planner role and whiteboard

The solve-run lead (Planner) maintains one compact `whiteboard.md` per run and
rewrites it after every planner step. Contents: current plan (wholesale
replacement), route history (newest first, each line with
`[FAILED|BLOCKED|PARTIAL|SUCCEEDED]` and failure mechanism), deferred ideas,
open obligations, and key-artifact index (slug + one-line summary + sha256).
The whiteboard is provided as input at every step; the interruption handoff is
a frozen snapshot of it plus recovery context.

### 7.2 Repository and verified-items-only rule

Repository items are addressed by slug (relative path under `runs/<run_id>/`).
The Planner observes only slugs and one-line summaries at each step. A Lean
item enters the repository only if it passed machine verification; otherwise
its errors and warnings are fed back to the responsible Worker. This gives
tighter feedback than a final-answer check and keeps the stored memory
machine-trusted.

### 7.3 Worker and Verifier independence

Workers are spawned with a single plaintext deliverable; they do not observe
other Workers' or the Planner's reasoning. The Verifier (audit agent) reviews
each finished output without the Worker's trace, returning
verdict + critical errors + gaps + repair hints. The Planner alone merges
routes, and merges only audited modules.

### 7.4 Lean real-time verification loop

Worker tools: `lean_verify` (verify a snippet, return exact errors),
`lean_search` (LeanExplore semantic search over Mathlib, arXiv:2506.11085,
record hits with source, never fabricate declaration names), and `lean_store`
(append verified snippets to `runs/<run_id>/lean_scratch/context.lean`,
prepended to later `lean_verify` calls). Mechanics delegate to `$lean-verify`.

### 7.5 Formalization feedback loop

Lean failures are classified (statement / proof / dependency /
boundary-convention) and repaired at the correct layer. Proof-layer flaws
route back to the Planner: fix the natural-language proof, re-audit affected
obligations, then re-formalize. Bounded loops (5-15 rounds per file), then an
exact obstacle report. No silent weakening of claims.

### 7.6 Interactive steering

Human-in-the-loop mode presents each plan/action set before execution,
allows redirecting Workers, interrupting unpromising routes, and accepting or
rejecting the next actions with feedback. Autonomous mode skips prompts.
