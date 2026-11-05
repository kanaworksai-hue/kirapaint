# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings and operators."""

import bpy
import bpy.utils.previews as bpy_previews
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from . import api, backgrounds, core, doodles, nodes
from .presets import LOOK_KEYS, ORDER, PRESETS

PRESET_ITEMS = [(k, PRESETS[k]["label"], PRESETS[k]["description"]) for k in ORDER]
_previews = None


def _background_items(self, context):
    items = []
    for i, key in enumerate(backgrounds.ORDER):
        bg = backgrounds.BACKGROUNDS[key]
        icon = _previews[key].icon_id if _previews is not None and key in _previews else 0
        items.append((key, bg["label"], f"{bg['ja']} / {bg['label']}", icon, i))
    items.append(("KEEP", "Keep Mine", "Keep your own world (reflections get less colorful)", "WORLD", len(items)))
    return items


def _background_changed(self, context):
    if self.updating:
        return
    scene = context.scene
    if bpy.data.worlds.get(core.WORLD_NAME) is None and not core.kira_objects(scene):
        return   # nothing applied yet: Make It Kira will use the choice
    core.setup_world(scene, self.background)
    doodles.recolor(self.background)


def _load_previews():
    global _previews
    _previews = bpy_previews.new()
    for key in backgrounds.ORDER:
        p = _previews.new(key)
        p.image_size = (96, 96)
        p.image_pixels_float = backgrounds.icon_pixels(key, 96)


def _look_changed(self, context):
    if self.updating:
        return
    values = {k: getattr(self, k) for k in LOOK_KEYS}
    nodes.set_look(values, context.scene)
    core.set_glints(self.sparkle)


def _outline_changed(self, context):
    if self.updating:
        return
    core.set_outline_width(core.kira_objects(context.scene), self.outline)


def _preset_changed(self, context):
    if self.updating:
        return
    self.updating = True
    try:
        for k in LOOK_KEYS:
            setattr(self, k, PRESETS[self.preset][k])
    finally:
        self.updating = False
    _look_changed(self, context)
    core.set_outline_width(core.kira_objects(context.scene), self.outline)


class KiraPaintSettings(bpy.types.PropertyGroup):
    updating: BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})
    paint: FloatProperty(name="2.5D", description="0 = plain render, 1 = full KiraPaint. Animate it for a reveal",
                         default=1.0, min=0.0, max=1.0, subtype="FACTOR", options={"ANIMATABLE"})
    preset: EnumProperty(name="Preset", items=PRESET_ITEMS, default="KIRA", update=_preset_changed)
    stroke: FloatProperty(name="Stroke", description="How strongly the surface breaks into painted facets",
                          default=0.72, min=0.0, max=1.0, subtype="FACTOR", update=_look_changed)
    facets: FloatProperty(name="Facet Density", description="More, smaller facets (1 = about 6 across the object)",
                          default=1.0, min=0.25, max=4.0, update=_look_changed)
    gloss: FloatProperty(name="Gloss", description="How glassy the facets get",
                         default=0.85, min=0.0, max=1.0, subtype="FACTOR", update=_look_changed)
    iridescence: FloatProperty(name="Iridescence", description="Pink / cyan thin-film sheen",
                               default=0.7, min=0.0, max=1.0, subtype="FACTOR", update=_look_changed)
    brush: FloatProperty(name="Brush Size", description="Paint brush size in pixels at 1080p",
                         default=4.0, min=1.0, max=30.0, update=_look_changed)
    sparkle: FloatProperty(name="Sparkle", description="Star glints on the brightest facets",
                           default=0.75, min=0.0, max=1.0, subtype="FACTOR", update=_look_changed)
    bloom: FloatProperty(name="Bloom", description="Soft glow", default=0.48, min=0.0, max=1.0,
                         subtype="FACTOR", update=_look_changed)
    outline: FloatProperty(name="Outline Width", description="0 = no outline", default=1.0, min=0.0, max=5.0,
                           update=_outline_changed)
    background: EnumProperty(name="Background", items=_background_items, default=0, update=_background_changed)
    doodles: BoolProperty(name="Chalk Doodles", description="Stars, hearts and twinkles around the object",
                          default=True)
    steam: BoolProperty(name="Steam", description="Three steam lines above the object (food!)", default=False)
    reveal_length: IntProperty(name="Reveal Frames", default=24, min=1, max=1000)
    turn_degrees: FloatProperty(name="Turn", default=60.0, min=-720.0, max=720.0)
    turn_length: IntProperty(name="Turn Frames", default=72, min=1, max=5000)


class KIRAPAINT_OT_apply(bpy.types.Operator):
    bl_idname = "kirapaint.apply"
    bl_label = "Make It Kira"
    bl_description = "Paint the selected objects (all meshes if nothing is selected) and set up the scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.kirapaint
        look = {k: getattr(s, k) for k in LOOK_KEYS}
        try:
            report = api.make_kira(preset=None, setup_scene=True, background=s.background, doodles_on=s.doodles,
                                   steam=s.steam, context=context, **look)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        self.report({"INFO"}, report)
        return {"FINISHED"}


