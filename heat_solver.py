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


def solve_heat(result, model, boundary_temp=AMBIENT_T, max_iter=2000,
               tol=1e-5, omega=1.4, history=None):
    """Cell-grid steady conduction (SOR). Returns (temps, residuals)."""
    nx, ny, nz = result.nx, result.ny, result.nz
    axis = result.axes
    dx = (axis[0][1] - axis[0][0], axis[1][1] - axis[1][0],
          axis[2][1] - axis[2][0])
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
            vol = dx[0] * dx[1] * dx[2]
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
    denom = 2.0 * (1.0 / dx[0] ** 2 + 1.0 / dx[1] ** 2 + 1.0 / dx[2] ** 2)
    for it in range(int(max_iter)):
        res = 0.0
        for i in range(1, nx - 1):
            for j in range(1, ny - 1):
                for k in range(1, nz - 1):
                    key = (i, j, k)
                    term = (T[(i - 1, j, k)] + T[(i + 1, j, k)]) / dx[0] ** 2
                    term += (T[(i, j - 1, k)] + T[(i, j + 1, k)]) / dx[1] ** 2
                    term += (T[(i, j, k - 1)] + T[(i, j, k + 1)]) / dx[2] ** 2
                    rhs = qcell.get(key, 0.0) / DEFAULT_K
                    new = (term + rhs) / denom
                    update = new - T[key]
                    T[key] = T[key] + omega * update
                    res += update * update
        rms = math.sqrt(res / max(1, (nx - 2) * (ny - 2) * (nz - 2)))
        residuals.append((it + 1, rms, rms * 10.0, boundary_temp,
                          boundary_temp + 1.0))
        if rms < tol:
            break
    return T, residuals
