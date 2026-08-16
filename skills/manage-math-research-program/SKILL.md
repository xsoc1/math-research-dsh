---
name: manage-math-research-program
description: >-
  Manage long-running, cross-paper, cross-problem mathematics research programs
  across sessions: initialize project workspaces; curate and version literature;
  maintain paper maps, open-problem portfolios, reusable tool libraries, research
  budgets, checkpoints, and stage summaries; prepare project-level task packets;
  delegate every concrete proof, disproof, construction, formalization,
  computation-to-proof, or rigorous audit to $rigorous-open-math-research; and
  ingest its audited artifacts by reference; and maintain a hash-bound, reviewed, canonical accepted-knowledge base. Use for research-program management
  and literature or knowledge-base maintenance, not for directly solving or
  auditing a single mathematical problem.
---

## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `manage-math-research-program`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message whose
first line is `/skill-name` also loads it). The sibling skills
`rigorous-open-math-research`, `math-research-workflow`, and `lean-verify` ship
beside this bundle under the same skill roots.

- `scripts/` (init_project.py, validate_project.py, sync_remotes.py), the
  `assets/` templates, and the blueprint-accepted-knowledge tools under
  `assets/blueprint-accepted-knowledge/tools/` live inside this bundle; run them
  with a local Python interpreter via the shell using the `resourceBase`
  directory path reported by the skill load result, with `PYTHONUTF8=1` on
  Windows. Prefer writing a temporary .py file over PowerShell one-line `-c`
  calls.
- `MANIFEST.sha256` is re-verified by the repository `scripts/validate_all.py`.
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the changelog relocation; the synced upstream commit is recorded in the
  repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Long scans and bulk retrieval run as background shell jobs, collected with
  job_output; never busy-poll.
- Concrete runs are delegated with the `subagent` tool (fresh, independent) or
  `subagent_fork` (context-heavy continuation); batch fan-out uses the
  `workflow` tool (template in the math-research-workflow bundle).
- Long-running programs use the goal tools (create_goal / get_goal /
  update_goal).
- Bundled scripts print verdicts last; for long outputs use the repository
  wrapper scripts/dsh_run.py (verdict + FAIL lines at the head, verdict at
  the tail, full log on disk). Optional external capabilities (document
  parsing for the literature frontier, vision for scanned sources):
  references/dsh-optional-capabilities.md.

# Manage Mathematics Research Programs

## Purpose

Use this skill as the project-management and knowledge-management layer for a sustained mathematics research program spanning papers, problems, runs, and conversations.

This skill owns the **program context**. `$rigorous-open-math-research` owns the **mathematical attack on each concrete problem**.

The only allowed dependency direction is:

```text
manage-math-research-program -> rigorous-open-math-research
```

Do not require `$rigorous-open-math-research` to call this skill, and do not create a second proof workflow inside this skill.

## Trigger boundary

Use this skill when the user asks to:

- establish, resume, or summarize a long-running mathematics research project;
- collect, version, organize, or analyze a body of papers;
- track a mathematical field, citation frontier, or portfolio of open problems;
- build or update a reusable mathematical tool library;
- prioritize several research questions or prepare a research roadmap;
- maintain cross-session state, research budgets, checkpoints, and recovery instructions;
- consolidate results from several `$rigorous-open-math-research` runs.

Do **not** use this skill as the solver when the request is only to prove, disprove, construct, formalize, or rigorously audit one specific mathematical claim. Invoke `$rigorous-open-math-research` instead.

For a mixed request, perform only the project-level setup and task packaging here, then delegate the concrete mathematical work.

## Hard non-overlap rule

This skill must not establish or reproduce:

- theorem contracts or contract audits;
- proof-obligation graphs;
- route portfolios, route registries, or dynamic proof search;
- proof, disproof, construction, or counterexample discovery;
- problem-level computational experiments or computation-to-proof bridges;
- proof-agent roles or their scheduling;
- candidate-proof synthesis, adversarial proof review, or revision;
- Lean or other formal-proof workflows;
- correctness, completeness, or novelty audits of an individual result;
- replacement result labels or a replacement result-reporting protocol.

