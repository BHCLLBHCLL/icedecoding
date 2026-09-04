# -*- coding: utf-8 -*-
"""P19-4: remaining real curves - network temperature / 3D variation."""
import json
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import fluent_fdat
from ice_create import default_object
from icepak_parser.project import IcepakProject

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _project_with_network():
    proj = IcepakProject.empty("net")
    o = default_object("network", "net.1")
    o.setvals = {"net_nodes": [json.dumps(
                     {"n1": [0.1, 0.1, 0.1], "n2": [0.2, 0.2, 0.2]})],
                 "net_links": ["[]"]}
    proj.model.objects.append(o)
    return proj


def test_network_nodes_collects():
    proj = _project_with_network()
    nodes = fluent_fdat.network_nodes(proj.model)
    assert ("n1", (0.1, 0.1, 0.1)) in nodes
    assert ("n2", (0.2, 0.2, 0.2)) in nodes


def test_network_temperatures_none_without_real_data():
    proj = _project_with_network()
    d = tempfile.mkdtemp(prefix="net_")
    assert fluent_fdat.network_temperatures(d, proj.model) is None


def test_real_3d_variation_distances(monkeypatch):
    import numpy as np
    pts = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)])
    temps = np.array([300.0, 305.0, 310.0])
    monkeypatch.setattr(fluent_fdat, "real_line_sample",
                        lambda d, p0, p1, n=41: (pts, temps))
    out = fluent_fdat.real_3d_variation("x", (0, 0, 0), (2, 0, 0), 3)
    assert len(out) == 3
    assert abs(out[0][0] - 0.0) < 1e-9
    assert abs(out[1][0] - 1.0) < 1e-9
    assert abs(out[2][0] - 2.0) < 1e-9
    assert out[1][1] == 305.0


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


def test_gui_plot_3d_variation_real(win, monkeypatch):
    win._new_project()
    d = tempfile.mkdtemp(prefix="curve_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    monkeypatch.setattr(fluent_fdat, "real_3d_variation",
                        lambda base, p0, p1, n=41:
                        [(0.0, 300.0), (1.0, 305.0), (2.0, 310.0)])
    pw = win._open_plot("3D Variation")
    assert getattr(pw, "_title", "").startswith("3D Variation (real)")
    assert len(pw._series[0]) == 3
    pw.close()


def test_gui_plot_network_temperature_real(win, monkeypatch):
    win._new_project()
    d = tempfile.mkdtemp(prefix="curve_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    monkeypatch.setattr(fluent_fdat, "network_temperatures",
                        lambda base, model: [("n1", 300.0), ("n2", 310.0)])
    pw = win._open_plot("Network temperature")
    assert getattr(pw, "_title", "").startswith("Network temperature (real)")
    assert len(pw._series[0]) == 2
    pw.close()


def test_gui_plot_3d_variation_falls_back_synthetic(win, monkeypatch):
    win._new_project()
    d = tempfile.mkdtemp(prefix="curve_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    monkeypatch.setattr(fluent_fdat, "real_3d_variation", lambda *a, **k: None)
    pw = win._open_plot("3D Variation")
    assert getattr(pw, "_title", "") == "3D Variation"
    pw.close()
