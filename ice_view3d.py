# -*- coding: utf-8 -*-
"""
P3: 3D viewport completeness — pure helpers (math + VTK actor factories).

Kept headless-testable: geometry math is pure python; actor builders create
vtk props guarded by optional vtk import.
"""
import math
import datetime


# --------------------------------------------------------------------------- #
# Snap / interaction math (Icepak Preferences->Interaction)
# --------------------------------------------------------------------------- #

def snap_value(v, step):
    """Snap a scalar to the nearest grid step (0 -> exact 0.0)."""
    if not step or step <= 0:
        return v
    return round(v / step) * step


def snap_point(p, step):
    return tuple(snap_value(v, step) for v in p)


def clamp_to_box(p, lo, hi):
    """Restrict movement to cabinet: clamp coordinates into [lo, hi]."""
    return tuple(min(max(p[i], lo[i]), hi[i]) for i in range(len(p)))


def allowed_delta(delta, axes):
    """Interaction rule: Motion allowed in direction X/Y/Z."""
    out = []
    for i, d in enumerate(delta):
        out.append(d if axes[i] else 0.0)
    return tuple(out)


def box_contains(p, lo, hi):
    return all(lo[i] <= p[i] <= hi[i] for i in range(len(p)))


# --------------------------------------------------------------------------- #
# Alignment / morph engine (Icepak align/match commands, red/yellow workflow)
# --------------------------------------------------------------------------- #

def axis_of_edge(edge):
    """Return the axis index (0/1/2) an aligned edge varies along, else -1."""
    dirs = []
    for i, (a, b) in enumerate(zip(edge[0], edge[1])):
        if abs(b - a) > 1e-12:
            dirs.append(i)
    return dirs[0] if len(dirs) == 1 else -1


def nearest_face(lo, hi, p):
    """Which face (axis index + sign) of the box is nearest to point p."""
    best = (0, 0, None)
    for i in range(3):
        for sign in (0, 1):
            d = abs(p[i] - (lo[i] if sign == 0 else hi[i]))
            if best[2] is None or d < best[2]:
                best = (i, 1 if sign == 1 else -1, d)
    return best[0], best[1]


def face_center(lo, hi, axis, sign):
    c = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    c[axis] = hi[axis] if sign > 0 else lo[axis]
    return tuple(c)


def translate_box(box, delta):
    lo, hi = box
    dl = tuple(lo[i] + delta[i] for i in range(3))
    dh = tuple(hi[i] + delta[i] for i in range(3))
    return dl, dh


def stretch_box_to_face(box, axis, sign, target):
    """Morph: change the box extent along axis so the signed face == target."""
    lo, hi = box
    new = list(hi if sign > 0 else lo)
    new[axis] = target
    if sign > 0:
        return lo, tuple(new)
    return tuple(new), hi


def align_face_move(box_a, face_a, box_b, face_b):
    """Center-align face_a of box_a to face_b of box_b by translation only."""
    axis_a, sign_a = face_a
    axis_b, sign_b = face_b
    ca = face_center(box_a[0], box_a[1], axis_a, sign_a)
    cb = face_center(box_b[0], box_b[1], axis_b, sign_b)
    return translate_box(box_a, tuple(cb[i] - ca[i] for i in range(3)))


def align_face_stretch(box_a, face_a, box_b, face_b):
    """Icepak LMB face align: stretch box_a's length so faces coincide."""
    axis_a, sign_a = face_a
    axis_b, sign_b = face_b
    ca = face_center(box_a[0], box_a[1], axis_a, sign_a)
    cb = face_center(box_b[0], box_b[1], axis_b, sign_b)
    moved = translate_box(box_a, tuple(cb[i] - ca[i] for i in range(3)))
    return stretch_box_to_face(moved, axis_a, sign_a, cb[axis_a])


def align_centers(box_a, box_b):
    """Align body centers: translate box_a so its center matches box_b."""
    ca = tuple((box_a[0][i] + box_a[1][i]) / 2.0 for i in range(3))
    cb = tuple((box_b[0][i] + box_b[1][i]) / 2.0 for i in range(3))
    return translate_box(box_a, tuple(cb[i] - ca[i] for i in range(3)))


