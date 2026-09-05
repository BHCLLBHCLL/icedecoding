# -*- coding: utf-8 -*-
"""P19-G4: optimization loop + solution id management (Phase G close)."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_actions import SLOT_MAP
from ice_mesh import generate_mesh
from ice_create import default_cabinet
from icepak_parser.project import IcepakProject

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp):
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    yield w
    w.close()


def test_opt_slot():
    assert SLOT_MAP.get("Run optimization") == "_run_optimization"


def test_solve_with_id(win, monkeypatch):
    win._new_project()
    win.project.model.objects.append(default_cabinet())
    win._mesh_result = generate_mesh(win.project.model, counts=(4, 4, 3),
                                     gtype="unif")
    d = tempfile.mkdtemp(prefix="g4_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    temps = win._solve_with_id("transient00", iters=30)
    assert temps and len(temps) > 0
    assert win._solution_id == "transient00"
    assert os.path.exists(os.path.join(d, "transient00.resd"))


def test_run_optimization_no_trials_nyi(win, monkeypatch):
    win._new_project()
    calls = []
    monkeypatch.setattr(win, "_nyi", lambda t: calls.append(t))
    win._run_optimization()
    assert calls == ["Run optimization"]


def test_set_solution_id(win, monkeypatch):
    from PyQt5.QtWidgets import QInputDialog
    win._new_project()
    win.project.problem = type("P", (), {"setters": {}})()
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("trial002", True)))
    win._set_solution_id()
    assert win._solution_id == "trial002"
    assert win.project.problem.setters.get("solve_id") == "trial002"


def test_solve_menu_has_solution_id(win):
    m = win._menus["Solve"]
    texts = [a.text() for a in m.actions()]
    assert "Solution id..." in texts
