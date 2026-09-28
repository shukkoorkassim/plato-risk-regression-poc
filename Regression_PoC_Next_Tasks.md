Risk-Based Regression AI Agent - Next Tasks
From the post-demo review (Shukkoor, Abhishek, Stuart, Satya)


Phase 1 - Quick wins   [DONE - implemented and demoable in: python run_poc.py --demo]

1. Add reopened-defect status as a risk factor in the defect score. (Shukkoor)   [DONE]
2. Add efficiency numbers: tests avoided and percent of suite reduced. (Shukkoor)   [DONE]
3. Make the agent explain how it weighted defects and changes for each choice. (Shukkoor)   [DONE]
4. Build a fixed evaluation set with expected results, and re-run it after any change. (Shukkoor, Abhishek)   [DONE - python run_poc.py --eval]
5. Add a data-quality check on test-to-component mappings before running. (Shukkoor, Abhishek, Satya)   [DONE - python run_poc.py --check-data]
6. Define where a human must approve: data quality, final risk ratings, defect assignment. (Shukkoor, Abhishek, Satya)   [DONE]
7. Make auto test-fixes open a pull request for QA review, never commit to main. (Shukkoor)   [DONE - PR_MODE=1 with git+gh]


Phase 2 - Evaluation and trust   [BUILT - see docs/BENCHMARK.md]

8. Pick a real public/open-source project with an old and a new release to test the agent on. (Abhishek, Shukkoor, Satya)   [DONE]
   - networkx 3.6.1 (BSD-3-Clause). 265 test files / ~7,000 tests. Measured scope:
     classes, utils, generators, linalg, tests = 67 files / 2,501 tests.
   - 16 defects seeded in real source. Ground truth is EXECUTED: patch, run the suite,
     record what actually failed. Nothing hand-asserted.
   - NOT Defects4J: this environment has no outbound network (github, gitlab and pypi
     are all refused by the egress proxy) and Defects4J also needs Java 11 + Perl.
     The adapter is written (eval/adapt_defects4j.py), so swapping to Defects4J later
     is a CSV change with no code change.
9. Compare the agent's selected tests against human choices, and study the differences. (Abhishek, Shukkoor, Satya)   [BUILT - labels pending]
   - python run_poc.py --compare-human. Scores BOTH sides against the executed ground
     truth, so it reports who was right, not just how much they overlapped.
   - PENDING: eval/human_selected.json holds PLACEHOLDER labels. A real labelling
     session is still needed before any human-vs-agent number is quoted externally.
10. Add accuracy numbers: how often the agent agrees with the expected selection. (Shukkoor, Abhishek)   [DONE]
    - python run_poc.py --benchmark. Recall / precision / F1 / agreement / reduction.
    - RESULT: the declared one-test-file-per-module map (what test_map.json does today)
      scores 45.6% recall. It misses more than half the tests that catch a bug and
      caught only 5 of 13 completely - while cutting 99% of the suite.
      Widening it with a MEASURED dependency map gives 100% recall at 47% reduction.
    - HEADLINE: 99% reduction is the wrong thing to optimise. Recall is.
    - CAVEAT: 16 seeded defects is a small sample. Do not quote as a general accuracy
      figure for the agent; that claim needs Defects4J's 850+ real bugs.
11. Flag risk areas that have no test, and improve the test-to-component coverage. (Shukkoor, Abhishek, Satya)   [DONE]
    - python run_poc.py --coverage. Ranks UNCOVERED / THIN / UNDETECTED, worst first.
    - UNDETECTED is executed proof rather than inference: NX-11 and NX-13 are real code
      changes that all 2,501 in-scope tests still pass.


Benchmark dataset - recommendation (for items 8, 9, 10)