When any of these is needed, call `$rigorous-open-math-research` by skill name.
The accepted-knowledge pipeline described below is an acceptance and ingestion
procedure, not a proof workflow. Its review covers evidence completeness,
epistemic classification, hash binding, and author-reviewer independence only.
It never re-audits a mathematical proof; proof review remains with
`$rigorous-open-math-research`.

The canonical knowledge base may record research state (goals, obligations,
inference statuses, audited failures) that `$rigorous-open-math-research`
proposes. Recording an accepted status is knowledge management; producing the
proof, refutation, audit, or novelty judgment is not. The deterministic trusted
closure, not the manager, decides whether a record may be reused as a proof
input, and only `proved` inferences propagate conclusions.

Never duplicate or rewrite the upstream files `problem_contract.md`, `repro_manifest.md`, `status_and_literature.md`, `obligation_graph.md`, `approach_registry.md`, `research_ledger.md`, `counterexample_log.md`, `candidate_proof.md`, or `audit_report.md`, nor the upstream `reproducibility/` tree. Record their paths, hashes, versions, and upstream status verbatim in the project index.

## Reference files

Read only the references needed for the current operation:

- `references/project-repository-spec.md` — directory ownership, IDs, deduplication, and project indexes.
- `references/literature-and-paper-analysis.md` — search, paper versioning, relations, and structured TeX analyses.
- `references/tool-library-spec.md` — reusable mathematical tool entries and promotion rules.
- `references/delegation-and-ingestion.md` — task packets, the upstream invocation contract, and result ingestion.
- `references/state-checkpoints-and-reports.md` — project states, effective-time budgets, checkpoints, recovery, and summaries.
- `references/boundary-checklist.md` — mandatory non-overlap check before dispatch and before stage closure.
- `references/accepted-knowledge-pipeline.md` — hash-bound submission, validation, review, and integration of accepted knowledge.
- `references/git-sync.md` — automatic git status check, commit, push, and proxy-bypass commands.

Use templates from `assets/`. Use scripts only for deterministic repository initialization or validation.

# Workflow

## 0. Automatic git repository sync

When the project root is a git repository, check synchronization before doing new work and restore it after every stage:

1. At session start, run `git status --porcelain` and `git fetch` (use `git -c http.proxy= -c https.proxy= ...` when a local proxy is configured but not running). Report uncommitted changes, untracked files, and ahead/behind versus the remote branch.
2. Do not build new work on a divergent or dirty state without recording it. If the working tree is not clean or the branch is behind the remote, first commit or pull according to the user's intent, or record the divergence explicitly in `state/current.json`.
3. Before committing, update the `AGENTS.md` session records, and keep secrets, credentials, large binaries, and generated caches out of the repository via `.gitignore` (`__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`).
4. Commit with a descriptive message at every stage boundary, then push and verify with `git status` that the working tree is clean and the branch is neither ahead nor behind. If `project.json` declares `git_sync.push_order`, push every listed remote in that order (e.g. parent first, then fork) using `scripts/sync_remotes.py --project .`, and record the order and commit hash in the session log.
5. If the remote is unreachable, keep the local commit, record the failure in the activity log, and retry the push; never silently drop local work.

Detailed commands, the proxy note, and the generic multi-remote rule are in `references/git-sync.md`.

## 1. Classify the request

Choose exactly one mode:

- `PROGRAM_ONLY` — literature, maps, tools, priorities, state, or summaries; no solver call is required.
- `PROGRAM_AND_DELEGATE` — prepare the project context and then call `$rigorous-open-math-research` for one concrete task.
- `SINGLE_PROBLEM_REDIRECT` — skip project machinery and invoke `$rigorous-open-math-research` directly.

Record the chosen mode in the activity log when a project exists.

## 2. Initialize or resume the project

If no project exists:

