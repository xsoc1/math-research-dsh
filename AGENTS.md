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
- `tests/` -- fixtures + 21 个 smoke + DSH 同步与 2.0 续接 unit tests
- `package.json` / `index.mjs` / `cordis.patch.yml` -- 官方 bundle 技能包 (社区一键安装)
- `scripts/dsh-check-bundle.py` -- bundle 打包门禁 (package.json/patch/index.mjs/skills)
- `upstream.lock.json` -- 父仓库 commit + 逐文件哈希
- `install.ps1` -- 安装到 $DSH_HOME/skills 的 junction (热更新)

## 维护规则

1. 每次变更后运行 `python scripts/validate_all.py .` (Python 3.10+, 建议 PYTHONUTF8=1).
2. 禁止手改同步文件: 上游内容改动走父仓库然后重跑 sync-from-parent.py; DSH 层只维护
   加载说明, 布局映射和测试输出目录. 简短 2.0 指南保留父源码的研究选择.
3. 父仓库冻结后: `sync-from-parent.py --upstream <clean-clone> --expect-commit <full-commit>`
   重新同步, 再运行相同命令加 `--check`. CI 从 lock 固定的父提交检查漂移.
4. 所有文本文件 UTF-8 无 BOM, LF 换行, 英文标点.
5. 提交后按 project.json 的 git_sync.push_order push (当前只有 origin).
6. 本机安装用 install.ps1 (junction 热更新); `git pull` 后无需重装.
7. README 中英两版必须同步更新 (README.md 中文 + README_EN.md 英文, 顶部互链).
8. 内容变更 (skill 正文/脚本) 时同步 bump package.json 的 version.
9. bundle 安装与 junction 安装二选一, 不要同时用 (同一批 skill 会双份注册).
10. 新代码使用 tab 缩进, snake_case 函数名和 PascalCase 多词变量名.

## 2.0 发布工作方法

- 当前授权: 用户已确认父提交 72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803 发布到
  origin/main, fork/main 及两处 v2.0.0, 父 CI 34336134215 全部通过. 实际同步,
  DSH 提交推送和发布 CI 验证均已获授权, 无需再次确认.
- 本机真实验收优先用原生 Windows Python + Lean.exe. 保存验收输入的逐文件哈希与原位
  测试工件. 发布后若对应输入字节一致, 可复用适用的行为测试结果; 不复制证明 receipt
  并认定其在新路径仍 current. 实际同步后仍运行 sync --check, bundle/结构检查和发布 CI.
- 当前只维护本仓库. 父工作目录 `_xsoc1_work` 由协调者维护; canonical clone 是
  `~/.dsh/_math-research-upstream/rigorous-open-math-research`.
- 以后尚未发布的父候选只用 `--preview <new-external-directory>` 进行迁移检查,
  以 PREVIEW.json 标记未发布源码. 正式同步必须核对已发布 main 的完整 SHA.
- 保留现有 bundle/junction 安装状态. 本轮不启动子 agent, 不重启 DSH, 不修改 auth/profile.
- 先核对遗留 diff, 再修改适配器, 然后在外部预览执行 README 索引和 CI 所列测试.
  比较实际安装文件前后哈希, 报告实际通过与 SKIP, 冻结后重跑最终同步与发布验证.
- Q9 直接继承父测试的祖先目录发现和缺原件 SKIP; 不改写 REPO_ROOT 或虚构外部数据.
  显式原件回放在固定父源码执行. Lean 可移植测试默认报告真实编译 SKIP; 专门 CI 任务
  按 `tests/fixtures/lean-v2-runtime/lean-toolchain` 固定 4.31.0 后显式启用真实编译.
- 长命令和证据范围见 [docs/v2-release-validation.md](docs/v2-release-validation.md).

## 注意事项 (Notes for future agents)

- **版本 bump 是硬门禁**: 修改 `skills/`、`index.mjs` 或 `cordis.patch.yml` 时必须同步
  bump `package.json`; CI 的 `version-bump` job 和本地 `validate_all.py` 都会检查.
- **上游同步纪律**: 不要手改 `skills/` 下从父仓库同步来的文件; 上游内容变更走
  `xsoc1/rigorous-open-math-research`, 然后重跑 `scripts/sync-from-parent.py`.
- **两种安装方式互斥**: `dsh plugin add github:xsoc1/math-research-dsh` (bundle) 与
  `install.ps1` (junction) 只能二选一, 同时安装会导致同一批 skill 双份注册.
- **README 中英同步**: README.md 与 README_EN.md 必须同步更新; `validate_all.py` 会
  检查所有 `tests/smoke_*.py` 是否都出现在两份 README 中.
- **测试索引**: 当前 21 个 smoke; 新增根 smoke/unit test 后同步更新 README 两版.
- **GitHub 网络**: 直连 github.com 失败时, 用本地代理 push:
  `git -c http.proxy=http://127.0.0.1:7897 push origin main` (本机实测可用).

## 会话记录

- 完整旧记录: [AGENTS_HISTORY.md](AGENTS_HISTORY.md). 仅在查找历史决策, benchmark 或故障证据时按关键词读取相关段落.
- 2026-09-05 用户要求: 根据既有 benchmark 优化 Codex 研究插件, 重点完善真实文献读取, agent 可注释工具库与指针表, 以及额度中断续接; 额度恢复后继续实施.
- 本轮方法: 先做确定性 L0, 使用隔离的真实工具卡和 sequence-26 工件回放; 保留主项目原文件和数学状态. 高成本 solver A/B 留待后续匹配实验.
- 功能与验证证据见父仓库 docs/optimization-20260905-results.md; 本地适配版本 1.15.1, 父提交以 upstream.lock.json 为准. 每次维护在本节追加简短结果, 长证据放专门报告.

