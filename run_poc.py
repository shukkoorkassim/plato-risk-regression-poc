"""
run_poc.py — one entry point for the whole POC.

    python run_poc.py --selftest           # ONE command: is everything working here?
    python run_poc.py --showcase           # the presentation: 10 phases, offline
    python run_poc.py --demo               # the live run: real pytest, real Jira defect

    python run_poc.py --dry-run            # both flows, deterministic, no API key
    python run_poc.py --flow 1             # live Flow 1 agent (self-heals checkout)
    python run_poc.py --flow 2             # live Flow 2 agent (self-heals payments)
    python run_poc.py --flow both          # both live agents, back to back
    python run_poc.py --reset              # re-plant the bugs + clear agent state

Phase 2 — evaluation and trust:
    python run_poc.py --build-truth        # rebuild ground truth by executing the suite per bug
    python run_poc.py --benchmark          # accuracy: recall / precision / F1 / agreement
    python run_poc.py --benchmark --per-bug
    python run_poc.py --compare-human      # agent vs human selection
    python run_poc.py --coverage           # risk areas with no test

Add a quoted task to override the built-in one, e.g.:
    python run_poc.py --flow 1 "Only look at the last 90 days of defects."
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# --threshold has to be honoured BEFORE agent.common is imported, because the
# shared THRESHOLD constant is resolved at import time. argparse runs too late,
# so the flag is lifted out of sys.argv here and handed over as an env var —
# the same channel RISK_THRESHOLD in .env uses.
import os                            # noqa: E402
for _i, _a in enumerate(sys.argv):
    if _a == "--threshold" and _i + 1 < len(sys.argv):
        os.environ["RISK_THRESHOLD"] = sys.argv[_i + 1]
    elif _a.startswith("--threshold="):
        os.environ["RISK_THRESHOLD"] = _a.split("=", 1)[1]

from agent.common import C, THRESHOLD   # noqa: E402


def _reset():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "reset_demo", str(Path(__file__).resolve().parent / "scripts" / "reset_demo.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.reset()


def main():
    ap = argparse.ArgumentParser(description="Plato risk-based regression POC")
    ap.add_argument("--flow", choices=["1", "2", "both", "combined"], help="which live agent flow to run")
    ap.add_argument("--dry-run", action="store_true", help="deterministic pipeline, no API key")
    ap.add_argument("--report", action="store_true", help="combined ranked/selected/filtered/executed report for both flows")
    ap.add_argument("--reset", action="store_true", help="re-plant bugs and clear agent state")
    ap.add_argument("--demo", action="store_true", help="deterministic two-path self-heal demo: fix a stale test, file an app defect")
    ap.add_argument("--eval", action="store_true", help="run the fixed evaluation set (expected vs actual selection)")
    ap.add_argument("--check-data", action="store_true", help="run the data-quality / coverage check")
    # ---- Phase 2 ----
    ap.add_argument("--benchmark", action="store_true",
                    help="accuracy benchmark vs executed ground truth (items 9, 10)")
    ap.add_argument("--build-truth", action="store_true",
                    help="rebuild the benchmark ground truth by running the suite per seeded bug (item 8)")
    ap.add_argument("--compare-human", action="store_true",
                    help="compare the agent's selection against human labels (item 9)")
    ap.add_argument("--coverage", action="store_true",
                    help="coverage-gap report: risk areas with no test (item 11)")
    ap.add_argument("--csv", help="corpus for --benchmark / --compare-human (default: bundled)")
    ap.add_argument("--human", help="human labels for --compare-human (default: eval/human_selected.json)")
    # ---- Phase 3 + governance + status ----
    ap.add_argument("--status", action="store_true",
                    help="status of all 21 requirements from the review")
    ap.add_argument("--gaps", action="store_true", help="with --status: only unfinished items")
    ap.add_argument("--verify", action="store_true",
                    help="run the command behind every requirement and report pass/fail")
    ap.add_argument("--gates", action="store_true",
                    help="governance controls: approval gates + write policy (items 6, 7)")
    ap.add_argument("--signals", action="store_true",
                    help="Phase 3 risk signals: business, sprint, RCA, feedback (12, 14, 15)")
    ap.add_argument("--arch", action="store_true",
                    help="architectural risk: fan-in/out, boundaries, clustering (item 13)")
    ap.add_argument("--path", help="package directory for --arch")
    ap.add_argument("--feedback", action="store_true",
                    help="show what past runs and reviews taught the agent (item 15)")
    ap.add_argument("--feedback-demo", action="store_true",
                    help="seed the feedback store with a worked example (item 15)")
    ap.add_argument("--pr-check", action="store_true",
                    help="fast smoke check for a pull request (item 16)")
    ap.add_argument("--base", help="git ref to diff against for --pr-check")
    ap.add_argument("--schedule", choices=["pr", "daily", "sprint", "quarterly"],
                    help="run under a schedule profile (item 17)")
    ap.add_argument("--schedules", action="store_true",
                    help="compare all run schedules side by side (item 17 / slide 21)")
    ap.add_argument("--showcase", action="store_true",
                    help="the whole story in the console: 10 phases, no API key needed")
    ap.add_argument("--pace", type=float, default=0.0,
                    help="--showcase: seconds between beats, for presenting (try 1.0)")
    ap.add_argument("--ascii", action="store_true",
                    help="--showcase: plain characters for older consoles")
    ap.add_argument("--deck-status", action="store_true",
                    help="what the deck says vs what the code does (items 18-21)")
    ap.add_argument("--selftest", action="store_true",
                    help="ONE command: check everything on this machine, live Jira included")
    ap.add_argument("--threshold", type=float, metavar="N",
                    help=f"selection cut-off for risk and impact (default {THRESHOLD:.1f}; "
                         f"also settable as RISK_THRESHOLD in .env)")
    ap.add_argument("--per-bug", action="store_true", help="per-bug table for --benchmark")
    ap.add_argument("task", nargs="?", help="optional task override for a single flow")
    args = ap.parse_args()

    if args.reset:
        _reset()
        return

    # ---- status / governance / Phase 3 ---------------------------------------
    if args.selftest:
        from agent.selftest import run as selftest_run
        raise SystemExit(0 if selftest_run() else 1)

    if args.status:
        from agent.status_report import render
        render(gaps_only=args.gaps)
        return

    if args.verify:
        from agent.status_report import verify
        raise SystemExit(0 if verify() else 1)

    if args.gates:
        from agent.guarded_tools import report as gates_report
        gates_report()
        return

    if args.signals:
        from agent.signals import report as signals_report
        signals_report()
        return

    if args.arch:
        from agent.arch_risk import report as arch_report
        from agent import flow1_defect_history as _f1
        _f1.read_defect_sources()          # so defect clustering has data
        arch_report(args.path)
        return

    if args.feedback_demo:
        from agent.feedback_demo import seed
        seed()
        return

    if args.feedback:
        from agent.feedback_demo import report as fb_report
        fb_report()
        return

    if args.pr_check:
        from agent.pr_check import run as pr_run
        pr_run(args.base)
        return

    if args.schedules:
        from agent.schedules import compare
        compare()
        return

    if args.schedule:
        from agent.schedules import run as sched_run
        sched_run(args.schedule)
        return

    if args.showcase:
        from agent.showcase import run as showcase_run
        showcase_run(pace=args.pace, ascii_only=args.ascii)
        return

    if args.deck_status:
        from agent.deck_status import report as deck_report
        deck_report()
        return

    if args.demo:
        import demo_selfheal
        demo_selfheal.main()
        return

    if args.eval:
        import subprocess
        raise SystemExit(subprocess.run([sys.executable, str(Path(__file__).resolve().parent/'eval'/'run_eval.py')]).returncode)

    if args.check_data:
        from agent import flow1_defect_history as _f1, flow2_change_driven as _f2
        from agent.data_quality import check_data_quality
        _f1.read_defect_sources(); _f2.read_release_delta()
        print(check_data_quality()[1])
        return

    # ---- Phase 2 -------------------------------------------------------------
    if args.build_truth:
        from benchmark import harness
        harness.build()
        return

    if args.benchmark:
        from eval import benchmark_d4j
        csv_path = Path(args.csv) if args.csv else benchmark_d4j.DEFAULT_CSV
        if not Path(csv_path).exists():
            print(f"{C.YELLOW}No corpus yet — building it first "
                  f"(python run_poc.py --build-truth){C.RESET}\n")
            from benchmark import harness
            harness.build()
        benchmark_d4j.report(csv_path, show_per_bug=args.per_bug)
        return

    if args.compare_human:
        from eval import compare_human, benchmark_d4j
        compare_human.compare(Path(args.human) if args.human else compare_human.HUMAN,
                              Path(args.csv) if args.csv else benchmark_d4j.DEFAULT_CSV)
        return

    if args.coverage:
        from agent import flow1_defect_history as _f1, flow2_change_driven as _f2
        from agent.coverage_gap import coverage_report
        # populate risk.json / impact.json so gaps can be ranked by real scores
        _f1.read_defect_sources(); _f1.score_risk()
        _f2.read_release_delta(); _f2.score_impact()
        print(coverage_report()[1])
        return

    if args.report:
        import report
        report.build()
        return

    if args.dry_run:
        import dry_run
        dry_run.dry_flow1()
        dry_run.dry_flow2()
        return

    if not args.flow:
        ap.print_help()
        print(f"\n{C.YELLOW}Tip: start with  python run_poc.py --dry-run{C.RESET}")
        return

    from agent import flow1_defect_history as flow1
    from agent import flow2_change_driven as flow2

    if args.flow == "combined":
        import combined_agent
        print(f"{C.BOLD}COMBINED · defect-history + change driven{C.RESET}")
        combined_agent.run(args.task)
        return

    if args.flow in ("1", "both"):
        print(f"{C.BOLD}FLOW 1 · defect-history driven{C.RESET}")
        flow1.run(args.task if args.flow == "1" else None)
    if args.flow in ("2", "both"):
        print(f"\n{C.BOLD}FLOW 2 · change driven{C.RESET}")
        flow2.run(args.task if args.flow == "2" else None)


if __name__ == "__main__":
    main()
