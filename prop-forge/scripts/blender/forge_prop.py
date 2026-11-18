"""prop-forge: build stylised toy-brand FiveM props (signs, ATM, safe, crates, bench, floating marker) from a JSON spec.

Every prop is built from bevelled primitives, extruded 2D shapes, slime skirts, crowns, mascot heads and mesh text,
then joined into one mesh with its origin at floor centre (Z up, front faces -Y, metres). The default finish maps every
face to a swatch of a small palette texture so the prop exports with one diffuse and one emissive material.

Usage (Blender 4.2+, no add-ons needed):
  blender -b --factory-startup -P forge_prop.py -- --spec spec.json --out <dir> [--only id[,id]] [--bake 1024]
                                                   [--no-render] [--lineup] [--samples 32] [--list]

Output per prop in <dir>: <id>.blend (Blender 4.2 format), <id>_preview.png, <id>_palette.png (or _atlas.png),
and report.json with size, tris, materials and warnings. --lineup also renders lineup.png with every prop in a row.
"""

import argparse
import json
import math
import os
import random
import sys
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FONT_DIR = os.path.join(SKILL_ROOT, "assets", "fonts")

DEFAULT_PALETTE = {
    "primary": "#8E2DE2",
    "accent": "#C9F31D",
    "light": "#F4F0E8",
    "dark": "#221E28",
    "gold": "#FFC62E",
    "trim": "#E04DFF",
    "metal": "#9BA1A8",
    "screen": "#2B1745",
    "glow": "#D9FF3B",
    "glowtrim": "#F06BFF",
    "wood": "#E9D7B8",
}

ROLE_SHADING = {
    "primary": {"rough": 0.38, "coat": 0.25},
    "accent": {"rough": 0.22, "coat": 0.6},
    "light": {"rough": 0.45},
    "dark": {"rough": 0.6},
    "gold": {"rough": 0.28, "metal": 0.85},
    "trim": {"rough": 0.35, "coat": 0.3},
    "metal": {"rough": 0.35, "metal": 0.9},
    "screen": {"rough": 0.2, "emit": 0.8},
    "glow": {"rough": 0.3, "emit": 4.0},
    "glowtrim": {"rough": 0.3, "emit": 4.0},
    "wood": {"rough": 0.7},
}

EMISSIVE_ROLES = {"screen", "glow", "glowtrim"}

