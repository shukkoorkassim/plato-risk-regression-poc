# Demo Runbook — Risk-Based Regression POC

A tight 8–10 minute script for showing both flows. Everything runs offline; the
only external call is to the Anthropic API for the two live agent runs.

## Before you start

```bash
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY
python run_poc.py --reset   # make sure both bugs are planted
```

Keep one terminal ready. A full agent run is ~9 steps and costs a few cents.

---

## Act 0 — the problem (30s, deck slides 1–2)

"We can't re-run the whole suite every release. Cherry-picking by gut feel leaves
no audit trail. This agent answers two questions, each with its own signal —
*what has broken before?* and *what just changed?*"

## Act 1 — Flow 1, defect-history driven (3 min, deck slides 3–4)

```bash
python dry_run.py 1
```

Talk track:
- **read → summarize**: 20 defects tidied from three sources (Jira, CSV, git).
- **score_risk**: `checkout` is HIGH (21.9) — a blocker + criticals, recent, high
  churn. `login` is MED. cart / inventory / search are LOW.
- **select**: only `checkout` + `login` tests are chosen — 2 of 6. Every skip has
  a reason.
- **run**: `checkout` fails — the planted "tax applied twice" bug.

Now the self-heal:

```bash
python risk_agent.py
```

"The agent reads `src/swaglabs.py`, finds the double-tax line, fixes it — *not*
the test — and re-runs until the selected suite is green. It ends with a
release-readiness summary."

## Act 2 — Flow 2, change driven (3 min, deck slides 5–6)

```bash
python run_poc.py --reset
python dry_run.py 2
```

Talk track:
- **read_release_delta**: 9 changes this release — 4 features, 3 bug fixes, 2
  requirement changes, plus churn.
- **summarize_changes**: for each change — *what changed · which component · where
  it came from*.
- **score_impact**: `payments` is HIGH (20.6) — new promo feature, a tax
  requirement change, heavy churn — even though it has almost no defect history.
  `checkout` is MED. `search` is LOW.
- **select**: `payments` + `checkout` — a **different** set than Flow 1, from a
  **different** signal.
- **run**: `payments` fails — the planted promo/tax bug.

Self-heal:

```bash
python change_agent.py
```

"Same agent, same self-heal — this time on the changed area."

## Act 3 — the point (1 min, deck slides 7–8)

- Flow 1 → `login / checkout` (old defects). Flow 2 → `payments / checkout` (new
  changes). One shared agent, two signals, two focused test runs.
- Feasibility (slide 8): it works today when changes are traceable to components
  and tests are mapped to components (`tests/test_map.json`). It can only run tests
  that exist; it needs a little tuning against real releases at first.

## Reset

```bash
python run_poc.py --reset
```

## If the API key isn't handy

Do the whole demo with `python dry_run.py` — you still get the read → score →
select → run story and the failing bug for both flows; you just narrate the fix
instead of watching it.
