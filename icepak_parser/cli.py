# -*- coding: utf-8 -*-
"""
批量命令行工具 + 交叉验证 (阶段3).

用法:
    python -m icepak_parser.cli scan <root> [-o outdir] [--csv report.csv] [--json report.json]
    python -m icepak_parser.cli analyze <project_dir_or_tzr>

scan   递归扫描 root 下所有项目目录和 *.tzr 归档, 逐项目解析并汇总。
analyze 对单个项目打印结构化摘要。

交叉验证:
    - post_objects 中引用的 object 名称是否都存在于 model (强校验)
    - grid_params 行类型 与 model 对象类型的对照(信息性)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re

from . import project as projmod
from . import export

_PROJ_FILES = ("model", "problem", "main.ice.xml")


def is_project_dir(path: str) -> bool:
    return any(os.path.isfile(os.path.join(path, f)) for f in _PROJ_FILES)


def find_projects(root: str):
    """返回 [(name, kind('dir'|'tzr'), source)]"""
    items = []
    if os.path.isfile(root) and root.lower().endswith(".tzr"):
        return [(os.path.basename(root), "tzr", root)]
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full) and is_project_dir(full):
            items.append((name, "dir", full))
        elif os.path.isfile(full) and name.lower().endswith(".tzr"):
            items.append((name, "tzr", full))
    return items


def load(entry):
    name, kind, source = entry
    try:
        if kind == "tzr":
            proj = projmod.IcepakProject.from_archive(source)
        else:
            proj = projmod.IcepakProject(source)
        return proj, None
    except Exception as e:
        return None, "%r: %s" % (source, e)


# ---------------------------------------------------------------- 交叉验证

_OBJREF_RE = re.compile(r"\bobject\s+([\w.+-]+)", re.I)


def cross_validate(proj):
    """返回 dict: 强校验(post引用对象缺失) 与 信息性(grid对照)."""
    ck = {"post_missing_in_model": [], "checked_post_refs": 0,
          "grid_types": {}, "model_kinds": {},
          "unknown_object_types": set()}
    model = proj.model
    if model:
        ck["model_kinds"] = dict(model.kind_counts())
    if proj.post:
        for po in proj.post:
            ref = (po.get("params") or {}).get("-object_names", "")
            for nm in _OBJREF_RE.findall(ref):
                ck["checked_post_refs"] += 1
                if model is not None and model.object_by_name(nm) is None:
                    ck["post_missing_in_model"].append(nm)
    # grid 行类型统计
    from collections import Counter
    ck["grid_types"] = dict(Counter((r[0] for r in proj.grid if r)))
    # 未知对象类型(疑似解析/识别缺口)
    known = {"domain", "plate", "block", "source", "package", "pcb", "wall",
             "fan", "opening", "resistance", "ventres", "material", "part",
             "heatsink", "enclosure", "collap", "sink", "assembly"}
    if model:
        ck["unknown_object_types"] = sorted(set(model.kind_counts()) - known)
    return ck


# ---------------------------------------------------------------- 汇总

def scan(root: str):
    """扫描全部项目, 返回逐项目结果(含校验)."""
    results = []
    entries = find_projects(root)
    if not entries:
        return results
    for entry in entries:
        proj, err = load(entry)
        if proj is None:
            results.append({"name": entry[0], "kind": entry[1], "error": err})
            continue
        r = {"name": proj.name, "kind": entry[1], **proj.summary()}
        r["cross"] = cross_validate(proj)
        results.append(r)
    return results


def _flat(r):
    """把结果拍平成一行用于 CSV."""
    c = r.get("cross") or {}
    return [
        r.get("name"), r.get("kind"),
        r.get("objects"), r.get("time") or "",
        ",".join("%s:%s" % kv for kv in (r.get("object_types") or {}).items()),
        ",".join("%s:%s" % kv for kv in c.get("grid_types", {}).items()),
        c.get("checked_post_refs", 0),
        ";".join(c.get("post_missing_in_model", [])),
        ",".join(c.get("unknown_object_types", [])),
        " | ".join(str(r.get("error", ""))).strip(),
    ]


_CSV_HEADER = ["name", "kind", "objects", "time", "object_types",
               "grid_types", "post_refs", "post_missing", "unknown_kinds", "error"]


def write_report(results, csv_path=None, json_path=None) -> tuple:
    out = {}
    if csv_path:
        with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(_CSV_HEADER)
            for r in results:
                w.writerow(_flat(r))
        out["csv"] = csv_path
    if json_path:
        with io.open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        out["json"] = json_path
    return out


def analyze_one(target: str) -> str:
    """单个项目/归档 -> 结构化 JSON 摘要."""
    if target.lower().endswith(".tzr"):
        proj = projmod.IcepakProject.from_archive(target)
    else:
        proj = projmod.IcepakProject(target)
    d = export.to_dict(proj)
    d["cross"] = cross_validate(proj)
    return json.dumps(d, ensure_ascii=False, indent=2, default=str)


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="icepak-cli",
                                 description="ANSYS Icepak 项目逆向解析与批量汇总")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="批量扫描目录下所有项目")
    s.add_argument("root")
    s.add_argument("-o", "--outdir", default=None, help="报告输出目录(可选)")
    s.add_argument("--csv", default=None)
    s.add_argument("--json", default=None)
    s.set_defaults(func=_do_scan)

    a = sub.add_parser("analyze", help="单个项目结构化导出")
    a.add_argument("target")
    a.set_defaults(func=_do_analyze)

    args = ap.parse_args(argv)
    return args.func(args)


def _do_scan(args) -> int:
    results = scan(args.root)
    print("found projects: %d" % len(results))
    for r in results:
        c = r.get("cross") or {}
        miss = c.get("post_missing_in_model") or []
        flag = "MISSING" if miss else "ok"
        print("  [%s] %-24s objects=%-4s %-7s post_refs=%d %s%s" % (
            r.get("kind"), r.get("name"), r.get("objects"),
            r.get("time") or "-", c.get("checked_post_refs", 0), flag,
            (" " + repr(miss)) if miss else ""))
    files = {}
    if args.outdir or args.csv or args.json:
        os.makedirs(args.outdir, exist_ok=True) if args.outdir else None
        csv_path = args.csv or (os.path.join(args.outdir, "report.csv") if args.outdir else None)
        json_path = args.json or (os.path.join(args.outdir, "report.json") if args.outdir else None)
        files = write_report(results, csv_path, json_path)
    print("wrote:", files or "(no report written)")
    return 0


def _do_analyze(args) -> int:
    print(analyze_one(args.target))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))