TRIS_BUDGET = {
    "sign_post": 14000,
    "kiosk_sign": 11000,
    "atm": 12000,
    "safe": 14000,
    "crate": 12000,
    "chest": 10000,
    "workbench": 18000,
    "mascot_marker": 5000,
}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(value):
    v = value.lstrip("#")
    return tuple(int(v[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def trs(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), Vector(scale))


def facing(direction):
    return Vector(direction).normalized().to_track_quat("-Y", "Z").to_matrix().to_4x4()


def rounded_rect(w, h, r, step=0.03):
    hw, hh = w / 2.0, h / 2.0
    r = max(0.0, min(r, hw * 0.95, hh * 0.95))
    pts = []
    corners = [(hw - r, -hh + r, -90.0), (hw - r, hh - r, 0.0), (-hw + r, hh - r, 90.0), (-hw + r, -hh + r, 180.0)]
    for cx, cz, start in corners:
        n = max(2, int((math.pi * r / 2.0) / step))
        for i in range(n + 1):
            a = math.radians(start + 90.0 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def resample(pts, step):
    out = []
    for i in range(len(pts)):
        a = Vector(pts[i])
        b = Vector(pts[(i + 1) % len(pts)])
        n = max(1, int((b - a).length / step))
        for k in range(n):
            p = a.lerp(b, k / n)
            out.append((p.x, p.y))
    return out


def outline_normals(pts):
    normals = []
    count = len(pts)
    area = 0.0
    for i in range(count):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % count]
        area += x0 * z1 - x1 * z0
    sign = 1.0 if area > 0 else -1.0
    for i in range(count):
        p0 = Vector(pts[i - 1])
        p1 = Vector(pts[(i + 1) % count])
        t = (p1 - p0).normalized()
        normals.append(Vector((t.y * sign, -t.x * sign)))
    return normals


def blob_outline(w, h, rng, wobble=0.015, lobes=3, lobe_amp=0.06, corner=0.12, step=0.02):
    step = max(step, (w + h) * 2.0 / 140.0)
    pts = resample(rounded_rect(w, h, min(w, h) * corner), step)
    normals = outline_normals(pts)
    phase = rng.uniform(0, math.tau)
    centers = [(-w / 2.0 + w * (i + 0.5) / lobes + rng.uniform(-0.04, 0.04) * w) for i in range(lobes)]
    widths = [w / lobes * rng.uniform(0.28, 0.4) for _ in range(lobes)]
    amps = [lobe_amp * rng.uniform(0.6, 1.0) for _ in range(lobes)]
    out = []
    for (x, z), n in zip(pts, normals):
        off = wobble * math.sin(x * 9.0 + z * 7.0 + phase)
        if n.y > 0.3:
            for c, wd, a in zip(centers, widths, amps):
                off += a * math.exp(-((x - c) / wd) ** 2) * n.y
        out.append((x + n.x * off, z + n.y * off))
    return out


def arrow_outline(w, h, tip, r, step=0.03):
    hw, hh = w / 2.0, h / 2.0
    pts = []
    n = max(2, int((math.pi * r / 2.0) / step))
    for i in range(n + 1):
        a = math.radians(180.0 + 90.0 * i / n)
        pts.append((-hw + r + r * math.cos(a), -hh + r + r * math.sin(a)))
    pts.append((hw - tip * 0.15, -hh))
    pts.append((hw + tip, 0.0))
    pts.append((hw - tip * 0.15, hh))
    for i in range(n + 1):
        a = math.radians(90.0 + 90.0 * i / n)
        pts.append((-hw + r + r * math.cos(a), hh - r + r * math.sin(a)))
    return pts


def star_outline(r_out, r_in, points=4):
    pts = []
    for i in range(points * 2):
        a = math.pi / 2.0 + math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


class PropBuilder:
    def __init__(self, spec, prop):
        self.spec = spec
        self.prop = prop
        self.id = prop["id"]
        self.palette = dict(DEFAULT_PALETTE)
        self.palette.update(spec.get("palette", {}))
        self.palette.update(prop.get("palette", {}))
        seed = prop.get("seed", zlib.crc32(self.id.encode("utf-8")))
        self.rng = random.Random(seed)
        self.parts = []
        self.colliders = []
        self.materials = {}
        self.warnings = []
        self.collection = bpy.data.collections.new(self.id + "_parts")
        bpy.context.scene.collection.children.link(self.collection)
        self.font = self.load_font(spec.get("font", "TitanOne-Regular.ttf"))
        brand = spec.get("brand", {})
        self.brand = brand.get("name", "GOO LAB")
        self.brand_short = brand.get("short", self.brand.split(" ")[0])

    def load_font(self, name):
        path = name if os.path.isabs(name) else os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            return bpy.data.fonts.load(path, check_existing=True)
        self.warnings.append("font not found, using Blender default: " + path)
        return None

    def material(self, role):
        if role in self.materials:
            return self.materials[role]
        name = "{}_{}".format(self.spec.get("set", "prop"), role)
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        shade = ROLE_SHADING.get(role, {"rough": 0.4})
        rgb = hex_rgb(self.palette.get(role, "#FF00FF"))
        lin = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Roughness"].default_value = shade.get("rough", 0.4)
        bsdf.inputs["Metallic"].default_value = shade.get("metal", 0.0)
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = shade.get("coat", 0.0)
        if shade.get("emit"):
            bsdf.inputs["Emission Color"].default_value = lin
            bsdf.inputs["Emission Strength"].default_value = shade["emit"]
        mat.diffuse_color = lin
        mat["prop_forge_role"] = role
        self.materials[role] = mat
        return mat

    def add(self, name, bm, role, matrix, bevel=0.0, segments=3, solidify=0.0):
        me = bpy.data.meshes.new(name)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        self.collection.objects.link(ob)
        ob.matrix_world = matrix
        me.materials.append(self.material(role))
        if solidify > 0:
            mod = ob.modifiers.new("solidify", "SOLIDIFY")
            mod.thickness = solidify
            mod.offset = 0.0
        if bevel > 0:
            mod = ob.modifiers.new("bevel", "BEVEL")
            mod.width = bevel
            mod.segments = segments
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(40)
            mod.use_clamp_overlap = True
        self.parts.append(ob)
        return ob

    def box(self, size, loc=(0, 0, 0), role="primary", bevel=0.02, rot=(0, 0, 0), M=None, matrix=None, collide=False, segments=3):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        local = matrix if matrix is not None else trs(loc, rot)
        world = (M or Matrix.Identity(4)) @ local
        bevel = min(bevel, 0.4 * min(size))
        if bevel < 0.007:
            segments = 1
        elif min(size) < 0.08:
            segments = min(segments, 2)
        ob = self.add("box", bm, role, world, bevel=bevel, segments=segments)
        if collide:
            self.collider_from(world, size)
        return ob

    def cyl(self, radius, depth, loc=(0, 0, 0), role="primary", axis="Z", segments=16, radius2=None, bevel=0.0, rot=(0, 0, 0), M=None, matrix=None, collide=False):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2, depth=depth)
        axis_rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        local = matrix if matrix is not None else trs(loc, rot)
        world = (M or Matrix.Identity(4)) @ local @ axis_rot
        bevel = min(bevel, 0.4 * min(radius, depth))
        ob = self.add("cyl", bm, role, world, bevel=bevel, segments=2)
        if collide:
            self.collider_from(world, (radius * 2, radius * 2, depth))
        return ob

    def sphere(self, radius, loc=(0, 0, 0), role="primary", scale=(1, 1, 1), u=16, v=10, rot=(0, 0, 0), M=None, matrix=None):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)
        local = matrix if matrix is not None else trs(loc, rot, scale)
        return self.add("sphere", bm, role, (M or Matrix.Identity(4)) @ local)

    def torus(self, major, minor, loc=(0, 0, 0), role="light", axis="Y", seg_major=28, seg_minor=8, rot=(0, 0, 0), M=None):
        bm = bmesh.new()
        rings = []
        for i in range(seg_major):
            a = math.tau * i / seg_major
            ring = []
            for j in range(seg_minor):
                b = math.tau * j / seg_minor
                r = major + minor * math.cos(b)
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), minor * math.sin(b))))
            rings.append(ring)
        for i in range(seg_major):
            for j in range(seg_minor):
                a = rings[i][j]
                b = rings[(i + 1) % seg_major][j]
                c = rings[(i + 1) % seg_major][(j + 1) % seg_minor]
                d = rings[i][(j + 1) % seg_minor]
                bm.faces.new((a, b, c, d))
        axis_rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        return self.add("torus", bm, role, (M or Matrix.Identity(4)) @ trs(loc, rot) @ axis_rot)

    def shape(self, pts, y0, y1, role="primary", bevel=0.01, loc=(0, 0, 0), rot=(0, 0, 0), M=None, matrix=None, collide=False):
        bm = bmesh.new()
        front = [bm.verts.new((x, y0, z)) for x, z in pts]
        back = [bm.verts.new((x, y1, z)) for x, z in pts]
        bm.faces.new(front)
        bm.faces.new(list(reversed(back)))
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((front[i], front[j], back[j], back[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        local = matrix if matrix is not None else trs(loc, rot)
        world = (M or Matrix.Identity(4)) @ local
        ob = self.add("shape", bm, role, world, bevel=bevel, segments=2)
        if collide:
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            center = ((min(xs) + max(xs)) / 2, (y0 + y1) / 2, (min(zs) + max(zs)) / 2)
            self.collider_from(world @ Matrix.Translation(center), (max(xs) - min(xs), abs(y1 - y0), max(zs) - min(zs)))
        return ob

    def text(self, body, height, loc=(0, 0, 0), role="light", depth=0.03, max_w=None, outline_role="dark", outline=0.14, rot_z=0.0, M=None, font=None):
        if not body:
            return None
        depsgraph = bpy.context.evaluated_depsgraph_get()

        def build(offset, extrude, bevel):
            cu = bpy.data.curves.new("txt", "FONT")
            cu.body = body
            if font or self.font:
                cu.font = font or self.font
            cu.size = 1.0
            cu.align_x = "CENTER"
            cu.align_y = "CENTER"
            cu.extrude = extrude
            cu.bevel_depth = min(0.018, extrude * 0.5) if bevel else 0.0
            cu.bevel_resolution = 0
            cu.resolution_u = self.prop.get("text_resolution", 2)
            cu.offset = offset
            ob = bpy.data.objects.new("txt", cu)
            self.collection.objects.link(ob)
            depsgraph.update()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))
            bpy.data.objects.remove(ob)
            bpy.data.curves.remove(cu)
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
            bm.normal_update()
            hidden = [f for f in bm.faces if f.normal.z < -0.7]
            bmesh.ops.delete(bm, geom=hidden, context="FACES")
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(4), verts=bm.verts, edges=bm.edges)
            bm.to_mesh(me)
            bm.free()
            return me

        base = build(0.0, 0.05, True)
        xs = [v.co.x for v in base.vertices]
        ys = [v.co.y for v in base.vertices]
        if not xs:
            bpy.data.meshes.remove(base)
            return None
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        scale = height / max(h, 1e-6)
        if max_w and w * scale > max_w:
            scale = max_w / w
        center = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0))
        z_scale = depth / 0.1 / scale
        world = (M or Matrix.Identity(4)) @ trs(loc, (math.pi / 2, 0, rot_z))
        layers = [(base, role, 0.0)]
        if outline_role:
            layers.append((build(outline * 0.5, 0.035, False), outline_role, depth * 0.55))
        made = []
        for me, layer_role, push in layers:
            me.transform(Matrix.Translation(-center))
            me.transform(Matrix.Diagonal((scale, scale, scale * z_scale, 1.0)))
            me.materials.clear()
            me.materials.append(self.material(layer_role))
            ob = bpy.data.objects.new("text", me)
            self.collection.objects.link(ob)
            ob.matrix_world = world @ Matrix.Translation((0, 0, -push))
            self.parts.append(ob)
            made.append(ob)
        return made

    def collider_from(self, world, size):
        corners = []
        for sx in (-0.5, 0.5):
            for sy in (-0.5, 0.5):
                for sz in (-0.5, 0.5):
                    corners.append(world @ Vector((sx * size[0], sy * size[1], sz * size[2])))
        lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
        hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
        self.colliders.append(((lo + hi) / 2, hi - lo))

    def skirt(self, w, d, z_top, role="accent", base=0.03, max_drop=0.18, drops_per_side=2, out=0.014, thick=0.02, sides=("front", "back", "left", "right"), bulbs=True, M=None, corner=0.08):
        hw, hd = w / 2.0, d / 2.0
        r = min(w, d) * corner
        segs = [
            ("front", (-hw + r, -hd), (hw - r, -hd), (0, -1)),
            ("right", (hw, -hd + r), (hw, hd - r), (1, 0)),
            ("back", (hw - r, hd), (-hw + r, hd), (0, 1)),
            ("left", (-hw, hd - r), (-hw, -hd + r), (-1, 0)),
        ]
        corner_centers = [(hw - r, -hd + r, -90), (hw - r, hd - r, 0), (-hw + r, hd - r, 90), (-hw + r, -hd + r, 180)]
        samples = []
        for (side, a, b, n), (cx, cy, start) in zip(segs, corner_centers):
            length = (Vector(b) - Vector(a)).length
            count = max(3, int(length / 0.025))
            for i in range(count):
                t = i / count
                samples.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, n[0], n[1], side))
            arc = max(2, int(math.pi * r / 2 / 0.025))
            for i in range(arc):
                ang = math.radians(start + 90.0 * i / arc)
                samples.append((cx + r * math.cos(ang), cy + r * math.sin(ang), math.cos(ang), math.sin(ang), side))
        s_acc = [0.0]
        for i in range(1, len(samples)):
            s_acc.append(s_acc[-1] + math.hypot(samples[i][0] - samples[i - 1][0], samples[i][1] - samples[i - 1][1]))
        total = s_acc[-1] + math.hypot(samples[0][0] - samples[-1][0], samples[0][1] - samples[-1][1])
        bumps = []
        for side_name, a, b, n in segs:
            if side_name not in sides:
                continue
            idx = [i for i, s in enumerate(samples) if s[4] == side_name]
            if not idx:
                continue
            s0, s1 = s_acc[idx[0]], s_acc[idx[-1]]
            for k in range(drops_per_side):
                c = s0 + (s1 - s0) * (k + 0.5) / drops_per_side + self.rng.uniform(-0.25, 0.25) * (s1 - s0) / drops_per_side
                bumps.append((c, max_drop * self.rng.uniform(0.45, 1.0), self.rng.uniform(0.025, 0.045)))

        def drop_at(s):
            v = base * (1.0 + 0.35 * math.sin(s * 23.0))
            for c, amp, wd in bumps:
                ds = min(abs(s - c), total - abs(s - c))
                v += amp * math.exp(-(ds / wd) ** 2)
            return v

        bm = bmesh.new()
        rows = []
        for (x, y, nx, ny, _), s in zip(samples, s_acc):
            drop = drop_at(s)
            row = [
                bm.verts.new((x - nx * out * 0.5, y - ny * out * 0.5, z_top + 0.012)),
                bm.verts.new((x + nx * out, y + ny * out, z_top - min(base, drop) * 0.4)),
                bm.verts.new((x + nx * out, y + ny * out, z_top - drop * 0.75)),
                bm.verts.new((x + nx * out * 0.7, y + ny * out * 0.7, z_top - drop)),
            ]
            rows.append(row)
        for i in range(len(rows)):
            a = rows[i]
            b = rows[(i + 1) % len(rows)]
            for k in range(3):
                bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        world = M or Matrix.Identity(4)
        self.add("skirt", bm, role, world, solidify=thick)
        if bulbs:
            for c, amp, wd in bumps:
                if amp < max_drop * 0.55:
                    continue
                i = min(range(len(s_acc)), key=lambda k: abs(s_acc[k] - c))
                x, y, nx, ny, _ = samples[i]
                rad = wd * 0.75
                z = z_top - drop_at(c) + rad * 0.55
                self.sphere(rad, (x + nx * out * 0.8, y + ny * out * 0.8, z), role, scale=(1, 1, 1.1), u=10, v=6, M=world)

    def curtain(self, x0, x1, z_top, y_front, role="accent", depth=0.025, base=0.025, max_drop=0.14, drops=3, M=None, bulbs=True):
        bumps = []
        for k in range(drops):
            c = x0 + (x1 - x0) * (k + 0.5) / drops + self.rng.uniform(-0.3, 0.3) * (x1 - x0) / drops
            bumps.append((c, max_drop * self.rng.uniform(0.45, 1.0), self.rng.uniform(0.025, 0.045)))

        def drop_at(x):
            v = base * (1.0 + 0.3 * math.sin(x * 31.0))
            for c, amp, wd in bumps:
                v += amp * math.exp(-((x - c) / wd) ** 2)
            return v

        n = max(6, int((x1 - x0) / 0.015))
        pts = [(x0, z_top + 0.02), (x1, z_top + 0.02)]
        for i in range(n + 1):
            x = x1 - (x1 - x0) * i / n
            pts.append((x, z_top - drop_at(x)))
        self.shape(pts, y_front - depth, y_front, role, bevel=0.006, M=M)
        if bulbs:
            for c, amp, wd in bumps:
                if amp < max_drop * 0.5:
                    continue
                rad = wd * 0.72
                self.sphere(rad, (c, y_front - depth * 0.5, z_top - drop_at(c) + rad * 0.5), role, scale=(1, 0.75, 1.1), u=10, v=6, M=M)

    def crown(self, loc, radius, height, role="gold", gem_role="primary", tilt=(0, 0, 0), spikes=5, M=None):
        group = (M or Matrix.Identity(4)) @ trs(loc, tilt)
        bm = bmesh.new()
        n = spikes * 6
        bottom = []
        top = []
        for i in range(n):
            a = math.tau * i / n - math.pi / 2
            phase = (i % 6) / 6.0
            h = height * (0.45 + 0.55 * max(0.0, 1.0 - abs(phase - 0.0 if phase < 0.5 else phase - 1.0) * 3.2))
            bottom.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), 0.0)))
            top.append(bm.verts.new((radius * 1.08 * math.cos(a), radius * 1.08 * math.sin(a), h)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self.add("crown", bm, role, group, solidify=radius * 0.12)
        self.cyl(radius * 1.04, height * 0.18, (0, 0, height * 0.09), role, segments=n, M=group)
        for i in range(spikes):
            a = math.tau * i / spikes - math.pi / 2
            self.sphere(radius * 0.13, (radius * 1.08 * math.cos(a), radius * 1.08 * math.sin(a), height * 1.02), role, u=10, v=6, M=group)
        self.sphere(radius * 0.22, (0, -radius * 1.06, height * 0.42), gem_role, scale=(1, 0.5, 1.15), u=8, v=6, M=group)

    def x_mark(self, center, direction, size, role="light", M=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(center) @ facing(direction)
        for angle in (math.pi / 4, -math.pi / 4):
            self.box((size, size * 0.3, size * 0.26), role=role, bevel=size * 0.08, matrix=base @ Matrix.Rotation(angle, 4, "Y"), segments=2)

    def star(self, loc, size, role="light", direction=(0, -1, 0), M=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        self.shape(star_outline(size, size * 0.32), -size * 0.08, size * 0.08, role, bevel=size * 0.03, matrix=base)

    def mascot(self, loc, radius, role="primary", eye_role="light", direction=(0, -1, 0), M=None, drips=True, tongue=True):
        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        self.sphere(radius, (0, 0, 0), role, scale=(1.0, 0.92, 0.95), u=20, v=12, M=group)
        for side in (-1, 1):
            d = Vector((side * 0.33, -1.0, 0.16)).normalized()
            p = Vector((d.x * radius, d.y * radius * 0.92, d.z * radius * 0.95)) * 0.97
            self.x_mark(p, d, radius * 0.4, eye_role, M=group)
        if tongue:
            self.sphere(radius * 0.16, (radius * 0.08, -radius * 0.86, -radius * 0.38), "accent", scale=(1.0, 0.6, 1.25), u=10, v=6, M=group)
        if drips:
            for x, length in ((-0.42, 0.22), (0.1, 0.34), (0.48, 0.16)):
                length *= radius
                y = -radius * 0.5
                z0 = -math.sqrt(max(0.0, 1.0 - x * x - 0.3)) * radius * 0.9
                self.cyl(radius * 0.11, length, (x * radius, y, z0 - length / 2), role, segments=10, radius2=radius * 0.09, M=group)
                self.sphere(radius * 0.13, (x * radius, y, z0 - length), role, scale=(1, 1, 1.15), u=10, v=6, M=group)


def build_sign_post(b, p):
    height = p.get("height", 2.45)
    board_role = p.get("board", "primary")
    b.box((0.8, 0.58, 0.05), (0, 0, 0.025), "primary", bevel=0.02)
    b.box((0.76, 0.54, 0.12), (0, 0, 0.11), "light", bevel=0.035, collide=True)
    b.box((0.62, 0.44, 0.1), (0, 0, 0.21), "light", bevel=0.03)
    b.box((0.24, 0.01, 0.05), (0, -0.276, 0.11), "dark", bevel=0.005)
    for x in (-0.07, 0.0, 0.07):
        b.box((0.035, 0.012, 0.03), (x, -0.282, 0.11), "glowtrim", bevel=0.004)
    pillar_top = height - 0.58
    ph = pillar_top - 0.26
    pz = 0.26 + ph / 2
    b.box((0.3, 0.26, ph), (0, 0, pz), "primary", bevel=0.03, collide=True)
    b.box((0.07, 0.012, ph * 0.82), (0.095, -0.131, pz - ph * 0.04), "light", bevel=0.006)
    b.box((0.055, 0.012, ph * 0.74), (-0.085, -0.131, pz - ph * 0.06), "dark", bevel=0.006)
    b.box((0.016, 0.014, ph * 0.66), (-0.085, -0.138, pz - ph * 0.06), "glowtrim", bevel=0.004)
    b.box((0.3, 0.012, 0.03), (0, -0.131, 0.36), "trim", bevel=0.004)
    sz = pillar_top - 0.2
    b.box((0.3, 0.13, 0.25), (0, -0.115, sz), "light", bevel=0.03)
    b.box((0.23, 0.012, 0.17), (0, -0.183, sz), "screen", bevel=0.01)
    b.x_mark((-0.055, -0.19, sz + 0.02), (0, -1, 0), 0.06, "glow")
    b.x_mark((0.055, -0.19, sz + 0.02), (0, -1, 0), 0.06, "glow")
    b.box((0.07, 0.01, 0.014), (0.01, -0.191, sz - 0.05), "glow", bevel=0.004)
    b.mascot((0, -0.17, 0.78), 0.085, "primary", "light", drips=False)
    b.crown((0, -0.17, 0.85), 0.05, 0.05, tilt=(0.2, 0, 0.15))
    bx = p.get("board_x", 0.22)
    bw, bh = p.get("board_w", 1.45), 0.56
    bz = height - 0.3
    group = Matrix.Translation((bx, 0, bz))
    outer = arrow_outline(bw, bh, 0.22, 0.12)
    b.shape(outer, -0.1, 0.1, "light", bevel=0.03, M=group, collide=True)
    inner = arrow_outline(bw - 0.12, bh - 0.12, 0.17, 0.08)
    b.shape(inner, -0.118, -0.095, board_role, bevel=0.01, M=group)
    b.shape(inner, 0.095, 0.118, board_role, bevel=0.01, M=group)
    for z in (0.06, -0.06):
        b.box((0.012, 0.12, 0.03), (-bw / 2 - 0.002, 0, z), "dark", bevel=0.004, M=group)
    icon = p.get("icon")
    label_x = -0.1 if icon else 0.02
    label_w = bw * (0.58 if icon else 0.8)
    sub = p.get("sub")
    label_h = 0.2 if not sub else 0.17
    label_z = 0.0 if not sub else 0.05
    text_role = p.get("text", "light")
    for side, y, rz in ((-1, -0.128, 0.0), (1, 0.128, math.pi)):
        gx = label_x
        b.text(p.get("label", "GARAGE"), label_h, (gx, y, label_z), text_role, depth=0.025, max_w=label_w, rot_z=rz, M=group)
        if sub:
            b.text(sub + "  >>", 0.075, (gx + 0.08 * (1 if side < 0 else -1), y, -0.13), p.get("sub_role", "primary" if board_role != "primary" else "accent"), depth=0.02, max_w=label_w * 0.6, outline_role="light", rot_z=rz, M=group)
    if icon:
        ix = bw / 2 - 0.24
        house = [(-0.11, -0.1), (0.11, -0.1), (0.11, 0.04), (0.0, 0.13), (-0.11, 0.04)]
        b.shape(house, -0.135, -0.115, "light", bevel=0.006, M=group @ Matrix.Translation((ix, 0, 0)))
        for k in range(3):
            b.box((0.15, 0.01, 0.022), (ix, -0.137, -0.065 + k * 0.04), board_role, bevel=0.003, M=group)
    b.curtain(-bw / 2 + 0.15, bw / 2 - 0.1, -bh / 2 + 0.02, -0.1, board_role, max_drop=0.16, drops=3, M=group)
    b.crown((bw / 2 - 0.22, 0, bh / 2 - 0.01), 0.1, 0.1, tilt=(0, 0.18, 0), M=group)


def build_kiosk_sign(b, p):
    b.box((0.92, 0.42, 0.12), (0, 0, 0.06), "dark", bevel=0.03, collide=True)
    b.box((0.94, 0.44, 0.02), (0, 0, 0.125), "trim", bevel=0.008)
    for x in (-0.36, 0.36):
        b.box((0.08, 0.012, 0.03), (x, -0.215, 0.06), "glow", bevel=0.004)
    pw, ph = 0.94, 1.12
    pz = 0.14 + ph / 2 + 0.02
    group = Matrix.Translation((0, 0, pz))
    b.shape(blob_outline(pw, ph, b.rng, wobble=0.012, lobes=3, lobe_amp=0.07), -0.07, 0.07, "accent", bevel=0.02, M=group, collide=True)
    inner = rounded_rect(pw - 0.16, ph - 0.2, 0.08)
    b.shape(inner, -0.088, -0.06, "primary", bevel=0.008, M=group @ Matrix.Translation((0, 0, -0.02)))
    b.shape(inner, 0.06, 0.088, "primary", bevel=0.008, M=group @ Matrix.Translation((0, 0, -0.02)))
    for y, rz in ((-0.094, 0.0), (0.094, math.pi)):
        b.text(p.get("label", "SHOP"), 0.15, (0, y, ph / 2 - 0.22), "light", depth=0.022, max_w=pw * 0.62, rot_z=rz, M=group)
        b.text(b.brand_short, 0.13, (0, y, 0.0), "accent", depth=0.022, max_w=pw * 0.62, rot_z=rz, M=group)
        b.star((0.3 * (1 if rz == 0 else -1), y, 0.14), 0.04, "light", (0, -1 if rz == 0 else 1, 0), M=group)
    b.mascot((0, -0.1, -0.27), 0.11, "primary", "light", drips=False, M=group)
    b.crown((0, -0.1, -0.18), 0.055, 0.05, tilt=(0.2, 0, -0.2), M=group)


def build_atm(b, p):
    b.box((0.96, 0.76, 0.14), (0, 0, 0.07), "dark", bevel=0.035, collide=True)
    for x in (-0.38, 0.38):
        b.box((0.08, 0.012, 0.03), (x, -0.382, 0.07), "glow", bevel=0.004)
    w, d, h = 0.82, 0.62, 1.5
    zc = 0.14 + h / 2
    group = Matrix.Translation((0, 0, zc))
    b.shape(blob_outline(w, h, b.rng, wobble=0.014, lobes=3, lobe_amp=0.08, corner=0.16), -d / 2, d / 2, "accent", bevel=0.035, M=group, collide=True)
    front = blob_outline(w - 0.14, h - 0.2, b.rng, wobble=0.01, lobes=2, lobe_amp=0.03, corner=0.12)
    b.shape(front, -d / 2 - 0.012, -d / 2 + 0.03, "primary", bevel=0.01, M=group @ Matrix.Translation((0, 0, -0.04)))
    for x in (-w / 2 - 0.012, w / 2 + 0.012):
        b.box((0.012, d - 0.16, h - 0.36), (x, 0, -0.06), "primary", bevel=0.006, M=group)
    for x, rz in ((-w / 2 - 0.022, -math.pi / 2), (w / 2 + 0.022, math.pi / 2)):
        b.text(b.brand_short, 0.1, (x, 0, -0.1), "accent", depth=0.018, max_w=d * 0.7, rot_z=rz, M=group)
    b.text(p.get("label", "ATM"), 0.15, (0, -d / 2 - 0.02, h / 2 - 0.17), "light", depth=0.025, max_w=w * 0.6, M=group)
    sz = 0.22
    b.box((0.52, 0.05, 0.36), (0, -d / 2 - 0.01, sz), "dark", bevel=0.02, M=group)
    b.box((0.44, 0.012, 0.28), (0, -d / 2 - 0.04, sz + 0.005), "screen", bevel=0.006, M=group)
    b.text(b.brand, 0.05, (0, -d / 2 - 0.05, sz + 0.05), "glow", depth=0.006, max_w=0.3, outline_role=None, M=group)
    for k, x in enumerate((-0.12, 0.0, 0.12)):
        b.box((0.07, 0.008, 0.045), (x, -d / 2 - 0.048, sz - 0.07), "glowtrim" if k == 1 else "glow", bevel=0.004, M=group)
    kz = -0.1
    b.box((0.54, 0.05, 0.22), (0, -d / 2 - 0.01, kz), "dark", bevel=0.015, M=group)
    for r in range(4):
        for c in range(3):
            b.box((0.032, 0.018, 0.03), (-0.2 + c * 0.042, -d / 2 - 0.042, kz + 0.07 - r * 0.042), "light", bevel=0.006, segments=2, M=group)
    for k, role in enumerate(("accent", "trim", "light")):
        b.box((0.06, 0.02, 0.035), (0.0, -d / 2 - 0.042, kz + 0.06 - k * 0.055), role, bevel=0.006, segments=2, M=group)
    b.box((0.13, 0.07, 0.16), (0.17, -d / 2 - 0.02, kz), "light", bevel=0.02, M=group)
    b.box((0.08, 0.012, 0.012), (0.17, -d / 2 - 0.058, kz + 0.04), "dark", bevel=0.003, M=group)
    for i in range(3):
        b.torus(0.012 + i * 0.012, 0.003, (0.17, -d / 2 - 0.058, kz - 0.025), "dark", seg_major=12, seg_minor=4, M=group)
    b.box((0.48, 0.05, 0.08), (0, -d / 2 - 0.01, -0.36), "dark", bevel=0.015, M=group)
    b.box((0.36, 0.012, 0.014), (0, -d / 2 - 0.04, -0.36), "glow", bevel=0.004, M=group)
    b.star((-w / 2 + 0.03, -d / 2 - 0.03, -0.45), 0.035, "light", M=group)


def build_safe(b, p):
    w, d, h = p.get("w", 1.0), p.get("d", 0.86), p.get("h", 0.95)
    for x in (-w / 2 + 0.1, w / 2 - 0.1):
        for y in (-d / 2 + 0.1, d / 2 - 0.1):
            b.box((0.12, 0.12, 0.05), (x, y, 0.025), "dark", bevel=0.015)
    b.box((w, d, h - 0.05), (0, 0, 0.05 + (h - 0.05) / 2), "primary", bevel=0.06, collide=True)
    b.box((w + 0.03, d + 0.03, 0.06), (0, 0, h + 0.01), "accent", bevel=0.03)
    b.skirt(w + 0.03, d + 0.03, h - 0.015, "accent", base=0.03, max_drop=0.2, drops_per_side=2, out=0.012)
    dz = 0.05 + (h - 0.05) * 0.5
    fy = -d / 2
    dx = -0.06
    b.cyl(0.26, 0.03, (dx, fy - 0.012, dz), "dark", axis="Y", segments=32)
    b.torus(0.27, 0.042, (dx, fy - 0.03, dz), "light", seg_major=32, seg_minor=8)
    b.cyl(0.085, 0.08, (dx, fy - 0.05, dz), "light", axis="Y", segments=20, bevel=0.01)
    b.cyl(0.05, 0.05, (dx, fy - 0.09, dz), "primary", axis="Y", segments=16, bevel=0.008)
    for k in range(3):
        a = k * math.pi / 3
        b.box((0.44, 0.035, 0.05), role="light", bevel=0.015, matrix=trs((dx, fy - 0.06, dz), (0, a, 0)))
        for s in (-1, 1):
            b.sphere(0.035, (dx + s * 0.22 * math.cos(a), fy - 0.06, dz - s * 0.22 * math.sin(a)), "accent", u=10, v=6)
    for z in (dz - 0.18, dz + 0.18):
        b.cyl(0.03, 0.12, (dx - 0.29, fy - 0.02, z), "dark", segments=10)
    kx = w / 2 - 0.13
    b.box((0.14, 0.03, 0.24), (kx, fy - 0.01, dz + 0.02), "light", bevel=0.015)
    b.box((0.1, 0.008, 0.04), (kx, fy - 0.028, dz + 0.1), "screen", bevel=0.004)
    for r in range(3):
        for c in range(3):
            b.box((0.025, 0.012, 0.022), (kx - 0.03 + c * 0.03, fy - 0.028, dz + 0.03 - r * 0.035), "dark", bevel=0.004, segments=2)
    for x, rz in ((-w / 2 - 0.012, -math.pi / 2), (w / 2 + 0.012, math.pi / 2)):
        b.text(b.brand, 0.13, (x, 0, h * 0.5), "accent", depth=0.022, max_w=d * 0.7, rot_z=rz)
    b.text(p.get("label", "SAFE"), 0.07, (dx, fy - 0.02, 0.11), "light", depth=0.018, max_w=0.3)
    b.star((-w / 2 + 0.09, fy - 0.01, 0.2), 0.04, "light")
    b.star((w / 2 - 0.1, fy - 0.01, 0.2), 0.035, "light")
    b.crown((w / 2 - 0.16, d / 2 - 0.2, h + 0.03), 0.1, 0.1, tilt=(0, -0.1, 0.3))


def build_crate(b, p):
    w, d, h = p.get("w", 1.3), p.get("d", 1.06), p.get("h", 1.0)
    for x in (-w / 2 + 0.16, w / 2 - 0.16):
        for y in (-d / 2 + 0.12, d / 2 - 0.12):
            b.box((0.24, 0.14, 0.06), (x, y, 0.03), "light", bevel=0.02)
    body_h = h - 0.06
    zc = 0.06 + body_h / 2
    b.box((w - 0.06, d - 0.06, body_h - 0.04), (0, 0, zc), "primary", bevel=0.02, collide=True)
    t = 0.11
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((t, t, body_h), (sx * (w / 2 - t / 2), sy * (d / 2 - t / 2), zc), "dark", bevel=0.02)
            if sy < 0:
                b.box((0.02, 0.012, body_h * 0.5), (sx * (w / 2 - t * 0.5), -d / 2 - 0.002, zc), "glow", bevel=0.004)
    for z in (0.06 + t / 2, h - t / 2):
        for sy in (-1, 1):
            b.box((w, t, t), (0, sy * (d / 2 - t / 2), z), "dark", bevel=0.02)
        for sx in (-1, 1):
            b.box((t, d, t), (sx * (w / 2 - t / 2), 0, z), "dark", bevel=0.02)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.06 + 0.09, h - 0.08):
                b.box((0.2, 0.2, 0.17), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), z), "accent", bevel=0.045)
    b.box((w - 0.2, d - 0.2, 0.03), (0, 0, h - 0.01), "primary", bevel=0.01)
    b.box((w * 0.9, 0.14, 0.035), (0, 0, h + 0.012), "accent", bevel=0.015)
    b.box((0.14, d * 0.9, 0.035), (0, 0, h + 0.012), "accent", bevel=0.015)
    b.curtain(-0.2, 0.25, h - 0.03, -d / 2 + 0.01, "accent", max_drop=0.2, drops=2)
    fy = -d / 2 + 0.03
    hx = -w / 2 + 0.34
    b.box((0.26, 0.04, 0.05), (hx, fy - 0.03, zc + 0.12), "light", bevel=0.015)
    b.box((0.26, 0.04, 0.05), (hx, fy - 0.03, zc - 0.06), "light", bevel=0.015)
    for x in (hx - 0.11, hx + 0.11):
        b.box((0.05, 0.04, 0.23), (x, fy - 0.03, zc + 0.03), "light", bevel=0.015)
    b.box((0.16, 0.03, 0.14), (hx, fy - 0.015, zc + 0.03), "dark", bevel=0.01)
    b.mascot((hx, fy - 0.01, zc - 0.25), 0.11, "primary", "light", drips=False)
    b.text(b.brand, 0.17, (0.22, fy - 0.03, zc - 0.05), "accent", depth=0.025, max_w=0.62)
    b.crown((hx, fy - 0.04, zc - 0.165), 0.055, 0.055, tilt=(0.25, 0, 0.2))
    for side in (-1, 1):
        sx = side * (w / 2 - 0.03)
        b.box((0.04, 0.26, 0.05), (sx + side * 0.03, 0, zc + 0.1), "light", bevel=0.015)
        b.box((0.04, 0.26, 0.05), (sx + side * 0.03, 0, zc - 0.05), "light", bevel=0.015)
        for y in (-0.11, 0.11):
            b.box((0.04, 0.05, 0.2), (sx + side * 0.03, y, zc + 0.025), "light", bevel=0.015)
    for x in (-w / 2 + 0.26, w / 2 - 0.26):
        b.box((0.1, 0.05, 0.08), (x, -d / 2 + 0.01, h - 0.08), "light", bevel=0.015)
    b.star((w / 2 - 0.22, fy - 0.02, zc - 0.3), 0.04, "light")


def build_chest(b, p):
    w, d, h = p.get("w", 0.74), p.get("d", 0.5), p.get("h", 0.42)
    b.box((w + 0.05, d + 0.05, 0.07), (0, 0, 0.035), "accent", bevel=0.03)
    b.box((w, d, h - 0.05), (0, 0, 0.05 + (h - 0.05) / 2), "primary", bevel=0.04, collide=True)
    b.box((w - 0.06, d - 0.06, 0.012), (0, 0, h + 0.004), "dark", bevel=0.004)
    b.skirt(w + 0.006, d + 0.006, h - 0.005, "accent", base=0.02, max_drop=0.13, drops_per_side=2, out=0.01, thick=0.016)
    for side in (-1, 1):
        sx = side * (w / 2 + 0.02)
        b.box((0.03, 0.2, 0.035), (sx, 0, h * 0.62), "light", bevel=0.01)
        for y in (-0.085, 0.085):
            b.box((0.03, 0.03, 0.09), (sx, y, h * 0.55), "light", bevel=0.01)
    b.box((0.1, 0.03, 0.08), (0, -d / 2 - 0.012, h - 0.06), "light", bevel=0.012)
    b.box((0.03, 0.01, 0.03), (0, -d / 2 - 0.03, h - 0.07), "dark", bevel=0.004)
    b.text(b.brand, 0.07, (0.12, -d / 2 - 0.012, h * 0.42), "accent", depth=0.016, max_w=w * 0.45)
    b.mascot((-0.2, -d / 2 - 0.005, h * 0.45), 0.065, "primary", "light", drips=False)
    angle = math.radians(p.get("open", 40))
    lid = Matrix.Translation((0, d / 2, h)) @ Matrix.Rotation(-angle, 4, "X") @ Matrix.Translation((0, -d / 2, 0.035))
    b.box((w + 0.02, d + 0.02, 0.07), role="primary", bevel=0.03, M=lid)
    b.box((w - 0.04, d - 0.04, 0.01), (0, 0, -0.037), "accent", bevel=0.004, M=lid)
    b.box((w + 0.04, 0.04, 0.03), (0, -d / 2, 0.0), "accent", bevel=0.012, M=lid)
    b.text(b.brand_short, 0.07, (0, 0, 0), "accent", depth=0.014, max_w=w * 0.5, M=lid @ Matrix.Translation((0, -0.02, 0.036)) @ Matrix.Rotation(-math.pi / 2, 4, "X"))
    rng = b.rng
    for k in range(p.get("coins", 40)):
        x = rng.uniform(-w / 2 + 0.07, w / 2 - 0.07)
        y = rng.uniform(-d / 2 + 0.07, d / 2 - 0.07)
        u = max(abs(x) / (w / 2), abs(y) / (d / 2))
        z = h + 0.01 + 0.08 * max(0.0, 1.0 - u * u) + rng.uniform(0, 0.012)
        b.cyl(0.032, 0.008, (x, y, z), "gold", segments=10, rot=(rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0))
    for x, y, rz in ((-0.08, 0.02, 0.3), (0.1, -0.03, -0.4)):
        b.box((0.16, 0.07, 0.04), (x, y, h + 0.06), "gold", bevel=0.012, rot=(0.1, 0.05, rz))


def build_workbench(b, p):
    w, d, top = p.get("w", 2.0), p.get("d", 0.8), p.get("top", 0.95)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.09, 0.09, top - 0.06), (sx * (w / 2 - 0.07), sy * (d / 2 - 0.07), (top - 0.06) / 2 + 0.05), "light", bevel=0.015)
            b.box((0.16, 0.16, 0.06), (sx * (w / 2 - 0.07), sy * (d / 2 - 0.07), 0.03), "primary", bevel=0.02)
    b.box((w, d, 0.07), (0, 0, top - 0.035), "light", bevel=0.02, collide=True)
    b.box((w + 0.01, 0.03, 0.05), (0, -d / 2 - 0.005, top - 0.04), "accent", bevel=0.01)
    b.box((w * 0.55, d * 0.55, 0.012), (0, -0.04, top + 0.006), "primary", bevel=0.004)
    b.box((w * 0.55 + 0.02, 0.012, 0.016), (0, -0.04 - d * 0.275, top + 0.008), "glow", bevel=0.003)
    b.curtain(-0.35, 0.35, top - 0.06, -d / 2 - 0.02, "accent", max_drop=0.16, drops=3)
    for sx in (-1, 1):
        cx = sx * (w / 2 - 0.36)
        b.box((0.5, d - 0.14, 0.66), (cx, 0, 0.1 + 0.33), "light", bevel=0.02, collide=True)
        for k in range(2):
            z = 0.26 + k * 0.32
            role = "primary" if k == 0 else "accent"
            b.box((0.44, 0.03, 0.26), (cx, -d / 2 + 0.06, z), role, bevel=0.02)
            b.box((0.16, 0.03, 0.03), (cx, -d / 2 + 0.035, z + 0.05), "light" if role == "accent" else "accent", bevel=0.01)
    b.box((w - 1.2, d - 0.2, 0.03), (0, 0.04, 0.14), "light", bevel=0.01)
    b.box((w - 1.22, 0.03, 0.62), (0, -d / 2 + 0.1, 0.45), "primary", bevel=0.01)
    blob = blob_outline(0.42, 0.34, b.rng, wobble=0.012, lobes=2, lobe_amp=0.04)
    b.shape(blob, -d / 2 + 0.05, -d / 2 + 0.08, "accent", bevel=0.01, loc=(0, 0, 0.5))
    b.mascot((0, -d / 2 + 0.02, 0.5), 0.13, "primary", "light", drips=False)
    b.crown((0.03, -d / 2 + 0.02, 0.6), 0.07, 0.065, tilt=(0.25, 0, -0.2))
    by = d / 2 - 0.06
    bh = 0.78
    bz = top + bh / 2
    b.box((w - 0.16, 0.05, bh), (0, by, bz), "wood", bevel=0.015, collide=True)
    b.box((w - 0.1, 0.06, 0.04), (0, by, top + bh), "primary", bevel=0.012)
    for r in range(5):
        for c in range(14):
            b.cyl(0.009, 0.01, (-w / 2 + 0.2 + c * ((w - 0.4) / 13), by - 0.028, top + 0.14 + r * 0.12), "dark", axis="Y", segments=6)
    for sx in (-1, 1):
        x = sx * (w / 2 - 0.05)
        b.box((0.08, 0.08, bh + 0.12), (x, by, top + (bh + 0.12) / 2), "primary", bevel=0.02)
        b.sphere(0.06, (x, by, top + bh + 0.16), "primary", u=12, v=8)
        b.sphere(0.025, (x, by - 0.045, top + bh + 0.16), "accent", u=8, v=6)
    b.box((w - 0.3, 0.16, 0.025), (0, by - 0.1, top + 0.62), "light", bevel=0.008)
    jar_roles = ("primary", "accent", "trim", "light", "primary", "accent")
    for k, role in enumerate(jar_roles):
        x = -w / 2 + 0.3 + k * 0.26
        b.cyl(0.035, 0.08, (x, by - 0.1, top + 0.672), role, segments=12, bevel=0.006)
        b.cyl(0.038, 0.015, (x, by - 0.1, top + 0.72), "light", segments=12)
    ty = by - 0.04
    b.box((0.03, 0.02, 0.26), (-0.55, ty, top + 0.32), "dark", bevel=0.008)
    b.box((0.14, 0.04, 0.05), (-0.55, ty, top + 0.45), "metal", bevel=0.01)
    b.box((0.03, 0.015, 0.22), (-0.3, ty, top + 0.33), "metal", bevel=0.006)
    b.torus(0.04, 0.012, (-0.3, ty, top + 0.46), "metal", seg_major=12, seg_minor=6)
    b.cyl(0.012, 0.16, (0.32, ty, top + 0.38), "metal", segments=8)
    b.cyl(0.022, 0.1, (0.32, ty, top + 0.26), "accent", segments=10, bevel=0.006)
    b.box((0.18, 0.02, 0.12), (0.6, ty, top + 0.35), "primary", bevel=0.01)
    b.box((0.12, 0.022, 0.05), (0.6, ty - 0.002, top + 0.35), "light", bevel=0.006)
    hz = top + bh + 0.24
    head = Matrix.Translation((0, by - 0.02, hz))
    b.shape(blob_outline(1.2, 0.38, b.rng, wobble=0.012, lobes=3, lobe_amp=0.06), -0.05, 0.05, "accent", bevel=0.015, M=head)
    b.shape(rounded_rect(1.06, 0.26, 0.06), -0.062, -0.045, "primary", bevel=0.006, M=head @ Matrix.Translation((0, 0, -0.01)))
    b.text(b.brand, 0.17, (0, -0.066, -0.01), "light", depth=0.022, max_w=0.8, M=head)
    b.crown((0, 0, 0.2), 0.08, 0.08, M=head)
    for sx in (-1, 1):
        b.star((sx * 0.52, -0.066, 0.1), 0.04, "accent", M=head)


