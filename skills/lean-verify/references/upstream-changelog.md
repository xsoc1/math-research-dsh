# Upstream changelog history

## Changelog (2026-08-12)

- 新增四道闸 + 人工语义复核 (Phase 3): 编译 / sorry 扫描 / axiom 集 / 陈述守护 + 人确认形式化陈述仍忠于来源; 已批准陈述的修改需重新过审与新 guard 快照.
- 新增修复策略 (Phase 3): 陈述冻结 (修证明不动陈述签名) + sorrifier 分解 (失败块 sorry 化保留骨架, 子问题递归) + 错误分类优先 (判定 -> 分类 -> 定位 -> 修正), 最终 sorry 清零.
- 新增首错定位与错误层分类 (Phase 4): 每个发现定位第一个错误步骤并分类 (陈述/证明/依赖/边界约定); 结构化输出新增可选 first_error 字段 (schema 同步).
- 方法来源: M2F (https://github.com/optsuite/M2F), MechMath sorrifier (https://github.com/MechMath/MechMath-v1), MMAT fl-prover (https://github.com/MechMath/MechMath-agent-team), FaithSieve (https://github.com/TropicalFatFish/anonymous-faithsieve), FormalRx (https://github.com/LARK-AI-Lab/formalrx, arXiv:2607.04655).
## Changelog (2026-08-14, DSH adaptation)

- Added the DSH runtime notes block and moved the changelog sections into this
  reference file; all upstream content is byte-identical otherwise (see
  `upstream.lock.json`). This bundle is the DSH counterpart of the Codex
  plugin `lean-verify` in the math-research marketplace repository
  (https://github.com/xsoc1/rigorous-open-math-research).
## Changelog (2026-08-14, DSH performance adaptation)

- Runtime notes extended with DSH execution patterns (background lake build,
  fresh-subagent verification, prune-aware output).
