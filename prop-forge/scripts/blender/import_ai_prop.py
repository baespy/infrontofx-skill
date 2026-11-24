"""prop-forge: turn an AI generated mesh (glb, gltf, fbx, obj from Tripo / Meshy / Rodin / Hunyuan3D) into a prop .blend
that passes validate_prop.py and exports with export_prop.py.

blender -b --factory-startup -P import_ai_prop.py -- --src model.glb --id 1nfx_brand_atm --out work\\build
        [--height 1.9 | --width 1.2] [--tris 6000] [--bake 1024] [--yaw 0] [--rot 0,0,0] [--strip-islands 0.04]
        [--weld 0.0004] [--ao 0.45] [--glossy] [--colliders 3] [--lod-dist 100] [--samples 16] [--no-render]

Steps: import, join, strip floating islands, rotate, scale to the target size, centre on X/Y with the lowest point at
z = 0, weld + decimate to the tris budget, bake the source colour (plus optional AO) into one fresh atlas, fill the
unused atlas area, build stacked collision boxes, write prop_forge metadata, render a preview and save <id>.blend.
"""

import argparse
from collections import deque
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
import numpy as np


def import_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise SystemExit("unsupported format {}; use glb, gltf, fbx or obj".format(ext))


def join_meshes():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh found in the file")
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    world = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    return ob


def strip_floating_islands(ob, min_ratio):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.verts.ensure_lookup_table()
    visited = set()
    islands = []
    for v in bm.verts:
        if v.index in visited:
            continue
        verts = []
        faces = set()
        queue = deque([v])
        visited.add(v.index)
        while queue:
            cur = queue.popleft()
            verts.append(cur)
            for f in cur.link_faces:
                faces.add(f.index)
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other.index not in visited:
                    visited.add(other.index)
                    queue.append(other)
        xs = [p.co.x for p in verts]
        ys = [p.co.y for p in verts]
        zs = [p.co.z for p in verts]
        diagonal = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
        islands.append((diagonal if faces else 0.0, verts))
    removed = 0
    if len(islands) > 1:
        threshold = max(d for d, _ in islands) * min_ratio
        doomed = []
        for d, verts in islands:
            if d < threshold:
                doomed.extend(verts)
                removed += 1
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()
    return removed, len(islands) - removed


def coords(ob):
    n = len(ob.data.vertices)
    flat = np.empty(n * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", flat)
    return flat.reshape((n, 3))


def bounds(ob):
    pts = coords(ob)
    return Vector(pts.min(axis=0)), Vector(pts.max(axis=0))


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def place(ob, height, width):
    lo, hi = bounds(ob)
    ext = hi - lo
    if width > 0:
        scale = width / max(ext.x, 1e-6)
    else:
        scale = height / max(ext.z, 1e-6)
    ob.data.transform(Matrix.Scale(scale, 4))
    lo, hi = bounds(ob)
    ob.data.transform(Matrix.Translation(Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))))
    ob.data.update()
    return scale


def weld_and_decimate(ob, target, weld):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    if weld > 0:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    tris = tri_count(ob)
    if tris > target:
        mod = ob.modifiers.new("decimate", "DECIMATE")
        mod.ratio = target / tris
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    bpy.ops.object.shade_smooth()
    return tri_count(ob)


def flatten_metal(ob):
    for mat in ob.data.materials:
        if not mat or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname != "ShaderNodeBsdfPrincipled":
                continue
            sock = node.inputs.get("Metallic")
            if sock is None:
                continue
            for link in list(sock.links):
                mat.node_tree.links.remove(link)
            sock.default_value = 0.0


def bake_pass(hi, lo, image, kind, extent, samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    bake = scene.render.bake
    bake.margin = 16
    mat = lo.data.materials[0]
    node = mat.node_tree.nodes["bake_target"]
    node.image = image
    mat.node_tree.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    if kind == "COLOR":
        bake.use_selected_to_active = True
        bake.cage_extrusion = 0.02 * extent
        bake.max_ray_distance = 0.06 * extent
        hi.select_set(True)
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_clear=True)
    else:
        bake.use_selected_to_active = False
        bpy.ops.object.bake(type="AO", use_clear=True)


def pixels_of(image):
    w, h = image.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(buf)
    return buf.reshape((h, w, 4))


