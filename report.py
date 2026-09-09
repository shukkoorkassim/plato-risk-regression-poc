"""
report.py — one combined, demo-friendly console report for BOTH flows.

Shows the whole Phase-1 story in a single run: data-quality check, ranking
(with the reopened factor), selection + efficiency, the agent's reasoning,
execution, and a self-heal / governance summary. Self-heal actions that only
happen in a live run (PR for a test fix, filing a defect) are shown as clearly
labelled placeholders — run `python run_poc.py --demo` to see them live.

    python report.py
    python run_poc.py --report
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.common import STATE, TESTS, run_pytest, C, efficiency_line   # noqa: E402
from agent.data_quality import check_data_quality                       # noqa: E402
from agent import approvals                                             # noqa: E402
from agent import flow1_defect_history as f1                            # noqa: E402
from agent import flow2_change_driven as f2                             # noqa: E402

BAR = "=" * 70
F1_THRESHOLD = 4.0
F2_THRESHOLD = 4.0


def _suite():
    p = TESTS / "test_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _tier(score):
    return "HIGH" if score >= 8 else "MED" if score >= 3 else "LOW"


def _reopen_counts():
    f = STATE / "defects.json"
    if not f.exists():
        return {}
    c = {}
    for d in json.loads(f.read_text()):
        if d.get("reopened"):
            c[d["component"]] = c.get(d["component"], 0) + 1
    return c


def _pytest_counts(selected):
    if not selected:
        return 0, 0
    out = run_pytest(" ".join(selected))
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else 0
    return passed, failed


def _section(title, tag=""):
    t = f"{title}   {C.GREY}{tag}{C.RESET}" if tag else title
    print(f"\n{C.CYAN}{BAR}\n {t}\n{BAR}{C.RESET}")


def _flow_block(title, subtitle, formula, ranked, score_key, threshold, reopen, kind):
    suite = _suite()
    selected = json.loads((STATE / "selected.json").read_text())
    sel_components = {suite[t] for t in selected}

    print(f"\n{C.MAGENTA}{BAR}\n {title}\n {C.GREY}{subtitle}{C.RESET}\n{C.MAGENTA}{BAR}{C.RESET}")
    print(f"{C.GREY} score {formula}{C.RESET}\n")

    print(f"{C.BOLD} RANKED{C.RESET}")
    for row in ranked:
        comp = row["component"]; score = row[score_key]
        run = comp in sel_components
        mark = f"{C.GREEN}▶ run {C.RESET}" if run else f"{C.GREY}– skip{C.RESET}"
        tier = _tier(score)
        tcol = {"HIGH": C.RED, "MED": C.YELLOW, "LOW": C.GREY}[tier]
        rtag = ""
        if reopen.get(comp):
            rtag = f"  {C.GREEN}reopen{reopen[comp]}{C.RESET}"
        print(f"   {comp:11} {score:6.1f}  {tcol}{tier:4}{C.RESET}  {mark}{rtag}")

    filtered = sorted(t for t in suite if t not in selected)
    avoided = len(suite) - len(selected)
    pct = round(avoided / len(suite) * 100) if suite else 0
    print(f"\n{C.BOLD} SELECTED{C.RESET}  ({len(selected)} of {len(suite)} tests, threshold >= {threshold})   "
          f"{C.GREEN}· EFFICIENCY: avoided {avoided} ({pct}% of the suite skipped){C.RESET}:")
    for t in sorted(selected):
        print(f"   {C.GREEN}RUN {C.RESET} {t:26} (covers {suite[t]})")

    # WHY — decision explanations
    print(f"\n{C.BOLD} WHY THESE{C.RESET}  (the agent's reasoning)")
    scores = {row["component"]: row[score_key] for row in ranked}
    for comp in sorted(sel_components):
        sc = scores.get(comp, 0)
        if kind == "risk":
            bits = "severe / recent / repeated defects"
            if reopen.get(comp):
                bits += f", {reopen[comp]} reopened (x1.6)"
            print(f"   {comp:11} risk {sc:.1f} >= {threshold}  — {bits}")
        else:
            print(f"   {comp:11} impact {sc:.1f} >= {threshold}  — features / fixes / requirements changed this release")

    print(f"\n{C.BOLD} FILTERED{C.RESET}  ({len(filtered)} skipped, each with a logged reason):")
    for t in filtered:
        print(f"   {C.GREY}skip {t:26} (covers {suite[t]}){C.RESET}")

    passed, failed = _pytest_counts(selected)
    total = passed + failed
    colour = C.GREEN if failed == 0 else C.RED
    print(f"\n{C.BOLD} EXECUTED{C.RESET}  {colour}{total} tests -> {passed} passed, {failed} failed{C.RESET}")
    return {"selected": sorted(selected), "components": sorted(sel_components),
            "passed": passed, "failed": failed}


def build():
    # read both signals first so the data-quality check sees everything
    f1.read_defect_sources()
    f2.read_release_delta()

    # ---- T5 · DATA QUALITY & COVERAGE ----
    _section(" DATA QUALITY & COVERAGE", "[T5]")
    print(check_data_quality()[1])

    # ---- FLOW 1 ----
    f1.score_risk(); f1.select_regression_tests()
    ranked1 = json.loads((STATE / "risk.json").read_text())
    b1 = _flow_block(
        "FLOW 1 · defect-history driven", "what has broken before?",
        "= severity × count × recency × (1 + churn)   ·   ×1.6 if reopened   [T1]",
        ranked1, "risk", F1_THRESHOLD, _reopen_counts(), "risk")

    # ---- FLOW 2 ----
    f2.score_impact(); f2.select_change_tests()
    ranked2 = json.loads((STATE / "impact.json").read_text())
    b2 = _flow_block(
        "FLOW 2 · change driven", "what just changed?",
        "= (2·features + 2·fixes + 3·requirements) × (1 + churn)",
        ranked2, "impact", F2_THRESHOLD, {}, "impact")

    # ---- COMPARISON ----
    s1, s2 = set(b1["components"]), set(b2["components"])
    union = sorted(s1 | s2)
    suite_n = len(_suite())
    print(f"\n{C.CYAN}{BAR}\n COMPARISON — same agent, two signals\n{BAR}{C.RESET}")
    print(f"   Flow 1 selected {len(b1['selected'])}: {', '.join(b1['components'])}")
    print(f"   Flow 2 selected {len(b2['selected'])}: {', '.join(b2['components'])}")
    print(f"   {C.GREY}shared:{C.RESET}       {', '.join(sorted(s1 & s2)) or '(none)'}")
    print(f"   {C.GREY}only Flow 1:{C.RESET}  {', '.join(sorted(s1 - s2)) or '(none)'}")
    print(f"   {C.GREY}only Flow 2:{C.RESET}  {', '.join(sorted(s2 - s1)) or '(none)'}")
    ru = len(union); av = suite_n - ru
    print(f"   {C.GREEN}Combined union: run {ru} of {suite_n} · avoided {av} ({round(av/suite_n*100) if suite_n else 0}% skipped)   [T2]{C.RESET}")

    # ---- SELF-HEAL & GOVERNANCE (live-only steps shown as placeholders) ----
    _section(" SELF-HEAL & GOVERNANCE", "(runs live in  python run_poc.py --demo)")
    print(f"   {C.BOLD}Approval gates [T6]{C.RESET} — a human signs off at each:")
    for name, label in approvals.GATES.items():
        print(f"     {C.YELLOW}□{C.RESET} {label}")
    print(f"\n   {C.BOLD}Self-heal [T3/T7]{C.RESET}")
    print(f"     {C.GREY}[live]{C.RESET} TEST-SCRIPT issue  →  fix the stale test  →  {C.CYAN}OPEN A PR for QA review{C.RESET}  {C.GREY}(placeholder here){C.RESET}")
    print(f"     {C.GREY}[live]{C.RESET} APPLICATION issue  →  {C.YELLOW}file a Jira defect{C.RESET} (assigned to the developer)")
    print(f"\n   {C.BOLD}Evaluation harness [T4]{C.RESET}")
    print(f"     run  {C.CYAN}python run_poc.py --eval{C.RESET}  — expected-vs-actual selection, re-run to catch drift")

    print(f"\n{C.GREY} Efficiency totals — Flow 1 executed {b1['passed']+b1['failed']} tests, "
          f"Flow 2 {b2['passed']+b2['failed']}. Failures = planted bugs the agent self-heals.{C.RESET}")
    print(BAR)


if __name__ == "__main__":
    build()
