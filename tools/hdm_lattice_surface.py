# -*- coding: utf-8 -*-
"""P19-1: lattice-derived surface sampling - same-column partial overlap check.

Generates surface nodes for the 10-1transient cylinder column (cx=0.15,
rows 0.25/0.30/0.35, cone r1=0.012 -> r2=0.02, z 0.13-0.19) via the GLOBAL
lattice mechanism and measures the oracle's fingerprint: same-column x/y
sets overlap PARTIALLY (oracle 27-41%), plus per-column distinct x/y and
the fine position spectrum size.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import lattice_surface_nodes

JOB = "10-1transient"
CX = 0.15
ROWS = (0.25, 0.30, 0.35)


def cyls():
    out = []
    for y in ROWS:
        out.append({"p1": np.array([CX, y, 0.13]),
                    "p2": np.array([CX, y, 0.19]),
                    "r1": 0.012, "r2": 0.02})
    return out


def annulus(pts, cy):
    rho = np.hypot(pts[:, 0] - CX, pts[:, 1] - cy)
    m = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19) & \
        (rho > 0.005) & (rho < 0.035)
    return pts[m]


def measure(depth, phase, band, snap_tol=1.0, stagger=0.0):
    pts = lattice_surface_nodes(cyls(), base=0.02, depth=depth,
                                phase=phase, band=band, snap_tol=snap_tol,
                                stagger=stagger)
    cols = {}
    for cy in ROWS:
        a = annulus(pts, cy)
        cols[cy] = (set(np.round(a[:, 0], 12)),
                    set(np.round(a[:, 1], 12)), len(a))
    ov = []
    for i, c1 in enumerate(ROWS):
        for c2 in ROWS[i + 1:]:
            ox = len(cols[c1][0] & cols[c2][0]) / float(
                max(len(cols[c1][0]), 1))
            oy = len(cols[c1][1] & cols[c2][1]) / float(
                max(len(cols[c1][1]), 1))
            ov.append((ox, oy))
    return {"depth": depth, "phase": list(phase), "band": band,
            "snap_tol": snap_tol, "stagger": stagger, "nodes": len(pts),
            "per_col_x": [len(cols[c][0]) for c in ROWS],
            "per_col_y": [len(cols[c][1]) for c in ROWS],
            "per_col_n": [cols[c][2] for c in ROWS],
            "overlap_xy": [[round(o, 4) for o in pair] for pair in ov]}


def main():
    out = []
    for depth in (3, 4):
        for phase in ((0.0, 0.008),):
            for band in (1.0, 1.5):
                for snap_tol in (0.3, 0.4):
                    for stagger in (0.3, 0.5, 0.7):
                        t0 = time.time()
                        rec = measure(depth, phase, band, snap_tol,
                                      stagger)
                rec["elapsed"] = round(time.time() - t0, 2)
                print(json.dumps(rec, ensure_ascii=False), flush=True)
                out.append(rec)
    out.sort(key=lambda r: min(
        min((abs(o[0] - 0.34), abs(o[1] - 0.34)) for o in r["overlap_xy"]),
        default=9.0))
    pout = os.path.join(ROOT, "tools", "probe_work",
                        "hdm_lattice_surface.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")


if __name__ == "__main__":
    main()
