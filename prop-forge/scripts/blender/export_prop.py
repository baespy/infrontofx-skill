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
BONE_DOF_FLAGS = ("RotX", "RotY", "RotZ", "TransX", "TransY", "TransZ", "ScaleX", "ScaleY", "ScaleZ")

if HERE not in sys.path:
    sys.path.insert(0, HERE)


def sollumz():
    if SZ not in bpy.context.preferences.addons:
        raise SystemExit("Sollumz extension is not enabled in this Blender (run without --factory-startup)")
    mods = {}
    for name in (
        "tools.drawablehelper",
        "tools.boundhelper",
        "tools.animationhelper",
        "tools.meshhelper",
        "ydr.shader_materials",
        "ybn.collision_materials",
        "ycd.ycdimport",
        "ycd.ycdexport",
        "sollumz_properties",
        "dependencies",
    ):
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


def ensure_dds(image, max_res, dds_cache=None):
    import dds_codec

    raw_path = bpy.path.abspath(image.filepath)
    if raw_path.lower().endswith(".dds"):
        png_cand = os.path.splitext(raw_path)[0] + ".png"
        src_path = png_cand if os.path.isfile(png_cand) else raw_path
    else:
        src_path = raw_path
    stem = os.path.splitext(os.path.basename(src_path or image.name))[0]
    dds = os.path.splitext(src_path)[0] + ".dds" if src_path else os.path.join(bpy.app.tempdir, stem + ".dds")
    key = (os.path.abspath(dds).lower(), int(max_res))
    if dds_cache is not None and key in dds_cache:
        image.filepath = dds
        image.reload()
        return dds, stem
    if src_path and src_path.lower().endswith(".png") and os.path.isfile(src_path):
        src_img = bpy.data.images.load(src_path, check_existing=False)
        try:
            dds_codec.encode_image_to_dds(src_img, dds_path=dds, max_res=max_res)
        finally:
            bpy.data.images.remove(src_img)
    else:
        if image.size[0] == 0:
            image.reload()
        dds_codec.encode_image_to_dds(image, dds_path=dds, max_res=max_res)
    if dds_cache is not None:
        dds_cache[key] = dds
    image.filepath = dds
    image.reload()
    return dds, stem


def convert_materials(sz, root, max_res=512, embed_textures=True):
    done = []
    dds_paths = {}
    dds_cache = {}
    for slot in root.material_slots:
        image = first_image(slot.material)
        if image is not None:
            dds_p, stem = ensure_dds(image, max_res, dds_cache=dds_cache)
            dds_paths[stem] = dds_p
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
                    node.texture_properties.embedded = bool(embed_textures)
                except AttributeError:
                    pass
            elif shader == "default_spec.sps" and hasattr(node, "set_float"):
                if node.name == "specularIntensityMult":
                    node.set_float(float(mat.get("prop_forge_spec_int", 0.48)))
                elif node.name == "specularFalloffMult":
                    node.set_float(float(mat.get("prop_forge_spec_falloff", 48.0)))
                elif node.name == "specularFresnel":
                    node.set_float(float(mat.get("prop_forge_spec_fresnel", 0.88)))
            elif shader in ("emissive.sps", "emissive_alpha.sps") and hasattr(node, "set_float"):
                if node.name == "emissiveMultiplier":
                    node.set_float(float(mat.get("prop_forge_emissive_mult", 1.6)))
        slot.material = new
        done.append("{} -> {}".format(mat.name, shader))
    return done, dds_paths


