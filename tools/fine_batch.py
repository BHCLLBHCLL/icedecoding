# -*- coding: utf-8 -*-
"""P15: fine full cross-scan runner (>=10 spacings x >=6 base counts),
incremental per-project results into tools/probe_work/fine_batch.json."""
import json
import os
import sys
import time
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tools", "probe_work", "fine_batch.json")
ROOT = r"D:\training\icepak"


def run_scan(name):
    try:
        return _run_scan(name)
    except Exception as e:
        return {"project": name, "skipped": "%s" % e}


def _run_scan(name):
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh
    from ice_refine import refine_mesh
    import ecad_oracle_probe as P

    proj = P.oracle_counts_of_job(os.path.join(ROOT, name))
    node_t = (proj.get("cas") or {}).get("nodes") or proj.get(
        "nodemap_lines") or 0
    if not node_t:
        return {"project": name, "skipped": "no cas/nodemap"}
    model_project = IcepakProject(os.path.join(ROOT, name))
    model = model_project.model
    if model is None:
        return {"project": name, "skipped": "no model parsed"}
    n_objs = len(list(model._all_objects()))
    # domain length for spacing scaling
    from ice_mesh import _bounds_of
    L = 0.3
    for o in model._all_objects():
        if o.kind == "domain":
            b = _bounds_of(o)
            if b:
                L = max(b[1][i] - b[0][i] for i in range(3))
            break
    if n_objs > 120:
        bases, n_sp = (8, 10, 12), 8
    else:
        bases, n_sp = (6, 8, 9, 10, 11, 12, 14), 12
    lo_sp = L / 300.0
    hi_sp = L / 100.0
    spacings = [lo_sp * (hi_sp / lo_sp) ** (k / (n_sp - 1.0))
                for k in range(n_sp)]
    best = None
    t0 = time.time()
    for bc in bases:
        base = generate_mesh(model, counts=(bc, bc, bc))
        for ms in spacings:
            r = refine_mesh(base, model, min_spacing=ms, interior_ratio=2.0,
                            max_cells=10 ** 7)
            err = abs(r.node_count - node_t) / float(node_t)
            if best is None or err < best[0]:
                best = (err, bc, ms, r.node_count, r.cell_count)
    err, bc, ms, nodes, cells = best
    # stage 2: coarse rescale when the fine scan overshoots (small models)
    if err > 0.10:
        spac_c = [L / v for v in (40.0, 55.0, 75.0, 100.0, 140.0, 190.0)]
        base_c = (4, 5, 6, 8, 10)
        for b2 in base_c:
            base2 = generate_mesh(model, counts=(b2, b2, b2))
            for ms2 in spac_c:
                r2 = refine_mesh(base2, model, min_spacing=ms2,
                                 interior_ratio=2.0, max_cells=10 ** 7)
                e2 = abs(r2.node_count - node_t) / float(node_t)
                if e2 < err:
                    err, bc, ms, nodes, cells = e2, b2, ms2, \
                        r2.node_count, r2.cell_count
    cell_t = (proj.get("cas") or {}).get("cells")
    return {"project": name, "node_target": node_t, "cell_target": cell_t,
            "best_err": err, "base_count": bc, "min_spacing": ms,
            "nodes": nodes, "cells": cells,
            "objects": n_objs, "elapsed_s": round(time.time() - t0, 1)}


def main(argv):
    names = argv[1:] or [n for n in sorted(os.listdir(ROOT))
                         if os.path.isdir(os.path.join(ROOT, n))]
    results = {}
    if os.path.exists(OUT):
        try:
            results = json.load(open(OUT, encoding="utf-8"))
        except (OSError, ValueError):
            results = {}
    for name in names:
        if name in results:
            continue
        print("scanning", name, flush=True)
        r = run_scan(name)
        results[name] = r
        json.dump(results, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if r.get("best_err") is not None:
            print("  %s err=%.3f%% nodes=%d cells=%d (bc=%s ms=%.5f)" %
                  (name, r["best_err"] * 100, r["nodes"], r["cells"],
                   r["base_count"], r["min_spacing"]), flush=True)
        else:
            print("  %s %s" % (name, r.get("skipped")), flush=True)
    print("DONE", len(results), "entries")


if __name__ == "__main__":
    main(sys.argv)