Recommended: Defects4J  (https://github.com/rjust/defects4j)
- A standard research benchmark: 854 real bugs across 17 open-source Java projects
  (commons-lang, jfreechart, gson, jackson-databind, jsoup, mockito, Closure, ...).
- For EVERY bug it gives the ground truth we need, so we do NOT need human labelling
  for the first pass:
    - tests.trigger    = the tests that actually catch the bug  (the "should-run" set)
    - classes.modified = the code the fix changed  (our change / churn signal)
    - tests.relevant   = the tests that touch the modified code
- Why it is the best fit: the "right answer" is built in, so we get real recall /
  precision / agreement numbers automatically. Start small: Commons-Lang or
  Commons-Cli (~60-65 bugs) to keep it quick.

How to implement:
  1. Install once: git clone https://github.com/rjust/defects4j ; run ./init.sh
     (needs Java 11 + Perl).
  2. Export metadata as CSV:
     defects4j query -p Lang -q "classes.modified,tests.trigger,tests.relevant"
  3. Adapter turns that CSV into our input format:
     classes.modified -> components / churn (the change signal);
     tests.trigger    -> the ground-truth "should-run" set.
  4. Run the agent's change-driven selection per bug -> predicted tests.
  5. Compare predicted vs tests.trigger across all bugs -> recall (did it catch the
     test that finds the bug?), precision, and overall agreement %.
  Note: selection only needs the exported CSV, so we can benchmark hundreds of real
  bugs in Python with NO Java execution (only needed if we also want to RUN the tests).

Alternative (more relatable for the deck, but more manual work): Saleor
  (https://github.com/saleor/saleor) - a real Django/GraphQL e-commerce app whose
  components (checkout, cart, payments, catalog) mirror the SauceDemo demo story.
  It has releases + a test suite + labelled issues, but NO built-in bug-to-test
  mapping, so we would build the churn diff, label bugs by component, and do the
  human-vs-agent labelling by hand. Better as an illustrative example than as the
  accuracy benchmark.

Suggested split:
  - Use Defects4J for the accuracy KPI (items 9, 10) - rigorous, reproducible, no
    labelling bottleneck.
  - Keep Saleor as the relatable example in the deck, since its domain matches the demo.

Code to build next (ready to scaffold):
  - eval/benchmark_d4j.py  - reads a Defects4J query CSV, runs selection per bug,
    prints per-bug recall + overall agreement % (feeds the KPI slide accuracy tile).
  - eval/compare_human.py  - takes human_selected.json + the agent's selection and
    prints overlap + recall / precision / agreement / F1 (for item 9).
  - python run_poc.py --coverage  - coverage-gap report for item 11 (extends the
    existing data-quality check: flags high-risk components that are thinly covered).


Phase 3 - Later improvements   [ALL IMPLEMENTED - 3 run on placeholder data, and say so]

12. Weight business-important features higher than old, low-usage ones. (Satya, Shukkoor)   [PLACEHOLDER DATA]
    - Bounded multiplier (max 1.6x) wired into BOTH risk and impact scoring, and shown
      in the printed arithmetic. python run_poc.py --signals
    - data/business_value.csv is INVENTED. Real source: the product owner's criticality
      rating plus usage from analytics. The loader announces this on every run.
13. Add architectural risk (interfaces, boundaries, where defects cluster). (Shukkoor)   [PARTIAL]
    - Real fan-in / fan-out / instability / import-cycle analysis. python run_poc.py --arch
    - Runs for real against networkx: 315 modules, utils is the top blast radius
      (fan-in 130), 11 import cycles found.
    - Cannot run against our own product: src/swaglabs.py is ONE module, so there are no
      internal boundaries to measure. The command says so rather than printing zeros.
      Point --arch --path at a real multi-module repo for product numbers.
14. Look at sprint history and root-cause notes as extra risk signals. (Abhishek, Shukkoor, Satya)   [PLACEHOLDER DATA]
    - Both load, score and feed the model (caps 1.35x and 1.4x). python run_poc.py --signals
    - data/sprint_history.csv and data/rca_notes.csv are INVENTED. Real source: Jira
      sprint reports (carry-over, spillover) and the RCA field on closed defects.
15. Feed self-heal decisions and human reviews back to improve the agent over time. (Abhishek, Shukkoor)   [DONE]
    - Every self-heal outcome and approval decision is recorded and adjusts that
      component's weight on later runs. python run_poc.py --feedback
    - Weighting is asymmetric on purpose: a MISSED defect is +2.0, a false alarm -1.0,
      so the loop leans towards over-testing. Capped at +/-30%.
16. Run a quick smoke/sanity check on every pull request using change signals. (Abhishek, Shukkoor)   [DONE]
    - python run_poc.py --pr-check. Real git diff -> components -> bounded smoke subset.
    - Also names changed files that map to NO component: the gate is blind to those,
      and says so instead of implying it checked them.
17. Allow different schedules: quarterly, per sprint, daily, and per pull request. (Shukkoor)   [DONE]
    - python run_poc.py --schedules (compare) and --schedule <profile> (run).
    - Each profile changes lookback, threshold AND test budget, so selection really differs.


Deck updates   [DONE - Risk_Based_Regression_AI_Agent_PoCv6.pptx, now 15 slides]

18. Add a metrics slide: efficiency and accuracy numbers.   [DONE - new slide 11]
    - Accuracy tile now filled from the real benchmark: recall 100%, suite cut 47%,
      today's map 45.6%, 13/13 caught in full.
19. Add an evaluation slide: historical benchmark and human vs agent comparison.   [DONE - new slide 12]
    - Marked ON THE SLIDE that the human comparison is still pending real labels.
20. Show future risk signals (reopened defects, business impact, architecture, sprint/RCA) as a roadmap.   [DONE - new slide 13]
    - Four signals marked live (green), three marked wired (amber) to match the code.
21. Add a slide on when it runs: quarterly, sprint, daily, pull request.   [DONE - new slide 14]

    python run_poc.py --deck-status  maps every deck claim to the command that proves it
    and flags which are still placeholder.


Suggested order

- DONE: Phase 1 (items 1-7) and the metrics slide (18).
- DONE: Phase 2 benchmark harness, accuracy numbers and coverage-gap report (8, 10, 11).
  Human-comparison tooling built (9), still needs a real labelling session.
- Now: (a) run the human labelling session to finish item 9;
       (b) re-run the benchmark on real Defects4J data on a machine with network +
           Java 11 + Perl - the adapter is already written;
       (c) decide whether to adopt the measured dependency map in the product's own
           selector, since the benchmark shows the current map misses over half the
           tests that catch a bug.
- Next: fill the accuracy tile on slide 11 and add the evaluation slide (19).
- Later: items 12-17, then slides 20-21.


Open item carried over from Phase 1   [CLOSED]

- The live agent flows used to hand the model a raw write_file tool, so the approval
  gates and PR flow only applied to the scripted demo. Now closed: the live flows are
  wired to agent/guarded_tools.py, so a test write becomes a pull request, a source
  write needs approval, and anything outside src/ and tests/ is refused outright.
  The model never receives an unguarded write. python run_poc.py --gates proves it by
  attempting a forbidden write and showing the file is untouched.


Status at a glance

    python run_poc.py --status         all 21 items, with the command that proves each
    python run_poc.py --status --gaps  only what is unfinished, and why
    python run_poc.py --verify         actually RUNS the command behind every item

  17 of 21 DONE, 1 PARTIAL, 3 PLACEHOLDER-DATA, 0 BLOCKED.

  The 4 unfinished items all have working, tested code. What is missing is real DATA
  or a human step, never the mechanism:
    9  needs a real human labelling session
    12 needs real business criticality / usage data
    13 needs a multi-module repo (our product source is a single file)
    14 needs a real Jira sprint export and the RCA field

  Every placeholder announces itself in the console on every run, naming the real
  source that should replace it. Nothing invented reaches a number quietly.


Notes

- All of these are doable. Nothing is blocked.
- Phase 1 is complete, including the governance gap that was open at the last update.
- Defects4J removes the human-labelling bottleneck for the accuracy benchmark - it is
  the key step for real trust, so start it early.
