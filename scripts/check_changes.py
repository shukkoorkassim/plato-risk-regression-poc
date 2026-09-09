"""
scripts/check_changes.py — verify Flow 2's LIVE release delta before you demo.

Prints the features & bug fixes pulled from Jira and the requirement changes
pulled from Confluence, so you can confirm the connection without running the
whole agent.

    # PowerShell
    $env:CHANGE_LIVE="1"
    $env:ATLASSIAN_SITE="your-site.atlassian.net"
    $env:ATLASSIAN_EMAIL="you@example.com"
    $env:ATLASSIAN_TOKEN="ATATT..."
    $env:JIRA_PROJECT_KEY="KAN"
    $env:CONFLUENCE_PAGE_ID="1572866"
    python scripts/check_changes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.change_source import use_live_changes, load_features_live, load_bugfixes_live  # noqa: E402
from agent.confluence_source import confluence_configured, load_requirements_live          # noqa: E402

if not use_live_changes():
    print("Live changes are OFF (set CHANGE_LIVE=1 and ATLASSIAN_SITE/EMAIL/TOKEN).")
    print("Flow 2 will read the CSVs in data/release_delta/ instead.")
    sys.exit(0)


def show(title, rows):
    print(f"\n{title}  ({len(rows)})")
    for r in rows:
        print(f"  {r['id']:8} {r['component']:10} {r['type']:11} {r['summary'][:52]}")


show("FEATURES  <- Jira", load_features_live())
show("BUG FIXES <- Jira", load_bugfixes_live())
if confluence_configured():
    show("REQUIREMENTS <- Confluence", load_requirements_live())
else:
    print("\nREQUIREMENTS <- Confluence: not configured "
          "(set CONFLUENCE_PAGE_ID or CONFLUENCE_SPACE_KEY+CONFLUENCE_PAGE_TITLE); "
          "Flow 2 will read requirements.csv.")
