"""agent/requirements.py — every requirement from the post-demo review, with live status.

This is the single source of truth for "where are we". Each of the 21 items from
Regression_PoC_Next_Tasks.md carries:

    state     DONE / PARTIAL / PLACEHOLDER / BLOCKED
    command   the thing you run to see it work (so no claim is unverifiable)
    note      what it does
    gap       what is still missing, and why — in plain words

    python run_poc.py --status            # the matrix
    python run_poc.py --status --gaps     # only what is not finished

Keeping this beside the code rather than in a document means it cannot quietly
drift out of date: `--verify` actually executes the listed commands.
"""
from .status import DONE, PARTIAL, PLACEHOLDER, BLOCKED

# phase -> [items]
REQUIREMENTS = [
    # ---------------- Phase 1 --------------------------------------------------
    {"id": 1, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Reopened defects raise the risk score",
     "command": "python run_poc.py --demo",
     "note": "REOPEN_MULT=1.6 in flow1; a reopened defect counts 60% more.",
     "gap": ""},

    {"id": 2, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Efficiency numbers: tests avoided, % of suite cut",
     "command": "python run_poc.py --demo",
     "note": "efficiency_line() prints ran / avoided / % for each flow.",
     "gap": ""},

    {"id": 3, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Agent explains how it weighted each choice",
     "command": "python run_poc.py --demo",
     "note": "score_risk / score_impact print the full arithmetic per component.",
     "gap": ""},

    {"id": 4, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Fixed evaluation set, re-run after any change",
     "command": "python run_poc.py --eval",
     "note": "eval/expected.json; guards against silent drift.",
     "gap": ""},

    {"id": 5, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Data-quality check on test-to-component mappings",
     "command": "python run_poc.py --check-data",
     "note": "Runs before selection; surfaces malformed or missing mappings.",
     "gap": ""},

    {"id": 6, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Defined human approval gates",
     "command": "python run_poc.py --gates",
     "note": "Four gates, default CLOSED. Now enforced on the LIVE flows too, "
             "not only the scripted demo.",
     "gap": ""},

    {"id": 7, "phase": "Phase 1 · quick wins", "state": DONE,
     "title": "Auto test-fixes open a PR, never commit to main",
     "command": "python run_poc.py --gates",
     "note": "Live flows route every test write through pr_flow; the model "
             "cannot write a test file directly any more.",
     "gap": ""},

    # ---------------- Phase 2 --------------------------------------------------
    {"id": 8, "phase": "Phase 2 · evaluation and trust", "state": DONE,
     "title": "Benchmark against a real open-source project",
     "command": "python run_poc.py --benchmark",
     "note": "networkx 3.6.1 (BSD-3-Clause), 16 seeded defects, ground truth "
             "built by EXECUTION over 2,501 real tests.",
     "gap": "Not Defects4J: no outbound network here (github/gitlab/pypi refused) "
            "and it needs Java 11 + Perl. eval/adapt_defects4j.py is written, so "
            "moving to it is a CSV swap with no code change."},

    {"id": 9, "phase": "Phase 2 · evaluation and trust", "state": PLACEHOLDER,
     "title": "Compare agent selection against human choices",
     "command": "python run_poc.py --compare-human",
     "note": "Scores BOTH sides against executed ground truth, so it reports who "
             "was right rather than only how much they overlapped.",
     "gap": "eval/human_selected.json holds INVENTED labels. Needs a real session: "
            "show a QA engineer the bug/component/kind columns WITHOUT "
            "tests_trigger, record their picks. Do not quote any human-vs-agent "
            "number until then."},

    {"id": 10, "phase": "Phase 2 · evaluation and trust", "state": DONE,
     "title": "Accuracy numbers",
     "command": "python run_poc.py --benchmark --per-bug",
     "note": "declared map 45.6% recall / 99% cut; measured dependency map "
             "100% recall / 47% cut. Recall is the metric that matters.",
     "gap": "16 seeded defects is a small sample — direction is solid, but do not "
            "quote the percentages as the agent's general accuracy."},

    {"id": 11, "phase": "Phase 2 · evaluation and trust", "state": DONE,
     "title": "Flag risk areas with no test",
     "command": "python run_poc.py --coverage",
     "note": "UNCOVERED / THIN / UNDETECTED, worst first. UNDETECTED is executed "
             "proof: real changes that the whole suite still passes.",
     "gap": ""},

    # ---------------- Phase 3 --------------------------------------------------
    {"id": 12, "phase": "Phase 3 · later improvements", "state": PLACEHOLDER,
     "title": "Weight business-important features above low-usage ones",
     "command": "python run_poc.py --signals",
     "note": "Business multiplier wired into BOTH risk and impact scoring and "
             "shown in the arithmetic.",
     "gap": "data/business_value.csv is INVENTED. Real source: product owner's "
            "criticality rating plus usage from analytics (sessions or revenue "
            "per feature over the last quarter)."},

    {"id": 13, "phase": "Phase 3 · later improvements", "state": PARTIAL,
     "title": "Architectural risk: interfaces, boundaries, defect clustering",
     "command": "python run_poc.py --arch",
     "note": "Fan-in / fan-out and defect clustering computed from a real import "
             "graph. Runs for real against the networkx benchmark project.",
     "gap": "Cannot run against the demo product: src/swaglabs.py is a single "
            "module, so it has no internal boundaries to measure. Point --arch at "
            "a real multi-module repo to get product numbers."},

    {"id": 14, "phase": "Phase 3 · later improvements", "state": PLACEHOLDER,
     "title": "Sprint history and root-cause notes as risk signals",
     "command": "python run_poc.py --signals",
     "note": "Both signals load, score and feed the risk model.",
     "gap": "data/sprint_history.csv and data/rca_notes.csv are INVENTED. Real "
            "source: Jira sprint reports (carry-over and spillover per component) "
            "and the RCA field on closed defects."},

    {"id": 15, "phase": "Phase 3 · later improvements", "state": DONE,
     "title": "Feed self-heal decisions and human reviews back in",
     "command": "python run_poc.py --feedback",
     "note": "Every self-heal outcome and approval decision is recorded, and the "
             "accumulated record adjusts each component's weight on later runs. "
             "Learns from real demo decisions.",
     "gap": "Adjustment is deliberately capped at ±30% so a short history cannot "
            "swamp the defect signal. Revisit the cap once there is real history."},

    {"id": 16, "phase": "Phase 3 · later improvements", "state": DONE,
     "title": "Smoke check on every pull request from change signals",
     "command": "python run_poc.py --pr-check",
     "note": "Maps a real git diff to components, picks a bounded smoke subset, "
             "runs it. Falls back to the staged release delta outside a repo.",
     "gap": ""},

    {"id": 17, "phase": "Phase 3 · later improvements", "state": DONE,
     "title": "Different schedules: quarterly, sprint, daily, per PR",
     "command": "python run_poc.py --schedule sprint",
     "note": "Each profile sets its own lookback window, threshold and budget; "
             "the selection genuinely changes between them.",
     "gap": ""},

    # ---------------- Deck -----------------------------------------------------
    {"id": 18, "phase": "Deck", "state": DONE,
     "title": "Metrics slide: efficiency and accuracy",
     "command": "python run_poc.py --deck-status",
     "note": "Accuracy tile now filled from the real benchmark run.",
     "gap": ""},

    {"id": 19, "phase": "Deck", "state": DONE,
     "title": "Evaluation slide: benchmark and human-vs-agent",
     "command": "python run_poc.py --deck-status",
     "note": "Added, and marked on-slide that the human comparison is pending "
             "real labels.",
     "gap": ""},

    {"id": 20, "phase": "Deck", "state": DONE,
     "title": "Roadmap slide of future risk signals",
     "command": "python run_poc.py --deck-status",
     "note": "Reopened defects, business impact, architecture, sprint/RCA — each "
             "marked live or placeholder to match the code.",
     "gap": ""},

    {"id": 21, "phase": "Deck", "state": DONE,
     "title": "Slide on when it runs",
     "command": "python run_poc.py --deck-status",
     "note": "Quarterly / sprint / daily / per-PR, matching --schedule.",
     "gap": ""},
]


def by_state(state):
    return [r for r in REQUIREMENTS if r["state"] == state]


def phases():
    out = []
    for r in REQUIREMENTS:
        if r["phase"] not in out:
            out.append(r["phase"])
    return out


def counts():
    c = {}
    for r in REQUIREMENTS:
        c[r["state"]] = c.get(r["state"], 0) + 1
    return c
