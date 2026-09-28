"""agent/coverage_gap.py — flag risk areas that have no test (Phase 2 · item 11).

The data-quality check (T5) answers "is the mapping well-formed?". This answers
the sharper question: "where is the risk that nothing tests?"

Three kinds of gap, worst first:

  UNCOVERED   a component carrying real risk/impact with no mapped test at all.
              Nothing would catch a regression here.
  THIN        a high-risk component covered by a single test file. One test file
              for the riskiest area of the product is thin cover.

Run:  python run_poc.py --coverage
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

from .common import TESTS, STATE, ROOT, C, THRESHOLD

HIGH = THRESHOLD    # the same cut-off the selectors use (agent/common.py)


def _suite():
    p = TESTS / "test_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _scores():
    """Merge the two signals into one per-component view."""
    out = defaultdict(lambda: {"risk": 0.0, "impact": 0.0})
    rf, imf = STATE / "risk.json", STATE / "impact.json"
    if rf.exists():
        for r in json.loads(rf.read_text()):
            out[r["component"]]["risk"] = r["risk"]
    if imf.exists():
        for r in json.loads(imf.read_text()):
            out[r["component"]]["impact"] = r["impact"]
    return out


def coverage_report():
    """Return (ok, text). ok is False when any component carries risk without cover.

    Product components only. The benchmark project's seeded-defect evidence used
    to appear here; two codebases in one gap report is the fastest way to leave
    an audience believing the holes are in their own checkout.
    """
    suite = _suite()
    covered = defaultdict(list)
    for test, comp in suite.items():
        covered[comp].append(test)
    scores = _scores()

    # Only the PRODUCT's own components belong in the gap tables. The benchmark
    # runs against networkx, a separate codebase with its own module names
    # (classes.graph, linalg.laplacianmatrix); folding those in here would
    # report them as untested areas of the product, which they are not. Its
    # undetected defects go below, in their own clearly-labelled section.
    known = set(scores) | set(covered)
    uncovered, thin, ok_rows = [], [], []
    for comp in known:
        s = scores.get(comp, {"risk": 0.0, "impact": 0.0})
        worst = max(s["risk"], s["impact"])
        tests = covered.get(comp, [])
        if not tests:
            uncovered.append((comp, worst, s))
        elif worst >= HIGH and len(tests) < 2:
            thin.append((comp, worst, s, tests))
        else:
            ok_rows.append((comp, worst, s, tests))

    uncovered.sort(key=lambda x: -x[1])
    thin.sort(key=lambda x: -x[1])
    ok_rows.sort(key=lambda x: -x[1])

    L = [f"{C.BOLD}Coverage-gap report{C.RESET}  {C.GREY}risk areas with no test, worst first  [T11]{C.RESET}", ""]

    if uncovered:
        L.append(f"  {C.RED}{C.BOLD}UNCOVERED{C.RESET} {C.GREY}— carries risk, nothing tests it{C.RESET}")
        for comp, worst, s in uncovered:
            sev = C.RED if worst >= HIGH else C.YELLOW if worst > 0 else C.GREY
            L.append(f"    {sev}x{C.RESET} {comp:12} flow1 {s['risk']:5.1f}  flow2 {s['impact']:5.1f}"
                     f"   {C.GREY}no test mapped{C.RESET}")
    if thin:
        L.append("")
        L.append(f"  {C.YELLOW}{C.BOLD}THIN{C.RESET} {C.GREY}— high risk, only one test file{C.RESET}")
        for comp, worst, s, tests in thin:
            L.append(f"    {C.YELLOW}!{C.RESET} {comp:12} flow1 {s['risk']:5.1f}  flow2 {s['impact']:5.1f}"
                     f"   {C.GREY}{tests[0]}{C.RESET}")
    if ok_rows:
        L.append("")
        L.append(f"  {C.GREEN}{C.BOLD}COVERED{C.RESET}")
        for comp, worst, s, tests in ok_rows:
            L.append(f"    {C.GREEN}+{C.RESET} {comp:12} flow1 {s['risk']:5.1f}  flow2 {s['impact']:5.1f}"
                     f"   {C.GREY}{len(tests)} test file(s){C.RESET}")

    gaps = len(uncovered) + len(thin)
    L.append("")
    if gaps:
        L.append(f"  {C.BOLD}{gaps} gap(s) to close{C.RESET} — "
                 f"{len(uncovered)} uncovered, {len(thin)} thin.")
    else:
        L.append(f"  {C.GREEN}No coverage gaps: every component carrying risk has a test.{C.RESET}")
    return not gaps, "\n".join(L)
