# -*- coding: utf-8 -*-
"""P19-4: true interpolated isosurface (vtkContourFilter triangle mesh)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import vtk
import numpy as np

from fluent_fdat import iso_surface_polys

pytestmark = pytest.mark.skipif(not vtk, reason="vtk not installed")


def _scattered_volume(n=6):
    """A 3D scattered cloud with temp = x (iso surfaces are planes)."""
    xs = np.linspace(0.0, 1.0, n)
    ys = np.linspace(0.0, 1.0, n)
    zs = np.linspace(0.0, 1.0, n)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
    centers = np.stack([gx, gy, gz], axis=-1).reshape(-1, 3)
    temps = centers[:, 0].copy() + 300.0  # 300..301 K, monotonic in x
    return centers, temps


def test_iso_surface_is_triangulated():
    centers, temps = _scattered_volume()
    surf = iso_surface_polys(centers, temps, 300.5, dims=24)
    assert surf is not None
    assert surf.GetNumberOfCells() > 0
    # every cell is a triangle (contour filter output), not a point/band
    for i in range(surf.GetNumberOfCells()):
        assert surf.GetCellType(i) == vtk.VTK_TRIANGLE, surf.GetCellType(i)


def test_iso_surface_has_scalar_and_positions():
    centers, temps = _scattered_volume()
    surf = iso_surface_polys(centers, temps, 300.5, dims=24)
    assert surf.GetNumberOfPoints() > 0
    # the surface must cross the true iso plane (temp=300.5 -> x~0.5).
    # (KD-fill may also add a thin shell at the domain occupancy boundary.)
    xs = [surf.GetPoint(i)[0] for i in range(surf.GetNumberOfPoints())]
    assert any(0.4 <= x <= 0.6 for x in xs), xs


def test_iso_surface_none_for_degenerate():
    centers = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    temps = np.array([300.0, 301.0])
    assert iso_surface_polys(centers, temps, 300.5) is None


def test_iso_surface_none_when_no_cells():
    centers, temps = _scattered_volume()
    assert iso_surface_polys(centers, temps, 305.0, dims=24) is None
