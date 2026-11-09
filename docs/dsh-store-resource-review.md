# DSH STORE #1185: 九项资源的逐项审查说明

用本说明和[机器可读清单](dsh-store-resource-review.json)核对各资源的用途、调用边界、字节数、原字节和 LF 规范化 SHA-256、Git blob 及父源对应. 2.0.5 保留全部 140 个原研究资源, 包内研究代码与
[2.0.4](https://github.com/xsoc1/math-research-dsh/commit/2ddaa456f8b801efa321deb474abcbcda4a88a69) 相同.

## 当前阻断在哪里

[2026-10-16 维护方回复](https://github.com/AI-Scarlett/DSH-Store/issues/1185#issuecomment-6213277159)要求解释 Lean 模板、校验清单、Blueprint 占位文件和 Mermaid. 2.0.4 已提供这六项说明. 用 [Store 当前扫描器 ac44d89](https://github.com/AI-Scarlett/DSH-Store/tree/ac44d89f1f897ad0cdf0c85e9104381caf5ca191) 对 2.0.4 的固定 Git 树作只读重放: 150 个分发文件中, 62 个源文件进入扫描, Mermaid 已在扫描范围, 仍有 8 个文件类型未获扫描覆盖. 状态原因只枚举前五项, 不能当作完整清单.

本版补充此前漏记的 `evidence_inventory.csv` 和两份 `.tex` 模板. 下列九项是仍未覆盖的八项加上已纳入扫描的 Mermaid. [Store 准入逻辑](https://github.com/AI-Scarlett/DSH-Store/blob/ac44d89f1f897ad0cdf0c85e9104381caf5ca191/src/admission-review.mjs)会先将扫描不完整的固定源码判为 `incomplete`; 随包作者说明不能替代这一门禁. 在保留研究功能的前提下, 需要 Store 补全这些类型的覆盖, 再对实际文件、网络和命令权限作独立准入判断.

清单展开 manage `MANIFEST.sha256` 的全部成员并绑定调用源码.
其中 `scripts/sync-from-parent.py` 和 `scripts/validate_all.py` 是 checkout 维护工具,
用于解释清单的生成和核对, 不随技能包运行.

## 完整性对应

根 [upstream.lock.json](../upstream.lock.json) 绑定父提交 `72a1cc17ce98f3d3fd3b001d7b25d442ba2d3803` 和适配后的 140 个资源的 LF 规范化摘要.
八项直接复制资源的 Git blob 已与该父提交的原文件比对; `MANIFEST.sha256` 是 DSH 同步器在布局/正文适配后生成的派生文件, 不冒称父仓库原始 manifest.
它完整列出 manage bundle 除清单自身外的成员. 根 lock 再绑定 manifest 自身, 避免自摘要循环.

校验门禁同时检查九项资源覆盖、重复记录、摘要、清单全部成员、调用源码和引用锚点.
提供 tarball 时, 它在内存中逐成员对比本次源码, 并拒绝额外、重复及非普通文件成员.
核对过程不运行 Lean、项目初始化器或其他随包研究程序.

## 1. Lean scaffold

路径: `skills/lean-verify/assets/lean-scaffold.template.lean`.

这是手工选用的形式化骨架, 头部保留来源、结果状态与开放义务说明, 正文保留两个 `sorry` 和 `<Namespace>` 等未替换占位符.
当前分发代码没有按该模板名读取文件的直接调用. 技能正文公开 `scripts/` 与 `assets/` 作为用户可选资源.
文件本身没有文件操作、子进程或网络 API; 填写后选择编译将进入用户的 Lean/Mathlib 工程及其导入代码.
原模板不能充当已完成证明, 也不会随 DSH Bundle 加载而编译.

## 2. Lean declaration probe

完整路径: `skills/lean-verify/scripts/LeanVerifyProbe.lean.template`.
维护方回复中的 `scripts/LeanVerifyProbe.lean.template` 指这一 skill 内路径.

这是实际会执行的 Lean 元程序. `verify_lean_project.py:extract_target` 在用户请求验证后读取它,
用 `.expandtabs(2)` 生成临时 `LeanVerifyProbe.lean`, 调用外部 Lean 编译,
再从 `InspectRoot.lean` 导入并调用 `#lean_verify_v2`.
探针读取 Lean Environment 中的声明、类型、传递公理、依赖和导入模块,
进行预期类型比较, 最后通过 `IO.FS.writeFile` 写出 JSON.
当前 Python caller 的输出是该次 `WorkDir/declaration.json`.

模板自身没有网络请求或子进程启动 API. 外部 Lean 由 Python caller 启动;
用户工程的 Lake 配置、导入模块和提交的 Lean 预期类型源码属于可执行代码, 此探针不提供沙箱.
所选环境若需要获取依赖, 其网络行为属于该环境及工作流.
生成源码、编译结果和目标输出由原证据机制记录;
`lean_evidence.py` 另核对生成探针等于当前模板 `.expandtabs(2)` 的内容.
这些机制用于核验身份与执行结果; 数学语义与独立审查仍须另外核查.

## 3. manage 哈希清单

路径: `skills/manage-math-research-program/MANIFEST.sha256`.

这是纯文本数据. 每行格式为 SHA-256、两个空格和 `./` 相对路径.
`scripts/sync-from-parent.py:regen_manifest` 按路径排序生成它;
`scripts/validate_all.py:check_manifest` 读取目标资源并核对摘要及覆盖.
机器可读资源说明逐项展开它的完整成员对应, 新门禁另外拒绝重复项和根目录外路径.
Bundle 入口不读取或执行此文件; 清单不作为命令列表或执行许可.
摘要相符说明字节对应, 不能由此认定被列出的脚本安全或数学正确.

## 4-5. 两个 Blueprint 目录占位文件

路径分别为:

- `skills/manage-math-research-program/assets/blueprint-accepted-knowledge/backups/.gitkeep`.
- `skills/manage-math-research-program/assets/blueprint-accepted-knowledge/submissions/.gitkeep`.

两份文件均只有一个 `0A` 字节, 不是零字节文件.
作用是让 Git 和分发包保留两个 seed 目录.
`init_project.py` 在显式初始化新项目时遍历 `knowledge_seed.rglob("*")`, 创建目标父目录,
并用 `shutil.copy2` 将它们复制到用户选择的项目 `knowledge/` 下.
内容不含可执行语句、网络地址、凭据或研究数据.
实际备份、提案与接收由后续 Blueprint 工作流处理, 占位文件不触发这些动作.
目录存在不代表已生成备份、已审查提案或已完成 canonical 接收.

## 6. Mermaid 示例资源

路径: `skills/manage-math-research-program/assets/blueprint-accepted-knowledge/dependency_graph.mmd`.
文件完整内容为:

```text
flowchart TD
    H["Problem hypothesis"] -->|premise_input| I1["Mathematical inference: open"]
    I1 -->|inference_input| C1["Candidate claim"]
    C1 -->|premise_input| I2["Mathematical inference: proved"]
    D["Definition contract"] -->|definition_input| I2
    I2 -->|inference_input| T["Target claim"]
    T -->|target_input| G["Research goal"]
    X["Verified counterexample"] -->|refutation_input| C1
```

它是关系角色示意图. 同目录 seed `blueprint.json` 的 `nodes` 和 `edges` 都为空,
所以不能把示意图当作实际项目已接收结果的展示.
初始化器会复制它. 当前 PNG renderer 实际读取 `blueprint.json` 并用 Pillow 写 PNG,
不以此 `.mmd` 为输入. DSH Bundle 加载时不渲染它.
文件没有 Mermaid `init` 指令、`click` 回调、URL 或脚本;
用户可另选 Mermaid 阅读器, 该阅读器的依赖与权限由用户选择的环境承担.

## 7. Blueprint 证据索引 seed

路径: `skills/manage-math-research-program/assets/blueprint-accepted-knowledge/evidence_inventory.csv`.

这是 11 列 CSV 表头, 无数据行、公式或外部引用. `init_project.py` 显式初始化时复制到所选项目的 `knowledge/`. 后续 Blueprint 查询和校验用 Python 的 `csv.DictReader` 读取项目索引; 查询将其与图成对读取, 校验检查所需列和证据对应. 文件内容不作代码或公式求值, 复制和解析不访问外部服务. 初始空表不含已接收证据; 写入真实证据属于后续 receiver 的独立操作.

## 8. 文献分析 LaTeX 模板

路径: `skills/manage-math-research-program/assets/paper-analysis.template.tex`.

文献分析指南按需引用这一骨架, 用来记录固定版本、假设、定理、证明结构、局限及可复用技术. Bundle 加载和项目初始化不编译它. 模板由常规 LaTeX 文档、宏、表格和包声明组成, 没有显式 shell escape 或加载外部文献的指令. 选择编译时, TeX 读取所用环境的类、包等资源, 并将 PDF 和辅助文件写入项目的输出位置. 环境、依赖和填入稿件的行为由编译工作流另行核对; 缺包不会影响 Bundle 注册.

## 9. 可读证明 LaTeX 模板

路径: `skills/manage-math-research-program/assets/proof-paper.template.tex`.

为 Lean 验证后的证明交付提供排版骨架. 初始化器只生成 `papers/` 入口说明; 用户或 agent 选择取用并完成文稿后才编译. 原件没有显式 shell escape、外部文献读取或 BibTeX 调用; XeLaTeX 字样是注释, 示例链接用于排版. 编译读取 TeX 环境的类和包, 写本地 PDF/辅助文件. 源中 `lake build: passed`、零 `sorry`/`axiom` 和 Lean 路径都是待填写的示例, 不执行 Lean, 不产生核验回执.

## 复核与维护命令

从本源码 checkout 执行, Python 3.10+, 核对程序只用标准库:

```sh
python scripts/dsh-resource-review.py
python scripts/dsh-resource-review.py --archive /absolute/path/math-research-dsh-2.0.5.tgz
python tests/test_store_resource_review.py -v
```

输出 `scope=author_inventory_integrity` 仅说明作者材料与所查源码/归档对应.
JSON 字段、能力说明或摘要变化都不能自动赋予 STORE 批准.
日后资源或调用实现发生变化时, 先重新阅读原文件及调用链, 修订逐项说明,
再显式执行 `python scripts/dsh-resource-review.py --refresh` 重绑摘要并重跑门禁.
`--refresh` 只更新机械字段, 不执行语义审查.

本轮未扩大兼容范围. 已声明的四个精确 DSH 版本继续由现有一次性 Profile CI 分别验收;
更新的 Desktop 版本需要自己的验收记录. 真实项目文件读写、Git/Lean 外部命令等能力继续按
[契约说明](dsh-store-contract.md) 披露. 作者测试结果与 STORE 独立复核分别登记.