def match_face(box_a, face_a, box_b, face_b):
    """Morph faces: same size & position on the chosen faces."""
    axis_a, sign_a = face_a
    axis_b, sign_b = face_b
    result = align_face_move(box_a, face_a, box_b, face_b)
    # stretch on the two tangent axes to match box_b face extents
    lo, hi = result
    lo2, hi2 = box_b
    for i in range(3):
        if i == axis_a:
            continue
        lo = list(lo)
        hi = list(hi)
        lo[i] = min(lo[i], lo2[i])
        hi[i] = max(hi[i], hi2[i])
        lo = tuple(lo)
        hi = tuple(hi)
    return lo, hi


def match_edge(box_a, edge_a, box_b, edge_b, axis):
    """Morph edges: translate + stretch so edge_a coincides with edge_b."""
    # translate: first endpoint of edge_a to first endpoint of edge_b
    delta = tuple(edge_b[0][i] - edge_a[0][i] for i in range(3))
    result = translate_box(box_a, delta)
    lo, hi = result
    e0, e1 = edge_a
    # stretch along the varying axis so both endpoints meet
    for i in range(3):
        if abs(edge_b[0][i] - edge_b[1][i]) > 1e-12:
            lo = list(lo)
            hi = list(hi)
            lo[i] = min(edge_b[0][i], edge_b[1][i]) \
                if lo[i] > hi[i] else lo[i]
            lo[i] = min(lo[i], edge_b[0][i], edge_b[1][i])
            hi[i] = max(hi[i], edge_b[0][i], edge_b[1][i])
            lo = tuple(lo)
            hi = tuple(hi)
    return lo, hi


# --------------------------------------------------------------------------- #
# box / circle pick support (AABB based, headless testable)
# --------------------------------------------------------------------------- #

def box_pick(object_bounds, rect, screen_to_world):
    """object_bounds: name -> (lo, hi) in world; rect: (x0,y0,x1,y1) screen.
    screen_to_world: (sx, sy) -> world point at the object's mid-depth."""
    hits = []

    def project(bounds):
        lo, hi = bounds
        c = tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
        return c

    for name, bounds in object_bounds.items():
        c = project(bounds)
        sx, sy = screen_to_world(c)
        if min(rect[0], rect[2]) <= sx <= max(rect[0], rect[2]) and \
           min(rect[1], rect[3]) <= sy <= max(rect[1], rect[3]):
            hits.append(name)
    return hits


def circle_pick(object_bounds, center_screen, radius, screen_to_world):
    hits = []
    for name, bounds in object_bounds.items():
        c = tuple((bounds[0][i] + bounds[1][i]) / 2.0 for i in range(3))
        sx, sy = screen_to_world(c)
        if (sx - center_screen[0]) ** 2 + (sy - center_screen[1]) ** 2 <= \
                radius ** 2:
            hits.append(name)
    return hits


# --------------------------------------------------------------------------- #
# Display layer actors (guarded vtk import)
# --------------------------------------------------------------------------- #

def today_string():
    return datetime.date.today().strftime("%b %d, %Y")


