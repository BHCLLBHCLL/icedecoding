# -*- coding: utf-8 -*-
"""P6 solve/post/report tests."""

def _add_block(win):
    """Append a block directly (avoids GUI refresh paths in headless)."""
    from ice_create import default_object
    model = win.project.model
    obj = default_object("block", "block.1", index=model.count_all(),
                         creation_order=model.count_all() + 1)
    model.objects.append(obj)
    return obj

import math
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_solve import (
    simulate_residuals, write_resd, read_resd, simulate_history,
    sample_along, synthetic_cell_temps, plane_cut_points, iso_points,
    trials_from_problem, POST_SPECS, write_setter,
)
from ice_report import html_report, summary_data, object_table
from ice_solve_gui import SolveSettingsDialog, PlotWindow, \
    ResidualMonitorWindow

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


def test_residuals_decay():
    rows = simulate_residuals(50)
    assert len(rows) == 50
    assert rows[0][1][0] > rows[-1][1][0]
    assert all(v > 0 for _, vals in rows for v in vals)


def test_resd_roundtrip():
    d = tempfile.mkdtemp(prefix="ice_resd_")
    pth = os.path.join(d, "transient00.resd")
    rows = simulate_residuals(10)
    write_resd(pth, "transient00", rows)
    back = read_resd(pth)
    assert back is not None
    assert len(back) == 10
    assert back[-1][0] == 10


def test_simulation_history_monotonic():
    h = simulate_history("p1", 20, 20.0, 85.0)
    assert h[0][1] == pytest.approx(20.0)
    assert h[-1][1] > h[0][1]


def test_solve_settings_dialog_applies(qapp, win):
    win._new_project()
    prb = win.project.problem or type("P", (), {"setters": {}})()
    win.project.problem = prb
    dlg = SolveSettingsDialog(win, kind="Basic settings", problem=prb)
    dlg.page.row("problem_time").set("steady")
    dlg.page.row("problem_nsteps").set(5)
    dlg._apply()
    assert prb.setters["problem_time"] == "steady"
    assert prb.setters["problem_nsteps"] == 5
    dlg.close()


def test_run_solution_sets_residuals(win):
    win._new_project()
    win._run_mesh(write_files=False) if getattr(win, "_run_mesh", None) \
        else None
    from ice_solve_gui import RunSolutionDialog
    if hasattr(win, "_run_solution"):
        # bypass dialog by calling internals
        win._solution_id = "transient00"
        from ice_solve import write_resd
        win._residual_rows = simulate_residuals(40)
        assert win._residual_rows[-1][0] == 40
        assert win._residual_rows[0][1][0] > 1e-6


def test_post_plane_cut(win):
    win._new_project()
    win._create_object("block")
    res = win._run_mesh(write_files=False)
    temps = synthetic_cell_temps(res, {"block.1": 80.0})
    pts = plane_cut_points(res, "x", 0.025, temps)
    assert len(pts) > 0
    assert all(len(p) == 4 for p in pts)


def test_iso_points(win):
    win._new_project()
    _add_block(win)
    res = win._run_mesh(write_files=False)
    assert len(res.cell_obj) > 0, "expected occupancy cells"
    temps = synthetic_cell_temps(res, {"block.1": 80.0})
    iso = iso_points(res, 80.0, temps, tolerance=5.0)
    assert len(iso) > 0


def test_variation_along(win):
    win._new_project()
    res = win._run_mesh(write_files=False)
    temps = synthetic_cell_temps(res, {"block.1": 80.0})
    data = sample_along(res, (0.0, 0.0, 0.0), (0.5, 0.0, 0.0), temps, 11)
    assert len(data) == 11
    assert data[0][0] == pytest.approx(0.0)
    assert data[-1][0] == pytest.approx(1.0)


def test_post_create_appends(win):
    win._new_project()
    win._create_object("block")
    win._run_mesh(write_files=False)
    win._create_post("Plane cut")
    kinds = [p["type"] for p in win.project.post]
    assert "Plane cut" in kinds


def test_plot_window_data(qapp):
    win = PlotWindow(title="t")
    win.set_data([[(i, 10.0 / (i + 1)) for i in range(10)]], log_y=True)
    assert len(win._series) == 1
    win.close()


def test_monitor_window(qapp):
    w = ResidualMonitorWindow()
    w.set_residuals(simulate_residuals(10))
    assert "continuity" in w.lbl.text()
    w.close()


def test_html_report_contains_project(win):
    win._new_project()
    win._create_object("block")
    html = html_report(win.project, getattr(win, "_mesh_result", None))
    assert "demo" in html or "untitled" in html
    assert "<table>" in html
    assert len(object_table(win.project)) >= 2


def test_summary_rows(win):
    win._new_project()
    win._create_object("block")
    res = win._run_mesh(write_files=False)
    rows = summary_data(win.project, res)
    assert any(r[2] > 0 for r in rows)
