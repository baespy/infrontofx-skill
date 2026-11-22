"""map-forge: Universal native FiveM GEN8 map exporter (Sollumz 2.9 + PyMateria + PCA DXT1/DXT5).

Exports a complete standalone FiveM map resource from:
  - `--spec`:     map-spec.json (anchor, entities [custom + vanilla], texture_rules, prop_overrides, vanilla_ytyps)
  - `--props`:    directory of modular/hero `<id>.blend` files (saved in Blender 4.2 format)
  - `--textures`: directory of PBR `.png` textures (`*_n.png` auto-flipped to DirectX -Y, `*_s.png` spec)
  - `--out`:      output resource package directory (writes `fxmanifest.lua` + `stream/` binaries)

Run WITHOUT --factory-startup so Sollumz + szio + PyMateria load:
  blender.exe -b -P export_map.py -- --spec map-spec.json --props build/props --textures build/textures --out my_map_pkg
"""

import argparse
import importlib
import json
import math
import os
import shutil
import subprocess
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import dds_codec


def get_sollumz_modules():
    """Robustly locate Sollumz 2.9+ helper modules."""
    pkg = None
    for addon in bpy.context.preferences.addons:
        if "sollumz" in addon.module.lower():
            pkg = addon.module
            break
    if pkg is None:
        raise RuntimeError("Sollumz addon not loaded. Run Blender 4.2.3 WITHOUT --factory-startup.")
    mods = {
        "sollumz_properties": importlib.import_module(pkg + ".sollumz_properties"),
        "shader_materials": importlib.import_module(pkg + ".ydr.shader_materials"),
        "drawablehelper": importlib.import_module(pkg + ".tools.drawablehelper"),
        "boundhelper": importlib.import_module(pkg + ".tools.boundhelper"),
        "collision_materials": importlib.import_module(pkg + ".ybn.collision_materials"),
        "meshhelper": importlib.import_module(pkg + ".tools.meshhelper"),
        "dependencies": importlib.import_module(pkg + ".dependencies"),
    }
    if not mods["dependencies"].IS_SZIO_AVAILABLE:
        raise RuntimeError("Sollumz szio dependency missing: run Sollumz > Preferences > Install Dependencies.")
    return mods


def all_children(obj):
    out = [obj]
    for ch in obj.children:
        out.extend(all_children(ch))
    return out


def select_only(objs):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        if o.name in bpy.context.scene.objects:
            o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def collision_index(sz, mat_name):
    mats = getattr(sz["collision_materials"], "collisionmats", None)
    if mats:
        upper = mat_name.upper()
        for idx, m in enumerate(mats):
            n = getattr(m, "name", "") or ""
            if n.upper() == upper:
                return idx
    return 0


def pick_max_res(stem, rules):
    low = stem.lower()
    for p in rules.get("swatch_prefixes", ["swatch_", "trim_"]):
        if low.startswith(p.lower()):
            return int(rules.get("swatch_max_res", 32))
    if low.endswith("_n"):
        return int(rules.get("normal_max_res", 256))
    if low.endswith("_s"):
        return int(rules.get("spec_max_res", 256))
    for p in rules.get("hero_prefixes", ["logo_", "sign_", "brand_"]):
        if low.startswith(p.lower()):
            return int(rules.get("hero_diffuse_max_res", 1024))
    return int(rules.get("default_diffuse_max_res", 512))


def encode_shared_pbr_dds(tex_dir, spec):
    """Encode all PNGs in tex_dir to DDS (DirectX -Y normal flip, tiered resolution, PCA DXT1/DXT5)."""
    rules = spec.get("texture_rules", {})
    dds_map = {}
    if not tex_dir or not os.path.isdir(tex_dir):
        return dds_map
    for fn in sorted(os.listdir(tex_dir)):
        if not fn.lower().endswith(".png"):
            continue
        stem = os.path.splitext(fn)[0]
        png_path = os.path.join(tex_dir, fn)
        dds_path = os.path.join(tex_dir, stem + ".dds")
        is_normal = stem.lower().endswith("_n")
        max_res = pick_max_res(stem, rules)

        img = bpy.data.images.load(png_path, check_existing=False)
        try:
            if is_normal:
                w, h = img.size[0], img.size[1]
                buf = np.empty(w * h * 4, dtype=np.float32)
                img.pixels.foreach_get(buf)
                arr = buf.reshape((h, w, 4))
                arr[:, :, 1] = 1.0 - arr[:, :, 1]
                tmp = bpy.data.images.new(stem + "_dx", width=w, height=h, alpha=False)
                tmp.pixels.foreach_set(arr.ravel())
                try:
                    dds_codec.encode_image_to_dds(tmp, dds_path=dds_path, max_res=max_res)
                finally:
                    bpy.data.images.remove(tmp)
            else:
                dds_codec.encode_image_to_dds(img, dds_path=dds_path, max_res=max_res)
        finally:
            bpy.data.images.remove(img)
        dds_map[stem] = dds_path
    return dds_map


