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

When the retrieval corpus is a local deterministic index (pure lexical, no LLM in the retrieval loop), keep the loop deterministic: identical query, identical result set; flag out-of-scope results explicitly (`oos_reason`) instead of hallucinating a source the index cannot contain. Cite results by section name or record ID, not by internal line numbers. (Distilled from dsh-kb-sieve: https://github.com/omdsh-dev/dsh-kb-sieve.)


When a canonical knowledge base exists (MRP `knowledge/` or Blueprint `statistics/`), bind this phase to it: run `snapshot`, then `math-closure --context <ID>` and `math-frontier --goal <ID> --context <ID>`; keep trusted claims, proved conditional inferences, and open research records in three separate classes; cite reused accepted results by node ID plus semantic hash. See `references/blueprint-math-graph-integration.md`.
## Phase 3 — Build the proof-obligation graph
### Divergent search contract

Run literature search as a divergent pass: search wide, do not gatekeep.

- The search role decides what is interesting, whose result it is, and where it came from - not what is admissible. Correctness auditing belongs to a separate verifier pass; never discard a candidate preemptively to spare the audit.
- Provenance honesty is the one hard constraint: every entry must be traceable to a real query result or source note. Record `query -> result -> locator` for every entry. Never fabricate a result, statement, locator, or citation.
- Record the retrieval facts of every entry, not just the locator: `status` is `ok` (the named source answered) / `degraded` (a stand-in corpus or fallback engine answered; say which) / `unavailable` (the source was unreachable - record that, never leave the slot silent). Separate `uncertainty` (epistemic doubt about the fact: conflicting sources, likely-outdated numbers, thin pages) from `warnings` (how the retrieval was produced: engine fallback, degraded stand-in). Keep the ordered list of engine attempts so routing facts cannot be retro-fabricated. Never invent a numerical relevance score; the result ordering itself carries relevance, and invented scores are lies. (Distilled from modsearch: https://github.com/liustack/modsearch, argo: https://github.com/taxueseek/argo.)
- Layer the pipeline and record what each layer contributed:
  1. keyword families (synonyms, notation variants, and the older vocabulary a result may be stated in); search each family, then merge;
  2. the project knowledge base and tool library first, to avoid re-tracing indexed results; also query the local read-literature index (paper analyses, Zotero-style local library when configured) and pull **bounded evidence fragments** with explicit budgets (max characters/passages), citing section names or record IDs, never bare line numbers;
  3. local references and recent query indexes; reuse prior search-log keys (queryId-style) so an already-answered question is never re-traced from scratch;
  4. arXiv / OpenAlex / zbMATH for surveys, theorem provenance, and reference chains;
  5. general web search (textbooks, lecture notes, course pages, blogs, MathOverflow/MSE, journal pages, GitHub) - non-paper sources frequently carry constructions, counterexamples, and numerical evidence that never made it into a paper; treat such finds as legitimate results with honest provenance;
  6. deep-read promising hits: extract the exact statement needed, its preconditions, and a locator; do not stop at the abstract.


### Target-problem status confirmation

Before any openness or novelty claim about the target problem itself, run a
directed confirmation pass whose job is exactly to confirm the problem status
(open / settled / settled under different hypotheses / known equivalent), not
to gather general background. Treat every hit about the target problem as
`fetch_required`: an abstract, title, or secondary summary is never enough to
claim the problem is open or solved - fetch the full text (or record the
paywall/unreachability explicitly) before the status claim. For each target
hit record its fetch status: `fetched-verified` | `abstract-only` |
`paywalled` | `unreachable`; a claimed status resting only on
`abstract-only`/`paywalled` hits is dishonest.

Layered confirmation, in order:

1. own knowledge base, tool library, and read-literature index (bounded
   evidence fragments, section-name citations) - the project may already
   contain the answer;
2. arXiv / OpenAlex / zbMATH latest versions, corrections, and reference
   chains (who cites whom, which formulation is newest);
3. semantic retrieval with full-text fetch pairs (search then fetch the
   candidate full text; a semantic hit without its text is a lead, not a
   fact);
4. general web fallback (blogs, MO/MSE, lecture notes, GitHub).

Order the corroborating hits with an explicit heuristic - domain authority,
evidence density (numbers, definitions, comparisons), freshness, and
consensus across independent sources - as an ordering aid only; the ordering
is a hypothesis about relevance, never a proof ingredient. After the pass,
list what evidence is still missing (a version behind a paywall, the original
proof text, an independent formulation) as directed reconnaissance targets.
Remember verified fetch status across sessions so re-confirmation reuses the
backfilled record instead of re-searching. (Distilled from argo:
https://github.com/taxueseek/argo, modsearch: https://github.com/liustack/modsearch,
dsh-zotero: https://github.com/Vncntvx/dsh-zotero, dsh-exa-mcp:
https://github.com/MicroHEROX/dsh-exa-mcp.)

### Coverage dimensions and gaps

Enumerate the information dimensions the search must span (methods, classes, regimes, notations, literature lineages) and map every route and subproblem to at least one dimension. Record `coverage_gaps` for dimensions nothing currently covers, and treat each declared gap as a target for directed reconnaissance, not as silently accepted territory. A controller that sees fewer dimensions than the domain has is guaranteed blind spots. (Inspired by dsh-deep-research: https://github.com/omdsh-dev/dsh-deep-research.)

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
