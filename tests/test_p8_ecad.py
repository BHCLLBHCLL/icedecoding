# -*- coding: utf-8 -*-
"""P8 ECAD tests: ECXML roundtrip, IDF, networks, JEDEC, powermaps,
EM mapping, ICB metal fractions."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_ecad import (
    parse_ecxml, parts_to_ecxml, register_components, parse_idf,
    import_idf_path, export_idf, parse_networks, register_networks,
    export_networks, parse_jedec, register_jedec, export_jedec,
    parse_powermap, apply_em_mapping, parse_icb, icb_metal_fractions,
    write_ecxml,
)

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

ECXML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<ECXML version="1.0">
  <Component name="QFP48" kind="two_resistor" manufacturer="Vendor"
             part_number="QFP-48">
    <Location x="0" y="0" z="0" unit="mm"/>
    <Size x="10" y="10" z="1.5" unit="mm"/>
    <Thermal>
      <Rjc unit="K/W">1.0</Rjc>
      <Rjb unit="K/W">5.0</Rjb>
      <Power unit="W">1.0</Power>
    </Thermal>
  </Component>
</ECXML>"""

IDF_SAMPLE = """IDF v3
BOARD
OUTLINE
0 0 0
0 0 50.0
0 0 50.0 40.0
0 0 0 40.0
END BOARD
COMPONENTS
R1, RESISTOR, TOP, 10.0, 10.0, 0
U1, IC, TOP, 25.0, 20.0, 90
END COMPONENTS
"""

NETWORK_SAMPLE = """# name=net1
node ns 0 0 0
node nb 0.02 0 0
link ns nb 2.5 0.0012
"""

JEDEC_SAMPLE = """[PACKAGE]
NAME=QFP48
WIDTH=10
LENGTH=10
[DIE]
SIZE=5
"""

ICB_SAMPLE = """[start board_outline]
0 0
50 0
50 40
0 40
[end board_outline]
[start layers]
L1 TOP
L2 BOTTOM
[end layers]
[start shapes]
L1 0 0 25 40
L1 25 0 50 40
L2 0 0 50 10
[end shapes]
[start vias]
via 25 20 0.3
[end vias]
[start nets]
net GND
[end nets]
"""


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


def test_ecxml_parse_sample():
    comps = parse_ecxml(ECXML_SAMPLE)
    assert len(comps) == 1
    c = comps[0]
    assert c["name"] == "QFP48"
    assert c["kind"] == "two_resistor"
    assert c["rjc"] == pytest.approx(1.0)
    assert c["rjb"] == pytest.approx(5.0)
    assert c["package_power"] == pytest.approx(1.0)
    assert c["size"] == pytest.approx((10.0, 10.0, 1.5))


def test_ecxml_register_and_export(win):
    win._new_project()
    comps = parse_ecxml(ECXML_SAMPLE)
    names = register_components(win.project.model, comps)
    assert names == ["QFP48"]
    o = win.project.model.object_by_name("QFP48")
    assert o.kind == "network"
    assert o.setvals["rjc"][0] == "1"
    txt = parts_to_ecxml(win.project.model)
    back = parse_ecxml(txt)
    assert back[0]["name"] == "QFP48"
    assert back[0]["kind"] == "two_resistor"


def test_ecxml_registered_units_mm_to_m(win):
    win._new_project()
    register_components(win.project.model, parse_ecxml(ECXML_SAMPLE))
    o = win.project.model.object_by_name("QFP48")
    pt1 = o.shape.setvals["point1"]
    pt2 = o.shape.setvals["point2"]
    assert (float(pt2[0]) - float(pt1[0])) == pytest.approx(0.010)
    assert (float(pt2[2]) - float(pt1[2])) == pytest.approx(0.0015)


