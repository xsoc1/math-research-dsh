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
- `tests/` -- fixtures + 11 个 smoke
- `package.json` / `index.mjs` / `cordis.patch.yml` -- 官方 bundle 技能包 (社区一键安装)
- `scripts/dsh-check-bundle.py` -- bundle 打包门禁 (package.json/patch/index.mjs/skills)
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
8. 内容变更 (skill 正文/脚本) 时同步 bump package.json 的 version.
9. bundle 安装与 junction 安装二选一, 不要同时用 (同一批 skill 会双份注册).

## 注意事项 (Notes for future agents)

- **版本 bump 是硬门禁**: 修改 `skills/`、`index.mjs` 或 `cordis.patch.yml` 时必须同步
  bump `package.json`; CI 的 `version-bump` job 和本地 `validate_all.py` 都会检查.
- **上游同步纪律**: 不要手改 `skills/` 下从父仓库同步来的文件; 上游内容变更走
  `xsoc1/rigorous-open-math-research`, 然后重跑 `scripts/sync-from-parent.py`.
- **两种安装方式互斥**: `dsh plugin add github:xsoc1/math-research-dsh` (bundle) 与
  `install.ps1` (junction) 只能二选一, 同时安装会导致同一批 skill 双份注册.
- **README 中英同步**: README.md 与 README_EN.md 必须同步更新; `validate_all.py` 会
  检查所有 `tests/smoke_*.py` 是否都出现在两份 README 中.
- **测试数量**: 当前 11 个 smoke; 新增 smoke 后同步更新 README 两版与 AGENTS.md.
- **GitHub 网络**: 直连 github.com 失败时, 用本地代理 push:
  `git -c http.proxy=http://127.0.0.1:7897 push origin main` (本机实测可用).

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
### 2026-08-14 会话 (本机安装视觉/文档解析插件)
- 安装: profiles/web 加装 @huanlin/dsh-plugin-mineru (bundle 层, prepare 构建通过;
  allowBuilds 需带 git URL 的精确键) 与 @dsh-external/dsh-vision (其 dsh.plugin.json
  清单格式本部署不支持 -> 装为普通依赖 + profiles/web/cordis.patch.yml 手工
  insert 行, 模块导出 Config/apply/inject/name 已验证).
- 组合校验: --dump-config 合成树含 dsh-mineru (bundle) 与 dsh-vision (insert),
  无警告. 激活需重启 web (会结束当前会话, 由用户决定时机).
- 待配置: dsh-vision 无 API key (本机无智谱/DashScope key, 无 Ollama) -> 激活后调用
  需先配 VISION_API_KEY 或装 Ollama; mineru 需 MinerU 服务端点 baseURL.
- 风险与回退: dsh-vision lib 按公开版 API 构建, 本部署签名若有漂移, 重启时可能报错;
  回退 = 删除 cordis.patch.yml 中的 insert 行 (一行).
- 经验登记: 本部署无 dsh.plugin.json 支持 (grep 零命中); 社区"公开版机制"与本地
  checkout 的差异必须逐项验证, 不能照 README 盲装.
### 2026-08-14 会话 (本地 Qwen VLM 落地 F 盘)
- Ollama 安装: 官方安装器 /S /D 参数被新版安装器忽略, 实际装到 C: 默认位置;
  按用户要求整目录迁移至 F:\tools\ollama (2.8GB), 停掉 C: 实例, 无自启项残留,
  服务以 F:\tools\ollama\ollama.exe serve 运行 (11434), OLLAMA_MODELS (用户级环境
  变量) = F:\tools\ollama\models.
- 模型: 拉取 qwen3-vl:4b (本地 VLM, 免 key).
- dsh-vision 行配置已指向 http://localhost:11434/v1 + qwen3-vl:4b
  (profiles/web/cordis.patch.yml).
- 待办: dsh web 重启后 view_image 工具才生效 (重启会结束当前会话, 由用户决定时机);
  重启后可先用一张图片验证 view_image -> 本地 qwen3-vl 链路.
### 2026-08-14 会话 (继承上游 25b380d: OpenProver 求解循环 + whiteboard 门禁)
- 上游更新 (25b380d, 双仓已同步): workflow 插件蒸馏 OpenProver 求解循环 -
  whiteboard 记忆协议 (assets/whiteboard.template.md) + 独立 Worker/Verifier 反馈 +
  Lean 实时验证回路 (lean_verify/lean_search/lean_store) + 形式化反馈环 + 人工引导;
  validate_pipeline.py 门禁硬校验 cutover 后求解 run 的 whiteboard (+81 行);
  SKILL.md +93 行, workflow-design.md +64 行; cachebuster 0.1.0+codex.20260814120000.
