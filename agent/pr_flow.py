"""agent/pr_flow.py — auto test-fixes go through a PR for QA review, never to main (T7).

When the agent corrects a stale test, it must NOT push to the main branch. It
prepares a reviewable change — a real pull request when git + gh are configured
(PR_MODE=1), otherwise a saved proposal — that a QA member approves before merge.
"""
import os
import subprocess
from pathlib import Path
from shutil import which

from .common import ROOT, load_dotenv


def _run(args):
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=60)


def propose_test_fix(path, new_content, summary):
    """Prepare a reviewable test fix. Never writes to main. Returns a status string."""
    load_dotenv()
    prop_dir = ROOT / "_proposed_fixes"
    prop_dir.mkdir(exist_ok=True)
    prop = prop_dir / (Path(path).name + ".proposed")
    prop.write_text(new_content)

    prmode = os.environ.get("PR_MODE", "").strip().lower() in ("1", "true", "yes", "on")
    if prmode and which("git"):
        branch = f"autofix/{Path(path).stem}"
        _run(["git", "checkout", "-b", branch])
        (ROOT / path).write_text(new_content)
        _run(["git", "add", path])
        _run(["git", "commit", "-m", f"[auto][test-fix] {summary}"])
        if which("gh"):
            r = _run(["gh", "pr", "create", "--title", f"[auto] {summary}",
                      "--body", "Auto-prepared stale-test fix. Requires QA review before merge.",
                      "--head", branch])
            _run(["git", "checkout", "-"])
            out = (r.stdout or r.stderr).strip().splitlines()
            return f"Opened PR for QA review on branch '{branch}'. {out[-1] if out else ''}".strip()
        _run(["git", "checkout", "-"])
        return f"Prepared branch '{branch}' with the fix — open a PR for QA review (gh not found)."
    return ("PR prepared for QA review (not merged): saved the proposed fix to "
            f"_proposed_fixes/{prop.name}. Set PR_MODE=1 with git + gh to open a real PR.")
