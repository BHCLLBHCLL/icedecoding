# -*- coding: utf-8 -*-
"""Run one curvature-criterion config (curv_c) for the depth alignment."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match

JOB = "10-1transient"


def main():
    jdir = os.path.join(r"D:\training\icepak", JOB)
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    oracle, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    out = []
    for curv_c in (0.17, 0.18, 0.2):
        t0 = time.time()
        boxes, verts, params, st = build(
            jdir, max_levels=2, surface_extra=1, use_object_sizes=False,
            max_cells=400000, cyl_cap=6, shell_factor=1.2, curv_c=curv_c)
        verts = np.unique(np.round(verts, 12), axis=0)
        m = position_match(verts, oracle)
        axes = {}
        for ax, name in enumerate(("x", "y", "z")):
            axes[name] = [len(np.unique(np.round(verts[:, ax], 12))),
                          len(np.unique(np.round(oracle[:, ax], 12)))]
        rec = {"cfg": {"curv_c": curv_c, "cap": 6, "factor": 1.2},
               "leaves": len(boxes), "nodes": len(verts),
               "axes_ours_vs_oracle": axes,
               "median": m["oracle_to_our"][1],
               "c1e6": m["oracle_matched_1e-6"],
               "c1e4": m["oracle_matched_1e-4"],
               "c1e3": m["oracle_matched_1e-3"],
               "elapsed": round(time.time() - t0, 1)}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        out.append(rec)
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_curv.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("saved", pout)


if __name__ == "__main__":
    main()
