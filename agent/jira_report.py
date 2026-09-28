"""
agent/jira_report.py — file a real Jira DEFECT when the agent finds an
application (dev) bug, and assign it.

Self-heal has two paths (see combined_agent.py):
  * TEST defect      -> the test asserts the wrong thing; the agent FIXES the test.
  * APPLICATION defect -> src/swaglabs.py is genuinely wrong; the agent does NOT
                          silently patch it — it FILES a Jira defect here so a
                          developer owns the fix, and the finding is tracked.

This module is the application-defect path. Gated behind REPORT_BUGS=1 so normal
runs and dry-runs never create tickets.

Environment:
    REPORT_BUGS=1                         # turn ticket creation on
    ATLASSIAN_SITE / ATLASSIAN_EMAIL / ATLASSIAN_TOKEN
    JIRA_PROJECT_KEY=KAN
    JIRA_ASSIGNEE_EMAIL=you@example.com   # who to assign to (defaults to ATLASSIAN_EMAIL)
    JIRA_DEFECT_ISSUETYPE=Task            # issue type to create (KAN has no Bug type -> Task)
"""

import os

from .common import load_dotenv, STATE


#: Every defect the agent files is recorded here, so a later run can show the
#: real Jira link without going back to the network. --showcase reads it.
FILED = STATE / "filed_defects.json"


def _record_filed(key, url, component, summary):
    """Append one filed defect to the local log. Never fatal: a logging problem
    must not turn a successfully-filed defect into a reported failure."""
    try:
        import json
        from datetime import datetime
        rows = json.loads(FILED.read_text()) if FILED.exists() else []
        rows.append({"key": key, "url": url, "component": component,
                     "summary": summary, "when": datetime.now().isoformat(timespec="seconds")})
        FILED.write_text(json.dumps(rows, indent=2))
    except Exception:  # noqa: BLE001
        pass


def last_filed(component=None):
    """The most recent defect filed (optionally for one component), or None."""
    try:
        import json
        rows = json.loads(FILED.read_text()) if FILED.exists() else []
    except Exception:  # noqa: BLE001
        return None
    if component:
        rows = [r for r in rows if r.get("component") == component]
    return rows[-1] if rows else None


def browse_url(key):
    """The Jira URL for an issue key, from config alone — no network call."""
    site = _cfg()["site"]
    return f"https://{site}/browse/{key}" if site else None


def report_enabled():
    load_dotenv()
    return os.environ.get("REPORT_BUGS", "").strip().lower() in ("1", "true", "yes", "on")


def _cfg():
    load_dotenv()
    return {
        "site": os.environ.get("ATLASSIAN_SITE", "").strip().replace("https://", "").rstrip("/"),
        "email": os.environ.get("ATLASSIAN_EMAIL", "").strip(),
        "token": os.environ.get("ATLASSIAN_TOKEN", "").strip(),
        "project": os.environ.get("JIRA_PROJECT_KEY", "KAN").strip(),
        "assignee": os.environ.get("JIRA_ASSIGNEE_EMAIL", "").strip() or os.environ.get("ATLASSIAN_EMAIL", "").strip(),
        # KAN (team-managed) has Epic/Task/Story/Subtask but no Bug -> default Task.
        "issuetype": os.environ.get("JIRA_DEFECT_ISSUETYPE", os.environ.get("JIRA_BUG_ISSUETYPE", "Task")).strip() or "Task",
    }


def _adf(text):
    # one paragraph per line so the description keeps its shape in Jira
    content = []
    for line in text.split("\n"):
        content.append({"type": "paragraph",
                        "content": [{"type": "text", "text": line}] if line else []})
    return {"type": "doc", "version": 1, "content": content}


def _account_id(base, auth, email):
    if not email:
        return None
    import requests
    try:
        r = requests.get(f"{base}/rest/api/3/user/search", params={"query": email}, auth=auth, timeout=30)
        r.raise_for_status()
        users = r.json()
        return users[0]["accountId"] if users else None
    except Exception:
        return None



