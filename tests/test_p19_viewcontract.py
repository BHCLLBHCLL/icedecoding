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


def test_kind_visuals_defaults():
    v = ice_gui.kind_visuals("block")
    assert v["opacity"] == 1.0
    assert v["width"] == 1.1
    assert len(v["color"]) == 3


def test_make_actor_uses_visuals(win):
    import vtk
    ice_gui.KIND_VISUALS["block"] = {"color": (1.0, 0.0, 0.0),
                                     "width": 3.0, "opacity": 0.8}
    so = SceneObject("blk.1", "block", (0.5, 0.5, 0.5), vtk.vtkPolyData(),
                     ((0, 0, 0), (1, 1, 1)), opacity=1.0)
    win._shading = "wire"
    win.selected = None
    actor = win._make_actor(so)
    assert abs(actor.GetProperty().GetOpacity() - 0.8) < 1e-6
    assert abs(actor.GetProperty().GetLineWidth() - 3.0) < 1e-6
    col = actor.GetProperty().GetColor()
    assert abs(col[0] - 1.0) < 1e-6 and abs(col[1]) < 1e-6
    ice_gui.KIND_VISUALS.pop("block", None)


def test_kind_visuals_dialog_values(qapp):
    from ice_panes import KindVisualsDialog
    dlg = KindVisualsDialog(parent=None, kinds=["block", "fan"],
                            visuals={"block": {"color": (1, 0, 0),
                                              "width": 2.5,
                                              "opacity": 0.5}})
    vals = dlg.values()
    assert vals["block"]["width"] == 2.5
    assert vals["block"]["opacity"] == 0.5
    assert abs(vals["block"]["color"][0] - 1.0) < 1e-6
    assert "fan" in vals  # default-filled row
    # edit a cell -> reflected
    dlg.table.item(1, 1).setText("2.0")
    vals2 = dlg.values()
    assert vals2["fan"]["width"] == 2.0
    dlg.close()


def test_construction_actors_present_and_hidden():
    r = _Renderer()
    actors = make_display_actors(r, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
    assert "construction" in actors
    assert "construction_points" in actors
    assert actors["construction"].GetVisibility() == 0
    assert actors["construction_points"].GetVisibility() == 0


def test_status_segments_update(win):
    win._new_project()
    assert len(win._status_segments) == 4
    win.selected = "blk.1"
    win._update_status_segments()
    assert win._status_segments[0].text() == "Sel: blk.1"
    assert win._status_segments[1].text().startswith("Shading:")
    assert win._status_segments[2].text() == "Units: SI"
    assert win._status_segments[3].text().startswith("Objects:")


def test_view_menu_per_type_visuals_present(win):
    m = win._menus["View"]
    texts = [a.text() for a in m.actions()]
    assert "Per-type visuals..." in texts
