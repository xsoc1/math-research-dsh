# math-research-dsh

[English: README_EN.md](README_EN.md)

`math-research` Codex 插件市场的 DSH (DeepSeek Harness) 适配版: 4 个 Codex 插件
(rigorous-open-math-research / manage-math-research-program / math-research-workflow /
lean-verify) 以原生 DSH skill 形式发布, 脚本与模板随 bundle 分发.

## 背景与现状

- 上游是 Codex marketplace 仓库, 只能以 Codex 打包格式安装 (plugin.json / openai.yaml /
  marketplace.json / cachebuster), DSH 无法直接消费. 本仓库把每个插件转为一个 DSH skill
  bundle (目录 + SKILL.md frontmatter), 内容与上游保持同步.
- 当前状态 (2026-08-14): 4 个 skill 全部适配完毕; 本机已通过 install.ps1 以 junction
  安装到 `$DSH_HOME/skills`; 安装后 DSH 会话技能目录即时可见 (watcher 跟随 junction);
  仓库校验与 5 个冒烟全绿; GitHub Actions 已接入.

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

## Skill 一览

| DSH skill | 角色 | 随包工具 |
|---|---|---|
| `math-research-workflow` | 编排: 管理 -> 研究 -> 验证流水线, 阶段门禁, 中断交接协议 | `scripts/validate_pipeline.py`, `assets/` 模板 |
| `manage-math-research-program` | 项目管理: 项目初始化, 文献, 工具库, 任务包, 已接受知识流水线 | `scripts/{init_project,validate_project,sync_remotes}.py`, `assets/` 模板, blueprint 工具 |
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
4. 层自有新增文件: `references/dsh-execution.md` (rigorous + workflow) 与
   `assets/dsh-solve-audit-workflow.js` (workflow).

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
| 观察中: [jacobian](https://github.com/morluto/jacobian) (数学内核) / [dsh-automation](https://github.com/titanwings/dsh-automation) (定时任务) | 待真实痛点出现再集成 | — |

许可证注意: 全部为方法级借鉴 (自撰措辞), 未复制任何仓库文字; 其中
dsh-multiagent-modes 为 CC BY-SA 4.0, 若未来直接引用其文字需同样开源署名.

## 校验

```powershell
python scripts\validate_all.py .      # 结构 / MANIFEST / lock / UTF-8+LF / py_compile / JSON+YAML
cd tests
python smoke_pipeline_gate.py         # 流水线门禁 fixtures
python smoke_handoff.py               # 中断交接 fixtures
python smoke_lean_verify.py           # lean-verify 扫描 (无需 Lean 工具链)
python smoke_sync_remotes.py          # 多远程同步 (本地 bare 仓库, 无网络)
python smoke_doctor.py                # dsh-doctor 模拟环境
python smoke_dsh_run.py               # dsh_run 截断感知包装器
```

GitHub Actions 每次 push 运行以上全部 + 对父仓库的 `--check` 漂移比较.

## 目录结构

```text
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
  dsh-doctor.py                   DSH 环境自检
  dsh_run.py                      截断感知脚本包装器 (verdict 头尾 + 完整日志落盘)
tests/                            冒烟测试 + fixtures
upstream.lock.json                父仓库 commit + 逐文件哈希
install.ps1                       junction 安装到 $DSH_HOME/skills
```

## 维护规则

1. 每次变更后运行 `python scripts/validate_all.py .`.
2. 不手改同步文件: 上游内容改动走父仓库, 然后重跑 `sync-from-parent.py`; DSH 层改动
   只允许改该脚本内的层常量.
3. README 中英两版必须同步更新 (本文件 + README_EN.md, 顶部互链).
4. 新文件一律 UTF-8 无 BOM, LF 换行, 英文标点.
5. 提交后按 project.json 的 git_sync.push_order 推送 (当前只有 origin).

版权: MIT (与父仓库一致).
