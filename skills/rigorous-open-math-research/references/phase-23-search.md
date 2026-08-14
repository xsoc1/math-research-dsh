> Phase file for the rigorous-open-math-research skill. Read this file before executing the phases it covers; the global contracts live in the parent SKILL.md. Relative paths in this file (assets/, references/, scripts/) resolve against the skill root (the directory containing SKILL.md).
## Phase 2 — Map known mathematics

Create a compact, exact map of:

- strongest known results and their hypotheses;
- standard reductions and whether they are reversible;
- extremal examples and known obstructions;
- nearby solved variants;
- relevant theories, representations, invariants, and computational resources;
- open sublemmas already known to be equivalent or nearly equivalent to the target.

For every cited theorem, store the exact statement needed and verify all hypotheses. Do not cite a paper title as if it proved the required formulation.

Distinguish:

- `KNOWN`: verified from a primary source or formal library;
- `DERIVED`: proved in this project;
- `CONJECTURED`: plausible but unproved;
- `HEURISTIC`: supported only by examples or analogy;
- `RECALLED_UNVERIFIED`: memory that must not be used as a premise yet.

### Semantic theorem retrieval

Prefer a semantic theorem-retrieval service (an indexed arXiv theorem/lemma/definition corpus queried with a complete mathematical statement rather than keywords) over full-text keyword search when available. For each returned item, record its full statement plus arXiv id, theorem id, and paper id. Download the paper and read its text before relying on the result; expand the paper's local definitions and check that terminology and hypotheses actually match the current setting. Read the proof of a useful theorem and extract adaptable techniques. If a result is only partial, record the extra hypotheses, why the method does not settle the full statement, and what obstruction this reveals. If semantic retrieval returns nothing useful, fall back to general web search and record the stalled query.


When a canonical knowledge base exists (MRP `knowledge/` or Blueprint `statistics/`), bind this phase to it: run `snapshot`, then `math-closure --context <ID>` and `math-frontier --goal <ID> --context <ID>`; keep trusted claims, proved conditional inferences, and open research records in three separate classes; cite reused accepted results by node ID plus semantic hash. See `references/blueprint-math-graph-integration.md`.
## Phase 3 — Build the proof-obligation graph
### Divergent search contract

Run literature search as a divergent pass: search wide, do not gatekeep.

- The search role decides what is interesting, whose result it is, and where it came from - not what is admissible. Correctness auditing belongs to a separate verifier pass; never discard a candidate preemptively to spare the audit.
- Provenance honesty is the one hard constraint: every entry must be traceable to a real query result or source note. Record `query -> result -> locator` for every entry. Never fabricate a result, statement, locator, or citation.
- Layer the pipeline and record what each layer contributed:
  1. keyword families (synonyms, notation variants, and the older vocabulary a result may be stated in); search each family, then merge;
  2. the project knowledge base and tool library first, to avoid re-tracing indexed results;
  3. local references and recent query indexes;
  4. arXiv / OpenAlex / zbMATH for surveys, theorem provenance, and reference chains;
  5. general web search (textbooks, lecture notes, course pages, blogs, MathOverflow/MSE, journal pages, GitHub) - non-paper sources frequently carry constructions, counterexamples, and numerical evidence that never made it into a paper; treat such finds as legitimate results with honest provenance;
  6. deep-read promising hits: extract the exact statement needed, its preconditions, and a locator; do not stop at the abstract.


Represent the desired result as a dependency graph.

Each node should contain:

```markdown
ID:
Statement:
Quantifiers:
Depends on:
Evidence/status: OPEN | PARTIAL | PROVED | FORMALIZED | REFUTED | BLOCKED
Proof or citation:
Known edge cases:
Verifier notes:
```

The root theorem is complete only when every dependency has an acceptable proof and every interface between modules has been checked.

If no useful decomposition is known, create explicit meta-obligations such as:

- find an invariant that decreases under the proposed reduction;
- characterize minimal counterexamples;
- derive a certificate for the computational construction;
- prove the representation change is reversible.


Represent the obligation graph as a proposition/inference hypergraph when recording it canonically: propositions are claim nodes, and every nontrivial entailment is a first-class `mathematical_inference` node with premises, definitions, one conclusion, and a `proof_status`. Claims carry `truth_status`; the generic `status` equals the specialized status. Only `proved` inferences propagate conclusions; `open`, `candidate_proof`, `blocked`, `refuted`, and `invalid` steps remain research memory and may be assigned but never cited as proof inputs.
