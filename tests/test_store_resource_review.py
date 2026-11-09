#!/usr/bin/env python3
"""Exercise omissions, resource/consumer changes, and archive substitutions."""

import importlib.util
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dsh_resource_review", ROOT / "scripts/dsh-resource-review.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class ResourceReview(unittest.TestCase):
	def setUp(self):
		self.Temporary = tempfile.TemporaryDirectory()
		self.addCleanup(self.Temporary.cleanup)
		self.Root = Path(self.Temporary.name)
		Inventory = REVIEW.read_json(ROOT / REVIEW.REVIEW_PATH)
		Lock = REVIEW.read_json(ROOT / "upstream.lock.json")
		Package = REVIEW.read_json(ROOT / "package.json")
		Paths = set(Package["files"] + ["package.json", "LICENSE", "README.md"])
		Paths.update("skills/" + Name for Name in Lock["files"])
		Paths.update(Item["path"] for Item in Inventory["sourceBindings"])
		for Name in Paths:
			Target = self.Root / Name
			Target.parent.mkdir(parents=True, exist_ok=True)
			shutil.copyfile(ROOT / Name, Target)

	def write_inventory(self, Inventory):
		(self.Root / REVIEW.REVIEW_PATH).write_text(json.dumps(Inventory, ensure_ascii=False) + "\n", encoding="utf-8")

	def test_current_inventory_covers_every_requested_resource(self):
		Result = REVIEW.validate_review(self.Root)
		self.assertEqual(Result["resources"], 9)
		Inventory = REVIEW.read_json(self.Root / REVIEW.REVIEW_PATH)
		Paths = {Item["path"] for Item in Inventory["resources"]}
		Prefix = "skills/manage-math-research-program/assets/"
		for Name in ("blueprint-accepted-knowledge/evidence_inventory.csv",
			"paper-analysis.template.tex", "proof-paper.template.tex"):
			self.assertIn(Prefix + Name, Paths)
		self.assertEqual(Result["lockedResources"], 140)
		self.assertGreater(Result["manifestMembers"], 0)

	def test_missing_or_duplicate_resource_is_rejected(self):
		Original = REVIEW.read_json(self.Root / REVIEW.REVIEW_PATH)
		for Failure in ("missing", "duplicate"):
			with self.subTest(failure=Failure):
				Inventory = json.loads(json.dumps(Original))
				if(Failure == "missing"):
					Inventory["resources"].pop()
				else:
					Inventory["resources"].append(Inventory["resources"][-1])
				self.write_inventory(Inventory)
				with self.assertRaisesRegex(ValueError, "coverage mismatch"):
					REVIEW.validate_review(self.Root)

	def test_resource_and_consumer_drift_are_rejected(self):
		Paths = ["skills/lean-verify/scripts/LeanVerifyProbe.lean.template", "skills/lean-verify/scripts/verify_lean_project.py"]
		for Name in Paths:
			with self.subTest(path=Name):
				FilePath = self.Root / Name
				Original = FilePath.read_bytes()
				FilePath.write_bytes(Original + b"changed\n")
				with self.assertRaisesRegex(ValueError, "changed since review"):
					REVIEW.validate_review(self.Root)
				FilePath.write_bytes(Original)

	def test_manifest_member_mapping_and_unsafe_paths_are_rejected(self):
		Inventory = REVIEW.read_json(self.Root / REVIEW.REVIEW_PATH)
		Inventory["manifestMembers"].pop()
		self.write_inventory(Inventory)
		with self.assertRaisesRegex(ValueError, "member mapping changed"):
			REVIEW.validate_review(self.Root)
		for Name in ("../private.json", "/private.json", "C:/private.json", "a\\private.json", "a/../private.json"):
			with self.subTest(path=Name), self.assertRaises(ValueError):
				REVIEW.safe_file(self.Root, Name)

	def test_new_matching_resource_requires_a_review_record(self):
		OriginalLock = REVIEW.read_json(self.Root / "upstream.lock.json")
		Inventory = REVIEW.read_json(self.Root / REVIEW.REVIEW_PATH)
		for Suffix in (".lean", ".csv", ".tex"):
			with self.subTest(suffix=Suffix):
				Lock = {**OriginalLock, "files": {**OriginalLock["files"], f"lean-verify/assets/new{Suffix}": "a" * 64}}
				(self.Root / "upstream.lock.json").write_text(json.dumps(Lock), encoding="utf-8")
				Inventory["upstreamLockSha256"] = REVIEW.file_identity(self.Root, "upstream.lock.json")["sha256"]
				self.write_inventory(Inventory)
				with self.assertRaisesRegex(ValueError, "coverage mismatch"):
					REVIEW.validate_review(self.Root)

	def test_archive_cannot_substitute_a_reviewed_resource(self):
		Package = REVIEW.read_json(self.Root / "package.json")
		Names = Package["files"] + ["package.json", "README.md", "LICENSE"]
		for Failure in (None, "changed", "duplicate", "symlink"):
			with self.subTest(failure=Failure):
				ArchivePath = self.Root / "candidate.tgz"
				with tarfile.open(ArchivePath, "w:gz") as Archive:
					for Name in Names + ([Names[0]] if Failure == "duplicate" else []):
						Data = (self.Root / Name).read_bytes()
						if(Failure == "changed" and Name == REVIEW.REVIEW_PATH):
							Data += b"changed\n"
						Info = tarfile.TarInfo("package/" + Name)
						Info.size = len(Data)
						if(Failure == "symlink" and Name == REVIEW.REVIEW_PATH):
							Info.type = tarfile.SYMTYPE
							Info.linkname = "other.json"
							Archive.addfile(Info)
						else:
							Archive.addfile(Info, io.BytesIO(Data))
				if(Failure is None):
					self.assertEqual(REVIEW.validate_review(self.Root, ArchivePath)["archiveMembers"], len(Names))
				else:
					with self.assertRaises(ValueError):
						REVIEW.validate_review(self.Root, ArchivePath)


if(__name__ == "__main__"):
	unittest.main()
