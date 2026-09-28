"""agent/arch_risk.py — architectural risk (Phase 3 · item 13).

"Interfaces, boundaries, and where defects cluster."

Not every module is equally dangerous to change. A module that half the codebase
depends on is a blast radius; a leaf module is not. This computes, from a real
import graph:

    fan-in (Ca)    how many modules depend on this one — the blast radius
    fan-out (Ce)   how many it depends on — how exposed it is to others
    instability    I = Ce / (Ca + Ce)   (Robert Martin's metric)
                   0 = rigid and depended-upon, 1 = volatile and depends on others
    boundary       fan-in x fan-out — modules that are BOTH widely used and
                   widely dependent are the real interface hot-spots
    clustering     defects already concentrated here

The risky place is high fan-in with high instability: lots of code depends on
it, and it keeps changing because of what IT depends on.

    python run_poc.py --arch                 # the benchmark project (networkx)
    python run_poc.py --arch --path <dir>    # any Python package

WHY NOT THE DEMO PRODUCT: src/swaglabs.py is a single module. A one-module
codebase has no internal boundaries, so every metric here is trivially zero —
there is nothing to measure, and pretending otherwise would be a fake number.
The command says so rather than printing zeros.
"""
import ast
import re
from collections import defaultdict
from pathlib import Path

from .common import C, ROOT, STATE
from . import status as S

MIN_MODULES = 3          # below this there is no architecture to speak of


def _module_name(py_file, root):
    rel = py_file.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts) if parts else rel.stem


