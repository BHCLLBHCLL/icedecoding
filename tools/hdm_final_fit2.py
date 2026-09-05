# -*- coding: utf-8 -*-
"""I1c: mechanism-level final fit — decoupled even-n rings + per-axis
partial lattice snap (the parity-stabilised interpolation path).

Stage 1: n x zfrac response at snap off (n decoupled from pitch_c).
Stage 2: y-merge calibration (snap_g x snap_tol_y) at the best n.
Writes tools/probe_work/final_fit2.json incrementally.
"""
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
OUT = os.path.join(ROOT, "tools", "probe_work", "final_fit2.json")


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(NL)
    if not raw.endswith(NL):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return (r[0] if r and r[0] is not None else np.zeros((0, 3))), n


ORACLE = None


def run(n_ang, zfrac, snap_g=None, tol_x=0.0, tol_y=0.0, pitch=0.10):
    global ORACLE
    t0 = time.time()
    if ORACLE is None:
        ORACLE = load_oracle()[0]
    boxes, verts, params, st = build(
        JDIR, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None, ring_pitch=pitch, ring_zfrac=zfrac,
        ring_stagger=0.0, ring_lattice=False, ring_base_step=0.02,
        ring_n=n_ang, ring_snap_g=snap_g, ring_snap_tol_x=tol_x,
        ring_snap_tol_y=tol_y)
    verts = np.unique(np.round(verts, 12), axis=0)
    m = position_match(verts, ORACLE)
    dx = len(np.unique(np.round(verts[:, 0], 12)))
    dy = len(np.unique(np.round(verts[:, 1], 12)))
    ddx = (dx - ORACLE_XY[0]) / float(ORACLE_XY[0])
    ddy = (dy - ORACLE_XY[1]) / float(ORACLE_XY[1])
    rec = {"n": n_ang, "zfrac": zfrac, "pitch": pitch, "snap_g": snap_g,
           "tol_x": tol_x, "tol_y": tol_y, "nodes": len(verts),
           "x": dx, "y": dy,
           "dx_pct": round(ddx * 100, 2), "dy_pct": round(ddy * 100, 2),
           "ratio": round(dx / float(dy), 4),
           "score": round(abs(ddx) + abs(ddy), 4),
           "both5": bool(abs(ddx) <= 0.05 and abs(ddy) <= 0.05),
           "c1e3": round(float(m["oracle_matched_1e-3"]), 4),
           "median": round(float(m["oracle_to_our"][1]), 6),
           "elapsed": round(time.time() - t0, 1)}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def load_recs():
    if os.path.exists(OUT):
        try:
            return json.load(open(OUT, encoding="utf-8"))
        except Exception:
            return []
    return []


def save(recs):
    recs.sort(key=lambda r: r.get("score", 9e9))
    json.dump(recs, open(OUT, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "1"
    recs = load_recs()
    if stage == "1":
        grid = [(n, zf) for n in (62, 64, 66, 68)
                for zf in (0.49, 0.50, 0.51)]
        for n, zf in grid:
            if any(r.get("n") == n and r.get("zfrac") == zf
                   and not r.get("snap_g") for r in recs):
                continue
            try:
                recs.append(run(n, zf))
            except Exception as e:
                print(json.dumps({"cfg": [n, zf], "error": repr(e)}),
                      flush=True)
            save(recs)
    elif stage == "2":
        grid = [(66, 0.50, 2e-4, ty) for ty in (0.01, 0.02, 0.05, 0.1)] \
             + [(66, 0.51, 2e-4, ty) for ty in (0.005, 0.01, 0.02, 0.05)]
        for n, zf, g, ty in grid:
            if any(r.get("n") == n and r.get("zfrac") == zf
                   and r.get("snap_g") == g and r.get("tol_y") == ty
                   for r in recs):
                continue
            try:
                recs.append(run(n, zf, snap_g=g, tol_y=ty))
            except Exception as e:
                print(json.dumps({"cfg": [n, zf, g, ty],
                                  "error": repr(e)}), flush=True)
            save(recs)
    elif stage == "3":
        grid = [(66, 0.50, 2e-4, ty) for ty in (0.06, 0.07, 0.08, 0.09)]
        for n, zf, g, ty in grid:
            if any(r.get("n") == n and r.get("zfrac") == zf
                   and r.get("snap_g") == g and r.get("tol_y") == ty
                   for r in recs):
                continue
            try:
                recs.append(run(n, zf, snap_g=g, tol_y=ty))
            except Exception as e:
                print(json.dumps({"cfg": [n, zf, g, ty],
                                  "error": repr(e)}), flush=True)
            save(recs)
    elif stage == "4":
        grid = [(70, 0.50, None, 0.0), (72, 0.50, None, 0.0)]
        for n, zf, g, ty in grid:
            if any(r.get("n") == n and r.get("zfrac") == zf
                   and not r.get("snap_g") for r in recs):
                continue
            try:
                recs.append(run(n, zf))
            except Exception as e:
                print(json.dumps({"cfg": [n, zf], "error": repr(e)}),
                      flush=True)
            save(recs)
    best = min(recs, key=lambda r: r.get("score", 9e9))
    print("BEST:", json.dumps(best, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
