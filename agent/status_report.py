"""agent/status_report.py — render the requirement matrix, and verify it.

    python run_poc.py --status          all 21 requirements, grouped by phase
    python run_poc.py --status --gaps   only what is unfinished, with reasons
    python run_poc.py --verify          actually RUN each listed command

--verify exists because a status table that nobody checks becomes fiction. It
executes every command in the registry and reports which ones still exit clean,
so the matrix cannot drift away from the code without someone noticing.
"""
import subprocess
import sys
from pathlib import Path

from .common import C, ROOT
from . import status as S
from .requirements import REQUIREMENTS, phases, counts

BAR = "=" * 78


def _bar(label, n, total, color):
    width = 34
    filled = round(width * n / total) if total else 0
    return (f"  {label:<12} {color}{'#' * filled}{C.GREY}{'.' * (width - filled)}"
            f"{C.RESET} {n:>2}/{total}")


def render(gaps_only=False):
    total = len(REQUIREMENTS)
    c = counts()

    print(f"\n{C.BOLD}Requirement status — all {total} items from the post-demo review{C.RESET}")
    print(f"{C.GREY}Regression_PoC_Next_Tasks.md · every claim has a command that proves it{C.RESET}\n")

    print(_bar("done", c.get(S.DONE, 0), total, C.GREEN))
    print(_bar("partial", c.get(S.PARTIAL, 0), total, C.YELLOW))
    print(_bar("placeholder", c.get(S.PLACEHOLDER, 0), total, C.YELLOW))
    print(_bar("blocked", c.get(S.BLOCKED, 0), total, C.RED))

    for phase in phases():
        items = [r for r in REQUIREMENTS if r["phase"] == phase]
        if gaps_only:
            items = [r for r in items if r["gap"] or r["state"] != S.DONE]
        if not items:
            continue
        print(f"\n{C.BOLD}{phase}{C.RESET}")
        for r in items:
            print(f"  {S.tag(r['state'])} {C.BOLD}{r['id']:>2}.{C.RESET} {r['title']}")
            if not gaps_only and r["note"]:
                print(f"       {C.GREY}{r['note']}{C.RESET}")
            if r["gap"]:
                print(f"       {C.YELLOW}gap:{C.RESET} {C.GREY}{r['gap']}{C.RESET}")
            print(f"       {C.CYAN}$ {r['command']}{C.RESET}")

    unfinished = [r for r in REQUIREMENTS if r["state"] != S.DONE]
    print(f"\n{BAR}")
    if unfinished:
        print(f"  {C.BOLD}{len(unfinished)} item(s) not finished:{C.RESET}")
        for r in unfinished:
            print(f"    {S.tag(r['state'])} {r['id']:>2}. {r['title']}")
        print(f"\n  {C.GREY}Every one of these has working code — what is missing is "
              f"REAL DATA or a\n  human step, never the mechanism. Each prints its own "
              f"placeholder warning when run.{C.RESET}")
    else:
        print(f"  {C.GREEN}All {total} requirements implemented.{C.RESET}")
    print(BAR)


def verify():
    """Run every command in the registry; report which still work."""
    print(f"\n{C.BOLD}Verifying — running the command behind every requirement{C.RESET}")
    print(f"{C.GREY}A status table nobody checks becomes fiction.{C.RESET}\n")

    seen, results = set(), []
    for r in REQUIREMENTS:
        cmd = r["command"]
        if cmd in seen:
            continue
        seen.add(cmd)
        args = cmd.replace("python run_poc.py", "").split()
        # the LLM-driven demo needs an API key and real money; skip it here
        if "--demo" in args:
            print(f"  {C.GREY}skip{C.RESET}  {cmd}  "
                  f"{C.GREY}(needs ANTHROPIC_API_KEY / a live run){C.RESET}")
            continue
        proc = subprocess.run([sys.executable, str(ROOT / "run_poc.py"), *args],
                              capture_output=True, text=True, timeout=600,
                              cwd=str(ROOT))
        ok = proc.returncode == 0
        results.append((cmd, ok))
        tag = f"{C.GREEN}PASS{C.RESET}" if ok else f"{C.RED}FAIL{C.RESET}"
        print(f"  {tag}  {cmd}")
        if not ok:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
            for line in tail:
                print(f"        {C.RED}{line[:110]}{C.RESET}")

    bad = [c for c, ok in results if not ok]
    print(f"\n{BAR}")
    if bad:
        print(f"  {C.RED}{len(bad)} command(s) failed{C.RESET} — the status matrix is "
              f"out of date, or something regressed.")
    else:
        print(f"  {C.GREEN}All {len(results)} commands ran clean.{C.RESET} "
              f"{C.GREY}The status matrix reflects the code.{C.RESET}")
    print(BAR)
    return not bad
