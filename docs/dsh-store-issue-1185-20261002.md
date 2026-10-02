# DSH STORE #1185 follow-up, 2026-10-02

The current [author notice](https://github.com/AI-Scarlett/DSH-Store/issues/1185)
still describes version 2.0.0 and remains open with no comments. Live reads of
the [Catalog detail](https://github.com/AI-Scarlett/DSH-Store/blob/main/registry/catalog/details/math-research-dsh.json)
and both production storefronts are distinct from that old notification.
They already reference 2.0.1 at
`888bcc0c92b6f85ada337f6a654a716c21a812c4`. The Catalog removed the missing
DSH/Node declaration reasons and retained exactly the real files, network and
commands capability signals. Upstream repair and automatic STORE admission
are different outcomes.

## Current defect and repair

The official npm `@deepseek-ai/dsh` latest tag is `0.2.0-rc.2`; its preceding
two non-deprecated releases are `0.2.0-rc.1` and `0.1.7-rc.2`.
The previous manifest excluded 0.2 releases and the Profile driver rejected
the latest official CLI before any installation test:

```text
RuntimeError: This evidence targets DSH 0.1.7-rc.2, got 0.2.0-rc.2
```

Version 2.0.2 preserves the four frozen parent skills, Bundle entry and Patch.
It adds exact compatibility and operation records for the two tested 0.2
prereleases, declares the recognized `suite` type, and provides `npm run check`.
The Profile driver verifies an explicit `--expect-dsh` instead of a hardcoded
release. CI uses a fixed three-release matrix and distinct evidence artifacts.

Final packaging inspection also reproduced a cache leak: running Python
validation before `npm pack` included 74 generated `.pyc` files in the tarball.
The manifest now excludes `__pycache__`, `.pyc` and `.pyo`; the driver rejects
such a tarball and requires all 140 locked parent resources to be packaged.
The cache-containing run remains a failed packaging candidate, despite its
successful runtime checks; the final acceptance uses the clean distribution.

## Acceptance scope

[Sanitized machine-readable evidence](dsh-store-issue-1185-20261002.json)
binds all three releases to one final tarball SHA-256. Each runs on Linux,
Node.js 24.17.0, pnpm 11.22.0, using a temporary `DSH_HOME` and the official
CLI for install and removal. Each checks:

- `headless` and `web` installation and unique Patch composition.
- Both boot paths without failed-import/inactive-entry warnings.
- A real loopback Web listener returning HTTP 401 without authentication.
- Removal restoring both composed configurations, and a headless reinstall
  and rollback restoring config, package manifest and lockfile bytes.
- A separate isolated Cordis context using the installed official Skills
  service and the Profile-installed tarball entry: four exact bodies and
  resource directories load, invocation defaults are valid, and disposal
  leaves no skills. Missing resource, wrong name and malformed frontmatter
  controls fail as expected.

This last check uses the official service, but does not inspect the Web
process's registry or invoke a skill through an authenticated model session.
Windows/macOS Profile acceptance and the user's real Profile are untested.
The historical 2.0.1 evidence is retained at its original path and hash.

## Remaining STORE decision

The [current registry contract](https://github.com/AI-Scarlett/DSH-Store/blob/main/registry/README.md)
allows automatic admission only when the bounded source has none of the
file/network/command/credential capability signals. Declarations and local
runtime results do not override that rule. This suite intentionally retains
project file helpers, optional Git/Lean execution and same-origin Blueprint
viewer requests. The source scan is therefore reporting real capabilities.

Catalog automation currently initializes permission details as `unknown`;
upstream prose is not promoted to independently reviewed permission metadata.
Only `dsh.pluginType` and the documented compatibility fields are used here;
no unrecognized manifest field is presented as a STORE approval mechanism.
An installable guarded listing still requires a separate STORE decision.
No Catalog status, contact record, notification, or issue is edited by this
upstream repair.
