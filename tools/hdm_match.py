# -*- coding: utf-8 -*-
"""P18: run the HDM prototype vs oracle node positions for one job."""
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, leaf_vertices, position_match


def main(argv):
    job = argv[1] if len(argv) > 1 else "10-1transient"
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    # oracle positions (reuse extractor)
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    oracle, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    print("job", job, "oracle nodes", n, flush=True)
    for lv in (2,):
        t0 = time.time()
        boxes, verts, params, st = build(jdir, max_levels=lv,
                                           surface_extra=2,
                                           use_object_sizes=False)
        verts = np.unique(np.round(verts, 12), axis=0)
        print("  built lv=%d leaves=%d in %.1fs" % (lv, len(boxes),
                                                    time.time() - t0),
              flush=True)
        m = position_match(verts, oracle)
        print("levels=%d leaves=%d nodes=%d (oracle %d) elapsed %.1fs"
              % (lv, len(boxes), len(verts), n, time.time() - t0))
        print("   our->oracle dist [min/med/mean/max]: %.2g %.2g %.2g %.2g"
              % tuple(m["our_to_oracle"]))
        print("   oracle->our dist [min/med/mean/max]: %.2g %.2g %.2g %.2g"
              % tuple(m["oracle_to_our"]))
        print("   oracle matched: 1e-6 %.3f%%  1e-4 %.3f%%  1e-3 %.3f%%"
              % (m["oracle_matched_1e-6"] * 100, m["oracle_matched_1e-4"] * 100,
                 m["oracle_matched_1e-3"] * 100))


if __name__ == "__main__":
    main(sys.argv)
