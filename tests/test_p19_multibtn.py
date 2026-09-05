# -*- coding: utf-8 -*-
"""P19-F4: multi-command toolbar buttons (golden 'multiple' scalars)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

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


def test_alignment_toolbar_multi_buttons(win):
    from PyQt5.QtWidgets import QToolButton
    tb = win._toolbars["Alignment"]
    btns = [b for b in tb.findChildren(QToolButton)
            if b.menu() is not None]
    assert len(btns) == 3  # the three golden 'multiple' scalars
    expected = [
        ("Align and morph faces", "Align faces - move only"),
        ("Align and morph edges", "Align edges - move only"),
        ("Align and morph vertices", "Align vertices - move only"),
    ]
    for btn, (a, b) in zip(btns, expected):
        texts = [x.text() for x in btn.menu().actions()]
        assert texts == [a, b], texts
        assert btn.defaultAction().text() == a


def test_golden_toolbar_actions_unchanged(win):
    # the multi buttons are widgets, not QActions: the golden action lists
    # per toolbar remain intact
    for name in win._toolbars:
        actions = [a.text() for a in win._toolbars[name].actions()]
        assert "multiple" not in actions
