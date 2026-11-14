"""weapon-forge: build stylised FiveM weapon-skin meshes from a JSON spec (Blender 4.2+).

blender -b --factory-startup -P forge_weapon.py -- --spec spec.json --out DIR
        [--only poolcue,bat] [--bake 1024] [--samples 32] [--no-sheet] [--icons]

Axes match the shipped skins: melee long axis +Z with the origin at the hand,
blades flat in XZ with the edge toward +X, knuckle flat in YZ, revolver muzzle +X.
Every material outputs Emission only, so a render shows what emissive.sps shows.
"""

import argparse
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

TAU = math.tau
FOCUS = None
YAW = 0.0

SLOTS = {
    "poolcue": {"prefix": "w_me", "z": (-0.15, 0.75), "tris": (8000, 36000)},
    "bat": {"prefix": "w_me", "z": (-0.14, 0.67), "tris": (8000, 30000)},
    "bottle": {"prefix": "w_me", "z": (-0.09, 0.28), "tris": (8000, 30000)},
    "machete": {"prefix": "w_me", "z": (-0.045, 0.46), "tris": (8000, 30000)},
    "knife": {"prefix": "w_me", "z": (-0.05, 0.31), "tris": (8000, 30000)},
    "knuckle": {"prefix": "w_me", "z": (-0.07, 0.11), "tris": (8000, 30000)},
    "revolver": {"prefix": "w_pi", "z": (-0.13, 0.07), "tris": (8000, 30000)},
}

