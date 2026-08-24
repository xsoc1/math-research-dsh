> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 12 — Stopping and reporting

### Completion gate

Claim a complete proof or disproof only when:

1. the theorem contract has passed fidelity audit;
2. every root-to-leaf obligation is closed;
3. all cited results and hypotheses are verified;
4. computational components have general certificates or proofs;
5. an independent audit returns `PASS` or only genuinely cosmetic issues;
6. the result label accurately reflects the available verification level.

### Fresh-context convergence check

Before terminal reporting, and during long runs or after strategy pivots, run a fresh-context convergence check: rebuild the current state from files only (ledger, obligation graph, approach registry, status files, artifact list) without conversational history, and answer whether the research is converging or diverging. File concise issues or memory items; this pass does not edit source or mark tasks complete.


Before promoting a proof or refutation canonically, freeze a content-hashed package (proof, refutation, or certificate) whose hash the inference node binds, and keep `transaction_status` separate from `research_status`: `transaction_status: merged` with `research_status: partial_progress` is correct when a partial lemma is accepted but the target is not yet in the trusted closure. Declare the goal solved only when its target is in the computed trusted closure for the intended context and the merged receipt is verified.

Before reporting, when the run workspace is a git repository: commit the final artifacts with a descriptive message, record the commit hash and working-tree state in the reproducibility manifest, and state any uncommitted leftovers explicitly.
### Research stop conditions

It is legitimate to stop a run when:

- the allotted resources are exhausted;
- all active routes are blocked or refuted;
- the remaining work requires unavailable expertise, data, software, or formal libraries;
- further sampling is producing only correlated duplicates;
- consecutive zero-gain rounds on every active branch (record the last marginal-gain witness per branch, per the Phase 5 rule);
- a decisive ambiguity in the problem cannot be resolved.

Stopping does not permit pretending success. Return the strongest rigorously supported result and the exact remaining gap.

### Token budget exhaustion = pause, not loss

When a token/resource budget is exhausted, do not drop the run. Follow the
pause-and-handoff discipline (see `references/openprover-absorption.md` in the
workflow skill and `assets/budget-state.template.json` in the manage skill):

1. Persist whiteboard, repository items, planner history, verified facts, and
   failed paths.
2. Write an interruption handoff with completed work progress, tools/methods
   tried, open obligations, and exact next actions.
3. Update `budget_state.json` (`status: paused_budget`) and `state/RESUME.md`.
4. Mark the run `PAUSED_BUDGET` / `RIGOROUS_PARTIAL_RESULT`; resumption reads
   the handoff + budget state and continues with an added budget.
5. If the target is almost complete, request an extension instead of stopping
   at the finish line.

## Result template

```markdown
# Result

## Exact theorem or result proved
## Proof or construction
## Verification performed
## Remaining gaps
## Failed and blocked routes
## Novelty status
## Human/model/tool contributions
## Reproducibility manifest
## Confidence by axis
- Semantic fidelity:
- Mathematical correctness:
- Completeness:
- Novelty:
- Reproducibility:
```

Do not present an unverified candidate as a theorem. Do not bury a fatal gap in a footnote.


When a canonical knowledge base exists, additionally report the trusted closure, proved conditional inferences, the exact current frontier, and blocked obligations with their strength relative to the target. Keep transaction status and research status separate in the report.
