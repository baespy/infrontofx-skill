"""prop-forge: turn forge_prop.py .blend files into GTA V assets with Sollumz (Drawable + embedded collision + ytyp).

Needs the Sollumz extension (2.9+) with its szio dependency installed in this Blender. Run WITHOUT --factory-startup so
the extension loads:
  blender -b -P export_prop.py -- --blend <file.blend | folder> --out <stream dir>
                                  [--format native|cwxml] [--collision PLASTIC]

--format native writes .ydr/.ytyp directly and needs Sollumz's optional PyMateria dependency (Cfx.re licence).
--format cwxml writes CodeWalker XML (.ydr.xml, .ytyp.xml + textures) that CodeWalker converts to binary.
Prints one EXPORT line per prop and ends with RESULT ok=<n> fail=<n>.
"""

import argparse
import importlib
import json
import os
import runpy
import subprocess
import sys

import bpy

SZ = "bl_ext.user_default.sollumz"
HERE = os.path.dirname(os.path.abspath(__file__))
DDS_ENCODER = os.path.normpath(os.path.join(HERE, "..", "..", "..", "weapon-forge", "scripts", "blender", "export_ydr.py"))


def sollumz():
    if SZ not in bpy.context.preferences.addons:
        raise SystemExit("Sollumz extension is not enabled in this Blender (run without --factory-startup)")
    mods = {}
    for name in ("tools.drawablehelper", "tools.boundhelper", "ydr.shader_materials", "ybn.collision_materials", "sollumz_properties", "dependencies"):
        mods[name.split(".")[-1]] = importlib.import_module(SZ + "." + name)
    if not mods["dependencies"].IS_SZIO_AVAILABLE:
        raise SystemExit("Sollumz is installed but szio is missing: run Sollumz > Preferences > Install Dependencies")
    return mods


def first_image(mat):
    if not mat or not mat.use_nodes:
        return None
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            return node.image
    return None


def ensure_dds(image, max_res):
    path = bpy.path.abspath(image.filepath)
    if path.lower().endswith(".dds") and os.path.isfile(path):
        return path
    if not os.path.isfile(DDS_ENCODER):
        raise SystemExit("DXT encoder not found at " + DDS_ENCODER + " (weapon-forge is part of this skill pack)")
    encoder = runpy.run_path(DDS_ENCODER, run_name="prop_forge_dds")
    if image.size[0] == 0:
        image.reload()
    dds = os.path.splitext(path)[0] + ".dds" if path else os.path.join(bpy.app.tempdir, image.name + ".dds")
    encoder["image_to_dxt5"](image, dds_path=dds, bloom=False, max_res=max_res)
    image.filepath = dds
    image.reload()
    return dds


def convert_materials(sz, root, max_res=2048):
    done = []
    for slot in root.material_slots:
        image = first_image(slot.material)
        if image is not None:
            ensure_dds(image, max_res)
    for slot in root.material_slots:
        mat = slot.material
        if mat is None or getattr(mat, "sollum_type", "") == "sollumz_material_shader":
            continue
        shader = mat.get("prop_forge_shader", "default.sps")
        image = first_image(mat)
        new = sz["shader_materials"].create_shader(shader)
        new.name = mat.name
        for node in new.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.name == "DiffuseSampler" and image is not None:
                node.image = image
                try:
                    node.texture_properties.embedded = True
                except AttributeError:
                    pass
        slot.material = new
        done.append("{} -> {}".format(mat.name, shader))
    return done


def collision_index(sz, name):
    for i, mat in enumerate(sz["collision_materials"].collisionmats):
        if mat.name == name:
            return i
    return 0


def build_collision(sz, root, col_name):
    cols = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith(root.name + "_col_")]
    if not cols:
        return None, 0
    index = collision_index(sz, col_name)
    for ob in cols:
        ob.data.materials.clear()
        ob.data.materials.append(sz["collision_materials"].create_collision_material_from_index(index))
    preset = getattr(bpy.context.scene, "sz_default_flag_preset_name", None)
    SollumType = sz["sollumz_properties"].SollumType
    composite = sz["boundhelper"].convert_objs_to_single_composite(cols, SollumType.BOUND_GEOMETRYBVH, preset)
    composite.name = root.name + ".col"
    return composite, len(cols)


