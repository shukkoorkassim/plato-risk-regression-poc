"""
agent/jira_source.py — pull Flow 1's defects LIVE from Jira instead of a CSV.

By default Flow 1 reads data/jira_export.csv. Set JIRA_LIVE=1 (and the Atlassian
credentials below) and Flow 1 will instead query Jira over the REST API with JQL,
normalising each issue into the same shape the CSV loader produces:

    {id, component, severity, summary, resolved, source="jira"}

Environment (put these in .env or export them):
    JIRA_LIVE=1
    ATLASSIAN_SITE=your-site.atlassian.net
    ATLASSIAN_EMAIL=you@example.com
    ATLASSIAN_TOKEN=ATATT...                 # https://id.atlassian.com/manage/api-tokens
    JIRA_PROJECT_KEY=KAN
    JIRA_JQL=...                              # optional; overrides the default query

Default JQL targets the resolved historical defects seeded for this POC:
    project = <KEY> AND labels = defect-history ORDER BY resolved DESC
In a real project you would use the "resolved bugs in the last 180 days" basis:
    project = <KEY> AND issuetype = Bug AND statusCategory = Done AND resolved >= -180d

Component & severity: read from the issue's real Components / Priority fields when
present; otherwise inferred from labels (which is how this POC's issues are tagged).
"""

import os

from .common import load_dotenv

KNOWN_COMPONENTS = {"login", "inventory", "cart", "checkout", "search", "payments"}
KNOWN_SEVERITIES = {"blocker", "critical", "major", "high", "medium", "minor", "low"}
# Jira Priority -> our severity vocabulary (used only when no severity label exists)
PRIORITY_TO_SEVERITY = {
    "highest": "critical", "high": "high", "medium": "medium",
    "low": "minor", "lowest": "low",
}


def _cfg():
    load_dotenv()
    return {
        "site": os.environ.get("ATLASSIAN_SITE", "").strip().replace("https://", "").rstrip("/"),
        "email": os.environ.get("ATLASSIAN_EMAIL", "").strip(),
        "token": os.environ.get("ATLASSIAN_TOKEN", "").strip(),
        "project": os.environ.get("JIRA_PROJECT_KEY", "KAN").strip(),
        "jql": os.environ.get("JIRA_JQL", "").strip(),
    }


def use_live_jira():
    """True only if JIRA_LIVE is truthy AND the credentials are present."""
    if os.environ.get("JIRA_LIVE", "").strip().lower() not in ("1", "true", "yes", "on"):
        # load_dotenv so a JIRA_LIVE set in .env is honoured too
        load_dotenv()
        if os.environ.get("JIRA_LIVE", "").strip().lower() not in ("1", "true", "yes", "on"):
            return False
    c = _cfg()
    return bool(c["site"] and c["email"] and c["token"])


def _component_of(fields):
    comps = fields.get("components") or []
    if comps and comps[0].get("name"):
        name = comps[0]["name"].strip().lower()
        return name
    for lbl in fields.get("labels") or []:
        if lbl.strip().lower() in KNOWN_COMPONENTS:
            return lbl.strip().lower()
    return "unknown"


def _severity_of(fields):
    for lbl in fields.get("labels") or []:
        if lbl.strip().lower() in KNOWN_SEVERITIES:
            return lbl.strip().lower()
    prio = (fields.get("priority") or {}).get("name", "")
    return PRIORITY_TO_SEVERITY.get(prio.strip().lower(), "medium")


def _resolved_of(fields):
    for key in ("resolutiondate", "updated", "created"):
        v = fields.get(key)
        if v:
            return str(v)[:10]  # YYYY-MM-DD
    return ""


def _normalize(issue):
    fields = issue.get("fields", {})
    return {
        "id": issue.get("key", "JIRA-?"),
        "component": _component_of(fields),
        "severity": _severity_of(fields),
        "summary": fields.get("summary", "") or "",
        "resolved": _resolved_of(fields),
        "reopened": any(str(l).strip().lower() == "reopened" for l in (fields.get("labels") or [])),
        "source": "jira",
    }


def search_issues(jql, fields):
    """Run a JQL search and return the raw issue nodes. Tries the enhanced
    /search/jql endpoint, falling back to the legacy /search. Reusable by any
    flow (Flow 1 defects, Flow 2 stories & bug fixes)."""
    c = _cfg()
    if not (c["site"] and c["email"] and c["token"]):
        return []
    try:
        import requests
    except ImportError:
        raise RuntimeError("live Jira needs the 'requests' package — pip install requests")
    auth = (c["email"], c["token"])
    base = f"https://{c['site']}"

    def _enhanced():
        out, token = [], None
        while True:
            body = {"jql": jql, "fields": fields, "maxResults": 100}
            if token:
                body["nextPageToken"] = token
            r = requests.post(f"{base}/rest/api/3/search/jql", json=body, auth=auth, timeout=30)
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("issues", []))
            token = data.get("nextPageToken")
            if not token:
                return out

    def _legacy():
        out, start = [], 0
        while True:
            params = {"jql": jql, "fields": ",".join(fields), "maxResults": 100, "startAt": start}
            r = requests.get(f"{base}/rest/api/3/search", params=params, auth=auth, timeout=30)
            r.raise_for_status()
            data = r.json()
            batch = data.get("issues", [])
            out.extend(batch)
            start += len(batch)
            if start >= data.get("total", 0) or not batch:
                return out

    try:
        return _enhanced()
    except Exception:
        return _legacy()  # older sites / different contract


def load_jira_live(path=None):  # path kept for signature-compatibility with the CSV loader
    """Query Jira and return normalized defects. Requires the `requests` package."""
    c = _cfg()
    if not (c["site"] and c["email"] and c["token"]):
        return []
    jql = c["jql"] or f'project = {c["project"]} AND labels = defect-history ORDER BY resolved DESC'
    fields = ["summary", "priority", "labels", "components", "resolutiondate", "updated", "created"]
    return [_normalize(i) for i in search_issues(jql, fields)]
