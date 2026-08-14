# AGENTS.md

## 仓库定位

DSH (DeepSeek Harness) 适配仓库: 把 Codex marketplace `math-research` 的 4 个插件
(rigorous-open-math-research / manage-math-research-program / math-research-workflow /
lean-verify) 以 DSH skill 形式发布, 附带脚本/模板/冒烟测试与同步工具链.

父仓库: https://github.com/xsoc1/rigorous-open-math-research (Codex marketplace).

## 目录结构

- `skills/<name>/` -- DSH skill bundles (SKILL.md + references/ + assets/ + scripts/)
- `scripts/sync-from-parent.py` -- 父仓库同步 + DSH 层重放 + upstream.lock.json
- `scripts/validate_all.py` -- 仓库校验 (结构/MANIFEST/lock/UTF-8+LF/py_compile/JSON+YAML)
- `scripts/dsh-doctor.py` -- DSH 环境自检 (skill 挂载/python/lake)
- `tests/` -- fixtures + 5 个 smoke
- `upstream.lock.json` -- 父仓库 commit + 逐文件哈希
- `install.ps1` -- 安装到 $DSH_HOME/skills 的 junction (热更新)

## 维护规则

1. 每次变更后运行 `python scripts/validate_all.py .` (Python 3.10+, 建议 PYTHONUTF8=1).
2. 禁止手改同步文件: 上游内容改动走父仓库然后重跑 sync-from-parent.py; DSH 层改动只允许
   改 sync-from-parent.py 内的层常量 (runtime notes/changelog/workflow 替换).
3. 父仓库前进时: `sync-from-parent.py --upstream <clone>` 重新同步并提交新 lock;
   CI 的 sync-check job 每次 push 自动做漂移检查.
4. 所有文本文件 UTF-8 无 BOM, LF 换行, 英文标点.
5. 提交后按 project.json 的 git_sync.push_order push (当前只有 origin).
6. 本机安装用 install.ps1 (junction 热更新); `git pull` 后无需重装.
7. README 中英两版必须同步更新 (README.md 中文 + README_EN.md 英文, 顶部互链).

## 会话记录
### 2026-08-14 会话: 初始适配 (从 Codex 父仓库)

- 上游基线: xsoc1/rigorous-open-math-research @ debc3be (2026-08-13).
- 4 个 skill 全部适配: DSH runtime notes + DSH changelog 注入每个 SKILL.md;
  workflow 的 doctor 段改写为仓库级 scripts/dsh-doctor.py; Codex 版 doctor.py 移除.
- 工具链: sync-from-parent.py (拷贝 + 层重放 + MANIFEST 重生成 + lock),
  validate_all.py (36 项), dsh-doctor.py (--json/--list-file), install.ps1 (junction),
  CI (validate + smoke + sync-check).
- 校验: validate_all 全绿; 5 个 smoke 全过; 本机 junction 安装后 DSH 会话目录即时
  出现 4 个 skill (watcher 跟随 junction, 无需重启).
- 修复: MANIFEST 自引用条目 (生成与校验都排除 MANIFEST.sha256 自身);
  dsh-doctor --json 混入汇总行导致 smoke 解析失败 (--json 只输出 JSON).
### 2026-08-14 会话 (README 中英双语 + 仓库关系说明)
- README.md 重写为中文版并新增英文 README_EN.md, 顶部互链; 两版新增 "背景与现状"
  与 "仓库间关系" 章节 (父仓库/fork/本仓库拓扑 + 单向同步关系 + 与 DSH 运行时关系).
