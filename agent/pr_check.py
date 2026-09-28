"""agent/pr_check.py — fast smoke check for a pull request (item 16).

A PR gate answers one narrow question: *did this change break anything?* It has
minutes, not hours, so it uses the change signal only — what these files touch —
and runs a small bounded subset.

Where the changed files come from, in order:
    1. --base <ref>      git diff against that ref
    2. a real git repo   git diff against the merge-base with the default branch
    3. no repo           fall back to the staged release delta, and SAY SO

    python run_poc.py --pr-check
    python run_poc.py --pr-check --base origin/main
"""
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from .common import C, ROOT, STATE
from . import status as S
from .schedules import PROFILES


def _git(*args):
    try:
        p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=60)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _in_repo():
    return _git("rev-parse", "--is-inside-work-tree") == "true"


def changed_files(base=None):
    """(files, how) — the changed paths and where we got them."""
    if not _in_repo():
        return [], "no-git"

    if base:
        diff = _git("diff", "--name-only", f"{base}...HEAD") or _git("diff", "--name-only", base)
        if diff:
            return [l for l in diff.splitlines() if l.strip()], f"git diff vs {base}"

    for ref in ("origin/main", "origin/master", "main", "master"):
        mb = _git("merge-base", "HEAD", ref)
        if mb:
            diff = _git("diff", "--name-only", f"{mb}...HEAD")
            if diff:
                return [l for l in diff.splitlines() if l.strip()], f"git diff vs {ref}"

    # uncommitted work is still a change worth checking
    diff = _git("diff", "--name-only", "HEAD")
    if diff:
        return [l for l in diff.splitlines() if l.strip()], "uncommitted changes"
    return [], "clean-tree"


def components_for(paths, suite):
    """Map changed paths to components, via the test map's own vocabulary."""
    known = set(suite.values())
    hits = defaultdict(list)
    for p in paths:
        stem = Path(p).stem.lower()
        text = p.lower()
        for comp in known:
            if comp in text or comp in stem:
                hits[comp].append(p)
    return dict(hits)


def run(base=None, execute=True):
    profile = PROFILES["pr"]
    S.banner("PULL-REQUEST SMOKE CHECK",
             f"item 16 · {profile['question']} · budget {profile['max_tests']} tests")

    from . import flow2_change_driven as f2
    suite = f2.list_test_suite()

    paths, how = changed_files(base)
    if how in ("no-git", "clean-tree"):
        reason = ("not a git repository" if how == "no-git"
                  else "working tree is clean — nothing changed")
        S.say(S.PARTIAL, "changed-file detection",
              f"{reason}; falling back to the staged release delta so the check "
              f"still demonstrates end to end")
        f2.read_release_delta()
        changes = json.loads((STATE / "changes.json").read_text())
        touched = defaultdict(list)
        for ch in changes:
            touched[ch["component"]].append(f"{ch['id']} ({ch['type']})")
        source = "release delta (no git diff available)"
    else:
        S.say(S.DONE, "changed-file detection", how)
        touched = components_for(paths, suite)
        source = how
        print(f"\n  {len(paths)} changed file(s):")
        for p in paths[:12]:
            print(f"    {C.GREY}{p}{C.RESET}")
        if len(paths) > 12:
            print(f"    {C.GREY}... and {len(paths) - 12} more{C.RESET}")

    if not touched:
        print(f"\n  {C.GREEN}No mapped component touched by this change.{C.RESET}")
        print(f"  {C.GREY}Nothing to smoke-test. If that looks wrong, the change "
              f"touches code the\n  test map does not cover — see "
              f"python run_poc.py --coverage{C.RESET}")
        return []

    print(f"\n  components touched ({source}):")
    for comp, why in sorted(touched.items()):
        print(f"    {C.YELLOW}*{C.RESET} {comp:12} {C.GREY}{', '.join(str(w) for w in why[:3])}"
              f"{' ...' if len(why) > 3 else ''}{C.RESET}")

    # Changed files that map to NO component are the dangerous ones: the gate
    # cannot reason about them, so it must not imply it has. Naming them is the
    # PR-time version of the coverage-gap report.
    if how not in ("no-git", "clean-tree"):
        mapped = {p for ps in touched.values() for p in ps}
        unmapped = [p for p in paths if p not in mapped]
        if unmapped:
            print(f"\n  {C.YELLOW}{len(unmapped)} changed file(s) map to NO component"
                  f"{C.RESET} {C.GREY}— the gate is blind to these:{C.RESET}")
            for p in unmapped[:8]:
                print(f"    {C.YELLOW}?{C.RESET} {p}")
            print(f"    {C.GREY}Their filenames carry no component name, so the test map "
                  f"cannot place them.\n    Extend tests/test_map.json, or name files "
                  f"after the component they serve.{C.RESET}")

    selected = sorted({t for t, comp in suite.items() if comp in touched})
    if len(selected) > profile["max_tests"]:
        print(f"\n  {C.YELLOW}budget:{C.RESET} {len(selected)} tests match, capping at "
              f"{profile['max_tests']} — a PR gate must stay fast.")
        selected = selected[:profile["max_tests"]]

    (STATE / "selected.json").write_text(json.dumps(selected))
    print(f"\n  {C.BOLD}SMOKE SET ({len(selected)} of {len(suite)}):{C.RESET}")
    for t in selected:
        print(f"    {C.GREEN}RUN{C.RESET}  {t}   {C.GREY}(covers {suite[t]}){C.RESET}")

    if execute and selected:
        print(f"\n  {C.GREY}running...{C.RESET}")
        verdict, tail = _execute(selected)
        colour = {"pass": C.GREEN, "fail": C.RED, "error": C.YELLOW}[verdict]
        print(f"  {colour}{tail}{C.RESET}")
        label = {"pass": "PASS", "fail": "FAIL",
                 "error": "COULD NOT RUN — treat as FAIL"}[verdict]
        print(f"\n  {C.BOLD}PR gate: {colour}{label}{C.RESET}")
        if verdict == "error":
            print(f"  {C.GREY}A gate that cannot run its tests must never report "
                  f"success — an unrunnable\n  suite is indistinguishable from a "
                  f"broken one.{C.RESET}")
    return selected


def _execute(selected):
    """Run the smoke set. Returns (verdict, summary_line).

    Uses the process exit code, not string-matching on output. An earlier
    version scanned stdout for the word "failed", which reported PASS when
    pytest was not installed at all — the single worst outcome for a merge gate.
    """
    import sys
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *[str(ROOT / t) for t in selected],
         "-q", "--no-header", "--tb=short"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [l for l in out.strip().splitlines() if l.strip()]
    tail = lines[-1] if lines else "no output"

    if proc.returncode == 0:
        return "pass", tail
    # exit 1 = tests failed; anything else (2=usage, 4=internal, 5=no tests
    # collected, 127=no interpreter/module) means we never got a verdict
    if proc.returncode == 1 and ("failed" in out.lower() or "error" in out.lower()):
        return "fail", tail
    if "No module named pytest" in out:
        return "error", "pytest is not installed — the smoke set could not run"
    return "error", f"pytest exited {proc.returncode}: {tail}"
