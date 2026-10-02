// Verify the packed entry against the installed official Skills service.
import assert from 'node:assert/strict'
import { cp, mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const [ModuleDirectory, BundleDirectory] = process.argv.slice(2)
assert.ok(ModuleDirectory && BundleDirectory, 'Expected official node_modules and packed Bundle directories')
const ModuleRoot = resolve(ModuleDirectory)
const BundleRoot = resolve(BundleDirectory)
const { Context } = await import(pathToFileURL(join(ModuleRoot, '@deepseek-ai/cordis/lib/index.js')))
const { default: SkillRegistry } = await import(pathToFileURL(join(ModuleRoot, '@deepseek-ai/dsh-skill/lib/index.js')))
const Bundle = await import(pathToFileURL(join(BundleRoot, 'index.mjs')))
const SkillNames = ['rigorous-open-math-research', 'manage-math-research-program', 'math-research-workflow', 'lean-verify'].sort()
const Root = new Context()
const RegistryFiber = await Root.plugin(SkillRegistry)
let BundleFiber
try
{
	assert.deepEqual(await Root.skills.list(), [])
	BundleFiber = await Root.plugin(Bundle)
	assert.deepEqual((await Root.skills.list()).map(Skill => Skill.name).sort(), SkillNames)
	for(const Name of SkillNames)
	{
		const Skill = await Root.skills.get(Name)
		assert.ok(Skill, `Official registry did not load ${Name}`)
		assert.equal(Skill.provider, 'math-research-dsh')
		assert.equal(Skill.invocation.modelInvocable, true)
		assert.equal(Skill.invocation.userInvocable, true)
		const Source = await readFile(join(BundleRoot, 'skills', Name, 'SKILL.md'), 'utf8')
		assert.equal(Skill.content, Source.split(/---\r?\n/).slice(2).join('---\n').trim())
		assert.equal(Skill.resourceBase.kind, 'directory')
		assert.equal(await readFile(join(Skill.resourceBase.path, 'SKILL.md'), 'utf8'), Source)
	}
	await BundleFiber.dispose()
	BundleFiber = undefined
	assert.deepEqual(await Root.skills.list(), [], 'Disposal left bundled skills in the official registry')
}
finally
{
	if(BundleFiber) await BundleFiber.dispose()
	await RegistryFiber.dispose()
}

// Broken packaged resources must fail import before any partial registration.
for(const Failure of ['missing-resource', 'wrong-name', 'invalid-frontmatter'])
{
	const FixtureRoot = await mkdtemp(join(tmpdir(), 'math-research-dsh-entry-'))
	try
	{
		await cp(join(BundleRoot, 'index.mjs'), join(FixtureRoot, 'index.mjs'))
		for(const Name of SkillNames)
		{
			await cp(join(BundleRoot, 'skills', Name, 'SKILL.md'), join(FixtureRoot, 'skills', Name, 'SKILL.md'), { recursive: true })
		}
		const BrokenPath = join(FixtureRoot, 'skills', 'lean-verify', 'SKILL.md')
		if(Failure === 'missing-resource')
		{
			await unlink(BrokenPath)
		}
		else
		{
			const Source = await readFile(BrokenPath, 'utf8')
			await writeFile(BrokenPath, Failure === 'wrong-name' ? Source.replace('name: lean-verify', 'name: wrong-name') : 'invalid frontmatter\n')
		}
		const Expected = Failure === 'missing-resource' ? /ENOENT/ : Failure === 'wrong-name' ? /unexpected skill name/ : /invalid frontmatter/
		await assert.rejects(import(pathToFileURL(join(FixtureRoot, 'index.mjs'))), Expected)
	}
	finally
	{
		await rm(FixtureRoot, { recursive: true, force: true })
	}
}
console.log(JSON.stringify({ status: 'passed', skillNames: SkillNames, loaded: 4, disposal: 'passed', malformedPackageControls: 3, scope: 'isolated official Cordis Skills registry using the installed tarball entry' }))