def convert_materials_for_sollumz(sz, root):
    done = []
    for slot in root.material_slots:
        mat = slot.material
        if mat is None or getattr(mat, "sollum_type", "") == "sollumz_material_shader":
            continue
        shader = mat.get("map_forge_shader") or mat.get("prop_forge_shader") or "default.sps"
        sampler_imgs = {}
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image is not None and node.name in (
                    "DiffuseSampler", "BumpSampler", "SpecSampler", "DetailSampler"
                ):
                    raw_p = bpy.path.abspath(node.image.filepath)
                    dds_p = os.path.splitext(raw_p)[0] + ".dds"
                    if not os.path.isfile(dds_p):
                        raise RuntimeError(f"Missing pre-encoded DDS for {node.name}: {dds_p}")
                    sampler_imgs[node.name] = bpy.data.images.load(dds_p, check_existing=True)

        new_mat = sz["shader_materials"].create_shader(shader)
        new_mat.name = mat.name

        def _get_f(key_a, key_b, default):
            if key_a in mat:
                return float(mat[key_a])
            if key_b in mat:
                return float(mat[key_b])
            return default

        for node in new_mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.name in sampler_imgs:
                node.image = sampler_imgs[node.name]
                try:
                    node.texture_properties.embedded = False
                except AttributeError:
                    pass
            elif hasattr(node, "set_float"):
                if node.name == "bumpiness":
                    node.set_float(_get_f("map_forge_bumpiness", "prop_forge_bumpiness", 1.0))
                elif node.name == "specularIntensityMult":
                    node.set_float(_get_f("map_forge_spec_int", "prop_forge_spec_int", 0.25))
                elif node.name == "specularFalloffMult":
                    node.set_float(_get_f("map_forge_spec_falloff", "prop_forge_spec_falloff", 40.0))
                elif node.name == "specularFresnel":
                    node.set_float(_get_f("map_forge_spec_fresnel", "prop_forge_spec_fresnel", 0.85))
                elif node.name == "emissiveMultiplier":
                    node.set_float(_get_f("map_forge_emissive_mult", "prop_forge_emissive_mult", 2.0))
                elif node.name == "wetnessMultiplier":
                    node.set_float(_get_f("map_forge_wetness", "prop_forge_wetness", 1.0))
                elif node.name == "SpecularFalloff":
                    node.set_float(_get_f("map_forge_water_falloff", "prop_forge_water_falloff", 1118.0))
                elif node.name == "SpecularIntensity":
                    node.set_float(_get_f("map_forge_water_spec", "prop_forge_water_spec", 1.0))
                elif node.name == "RippleScale":
                    node.set_float(_get_f("map_forge_ripple_scale", "prop_forge_ripple_scale", 0.04))
                elif node.name == "RippleBumpiness":
                    node.set_float(_get_f("map_forge_ripple_bump", "prop_forge_ripple_bump", 0.356))

        slot.material = new_mat
        done.append(f"{mat.name}->{shader}")
    return done


def ensure_rage_mesh_attributes(root):
    """Ensure UVMap 0 and Color 1 (defaulting to #FF00FF outdoor RAGE ambient if absent)."""
    me = root.data
    if me.uv_layers:
        if "UVMap 0" not in me.uv_layers:
            me.uv_layers[0].name = "UVMap 0"
    else:
        me.uv_layers.new(name="UVMap 0")

    ca = me.color_attributes.get("Color 1")
    if ca is None:
        if me.color_attributes:
            me.color_attributes[0].name = "Color 1"
        else:
            ca = me.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
            n = len(ca.data)
            # #FF00FF exterior RAGE baseline: R=1 (day), G=0 (no artificial night glow), B=1 (AO), A=1
            vals = np.tile(np.array([1.0, 0.0, 1.0, 1.0], dtype=np.float32), n)
            ca.data.foreach_set("color", vals)


def build_embedded_collision(sz, root, col_mat_name):
    stem = root.name
    col_objs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(stem + "_col_")]
    if not col_objs:
        return None, 0
    cidx = collision_index(sz, col_mat_name)
    cmat = sz["collision_materials"].create_collision_material_from_index(cidx)
    for o in col_objs:
        o.data.materials.clear()
        o.data.materials.append(cmat)
    SollumType = sz["sollumz_properties"].SollumType
    preset = getattr(bpy.context.scene, "sz_default_flag_preset_name", "General (Default)")
    composite = sz["boundhelper"].convert_objs_to_single_composite(col_objs, SollumType.BOUND_GEOMETRYBVH, preset)
    return composite, len(col_objs)


