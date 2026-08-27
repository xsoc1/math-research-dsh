---
name: math-research-workflow
description: >-
  Orchestrate the full mathematics research pipeline: program management
  (manage-math-research-program) to rigorous problem research
  (rigorous-open-math-research) to Lean formal verification (lean-verify),
  with sub-agent division of labor, artifact handoff contracts, hash binding,
  and automatic git sync at every stage boundary. Use when the user asks to
  run or manage a complete research+verification workflow for a mathematics
  project, to iterate the three-skill pipeline, or to coordinate parallel
  solve/audit/formalize agents. 中文触发: 数学项目全流程一体化 (管理-研究-验证),
  三个 skill 协同工作流, 研究+Lean 形式化验证流水线, 子 agent 分工优化.
---

## DSH runtime notes (DSH adaptation)

This bundle is the DSH adaptation of the Codex plugin `math-research-workflow`.
In this runtime, every reference written as `$skill-name` means: load the skill
named `skill-name` with the `skill` tool using its exact name (a user message
whose first line is `/skill-name` also loads it). The sibling skills ship beside
this bundle under the same skill roots.

- `scripts/validate_pipeline.py` and the `assets/` templates live inside this
  bundle; run them with a local Python interpreter via the shell using the
  `resourceBase` directory path reported by the skill load result, with
  `PYTHONUTF8=1` on Windows. Prefer writing a temporary .py file over PowerShell
  one-line `-c` calls.
- The DSH environment preflight is `scripts/dsh-doctor.py` in the
  `math-research-dsh` repository checkout (when installed by the repository
  `install.ps1`, the checkout lives at `$DSH_HOME/math-research-dsh`).
- The DSH adaptation keeps every upstream file byte-identical except this block,
  the DSH changelog append, and the doctor-related passages rewritten for DSH;
  the synced upstream commit is recorded in the repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Stage dispatches use the DSH delegation tools: fresh `subagent` (spawn) for
  solver/audit/formalizer/verifier roles so audit and verify share no chain of
  thought with the solver; `subagent_fork` for continuation with full history.
- Batch packets fan out through the `workflow` tool with
  assets/dsh-solve-audit-workflow.js (solve + audit in parallel per packet,
  then verify only qualified results).
- `lake build` and long gate runs execute as background shell jobs, collected
  with job_output.
- Long outputs run through the repository wrapper scripts/dsh_run.py so the
  verdict and FAIL lines survive DSH result truncation (full log on disk).
- Full details: references/dsh-execution.md in this bundle.

# Math Research Workflow (管理-研究-验证一体化流水线)

## Purpose

This skill is the **orchestration layer** for the three-skill pipeline. It
sequences, delegates, and hands off work between:

- `$manage-math-research-program` -- program context, task packets, tool
  library, accepted knowledge, git sync (stage A);
- `$rigorous-open-math-research` -- theorem contracts, routes, adversarial
  proof audit, candidate proofs (stage B);
- `$lean-verify` -- Lean 4 formalization, machine checks, obligation-level
  audit, structured verdicts (stage C).

It never re-implements any of their workflows. Its only job is to decide
**what** runs **when**, **by whom** (sub-agents), and to enforce the **handoff
contract** between stages.

## Dependency direction

```text
math-research-workflow -> manage-math-research-program -> rigorous-open-math-research
math-research-workflow -> lean-verify
```

No reverse calls. Each referenced skill keeps its own hard boundaries (see
`manage-math-research-program` "Hard non-overlap rule").

## Trigger boundary

Use this skill when the user asks to:

- run a complete research program end to end (manage -> solve -> verify);
- formalize a batch of already-proved results into Lean and verify them;
- coordinate several sub-agents (solve / audit / formalize / verify) on one
  project with a shared task packet;
- sync a mathematics project repository (git) across research sessions;
- resume or checkpoint a multi-stage research pipeline.

Do **not** use this skill for a single proof request (use
`$rigorous-open-math-research`), a single formalization audit (use
`$lean-verify`), or project bookkeeping only (use
`$manage-math-research-program`).

## Pipeline protocol

### Stage A -- Program (manager)

1. Read the project entry point (`AGENTS.md` if present), `lean-proof/STATUS.md`
   (formalization matrix) and the program index produced by
   `manage-math-research-program`.
