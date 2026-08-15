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