class KIRAPAINT_OT_make_kira(bpy.types.Operator):
    """One call for scripts and AI agents (all options in one place)."""
    bl_idname = "kirapaint.make_kira"
    bl_label = "Make Kira (one call)"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(items=[("KEEP", "Keep", "")] + PRESET_ITEMS, default="KEEP")
    target: EnumProperty(items=[("SELECTED_OR_ALL", "Selected or All", ""), ("SELECTED", "Selected", ""),
                                ("ALL", "All", "")], default="SELECTED_OR_ALL")
    setup_scene: BoolProperty(default=True)
    background: StringProperty(default="", description="NIGHT STARRY SAKURA POLKA MINT SODA LEMON PEACH "
                                                        "SUNSET STUDIO or KEEP; empty keeps the current one")
    doodles: EnumProperty(items=[("AUTO", "Auto", ""), ("ON", "On", ""), ("OFF", "Off", "")], default="AUTO")
    steam: BoolProperty(default=False)
    outline: BoolProperty(default=True)
    paint: FloatProperty(default=1.0, min=0.0, max=1.0)
    stroke: FloatProperty(default=-1.0)
    facets: FloatProperty(default=-1.0)
    gloss: FloatProperty(default=-1.0)
    iridescence: FloatProperty(default=-1.0)
    brush: FloatProperty(default=-1.0)
    sparkle: FloatProperty(default=-1.0)
    bloom: FloatProperty(default=-1.0)
    outline_width: FloatProperty(default=-1.0)

    def execute(self, context):
        look = {k: getattr(self, k) for k in ("stroke", "facets", "gloss", "iridescence", "brush", "sparkle", "bloom")
                if getattr(self, k) >= 0.0}
        if self.outline_width >= 0.0:
            look["outline"] = self.outline_width
        try:
            report = api.make_kira(preset=None if self.preset == "KEEP" else self.preset, target=self.target,
                                   setup_scene=self.setup_scene, background=self.background or None,
                                   doodles_on={"AUTO": None, "ON": True, "OFF": False}[self.doodles],
                                   steam=self.steam, outline=self.outline, paint=self.paint, context=context, **look)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        self.report({"INFO"}, report)
        return {"FINISHED"}


class KIRAPAINT_OT_remove(bpy.types.Operator):
    bl_idname = "kirapaint.remove"
    bl_label = "Remove KiraPaint"
    bl_description = "Put the materials back and remove KiraPaint lights, world, compositor and doodles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        self.report({"INFO"}, api.remove(context=context))
        return {"FINISHED"}


class KIRAPAINT_OT_doodles(bpy.types.Operator):
    bl_idname = "kirapaint.doodles"
    bl_label = "Redraw Doodles"
    bl_description = "Draw the chalk doodles again around the painted objects (e.g. after moving the camera)"
    bl_options = {"REGISTER", "UNDO"}

    remove: BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        if self.remove:
            doodles.remove_doodles(scene)
            return {"FINISHED"}
        objs = core.kira_objects(scene) or api.resolve_objects(context=context)
        if not objs:
            self.report({"WARNING"}, "No objects to draw around")
            return {"CANCELLED"}
        doodles.add_doodles(scene, objs, steam=scene.kirapaint.steam)
        return {"FINISHED"}


class KIRAPAINT_OT_relight(bpy.types.Operator):
    bl_idname = "kirapaint.relight"
    bl_label = "Re-aim Lights"
    bl_description = "Place the KiraPaint lights again for the current camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        objs = core.kira_objects(scene) or api.resolve_objects(context=context)
        if not objs:
            return {"CANCELLED"}
        core.setup_lights(scene, objs, scene.kirapaint.sparkle)
        return {"FINISHED"}


class KIRAPAINT_OT_reveal(bpy.types.Operator):
    bl_idname = "kirapaint.reveal"
    bl_label = "Add Reveal"
    bl_description = "Keyframe 2.5D from 0 to 1, starting at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        a, b = core.add_reveal(scene, length=scene.kirapaint.reveal_length)
        self.report({"INFO"}, f"Reveal: frames {a}-{b}")
        return {"FINISHED"}


class KIRAPAINT_OT_turntable(bpy.types.Operator):
    bl_idname = "kirapaint.turntable"
    bl_label = "Add Turntable"
    bl_description = "Turn the painted objects in front of the fixed lights, starting at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        objs = core.kira_objects(scene) or api.resolve_objects(context=context)
        if not objs:
            return {"CANCELLED"}
        s = scene.kirapaint
        core.add_turntable(scene, objs, s.turn_degrees, length=s.turn_length)
        return {"FINISHED"}


CLASSES = (KiraPaintSettings, KIRAPAINT_OT_apply, KIRAPAINT_OT_make_kira, KIRAPAINT_OT_remove,
           KIRAPAINT_OT_doodles, KIRAPAINT_OT_relight, KIRAPAINT_OT_reveal, KIRAPAINT_OT_turntable)


@bpy.app.handlers.persistent
def _keep_brush(scene, *_args):
    # brush size is in pixels: follow resolution changes at render time
    try:
        s = scene.kirapaint
    except AttributeError:
        return
    if nodes.comp_group() is not None:
        nodes.update_brush(s.brush, scene)
    core.update_aspect(scene)


def register():
    _load_previews()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kirapaint = PointerProperty(type=KiraPaintSettings)
    bpy.app.handlers.render_pre.append(_keep_brush)


def unregister():
    if _keep_brush in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(_keep_brush)
    del bpy.types.Scene.kirapaint
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    global _previews
    if _previews is not None:
        bpy_previews.remove(_previews)
        _previews = None
