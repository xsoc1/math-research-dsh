# Upstream changelog history

## Changelog (2026-08-12)

- 新增发散式检索契约 (第 3 节): 搜索宽不守门, 相关性判断与正确性审计分离, 来源诚实三要素 (query -> result -> locator), KB/工具库优先, 分层检索流水线, 原始源不可变存储 + 编译知识卡片 (完整分析/部分证明/受阻路径), 先前部分进展与排除路线也是知识.
- 新增组合与工具库演化规则 (第 5 节): 问题记录带一行证据状态 (OPEN/PARTIAL/NUMERICAL_EVIDENCE/PROVED/FORMALIZED) 与研究状态; 工具条目按边际收益采纳 (解决已知阻塞/提升证据等级/降低检索成本) 并在维护日志登记.
- 新增失败入档分类 (第 8 节 5b): 上游审计报告缺口记录首错位置与错误层 (陈述/证明/依赖/边界约定), 后续按最小责任路由.
- 新增新鲜上下文收敛检查 (第 9 节): 阶段收尾只从文件重建程序状态, 判断收敛/发散, 只登记不重写.
- 方法来源: MMAT kb-manager/searcher (https://github.com/MechMath/MechMath-agent-team), EvE (https://github.com/scaling-group/eve, arXiv:2605.09018), Archon-Horizon (https://github.com/frenzymath/Archon-Horizon).

## Changelog (2026-08-14, formalization decision field)
- 任务包模板新增可选 `Verify: yes|no|not-requested` 字段: yes 表示该 run 进入
  Stage C Lean 验证, run-manifest 必须记录 formalization: requested 并产出机器
  验证证据; 配合 workflow 门禁的形式化决策检查 (静默跳过验证 = FAIL).
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `manage-math-research-program` in the math-research marketplace
  repository (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background jobs,
  subagent delegation, workflow fan-out, goal tools, prune-aware output).
