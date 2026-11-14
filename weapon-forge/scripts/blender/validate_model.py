"""weapon-forge: check a model against the slot contract before baking or export.

Headless:
  blender -b --factory-startup --python-exit-code 1 -P validate_model.py -- --blend model.blend [--slot knife]

Inside a live Blender session (Antigravity / Blender MCP execute_blender_code):
  import runpy
  check = runpy.run_path(r"<skill>/scripts/blender/validate_model.py")["validate_scene"]
  print(check("knife"))

Never saves or changes the scene.
"""

import argparse
import re
import sys

import bpy
from mathutils import Vector

SLOTS = {
    "poolcue": {"z": (-0.18, 0.78), "tris": 40054, "kind": "long", "bones": ["Gun_Root", "Gun_GripR", "Gun_GripL"]},
    "bat": {"z": (-0.18, 0.72), "tris": 30000, "kind": "long", "bones": ["Gun_Root", "Gun_GripR"]},
    "bottle": {"z": (-0.065, 0.31), "tris": 30000, "kind": "long", "bones": ["Gun_Root", "Gun_GripR"]},
    "machete": {"z": (-0.060, 0.49), "tris": 30000, "kind": "long", "bones": ["Gun_Root", "Gun_GripR"]},
    "knife": {"z": (-0.065, 0.27), "tris": 30000, "kind": "long", "bones": ["Gun_Root", "Gun_GripR"]},
    "knuckle": {"z": (-0.075, 0.12), "tris": 30000, "kind": "plate", "bones": ["Gun_Root", "Gun_GripR"]},
    "revolver": {"z": (-0.14, 0.10), "tris": 30000, "kind": "gun", "bones": ["Gun_Root", "Gun_GripR", "Gun_Muzzle"]},
}


def detect_slot(name):
    low = name.lower()
    for s in ("poolcue", "bottle", "machete", "knife", "knuckle", "revolver", "bat"):
        if s in low:
            return s
    return ""


def is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0


