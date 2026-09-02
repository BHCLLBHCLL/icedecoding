# -*- coding: utf-8 -*-
"""
P7: Icepak Macros — three-level registration (type/subtype/macro) mirroring
add_macro_commands() (macro_definition / macro_subtype / macro_subsubtype),
directory scanner (system/user/project layers), parameterized built-in macros
(digest is encrypted upstream, so macros ship as .macro.json descriptors and
Python builders; Icepak .tcl macro names from icepak_lib/macros are still
listed for parity).
"""
import json
import os
import re

MACRO_SUFFIX = ".macro.json"

# --------------------------------------------------------------------------- #
# Built-in macro registry (parameterized, cab_parts-style)
# --------------------------------------------------------------------------- #

BUILTIN_MACROS = {
    "angled_fin": {
        "name": "Angled fin heat sink",
        "subtype": "Heat sinks",
        "subsubtype": "Extruded",
        "params": [
            ("width", "Width (m)", "spin", 0.1),
            ("depth", "Depth (m)", "spin", 0.1),
            ("height", "Height (m)", "spin", 0.05),
            ("base_thickness", "Base thickness (m)", "spin", 0.005),
            ("fin_gap", "Fin gap (m)", "spin", 0.004),
            ("fin_thickness", "Fin thickness (m)", "spin", 0.001),
            ("fin_count", "Fin count", "int", 8),
        ],
        "builder": "build_heat_sink",
    },
    "bga": {
        "name": "BGA package",
        "subtype": "Packages",
        "subsubtype": "Ball grid array",
        "params": [
            ("body_size", "Body size (m)", "spin", 0.027),
            ("body_thickness", "Body thickness (m)", "spin", 0.0012),
            ("die_size", "Die size (m)", "spin", 0.006),
            ("ball_count", "Balls per row", "int", 8),
            ("ball_pitch", "Ball pitch (m)", "spin", 0.0012),
        ],
        "builder": "build_bga",
    },
    "tec": {
        "name": "Thermoelectric cooler (TEC)",
        "subtype": "Components",
        "subsubtype": "TEC",
        "params": [
            ("width", "Width (m)", "spin", 0.04),
            ("depth", "Depth (m)", "spin", 0.04),
            ("thickness", "Thickness (m)", "spin", 0.004),
            ("pellets", "Pellet pairs", "int", 5),
            ("power", "Power (W)", "text", 12.0),
        ],
        "builder": "build_tec",
    },
    "sot": {
        "name": "SOIC/SOT package",
        "subtype": "Packages",
        "subsubtype": "Small outline",
        "params": [
            ("body_size", "Body size (m)", "spin", 0.006),
            ("body_thickness", "Body thickness (m)", "spin", 0.0014),
            ("die_size", "Die size (m)", "spin", 0.003),
            ("lead_count", "Lead count per side", "int", 4),
        ],
        "builder": "build_sot",
    },
    "blower": {
        "name": "Centrifugal blower",
        "subtype": "Fans",
        "subsubtype": "Centrifugal",
        "params": [
            ("diameter", "Diameter (m)", "spin", 0.08),
            ("depth", "Depth (m)", "spin", 0.06),
            ("power", "Power (W)", "text", 8.0),
            ("flow", "Flow (m3/s)", "text", 0.03),
        ],
        "builder": "build_blower",
    },
}


def scan_macro_dir(path):
    """Scan one directory for *.macro.json descriptors."""
    out = []
    if not path or not os.path.isdir(path):
        return out
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(MACRO_SUFFIX):
            continue
        fp = os.path.join(path, fn)
        try:
            with open(fp, encoding="utf-8") as fh:
                data = json.load(fh)
            data.setdefault("name", fn.split(".")[0])
            data.setdefault("subtype", "General")
            data.setdefault("subsubtype", "General")
            data.setdefault("params", [])
            data.setdefault("builder", "build_heat_sink")
            data["_file"] = fp
            out.append(data)
        except (OSError, ValueError):
            continue
    return out


def scan_macros(system_dir=None, user_dir=None, project_dir=None):
    """Merge the three layers (project > user > system)."""
    order = [system_dir, user_dir, project_dir]
    merged = {}
    for d in order:
        for m in scan_macro_dir(d):
            merged[m["name"]] = m
    return merged


def avail_macros_system_names(system_dir):
    """List Icepak .tcl macro folder names (encrypted upstream) for parity."""
    names = []
    if not system_dir:
        return names
    try:
        for fn in os.listdir(system_dir):
            if fn.endswith(".tcl") or os.path.isdir(os.path.join(system_dir,
                                                                 fn)):
                names.append(fn)
    except OSError:
        pass
    return names


def default_project_macro_dir(root):
    if not root:
        return None
    return os.path.join(root, "macros")


def default_user_macro_dir():
    home = os.path.expanduser("~")
    return os.path.join(home, "icepak_lib", "macros")
