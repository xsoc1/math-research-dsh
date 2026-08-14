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
