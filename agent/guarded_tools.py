"""agent/guarded_tools.py — enforce the governance rules on the LIVE agent path.

This closes the Phase 1 gap. Items 6 and 7 were implemented, but only the
scripted demo honoured them: the live flows handed the model a raw `write_file`
tool, so "fix the source, never the test" and "never commit to main" were
enforced by prompt wording alone. A model that ignored the wording could write
anywhere, and nothing would stop it.

Now the tool itself refuses:

    writing a TEST file          -> routed to pr_flow as a reviewable PR, and the
                                    working tree is left untouched
    writing SOURCE               -> allowed, but gated on test_fix_merge approval
    writing anything outside     -> refused outright
    src/ or tests/

The model cannot opt out of this, because it never gets the unguarded tool.
Prompt text is guidance; this is a control.
"""
from pathlib import Path

from .common import ROOT, C, write_file as _raw_write, GENERIC_TOOLS, GENERIC_IMPL
from . import approvals
from .pr_flow import propose_test_fix
from . import status as S

#: only these roots are writable at all
ALLOWED_ROOTS = ("src", "tests")


def _classify(path):
    p = Path(str(path).replace("\\", "/"))
    parts = p.parts
    if not parts:
        return "outside"
    root = parts[0]
    if root not in ALLOWED_ROOTS:
        return "outside"
    name = p.name
    if root == "tests" or name.startswith("test_"):
        return "test"
    return "source"


def guarded_write_file(path, content):
    """write_file, with the governance rules enforced in code."""
    kind = _classify(path)

    if kind == "outside":
        return (f"REFUSED: {path} is outside src/ and tests/. The agent may only "
                f"modify application source or tests. Nothing was written.")

    if kind == "test":
        # T7: a test change never lands directly — it becomes a reviewable PR.
        result = propose_test_fix(str(path), content,
                                  f"agent-proposed update to {Path(path).name}")
        approved, gate_line = approvals.gate("test_fix_merge", str(path))
        msg = [f"NOT WRITTEN to the working tree — test changes go through review.",
               result, gate_line.replace(C.GREEN, "").replace(C.YELLOW, "")
               .replace(C.GREY, "").replace(C.RESET, "")]
        if approved:
            _raw_write(path, content)
            msg.append(f"Approved, so {path} has now been updated.")
        else:
            msg.append("Pending approval: the change is staged for QA, not applied. "
                       "Do not retry — continue with the rest of the task.")
        return "\n".join(msg)

    # T6: source fixes are the agent's job, but still pass an approval gate.
    approved, gate_line = approvals.gate("test_fix_merge", f"source fix: {path}")
    if not approved:
        return (f"NOT WRITTEN: a human must approve source changes.\n{gate_line}\n"
                f"The proposed fix was not applied. Continue without retrying.")
    return _raw_write(path, content)


GUARDED_TOOLS = []
for _t in GENERIC_TOOLS:
    if _t["name"] == "write_file":
        _t = dict(_t)
        _t["description"] = (
            "Write a file under src/ or tests/. Test files are NOT written directly — "
            "they are turned into a pull request for QA review. Source writes require "
            "approval. Anything outside src/ and tests/ is refused.")
    GUARDED_TOOLS.append(_t)

GUARDED_IMPL = dict(GENERIC_IMPL)
GUARDED_IMPL["write_file"] = guarded_write_file


def report():
    """`python run_poc.py --gates` — show the governance controls and prove them."""
    S.banner("GOVERNANCE CONTROLS",
             "items 6 and 7 · enforced in code on the live agent path")

    print(f"  {C.BOLD}Approval gates{C.RESET} {C.GREY}(item 6){C.RESET}")
    for name, label in approvals.GATES.items():
        open_now, line = approvals.gate(name)
        mark = f"{C.GREEN}open{C.RESET}" if open_now else f"{C.YELLOW}closed{C.RESET}"
        print(f"    [{mark}] {name:18} {C.GREY}{label}{C.RESET}")
    print(f"    {C.GREY}closed by default; APPROVE_ALL=1 opens them for a demo{C.RESET}")

    print(f"\n  {C.BOLD}Write policy{C.RESET} {C.GREY}(item 7){C.RESET}")
    cases = [
        ("tests/test_login.py", "test file"),
        ("src/swaglabs.py", "application source"),
        ("run_poc.py", "outside src/ and tests/"),
        ("../../etc/passwd", "outside the project"),
    ]
    for path, desc in cases:
        kind = _classify(path)
        verdict = {"test": f"{C.CYAN}-> pull request for QA review{C.RESET}",
                   "source": f"{C.YELLOW}-> allowed, behind an approval gate{C.RESET}",
                   "outside": f"{C.RED}-> REFUSED{C.RESET}"}[kind]
        print(f"    {path:26} {C.GREY}{desc:24}{C.RESET} {verdict}")

    print(f"\n  {C.BOLD}Proof{C.RESET} {C.GREY}— the refusal is real, not documentation{C.RESET}")
    out = guarded_write_file("run_poc.py", "# malicious\n")
    print(f"    write to run_poc.py:  {C.RED}{out.splitlines()[0]}{C.RESET}")
    before = (ROOT / "tests" / "test_login.py").read_text()
    out = guarded_write_file("tests/test_login.py", "# weakened test\n")
    after = (ROOT / "tests" / "test_login.py").read_text()
    print(f"    write to a test file: {C.CYAN}{out.splitlines()[0]}{C.RESET}")
    print(f"    test file unchanged:  "
          f"{(C.GREEN + 'yes') if before == after else (C.RED + 'NO — LEAKED')}{C.RESET}")
    import shutil
    shutil.rmtree(ROOT / "_proposed_fixes", ignore_errors=True)

    print(f"\n  {C.GREY}The live flows are wired to these tools, so the model never "
          f"receives an\n  unguarded write. Prompt text is guidance; this is a "
          f"control.{C.RESET}")
