# -*- coding: utf-8 -*-
"""P19-H2/H4: annotations + image-export formats."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_prefs_gui import AnnotationsDialog

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_annotations_dialog_has_text_fields(qapp):
    dlg = AnnotationsDialog()
    keys = [r.key for r in dlg.page._rows]
    for k in ("annot_text", "annot_x", "annot_y", "annot_z"):
        assert k in keys, keys
    dlg.close()


@pytest.fixture
def win(qapp):
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    yield w
    w.close()


def test_apply_annotations_stores(win):
    win._apply_annotations({"annot_text": "Hot spot", "annot_x": 0.2,
                            "annot_y": 0.3, "annot_z": 0.05,
                            "title": "Proj"})
    assert win._annotations and win._annotations[0]["text"] == "Hot spot"
    assert win._annotations[0]["x"] == 0.2


def test_apply_annotations_empty(win):
    win._apply_annotations({"annot_text": "", "annot_x": 0.1,
                            "annot_y": 0.1, "annot_z": 0.1})
    assert win._annotations == []


def test_grab_view_writes_bmp_tiff(win):
    d = tempfile.mkdtemp(prefix="img_")
    for ext in (".bmp", ".tiff"):
        p = os.path.join(d, "view" + ext)
        win._grab_view(p)
        assert os.path.exists(p), ext
        assert os.path.getsize(p) > 0, ext
