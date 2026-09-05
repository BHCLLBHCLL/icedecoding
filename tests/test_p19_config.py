# -*- coding: utf-8 -*-
"""P19-H1: .icepak_config variable-level compatible import/export."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ice_prefs import PrefsStore

CONFIG = """
set background_style solid
set obj_width 1.2
set ansi_device icepak_custom
set user_macro_dir {C:/ice/macros}
set min_elements_gap 5
set unknown_var_keep 42
set color_mode on
"""


def test_load_legacy_preserves_unknown_vars():
    s = PrefsStore()
    d = tempfile.mkdtemp(prefix="cfg_")
    p = os.path.join(d, ".icepak_config")
    open(p, "w", encoding="latin-1").write(CONFIG)
    s.load_legacy(p)
    assert s.get("background_style") == "solid"
    assert s.get("obj_width") == 1.2
    assert s.get("min_elements_gap") == 5
    assert s.get("ansi_device") == "icepak_custom"
    assert s.get("user_macro_dir") == "C:/ice/macros"
    assert s.get("unknown_var_keep") == 42
    assert s.get("color_mode") == 1


def test_legacy_roundtrip():
    s = PrefsStore()
    d = tempfile.mkdtemp(prefix="cfg_")
    p = os.path.join(d, ".icepak_config")
    open(p, "w", encoding="latin-1").write(CONFIG)
    s.load_legacy(p)
    text = s.legacy_text()
    assert "set unknown_var_keep 42" in text
    assert "set min_elements_gap 5" in text
    p2 = os.path.join(d, ".icepak_config.2")
    open(p2, "w", encoding="latin-1").write(text)
    s2 = PrefsStore()
    s2.load_legacy(p2)
    for k in ("background_style", "obj_width", "unknown_var_keep",
              "color_mode", "min_elements_gap"):
        assert s2.get(k) == s.get(k), (k, s2.get(k), s.get(k))


def test_save_legacy_writes_all():
    s = PrefsStore({"tmp_key": "abc"})
    d = tempfile.mkdtemp(prefix="cfg_")
    p = s.save_legacy(os.path.join(d, ".icepak_config"))
    assert os.path.exists(p)
    text = open(p, encoding="latin-1").read()
    assert 'set tmp_key "abc"' in text
    assert 'set background_style "gradient"' in text
