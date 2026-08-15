// math-research-dsh - bundle entry.
// Registers the packaged skills/ tree as a custom skill provider, reusing the
// official filesystem provider so skills load exactly like user-level skills
// (frontmatter parsing, watcher, ranks, resourceBase).
//
// Note: @deepseek-ai/dsh-skill-filesystem is NOT declared in dependencies -
// official packages are injected by the profile's pnpm closure at install
// time (declaring them fails on public npm).
//
// This bundle intentionally mounts only the packaged skill directories
// (includeDefaultRoots: false), so installing it never re-discovers the
// app's own bundled or user skills under a second provider name.

import { fileURLToPath } from 'node:url'
import { FileSystemSkillProvider } from '@deepseek-ai/dsh-skill-filesystem'

export const name = 'math-research-dsh'
export const inject = ['skills']

const SKILL_DIRS = [
  'rigorous-open-math-research',
  'manage-math-research-program',
  'math-research-workflow',
  'lean-verify',
]

export function apply(ctx) {
  const root = fileURLToPath(new URL('./skills', import.meta.url))
  const customSkillDirs = SKILL_DIRS.map((dir) => `${root}/${dir}`)
  ctx.skills.registerProvider((control) =>
    new FileSystemSkillProvider(ctx, control, {
      providerName: 'math-research-dsh',
      customSkillDirs,
      includeDefaultRoots: false,
    }),
  )
}
