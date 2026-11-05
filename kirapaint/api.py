# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-call Python API, meant for AI agents and scripts.

    import bpy
    bpy.ops.kirapaint.make_kira(preset="KIRA", target="SELECTED_OR_ALL", setup_scene=True, doodles=True)

or, from Python inside Blender:

    from <this package> import api
    api.make_kira(preset="dreamy", sparkle=1.0)
"""

import bpy

from . import backgrounds, core, doodles, nodes
from .presets import LOOK_KEYS, ORDER, PRESETS


def preset_key(name):
    key = (name or "KIRA").strip().upper().replace(" ", "_").replace("-", "_")
    if key not in PRESETS:
        raise ValueError(f"Unknown preset {name!r}. Choose one of: {', '.join(ORDER)}")
    return key


def resolve_objects(target="SELECTED_OR_ALL", names=None, context=None):
    context = context or bpy.context
    scene = context.scene
    if names:
        objs = [scene.objects[n] for n in names if n in scene.objects]
    elif target == "ALL":
        objs = list(scene.objects)
    else:
        objs = list(context.selected_objects)
        if not objs and target == "SELECTED_OR_ALL":
            objs = list(scene.objects)
    return [o for o in objs if o.type in core.MESHY and o.name != doodles.DOODLE_OBJECT]


def current_look(scene):
    s = scene.kirapaint
    return {k: getattr(s, k) for k in LOOK_KEYS}


def make_kira(objects=None, preset=None, target="SELECTED_OR_ALL", setup_scene=True, background=None,
              doodles_on=None, steam=False, outline=True, paint=1.0, context=None, **look):
    """Apply KiraPaint. Returns a short human-readable report.

    preset: KIRA (default) SOFT INK DREAMY; None keeps the scene's current look on later calls
    look overrides (0-1 unless noted): stroke, facets (0.25-4), gloss, iridescence, brush (px at 1080p),
        sparkle, bloom, outline (width multiplier, 0 = none)
    background: one of NIGHT STARRY SAKURA POLKA MINT SODA LEMON PEACH SUNSET STUDIO, or KEEP (your own
        world stays; reflections get less colorful). None keeps the scene's current choice (NIGHT at first)
    doodles_on: True/False; None = add them with a new scene setup, leave them as they are otherwise
    """
    context = context or bpy.context
    scene = context.scene
    objs = objects if objects is not None else resolve_objects(target, context=context)
    objs = [o for o in objs if o.type in core.MESHY and o.name != doodles.DOODLE_OBJECT]
    if not objs:
        return "No mesh objects to change."
    bad = set(look) - set(LOOK_KEYS)
    if bad:
        raise ValueError(f"Unknown option(s) {sorted(bad)}. Use: {', '.join(LOOK_KEYS)}")
    s = scene.kirapaint
    first_time = not core.kira_objects(scene)
    if preset not in (None, "", "KEEP") or first_time:
        key = preset_key(preset if preset not in (None, "", "KEEP") else "KIRA")
        s.updating = True
        try:
            s.preset = key
        finally:
            s.updating = False
        values = {k: PRESETS[key][k] for k in LOOK_KEYS}
    else:
        key = s.preset
        values = current_look(scene)
    values.update({k: float(v) for k, v in look.items()})

    if background in (None, "", "KEEP_CURRENT"):
        background = s.background
    background = {"PAINTED": "NIGHT"}.get(str(background).upper(), str(background).upper())
    if background != "KEEP" and background not in backgrounds.BACKGROUNDS:
        raise ValueError(f"Unknown background {background!r}. Choose one of: {', '.join(backgrounds.ORDER)}, KEEP")

    nodes.build_surface_group(scene)
    changed, skipped = core.apply_to_objects(objs, scene)
    if setup_scene:
        core.setup_scene(scene, objs, values, background)
    else:
        nodes.build_comp_group(scene)
    width = values["outline"]
    for ob in objs:
        if outline and width > 0:
            core.add_outline(ob, width, scene)
        else:
            core.remove_outline(ob)
    if doodles_on or (doodles_on is None and setup_scene and bpy.data.objects.get(doodles.DOODLE_OBJECT) is None):
        doodles.add_doodles(scene, objs, steam=steam, background=background)
    elif doodles_on is False:
        doodles.remove_doodles(scene)

    s.updating = True
    try:
        s.background = background
        for k in LOOK_KEYS:
            setattr(s, k, values[k])
    finally:
        s.updating = False
    nodes.set_look(values, scene)
    core.set_glints(values["sparkle"])
    s.paint = paint
    report = f"KiraPaint {PRESETS.get(key, {}).get('label', key)} applied to {changed} object(s)."
    if skipped:
        report += f" Skipped materials without a Principled BSDF: {', '.join(skipped)}."
    return report


def remove(objects=None, scene_too=True, context=None):
    context = context or bpy.context
    scene = context.scene
    objs = objects if objects is not None else core.kira_objects(scene)
    core.remove_from_objects(objs)
    if scene_too:
        core.remove_scene(scene)
        doodles.remove_doodles(scene)
    return f"KiraPaint removed from {len(objs)} object(s)."


def list_presets():
    return [(k, PRESETS[k]["label"], PRESETS[k]["description"]) for k in ORDER]


def list_backgrounds():
    return [(k, backgrounds.BACKGROUNDS[k]["label"], backgrounds.BACKGROUNDS[k]["ja"]) for k in backgrounds.ORDER]
