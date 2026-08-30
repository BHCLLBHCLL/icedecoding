# -*- coding: utf-8 -*-
"""P18e: compare shell cell-size spectra (ours vs oracle) after the
bounded-face fix — find why our shell over-fragments 3x."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scipy.spatial import cKDTree

CY = (0.25, 0.30, 0.35)


def main():
    from tools.grid_positions import extract_nodes
    from ice_hdm import build
    jdir = os.path.join(r"D:\training\icepak", "10-1transient")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    oracle, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=False,
        max_cells=400000, cyl_cap=6, shell_factor=0.8, curv_c=0.165,
        proj_tol=0.02 * 0.25)
    verts = np.unique(np.round(verts, 12), axis=0)

    def shell_mask(pts):
        m = np.zeros(len(pts), dtype=bool)
        for cy in CY:
            m |= np.abs(pts[:, 1] - cy) < 0.05
        return m

    for name, pts in (("oracle", oracle), ("ours", verts)):
        m = shell_mask(pts)
        sh = pts[m]
        tree = cKDTree(sh)
        d, _ = tree.query(sh, k=2)
        nn = d[:, 1]
        lv = np.clip(np.round(np.log2(0.02 / np.clip(nn, 1e-12, None))), -2,
                     12).astype(int)
        uniq, cnts = np.unique(lv, return_counts=True)
        print(name, "shell nodes", len(sh),
              "NN min %.5g med %.5g" % (nn.min(), np.median(nn)))
        print("   level hist:", dict(zip(uniq.tolist(), cnts.tolist())))


if __name__ == "__main__":
    main()