- 继承: 重跑 sync-from-parent.py (DSH 层自动重放, 无锚点冲突), lock 80 文件;
  移植 smoke_whiteboard.py (路径改为 skills/ 布局) + pipeline-whiteboard-good/bad
  fixtures; 公共 fixtures 与上游逐文件一致 (parity 检查通过).
- 说明: 首次同步曾瞬时中断 (copy 阶段, 部分树 + validate 23 FAIL), 原样重跑即恢复,
  无代码缺陷; 第二次同步全量成功.
- 校验: 48 项全绿, 8 个 smoke 全过 (新增 whiteboard), sync-check 干净 (25b380d);
  CI 待确认.
### 2026-08-14 会话 (事故修复: 静默跳过 Lean 验证门禁)
- 事故: densbc run (R-20260814T070000Z) 声称 STRICT 完成却无任何 Lean 验证产物;
  根因链 = (1) 会话遇子代理提供方故障 (审计备注已记录 3 次尝试 + probe 失败),
  独立 verifier 无法生成, 协调者自审后直接关 run; (2) 插件缺口: Stage C 纯文字约定,
  门禁只查 FORMALLY_VERIFIED 声称, 静默跳过验证无痕可过.
- 修复 (上游 5f58f3d + 56d6657, 双仓同步): validate_pipeline.py 新增形式化决策
  硬检查 - 声称 gate 状态的 run 必须记录 formalization
  (requested|not_requested|skipped); requested 要求 formalization_manifest 存在 +
  lean-proof/verification.json; skipped 要求非占位 formalization_reason;
  缺失决策 = FAIL. 任务包模板 + manage SKILL 新增可选 Verify 字段;
  workflow SKILL Stage C 决策协议 + changelog; smoke_formalization.py + 3 fixtures;
  中途修 MANIFEST 过期 (重生成 44 条). cachebuster -> 0.1.0+codex.20260814155902.
- 本仓库 (0d68b66): 继承 56d6657 (lock 80), 移植 smoke_formalization (路径适配) +
  fixtures (LF 规范化), 48 项 + 9 smoke 全绿, CI 待确认.
- 既有历史 run 不受影响 (非 gate 状态或补决策字段后通过).
### 2026-08-14 会话 (全量功能面审计 + 测试机械同步)
- 审计: 上游 71 个功能文件 vs DSH 全部核实 - 66 字节一致 + 4 LAYERED (SKILL.md,
  sync --check 重放逐字节验证) + 1 有意替换 (doctor.py -> dsh-doctor.py),
  0 缺失 0 差异; 12 个 fixture 目录逐文件齐全.
- 发现真实漂移 (机械同步立刻纠正): 早先手工移植的 4 个 smoke (docstring/尾部换行
  差异) 与 2 个 fixture manifest (JSON 格式差异) 与上游规范版不一致.
- 机制升级 (8a05924): sync-from-parent.py 现在同步 tests 树 - 全部上游 smoke
  (路径重写至 skills/ 布局, smoke_doctor 除外) + 完整 fixtures; --check 也校验
  tests 平价; 上游新增门禁/交接测试从此不可能被漏继承.
- 门禁覆盖映射: B0/任务包/hash 绑定/数值纪律 -> smoke_pipeline_gate; 交接 ->
  smoke_handoff; whiteboard -> smoke_whiteboard; 形式化决策 -> smoke_formalization;
  Lean 扫描/机器证据 -> smoke_lean_verify; 多远程同步 -> smoke_sync_remotes;
  环境 -> smoke_doctor (DSH 版). 48 项 + 9 smoke 全绿, CI 待确认.
### 2026-08-16 会话: 社区市场接入 (安装 dsh-market + 本仓库打包提交社区)
- 任务: 在社区搜索并安装一个插件市场的插件, 然后把本仓库提交到社区.
- 调研结论: 官方 0811 已删除 repository 插件机制, 社区插件统一经 profile bundle 安装
  (dsh.bundle 包进 dsh.profile.bundles 层栈 / 纯 cordis 包走 cordis.patch.yml insert);
  本机 checkout 无 marketplace 子命令, 也无 dsh.skills 字段支持; 技能包插件范式 =
  package.json (dsh.bundle.patch) + index.mjs (FileSystemSkillProvider + customSkillDirs,
  includeDefaultRoots: false 隔离根) + cordis.patch.yml (insert 行).
