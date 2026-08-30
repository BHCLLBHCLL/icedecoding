# -*- coding: utf-8 -*-
"""P18: analyze oracle node positions — skeleton lattice vs octree jitter."""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load(job):
    p = os.path.join(ROOT, "tools", "probe_work",
                     "pos_" + job.replace(" ", "_") + ".json")
    d = json.load(open(p, encoding="utf-8"))
    return d


def cluster_stats(col, tol):
    u = np.unique(np.round(col, 15))
    n = len(u)
    # greedy cluster
    centers = []
    sizes = []
    cur = [u[0]]
    for v in u[1:]:
        if v - cur[0] <= tol:
            cur.append(v)
        else:
            centers.append(np.mean(cur))
            sizes.append(len(cur))
            cur = [v]
    centers.append(np.mean(cur))
    sizes.append(len(cur))
    return np.array(centers), np.array(sizes)


def main(job):
    d = load(job)
    ax = d["axes"]
    print("job", job, "nodes", d["nodes"])
    for name in ("x", "y", "z"):
        a = ax[name]
        print("==", name, "distinct", a["lines"], "range %.6g..%.6g"
              % (a["min"], a["max"]), "spacing med %.4g" % a["spacing_median"])
        # cluster near-duplicates at several tolerances
        col = np.loadtxt  # placeholder to avoid lint; real below
    # reload raw col arrays from JSON 'first' only has 12 entries -> need
    # full arrays; rebuild from grid_output instead
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    print("bounds:", ["%.6g" % v for v in pts.min(0)], "..",
          ["%.6g" % v for v in pts.max(0)])
    for ax, name in enumerate(("x", "y", "z")):
        col = np.unique(np.round(pts[:, ax], 14))
        print("==", name, "distinct", len(col),
              "min %.8g max %.8g" % (col[0], col[-1]))
        for tol in (1e-9, 1e-7, 1e-6, 1e-5, 1e-4):
            c, s = cluster_stats(col, tol)
            print("   tol %.0e -> %d clusters, max cluster %d, mean %.2f"
                  % (tol, len(c), s.max(), s.mean()))
        d = np.diff(col)
        dd = d[d > 1e-9]
        print("   nonzero spacings: min %.3g med %.4g; top modes:"
              % (dd.min(), np.median(dd)))
        uniq, cnts = np.unique(np.round(dd, 7), return_counts=True)
        idx = np.argsort(-cnts)[:6]
        for i in idx:
            print("      %.6g x %d" % (uniq[i], cnts[i]))
    # lattice hypothesis: are positions near multiples of a base step?
    for ax, name in enumerate(("x", "y", "z")):
        col = np.unique(np.round(pts[:, ax], 14))
        for step in (0.02, 0.01, 0.005, 0.0025, 0.001):
            frac = (col / step) % 1.0
            close = ((frac < 1e-6) | (frac > 1 - 1e-6)).mean()
            print(name, "on %g-grid: %.1f%%" % (step, close * 100))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "10-1transient")
