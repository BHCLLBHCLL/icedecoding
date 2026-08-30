# -*- coding: utf-8 -*-
"""P18e: partition y-spectra into background lattice vs cylinder-shell
projected values — locate the +11% y overshoot source."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CY = (0.25, 0.30, 0.35)
CX = (0.15, 0.20, 0.25)


def partition(vals):
    """Split distinct axis values into shell band vs background."""
    shell = np.zeros(len(vals), dtype=bool)
    for cy in CY:
        shell |= np.abs(vals - cy) < 0.05
    return vals[shell], vals[~shell]


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
    oracle = load_oracle()
    from ice_hdm import build
    boxes, verts, params, st = build(
        os.path.join(r"D:\training\icepak", "10-1transient"),
        max_levels=2, surface_extra=1, use_object_sizes=False,
        max_cells=400000, cyl_cap=6, shell_factor=0.8, curv_c=0.165,
        proj_tol=0.02 * 0.25)
    verts = np.unique(np.round(verts, 12), axis=0)
    for name, pts in (("oracle", oracle), ("ours", verts)):
        for ax, aname in enumerate(("x", "y")):
            vals = np.unique(np.round(pts[:, ax], 12))
            sh, bg = partition(vals)
            print("%s %s: total %d shell %d background %d"
                  % (name, aname, len(vals), len(sh), len(bg)))
            # background: how many on binary lattice of 0.02?
            frac = (bg / 0.02) % 1.0
            on_lattice = ((frac < 1e-6) | (frac > 1 - 1e-6)).sum()
            print("    background on 0.02-lattice: %d (%.1f%%)"
                  % (on_lattice, on_lattice * 100.0 / max(1, len(bg))))


if __name__ == "__main__":
    main()
