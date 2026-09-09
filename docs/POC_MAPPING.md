# POC Deck → Implementation Mapping

How each slide of `PlatoTech_Regression_POC-v2.pptx` shows up in the code.

| Deck slide | Concept | Where it lives |
|---|---|---|
| 1 — Two flows | Defect-history driven & change driven | `risk_agent.py` (Flow 1), `change_agent.py` (Flow 2), shared `agent/common.py` |
| 2 — The problem | Two questions, two signals | `dry_run.py` runs both; README "The two models" |
| 3 — Flow 1 pipeline | tidy up → rate risk → pick tests → run | `agent/flow1_defect_history.py`: `read_defect_sources` → `summarize_defects` → `score_risk` → `select_regression_tests` → `run_pytest` |
| 4 — Flow 1 risk model | `risk = severity × count × recency × (1 + churn)` | `score_risk()` in `flow1_defect_history.py`; `SEVERITY_WEIGHT`, `LOOKBACK_DAYS` |
| 4 — RUN vs SKIP with a reason | Every choice logged | `select_regression_tests()` prints RUN/skip + reason; `run_pytest` only runs the subset |
| 5 — Flow 2 change types | features, bug fixes, requirement changes | `data/release_delta/stories.csv`, `bugfixes.csv`, `requirements.csv`; loaders in `flow2_change_driven.py` |
| 5 — what changed · which part · where from | Per-change record | `summarize_changes()` prints id, component, source, summary |
| 6 — Flow 2 pipeline | find parts → rank by impact → pick & run | `read_release_delta` → `summarize_changes` → `score_impact` → `select_change_tests` → `run_pytest` |
| 6 — impact ranking | most-changed / most-linked first | `score_impact()`: `(2·feat + 2·fix + 3·req) × (1 + churn)` |
| 7 — POC plan | one shared agent; Flow 2 adds reading + ranking changes | `agent/common.py` is the shared base; each flow adds data tools + system prompt |
| 8 — Conditions | changes traceable to components; tests mapped to components; agent can read inputs | component column in every CSV; `tests/test_map.json`; loaders in each flow |
| 8 — Challenges | only as good as the links; can't test what isn't there; needs tuning | thresholds in `select_*` (3.0 / 4.0), weights in each model — all tunable in one place |

## The two planted bugs (self-heal proof)

| Bug | Function | Caught by | Fixed by |
|---|---|---|---|
| Tax applied twice | `checkout_totals` in `src/swaglabs.py` | `tests/test_checkout.py` | Flow 1 agent |
| Promo ignored / tax on pre-discount subtotal | `process_payment` in `src/swaglabs.py` | `tests/test_payments.py` | Flow 2 agent |

`scripts/reset_demo.py` restores both from `scripts/_swaglabs_baseline.py`.

## Tuning knobs (deck slide 8: "needs tuning at the start")

- Flow 1 risk: `SEVERITY_WEIGHT`, `LOOKBACK_DAYS`, threshold in `select_regression_tests` (default 3.0).
- Flow 2 impact: `CHANGE_WEIGHT`, churn normaliser, threshold in `select_change_tests` (default 4.0).
- Model + pricing: `ANTHROPIC_MODEL` env, `PRICE_*` in `agent/common.py`.
