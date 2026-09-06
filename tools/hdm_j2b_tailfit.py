# -*- coding: utf-8 -*-
"""J2b-3: tail-family law verification + last closed-form test on TAIL.

For each cone/cylinder job: every tail member (mod H2 == +-TAIL) is
catalogued as (z_ref, m, exact) under the law
    z_tail = z_ref + m*H2 + TAIL          (H2 = 0.0025)
with z_ref = cylinder base/top z-planes from the model.
Closes with a negative-evidence record of the TAIL closed-form test
(versine/sin families x job-native constants).
"""
import json
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.grid_positions import find_node_section, _be

BASE = os.path.join("D:", os.sep, "training", "icepak")
TAIL = 0.000985281374239
H2 = 0.0025
JOBS = ["10-1transient", "8-1cold-plate", "7-2Heat-pipe"]


def z_levels(jd):
    data = open(os.path.join(jd, "grid_output"), "rb").read()
    off, k, nh = find_node_section(data)
    pts = np.array([_be(data, off + i * 28 + 4, ">ddd")
                    for i in range(k)])
    u = np.unique(np.round(pts, 12), axis=0)
    return Counter(np.round(u[:, 2], 12).tolist())


def cyl_planes(jd):
    from icepak_parser.project import IcepakProject
    from ice_hdm import model_cylinders
    cy = model_cylinders(IcepakProject(jd).model)
    planes = []
    for c in cy:
        planes.append(round(float(c["p1"][2]), 9))
        planes.append(round(float(c["p2"][2]), 9))
    return sorted(set(planes))


def main():
    out = {"tail": TAIL, "jobs": {}}
    for job in JOBS:
        jd = os.path.join(BASE, job)
        try:
            zc = z_levels(jd)
            planes = cyl_planes(jd)
        except Exception as e:
            out["jobs"][job] = {"error": repr(e)[:100]}
            continue
        members = [zz for zz in zc
                   if abs((zz - H2 * round(zz / H2)) - TAIL) < 1e-9
                   or abs((zz - H2 * round(zz / H2)) + TAIL) < 1e-9]
        cats = []
        for m in members:
            best = None
            for z0 in planes:
                for sgn in (+1, -1):
                    off = sgn * (m - z0)
                    k = round(off / H2)
                    err = abs(off - (k * H2 + TAIL))
                    if best is None or err < best[0]:
                        best = (round(err, 12), z0, k, sgn)
            cats.append({"z": m, "z_ref": best[1], "m": best[2],
                         "sgn": best[3], "err": best[0]})
        out["jobs"][job] = {"n_members": len(members),
                            "planes": planes[:12], "members": cats}
        print(job, "members", len(members))
        for c in sorted(cats, key=lambda t: t["z"]):
            print("   z=%.12f z_ref=%.4f m=%d sgn=%+d err=%.2e"
                  % (c["z"], c["z_ref"], c["m"], c["sgn"], c["err"]))

    # TAIL closed-form last test: versine/sin x job-native constants
    import math
    ring = [0.0, 17.641, 34.919, 45.0, 55.081, 72.359, 90.0, 9.84345]
    cons = [0.0025, 0.005, 0.0075, 0.01, 0.012, 0.015, 0.016, 0.02,
            0.03, 0.06, 0.09]
    cands = []
    for th in ring:
        for c in cons:
            for label, val in (
                    ("versine", (1 - math.cos(math.radians(th))) * c),
                    ("sin", math.sin(math.radians(th)) * c),
                    ("tan", math.tan(math.radians(th)) * c)):
                cands.append((abs(val - TAIL), th, c, label, val))
    cands.sort(key=lambda t: t[0])
    out["closed_form_closest"] = [
        {"err": round(e, 12), "theta": t, "c": c, "kind": k,
         "val": round(v, 12)} for e, t, c, k, v in cands[:6]]
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j2b_tailfit.json"), "w",
                        encoding="utf-8"), indent=1)
    print("closed-form closest:", out["closed_form_closest"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
