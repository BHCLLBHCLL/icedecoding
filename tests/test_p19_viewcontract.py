# -*- coding: utf-8 -*-
"""P19-2: 3D viewport visual contract - per-object opacity, display layers,
background, user views."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_gui import build_scene, SceneObject
from ice_view3d import make_display_actors
from ice_create import default_object
from icepak_parser.project import IcepakProject

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _model_with_opacity():
    proj = IcepakProject.empty("vpc")
    blk = default_object("block", "blk.1")
    blk.setvals = {"opacity": ["0.5"]}
    proj.model.objects.append(blk)
    return proj


def test_build_scene_respects_opacity():
    proj = _model_with_opacity()
    layer_on = {"block": True, "domain": True}
    objs = build_scene(proj.model, layer_on, wireframe=False)
    blk = [o for o in objs if o.name == "blk.1"]
    assert blk and blk[0].opacity == 0.5


def test_make_actor_applies_opacity(win):
    import vtk
    so = SceneObject("blk.1", "block", (0.5, 0.5, 0.5), vtk.vtkPolyData(),
                     ((0, 0, 0), (1, 1, 1)), opacity=0.5)
    win._shading = "solid"
    win.selected = None
    actor = win._make_actor(so)
    assert abs(actor.GetProperty().GetOpacity() - 0.5) < 1e-6


class _Renderer(object):
    def __init__(self):
        self._actors = []

    def AddActor(self, a):
        self._actors.append(a)


def test_display_actors_layers_present():
    r = _Renderer()
    actors = make_display_actors(r, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
    for name in ("grid", "origin", "rulers", "title", "date", "mesh"):
        assert name in actors, name
    assert len(r._actors) == len(actors)


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


def test_toggle_depthcue_no_crash(win):
    # enable_3d=False -> renderer is None; the guard makes this a no-op
    win._toggle_display_layer("Depthcue", True)
    assert win._display_state.get("Depthcue") is True


def test_set_background_solid_path(win):
    win._new_project()
    # renderer is None offscreen -> just sets the bg_style/colors, no crash
    win._set_background("solid", c1="#123456")
    assert win._bg_style == "solid"
    assert win._bg_color1 == "#123456"
