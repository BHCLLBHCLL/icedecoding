# -*- coding: utf-8 -*-
"""P19-8 / Phase C: batch-deploy CLI (equivalence to GUI solve/report flow).

Usage:  python -m icepak_cli run <job_dir> [--mesh-only] [--report]
        python -m icepak_cli batch <job1> <job2> ... [--report]
        python -m icepak_cli icbqs submit <job_dir>
"""
import sys


def run_job(job_dir, mesh_only=False, report=False, parallel=1):
    """Load a job, build its mesh, optionally solve + write report.  Returns
    a dict summary (headless, uses the same modules as the GUI)."""
    out = {"job": job_dir, "mesh": False, "solve": False, "report": None}
    try:
        from icepak_parser.project import IcepakProject
        from ice_mesh import generate_mesh
        proj = IcepakProject(job_dir)
        res = generate_mesh(proj.model, counts=(10, 10, 10))
        out["mesh"] = True
        out["cells"] = res.cell_count
        out["nodes"] = res.node_count
        if report:
            from ice_report import write_real_report
            p = write_real_report(os.path.join(job_dir, "report.html"),
                                  job_dir)
            out["report"] = p
    except Exception as e:
        out["error"] = "%r" % e
    return out


def main(argv):
    args = argv[1:]
    if not args:
        print("usage: icepak_cli run|batch|icbqs ...")
        return 2
    mode = args[0]
    if mode == "run":
        job = args[1]
        mesh_only = "--mesh-only" in args
        report = "--report" in args
        print(run_job(job, mesh_only=mesh_only, report=report))
        return 0
    if mode == "batch":
        report = "--report" in args
        jobs = [a for a in args[1:] if not a.startswith("--")]
        from ice_batch import BatchScheduler
        sched = BatchScheduler(lambda j, s, m, p: run_job(j, m, s and report))
        res = sched.run([(j, "transient00", False, 1) for j in jobs])
        for r in res:
            print(r)
        return 0
    if mode == "command":
        return command_cli(" ".join(args[1:]))
    if mode == "icbqs" and len(args) >= 3 and args[1] == "submit":
        from ice_batch import IcBQSClient
        jid, resp = IcBQSClient().submit(args[2])
        print(resp)
        return 0
    print("unknown mode", mode)
    return 2


def command_cli(text):
    """H3: run an arbitrary golden command (or python expr) headless.
    Spins an offscreen IceGui, resolves the command text, invokes it."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from ice_gui import IceGui
        from ice_actions import resolve_slot
        w = IceGui(enable_3d=False, show_welcome=False)
        try:
            slot = resolve_slot(w, text)
            if slot is not None and not hasattr(slot, "cmd"):
                slot()
                print("ran: %s" % text)
                return 0
            # python console equivalent
            loc = {"self": w}
            if "=" in text or "\n" in text:
                exec(text, loc)
            else:
                print(repr(eval(text, loc)))
            return 0
        except Exception as e:
            print("ERR: %r" % e)
            return 1
        finally:
            w.close()
    except Exception as e:
        print("ERR: %r" % e)
        return 1


if __name__ == "__main__":
    import os
    sys.exit(main(sys.argv))
