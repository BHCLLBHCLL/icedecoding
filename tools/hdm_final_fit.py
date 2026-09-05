# -*- coding: utf-8 -*-
"""I1: P19-1 final parameter fit on the full 10-1 pipeline."""
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
NL = bytes([10])
JDIR = os.path.join("D:", os.sep, "training", "icepak", JOB)


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(NL)
    if not raw.endswith(NL):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return (r[0] if r and r[0] is not None else np.zeros((0, 3))), n


def run(pitch, zfrac, lattice, base_step):
    t0 = time.time()
    boxes, verts, params, st = build(
        JDIR, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None, ring_pitch=pitch, ring_zfrac=zfrac,
        ring_stagger=0.0, ring_lattice=lattice, ring_base_step=base_step)
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    dx = len(np.unique(np.round(verts[:, 0], 12)))
    dy = len(np.unique(np.round(verts[:, 1], 12)))
    ddx = (dx - ORACLE_XY[0]) / float(ORACLE_XY[0])
    ddy = (dy - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"pitch": pitch, "zfrac": zfrac, "lattice": lattice,
           "base_step": base_step, "nodes": len(verts), "x": dx, "y": dy,
           "dx_pct": round(ddx * 100, 2), "dy_pct": round(ddy * 100, 2),
           "ratio": round(dx / float(dy), 4),
           "score": round(abs(ddx) + abs(ddy), 4),
           "c1e3": round(float(m["oracle_matched_1e-3"]), 4),
           "median": round(float(m["oracle_to_our"][1]), 6),
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    grid = [(0.10, 0.50, False, 0.02), (0.105, 0.48, False, 0.02),
            (0.11, 0.45, False, 0.02)]
    out = []
    for cfg in grid:
        try:
            out.append(run(*cfg))
        except Exception as e:
            print(json.dumps({"cfg": cfg, "error": repr(e)}), flush=True)
    out.sort(key=lambda r: r.get("score", 9e9))
    pout = os.path.join(ROOT, "tools", "probe_work", "final_fit.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
