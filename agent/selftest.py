"""agent/selftest.py — one command that checks the whole POC on this machine.

    python run_poc.py --selftest

Eight groups of checks, in the order things actually break:

    1  environment      python, pytest, requests, .env
    2  live Jira        can it read real defects and real changes?
    3  live Confluence  can it parse the real requirement pages?
    4  data & scoring   sources -> scores -> selection, with the cut-off applied
    5  app test suite   python -m pytest tests
    6  the demos        --showcase renders end to end
    7  requirements     the command behind all 21 items still exits clean
    8  clean tree       nothing a demo planted was left behind

Every check reports PASS / FAIL / SKIP with a one-line reason, and the exit code
is non-zero if anything FAILED. SKIP is not a failure: a machine with no network
or no Jira token can still prove the offline half works, and the summary says
exactly which half was not covered rather than implying a clean bill of health.

No Jira issue is ever created by this command. --demo files a real defect, so it
is deliberately left out; run it yourself when you want that.
"""
import io
import contextlib
import subprocess
import sys
import time
from pathlib import Path

from .common import C, ROOT, STATE, THRESHOLD

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
W = 78


class Results:
    def __init__(self):
        self.rows = []

    def add(self, group, name, state, note=""):
        self.rows.append((group, name, state, note))
        colour = {PASS: C.GREEN, FAIL: C.RED, SKIP: C.YELLOW}[state]
        print(f"    {colour}{state:<4}{C.RESET}  {name:<34} {C.GREY}{note}{C.RESET}")
        return state == PASS

    def count(self, state):
        return sum(1 for *_, s, _ in self.rows if s == state)

    @property
    def failures(self):
        return [(g, n, note) for g, n, s, note in self.rows if s == FAIL]


def group(n, title):
    print(f"\n  {C.BOLD}{n}. {title}{C.RESET}")


