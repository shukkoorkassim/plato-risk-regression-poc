"""
demo_selfheal.py — the FULL narrated POC in one run.

  SIGNAL 1 · defect history   read sources -> summarize -> rank risk -> select
  SIGNAL 2 · release delta     read delta   -> summarize -> rank impact -> select
  COMBINED                     the union of tests either signal flags
  SELF-HEAL (two paths)        run the subset, then for each failure:
        * TEST SCRIPT issue  -> the app is right, the test is stale -> FIX THE TEST
        * APPLICATION issue  -> the source is wrong -> LOG A DEFECT IN JIRA (real ticket)

The self-heal section is self-contained: it forces the two tested functions to a
known-clean state (whatever run_poc.py --reset left behind), plants exactly two
failures, heals them, then restores your files to how it found them.

By default it FILES A REAL Jira defect (needs ATLASSIAN_SITE/EMAIL/TOKEN — the same
creds JIRA_LIVE uses). Set REPORT_BUGS=0 to switch to a dry run (no ticket created).

    python demo_selfheal.py            # or:  python run_poc.py --demo
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.common import C, ROOT, TESTS                        # noqa: E402
from agent.jira_report import report_defect_to_jira            # noqa: E402
from agent.data_quality import check_data_quality              # noqa: E402
from agent.pr_flow import propose_test_fix                     # noqa: E402
from agent import approvals                                    # noqa: E402
from agent import flow1_defect_history as flow1                # noqa: E402
from agent import flow2_change_driven as flow2                 # noqa: E402

SRC = ROOT / "src" / "swaglabs.py"
TEST_SEARCH = ROOT / "tests" / "test_search.py"
STATE = ROOT / "._agent_state"
SEL = STATE / "selected.json"
BAR = "=" * 72

SPEC = {"checkout": {"tax": 2.40, "total": 32.39},
        "search": {"upper": ["sauce-labs-backpack"]}}


def head(n, title, color=C.MAGENTA):
    print(f"\n{color}{BAR}\n {n}  {title}\n{BAR}{C.RESET}")


def colorize(text):
    """Prettify the flows' plain text: RUN green, skip dim, risk tiers coloured."""
    out = []
    for ln in text.split("\n"):
        ln = (ln.replace("[HIGH]", f"{C.RED}[HIGH]{C.RESET}")
                .replace("[MED ]", f"{C.YELLOW}[MED ]{C.RESET}")
                .replace("[LOW ]", f"{C.GREY}[LOW ]{C.RESET}"))
        body = ln.lstrip()
        if body.startswith("RUN "):
            ln = ln.replace("RUN ", f"{C.GREEN}RUN{C.RESET} ", 1)
        elif body.startswith("skip "):
            ln = f"{C.GREY}{ln}{C.RESET}"
        out.append(ln)
    return "\n".join(out)


def step(fn, label):
    print(f"\n{C.CYAN}> {label}{C.RESET}")
    print(colorize(fn()))


def test_report(paths, title):
    """Run pytest and render a compact, fancy pass/fail report."""
    full = [str(ROOT / t) for t in paths.split()]
    proc = subprocess.run([sys.executable, "-m", "pytest", *full, "-q", "--tb=no"],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=180)
    out = proc.stdout + proc.stderr
    passed = int((re.search(r"(\d+) passed", out) or [0, 0])[1]) if re.search(r"(\d+) passed", out) else 0
    failed = int(re.search(r"(\d+) failed", out).group(1)) if re.search(r"(\d+) failed", out) else 0
    fails = [ln.split(" - ")[0].replace("FAILED ", "").strip()
             for ln in out.splitlines() if ln.startswith("FAILED")]
    total = passed + failed
    rule = "-" * 68
    R = [f"{C.GREY}{rule}{C.RESET}",
         f"  {C.BOLD}{title}{C.RESET}",
         f"  We ran {C.BOLD}{total}{C.RESET} tests   "
         f"{C.GREEN}PASS {passed:>2}{C.RESET}   "
         f"{(C.RED if failed else C.GREY)}FAIL {failed:>2}{C.RESET}"]
    if fails:
        R.append(f"{C.GREY}{rule}{C.RESET}")
        R.append(f"  {C.RED}Failed tests:{C.RESET}")
        for f in fails:
            R.append(f"    {C.RED}x{C.RESET} {f}")
    else:
        R.append(f"  {C.GREEN}All selected tests passed.{C.RESET}")
    R.append(f"{C.GREY}{rule}{C.RESET}")
    return "\n".join(R), passed, failed