- AGENTS.md 维护规则新增第 7 条 (README 中英同步); 本文件追加会话记录.
- 校验: validate_all 全绿; 提交后 push origin.
- 修复: 跑 smoke 会在 bundle 内生成 __pycache__/*.pyc, 污染 lock/MANIFEST 覆盖检查
  (22 个 FAIL); validate_all.py 与 sync-from-parent.py 全部文件遍历统一忽略
  __pycache__ 与 *.pyc (is_transient), 清理存量缓存后 36 项全绿, 5 个 smoke 全过,
  sync --check 干净.
- 修复: CI sync-check 报 drift in MANIFEST.sha256. 根因 = pathlib 平台排序差异:
  sorted() 对 Path 对象在 Windows 按大小写不敏感 (normcase), 在 Linux 按大小写敏感,
  导致两端生成的 MANIFEST 行序不同 (本地首行 ./assets/..., CI 首行 ./SKILL.md).
  修复: regen_manifest 改按相对路径 as_posix() 字符串排序 (码点序, 跨平台确定);
  重同步后 MANIFEST/lock 更新, 本地 36 项 + 5 smoke + check 全绿. 诊断输出保留在
  run_check 中 (漂移文件打印 expected/current 哈希与首处差异行).
### 2026-08-14 会话 (DSH 性能适配层)
- 结合 DSH 运行时机制做性能适配 (全部经 sync-from-parent.py 层重放, 上游文件仍字节一致):
  - 加载瘦身: 4 个 SKILL.md 的 changelog 段落迁出到 references/upstream-changelog.md,
    正文替换为指针; 上游 changelog 以后增长不再拖累 skill 加载 (validate_all 新增
    指针/参考文件/无残留 changelog 标题 3 项检查, 共 48 项).
  - 截断感知: 新增 scripts/dsh_run.py (verdict 头 + FAIL 行 + verdict 尾 + 完整日志
    落盘) 与 tests/smoke_dsh_run.py; 校验器忽略 .dsh_run.log 执行产物.
  - DSH 执行模式: runtime notes 全部升级 (后台任务/spawn 子代理隔离/workflow fan-out/
    goal 工具); 新增层自有文件 references/dsh-execution.md (rigorous+workflow) 与
    assets/dsh-solve-audit-workflow.js (workflow 模板).
  - README 中英同步更新 (DSH 性能适配表 + 同步契约 4 项 + 目录树).
- 校验: 48 项全绿, 6 个 smoke 全过, sync --check 干净, lock 69 文件.
- 诚实声明: rigorous changelog 本体仅 ~26 行, 该 skill 单次加载节省有限 (~1K tokens);
  主要收益是 changelog 随上游增长的长期有界性与 workflow (~40 行) 的立省.
### 2026-08-14 会话 (A1 渐进式披露 + A2 回传契约落地)
- 上游 (91293b0, 双仓同步): rigorous SKILL.md 纯移动拆分为驱动层 168 行/12,546 bytes
  (原 760 行/44,978 bytes, -72%) + references/ 8 个 phase 文件; 驱动层保留全局规则/
  工件清单/Phase 索引表/Output protocol/Anti-patterns; scripts/split_rigorous_skill.py
  --verify 复验 760 行零丢失零改写; cachebuster 刷新为 0.1.0+codex.20260814110748
  (本机无官方工具, 直接改版本字段); 上游 validate_all 68 项全绿.
- 本仓库 (1be12f3): 同步 91293b0 (lock 77 文件); A2 落地 (workflow 模板三 prompt 与
  dsh-execution.md 增加子代理回传契约: 完整报告落盘, 回复只含 verdict+路径+hash);
  sync 增加 normalize_tree (上游 Windows 工作树 CRLF 不得漏进本仓库; 起因: 上游拆分
  脚本文本模式写文件在 Windows 翻译 \n->\r\n, 上游 blob 已被 git 归一化不受影响).
- A/B 评测: baseline (旧版) 与新版各跑一次 planted-error 审计 (Weierstrass 导数
  不收敛 + 数值冒充证明); baseline 全部命中 (FATAL_GAP, 两埋点全抓); after 结果见
  _ab_test 目录与本文件后续记录.
- 校验: 48 项全绿, 6 smoke 全过, sync-check 干净; CI 待确认.
- A/B 结果 (after, 已完成): FATAL_GAP + NO_MATERIAL_PROGRESS, 两埋点全抓且攻击更深入
  (比值泛函非 sup 连续 + f_m=m^{-1}sin(m^2 x) 反例; 数值不覆盖全部 <=12 次多项式);
  陈述真伪与证明有效性正确分离 (MVT 证明陈述为真且尖锐, verify_ineq.py 数值 2.668
  如实标 EVIDENCE); 工件 6 件 (较 baseline 3 件更全, 含 obligation_graph/
  research_ledger/verify_ineq.py); 四强制审计结构来自 phase-78 文件 = 渐进式披露
  路径被实际使用. 结论: 行为质量无退化 (n=1 单样本, 不宣称提升); 机器性能
  43.6KB->10.7KB/load. 诚实标注: A2 回传收束未被本 A/B 检验 (审计 prompt 未走
  workflow 模板路径), 如需验证 A2 需按模板再跑一轮.
### 2026-08-14 会话 (社区方法蒸馏吸收)
- 检索开源 DSH 生态 (官方 deepseek-ai/deepseek-harness 63K stars + awesome 清单),
  将可借鉴方法全部蒸馏进插件 (方法级借鉴, 自撰措辞, 无文字复制):
  - 上游 (01140b1, 双仓同步, cachebuster 0.1.0+codex.20260814125833): rigorous
    phase 文件纯增量 5 处 - 答案空间/验收标准 (phase-01), 覆盖维度 + coverage_gaps
    (phase-23), 边际增益停止规则 + 证据三态 (phase-45), 零增益停止见证 (phase-12),
    角色模型分层 (agent-orchestration); 来源 dsh-deep-research + dsh-multiagent-modes.
  - 本仓库层: workflow 模板 v2 (manifest 头部/依赖声明 + 波次执行/roster 注入/
    模型分层), dsh-execution.md 分级回报格式 + 第 7 节 context audit.
  - 新工具: scripts/context-audit.py (指令链 64KB 截断标记/技能体积/重复段落/名字
    遮蔽) + tests/smoke_context_audit.py.
  - 观察不集成: jacobian (数学内核 MCP), dsh-automation (定时任务), dsh_workflow
    (完整资产层) - 待真实痛点.
  - 许可证: 全部方法级借鉴; dsh-multiagent-modes 为 CC BY-SA 4.0, 未来直接引用其
    文字需同样开源署名 (README 已注明).
- 校验: 48 项全绿, 7 个 smoke 全过, sync-check 干净 (01140b1), lock 77 文件; CI 待确认.
### 2026-08-14 会话 (可选外部能力目录)
- 多模态检索结论: DSH 生态视觉插件以桥接外部 VLM 实现 (dsh-vision-toolkit 232 stars,
  dsh-vision 13 stars 免费档), 文档解析 dsh-plugin-mineru (公式友好 PDF->Markdown).
- 本部署机制核实: profiles/web 的 dsh.profile.bundles 层栈 + checkout 内 dsh plugin
  (转发 pnpm) 存在, Node v24.17 满足要求; dsh CLI 不在 PATH (经 checkout bin 调用);
  安装会动线上 web profile, 建议先副本 profile 试装 (未实际安装).
- 蒸馏: 上游 dd3bfec phase-01 新增第 9 条 (解析/视觉输出 = 未验证输入, 回查原源;
  cachebuster 0.1.0+codex.20260814154520); 本仓库新增层文件
  references/dsh-optional-capabilities.md (vision 约定/文档解析约定/何时不用,
  挂 rigorous + manage), runtime notes 指针同步; lock 79 文件.
- 校验: 48 项全绿, 7 smoke 全过, sync-check 干净 (dd3bfec); CI 待确认.
