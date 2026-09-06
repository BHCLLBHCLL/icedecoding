# -*- coding: utf-8 -*-
"""J3 assembly: build every z-level's (x,y) grid from the recovered
components and score the exact-match coverage against the oracle.

Components (formula vs golden table):
  - skeleton_x/y : J1b law (graded chains + fitted quad-segment
                   decompositions)  [FORMULA]
  - ring angles  : j1c 24-angle star (normalised pairs) [FORMULA]
  - template     : per-cylinder fixed offsets [GOLDEN TABLE]
  - far 30       : block/quad neighbourhood [GOLDEN TABLE]
  - replaced     : per-level skeleton nodes removed [GOLDEN TABLE]
  - warp images  : skeleton-line images under W [GOLDEN TABLE; boundary
                   of the warp patch only — interior images NOT closed]
Coarse levels use skeleton only (proved exact in J1b).
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ice_hdm
from tools.hdm_j1b_regenerate import (X_ANCHORS, X_OVERRIDES,
                                      Y_ANCHORS, Y_OVERRIDES, skeleton)

OUT = os.path.join(ROOT, "tools", "probe_work", "j3_coverage.json")
JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")

CYLS = [(0.15, 0.25), (0.15, 0.3), (0.15, 0.35), (0.2, 0.25), (0.2, 0.3),
        (0.2, 0.35), (0.25, 0.25), (0.25, 0.3), (0.25, 0.35)]
MAIN_Z = [0.13, 0.135, 0.145, 0.16, 0.175, 0.185, 0.19]
# 24-angle star, r-normalised pairs (j1c probe_work/j1c_ring.json,
# verified identical at z=0.13/0.16/0.19)
RING_PAIRS = [
    (1.0, 0.0), (0.952976, 0.303046), (0.819961, 0.57242),
    (0.707107, 0.707107), (0.57242, 0.819961), (0.303046, 0.952976),
    (0.0, 1.0), (-0.303046, 0.952976), (-0.57242, 0.819961),
    (-0.707107, 0.707107), (-0.819961, 0.57242), (-0.952976, 0.303046),
    (-1.0, 0.0), (-0.952976, -0.303046), (-0.819961, -0.57242),
    (-0.707107, -0.707107), (-0.57242, -0.819961), (-0.303046, -0.952976),
    (0.0, -1.0), (0.303046, -0.952976), (0.57242, -0.819961),
    (0.707107, -0.707107), (0.819961, -0.57242), (0.952976, -0.303046)]


def r_at(z):
    return 0.02 + (0.012 - 0.02) * (z - 0.13) / 0.06


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(bytes([10]))
    if not raw.endswith(bytes([10])):
        n += 1
    return extract_nodes(os.path.join(JDIR, "grid_output"), n)[0]


def rxy_set(pts):
    return set(map(tuple, np.round(pts, 12)))


def main():
    from icepak_parser.project import IcepakProject
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    cnt = Counter(z.tolist())
    levels = sorted(cnt.items())
    orac = {zz: rxy_set(nodes[np.abs(z - zz) < 1e-9][:, :2])
            for zz, c in levels}

    def classify(c):
        if c == 1710:
            return "coarse"
        if c == 3212:
            return "main"
        if c == 1470:
            return "mid"
        if c in (1932, 1665):
            return "special"
        if c == 1:
            return "artifact"
        return "cluster"

    sk = rxy_set(np.array([(x, y) for x in skeleton(X_ANCHORS, X_OVERRIDES)
                           for y in skeleton(Y_ANCHORS, Y_OVERRIDES)]))

    # --- golden tables (from oracle, layer-independent) ---
    # shared/fixed per-cylinder templates + far from the 7-layer shared set
    shared = set.intersection(*[orac[zz] - sk for zz in MAIN_Z])
    shared = {p for p in shared if p not in sk}
    Sarr = np.array(sorted(shared))
    C = np.array(CYLS)
    d = np.sqrt(((Sarr[:, None, :] - C[None, :, :]) ** 2).sum(-1))
    nearest = d.argmin(1)
    dmin = d.min(1)
    templates = {}
    far = []
    for ci, (cx, cy) in enumerate(CYLS):
        m = (nearest == ci) & (dmin < 0.05)
        templates[ci] = sorted(set(map(tuple, np.round(Sarr[m], 12))))
    farpts = sorted(set(map(tuple, np.round(Sarr[dmin >= 0.05], 12))))
    # replaced per level (skeleton nodes absent in the layer)
    replaced = {}
    for zz, _ in levels:
        t = orac[zz]
        replaced[zz] = sorted(sk - t)
    # warp images (boundary of the warp patch, per cylinder-1 pattern)
    wf = json.load(open(os.path.join(ROOT, "tools", "probe_work",
                                     "j1c_warpfull.json"), encoding="utf-8"))
    warps_x = [tuple(p) for p in wf["samples_x"]]
    warps_y = [tuple(p) for p in wf["samples_y"]]

    def warp_set(cx, cy):
        s = set()
        for y0, x0, xp in warps_x:
            s.add((xp, cy + (y0 - 0.25)))
        for x0, y0, yp in warps_y:
            s.add((cx + (x0 - 0.15), yp))
        return {p for p in s if p not in sk}

    per_level = {}
    totals = {"exact": 0, "partial_nodes": 0, "oracle_nodes": 0}
    class_acc = {}
    for zz, c in levels:
        t = classify(c)
        if t == "coarse":
            our = sk
        elif t in ("main", "special", "mid", "cluster"):
            base = sk - set(replaced[zz])
            ring = set()
            r = r_at(zz) if t == "main" else 0.016
            for cx, cy in CYLS:
                for px, py in RING_PAIRS:
                    ring.add((round(cx + r * px, 12),
                              round(cy + r * py, 12)))
            our = base | ring
            for ci in range(len(CYLS)):
                our |= set(templates[ci])
                our |= warp_set(*CYLS[ci])
            our |= set(farpts)
        else:
            our = sk
        o = orac[zz]
        ov = len(our & o)
        per_level[str(zz)] = {"type": t, "oracle": len(o), "ours": len(our),
                              "exact": bool(our == o),
                              "matched": ov,
                              "frac": round(ov / float(len(o)), 4)}
        if our == o:
            totals["exact"] += len(o)
        totals["partial_nodes"] += ov
        totals["oracle_nodes"] += len(o)
        acc = class_acc.setdefault(t, {"oracle": 0, "matched": 0})
        acc["oracle"] += len(o)
        acc["matched"] += ov

    rec = {
        "skeleton_nodes": len(sk),
        "template_per_cyl": {str(k): len(v) for k, v in templates.items()},
        "far_n": len(farpts),
        "class_accuracy": {k: {**{m: v[m] for m in ("oracle", "matched")},
                               "frac": round(v["matched"] /
                                             float(v["oracle"]), 4)}
                           for k, v in class_acc.items()},
        "total_nodes": totals["oracle_nodes"],
        "exact_levels": sum(1 for p in per_level.values() if p["exact"]),
        "exact_level_nodes": totals["exact"],
        "matched_nodes": totals["partial_nodes"],
        "matched_frac": round(totals["partial_nodes"] /
                              float(totals["oracle_nodes"]), 4),
        "per_level": per_level,
    }
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in rec.items() if k != "per_level"},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
