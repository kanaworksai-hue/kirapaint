# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a before / after pair of any model.

  blender -b --factory-startup --python tests/render_demo.py -- MODEL OUT_PREFIX [PRESET] [WIDTH] [HEIGHT] [key=value ...]

MODEL: a .glb/.gltf/.fbx/.obj file, or SUZANNE. Writes OUT_PREFIX_before.png and OUT_PREFIX_after.png.
The "before" render uses the same camera with a plain grey background and a soft studio light.
Extra key=value pairs: look overrides (sparkle=1.0 ...), turn=DEG, zoom=X, steam=1, doodles=0.
"""

import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import kirapaint  # noqa: E402
from kirapaint import api  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
model, prefix = argv[0], os.path.abspath(argv[1])
preset = argv[2] if len(argv) > 2 else "KIRA"
width = int(argv[3]) if len(argv) > 3 else 1080
height = int(argv[4]) if len(argv) > 4 else 1350
extra = dict(a.split("=", 1) for a in argv[5:])

kirapaint.register()
import demo_scene  # noqa: E402

scene = bpy.context.scene
objs = demo_scene.load(scene, model, width, height, float(extra.pop("turn", "0")), float(extra.pop("zoom", "1")))
demo_scene.studio(scene)
scene.render.filepath = prefix + "_before.png"
bpy.ops.render.render(write_still=True)

demo_scene.clear_studio(scene)
bg = extra.pop("background", None)
look = {k: float(v) for k, v in extra.items() if k not in ("doodles", "steam")}
print(api.make_kira(objects=objs, preset=preset, setup_scene=True, background=bg,
                    doodles_on=extra.get("doodles", "1") != "0", steam=extra.get("steam", "0") == "1", **look))
scene.frame_set(scene.frame_current)
scene.render.filepath = prefix + "_after.png"
bpy.ops.render.render(write_still=True)
print("DEMO OK", prefix)