def _studio_full_collision_flags(pmg):
    cf = pmg.CollisionFlags
    t_std = cf.MAP_TYPE_WEAPON | cf.MAP_TYPE_MOVER | cf.MAP_TYPE_HORSE | cf.MAP_TYPE_COVER | cf.MAP_TYPE_VEHICLE
    # Exact Rockstar canonical static-map include_flags (collides solidly with ALL Peds, Ragdolls, Vehicles, Objects,
    # Projectiles, Weapons, Cameras, AI, Scripts, Wheels & Glass — while EXCLUDING MAP_TYPE_* so static .ybn + .ydr
    # bounds never generate redundant static-vs-static physics broadphase contacts!).
    inc_std = (
        cf.VEHICLE_NON_BVH_TYPE | cf.VEHICLE_BVH_TYPE | cf.PED_TYPE | cf.RAGDOLL_TYPE
        | cf.HORSE_TYPE | cf.HORSE_RAGDOLL_TYPE | cf.OBJECT_TYPE | cf.PLANT_TYPE
        | cf.PROJECTILE_TYPE | cf.EXPLOSION_TYPE | cf.FORKLIFT_FORKS_TYPE
        | cf.WEAPON_TEST | cf.CAMERA_TEST | cf.AI_TEST | cf.SCRIPT_TEST
        | cf.WHEEL_TEST | cf.GLASS_TYPE
    )
    return t_std, inc_std


def patch_bound_composite_flags(bound_obj, pmg):
    if bound_obj is None or not hasattr(bound_obj, "bounds"):
        return 0
    t_std, all_inc = _studio_full_collision_flags(pmg)
    cnt = 0
    for i in range(len(bound_obj.bounds)):
        el = bound_obj.bounds[i]
        el.type_flags = t_std
        el.include_flags = all_inc
        bound_obj.bounds[i] = el
        cnt += 1
    return cnt


def inject_drawable_lights(ydr_path, light_specs, water_fog=None):
    """Upgrade embedded Drawable collision flags to full studio flags + optional water FogColor + inject PyMateria Drawable.lights."""
    import pymateria as pma
    import pymateria.gta5 as pmg
    import pymateria.gta5.gen8 as pmg8

    d = pmg8.Drawable.import_rsc(ydr_path).result
    changed = False
    if getattr(d, "bound", None) is not None and patch_bound_composite_flags(d.bound, pmg) > 0:
        changed = True
    if water_fog and len(water_fog) == 4 and getattr(d, "shader_group", None):
        wf = pma.Vector4f(float(water_fog[0]), float(water_fog[1]), float(water_fog[2]), float(water_fog[3]))
        for sh in d.shader_group.shaders:
            if "water" in sh.basis_material.string_or_placeholder.lower():
                for pr in sh.parameters:
                    if pr.name.string_or_placeholder == "FogColor":
                        pr.data = [wf]
                        changed = True
    if not light_specs:
        if changed:
            pmg8.Drawable.export_rsc(d, ydr_path)
        return 0
    for ls in light_specs:
        l = pmg.Light()
        ltype = str(ls.get("type", "POINT")).upper()
        l.type = getattr(pmg.LightType, ltype, pmg.LightType.POINT)
        pos = ls.get("position", [0.0, 0.0, 3.0])
        l.position = pma.Vector3f(float(pos[0]), float(pos[1]), float(pos[2]))
        dvec = Vector(ls.get("direction", [0.0, 0.0, -1.0])).normalized()
        l.direction = pma.Vector3f(float(dvec.x), float(dvec.y), float(dvec.z))
        up = Vector((0.0, 1.0, 0.0)) if abs(dvec.z) > 0.9 else Vector((0.0, 0.0, 1.0))
        tvec = dvec.cross(up).normalized()
        l.tangent = pma.Vector3f(float(tvec.x), float(tvec.y), float(tvec.z))
        col = ls.get("color", [255, 224, 168])
        l.color = pma.ColorRGB(int(col[0]), int(col[1]), int(col[2]))
        l.intensity = float(ls.get("intensity", 3.0))
        l.falloff = float(ls.get("falloff", 30.0))
        l.falloff_exponent = float(ls.get("falloff_exponent", 128.0))
        l.cone_inner_angle = float(ls.get("cone_inner_angle", 25.0 if ltype == "SPOT" else 0.0))
        l.cone_outer_angle = float(ls.get("cone_outer_angle", 80.0 if ltype == "SPOT" else 0.0))
        l.corona_size = float(ls.get("corona_size", 0.5))
        l.corona_intensity = float(ls.get("corona_intensity", 0.0))
        l.flashiness = pmg.LightFlashiness.CONSTANT
        l.shadow_near_clip = float(ls.get("shadow_near_clip", 0.55))
        l.volume_intensity = float(ls.get("volume_intensity", 0.0))
        l.volume_size_scale = float(ls.get("volume_size_scale", 1.0))

        tf_mode = str(ls.get("time_flags", "NIGHT")).upper()
        if tf_mode == "ALWAYS":
            l.time_flags = pmg.TimeFlags.ALWAYS
        elif tf_mode == "DAY":
            l.time_flags = pmg.TimeFlags.DAY
        else:
            l.time_flags = pmg.TimeFlags.NIGHT

        lf = pmg.LightFlags(0)
        if ls.get("cast_static_shadows", False):
            lf = lf | pmg.LightFlags.CAST_STATIC_GEOM_SHADOWS
        if ls.get("cast_dynamic_shadows", False):
            lf = lf | pmg.LightFlags.CAST_DYNAMIC_GEOM_SHADOWS
        if ls.get("exterior_only", False):
            lf = lf | pmg.LightFlags.EXTERIOR_ONLY
        if ls.get("interior_only", False):
            lf = lf | pmg.LightFlags.INTERIOR_ONLY
        l.flags = lf
        d.lights.append(l)

    pmg8.Drawable.export_rsc(d, ydr_path)
    return len(light_specs)