def _quiet(fn, *a, **kw):
    """Run something noisy and keep its output; return (value, text, error)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            val = fn(*a, **kw)
        return val, buf.getvalue(), None
    except Exception as e:  # noqa: BLE001
        return None, buf.getvalue(), e


def _run(args, timeout=600):
    return subprocess.run([sys.executable, str(ROOT / "run_poc.py"), *args],
                          capture_output=True, text=True, timeout=timeout,
                          cwd=str(ROOT))


# ---------------------------------------------------------------------------
def run(deep=False):
    t0 = time.time()
    R = Results()

    print(f"\n{C.MAGENTA}{'=' * W}{C.RESET}")
    print(f"  {C.BOLD}SELF-TEST — is this POC working on this machine?{C.RESET}")
    print(f"  {C.GREY}Nothing here creates a Jira issue. Cut-off in use: "
          f"{THRESHOLD:.1f}{C.RESET}")
    print(f"{C.MAGENTA}{'=' * W}{C.RESET}")

    # ---- 1 · environment ---------------------------------------------------
    group(1, "ENVIRONMENT")
    v = sys.version_info
    R.add("env", "python", PASS if v >= (3, 8) else FAIL,
          f"{v.major}.{v.minor}.{v.micro}")

    for mod, why in (("pytest", "needed to run the app's tests"),
                     ("requests", "needed for live Jira / Confluence")):
        try:
            __import__(mod)
            R.add("env", mod, PASS, "installed")
        except ImportError:
            R.add("env", mod, FAIL, f"missing — pip install {mod} ({why})")

    env_file = ROOT / ".env"
    if env_file.exists():
        R.add("env", ".env", PASS, "present")
    else:
        R.add("env", ".env", SKIP,
              "not found — live checks will be skipped (copy env-template-demo.txt)")

    # ---- 2 · live Jira -----------------------------------------------------
    group(2, "LIVE JIRA")
    from . import flow1_defect_history as f1
    from . import flow2_change_driven as f2

    src1, _, err = _quiet(f1.read_defect_sources)
    if err:
        R.add("jira", "read defects", FAIL, str(err)[:70])
        src1 = ""
    elif "jira (live)" in src1:
        n = next((ln.split(":")[-1].strip() for ln in src1.splitlines()
                  if "jira (live)" in ln), "?")
        R.add("jira", "read defects", PASS, f"{n} issues from your Jira")
    else:
        R.add("jira", "read defects", SKIP,
              "reading bundled CSVs — set JIRA_LIVE=1 in .env for live data")

    src2, _, err = _quiet(f2.read_release_delta)
    if err:
        R.add("jira", "read release delta", FAIL, str(err)[:70])
        src2 = ""
    elif "jira (live)" in src2:
        R.add("jira", "read release delta", PASS, "features and fixes from your Jira")
    else:
        R.add("jira", "read release delta", SKIP, "reading bundled CSVs")

    # ---- 3 · live Confluence -----------------------------------------------
    group(3, "LIVE CONFLUENCE")
    try:
        from .confluence_source import confluence_configured, load_requirements_live
        if confluence_configured():
            reqs, _, err = _quiet(load_requirements_live)
            if err:
                R.add("confluence", "requirement pages", FAIL, str(err)[:70])
            elif reqs:
                R.add("confluence", "requirement pages", PASS,
                      f"{len(reqs)} requirement change(s) parsed")
            else:
                R.add("confluence", "requirement pages", FAIL,
                      "configured, but the page returned no rows")
        else:
            R.add("confluence", "requirement pages", SKIP,
                  "not configured — set CONFLUENCE_* in .env")
    except Exception as e:  # noqa: BLE001
        R.add("confluence", "requirement pages", FAIL, str(e)[:70])

    # ---- 4 · scoring and selection -----------------------------------------
    group(4, "SCORING AND SELECTION")
    import json
    _quiet(f1.score_risk)
    _quiet(f2.score_impact)
    try:
        risks = {r["component"]: r["risk"] for r in
                 json.loads((STATE / "risk.json").read_text())}
        impact = {r["component"]: r["impact"] for r in
                  json.loads((STATE / "impact.json").read_text())}
        R.add("score", "risk scored", PASS if risks else FAIL,
              f"{len(risks)} components, top {max(risks.values(), default=0):.1f}")
        R.add("score", "impact scored", PASS if impact else FAIL,
              f"{len(impact)} components, top {max(impact.values(), default=0):.1f}")

        # the selection must actually honour the cut-off in both directions
        sel, _, err = _quiet(f1.select_regression_tests)
        chosen = json.loads((STATE / "selected.json").read_text())
        above = {c for c in risks if risks[c] >= THRESHOLD}
        suite = f2.list_test_suite()
        expect = sorted(t for t, comp in suite.items() if comp in above)
        R.add("score", f"cut-off {THRESHOLD:.1f} applied",
              PASS if sorted(chosen) == expect else FAIL,
              f"{len(chosen)} of {len(suite)} tests selected on risk")

        # and it must move when the cut-off moves
        low = _run(["--showcase", "--threshold", "0.1"])
        high = _run(["--showcase", "--threshold", "999"])
        moved = ("RAN 6 of 6" in low.stdout and "RAN 0 of 6" in high.stdout)
        R.add("score", "cut-off is live, not hardcoded", PASS if moved else FAIL,
              "0.1 selects everything, 999 selects nothing")
    except Exception as e:  # noqa: BLE001
        R.add("score", "scoring", FAIL, str(e)[:70])

    # ---- 5 · the app's own tests -------------------------------------------
    group(5, "APP TEST SUITE")
    try:
        import pytest  # noqa: F401
        proc = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                              capture_output=True, text=True, timeout=600,
                              cwd=str(ROOT))
        tail = [l for l in proc.stdout.strip().splitlines() if l.strip()]
        summary = tail[-1][:60] if tail else "no output"
        R.add("tests", "python -m pytest tests",
              PASS if proc.returncode == 0 else FAIL, summary)
    except ImportError:
        R.add("tests", "python -m pytest tests", SKIP, "pytest not installed")
    except Exception as e:  # noqa: BLE001
        R.add("tests", "python -m pytest tests", FAIL, str(e)[:70])

    # ---- 6 · the demo renders ----------------------------------------------
    group(6, "THE DEMO")
    proc = _run(["--showcase"])
    phases_seen = proc.stdout.count("PHASE ")
    R.add("demo", "--showcase runs end to end",
          PASS if proc.returncode == 0 and phases_seen >= 10 else FAIL,
          f"{phases_seen} phases rendered")
    R.add("demo", "--showcase --ascii", PASS if _run(["--showcase", "--ascii"]).returncode == 0
          else FAIL, "plain-character fallback")
    # --demo files a real Jira defect, so it is never run here
    R.add("demo", "--demo (live LLM + Jira)", SKIP,
          "not run — it files a real defect; run it yourself")

    # ---- 7 · every requirement's command -----------------------------------
    group(7, "ALL 21 REQUIREMENTS")
    proc = _run(["--verify"])
    ok = proc.returncode == 0
    line = next((l for l in proc.stdout.splitlines() if "ran clean" in l or "failed" in l), "")
    R.add("reqs", "--verify", PASS if ok else FAIL,
          line.strip()[:60] or f"exit {proc.returncode}")
    if not ok:
        for l in proc.stdout.splitlines():
            if "FAIL" in l:
                print(f"          {C.RED}{l.strip()[:100]}{C.RESET}")

    # ---- 8 · the tree is as we found it ------------------------------------
    group(8, "CLEAN TREE")
    dirty = []
    for rel, marker in (("src/swaglabs.py", "TAX_RATE * 2"),):
        f = ROOT / rel
        if f.exists() and marker in f.read_text():
            dirty.append(rel)
    R.add("tree", "no planted bug left behind", FAIL if dirty else PASS,
          ", ".join(dirty) if dirty else "src and tests are clean")

    git = subprocess.run(["git", "status", "--porcelain", "src", "tests"],
                         capture_output=True, text=True, cwd=str(ROOT))
    if git.returncode == 0:
        changed = [l for l in git.stdout.splitlines() if l.strip()]
        R.add("tree", "git status src/ tests/", PASS if not changed else FAIL,
              "unmodified" if not changed else f"{len(changed)} file(s) modified")
    else:
        R.add("tree", "git status src/ tests/", SKIP, "not a git checkout")

    # ---- summary -----------------------------------------------------------
    n_pass, n_fail, n_skip = R.count(PASS), R.count(FAIL), R.count(SKIP)
    elapsed = time.time() - t0
    colour = C.RED if n_fail else (C.YELLOW if n_skip else C.GREEN)
    print(f"\n{colour}{'=' * W}{C.RESET}")
    if n_fail:
        print(f"  {C.RED}{C.BOLD}{n_fail} CHECK(S) FAILED{C.RESET}   "
              f"{C.GREEN}{n_pass} passed{C.RESET}  {C.YELLOW}{n_skip} skipped{C.RESET}"
              f"   {C.GREY}{elapsed:.1f}s{C.RESET}")
        print(f"{colour}{'=' * W}{C.RESET}")
        for g, n, note in R.failures:
            print(f"    {C.RED}x{C.RESET} {n} {C.GREY}— {note}{C.RESET}")
    else:
        print(f"  {C.GREEN}{C.BOLD}ALL CHECKS PASSED{C.RESET}   "
              f"{C.GREEN}{n_pass} passed{C.RESET}  {C.YELLOW}{n_skip} skipped{C.RESET}"
              f"   {C.GREY}{elapsed:.1f}s{C.RESET}")
        print(f"{colour}{'=' * W}{C.RESET}")
        if n_skip:
            print(f"  {C.YELLOW}Skipped is not passed.{C.RESET} {C.GREY}These were not "
                  f"covered:{C.RESET}")
            for g, n, s, note in R.rows:
                if s == SKIP:
                    print(f"    {C.YELLOW}-{C.RESET} {n} {C.GREY}— {note}{C.RESET}")
    print(f"\n  {C.GREY}Ready to present:{C.RESET} python run_poc.py --showcase")
    return n_fail == 0
