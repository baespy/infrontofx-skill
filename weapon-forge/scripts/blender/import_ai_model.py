"""weapon-forge: turn an externally generated mesh (glb, gltf, fbx, obj) into a FiveM weapon slot model.

blender -b --factory-startup -P import_ai_model.py -- --src model.glb --slot bottle --id onikage --out DIR
        [--length 0.8] [--tris 14000] [--bake 1024] [--rot 0,0,0] [--flip] [--grip 0.33] [--samples 24]
        [--pca] [--strip-islands 0.03] [--bake-mode lit|color] [--ydr [STREAM_DIR]]

Steps: import, join, strip floating islands, align axes (PCA or AABB) to the slot convention, scale to the
slot length, place the grip at the origin, decimate, bake studio-lit PBR + AO (or raw diffuse colour) from
the high mesh into a fresh UV atlas, apply bloom + DXT5 .dds export, add the skeleton + Sollumz collision,
save .blend + preview sheet, and optionally compile RSC7 .ydr + .ytd directly.
"""

import argparse
from collections import deque
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_ydr as eydr
import forge_weapon as fw

SLOT_SPEC = {
    "poolcue": {"prefix": "w_me", "length": 0.95, "grip": 0.16, "tris": 16000, "kind": "long"},
    "bottle": {"prefix": "w_me", "length": 0.37, "grip": 0.24, "tris": 16000, "kind": "long"},
    "machete": {"prefix": "w_me", "length": 0.505, "grip": 0.09, "tris": 16000, "kind": "long"},
    "knife": {"prefix": "w_me", "length": 0.36, "grip": 0.14, "tris": 12000, "kind": "long"},
    "bat": {"prefix": "w_me", "length": 0.81, "grip": 0.17, "tris": 16000, "kind": "long"},
    "knuckle": {"prefix": "w_me", "length": 0.15, "grip": 0.5, "tris": 12000, "kind": "plate"},
    "revolver": {"prefix": "w_pi", "length": 0.36, "grip": 0.5, "tris": 14000, "kind": "gun"},
}


def import_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise SystemExit(f"unsupported format {ext}; use glb, gltf, fbx or obj")


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
    ob.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    return ob


def strip_floating_islands(ob, min_ratio=0.02):
    """Remove disconnected mesh islands smaller than min_ratio of the largest island's face count."""
    if min_ratio <= 0.0:
        return 0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    visited = set()
    islands = []
    for v in bm.verts:
        if v.index in visited:
            continue
        comp_verts = []
        comp_faces = set()
        q = deque([v])
        visited.add(v.index)
        while q:
            curr = q.popleft()
            comp_verts.append(curr)
            for f in curr.link_faces:
                comp_faces.add(f.index)
            for e in curr.link_edges:
                other = e.other_vert(curr)
                if other.index not in visited:
                    visited.add(other.index)
                    q.append(other)
        islands.append((len(comp_faces), comp_verts))
    if len(islands) <= 1:
        bm.free()
        return 0
    max_faces = max(fc for fc, _ in islands)
    threshold = max(1, int(max_faces * min_ratio))
    removed_islands = 0
    to_delete = []
    for fc, verts in islands:
        if fc < threshold:
            to_delete.extend(verts)
            removed_islands += 1
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
        bm.to_mesh(ob.data)
        ob.data.update()
    bm.free()
    if removed_islands:
        print(f"@@ISLANDS stripped={removed_islands} kept={len(islands) - removed_islands} threshold_faces={threshold}")
    return removed_islands


def bounds(ob):
    n = len(ob.data.vertices)
    flat = [0.0] * (n * 3)
    ob.data.vertices.foreach_get("co", flat)
    xs, ys, zs = flat[0::3], flat[1::3], flat[2::3]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def apply_matrix(ob, m):
    ob.data.transform(m)
    ob.data.update()


