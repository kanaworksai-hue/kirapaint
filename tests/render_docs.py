# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Renders for the README images.

  blender -b --factory-startup --python tests/render_docs.py -- MODE MODEL OUT_DIR [WIDTH HEIGHT] [key=value ...]

MODE layers   before, facets only, + brush, + sparkle, + outline & doodles  -> layer_0..4.png
MODE presets  one render per preset                                         -> preset_KIRA.png ...
"""

import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import kirapaint  # noqa: E402
from kirapaint import api, core, doodles, nodes  # noqa: E402
from kirapaint.presets import ORDER  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
mode, model, out = argv[0], argv[1], os.path.abspath(argv[2])
width = int(argv[3]) if len(argv) > 3 else 1080
height = int(argv[4]) if len(argv) > 4 else 1080
extra = dict(a.split("=", 1) for a in argv[5:])
os.makedirs(out, exist_ok=True)

kirapaint.register()
import demo_scene  # noqa: E402

scene = bpy.context.scene
objs = demo_scene.load(scene, model, width, height, float(extra.pop("turn", "0")), float(extra.pop("zoom", "1")))
steam = extra.pop("steam", "0") == "1"


def render(name):
    scene.frame_set(scene.frame_current)
    scene.render.filepath = os.path.join(out, name)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)


def undrive(id_block, prefix):
    ad = id_block.animation_data
    if ad:
        for fc in list(ad.drivers):
            if fc.data_path.startswith(prefix):
                ad.drivers.remove(fc)


if mode == "layers":
    demo_scene.studio(scene)
    render("layer_0.png")
    demo_scene.clear_studio(scene)
    api.make_kira(objects=objs, preset=extra.pop("preset", "KIRA"), steam=steam,
                  **{k: float(v) for k, v in extra.items()})
    comp = nodes.comp_group()
    undrive(comp, 'nodes["KP Paint"]')
    sparkle = comp.nodes["KP Sparkle"].inputs["Strength"].default_value
    gp = bpy.data.objects.get(doodles.DOODLE_OBJECT)
    for ob in objs:
        undrive(ob, f'modifiers["{core.OUTLINE_MOD}"]')

    def outline(on):
        for ob in objs:
            mod = ob.modifiers.get(core.OUTLINE_MOD)
            if mod:
                mod.show_render = mod.show_viewport = on

    comp.nodes["KP Paint"].outputs[0].default_value = 0.0
    comp.nodes["KP Sparkle"].inputs["Strength"].default_value = 0.0
    outline(False)
    if gp:
        gp.hide_render = True
    render("layer_1.png")
    comp.nodes["KP Paint"].outputs[0].default_value = 1.0
    render("layer_2.png")
    comp.nodes["KP Sparkle"].inputs["Strength"].default_value = sparkle
    render("layer_3.png")
    outline(True)
    if gp:
        gp.hide_render = False
    render("layer_4.png")
elif mode == "presets":
    for key in ORDER:
        api.make_kira(objects=objs, preset=key, steam=steam)
        render(f"preset_{key}.png")
elif mode == "backgrounds":
    from kirapaint import backgrounds
    keys = extra.pop("only", ",".join(backgrounds.ORDER)).split(",")
    api.make_kira(objects=objs, preset=extra.pop("preset", "KIRA"), steam=steam, background=keys[0])
    for key in keys:
        scene.kirapaint.background = key
        render(f"bg_{key}.png")
print("DOCS OK")
