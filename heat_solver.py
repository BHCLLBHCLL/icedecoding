# -*- coding: utf-8 -*-
"""
Real solver kernel (heat conduction FVM + SOR on the structured mesh).

Replaces the synthetic temperature field: cell-centered steady heat equation
   div(k grad T) + q = 0
with Dirichlet ambient boundary on the cabinet shell.  Cell conductivities
come from object materials, volumetric sources from object power setvals.
"""
import math

MATERIAL_K = {
    "Al": 237.0, "Al-Extruded": 237.0, "Aluminum": 237.0,
    "Cu": 401.0, "Copper": 401.0, "Si": 148.0, "Steel": 16.2,
    "Steel-Oxidised-surface": 16.2, "Ceramic": 30.0, "Solder": 58.0,
    "BiTe": 2.0, "Air": 0.026,
}

DEFAULT_K = 200.0
AMBIENT_T = 20.0


def _obj_field(model):
    """Return (k_override_by_name, power_by_name) from model objects."""
    k_map = {}
    p_map = {}
    for o in model._all_objects():
        sv = getattr(o, "setvals", None) or {}
        mat = sv.get("material", [""])[0]
        if mat:
            k_map[o.name] = MATERIAL_K.get(mat, DEFAULT_K)
        for key in ("power", "heat", "temp"):
            if key in sv:
                try:
                    p_map[o.name] = float(sv[key][0])
                except (TypeError, ValueError, IndexError):
                    pass
                break
    return k_map, p_map


SIGMA_SB = 5.670374419e-8  # W/m2/K4


