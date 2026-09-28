"""agent/feedback_demo.py — the learning loop, visible (item 15).

Item 15 asks for self-heal decisions and human reviews to feed back in. The
machinery lives in signals.py; this is the view of it, plus a way to seed a
worked example so the effect is demonstrable without a paid LLM run.

    python run_poc.py --feedback-demo    # seed a worked history
    python run_poc.py --feedback         # what the agent has learned

What it learns from, and why the weights differ:

    missed       a defect appeared where we did NOT select  -> +2.0, the
                 expensive mistake; this is a bug we shipped
    real_defect  we selected here and found a genuine bug   -> +1.0
    rejected     a human overrode our rating                -> +0.5
    approved     a human agreed                             ->  0.0 (no news)
    stale_test   the test was wrong, not the app            -> -0.5
    false_alarm  we ran tests here and nothing was wrong    -> -1.0, cheap

Asymmetry is deliberate: missing a defect costs far more than running a test
that passes, so the loop is biased towards over-testing rather than under.
"""
import json

from .common import C, STATE
from . import status as S
from .signals import (FEEDBACK_FILE, OUTCOME_WEIGHT, feedback_multipliers,
                      record_feedback, FEEDBACK_MAX, _load_feedback)

#: A worked history. These mirror what the demo actually produces: the checkout
#: defect was real, the search failure was a stale test, payments was selected
#: and clean, and cart is the one we missed.
WORKED_EXAMPLE = [
    ("checkout", "real_defect", "DEF-11 tax applied twice — caught by our selection"),
    ("checkout", "real_defect", "reopened after the first fix"),
    ("checkout", "approved", "QA approved the risk rating"),
    ("search", "stale_test", "test was written before REQ-413; app was right"),
    ("search", "false_alarm", "selected on churn, nothing wrong"),
    ("payments", "false_alarm", "high impact score, suite clean"),
    ("cart", "missed", "CART-77 escaped to production — we skipped cart"),
    ("login", "approved", "QA agreed with the selection"),
]


def seed():
    S.banner("FEEDBACK LOOP · seeding a worked example",
             "item 15 · what past runs and human reviews teach the agent")
    FEEDBACK_FILE.unlink(missing_ok=True)
    for comp, outcome, detail in WORKED_EXAMPLE:
        record_feedback(comp, outcome, detail)
    print(f"  recorded {len(WORKED_EXAMPLE)} events -> "
          f"{FEEDBACK_FILE.relative_to(STATE.parent)}")
    print(f"  {C.GREY}These mirror what --demo produces. In a live deployment they are\n"
          f"  appended automatically by the self-heal step and by each approval "
          f"decision.{C.RESET}\n")
    report(banner=False)


def report(banner=True):
    if banner:
        S.banner("FEEDBACK LOOP", "item 15 · what the agent has learned so far")

    data = _load_feedback()
    events = data.get("events", [])
    if not events:
        S.say(S.PARTIAL, "feedback loop (item 15)",
              "no history recorded yet")
        print(f"\n  {C.GREY}The mechanism is live — every self-heal outcome and approval\n"
              f"  decision is recorded. There is simply nothing to learn from yet.\n"
              f"  Seed a worked example with: python run_poc.py --feedback-demo{C.RESET}")
        return {}

    by_comp = {}
    for e in events:
        by_comp.setdefault(e["component"], []).append(e)

    mult, n = feedback_multipliers(announce=False)

    print(f"  {len(events)} event(s) across {len(by_comp)} component(s)\n")
    print(f"  {'component':12} {'events':>7} {'score':>7} {'weight':>8}   what it learned")
    print(f"  {C.GREY}{'-' * 84}{C.RESET}")
    for comp in sorted(by_comp, key=lambda c: -mult.get(c, 1.0)):
        evs = by_comp[comp]
        score = sum(OUTCOME_WEIGHT.get(e["outcome"], 0.0) for e in evs)
        m = mult.get(comp, 1.0)
        if m > 1.02:
            colour, verdict = C.RED, "test MORE here"
        elif m < 0.98:
            colour, verdict = C.GREEN, "test less here"
        else:
            colour, verdict = C.GREY, "no change"
        kinds = ", ".join(sorted({e["outcome"] for e in evs}))
        print(f"  {comp:12} {len(evs):>7} {score:>+7.1f} {colour}{m:>7.2f}x{C.RESET}   "
              f"{verdict}  {C.GREY}({kinds}){C.RESET}")

    print(f"\n  {C.BOLD}How it weighs outcomes{C.RESET}")
    for outcome, w in sorted(OUTCOME_WEIGHT.items(), key=lambda kv: -kv[1]):
        colour = C.RED if w > 0 else C.GREEN if w < 0 else C.GREY
        print(f"    {colour}{w:+5.1f}{C.RESET}  {outcome}")
    print(f"  {C.GREY}Asymmetric on purpose: missing a defect (+2.0) costs far more than\n"
          f"  running a test that passes (-1.0), so the loop leans towards "
          f"over-testing.{C.RESET}")

    print(f"\n  {C.GREY}Bounded at {FEEDBACK_MAX}x either way, so a short history cannot "
          f"swamp the\n  defect evidence. The weights above are already live in "
          f"--signals and in both flows.{C.RESET}")
    return mult
