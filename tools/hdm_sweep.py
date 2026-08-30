# -*- coding: utf-8 -*-
"""P18c: refinement-depth sweep (cyl_cap x shell width x object sizes) to
align our x/y position spectra with the oracle (10-1: 8190 / 6777)."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match

JOB = "10-1transient"


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


def run(cfg):
    jdir = os.path.join(r"D:\training\icepak", JOB)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1,
        use_object_sizes=cfg.get("obj", False),
        max_cells=400000, cyl_cap=cfg["cap"],
        shell_factor=cfg.get("factor", 1.05),
        curv_c=cfg.get("curv_c"))
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    axes = {}
    for ax, name in enumerate(("x", "y", "z")):
        axes[name] = [len(np.unique(np.round(verts[:, ax], 12))),
                      len(np.unique(np.round(oracle[:, ax], 12)))]
    rec = {"cfg": cfg, "leaves": len(boxes), "nodes": len(verts),
           "oracle_nodes": n, "axes_ours_vs_oracle": axes,
           "median": m["oracle_to_our"][1],
           "c1e6": m["oracle_matched_1e-6"],
           "c1e4": m["oracle_matched_1e-4"],
           "c1e3": m["oracle_matched_1e-3"],
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    cfgs = [
        {"cap": 3, "factor": 1.05, "obj": False},
        {"cap": 3, "factor": 1.05, "obj": True},
        {"cap": 4, "factor": 0.55, "obj": False},
        {"cap": 4, "factor": 0.55, "obj": True},
    ]
    out = []
    for c in cfgs:
        try:
            out.append(run(c))
        except Exception as e:
            print({"cfg": c, "error": repr(e)}, flush=True)
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_sweep.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("saved", pout)


if __name__ == "__main__":
    main()