# --------------------------------------------------------------------------- #
# Parameterized built-in builders (create ModelObjects in the model)
# --------------------------------------------------------------------------- #

def _obj(model, kind, name, lo, hi, props=None, objname=None):
    from ice_create import default_object
    idx = model.count_all()
    o = default_object(kind, objname or name, index=idx, creation_order=idx + 1)
    o.name = name
    o.shape.setvals["point1"] = [str(v) for v in lo]
    o.shape.setvals["point2"] = [str(v) for v in hi]
    for k, v in (props or {}).items():
        sv = getattr(o, "setvals", None) or {}
        sv[k] = [str(v)]
        o.setvals = sv
    model.objects.append(o)
    return o


def _name(model, prefix):
    n = 1
    while True:
        cand = "%s.%d" % (prefix, n)
        if model.object_by_name(cand) is None:
            return cand
        n += 1


def build_macro(model, key, params):
    """Dispatcher: params dict -> list of created ModelObjects."""
    spec = BUILTIN_MACROS.get(key)
    if spec is None:
        return []
    fn = globals().get(spec["builder"])
    if fn is None:
        return []
    return fn(model, params) or []


def build_heat_sink(model, p):
    """Angled-fin heatsink: base + fins."""
    out = []
    w = float(p.get("width", 0.1))
    d = float(p.get("depth", 0.1))
    h = float(p.get("height", 0.05))
    bt = float(p.get("base_thickness", 0.005))
    gap = float(p.get("fin_gap", 0.004))
    ft = float(p.get("fin_thickness", 0.001))
    cnt = int(p.get("fin_count", 8))
    nm = _name(model, "hs_angled")
    out.append(_obj(model, "block", "%s.base" % nm, (0, 0, 0), (w, d, bt),
                    {"block_type": "solid", "material": "Al-Extruded"}))
    total = cnt * ft + (cnt + 1) * gap
    scale = min(1.0, w / total) if total > 0 else 1.0
    x = (w - total * scale) / 2.0
    for i in range(cnt):
        x0 = x + i * (ft + gap) * scale
        f = _obj(model, "block", "%s.fin%d" % (nm, i + 1),
                 (x0, 0, bt), (x0 + ft * scale, d, bt + h),
                 {"block_type": "solid", "material": "Al-Extruded"})
        out.append(f)
    return out


def build_bga(model, p):
    body = float(p.get("body_size", 0.027))
    bt = float(p.get("body_thickness", 0.0012))
    die = float(p.get("die_size", 0.006))
    n = int(p.get("ball_count", 8))
    pitch = float(p.get("ball_pitch", 0.0012))
    nm = _name(model, "bga_pkg")
    out = [_obj(model, "package", "%s.body" % nm, (0, 0, 0), (body, body, bt),
                {"package_type": "bga", "rjc": "10", "rjb": "20"})]
    dm = (body - die) / 2.0
    out.append(_obj(model, "block", "%s.die" % nm,
                    (dm, dm, bt), (dm + die, dm + die, bt + 0.0003),
                    {"block_type": "solid", "material": "Si"}))
    span = (n - 1) * pitch
    s0 = (body - span) / 2.0
    for i in range(n):
        for j in range(n):
            x = s0 + i * pitch
            y = s0 + j * pitch
            r = pitch * 0.4
            b = _obj(model, "block", "%s.ball%d_%d" % (nm, i + 1, j + 1),
                     (x - r, y - r, -r - 0.0002), (x + r, y + r, 0.0002),
                     {"block_type": "solid", "material": "Solder"})
            out.append(b)
    return out


def build_tec(model, p):
    w = float(p.get("width", 0.04))
    d = float(p.get("depth", 0.04))
    th = float(p.get("thickness", 0.004))
    power = float(p.get("power", 12.0))
    pellets = int(p.get("pellets", 5))
    nm = _name(model, "tec")
    out = [_obj(model, "block", "%s.cold" % nm, (0, 0, 0), (w, d, th * 0.25),
                {"block_type": "solid", "material": "Ceramic"})]
    out.append(_obj(model, "block", "%s.hot" % nm, (0, 0, th * 0.75),
                    (w, d, th), {"block_type": "solid",
                                 "material": "Ceramic"}))
    step = w / pellets
    for i in range(pellets):
        x = i * step
        hot = (i % 2) == 0
        pl = _obj(model, "block", "%s.pel%d" % (nm, i + 1),
                  (x - step * 0.25, 0, th * 0.25),
                  (x + step * 0.25, d, th * 0.75),
                  {"block_type": "solid", "material": "BiTe",
                   "temp": 45.0 if hot else 25.0,
                   "power": power / pellets})
        out.append(pl)
    return out


