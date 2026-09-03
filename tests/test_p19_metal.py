# -*- coding: utf-8 -*-
"""P19-D6: Show metal fractions viewport display (per-layer copper actors)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_ecad import parse_icb, icb_metal_fractions
from ice_view3d import metal_fraction_actors

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

ICB = """[start board_outline]
0 0
50 0
50 40
0 40
[end]
[start layers]
TOP,Cu-Pure,top,0.035
BOTTOM,Cu-Pure,bottom,0.035
[end]
[start shapes]
TOP 5 5 25 25
TOP 30 10 45 30
BOTTOM 10 10 40 35
[end]"""


def test_parse_and_fractions():
    icb = parse_icb(ICB)
    assert len(icb["layers"]) == 2
    assert len(icb["shapes"]) == 3
    f = icb_metal_fractions(icb)
    assert abs(f["TOP"] - 0.35) < 1e-6
    assert abs(f["BOTTOM"] - 0.375) < 1e-6


def test_metal_fraction_actors_geometry():
    icb = parse_icb(ICB)
    # renderer=None -> only geometry/legend, no vtk render call
    res = metal_fraction_actors(None, icb)
    assert len(res["actors"]) == 3  # 2 TOP + 1 BOTTOM
    assert len(res["legend"]) == 2
    layers = [l[0] for l in res["legend"]]
    assert "TOP" in layers and "BOTTOM" in layers
    assert abs(res["legend"][0][2] - 0.35) < 1e-6


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


class _Renderer(object):
    """Minimal recording renderer for offscreen tests (enable_3d=False)."""
    def __init__(self):
        self._actors = []

    def AddActor(self, a):
        self._actors.append(a)

    def ResetCamera(self):
        pass

    def GetActors(self):
        return _ActorList(self._actors)


class _ActorList(object):
    def __init__(self, lst):
        self._lst = lst

    def GetNumberOfItems(self):
        return len(self._lst)


def test_gui_show_metal_fractions_renders(win):
    win._new_project()
    win._icb_text = ICB
    win.renderer = _Renderer()
    win._show_metal_fractions()
    assert len(win.renderer._actors) == 3  # 2 TOP + 1 BOTTOM actors added


def test_gui_show_metal_fractions_no_data_warns(win):
    win._new_project()
    win._icb_text = None
    win._show_metal_fractions()  # must not raise
    assert True
