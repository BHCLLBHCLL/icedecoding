# -*- coding: utf-8 -*-
"""P19-I1: final-fit harness - oracle loading + metric report machinery."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import tools.hdm_final_fit as F

JOB = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
HAS_JOB = os.path.isdir(JOB)


@pytest.mark.skipif(not HAS_JOB, reason="oracle job missing")
def test_oracle_load():
    pts, n = F.load_oracle()
    assert n == 62626
    assert pts.shape == (62626, 3)


def test_oracle_targets():
    # P18j anchored targets for the distinct-x/y comparison
    assert F.ORACLE_XY == (8190, 6777)


@pytest.mark.skipif(not HAS_JOB, reason="oracle job missing")
def test_full_pipeline_metric_round_trip():
    # the harness records a finite metric dict per config (machinery works)
    rec = F.run(0.165, 0.8, False, 0.02)
    for k in ("dx_pct", "dy_pct", "ratio", "score", "c1e3"):
        assert k in rec, k
    assert rec["score"] > 0
