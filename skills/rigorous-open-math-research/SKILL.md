---
name: rigorous-open-math-research
description: >-
  Investigate open or research-level mathematics problems with explicit theorem contracts, diverse search, persistent research ledgers, executable checks, adversarial proof audits, literature verification, calibrated reporting, and snapshot-bound mathematics knowledge-graph integration when the project provides one. Use when asked to solve, disprove, advance, formalize, or rigorously audit a difficult mathematics problem.
  中文触发: 适用于定理证明, 猜想攻关, 反例搜索, 结构分类, 等价刻画, 复杂推导, 严格审计等困难数学问题,
  也用于把计算证据升级为可审计定理或给出精确剩余缺口.
---

## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `rigorous-open-math-research`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`manage-math-research-program`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- Reference files under `references/` and `assets/` are read with the read tool
  using the `resourceBase` directory path reported by the skill load result.
- Bundled scripts (of the sibling skills) run with a local Python interpreter via
  the shell: `python <script> ...`, with `PYTHONUTF8=1` on Windows. Prefer writing
  a temporary .py file over PowerShell one-line `-c` calls.
- The DSH adaptation keeps every upstream file byte-identical except this block;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.

# Rigorous Open Mathematics Research

## 中文使用说明 (摘要)

本 Skill 用于对开放、前沿或高难度数学问题做严格研究. 它不承诺用措辞解决开放问题,
而是最大化可审计进展: 显式定理契约, 多样化搜索, 持久研究台账, 可执行验证, 对抗性证明审计, 文献核验与校准式报告.

- 触发场景: 定理证明, 猜想攻关, 反例搜索, 结构分类, 等价刻画, 复杂推导, 严格审计.
- 图谱集成: 若项目提供已接受知识库 (Blueprint v2.2 数学超图), 检索将绑定快照 (math-closure / math-frontier), 可依赖前提与前沿由确定性程序给出, 合同见 references\blueprint-math-graph-integration.md.
- 启动后按 Phase 0-12 工作, 并维护 "Default research artifacts" 中的台账文件.
- 结果必须按 "Output protocol" 的状态标签开头, 未闭合义务不得标为完成.
- 本 Skill 是求解执行层; 长期项目管理由 `$manage-math-research-program` 负责, 二者只允许 管理到求解 的单向调用.
- 中文设计依据与完整分析: `references/ai-open-math-prompting-design-analysis.zh-CN.md`; 旧版中文 v1 全文: `references/rigorous-mathematical-research.v1-zh-CN.md`.
## Purpose

Use this skill to conduct serious AI-assisted research on an open, frontier, or unusually difficult mathematics problem.

The goal is not to produce a persuasive-looking proof. The goal is to maximize the chance of obtaining one of the following, with its status stated honestly:

- a complete proof or disproof;
- a formally or independently verified construction;
- a rigorous partial theorem;
- a useful reduction with a strictly smaller unresolved core;
- a falsified route, counterexample, or exact obstruction;
- a reproducible computational pattern that yields clear proof obligations.

Treat the **entire research configuration** as the input: problem statement, attachments, known results, code, evaluators, theorem-prover versions, tools, model constraints, search restrictions, and human-provided hints. Never pretend that a one-line instruction was the full prompt when essential context came from other files or systems.

## Non-negotiable epistemic rules

1. Never claim a complete solution while any required proof obligation remains open.
2. Never silently change a quantifier, domain, definition, regularity assumption, asymptotic regime, or boundary case.
3. Never call a theorem-strength missing lemma “routine”, “standard”, or “technical” without proving it or citing an exact applicable theorem.
4. Finite computation, numerical evidence, and passing a score function do not imply a general theorem unless a proof or universally checkable certificate bridges the gap.
5. Formal verification proves the formal statement, not automatically its fidelity to the original problem or its novelty.
6. Distinguish correctness, completeness, novelty, autonomy, and reproducibility. Do not collapse them into one word such as “solved”.
7. Do not invent hidden prompts, run counts, model settings, tool traces, or human interventions. Mark unknown information as unknown.
8. Do not require or expose private chain-of-thought. Require externally checkable artifacts: definitions, lemmas, equations, constructions, counterexamples, citations, code, certificates, and exact gap reports.
9. A failed route is a research result when its failure mechanism is precise and reusable. Record it.
10. At a resource boundary, report the strongest audited progress and exact remaining gaps. Only the **completion label** is withheld until the proof is complete; useful partial results must not be suppressed.

## Default research artifacts

When persistent files are available, maintain the following. If files are unavailable, use equivalent clearly labeled sections in the response.

