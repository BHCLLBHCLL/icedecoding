# -*- coding: utf-8 -*-
"""P19-8 / Phase C: IcBQS (Icepak Batch Queuing System) client + scheduler.

IcBQS semantics: a line-based TCP queue server (default port 6791) that
accepts job submissions and reports status.  This module provides a client
binding and a local serial scheduler; the wire protocol is a best-effort
reconstruction (the original icbqs_server.tcl is encrypted).
"""
import os
import socket
import time


class IcBQSClient(object):
    """Submit / poll jobs on an IcBQS server (default 127.0.0.1:6791)."""

    def __init__(self, host="127.0.0.1", port=6791, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def _send(self, line):
        with socket.create_connection((self.host, self.port),
                                      timeout=self.timeout) as s:
            s.sendall((line.rstrip("\n") + "\n").encode("latin-1"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
            return buf.decode("latin-1", "replace").strip()

    def submit(self, job_dir, solver="transient00", mesh_only=False,
               parallel=None):
        """Submit a job; returns (job_id, message)."""
        msg = "submit %s %s %s %s" % (job_dir, solver,
                                      1 if mesh_only else 0,
                                      parallel or 1)
        resp = self._send(msg)
        parts = resp.split()
        jid = parts[1] if len(parts) > 1 else None
        return jid, resp

    def status(self, job_id):
        resp = self._send("status %s" % job_id)
        st = resp.split(" ", 1)[0] if resp else None
        return st, resp

    def poll(self, job_id, timeout=120.0, interval=2.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st, resp = self.status(job_id)
            if st in ("done", "failed", "cancelled"):
                return st, resp
            time.sleep(interval)
        return "timeout", resp


class BatchScheduler(object):
    """Local serial scheduler: run jobs in order on this host."""

    def __init__(self, runnable=None):
        # runnable: callable(job_dir, solver, mesh_only, parallel) -> dict
        self.runnable = runnable or (lambda *a, **k: {"ok": True})

    def run(self, jobs):
        results = []
        for job in jobs:
            job_dir, solver = job[0], job[1]
            mesh_only = job[2] if len(job) > 2 else False
            parallel = job[3] if len(job) > 3 else 1
            results.append(self.runnable(job_dir, solver, mesh_only,
                                         parallel))
        return results