def prepare_mesh_attributes(sz, root):
    """Ensure Sollumz-required UV map ('UVMap 0') and white vertex color ('Color 1') exist before YDR export.

    Without 'UVMap 0' and 'Color 1' (CORNER, BYTE_COLOR, 255/255/255/255), Sollumz 2.9 omits TEXTURE0 and DIFFUSE
    from the binary vertex buffer, causing every prop to render pitch black in GTA V / FiveM.
    """
    me = root.data
    meshhelper = sz["meshhelper"]
    meshhelper.mesh_rename_uv_maps_by_order(me)
    uv_name = meshhelper.get_uv_map_name(0)
    if uv_name not in me.uv_layers:
        if me.uv_layers:
            me.uv_layers[0].name = uv_name
        else:
            raise RuntimeError("Mesh {} has no UV layer for {}".format(root.name, uv_name))
    me.uv_layers.active = me.uv_layers[uv_name]

    col_name = meshhelper.get_color_attr_name(0)
    col_attr = me.color_attributes.get(col_name)
    if col_attr is not None and (col_attr.domain != "CORNER" or col_attr.data_type != "BYTE_COLOR"):
        me.color_attributes.remove(col_attr)
        col_attr = None
    if col_attr is None:
        col_attr = me.color_attributes.new(name=col_name, type="BYTE_COLOR", domain="CORNER")
        n_loops = len(me.loops)
        col_attr.data.foreach_set("color_srgb", [1.0] * (n_loops * 4))
    me.color_attributes.active_color = col_attr
    me.update_tag()


def verify_native_ydr(ydr_path, expect_embedded=True):
    """Verify exported binary .ydr has valid TEXTURE0, white DIFFUSE vertex colors, and textures/refs."""
    import numpy as np
    import pymateria.gta5 as pmg
    import pymateria.gta5.gen8 as pmg8

    res = pmg8.Drawable.import_rsc(ydr_path)
    d = res.result
    if pmg.LodType.HIGH not in d.lods:
        raise RuntimeError("Exported YDR has no HIGH LOD: " + ydr_path)
    lod = d.lods[pmg.LodType.HIGH]
    if not lod.models:
        raise RuntimeError("Exported YDR has no HIGH LOD models: " + ydr_path)
    geom_count = 0
    for m in lod.models:
        for gi, g in enumerate(m.geometries):
            geom_count += 1
            buf = g.vb.buffer
            names = set(buf.dtype.names or ())
            if "TEXTURE0" not in names:
                raise RuntimeError("Exported YDR geometry {} missing TEXTURE0: {}".format(gi, ydr_path))
            if "DIFFUSE" not in names:
                raise RuntimeError("Exported YDR geometry {} missing DIFFUSE vertex color: {}".format(gi, ydr_path))
            uvs = buf["TEXTURE0"]
            if len(uvs) > 0 and float(np.ptp(uvs)) < 1e-4:
                raise RuntimeError("Exported YDR geometry {} has constant zero UVs: {}".format(gi, ydr_path))
            cols = buf["DIFFUSE"]
            if len(cols) > 0 and float(cols.mean()) < 10.0:
                raise RuntimeError("Exported YDR geometry {} has black DIFFUSE vertex colors: {}".format(gi, ydr_path))
    td = d.shader_group.texture_dictionary
    tex_count = len(td.textures) if td else 0
    if expect_embedded and tex_count == 0:
        raise RuntimeError("Exported YDR has 0 embedded textures: " + ydr_path)
    return {"geometries": geom_count, "embedded_textures": tex_count}


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


def build_rigged_drawable(sz, stem, root, rig):
    SollumType = sz["sollumz_properties"].SollumType
    action = rig.animation_data.action if rig.animation_data else None
    if rig.animation_data:
        rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()

    for idx, bone in enumerate(rig.data.bones):
        bone.bone_properties.tag = 0 if bone.name == "root" else idx
        bone.bone_properties.flags.clear()
        for fname in BONE_DOF_FLAGS:
            f = bone.bone_properties.flags.add()
            f.name = fname

    sz["drawablehelper"].convert_obj_to_model(root)
    root.name = stem + ".model"
    rig.name = stem
    rig.sollum_type = SollumType.DRAWABLE
    root.parent = rig
    root.location = (0.0, 0.0, 0.0)
    root.rotation_euler = (0.0, 0.0, 0.0)
    root.scale = (1.0, 1.0, 1.0)
    has_mod = False
    for m in root.modifiers:
        if m.type == "ARMATURE":
            m.object = rig
            has_mod = True
    if not has_mod:
        m = root.modifiers.new("Armature", "ARMATURE")
        m.object = rig
    return rig, action


