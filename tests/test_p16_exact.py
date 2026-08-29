# -*- coding: utf-8 -*-
"""P17 tests: exact-0 node replication (hanging-node slab refinement)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_refine import decompose_slabs, exact_axis_plan, tune_exact

pytestmark = []  # pure logic, no GUI

TARGETS = [62626, 94756, 98310, 127394, 186209, 47503, 5022, 54613,
           183732, 31764, 162053, 351110, 141720, 187730, 143205, 827889]


def test_decompose_slabs_basic():
    assert decompose_slabs(0, 10, 10) == []
    assert decompose_slabs(5, 10, 10) is None       # prime residual
    assert decompose_slabs(1, 10, 10) is None
    slabs = decompose_slabs(226, 40, 40)
    assert slabs is not None
    assert sum(x * z for x, z in slabs) == 226
    assert all(2 <= x <= 40 and 2 <= z <= 40 for x, z in slabs)


@pytest.mark.parametrize("t", TARGETS)
def test_exact_plan_zero_error(t):
    plan = exact_axis_plan(t)
    assert plan is not None, t
    assert plan["nodes"] == t, (t, plan)
    a, b, c = plan["a"], plan["b"], plan["c"]
    assert a * b * c + plan["r"] == t
    assert sum(x * z for x, z in plan["slabs"]) == plan["r"]
    # balanced base grid: max/min axis count <= 3.0
    assert max(a, b, c) / float(min(a, b, c)) <= 3.0, (t, a, b, c)


def test_exact_plan_factor_mode():
    plan = exact_axis_plan(8000)   # 20**3
    assert plan["mode"] == "factor"
    assert plan["r"] == 0
    assert plan["nodes"] == 8000


def test_tune_exact_demo_prime_target():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet, default_object
    proj = IcepakProject.empty("t17")
    proj.model.objects.append(default_cabinet())
    proj.model.objects.append(default_object("block", "block.1"))
    rec = tune_exact("", 2003, model=proj.model)   # prime target
    assert rec is not None
    assert rec["err"] == 0.0
    assert rec["nodes"] == 2003
    a, b, c = rec["axis_counts"]
    assert len(rec["result"].axes[0]) == a
    assert len(rec["result"].axes[1]) == b
    assert len(rec["result"].axes[2]) == c
    assert rec["base_nodes"] + rec["r"] == 2003


def test_tune_exact_demo_large():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet, default_object
    proj = IcepakProject.empty("t17b")
    proj.model.objects.append(default_cabinet())
    proj.model.objects.append(default_object("block", "block.1"))
    rec = tune_exact("", 62626, model=proj.model)
    assert rec is not None
    assert rec["nodes"] == 62626
