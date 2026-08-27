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
- The DSH adaptation keeps every upstream file byte-identical except this block
  and the DSH changelog append; the synced upstream commit is recorded in the
  repository `upstream.lock.json`.

### DSH execution patterns (performance)

- Long computations (numerical scans, finite verifications, big derivations)
  run as background shell jobs (`run_in_background: true`), collected with
  job_output and cancelled with job_kill; never block a turn polling them.
- Adversarial audit / verifier roles run as fresh `subagent` (spawn provider:
  no conversation seed, artifact-only prompts), so they share no chain of
  thought with the solver; `subagent_fork` is for context-heavy continuation.
  Follow-ups go through send_message; the runtime reports completion.
- Fan-out across many packets uses the `workflow` tool with the template in
  the math-research-workflow bundle (assets/dsh-solve-audit-workflow.js).
- Multi-round objectives use the goal tools (create_goal / get_goal /
  update_goal).
- DSH truncates tool results (~8K chars, head 4096 + tail 1024): bundled
  scripts print verdicts last; for long outputs run them through the
  repository-level wrapper scripts/dsh_run.py, which pins the verdict and the
  FAIL lines outside the truncated middle and keeps the full log on disk.
- Full details: references/dsh-execution.md in this bundle. Optional external
  capabilities (vision for text-only models, document parsing to Markdown)
  and their invocation conventions: references/dsh-optional-capabilities.md.

# Rigorous Open Mathematics Research

## 中文使用说明 (摘要)

本 Skill 用于对开放、前沿或高难度数学问题做严格研究. 它不承诺用措辞解决开放问题,
而是最大化可审计进展: 显式定理契约, 多样化搜索, 持久研究台账, 可执行验证, 对抗性证明审计, 文献核验与校准式报告.

- 触发场景: 定理证明, 猜想攻关, 反例搜索, 结构分类, 等价刻画, 复杂推导, 严格审计.
- 图谱集成: 若项目提供已接受知识库 (Blueprint v2.2 数学超图), 检索将绑定快照 (math-closure / math-frontier), 可依赖前提与前沿由确定性程序给出, 合同见 references\blueprint-math-graph-integration.md.
- 启动后按 Phase 0-12 工作, 并维护 "Default research artifacts" 中的台账文件.
- 单一目标默认先执行 closure-first 门禁: 定位首个承重义务, 直接求解并做廉价证伪, 只有出现明确升级理由后才扩展多路线或子 agent.
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
11. Every material progress item is first-class: register it immediately in the ledger, route registry, and tool library, and when a formalization project exists create a Lean scaffold for the new result before moving on. Partial progress is progress; it must be auditable and formalization-tracked, not deferred until a complete proof exists.
12. Lean verification is not only for the final conclusion: machine-check key intermediate lemmas as soon as they become load-bearing, so errors are caught before a route is invested further. A later, more advanced result may supersede an earlier partial/scaffold result; keep the old record in history but mark it superseded in the formalization progress and knowledge base.
13. A candidate proof submitted for repository acceptance must pass the proof submission audit pipeline (manage workflow 8e): repository comparison, Lean verification/audit, then rule-based integration. The submission audit record must accompany the proof.
14. Before broad route generation or research sub-agent fan-out, run the closure-first preflight: identify the first open load-bearing claim, attempt it directly, run a cheap falsification probe, and record the decision that escalation can change. Difficulty alone is not an escalation reason.

## Default research artifacts

When persistent files are available, maintain the following. If files are unavailable, use equivalent clearly labeled sections in the response. Materialize lazily: start with `problem_contract.md`, `obligation_graph.md`, `research_ledger.md`, and `closure_gate.md` when closure-first is active; create the remaining artifacts when they acquire content or a stopping/handoff boundary requires them. Do not spend research calls on empty duplicate scaffolding.

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
- `formalization_progress.md` — when a formalization project exists, track every new result's Lean scaffold/status here (or in the project's `lean-proof/STATUS.md`).
- `research_map.md` — the human-readable, continuously updated survey of the problem: routes/methods tried, intermediate results, unexpected findings, failures and reasons, tools, open directions, an avoid list, and human/other-agent contributions (maintained per manage workflow 8f).
- `escalation_ladder.md` — when cost-tiered escalation is used, the run-level log of cheap probes attempted, tier changes, triggers, failure mechanisms, and the current cost tier (see `references/escalation-ladder.md`).
- `closure_gate.md` — the first open load-bearing claim, direct attempt, cheapest falsification probe, gate decision, and next decision-changing action (see `references/closure-first-protocol.md`).
- `reuse_summary.md` — when the workflow lightweight reuse protocol is active, the post-run record of actual reused items, duplicate work avoided/remaining, new methods, and a one-line cost assessment (see workflow `references/reuse-protocol.md`).

Update the ledger immediately after any substantial computation, proof attempt, literature discovery, or route decision. Do not begin a near-duplicate exploration until the previous result and failure mechanism are recorded. Publish every material finding, surprise, and failure reason to the research map (or ensure its source is aggregated there) so partial progress is never lost and later humans/agents can build on it.

# Workflow

## Phase index

Read the referenced file through this skill's resourceBase directory before
executing a phase; every phase file repeats this contract at its top.

| Phase | File |
|---|---|
| 0-1 provenance, scope, theorem contract | `references/phase-01-contract.md` |
| 2-3 literature map + proof-obligation graph | `references/phase-23-search.md` |
| 4-5 route portfolio + research loop | `references/phase-45-routes-loop.md` |
| closure-first preflight and spawn gate | `references/closure-first-protocol.md` |
| cost-aware escalation ladder (light first) | `references/escalation-ladder.md` |
| 6 computational and evolutionary search | `references/phase-6-computation.md` |
| 7-8 synthesis + adversarial proof audit | `references/phase-78-synthesis-audit.md` |
| 9-11 revision, formalization, novelty | `references/phase-91011.md` |
| 12 stopping and reporting (+ Result template) | `references/phase-12-reporting.md` |
| delegation, sub-agents, role prompts | `references/agent-orchestration.md` |
| Rethlas-distilled methods (memory/failure synthesis/counterexample reuse/search discipline) | `references/rethlas-distilled.md` |
| Dual-track audit (informal + Lean formal verification coexistence) | `references/dual-track-audit.md` |

Global contracts (epistemic rules, artifacts, Output protocol, anti-patterns)
stay in this file and bind every phase.
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

Then use the result template in `references/phase-12-reporting.md`. Do not
present an unverified candidate as a theorem or bury a fatal gap in a
footnote. When a canonical knowledge base exists, also report the trusted
closure, exact frontier, blocked obligations, and separate transaction status
from research status.

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

## History

Release history, method provenance, and source links live in
`references/changelog.md`. Read it only when auditing provenance or preparing
a release.
