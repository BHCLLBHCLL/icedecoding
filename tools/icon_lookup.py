# -*- coding: utf-8 -*-
import re, os, io
ROOT = r'C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\lib'
pat = re.compile(r'command_define\s+"([^"]+)"\s+"([^"]+)"\s+([A-Za-z0-9_]+)', re.S)
entries = {}
# Prefer icepak/commands_icepak.tcl and guibase/commands_guibase.tcl as canonical, but merge all with priority order
priority = [r'icepak\commands_icepak.tcl', r'guibase\commands_guibase.tcl']
found = {}
for dirpath, dirs, files in os.walk(ROOT):
    for f in files:
        if not f.endswith('.tcl'):
            continue
        full = os.path.join(dirpath, f)
        try:
            txt = open(full, encoding='latin1').read()
        except Exception:
            continue
        rel = os.path.relpath(full, ROOT)
        for m in pat.finditer(txt):
            name, short, icon = m.group(1), m.group(2), m.group(3)
            found.setdefault(name, (rel, short, icon))
# second pass: prefer priority files when icon is no_icon in first-hit
want = ['New project','Open project','Merge project','Reload main version','Save project','Save project as','Print screen','Create image file','Undo','Redo','Home position','Zoom in','Scale to fit','Rotate about screen normal','One viewing window','Four viewing windows','Display object names','Orient negative X','Orient positive Y','Orient negative Z','Isometric view','Reverse orientation','Power and temperature limits','Generate mesh','Radiation','Check model','Run solution','Run optimization','Object face','Plane cut','Isosurface','Point','Surface probe','Variation plot','History plot','Trials plot','Transient settings','Load solution ID','Summary report','Power and temperature values','Edit object','Delete object','Move object','Copy object','Align and morph faces','Align faces - move only','Align object centers','Align face centers','Morph faces','Morph edges','Edit toolbars','Default shading','Selected solid shading','Object names','No object names','Selected object names','Coord axes','Visible grid','Origin marker','Display rulers','Display project title','Display ANSYS logo','Display current date','Display construction lines','Display construction points','Display mesh','Mouse position','Depthcue','Tcl console','Lights','Set background','Edit priorities','Edit cutouts','Create material library','Show objects by material','Show objects by property','Show objects by type','Show metal fractions','Basic settings','Advanced settings','Parallel settings','Patch temperatures','Create Krylov ROM','Solution monitor','Define trials','Define report','Object face (node)','Object face (facet)','Min/max locations','Convergence plot','3D Variation plot','Network temperature plot','Postprocessing units','Load post objects from file','Save post objects to file','Rescale vectors','Create zoom-in model','Display powermap property','HTML report','Solution overview','Summary report','Point report','Full report','Network block values','Fan operating points','EM heat losses','Solar loads','Write Autotherm file','Import CSV/Excel','IDF file','New board','Update board','Import IDX file','Import Electronics Cooling XML','Import Networks','Import JEDEC PTD/JEP30 file','Powermaps','ANSYS Electronics Desktop script','Export CSV/Excel','Export IDF file','Export Electronics Cooling XML','Export Networks','Export JEDEC PTD/JEP30 file','EM Mapping','Volumetric heat losses','Surface heat losses','Pack project','Unpack project','Cleanup','Command prompt','Quit','About Icepak','Help','Icepak on the Web','Customer Portal','List shortcuts','Summary (HTML)','Location','Distance','Angle','Unit vector','Unit normal','Bounding box','Traces','Net info','Trace info','Add marker','Clear markers','Add rubber band','Clear rubber bands','Visible','Find in tree','Find','Show clipboard','Clear clipboard','Snap to grid','Preferences','Annotations','Mouse bindings','Text Editor','Save user view','Clear user views','Write user views to file','Read user views from file','Nearest axis','Radiation form factors','Check model','Default shading','Wireframe shading','Solid shading','Solid/Wire shading','Hidden line shading','Current assembly object names','Refresh Input Data','Generate mesh','Toggle object active','Toggle object visible','Toggle object shading','Open/close tree node','Open/close model subtree','Edit object or postprocessing object','Reload main version','Run optimization','Run solution']
for n in want:
    if n in found:
        rel, short, icon = found[n]
        print('%-34s -> %-24s (short=%s)' % (n, icon, short))
        if icon == 'no_icon':
            print('    ^^ first file:', rel)
    else:
        print('%-34s -> NOT FOUND' % n)
