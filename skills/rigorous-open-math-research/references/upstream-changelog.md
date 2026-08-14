# Upstream changelog history

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

## Changelog (2026-08-14)
- 渐进式披露重构: Phase 0-12 详细契约与角色 prompt 纯移动至 references/ (phase-01-contract, phase-23-search, phase-45-routes-loop, phase-6-computation, phase-78-synthesis-audit, phase-91011, phase-12-reporting, agent-orchestration); SKILL.md 退化为驱动层 (全局规则/工件清单/Phase 索引表/Output protocol/Anti-patterns), 单次加载从 44978 bytes 降至 12042 bytes; 内容未改写, scripts/split_rigorous_skill.py --verify 可复验覆盖.
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file (keeps DSH skill loads light); all upstream workflow content
  is byte-identical otherwise (see `upstream.lock.json`). This bundle is the
  DSH counterpart of the Codex plugin `rigorous-open-math-research` in the
  math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Added references/dsh-execution.md (background jobs, spawn/fork subagent
  isolation, workflow fan-out, goal tools, prune-aware script output).