def export_clip_dictionary(sz, stem, drawable, action, anim_meta, out_dir, fmt):
    SollumType = sz["sollumz_properties"].SollumType
    ycdimport = sz["ycdimport"]
    ycdexport = sz["ycdexport"]
    animhelper = sz["animationhelper"]

    scene = bpy.context.scene
    fps = int(anim_meta.get("fps", 30))
    scene.render.fps = fps

    clip_dict_obj, clips_obj, anims_obj = ycdimport.create_clip_dictionary_template(stem)

    anim_obj = ycdimport.create_anim_obj(SollumType.ANIMATION)
    anim_obj.name = stem
    anim_obj.animation_properties.hash = stem
    anim_obj.animation_properties.target_id = drawable.data
    anim_obj.animation_properties.action = action
    anim_obj.parent = anims_obj

    dur_frames = animhelper.get_action_duration_frames(action)
    dur_secs = animhelper.get_action_duration_secs(action)

    for clip_hash, clip_name in ((stem, stem + ".clip"), ("idle", "idle.clip")):
        clip_obj = ycdimport.create_anim_obj(SollumType.CLIP)
        clip_obj.name = clip_hash
        clip_obj.clip_properties.hash = clip_hash
        clip_obj.clip_properties.name = clip_name
        clip_obj.clip_properties.duration = dur_secs
        clip_obj.clip_properties.animations.clear()
        ca = clip_obj.clip_properties.animations.add()
        ca.animation = anim_obj
        ca.start_frame = 0.0
        ca.end_frame = float(dur_frames)
        clip_obj.parent = clips_obj

    ycd_xml_path = os.path.join(out_dir, stem + ".ycd.xml")
    ok = ycdexport.export_ycd(clip_dict_obj, ycd_xml_path)
    if not ok or not os.path.isfile(ycd_xml_path):
        raise RuntimeError("Sollumz export_ycd failed for " + stem)

    if fmt == "NATIVE":
        import ycd_rsc7
        ycd_bin_path = os.path.join(out_dir, stem + ".ycd")
        ycd_rsc7.compile_ycd_xml_to_binary(ycd_xml_path, ycd_bin_path)
        os.remove(ycd_xml_path)
        return stem + ".ycd"
    return stem + ".ycd.xml"


