# -*- coding: utf-8 -*-
"""P18b: HDM prototype v2 (base-size rule + curved-surface projection)
vs oracle node positions — coincidence stats per job."""
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match


def analyze(job):
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    oracle, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    print("job", job, "oracle nodes", n, flush=True)
    t0 = time.time()
    boxes, verts, params, st = build(jdir, max_levels=2, surface_extra=1,
                                     use_object_sizes=False,
                                     max_cells=400000, cyl_cap=4)
    verts = np.unique(np.round(verts, 12), axis=0)
    print("  built leaves=%d nodes=%d in %.1fs (grid_size=%s)"
          % (len(boxes), len(verts), time.time() - t0,
             (st.get("grid_size_x"), st.get("grid_size_y"),
              st.get("grid_size_z"))), flush=True)
    m = position_match(verts, oracle)
    print("  oracle->our dist [min/med/mean/max]: %.3g %.3g %.3g %.3g"
          % tuple(m["oracle_to_our"]), flush=True)
    print("  oracle matched: 1e-6 %.3f%%  1e-4 %.3f%%  1e-3 %.3f%%"
          % (m["oracle_matched_1e-6"] * 100, m["oracle_matched_1e-4"] * 100,
             m["oracle_matched_1e-3"] * 100), flush=True)
    # distinct-per-axis comparison (octree fragmentation signature)
    for ax, name in enumerate(("x", "y", "z")):
        ours = len(np.unique(np.round(verts[:, ax], 12)))
        o = len(np.unique(np.round(oracle[:, ax], 12)))
        print("  axis %s: distinct ours=%d oracle=%d" % (name, ours, o),
              flush=True)
    return {"job": job, "leaves": len(boxes), "nodes": len(verts),
            "oracle_nodes": n, "match": m,
            "grid_size": (st.get("grid_size_x"), st.get("grid_size_y"),
                          st.get("grid_size_z"))}


def main(argv):
    jobs = argv[1:] or ["8-2yyhh", "10-1transient"]
    out = {}
    for j in jobs:
        try:
            out[j] = analyze(j)
        except Exception as e:
            print(j, "FAIL", repr(e), flush=True)
    import json
    pout = os.path.join(ROOT, "tools", "probe_work", "hdm_report.json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False, default=str)
    print("saved", pout)


if __name__ == "__main__":
    main(sys.argv)