def align_pca(ob, kind):
    """Align a diagonally oriented mesh using Principal Component Analysis (eigenvectors of vertex covariance)."""
    n = len(ob.data.vertices)
    flat = np.empty(n * 3, dtype=np.float64)
    ob.data.vertices.foreach_get("co", flat)
    pts = flat.reshape((n, 3))
    mean = pts.mean(axis=0)
    centered = pts - mean
    cov = np.cov(centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # eigh returns eigenvalues in ascending order: index 0 = smallest variance, 1 = mid, 2 = largest
    v_small = eigvecs[:, 0]
    v_mid = eigvecs[:, 1]
    v_large = eigvecs[:, 2]

    if kind == "long":
        rows = np.vstack([v_mid, v_small, v_large])
    elif kind == "plate":
        rows = np.vstack([v_small, v_mid, v_large])
    else:
        rows = np.vstack([v_large, v_small, v_mid])

    if np.linalg.det(rows) < 0:
        rows[2, :] = -rows[2, :]

    m4 = Matrix.Identity(4)
    for r in range(3):
        for c in range(3):
            m4[r][c] = float(rows[r, c])
    apply_matrix(ob, m4 @ Matrix.Translation(Vector((-float(mean[0]), -float(mean[1]), -float(mean[2])))))
    print("@@PCA eigenvalues", [round(float(x), 6) for x in eigvals])


def permute_axes(ob, kind):
    lo, hi = bounds(ob)
    ext = [hi[i] - lo[i] for i in range(3)]
    order = sorted(range(3), key=lambda i: ext[i])
    small, mid, large = order
    if kind == "long":
        target = {large: 2, mid: 0, small: 1}
    elif kind == "plate":
        target = {small: 0, mid: 1, large: 2}
    else:
        target = {large: 0, small: 1, mid: 2}
    rows = [[0.0] * 3 for _ in range(3)]
    for src, dst in target.items():
        rows[dst][src] = 1.0
    m3 = Matrix(rows)
    if m3.determinant() < 0:
        for j in range(3):
            m3[2][j] = -m3[2][j]
    apply_matrix(ob, m3.to_4x4())
    print("@@AXES extents before", [round(e, 3) for e in ext], "order small,mid,large", order)


def place(ob, spec, length, grip):
    lo, hi = bounds(ob)
    ext = [hi[i] - lo[i] for i in range(3)]
    long_i = {"long": 2, "plate": 2, "gun": 0}[spec["kind"]]
    scale = length / max(ext[long_i], 1e-6)
    apply_matrix(ob, Matrix.Scale(scale, 4))
    lo, hi = bounds(ob)
    c = (lo + hi) / 2
    if spec["kind"] == "long":
        z_ref = lo.z + grip * (hi.z - lo.z)
        shift = Vector((-c.x, -c.y, -z_ref))
    elif spec["kind"] == "plate":
        shift = Vector((0.022 - c.x, -0.016 - c.y, -c.z))
    else:
        shift = Vector((0.245 - hi.x, -c.y, 0.07 - hi.z))
    apply_matrix(ob, Matrix.Translation(shift))
    return scale


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(ob, target):
    tris = tri_count(ob)
    if tris <= target:
        return tris
    mod = ob.modifiers.new("decimate", "DECIMATE")
    mod.ratio = target / tris
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return tri_count(ob)


def upgrade_pbr_to_studio_emit(hi):
    """Wrap each material on hi so its Base Color, Metallic, Normal, AO, and Bevel curvature bake as rich studio-lit Emission."""
    for mat in hi.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        bsdf = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        out_node = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if not bsdf or not out_node:
            continue

        # Capture Base Color socket or value
        base_sock = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
        if base_sock is None:
            rgb_n = nodes.new("ShaderNodeRGB")
            rgb_n.outputs[0].default_value = tuple(bsdf.inputs["Base Color"].default_value)
            base_sock = rgb_n.outputs[0]

        # Capture Normal socket or Bevel normal
        norm_sock = bsdf.inputs["Normal"].links[0].from_socket if bsdf.inputs["Normal"].is_linked else None
        bevel = nodes.new("ShaderNodeBevel")
        bevel.samples = 4
        bevel.inputs["Radius"].default_value = 0.0018
        if norm_sock is not None:
            links.new(norm_sock, bevel.inputs["Normal"])

        geo = nodes.new("ShaderNodeNewGeometry")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(bevel.outputs[0], sep.inputs[0])

        def math_node(op, a, b=None):
            m = nodes.new("ShaderNodeMath")
            m.operation = op
            if isinstance(a, (int, float)):
                m.inputs[0].default_value = a
            else:
                links.new(a, m.inputs[0])
            if b is not None:
                if isinstance(b, (int, float)):
                    m.inputs[1].default_value = b
                else:
                    links.new(b, m.inputs[1])
            return m.outputs[0]

        # 3-Point studio lighting + grazing rim + AO + curvature edge highlight
        key_l = math_node("ADD", math_node("MULTIPLY", sep.outputs[2], 0.62), math_node("MULTIPLY", sep.outputs[0], -0.35))
        key_l = math_node("ADD", key_l, math_node("MULTIPLY", sep.outputs[1], -0.45))
        rim_l = math_node("POWER", math_node("MAXIMUM", math_node("SUBTRACT", 1.0, math_node("ABSOLUTE", sep.outputs[1])), 0.0), 3.0)
        lit = math_node("ADD", math_node("MULTIPLY", key_l, 0.45), 0.82)
        lit = math_node("ADD", lit, math_node("MULTIPLY", rim_l, 0.25))

        dotn = nodes.new("ShaderNodeVectorMath")
        dotn.operation = "DOT_PRODUCT"
        links.new(bevel.outputs[0], dotn.inputs[0])
        links.new(geo.outputs["Normal"], dotn.inputs[1])
        edge = math_node("MINIMUM", math_node("MULTIPLY", math_node("SUBTRACT", 1.0, dotn.outputs["Value"]), 3.0), 1.0)

        ao = nodes.new("ShaderNodeAmbientOcclusion")
        ao.samples = 6
        ao.inputs["Distance"].default_value = 0.012
        if norm_sock is not None:
            links.new(norm_sock, ao.inputs["Normal"])
        ao_fac = math_node("ADD", math_node("MULTIPLY", ao.outputs["AO"], 0.55), 0.45)
        shade = math_node("MULTIPLY", lit, ao_fac)

        # Mix edge highlight + studio shade
        edge_mix = nodes.new("ShaderNodeMix")
        edge_mix.data_type = "RGBA"
        edge_mix.blend_type = "MIX"
        links.new(math_node("MULTIPLY", edge, 0.28), edge_mix.inputs[0])
        links.new(base_sock, edge_mix.inputs[6])
        edge_mix.inputs[7].default_value = (0.95, 0.96, 1.0, 1.0)

        mul_mix = nodes.new("ShaderNodeMix")
        mul_mix.data_type = "RGBA"
        mul_mix.blend_type = "MULTIPLY"
        mul_mix.inputs[0].default_value = 1.0
        links.new(edge_mix.outputs[2], mul_mix.inputs[6])
        links.new(shade, mul_mix.inputs[7])

        # Add any existing emission from the AI material
        final_col = mul_mix.outputs[2]
        if "Emission Color" in bsdf.inputs and bsdf.inputs["Emission Color"].is_linked:
            em_sock = bsdf.inputs["Emission Color"].links[0].from_socket
            add_em = nodes.new("ShaderNodeMix")
            add_em.data_type = "RGBA"
            add_em.blend_type = "ADD"
            add_em.inputs[0].default_value = 1.0
            links.new(final_col, add_em.inputs[6])
            links.new(em_sock, add_em.inputs[7])
            final_col = add_em.outputs[2]

        em_out = nodes.new("ShaderNodeEmission")
        links.new(final_col, em_out.inputs["Color"])
        links.new(em_out.outputs[0], out_node.inputs["Surface"])


def bake_color(hi, lo, size, samples, bake_mode="lit"):
    scene = bpy.context.scene
    if bake_mode == "lit":
        upgrade_pbr_to_studio_emit(hi)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = lo
    lo.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{lo.name}_d", size, size, alpha=True)
    img.generated_color = (0, 0, 0, 1)
    mat = bpy.data.materials.new(f"{lo.name}_bake")
    mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node
    lo.data.materials.clear()
    lo.data.materials.append(mat)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = 0.004
    scene.render.bake.max_ray_distance = 0.02
    scene.render.bake.margin = 8
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    if bake_mode == "lit":
        bpy.ops.object.bake(type="EMIT", use_clear=True)
    else:
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_clear=True)
    return img


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--slot", required=True, choices=sorted(SLOT_SPEC))
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--length", type=float, default=0.0)
    ap.add_argument("--grip", type=float, default=-1.0)
    ap.add_argument("--tris", type=int, default=0)
    ap.add_argument("--bake", type=int, default=1024)
    ap.add_argument("--bake-mode", choices=("lit", "color"), default="lit", help="lit: bake studio lighting + AO + bevel + normal into emission; color: raw diffuse color only")
    ap.add_argument("--pca", action="store_true", help="align diagonally oriented AI meshes using PCA covariance eigenvectors")
    ap.add_argument("--strip-islands", type=float, default=0.02, help="remove disconnected mesh islands smaller than this fraction of the main mesh (0 to disable)")
    ap.add_argument("--ydr", nargs="?", const="AUTO", default="", help="compile RSC7 .ydr + .ytd into stream dir (or pass explicit dir)")
    ap.add_argument("--rot", default="0,0,0", help="extra rotation in degrees x,y,z after axis alignment")
    ap.add_argument("--flip", action="store_true", help="turn the model end for end")
    ap.add_argument("--samples", type=int, default=24)
    args = ap.parse_args(argv)

    spec = SLOT_SPEC[args.slot]
    length = args.length or spec["length"]
    grip = spec["grip"] if args.grip < 0 else args.grip
    target = args.tris or spec["tris"]
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    ydr_dir = ""
    if args.ydr:
        if args.ydr == "AUTO":
            parent = os.path.dirname(out_dir)
            ydr_dir = os.path.join(parent, "stream") if os.path.basename(out_dir).lower() == "source" else out_dir
        else:
            ydr_dir = os.path.abspath(args.ydr)
        os.makedirs(ydr_dir, exist_ok=True)

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    import_any(os.path.abspath(args.src))
    hi = join_meshes()
    hi.name = "hi"
    if args.strip_islands > 0:
        strip_floating_islands(hi, args.strip_islands)
    print("@@IMPORT tris", tri_count(hi), "materials", [m.name for m in hi.data.materials if m])

    if args.pca:
        align_pca(hi, spec["kind"])
    else:
        permute_axes(hi, spec["kind"])
    rx, ry, rz = (float(v) for v in args.rot.split(","))
    extra = Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X")
    if args.flip:
        extra = Matrix.Rotation(math.pi, 4, "X" if spec["kind"] != "gun" else "Z") @ extra
    apply_matrix(hi, extra)
    scale = place(hi, spec, length, grip)

    model = f"{spec['prefix']}_{args.id}_{args.slot}"
    lo = hi.copy()
    lo.data = hi.data.copy()
    lo.name = model
    bpy.context.scene.collection.objects.link(lo)
    final_tris = decimate(lo, target)
    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    bpy.ops.object.shade_smooth()
    img = bake_color(hi, lo, args.bake, max(args.samples, 16), bake_mode=args.bake_mode)
    png = os.path.join(out_dir, f"{model}_d.png")
    img.filepath_raw = png
    img.file_format = "PNG"
    img.save()
    dds_path = os.path.join(out_dir, f"{model}_d.dds")
    eydr.image_to_dxt5(img, dds_path=dds_path, bloom=True)
    img.filepath = png

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

    lo_lo, lo_hi = bounds(lo)
    bpy.data.objects.remove(hi)
    bpy.context.scene.collection.objects.unlink(lo)
    fw.setup_cycles(args.samples)
    sheet = os.path.join(out_dir, f"{model}_sheet.png")
    fw.render_sheet([(args.slot, lo)], sheet, args.samples, "#6f7379")
    fw.render_icon(args.slot, lo, os.path.join(out_dir, f"icon_{args.slot}.png"), args.samples)
    rig = fw.add_skeleton(lo, model, args.slot)
    blend = os.path.join(out_dir, f"{model}.blend")
    fw.save_model(rig, lo, blend, slot=args.slot, dds_path=dds_path)
    if ydr_dir:
        res = eydr.export_ydr_from_objects(rig, lo, args.slot, ydr_dir, make_hi=True, dds_out_dir=out_dir)
        print(f"@@AI_YDR {args.slot} ydr={res['ydr']} ({res['size_kb']} KB)")
    print("@@AI", args.slot, f"tris={final_tris}", f"scale={scale:.4f}", "bbox", [round(v, 3) for v in lo_lo], [round(v, 3) for v in lo_hi])
    print("@@AI done", blend)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
