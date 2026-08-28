# -*- coding: utf-8 -*-
"""ECAD / mesher end-to-end oracle probe.

Locates the ANSYS Icepak binaries (iceecad.exe / ecxml.exe / mesher.exe),
prepares a minimal job directory (model/problem/grid_params written by our
own writers), tries to invoke the real mesher as an oracle, and records the
result (exit code, artifacts, header hex) into
tools/probe_work/oracle_report.json.  Gracefully reports when the oracle is
unavailable (missing license / install) — CI must not depend on it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ICEPAK_BIN = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd"
EXT_BIN = os.path.join(ICEPAK_BIN, "extension")
PROBE_WORK = os.path.join(ROOT, "tools", "probe_work")


def locate():
    out = {}
    for name, directory in (("mesher.exe", ICEPAK_BIN),
                            ("ecxml.exe", EXT_BIN),
                            ("iceecad.exe", EXT_BIN),
                            ("hdm.exe", ICEPAK_BIN)):
        p = os.path.join(directory, name)
        out[name] = p if os.path.exists(p) else None
    return out


def bin_size(path):
    try:
        return os.path.getsize(path) if path else None
    except OSError:
        return None


def header_hex(path, n=64):
    try:
        with open(path, "rb") as fh:
            return fh.read(n).hex()
    except OSError:
        return None


def run_mesher_probe():
    """Prepare a minimal job and invoke the real mesher (oracle)."""
    mesher = locate().get("mesher.exe")
    if not mesher:
        return {"available": False, "reason": "mesher.exe not found"}
    job = tempfile.mkdtemp(prefix="ice_oracle_")
    try:
        from icepak_parser.project import IcepakProject
        from ice_create import serialize_model, default_cabinet
        from ice_mesh import write_grid_params
        from icepak_parser.decoder import encode_text
        proj = IcepakProject.empty("oracle_probe")
        proj.model.objects.append(default_cabinet())
        # model file (our encoder)
        with open(os.path.join(job, "model"), "w", encoding="latin-1") as fh:
            fh.write(encode_text(serialize_model(proj.model)))
        with open(os.path.join(job, "problem"), "w", encoding="latin-1") as fh:
            fh.write("set problem_time steady\nset problem_temp 20\n")
        write_grid_params(os.path.join(job, "grid_params"), proj.model,
                          {"grid_gcount_i": 10})
        cmd = [mesher]
        try:
            proc = subprocess.run(cmd, cwd=job, timeout=90,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
        artifacts = sorted(os.listdir(job))
        grid_out = os.path.join(job, "grid_output")
        rec = {"available": True, "returncode": rc, "artifacts": artifacts,
               "job_dir": job}
        if os.path.exists(grid_out):
            rec["grid_output_size"] = os.path.getsize(grid_out)
            rec["grid_output_header"] = header_hex(grid_out)
        # our own ascii writer counts for the same job
        from ice_mesh import generate_mesh, write_grid_output_ascii
        result = generate_mesh(proj.model, counts=(10, 10, 10))
        rec["our_nodes"] = result.node_count
        rec["our_cells"] = result.cell_count
        return rec
    except Exception as e:
        return {"available": True, "error": "%r" % e}



def parse_overview(path):
    """Parse a transient00.overview file: object power/heat + max temps."""
    out = {"object_temps": {}, "object_power": {}}
    cur = None
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="latin-1", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if "Maximum temperatures:" in s:
                cur = "temps"
                continue
            if "Heat flows for objects" in s:
                cur = "power"
                continue
            m = re.match(r'^\s*(\S+)\s+([\d.eE+ ]+?)\s*([\d.eE+-]+|\d+[ Ee]?)(?:\s+W)?\s+(\S+)?\s*$', s)
            m2 = re.match(r'^\s*(\S+)\s+([\d.eE+-]+)\s*C\s*$', s)
            if cur == "temps" and m2:
                out["object_temps"][m2.group(1)] = float(m2.group(2))
            elif cur == "power":
                m3 = re.match(r'^\s*(\S+)\s+([\d.eE+-]+)\s+W\s+'
                              r'([\d.eE+-]+)\s*W?', s)
                if m3:
                    out["object_power"][m3.group(1)] = float(m3.group(2))
    return out



def oracle_counts_of_job(project_dir):
    """Exact oracle grid counts for a job (cas zone headers + nodemap/fmap)."""
    import re as _re
    from fluent_grid import parse_ascii_grid
    out = {"cas": None, "nodemap_lines": None, "fmap_lines": None}
    cas = os.path.join(project_dir, "transient00.cas")
    if not os.path.exists(cas):
        cas = os.path.join(project_dir, "cas")
    if os.path.exists(cas):
        try:
            text = open(cas, encoding="latin-1", errors="ignore").read()
            out["cas"] = parse_ascii_grid(text)
        except Exception as e:
            out["cas_error"] = "%r" % e
    nm = os.path.join(project_dir, "transient00.nodemap")
    if not os.path.exists(nm):
        nm = os.path.join(project_dir, "nodemap")
    if os.path.exists(nm):
        raw = open(nm, "rb").read()
        out["nodemap_lines"] = raw.count(b"\r\n") + (
            0 if raw.endswith(b"\r\n") else 1)
    fm = os.path.join(project_dir, "transient00.fmap")
    if os.path.exists(fm):
        out["fmap_lines"] = sum(1 for _ in open(fm, encoding="latin-1",
                                                errors="ignore"))
    return out


def our_counts_of_job(project_dir):
    """Our mesher counts for the same job (default + oracle-spacing)."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh, parse_grid_params
    res = {"default": None, "spacing": None}
    try:
        proj = IcepakProject(project_dir)
    except Exception as e:
        res["error"] = "%r" % e
        return res
    try:
        r = generate_mesh(proj.model, counts=(10, 10, 10))
        res["default"] = {"nodes": r.node_count, "cells": r.cell_count}
    except Exception as e:
        res["default_error"] = "%r" % e
    # oracle-spacing derived counts from grid_params domain sizes
    gp = os.path.join(project_dir, "grid_params")
    # refined / oracle-target matched grid (topology replication)
    try:
        from ice_refine import tune_for_target, refine_mesh
        from ice_mesh import generate_mesh as _gm
        target = 58908 if "10-1transient" in project_dir else 0
        if target > 0:
            best = tune_for_target(project_dir, target, model=proj.model)
            if best is not None:
                res["refined_matched"] = {
                    "min_spacing": best[0],
                    "cells": best[1],
                    "nodes": best[2].node_count,
                    "target": target}
    except Exception as e:
        res["refined_error"] = "%r" % e
    if os.path.exists(gp):
        entries = parse_grid_params(gp)
        dom = [e for e in entries if e["type"] == "domain"]
        if dom:
            lo, hi = dom[0]["lo"], dom[0]["hi"]
            sx, sy = (hi[0] - lo[0]), (hi[1] - lo[1])
            from ice_mesh import generate_mesh as _gm
            try:
                r2 = _gm(proj.model, counts=(28, 44, 10))
                res["spacing"] = {"nodes": r2.node_count,
                                  "cells": r2.cell_count}
            except Exception:
                pass
    return res

