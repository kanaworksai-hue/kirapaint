# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Chalk doodles (stars, hearts, swirls, sparkles, optional steam) on a Grease Pencil sheet behind the
object, laid out in screen space around it so they never cover it. Twinkles flicker; everything fades
in with scene.kirapaint.paint."""

import math
import random

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

from . import backgrounds, core

DOODLE_OBJECT = "KiraPaint Doodles"
CHALK = (0.95, 0.92, 0.88, 1.0)
STEAM = (1.0, 0.85, 0.6, 1.0)
TWINKLE = (1.8, 1.75, 1.6, 1.0)   # brighter than white: the sparkle glare turns these into stars

# screen slots (x, y in -1..1 of the camera frame) and the doodle each one gets
SLOTS = (
    (-0.74, 0.80, "STAR"), (0.70, 0.74, "HEART"), (-0.84, 0.20, "SWIRL"), (0.84, 0.30, "CROSS"),
    (-0.70, -0.56, "HEART"), (0.76, -0.60, "STAR"), (-0.30, 0.90, "CROSS"), (0.36, 0.88, "TWINKLE"),
    (0.02, -0.86, "TWINKLE"), (-0.48, -0.84, "CROSS"), (0.50, -0.86, "SWIRL"), (0.88, -0.12, "TWINKLE"),
    (-0.88, -0.16, "TWINKLE"), (-0.58, 0.52, "TWINKLE"), (0.60, 0.48, "STAR"), (0.20, -0.70, "HEART"),
    (-0.90, 0.92, "TWINKLE"), (0.90, 0.92, "CROSS"), (-0.90, -0.90, "STAR"), (0.90, -0.88, "TWINKLE"),
    (-0.92, 0.55, "HEART"), (0.92, 0.60, "TWINKLE"), (-0.10, 0.94, "STAR"), (0.12, -0.94, "CROSS"),
)


def _wobble(points, rng, amount):
    return [(x + rng.uniform(-amount, amount), y + rng.uniform(-amount, amount)) for x, y in points]


def _star(s, n=5, inner=0.45):
    return [(math.cos(math.pi / 2 + i * math.pi / n) * (s if i % 2 == 0 else s * inner),
             math.sin(math.pi / 2 + i * math.pi / n) * (s if i % 2 == 0 else s * inner)) for i in range(2 * n)]


def _heart(s, steps=36):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * s / 17, y * s / 17))
    return pts


def _swirl(s, turns=2.2, steps=48):
    return [(math.cos(t) * s * i / steps, math.sin(t) * s * i / steps)
            for i in range(1, steps + 1) for t in [turns * 2 * math.pi * i / steps]]


def _twinkle(s):
    pts = []
    for i in range(8):
        a = math.pi / 2 + i * math.pi / 4
        r = s if i % 2 == 0 else s * 0.22
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return pts


def _steam(s, height, steps=30, phase=0.0):
    return [(math.sin(phase + 2.4 * math.pi * i / steps) * s * 0.35, height * i / steps) for i in range(steps)]


def _gp_material(name, color, fill=False):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        bpy.data.materials.create_gpencil_data(mat)
    gp = mat.grease_pencil
    gp.color = color
    gp.show_stroke = not fill
    gp.show_fill = fill
    if fill:
        gp.fill_color = color
    return mat


def _screen_to_world(cam, scene, u, v, distance):
    frame = cam.data.view_frame(scene=scene)
    xs = [c.x for c in frame]
    ys = [c.y for c in frame]
    d = -frame[0].z
    local = Vector(((min(xs) + (u + 1) / 2 * (max(xs) - min(xs))),
                    (min(ys) + (v + 1) / 2 * (max(ys) - min(ys))), -d)) * (distance / d)
    return cam.matrix_world @ local, (max(ys) - min(ys)) / 2 * distance / d


def remove_doodles(scene=None):
    ob = bpy.data.objects.get(DOODLE_OBJECT)
    if ob is not None:
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            bpy.data.grease_pencils.remove(data)


def add_doodles(scene, objects, steam=False, seed=7, background=None):
    remove_doodles(scene)
    cam = core.ensure_camera(scene, objects)
    center, radius = core.bounds(objects)
    cam_pos = cam.matrix_world.translation
    dist = (center - cam_pos).length + radius * 1.2
    plane_center, half_h = _screen_to_world(cam, scene, 0.0, 0.0, dist)

    gpd = bpy.data.grease_pencils.new(DOODLE_OBJECT)
    ob = bpy.data.objects.new(DOODLE_OBJECT, gpd)
    scene.collection.objects.link(ob)
    sheet = Matrix.Translation(plane_center) @ cam.matrix_world.to_quaternion().to_matrix().to_4x4()
    ob.matrix_world = sheet
    inv = sheet.inverted()

    chalk = _gp_material("KiraPaint Chalk", chalk_color(background))
    steam_mat = _gp_material("KiraPaint Steam", steam_color(background))
    twinkle = _gp_material("KiraPaint Twinkle", twinkle_color(background), fill=True)
    for m in (chalk, steam_mat, twinkle):
        gpd.materials.append(m)

    # where the object sits on screen, so nothing is drawn on top of it
    # (projected bounding box corners, as an ellipse with a small margin)
    uv = []
    for o in objects:
        for c in o.bound_box:
            p = world_to_camera_view(scene, cam, o.matrix_world @ Vector(c))
            uv.append((p.x * 2 - 1, p.y * 2 - 1))
    lo_u, hi_u = min(p[0] for p in uv), max(p[0] for p in uv)
    lo_v, hi_v = min(p[1] for p in uv), max(p[1] for p in uv)
    obj_u, obj_v = (lo_u + hi_u) / 2, (lo_v + hi_v) / 2
    obj_ru, obj_rv = max((hi_u - lo_u) / 2, 0.05), max((hi_v - lo_v) / 2, 0.05)

    rng = random.Random(seed)
    unit = half_h * 0.065
    width = half_h * 0.0045
    ink, sparkles = [], []
    for u, v, kind in SLOTS:
        if abs(u - obj_u) < obj_ru * 1.05 + 0.08 and abs(v - obj_v) < obj_rv * 1.05 + 0.06:
            continue
        if steam and abs(u - obj_u) < 0.3 and v > obj_v:
            continue   # the steam goes here
        pos, _ = _screen_to_world(cam, scene, u, v, dist)
        p = inv @ pos
        s = unit * rng.uniform(0.75, 1.25)
        if kind == "STAR":
            ink.append((_wobble(_star(s), rng, s * 0.04), True, p))
        elif kind == "HEART":
            ink.append((_wobble(_heart(s), rng, s * 0.03), True, p))
        elif kind == "SWIRL":
            ink.append((_wobble(_swirl(s * 0.9), rng, s * 0.02), False, p))
        elif kind == "CROSS":
            ink.append(([(0, -s * 0.7), (0, s * 0.7)], False, p))
            ink.append(([(-s * 0.45, 0), (s * 0.45, 0)], False, p))
        else:
            sparkles.append((_twinkle(s * 0.8), True, p))
    steam_strokes = []
    if steam:
        top, _ = _screen_to_world(cam, scene, obj_u, min(obj_v + obj_rv * 0.95, 0.9), dist)
        tp = inv @ top
        for i, dx in enumerate((-1.0, 0.0, 1.0)):
            pts = _steam(unit * 1.4, unit * 5.5, phase=i * 1.3)
            steam_strokes.append(([(x + dx * unit * 1.2, y) for x, y in pts], False, tp))

    layers = []
    for name, strokes, mat_index, lw in (("Ink", ink, 0, width), ("Steam", steam_strokes, 1, width * 1.3),
                                          ("Twinkle", sparkles, 2, width * 0.6)):
        if not strokes:
            continue
        layer = gpd.layers.new(name)
        layer.use_lights = False
        drawing = layer.frames.new(scene.frame_start).drawing
        drawing.add_strokes([len(pts) for pts, _, _ in strokes])
        for stroke, (pts, cyclic, origin) in zip(drawing.strokes, strokes):
            stroke.cyclic = cyclic
            stroke.material_index = mat_index
            for point, (x, y) in zip(stroke.points, pts):
                point.position = (origin.x + x, origin.y + y, origin.z)
                point.radius = lw
                point.opacity = 1.0
        layers.append(name)

    for name in layers:
        expr = "p * (0.55 + 0.45 * sin(frame * 0.4))" if name == "Twinkle" else "p"
        fc = gpd.driver_add(f'layers["{name}"].opacity')
        drv = fc.driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "p"
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = scene
        var.targets[0].data_path = "kirapaint.paint"
        drv.expression = expr
    return ob


def chalk_color(background):
    spec = backgrounds.BACKGROUNDS.get(background or "")
    if spec is None:
        return CHALK
    r, g, b, _ = backgrounds.hex_to_linear(spec["doodle"])
    return (r, g, b, 1.0)


def _is_dark(background):
    r, g, b, _ = chalk_color(background)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4   # light chalk = dark backdrop


def steam_color(background):
    return STEAM if background is None or _is_dark(background) else chalk_color(background)


def twinkle_color(background):
    if background is None or _is_dark(background):
        return TWINKLE
    r, g, b, _ = chalk_color(background)
    return (r * 1.4, g * 1.4, b * 1.4, 1.0)


def recolor(background):
    """Doodles stay readable: white chalk on dark backdrops, dark ink on light ones."""
    for name, color, fill in (("KiraPaint Chalk", chalk_color(background), False),
                              ("KiraPaint Steam", steam_color(background), False),
                              ("KiraPaint Twinkle", twinkle_color(background), True)):
        mat = bpy.data.materials.get(name)
        if mat is not None and mat.grease_pencil is not None:
            mat.grease_pencil.color = color
            if fill:
                mat.grease_pencil.fill_color = color
