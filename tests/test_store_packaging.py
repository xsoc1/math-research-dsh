#!/usr/bin/env python3
"""Lock the published Bundle surface without excluding research resources."""

import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dsh_sync_packaging", ROOT / "scripts/sync-from-parent.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)
PROFILE_SPEC = importlib.util.spec_from_file_location("dsh_profile_packaging", ROOT / "tests/test_store_disposable_profile.py")
PROFILE = importlib.util.module_from_spec(PROFILE_SPEC)
PROFILE_SPEC.loader.exec_module(PROFILE)


class StorePackaging(unittest.TestCase):
	def test_manifest_uses_exact_locked_resources(self):
		Package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
		Lock = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))
		Expected = ["index.mjs", "cordis.patch.yml", "README_EN.md", "docs/dsh-store-contract.md"]
		Expected.extend("skills/" + Name for Name in sorted(Lock["files"]))
		self.assertEqual(Package["files"], Expected, "Ambiguous selectors force STORE to scan checkout-only tools and tests")
		for Name in Package["files"]:
			self.assertTrue((ROOT / Name).is_file(), Name)

	def test_invalid_lock_cannot_expand_the_package_surface(self):
		for Name in ["../private.json", "/private.json", "a\\private.json", "a/*.py", "a/../private.json", "a/__pycache__/x.pyc", "a/x.pyo"]:
			with self.subTest(path=Name), self.assertRaises(ValueError):
				SYNC.bundle_files({"files": {Name: "a" * 64}})

	def test_files_generation_keeps_templates_and_commands_visible(self):
		Names = ["lean-verify/assets/proof.lean.template", "manage-math-research-program/scripts/sync_remotes.py"]
		Files = SYNC.bundle_files({"files": {Name: "a" * 64 for Name in Names}})
		self.assertTrue(all("skills/" + Name in Files for Name in Names))
		self.assertFalse(any("!" in Name or "*" in Name for Name in Files))

	def test_archive_checks_resources_membership_and_duplicates(self):
		Package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
		Names = Package["files"] + ["package.json", "README.md", "LICENSE"]
		for Failure in [None, "resource-changed", "extra-file", "duplicate-file"]:
			with self.subTest(failure=Failure), tempfile.TemporaryDirectory() as Directory:
				ArchivePath = Path(Directory) / "bundle.tgz"
				with tarfile.open(ArchivePath, "w:gz") as Archive:
					Members = [(Name, (ROOT / Name).read_bytes()) for Name in Names]
					if(Failure == "resource-changed"):
						Members = [(Name, Data + b"changed\n" if Name.endswith("lean-verify/SKILL.md") else Data) for Name, Data in Members]
					elif(Failure == "extra-file"):
						Members.append(("tests/development.py", b"development fixture\n"))
					elif(Failure == "duplicate-file"):
						Members.append(("index.mjs", (ROOT / "index.mjs").read_bytes()))
					for Name, Data in Members:
						Info = tarfile.TarInfo("package/" + Name)
						Info.size = len(Data)
						Archive.addfile(Info, io.BytesIO(Data))
				if(Failure is None):
					PROFILE.assert_clean_package(ArchivePath)
				else:
					with self.assertRaises(RuntimeError):
						PROFILE.assert_clean_package(ArchivePath)


if(__name__ == "__main__"):
	unittest.main()
