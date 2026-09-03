# -*- coding: utf-8 -*-
"""P19-4 fine point: real-temperature coloured iso/plane/extrema clouds."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fluent_fdat import temp_cloud_polys, iso_band_data
import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _cloud():
    import numpy as np
    pts = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
                    (0.5, 0.5, 0.5)])
    temps = np.array([290.0, 300.0, 310.0, 305.0])
    return temp_cloud_polys(pts, temps)


def test_cloud_has_rgba_temperature_scalars():
    cloud, tmin, tmax = _cloud()
    sc = cloud.GetPointData().GetScalars()
    assert sc.GetName() == "Temperature"
    assert sc.GetNumberOfComponents() == 4
    assert tmin == 290.0 and tmax == 310.0


def test_temp_colored_actor_direct_scalars():
    import vtk
    cloud, _, _ = _cloud()
    actor = ice_gui._temp_colored_actor(cloud, 0.0028)
    mapper = actor.GetMapper()
    assert mapper.GetScalarVisibility() == 1
    assert mapper.GetColorMode() == vtk.VTK_COLOR_MODE_DIRECT_SCALARS
    # the old code forced uniform red; the temperature actor must not
    col = actor.GetProperty().GetColor()
    assert abs(col[0] - 0.9) > 1e-6 or abs(col[1] - 0.2) > 1e-6 or abs(col[2] - 0.2) > 1e-6, col


def test_iso_band_keeps_temperature_scalars():
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
           (0.5, 0.5, 0.5), (0.2, 0.2, 0.2)]
    temps = [290.0, 300.0, 310.0, 305.0, 295.0]
    import numpy as np
    centers = np.array(pts); tt = np.array(temps)
    sel, polydata = iso_band_data(centers, tt, 300.0)
    assert sel.shape[1] == 4  # x,y,z,temp
    sc = polydata.GetPointData().GetScalars()
    assert sc.GetName() == "Temperature"
