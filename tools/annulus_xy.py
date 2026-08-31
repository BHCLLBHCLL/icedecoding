# -*- coding: utf-8 -*-
"""P18i: where does the per-cylinder x-surplus live? annulus vs rest."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CYLINDERS = [(0.15, 0.25), (0.15, 0.30), (0.15, 0.35),
             (0.20, 0.25), (0.20, 0.30), (0.20, 0.35),
             (0.25, 0.25), (0.25, 0.30), (0.25, 0.35)]


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


def main():
    pts = load_oracle()
    xs = np.unique(np.round(pts[:, 0], 12))
    ys = np.unique(np.round(pts[:, 1], 12))
    tot_dx = tot_dy = 0
    for cx, cy in CYLINDERS:
        rho = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        zok = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19)
        m = (rho > 0.005) & (rho < 0.035) & zok
        ann = pts[m]
        dx = len(np.unique(np.round(ann[:, 0], 12)))
        dy = len(np.unique(np.round(ann[:, 1], 12)))
        # nodes in the cylinder's x-band but NOT in the annulus
        band = ((pts[:, 0] >= cx - 0.025) & (pts[:, 0] <= cx + 0.025))
        nonann = pts[band & ~m]
        bdx = len(np.unique(np.round(nonann[:, 0], 12)))
        bdy = len(np.unique(np.round(nonann[:, 1], 12)))
        tot_dx += dx
        tot_dy += dy
        print("cyl(%.2f,%.2f) annulus distinct x/y = %d/%d  non-annulus %d/%d"
              % (cx, cy, dx, dy, bdx, bdy))
    print("annulus totals x/y:", tot_dx, tot_dy,
          "ratio %.3f" % (tot_dx / float(tot_dy)))


if __name__ == "__main__":
    main()
