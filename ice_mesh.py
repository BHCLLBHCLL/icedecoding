# -*- coding: utf-8 -*-
"""
P5: AutoHex (Complete Hex Mesher) — params spec from lib/autohex/params_auto.tcl,
six-tab dialog, structured mesh generation (uniform/geometric axes + occupancy),
job file writers (grid_params / ascii grid_output), oracle-probe helpers.
"""
import re

# --------------------------------------------------------------------------- #
# Parameter table (params_auto.tcl defaults; subagent-verified field names)
# --------------------------------------------------------------------------- #

PARAMS_DEFAULTS = {
    "grid_type": "hexa",
    "grid_usesize_x": 0, "grid_usesize_y": 0, "grid_usesize_z": 0,
    "grid_usesize_h": 0,
    "grid_size_x": 1.0, "grid_size_y": 1.0, "grid_size_z": 1.0,
    "grid_size_h": 0.0,
    "grid_max_elements": 25000000,
    "grid_gcount_i": 10, "grid_gcount_j": 10, "grid_gcount_k": 10,
    "grid_gtype": "unif",
    "grid_gmax_i": 0, "grid_gmax_j": 0, "grid_gmax_k": 0,
    "grid_gmin_i": 0, "grid_gmin_j": 0, "grid_gmin_k": 0,
    "grid_ratios": 0,
    "grid_sep_x": 0.001, "grid_sep_y": 0.001, "grid_sep_z": 0.001,
    "grid_gr_ratio": 1.0,
    "grid_settings_type": "normal",
    "min_elements_gap": 3,
    "min_elements_block": 2,
    "max_ratio": 2.0,
    "conformal_tol": 0.01,
    "cyl_shrink_factor": 0.99,
    "grid_tetra_settings_type": "normal",
    "n_cells_in_gap": 2,
    "natural_size_refinement": 32,
    "grid_hdm_feature_angle": 40,
    "grid_hdm_mlm_auto": "auto",
    "grid_hdm_mlm_auto_levels": 2,
    "grid_hdm_icechip": 1,
    "grid_run_smoother": 0,
    "limit_bad_angle": 35.0,
    "mth_local_sm": "Optimize",
    "grid_qual": "facealign",
    "bad_face_align": 0.05,
    "pipe_mesh_on": 0,
    "ogrid_height": 0.5,
    "edge_eps": 0.00015,
    "element_threshold": 0.9,
    "panel_block_face": 0,
    "check_scheme": 0,
    "part_mesh_option": 0,
    "grid_display_mesh_separately": 0,
}

MESHER_PRESETS = {
    "normal": dict(min_elements_gap=3, min_elements_block=2, max_ratio=2.0),
    "coarse": dict(min_elements_gap=2, min_elements_block=1, max_ratio=10.0),
    "null": dict(min_elements_gap=1, min_elements_block=1, max_ratio=10000.0),
}


def class_of_params_from_tcl(text):
    """Parse the 'set grid_...' lines (probe helper)."""
    out = {}
    for m in re.finditer(r'^set\s+([A-Za-z0-9_]+)\s+(.+?)\s*$', text, re.M):
        key, val = m.group(1), m.group(2).strip()
        if val.startswith('"'):
            val = val.strip('"')
        low = val.lower()
        if low in ("true", "on"):
            val = 1
        elif low in ("false", "off"):
            val = 0
        else:
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
        out[key] = val
    return out


# --------------------------------------------------------------------------- #
# Axis generation: uniform or geometric ratio spacing (stpre-style formula)
# --------------------------------------------------------------------------- #

def geometric_coords(L, n, q):
    """Coordinates 0..L with n intervals and growth ratio q.

    g0 = L*(1-q)/(1-q**n);  x_k = g0*(1-q**k)/(1-q).  q == 1 -> uniform.
    """
    if n < 1:
        return [0.0]
    if abs(q - 1.0) < 1e-12:
        return [L * k / n for k in range(n + 1)]
    g0 = L * (1.0 - q) / (1.0 - q ** n)
    coords = [0.0]
    x = 0.0
    for k in range(n):
        x += g0 * (q ** k)
        coords.append(x)
    coords[-1] = L
    return coords


def uniform_coords(L, n):
    return geometric_coords(L, n, 1.0)


def build_axes(lo, hi, counts, gtype="unif", ratio=1.0):
    axes = []
    for i in range(3):
        L = hi[i] - lo[i]
        n = max(1, int(counts[i]))
        q = ratio if (gtype == "geom" and abs(ratio - 1.0) > 1e-12) else 1.0
        axes.append([lo[i] + x for x in geometric_coords(L, n, q)])
    return axes