- `problem_contract.md` — exact normalized statement and completion criteria.
- `repro_manifest.md` — all inputs, versions, tools, restrictions, hashes or identifiers, and unknown fields.
- `status_and_literature.md` — current problem status, exact known theorems, citations, and novelty risks.
- `obligation_graph.md` — claims, dependencies, and proof status.
- `approach_registry.md` — route families, owners, states, and exact gaps.
- `research_ledger.md` — chronological experiments, derivations, decisions, and failures.
- `counterexample_log.md` — tested edge cases, failed lemmas, minimal counterexamples, and search code.
- `candidate_proof.md` — current integrated proof or disproof draft.
- `audit_report.md` — independent verification results and unresolved issues.
- `reproducibility/` — code, exact commands, seeds, certificates, and formalization files.

Update the ledger immediately after any substantial computation, proof attempt, literature discovery, or route decision. Do not begin a near-duplicate exploration until the previous result and failure mechanism are recorded.

# Workflow

## Phase 0 — Provenance, status, and scope

Before mathematical search:

1. Identify the authoritative problem statement and date/version.
2. Check whether the problem is genuinely open as of the research date, unless the user explicitly requests a blind benchmark phase.
3. Locate variants whose quantifiers or definitions differ.
4. Inventory every attachment, program, verifier, seed, example, formal library, and environment version.
5. When the run provides a per-problem reference directory (for example `data/<id>.refs/` with markdown, LaTeX, plain text, or pre-extracted PDF text), read those user-provided files before external search. Treat them as user-provided context, not verified facts; cite them in the ledger and in proof steps when they influence the proof. Never present user-provided notes as independently verified results.
6. Record tool and web restrictions exactly.
7. Separate historical facts from reconstructed prompts or suggested workflows.
8. When the run workspace is a git repository, check its state before starting: record the current commit hash and any dirty files in the ledger. Do not silently overwrite uncommitted artifacts; commit them or record the divergence first.

If exact-solution search is forbidden for benchmarking, use two phases:

- **Blind discovery phase:** obey the restriction and record it.
- **Post-discovery novelty audit:** search the literature before making any novelty claim, unless the user explicitly forbids even a later audit.

## Phase 1 — Build the theorem contract

Write `problem_contract.md` with this schema:

```markdown
# Problem contract

## Objects and definitions
## Hypotheses
## Target conclusion
## Quantifiers and dependency of constants
## Equivalent formulations that are actually proved equivalent
## Boundary and degenerate cases
## Permitted outcomes
- affirmative proof
- negative proof / counterexample
- independence or inconsistency result, when logically relevant

## Completion criteria
## Results that do not count as completion
## Tool, citation, and search constraints
## Ambiguities or competing interpretations
## Contract audit
```

For an open conjecture, do not assume an affirmative proof exists by default. Preserve both proof and disproof routes unless a trusted benchmark guarantees polarity. If the wording is ambiguous, either obtain clarification or analyze each materially different interpretation separately.

Assign a second role or pass to audit the contract against the source. A proof of the wrong contract is not progress on the original problem.

When a canonical knowledge base exists, freeze these fields on the `research_goal` record and mirror them in `problem_contract.md`: `contract_version`, `quantifier_contract`, explicit `boundary_cases`, `completion_criteria`, `non_completion_conditions`, `permitted_outcomes`, and `tool_constraints`. A statement or completion-contract change requires a new goal or claim version with an explicit supersession relation; never mutate a frozen statement in place.

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

## Phase 6 — Computational and evolutionary search

Use computation as a discovery and falsification instrument.

Before running code, specify:

```markdown
Mathematical object returned:
Property checked exactly:
Objective or score:
Penalty for invalidity:
Parameter domain and test distribution:
Exact versus floating-point operations:
Time and memory limits:
Random seeds:
Certificate or witness produced:
How a successful candidate could imply a general theorem:
Known evaluator exploits or blind spots:
```

Required safeguards:

- Separate validity from quality scores.
- Include small, large, random, structured, and adversarial parameters.
- Hold out tests not seen during search when possible.
- Minimize or symbolically simplify successful programs to expose a general pattern.
- Search for counterexamples to every inferred formula.
- Preserve the best candidate, its full provenance, and a replay command.
- Audit whether the candidate exploits an implementation detail rather than the mathematical definition.

After finding a pattern, create a **proof bridge**:

1. state the candidate formula or construction for general parameters;
2. prove it is well-defined;
3. prove validity for every allowed parameter;
4. prove the claimed bound or objective;
5. identify what remains unproved about optimality.

Never label a high-scoring numerical path as an optimal theorem without this bridge.

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
## Phase 9 — Revision policy

A reviser receives the exact gap list, not a vague request to improve the proof.

For each gap:

1. classify it as local, structural, semantic, bibliographic, or computational;
2. attempt the smallest valid repair;
3. rerun all downstream obligations affected by the change;
4. if the repair introduces a theorem-strength lemma, mark the route blocked;
5. if the core mechanism fails, archive the route and switch methods rather than cosmetically rewriting it.

