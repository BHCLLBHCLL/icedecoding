# -*- coding: utf-8 -*-
"""P18f: verify per-axis face-size targets on 10-1 (best config) and 8-2."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import build, position_match, parse_grid_params

for job, xy in (("10-1transient", (8190, 6777)), ("8-2yyhh", (28, 7))):
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    params = parse_grid_params(os.path.join(jdir, "grid_params"))
    faces = [r.get("face_sizes") for r in params]
    print(job, "face_sizes:", faces)
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    oracle, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    t0 = time.time()
    boxes, verts, params, st = build(
        jdir, max_levels=2, surface_extra=1, use_object_sizes=True,
        max_cells=500000, cyl_cap=8, shell_factor=0.3, curv_c=0.165,
        proj_tol=None)
    verts = np.unique(np.round(verts, 12), axis=0)
    m = position_match(verts, oracle)
    ax = {}
    for i, name in enumerate(("x", "y")):
        ax[name] = len(np.unique(np.round(verts[:, i], 12)))
    print("%s nodes=%d distinct x/y=%d/%d (oracle %d/%d) 1e-3=%.3f%%"
          % (job, len(verts), ax["x"], ax["y"], xy[0], xy[1],
             m["oracle_matched_1e-3"] * 100))
    print("  dx=%.1f%% dy=%.1f%% median=%.4f %.1fs" %
          ((ax["x"] - xy[0]) * 100.0 / xy[0],
           (ax["y"] - xy[1]) * 100.0 / xy[1],
           m["oracle_to_our"][1], time.time() - t0))
