#!/usr/bin/env python3
"""Isolated replay of frozen Q9 evidence; no new solver or accepted-graph update."""

import argparse
import ast
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = next((Parent for Parent in Path(__file__).resolve().parents if (Parent / "benchmarks/codex-20260908-q9/evidence").is_dir()), None)
sys.path.insert(0, str(SCRIPT_ROOT))
import research_experience as experience
import research_library as library


def reuse_in_new_process(Project, Problem):
	"""A deterministic consumer: retrieve a program and check its recorded box."""
	Query = library.query_tools(Project, Problem["query"], limit=50)
	Hits = [Hit for Hit in Query["hits"] if Hit["kind"] == "program"]
	if(len(Hits) != 1):
		raise ValueError("expected the single exact certificate resource from retrieval")
	Hit = Hits[0]
	Front, _, _ = library.read_metadata(library.inside(Project, Hit["location"]).read_bytes())
	Contract = Front["reuse_contract"]
	Reasons = []
	for Variable in ("c", "t"):
		Lower, Upper = map(Fraction, Contract[Variable])
		Start, End = map(Fraction, Problem[Variable])
		if(not Lower <= Start <= End <= Upper):
			Reasons.append(Variable + " interval is outside the recorded polynomial box")
	if(Reasons):
		return dict(verdict="NOT_COVERED", reasons=Reasons, pointer=Hit["location"], mathematical_counterexample=False)
	Program = next(Reference for Reference in Hit["resources"] if Reference.get("kind") == "program")
	if(Program["binding_state"] != "CURRENT"):
		raise ValueError("the retrieved program version changed")
	PathValue = library.inside(Project, Program["path"])
	Spec = importlib.util.spec_from_file_location("frozen_q9_polynomial", PathValue)
	Module = importlib.util.module_from_spec(Spec)
	Spec.loader.exec_module(Module)
	C0, C1 = map(Fraction, Problem["c"])
	T0, T1 = map(Fraction, Problem["t"])
	Polynomial = Module.polys[Problem["polynomial"]]
	Coefficients = Polynomial.compose(C0 + (C1 - C0) * Module.c, T0 + (T1 - T0) * Module.t).bern()
	Minimum = min(Value for Row in Coefficients for Value in Row)
	assert Minimum > 0
	return dict(verdict="SCOPED_POLYNOMIAL_REUSE_PASS", pointer=Hit["location"], program=Program["path"],
		program_sha256=Program["sha256"], polynomial=Problem["polynomial"], c=Problem["c"], t=Problem["t"],
		coefficient_count=sum(len(Row) for Row in Coefficients), minimum=str(Minimum),
		new_mathematical_discovery=False, claims_full_q9_formalization=False)


