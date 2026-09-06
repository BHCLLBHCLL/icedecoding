# -*- coding: utf-8 -*-
"""J1c forensic v2: exact per-cylinder refinement pattern.

- Voronoi assignment of refinement nodes to cylinder axes
- ring-24 angular test: theta = k*2*pi/24 ?
- fixed radii (layer-independent) exact values per cylinder
- shared-760 decomposition: per-cylinder shared vs layer-specific
- where are the 538 absent coarse nodes?
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CYLS = [(0.15, 0.25), (0.15, 0.3), (0.15, 0.35), (0.2, 0.25), (0.2, 0.3),
        (0.2, 0.35), (0.25, 0.25), (0.25, 0.3), (0.25, 0.35)]
MAIN_Z = [0.13, 0.135, 0.145, 0.16, 0.175, 0.185, 0.19]


def r_at(z):
    return 0.02 + (0.012 - 0.02) * (z - 0.13) / 0.06


def main():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    layer = lambda zz: nodes[np.abs(z - zz) < 1e-9][:, :2]
    coarse = set(map(tuple, np.round(layer(0.25), 12)))
    C = np.array(CYLS)

    out = {}
    refsets = {}
    for zz in MAIN_Z:
        S = set(map(tuple, np.round(layer(zz), 12)))
        refsets[zz] = S - coarse
    shared = set.intersection(*refsets.values())

    # Voronoi per-cylinder at z=0.16 (r=0.016) and z=0.13 (r=0.02)
    for zz in (0.13, 0.16):
        R = np.array(sorted(refsets[zz]))
        d = np.sqrt(((R[:, None, :] - C[None, :, :]) ** 2).sum(-1))
        nearest = d.argmin(1)
        dmin = d.min(1)
        r = r_at(zz)
        rec = {"refine": len(R), "shared": len(refsets[zz] & shared),
               "per_cyl": [], "far": []}
        for ci, (cx, cy) in enumerate(CYLS):
            m = (nearest == ci) & (dmin < 0.05)
            cl = R[m]
            rho = np.sqrt((cl[:, 0] - cx) ** 2 + (cl[:, 1] - cy) ** 2)
            th = np.arctan2(cl[:, 1] - cy, cl[:, 0] - cx)
            ring = np.abs(rho - r) < 1e-6
            # ring angular test vs 24-gon
            offs = []
            for t in th[ring]:
                k = round(t / (2 * np.pi / 24))
                offs.append(float(t - k * 2 * np.pi / 24))
            rec["per_cyl"].append({
                "n": int(m.sum()),
                "ring24": int(ring.sum()),
                "ring_theta_max_off_15deg": round(max(abs(o) for o in offs),
                                                   12) if offs else None,
                "rho_counts": {str(k): v for k, v in
                               sorted(Counter(np.round(rho, 9).tolist())
                                      .items(), key=lambda t: -t[1])[:10]},
            })
        far = R[dmin >= 0.05]
        rec["far_n"] = len(far)
        rec["far_xy"] = sorted(set(map(tuple, np.round(far, 6).tolist())))
        out["z%.3f" % zz] = rec

    # shared-760: per-cylinder fixed radii (z=0.16 shared nodes)
    S16 = np.array(sorted(refsets[0.16] & shared))
    d = np.sqrt(((S16[:, None, :] - C[None, :, :]) ** 2).sum(-1))
    nearest = d.argmin(1)
    dmin = d.min(1)
    shared_cyl = int((dmin < 0.05).sum())
    shared_far = int((dmin >= 0.05).sum())
    cx, cy = CYLS[0]
    m = (nearest == 0) & (dmin < 0.05)
    cl = S16[m]
    rho = np.sqrt((cl[:, 0] - cx) ** 2 + (cl[:, 1] - cy) ** 2)
    rc = Counter(np.round(rho, 9).tolist())
    out["shared"] = {"total": len(shared), "cyl": shared_cyl,
                     "far": shared_far,
                     "cyl1_rho_exact": {str(k): v for k, v in
                                        sorted(rc.items(),
                                               key=lambda t: -t[1])}}

    # absent coarse nodes: where?
    S = set(map(tuple, np.round(layer(0.16), 12)))
    A = np.array(sorted(coarse - S))
    da = np.sqrt(((A[:, None, :] - C[None, :, :]) ** 2).sum(-1)).min(1)
    out["absent_coarse"] = {
        "n": len(A),
        "within_0.03_of_axis": int((da < 0.03).sum()),
        "within_0.05": int((da < 0.05).sum()),
        "rho_min_max": [float(da.min()), float(da.max())],
        "sample": sorted(set(map(tuple, np.round(A[:20], 6).tolist())))}

    print(json.dumps(out, indent=1, default=float)[:6000])
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j1c_refine2.json"), "w",
                        encoding="utf-8"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
