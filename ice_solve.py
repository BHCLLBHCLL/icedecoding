# -*- coding: utf-8 -*-
"""
P6: Solve settings forms (problem var editor), run-solution panel,
synthetic residual/model (monitor), patch temperatures.
Keys verified against oracle D:/training/icepak/*/problem files.
"""
import math
import os
import re

BASIC_FIELDS = [
    ("problem_time", "Analysis", "combo", ["steady", "transient"]),
    ("problem_nsteps", "Time steps", "int", 20),
    ("problem_stepincr", "Step size (s)", "text", 1.0),
    ("problem_integrator", "Integrator", "combo", ["first", "second"]),
    ("problem_tempvar", "Solve temperature", "check", 1),
    ("problem_turbulent", "Turbulent", "check", 0),
    ("problem_turbmodel", "Turbulence model", "combo",
     ["two", "ke", "komega"]),
    ("problem_gravity", "Gravity", "check", 1),
    ("problem_gravx", "Gravity X", "spin", 0.0),
    ("problem_gravy", "Gravity Y", "spin", -9.8),
    ("problem_gravz", "Gravity Z", "spin", 0.0),
    ("problem_temp", "Ambient temp (C)", "text", 20),
    ("problem_pressure", "Gauge pressure", "text", 0),
    ("problem_opressure", "Operating pressure (Pa)", "text", 101325),
    ("problem_odensity", "Operating density (kg/m3)", "text", 1.225),
    ("problem_init_t", "Initial temp", "text", 20),
    ("problem_init_x", "Initial vx (m/s)", "text", 0),
    ("problem_init_y", "Initial vy (m/s)", "text", 0.001),
    ("problem_init_z", "Initial vz (m/s)", "text", 0),
]

ADVANCED_FIELDS = [
    ("problem_ptol", "Pressure tolerance", "text", 1e-6),
    ("problem_radthreshhold", "Radiation threshold", "text", 0.05),
    ("problem_turb_prandtl", "Turbulent Prandtl", "text", 0.9),
    ("problem_ideal_gas", "Ideal gas", "check", 0),
    ("problem_charvel", "Characteristic velocity", "text", 0),
    ("problem_charlen", "Characteristic length", "text", 0),
    ("problem_saveinter", "Save intermediate", "check", 1),
    ("problem_temp_trans", "Temperature transient", "check", 0),
    ("problem_temp_units", "Temp units", "combo", ["C", "K", "F"]),
    ("problem_pressure_units", "Pressure units", "combo",
     ["N/m2", "Pa", "psi"]),
    ("problem_varstep", "Variable step", "text", 0.001),
    ("problem_increments", "Increments", "combo", ["fixed", "adapt"]),
]

PARALLEL_FIELDS = [
    ("solve_parallel_interconnect", "Interconnect", "combo",
     ["default", "tcp", "ib"]),
    ("solve_parallel_mpi", "MPI", "combo", ["default", "msmpi", "cray"]),
    ("solve_parallel_processes", "Processes", "int", 1),
    ("solve_parallel_cpus", "CPUs", "int", 1),
]

# P19-4: Patch temperatures / trials / Krylov ROM field tables
# (keys from oracle problem files: solve_do_trials / solve_trial_*,
#  ss_krylov / krylov_* verified in D:/training/icepak/*/problem)
PATCH_FIELDS = [
    ("patch_object", "Object name", "text", ""),
    ("patch_temp", "Temperature (C)", "spin", 80.0),
    ("patch_apply_to", "Apply to", "combo", ["object", "assembly", "group"]),
]

TRIALS_FIELDS = [
    ("solve_do_trials", "Run trials", "check", 0),
    ("solve_trial_prefix", "Trial prefix", "text", "trial"),
    ("solve_trial_fixed_prefix", "Fixed prefix", "check", 1),
    ("solve_do_fast_trials", "Fast trials", "check", 0),
]

