# -*- coding: utf-8 -*-
"""Phase J: test the GRADED-LATTICE hypothesis against the smoother.

If oracle off-plane coordinates share a modular offset t (mod the local
refinement step) and form arithmetic families with dyadic steps, the
non-lattice positions come from graded lattice placement (geometric
transition bands), not a relaxation smoother.
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

JOB = "10-1transient"
JDIR = os.path.join("D:", os.sep, "training", "icepak", JOB)
NL = bytes([10])


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(NL)
    if not raw.endswith(NL):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return r[0] if r and r[0] is not None else np.zeros((0, 3))


def mod_offsets(vals, step, top=8):
    """Cluster fractional parts mod step; report dominant offsets."""
    f = np.mod(vals, step)
    # cluster with tolerance much finer than step
    order = np.sort(f)
    gaps = np.diff(order)
    cuts = np.where(gaps > 1e-9)[0]
    groups = np.split(order, cuts + 1)
    items = [(float(g[0]), len(g), float(np.ptp(g))) for g in groups
             if len(g)]
    items.sort(key=lambda t: -t[1])
    return items[:top]


def main():
    nodes = load_oracle()
    out = {}
    for ax, name in enumerate("xyz"):
        vals = np.unique(np.round(nodes[:, ax], 15))
        rec = {"distinct": len(vals)}
        for step in (0.02, 0.01, 0.005, 0.0025, 0.00125, 0.000625):
            rec["mod_%g" % step] = [
                {"off": o, "n": n, "spread": s}
                for o, n, s in mod_offsets(vals, step)]
        out[name] = rec
        # difference multiset: top repeated gaps (grading steps)
        dv = np.diff(vals)
        cnt = Counter(np.round(dv, 12).tolist())
        out[name + "_top_gaps"] = [[g, c] for g, c in
                                   cnt.most_common(15)]
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "graded_lattice.json"), "w",
                        encoding="utf-8"), indent=1)
    for name in "xyz":
        print("==", name, "==")
        for step in (0.01, 0.0025, 0.000625):
            top = out[name]["mod_%g" % step][:4]
            print("  mod %g:" % step, [(round(t["off"], 12), t["n"])
                                       for t in top])
        print("  top gaps:", [(g, c) for g, c in
                              out[name + "_top_gaps"][:8]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