def normalise_clean():
    src = SRC.read_text()
    src = re.sub(
        r"(def checkout_totals\(cart[^\n]*\n(?:.*?\n)*?    subtotal = cart\.subtotal\(\)\n)"
        r"\s*tax = [^\n]*\n\s*total = [^\n]*\n",
        "\\1    tax = round(subtotal * TAX_RATE, 2)\n    total = round(subtotal + tax, 2)\n",
        src, count=1)
    src = re.sub(
        r"(def process_payment\(cart[^\n]*\n(?:.*?\n)*?    discounted = apply_promo\(subtotal, promo\)\n)"
        r"\s*tax = [^\n]*\n\s*total = [^\n]*\n",
        "\\1    tax = round(discounted * TAX_RATE, 2)\n    total = round(discounted + tax, 2)\n",
        src, count=1)
    SRC.write_text(src)
    t = TEST_SEARCH.read_text()
    t = re.sub(
        r'def test_search_is_case_insensitive\(\):\n(?:    #[^\n]*\n)?\s*assert search_products\("BACKPACK"\) == [^\n]*\n',
        'def test_search_is_case_insensitive():\n    assert search_products("BACKPACK") == ["sauce-labs-backpack"]\n',
        t, count=1)
    TEST_SEARCH.write_text(t)


def plant_bugs():
    src = SRC.read_text().replace(
        "    tax = round(subtotal * TAX_RATE, 2)\n    total = round(subtotal + tax, 2)",
        "    tax = round(subtotal * TAX_RATE * 2, 2)   # BUG: tax rate applied twice\n"
        "    total = round(subtotal + tax, 2)", 1)
    SRC.write_text(src)
    t = TEST_SEARCH.read_text().replace(
        'def test_search_is_case_insensitive():\n    assert search_products("BACKPACK") == ["sauce-labs-backpack"]',
        'def test_search_is_case_insensitive():\n'
        '    # STALE TEST (written before REQ-413): still expects case-SENSITIVE search\n'
        '    assert search_products("BACKPACK") == []', 1)
    TEST_SEARCH.write_text(t)