ROM_FIELDS = [
    ("ss_krylov", "Krylov ROM", "check", 0),
    ("krylov_input_objects", "Input objects", "text", ""),
    ("krylov_cons_order", "Construction order", "int", 3),
    ("krylov_eval_order", "Evaluation order", "int", 3),
    ("krylov_heat_flux", "Heat flux", "check", 0),
    ("krylov_eval_times", "Evaluation times", "text", 0.0),
    ("krylov_trans_id", "Transient ID", "text", "transient00"),
]

SOLVE_FIELDS = {  # solution-id block
    "solve_id": "Solution ID",
    "solve_startmon": "Start monitor",
    "solve_when": "When",
    "solve_where": "Where",
    "solve_lsf": "Use LSF",
    "solve_jobtype": "Job type",
    "solve_savesteady": "Save steady every",
}


def read_setters(problem, key, default):
    if problem is None:
        return default
    sv = getattr(problem, "setters", None) or {}
    return sv.get(key, default)


def write_setter(problem, key, value):
    sv = getattr(problem, "setters", None)
    if sv is None:
        sv = {}
        problem.setters = sv
    sv[key] = value


# --------------------------------------------------------------------------- #
# Synthetic solution model (monitor / post displays without a solver)
# --------------------------------------------------------------------------- #

def simulate_residuals(n_iter=100, seed=0.0, scale=1.0):
    """Decaying residual curves: [(iter, [r_cont, r_vel, r_tke, r_temp])]."""
    out = []
    base = 10.0 ** (1.0 + seed)
    for i in range(1, n_iter + 1):
        decay = math.exp(-i / (n_iter / 4.5))
        r = [base * decay * (1.0 + 0.15 * math.sin(i * 0.7 + k))
             for k in range(4)]
        out.append((i, [max(v * scale, 1e-16) for v in r]))
    return out


def read_resd(path):
    """Read text residual file 'iter r1 r2 r3 r4'; None if absent/binary."""
    if not path or not os.path.exists(path):
        return None
    rows = []
    pat = re.compile(r'^\s*(\d+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)'
                     r'\s+([-\d.eE+]+)\s+([-\d.eE+]+)')
    with open(path, encoding="latin-1", errors="ignore") as fh:
        head = fh.read(32)
        if "\x00" in head:
            return None
        fh.seek(0)
        for line in fh:
            m = pat.match(line)
            if m:
                rows.append((int(m.group(1)),
                             [float(m.group(i)) for i in range(2, 6)]))
    return rows or None


def write_resd(path, resid_id, rows):
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("# Icepak residual %s (synthetic solver monitor)\n" % resid_id)
        for it, vals in rows:
            fh.write("%d %s\n" % (it, " ".join("%.10g" % v for v in vals)))


def simulate_history(mon_pt, iters=20, start=20.0, target=80.0):
    """Exponential approach history for a monitor point."""
    rows = []
    for i in range(iters + 1):
        v = start + (target - start) * (1.0 - math.exp(-i / (iters / 3.0)))
        rows.append((i, v))
    return rows


# --------------------------------------------------------------------------- #
# Post-processing object specs (Icepak post_create objsurface|planecut|...)
# --------------------------------------------------------------------------- #

POST_SPECS = {
    "Object face (node)": [("variable", "Variable", "combo", ["Temperature", "Pressure", "Velocity"]),
                            ("object", "Object", "text", "*")],
    "Object face (facet)": [("variable", "Variable", "combo", ["Temperature", "Pressure", "Velocity"]),
                             ("object", "Object", "text", "*")],
    "Plane cut": [("variable", "Variable", "combo", ["Temperature", "Pressure", "Velocity"]),
                   ("axis", "Axis", "combo", ["x", "y", "z"]),
                   ("offset", "Offset", "spin", 0.0)],
    "Isosurface": [("variable", "Variable", "combo", ["Temperature", "Pressure"]),
                    ("value", "Value", "spin", 50.0)],
    "Point": [("x", "X", "spin", 0.1), ("y", "Y", "spin", 0.1),
              ("z", "Z", "spin", 0.1),
              ("variable", "Variable", "combo", ["Temperature"])],
    "Surface probe": [("object", "Object", "text", "*"),
                       ("face", "Face", "combo", ["top", "bottom", "side"]),
                       ("variable", "Variable", "combo", ["Temperature"])],
    "Min/max locations": [("variable", "Variable", "combo", ["Temperature", "Pressure"])],
}# --------------------------------------------------------------------------- #
# Sample field / post data generators (mesh + object synthetic temperatures)
# --------------------------------------------------------------------------- #

