# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""The two node groups KiraPaint is made of.

KiraPaint Surface (shader): goes in front of every Principled BSDF. It breaks the normal into flat,
    glossy facets (Voronoi cells -> Noise color -> Linear Light on the normal), pulls roughness down and
    adds a thin-film sheen. Every facet then reflects the colored lights and environment differently,
    which is what reads as "crushed diamond" once the compositor paints over it.
KiraPaint Comp (compositor): bloom -> sharpen -> two anisotropic Kuwahara filters (small brush and a
    1.5x brush) -> sharpen -> mix, then four-point star glare on the brightest facets.

Both groups hold their settings in named Value nodes ("KP ...") so one change updates every material.
The "KP Paint" value is driven by scene.kirapaint.paint: 0 = plain render, 1 = full 2.5D.
"""

import math

import bpy

SURFACE_GROUP = "KiraPaint Surface"
COMP_GROUP = "KiraPaint Comp"
SURFACE_NODE = "KiraPaint"
VERSION = 2

FACETS_PER_OBJECT = 6.5   # Voronoi cells across the object at facets = 1
FILM_THICKNESS = 520.0    # nm; the film IOR (1.0 = no film) does the fading


def _value(tree, name, value, location):
    node = tree.nodes.new("ShaderNodeValue")
    node.name = node.label = name
    node.outputs[0].default_value = value
    node.location = location
    return node


def _math(tree, op, a, b=None, location=(0, 0), clamp=False):
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = op
    node.use_clamp = clamp
    node.location = location
    for i, src in enumerate((a, b)):
        if src is None:
            continue
        if isinstance(src, (int, float)):
            node.inputs[i].default_value = src
        else:
            tree.links.new(src, node.inputs[i])
    return node.outputs[0]


def _socket(tree, name, in_out, kind, default=None, lo=None, hi=None):
    sock = tree.interface.new_socket(name, in_out=in_out, socket_type=kind)
    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default
    if lo is not None:
        sock.min_value = lo
    if hi is not None:
        sock.max_value = hi
    return sock


def driver_paint(socket_owner, path, scene, expression="p", index=-1):
    """Drive `path` on `socket_owner` by scene.kirapaint.paint (simple expression, no Python needed)."""
    fcurve = socket_owner.driver_add(path, index) if index >= 0 else socket_owner.driver_add(path)
    drv = fcurve.driver
    drv.type = "SCRIPTED"
    for v in list(drv.variables):
        drv.variables.remove(v)
    var = drv.variables.new()
    var.name = "p"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "SCENE"
    var.targets[0].id = scene
    var.targets[0].data_path = "kirapaint.paint"
    drv.expression = expression
    return fcurve


# --------------------------------------------------------------------------------------------- surface

def build_surface_group(scene):
    tree = bpy.data.node_groups.get(SURFACE_GROUP)
    if tree is not None and tree.get("kirapaint_version") == VERSION:
        return tree
    if tree is None:
        tree = bpy.data.node_groups.new(SURFACE_GROUP, "ShaderNodeTree")
    tree.nodes.clear()
    tree.interface.clear()
    tree["kirapaint_version"] = VERSION
    _socket(tree, "Normal", "INPUT", "NodeSocketVector", (0.0, 0.0, 1.0)).hide_value = True
    _socket(tree, "Roughness", "INPUT", "NodeSocketFloat", 0.5, 0.0, 1.0)
    _socket(tree, "Object Size", "INPUT", "NodeSocketFloat", 2.0, 0.0001, 10000.0)
    _socket(tree, "Normal", "OUTPUT", "NodeSocketVector")
    _socket(tree, "Roughness", "OUTPUT", "NodeSocketFloat")
    _socket(tree, "Thin Film Thickness", "OUTPUT", "NodeSocketFloat")
    _socket(tree, "Thin Film IOR", "OUTPUT", "NodeSocketFloat")
    nodes, links = tree.nodes, tree.links

    gin = nodes.new("NodeGroupInput")
    gin.location = (-1200, 0)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (700, 0)

    paint = _value(tree, "KP Paint", 1.0, (-1200, 400))
    stroke = _value(tree, "KP Stroke", 0.72, (-1200, 300))
    facets = _value(tree, "KP Facets", 1.0, (-1200, 200))
    gloss = _value(tree, "KP Gloss", 0.85, (-1200, -300))
    iri = _value(tree, "KP Iridescence", 0.7, (-1200, -400))
    driver_paint(paint.outputs[0], "default_value", scene)

    # facet coordinates: object space scaled so the object holds ~6.5 cells
    per = _math(tree, "MULTIPLY", facets.outputs[0], FACETS_PER_OBJECT, (-1000, 200))
    size = _math(tree, "MAXIMUM", gin.outputs["Object Size"], 0.0001, (-1000, 100))
    scale = _math(tree, "DIVIDE", per, size, (-850, 150))
    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-1000, -50)
    vscale = nodes.new("ShaderNodeVectorMath")
    vscale.operation = "SCALE"
    vscale.location = (-700, 50)
    links.new(coord.outputs["Object"], vscale.inputs[0])
    links.new(scale, vscale.inputs["Scale"])

    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "3D"
    vor.feature = "F1"
    vor.location = (-500, 50)
    vor.inputs["Scale"].default_value = 1.0
    vor.inputs["Randomness"].default_value = 1.0
    links.new(vscale.outputs[0], vor.inputs["Vector"])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-300, 50)
    noise.inputs["Scale"].default_value = 1.17
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.5
    noise.inputs["Distortion"].default_value = 0.6
    links.new(vor.outputs["Position"], noise.inputs["Vector"])

    amount = _math(tree, "MULTIPLY", stroke.outputs[0], paint.outputs[0], (-300, 300))
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "LINEAR_LIGHT"
    mix.location = (-50, 150)
    links.new(amount, mix.inputs[0])
    links.new(gin.outputs["Normal"], mix.inputs[6])
    links.new(noise.outputs["Color"], mix.inputs[7])
    norm = nodes.new("ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"
    norm.location = (200, 150)
    links.new(mix.outputs[2], norm.inputs[0])
    links.new(norm.outputs[0], gout.inputs["Normal"])

    # roughness pulled toward a glassy 0.06
    gl = _math(tree, "MULTIPLY", gloss.outputs[0], paint.outputs[0], (-300, -250))
    rmix = nodes.new("ShaderNodeMix")
    rmix.data_type = "FLOAT"
    rmix.location = (200, -150)
    links.new(gl, rmix.inputs[0])
    links.new(gin.outputs["Roughness"], rmix.inputs[2])
    rmix.inputs[3].default_value = 0.06
    links.new(rmix.outputs[0], gout.inputs["Roughness"])

    # thin film: fixed thickness, IOR 1.0 (no film) .. 1.45
    film = _value(tree, "KP Film Thickness", FILM_THICKNESS, (200, -350))
    links.new(film.outputs[0], gout.inputs["Thin Film Thickness"])
    ir = _math(tree, "MULTIPLY", iri.outputs[0], paint.outputs[0], (-300, -450))
    ir = _math(tree, "MULTIPLY", ir, 0.45, (-100, -450))
    ir = _math(tree, "ADD", ir, 1.0, (100, -450))
    links.new(ir, gout.inputs["Thin Film IOR"])
    return tree


def surface_group():
    return bpy.data.node_groups.get(SURFACE_GROUP)


def surface_nodes(material):
    if material is None or material.node_tree is None:
        return []
    return [n for n in material.node_tree.nodes
            if n.type == "GROUP" and n.node_tree is not None and n.node_tree.name.startswith(SURFACE_GROUP)]


# ------------------------------------------------------------------------------------------- compositor

def _menu(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        try:
            sock.default_value = value
        except TypeError:
            pass


def _set(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        sock.default_value = value


def build_comp_group(scene):
    tree = bpy.data.node_groups.get(COMP_GROUP)
    if tree is not None and tree.get("kirapaint_version") == VERSION:
        return tree
    if tree is None:
        tree = bpy.data.node_groups.new(COMP_GROUP, "CompositorNodeTree")
    tree.nodes.clear()
    tree.interface.clear()
    tree["kirapaint_version"] = VERSION
    _socket(tree, "Image", "INPUT", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0))
    _socket(tree, "Image", "OUTPUT", "NodeSocketColor")
    nodes, links = tree.nodes, tree.links
    gin = nodes.new("NodeGroupInput")
    gin.location = (-1400, 0)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (900, 0)

    bloom = nodes.new("CompositorNodeGlare")
    bloom.name = bloom.label = "KP Bloom"
    bloom.location = (-1200, 0)
    _menu(bloom, "Type", "Bloom")
    _menu(bloom, "Quality", "Medium")
    _set(bloom, "Threshold", 0.8)
    _set(bloom, "Strength", 0.48)
    _set(bloom, "Saturation", 1.0)
    _set(bloom, "Size", 0.34)
    links.new(gin.outputs["Image"], bloom.inputs["Image"])

    sharpen = nodes.new("CompositorNodeFilter")
    sharpen.location = (-1000, 0)
    _menu(sharpen, "Type", "Diamond Sharpen")
    _set(sharpen, "Factor", 0.513)
    links.new(bloom.outputs["Image"], sharpen.inputs["Image"])

    kuwa = []
    for i, (name, y) in enumerate((("KP Brush A", 150), ("KP Brush B", -150))):
        k = nodes.new("CompositorNodeKuwahara")
        k.name = k.label = name
        k.location = (-750, y)
        _menu(k, "Type", "Anisotropic")
        _set(k, "Size", 4.0 if i == 0 else 6.0)
        _set(k, "Uniformity", 4)
        _set(k, "Sharpness", 1.0)
        _set(k, "Eccentricity", 1.0)
        links.new(sharpen.outputs["Image"], k.inputs["Image"])
        kuwa.append(k)
    sharpen2 = nodes.new("CompositorNodeFilter")
    sharpen2.location = (-500, 150)
    _menu(sharpen2, "Type", "Diamond Sharpen")
    _set(sharpen2, "Factor", 0.573)
    links.new(kuwa[0].outputs["Image"], sharpen2.inputs["Image"])

    stroke_mix = nodes.new("ShaderNodeMix")
    stroke_mix.data_type = "RGBA"
    stroke_mix.location = (-250, 50)
    stroke_mix.inputs[0].default_value = 0.484
    links.new(sharpen2.outputs["Image"], stroke_mix.inputs[6])
    links.new(kuwa[1].outputs["Image"], stroke_mix.inputs[7])

    paint = nodes.new("ShaderNodeValue")
    paint.name = paint.label = "KP Paint"
    paint.location = (-250, 350)
    paint.outputs[0].default_value = 1.0
    driver_paint(paint.outputs[0], "default_value", scene)

    switch = nodes.new("ShaderNodeMix")
    switch.name = switch.label = "KP Switch"
    switch.data_type = "RGBA"
    switch.location = (50, 100)
    links.new(paint.outputs[0], switch.inputs[0])
    links.new(bloom.outputs["Image"], switch.inputs[6])
    links.new(stroke_mix.outputs[2], switch.inputs[7])

    sparkle = nodes.new("CompositorNodeGlare")
    sparkle.name = sparkle.label = "KP Sparkle"
    sparkle.location = (350, 100)
    _menu(sparkle, "Type", "Streaks")
    _menu(sparkle, "Quality", "High")
    _set(sparkle, "Threshold", 1.3)
    _set(sparkle, "Strength", 0.75)
    _set(sparkle, "Streaks", 4)
    _set(sparkle, "Streaks Angle", math.radians(45.0))
    _set(sparkle, "Fade", 0.9)
    _set(sparkle, "Iterations", 4)
    links.new(switch.outputs[2], sparkle.inputs["Image"])
    fade = nodes.new("ShaderNodeMix")   # star glints fade in with the paint too
    fade.name = fade.label = "KP Sparkle Fade"
    fade.data_type = "RGBA"
    fade.location = (650, 100)
    links.new(paint.outputs[0], fade.inputs[0])
    links.new(switch.outputs[2], fade.inputs[6])
    links.new(sparkle.outputs["Image"], fade.inputs[7])
    links.new(fade.outputs[2], gout.inputs["Image"])
    return tree


def comp_group():
    return bpy.data.node_groups.get(COMP_GROUP)


# ---------------------------------------------------------------------------------------------- values

def set_look(look, scene=None):
    """Push look values into both groups. `look` holds any of presets.LOOK_KEYS."""
    tree = surface_group()
    if tree is not None:
        for key, node in (("stroke", "KP Stroke"), ("facets", "KP Facets"), ("gloss", "KP Gloss"),
                          ("iridescence", "KP Iridescence")):
            if key in look and tree.nodes.get(node) is not None:
                tree.nodes[node].outputs[0].default_value = float(look[key])
    comp = comp_group()
    if comp is not None:
        if "bloom" in look and comp.nodes.get("KP Bloom") is not None:
            _set(comp.nodes["KP Bloom"], "Strength", max(0.0, min(1.0, float(look["bloom"]))))
        if "sparkle" in look and comp.nodes.get("KP Sparkle") is not None:
            s = float(look["sparkle"])
            node = comp.nodes["KP Sparkle"]
            _set(node, "Strength", max(0.0, min(1.0, s)))
            _set(node, "Threshold", 1.6 - 0.4 * s)
        if "brush" in look:
            update_brush(float(look["brush"]), scene)


def update_brush(brush_1080, scene=None):
    """Kuwahara sizes are in pixels; keep the brush the same on screen at any resolution."""
    comp = comp_group()
    if comp is None:
        return
    scale = 1.0
    if scene is not None:
        r = scene.render
        scale = min(r.resolution_x, r.resolution_y) * r.resolution_percentage / 100.0 / 1080.0
    a = max(1.0, brush_1080 * scale)
    for name, factor in (("KP Brush A", 1.0), ("KP Brush B", 1.5)):
        node = comp.nodes.get(name)
        if node is not None:
            _set(node, "Size", round(a * factor, 2))
