# -*- coding: utf-8 -*-
"""P19-4: zoom-in modeling (local mesh refinement around picked objects)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_create import default_cabinet, default_object
from ice_refine import zoom_object_names, zoom_bounds, refine_mesh
from ice_mesh import generate_mesh
from icepak_parser.project import IcepakProject

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _model_with_two_blocks():
    proj = IcepakProject.empty("zoom")
    model = proj.model
    model.objects.append(default_cabinet())
    for name, lo, hi in (("blk.1", (0.1, 0.1, 0.0), (0.3, 0.3, 0.2)),
                         ("blk.2", (0.35, 0.1, 0.0), (0.45, 0.25, 0.2))):
        o = default_object("block", name)
        o.shape.setvals["point1"] = [str(v) for v in lo]
        o.shape.setvals["point2"] = [str(v) for v in hi]
        model.objects.append(o)
    return proj


def test_zoom_object_names_and_bounds():
    proj = _model_with_two_blocks()
    names = zoom_object_names(proj.model)
    assert "blk.1" in names and "blk.2" in names
    assert "cabinet" not in names
    b = zoom_bounds(proj.model, ["blk.1"])
    assert b is not None
    assert abs(b[0][0] - 0.1) < 1e-9 and abs(b[1][0] - 0.3) < 1e-9


def test_refine_zoom_only_object_has_fewer_cells():
    proj = _model_with_two_blocks()
    base = generate_mesh(proj.model, counts=(8, 8, 4), gtype="unif")
    full = refine_mesh(base, proj.model, min_spacing=0.02,
                       interior_ratio=2.0)
    zoom = refine_mesh(base, proj.model, min_spacing=0.02,
                       interior_ratio=2.0, zoom_names=["blk.1"])
    assert full.cell_count > zoom.cell_count


def test_refine_zoom_keeps_conformal_other_face():
    proj = _model_with_two_blocks()
    base = generate_mesh(proj.model, counts=(8, 8, 4), gtype="unif")
    zoom = refine_mesh(base, proj.model, min_spacing=0.02,
                       interior_ratio=2.0, zoom_names=["blk.1"])
    # blk.2 min x face at 0.35 must still be cut (conformal), even unlisted
    xs = zoom.axes[0]
    assert any(abs(v - 0.35) < 1e-9 for v in xs), xs


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


def test_gui_zoom_menu_present(win):
    m = win._menus["Model"]
    texts = [a.text() for a in m.actions()]
    assert "Zoom-in modeling" in texts


def test_gui_zoom_no_project_nyi(win, monkeypatch):
    calls = []
    monkeypatch.setattr(win, "_nyi", lambda t: calls.append(t))
    win.project = None
    win._zoom_in_modeling()
    assert calls == ["Zoom-in modeling"]