def bake_atlas(hi, lo, prop_id, size, samples, ao_strength, out_dir):
    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    while lo.data.uv_layers:
        lo.data.uv_layers.remove(lo.data.uv_layers[0])
    lo.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.012)
    bpy.ops.object.mode_set(mode="OBJECT")
    work = bpy.data.materials.new(prop_id + "_bakework")
    work.use_nodes = True
    target = work.node_tree.nodes.new("ShaderNodeTexImage")
    target.name = "bake_target"
    lo.data.materials.clear()
    lo.data.materials.append(work)
    lo_b, hi_b = bounds(lo)
    extent = max(hi_b - lo_b)
    color = bpy.data.images.new(prop_id + "_atlas", size, size, alpha=True)
    color.generated_color = (0, 0, 0, 0)
    flatten_metal(hi)
    bake_pass(hi, lo, color, "COLOR", extent, samples)
    px = pixels_of(color)
    if ao_strength > 0:
        hi.hide_render = True
        ao = bpy.data.images.new(prop_id + "_ao", size, size, alpha=True)
        ao.generated_color = (1, 1, 1, 0)
        bake_pass(hi, lo, ao, "AO", extent, max(samples, 32))
        shade = pixels_of(ao)[:, :, 0:1]
        px[:, :, 0:3] *= (1.0 - ao_strength) + ao_strength * shade
        bpy.data.images.remove(ao)
    covered = px[:, :, 3] > 0.5
    coverage = float(covered.mean())
    if covered.any():
        fill = px[covered][:, 0:3].mean(axis=0)
        px[~covered, 0:3] = fill
    px[:, :, 3] = 1.0
    color.pixels.foreach_set(px.reshape(-1))
    png = os.path.join(out_dir, prop_id + "_atlas.png")
    color.filepath_raw = png
    color.file_format = "PNG"
    color.save()
    color.filepath = png
    lo.data.materials.clear()
    bpy.data.materials.remove(work)
    return color, coverage


def final_material(lo, prop_id, image, glossy):
    mat = bpy.data.materials.new(prop_id + "_diffuse")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next(n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.32 if glossy else 0.6
    mat["prop_forge_shader"] = "default_spec.sps" if glossy else "default.sps"
    if glossy:
        mat["prop_forge_spec_int"] = 0.48
        mat["prop_forge_spec_falloff"] = 48.0
        mat["prop_forge_spec_fresnel"] = 0.88
    lo.data.materials.append(mat)
    for poly in lo.data.polygons:
        poly.material_index = 0
    return mat


def make_colliders(lo, prop_id, slabs):
    if slabs <= 0:
        return 0
    pts = coords(lo)
    z_lo, z_hi = float(pts[:, 2].min()), float(pts[:, 2].max())
    coll = bpy.data.collections.new(prop_id + "_collision")
    bpy.context.scene.collection.children.link(coll)
    made = 0
    step = (z_hi - z_lo) / slabs
    for i in range(slabs):
        a, b = z_lo + step * i, z_lo + step * (i + 1)
        inside = pts[(pts[:, 2] >= a - 1e-6) & (pts[:, 2] <= b + 1e-6)]
        if len(inside) < 3:
            continue
        lo_c, hi_c = inside.min(axis=0), inside.max(axis=0)
        size = Vector((max(hi_c[0] - lo_c[0], 0.04), max(hi_c[1] - lo_c[1], 0.04), max(b - a, 0.04)))
        center = Vector(((lo_c[0] + hi_c[0]) / 2, (lo_c[1] + hi_c[1]) / 2, (a + b) / 2))
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=bm.verts)
        bmesh.ops.translate(bm, vec=center, verts=bm.verts)
        me = bpy.data.meshes.new("{}_col_{}".format(prop_id, made))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        coll.objects.link(ob)
        ob.display_type = "WIRE"
        ob.hide_render = True
        ob["prop_forge_collision"] = "box"
        made += 1
    return made


