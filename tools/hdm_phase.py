# -*- coding: utf-8 -*-
"""P18g: base-lattice phase sweep — reproduce the oracle's 1.20 x/y ratio."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match

JOB = "10-1transient"
ORACLE_XY = (8190, 6777)
RATIO = 8190.0 / 6777.0


def load_oracle():
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", JOB)
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    return pts, n


def run(dx, dy):
    jdir = os.path.join(r"D:\training\icepak", JOB)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None, base_phase=(dx, dy, 0.0))
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    ax = {}
    for i, name in enumerate(("x", "y")):
        ax[name] = len(np.unique(np.round(verts[:, i], 12)))
    r = ax["x"] / float(ax["y"])
    ddx = (ax["x"] - ORACLE_XY[0]) / float(ORACLE_XY[0])
    ddy = (ax["y"] - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"phase": [dx, dy], "nodes": len(verts),
           "x": ax["x"], "y": ax["y"], "ratio": round(r, 4),
           "dx_pct": round(ddx * 100, 2), "dy_pct": round(ddy * 100, 2),
           "score": abs(ddx) + abs(ddy),
           "c1e3": m["oracle_matched_1e-3"],
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    out = []
    for dx in (0.0, 0.002, 0.004, 0.006, 0.008, 0.01):
        for dy in (0.0, 0.002, 0.004, 0.006, 0.008, 0.01):
            try:
                out.append(run(dx, dy))
            except Exception as e:
                print({"phase": [dx, dy], "error": repr(e)}, flush=True)
    out.sort(key=lambda r: r.get("score", 9e9))
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_phase.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("oracle ratio:", RATIO)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")


if __name__ == "__main__":
    main()
