# -*- coding: utf-8 -*-
"""P19-10: Fluent .fdat real data source (field parser)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fluent_fdat import (parse_fdat, parse_cas_cells, fields_of, stats,
                         load_real_temperature)

FDAT = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                      "transient00.fdat")


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_fdat_header_counts_match_cas():
    pf = parse_fdat(FDAT)
    h = pf["header"]
    assert h["cells"] == 58908
    assert h["nodes"] == 62626
    assert len(pf["fields"]) > 50


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_fdat_temperature_plausible():
    pf = parse_fdat(FDAT)
    t = fields_of(pf, "SV_T")
    assert t is not None
    s = stats(t[2])
    assert 293.0 < s["min"] < s["max"] < 330.0, s   # room -> slightly heated
    assert s["min"] >= 273.0 and s["max"] <= 373.0


@pytest.mark.skipif(not os.path.exists(FDAT), reason="oracle fdat missing")
def test_real_temperature_loader():
    vals, centers = load_real_temperature(os.path.dirname(FDAT))
    assert vals and len(vals) > 1000
    assert min(vals) >= 273.0 and max(vals) <= 373.0


def test_fdat_synthetic_section():
    """A minimal fdat: header (33 ...) + one SV_T field section."""
    import struct
    hdr_lines = [
        "\n(33 (8 20 10))\n\n(0 x)\n",
        "(3700 (1 1 0 1 2) (\n",
        "  (temperature 0.)\n  (flow-time 0.)\n)\n",
        '\n(0 "SV_T, domain 1, cell zone 1: 8")\n',
        "(3300 (1 1 1 0 1 0 8)\n(",
    ]
    vals = struct.pack("<8d", 300.0, 301.0, 302.0, 303.0, 304.0, 305.0,
                       306.0, 307.0)
    data = "".join(hdr_lines).encode("latin-1") + vals + b")\n"
    import tempfile
    d = tempfile.mkdtemp(prefix="ice_fdat_")
    p = os.path.join(d, "s.fdat")
    open(p, "wb").write(data)
    pf = parse_fdat(p)
    assert pf["header"]["cells"] == 8
    t = fields_of(pf, "SV_T")
    assert t is not None
    assert t[2] == pytest.approx([300.0, 301.0, 302.0, 303.0, 304.0,
                                  305.0, 306.0, 307.0])