FAMILIES = {
    "holy_gothic": {
        "palette": {"primary": "#0d0d11", "secondary": "#f1eee7", "accent": "#dcdce4", "glow": "#fff1cf", "grip": "#15151a", "metal": "#e8e8ee"},
        "finish": {"primary": "gloss", "secondary": "porcelain", "accent": "chrome", "glow": "emit", "grip": "quilted", "metal": "chrome"},
        "wrap": "thorn", "motif": "cross", "charm": "cross", "cap": "drip", "topper": "wings", "blade": "clip", "lace": True,
        "bottle_type": "balisong", "knuckle_type": "blade_knuckle", "optic": True, "tac_light": True, "wings_slide": True,
    },
    "obsidian_beast": {
        "palette": {"primary": "#08080b", "secondary": "#f2f2f4", "accent": "#e6e6ea", "glow": "#ffffff", "grip": "#0f0f13", "metal": "#dfe0e6"},
        "finish": {"primary": "marble", "secondary": "matte", "accent": "chrome", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "scale", "motif": "none", "charm": "none", "cap": "ring", "topper": "dragon", "blade": "kris",
        "bottle_type": "war_pick", "knuckle_type": "blade_knuckle", "dragon_slide": True,
    },
    "silver_chain": {
        "palette": {"primary": "#d9dbe2", "secondary": "#16171c", "accent": "#f7f8fb", "glow": "#ffffff", "grip": "#15161b", "metal": "#eceef3"},
        "finish": {"primary": "chrome", "secondary": "matte", "accent": "chrome", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "chain", "motif": "star4", "charm": "none", "cap": "ring", "topper": "none", "blade": "clip",
        "knuckle_type": "blade_knuckle",
    },
    "mono_street": {
        "palette": {"primary": "#0f0f11", "secondary": "#f2f2f2", "accent": "#f2f2f2", "glow": "#ffffff", "grip": "#141416", "metal": "#2a2a2e"},
        "finish": {"primary": "matte", "secondary": "matte", "accent": "matte", "glow": "emit", "grip": "carbon", "metal": "matte"},
        "wrap": "none", "motif": "bars", "charm": "tag", "cap": "ring", "topper": "none", "blade": "clip", "bands": True,
    },
    "toxic_graffiti": {
        "palette": {"primary": "#060608", "secondary": "#f5f5f2", "accent": "#8cff1a", "glow": "#9dff2e", "grip": "#0a0a0c", "metal": "#c8c8cc"},
        "finish": {"primary": "gloss", "secondary": "porcelain", "accent": "gloss", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "bone", "motif": "crown", "charm": "none", "cap": "drip", "drip_key": "accent", "topper": "none", "blade": "tanto",
        "knuckle_type": "blade_knuckle",
    },
    "clean_scifi": {
        "palette": {"primary": "#f2f5f8", "secondary": "#15181d", "accent": "#32c8ff", "glow": "#4fd8ff", "grip": "#15181d", "metal": "#c5ccd4"},
        "finish": {"primary": "porcelain", "secondary": "matte", "accent": "gloss", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "none", "motif": "hex", "charm": "none", "cap": "ring", "topper": "none", "blade": "tanto", "vents": True, "glowlines": True,
        "optic": True, "tac_light": True,
    },
    "storm": {
        "palette": {"primary": "#07090f", "secondary": "#0e6fff", "accent": "#dff3ff", "glow": "#3fb6ff", "grip": "#0b0d14", "metal": "#cfd6e2"},
        "finish": {"primary": "lightning", "secondary": "gloss", "accent": "chrome", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "bolt", "motif": "bolt", "charm": "none", "cap": "claw", "topper": "none", "blade": "bolt",
    },
    "cosmos": {
        "palette": {"primary": "#3b1a9e", "secondary": "#ff9df2", "accent": "#b58cff", "glow": "#d9b8ff", "grip": "#16141c", "metal": "#3a3844"},
        "finish": {"primary": "nebula", "secondary": "gloss", "accent": "gloss", "glow": "emit", "grip": "carbon", "metal": "chrome"},
        "wrap": "none", "motif": "star4", "charm": "none", "cap": "ring", "topper": "none", "blade": "kris", "glowlines": True,
    },
    "ocean": {
        "palette": {"primary": "#7fd0f2", "secondary": "#f4fbff", "accent": "#c9ced6", "glow": "#8fe6ff", "grip": "#f0f6fa", "metal": "#b9c0ca"},
        "finish": {"primary": "marble", "secondary": "porcelain", "accent": "chrome", "glow": "emit", "grip": "gloss", "metal": "chrome"},
        "wrap": "rope", "motif": "diamond", "charm": "none", "cap": "claw", "topper": "shell", "blade": "scythe",
    },
    "kawaii_mascot": {
        "palette": {"primary": "#ffd6e2", "secondary": "#fff3f0", "accent": "#ff86ab", "glow": "#ffd1e0", "grip": "#ffc2d4", "metal": "#fff6f2"},
        "finish": {"primary": "porcelain", "secondary": "porcelain", "accent": "gloss", "glow": "emit", "grip": "quilted", "metal": "porcelain"},
        "wrap": "ribbon", "motif": "heart", "charm": "heart", "cap": "mascot", "topper": "mascot", "mascot": "bunny", "blade": "spear", "bow": True,
        "bottle_type": "scepter", "knuckle_type": "lace_fan",
    },
    "pastel_jewel": {
        "palette": {"primary": "#f6e3ef", "secondary": "#cfe0f7", "accent": "#f6b7cd", "glow": "#ffe6f2", "grip": "#f3c6d8", "metal": "#f7e8ec"},
        "finish": {"primary": "cracked_marble", "secondary": "iridescent", "accent": "gloss", "glow": "emit", "grip": "rope", "metal": "chrome"},
        "wrap": "rope", "motif": "butterfly", "charm": "heart", "cap": "gem", "topper": "wings", "blade": "kris", "lace": True, "stones": True, "bow": True,
        "bottle_type": "scepter", "knuckle_type": "lace_fan", "wings_slide": True,
    },
    "pop_arcade": {
        "palette": {"primary": "#ff2f8e", "secondary": "#f7e3c5", "accent": "#16161c", "glow": "#4fe3ff", "grip": "#17171d", "metal": "#ffd24a"},
        "finish": {"primary": "gloss", "secondary": "matte", "accent": "gloss", "glow": "emit", "grip": "carbon", "metal": "gloss"},
        "wrap": "none", "motif": "paw", "charm": "none", "cap": "gem", "topper": "none", "blade": "pixel", "stickers": True,
    },
    "field_tactical": {
        "palette": {"primary": "#eaeae2", "secondary": "#4b5a2b", "accent": "#d8342a", "glow": "#ffb23a", "grip": "#1b1b1b", "metal": "#8a8d86"},
        "finish": {"primary": "matte", "secondary": "matte", "accent": "matte", "glow": "emit", "grip": "rope", "metal": "brushed_steel"},
        "wrap": "none", "motif": "bars", "charm": "none", "cap": "ring", "topper": "none", "blade": "tanto", "vents": True,
        "optic": True, "tac_light": True,
    },
    "oni_blackgold": {
        "palette": {"primary": "#0b0a0e", "secondary": "#1a0f14", "accent": "#a31828", "glow": "#ff2d3d", "grip": "#100a0d", "metal": "#e2b24c", "ember": "#9b1020"},
        "finish": {"primary": "lacquer", "secondary": "lacquer", "accent": "porcelain", "glow": "emit", "hot": "emit", "ember": "emit", "grip": "matte", "metal": "gold"},
        "wrap": "none", "motif": "none", "charm": "none", "cap": "ring", "topper": "none", "blade": "clip", "serrate": True, "oni": True,
    },
    "festival_lantern": {
        "palette": {"primary": "#1d1018", "secondary": "#f7ebd9", "accent": "#ff9ec6", "glow": "#ffcf6e", "grip": "#2a1520", "metal": "#e6b85c"},
        "finish": {"primary": "lacquer", "secondary": "porcelain", "accent": "gloss", "glow": "emit", "grip": "rope", "metal": "gold"},
        "wrap": "ribbon", "motif": "star4", "charm": "tassel", "cap": "gem", "topper": "wings", "blade": "katana", "bow": True, "fuller": True,
        "bottle_type": "scepter", "knuckle_type": "lace_fan",
    },
    "crystal_prism": {
        "palette": {"primary": "#e8f6ff", "secondary": "#c7a8ff", "accent": "#7be3ff", "glow": "#ff9ce6", "grip": "#d8e6f8", "metal": "#f2f6fc"},
        "finish": {"primary": "iridescent", "secondary": "cracked_marble", "accent": "chrome", "glow": "emit", "grip": "quilted", "metal": "chrome"},
        "wrap": "ribbon", "motif": "butterfly", "charm": "star", "cap": "gem", "topper": "wings", "blade": "spear", "stones": True, "glowlines": True,
        "bottle_type": "scepter", "knuckle_type": "lace_fan", "wings_slide": True,
    },
    "velvet_venom": {
        "palette": {"primary": "#090408", "secondary": "#38091e", "accent": "#ff2468", "glow": "#ff5c9a", "grip": "#12070f", "metal": "#d4c8d0"},
        "finish": {"primary": "forged_carbon", "secondary": "lacquer", "accent": "gloss", "glow": "emit", "grip": "quilted", "metal": "chrome"},
        "wrap": "thorn", "motif": "diamond", "charm": "cross", "cap": "claw", "topper": "dragon", "blade": "kris", "serrate": True, "fuller": True,
        "bottle_type": "balisong", "knuckle_type": "blade_knuckle", "dragon_slide": True,
    },
    "cursed_pirate": {
        "palette": {"primary": "#071c1b", "secondary": "#13423c", "accent": "#ffd15c", "glow": "#26f2a6", "grip": "#1a1410", "metal": "#c9a45c"},
        "finish": {"primary": "jade", "secondary": "damascus", "accent": "gold", "glow": "emit", "grip": "rope", "metal": "gold"},
        "wrap": "chain", "motif": "crown", "charm": "tag", "cap": "claw", "topper": "shell", "blade": "scythe", "serrate": True,
        "bottle_type": "war_pick", "knuckle_type": "jaw_shield",
    },
    "pumpkin_specter": {
        "palette": {"primary": "#160824", "secondary": "#ff7b1a", "accent": "#9b3cff", "glow": "#9dff3a", "grip": "#12071c", "metal": "#2b2436"},
        "finish": {"primary": "lacquer", "secondary": "gloss", "accent": "gloss", "glow": "emit", "grip": "rope", "metal": "brushed_steel"},
        "wrap": "bone", "motif": "x_face", "charm": "star", "cap": "drip", "drip_key": "secondary", "topper": "wings", "blade": "cleaver", "serrate": True,
        "bottle_type": "war_pick", "knuckle_type": "jaw_shield",
    },
    "sweet_confection": {
        "palette": {"primary": "#ffd8ec", "secondary": "#fff7fb", "accent": "#8be8ff", "glow": "#ffe875", "grip": "#ffc4e2", "metal": "#fff2f8"},
        "finish": {"primary": "porcelain", "secondary": "porcelain", "accent": "gloss", "glow": "emit", "grip": "quilted", "metal": "porcelain"},
        "wrap": "ribbon", "motif": "star5", "charm": "heart", "cap": "mascot", "topper": "mascot", "mascot": "cat", "blade": "spear", "bow": True, "stickers": True,
        "bottle_type": "scepter", "knuckle_type": "lace_fan",
    },
}


def xform(loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    s = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return Matrix.LocRotScale(Vector(loc), Euler([math.radians(a) for a in rot], "XYZ"), Vector(s))


def facing(loc, normal, size=1.0, spin=0.0):
    quat = Vector(normal).normalized().to_track_quat("Z", "Y")
    return Matrix.LocRotScale(Vector(loc), quat, Vector((size, size, 1.0))) @ Matrix.Rotation(math.radians(spin), 4, "Z")


def circle(r=1.0, n=24, cx=0.0, cy=0.0, phase=0.0):
    return [(cx + r * math.cos(phase + i / n * TAU), cy + r * math.sin(phase + i / n * TAU)) for i in range(n)]


def ellipse(rx, ry, n=20, cx=0.0, cy=0.0):
    return [(cx + rx * math.cos(i / n * TAU), cy + ry * math.sin(i / n * TAU)) for i in range(n)]


def chaikin(loop, n=2):
    pts = list(loop)
    for _ in range(n):
        out = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            if a == b:
                out.append(a)
                continue
            out.append((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25))
            out.append((a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))
        pts = out
    return pts


def sharp(p):
    return [p, p, p]


def star(n, inner, outer=1.0):
    return [
        ((outer if i % 2 == 0 else inner) * math.cos(TAU / 4 + i * math.pi / n),
         (outer if i % 2 == 0 else inner) * math.sin(TAU / 4 + i * math.pi / n))
        for i in range(2 * n)
    ]


def motif_loops(name):
    if name == "heart":
        pts = []
        for i in range(36):
            t = i / 36 * TAU
            pts.append((16 * math.sin(t) ** 3 / 17, (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17 + 0.1))
        return [pts]
    if name == "star4":
        return [star(4, 0.2)]
    if name == "star5":
        return [star(5, 0.45)]
    if name == "cross":
        w, f, c = 0.15, 0.32, 0.28
        return [[(-w, c + w), (-f, 1.0), (0, 0.86), (f, 1.0), (w, c + w), (0.72, c + f), (0.6, c), (0.72, c - f), (w, c - w), (f, -1.0), (0, -0.86), (-f, -1.0), (-w, c - w), (-0.72, c - f), (-0.6, c), (-0.72, c + f)]]
    if name == "bolt":
        return [[(0.1, 1), (-0.55, -0.1), (-0.05, -0.1), (-0.25, -1), (0.55, 0.2), (0.05, 0.2), (0.45, 1)]]
    if name == "crown":
        return [[(-1, -0.6), (-1, 0.7), (-0.5, 0.05), (0, 0.9), (0.5, 0.05), (1, 0.7), (1, -0.6)]]
    if name == "diamond":
        return [[(0, 1), (0.6, 0), (0, -1), (-0.6, 0)]]
    if name == "hex":
        return [circle(1, 6, phase=TAU / 12), circle(0.45, 6, phase=TAU / 12)]
    if name == "shuriken":
        return [star(4, 0.3), circle(0.2, 12)]
    if name == "paw":
        return [ellipse(0.55, 0.45, cy=-0.35), circle(0.2, 14, -0.62, 0.2), circle(0.2, 14, -0.22, 0.58), circle(0.2, 14, 0.22, 0.58), circle(0.2, 14, 0.62, 0.2)]
    if name == "bars":
        return [[(-0.9 + i * 0.65, -0.7), (-0.55 + i * 0.65, -0.7), (-0.1 + i * 0.65, 0.7), (-0.45 + i * 0.65, 0.7)] for i in range(3)]
    if name == "butterfly":
        upper = chaikin([(0.04, 0.05), (0.4, 0.95), (1.0, 0.85), (0.85, 0.2), (0.3, -0.05)], 2)
        lower = chaikin([(0.04, -0.08), (0.3, -0.12), (0.7, -0.3), (0.55, -0.85), (0.15, -0.65)], 2)
        return [upper, lower, [(-x, y) for x, y in upper], [(-x, y) for x, y in lower], ellipse(0.05, 0.6, n=10)]
    if name == "bow":
        right = chaikin([(0.12, 0.1), (0.95, 0.65), (1.0, -0.55), (0.12, -0.1)], 2)
        return [right, [(-x, y) for x, y in right], ellipse(0.17, 0.2, n=12)]
    if name == "wing":
        return [chaikin([(0, 0.12), (0.35, 0.5), (0.75, 0.62), (1.0, 0.5), (0.82, 0.34), (0.92, 0.18), (0.7, 0.06), (0.76, -0.1), (0.52, -0.16), (0.52, -0.32), (0.3, -0.24), (0, -0.12)], 2)]
    if name == "shell":
        pts = [(0.0, -1.0)]
        for i in range(7):
            a = math.radians(170 - i * 160 / 6)
            pts.append((math.cos(a), 0.15 + math.sin(a) * 0.85))
            pts.append((0.8 * math.cos(a - 0.14), 0.15 + 0.8 * math.sin(a - 0.14)))
        return [pts[:-1]]
    if name == "x_face":
        def x_at(cx, cy):
            w, l = 0.05, 0.2
            plus = [(-w, l), (w, l), (w, w), (l, w), (l, -w), (w, -w), (w, -l), (-w, -l), (-w, -w), (-l, -w), (-l, w), (-w, w)]
            return [(cx + (x - y) * 0.707, cy + (x + y) * 0.707) for x, y in plus]
        smile = [(-0.5, -0.25), (-0.2, -0.55), (0.2, -0.55), (0.5, -0.25), (0.42, -0.2), (0.15, -0.44), (-0.15, -0.44), (-0.42, -0.2)]
        return [circle(1, 28), x_at(-0.38, 0.25), x_at(0.38, 0.25), smile]
    return []


def scene():
    return bpy.context.scene


def shape2d(loops, depth, bevel=0.0, bevel_res=0, inset=0.0):
    cu = bpy.data.curves.new("forge_shape", "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = bevel_res
    cu.offset = -bevel - inset
    for loop in loops:
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for p, (x, y) in zip(sp.points, loop):
            p.co = (x, y, 0.0, 1.0)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new("forge_shape", cu)
    scene().collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return bm


def lathe(profile, seg=16):
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(i / seg * TAU), r * math.sin(i / seg * TAU), z)) for i in range(seg)])
    for lower, upper in zip(rings, rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((lower[j], lower[k], upper[k], upper[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm


def tube(points, radius, seg=6, flat=None, radial=False, taper=None):
    bm = bmesh.new()
    pts = [Vector(p) for p in points]
    last = len(pts) - 1
    rings = []
    normal = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, last)] - pts[max(i - 1, 0)]).normalized()
        if radial:
            n = Vector((p.x, p.y, 0.0))
            n = (n - t * n.dot(t)).normalized()
        else:
            if normal is None:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                normal = t.cross(ref).normalized()
            normal = (normal - t * normal.dot(t)).normalized()
            n = normal
        b = t.cross(n)
        r = radius * (taper(i / last) if taper else 1.0)
        rings.append([bm.verts.new(p + n * (math.cos(k / seg * TAU) * r * (flat or 1.0)) + b * (math.sin(k / seg * TAU) * r)) for k in range(seg)])
    for lower, upper in zip(rings, rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((lower[j], lower[k], upper[k], upper[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm


def torus(major, minor, seg=10, tube_seg=5):
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = i / seg * TAU
        c = Vector((math.cos(a), math.sin(a), 0.0))
        rings.append([bm.verts.new(c * (major + minor * math.cos(j / tube_seg * TAU)) + Vector((0, 0, minor * math.sin(j / tube_seg * TAU)))) for j in range(tube_seg)])
    for i in range(seg):
        for j in range(tube_seg):
            a, b = rings[i], rings[(i + 1) % seg]
            k = (j + 1) % tube_seg
            bm.faces.new((a[j], b[j], b[k], a[k]))
    return bm


def box(sx, sy, sz, chamfer=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    if chamfer > 0.0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=chamfer, segments=1, profile=0.5, affect="EDGES")
    return bm


def ball(radius, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    return bm


def cone(radius, height, seg=6):
    return lathe([(radius, 0.0), (radius * 0.01, height)], seg)


def helix(rfn, z0, z1, turns, phase=0.0, per_turn=22, lift=0.0):
    count = max(4, int(turns * per_turn))
    out = []
    for i in range(count + 1):
        u = i / count
        z = z0 + (z1 - z0) * u
        a = phase + turns * TAU * u
        r = rfn(z) + lift
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def along(points, step):
    out = [(points[0], (points[1] - points[0]).normalized())]
    travelled = 0.0
    for a, b in zip(points, points[1:]):
        seg = (b - a).length
        travelled += seg
        while travelled >= step:
            travelled -= step
            p = b - (b - a).normalized() * travelled
            out.append((p, (b - a).normalized()))
    return out


class Forge:
    def __init__(self, style, rng):
        self.style = style
        self.rng = rng
        self.parts = {}

    def put(self, bm, key, m=None):
        if m is not None:
            bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
        me = bpy.data.meshes.new("forge_tmp")
        bm.to_mesh(me)
        bm.free()
        self.parts.setdefault(key, bmesh.new()).from_mesh(me)
        bpy.data.meshes.remove(me)

    def badge(self, name, key, m, depth=0.0015):
        loops = motif_loops(name)
        if loops:
            self.put(shape2d(loops, depth), key, m)

    def badge_on_shaft(self, name, key, rfn, z, angle, size, lift=0.0008):
        r = rfn(z) + lift
        n = (math.cos(angle), math.sin(angle), 0.0)
        self.badge(name, key, facing((n[0] * r, n[1] * r, z), n, size))

    def badge_on_face(self, name, key, x, z, half_t, size, spin=0.0):
        self.badge(name, key, facing((x, half_t, z), (0, 1, 0), size, spin))
        self.badge(name, key, facing((x, -half_t, z), (0, -1, 0), size, spin))

    def ring(self, key, rfn, z, thick=0.002):
        self.put(torus(rfn(z), thick, 18, 5), key, xform((0, 0, z)))

    def stones(self, key, rfn, z, size=0.0016):
        r = rfn(z) + size * 0.55
        count = int(TAU * r / (size * 2.2))
        for i in range(count):
            a = i / count * TAU
            self.put(ball(size, 1), key, xform((r * math.cos(a), r * math.sin(a), z)))

    def lace(self, key, rfn, z, size=0.005):
        r = rfn(z) + 0.0006
        count = int(TAU * r / (size * 1.9))
        for i in range(count):
            a = i / count * TAU
            m = facing((r * math.cos(a), r * math.sin(a), z - size * 0.8), (math.cos(a), math.sin(a), 0), 1.0)
            self.put(torus(size, 0.0009, 8, 3), key, m)

    def wrap(self, rfn, z0, z1):
        kind = self.style["wrap"]
        if kind == "none" or z1 <= z0:
            return
        span = z1 - z0
        if kind == "thorn":
            path = helix(rfn, z0, z1, span * 6.0, lift=0.0016)
            self.put(tube(path, 0.0017, 5), "accent")
            for p, t in along(path, 0.018)[1::1]:
                side = Vector((p.x, p.y, 0)).normalized()
                direction = (side * 0.9 + t * self.rng.uniform(-0.5, 0.5)).normalized()
                self.put(cone(0.0022, self.rng.uniform(0.009, 0.015), 4), "accent", Matrix.Translation(p) @ direction.to_track_quat("Z", "Y").to_matrix().to_4x4())
        elif kind == "chain":
            path = helix(rfn, z0, z1, span * 5.5, lift=0.0024)
            for i, (p, t) in enumerate(along(path, 0.0118)):
                q = t.to_track_quat("X", "Z").to_matrix().to_4x4()
                self.put(torus(0.0062, 0.0015, 10, 4), "accent", Matrix.Translation(p) @ q @ Matrix.Rotation(math.radians(90 * (i % 2) + 45), 4, "X") @ Matrix.Diagonal((1.25, 0.8, 1.0, 1.0)))
        elif kind == "rope":
            for offset in (0.0, TAU / 2):
                self.put(tube(helix(rfn, z0, z1, span * 14.0, offset, 12, 0.0014), 0.0024, 5), "accent")
        elif kind == "ribbon":
            self.put(tube(helix(rfn, z0, z1, span * 5.0, 0.0, 26, 0.0012), 0.0065, 4, flat=0.22, radial=True), "accent")
        elif kind == "bone":
            a = helix(rfn, z0, z1, span * 3.2, 0.0, 22, 0.002)
            b = helix(rfn, z0, z1, -span * 3.2, 1.2, 22, 0.002)
            self.put(tube(a, 0.0048, 6, taper=lambda u: 0.75 + 0.5 * abs(math.sin(u * 31.0))), "secondary")
            self.put(tube(b, 0.0048, 6, taper=lambda u: 0.75 + 0.5 * abs(math.sin(u * 23.0))), "secondary")
        elif kind == "bolt":
            for offset in (0.0, TAU / 2):
                path = helix(rfn, z0, z1, span * 2.6, offset, 16, 0.0014)
                jag = [p + Vector((0, 0, 0.012 if i % 2 else -0.012)) for i, p in enumerate(path)]
                self.put(tube(jag, 0.0024, 4, flat=0.5, radial=True), "glow")
        elif kind in ("scale", "dragon"):
            key = self.style.get("wrap_key", "accent")
            path = helix(rfn, z0, z1, span * 3.6, 0.0, 28, 0.0042)
            self.put(
                tube(
                    path,
                    0.0085,
                    10,
                    taper=lambda u: 0.22 + 0.95 * min(1.0, u * 4.5) * min(1.0, (1.0 - u) * 5.0 + 0.58),
                ),
                key,
            )
            # Belly plates & dorsal ridge spines along the coiled dragon body
            for idx_s, (p, t) in enumerate(along(path, 0.0085)[4:]):
                side = Vector((p.x, p.y, 0)).normalized()
                fin_dir = (side * 0.65 + t * 0.75).normalized()
                h_fin = 0.0065 + 0.0035 * math.sin(min(1.0, idx_s / 30.0) * math.pi)
                self.put(
                    cone(0.0036, h_fin, 4),
                    key,
                    Matrix.Translation(p + side * 0.0048) @ fin_dir.to_track_quat("Z", "Y").to_matrix().to_4x4(),
                )
            head = path[-1]
            tangent = (path[-1] - path[-2]).normalized()
            side = Vector((head.x, head.y, 0)).normalized()
            head_dir = (side * 0.55 + Vector((0, 0, 0.84))).normalized()
            up_dir = (side - head_dir * side.dot(head_dir)).normalized()
            hm = (
                Matrix.Translation(head + side * 0.005)
                @ head_dir.to_track_quat("Z", "Y").to_matrix().to_4x4()
            )
            self.dragon_head(hm, scale=0.028, key=key)

    def dragon_head(self, m, scale=0.032, key="metal", eye_key="glow"):
        """Sculpted 3D Eastern dragon head with snout, open fanged jaws, antlers, whiskers & mane."""
        put = lambda bm, k, local=Matrix.Identity(4): self.put(bm, k, m @ Matrix.Scale(scale, 4) @ local)
        # Cranium & brow dome
        put(ball(0.46, 2), key, xform((0, -0.05, 0.12), scale=(0.88, 0.95, 1.15)))
        # Upper snout bridge (+Z forward, -Y top dorsal, +Y palate)
        snout_pts = [(0, -0.10, 0.20), (0, -0.14, 0.55), (0, -0.12, 0.92), (0, -0.06, 1.18)]
        put(tube(snout_pts, 0.28, 8, flat=1.25, taper=lambda u: 1.0 - 0.32 * u), key)
        # Nasal ridge & flaring nostrils
        put(tube([(0, -0.26, 0.22), (0, -0.30, 0.65), (0, -0.26, 1.12)], 0.09, 6, taper=lambda u: 0.8 + 0.3 * math.sin(u * math.pi)), key)
        for sx in (-1, 1):
            put(ball(0.11, 1), key, xform((sx * 0.16, -0.18, 1.08), scale=(1.1, 0.8, 1.3)))
            # Fierce brow ridges & glowing eyes
            put(tube([(sx * 0.14, -0.26, 0.36), (sx * 0.32, -0.28, 0.20), (sx * 0.42, -0.22, -0.05)], 0.085, 6, taper=lambda u: 1.1 - 0.6 * u), key)
            put(ball(0.085, 2), eye_key, xform((sx * 0.26, -0.18, 0.26), scale=(0.8, 0.9, 1.25)))
            # Sweeping main horns & antler tines
            horn_pts = [(sx * 0.22, -0.22, 0.08), (sx * 0.38, -0.38, -0.32), (sx * 0.44, -0.52, -0.78), (sx * 0.36, -0.68, -1.18)]
            put(tube(horn_pts, 0.12, 6, taper=lambda u: 1.0 - 0.88 * u), key)
            branch_pts = [(sx * 0.36, -0.36, -0.28), (sx * 0.52, -0.26, -0.56), (sx * 0.58, -0.18, -0.82)]
            put(tube(branch_pts, 0.065, 5, taper=lambda u: 1.0 - 0.88 * u), key)
            # Cheek spikes / mane Ruff
            for j in range(3):
                ang = -15 + j * 22
                put(cone(0.08, 0.42, 4), key, xform((sx * 0.34, 0.02 + j * 0.08, 0.02 - j * 0.10), (-115 - j * 12, sx * (38 + ang), 0)))
            # Flowing whisker tendrils
            whisk = [(sx * 0.18, -0.08, 1.02), (sx * 0.42, 0.02, 0.88), (sx * 0.56, 0.16, 0.52), (sx * 0.48, 0.28, 0.18)]
            put(tube(whisk, 0.038, 5, taper=lambda u: 1.0 - 0.85 * u), key)
        # Open lower jaw
        jaw_pts = [(0, 0.12, 0.12), (0, 0.22, 0.48), (0, 0.28, 0.82), (0, 0.24, 1.04)]
        put(tube(jaw_pts, 0.21, 8, flat=1.3, taper=lambda u: 1.0 - 0.42 * u), key)
        # Glowing tongue / fire core inside maw
        put(tube([(0, 0.06, 0.24), (0, 0.12, 0.62), (0, 0.10, 0.88)], 0.09, 6, flat=1.4, taper=lambda u: 1.0 - 0.65 * u), eye_key)
        # Upper and lower fangs
        for sx in (-1, 1):
            put(cone(0.055, 0.24, 5), key, xform((sx * 0.17, -0.02, 0.98), (92, 0, 0)))
            put(cone(0.042, 0.16, 4), key, xform((sx * 0.19, -0.02, 0.72), (92, 0, 0)))
            put(cone(0.048, 0.20, 5), key, xform((sx * 0.14, 0.20, 0.92), (-88, 0, 0)))
            put(cone(0.036, 0.14, 4), key, xform((sx * 0.16, 0.19, 0.68), (-88, 0, 0)))

    def drips(self, key, rfn, z, count=9, longest=0.05):
        for i in range(count):
            a = i / count * TAU + self.rng.uniform(-0.2, 0.2)
            length = self.rng.uniform(0.25, 1.0) * longest
            steps = 7
            pts = [Vector(((rfn(z - length * s / steps) + 0.0009) * math.cos(a), (rfn(z - length * s / steps) + 0.0009) * math.sin(a), z - length * s / steps)) for s in range(steps + 1)]
            self.put(tube(pts, 0.0042, 6, taper=lambda u: 0.7 + 0.6 * math.sin(min(1.0, u * 1.2) * math.pi / 2) ** 8), key)
        self.ring(key, rfn, z, 0.0034)

    def mascot(self, m):
        kind = self.style.get("mascot", "bunny")
        put = lambda bm, key, local=Matrix.Identity(4): self.put(bm, key, m @ local)
        put(ball(0.03, 3), "secondary", xform(scale=(1.08, 0.96, 0.92)))
        if kind == "bunny":
            for side in (-1, 1):
                put(tube([(side * 0.014, 0, 0.018), (side * 0.021, 0, 0.05), (side * 0.021, 0, 0.078)], 0.0086, 8, taper=lambda u: 0.75 + 0.5 * math.sin(u * math.pi) - u * 0.25), "secondary")
                put(tube([(side * 0.014, -0.006, 0.026), (side * 0.021, -0.006, 0.05), (side * 0.021, -0.006, 0.07)], 0.0046, 6), "accent")
        elif kind == "bear":
            for side in (-1, 1):
                put(ball(0.0118, 2), "secondary", xform((side * 0.024, 0, 0.024)))
                put(ball(0.0072, 2), "accent", xform((side * 0.024, -0.005, 0.024)))
        elif kind == "cat":
            for side in (-1, 1):
                put(cone(0.012, 0.026, 4), "secondary", xform((side * 0.019, 0, 0.018), (0, side * 18, 0)))
                put(cone(0.0065, 0.016, 4), "accent", xform((side * 0.019, -0.005, 0.02), (0, side * 18, 0)))
        elif kind == "pig":
            for side in (-1, 1):
                put(cone(0.0105, 0.018, 4), "accent", xform((side * 0.021, 0, 0.018), (0, side * 42, 0)))
            put(ball(0.0115, 2), "accent", xform((0, -0.026, -0.005), scale=(1.15, 0.5, 0.86)))
        for side in (-1, 1):
            put(ball(0.0054, 2), "grip_dark", xform((side * 0.012, -0.0268, 0.005)))
            put(ball(0.0017, 1), "glow", xform((side * 0.0102, -0.0316, 0.0072)))
            put(ball(0.0048, 1), "accent", xform((side * 0.0192, -0.0235, -0.006), scale=(1.1, 0.42, 0.7)))
        if kind != "pig":
            put(ball(0.0026, 1), "grip_dark", xform((0, -0.0294, -0.0012), scale=(1.3, 0.8, 0.9)))

    def bow(self, m, size=0.018):
        self.put(shape2d(motif_loops("bow"), 0.0032, 0.0008), "accent", m @ Matrix.Diagonal((size, size, 1.0, 1.0)))
        # Hanging ribbon tails
        for sx in (-1, 1):
            tail = [
                (sx * size * 0.15, 0, -size * 0.1),
                (sx * size * 0.48, -0.0015, -size * 0.65),
                (sx * size * 0.62, 0.001, -size * 1.18),
            ]
            self.put(tube(tail, size * 0.16, 4, flat=0.28, taper=lambda u: 0.85 + 0.25 * u), "accent", m)

    def wings(self, z, size=0.05):
        for side in (-1, 1):
            m = Matrix.Translation((side * 0.008, 0, z)) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Diagonal((side * size, size, 1.0, 1.0))
            self.put(shape2d(motif_loops("wing"), 0.0026, 0.0008), "secondary", m)
            m_inner = Matrix.Translation((side * 0.009, -0.001, z + 0.002)) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Diagonal((side * size * 0.72, size * 0.72, 1.0, 1.0))
            self.put(shape2d(motif_loops("wing"), 0.0032, 0.0006), "accent", m_inner)

    def charm(self, x, z, length=0.04):
        kind = self.style["charm"]
        if kind == "none":
            return
        pts = [(x, 0, z), (x + 0.006, 0, z - length * 0.5), (x + 0.004, 0, z - length)]
        for p, t in along([Vector(p) for p in pts], 0.0055):
            self.put(torus(0.0026, 0.0007, 6, 3), "accent", Matrix.Translation(p) @ t.to_track_quat("X", "Z").to_matrix().to_4x4())
        tip = (x + 0.004, 0, z - length - 0.012)
        if kind == "tag":
            self.put(shape2d([[(-0.7, 1), (0.7, 1), (0.7, -1), (-0.7, -1)], [(-0.2, 0.86), (0.2, 0.86), (0.2, 0.62), (-0.2, 0.62)]], 0.0009, 0.0004), "secondary", facing(tip, (0, -1, 0), 0.014))
        else:
            self.put(shape2d(motif_loops({"cross": "cross", "heart": "heart", "star": "star5"}.get(kind, "star5")), 0.0016, 0.0006), "accent", facing(tip, (0, -1, 0), 0.0125))

    def cap(self, rfn, z):
        kind = self.style["cap"]
        if kind in ("ring", "drip"):
            self.ring("metal", rfn, z + 0.02, 0.0028)
        elif kind == "claw":
            for i in range(3):
                a = i / 3 * TAU
                self.put(cone(0.0058, 0.034, 5), "metal", xform((0.012 * math.cos(a), 0.012 * math.sin(a), z + 0.002), (180 + 22 * math.sin(a), 22 * math.cos(a), 0)))
        elif kind == "gem":
            self.put(ball(0.0115, 1), "accent", xform((0, 0, z - 0.006), scale=(1.0, 1.0, 1.25)))
        elif kind == "mascot":
            self.mascot(xform((0, 0, z - 0.012), scale=0.52) @ Matrix.Rotation(math.pi, 4, "Y"))
        elif kind == "dragon":
            self.dragon_head(xform((0, 0, z - 0.005), (180, 0, 0)), scale=0.026, key=self.style.get("wrap_key", "metal"))

    def topper(self, z, rfn):
        kind = self.style["topper"]
        if kind == "mascot":
            self.mascot(xform((0, 0, z + 0.022), scale=0.82))
        elif kind == "wings":
            self.wings(z - 0.02, 0.058)
            self.put(ball(0.0125, 2), "accent", xform((0, 0, z + 0.008)))
        elif kind == "shell":
            self.put(shape2d(motif_loops("shell"), 0.0035, 0.0008), "metal", facing((0, 0, z + 0.026), (0, -1, 0), 0.036))
            self.put(ball(0.0078, 2), "secondary", xform((0, 0, z + 0.01)))
        elif kind == "dragon":
            self.dragon_head(xform((0, 0, z + 0.008)), scale=0.032, key=self.style.get("wrap_key", "metal"))

    def decorate_long(self, rfn, z0, z1):
        s = self.style
        span = z1 - z0
        self.wrap(rfn, z0, z1)
        if s["cap"] == "drip":
            self.drips(s.get("drip_key", "secondary"), rfn, z1, 11, min(0.12, span * 0.4))
        if s["motif"] != "none":
            for u in (0.22, 0.5, 0.78):
                for a in (-TAU / 4, TAU / 4):
                    self.badge_on_shaft(s["motif"], "accent", rfn, z0 + span * u, a, max(0.0095, rfn(z0 + span * u) * 0.72))
        if s.get("lace"):
            self.lace("secondary", rfn, z1 - span * 0.02)
            self.lace("secondary", rfn, z0 + span * 0.02)
        if s.get("stones"):
            for u in (0.04, 0.96):
                self.stones("metal", rfn, z0 + span * u)
        if s.get("bands"):
            for u in (0.36, 0.4, 0.44):
                self.put(lathe([(rfn(z0 + span * u) + 0.0006, z0 + span * u), (rfn(z0 + span * u) + 0.0006, z0 + span * (u + 0.018))], 16), "secondary")
        if s.get("vents"):
            for i in range(6):
                z = z0 + span * 0.08 + i * 0.0075
                self.put(box(0.0012, rfn(z) * 0.9, 0.0034), "grip", xform((rfn(z), 0, z)))
        if s.get("glowlines"):
            for a in (0.0, math.pi):
                r = rfn(z0) + 0.0005
                self.put(box(0.0014, 0.0026, span * 0.8), "glow", xform((r * math.cos(a), r * math.sin(a), z0 + span * 0.5)))
        if s.get("stickers"):
            names = ["star5", "heart", "paw", "bars", "bolt", "x_face"]
            for i in range(9):
                u = 0.06 + i * 0.1
                a = self.rng.uniform(0, TAU)
                self.badge_on_shaft(self.rng.choice(names), self.rng.choice(["accent", "secondary", "glow", "metal"]), rfn, z0 + span * u, a, rfn(z0 + span * u) * 0.75)

    def edge_points(self, kind, length, width, z0):
        hw = width * 0.5
        if kind == "spear":
            pts = [(-hw, z0), (-hw * 0.95, z0 + length * 0.7)] + sharp((0, z0 + length)) + [(hw * 0.95, z0 + length * 0.7), (hw, z0)]
            return chaikin(pts, 2)
        if kind == "tanto":
            return [(-hw * 0.8, z0), (-hw * 0.8, z0 + length * 0.95), (0.0, z0 + length), (hw, z0 + length * 0.72), (hw, z0)]
        if kind == "kris":
            pts = []
            n = 6
            for i in range(n + 1):
                u = i / n
                pts.append((-hw * (1 - u * 0.7) + math.sin(u * TAU * 1.5) * width * 0.16, z0 + length * u * 0.96))
            pts += sharp((width * 0.08, z0 + length))
            for i in range(n, -1, -1):
                u = i / n
                pts.append((hw * (1 - u * 0.7) + math.sin(u * TAU * 1.5) * width * 0.16, z0 + length * u * 0.96))
            return chaikin(pts, 2)
        if kind == "bolt":
            return [(-hw, z0), (-hw * 0.2, z0 + length * 0.36), (-hw * 1.1, z0 + length * 0.42), (hw * 0.1, z0 + length), (hw * 0.25, z0 + length * 0.6), (hw * 1.15, z0 + length * 0.54), (hw, z0)]
        if kind == "pixel":
            grid = width / 6.0
            steps = max(5, int(length / grid))
            left, right = [], []
            for i in range(steps):
                u = i / steps
                half = hw * (1.0 if u < 0.5 else max(0.2, 1.0 - (u - 0.5) * 1.7))
                snapped = max(grid, round(half / grid) * grid)
                z = z0 + grid * i
                z2 = z0 + grid * (i + 1)
                left += [(-snapped, z), (-snapped, z2)]
                right = [(snapped, z2), (snapped, z)] + right
            return left + right
        if kind == "scythe":
            pts = [(-hw * 0.5, z0), (-hw * 1.0, z0 + length * 0.4), (-hw * 0.2, z0 + length * 0.85)] + sharp((hw * 1.5, z0 + length)) + [(hw * 0.5, z0 + length * 0.66), (hw * 0.45, z0 + length * 0.3), (hw * 0.7, z0)]
            return chaikin(pts, 2)
        if kind == "cleaver":
            pts = sharp((-hw * 0.7, z0)) + sharp((-hw * 0.7, z0 + length * 0.86)) + [(-hw * 0.5, z0 + length * 0.94)] + sharp((hw * 0.12, z0 + length)) + [(hw * 0.92, z0 + length * 0.9), (hw * 1.08, z0 + length * 0.62), (hw * 0.92, z0 + length * 0.26)] + sharp((hw * 0.66, z0))
            return chaikin(pts, 2)
        spine = sharp((-hw * 0.72, z0))
        if self.style.get("serrate"):
            teeth = 8
            start, end = z0 + length * 0.1, z0 + length * 0.56
            step = (end - start) / teeth
            for i in range(teeth):
                z = start + step * i
                spine += sharp((-hw * 0.72, z)) + sharp((-hw * 1.04, z + step * 0.22)) + sharp((-hw * 0.68, z + step * 0.58))
        spine += sharp((-hw * 0.72, z0 + length * 0.62)) + [(-hw * 0.48, z0 + length * 0.74), (-hw * 0.18, z0 + length * 0.84)]
        pts = spine + sharp((hw * 0.34, z0 + length)) + [(hw * 0.86, z0 + length * 0.78), (hw, z0 + length * 0.5), (hw * 0.98, z0 + length * 0.2)] + sharp((hw * 0.82, z0))
        return chaikin(pts, 2)

    def blade(self, length, width, z0=0.02, thick=0.0032, kind=None):
        """Build a multi-layered 3D beveled blade with razor edge, shinogi ridge, spine & fuller groove."""
        s = self.style
        kind = kind or s["blade"]
        outline = self.edge_points(kind, length, width, z0)
        to_xz = xform(rot=(90, 0, 0))
        # Outer razor cutting edge bevel (thin, sharp chamfer)
        self.put(shape2d([outline], thick * 0.22, thick * 0.55, bevel_res=2), "metal" if s["finish"]["primary"] == "matte" else "primary", to_xz)
        # Mid shinogi bevel body
        self.put(shape2d([outline], thick * 0.88, thick * 0.28, bevel_res=1, inset=width * 0.065), "primary", to_xz)
        # Raised spine / core plate
        self.put(shape2d([outline], thick * 1.18, thick * 0.12, bevel_res=1, inset=width * 0.14), "secondary", to_xz)
        half = thick * 1.30
        # Recessed fuller / blood groove ridge lines along both blade faces
        if kind != "pixel":
            for side in (-1, 1):
                y_pos = side * (half + 0.0004)
                fuller_key = "glow" if s.get("glowlines") else "metal"
                self.put(box(width * 0.045, 0.0012, length * 0.56, 0.0004), fuller_key, xform((-width * 0.12, y_pos, z0 + length * 0.36)))
                self.put(box(width * 0.018, 0.0016, length * 0.54), "grip_dark", xform((-width * 0.12, y_pos, z0 + length * 0.36)))
        if s.get("glowlines"):
            self.put(box(width * 0.04, thick * 1.55, length * 0.66), "glow", xform((width * 0.06, 0, z0 + length * 0.42)))
        if s.get("vents"):
            for i in range(5):
                self.put(box(width * 0.28, thick * 1.7, 0.0035, 0.0005), "grip", xform((-width * 0.08, 0, z0 + length * 0.1 + i * 0.009)))
        if s["motif"] != "none":
            for u, scale in ((0.18, 0.2), (0.42, 0.26)):
                self.badge_on_face(s["motif"], "accent", 0.0, z0 + length * u, half, width * scale)
        if s["wrap"] in ("chain", "thorn", "ribbon", "bone", "bolt", "rope", "scale", "dragon"):
            flat = lambda z: width * 0.46
            self.wrap(flat, z0 + length * 0.1, z0 + length * 0.44)
        if s.get("lace"):
            for i in range(9):
                self.put(torus(width * 0.05, 0.0008, 8, 4), "accent", facing((-width * 0.28, half, z0 + length * (0.14 + i * 0.05)), (0, 1, 0)))
                self.put(torus(width * 0.05, 0.0008, 8, 4), "accent", facing((-width * 0.28, -half, z0 + length * (0.14 + i * 0.05)), (0, -1, 0)))
        return half

    def handle(self, z_bottom, z_top, radius, guard=True):
        """Sculpted ergonomic grip with finger scallops, bolster collar, crossguard, and pommel."""
        span = z_top - z_bottom
        steps = 16
        pts = []
        sizes = []
        for i in range(steps + 1):
            u = i / steps
            z = z_bottom + span * u
            # Ergonomic finger grooves on front (+X) and palm swell on back (-X)
            groove = -0.0014 * math.sin(u * math.pi * 4.0) ** 2 if 0.12 < u < 0.88 else 0.0
            swell = 0.0018 * math.sin(u * math.pi)
            flare = 0.0025 * (1.0 - u) ** 3 + 0.0015 * u ** 3
            rx = radius * 1.05 + swell + groove + flare
            ry = radius * 0.82 + swell * 0.5 + flare * 0.6
            x_off = groove * 0.6 - 0.0012 * (1.0 - u) ** 2
            pts.append((x_off, 0.0, z))
            sizes.append((rx, ry))
        self.put(loft(pts, (1, 0, 0), sizes, seg=16), "grip")
        # Ribbed grip bands
        for u in (0.22, 0.44, 0.66, 0.84):
            z = z_bottom + span * u
            self.put(torus(radius * 1.04, 0.0011, 16, 4), "accent", xform((0, 0, z), scale=(1.05, 0.84, 1.0)))
        # Pommel cap & lanyard ring
        self.put(lathe([(radius * 1.34, z_bottom - 0.014), (radius * 1.38, z_bottom - 0.002), (radius * 1.18, z_bottom + 0.005)], 14), "metal", xform(scale=(1.06, 0.84, 1.0)))
        self.put(torus(radius * 0.72, 0.0022, 14, 5), "metal", xform((0, 0, z_bottom - 0.020), (90, 0, 0)))
        if guard:
            s = self.style
            # Sculpted multi-tier crossguard with swept quillons
            self.put(box(radius * 5.2, radius * 2.1, 0.0085, 0.0018), "metal", xform((0, 0, z_top + 0.002)))
            self.put(box(radius * 3.4, radius * 2.35, 0.012, 0.0016), "secondary", xform((0, 0, z_top + 0.007)))
            for sx in (-1, 1):
                self.put(cone(0.0042, 0.018, 5), "metal", xform((sx * radius * 2.5, 0, z_top + 0.002), (0, sx * 72, 0)))
            if s["motif"] != "none":
                self.badge_on_face(s["motif"], "accent", 0.0, z_top + 0.005, radius * 1.22, radius * 1.1)
        self.cap(lambda z: radius * 1.02, z_bottom - 0.014)


def build_poolcue(f):
    s = f.style
    z0, z1 = -0.15, 0.75
    rfn = lambda z: 0.0205 + (0.0125 - 0.0205) * (z - z0) / (z1 - z0)
    f.put(lathe([(0.018, z0), (rfn(z0) + 0.005, z0), (rfn(z0) + 0.005, z0 + 0.024), (rfn(z0 + 0.03), z0 + 0.03)], 18), "metal")
    f.put(lathe([(rfn(z0 + 0.03), z0 + 0.03), (rfn(z0 + 0.24), z0 + 0.24)], 18), "grip")
    f.put(lathe([(rfn(0.09) + 0.0028, 0.09), (rfn(0.104) + 0.0028, 0.104)], 18), "metal")
    f.put(lathe([(rfn(0.104), 0.104), (rfn(0.42), 0.42)], 18), "primary")
    f.put(lathe([(rfn(0.42) + 0.0022, 0.42), (rfn(0.436) + 0.0022, 0.436)], 18), "accent")
    f.put(lathe([(rfn(0.436), 0.436), (rfn(0.72), 0.72)], 18), "secondary" if s["finish"]["secondary"] != "matte" else "primary")
    f.put(lathe([(rfn(0.72) + 0.0014, 0.72), (rfn(0.745) + 0.0014, 0.745), (rfn(0.75), z1), (0.006, z1 + 0.002)], 16), "metal")
    f.decorate_long(rfn, 0.13, 0.7)
    f.cap(rfn, z0)
    f.topper(z1, rfn)
    f.charm(rfn(0.095) + 0.006, 0.09)
    if s.get("bow"):
        f.bow(facing((0, -rfn(0.1) - 0.003, 0.098), (0, -1, 0)), 0.022)


def build_bat(f):
    s = f.style
    z0, z1 = -0.14, 0.67
    def rfn(z):
        u = (z - z0) / (z1 - z0)
        return 0.0135 + (0.0345 - 0.0135) * min(1.0, max(0.0, (u - 0.28) / 0.46)) ** 1.5
    f.put(lathe([(0.012, z0), (0.0215, z0), (0.022, z0 + 0.012), (rfn(z0 + 0.02), z0 + 0.02)], 18), "metal")
    f.put(lathe([(rfn(z0 + 0.02), z0 + 0.02), (rfn(z0 + 0.2), z0 + 0.2)], 18), "grip")
    prof = [(rfn(z), z) for z in [z0 + 0.2 + i * (z1 - z0 - 0.21) / 14 for i in range(15)]]
    prof += [(0.031, z1 - 0.004), (0.022, z1)]
    f.put(lathe(prof, 20), "primary")
    f.ring("accent", rfn, z0 + 0.204, 0.0032)
    f.decorate_long(rfn, z0 + 0.24, z1 - 0.03)
    f.cap(rfn, z0)
    f.topper(z1, rfn)
    if s.get("bow"):
        f.bow(facing((0, -rfn(0.08) - 0.003, 0.08), (0, -1, 0)), 0.022)


def build_bottle(f):
    s = f.style
    btype = s.get("bottle_type", "bottle")
    if btype == "katana":
        oni_katana(f)
        return
    if btype == "scepter":
        z0, z1 = -0.10, 0.28
        rfn = lambda z: 0.0095 + 0.002 * math.sin((z - z0) / (z1 - z0) * math.pi)
        f.put(lathe([(0.006, z0 - 0.015), (0.013, z0), (0.011, z0 + 0.018), (rfn(z0 + 0.02), z0 + 0.02)], 16), "metal")
        f.put(lathe([(rfn(z0 + 0.02), z0 + 0.02), (rfn(0.06), 0.06)], 16), "grip")
        f.put(lathe([(rfn(0.06), 0.06), (rfn(0.16), 0.16)], 16), "primary")
        f.wrap(rfn, z0 + 0.025, 0.155)
        for zc in (0.02, 0.062, 0.158):
            f.ring("metal", rfn, zc, 0.0032)
        key_bit = [(-0.010, z0 + 0.004), (-0.028, z0 + 0.004), (-0.028, z0 + 0.026), (-0.019, z0 + 0.026), (-0.019, z0 + 0.015), (-0.010, z0 + 0.015)]
        f.put(shape2d([key_bit], 0.0024, 0.0006), "metal", xform(rot=(90, 0, 0)))
        cz = 0.215
        f.put(torus(0.038, 0.0042, 28, 8), "metal", xform((0, 0, cz), (90, 0, 0)))
        f.put(torus(0.032, 0.0022, 24, 6), "glow", xform((0, 0, cz), (90, 0, 0)))
        f.badge(s["motif"] if s["motif"] != "none" else "heart", "accent", xform((0, 0, cz), (90, 0, 0), (0.028, 0.028, 1.8)))
        f.wings(cz, 0.044)
        for sx in (-1, 1):
            scroll = [
                Vector((sx * 0.011, 0, 0.162)),
                Vector((sx * 0.036, 0, 0.172)),
                Vector((sx * 0.046, 0, 0.198)),
                Vector((sx * 0.032, 0, 0.212)),
            ]
            f.put(tube(scroll, 0.0028, 6, taper=lambda u: 1.0 - 0.35 * u), "metal")
        f.put(ball(0.0075, 2), "glow", xform((0, 0, z1 - 0.005)))
        f.put(cone(0.006, 0.018, 6), "metal", xform((0, 0, z1)))
        if s.get("bow"):
            f.bow(facing((0, -0.014, 0.158), (0, -1, 0)), 0.024)
        f.charm(0.018, 0.018, 0.034)
        return
    if btype == "balisong":
        to_xz = xform(rot=(90, 0, 0))
        b_len, b_w, z_pivot = 0.165, 0.024, 0.045
        f.blade(b_len, b_w, z_pivot, 0.0026, override="spear")
        f.put(box(0.032, 0.010, 0.012, 0.0018), "metal", xform((0, 0, z_pivot - 0.004)))
        for sx in (-1, 1):
            hx = sx * 0.0105
            tilt = sx * 3.5
            h_mat = xform((hx, 0, z_pivot - 0.002), (0, tilt, 0))
            f.put(box(0.0115, 0.0118, 0.135, 0.0022), "primary", h_mat @ xform((0, 0, -0.068)))
            f.put(box(0.0085, 0.0128, 0.125, 0.0012), "secondary", h_mat @ xform((0, 0, -0.068)))
            for k in range(4):
                sz = -0.024 - k * 0.026
                f.put(box(0.0045, 0.0136, 0.014, 0.0008), "glow" if s.get("glowlines") else "metal", h_mat @ xform((0, 0, sz)))
            f.put(lathe([(0.0042, -0.007), (0.0042, 0.007)], 12), "metal", h_mat @ xform(rot=(90, 0, 0)))
            f.put(lathe([(0.0028, -0.0075), (0.0028, 0.0075)], 10), "accent", h_mat @ xform(rot=(90, 0, 0)))
        f.put(box(0.018, 0.006, 0.008, 0.0012), "metal", xform((0.006, 0, z_pivot - 0.142)))
        f.charm(0.018, z_pivot - 0.14, 0.032)
        return
    if btype == "war_pick":
        z0, z1 = -0.10, 0.26
        rfn = lambda z: 0.0125 + 0.002 * math.sin((z - z0) / (z1 - z0) * math.pi)
        f.put(lathe([(0.010, z0), (0.016, z0 + 0.01), (rfn(z0 + 0.02), z0 + 0.02)], 16), "metal")
        f.put(lathe([(rfn(z0 + 0.02), z0 + 0.02), (rfn(0.12), 0.12)], 16), "grip")
        f.put(lathe([(rfn(0.12), 0.12), (rfn(z1 - 0.03), z1 - 0.03)], 16), "primary")
        f.wrap(rfn, z0 + 0.025, 0.19)
        f.dragon_head(xform((0, 0, z1 - 0.025), (-20, 0, 0)), 0.024, "metal")
        pick_pts = [
            Vector((0, -0.01, z1 - 0.015)),
            Vector((0, -0.045, z1 + 0.01)),
            Vector((0, -0.095, z1 - 0.005)),
            Vector((0, -0.135, z1 - 0.045)),
        ]
        f.put(tube(pick_pts, 0.012, 6, taper=lambda u: 1.0 - 0.88 * u, flat=0.38), "metal")
        f.put(tube(pick_pts, 0.006, 4, taper=lambda u: 1.0 - 0.92 * u, flat=0.25), "glow", xform((0, -0.004, 0)))
        rear_spike = [Vector((0, 0.01, z1 - 0.015)), Vector((0, 0.045, z1 - 0.002)), Vector((0, 0.072, z1 - 0.022))]
        f.put(tube(rear_spike, 0.0085, 6, taper=lambda u: 1.0 - 0.88 * u, flat=0.4), "accent")
        f.cap(rfn, z0)
        f.charm(0.018, z0 + 0.015, 0.034)
        return

    z0, z1 = -0.09, 0.28
    def rfn(z):
        if z < 0.02:
            return 0.0145
        u = (z - 0.02) / (z1 - 0.02)
        return 0.0145 + 0.024 * min(1.0, u * 2.1) ** 1.4
    f.put(lathe([(0.012, z0), (0.0195, z0), (0.0195, z0 + 0.012), (rfn(z0), z0 + 0.016)], 16), "metal")
    f.put(lathe([(rfn(z0), z0 + 0.016), (rfn(0.02), 0.02)], 16), "grip")
    prof = [(rfn(z), z) for z in [0.02 + i * (z1 - 0.06) / 12 for i in range(13)]]
    f.put(lathe(prof, 20), "primary")
    inner_prof = [(max(0.004, r * 0.78), z) for r, z in prof[1:-1]]
    f.put(lathe(inner_prof, 16), "glow" if s.get("glowlines") else "secondary")
    teeth = 9
    top = prof[-1][1]
    r = prof[-1][0]
    for i in range(teeth):
        a = i / teeth * TAU
        h = f.rng.uniform(0.022, 0.05)
        n = (math.cos(a), math.sin(a), 0.0)
        tri = [(-0.0098, 0.0), (0.0098, 0.0), (f.rng.uniform(-0.003, 0.003), h)]
        m = Matrix.Translation((n[0] * r, n[1] * r, top - 0.002)) @ Matrix.Rotation(a + math.pi / 2, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
        f.put(shape2d([tri], 0.0026, 0.0008), "metal", m)
    f.ring("accent", rfn, 0.022, 0.0034)
    f.ring("accent", rfn, top - 0.006, 0.003)
    f.decorate_long(rfn, 0.05, top - 0.012)
    f.cap(rfn, z0)
    if s.get("bow"):
        f.bow(facing((0, -rfn(0.024) - 0.003, 0.024), (0, -1, 0)), 0.02)
    f.charm(rfn(0.022) + 0.006, 0.018, 0.034)


def build_machete(f):
    half = f.blade(0.43, 0.085, 0.03, 0.0032, "cleaver" if f.style["blade"] in ("clip", "spear") else None)
    f.handle(-0.03, 0.025, 0.0125)
    f.charm(0.04, 0.02)
    if f.style.get("bow"):
        f.bow(facing((0, -half - 0.0065, 0.028), (0, -1, 0)), 0.024)


def build_knife(f):
    half = f.blade(0.24, 0.046, 0.03, 0.0028)
    f.handle(-0.03, 0.025, 0.0115)
    f.charm(0.026, 0.02, 0.032)
    if f.style.get("bow"):
        f.bow(facing((0, -half - 0.0065, 0.028), (0, -1, 0)), 0.018)


def build_knuckle(f):
    s = f.style
    ktype = s.get("knuckle_type", "standard")
    if ktype == "jaw_shield":
        oni_knuckle(f)
        return
    cz = [-0.052, -0.016, 0.02, 0.056]
    to_yz = Matrix.Translation((0.022, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "Z")

    if ktype == "blade_knuckle":
        outer = [
            (0.052, -0.072), (0.064, -0.038), (0.068, 0.0), (0.064, 0.038), (0.052, 0.074),
            (0.020, 0.092), (-0.032, 0.082), (-0.056, 0.048), (-0.058, -0.042), (-0.032, -0.080), (0.020, -0.090),
        ]
        plate_loops = [chaikin(outer, 2)] + [circle(0.0168, 22, 0.03, z) for z in cz]
        plate_loops.append([(-0.018, -0.052), (-0.004, -0.054), (-0.004, 0.056), (-0.018, 0.054)])
        f.put(shape2d(plate_loops, 0.0056, 0.0026), "primary", to_yz)
        f.put(shape2d([circle(0.0208, 22, 0.03, z) for z in cz] + [circle(0.0168, 22, 0.03, z) for z in cz], 0.0096), "metal", to_yz)
        f.put(shape2d([[(-0.046, -0.050), (-0.028, -0.052), (-0.028, 0.054), (-0.046, 0.050)]], 0.0102, 0.0014), "grip", to_yz)
        claw_outer = [
            (0.048, -0.088), (0.078, -0.068), (0.104, -0.028), (0.114, 0.018),
            (0.102, 0.066), (0.078, 0.112), (0.042, 0.138), (0.046, 0.088),
            (0.058, 0.042), (0.060, 0.0), (0.058, -0.042), (0.046, -0.074),
        ]
        f.put(shape2d([chaikin(claw_outer, 2)], 0.0022, 0.0024), "metal", to_yz)
        claw_core = [
            (0.052, -0.068), (0.076, -0.046), (0.092, 0.0), (0.084, 0.052),
            (0.056, 0.098), (0.052, 0.056), (0.054, 0.0), (0.052, -0.048),
        ]
        f.put(shape2d([chaikin(claw_core, 1)], 0.0068, 0.0012), "secondary", to_yz)
        if s.get("glowlines"):
            f.put(shape2d([chaikin(claw_core, 1)], 0.0074, 0.0, inset=0.004), "glow", to_yz)
        for sz in (-0.078, 0.082):
            f.put(cone(0.0055, 0.026, 5), "accent", xform((0.022, 0.056, sz), (-65 if sz < 0 else -115, 0, 0)))
        f.charm(0.022, -0.085, 0.03)
        return

    if ktype == "lace_fan":
        outer = []
        r_out = 0.026
        for z in cz:
            outer.append((0.03 + r_out, z - r_out * 0.6))
            outer.append((0.03 + r_out * 1.18, z))
            outer.append((0.03 + r_out, z + r_out * 0.6))
        outer += [(0.022, 0.088), (-0.028, 0.080), (-0.054, 0.048), (-0.054, -0.048), (-0.028, -0.080), (0.022, -0.088)]
        plate_loops = [chaikin(outer, 2)] + [circle(0.0172, 22, 0.03, z) for z in cz]
        f.put(shape2d(plate_loops, 0.0052, 0.0024), "primary", to_yz)
        f.put(shape2d([circle(0.0212, 22, 0.03, z) for z in cz] + [circle(0.0172, 22, 0.03, z) for z in cz], 0.0094), "metal", to_yz)
        fan_pts = []
        pleats = 18
        for i in range(pleats + 1):
            a = -0.95 + 1.90 * (i / pleats)
            rad = 0.092 if i % 2 == 0 else 0.082
            fan_pts.append((0.018 + rad * math.cos(a), rad * math.sin(a)))
        for i in range(pleats, -1, -1):
            a = -0.95 + 1.90 * (i / pleats)
            fan_pts.append((0.018 + 0.046 * math.cos(a), 0.046 * math.sin(a)))
        f.put(shape2d([chaikin(fan_pts, 1)], 0.0032, 0.0012), "secondary", to_yz)
        lace_trim = []
        for i in range(pleats + 1):
            a = -0.95 + 1.90 * (i / pleats)
            rad = 0.097 if i % 2 == 0 else 0.089
            lace_trim.append((0.018 + rad * math.cos(a), rad * math.sin(a)))
        for i in range(pleats, -1, -1):
            a = -0.95 + 1.90 * (i / pleats)
            lace_trim.append((0.018 + 0.082 * math.cos(a), 0.082 * math.sin(a)))
        f.put(shape2d([chaikin(lace_trim, 1)], 0.0042, 0.0008), "metal", to_yz)
        for sign in (-1, 1):
            f.badge("heart", "accent", Matrix.Translation((0.022 + sign * 0.0075, 0.068, 0.0)) @ Vector((sign, 0, 0)).to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.022, 0.022, 1.4, 1.0)))
        f.bow(Matrix.Translation((0.032, 0.052, 0.0)) @ Vector((1, 0, 0)).to_track_quat("Z", "Y").to_matrix().to_4x4(), 0.028)
        f.charm(0.022, -0.085, 0.03)
        return

    outer = []
    r_out = 0.0262
    for z in cz:
        outer.append((0.03 + r_out, z - r_out * 0.6))
        outer.append((0.03 + r_out * 1.18, z))
        outer.append((0.03 + r_out, z + r_out * 0.6))
    outer += [(0.022, 0.09), (-0.03, 0.082), (-0.056, 0.05), (-0.058, -0.04), (-0.03, -0.08), (0.022, -0.09)]
    plate_loops = [chaikin(outer, 2)]
    plate_loops += [circle(0.0178, 22, 0.03, z) for z in cz]
    plate_loops.append([(-0.0165, -0.056), (-0.0035, -0.058), (-0.0035, 0.06), (-0.0165, 0.058)])
    f.put(shape2d(plate_loops, 0.0054, 0.0028), "primary", to_yz)
    f.put(shape2d([circle(0.0219, 22, 0.03, z) for z in cz] + [circle(0.0178, 22, 0.03, z) for z in cz], 0.0098), "metal", to_yz)
    f.put(shape2d([[(-0.044, -0.05), (-0.0274, -0.052), (-0.0274, 0.054), (-0.044, 0.05)]], 0.0098, 0.0014), "grip", to_yz)
    for z in cz:
        f.put(cone(0.0055, 0.012, 6), "metal", xform((0.022, 0.062, z), (-90, 0, 0)))
    if s["motif"] != "none":
        for sign in (-1, 1):
            for z in (-0.04, 0.04):
                f.badge(s["motif"], "accent", Matrix.Translation((0.022 + sign * 0.0084, 0.0, z)) @ Vector((sign, 0, 0)).to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.009, 0.009, 1.0, 1.0)))
    if s["wrap"] == "thorn" or s["cap"] == "claw" or s["blade"] in ("scythe", "bolt"):
        hook = sharp((-0.05, 0.07)) + [(-0.066, 0.118)] + sharp((-0.018, 0.17)) + [(-0.032, 0.126), (-0.012, 0.102)] + sharp((0.024, 0.088))
        f.put(shape2d([chaikin(hook, 2)], 0.0026, 0.0024), "accent", to_yz)
    if s.get("stones"):
        for i in range(9):
            f.put(ball(0.0019, 1), "metal", xform((0.0326, 0.0598, -0.052 + i * 0.0135)))
    if s["topper"] == "mascot":
        for z in cz:
            f.mascot(Matrix.Translation((0.022, 0.0655, z)) @ xform(scale=0.42) @ Matrix.Rotation(math.radians(-90), 4, "X") @ Matrix.Rotation(math.radians(-90), 4, "Z") @ Matrix.Rotation(math.radians(180), 4, "Z"))
    if s["wrap"] == "chain":
        pts = [Vector((0.022, 0.066 + 0.008 * math.sin(i * 0.6), -0.08 + i * 0.008)) for i in range(21)]
        for i, (p, t) in enumerate(along(pts, 0.0118)):
            f.put(torus(0.0062, 0.0015, 10, 4), "accent", Matrix.Translation(p) @ t.to_track_quat("X", "Z").to_matrix().to_4x4() @ Matrix.Rotation(math.radians(90 * (i % 2)), 4, "X") @ Matrix.Diagonal((1.25, 0.8, 1.0, 1.0)))
    if s.get("bow"):
        f.bow(Matrix.Translation((0.0335, -0.012, 0.012)) @ Vector((1, 0, 0)).to_track_quat("Z", "Y").to_matrix().to_4x4(), 0.024)
    f.charm(-0.03 + 0.05, -0.08, 0.03)


def build_revolver(f):
    s = f.style
    to_xz = xform(rot=(90, 0, 0))
    slide = sharp((-0.098, 0.012)) + sharp((-0.102, 0.050)) + [(-0.090, 0.064)] + sharp((0.174, 0.064)) + [(0.188, 0.056)] + sharp((0.192, 0.012))
    f.put(shape2d([chaikin(slide, 1)], 0.0092, 0.0032), "primary", to_xz)
    top_rib = [(-0.086, 0.058), (0.168, 0.058), (0.178, 0.066), (-0.082, 0.066)]
    f.put(shape2d([top_rib], 0.0052, 0.0016), "metal", to_xz)
    f.put(box(0.044, 0.0195, 0.014, 0.0012), "grip_dark", xform((0.024, 0.0035, 0.052)))
    comp = [(0.190, 0.010), (0.224, 0.014), (0.232, 0.054), (0.218, 0.064), (0.188, 0.064)]
    f.put(shape2d([chaikin(comp, 1)], 0.0096, 0.0022), "metal", to_xz)
    frame = (
        sharp((-0.094, 0.015)) + sharp((0.168, 0.015)) + sharp((0.164, -0.012))
        + [(0.074, -0.017), (0.070, -0.052), (0.056, -0.066), (-0.004, -0.067), (-0.018, -0.050), (-0.026, -0.030), (-0.056, -0.122)]
        + sharp((-0.104, -0.125)) + [(-0.098, -0.050), (-0.086, -0.020), (-0.114, 0.002)] + sharp((-0.094, 0.015))
    )
    guard_hole = chaikin([(-0.008, -0.021), (0.058, -0.019), (0.058, -0.050), (0.048, -0.056), (0.0, -0.058), (-0.010, -0.046)], 2)
    f.put(shape2d([chaikin(frame, 2), guard_hole], 0.0076, 0.0026), "secondary", to_xz)
    for k in range(5):
        rx = 0.088 + k * 0.015
        f.put(box(0.007, 0.0185, 0.0045, 0.0008), "metal", xform((rx, 0, -0.013)))
    f.put(shape2d([chaikin([(0.022, -0.020), (0.014, -0.044), (0.020, -0.050), (0.032, -0.022)], 1)], 0.0024, 0.0006), "accent", to_xz)
    hammer = [(-0.098, 0.046), (-0.122, 0.058), (-0.116, 0.038), (-0.096, 0.026)]
    f.put(shape2d([chaikin(hammer, 1)], 0.0032, 0.0008), "metal", to_xz)
    panel = chaikin(sharp((-0.083, -0.030)) + [(-0.097, -0.112)] + sharp((-0.060, -0.114)) + sharp((-0.036, -0.030)), 1)
    f.put(shape2d([panel], 0.0118, 0.0018), "grip", to_xz)
    f.put(box(0.060, 0.0252, 0.011, 0.0022), "metal", xform((-0.080, 0, -0.1255), (0, -7, 0)))
    axis = Matrix.Rotation(math.radians(90), 4, "Y")
    f.put(lathe([(0.0086, 0.186), (0.0096, 0.236), (0.0118, 0.238), (0.0118, 0.248), (0.0052, 0.248), (0.0052, 0.230)], 18), "metal", Matrix.Translation((0, 0, 0.039)) @ axis)
    for i in range(7):
        f.put(box(0.0034, 0.0222, 0.028, 0.0006), "grip", xform((-0.088 + i * 0.0072, 0, 0.038), (0, 12, 0)))
    for i in range(4):
        f.put(box(0.0034, 0.0222, 0.024, 0.0006), "grip", xform((0.125 + i * 0.0076, 0, 0.038), (0, 12, 0)))
    f.put(box(0.011, 0.014, 0.0095, 0.0012), "metal", xform((-0.082, 0, 0.068)))
    f.put(box(0.0025, 0.009, 0.0045), "glow", xform((-0.087, 0, 0.070)))
    f.put(box(0.0085, 0.0042, 0.0095, 0.0010), "metal", xform((0.168, 0, 0.068)))
    f.put(ball(0.0018, 1), "glow", xform((0.165, 0, 0.071)))
    if s.get("optic"):
        f.put(box(0.042, 0.022, 0.006, 0.0012), "metal", xform((-0.032, 0, 0.068)))
        hood = [(-0.018, 0.0), (-0.018, 0.022), (-0.012, 0.028), (0.012, 0.028), (0.018, 0.022), (0.018, 0.0), (0.014, 0.0), (0.014, 0.020), (0.009, 0.024), (-0.009, 0.024), (-0.014, 0.020), (-0.014, 0.0)]
        f.put(shape2d([hood], 0.014, 0.0012), "metal", xform((-0.032, 0, 0.070), (90, 0, 90)))
        f.put(box(0.0018, 0.024, 0.019), "glow", xform((-0.024, 0, 0.081)))
    if s.get("tac_light"):
        f.put(box(0.056, 0.021, 0.018, 0.0024), "metal", xform((0.125, 0, -0.024)))
        f.put(lathe([(0.0085, 0.150), (0.0102, 0.166), (0.0092, 0.168)], 16), "metal", Matrix.Translation((0, 0, -0.024)) @ axis)
        f.put(lathe([(0.0, 0.167), (0.0082, 0.167)], 16), "glow", Matrix.Translation((0, 0, -0.024)) @ axis)
    if s.get("dragon_slide"):
        f.dragon_head(xform((0.175, 0, 0.068), (-82, 0, 0)), 0.022, "accent")
        pts = [Vector((-0.075 + i * 0.014, 0.004 * math.sin(i * 0.9), 0.068 + 0.003 * math.cos(i * 0.9))) for i in range(18)]
        f.put(tube(pts, 0.0062, 8, taper=lambda u: 0.65 + 0.35 * math.sin(u * math.pi)), "accent")
    if s["motif"] != "none":
        f.badge_on_face(s["motif"], "accent", 0.112, 0.034, 0.0124, 0.0185)
        f.badge_on_face(s["motif"], "accent", -0.066, -0.074, 0.0138, 0.0165)
    if s["wrap"] in ("chain", "thorn", "rope", "ribbon", "bone", "bolt", "scale"):
        sub = Forge(s, f.rng)
        sub.wrap(lambda z: 0.0108, 0.08, 0.21)
        for key, bm in sub.parts.items():
            bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.039)) @ axis, verts=bm.verts)
            f.put(bm, key)
    if s.get("vents"):
        for i in range(5):
            f.put(box(0.0038, 0.0228, 0.028), "glow" if s.get("glowlines") else "grip", xform((0.085 + i * 0.0092, 0, 0.038), (0, 14, 0)))
    if s.get("glowlines"):
        for side in (-1, 1):
            f.put(box(0.128, 0.0014, 0.0034), "glow", xform((0.045, side * 0.0112, 0.014)))
            f.put(box(0.095, 0.0014, 0.0028), "glow", xform((0.035, side * 0.0115, 0.052)))
    if s["topper"] == "mascot":
        f.mascot(xform((0.07, 0, 0.088), scale=0.74))
    if s["topper"] == "wings" or s.get("wings_slide"):
        f.wings(0.075, 0.044)
        f.put(ball(0.009, 2), "accent", xform((0.0, 0, 0.075)))
    if s.get("stickers"):
        names = ["star5", "heart", "paw", "bars", "bolt"]
        for i in range(7):
            f.badge_on_face(f.rng.choice(names), f.rng.choice(["accent", "glow", "metal"]), -0.06 + i * 0.038, 0.03 + (i % 2) * 0.014, 0.0124, 0.0105)
    if s.get("bow"):
        f.bow(facing((-0.078, -0.0184, -0.112), (0, -1, 0)), 0.022)
    f.charm(0.054, -0.06, 0.03)


def aim(direction):
    d = Vector(direction).normalized()
    up = "X" if abs(d.y) > 0.9 else "Y"
    return d.to_track_quat("Z", up).to_matrix().to_4x4()


def basis_matrix(x_axis, y_axis, z_axis):
    return Matrix((
        (x_axis.x, y_axis.x, z_axis.x, 0.0),
        (x_axis.y, y_axis.y, z_axis.y, 0.0),
        (x_axis.z, y_axis.z, z_axis.z, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ))


def mask_matrix(center, face, up, size):
    y_axis = -Vector(face).normalized()
    z_axis = Vector(up).normalized()
    x_axis = y_axis.cross(z_axis).normalized()
    return Matrix.Translation(Vector(center)) @ basis_matrix(x_axis, y_axis, z_axis) @ Matrix.Diagonal((size, size, size, 1.0))


def coil(rfn, z0, z1, turns, phase=0.0, lift=0.0, per_turn=20):
    count = max(6, int(abs(turns) * per_turn))
    out = []
    for i in range(count + 1):
        u = i / count
        z = z0 + (z1 - z0) * u
        a = phase + turns * TAU * u
        r = rfn(z) + lift
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def lattice(f, rfn, z0, z1, turns, key, wire, lift, local=None):
    for sign in (1, -1):
        f.put(tube(coil(rfn, z0, z1, sign * turns, 0.0, lift), wire, 4), key, local)


def spike(f, base, direction, radius, height, key="metal", seg=5):
    f.put(cone(radius, height, seg), key, Matrix.Translation(Vector(base)) @ aim(direction))


def line_xz(f, a, b, y, w, key, h=0.0008):
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dz)
    if length < 1e-6:
        return
    m = Matrix.Translation(((a[0] + b[0]) / 2, y, (a[1] + b[1]) / 2)) @ Matrix.Rotation(-math.atan2(dz, dx), 4, "Y")
    f.put(box(length + w * 0.6, h, w), key, m)


def mirror_loop(right):
    return right + [(-x, y) for x, y in reversed(right[1:-1])]


ONI_FACE = [(0.0, 0.42), (0.18, 0.40), (0.33, 0.31), (0.43, 0.17), (0.50, 0.04), (0.58, -0.08), (0.45, -0.11), (0.40, -0.27), (0.27, -0.41), (0.12, -0.49), (0.0, -0.51)]
ONI_EYE = [(0.07, 0.07), (0.40, 0.22), (0.34, 0.06), (0.13, 0.0)]
ONI_BROW = [(0.05, 0.17), (0.47, 0.35), (0.47, 0.25), (0.05, 0.10)]
ONI_MOUTH = [(-0.30, -0.17), (0.30, -0.17), (0.27, -0.31), (0.13, -0.36), (-0.13, -0.36), (-0.27, -0.31)]


def loft(points, up_hint, sizes, seg=8):
    bm = bmesh.new()
    pts = [Vector(p) for p in points]
    last = len(pts) - 1
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, last)] - pts[max(i - 1, 0)]).normalized()
        hint = Vector(up_hint)
        up = (hint - t * hint.dot(t)).normalized()
        side = t.cross(up)
        rx, ry = sizes[i]
        rings.append([bm.verts.new(p + up * (math.cos(k / seg * TAU) * rx) + side * (math.sin(k / seg * TAU) * ry)) for k in range(seg)])
    for lower, upper in zip(rings, rings[1:]):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((lower[j], lower[k], upper[k], upper[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm


def horn(f, base, direction, length, radius, bend=(0, 0, 0), key="metal", seg=6):
    d = Vector(direction).normalized()
    b = Vector(base)
    bv = Vector(bend)
    pts = [b + d * length * (i / 6) + bv * (i / 6) ** 2 for i in range(7)]
    f.put(tube(pts, radius, seg, taper=lambda u: (1.0 - 0.90 * u) * (1.0 + 0.08 * math.sin(u * 22.0))), key)


def oni_mask(f, m, horns=True, black=False):
    flat = xform(rot=(90, 0, 0))
    face = "primary" if black else "metal"
    trim = "metal"

    def layer(loops, key, y, depth, bevel=0.0):
        f.put(shape2d(loops, depth, bevel), key, m @ Matrix.Translation((0, y, 0)) @ flat)

    def solid(bm, key, local):
        f.put(bm, key, m @ local)

    # Base sculpted face plate (front surface at y = -0.095)
    layer([mirror_loop(ONI_FACE)], face, 0.0, 0.055, 0.040)
    if black:
        layer([[(x * 1.08, y * 1.08 - 0.01) for x, y in mirror_loop(ONI_FACE)]], trim, 0.035, 0.045, 0.020)
    # 3D cheek & cranium volume domes (kept behind y = -0.095 so they never occlude eyes or brows)
    solid(ball(0.22, 2), face, xform((0.0, 0.01, 0.18), scale=(1.18, 0.38, 0.85)))
    for sx in (-1, 1):
        solid(ball(0.17, 2), face, xform((sx * 0.30, -0.02, -0.03), scale=(1.0, 0.45, 0.78)))
    solid(ball(0.14, 2), face, xform((0.0, -0.02, -0.36), scale=(1.1, 0.42, 0.68)))
    # Sculpted 3D nose bridge and nostrils projecting forward (y = -0.10 to -0.17)
    nose_pts = [Vector((0.0, -0.09, 0.16)), Vector((0.0, -0.14, 0.04)), Vector((0.0, -0.17, -0.05))]
    solid(tube(nose_pts, 0.052, 6, taper=lambda u: 0.65 + 0.50 * u), face, Matrix.Identity(4))
    for sx in (-1, 1):
        solid(ball(0.042, 1), face, xform((sx * 0.055, -0.13, -0.05), scale=(1.0, 0.75, 0.7)))
    # Heavy furrowed demon brows + forehead diamond crest (projecting to y = -0.155)
    layer([ONI_BROW], trim, -0.105, 0.042, 0.012)
    layer([[(-x, y) for x, y in ONI_BROW]], trim, -0.105, 0.042, 0.012)
    layer([[(-0.032, 0.27), (0.032, 0.27), (0.0, 0.41)]], "glow", -0.115, 0.025, 0.006)
    # Snarling mouth rim + recessed dark cavity
    outer = [(x * 1.18, y * 1.18 - 0.02) for x, y in ONI_MOUTH]
    layer([outer, ONI_MOUTH], trim, -0.105, 0.034, 0.010)
    layer([ONI_MOUTH], "grip_dark", -0.098, 0.018)
    # Glowing demon eyes with hot pupils (projecting to y = -0.138, clearly in front of face)
    for sx in (1, -1):
        eye = [(sx * x, y) for x, y in ONI_EYE]
        layer([eye], "glow", -0.108, 0.024, 0.005)
        layer([circle(0.044, 12, sx * 0.235, 0.095)], "hot", -0.118, 0.022)
    # 3D curved upper and lower fangs & tusks
    for x, r, h in ((0.25, 0.054, 0.22), (-0.25, 0.054, 0.22), (0.11, 0.036, 0.15), (-0.11, 0.036, 0.15)):
        solid(cone(r, h, 6), trim, Matrix.Translation((x, -0.125, -0.15)) @ xform(rot=(175, 0, 0)))
    for i in range(7):
        x = -0.18 + i * 0.06
        solid(cone(0.022, 0.072, 5), trim, Matrix.Translation((x, -0.125, -0.33)))
    for x in (0.18, -0.18):
        solid(cone(0.042, 0.17, 6), trim, Matrix.Translation((x, -0.128, -0.38)))
    # Ear fins and segmented curling horns
    for sx in (1, -1):
        layer([[(sx * 0.50, 0.03), (sx * 0.75, 0.12), (sx * 0.68, -0.04), (sx * 0.81, -0.17), (sx * 0.54, -0.14)]], trim, 0.0, 0.032, 0.010)
    for sx in (-1, 1) if horns else ():
        pts = [
            Vector((sx * 0.22, -0.01, 0.33)),
            Vector((sx * 0.37, -0.03, 0.55)),
            Vector((sx * 0.39, -0.02, 0.76)),
            Vector((sx * 0.29, 0.02, 0.95)),
        ]
        solid(tube(pts, 0.088, 7, taper=lambda u: (1.0 - 0.88 * u) * (1.0 + 0.07 * math.sin(u * 26.0))), trim, Matrix.Identity(4))


def oni_katana(f):
    to_xz = xform(rot=(90, 0, 0))
    L, hw, tk, z0 = 0.58, 0.0220, 0.0036, 0.0
    off = lambda u: -0.022 * u * u
    spine = [(-hw + off(i / 32 * 0.94), z0 + L * i / 32 * 0.94) for i in range(33)]
    tip = (-hw * 0.25 + off(1.0), z0 + L)
    edge = [(hw + off(i / 32 * 0.91), z0 + L * i / 32 * 0.91) for i in range(32, -1, -1)]
    outline = spine + [tip] + edge
    # Multi-bevel 3D katana blade with sharp edge, shinogi ridge, and fuller groove
    f.put(shape2d([outline], tk * 0.22, tk * 0.55), "primary", to_xz)
    f.put(shape2d([outline], tk * 1.05, tk * 0.25, 1, inset=hw * 0.16), "secondary", to_xz)
    spine_bar = [(-hw + off(i / 28 * 0.90), z0 + L * i / 28 * 0.90) for i in range(29)] + [(-hw * 0.42 + off(i / 28 * 0.90), z0 + L * i / 28 * 0.90) for i in range(28, -1, -1)]
    f.put(shape2d([spine_bar], tk * 1.25, tk * 0.18), "primary", to_xz)
    us = [i / 140 * 0.91 for i in range(3, 141)]

    def lava(u):
        return (0.0092 + 0.0058 * abs(math.sin(u * 48.0)) + 0.0024 * math.sin(u * 125.0)) * min(1.0, (1.0 - u) / 0.15)

    outer = [(hw + off(u), z0 + L * u) for u in us] + [tip]
    for key, scale, thick in (("ember", 1.75, 1.14), ("glow", 1.05, 1.25), ("hot", 0.40, 1.38)):
        inner = [(hw + off(u) - lava(u) * scale, z0 + L * u) for u in reversed(us)]
        f.put(shape2d([outer + inner], tk * thick), key, to_xz)
    for side in (-1, 1):
        for i in range(13):
            u0, u1 = 0.05 + i * 0.062, 0.05 + (i + 1) * 0.062
            line_xz(f, (-hw * 0.52 + off(u0), z0 + L * u0), (-hw * 0.52 + off(u1), z0 + L * u1), side * (tk * 1.15 + 0.0005), 0.0018, "glow")
    # Engraved gold habaki collar
    f.put(box(2 * hw + 0.005, 2 * tk + 0.007, 0.030, 0.0016), "metal", xform((0, 0, 0.017)))
    # Ornate 4-lobe mokko tsuba guard with raised gold rim and glowing inlays
    lobes = [(0.038 * (0.88 + 0.12 * math.cos(4 * i / 48 * TAU)) * math.cos(i / 48 * TAU), 0.034 * (0.88 + 0.12 * math.cos(4 * i / 48 * TAU)) * math.sin(i / 48 * TAU)) for i in range(48)]
    f.put(shape2d([lobes], 0.0038, 0.0012), "metal", xform((0, 0, -0.001)))
    f.put(shape2d([lobes], 0.0046, 0.0, inset=0.0045), "primary", xform((0, 0, -0.001)))
    f.put(torus(0.029, 0.0013, 28, 6), "glow", xform((0, 0, 0.0042)))
    f.put(torus(0.029, 0.0013, 28, 6), "glow", xform((0, 0, -0.0052)))
    oval = xform(scale=(1.0, 0.78, 1.0))
    f.put(lathe([(0.0150, -0.018), (0.0160, -0.015), (0.0160, -0.006), (0.0138, -0.004)], 16), "metal", oval)
    # Curved katana tsuka handle with red ray-skin core and black tsuka-ito diamond wrap
    grip = [(0.0112, -0.258), (0.0134, -0.246), (0.0144, -0.20), (0.0148, -0.13), (0.0144, -0.06), (0.0136, -0.012)]
    f.put(lathe(grip, 16), "accent", oval)
    for k in range(4):
        for sign in (1, -1):
            f.put(tube(coil(lambda z: 0.0145, -0.246, -0.018, sign * 2.2, k * TAU / 4, 0.0012, 28), 0.0052, 6, flat=0.34, radial=True), "grip", oval)
    for z_m in (-0.09, -0.17):
        for sy in (-1, 1):
            f.put(ball(0.0038, 1), "metal", xform((0, sy * 0.0118, z_m), scale=(1.8, 0.4, 1.1)))
    # Ornate kashira pommel cap with bottom demon spike
    f.put(box(0.031, 0.025, 0.028, 0.0042), "metal", xform((0, 0, -0.262)))
    f.put(cone(0.0075, 0.022, 6), "metal", xform((0, 0, -0.276), (180, 0, 0)))
    oni_mask(f, mask_matrix((0, -0.0135, 0.042), (0, -1, 0), (0, 0, 1), 0.076))
    oni_mask(f, mask_matrix((0, 0.0135, 0.042), (0, 1, 0), (0, 0, 1), 0.076))


def oni_karambit(f):
    to_xz = xform(rot=(90, 0, 0))
    R, zc, tk, n = 0.076, 0.038, 0.0034, 18
    shift = Matrix.Translation((-0.016, 0, 0)) @ to_xz

    def pt(phi_deg, r):
        a = math.radians(phi_deg)
        return (R + r * math.cos(a), zc + r * math.sin(a))

    def width(t):
        return 0.032 * (1.0 - t) ** 0.62 + 0.0006

    def phi(t):
        return 182.0 + (92.0 - 182.0) * t

    outer = [pt(phi(i / n), R) for i in range(n + 1)]
    inner = [pt(phi(i / n), R - width(i / n)) for i in range(n, -1, -1)]
    # Multi-bevel 3D curved hawkbill claw blade
    f.put(shape2d([outer + inner], tk * 0.25, tk * 0.55), "primary", shift)
    f.put(shape2d([outer + inner], tk * 1.12, tk * 0.22, 1, inset=0.0038), "secondary", shift)
    edge_a = [pt(phi(i / n), R - width(i / n)) for i in range(1, n + 1)]
    edge_b = [pt(phi(i / n), min(R - width(i / n) + 0.0085 * (1.0 - i / n) ** 0.4, R - 0.0004)) for i in range(n, 0, -1)]
    f.put(shape2d([edge_a + edge_b], tk * 1.24), "glow", shift)
    hot_b = [pt(phi(i / n), min(R - width(i / n) + 0.0032 * (1.0 - i / n) ** 0.4, R - 0.0004)) for i in range(n, 0, -1)]
    f.put(shape2d([edge_a + hot_b], tk * 1.38), "hot", shift)
    # Dorsal spine serration spikes
    for k in range(3):
        u = 0.14 + k * 0.16
        px, pz = pt(phi(u), R)
        spike(f, (px - 0.016, 0, pz), (-0.45, 0, 0.85), 0.0055 * (1.0 - 0.2 * k), 0.024 * (1.0 - 0.15 * k), "metal", 5)
    oval = xform(scale=(1.0, 0.78, 1.0))
    grip = [(0.0112, -0.052), (0.0132, -0.044), (0.0142, -0.015), (0.0136, 0.018), (0.0145, 0.032)]
    f.put(lathe(grip, 16), "grip", oval)
    f.put(lathe([(0.0146, 0.026), (0.0168, 0.030), (0.0168, 0.040), (0.0142, 0.043)], 16), "metal", oval)
    lattice(f, lambda z: 0.0138, -0.046, 0.024, 3.5, "accent", 0.0020, 0.0012, oval)
    # Heavy gold finger ring + rear talon spike
    f.put(torus(0.0195, 0.0044, 22, 8), "metal", Matrix.Translation((0, 0, -0.066)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    f.put(torus(0.0195, 0.0016, 22, 6), "glow", Matrix.Translation((0, 0, -0.066)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    spike(f, (0.014, 0, -0.082), (0.45, 0, -0.88), 0.0052, 0.022, "metal", 5)
    oni_mask(f, mask_matrix((0, -0.0135, -0.008), (0, -1, 0), (0, 0, 1), 0.034))
    oni_mask(f, mask_matrix((0, 0.0135, -0.008), (0, 1, 0), (0, 0, 1), 0.034))


def rune_strokes(rng):
    glyphs = [
        [((0, -1), (0, 1)), ((0, 0.1), (-1, 1)), ((0, 0.1), (1, 1))],
        [((-0.6, -1), (-0.6, 1)), ((-0.6, 1), (0.9, 0.4)), ((-0.6, 0.2), (0.9, -0.4))],
        [((-0.6, -1), (-0.6, 1)), ((-0.6, 0.7), (0.8, 0.2)), ((0.8, 0.2), (-0.6, -0.3))],
        [((0, 1), (0.8, 0)), ((0.8, 0), (0, -1)), ((0, -1), (-0.8, 0)), ((-0.8, 0), (0, 1))],
        [((-0.8, 1), (0.8, -1)), ((0.8, 1), (-0.8, -1))],
        [((0.6, 1), (-0.6, 0.3)), ((-0.6, 0.3), (0.6, -0.3)), ((0.6, -0.3), (-0.6, -1))],
        [((-0.6, -1), (-0.6, 1)), ((-0.6, 1), (0.8, 0.5)), ((-0.6, 0.3), (0.8, -0.2))],
    ]
    return rng.choice(glyphs)


def oni_cleaver(f):
    to_xz = xform(rot=(90, 0, 0))
    L, W, z0, tk = 0.43, 0.102, 0.03, 0.0038
    core = tk * 1.14
    outline = f.edge_points("clip", L, W, z0)
    # Multi-bevel heavy demonic cleaver blade
    f.put(shape2d([outline], tk * 0.24, tk * 0.58), "primary", to_xz)
    f.put(shape2d([outline], core, tk * 0.22, 1, inset=W * 0.10), "secondary", to_xz)
    tip_i = max(range(len(outline)), key=lambda i: outline[i][1])
    ztip = outline[tip_i][1]
    chain = [p for p in outline[tip_i:] if p[1] > z0 + 0.05 * L]
    inner = [(x - 0.014 * min(1.0, (ztip - z) / (0.22 * L)), z) for x, z in chain]
    f.put(shape2d([chain + list(reversed(inner))], tk * 1.25), "glow", to_xz)
    core_edge = [(x - 0.0052 * min(1.0, (ztip - z) / (0.22 * L)), z) for x, z in chain]
    f.put(shape2d([chain + list(reversed(core_edge))], tk * 1.38), "hot", to_xz)
    # Dorsal spine saw-hooks and gold spine rib
    for k in range(4):
        sz = z0 + 0.14 + k * 0.062
        spike(f, (-W * 0.42, 0, sz), (-0.85, 0, 0.45), 0.0058, 0.024, "metal", 5)
    cx, gw = 0.003, 0.0056
    glyphs = [rune_strokes(f.rng) for _ in range(10)]
    for side in (-1, 1):
        y = side * (core + 0.0005)
        for sx in (-0.0092, 0.0092):
            line_xz(f, (cx + sx, z0 + 0.125), (cx + sx, z0 + 0.382), y, 0.0014, "metal")
            line_xz(f, (cx + sx, z0 + 0.125), (cx + sx, z0 + 0.382), y + side * 0.0003, 0.0009, "glow")
        for i, strokes in enumerate(glyphs):
            gz = z0 + 0.150 + i * 0.0235
            for (a, b), (c, d) in strokes:
                line_xz(f, (cx + a * gw, gz + b * 0.0085), (cx + c * gw, gz + d * 0.0085), y, 0.0014, "glow")
    for sx in (-1, 1):
        spike(f, (sx * 0.028, 0, 0.028), (sx * 0.85, 0, -0.45), 0.0082, 0.052, "metal", 6)
    oval = xform(scale=(1.0, 0.78, 1.0))
    f.put(box(0.062, 0.028, 0.011, 0.0022), "metal", xform((0, 0, 0.0285)))
    f.put(lathe([(0.0124, -0.076), (0.0132, -0.04), (0.0138, 0.0), (0.0130, 0.022)], 16), "grip", oval)
    lattice(f, lambda z: 0.0134, -0.070, 0.020, 4.5, "accent", 0.0021, 0.0013, oval)
    f.put(lathe([(0.0112, -0.085), (0.0160, -0.076), (0.0164, -0.066), (0.0136, -0.061)], 16), "metal", oval)
    f.put(ball(0.0052, 2), "glow", xform((0, 0, -0.086), scale=(1.0, 0.8, 0.7)))
    oni_mask(f, mask_matrix((0, -(core + 0.0028), 0.078), (0, -1, 0), (0, 0, 1), 0.056))
    oni_mask(f, mask_matrix((0, core + 0.0028, 0.078), (0, 1, 0), (0, 0, 1), 0.056))


def oni_knuckle(f):
    # 4 gold-rimmed finger rings, sculpted 3D Oni mask on the bridge, open fanged jaw arch, and red-wrapped palm bar
    cz = [-0.052, -0.016, 0.020, 0.056]
    r_out = 0.0262
    outer = []
    for z in cz:
        outer.append((0.03 + r_out, z - r_out * 0.6))
        outer.append((0.03 + r_out * 1.18, z))
        outer.append((0.03 + r_out, z + r_out * 0.6))
    outer += [(0.022, 0.09), (-0.04, 0.088), (-0.08, 0.052), (-0.088, 0.0), (-0.08, -0.05), (-0.04, -0.086), (0.022, -0.09)]
    mouth_hole = chaikin([(-0.048, -0.042), (-0.034, -0.032), (-0.034, 0.032), (-0.048, 0.042), (-0.068, 0.040), (-0.068, -0.040)], 2)
    plate = [chaikin(outer, 2), mouth_hole] + [circle(0.0152, 22, 0.03, z) for z in cz]
    to_yz = Matrix.Translation((0.022, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(math.radians(90), 4, "Z")
    f.put(shape2d(plate, 0.0058, 0.0028), "primary", to_yz)
    f.put(shape2d([circle(0.0184, 22, 0.03, z) for z in cz] + [circle(0.0150, 22, 0.03, z) for z in cz], 0.0102, 0.0012), "metal", to_yz)
    f.put(shape2d([[(-0.092, -0.05), (-0.074, -0.052), (-0.074, 0.054), (-0.092, 0.05)]], 0.0102, 0.0014), "accent", to_yz)
    for z in (-0.042, -0.021, 0.0, 0.021, 0.042):
        f.put(box(0.0215, 0.0180, 0.0048, 0.0008), "grip", xform((0.022, -0.083, z)))
    for sign in (-1, 1):
        cx = 0.0365 if sign > 0 else 0.0075
        oni_mask(f, mask_matrix((cx, -0.024, 0.0), (sign, 0, 0), (0, 1, 0), 0.072), horns=False, black=True)
    for z in (-1, 1):
        horn(f, (0.022, -0.004, z * 0.084), (0.0, 0.35, z * 0.94), 0.054, 0.0095, (0.0, 0.034, 0.0))
    for z in cz:
        f.put(cone(0.0052, 0.013, 6), "metal", xform((0.022, 0.062, z), (-90, 0, 0)))
        for x in (0.0325, 0.0115):
            f.put(torus(0.0165, 0.0010, 18, 4), "glow", Matrix.Translation((x, 0.03, z)) @ Matrix.Rotation(math.radians(90), 4, "Y"))


def oni_pistol(f):
    build_revolver(f)
    # Sculpted gold demon shroud on the barrel nose + dorsal spine ridges
    f.dragon_head(xform((0.185, 0, 0.052), (-86, 0, 0)), 0.022, "metal")
    y = 0.0128
    for side in (-1, 1):
        ys = side * y
        for a, b in (
            ((0.155, 0.036), (0.020, 0.036)),
            ((0.020, 0.036), (-0.005, 0.050)),
            ((-0.005, 0.050), (-0.065, 0.050)),
            ((-0.020, 0.050), (-0.020, 0.026)),
            ((-0.020, 0.026), (-0.075, 0.026)),
            ((0.155, 0.024), (0.070, 0.024)),
            ((0.070, 0.024), (0.045, 0.019)),
        ):
            line_xz(f, a, b, ys, 0.0016, "glow", 0.0010)
        for p in ((-0.020, 0.050), (-0.020, 0.026), (0.020, 0.036), (0.045, 0.019)):
            f.put(ball(0.0020, 1), "hot", xform((p[0], ys, p[1])))
        horn(f, (-0.088, side * 0.0112, 0.058), (-0.32, side * 0.42, 0.82), 0.056, 0.0068, (-0.024, side * 0.012, -0.008))
        oni_mask(f, mask_matrix((-0.064, side * 0.0178, -0.072), (0, side, 0), (0, 0, 1), 0.054), horns=True, black=True)
    anchor = (-0.095, 0.0, -0.128)
    for i in range(2):
        f.put(torus(0.0038, 0.0011, 10, 4), "metal", Matrix.Translation((anchor[0] - 0.0004 * i, 0, anchor[2] - 0.0068 * i)) @ Matrix.Rotation(math.radians(90 * i), 4, "X"))
    f.put(ball(0.0040, 2), "metal", xform((anchor[0] - 0.001, 0, anchor[2] - 0.017)))
    f.put(lathe([(0.0016, -0.1465), (0.0048, -0.152), (0.0058, -0.165), (0.0034, -0.174), (0.0008, -0.178)], 12), "accent", Matrix.Translation((anchor[0] - 0.001, 0, 0.0)))


def oni_staff(f):
    z0, z1, r = -0.15, 0.66, 0.0168
    rfn = lambda z: r
    collars = (-0.085, 0.085, 0.328, 0.498, 0.64)
    f.put(lathe([(r, z0), (r, z1)], 18), "primary")
    f.put(lathe([(r + 0.0010, -0.072), (r + 0.0010, 0.072)], 18), "grip")
    lattice(f, rfn, -0.068, 0.068, 6.0, "accent", 0.0022, 0.0013)
    f.put(lathe([(r + 0.0010, 0.340), (r + 0.0010, 0.486)], 18), "grip")
    lattice(f, rfn, 0.344, 0.482, 5.0, "accent", 0.0020, 0.0012)
    for z in collars:
        f.put(lathe([(r + 0.0005, z), (r + 0.0034, z + 0.002), (r + 0.0034, z + 0.010), (r + 0.0005, z + 0.012)], 18), "metal")
        f.ring("glow", rfn, z - 0.006, 0.0022)
        f.ring("glow", rfn, z + 0.017, 0.0022)
    # Spear-point butt cap
    f.put(lathe([(r * 0.96, z0), (0.0145, z0 - 0.018), (0.0052, z0 - 0.052), (0.0008, z0 - 0.066)], 14), "metal")
    f.put(torus(0.0135, 0.0020, 16, 6), "glow", xform((0, 0, z0 - 0.0075)))
    # Coiled 3D golden dragon with dorsal spines + dragon head at top of shaft
    saved = f.style
    f.style = dict(saved, wrap="scale", wrap_key="metal")
    f.wrap(rfn, 0.10, 0.61)
    f.style = saved
    # Crown pedestal + twin 3D Oni masks + halberd side spikes + glowing finial orb
    f.put(lathe([(r + 0.0005, z1), (0.0235, z1 + 0.006), (0.0235, z1 + 0.015), (0.0130, z1 + 0.024), (0.0110, z1 + 0.036)], 18), "metal")
    f.ring("glow", rfn, z1 + 0.0105, 0.0025)
    top = z1 + 0.080
    oni_mask(f, mask_matrix((0, -0.0105, top), (0, -1, 0), (0, 0, 1), 0.082))
    oni_mask(f, mask_matrix((0, 0.0105, top), (0, 1, 0), (0, 0, 1), 0.082))
    f.put(box(0.044, 0.0032, 0.060, 0.0014), "metal", xform((0, 0, top - 0.006)))
    for sx in (-1, 1):
        spike(f, (sx * 0.022, 0, z1 + 0.028), (sx * 1.0, 0, 0.55), 0.0072, 0.046, "metal", 6)
    f.put(ball(0.0065, 2), "glow", xform((0, 0, top + 0.062)))
    f.put(torus(0.011, 0.0018, 16, 6), "metal", xform((0, 0, top + 0.062), (90, 0, 0)))



ONI_BUILDERS = {
    "poolcue": oni_staff,
    "bottle": oni_katana,
    "machete": oni_cleaver,
    "knife": oni_karambit,
    "knuckle": oni_knuckle,
    "revolver": oni_pistol,
}


BUILDERS = {
    "poolcue": build_poolcue,
    "bat": build_bat,
    "bottle": build_bottle,
    "machete": build_machete,
    "knife": build_knife,
    "knuckle": build_knuckle,
    "revolver": build_revolver,
}


def hex_linear(value):
    v = value.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(v[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


class Graph:
    def __init__(self, material):
        material.use_nodes = True
        self.tree = material.node_tree
        self.tree.nodes.clear()

    def node(self, kind, **props):
        n = self.tree.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.tree.links.new(a, b)

    def rgb(self, color):
        n = self.node("ShaderNodeRGB")
        n.outputs[0].default_value = color
        return n.outputs[0]

    def mix(self, a, b, fac, blend="MIX"):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self.link(fac, n.inputs[0])
        self.link(a, n.inputs[6])
        self.link(b, n.inputs[7])
        return n.outputs[2]

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        cr = n.color_ramp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[0])
        cr.elements[0].position, cr.elements[0].color = stops[0][0], (stops[0][1],) * 3 + (1.0,)
        for pos, val in stops[1:]:
            e = cr.elements.new(pos)
            e.color = (val,) * 3 + (1.0,)
        self.link(fac, n.inputs[0])
        return n.outputs[0]

    def value(self, v):
        n = self.node("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def math(self, op, a, b=None):
        n = self.node("ShaderNodeMath", operation=op)
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            self.link(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)):
                n.inputs[1].default_value = b
            else:
                self.link(b, n.inputs[1])
        return n.outputs[0]


def make_material(name, finish, color, c2, c3):
    m = bpy.data.materials.new(name)
    g = Graph(m)
    geo = g.node("ShaderNodeNewGeometry")
    tc = g.node("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    c = g.rgb(hex_linear(color))
    two = g.rgb(hex_linear(c2))
    three = g.rgb(hex_linear(c3))

    # Dual-bevel normal + Pointiness curvature edge detector
    bevel = g.node("ShaderNodeBevel", samples=6)
    bevel.inputs["Radius"].default_value = 0.0018
    bevel_wide = g.node("ShaderNodeBevel", samples=4)
    bevel_wide.inputs["Radius"].default_value = 0.0045
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(bevel.outputs[0], sep.inputs[0])

    # 3-Point Virtual Studio Rig (Key + Fill + Grazing Rim)
    key_l = g.math("ADD", g.math("MULTIPLY", sep.outputs[2], 0.64), g.math("MULTIPLY", sep.outputs[0], -0.36))
    key_l = g.math("ADD", key_l, g.math("MULTIPLY", sep.outputs[1], -0.48))
    fill_l = g.math("ADD", g.math("MULTIPLY", sep.outputs[2], -0.22), g.math("MULTIPLY", sep.outputs[0], 0.52))
    fill_l = g.math("ADD", fill_l, g.math("MULTIPLY", sep.outputs[1], -0.28))
    rim_l = g.math("SUBTRACT", 1.0, g.math("ABSOLUTE", sep.outputs[1]))
    rim_grazing = g.math("POWER", g.math("MAXIMUM", rim_l, 0.0), 3.2)

    light = g.math("ADD", key_l, g.math("MULTIPLY", g.math("MAXIMUM", fill_l, 0.0), 0.35))
    lit = g.math("ADD", g.math("MULTIPLY", light, 0.48), 0.78)
    lit = g.math("ADD", lit, g.math("MULTIPLY", rim_grazing, 0.22))

    pos = g.node("ShaderNodeSeparateXYZ")
    g.link(obj, pos.inputs[0])
    sweep = g.math("SINE", g.math("ADD", g.math("MULTIPLY", pos.outputs[2], 19.0), g.math("MULTIPLY", pos.outputs[0], 41.0)))

    dotn = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.link(bevel.outputs[0], dotn.inputs[0])
    g.link(geo.outputs["Normal"], dotn.inputs[1])
    dotn_w = g.node("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    g.link(bevel_wide.outputs[0], dotn_w.inputs[0])
    g.link(geo.outputs["Normal"], dotn_w.inputs[1])
    bevel_edge = g.math("MINIMUM", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, dotn.outputs["Value"]), 3.2), 1.0)
    wide_edge = g.math("MINIMUM", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, dotn_w.outputs["Value"]), 2.2), 1.0)
    pointy = g.ramp(geo.outputs["Pointiness"], [(0.48, 0.0), (0.56, 1.0)])
    edge = g.math("MAXIMUM", bevel_edge, g.math("MULTIPLY", g.math("MAXIMUM", wide_edge, pointy), 0.65))

    base = c
    if finish == "chrome":
        band = g.math("ADD", g.math("ADD", g.math("MULTIPLY", light, 0.46), 0.5), g.math("MULTIPLY", sweep, 0.16))
        r = g.ramp(band, [(0.0, 0.06), (0.24, 0.28), (0.44, 1.0), (0.54, 0.22), (0.74, 0.88), (1.0, 1.0)])
        base = g.mix(c, r, g.value(1.0), "MULTIPLY")
        base = g.mix(base, g.rgb((1.0, 1.0, 1.0, 1.0)), g.math("MULTIPLY", edge, 0.65))
        lit = g.value(1.0)
    elif finish == "brushed_steel":
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
        wave.inputs["Scale"].default_value = 520.0
        wave.inputs["Distortion"].default_value = 1.8
        g.link(obj, wave.inputs["Vector"])
        band = g.math("ADD", g.math("MULTIPLY", light, 0.45), 0.52)
        r = g.ramp(band, [(0.0, 0.14), (0.35, 0.52), (0.55, 0.96), (0.72, 0.44), (1.0, 1.0)])
        steel = g.mix(c, r, g.value(1.0), "MULTIPLY")
        grain = g.mix(steel, g.rgb((0.12, 0.13, 0.15, 1.0)), g.math("MULTIPLY", wave.outputs["Fac"], 0.22))
        base = g.mix(grain, g.rgb((0.96, 0.98, 1.0, 1.0)), g.math("MULTIPLY", edge, 0.78))
        lit = g.value(1.0)
    elif finish == "damascus":
        wave = g.node("ShaderNodeTexWave", wave_type="RINGS", rings_direction="Y")
        wave.inputs["Scale"].default_value = 68.0
        wave.inputs["Distortion"].default_value = 14.5
        wave.inputs["Detail"].default_value = 6.0
        g.link(obj, wave.inputs["Vector"])
        folds = g.ramp(wave.outputs["Fac"], [(0.0, 0.0), (0.42, 0.15), (0.50, 1.0), (0.58, 0.15), (1.0, 0.85)])
        layered = g.mix(c, two, g.math("MULTIPLY", folds, 0.75))
        glint = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", light, 0.0), 10.0), 0.65)
        shiny = g.mix(layered, g.rgb((0.92, 0.95, 1.0, 1.0)), glint)
        base = g.mix(shiny, g.rgb((0.95, 0.96, 1.0, 1.0)), g.math("MULTIPLY", edge, 0.68))
    elif finish == "forged_carbon":
        vor = g.node("ShaderNodeTexVoronoi", feature="F1")
        vor.inputs["Scale"].default_value = 95.0
        g.link(obj, vor.inputs["Vector"])
        flake = g.ramp(vor.outputs["Color"], [(0.0, 0.04), (0.45, 0.18), (0.75, 0.65), (1.0, 0.95)])
        chip = g.mix(c, g.rgb((0.24, 0.26, 0.30, 1.0)), g.math("MULTIPLY", flake, 0.55))
        glint = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", light, 0.0), 14.0), 0.75)
        base = g.mix(chip, two, g.math("MULTIPLY", edge, 0.45))
        base = g.mix(base, g.rgb((0.9, 0.92, 0.96, 1.0)), glint)
    elif finish in ("gloss", "porcelain"):
        power = 18.0 if finish == "gloss" else 7.0
        amount = 1.0 if finish == "gloss" else 0.38
        glint = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", light, 0.0), power), amount)
        streak = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", sweep, 0.0), 8.0), 0.32 if finish == "gloss" else 0.12)
        spec = g.math("ADD", glint, streak)
        base = g.mix(c, g.rgb((1, 1, 1, 1)), g.math("MINIMUM", spec, 1.0))
        base = g.mix(base, two, g.math("MULTIPLY", edge, 0.24))
    elif finish == "jade":
        noise = g.node("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 32.0
        noise.inputs["Detail"].default_value = 6.0
        noise.inputs["Distortion"].default_value = 0.9
        g.link(obj, noise.inputs["Vector"])
        cloud = g.ramp(noise.outputs["Fac"], [(0.2, 0.0), (0.8, 1.0)])
        sub = g.mix(c, two, g.math("MULTIPLY", cloud, 0.55))
        sss = g.math("ADD", g.math("MULTIPLY", rim_grazing, 0.55), g.math("MULTIPLY", edge, 0.45))
        glow_jade = g.mix(sub, three, g.math("MINIMUM", sss, 1.0))
        glint = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", light, 0.0), 14.0), 0.75)
        base = g.mix(glow_jade, g.rgb((1.0, 1.0, 1.0, 1.0)), glint)
    elif finish == "carbon":
        chk = g.node("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 620.0
        g.link(obj, chk.inputs["Vector"])
        base = g.mix(c, g.rgb((0.1, 0.1, 0.11, 1)), chk.outputs["Fac"], "ADD")
        base = g.mix(base, g.rgb((0.45, 0.48, 0.52, 1)), g.math("MULTIPLY", edge, 0.38))
    elif finish == "quilted":
        rot = g.node("ShaderNodeVectorRotate", rotation_type="Y_AXIS")
        rot.inputs["Angle"].default_value = math.radians(45)
        g.link(obj, rot.inputs["Vector"])
        chk = g.node("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 170.0
        g.link(rot.outputs[0], chk.inputs["Vector"])
        base = g.mix(c, g.rgb((1, 1, 1, 1)), g.math("MULTIPLY", chk.outputs["Fac"], 0.17))
    elif finish == "rope":
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL")
        wave.inputs["Scale"].default_value = 260.0
        wave.inputs["Distortion"].default_value = 0.0
        g.link(obj, wave.inputs["Vector"])
        base = g.mix(c, g.rgb((1, 1, 1, 1)), g.math("MULTIPLY", wave.outputs["Fac"], 0.35))
    elif finish in ("marble", "cracked_marble"):
        noise = g.node("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 26.0
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Distortion"].default_value = 1.6
        g.link(obj, noise.inputs["Vector"])
        vein = g.ramp(noise.outputs["Fac"], [(0.0, 0.0), (0.46, 0.0), (0.5, 1.0), (0.54, 0.0), (1.0, 0.0)])
        base = g.mix(c, two, vein)
        if finish == "cracked_marble":
            vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
            vor.inputs["Scale"].default_value = 24.0
            g.link(obj, vor.inputs["Vector"])
            cracks = g.ramp(vor.outputs["Distance"], [(0.0, 1.0), (0.018, 1.0), (0.055, 0.0), (1.0, 0.0)])
            base = g.mix(base, three, cracks)
            lit = g.math("MAXIMUM", lit, cracks)
    elif finish == "lava_crack":
        vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        vor.inputs["Scale"].default_value = 34.0
        g.link(obj, vor.inputs["Vector"])
        fissure = g.ramp(vor.outputs["Distance"], [(0.0, 1.0), (0.022, 1.0), (0.075, 0.0), (1.0, 0.0)])
        core_hot = g.ramp(vor.outputs["Distance"], [(0.0, 1.0), (0.008, 1.0), (0.025, 0.0), (1.0, 0.0)])
        base = g.mix(g.mix(c, two, fissure), g.rgb((1.0, 0.96, 0.82, 1.0)), core_hot)
        lit = g.math("MAXIMUM", lit, fissure)
    elif finish == "nebula":
        noise = g.node("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 22.0
        noise.inputs["Detail"].default_value = 7.0
        g.link(obj, noise.inputs["Vector"])
        cloud = g.ramp(noise.outputs["Fac"], [(0.0, 0.0), (0.35, 0.0), (0.7, 1.0), (1.0, 1.0)])
        vor = g.node("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 140.0
        g.link(obj, vor.inputs["Vector"])
        stars = g.ramp(vor.outputs["Distance"], [(0.0, 1.0), (0.1, 0.0), (1.0, 0.0)])
        base = g.mix(g.mix(c, two, cloud), g.rgb((1, 1, 1, 1)), stars)
    elif finish == "lightning":
        warp = g.node("ShaderNodeTexNoise")
        warp.inputs["Scale"].default_value = 60.0
        g.link(obj, warp.inputs["Vector"])
        mixv = g.node("ShaderNodeMix", data_type="VECTOR")
        mixv.inputs["Factor"].default_value = 0.012
        g.link(obj, mixv.inputs["A"])
        g.link(warp.outputs["Color"], mixv.inputs["B"])
        vor = g.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        vor.inputs["Scale"].default_value = 30.0
        g.link(mixv.outputs[1], vor.inputs["Vector"])
        arcs = g.ramp(vor.outputs["Distance"], [(0.0, 1.0), (0.012, 1.0), (0.05, 0.0), (1.0, 0.0)])
        base = g.mix(c, two, arcs)
        lit = g.math("MAXIMUM", lit, arcs)
    elif finish == "iridescent":
        band = g.math("ADD", g.math("MULTIPLY", light, 0.5), 0.5)
        base = g.mix(g.mix(c, two, band), three, g.math("POWER", band, 3.0))
        base = g.mix(base, g.rgb((1.0, 1.0, 1.0, 1.0)), g.math("MULTIPLY", edge, 0.45))
    elif finish == "gold":
        band = g.math("ADD", g.math("ADD", g.math("MULTIPLY", light, 0.48), 0.5), g.math("MULTIPLY", sweep, 0.14))
        ramp = g.ramp(band, [(0.0, 0.12), (0.22, 0.42), (0.42, 1.0), (0.55, 0.34), (0.75, 0.90), (1.0, 1.0)])
        warm = g.mix(c, ramp, g.value(1.0), "MULTIPLY")
        wave = g.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="DIAGONAL")
        wave.inputs["Scale"].default_value = 340.0
        wave.inputs["Distortion"].default_value = 3.0
        g.link(obj, wave.inputs["Vector"])
        grain = g.mix(warm, g.rgb((0.18, 0.10, 0.02, 1.0)), g.math("MULTIPLY", wave.outputs["Fac"], 0.14))
        base = g.mix(grain, g.rgb((1.0, 0.95, 0.72, 1.0)), g.math("MULTIPLY", edge, 0.92))
        lit = g.value(1.0)
    elif finish == "lacquer":
        glint = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", light, 0.0), 14.0), 0.92)
        streak = g.math("MULTIPLY", g.math("POWER", g.math("MAXIMUM", sweep, 0.0), 10.0), 0.25)
        spec = g.math("MINIMUM", g.math("ADD", glint, streak), 1.0)
        shiny = g.mix(c, g.rgb((0.88, 0.88, 0.94, 1.0)), spec)
        base = g.mix(shiny, g.rgb((1.0, 0.20, 0.26, 1.0)), g.math("MULTIPLY", edge, 0.44))
    elif finish == "emit":
        lit = g.value(1.0)
    else:
        # Matte / tactical polymer with subtle edge highlight
        base = g.mix(c, g.rgb((0.75, 0.78, 0.82, 1.0)), g.math("MULTIPLY", edge, 0.22))

    ao = g.node("ShaderNodeAmbientOcclusion", samples=6)
    ao.inputs["Distance"].default_value = 0.014
    occl = g.ramp(ao.outputs["AO"], [(0.0, 0.38), (1.0, 1.0)]) if finish not in ("emit",) else g.value(1.0)
    if finish not in ("emit",):
        ao2 = g.node("ShaderNodeAmbientOcclusion", samples=6)
        ao2.inputs["Distance"].default_value = 0.0035
        occl = g.math("MULTIPLY", occl, g.ramp(ao2.outputs["AO"], [(0.0, 0.52), (1.0, 1.0)]))
    shade = g.math("MULTIPLY", lit, occl)
    combine = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    combine.inputs[0].default_value = 1.0
    g.link(base, combine.inputs[6])
    g.link(shade, combine.inputs[7])
    em = g.node("ShaderNodeEmission")
    g.link(combine.outputs[2], em.inputs["Color"])
    out = g.node("ShaderNodeOutputMaterial")
    g.link(em.outputs[0], out.inputs["Surface"])
    return m


def build_materials(style, spec_id):
    pal, fin = style["palette"], style["finish"]
    mats = {}
    for key in ("primary", "secondary", "accent", "glow", "grip", "metal", "hot", "ember"):
        mats[key] = make_material(f"{spec_id}_{key}", fin.get(key, "matte"), pal.get(key, "#ffd2c8"), pal["secondary"] if key == "primary" else pal["glow"], pal["accent"])
    mats["grip_dark"] = make_material(f"{spec_id}_ink", "gloss", "#1b1518", "#000000", "#000000")
    return mats


def finish_object(forge, name, mats):
    bm = bmesh.new()
    order = sorted(forge.parts.keys())
    me = bpy.data.meshes.new(name)
    for idx, key in enumerate(order):
        part = forge.parts[key]
        bmesh.ops.recalc_face_normals(part, faces=part.faces)
        tmp = bpy.data.meshes.new("t")
        part.to_mesh(tmp)
        part.free()
        before = len(bm.faces)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[before:]:
            f.material_index = idx
        me.materials.append(mats[key])
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    for f in bm.faces:
        f.smooth = True
    limit = math.radians(38)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > limit:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap 0")
    me.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
    col = me.color_attributes["Color 1"]
    col.data.foreach_set("color", [1.0] * (len(col.data) * 4))
    ob = bpy.data.objects.new(name, me)
    return ob, sum(len(p.vertices) - 2 for p in me.polygons)


def setup_cycles(samples):
    s = scene()
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = False
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.cycles.max_bounces = 0
    s.cycles.use_adaptive_sampling = False


def _load_export_ydr():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import export_ydr
    return export_ydr


def bake(ob, size, out_dir, samples):
    s = scene()
    s.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{ob.name}_d", size, size, alpha=True)
    img.generated_color = (0, 0, 0, 1)
    img.colorspace_settings.name = "sRGB"
    for m in ob.data.materials:
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        m.node_tree.nodes.active = n
    s.cycles.samples = samples
    s.render.bake.margin = 8
    s.render.bake.use_clear = True
    bpy.ops.object.bake(type="EMIT", use_clear=True, margin=8)
    path = os.path.join(out_dir, f"{ob.name}_d.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    eydr = _load_export_ydr()
    dds_path = os.path.join(out_dir, f"{ob.name}_d.dds")
    eydr.image_to_dxt5(img, dds_path=dds_path, bloom=True)
    img.filepath = path
    final = bpy.data.materials.new(f"{ob.name}_body")
    g = Graph(final)
    tex = g.node("ShaderNodeTexImage")
    tex.image = img
    em = g.node("ShaderNodeEmission")
    out = g.node("ShaderNodeOutputMaterial")
    g.link(tex.outputs[0], em.inputs["Color"])
    g.link(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.clear()
    ob.data.materials.append(final)
    ob.select_set(False)
    s.collection.objects.unlink(ob)
    return path


SKELETONS = {
    "melee": [("Gun_Root", None, (0, 0, 0)), ("Gun_GripR", "Gun_Root", (-0.046, 0.002, 0.012)), ("Gun_Main_Bone", "Gun_GripR", (0, 0, 0))],
    "revolver": [
        ("Gun_Root", None, (0, 0, 0)),
        ("Gun_GripR", "Gun_Root", (-0.095, -0.017, -0.061)),
        ("Gun_Main_Bone", "Gun_GripR", (0.0, 0.0, 0.0)),
        ("gun_crane", "Gun_Main_Bone", (0.072, 0.005, 0.0)),
        ("gun_cylinder", "gun_crane", (0.066, -0.005, -0.026)),
        ("Gun_VFX_Eject", "gun_cylinder", (0, 0, 0)),
        ("WAPClip", "gun_cylinder", (0, 0, 0)),
        ("Gun_Muzzle", "Gun_Main_Bone", (0.247, 0.0, 0.039)),
        ("Gun_Trigger_Pr", "Gun_Main_Bone", (0.007, 0.0, -0.007)),
        ("Gun_Hammer", "Gun_Main_Bone", (-0.027, 0.0, 0.037)),
    ],
}


def add_skeleton(ob, name, slot):
    arm = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm)
    s = scene()
    s.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    bones = list(SKELETONS["revolver" if slot == "revolver" else "melee"])
    if slot == "poolcue":
        bones.append(("Gun_GripL", "Gun_Root", (0.0, 0.0, 0.413)))
    for bone, parent, head in bones:
        eb = arm.edit_bones.new(bone)
        eb.head = head
        eb.tail = Vector(head) + Vector((0, 0, 0.03))
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    s.collection.objects.unlink(rig)
    ob.name = f"{name}_mesh"
    rig.name = name
    arm.name = name
    ob.parent = rig
    ob.vertex_groups.clear()
    group = ob.vertex_groups.new(name="Gun_Main_Bone")
    group.add(range(len(ob.data.vertices)), 1.0, "REPLACE")
    return rig


def save_model(rig, ob, path, slot="machete", dds_path=None):
    eydr = _load_export_ydr()
    sc = bpy.data.scenes.new(rig.name)
    sc.collection.objects.link(rig)
    sc.collection.objects.link(ob)
    working_name = ob.name
    ob.name = "Gun_Root"
    eydr.attach_sollumz_hierarchy(rig, ob, slot, dds_path=dds_path)
    for child in rig.children:
        if child.name not in sc.collection.objects:
            sc.collection.objects.link(child)
        for sub in child.children:
            if sub.name not in sc.collection.objects:
                sc.collection.objects.link(sub)
    bpy.data.libraries.write(path, {sc}, path_remap="RELATIVE", fake_user=True, compress=True)
    ob.name = working_name
    bpy.data.scenes.remove(sc)


def render_sheet(items, path, samples, background):
    s = scene()
    bpy.context.view_layer.update()
    pre_objs = [o for o in s.objects if o.type == "MESH" and not o.hide_render]
    for o in pre_objs:
        o.hide_render = True
    cam_data = bpy.data.cameras.new("sheet")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("sheet", cam_data)
    s.collection.objects.link(cam)
    s.camera = cam
    cursor = 0.0
    tall = 0.0
    placed = []
    gap = 0.075
    for slot, ob in items:
        inst = bpy.data.objects.new(ob.name + "_sheet", ob.data)
        s.collection.objects.link(inst)
        placed.append(inst)
        rot = Matrix.Rotation(math.radians(YAW), 4, "Z")
        if slot == "knuckle":
            rot = rot @ Matrix.Rotation(math.radians(-90), 4, "Z")
        co = [rot @ Vector(c) for c in ob.bound_box]
        xs, zs = [v.x for v in co], [v.z for v in co]
        width = max(xs) - min(xs)
        inst.matrix_world = Matrix.Translation((cursor - min(xs), 0, -min(zs))) @ rot
        cursor += width + gap
        tall = max(tall, max(zs) - min(zs))
    total = cursor - gap
    aspect = 16 / 9
    span = max(total, tall * aspect) * 1.08
    cam_z = tall / 2
    if FOCUS:
        span = max(tall * (FOCUS[1] - FOCUS[0]) * aspect, total) * 1.1
        cam_z = tall * (FOCUS[0] + FOCUS[1]) / 2
    cam_data.ortho_scale = span
    cam.matrix_world = Matrix.Translation((total / 2, -2.0, cam_z)) @ Matrix.Rotation(math.radians(90), 4, "X")
    world = bpy.data.worlds.new("sheet")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = hex_linear(background)
    s.world = world
    s.render.resolution_x, s.render.resolution_y = 1600, 900
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = path
    s.cycles.samples = samples
    bpy.ops.render.render(write_still=True)
    for inst in placed:
        bpy.data.objects.remove(inst)
    bpy.data.objects.remove(cam)
    for o in pre_objs:
        o.hide_render = False


def render_icon(slot, ob, path, samples):
    s = scene()
    bpy.context.view_layer.update()
    pre_objs = [o for o in s.objects if o.type == "MESH" and not o.hide_render]
    for o in pre_objs:
        o.hide_render = True
    inst = bpy.data.objects.new(ob.name + "_icon", ob.data)
    s.collection.objects.link(inst)
    cam_data = bpy.data.cameras.new("icon")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("icon", cam_data)
    s.collection.objects.link(cam)
    s.camera = cam
    turn = Matrix.Rotation(math.radians(-90), 4, "Z") if slot == "knuckle" else Matrix.Identity(4)
    tilt = Matrix.Rotation(math.radians(-42 if slot not in ("knuckle", "revolver") else 0), 4, "Y")
    inst.matrix_world = tilt @ turn
    pts = [inst.matrix_world @ Vector(c) for c in ob.bound_box]
    xs, zs = [p.x for p in pts], [p.z for p in pts]
    cam_data.ortho_scale = max(max(xs) - min(xs), max(zs) - min(zs)) * 1.08
    cam.matrix_world = Matrix.Translation(((max(xs) + min(xs)) / 2, -2.0, (max(zs) + min(zs)) / 2)) @ Matrix.Rotation(math.radians(90), 4, "X")
    s.render.film_transparent = True
    s.render.resolution_x, s.render.resolution_y = 96, 96
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.render.filepath = path
    s.cycles.samples = samples
    bpy.ops.render.render(write_still=True)
    s.render.film_transparent = False
    s.render.image_settings.color_mode = "RGB"
    bpy.data.objects.remove(inst)
    bpy.data.objects.remove(cam)
    for o in pre_objs:
        o.hide_render = False


def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--bake", type=int, default=0)
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--icons", action="store_true")
    ap.add_argument("--ydr", nargs="?", const="AUTO", default="", help="compile RSC7 .ydr + .ytd into stream dir (or pass explicit dir)")
    ap.add_argument("--focus", default="", help="zoom the sheet on a slice of the item height, e.g. 0.85,1.0")
    ap.add_argument("--yaw", type=float, default=0.0, help="turn items about the long axis in the sheet, degrees")
    args = ap.parse_args(argv)
    global FOCUS, YAW
    YAW = args.yaw
    if args.focus:
        FOCUS = tuple(float(v) for v in args.focus.split(","))
    with open(args.spec, "r", encoding="utf-8-sig") as fh:
        spec = json.load(fh)
    if spec["family"] not in FAMILIES:
        raise SystemExit(f"unknown family {spec['family']}; expected one of {sorted(FAMILIES)}")
    style = merge(FAMILIES[spec["family"]], spec.get("style", {}))
    if "palette" in spec:
        style["palette"] = merge(style["palette"], spec["palette"])
    sid = spec["id"]
    only = [w for w in args.only.split(",") if w]
    weapons = only or spec.get("weapons") or list(BUILDERS)
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
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    setup_cycles(args.samples)
    mats = build_materials(style, sid)
    built = []
    report = {"id": sid, "family": spec["family"], "models": []}
    for idx, slot in enumerate(weapons):
        rng = random.Random(int(spec.get("seed", 7)) * 1000 + idx)
        forge = Forge(style, rng)
        builder = (ONI_BUILDERS.get(slot) if style.get("oni") else None) or BUILDERS[slot]
        builder(forge)
        model = f"{SLOTS[slot]['prefix']}_{sid}_{slot}"
        ob, tris = finish_object(forge, model, mats)
        bbox = [Vector(c) for c in ob.bound_box]
        lows = [min(v[a] for v in bbox) for a in range(3)]
        highs = [max(v[a] for v in bbox) for a in range(3)]
        entry = {
            "slot": slot, "model": model, "tris": tris,
            "bbox_min": [round(v, 3) for v in lows], "bbox_max": [round(v, 3) for v in highs],
            "over_budget": tris > SLOTS[slot]["tris"][1],
        }
        report["models"].append(entry)
        built.append((slot, ob, model))
        print(f"@@FORGE {slot} tris={tris} bbox={entry['bbox_min']}..{entry['bbox_max']}")
    if not args.no_sheet:
        sheet = os.path.join(out_dir, f"{sid}_sheet.png")
        render_sheet([(slot, ob) for slot, ob, _ in built], sheet, args.samples, style.get("sheet_bg", "#6f7379"))
        report["sheet"] = sheet
    if args.icons:
        for slot, ob, _ in built:
            render_icon(slot, ob, os.path.join(out_dir, f"icon_{slot}.png"), args.samples)
    eydr = _load_export_ydr()
    for slot, ob, model in built:
        entry = next(e for e in report["models"] if e["slot"] == slot)
        bake_res = args.bake or (1024 if ydr_dir else 0)
        dds_path = os.path.join(out_dir, f"{model}_d.dds") if bake_res else None
        if bake_res:
            entry["texture"] = bake(ob, bake_res, out_dir, max(args.samples, 32))
            entry["dds"] = dds_path
        rig = add_skeleton(ob, model, slot)
        path = os.path.join(out_dir, f"{model}.blend")
        save_model(rig, ob, path, slot=slot, dds_path=dds_path)
        entry["blend"] = path
        if ydr_dir:
            res = eydr.export_ydr_from_objects(rig, ob, slot, ydr_dir, make_hi=True, dds_out_dir=out_dir)
            entry["ydr"] = res["ydr"]
            entry["ytd"] = res["ytd"]
            print(f"@@FORGE_YDR {slot} ydr={res['ydr']} ({res['size_kb']} KB) geometries={res['geometries']}")
    with open(os.path.join(out_dir, "forge_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("@@FORGE done", json.dumps({"models": len(report["models"]), "ydr_exported": bool(ydr_dir)}))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
