# -*- coding: utf-8 -*-
"""P18e: re-sweep after bounded-face fix (landscape shifted)."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match

JOB = "10-1transient"
CURV_C = 0.165
ORACLE_XY = (8190, 6777)


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


def run(sf, tf, curv_c=CURV_C, max_cells=400000):
    jdir = os.path.join(r"D:\training\icepak", JOB)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=False,
        max_cells=max_cells, cyl_cap=6, shell_factor=sf, curv_c=curv_c,
        proj_tol=0.02 * tf)
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    ax = {}
    for i, name in enumerate(("x", "y", "z")):
        ax[name] = len(np.unique(np.round(verts[:, i], 12)))
    dx = (ax["x"] - ORACLE_XY[0]) / float(ORACLE_XY[0])
    dy = (ax["y"] - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"shell_factor": sf, "tol_factor": tf, "curv_c": curv_c,
           "nodes": len(verts), "leaves": len(boxes),
           "x": ax["x"], "y": ax["y"],
           "dx_pct": round(dx * 100, 2), "dy_pct": round(dy * 100, 2),
           "score": abs(dx) + abs(dy),
           "median": m["oracle_to_our"][1],
           "c1e3": m["oracle_matched_1e-3"],
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    out = []
    # coarser shell + tighter proj (to counter the freed budget)
    for sf, tf in ((0.8, 0.25), (0.6, 0.25), (0.8, 0.2), (0.6, 0.2),
                   (0.8, 0.3), (0.5, 0.25), (0.4, 0.2), (0.4, 0.25)):
        try:
            out.append(run(sf, tf))
        except Exception as e:
            print({"sf": sf, "tf": tf, "error": repr(e)}, flush=True)
    out.sort(key=lambda r: r.get("score", 9e9))
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_sweep2d_b.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")


if __name__ == "__main__":
    main()
