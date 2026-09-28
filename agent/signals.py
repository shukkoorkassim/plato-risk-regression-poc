"""agent/signals.py — the Phase 3 risk signals (items 12, 14, 15).

Three extra signals feed the risk model beyond defects and churn:

    business   (item 12)  what the feature is worth — criticality x usage
    sprint     (item 14)  delivery pressure — carry-over, spillover, re-opens
    rca        (item 14)  root causes, weighted up when the cause is systemic
    feedback   (item 15)  what past runs and human reviews taught us

Each returns a MULTIPLIER on a component's risk, not a replacement for it. That
matters: a business-critical component with no defect history should not
outrank one that is actually breaking. Multipliers are bounded so no single
signal can dominate the evidence.

DATA HONESTY. The CSVs for business / sprint / rca ship as invented placeholder
data, and every loader announces that on load, naming the real source. A
made-up criticality table that prints nothing looks exactly like a real one on
a slide — so these never stay quiet.
"""
import csv
import json
from collections import defaultdict

from .common import DATA, STATE, C
from . import status as S

# ---- bounds: no single signal may swamp the defect evidence --------------------
BUSINESS_MAX = 1.60      # a critical, heavily used feature counts 60% more
SPRINT_MAX = 1.35
RCA_MAX = 1.40
FEEDBACK_MAX = 1.30      # and 1/1.30 on the downside

#: Ceiling on the PRODUCT of all four signals. Each signal is capped on its own,
#: but 1.6 x 1.35 x 1.4 x 1.3 = 3.9x — enough for context to swamp the evidence
#: of what is actually breaking. 2.0x is the most the extra signals may ever
#: move a component: meaningful, but never decisive on its own.
COMBINED_MAX = 2.00

CRITICALITY_WEIGHT = {"critical": 1.0, "high": 0.65, "medium": 0.35, "low": 0.1}


def _rows(name):
    p = DATA / name
    if not p.exists():
        return []
    return list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))


def _is_placeholder(rows):
    return bool(rows) and any((r.get("source") or "").strip().upper() == "PLACEHOLDER"
                              for r in rows)


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---- item 12 · business value ---------------------------------------------------
def business_multipliers(announce=True):
    """Criticality x usage -> a bounded multiplier per component."""
    rows = _rows("business_value.csv")
    if not rows:
        if announce:
            S.say(S.PARTIAL, "business value (item 12)",
                  "data/business_value.csv not found — signal inactive, weight 1.0")
        return {}, False

    placeholder = _is_placeholder(rows)
    if announce and placeholder:
        S.placeholder(
            "business value (item 12)",
            "data/business_value.csv is INVENTED — do not quote these weights",
            "product owner's criticality rating + usage from analytics "
            "(sessions or revenue share per feature, last quarter)")

    peak = max((_f(r.get("monthly_sessions")) for r in rows), default=0.0) or 1.0
    out = {}
    for r in rows:
        comp = (r.get("component") or "").strip()
        if not comp:
            continue
        crit = CRITICALITY_WEIGHT.get((r.get("criticality") or "").strip().lower(), 0.35)
        usage = _f(r.get("monthly_sessions")) / peak
        revenue = _f(r.get("revenue_share_pct")) / 100.0
        # criticality leads; usage and revenue temper it
        strength = 0.6 * crit + 0.25 * usage + 0.15 * revenue
        out[comp] = round(1.0 + (BUSINESS_MAX - 1.0) * min(1.0, strength), 3)
    return out, placeholder


# ---- item 14 · sprint history ---------------------------------------------------
def sprint_multipliers(announce=True):
    """Carry-over and spillover mean a component is under delivery pressure."""
    rows = _rows("sprint_history.csv")
    if not rows:
        if announce:
            S.say(S.PARTIAL, "sprint history (item 14)",
                  "data/sprint_history.csv not found — signal inactive, weight 1.0")
        return {}, False

    placeholder = _is_placeholder(rows)
    if announce and placeholder:
        S.placeholder(
            "sprint history (item 14)",
            "data/sprint_history.csv is INVENTED",
            "Jira sprint reports — carry-over issues and spillover days per component")

    agg = defaultdict(lambda: {"carried": 0.0, "spill": 0.0, "reopened": 0.0})
    for r in rows:
        comp = (r.get("component") or "").strip()
        if not comp:
            continue
        a = agg[comp]
        a["carried"] += _f(r.get("carried_over"))
        a["spill"] += _f(r.get("spillover_days"))
        a["reopened"] += _f(r.get("reopened_in_sprint"))

    worst = max((a["carried"] + a["spill"] / 2 + a["reopened"] * 2
                 for a in agg.values()), default=0.0) or 1.0
    out = {}
    for comp, a in agg.items():
        raw = a["carried"] + a["spill"] / 2 + a["reopened"] * 2
        out[comp] = round(1.0 + (SPRINT_MAX - 1.0) * min(1.0, raw / worst), 3)
    return out, placeholder


