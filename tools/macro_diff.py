# -*- coding: utf-8 -*-
"""P19-5: macro oracle-diff harness.

Official macro Tcl is digest-encrypted upstream, so the 'oracle' here is
two-fold:
  1. builtin parameterized macros -> rule table derived from the builders
     (object counts / kinds / geometry bounds / setvals), diffed per build;
  2. the 845 macro-library parts -> their OFFICIAL parameter files (the real
     icepak_lib corpus) are the golden; every part's generated package must
     echo the official params and reproduce the official geometry rules
     (bbox = ball_num * ball_pitch / thickness).

Golden anchors live in tools/probe_work/macro_golden.json; run_macro_diff()
reports deltas (0 = full match).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ice_macros import (BUILTIN_MACROS, build_macro, build_library_part,
                        scan_macro_library)
from icepak_parser.project import IcepakProject

GOLDEN_PATH = os.path.join(ROOT, "tools", "probe_work", "macro_golden.json")


def bbox_of(obj):
    """(lo, hi) float bbox from an object's hexa shape point1/point2."""
    sh = getattr(obj, "shape", None)
    sv = getattr(sh, "setvals", None) or {}
    p1 = sv.get("point1") or ["0", "0", "0"]
    p2 = sv.get("point2") or ["0", "0", "0"]
    try:
        lo = tuple(float(v) for v in p1)
        hi = tuple(float(v) for v in p2)
    except (TypeError, ValueError):
        return None
    return lo, hi


