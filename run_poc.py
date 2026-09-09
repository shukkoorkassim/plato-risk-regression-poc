"""
run_poc.py — one entry point for the whole POC.

    python run_poc.py --dry-run            # both flows, deterministic, no API key
    python run_poc.py --flow 1             # live Flow 1 agent (self-heals checkout)
    python run_poc.py --flow 2             # live Flow 2 agent (self-heals payments)
    python run_poc.py --flow both          # both live agents, back to back
    python run_poc.py --reset              # re-plant the bugs + clear agent state

Add a quoted task to override the built-in one, e.g.:
    python run_poc.py --flow 1 "Only look at the last 90 days of defects."
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.common import C           # noqa: E402


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
    ap.add_argument("task", nargs="?", help="optional task override for a single flow")
    args = ap.parse_args()

    if args.reset:
        _reset()
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
