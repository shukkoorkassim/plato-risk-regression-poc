# Demo Cheat-Sheet — Risk-Based Regression POC

Everything runs from **inside** `plato-risk-regression-poc`, in **one** PowerShell window.

## 0 · Pre-flight (before the audience)
```
cd $HOME\Desktop\risk-Agent\plato-risk-regression-poc
python -m pip install -r requirements.txt

# keys for this window (skip any you set permanently with setx / .env)
$env:ANTHROPIC_API_KEY  = "sk-ant-...your key..."
$env:ATLASSIAN_SITE     = "your-site.atlassian.net"
$env:ATLASSIAN_EMAIL    = "you@example.com"
$env:ATLASSIAN_TOKEN    = "ATATT...your token..."
$env:JIRA_PROJECT_KEY   = "KAN"
$env:CONFLUENCE_PAGE_ID = "1572866"
$env:JIRA_LIVE   = "1"
$env:CHANGE_LIVE = "1"

python run_poc.py --reset        # plant the bugs fresh
python scripts/check_jira.py     # sanity: 9 defects from Jira
python scripts/check_changes.py  # sanity: 4 features + 3 fixes (Jira), 3 requirements (Confluence)
```
Open two browser tabs: the Jira POC issues and the Confluence page.

> **What the switches mean:** `JIRA_LIVE=1` tells **Flow 1** to read defects live from Jira instead of `data/jira_export.csv`. `CHANGE_LIVE=1` tells **Flow 2** to read its release delta live — stories & bug-fixes from Jira, requirements from Confluence — instead of the CSVs. Both default to off (CSV mode) and only turn on when the Atlassian credentials are also set; otherwise they safely fall back to the files.

## 1 · The pitch (talk, 20s)
"Re-running every regression test each release is slow. This agent decides which tests are worth running — two different ways — runs only those, fixes any real bug it finds, and reads its inputs live from Jira and Confluence."

## 2 · Inputs are live (Jira + Confluence)
```
python scripts/check_jira.py
python scripts/check_changes.py
```
Flip to the browser tabs — same KAN issues, same REQ rows. "Not local files — this is your real Jira and Confluence."

## 3 · The selection report (2 vs 3)
```
python run_poc.py --report
```
Shows, per flow: RANKED → SELECTED → FILTERED → EXECUTED, then a comparison:
- Flow 1 → **2** tests: checkout, login  (from past defects)
- Flow 2 → **3** tests: payments, checkout, search  (from what changed)
- only Flow 1: login · only Flow 2: payments, search · shared: checkout
"Same agent, two signals, two different test sets — and different sizes."
(The EXECUTED failures here are the planted bugs — that's the 'before'.)

## 4 · Flow 1 self-heals (live Jira)
```
python risk_agent.py
```
Step 1 says `jira (live): 9`. It picks checkout+login → runs → checkout fails → reads `src/swaglabs.py` → fixes the double-tax → re-runs → green → summary.

## 5 · Flow 2 self-heals (live Jira + Confluence)
```
python run_poc.py --reset
python change_agent.py
```
Step 1 says `feature: 4 (jira (live))`, `requirement: 3 (confluence (live))`. Picks payments+checkout+search → fixes the promo bug → green (search passes — it changed, we re-tested it, it's fine).

## 6 · Green report (the 'after')
```
python run_poc.py --report
```
Now EXECUTED shows all passing.

## 7 · Close
"One agent, two signals — past defects and current changes — read live from Jira and Confluence. Each produces a short, justified, auditable test run, and each fixes the bug it finds."

---

## Reset between runs
```
python run_poc.py --reset
```

## Safety nets
- Live call hiccups? `\$env:JIRA_LIVE="0"; \$env:CHANGE_LIVE="0"` → reads CSVs, demo still runs.
- No API key? `python dry_run.py` → full pipeline + failing bug, no key needed (you narrate the fix).
- Want the whole story auto-narrated? `python run_poc.py --demo` — pulls & ranks both signals, selects the union, then self-heals: **fixes the stale test** and **logs the real app defect to Jira** (prints the new KAN-###). With your Atlassian creds set it files a real ticket each run; add `REPORT_BUGS=0` to rehearse without creating tickets. Backs up and restores its files.

## Command reference
| What | Command |
|---|---|
| Reset (plant bugs) | `python run_poc.py --reset` |
| Verify live Jira | `python scripts/check_jira.py` |
| Verify live Jira+Confluence | `python scripts/check_changes.py` |
| Combined report | `python run_poc.py --report` |
| No-key pipeline | `python dry_run.py` |
| Full self-heal demo (no key) | `python run_poc.py --demo` |
| Flow 1 self-heal | `python risk_agent.py` |
| Flow 2 self-heal | `python change_agent.py` |
