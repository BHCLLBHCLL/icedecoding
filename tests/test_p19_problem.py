# -*- coding: utf-8 -*-
"""P19-E2: problem array-field full parse + structured accessors."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from icepak_parser.problem_parser import parse_text

SYNTH = """
set solve_id trial002
set solve_do_trials 1
array set expression_param_trials {
trial001 1
trial002 1
}
array set expression_param_random {
trial001 {finCount 18 finThick 0.56084854433951 }
trial002 {finCount 16 finThick 0.73864854433951 }
}
array set expression_params {
finCount 16
finThick 0.56
}
array set expression_param_range {
finCount {0 0 1 1}
finThick {0 0 1 1}
}
array set expression_trial_name {
trial001 trial001
trial002 trial002
}
array set problem_trans_tsq_vals {
min_duration 0.0
maxval 0.0
phase_delay 0.0
}
"""

OPT = os.path.join("D:", os.sep, "training", "icepak", "9-2Optimization",
                   "problem")
TRN = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                   "problem")


def test_arrays_full_parse_synthetic():
    pf = parse_text(SYNTH)
    assert pf.value("solve_do_trials") == "1"
    assert pf.array("expression_param_trials") == {"trial001": "1",
                                                   "trial002": "1"}
    rnd = pf.array("expression_param_random")
    assert "finCount 18 finThick 0.56084854433951" in rnd["trial001"]


def test_trials_structured_synthetic():
    pf = parse_text(SYNTH)
    tr = pf.trials()
    assert sorted(tr) == ["trial001", "trial002"]
    assert tr["trial001"]["vars"]["finCount"] == "18"
    assert tr["trial002"]["vars"]["finThick"] == "0.73864854433951"


def test_transient_tables_synthetic():
    pf = parse_text(SYNTH)
    tt = pf.transient_tables()
    assert "problem_trans_tsq_vals" in tt
    assert tt["problem_trans_tsq_vals"]["maxval"] == "0.0"


def test_table_splits_multi_tokens():
    pf = parse_text(SYNTH)
    tbl = pf.table("expression_param_random")
    assert tbl["trial001"] == ["finCount", "18", "finThick",
                               "0.56084854433951"]


@pytest.mark.skipif(not os.path.exists(OPT), reason="oracle problem missing")
def test_trials_real_optimization():
    pf = parse_text(open(OPT, encoding="latin-1", errors="replace").read())
    tr = pf.trials()
    assert len(tr) >= 3
    assert any("finCount" in t["vars"] for t in tr.values())
    assert tr["trial001"]["vars"]["finCount"] == "18"


def test_design_params_structured():
    pf = parse_text(SYNTH)
    dp = pf.design_params()
    assert dp["finCount"]["value"] == "16"
    assert dp["finCount"]["range"] == ["0", "0", "1", "1"]


@pytest.mark.skipif(not os.path.exists(TRN), reason="oracle problem missing")
def test_transient_tables_real():
    pf = parse_text(open(TRN, encoding="latin-1", errors="replace").read())
    tt = pf.transient_tables()
    assert len(tt) >= 5
    assert "problem_trans_tsq_vals" in tt or "problem_trans_auto_vals" in tt
