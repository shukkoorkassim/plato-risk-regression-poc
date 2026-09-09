"""
agent/flow1_defect_history.py — FLOW 1: defect-history driven.

"What has broken before?"  Read past defects from the bug tracker, a defect CSV
and git churn; tidy them into one shape; rate each component's risk with

    risk = severity x count x recency x (1 + churn)

then pick and run only the tests that cover the high-risk components. If a
selected test fails because src/swaglabs.py is buggy, fix the source (never the
test) and re-run until the selected suite is green.
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta

from .common import (
    DATA, TESTS, STATE, parse_date, GENERIC_TOOLS, GENERIC_IMPL, run_agent, efficiency_line,
)
from .jira_source import use_live_jira, load_jira_live
from .jira_report import report_bug_to_jira, REPORT_TOOL

LOOKBACK_DAYS = 180
SEVERITY_WEIGHT = {
    "blocker": 5.0, "critical": 4.0, "major": 3.0,
    "high": 3.0, "medium": 2.0, "minor": 1.0, "low": 1.0,
}
REOPEN_MULT = 1.6  # a defect reopened after a "fix" counts 60% more — it broke again


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "reopened")


# ---- source loaders (Flow 1) --------------------------------------------------
def load_jira_defects(path="jira_export.csv"):
    p = DATA / path
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.read_text().splitlines()))
    return [{
        "id": r.get("key") or r.get("id") or "JIRA-?",
        "component": (r.get("component") or "unknown").strip(),
        "severity": (r.get("severity") or "medium").strip().lower(),
        "summary": r.get("summary") or "",
        "resolved": r.get("resolved") or r.get("resolutiondate") or "",
        "reopened": _truthy(r.get("reopened")),
        "source": "jira",
    } for r in rows]


def load_defect_csv(path="defects.csv"):
    p = DATA / path
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.read_text().splitlines()))
    return [{
        "id": r.get("id") or r.get("defect_id") or "DEF-?",
        "component": (r.get("component") or "unknown").strip(),
        "severity": (r.get("severity") or "medium").strip().lower(),
        "summary": r.get("summary") or r.get("title") or "",
        "resolved": r.get("resolved") or r.get("fixed_date") or "",
        "reopened": _truthy(r.get("reopened")),
        "source": "csv",
    } for r in rows]


def load_git_history(path="git_churn.csv"):
    p = DATA / path
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.read_text().splitlines()))
    return [{
        "id": r.get("commit", "git")[:8],
        "component": (r.get("component") or "unknown").strip(),
        "severity": "minor",
        "summary": r.get("message") or "code churn",
        "resolved": r.get("date") or "",
        "reopened": False,
        "source": "git",
    } for r in rows]


def list_test_suite():
    p = TESTS / "test_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _defect_sources():
    """Pick the defect sources. The Jira source is a live REST+JQL pull when
    JIRA_LIVE=1 and credentials are set; otherwise it reads data/jira_export.csv."""
    if use_live_jira():
        jira = ("jira (live)", load_jira_live)
    else:
        jira = ("jira (csv)", load_jira_defects)
    return [jira, ("csv", load_defect_csv), ("git", load_git_history)]


# ---- pipeline tools (Flow 1) --------------------------------------------------
def read_defect_sources():
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    all_defects, per_source = [], {}
    for name, loader in _defect_sources():
        rows = loader()
        kept = [d for d in rows if not d["resolved"] or parse_date(d["resolved"]) >= cutoff]
        per_source[name] = len(kept)
        all_defects.extend(kept)
    (STATE / "defects.json").write_text(json.dumps(all_defects))
    lines = [f"Read {len(all_defects)} defects from {len(per_source)} sources (last {LOOKBACK_DAYS} days):"]
    lines += [f"  - {n}: {c}" for n, c in per_source.items()]
    return "\n".join(lines)


def summarize_defects():
    f = STATE / "defects.json"
    if not f.exists():
        return "ERROR: run read_defect_sources first."
    defects = json.loads(f.read_text())
    by = defaultdict(list)
    for d in defects:
        by[d["component"]].append(d)
    lines = ["Defects by component/feature:"]
    for comp, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        sevs = defaultdict(int)
        for it in items:
            sevs[it["severity"]] += 1
        sev = ", ".join(f"{k}:{v}" for k, v in sorted(sevs.items()))
        lines.append(f"  {comp:12} {len(items):2} defects  [{sev}]  e.g. \"{items[0]['summary'][:52]}\"")
    return "\n".join(lines)


def score_risk():
    f = STATE / "defects.json"
    if not f.exists():
        return "ERROR: run read_defect_sources first."
    defects = json.loads(f.read_text())
    now = datetime.now()
    agg = defaultdict(lambda: {"score": 0.0, "count": 0, "churn": 0, "worst": 0.0, "reopened": 0})
    for d in defects:
        w = SEVERITY_WEIGHT.get(d["severity"], 2.0)
        age = (now - parse_date(d["resolved"])).days if d["resolved"] else LOOKBACK_DAYS
        recency = max(0.2, 1.0 - age / LOOKBACK_DAYS)
        a = agg[d["component"]]
        if d["source"] == "git":
            a["churn"] += 1
        else:
            reop = bool(d.get("reopened"))
            a["count"] += 1
            a["score"] += w * recency * (REOPEN_MULT if reop else 1.0)
            a["worst"] = max(a["worst"], w)
            if reop:
                a["reopened"] += 1
    all_comps = set(agg) | set(list_test_suite().values())
    ranked = []
    for comp in all_comps:
        a = agg[comp]
        risk = a["score"] * (1 + min(1.0, a["churn"] / 10.0))
        ranked.append((comp, risk, a))
    ranked.sort(key=lambda x: (-x[1], x[0]))
    (STATE / "risk.json").write_text(json.dumps([{"component": c, "risk": round(r, 2)} for c, r, _ in ranked]))
    lines = ["Risk-ranked   risk = score[sum severity x recency] x (1 + churn/10):"]
    for comp, risk, a in ranked:
        tier = "HIGH" if risk >= 8 else "MED" if risk >= 3 else "LOW"
        mult = 1 + min(1.0, a["churn"] / 10.0)
        lines.append(
            f"  [{tier:4}] {comp:12} {a['count']}d sev{a['worst']:.0f} churn{a['churn']} reopen{a['reopened']}   "
            f"score {a['score']:.1f} x (1 + {a['churn']}/10)={mult:.2f} = risk {risk:.1f}")
    return "\n".join(lines)


def select_regression_tests(threshold=4.0):
    rf = STATE / "risk.json"
    if not rf.exists():
        return "ERROR: run score_risk first."
    risks = {r["component"]: r["risk"] for r in json.loads(rf.read_text())}
    suite = list_test_suite()
    high = {c for c, r in risks.items() if r >= threshold}
    selected = sorted(t for t, comp in suite.items() if comp in high)
    skipped = sorted(t for t, comp in suite.items() if comp not in high)
    (STATE / "selected.json").write_text(json.dumps(selected))
    lines = [f"Risk threshold >= {threshold}. High-risk components: {', '.join(sorted(high)) or '(none)'}",
             f"SELECTED {len(selected)} of {len(suite)} regression tests:"]
    lines += [f"  RUN  {t}   (covers {suite[t]}, risk={risks.get(suite[t],0):.1f})" for t in selected]
    lines += [f"  skip {t}   (covers {suite[t]}, low risk)" for t in skipped]
    lines.append(efficiency_line(selected, len(suite)))
    return "\n".join(lines)


# ---- tool wiring (Flow 1) -----------------------------------------------------
TOOL_IMPL = {
    "read_defect_sources": read_defect_sources,
    "summarize_defects": summarize_defects,
    "score_risk": score_risk,
    "select_regression_tests": select_regression_tests,
    "report_bug_to_jira": report_bug_to_jira,
    **GENERIC_IMPL,
}

TOOLS = [
    {"name": "read_defect_sources", "description": "Pull and normalize defects from all sources (Jira export, defect CSV, git churn), filtered to the recent lookback window. Call first.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "summarize_defects", "description": "Group loaded defects by component/feature: what broke and where.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "score_risk", "description": "Rank components by risk = severity x count x recency x (1 + churn).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "select_regression_tests", "description": "Select the regression tests covering high-risk components. Optional threshold (default 4.0).", "input_schema": {"type": "object", "properties": {"threshold": {"type": "number"}}}},
    REPORT_TOOL,
] + GENERIC_TOOLS

SYSTEM = (
    "You are a risk-based regression selection agent for an SDET team testing a "
    "Swag Labs style store (login, inventory, cart, checkout, search, payments). The "
    "app has been in production for months with many logged and fixed defects; QA "
    "cannot re-run the whole suite each release. Decide which regression tests are "
    "critical NOW from the DEFECT HISTORY.\n\n"
    "Order of work:\n"
    "  1. read_defect_sources\n  2. summarize_defects\n  3. score_risk\n"
    "  4. select_regression_tests\n  5. run_pytest on ONLY the selected subset\n"
    "If a selected test fails because the SOURCE is buggy: (a) call report_bug_to_jira "
    "to file the defect and assign it to the developer/BA, then (b) read src/swaglabs.py, "
    "fix the bug with write_file (never weaken the test), and re-run until the selected "
    "suite passes. Finish with a short release-readiness summary: highest-risk "
    "components, tests run vs skipped, any Jira bugs filed, and the final result. Then STOP."
)

DEFAULT_TASK = (
    "Our Swag Labs store has been in production about six months. Read the logged "
    "and fixed defects from all sources, tell me what broke and in which components, "
    "rank components by risk, then select and run ONLY the regression tests that are "
    "critical given that risk. If a selected test fails because src/swaglabs.py is "
    "buggy, fix the source (not the test) and re-run until the selected suite is "
    "green. Finish with a release-readiness summary."
)


def run(task=None, max_steps=16):
    run_agent(task or DEFAULT_TASK, TOOLS, TOOL_IMPL, SYSTEM, max_steps=max_steps)
