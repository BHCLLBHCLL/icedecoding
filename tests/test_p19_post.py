# -*- coding: utf-8 -*-
"""Phase A1: real scalar-field iso / plane / extrema ops on the temp cloud."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from fluent_fdat import iso_band_data, plane_band_data, extrema_data

FDAT = os.path.join("D:", os.sep, "training", "icepak", "12-1datacenter",
                    "datacenter00.fdat")


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_iso_band_real():
    from fluent_fdat import real_temp_cloud_face
    r = real_temp_cloud_face(os.path.dirname(FDAT))
    assert r is not None
    c, t = r
    mid = float(t.mean())
    sel, pd = iso_band_data(c, t, mid)
    assert len(sel) > 0
    assert pd.GetNumberOfPoints() == len(sel)
    assert np.abs(sel[:, 3] - mid).max() <= 0.02 * (t.max() - t.min())


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_extrema_real():
    from fluent_fdat import real_temp_cloud_face
    c, t = real_temp_cloud_face(os.path.dirname(FDAT))
    sel, _ = extrema_data(c, t, k=10)
    assert len(sel) == 20
    assert sel[:, 3].max() <= t.max() + 1e-9
    assert sel[:, 3].min() >= t.min() - 1e-9


def test_plane_band_synthetic():
    c = np.array([[0.10, 0.1, 0.1], [0.101, 0.1, 0.1], [0.20, 0.2, 0.2]])
    t = np.array([295.0, 296.0, 300.0])
    sel, _ = plane_band_data(c, t, axis=0, offset=0.100, tol=0.002)
    assert len(sel) == 2



@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_real_velocity_cloud():
    from fluent_fdat import real_velocity_cloud, vector_glyph_cloud
    r = real_velocity_cloud(os.path.dirname(FDAT))
    assert r is not None
    centers, vecs = r
    assert len(centers) > 100000
    speed = np.linalg.norm(vecs, axis=1)
    assert speed.max() > 0.1            # real airflow
    glyph = vector_glyph_cloud(centers[:500], vecs[:500])
    assert glyph.GetNumberOfPoints() == 500
    assert glyph.GetPointData().GetVectors().GetNumberOfTuples() == 500



@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_real_line_sample_and_point():
    from fluent_fdat import real_line_sample, real_point_temp
    base = os.path.dirname(FDAT)
    r = real_line_sample(base, (0.2, 0.2, 0.2), (0.5, 0.3, 0.3), n=25)
    assert r is not None
    pts, temps = r
    assert len(pts) == 25 and len(temps) == 25
    assert 280.0 < temps.min() < temps.max() < 320.0
    pt = real_point_temp(base, (0.3, 0.2, 0.2))
    assert pt is not None and 280.0 < pt < 320.0
