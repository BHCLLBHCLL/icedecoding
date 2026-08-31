# -*- coding: utf-8 -*-
"""P18j: measure theta-stagger effect (per-cylinder phase diversity)."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match, ring_nodes

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


def run(pitch, zfrac, tag):
    jdir = os.path.join(r"D:\training\icepak", JOB)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None, ring_pitch=pitch, ring_zfrac=zfrac)
    verts = np.unique(np.round(verts, 12), axis=0)
    oracle, n = load_oracle()
    m = position_match(verts, oracle)
    ax = {}
    for i, name in enumerate(("x", "y")):
        ax[name] = len(np.unique(np.round(verts[:, i], 12)))
    ddx = (ax["x"] - ORACLE_XY[0]) / float(ORACLE_XY[0])
    ddy = (ax["y"] - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"tag": tag, "pitch": pitch, "zfrac": zfrac, "nodes": len(verts),
           "x": ax["x"], "y": ax["y"],
           "dx_pct": round(ddx * 100, 2), "dy_pct": round(ddy * 100, 2),
           "ratio": round(ax["x"] / float(ax["y"]), 4),
           "score": abs(ddx) + abs(ddy),
           "c1e3": m["oracle_matched_1e-3"],
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    out = []
    out.append(run(0.10, 0.5, "stagger"))
    out.append(run(0.10, 0.5, "stagger"))  # reproducibility not needed; dup
    # no-stagger reference via monkeypatching default? build uses stagger
    # by default now — measure both via direct ring counts instead:
    from ice_hdm import model_cylinders
    from icepak_parser.project import IcepakProject
    m = IcepakProject(os.path.join(r"D:\training\icepak", JOB)).model
    cyls = model_cylinders(m)
    for tag, st in (("no-stagger", False), ("stagger", True)):
        r = ring_nodes(cyls, pitch_c=0.10, z_frac=0.5, theta_stagger=st)
        print("rings-only", tag, len(r), "distinct x/y:",
              len(np.unique(np.round(r[:, 0], 12))),
              len(np.unique(np.round(r[:, 1], 12))), flush=True)
    out.sort(key=lambda r: r.get("score", 9e9))
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_stagger.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("BEST:", json.dumps(out[0], ensure_ascii=False) if out else "none")


if __name__ == "__main__":
    main()
