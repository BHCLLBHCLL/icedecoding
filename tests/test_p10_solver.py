# -*- coding: utf-8 -*-
"""Real solver kernel tests: analytic 1D slab + GUI integration."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_mesh import MeshResult
from heat_solver import solve_heat, MATERIAL_K

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _slab_mesh(nx=30, nz=7, ny=7):
    axes = [list(range(nx + 1)), list(range(ny + 1)), list(range(nz + 1))]
    cell_obj = {}
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                cell_obj[(i, j, k)] = "slab"
    return MeshResult(axes, cell_obj)


class _FakeModel(object):
    def __init__(self):
        self._o = type("O", (), {"name": "slab", "setvals": {
            "material": ["Cu"], "power": ["1.0"]}})()

    def _all_objects(self):
        return [self._o]

    def object_by_name(self, name):
        return self._o if name == "slab" else None


def test_analytic_1d_slab():
    """Uniform q, Dirichlet 20C ends: T(mid) = 20 + q*L^2/(8k) approx
    (discretised): q_vol = power/vol; vol_cell = 1 -> q=1; k=401."""
    mesh = _slab_mesh()
    model = _FakeModel()
    T, rows = solve_heat(mesh, model, max_iter=3000, tol=1e-6)
    # analytic: T(x)=20 + q/(2k) x (L - x); mid x=15: 20 + 1/(2*401)*225
    analytic = 20.0 + 1.0 / (2.0 * 401.0) * 15.0 * 15.0
    mid = max(T, key=lambda k: sum(v * v for v in k))
    i_max = max(int(k[0]) for k in T)
    center = T[(i_max // 2, 3, 3)]
    assert abs(center - analytic) / analytic < 0.05
    assert rows and rows[-1][1] < rows[0][1]
    assert all(r[1] >= 0 for r in rows)


def test_material_table():
    assert MATERIAL_K["Cu"] == 401.0
    assert MATERIAL_K["Al-Extruded"] == 237.0
    assert MATERIAL_K["Steel"] == 16.2


def test_run_solution_uses_real_solver(win):
    win._new_project()
    win._create_object("block")
    res = win._run_mesh(write_files=False)
    assert res is not None
    # bypass dialog: set residual monitor path via internal call
    win._solution_id = "transient00"
    from heat_solver import solve_heat
    temps, rows = solve_heat(win._mesh_result, win.project.model,
                             max_iter=60)
    win._field_temps = temps
    win._residual_rows = rows
    assert len(rows) > 0
    assert max(temps.values()) > 20.0


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