def run_replay(Output, LegacyProject=None):
	if(REPO_ROOT is None):
		raise ValueError("frozen Q9 evidence is absent; run this optional replay from the source repository")
	Output = Path(Output).resolve()
	Output.mkdir(parents=True, exist_ok=False)
	Project = Output / "project"
	Project.mkdir()
	Started = time.perf_counter()
	Bindings = dict()
	def copy_input(PathValue, Destination):
		Raw = PathValue.read_bytes()
		Bindings[str(PathValue)] = library.digest(Raw)
		Destination.parent.mkdir(parents=True, exist_ok=True)
		Destination.write_bytes(Raw)
		return Raw
	LegacyCount, LegacyRows = 0, []
	if(LegacyProject is not None):
		LegacyProject = Path(LegacyProject).resolve()
		for PathValue in sorted((LegacyProject / "tools").rglob("*.md")):
			copy_input(PathValue, Project / PathValue.relative_to(LegacyProject))
			LegacyCount += PathValue.name.lower() != "readme.md"
		OldIndex = LegacyProject / "index/tools.json"
		copy_input(OldIndex, Project / "index/tools.json")
		LegacyRows = library.read_json(OldIndex)["items"]
		for PathValue in sorted((LegacyProject / "research/library/annotations").glob("*.json")):
			copy_input(PathValue, Project / PathValue.relative_to(LegacyProject))
	else:
		(Project / "tools").mkdir()
		(Project / "tools/README.md").write_bytes(b"# Human research notes\nKeep this project context.\n")
	InitialIndex = library.make_index(Project, ["tools"], ReadmePath="tools/README.md")
	Index = library.read_json(Project / "index/tools.json")
	for Old in LegacyRows:
		New = next(Row for Row in Index["items"] if Row["location"] == Old["location"])
		for Key, Value in Old.items():
			if(Key not in ("title", "summary", "kind", "aliases", "applicability", "lifecycle")):
				assert New[Key] == Value, (Old["location"], Key)
	Campaign = REPO_ROOT / "benchmarks/codex-20260908-q9"
	Commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
	Routes, Captures = [], []
	Scope = ["Only the stated Q9 implication Q_quad > 0 => R_quad > 0.", "m > 1; 2/3 < c < 1; 0 < r < c^2; 0 < g < B < pi/2.",
		"s=sqrt(r), A=arcsin(s sin(B)), d=arcsin(s sin(g)); principal acute branches.",
		"C2: H(d)+H(g)/c=pi/2; C3: B-g=c(A+d); H(z)=arctan(m tan(z))."]
	Conclusions = dict(A="Q>0 gives sqrt(r)<12/25, then S>0 and R_quad>0 on the stated Q9 domain.",
		B="Q>0 gives r<c^2/4, then S>0 and R_quad>0 on the stated Q9 domain.",
		C="Q>0 gives r<1/9; the small-r estimate gives R_quad>0 on the stated Q9 domain.")
	FrozenChecked = 0
	for Arm in ("A", "B", "C"):
		Folder = Campaign / "evidence" / ("q9-" + Arm + "-solver")
		Frozen = library.read_json(Folder / "frozen-hashes.json")
		Source = Folder / "artifacts/answer.md"
		Raw = copy_input(Source, Project / ("evidence/q9-" + Arm + "/answer.md"))
		assert library.digest(Raw) == Frozen["answer.md"]
		FrozenChecked += 1
		Relative = Source.relative_to(REPO_ROOT).as_posix()
		Committed = subprocess.run(["git", "show", Commit + ":" + Relative], cwd=REPO_ROOT, capture_output=True, check=True).stdout
		assert Committed == Raw
		Captured = library.capture_source(Project, Project / ("evidence/q9-" + Arm + "/answer.md"),
			"https://github.com/xsoc1/rigorous-open-math-research/blob/" + Commit + "/" + Relative,
			"git:" + Commit, "Frozen Q9 " + Arm + " proof", method="original-markdown", SourceKind="primary",
			Coverage="full frozen answer", Locators=["Opening claim and explicitly numbered proof sections"])
		Captures.append(Captured["source_id"])
		Offset, Pieces = 0, []
		while(Offset is not None):
			Read = library.read_source(Project, Captured["source_id"], StartOffset=Offset)
			Pieces.append(Read["content"])
			Offset = Read["next_offset"]
		assert "".join(Pieces).encode("utf-8") == Raw
		Route = experience.record_experience(Project, dict(tool_id="q9-frozen-" + Arm, title="Frozen Q9 route " + Arm,
			question="Reuse experience from an already solved Q9 benchmark.", outcome="success", scope=Scope,
			conclusion=Conclusions[Arm], transformations=["Preserve exact angular information before a rational polynomial certificate."],
			not_applicable_to=["C1 is unused only for this specified Q9 conclusion; this does not remove C1 from the whole KP-DET problem.",
				"No new discovery, Lean formalization, or main canonical integration is claimed."],
			evidence_status="FROZEN_BENCHMARK_PROOF_REPLAY", evidence=[dict(path="evidence/q9-" + Arm + "/answer.md", locator="Opening theorem, domain and proof")],
			sources=[dict(source_id=Captured["source_id"], locator="Opening theorem and proof sections")]))
		Routes.append(Route["location"])
	MapPath = Campaign / "evidence/q9-B-solver/artifacts/research_map.md"
	copy_input(MapPath, Project / "evidence/q9-B/research_map.md")
	assert library.digest(MapPath.read_bytes()) == library.read_json(Campaign / "evidence/q9-B-solver/frozen-hashes.json")["research_map.md"]
	FrozenChecked += 1
	Failure = experience.record_experience(Project, dict(title="Q9 crude cotangent relaxation", outcome="failed", failure_kind="method_limit",
		question="Why did the crude relaxation leave a large-g gap?", scope=Scope, mechanism="Crude cotangent relaxations lost information and left large-g gaps.",
		transformations=["Preserve exact angular information before a rational polynomial certificate."],
		reconsider_when=["Use a sharper inequality retaining the C3 angular dependency."],
		not_applicable_to=["The failure concerns this relaxation, not the truth of Q9."],
		evidence=[dict(path="evidence/q9-B/research_map.md", locator="Failed/blocked routes")]))
	NoReturnSource = Campaign / "sources/route-11-q9-wave/reconciliation.md"
	copy_input(NoReturnSource, Project / "evidence/route11-reconciliation.md")
	NoReturn = experience.record_experience(Project, dict(title="Route11 no returned mathematical artifact", outcome="no_return",
		question="What returned from the recorded wave?", scope="Only the recorded Route11 W16/W17 dispatches.",
		mechanism="W16 cause unknown; W17 turn rejected at usage limit. No mathematical artifact returned.",
		reconsider_when=["A returned artifact or a separately authorized later attempt supplies mathematical evidence."],
		not_applicable_to=["NO_RETURN is not a mathematical counterexample or a refuted method."],
		evidence=[dict(path="evidence/route11-reconciliation.md", locator="W16/W17 observed outcomes")]))
	ProgramSource = Campaign / "evidence/q9-C-solver/artifacts/verify_certificate.py"
	ProgramBytes = copy_input(ProgramSource, Project / "evidence/q9-C/verify_certificate.py")
	CFrozen = library.read_json(Campaign / "evidence/q9-C-solver/frozen-hashes.json")
	assert library.digest(ProgramBytes) == CFrozen["verify_certificate.py"]
	FrozenChecked += 1
	for Name in ("N1", "Np1", "n2", "Npstar"):
		FileName = "root_cert_" + Name + ".json"
		Raw = copy_input(Campaign / "evidence/q9-C-solver/artifacts" / FileName, Project / "evidence/q9-C" / FileName)
		assert library.digest(Raw) == CFrozen[FileName]
		FrozenChecked += 1
	Program = library.save_card(Project, dict(tool_id="q9-exact-polynomial-program", title="Q9 exact Bernstein certificate program", kind="program",
		content="Reconstruct the four frozen Q9 polynomials with exact rational arithmetic and verify their Bernstein coefficients. This program verifies polynomial inequalities, not the full trigonometric argument.",
		conditions=["Polynomial box: c in [2/3,1], t in [1/3,1].", "Npstar is strictly positive on this box; the full Q9 theorem retains its separate C2/C3 and domain assumptions."],
		reuse_contract=dict(c=["2/3", "1"], t=["1/3", "1"]),
		resources=[dict(path="evidence/q9-C/verify_certificate.py", kind="program", locator="polys, P.compose, P.bern")],
		evidence=[dict(path="evidence/q9-C/answer.md", locator="Exact polynomial positivity certificate")]))
	Run = subprocess.run([sys.executable, str(Project / "evidence/q9-C/verify_certificate.py")], cwd=Project, capture_output=True, text=True, timeout=60)
	assert Run.returncode == 0, Run.stderr
	library.atomic_write(Output / "frozen-certificate-check.log", Run.stdout.encode("utf-8"))
	Spec = importlib.util.spec_from_file_location("q9_replayed_certificate", Project / "evidence/q9-C/verify_certificate.py")
	Module = importlib.util.module_from_spec(Spec)
	Spec.loader.exec_module(Module)
	CoefficientCount = 0
	for Name, Polynomial in Module.polys.items():
		Certificate = library.read_json(Project / "evidence/q9-C" / ("root_cert_" + Name + ".json"))
		assert {ast.literal_eval(Key): Fraction(Value) for Key, Value in Certificate["definition"].items()} == Polynomial.d
		Reconstructed = Polynomial.compose((2 + Module.c) * Fraction(1, 3), (1 + 2 * Module.t) * Fraction(1, 3)).bern()
		assert [[Fraction(Value) for Value in Row] for Row in Certificate["bernstein"]] == Reconstructed
		CoefficientCount += sum(len(Row) for Row in Reconstructed)
	assert CoefficientCount == 230
	library.make_index(Project)
	Note = library.annotate(Project, Failure["location"], author="q9-replay", kind="reconsideration", text="angular-recovery-cue: compare the successful exact sine-concavity step before reopening the failed relaxation.")
	assert library.query_tools(Project, "angular-recovery-cue")["hits"]
	NoteBytes = (library.library_root(Project) / "annotations" / (Note["annotation_id"] + ".json")).read_bytes()
	Changed = experience.record_experience(Project, dict(reconsider_when=["The frozen successful routes supply a sharper C3 comparison; test transfer on a distinct subdomain."]), Failure["location"], Failure["sha256"])
	library.make_index(Project)
	assert not library.query_tools(Project, "angular-recovery-cue")["hits"]
	Historical = library.query_tools(Project, "angular-recovery-cue", IncludeStale=True)["hits"][0]
	assert Historical["annotations"][0]["state"] == "STALE"
	assert (library.library_root(Project) / "annotations" / (Note["annotation_id"] + ".json")).read_bytes() == NoteBytes
	Comparison = experience.compare_routes(Project, Routes + [Changed["location"]], dict(
		explanation="Exact angular information may explain why the successful bounds close regions missed by the crude relaxation.",
		scope="Candidate explanation of these frozen Q9 routes only; no universal method claim.",
		prediction="On a separately chosen compact subrectangle, the exact polynomial certificate remains usable with its recorded domain.",
		test="Retrieve the certificate program in a fresh process, check box inclusion and recompute rational Bernstein coefficients; reject out-of-box reuse.",
		falsifier="A nonpositive exact coefficient would invalidate this sufficient certificate test, not itself disprove the underlying polynomial."))
	Page = Project / "research/understanding.md"
	Page.parent.mkdir(exist_ok=True)
	Human = b"# Project understanding\n\n## Human intuition\nCould the angular dependency explain the difference? This remains a question.\n"
	Page.write_bytes(Human)
	experience.update_understanding(Project, Routes + [Changed["location"], NoReturn["location"]], [Comparison["path"]])
	assert Page.read_bytes().startswith(Human)
	Problems = [dict(query="Q9 exact Bernstein certificate program", polynomial="Npstar", c=["3/4", "5/6"], t=["2/5", "3/5"]),
		dict(query="Q9 exact Bernstein certificate program", polynomial="Npstar", c=["1/2", "3/5"], t=["2/5", "3/5"])]
	Reuses = []
	for Number, Problem in enumerate(Problems):
		TaskPath = Output / ("reuse-problem-" + str(Number) + ".json")
		library.atomic_write(TaskPath, library.json_bytes(Problem))
		Run = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--reuse-child", str(Project), "--problem", str(TaskPath)], capture_output=True, text=True, timeout=60)
		assert Run.returncode == 0, Run.stderr
		Reuses.append(json.loads(Run.stdout))
	assert Reuses[0]["verdict"] == "SCOPED_POLYNOMIAL_REUSE_PASS"
	assert Reuses[1]["verdict"] == "NOT_COVERED"
	assert not Reuses[1]["mathematical_counterexample"]
	assert experience.read_route(Project, NoReturn["location"])["experience"]["failure_kind"] == "infrastructure"
	assert all(library.digest(Path(PathValue).read_bytes()) == Hash for PathValue, Hash in Bindings.items())
	Result = dict(verdict="PASS", kind="DETERMINISTIC_FROZEN_Q9_LIBRARY_REPLAY", elapsed_seconds=time.perf_counter() - Started,
		full_certificate_coefficient_count=CoefficientCount,
		legacy_cards=LegacyCount, legacy_index_rows_preserved=len(LegacyRows), initial_index=InitialIndex,
		frozen_bindings_checked=FrozenChecked, original_inputs_unchanged=len(Bindings), source_bindings=Bindings,
		captured_sources=Captures, route_cards=Routes, failure_card=Changed["location"], no_return_card=NoReturn["location"],
		program_card=Program["location"], comparison=Comparison["path"], understanding="research/understanding.md", reuses=Reuses,
		model_calls=0, new_discovery_claims=0, accepted_graph_modified=False,
		limits="Fresh processes are deterministic consumers, not a new agent study. This checks polynomial reuse, not the complete Q9 proof or Lean formalization.")
	library.atomic_write(Output / "results.json", library.json_bytes(Result))
	return Result


class Q9ReplayTests(unittest.TestCase):
	@unittest.skipUnless(REPO_ROOT, "optional frozen Q9 evidence is not bundled with installed plugins")
	def test_frozen_q9_source_and_program_reuse(self):
		with tempfile.TemporaryDirectory() as Folder:
			Result = run_replay(Path(Folder) / "replay")
			self.assertEqual(Result["verdict"], "PASS")
			self.assertEqual(Result["frozen_bindings_checked"], 9)
			self.assertEqual(Result["reuses"][0]["coefficient_count"], 130)


if(__name__ == "__main__"):
	if("--output" in sys.argv or "--reuse-child" in sys.argv):
		Parser = argparse.ArgumentParser(description=__doc__)
		Parser.add_argument("--output")
		Parser.add_argument("--legacy-project")
		Parser.add_argument("--reuse-child")
		Parser.add_argument("--problem")
		Args = Parser.parse_args()
		Result = reuse_in_new_process(Args.reuse_child, library.read_json(Path(Args.problem))) if Args.reuse_child else run_replay(Args.output, Args.legacy_project)
		print(json.dumps(Result, ensure_ascii=False))
	else:
		unittest.main()
