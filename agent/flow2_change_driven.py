"""
agent/flow2_change_driven.py — FLOW 2: change driven.

"What just changed?"  Read the release delta — new user stories / features, bug
fixes and requirement changes — plus the release's code churn. For each change
record what changed, which component it touches and where it came from. Rank
components by IMPACT

    impact = (2 x features + 2 x bug fixes + 3 x requirement changes) x (1 + churn)

then pick and run only the tests that cover the most-changed components. If a
selected test fails because src/swaglabs.py is buggy, fix the source (never the
test) and re-run until the selected suite is green.
"""

import csv
import json
from collections import defaultdict

from .console import tier_of
from .common import (
    DATA, TESTS, STATE, THRESHOLD, run_agent, efficiency_line,
)
from .change_source import use_live_changes, load_features_live, load_bugfixes_live
from .confluence_source import confluence_configured, load_requirements_live
from .jira_report import report_bug_to_jira, REPORT_TOOL
from .guarded_tools import GUARDED_TOOLS as GENERIC_TOOLS, GUARDED_IMPL as GENERIC_IMPL

DELTA = DATA / "release_delta"

# how much each kind of change says "re-test me"
CHANGE_WEIGHT = {"feature": 2.0, "bugfix": 2.0, "requirement": 3.0}


# ---- release-delta loaders (Flow 2) -------------------------------------------
def _rows(name):
    p = DELTA / name
    return list(csv.DictReader(p.read_text().splitlines())) if p.exists() else []


def load_features():
    return [{
        "id": r.get("key") or "STORY-?",
        "component": (r.get("component") or "unknown").strip(),
        "type": "feature",
        "summary": r.get("summary") or "",
        "source": "user story",
    } for r in _rows("stories.csv")]


def load_bugfixes():
    return [{
        "id": r.get("key") or "FIX-?",
        "component": (r.get("component") or "unknown").strip(),
        "type": "bugfix",
        "summary": r.get("summary") or "",
        "source": "bug fix",
    } for r in _rows("bugfixes.csv")]


def load_requirements():
    return [{
        "id": r.get("key") or "REQ-?",
        "component": (r.get("component") or "unknown").strip(),
        "type": "requirement",
        "summary": r.get("summary") or "",
        "source": "requirement change",
    } for r in _rows("requirements.csv")]


def load_release_churn():
    churn = defaultdict(int)
    for r in _rows("release_churn.csv"):
        comp = (r.get("component") or "unknown").strip()
        try:
            churn[comp] += int(r.get("files_changed") or 1)
        except ValueError:
            churn[comp] += 1
    return dict(churn)


def _change_sources():
    """Pick the release-delta sources. With CHANGE_LIVE=1 (+ credentials),
    features & bug fixes come live from Jira and requirement changes live from
    Confluence; each part falls back to its CSV otherwise. Churn always comes
    from the CSV because it is git history, not a tracker."""
    live = use_live_changes()
    if live:
        feat = ("feature", "jira (live)", load_features_live)
        fix = ("bugfix", "jira (live)", load_bugfixes_live)
    else:
        feat = ("feature", "csv", load_features)
        fix = ("bugfix", "csv", load_bugfixes)
    if live and confluence_configured():
        req = ("requirement", "confluence (live)", load_requirements_live)
    else:
        req = ("requirement", "csv", load_requirements)
    return [feat, fix, req]


def list_test_suite():
    p = TESTS / "test_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---- pipeline tools (Flow 2) --------------------------------------------------
def read_release_delta():
    """Read the release delta (features, bug fixes, requirement changes) + churn."""
    changes, per_type, origin = [], defaultdict(int), {}
    for typ, org, loader in _change_sources():
        for ch in loader():
            changes.append(ch)
            per_type[ch["type"]] += 1
        origin[typ] = org
    churn = load_release_churn()
    (STATE / "changes.json").write_text(json.dumps(changes))
    (STATE / "release_churn.json").write_text(json.dumps(churn))
    lines = [f"Read {len(changes)} changes in this release delta:"]
    lines += [f"  - {t}: {per_type[t]:2}  ({origin.get(t, 'csv')})" for t in ("feature", "bugfix", "requirement")]
    dist = ", ".join(f"{k} {v}" for k, v in sorted(churn.items(), key=lambda kv: -kv[1]))
    lines.append(f"  - churn: {sum(churn.values())} files changed  ->  {dist}  (git csv, weighting only)")
    return "\n".join(lines)


