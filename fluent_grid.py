# -*- coding: utf-8 -*-
"""Best-effort analyzer for the Icepak 19.5 binary grid_output (Fluent 64-bit
node-record layout hypothesis): documents the observed record stride
[marker int32 0x321caf6b, counter int32, double x, double y, double z] and
reports an estimated node count from the counter sequence.  ASCII grids are
fully parsed (parse_ascii_grid); our own ASCII writer round-trips."""
import re
import struct


def _num(tok):
    """Icepak cas zone counts are HEX (observed: '17224' -> 94756 nodes,
    '1f1a2' -> 127394, '22998' -> 141720; cross-validated by *.nodemap)."""
    tok = tok.strip()
    if tok.lower().startswith("0x"):
        tok = tok[2:]
    try:
        return int(tok, 16)
    except ValueError:
        return 0


def parse_ascii_grid(text):
    out = {}
    pat = re.compile(
        r'\(\s*(10|12|18)\s+\(\s*0\s+1\s+([0-9a-fA-F]+)\s+[01]\s*\)')
    for m in pat.finditer(text):
        kind, cnt = int(m.group(1)), _num(m.group(2))
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


# ---- P19-E1: full binary grid_output decode (nodes / cells / faces) ---------
def decode_grid_output(path, n_nodes=None):
    """E1: decode every section of the binary grid_output.

    Layout (10-1transient verified; section boundaries driven by the id runs,
    not fixed counts):
      64-byte header
      node section:  28-byte BE records [counter][x][y][z], counters 0..N-1
      lead face:     24-byte record [face id][zone][n0][n1][n2][n3] with
                     face id == N+1 (first global id after the nodes)
      cell section:  40-byte records [8 node ids][cell id][zone], cell ids
                     consecutive from N+2
      face section:  24-byte records [face id][zone][4 node ids], face ids
                     consecutive from N + n_cells + 2

    Returns a dict {'nodes': (N,3), 'cells': (C,8) int, 'cell_ids',
    'faces': (F,4) int node ids, 'face_ids', 'zones', 'offsets'} or None.
    """
    import numpy as np
    with open(path, "rb") as fh:
        data = fh.read()
    # 1) node section: counter run 0,1,2 in the header tail
    off = None
    for o in range(56, 200, 4):
        if o + 56 <= len(data) and _be_int(data, o) == 0 and \
                _be_int(data, o + 28) == 1 and _be_int(data, o + 56) == 2:
            off = o
            break
    if off is None:
        return None
    if not n_nodes:
        k = 0
        p = off
        while p + 28 <= len(data) and _be_int(data, p) == k:
            k += 1
            p += 28
        n_nodes = k
    nodes = np.empty((n_nodes, 3), dtype=np.float64)
    for i in range(n_nodes):
        o = off + i * 28
        if _be_int(data, o) != i:
            return None
        x, y, z = struct.unpack_from(">ddd", data, o + 4)
        nodes[i] = (x, y, z)
    p = off + n_nodes * 28
    # 2) lead 24-byte record: [4 node ids][face id][zone], id == n_nodes + 1
    lead = None
    if p + 24 <= len(data):
        rec = struct.unpack_from(">6i", data, p)
        if rec[4] == n_nodes + 1:
            lead = rec
            p += 24
    # 3) cell section: 40-byte records, ids consecutive from n_nodes + 2
    cells = []
    cell_ids = []
    expect = n_nodes + 2
    while p + 40 <= len(data):
        ids = struct.unpack_from(">8i", data, p)
        cid = _be_int(data, p + 32)
        if cid != expect:
            break
        if any(v < 0 or v >= n_nodes for v in ids):
            break
        cells.append(ids)
        cell_ids.append(cid)
        expect += 1
        p += 40
    # 4) face section: 24-byte records [4 node ids][face id][zone],
    #    face ids consecutive from n_nodes + n_cells + 2
    faces = []
    face_ids = []
    expect_f = n_nodes + len(cell_ids) + 2
    while p + 24 <= len(data):
        rec = struct.unpack_from(">6i", data, p)
        if rec[4] != expect_f:
            break
        faces.append(rec)
        face_ids.append(rec[4])
        expect_f += 1
        p += 24
    return {
        "nodes": nodes,
        "cells": np.array(cells, dtype=np.int64).reshape(-1, 8) if cells
        else np.zeros((0, 8), dtype=np.int64),
        "cell_ids": np.array(cell_ids, dtype=np.int64),
        "faces": np.array([f[0:4] for f in faces], dtype=np.int64),
        "face_ids": np.array(face_ids, dtype=np.int64),
        "face_zones": np.array([f[5] for f in faces], dtype=np.int64),
        "lead_face": lead,
        "offsets": {"header": 64, "nodes": off,
                     "cells": off + n_nodes * 28 + (24 if lead else 0),
                     "faces": p - len(face_ids) * 24},
        "n_nodes": n_nodes, "n_cells": len(cell_ids),
        "n_faces": len(face_ids),
    }
