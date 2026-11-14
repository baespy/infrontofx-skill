"""weapon-forge: turn one AI-generated file that holds a weapon set into separate slot models.

blender -b --factory-startup --python-exit-code 1 -P split_ai_set.py -- --src set.fbx --out DIR --mode inspect [--id myset]
blender ... -- --src set.fbx --config set.json --out DIR --mode preview
blender ... -- --src set.fbx --config set.json --out DIR --mode final [--only knife,knuckle] [--samples 32] [--bake 2048]
blender ... -- --src set.fbx --config set.json --out DIR --mode sheet
blender ... -- --src set.fbx --config set.json --out DIR --mode zoom --zoom poolcue,-0.2,0.2,180

inspect lists the loose parts, renders a numbered overview and writes set.draft.json to edit.
preview renders every piece straightened with the hand and muzzle marked; nothing is baked.
final straightens, scales, decimates, bakes the lit high mesh, grades the colour, adds the skeleton.
sheet renders every finished piece from the front and back.
zoom renders the high mesh beside the finished piece for one height range.
A file with a single weapon works the same way with one entry in pieces.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forge_weapon as fw
import import_ai_model as iam

LIGHT = {"long": (0.55, 0.0, 0.83), "plate": (0.0, 0.8, 0.6), "gun": (0.25, 0.0, 0.97)}
WORLD_LOW, WORLD_HIGH = 0.42, 1.9
GRADE = {"black": 0.13, "gamma": 1.3, "red": 0.55}
MARKERS = {
    "long": [((-0.046, 0.002, 0.012), "red"), ((0, 0, 0), "white")],
    "plate": [((-0.046, 0.002, 0.012), "red"), ((0, 0, 0), "white")],
    "gun": [((-0.095, -0.017, -0.061), "red"), ((0.247, 0.0, 0.039), "cyan"), ((0, 0, 0), "white")],
}


def coords(ob):
    n = len(ob.data.vertices)
    flat = np.empty(n * 3)
    ob.data.vertices.foreach_get("co", flat)
    return flat.reshape(-1, 3)


def box(ob):
    pts = coords(ob)
    return pts.min(axis=0), pts.max(axis=0)


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def round_list(values, digits=4):
    return [round(float(v), digits) for v in values]


def load_parts(src):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    iam.import_any(os.path.abspath(src))
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("no mesh found in the file")
    for o in meshes:
        world = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = world
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    active = bpy.context.view_layer.objects.active
    low, high = box(active)
    need_weld = len(active.data.vertices) > len(active.data.polygons)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    if need_weld:
        bpy.ops.mesh.remove_doubles(threshold=max(float((high - low).max()) * 1e-5, 1e-6))
        bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    parts.sort(key=lambda o: len(o.data.polygons), reverse=True)
    return parts


def flat_material(name, color):
    mat = bpy.data.materials.new(name)
    g = fw.Graph(mat)
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    out = g.node("ShaderNodeOutputMaterial")
    g.link(em.outputs[0], out.inputs["Surface"])
    return mat


def lit_cycles(samples):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = False
    s.cycles.use_adaptive_sampling = False
    s.cycles.max_bounces = 3
    s.cycles.diffuse_bounces = 1
    s.cycles.glossy_bounces = 1
    s.cycles.transmission_bounces = 0
    s.cycles.volume_bounces = 0
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"


def set_world(color):
    world = bpy.data.worlds.new("flat")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = color
    bpy.context.scene.world = world


def ortho_camera(name, scale, matrix):
    s = bpy.context.scene
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = scale
    cam = bpy.data.objects.new(name, data)
    s.collection.objects.link(cam)
    cam.matrix_world = matrix
    s.camera = cam
    return cam


def render_to(path, size, samples):
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = size
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = path
    s.cycles.samples = samples
    bpy.ops.render.render(write_still=True)


def label(text, location, size, material):
    curve = bpy.data.curves.new("label", "FONT")
    curve.body = text
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.materials.append(material)
    ob = bpy.data.objects.new("label", curve)
    ob.location = location
    ob.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.scene.collection.objects.link(ob)


def inspect(args):
    parts = load_parts(args.src)
    biggest = len(parts[0].data.polygons)
    majors = [o for o in parts if len(o.data.polygons) >= biggest * 0.01]
    print("@@PARTS", len(parts), "major", len(majors), flush=True)
    pieces = []
    lows, highs = [], []
    for i, o in enumerate(parts):
        lo, hi = box(o)
        lows.append(lo)
        highs.append(hi)
        print("@@PART", i + 1, "faces", len(o.data.polygons), "size_mm", round_list((hi - lo) * 1000, 1), "center", round_list((lo + hi) / 2, 3), flush=True)
        if o in majors:
            ext = hi - lo
            main = [0.0, 0.0, 0.0]
            main[int(np.argmax(ext))] = 1.0
            pieces.append({"name": f"piece{i + 1}", "slot": "", "center": round_list((lo + hi) / 2, 3), "main": main, "sec": [0.0, 0.0, -1.0], "flat": True})
    draft = {"id": args.id or "myset", "pieces": pieces}
    with open(os.path.join(args.out, "set.draft.json"), "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2)

    lit_cycles(args.samples)
    set_world((0.72, 0.72, 0.75, 1.0))
    mins, maxs = np.min(lows, axis=0), np.max(highs, axis=0)
    center = (mins + maxs) / 2
    extent = float((maxs - mins).max()) * 1.08
    yellow = flat_material("m_label", (1.0, 0.85, 0.0, 1.0))
    for i, o in enumerate(majors):
        lo, hi = box(o)
        c = (lo + hi) / 2
        label(str(i + 1), (float(c[0]), float(mins[1]) - extent * 0.05, float(c[2])), extent * 0.05, yellow)
    front = Matrix.Translation((float(center[0]), float(mins[1]) - extent * 3, float(center[2]))) @ Matrix.Rotation(math.radians(90), 4, "X")
    cam = ortho_camera("overview", extent, front)
    render_to(os.path.join(args.out, "overview_front.png"), (1600, 1600), args.samples)
    cam.matrix_world = Matrix.Translation((float(center[0]), float(center[1]), float(maxs[2]) + extent * 3))
    render_to(os.path.join(args.out, "overview_top.png"), (1600, 1600), args.samples)
    print("@@INSPECT done; +X is right and +Z is up in overview_front.png", flush=True)


def read_config(path):
    if not path:
        raise SystemExit("--config is required for this mode; run --mode inspect first")
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    pieces = []
    names = set()
    for raw in cfg["pieces"]:
        for key in ("slot", "main", "sec"):
            if not raw.get(key):
                raise SystemExit(f"piece {raw.get('name', '?')} is missing '{key}'")
        if raw["slot"] not in iam.SLOT_SPEC:
            raise SystemExit(f"unknown slot {raw['slot']}; use one of {sorted(iam.SLOT_SPEC)}")
        spec = iam.SLOT_SPEC[raw["slot"]]
        piece = dict(raw)
        piece.setdefault("name", raw["slot"])
        if piece["name"] in names:
            raise SystemExit(f"duplicate piece name {piece['name']}")
        names.add(piece["name"])
        piece["kind"] = spec["kind"]
        piece["prefix"] = spec["prefix"]
        piece.setdefault("length", spec["length"])
        piece.setdefault("grip", spec["grip"])
        piece.setdefault("tris", spec["tris"])
        piece.setdefault("bake", 1024)
        piece.setdefault("light", LIGHT[spec["kind"]])
        pieces.append(piece)
    if len(pieces) > 1 and any("center" not in p for p in pieces):
        raise SystemExit("every piece needs 'center' when the file holds more than one")
    cfg["pieces"] = pieces
    return cfg


def build_hi(args, cfg, path):
    parts = load_parts(args.src)
    pieces = cfg["pieces"]
    if len(parts) < len(pieces):
        raise SystemExit(f"config lists {len(pieces)} pieces but the file has {len(parts)} loose parts; the weapons may be fused together")
    majors, extras = parts[: len(pieces)], parts[len(pieces) :]
    boxes = {o.name: box(o) for o in majors}
    groups = {o.name: [] for o in majors}
    outside = 0
    for e in extras:
        lo, hi = box(e)
        c = (lo + hi) / 2
        hosts = [(float(np.prod(b[1] - b[0])), name) for name, b in boxes.items() if np.all(c >= b[0] - 1e-4) and np.all(c <= b[1] + 1e-4)]
        if hosts:
            host = min(hosts)[1]
        else:
            host = min(boxes, key=lambda name: float(np.linalg.norm(np.maximum(boxes[name][0] - c, 0) + np.maximum(c - boxes[name][1], 0))))
            outside += len(e.data.polygons)
        groups[host].append(e)
    total_faces = sum(len(o.data.polygons) for o in parts)
    if outside:
        print("@@WARN", outside, "faces lie outside every piece and were merged into the nearest one", flush=True)
    if len(pieces) > 1 and outside > total_faces * 0.01:
        raise SystemExit(f"{outside} of {total_faces} faces fit no piece; run --mode inspect and check that the config lists every weapon")
    span = float((np.max([b[1] for b in boxes.values()], axis=0) - np.min([b[0] for b in boxes.values()], axis=0)).max())
    for o in majors:
        if groups[o.name]:
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            for e in groups[o.name]:
                e.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.join()
    bpy.ops.object.select_all(action="DESELECT")
    print("@@MERGED", len(extras), "small parts into", len(majors), "pieces", flush=True)
    taken = set()
    for o in majors:
        lo, hi = box(o)
        c = (lo + hi) / 2
        piece = min(pieces, key=lambda p: float(np.linalg.norm(c - np.array(p.get("center", (0, 0, 0)), dtype=float))))
        if piece["name"] in taken:
            raise SystemExit(f"two parts matched {piece['name']}; check its center")
        if len(pieces) > 1 and float(np.linalg.norm(c - np.array(piece["center"], dtype=float))) > span * 0.05:
            raise SystemExit(f"the part at {round_list(c, 3)} is far from the center of {piece['name']}; run --mode inspect and update the config")
        taken.add(piece["name"])
        o.name = f"hi_{piece['name']}"
        o.data.name = o.name
        print("@@PIECE", piece["name"], "tris", sum(len(p.vertices) - 2 for p in o.data.polygons), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=False)


def hi_path(args, cfg):
    if args.work:
        path = os.path.abspath(args.work)
    else:
        tag = hashlib.md5(os.path.abspath(args.src).encode("utf-8")).hexdigest()[:8]
        path = os.path.join(tempfile.gettempdir(), f"weapon_forge_{cfg['id']}_{tag}.blend")
    info = os.stat(args.src)
    layout = [(p["name"], p.get("center")) for p in cfg["pieces"]]
    signature = hashlib.md5(json.dumps([os.path.abspath(args.src), info.st_size, info.st_mtime, layout]).encode("utf-8")).hexdigest()
    sig_path = path + ".sig"
    current = ""
    if os.path.exists(path) and os.path.exists(sig_path):
        with open(sig_path, encoding="utf-8") as f:
            current = f.read()
    if current != signature:
        build_hi(args, cfg, path)
        with open(sig_path, "w", encoding="utf-8") as f:
            f.write(signature)
    return path


def principal(pts):
    c = pts - pts.mean(axis=0)
    _, vecs = np.linalg.eigh(c.T @ c / len(c))
    return vecs[:, ::-1].T


def frame(pts, piece):
    hint = unit(piece["main"])
    if piece.get("fixed"):
        main = hint
    else:
        e = principal(pts)[0]
        main = e if e @ hint >= 0 else -e
        if piece.get("range"):
            t = (pts - pts.mean(axis=0)) @ main
            a = t.min() + piece["range"][0] * (t.max() - t.min())
            b = t.min() + piece["range"][1] * (t.max() - t.min())
            e = principal(pts[(t >= a) & (t <= b)])[0]
            main = e if e @ hint >= 0 else -e
    sec_hint = unit(piece["sec"])
    if piece.get("flat"):
        thin = principal(pts)[2]
        thin = unit(thin - (thin @ main) * main)
        sec = np.cross(thin, main)
        if sec @ sec_hint < 0:
            sec = -sec
    else:
        sec = unit(sec_hint - (sec_hint @ main) * main)
    if piece["kind"] == "long":
        x, z = sec, main
        y = np.cross(z, x)
    elif piece["kind"] == "gun":
        x, z = main, sec
        y = np.cross(z, x)
    else:
        z, y = main, -sec
        x = np.cross(y, z)
    return np.array([x, y, z])


def shorten_hanging(ob, factor):
    pts = coords(ob)
    z = pts[:, 2]
    bottom = float(z.min())
    tip = pts[z < bottom + 0.01]
    xc = float(tip[:, 0].min() + tip[:, 0].max()) / 2
    edge = None
    for step in np.arange(bottom, bottom + 0.12, 0.002):
        slab = pts[(z >= step) & (z < step + 0.002)]
        if len(slab) and float(np.ptp(slab[:, 0])) > 0.05:
            edge = float(step)
            break
    if edge is None:
        raise SystemExit("could not find where the hanging part meets the grip")
    mask = (z < edge) & (np.abs(pts[:, 0] - xc) < 0.03)
    pts[mask, 2] = edge - (edge - z[mask]) * factor
    ob.data.vertices.foreach_set("co", pts.ravel())
    ob.data.update()
    print("@@TASSEL edge", round(edge, 4), "moved", int(mask.sum()), "bottom", round(float(pts[:, 2].min()), 4), flush=True)


def shorten_blade_z(ob, z_collar, z_target, shear_x=0.0, x_damp=1.0):
    pts = coords(ob)
    z = pts[:, 2]
    top = float(z.max())
    if top <= z_collar + 1e-4:
        return
    span = top - z_collar
    k = (z_target - z_collar) / span
    collar_slab = pts[np.abs(z - z_collar) < 0.006]
    x_ref = float(collar_slab[:, 0].mean()) if len(collar_slab) else 0.0
    mask = z > z_collar
    dz = z[mask] - z_collar
    blend = np.clip(dz / 0.008, 0.0, 1.0)
    eff_k = 1.0 + (k - 1.0) * blend
    pts[mask, 2] = z_collar + dz * eff_k
    if x_damp != 1.0:
        eff_xd = 1.0 + (float(x_damp) - 1.0) * blend
        pts[mask, 0] = x_ref + (pts[mask, 0] - x_ref) * eff_xd
    if shear_x:
        pts[mask, 0] += dz * float(shear_x) * blend
    ob.data.vertices.foreach_set("co", pts.ravel())
    ob.data.update()
    print("@@BLADE_Z collar", round(z_collar, 4), "old_top", round(top, 4), "new_top", round(float(pts[:, 2].max()), 4), flush=True)


def compress_handle_z(ob, z_collar_bot, factor):
    pts = coords(ob)
    z = pts[:, 2]
    mask = z < z_collar_bot
    if not mask.any():
        return
    dz = z_collar_bot - z[mask]
    blend = np.clip(dz / 0.006, 0.0, 1.0)
    eff_k = 1.0 + (float(factor) - 1.0) * blend
    pts[mask, 2] = z_collar_bot - dz * eff_k
    ob.data.vertices.foreach_set("co", pts.ravel())
    ob.data.update()


def fit(ob, piece):
    me = ob.data
    me.transform(Matrix(frame(coords(ob), piece).tolist()).to_4x4())
    if piece.get("rot"):
        rx, ry, rz = piece["rot"]
        rot_m = (
            Matrix.Rotation(math.radians(float(rz)), 4, "Z")
            @ Matrix.Rotation(math.radians(float(ry)), 4, "Y")
            @ Matrix.Rotation(math.radians(float(rx)), 4, "X")
        )
        me.transform(rot_m)
    lo, hi = box(ob)
    axis = 0 if piece["kind"] == "gun" else 2
    scale = piece["length"] / float(hi[axis] - lo[axis])
    me.transform(Matrix.Scale(scale, 4))
    if piece.get("scale_xyz"):
        sx_m, sy_m, sz_m = piece["scale_xyz"]
        me.transform(
            Matrix.Scale(float(sx_m), 4, (1, 0, 0))
            @ Matrix.Scale(float(sy_m), 4, (0, 1, 0))
            @ Matrix.Scale(float(sz_m), 4, (0, 0, 1))
        )
    pts = coords(ob)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    if piece["kind"] == "long":
        z0 = float(lo[2] + piece["grip"] * (hi[2] - lo[2]))
        slab = pts[np.abs(pts[:, 2] - z0) < 0.03]
        cx, cy = (slab[:, :2].min(axis=0) + slab[:, :2].max(axis=0)) / 2
        shift = (-float(cx), -float(cy), -z0)
    elif piece["kind"] == "plate":
        c = (lo + hi) / 2
        shift = (-float(c[0]), -0.014 - float(c[1]), -float(c[2]))
    else:
        y_span = float(hi[1] - lo[1])
        if y_span > 0.052:
            sy = 0.046 / y_span
            me.transform(Matrix.Scale(sy, 4, (0, 1, 0)))
            pts = coords(ob)
            lo, hi = pts.min(axis=0), pts.max(axis=0)
        front = pts[pts[:, 0] > hi[0] - 0.03]
        barrel_z = float(front[:, 2].min() + front[:, 2].max()) / 2
        barrel_y = float(front[:, 1].min() + front[:, 1].max()) / 2
        grip_slab = pts[np.abs(pts[:, 2] - (barrel_z - 0.10)) < 0.015]
        if len(grip_slab) > 20 and float(np.ptp(grip_slab[:, 0])) < 0.12:
            grip_cx = float(grip_slab[:, 0].min() + grip_slab[:, 0].max()) / 2
            sx = -0.088 - grip_cx
        else:
            sx = 0.215 - float(hi[0])
        shift = (sx, -barrel_y, 0.048 - barrel_z)
    if piece.get("shift"):
        off = piece["shift"]
        shift = (shift[0] + float(off[0]), shift[1] + float(off[1]), shift[2] + float(off[2]))
    me.transform(Matrix.Translation(shift))
    me.update()
    if piece.get("tassel"):
        shorten_hanging(ob, piece["tassel"])
    if piece.get("grip_z_scale"):
        zg, gf = piece["grip_z_scale"]
        compress_handle_z(ob, float(zg), float(gf))
    if piece.get("blade_z"):
        zc, zt = piece["blade_z"]
        shorten_blade_z(
            ob,
            float(zc),
            float(zt),
            float(piece.get("blade_shear_x", 0.0)),
            float(piece.get("blade_x_damp", 1.0)),
        )
    lo, hi = box(ob)
    return {"scale": round(scale, 4), "min": round_list(lo, 3), "max": round_list(hi, 3)}


def layout_render(items, path, samples, yaw=0.0, background=(0.42, 0.43, 0.46, 1.0), size=(2400, 1400), markers=False, window=None):
    s = bpy.context.scene
    set_world(background)
    made = []
    mats = {"red": flat_material("m_red", (1, 0.02, 0.02, 1)), "cyan": flat_material("m_cyan", (0.02, 0.9, 1, 1)), "white": flat_material("m_white", (1, 1, 1, 1))}
    dot_mesh = None
    if markers:
        dot_mesh = bpy.data.meshes.new("marker")
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.008)
        bm.to_mesh(dot_mesh)
        bm.free()
    cursor = 0.0
    gap = 0.07
    heights = []
    for piece, ob in items:
        rot = Matrix.Rotation(math.radians(yaw), 4, "Z")
        low, high = box(ob)
        corners = [rot @ Vector((float(x), float(y), float(z))) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
        xs = [v.x for v in corners]
        heights += [v.z for v in corners]
        inst = bpy.data.objects.new(ob.name + "_v", ob.data)
        s.collection.objects.link(inst)
        place = Matrix.Translation((cursor - min(xs), 0, 0)) @ rot
        inst.matrix_world = place
        made.append(inst)
        if markers:
            todo = list(MARKERS[piece["kind"]])
            if piece["slot"] == "poolcue":
                todo.append(((0.0, 0.0, 0.413), "cyan"))
            for pos, col in todo:
                me = dot_mesh.copy()
                me.materials.append(mats[col])
                dot = bpy.data.objects.new("dot", me)
                s.collection.objects.link(dot)
                dot.matrix_world = place @ Matrix.Translation(pos)
                made.append(dot)
        cursor += (max(xs) - min(xs)) + gap
    total = cursor - gap
    zlo, zhi = window if window else (min(heights), max(heights))
    scale = max(total, (zhi - zlo) * size[0] / size[1]) * 1.05
    cam = ortho_camera("layout", scale, Matrix.Translation((total / 2, -3.0, (zlo + zhi) / 2)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    render_to(path, size, samples)
    for o in made:
        bpy.data.objects.remove(o)
    bpy.data.objects.remove(cam)


def detach(objects):
    for o in objects:
        for coll in list(o.users_collection):
            coll.objects.unlink(o)


def model_name(cfg, piece):
    return f"{piece['prefix']}_{cfg['id']}_{piece['name']}"


def preview(args, cfg, pieces):
    bpy.ops.wm.open_mainfile(filepath=hi_path(args, cfg))
    lit_cycles(args.samples)
    items = []
    for piece in pieces:
        ob = bpy.data.objects[f"hi_{piece['name']}"]
        print("@@FIT", piece["name"], fit(ob, piece), flush=True)
        items.append((piece, ob))
    detach(list(bpy.context.scene.objects))
    layout_render(items, os.path.join(args.out, "preview_front.png"), args.samples, 0.0, markers=True)
    layout_render(items, os.path.join(args.out, "preview_side.png"), args.samples, 90.0, markers=True)


def bake_world(direction):
    world = bpy.data.worlds.new("bake")
    world.use_nodes = True
    nt = world.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = tuple(unit(direction))
    remap = nt.nodes.new("ShaderNodeMapRange")
    remap.inputs["From Min"].default_value = -1.0
    remap.inputs["From Max"].default_value = 1.0
    remap.inputs["To Min"].default_value = WORLD_LOW
    remap.inputs["To Max"].default_value = WORLD_HIGH
    nt.links.new(tc.outputs["Generated"], dot.inputs[0])
    nt.links.new(dot.outputs["Value"], remap.inputs["Value"])
    nt.links.new(remap.outputs["Result"], nt.nodes["Background"].inputs["Strength"])
    nt.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    bpy.context.scene.world = world


def grade(px, opts):
    if opts is False:
        px[3::4] = 1.0
        return px
    black = opts.get("black", GRADE["black"])
    k = opts.get("red", GRADE["red"]) / 0.55
    rgb = px.reshape(-1, 4)[:, :3]
    lifted = np.clip((rgb - black) / (1.0 - black), 0.0, 1.0) ** opts.get("gamma", GRADE["gamma"])
    r, g, b = lifted[:, 0], lifted[:, 1], lifted[:, 2]
    red = np.clip(((r - g) / np.maximum(r, 1e-3) - 0.35) / 0.25, 0.0, 1.0) * np.clip(r / 0.12, 0.0, 1.0)
    red *= np.clip((b - 0.55 * g + 0.02) / 0.04, 0.0, 1.0)
    out = np.empty_like(px)
    out[0::4] = np.clip(r * (1.0 + 0.55 * k * red), 0.0, 1.0)
    out[1::4] = g * (1.0 - 0.3 * k * red)
    out[2::4] = b * (1.0 - 0.1 * k * red)
    out[3::4] = 1.0
    return out


def add_bake_suns(direction):
    s = bpy.context.scene
    suns = []
    specs = [
        ("bake_sun_key", direction, 1.45, (1.0, 0.96, 0.90), 16.0),
        ("bake_sun_rim", (-0.55, 0.62, 0.56), 0.75, (1.0, 0.92, 0.80), 26.0),
        ("bake_sun_fill", (-0.30, -0.75, 0.58), 0.45, (0.90, 0.93, 1.0), 32.0),
    ]
    for name, vec, energy, col, ang_deg in specs:
        ld = bpy.data.lights.new(name, type="SUN")
        ld.energy = energy
        ld.color = col
        ld.angle = math.radians(ang_deg)
        lo = bpy.data.objects.new(name, ld)
        s.collection.objects.link(lo)
        d = Vector(tuple(unit(vec)))
        lo.rotation_mode = "QUATERNION"
        lo.rotation_quaternion = d.to_track_quat("Z", "Y")
        suns.append(lo)
    return suns


def boost_hi_crimson_emission(hi, strength):
    if not strength or strength <= 0:
        return
    for mat in hi.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf or not bsdf.inputs["Base Color"].is_linked:
            continue
        base_sock = bsdf.inputs["Base Color"].links[0].from_socket
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(base_sock, sep.inputs["Color"])
        # Linear space crimson mask: R - 2.2*G > 0.08 and R > 0.16
        mul_g = nt.nodes.new("ShaderNodeMath")
        mul_g.operation = "MULTIPLY"
        mul_g.inputs[1].default_value = 2.2
        nt.links.new(sep.outputs["Green"], mul_g.inputs[0])
        sub_rg = nt.nodes.new("ShaderNodeMath")
        sub_rg.operation = "SUBTRACT"
        nt.links.new(sep.outputs["Red"], sub_rg.inputs[0])
        nt.links.new(mul_g.outputs["Value"], sub_rg.inputs[1])
        rm1 = nt.nodes.new("ShaderNodeMapRange")
        rm1.inputs["From Min"].default_value = 0.06
        rm1.inputs["From Max"].default_value = 0.24
        nt.links.new(sub_rg.outputs["Value"], rm1.inputs["Value"])
        rm2 = nt.nodes.new("ShaderNodeMapRange")
        rm2.inputs["From Min"].default_value = 0.14
        rm2.inputs["From Max"].default_value = 0.36
        nt.links.new(sep.outputs["Red"], rm2.inputs["Value"])
        mask = nt.nodes.new("ShaderNodeMath")
        mask.operation = "MULTIPLY"
        nt.links.new(rm1.outputs["Result"], mask.inputs[0])
        nt.links.new(rm2.outputs["Result"], mask.inputs[1])
        est = nt.nodes.new("ShaderNodeMath")
        est.operation = "MULTIPLY"
        est.inputs[1].default_value = float(strength)
        nt.links.new(mask.outputs["Value"], est.inputs[0])
        em_col_in = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        em_str_in = bsdf.inputs.get("Emission Strength")
        if em_col_in is not None:
            em_col_in.default_value = (1.0, 0.07, 0.11, 1.0)
        if em_str_in is not None:
            nt.links.new(est.outputs["Value"], em_str_in)


def finish(args, cfg, piece):
    bpy.ops.wm.open_mainfile(filepath=hi_path(args, cfg))
    hi = bpy.data.objects[f"hi_{piece['name']}"]
    for o in list(bpy.data.objects):
        if o is not hi:
            bpy.data.objects.remove(o)
    info = fit(hi, piece)
    model = model_name(cfg, piece)
    lo = hi.copy()
    lo.data = hi.data.copy()
    lo.name = model
    s = bpy.context.scene
    s.collection.objects.link(lo)
    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    tris = iam.decimate(lo, piece["tris"])
    bpy.ops.object.shade_smooth()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
    s.tool_settings.use_uv_select_sync = True
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", scale=True, margin_method="SCALED", margin=0.003, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")

    size = args.bake or piece["bake"]
    img = bpy.data.images.new(f"{model}_d", size, size, alpha=True)
    img.generated_color = (0, 0, 0, 1)
    img.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new(f"{model}_bake")
    mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node
    lo.data.materials.clear()
    lo.data.materials.append(mat)

    lit_cycles(args.samples)
    bake_world(piece["light"])
    suns = add_bake_suns(piece["light"]) if cfg.get("studio_lights") else []
    boost_hi_crimson_emission(hi, cfg.get("emit_red", 0.0))
    bk = s.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = 0.005
    bk.max_ray_distance = 0.03
    bk.margin = max(8, size // 128)
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    bpy.ops.object.bake(type="COMBINED", use_clear=True)
    for sun_ob in suns:
        ld = sun_ob.data
        bpy.data.objects.remove(sun_ob)
        bpy.data.lights.remove(ld)

    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    graded = grade(px, cfg.get("grade", {}))
    out_tex = int(piece.get("out_tex", cfg.get("out_tex", size)))
    if out_tex and out_tex < size and size % out_tex == 0:
        f = size // out_tex
        graded_2d = graded.reshape(size, size, 4).reshape(out_tex, f, out_tex, f, 4).mean(axis=(1, 3))
        bpy.data.images.remove(img)
        size = out_tex
        img = bpy.data.images.new(f"{model}_d", size, size, alpha=True)
        img.colorspace_settings.name = "sRGB"
        img.pixels.foreach_set(graded_2d.ravel())
    else:
        img.pixels.foreach_set(graded)
    img.update()
    png = os.path.join(args.out, f"{model}_d.png")
    img.filepath_raw = png
    img.file_format = "PNG"
    img.save()

    final = bpy.data.materials.new(f"{model}_body")
    g = fw.Graph(final)
    tex = g.node("ShaderNodeTexImage")
    tex.image = img
    em = g.node("ShaderNodeEmission")
    outn = g.node("ShaderNodeOutputMaterial")
    g.link(tex.outputs[0], em.inputs["Color"])
    g.link(em.outputs[0], outn.inputs["Surface"])
    lo.data.materials.clear()
    lo.data.materials.append(final)
    lo.data.uv_layers.active.name = "UVMap 0"
    lo.data.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
    col = lo.data.color_attributes["Color 1"]
    col.data.foreach_set("color", [1.0] * (len(col.data) * 4))

    bpy.data.objects.remove(hi)
    lo.data.update()
    bpy.context.view_layer.update()
    s.collection.objects.unlink(lo)
    fw.setup_cycles(args.samples)
    fw.render_sheet([(piece["slot"], lo)], os.path.join(args.out, f"{model}_sheet.png"), args.samples, "#6f7379")
    fw.render_icon(piece["slot"], lo, os.path.join(args.out, f"icon_{piece['name']}.png"), args.samples)
    rig = fw.add_skeleton(lo, model, piece["slot"])
    dds_path = os.path.join(args.out, f"{model}_d.dds")
    fw.save_model(rig, lo, os.path.join(args.out, f"{model}.blend"), slot=piece["slot"], dds_path=dds_path)
    info.update({"name": piece["name"], "slot": piece["slot"], "model": model, "tris": tris, "texture": size})
    if getattr(args, "ydr", "") and piece["name"] == piece["slot"]:
        import export_ydr as eydr
        ydr_dir = args.ydr
        if ydr_dir == "AUTO":
            parent = os.path.dirname(args.out)
            ydr_dir = os.path.join(parent, "stream") if os.path.basename(args.out).lower().startswith("source") else args.out
        else:
            ydr_dir = os.path.abspath(ydr_dir)
        yres = eydr.export_ydr_from_objects(rig, lo, piece["slot"], ydr_dir, make_hi=True, dds_out_dir=args.out)
        info["ydr"] = yres["ydr"]
        info["ytd"] = yres["ytd"]
    print("@@DONE", json.dumps(info), flush=True)
    return info


def load_final(args, cfg, piece):
    path = os.path.join(args.out, f"{model_name(cfg, piece)}.blend")
    if not os.path.exists(path):
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    return next(o for o in dst.objects if o.type == "MESH")


def contact_sheet(args, cfg, pieces):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fw.setup_cycles(args.samples)
    items = [(p, load_final(args, cfg, p)) for p in pieces]
    items = [(p, ob) for p, ob in items if ob is not None]
    if not items:
        raise SystemExit("no finished pieces; run --mode final first")
    dark = (0.16, 0.17, 0.19, 1.0)
    layout_render(items, os.path.join(args.out, f"{cfg['id']}_set_front.png"), args.samples, 0.0, background=dark)
    layout_render(items, os.path.join(args.out, f"{cfg['id']}_set_back.png"), args.samples, 180.0, background=dark)


def zoom(args, cfg):
    name, z0, z1, yaw = args.zoom.split(",")
    piece = next((p for p in cfg["pieces"] if p["name"] == name), None)
    if piece is None:
        raise SystemExit(f"no piece named {name}")
    bpy.ops.wm.open_mainfile(filepath=hi_path(args, cfg))
    lit_cycles(args.samples)
    hi = bpy.data.objects[f"hi_{name}"]
    fit(hi, piece)
    detach(list(bpy.context.scene.objects))
    lo = load_final(args, cfg, piece)
    if lo is None:
        raise SystemExit(f"{name} is not finished; run --mode final first")
    layout_render([(piece, hi), (piece, lo)], os.path.join(args.out, f"zoom_{name}.png"), args.samples, float(yaw), size=(1800, 1000), window=(float(z0), float(z1)))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", required=True, choices=["inspect", "preview", "final", "sheet", "zoom"])
    ap.add_argument("--config", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--bake", type=int, default=0)
    ap.add_argument("--work", default="")
    ap.add_argument("--zoom", default="")
    ap.add_argument("--ydr", nargs="?", const="AUTO", default="", help="compile RSC7 .ydr + .ytd into stream dir")
    args = ap.parse_args(argv)
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)
    if args.mode == "inspect":
        inspect(args)
        return
    cfg = read_config(args.config)
    only = [s for s in args.only.split(",") if s]
    pieces = [
        p for p in cfg["pieces"]
        if ((p["name"] in only) if only else (p.get("name") == p.get("slot") and not p.get("skip", False)))
    ]
    if only and len(pieces) != len(only):
        raise SystemExit(f"--only names not in the config: {sorted(set(only) - {p['name'] for p in pieces})}")
    if args.mode == "preview":
        preview(args, cfg, pieces)
    elif args.mode == "sheet":
        contact_sheet(args, cfg, pieces)
    elif args.mode == "zoom":
        zoom(args, cfg)
    else:
        report_path = os.path.join(args.out, "fit_report.json")
        report = {}
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as f:
                report = json.load(f)
        for piece in pieces:
            report[piece["name"]] = finish(args, cfg, piece)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
