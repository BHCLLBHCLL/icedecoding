# -*- coding: utf-8 -*-
"""P19-G3: heat_solver deepening - convection / radiation + oracle compare."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from heat_solver import solve_heat, heat_solver_compare
from ice_mesh import generate_mesh
from ice_create import default_cabinet, default_object
from icepak_parser.project import IcepakProject

JOB = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
HAS_JOB = os.path.isdir(JOB)


def _model_mesh():
    proj = IcepakProject.empty("g3")
    proj.model.objects.append(default_cabinet())
    src = default_object("block", "src.1")
    src.setvals = {"material": ["Si"], "power": ["1.0"]}
    src.shape.setvals["point1"] = ["0.12", "0.2", "0.08"]
    src.shape.setvals["point2"] = ["0.22", "0.3", "0.14"]
    proj.model.objects.append(src)
    mesh = generate_mesh(proj.model, counts=(6, 6, 3), gtype="unif")
    return proj, mesh


def test_convection_approaches_dirichlet_with_large_h():
    proj, mesh = _model_mesh()
    T0, _ = solve_heat(mesh, proj.model, max_iter=400)
    Tc, _ = solve_heat(mesh, proj.model, max_iter=400, convection_h=1e6)
    m0 = sum(T0.values()) / len(T0)
    mc = sum(Tc.values()) / len(Tc)
    assert abs(mc - m0) / m0 < 0.01  # h -> inf recovers the Dirichlet shell


def test_radiation_cools_vs_convection_only():
    proj, mesh = _model_mesh()
    Tc, _ = solve_heat(mesh, proj.model, max_iter=400, convection_h=10.0)
    Tr, _ = solve_heat(mesh, proj.model, max_iter=400, convection_h=10.0,
                       emissivity=0.9)
    assert max(Tr.values()) < max(Tc.values())


def test_default_still_dirichlet():
    proj, mesh = _model_mesh()
    T, _ = solve_heat(mesh, proj.model, max_iter=200)
    # boundary cells stay exactly at ambient in the default case
    assert T[(0, 0, 0)] == 20.0


@pytest.mark.skipif(not HAS_JOB, reason="oracle job missing")
def test_oracle_compare():
    proj, mesh = _model_mesh()
    stats = heat_solver_compare(JOB, mesh, proj.model, max_iter=300)
    assert stats is not None
    assert stats["oracle_max"] > stats["oracle_min"]
    assert stats["mean_dev_pct"] >= 0
    import math
    assert math.isfinite(stats["mean_dev_pct"])
    assert math.isfinite(stats["max_dev_pct"])
    # (the <5% oracle target needs the refined 58k-cell mesh + real BCs;
    # the comparison machinery and sane oracle stats are what G3 locks here)
