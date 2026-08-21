# Cost-tiered escalation ladder (light first)

This reference adds a cost-aware layer to the research loop. It tells the
solver to begin every problem with lightweight, minimal-change actions and to
escalate to heavier or more complex machinery only when the cheap actions have
produced a recorded reason to do so. It complements, and does not replace, the
marginal-information-gain rule, the route state machine, the verification
tiers, and the resource-boundary reporting rules.

## 1. Why light first

- Cheap probes are fast to run and cheap to discard. They often reveal a
  counterexample, a hidden assumption, or a known theorem that removes the need
  for a heavy attack.
- A minimal change isolates cause and effect. A small specialization or a
  single weakened hypothesis is easier to audit and easier to formalize than a
  brand-new theory.
- Heavy methods are expensive and can hide errors behind complex machinery.
  They should be bought with evidence, not with optimism.
- Every escalation becomes a first-class decision in the ledger: what cheap
  actions were tried, what they showed, and why a heavier action is now
  justified.

## 2. Cost tiers

| Tier | Name | Typical cost | Typical actions |
|---|---|---|---|
| 0 | Inspect and probe | minutes | Read existing artifacts, research map, tool library, LEMMA_INDEX, accepted-knowledge index; run existing scripts; small numerical spot checks; n=0/1/2/3 cases; diagonal/banded/symmetric/degenerate cases; confirm a baseline. |
| 1 | Minimal change | minutes to hours | Fix one parameter; restrict to a subclass; weaken or remove one hypothesis; patch one constant or coefficient in an existing proof; instantiate an existing theorem or lemma directly; check whether a known result already covers the current claim. |
| 2 | Systematic medium | hours | Small exhaustive case search; targeted literature scan; prove one rigorous partial lemma; Lean Tier 1 check of one load-bearing lemma; two or three cheap independent subagents. |
| 3 | Heavy and parallel | hours to days | Full multi-route portfolio; large numerical or random search; new theoretical machinery; full Lean Tier 2 formalization; complete independent adversarial audit; broad parallel workflow fan-out. |

Tier numbers are guidance, not a law. A task that needs a known heavy theorem
may legitimately start at Tier 2 or 3 if the cheap probes already show the
obstruction. What matters is that the skip is explicit and recorded.

## 3. Action selection rule

Choose actions by expected information gain per unit cost:

```text
score = expected_information_gain / estimated_cost
```

- Prefer the lowest tier that can still distinguish between the live
  hypotheses.
- Do not skip Tier 0/1 to reach Tier 3 unless the Tier 0/1 attempts produced a
  recorded jump-level obstruction (for example a small case that proves a new
  structural theorem is necessary).
- Parallel fan-out is a Tier 3 action. Do not open many parallel workers until
  a few single-line cheap probes have been tried and recorded.
- Every action must produce a concrete artifact: a formula, a small case
  result, a counterexample, an exact gap, or a reused lemma identifier. A
  status report is not an artifact.

## 4. Upgrade triggers

Escalate one tier only when at least one of these is satisfied:

1. The current tier has produced two consecutive zero-gain rounds (the
   existing zero-gain rule, now bound to a tier).
2. A cheap test produced a counterexample or obstruction whose character
   indicates that a heavier mechanism is required.
3. A claim has become load-bearing and the informal proof keeps repeating the
   same gap; machine verification (Lean Tier 1/2) can close that gap faster.
4. The user explicitly requests deeper verification or authorizes a larger
   budget.

Record the trigger in the escalation ladder and in the route card before
starting the heavier action.

## 5. De-escalation and retry rules

- When a heavy route fails, record the precise failure mechanism first.
- Then return to Tier 0/1 and ask whether a smaller variant avoids that
  failure: a narrower subclass, a weaker conclusion, a repaired local step, or
  a reused lemma that was missed.
- Reopening a `REFUTED` or `BLOCKED` route without a new mechanism is a loop,
  not progress, and is rejected by the existing loop-control rule.
- A successful heavy result does not invalidate the cheap probes that led to
  it. Keep both in the ledger; mark superseded results when a later result
  covers an older one.

## 6. Minimal-change checklist

Before starting a full proof or a large search, try, in order:

1. **Specialize.** Fix one parameter or restrict to a diagonal/banded/symmetric/
   low-dimensional subclass.
2. **Weaken.** Remove or weaken one hypothesis and see whether the conclusion
   survives or a counterexample appears.
3. **Instantiate.** Check LEMMA_INDEX, the tool library, and the accepted
   knowledge base for an existing theorem or lemma that covers the claim.
4. **Patch locally.** Adjust one constant, coefficient, or intermediate
   assertion in an existing proof.
5. **Small cases.** n=0/1/2/3, finite fields, degenerate boundaries, known
   extremizers.
6. **Numerical probe.** Run existing code on a small parameter range; do not
   mistake this for proof.
7. **Reproduce.** Re-run an existing artifact to confirm that the baseline is
   real and not a bug.

## 7. Run-level record

Maintain `escalation_ladder.md` under the run root. It is a compact,
append-only log of cost-tier decisions. Suggested format:

```markdown
# Escalation ladder

- **Run ID:** `R-...`
- **Task packet ID:** `Q-...`
- **Current cost tier:** `0 | 1 | 2 | 3`

## Attempts

- `YYYY-MM-DDTHH:MM:SSZ` tier 0: <action>;
  result: <artifact or exact gap>; sha256 <hash>.
- `YYYY-MM-DDTHH:MM:SSZ` tier 1: <action>;
  result: <artifact or exact gap>; sha256 <hash>.

## Escalations

- `YYYY-MM-DDTHH:MM:SSZ` tier 1 -> tier 2:
  trigger: <zero-gain | counterexample | load-bearing gap | user request>;
  evidence: <artifact path or one-line summary>.
- `YYYY-MM-DDTHH:MM:SSZ` tier 2 -> tier 1:
  reason: <failure mechanism>; next smaller variant: <one line>.

## Avoid list (updated)

- <failed route or cheap action that must not be repeated without new input>
```

The whiteboard should carry the current tier and the last escalation reason so
the planner sees them every step without re-reading the full ladder.

## 8. Integration points

- Phase 4 route cards: add `cost_tier`, `minimal_first_step`, and
  `escalation_criteria` fields.
- Phase 5 research loop: step 0 runs the cheapest admissible probe before the
  full artifact is produced.
- Stage B whiteboard: keep `current_cost_tier` and `last_escalation_reason` in
  the live memory.
- Math-research-workflow: Planner action selection ranks candidates by
  information gain per cost; parallel fan-out is a Tier 3 action.
- Manage-math-research-program task packets: optional `escalation_budget` and
  `max_cost_tier` fields let the manager set an explicit ceiling.
- lean-verify: existing verification tiers remain the reference for how heavy
  a machine check should be.