DEFAULT_OBJ_TEMPS = {
    "block": 80.0, "source": 95.0, "package": 85.0, "heatsink": 60.0,
    "pcb": 70.0, "fan": 30.0, "wall": 25.0, "material": 40.0,
    "assembly": 65.0, "network": 50.0, "resistance": 45.0,
}


def obj_temperature(obj, default_scale=1.0):
    kind = getattr(obj, "kind", "block")
    sv = getattr(obj, "setvals", None) or {}
    for k in ("temp", "temperature", "power"):
        if k in sv:
            try:
                return float(sv[k])
            except (TypeError, ValueError):
                pass
    return DEFAULT_OBJ_TEMPS.get(kind, 50.0) * default_scale


def synthetic_cell_temps(result, temps_by_name):
    """Map cell -> temperature from per-object temperatures."""
    out = {}
    for (i, j, k), name in result.cell_obj.items():
        out[(i, j, k)] = temps_by_name.get(name, 20.0)
    return out


def plane_cut_points(result, axis, offset, temps):
    """Cell centers on the plane axis==offset; returns [(x,y,z,T)] sorted."""
    pts = []
    a = result.axes
    ai = {"x": 0, "y": 1, "z": 2}[axis]
    col = a[ai]
    tol = min((col[i + 1] - col[i]) for i in range(len(col) - 1)) / 2.0 * 1.2
    for (i, j, k), t in temps.items():
        c = [(a[0][i] + a[0][i + 1]) / 2,
             (a[1][j] + a[1][j + 1]) / 2,
             (a[2][k] + a[2][k + 1]) / 2]
        if abs(c[ai] - offset) <= tol:
            pts.append((c[0], c[1], c[2], t))
            if len(pts) > 4000:
                break
    pts.sort(key=lambda p: (p[(ai + 1) % 3], p[(ai + 2) % 3]))
    return pts


def iso_points(result, value, temps, tolerance=None):
    pts = []
    for (i, j, k), t in temps.items():
        if abs(t - value) < (tolerance or max(1.0, value * 0.05)):
            a = result.axes
            c = [(a[0][i] + a[0][i + 1]) / 2,
                 (a[1][j] + a[1][j + 1]) / 2,
                 (a[2][k] + a[2][k + 1]) / 2]
            pts.append((c[0], c[1], c[2], t))
    return pts


def sample_along(result, p0, p1, temps, n=41):
    """Variation plot data along a line; returns [(t, value)]."""
    pts = []

    def cell_t(x, y, z):
        a = result.axes
        idx = []
        for d in range(3):
            c = a[d]
            for k in range(len(c) - 1):
                if c[k] <= (x, y, z)[d] <= c[k + 1]:
                    idx.append(k)
                    break
        if len(idx) < 3:
            return None
        return temps.get(tuple(idx))

    for s in range(n):
        f = s / (n - 1)
        x = p0[0] + (p1[0] - p0[0]) * f
        y = p0[1] + (p1[1] - p0[1]) * f
        z = p0[2] + (p1[2] - p0[2]) * f
        t = cell_t(x, y, z)
        pts.append((f, t if t is not None else 20.0))
    return pts


def trials_from_problem(problem):
    """List trial entries from problem setters (parameters and trials)."""
    out = []
    if problem is None:
        return out
    sv = getattr(problem, "setters", None) or {}
    for key in sorted(sv):
        if key.startswith("param_") or key.startswith("problem_par"):
            out.append((key, sv[key]))
    return out
