# -*- coding: utf-8 -*-
"""P16 tests: continuous subdivision engine (non-integer m, staggered lines
+ clipping) — exact (a,b,c) axis triple replication inside 1% of the oracle
node count, with the corrected HEX cas zone-count semantics."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_refine import (clipped_lines, axis_raw, solve_axis,
                        best_axis_triples, tune_continuous)

pytestmark = []  # pure logic, no GUI


def test_clipped_lines_fractional_m():
    # span 1.0, d = 0.33 -> non-integer m = 3.03; lines at 0.33/0.66/0.99
    out = clipped_lines(0.0, 1.0, 0.33, 0.0)
    assert out == pytest.approx([0.33, 0.66, 0.99])
    # phase staggers the lattice (half-offset)
    out2 = clipped_lines(0.0, 1.0, 0.33, 0.5)
    assert out2 == pytest.approx([0.165, 0.495, 0.825])
    # clipping: the last (partial) interval never adds a line past hi
    assert max(out2) < 1.0


def test_axis_count_monotone_in_dg():
    lo, hi = 0.0, 1.0
    objs = [("b", ((0.2, 0.0, 0.0), (0.6, 1.0, 1.0))),
            ("c", ((0.7, 0.0, 0.0), (0.9, 1.0, 1.0)))]
    counts = [len(axis_raw(lo, hi, objs, 0, d)) for d in
              (0.3, 0.15, 0.08, 0.04, 0.02)]
    assert counts == sorted(counts)


def test_solve_axis_exact_count():
    lo, hi = 0.0, 1.0
    objs = [("b", ((0.2, 0.0, 0.0), (0.6, 1.0, 1.0)))]
    sol = solve_axis(lo, hi, objs, 0, 21)
    assert sol is not None
    axis, prm = sol
    assert len(axis) == 21
    assert axis[0] == lo and axis[-1] == hi


@pytest.mark.parametrize("target", [62626, 94756, 98310, 127394, 186209,
                                    47503, 5022, 31764, 162053, 351110,
                                    141720, 187730])
def test_best_triple_under_one_percent(target):
    triples = best_axis_triples(target, k=8)
    assert triples, target
    err, a, b, c, sk = triples[0]
    assert err < 0.01, (target, a, b, c, err)
    assert a * b * c == pytest.approx(target, rel=0.01)


def test_tune_continuous_exact_on_demo():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet, default_object
    proj = IcepakProject.empty("t16")
    proj.model.objects.append(default_cabinet())
    proj.model.objects.append(default_object("block", "block.1"))
    rec = tune_continuous("", 2000, model=proj.model)
    assert rec is not None
    err = abs(rec["nodes"] - 2000) / 2000.0
    assert err < 0.01, rec
    a, b, c = rec["axis_counts"]
    assert rec["nodes"] == a * b * c
    assert len(rec["result"].axes[0]) == a
    assert len(rec["result"].axes[1]) == b
    assert len(rec["result"].axes[2]) == c


def test_continuous_axes_valid():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet, default_object
    proj = IcepakProject.empty("t16b")
    proj.model.objects.append(default_cabinet())
    proj.model.objects.append(default_object("block", "block.1"))
    rec = tune_continuous("", 3000, model=proj.model)
    assert rec is not None
    for ax in rec["result"].axes:
        assert ax == sorted(ax)
        assert len(set(ax)) == len(ax)
