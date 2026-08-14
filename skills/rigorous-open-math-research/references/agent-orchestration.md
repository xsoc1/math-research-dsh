> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
# Agent orchestration

Use multiple agents only when available and useful. The value comes from role separation and uncorrelated approaches, not agent count.

Recommended roles:

- **Coordinator:** owns the contract, obligation graph, registry, and resource allocation.
- **Explorers:** pursue distinct mathematical mechanisms independently.
- **Counterexample hunter:** attacks conjectures and every proposed lemma.
- **Computation specialist:** builds exact tests, searches examples, and extracts certificates.
- **Literature auditor:** verifies current status, exact citations, and novelty.
- **Proof verifier:** checks semantic fidelity and each logical dependency.
- **Reviser:** repairs explicitly identified gaps.
- **Formalizer:** translates critical statements and proofs into a proof assistant.
- **Synthesizer:** combines only audited modules.

Dynamic policy:

1. Start with several genuinely different route families.
2. Keep early explorers independent.
3. Redirect duplicate routes toward underexplored mechanisms.
4. Give more resources to routes producing verified lemmas, counterexamples, or high-information experiments.
5. Block routes whose only progress is an equivalent conjecture.
6. Cross-pollinate after routes expose their real bottlenecks.
7. Keep an adversarial verifier active throughout, not only at the end.

### Model tiering

Where the runtime supports per-agent model selection, tier the roles instead of giving everyone the strongest model: planner, synthesizer, and audit roles on the strong model; bulk research, retrieval, and candidate scanning on a cheap model; formalizer on whatever model the proof-assistant workflow requires. Default to inheriting the main agent's model when no tiering is configured. (Inspired by dsh-deep-research: https://github.com/omdsh-dev/dsh-deep-research and dsh-multiagent-modes: https://github.com/y08lin4/dsh-multiagent-modes.)

### Sub-agent delegation

Use spawned sub-agents when the runtime provides them (for example Codex multi-agent), for
parallelizable, well-bounded subtasks. Role separation and uncorrelated approaches are the
value; agent count is not. Do not delegate global synthesis or resource decisions. Detailed
scheduling, isolation, merge, and failure rules: `references/subagent-delegation.md`.

Appropriate parallel targets:

- **Route explorers (Phase 4):** one sub-agent per mechanism-distinct route, given its route
  card, a contract slice, and fast falsification tests.
- **Obligation provers (Phase 3/5):** independent obligations with no circular dependency
  proved in parallel by separate sub-agents, each returning its obligation ID, artifact, and
  exact gap.
- **Counterexample hunters:** one hunter per key lemma or inferred formula, with the exact
  claim to attack and a search budget.
- **Literature auditors (Phase 2/11):** per-topic parallel retrieval and citation verification.
- **Proof verifiers (Phase 8):** an independent audit pass with a context different from the
  formalizer; never the same agent that wrote the proof.

Subtask packet contract (template in `assets/subtask-packet.template.md`):

- `subgoal_id` binding to the obligation or route, and the exact claim attacked.
- Input artifacts by exact path and hash, plus the minimal context slice, not the whole project.
- Output contract: structured return (artifact path, artifact sha256, status label, exact gap, failure mechanism), raw JSON without a markdown code fence.
- Constraints: do not claim global completion; do not mutate shared artifacts; do not repeat a
  recorded failure without new evidence.
- Budget: explicit effort and deadline.

Isolation and decorrelation:

- Keep early sub-agents independent; do not broadcast the currently fashionable route.
- Give different sub-agents different mechanisms or adversarial perspectives.
- Have each sub-agent write to its own artifact paths; the coordinator merges only audited
  results.

Merge protocol:

- Merge only modules that passed their own audit; apply the Phase 7 interface checks (domains,
  notation, constants, simultaneous choices, gluing, interchange).
- Conflicts resolve against the audited problem contract; a sub-agent cannot override the
  contract.
- Record every sub-agent outcome (`PROVED`, `PARTIAL`, `BLOCKED`, `REFUTED`, `FALSIFIED`) in the
  ledger and approach registry; failures with a precise mechanism are research results.

Resource policy:

- Allocate dynamically by marginal information gain; no fixed agent counts.
- Cap concurrency and total budget; stop correlated duplicates early.
- If a sub-agent stalls or returns noise, record it and redirect resources.

Single-agent fallback: execute these roles sequentially, write each role's artifact before
switching, and perform the verifier pass with a fresh context or deliberately adversarial
prompt. When spawn capability is unavailable, run sub-tasks one at a time in the same session,
preserving the same packet contract and isolation rules.

# Reusable role prompts

## Explorer

```text
Work only on route {{route_id}} for the theorem contract below.
Return externally checkable mathematics, not a motivational discussion.

Produce:
1. the exact subclaim attacked;
2. a concrete lemma, construction, equation, counterexample, or algorithm;
3. all assumptions and dependencies;
4. small and adversarial tests;
5. the first unresolved step;
6. whether that step is strictly easier than the original theorem.

Do not claim completion of the global problem.
```

## Counterexample hunter

```text
Attack the proposed claim literally. Search boundary cases, degenerate objects,
small parameters, equality cases, disconnected or singular examples, and cases
where choices cannot be made simultaneously. When possible, write exact search
code or provide a minimal symbolic counterexample. If no counterexample is found,
state only the tested domain and do not infer universal truth.
```

## Verifier

```text
Audit the candidate against the exact theorem contract. Identify the earliest
nontrivial unsupported step. Check quantifiers, hypotheses, edge cases, circularity,
equivalent-strength missing lemmas, citations, and any computation-to-theorem leap.
Return a verdict from the audit taxonomy, an exact gap list, and whether each gap
is locally repairable. Do not rewrite the proof unless asked after the audit.
Treat the proof as a first-time submission with no memory of prior rounds, and apply
the automatic failure patterns (first-time verifier standard). Localize the FIRST
erroneous step and classify its error layer (statement/proof/dependency/boundary-
convention).
```

## Reviser

```text
Repair only the enumerated gaps. For every change, state which obligation is closed
and which downstream obligations must be rechecked. If a repair requires a new
lemma comparable in strength to the original problem, mark the route BLOCKED and
do not conceal this by prose. If the mechanism fails, propose a materially different
route rather than cosmetic edits.
```

## Coordinator

```text
Update the problem contract, obligation graph, approach registry, and research ledger.
Group routes by mathematical mechanism. Detect duplicates and theorem-strength gaps.
Allocate the next round toward the actions with greatest expected information gain:
a decisive lemma, counterexample, exact computation, representation change, or
independent audit. Preserve at least one disproof-oriented route unless polarity is known.
```
