# -*- coding: utf-8 -*-
"""Parse all command_define entries in Icepak lib tcl files -> command registry with icons."""
import re, os, sys, json

ROOT = r'C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\lib'
pat = re.compile(r'command_define\s+"([^"]+)"\s+"([^"]+)"\s+([A-Za-z0-9_]+)', re.S)
entries = []
for dirpath, dirs, files in os.walk(ROOT):
    for f in files:
        if not f.endswith('.tcl'): continue
        full = os.path.join(dirpath, f)
        try:
            txt = open(full, encoding='latin1').read()
        except Exception: continue
        for m in pat.finditer(txt):
            name, short, icon = m.group(1), m.group(2), m.group(3)
            entries.append((os.path.relpath(full, ROOT), name, short, icon))

# dedupe by (name): first occurrence
seen = {}
for rel, name, short, icon in entries:
    if name not in seen:
        seen[name] = (rel, short, icon)

print(json.dumps({'count': len(seen), 'entries': [
    {'cmd': k, 'icon': v[2], 'file': v[0]} for k, v in sorted(seen.items())
]}, ensure_ascii=False, indent=1))
