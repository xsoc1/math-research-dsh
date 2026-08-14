# Mathematics Graph Integration (Blueprint v2.2 distilled)

This contract is distilled from the Blueprint v2.2 mathematics toolkit. Use it
when the project provides a canonical accepted-knowledge base: a
`manage-math-research-program` project root with `knowledge/`, or a Blueprint
v2.2 project with `statistics/`. When no such base exists, run the standard
file-artifact workflow of this Skill unchanged.

## 1. Snapshot-bound retrieval

Start with the deterministic gateway:

```text
<python3> knowledge/tools/blueprint_query.py snapshot            # or statistics/tools/...
<python3> knowledge/tools/blueprint_query.py math-closure --context <CONTEXT-ID>
<python3> knowledge/tools/blueprint_query.py math-frontier --goal <GOAL-OR-CLAIM-ID> --context <CONTEXT-ID>
<python3> knowledge/tools/blueprint_query.py math-goals --context <CONTEXT-ID>
```

Bind every follow-up query to both snapshot hashes. On `SNAPSHOT_MISMATCH`,
discard accumulated results and re-fetch. Keep three classes separate:

1. trusted claims and definitions available in the current context;
2. proved conditional inferences whose premises are not yet available;
3. open, blocked, candidate, refuted, and historical research records.

Only class 1 may be cited as an available premise. Class 2 may be reused as a
conditional theorem. Class 3 may be assigned as research but never propagates
truth.

## 2. Proposition/inference hypergraph

Represent propositions as claim nodes and every nontrivial entailment as a
first-class inference node:

```text
premise claims -> mathematical_inference -> conclusion claim
definitions    -> mathematical_inference
```

Several premises entering one inference encode logical AND; several inferences
concluding the same claim encode alternative OR routes. Never omit an unknown
link or present it as an accepted edge. Create claim nodes and inference nodes
for every step of a chain `A -> B -> C -> D`, marking unproved steps `open`.

Claim epistemic types: `problem_hypothesis`, `definition_contract`,
`external_mathematical_result`, `mathematical_claim`, `verified_counterexample`.
Research types: `mathematical_inference`, `research_goal`, `proof_obligation`,
`research_attempt`.

Status semantics:

- claims carry `truth_status`: `given`, `imported_verified`, `open`,
  `candidate_supported`, `established`, `refuted`, `contested`, `target`,
  `superseded`;
- inferences carry `proof_status`: `proposed`, `open`, `assigned`,
  `candidate_proof`, `proved`, `refuted`, `blocked`, `invalid`, `superseded`;
- the generic `status` field equals the specialized status;
- only `proved` inferences propagate conclusions; all other statuses are
  research memory.

## 3. Trusted closure

The deterministic closure, not grade or file location, decides proof-input
eligibility. Seed from problem hypotheses, source-verified imported results,
and accepted verified counterexamples in the context. Repeatedly add the
conclusion of any `proved` inference whose premises are trusted. Never add
refuted, contested, or superseded conclusions. If a verified counterexample
refutes an available claim, report the contradiction and stop using that claim
until the conflict is resolved.

## 4. Research goals are theorem contracts

A `research_goal` freezes `contract_version`, `quantifier_contract`, explicit
`boundary_cases`, `completion_criteria`, `non_completion_conditions`,
`permitted_outcomes`, and `tool_constraints`. Changing the statement or the
completion contract requires a new goal or claim version with an explicit
supersession relation. Never mutate a frozen statement in place.

## 5. Proof and refutation packages

Before proposing `proof_status: proved`, freeze a content-hashed proof package
and bind its path and exact SHA-256 on the inference node. The package records
the inference ID and statement hash, premise IDs and semantic hashes,
definition IDs, ordered proof steps, boundary-case discharges, external theorem
contracts and symbol mappings, computational certificates and limitations,
`unresolved_obligations: []`, and author/run lineage. Every nontrivial step
identifies an upstream claim, an exact imported theorem, a definition, or an
explicit valid transformation.

A refuted inference binds a `refutation_package`; a verified counterexample
binds a `certificate` and names its refutation targets. A candidate
counterexample not checked against every premise remains non-trusted.

## 6. Four mandatory audits

Independent proof approval requires all four audits, each bound to the exact
proof-package hash:

- definition audit: objects, maps, quotients, multiplicities, orientation,
  notation, local/global distinctions, category membership;
- logic audit: quantifier order, implication direction, necessity versus
  sufficiency, induction decrease, termination, existence choices, circularity,
  local-to-global transitions;
- boundary audit: empty, zero, disconnected, low-dimensional, parity, equality,
  singular, noncompact, noncomplete, non-smooth, critical-parameter, and
  degenerate cases;
- adversarial audit: attack the weakest step, enumerate smallest objects,
  search extreme parameters, verify every obvious compatibility condition, and
  test whether the central missing lemma merely restates the target.

## 7. Mathematics evidence and review coverage

In proposals, use `math_premise_contracts`, `math_proof_justifications`,
`math_refutations`, and `math_research_state_records`. In independent review,
use the matching `math_premise_checks`, `math_proof_checks`,
`math_refutation_checks`, and `math_research_state_checks`. Every proposed
mathematics record needs a matching review entry; approval repeats the exact
`proof_package_sha256` and reports the four passing audits. The receiver
rejects missing coverage or hash binding even if the verdict says `approve`.

## 8. Computation under contract

Record the exact mathematical object and property checked, the validity
predicate separately from any score, the parameter domain, arithmetic model,
precision, tolerance, time and memory limits, software versions, random seeds,
witness or certificate format, and exact replay command. Use adversarial and
held-out tests. Finite or numerical success yields a `research_attempt`,
candidate counterexample, or bounded result; it becomes a general theorem only
after a proof or completeness certificate closes the bridge.

## 9. Failure admission

Admit a failed route canonically only when it names a stable target, its
method family, the first failing mathematical step, an exact gap, whether the
failure refutes the implication or only the method, and restart conditions.
Every `research_attempt` carries a mechanism-distinct `route_key`, a concrete
`deliverable_contract`, fast `falsification_tests`, an expected bottleneck, and
provenance. A `proof_obligation` records discharge criteria and its strength
relative to the target; equivalent or near-equivalent theorem-strength gaps are
marked blocked until a materially new mechanism appears.

## 10. Reporting: transaction status versus research status

Keep transaction status separate from research status:

```text
transaction_status: merged
research_status: partial_progress
```

A merged partial lemma means the update transaction succeeded, not that the
goal is solved. Declare the goal solved only when the target belongs to the
computed trusted closure in the intended context and the merged receipt is
verified. Report the exact frontier, blocked obligations with their strength,
refuted routes, reusable audited failures, and the minimum next mathematical or
computational evidence required. Use the calibrated result labels and the
novelty labels of this Skill; distinguish human, model, tool, and source
contributions.