def test_idf_parse_and_import(win):
    data = parse_idf(IDF_SAMPLE)
    assert bool(data["board"])
    assert len(data["components"]) == 2
    win._new_project()
    created, _ = import_idf_path(_tmp("board.idf", IDF_SAMPLE),
                                 win.project.model)
    names = [o.name for o in created]
    assert "pcb_ecad" in names
    pcb = win.project.model.object_by_name("pcb_ecad")
    assert pcb.kind == "pcb"
    assert any(n.startswith("pkg_R1") for n in names)
    assert any(n.startswith("pkg_U1") for n in names)


def test_idf_export(win):
    win._new_project()
    import_idf_path(_tmp("b.idf", IDF_SAMPLE), win.project.model)
    path = os.path.join(_tmpd(), "out.idf")
    export_idf(path, win.project.model)
    txt = open(path, encoding="latin-1").read()
    assert "BOARD" in txt and "COMPONENTS" in txt
    assert "pkg_R1" in txt and "pkg_U1" in txt


def test_networks_roundtrip(win):
    win._new_project()
    data = parse_networks(NETWORK_SAMPLE)
    assert "ns" in data["nodes"] and len(data["links"]) == 1
    obj = register_networks(win.project.model, "net1", data)
    assert obj.kind == "network"
    path = os.path.join(_tmpd(), "n.txt")
    export_networks(path, win.project.model)
    txt = open(path, encoding="latin-1").read()
    assert "node ns" in txt and "link ns nb" in txt


def test_jedec_parse_register(win):
    entries = parse_jedec(JEDEC_SAMPLE)
    assert ("PACKAGE", "WIDTH", "10") in entries
    win._new_project()
    obj = register_jedec(win.project.model, entries)
    assert obj.kind == "package"
    assert "ptd_width" in obj.setvals


def test_powermap_formats():
    d = _tmpd()
    tab = os.path.join(d, "t.txt")
    open(tab, "w", encoding="latin-1").write("0.0 0.0 1.2\n0.5 0.0 2.4\n")
    rows = parse_powermap(tab, "tab")
    assert len(rows) == 2 and rows[0][2] == pytest.approx(1.2)
    i2p = os.path.join(d, "t.i2p")
    open(i2p, "w", encoding="latin-1").write(
        "POWERSET 1\nPOINT 1 2 3.5\n")
    assert parse_powermap(i2p, "i2p")[0][2] == pytest.approx(3.5)
    ctm = os.path.join(d, "t.ctm")
    open(ctm, "w", encoding="latin-1").write("HEADER=x\n0.5 1.5 2.0\n")
    assert parse_powermap(ctm, "ctm")[0][0] == pytest.approx(0.5)
    sen = os.path.join(d, "t.csv")
    open(sen, "w", encoding="latin-1").write("1.0,2.0,75.5\n")
    assert parse_powermap(sen, "sentinel")[0][2] == pytest.approx(75.5)
    ap = os.path.join(d, "t.aps")
    open(ap, "w", encoding="latin-1").write("1.0;2.0;9.9\n")
    assert parse_powermap(ap, "apache")[0][2] == pytest.approx(9.9)


def test_em_mapping(win):
    win._new_project()
    losses = {"chip.1": 5.0}
    created = apply_em_mapping(win.project.model, losses, "volumetric")
    assert len(created) == 1
    assert created[0].setvals["power"][0] == "5"


def test_icb_parse_and_metal_fractions():
    icb = parse_icb(ICB_SAMPLE)
    assert len(icb["board_outline"]) == 4
    assert len(icb["layers"]) == 2
    fracs = icb_metal_fractions(icb)
    # L1 shapes cover full 50x40 -> 1.0 ; L2 shape 50x10 -> 0.25
    assert fracs["L1"] == pytest.approx(1.0)
    assert fracs["L2"] == pytest.approx(0.25)


def _tmp(name, text):
    d = _tmpd()
    p = os.path.join(d, name)
    with open(p, "w", encoding="latin-1") as fh:
        fh.write(text)
    return p


def _tmpd():
    d = tempfile.mkdtemp(prefix="ice_ecad_")
    return d
