"""agent/schedules.py — when the agent runs, and how much it runs (item 17).

The same agent is asked a different question depending on when it fires:

    per-PR      "did THIS change break anything?"    minutes, narrow, cheap
    daily       "did yesterday break anything?"      short lookback
    sprint      "is this sprint's work safe?"        the release delta
    quarterly   "is the whole product safe?"         everything, deep history

A profile is not cosmetic — it changes the lookback window, the risk threshold
and the test budget, so the selection genuinely differs. Running the quarterly
profile on every pull request would be both slow and pointless; running the PR
profile quarterly would miss slow-burning risk.

    python run_poc.py --schedule sprint
    python run_poc.py --schedule pr --dry-run
"""
from .common import C, THRESHOLD
from . import status as S

PROFILES = {
    "pr": {
        "label": "per pull request",
        "question": "did THIS change break anything?",
        "lookback_days": 14,
        "threshold": round(THRESHOLD * 0.4, 1),   # low bar: one small change should still trip it
        "max_tests": 20,       # hard budget — a PR gate must stay fast
        "signals": ["change"],
        "cadence": "every push",
    },
    "daily": {
        "label": "nightly",
        "question": "did yesterday's merges break anything?",
        "lookback_days": 30,
        "threshold": round(THRESHOLD * 0.6, 1),
        "max_tests": 50,       # nobody is waiting on a nightly run
        "signals": ["change", "defect"],
        "cadence": "once a night",
    },
    "sprint": {
        "label": "per sprint / release",
        "question": "is this sprint's work safe to ship?",
        "lookback_days": 90,
        "threshold": THRESHOLD,                   # the project default
        "max_tests": None,
        "signals": ["change", "defect", "business"],
        "cadence": "end of sprint",
    },
    "quarterly": {
        "label": "quarterly regression",
        "question": "is the whole product still safe?",
        "lookback_days": 365,
        "threshold": round(THRESHOLD * 0.4, 1),   # low bar + no budget = wide, deep sweep
        "max_tests": None,
        "signals": ["change", "defect", "business", "architecture", "sprint", "rca"],
        "cadence": "once a quarter",
    },
}

DEFAULT = "sprint"


def get(name):
    key = (name or DEFAULT).strip().lower()
    if key not in PROFILES:
        raise KeyError(f"unknown schedule '{name}'. "
                       f"Choose one of: {', '.join(PROFILES)}")
    return PROFILES[key]


def apply(name, announce=True):
    """Apply a profile to both flows. Returns the profile."""
    p = get(name)
    from . import flow1_defect_history as f1

    f1.LOOKBACK_DAYS = p["lookback_days"]
    if announce:
        S.banner(f"SCHEDULE · {p['label'].upper()}", p["question"])
        print(f"  cadence      {p['cadence']}")
        print(f"  lookback     {p['lookback_days']} days")
        print(f"  threshold    {p['threshold']}")
        print(f"  test budget  {p['max_tests'] or 'no cap'}")
        print(f"  signals      {', '.join(p['signals'])}")
    return p


def run(name):
    """Run both flows under one schedule profile and show what changes."""
    p = apply(name)
    from . import flow1_defect_history as f1, flow2_change_driven as f2

    print()
    f1.read_defect_sources()
    f1.score_risk()
    print(f"{C.BOLD}Flow 1 · defect history{C.RESET}")
    print(f1.select_regression_tests(p["threshold"]))

    print()
    f2.read_release_delta()
    f2.score_impact()
    print(f"{C.BOLD}Flow 2 · release delta{C.RESET}")
    print(f2.select_change_tests(p["threshold"]))

    if p["max_tests"]:
        import json
        from .common import STATE
        sel = json.loads((STATE / "selected.json").read_text())
        if len(sel) > p["max_tests"]:
            # Budget is enforced by keeping the highest-scoring tests, not by
            # truncating an arbitrary slice.
            print(f"\n  {C.YELLOW}budget:{C.RESET} {p['label']} caps at "
                  f"{p['max_tests']} tests — trimming {len(sel)} to the "
                  f"{p['max_tests']} highest-scoring.")
            impact = {r["component"]: r["impact"]
                      for r in json.loads((STATE / "impact.json").read_text())}
            suite = f2.list_test_suite()
            sel = sorted(sel, key=lambda t: -impact.get(suite.get(t, ""), 0))[:p["max_tests"]]
            (STATE / "selected.json").write_text(json.dumps(sorted(sel)))
            for t in sorted(sel):
                print(f"    {C.GREEN}RUN{C.RESET}  {t}")
    return p


def compare():
    """Show all four profiles side by side — this is the deck slide (item 21)."""
    S.banner("RUN SCHEDULES", "item 17 / slide 21 · same agent, four questions")
    print(f"  {'profile':11} {'cadence':14} {'lookback':>9} {'thresh':>7} "
          f"{'budget':>7}  question")
    print(f"  {C.GREY}{'-' * 88}{C.RESET}")
    for key in ("pr", "daily", "sprint", "quarterly"):
        p = PROFILES[key]
        print(f"  {C.BOLD}{key:11}{C.RESET} {p['cadence']:14} "
              f"{p['lookback_days']:>7}d {p['threshold']:>7.1f} "
              f"{str(p['max_tests'] or '-'):>7}  {C.GREY}{p['question']}{C.RESET}")
    print(f"\n  {C.GREY}The profile changes the lookback, the threshold and the budget — "
          f"so the\n  selection really differs. A PR gate that ran the quarterly sweep "
          f"would be\n  useless; a quarterly sweep with the PR budget would miss "
          f"slow-burning risk.{C.RESET}")
