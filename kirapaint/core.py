# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Materials, outlines, lights, world and compositor. No UI here, so tests can call it directly.

KiraPaint never replaces a material: it slips the "KiraPaint Surface" group in front of each Principled
BSDF and remembers what was there, so `remove_from_objects` puts everything back.
"""

import math

import bpy
from mathutils import Vector

from . import backgrounds, nodes

OUTLINE_MOD = "KiraPaint Outline"
OUTLINE_MAT = "KiraPaint Ink"
LIGHTS_COLLECTION = "KiraPaint Lights"
WORLD_NAME = "KiraPaint World"
COMP_TREE = "KiraPaint Compositing"
GEO_NODE = "KiraPaint Geometry"
MESHY = {"MESH", "CURVE", "SURFACE", "META", "FONT"}

OUTLINE_PER_SIZE = 0.0033   # outline thickness as a fraction of the object's size, at width 1
REF_RADIUS = 1.684          # the lighting below was tuned on an object with this bounding radius


# ------------------------------------------------------------------------------------------- objects

def local_size(ob):
    """Largest bounding-box side in the object's own coordinates (what Object texture coords see)."""
    pts = [Vector(c) for c in ob.bound_box]
    return max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)) or 1.0


def bounds(objects):
    pts = [ob.matrix_world @ Vector(c) for ob in objects for c in ob.bound_box]
    if not pts:
        return Vector((0, 0, 0)), 1.0
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2, max((hi - lo).length / 2, 0.01)


