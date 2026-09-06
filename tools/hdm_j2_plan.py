# -*- coding: utf-8 -*-
"""J2 plan: layer-stack taxonomy — per-level type assignment + the
law-coverage of the 150 z-levels.

Type by node count (proven J1a/J1c classes):
  coarse 1710, main 3212, mid 1470, special (1932/1665), artifact 1,
  cluster = everything else.
Verifies: main z-set == graded chain of the cylinder span (law),
coarse z-set == chain(0.05,0.12) + above-band (partially open),
cluster layer counts distribution, and node-coverage per class.
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm_layers import graded_chain

OUT = os.path.join(ROOT, "tools", "probe_work", "j2_plan.json")


def main():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    cnt = Counter(z.tolist())
    levels = sorted(cnt.items())

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

    typ = {zz: classify(c) for zz, c in levels}
    classes = Counter(typ.values())
    node_by_class = Counter()
    for zz, c in levels:
        node_by_class[typ[zz]] += c

    # law checks
    main_z = sorted(zz for zz, c in levels if typ[zz] == "main")
    span = graded_chain(0.13, 0.19, 5e-3, 2.0, 2e-2)
    span_full = np.sort(np.append(span, [0.13, 0.19]))
    main_exact = bool(np.allclose(main_z, span_full, atol=1e-12))

    coarse_zz = sorted(zz for zz, c in levels if typ[zz] == "coarse")
    below = graded_chain(0.05, 0.12, 5e-3, 2.0, 2e-2)
    below_full = np.sort(np.append(below, [0.05, 0.12]))
    below_ok = [zz for zz in coarse_zz if zz <= 0.12 + 1e-12]
    above = [zz for zz in coarse_zz if zz > 0.19 + 1e-9]
    above_exact_matches = {}
    ca = np.array(above)
    cand1 = np.sort(np.append(graded_chain(0.19, 0.25, 5e-3, 2.0, 2e-2),
                              [0.19, 0.25]))
    above_exact_matches["chain_0.19_0.25"] = bool(
        len(cand1) == len(ca) and np.allclose(cand1, ca, atol=1e-12))
    cand2 = np.sort(np.append(graded_chain(0.205985281374239, 0.25,
                                           5e-3, 2.0, 2e-2),
                              [0.205985281374239, 0.25]))
    above_exact_matches["shifted_anchor_0.205985"] = bool(
        len(cand2) == len(ca) and np.allclose(cand2, ca, atol=1e-12))

    cluster_zz = [zz for zz, c in levels if typ[zz] == "cluster"]
    cluster_below = [zz for zz in cluster_zz if zz < 0.13]
    cluster_above = [zz for zz in cluster_zz if zz > 0.19]
    special_zz = [zz for zz, c in levels if typ[zz] == "special"]

    rec = {
        "n_levels": len(levels), "sum_nodes": sum(cnt.values()),
        "classes": dict(classes), "nodes_per_class": dict(node_by_class),
        "main_z_law_exact": main_exact,
        "main_z": [float(v) for v in main_z],
        "coarse_below_law_ok": bool(len(below_ok) == len(below_full)
                                    and np.allclose(
                                        np.sort(below_ok), below_full,
                                        atol=1e-12)),
        "coarse_above": [float(v) for v in above],
        "above_law_tests": above_exact_matches,
        "cluster_n_below": len(cluster_below),
        "cluster_n_above": len(cluster_above),
        "cluster_z_below": [float(zz) for zz in cluster_below],
        "cluster_z_above": [float(zz) for zz in cluster_above],
        "special_z": [float(zz) for zz in special_zz],
        "mid_z": [float(zz) for zz, c in levels if typ[zz] == "mid"],
        "artifact_z": [float(zz) for zz, c in levels
                       if typ[zz] == "artifact"],
    }
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    slim = {k: v for k, v in rec.items()
            if k not in ("cluster_z_below", "cluster_z_above")}
    print(json.dumps(slim, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
