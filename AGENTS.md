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
- `tests/` -- fixtures + 22 个 smoke
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
- **测试数量**: 当前 22 个 smoke; 新增 smoke 后同步更新 README 两版与 AGENTS.md.
- **GitHub 网络**: 直连 github.com 失败时, 用本地代理 push:
  `git -c http.proxy=http://127.0.0.1:7897 push origin main` (本机实测可用).

## 会话记录

- 完整旧记录: [AGENTS_HISTORY.md](AGENTS_HISTORY.md). 仅在查找历史决策, benchmark 或故障证据时按关键词读取相关段落.
- 2026-09-05 用户要求: 根据既有 benchmark 优化 Codex 研究插件, 重点完善真实文献读取, agent 可注释工具库与指针表, 以及额度中断续接; 额度恢复后继续实施.
- 本轮方法: 先做确定性 L0, 使用隔离的真实工具卡和 sequence-26 工件回放; 保留主项目原文件和数学状态. 高成本 solver A/B 留待后续匹配实验.
- 功能与验证证据见父仓库 docs/optimization-20260905-results.md; 本地适配版本 1.15.1, 父提交以 upstream.lock.json 为准. 每次维护在本节追加简短结果, 长证据放专门报告.

- 2026-09-05 发布 1.15.1: 从父提交 0af2461 同步 manage 1.8.1 修复, 测试版本断言改用本包版本. 51 项校验, library 7 项, closure-first, bundle 和 sync 检查通过. 当前完整旧记录仍可从 AGENTS_HISTORY.md 查阅.
