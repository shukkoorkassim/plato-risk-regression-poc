"""agent/approvals.py — human-in-the-loop approval gates (Phase 1 · T6).

The agent analyses and prepares actions, but a responsible human approves the
side-effectful ones. These are the defined checkpoints; a real deployment wires
each to a person / ticket. In a demo, APPROVE_ALL=1 auto-approves them.
"""
import os
from .common import C, load_dotenv

GATES = {
    "data_quality":      "Data quality & coverage reviewed before running",
    "risk_ratings":      "Final risk / impact ratings reviewed before selection is trusted",
    "defect_assignment": "Defect report & assignee approved before filing",
    "test_fix_merge":    "Auto test-fix reviewed & approved before merge",
}


def auto():
    load_dotenv()
    return os.environ.get("APPROVE_ALL", "").strip().lower() in ("1", "true", "yes", "on")


def gate(name, detail=""):
    """Return (approved, line). approved is True only when APPROVE_ALL is set."""
    label = GATES.get(name, name)
    tail = f" — {detail}" if detail else ""
    if auto():
        return True, f"{C.GREEN}[approved]{C.RESET} {label}{tail}"
    return False, (f"{C.YELLOW}[approval required]{C.RESET} {label}{tail}"
                   f"  {C.GREY}(APPROVE_ALL=1 to auto-approve in a demo){C.RESET}")
