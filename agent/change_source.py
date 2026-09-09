"""
agent/change_source.py — pull Flow 2's release delta LIVE.

Turns the change-driven inputs into live reads instead of CSV files:
    features (user stories)  <- Jira   (labels: release-delta + feature)
    bug fixes                <- Jira   (labels: release-delta + bugfix)
    requirement changes      <- Confluence   (see agent/confluence_source.py)
    code churn               <- data/release_delta/release_churn.csv   (git history; stays a file)

Enable with CHANGE_LIVE=1 plus the Atlassian credentials (see .env.example).
Each source degrades gracefully: if Jira/Confluence isn't configured, that part
falls back to its CSV. Churn is always read from the CSV because it comes from
git, not a tracker.
"""

import os

from .common import load_dotenv
from .jira_source import _cfg as _jira_cfg, search_issues, KNOWN_COMPONENTS

FEATURE_FIELDS = ["summary", "labels", "components"]


def use_live_changes():
    """True if CHANGE_LIVE is truthy AND Jira credentials are present."""
    load_dotenv()
    if os.environ.get("CHANGE_LIVE", "").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    c = _jira_cfg()
    return bool(c["site"] and c["email"] and c["token"])


def _component_from(fields):
    comps = fields.get("components") or []
    if comps and comps[0].get("name"):
        return comps[0]["name"].strip().lower()
    for lbl in fields.get("labels") or []:
        if lbl.strip().lower() in KNOWN_COMPONENTS:
            return lbl.strip().lower()
    return "unknown"


def _jql(kind):
    c = _jira_cfg()
    env = os.environ.get(f"JIRA_{kind.upper()}_JQL", "").strip()
    if env:
        return env
    return f'project = {c["project"]} AND labels = "release-delta" AND labels = "{kind}" ORDER BY created ASC'


def load_features_live():
    issues = search_issues(_jql("feature"), FEATURE_FIELDS)
    return [{
        "id": i.get("key", "STORY-?"),
        "component": _component_from(i.get("fields", {})),
        "type": "feature",
        "summary": i.get("fields", {}).get("summary", "") or "",
        "source": "user story",
    } for i in issues]


def load_bugfixes_live():
    issues = search_issues(_jql("bugfix"), FEATURE_FIELDS)
    return [{
        "id": i.get("key", "FIX-?"),
        "component": _component_from(i.get("fields", {})),
        "type": "bugfix",
        "summary": i.get("fields", {}).get("summary", "") or "",
        "source": "bug fix",
    } for i in issues]