- 安装市场: dshmarket 1.3.0 (dsh-market, awesome 列表推荐) 装进 web profile
  (dependencies + bundles + minimumReleaseAgeExclude; 免构建授权, 产物已入库);
  重启 dsh web 后设置页出现插件市场.
- 本仓库打包 (e74f163): package.json (name math-research-dsh, version 0.1.0,
  dsh.bundle.patch + marketplace 声明), index.mjs (4 skill 目录注册, 隔离 provider),
  cordis.patch.yml; 新增 scripts/dsh-check-bundle.py 门禁并接入 CI;
  README 双语加社区安装路径 + badge + 目录/规则更新.
- 验证: dsh-check-bundle BUNDLE OK; node --check 通过; validate_all 48 项全绿;
  sync --check 无漂移; 真实 runtime 包 (profiles closure 的 dsh-skill-filesystem)
  发现并加载全部 4 个 skill (正文/描述/resourceBase 正常); CI (e74f163) success.
- 社区提交: 仓库打上 dsh-plugin topic; fork awesome-dsh-plugin 并 PR #445
  (README.md + README.zh.md Skills/技能包分类各一条目); 收录经合并后
  awesome-dsh-plugin.com 与 dsh-market 自动生效 (通常一天内).
- 待办: 重启 dsh web 后可在设置页看到插件市场 (dshmarket); 如用 bundle 安装本仓库
  则与 junction 二选一; PR #445 等待维护者合并.
### 2026-08-16 会话: manage 继承上游 8c 规范 (人类可读 LaTeX 双语证明交付)
- 任务: 在 manage-math-research-program 加入规范 - Lean 验证之后必须有存放 LaTeX
  格式证明的文件夹供人类自然语言阅读, 参考 arXiv 论文规范, 中英两个版本.
- 上游变更 (b2f45c9, 双推 origin+fork): SKILL.md 新增工作流 8c (强制) - Lean 验证
  通过 (FORMALLY_VERIFIED + build_passed + 零 sorry/axiom) 的定理必须在
  `papers/<SLUG>/` 交付 `<SLUG>-en.tex` (arXiv 规范: amsart + amsthm/amsmath/
  hyperref, 摘要/编号定理环境/DOI 或 arXiv 链接, xelatex 零警告) + `<SLUG>-zh.tex`
  (中文对照, 同一陈述/证明结构); 文档头绑定机器验证契约; STRICT/EVIDENCE 标签
  纪律; 证据规则 13 + 完成清单; 模板 assets/proof-paper.template.tex;
  init/validate 创建并校验 papers/; MANIFEST 45 条; cachebuster
  0.1.0+codex.20260815170001; 根 README 中英版本历史.
- 本仓库: sync-from-parent.py 继承 (upstream.lock 81 文件, DSH 层重放, MANIFEST 重
  生成); validate_all 48 项 + BUNDLE OK + 9 冒烟全绿; package.json bump 0.1.1;
  README 双语 manage 行补 papers/ 交付说明.
- 待办: CI 确认; 若用 bundle 安装本仓库则与 junction 二选一.
### 2026-08-16 会话: 继承上游蒸馏第二轮 (搜索/多 agent/Lean/方法论)
- 任务: 在 awesome-dsh-plugin 生态寻找可改良本插件的方法, 方向 = 网络搜索 (arXiv
  等确认问题状态)、多 agent 协作、Lean 验证、数学研究方法.
- 上游 (dfd03f9, 双推): 4 子代理深挖 28 仓库 (全 MIT; eval-harness 许可证未确认仅
  作思想参考). 蒸馏落点: rigorous phase-01/23/45/78 (检索证据契约 status 三态 +
  uncertainty-warnings + fetch_required 目标问题状态确认 + 反例-only 对抗 + 双导线
  ground-truth + covered_scope/residual_risk + 路线假说状态机 + 循环检测 + Forbidden
  moves); workflow Stage B/C (义务认领/缺口回灌/失败聚合/循环检测/Lean 升级通道);
  lean-verify Phase 3-5 (单一 JSON 判定 gate 协议/原子有界检查/同缺口三轮收敛/证伪
  优先裁决); manage §3/§5/8b (检索证据契约/工具溯源/证据边界). 四插件 cachebuster
  0.1.0+codex.20260815171704; MANIFEST 45 条; 根 README 中英版本历史.
