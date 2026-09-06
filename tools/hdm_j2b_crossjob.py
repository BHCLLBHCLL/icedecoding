# -*- coding: utf-8 -*-
"""J2b probe: transition-band z structure — cross-job universality +
exact-value attribution on 10-1.

(A) For each meshed job: extract z-layer structure (unique z, per-level
    node count) and test the 10-1 tail constant 0.000985281374239
    presence (z - 0.01*round(z/0.01) == tail).
(B) On 10-1: cluster z's vs exact combination families
    (1-cos(theta_k)) * R  for R in {0.012, 0.0148, 0.016, 0.02} and
    theta_k in the 24-angle star, plus r(z)-self-consistent forms.
"""
import json
import math
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = os.path.join("D:", os.sep, "training", "icepak")
TAIL = 0.000985281374239


def z_structure(job):
    from tools.grid_positions import extract_nodes
    jd = os.path.join(BASE, job)
    nm = [f for f in os.listdir(jd) if f.endswith(".nodemap")]
    if not nm:
        return None
    raw = open(os.path.join(jd, nm[0]), "rb").read()
    n = raw.count(bytes([10]))
    if not raw.endswith(bytes([10])):
        n += 1
    r = extract_nodes(os.path.join(jd, "grid_output"), n)
    nodes = r[0] if r and r[0] is not None else np.zeros((0, 3))
    z = np.round(nodes[:, 2], 9)
    cnt = Counter(z.tolist())
    levels = sorted(cnt.items())
    # tail test on non-lattice z's (z not close to 0.02*k forms except
    # coarse): detect any z with z mod 0.0025 == TAIL or 0.0025-TAIL
    tails = [zz for zz, c in levels
             if abs((zz - 0.0025 * round(zz / 0.0025)) - TAIL) < 1e-9
             or abs((zz - 0.0025 * round(zz / 0.0025)) + TAIL) < 1e-9]
    return {"layers": len(levels), "nodes": len(nodes), "tail_members":
            len(tails), "tail_sample": tails[:4],
            "hist_top": [[c, int(n)] for n, c in
                         Counter([c for _, c in levels]).most_common(8)]}


def main():
    jobs = ["10-1transient", "8-2yyhh", "7-1hsink-rad", "5-1fin",
            "11-2BGA-package", "9-3Loss_coefficient"]
    rec = {}
    for j in jobs:
        try:
            rec[j] = z_structure(j)
        except Exception as e:
            rec[j] = {"error": repr(e)[:120]}
    out = {"cross_job": rec}
    print(json.dumps(out, indent=1)[:3500])

    # (B) exact family test on 10-1 cluster z's
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    cnt = Counter(z.tolist())
    cluster = [zz for zz, c in cnt.items() if 20 < c < 600]
    cl = np.array(sorted(cluster))
    pairs = [(1.0, 0.0), (0.952976, 0.303046), (0.819961, 0.57242),
             (0.707107, 0.707107), (0.57242, 0.819961),
             (0.303046, 0.952976)]
    R = [0.012, 0.0148, 0.016, 0.02, 0.016491569, 0.018]
    hits = []
    for px, py in pairs:
        for r in R:
            d = math.sqrt(px * px + py * py)
            c0 = px / d
            # theta from pair, 1-cos and sin
            for kind, val in (("1-cos", 1 - c0), ("sin", py / d)):
                for z0, sgn in ((0.13, -1), (0.19, +1)):
                    cand = np.unique(np.round(z0 + sgn * r * val, 12))
                    h = int(sum(1 for v in cand
                                if any(abs(v - c) < 1e-9 for c in cl)))
                    if h > 0:
                        hits.append([h, len(cand), round(r, 6), kind,
                                     round(math.degrees(
                                         math.acos(c0)), 4), z0])
    hits.sort(key=lambda t: -t[0])
    out["family_hits"] = hits[:10]
    print("family_hits:", hits[:10])
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j2b_crossjob.json"), "w",
                        encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
