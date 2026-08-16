# Rethlas-distilled methods

This file distills the method essence of
[Rethlas](https://github.com/frenzymath/Rethlas) into the rigorous research
workflow. It is method-level borrowing; text is self-authored. The original
system uses two Codex agents (generation + verification) with persistent
structured memory. We keep the ideas that reduce blind rework and increase the
reliability of partial progress.

## 1. Persistent structured memory

Every intermediate artifact is persisted in append-only, queryable channels
instead of living only in the conversation:

- immediate conclusions;
- toy examples;
- counterexamples;
- big decisions;
- subgoals / decomposition plans;
- proof steps;
- failed paths;
- verification reports;
- branch states;
- events.

In this project, the file-level counterparts are `research_ledger.md`,
`approach_registry.md`, `counterexample_log.md`, `obligation_graph.md`, and
`whiteboard.md`. Treat them as append-only and queryable. Never let a material
conclusion, example, counterexample, or failure exist only in a chat reply.

## 2. Failures are first-class and drive the next plan

- Every failed route is recorded with a concrete failure mechanism and
  evidence.
- When a batch of decomposition plans fails, synthesize the **common** stuck
  points across plans and store them as a `key_failures_summary`.
- Use that summary to propose the next generation of plans. A new plan must
  state which earlier failures/counterexamples it avoids.
- Do not re-run a `[FAILED]` route without a materially new mechanism.

## 3. Decomposition-plan portfolio with screening and recursion

- Propose multiple **materially different** decomposition plans, not one.
- Screen each plan by attempting all its subgoals directly.
- If a plan does not fully go through, identify the key stuck points, not just
  "failed".
- If all plans fail, spawn one sub-agent per plan in parallel, sharing the
  known stuck points; allow recursion.
- After the recursive round, synthesize failures and start the next planning
  generation.

## 4. Counterexample-driven stress testing

- For any fragile claim or blocked subgoal, immediately try to construct a
  counterexample before treating the claim as merely hard.
- Store every useful counterexample (and even informative non-counterexamples)
  in a reusable library with the assumptions it satisfies and the conclusion it
  violates.
- Reuse stored counterexamples against future claims.

## 5. Search is support, not a substitute

- Use external search early for background, terminology, standard lemmas, and
  related results.
- When extensive search stops producing useful information, switch to deep
  independent reasoning with the non-search skills.
- A partial external result is diagnostic: analyze the extra hypotheses, why
  the method fails without them, and what this reveals about the true
  obstruction. Do not blindly force the current problem into the extra
  hypotheses and apply the result.

## 6. External references are not black boxes

- Every cited external theorem must be checked against its source.
- Expand the source paper's definitions and terminology; verify that the words
  in the current proof mean the same thing.
- Compare exact formulas, notation, and quantifiers; do not collapse
  similar-looking definitions.
- Check the downstream transition from the cited theorem to the current
  conclusion; a hand-wavy specialization is a gap.
- Record the complete statement, paper id, theorem id, and arXiv id when
  available.

## 7. Strict verifier acceptance and repair hints

- Full proof acceptance requires **zero critical errors and zero gaps**.
- Any error or gap makes the proof fail, with non-empty repair hints.
- Verification is performed by an independent role/service, not by the proof
  author.
- Partial progress is preserved, but the completion label is withheld until the
  strict acceptance condition is met.

## 8. Paper-like blueprint output

- Write proofs as paper-style markdown: supporting definitions, lemmas, and
  propositions appear before the statements that rely on them; the main theorem
  appears last.
- The final theorem statement must be the original complete statement from the
  problem input, not a paraphrase.
- Preserve long blueprints for difficult problems; partial progress is allowed
  as long as it is clearly labeled.