def make_display_actors(renderer, bounds, prefix="_ice_lay"):
    """Create overlay actors in the renderer for the display layer toggles.
    Returns dict name -> (actor, enabled_ctor)."""
    try:
        import vtk
    except Exception:
        return {}
    out = {}
    lo, hi = bounds
    size = tuple(hi[i] - lo[i] for i in range(3))

    def add_actor(name, actor):
        renderer.AddActor(actor)
        out[name] = actor

    # visible grid: points on cabinet faces
    grid = vtk.vtkPolyData()
    pts = vtk.vtkPoints()
    n = 10
    for i in range(n + 1):
        f = i / float(n)
        x = lo[0] + f * size[0]
        pts.InsertNextPoint(x, lo[1], lo[2])
    for i in range(n + 1):
        f = i / float(n)
        y = lo[1] + f * size[1]
        pts.InsertNextPoint(lo[0], y, lo[2])
    for i in range(n + 1):
        f = i / float(n)
        z = lo[2] + f * size[2]
        pts.InsertNextPoint(lo[0], lo[1], z)
    grid.SetPoints(pts)
    ga = vtk.vtkActor()
    ga.SetMapper(vtk.vtkPolyDataMapper())
    ga.GetMapper().SetInputData(grid)
    ga.GetProperty().SetColor(0.55, 0.59, 0.63)
    ga.GetProperty().SetPointSize(2)
    ga.SetPickable(0)
    add_actor("grid", ga)

    # origin marker
    om = vtk.vtkAxesActor()
    om.SetTotalLength(0.25 * max(size), 0.25 * max(size), 0.25 * max(size))
    om.SetShaftTypeToLine()
    om.SetPickable(0)
    add_actor("origin", om)

    # rulers: three axes with ticks on cabinet edges
    rul = vtk.vtkAxesActor()
    rul.SetTotalLength(1.05 * size[0], 1.05 * size[1], 1.05 * size[2])
    rul.SetPickable(0)
    add_actor("rulers", rul)

    # project title
    pt = vtk.vtkTextActor()
    pt.SetInput("Project")
    pt.GetTextProperty().SetFontSize(15)
    pt.GetTextProperty().SetColor(0.15, 0.27, 0.40)
    pt.SetPosition(0.40, 0.985)
    pt.GetTextProperty().SetJustificationToCentered()
    add_actor("title", pt)

    # current date
    dt = vtk.vtkTextActor()
    dt.SetInput(today_string())
    dt.GetTextProperty().SetFontSize(11)
    dt.GetTextProperty().SetColor(0.30, 0.34, 0.38)
    dt.SetPosition(0.985, 0.012)
    dt.GetTextProperty().SetJustificationToRight()
    add_actor("date", dt)

    # mesh lines placeholder (filled by set_mesh_actor later)
    mesh = vtk.vtkActor()
    mapper = vtk.vtkPolyDataMapper()
    pd = vtk.vtkPolyData()
    pts2 = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    pts2.InsertNextPoint(lo)
    pts2.InsertNextPoint(hi)
    lines.InsertNextCell(2)
    lines.InsertCellPoint(0)
    lines.InsertCellPoint(1)
    pd.SetPoints(pts2)
    pd.SetLines(lines)
    mapper.SetInputData(pd)
    mesh.SetMapper(mapper)
    mesh.GetProperty().SetColor(0.35, 0.55, 0.75)
    mesh.SetPickable(0)
    add_actor("mesh", mesh)
    return out


# --------------------------------------------------------------------------- #
# P3b: interactive alignment session (red/yellow, MMB accept, RMB finish)
# --------------------------------------------------------------------------- #

class AlignSession(object):
    """Two-pick alignment state machine (Icepak Alignment toolbar)."""

    PICK_SOURCE = "pick_source"
    PICK_TARGET = "pick_target"

    def __init__(self, op="align_centers"):
        self.op = op
        self.state = None
        self.source = None      # bounds tuple (lo, hi)
        self.target = None

    def reset(self):
        self.state = None
        self.source = None
        self.target = None

    def start(self, op):
        self.op = op
        self.reset()
        self.state = self.PICK_SOURCE

    def pick(self, bounds, point=None):
        """Feed next pick. Returns ('pick_source'|'pick_target'|'applied'|'ignored', result)."""
        if self.state is None:
            return ("ignored", None)
        if self.state == self.PICK_SOURCE:
            self.source = bounds
            self.state = self.PICK_TARGET
            return ("pick_source", None)
        if self.state == self.PICK_TARGET:
            self.target = bounds
            result = self.apply()
            op = self.op
            self.reset()
            self.state = self.PICK_SOURCE
            self.op = op
            return ("applied", result if result is not None else self.source)
        return ("ignored", None)

    def apply(self):
        from ice_view3d import (align_face_move, align_face_stretch,
                                align_centers, match_face)
        if not self.source or not self.target:
            return None
        a, b = self.source, self.target
        if self.op == "align_centers":
            return align_centers(a, b)
        fa = _face_toward(a, _mid(b))
        fb = _face_toward(b, _mid(a))
        if self.op == "align_face_centers":
            return align_face_move(a, fa, b, fb)
        if self.op == "align_face_stretch":
            return align_face_stretch(a, fa, b, fb)
        if self.op == "align_face_move" or self.op == "match_edge":
            return align_face_move(a, fa, b, fb)
        if self.op == "match_face":
            return match_face(a, fa, b, fb)
        return None


def _face_toward(bounds, other_mid):
    """Choose the box face (axis, sign) facing the other box's center."""
    lo, hi = bounds
    my = _mid(bounds)
    d = [other_mid[i] - my[i] for i in range(3)]
    axis = max(range(3), key=lambda i: abs(d[i]))
    sign = 1 if d[axis] >= 0 else -1
    return (axis, sign)


