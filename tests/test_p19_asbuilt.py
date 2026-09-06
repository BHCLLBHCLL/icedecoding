# -*- coding: utf-8 -*-
"""J3-A: as-built full reproduction (components + per-level residual
tables) — end-to-end roundtrip provenance lock."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
HAS_ORACLE = os.path.isdir(JDIR) and os.path.exists(
    os.path.join(JDIR, "grid_output"))


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_asbuilt_full_reproduction():
    """150/150 levels, 62626/62626 nodes reproduced (components +
    per-level residual tables)."""
    import tools.hdm_j3_asbuilt as A
    assert A.main() == 0
    rec = json.load(open(os.path.join(ROOT, "tools", "probe_work",
                                      "j3_asbuilt.json"), encoding="utf-8"))
    assert rec["exact_levels"] == 150
    assert rec["exact_nodes"] == 62626
    assert rec["nodes_total"] == 62626
    assert rec["residual_total"] + rec["matched_nodes"] == 62626


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_asbuilt_residual_provenance():
    """Residual accounting matches the measured class gaps."""
    rec = json.load(open(os.path.join(ROOT, "tools", "probe_work",
                                      "j3_asbuilt.json"), encoding="utf-8"))
    rp = rec["residual_per_class"]
    assert rp["coarse"] == 0
    assert rp["main"] == 8832
    assert rp["mid"] == 596
    assert rp["special"] == 853
    assert rp["cluster"] == 10998
    assert rp["artifact"] == 1
    # residual table well-formed: one entry per level
    res = json.load(open(os.path.join(ROOT, "tools", "probe_work",
                                      "j3_remaining.json"), encoding="utf-8"))
    assert len(res) == 150
