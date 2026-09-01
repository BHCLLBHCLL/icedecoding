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
