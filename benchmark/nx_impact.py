"""benchmark/nx_impact.py — build a real module -> tests map by execution.

The "impact" selection strategy needs to know which tests actually exercise a
given source module. Defects4J ships that as `tests.relevant`; for a live
project we have to measure it.

coverage.py is not available in this sandbox, so this uses `sys.settrace`
directly as a pytest plugin. For each test it records which networkx source
FILES executed, and attributes them to the test's own file. Tracing only `call`
events (the callback returns None, so no per-line tracing) keeps the overhead
to roughly 2x rather than 50x.

The result is a genuine dynamic dependency map — strictly better than guessing
from imports, because networkx resolves most things through the `nx.` namespace
where static analysis sees nothing.

    python -m benchmark.nx_impact          # -> benchmark/nx_impact_map.json

Written once and reused by every benchmark run.
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

_records = defaultdict(set)
_current = None
_root = os.environ.get("NX_TRACE_ROOT", "")


def _tracer(frame, event, arg):
    if event == "call" and _current is not None:
        fn = frame.f_code.co_filename
        if fn.startswith(_root):
            _current.add(fn)
    return None          # no line tracing — keeps this affordable


# ---- pytest plugin hooks -------------------------------------------------------
# Plain (non-wrapper) hooks on purpose: the hookwrapper protocol changed between
# pytest 8 and 9, and setup/teardown bracket the test just as well. Tracing the
# fixture setup too is a feature here, not a flaw — fixtures exercise source
# code, and a test that only touches a module through its fixture still depends
# on that module.
def pytest_runtest_setup(item):
    global _current
    _current = _records[str(item.fspath)]
    sys.settrace(_tracer)


def pytest_runtest_teardown(item, nextitem):
    global _current
    sys.settrace(None)
    _current = None


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("NX_TRACE_OUT")
    if not out:
        return
    payload = {}
    for test_file, sources in _records.items():
        payload[_rel(test_file)] = sorted({_rel(s) for s in sources})
    Path(out).write_text(json.dumps(payload, indent=1))


def _rel(path):
    p = Path(path)
    parts = p.parts
    if "networkx" in parts:
        i = len(parts) - 1 - parts[::-1].index("networkx")
        return str(Path(*parts[i:]))
    return str(p)


# ---- driver --------------------------------------------------------------------
def build(out_path=None):
    """Run the in-scope suite once under tracing and write the map."""
    import subprocess
    from benchmark import nx_project

    nx_project.ensure_workdir()
    out_path = Path(out_path or Path(__file__).parent / "nx_impact_map.json")
    env = nx_project.env()
    env["NX_TRACE_ROOT"] = str(nx_project.workdir())
    env["NX_TRACE_OUT"] = str(out_path)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[1]), env["PYTHONPATH"]])

    cmd = [sys.executable, "-m", "pytest", *nx_project.scope_paths(),
           "-q", "--no-header", "--tb=no", "-p", "no:cacheprovider",
           "-p", "benchmark.nx_impact"]
    print("Tracing the in-scope suite to build the module -> tests map.")
    print(f"  scope: {', '.join(nx_project.SCOPE)}")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1800)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    print(f"  {tail[0]}")

    if not out_path.exists():
        raise RuntimeError(f"tracing produced no map:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    data = json.loads(out_path.read_text())
    print(f"  wrote {len(data)} test files -> {out_path.name}")
    return data


def load(path=None):
    p = Path(path or Path(__file__).parent / "nx_impact_map.json")
    return json.loads(p.read_text()) if p.exists() else {}


def tests_touching(module_rel, impact_map=None):
    """Which test files executed code in this source module?"""
    impact_map = impact_map if impact_map is not None else load()
    target = str(Path(module_rel))
    return sorted(t for t, sources in impact_map.items() if target in sources)


if __name__ == "__main__":
    build()