2. Run the DSH environment preflight (`scripts/dsh-doctor.py` in the
   math-research-dsh repository checkout, installed under
   `$DSH_HOME/math-research-dsh`). On a hard `FAIL`, apply the printed repair
   command before any dispatch. It verifies that all four skill bundles are
   mounted under the DSH skill roots (`$DSH_HOME/skills` or the project
   `.dsh/skills`), that a Python interpreter is available, and that the Lean
   toolchain exists when stage C is planned.
3. Run the git-sync check (manage skill section 0): record dirty files,
   ahead/behind, current commit hash.
4. Run the deterministic pipeline gate shipped with this plugin
   (`scripts/validate_pipeline.py --project .`). Fix every hard `FAIL` before
   dispatch; treat `warn:` lines as advisory notes to record, not as blockers.
5. For each task: build or refresh the **task packet** (contract, source
   documents, obligations, verification criteria, hashes) and delegate.

**Stage B0 -- Openness and novelty preflight (mandatory before dispatch):**

Before any solver is dispatched, every concrete problem in the packet must
carry a completed novelty preflight (recorded in the packet's
`## Novelty preflight` section):

1. **Openness check** (per `$rigorous-open-math-research` Phase 0/1): verify
   whether the problem is genuinely open as of the research date, unless the
   user explicitly requested a blind benchmark phase. Record the checked date
   and the sources consulted.
2. **Novelty audit**: run the divergent search contract (keyword families ->
   project KB/tool library -> arXiv/OpenAlex/zbMATH -> general web), then
   deep-read promising hits. Write/refresh the run's
   `status_and_literature.md` with exact known theorems, citations recorded
   as `query -> result -> locator`, and a novelty-risk line. Never fabricate
   a paper, statement, or locator; abstract-only or paywalled evidence is
   recorded as such and never promoted to theorem level.
3. **Snapshot backfill**: ingest the audit conclusions into the manage
   skill's literature frontier (paper records with stable links, portfolio
   `novelty risk` field, evidence status) and bind them to the current
   knowledge snapshot hash. On `SNAPSHOT_MISMATCH`, discard accumulated
   retrieval and re-fetch before dispatch.
4. **Gate**: a solver is dispatched only when the packet carries the
   openness verdict, the audit path (or an explicit `skip:` record such as
   `blind_benchmark` / `search_forbidden` with a scheduled post-discovery
   audit), and the snapshot hash. A missing preflight is a hard `FAIL` at
   the A -> B boundary (enforced by `validate_pipeline.py`).

### Stage B -- Research (solver)

For every concrete problem in the packet, invoke `$rigorous-open-math-research`
with the exact contract. Its run artifacts (`problem_contract.md`,
`candidate_proof.md`, `audit_report.md`, `reproducibility/`, ...) are produced
in a per-run directory and ingested by reference (never rewritten by the
manager). For a single scoped target, Stage B follows the rigorous skill's
closure-first protocol before route expansion or Worker dispatch.

**Sub-agent division (efficiency):**

- **Solver agent**: runs the closure-first direct attempt, then builds routes only after a
  recorded escalation decision; derives and records ledger entries.
- **Adversarial audit agent**: independently re-derives each obligation and
  attacks the candidate proof; reports F-xxx findings.
- The two alternate in bounded loops until either `CANDIDATE_COMPLETE_PROOF`
  or an exact gap report is reached. The audit agent never shares a chain of
  thought with the solver; only artifacts are exchanged.
