# DSH execution options

This reference describes runtime tools. Choose them when they help the current
work. The parent skill and the user's project determine research and review.

## Files and long-running work

Load a skill by its exact name with `skill`; use the returned `resourceBase`
for its references and helpers. The four skills can be used independently.
Plugin-level helpers are merged into the corresponding DSH skill's `scripts/`;
the manage Blueprint gateway is `<resourceBase>/runtime/blueprintctl.py`.

For long shell work, DSH can return a background job ID with
`run_in_background: true`. Keep the actual job ID and input identity with the
project's current progress. Collect results with `job_output`; `job_kill` can
stop a job when authorized. Reconcile a job of unknown status before
redispatching that action. Process completion alone is not mathematical proof.
The workflow skill's `references/v2-continuity.md` documents durable helpers.

For truncated output, save full logs and read the relevant ranges. A repository
checkout additionally provides `scripts/dsh_run.py` for complete logs and a
compact verdict, `scripts/dsh-doctor.py` for installation diagnostics and
`scripts/context-audit.py` for inspecting context size. These checkout helpers
are optional and are not included in the npm skill bundle.

## Optional collaboration

When collaboration is useful and authorized, `subagent` starts from the supplied
prompt; `subagent_fork` carries the conversation. Supply the relevant artifacts
and describe the scope of the review or task. Choose the number of agents and
result format for the work at hand. A fresh agent adds a separate perspective;
its verdict still needs identifiable evidence.

For a batch of independent tasks, the workflow bundle retains
`assets/dsh-solve-audit-workflow.js` as a compatibility filename. Its 2.0 body
runs explicit task prompts with optional dependencies. It assigns no research
roles, infers no proof status and creates no subsequent verification stage.
Dependent tasks run after their dependencies finish; cycles and missing task
IDs are rejected before dispatch. A completion is an execution result, not an
accepted mathematical claim.

## Source reading

Use bounded source reads and keep raw input, version and locators. A parser or
vision tool can help transcribe a difficult page; compare mathematical content
with the original before relying on it. Optional capabilities are described in
`dsh-optional-capabilities.md` in the rigorous and manage bundles.
