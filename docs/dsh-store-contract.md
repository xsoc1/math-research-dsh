# DSH STORE contract / 上架契约

This document records the repository's own compatibility and capability claims for
[DSH STORE issue #1185](https://github.com/AI-Scarlett/DSH-Store/issues/1185).
It is not a DSH STORE approval or an independent security audit.

## Package and host

- Package: `math-research-dsh` 2.0.1, one additive Cordis Patch entry
  (`math-research-dsh`) and four packaged skills.
- Host integration: `index.mjs` reads the packaged `SKILL.md` files and registers
  them with DSH's injected public `ctx.skills.register` service. It neither
  modifies DSH core nor replaces official tools or skills.
- Node.js: `^22.19.0 || >=24.2.0`. The first range follows DSH's repository
  requirement; the second excludes Node 24 versions without `import.meta.main`
  needed by the published CLI. This is a declared runtime range, not proof that
  every matching Node release was tested.
- DSH: `>=0.1.7-rc.2 <0.2.0` is the declared range. Exact release results in
  `package.json` are the evidence boundary. `unknown` means no disposable
  Profile acceptance has been completed for that release.
- Supported installation surfaces: DSH Bundle for `web` and `headless` Profiles;
  checkout-only `install.ps1` links user skills and must not be combined with
  Bundle installation.

## Dependencies and permissions

The Bundle has no npm runtime or optional dependencies and no `preinstall`,
`install`, `postinstall`, or `prepare` script. It uses DSH's injected `skills`
service and Node built-ins. The Python helpers inside packaged skills are
invoked only when the user or agent selects the corresponding workflow. Those
helpers require Python 3.10 or newer. Lean/Lake, Git, and optional Python
packages are needed only for the workflows that call them; they are not
installed by this Bundle.

| Surface | Capability and trigger | Boundary |
| --- | --- | --- |
| Bundle loading | Reads four packaged `SKILL.md` files | No project write or network request on load |
| Research helpers | Read and write user-selected project, evidence and log paths | Caller chooses the workspace and should review generated changes |
| Blueprint viewer | Browser `fetch` reads its same-origin `blueprint.json` | No remote service is required by the Bundle |
| Git synchronization | The optional `sync_remotes.py` invokes `git` and can contact configured remotes | Run only for an explicitly requested synchronization; Git may use existing local credentials |
| Lean verification | Optional helpers launch Lean/Lake and write verification logs | Compiler/cache setup and any network access belong to the chosen Lean environment |

The packaged source therefore has file, network, and command capability signals.
The automatic low-risk DSH STORE policy may keep this plugin blocked. A possible
guarded `user-reviewed` route requires the STORE's separate fixed-source review;
this repository cannot grant that status to itself. No credentials are collected
or stored by the Bundle entry. User-invoked Git or external tools can use the
user's pre-existing credentials according to those tools' own configuration.

## Failure and evidence boundaries

- The Bundle fails import if a packaged skill is missing or its frontmatter
  name does not match the declared directory. It does not silently register a
  partial set of skills.
- A missing optional Python, Git, Lean/Lake or service prerequisite affects the
  corresponding selected workflow, not Bundle installation.
- `--dump-config` proves Patch composition only. Profile startup and skill
  registration are separate checks. No source scan or CI unit test proves a
  user's real Profile or account works.
- The repository's historical 2.0 tests and Lean evidence belong to the frozen
  parent source and do not establish DSH 0.1.7 runtime compatibility.

## Disposable Profile acceptance

On Linux with Node.js 24.17.0 and DSH 0.1.7-rc.2, a disposable Profile
installed the 2.0.1 tarball through the official CLI. Both `headless` and `web`
Profiles composed the Patch and booted without an inactive-entry warning. The
`web` Profile listened on `127.0.0.1` and rejected an unauthenticated request
with HTTP 401. Official CLI removal restored each Profile's composed config;
a separate reinstall/removal cycle restored the `headless` config, manifest and
lockfile byte for byte. These checks support the exact `compatible` and four
`passed` operation records for 0.1.7-rc.2 in `package.json`. The other two
releases in the observed latest-three window remain `unknown`.

The user's real DSH Profile, credentials and processes were not changed or
verified. Skill invocation through an authenticated model session was not
tested. DSH STORE's fixed-Commit review and guarded listing decision remain
separate from this local acceptance.
