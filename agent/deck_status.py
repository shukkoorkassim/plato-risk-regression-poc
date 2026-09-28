"""agent/deck_status.py — what the deck claims vs what the code does (items 18-21).

A deck drifts away from its code the moment either changes, and the drift is
invisible until someone asks a question in the room. This maps each deck claim
to the command that proves it, and flags anything on a slide that is NOT backed
by real data.

    python run_poc.py --deck-status
"""
from .common import C
from . import status as S

DECK = "Risk_Based_Regression_AI_Agent_PoCv7.pptx"

SLIDES = [
    {"n": 11, "item": 18, "title": "We tried it on real software and measured the result",
     "claims": [
         ("bugs caught 13 of 13", "run_poc.py --benchmark", True),
         ("tests skipped 47%", "run_poc.py --benchmark", True),
         ("our old rule 45.6%", "run_poc.py --benchmark", True),
         ("bugs missed: none", "run_poc.py --benchmark --per-bug", True),
     ]},
    {"n": 12, "item": 19, "title": "Why you can believe these numbers",
     "claims": [
         ("real software, not a demo app", "run_poc.py --benchmark", True),
         ("we broke it on purpose", "run_poc.py --build-truth", True),
         ("exposed two blind spots of ours", "run_poc.py --benchmark", True),
         ("against a person — not yet real", "run_poc.py --compare-human", False),
         ("a bigger test bed is ready", "eval/adapt_defects4j.py --help", True),
     ]},
    {"n": 13, "item": 20, "title": "The clues it uses — and what comes next",
     "claims": [
         ("bugs that came back · working now", "run_poc.py --demo", True),
         ("how much the code moved · working now", "run_poc.py --signals", True),
         ("how connected the code is · working now", "run_poc.py --arch", True),
         ("what it learns from us · working now", "run_poc.py --feedback", True),
         ("how important the feature is · needs data", "run_poc.py --signals", False),
         ("how the sprint went · needs data", "run_poc.py --signals", False),
         ("why bugs happened · needs data", "run_poc.py --signals", False),
     ]},
    {"n": 14, "item": 21, "title": "Same agent, four different jobs",
     "claims": [
         ("before merging · 2 weeks, 3 tests", "run_poc.py --pr-check", True),
         ("overnight · 1 month, 6 tests", "run_poc.py --schedule daily", True),
         ("before you ship · 3 months, no limit", "run_poc.py --schedule sprint", True),
         ("the full sweep · 1 year, no limit", "run_poc.py --schedule quarterly", True),
     ]},
]


def report():
    S.banner("DECK vs CODE", f"items 18-21 · {DECK}")

    print(f"  {C.GREY}Four slides added after 'Since the demo'. The deck is now 15 "
          f"slides.\n  Every claim below maps to a command that produces it.{C.RESET}\n")

    total = backed = 0
    for sl in SLIDES:
        print(f"  {C.BOLD}slide {sl['n']}{C.RESET} {C.GREY}(item {sl['item']}){C.RESET}  "
              f"{sl['title']}")
        for claim, cmd, real in sl["claims"]:
            total += 1
            backed += bool(real)
            mark = (f"{C.GREEN}real data{C.RESET}" if real
                    else f"{C.YELLOW}placeholder{C.RESET}")
            print(f"      {mark:22} {claim:34} {C.CYAN}$ python {cmd}{C.RESET}")
        print()

    print(f"  {C.BOLD}{backed} of {total} deck claims are backed by real measured data."
          f"{C.RESET}")
    print(f"  {C.GREY}The {total - backed} that are not are labelled on the slide itself "
          f"— 'needs your data', 'not yet real',\n  and an amber marker rather than a green tick. "
          f"Nobody should have to read this\n  file to find out which numbers are "
          f"invented.{C.RESET}")

    print(f"\n  {C.BOLD}Still to do before this deck is presented externally{C.RESET}")
    S.say(S.PLACEHOLDER, "slide 12 · human-vs-agent",
          "labels are invented; run a real labelling session first")
    S.say(S.PLACEHOLDER, "slide 13 · the three 'needs your data' clues",
          "they run on invented CSVs; get the real exports")
    print(f"  {C.GREY}Both are already stated on the slides, so presenting as-is is "
          f"honest —\n  it just is not yet the strongest version of the story.{C.RESET}")
