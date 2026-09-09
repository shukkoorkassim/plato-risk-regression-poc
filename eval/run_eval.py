"""eval/run_eval.py — fixed evaluation set (Phase 1 · T4).

Runs both flows deterministically and checks the selected tests against a known
expected set. Re-run this after ANY model, workflow, or data change to confirm
the agent still makes acceptable selections (guards against silent drift).

    python eval/run_eval.py           # or:  python run_poc.py --eval
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.common import STATE, C                       # noqa: E402
from agent import flow1_defect_history as f1            # noqa: E402
from agent import flow2_change_driven as f2             # noqa: E402

EXP = json.loads((Path(__file__).parent / "expected.json").read_text())


def _run_flow1():
    f1.read_defect_sources(); f1.score_risk(); f1.select_regression_tests(EXP["flow1"]["threshold"])
    return sorted(json.loads((STATE / "selected.json").read_text()))


def _run_flow2():
    f2.read_release_delta(); f2.score_impact(); f2.select_change_tests(EXP["flow2"]["threshold"])
    return sorted(json.loads((STATE / "selected.json").read_text()))


def _check(name, got, exp):
    exp = sorted(exp)
    ok = got == exp
    tag = f"{C.GREEN}PASS{C.RESET}" if ok else f"{C.RED}FAIL{C.RESET}"
    print(f"  {tag}  {name}")
    print(f"        got      {got}")
    if not ok:
        print(f"        expected {exp}")
    return ok


def main():
    print("Evaluation — expected vs actual test selection (re-run after any change):\n")
    a = _check("flow1 · defect history", _run_flow1(), EXP["flow1"]["selected"])
    b = _check("flow2 · release delta", _run_flow2(), EXP["flow2"]["selected"])
    ok = a and b
    print(f"\n  {(C.GREEN + 'ALL CHECKS PASSED' if ok else C.RED + 'SOME CHECKS FAILED — review the risk model / data')}{C.RESET}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