A verifier must recheck the revised proof from the changed point onward. The reviser cannot self-certify closure.

### Failure routing by smallest owner

Classify each failure by its owner: plan, source theorem, definition, final assembly, route strategy, or target obstruction. Route the repair to the smallest responsible role. Do not ask the same proof writer to rephrase the same failed route when the audit identifies a different owner. A regulator role may classify difficult failures and queue alternates, but must not prove, verify, or merge.

## Phase 10 — Formalization and reproducibility

When using Lean, Coq, Isabelle, HOL, or another prover:

- pin the prover and library versions;
- store the exact theorem statement and compare it line-by-line with the problem contract;
- record all imported axioms and nonconstructive principles;
- disallow unfinished placeholders such as `sorry` or `admit` in the final artifact;
- avoid opaque native-decision shortcuts unless their trust model is explicitly accepted;
- provide clean build and audit commands;
- retain the generated certificate or proof term when feasible.

### Statement freeze before proof repair

Compile the declarations first as a structural skeleton: translate every statement, allow proof holes (`sorry`) during compilation, and repair namespace, type, and signature consistency so the whole project compiles. Then freeze the statement signatures and only then iterate proof repair against verifier feedback. Any change to an already-approved statement requires a fresh statement re-audit (and, when the run uses a statement guard, a new guard snapshot) before proof work resumes.

### Sorrifier decomposition

When a proof block fails, replace that block with `sorry`, re-check that the remaining skeleton still compiles, extract the failing block as a clean subproblem, and solve it recursively. Do not regenerate the whole proof, and do not let context grow without bound. Track every `sorry`; the final artifact must contain none.

### Four gates plus semantic review

Before an edited declaration enters the accepted development, run: (1) compile check, (2) sorry/admit scan, (3) axiom-set check, and (4) a guard that protected statement signatures did not change. Then a human semantic review confirms the formal statement still means what the source means - this last check cannot be delegated to the same LLM that wrote the statement.

If full formalization is too expensive, prioritize:

1. the statement translation;
2. the most novel or fragile lemma;
3. finite combinatorial reductions;
4. algebraic identities and boundary cases;
5. interfaces between independently proved modules.

For code, store dependencies, seeds, exact commands, input hashes, expected outputs, and a minimal test suite.

When the run workspace is a git repository, commit the run artifacts before stopping and record the commit hash plus any uncommitted leftovers in the reproducibility manifest, so the exact audited state can be restored.

## Phase 11 — Novelty and significance audit

Correctness and novelty are separate.

Classify novelty as:

- `KNOWN_IN_LITERATURE`
- `DIRECT_COROLLARY_OF_KNOWN_RESULT`
- `INDEPENDENT_REDISCOVERY_POSSIBLE`
- `POTENTIALLY_NEW`
- `EXPERT_NOVELTY_CHECKED`
- `UNKNOWN`

Search for alternate terminology, equivalent formulations, older surveys, theses, and results with extra assumptions. Record whether the candidate could have been reproduced from pretraining without explicit citation. Formal verification does not settle this question.

Also classify significance separately: exercise-level consequence, useful lemma, new method, substantial theorem, or major resolution. Do not infer significance merely from how long the problem was listed as open.

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
- a decisive ambiguity in the problem cannot be resolved.

Stopping does not permit pretending success. Return the strongest rigorously supported result and the exact remaining gap.

# Output protocol

Begin with a one-line status chosen from:

- `FORMALLY_VERIFIED_PROOF`
- `INDEPENDENTLY_AUDITED_PROOF`
- `CANDIDATE_COMPLETE_PROOF`
- `RIGOROUS_PARTIAL_RESULT`
- `VERIFIED_GENERAL_CONSTRUCTION`
- `FINITE_COMPUTATIONAL_RESULT`
- `NUMERICAL_EVIDENCE`
- `COUNTEREXAMPLE_CANDIDATE`
- `BLOCKED_REDUCTION`
- `NO_MATERIAL_PROGRESS`

Then provide:

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

# Anti-patterns

Do not rely on:

- “You are a genius mathematician” role-play;
- forceful persistence language without actual resources;
- fixed numbers of ideas, agents, or hours as universal constants;
- long prompts that repeat the same completion demand;
- post-hoc hints presented as original discovery prompts;
- same-model approval as the only proof check;
- a verifier that checks style instead of obligations;
- finite test success presented as asymptotic or universal proof;
- hidden human selection presented as autonomous discovery;
- a beautiful reduction whose missing lemma is equivalent to the conjecture;
- polished LaTeX before mathematical closure;
- novelty claims without literature audit.

# Minimal invocation