def validate_scene(slot="", objects=None):
    items = []

    def add(level, msg):
        items.append((level, msg))

    objs = list(objects if objects is not None else bpy.context.scene.objects)
    rigs = [o for o in objs if o.type == "ARMATURE"]
    meshes = [o for o in objs if o.type == "MESH" and not o.name.lower().startswith("bound")]
    if len(rigs) != 1:
        add("FAIL", f"expected 1 armature, found {len(rigs)}")
    if len(meshes) != 1:
        add("WARN" if meshes else "FAIL", f"expected 1 render mesh, found {len(meshes)}")
    if not rigs or not meshes:
        return report(items)

    rig, ob = rigs[0], meshes[0]
    slot = slot or detect_slot(rig.name)
    if slot not in SLOTS:
        add("FAIL", f"cannot tell the slot from '{rig.name}', pass --slot")
        return report(items)
    spec = SLOTS[slot]

    if re.fullmatch(r"w_(me|pi)_[a-z0-9_]+", rig.name):
        add("PASS", f"model name {rig.name}")
    else:
        add("WARN", f"model name {rig.name} does not follow w_me_<id>_<slot>; it must match <Model> in the meta")
    if ob.parent is not rig:
        add("WARN", "render mesh is not parented to the armature")

    for o, label in ((rig, "armature"), (ob, "mesh")):
        moved = o.location.length > 1e-5 or max(abs(v) for v in o.rotation_euler) > 1e-5
        scaled = max(abs(v - 1.0) for v in o.scale) > 1e-5
        if moved or scaled:
            add("FAIL", f"{label} '{o.name}' has an unapplied transform (loc {tuple(round(v, 4) for v in o.location)}, scale {tuple(round(v, 4) for v in o.scale)})")
    bone_names = set(rig.data.bones.keys())
    for b in spec["bones"]:
        add("PASS" if b in bone_names else "FAIL", f"bone {b}" + ("" if b in bone_names else " is missing"))

    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if tris <= 0:
        add("FAIL", "mesh has no faces")
        return report(items)
    add("WARN" if tris > spec["tris"] else "PASS", f"tris {tris} (budget {spec['tris']})")

    n = len(me.vertices)
    flat = [0.0] * (n * 3)
    me.vertices.foreach_get("co", flat)
    lo = Vector((min(flat[0::3]), min(flat[1::3]), min(flat[2::3])))
    hi = Vector((max(flat[0::3]), max(flat[1::3]), max(flat[2::3])))
    ext = hi - lo
    z0, z1 = spec["z"]
    if slot == "revolver":
        add("WARN" if ext.x < 0.25 or ext.x > 0.42 else "PASS", f"gun length on X {ext.x:.3f} m")
    in_range = lo.z >= z0 and hi.z <= z1
    add("PASS" if in_range else "WARN", f"Z {lo.z:.3f}..{hi.z:.3f} (slot {z0}..{z1})")
    if spec["kind"] == "long":
        g_xs = [flat[i] for i in range(0, len(flat), 3) if -0.015 <= flat[i + 2] <= 0.025]
        g_ys = [flat[i + 1] for i in range(0, len(flat), 3) if -0.015 <= flat[i + 2] <= 0.025]
        if g_xs and g_ys:
            gcx = 0.5 * (min(g_xs) + max(g_xs))
            gcy = 0.5 * (min(g_ys) + max(g_ys))
            ok_grip = abs(gcx) <= 0.012 and abs(gcy) <= 0.012
            add("PASS" if ok_grip else "WARN", f"grip center at Z=0.0123 is ({gcx:.4f}, {gcy:.4f})")
    axis = "XYZ"[max(range(3), key=lambda i: ext[i])]
    thin = "XYZ"[min(range(3), key=lambda i: ext[i])]
    if spec["kind"] == "long" and axis != "Z":
        add("FAIL", f"longest axis is {axis}, melee weapons must run along Z")
    if spec["kind"] == "plate" and (thin != "X" or axis == "X"):
        add("WARN", f"knuckle should be thin on X and long on Z, found thin {thin}, long {axis}")
    if spec["kind"] == "gun" and axis != "X":
        add("FAIL", f"longest axis is {axis}, guns must point along +X")

    group = ob.vertex_groups.get("Gun_Main_Bone") or ob.vertex_groups.get("Gun_Root")
    if group is None:
        add("WARN", "no Gun_Main_Bone or Gun_Root vertex group")
    else:
        unweighted = sum(1 for v in me.vertices if not any(g.group == group.index and g.weight > 0 for g in v.groups))
        add("WARN" if unweighted else "PASS", f"{group.name} covers all vertices ({unweighted} unweighted)")

    if not me.uv_layers:
        add("FAIL", "no UV map")
    elif me.uv_layers[0].name != "UVMap 0":
        add("WARN", f"first UV map is '{me.uv_layers[0].name}', Sollumz expects 'UVMap 0'")
    if "Color 1" not in me.color_attributes:
        add("WARN", "no 'Color 1' colour attribute")

    used = sorted({p.material_index for p in me.polygons})
    mats = [me.materials[i] for i in used if i < len(me.materials) and me.materials[i]]
    if not mats:
        add("FAIL", "no material on the faces")
    if len(mats) > 3:
        add("WARN", f"{len(mats)} materials in use; every extra one is another draw call, the server's models use 1-3")
    baked = 0
    for m in mats:
        imgs = [n.image for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image] if m.use_nodes else []
        for img in imgs:
            baked += 1
            w, h = img.size
            if w and h and not (is_power_of_two(w) and is_power_of_two(h)):
                add("WARN", f"texture {img.name} is {w}x{h}, not a power of two")
    if not baked:
        add("WARN", "no baked image texture yet; run with --bake before export")

    return report(items)


def report(items):
    fails = sum(1 for level, _ in items if level == "FAIL")
    warns = sum(1 for level, _ in items if level == "WARN")
    lines = [f"{level}  {msg}" for level, msg in items]
    lines.append(f"RESULT fail={fails} warn={warns}")
    return "\n".join(lines)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--slot", default="", choices=[""] + sorted(SLOTS))
    args = ap.parse_args(argv)
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    text = validate_scene(args.slot)
    print(f"@@VALIDATE {args.blend}")
    print(text)
    if " fail=0 " not in text.splitlines()[-1] + " ":
        sys.exit(1)


if __name__ == "__main__":
    main()
