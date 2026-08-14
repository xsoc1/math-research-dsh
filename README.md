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
   运行方式);
2. 每个 `SKILL.md` 追加 DSH changelog 条目;
3. workflow `SKILL.md` 的 doctor 段落改写为仓库级 `scripts/dsh-doctor.py`
   (Codex 版 `scripts/doctor.py` 移除).

`scripts/sync-from-parent.py` 拷贝父仓库 bundles, 重放 DSH 层, 重生成 manage bundle
的 `MANIFEST.sha256`, 并写入 `upstream.lock.json` (父仓库 commit + 逐文件哈希).

```powershell
# 全量同步 (需要父仓库本地克隆)
git clone https://github.com/xsoc1/rigorous-open-math-research.git "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"
python scripts\sync-from-parent.py --upstream "$env:DSH_HOME\_math-research-upstream\rigorous-open-math-research"

# 漂移检查 (父仓库前进或 skills/ 被手改时 exit 1)
python scripts\sync-from-parent.py --upstream <父仓库克隆> --check
```

## 校验

```powershell
python scripts\validate_all.py .      # 结构 / MANIFEST / lock / UTF-8+LF / py_compile / JSON+YAML
cd tests
python smoke_pipeline_gate.py         # 流水线门禁 fixtures
python smoke_handoff.py               # 中断交接 fixtures
python smoke_lean_verify.py           # lean-verify 扫描 (无需 Lean 工具链)
python smoke_sync_remotes.py          # 多远程同步 (本地 bare 仓库, 无网络)
python smoke_doctor.py                # dsh-doctor 模拟环境
```

GitHub Actions 每次 push 运行以上全部 + 对父仓库的 `--check` 漂移比较.

## 目录结构

```text
skills/                         DSH skill bundles (父仓库同步 + DSH 层)
  rigorous-open-math-research/
  manage-math-research-program/   (含 MANIFEST.sha256)
  math-research-workflow/
  lean-verify/
scripts/
  sync-from-parent.py             父仓库同步 + 层重放 + lock
  validate_all.py                 仓库校验
  dsh-doctor.py                   DSH 环境自检
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
