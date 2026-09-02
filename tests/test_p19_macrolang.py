# -*- coding: utf-8 -*-
"""Phase D2/D3: macro-library port + i18n language keys."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ice_macros import scan_macro_library, build_library_part,     parse_macro_params
from icepak_parser.project import IcepakProject
import ice_i18n


def test_macro_library_scan_count():
    ms = scan_macro_library()
    assert len(ms) > 100          # full library corpus
    libs = {m["library"] for m in ms}
    assert "BGA_library" in libs
    # every macro carries params
    assert all(m["params"] for m in ms[:50])


def test_macro_library_build_part():
    ms = scan_macro_library()
    proj = IcepakProject.empty("mlib")
    o = build_library_part(proj.model, ms[0])
    assert o.kind == "package"
    assert len(list(proj.model._all_objects())) == 1
    assert "ball_pitch" in o.setvals


def test_parse_macro_params():
    p = parse_macro_params("ball_num1  12\r\ndie_dim1  3.9\r\n")
    assert p["ball_num1"] == 12
    assert p["die_dim1"] == 3.9


def test_i18n_language_keys():
    keys = ice_i18n.language_keys()
    assert len(keys) > 50
    assert "Main" in keys
    # tr() returns a string (EN identity at minimum)
    assert isinstance(ice_i18n.tr("Main"), str)