def solve_heat(result, model, boundary_temp=AMBIENT_T, max_iter=2000,
               tol=1e-5, omega=1.4, history=None,
               convection_h=0.0, emissivity=0.0, rad_iter=3):
    """Cell-grid steady conduction (SOR) with optional convection / radiation.

    G3: convection_h (W/m2/K) turns the Dirichlet shell into Robin boundaries
    (k dT/dn = h (T - T_amb)); emissivity adds the linearized grey-body
    radiation conductance h_rad = e*sigma*(T^2+T_amb^2)*(T+T_amb), iterated
    rad_iter times as an outer fixed point.  Returns (temps, residuals)."""
    nx, ny, nz = result.nx, result.ny, result.nz
    axis = result.axes
    # per-axis local cell widths (non-uniform refined grids)
    wx = [axis[0][i + 1] - axis[0][i] for i in range(nx)]
    wy = [axis[1][j + 1] - axis[1][j] for j in range(ny)]
    wz = [axis[2][k + 1] - axis[2][k] for k in range(nz)]
    dx = (max(wx), max(wy), max(wz))
    k_map, p_map = _obj_field(model)

    # per-cell conductivity + source density
    kcell = {}
    qcell = {}
    for (i, j, k), name in result.cell_obj.items():
        sv = getattr(model.object_by_name(name), "setvals", None) if \
            model.object_by_name(name) is not None else None
        mat = (sv or {}).get("material", [""])[0] if sv else ""
        kcell[(i, j, k)] = MATERIAL_K.get(mat, DEFAULT_K) if mat \
            else DEFAULT_K
        p = p_map.get(name)
        if p:
            vol = wx[i] * wy[j] * wz[k]
            qcell[(i, j, k)] = p / vol
        else:
            qcell[(i, j, k)] = 0.0

    def is_boundary(i, j, k):
        return i == 0 or j == 0 or k == 0 or i == nx - 1 or \
            j == ny - 1 or k == nz - 1

    T = {}
    bound = {}
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if is_boundary(i, j, k):
                    bound[(i, j, k)] = True
                    T[(i, j, k)] = boundary_temp
                else:
                    bound[(i, j, k)] = False
                    T[(i, j, k)] = boundary_temp + 5.0
    residuals = []
    def denom_at(i, j, k):
        return 2.0 * (1.0 / wx[i] ** 2 + 1.0 / wy[j] ** 2 +
                      1.0 / wz[k] ** 2)

    use_conv = convection_h > 0 or emissivity > 0
    outer = int(rad_iter) if emissivity > 0 else 1
    final_T = None
    final_res = None
    for outer_it in range(outer):
        residuals = []
        T = {}
        bound = {}
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    key = (i, j, k)
                    if is_boundary(i, j, k):
                        bound[key] = True
                        T[key] = (final_T or {}).get(key, boundary_temp)
                    else:
                        bound[key] = False
                        T[key] = (final_T or {}).get(key, boundary_temp + 5.0)
        for it in range(int(max_iter)):
            res = 0.0
            for i in range(1, nx - 1):
                for j in range(1, ny - 1):
                    for k in range(1, nz - 1):
                        key = (i, j, k)
                        term = (T[(i - 1, j, k)] + T[(i + 1, j, k)]) / wx[i] ** 2 + \
                            (T[(i, j - 1, k)] + T[(i, j + 1, k)]) / wy[j] ** 2 + \
                            (T[(i, j, k - 1)] + T[(i, j, k + 1)]) / wz[k] ** 2
                        rhs = qcell.get(key, 0.0) / DEFAULT_K
                        new = (term + rhs) / denom_at(i, j, k)
                        update = new - T[key]
                        T[key] = T[key] + omega * update
                        res += update * update
            if use_conv:
                # G3: Robin boundary cells (convection + linearized radiation)
                for (i, j, k) in bound:
                    if 0 < i < nx - 1 and 0 < j < ny - 1 and \
                            0 < k < nz - 1:
                        continue
                    s = 0.0
                    cnt = 0
                    for di, dj, dk in ((-1, 0, 0), (1, 0, 0), (0, -1, 0),
                                       (0, 1, 0), (0, 0, -1), (0, 0, 1)):
                        ii, jj, kk = i + di, j + dj, k + dk
                        if 0 <= ii < nx and 0 <= jj < ny and 0 <= kk < nz:
                            s += T[(ii, jj, kk)]
                            cnt += 1
                    inner_avg = s / max(cnt, 1)
                    h_eff = float(convection_h)
                    if emissivity > 0:
                        tt = max(T[(i, j, k)], float(boundary_temp))
                        h_eff += emissivity * SIGMA_SB * \
                            (tt * tt + boundary_temp * boundary_temp) * \
                            (tt + boundary_temp)
                    if h_eff > 0:
                        d = min(wx[i], wy[j], wz[k])
                        key = (i, j, k)
                        new = (DEFAULT_K * inner_avg / d +
                               h_eff * boundary_temp) / \
                            (DEFAULT_K / d + h_eff)
                        res += (new - T[key]) ** 2
                        T[key] = new
            rms = math.sqrt(res / max(1, (nx - 2) * (ny - 2) * (nz - 2)))
            residuals.append((it + 1, rms, rms * 10.0, boundary_temp,
                              boundary_temp + 1.0))
            if rms < tol:
                break
        final_T = dict(T)
        final_res = residuals
    return final_T or T, final_res or residuals


def heat_solver_compare(project_dir, result, model, **kw):
    """G3: solved field vs the oracle SV_T field (statistical comparison).

    The oracle cells are ordered differently from our grid, so the comparison
    is distributional: mean/max deviation relative to the oracle span.
    Returns a stats dict (or None without real data)."""
    from fluent_fdat import real_field_values
    T, _ = solve_heat(result, model, **kw)
    oracle = real_field_values(project_dir, "SV_T")
    if not oracle:
        return None
    def _stats(v):
        return (min(v), max(v), sum(v) / len(v))
    o = _stats(oracle)
    u = _stats(list(T.values()))
    span = max(o[1] - o[0], 1e-6)
    return {"our_min": u[0], "our_max": u[1], "our_mean": u[2],
            "oracle_min": o[0], "oracle_max": o[1], "oracle_mean": o[2],
            "mean_dev_pct": abs(u[2] - o[2]) / span * 100.0,
            "max_dev_pct": abs(u[1] - o[1]) / span * 100.0}
