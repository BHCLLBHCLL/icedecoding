# -*- coding: utf-8 -*-
"""P19-G1: mesh quality statistics (panel + metrics)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_mesh import generate_mesh, mesh_quality
from ice_create import default_cabinet
from icepak_parser.project import IcepakProject

import ice_gui
import ice_panes

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _mesh():
    proj = IcepakProject.empty("q")
    proj.model.objects.append(default_cabinet())
    return generate_mesh(proj.model, counts=(8, 8, 4), gtype="unif")


def test_mesh_quality_uniform_grid():
    q = mesh_quality(_mesh())
    assert q["orthogonality"] == 1.0
    assert q["skewness"] == 0.0
    # rectangular cabinet (0.35 x 0.55 x 0.25) with equal counts per axis
    # -> mild structured aspect ~1.57 (dy/dx), never below 1
    assert q["aspect_min"] >= 1.0
    assert q["aspect_max"] < 3.0
    assert q["cells"] == 8 * 8 * 4
    assert q["nodes"] == 9 * 9 * 5


def test_mesh_quality_nonuniform_aspect():
    import numpy as np
    from ice_mesh import MeshResult
    axes = (np.array([0.0, 0.1, 0.2, 0.3]),
            np.array([0.0, 0.05, 0.1]),
            np.array([0.0, 0.01, 0.02]))
    r = MeshResult(axes, {})
    q = mesh_quality(r)
    assert q["aspect_max"] > 1.0
    assert q["aspect_min"] >= 1.0


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


def test_gui_quality_no_mesh_warns(win):
    win._mesh_result = None
    win._show_mesh_quality()  # must not raise


def test_gui_quality_dialog(win, monkeypatch):
    win._new_project()
    win._mesh_result = _mesh()
    opened = []

    class FakeDlg(object):
        def __init__(self, parent=None, quality=None):
            opened.append(quality)

        def exec_(self):
            return 1

    monkeypatch.setattr(ice_panes, "MeshQualityDialog", FakeDlg)
    win._show_mesh_quality()
    assert opened and opened[0]["cells"] == 8 * 8 * 4


def test_model_menu_quality_present(win):
    m = win._menus["Model"]
    texts = [a.text() for a in m.actions()]
    assert "Mesh quality..." in texts