def build_sot(model, p):
    body = float(p.get("body_size", 0.006))
    bt = float(p.get("body_thickness", 0.0014))
    die = float(p.get("die_size", 0.003))
    leads = int(p.get("lead_count", 4))
    nm = _name(model, "sot_pkg")
    out = [_obj(model, "package", "%s.body" % nm, (0, 0, 0), (body, body, bt),
                {"package_type": "sot", "rjc": "25", "rjb": "60"})]
    dm = (body - die) / 2.0
    out.append(_obj(model, "block", "%s.die" % nm,
                    (dm, dm, bt), (dm + die, dm + die, bt + 0.0003),
                    {"block_type": "solid", "material": "Si"}))
    lead = body * 0.25
    for i in range(leads):
        y = body * (i + 0.5) / leads
        for side in (0, 1):
            x0 = -lead if side == 0 else body
            _obj(model, "block", "%s.lead%d_%d" % (nm, i + 1, side + 1),
                 (x0, y - 0.0002, bt * 0.25),
                 (x0 + lead, y + 0.0002, bt * 0.5),
                 {"block_type": "solid", "material": "Cu"})
    return out


def build_blower(model, p):
    dia = float(p.get("diameter", 0.08))
    depth = float(p.get("depth", 0.06))
    nm = _name(model, "blower")
    o = default_object("blower", nm, index=model.count_all(),
                       creation_order=model.count_all() + 1)
    o.shape.setvals["point1"] = ["0", "0", "0"]
    o.shape.setvals["point2"] = [str(dia), str(depth), str(depth)]
    sv = o.setvals or {}
    sv["blower_type"] = ["centrifugal"]
    sv["power"] = [str(float(p.get("power", 8.0)))]
    sv["flow"] = [str(float(p.get("flow", 0.03)))]
    o.setvals = sv
    model.objects.append(o)
    return [o]

# ---- Phase D2: full macro-library port (libraries/*/pitch/rows/* params) ----
import os as _os
def default_macro_library():
    for base in (r'C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\icepak_lib\macros\libraries',
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icepak_lib', 'macros', 'libraries')):
        if _os.path.isdir(base): return base
    return None
def parse_macro_params(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or '#' in line[:1]: continue
        line = line.replace(chr(9), ' ')
        parts = line.split(None, 1)
        if len(parts) == 2:
            k, v = parts[0], parts[1].strip()
            try: v = float(v)
            except ValueError: pass
            out[k] = v
    return out
def scan_macro_library(root=None):
    root = root or default_macro_library()
    if not root: return []
    out = []
    for lib in sorted(_os.listdir(root)):
        libd = _os.path.join(root, lib)
        if not _os.path.isdir(libd): continue
        for pitch in sorted(_os.listdir(libd)):
            pd = _os.path.join(libd, pitch)
            if not _os.path.isdir(pd): continue
            for rows in sorted(_os.listdir(pd)):
                rd = _os.path.join(pd, rows)
                if not _os.path.isdir(rd): continue
                for fn in sorted(_os.listdir(rd)):
                    fp = _os.path.join(rd, fn)
                    if not _os.path.isfile(fp): continue
                    try:
                        params = parse_macro_params(open(fp, encoding='latin-1', errors='replace').read())
                    except Exception: params = {}
                    out.append({'library': lib, 'pitch': pitch, 'rows': rows, 'name': fn, 'params': params, 'path': fp})
    return out
def build_library_part(model, macro):
    """Create a package part from a macro-lib parameter set (BGA/QFP)."""
    from ice_create import default_object
    from ice_ecad import _ensure_shape
    p = macro.get('params', {})
    n1 = int(p.get('ball_num1', 8)); n2 = int(p.get('ball_num2', 8))
    bp = float(p.get('ball_pitch', 1.0)) * 0.001
    dd = float(p.get('die_dim1', 3.0)) * 0.001
    t = float(p.get('package_thickness', 2.0)) * 0.001
    name = (macro.get('name') or 'part')[:40]
    base = (0.0, 0.0, 0.0)
    obj = default_object('package', name)
    _ensure_shape(obj, base, (n2*bp, n1*bp, t))
    if getattr(obj, 'setvals', None) is None: obj.setvals = {}
    obj.setvals['package_type'] = ['bga' if 'BGA' in name.upper() or 'bga' in str(macro.get('library','')).lower() else 'qfp']
    obj.setvals['ball_pitch'] = [str(p.get('ball_pitch', ''))]
    obj.setvals['ball_num1'] = [str(p.get('ball_num1', ''))]
    obj.setvals['ball_num2'] = [str(p.get('ball_num2', ''))]
    obj.setvals['die_dim1'] = [str(p.get('die_dim1', ''))]
    obj.setvals['die_dim2'] = [str(p.get('die_dim2', ''))]
    obj.setvals['library'] = [str(macro.get('library', ''))]
    model.objects.append(obj)
    return obj