1. Create the repository described in `references/project-repository-spec.md`.
2. Create stable project, paper, problem, tool, task, run, and artifact IDs.
3. Set the research budget from the user's instruction. Leave it unset when no budget was requested.
4. Create `state/RESUME.md` with the immediate recovery path.

Prefer:

```bash
python scripts/init_project.py PROJECT_ROOT --name "PROJECT NAME"
```

Add `--research-budget-hours 8` only when this project actually uses that configured threshold. Eight hours is not a universal default.

If a project exists, read `project.json`, `state/current.json`, `state/RESUME.md`, the relevant indexes, and the latest checkpoint before doing new work.

## 3. Curate the literature frontier

For each search cycle:

1. Search Google, Google Scholar, arXiv, and relevant professional databases when available.
2. Record the exact query, date, database, filters, and result-selection rationale.
3. Prefer primary papers for mathematical claims; use surveys to navigate terminology and citation chains.
4. Follow backward references, forward citations, later versions, corrections, and independent formulations.
5. Normalize identifiers and deduplicate before saving a new paper.
6. Preserve version-specific provenance: source URL, retrieval date, local path, hash, and preferred version.
7. Update paper relations, the field overview, and the open-problem portfolio.
8. Citation integrity: every saved paper must include a stable source link (DOI, arXiv, or permanent URL); a paper without a verifiable link is not registered. Never invent a paper or a conclusion attributed to it.

Do not treat a title, abstract, or secondary summary as the exact statement of a theorem.

### Divergent search contract

Run each search cycle as a divergent pass: search wide, do not gatekeep.

