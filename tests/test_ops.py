# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator smoke test (headless).

Run:
  "/Applications/Blender 5.2.app/Contents/MacOS/Blender" -b --factory-startup --python tests/test_ops.py
"""

import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kirapaint  # noqa: E402
from kirapaint import api, core, doodles, nodes  # noqa: E402

failures = []


def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        failures.append(label)


try:
    kirapaint.register()
    scene = bpy.context.scene
    s = scene.kirapaint

    # a cube with a normal-mapped, rough material; Suzanne with no material at all
    cube = bpy.data.objects["Cube"]
    mat = bpy.data.materials.new("Rough")
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.7
    bump = tree.nodes.new("ShaderNodeBump")
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    cube.data.materials.clear()
    cube.data.materials.append(mat)
    bpy.ops.mesh.primitive_monkey_add(location=(3, 0, 0))
    monkey = bpy.context.object

    report = api.make_kira(objects=[cube, monkey], preset="KIRA", setup_scene=True)
    print(report)
    check("report counts both objects", "2 object" in report)
    check("surface group inserted on cube", len(nodes.surface_nodes(mat)) == 1)
    check("monkey got a default material", any(sl.material and sl.material.get("kirapaint")
                                               for sl in monkey.material_slots))
    group = nodes.surface_nodes(mat)[0]
    check("bump stays upstream", group.inputs["Normal"].links[0].from_node == bump)
    check("bsdf normal comes from KiraPaint", bsdf.inputs["Normal"].links[0].from_node == group)
    check("roughness value carried", abs(group.inputs["Roughness"].default_value - 0.7) < 1e-6)
    check("outline modifier", cube.modifiers.get(core.OUTLINE_MOD) is not None)
    check("lights collection", bpy.data.collections.get(core.LIGHTS_COLLECTION) is not None)
    check("world", scene.world.name == core.WORLD_NAME)
    s.background = "POLKA"
    check("background switch", scene.world.get("kirapaint_background") == "POLKA")
    check("compositor", scene.compositing_node_group.name == core.COMP_TREE)
    check("doodles", bpy.data.objects.get(doodles.DOODLE_OBJECT) is not None)
    check("EEVEE", scene.render.engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"))

    # sliders reach the node groups
    s.stroke = 0.33
    check("stroke slider", abs(nodes.surface_group().nodes["KP Stroke"].outputs[0].default_value - 0.33) < 1e-6)
    s.brush = 8.0
    k = nodes.comp_group().nodes["KP Brush A"].inputs["Size"].default_value
    check("brush follows resolution", k > 1.0)
    s.preset = "INK"
    check("preset sets outline", abs(s.outline - 2.0) < 1e-6)
    s.outline = 1.5
    mod = cube.modifiers[core.OUTLINE_MOD]
    check("outline width slider", abs(mod.thickness - core.OUTLINE_PER_SIZE * core.local_size(cube) * 1.5) < 1e-6)

    # paint driver
    s.paint = 0.0
    scene.frame_set(scene.frame_current)
    check("paint drives the surface group",
          nodes.surface_group().nodes["KP Paint"].outputs[0].default_value < 1e-6)
    s.paint = 1.0
    scene.frame_set(scene.frame_current)

    # one-call operator
    r = bpy.ops.kirapaint.make_kira(preset="DREAMY", sparkle=1.0, doodles="OFF")
    check("make_kira operator", r == {"FINISHED"})
    check("doodles off", bpy.data.objects.get(doodles.DOODLE_OBJECT) is None)
    check("sparkle override", abs(s.sparkle - 1.0) < 1e-6 and s.preset == "DREAMY")

    # animation helpers
    core.add_reveal(scene, start=1, length=10)
    holder = bpy.data.objects.new("Holder", None)
    scene.collection.objects.link(holder)
    monkey.parent = holder
    core.add_turntable(scene, [monkey], 90.0, start=1, length=10)
    scene.frame_set(1)
    a = monkey.matrix_world.to_euler().z
    scene.frame_set(11)
    b = monkey.matrix_world.to_euler().z
    check("turntable turns parented objects", abs(b - a) > 1.0)
    monkey.parent = None
    check("reveal keys", scene.animation_data is not None and scene.animation_data.action is not None)

    # render a tiny frame
    scene.render.resolution_percentage = 10
    scene.render.filepath = os.path.join(ROOT, "tests", "out", "smoke.png")
    bpy.ops.render.render(write_still=True)
    check("render", os.path.isfile(scene.render.filepath))

    # remove puts everything back
    print(api.remove())
    check("surface group removed", not nodes.surface_nodes(mat))
    check("bump relinked", bsdf.inputs["Normal"].links[0].from_node == bump)
    check("roughness restored", abs(bsdf.inputs["Roughness"].default_value - 0.7) < 1e-6
          and not bsdf.inputs["Roughness"].is_linked)
    check("outline removed", cube.modifiers.get(core.OUTLINE_MOD) is None)
    check("lights removed", bpy.data.collections.get(core.LIGHTS_COLLECTION) is None)
    check("world restored", scene.world is None or scene.world.name != core.WORLD_NAME)
    # Japanese UI: automatic (Blender in Japanese) and by hand (panel menu)
    from kirapaint import i18n, ops as kops
    import bpy.app.translations as T
    check("english by default", i18n.t("Stroke") == "Stroke")
    view = bpy.context.preferences.view
    view.language = "ja_JP"
    view.use_translate_interface = True
    view.use_translate_tooltips = True
    check("japanese auto", i18n.is_japanese() and i18n.t("Stroke") == "砕け具合")
    check("operator label translated", T.pgettext_iface("Make It Kira", "Operator") == "キラキラにする")
    check("tooltip translated", T.pgettext_tip("Soft glow") == "ふんわりした光のにじみ")
    check("preset names in japanese", kops._preset_items(None, None)[0][1] == "キラ（砕いたダイヤ）")
    check("background names in japanese", kops._background_items(None, None)[0][1] == "夜空パープル")
    check("report in japanese", i18n.report("KiraPaint Soft Paint applied to 2 object(s).") ==
          "KiraPaint（ソフトペイント）を 2 個のオブジェクトに適用しました。")
    view.language = "en_US"
    check("back to english", i18n.t("Stroke") == "Stroke")
    i18n.preference = lambda: "JA"
    check("japanese by hand", i18n.t("Gloss") == "光沢" and i18n.t("Make It Kira") == "キラキラにする")
    i18n.preference = lambda: "EN"
    view.language = "ja_JP"
    check("english by hand on japanese blender", i18n.t("Gloss") == "Gloss")
    view.language = "en_US"
    kirapaint.unregister()
    check("unregister clean", not hasattr(bpy.types.Scene, "kirapaint"))
    kirapaint.register()
    check("register again", hasattr(bpy.types.Scene, "kirapaint"))
except Exception:
    traceback.print_exc()
    failures.append("exception")

print("FAILURES:", failures if failures else "none")
sys.exit(1 if failures else 0)
