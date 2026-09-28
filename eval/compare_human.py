"""eval/compare_human.py — agent vs human selection (Phase 2 · item 9).

Item 9 asks us to compare what the agent picked against what a human picked and
study the differences. The interesting part is not the agreement score, it is
the two disagreement buckets:

    human-only   the human ran it, the agent skipped it. If a bug lives there,
                 the agent would have shipped it. This is the expensive mistake.
    agent-only   the agent ran it, the human skipped it. Cheap if it is noise —
                 but when the ground truth says a bug lives there, the AGENT was
                 right and the human missed it. Worth showing on the deck.

With a ground-truth corpus available we score both sides against it, so the
comparison says who was correct rather than only how much they overlapped.

    python run_poc.py --compare-human
    python run_poc.py --compare-human --human eval/human_selected.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.common import C                                      # noqa: E402
from eval.benchmark_d4j import (                                # noqa: E402
    DEFAULT_CSV, load_rows, all_tests, select_impact, _split,
)

HUMAN = Path(__file__).resolve().parent / "human_selected.json"


def prf(pred, truth):
    p, t = set(pred), set(truth)
    hit = len(p & t)
    recall = hit / len(t) if t else None
    precision = hit / len(p) if p else 0.0
    return recall, precision


def compare(human_path, csv_path):
    human = json.loads(Path(human_path).read_text())
    selections = human.get("selections", human)
    rows = {r["bug_id"]: r for r in load_rows(csv_path)}
    suite = all_tests(load_rows(csv_path))

    print(f"{C.BOLD}Agent vs human selection{C.RESET}  ·  "
          f"{len(selections)} case(s)  ·  {Path(human_path).name}")
    if human.get("labelled_by"):
        print(f"{C.GREY}labelled by {human['labelled_by']}{C.RESET}")
    print()

    tot_overlap = tot_union = 0
    agent_recalls, human_recalls = [], []
    agent_saves, human_saves = [], []

    for bug_id, picked in sorted(selections.items()):
        row = rows.get(bug_id)
        if row is None:
            print(f"  {C.YELLOW}skip{C.RESET} {bug_id} — not in the corpus")
            continue
        agent = set(select_impact(row, suite))
        person = set(picked)
        truth = set(_split(row["tests_trigger"]))

        overlap = agent & person
        union = agent | person
        tot_overlap += len(overlap)
        tot_union += len(union)
        jaccard = len(overlap) / len(union) if union else 1.0

        a_rec, a_prec = prf(agent, truth)
        h_rec, h_prec = prf(person, truth)
        if a_rec is not None:
            agent_recalls.append(a_rec)
            human_recalls.append(h_rec)

        agent_only = sorted(agent - person)
        human_only = sorted(person - agent)

        # who was right about the disagreements?
        agent_only_useful = sorted(set(agent_only) & truth)
        human_only_useful = sorted(set(human_only) & truth)
        if agent_only_useful:
            agent_saves.append((bug_id, agent_only_useful))
        if human_only_useful:
            human_saves.append((bug_id, human_only_useful))

        head = f"  {C.BOLD}{bug_id}{C.RESET} {C.GREY}({row['component']} · {row.get('kind','')}){C.RESET}"
        print(f"{head}  agreement {jaccard * 100:.0f}%")
        print(f"      agent {len(agent):2} tests   recall {_fmt(a_rec)}   "
              f"human {len(person):2} tests   recall {_fmt(h_rec)}")
        if agent_only:
            tag = (f"{C.GREEN}{len(agent_only_useful)} of them catch the bug{C.RESET}"
                   if agent_only_useful else f"{C.GREY}none of them find anything{C.RESET}")
            print(f"      {C.CYAN}agent only ({len(agent_only)}):{C.RESET} "
                  f"{_names(agent_only)}  {tag}")
        if human_only:
            tag = (f"{C.RED}<- the agent would have MISSED this{C.RESET}"
                   if human_only_useful else f"{C.GREY}no bug there{C.RESET}")
            print(f"      {C.YELLOW}human only ({len(human_only)}):{C.RESET} "
                  f"{_names(human_only)}  {tag}")
        print()

    n = len(agent_recalls) or 1
    print(f"  {C.BOLD}Overall{C.RESET}")
    print(f"    overlap (Jaccard)   {tot_overlap / tot_union * 100 if tot_union else 100:.1f}%")
    print(f"    agent recall        {sum(agent_recalls) / n * 100:.1f}%")
    print(f"    human recall        {sum(human_recalls) / n * 100:.1f}%")
    if agent_saves:
        print(f"    {C.GREEN}agent caught what the human skipped:{C.RESET} "
              f"{len(agent_saves)} case(s)")
        for bug_id, tests in agent_saves:
            print(f"      {C.GREEN}+{C.RESET} {bug_id}: {len(tests)} test file(s) "
                  f"the human skipped that do catch it — {_names(tests, 3)}")
    if human_saves:
        print(f"    {C.RED}human caught what the agent skipped:{C.RESET} "
              f"{len(human_saves)} case(s)")
        for bug_id, tests in human_saves:
            print(f"      {C.RED}-{C.RESET} {bug_id}: {len(tests)} test file(s) "
                  f"the agent skipped that do catch it — {_names(tests, 3)}")
    if not human_saves:
        print(f"    {C.GREEN}the agent missed nothing the human caught.{C.RESET}")


def _fmt(x):
    return "  n/a" if x is None else f"{x * 100:3.0f}%"


def _names(paths, limit=4):
    """Readable file list. These sets run to 50+ entries on a base module —
    printing them all buries the point."""
    names = [Path(p).name for p in paths]
    shown = ", ".join(names[:limit])
    return shown + (f" +{len(names) - limit} more" if len(names) > limit else "")


def main():
    ap = argparse.ArgumentParser(description="Compare agent selection against human labels (item 9)")
    ap.add_argument("--human", default=str(HUMAN), help="human_selected.json")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="ground-truth corpus")
    args = ap.parse_args()
    if not Path(args.human).exists():
        sys.exit(f"{C.RED}No human labels at {args.human}.{C.RESET}\n"
                 "Create one: {\"selections\": {\"Bug-1\": [\"benchmark/btests/test_x.py\"]}}")
    compare(args.human, args.csv)


if __name__ == "__main__":
    main()
