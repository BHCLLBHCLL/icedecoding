# -*- coding: utf-8 -*-
"""Extract ASCII/UTF16 strings and PE import names from a binary."""
import re, sys, struct, os

def ascii_strings(b, minlen=5):
    return re.findall(rb'[\x20-\x7e]{%d,}' % minlen, b)

def utf16_strings(b, minlen=4):
    out = []
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}' % minlen, b):
        try:
            s = m.group(0).decode('utf-16le')
            if s.isprintable():
                out.append(s.encode())
        except Exception:
            pass
    return out

def pe_imports(b):
    """Parse PE import table names (rudimentary)."""
    try:
        if b[:2] != b'MZ':
            return []
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        if b[e_lfanew:e_lfanew+4] != b'PE\x00\x00':
            return []
        coff = e_lfanew + 4
        nsec = struct.unpack_from('<H', b, coff + 2)[0]
        optsz = struct.unpack_from('<H', b, coff + 16)[0]
        magic = struct.unpack_from('<H', b, coff + 20)[0]
        opt = coff + 20
        if magic == 0x10B:
            imp_rva, imp_sz = struct.unpack_from('<II', b, opt + 8 + 96 + 12)
        elif magic == 0x20B:
            imp_rva, imp_sz = struct.unpack_from('<II', b, opt + 8 + 104 + 12)
        else:
            return []
        sec = coff + 20 + optsz
        secs = []
        for i in range(nsec):
            o = sec + i * 40
            va = struct.unpack_from('<I', b, o + 12)[0]
            vsz = struct.unpack_from('<I', b, o + 8)[0]
            raw = struct.unpack_from('<I', b, o + 20)[0]
            secs.append((va, vsz, raw))
        def rva2off(rva):
            for va, vsz, raw in secs:
                if va <= rva < va + max(vsz, 0x1000):
                    return raw + (rva - va)
            return None
        names = []
        off = rva2off(imp_rva) if imp_rva else None
        if off is None:
            return names
        while True:
            dll_name_rva = struct.unpack_from('<I', b, off + 12)[0]
            if dll_name_rva == 0:
                break
            doff = rva2off(dll_name_rva)
            if doff is None:
                break
            end = b.find(b'\x00', doff)
            names.append(b[doff:end].decode('latin1'))
            off += 20
        return names
    except Exception:
        return []

def main(path, kws, limit, minlen):
    b = open(path, 'rb').read()
    print('### FILE:', path, os.path.getsize(path))
    print('### PE IMPORTS:')
    for n in pe_imports(b):
        print('   ', n)
    print('### MATCHING STRINGS (kw=OR):')
    kwb = [k.lower().encode() for k in kws]
    seen = set()
    shown = 0
    total = 0
    for s in list(ascii_strings(b, minlen)) + list(utf16_strings(b, minlen)):
        if s in seen: continue
        seen.add(s)
        low = s.lower()
        if any(k in low for k in kwb):
            total += 1
            if shown < limit:
                print(repr(s.decode('latin1')))
                shown += 1
    print('### total matched:', total, '| shown:', shown)

if __name__ == '__main__':
    path = sys.argv[1]
    kws = sys.argv[2].split('|') if len(sys.argv) > 2 and sys.argv[2] else []
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    minlen = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    main(path, kws, limit, minlen)
