# -*- coding: utf-8 -*-
"""A4: solve settings field-table coverage gate."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ice_solve import BASIC_FIELDS, ADVANCED_FIELDS, PARALLEL_FIELDS,     SOLVE_FIELDS


def test_solve_basic_fields_complete():
    keys = [f[0] for f in BASIC_FIELDS]
    for expected in ("problem_time", "problem_temp", "problem_pressure",
                     "problem_gravity", "problem_nsteps", "problem_turbulent"):
        assert expected in keys


def test_solve_advanced_and_parallel():
    ak = [f[0] for f in ADVANCED_FIELDS]
    pk = [f[0] for f in PARALLEL_FIELDS]
    assert "problem_ptol" in ak or "problem_turb_prandtl" in ak
    assert "solve_parallel_processes" in pk
    assert "solve_id" in SOLVE_FIELDS


def test_solve_specs_wellformed():
    for table in (BASIC_FIELDS, ADVANCED_FIELDS, PARALLEL_FIELDS):
        for item in table:
            key, label, kind = item[0], item[1], item[2]
            assert key and label
            assert kind in ("text", "combo", "spin", "int", "check")
