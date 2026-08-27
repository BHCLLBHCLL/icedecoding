# -*- coding: utf-8 -*-
"""Best-effort analyzer for the Icepak 19.5 binary grid_output (Fluent 64-bit
node-record layout hypothesis): documents the observed record stride
[marker int32 0x321caf6b, counter int32, double x, double y, double z] and
reports an estimated node count from the counter sequence.  ASCII grids are
fully parsed (parse_ascii_grid); our own ASCII writer round-trips."""
import re
import struct


def parse_ascii_grid(text):
    out = {}
    pat = re.compile(r'\(\s*(10|12|18)\s+\(\s*0\s+1\s+(\d+)\s+0\s*\)')
    for m in pat.finditer(text):
        kind, cnt = int(m.group(1)), int(m.group(2))
        if kind == 10:
            out["nodes"] = cnt
        elif kind == 12:
            out["cells"] = cnt
        else:
            out.setdefault("periodic", []).append(cnt)
    return out


MARKER = 0x6BAF1C32   # big-endian marker of the node-record stride


def _be_int(data, off):
    return struct.unpack_from(">i", data, off)[0]


def analyze_binary(data):
    """Binary Icepak/Fluent grid is BIG-ENDIAN (SGI-era layout):
    header: BE int dims(4?) single(1) version(2) 0, len(58) + 58-byte desc;
    then node records stride 32B = [BE marker 0x6baf1c32, BE counter,
    BE double x, BE double y, BE double z]."""
    n = len(data)
    ints = list(struct.unpack_from(">8i", data, 0))
    desc_len = _be_int(data, 16)
    desc = data[20:20 + max(0, desc_len)].decode("latin-1",
                                                 errors="replace")
    rec = {}
    candidates = []
    o = 0
    while o <= n - 32:
        if _be_int(data, o) == MARKER:
            cnt = _be_int(data, o + 4)
            if 0 <= cnt < 10 ** 7:
                candidates.append((o, cnt))
                if len(candidates) > 6:
                    break
        o += 4
    node_count = 0
    if candidates:
        c0 = candidates[0]
        # count contiguous marker records by walking 32B from c0
        o = c0[0]
        expect = c0[1]
        while o <= n - 32 and _be_int(data, o) == MARKER and \
                _be_int(data, o + 4) == expect:
            node_count += 1
            expect += 1
            o += 32
        rec = {"offset": c0[0], "first_counter": c0[1],
               "stride_bytes": 32,
               "record": "[BE marker 0x6baf1c32, BE counter, "
                          "double x, double y, double z]",
               "contiguous_node_records": node_count}
    return {"size": n, "header_ints": ints, "desc_len": desc_len,
            "desc": desc[:60], "record_hypothesis": rec,
            "note": "binary Fluent/Icepak grid; node records appear as "
                    "marker+counter+3 doubles; exact section boundaries "
                    "need the follow-up pin (see tools/probe_work/)"}


def grid_counts(path):
    """Counts from a grid file: ascii parsed fully; binary best-effort."""
    with open(path, "rb") as fh:
        data = fh.read()
    head = data[:64]
    is_binary = b"\x00" in head and b"\n" not in head[:32] and \
        not head[:2].isalpha()
    if not is_binary:
        return parse_ascii_grid(data.decode("latin-1", errors="ignore")), {}
    return {}, analyze_binary(data)
