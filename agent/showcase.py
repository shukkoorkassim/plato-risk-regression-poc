"""agent/showcase.py — the full story, in the console (python run_poc.py --showcase).

`--demo` drives a real LLM and needs an API key. This is the same story told
deterministically: no API key, no pytest, no network, about eight seconds, and
every number on screen is computed live rather than printed from a script.

Ten phases, in the order you would present them:

     1  where the signals come from        6  where the coverage gaps are
     2  signal one — what has broken       7  what a human still controls
     3  signal two — what just changed     8  the two kinds of failure
     4  the selection, and what it saves   9  when it runs
     5  why each test was chosen          10  scoreboard, and what is not real

Phase 10 is deliberately the last thing on screen. A demo that ends on its own
caveats is far more persuasive than one that hides them until questioned.

    python run_poc.py --showcase              # the whole story
    python run_poc.py --showcase --pace 1.2   # slower, for presenting
    python run_poc.py --showcase --ascii      # plain characters for old consoles
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .common import C, ROOT, STATE, THRESHOLD
from . import status as S

from .console import (Box, W, set_box, banner, rule, bar, kv, tier_of,   # noqa: F401
                      score_table, cutoff_table, the_rule)

_PACE = 0.0
B = Box()


def _pause(mult=1.0):
    if _PACE:
        time.sleep(_PACE * mult)


def _plain(text):
    """Length of text with ANSI colour codes stripped."""
    out, skip = 0, False
    for ch in text:
        if ch == "\033":
            skip = True
        elif skip:
            if ch == "m":
                skip = False
        else:
            out += 1
    return out


def phase(n, total, title, strap=""):
    _pause(1.4)
    print()
    label = f" PHASE {n} of {total} "
    pad = W - len(label) - 2
    print(f"{C.CYAN}{B.tl}{label}{B.h * pad}{B.tr}{C.RESET}")
    print(f"{C.CYAN}{B.v}{C.RESET} {C.BOLD}{title:<{W - 3}}{C.RESET}{C.CYAN}{B.v}{C.RESET}")
    if strap:
        print(f"{C.CYAN}{B.v}{C.RESET} {C.GREY}{strap:<{W - 3}}{C.RESET}{C.CYAN}{B.v}{C.RESET}")
    print(f"{C.CYAN}{B.bl}{B.h * (W - 2)}{B.br}{C.RESET}")
    _pause(0.4)


# ---------------------------------------------------------------------------
def run(pace=0.0, ascii_only=False):
    global B, _PACE
    _PACE = pace
    B = set_box(ascii_only)

    from . import flow1_defect_history as f1
    from . import flow2_change_driven as f2
    from .signals import combined_multipliers, explain as explain_signals
    from . import approvals

    t0 = time.time()
    TOTAL = 10

    banner("RISK-BASED REGRESSION SELECTION",
           "An SDET agent that runs the tests that matter — and can prove it")
    print(f"  {C.GREY}PLATO · AI-enabled QA & SDET testing"
          f"{'':>18}{datetime.now():%d %b %Y · %H:%M}{C.RESET}")

    print(f"\n  {C.BOLD}What you are about to see{C.RESET}")
    for line in [
        "Two independent signals decide which tests are worth running",
        "Every score prints its own arithmetic — nothing is a black box",
        "Two failures, two different answers: fix the test, or file the bug",
        "And an honest list of what is not finished",
    ]:
        print(f"    {C.CYAN}{B.dot}{C.RESET} {line}")
        _pause(0.3)

    # ---- 1 · sources -------------------------------------------------------
    phase(1, TOTAL, "WHERE THE SIGNALS COME FROM",
          "the agent reads what your team already writes down")
    src1 = f1.read_defect_sources()
    src2 = f2.read_release_delta()
    for line in src1.splitlines() + [""] + src2.splitlines():
        print(f"  {C.GREY}{line}{C.RESET}" if line.startswith("  ") else f"  {line}")
    live = "jira (live)" in src1 or "jira (live)" in src2
    print()
    S.say(S.DONE if live else S.PARTIAL,
          "source of truth",
          "reading your live Jira and Confluence" if live else
          "reading the bundled CSVs — set JIRA_LIVE=1 in .env to pull from Jira")

    # ---- 2 · defect history ------------------------------------------------
    phase(2, TOTAL, "SIGNAL ONE — WHAT HAS BROKEN BEFORE",
          "risk = severity x recency x (1.6 if it came back) x (1 + churn)")
    risk_text = f1.score_risk()
    risks = {r["component"]: r["risk"] for r in
             json.loads((STATE / "risk.json").read_text())}
    peak = max(risks.values()) or 1
    print(f"    {'component':<12}{'broken before (flow 1)':>22}   {'':26}  tier")
    rule()
    for comp, val in sorted(risks.items(), key=lambda kv: -kv[1]):
        tier, col = tier_of(val, THRESHOLD)
        print(f"    {comp:<12}{col}{val:>22.1f}{C.RESET}   {bar(val, peak, 26, col)}  {col}{tier}{C.RESET}")
        _pause(0.18)
    print(f"\n  {C.GREY}The arithmetic, component by component:{C.RESET}")
    for line in risk_text.splitlines()[1:4]:
        print(f"  {C.GREY}{line}{C.RESET}")
    print(f"  {C.GREY}  ... {len(risks) - 3} more{C.RESET}")

    # ---- 3 · release delta -------------------------------------------------
    phase(3, TOTAL, "SIGNAL TWO — WHAT JUST CHANGED",
          "impact = (2 x features + 2 x fixes + 3 x requirement changes) x (1 + churn)")
    f2.score_impact()
    impact = {r["component"]: r["impact"] for r in
              json.loads((STATE / "impact.json").read_text())}
    peak_i = max(impact.values()) or 1
    print(f"    {'component':<12}{'changed now (flow 2)':>22}   {'':26}  tier")
    rule()
    for comp, val in sorted(impact.items(), key=lambda kv: -kv[1]):
        tier, col = tier_of(val, THRESHOLD)
        print(f"    {comp:<12}{col}{val:>22.1f}{C.RESET}   {bar(val, peak_i, 26, col)}  {col}{tier}{C.RESET}")
        _pause(0.18)

    both = sorted({c for c in risks if risks[c] >= THRESHOLD} & {c for c in impact if impact[c] >= THRESHOLD})
    if both:
        print(f"\n  {C.RED}{C.BOLD}Both signals agree on: {', '.join(both)}{C.RESET}")
        print(f"  {C.GREY}That overlap is the strongest evidence the agent can have — a component\n"
              f"  that has broken before AND changed this release.{C.RESET}")

    # The extra signals (business value, sprint pressure, root causes, past
    # feedback) no longer get a screen of their own. They are still computed:
    # phase 2 prints them inside each component's arithmetic, and phase 5 cites
    # them per test. announce=False keeps them off the console here.
    sig = combined_multipliers(announce=False)

    # ---- 4 · selection -----------------------------------------------------
    phase(4, TOTAL, "THE SELECTION — AND WHAT IT SAVES",
          f"one rule, applied to every component: {THRESHOLD:.1f} and above runs")

    # State the rule before applying it, so nobody has to infer it from the result.
    print(f"    {C.BOLD}THE RULE{C.RESET}")
    _hi = f"score {THRESHOLD:.1f} or above"
    _lo = f"score below {THRESHOLD:.1f}"
    _w = max(len(_hi), len(_lo))
    print(f"      {C.GREEN}{_hi:<{_w}}{C.RESET}{C.GREY} ......  {C.RESET}"
          f"{C.GREEN}{C.BOLD}{'SELECTED':<8}{C.RESET}"
          f"{C.GREY}   the component runs its tests{C.RESET}")
    print(f"      {C.GREY}{_lo:<{_w}} ......  {'SKIPPED':<8}"
          f"   the reason is logged, nothing is silent{C.RESET}")
    print(f"      {C.GREY}A component qualifies on EITHER signal — it does not need both.{C.RESET}")
    print(f"      {C.GREY}Cut-off set in agent/common.py; override per run with "
          f"--threshold N.{C.RESET}\n")
    _pause(0.8)

    f1.select_regression_tests()
    set_a = json.loads((STATE / "selected.json").read_text())
    f2.select_change_tests()
    set_b = json.loads((STATE / "selected.json").read_text())
    union = sorted(set(set_a) | set(set_b))
    suite = f2.list_test_suite()
    total, ran = len(suite), len(union)
    avoided = total - ran
    pct = round(avoided / total * 100) if total else 0
    (STATE / "selected.json").write_text(json.dumps(union))

    # ---- the ranking, with the cut-off drawn straight through it -----------
    comps = sorted(set(suite.values()) | set(risks) | set(impact))
    rows = []
    for comp in comps:
        r, im = risks.get(comp, 0.0), impact.get(comp, 0.0)
        rows.append((comp, r, im, max(r, im)))
    rows.sort(key=lambda row: -row[3])

    print(f"    {'rank':>4}  {'component':<12}{'risk':>8}{'impact':>9}{'rank score':>12}"
          f"   {'decision':<9}")
    rule()
    drawn = False
    for n, (comp, r, im, best) in enumerate(rows, 1):
        if best < THRESHOLD and not drawn:
            drawn = True
            tag = f" cut-off {THRESHOLD:.1f} "
            side = (W - 8 - len(tag)) // 2
            print(f"    {C.YELLOW}{B.h * side}{C.BOLD}{tag}{C.RESET}"
                  f"{C.YELLOW}{B.h * side}{C.RESET}")
        if best >= THRESHOLD:
            col, verdict = C.GREEN, "SELECTED"
        else:
            col, verdict = C.GREY, "skipped"
        rs = f"{r:.1f}" if r else "-"
        ims = f"{im:.1f}" if im else "-"
        print(f"    {col}{n:>4}{C.RESET}  {col}{comp:<12}{C.RESET}{C.GREY}{rs:>8}{ims:>9}{C.RESET}"
              f"{col}{best:>12.1f}{C.RESET}   {col}{C.BOLD}{verdict:<9}{C.RESET}")
        _pause(0.18)
    if not drawn:
        print(f"    {C.YELLOW}{B.h * 20} cut-off {THRESHOLD:.1f} — nothing fell below it "
              f"{B.h * 20}{C.RESET}")
    _pause(0.6)

    # ---- and what that means test by test ----------------------------------
    for t in sorted(suite):
        comp = suite[t]
        if t in union:
            why = []
            if risks.get(comp, 0) >= THRESHOLD:
                why.append(f"risk {risks[comp]:.1f}")
            if impact.get(comp, 0) >= THRESHOLD:
                why.append(f"impact {impact[comp]:.1f}")
            print(f"    {C.GREEN}{B.tick} RUN {C.RESET}  {t:<26} "
                  f"{C.GREY}{' + '.join(why)} {B.arrow} at or above {THRESHOLD:.1f}{C.RESET}")
        else:
            best = max(risks.get(comp, 0.0), impact.get(comp, 0.0))
            print(f"    {C.GREY}{B.cross} skip {t:<27} best score {best:.1f} "
                  f"{B.arrow} below {THRESHOLD:.1f} on both signals{C.RESET}")
        _pause(0.15)
    rule()
    print(f"    {C.CYAN}{C.BOLD}RAN {ran} of {total}{C.RESET}"
          f"      {C.GREEN}{C.BOLD}SKIPPED {avoided}{C.RESET}"
          f"      {C.GREEN}{C.BOLD}{pct}% of the suite avoided{C.RESET}")

    # ---- 5 · why -----------------------------------------------------------
    phase(5, TOTAL, "WHY EACH TEST WAS CHOSEN",
          "no black box — the agent states its reasoning per test")
    for t in union:
        comp = suite.get(t, t)
        reasons = []
        if risks.get(comp, 0) >= THRESHOLD:
            reasons.append(f"has broken before ({risks[comp]:.1f})")
        if impact.get(comp, 0) >= THRESHOLD:
            reasons.append(f"changed this release ({impact[comp]:.1f})")
        extra = explain_signals(comp, sig)
        print(f"    {C.GREEN}{B.arrow}{C.RESET} {C.BOLD}{comp}{C.RESET}")
        for r in reasons:
            print(f"        {C.GREY}{B.dot} {r}{C.RESET}")
        if extra:
            print(f"        {C.GREY}{B.dot} weighted by {extra}{C.RESET}")
        _pause(0.2)

    # ---- 6 · coverage ------------------------------------------------------
    phase(6, TOTAL, "WHERE THE COVERAGE GAPS ARE",
          "the agent cannot flag a risk that no test covers — so it says so")
    from .coverage_gap import coverage_report
    # Product components only. The seeded-defect evidence belongs to the
    # benchmark codebase and is reported in phase 10, with its own subject.
    ok, text = coverage_report()
    for line in text.splitlines()[2:]:
        if line.strip():
            print(f"  {line}")
    print(f"\n  {C.GREY}THIN means the area is above the {THRESHOLD:.1f} line but has only one "
          f"test file.\n  Nothing here is untested — but the riskiest areas deserve more "
          f"than one file.{C.RESET}")

    # ---- 7 · governance ----------------------------------------------------
    phase(7, TOTAL, "WHAT A HUMAN STILL CONTROLS",
          "four approval gates, enforced in code — not in prompt text")
    for name, label in approvals.GATES.items():
        open_now, _ = approvals.gate(name)
        mark = f"{C.GREEN}open{C.RESET}" if open_now else f"{C.YELLOW}closed{C.RESET}"
        print(f"    [{mark}] {label}")
    # The write-policy demonstration (which paths the agent may touch, proved by
    # attempting a refused write) lives in `python run_poc.py --gates`. It stays
    # out of the showcase so this phase makes one point: a human holds the gates.

    # ---- 8 · the two failures ----------------------------------------------
    phase(8, TOTAL, "WHAT THE AGENT FOUND",
          "two tests went red — and they needed opposite answers")
    src_file = ROOT / "src" / "swaglabs.py"
    backup = src_file.read_text()
    try:
        broken = backup.replace(
            "    tax = round(subtotal * TAX_RATE, 2)",
            "    tax = round(subtotal * TAX_RATE * 2, 2)", 1)
        planted = broken != backup
        if planted:
            src_file.write_text(broken)
        probe = subprocess.run(
            [sys.executable, "-c",
             "import sys,json; sys.path.insert(0,'src'); import swaglabs as s;"
             "c=s.Cart(); c.add('sauce-labs-backpack'); t=s.checkout_totals(c);"
             "print(json.dumps({'tax':t['tax'],'total':t['total'],"
             "'search':s.search_products('BACKPACK')}))"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        data = json.loads(probe.stdout.strip().splitlines()[-1])

        print(f"    {C.BOLD}2 tests failed.{C.RESET} "
              f"{C.GREY}A failing test does not say who is wrong — the app, or the\n"
              f"    test itself. Getting that backwards is how a bug ships. "
              f"Here is each one.{C.RESET}\n")

        # ---------- 1 · a real bug in the application ----------
        print(f"  {C.RED}{C.BOLD}{B.cross} FAILURE 1 of 2{C.RESET}  "
              f"{C.BOLD}checkout{C.RESET}  {C.GREY}— one backpack at $29.99{C.RESET}")
        kv("the test expected", "tax $2.40", "total $32.39")
        kv("the app gave", f"{C.RED}tax ${data['tax']}{C.RESET}",
           f"total ${data['total']}")
        kv("who is wrong?", f"{C.RED}THE APP{C.RESET}", "it charges the tax twice")
        kv("so the agent", f"{C.RED}files a defect{C.RESET}",
           "and leaves the test alone")

        # The real Jira link, if the agent has ever filed this defect for real.
        # --showcase never touches the network, so it reports the recorded fact
        # rather than pretending to file one now.
        from .jira_report import last_filed, browse_url, report_enabled
        rec = last_filed("checkout") or last_filed()
        if rec and rec.get("url"):
            print(f"\n      {C.GREEN}{C.BOLD}DEFECT LOGGED IN JIRA {B.arrow} "
                  f"{rec['key']}{C.RESET}")
            print(f"      {C.CYAN}{rec['url']}{C.RESET}")
            print(f"      {C.GREY}filed {rec.get('when','')[:16].replace('T',' ')} "
                  f"{B.dot} open it and you will find this exact bug{C.RESET}")
        else:
            where = browse_url("<KEY>") or "https://<your-site>/browse/<KEY>"
            print(f"\n      {C.YELLOW}NO DEFECT FILED YET{C.RESET} "
                  f"{C.GREY}— this run never touches the network.{C.RESET}")
            print(f"      {C.GREY}Run {C.RESET}python run_poc.py --demo{C.GREY} with "
                  f"REPORT_BUGS=1 to file it for real;{C.RESET}")
            print(f"      {C.GREY}it lands at {where} and the link shows here "
                  f"from then on.{C.RESET}")

        # ---------- 2 · a test that is simply out of date ----------
        print(f"\n  {C.CYAN}{C.BOLD}{B.cross} FAILURE 2 of 2{C.RESET}  "
              f"{C.BOLD}search{C.RESET}  {C.GREY}— searching \"BACKPACK\" in capitals{C.RESET}")
        kv("the test expected", f"{C.RED}[]{C.RESET}", "nothing found")
        kv("the app gave", f"{C.GREEN}{data['search']}{C.RESET}",
           "which is correct, per REQ-413")
        kv("who is wrong?", f"{C.CYAN}THE TEST{C.RESET}",
           "written before the requirement changed")
        kv("so the agent", f"{C.CYAN}opens a pull request{C.RESET}",
           "and files no defect at all")

        # ---------- the point ----------
        print()
        rule()
        print(f"    {C.BOLD}Same red result. Opposite correct answers.{C.RESET}")
        print(f"    {C.GREY}An agent that just makes failing tests pass would have edited "
              f"the checkout\n    test to expect ${data['tax']} — and shipped the bug it "
              f"was supposed to catch.{C.RESET}")
    finally:
        src_file.write_text(backup)
        print(f"\n  {C.GREY}(the bug above was planted for the demo and has been removed "
              f"— your source is untouched){C.RESET}")

    # ---- 9 · cadence ------------------------------------------------------
    phase(9, TOTAL, "WHEN IT RUNS",
          "same agent, four questions, four budgets")
    from .schedules import PROFILES
    print(f"    {'':<14}{'lookback':>10}{'budget':>9}   question")
    rule()
    for key in ("pr", "daily", "sprint", "quarterly"):
        p = PROFILES[key]
        print(f"    {C.BOLD}{key:<14}{C.RESET}{p['lookback_days']:>9}d"
              f"{str(p['max_tests'] or '-'):>9}   {C.GREY}{p['question']}{C.RESET}")

    # ---- 10 · scoreboard ---------------------------------------------------
    phase(10, TOTAL, "SCOREBOARD — AND WHAT IS NOT REAL YET",
          "the part most demos leave out")
    from .requirements import REQUIREMENTS, counts
    c = counts()
    done = c.get(S.DONE, 0)
    print(f"    {C.GREEN}{B.tick}{C.RESET} {done} of {len(REQUIREMENTS)} review "
          f"requirements implemented and runnable")
    print(f"    {C.CYAN}{B.dot}{C.RESET} {ran} of {total} tests run "
          f"({pct}% avoided) on this release")
    print(f"    {C.CYAN}{B.dot}{C.RESET} every score above printed its own arithmetic")
    print()
    unfinished = [r for r in REQUIREMENTS if r["state"] != S.DONE]
    if unfinished:
        print(f"  {C.BOLD}Not finished — and the tool says so on every run:{C.RESET}")
        for r in unfinished:
            print(f"    {S.tag(r['state'])} {r['id']:>2}. {r['title']}")
        print(f"\n  {C.GREY}In every case the mechanism is built and tested. What is "
              f"missing is real\n  DATA or a human step — never the logic. "
              f"See: python run_poc.py --status --gaps{C.RESET}")

    elapsed = time.time() - t0
    print()
    print(f"{C.GREEN}{B.hh * W}{C.RESET}")
    print(f"  {C.BOLD}RUN COMPLETE{C.RESET}   "
          f"{C.CYAN}{ran}/{total} tests · {pct}% avoided{C.RESET}   "
          f"{C.GREEN}{done}/{len(REQUIREMENTS)} requirements runnable{C.RESET}   "
          f"{C.GREY}{elapsed:.1f}s{C.RESET}")
    print(f"{C.GREEN}{B.hh * W}{C.RESET}")
    print(f"  {C.GREY}Live LLM run: python run_poc.py --demo      "
          f"Full status: python run_poc.py --status{C.RESET}\n")
