"""agent/console.py — the shared look: box drawing, bars, tables, banners.

Both --showcase and --demo print the same kinds of thing: a ranked table with a
bar per row, a cut-off drawn through a list, a boxed heading. This module is the
one copy of that, so the two commands cannot drift into looking like different
products.

Everything renders twice: once with Unicode box characters, once with plain
ASCII for consoles that cannot show them. Call set_box() once at the start of a
run; every helper below then uses that choice.
"""
import sys

W = 76                      # content width, shared by both commands


class Box:
    """Box-drawing characters, with an ASCII fallback for old Windows consoles."""
    def __init__(self, ascii_only=False):
        if ascii_only:
            self.tl, self.tr, self.bl, self.br = "+", "+", "+", "+"
            self.h, self.v, self.hh = "-", "|", "="
            self.dot, self.arrow, self.tick, self.cross = "*", "->", "+", "x"
            self.bar_full, self.bar_empty = "#", "."
        else:
            self.tl, self.tr, self.bl, self.br = "┌", "┐", "└", "┘"
            self.h, self.v, self.hh = "─", "│", "═"
            self.dot, self.arrow, self.tick, self.cross = "•", "→", "✓", "✗"
            self.bar_full, self.bar_empty = "█", "░"


def supports_unicode():
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


_B = Box(not supports_unicode())


def set_box(ascii_only=False):
    """Choose the character set for this run and return it."""
    global _B
    _B = Box(ascii_only or not supports_unicode())
    return _B


def box():
    return _B


# ---------------------------------------------------------------------------
from .common import C  # noqa: E402  (imported late: C is plain data)


def banner(title, subtitle=""):
    print()
    print(f"{C.MAGENTA}{_B.hh * W}{C.RESET}")
    print(f"{C.BOLD}  {title}{C.RESET}")
    if subtitle:
        print(f"{C.GREY}  {subtitle}{C.RESET}")
    print(f"{C.MAGENTA}{_B.hh * W}{C.RESET}")


def rule(width=None):
    print(f"  {C.GREY}{_B.h * (width or W - 4)}{C.RESET}")


def bar(value, peak, width=26, colour=None):
    """A proportional bar. Guards against a zero or negative peak."""
    n = 0 if peak <= 0 else max(0, min(width, round(width * value / peak)))
    colour = colour or C.CYAN
    return f"{colour}{_B.bar_full * n}{C.GREY}{_B.bar_empty * (width - n)}{C.RESET}"


def kv(label, value, note=""):
    print(f"    {label:<26} {C.BOLD}{value}{C.RESET}"
          + (f"   {C.GREY}{note}{C.RESET}" if note else ""))


def tier_of(value, threshold):
    """HIGH / MED / low, with MED starting exactly at the selection cut-off.

    Tying the tier boundary to the cut-off matters: before, a component could
    read [MED] and still be skipped, which looks like the tool contradicting
    itself. Now MED or better always means selected, and low always means
    skipped — the label and the decision say the same thing.
    """
    if value >= max(threshold * 1.6, threshold + 3):
        return "HIGH", C.RED
    if value >= threshold:
        return "MED", C.YELLOW
    return "low", C.GREY


def score_table(scores, threshold, label="risk", width=26):
    """The ranked bar chart used by both commands for risk and for impact."""
    if not scores:
        return
    peak = max(scores.values()) or 1
    print(f"    {'component':<12}{label:>22}   {'':{width}}  tier")
    rule()
    for comp, val in sorted(scores.items(), key=lambda kv_: -kv_[1]):
        tier, col = tier_of(val, threshold)
        print(f"    {comp:<12}{col}{val:>22.1f}{C.RESET}   "
              f"{bar(val, peak, width, col)}  {col}{tier}{C.RESET}")


def cutoff_table(risks, impact, components, threshold):
    """Every component ranked against the cut-off, with the line drawn through.

    Returns the ordered rows so the caller can reuse them without recomputing.
    """
    rows = sorted(({"c": c,
                    "r": risks.get(c, 0.0),
                    "i": impact.get(c, 0.0),
                    "best": max(risks.get(c, 0.0), impact.get(c, 0.0))}
                   for c in components),
                  key=lambda d: -d["best"])

    # Plain-English headers. "risk" and "impact" are what the code calls them;
    # nobody watching a demo should have to hold that mapping in their head to
    # read the table, so the columns say what the numbers actually mean.
    # Two header rows rather than one long one: "broken before (flow 1)" in a
    # single line pushes the table past the 76-column width and the bars stop
    # lining up. The flow labels sit underneath, in the same columns.
    print(f"    {'rank':>4}  {'component':<12}{'broken before':>14}{'changed now':>13}"
          f"{'score used':>12}   decision")
    print(f"    {'':>4}  {'':<12}{C.GREY}{'(flow 1)':>14}{'(flow 2)':>13}"
          f"{'the higher':>12}{C.RESET}")
    rule()
    drawn = False
    for n, d in enumerate(rows, 1):
        if d["best"] < threshold and not drawn:
            drawn = True
            tag = f" cut-off {threshold:.1f} "
            side = (W - 8 - len(tag)) // 2
            print(f"    {C.YELLOW}{_B.h * side}{C.BOLD}{tag}{C.RESET}"
                  f"{C.YELLOW}{_B.h * side}{C.RESET}")
        col, verdict = ((C.GREEN, "SELECTED") if d["best"] >= threshold
                        else (C.GREY, "skipped"))
        rs = f"{d['r']:.1f}" if d["r"] else "none"
        ims = f"{d['i']:.1f}" if d["i"] else "none"
        print(f"    {col}{n:>4}  {d['c']:<12}{C.RESET}{C.GREY}{rs:>14}{ims:>13}{C.RESET}"
              f"{col}{d['best']:>12.1f}   {verdict}{C.RESET}")
    if not drawn:
        print(f"    {C.YELLOW}{_B.h * 20} cut-off {threshold:.1f} — nothing fell "
              f"below it {_B.h * 20}{C.RESET}")
    print()
    print(f"    {C.GREY}broken before (flow 1) = defect history: severity x recency, "
          f"x1.6 if it was reopened{C.RESET}")
    print(f"    {C.GREY}changed now   (flow 2) = this release: features, fixes and "
          f"requirement changes{C.RESET}")
    print(f"    {C.GREY}score used             = whichever flow scored higher — a "
          f"component only has to fail one{C.RESET}")
    return rows


def the_rule(threshold):
    """State the selection rule before applying it."""
    hi = f"score {threshold:.1f} or above"
    lo = f"score below {threshold:.1f}"
    w = max(len(hi), len(lo))
    print(f"    {C.BOLD}THE RULE{C.RESET}")
    print(f"      {C.GREEN}{hi:<{w}}{C.RESET}{C.GREY} ......  {C.RESET}"
          f"{C.GREEN}{C.BOLD}{'SELECTED':<8}{C.RESET}"
          f"{C.GREY}   the component runs its tests{C.RESET}")
    print(f"      {C.GREY}{lo:<{w}} ......  {'SKIPPED':<8}"
          f"   the reason is logged, nothing is silent{C.RESET}")
    print(f"      {C.GREY}A component qualifies on EITHER signal — it does not need "
          f"both.{C.RESET}")
    print(f"      {C.GREY}Cut-off set in agent/common.py; override per run with "
          f"--threshold N.{C.RESET}")
