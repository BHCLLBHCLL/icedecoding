# -*- coding: utf-8 -*-
"""P5 mesh pipeline tests: params table, axes formulas, occupancy, dialog,
job writers, gui integration."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_mesh import (
    PARAMS_DEFAULTS, geometric_coords, build_axes, classify_cells,
    generate_mesh, MeshResult, write_grid_params, parse_grid_params,
    write_grid_output_ascii, class_of_params_from_tcl,
)

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

TCL_SNIPPET = """
set grid_gcount_i 10
set grid_gcount_j 10
set grid_gcount_k 10
set grid_gtype unif
set grid_max_elements 25000000
set grid_hdm_feature_angle 40
set grid_hdm_mlm_auto_levels 2
set grid_hdm_icechip 1
set grid_sep_x 0.001
"""


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


def test_params_defaults_spot():
    assert PARAMS_DEFAULTS["grid_gcount_i"] == 10
    assert PARAMS_DEFAULTS["grid_gtype"] == "unif"
    assert PARAMS_DEFAULTS["grid_max_elements"] == 25000000
    assert PARAMS_DEFAULTS["grid_hdm_feature_angle"] == 40
    assert PARAMS_DEFAULTS["grid_hdm_mlm_auto_levels"] == 2
    assert PARAMS_DEFAULTS["grid_hdm_icechip"] == 1
    assert PARAMS_DEFAULTS["bad_face_align"] == 0.05


def test_class_of_params_from_tcl():
    d = class_of_params_from_tcl(TCL_SNIPPET)
    assert d["grid_gcount_i"] == 10
    assert d["grid_hdm_feature_angle"] == 40
    assert d["grid_hdm_icechip"] == 1


def test_geometric_coords_uniform():
    coords = geometric_coords(1.0, 10, 1.0)
    assert len(coords) == 11
    assert abs(coords[-1] - 1.0) < 1e-12
    steps = [coords[i + 1] - coords[i] for i in range(10)]
    for s in steps:
        assert abs(s - 0.1) < 1e-12


def test_geometric_coords_ratio():
    coords = geometric_coords(1.0, 5, 2.0)
    assert len(coords) == 6
    assert abs(coords[-1] - 1.0) < 1e-12
    steps = [coords[i + 1] - coords[i] for i in range(5)]
    assert steps[1] > steps[0]          # monotonic growth
    g0 = 1.0 * (1 - 2.0) / (1 - 2.0 ** 5)
    assert abs(steps[0] - g0) < 1e-12   # golden: g0 = L*(1-q)/(1-q**n)


def test_build_axes_bounds():
    axes = build_axes((0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (2, 4, 6))
    assert axes[0][-1] == pytest.approx(1.0)
    assert axes[1][-1] == pytest.approx(2.0)
    assert axes[2][-1] == pytest.approx(3.0)


def test_classify_cells_center_block():
    axes = [list(range(11)) for _ in range(3)]
    objs = [("block.1", ((3.0, 3.0, 3.0), (6.0, 6.0, 6.0)))]
    cell_obj = classify_cells(axes, objs)
    assert len(cell_obj) == 3 * 3 * 3
    assert all(v == "block.1" for v in cell_obj.values())


def test_autohax_dialog_six_tabs(qapp):
    from ice_panes import AutoHexDialog
    dlg = AutoHexDialog()
    assert [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())] == \
        list(AutoHexDialog.TABS)
    basic = dlg.tabs.widget(0)
    assert basic.row("grid_gtype").get() == "unif"
    dlg.close()


def test_generate_mesh_result(win):
    win._new_project()
    win._create_object("block")
    res = win._run_mesh(write_files=False)
    assert res is not None
    assert res.cell_count == pytest.approx(10 * 10 * 10)
    assert win._mesh_result is res
    assert res.counts_by_object().get("block.1", 0) > 0


def test_grid_params_roundtrip(win, monkeypatch):
    import tempfile
    d = tempfile.mkdtemp(prefix="ice_gp_")
    win._new_project()
    win._create_object("block")
    pth = os.path.join(d, "grid_params")
    write_grid_params(pth, win.project.model)
    entries = parse_grid_params(pth)
    assert len(entries) >= 2
    dom = [e for e in entries if e["type"] == "domain"][0]
    assert dom["lo"][0] == pytest.approx(0.0)
    assert dom["hi"][2] == pytest.approx(0.3)


def test_grid_output_ascii_counts(win, monkeypatch):
    import tempfile
    d = tempfile.mkdtemp(prefix="ice_go_")
    win._new_project()
    res = win._run_mesh(write_files=False)
    assert res is not None
    pth = os.path.join(d, "grid_output")
    write_grid_output_ascii(pth, res)
    txt = open(pth, encoding="latin-1").read()
    assert "(10 (0 1 %d 0))" % res.node_count in txt
    assert "(12 (0 1 %d 0))" % res.cell_count in txt