def ydr_bounds(d):
    import pymateria as pma
    import pymateria.gta5 as pmg

    chunks = []
    for m in d.lods[pmg.LodType.HIGH].models:
        for g in m.geometries:
            pos = g.vb.buffer["POSITION"]
            if len(pos) > 0:
                chunks.append(np.asarray(pos, dtype=np.float64)[:, :3])
    pts = np.concatenate(chunks, axis=0)
    lo = pts.min(axis=0)
    hi = pts.max(axis=0)
    ctr = (lo + hi) * 0.5
    rad = float(np.linalg.norm(pts - ctr, axis=1).max())
    aabb = pma.AABB3f(
        pma.Vector3f(float(lo[0]), float(lo[1]), float(lo[2])),
        pma.Vector3f(float(hi[0]), float(hi[1]), float(hi[2])),
    )
    sphere = pma.Sphere(pma.Vector3f(float(ctr[0]), float(ctr[1]), float(ctr[2])), rad)
    return aabb, sphere, Vector((float(lo[0]), float(lo[1]), float(lo[2]))), Vector((float(hi[0]), float(hi[1]), float(hi[2])))


def export_single_ydr(blend_path, out_dir, spec):
    sz = get_sollumz_modules()
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    stem = os.path.splitext(os.path.basename(blend_path))[0]
    root = bpy.data.objects.get(stem)
    if root is None or root.type != "MESH":
        raise RuntimeError(f"Missing drawable mesh {stem} in {blend_path}")

    meta = json.loads(root.get("map_forge") or root.get("prop_forge") or "{}")
    ov = spec.get("prop_overrides", {}).get(stem, {})
    col_mat = ov.get("collision_material") or meta.get("collision_material") or "CONCRETE"
    lights_cfg = ov.get("lights") or meta.get("lights") or []

    mats = convert_materials_for_sollumz(sz, root)
    ensure_rage_mesh_attributes(root)
    composite, n_cols = build_embedded_collision(sz, root, col_mat)

    drawable = sz["drawablehelper"].convert_obj_to_drawable(root)
    drawable.name = stem
    if composite is not None:
        composite.parent = drawable
        composite.location = (0.0, 0.0, 0.0)

    os.makedirs(out_dir, exist_ok=True)
    select_only(all_children(drawable))
    with bpy.context.temp_override(active_object=drawable, object=drawable, selected_objects=all_children(drawable)):
        res = bpy.ops.sollumz.export_assets(
            directory=out_dir,
            direct_export=True,
            use_custom_settings=True,
            target_formats={"NATIVE"},
            target_versions={"GEN8"},
            limit_to_selected=True,
            apply_transforms=False,
            export_ytyps=False,
        )
    if "FINISHED" not in res:
        raise RuntimeError(f"sollumz.export_assets returned {res}")

    ydr_path = os.path.join(out_dir, stem + ".ydr")
    if not os.path.isfile(ydr_path):
        raise RuntimeError("Missing exported YDR: " + ydr_path)

    n_lights = inject_drawable_lights(ydr_path, lights_cfg, water_fog=ov.get("water_fog_color"))
    print("YDR_EXPORT " + json.dumps({
        "id": stem,
        "bytes": os.path.getsize(ydr_path),
        "materials": len(mats),
        "colliders": n_cols,
        "lights": n_lights,
    }), flush=True)


