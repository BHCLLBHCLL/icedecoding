# -*- coding: utf-8 -*-
"""P19-4: Post -> Postprocessing units command wiring."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_actions import SLOT_MAP
from ice_panes import SOLUTION_UNITS_KEYS

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def test_units_slot_resolves():
    assert SLOT_MAP.get("Postprocessing units") == "_show_postprocessing_units"


def test_solution_units_keys():
    assert "problem_temp_units" in SOLUTION_UNITS_KEYS
    assert "problem_pressure_units" in SOLUTION_UNITS_KEYS


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


def test_gui_show_units(win, monkeypatch):
    calls = []
    def rec(title, keys):
        calls.append((title, keys))
    monkeypatch.setattr(win, "_show_problem_keys", rec)
    win._show_postprocessing_units()
    assert calls == [("Postprocessing units", SOLUTION_UNITS_KEYS)]
