# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiraPaint tab in the 3D view sidebar (N)."""

import bpy

from . import core


class KiraPaintPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "KiraPaint"


class KIRAPAINT_PT_main(KiraPaintPanel, bpy.types.Panel):
    bl_label = "KiraPaint"

    def draw(self, context):
        layout = self.layout
        s = context.scene.kirapaint
        col = layout.column(align=True)
        col.label(text="Style")
        col.prop(s, "preset", text="")
        col = layout.column(align=True)
        col.label(text="Background")
        col.template_icon_view(s, "background", show_labels=True, scale=4.0, scale_popup=4.0)
        row = layout.row(align=True)
        row.prop(s, "doodles")
        row.prop(s, "steam")
        row = layout.row(align=True)
        row.scale_y = 1.6
        row.operator("kirapaint.apply", icon="SHADERFX")
        if core.kira_objects(context.scene):
            layout.prop(s, "paint", slider=True)
            layout.operator("kirapaint.remove", icon="TRASH")
        if context.scene.render.engine not in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            layout.label(text="Best in EEVEE (Make It Kira switches)", icon="INFO")


class KIRAPAINT_PT_look(KiraPaintPanel, bpy.types.Panel):
    bl_label = "Look"
    bl_parent_id = "KIRAPAINT_PT_main"

    def draw(self, context):
        s = context.scene.kirapaint
        col = self.layout.column(align=True)
        col.label(text="Surface")
        col.prop(s, "stroke", slider=True)
        col.prop(s, "facets")
        col.prop(s, "gloss", slider=True)
        col.prop(s, "iridescence", slider=True)
        col = self.layout.column(align=True)
        col.label(text="Paint & Shine")
        col.prop(s, "brush")
        col.prop(s, "sparkle", slider=True)
        col.prop(s, "bloom", slider=True)
        col.prop(s, "outline")


class KIRAPAINT_PT_scene(KiraPaintPanel, bpy.types.Panel):
    bl_label = "Scene & Animation"
    bl_parent_id = "KIRAPAINT_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = context.scene.kirapaint
        layout = self.layout
        row = layout.row(align=True)
        row.operator("kirapaint.relight", icon="LIGHT_AREA")
        row.operator("kirapaint.doodles", icon="GREASEPENCIL")
        col = layout.column(align=True)
        col.prop(s, "reveal_length")
        col.operator("kirapaint.reveal", icon="KEYFRAME")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(s, "turn_degrees")
        row.prop(s, "turn_length")
        col.operator("kirapaint.turntable", icon="FILE_REFRESH")


class KIRAPAINT_PT_about(KiraPaintPanel, bpy.types.Panel):
    bl_label = "About"
    bl_parent_id = "KIRAPAINT_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="KiraPaint by KanaWorks_AI")
        col.operator("wm.url_open", text="GitHub", icon="URL").url = "https://github.com/kanaworksai-hue/kirapaint"
        col.operator("wm.url_open", text="More KanaWorks add-ons",
                     icon="PLUGIN").url = "https://github.com/kanaworksai-hue"


CLASSES = (KIRAPAINT_PT_main, KIRAPAINT_PT_look, KIRAPAINT_PT_scene, KIRAPAINT_PT_about)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
