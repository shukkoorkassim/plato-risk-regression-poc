# Phase 2 — Evaluation and trust

Items 8–11 of `Regression_PoC_Next_Tasks.md`. This document explains what the
benchmark measures, what it found, and what it does not prove.

## What we benchmark against

**networkx 3.6.1** (BSD-3-Clause) — a real, widely used open-source library.
Not a fixture written for this PoC.

| | |
|---|---|
| Project | networkx 3.6.1 |
| Test suite | 265 test files, ~7,000 tests |
| Measured scope | `classes`, `utils`, `generators`, `linalg`, `tests` — 67 test files, 2,501 tests |
| Seeded defects | 16, in real source |
| Ground truth | **Executed.** Patch, run the suite, record what actually failed. |

### Why a scope, and why this one

The full suite takes over two minutes and the harness runs it once per seeded
bug, so the benchmark measures a named subset that runs in ~21s. Defects4J
scopes per project for the same reason. **The number is only meaningful next to
the scope**, so every report prints it.

The subset is not arbitrary. `classes/graph.py` is the base that the generators,
matrix builders and converters all depend on, so a defect seeded there really
does propagate across component boundaries. That propagation is the thing the
accuracy metric exists to measure.

### Why not Defects4J

Defects4J is still the right benchmark for a headline accuracy number, and the
code is ready for it (see below). It could not be used here because **this
sandbox has no outbound network** — `github.com`, `gitlab.com` and `pypi.org`
are all refused by the egress proxy — and Defects4J additionally needs Java 11
and Perl. networkx was already installed locally, which is what made it usable.

## The two strategies compared

| Strategy | Rule |
|---|---|
| `declared` | One test file per changed module — what `tests/test_map.json` encodes today. A change in `classes/graph.py` selects `classes/tests/test_graph.py`. |
| `impact` | The declared pick, widened by a **measured** dependency map: which test files actually execute the changed module, recorded by tracing a real run (`benchmark/nx_impact.py`). |

## Results

Run `python run_poc.py --benchmark`.

| Metric | `declared` | `impact` |
|---|---|---|
| **Recall** — of the tests that catch a bug, how many we ran | **45.6%** | **100.0%** |
| Precision — of the tests we ran, how many were needed | 84.6% | 29.6% |
| F1 | 49.6% | 36.7% |
| Agreement — bugs caught completely | 38.5% (5/13) | 100% (13/13) |
| Suite reduction | 99% | 47% |

### What this means

**The headline is that 99% reduction is the wrong thing to optimise.** The
declared map — the convention the PoC ships with — cuts the suite to almost
nothing, and misses more than half the tests that would actually catch a
regression. It caught only 5 of 13 bugs completely. A cheap test run that ships
the bug is not a saving.

Recall is the metric to hold the agent to. Precision and reduction are the
budget you spend to get it.

Two failures are worth calling out because they are not subtle:

- **NX-9** (`utils/union_find.py`) scored **0% recall** under `declared`. The
  test file is `test_unionfind.py`, not `test_union_find.py`. A one-character
  naming difference and the convention selects nothing.
- **NX-14** (`linalg/laplacianmatrix.py`) also scored **0%**. The tests live in
  `test_laplacian.py`.

Name-convention mapping is brittle in exactly the way a measured dependency map
is not.

### Honest caveats

- **47% reduction is modest**, and that is the real trade. For a base module
  like `classes/graph.py`, 56 of 67 test files genuinely touch it — no selector
  can be both correct and cheap there. The saving is real for leaf modules and
  small for foundational ones, which is what you would expect and what a slide
  claiming "80% fewer tests" would be hiding.
- **16 seeded defects is a small sample.** The direction is clear and the
  mechanism is understood, but do not quote these percentages as a general
  accuracy figure for the agent. Defects4J's 850+ real bugs is what that claim
  needs.
- **Seeded defects are not real defects.** They are realistic single-point
  changes, but Defects4J bugs are drawn from real project history.

## Three outcomes, not two

A seeded defect can do one of three things, and collapsing them would distort
the metric:

| Outcome | Meaning | Scored? |
|---|---|---|
| `detected` | Tests failed. We have a ground-truth set. | Yes |
| `undetected` | Every in-scope test still passed. **A coverage hole.** | No — reported by `--coverage` |
| `hang` | The suite never finished. | No — CI catches it, but there is no failure list |

- `NX-11`, `NX-13` — **undetected**. A real change that the entire 2,501-test
  suite passes through. This is executed proof of a coverage gap, not inference.
- `NX-4` — **hangs**. Making `has_edge` return true for any node pair sends the
  generators into runaway graph construction. Detected in CI, unscoreable here.

## Commands

```bash
python run_poc.py --build-truth      # re-run the corpus (~6 min); executes the suite per bug
python run_poc.py --benchmark        # accuracy: recall / precision / F1 / agreement
python run_poc.py --benchmark --per-bug
python run_poc.py --compare-human    # agent vs human selection  (item 9)
python run_poc.py --coverage         # risk areas with no test   (item 11)
```

## Swapping in real Defects4J

Nothing in the benchmark is networkx-specific — it reads a CSV. On a machine
with network, Java 11 and Perl:

```bash
git clone https://github.com/rjust/defects4j
cd defects4j && ./init.sh && export PATH=$PWD/framework/bin:$PATH

defects4j query -p Lang \
    -q "classes.modified,tests.trigger,tests.relevant" -o lang.csv

python eval/adapt_defects4j.py --in lang.csv --project Lang \
    --out benchmark/defects4j_lang.csv

python run_poc.py --benchmark --csv benchmark/defects4j_lang.csv
```

Selection only needs the exported CSV, so hundreds of real bugs can be scored
in Python with no Java execution.

## Safety

The benchmark **never mutates the installed networkx**. `nx_project.ensure_workdir()`
clones the package to `~/.cache/risk-agent-benchmark/` and every patch is applied
there, with that directory first on `sys.path`. After a full run the working copy
is byte-identical to the installed package (`diff -rq` is clean). If a run is
interrupted mid-patch, the next one detects the dirty copy and re-clones.

Two failure modes are handled explicitly because both silently corrupt results:

- **Stale bytecode.** Several mutations are the same length as the original and
  are written within the same second. CPython keys `.pyc` validity on
  `(mtime, size)`, so a restore can appear to fail and every later bug inherits
  the corruption. The harness purges `__pycache__` and runs with `-B`.
- **Orphaned workers.** A hung run leaves pytest processes holding the working
  copy; the harness reaps them before the next bug.

## Item 9 — human comparison

`eval/human_selected.json` currently holds **placeholder labels**, clearly marked
as such. They make the comparison runnable today; they are not a real labelling
session and no human-vs-agent number should be quoted externally until they are
replaced.

To do it properly: show a QA engineer the `bug_id`, `component`,
`classes_modified` and `kind` columns of `benchmark/ground_truth.csv` **without**
the `tests_trigger` column, ask which test files they would run, and paste the
answers in. The script then scores both sides against the executed ground truth,
so it reports who was *right*, not merely how much they overlapped.