def _near(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def builtin_expectations(key, params):
    """Expected invariants for each builtin macro at the given params."""
    if key == "angled_fin":
        return {"count": 1 + int(params.get("fin_count", 8))}
    if key == "bga":
        n = int(params.get("ball_count", 8))
        body = float(params.get("body_size", 0.027))
        bt = float(params.get("body_thickness", 0.0012))
        return {"count": 2 + n * n,
                "body_bbox": ((0.0, 0.0, 0.0), (body, body, bt)),
                "package_type": "bga"}
    if key == "tec":
        return {"count": 2 + int(params.get("pellets", 5))}
    if key == "sot":
        return {"count": 2 + 2 * int(params.get("lead_count", 4))}
    if key == "blower":
        return {"count": 1, "kind": "blower"}
    return {}


def diff_builtin(key, params=None):
    """Build a builtin macro and diff against its rule table -> delta strings."""
    params = dict(params or {})
    spec = BUILTIN_MACROS.get(key)
    if spec is None:
        return ["%s: unknown macro" % key]
    proj = IcepakProject.empty("md_%s" % key)
    created = build_macro(proj.model, key, params)
    objs = list(proj.model._all_objects())
    deltas = []
    exp = builtin_expectations(key, params)
    if "count" in exp and len(objs) != exp["count"]:
        deltas.append("%s: count expected %d got %d"
                      % (key, exp["count"], len(objs)))
    if "kind" in exp and objs and objs[0].kind != exp["kind"]:
        deltas.append("%s: kind expected %s got %s"
                      % (key, exp["kind"], objs[0].kind))
    if "package_type" in exp:
        pkg = [o for o in objs if getattr(o, "kind", None) == "package"]
        if not pkg:
            deltas.append("%s: no package object" % key)
        else:
            sv = getattr(pkg[0], "setvals", None) or {}
            got = (sv.get("package_type") or ["?"])[0]
            if got != exp["package_type"]:
                deltas.append("%s: package_type expected %s got %s"
                              % (key, exp["package_type"], got))
    if "body_bbox" in exp:
        pkg = [o for o in objs if getattr(o, "kind", None) == "package"]
        if pkg:
            bb = bbox_of(pkg[0])
            if bb is None:
                deltas.append("%s: body has no bbox" % key)
            else:
                (lo, hi), (elo, ehi) = bb, exp["body_bbox"]
                for i in range(3):
                    if not _near(lo[i], elo[i]) or not _near(hi[i], ehi[i]):
                        deltas.append("%s: body bbox axis %d expected %s..%s "
                                      "got %s..%s"
                                      % (key, i, elo, ehi, lo, hi))
                        break
    return deltas


def diff_library_part(macro):
    """Build one macro-library part and diff against its OFFICIAL param file."""
    proj = IcepakProject.empty("mdlib")
    try:
        obj = build_library_part(proj.model, macro)
    except Exception as err:
        return ["%s: build failed: %r" % (macro.get("name"), err)]
    p = macro.get("params", {})
    deltas = []
    name = macro.get("name")
    sv = getattr(obj, "setvals", None) or {}
    def got(key):
        v = sv.get(key)
        if isinstance(v, list):
            v = v[-1] if v else ""
        return str(v)
    # official params echoed verbatim
    for key in ("ball_pitch", "ball_num1", "ball_num2", "die_dim1",
                "die_dim2"):
        official = str(p.get(key, ""))
        if got(key) != official:
            deltas.append("%s: setvals[%s] expected %s got %s"
                          % (name, key, official, got(key)))
    if got("library") != str(macro.get("library", "")):
        deltas.append("%s: library expected %s got %s"
                      % (name, macro.get("library"), got("library")))
    # official geometry rules: bbox = ball_num2*pitch x ball_num1*pitch x pkg
    n1 = int(p.get("ball_num1", 8))
    n2 = int(p.get("ball_num2", 8))
    bp = float(p.get("ball_pitch", 1.0)) * 0.001
    th = float(p.get("package_thickness", 2.0)) * 0.001
    bb = bbox_of(obj)
    if bb is None:
        deltas.append("%s: no bbox" % name)
    else:
        (lo, hi) = bb
        sx = hi[0] - lo[0]
        sy = hi[1] - lo[1]
        sz = hi[2] - lo[2]
        if not _near(sx, n2 * bp, 1e-9):
            deltas.append("%s: x-span expected %g got %g" % (name, n2 * bp, sx))
        if not _near(sy, n1 * bp, 1e-9):
            deltas.append("%s: y-span expected %g got %g" % (name, n1 * bp, sy))
        if not _near(sz, th, 1e-9):
            deltas.append("%s: z-span expected %g got %g" % (name, th, sz))
    return deltas


def run_macro_diff(lib_limit=None):
    """Diff all builtin macros + the macro-library corpus -> summary dict."""
    summary = {"builtin_checked": 0, "builtin_deltas": [],
               "library_checked": 0, "library_deltas": []}
    for key in sorted(BUILTIN_MACROS):
        summary["builtin_checked"] += 1
        summary["builtin_deltas"].extend(diff_builtin(key))
    parts = scan_macro_library()
    for macro in parts[:lib_limit]:
        summary["library_checked"] += 1
        summary["library_deltas"].extend(diff_library_part(macro))
    summary["library_total"] = len(parts)
    summary["delta_total"] = (len(summary["builtin_deltas"]) +
                              len(summary["library_deltas"]))
    return summary


def write_golden():
    """Freeze the expected builtin counts/keys into the golden JSON."""
    golden = {"builtin": {}}
    for key in sorted(BUILTIN_MACROS):
        deltas = diff_builtin(key)
        golden["builtin"][key] = {"default_deltas": deltas}
    golden["library_total"] = len(scan_macro_library())
    os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
    with open(GOLDEN_PATH, "w", encoding="utf-8") as fh:
        json.dump(golden, fh, indent=1)
    return golden


def main(argv=None):
    argv = argv or sys.argv[1:]
    if argv and argv[0] == "--golden":
        out = write_golden()
        print("golden written: %s (library_total=%d)"
              % (GOLDEN_PATH, out["library_total"]))
        return 0
    summary = run_macro_diff(lib_limit=None)
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    report = os.path.join(ROOT, "tools", "probe_work", "macro_diff_report.json")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    return 0 if summary["delta_total"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
