"""
seed/seed_confluence.py — publish the POC's requirement changes to Confluence.

Creates one Confluence page, "Release Requirements — Swag Labs", holding the
requirement changes the Flow 2 agent treats as release signal, plus a short
description of both flows. Flow 2 can then be pointed at a real Confluence page
instead of data/release_delta/requirements.csv.

USAGE
    pip install requests
    export ATLASSIAN_SITE=your-site.atlassian.net
    export ATLASSIAN_EMAIL=you@example.com
    export ATLASSIAN_TOKEN=ATATT...
    export CONFLUENCE_SPACE_KEY=SWAG          # an existing space key
    python seed/seed_confluence.py
    python seed/seed_confluence.py --dry-run

Run from a machine that can reach your Atlassian site (the Cowork sandbox
cannot). If you use the Atlassian Rovo connector in Claude, you don't need this.
"""
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTA = ROOT / "data" / "release_delta"

SITE = os.environ.get("ATLASSIAN_SITE", "")
EMAIL = os.environ.get("ATLASSIAN_EMAIL", "")
TOKEN = os.environ.get("ATLASSIAN_TOKEN", "")
SPACE = os.environ.get("CONFLUENCE_SPACE_KEY", "SWAG")
DRY = "--dry-run" in sys.argv
TITLE = "Release Requirements — Swag Labs"


def _rows(path):
    return list(csv.DictReader(path.read_text().splitlines())) if path.exists() else []


def build_html():
    reqs = _rows(DELTA / "requirements.csv")
    rows = "".join(
        f"<tr><td>{r['key']}</td><td>{r['component']}</td>"
        f"<td>{r['summary']}</td><td>{r.get('changed_date','')}</td></tr>"
        for r in reqs
    )
    return (
        "<p>Requirement changes for the current release of the Swag Labs store. "
        "The change-driven regression agent (Flow 2) reads these to decide which "
        "components to re-test.</p>"
        "<table><thead><tr><th>Key</th><th>Component</th>"
        "<th>Requirement change</th><th>Changed</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "<p><strong>Flow 1 (defect-history driven)</strong> scores risk from past "
        "defects; <strong>Flow 2 (change driven)</strong> scores components from "
        "this release delta. Both flows then run only the tests that matter.</p>"
    )


def main():
    body = build_html()
    print(f'Prepared Confluence page "{TITLE}" for space {SPACE}.')
    if DRY:
        print(body)
        print("\n(dry run — nothing created)")
        return
    if not (SITE and EMAIL and TOKEN):
        sys.exit("ERROR: set ATLASSIAN_SITE, ATLASSIAN_EMAIL and ATLASSIAN_TOKEN "
                 "(or run with --dry-run).")
    import requests
    url = f"https://{SITE}/wiki/rest/api/content"
    payload = {
        "type": "page", "title": TITLE,
        "space": {"key": SPACE},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    resp = requests.post(url, json=payload, auth=(EMAIL, TOKEN), timeout=30)
    if resp.status_code >= 300:
        sys.exit(f"ERROR {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    link = data.get("_links", {})
    print(f"Created page id={data.get('id')}  {link.get('base','')}{link.get('webui','')}")


if __name__ == "__main__":
    main()