# --------------------------------------------------------------------------- #
# Occupancy classification / mesh result
# --------------------------------------------------------------------------- #

def classify_cells(axes, objects):
    """objects: (name, (lo,hi)) list; cell -> object name on center hit."""
    nx, ny, nz = len(axes[0]) - 1, len(axes[1]) - 1, len(axes[2]) - 1
    cell_obj = {}
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                # boundary shell is still classified (occupancy wins)
                cx = (axes[0][i] + axes[0][i + 1]) / 2.0
                cy = (axes[1][j] + axes[1][j + 1]) / 2.0
                cz = (axes[2][k] + axes[2][k + 1]) / 2.0
                for name, (lo, hi) in objects:
                    if lo[0] <= cx <= hi[0] and lo[1] <= cy <= hi[1] and \
                            lo[2] <= cz <= hi[2]:
                        cell_obj[(i, j, k)] = name
                        break
    return cell_obj


class MeshResult(object):
    def __init__(self, axes, cell_obj, domain=(0, 0, 0)):
        self.axes = axes
        self.cell_obj = cell_obj
        self.nx = len(axes[0]) - 1
        self.ny = len(axes[1]) - 1
        self.nz = len(axes[2]) - 1

    @property
    def cell_count(self):
        return self.nx * self.ny * self.nz

    @property
    def node_count(self):
        return (self.nx + 1) * (self.ny + 1) * (self.nz + 1)

    def counts_by_object(self):
        out = {}
        for o in self.cell_obj.values():
            out[o] = out.get(o, 0) + 1
        return out

    def structured_lines(self):
        """World-space line segments for VTK mesh display."""
        lines = []
        a = self.axes
        for i in range(self.nx + 1):
            for j in range(self.ny + 1):
                lines.append((a[0][i], a[1][j], a[2][0],
                              a[0][i], a[1][j], a[2][-1]))
        for j in range(self.ny + 1):
            for k in range(self.nz + 1):
                lines.append((a[0][0], a[1][j], a[2][k],
                              a[0][-1], a[1][j], a[2][k]))
        for k in range(self.nz + 1):
            for i in range(self.nx + 1):
                lines.append((a[0][i], a[1][0], a[2][k],
                              a[0][i], a[1][-1], a[2][k]))
        return lines

def _bounds_of(obj):
    sh = getattr(obj, "shape", None)
    if sh is None:
        return None
    p1 = sh.setvals.get("point1")
    p2 = sh.setvals.get("point2")
    if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple))):
        return None
    try:
        lo = tuple(float(x) for x in p1)
        hi = tuple(float(x) for x in p2)
    except (TypeError, ValueError):
        return None
    return lo, hi


def generate_mesh(model, domain_bounds=None, counts=None, gtype="unif",
                  ratio=1.0, objects=None):
    """Probe entry: build the structured mesh over the cabinet domain."""
    if domain_bounds is None:
        domains = [o for o in model._all_objects() if o.kind == "domain"]
        if not domains:
            raise ValueError("no cabinet/domain object")
        d = domains[0]
        domain_bounds = _bounds_of(d)
    lo, hi = domain_bounds
    if counts is None:
        size = tuple(hi[i] - lo[i] for i in range(3))
        base = PARAMS_DEFAULTS["grid_gcount_i"]
        counts = tuple(max(1, int(round(size[i] / max(size) * base)))
                       for i in range(3))
    axes = build_axes(lo, hi, counts, gtype, ratio)
    objs = objects
    if objs is None:
        objs = []
        for o in model._all_objects():
            if o.kind == "domain":
                continue
            b = _bounds_of(o)
            if b is not None:
                objs.append((o.name, b))
    cell_obj = classify_cells(axes, objs)
    return MeshResult(axes, cell_obj)


# --------------------------------------------------------------------------- #
# Job file writers (Icepak job naming: grid_params / grid_output)
# --------------------------------------------------------------------------- #

OBJ_TYPE_NAMES = {
    "domain": "domain", "block": "hexa", "plate": "quad", "fan": "cyl2",
    "blower": "cyl2", "source": "hexa", "opening": "quad", "wall": "quad",
    "grille": "quad", "ventres": "quad", "resistance": "hexa",
    "package": "hexa", "heatsink": "hexa", "pcb": "quad", "enclosure": "hexa",
    "network": "hexa", "assembly": "hexa", "periodic": "quad",
    "material": "hexa",
}


