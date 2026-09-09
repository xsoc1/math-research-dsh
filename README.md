# math-research-dsh

[English](README_EN.md)

面向长期数学研究的 DSH (DeepSeek Harness) 技能包. 它将
[math-research 父插件](https://github.com/xsoc1/rigorous-open-math-research)
单向适配为四个可独立使用的 skill, 帮助研究者阅读文献, 积累可批注的工具与经验,
续接研究任务, 并在需要时使用 Lean 验证.

当前版本为 **2.0.0**, 同步自父仓库已发布 main 提交
[`72a1cc17`](https://github.com/xsoc1/rigorous-open-math-research/commit/72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803).
[upstream.lock.json](upstream.lock.json) 记录完整父提交和包内文件哈希.

## 选择入口

| Skill | 适用工作 |
| --- | --- |
| `math-research-workflow` | 选择研究工具, 维护当前进展, 续接会话与实际任务 |
| `manage-math-research-program` | 阅读文献, 工具卡与批注, 经验比较, 人可编辑的理解页面, Blueprint 已接受知识 |
| `rigorous-open-math-research` | 发展证明或反例, 解释成功与失败路线, 按问题需要审计论证 |
| `lean-verify` | 编译反馈, 精确目标与传递公理检查, 语义复核和可复现证据 |

2.0 提供工作方法和可执行工具. 研究者与 agent 根据问题选择方法, 协作方式和验证范围.
旧 sealed checkpoint 与流水线仍有兼容工具; 旧完整校验需要显式 `--legacy-v1`.
历史实验的阶段, 角色和额度规则仅属于对应的旧记录.

DSH 的 `skill` 工具按准确名称加载技能, 返回正文与 `resourceBase`. 包内文件和
Python helper 从该路径定位. 父插件中的 `$skill-name` 在此对应 DSH `skill` 工具;
也可在用户消息首行使用 `/skill-name`.

## 安装

以下两种安装方式二选一, 避免重复注册同一批 skill.

**Bundle 安装**:

```sh
dsh plugin --profile web add github:xsoc1/math-research-dsh
```

`package.json`, `cordis.patch.yml` 和 `index.mjs` 使用 DSH 的
`FileSystemSkillProvider` 注册包内技能根. 新安装按 DSH 的 profile 重载方式生效.

**本地开发与 junction 安装**:

```powershell
if($env:DSH_HOME)
{
	$DshHomePath = $env:DSH_HOME
}
else
{
	$DshHomePath = Join-Path $HOME '.dsh'
}
$DshRepoPath = Join-Path $DshHomePath 'math-research-dsh'
git clone https://github.com/xsoc1/math-research-dsh.git $DshRepoPath
powershell -ExecutionPolicy Bypass -File (Join-Path $DshRepoPath 'install.ps1')
python (Join-Path $DshRepoPath 'scripts/dsh-doctor.py')
```

`install.ps1` 将四个目录链接到用户技能根. 项目安装也可使用 `.dsh/skills` 或
`.agents/skills`. 普通目录副本的替换需要显式选择 `install.ps1 -Force`.
仓库脚本 `dsh_run.py` 可保存完整日志, `context-audit.py` 可检查上下文体积;
它们是 checkout 工具, 不随 npm 的 `skills/` bundle 分发.

## 单向同步与维护

父仓库是研究方法和数学实现的唯一内容源. 本仓库只维护 DSH 加载方式, 布局映射,
打包和测试适配. 对上游内容的修改先进入父仓库, 再重放
[scripts/sync-from-parent.py](scripts/sync-from-parent.py).

同步器复制四个 skill, 合并 workflow/Lean 的插件级 `scripts/` 和 `assets/`,
将 manage 的 `runtime/` 放到对应 skill 根, 同步根 smoke/unit tests 与 fixtures,
并改写 2.0 指南链接. Q9 测试沿用父源码的祖先目录发现逻辑, benchmark 不随 bundle 分发.
每次正式同步生成 manage `MANIFEST.sha256` 和父提交绑定的 `upstream.lock.json`.

```sh
python scripts/sync-from-parent.py --upstream <clean-parent-clone> --expect-commit <full-parent-commit>
python scripts/sync-from-parent.py --upstream <clean-parent-clone> --expect-commit <full-parent-commit> --check
python scripts/validate_all.py .
python scripts/dsh-check-bundle.py
```

工作中的父源码可用 `--preview <new-external-directory>` 在外部目录试算, 正式目录不变.
预览包含 `PREVIEW.json`, 不代表已从冻结提交发布. 具体命令及证据范围见
[2.0 发布验证](docs/v2-release-validation.md).

维护规则:

1. 每次变更运行仓库校验及相关行为测试. 提交前做 bundle 与 sync 检查.
2. 不手改同步的 `skills/`, tests 或 docs. DSH 差异只通过同步脚本的层常量与明确路径改写重放.
3. 两份 README 顶部互链, 同步维护测试索引. 文本使用 UTF-8 无 BOM, LF 和英文标点.
4. 内容变更同步提升 `package.json` 版本. 提交后按 `project.json` 的 `git_sync.push_order` 推送.
5. 正式同步使用 canonical clone 的已发布 main; 工作源码与未发布候选仅用于外部预览.
6. 本仓库适配不修改 harness, profile 或 auth. 安装与进程操作由实际部署任务决定.

## 测试索引

当前保留 21 个根 smoke, 可逐个执行 `python tests/<filename>`. 1.x 测试验证兼容实现,
不是 2.0 研究行为要求. 根 unit tests 使用 `python -m unittest discover -s tests -p 'test_*.py' -v`.
测试环境安装 `pyyaml` 和 `jsonschema`; 可选任务模板的行为测试使用 Node.js.

| 范围 | 根测试文件 |
| --- | --- |
| DSH 适配与打包 | `test_sync_from_parent.py`, `smoke_doctor.py`, `smoke_dsh_run.py`, `smoke_context_audit.py`, `smoke_version_bump.py` |
| 2.0 续接 | `test_research_state.py`, `smoke_recovery_status.py` |
| 文献与观测 | `smoke_research_library.py`, `smoke_performance_metrics.py`, `smoke_skill_sources.py` |
| Blueprint 与 Git | `smoke_blueprint_gateway.py`, `smoke_sync_remotes.py` |
| Lean 兼容 | `smoke_lean_verify.py`, `smoke_lake_build_guard.py` |
| 1.x 流水线兼容 | `smoke_pipeline_gate.py`, `smoke_scoped_pipeline.py`, `smoke_nested_repo.py`, `smoke_closure_first.py` |
| 1.x 状态与交接兼容 | `smoke_handoff.py`, `smoke_checkpoint_resume.py`, `smoke_formalization.py`, `smoke_formalization_handoff.py`, `smoke_whiteboard.py` |

包内插件测试:

- `skills/manage-math-research-program/scripts/tests/`: `test_research_experience.py`,
  `test_research_library_v2.py`, `test_library_q9_reuse.py`.
- `skills/lean-verify/scripts/tests/`: `test_v2_verifier.py`, `test_v2_lean_real.py`.

Q9 测试在祖先目录寻找 `benchmarks/codex-20260908-q9/evidence`.
bundle 缺少原件时明确 SKIP; 此时直接请求 `--output` 回放会失败并说明缺少原件.
Lean 实测通过
`LEAN_VERIFY_REAL_LEAN` 指定固定工具链, 可选 `LEAN_VERIFY_REAL_LAKE`;
未配置时明确跳过, 不计为编译验证通过. `LEAN_VERIFY_TEST_TMPDIR` 可指定测试临时目录,
默认使用系统临时目录. CI 在 Windows/Linux 跑可移植测试, 另由
`leanprover/lean-action@v1` 按 fixture 固定 4.31.0 并显式启用真实 Lean 测试.
包目录为 `tests/fixtures/lean-v2-runtime`, 同步保留 `lean-toolchain`, `lakefile.toml`
及父仓库实际生成的 `lake-manifest.json`; `.lake/` 构建缓存不随同步复制.
CI 在该固定工具链目录启动测试, helper 在各自固定了 `lean-toolchain` 的临时项目中执行 Lean.
sync-check 从 lock 固定的父提交运行同步检查与 Q9 原件回放, 保存实际证据.

## 文件与历史

- `skills/`: 单向同步的技能, helper, runtime, 参考资料与模板.
- `scripts/`, `tests/`: DSH 维护工具与行为测试.
- `docs/`: 同步指南与 DSH 发布验证说明.
- [AGENTS.md](AGENTS.md): 工作方法和本轮维护记录.
- [AGENTS_HISTORY.md](AGENTS_HISTORY.md): 旧维护, 故障与方法来源记录; 各技能历史位于 `references/changelog.md`.

许可证: [MIT](LICENSE).
