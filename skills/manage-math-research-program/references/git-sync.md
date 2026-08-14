# Automatic git repository sync

Conventions for keeping a research-program repository synchronized with its
remote from inside the agent.

## When to check

- At session start (workflow step 0): verify the working tree and remote state before building new work.
- At every stage close (workflow step 9): commit and push the stage.
- Before delegating a run: ensure the task packet and indexes are committed so the run root is reproducible.

## Commands

Status and sync check:

```bash
git status --porcelain   # uncommitted and untracked files
git fetch                # update remote refs
git status -sb           # ahead/behind vs upstream
```

Commit and push a stage:

```bash
git add -A
git commit -m "<descriptive stage summary>"
git push
git status -sb           # expect: working tree clean, up to date with origin
```

## Proxy note (Windows)

If the global git configuration points to a local proxy that is not running
(for example `http.proxy=127.0.0.1:7897`), override it per command:

```bash
git -c http.proxy= -c https.proxy= fetch
git -c http.proxy= -c https.proxy= push
```

Do not change the user's global proxy configuration without asking.

## Hygiene rules

- Keep secrets, credentials, tokens, and API keys out of commits; add them to `.gitignore` or keep them outside the repository.
- Ignore generated caches: `__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`.
- Update `AGENTS.md` session records before committing so history is traceable.
- Commit after each substantial stage; small incremental commits are preferred over one giant commit.
- On push failure (network or proxy), keep the local commit, record the failure in the activity log, and retry; never silently drop local work.
- A clean synchronized repository is part of stage completion, not optional bookkeeping.

## Optional multi-remote sync (generic)

A project repository may have any number of remotes (default remote, fork,
upstream mirror, personal copy).  The default sync is a plain `git push` to
the branch's upstream.  When the project declares a push order in
`project.json`, every listed remote is pushed in that order:

```json
{
  "git_sync": {
    "push_order": ["origin", "fork"]
  }
}
```

- `push_order` is optional; when absent, only the default remote is pushed.
- The order is the configuration: "parent first, then child fork" is simply
  the `["origin", "fork"]` instance of this rule.  Never hard-code any
  specific owner/repository topology in the skill.
- The deterministic helper `scripts/sync_remotes.py --project ROOT` reads
  `git_sync.push_order`, refuses to run on a dirty tree (use `--allow-dirty`
  only when uncommitted artifacts are intentionally local), pushes the
  current branch to each remote in order, and verifies `HEAD == <remote>/<branch>`
  after each push.  Use `--dry-run` to preview.
- After a multi-remote sync, record the order and the resulting commit hash
  in the session log (`AGENTS.md`).

If a fork relationship is lost (the GitHub API reports `fork=false` on a
child that should be a fork), restore it with the repository owner's own
fork flow:

1. Optionally rename the detached child so the original name is free
   (`PATCH /repos/<owner>/<repo>` with a temporary `name`).
2. Recreate the fork from the parent via the GitHub web/API fork action.
3. Verify the new child reports `fork=true` with the expected
   `parent.full_name` and an identical HEAD commit.