def write_grid_params(path, model, params=None):
    """Write Icepak-style grid_params (per-object mesh control lines)."""
    params = params or {}
    lines = []
    idx = 0
    for o in model._all_objects():
        b = _bounds_of(o)
        if b is None:
            continue
        lo, hi = b
        t = OBJ_TYPE_NAMES.get(o.kind, "hexa")
        size = tuple(hi[i] - lo[i] for i in range(3))
        base = int(params.get("grid_gcount_i", 10))
        dx = size[0] / base if base else size[0]
        dy = size[1] / base if base else size[1]
        dz = 1e37
        min_gap = params.get("min_elements_gap", 3)
        max_ratio = params.get("max_ratio", 2.0)
        line = "%s %d %.6g %.6g %.6g %.6g %.6g %.6g %.6g %.6g %.6g" \
               " %.6g %d %.6g %d %.6g %d" % (
                   t, idx, lo[0], lo[1], lo[2], hi[0], hi[1], hi[2],
                   dx, dy, dz, 0.005, min_gap, 0.005, min_gap, max_ratio, 1)
        lines.append(line)
        idx += 1
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("\n".join(lines) + "\n")
    return lines


def parse_grid_params(path):
    """Parse grid_params lines -> list of dicts (probe/golden helper)."""
    out = []
    pat = re.compile(
        r'^(\S+)\s+(\d+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)'
        r'\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)')
    with open(path, encoding="latin-1") as fh:
        for line in fh:
            m = pat.match(line.strip())
            if not m:
                continue
            vals = [float(m.group(i)) for i in range(3, 9)]
            out.append({"type": m.group(1), "id": int(m.group(2)),
                        "lo": tuple(vals[:3]), "hi": tuple(vals[3:])})
    return out


def write_grid_output_ascii(path, result):
    """Write a Fluent-style ASCII subset (header + nodes + hex cells)."""
    a = result.axes
    nx, ny, nz = result.nx, result.ny, result.nz
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("(10 (0 1 %x 0))\n" % result.node_count)  # hex like Icepak
        nid = 0
        for i in range(nx + 1):
            for j in range(ny + 1):
                for k in range(nz + 1):
                    nid += 1
                    fh.write("%d %.8g %.8g %.8g\n" %
                             (nid, a[0][i], a[1][j], a[2][k]))
        fh.write("(12 (0 1 %x 0))\n" % result.cell_count)  # hex like Icepak
        cid = 0
        d1 = (nz + 1)
        d2 = (ny + 1) * (nz + 1)
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    cid += 1
                    n0 = i * d2 + j * d1 + k + 1
                    fh.write("%d %d %d %d %d %d %d %d %d 1\n" % (
                        cid, n0, n0 + 1, n0 + d1 + 1, n0 + d1,
                        n0 + d2, n0 + d2 + 1, n0 + d2 + d1 + 1,
                        n0 + d2 + d1))
    return result


def mesh_quality(result):
    """G1: structured-mesh quality metrics (Icepak quality panel data).

    For a structured hexa grid the cells are axis-aligned: orthogonality is
    1.0 (perfect) and skewness 0; the meaningful metric is the aspect-ratio
    distribution (dx/dy/dz per cell).  Returns a dict.
    """
    import numpy as np
    a = result.axes
    dx = np.diff(a[0]) if len(a[0]) > 1 else np.array([1.0])
    dy = np.diff(a[1]) if len(a[1]) > 1 else np.array([1.0])
    dz = np.diff(a[2]) if len(a[2]) > 1 else np.array([1.0])
    dmax = np.maximum(np.maximum(dx[:, None, None], dy[None, :, None]),
                      dz[None, None, :])
    dmin = np.minimum(np.minimum(dx[:, None, None], dy[None, :, None]),
                      dz[None, None, :])
    aspect = dmax / np.maximum(dmin, 1e-300)
    vol = float((dx.sum() * dy.sum() * dz.sum()))
    worst = tuple(int(v) for v in
                  np.unravel_index(np.argmax(aspect), aspect.shape))
    return {
        "cells": int(result.cell_count),
        "nodes": int(result.node_count),
        "orthogonality": 1.0,
        "skewness": 0.0,
        "aspect_min": float(aspect.min()),
        "aspect_max": float(aspect.max()),
        "aspect_mean": float(aspect.mean()),
        "worst_cell": worst,
        "volume": vol,
    }
