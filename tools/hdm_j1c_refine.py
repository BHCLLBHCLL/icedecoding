# -*- coding: utf-8 -*-
"""J1c forensic: main-layer 2D refinement structure.

For each of the 7 cylinder-span layers (3212 nodes each):
  - layer set vs coarse skeleton set: R = layer - coarse, A = coarse - layer
  - refinement node clustering per cylinder footprint
  - (rho, theta) quantisation relative to the cylinder axis
  - cross-layer overlap of refinement sets
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

JOB = "10-1transient"
JDIR = os.path.join("D:", os.sep, "training", "icepak", JOB)
OUT = os.path.join(ROOT, "tools", "probe_work", "j1c_refine.json")

CYLS = [(0.15, 0.25), (0.15, 0.3), (0.15, 0.35), (0.2, 0.25), (0.2, 0.3),
        (0.2, 0.35), (0.25, 0.25), (0.25, 0.3), (0.25, 0.35)]
MAIN_Z = [0.13, 0.135, 0.145, 0.16, 0.175, 0.185, 0.19]
# cone radius at layer z: r1=0.02 at z=0.13 -> r2=0.012 at z=0.19
def r_at(z):
    return 0.02 + (0.012 - 0.02) * (z - 0.13) / 0.06


def main():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    layer = lambda zz: nodes[np.abs(z - zz) < 1e-9][:, :2]
    coarse = set(map(tuple, np.round(layer(0.25), 12)))

    out = {"layers": []}
    sets = {}
    for zz in MAIN_Z:
        S = set(map(tuple, np.round(layer(zz), 12)))
        sets[zz] = S
        R = S - coarse
        A = coarse - S
        out["layers"].append({
            "z": zz, "r": round(r_at(zz), 5), "n": len(S),
            "refine": len(R), "coarse_absent": len(A),
            "coarse_kept": len(S & coarse)})
    out["layers_sum"] = {
        "refine": sum(l["refine"] for l in out["layers"]),
        "coarse_absent": sum(l["coarse_absent"] for l in out["layers"])}

    # per-cylinder cluster structure at z=0.16 and z=0.13
    detail = {}
    for zz in (0.13, 0.16, 0.19):
        S = sets[zz]
        R = np.array(sorted(S - coarse))
        C = np.array(CYLS)
        d = np.sqrt(((R[:, None, :] - C[None, :, :]) ** 2).sum(-1)).min(1)
        near = R[d < 0.045]
        far = R[d >= 0.045]
        cx, cy = CYLS[0]
        r = r_at(zz)
        # cluster around cylinder (0.15, 0.25): nodes with |x-0.15|<=0.03, |y-0.25|<=0.03
        m = (np.abs(R[:, 0] - cx) <= 0.032) & (np.abs(R[:, 1] - cy) <= 0.032)
        cl = R[m]
        rho = np.sqrt((cl[:, 0] - cx) ** 2 + (cl[:, 1] - cy) ** 2)
        th = np.arctan2(cl[:, 1] - cy, cl[:, 0] - cx)
        rec = {
            "refine_total": len(R), "near_cyls": len(near),
            "far_from_cyls": len(far), "cluster1": int(m.sum()),
            "rho_hist": {round(float(a), 5): int(b) for a, b in
                         sorted(Counter(np.round(rho, 4).items().__iter__())
                                )} if False else None,
        }
        # rho levels: distinct rho rounded to 1e-4, top values
        rc = Counter(np.round(rho, 5).tolist())
        rec["rho_top"] = [[k, v] for k, v in
                          sorted(rc.items(), key=lambda t: -t[1])[:12]]
        rec["rho_near_r"] = int((np.abs(rho - r) < 5e-4).sum())
        # ring nodes (|rho - r| < 2e-3): angular count
        ring = np.abs(rho - r) < 2e-3
        rec["ring_nodes"] = int(ring.sum())
        if ring.any():
            ts = np.sort(th[ring])
            rec["ring_theta_min_gap"] = float(np.min(np.diff(ts))) \
                if len(ts) > 1 else None
        # far nodes: where are they?
        if len(far):
            fx = Counter(np.round(far[:, 0], 3).tolist())
            fy = Counter(np.round(far[:, 1], 3).tolist())
            rec["far_x_top"] = [[k, v] for k, v in fx.most_common(6)]
            rec["far_y_top"] = [[k, v] for k, v in fy.most_common(6)]
        detail[str(zz)] = rec
    out["detail"] = detail

    # cross-layer refinement overlap
    ov = {}
    refsets = {zz: sets[zz] - coarse for zz in MAIN_Z}
    for i, a in enumerate(MAIN_Z):
        for b in MAIN_Z[i + 1:]:
            ov["%.3f-%.3f" % (a, b)] = len(refsets[a] & refsets[b])
    out["refine_overlap"] = ov

    print(json.dumps(out, indent=1, default=float)[:5500])
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1,
              default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
