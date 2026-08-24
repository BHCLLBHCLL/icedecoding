# -*- coding: utf-8 -*-
"""In-memory Icepak object factories (M2 create / New project)."""

from __future__ import annotations

import copy
import os

from icepak_parser.model_parser import ModelObject, Shape

HEXA_KINDS = {
    "domain", "block", "package", "pcb", "heatsink", "enclosure",
    "assembly", "heat_exchanger", "resistance",
}
QUAD_KINDS = {
    "plate", "opening", "wall", "source", "ventres", "periodic",
}
CYL_KINDS = {"fan", "blower"}
# material / network / profile: no tessellated body


def next_object_name(model, kind):
    names = set()
    if model is not None:
        names = {o.name for o in model._all_objects()}
    n = 1
    while True:
        cand = "%s.%d" % (kind, n)
        if cand not in names:
            return cand
        n += 1


def default_shape(kind, index=0):
    """Default primitive so a newly created object is visible in Graphics."""
    off = 0.02 * int(index)
    if kind in CYL_KINDS:
        z0, z1 = 0.0 + off, 0.03 + off
        return Shape(kind, "shape_cyl", {
            "center": ["%.6g" % (0.05 + off), "%.6g" % (0.05 + off), "%.6g" % z0],
            "center2": ["%.6g" % (0.05 + off), "%.6g" % (0.05 + off), "%.6g" % z1],
            "radius": ["0.015"],
            "iradius": ["0.005"],
        })
    if kind in QUAD_KINDS:
        return Shape(kind, "shape_quad", {
            "point1": ["%.6g" % off, "%.6g" % off, "%.6g" % off],
            "point2": ["%.6g" % (0.08 + off), "%.6g" % (0.06 + off), "%.6g" % off],
            "thickness": ["0.002"],
            "plane": ["2"],
        })
    if kind in HEXA_KINDS or kind not in ("material", "network", "profile"):
        dx = 0.5 if kind == "domain" else 0.05
        dy = 0.4 if kind == "domain" else 0.04
        dz = 0.3 if kind == "domain" else 0.03
        return Shape(kind, "shape_hexa", {
            "point1": ["%.6g" % off, "%.6g" % off, "%.6g" % off],
            "point2": ["%.6g" % (dx + off), "%.6g" % (dy + off), "%.6g" % (dz + off)],
        })
    return None


def default_object(kind, name=None, index=0, creation_order=1):
    name = name or "%s.%d" % (kind, max(1, index + 1))
    shape = default_shape(kind, index)
    props = {"creation_order": [str(creation_order)]}
    if kind == "block":
        props["block_type"] = ["solid"]
    elif kind == "plate":
        props["plate_type"] = ["solid"]
    return ModelObject(kind, name, props, shape)


def default_cabinet():
    return default_object("domain", "cabinet", index=0, creation_order=1)


def serialize_shape(shape, indent=1):
    sp = "    " * indent
    lines = ["%sshape %s %s" % (sp, shape.name, shape.type)]
    if shape.setvals:
        parts = []
        for k, v in shape.setvals.items():
            inner = " ".join(str(x) for x in v)
            parts.append("%s {%s}" % (k, inner))
        lines.append("%s    setval %s" % (sp, " ".join(parts)))
    lines.append("%send shape" % sp)
    return lines


def serialize_object(obj, indent=0):
    sp = "    " * indent
    lines = ["%sobject %s %s" % (sp, obj.kind, obj.name)]
    for k, v in (obj.properties or {}).items():
        if isinstance(v, (list, tuple)):
            val = " ".join(str(x) for x in v)
        else:
            val = str(v)
        lines.append("%s    %s %s" % (sp, k, val))
    if obj.shape is not None:
        lines.extend(serialize_shape(obj.shape, indent + 1))
    for ch in obj.children or []:
        lines.extend(serialize_object(ch, indent + 1))
    lines.append("%send object" % sp)
    return lines


def serialize_model(model):
    lines = ["#@ ice viewer model"]
    for o in getattr(model, "objects", []) or []:
        lines.extend(serialize_object(o))
    return "\n".join(lines) + "\n"


def project_files_for_pack(project):
    """Bytes map suitable for tzr.pack from a loaded or in-memory project."""
    files = dict(getattr(project, "files", None) or {})
    if files:
        return files
    path = getattr(project, "path", None)
    if path and os.path.isdir(str(path)):
        out = {}
        for fn in os.listdir(path):
            if fn.startswith("."):
                continue
            fp = os.path.join(path, fn)
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    out[fn] = f.read()
        return out
    model = getattr(project, "model", None)
    if model is not None:
        from icepak_parser.decoder import encode_text
        files["model"] = encode_text(serialize_model(model)).encode("latin-1")
    return files


def remove_object(model, name):
    """Remove named object from a ModelFile (including nested assemblies)."""
    if model is None:
        return False

    def drop(lst):
        for i, o in enumerate(lst):
            if o.name == name:
                lst.pop(i)
                return True
            if o.children and drop(o.children):
                return True
        return False

    return drop(model.objects)


def take_object(model, name):
    """Remove and return the named object, or None."""
    if model is None:
        return None

    def take(lst):
        for i, o in enumerate(lst):
            if o.name == name:
                return lst.pop(i)
            if o.children:
                hit = take(o.children)
                if hit is not None:
                    return hit
        return None

    return take(model.objects)


def clone_object(obj, new_name):
    clone = copy.deepcopy(obj)
    clone.name = new_name
    return clone


def _shift_xyz(vals, dx, dy, dz):
    nums = []
    for i, raw in enumerate(list(vals)[:3]):
        try:
            nums.append(float(raw))
        except (TypeError, ValueError):
            nums.append(0.0)
    while len(nums) < 3:
        nums.append(0.0)
    nums[0] += dx
    nums[1] += dy
    nums[2] += dz
    return ["%.6g" % v for v in nums]


def translate_shape(shape, dx, dy, dz):
    if shape is None or not shape.setvals:
        return
    for key in ("point1", "point2", "point3", "center", "center2", "pos",
                "position"):
        if key in shape.setvals and shape.setvals[key]:
            shape.setvals[key] = _shift_xyz(shape.setvals[key], dx, dy, dz)


def translate_object(obj, dx, dy, dz, recursive=True):
    if obj is None:
        return
    translate_shape(obj.shape, dx, dy, dz)
    if recursive:
        for ch in obj.children or []:
            translate_object(ch, dx, dy, dz, True)


def object_active(obj):
    props = getattr(obj, "properties", None) or {}
    if "active" in props and props["active"]:
        s = str(props["active"][0]).lower()
        return s not in ("0", "off", "false", "no")
    if "inactive" in props and props["inactive"]:
        s = str(props["inactive"][0]).lower()
        return s in ("0", "off", "false", "no")
    return True


def set_object_active(obj, on):
    if obj is None:
        return
    if obj.properties is None:
        obj.properties = {}
    obj.properties["active"] = ["1" if on else "0"]