def build_shared_ytd(ytd_name, dds_map, out_dir):
    """Pack all unique DDS textures into one native RSC7 .ytd dictionary (zero duplicate VRAM)."""
    import pymateria.gta5.gen8 as pmg8

    txd = pmg8.TextureDictionary()
    for stem, dds_path in sorted(dds_map.items()):
        t = pmg8.Texture()
        t.name = stem
        t.import_dds(dds_path)
        txd.textures[stem] = t
    ytd_path = os.path.join(out_dir, ytd_name + ".ytd")
    pmg8.TextureDictionary.export_rsc(txd, ytd_path)
    # Round-trip verify
    txd2 = pmg8.TextureDictionary.import_rsc(ytd_path).result
    tex_info = {}
    raw_bytes = 0
    for _, t in txd2.textures.items():
        tb = sum(len(l) for mip in t.mips for l in mip.layers)
        raw_bytes += tb
        tex_info[t.name] = "{}x{} {} mips={} {}KB".format(t.width, t.height, str(t.format).split(".")[-1], len(t.mips), tb // 1024)
    return {
        "ytd": ytd_name + ".ytd",
        "file_kb": os.path.getsize(ytd_path) // 1024,
        "raw_vram_kb": raw_bytes // 1024,
        "count": len(tex_info),
        "textures": tex_info,
    }


def export_one(sz, path, out_dir, args):
    bpy.ops.wm.open_mainfile(filepath=path)
    stem = os.path.splitext(os.path.basename(path))[0]
    root = bpy.data.objects.get(stem)
    if root is None or root.type != "MESH":
        return {"id": stem, "ok": False, "error": "no mesh named " + stem}
    meta = json.loads(root.get("prop_forge", "{}"))
    anim_meta = meta.get("anim")
    rig = bpy.data.objects.get(anim_meta["rig_name"]) if anim_meta else None
    embed_tex = not bool(args.shared_ytd)
    mats, dds_paths = convert_materials(sz, root, max_res=args.max_res, embed_textures=embed_tex)
    prepare_mesh_attributes(sz, root)
    composite, ncol = build_collision(sz, root, args.collision)
    action = None
    if rig is not None and rig.type == "ARMATURE":
        drawable, action = build_rigged_drawable(sz, stem, root, rig)
    else:
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
        lod_val = float(meta.get("lod_dist", 100))
        archetype.lod_dist = lod_val
        archetype.hd_texture_dist = lod_val
        if args.shared_ytd:
            archetype.texture_dictionary = args.shared_ytd
        if action is not None:
            archetype.clip_dictionary = stem
            archetype.flags.flag10 = True  # Has Anim (YCD)
            archetype.flags.flag20 = bool(anim_meta.get("auto_start", True))  # Auto Start Anim
            archetype.flags.flag30 = True  # Use Ambient Scale
    select_only(all_children(drawable))
    fmt = "NATIVE" if args.format == "native" else "CWXML"
    os.makedirs(out_dir, exist_ok=True)
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
    ycd_file = None
    if action is not None:
        ycd_file = export_clip_dictionary(sz, stem, drawable, action, anim_meta, out_dir, fmt)
    ydr_check = None
    ext = ".ydr" if fmt == "NATIVE" else ".ydr.xml"
    ydr_out = os.path.join(out_dir, stem + ext)
    if fmt == "NATIVE" and "FINISHED" in result:
        ydr_check = verify_native_ydr(ydr_out, expect_embedded=embed_tex)
    written = [fn for fn in (stem + ext, stem + (".ytyp" if fmt == "NATIVE" else ".ytyp.xml"), ycd_file) if fn and os.path.isfile(os.path.join(out_dir, fn))]
    return {
        "id": stem,
        "ok": "FINISHED" in result and os.path.isfile(ydr_out),
        "format": fmt,
        "materials": mats,
        "dds_paths": dds_paths,
        "collision_boxes": ncol,
        "lod_dist": archetype.lod_dist if archetype is not None else None,
        "hd_texture_dist": archetype.hd_texture_dist if archetype is not None else None,
        "texture_dictionary": archetype.texture_dictionary if archetype is not None else None,
        "animated": action is not None,
        "ycd": ycd_file,
        "ydr_check": ydr_check,
        "written": written,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=("native", "cwxml"), default="native")
    ap.add_argument("--collision", default="PLASTIC")
    ap.add_argument("--max-res", type=int, default=512)
    ap.add_argument("--shared-ytd", default="")
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
    all_dds = {}
    for path in paths:
        cmd = [
            bpy.app.binary_path, "-b", "-P", os.path.abspath(__file__), "--",
            "--blend", path, "--out", out_dir, "--format", args.format, "--collision", args.collision,
            "--max-res", str(args.max_res),
        ]
        if args.shared_ytd:
            cmd += ["--shared-ytd", args.shared_ytd]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in run.stdout.splitlines() if l.startswith("EXPORT ")]
        info = json.loads(lines[-1][7:]) if lines else {"id": os.path.basename(path), "ok": False, "error": "no EXPORT line", "tail": run.stdout[-400:]}
        all_dds.update(info.get("dds_paths") or {})
        print("EXPORT " + json.dumps(info), flush=True)
        ok += 1 if info.get("ok") else 0
        fail += 0 if info.get("ok") else 1
    if args.shared_ytd and args.format == "native" and all_dds:
        ytd_info = build_shared_ytd(args.shared_ytd, all_dds, out_dir)
        print("SHARED_YTD " + json.dumps(ytd_info), flush=True)
    print("RESULT ok={} fail={}".format(ok, fail), flush=True)


if __name__ == "__main__":
    main()
