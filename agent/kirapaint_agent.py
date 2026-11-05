# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""KiraPaint in one command. Written for AI agents; humans just ask their agent.

Install (once, permanent):
  blender -b --python kirapaint_agent.py -- --install kirapaint-x.y.z.zip
  (never add --factory-startup here: the install is saved into the user's preferences)

Paint a .blend (installs first if --install is given and it is missing):
  blender -b scene.blend --python kirapaint_agent.py -- --preset KIRA --save scene_kira.blend --render preview.png

Paint a model file straight away (.glb .gltf .fbx .obj); a camera is added:
  blender -b --python kirapaint_agent.py -- --model duck.glb --preset KIRA --save duck_kira.blend --render preview.png

Options:
  --install ZIP          install + enable the extension from a zip (saved to user preferences)
  --model PATH           import this model into an empty scene first
  --preset NAME          KIRA SOFT INK DREAMY (omit on later tweaks to keep the current look)
  --stroke X --facets X --gloss X --iridescence X --brush PX --sparkle X --bloom X --outline X
                         look overrides (see --list for what they do)
  --objects A,B          only these objects (default: every mesh in the scene)
  --background NAME      NIGHT (default) STARRY SAKURA POLKA MINT SODA LEMON PEACH SUNSET STUDIO, or KEEP
  --doodles on|off       chalk stars and hearts (default: on for a new setup)
  --steam                three steam lines above the object (food)
  --no-outline           skip the outline
  --no-scene             only touch materials (no lights, world or compositor)
  --paint X              0 = plain render, 1 = full KiraPaint (default 1)
  --reveal N             animate plain -> KiraPaint over N frames from the scene start
  --turntable DEG        turn the objects DEG degrees over the scene's frame range
  --frame-camera         point a KiraPaint camera at the objects (the user's camera is left alone)
  --preview-size PCT     render size in % of the scene resolution, e.g. 50 for quick previews
  --save PATH            save the .blend here (default: do not save)
  --render PATH          render a PNG (adds a camera if the scene has none)
  --remove               take KiraPaint out of the scene again
  --list                 print the presets and exit
Exit code 0 on success; the last line printed starts with "KIRAPAINT OK" or "KIRAPAINT ERROR".
"""

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
LOOK = ("stroke", "facets", "gloss", "iridescence", "brush", "sparkle", "bloom", "outline")


def arg(name, default=None, flag=False):
    if name not in argv:
        return default
    if flag:
        return True
    i = argv.index(name)
    return argv[i + 1] if i + 1 < len(argv) else default


def fail(msg):
    print("KIRAPAINT ERROR", msg)
    sys.exit(1)


def installed():
    return hasattr(bpy.types, "KIRAPAINT_OT_make_kira")


def install(zip_path):
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path):
        fail(f"zip not found: {zip_path}")
    if bpy.app.factory_startup:
        fail("do not use --factory-startup when installing; it would overwrite the user's preferences")
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    if not installed():
        import addon_utils
        addon_utils.enable("bl_ext.user_default.kirapaint", default_set=True, persistent=True)
    bpy.ops.wm.save_userpref()
    if not installed():
        fail("install finished but the add-on did not load")
    print("KiraPaint installed:", zip_path)


def package():
    import importlib
    base = bpy.types.KIRAPAINT_OT_make_kira.__module__.rsplit(".", 1)[0]
    return importlib.import_module(base + ".api"), importlib.import_module(base + ".core")


def import_model(path):
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        fail(f"model not found: {path}")
    for ob in list(bpy.context.scene.objects):
        bpy.data.objects.remove(ob)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        fail(f"unsupported model type {ext} (use .glb .gltf .fbx .obj)")


def main():
    zip_path = arg("--install")
    if zip_path and not installed():
        install(zip_path)
    elif zip_path:
        print("KiraPaint already installed")
    if not installed():
        fail("KiraPaint is not installed (run with --install kirapaint.zip)")
    api, core = package()

    if arg("--list", flag=True):
        for key, label, desc in api.list_presets():
            print(f"{key:8s} {label:24s} {desc}")
        print("look options: stroke facets gloss iridescence brush sparkle bloom outline")
        for key, label, ja in api.list_backgrounds():
            print(f"background {key:8s} {label:18s} {ja}")
        print("KIRAPAINT OK listed presets")
        return

    if arg("--model"):
        import_model(arg("--model"))
    scene = bpy.context.scene

    if arg("--remove", flag=True):
        report = api.remove()
    else:
        has_job = any(a in argv for a in ("--preset", "--model", "--save", "--render", "--objects", "--paint",
                                          "--reveal", "--turntable", "--doodles", "--steam", "--no-outline", "--background")
                      + tuple("--" + k for k in LOOK))
        if not has_job:
            print("KIRAPAINT OK", "installed" if zip_path else "nothing to do")
            return
        names = arg("--objects")
        objs = api.resolve_objects("ALL", names=names.split(",") if names else None)
        if arg("--frame-camera", flag=True) or (arg("--model") and scene.camera is None):
            cam = scene.objects.get("KiraPaint Camera")
            if cam is None:
                cam = bpy.data.objects.new("KiraPaint Camera", bpy.data.cameras.new("KiraPaint Camera"))
                scene.collection.objects.link(cam)
            scene.camera = cam
            core.aim_camera(cam, objs)
        look = {}
        try:
            for k in LOOK:
                if arg("--" + k) is not None:
                    look[k] = float(arg("--" + k))
            doodles = {"on": True, "off": False}.get((arg("--doodles") or "").lower())
            report = api.make_kira(objects=objs, preset=arg("--preset"), setup_scene=not arg("--no-scene", flag=True),
                                   background=arg("--background"), doodles_on=doodles,
                                   steam=arg("--steam", flag=True), outline=not arg("--no-outline", flag=True),
                                   paint=float(arg("--paint", 1.0)), **look)
        except ValueError as err:
            fail(str(err))
        if arg("--reveal"):
            core.add_reveal(scene, start=scene.frame_start, length=int(arg("--reveal")))
        if arg("--turntable"):
            core.add_turntable(scene, objs, float(arg("--turntable")), start=scene.frame_start,
                               length=max(1, scene.frame_end - scene.frame_start))
    print(report)

    render = arg("--render")
    if render:
        core.ensure_camera(scene, api.resolve_objects("ALL"))
        if arg("--preview-size"):
            scene.render.resolution_percentage = int(float(arg("--preview-size")))
        scene.render.filepath = os.path.abspath(render)
        bpy.ops.render.render(write_still=True)
        print("preview:", scene.render.filepath)
    save = arg("--save")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(save))
        print("saved:", os.path.abspath(save))
    print("KIRAPAINT OK", report)


main()