def _get_arenas(spec):
    """Return list of arena anchor dicts (supports single `anchor` or multi-arena `arenas` sharing 1 YDR/YTD/YTYP!)."""
    if spec.get("arenas"):
        return list(spec["arenas"])
    return [spec["anchor"]]


def export_static_world_ybn(spec, props_dir, out_dir, arena_idx=0):
    import pymateria.gta5 as pmg

    sz = get_sollumz_modules()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    arenas = _get_arenas(spec)
    anchor = arenas[arena_idx]
    ybn_name = anchor.get("ybn_name")
    if not ybn_name:
        return
    origin = Vector(anchor["center"])
    static_ents = [e for e in spec["entities"] if (not e.get("vanilla")) and e.get("static_col", True)]
    if not static_ents:
        return

    unique_models = sorted({e["model"] for e in static_ents})
    col_templates = {}
    for model_name in unique_models:
        bpath = os.path.join(props_dir, model_name + ".blend")
        with bpy.data.libraries.load(bpath, link=False) as (data_from, data_to):
            data_to.objects = [n for n in data_from.objects if n == model_name or n.startswith(model_name + "_col_")]
        root_ob = bpy.data.objects.get(model_name)
        ov = spec.get("prop_overrides", {}).get(model_name, {})
        meta = json.loads(root_ob.get("map_forge") or root_ob.get("prop_forge") or "{}") if root_ob else {}
        col_mat = ov.get("collision_material") or meta.get("collision_material") or "CONCRETE"
        col_meshes = []
        for ob in list(bpy.data.objects):
            if ob.name.startswith(model_name + "_col_") and ob.type == "MESH":
                verts = [ob.matrix_world @ v.co for v in ob.data.vertices]
                faces = [list(p.vertices) for p in ob.data.polygons]
                col_meshes.append((verts, faces))
        col_templates[model_name] = (col_mat, col_meshes)
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob, do_unlink=True)

    bms_by_mat = {}
    placed = 0
    for item in static_ents:
        col_mat, col_meshes = col_templates[item["model"]]
        if not col_meshes:
            continue
        bm = bms_by_mat.setdefault(col_mat, bmesh.new())
        world_pos = origin + Vector(item["pos"])
        yaw_rad = math.radians(float(item.get("yaw_deg", 0.0)))
        M_world = Matrix.Translation(world_pos) @ Matrix.Rotation(yaw_rad, 4, "Z")
        for verts, faces in col_meshes:
            bverts = [bm.verts.new(M_world @ v) for v in verts]
            for fidx in faces:
                try:
                    bm.faces.new([bverts[i] for i in fidx])
                except ValueError:
                    pass
            placed += 1

    col_objs = []
    for mat_name, bm in sorted(bms_by_mat.items()):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f"{ybn_name}_{mat_name.lower()}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        cidx = collision_index(sz, mat_name)
        ob.data.materials.append(sz["collision_materials"].create_collision_material_from_index(cidx))
        col_objs.append(ob)

    SollumType = sz["sollumz_properties"].SollumType
    preset = getattr(bpy.context.scene, "sz_default_flag_preset_name", "General (Default)")
    composite = sz["boundhelper"].convert_objs_to_single_composite(col_objs, SollumType.BOUND_GEOMETRYBVH, preset)
    composite.name = ybn_name

    select_only(all_children(composite))
    with bpy.context.temp_override(active_object=composite, object=composite, selected_objects=all_children(composite)):
        res = bpy.ops.sollumz.export_assets(
            directory=out_dir,
            direct_export=True,
            use_custom_settings=True,
            target_formats={"NATIVE"},
            target_versions={"GEN8"},
            limit_to_selected=True,
            apply_transforms=False,
            export_ytyps=False,
        )
    if "FINISHED" not in res:
        raise RuntimeError(f"sollumz.export_assets (.ybn) returned {res}")

    ybn_path = os.path.join(out_dir, ybn_name + ".ybn")
    b = pmg.Bound.import_rsc(ybn_path).result
    # Upgrade all child bounds to full studio include_flags (DEFAULT_TYPE|MAP_TYPE_MOVER|PED|VEHICLE|STAIR_SLOPE|SCRIPT_TEST|...)
    if patch_bound_composite_flags(b, pmg) > 0:
        pmg.Bound.export_rsc(b, ybn_path)
        b = pmg.Bound.import_rsc(ybn_path).result
    total_prims = sum(len(c.bound.primitives) for c in b.bounds if hasattr(c.bound, "primitives"))
    print("YBN_EXPORT " + json.dumps({
        "ybn": os.path.basename(ybn_path),
        "bytes": os.path.getsize(ybn_path),
        "children": len(b.bounds),
        "placed_colliders": placed,
        "prims": total_prims,
    }), flush=True)


