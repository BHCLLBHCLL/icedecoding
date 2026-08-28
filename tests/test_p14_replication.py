# -*- coding: utf-8 -*-
"""P14 tests: adaptive subdivision, node-target replication, refined solver."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_refine import tune_replication_v2
from heat_solver import solve_heat

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


def test_v2_matches_node_target_on_demo(win):
    win._new_project()
    win._create_object("block")
    best = tune_replication_v2(os.getcwd(), 4000, model=win.project.model,
                               base_counts=(8, 9, 10),
                               spacings=(0.004, 0.005, 0.006))
    err, bc, ms, r = best
    assert err < 0.20
    assert r.node_count == (r.nx + 1) * (r.ny + 1) * (r.nz + 1)


def test_refined_mesh_supports_heat_solver(win):
    win._new_project()
    win._create_object("block")
    from ice_mesh import generate_mesh
    from ice_refine import refine_mesh
    base = generate_mesh(win.project.model, counts=(10, 10, 10))
    r = refine_mesh(base, win.project.model, min_spacing=0.02,
                    interior_ratio=2.0)
    assert r.cell_count > base.cell_count
    T, rows = solve_heat(r, win.project.model, max_iter=40)
    assert len(T) == r.cell_count
    assert rows and rows[-1][1] <= rows[0][1] + 1e-12
    assert max(T.values()) >= 20.0
