# -*- coding: utf-8 -*-
"""P18h: extract the oracle's base-lattice lines from its distinct axis
values (coarse lines = large forward gaps)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load():
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", "10-1transient")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    return pts


def base_lines(vals, thr):
    """Keep values whose forward gap >= thr (base/coarse skeleton)."""
    keep = []
    for i, v in enumerate(vals):
        if i == len(vals) - 1 or vals[i + 1] - v >= thr:
            keep.append(v)
    # always keep the very first (domain start)
    if keep and keep[0] != vals[0]:
        keep.insert(0, vals[0])
    return np.array(keep)


def main():
    pts = load()
    for ax, name in enumerate(("x", "y", "z")):
        vals = np.unique(np.round(pts[:, ax], 12))
        d = np.diff(vals)
        dd = d[d > 1e-9]
        print("==", name, len(vals), "gaps min/med/p90/max: %.2g %.2g %.2g %.2g"
              % (dd.min(), np.median(dd), np.percentile(dd, 90), dd.max()))
        for thr in (0.008, 0.012, 0.015, 0.018):
            bl = base_lines(vals, thr)
            print("   thr %.3f -> %d base lines: %s" %
                  (thr, len(bl), np.round(bl, 4)))
    # look at coarse gaps distribution
    vals_x = np.unique(np.round(pts[:, 0], 12))
    d = np.diff(vals_x)
    dd = np.sort(d[d > 1e-9])
    print("x gap quantiles:", np.round(np.percentile(dd, [50, 80, 90, 95,
                                                          98, 99]), 6))


if __name__ == "__main__":
    main()
