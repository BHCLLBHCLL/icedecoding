# -*- coding: utf-8 -*-
"""Generate machine-readable Icepak 19.5 GUI golden spec (menus, toolbars, hotkeys, icons)."""
import re, json, os, io

BASE = r'C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\lib'
def read(p): return open(os.path.join(BASE, p), encoding='latin1').read()

menus_tcl = read(r'icepak\menus_icepak.tcl')
cmds_icepak = read(r'icepak\commands_icepak.tcl')
cmds_guibase = read(r'guibase\commands_guibase.tcl')
cmds_autohex = read(r'autohex\commands_autohex.tcl')

def tokenize(s):
    toks=[];i,n=0,len(s)
    while i<n:
        c=s[i]
        if c.isspace():i+=1;continue
        if c=='{':
            depth=1;j=i+1
            while j<n and depth:
                if s[j]=='{':depth+=1
                elif s[j]=='}':depth-=1
                j+=1
            toks.append(('block',s[i+1:j-1]));i=j
        elif c=='"':
            j=i+1
            while j<n:
                if s[j]=='\\':j+=2;continue
                if s[j]=='"':break
                j+=1
            toks.append(('str',s[i+1:j]));i=j+1
        elif c=='[':
            j=i+1;depth=1
            while j<n and depth:
                if s[j]=='[':depth+=1
                elif s[j]==']':depth-=1
                j+=1
            toks.append(('cmd',s[i+1:j-1]));i=j+1
        else:
            m=re.match(r'[^\s\{\}\[\]"]+',s[i:])
            toks.append(('word',m.group(0)));i+=m.end()
    return toks

def parse_entries(inner, expand_multi=True):
    toks=tokenize(inner);items=[];i=0
    while i<len(toks):
        t,v=toks[i]
        if t=='word' and v=='separator':
            items.append({'sep':True});i+=1;continue
        if t=='block':
            items.append({'list':parse_entries(v,False)});i+=1;continue
        words=[v];i+=1
        while i<len(toks) and toks[i][0] in ('str','word'):
            words.append(toks[i][1]);i+=1
        if i<len(toks) and toks[i][0]=='block':
            items.append({'descriptor':words,'cascade':parse_entries(toks[i][1],False)});i+=1
            continue
        if expand_multi:
            for w in words: items.append({'scalar':w})
        else:
            items.append({'scalar':words if len(words)>1 else words[0]})
    return items

def parse_toolbars(text):
    toks=tokenize(text);res=[]
    for i,(t,v) in enumerate(toks):
        if t in ('word','cmd') and v.strip().endswith('command_make_toolbar'):
            arg=[];j=i+1
            while j<len(toks) and len(arg)<4 and toks[j][0] in ('str','word','block'):
                arg.append(toks[j]);j+=1
            if len(arg)>=3:
                res.append({'name':arg[0][1],'row':arg[1][1],'entries':parse_entries(arg[2][1]),
                            'at_end':arg[3][1] if len(arg)>3 else '1'})
        elif t=='block':
            # recurse into if/else blocks (File commands live inside them)
            res.extend(parse_toolbars(v))
    return res

def parse_menus(text):
    toks=tokenize(text);res=[]
    for i,(t,v) in enumerate(toks):
        if t in ('word','cmd') and v.strip().endswith('command_make_menu'):
            arg=[];j=i+1
            while j<len(toks) and len(arg)<6 and toks[j][0] in ('str','word','block'):
                arg.append(toks[j]);j+=1
            if len(arg)>=4:
                side=arg[2][1] if arg[2][0] in ('str','word') else 'left'
                entries=parse_entries(arg[3][1])
                kbd=''
                for a in arg[4:]:
                    if a[0]=='block' and 'keyboard' in a[1]:
                        m=re.search(r'keyboard\s+(\w+)',a[1])
                        if m:kbd=m.group(1)
                res.append({'name':arg[0][1],'active':arg[1][1],'side':side,'entries':entries,'keyboard':kbd})
    return res

def parse_hotkeys(text):
    out=[]
    for kind in ('command_set_hotkeys','command_set_hotkeys_tdv'):
        for m in re.finditer(re.escape(kind)+r'\s*\{',text):
            j=m.end()-1;depth=1
            while j<len(text) and depth:
                if text[j]=='{':depth+=1
                elif text[j]=='}':depth-=1
                j+=1
            inner=text[m.end():j-1]
            for k,cmd in re.findall(r'([A-Za-z0-9\-+?*]+)\s+"([^"]+)"',inner):
                out.append({'key':k,'cmd':cmd,'kind':kind})
    return out

def E(*scalars):
    """helper: entry scalars -> list of entries"""
    return [{'scalar':s} for s in scalars]
def SEP():
    return E('separator')
def DESC(words, cascade):
    return [{'descriptor':words,'cascade':cascade}]

