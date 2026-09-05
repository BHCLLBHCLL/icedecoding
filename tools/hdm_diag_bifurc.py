# -*- coding: utf-8 -*-
"""I1c diagnostic: decompose distinct x/y into background vs ring layers.

Hypothesis under test: the (0.105,0.48)/(0.11,0.45) "bifurcation" (y +97%)
is the parity of n = int(2*pi/pitch_c): for even n the sin grid self-pairs
(sin(pi-x)=sin x via k <-> n/2-k) so distinct sin ~ n/2; for odd n there is
no identity pairing so distinct sin ~ n -> y_rings doubles.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ice_hdm
from ice_hdm import build

JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
NL = bytes([10])
ORACLE_XY = (8190, 6777)


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(NL)
    if not raw.endswith(NL):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return r[0] if r and r[0] is not None else np.zeros((0, 3))


def diag(pitch, zfrac, oracle):
    captured = {}
    orig = ice_hdm.ring_nodes

    def spy(cyls, **kw):
        r = orig(cyls, **kw)
        captured["rings"] = r
        captured["cyls"] = [dict(c) for c in cyls]
        captured["kw"] = dict(kw)
        return r

    ice_hdm.ring_nodes = spy
    try:
        boxes, verts, params, st = build(
            JDIR, max_levels=2, surface_extra=1, use_object_sizes=True,
            max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
            proj_tol=None, ring_pitch=pitch, ring_zfrac=zfrac,
            ring_stagger=0.0, ring_lattice=False, ring_base_step=0.02)
    finally:
        ice_hdm.ring_nodes = orig

    rings = captured["rings"]
    vr = np.round(verts, 12)
    rr = np.round(rings, 12)
    # background = verts minus ring rows (multiset by exact rounded row)
    def rows(a):
        v = np.ascontiguousarray(a)
        view = v.view([("f%d" % i, np.float64) for i in range(v.shape[1])])
        return view.ravel()
    rv, rrk = rows(vr), rows(rr)
    # multiset-safe removal: one matching vert row per ring row
    from collections import Counter
    rvb = np.array([r.tobytes() for r in rv])
    rrk = np.array([r.tobytes() for r in rrk])
    need = Counter(rrk.tolist())
    bg_rows = []
    for i in range(len(rvb)):
        k = rvb[i]
        if need.get(k, 0) > 0:
            need[k] -= 1
        else:
            bg_rows.append(i)
    bg = vr[bg_rows]

    n_ang = int(2 * np.pi / max(pitch, 1e-4))
    th = 2 * np.pi * np.arange(n_ang) / n_ang
    d_cos = len(np.unique(np.round(np.cos(th), 12)))
    d_sin = len(np.unique(np.round(np.sin(th), 12)))

    cyls = captured["cyls"]
    # rings per cylinder + z levels
    per_z = []
    for c in cyls:
        z = np.unique(np.round(rr[np.abs(rr[:, 0] - c["p1"][0]) < 1e-9][:, 2]
                               if len(rr) else [], 9))
        per_z.append(len(z))
    # per-column ring x sets (group cylinders by cx)
    cxs = sorted(set(round(float(c["p1"][0]), 9) for c in cyls))
    col_sets = []
    for cx in cxs:
        m = np.abs(rr[:, 0] - cx) < 1e-9
        col_sets.append(sorted(set(np.round(rr[m][:, 0], 12).tolist())))
    ov01 = []
    if len(col_sets) >= 2:
        a, b = set(col_sets[0]), set(col_sets[1])
        ov01 = [len(a & b), len(a), len(b)]

    rec = {
        "pitch": pitch, "zfrac": zfrac, "n_ang": n_ang,
        "n_parity": "even" if n_ang % 2 == 0 else "odd",
        "distinct_cos": d_cos, "distinct_sin": d_sin,
        "nodes": len(verts), "rings": len(rings), "bg": len(bg),
        "rings_per_cyl": per_z,
        "x_total": len(np.unique(vr[:, 0])),
        "y_total": len(np.unique(vr[:, 1])),
        "x_rings": len(np.unique(rr[:, 0])) if len(rr) else 0,
        "y_rings": len(np.unique(rr[:, 1])) if len(rr) else 0,
        "x_bg": len(np.unique(bg[:, 0])) if len(bg) else 0,
        "y_bg": len(np.unique(bg[:, 1])) if len(bg) else 0,
        "col_x_overlap_a_b": ov01,
        "oracle_xy": list(ORACLE_XY),
    }
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec


def main():
    oracle = load_oracle()
    out = [diag(0.10, 0.50, oracle), diag(0.105, 0.48, oracle),
           diag(0.11, 0.45, oracle)]
    p = os.path.join(ROOT, "tools", "probe_work", "diag_bifurc.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
