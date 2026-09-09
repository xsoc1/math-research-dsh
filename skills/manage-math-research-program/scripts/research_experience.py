#!/usr/bin/env python3
"""Save research experience, compare routes and assemble an editable understanding page.

The author supplies mathematical explanations and tests. This helper binds and
assembles them; shared words do not establish a theorem or an accepted premise.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

import research_library as library

OUTCOMES = ("success", "partial", "failed", "no_return", "unknown")
FAILURE_KINDS = ("counterexample", "method_limit", "missing_lemma", "infrastructure", "unknown")
START = "<!-- research-understanding:v2:start -->"
END = "<!-- research-understanding:v2:end -->"
HASH_PREFIX = "<!-- research-understanding-sha256:"


def text_items(Value):
	if(Value is None):
		return []
	if(isinstance(Value, str)):
		return [Value] if Value.strip() else []
	if(not isinstance(Value, list) or any(not isinstance(Item, str) for Item in Value)):
		raise ValueError("expected text or a list of text")
	return Value


def record_experience(project, Data, ToolPath=None, ExpectedHash=None):
	Data = dict(Data)
	if(ToolPath is not None and library.inside(project, ToolPath).exists()):
		Front, Body, _ = library.read_metadata(library.inside(project, ToolPath).read_bytes())
		if(Front.get("kind") == "experience"):
			Previous = dict(Front.get("experience", dict()))
			Previous["content"] = Body
			Previous["title"] = Front.get("title", "Research experience")
			Previous["evidence_status"] = Front.get("evidence_status", "RESEARCH_NOTE")
			Data = dict(Previous, **Data)
	Outcome = str(Data.pop("outcome", "unknown")).lower()
	FailureKind = Data.pop("failure_kind", None)
	if(Outcome not in OUTCOMES or (FailureKind is not None and FailureKind not in FAILURE_KINDS)):
		raise ValueError("unknown outcome or failure_kind; describe details freely in mechanism")
	if(Outcome == "no_return"):
		if(FailureKind not in (None, "unknown", "infrastructure")):
			raise ValueError("no_return is not evidence for a mathematical failure")
		FailureKind = "infrastructure"
	elif(Outcome == "failed" and FailureKind is None):
		FailureKind = "unknown"
	Scope = Data.pop("scope", Data.get("conditions", "UNSPECIFIED"))
	Experience = dict(outcome=Outcome, failure_kind=FailureKind, scope=Scope,
		question=Data.pop("question", ""), conclusion=Data.pop("conclusion", ""),
		mechanism=Data.pop("mechanism", ""),
		transformations=text_items(Data.pop("transformations", [])),
		reconsider_when=text_items(Data.pop("reconsider_when", [])),
		not_applicable_to=text_items(Data.pop("not_applicable_to", [])))
	Content = Data.get("content", "")
	if(not Content and not Experience["question"] and not Experience["conclusion"]):
		raise ValueError("provide content, a question or a conclusion worth retaining")
	if(not Content):
		Sections = ["# " + str(Data.get("title", "Research experience"))]
		for Key in ("question", "conclusion", "scope", "mechanism", "transformations", "reconsider_when", "not_applicable_to"):
			Value = Experience[Key]
			if(Value):
				Sections.extend(["", "## " + Key.replace("_", " ").capitalize(), "",
					"\n".join("- " + Item for Item in text_items(Value))])
		Data["content"] = "\n".join(Sections)
	Data.update(kind="experience", experience=Experience, conditions=Scope)
	Data.setdefault("evidence_status", "RESEARCH_NOTE")
	if(ToolPath is None):
		RecordId = str(Data.get("tool_id") or "experience-" + library.digest(library.json_bytes(Data))[:20])
		if(not re.fullmatch(r"[A-Za-z0-9_.-]+", RecordId)):
			raise ValueError("use a file-safe tool_id or specify --tool")
		Data["tool_id"] = RecordId
		ToolPath = library.relative(project, library.library_root(project) / "experiences" / (RecordId + ".md"))
	return library.save_card(project, Data, ToolPath, ExpectedHash)


def read_route(project, PathValue):
	PathValue = library.inside(project, PathValue)
	Raw = PathValue.read_bytes()
	Front, Body, MetadataStatus = library.read_metadata(Raw)
	Experience = Front.get("experience", dict())
	for Key in ("question", "conclusion", "mechanism", "scope", "transformations", "reconsider_when", "not_applicable_to"):
		text_items(Experience.get(Key))
	return dict(path=library.relative(project, PathValue), sha256=library.digest(Raw),
		tool_id=Front.get("tool_id", PathValue.stem), title=Front.get("title", PathValue.stem),
		metadata_status=MetadataStatus, evidence_status=Front.get("evidence_status", "UNKNOWN"),
		conditions=Front.get("conditions", "UNSPECIFIED"), experience=Experience,
		summary=Front.get("summary", Experience.get("conclusion", Body[:500])),
		evidence=library.reference_states(project, Front.get("evidence", [])),
		resources=library.reference_states(project, Front.get("resources", [])),
		sources=library.reference_states(project, Front.get("sources", [])),
		lean=library.lean_reference_states(project, Front.get("lean", [])),
		trust="RETRIEVAL_ONLY_REVALIDATE_APPLICATION")


def compare_routes(project, Routes, Hypotheses=None):
	Paths = list(dict.fromkeys(Routes))
	if(len(Paths) < 2):
		raise ValueError("compare at least two explicit routes")
	Records = [read_route(project, PathValue) for PathValue in Paths]
	Hypotheses = [] if Hypotheses is None else Hypotheses
	if(isinstance(Hypotheses, dict)):
		Hypotheses = [Hypotheses]
	if(not isinstance(Hypotheses, list)):
		raise ValueError("hypotheses must be an object or a list of objects")
	Candidates = []
	for Hypothesis in Hypotheses:
		if(not isinstance(Hypothesis, dict) or any(not isinstance(Hypothesis.get(Key), str) or not Hypothesis[Key].strip() for Key in ("explanation", "prediction", "test", "scope"))):
			raise ValueError("each supplied hypothesis needs an explanation, scope, prediction and test")
		Candidates.append(dict(Hypothesis, status="CANDIDATE_EXPLANATION", origin="AUTHOR_SUPPLIED", validated=False))
	Transforms = [set(text_items(Record["experience"].get("transformations", []))) for Record in Records]
	Shared = sorted(set.intersection(*Transforms))
	Comparison = dict(schema_version=2, kind="route_comparison", status="CANDIDATE_COMPARISON",
		routes=Records, shared_transformations=Shared, hypotheses=Candidates,
		interpretation="Shared labels are exact text matches, not inferred equivalence or mathematical evidence.",
		accepted_graph_modified=False)
	Data = library.json_bytes(Comparison)
	PathValue = library.inside(project, library.library_root(project) / "comparisons" / (library.digest(Data) + ".json"))
	with library.writer_lock(library.library_root(project)):
		for Record in Records:
			if(library.digest(library.inside(project, Record["path"]).read_bytes()) != Record["sha256"]):
				raise ValueError("route changed while comparing; read the current route")
		library.immutable_write(PathValue, Data)
	return dict(path=library.relative(project, PathValue), sha256=library.digest(Data), **Comparison)


def read_comparison(project, PathValue):
	PathValue = library.inside(project, PathValue)
	Data = PathValue.read_bytes()
	Record = json.loads(Data)
	if(Record.get("kind") != "route_comparison" or library.digest(Data) != PathValue.stem):
		raise ValueError("comparison identity mismatch")
	Routes = []
	for Route in Record["routes"]:
		try:
			State = "CURRENT" if library.digest(library.inside(project, Route["path"]).read_bytes()) == Route["sha256"] else "STALE"
		except OSError:
			State = "MISSING"
		Routes.append(dict(Route, binding_state=State))
	return dict(Record, routes=Routes, path=library.relative(project, PathValue), sha256=library.digest(Data))


def markdown_text(Value):
	return str(Value).replace("\r", "").replace("<!--", "&lt;!--")


def markdown_link(project, Output, Reference):
	if(not Reference.get("path")):
		return markdown_text(Reference.get("url", Reference.get("source_id", "unbound reference")))
	try:
		PathValue = library.inside(project, Reference["path"])
	except (ValueError, TypeError):
		return markdown_text(Reference["path"]) + " [INVALID_PATH]"
	Link = os.path.relpath(PathValue, Output.parent).replace("\\", "/")
	return "[" + markdown_text(Reference["path"]).replace("[", "\\[").replace("]", "\\]") + "](<" + Link.replace(">", "%3E") + ">)"


def replace_generated(Before, Payload):
	Text = Before.decode("utf-8")
	if(Text.count(START) != Text.count(END) or Text.count(START) > 1):
		raise ValueError("understanding page markers are malformed; human content was not changed")
	HashLine = HASH_PREFIX + library.digest(Payload.encode("utf-8")) + " -->\n"
	Block = START + "\n" + HashLine + Payload + END
	if(START not in Text):
		return (Text + ("\n\n" if Text else "") + Block + "\n").encode("utf-8")
	StartOffset, EndOffset = Text.index(START), Text.index(END)
	if(StartOffset > EndOffset):
		raise ValueError("understanding page markers are reversed")
	Old = Text[StartOffset + len(START) + 1:EndOffset]
	Match = re.match(re.escape(HASH_PREFIX) + r"([0-9a-f]{64}) -->\n", Old)
	if(not Match or library.digest(Old[Match.end():].encode("utf-8")) != Match[1]):
		raise ValueError("generated region has manual edits; move them outside the markers before refreshing, all bytes retained")
	return (Text[:StartOffset] + Block + Text[EndOffset + len(END):]).encode("utf-8")


def update_understanding(project, Routes=None, Comparisons=None, OutputPath=None):
	Output = library.inside(project, OutputPath or library.library_root(project).parent / "understanding.md")
	if(Output.suffix != ".md"):
		raise ValueError("the understanding page must be Markdown")
	if(Routes is None):
		Index = library.read_json(library.inside(project, "index/tools.json"))
		Routes = [Row["location"] for Row in Index["items"] if Row.get("kind") == "experience" and Row.get("pointer_state") == "CURRENT"]
	if(any(library.inside(project, PathValue) == Output for PathValue in Routes)):
		raise ValueError("the output page cannot also be an input card")
	Records, Reports, Issues = [], [], []
	for PathValue in dict.fromkeys(Routes):
		try:
			Records.append(read_route(project, PathValue))
		except (OSError, ValueError, TypeError, KeyError) as Error:
			Issues.append(library.issue(PathValue, Error))
	for PathValue in dict.fromkeys(Comparisons or []):
		try:
			Reports.append(read_comparison(project, PathValue))
		except (OSError, ValueError, TypeError, KeyError) as Error:
			Issues.append(library.issue(PathValue, Error))
	Lines = ["\n## Evidence and candidate explanations", "",
		"This section assembles recorded statements. It does not establish their mathematical validity.",
		"Write questions, intuition and decisions outside the generated markers.", ""]
	for Record in Records:
		Experience = Record["experience"]
		Lines.extend(["### " + markdown_text(Record["title"]), "",
			markdown_link(project, Output, Record) + " (sha256 `" + Record["sha256"] + "`).", "",
			"- Reported evidence: " + markdown_text(Record["evidence_status"]),
			"- Outcome: " + markdown_text(Experience.get("outcome", "unknown")),
			"- Failure kind: " + markdown_text(Experience.get("failure_kind") or "not recorded"),
			"- Scope: " + markdown_text(Record["conditions"]),
			"- Recorded conclusion: " + markdown_text(Experience.get("conclusion") or Record["summary"])])
		for Key in ("mechanism", "transformations", "reconsider_when", "not_applicable_to"):
			for Value in text_items(Experience.get(Key)):
				Lines.append("- " + Key.replace("_", " ").capitalize() + ": " + markdown_text(Value))
		for Key in ("evidence", "resources", "sources"):
			for Reference in Record[Key]:
				Lines.append("- " + Key.capitalize() + ": " + markdown_link(project, Output, Reference) + " [" + Reference["binding_state"] + "]")
		Lines.append("")
	for Report in Reports:
		Lines.extend(["### Candidate route comparison", "", markdown_link(project, Output, Report), ""])
		for Route in Report["routes"]:
			Lines.append("- Input " + markdown_link(project, Output, Route) + ": " + Route["binding_state"])
		for Hypothesis in Report["hypotheses"]:
			Lines.extend(["", "- Candidate explanation: " + markdown_text(Hypothesis["explanation"]),
				"- Scope: " + markdown_text(Hypothesis["scope"]),
				"- Testable prediction: " + markdown_text(Hypothesis["prediction"]),
				"- Proposed test: " + markdown_text(Hypothesis["test"])])
		Lines.append("")
	if(Issues):
		Lines.extend(["### Unavailable records", ""])
		Lines.extend("- " + markdown_text(Item["path"]) + ": " + markdown_text(Item["error"]) for Item in Issues)
	Payload = "\n".join(Lines).rstrip("\n") + "\n\n"
	with library.writer_lock(library.library_root(project)):
		Before = Output.read_bytes() if Output.exists() else b"# Project understanding\n\n## Human notes\n\n"
		for Record in Records:
			if(library.digest(library.inside(project, Record["path"]).read_bytes()) != Record["sha256"]):
				raise ValueError("an input changed while assembling the page; retry")
		After = replace_generated(Before, Payload)
		if(After != Before):
			library.atomic_write(Output, After)
	return dict(path=library.relative(project, Output), sha256=library.digest(After),
		reused=Before == After, assembled_routes=len(Records), assembled_comparisons=len(Reports),
		issues=Issues, status="ASSEMBLED_RESEARCH_NOTES", accepted_graph_modified=False)


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Sub = Parser.add_subparsers(dest="command", required=True)
	Record = Sub.add_parser("record")
	Record.add_argument("--project", required=True)
	Record.add_argument("--input", required=True)
	Record.add_argument("--tool")
	Record.add_argument("--expected-sha256")
	Compare = Sub.add_parser("compare")
	Compare.add_argument("--project", required=True)
	Compare.add_argument("--route", action="append", required=True)
	Compare.add_argument("--hypothesis", help="JSON object or list: explanation, scope, prediction and test")
	Understanding = Sub.add_parser("understanding")
	Understanding.add_argument("--project", required=True)
	Understanding.add_argument("--route", action="append")
	Understanding.add_argument("--comparison", action="append")
	Understanding.add_argument("--output")
	Args = Parser.parse_args()
	try:
		if(Args.command == "record"):
			Result = record_experience(Args.project, library.read_json(Path(Args.input)), Args.tool, Args.expected_sha256)
		elif(Args.command == "compare"):
			Hypotheses = library.read_json(Path(Args.hypothesis)) if Args.hypothesis else None
			Result = compare_routes(Args.project, Args.route, Hypotheses)
		else:
			Result = update_understanding(Args.project, Args.route, Args.comparison, Args.output)
		print(json.dumps(Result, ensure_ascii=False))
		return 0
	except (OSError, ValueError, TypeError, KeyError) as Error:
		print(json.dumps(dict(verdict="INVALID", error=str(Error)), ensure_ascii=False))
		return 1


if(__name__ == "__main__"):
	raise SystemExit(main())
