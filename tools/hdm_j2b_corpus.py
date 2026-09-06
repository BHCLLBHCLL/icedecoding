# -*- coding: utf-8 -*-
"""J2b-2: locate cone/cylinder jobs across the corpus and build the
z-structure / tail-constant cross-check table."""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = os.path.join("D:", os.sep, "training", "icepak")
TAIL = 0.000985281374239
JOBS = ["10-1transient", "11-1compact-package", "11-2BGA-package",
        "11-3joule-heating", "12-1datacenter", "12-2avonics",
        "12-3TEC Tutorial", "5-1fin", "5-2rf_amp", "7-1hsink-rad",
        "7-2Heat-pipe", "8-1cold-plate", "8-2yyhh", "9-1FAN_Location",
        "9-2Optimization", "9-3Loss_coefficient"]


def find_dir(job):
    jd = os.path.join(BASE, job)
    if os.path.isdir(jd):
        return jd
    for sub in ("compack-package", os.listdir(BASE)):
        p = os.path.join(BASE, job, sub)
        if os.path.isdir(p) and os.path.exists(os.path.join(p,
                                                            "grid_params")):
            return p
    return jd


def cyls_of(jd):
    try:
        from icepak_parser.project import IcepakProject
        from ice_hdm import model_cylinders
        return model_cylinders(IcepakProject(jd).model)
    except Exception:
        return None


def z_struct(jd):
    """Return (n_levels, n_nodes, tail_members) or None."""
    from tools.grid_positions import find_node_section, _be
    go = os.path.join(jd, "grid_output")
    if not os.path.exists(go):
        return None
    nm = [f for f in os.listdir(jd) if f.endswith(".nodemap")]
    if not nm:
        return None
    data = open(go, "rb").read()
    sec = find_node_section(data)
    if sec is None:
        return None
    off, k, nh = sec
    pts = np.array([_be(data, off + i * 28 + 4, ">ddd")
                    for i in range(k)])
    u = np.unique(np.round(pts, 12), axis=0)
    zc = Counter(np.round(u[:, 2], 9).tolist())
    tail = sum(1 for zz in zc
               if abs((zz - 0.0025 * round(zz / 0.0025)) - TAIL) < 1e-9
               or abs((zz - 0.0025 * round(zz / 0.0025)) + TAIL) < 1e-9)
    return {"levels": len(zc), "nodes": len(u), "tail": tail,
            "hist_top": [[c, int(n)] for n, c in
                         Counter(zc.values()).most_common(5)]}


def main():
    out = {}
    for job in JOBS:
        jd = find_dir(job)
        cy = cyls_of(jd)
        zs = z_struct(jd)
        ncy = len(cy) if cy is not None else -1
        cone = sum(1 for c in (cy or [])
                   if float(c["r1"]) != float(c["r2"]))
        if zs is None:
            out[job] = {"dir": jd, "cyls": ncy, "cones": cone,
                        "z": None}
            continue
        out[job] = {"dir": jd, "cyls": ncy, "cones": cone,
                    "z": {k: v for k, v in zs.items()
                          if k != "hist_top"},
                    "hist": zs["hist_top"]}
        print("%-22s cyl=%-4d cone=%-3d levels=%-4d nodes=%-7d tail=%d  hist=%s"
              % (job, ncy, cone, zs["levels"], zs["nodes"], zs["tail"],
                 zs["hist_top"][:3]))
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j2b_corpus.json"), "w",
                        encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
