# -*- coding: utf-8 -*-
"""P13: conformal refinement replication tests."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_refine import merged_axis, refine_axes, refine_mesh, tune_for_target

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


def test_merged_axis_inserts_cuts():
    base = [0.0, 0.5, 1.0]
    m = merged_axis(base, [0.2, 0.8], 0.01)
    assert 0.2 in m and 0.8 in m
    assert m == sorted(m)


def test_refine_axes_monotonic_and_spacing():
    axes = [[0.0, 0.1, 0.2], [0.0, 0.1, 0.2], [0.0, 0.1, 0.2]]
    objs = [("b1", ((0.03, 0.0, 0.0), (0.07, 0.1, 0.1)))]
    out = refine_axes(axes, objs, min_spacing=0.005, interior_ratio=2)
    for a in out:
        assert a == sorted(a)
        assert all(a[i + 1] - a[i] >= 0.002 for i in range(len(a) - 1))
    assert out[0][-1] == pytest.approx(0.2)


def test_refine_increases_cells(win):
    win._new_project()
    win._create_object("block")  # 0.02..0.07 box inside cabinet
    from ice_mesh import generate_mesh
    base = generate_mesh(win.project.model, counts=(10, 10, 10))
    r = refine_mesh(base, win.project.model, min_spacing=0.01,
                    interior_ratio=2)
    assert r.cell_count > base.cell_count
    assert r.node_count == (r.nx + 1) * (r.ny + 1) * (r.nz + 1)


def test_tune_for_target_converges(win):
    win._new_project()
    win._create_object("block")
    best = tune_for_target(os.getcwd(), 2000, model=win.project.model,
                           lo=0.004, hi=0.02, iters=10)
    assert best is not None
    assert abs(best[1] - 2000) / 2000.0 < 0.15
    assert best[2].cell_count == best[1]


def test_autohax_edit_tab_refine(qapp):
    from ice_panes import AutoHexDialog
    dlg = AutoHexDialog()
    edit = dlg.tabs.widget(3)
    assert edit.row("refine_faces_on").get() is True
    assert edit.row("min_spacing").get() is not None
    dlg.close()


def test_gui_run_mesh_refined(win):
    win._new_project()
    win._create_object("block")
    res = win._run_mesh({"refine_faces_on": True, "min_spacing": 0.01,
                         "interior_ratio": 2.0, "match_oracle_cells": 0},
                        write_files=False)
    assert res is not None
    assert res.cell_count > 1000
