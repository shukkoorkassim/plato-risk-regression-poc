"""benchmark/nx_project.py — the open-source project under test (Phase 2 · item 8).

The benchmark runs against **networkx 3.6.1** (BSD-3-Clause), a real, widely
used open-source library — not a fixture written for this PoC. It is chosen
because it is already installed here (this sandbox has no outbound network),
is pure Python, and ships its own test suite: 265 test files, ~7,000 tests.

Two things matter for the benchmark to be honest:

1. WE NEVER TOUCH THE INSTALLED COPY. `ensure_workdir()` clones the package to
   a scratch directory and every mutation is applied there, with that directory
   first on sys.path.

2. SCOPE IS DECLARED, NOT FUDGED. The full suite takes over two minutes, and
   the harness must re-run it once per seeded bug, so the benchmark measures a
   named subset: classes, utils, generators, linalg and the top-level tests —
   2,501 tests in ~18s. Ground truth is "every test IN SCOPE that fails".
   Defects4J scopes per project for the same reason; the number is only
   meaningful next to the scope, so the scope is printed in every report.

   The subset is not arbitrary: `classes/graph.py` is the base every generator,
   matrix builder and converter depends on, so bugs seeded in it propagate
   across components for real. That cross-component propagation is the thing
   the accuracy metric exists to measure.
"""
import shutil
import sys
from pathlib import Path

WORK = Path.home() / ".cache" / "risk-agent-benchmark"
PYTEST_PATH = Path("/root/.local/share/uv/tools/pytest/lib/python3.11/site-packages")

# subpackages the benchmark measures, relative to the networkx package root
SCOPE = ["classes", "utils", "generators", "linalg", "tests"]

PROJECT = "networkx"
VERSION = "3.6.1"
LICENCE = "BSD-3-Clause"


def installed_root():
    """Where networkx actually lives, without importing it."""
    import importlib.util
    spec = importlib.util.find_spec("networkx")
    if spec is None or not spec.origin:
        raise RuntimeError(
            "networkx is not installed. The benchmark needs a real open-source "
            "project to run against; see docs/BENCHMARK.md for alternatives.")
    return Path(spec.origin).parent


def workdir():
    return WORK / PROJECT


def ensure_workdir(force=False):
    """Clone the installed package into a scratch dir we are free to mutate."""
    dest = workdir()
    if dest.exists() and not force:
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(installed_root(), dest)
    return dest


def scope_paths():
    """Absolute paths pytest should collect, inside the working copy."""
    root = workdir()
    return [str(root / s) for s in SCOPE if (root / s).exists()]


def env():
    """Environment that makes the WORKING COPY win over the installed package."""
    import os
    e = dict(os.environ)
    e["PYTHONPATH"] = os.pathsep.join([str(WORK), str(PYTEST_PATH)])
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["NETWORKX_FALLBACK_TO_NX"] = "True"
    return e


def rel(path):
    """Any path inside the working copy -> 'networkx/classes/graph.py'.

    pytest reports node IDs relative to its rootdir, which can come back as
    '../../../root/.cache/.../networkx/linalg/tests/test_x.py::Cls::test'. A
    plain relative_to() fails on those, so normalise by finding the LAST
    'networkx' segment instead. Getting this wrong silently breaks the whole
    benchmark: tests_trigger would not match tests_relevant, and every bug
    would score zero recall.
    """
    p = Path(str(path))
    parts = p.parts
    if PROJECT in parts:
        i = len(parts) - 1 - parts[::-1].index(PROJECT)
        return str(Path(*parts[i:]))
    return str(p)


def component_of_module(module_rel):
    """'networkx/classes/graph.py' -> 'classes.graph'"""
    p = Path(module_rel)
    parts = list(p.parts)
    if parts and parts[0] == PROJECT:
        parts = parts[1:]
    parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def component_of_test(test_rel):
    """'networkx/classes/tests/test_graph.py' -> 'classes.graph'

    This is the project's own convention — a test file named after the module
    it covers, sitting in a tests/ dir beside it. It is the direct equivalent of
    the PoC's test_map.json, which is why it is the baseline strategy.
    """
    p = Path(test_rel)
    parts = [x for x in p.parts if x != "tests"]
    if parts and parts[0] == PROJECT:
        parts = parts[1:]
    parts[-1] = Path(parts[-1]).stem
    if parts[-1].startswith("test_"):
        parts[-1] = parts[-1][len("test_"):]
    return ".".join(parts)


def describe():
    return (f"{PROJECT} {VERSION} ({LICENCE}) · scope: "
            f"{', '.join(SCOPE)} · working copy: {workdir()}")


if __name__ == "__main__":
    print(describe())
    print("installed:", installed_root())
    print("scope paths:", *scope_paths(), sep="\n  ")
    sys.exit(0)