def build_mascot_marker(b, p):
    r = p.get("radius", 0.34)
    zc = r * 1.42
    b.mascot((0, 0, zc), r, "primary", "light")
    b.crown((r * 0.18, 0, zc + r * 0.72), r * 0.55, r * 0.5, tilt=(0, 0.32, 0))
    b.star((-r * 1.35, -0.02, zc + r * 0.55), r * 0.16, "accent")
    b.star((r * 1.3, -0.02, zc - r * 0.2), r * 0.12, "light")
    rng = b.rng
    for k in range(5):
        a = math.tau * k / 5 + rng.uniform(-0.3, 0.3)
        rr = r * rng.uniform(1.25, 1.6)
        b.sphere(r * rng.uniform(0.05, 0.08), (rr * math.cos(a), rr * math.sin(a) * 0.5, zc + rng.uniform(-0.2, 0.4) * r), "accent", scale=(1, 1, 1.4), u=8, v=6)


ARCHETYPES = {
    "sign_post": build_sign_post,
    "kiosk_sign": build_kiosk_sign,
    "atm": build_atm,
    "safe": build_safe,
    "crate": build_crate,
    "chest": build_chest,
    "workbench": build_workbench,
    "mascot_marker": build_mascot_marker,
}


def apply_and_join(b):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for ob in b.parts:
        if ob.modifiers:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
            old = ob.data
            ob.modifiers.clear()
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
    root = b.parts[0]
    with bpy.context.temp_override(active_object=root, object=root, selected_objects=b.parts, selected_editable_objects=b.parts):
        bpy.ops.object.join()
    root.data.transform(root.matrix_world)
    root.matrix_world = Matrix.Identity(4)
    root.name = b.id
    root.data.name = b.id
    for coll in list(root.users_collection):
        coll.objects.unlink(root)
    bpy.context.scene.collection.objects.link(root)
    bpy.data.collections.remove(b.collection)
    bm = bmesh.new()
    bm.from_mesh(root.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
    bmesh.ops.dissolve_degenerate(bm, dist=0.00002, edges=bm.edges)
    tiny = [f for f in bm.faces if f.calc_area() < 1e-9]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if not e.is_manifold or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(38)):
            e.smooth = False
    bm.to_mesh(root.data)
    bm.free()
    root.data.update()
    return root


