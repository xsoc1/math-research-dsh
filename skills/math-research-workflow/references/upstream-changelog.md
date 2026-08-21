# Upstream changelog history

## Changelog (2026-08-14)

- Distilled the OpenProver method (arXiv:2607.09217, github.com/kripner/OpenProver)
  into stage B/C: Planner-Worker-Verifier solve loop with a mandatory compact
  `whiteboard.md` per run (current plan, route history with outcome markers,
  deferred ideas, open obligations, key-artifact index); independent parallel
  Workers that never see each other's or the Planner's reasoning traces;
  independent Verifier feedback on finished Worker outputs; repository items
  addressed by slug with a verified-items-only rule for Lean snippets; a Lean
  real-time verification loop (`lean_verify` / `lean_search` via LeanExplore /
  `lean_store` context accumulation); a formalization feedback loop that routes
  proof-layer flaws back to the solve-run lead; and interactive steering for
  human-in-the-loop runs. `validate_pipeline.py` hard-requires the whiteboard
  (fields + sections) for stage B runs started on or after 2026-08-14; new
  `tests/smoke_whiteboard.py` wired into CI.
- Cachebuster bumped to `0.1.0+codex.20260814120000` to propagate the protocol.

## Changelog (2026-08-13)

- Added `scripts/doctor.py`, an environment preflight: verifies the workflow
  plugin, the three dependency skills, the marketplace, and the `config.toml`
  enable entry; prints exact repair commands. Stage A runs it before dispatch
  (guards against the desktop app rewriting `config.toml` and dropping the
  plugin-enable entry).
- `validate_pipeline.py` now enforces numerical-evidence discipline: a gate
  status requires `candidate_proof.md` or `audit_report.md` in the run
  directory; numerical labels mixed with strong claims need a strict label or
  an explicit downgrade statement; `verification.json` verdict
  `FORMALLY_VERIFIED` requires `machine.build_passed == true` and zero
  sorry/axiom hits; `STATUS.md` cannot claim `FORMALLY_VERIFIED` without the
  verdict file. Fixed lean-manifest input-hash resolution (paths are relative
  to `lean-proof/` and may use Windows separators).
- Fork-sync specifics removed from this plugin; git sync now defers to the
  manage skill's generic remote-topology configuration.
- Cachebuster bumped to `0.1.0+codex.20260813054312` to propagate the gate.

- Stage B now starts with a mandatory B0 novelty preflight: openness check
  (genuinely open as of the research date), divergent novelty audit with
  `query -> result -> locator` provenance, snapshot-hash backfill into the
  manage skill's literature frontier, and a deterministic gate - every
  solve/disprove/construct task packet must carry a `## Novelty preflight`
  section (openness verdict + audit path or explicit skip + snapshot hash),
  enforced by `validate_pipeline.py`. A missing preflight is a hard FAIL at
  the A -> B boundary.
- Cachebuster bumped to `0.1.0+codex.20260813101438` to propagate the B0 gate.

- Interruption handoff and resume protocol: when a stage stops before
  completion, the interrupting agent writes
  `runs/<run_id>/handoff-interrupted-<ts>.md` from
  `assets/interruption-handoff.template.md` - run/packet IDs, interrupt
  reason, task state, completed/open obligations, every route tried with
  `[FAILED|BLOCKED|PARTIAL|SUCCEEDED]` outcome markers, exact next actions,
  and hashed artifact paths; the successor agent resumes from the handoff and
  must not re-run a FAILED route without a new recorded reason.
  `validate_pipeline.py` hard-fails handoffs missing required fields or
  sections. Added `tests/smoke_handoff.py` (+ good/bad fixtures) and wired it
  into CI.
- Cachebuster bumped to `0.1.0+codex.20260813144928` to propagate the handoff protocol.

## Changelog (2026-08-14, formalization decision gate)
- 修复静默跳过 Lean 验证: 声称完成状态 (已证/CANDIDATE_COMPLETE_PROOF) 的 run 必须在
  run-manifest 记录形式化决策 (formalization: requested | not_requested | skipped);
  requested 要求 formalization_manifest 指向存在文件 + lean-proof/verification.json
  干净机器裁决; skipped 要求非占位 formalization_reason 且重新验证义务保持开放;
  门禁机械强制 (validate_pipeline.py), 缺失决策即 FAIL.
- 任务包模板新增可选 Verify: yes|no|not-requested 字段 (manage skill).
- 新增 tests/smoke_formalization.py + 三个 fixtures (good/missing/requested).