- 本仓库: sync 继承 (lock 81); validate_all 48 项 + BUNDLE OK 全绿; package.json
  bump 0.1.2; README 双语蒸馏表新增第二轮 17 行 (四方向), jacobian 从观察中移入
  Lean 蒸馏; 9 冒烟复跑待确认; CI 待确认.
### 2026-08-16 会话: 优化方向落地 (包质量/CI 门禁/蒸馏测试)
- 任务: 用户选定三组优化方向 (快速修复/同步自动化/插件能力增强) 后实施.
- 快速修复: package.json bump 0.1.2 -> 0.1.3 (fbb3566 已改 manage SKILL 未 bump);
  README 中英冒烟数 5 -> 10, 补全 smoke 清单 (含新 smoke_distilled_methods.py).
- CI 门禁: validate_all.py 新增 README smoke parity 检查与本地 worktree version-bump
  守卫; 新增 scripts/check_version_bump.py (PR/push diff 检查); validate.yml 新增
  version-bump job; 父仓库新增 scripts/sync-fork.sh 与 .github/workflows/sync-fork.yml
  (需 FORK_PAT secret).
- 能力增强: 新增 tests/smoke_distilled_methods.py (静态标记覆盖蒸馏方法, 7 组检查);
  关联项目 AGENTS.md 瘦身 (会话日志迁至 state/AGENTS_SESSION_LOG.md), 新增
  docs/sl-project-template.md 与 docs/archive-policy.md + scripts/archive_old_runs.py.
- 校验: validate_all 51 项全绿; BUNDLE OK; 11 个 smoke 全过 (新增
  smoke_version_bump.py 覆盖版本 bump 门禁脚本); sync-check 无漂移
  (skills/ 未改动, lock 仍 81 文件).
- 备注: 父仓库 fork 自动化需在 xsoc1 仓库配置 FORK_PAT 后生效; 本地手动同步可用
  scripts/sync-fork.sh.
### 2026-08-16 会话: 继承“进展全登记 + 每个新结果形式化 scaffold”规则
- 上游 (094937c, 双推): 四插件新增强制规则 - 问题进展/失败路线/新工具全部登记;
  每个新结果 (含 RIGOROUS_PARTIAL_RESULT) 在存在 `lean-proof/` 时必须创建 Lean
  scaffold 并更新形式化进度; run-manifest 形式化决策新增 `scaffold`;
  validate_pipeline.py 对 2026-08-16 后新 run 强制 scaffold/requested; lean-verify
  新增 Scaffold mode + `SCAFFOLDED` 状态 + `assets/lean-scaffold.template.lean`;
  cachebuster `0.1.0+codex.20260816180000`.
- 本仓库: sync 继承 (lock 82 文件), package.json bump 0.1.3 -> 0.1.4;
  validate_all 51 项 + BUNDLE OK + 11 smoke 全绿.
- 备注: 该规则要求后续 run 即使只得到部分结果也要立即搭建 Lean scaffold, 并同步
  `lean-proof/STATUS.md` / `README.md` / `formalization_progress.md`.
### 2026-08-16 会话: 继承“交接手续独立成文”增强
- 上游 (5fcd33f, 双推): 交接记录独立成文并强制包含 `Completed work progress`
  (已完成进度, 后续不得重做) 与 `Tools and methods tried` (尝试过的工具/方法/
  命令 + 结果标记 + 证据路径 + sha256); `validate_pipeline.py` 新增两个必需
  section; workflow/manage cachebuster `0.1.0+codex.20260816183000`.
- 本仓库: sync 继承 (lock 82), package.json bump 0.1.4 -> 0.1.5; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“Lean 中间验证 + 结果覆盖”微调
- 上游 (0a28107, 双推): Lean 验证定位微调 - 中间承重引理尽早机器验证 (避免走
  弯路); 更先进结果可把旧 scaffold/partial/verified 标记 `superseded` 并保留
  历史; 四插件 cachebuster `0.1.0+codex.20260816190000`.
