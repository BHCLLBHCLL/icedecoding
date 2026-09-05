# -*- coding: utf-8 -*-
"""P19-I2: screenshot regression - structural snapshot (offscreen-safe)."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
import tools.screenshot_regression as S

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


def test_structural_snapshot_objects(win):
    win._new_project()
    from ice_create import default_cabinet, default_object
    win.project.model.objects.append(default_cabinet())
    blk = default_object("block", "blk.1")
    win.project.model.objects.append(blk)
    win._refresh()
    rec = S.capture(win, tempfile.mkdtemp(prefix="scr_"), "objects",
                    grab=False)
    assert rec["objects"] >= 2
    assert rec["title"].startswith("ANSYS Icepak")
    assert rec["shading"] in ("solid", "wire", "solid/wire", "hidden line",
                              "selected_solid")
    assert "error" not in rec


def test_structural_snapshot_mesh(win):
    win._new_project()
    from ice_create import default_cabinet
    from ice_mesh import generate_mesh
    win.project.model.objects.append(default_cabinet())
    win._mesh_result = generate_mesh(win.project.model, counts=(6, 6, 3))
    win._refresh()
    rec = S.capture(win, tempfile.mkdtemp(prefix="scr_"), "mesh", grab=False)
    assert rec["mesh_cells"] == 6 * 6 * 3
    assert "error" not in rec


def test_scenario_builder(win):
    w = S.build_scenario("objects")
    try:
        assert len(list(w.project.model._all_objects())) >= 2
    finally:
        w.close()
