# -*- coding: utf-8 -*-
"""P18h: angular sampling histograms of cylinder-surface nodes
(oracle vs ours) — locate the tangent-neighbourhood overcount."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CX = 0.15
CY = 0.25


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


def ang_hist(pts, cx, cy):
    """Angular histogram of nodes in the annulus around (cx,cy)."""
    rho = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    zok = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19)
    m = (rho > 0.005) & (rho < 0.035) & zok
    th = np.arctan2(pts[m, 1] - cy, pts[m, 0] - cx)
    hist, edges = np.histogram(th, bins=np.linspace(-np.pi, np.pi, 37))
    return hist, len(th), edges


def main():
    oracle = load_oracle()
    from ice_hdm import build
    boxes, verts, params, st = build(
        os.path.join(r"D:\training\icepak", "10-1transient"),
        max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None, base_phase=(0.0, 0.008, 0.0))
    verts = np.unique(np.round(verts, 12), axis=0)
    for name, pts in (("oracle", oracle), ("ours", verts)):
        hist, n, edges = ang_hist(pts, CX, CY)
        print("==", name, "annulus nodes", n)
        print("   theta bins (-pi..pi, 10deg):")
        print("   ", [int(h) for h in hist])
        # quadrant totals
        q = [hist[:9].sum(), hist[9:18].sum(), hist[18:27].sum(),
             hist[27:36].sum()]
        print("   quadrant totals (x+,y+,x-,y-):", [int(v) for v in q])


if __name__ == "__main__":
    main()
