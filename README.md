# Plato — Risk-Based Regression Selection & Testing (POC)

An SDET agent that picks the regression tests worth running — **two ways**:

- **Flow 1 · defect-history driven** — *what has broken before?* Reads past
  defects from the bug tracker, a defect CSV and git churn, scores each component
  by risk, and runs only the tests that cover the risky parts.
- **Flow 2 · change driven** — *what just changed?* Reads this release's user
  stories, bug fixes and requirement changes, scores each component by impact,
  and runs only the tests that cover the changed parts.

Both flows share **one agent** (`agent/common.py`): the same Reason → Act →
Observe loop, the same self-heal step. Flow 2 just adds a way to read what
changed and rank it — exactly as the POC deck describes.

The app under test is a tiny offline model of [saucedemo.com](https://www.saucedemo.com)
(`src/swaglabs.py`) with **two planted bugs**, one per flow, so you can watch each
agent read the source, fix it, and re-run until green.

```
Flow 1:  20 defects (3 sources) -> checkout HIGH 21.9 · login MED 6.3
         -> run 2 of 6 tests -> checkout fails (tax twice) -> agent fixes source -> green

Flow 2:  9 changes this release -> payments HIGH 20.6 · checkout MED 7.9
         -> run 2 of 6 tests -> payments fails (promo/tax) -> agent fixes source -> green
```

Notice the two flows pick **different** tests from **different** signals — Flow 1
lands on `login/checkout` (old defects), Flow 2 on `payments/checkout` (new
changes). That contrast is the whole point.

## Setup

Python 3.9+.

```bash
pip install -r requirements.txt
cp .env.example .env          # then put your ANTHROPIC_API_KEY in .env
```

## Run it

### 1. No API key — see both pipelines and the failing bugs

```bash
python dry_run.py             # both flows
python dry_run.py 1           # Flow 1 only
python dry_run.py 2           # Flow 2 only
```

Runs read → summarize → score → select → run and shows the planted bug failing.
It does **not** auto-fix — that's the agent's job.

### 2. Full agent — watch it self-heal

```bash
python run_poc.py --flow 1    # Flow 1 (defect-history driven)
python run_poc.py --flow 2    # Flow 2 (change driven)
python run_poc.py --flow both # both, back to back
python run_poc.py --dry-run   # no API key needed
```

You'll see the Reason → Act → Observe loop, a live token/cost meter, the ranking,
the selected subset, the failing test, the source fix, and a green re-run. A run
costs a few cents.

### 2b. Check everything works on this machine

```bash
python run_poc.py --selftest    # one command: deps, data, live Jira, the lot
python run_poc.py --showcase    # the whole story in the console, no API key
```

### 3. Reset between demos

The agents fix `src/swaglabs.py`. To re-plant the bugs and clear agent state:

```bash
python run_poc.py --reset     # or: python scripts/reset_demo.py
```

### 4. Optional — live browser tests against the real site

```bash
pip install playwright && playwright install chromium
pytest tests/test_live_saucedemo.py
```

## Wire it to real tools

- **Live Jira for Flow 1** — by default Flow 1 reads `data/jira_export.csv`. Set
  `JIRA_LIVE=1` plus your Atlassian credentials (see `.env.example`) and it pulls
  the resolved defects straight from Jira via REST + JQL instead — the CSV is no
  longer touched. Verify the connection first with:

  ```bash
  python scripts/check_jira.py
  ```

  The default JQL targets this POC's seeded issues
  (`labels = defect-history`); for a real project use the resolved-bugs basis
  `issuetype = Bug AND statusCategory = Done AND resolved >= -180d` via `JIRA_JQL`.
  Component and severity are read from the issue's Components/Priority fields, or
  from labels when those aren't set (as in a team-managed project).
- **Live release delta for Flow 2** — by default Flow 2 reads the CSVs in
  `data/release_delta/`. Set `CHANGE_LIVE=1` plus your credentials and it reads
  the delta live: **features & bug fixes from Jira** (labels `release-delta` +
  `feature`/`bugfix`) and **requirement changes from a Confluence page**
  (`CONFLUENCE_PAGE_ID`, any table row keyed `REQ-###`). Churn stays a CSV because
  it is git history. Verify the connection with:

  ```bash
  python scripts/check_changes.py
  ```

- **Seed Jira / Confluence** — `seed/seed_jira.py` and `seed/seed_confluence.py`
  create the sample stories, defects and requirement pages in a real Atlassian
  site. Or use the **Atlassian Rovo** connector in Claude and skip the scripts.
- **GitHub** — `scripts/push_github.sh <repo-url>` initialises and pushes this repo.

## Project layout

```
plato-risk-regression-poc/
├── src/swaglabs.py                    # app under test (2 planted bugs)
├── tests/                             # one file per component + test_map.json
│   ├── test_login.py  test_inventory.py  test_cart.py
│   ├── test_checkout.py               # catches the Flow 1 tax bug
│   ├── test_search.py  test_payments.py  # catches the Flow 2 promo bug
│   └── test_live_saucedemo.py         # optional live Playwright tests
├── data/
│   ├── jira_export.csv defects.csv git_churn.csv   # Flow 1 sources
│   └── release_delta/                 # Flow 2 sources
│       ├── stories.csv bugfixes.csv requirements.csv release_churn.csv
├── agent/
│   ├── common.py                      # shared agent loop + generic tools
│   ├── flow1_defect_history.py        # Flow 1 tools + risk model
│   └── flow2_change_driven.py         # Flow 2 tools + impact model
├── run_poc.py  dry_run.py  report.py  demo_selfheal.py   # entry points
├── seed/seed_jira.py  seed/seed_confluence.py
├── scripts/reset_demo.py  scripts/push_github.sh
└── docs/DEMO_RUNBOOK.md  docs/POC_MAPPING.md
```

## The two models

**Flow 1 — risk** `= severity × count × recency × (1 + churn)`
Blocker/critical weigh more; repeated breaks add up; a recent fix beats an old
one; heavily-churned code is likelier to regress.

**Flow 2 — impact** `= (2·features + 2·bug-fixes + 3·requirement-changes) × (1 + churn)`
The more a component changed this release — and the more different signals point
at it — the higher it ranks.

Every choice, run or skip, is logged with a clear reason.

## Self-healing: fix the test, or file a defect

A failing test has two very different causes, and the agent handles them
differently (see `combined_agent.py`):

- **The test is wrong** — the app is correct for the current requirement, but the
  test asserts an old value. The agent **fixes the test** (`fix_test`, restricted
  to `tests/`). It never weakens a real assertion to force a pass.
- **The app is wrong** — the test asserts the correct behaviour, but
  `src/swaglabs.py` produces the wrong result. The agent **files a Jira defect**
  (`report_defect_to_jira`) and leaves the source for a developer — it does not
  silently patch application code.

See it deterministically, no API key needed:

```bash
python demo_selfheal.py        # or: python run_poc.py --demo
```

It plants one of each — a stale case-sensitive `search` test (the app is correct
per REQ-413) and a real `checkout` double-tax bug — then fixes the test and files
the defect. The two files are backed up and restored, so your tree stays green.
By default the demo **files a real Jira defect** for the checkout bug (needs the
same `ATLASSIAN_SITE/EMAIL/TOKEN` that `JIRA_LIVE` uses) and prints the new issue
key; the first one filed was **KAN-47**. Add `REPORT_BUGS=0` to rehearse without
creating a ticket.

## Phase 1 additions (post-demo review)

Seven improvements delivered from the demo feedback:

- **Reopened defects raise risk** — a defect reopened after a fix weighs 1.6x more.
  Source: a `reopened` column in `data/*.csv`, or a `reopened` label on the Jira issue.
- **Efficiency metrics** — the selection step reports tests avoided and % of the suite skipped.
- **Decision explanations** — `python run_poc.py --demo` prints why each test was chosen.
- **Fixed evaluation set** — `python run_poc.py --eval` checks expected-vs-actual selection; re-run after any model/workflow/data change to catch drift.
- **Data-quality check** — `python run_poc.py --check-data` flags missing test-to-component coverage.
- **Human approval gates** (`agent/approvals.py`) — data quality, risk ratings, defect assignment, test-fix merge. `APPROVE_ALL=1` auto-approves them in a demo.
- **PR-based test fixes** (`agent/pr_flow.py`) — auto-fixes open a pull request for QA review and never write to main. `PR_MODE=1` with git + gh opens a real PR; otherwise a proposal is saved for review.
