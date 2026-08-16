/-
SCAFFOLD: <result-slug> <status> <open-obligations>
This file is a formalization scaffold for a new/partial result.
It is NOT a verified artifact. Unfinished proof blocks are marked with `sorry`.
Do not report this file as FORMALLY_VERIFIED until a full lean-verify pass
removes every `sorry` and records a clean machine verdict.
-/
import Mathlib

/-!
# <Result title>

Informal source: <source path / run id>
Status: <RIGOROUS_PARTIAL_RESULT | CANDIDATE_COMPLETE_PROOF | ...>
Open obligations: <O1, O2, ...>
-/

namespace <Namespace>

/-- <Statement of the new result> -/
theorem <result_name> <binder> : <statement> := by
  -- TODO: proof
  sorry

/-- <Open obligation 1> -/
lemma <obligation_1> <binder> : <statement> := by
  -- TODO: proof
  sorry

end <Namespace>
