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


Phase 2 - Evaluation and trust

8. Pick a real public/open-source project with an old and a new release to test the agent on. (Abhishek, Shukkoor, Satya)
9. Compare the agent's selected tests against human choices, and study the differences. (Abhishek, Shukkoor, Satya)
10. Add accuracy numbers: how often the agent agrees with the expected selection. (Shukkoor, Abhishek)
11. Flag risk areas that have no test, and improve the test-to-component coverage. (Shukkoor, Abhishek, Satya)


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


Phase 3 - Later improvements

12. Weight business-important features higher than old, low-usage ones. (Satya, Shukkoor)
13. Add architectural risk (interfaces, boundaries, where defects cluster). (Shukkoor)
14. Look at sprint history and root-cause notes as extra risk signals. (Abhishek, Shukkoor, Satya)
15. Feed self-heal decisions and human reviews back to improve the agent over time. (Abhishek, Shukkoor)
16. Run a quick smoke/sanity check on every pull request using change signals. (Abhishek, Shukkoor)
17. Allow different schedules: quarterly, per sprint, daily, and per pull request. (Shukkoor)


Deck updates

18. Add a metrics slide: efficiency and accuracy numbers.   [DONE - slide 11 "Fewer tests - measured" (accuracy tile pending benchmark)]
19. Add an evaluation slide: historical benchmark and human vs agent comparison.
20. Show future risk signals (reopened defects, business impact, architecture, sprint/RCA) as a roadmap.
21. Add a slide on when it runs: quarterly, sprint, daily, pull request.


Suggested order

- DONE: Phase 1 (items 1-7) and the metrics slide (18).
- Now: set up the Defects4J benchmark (8), build eval/benchmark_d4j.py, get the first
  accuracy number (9, 10), and add the coverage-gap report (11).
- Next: fill the accuracy tile on slide 11 and add the evaluation slide (19).
- Later: items 12-17, then slides 20-21.


Notes

- All of these are doable. Nothing is blocked.
- Phase 1 is complete. The main remaining limits are: getting the data (12, 13, 14),
  and more research for architecture and auto-learning (13, 15).
- Defects4J removes the human-labelling bottleneck for the accuracy benchmark - it is
  the key step for real trust, so start it early.