## Changelog (2026-08-16, distilled methods round 2)
- 多 agent 协作增强 (纯增量): Stage B 新增义务认领协议 (claim before work -
  ledger 记录唯一所有者, 防重复证明; 来自 dsh-suite plugin-team-board);
  Loop control 新增缺口回灌硬规则 (非 PASS 评审输出必须被修订轮消费或登记为
  路由义务, 静默丢弃 = 门禁失败; 来自 dsh-proof); Efficiency rules 新增并行
  失败聚合 (收集全部成员失败, 不短路; 来自 dsh-agent-team-gui) 与循环检测
  (无新机制重试失败路线即阻断并记录见证; 来自 dsh-trajectory-governance).
- Stage C 新增 Lean 升级通道: 证明关键且可机器验证的断言先形式化验证再声称
  完成状态 (先 Lean 再落地, 非事后补验; 来自 dsh-rigorquant).

## Changelog (2026-08-16, progress registration + formalization scaffolding)
- Stage B/C: 每个新结果 (含 RIGOROUS_PARTIAL_RESULT / 结构定理 / 反例 /
  约化) 都必须登记并创建 Lean scaffold; 只有完成标签 (已证 /
  CANDIDATE_COMPLETE_PROOF) 才做完整 Lean 验证.
- run-manifest 形式化决策新增 `scaffold`: 必须指向存在的 scaffold 文件
  (.lean 或 formalization_progress.md), 不要求 verification.json, 不得声称
  FORMALLY_VERIFIED.
- 门禁 (validate_pipeline.py): 2026-08-16 之后开始且有实质进展的 run 必须记录
  `formalization: scaffold | requested`, 否则 FAIL; 旧 run 不追溯.

## Changelog (2026-08-16, handoff improvement)
- 交接记录独立成文并增强: 必须包含 `Completed work progress` (已完成工作进度,
  后续不得重做) 与 `Tools and methods tried` (尝试过的工具/方法/命令 + 结果标记
  + 证据路径 + sha256); 门禁新增这两个必需 section, 缺失即 FAIL.
- Lean 中间验证与覆盖: Stage B 增加 Intermediate Lean checkpoints (承重引理
  尽早 lean_verify); Stage C 明确更先进结果可把旧 scaffold/partial 标记
  `superseded` 并保留历史.
- 新增 Proof submission audit: 证明文件提交仓库前必须走 仓库比对 -> Lean 验证与
  审计 -> 依规则加入 三阶段流程 (由 manage 8e 负责).
- 效率优化: 引入 Tier 0/1/2 分级验证 (scaffold / 单引理机器验证 / 全量验证);
  新增 lemma reuse index, 证明前先查 `lean-proof/LEMMA_INDEX.md` 避免重复证明.
- Rethlas 蒸馏: Stage B 增加失败综合与反例复用 (key_failures_summary + 反例库),
  并明确搜索是支撑不是替代.
- 双轨审计: Stage C 增加非正式审计 + Lean 形式化双轨验证矩阵, 冲突裁决规则
  (非正式 gap > Lean 通过; Lean 失败 > 非正式通过; 论文级失败 > 两者).
- OpenProver token-conscious 吸收: 新增 `references/openprover-absorption.md`;
  Stage B 增加 Planner action 协议、Repository item 系统、`theorem.lean`
  前置骨架、Planner history、token budget pause+handoff+resume.
- 研究地图: Stage A/B/C 阶段边界强制更新 `research_map.md` (路线/方法/中间
  结果/失败原因/工具/开放方向/avoid list/人类补充); 深挖子分支前先读地图避免
  钻牛角尖.

## Changelog (2026-08-16, cost-tiered escalation)
- Stage B 新增 cost-tiered escalation (light first): Planner 先跑 Tier 0/1
  cheap probes (已有工件/工具库/特化/弱化/实例化/局部修补), 按信息增益/成本
  排序行动, 只有 zero-gain / 反例障碍 / load-bearing gap / 用户授权才升到
  Tier 2/3; 并行 fan-out 视为 Tier 3, 禁止无记录直接并行; 白板模板新增
  `current_cost_tier` 与 `last_escalation_reason`; 详细协议见 rigorous
  `references/escalation-ladder.md`.
## Changelog (2026-08-14, DSH adaptation)

- DSH adaptation layer: this bundle now ships as a DeepSeek Harness skill.
  Added the DSH runtime notes block; the Codex environment preflight
  (`scripts/doctor.py`) is replaced by the repository-level `scripts/dsh-doctor.py`
  (DSH skill roots, Python interpreter, Lean toolchain); Stage A step 2 and the
  reference-file list were rewritten accordingly. Upstream content is otherwise
  byte-identical (see `upstream.lock.json`).
## Changelog (2026-08-14, DSH performance adaptation)

- Added references/dsh-execution.md and assets/dsh-solve-audit-workflow.js
  (parallel solve+audit per packet via the DSH workflow tool, verify stage for
  qualified results only).
