# -*- coding: utf-8 -*-
"""P18j: overlap of same-column cylinders' annulus x-sets (theta-phase
diversity check)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CX = 0.15
ROWS = (0.25, 0.30, 0.35)


def load_oracle():
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", "10-1transient")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    return pts


def annulus(pts, cx, cy):
    rho = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    zok = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19)
    m = (rho > 0.005) & (rho < 0.035) & zok
    return pts[m]


def main():
    pts = load_oracle()
    sets = {}
    for cy in ROWS:
        a = annulus(pts, CX, cy)
        sx = set(np.round(a[:, 0], 12))
        sy = set(np.round(a[:, 1], 12))
        sets[cy] = (sx, sy)
        print("cyl(%.2f,%.2f) distinct x %d, y %d" % (CX, cy, len(sx), len(sy)))
    # pairwise overlaps of x-sets (same column) and y-sets (same column too)
    for i, c1 in enumerate(ROWS):
        for c2 in ROWS[i + 1:]:
            ox = len(sets[c1][0] & sets[c2][0])
            oy = len(sets[c1][1] & sets[c2][1])
            print("rows %.2f vs %.2f: x overlap %d, y overlap %d" %
                  (c1, c2, ox, oy))


if __name__ == "__main__":
    main()
