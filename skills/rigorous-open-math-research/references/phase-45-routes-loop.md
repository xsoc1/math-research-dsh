> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 4 — Create a genuinely diverse route portfolio

Generate route families by mathematical mechanism, not by paraphrasing the same idea.

Candidate families, selected only when relevant, include:

- direct construction or direct inequality;
- extremal or minimal-counterexample arguments;
- induction, decomposition, surgery, or local-to-global gluing;
- algebraic, representation-theoretic, number-theoretic, or generating-function encodings;
- geometric, topological, dynamical, or variational reformulations;
- probabilistic, entropy, Fourier, spectral, or analytic methods;
- duality, flow, matching, linear programming, semidefinite, or matroid formulations;
- compactness, limiting, stability, or regularity arguments;
- exhaustive small-case analysis and automated counterexample search;
- proof transfer from a simplified continuous, discrete, finite, or formal model;
- deliberate attempts to disprove the conjecture.

For each route, create a route card:

```markdown
Route ID and family:
Core mechanism:
Target obligation:
Why it could be strictly easier than the original problem:
Required known results:
First concrete deliverable:
Fast falsification tests:
Expected bottleneck:
Status:
Exact gap:
Next action:
```


Give every route a mechanism-distinct `route_key` and record a concrete `deliverable_contract`, fast `falsification_tests`, expected bottleneck, and provenance in the route card.
Early in the search, preserve independence. Do not broadcast the currently fashionable route to every explorer. Merge routes only after each has produced enough concrete mathematics to reveal its strengths and real gaps.

Do not use fixed agent counts as a principle. Allocate resources dynamically according to marginal information gain.

## Phase 5 — Execute the research loop

For each active route, repeat:

1. **Produce a concrete artifact.** A lemma, formula, construction, algorithm, counterexample, invariant, or precise reduction—not a status report.
2. **Stress-test immediately.** Check smallest cases, degenerate cases, symmetry-breaking examples, known extremizers, dimensional limits, and random/adversarial instances.
3. **Attempt a local proof.** State every hypothesis and the exact claim.
4. **Run an adversarial review.** Seek the first non-repairable gap rather than polishing exposition.
5. **Update the obligation graph and ledger.** Record what changed.
6. **Decide:** continue, repair, branch, merge, block, refute, or archive.

Use these route states:

- `UNEXPLORED`
- `ACTIVE`
- `PROMISING`
- `PARTIAL`
- `BLOCKED`
- `REFUTED`
- `MERGED`
- `PROVED`
- `FORMALIZED`

### Retrieval / deep-thinking scheduling

Avoid search dependency. Alternate explicit retrieval phases with retrieval-free deep-thinking phases: after a search round, run a round in which search tools are disabled and the route is advanced by independent reasoning, constructions, and stress tests. When retrieval stops yielding useful support, stop leaning on it and continue with the non-search skills; record stalled queries and the reason the results were not useful. Deep independent reasoning is a required mode, not a fallback.

### The theorem-strength gap test

Before calling a reduction progress, ask:

1. Is the missing lemma demonstrably narrower, more local, or structurally simpler than the original target?
2. Does the route provide a new mechanism for proving it?
3. Can it be verified independently on meaningful examples or known classes?
4. Would proving the missing lemma essentially settle the original conjecture with no additional insight?

If only the fourth is true, mark the route `BLOCKED`. Reopen it only when a materially new invariant, construction, or proof mechanism appears.
