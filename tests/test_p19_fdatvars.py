# -*- coding: utf-8 -*-
"""P19-E3: fdat full-variable access (pressure/velocity/multi-step prev)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import fluent_fdat as F

FDAT = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                    "transient00.fdat")
HAS_FDAT = os.path.exists(FDAT)


def test_fdat_variables_synthetic():
    parsed = {"header": {}, "fields": [
        ("SV_P, domain 1, cell zone 16, 47474 cells:", [3300], [1.0, 2.0]),
        ("SV_T, domain 1, cell zone 16, 47474 cells:", [3300], [300.0]),
        ("SV_U, domain 1, wall zone 3, 6982 faces:", [3300], [0.0]),
    ]}
    assert F.fdat_variables(parsed) == ["SV_P", "SV_T", "SV_U"]
    name, args, vals = F.cell_zone_field(parsed, "SV_P")
    assert vals == [1.0, 2.0]
    assert F.cell_zone_field(parsed, "SV_U") is None  # wall zone, not cells


@pytest.mark.skipif(not HAS_FDAT, reason="real fdat missing")
def test_real_full_variables():
    parsed = F.parse_fdat(FDAT)
    vars_ = F.fdat_variables(parsed)
    for v in ("SV_T", "SV_P", "SV_U", "SV_V", "SV_W"):
        assert v in vars_, vars_
    # every main variable has a cell-zone section; sentinels cleaned
    for v in ("SV_P", "SV_U", "SV_V", "SV_W"):
        got = F.cell_zone_field(parsed, v)
        assert got is not None and len(got[2]) > 10000, v
        assert all(abs(x) < 1e100 for x in got[2]), v
    # pressure range sane (gauge around ambient, Pa) after sentinel clean
    p = F.cell_zone_field(parsed, "SV_P")[2]
    assert max(p) - min(p) < 1e4
    # previous-time-step fields present (multi-step transient)
    assert "SV_T_M1" in vars_ or "SV_P_M1" in vars_


@pytest.mark.skipif(not HAS_FDAT, reason="real fdat missing")
def test_real_field_values_accessor():
    d = os.path.dirname(FDAT)
    p = F.real_field_values(d, "SV_P")
    assert p is not None and len(p) > 10000
    assert all(abs(x) < 1e100 for x in p)
    u = F.real_field_values(d, "SV_U")
    assert u is not None and len(u) > 10000