def summarize_changes():
    """For each change: what changed, which component, where it came from."""
    f = STATE / "changes.json"
    if not f.exists():
        return "ERROR: run read_release_delta first."
    changes = json.loads(f.read_text())
    by = defaultdict(list)
    for ch in changes:
        by[ch["component"]].append(ch)
    lines = ["Changes by component (what changed · from where):"]
    for comp, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        types = defaultdict(int)
        for it in items:
            types[it["type"]] += 1
        tsum = ", ".join(f"{k}:{v}" for k, v in sorted(types.items()))
        lines.append(f"  {comp:12} {len(items):2} changes  [{tsum}]")
        for it in items:
            lines.append(f"      {it['id']:10} ({it['source']}) {it['summary'][:56]}")
    return "\n".join(lines)


def score_impact():
    """Rank components by impact = weighted change count x (1 + churn)."""
    cf = STATE / "changes.json"
    if not cf.exists():
        return "ERROR: run read_release_delta first."
    changes = json.loads(cf.read_text())
    churn = json.loads((STATE / "release_churn.json").read_text()) if (STATE / "release_churn.json").exists() else {}
    agg = defaultdict(lambda: {"score": 0.0, "feature": 0, "bugfix": 0, "requirement": 0})
    for ch in changes:
        a = agg[ch["component"]]
        a[ch["type"]] += 1
        a["score"] += CHANGE_WEIGHT.get(ch["type"], 1.0)
    # Phase 3 signals (items 12, 14, 15) — same bounded multipliers as flow 1, so
    # a business-critical component that changed outranks an equally-changed
    # low-usage one.
    from .signals import combined_multipliers, explain as explain_signals
    signals = combined_multipliers(announce=False)

    all_comps = set(agg) | set(churn) | set(list_test_suite().values())
    ranked = []
    for comp in all_comps:
        a = agg[comp]
        c = churn.get(comp, 0)
        base = a["score"] * (1 + min(1.0, c / 8.0))
        sig = signals["combined"].get(comp, 1.0)
        ranked.append((comp, base * sig, a, c, sig))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    (STATE / "impact.json").write_text(json.dumps(
        # Stored at full precision on purpose. Rounding to 2dp here and then
        # formatting to 1dp elsewhere rounds twice: 6.9499 -> 6.95 -> "7.0",
        # while the line that prints the raw value says "6.9". One number, two
        # spellings, on the same screen.
        [{"component": c, "impact": i} for c, i, _, _, _ in ranked]))

    any_sig = any(abs(s - 1.0) > 0.001 for *_, s in ranked)
    lines = ["Impact-ranked components   impact = (2*feat + 2*fix + 3*req) x (1 + churn)"
             + (" x business/sprint/rca/feedback:" if any_sig else ":")]
    for comp, impact, a, c, sig in ranked:
        # MED starts at the selection cut-off, so the label and the decision
        # agree: MED or better is always run, LOW is always skipped.
        tier = tier_of(impact, THRESHOLD)[0].upper()
        weighted = a["score"]                       # 2*feat + 2*fix + 3*req
        mult = 1 + min(1.0, c / 8.0)                # churn multiplier (capped at 2.0)
        tail = ""
        if abs(sig - 1.0) > 0.001:
            tail = f" x {sig:.2f} [{explain_signals(comp, signals)}]"
        lines.append(
            f"  [{tier:4}] {comp:12} {a['feature']}f {a['bugfix']}x {a['requirement']}r churn{c}   "
            f"(2*{a['feature']}+2*{a['bugfix']}+3*{a['requirement']})={weighted:.0f} x (1+{c}/8)={mult:.2f}{tail} = impact {impact:.1f}")
    return "\n".join(lines)


