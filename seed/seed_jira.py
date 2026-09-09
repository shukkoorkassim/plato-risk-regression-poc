"""
seed/seed_jira.py — create the POC's sample Jira issues in a real Jira project.

Reads the same CSVs the agents read and creates matching Jira issues so a live
demo can point the Flow 1 loader at a real Jira export and the Flow 2 loader at
real release stories/bugs.

  - data/release_delta/stories.csv   -> Story  issues (the new features)
  - data/release_delta/bugfixes.csv  -> Bug    issues (defects fixed this release)
  - data/jira_export.csv             -> Bug    issues (historical defects, resolved)

Component names become labels (Jira components must be pre-created; labels don't),
so nothing needs to exist in the project beforehand except the project itself.

USAGE
    pip install requests
    export ATLASSIAN_SITE=your-site.atlassian.net
    export ATLASSIAN_EMAIL=you@example.com
    export ATLASSIAN_TOKEN=ATATT...           # https://id.atlassian.com/manage/api-tokens
    export JIRA_PROJECT_KEY=SWAG              # an existing project key
    python seed/seed_jira.py                   # create the issues
    python seed/seed_jira.py --dry-run         # print what would be created

Note: this talks to Atlassian directly, so run it from a machine that can reach
your Atlassian site (the Cowork sandbox cannot). If you use the Atlassian Rovo
connector in Claude instead, you don't need this script at all.
"""
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DELTA = DATA / "release_delta"

SITE = os.environ.get("ATLASSIAN_SITE", "")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
PROJECT = os.environ.get("JIRA_PROJECT_KEY", "SWAG")
DRY = "--dry-run" in sys.argv


def _rows(path):
    return list(csv.DictReader(path.read_text().splitlines())) if path.exists() else []


def _adf(text):
    """Minimal Atlassian Document Format wrapper for a plain-text description."""
    return {"type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def build_issues():
    issues = []
    for r in _rows(DELTA / "stories.csv"):
        issues.append({
            "type": "Story", "component": r["component"],
            "summary": f'[{r["key"]}] {r["summary"]}',
            "desc": f'Release feature for the "{r["component"]}" component. Story points: {r.get("points","?")}.',
            "labels": ["poc", "release-delta", "feature", r["component"]],
        })
    for r in _rows(DELTA / "bugfixes.csv"):
        issues.append({
            "type": "Bug", "component": r["component"],
            "summary": f'[{r["key"]}] {r["summary"]}',
            "desc": f'Bug fixed this release in "{r["component"]}" (severity: {r.get("severity","?")}).',
            "labels": ["poc", "release-delta", "bugfix", r["component"], r.get("severity", "")],
        })
    for r in _rows(DATA / "jira_export.csv"):
        issues.append({
            "type": "Bug", "component": r["component"],
            "summary": f'[{r["key"]}] {r["summary"]}',
            "desc": f'Historical defect in "{r["component"]}" (severity: {r.get("severity","?")}, resolved {r.get("resolved","?")}).',
            "labels": ["poc", "defect-history", r["component"], r.get("severity", "")],
        })
    return issues


def main():
    issues = build_issues()
    print(f"Prepared {len(issues)} Jira issues for project {PROJECT}.")
    if DRY:
        for i in issues:
            print(f"  [{i['type']:5}] {i['summary']}  labels={','.join(l for l in i['labels'] if l)}")
        print("\n(dry run — nothing created)")
        return
    if not (SITE and EMAIL and TOKEN):
        sys.exit("ERROR: set ATLASSIAN_SITE, ATLASSIAN_EMAIL and ATLASSIAN_TOKEN "
                 "(or run with --dry-run).")
    import requests
    url = f"https://{SITE}/rest/api/3/issue"
    auth = (EMAIL, TOKEN)
    created = []
    for i in issues:
        payload = {"fields": {
            "project": {"key": PROJECT},
            "issuetype": {"name": i["type"]},
            "summary": i["summary"],
            "description": _adf(i["desc"]),
            "labels": [l for l in i["labels"] if l],
        }}
        resp = requests.post(url, json=payload, auth=auth, timeout=30)
        if resp.status_code >= 300:
            print(f"  ! {i['summary'][:50]} -> {resp.status_code} {resp.text[:200]}")
            continue
        key = resp.json().get("key")
        created.append(key)
        print(f"  + {key}  {i['summary'][:60]}")
    print(f"\nCreated {len(created)} issues in {PROJECT}.")


if __name__ == "__main__":
    main()