def select_only(objs):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def all_children(ob):
    out = [ob]
    for child in ob.children:
        out += all_children(child)
    return out


def export_one(sz, path, out_dir, args):
    bpy.ops.wm.open_mainfile(filepath=path)
    stem = os.path.splitext(os.path.basename(path))[0]
    root = bpy.data.objects.get(stem)
    if root is None or root.type != "MESH":
        return {"id": stem, "ok": False, "error": "no mesh named " + stem}
    meta = json.loads(root.get("prop_forge", "{}"))
    mats = convert_materials(sz, root)
    composite, ncol = build_collision(sz, root, args.collision)
    drawable = sz["drawablehelper"].convert_obj_to_drawable(root)
    if composite is not None:
        composite.parent = drawable
    scene = bpy.context.scene
    ytyp = scene.ytyps.add()
    ytyp.name = stem
    scene.ytyp_index = len(scene.ytyps) - 1
    select_only([drawable])
    with bpy.context.temp_override(active_object=drawable, object=drawable, selected_objects=[drawable]):
        bpy.ops.sollumz.createarchetypefromselected()
    archetype = ytyp.archetypes[len(ytyp.archetypes) - 1] if len(ytyp.archetypes) else None
    if archetype is not None:
        archetype.lod_dist = float(meta.get("lod_dist", 100))
    select_only(all_children(drawable))
    fmt = "NATIVE" if args.format == "native" else "CWXML"
    os.makedirs(out_dir, exist_ok=True)
    before = set(os.listdir(out_dir))
    with bpy.context.temp_override(active_object=drawable, object=drawable, selected_objects=all_children(drawable)):
        result = bpy.ops.sollumz.export_assets(
            directory=out_dir,
            direct_export=True,
            use_custom_settings=True,
            target_formats={fmt},
            target_versions={"GEN8"},
            limit_to_selected=True,
            apply_transforms=False,
            export_ytyps=True,
            export_ytyps_include="SELECTED",
        )
    written = sorted(set(os.listdir(out_dir)) - before)
    return {
        "id": stem,
        "ok": "FINISHED" in result and bool(written),
        "format": fmt,
        "materials": mats,
        "collision_boxes": ncol,
        "lod_dist": archetype.lod_dist if archetype is not None else None,
        "written": written,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=("native", "cwxml"), default="native")
    ap.add_argument("--collision", default="PLASTIC")
    args = ap.parse_args(argv)
    sz = sollumz()
    if args.format == "native" and not sz["dependencies"].IS_SZIO_NATIVE_AVAILABLE:
        raise SystemExit("native export needs Sollumz's optional PyMateria dependency; use --format cwxml or install it")
    if os.path.isdir(args.blend):
        paths = [os.path.join(args.blend, f) for f in sorted(os.listdir(args.blend)) if f.endswith(".blend")]
    else:
        paths = [args.blend]
    out_dir = os.path.abspath(args.out)
    if len(paths) == 1:
        try:
            info = export_one(sz, paths[0], out_dir, args)
        except Exception as exc:
            info = {"id": os.path.basename(paths[0]), "ok": False, "error": repr(exc)}
        print("EXPORT " + json.dumps(info), flush=True)
        sys.stdout.flush()
        os._exit(0 if info.get("ok") else 1)
    ok = fail = 0
    for path in paths:
        cmd = [bpy.app.binary_path, "-b", "-P", os.path.abspath(__file__), "--", "--blend", path, "--out", out_dir, "--format", args.format, "--collision", args.collision]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in run.stdout.splitlines() if l.startswith("EXPORT ")]
        info = json.loads(lines[-1][7:]) if lines else {"id": os.path.basename(path), "ok": False, "error": "no EXPORT line", "tail": run.stdout[-400:]}
        print("EXPORT " + json.dumps(info), flush=True)
        ok += 1 if info.get("ok") else 0
        fail += 0 if info.get("ok") else 1
    print("RESULT ok={} fail={}".format(ok, fail), flush=True)


if __name__ == "__main__":
    main()