def _transition_to_todo(base, auth, key):
    """Best-effort: move a freshly-created issue to an open 'To Do' status so a
    filed defect doesn't sit in Done (some team-managed boards default there)."""
    import requests
    try:
        r = requests.get(f"{base}/rest/api/3/issue/{key}/transitions", auth=auth, timeout=30)
        for t in r.json().get("transitions", []):
            to = t.get("to", {})
            if to.get("name", "").lower() == "to do" or to.get("statusCategory", {}).get("key") == "new":
                requests.post(f"{base}/rest/api/3/issue/{key}/transitions",
                              json={"transition": {"id": t["id"]}}, auth=auth, timeout=30)
                return
    except Exception:
        pass

def report_defect_to_jira(component, summary, details="", severity="major"):
    """Create a Jira DEFECT for a real APPLICATION bug and assign it to the dev/BA.

    Use this only when a selected test failed because src/swaglabs.py is genuinely
    wrong (the test asserts the correct behaviour). For a wrong TEST, fix the test
    instead — do not file a defect. Returns a human-readable status string.
    """
    if not report_enabled():
        return ("[would file DEFECT to Jira] "
                f"{component}: {summary}  (set REPORT_BUGS=1 + Atlassian creds to create the ticket)")
    c = _cfg()
    if not (c["site"] and c["email"] and c["token"]):
        return "Cannot file defect: ATLASSIAN_SITE/EMAIL/TOKEN not set."
    try:
        import requests
    except ImportError:
        return "Cannot file defect: the 'requests' package is required (pip install requests)."

    base = f"https://{c['site']}"
    auth = (c["email"], c["token"])
    account_id = _account_id(base, auth, c["assignee"])

    desc = (f"Auto-filed by the risk-based regression agent (self-heal, application-defect path).\n"
            f"\nComponent: {component}\nSeverity: {severity}\n"
            f"Type: application / dev bug (source is wrong; the test is correct)\n\n{details}").strip()
    fields = {
        "project": {"key": c["project"]},
        "issuetype": {"name": c["issuetype"]},
        "summary": f"[DEFECT][{component}] {summary}",
        "description": _adf(desc),
        "labels": ["defect", "bug", "found-by-agent", "self-heal", str(component), str(severity)],
    }
    if account_id:
        fields["assignee"] = {"id": account_id}

    try:
        r = requests.post(f"{base}/rest/api/3/issue", json={"fields": fields}, auth=auth, timeout=30)
        if r.status_code >= 300 and account_id:
            fields.pop("assignee", None)  # retry unassigned if assignment was the problem
            r = requests.post(f"{base}/rest/api/3/issue", json={"fields": fields}, auth=auth, timeout=30)
        if r.status_code >= 300:
            return f"Failed to file defect: {r.status_code} {r.text[:200]}"
        key = r.json().get("key")
        _transition_to_todo(base, auth, key)
        who = c["assignee"] if account_id else "unassigned"
        url = f"{base}/browse/{key}"
        _record_filed(key, url, component, summary)
        return f"Filed Jira DEFECT {key} for the {component} bug and assigned to {who}. {url}"
    except Exception as e:  # noqa: BLE001
        return f"Failed to file defect: {e}"


# backward-compatible alias (older prompts call report_bug_to_jira)
def report_bug_to_jira(component, summary, details=""):
    return report_defect_to_jira(component, summary, details)


REPORT_DEFECT_TOOL = {
    "name": "report_defect_to_jira",
    "description": (
        "File a Jira DEFECT for a REAL application bug: a selected test failed because "
        "src/swaglabs.py is genuinely wrong AND the test asserts the correct behaviour. "
        "Do NOT call this for a wrong test — fix the test instead. Call once per distinct "
        "application bug. Args: component (e.g. 'checkout'), summary (one line), details "
        "(expected vs actual + the failing test), severity (blocker|critical|major|minor)."),
    "input_schema": {"type": "object", "properties": {
        "component": {"type": "string"},
        "summary": {"type": "string"},
        "details": {"type": "string"},
        "severity": {"type": "string"},
    }, "required": ["component", "summary"]},
}

# keep the old symbol importable
REPORT_TOOL = REPORT_DEFECT_TOOL
