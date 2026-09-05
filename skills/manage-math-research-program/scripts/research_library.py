#!/usr/bin/env python3
"""Capture source bytes, retrieve bounded passages, index tool cards and annotate them.

All records are retrieval aids, never accepted mathematical premises. This tool
does not search the network, extract PDFs or modify a Blueprint accepted graph.
Feed it actual browser retrievals or extracted text with the raw source attached.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from manage_tool_lifecycle import read_tool, derived_status

START = "<!-- research-tool-pointers:v1:start -->"
END = "<!-- research-tool-pointers:v1:end -->"
NOTE_KINDS = ("retrieval_hint", "applicability", "correction", "failure", "observation")


def utc_now():
	return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(Data):
	return hashlib.sha256(Data).hexdigest()


def json_bytes(Data):
	return (json.dumps(Data, ensure_ascii=False, sort_keys=True, indent="\t", allow_nan=False) + "\n").encode("utf-8")


def read_json(path):
	return json.loads(path.read_text(encoding="utf-8"))


def inside(project, path):
	Root = Path(project).resolve()
	Target = (Root / path).resolve()
	Target.relative_to(Root)
	if(Target == Root):
		raise ValueError("a file or subdirectory inside the project is required")
	return Target


def library_root(project):
	ConfigPath = Path(project) / "blueprint-project.json"
	ResearchRoot = "research"
	if(ConfigPath.is_file()):
		ResearchRoot = read_json(ConfigPath).get("paths", dict()).get("research_root", ResearchRoot)
	return inside(project, Path(ResearchRoot) / "library")


def relative(project, path):
	return path.resolve().relative_to(Path(project).resolve()).as_posix()


def immutable_write(path, Data):
	path.parent.mkdir(parents=True, exist_ok=True)
	Fd, TempPath = tempfile.mkstemp(prefix=".capture-", dir=path.parent)
	try:
		with os.fdopen(Fd, "wb") as Handle:
			Handle.write(Data)
			Handle.flush()
			os.fsync(Handle.fileno())
		try:
			os.link(TempPath, path)
		except FileExistsError:
			if(path.read_bytes() != Data):
				raise ValueError(f"immutable record conflict: {path}")
	finally:
		os.unlink(TempPath)


def atomic_write(path, Data):
	path.parent.mkdir(parents=True, exist_ok=True)
	Fd, TempPath = tempfile.mkstemp(prefix=".library-", dir=path.parent)
	try:
		with os.fdopen(Fd, "wb") as Handle:
			Handle.write(Data)
			Handle.flush()
			os.fsync(Handle.fileno())
		os.replace(TempPath, path)
	finally:
		if(os.path.exists(TempPath)):
			os.unlink(TempPath)


@contextmanager
def writer_lock(Root):
	Root.mkdir(parents=True, exist_ok=True)
	LockPath = Root / "writer.lock"
	with LockPath.open("x", encoding="utf-8") as Handle:
		Handle.write(f"pid={os.getpid()} time={utc_now()}\n")
	try:
		yield
	finally:
		LockPath.unlink()


def find_sources(project, query, limit=8):
	if(not query.strip() or not 1 <= limit <= 50):
		raise ValueError("query is required and limit must be in 1..50")
	Hits = []
	Terms = query.casefold().split()
	for path in sorted((library_root(project) / "sources").glob("*/source.json")):
		path = inside(project, path)
		Record = read_json(path)
		if(digest(json_bytes(Record)) != path.parent.name):
			raise ValueError("source metadata hash mismatch")
		SearchText = " ".join(Record[Key] for Key in ("url", "title", "version")).casefold()
		Score = sum(Term in SearchText for Term in Terms)
		if(Score):
			Hits.append(dict(score=Score, source_id=path.parent.name,
				source=relative(project, path), **Record))
	Hits.sort(key=lambda Item: (-Item["score"], Item["source_id"]))
	return dict(verdict="RETRIEVAL_ONLY", hits=Hits[:limit], total_matches=len(Hits))


def capture_source(project, InputPath, url, version, title, TextPath=None, method="provided-text", SourceKind="primary"):
	if(urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc):
		raise ValueError("a real HTTP(S) source locator is required")
	if(not version.strip() or not title.strip()):
		raise ValueError("source title and version are required")
	Raw = Path(InputPath).read_bytes()
	TextBytes = Path(TextPath or InputPath).read_bytes()
	if(max(len(Raw), len(TextBytes)) > 32 * 1024 * 1024):
		raise ValueError("source exceeds 32 MiB; provide a scoped extraction")
	Text = TextBytes.decode("utf-8")
	if(not Text.strip() or "\x00" in Text):
		raise ValueError("provide readable UTF-8 text; extract PDF/OCR text separately")
	Record = dict(schema_version=1, url=url, version=version, title=title,
		source_kind=SourceKind, extraction_method=method, raw_sha256=digest(Raw),
		text_sha256=digest(TextBytes), line_count=len(Text.splitlines()),
		trust="UNVERIFIED_SOURCE_CONTENT")
	SourceId = digest(json_bytes(Record))
	Folder = inside(project, library_root(project) / "sources" / SourceId)
	with writer_lock(library_root(project)):
		immutable_write(inside(project, Folder / "raw.bin"), Raw)
		immutable_write(inside(project, Folder / "text.txt"), TextBytes)
		immutable_write(inside(project, Folder / "source.json"), json_bytes(Record))
	return dict(source_id=SourceId, source=relative(project, Folder / "source.json"), **Record)


def read_source(project, SourceId, StartLine=1, MaxLines=80, StartOffset=None):
	if(not re.fullmatch(r"[0-9a-f]{64}", SourceId)):
		raise ValueError("invalid source content ID")
	Folder = inside(project, library_root(project) / "sources" / SourceId)
	Record = read_json(inside(project, Folder / "source.json"))
	if(digest(json_bytes(Record)) != SourceId):
		raise ValueError("source metadata hash mismatch")
	TextBytes = inside(project, Folder / "text.txt").read_bytes()
	if(digest(TextBytes) != Record["text_sha256"] or digest(inside(project, Folder / "raw.bin").read_bytes()) != Record["raw_sha256"]):
		raise ValueError("source bytes changed")
	if(StartLine < 1 or not 1 <= MaxLines <= 200):
		raise ValueError("start-line must be positive and max-lines must be in 1..200")
	Text = TextBytes.decode("utf-8")
	Lines = Text.splitlines(keepends=True)
	if(StartLine > len(Lines)):
		raise ValueError("start-line is beyond the source")
	Offset = sum(len(Line) for Line in Lines[:StartLine - 1]) if StartOffset is None else StartOffset
	if(not isinstance(Offset, int) or not 0 <= Offset < len(Text)):
		raise ValueError("start-offset is outside the extracted text")
	Passage = "".join(Text[Offset:].splitlines(keepends=True)[:MaxLines])[:12000]
	EndOffset = Offset + len(Passage)
	StartLine = Text[:Offset].count("\n") + 1
	EndLine = Text[:max(Offset, EndOffset - 1)].count("\n") + 1
	return dict(source_id=SourceId, metadata=Record, start_line=StartLine,
		end_line=EndLine, start_offset=Offset, next_offset=EndOffset if EndOffset < len(Text) else None,
		passage_sha256=digest(Passage.encode("utf-8")), content=Passage,
		locator_note="Extraction line numbers; verify original page/theorem separately.")


def collect_notes(project):
	Root = library_root(project) / "annotations"
	Notes = []
	for path in sorted(Root.glob("*.json")):
		path = inside(project, path)
		Note = read_json(path)
		if(digest(json_bytes(Note)) != path.stem):
			raise ValueError(f"annotation content hash mismatch: {path}")
		Notes.append(dict(path=relative(project, path), sha256=digest(path.read_bytes()), **Note))
	return Notes


def annotate(project, ToolPath, ExpectedHash, author, kind, locator, text, SourceId=None):
	Tool = inside(project, ToolPath)
	CurrentHash = digest(Tool.read_bytes())
	if(CurrentHash != ExpectedHash):
		raise ValueError("tool changed since it was read; read the current card before annotating")
	if(kind not in NOTE_KINDS or not all(str(Value).strip() for Value in (author, locator, text))):
		raise ValueError("annotation needs author, kind, exact locator and content")
	if(SourceId):
		read_source(project, SourceId, 1, 1)
	Note = dict(schema_version=1, tool_path=relative(project, Tool), tool_sha256=CurrentHash,
		author=author, kind=kind, locator=locator, content=text, source_id=SourceId,
		status="CANDIDATE_ANNOTATION")
	NoteId = digest(json_bytes(Note))
	with writer_lock(library_root(project)):
		if(digest(Tool.read_bytes()) != ExpectedHash):
			raise ValueError("tool changed during annotation")
		immutable_write(inside(project, library_root(project) / "annotations" / (NoteId + ".json")), json_bytes(Note))
	return dict(annotation_id=NoteId, **Note)


def make_index(project, ToolRoots, IndexPath="index/tools.json", ReadmePath=None):
	Root = Path(project).resolve()
	Index = inside(Root, IndexPath)
	Roots = [inside(Root, path) for path in ToolRoots]
	if(not Roots or any(not path.is_dir() for path in Roots)):
		raise ValueError("all tool roots must exist")
	Readme = inside(Root, ReadmePath) if ReadmePath else None
	with writer_lock(library_root(Root)):
		Previous = read_json(Index) if Index.exists() else dict(schema_version=1, items=[])
		if(not isinstance(Previous, dict) or not isinstance(Previous.get("items"), list)):
			raise ValueError("tool index must be an object with an items array")
		ByPath = dict()
		for Item in Previous["items"]:
			if(not isinstance(Item, dict) or not isinstance(Item.get("location"), str) or Item["location"] in ByPath):
				raise ValueError("legacy index entries need distinct string locations")
			ByPath[Item["location"]] = Item
		Notes = collect_notes(Root)
		Rows, SeenIds, SeenPaths = [], set(), set()
		for ToolRoot in Roots:
			for path in sorted(ToolRoot.rglob("*.md")):
				path = inside(Root, path)
				if(path.name.lower() == "readme.md" or path == Readme or path in SeenPaths):
					continue
				SeenPaths.add(path)
				Raw = path.read_bytes()
				Front, Body = read_tool(path)
				Front = Front or dict()
				if(not isinstance(Front, dict)):
					raise ValueError(f"tool frontmatter must be a mapping: {path}")
				Body = Body if Body is not None else Raw.decode("utf-8")
				Location = relative(Root, path)
				Old = ByPath.pop(Location, dict())
				ToolId = str(Old.get("tool_id") or Front.get("tool_id") or Front.get("slug") or path.stem)
				if(ToolId in SeenIds):
					raise ValueError(f"duplicate tool ID: {ToolId}")
				SeenIds.add(ToolId)
				Headings = re.findall(r"^#\s+(.+)$", Body, re.M)
				Summary = Front.get("summary") or Old.get("summary") or ""
				Applicability = Front.get("applicability", Old.get("applicability", []))
				Lifecycle = derived_status(dict(applicability=Applicability))
				if("applicability" not in Front):
					Lifecycle = Old.get("lifecycle", Lifecycle)
				Row = dict(Old)
				Row.update(tool_id=ToolId, location=Location, sha256=digest(Raw),
					title=str(Front.get("title") or Old.get("title") or (Headings[0] if Headings else ToolId)),
					summary=str(Summary)[:500], aliases=Front.get("aliases", Old.get("aliases", [])),
					kind=Front.get("kind", Old.get("kind", "unknown")),
					applicability=Applicability, lifecycle=Lifecycle,
					pointer_state="CURRENT", trust="RETRIEVAL_ONLY_REVALIDATE_APPLICATION")
				Row["annotations"] = [dict(path=Note["path"], sha256=Note["sha256"],
					kind=Note["kind"], state="CURRENT" if Note["tool_sha256"] == Row["sha256"] else "STALE")
					for Note in Notes if Note["tool_path"] == Location]
				Rows.append(Row)
		for Item in ByPath.values():
			Row = dict(Item, pointer_state="UNSCANNED")
			if(Row.get("tool_id") in SeenIds):
				raise ValueError("unscanned legacy entry collides with a current tool ID")
			Rows.append(Row)
		Previous.update(items=Rows, updated_at=utc_now(),
			pointer_schema="tool-pointers/v1", tool_roots=[relative(Root, path) for path in Roots],
			generated_readme=relative(Root, Readme) if Readme else None)
		ReadmeBytes = None
		if(Readme):
			Text = Readme.read_bytes().decode("utf-8") if Readme.exists() else "# Mathematical tools\n"
			if(Text.count(START) != Text.count(END) or Text.count(START) > 1 or (START in Text and Text.index(START) > Text.index(END))):
				raise ValueError("malformed generated pointer markers")
			Table = [START, "", "## Generated retrieval pointers", "", "Cards and agent annotations are retrieval leads; verify applicability before reuse.", "", "| Tool | Card | Annotations |", "| --- | --- | --- |"]
			for Row in Rows:
				if(Row.get("pointer_state") != "CURRENT"):
					continue
				Link = os.path.relpath(Root / Row["location"], Readme.parent).replace("\\", "/")
				Label = Row["tool_id"].replace("|", "\\|")
				Table.append(f"| {Label} | [card](<{Link}>) | {len(Row['annotations'])} |")
			Table.extend(["", END])
			Block = "\n".join(Table)
			if(START in Text):
				Text = Text[:Text.index(START)] + Block + Text[Text.index(END) + len(END):]
			else:
				Text = Text.rstrip("\n") + "\n\n" + Block + "\n"
			ReadmeBytes = Text.encode("utf-8")
		for Row in Rows:
			if(Row.get("pointer_state") == "CURRENT" and digest(inside(Root, Row["location"]).read_bytes()) != Row["sha256"]):
				raise ValueError("tool changed while building pointers; retry indexing")
		atomic_write(Index, json_bytes(Previous))
		if(ReadmeBytes is not None):
			atomic_write(Readme, ReadmeBytes)
	return dict(index=relative(Root, Index), indexed=sum(Row.get("pointer_state") == "CURRENT" for Row in Rows),
		retained_unscanned=sum(Row.get("pointer_state") == "UNSCANNED" for Row in Rows))


def query_tools(project, query, IndexPath="index/tools.json", limit=8, IncludeArchived=False):
	if(not query.strip() or not 1 <= limit <= 50):
		raise ValueError("query is required and limit must be in 1..50")
	Index = read_json(inside(project, IndexPath))
	if(Index.get("pointer_schema") != "tool-pointers/v1"):
		raise ValueError("build a current pointer index before querying")
	Notes = collect_notes(project)
	Hits, Stale = [], []
	KnownPaths = set(Row["location"] for Row in Index["items"] if Row.get("pointer_state") == "CURRENT")
	LivePaths = set()
	for ToolRoot in Index["tool_roots"]:
		for path in inside(project, ToolRoot).rglob("*.md"):
			Location = relative(project, inside(project, path))
			if(path.name.lower() != "readme.md" and Location != Index.get("generated_readme")):
				LivePaths.add(Location)
	if(LivePaths != KnownPaths):
		return dict(verdict="STALE_INDEX", changed_paths=sorted(LivePaths ^ KnownPaths), hits=[])
	Terms = query.casefold().split()
	for Row in Index["items"]:
		if(Row.get("pointer_state") != "CURRENT"):
			continue
		path = inside(project, Row["location"])
		if(not path.is_file() or digest(path.read_bytes()) != Row["sha256"]):
			Stale.append(Row["location"])
			continue
		if(not IncludeArchived and Row.get("lifecycle") == "archived"):
			continue
		ToolNotes = [dict(Note, state="CURRENT" if Note["tool_sha256"] == Row["sha256"] else "STALE")
			for Note in Notes if Note["tool_path"] == Row["location"]]
		SearchText = json.dumps([Row["tool_id"], Row["title"], Row["summary"], Row["aliases"], Row["kind"],
			Row["applicability"], [Note["content"] for Note in ToolNotes if Note["state"] == "CURRENT"]], ensure_ascii=False).casefold()
		Score = sum(Term in SearchText for Term in Terms)
		if(Score):
			Hits.append(dict(score=Score, tool_id=Row["tool_id"], title=Row["title"],
				location=Row["location"], sha256=Row["sha256"], summary=Row["summary"],
				trust=Row["trust"], annotations=[dict(path=Note["path"], sha256=Note["sha256"],
					kind=Note["kind"], state=Note["state"]) for Note in ToolNotes]))
	if(Stale):
		return dict(verdict="STALE_INDEX", changed_paths=Stale, hits=[])
	Hits.sort(key=lambda Item: (-Item["score"], Item["tool_id"]))
	return dict(verdict="RETRIEVAL_ONLY", hits=Hits[:limit], total_matches=len(Hits))


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Sub = Parser.add_subparsers(dest="command", required=True)
	Capture = Sub.add_parser("capture-source")
	for name in ("project", "input", "url", "version", "title"):
		Capture.add_argument("--" + name, required=True)
	Capture.add_argument("--text-file")
	Capture.add_argument("--method", default="provided-text")
	Capture.add_argument("--source-kind", choices=("primary", "secondary"), default="primary")
	Find = Sub.add_parser("find-source")
	Find.add_argument("--project", required=True)
	Find.add_argument("--query", required=True)
	Find.add_argument("--limit", type=int, default=8)
	Read = Sub.add_parser("read-source")
	Read.add_argument("--project", required=True)
	Read.add_argument("--source-id", required=True)
	Read.add_argument("--start-line", type=int, default=1)
	Read.add_argument("--max-lines", type=int, default=80)
	Read.add_argument("--start-offset", type=int)
	Note = Sub.add_parser("annotate")
	for name in ("project", "tool", "expected-sha256", "author", "kind", "locator", "text-file"):
		Note.add_argument("--" + name, required=True)
	Note.add_argument("--source-id")
	Index = Sub.add_parser("index")
	Index.add_argument("--project", required=True)
	Index.add_argument("--tool-root", action="append", required=True)
	Index.add_argument("--index", default="index/tools.json")
	Index.add_argument("--readme")
	Query = Sub.add_parser("query")
	Query.add_argument("--project", required=True)
	Query.add_argument("--query", required=True)
	Query.add_argument("--index", default="index/tools.json")
	Query.add_argument("--limit", type=int, default=8)
	Query.add_argument("--include-archived", action="store_true")
	Args = Parser.parse_args()
	try:
		if(Args.command == "capture-source"):
			Result = capture_source(Args.project, Args.input, Args.url, Args.version, Args.title, Args.text_file, Args.method, Args.source_kind)
		elif(Args.command == "find-source"):
			Result = find_sources(Args.project, Args.query, Args.limit)
		elif(Args.command == "read-source"):
			Result = read_source(Args.project, Args.source_id, Args.start_line, Args.max_lines, Args.start_offset)
		elif(Args.command == "annotate"):
			Result = annotate(Args.project, Args.tool, Args.expected_sha256, Args.author, Args.kind, Args.locator,
				Path(Args.text_file).read_text(encoding="utf-8"), Args.source_id)
		elif(Args.command == "index"):
			Result = make_index(Args.project, Args.tool_root, Args.index, Args.readme)
		else:
			Result = query_tools(Args.project, Args.query, Args.index, Args.limit, Args.include_archived)
		print(json.dumps(Result, ensure_ascii=False))
		return 1 if Result.get("verdict") == "STALE_INDEX" else 0
	except (OSError, ValueError, TypeError, KeyError, RuntimeError) as Error:
		print(json.dumps(dict(verdict="INVALID", error=str(Error)), ensure_ascii=False))
		return 1


if(__name__ == "__main__"):
	raise SystemExit(main())
