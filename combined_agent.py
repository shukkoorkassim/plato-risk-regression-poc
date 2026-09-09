"""
combined_agent.py — ONE agent, BOTH signals, and a TWO-PATH self-heal.

Flow 1 (defect history) and Flow 2 (release changes) share the same agent loop,
so this wires both toolsets into a single agent. It scores risk from past defects
AND impact from what changed, runs the UNION of the tests either signal flags, and
then heals what breaks — but it heals the RIGHT thing:

    * TEST defect        -> the test asserts the wrong thing (the app is correct
                            per the requirement). The agent FIXES THE TEST.
    * APPLICATION defect -> src/swaglabs.py is genuinely wrong (the test is
                            correct). The agent FILES A JIRA DEFECT and leaves the
                            code for a developer — it does NOT silently patch it.

    python combined_agent.py
    python combined_agent.py "your own task"
    python run_poc.py --flow combined

No API key? Use  python demo_selfheal.py  for the deterministic two-path demo,
or  python run_poc.py --report  for the side-by-side selection report.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.common import C, run_agent, GENERIC_TOOLS, write_file, ROOT   # noqa: E402
from agent.jira_report import report_defect_to_jira, REPORT_DEFECT_TOOL   # noqa: E402
from agent import flow1_defect_history as f1                             # noqa: E402
from agent import flow2_change_driven as f2                              # noqa: E402


# ---- fix_test: the TEST-defect path -------------------------------------------
def fix_test(path, content):
    """Overwrite a TEST file to correct a wrong expectation. Restricted to tests/
    so the agent can never 'fix' a failure by weakening the app or editing source."""
    norm = str(path).replace("\\", "/")
    if not norm.startswith("tests/"):
        return ("fix_test only edits files under tests/. If src/swaglabs.py is the "
                "problem, that's an application defect — call report_defect_to_jira instead.")
    return write_file(path, content)


FIX_TEST_TOOL = {
    "name": "fix_test",
    "description": (
        "Fix a TEST whose expectation is wrong (the app is correct for the current "
        "requirement, but the test asserts an old/incorrect value). Restricted to files "
        "under tests/. Use this — never report_defect_to_jira — when the source is right "
        "and the test is stale. Args: path (e.g. 'tests/test_search.py'), content (the full "
        "corrected file)."),
    "input_schema": {"type": "object", "properties": {
        "path": {"type": "string"}, "content": {"type": "string"},
    }, "required": ["path", "content"]},
}

# both flows' pipeline tools (first 4 of each) + the two self-heal tools + generics
TOOLS = f1.TOOLS[:4] + f2.TOOLS[:4] + [REPORT_DEFECT_TOOL, FIX_TEST_TOOL] + GENERIC_TOOLS
TOOL_IMPL = {**f1.TOOL_IMPL, **f2.TOOL_IMPL,
             "report_defect_to_jira": report_defect_to_jira, "fix_test": fix_test}

SYSTEM = (
    "You are a combined risk-based regression selection agent for an SDET team "
    "testing a Swag Labs style store (login, inventory, cart, checkout, search, "
    "payments). You have TWO signals and must use BOTH in one pass.\n\n"
    "Order of work:\n"
    "  1. DEFECT HISTORY: read_defect_sources -> summarize_defects -> score_risk -> "
    "select_regression_tests. Note the tests it selects (set A).\n"
    "  2. RELEASE CHANGES: read_release_delta -> summarize_changes -> score_impact -> "
    "select_change_tests. Note the tests it selects (set B).\n"
    "  3. Run run_pytest on the UNION of set A and set B (pass the combined file paths "
    "explicitly, space-separated).\n\n"
    "  4. For EACH failing test, DIAGNOSE before you act. read_file the failing test AND "
    "the relevant part of src/swaglabs.py, and decide which is wrong:\n"
    "       - If the SOURCE is right for the current requirement but the TEST asserts an "
    "old or incorrect value -> it is a TEST defect. Call fix_test with the corrected "
    "test file. NEVER weaken a real assertion just to make it pass.\n"
    "       - If the TEST asserts the correct behaviour but the SOURCE (src/swaglabs.py) "
    "produces the wrong result -> it is an APPLICATION defect. Call report_defect_to_jira "
    "with component, a one-line summary, expected-vs-actual details and the failing test "
    "name. Do NOT edit src/swaglabs.py — a developer owns that fix; your job is to report "
    "and track it.\n"
    "  5. Re-run run_pytest. Test defects you fixed should now pass. Application defects "
    "stay red on purpose — they are tracked in Jira, not silently patched.\n\n"
    "Finish with ONE combined report: what defect history flagged (set A), what the "
    "release changes flagged (set B), the union you executed, then a SELF-HEAL section "
    "listing each failure as either 'TEST defect -> fixed' or 'APPLICATION defect -> filed "
    "<Jira key>'. Then STOP."
)

DEFAULT_TASK = (
    "Assess this release two ways at once — by past defect history and by what changed "
    "this release — then run the combined set of regression tests that either signal "
    "flags. For every failure, diagnose whether the TEST is wrong (fix the test) or the "
    "APPLICATION is wrong (file a Jira defect and leave the code for a developer). Give me "
    "one combined report showing what each signal contributed and how each failure was "
    "handled."
)


def run(task=None, max_steps=24):
    run_agent(task or DEFAULT_TASK, TOOLS, TOOL_IMPL, SYSTEM, max_steps=max_steps)


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"{C.BOLD}COMBINED · defect-history + change driven · two-path self-heal{C.RESET}")
    print(f"{C.BOLD}TASK:{C.RESET} {task or DEFAULT_TASK}")
    run(task)
