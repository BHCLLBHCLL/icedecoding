# -*- coding: utf-8 -*-
"""P19 coverage gates: 18-type editor property specs + user-views file IO."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_editors import PROPERTY_SPECS, spec_for

import ice_gui


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


ALL_KINDS = [
    "block", "plate", "source", "fan", "blower", "opening", "ventres",
    "grille", "wall", "resistance", "package", "heatsink", "pcb",
    "enclosure", "network", "assembly", "material", "periodic", "domain",
]


def test_property_specs_cover_all_18_types():
    missing = [k for k in ALL_KINDS if k not in PROPERTY_SPECS]
    assert missing == [], missing
    for k in ALL_KINDS:
        assert len(spec_for(k)) >= 1, k


def test_property_specs_wellformed():
    for k, spec in PROPERTY_SPECS.items():
        for item in spec:
            key, label, widget = item[0], item[1], item[2]
            assert key and label
            assert widget in ("text", "combo", "spin", "int", "check",
                              "label"), (k, item)
            if widget == "combo":
                assert item[3], (k, item)   # options required


def test_user_views_file_roundtrip(win):
    import json
    import tempfile
    win._user_views = [{"name": "iso", "pos": [1, -1, 1],
                        "focal": [0, 0, 0], "viewup": [0, 0, 1]},
                       {"name": "top", "pos": [0, 0, 1],
                        "focal": [0, 0, 0], "viewup": [0, 1, 0]}]
    d = tempfile.mkdtemp(prefix="ice_uv_")
    p = os.path.join(d, "uv.json")
    assert win._write_user_views(p) == p
    win._user_views = []
    win._read_user_views(p)
    assert len(win._user_views) == 2
    assert win._user_views[0]["name"] == "iso"
