"""
dry_run.py — see BOTH pipelines WITHOUT an Anthropic API key.

This calls the same deterministic tools the agents use (read -> summarize ->
score -> select -> run) directly, so you can verify each flow's selection and
watch the planted bug fail. It does NOT auto-fix the bugs — that self-healing
step is what the real agents (risk_agent.py / change_agent.py) do with the LLM.

    python dry_run.py            # both flows
    python dry_run.py 1          # Flow 1 only
    python dry_run.py 2          # Flow 2 only
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import flow1_defect_history as flow1   # noqa: E402
from agent import flow2_change_driven as flow2     # noqa: E402
from agent.common import run_pytest                # noqa: E402

BAR = "=" * 68


def show(title, text):
    print(f"\n{BAR}\n {title}\n{BAR}")
    print(text)


def dry_flow1():
    print(f"\n{'#'*68}\n# FLOW 1 · DEFECT-HISTORY DRIVEN  (what has broken before?)\n{'#'*68}")
    show("1. read_defect_sources", flow1.read_defect_sources())
    show("2. summarize_defects", flow1.summarize_defects())
    show("3. score_risk", flow1.score_risk())
    show("4. select_regression_tests", flow1.select_regression_tests())
    show("5. run_pytest (selected subset only)", run_pytest())
    print("\n  ^ checkout SHOULD fail — the planted tax bug in src/swaglabs.py.")
    print("    Run  python risk_agent.py  with an API key to watch the agent fix it.")


def dry_flow2():
    print(f"\n{'#'*68}\n# FLOW 2 · CHANGE DRIVEN  (what just changed?)\n{'#'*68}")
    show("1. read_release_delta", flow2.read_release_delta())
    show("2. summarize_changes", flow2.summarize_changes())
    show("3. score_impact", flow2.score_impact())
    show("4. select_change_tests", flow2.select_change_tests())
    show("5. run_pytest (selected subset only)", run_pytest())
    print("\n  ^ payments SHOULD fail — the planted promo/tax bug in src/swaglabs.py.")
    print("    Run  python change_agent.py  with an API key to watch the agent fix it.")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("1", "flow1"):
        dry_flow1()
    elif which in ("2", "flow2"):
        dry_flow2()
    else:
        dry_flow1()
        dry_flow2()
    print(f"\n{BAR}\n Done. The agents (risk_agent.py / change_agent.py) add the self-heal step.\n{BAR}")
