# Upstream changelog history

## Changelog (2026-08-12)

- 新增四道闸 + 人工语义复核 (Phase 3): 编译 / sorry 扫描 / axiom 集 / 陈述守护 + 人确认形式化陈述仍忠于来源; 已批准陈述的修改需重新过审与新 guard 快照.
- 新增修复策略 (Phase 3): 陈述冻结 (修证明不动陈述签名) + sorrifier 分解 (失败块 sorry 化保留骨架, 子问题递归) + 错误分类优先 (判定 -> 分类 -> 定位 -> 修正), 最终 sorry 清零.
- 新增首错定位与错误层分类 (Phase 4): 每个发现定位第一个错误步骤并分类 (陈述/证明/依赖/边界约定); 结构化输出新增可选 first_error 字段 (schema 同步).
- 方法来源: M2F (https://github.com/optsuite/M2F), MechMath sorrifier (https://github.com/MechMath/MechMath-v1), MMAT fl-prover (https://github.com/MechMath/MechMath-agent-team), FaithSieve (https://github.com/TropicalFatFish/anonymous-faithsieve), FormalRx (https://github.com/LARK-AI-Lab/formalrx, arXiv:2607.04655).

## Changelog (2026-08-16, distilled methods round 2)
- Phase 3 机器核查升级: 单一结构化判定 gate 协议 (build_passed/sorry_axiom_hits/
  first_error 进机器可读裁决, 禁止自由文本解析当证据; 干净构建 = proved 分支,
  构建失败 = 局部反证分支, 定位首错 + 最小失败声明; 来自 forge-gates);
  原子/有界/无状态检查 (请求级临时目录 + 固定环境, 不保留会话与源码, 结果作为
  类型化值供义务图消费; 来自 jacobian lean.check).
- 修复策略新增同缺口收敛规则: 同一义务同一缺口连续三轮未修复即停止, 记录最强
  推导 + 精确缺口 (有反例则记录) 并降级裁决 (来自 dsh-rigorquant 三级停止).
- 裁决新增证伪优先规则: 任一义务被已核验反例/矛盾否决即整体否决; 状态不确定的
  义务不得当作通过, 全不确定不得 FORMALLY_VERIFIED (来自 Vibe-Mathematics).

## Changelog (2026-08-16, scaffold mode)
- 新增 Scaffold mode: 部分/结构结果必须先创建 Lean scaffold (声明 + 开放义务 +
  `-- SCAFFOLD` 头注释, 允许 `sorry`), 登记到 STATUS/README/formalization_progress,
  状态 `SCAFFOLDED`, 不得声称 FORMALLY_VERIFIED.
- 输出协议新增 `SCAFFOLDED` 状态.

## Changelog (2026-08-16, intermediate verification + supersession)
- 明确 Lean 验证也是研究途中的校验工具: 承重中间引理尽早验证, 避免走弯路.
- 更先进结果可覆盖旧结果: 旧 scaffold/partial/verified 记录标记 `superseded`
  并指向新结果, 保留历史但不得作为当前状态.
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `lean-verify` in the math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background lake build,
  fresh-subagent verification, prune-aware output).
