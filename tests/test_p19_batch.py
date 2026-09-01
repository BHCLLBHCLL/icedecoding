# -*- coding: utf-8 -*-
"""Phase C: IcBQS client + batch scheduler + CLI tests."""
import os
import socket
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ice_batch import IcBQSClient, BatchScheduler
import ice_cli


def test_scheduler_runs_jobs():
    calls = []
    sched = BatchScheduler(lambda j, s, m, p: calls.append((j, s, m, p))
                           or {"ok": True})
    res = sched.run([("a", "t", False, 1), ("b", "u", True, 4)])
    assert len(res) == 2 and len(calls) == 2
    assert calls[1] == ("b", "u", True, 4)


def test_icbqs_client_against_mock_server():
    server_port = []

    def serve():
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(2)
        server_port.append(srv.getsockname()[1])
        for _ in range(2):
            conn, _ = srv.accept()
            conn.settimeout(5)
            data = conn.recv(4096).decode("latin-1")
            line = data.strip()
            if line.startswith("submit"):
                conn.sendall(b"ok JOB1\n")
            elif line.startswith("status"):
                conn.sendall(b"done ok\n")
            conn.close()
        srv.close()

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    import time
    for _ in range(200):
        if server_port:
            break
        time.sleep(0.005)
    assert server_port
    client = IcBQSClient(port=server_port[0])
    jid, resp = client.submit("jobdir")
    assert jid == "JOB1"
    st, _ = client.status("JOB1")
    assert st == "done"


def test_cli_run_returns_dict():
    out = ice_cli.run_job("no-such-dir", report=False)
    assert "job" in out
