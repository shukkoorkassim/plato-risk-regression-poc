"""benchmark/nx_bugs.py — seeded defects in real networkx source (Phase 2 · item 8).

Each entry is a realistic single-point defect applied to the networkx working
copy. The categories mirror what Defects4J's real bugs look like — wrong
operator, off-by-one, dropped branch, wrong variable, inverted condition — and
each one is a change a developer could plausibly make.

The harness applies a bug, runs the in-scope suite, and records which tests
ACTUALLY fail. That executed result is the ground truth: nothing here asserts
which tests should catch what.

`old` must appear exactly once in its file — `python -m benchmark.nx_bugs`
validates that for every entry and is run by the harness before any bug is used.
"""

BUGS = [
    # ---- classes.function ----------------------------------------------------
    {"id": "NX-1", "module": "networkx/classes/function.py", "kind": "wrong-operator",
     "old": "    d = m / (n * (n - 1))",
     "new": "    d = m / (n * n)",
     "note": "density: denominator uses n^2 instead of n(n-1)"},

    {"id": "NX-2", "module": "networkx/classes/function.py", "kind": "dropped-case",
     "old": "    counts = Counter(d for n, d in G.degree())",
     "new": "    counts = Counter(d for n, d in G.degree() if d > 0)",
     "note": "degree_histogram: isolated (degree-0) nodes silently dropped"},

    {"id": "NX-3", "module": "networkx/classes/function.py", "kind": "inverted-condition",
     "old": "    if m == 0 or n <= 1:\n        return 0",
     "new": "    if m == 0 or n < 1:\n        return 0",
     "note": "density: single-node graph divides by zero instead of returning 0"},

    # ---- classes.graph -------------------------------------------------------
    {"id": "NX-4", "module": "networkx/classes/graph.py", "kind": "wrong-container",
     "old": "            return v in self._adj[u]",
     "new": "            return v in self._node",
     "note": "has_edge: reports an edge between any two existing nodes"},

    {"id": "NX-5", "module": "networkx/classes/graph.py", "kind": "dropped-update",
     "old": "        self._adj[u][v] = datadict\n        self._adj[v][u] = datadict",
     "new": "        self._adj[u][v] = datadict",
     "note": "add_edge: only one direction recorded, breaking undirected symmetry"},

    # ---- classes.digraph -----------------------------------------------------
    {"id": "NX-6", "module": "networkx/classes/digraph.py", "kind": "swapped-direction",
     "old": "        self._succ[u][v] = datadict\n        self._pred[v][u] = datadict",
     "new": "        self._succ[v][u] = datadict\n        self._pred[u][v] = datadict",
     "note": "add_edge: successor/predecessor reversed"},

    {"id": "NX-7", "module": "networkx/classes/digraph.py", "kind": "dropped-update",
     "old": "            self._succ[u][v] = datadict\n            self._pred[v][u] = datadict",
     "new": "            self._succ[u][v] = datadict",
     "note": "add_edges_from: predecessor map not maintained"},

    # ---- utils.misc ----------------------------------------------------------
    {"id": "NX-8", "module": "networkx/utils/misc.py", "kind": "dropped-branch",
     "old": "    return zip(a, chain(b, (first,)))",
     "new": "    return zip(a, b)",
     "note": "pairwise(cyclic=True): the wrap-around pair is lost"},

    # ---- utils.union_find ----------------------------------------------------
    {"id": "NX-9", "module": "networkx/utils/union_find.py", "kind": "inverted-heuristic",
     "old": "                {self[x] for x in objects}, key=lambda r: self.weights[r], reverse=True",
     "new": "                {self[x] for x in objects}, key=lambda r: self.weights[r]",
     "note": "union: merges into the lightest root instead of the heaviest"},

    # ---- generators.classic --------------------------------------------------
    {"id": "NX-10", "module": "networkx/generators/classic.py", "kind": "dropped-flag",
     "old": "    G.add_edges_from(pairwise(nodes, cyclic=True))",
     "new": "    G.add_edges_from(pairwise(nodes))",
     "note": "cycle_graph: produces a path, the closing edge is missing"},

    {"id": "NX-11", "module": "networkx/generators/classic.py", "kind": "off-by-one",
     "old": "    G.add_nodes_from(range(m1, m1 + m2 - 1))",
     "new": "    G.add_nodes_from(range(m1, m1 + m2))",
     "note": "barbell_graph: path segment one node too long"},

    {"id": "NX-12", "module": "networkx/generators/classic.py", "kind": "off-by-one",
     "old": "    G.add_edges_from(pairwise(range(n)))\n    G.add_edges_from(pairwise(range(n, 2 * n)))",
     "new": "    G.add_edges_from(pairwise(range(n)))\n    G.add_edges_from(pairwise(range(n, 2 * n - 1)))",
     "note": "ladder_graph: second rail one edge short"},

    # ---- linalg.graphmatrix --------------------------------------------------
    {"id": "NX-13", "module": "networkx/linalg/graphmatrix.py", "kind": "wrong-ordering",
     "old": "        nodelist = list(G)",
     "new": "        nodelist = sorted(G, key=str)",
     "note": "adjacency_matrix: rows ordered differently from G's node order"},

    # ---- linalg.laplacianmatrix ----------------------------------------------
    {"id": "NX-14", "module": "networkx/linalg/laplacianmatrix.py", "kind": "sign-flip",
     "old": "    return D - A",
     "new": "    return A - D",
     "note": "laplacian_matrix: sign inverted"},

    # ---- relabel -------------------------------------------------------------
    {"id": "NX-15", "module": "networkx/relabel.py", "kind": "dropped-default",
     "old": "    H.add_nodes_from(mapping.get(n, n) for n in G)",
     "new": "    H.add_nodes_from(mapping[n] for n in G if n in mapping)",
     "note": "relabel_nodes(copy=True): unmapped nodes dropped instead of kept"},

    # ---- convert -------------------------------------------------------------
    {"id": "NX-16", "module": "networkx/convert.py", "kind": "dropped-filter",
     "old": "        d[n] = [nbr for nbr in G.neighbors(n) if nbr in nodelist]",
     "new": "        d[n] = [nbr for nbr in G.neighbors(n)]",
     "note": "to_dict_of_lists: nodelist filter ignored"},
]


def validate(root=None):
    """Every `old` must appear exactly once in its module. Returns (ok, problems)."""
    from pathlib import Path
    from benchmark import nx_project

    root = Path(root) if root else nx_project.workdir().parent
    problems = []
    for b in BUGS:
        target = root / b["module"]
        if not target.exists():
            problems.append(f"{b['id']}: missing file {b['module']}")
            continue
        n = target.read_text(encoding="utf-8").count(b["old"])
        if n != 1:
            problems.append(f"{b['id']}: pattern appears {n}x in {b['module']} "
                            f"(need exactly 1)")
    return not problems, problems


def by_id(bug_id):
    for b in BUGS:
        if b["id"] == bug_id:
            return b
    raise KeyError(bug_id)


if __name__ == "__main__":
    import sys
    from benchmark import nx_project

    nx_project.ensure_workdir()
    ok, problems = validate()
    print(f"{len(BUGS)} seeded bugs against {nx_project.describe()}\n")
    if ok:
        print("  all patterns match exactly once — corpus is valid")
        sys.exit(0)
    for p in problems:
        print(f"  INVALID  {p}")
    sys.exit(1)
