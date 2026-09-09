// Optional DSH task fan-out. Compatibility filename, template version 3.
// args.tasks: [{id, prompt, deps?: [id], model?}]. Results are execution output.
// Supply each task's artifact paths in its prompt. No filesystem access here.

const Tasks = args.tasks || []
const ById = new Map()
for(const Task of Tasks)
{
	if(!Task.id || ById.has(Task.id) || typeof Task.prompt !== "string")
	{
		throw new Error("Each task needs a unique id and a prompt")
	}
	ById.set(Task.id, Task)
}
for(const Task of Tasks)
{
	if(Task.deps !== undefined && !Array.isArray(Task.deps))
	{
		throw new Error("deps must be an array: " + Task.id)
	}
	for(const Dependency of Task.deps || [])
	{
		if(!ById.has(Dependency))
		{
			throw new Error("Unknown dependency: " + Dependency)
		}
	}
}
const Planned = new Set()
const Waves = []
while(Planned.size < Tasks.length)
{
	const Wave = Tasks.filter(Task => !Planned.has(Task.id)
		&& (Task.deps || []).every(Id => Planned.has(Id)))
	if(Wave.length === 0)
	{
		throw new Error("Task dependencies contain a cycle")
	}
	Waves.push(Wave)
	Wave.forEach(Task => Planned.add(Task.id))
}

const Results = []
phase("tasks")
for(const Wave of Waves)
{
	const Completed = await pipeline(Wave, async (Task) =>
	{
		const Options = { label: Task.id }
		if(Task.model)
		{
			Options.model = Task.model
		}
		const Result = await agent(Task.prompt, Options)
		return { id: Task.id, result: Result }
	})
	Results.push(...Completed)
}
return { results: Results }
