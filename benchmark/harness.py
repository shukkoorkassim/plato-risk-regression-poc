"""benchmark/harness.py — build ground truth by EXECUTION against real OSS code.

For every seeded bug in benchmark/nx_bugs.py:
    1. patch the networkx WORKING COPY (never the installed package),
    2. run the in-scope suite,
    3. record which tests actually failed  -> tests.trigger (the ground truth),
    4. restore the file.

Nothing is hand-asserted: the "should-run" set is whatever really went red in a
real project's real test suite.

Output is the same CSV shape Defects4J's `query` emits, so eval/benchmark_d4j.py
runs unchanged on this corpus or on a real Defects4J export.

    python run_poc.py --build-truth           # ~6 minutes, 16 bugs
    python -m benchmark.harness --bug NX-4    # one bug, verbose
"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "ground_truth.csv"

sys.path.insert(0, str(ROOT))
from benchmark import nx_project, nx_impact           # noqa: E402
from benchmark.nx_bugs import BUGS, validate          # noqa: E402

FAIL_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)")


class PatchFailed(RuntimeError):
    pass


def _apply(bug):
    """Patch the working copy. Returns (path, original_text)."""
    target = nx_project.workdir().parent / bug["module"]
    original = target.read_text(encoding="utf-8")
    if original.count(bug["old"]) != 1:
        raise PatchFailed(f"{bug['id']}: pattern not unique in {bug['module']}")
    target.write_text(original.replace(bug["old"], bug["new"], 1), encoding="utf-8")
    return target, original


def _purge_bytecode():
    """Drop cached .pyc in the working copy.

    Several mutations are the same length as the original and are written within
    the same second; CPython keys .pyc validity on (mtime, size), so a stale
    cache can survive the restore and silently corrupt every later bug. The
    subprocess also runs with PYTHONDONTWRITEBYTECODE=1.
    """
    for cache in nx_project.workdir().rglob("__pycache__"):
        for pyc in cache.glob("*.pyc"):
            pyc.unlink(missing_ok=True)


#: A healthy run of the in-scope suite takes ~21s. Some defects don't make tests
#: fail, they make them never finish — NX-4 (has_edge true for any node pair)
#: sends the generators into runaway graph construction. A hang is a real
#: detection in CI, but it yields no failure list, so it is recorded as its own
#: outcome and kept out of the recall average rather than silently scored as 0.
SUITE_TIMEOUT = 150


class SuiteHung(RuntimeError):
    pass


def _run_suite(timeout=SUITE_TIMEOUT):
    """Run the in-scope suite; return (failing_test_files, failing_node_ids, summary)."""
    _purge_bytecode()
    cmd = [sys.executable, "-m", "pytest", *nx_project.scope_paths(),
           "-q", "--no-header", "--tb=no", "-rfE", "-p", "no:cacheprovider"]
    try:
        proc = subprocess.run(cmd, env=nx_project.env(), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SuiteHung(f"suite did not finish within {timeout}s")
    out = proc.stdout or ""
    nodes = []
    for line in out.splitlines():
        m = FAIL_RE.match(line.strip())
        if m:
            nodes.append(m.group(1))
    files = sorted({nx_project.rel(n.split("::")[0]) for n in nodes})
    summary = (out.strip().splitlines() or [""])[-1]
    return files, sorted(nodes), summary


def baseline():
    files, nodes, summary = _run_suite()
    return {"files": files, "nodes": nodes, "summary": summary}


def run_one(bug, verbose=False):
    """Returns (files, nodes, hung). On a hang, files/nodes are empty."""
    target, original = _apply(bug)
    hung = False
    try:
        try:
            files, nodes, summary = _run_suite()
        except SuiteHung as exc:
            files, nodes, summary, hung = [], [], str(exc), True
    finally:
        target.write_text(original, encoding="utf-8")
        _purge_bytecode()
        # a hang leaves orphaned pytest workers holding the working copy open
        subprocess.run(["pkill", "-f", "pytest.*risk-agent-benchmark"],
                       capture_output=True)
    if verbose:
        print(f"  {bug['id']}  {summary}")
        for n in nodes[:25]:
            print(f"      {nx_project.rel(n)}")
        if len(nodes) > 25:
            print(f"      ... and {len(nodes) - 25} more")
    return files, nodes, hung


def build(verbose=False):
    print(f"Ground truth by execution — {nx_project.describe()}\n")
    try:
        nx_project.ensure_workdir()
    except RuntimeError as exc:
        # Rebuilding ground truth means executing networkx's real test suite, so
        # the library has to be present. Reading the results does NOT — that is
        # just benchmark/ground_truth.csv — so say which is which rather than
        # dying on an import traceback.
        from agent import status as S
        S.blocked("rebuilding the ground truth", str(exc))
        print("\n  To re-run the experiment here:  pip install networkx pytest")
        print("  To just READ the existing results, nothing extra is needed:")
        print("      python run_poc.py --benchmark")
        print("      python run_poc.py --compare-human")
        sys.exit(1)

    ok, problems = validate()
    if not ok:
        # Usually means a previous run was interrupted before it could restore a
        # patched file, leaving the working copy dirty. Re-clone from the
        # installed package and try once more before giving up.
        print("  working copy looks dirty — re-cloning from the installed package")
        nx_project.ensure_workdir(force=True)
        ok, problems = validate()
    if not ok:
        print("  corpus is invalid:")
        for p in problems:
            print(f"    {p}")
        sys.exit(1)

    impact_map = nx_impact.load()
    if not impact_map:
        print("  building the module -> tests map first (one-off)...")
        impact_map = nx_impact.build()
        print()

    base = baseline()
    if base["files"]:
        print(f"  ABORT: the suite is not green before seeding "
              f"({len(base['nodes'])} failing).")
        for n in base["nodes"][:10]:
            print(f"    {n}")
        sys.exit(1)
    print(f"  baseline: {base['summary']}\n")

    rows, undetected, hangs = [], [], []
    for i, bug in enumerate(BUGS, 1):
        files, nodes, hung = run_one(bug, verbose=verbose)
        relevant = nx_impact.tests_touching(bug["module"], impact_map)
        if hung:
            hangs.append(bug["id"])
        elif not files:
            undetected.append(bug["id"])
        rows.append({
            "bug_id": bug["id"],
            "component": nx_project.component_of_module(bug["module"]),
            "classes_modified": bug["module"],
            "kind": bug["kind"],
            "outcome": "hang" if hung else ("undetected" if not files else "detected"),
            "tests_trigger": ";".join(files),
            "tests_trigger_cases": ";".join(nx_project.rel(n) for n in nodes),
            "tests_relevant": ";".join(relevant),
            "n_trigger_cases": len(nodes),
        })
        if hung:
            flag = f"   (SUITE HANGS — detected, no failure list)"
        elif not files:
            flag = "   (NO TEST DETECTS THIS)"
        else:
            flag = ""
        print(f"  [{i:2}/{len(BUGS)}] {bug['id']:6} {bug['kind']:20} "
              f"{len(nodes):5} cases in {len(files):3} files{flag}")

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n  wrote {len(rows)} bugs -> benchmark/{OUT.name}")
    if undetected:
        print(f"  {len(undetected)} bug(s) no in-scope test detects: {', '.join(undetected)}")
    if hangs:
        print(f"  {len(hangs)} bug(s) hang the suite instead of failing it: "
              f"{', '.join(hangs)} — detected in CI, but scored separately.")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Build executed ground truth from real OSS code")
    ap.add_argument("--bug", help="run a single bug verbosely")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    nx_project.ensure_workdir()
    if args.bug:
        from benchmark.nx_bugs import by_id
        b = by_id(args.bug)
        print(f"{b['id']} — {b['kind']} in {b['module']}\n  {b['note']}\n")
        run_one(b, verbose=True)
        return
    build(verbose=args.verbose)


if __name__ == "__main__":
    main()
