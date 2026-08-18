# math-research-dsh

[English: README_EN.md](README_EN.md)

[![Awesome DSH Plugin](https://awesome-dsh-plugin.com/badge.svg)](https://awesome-dsh-plugin.com)

`math-research` Codex 插件市场的 DSH (DeepSeek Harness) 适配版: 4 个 Codex 插件
(rigorous-open-math-research / manage-math-research-program / math-research-workflow /
lean-verify) 以原生 DSH skill 形式发布, 脚本与模板随 bundle 分发.

## 背景与现状

- 上游是 Codex marketplace 仓库, 只能以 Codex 打包格式安装 (plugin.json / openai.yaml /
  marketplace.json / cachebuster), DSH 无法直接消费. 本仓库把每个插件转为一个 DSH skill
  bundle (目录 + SKILL.md frontmatter), 内容与上游保持同步.
- 当前状态 (2026-08-16): 4 个 skill 全部适配完毕; 本机已通过 install.ps1 以 junction
  安装到 `$DSH_HOME/skills`; 安装后 DSH 会话技能目录即时可见 (watcher 跟随 junction);
  仓库校验与 12 个冒烟全绿; GitHub Actions 已接入; 仓库根已打包为官方 bundle 技能包
  (社区一键安装 + 收录申请已提交).

## 仓库间关系

```text
xsoc1/rigorous-open-math-research            Codex 市场父仓库 (public, 上游内容源)
  +-- fork: Zhongshan-Big-Jun/rigorous-open-math-research   组织 fork (随父仓库同步)
xsoc1/math-research-dsh                     本仓库 (DSH 适配, public)
  +-- 单向同步: scripts/sync-from-parent.py 从父仓库拷贝并重放 DSH 层
```

- 本仓库只读消费父仓库, 从不修改它; 父仓库自身的维护规则 (validate_all, cachebuster,
  双仓库推送) 与本仓库互不干扰.
- 上游内容更新时, 在本仓库重跑 `sync-from-parent.py` 即可; CI 的 sync-check job 每次
  push 自动做漂移检查.
- 本仓库不修改 DSH harness 本体, 也不绑定某个 agent preset; 安装到用户技能根
  (`$DSH_HOME/skills`) 后, 任何 standard/cordis preset 会话自动发现这 4 个 skill.

## 工作流与完整流程

- 一轮完整运行 (输入数学问题 → Stage A 管理 → Stage B 求解 → Stage C 验证 →
  提交审计 8e → 结果入库) 的所有分支与终态, 见父仓库:
  [`docs/pipeline-full-flow.md`](https://github.com/xsoc1/rigorous-open-math-research/blob/main/docs/pipeline-full-flow.md)
- 每个项目还会持续维护人类可读的 `research_map.md` (路线/方法/中间结果/失败
  原因/工具/开放方向/avoid list/人类补充), 部分进展也入图.

## Skill 一览

| DSH skill | 角色 | 随包工具 |
|---|---|---|
| `math-research-workflow` | 编排: 管理 -> 研究 -> 验证流水线, 阶段门禁, 中断交接协议 | `scripts/validate_pipeline.py`, `assets/` 模板 |
| `manage-math-research-program` | 项目管理: 项目初始化, 文献, 工具库, 任务包, 已接受知识流水线; Lean 验证后强制交付论文级 LaTeX 双语证明 (`papers/`, arXiv 规范) | `scripts/{init_project,validate_project,sync_remotes}.py`, `assets/` 模板, blueprint 工具 |
| `rigorous-open-math-research` | 求解层: 定理契约, 路线搜索, 对抗性审计, 校准式报告 | `references/`, `assets/` |
| `lean-verify` | Lean 4 形式化审计: sorry/axiom 扫描, 义务级审计, 结构化裁决 | `scripts/verify_lean_project.py`, `assets/` 模板 |

## DSH 如何加载这些 skill

DSH 从以下根目录发现 skill: **用户技能根** `$DSH_HOME/skills` (`$DSH_HOME` 默认
`~/.dsh`), 会话工作区的 **项目技能根** `.dsh/skills` 与 `.agents/skills`, 以及
preset 自带 bundle. 一个 skill 是一个含 `SKILL.md` 的目录, 其 YAML frontmatter
声明 `name` 与 `description`. 用 `skill` 工具加载时返回正文 + `resourceBase`
目录路径; 包内 `references/`, `assets/`, `scripts/` 经该路径读取或执行. 用户消息
首行为 `/skill-name` 时直接加载该 skill (即 Codex `$skill-name` 手势的 DSH 等价物;
上游内容中的一切 `$skill-name` 引用都按此映射).

## 安装

**方式一: 社区一键安装 (官方 bundle 插件)**

```sh
dsh plugin --profile web add github:xsoc1/math-research-dsh
```

仓库根以官方 bundle 技能包格式发布 (`package.json` 声明 `dsh.bundle.patch`,
`index.mjs` 用官方 `FileSystemSkillProvider` 把 4 个 skill 注册为自定义技能根,
只挂载包内目录, 不重扫用户/项目技能根). 安装后重启 `dsh web` 生效, 之后
[dsh-market](https://github.com/dsh-market/dsh-market) 等社区市场可直接检索;
收录申请已提交 [awesome-dsh-plugin](https://awesome-dsh-plugin.com).

> 注意: 方式一与方式二 (junction) 二选一, 不要同时安装, 否则同一批 skill 会双份注册.

**方式二: junction 热更新 (开发/本机使用)**

```powershell
git clone https://github.com/xsoc1/math-research-dsh.git "$env:DSH_HOME\math-research-dsh"
powershell -ExecutionPolicy Bypass -File "$env:DSH_HOME\math-research-dsh\install.ps1"
```

`install.ps1` 把 4 个 bundle 以目录 junction 挂到 `$DSH_HOME\skills`, 之后
`git pull` 即热更新 (DSH skill watcher 跟随链接). 已有普通目录副本时加 `-Force`
替换. 只想装进单个项目: 把 bundles 复制或链接到项目 `.dsh\skills` 即可.

自检:

```powershell
python "$env:DSH_HOME\math-research-dsh\scripts\dsh-doctor.py"
```

## 与父仓库的同步契约

上游内容来自 Codex 市场仓库
[xsoc1/rigorous-open-math-research](https://github.com/xsoc1/rigorous-open-math-research).
本仓库保持上游文件字节级一致, 只叠加一个机器重放的 **DSH 层**:

1. 每个 `SKILL.md` frontmatter 之后注入 `## DSH runtime notes (DSH adaptation)`
   (说明 `$name` -> skill 工具的映射, `resourceBase` 访问方式, 包内 Python 脚本
   运行方式, 以及 DSH 执行模式);
2. 每个 `SKILL.md` 的 changelog 段落迁出到 `references/upstream-changelog.md`
   (保持 skill 加载轻量), 正文替换为一行指针;
3. workflow `SKILL.md` 的 doctor 段落改写为仓库级 `scripts/dsh-doctor.py`
   (Codex 版 `scripts/doctor.py` 移除);
4. 层自有新增文件: `references/dsh-execution.md` (rigorous + workflow),
   `assets/dsh-solve-audit-workflow.js` (workflow), 以及仓库根官方 bundle 打包
   `package.json` / `index.mjs` / `cordis.patch.yml` 与门禁
   `scripts/dsh-check-bundle.py`.

`scripts/sync-from-parent.py` 拷贝父仓库 bundles, 重放 DSH 层, 重生成 manage bundle
的 `MANIFEST.sha256`, 并写入 `upstream.lock.json` (父仓库 commit + 逐文件哈希).

```powershell
# 全量同步 (需要父仓库本地克隆)
git clone https://github.com/xsoc1/rigorous-open-math-research.git "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"
python scripts\sync-from-parent.py --upstream "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"

# 漂移检查 (父仓库前进或 skills/ 被手改时 exit 1)
python scripts\sync-from-parent.py --upstream <父仓库克隆> --check
```

## DSH 性能适配

针对 DSH 运行时的实际机制做的专项适配 (详见各 bundle 的 `references/dsh-execution.md`
与 runtime notes):

| DSH 机制 | 适配 |
|---|---|
| skill 工具加载全文进上下文 | **渐进式披露**: rigorous 正文已拆分为驱动层 (168 行 / ~2.7K tokens, 原 ~11K) + 8 个 phase 引用文件, 按 Phase 经 resourceBase 按需读取; changelog 历史也迁出正文 |
| 工具结果截断 (约 8K, 保留头 4096 + 尾 1024) | 仓库级 `scripts/dsh_run.py` 包装器: verdict 与 FAIL 行放头部, verdict 尾部重复, 完整输出落盘; 脚本惯例 = verdict 在末尾打印 |
| 后台任务 (无超时) | 长计算 (数值扫描, lake build) 一律 `run_in_background: true` + job_output 收集, 不占轮次 |
| spawn 子代理无会话种子 | 对抗性审计/验证用全新 `subagent` (天然零思维链共享); `subagent_fork` 留给上下文续接; **子代理回传契约**: 完整报告落盘, 回复只含 verdict + 路径 + hash |
| workflow 工具 | `assets/dsh-solve-audit-workflow.js` 模板: 每个任务包 solve + audit 并行, 仅合格结果进 verify 阶段 |
| goal 工具 | 多轮目标用 create_goal/get_goal/update_goal 跟踪 |
| Windows 环境 | PYTHONUTF8=1, python 全路径, 避免一行 -c (写临时 .py) |

## 社区方法蒸馏 (2026-08-14)

从开源 DSH 生态吸收并蒸馏进本插件的方法 (纯增量, 不改动已有内容):

| 来源 | 蒸馏内容 | 落点 |
|---|---|---|
| [dsh-deep-research](https://github.com/omdsh-dev/dsh-deep-research) | 答案空间与验收标准前置; 覆盖维度枚举 + coverage_gaps 定向侦察; 边际信息增益停止规则 + 证据三态 confirmed/uncertain/gaps | rigorous phase-01/23/45/12 |
| [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) | 任务依赖声明 + 波次执行 (拓扑分层, 环回退) | workflow 模板 v2 |
| [dsh-multiagent-modes](https://github.com/y08lin4/dsh-multiagent-modes) | 分级回报格式 (汇总→JSON / 阅读→结构化 md / 单一结论→1-3 行+依据+风险); 模型分层 | dsh-execution.md + 模板 v2 |
| [dsh-agent-presets 队长模式](https://github.com/MoreChanger/dsh-agent-presets) | 角色 roster 数据化 (args.roles 注入, 加角色不改模板) | workflow 模板 v2 |
| [dsh_workflow](https://github.com/icetomoyo/dsh_workflow) | workflow 资产化: manifest 头部 (intent/inputs/provenance/limits) | workflow 模板 v2 |
| [dsh-context-doctor](https://github.com/Zhenyu98/dsh-context-doctor) | 上下文注入审计: 指令链 64KB 截断标记 / 技能体积 / 重复段落 / 名字遮蔽 | `scripts/context-audit.py` |
| [dsh-vision](https://github.com/william-jin-cmu/dsh-vision) + [dsh-vision-toolkit](https://github.com/Anionex/dsh-vision-toolkit) | 视觉调用约定 (VLM 输出 = 未验证输入, 回查规则, 免费档/本地端点) | `references/dsh-optional-capabilities.md` (rigorous + manage) |
| [dsh-plugin-mineru](https://github.com/HuanLinOTO/dsh-plugin-mineru) + [dsh-paddle-ocr](https://github.com/omdsh-dev/dsh-paddle-ocr) | 文档解析调用约定 (PDF→结构化 Markdown, 长文档落盘引用) | 同上 + 上游 phase-01 第 9 条 |
| 观察中: [dsh-automation](https://github.com/titanwings/dsh-automation) (定时任务) | 待真实痛点出现再集成 | — |

### 第二轮 (2026-08-16, 四方向)

| 方向 | 来源 | 蒸馏内容 | 落点 |
|---|---|---|---|
| 搜索/状态确认 | [modsearch](https://github.com/liustack/modsearch) | 检索输出契约: status 三态 (ok/degraded/unavailable) + uncertainty vs warnings 二分 + 引擎尝试顺序; 禁止编造相关性分数 | rigorous phase-23 + manage §3 |
| 搜索/状态确认 | [argo](https://github.com/taxueseek/argo) | 目标问题状态确认 (fetch_required, fetch status 四态, 分层确认, 证据强度排序启发, 缺口侦察清单, 跨会话回填) | rigorous phase-23/01 + workflow B0 |
| 搜索/状态确认 | [dsh-zotero](https://github.com/Vncntvx/dsh-zotero) | 本地已读文献先查: 有界证据片段 (预算上限) + 章节名/记录 ID 引用 | rigorous phase-23 + manage §3 |
| 搜索/状态确认 | [dsh-kb-sieve](https://github.com/omdsh-dev/dsh-kb-sieve) | 确定性检索闭环 + OOV 越界门 + 同输入同产出 | rigorous phase-23 语义检索 |
| 搜索/状态确认 | [dsh-web-search-pro](https://github.com/anweat/dsh-web-search-pro) / [dsh-exa-mcp](https://github.com/MicroHEROX/dsh-exa-mcp) | 检索历史键复用防重走; 语义召回 + 全文抓取成对 | manage §3 / rigorous phase-23 |
| 多 agent | [dsh-suite plugin-team-board](https://github.com/whyihaveyou/dsh-suite/tree/main/packages/plugins/plugin-team-board) | 义务认领协议 (claim before work, 唯一所有者, 防重复证明) | workflow Stage B |
| 多 agent | [dsh-proof](https://github.com/EvilIrving/dsh-proof) | 缺口回灌硬规则 (非 PASS 评审输出必须被修订轮消费, 静默丢弃 = 门禁失败) | workflow Stage B |
| 多 agent | [dsh-agent-team-gui](https://github.com/toolclub/dsh-agent-team-gui) | 并行成员失败聚合 (不短路) | workflow Efficiency rules |
| 多 agent | [dsh-trajectory-governance](https://github.com/dfycaly98931680/dsh-trajectory-governance) | 循环检测 (无新机制重试失败路线即阻断) | workflow + rigorous phase-45 |
| Lean | [forge-gates](https://github.com/jinguanghai/deepseek-harness-forge-plugins) | 单一结构化判定 gate 协议 (proved 分支 / 局部反证分支, 禁止自由文本当证据) | lean-verify Phase 3 |
| Lean | [jacobian](https://github.com/morluto/jacobian) | lean.check 原子化: 固定环境 + 请求级临时目录 + 类型化诊断, 无会话不保留源码 | lean-verify Phase 3 |
| Lean | [dsh-rigorquant](https://github.com/linxichen/dsh-rigorquant) | 双导线 ground-truth + 反例-only 对抗者 + 关键断言先 Lean 再实现 + 同缺口三轮收敛 | rigorous phase-78 + workflow Stage C + lean-verify |
| Lean | [Vibe-Mathematics](https://github.com/ChongCyrus/Vibe-Mathematics) | 证伪优先裁决 (已核验反例整体否决; 不确定义务不通过) | lean-verify Phase 4/5 |
| 方法论 | [Aegis](https://github.com/GanyuanRan/Aegis) | 完成声明 = 新鲜证据 + covered scope + residual risk | rigorous phase-78/12 |
| 方法论 | [dsh-science](https://github.com/biociao/dsh-science) | 路线假说状态机 + forward-only; 工具/产物溯源字段 (run/输入/环境/hash + 追加型注记) | rigorous phase-45 + manage §5 |
| 方法论 | [dsh-scholar](https://github.com/lzszq/dsh-scholar) | 证据边界: 非受控输出 (Chat/stdout) 不成为正式证据; 受控 run 冻结环境 | manage 8b 第 8 条 |
| 方法论 | [dsh-design-skills](https://github.com/zhaiyateng/dsh-design-skills) / [dsh-ops-kit](https://github.com/LeslieWylie/dsh-ops-kit) | 契约新增 Forbidden moves 禁用清单; 证据完整性三件套 (prechecks/inventory/integrity) | rigorous phase-01 + manage 8b |

许可证注意: 全部为方法级借鉴 (自撰措辞), 未复制任何仓库文字; 其中
dsh-multiagent-modes 为 CC BY-SA 4.0, 若未来直接引用其文字需同样开源署名.

## 校验

```powershell
python scripts\validate_all.py .      # 结构 / MANIFEST / lock / UTF-8+LF / py_compile / JSON+YAML
python scripts\dsh-check-bundle.py    # 官方 bundle 打包门禁 (package.json / patch / index.mjs / skills)
python scripts\check_version_bump.py --base HEAD^   # CI 版本 bump 门禁 (本地按需)
cd tests
python smoke_pipeline_gate.py         # 流水线门禁 fixtures
python smoke_handoff.py               # 中断交接 fixtures
python smoke_lean_verify.py           # lean-verify 扫描 (无需 Lean 工具链)
python smoke_sync_remotes.py          # 多远程同步 (本地 bare 仓库, 无网络)
python smoke_doctor.py                # dsh-doctor 模拟环境
python smoke_dsh_run.py               # dsh_run 截断感知包装器
python smoke_context_audit.py         # 上下文注入审计
python smoke_formalization.py         # 形式化决策门禁 fixtures
python smoke_whiteboard.py            # whiteboard 门禁 fixtures
python smoke_distilled_methods.py     # 蒸馏社区方法的静态标记覆盖
python smoke_version_bump.py          # 版本 bump 门禁脚本冒烟 (临时 git 仓库)
python smoke_nested_repo.py           # 门禁跳过嵌套 git 仓库回归测试
```

GitHub Actions 每次 push 运行以上全部 + 对父仓库的 `--check` 漂移比较.

## 目录结构

```text
package.json                      官方 bundle 声明 (dsh.bundle.patch / marketplace 信息)
index.mjs                         bundle 入口: FileSystemSkillProvider 注册 skills/
cordis.patch.yml                  层栈 insert 行 (id = index.mjs 的 name, name = 包名)
skills/                         DSH skill bundles (父仓库同步 + DSH 层)
  rigorous-open-math-research/
  manage-math-research-program/   (含 MANIFEST.sha256)
  math-research-workflow/
  lean-verify/
  每个 bundle 内: references/upstream-changelog.md (changelog 迁出)
                  references/dsh-execution.md (rigorous/workflow, 执行手册)
                  assets/dsh-solve-audit-workflow.js (workflow, fan-out 模板)
scripts/
  sync-from-parent.py             父仓库同步 + 层重放 + lock
  validate_all.py                 仓库校验
  dsh-check-bundle.py             官方 bundle 打包门禁
  dsh-doctor.py                   DSH 环境自检
  dsh_run.py                      截断感知脚本包装器 (verdict 头尾 + 完整日志落盘)
  check_version_bump.py           CI 版本 bump 门禁 (skills/或 bundle 入口变更必须 bump package.json)
tests/                            冒烟测试 + fixtures
upstream.lock.json                父仓库 commit + 逐文件哈希
install.ps1                       junction 安装到 $DSH_HOME/skills
```

## 版本历史

| 版本 | 日期 | 摘要 |
| --- | --- | --- |
| 0.1.12 | 2026-08-16 | 研究地图 (research_map.md): 实时记录路线/方法/失败/工具/人类补充 |
| 0.1.11 | 2026-08-16 | OpenProver token-conscious: planner action/repo/theorem.lean/history + 预算 pause-resume |
| 0.1.10 | 2026-08-16 | 双轨审计: Danus 式非正式审计 + Lean 形式化共存 |
| 0.1.9 | 2026-08-16 | Rethlas 方法蒸馏 (失败综合/反例复用/搜索纪律) |
| 0.1.8 | 2026-08-16 | 效率优化: scaffold/审计脚本 + Lean 分级验证 + lemma 索引 |
| 0.1.7 | 2026-08-16 | 证明文件提交审计流程 8e |
| 0.1.6 | 2026-08-16 | Lean 中间验证 + superseded 覆盖 |
| 0.1.5 | 2026-08-16 | 交接手续独立成文 |
| 0.1.4 | 2026-08-16 | 进展全登记 + 每个新结果 scaffold |
| 0.1.3 | 2026-08-16 | README 同步 + CI 版本 bump 门禁 + 蒸馏方法冒烟 |

## 维护规则

1. 每次变更后运行 `python scripts/validate_all.py .`.
2. 不手改同步文件: 上游内容改动走父仓库, 然后重跑 `sync-from-parent.py`; DSH 层改动
   只允许改该脚本内的层常量.
3. README 中英两版必须同步更新 (本文件 + README_EN.md, 顶部互链).
4. 新文件一律 UTF-8 无 BOM, LF 换行, 英文标点.
5. 内容变更 (skill 正文/脚本) 时同步 bump `package.json` 的 `version`, 让市场能检出更新.
6. 提交后按 project.json 的 git_sync.push_order 推送 (当前只有 origin).

版权: MIT (与父仓库一致).
