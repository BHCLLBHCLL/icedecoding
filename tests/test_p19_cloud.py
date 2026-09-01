
# -*- coding: utf-8 -*-
"""P19-4: real VTK temperature cloud (face-based cell centers + fdat)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fluent_fdat import (real_temp_cloud_face, temp_cloud_polys,
                         parse_cas_faces, parse_cas_nodes,
                         cell_centers_from_faces)

CAS = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                   "transient00.cas")
FDAT = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                    "transient00.fdat")


@pytest.mark.skipif(not os.path.exists(CAS), reason="oracle cas missing")
def test_face_cell_centers_match_cabinet():
    text = open(CAS, encoding="latin-1", errors="replace").read()
    nodes = parse_cas_nodes(text)
    assert len(nodes) == 62626
    centers = cell_centers_from_faces(text, nodes)
    assert len(centers) == 58908          # matches global cell count
    arr = [v for v in centers.values()]
    xs = [p[0] for p in arr]
    ys = [p[1] for p in arr]
    assert 0.03 < min(xs) < 0.36 and 0.09 < min(ys) < 0.57
    assert max(xs) < 0.36 and max(ys) < 0.57


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_real_temp_cloud_physically_plausible():
    r = real_temp_cloud_face(os.path.dirname(FDAT))
    assert r is not None
    centers, temps = r
    assert len(centers) == len(temps) > 1000
    assert 293.0 < temps.min() < temps.max() < 330.0
    assert centers[:, 0].min() >= 0.03 and centers[:, 0].max() <= 0.36


def test_temp_cloud_polys_builds():
    import numpy as np
    centers = np.array([[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.3, 0.3, 0.3]])
    temps = np.array([293.15, 300.0, 310.0])
    cloud, tmin, tmax = temp_cloud_polys(centers, temps)
    assert cloud.GetNumberOfPoints() == 3
    assert abs(tmin - 293.15) < 1e-9 and abs(tmax - 310.0) < 1e-9
