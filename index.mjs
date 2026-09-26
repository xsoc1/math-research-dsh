// Register the four immutable packaged skills through DSH's public skills
// service. A clean Profile does not necessarily install the optional
// @deepseek-ai/dsh-skill-filesystem package into this bundle's dependency
// closure, so the bundle must not import that package directly.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const SkillRoot = fileURLToPath(new URL('./skills/', import.meta.url))
const SkillDirs = [
	'rigorous-open-math-research',
	'manage-math-research-program',
	'math-research-workflow',
	'lean-verify',
]

function frontmatter_value(Header, Key)
{
	const Match = Header.match(new RegExp(`^${Key}:\\s*(.+)$`, 'm'))
	if(Match === null || Match[1].trim() === '')
	{
		throw new Error(`math-research-dsh: missing ${Key} in SKILL.md`)
	}
	return Match[1].trim()
}

function load_skill(SkillName)
{
	const SkillDirectory = join(SkillRoot, SkillName)
	const SkillPath = join(SkillDirectory, 'SKILL.md')
	const SkillSource = readFileSync(SkillPath, 'utf8')
	const Frontmatter = SkillSource.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/)
	if(Frontmatter === null)
	{
		throw new Error(`math-research-dsh: invalid frontmatter in ${SkillPath}`)
	}
	const Name = frontmatter_value(Frontmatter[1], 'name')
	if(Name !== SkillName)
	{
		throw new Error(`math-research-dsh: unexpected skill name ${Name}`)
	}
	return Object.freeze({
		name: Name,
		description: frontmatter_value(Frontmatter[1], 'description'),
		source: 'bundled',
		provider: 'math-research-dsh',
		resourceBase: Object.freeze({ kind: 'directory', path: SkillDirectory }),
		path: SkillPath,
		content: Frontmatter[2].trim(),
	})
}

const Skills = SkillDirs.map(load_skill)

export const name = 'math-research-dsh'
export const inject = ['skills']

export function apply(ctx)
{
	for(const Skill of Skills)
	{
		ctx.skills.register(Skill)
	}
}
