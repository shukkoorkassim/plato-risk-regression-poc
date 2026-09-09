"""agent/data_quality.py — pre-run data-quality & coverage checks (Phase 1 · T5).

Bad or incomplete test-to-component mappings make the agent select the wrong
tests, and it cannot flag a risk area that has no test at all. This runs before
selection and surfaces those gaps for a human to review.
"""
import json
from .common import TESTS, STATE, ROOT

KNOWN = {"login", "inventory", "cart", "checkout", "search", "payments"}


def _suite():
    p = TESTS / "test_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


def check_data_quality():
    """Return (ok, report_text). ok is False if anything needs human review."""
    suite = _suite()
    covered = set(suite.values())
    referenced = set()
    for f in ("defects.json", "changes.json"):
        fp = STATE / f
        if fp.exists():
            for r in json.loads(fp.read_text()):
                if r.get("component"):
                    referenced.add(r["component"])
    warns, infos = [], []
    for c in sorted(referenced - covered):
        warns.append(f"coverage gap: '{c}' has defects/changes but NO test mapped")
    for c in sorted(KNOWN - covered):
        warns.append(f"coverage gap: known component '{c}' has no regression test mapped")
    for t, c in sorted(suite.items()):
        if c not in KNOWN:
            infos.append(f"test {t} maps to unknown component '{c}'")
    for t in sorted(suite):
        if not (ROOT / t).exists():
            warns.append(f"mapped test file is missing on disk: {t}")
    ok = not warns
    head = "PASS — mappings look complete" if ok else f"{len(warns)} issue(s) to review"
    lines = [f"Data-quality check: {head}"]
    for w in warns:
        lines.append(f"  ! {w}")
    for i in infos:
        lines.append(f"  · {i}")
    if ok:
        lines.append(f"  · {len(covered)} components mapped to tests; "
                     f"{len(referenced)} referenced by data — all covered")
    return ok, "\n".join(lines)
