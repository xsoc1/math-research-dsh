#!/usr/bin/env python3
"""Bind author-written STORE resource explanations to the distributed bytes.

This gate detects inventory drift. It does not grant a STORE or security verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = "docs/dsh-store-resource-review.json"
MANIFEST_PATH = "skills/manage-math-research-program/MANIFEST.sha256"
REVIEW_METADATA = ["upstream.lock.json", REVIEW_PATH, "docs/dsh-store-resource-review.md"]
BOUNDARY_FIELDS = ("purpose", "activation", "execution", "file_access", "external_calls", "failure_boundary")


def require(Condition: bool, Message: str) -> None:
	if(not Condition):
		raise ValueError(Message)


def unique_object(Pairs: list) -> dict:
	Result = {}
	for Key, Value in Pairs:
		require(Key not in Result, f"duplicate JSON key: {Key}")
		Result[Key] = Value
	return Result


def read_json(FilePath: Path) -> dict:
	return json.loads(FilePath.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def safe_file(Root: Path, Relative: str) -> Path:
	require(isinstance(Relative, str) and bool(Relative), "empty resource path")
	require(not re.search(r"[\\:\x00\r\n]", Relative), f"invalid resource path: {Relative}")
	require(all(Part not in ("", ".", "..") for Part in Relative.split("/")), f"unsafe resource path: {Relative}")
	require(not PurePosixPath(Relative).is_absolute(), f"absolute resource path: {Relative}")
	FilePath = Root / Relative
	require(FilePath.resolve().is_relative_to(Root.resolve()) and not FilePath.is_symlink(), f"resource escapes root: {Relative}")
	require(FilePath.is_file(), f"missing resource: {Relative}")
	return FilePath


def file_identity(Root: Path, Relative: str) -> dict:
	Data = safe_file(Root, Relative).read_bytes()
	return {
		"bytes": len(Data),
		"sha256": hashlib.sha256(Data).hexdigest(),
		"lfSha256": hashlib.sha256(Data.replace(b"\r\n", b"\n")).hexdigest(),
		"gitBlobSha1": hashlib.sha1(f"blob {len(Data)}\0".encode() + Data).hexdigest(),
	}


def review_paths(Lock: dict) -> list[str]:
	return sorted("skills/" + Name for Name in Lock["files"]
		if Name.endswith((".lean", ".template", ".sha256", ".gitkeep", ".mmd", ".mermaid", ".csv", ".tex")))


def manifest_members(Root: Path, Lock: dict) -> list[dict]:
	Prefix = "skills/manage-math-research-program/"
	Members = []
	Seen = set()
	for Line in safe_file(Root, MANIFEST_PATH).read_text(encoding="utf-8").splitlines():
		Match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", Line)
		require(Match is not None, "invalid MANIFEST.sha256 line")
		Digest, Relative = Match.groups()
		Name = Prefix + Relative
		require(Name not in Seen, f"duplicate manifest member: {Name}")
		Seen.add(Name)
		Identity = file_identity(Root, Name)
		require(Identity["lfSha256"] == Digest, f"manifest hash mismatch: {Name}")
		require(Lock["files"].get(Name.removeprefix("skills/")) == Digest, f"manifest/lock mismatch: {Name}")
		Members.append({"path": Name, "sha256": Digest})
	Expected = {"skills/" + Name for Name in Lock["files"]
		if Name.startswith("manage-math-research-program/") and "skills/" + Name != MANIFEST_PATH}
	require(Seen == Expected, "manifest does not cover every locked manage resource exactly once")
	require(Members == sorted(Members, key=lambda Item: Item["path"]), "manifest order drift")
	return Members


def refresh_identities(Root: Path, Review: dict) -> None:
	Package = read_json(Root / "package.json")
	Lock = read_json(Root / "upstream.lock.json")
	Review["packageVersion"] = Package["version"]
	Review["upstreamCommit"] = Lock["upstream_commit"]
	Review["upstreamLockSha256"] = file_identity(Root, "upstream.lock.json")["sha256"]
	for Item in Review["resources"]:
		Item["identity"] = file_identity(Root, Item["path"])
		Item["lockKey"] = Item["path"].removeprefix("skills/")
		Item["lockSha256"] = Lock["files"][Item["lockKey"]]
	for Item in Review["sourceBindings"]:
		Item["sha256"] = file_identity(Root, Item["path"])["sha256"]
	Review["manifestMembers"] = manifest_members(Root, Lock)


def check_archive(Root: Path, Package: dict, ArchivePath: Path) -> int:
	Expected = {"package/" + Name for Name in Package["files"] + ["package.json", "README.md", "LICENSE"]}
	with tarfile.open(ArchivePath, "r:gz") as Archive:
		Members = Archive.getmembers()
		require(len(Members) == len(Expected) and {Item.name for Item in Members} == Expected, "archive membership mismatch or duplicates")
		for Member in Members:
			require(Member.isfile(), f"non-regular archive resource: {Member.name}")
			Relative = Member.name.removeprefix("package/")
			require(Archive.extractfile(Member).read() == safe_file(Root, Relative).read_bytes(), f"archive/source mismatch: {Relative}")
	return len(Members)


def validate_review(Root: Path, ArchivePath: Path | None = None) -> dict:
	Root = Root.resolve()
	Package = read_json(Root / "package.json")
	Lock = read_json(Root / "upstream.lock.json")
	Review = read_json(Root / REVIEW_PATH)
	require(Review.get("schemaVersion") == 1, "unsupported resource review schema")
	require(Review.get("packageVersion") == Package["version"], "review/package version mismatch")
	require(Review.get("upstreamCommit") == Lock["upstream_commit"], "review/upstream commit mismatch")
	require(Review.get("upstreamLockSha256") == file_identity(Root, "upstream.lock.json")["sha256"], "resource lock changed since review")
	require(all(Name in Package["files"] for Name in REVIEW_METADATA), "review metadata must ship with the Bundle")
	Resources = Review["resources"]
	require([Item["path"] for Item in Resources] == review_paths(Lock), "resource review coverage mismatch or duplicates")
	Bindings = Review["sourceBindings"]
	BindingPaths = [Item["path"] for Item in Bindings]
	require(len(set(BindingPaths)) == len(BindingPaths), "duplicate source binding")
	for Item in Bindings:
		require(Item["sha256"] == file_identity(Root, Item["path"])["sha256"], f"consumer changed since review: {Item['path']}")
	UsedBindings = {"index.mjs"}
	for Item in Resources:
		Name = Item["path"]
		require(Item["identity"] == file_identity(Root, Name), f"resource changed since review: {Name}")
		Key = Name.removeprefix("skills/")
		require(Item["lockKey"] == Key and Item["lockSha256"] == Lock["files"][Key] == Item["identity"]["lfSha256"], f"resource/lock mismatch: {Name}")
		require(Name in Package["files"], f"reviewed resource is not distributed: {Name}")
		for Field in BOUNDARY_FIELDS:
			require(isinstance(Item.get(Field), str) and bool(Item[Field].strip()), f"missing {Field}: {Name}")
		for Reference in Item["references"]:
			UsedBindings.add(Reference["path"])
			Text = safe_file(Root, Reference["path"]).read_text(encoding="utf-8")
			require(Reference["anchor"] in Text, f"missing consumer anchor: {Reference['path']}")
		require(bool(Item.get("provenance")), f"missing provenance: {Name}")
		if(Item["provenance"]["kind"] == "parent-copy"):
			require(Item["provenance"]["gitBlobSha1"] == Item["identity"]["gitBlobSha1"], f"parent blob mismatch: {Name}")
	require(set(BindingPaths) == UsedBindings, "resource references/source binding coverage mismatch")
	Members = manifest_members(Root, Lock)
	require(Review["manifestMembers"] == Members, "reviewed manifest member mapping changed")
	Summary = {"status": "passed", "scope": "author_inventory_integrity", "resources": len(Resources), "manifestMembers": len(Members), "lockedResources": len(Lock["files"])}
	if(ArchivePath is not None):
		Summary["archiveMembers"] = check_archive(Root, Package, ArchivePath)
	return Summary


def main() -> int:
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--root", type=Path, default=ROOT)
	Parser.add_argument("--archive", type=Path)
	Parser.add_argument("--refresh", action="store_true", help="Rebind mechanical fields after manually reviewing changed source; never grants approval")
	Arguments = Parser.parse_args()
	if(Arguments.refresh):
		Review = read_json(Arguments.root / REVIEW_PATH)
		refresh_identities(Arguments.root, Review)
		(Arguments.root / REVIEW_PATH).write_text(json.dumps(Review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
		print("RESOURCE_IDENTITIES_UPDATED: review explanations before publication")
		return 0
	print(json.dumps(validate_review(Arguments.root, Arguments.archive), sort_keys=True))
	return 0


if(__name__ == "__main__"):
	raise SystemExit(main())