- **Claim before work.** Every obligation is claimed by exactly one worker at
  a time: the ledger records the owner before solving starts and releases the
  claim on completion, so two agents never prove the same obligation. A
  re-claim requires the previous owner's result or an explicit release.
  (Distilled from dsh-suite plugin-team-board:
  https://github.com/whyihaveyou/dsh-suite/tree/main/packages/plugins/plugin-team-board.)

**OpenProver-style solve loop (distilled, mandatory for stage B runs):**

The solve loop follows the Planner-Worker-Verifier pattern: a single
solve-run lead (Planner role) keeps a compact memory and decomposes work into
independent Workers whose outputs are reviewed by an independent Verifier.
This is a refined form of the solver/audit alternation above; it does not
replace the theorem contract, B0 gate, or evidence discipline.

0. **Closure-first gate.** Before `spawn`, the Planner writes the shortest
   target dependency chain, directly attacks the first open load-bearing
   claim, and runs the cheapest decisive falsification probe. Worker dispatch
   starts only when the gate records the exact decision it can change. Use
   `$rigorous-open-math-research`
   `references/closure-first-protocol.md` and its closure-gate template.

1. **Whiteboard memory (mandatory).** Every stage B run keeps
   `runs/<skill>/<run_id>/whiteboard.md` (template
   `assets/whiteboard.template.md`). It holds the current plan, the route
   history with `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]` outcome markers, deferred
   ideas, open obligations, and the key-artifact index (slug + one-line
   summary + sha256). The solve-run lead rewrites it after every planner step
   and reads it at every step; old plans are replaced, not appended. The
   interruption handoff is a frozen snapshot of this record plus recovery
   context. The stage gate hard-requires the whiteboard for runs started on or
   after 2026-08-14 and validates its fields and sections.
2. **Independent Workers after the spawn gate.** A Worker explores exactly one
   deliverable: a proof direction, a lemma, a counterexample search, a
   simplified variant, or a formalization task. A Worker does not observe the
   reasoning traces of other Workers or the Planner's chain of thought; only
   the whiteboard plan and the repository slugs are shared. This keeps
   distinct attempts genuinely independent and prevents one fashionable but
   flawed line of thought from contaminating the portfolio.
3. **Independent Verifier feedback.** Every Worker output proposed as a
   load-bearing dependency or reusable result is reviewed by the adversarial
   audit agent without access to the Worker's reasoning trace. Empty,
   duplicate, or no-`decision_delta` returns are rejected by the Planner
   without buying a separate global review. The Verifier returns structured
   feedback (verdict + critical errors + gaps + repair hints); the Planner
   decides continue / repair / branch / block / refute / archive. Feedback is
   an artifact, never an approval chain of thought.
4. **Repository with verified-items-only rule.** Every intermediate item
   lives in the run directory and is addressed by slug (relative path); the
   whiteboard keeps only slugs plus one-line summaries. A **Lean item is
   stored only if it passes machine verification**; otherwise the verifier's
   errors and warnings are fed back to the responsible Worker, giving tighter
   feedback than a final-answer check.
5. **Lean real-time verification loop (worker tools).** Workers may call
   three Lean tools (mechanics delegated to `$lean-verify`):
   - `lean_verify <snippet>` -- verify a Lean snippet and return the exact
     errors/warnings; never store an unverified snippet as a repository item.
   - `lean_search <query>` -- semantic search over Mathlib declarations
     (LeanExplore, arXiv:2506.11085) before re-proving a known lemma; record
     hits with their source and never fabricate a declaration name.
   - `lean_store <snippet>` -- append an already-verified snippet (imports,
     namespace openings, definitions, proven sub-lemmas) to
     `runs/<run_id>/lean_scratch/context.lean`, which is prepended to later
     `lean_verify` calls in that run.
5b. **Intermediate Lean checkpoints (mandatory).** When a Worker produces a
   load-bearing lemma, a structural claim, or a reusable reduction, run
   `lean_verify` on that snippet before letting the route depend on it. A
   machine-checked intermediate result is a checkpoint: it catches errors
   early, prevents a route from silently building on a false step, and gives
   the next agent a verified stepping stone even if the final theorem is still
   open.
6. **Loop control.** The Planner iterates: direct attempt -> optional Worker dispatch -> collect outputs ->
   independent review -> update whiteboard and repository -> next plan step,
   until `CANDIDATE_COMPLETE_PROOF`, an exact gap report, or the compute
   budget runs out. Do not use fixed worker counts as a principle; allocate
   dynamically by marginal information gain.
   **Gap re-injection (mandatory):** every non-pass review output must be
   consumed by a revision round or recorded as a routed obligation; a
   finding that is silently dropped is a gate failure. (Distilled from
   dsh-proof: https://github.com/EvilIrving/dsh-proof.)
7. **Interactive steering.** When the user is in the loop, present each plan
   or action set before executing it, allow the user to redirect Workers,
   interrupt unpromising routes, and accept or reject the next actions with
   feedback. In autonomous mode skip the prompts but keep everything else.

**Cost-tiered escalation (light first):** before opening parallel Workers or
any Tier 3 machinery, the Planner runs the cheapest admissible probes (Tier 0:
existing artifacts/tool library/small cases; Tier 1: specialization, weakening,
instantiation, local patch). Rank candidate actions by expected information
gain per unit cost, and record the current tier plus the last escalation
reason in the whiteboard. Escalate to Tier 2/3 only on a recorded zero-gain
witness, a counterexample or obstruction that requires a heavier mechanism, a
load-bearing gap that machine checking can close faster, or an explicit user
request. Difficulty alone is not a spawn trigger. The first Worker wave is the
smallest set that can change the closure decision, and every further wave
requires a durable `decision_delta`. See
`$rigorous-open-math-research` `references/escalation-ladder.md`.

**Lightweight reuse protocol (mandatory default):** before major derivation,
run a compact pre-scan over `research_map.md`, `tools/README.md` plus relevant
tool summaries, `lean-proof/LEMMA_INDEX.md`, and the latest relevant
`final_report.md` / handoff. Do not require per-route REUSE tags. At run close,
write `reuse_summary.md` with actual reused items, duplicate work avoided,
remaining duplicate work, new methods, and a one-line cost assessment. Every
material run must also meet the minimum artifact checklist. Full details:
`references/reuse-protocol.md`.

**Performance observability and user alerts:** when performance metrics are
available, compare the run against a comparable baseline with
`scripts/performance_alert.py`. If a cost metric increases materially without
a compensating improvement in output/artifacts/reuse, write
`performance_alert.md` (template `assets/performance-alert.template.md`), add a
short "Performance alert" section to `final_report.md`, and surface it to the
user as a candidate regression. Alerts are candidates, not verdicts: a single
run can be misleading, so require a repeat run or a different-class baseline
before drawing a conclusion. Full protocol:
`references/performance-observability.md`.

**Failure synthesis and counterexample reuse (distilled from Rethlas):**
when a batch of plans/routes fails, synthesize the common stuck points into a
`key_failures_summary`, store it in the whiteboard/ledger, and use it to propose
the next generation of plans. Maintain a reusable counterexample library; before
attacking a fragile claim, query stored counterexamples first. Search is a
support tool, not a substitute for deep reasoning: when retrieval stops being
useful, continue with non-search skills and record why the results were not
useful.

**Research map (mandatory):** every project keeps a human-readable
`research_map.md` (see `$manage-math-research-program` workflow 8f and
`assets/research-map.template.md`). It records every route/method tried,
intermediate results, unexpected findings, failures and reasons, tools, open
directions, an avoid list, and human/other-agent contributions. Update it at
every stage boundary and after every material step (worker round, failed route,
verified fact, discovery, budget pause). Before a long deep-dive into a small
sub-branch, re-read the map's routes/avoid list to avoid rabbit-holing;
human/AI-supplied routes are merged as leads to verify.

**Token-conscious Planner/repo/budget protocol (distilled from OpenProver):**
follow `references/openprover-absorption.md`. In short:

- Planner steps emit a compact decision summary + machine-readable action list
  (`spawn`, `read_items`, `write_items`, `read_theorem`, `write_whiteboard`,
  `submit_proof`, `submit_lean_proof`, `literature_search`).
- Long content lives in `runs/<run_id>/repo/`; the Planner sees only
  `repo_index.md` slugs and one-line summaries and reads items on demand.
- In Codex, locate relevant paths once with indexed search, read only the
  needed slices, and batch independent read-only lookups or deterministic
  checks in one programmable tool call when the runtime supports it. Keep
  theorem-contract changes, route selection, synthesis, and audit as explicit
  model-decision boundaries.
- Each task packet may include a `theorem.lean` skeleton with `sorry`; formalize
  from it after the informal proof is found.
- Planner steps are appended to `runs/<run_id>/planner_history.jsonl`; only the
  last 3–5 steps are fed to the model.
- At route boundaries or before context compaction, reconstruct from the
  whiteboard, repository index, and exact artifact paths instead of replaying
  the transcript. Record the current open obligations and next action first.
- Token budget is checked at safe boundaries. On exhaustion: persist
  whiteboard/repo/history/facts, write an interruption handoff, mark
  `PAUSED_BUDGET`, and resume later with an added budget. Budget exhaustion
  never deletes work.

**Numerical evidence discipline (hard rule):**

- Numerical computation is allowed for exploration, counterexample search, and
  corroboration only. It is never a delivery: a result may not be labeled
  `已证` / `CANDIDATE_COMPLETE_PROOF` / `FORMALLY_VERIFIED` on
  numerical evidence alone.
- Every deliverable that uses numerical labels must carry either a strict
  label (`严格证明` / `定理已证` / `STRICT` /
  `机器验证` / `形式化验证`) or an
  explicit downgrade statement (e.g. "evidence only", "does not constitute
  proof"). The stage gate (`validate_pipeline.py`) enforces this mechanically.
- If a solver starts substituting numerical evidence for proof, the audit
  agent must fail the run and report the exact missing obligations; the
  manager records the F-xxx finding and does not advance the packet.

### Stage C -- Verification (formalizer)

Every run with material progress - including partial results such as
`RIGOROUS_PARTIAL_RESULT` - must record a formalization decision and, when a
`lean-proof/` project exists, create a Lean scaffold for each new result. Full
Lean verification is still reserved for results labeled `已证` /
`CANDIDATE_COMPLETE_PROOF` that the user wants formalized.

Every run records its formalization decision in `run-manifest.json`
(`formalization: requested | not_requested | skipped | scaffold`): a skipped
lean-verify step must be a recorded decision, never a silent omission.

- `requested` -- the formalizer/verifier agents MUST run, and the run must
  reference the produced `lean-proof/run-manifest.json` in
  `formalization_manifest`; `lean-proof/verification.json` must exist with a
  clean machine verdict;
- `scaffold` -- a Lean scaffold file was created for the new result(s); the
  run must reference it in `formalization_manifest` (a `.lean` file or
  `formalization_progress.md`). Scaffolds are not verified artifacts and must
  not be reported as `FORMALLY_VERIFIED`;
- `skipped` -- requires a non-placeholder `formalization_reason` (for example
  a tool outage) and the re-verification obligation must stay open in the
  obligation graph;
- `not_requested` -- the user did not ask for formalization for this result
  (allowed only for runs without material progress or before the scaffold
  cutover).

The stage gate enforces all four mechanically: a run claiming a completion
label without a decision fails, and new runs (started on/after 2026-08-16)
with material progress must record `scaffold` or `requested`.

1. Create/update the Lean project (`lean-proof/`), map each obligation to a
   `.lean` declaration (obligation map O1..On).
2. **Formalizer agent** writes the Lean files; **verifier agent** runs
   `verify_lean_project.py --project . --build` (sorry/axiom scan + lake
   build) and refreshes `run-manifest.json`.
3. Write/extend `audit_report.md` (per-obligation fidelity) and
   `verification.json` (structured verdict), then update `STATUS.md` and
   `README.md`. Fix source-document errors found in the process in place and
   record them as F-xxx in the audit report (do not silently change sources).
4. Machine evidence required: build exit 0, zero sorry/admit/axiom hits,
   obligation map complete. No machine evidence => no "FORMALLY_VERIFIED".

**Scaffold path for partial results (mandatory since 2026-08-16):** when a run
closes with a partial/structural result (e.g. `RIGOROUS_PARTIAL_RESULT`), the
formalizer writes a Lean scaffold file under `lean-proof/` that states the new
declarations and open obligations, marks unfinished blocks with `sorry` and a
`-- SCAFFOLD` header, and updates `lean-proof/STATUS.md` /
`lean-proof/README.md` / `formalization_progress.md`. This is not full
verification and must never be labeled `FORMALLY_VERIFIED`.

**Intermediate verification is encouraged throughout Stage B/C**: verify
load-bearing lemmas as soon as they are stable, not only at the end. A
machine-checked intermediate lemma is a valid checkpoint that reduces detours.

**Verification tiers (use the cheapest sufficient one):**
- Tier 0: statement scaffold with `sorry`, compile skeleton.
- Tier 1: machine-check a load-bearing lemma with `lean_verify`.
- Tier 2: full `lake build` + zero sorry/axiom + independent audit
  (`FORMALLY_VERIFIED`). Full verification is reserved for completion labels.

**Dual-track audit:** every submission is checked on two tracks - the informal
(Danus-style) natural-language audit and the Lean formal track. Record both in
the verification matrix (see `references/dual-track-audit.md` in the rigorous
skill). Conflict rule: informal gaps trump a passing Lean check; Lean failures
trump a passing informal check; paper-level failures trump both.

**Lemma reuse index:** before proving a new lemma, check
`lean-proof/LEMMA_INDEX.md` (generated by
`scripts/index_lean_lemmas.py` in the manage skill). If the declaration
already exists, import/reuse it instead of re-proving; record the reuse in the
run ledger.

**Supersession:** when a newer, more advanced result covers an older
scaffold/partial/formalized result, mark the older entry `superseded` in
`lean-proof/STATUS.md`, `README.md`, and `formalization_progress.md`, with a
pointer to the superseding result. Keep the old files and history; never
present a superseded result as the current state.

**Lean escalation lane (proof-critical claims):** when a proof-critical
claim is load-bearing (the final status depends on it) and machine
verification is available, formalize that claim before the completion status
is claimed, not as a post-hoc audit: escalate the lemma into the Lean project
first, verify it, then claim the label. This is a prioritization rule - key
claims go through Lean early - not a replacement for the final stage gate.
(Distilled from dsh-rigorquant: https://github.com/linxichen/dsh-rigorquant.)

**Formalization feedback loop (mandatory):**

Formalization errors are feedback, not dead ends. On every Lean failure,
classify the error (statement / proof / dependency / boundary-convention),
then repair at the correct layer:

- If the flaw is in the Lean proof, repair the Lean file (statement freeze:
  a statement change is a new audit, not a repair) and re-verify.
- If the flaw is in the natural-language proof, route back to the solve-run
  lead: fix the candidate proof, re-audit the affected obligations, then
  re-formalize. Never silently patch a formalization around a real flaw in
  the source argument.
- Keep bounded loops (5-15 rounds per file by default), then report the exact
  obstacle instead of weakening the claim.

### Stage boundary checks (mandatory)

- A -> B: packet contains contract + source paths + obligation list; B0
  novelty preflight recorded (openness verdict + audit path or skip +
  snapshot hash); no open questions left unresolved; research map (`research_map.md`)
  initialized with problem/target.
- B -> C: full Lean verification is reserved for results with an honest
  completion label (`已证` / `CANDIDATE_COMPLETE_PROOF`); partial/structural
  results still enter Stage C in **scaffold mode** (create/update Lean scaffold
  + formalization progress). Numerical/猜想 results are excluded from full
  verification but, when they represent new material progress, still require a
  scaffold/registration per the 2026-08-16 rule. The research map is updated with
  all routes/findings/failures before leaving Stage B.
- C -> done: verification.json verdict, audit report, STATUS matrix updated;
  research map status updated; git synced; AGENTS.md session log appended.
- Every dispatch and every stage close re-runs
  `scripts/validate_pipeline.py`; a hard `FAIL` must not be left open at a
  stage boundary. Statuses outside the formalization gate are reported as
  warnings, never silently promoted.

### Proof submission audit (mandatory)

Any proof document submitted for acceptance into the repository goes through
the three-stage audit owned by `$manage-math-research-program` (workflow 8e):

1. **Repository comparison** - check against `docs/`, `runs/`,
   `lean-proof/STATUS.md`, `tools/`, `knowledge/`, `papers/` for duplicates,
   superseded results, or contradictions.
2. **Lean verification and audit** - `$lean-verify` machine checks + statement
   fidelity + independent audit; informal completion claims require full Lean
   formalization; partial/structural results require a Lean scaffold.
3. **Add by rules** - update `lean-proof/STATUS.md`, `README.md`,
   `formalization_progress.md`, indexes, `papers/`, `tools/`; mark superseded
   old results; record audit decision and sync remotes.

The submission audit record (`assets/proof-submission-audit.template.md` in
the manage skill) must accompany the submission and be committed with it.

### Interruption handoff and resume (mandatory)

When any stage stops before completion (budget exhausted, user requests a
stop, tool/environment failure, or any cross-session cut), the interrupting
agent writes an interruption handoff before returning control:

1. **Write the record**: use `assets/interruption-handoff.template.md`, saved
   as `runs/<skill>/<run_id>/handoff-interrupted-<UTC timestamp>.md`. This is
   an independent, self-contained document. Record the run ID, packet ID,
   date, interrupt reason, task state, **completed work progress** (what has
   been achieved and must not be redone), completed/open obligations,
   **tools and methods tried with outcome markers**
   (`[FAILED|BLOCKED|PARTIAL|SUCCEEDED]` plus the failure mechanism or partial
   progress), the exact next actions, and path + sha256 for every key
   artifact. Do not promote numerical evidence here: reuse upstream status
   labels verbatim.
2. **Register**: the manager records the handoff path and hash in the project
   index and appends a one-line session-log entry. Commit when the working
   tree allows it.
3. **Resume**: the successor agent starts by reading the latest handoff, then
   `research_ledger.md` (last entries first), then `approach_registry.md`,
   then the key artifacts, then the task packet. It continues only the listed
   next actions; re-running a `[FAILED]` route requires a new reason recorded
   in the handoff first.
4. **Gate**: `validate_pipeline.py` hard-fails handoffs that miss required
   fields/sections (run ID, packet ID, date, interrupt reason, task state,
   completed work progress, completed/open obligations, tools and methods
   tried, attempted routes, next actions), so a successor never resumes
   blind. Project-level recovery (`state/RESUME.md`, checkpoints) stays with
   the manage skill (stage A); this protocol covers run-level details from
   stages B and C.

## Efficiency rules

- Parallelize only after the closure-first spawn gate and where dependencies allow: stage B's audit agent may review
  obligations while the solver opens the next route; stage C's verifier may
  scan files as the formalizer writes them. When several members run in
  parallel, aggregate every member's failures into the report (first-fail
  short-circuit hides independent errors). (Distilled from
  dsh-agent-team-gui: https://github.com/toolclub/dsh-agent-team-gui.)
- Detect loops from the route/obligation history: re-attempting a failed
  route without a materially new mechanism is a loop, not progress; block it
  and record the witness. (Distilled from
  dsh-trajectory-governance: https://github.com/dfycaly98931680/dsh-trajectory-governance.)
- Reuse before redo: check the tool library (`tools/`), the accepted-knowledge
  base, and `STATUS.md` before starting a route or a formalization; hash-bound
  artifacts prevent duplicate work.
- One artifact per claim: never maintain two copies of a proof state; the
  manager records paths and hashes verbatim.
- Automatic git sync after every stage (manage skill section 0, generic
  remote-topology configuration). This plugin does not hard-code any fork
  layout; if `project.json` declares `git_sync.push_order`, sync every listed
  remote in that order (e.g. parent first, child fork second) and state the
  direction in the session log.

## Reference files

- `references/workflow-design.md` -- full design: roles, handoff schemas,
  parallelism, checklists, and failure handling.
- `assets/pipeline-handoff.template.md` -- normal stage-transition
  handoff record template.
- `assets/interruption-handoff.template.md` -- interrupted-work handoff
  template (routes tried, open obligations, next actions) for cross-session
  resume.
- `assets/whiteboard.template.md` -- compact Planner-memory whiteboard
  template (current plan, route history, deferred ideas, open obligations,
  artifact index) for the OpenProver-style solve loop.
- `scripts/validate_pipeline.py` -- deterministic task-packet, hash-binding,
  run-manifest, numerical-evidence discipline, and git gate checks for stage
  boundaries.
- Repository-level `scripts/dsh-doctor.py` -- DSH environment preflight: the
  four skill bundles under the DSH skill roots, a Python interpreter, and the
  Lean toolchain for stage C.
- `assets/dsh-solve-audit-workflow.js` -- DSH workflow-tool template: parallel
  solve + adversarial audit per packet, then a verify stage for qualified
  results.
- `references/openprover-absorption.md` -- token-conscious OpenProver
  absorption: Planner action protocol, Repository item system, `theorem.lean`
  skeleton, Planner history, and token budget pause/handoff/resume discipline.
- `references/reuse-protocol.md` -- lightweight reuse protocol: compact
  pre-scan, minimum artifact set, post-run `reuse_summary.md`, no per-route
  tags, mandatory Lean scaffold.
- `references/performance-observability.md` -- performance metrics, baselines,
  alert levels, and the rule that single-run alerts are candidates requiring
  confirmation.
- `scripts/performance_alert.py` -- compare a run metrics file against a
  baseline and write `performance_alert.md`.

## History

Release history, method provenance, and source links live in
`references/changelog.md`. Read it only when auditing provenance or preparing
a release.