- 本仓库: sync 继承 (lock 82), package.json bump 0.1.5 -> 0.1.6; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“证明文件提交审计流程”
- 上游 (4656a83, 双推): 新增 manage 8e 证明文件提交审计流程 - 提交证明文件必须
  依次经过 仓库比对 -> Lean 验证与审计 -> 依规则加入; 新增模板
  `assets/proof-submission-audit.template.md`; 四插件 cachebuster
  `0.1.0+codex.20260816193000`.
- 本仓库: sync 继承 (lock 83), package.json bump 0.1.6 -> 0.1.7; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“插件效率优化”
- 上游 (f814c03, 双推): 新增 `scripts/scaffold_result.py` (自动生成 Lean
  scaffold + STATUS + progress + audit record) 与 `scripts/index_lean_lemmas.py`
  (生成 `LEMMA_INDEX.md` 复用索引); 引入 Tier 0/1/2 分级验证; 四插件 cachebuster
  `0.1.0+codex.20260816200000`.
- 本仓库: sync 继承 (lock 85), package.json bump 0.1.7 -> 0.1.8; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“Rethlas 方法蒸馏”
- 上游 (059813f, 双推): 新增 `references/rethlas-distilled.md`; rigorous
  phase-45 增加失败综合与反例复用; workflow Stage B 增加 Rethlas 式失败综合/
  反例库/搜索纪律; manage 增加反例库检查; rigorous/manage/workflow cachebuster
  `0.1.0+codex.20260816210000`.
- 本仓库: sync 继承 (lock 86), package.json bump 0.1.8 -> 0.1.9; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“双轨审计协议”
- 上游 (9435f0c, 双推): 新增 `references/dual-track-audit.md` - Danus 式非正式
  审计与 Lean 形式化验证共存 (非正式审计 -> Lean scaffold -> Lean 完整验证 ->
  论文级再验证), 冲突裁决规则, Danus 硬禁止项, 验证矩阵; manage 8e Stage 2 增加
  双轨矩阵; workflow Stage C 增加双轨 gate; lean-verify 增加 coexistence 说明;
  四插件 cachebuster `0.1.0+codex.20260816220000`.
- 本仓库: sync 继承 (lock 87), package.json bump 0.1.9 -> 0.1.10; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“OpenProver token-conscious 协议”
- 上游 (97e4910, 双推): workflow 新增 `references/openprover-absorption.md`
  (Planner action 协议/repo item/theorem.lean 前置骨架/planner history/token
  budget pause+handoff+resume); manage 新增 `assets/budget-state.template.json`
  与任务包 `theorem.lean`/`budget` 字段、摄入时登记 budget_state; rigorous
  phase-12 增加预算耗尽=暂停不丢工作; 追踪记录
  `docs/implementation-tracking-openprover.md`; rigorous/manage/workflow
  cachebuster `0.1.0+codex.20260816230000`.
- 本仓库: sync 继承 (lock 89), package.json bump 0.1.10 -> 0.1.11; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 继承“研究地图”
- 上游 (d59f0ce, 双推): 每个项目维护人类可读、持续更新的 `research_map.md`;
  manage 新增 8f 节 + `assets/research-map.template.md` + `scripts/update_research_map.py`
  (init + append route/finding/failure/avoid/human); workflow Stage A/B/C 边界
  强制更新 + 防钻牛角尖; rigorous 默认工件加入 research_map.md; 追踪记录
  `docs/implementation-tracking-research-map.md`; rigorous/manage/workflow
  cachebuster `0.1.0+codex.20260816240000`.
- 本仓库: sync 继承 (lock 91), package.json bump 0.1.11 -> 0.1.12; validate_all
  51 项 + BUNDLE OK + 11 smoke 全绿.
### 2026-08-16 会话: 修复门禁嵌套 git 仓库误扫 + 研究流水线运行
- 上游 (319a8e1, 双推): validate_pipeline.py 跳过嵌套 git 仓库 (如 `_xsoc1_work`),
  新增 smoke_nested_repo.py; workflow cachebuster `0.1.0+codex.20260816243000`.
- 本仓库: sync 继承 (lock 91), 新增 smoke_nested_repo.py, README 冒烟 11 -> 12,
  validate_all 51 项 + BUNDLE OK + 12 smoke 全绿; package.json bump 0.1.12 -> 0.1.13.
- 关联: 用 math-research-workflow 运行 DensBC O1' (run
  R-20260816T210000Z-densbc-o1p), 在 H_beta + 有限多项式约束子类上闭合 O1',
  双轮独立审计 REPAIRABLE_GAP 均已修复; 报告在
  `reports/pipeline-run-report-densbc-o1p.md`.
