# -*- coding: utf-8 -*-
"""P18c: oracle leaf-depth autopsy near curved surfaces (10-1 cylinders)."""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scipy.spatial import cKDTree


def main():
    jdir = os.path.join(r"D:\training\icepak", "10-1transient")
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    cyls = [(0.15, 0.25), (0.15, 0.30), (0.15, 0.35), (0.20, 0.25),
            (0.20, 0.30), (0.20, 0.35), (0.25, 0.25), (0.25, 0.30),
            (0.25, 0.35)]
    tree = cKDTree(pts)
    d, _ = tree.query(pts, k=2)
    nn = d[:, 1]                      # nearest-neighbour distance
    print("3D NN distances: min %.3g p1 %.3g p10 %.3g median %.3g"
          % (nn.min(), np.percentile(nn, 1), np.percentile(nn, 10),
             np.median(nn)))
    # shell nodes: within radial band around a cylinder axis
    shell = np.zeros(len(pts), dtype=bool)
    for cx, cy in cyls:
        rho = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        zok = (pts[:, 2] >= 0.12) & (pts[:, 2] <= 0.20)
        shell |= (rho < 0.045) & zok
    nn_s = nn[shell]
    print("shell nodes:", shell.sum(), "NN: min %.3g p10 %.3g median %.3g"
          % (nn_s.min(), np.percentile(nn_s, 10), np.median(nn_s)))
    # level histogram: level = log2(0.02 / nn)
    lv = np.log2(0.02 / np.clip(nn_s, 1e-9, None))
    lv = np.clip(np.round(lv), 0, 20).astype(int)
    uniq, cnts = np.unique(lv, return_counts=True)
    print("shell level histogram (0.02 base):")
    for u, c in zip(uniq, cnts):
        print("   level %2d: %d nodes" % (u, c))
    # also far-field level histogram
    lv0 = np.clip(np.round(np.log2(0.02 / np.clip(nn, 1e-9, None))), 0,
                  20).astype(int)
    u0, c0 = np.unique(lv0, return_counts=True)
    print("all-node level histogram:")
    for u, c in zip(u0, c0):
        print("   level %2d: %d" % (u, c))


if __name__ == "__main__":
    main()
