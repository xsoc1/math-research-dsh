> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 7 — Synthesis

The synthesizer may combine only audited modules.

For every transition between modules, check:

- domains and notation agree;
- all constants have the permitted dependencies;
- reductions preserve the required hypotheses;
- choices can be made simultaneously, not merely one at a time;
- local constructions glue globally;
- limits, sums, derivatives, expectations, or integrals may be interchanged;
- the final object satisfies the original, not a relaxed, definition.

Write the candidate proof with obligation IDs in comments or margins until the audit is complete. Do not hide gaps by converting the draft to polished LaTeX early.

## Phase 8 — Adversarial proof audit

Use an independent verifier, a different model or prompt when possible, and formal/computational checks where appropriate.

The verifier must return one of:

- `PASS`
- `REPAIRABLE_GAP`
- `FATAL_GAP`
- `WRONG_PROBLEM`
- `CIRCULAR_OR_EQUIVALENT_REDUCTION`
- `UNVERIFIED_CITATION`
- `COMPUTATIONAL_ONLY`
- `UNCERTAIN`

Audit categories:

### Semantic fidelity
- Exact objects, hypotheses, quantifiers, constants, and conclusion.
- No accidental strengthening or weakening of definitions.
- All disconnected, empty, zero, boundary, singular, and low-dimensional cases.

### Logical structure
- No circular dependence.
- No use of a statement equivalent in strength to the target without a new proof.
- Every induction measure is well-founded and decreases.
- Every case split is exhaustive and disjoint where required.
- Every existential choice is compatible with later choices.

### Analysis and probability
- Convergence modes are not interchanged without proof.
- Compactness and subsequence arguments yield the claimed full convergence.
- Uniformity in parameters is justified.
- Null sets, measurability, integrability, and conditioning are handled.

### Algebra, combinatorics, and geometry
- Signs, multiplicities, orientation, parallel objects, loops, repeated elements, and quotient identifications.
- Rank, dimension, characteristic, torsion, and genericity assumptions.
- Local conditions genuinely imply global compatibility.

### Computation
- Exact definition matches the verifier.
- No overflow, floating-point ambiguity, sampling gap, hidden timeout, or test leakage.
- Generalization is proved rather than inferred from a finite test suite.

### References
- The cited source exists.
- It states the needed result.
- Every hypothesis is met.
- The result was not already known under another name when novelty is claimed.

For each gap, identify the smallest failing claim and provide a counterexample or explicit missing proof obligation whenever possible.

### First-time verifier standard and automatic failure patterns

The verifier must treat the submission as a first-time proof: no memory of prior rounds, and the standard for `PASS` is that the verifier would stake its professional reputation on every step. The following patterns always produce `FAIL`, regardless of the rest of the proof:

- circular reasoning (conclusion or an equivalent used as a premise);
- wrong direction (proving A -> B when the lemma requires B -> A);
- missing cases in a claimed exhaustive analysis;
- incorrect theorem application outside its hypotheses;
- scope error (a weaker statement proved than claimed);
- added or strengthened hypotheses not present in the statement and not derived;
- dependency misuse (using a dependency without its hypotheses, or beyond its conclusion);
- unsupported target-defect claim (replacing the proof by the claim that the statement omitted a construction, map, or invariant, without a rigorous counterexample, contradiction, or impossible-precondition audit);
- unresolved load-bearing obligation (the main implication rests on an asserted, vaguely cited, or deferred construction, estimate, case-exhaustion, or assembly step);
- unwarranted source theorem (a named theorem or folklore result carries the proof but is not stated in the exact form used, lacks an independent source or derivation route, has unchecked preconditions, or is equivalent to the target);
- guessed definition (proving or refuting a statement under a chosen interpretation of specialized notation that is not accepted from the statement, dependencies, or research context);
- incomplete result presented as conclusion (the decisive claim is that a route, source, or construction is unavailable, without proving the statement or giving a verified counterexample);
- premature target-defect claim (treating a repairable typo, harmless symbol collision, conventional shorthand, or boundary convention as a disproof without auditing accepted readings);
- ignored global obstruction or compatibility constraint (local arguments never check a load-bearing global invariant, conservation law, boundary condition, compact-support condition, gluing compatibility, exactness, integrality/parity, regularity, or a known no-go theorem).

Every non-`PASS` finding must localize the **first** erroneous step (step index or smallest failing claim) and classify the error layer (statement / proof / dependency / boundary-convention), instead of giving vague comments. Record it in the structured verification output as `first_error` when applicable.

### Structured verification output

Record the audit in a machine-readable shape so downstream revision and ingestion can act on it:

```json
{
  "verdict": "PASS | REPAIRABLE_GAP | FATAL_GAP | WRONG_PROBLEM | CIRCULAR_OR_EQUIVALENT_REDUCTION | UNVERIFIED_CITATION | COMPUTATIONAL_ONLY | UNCERTAIN",
  "critical_errors": [{"location": "...", "issue": "..."}],
  "gaps": [{"location": "...", "issue": "..."}],
  "repair_hints": "..."
}
```

Strict rule: `PASS` only when `critical_errors` and `gaps` are both empty. Every finding carries a location and, whenever possible, the smallest failing claim (or a counterexample / explicit missing obligation). Any non-`PASS` verdict must include non-empty `repair_hints`. Aggregate without dropping issues; the revision phase consumes the exact gap list.

For canonical promotion, structure the audit as four mandatory audits, each bound to the exact content-hashed proof package: **definition audit** (objects, maps, quotients, multiplicities, orientation, notation, local/global distinctions, category membership), **logic audit** (quantifier order, implication direction, necessity versus sufficiency, induction decrease, termination, existence choices, circularity, local-to-global transitions), **boundary audit** (empty, zero, disconnected, low-dimensional, parity, equality, singular, noncompact, noncomplete, non-smooth, critical-parameter, and degenerate cases), and **adversarial audit** (attack the weakest step, enumerate smallest objects, search extreme parameters, verify every obvious compatibility condition, test whether the central missing lemma restates the target).
