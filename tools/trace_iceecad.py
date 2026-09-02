# -*- coding: utf-8 -*-
import os, subprocess, sys, time, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
PS = "Get-CimInstance Win32_Process -Filter \"name='iceecad.exe'\" | Select-Object ProcessId,CommandLine,Name | ConvertTo-Json -Compress"
def iceecad_processes():
    out = []
    try:
        r = subprocess.run(['powershell','-NoProfile','-Command',PS], capture_output=True, timeout=15)
        txt = r.stdout.decode('utf-8','replace').strip()
        if not txt: return out
        data = json.loads(txt)
        if isinstance(data, dict): data = [data]
        for d in data:
            out.append({'pid': d.get('ProcessId'), 'cmdline': d.get('CommandLine'), 'name': d.get('Name')})
    except Exception as e:
        out.append({'error': repr(e)})
    return out
def watch(seconds=60, interval=1.0, log=None):
    seen = set(); t0 = time.time()
    while time.time() - t0 < seconds:
        for p in iceecad_processes():
            key = (p.get('pid'), p.get('cmdline'))
            if key in seen: continue
            seen.add(key)
            rec = json.dumps(p, ensure_ascii=False)
            print('ICP', rec, flush=True)
            if log: open(log,'a',encoding='utf-8').write(rec + chr(10))
        time.sleep(interval)
    return len(seen)
if __name__ == '__main__':
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    log = sys.argv[2] if len(sys.argv) > 2 else None
    print('watching iceecad.exe for %.0fs...' % seconds, flush=True)
    n = watch(seconds, log=log)
    print('observed', n, 'invocations', flush=True)