# ---- item 14 · root-cause notes -------------------------------------------------
def rca_multipliers(announce=True):
    """A systemic root cause is a reason to re-test more, not less."""
    rows = _rows("rca_notes.csv")
    if not rows:
        if announce:
            S.say(S.PARTIAL, "root-cause notes (item 14)",
                  "data/rca_notes.csv not found — signal inactive, weight 1.0")
        return {}, False, {}

    placeholder = _is_placeholder(rows)
    if announce and placeholder:
        S.placeholder(
            "root-cause notes (item 14)",
            "data/rca_notes.csv is INVENTED",
            "the RCA / root-cause field on closed defects in Jira")

    agg = defaultdict(lambda: {"n": 0, "systemic": 0, "causes": defaultdict(int)})
    for r in rows:
        comp = (r.get("component") or "").strip()
        if not comp:
            continue
        a = agg[comp]
        a["n"] += 1
        if str(r.get("systemic", "")).strip().lower() in ("1", "true", "yes"):
            a["systemic"] += 1
        cause = (r.get("root_cause") or "unknown").strip()
        a["causes"][cause] += 1

    worst = max((a["n"] + a["systemic"] * 2 for a in agg.values()), default=0.0) or 1.0
    out, detail = {}, {}
    for comp, a in agg.items():
        raw = a["n"] + a["systemic"] * 2
        out[comp] = round(1.0 + (RCA_MAX - 1.0) * min(1.0, raw / worst), 3)
        detail[comp] = {"n": a["n"], "systemic": a["systemic"],
                        "causes": dict(a["causes"])}
    return out, placeholder, detail


# ---- item 15 · feedback ----------------------------------------------------------
FEEDBACK_FILE = STATE / "feedback.json"


def _load_feedback():
    if not FEEDBACK_FILE.exists():
        return {"events": []}
    try:
        return json.loads(FEEDBACK_FILE.read_text())
    except (ValueError, OSError):
        return {"events": []}


def record_feedback(component, outcome, detail=""):
    """Append one learning event.

    outcome is one of:
        real_defect     selection was right — a genuine bug was found here
        stale_test      the test was wrong, not the app (weak signal to de-weight)
        false_alarm     we ran tests here and nothing was wrong
        missed          a defect appeared here that we did NOT select for
        approved        a human approved our selection/rating for this component
        rejected        a human overrode us here
    """
    data = _load_feedback()
    data["events"].append({"component": component, "outcome": outcome,
                           "detail": detail})
    FEEDBACK_FILE.parent.mkdir(exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(data, indent=1))
    return len(data["events"])


#: what each outcome teaches. Missing a defect is the expensive mistake, so it
#: moves the weight hardest; a false alarm is cheap and barely moves it.
OUTCOME_WEIGHT = {
    "missed": +2.0,
    "real_defect": +1.0,
    "rejected": +0.5,
    "approved": 0.0,
    "stale_test": -0.5,
    "false_alarm": -1.0,
}


def feedback_multipliers(announce=True):
    """Turn accumulated history into a bounded per-component adjustment."""
    data = _load_feedback()
    events = data.get("events", [])
    if not events:
        if announce:
            S.say(S.PARTIAL, "feedback loop (item 15)",
                  "no history yet — run --demo, or seed with --feedback-demo")
        return {}, 0

    agg = defaultdict(float)
    for e in events:
        agg[e["component"]] += OUTCOME_WEIGHT.get(e["outcome"], 0.0)

    peak = max((abs(v) for v in agg.values()), default=0.0) or 1.0
    out = {}
    for comp, score in agg.items():
        # score in [-peak, +peak] -> multiplier in [1/FEEDBACK_MAX, FEEDBACK_MAX]
        frac = max(-1.0, min(1.0, score / peak))
        out[comp] = round(FEEDBACK_MAX ** frac, 3)
    return out, len(events)