```text
Use the rigorous-open-math-research skill on the following problem.
First build and audit the theorem contract, then run a diverse research portfolio,
maintain an obligation graph and route ledger, use computation or formalization where
appropriate, and subject every candidate proof to adversarial verification.
Return the strongest rigorously supported result with an exact status label, remaining
gaps, provenance, and reproducibility information. Do not invent unpublished run data.

Problem:
{{problem}}

Available attachments/tools/constraints:
{{context}}
```


## Changelog (2026-08-11)
## Changelog (2026-08-12)

- 新增发散式检索契约 (Phase 2): 搜索宽不守门, 相关性判断与正确性审计分离, 来源诚实三要素 (query -> result -> locator), 分层检索流水线 (关键词族/KB 优先/本地引用/arXiv+OpenAlex+zbMATH/通用网页/深读正文).
- 新增首次见证验证者标准与自动失败模式 (Phase 8): verifier 无记忆首次审稿, 14 类自动 FAIL 模式, 首错定位 + 错误层分类 (陈述/证明/依赖/边界约定), 结构化输出增加 first_error.
- 新增最小责任失败路由 (Phase 9): 失败按归属分类 (计划/来源/定义/装配/路线策略/目标障碍), 派最小责任角色, regulator 只分类不代笔.
- 新增形式化三机制 (Phase 10): 陈述冻结后再修证明 (已批准陈述修改需重新过审), sorrifier 分解 (失败块 sorry 化保留骨架 + 子问题递归), 四道闸 + 人工语义复核 (编译/sorry/axiom/guard + 陈述仍忠于来源).
- 新增新鲜上下文收敛检查 (Phase 12): 收尾/长跑中段/策略转向后只从文件重建现状, 判断收敛与否, 只登记不修改.
- 方法来源: MMAT nl-prover/fl-prover prompts (https://github.com/MechMath/MechMath-agent-team), LeanMarathon (https://github.com/YuanheZ/LeanMarathon), MechMath-v1 sorrifier (https://github.com/MechMath/MechMath-v1), M2F (https://github.com/optsuite/M2F), FaithSieve (https://github.com/TropicalFatFish/anonymous-faithsieve), FormalRx (https://github.com/LARK-AI-Lab/formalrx, arXiv:2607.04655), Archon-Horizon (https://github.com/frenzymath/Archon-Horizon).


- 新增子 agent 分工模式 (Agent orchestration + references/subagent-delegation.md + assets/subtask-packet.template.md): 路线探索/义务证明/反例猎手/文献审计/证明验证的并行子 agent 分工, 子任务包契约 (subgoal_id, 输入 hash, 输出契约, 约束, 预算), 隔离与去相关, 合并协议 (只合并已审计模块 + Phase 7 接口检查), 失败机制入档, 动态资源分配与单 agent 顺序 fallback.
- 新增 arXiv 定理语义检索机制 (Phase 2): 以完整数学陈述查询语义定理检索服务, 记录完整陈述/arXiv id/theorem id/paper id, 下载原文核验后再引用; 局部结果必须记录额外假设与真实障碍.
- 新增检索与深度思考交替调度 (Phase 5): 检索轮与禁用检索的独立推理轮交替, 检索失效时转入非检索技能并记录停滞查询.
- 新增结构化验证输出规范 (Phase 8): audit 记录采用 verdict + critical_errors/gaps/repair_hints 字段, 严格规则 (errors 与 gaps 全空才 PASS), 非 PASS 必须提供修复提示.
- 新增用户引用目录机制 (Phase 0): 问题附带引用目录时先于外部检索读取, 视为用户提供的上下文而非已核验事实.
## Changelog (2026-08-09)

- 蒸馏整合 Blueprint v2.2 数学工具包 (Downloads/blueprint-v22-math-codex-toolkit): 命题/推理超图与状态语义, 可信闭包与目标 frontier 查询钩子, research_goal 结构化契约字段, 内容哈希证明包, 四项强制审计 (definition/logic/boundary/adversarial), 事务状态与研究状态分离, 失败入档纪律.
- 新增参考: `references/blueprint-math-graph-integration.md` (v2.2 蒸馏合同).
- 原有 Phase 3/4/8/12 与 Output protocol 相应增强; 当项目提供规范知识库 (MRP knowledge/ 或 Blueprint statistics/) 时, 工作流与图集成.
## Changelog (2026-08-05)

- 由 `rigorous-mathematical-research` v1.0 (中文) 迭代升级并改名为 `rigorous-open-math-research`.
- 基底内容来自 `Downloads/rigorous-open-math-research` (英文版).
- 新增: 双语触发描述, 中文使用说明摘要, `references/` 中文设计分析报告与旧版 v1 全文.
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block; all upstream content is byte-identical
  otherwise (see `upstream.lock.json`). This bundle is the DSH counterpart of
  the Codex plugin `rigorous-open-math-research` in the math-research
  marketplace repository (https://github.com/xsoc1/rigorous-open-math-research).