def palette_finish(b, root, out_dir):
    roles = []
    for slot in root.material_slots:
        role = slot.material.get("prop_forge_role", slot.material.name) if slot.material else "primary"
        roles.append(role)
    unique = list(DEFAULT_PALETTE) + sorted(k for k in b.palette if k not in DEFAULT_PALETTE)
    for role in roles:
        if role not in unique:
            unique.append(role)
    unique = unique[:64]
    cell = 32
    grid = 8
    size = cell * grid
    pixels = [0.0] * (size * size * 4)
    swatch_uv = {}
    for idx, role in enumerate(unique):
        gx, gy = idx % grid, idx // grid
        rgb = hex_rgb(b.palette.get(role, "#FF00FF"))
        for y in range(gy * cell, (gy + 1) * cell):
            for x in range(gx * cell, (gx + 1) * cell):
                o = (y * size + x) * 4
                pixels[o:o + 4] = [rgb[0], rgb[1], rgb[2], 1.0]
        swatch_uv[role] = ((gx + 0.5) / grid, (gy + 0.5) / grid)
    tex_name = (b.spec.get("set") or b.id) + "_palette"
    if b.prop.get("palette"):
        tex_name = b.id + "_palette"
    image = bpy.data.images.new(tex_name, size, size, alpha=False)
    image.pixels.foreach_set(pixels)
    path = os.path.join(out_dir, tex_name + ".png")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    me = root.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        u, v = swatch_uv[roles[poly.material_index]]
        jitter = 0.18 / grid
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (u + math.sin(co.x * 13 + co.z * 7) * jitter * 0.5, v + math.cos(co.y * 11 + co.z * 5) * jitter * 0.5)
    rebuild_materials(b, root, roles, image)
    return path