- The search role records what is interesting, whose result it is, and where it came from; it does not decide admissibility. Correctness auditing belongs to the solving layer (`$rigorous-open-math-research`); never discard a candidate preemptively.
- Provenance honesty is the one hard constraint: every entry must be traceable to a real query result or source note, recorded as `query -> result -> locator`. Never fabricate a result, a statement, a locator, or a citation.
- Before a search cycle, check the project tool library, paper indexes, and knowledge base first, to avoid re-tracing indexed results.
- Layer the pipeline: keyword families (synonyms, notation variants, older vocabulary); arXiv/OpenAlex/zbMATH for surveys and provenance; general web (textbooks, lecture notes, blogs, MathOverflow/MSE, journal pages, GitHub) for constructions, counterexamples, and numerical evidence not in papers; then deep-read promising hits to extract the exact statement, preconditions, and a locator.
- Store original sources immutably (hash-addressed when feasible) and keep compiled knowledge in indexed records; record complete analyses, partial proofs, and obstructions as first-class knowledge cards with source links. Prior partial progress and ruled-out paths are part of the knowledge base.
- Record the retrieval evidence contract for every search cycle: each entry carries a fetch status (`fetched-verified` | `abstract-only` | `paywalled` | `unreachable`), and the cycle separates `uncertainty` (epistemic doubt about a fact: conflicts, likely-outdated numbers) from `warnings` (how the retrieval was produced: engine fallback, degraded stand-in). An abstract-level hit is never registered as settling a theorem. (Distilled from modsearch: https://github.com/liustack/modsearch, argo: https://github.com/taxueseek/argo.)
- Query the local read-literature index before external search: pull bounded evidence fragments (explicit character/passage budgets) and cite section names or record IDs, never bare line numbers. Reuse prior search-log keys so an already-answered question is not re-traced from scratch. (Distilled from dsh-zotero: https://github.com/Vncntvx/dsh-zotero, dsh-kb-sieve: https://github.com/omdsh-dev/dsh-kb-sieve, dsh-web-search-pro: https://github.com/anweat/dsh-web-search-pro.)


## 4. Analyze important papers

For a paper important enough to affect the program:

1. Verify the exact source and version.
2. Create a structured TeX analysis using `assets/paper-analysis.template.tex` and `references/literature-and-paper-analysis.md`.
3. Record theorem locations, proof architecture, hypotheses and where they enter, key techniques, limitations, relations to earlier and later work, and plausible generalizations.
4. Extract candidate reusable tools into the tool library with explicit provenance and maturity.
5. Update the paper map and relevant problem records.

A paper analysis is a navigation artifact, not an authoritative proof premise. When a theorem from the paper will be used in a concrete proof, include the original source and the analysis in the task packet and require `$rigorous-open-math-research` to recheck its exact statement and hypotheses.

## 5. Maintain the program portfolio

Maintain project-level records for:

- research directions and their rationale;
- papers and version relationships;
- open problems and source formulations;
- dependencies among directions, papers, tools, and problems;
- management priority, expected leverage, novelty risk, and verification cost;
- unresolved bibliographic questions and missing sources.

Portfolio problem records carry a one-line evidence status (`OPEN` / `PARTIAL` / `NUMERICAL_EVIDENCE` / `PROVED` / `FORMALIZED`) and the research state (contract frozen? obligations open?) without duplicating upstream obligation graphs. Every material progress item is registered: partial results, structural theorems, failed routes with precise failure mechanisms, and new reusable tools all become first-class records (problem record, route/tool index, knowledge card, or formalization progress). Nothing that changes the problem state is left only in a chat transcript. Maintain a reusable counterexample library and a failure-synthesis record: common stuck points across failed plans are summarized and used to design the next generation of plans. When a newer, more advanced result covers an earlier partial/scaffold result, mark the earlier record as `superseded` with a pointer to the newer result; keep the history, but never present the superseded record as the current state.

Tool-library and portfolio evolution follows a marginal-benefit rule: a new tool entry or priority change is adopted when it resolves a known blocker, raises an evidence level, or reduces retrieval cost; record the marginal benefit in the maintenance log. Tool entries carry artifact provenance: the producing run/command, inputs, environment, source hash, and an append-only verification note (what was checked, at which precision, and by whom); a tool entry without provenance is a lead, not a reusable tool. (Distilled from dsh-science: https://github.com/biociao/dsh-science.) Promotion and retirement triggers: a technique enters the library only after repeated confirmed use (e.g. three successful applications) or one machine-verified proof; an anti-pattern is retired after two confirmed failures with recorded mechanisms. (Distilled from dsh-task-planner: https://github.com/ztl34245881-commits/dsh-task-planner.)

Project priority scores are planning aids, not mathematical evidence. Keep their rationale visible.

## 6. Build a task packet

Before delegating a concrete problem, create one task packet containing:

- the authoritative source wording or source location;
- the project reason for studying it now;
- relevant paper IDs, exact source versions, and file paths;
- relevant tool entries as leads, never as automatically trusted premises;
- known ambiguities and bibliographic risks;
- user constraints, available tools, and the research budget for this run;
- the requested run root and expected upstream artifacts;
- a `## Novelty preflight (B0)` section (openness verdict, audit path or
  explicit skip, snapshot hash) - the workflow stage B0 fills or audits it,
  and the deterministic gate (`validate_pipeline.py`) refuses to dispatch a
  solver without it.

Do not add a theorem contract, obligation graph, route plan, candidate proof, or audit rubric to the packet.

## 7. Delegate concrete mathematics

Invoke:

```text
Use $rigorous-open-math-research on the concrete problem in TASK_PACKET_PATH.
Treat the task packet as project context, not as a verified theorem contract.
Rebuild and audit the exact problem statement and recheck every cited theorem against its original source.
Write the standard upstream artifacts under RUN_ROOT.
Return the upstream result status and artifact locations without changing its protocol.
```

The manager may specify project constraints and file locations. It must not prescribe a substitute proof workflow.

## 8. Ingest an upstream run

After `$rigorous-open-math-research` returns:

1. Record the run ID, task ID, timestamps, upstream status label verbatim, run root, artifact paths, hashes, and tool versions when available.
2. Link to upstream files; do not copy their contents into project-level replacements.
3. Update the problem portfolio's management state and next action without re-auditing the proof.
4. Promote only explicitly supported, reusable knowledge into the tool library, with a precise pointer to the upstream proof or audit.
5. Record rigorous intermediate results, exact failure mechanisms, remaining gaps, and follow-up dependencies at project level.

5b. When an upstream audit reports gaps, record the first-error location and the error layer (statement / proof / dependency / boundary-convention) so follow-ups route to the smallest responsible owner.
6. Update maps, indexes, budget accounting, `state/RESUME.md`, and the checkpoint.
7. Register formalization progress: every new result (including partial/structural ones) must have a Lean scaffold in `lean-proof/` and an updated entry in `lean-proof/STATUS.md` / `lean-proof/README.md`; record the scaffold path and hash in the run record and `formalization_progress.md`.

If an upstream artifact is missing or its status is unclear, record that fact. Do not infer success.

## 8b. Ingest accepted knowledge into the canonical knowledge base

When the user authorizes acceptance and an upstream run produced reusable knowledge, promote it through the accepted-knowledge pipeline instead of ad-hoc copying:

1. Classify the knowledge with one epistemic type: generic roles (`basic_assumption`, `definition_contract`, `theory_from_assumptions`, `numerical_method`, `numerical_result`, `numerical_experiment_design`, `theory_from_numerics`, `superseded`) plus mathematics roles (`problem_hypothesis`, `external_mathematical_result`, `mathematical_claim`, `mathematical_inference`, `verified_counterexample`, `research_goal`, `proof_obligation`, `research_attempt`). Claims carry a `truth_status`; inferences carry a `proof_status`. Only `proved` inferences propagate conclusions.
2. Freeze the candidate as `knowledge/submissions/<SUBMISSION_ID>/proposal.json` with exact base snapshot hashes and complete write/read sets. A basic assumption must carry exact literature sources, stable identifiers, locators, and a consensus explanation. A proved inference must bind a content-hashed proof package with `unresolved_obligations: []`; a refutation binds a refutation package; a verified counterexample binds a certificate. Never invent a citation or a conclusion.
3. Validate deterministically with `python knowledge/tools/receive_blueprint.py --blueprint-root knowledge --submission submissions/<SUBMISSION_ID> --validate-only --actor-agent-id <AGENT_ID>`. Never send a proposal to review unless `valid` is true.
4. Have an independent reviewer (reviewer ID must differ from the author) write an immutable `review.json` that binds the proposal and validation hashes. Acceptance review checks evidence completeness, classification, hash binding, and mathematics coverage only; it does not re-audit the proof. A proof approval must record passing definition, logic, boundary, and adversarial audits bound to the exact proof-package hash.
5. Integrate only through the deterministic receiver with `python knowledge/tools/receive_blueprint.py --blueprint-root knowledge --submission submissions/<SUBMISSION_ID> --integrator-agent-id <AGENT_ID>`. Never edit `knowledge/blueprint.json` or `knowledge/evidence_inventory.csv` by hand.
6. Record the resulting snapshot hashes from `python knowledge/tools/blueprint_query.py snapshot` in the checkpoint and `state/current.json`. For mathematics, verify the post-merge state with `python knowledge/tools/blueprint_query.py math-closure --context <CONTEXT_ID>`; keep transaction status separate from research status.
7. Mirror the epistemic class into the paper record, tool entry, or project result record, and link the receipt path. Bind future task packets and research sub-agents to the snapshot; on `SNAPSHOT_MISMATCH`, discard accumulated retrieval and re-fetch. A merged partial lemma is `transaction_status: merged` with `research_status: partial_progress`, never `solved`.
8. **Evidence boundary.** Chat output, plain stdout, and interactive-terminal output never become formal evidence by themselves; only artifacts of a controlled run (hash-bound inputs, frozen environment) that pass independent review may be promoted. Formal computations should bind an immutable code/data snapshot and a fixed execution environment; a claim resting on an uncontrolled run is not accepted knowledge. (Distilled from dsh-scholar: https://github.com/lzszq/dsh-scholar.)

Full contracts and CLI details are in `references/accepted-knowledge-pipeline.md`.

## 8c. Deliver human-readable proofs as arXiv-style LaTeX (papers/)

Every theorem whose run passes Lean verification (machine verdict
`FORMALLY_VERIFIED` with `build_passed: true` and zero sorry/axiom hits) must
also be delivered as a human-readable LaTeX proof document under `papers/`,
so people can read and check the result without touching the Lean code. This
is a mandatory delivery for formally verified results, not an optional extra.

1. **Location and naming.** One folder per result: `papers/<SLUG>/` holding
   `<SLUG>-en.tex` (English, the arXiv-style version) and `<SLUG>-zh.tex`
   (Chinese companion). Compiled PDFs may sit next to the sources or under
   `papers/<SLUG>/build/`. `<SLUG>` is the stable result slug used in the
   indexes.
2. **arXiv-style conventions (English version).** Use `\documentclass{amsart}`
   (the arXiv-recommended class) with `amsthm`, `amsmath`, and `hyperref`;
   include a title, author, date, abstract, numbered theorem/lemma/proof
   environments, and a references list in which every cited paper carries a
   stable DOI or arXiv link. Compile with `xelatex` (or `latexmk`) to zero
   warnings when a toolchain is available, and record the compile result in
   the checkpoint. The template is `assets/proof-paper.template.tex`.
3. **Machine-verification binding.** The header or first section must state
   the formalization contract: Lean file paths, the verified statement, the
   verification commit hash, `lake build` success, and zero sorry/axiom hits.
   The LaTeX statement must match the formalized statement; the prose proof
   is a human re-derivation, never a replacement for the machine check, and
   must not assert anything the machine-checked statement does not imply.
4. **Evidence discipline.** Keep the STRICT vs EVIDENCE label discipline in
   the document. Anything not machine-verified (numerical checks, conjectures,
   open problems) must be explicitly labeled (`STRICT`, `EVIDENCE`, `猜想`,
   `开放`) and never presented as proved.
5. **Bilingual parity.** The Chinese version states the same theorems, proof
   structure, and references as the English version; it may add explanatory
   prose but must not change the statement or the proof obligations.
6. **Registration.** Record the `papers/` paths and the source-tex hashes in
   the run record, the artifact index, and (when the accepted-knowledge
   pipeline is used) the receipt.

## 8d. Formalization scaffolding on every new result

Every new result - even a `RIGOROUS_PARTIAL_RESULT`, a structural theorem, a
counterexample, or a useful reduction - must receive a Lean scaffold when the
project has a `lean-proof/` directory. This is the project-level counterpart of
the solver rule in `$rigorous-open-math-research` Phase 10.

1. **Create the scaffold.** Write a `.lean` file under `lean-proof/SL/` that
   states the new declaration(s) and open proof obligations. Unfinished proof
   blocks are marked with `sorry` and a header comment:
   `-- SCAFFOLD: <slug> <status> <open obligations>`.
2. **Register it.** Add/update the row in `lean-proof/STATUS.md` and
   `lean-proof/README.md` with status `SCAFFOLD` (not `FORMALLY_VERIFIED`),
   and record the scaffold path + sha256 in the run record and
   `formalization_progress.md`.
3. **Do not claim verification.** A scaffold is a machine-readable statement of
   intent, not a verified artifact. It must never be reported as
   `FORMALLY_VERIFIED`; only a full `lean-verify` pass may upgrade it.
4. **Keep it current.** After each subsequent result or repair, update the
   scaffold and the formalization progress immediately, so the problem's
   formalization state never lags behind the research state.
5. **Intermediate verification.** Machine-check load-bearing intermediate
   lemmas as they appear; a verified intermediate result is a valid checkpoint
   and helps avoid re-running failed routes.
6. **Supersession.** When a newer result covers an older scaffold/partial
   result, mark the older entry `superseded` in `lean-proof/STATUS.md` and the
   formalization progress, with a pointer to the newer result. Keep history;
   do not delete it.
7. **Use automation.** Generate scaffolds and records with
   `scripts/scaffold_result.py` (creates the `.lean` scaffold, updates
   `STATUS.md`, `formalization_progress.md`, and `proof-submission-audit.md`).
   Regenerate the reuse index with `scripts/index_lean_lemmas.py` after adding
   or changing Lean files.

## 8e. Proof submission audit pipeline (mandatory)

Any proof document submitted for acceptance into the repository - Lean file,
LaTeX proof, candidate proof, or scaffold - must pass the following three-stage
audit before it is added. Use `assets/proof-submission-audit.template.md` as
the record.

### Stage 1: Repository comparison

Before running any verification, compare the submission with the current
repository state:

1. Search existing results in `docs/`, `runs/`, `lean-proof/STATUS.md`,
   `tools/`, `knowledge/`, and `papers/` for the same statement, hypotheses,
   boundary cases, or proof technique.
2. Record a comparison table: each existing result ID/path, whether it is
   duplicate, superseded, contradictory, or unrelated.
3. If the submission is a duplicate or is covered by an existing result, do
   not re-add it; either reject or route to a supersession update.
4. If the submission contradicts an existing result, record the conflict
   explicitly and stop; a contradiction requires a resolution before any
   repository change.
5. Check the reusable counterexample library and failure-synthesis records:
   if the submission is already refuted or blocked by a recorded
   counterexample/failure, reject or route to a revised attempt instead of
   re-running the same path.

### Stage 2: Lean verification and audit

Run the verification pipeline on the submitted proof:

1. If Lean files are submitted, invoke `$lean-verify`:
   - pin environment; `lake build`; sorry/admit/axiom scan;
   - statement fidelity audit;
   - independent audit by an auditor different from the submitter.
2. Use the cheapest verification tier that answers the question:
   - Tier 0: scaffold/statement skeleton compiles;
   - Tier 1: load-bearing lemma machine-checked;
   - Tier 2: full `FORMALLY_VERIFIED`.
3. Before accepting a new lemma, check `lean-proof/LEMMA_INDEX.md` (or run
   `scripts/index_lean_lemmas.py`) to reuse existing formalizations instead of
   re-proving them.
4. If only an informal proof (LaTeX/markdown) is submitted:
   - a completion claim (`已证` / `CANDIDATE_COMPLETE_PROOF` /
     `FORMALLY_VERIFIED`) requires a Lean formalization (full verification);
   - a partial/structural result requires a Lean scaffold (workflow 8d).
5. Record the machine verdict, fidelity results, critical errors, gaps, and
   repair hints in the submission audit record.

### Stage 3: Add by rules

Only after Stage 1 and Stage 2 pass (or pass with explicit scaffold status):

1. Update `lean-proof/STATUS.md`, `lean-proof/README.md`, and
   `formalization_progress.md`.
2. Update `index/`, `state/current.json`, `state/RESUME.md`.
3. If the result is formally verified, add the human-readable LaTeX proof to
   `papers/` (workflow 8c).
4. If a new reusable method/tool appeared, add it to `tools/` with provenance.
5. Mark any older result that this submission covers as `superseded`, with a
   pointer to the new submission; keep history.
6. Record the audit decision (`ACCEPT` / `ACCEPT_AS_SCAFFOLD` / `REJECT` /
   `REVISE_AND_RESUBMIT`), commit, and sync remotes.

## 9. Checkpoint and close a stage

After every substantial literature batch, paper analysis, delegation, or ingestion:

- append an evidence-backed activity record;
- update `state/current.json` and `state/RESUME.md`;
- write a checkpoint with completed work, active items, blockers, and exact next commands or files;
- run `python scripts/validate_project.py PROJECT_ROOT` when available.
- commit and push the stage: update `AGENTS.md` session records first, then `git add -A`, `git commit -m "<stage summary>"`, and `git push` (see `references/git-sync.md` for the proxy bypass); verify `git status` shows a clean tree in sync with the remote.

At a stage boundary, write a project-level summary using `assets/stage-summary.template.md`. Preserve upstream result labels verbatim and link their independent proof and audit documents when present. If no proof was obtained, preserve the strongest rigorous intermediate results, failed mechanisms, and exact remaining gaps. When a run is interrupted, require the workflow handoff record to be independent and to include completed work progress plus tools/methods tried (see `$math-research-workflow` interruption handoff protocol); the manager registers its path and hash.

### Fresh-context convergence check

Before closing a stage, rebuild the program state from files only (indexes, `state/current.json`, `state/RESUME.md`, checkpoints, and the latest stage summaries) without conversational history, and answer whether the program is converging or diverging. File follow-up items without rewriting artifacts; record the check in the activity log.

# Evidence and provenance rules

1. Date every literature-status claim and identify the searched sources.
2. Store original sources or stable source references; do not rely on memory as project evidence.
3. Distinguish a paper work from its versions, corrections, and published form.
4. Do not fabricate searches, access to paywalled databases, elapsed research time, hashes, or files.
5. The tool library is an indexed retrieval aid. Concrete proof use still requires upstream source verification.
6. Preserve upstream result labels and audit findings; never silently upgrade them.
7. Prefer one canonical record with aliases and version links over duplicate copies.
8. Every cited or registered paper must carry a stable verifiable link (DOI, arXiv, or permanent URL). Never fabricate a paper, a citation, a theorem, or a conclusion; any statement about what a paper proves must be checked against the actual source and version.
9. Classify reusable knowledge with the accepted epistemic taxonomy (generic roles plus `problem_hypothesis`, `external_mathematical_result`, `mathematical_claim`, `mathematical_inference`, `verified_counterexample`, `research_goal`, `proof_obligation`, and `research_attempt`) and record the class in paper records, tool entries, and result records.
10. The canonical accepted-knowledge base changes only through the deterministic receiver. Never edit `knowledge/blueprint.json`, `knowledge/evidence_inventory.csv`, or any submission artifact by hand.
11. Bind task packets and research sub-agents to a knowledge snapshot hash. A snapshot mismatch invalidates all accumulated retrieval.
12. Keep transaction status separate from research status. A merged partial lemma means the record was accepted, not that the goal is solved; report `research_status` such as `partial_progress` until the target belongs to the post-merge trusted closure.
13. Every Lean-verified theorem must ship a human-readable LaTeX proof under `papers/` (English arXiv-style version + Chinese companion) bound to the machine verification as described in workflow 8c; no formally verified result is complete without it.
14. Every new result (including partial/structural ones) must be registered in the problem/route/tool records and must have a Lean scaffold + formalization-progress update when a `lean-proof/` project exists; a result without registration or scaffold is not considered fully ingested.
15. No proof document is added to the repository without passing the proof submission audit pipeline (workflow 8e): repository comparison, Lean verification/audit, then rule-based integration. The audit record must be kept with the submission.

# Project-level completion

A program-management stage is complete when:

- the requested corpus or project scope has been indexed;
- important sources and versions are traceable;
- paper, problem, tool, task, run, and artifact indexes are internally consistent;
- the current state and recovery entry are current;
- every concrete mathematical task is either delegated, queued, or explicitly out of scope;
- upstream results are linked and represented without changing their status;
- every formally verified theorem has its `papers/` LaTeX delivery (English + Chinese versions, bound to the machine verification);
- the accepted-knowledge base (when present) is consistent and its latest snapshot is recorded;
- the project repository is committed and synchronized with its remote;
- the stage summary states what changed, what remains, and what should happen next.

This completion criterion says nothing about whether any underlying open problem is solved.

## Changelog

Changelog history (upstream entries and DSH adaptation entries) lives in
`references/upstream-changelog.md`, kept out of the skill body to keep DSH
skill loads light.