def mesh_actor_from_lines(lines, color=(0.25, 0.45, 0.70), opacity=0.9):
    """VTK actor for structured mesh line segments (returns None w/o vtk)."""
    try:
        import vtk
        from vtk.util import numpy_support
        import numpy as np
    except Exception:
        return None
    pts = []
    for x0, y0, z0, x1, y1, z1 in lines:
        pts.append((x0, y0, z0))
        pts.append((x1, y1, z1))
    pd = vtk.vtkPolyData()
    vpts = vtk.vtkPoints()
    vpts.SetData(numpy_support.numpy_to_vtk(
        np.asarray(pts, dtype=float), deep=True))
    pd.SetPoints(vpts)
    cells = vtk.vtkCellArray()
    n = len(pts)
    for i in range(0, n, 2):
        cells.InsertNextCell(2)
        cells.InsertCellPoint(i)
        cells.InsertCellPoint(i + 1)
    pd.SetLines(cells)
    actor = vtk.vtkActor()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(pd)
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetOpacity(opacity)
    actor.SetPickable(0)
    return actor


# ---- P19-D6: Show metal fractions viewport display (per-layer copper) --------
_LAYER_COLORS = [(0.85, 0.60, 0.20), (0.20, 0.60, 0.85), (0.85, 0.30, 0.25),
                 (0.35, 0.75, 0.35), (0.65, 0.35, 0.75), (0.75, 0.70, 0.20),
                 (0.25, 0.70, 0.65), (0.70, 0.45, 0.25), (0.45, 0.45, 0.75),
                 (0.80, 0.55, 0.65)]


def metal_fraction_actors(renderer, icb, scale=0.001):
    """Build per-layer copper block actors for the Show metal fractions viewport
    display.  Shapes (layer x0 y0 x1 y1 ...) become thin boxes stacked along z by
    layer thickness; colors cycle per layer.  Returns a dict:
      {'actors': [...], 'legend': [(layer, material, fraction), ...]}
    Returns {'actors': [], 'legend': []} when vtk/geometry unavailable."""
    try:
        import vtk
        from ice_ecad import icb_metal_fractions
    except Exception:
        return {'actors': [], 'legend': []}
    bl = icb.get('board_outline') or []
    layers = icb.get('layers') or []
    shapes = icb.get('shapes') or []
    if not bl or not layers:
        return {'actors': [], 'legend': []}
    xs = [p[0] for p in bl]
    ys = [p[1] for p in bl]
    fracs = icb_metal_fractions(icb)
    layer_rows = []
    for row in layers:
        parts = [p.strip() for p in row.split(',')]
        if len(parts) < 3:
            continue
        thick = 1.0
        if len(parts) > 3 and parts[3].replace('.', '').isdigit():
            try:
                thick = float(parts[3])
            except ValueError:
                pass
        layer_rows.append((parts[0], parts[1], thick))
    if not layer_rows:
        return {'actors': [], 'legend': []}
    board_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    actors = []
    legend = []
    z = 0.0
    for i, (lname, mat, thick) in enumerate(layer_rows):
        z0, z1 = z, z + max(thick, 0.05) * scale
        color = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        for row in shapes:
            parts = row.split()
            if len(parts) < 5 or parts[0] != lname:
                continue
            try:
                sx = [float(v) for v in parts[1::2]]
                sy = [float(v) for v in parts[2::2]]
            except ValueError:
                continue
            if not sx or not sy:
                continue
            x0, x1 = min(sx) * scale, max(sx) * scale
            y0, y1 = min(sy) * scale, max(sy) * scale
            cube = vtk.vtkCubeSource()
            cube.SetBounds(x0, x1, y0, y1, z0, z1)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(cube.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            prop = actor.GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(0.55)
            prop.SetRepresentationToSurface()
            actor.SetPickable(0)
            if renderer is not None:
                renderer.AddActor(actor)
            actors.append(actor)
        f = fracs.get(lname, 0.0)
        legend.append((lname, mat, f))
        z = z1
    return {'actors': actors, 'legend': legend}


def _mid(bounds):
    lo, hi = bounds
    return tuple((lo[i] + hi[i]) / 2.0 for i in range(3))
