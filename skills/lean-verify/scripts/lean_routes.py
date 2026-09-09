#!/usr/bin/env python3
"""Calculate AND/OR route readiness; only actual root evidence can close a goal."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from lean_runtime import sha256_file
from lean_evidence import recheck_manifest


def evaluate_routes(Graph, Root, RootManifest=None):
	if(not isinstance(Graph, dict) or not isinstance(Graph.get("nodes"), list)):
		raise ValueError("a route graph requires a nodes array")
	for Node in Graph["nodes"]:
		if(not isinstance(Node.get("id"), str) or not Node["id"] or not isinstance(Node.get("semantic_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", Node["semantic_sha256"])):
			raise ValueError("each node needs an ID and a nonempty SHA-256 statement identity")
	Nodes = {Node["id"]: Node for Node in Graph["nodes"]}
	if(len(Nodes) != len(Graph["nodes"]) or Root not in Nodes):
		raise ValueError("unique node IDs and an existing root are required")
	Ready = set()
	Selected = {}
	Rejected = {}
	for Name, Node in Nodes.items():
		Evidence = Node.get("evidence")
		if(Evidence):
			try:
				FilePath = Path(Evidence["manifest"])
				Check = recheck_manifest(FilePath)
				Bound = sha256_file(FilePath) == Evidence["sha256"] and Check.get("semantic_sha256") == Node["semantic_sha256"]
				if(Bound and Check["exact_root_passed"] is True):
					Ready.add(Name)
					Selected[Name] = "checked_evidence"
				else:
					Rejected[Name] = "evidence does not close this statement version"
			except (OSError, ValueError, KeyError, TypeError):
				Rejected[Name] = "unavailable or invalid evidence"
	# Least fixed point: a cycle cannot create a proof; an alternative ready route can break it.
	Changed = True
	while(Changed):
		Changed = False
		for Name, Node in Nodes.items():
			if(Name in Ready):
				continue
			for Route in Node.get("routes", []):
				Dependencies = Route.get("dependencies", [])
				if(not isinstance(Dependencies, list) or not Dependencies or not Route.get("id") or Route.get("statement_sha256") != Node["semantic_sha256"]):
					continue
				if(all(Dependency in Ready for Dependency in Dependencies)):
					Ready.add(Name)
					Selected[Name] = Route["id"]
					Changed = True
					break
	Result = {"root": Root, "status": "ready_to_materialize" if Root in Ready else "open", "ready_nodes": sorted(Ready), "open_nodes": sorted(set(Nodes) - Ready), "selected_routes": Selected, "rejected_evidence": Rejected, "exact_root_passed": False, "scope": "route readiness; route records are not Lean proof terms"}
	if(RootManifest):
		Check = recheck_manifest(RootManifest)
		Closed = Check["exact_root_passed"] is True and Check.get("semantic_sha256") == Nodes[Root].get("semantic_sha256")
		Result.update(status="closed" if Closed else "root_check_incomplete", exact_root_passed=Closed, root_evidence_check=Check, scope="saved root evidence rechecked against current inputs; no new Lean replay")
	return Result


def main():
	Parser = argparse.ArgumentParser(description=__doc__)
	Parser.add_argument("--graph", required=True)
	Parser.add_argument("--root", required=True)
	Parser.add_argument("--root-manifest")
	Arguments = Parser.parse_args()
	try:
		Result = evaluate_routes(json.loads(Path(Arguments.graph).read_text(encoding="utf-8")), Arguments.root, Arguments.root_manifest)
	except (OSError, ValueError, KeyError, TypeError, AttributeError) as Failure:
		print(json.dumps({"status": "invalid", "exact_root_passed": False, "reason": str(Failure)}))
		return 2
	print(json.dumps(Result, ensure_ascii=False, indent="\t"))
	return 0


if(__name__ == "__main__"):
	sys.exit(main())
