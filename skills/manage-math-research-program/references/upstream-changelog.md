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

## Changelog (2026-08-16, human-readable LaTeX proof delivery)
- 新增第 8c 节 (强制): Lean 验证通过 (FORMALLY_VERIFIED + build_passed +
  零 sorry/axiom) 的定理必须在 `papers/<SLUG>/` 交付人类可读 LaTeX 证明文档 -
  英文 arXiv 规范版 (`\documentclass{amsart}` + amsthm/amsmath/hyperref, 标题/
  摘要/编号定理环境/带 DOI 或 arXiv 链接的参考文献, xelatex 零警告) 与中文对照版
  (同一陈述/证明结构/文献), 文档头绑定机器验证契约 (Lean 路径/验证提交哈希/
  lake build/零 sorry-axiom), 陈述与形式化一致, STRICT vs EVIDENCE 标签纪律
  不变; 证据规则 13 与项目完成清单同步; 新增模板
  `assets/proof-paper.template.tex`; init/validate 创建并校验 `papers/`
  (目录 + README), MANIFEST.sha256 重新生成.

## Changelog (2026-08-16, distilled methods round 2)
- 检索证据契约 (第 3 节): 每条检索条目携带 fetch status (fetched-verified /
  abstract-only / paywalled / unreachable), uncertainty vs warnings 二分,
  摘要级命中不得视为定理已定; 本地已读文献先查 (有界证据片段 + 章节名引用),
  检索历史键复用防重走. 方法来源: modsearch, argo, dsh-zotero, dsh-kb-sieve,
  dsh-web-search-pro.
- 工具库溯源 (第 5 节): 工具条目必须带产物溯源 (产生 run/命令/输入/环境/源
  hash + 追加型验证注记), 无溯源的工具条目只是线索. 方法来源: dsh-science.
- 已接受知识流水线新增第 8 条证据边界 (8b): Chat/stdout/交互终端输出本身不
  成为正式证据, 只有受控 run 产物 (hash 绑定输入 + 冻结环境) 经独立评审才可
  晋升; 正式计算须绑定不可变快照与固定环境. 方法来源: dsh-scholar.

## Changelog (2026-08-16, progress registration + formalization scaffolding)
- 问题进展全面登记 (第 5/8 节): 部分结果、结构定理、失败路线与精确失败机制、
  新工具全部成为一等记录; 不允许只留在对话记录中.
- 新增第 8d 节 (强制): 每个新结果 (含 RIGOROUS_PARTIAL_RESULT / 结构定理 /
  反例 / 约化) 在存在 `lean-proof/` 时必须创建 Lean scaffold, 登记到
  `lean-proof/STATUS.md` / `README.md` / `formalization_progress.md`, 并记录
  scaffold 路径 + sha256; scaffold 不得声称 FORMALLY_VERIFIED.
- 证据规则新增第 14 条: 未登记或未 scaffold 的结果不算完整摄入.
- 交接增强: 中断 run 的交接记录必须独立成文, 包含已完成工作进度与尝试过的
  工具/方法 (配合 workflow handoff 模板与门禁).
- Lean 中间验证与覆盖: 承重中间引理尽早机器验证; 更新的结果可标记旧结果为
  `superseded` 并保留历史, 不得把旧结果当作当前状态.
- 新增 8e 证明文件提交审计流程: 先仓库比对 -> Lean 验证与审计 -> 依规则加入;
  模板 `assets/proof-submission-audit.template.md`, 证据规则 15.
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `manage-math-research-program` in the math-research marketplace
  repository (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background jobs,
  subagent delegation, workflow fan-out, goal tools, prune-aware output).
