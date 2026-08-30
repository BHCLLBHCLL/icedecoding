# -*- coding: utf-8 -*-
"""P18f: re-sweep curv_c x shell_factor under the corrected pipeline
(bounded faces + local projection + object face-size field)."""
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


def run(sf, curv_c):
    jdir = os.path.join(r"D:\training\icepak", JOB)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=sf, curv_c=curv_c,
        proj_tol=None)
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    ax = {}
    for i, name in enumerate(("x", "y", "z")):
        ax[name] = len(np.unique(np.round(verts[:, i], 12)))
    dx = (ax["x"] - ORACLE_XY[0]) / float(ORACLE_XY[0])
    dy = (ax["y"] - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"shell_factor": sf, "curv_c": curv_c, "nodes": len(verts),
           "leaves": len(boxes),
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
    for sf in (0.3, 0.45, 0.6):
        for curv_c in (0.05, 0.08, 0.11, 0.14, 0.165):
            try:
                out.append(run(sf, curv_c))
            except Exception as e:
                print({"sf": sf, "curv_c": curv_c, "error": repr(e)},
                      flush=True)
    out.sort(key=lambda r: r.get("score", 9e9))
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_curvsweep.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")


if __name__ == "__main__":
    main()
