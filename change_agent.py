"""
change_agent.py — FLOW 2 entry point (change driven).

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...        # or put it in .env
    python change_agent.py                      # uses the built-in task
    python change_agent.py "your own task here" # or give it any task

No API key? See the deterministic pipeline with:  python dry_run.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.common import C          # noqa: E402
from agent import flow2_change_driven as flow2   # noqa: E402


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"{C.BOLD}FLOW 2 · change driven{C.RESET}")
    print(f"{C.BOLD}TASK:{C.RESET} {task or flow2.DEFAULT_TASK}")
    flow2.run(task)