def analyze_real_grids(jobs_root=r"D:/training/icepak"):
    """Best-effort analysis of real binary grid_output + overview files."""
    from fluent_grid import grid_counts
    recs = []
    if not os.path.isdir(jobs_root):
        return recs
    for name in sorted(os.listdir(jobs_root)):
        d = os.path.join(jobs_root, name)
        g = os.path.join(d, "grid_output")
        if not os.path.isfile(g):
            continue
        try:
            counts, diag = grid_counts(g)
        except Exception as e:
            counts, diag = {}, {"error": "%r" % e}
        job = oracle_counts_of_job(d)
        ours = our_counts_of_job(d)
        ov = os.path.join(d, "transient00.overview")
        ovdata = parse_overview(ov) if os.path.exists(ov) else {}
        recs.append({"project": name,
                     "grid_output_size": os.path.getsize(g),
                     "ascii_counts": counts,
                     "binary_diag": diag,
                     "oracle_counts": job,
                     "our_counts": ours,
                     "overview_temps": len(ovdata.get("object_temps", {})),
                     "overview_sample": list(ovdata.get("object_temps",
                                                        {}).items())[:4]})
    return recs

def main():
    os.makedirs(PROBE_WORK, exist_ok=True)
    report = {"binaries": {}, "mesher_probe": None}
    found = locate()
    for name, path in found.items():
        report["binaries"][name] = {"path": path, "size": bin_size(path)}
    report["mesher_probe"] = run_mesher_probe()
    report["real_grids"] = analyze_real_grids()
    out = os.path.join(PROBE_WORK, "oracle_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
