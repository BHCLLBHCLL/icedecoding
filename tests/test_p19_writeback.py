# -*- coding: utf-8 -*-
"""Phase B1: byte-level model codec roundtrip."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from icepak_parser.decoder import decode_text, encode_text_faithful,     decode_line, encode_line

ROOT = os.path.join("D:", os.sep, "training", "icepak")


def _find_model(job):
    for pth in (os.path.join(ROOT, job, "model"),
                os.path.join(ROOT, job, "compack-package", "model"),
                os.path.join(ROOT, job, job + "00.model")):
        if os.path.exists(pth):
            return pth
    return None


def test_codec_per_line_identity():
    # decode_line(encode_line(x, seed), seed) == x for a sample
    for seed in (0x21, 0x41, 0x7E):
        enc = encode_line("object block name", seed)
        assert decode_line(enc) == "object block name"


def test_faithful_encode_roundtrip():
    for job in ("10-1transient", "8-2yyhh", "5-1fin", "11-2BGA-package"):
        pth = _find_model(job)
        if pth is None:
            continue
        raw = open(pth, "r", encoding="latin-1", errors="replace").read()
        dec = decode_text(raw)
        enc = encode_text_faithful(dec, raw)
        assert enc == raw, job
