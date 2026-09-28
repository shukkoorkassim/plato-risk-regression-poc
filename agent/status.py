"""agent/status.py — one vocabulary for "what is real and what is not".

Every feature in this PoC is in one of four states, and the console says which
one, every time it runs. Nothing silently pretends to be finished.

    DONE         implemented and exercised by a command you can run
    PARTIAL      the mechanism is real; some input or step is still missing
    PLACEHOLDER  the wiring is real, the DATA is invented — never quote it
    BLOCKED      cannot be done in this environment, with the reason

The point of PLACEHOLDER is that a stand-in is only safe if it announces
itself. A made-up business-criticality table that prints nothing looks exactly
like a real one on a slide. So every placeholder prints what it is, why, and
the real source that should replace it.
"""
from .common import C

DONE = "DONE"
PARTIAL = "PARTIAL"
PLACEHOLDER = "PLACEHOLDER"
BLOCKED = "BLOCKED"

_COLOR = {
    DONE: C.GREEN,
    PARTIAL: C.YELLOW,
    PLACEHOLDER: C.YELLOW,
    BLOCKED: C.RED,
}

_WIDTH = 11


def tag(state):
    return f"{_COLOR.get(state, C.GREY)}[{state:^{_WIDTH}}]{C.RESET}"


def line(state, what, reason="", replace_with=""):
    """One status line: [ STATE ] what — reason (replace with: ...)"""
    out = f"{tag(state)} {what}"
    if reason:
        out += f" {C.GREY}— {reason}{C.RESET}"
    if replace_with:
        out += f"\n{' ' * (_WIDTH + 3)}{C.GREY}replace with: {replace_with}{C.RESET}"
    return out


def say(state, what, reason="", replace_with=""):
    print(line(state, what, reason, replace_with))


def placeholder(what, reason, replace_with):
    """Announce invented data. Always call this when loading stand-in input."""
    say(PLACEHOLDER, what, reason, replace_with)


def in_progress(what, reason=""):
    say(PARTIAL, what, reason or "in progress")


def blocked(what, reason):
    say(BLOCKED, what, reason)


def banner(title, subtitle=""):
    bar = "=" * 72
    print(f"\n{C.MAGENTA}{bar}\n {title}" + (f"\n {C.GREY}{subtitle}{C.RESET}" if subtitle else "")
          + f"\n{C.MAGENTA}{bar}{C.RESET}")
