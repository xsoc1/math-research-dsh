# Canonical accepted knowledge

Use this interface when the project actually maintains a Blueprint. Ordinary
literature notes, experience and hypotheses need no canonical transaction.

In this DSH bundle, the gateway is `runtime/blueprintctl.py` relative
to this skill's directory. In an adapted package resolve the active package's
runtime rather than copying a project-local tool. The project marker
`blueprint-project.json` owns its physical layout.

```text
python <manage-plugin>/runtime/blueprintctl.py ensure --project <project>
python <manage-plugin>/runtime/blueprintctl.py query --project <project> snapshot
python <manage-plugin>/runtime/blueprintctl.py query --project <project> math-frontier --goal <goal> --context <context>
python <manage-plugin>/runtime/blueprintctl.py validate --project <project>
```

Run `ensure` once for the active project/runtime. It records runtime and layout
identity. On an actual accepted-knowledge change, follow the existing
[proposal and reviewed integration contract](accepted-knowledge-pipeline.md).
The receiver enforces immutable evidence, snapshot freshness and protected
claims. Its data requirements apply to canonical integration, not to every
research attempt. A merged partial result still leaves its parent theorem open.
