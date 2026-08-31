# -*- coding: utf-8 -*-
"""P18j: locate the oracle's non-annulus x-positions (column cx=0.15)
by y/z sub-region."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CX, CY = 0.15, 0.25


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
    # nodes in the column x-band, excluding ALL cylinder annuli
    band = (pts[:, 0] >= CX - 0.025) & (pts[:, 0] <= CX + 0.025)
    col = pts[band]
    in_ann = np.zeros(len(col), dtype=bool)
    for cy in (0.25, 0.30, 0.35):
        rho = np.hypot(col[:, 0] - CX, col[:, 1] - cy)
        in_ann |= (rho > 0.005) & (rho < 0.035)
    nonann = col[~in_ann]
    print("column nodes", len(col), "non-annulus", len(nonann))
    print("non-annulus distinct x:", len(np.unique(np.round(nonann[:, 0], 12))))
    # z sub-regions
    for lo, hi, label in ((0.12, 0.13, "block interior z .12-.13"),
                          (0.13, 0.19, "cylinder z-range .13-.19"),
                          (0.05, 0.12, "below block .05-.12"),
                          (0.19, 0.25, "above cylinders .19-.25")):
        m = (nonann[:, 2] >= lo) & (nonann[:, 2] < hi)
        if m.sum():
            dx = len(np.unique(np.round(nonann[m, 0], 12)))
            print("  z[%.2f,%.2f): %d nodes, %d distinct x" %
                  (lo, hi, m.sum(), dx))
    # y sub-regions (aisles vs outside)
    for lo, hi, label in ((0.20, 0.23, "below row1 .20-.23"),
                          (0.23, 0.27, "row1 band .23-.27"),
                          (0.27, 0.28, "aisle1 .27-.28"),
                          (0.28, 0.32, "row2 band .28-.32"),
                          (0.32, 0.33, "aisle2 .32-.33"),
                          (0.33, 0.37, "row3 band .33-.37"),
                          (0.37, 0.40, "above row3 .37-.40")):
        m = (nonann[:, 1] >= lo) & (nonann[:, 1] < hi)
        if m.sum():
            dx = len(np.unique(np.round(nonann[m, 0], 12)))
            print("  y[%.2f,%.2f): %d nodes, %d distinct x" %
                  (lo, hi, m.sum(), dx))


if __name__ == "__main__":
    main()