def rebuild_materials(b, root, roles, image):
    diffuse = new_game_material(b.id + "_diffuse", image, emissive=False)
    emissive = None
    remap = []
    for role in roles:
        if role in EMISSIVE_ROLES:
            if emissive is None:
                emissive = new_game_material(b.id + "_emissive", image, emissive=True)
            remap.append(1)
        else:
            remap.append(0)
    me = root.data
    old_index = [p.material_index for p in me.polygons]
    me.materials.clear()
    me.materials.append(diffuse)
    if emissive:
        me.materials.append(emissive)
    for poly, idx in zip(me.polygons, old_index):
        poly.material_index = remap[idx] if emissive else 0
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def new_game_material(name, image, emissive):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    tex.location = (-400, 200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.38
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.2
    if emissive:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
    mat["prop_forge_shader"] = "emissive.sps" if emissive else "default.sps"
    return mat


def bake_finish(b, root, out_dir, size):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    roles = [slot.material.get("prop_forge_role", "primary") for slot in root.material_slots]
    me = root.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = root
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == root)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    image = bpy.data.images.new(b.id + "_atlas", size, size, alpha=False)
    for slot in root.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = image
        nt.nodes.active = node
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    scene.render.bake.margin = 6
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=6, use_clear=True)
    path = os.path.join(out_dir, b.id + "_atlas.png")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    rebuild_materials(b, root, roles, image)
    for mat in root.data.materials:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.interpolation = "Linear"
    return path