- 2026-09-05 发布 1.15.1: 从父提交 0af2461 同步 manage 1.8.1 修复, 测试版本断言改用本包版本. 51 项校验, library 7 项, closure-first, bundle 和 sync 检查通过. 当前完整旧记录仍可从 AGENTS_HISTORY.md 查阅.

- 2026-09-06: 1.15.1 发布 CI 通过 (2b80ea4). 上游仅补发布文档后将 lock 前移至 6d6d739, skill 内容和版本不变; canonical clone 与父仓库远端一致.

- 2026-09-09 用户要求: 从意外中断处恢复有界 2.0 DSH 适配, 接手 README 中英版,
  package 2.0.0, sync/validate 修改, 同步 unit test 及旧 distilled smoke 删除.
  既有父仓库/fork/DSH 发布计划已获授权, 本轮等协调者给出冻结父提交再实际同步和提交.
  协调者补充: library smoke 改为隔离损坏批注并保留正常命中; Q9 已使用真实 evidence
  祖先目录发现并明确跳过缺数据; 保留新版 Lean portable tests 与 4.31.0 fixture/CI.
  本轮方法: 移除旧 Q9 专用改写, 仅适配 Lean 测试临时目录, 扩展 Linux/Windows CI,
  保留简短运行说明与可选任务模板. 检查结果记录在发布验证说明和用户指定 prep report.
- 2026-09-09 预览实测: Linux 21 个 smoke 通过. DSH 包装器 smoke 改用外部临时程序,
  验证退出码与完整日志, 避免假定旧流水线是默认行为. 原生 Windows/Python 3.10 暴露
  续接测试的分隔符断言, 已通过同步层的 Path.as_posix 路径适配处理. library 两平台
  各 25 项通过, Q9 缺原件 SKIP 1 项, 直接回放请求明确失败且不创建输出.
  父 Lean 路线测试的简化证据与新版 manifest 重检不匹配, Windows mock 还依赖 os.killpg;
  这两项作为父源码冻结前待修问题交还协调者, 不在 DSH 层放宽证据校验.
- 2026-09-09 有界刷新: 已接收父源码的路线测试修复, Linux Lean portable 12 项通过,
  真实 Lean 11 项明确 SKIP. 新增 schema 测试的 jsonschema 依赖已补入 DSH CI.
  Windows 根测试为 20 项通过 + 2 项 POSIX 专用 SKIP; 父 Lean timeout mock 的
  os.killpg Windows 错误仍待协调者修复. 正式冻结后须重新同步并验证, 预览不计发布.
- 2026-09-09 后续协调: 用户报告 Windows Lean mock 已修复, recovery 最终为 Windows 26
  通过, Linux 24 通过 + 2 项 Windows 专用 SKIP; 尚待最终复查和冻结, 本 sidecar 未复跑.
  用户要求不再生成父工作源码预览. CI fixture 新增 lakefile.toml 和实际 lake.exe update
  生成的 lake-manifest.json, 因 lean-action v1 即使关闭自动配置/构建仍要求 manifest.
  方法: 保留三文件源内容, 同步前检查 fixture 完整性并排除 .lake 缓存, CI 在
  tests/fixtures/lean-v2-runtime 固定工具链目录启动. Elan 无默认工具链, 不在未固定
  工具链的仓库根调用 Lean. 本轮仅运行同步 unit tests 和只读检查, 不实际同步或提交.
  结果: 同步 unit tests 在 Linux 和原生 Windows 各 9 项通过, 仓库 51 项校验通过;
  三个 fixture 文件待同步内容与父源码一致, 120 个已安装受保护文件哈希未变.
- 2026-09-09 用户重新授权并行准备: 候选 72a1cc17 已提交且干净, 全部定向复查完成,
  父 CI 34336134215 仍运行. 方法: 从该提交建立独立源码副本并使用现有 preview 流程,
  明确未发布, 启用原生 Windows 的完整 15 项真实 Lean 测试与适配验收. 新版真实测试
  也使用 jsonschema, 已加入对应 DSH CI 任务. 用户确认 published main 前保持实际安装不变.
- 2026-09-09 用户确认正式发布: 父 main/fork 和 v2.0.0 均为 72a1cc17, 父 CI 五项
  全通过, 包括真实 Lean 15 项. 已授权本 sidecar 实际同步, 提交推送及 CI 核验.
  本机原记录的 canonical 副本缺失, 从官方已发布 main 重建并核对完整提交.
  方法: 逐文件比较外部预览和实际同步, 在实际 DSH 目录运行当前测试, 保留原位
  Lean 工件; 协调者单独负责 Codex 安装验收, 本轮保持 DSH 安装方式和进程配置.
- 2026-09-09 实际同步: clean canonical main/tag 均为 72a1cc17, sync 与 sync --check
  通过, lock 覆盖 140 文件. 外部预览和实际目录的 221 个代码/测试/配置输入字节一致.
  已通过 51 项结构校验, bundle, 全部 21 smoke, Windows 根测试 36 项,
  Linux 根测试 34 项 + 2 项 Windows 专用 SKIP. 两平台 library 各 25 项通过 +
  1 项缺可选 Q9 原件 SKIP, 两平台 Lean portable 各 12 项通过. 固定父源 Q9 回放通过.
  原生实际 Lean 15 项验收与发布 CI 的日志和最终状态保存在外部 dsh-prep-report.md;
  证明 receipt 留在原位测试项目, 不作路径重绑定. index/patch/install 内容哈希保持原值.
