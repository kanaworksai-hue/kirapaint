# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiraPaint tab in the 3D view sidebar (N). Every text goes through i18n.t(), so the panel follows the
language picked in its header menu (or Blender's own language on Automatic)."""

import bpy

from . import core, i18n
from .i18n import t


def _prop(layout, owner, name, label, **kw):
    layout.prop(owner, name, text=t(label), translate=False, **kw)


def _op(layout, idname, label, **kw):
    return layout.operator(idname, text=t(label), text_ctxt="Operator", translate=False, **kw)


class KiraPaintPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "KiraPaint"


class KiraPaintSubPanel(KiraPaintPanel):
    """Sub-panels draw their own title so it follows the panel language."""
    bl_parent_id = "KIRAPAINT_PT_main"
    title = ""

    def draw_header(self, context):
        self.layout.label(text=t(self.title), translate=False)


class KIRAPAINT_PT_main(KiraPaintPanel, bpy.types.Panel):
    bl_label = "KiraPaint"

    def draw_header_preset(self, context):
        addon = context.preferences.addons.get(i18n.PACKAGE)
        if addon is not None and addon.preferences is not None:
            self.layout.prop(addon.preferences, "ui_language", text="", icon="WORLD_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.kirapaint
        col = layout.column(align=True)
        col.label(text=t("Style"), translate=False)
        col.prop(s, "preset", text="")
        col = layout.column(align=True)
        col.label(text=t("Background"), translate=False)
        col.template_icon_view(s, "background", show_labels=True, scale=4.0, scale_popup=4.0)
        row = layout.row(align=True)
        _prop(row, s, "doodles", "Chalk Doodles")
        _prop(row, s, "steam", "Steam")
        row = layout.row(align=True)
        row.scale_y = 1.6
        _op(row, "kirapaint.apply", "Make It Kira", icon="SHADERFX")
        if core.kira_objects(context.scene):
            _prop(layout, s, "paint", "2.5D", slider=True)
            _op(layout, "kirapaint.remove", "Remove KiraPaint", icon="TRASH")
        if context.scene.render.engine not in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            layout.label(text=t("Best in EEVEE (Make It Kira switches)"), icon="INFO", translate=False)


class KIRAPAINT_PT_look(KiraPaintSubPanel, bpy.types.Panel):
    bl_label = ""
    title = "Look"

    def draw(self, context):
        s = context.scene.kirapaint
        col = self.layout.column(align=True)
        col.label(text=t("Surface"), translate=False)
        _prop(col, s, "stroke", "Stroke", slider=True)
        _prop(col, s, "facets", "Facet Density")
        _prop(col, s, "gloss", "Gloss", slider=True)
        _prop(col, s, "iridescence", "Iridescence", slider=True)
        col = self.layout.column(align=True)
        col.label(text=t("Paint & Shine"), translate=False)
        _prop(col, s, "brush", "Brush Size")
        _prop(col, s, "sparkle", "Sparkle", slider=True)
        _prop(col, s, "bloom", "Bloom", slider=True)
        _prop(col, s, "outline", "Outline Width")


class KIRAPAINT_PT_scene(KiraPaintSubPanel, bpy.types.Panel):
    bl_label = ""
    bl_options = {"DEFAULT_CLOSED"}
    title = "Scene & Animation"

    def draw(self, context):
        s = context.scene.kirapaint
        layout = self.layout
        row = layout.row(align=True)
        _op(row, "kirapaint.relight", "Re-aim Lights", icon="LIGHT_AREA")
        _op(row, "kirapaint.doodles", "Redraw Doodles", icon="GREASEPENCIL")
        col = layout.column(align=True)
        _prop(col, s, "reveal_length", "Reveal Frames")
        _op(col, "kirapaint.reveal", "Add Reveal", icon="KEYFRAME")
        col = layout.column(align=True)
        row = col.row(align=True)
        _prop(row, s, "turn_degrees", "Turn")
        _prop(row, s, "turn_length", "Turn Frames")
        _op(col, "kirapaint.turntable", "Add Turntable", icon="FILE_REFRESH")


class KIRAPAINT_PT_about(KiraPaintSubPanel, bpy.types.Panel):
    bl_label = ""
    bl_options = {"DEFAULT_CLOSED"}
    title = "About"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="KiraPaint by KanaWorks_AI", translate=False)
        col.operator("wm.url_open", text="GitHub", icon="URL",
                     translate=False).url = "https://github.com/kanaworksai-hue/kirapaint"
        col.operator("wm.url_open", text=t("More KanaWorks add-ons"), icon="PLUGIN",
                     translate=False).url = "https://github.com/kanaworksai-hue"
        addon = context.preferences.addons.get(i18n.PACKAGE)
        if addon is not None and addon.preferences is not None:
            col.separator()
            col.label(text=t("UI Language"), translate=False)
            col.row(align=True).prop(addon.preferences, "ui_language", expand=True)


CLASSES = (KIRAPAINT_PT_main, KIRAPAINT_PT_look, KIRAPAINT_PT_scene, KIRAPAINT_PT_about)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
