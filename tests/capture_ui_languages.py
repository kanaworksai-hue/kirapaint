# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Screenshots of the KiraPaint panel in three language setups (GUI Blender, KiraPaint installed as an extension).

  BLENDER_USER_RESOURCES=<temp profile> blender --python tests/capture_ui_languages.py -- OUT_DIR

Writes panel_auto_ja.png (Blender in Japanese), panel_forced_ja.png (Blender in English, panel set to 日本語)
and panel_en.png. Blender quits when done. Preferences are not saved.
"""

import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.use_preferences_save = False

STEPS = []


def package():
    import importlib
    base = bpy.types.KIRAPAINT_OT_make_kira.__module__.rsplit(".", 1)[0]
    return base, importlib.import_module(base + ".api"), importlib.import_module(base + ".ui")


def area3d():
    win = bpy.context.window_manager.windows[0]
    return win, max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)


def setup():
    import demo_scene
    base, api, ui = package()
    scene = bpy.context.scene
    objs = demo_scene.load(scene, "SUZANNE", 1080, 1080, -30, 1.1)
    api.make_kira(objects=objs, preset="KIRA", background="POLKA")
    for o in scene.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = None
    # the sidebar opens on "Tool" when nothing is selected; show the KiraPaint panels there just for the screenshot
    for cls in ui.CLASSES:
        bpy.utils.unregister_class(cls)
    for cls in ui.CLASSES:
        cls.bl_category = "Tool"
        bpy.utils.register_class(cls)
    win, area = area3d()
    sp = area.spaces.active
    sp.region_3d.view_perspective = "CAMERA"
    sp.shading.type = "MATERIAL"
    sp.show_region_ui = True
    sp.overlay.show_overlays = False


def language(blender, panel):
    view = bpy.context.preferences.view
    view.language = blender
    view.use_translate_interface = True
    view.use_translate_tooltips = True
    base, _, _ = package()
    bpy.context.preferences.addons[base].preferences.ui_language = panel


def shot(name):
    """Full-window screenshot, then crop the 3D view's sidebar plus a slice of the viewport."""
    win, area = area3d()
    full = os.path.join(OUT, "_full.png")
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        bpy.ops.screen.screenshot(filepath=full)
    img = bpy.data.images.load(full)
    scale = img.size[0] / win.width
    ui = next(r for r in area.regions if r.type == "UI")
    x0 = int((ui.x - 260) * scale)
    x1 = int((ui.x + ui.width) * scale)
    top = int((win.height - (ui.y + ui.height)) * scale)
    bottom = int((win.height - ui.y) * scale)
    bpy.data.images.remove(img)
    with open(os.path.join(OUT, name + ".crop"), "w") as fh:
        fh.write(f"{x0} {top} {x1} {bottom}")
    os.replace(full, os.path.join(OUT, name))
    print("SHOT", name, flush=True)


STEPS = [
    setup,
    lambda: language("ja_JP", "AUTO"), lambda: shot("panel_auto_ja.png"),
    lambda: language("en_US", "JA"), lambda: shot("panel_forced_ja.png"),
    lambda: language("en_US", "AUTO"), lambda: shot("panel_en.png"),
    lambda: bpy.ops.wm.quit_blender(),
]


def tick():
    if not STEPS:
        return None
    step = STEPS.pop(0)
    try:
        step()
    except Exception as err:   # report and quit rather than hang
        print("CAPTURE ERROR", repr(err), flush=True)
        bpy.ops.wm.quit_blender()
        return None
    return 2.5


bpy.app.timers.register(tick, first_interval=4.0)
