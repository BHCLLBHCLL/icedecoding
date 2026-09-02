# -*- coding: utf-8 -*-
import os, shutil, subprocess, sys, tempfile, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
ICEECAD = os.path.join('C:', os.sep, 'Program Files', 'ANSYS Inc', 'v195', 'Icepak', 'icepak19.5', 'bin.win64_amd', 'extension', 'iceecad.exe')
MINIMAL_ANF = r'%s' % 'S\n%NM_Began% \n%NM_Job%\n%NM_PackageName% demo_board\n%NM_BoardSize% 50 40 0\n%NM_Outline% 0 0 50 0 50 40 0 40 0 0\n%NM_GlobalLayerCount% 2\n%NM_LayerNames% TOP BOTTOM\n%NM_GlobalComponentCount% 1\n%NM_CompName_1% U1\n%NM_CompLocX_1% 10 %NM_CompLocY_1% 15\n%NM_End%\n'
def locate_iceecad():
    if os.path.exists(ICEECAD):
        return ICEECAD
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ecad_oracle_probe as P
        return P.locate().get('iceecad.exe')
    except Exception:
        return None
def probe_version(exe):
    import subprocess
    try:
        r = subprocess.run([exe, "--version"], cwd=os.getcwd(), timeout=20,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode == 0:
            return r.stdout.decode("latin-1", "replace").strip()
    except Exception:
        pass
    return None


def run_iceecad(anf_text, sandbox):
    exe = locate_iceecad()
    if not exe or not os.path.exists(exe): return {'available': False, 'reason': 'iceecad not found'}
    ver = probe_version(exe)
    if ver is None:
        return {'available': False, 'reason': 'iceecad --version failed'}
    anf = os.path.join(sandbox, 'demo.anf')
    open(anf, 'w', encoding='latin-1').write(anf_text)
    found = None; proc=None
    for args in (['-h'], [], [anf]):
        try: proc = subprocess.run([exe]+args, cwd=sandbox, timeout=60, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.TimeoutExpired: return {'available': True, 'error': 'timeout'}
        for n in sorted(os.listdir(sandbox)):
            if n.endswith('.icb'): found = os.path.join(sandbox, n); break
        if found: break
    if not found: return {'available': True, 'error': 'no .icb', 'rc': getattr(proc,'returncode',None)}
    icb = open(found, encoding='latin-1', errors='replace').read()
    from ice_ecad import parse_icb, icb_metal_fractions
    parsed = parse_icb(icb)
    return {'available': True, 'icb_file': os.path.basename(found), 'icb': parsed, 'layers': len(parsed['layers']), 'shapes': len(parsed['shapes']), 'vias': len(parsed['vias']), 'nets': len(parsed['nets']), 'metal': icb_metal_fractions(parsed)}
def main(argv=None):
    argv = argv or sys.argv[1:]
    anf = MINIMAL_ANF
    sandbox = tempfile.mkdtemp(prefix='ice_icb_')
    try: print(json.dumps(run_iceecad(anf, sandbox), indent=1, ensure_ascii=False, default=str))
    finally: shutil.rmtree(sandbox, ignore_errors=True)
    return 0
if __name__ == '__main__': sys.exit(main())