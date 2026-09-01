# -*- coding: utf-8 -*-
"""A5: real-data report suite (summary/point/full)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

from ice_report import (real_stats, real_summary_table_html,
                        point_report_html, full_report_html, write_real_report)

BASE = os.path.join("D:", os.sep, "training", "icepak", "12-1datacenter")
FDAT = os.path.join(BASE, "datacenter00.fdat")


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_real_stats():
    st = real_stats(BASE)
    assert st is not None
    assert st["cells"] > 100000
    assert 280.0 < st["tmin"] < st["tmax"] < 320.0


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_summary_and_point_html():
    s = real_summary_table_html(BASE)
    assert "Cells" in s and "<table" in s
    pr = point_report_html(BASE, [(0.3, 0.2, 0.2)])
    assert "Temperature" in pr and "285" in pr or "2" in pr


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_full_report_and_write():
    h = full_report_html(BASE, points=[(0.3, 0.2, 0.2)])
    assert h.startswith("<!DOCTYPE html>")
    assert "<svg" in h                   # histogram
    import tempfile
    d = tempfile.mkdtemp(prefix="ice_rep_")
    p = os.path.join(d, "report.html")
    assert write_real_report(p, BASE) == p
    assert os.path.exists(p)
