# -*- coding: utf-8 -*-
"""P18i: per-cylinder quadrant densities vs nearest block corner direction."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CYLINDERS = [(0.15, 0.25), (0.15, 0.30), (0.15, 0.35),
             (0.20, 0.25), (0.20, 0.30), (0.20, 0.35),
             (0.25, 0.25), (0.25, 0.30), (0.25, 0.35)]
# block corners of the source hexa (x 0.1-0.3, y 0.2-0.4)
CORNERS = [(0.1, 0.2), (0.3, 0.2), (0.1, 0.4), (0.3, 0.4)]


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


def quadrants(pts, cx, cy):
    rho = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    zok = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19)
    m = (rho > 0.005) & (rho < 0.035) & zok
    th = np.arctan2(pts[m, 1] - cy, pts[m, 0] - cx)
    q = [int(((th > 0) & (th <= np.pi / 2)).sum()),      # x+, y+
         int(((th > np.pi / 2) & (th <= np.pi)).sum()),  # x-, y+
         int(((th < 0) & (th >= -np.pi / 2)).sum()),     # x+, y-
         int(((th < -np.pi / 2) & (th >= -np.pi)).sum())]  # x-, y-
    return q, int(m.sum())


def main():
    pts = load_oracle()
    for cx, cy in CYLINDERS:
        q, n = quadrants(pts, cx, cy)
        # nearest block corner direction
        dist = [( (cx - X) ** 2 + (cy - Y) ** 2, X, Y) for X, Y in CORNERS]
        _, X, Y = min(dist)
        dr = ("x+" if X > cx else "x-", "y+" if Y > cy else "y-")
        # densest quadrant
        labels = ["x+y+", "x-y+", "x+y-", "x-y-"]
        densest = labels[int(np.argmax(q))]
        # quadrant in the corner direction
        corner_q = labels.index("".join(dr))
        print("cyl(%.2f,%.2f) n=%4d quadrants %s nearest corner %s->%s match=%s"
              % (cx, cy, n, q, (round(X, 1), round(Y, 1)), dr,
                 densest == labels[corner_q]))


if __name__ == "__main__":
    main()
