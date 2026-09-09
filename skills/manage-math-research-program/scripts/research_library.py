#!/usr/bin/env python3
"""Capture source bytes, retrieve bounded passages, index tool cards and annotate them.

All records are retrieval aids, never accepted mathematical premises. This tool
does not search the network, extract PDFs or modify a Blueprint accepted graph.
Feed it actual browser retrievals or extracted text with the raw source attached.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

try:
	import yaml
except ImportError:
	yaml = None

START = "<!-- research-tool-pointers:v1:start -->"
END = "<!-- research-tool-pointers:v1:end -->"
NOTE_KINDS = ("retrieval_hint", "applicability", "correction", "failure", "observation")
POINTER_SCHEMA = "tool-pointers/v2"


def utc_now():
	return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(Data):
	return hashlib.sha256(Data).hexdigest()


def json_bytes(Data):
	return (json.dumps(Data, ensure_ascii=False, sort_keys=True, indent="\t", allow_nan=False) + "\n").encode("utf-8")


def read_json(path):
	return json.loads(path.read_text(encoding="utf-8-sig"))


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


def issue(path, Error):
	return dict(path=str(path), state="INVALID", error=str(Error))


def read_metadata(Raw):
	Text = Raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
	Header = re.match(r"\A---[ \t]*\n(.*?)^---[ \t]*(?:\n|\Z)(.*)\Z", Text, re.M | re.S)
	if(not Header):
		if(re.match(r"\A---[ \t]*(?:\n|$)", Text)):
			raise ValueError("opening header has no closing delimiter")
		return dict(), Text, "ABSENT"
	try:
		Front = json.loads(Header[1])
	except ValueError:
		if(yaml is None):
			raise ValueError("PyYAML is needed to read this legacy YAML header")
		try:
			Front = yaml.safe_load(Header[1])
		except yaml.YAMLError as Error:
			raise ValueError(str(Error)) from Error
	Front = dict() if Front is None else Front
	if(not isinstance(Front, dict)):
		raise ValueError("tool frontmatter must be a mapping")
	for Key in ("aliases", "applicability", "sources", "evidence", "resources", "lean"):
		if(Key in Front and not isinstance(Front[Key], list)):
			raise ValueError(f"{Key} must be a list")
	if("conditions" in Front and not isinstance(Front["conditions"], (str, list))):
		raise ValueError("conditions must be text or a list")
	if("experience" in Front and not isinstance(Front["experience"], dict)):
		raise ValueError("experience must be an object")
	return Front, Header[2], "VALID"


def derived_status(Front):
	Statuses = {str(Row.get("status", "")) for Row in Front.get("applicability", []) if isinstance(Row, dict)}
	for Status, Lifecycle in (("active", "active"), ("conditional", "conditional"), ("retired", "archived")):
		if(Status in Statuses):
			return Lifecycle
	return "unclassified"


def snapshot_card(project, Raw):
	Path = inside(project, library_root(project) / "card-versions" / (digest(Raw) + ".md"))
	immutable_write(Path, Raw)
	return relative(project, Path)


def bind_references(project, References):
	if(not isinstance(References, list)):
		raise ValueError("references must be a list")
	Bound = []
	for Reference in References:
		Reference = dict(path=Reference) if isinstance(Reference, str) else dict(Reference)
		if(Reference.get("path")):
			Path = inside(project, Reference["path"])
			Hash = digest(Path.read_bytes())
			if(Reference.get("sha256", Hash) != Hash):
				raise ValueError(f"referenced bytes changed: {Reference['path']}")
			Reference.update(path=relative(project, Path), sha256=Hash)
		elif(Reference.get("source_id")):
			read_source(project, Reference["source_id"], 1, 1)
		elif(not Reference.get("url")):
			raise ValueError("a reference needs a local path, captured source_id or URL")
		Bound.append(Reference)
	return Bound


def reference_states(project, References):
	States = []
	for Reference in References:
		try:
			if(not isinstance(Reference, dict)):
				raise ValueError("reference is not an object")
			State = dict(Reference, binding_state="UNBOUND_REFERENCE")
			if(Reference.get("path")):
				Hash = digest(inside(project, Reference["path"]).read_bytes())
				State["binding_state"] = "CURRENT" if Reference.get("sha256") == Hash else "STALE_OR_UNBOUND"
			elif(Reference.get("source_id")):
				read_source(project, Reference["source_id"], 1, 1)
				State["binding_state"] = "CURRENT"
		except (OSError, ValueError, TypeError, KeyError) as Error:
			State = dict(reference=Reference, binding_state="INVALID", error=str(Error))
		States.append(State)
	return States


def lean_reference_states(project, References):
	States = []
	for Reference in References:
		if(not isinstance(Reference, dict)):
			States.append(dict(reference=Reference, trust="INVALID_REFERENCE"))
			continue
		State = dict(Reference, trust="UNVERIFIED_DECLARATION_REFERENCE")
		for Key in ("source", "verification"):
			if(Reference.get(Key)):
				State[Key] = reference_states(project, [Reference[Key]])[0]
		if(Reference.get("definitions")):
			State["definitions"] = reference_states(project, Reference["definitions"])
		State["identity_fields_missing"] = [Key for Key in ("repository", "commit", "module", "declaration", "environment", "actual_type") if not Reference.get(Key)]
		States.append(State)
	return States


def save_card(project, Data, ToolPath=None, ExpectedHash=None):
	"""Save a small card. Changed existing bytes require the hash the caller read."""
	Data = dict(Data)
	Content = Data.pop("content", "")
	if(not isinstance(Content, str) or not Content.strip()):
		raise ValueError("a card needs nonempty content")
	for Key in ("sources", "evidence", "resources"):
		if(Key in Data):
			Data[Key] = bind_references(project, Data[Key])
	if("lean" in Data and (not isinstance(Data["lean"], list) or any(not isinstance(Item, dict) for Item in Data["lean"]))):
		raise ValueError("lean must be a list of declaration references")
	if("lean" in Data):
		Data["lean"] = [dict(Item) for Item in Data["lean"]]
		for Reference in Data["lean"]:
			for Key in ("source", "verification"):
				if(Reference.get(Key)):
					Reference[Key] = bind_references(project, [Reference[Key]])[0]
			if(Reference.get("definitions")):
				Reference["definitions"] = bind_references(project, Reference["definitions"])
	ToolId = str(Data.get("tool_id") or (Path(ToolPath).stem if ToolPath else "tool-" + digest(json_bytes([Data, Content]))[:20]))
	PathValue = ToolPath or "tools/" + ToolId + ".md"
	Target = inside(project, PathValue)
	if(Target.suffix != ".md" or Target.name.lower() == "readme.md"):
		raise ValueError("a card needs its own .md path")
	with writer_lock(library_root(project)):
		Old = Target.read_bytes() if Target.exists() else None
		if(Old is not None):
			Front, _, _ = read_metadata(Old)
			ToolId = str(Front.get("tool_id") or Front.get("slug") or ToolId)
			if(Data.get("tool_id", ToolId) != ToolId):
				raise ValueError("keep the existing card identity; create a separate card for a different tool")
			Data = dict(Front, **Data)
		Data.update(tool_id=ToolId)
		Data.setdefault("evidence_status", "CANDIDATE")
		Raw = ("---\n" + json.dumps(Data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n---\n" + Content.rstrip("\n") + "\n").encode("utf-8")
		read_metadata(Raw)
		if(Old != Raw and Old is not None and digest(Old) != ExpectedHash):
			raise ValueError("existing card differs; pass its current --expected-sha256")
		if(Old is None and ExpectedHash is not None):
			raise ValueError("expected an existing card but it is missing")
		if(Old is not None):
			snapshot_card(project, Old)
		Version = snapshot_card(project, Raw)
		if(Old != Raw):
			atomic_write(Target, Raw)
	return dict(tool_id=ToolId, location=relative(project, Target), sha256=digest(Raw),
		version=Version, reused=Old == Raw, trust="RETRIEVAL_ONLY_REVALIDATE_APPLICATION")


def immutable_write(path, Data):
	path.parent.mkdir(parents=True, exist_ok=True)
	if(path.exists()):
		if(path.read_bytes() != Data):
			raise ValueError(f"immutable record conflict: {path}")
		return
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


def find_sources(project, query, limit=8, SearchContent=False):
	if(not query.strip() or not 1 <= limit <= 50):
		raise ValueError("query is required and limit must be in 1..50")
	Hits, Issues = [], []
	Terms = query.casefold().split()
	for path in sorted((library_root(project) / "sources").glob("*/source.json")):
		try:
			path = inside(project, path)
			Record = read_json(path)
			if(digest(json_bytes(Record)) != path.parent.name):
				raise ValueError("source metadata hash mismatch")
			SearchText = " ".join(Record[Key] for Key in ("url", "title", "version")).casefold()
			if(SearchContent):
				read_source(project, path.parent.name, 1, 1)
				SearchText += " " + (path.parent / "text.txt").read_text(encoding="utf-8").casefold()
		except (OSError, ValueError, KeyError, TypeError) as Error:
			Issues.append(issue(path, Error))
			continue
		Score = sum(Term in SearchText for Term in Terms)
		if(Score):
			Hits.append(dict(score=Score, source_id=path.parent.name,
				source=relative(project, path), **Record))
	Hits.sort(key=lambda Item: (-Item["score"], Item["source_id"]))
	return dict(verdict="RETRIEVAL_ONLY", hits=Hits[:limit], total_matches=len(Hits), issues=Issues)


def capture_source(project, InputPath, url, version, title, TextPath=None, method="provided-text", SourceKind="primary", Coverage=None, Locators=None):
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
	if(Coverage is not None):
		Record["coverage"] = str(Coverage)
	if(Locators):
		Record["original_locators"] = list(Locators)
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
	LineStarts, Position = [], 0
	for Line in Lines:
		LineStarts.append(Position)
		Position += len(Line)
	StartLine = bisect_right(LineStarts, Offset)
	EndLine = bisect_right(LineStarts, max(Offset, EndOffset - 1))
	return dict(source_id=SourceId, metadata=Record, start_line=StartLine,
		end_line=EndLine, start_offset=Offset, next_offset=EndOffset if EndOffset < len(Text) else None,
		passage_sha256=digest(Passage.encode("utf-8")), content=Passage,
		locator_note="Extraction line numbers; verify original page/theorem separately.")


def collect_notes(project, Issues=None):
	Root = library_root(project) / "annotations"
	Notes = []
	for path in sorted(Root.glob("*.json")):
		try:
			path = inside(project, path)
			Note = read_json(path)
			if(digest(json_bytes(Note)) != path.stem):
				raise ValueError("annotation content hash mismatch")
			if(any(not isinstance(Note.get(Key), str) for Key in ("tool_path", "tool_sha256", "kind", "content"))):
				raise ValueError("annotation has invalid fields")
			Notes.append(dict(Note, path=relative(project, path), sha256=digest(path.read_bytes())))
		except (OSError, ValueError, TypeError, KeyError) as Error:
			if(Issues is None):
				raise
			Issues.append(issue(path, Error))
	return Notes


def annotate(project, ToolPath, ExpectedHash=None, author="unspecified", kind="observation", locator="card", text="", SourceId=None):
	Tool = inside(project, ToolPath)
	CurrentHash = digest(Tool.read_bytes())
	ExpectedHash = CurrentHash if ExpectedHash is None else ExpectedHash
	if(CurrentHash != ExpectedHash):
		raise ValueError("tool changed since it was read; read the current card before annotating")
	if(not all(isinstance(Value, str) and Value.strip() for Value in (author, kind, locator, text))):
		raise ValueError("annotation needs author, kind, exact locator and content")
	if(SourceId):
		read_source(project, SourceId, 1, 1)
	Note = dict(schema_version=1, tool_path=relative(project, Tool), tool_sha256=CurrentHash,
		author=author, kind=kind, locator=locator, content=text, source_id=SourceId,
		status="CANDIDATE_ANNOTATION")
	NoteId = digest(json_bytes(Note))
	with writer_lock(library_root(project)):
		Raw = Tool.read_bytes()
		if(digest(Raw) != ExpectedHash):
			raise ValueError("tool changed during annotation")
		snapshot_card(project, Raw)
		immutable_write(inside(project, library_root(project) / "annotations" / (NoteId + ".json")), json_bytes(Note))
	return dict(annotation_id=NoteId, **Note)


def card_paths(project, Roots, ReadmePath=None, Issues=None):
	Paths = set()
	for ToolRoot in Roots:
		try:
			Root = inside(project, ToolRoot)
			if(not Root.is_dir()):
				raise ValueError("tool root is missing")
			for PathValue in Root.rglob("*.md"):
				try:
					Location = relative(project, inside(project, PathValue))
					if(PathValue.name.lower() != "readme.md" and Location != ReadmePath):
						Paths.add(Location)
				except (OSError, ValueError) as Error:
					if(Issues is not None):
						Issues.append(issue(PathValue, Error))
		except (OSError, ValueError) as Error:
			if(Issues is not None):
				Issues.append(issue(ToolRoot, Error))
	return Paths


def annotation_pointers(Notes, Row):
	return [dict(path=Note["path"], sha256=Note["sha256"], kind=Note["kind"],
		author=Note.get("author", "unspecified"), locator=Note.get("locator", "card"), source_id=Note.get("source_id"),
		tool_sha256=Note["tool_sha256"], state="CURRENT" if Note["tool_sha256"] == Row["sha256"] else "STALE")
		for Note in Notes if Note["tool_path"] == Row["location"]]


def parse_card(project, Location, Raw, Old):
	MetadataError = None
	try:
		Front, Body, MetadataStatus = read_metadata(Raw)
	except (ValueError, TypeError) as Error:
		Front, Body, MetadataStatus = dict(), Raw.decode("utf-8", errors="replace"), "UNPARSEABLE"
		MetadataError = str(Error)
	ToolId = str(Old.get("tool_id") or Front.get("tool_id") or Front.get("slug") or Path(Location).stem)
	Headings = re.findall(r"^#\s+(.+)$", Body, re.M)
	Applicability = Front.get("applicability", Old.get("applicability", []))
	Lifecycle = derived_status(dict(applicability=Applicability)) if isinstance(Applicability, list) else "unclassified"
	if("applicability" not in Front):
		Lifecycle = Old.get("lifecycle", Lifecycle)
	Row = dict(Old)
	Row.update(tool_id=ToolId, location=Location, sha256=digest(Raw),
		metadata_status=MetadataStatus, metadata_error=MetadataError,
		title=str(Front.get("title") or Old.get("title") or (Headings[0] if Headings else ToolId)),
		summary=str(Front.get("summary") or Old.get("summary") or re.sub(r"\s+", " ", Body).strip())[:500],
		aliases=Front.get("aliases", Old.get("aliases", [])), kind=Front.get("kind", Old.get("kind", "tool")),
		applicability=Applicability, lifecycle=Lifecycle,
		pointer_state="CURRENT", trust="RETRIEVAL_ONLY_REVALIDATE_APPLICATION")
	Defaults = dict(conditions="UNSPECIFIED", scope="UNSPECIFIED", sources=[], evidence=[], resources=[], lean=[], experience=dict(), evidence_status="UNKNOWN")
	Row["inherited_metadata"] = [Key for Key in ("applicability", "lifecycle", *Defaults) if Key not in Front and Key in Old]
	for Key, Default in Defaults.items():
		Row[Key] = Front.get(Key, Old.get(Key, Default))
	json_bytes(Row)
	Row["version"] = snapshot_card(project, Raw)
	return Row


def make_index(project, ToolRoots=None, IndexPath="index/tools.json", ReadmePath=None, PreviousIndex=None):
	Root = Path(project).resolve()
	Index = inside(Root, IndexPath)
	with writer_lock(library_root(Root)):
		IndexBefore = Index.read_bytes() if Index.exists() else None
		if(PreviousIndex is not None and IndexBefore is not None):
			raise ValueError("--from-index requires a missing destination index; preserve an existing index before explicit recovery")
		MetadataBytes = inside(Root, PreviousIndex).read_bytes() if PreviousIndex is not None else IndexBefore
		Previous = json.loads(MetadataBytes.decode("utf-8-sig")) if MetadataBytes is not None else dict(schema_version=1, items=[])
		if(not isinstance(Previous, dict) or not isinstance(Previous.get("items"), list)):
			raise ValueError("tool index must be an object with an items array; preserve damaged bytes before rebuilding")
		RootValues = ToolRoots or Previous.get("tool_roots") or [Name for Name in ("tools", "knowledge/tools") if (Root / Name).is_dir()]
		Roots = list(dict.fromkeys(relative(Root, inside(Root, PathValue)) for PathValue in RootValues))
		ExperienceRoot = relative(Root, library_root(Root) / "experiences")
		if((Root / ExperienceRoot).is_dir() and ExperienceRoot not in Roots):
			Roots.append(ExperienceRoot)
		if(not Roots):
			raise ValueError("no card roots found; pass --tool-root")
		ReadmePath = ReadmePath if ReadmePath is not None else Previous.get("generated_readme")
		Readme = inside(Root, ReadmePath) if ReadmePath else None
		if(Readme == Index):
			raise ValueError("index and README must use different paths")
		ByPath = dict()
		for Item in Previous["items"]:
			if(not isinstance(Item, dict) or not isinstance(Item.get("location"), str) or Item["location"] in ByPath):
				raise ValueError("legacy index entries need distinct string locations; original index has not been changed")
			ByPath[Item["location"]] = Item
		Issues = []
		Notes = collect_notes(Root, Issues)
		Rows, Parsed, Reused = [], 0, 0
		Paths = card_paths(Root, Roots, relative(Root, Readme) if Readme else None, Issues)
		for Location in sorted(Paths):
			Old = ByPath.pop(Location, dict())
			try:
				Raw = inside(Root, Location).read_bytes()
				if(Previous.get("pointer_schema") == POINTER_SCHEMA and "scope" in Old and Old.get("sha256") == digest(Raw) and Old.get("metadata_status") != "UNPARSEABLE"):
					Row = dict(Old, pointer_state="CURRENT")
					Row["version"] = snapshot_card(Root, Raw)
					Reused += 1
				else:
					Row = parse_card(Root, Location, Raw, Old)
					Parsed += 1
				Row["annotations"] = annotation_pointers(Notes, Row)
				Row.pop("identity_error", None)
				Rows.append(Row)
			except (OSError, ValueError, TypeError) as Error:
				Issues.append(issue(Location, Error))
				Rows.append(dict(Old, location=Location, pointer_state="INVALID", metadata_status="UNPARSEABLE", metadata_error=str(Error)))
		Rows.extend(dict(Item, pointer_state="UNSCANNED") for Item in ByPath.values())
		ById = dict()
		for Row in Rows:
			if(Row.get("tool_id")):
				ById.setdefault(Row["tool_id"], []).append(Row)
		for ToolId, Duplicates in ById.items():
			if(len(Duplicates) > 1):
				for Row in Duplicates:
					Row["identity_error"] = f"duplicate tool ID: {ToolId}; use the exact path and resolve identity explicitly"
		Previous.update(items=Rows, pointer_schema=POINTER_SCHEMA, tool_roots=Roots,
			generated_readme=relative(Root, Readme) if Readme else None, issues=Issues)
		ReadmeBytes, ReadmeBefore = None, None
		if(Readme):
			ReadmeBefore = Readme.read_bytes() if Readme.exists() else None
			Text = ReadmeBefore.decode("utf-8") if ReadmeBefore is not None else "# Mathematical tools\n"
			if(Text.count(START) != Text.count(END) or Text.count(START) > 1 or (START in Text and Text.index(START) > Text.index(END))):
				raise ValueError("malformed generated pointer markers")
			Table = [START, "", "## Generated retrieval pointers", "", "Cards and notes are retrieval leads. Check their scope and evidence before reuse.", "", "| Tool | Card | Annotations |", "| --- | --- | --- |"]
			for Row in Rows:
				if(Row.get("pointer_state") != "CURRENT"):
					continue
				Link = os.path.relpath(Root / Row["location"], Readme.parent).replace("\\", "/")
				Label = str(Row["tool_id"]).replace("|", "\\|").replace("\n", " ")
				Table.append(f"| {Label} | [card](<{Link}>) | {len(Row['annotations'])} |")
			Block = "\n".join(Table + ["", END])
			if(START in Text):
				Text = Text[:Text.index(START)] + Block + Text[Text.index(END) + len(END):]
			else:
				Text = Text + ("\n\n" if Text else "") + Block + "\n"
			ReadmeBytes = Text.encode("utf-8")
		for Row in Rows:
			if(Row.get("pointer_state") != "CURRENT"):
				continue
			try:
				if(digest(inside(Root, Row["location"]).read_bytes()) != Row["sha256"]):
					raise ValueError("card changed while building pointers; reindex this card")
			except (OSError, ValueError) as Error:
				Row["pointer_state"] = "STALE"
				Issues.append(issue(Row["location"], Error))
		if((Index.read_bytes() if Index.exists() else None) != IndexBefore):
			raise ValueError("index changed during refresh; retry against the current index")
		IndexChanged = IndexBefore is None or json.loads(IndexBefore.decode("utf-8-sig")) != Previous
		PreviousSnapshot = None
		if(IndexChanged and IndexBefore is not None):
			Snapshot = inside(Root, library_root(Root) / "index-history" / (digest(IndexBefore) + ".json"))
			immutable_write(Snapshot, IndexBefore)
			PreviousSnapshot = relative(Root, Snapshot)
		if(IndexChanged):
			Previous["updated_at"] = utc_now()
			atomic_write(Index, json_bytes(Previous))
		if(ReadmeBytes is not None):
			if((Readme.read_bytes() if Readme.exists() else None) != ReadmeBefore):
				raise ValueError("README changed while indexing; index is saved, retry the generated view")
			if(ReadmeBytes != ReadmeBefore):
				atomic_write(Readme, ReadmeBytes)
	return dict(index=relative(Root, Index), indexed=sum(Row.get("pointer_state") == "CURRENT" for Row in Rows),
		needs_metadata_review=[Row["location"] for Row in Rows if Row.get("metadata_status") == "UNPARSEABLE" or Row.get("identity_error")],
		retained_unscanned=sum(Row.get("pointer_state") == "UNSCANNED" for Row in Rows),
		parsed=Parsed, reused=Reused, index_changed=IndexChanged, previous_index_snapshot=PreviousSnapshot, issues=Issues)


def query_tools(project, query, IndexPath="index/tools.json", limit=8, IncludeArchived=False, IncludeUnreviewed=False, IncludeStale=False):
	if(not query.strip() or not 1 <= limit <= 50):
		raise ValueError("query is required and limit must be in 1..50")
	Index = read_json(inside(project, IndexPath))
	if(Index.get("pointer_schema") not in ("tool-pointers/v1", POINTER_SCHEMA)):
		raise ValueError("build a current pointer index before querying")
	Issues = list(Index.get("issues", []))
	Notes = collect_notes(project, Issues)
	Hits = []
	KnownPaths = set(Row["location"] for Row in Index["items"] if Row.get("pointer_state") == "CURRENT")
	LivePaths = card_paths(project, Index["tool_roots"], Index.get("generated_readme"), Issues)
	Stale = LivePaths ^ KnownPaths
	Terms = query.casefold().split()
	for Row in Index["items"]:
		if(Row.get("pointer_state") != "CURRENT"):
			continue
		try:
			Raw = inside(project, Row["location"]).read_bytes()
			if(digest(Raw) != Row["sha256"]):
				raise ValueError("card changed since indexing")
		except (OSError, ValueError, KeyError) as Error:
			Stale.add(Row["location"])
			Issues.append(issue(Row["location"], Error))
			continue
		if(not IncludeArchived and Row.get("lifecycle") == "archived"):
			continue
		if(not IncludeUnreviewed and (Row.get("metadata_status") == "UNPARSEABLE" or Row.get("identity_error"))):
			continue
		ToolNotes = [dict(Note, state="CURRENT" if Note["tool_sha256"] == Row["sha256"] else "STALE")
			for Note in Notes if Note["tool_path"] == Row["location"]]
		CurrentText = json.dumps([dict(Row, annotations=[]), Raw.decode("utf-8", errors="replace"),
			[Note for Note in ToolNotes if Note["state"] == "CURRENT"]], ensure_ascii=False, default=str).casefold()
		OldText = json.dumps([Note for Note in ToolNotes if Note["state"] == "STALE"], ensure_ascii=False).casefold()
		Score = sum(Term in CurrentText or (IncludeStale and Term in OldText) for Term in Terms)
		if(not Score):
			continue
		Hit = dict(score=Score, tool_id=Row["tool_id"], title=Row["title"], kind=Row.get("kind", "tool"),
			metadata_status=Row.get("metadata_status", "UNKNOWN"), identity_error=Row.get("identity_error"),
			location=Row["location"], sha256=Row["sha256"], version=Row.get("version"), summary=Row["summary"],
			conditions=Row.get("conditions", "UNSPECIFIED"), scope=Row.get("scope", "UNSPECIFIED"),
			applicability=Row.get("applicability", []), lifecycle=Row.get("lifecycle"),
			evidence_status=Row.get("evidence_status", "UNKNOWN"), trust=Row["trust"],
			inherited_metadata=Row.get("inherited_metadata", []),
			annotations=annotation_pointers(ToolNotes, Row),
			matched_historical_annotation=IncludeStale and any(Term in OldText for Term in Terms))
		for Key in ("sources", "evidence", "resources"):
			Hit[Key] = reference_states(project, Row.get(Key, []))
		Hit["lean"] = lean_reference_states(project, Row.get("lean", []))
		Hit["experience"] = Row.get("experience", dict())
		Hits.append(Hit)
	Hits.sort(key=lambda Item: (-Item["score"], Item["tool_id"], Item["location"]))
	return dict(verdict="STALE_INDEX" if Stale else "RETRIEVAL_ONLY", changed_paths=sorted(Stale),
		hits=Hits[:limit], total_matches=len(Hits), issues=Issues)


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Sub = Parser.add_subparsers(dest="command", required=True)
	Capture = Sub.add_parser("capture-source")
	for name in ("project", "input", "url", "version", "title"):
		Capture.add_argument("--" + name, required=True)
	Capture.add_argument("--text-file")
	Capture.add_argument("--method", default="provided-text")
	Capture.add_argument("--source-kind", choices=("primary", "secondary"), default="primary")
	Capture.add_argument("--coverage", help="what was actually retrieved: full text, pages, abstract or excerpt")
	Capture.add_argument("--locator", action="append", help="original page, theorem or equation locator")
	Find = Sub.add_parser("find-source")
	Find.add_argument("--project", required=True)
	Find.add_argument("--query", required=True)
	Find.add_argument("--limit", type=int, default=8)
	Find.add_argument("--content", action="store_true", help="also search verified captured text bytes")
	Read = Sub.add_parser("read-source")
	Read.add_argument("--project", required=True)
	Read.add_argument("--source-id", required=True)
	Read.add_argument("--start-line", type=int, default=1)
	Read.add_argument("--max-lines", type=int, default=80)
	Read.add_argument("--start-offset", type=int)
	Note = Sub.add_parser("annotate")
	for name in ("project", "tool", "text-file"):
		Note.add_argument("--" + name, required=True)
	Note.add_argument("--expected-sha256")
	Note.add_argument("--author", default="unspecified")
	Note.add_argument("--kind", default="observation")
	Note.add_argument("--locator", default="card")
	Note.add_argument("--source-id")
	Card = Sub.add_parser("card", help="save JSON containing content and optional title, conditions and references")
	Card.add_argument("--project", required=True)
	Card.add_argument("--input", required=True)
	Card.add_argument("--tool")
	Card.add_argument("--expected-sha256")
	Index = Sub.add_parser("index")
	Index.add_argument("--project", required=True)
	Index.add_argument("--tool-root", action="append")
	Index.add_argument("--index", default="index/tools.json")
	Index.add_argument("--readme")
	Index.add_argument("--from-index", help="recover metadata from a preserved index after the destination index was lost")
	Query = Sub.add_parser("query")
	Query.add_argument("--project", required=True)
	Query.add_argument("--query", required=True)
	Query.add_argument("--index", default="index/tools.json")
	Query.add_argument("--limit", type=int, default=8)
	Query.add_argument("--include-archived", action="store_true")
	Query.add_argument("--include-unreviewed", action="store_true")
	Query.add_argument("--include-stale", action="store_true", help="also match historical annotations, marked STALE")
	Args = Parser.parse_args()
	try:
		if(Args.command == "capture-source"):
			Result = capture_source(Args.project, Args.input, Args.url, Args.version, Args.title, Args.text_file, Args.method, Args.source_kind, Args.coverage, Args.locator)
		elif(Args.command == "find-source"):
			Result = find_sources(Args.project, Args.query, Args.limit, Args.content)
		elif(Args.command == "read-source"):
			Result = read_source(Args.project, Args.source_id, Args.start_line, Args.max_lines, Args.start_offset)
		elif(Args.command == "annotate"):
			Result = annotate(Args.project, Args.tool, Args.expected_sha256, Args.author, Args.kind, Args.locator,
				Path(Args.text_file).read_text(encoding="utf-8"), Args.source_id)
		elif(Args.command == "index"):
			Result = make_index(Args.project, Args.tool_root, Args.index, Args.readme, Args.from_index)
		elif(Args.command == "card"):
			Result = save_card(Args.project, read_json(Path(Args.input)), Args.tool, Args.expected_sha256)
		else:
			Result = query_tools(Args.project, Args.query, Args.index, Args.limit, Args.include_archived, Args.include_unreviewed, Args.include_stale)
		print(json.dumps(Result, ensure_ascii=False))
		return 1 if Result.get("verdict") == "STALE_INDEX" else 0
	except (OSError, ValueError, TypeError, KeyError, RuntimeError) as Error:
		print(json.dumps(dict(verdict="INVALID", error=str(Error)), ensure_ascii=False))
		return 1


if(__name__ == "__main__"):
	raise SystemExit(main())
