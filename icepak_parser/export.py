# -*- coding: utf-8 -*-
"""
类型化数据模型 与 JSON/CSV 导出 (阶段2).

将解析好的项目聚合成可序列化的字典/记录:
    object_records(model)   -> 每条对象扁平化为带几何信息的 dict
    geometry_of(shape)      -> 按 shape 类型提取 bbox/center/radius 等几何量
    to_dict(project)        -> 完整项目结构(可 json.dumps)
    to_json / objects_csv / problem_csv / grid_csv / export_all
"""

from __future__ import annotations

import csv
import io
import json


# ---------------------------------------------------------------- 数值工具

def to_float(v):
    """字符串 -> float; 失败返回 None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def f3(vals):
    """取至多3个点坐标 float; 不足补 None."""
    n3 = [None, None, None]
    for i in range(3):
        if i < len(vals):
            n3[i] = to_float(vals[i])
    return n3


def _bbox(**kw):
    """由 point1/point2 计算 geometry."""
    p1 = f3(kw.get("point1") or [])
    p2 = f3(kw.get("point2") or [])
    _ok = lambda a: all(x is not None for x in a)
    if _ok(p1) and _ok(p2):
        center = [round((a + b) / 2.0, 12) for a, b in zip(p1, p2)]
        size = [round(abs(b - a), 12) for a, b in zip(p1, p2)]
        return {"bbox_min": p1, "bbox_max": p2, "center": center, "size": size}
    return {}


_KEY_ORDER = ("point1", "point2", "point3", "center", "center2", "pos",
              "radius", "iradius", "height", "angle1", "angle2")


def geometry_of(shape, props=None):
    """按 shape.type 提取常用几何量. 返回 dict(空则无)."""
    if shape is None:
        return {}
    sv = shape.setvals or {}
    t = shape.type or ""
    g = {}
    pts = {}
    for k in _KEY_ORDER:
        if k in sv:
            pts[k] = f3(sv[k]) or to_float(sv[k][0] if sv[k] else "")
    if t == "shape_hexa":
        g = _bbox(point1=pts.get("point1"), point2=pts.get("point2"))
    elif t in ("shape_quad", "shape_plate"):
        g = _bbox(point1=pts.get("point1"), point2=pts.get("point2"))
        if pts.get("point2"):
            pass
    elif t == "shape_cyl":
        center = pts.get("center")
        center2 = pts.get("center2")
        if center:
            g["center"] = center
        if center2:
            g["center2"] = center2
        if "radius" in pts and isinstance(pts["radius"], (int, float)):
            g["radius"] = pts["radius"]
        if "iradius" in pts and isinstance(pts["iradius"], (int, float)):
            g["iradius"] = pts["iradius"]
        if "height" in pts and isinstance(pts["height"], (int, float)):
            g["height"] = pts["height"]
    elif t in ("shape_polygon", "shape_poly"):
        g["note"] = "polygon: 详见 setvals"
    else:
        g = dict(pts)
    return g


def _num_props(properties):
    """尝试把标量属性数值化, 失败保留原字符串."""
    out = {}
    for k, v in properties.items():
        if len(v) == 1 and v[0] != "":
            f = to_float(v[0])
            out[k] = f if f is not None else v[0]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------- 扁平记录

def object_records(model):
    """每个对象(含嵌套) -> 扁平 dict(kind,name,path,depth,shape,geometry,properties)."""
    records = []
    if model is None:
        return records
    def walk(nodes, depth, prefix):
        for o in nodes:
            path = ".".join(p for p in (prefix + [o.name]) if p)
            records.append({
                "kind": o.kind,
                "name": o.name,
                "path": path,
                "depth": depth,
                "creation_order": _first_int(o.properties.get("creation_order")),
                "shape_type": o.shape.type if o.shape else None,
                "geometry": geometry_of(o.shape),
                "properties": _num_props(o.properties),
                "setvals": o.shape.setvals if o.shape else {},
                "children": len(o.children),
            })
            if o.children:
                walk(o.children, depth + 1, prefix + [o.name])
    walk(model.objects, 0, [])
    return records


def _first_int(v):
    try:
        return int(float(v[0]))
    except (TypeError, ValueError, IndexError):
        return None


# ---------------------------------------------------------------- 结构导出

def to_dict(project):
    """把 IcepakProject 转成可序列化 dict."""
    model = None
    if project.model is not None:
        model = {
            "header": project.model.header,
            "objects": object_records(project.model),
        }
    problem = None
    if project.problem is not None:
        problem = {
            "setters": project.problem.setters,
            "arrays": project.problem.arrays,
        }
    return {
        "name": project.name,
        "path": getattr(project, "path", None),
        "summary": project.summary(),
        "model": model,
        "problem": problem,
        "xml": project.xml,
        "grid": project.grid,
        "materials_lines": len(project.materials) if project.materials else 0,
        "post": project.post,
    }


def to_json(project, path=None, indent=2) -> str:
    """序列化项目为 JSON 字符串; path 给出则写入文件."""
    text = json.dumps(to_dict(project), ensure_ascii=False, indent=indent, default=str)
    if path:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


# ---------------------------------------------------------------- CSV 导出

def _write_csv(path, header, rows) -> str:
    if path:
        with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    else:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        return buf.getvalue()


def objects_csv(project, path=None) -> str:
    """对象清单 CSV: kind,name,creation_order,shape_type,center,size,properties摘要."""
    rows = []
    for rec in object_records(project.model):
        g = rec["geometry"]
        props = {k: v for k, v in rec["properties"].items()
                 if k in ("block_type", "plate_type", "temp", "grid_priority")}
        rows.append([
            rec["kind"], rec["name"], rec["creation_order"], rec["shape_type"],
            g.get("center"), g.get("size"),
            " ".join("%s=%s" % (k, v) for k, v in props.items()),
        ])
    return _write_csv(path, ["kind", "name", "creation_order", "shape_type",
                             "center", "size", "props"], rows)


def problem_csv(project, path=None) -> str:
    """problem 设置 CSV: name,value (setters) 以 problem_ 前缀为主."""
    rows = [[k, v] for k, v in (project.problem.setters.items() if project.problem else [])]
    return _write_csv(path, ["name", "value"], rows)


def grid_csv(project, path=None, prefix="") -> str:
    """grid_params CSV: 行+字段索引."""
    rows = [[i] + row for i, row in enumerate(project.grid)]
    return _write_csv(path, ["row"] + ["c%d" % i for i in range(
        max((len(r) for r in project.grid), default=0))], rows)


def export_all(project, outdir, name=None) -> dict:
    """导出到目录. 返回生成文件路径 dict."""
    import os
    os.makedirs(outdir, exist_ok=True)
    stem = (name or project.name or "project").replace(" ", "_").replace("/", "_")
    json_path = os.path.join(outdir, stem + ".json")
    obj_csv = os.path.join(outdir, stem + "_objects.csv")
    prb_csv = os.path.join(outdir, stem + "_problem.csv")
    grd_csv = os.path.join(outdir, stem + "_grid.csv")
    to_json(project, json_path)
    objects_csv(project, obj_csv)
    problem_csv(project, prb_csv)
    grid_csv(project, grd_csv)
    return {"json": json_path, "objects": obj_csv,
            "problem": prb_csv, "grid": grd_csv}


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from .project import IcepakProject
    p = sys.argv[1] if len(sys.argv) > 1 else r"D:\training\icepak\10-1transient"
    proj = IcepakProject(p)
    d = to_dict(proj)
    print("exported dict: %d objects, %d setters" % (
        len(d["model"]["objects"] if d["model"] else []),
        len(d["problem"]["setters"] if d["problem"] else [])))
    print(json.dumps(proj.summary(), ensure_ascii=False, default=str))