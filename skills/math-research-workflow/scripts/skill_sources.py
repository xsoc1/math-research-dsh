#!/usr/bin/env python3
"""Inventory physical copies of named skills without choosing or changing one."""

import hashlib
from pathlib import Path
import re


def source_inventory(CodexHome, ListingText, names):
	Root = Path(CodexHome)
	Rows = []
	for Line in ListingText.splitlines():
		Parts = re.split(r"\s{2,}", Line.strip(), maxsplit=3)
		if(len(Parts) == 4 and "@" in Parts[0]):
			Rows.append(Parts)
	Result = []
	for name in sorted(set(names)):
		Candidates = [(Root / "skills" / name / "SKILL.md", "plain_skill", None, None)]
		for Key, Status, Version, Source in Rows:
			if(Key.split("@", 1)[0] != name):
				continue
			Enabled = {Token.strip() for Token in Status.split(",")} >= {"installed", "enabled"}
			Candidates.append((Path(Source) / "skills" / name / "SKILL.md", "marketplace_source", Key, Enabled))
			Cache = Root / "plugins" / "cache" / Key.split("@", 1)[1] / name / Version / "skills" / name / "SKILL.md"
			Candidates.append((Cache, "listed_version_cache", Key, Enabled))
		Copies, Seen = [], set()
		for path, Kind, Key, Enabled in Candidates:
			if(not path.is_file() or path.resolve() in Seen):
				continue
			Seen.add(path.resolve())
			Data = path.read_bytes()
			Copies.append(dict(path=str(path.resolve()), kind=Kind, plugin=Key,
				listed_enabled=Enabled, bytes=len(Data), sha256=hashlib.sha256(Data).hexdigest()))
		Result.append(dict(name=name, copies=Copies,
			different_content=len({Item["sha256"] for Item in Copies}) > 1))
	return dict(skills=Result, selection="NOT_INFERRED",
		instruction="Resolve the loaded SKILL.md path before running its helpers. Physical copies do not prove which skill was loaded or its token cost.")
