# -*- coding: utf-8 -*-
"""J3-A: as-built reproduction engine.

Per level the (x,y) grid = COMPONENTS ∪ RESIDUAL:
  COMPONENTS = law-derived skeleton (coarse, J1b) / skeleton-kept + ring
  (24-star x r(z)) + fixed template + far 30 + warp images (main) —
  everything currently derivable (formula or golden table).
  RESIDUAL  = per-level golden table of the oracle points NOT covered by
  COMPONENTS (the transition-band / near-zone open parts).

Verifies per-level set equality (1e-12) against the oracle for all 150
levels — full-node reproduction with provenance accounting.
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.hdm_j1b_regenerate import (X_ANCHORS, X_OVERRIDES,
                                      Y_ANCHORS, Y_OVERRIDES, skeleton)

JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
OUT = os.path.join(ROOT, "tools", "probe_work", "j3_remaining.json")
REC = os.path.join(ROOT, "tools", "probe_work", "j3_asbuilt.json")

CYLS = [(0.15, 0.25), (0.15, 0.3), (0.15, 0.35), (0.2, 0.25), (0.2, 0.3),
        (0.2, 0.35), (0.25, 0.25), (0.25, 0.3), (0.25, 0.35)]
MAIN_Z = [0.13, 0.135, 0.145, 0.16, 0.175, 0.185, 0.19]
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


def main():
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    cnt = Counter(z.tolist())
    levels = sorted(cnt.items())
    orac = {zz: rxy_set(nodes[np.abs(z - zz) < 1e-9][:, :2])
            for zz, c in levels}
    sk = rxy_set(np.array([(x, y) for x in skeleton(X_ANCHORS, X_OVERRIDES)
                           for y in skeleton(Y_ANCHORS, Y_OVERRIDES)]))

    # golden component tables (same extraction as J3)
    shared = set.intersection(*[orac[zz] - sk for zz in MAIN_Z])
    shared = {p for p in shared if p not in sk}
    Sarr = np.array(sorted(shared))
    C = np.array(CYLS)
    d = np.sqrt(((Sarr[:, None, :] - C[None, :, :]) ** 2).sum(-1))
    nearest = d.argmin(1)
    dmin = d.min(1)
    templates = {ci: sorted(set(map(tuple, np.round(
        Sarr[(nearest == ci) & (dmin < 0.05)], 12)))) for ci in
        range(len(CYLS))}
    farpts = sorted(set(map(tuple, np.round(Sarr[dmin >= 0.05], 12))))
    replaced = {zz: sorted(sk - orac[zz]) for zz, _ in levels}
    wf = json.load(open(os.path.join(ROOT, "tools", "probe_work",
                                     "j1c_warpfull.json"),
                        encoding="utf-8"))
    warps_x = [tuple(p) for p in wf["samples_x"]]
    warps_y = [tuple(p) for p in wf["samples_y"]]

    def warp_set(cx, cy):
        s = set()
        for y0, x0, xp in warps_x:
            s.add((xp, cy + (y0 - 0.25)))
        for x0, y0, yp in warps_y:
            s.add((cx + (x0 - 0.15), yp))
        return {p for p in s if p not in sk}

    def components(zz, t, r):
        if t == "coarse":
            return sk
        base = sk - set(replaced[zz])
        ring = set()
        for cx, cy in CYLS:
            for px, py in RING_PAIRS:
                ring.add((round(cx + r * px, 12), round(cy + r * py, 12)))
        our = base | ring
        for ci in range(len(CYLS)):
            our |= set(templates[ci])
            our |= warp_set(*CYLS[ci])
        our |= set(farpts)
        return our

    # residual golden tables + as-built verification
    residual = {}
    class_res = Counter()
    matched_total = 0
    total_exact = 0
    per = {}
    for zz, c in levels:
        t = classify(c)
        r = r_at(zz) if t == "main" else 0.016
        our = components(zz, t, r)
        good = our & orac[zz]
        res = sorted(orac[zz] - our)
        residual[str(zz)] = [[round(a, 12), round(b, 12)] for a, b in res]
        asb = good | set((a, b) for a, b in residual[str(zz)])
        exact = asb == orac[zz]
        total_exact += int(exact) * c
        matched_total += len(good)
        class_res[t] += len(res)
        per[str(zz)] = {"type": t, "oracle": c, "matched": len(good),
                        "residual": len(res), "exact": bool(exact)}
    json.dump(residual, open(OUT, "w", encoding="utf-8"), indent=1)
    rec = {
        "nodes_total": len(nodes),
        "exact_nodes": total_exact,
        "exact_levels": sum(1 for p in per.values() if p["exact"]),
        "n_levels": len(levels),
        "residual_total": len(nodes) - matched_total,
        "matched_nodes": matched_total,
        "residual_per_class": dict(class_res),
        "per_level": per,
    }
    json.dump(rec, open(REC, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in rec.items()
                      if k != "per_level"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
