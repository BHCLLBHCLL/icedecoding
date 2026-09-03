# -*- coding: utf-8 -*-
"""P19-4: real transient History curve from monitor-point .out files."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import fluent_fdat
import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

HIST = """
"Convergence history of Static Temperature on p1 (in SI units)"
"Time Step" "flow-time etc.."
("Time Step" "flow-time" "Vertex Average Static Temperature")
0 0 293.1499938964844
1 1 296.6068420410156
2 2 298.0968322753906
3 3 299.1039428710938
"""


def _dir_with_hist():
    d = tempfile.mkdtemp(prefix="hist_")
    with open(os.path.join(d, "transient00.1.mon_pt_1_1_1.out"), "w",
              encoding="latin-1") as fh:
        fh.write(HIST)
    return d


def test_real_history_parses():
    d = _dir_with_hist()
    rows = fluent_fdat.real_history(d)
    assert rows is not None
    assert rows[0][0] == 0.0 and abs(rows[0][1] - 293.15) < 1e-3
    assert rows[1][0] == 1.0 and abs(rows[1][1] - 296.6068) < 1e-3
    assert len(rows) == 4


def test_real_history_none_when_empty():
    d = tempfile.mkdtemp(prefix="hist_")
    assert fluent_fdat.real_history(d) is None
    assert fluent_fdat.real_history(None) is None


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


def test_gui_history_uses_real(win, monkeypatch):
    win._new_project()
    d = _dir_with_hist()
    monkeypatch.setattr(win, "_job_base", lambda: d)
    pw = win._open_plot("History")
    assert getattr(pw, "_title", "").startswith("History (real)")
    assert len(pw._series[0]) == 4
    assert abs(pw._series[0][0][1] - 293.15) < 1e-3
    pw.close()


def test_gui_history_falls_back_synthetic(win, monkeypatch):
    win._new_project()
    d = tempfile.mkdtemp(prefix="hist_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    pw = win._open_plot("History")
    assert getattr(pw, "_title", "") == "History"
    pw.close()
