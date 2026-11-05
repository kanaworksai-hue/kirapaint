# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared helpers for the demo renders: load a model, size it, add a camera and a plain studio look."""

import math
import os

import bpy
from mathutils import Vector

from kirapaint import core


def load(scene, model, width, height, turn=0.0, zoom=1.0):
    for ob in list(scene.objects):
        bpy.data.objects.remove(ob)
    before = set(bpy.data.objects)
    ext = os.path.splitext(model)[1].lower()
    if model.upper() == "SUZANNE":
        bpy.ops.mesh.primitive_monkey_add()
        ob = bpy.context.object
        ob.modifiers.new("Sub", "SUBSURF").levels = 2
        bpy.ops.object.shade_smooth()
        mat = bpy.data.materials.new("Suzanne Lilac")
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (0.42, 0.2, 0.78, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.35
        ob.data.materials.append(mat)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=model, merge_vertices=True)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=model)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=model)
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    bpy.context.view_layer.update()
    roots = {o for o in bpy.data.objects if o not in before and o.parent is None}
    pivot = bpy.data.objects.new("Demo Root", None)
    scene.collection.objects.link(pivot)
    for r in roots:
        r.parent = pivot
    _, radius = core.bounds(objs)
    k = 1.6 / radius
    pivot.scale = (k, k, k)
    bpy.context.view_layer.update()
    center, radius = core.bounds(objs)
    lo_z = min((o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box)
    pivot.location = (-center.x, -center.y, -lo_z)
    pivot.rotation_euler.z = math.radians(turn)
    bpy.context.view_layer.update()
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    core.aim_camera(cam, objs)
    cam.data.lens = 50 * zoom
    return objs


def studio(scene):
    core.set_engine_eevee(scene)
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.get("Studio") or bpy.data.worlds.new("Studio")
    scene.world = world
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.045, 0.045, 0.05, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    sun = bpy.data.objects.new("Studio Sun", bpy.data.lights.new("Studio Sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("Studio Fill", bpy.data.lights.new("Studio Fill", "AREA"))
    fill.data.energy = 300
    fill.data.size = 3
    fill.location = (-3, -3, 2)
    fill.rotation_euler = (Vector((0, 0, 1)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(fill)
    scene.render.use_compositing = False


def clear_studio(scene):
    for name in ("Studio Sun", "Studio Fill"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
