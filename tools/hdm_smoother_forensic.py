# -*- coding: utf-8 -*-
"""Phase J1/J3 forensic: oracle node residuals against the closed-form
candidate plane family.

Candidate planes per axis = base grid (min(grid_size, L/gcount)) dyadic
refinement + every object interval refined at its requested size (with a
few halving levels) + domain hi.  Coordinates exactly on a candidate are
"un-smoothed"; the residual of the rest measures the final smoother.

Also: full inventory of the z axis (only ~150 distinct values) and a
cone-surface class check (projected nodes are exact on geometry).
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm import model_cylinders, parse_grid_params, problem_grid_settings

JOB = "10-1transient"
JDIR = os.path.join("D:", os.sep, "training", "icepak", JOB)
NL = bytes([10])
OUT = os.path.join(ROOT, "tools", "probe_work", "smoother_forensic.json")


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(NL)
    if not raw.endswith(NL):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return (r[0] if r and r[0] is not None else np.zeros((0, 3))), n


def sane(v, L):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v <= 0 or v >= L or v != v:
        return None
    return v


def candidate_planes(axis, params, dom_lo, dom_hi, base):
    """Closed-form candidate plane family for one axis."""
    lo0, hi = float(dom_lo[axis]), float(dom_hi[axis])
    planes = [lo0 + m * base for m in range(int(round((hi - lo0) / base)) + 2)]
    planes.append(hi)
    for r in params:
        if r["type"] == "domain":
            continue
        a, b = float(r["lo"][axis]), float(r["hi"][axis])
        if b <= a:
            continue
        s = sane(r["size"][axis], b - a) if len(r.get("size", [])) > axis \
            else None
        planes.extend([a, b])
        if s is None:
            continue
        for k in range(0, 5):
            step = s / float(2 ** k)
            m = 0
            while a + m * step <= b + 1e-15 and m < 4000:
                planes.append(a + m * step)
                m += 1
    return np.unique(np.round(np.array(planes), 15))


def axis_residual(vals, planes):
    """Nearest-candidate residual for every value."""
    idx = np.searchsorted(planes, vals)
    idx = np.clip(idx, 1, len(planes) - 1)
    left = planes[idx - 1]
    right = planes[idx]
    d = np.minimum(np.abs(vals - left), np.abs(vals - right))
    return d


def cone_mask(nodes, cyls):
    m = np.zeros(len(nodes), dtype=bool)
    for c in cyls:
        p1, p2 = c["p1"], c["p2"]
        u = p2 - p1
        h = float(np.linalg.norm(u))
        if h <= 0:
            continue
        u = u / h
        d = (nodes - p1) @ u
        w = nodes - p1 - d[:, None] * u
        rho = np.linalg.norm(w, axis=1)
        rt = c["r1"] + (c["r2"] - c["r1"]) * np.clip(d / h, 0.0, 1.0)
        m |= (np.abs(rho - rt) < 1e-7) & (d >= -1e-9) & (d <= h + 1e-9)
    return m


def main():
    nodes, ncount = load_oracle()
    params = parse_grid_params(os.path.join(JDIR, "grid_params"))
    dom = [r for r in params if r["type"] == "domain"][0]
    dom_lo = np.minimum(np.array(dom["lo"], float), 0.0)
    dom_hi = np.array(dom["hi"], float)
    st = problem_grid_settings(JDIR)
    span = dom_hi - dom_lo
    gcount = (st.get("grid_gcount_i", 10), st.get("grid_gcount_j", 10),
              st.get("grid_gcount_k", 10))
    base = []
    for i in range(3):
        g = sane(st.get("grid_size_" + "xyz"[i], 0.02), span[i])
        base.append(min(g, span[i] / gcount[i]) if g else span[i] / gcount[i])
    base = tuple(base)

    try:
        from icepak_parser.project import IcepakProject
        cyls = model_cylinders(IcepakProject(JDIR).model)
    except Exception:
        cyls = []
    surf = cone_mask(nodes, cyls) if cyls else \
        np.zeros(len(nodes), dtype=bool)

    res = {"job": JOB, "nodes": int(len(nodes)), "oracle_declared": ncount,
           "base_step": base, "cone_surface_nodes": int(surf.sum())}
    plane_sets = []
    per_axis = {}
    for ax, name in enumerate("xyz"):
        pl = candidate_planes(ax, params, dom_lo, dom_hi, base[ax])
        plane_sets.append(pl)
        vals = np.unique(np.round(nodes[:, ax], 15))
        d = axis_residual(vals, pl)
        per_axis[name] = {
            "distinct": int(len(vals)),
            "candidates": int(len(pl)),
            "exact_1e-12": float((d < 1e-12).mean()),
            "within_1e-9": float((d < 1e-9).mean()),
            "within_1e-6": float((d < 1e-6).mean()),
            "within_1e-4": float((d < 1e-4).mean()),
            "resid_median_off": float(np.median(d[d >= 1e-12])) if
                (d >= 1e-12).any() else 0.0,
            "resid_max": float(d.max()),
        }
    res["per_axis"] = per_axis

    # node-level smoothing cross-tab (vol nodes only, surface excluded)
    vol = ~surf
    nv = nodes[vol]
    exact = np.stack([axis_residual(nv[:, ax], plane_sets[ax]) < 1e-12
                      for ax in range(3)], axis=1)
    k = exact.sum(axis=1)
    res["vol_nodes"] = int(vol.sum())
    res["node_exact_axes_hist"] = {
        "3_axes": int((k == 3).sum()), "2_axes": int((k == 2).sum()),
        "1_axis": int((k == 1).sum()), "0_axes": int((k == 0).sum())}
    # displaced coordinates: residual vs local spacing ratio
    ratios = []
    for ax in range(3):
        d = axis_residual(nv[:, ax], plane_sets[ax])
        vals = nv[:, ax]
        idx = np.clip(np.searchsorted(plane_sets[ax], vals), 1,
                      len(plane_sets[ax]) - 1)
        spacing = (plane_sets[ax][idx] - plane_sets[ax][idx - 1])
        m = (d >= 1e-12) & (spacing > 0)
        if m.any():
            ratios.append((float(np.median(d[m] / spacing[m])),
                           float((d[m] / spacing[m]).max()),
                           int(m.sum())))
    res["displaced_ratio_median_max_n_per_axis"] = ratios

    # z-axis full inventory
    zv = np.unique(np.round(nodes[:, 2], 15))
    zpl = plane_sets[2]
    idx = np.clip(np.searchsorted(zpl, zv), 1, len(zpl) - 1)
    d = np.minimum(np.abs(zv - zpl[idx - 1]), np.abs(zv - zpl[idx]))
    zinv = []
    for v, dd in zip(zv, d):
        zinv.append({"z": float(v),
                     "on": bool(dd < 1e-12),
                     "near": float(zpl[int(np.argmin(np.abs(zpl - v)))]),
                     "resid": float(dd) if dd >= 1e-12 else 0.0})
    res["z_inventory"] = zinv
    res["z_explained_exact"] = int(sum(1 for e in zinv if e["on"]))

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    slim = {k: v for k, v in res.items() if k != "z_inventory"}
    slim["z_inventory_offplane"] = [e for e in zinv if not e["on"]]
    print(json.dumps(slim, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
