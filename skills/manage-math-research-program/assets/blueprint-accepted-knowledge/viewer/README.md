# Blueprint Explorer

`index.html` 是一个无构建依赖的本地浏览器查看器。它默认读取上一级目录的 `blueprint.json`；也可以通过界面中的“打开 Blueprint JSON”读取任意兼容的 JSON 文件。

## 启动

在 `research_blueprint/statistics` 目录运行：

```powershell
python tools/serve_blueprint_viewer.py
```

浏览器会打开本地地址。关闭终端或按 `Ctrl+C` 即停止服务。也可以直接双击 `viewer/index.html`，再使用文件选择器载入 Blueprint；这一路径不依赖浏览器读取相邻文件的权限。

## 交互

- 默认“概览”将节点折叠为主线 × 认识论类型模块，并在边上显示聚合依赖数。
- 点击概览模块进入其详细局部图；详细图保留模块节点及其一跳上下游。
- 点击节点查看陈述、状态、证明前提、定义、推理结论、反驳、研究目标、证据哈希和直接上下游。
- 鼠标滚轮缩放，拖动空白处平移；“适配画布”恢复全图。
- 可按主线、类型和文本筛选；“全局弱化；选中后高亮”是默认关系显示方式。
- 可导出当前图为独立 SVG。

## 可选显示元数据

查看器不要求修改现有 Blueprint。没有显示元数据时，它会自动按 `mainline × epistemic_type` 生成概览模块。

需要更细粒度的长期组织时，可在 Blueprint 中加入下列可选字段：

```json
{
  "display": {
    "groups": [
      {
        "id": "kr_isotropic",
        "label": "各向同性 Kac–Rice",
        "mainline": "theory",
        "order": 20,
        "default_collapsed": true
      }
    ]
  },
  "nodes": [
    {
      "id": "THM-KR-ISO-001",
      "display": {
        "group": "kr_isotropic",
        "short_label": "各向同性 Kac–Rice"
      }
    }
  ]
}
```

显示元数据是向后兼容的：不影响现有验证器或科学依赖结构。`display.group` 会替代自动模块分组；`order` 决定概览中的同类模块排序。v2.2 的新边使用带角色对象：

```json
{"source": "CLM-A", "target": "INF-A-B", "role": "premise_input"}
```

数组边仍被支持以迁移旧项目；查看器会从目标节点的各种 typed input 字段自动推断边类型。新 proposal 由接收器持久化为包含 `source`、`target` 和 `role` 的对象。
