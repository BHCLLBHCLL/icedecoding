# -*- coding: utf-8 -*-
"""P19-4: report suite - Overview wiring + network/EM/solar + Autotherm export."""
import json
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_report import full_report_html, write_real_report
from ice_create import default_object
from icepak_parser.project import IcepakProject
from ice_ecad import export_autotherm
from ice_actions import SLOT_MAP

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _project_with_sections():
    proj = IcepakProject.empty("rep")
    fan = default_object("fan", "fan.1")
    fan.setvals = {"flow": "0.05", "power": "6.0", "rpm": "3000"}
    net = default_object("network", "net.1")
    net.setvals = {"net_nodes": [json.dumps({"n1": [0.1, 0.1, 0.1]})],
                   "net_links": ["[]"]}
    em = default_object("source", "em_src")
    em.setvals = {"em_mapping": ["volumetric"], "power": ["2.5"],
                  "source_type": ["power"]}
    sol = default_object("block", "solar_blk")
    sol.setvals = {"solar_load": ["1.2"]}
    for o in (fan, net, em, sol):
        proj.model.objects.append(o)
    return proj


def test_full_report_html_includes_sections():
    proj = _project_with_sections()
    d = tempfile.mkdtemp(prefix="rep_")
    h = full_report_html(d, project=proj)
    for sec in ("Temperature summary", "Fan operating points",
                "Network block values", "EM mapping", "Solar loads"):
        assert sec in h, sec
    assert "fan.1" in h and "em_src" in h and "n1" in h


def test_full_report_sections_empty():
    proj = IcepakProject.empty("rep")
    d = tempfile.mkdtemp(prefix="rep_")
    h = full_report_html(d, project=proj)
    assert "No fans" in h
    assert "No network nodes" in h
    assert "No EM mapping applied" in h
    assert "No solar loads" in h


def test_write_real_report_with_project():
    proj = _project_with_sections()
    d = tempfile.mkdtemp(prefix="rep_")
    path = os.path.join(d, "full.html")
    write_real_report(path, d, project=proj)
    text = open(path, encoding="utf-8").read()
    assert "Fan operating points" in text and "EM mapping" in text


def test_export_autotherm_writes_thermal_model():
    proj = IcepakProject.empty("rep")
    src = default_object("source", "src.1")
    src.setvals = {"power": ["2.5"], "source_type": ["power"]}
    fan = default_object("fan", "fan.1")
    fan.setvals = {"flow": ["0.05"]}
    blk = default_object("block", "blk.1")
    for o in (src, fan, blk):
        proj.model.objects.append(o)
    d = tempfile.mkdtemp(prefix="at_")
    path = os.path.join(d, "m.autotherm")
    export_autotherm(path, proj.model)
    text = open(path, encoding="latin-1").read()
    assert "source src.1 2.5" in text
    assert "fan fan.1 0.05" in text
    assert "block blk.1" in text


def test_autotherm_slot():
    assert SLOT_MAP.get("Write Autotherm file") == "_export_autotherm"