def build_shared_ytd(ytd_name, dds_map, out_dir):
    import pymateria.gta5.gen8 as pmg8

    txd = pmg8.TextureDictionary()
    for stem, dds_path in sorted(dds_map.items()):
        tex = pmg8.Texture()
        tex.name = stem
        tex.import_dds(dds_path)
        txd.textures[stem] = tex
    ytd_path = os.path.join(out_dir, ytd_name + ".ytd")
    pmg8.TextureDictionary.export_rsc(txd, ytd_path)
    check = pmg8.TextureDictionary.import_rsc(ytd_path).result
    vram_b = sum(len(l) for _, t in check.textures.items() for m in t.mips for l in m.layers)
    return {
        "file": os.path.basename(ytd_path),
        "bytes": os.path.getsize(ytd_path),
        "textures": len(check.textures),
        "vram_mb": round(vram_b / (1024 * 1024), 2),
    }


def build_ytd_ytyp_ymap_package(spec, stream_dir, pkg_dir, dds_map):
    import pymateria as pma
    import pymateria.gta5 as pmg
    import pymateria.gta5.gen8 as pmg8

    shared_ytd = spec["shared_ytd"]
    ytyp_name = spec["ytyp_name"]
    anchor = spec.get("anchor") or _get_arenas(spec)[0]
    ymap_name = anchor["ymap_name"]
    ybn_name = anchor.get("ybn_name", "")
    origin = Vector(anchor["center"])

    if dds_map:
        ytd_info = build_shared_ytd(shared_ytd, dds_map, stream_dir)
        print("SHARED_YTD " + json.dumps(ytd_info), flush=True)

    ydr_files = sorted(f for f in os.listdir(stream_dir) if f.lower().endswith(".ydr"))
    mt = pmg8.MapTypes()
    mt.name = ytyp_name
    bounds_by_id = {}
    lod_by_id = {}

    for fname in ydr_files:
        prop_id = os.path.splitext(fname)[0]
        ydr_path = os.path.join(stream_dir, fname)
        d = pmg8.Drawable.import_rsc(ydr_path).result
        aabb, sphere, bb_lo, bb_hi = ydr_bounds(d)
        bounds_by_id[prop_id] = (bb_lo, bb_hi)
        ov = spec.get("prop_overrides", {}).get(prop_id, {})
        lod_d = float(ov.get("lod_dist", 380.0))
        lod_by_id[prop_id] = lod_d

        arch = pmg.ArchetypeDefinition()
        arch.name = prop_id
        arch.asset_name = prop_id
        arch.asset_type = pmg.ArchetypeAssetType.DRAWABLE
        arch.texture_dictionary = shared_ytd
        arch.physics_dictionary = prop_id
        arch.flags = int(ov.get("arch_flags", 32))
        arch.lod_distance = lod_d
        arch.hd_texture_distance = lod_d
        arch.bounding_box = aabb
        arch.bounding_sphere = sphere
        mt.archetypes.append(arch)

    ytyp_path = os.path.join(stream_dir, ytyp_name + ".ytyp")
    pmg8.MapTypes.export_rsc(mt, ytyp_path)
    print("YTYP_EXPORT " + json.dumps({"file": os.path.basename(ytyp_path), "archetypes": len(mt.archetypes)}), flush=True)

    arenas = _get_arenas(spec)
    ymap_names_exported = []
    for arena in arenas:
        a_origin = Vector(arena["center"])
        a_ymap = arena["ymap_name"]
        a_ybn = arena.get("ybn_name")
        md = pmg.MapData()
        md.name = a_ymap
        md.flags = 0
        has_ybn = bool(a_ybn and os.path.isfile(os.path.join(stream_dir, a_ybn + ".ybn")))
        md.content_flags = (1 | 64) if has_ybn else 1
        if has_ybn:
            md.physics_dictionaries = [pmg.CombinedHashString(a_ybn)]

        ent_min = Vector((1e9, 1e9, 1e9))
        ent_max = Vector((-1e9, -1e9, -1e9))
        strm_min = Vector((1e9, 1e9, 1e9))
        strm_max = Vector((-1e9, -1e9, -1e9))

        for idx, item in enumerate(spec["entities"]):
            model_name = item["model"]
            is_vanilla = bool(item.get("vanilla", False))
            if (not is_vanilla) and model_name not in bounds_by_id:
                raise RuntimeError("Missing exported YDR for custom entity: " + model_name)

            pos = a_origin + Vector(item["pos"])
            rx = math.radians(float(item.get("pitch_deg", 0.0)))
            ry = math.radians(float(item.get("roll_deg", 0.0)))
            rz = math.radians(float(item.get("yaw_deg", 0.0)))
            q = Euler((rx, ry, rz), "XYZ").to_quaternion()
            q_gtav = q.inverted()

            if is_vanilla:
                kind = str(item.get("kind", "")).lower()
                lod_d = float(item.get("lod_dist", 340.0 if "tree" in kind else 220.0))
                bb_lo = Vector((-6.0, -6.0, -0.5)) if "tree" in kind else Vector((-2.0, -2.0, -0.3))
                bb_hi = Vector((6.0, 6.0, 14.0)) if "tree" in kind else Vector((2.0, 2.0, 4.5))
            else:
                lod_d = float(item.get("lod_dist", lod_by_id[model_name]))
                bb_lo, bb_hi = bounds_by_id[model_name]

            e = pmg.ArchetypeEntity()
            e.archetype_name = model_name
            e.position = pma.Vector3f(pos.x, pos.y, pos.z)
            e.rotation = pma.Quaternion(q_gtav.x, q_gtav.y, q_gtav.z, q_gtav.w)
            e.scale_xy = float(item.get("scale_xy", 1.0))
            e.scale_z = float(item.get("scale_z", 1.0))
            # Clean studio static prop flag (32 = FLAG_STATIC_PROP, matching all verified studio custom YMAPs;
            # avoids adding 524288|1048576 reflection/dynamic-gate bits across 200+ props which can exhaust a 256-slot pool!)
            e.flags = int(item.get("flags", 32))
            e.guid = (zlib.crc32(f"{a_ymap}:{idx}:{model_name}".encode("utf-8")) & 0xFFFFFFFF) or (idx + 1)
            e.parent_index = -1
            e.lod_distance = lod_d
            e.child_lod_distance = 0.0
            e.lod_level = pmg.ArchetypeLodType.ORPHANHD
            e.priority_level = pmg.PriorityLevel.REQUIRED
            e.num_children = 0
            e.ambient_occlusion_multiplier = int(item.get("ao_natural", 255))
            e.artificial_ambient_occlusion = int(item.get("ao_artificial", 255))
            e.tint_value = 0
            md.entities.append(e)

            rot_mat = q.to_matrix()
            for cx in (bb_lo.x, bb_hi.x):
                for cy in (bb_lo.y, bb_hi.y):
                    for cz in (bb_lo.z, bb_hi.z):
                        wp = pos + (rot_mat @ Vector((cx, cy, cz)))
                        for ax in range(3):
                            ent_min[ax] = min(ent_min[ax], wp[ax])
                            ent_max[ax] = max(ent_max[ax], wp[ax])
                            strm_min[ax] = min(strm_min[ax], wp[ax] - lod_d)
                            strm_max[ax] = max(strm_max[ax], wp[ax] + lod_d)

        if has_ybn:
            yb = pmg.Bound.import_rsc(os.path.join(stream_dir, a_ybn + ".ybn")).result
            if hasattr(yb, "bounds"):
                for ch in yb.bounds:
                    bb = getattr(ch.bound, "bounding_box", None)
                    if bb is not None:
                        for pt in (bb.min, bb.max):
                            ent_min.x = min(ent_min.x, pt.x); ent_max.x = max(ent_max.x, pt.x)
                            ent_min.y = min(ent_min.y, pt.y); ent_max.y = max(ent_max.y, pt.y)
                            ent_min.z = min(ent_min.z, pt.z); ent_max.z = max(ent_max.z, pt.z)
                            strm_min.x = min(strm_min.x, pt.x - 450.0); strm_max.x = max(strm_max.x, pt.x + 450.0)
                            strm_min.y = min(strm_min.y, pt.y - 450.0); strm_max.y = max(strm_max.y, pt.y + 450.0)
                            strm_min.z = min(strm_min.z, pt.z - 450.0); strm_max.z = max(strm_max.z, pt.z + 450.0)

        md.entities_extents_min = pma.Vector3f(ent_min.x, ent_min.y, ent_min.z)
        md.entities_extents_max = pma.Vector3f(ent_max.x, ent_max.y, ent_max.z)
        md.streaming_extents_min = pma.Vector3f(strm_min.x, strm_min.y, strm_min.z)
        md.streaming_extents_max = pma.Vector3f(strm_max.x, strm_max.y, strm_max.z)

        ymap_path = os.path.join(stream_dir, a_ymap + ".ymap")
        pmg.MapData.export_rsc(md, ymap_path)
        ymap_names_exported.append(a_ymap)
        print("YMAP_EXPORT " + json.dumps({
            "file": os.path.basename(ymap_path),
            "entities": len(md.entities),
            "content_flags": int(md.content_flags),
        }), flush=True)

    deps = [ytyp_name] + [d for d in spec.get("vanilla_ytyps", []) if d != ytyp_name]
    dep_xml = "\n".join(f"        <Item>{d}</Item>" for d in deps)
    imap_items = "\n".join(
        f"    <Item>\n      <imapName>{yn}</imapName>\n      <manifestFlags/>\n      <itypDepArray>\n{dep_xml}\n      </itypDepArray>\n    </Item>"
        for yn in ymap_names_exported
    )
    ymf_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<CPackFileMetaData>
  <MapDataGroups/>
  <HDTxdBindingArray/>
  <imapDependencies/>
  <imapDependencies_2>
{imap_items}
  </imapDependencies_2>
  <itypDependencies_2/>
  <Interiors/>
