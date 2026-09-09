"""
scripts/reset_demo.py — put the demo back to its starting state.

The two agents FIX src/swaglabs.py when they run. To demo again from scratch you
need the planted bugs back. This restores src/swaglabs.py from the committed
baseline (scripts/_swaglabs_baseline.py) and clears the agents' ._agent_state.

    python scripts/reset_demo.py
    python run_poc.py --reset          # same thing
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "_swaglabs_baseline.py"
SRC = ROOT / "src" / "swaglabs.py"
STATE = ROOT / "._agent_state"


def reset():
    if not BASELINE.exists():
        print(f"ERROR: baseline not found at {BASELINE}")
        sys.exit(1)
    shutil.copyfile(BASELINE, SRC)
    print(f"restored {SRC.relative_to(ROOT)} from baseline (both bugs re-planted)")
    if STATE.exists():
        n = 0
        for f in STATE.glob("*.json"):
            f.unlink()
            n += 1
        print(f"cleared {n} agent-state file(s) in {STATE.relative_to(ROOT)}/")
    print("Ready for a fresh demo. Try:  python dry_run.py")


if __name__ == "__main__":
    reset()
