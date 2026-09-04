# -*- coding: utf-8 -*-
"""P19-4: report suite - fan operating points section."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ice_report import (fan_operating_points, fan_operating_points_html,
                        html_report)
from ice_create import default_object
from icepak_parser.project import IcepakProject


def _project_with_fan():
    proj = IcepakProject.empty("rep")
    fan = default_object("fan", "fan.1")
    fan.setvals = {"flow": "0.05", "power": "6.0", "rpm": "3000"}
    proj.model.objects.append(fan)
    return proj


def test_fan_operating_points_rows():
    proj = _project_with_fan()
    rows = fan_operating_points(proj)
    assert len(rows) == 1
    assert rows[0][0] == "fan.1"
    assert rows[0][1] == "0.05" and rows[0][2] == "6.0"
    assert rows[0][3] == "3000"


def test_html_report_includes_fan_section():
    proj = _project_with_fan()
    h = html_report(proj)
    assert "Fan operating points" in h
    assert "fan.1" in h
    assert "3000" in h


def test_fan_section_no_fans():
    proj = IcepakProject.empty("rep")
    s = fan_operating_points_html(proj)
    assert "No fans" in s


def test_network_enabled_fan_only_in_report():
    proj = IcepakProject.empty("rep")
    # a block should NOT appear as a fan operating point
    b = default_object("block", "blk.1")
    proj.model.objects.append(b)
    assert fan_operating_points(proj) == []