### 2026-08-16 会话: lake build 循环防护 + O1' 第二轮
- 上游 (b41c852, 双推): lean-verify 新增 `scripts/lake_build_guard.py` 并集成到
  `verify_lean_project.py --build`: 防止会话反复 `lake build` / 反复 clone
  mathlib4 占满网络/CPU (fresh lock + 近期尝试次数限制 + mathlib 缓存提示);
  新增 smoke_lake_build_guard.py; lean-verify cachebuster `0.1.0+codex.20260816250000`.
- 本仓库: sync 继承 (lock 92), 新增 smoke_lake_build_guard.py, README 冒烟
  12 -> 13, validate_all 51 项 + BUNDLE OK + 13 smoke 全绿; package.json bump
  0.1.13 -> 0.1.14.
- 关联: DensBC O1' 第二轮 run R-20260816T220000Z-densbc-o1p2 闭合 H_lambda
  带状非对角子类 (density <=> ker(T|B_fin)={0}; v_1=x^4 非稠密, 显式障碍);
  性能测试报告 reports/plugin-performance-test-round2.md.
### 2026-08-16 会话: lake build 鲁棒性增强
- 上游 (ce717e6, 双推): lean-verify `verify_lean_project.py --build` 新增
  `--build-targets` (单文件 `lake env lean`, 避免全量 build)、`--use-cache`
  (先 `lake exe cache get`)、`--build-timeout` (超时记为失败); SKILL 新增
  Build robustness; lean-verify cachebuster `0.1.0+codex.20260816260000`.
- 本仓库: sync 继承 (lock 92), validate_all 51 项 + BUNDLE OK + 13 smoke 全绿;
  package.json bump 0.1.14 -> 0.1.15.
### 2026-08-16 会话: 版本号改为语义化 (大版本/小版本)
- 父仓库: 四个插件 version 统一改为 `1.1.0` (不再使用 0.1.0+codex.日期);
  版本规则 = 大版本(架构/能力代际)/小版本(功能批次)/补丁(纯修复);
  README 版本历史压缩为 1.1.0/1.0.0 两行, AGENTS 维护规则同步.
- 本仓库: package.json 从 0.1.15 改为 `1.1.0`, README 版本历史同步压缩,
  维护规则仍按语义化版本升级.
### 2026-08-16 会话: 轻量优先成本分级升级协议
- 父仓库 (0480584, 双推): 新增 rigorous `references/escalation-ladder.md`
  (Tier 0 查与测 / Tier 1 小改动 / Tier 2 中等系统化 / Tier 3 重型并行,
  升级触发器 + 回退 + 记录模板); Phase 4 route card 增加 `cost_tier` /
  `minimal_first_step` / `escalation_criteria`; Phase 5 增加 cheapest
  admissible probe; workflow Stage B 增加 cost-tiered escalation, 白板增加
  `current_cost_tier` / `last_escalation_reason`; manage 任务包增加
  `Max cost tier` / `Escalation policy`; 四插件版本统一 `1.2.0`.
- 本仓库: sync 继承 (lock 93), package.json bump `1.1.0` -> `1.2.0`,
  README 中英版本历史新增 1.2.0 条目; validate_all 待跑.
### 2026-08-23 会话: 继承轻量 reuse 协议 (v1.3.0)
- 上游 (父仓库, 未提交? 待推送): 新增 workflow references/reuse-protocol.md,
  workflow SKILL 轻量 reuse 协议, manage §5 reuse_summary 维护证据,
  rigorous 默认工件新增 reuse_summary.md; 四插件版本统一 1.3.0.
- 本仓库: sync 继承 (lock 94 文件), package.json bump 1.2.0 -> 1.3.0,
  README 中英版本历史新增 1.3.0 条目; 待 validate/commit/push.
### 2026-08-23 会话: 继承工具类作用域生命周期 (v1.4.0)
- 上游 (18105b2): 工具按问题类 retirement/archive, 不删除; 新增
  scripts/manage_tool_lifecycle.py; tool-library-spec/tool-entry.template 增加
  applicability/failure_records; reuse-protocol 按类选择工具.
- 本仓库: sync 继承 (lock 95 文件), package.json bump 1.3.0 -> 1.4.0,
  README 中英版本历史新增 1.4.0 条目.
