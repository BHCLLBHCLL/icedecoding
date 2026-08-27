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


def main():
    os.makedirs(PROBE_WORK, exist_ok=True)
    report = {"binaries": {}, "mesher_probe": None}
    found = locate()
    for name, path in found.items():
        report["binaries"][name] = {"path": path, "size": bin_size(path)}
    report["mesher_probe"] = run_mesher_probe()
    out = os.path.join(PROBE_WORK, "oracle_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