def select_change_tests(threshold=None):
    """Select the tests covering the most-changed components."""
    threshold = THRESHOLD if threshold is None else float(threshold)
    imf = STATE / "impact.json"
    if not imf.exists():
        return "ERROR: run score_impact first."
    impact = {r["component"]: r["impact"] for r in json.loads(imf.read_text())}
    suite = list_test_suite()
    changed = {c for c, i in impact.items() if i >= threshold}
    selected = sorted(t for t, comp in suite.items() if comp in changed)
    skipped = sorted(t for t, comp in suite.items() if comp not in changed)
    (STATE / "selected.json").write_text(json.dumps(selected))
    lines = [f"Impact threshold >= {threshold}. Most-changed components: {', '.join(sorted(changed)) or '(none)'}",
             f"SELECTED {len(selected)} of {len(suite)} regression tests:"]
    lines += [f"  RUN  {t}   (covers {suite[t]}, impact={impact.get(suite[t],0):.1f})" for t in selected]
    lines += [f"  skip {t}   (covers {suite[t]}, unchanged this release)" for t in skipped]
    lines.append(efficiency_line(selected, len(suite)))
    return "\n".join(lines)


# ---- tool wiring (Flow 2) -----------------------------------------------------
TOOL_IMPL = {
    "read_release_delta": read_release_delta,
    "summarize_changes": summarize_changes,
    "score_impact": score_impact,
    "select_change_tests": select_change_tests,
    "report_bug_to_jira": report_bug_to_jira,
    **GENERIC_IMPL,
}

TOOLS = [
    {"name": "read_release_delta", "description": "Read this release's changes — new user stories/features, bug fixes, requirement changes — plus the code churn. Call first.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "summarize_changes", "description": "Group the changes by component: what changed, and where each change came from.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "score_impact", "description": "Rank components by impact = weighted change count x (1 + churn).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "select_change_tests", "description": f"Select the regression tests covering the most-changed components. Optional threshold (default {THRESHOLD:.1f}).", "input_schema": {"type": "object", "properties": {"threshold": {"type": "number"}}}},
    REPORT_TOOL,
] + GENERIC_TOOLS

SYSTEM = (
    "You are a change-driven regression selection agent for an SDET team testing a "
    "Swag Labs style store (login, inventory, cart, checkout, search, payments). You "
    "decide which regression tests to run for THIS release based on WHAT CHANGED — "
    "new user stories/features, bug fixes and requirement changes — not on old "
    "defect history.\n\n"
    "Order of work:\n"
    "  1. read_release_delta\n  2. summarize_changes\n  3. score_impact\n"
    "  4. select_change_tests\n  5. run_pytest on ONLY the selected subset\n"
    "If a selected test fails because the SOURCE is buggy: (a) call report_bug_to_jira "
    "to file the defect and assign it to the developer/BA, then (b) read src/swaglabs.py, "
    "fix the bug with write_file (never weaken the test), and re-run until the selected "
    "suite passes. Finish with a short release-readiness summary: most-changed "
    "components, tests run vs skipped, any Jira bugs filed, and the final result. Then STOP."
)

DEFAULT_TASK = (
    "We are cutting a release of our Swag Labs store. Read the release delta — the "
    "new user stories, the bug fixes and the requirement changes — plus the code "
    "churn. Tell me which components changed and by how much, rank them by impact, "
    "then select and run ONLY the regression tests that cover the changed components. "
    "If a selected test fails because src/swaglabs.py is buggy, fix the source (not "
    "the test) and re-run until the selected suite is green. Finish with a "
    "release-readiness summary."
)


def run(task=None, max_steps=16):
    run_agent(task or DEFAULT_TASK, TOOLS, TOOL_IMPL, SYSTEM, max_steps=max_steps)