# FILE menu — authoritative transcription from menus_icepak.tcl lines 170-279 (standalone variant)
file_standalone = (
    E('New project','Open project','Merge project','Reload main version') + SEP() +
    E('Save project','Save project as') + SEP() +
    DESC(['Import','','cascade'],
        E('Import CSV/Excel') +
        DESC(['IDF file','','cascade'], E('New board','Update board')) +
        E('Import IDX file','Import Electronics Cooling XML') + SEP() +
        DESC(['Powermaps','','cascade'], E('Apache Sentinel TI profile','Cadence tab file','Cadence Stacked Die tab files','Gradient Firebolt i2p file','RedHawk CTM profile')) +
        E('Import Networks','Import JEDEC PTD/JEP30 file')) +
    DESC(['Export','','cascade'],
        E('ANSYS Electronics Desktop script') + SEP() +
        E('Export CSV/Excel','Export IDF file','Export Electronics Cooling XML') + SEP() +
        E('Export Networks','Export JEDEC PTD/JEP30 file')) +
    DESC(['EM Mapping','','cascade'], E('Volumetric heat losses','Surface heat losses')) +
    SEP() + E('Unpack project','Pack project') +
    SEP() + E('Cleanup','Print screen','Create image file','Command prompt','Quit')
)
file_workbench = (
    E('Refresh Input Data','Merge project','Reload main version') + SEP() +
    E('Save project') + SEP() +
    DESC(['Import','','cascade'],
        E('Import CSV/Excel') +
        DESC(['IDF file','','cascade'], E('New board','Update board')) +
        E('Import IDX file','Import Electronics Cooling XML') + SEP() +
        DESC(['Powermaps','','cascade'], E('Apache Sentinel TI profile','Cadence tab file','Cadence Stacked Die tab files','Gradient Firebolt i2p file','RedHawk CTM profile')) +
        E('Import Networks')) +
    DESC(['Export','','cascade'],
        E('ANSYS Electronics Desktop script') + SEP() +
        E('Export CSV/Excel','Export IDF file','Export Electronics Cooling XML') + SEP() +
        E('Export Networks')) +
    DESC(['EM Mapping','','cascade'], E('Volumetric heat losses','Surface heat losses')) +
    SEP() + E('Pack project') +
    SEP() + E('Cleanup','Print screen','Create image file','Command prompt','Close Icepak')
)

pat=re.compile(r'command_define\s+"([^"]+)"\s+"([^"]+)"\s+([A-Za-z0-9_]+)',re.S)
icons={}
for f in (cmds_icepak,cmds_guibase,cmds_autohex,menus_tcl):
    for m in pat.finditer(f):
        if m.group(3)!='no_icon' and m.group(1) not in icons:
            icons[m.group(1)]=m.group(3)
for m in re.finditer(r'command_set_icon\s+"([^"]+)"\s+([A-Za-z0-9_]+)',menus_tcl+cmds_icepak):
    icons[m.group(1)]=m.group(2)

toolbars=parse_toolbars(menus_tcl)
# File commands is defined twice (Workbench variant + standalone); keep the
# standalone (last) definition, first occurrence order.
_dedup=[]
for tb in toolbars:
    _dedup=[x for x in _dedup if x['name']!=tb['name']]
    _dedup.append(tb)
toolbars=_dedup
obj_order=['Create blocks','Create blowers','Create enclosures','Create fans','Create heat exchangers','Create heat sinks','Create materials','Create networks','Create openings','Create packages','Create assemblies','Create printed circuit boards','Create periodic boundaries','Create plates','Create resistances','Create sources','Create grille','Create walls']
toolbars.insert(0,{'name':'Object creation','row':'1 object_tools','entries':[{'scalar':c} for c in obj_order],'at_end':'0'})

menus=parse_menus(menus_tcl)
for m in menus:
    if m['name']=='File':
        m['entries']=file_standalone
        m['note']='standalone variant shown; Workbench variant differs (see menus_icepak.tcl L170-211): no New/Open/Save-as/Unpack/Import JEDEC/Export JEDEC; has Refresh Input Data first and Close Icepak instead of Quit.'
    if m['name']=='Macros':
        m['dynamic']='populated at runtime from icepak_lib/macros/*.tcl via add_macro_commands()'
    if m['name']=='Windows':
        m['dynamic']='populated at runtime from toplevel registry'

spec={'product':'ANSYS Icepak 19.5 (2019 R3)',
      'source':'menus_icepak.tcl + commands_*.tcl (reverse engineered, authoritative)',
      'menus':menus,'toolbars':toolbars,'hotkeys':parse_hotkeys(menus_tcl),'icons':icons}
out_json=os.path.join(r'D:\training\caedecoder\icedecoding\docs','icepak_gui_golden.json')
with io.open(out_json,'w',encoding='utf-8') as fp:
    json.dump(spec,fp,ensure_ascii=False,indent=1)

def tree_summary(entries, depth):
    out=[]
    for e in entries:
        if 'sep' in e: out.append('\t'*depth+'-- separator --')
        elif 'scalar' in e: out.append('\t'*depth+'- '+str(e['scalar']))
        elif 'descriptor' in e: out.append('\t'*depth+'* '+str(e['descriptor'][0])+' ->'); out += tree_summary(e['cascade'],depth+1)
        elif 'list' in e: out.append('\t'*depth+'? >'); out += tree_summary(e['list'],depth+1)
    return out

print('MENUS:',len(menus))
for m in menus:
    print('\n## %s (kbd=%s%s)'%(m['name'],m['keyboard'],' DYNAMIC' if m.get('dynamic') else ''))
    for l in tree_summary(m['entries'],1): print(l)
print('\nTOOLBARS:',len(toolbars))
for tb in toolbars:
    print('\n== %s row=%s =='%(tb['name'],tb['row']))
    for l in tree_summary(tb['entries'],1): print(l)
print('\nHOTKEYS:',len(spec['hotkeys']))
for h in spec['hotkeys']: print('  %-12s %s (%s)'%(h['key'],h['cmd'],h['kind']))
print('\nICONS:',len(icons))
print('wrote',out_json)
