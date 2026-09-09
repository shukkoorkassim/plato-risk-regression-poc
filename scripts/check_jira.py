"""
scripts/check_jira.py — verify the live Jira connection before you demo.

Pulls the defects with the current settings and prints them normalised, so you
can confirm credentials + JQL work without running the whole agent.

    # PowerShell
    $env:JIRA_LIVE="1"
    $env:ATLASSIAN_SITE="your-site.atlassian.net"
    $env:ATLASSIAN_EMAIL="you@example.com"
    $env:ATLASSIAN_TOKEN="ATATT..."
    $env:JIRA_PROJECT_KEY="KAN"
    python scripts/check_jira.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.jira_source import use_live_jira, load_jira_live, _cfg  # noqa: E402

if not use_live_jira():
    print("Live Jira is OFF (set JIRA_LIVE=1 and ATLASSIAN_SITE/EMAIL/TOKEN).")
    print("Flow 1 will read data/jira_export.csv instead.")
    sys.exit(0)

c = _cfg()
jql = c["jql"] or f'project = {c["project"]} AND labels = defect-history ORDER BY resolved DESC'
print(f"Site : {c['site']}")
print(f"JQL  : {jql}\n")

defects = load_jira_live()
print(f"Pulled {len(defects)} issues from Jira:\n")
for d in defects:
    print(f"  {d['id']:8} {d['component']:10} {d['severity']:9} {d['resolved']}  {d['summary'][:50]}")
if not defects:
    print("  (none — check the JQL and that the issues are labelled)")