def _default_material():
    mat = bpy.data.materials.get("KiraPaint Default")
    if mat is None:
        mat = bpy.data.materials.new("KiraPaint Default")
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (0.5, 0.3, 0.78, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.4
    return mat


# ----------------------------------------------------------------------------------------- materials

def is_line(material):
    return material is not None and material.name.startswith(OUTLINE_MAT)


def principled_nodes(material):
    if material is None or not material.use_nodes or material.node_tree is None:
        return []
    return [n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"]


def apply_to_material(material, scene, size):
    """Insert the KiraPaint Surface group in front of every Principled BSDF. Returns how many."""
    group = nodes.build_surface_group(scene)
    tree = material.node_tree
    done = 0
    for bsdf in principled_nodes(material):
        existing = next((n for n in nodes.surface_nodes(material)
                         if any(link.to_node == bsdf for out in n.outputs for link in out.links)), None)
        if existing is not None:
            existing.inputs["Object Size"].default_value = max(existing.inputs["Object Size"].default_value, size)
            done += 1
            continue
        node = tree.nodes.new("ShaderNodeGroup")
        node.node_tree = group
        node.name = node.label = nodes.SURFACE_NODE
        node.location = bsdf.location + Vector((-260, -320))
        node.inputs["Object Size"].default_value = size
        node["bsdf"] = bsdf.name
        node["film_thickness"] = bsdf.inputs["Thin Film Thickness"].default_value
        node["film_ior"] = bsdf.inputs["Thin Film IOR"].default_value

        normal = bsdf.inputs["Normal"]
        if normal.is_linked:
            tree.links.new(normal.links[0].from_socket, node.inputs["Normal"])
        else:
            geo = tree.nodes.new("ShaderNodeNewGeometry")
            geo.name = geo.label = GEO_NODE
            geo.location = node.location + Vector((-200, 0))
            tree.links.new(geo.outputs["Normal"], node.inputs["Normal"])
        rough = bsdf.inputs["Roughness"]
        if rough.is_linked:
            tree.links.new(rough.links[0].from_socket, node.inputs["Roughness"])
        else:
            node.inputs["Roughness"].default_value = rough.default_value
        tree.links.new(node.outputs["Normal"], normal)
        tree.links.new(node.outputs["Roughness"], rough)
        for name in ("Thin Film Thickness", "Thin Film IOR"):
            sock = bsdf.inputs[name]
            if not sock.is_linked:
                tree.links.new(node.outputs[name], sock)
        done += 1
    if done:
        material["kirapaint"] = True
    return done


def remove_from_material(material):
    tree = material.node_tree if material is not None else None
    if tree is None:
        return 0
    removed = 0
    for node in nodes.surface_nodes(material):
        bsdf = tree.nodes.get(node.get("bsdf", ""))
        if bsdf is not None:
            src = node.inputs["Normal"].links[0].from_node if node.inputs["Normal"].is_linked else None
            if src is not None and src.name.startswith(GEO_NODE):
                for link in list(bsdf.inputs["Normal"].links):
                    tree.links.remove(link)
            elif node.inputs["Normal"].is_linked:
                tree.links.new(node.inputs["Normal"].links[0].from_socket, bsdf.inputs["Normal"])
            if node.inputs["Roughness"].is_linked:
                tree.links.new(node.inputs["Roughness"].links[0].from_socket, bsdf.inputs["Roughness"])
            else:
                for link in list(bsdf.inputs["Roughness"].links):
                    tree.links.remove(link)
                bsdf.inputs["Roughness"].default_value = node.inputs["Roughness"].default_value
            for name, key in (("Thin Film Thickness", "film_thickness"), ("Thin Film IOR", "film_ior")):
                for link in list(bsdf.inputs[name].links):
                    if link.from_node == node:
                        tree.links.remove(link)
                if key in node:
                    bsdf.inputs[name].default_value = node[key]
            if src is not None and src.name.startswith(GEO_NODE):
                tree.nodes.remove(src)
        tree.nodes.remove(node)
        removed += 1
    if "kirapaint" in material:
        del material["kirapaint"]
    return removed


def apply_to_objects(objects, scene):
    """Returns (objects changed, materials without a Principled BSDF that were skipped)."""
    sizes = {}
    changed, skipped = 0, set()
    for ob in objects:
        if ob.type not in MESHY:
            continue
        if not any(sl.material and not is_line(sl.material) for sl in ob.material_slots):
            if ob.data is not None and hasattr(ob.data, "materials"):
                ob.data.materials.append(_default_material())
        size = local_size(ob)
        for sl in ob.material_slots:
            mat = sl.material
            if mat is None or is_line(mat):
                continue
            sizes[mat] = max(sizes.get(mat, 0.0), size)
    for mat, size in sizes.items():
        if not principled_nodes(mat):
            skipped.add(mat.name)
            continue
        apply_to_material(mat, scene, size)
    for ob in objects:
        if ob.type in MESHY and any(sl.material in sizes and sl.material.name not in skipped
                                    for sl in ob.material_slots):
            ob["kirapaint"] = True
            changed += 1
    return changed, sorted(skipped)


def kira_objects(scene):
    return [ob for ob in scene.objects if ob.get("kirapaint")]


def remove_from_objects(objects):
    mats = {sl.material for ob in objects for sl in ob.material_slots if sl.material is not None}
    for mat in mats:
        remove_from_material(mat)
    for ob in objects:
        remove_outline(ob)
        if "kirapaint" in ob:
            del ob["kirapaint"]


# -------------------------------------------------------------------------------------------- outline

def outline_material(color=(0.06, 0.03, 0.045)):
    mat = bpy.data.materials.get(OUTLINE_MAT)
    if mat is None:
        mat = bpy.data.materials.new(OUTLINE_MAT)
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        out = tree.nodes.new("ShaderNodeOutputMaterial")
        em = tree.nodes.new("ShaderNodeEmission")
        em.location = (-200, 0)
        tree.links.new(em.outputs[0], out.inputs["Surface"])
        mat.use_backface_culling = True
        if hasattr(mat, "use_backface_culling_shadow"):
            mat.use_backface_culling_shadow = True
    em = next(n for n in mat.node_tree.nodes if n.type == "EMISSION")
    em.inputs["Color"].default_value = (*color[:3], 1.0)
    mat.diffuse_color = (*color[:3], 1.0)
    return mat


def add_outline(ob, width, scene, color=None):
    if ob.type != "MESH":
        return False
    line = outline_material(color) if color is not None else outline_material()
    mats = ob.data.materials
    if line.name not in [m.name for m in mats if m]:
        mats.append(line)
    index = [m.name if m else "" for m in mats].index(line.name)
    mod = ob.modifiers.get(OUTLINE_MOD) or ob.modifiers.new(OUTLINE_MOD, "SOLIDIFY")
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_even_offset = False   # even offset spikes on dense scanned / generated meshes
    mod.offset = 1.0
    mod.material_offset = index
    mod.material_offset_rim = index
    mod.thickness = OUTLINE_PER_SIZE * local_size(ob) * width
    mod.show_in_editmode = False
    for prop in ("show_render", "show_viewport"):
        nodes.driver_paint(mod, prop, scene, "p > 0.01")
    mod.show_expanded = False
    return True


def set_outline_width(objects, width):
    for ob in objects:
        mod = ob.modifiers.get(OUTLINE_MOD)
        if mod is not None:
            mod.thickness = OUTLINE_PER_SIZE * local_size(ob) * width


def remove_outline(ob):
    mod = ob.modifiers.get(OUTLINE_MOD)
    if mod is not None:
        if ob.animation_data:
            for fc in list(ob.animation_data.drivers):
                if fc.data_path.startswith(f'modifiers["{OUTLINE_MOD}"]'):
                    ob.animation_data.drivers.remove(fc)
        ob.modifiers.remove(mod)
    if ob.type == "MESH":
        mats = ob.data.materials
        for i in reversed(range(len(mats))):
            if is_line(mats[i]):
                mats.pop(index=i)


# --------------------------------------------------------------------------------------------- scene

def set_engine_eevee(scene):
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            return
        except TypeError:
            continue


def refresh():
    """Matrices are only recomputed on a depsgraph update; we read camera matrices right after edits."""
    try:
        bpy.context.view_layer.update()
    except AttributeError:
        pass


def ensure_camera(scene, objects):
    if scene.camera is None:
        cam = bpy.data.objects.new("KiraPaint Camera", bpy.data.cameras.new("KiraPaint Camera"))
        scene.collection.objects.link(cam)
        scene.camera = cam
        aim_camera(cam, objects)
    refresh()
    return scene.camera


def aim_camera(cam, objects):
    center, radius = bounds(objects)
    cam.data.lens = 50
    cam.location = center + Vector((0.0, -1.0, 0.62)).normalized() * radius * 3.0
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    refresh()


# camera-relative positions (right, up, toward camera) in units of the object radius, tuned on v1
LIGHT_RIG = (
    # name, kind, offset, energy at REF_RADIUS, color, size, glint (specular only)
    ("KP Rim Cool", "AREA", (2.078, 0.612, 1.698), 400.0, (0.55, 0.6, 1.0), 1.0, False),
    ("KP Rim Pink", "AREA", (-2.019, 1.615, -0.597), 260.0, (1.0, 0.45, 0.75), 1.5, False),
    ("KP Glint Pink", "AREA", (-1.9, 0.756, 1.439), 450.0, (1.0, 0.4, 0.78), 0.12, True),
    ("KP Glint Cyan", "AREA", (1.781, 0.023, 1.779), 450.0, (0.4, 0.9, 1.0), 0.12, True),
    ("KP Glint White", "AREA", (0.356, 0.813, 3.169), 380.0, (1.0, 0.97, 0.9), 0.08, True),
    ("KP Glint Gold", "AREA", (-0.891, -0.634, 2.229), 300.0, (1.0, 0.8, 0.4), 0.12, True),
    ("KP Glint Violet", "AREA", (1.306, 1.523, 1.526), 380.0, (0.7, 0.5, 1.0), 0.12, True),
)
SUN_DIR = (-0.309, 0.29, 0.906)   # toward the light, camera-relative


def _cam_basis(cam, center):
    fwd = (center - cam.matrix_world.translation).normalized()
    right = fwd.cross(Vector((0, 0, 1)))
    if right.length < 1e-4:
        right = Vector((1, 0, 0))
    right.normalize()
    up = right.cross(fwd).normalized()
    return right, up, -fwd


def setup_lights(scene, objects, sparkle=0.75):
    center, radius = bounds(objects)
    cam = ensure_camera(scene, objects)
    right, up, back = _cam_basis(cam, center)
    coll = bpy.data.collections.get(LIGHTS_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(LIGHTS_COLLECTION)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    k = radius / REF_RADIUS

    def light(name, kind):
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != "LIGHT":
            ob = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
        if ob.name not in coll.objects:
            coll.objects.link(ob)
        return ob

    sun = light("KP Key Sun", "SUN")
    sun.data.energy = 3.4
    sun.data.color = (1.0, 0.88, 0.72)
    sun.data.angle = math.radians(3.0)
    d = (right * SUN_DIR[0] + up * SUN_DIR[1] + back * SUN_DIR[2]).normalized()
    sun.location = center + d * radius * 3
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

    for name, kind, off, energy, color, size, glint in LIGHT_RIG:
        ob = light(name, kind)
        ob.location = center + (right * off[0] + up * off[1] + back * off[2]) * radius
        ob.rotation_euler = (center - ob.location).to_track_quat("-Z", "Y").to_euler()
        ld = ob.data
        ld.color = color
        ld.size = size * k
        ld["kirapaint_energy"] = energy * k * k
        if glint:
            ld.diffuse_factor = 0.0
            ld.specular_factor = 1.0
            ld["kirapaint_glint"] = True
            nodes.driver_paint(ld, "energy", scene, "0")
            _glint_expression(ld, sparkle)
        else:
            ld.energy = ld["kirapaint_energy"]
    return coll


def glint_scale(sparkle):
    return 0.4 + 0.8 * sparkle


def _glint_expression(light_data, sparkle):
    """Glint lights are driven by the 2.5D slider: dim in the plain render, full when painted."""
    energy = light_data.get("kirapaint_energy", 400.0) * glint_scale(sparkle)
    ad = light_data.animation_data
    fc = next((f for f in ad.drivers if f.data_path == "energy"), None) if ad else None
    if fc is None:
        light_data.energy = energy
        return
    fc.driver.expression = f"{energy:.2f} * (0.25 + 0.75 * p)"


def set_glints(sparkle):
    coll = bpy.data.collections.get(LIGHTS_COLLECTION)
    if coll is None:
        return
    for ob in coll.objects:
        if ob.type == "LIGHT" and ob.data.get("kirapaint_glint"):
            _glint_expression(ob.data, sparkle)


def remove_lights():
    coll = bpy.data.collections.get(LIGHTS_COLLECTION)
    if coll is None:
        return
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            bpy.data.lights.remove(data)
    bpy.data.collections.remove(coll)


def _ramp(node, stops, interpolation):
    cr = node.color_ramp
    cr.interpolation = interpolation
    while len(cr.elements) > 2:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position, cr.elements[0].color = stops[0]
    cr.elements[1].position, cr.elements[1].color = stops[-1]
    for pos, col in stops[1:-1]:
        cr.elements.new(pos).color = col


def build_world(background="NIGHT", aspect=1.0):
    """Camera sees a painted backdrop (one of backgrounds.BACKGROUNDS); reflections always see a
    pink / violet / cyan / gold ring, which is what makes the facets sparkle."""
    spec = backgrounds.BACKGROUNDS[background]
    world = bpy.data.worlds.get(WORLD_NAME) or bpy.data.worlds.new(WORLD_NAME)
    world.use_nodes = True
    world["kirapaint_background"] = background
    tree = world.node_tree
    tree.nodes.clear()
    n, l = tree.nodes, tree.links
    out = n.new("ShaderNodeOutputWorld")
    out.location = (1300, 0)
    coord = n.new("ShaderNodeTexCoord")
    coord.location = (-1100, 0)

    # reflections: hue ring around the vertical axis, brighter toward the top
    sep = n.new("ShaderNodeSeparateXYZ")
    sep.location = (-700, -450)
    l.new(coord.outputs["Generated"], sep.inputs[0])
    atan = n.new("ShaderNodeMath")
    atan.operation = "ARCTAN2"
    atan.location = (-500, -450)
    l.new(sep.outputs[1], atan.inputs[0])
    l.new(sep.outputs[0], atan.inputs[1])
    rng = n.new("ShaderNodeMapRange")
    rng.location = (-300, -450)
    rng.inputs[1].default_value = -math.pi
    rng.inputs[2].default_value = math.pi
    l.new(atan.outputs[0], rng.inputs[0])
    ring = n.new("ShaderNodeValToRGB")
    ring.location = (-100, -450)
    _ramp(ring, [(0.0, (0.25, 0.12, 0.55, 1)), (0.17, (1.0, 0.35, 0.7, 1)), (0.33, (0.35, 0.2, 0.8, 1)),
                 (0.5, (0.2, 0.85, 1.0, 1)), (0.67, (0.45, 0.25, 0.9, 1)), (0.83, (1.0, 0.75, 0.45, 1)),
                 (1.0, (0.25, 0.12, 0.55, 1))], "EASE")
    l.new(rng.outputs[0], ring.inputs[0])
    height = n.new("ShaderNodeMapRange")
    height.location = (-100, -700)
    height.inputs[3].default_value = 0.25
    height.inputs[4].default_value = 1.3
    l.new(sep.outputs[2], height.inputs[0])
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.location = (200, -500)
    tint.inputs[0].default_value = 1.0
    l.new(ring.outputs[0], tint.inputs[6])
    l.new(height.outputs[0], tint.inputs[7])
    env = n.new("ShaderNodeBackground")
    env.name = env.label = "KP Environment"
    env.location = (450, -450)
    env.inputs["Strength"].default_value = 0.3
    l.new(tint.outputs[2], env.inputs["Color"])

    # what the camera sees: screen-space painted card, so it never stretches when the camera moves
    mapping = n.new("ShaderNodeMapping")
    mapping.name = "KP Backdrop Mapping"
    mapping.location = (-900, 300)
    mapping.inputs["Scale"].default_value = (aspect, 1.0, 1.0)
    l.new(coord.outputs["Window"], mapping.inputs["Vector"])
    noise = n.new("ShaderNodeTexNoise")
    noise.location = (-700, 400)
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.6
    noise.inputs["Distortion"].default_value = 0.3
    l.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    vor = n.new("ShaderNodeTexVoronoi")
    vor.location = (-500, 500)
    vor.inputs["Scale"].default_value = 7.0
    l.new(noise.outputs["Color"], vor.inputs["Vector"])
    fmix = n.new("ShaderNodeMix")
    fmix.data_type = "FLOAT"
    fmix.location = (-300, 400)
    fmix.inputs[0].default_value = 0.35
    l.new(noise.outputs["Fac"], fmix.inputs[2])
    l.new(vor.outputs["Distance"], fmix.inputs[3])
    paint = n.new("ShaderNodeValToRGB")
    paint.location = (-100, 400)
    cols = [backgrounds.hex_to_linear(c) for c in spec["paint"]]
    _ramp(paint, list(zip((0.0, 0.38, 0.5, 0.6, 0.72), cols)), "CONSTANT")
    l.new(fmix.outputs[0], paint.inputs[0])

    wsep = n.new("ShaderNodeSeparateXYZ")
    wsep.location = (-700, 150)
    l.new(coord.outputs["Window"], wsep.inputs[0])
    wash = n.new("ShaderNodeValToRGB")
    wash.location = (-450, 150)
    _ramp(wash, [(0.0, backgrounds.hex_to_linear(spec["bottom"])),
                 (1.0, backgrounds.hex_to_linear(spec["top"]))], "EASE")
    l.new(wsep.outputs[1], wash.inputs[0])
    washed = n.new("ShaderNodeMix")
    washed.data_type = "RGBA"
    washed.location = (200, 300)
    washed.inputs[0].default_value = spec["wash"]
    l.new(paint.outputs[0], washed.inputs[6])
    l.new(wash.outputs[0], washed.inputs[7])
    color = washed.outputs[2]

    if spec["dots"]:
        polka = spec["dots"] == "POLKA"
        dmap = n.new("ShaderNodeMapping")
        dmap.location = (-700, 750)
        dmap.inputs["Scale"].default_value = (aspect * (6.0 if polka else 28.0), 6.0 if polka else 28.0, 1.0)
        l.new(coord.outputs["Window"], dmap.inputs["Vector"])
        dvor = n.new("ShaderNodeTexVoronoi")
        dvor.location = (-500, 800)
        dvor.inputs["Randomness"].default_value = 0.0 if polka else 1.0
        l.new(dmap.outputs["Vector"], dvor.inputs["Vector"])
        mask = n.new("ShaderNodeMath")
        mask.operation = "LESS_THAN"
        mask.location = (-300, 800)
        mask.inputs[1].default_value = 0.2 if polka else 0.085
        l.new(dvor.outputs["Distance"], mask.inputs[0])
        if not polka:   # only some cells get a star
            pick = n.new("ShaderNodeMath")
            pick.operation = "GREATER_THAN"
            pick.location = (-300, 650)
            pick.inputs[1].default_value = 0.8
            sep_c = n.new("ShaderNodeSeparateColor")
            sep_c.location = (-450, 650)
            l.new(dvor.outputs["Color"], sep_c.inputs[0])
            l.new(sep_c.outputs[0], pick.inputs[0])
            both = n.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            both.location = (-100, 750)
            l.new(mask.outputs[0], both.inputs[0])
            l.new(pick.outputs[0], both.inputs[1])
            mask = both
        dots = n.new("ShaderNodeMix")
        dots.data_type = "RGBA"
        dots.location = (450, 400)
        l.new(mask.outputs[0], dots.inputs[0])
        l.new(color, dots.inputs[6])
        dots.inputs[7].default_value = (1.0, 0.95, 0.97, 1.0) if polka else (1.4, 1.35, 1.15, 1.0)
        color = dots.outputs[2]

    wall = n.new("ShaderNodeBackground")
    wall.name = wall.label = "KP Backdrop"
    wall.location = (700, 300)
    l.new(color, wall.inputs["Color"])

    path = n.new("ShaderNodeLightPath")
    path.location = (700, 600)
    mix = n.new("ShaderNodeMixShader")
    mix.location = (1000, 100)
    l.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    l.new(env.outputs[0], mix.inputs[1])
    l.new(wall.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    return world


def _aspect(scene):
    r = scene.render
    return (r.resolution_x * r.pixel_aspect_x) / max(1.0, r.resolution_y * r.pixel_aspect_y)


def update_aspect(scene):
    world = bpy.data.worlds.get(WORLD_NAME)
    if world is None or world.node_tree is None:
        return
    a = _aspect(scene)
    for node in world.node_tree.nodes:
        if node.type == "MAPPING":
            sx, sy, sz = node.inputs["Scale"].default_value
            node.inputs["Scale"].default_value = (sy * a, sy, sz)


def setup_world(scene, background="NIGHT"):
    """One of backgrounds.ORDER, or KEEP to leave the world alone."""
    background = {"PAINTED": "NIGHT"}.get(background, background)
    if background == "KEEP":
        return
    if background not in backgrounds.BACKGROUNDS:
        raise ValueError(f"Unknown background {background!r}. Choose one of: {', '.join(backgrounds.ORDER)}, KEEP")
    if scene.world is not None and scene.world.name != WORLD_NAME:
        scene["kirapaint_prev_world"] = scene.world.name
    scene.world = build_world(background, _aspect(scene))


def setup_compositor(scene):
    group = nodes.build_comp_group(scene)
    tree = bpy.data.node_groups.get(COMP_TREE)
    if tree is None:
        tree = bpy.data.node_groups.new(COMP_TREE, "CompositorNodeTree")
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = tree.nodes.new("CompositorNodeRLayers")
        rl.location = (-400, 0)
        gnode = tree.nodes.new("CompositorNodeGroup")
        gnode.node_tree = group
        gnode.name = gnode.label = "KiraPaint"
        out = tree.nodes.new("NodeGroupOutput")
        out.location = (400, 0)
        tree.links.new(rl.outputs["Image"], gnode.inputs["Image"])
        tree.links.new(gnode.outputs["Image"], out.inputs["Image"])
    for node in tree.nodes:
        if node.bl_idname == "CompositorNodeRLayers":
            node.scene = scene
    current = scene.compositing_node_group
    if current is not None and current != tree:
        scene["kirapaint_prev_comp"] = current.name
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return tree


def setup_scene(scene, objects, look, background="NIGHT"):
    set_engine_eevee(scene)
    vs = scene.view_settings
    try:
        vs.view_transform = "Standard"
    except TypeError:
        pass
    try:
        vs.look = "None"
    except TypeError:
        pass
    vs.exposure = 0.0
    vs.gamma = 1.0
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = True
    setup_world(scene, background)
    setup_lights(scene, objects, look.get("sparkle", 0.75))
    setup_compositor(scene)
    nodes.set_look(look, scene)
    scene["kirapaint_scene"] = True


def remove_scene(scene):
    remove_lights()
    prev = scene.get("kirapaint_prev_world")
    if scene.world is not None and scene.world.name == WORLD_NAME:
        scene.world = bpy.data.worlds.get(prev) if prev else None
    prev = scene.get("kirapaint_prev_comp")
    tree = scene.compositing_node_group
    if tree is not None and tree.name == COMP_TREE:
        scene.compositing_node_group = bpy.data.node_groups.get(prev) if prev else None
    for key in ("kirapaint_prev_world", "kirapaint_prev_comp", "kirapaint_scene"):
        if key in scene:
            del scene[key]


# --------------------------------------------------------------------------------------- animation

def add_reveal(scene, start=None, length=24):
    """Plain render -> 2.5D over `length` frames."""
    start = scene.frame_current if start is None else start
    s = scene.kirapaint
    s.paint = 0.0
    scene.keyframe_insert('kirapaint.paint', frame=start)
    s.paint = 1.0
    scene.keyframe_insert('kirapaint.paint', frame=start + length)
    return start, start + length


def add_turntable(scene, objects, degrees=60.0, start=None, length=72):
    """Parent the objects to an empty at their center and turn it. Lights and camera stay put."""
    start = scene.frame_current if start is None else start
    center, _ = bounds(objects)
    pivot = bpy.data.objects.get("KiraPaint Turntable")
    if pivot is None:
        pivot = bpy.data.objects.new("KiraPaint Turntable", None)
        pivot.empty_display_type = "CIRCLE"
        scene.collection.objects.link(pivot)
        pivot.location = (center.x, center.y, center.z)
    refresh()
    roots = []
    for ob in objects:   # imported models often sit under an empty: turn the top of each hierarchy
        top = ob
        while top.parent is not None and top.parent != pivot:
            top = top.parent
        if top.parent is None and top != pivot and top not in roots:
            roots.append(top)
    for top in roots:
        mw = top.matrix_world.copy()
        top.parent = pivot
        top.matrix_parent_inverse = pivot.matrix_world.inverted()
        top.matrix_world = mw
    pivot.rotation_mode = "XYZ"
    pivot.rotation_euler = (0.0, 0.0, 0.0)
    pivot.keyframe_insert("rotation_euler", index=2, frame=start)
    pivot.rotation_euler = (0.0, 0.0, math.radians(degrees))
    pivot.keyframe_insert("rotation_euler", index=2, frame=start + length)
    return pivot