def probe():
    code = (
        "import sys, json; sys.path.insert(0, 'src'); import swaglabs as s;"
        "c = s.Cart(); c.add('sauce-labs-backpack'); ct = s.checkout_totals(c);"
        "print(json.dumps({'checkout_tax': ct['tax'], 'checkout_total': ct['total'],"
        " 'search_upper': s.search_products('BACKPACK')}))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    STATE.mkdir(exist_ok=True)
    print(f"{C.BOLD}RISK-BASED REGRESSION · full self-healing demo{C.RESET}")

    head("1", "SIGNAL 1 · DEFECT HISTORY   (what has broken before?)")
    step(flow1.read_defect_sources, "read_defect_sources  — pull & normalise defects (Jira + CSV + git churn)")
    step(flow1.summarize_defects,   "summarize_defects    — group by component: what broke, and how badly")
    step(flow1.score_risk,          "score_risk           — rank: severity x recency (x1.6 if reopened) x (1 + churn)")
    step(flow1.select_regression_tests, "select_regression_tests — keep tests for high-risk components")
    set_a = json.loads(SEL.read_text())

    head("2", "SIGNAL 2 · RELEASE DELTA   (what just changed?)")
    step(flow2.read_release_delta, "read_release_delta   — pull this release's features, fixes, requirement changes + churn")
    step(flow2.summarize_changes,  "summarize_changes    — per change: what changed, which part, where from")
    step(flow2.score_impact,       "score_impact         — rank: impact = (2*feat + 2*fix + 3*req) x (1 + churn)")
    step(flow2.select_change_tests, "select_change_tests  — keep tests for the most-changed components")
    set_b = json.loads(SEL.read_text())

    head("3", "COMBINED SELECTION   (run what either signal flags)")
    union = sorted(set(set_a) | set(set_b))
    print(f"  Flow 1 (defect history) selected {len(set_a)}: {', '.join(set_a)}")
    print(f"  Flow 2 (release delta)  selected {len(set_b)}: {', '.join(set_b)}")
    print(f"  shared: {', '.join(sorted(set(set_a)&set(set_b))) or '(none)'}")
    print(f"  {C.BOLD}UNION to execute ({len(union)}): {', '.join(union)}{C.RESET}")
    suite = json.loads((TESTS / "test_map.json").read_text())
    total = len(suite); avoided = total - len(union)
    SEL.write_text(json.dumps(union))
    os.environ.setdefault("APPROVE_ALL", "1")   # demo auto-approves gates; set APPROVE_ALL=0 to see them pause

    # T2 — efficiency KPIs (dedicated section)
    head("4", "EFFICIENCY   ·   fewer tests, same coverage   [T2]")
    def _pct(n): return round((total - n) / total * 100) if total else 0
    ra, rb, ru = len(set_a), len(set_b), len(union)
    rule = "   " + "-" * 60
    print(rule)
    print(f"     {C.CYAN}RAN {C.BOLD}{ru} / {total}{C.RESET}{C.CYAN} tests{C.RESET}      "
          f"{C.GREEN}AVOIDED {C.BOLD}{total-ru}{C.RESET}{C.GREEN} tests{C.RESET}      "
          f"{C.GREEN}{C.BOLD}{_pct(ru)}% of the suite skipped{C.RESET}")
    print(rule)
    print(f"     Flow 1 · defect history   {C.BOLD}{ra} / {total}{C.RESET}  ({_pct(ra)}% avoided)")
    print(f"     Flow 2 · release delta    {C.BOLD}{rb} / {total}{C.RESET}  ({_pct(rb)}% avoided)")
    print(f"     Combined union            {C.BOLD}{ru} / {total}{C.RESET}  ({_pct(ru)}% avoided)")
    print(f"   {C.GREY}Only the tests that carry risk or changed this release are run — the rest are skipped with a logged reason.{C.RESET}")

    # T3 — decision explanations
    head("5", "WHY THESE TESTS   ·   the agent's reasoning")
    risk = {r["component"]: r["risk"] for r in json.loads((STATE / "risk.json").read_text())}
    impact = {r["component"]: r["impact"] for r in json.loads((STATE / "impact.json").read_text())}
    for t in union:
        comp = suite.get(t, t); why = []
        if risk.get(comp, 0) >= 4: why.append(f"defect-history risk {risk[comp]:.1f}")
        if impact.get(comp, 0) >= 4: why.append(f"release impact {impact[comp]:.1f}")
        print(f"  {C.GREEN}RUN{C.RESET}  {comp:9} — {' + '.join(why) or 'selected'}  (>= 4.0 threshold)")
    print(f"  {C.GREY}every skipped component scored below 4.0 on both signals — logged with its reason.{C.RESET}")

    # T5 data quality + T6 approval gates
    head("6", "DATA QUALITY & APPROVAL GATES   [T5 · T6]")
    ok, dq = check_data_quality(); print(dq)
    for g in ("data_quality", "risk_ratings"):
        print("  " + approvals.gate(g)[1])

    # T4 — evaluation harness (expected vs actual selection, drift check)
    head("7", "EVALUATION HARNESS   ·   expected vs actual selection (drift check)   [T4]")
    exp_path = ROOT / "eval" / "expected.json"
    if exp_path.exists():
        exp = json.loads(exp_path.read_text())
        def _chk(name, got, want):
            got = sorted(got); want = sorted(want); ok = got == want
            tag = f"{C.GREEN}PASS{C.RESET}" if ok else f"{C.RED}FAIL{C.RESET}"
            print(f"  {tag}  {name}: {len(got)} selected {'match the expected set' if ok else 'DIFFER from expected'}")
            if not ok:
                print(f"        got      {got}")
                print(f"        expected {want}")
            return ok
        _chk("flow1 · defect history", set_a, exp["flow1"]["selected"])
        _chk("flow2 · release delta", set_b, exp["flow2"]["selected"])
        print(f"  {C.GREY}re-run after any model / workflow / data change to catch drift  ·  python run_poc.py --eval{C.RESET}")
    else:
        print(f"  {C.GREY}[placeholder] fixed evaluation set not found (eval/expected.json).{C.RESET}")

    src_backup = SRC.read_text()
    test_backup = TEST_SEARCH.read_text()
    try:
        head("8", "SELF-HEAL · run the selected subset (two failures planted)", C.YELLOW)
        normalise_clean()
        plant_bugs()
        print(test_report(" ".join(union), "TEST REPORT  ·  selected subset (2 issues planted)")[0])

        p = probe()
        checkout_ok = (p["checkout_tax"] == SPEC["checkout"]["tax"]
                       and p["checkout_total"] == SPEC["checkout"]["total"])
        search_ok = (p["search_upper"] == SPEC["search"]["upper"])

        head("9", "DIAGNOSE & ACT   (test-script → PR for review · application → log defect)   [T3 · T7]")
        jira_key = None; merged = False

        # TEST SCRIPT issue -> prepare a PR, merge only after approval (T6, T7)
        print(f"\n{C.CYAN}search:{C.RESET} app returns {p['search_upper']} — correct per REQ-413 (case-insensitive). Test is stale.")
        if search_ok:
            print(f"  {C.GREEN}→ This is a TEST SCRIPT issue. Preparing a fix for QA review.{C.RESET}")
            pr = propose_test_fix("tests/test_search.py", test_backup,
                                  "search test updated for REQ-413 (case-insensitive)")
            print(f"  {C.GREY}  {pr}{C.RESET}")
            approved, gline = approvals.gate("test_fix_merge")
            print("  " + gline)
            if approved:
                TEST_SEARCH.write_text(test_backup); merged = True
                print(f"  {C.GREEN}  merged after QA approval — the stale test now passes.{C.RESET}")
            else:
                print(f"  {C.GREY}  left unmerged — it will pass once QA approves the PR.{C.RESET}")

        # APPLICATION issue -> gate, then log a real Jira defect (T6)
        print(f"\n{C.CYAN}checkout:{C.RESET} app taxes twice — tax {p['checkout_tax']} (expected 2.40), total {p['checkout_total']} (expected 32.39).")
        if not checkout_ok:
            print(f"  {C.YELLOW}→ This is an APPLICATION issue. Logging it in Jira as a defect.{C.RESET}")
            os.environ.setdefault("REPORT_BUGS", "1")
            approved_d, dgline = approvals.gate("defect_assignment", "checkout · tax applied twice")
            print("  " + dgline)
            details = ("One Sauce Labs Backpack ($29.99): tax expected 2.40 / actual "
                       f"{p['checkout_tax']}, total expected 32.39 / actual {p['checkout_total']}. "
                       "checkout_totals() applies TAX_RATE twice. Caught by "
                       "tests/test_checkout.py::test_tax_is_eight_percent_of_subtotal.")
            if approved_d:
                result = report_defect_to_jira(
                    "checkout", "Tax applied twice on checkout overview — total overcharged",
                    details, severity="blocker")
                m = re.search(r"[A-Z][A-Z0-9]+-\d+", result)
                jira_key = m.group(0) if m else None
                if jira_key:
                    print(f"  {C.YELLOW}  Logged as {jira_key}{C.RESET}  {C.GREY}{result.split(jira_key,1)[-1].strip(' .')}{C.RESET}")
                else:
                    print(f"  {C.GREY}  {result}{C.RESET}")
            else:
                print(f"  {C.GREY}  defect prepared — pending approval before filing.{C.RESET}")
            print(f"  {C.GREY}  source left unchanged — a developer owns the fix.{C.RESET}")

        head("10", "RE-RUN   (test fixed → the only failure left is the app defect)")
        rep, _passed_after, failed_after = test_report(" ".join(union), "TEST REPORT  ·  after self-heal")
        print(rep)
        remaining = jira_key or "the checkout defect in Jira"
        print(f"\n  {C.BOLD}Result:{C.RESET} the test-script issue is fixed; only the "
              f"{C.YELLOW}APPLICATION defect (checkout){C.RESET} remains — tracked as {C.BOLD}{remaining}{C.RESET} for the developer.")

        fixed_n = 1 if (search_ok and merged) else 0
        defect_str = f"1 defect filed ({jira_key})" if jira_key else ("1 defect logged" if not checkout_ok else "0 defects")
        eff = f"{len(union)}/{total} run · {round((total-len(union))/total*100)}% avoided"
        bar = "=" * 78
        print(f"\n{C.GREEN}{bar}{C.RESET}")
        print(f"  {C.BOLD}RUN COMPLETE{C.RESET}   {C.CYAN}{eff}{C.RESET}   -   {C.GREEN}{fixed_n} test fixed{C.RESET}   -   "
              f"{C.YELLOW}{defect_str}{C.RESET}   -   {C.RED}{failed_after} red (tracked){C.RESET}")
        print(f"{C.GREEN}{bar}{C.RESET}")
    finally:
        SRC.write_text(src_backup)
        TEST_SEARCH.write_text(test_backup)
        try:
            import shutil
            shutil.rmtree(ROOT / "_proposed_fixes", ignore_errors=True)
        except Exception:
            pass
        print(f"\n{C.GREY}(restored src/swaglabs.py and tests/test_search.py — tree is exactly as found){C.RESET}")

if __name__ == "__main__":
    main()
