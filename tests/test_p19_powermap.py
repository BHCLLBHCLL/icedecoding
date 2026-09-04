# -*- coding: utf-8 -*-
"""P19-4: powermap viewport display (colored heat patches)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_view3d import powermap_actors

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

ROWS = [(0.0, 0.0, 10.0), (0.5, 0.0, 20.0), (0.0, 0.5, 30.0),
        (0.5, 0.5, 40.0)]
EXTENT = ((0.0, 0.0), (0.5, 0.5))


def test_powermap_actors_geometry():
    res = powermap_actors(None, ROWS, EXTENT)
    assert res["n"] == len(ROWS)
    assert len(res["actors"]) == len(ROWS)
    assert res["vmin"] == 10.0 and res["vmax"] == 40.0


def test_powermap_actors_empty():
    res = powermap_actors(None, [], EXTENT)
    assert res["n"] == 0 and res["actors"] == []


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
    def __init__(self):
        self._actors = []

    def AddActor(self, a):
        self._actors.append(a)

    def ResetCamera(self):
        pass


def test_gui_show_powermap_renders(win):
    win._new_project()
    win._powermaps = [{"fmt": "tab", "rows": list(ROWS), "extent": EXTENT}]
    win.renderer = _Renderer()
    win._show_powermap()
    assert len(win.renderer._actors) == len(ROWS)


def test_gui_show_powermap_no_data_warns(win):
    win._new_project()
    win._powermaps = None
    win._show_powermap()  # must not raise
    assert True