def _imports_of(py_file, root, own_modules):
    """Which of THIS package's modules does this file import?"""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return set()
    here = _module_name(py_file, root)
    pkg_parts = here.split(".")[:-1]
    found = set()

    def _resolve(name):
        if name in own_modules:
            found.add(name)
            return
        # tolerate 'pkg.sub.mod' spellings of our own modules
        for m in own_modules:
            if name.endswith("." + m) or m.endswith("." + name):
                found.add(m)
                return

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:                       # relative: from . import x
                base = pkg_parts[:len(pkg_parts) - (node.level - 1)] if node.level > 1 else pkg_parts
                head = ".".join(base + ([node.module] if node.module else []))
                for alias in node.names:
                    _resolve(".".join([p for p in [head, alias.name] if p]))
                    _resolve(head)
            elif node.module:
                for alias in node.names:
                    _resolve(f"{node.module}.{alias.name}")
                _resolve(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                _resolve(alias.name)

    found.discard(here)
    return found


def build_graph(root):
    """root -> {module: set(modules it imports)} for one Python package."""
    root = Path(root)
    files = [f for f in root.rglob("*.py")
             if "test" not in f.parts and not f.name.startswith("test_")]
    own = {_module_name(f, root) for f in files}
    graph = {}
    for f in files:
        graph[_module_name(f, root)] = _imports_of(f, root, own)
    return graph


def _defect_clusters():
    """Where defects already concentrate, from whatever the flows loaded."""
    import json
    f = STATE / "defects.json"
    if not f.exists():
        return {}
    try:
        rows = json.loads(f.read_text())
    except (ValueError, OSError):
        return {}
    counts = defaultdict(int)
    for d in rows:
        if d.get("component"):
            counts[d["component"]] += 1
    return dict(counts)


def analyse(root):
    """Return per-module architectural metrics, ranked by risk."""
    graph = build_graph(root)
    modules = [m for m in graph if m]
    fan_out = {m: len(graph[m]) for m in modules}
    fan_in = defaultdict(int)
    for m in modules:
        for dep in graph[m]:
            fan_in[dep] += 1

    clusters = _defect_clusters()
    peak_in = max(fan_in.values(), default=0) or 1
    peak_boundary = max((fan_in[m] * fan_out[m] for m in modules), default=0) or 1

    rows = []
    for m in modules:
        ca, ce = fan_in.get(m, 0), fan_out.get(m, 0)
        instability = ce / (ca + ce) if (ca + ce) else 0.0
        boundary = ca * ce
        leaf = m.split(".")[-1]
        defects = clusters.get(leaf, 0) or clusters.get(m, 0)

        # Blast radius is the whole story: a module nothing depends on cannot be
        # architecturally risky, however unstable it is. So instability is a
        # MULTIPLIER on the radius, not a term added to it — otherwise every
        # isolated leaf (fan-in 0, instability 1.0) scores above a real hub.
        radius = 0.70 * (ca / peak_in) + 0.30 * (boundary / peak_boundary)
        risk = radius * (1 + 0.4 * instability)
        risk *= (1 + min(1.0, defects / 5.0))     # defects already clustering here
        rows.append({"module": m, "fan_in": ca, "fan_out": ce,
                     "instability": round(instability, 2),
                     "boundary": boundary, "defects": defects,
                     "risk": round(risk, 3)})
    rows.sort(key=lambda r: -r["risk"])
    return rows


def _cycles(graph):
    """Import cycles — the clearest boundary violation there is."""
    found, seen = [], set()
    for a, deps in graph.items():
        for b in deps:
            if a != b and a in graph.get(b, ()) and (b, a) not in seen:
                seen.add((a, b))
                found.append((a, b))
    return found


def report(path=None, top=15):
    S.banner("ARCHITECTURAL RISK",
             "item 13 · interfaces, boundaries, and where defects cluster")

    product_src = ROOT / "src"
    target = Path(path) if path else None

    if target is None:
        # Default to the benchmark project, and say plainly why not the product.
        py = list(product_src.glob("*.py")) if product_src.exists() else []
        S.say(S.BLOCKED, "architectural risk for the demo product",
              f"src/ holds {len(py)} module(s) — a single-module codebase has no "
              f"internal boundaries, so fan-in/fan-out are all zero. Nothing to "
              f"measure, so nothing is invented.")
        print(f"       {C.GREY}point it at a real repo: "
              f"python run_poc.py --arch --path <package-dir>{C.RESET}\n")
        try:
            from benchmark import nx_project
            target = nx_project.workdir()
            if not target.exists():
                target = nx_project.installed_root()
            S.say(S.DONE, "running against the benchmark project instead",
                  f"networkx — a real multi-module codebase")
        except Exception as exc:  # noqa: BLE001
            S.blocked("no multi-module codebase available", str(exc))
            return []

    if not Path(target).exists():
        S.blocked("architectural risk", f"path not found: {target}")
        return []

    graph = build_graph(target)
    if len(graph) < MIN_MODULES:
        S.blocked("architectural risk",
                  f"{len(graph)} module(s) at {target} — too few to have an architecture")
        return []

    rows = analyse(target)
    print(f"\n  {len(graph)} modules · {sum(len(v) for v in graph.values())} internal imports"
          f"  {C.GREY}({target}){C.RESET}\n")
    print(f"  {'module':42} {'fan-in':>7} {'fan-out':>8} {'instab':>7} "
          f"{'defects':>8} {'risk':>7}")
    print(f"  {C.GREY}{'-' * 84}{C.RESET}")
    for r in rows[:top]:
        tier = C.RED if r["risk"] >= 0.5 else C.YELLOW if r["risk"] >= 0.25 else C.GREY
        name = r["module"] if len(r["module"]) <= 42 else "…" + r["module"][-41:]
        print(f"  {name:42} {r['fan_in']:>7} {r['fan_out']:>8} "
              f"{r['instability']:>7.2f} {r['defects']:>8} {tier}{r['risk']:>7.3f}{C.RESET}")

    hot = [r for r in rows if r["fan_in"] >= 3 and r["instability"] >= 0.5]
    if hot:
        print(f"\n  {C.RED}{C.BOLD}INTERFACE HOT-SPOTS{C.RESET} "
              f"{C.GREY}— widely depended on AND unstable{C.RESET}")
        for r in hot[:6]:
            print(f"    {C.RED}!{C.RESET} {r['module']:40} {r['fan_in']} modules depend "
                  f"on it, instability {r['instability']:.2f}")
        print(f"    {C.GREY}Changing one of these is the expensive kind of change: a lot "
              f"depends on it,\n    and it keeps moving because of what it depends on. "
              f"Re-test its dependents.{C.RESET}")

    cyc = _cycles(graph)
    if cyc:
        print(f"\n  {C.YELLOW}{C.BOLD}IMPORT CYCLES{C.RESET} "
              f"{C.GREY}— boundary violations ({len(cyc)}){C.RESET}")
        for a, b in cyc[:6]:
            print(f"    {C.YELLOW}<->{C.RESET} {a}  <->  {b}")

    print(f"\n  {C.GREY}risk = 0.55*blast-radius + 0.25*boundary + 0.20*instability,"
          f" scaled by defects\n  already clustering in the module.{C.RESET}")
    return rows
