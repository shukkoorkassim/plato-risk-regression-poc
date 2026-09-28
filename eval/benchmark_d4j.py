"""eval/benchmark_d4j.py — accuracy benchmark (Phase 2 · items 9, 10).

Reads a Defects4J-shaped CSV, replays the agent's change-driven selection for
every bug, and scores the prediction against the tests that actually catch it.

    python run_poc.py --benchmark                    # the networkx corpus
    python run_poc.py --benchmark --csv <file.csv>   # a real Defects4J export

The default corpus is 16 defects seeded into networkx 3.6.1, with ground truth
built by EXECUTION (benchmark/harness.py). The script itself is corpus-agnostic:
it only needs these columns, which is exactly what
`defects4j query -p Lang -q "classes.modified,tests.trigger,tests.relevant"`
gives you, plus a component column eval/adapt_defects4j.py fills in:

    bug_id, component, classes_modified, tests_trigger, tests_relevant

Metrics, per bug and overall:
    recall     of the tests that catch the bug, how many did we select?
               This is the one that matters — a miss is a bug shipped.
    precision  of the tests we selected, how many were needed?
    F1         harmonic mean of the two
    agreement  fraction of bugs where recall was 1.0 (we caught it completely)
    reduction  how much of the suite we skipped

Two selection strategies are compared, because the difference IS the finding:
    declared  the test_map.json convention — one test file per changed module.
    impact    the same, widened by a measured dependency map (tests.relevant):
              also run the tests that actually execute the changed code.

On the networkx corpus `declared` scores 45.6% recall while cutting 99% of the
suite, and `impact` scores 100% while cutting 47%. The lesson is that suite
reduction is the wrong headline: a 99% saving that misses the test which catches
the bug has not saved anything. See docs/BENCHMARK.md.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.common import C  # noqa: E402

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "benchmark" / "ground_truth.csv"


def _split(cell):
    return [x for x in (cell or "").split(";") if x.strip()]


def load_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def all_tests(rows):
    """The full suite the selector is choosing from.

    Prefer the measured set of in-scope test files (every file the traced run
    saw), because the suite-reduction figure is only honest against the real
    suite size. Fall back to whatever the corpus mentions — which is what a raw
    Defects4J export gives us.
    """
    try:
        from benchmark import nx_impact
        measured = set(nx_impact.load())
        if measured:
            return sorted(measured)
    except Exception:  # noqa: BLE001 — corpus may not be the networkx one
        pass
    suite = set()
    for r in rows:
        suite |= set(_split(r["tests_trigger"])) | set(_split(r["tests_relevant"]))
    return sorted(suite)


# ---- the two selection strategies ---------------------------------------------
def select_declared(row, suite):
    """One test file per changed module — the convention the PoC ships with.

    test_map.json maps each test file to exactly one component, so a change in
    component X selects the test file named after X. networkx follows the same
    convention (classes/graph.py <-> classes/tests/test_graph.py), which is what
    makes it a fair baseline to measure rather than a straw man.
    """
    stem = Path(row["classes_modified"]).stem
    return sorted(t for t in suite if Path(t).stem == f"test_{stem}")


def select_impact(row, suite):
    """Widen the declared selection with the measured dependency map.

    tests_relevant answers "which tests actually execute the modified module".
    For the networkx corpus that is measured by tracing a real run (see
    benchmark/nx_impact.py); for a Defects4J export it is the shipped
    tests.relevant column. Either way it means a change in a low-level module
    also pulls in the higher-level tests that depend on it.
    """
    declared = set(select_declared(row, suite))
    return sorted(declared | set(_split(row["tests_relevant"])))


STRATEGIES = {
    "declared": ("declared map — one test file per changed module", select_declared),
    "impact": ("declared + measured dependency map (tests.relevant)", select_impact),
}


# ---- scoring -------------------------------------------------------------------
def score(predicted, truth):
    p, t = set(predicted), set(truth)
    hit = len(p & t)
    recall = hit / len(t) if t else None          # undefined when no test catches it
    precision = hit / len(p) if p else 0.0
    if recall is None:
        f1 = None
    elif recall + precision == 0:
        f1 = 0.0
    else:
        f1 = 2 * recall * precision / (recall + precision)
    return recall, precision, f1


def evaluate(rows, strategy, suite):
    _, fn = STRATEGIES[strategy]
    per_bug, scored, missed_bugs, undetectable, hung = [], [], [], [], []
    for r in rows:
        truth = _split(r["tests_trigger"])
        pred = fn(r, suite)
        recall, precision, f1 = score(pred, truth)
        outcome = r.get("outcome") or ("undetected" if not truth else "detected")
        rec = {"bug_id": r["bug_id"], "component": r["component"],
               "kind": r.get("kind", ""), "n_selected": len(pred),
               "n_truth": len(truth), "recall": recall,
               "precision": precision, "f1": f1, "outcome": outcome,
               "missed": sorted(set(truth) - set(pred))}
        per_bug.append(rec)
        if recall is None:
            # No failure list to score against: either no test catches it, or
            # it hangs the suite. Both are real outcomes but neither is a
            # selection error, so they are reported apart from the averages.
            (hung if outcome == "hang" else undetectable).append(r["bug_id"])
            continue
        scored.append(rec)
        if recall < 1.0:
            missed_bugs.append(rec)
    n = len(scored) or 1
    summary = {
        "strategy": strategy,
        "bugs_total": len(rows),
        "bugs_scored": len(scored),
        "bugs_undetectable": undetectable,
        "bugs_hung": hung,
        "recall": sum(b["recall"] for b in scored) / n,
        "precision": sum(b["precision"] for b in scored) / n,
        "f1": sum(b["f1"] for b in scored) / n,
        "agreement": sum(1 for b in scored if b["recall"] == 1.0) / n,
        "avg_selected": sum(b["n_selected"] for b in scored) / n,
        "suite_size": len(suite),
        "missed": missed_bugs,
    }
    summary["reduction"] = 1 - summary["avg_selected"] / len(suite) if suite else 0.0
    return summary, per_bug


# ---- reporting -----------------------------------------------------------------
def _pct(x):
    return "   n/a" if x is None else f"{x * 100:5.1f}%"


def _tile(label, value, good):
    color = C.GREEN if good else (C.YELLOW if value >= 0.75 else C.RED)
    return f"{label} {color}{C.BOLD}{value * 100:.1f}%{C.RESET}"


def report(csv_path, show_per_bug=False):
    rows = load_rows(csv_path)
    suite = all_tests(rows)
    print(f"{C.BOLD}Accuracy benchmark{C.RESET}  ·  {len(rows)} bugs  ·  "
          f"suite of {len(suite)} test files  ·  {Path(csv_path).name}")
    print(f"{C.GREY}Ground truth = the tests that actually fail on each bug "
          f"(executed, not assumed).{C.RESET}\n")

    results = {}
    for name in ("declared", "impact"):
        label, _ = STRATEGIES[name]
        summary, per_bug = evaluate(rows, name, suite)
        results[name] = (summary, per_bug)

        print(f"  {C.BOLD}{name}{C.RESET} — {C.GREY}{label}{C.RESET}")
        print(f"    {_tile('recall   ', summary['recall'], summary['recall'] >= 0.95)}"
              f"   {C.GREY}of the tests that catch a bug, how many we ran{C.RESET}")
        print(f"    {_tile('precision', summary['precision'], summary['precision'] >= 0.5)}"
              f"   {C.GREY}of the tests we ran, how many were needed{C.RESET}")
        print(f"    {_tile('F1       ', summary['f1'], summary['f1'] >= 0.6)}")
        print(f"    {_tile('agreement', summary['agreement'], summary['agreement'] >= 0.95)}"
              f"   {C.GREY}bugs caught completely ({int(summary['agreement'] * summary['bugs_scored'])}"
              f"/{summary['bugs_scored']}){C.RESET}")
        print(f"    {C.CYAN}suite cut {summary['reduction'] * 100:.0f}%{C.RESET}"
              f"   {C.GREY}ran {summary['avg_selected']:.1f} of {len(suite)} test files on average{C.RESET}")
        if summary["missed"]:
            print(f"    {C.RED}missed {len(summary['missed'])} bug(s):{C.RESET}")
            for m in summary["missed"][:8]:
                names = [Path(x).name for x in m["missed"]]
                shown = ", ".join(names[:4])
                more = f" +{len(names) - 4} more" if len(names) > 4 else ""
                print(f"      {C.RED}x{C.RESET} {m['bug_id']:12} {m['kind']:22} "
                      f"recall {m['recall'] * 100:3.0f}%  missed {len(names):2}: {shown}{more}")
            if len(summary["missed"]) > 8:
                print(f"      {C.GREY}... and {len(summary['missed']) - 8} more{C.RESET}")
        print()

    # the headline comparison
    d, i = results["declared"][0], results["impact"][0]
    print(f"  {C.BOLD}Verdict{C.RESET}")
    print(f"    recall {d['recall'] * 100:.1f}% -> {C.GREEN}{i['recall'] * 100:.1f}%{C.RESET} "
          f"using the measured dependency map, at {i['reduction'] * 100:.0f}% suite "
          f"reduction (was {d['reduction'] * 100:.0f}%).")
    print(f"    {C.GREY}The declared map cuts more but catches less — 99% reduction is "
          f"worthless if it{C.RESET}")
    print(f"    {C.GREY}misses the test that finds the bug. Recall is the metric to hold "
          f"the agent to.{C.RESET}")
    caught = int(i["agreement"] * i["bugs_scored"]) - int(d["agreement"] * d["bugs_scored"])
    if caught > 0:
        print(f"    {C.GREEN}{caught} more bug(s) caught completely{C.RESET} — the declared "
              f"one-test-file-per-component map misses cross-component failures.")
    if d["bugs_undetectable"]:
        print(f"    {C.YELLOW}{len(d['bugs_undetectable'])} bug(s) no in-scope test detects"
              f"{C.RESET} {C.GREY}({', '.join(d['bugs_undetectable'])}) — "
              f"coverage holes, see  python run_poc.py --coverage{C.RESET}")
    if d["bugs_hung"]:
        print(f"    {C.YELLOW}{len(d['bugs_hung'])} bug(s) hang the suite rather than failing it"
              f"{C.RESET} {C.GREY}({', '.join(d['bugs_hung'])}) — caught by CI, "
              f"but they produce no failure list to score.{C.RESET}")

    if show_per_bug:
        print(f"\n  {C.BOLD}Per bug{C.RESET}  {C.GREY}(impact strategy){C.RESET}")
        print(f"    {'bug':12} {'component':22} {'kind':22} {'ran':>4} {'truth':>6} "
              f"{'recall':>7} {'prec':>7}")
        for b in results["impact"][1]:
            mark = C.GREY if b["recall"] is None else (C.GREEN if b["recall"] == 1.0 else C.RED)
            print(f"    {mark}{b['bug_id']:12}{C.RESET} {b['component']:22} {b['kind']:22} "
                  f"{b['n_selected']:>4} {b['n_truth']:>6} {_pct(b['recall']):>7} "
                  f"{_pct(b['precision']):>7}")

    out = Path(__file__).resolve().parent / "benchmark_results.json"
    out.write_text(json.dumps(
        {k: {kk: vv for kk, vv in v[0].items() if kk != "missed"} for k, v in results.items()},
        indent=2))
    print(f"\n  {C.GREY}summary written to eval/{out.name}{C.RESET}")
    return results


def main():
    ap = argparse.ArgumentParser(description="Risk-agent accuracy benchmark (items 9, 10)")
    ap.add_argument("--csv", default=str(DEFAULT_CSV),
                    help="Defects4J-shaped CSV (default: the bundled sample-app corpus)")
    ap.add_argument("--per-bug", action="store_true", help="show the per-bug table")
    args = ap.parse_args()
    path = Path(args.csv)
    if not path.exists():
        sys.exit(f"{C.RED}No corpus at {path}.{C.RESET}\n"
                 f"Build the bundled one with:  python -m benchmark.harness")
    report(path, show_per_bug=args.per_bug)


if __name__ == "__main__":
    main()
