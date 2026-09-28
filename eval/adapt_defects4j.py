"""eval/adapt_defects4j.py — turn a real Defects4J export into our corpus shape (item 8).

The benchmark does not care where the corpus came from, only that it has the
columns below. This adapter converts a Defects4J `query` export into exactly
that, so `--benchmark` runs on 850+ real bugs from real Java projects with no
other code change.

ON A MACHINE WITH NETWORK + JAVA 11 + PERL:

    git clone https://github.com/rjust/defects4j
    cd defects4j && ./init.sh && export PATH=$PWD/framework/bin:$PATH

    defects4j query -p Lang \\
        -q "classes.modified,tests.trigger,tests.relevant" \\
        -o lang.csv

    python eval/adapt_defects4j.py --in lang.csv --project Lang \\
        --out benchmark/defects4j_lang.csv

    python run_poc.py --benchmark --csv benchmark/defects4j_lang.csv

Defects4J's export has no header and its columns are, in order:
    bug_id, classes.modified, tests.trigger, tests.relevant
Multi-valued cells are ';'-separated, which is what we use too.

The one thing Defects4J does NOT give us is a COMPONENT, because Java projects
have packages rather than our notion of components. We derive one from the
modified class's package — `org.apache.commons.lang3.time.DateUtils` becomes
`time`. That is the change signal the selector keys on. Override the depth with
--component-from if a project's layout suits a different level.
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

FIELDS = ["bug_id", "component", "classes_modified", "kind", "outcome",
          "tests_trigger", "tests_trigger_cases", "tests_relevant", "n_trigger_cases"]


def component_from_class(fqcn, level="package-tail"):
    """Derive a component name from a fully-qualified Java class name."""
    parts = fqcn.strip().split(".")
    if len(parts) < 2:
        return fqcn.strip() or "unknown"
    if level == "class":
        return parts[-1]
    if level == "package":
        return ".".join(parts[:-1])
    # default: the last package segment, e.g. ...lang3.time.DateUtils -> "time"
    return parts[-2]


def test_file_of(test_id):
    """'org.apache.commons.lang3.time.DateUtilsTest::testRound' -> the class part."""
    return test_id.split("::")[0].strip()


def _split(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


def convert(in_path, project, out_path, level="package-tail"):
    rows_out = []
    with Path(in_path).open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for raw in reader:
            if not raw or not raw[0].strip():
                continue
            if raw[0].strip().lower() in ("bug_id", "bug.id"):
                continue                      # tolerate a header if one was added
            if len(raw) < 3:
                print(f"  skipping malformed row: {raw[:2]}", file=sys.stderr)
                continue
            bug_id, modified, trigger = raw[0], raw[1], raw[2]
            relevant = raw[3] if len(raw) > 3 else ""

            modified_classes = _split(modified)
            component = (component_from_class(modified_classes[0], level)
                         if modified_classes else "unknown")

            trigger_cases = _split(trigger)
            trigger_files = sorted({test_file_of(t) for t in trigger_cases})
            relevant_files = sorted(set(_split(relevant)))

            rows_out.append({
                "bug_id": f"{project}-{bug_id.strip()}",
                "component": component,
                "classes_modified": ";".join(modified_classes),
                "kind": "real-defect",
                # Defects4J bugs come with their triggering tests already known,
                # so anything with a trigger set is "detected" by construction.
                "outcome": "detected" if trigger_files else "undetected",
                "tests_trigger": ";".join(trigger_files),
                "tests_trigger_cases": ";".join(trigger_cases),
                "tests_relevant": ";".join(relevant_files),
                "n_trigger_cases": len(trigger_cases),
            })

    if not rows_out:
        sys.exit(f"No usable rows in {in_path}. Check the defects4j query output.")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows_out)

    comps = Counter(r["component"] for r in rows_out)
    no_trigger = [r["bug_id"] for r in rows_out if not r["tests_trigger"]]
    print(f"Converted {len(rows_out)} bugs from {project} -> {out}")
    print(f"  components ({len(comps)}): "
          f"{', '.join(f'{c}:{n}' for c, n in comps.most_common(12))}"
          f"{' ...' if len(comps) > 12 else ''}")
    if no_trigger:
        print(f"  {len(no_trigger)} bug(s) have no trigger test and will be "
              f"reported as undetectable, not scored.")
    print(f"\nNow run:  python run_poc.py --benchmark --csv {out}")
    return rows_out


def main():
    ap = argparse.ArgumentParser(
        description="Adapt a Defects4J query export into the benchmark corpus format")
    ap.add_argument("--in", dest="in_path", required=True,
                    help="CSV from: defects4j query -q 'classes.modified,tests.trigger,tests.relevant'")
    ap.add_argument("--project", required=True, help="project name, e.g. Lang or Cli")
    ap.add_argument("--out", required=True, help="destination CSV")
    ap.add_argument("--component-from", default="package-tail",
                    choices=["package-tail", "package", "class"],
                    help="how to derive a component from the modified class")
    args = ap.parse_args()
    convert(args.in_path, args.project, args.out, args.component_from)


if __name__ == "__main__":
    main()
