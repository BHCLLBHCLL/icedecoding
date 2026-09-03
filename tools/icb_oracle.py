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

ICE_BIN = r'C:/Program Files/ANSYS Inc/v195/Icepak/bin//../icepak19.5/bin.win64_amd'
ICE_INST = r'C:/Program Files/ANSYS Inc/v195/Icepak/bin//../icepak19.5'
ICE_VERSION = '19.5'
def convert_anf_to_icb(anf_path, out_dir, board_name='BOARD_OUTLINE_1'):
    """Run iceecad with the GUI's exact arg template (captured by
    tools/trace_iceecad.py during an ECAD import).  Delegates to
    convert_ecad_to_icb with input_type='anf'."""
    return convert_ecad_to_icb(anf_path, out_dir, board_name, input_type='anf')


# ---- P19-D6: ODB++/ANF -> ICB oracle sandbox pipeline (generalized) ---------
# iceecad <mode> selects the input format (probed from the binary on A1.anf):
#   mode=1  ANF V4/V2 -> EDB -> ICB         (rc 0, produces <board>.icb)
#   mode=2  EDB (existing directory) -> ICB
#   mode=3  ODB++ -> EDB -> ICB
#   mode=8  ICB -> BOOL/INFO (output postprocess)
INPUT_MODES = {'anf': 1, 'edb': 2, 'odbpp': 3}
_EXT_BY_TYPE = {'.anf': 'anf', '.tgz': 'odbpp', '.tar.gz': 'odbpp',
                '.odb': 'odbpp', '.edb': 'edb', '.aedb': 'edb'}


def sniff_ecad_type(path):
    """Guess the ECAD input type from path: anf / odpbb / edb / None."""
    if not path:
        return None
    low = str(path).lower()
    if os.path.isdir(str(path)):
        # an EDB project: .aedb dir with edbdata/ + an .aedb proj file
        for cand in ('edbdata', 'aedb'):
            if os.path.exists(os.path.join(str(path), cand)):
                return 'edb'
        # ODB++ job has matrix/ and steps/ subdirectories
        for cand in ('matrix', 'steps'):
            if os.path.isdir(os.path.join(str(path), cand)):
                return 'odbpp'
        return None
    for ext in ('.tar.gz', '.tgz', '.anf', '.odb', '.edb', '.aedb'):
        if low.endswith(ext):
            return _EXT_BY_TYPE[ext]
    return None


def convert_ecad_to_icb(input_path, out_dir, board_name='BOARD_OUTLINE_1',
                        input_type=None):
    """Generalized ANF / ODB++ / EDB -> ICB oracle conversion.

    Runs the real iceecad.exe in a sandbox output dir with the GUI's exact arg
    template; the input format is selected by the mode (from INPUT_MODES).
    Returns a dict; never raises on oracle absence.
    """
    exe = locate_iceecad()
    if not exe or not os.path.exists(exe):
        return {'available': False, 'reason': 'iceecad not found'}
    itype = input_type or sniff_ecad_type(input_path)
    if itype is None:
        return {'available': True, 'input_type': None, 'mode': None,
                'error': 'unknown ECAD input type', 'returncode': None,
                'icb_file': None}
    mode = INPUT_MODES.get(itype)
    if mode is None:
        return {'available': True, 'input_type': itype, 'mode': None,
                'error': 'unsupported input type %r' % itype,
                'returncode': None, 'icb_file': None}
    os.makedirs(out_dir, exist_ok=True)
    args = [exe, str(mode), os.path.abspath(input_path), board_name,
            os.path.abspath(out_dir), ICE_BIN, ICE_INST, ICE_VERSION,
            'spike', '0', 'smooth', '0', 'nocheckoverlap', 'sliver', '15.0',
            'use_edb', '1', 'is_pkg', '0', 'is_dstk', '0']
    import subprocess
    r = subprocess.run(args, cwd=out_dir, timeout=600,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    icb = None
    for n in sorted(os.listdir(out_dir)):
        if n.endswith('.icb'):
            icb = os.path.join(out_dir, n)
            break
    return {'available': True, 'input_type': itype, 'mode': mode,
            'returncode': r.returncode, 'icb_file': icb,
            'icb_name': os.path.basename(icb) if icb else None}


def parse_icb_file(icb_path):
    """Parse an .icb file written by iceecad into the sectioned dict."""
    from ice_ecad import parse_icb
    return parse_icb(open(icb_path, encoding='latin-1', errors='replace').read())


def icb_text_of(icb_path):
    return open(icb_path, encoding='latin-1', errors='replace').read()
