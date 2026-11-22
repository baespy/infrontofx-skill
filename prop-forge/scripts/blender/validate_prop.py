"""prop-forge: check a prop .blend against the export contract before Sollumz / CodeWalker.

Headless:  blender -b --factory-startup -P validate_prop.py -- --blend <file.blend | folder> [--budget 12000]
Live MCP:  import runpy; check = runpy.run_path(r"<skill>/scripts/blender/validate_prop.py")["validate_scene"]
           result = {"report": check("1nfx_goo_atm")}

Prints one line per check (OK / WARN / FAIL) and ends with RESULT fail=<n> warn=<n>.
"""

import argparse
import json
import math
import os
import re
import sys

import bpy

NAME_RULE = re.compile(r"^[a-z0-9_]{3,60}$")


def tris_of(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def world_bbox(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    return lo, hi


def validate_scene(prop_id=None, budget=None):
    lines = []

    def out(level, text):
        lines.append("{} {}".format(level, text))

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and "prop_forge_collision" not in o and "_col_" not in o.name]
    if prop_id is None:
        tagged = [o for o in meshes if "prop_forge" in o]
        prop_id = tagged[0].name if tagged else (meshes[0].name if meshes else "")
    root = bpy.data.objects.get(prop_id)
    if root is None or root.type != "MESH":
        out("FAIL", "no mesh object named {}".format(prop_id))
        return finish(lines)
    meta = {}
    if "prop_forge" in root:
        try:
            meta = json.loads(root["prop_forge"])
        except ValueError:
            out("WARN", "prop_forge metadata is not valid JSON")
    out("OK" if NAME_RULE.match(root.name) else "FAIL", "model name {} (lowercase a-z 0-9 _ , 3-60 chars)".format(root.name))
    extra = [o.name for o in meshes if o is not root]
    out("OK" if not extra else "WARN", "one drawable mesh" + ("" if not extra else ", extra meshes: " + ", ".join(extra[:6])))
    loc_ok = root.location.length < 1e-4
    rot_ok = max(abs(a) for a in root.rotation_euler) < 1e-4
    scale_ok = max(abs(s - 1.0) for s in root.scale) < 1e-4
    out("OK" if loc_ok and rot_ok and scale_ok else "FAIL", "transforms applied (location 0, rotation 0, scale 1)")
    if root.parent is not None:
        out("FAIL", "root has a parent ({}); export the prop as a top-level object".format(root.parent.name))
    me = root.data
    if not me.vertices:
        out("FAIL", "mesh is empty")
        return finish(lines)
    lo, hi = world_bbox(root)
    size = [hi[i] - lo[i] for i in range(3)]
    out("OK" if abs(lo[2]) <= 0.02 else "FAIL", "origin at floor: lowest point z={:.3f}".format(lo[2]))
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    off = math.hypot(cx, cy)
    out("OK" if off <= max(0.05, 0.08 * max(size[0], size[1])) else "WARN", "origin centred in X/Y (offset {:.3f} m)".format(off))
    out("OK" if 0.05 <= max(size) <= 6.0 else "WARN", "size {:.2f} x {:.2f} x {:.2f} m (metres, Z up)".format(*size))
    tris = tris_of(me)
    limit = budget or meta.get("budget") or 12000
    out("OK" if tris <= limit else "FAIL", "tris {} / budget {}".format(tris, limit))
    nan = sum(1 for v in me.vertices if any(math.isnan(c) for c in v.co))
    out("OK" if nan == 0 else "FAIL", "no NaN vertices ({})".format(nan))
    me.calc_loop_triangles()
    degenerate = sum(1 for t in me.loop_triangles if t.area < 1e-9)
    out("OK" if degenerate == 0 else "WARN", "degenerate triangles: {}".format(degenerate))
    loose = len(me.vertices) - len({v for p in me.polygons for v in p.vertices})
    out("OK" if loose == 0 else "WARN", "loose vertices: {}".format(loose))
    out("OK" if me.uv_layers else "FAIL", "UV map present")
    mats = [m for m in me.materials if m]
    out("OK" if 1 <= len(mats) <= 4 else "WARN", "materials {} (keep 1-4: diffuse, emissive, decals)".format(len(mats)))
    used = {p.material_index for p in me.polygons}
    unused = [m.name for i, m in enumerate(me.materials) if i not in used]
    out("OK" if not unused else "WARN", "unused material slots: {}".format(", ".join(unused) or "none"))
    for m in mats:
        images = [n.image for n in (m.node_tree.nodes if m.use_nodes else []) if n.type == "TEX_IMAGE" and n.image]
        if not images:
            out("FAIL", "material {} has no image texture (GTA shaders need a DiffuseSampler)".format(m.name))
            continue
        for img in images:
            w, h = img.size
            pow2 = w > 0 and h > 0 and (w & (w - 1)) == 0 and (h & (h - 1)) == 0
            out("OK" if pow2 and max(w, h) <= 2048 else "FAIL", "texture {} {}x{} (power of two, max 2048)".format(img.name, w, h))
            path = bpy.path.abspath(img.filepath) if img.filepath else ""
            if not img.packed_file and (not path or not os.path.exists(path)):
                out("FAIL", "texture file missing on disk: {}".format(img.filepath or img.name))
        shader = m.get("prop_forge_shader")
        if shader:
            out("OK", "material {} -> {}".format(m.name, shader))
    cols = [o for o in bpy.context.scene.objects if o.name.startswith(root.name + "_col_")]
    is_marker = meta.get("archetype") == "mascot_marker" or meta.get("colliders") == 0
    if cols:
        out("OK", "collision boxes: {}".format(len(cols)))
    elif is_marker:
        out("OK", "no collision (marker / decoration)")
    else:
        out("FAIL", "no collision boxes named {}_col_N; players will walk through the prop".format(root.name))
    anim_meta = meta.get("anim")
    if anim_meta:
        rig = bpy.data.objects.get(anim_meta.get("rig_name", root.name + "_rig"))
        has_rig = rig is not None and rig.type == "ARMATURE"
        out("OK" if has_rig else "FAIL", "animation rig {} present".format(anim_meta.get("rig_name", root.name + "_rig")))
        if has_rig:
            nbones = len(rig.data.bones)
            out("OK" if 2 <= nbones <= 64 else "FAIL", "rig bones: {} (2-64)".format(nbones))
            has_arm_mod = any(m.type == "ARMATURE" and m.object == rig for m in root.modifiers)
            out("OK" if has_arm_mod else "FAIL", "mesh has ARMATURE modifier bound to rig")
            bone_names = {b.name for b in rig.data.bones}
            bad_vg = [vg.name for vg in root.vertex_groups if vg.name not in bone_names]
            out("OK" if not bad_vg else "FAIL", "vertex groups match rig bones" + ("" if not bad_vg else " (unknown: {})".format(", ".join(bad_vg))))
            act = rig.animation_data.action if rig.animation_data else None
            out("OK" if act is not None and len(act.fcurves) > 0 else "FAIL", "rig action keyframes: {}".format(len(act.fcurves) if act else 0))
    orphans = sum(1 for m in bpy.data.meshes if m.users == 0) + sum(1 for m in bpy.data.materials if m.users == 0)
    out("OK" if orphans == 0 else "WARN", "orphan meshes/materials: {}".format(orphans))
    return finish(lines)


def finish(lines):
    fails = sum(1 for l in lines if l.startswith("FAIL"))
    warns = sum(1 for l in lines if l.startswith("WARN"))
    lines.append("RESULT fail={} warn={}".format(fails, warns))
    return lines


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--budget", type=int, default=0)
    args = ap.parse_args(argv)
    paths = []
    if os.path.isdir(args.blend):
        paths = [os.path.join(args.blend, f) for f in sorted(os.listdir(args.blend)) if f.endswith(".blend")]
    else:
        paths = [args.blend]
    total_fail = 0
    for path in paths:
        bpy.ops.wm.open_mainfile(filepath=path)
        stem = os.path.splitext(os.path.basename(path))[0]
        lines = validate_scene(stem if bpy.data.objects.get(stem) else None, args.budget or None)
        print("== " + path)
        for line in lines:
            print(line)
        total_fail += int(lines[-1].split("fail=")[1].split()[0])
    print("TOTAL files={} fail={}".format(len(paths), total_fail))


if __name__ == "__main__":
    main()