def add_decals(b, root, decals, spec_dir):
    lo, hi = bbox(root)
    made = []
    for i, dec in enumerate(decals):
        img_path = dec["image"] if os.path.isabs(dec["image"]) else os.path.join(spec_dir, dec["image"])
        if not os.path.exists(img_path):
            b.warnings.append("decal image missing: " + img_path)
            continue
        side = dec.get("side", "front")
        cu, cz = dec.get("center", [0.0, (lo.z + hi.z) / 2])
        width = dec.get("width", 0.4)
        image = bpy.data.images.load(img_path, check_existing=True)
        aspect = image.size[1] / max(1, image.size[0])
        height = dec.get("height", width * aspect)
        gap = dec.get("offset", 0.004)
        place = {
            "front": ((cu, dec.get("y", lo.y) - gap, cz), (math.pi / 2, 0, 0)),
            "back": ((cu, dec.get("y", hi.y) + gap, cz), (math.pi / 2, 0, math.pi)),
            "left": ((dec.get("x", lo.x) - gap, cu, cz), (math.pi / 2, 0, -math.pi / 2)),
            "right": ((dec.get("x", hi.x) + gap, cu, cz), (math.pi / 2, 0, math.pi / 2)),
            "top": ((cu, cz, dec.get("z", hi.z) + gap), (0, 0, 0)),
        }[side]
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(width, height, 1), verts=bm.verts)
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for loop in f.loops:
                loop[uv].uv = (loop.vert.co.x / width + 0.5, loop.vert.co.y / height + 0.5)
        me = bpy.data.meshes.new("{}_decal_{}".format(b.id, i))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = trs(place[0], place[1])
        mat = bpy.data.materials.new(me.name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        try:
            mat.blend_method = "CLIP"
        except Exception:
            pass
        mat["prop_forge_shader"] = "decal.sps"
        me.materials.append(mat)
        made.append(ob)
    if made:
        objs = [root] + made
        with bpy.context.temp_override(active_object=root, object=root, selected_objects=objs, selected_editable_objects=objs):
            bpy.ops.object.join()
        root.data.transform(root.matrix_world)
        root.matrix_world = Matrix.Identity(4)


def bbox(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def recentre(root, archetype):
    lo, hi = bbox(root)
    shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    root.data.transform(Matrix.Translation(shift))
    return shift


def make_colliders(b, root, shift):
    coll = bpy.data.collections.new(b.id + "_collision")
    bpy.context.scene.collection.children.link(coll)
    made = []
    for i, (center, size) in enumerate(b.colliders):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=size, verts=bm.verts)
        me = bpy.data.meshes.new("{}_col_{}".format(b.id, i))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        coll.objects.link(ob)
        ob.location = center + shift
        ob.display_type = "WIRE"
        ob.hide_render = True
        ob["prop_forge_collision"] = "box"
        made.append(ob)
    return made


def tris_of(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def purge():
    try:
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass


def setup_render(scene, samples, res):
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.eevee.taa_render_samples = samples
        scene.eevee.use_shadows = True
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "Medium High Contrast"
    except Exception:
        pass
    world = bpy.data.worlds.new("pf_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.62, 0.72, 0.86, 1.0)
    bg.inputs["Strength"].default_value = 0.9
    scene.world = world
    sun_data = bpy.data.lights.new("pf_sun", "SUN")
    sun_data.energy = 3.2
    sun_data.angle = math.radians(4)
    sun = bpy.data.objects.new("pf_sun", sun_data)
    sun.rotation_euler = (math.radians(48), math.radians(8), math.radians(-35))
    scene.collection.objects.link(sun)
    fill_data = bpy.data.lights.new("pf_fill", "AREA")
    fill_data.energy = 400
    fill_data.size = 6
    fill = bpy.data.objects.new("pf_fill", fill_data)
    fill.location = (-4, -6, 4)
    fill.rotation_euler = Vector((-4, -6, 4)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(fill)
    ground_me = bpy.data.meshes.new("pf_ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    bm.to_mesh(ground_me)
    bm.free()
    ground = bpy.data.objects.new("pf_ground", ground_me)
    gmat = bpy.data.materials.new("pf_ground")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = (0.2, 0.19, 0.18, 1.0)
    gb.inputs["Roughness"].default_value = 0.95
    ground_me.materials.append(gmat)
    scene.collection.objects.link(ground)
    return [sun, fill, ground]


def render_objects(objs, path, samples=32, res=(900, 900), direction=(0.78, -1.0, 0.5), fit=0.92):
    scene = bpy.context.scene
    helpers = setup_render(scene, samples, res)
    pts = []
    for ob in objs:
        lo, hi = bbox(ob)
        pts += [lo, hi]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) / 2
    radius = (hi - lo).length / 2
    cam_data = bpy.data.cameras.new("pf_cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("pf_cam", cam_data)
    scene.collection.objects.link(cam)
    aspect = res[0] / res[1]
    fov = 2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)
    if aspect < 1:
        fov *= aspect
    dist = radius / math.sin(fov / 2) * (fit if aspect >= 1 else 1.0)
    d = Vector(direction).normalized()
    cam.location = center + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_data.clip_end = dist * 4
    scene.camera = cam
    scene.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
    except Exception:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        bpy.ops.render.render(write_still=True)
    for ob in helpers + [cam]:
        bpy.data.objects.remove(ob)


def build_prop(spec, prop, out_dir, spec_dir, args):
    clean_scene()
    archetype = prop["archetype"]
    if archetype not in ARCHETYPES:
        raise SystemExit("unknown archetype {} (known: {})".format(archetype, ", ".join(ARCHETYPES)))
    b = PropBuilder(spec, prop)
    ARCHETYPES[archetype](b, prop)
    part_count = len(b.parts)
    root = apply_and_join(b)
    shift = recentre(root, archetype)
    if args.bake:
        texture = bake_finish(b, root, out_dir, args.bake)
    else:
        texture = palette_finish(b, root, out_dir)
    if prop.get("decals"):
        add_decals(b, root, prop["decals"], spec_dir)
    colliders = [] if archetype == "mascot_marker" or prop.get("collision") is False else make_colliders(b, root, shift)
    lo, hi = bbox(root)
    tris = tris_of(root)
    budget = prop.get("budget", TRIS_BUDGET.get(archetype, 10000))
    if tris > budget:
        b.warnings.append("tris {} over budget {}".format(tris, budget))
    meta = {
        "id": b.id,
        "archetype": archetype,
        "set": spec.get("set", ""),
        "size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
        "tris": tris,
        "budget": budget,
        "parts": part_count,
        "materials": [m.name for m in root.data.materials],
        "shaders": [m.get("prop_forge_shader", "") for m in root.data.materials],
        "texture": os.path.basename(texture),
        "colliders": len(colliders),
        "lod_dist": prop.get("lod_dist", 120 if archetype in ("sign_post", "workbench", "atm") else 80),
        "warnings": b.warnings,
    }
    root["prop_forge"] = json.dumps(meta)
    purge()
    blend_path = os.path.join(out_dir, b.id + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=False)
    if not args.no_render:
        render_objects([root], os.path.join(out_dir, b.id + "_preview.png"), samples=args.samples)
    meta["blend"] = os.path.basename(blend_path)
    print("PROP_FORGE " + json.dumps(meta))
    return meta


def render_lineup(metas, out_dir, samples):
    clean_scene()
    objs = []
    x = 0.0
    for meta in metas:
        path = os.path.join(out_dir, meta["blend"])
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [meta["id"]]
        ob = dst.objects[0]
        bpy.context.scene.collection.objects.link(ob)
        width = meta["size_m"][0]
        ob.location.x = x + width / 2
        x += width + 0.5
        objs.append(ob)
    for ob in objs:
        ob.location.x -= x / 2
    bpy.context.view_layer.update()
    render_objects(objs, os.path.join(out_dir, "lineup.png"), samples=samples, res=(1920, 820), direction=(0.3, -1.0, 0.4), fit=1.12)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=False)
    ap.add_argument("--out", required=False)
    ap.add_argument("--only", default="")
    ap.add_argument("--bake", type=int, default=0)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--lineup", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list:
        print("archetypes: " + ", ".join(ARCHETYPES))
        print("roles: " + ", ".join(DEFAULT_PALETTE))
        return
    if not args.spec or not args.out:
        raise SystemExit("--spec and --out are required")
    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    spec_dir = os.path.dirname(os.path.abspath(args.spec))
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    metas = []
    for prop in spec["props"]:
        if only and prop["id"] not in only:
            continue
        metas.append(build_prop(spec, prop, out_dir, spec_dir, args))
    report_path = os.path.join(out_dir, "report.json")
    previous = []
    if only and os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as fh:
            previous = [m for m in json.load(fh) if m["id"] not in only]
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(previous + metas, fh, indent=2)
    if args.lineup and not args.no_render:
        everything = previous + metas
        order = [p["id"] for p in spec["props"]]
        everything.sort(key=lambda m: order.index(m["id"]) if m["id"] in order else 999)
        render_lineup(everything, out_dir, args.samples)
    warn = sum(len(m["warnings"]) for m in metas)
    print("RESULT props={} warnings={}".format(len(metas), warn))


if __name__ == "__main__":
    main()