# ---- combined ---------------------------------------------------------------------
def combined_multipliers(announce=True):
    """Every Phase 3 signal folded into one multiplier per component."""
    biz, biz_ph = business_multipliers(announce)
    spr, spr_ph = sprint_multipliers(announce)
    rca, rca_ph, rca_detail = rca_multipliers(announce)
    fb, fb_n = feedback_multipliers(announce)

    comps = set(biz) | set(spr) | set(rca) | set(fb)
    combined = {}
    for c in comps:
        raw = (biz.get(c, 1.0) * spr.get(c, 1.0)
               * rca.get(c, 1.0) * fb.get(c, 1.0))
        # Cap the COMBINED multiplier, not just each part. Four individually
        # bounded signals still compound: 1.6 x 1.35 x 1.4 x 1.3 is 3.9x, which
        # would let context outweigh the defect evidence entirely and make the
        # word "bounded" a lie. The product is what needs the ceiling.
        combined[c] = round(max(1.0 / COMBINED_MAX, min(COMBINED_MAX, raw)), 3)
    return {
        "business": biz, "sprint": spr, "rca": rca, "feedback": fb,
        "combined": combined,
        "placeholder": {"business": biz_ph, "sprint": spr_ph, "rca": rca_ph},
        "feedback_events": fb_n,
        "rca_detail": rca_detail,
    }


def multiplier_for(component, signals=None):
    signals = signals or combined_multipliers(announce=False)
    return signals["combined"].get(component, 1.0)


def explain(component, signals=None):
    """Short human-readable breakdown, for the 'why this test' output."""
    signals = signals or combined_multipliers(announce=False)
    parts = []
    for name in ("business", "sprint", "rca", "feedback"):
        m = signals[name].get(component)
        if m and abs(m - 1.0) > 0.001:
            parts.append(f"{name} x{m:.2f}")
    return " · ".join(parts)


def report():
    """`python run_poc.py --signals` — show every Phase 3 signal and its honesty."""
    S.banner("PHASE 3 RISK SIGNALS",
             "items 12 (business value) · 14 (sprint + RCA) · 15 (feedback)")
    signals = combined_multipliers(announce=True)

    comps = sorted(signals["combined"], key=lambda c: -signals["combined"][c])
    if not comps:
        print(f"\n  {C.GREY}No signals active.{C.RESET}")
        return signals

    print(f"\n  {'component':12} {'business':>9} {'sprint':>8} {'rca':>7} "
          f"{'feedback':>9} {'combined':>9}")
    print(f"  {C.GREY}{'-' * 62}{C.RESET}")
    for c in comps:
        def cell(name):
            m = signals[name].get(c)
            return f"{m:.2f}" if m else "  -  "
        comb = signals["combined"][c]
        color = C.RED if comb >= 1.5 else C.YELLOW if comb >= 1.2 else C.GREY
        print(f"  {c:12} {cell('business'):>9} {cell('sprint'):>8} "
              f"{cell('rca'):>7} {cell('feedback'):>9} "
              f"{color}{comb:>8.2f}x{C.RESET}")

    print(f"\n  {C.GREY}Each is a bounded MULTIPLIER on risk, never a replacement for it —")
    print(f"  a business-critical component with no defects should not outrank one "
          f"that is\n  actually breaking.{C.RESET}")
    print(f"  {C.GREY}Caps: business {BUSINESS_MAX}x · sprint {SPRINT_MAX}x · rca "
          f"{RCA_MAX}x · feedback {FEEDBACK_MAX}x,\n  and the PRODUCT of all four is "
          f"capped at {COMBINED_MAX}x so context can never outweigh evidence.{C.RESET}")

    ph = [k for k, v in signals["placeholder"].items() if v]
    if ph:
        print(f"\n  {C.YELLOW}{len(ph)} signal(s) running on INVENTED data:{C.RESET} "
              f"{', '.join(ph)}")
        print(f"  {C.GREY}The mechanism is real and the maths is real. The numbers are "
              f"not.\n  Nothing here should reach a slide until the CSVs are "
              f"replaced.{C.RESET}")
    return signals
