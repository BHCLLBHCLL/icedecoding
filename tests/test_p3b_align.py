# -*- coding: utf-8 -*-
"""P3b alignment session tests."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_view3d import AlignSession

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


def test_align_session_two_picks_centers():
    s = AlignSession("align_centers")
    s.start("align_centers")
    a = ((0.0, 0.0, 0.0), (2.0, 2.0, 2.0))
    b = ((10.0, 4.0, 0.0), (12.0, 6.0, 2.0))
    action1, _ = s.pick(a)
    assert action1 == "pick_source"
    action2, result = s.pick(b)
    assert action2 == "applied"
    new_cx = (result[0][0] + result[1][0]) / 2.0
    assert abs(new_cx - 11.0) < 1e-9
    assert abs(result[1][0] - 12.0) < 1e-9


def test_align_session_move_face():
    s = AlignSession("align_face_move")
    s.start("align_face_move")
    a = ((0.0, 0.0, 0.0), (2.0, 2.0, 2.0))
    b = ((5.0, 5.0, 0.0), (7.0, 7.0, 2.0))
    s.pick(a)
    _, result = s.pick(b)
    # result: box a positioned so faces coincide on the nearest axes pair
    assert result is not None
    assert abs(result[1][0] - 5.0) < 1e-9


def test_gui_align_pick_updates_object(win):
    win._new_project()
    blk = win._create_object("block")
    blk2 = win._create_object("block")
    blk2.name = "block.2"
    from ice_create import translate_object
    translate_object(blk2, 0.5, 0.0, 0.0)
    win._start_align("align_centers")
    win._on_object_selected(blk)
    win._on_object_selected(blk2)
    assert win._dirty is True
    c1 = win._object_bounds(blk)
    cab = win.project.model.object_by_name("cabinet")
    # centers of blk and blk2 now align
    c2 = win._object_bounds(blk2)
    m1 = [(c1[0][i] + c1[1][i]) / 2 for i in range(3)]
    m2 = [(c2[0][i] + c2[1][i]) / 2 for i in range(3)]
    assert all(abs(m1[i] - m2[i]) < 1e-9 for i in range(3))


def test_align_session_reset():
    s = AlignSession()
    s.start("align_centers")
    assert s.state is not None
    s.reset()
    assert s.state is None
    action, _ = s.pick(((0, 0, 0), (1, 1, 1)))
    assert action == "ignored"