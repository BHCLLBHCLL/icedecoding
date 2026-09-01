# -*- coding: utf-8 -*-
"""P19-4b: real temperature -> report HTML section + plot histogram."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_report import histogram_svg, real_temp_section


def test_histogram_svg_wellformed():
    svg, hist, edges = histogram_svg([293.0, 295.0, 300.0, 305.0, 310.0],
                                     bins=4)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert len(hist) == 4
    assert sum(hist) == 5
    assert len(edges) == 5


def test_real_temp_section_html():
    import numpy as np
    c = np.array([[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.3, 0.3, 0.3]])
    t = np.array([293.15, 300.0, 310.0])
    s = real_temp_section(c, t)
    assert "<h2>Temperature field</h2>" in s
    assert "293.15" in s    # min
    assert "310.00" in s    # max
    assert "<svg" in s      # histogram
    assert "Cells" in s and "3" in s


def test_real_temp_section_no_centers():
    s = real_temp_section(None, [300.0, 301.0, 302.0])
    assert "<h2>Temperature field</h2>" in s
    assert "<svg" in s


def test_plotwindow_histogram(qapp2):
    from ice_solve_gui import PlotWindow
    w = PlotWindow(title="t")
    w.set_histogram([293.0, 295.0, 297.0, 299.0, 301.0, 303.0], bins=4,
                    title="Temperature")
    assert len(w._series) == 4
    assert w._xlabel == "Temperature (K)"
    w.close()


@pytest.fixture
def qapp2():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