</CPackFileMetaData>
"""
    with open(os.path.join(stream_dir, "_manifest.ymf"), "w", encoding="utf-8", newline="\n") as f:
        f.write(ymf_xml)

    cl_scripts = spec.get("client_scripts") or []
    cl_block = ""
    if cl_scripts:
        cl_items = "\n".join(f'    "{s}",' for s in cl_scripts)
        cl_block = f"\nclient_scripts {{\n{cl_items}\n}}\n"

    fxmanifest = f"""fx_version "cerulean"
game "gta5"
lua54 "yes"

this_is_a_map "yes"

files {{
    "stream/{ytyp_name}.ytyp",
}}

data_file "DLC_ITYP_REQUEST" "stream/{ytyp_name}.ytyp"
{cl_block}"""
    with open(os.path.join(pkg_dir, "fxmanifest.lua"), "w", encoding="utf-8", newline="\n") as f:
        f.write(fxmanifest)
    print("PACKAGE_READY " + json.dumps({"dir": pkg_dir, "stream_files": len(os.listdir(stream_dir))}), flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Export FiveM GEN8 map package from spec + blend props + PBR textures")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--props", required=True)
    ap.add_argument("--textures", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--one", default="")
    ap.add_argument("--ybn", action="store_true")
    ap.add_argument("--ybn-index", type=int, default=0)
    args = ap.parse_args(argv)

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    stream_dir = os.path.join(args.out, "stream")
    os.makedirs(stream_dir, exist_ok=True)

    if args.one:
        export_single_ydr(args.one, stream_dir, spec)
        os._exit(0)

    if args.ybn:
        export_static_world_ybn(spec, args.props, stream_dir, arena_idx=args.ybn_index)
        os._exit(0)

    for fn in os.listdir(stream_dir):
        fp = os.path.join(stream_dir, fn)
        if os.path.isfile(fp):
            os.remove(fp)

    dds_map = encode_shared_pbr_dds(args.textures, spec)
    print("DDS_PREENCODED " + json.dumps({"count": len(dds_map)}), flush=True)

    custom_models = sorted({e["model"] for e in spec["entities"] if not e.get("vanilla")})
    ok, fail = 0, 0
    for model_id in custom_models:
        bpath = os.path.join(args.props, model_id + ".blend")
        if not os.path.isfile(bpath):
            print("FAIL MISSING BLEND: " + bpath, flush=True)
            fail += 1
            continue
        cmd = [
            bpy.app.binary_path, "-b", "-P", os.path.abspath(__file__), "--",
            "--spec", args.spec, "--props", args.props, "--textures", args.textures,
            "--out", args.out, "--one", bpath,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [l for l in proc.stdout.splitlines() if l.startswith("YDR_EXPORT ")]
        if lines:
            print(lines[-1], flush=True)
            ok += 1
        else:
            print(f"FAIL YDR {model_id}: {(proc.stderr or proc.stdout)[-700:]}", flush=True)
            fail += 1

    if fail > 0:
        print(f"MAP_EXPORT_FAIL ok={ok} fail={fail}", flush=True)
        os._exit(1)

    for ai, arena in enumerate(_get_arenas(spec)):
        if not arena.get("ybn_name"):
            continue
        cmd_ybn = [
            bpy.app.binary_path, "-b", "-P", os.path.abspath(__file__), "--",
            "--spec", args.spec, "--props", args.props, "--textures", args.textures,
            "--out", args.out, "--ybn", "--ybn-index", str(ai),
        ]
        proc_ybn = subprocess.run(cmd_ybn, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ybn_lines = [l for l in proc_ybn.stdout.splitlines() if l.startswith("YBN_EXPORT ")]
        if ybn_lines:
            print(ybn_lines[-1], flush=True)
        else:
            print("FAIL YBN: " + (proc_ybn.stderr or proc_ybn.stdout)[-700:], flush=True)
            os._exit(1)

    build_ytd_ytyp_ymap_package(spec, stream_dir, args.out, dds_map)
    print(f"MAP_EXPORT_PASS ydr_ok={ok} fail=0 textures={len(dds_map)}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