def render_preview(lo, path, samples):
    scene = bpy.context.scene
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = name
            break
        except TypeError:
            continue
    lo_b, hi_b = bounds(lo)
    centre = (lo_b + hi_b) / 2
    radius = max((hi_b - lo_b).length / 2, 0.1)
    cam_data = bpy.data.cameras.new("preview_cam")
    cam_data.lens = 60
    cam = bpy.data.objects.new("preview_cam", cam_data)
    scene.collection.objects.link(cam)
    direction = Vector((0.62, -1.0, 0.42)).normalized()
    cam.location = centre + direction * radius * 4.1
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    made = [cam]
    for name, energy, angle in (("preview_key", 3.2, (0.9, 0.0, 0.6)), ("preview_fill", 1.1, (1.1, 0.0, -2.2))):
        data = bpy.data.lights.new(name, "SUN")
        data.energy = energy
        light = bpy.data.objects.new(name, data)
        light.rotation_euler = angle
        scene.collection.objects.link(light)
        made.append(light)
    world = bpy.data.worlds.new("preview_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.36, 0.38, 0.42, 1.0)
    scene.world = world
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples
    bpy.ops.render.render(write_still=True)
    for ob in made:
        data = ob.data
        bpy.data.objects.remove(ob)
        if isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
        else:
            bpy.data.lights.remove(data)
    scene.world = None
    bpy.data.worlds.remove(world)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--height", type=float, default=1.6)
    ap.add_argument("--width", type=float, default=0.0)
    ap.add_argument("--tris", type=int, default=6000)
    ap.add_argument("--bake", type=int, default=1024)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--rot", default="0,0,0")
    ap.add_argument("--strip-islands", type=float, default=0.04)
    ap.add_argument("--weld", type=float, default=0.0004)
    ap.add_argument("--ao", type=float, default=0.45)
    ap.add_argument("--glossy", action="store_true")
    ap.add_argument("--colliders", type=int, default=3)
    ap.add_argument("--lod-dist", type=float, default=100.0)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args(argv)

    prop_id = args.id.lower()
    if not all(c.isdigit() or c == "_" or "a" <= c <= "z" for c in prop_id) or not 3 <= len(prop_id) <= 60:
        raise SystemExit("--id must be 3-60 chars of a-z 0-9 _")
    if args.bake & (args.bake - 1) or not 256 <= args.bake <= 2048:
        raise SystemExit("--bake must be a power of two between 256 and 2048")
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    import_any(os.path.abspath(args.src))
    hi = join_meshes()
    hi.name = "ai_source"
    removed, kept = strip_floating_islands(hi, args.strip_islands) if args.strip_islands > 0 else (0, 0)
    src_tris = tri_count(hi)
    rx, ry, rz = (float(v) for v in args.rot.split(","))
    turn = Matrix.Rotation(math.radians(rz + args.yaw), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X")
    hi.data.transform(turn)
    scale = place(hi, args.height, args.width)

    lo = hi.copy()
    lo.data = hi.data.copy()
    lo.name = prop_id
    lo.data.name = prop_id
    bpy.context.scene.collection.objects.link(lo)
    tris = weld_and_decimate(lo, args.tris, args.weld)
    lo_b, hi_b = bounds(lo)
    lo.data.transform(Matrix.Translation(Vector((-(lo_b.x + hi_b.x) / 2, -(lo_b.y + hi_b.y) / 2, -lo_b.z))))
    lo.data.update()

    image, coverage = bake_atlas(hi, lo, prop_id, args.bake, max(args.samples, 8), max(0.0, min(args.ao, 1.0)), out_dir)
    hi_data = hi.data
    hi_mats = [m for m in hi_data.materials if m]
    bpy.data.objects.remove(hi)
    bpy.data.meshes.remove(hi_data)
    for m in hi_mats:
        if m.users == 0:
            bpy.data.materials.remove(m)
    final_material(lo, prop_id, image, args.glossy)
    ncol = make_colliders(lo, prop_id, args.colliders)

    lo_b, hi_b = bounds(lo)
    size = hi_b - lo_b
    meta = {
        "id": prop_id,
        "archetype": "ai_import",
        "source": os.path.basename(args.src),
        "size": [round(size.x, 3), round(size.y, 3), round(size.z, 3)],
        "tris": tris,
        "budget": max(args.tris, tris),
        "source_tris": src_tris,
        "materials": [m.name for m in lo.data.materials],
        "colliders": ncol,
        "atlas": args.bake,
        "atlas_coverage": round(coverage, 3),
        "lod_dist": args.lod_dist,
        "shader": "default_spec.sps" if args.glossy else "default.sps",
    }
    lo["prop_forge"] = json.dumps(meta)

    preview = os.path.join(out_dir, prop_id + "_preview.png")
    if not args.no_render:
        render_preview(lo, preview, max(args.samples, 16))
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    blend = os.path.join(out_dir, prop_id + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    with open(os.path.join(out_dir, prop_id + "_import.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("@@AI_PROP islands_removed={} islands_kept={} scale={:.4f}".format(removed, kept, scale))
    print("@@AI_PROP " + json.dumps(meta))
    print("RESULT ok=1 blend={}".format(blend))
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
