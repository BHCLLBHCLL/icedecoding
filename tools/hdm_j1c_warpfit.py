# -*- coding: utf-8 -*-
"""J1c last cut: warp-field dataset + closed-form kernel fitting.

The warp field W(u,v) moves skeleton lines near a cylinder (fixed,
layer-independent — j1c_warp showed identical values at z=0.13/0.16/0.19).
Dataset: for cylinder (0.15,0.25) at z=0.13, every skeleton row y0 and
column x0 carries a warped position (x')/(y') where the skeleton line
was displaced.  Fit hypotheses on the radial component drho = rho'-rho:
  H1 drho = A/rho ; H2 drho = A/rho^2 ; H3 drho = A*exp(-rho/lambda)
  H4 drho = A*(R/rho)^p ; H5 drho = A*(1/r)^n form
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scipy.optimize import curve_fit

CY = (0.15, 0.25)
R_MID = 0.016
OUT = os.path.join(ROOT, "tools", "probe_work", "j1c_warpfull.json")
OUTF = os.path.join(ROOT, "tools", "probe_work", "j1c_warpfit.json")


def main():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    layer = lambda zz: nodes[np.abs(z - zz) < 1e-9][:, :2]
    scale = set(map(tuple, np.round(layer(0.25), 12)))
    S = set(map(tuple, np.round(layer(0.13), 12)))
    skel_x = [v for v in sorted(set(p[0] for p in scale))]
    skel_y = [v for v in sorted(set(p[1] for p in scale))]

    cx, cy = CY
    INFL = 0.052
    rows = []   # (y0, x0, x')  x-warp on skeleton row y0
    cols = []   # (x0, y0, y')  y-warp on skeleton column x0
    for y0 in skel_y:
        if abs(y0 - cy) > INFL:
            continue
        pts = sorted((p[0] for p in S if abs(p[1] - y0) < 1e-12))
        for x0 in skel_x:
            if abs(x0 - cx) > INFL:
                continue
            if (x0, y0) in S:
                continue
            # warped image of this skeleton line on this row: nearest
            # non-skeleton x to x0 (only if this row actually carries it)
            near = [x for x in pts if min(abs(x - s) for s in skel_x) > 1e-9]
            if not near:
                continue
            n = min(near, key=lambda x: abs(x - x0))
            if abs(n - x0) < 0.004:
                rows.append((y0, x0, n))
    for x0 in skel_x:
        if abs(x0 - cx) > INFL:
            continue
        pts = sorted((p[1] for p in S if abs(p[0] - x0) < 1e-12))
        for y0 in skel_y:
            if abs(y0 - cy) > INFL:
                continue
            if (x0, y0) in S:
                continue
            near = [y for y in pts if min(abs(y - s) for s in skel_y) > 1e-9]
            if not near:
                continue
            n = min(near, key=lambda y: abs(y - y0))
            if abs(n - y0) < 0.004:
                cols.append((x0, y0, n))

    # radial data (magnitude of displacement, treated as radial)
    data = []
    for y0, x0, xp in rows:
        u, v = x0 - cx, y0 - cy
        rho0 = np.hypot(u, v)
        rho1 = np.hypot(xp - cx, v)
        data.append((rho0, rho1 - rho0, (x0, y0), (xp, y0)))
    for x0, y0, yp in cols:
        u, v = x0 - cx, y0 - cy
        rho0 = np.hypot(u, v)
        rho1 = np.hypot(u, yp - cy)
        data.append((rho0, rho1 - rho0, (x0, y0), (x0, yp)))
    rho = np.array([d[0] for d in data])
    dr = np.array([d[1] for d in data])

    # filter: only points with positive outward warp (the signature)
    m = dr > 0
    rho_p, dr_p = rho[m], dr[m]

    fits = {}
    for name, fn in (
            ("H1 A/rho", lambda r, A: A / r),
            ("H2 A/rho^2", lambda r, A: A / r ** 2),
            ("H4 A*(R/rho)^p", lambda r, A, p: A * (R_MID / r) ** p)):
        try:
            p0 = [dr_p[0] * rho_p[0]] if name != "H4 A*(R/rho)^p" else [1e-5, 2]
            popt, _ = curve_fit(fn, rho_p, dr_p, p0=p0, maxfev=8000)
            res = dr_p - fn(rho_p, *popt)
            fits[name] = {"params": [float(v) for v in popt],
                          "rms": float(np.sqrt((res ** 2).mean())),
                          "max": float(np.abs(res).max())}
        except Exception as e:
            fits[name] = {"error": repr(e)}
    # H3 exponential: grid search lambda
    best = None
    for lam in np.logspace(-4, -1, 60):
        A = (dr_p / np.exp(-rho_p / lam)).mean() if len(rho_p) else 0
        res = dr_p - A * np.exp(-rho_p / lam)
        rms = float(np.sqrt((res ** 2).mean()))
        if best is None or rms < best[0]:
            best = (rms, float(lam), float(A))
    fits["H3 A*exp(-rho/lam)"] = {"params": [best[2], best[1]],
                                  "rms": best[0]}

    rec = {
        "n_rows_warp": len(rows), "n_cols_warp": len(cols),
        "n_data": len(data), "n_positive": int(m.sum()),
        "fits": fits,
        "samples_x": [[round(a, 9), round(b, 9), round(c, 9)]
                      for a, b, c in rows[:40]],
        "samples_y": [[round(a, 9), round(b, 9), round(c, 9)]
                      for a, b, c in cols[:40]],
    }
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    json.dump({"n_data": len(data), "fits": fits}, open(OUTF, "w"),
              indent=1)
    print(json.dumps({"n_rows": len(rows), "n_cols": len(cols),
                      "n_data": len(data), "fits": fits}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
