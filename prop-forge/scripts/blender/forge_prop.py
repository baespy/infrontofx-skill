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
import colorsys
from contextlib import contextmanager
import json
import math
import os
import random
import sys
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

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
    "sign_post": 15000,
    "kiosk_sign": 11000,
    "atm": 12000,
    "safe": 14000,
    "crate": 12000,
    "chest": 10000,
    "workbench": 18000,
    "mascot_marker": 6000,
    "airdrop": 15000,
    "powerbox": 15000,
    "parking": 15000,
    "redbox": 13000,
    "waterpipe": 13000,
    "gachapon": 14000,
    "washmoney": 14000,
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


def smooth_pts(pts, passes=2, closed=True):
    cur = list(pts)
    for _ in range(passes):
        n = len(cur)
        if n < 4:
            break
        nxt = []
        for i in range(n):
            if not closed and (i == 0 or i == n - 1):
                nxt.append(cur[i])
                continue
            p0 = cur[(i - 1) % n]
            p1 = cur[i]
            p2 = cur[(i + 1) % n]
            nxt.append((0.25 * p0[0] + 0.5 * p1[0] + 0.25 * p2[0], 0.25 * p0[1] + 0.5 * p1[1] + 0.25 * p2[1]))
        cur = nxt
    return cur


def inset_outline(pts, amount, smooth=2):
    normals = outline_normals(pts)
    out = [(x - n.x * amount, z - n.y * amount) for (x, z), n in zip(pts, normals)]
    return smooth_pts(out, passes=smooth, closed=True) if smooth > 0 else out


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
    return smooth_pts(out, passes=2, closed=True)


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


def crown_wave_outline(w, h, peak_h=0.18, side_h=0.085, corner=0.18, step=0.042):
    """3-peak wavy crown-top toy-kiosk contour (Shop, ATM, Workbench header)."""
    pts = resample(rounded_rect(w, h, min(w, h) * corner, step=step), step)
    hw, hh = w * 0.5, h * 0.5
    out = []
    for x, z in pts:
        nx = x / max(hw, 1e-6)
        nz = z / max(hh, 1e-6)
        # Subtle plump vinyl swell on lower sides, gentle waist near upper-mid
        sx = x * (1.0 + 0.04 * max(0.0, -nz) - 0.025 * math.exp(-((nz - 0.42) / 0.28) ** 2))
        sz = z
        if nz > 0.35:
            top_w = min(1.0, (nz - 0.35) / 0.65)
            # Bold 3-peak scalloped crown wave: tall center peak + two playful shoulder peaks
            c_peak = peak_h * math.exp(-((nx / 0.24) ** 2))
            l_peak = side_h * math.exp(-(((nx + 0.62) / 0.24) ** 2))
            r_peak = side_h * math.exp(-(((nx - 0.62) / 0.24) ** 2))
            valleys = -0.045 * (math.exp(-(((nx + 0.33) / 0.14) ** 2)) + math.exp(-(((nx - 0.33) / 0.14) ** 2)))
            sz += (c_peak + l_peak + r_peak + valleys) * (top_w ** 1.2)
        out.append((sx, sz))
    return smooth_pts(out, passes=2, closed=True)


def mecha_sign_outline(w, h, chamfer=0.22, nose_r=0.23, step=0.03):
    """Chunky chamfered-hood street-post sign head (45-deg armored left chamfer + rounded pill nose)."""
    hw, hh = w * 0.5, h * 0.5
    ch = min(chamfer, hh * 0.85, hw * 0.55)
    nr = min(nose_r, hh * 0.92)
    bl_r = min(0.11, hh * 0.4)
    pts = []
    # Bottom-left soft corner
    n_bl = max(2, int((math.pi * bl_r * 0.5) / step))
    for i in range(n_bl + 1):
        a = math.radians(180.0 + 90.0 * i / n_bl)
        pts.append((-hw + bl_r + bl_r * math.cos(a), -hh + bl_r + bl_r * math.sin(a)))
    # Bottom-right rounded pill nose -> top-right rounded pill nose
    n_nose = max(6, int((math.pi * nr) / step))
    for i in range(n_nose + 1):
        a = math.radians(-90.0 + 180.0 * i / n_nose)
        pts.append((hw - nr + nr * math.cos(a), nr * math.sin(a) * (hh / nr)))
    # Top-left 45-degree futuristic armored chamfer
    pts.append((-hw + ch, hh))
    pts.append((-hw, hh - ch))
    return resample(pts, step)


def sculpted_sign_outline(w, h, arch=0.055, wave=0.036, chamfer=0.26, nose_r=0.28, step=0.048):
    """Organic puffed & swept vinyl-toy sign contour (zero rigid horizontal rectangle!)."""
    pts = mecha_sign_outline(w, h, chamfer=chamfer, nose_r=nose_r, step=step)
    hw, hh = w * 0.5, h * 0.5
    out = []
    for x, z in pts:
        nx = max(-1.0, min(1.0, x / max(hw, 1e-6)))
        nz = max(-1.0, min(1.0, z / max(hh, 1e-6)))
        # Plump vinyl belly puff + playful swept arch rising softly toward the right nose
        sx = x * (1.0 + 0.03 * (1.0 - nz * nz))
        sz = z
        if nz > 0.15:
            u = (nx + 1.0) * 0.5
            sz += arch * math.sin(u * math.pi) * (0.75 + 0.35 * u) * ((nz - 0.15) / 0.85)
        elif nz < -0.15:
            # Subtle comic S-wave underneath: tucked nicely on left, fuller cheek on right
            sz += wave * (-0.55 * math.sin(nx * math.pi * 0.85) + 0.25) * ((-nz - 0.15) / 0.85)
        out.append((sx, sz))
    return smooth_pts(out, passes=3, closed=True)


class PropBuilder:
    def __init__(self, spec, prop, spec_dir=""):
        self.spec = spec
        self.prop = prop
        self.spec_dir = spec_dir
        self.id = prop["id"]
        self.palette = dict(DEFAULT_PALETTE)
        self.palette.update(spec.get("palette", {}))
        self.palette.update(prop.get("palette", {}))
        seed = prop.get("seed", zlib.crc32(self.id.encode("utf-8")))
        self.rng = random.Random(seed)
        self.parts = []
        self.colliders = []
        self.pending_decals = []
        self.materials = {}
        self.warnings = []
        self.collection = bpy.data.collections.new(self.id + "_parts")
        bpy.context.scene.collection.children.link(self.collection)
        self.font = self.load_font(spec.get("font", "TitanOne-Regular.ttf"))
        brand = spec.get("brand", {})
        self.brand = brand.get("name", "GOO LAB")
        self.brand_short = brand.get("short", self.brand.split(" ")[0])
        self.mascot_style = prop.get("mascot_style", spec.get("mascot_style", "slime"))
        self.style = prop.get("style", spec.get("style", "default"))
        self.is_kawaii = (self.style == "kawaii_billie")
        self.is_stylized = (self.style in ("vinyl_toy", "kawaii_billie"))
        self.logo = prop.get("logo", spec.get("logo", ""))
        self.logo_aspect = prop.get("logo_aspect", spec.get("logo_aspect", None))
        self.logo_bg = prop.get("logo_bg", spec.get("logo_bg", ""))
        self.logo_bg_aspect = prop.get("logo_bg_aspect", spec.get("logo_bg_aspect", self.logo_aspect))
        self.animate = bool(prop.get("animate", spec.get("animate", False)))
        self.low_poly = bool(prop.get("low_poly", spec.get("low_poly", False)))
        self.current_bone = "root"
        self.bones = {"root": {"pivot": (0.0, 0.0, 0.0), "parent": None}}
        self.anim_config = None

    def define_bone(self, name, pivot, parent="root"):
        if name not in self.bones:
            self.bones[name] = {"pivot": tuple(float(v) for v in pivot), "parent": parent}
        return name

    @contextmanager
    def use_bone(self, name):
        prev = self.current_bone
        self.current_bone = name if (self.animate and name in self.bones) else "root"
        try:
            yield
        finally:
            self.current_bone = prev

    def set_anim(self, frames=121, fps=30, tracks=None):
        if not self.animate:
            return
        self.anim_config = {
            "fps": int(fps),
            "frames": int(frames),
            "tracks": dict(tracks or {}),
        }

    def decal(self, image, width, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), height=None, M=None, shader="decal.sps", aspect=None):
        if not image:
            return
        if height is None and aspect:
            height = width / aspect
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        self.pending_decals.append({
            "image": image,
            "width": width,
            "height": height,
            "matrix": world,
            "shader": shader,
            "bone": self.current_bone,
        })

    def logo_decal(self, width, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), height=None, M=None, shader="decal.sps"):
        if not self.logo:
            return False
        self.decal(self.logo, width, loc=loc, rot=rot, height=height, M=M, shader=shader, aspect=self.logo_aspect)
        return True

    def banner_decal(self, width, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), height=None, M=None, shader="decal.sps"):
        img = self.logo_bg or self.logo
        if not img:
            return False
        asp = self.logo_bg_aspect if self.logo_bg else self.logo_aspect
        self.decal(img, width, loc=loc, rot=rot, height=height, M=M, shader=shader, aspect=asp)
        return True

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
        ob["prop_forge_bone"] = self.current_bone
        self.parts.append(ob)
        return ob

    def box(self, size, loc=(0, 0, 0), role="primary", bevel=0.02, rot=(0, 0, 0), M=None, matrix=None, collide=False, segments=3):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        local = matrix if matrix is not None else trs(loc, rot)
        world = (M or Matrix.Identity(4)) @ local
        bevel = min(bevel, 0.4 * min(size))
        if self.low_poly:
            if bevel < 0.008 or min(size) < 0.032:
                bevel = 0.0
            segments = 1
        elif bevel < 0.007:
            segments = 1
        elif min(size) < 0.08:
            segments = min(segments, 2)
        ob = self.add("box", bm, role, world, bevel=bevel, segments=segments)
        if collide:
            self.collider_from(world, size)
        return ob

    def cyl(self, radius, depth, loc=(0, 0, 0), role="primary", axis="Z", segments=16, radius2=None, bevel=0.0, rot=(0, 0, 0), M=None, matrix=None, collide=False):
        if self.low_poly:
            segments = max(6, min(segments, 10))
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2, depth=depth)
        axis_rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        local = matrix if matrix is not None else trs(loc, rot)
        world = (M or Matrix.Identity(4)) @ local @ axis_rot
        bevel = min(bevel, 0.4 * min(radius, depth))
        ob = self.add("cyl", bm, role, world, bevel=bevel, segments=1 if self.low_poly else 2)
        if collide:
            self.collider_from(world, (radius * 2, radius * 2, depth))
        return ob

    def sphere(self, radius, loc=(0, 0, 0), role="primary", scale=(1, 1, 1), u=16, v=10, rot=(0, 0, 0), M=None, matrix=None):
        if self.low_poly:
            u = max(6, min(u, 8))
            v = max(4, min(v, 5))
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)
        local = matrix if matrix is not None else trs(loc, rot, scale)
        return self.add("sphere", bm, role, (M or Matrix.Identity(4)) @ local)

    def torus(self, major, minor, loc=(0, 0, 0), role="light", axis="Y", seg_major=28, seg_minor=8, rot=(0, 0, 0), M=None):
        if self.low_poly:
            seg_major = max(8, min(seg_major, 16))
            seg_minor = max(4, min(seg_minor, 5))
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
        if self.low_poly and len(pts) > 22:
            # Keep every 2nd vertex only on overly dense smooth curves while preserving crisp silhouette corners
            simp = [pts[0]]
            n0 = len(pts)
            for i in range(1, n0):
                p_prev = simp[-1]
                p_cur = pts[i]
                p_next = pts[(i + 1) % n0]
                v1 = (p_cur[0] - p_prev[0], p_cur[1] - p_prev[1])
                v2 = (p_next[0] - p_cur[0], p_next[1] - p_cur[1])
                l1 = math.hypot(v1[0], v1[1])
                l2 = math.hypot(v2[0], v2[1])
                if l1 < 1e-6 or l2 < 1e-6:
                    continue
                dot = (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                if dot < 0.965 or l1 > 0.14:
                    simp.append(p_cur)
            if len(simp) >= 8:
                pts = simp
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
        ob = self.add("shape", bm, role, world, bevel=bevel, segments=1 if self.low_poly else 2)
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
            cu.bevel_depth = 0.0 if self.low_poly else (min(0.018, extrude * 0.5) if bevel else 0.0)
            cu.bevel_resolution = 0
            cu.resolution_u = 1 if self.low_poly else self.prop.get("text_resolution", 2)
            cu.offset = offset
            ob = bpy.data.objects.new("txt", cu)
            self.collection.objects.link(ob)
            depsgraph.update()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))
            bpy.data.objects.remove(ob)
            bpy.data.curves.remove(cu)
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002 if self.low_poly else 0.0005)
            bm.normal_update()
            hidden = [f for f in bm.faces if f.normal.z < -0.7]
            bmesh.ops.delete(bm, geom=hidden, context="FACES")
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(9 if self.low_poly else 4), verts=bm.verts, edges=bm.edges)
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
            ob["prop_forge_bone"] = self.current_bone
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

    def fat_drip(self, loc, length, radius, role="accent", M=None, pearl=False, detail="med"):
        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
        segs = 8
        u, v = (8, 5)
        self.sphere(radius * 1.15, (0, 0, 0), role, scale=(1.1, 0.85, 0.85), u=u, v=v, M=group)
        if length > radius * 0.6:
            self.cyl(radius * 0.88, length, (0, 0, -length * 0.5), role, segments=segs, radius2=radius * 1.02, M=group)
            self.sphere(radius * 1.12, (0, 0, -length), role, scale=(1.0, 0.85, 1.15), u=u, v=v, M=group)
        if pearl:
            self.sphere(radius * 0.48, (0, -radius * 0.1, -length - radius * 1.95), role, scale=(1.0, 0.85, 1.25), u=7, v=4, M=group)

    def fat_curtain(self, x0, x1, z_top, y_front, role="accent", thick=0.045, max_drop=0.20, drops=3, M=None, pearls=True, swell=True):
        w = max(0.08, x1 - x0)
        bumps = []
        for k in range(drops):
            c = x0 + w * (k + 0.5) / drops + self.rng.uniform(-0.18, 0.18) * (w / max(1, drops))
            c = max(x0 + 0.05, min(x1 - 0.05, c))
            wd = max(0.045, min(0.095, w / max(2.2, drops * 1.65) * self.rng.uniform(0.72, 1.0)))
            amp = max_drop * self.rng.uniform(0.55, 1.0)
            bumps.append((c, amp, wd))
        base = max(0.032, thick * 0.9)

        def drop_at(x):
            edge = min(1.0, min(x - x0, x1 - x) / max(0.04, thick * 1.4))
            v = base * (0.6 + 0.4 * edge)
            for c, amp, wd in bumps:
                t = abs(x - c) / wd
                if t < 2.2:
                    v += amp * math.exp(-(t ** 2.2))
            return v

        n = max(16, min(42, int(w / 0.028)))
        pts = [(x0, z_top + thick * 0.45), (x1, z_top + thick * 0.45)]
        for i in range(n + 1):
            x = x1 - w * i / n
            pts.append((x, z_top - drop_at(x)))
        pts = smooth_pts(pts, passes=1, closed=True)
        self.shape(pts, y_front - thick, y_front + thick * 0.25, role, bevel=min(0.018, thick * 0.42), M=M)
        if pearls:
            for c, amp, wd in bumps:
                if amp >= max_drop * 0.72:
                    self.sphere(min(0.022, wd * 0.32), (c, y_front - thick * 0.45, z_top - drop_at(c) - 0.036), role, scale=(1.0, 0.85, 1.2), u=7, v=5, M=M)

    def fat_skirt(self, w, d, z_top, role="accent", thick=0.048, max_drop=0.22, drops_per_side=2, sides=("front", "back", "left", "right"), corners=True, M=None, pearls=True):
        self.skirt(w, d, z_top, role=role, base=0.045, max_drop=max_drop, drops_per_side=drops_per_side, out=0.018, thick=thick * 0.78, sides=sides, bulbs=True, M=M, corner=0.10)
        if corners:
            hw, hd = w * 0.5, d * 0.5
            for sx in (-1, 1):
                for sy in (-1, 1):
                    self.sphere(thick * 0.95, (sx * hw, sy * hd, z_top - 0.025), role, scale=(1.05, 1.05, 1.2), u=8, v=6, M=M)

    def tube_along_outline(self, pts, y_center, tube_r, role="accent", swell=0.08, seg=10, M=None):
        if self.low_poly:
            seg = min(seg, 6)
            if len(pts) > 28:
                pts = pts[::2]
        spts = smooth_pts(pts, passes=2, closed=True)
        normals = outline_normals(spts)
        bm = bmesh.new()
        rings = []
        n = len(spts)
        for i, ((x, z), nm) in enumerate(zip(spts, normals)):
            sw = 1.0 + swell * math.sin(i * 0.42) + (swell * 0.65 if nm.y > 0.5 else 0.0)
            tr = tube_r * sw
            ring = []
            for j in range(seg):
                a = math.tau * j / seg
                ca = math.cos(a)
                sa = math.sin(a)
                ring.append(bm.verts.new((x + nm.x * tr * ca, y_center + tr * 0.88 * sa, z + nm.y * tr * ca)))
            rings.append(ring)
        for i in range(n):
            r0 = rings[i]
            r1 = rings[(i + 1) % n]
            for j in range(seg):
                j1 = (j + 1) % seg
                bm.faces.new((r0[j], r1[j], r1[j1], r0[j1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add("blob_tube", bm, role, M or Matrix.Identity(4))

    def blob_tube_frame(self, w, h, y_center, tube_r, role="accent", lobes=3, lobe_amp=0.075, corner=0.16, M=None):
        pts = blob_outline(w, h, self.rng, wobble=0.012, lobes=lobes, lobe_amp=lobe_amp, corner=corner, step=max(0.052, (w + h) * 2.0 / 62.0))
        return self.tube_along_outline(pts, y_center, tube_r, role=role, swell=0.10, seg=8, M=M)

    def hollow_vault_shell(self, w, d, z_bot, z_top, hole_cx, hole_cz, hole_r, role="primary", per_side=7, bevel=0.052, lip_depth=0.050, M=None):
        """Build a single seamless beveled cabinet with a circular vault opening on the front (-Y) face."""
        if self.low_poly:
            per_side = min(per_side, 4)
        ox0, ox1 = -w * 0.5, w * 0.5
        oz0, oz1 = z_bot, z_top
        y_front, y_back = -d * 0.5, d * 0.5
        # Build CCW outer perimeter with exact 4 corners so outer cabinet edges stay razor-straight before beveling
        outer_2d = []
        corners = [(ox0, oz0), (ox1, oz0), (ox1, oz1), (ox0, oz1)]
        for ci in range(4):
            ax, az = corners[ci]
            bx, bz = corners[(ci + 1) % 4]
            for k in range(per_side):
                t = k / per_side
                outer_2d.append((ax + (bx - ax) * t, az + (bz - az) * t))
        n = len(outer_2d)
        inner_2d = []
        for ox, oz in outer_2d:
            a = math.atan2(oz - hole_cz, ox - hole_cx)
            inner_2d.append((hole_cx + hole_r * math.cos(a), hole_cz + hole_r * math.sin(a)))
        bm = bmesh.new()
        vf_out = [bm.verts.new((x, y_front, z)) for x, z in outer_2d]
        vb_out = [bm.verts.new((x, y_back, z)) for x, z in outer_2d]
        vf_in = [bm.verts.new((x, y_front, z)) for x, z in inner_2d]
        vl_in = [bm.verts.new((x, y_front + lip_depth, z)) for x, z in inner_2d]
        vc_in = [bm.verts.new((x, y_back - 0.07, z)) for x, z in inner_2d]
        for i in range(n):
            j = (i + 1) % n
            # Front wall ring (outer to circular opening)
            bm.faces.new((vf_out[i], vf_out[j], vf_in[j], vf_in[i]))
            # Outer perimeter side/top/bottom walls (seamless)
            bm.faces.new((vf_out[i], vb_out[i], vb_out[j], vf_out[j]))
            # Circular opening recessed return lip + deep cavity wall
            bm.faces.new((vf_in[i], vf_in[j], vl_in[j], vl_in[i]))
            bm.faces.new((vl_in[i], vl_in[j], vc_in[j], vc_in[i]))
        # Solid outer back face + deep cavity rear wall (100% watertight manifold)
        bm.faces.new(list(reversed(vb_out)))
        bm.faces.new(vc_in)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # Bevel ONLY sharp outer cabinet edges (>35 deg), leaving flat faces and inner lip clean
        sharp_outer = []
        lip_edges = []
        vf_in_set = set(vf_in)
        vf_out_set = set(vf_out)
        vb_out_set = set(vb_out)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(35):
                v0, v1 = e.verts
                if v0 in vf_in_set and v1 in vf_in_set:
                    lip_edges.append(e)
                elif (v0 in vf_out_set or v0 in vb_out_set) and (v1 in vf_out_set or v1 in vb_out_set):
                    sharp_outer.append(e)
        if sharp_outer and bevel > 0:
            bmesh.ops.bevel(bm, geom=sharp_outer, offset=bevel, segments=1 if self.low_poly else 3, affect="EDGES", clamp_overlap=True, profile=0.55)
        if lip_edges:
            cur_lip = [
                e for e in bm.edges
                if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(40)
                and all(abs(v.co.y - y_front) < 0.004 and math.hypot(v.co.x - hole_cx, v.co.z - hole_cz) < hole_r + 0.015 for v in e.verts)
            ]
            if cur_lip:
                bmesh.ops.bevel(bm, geom=cur_lip, offset=0.014, segments=1 if self.low_poly else 2, affect="EDGES", clamp_overlap=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add("vault_shell", bm, role, M or Matrix.Identity(4))

    def open_cyl_liner(self, radius, y_front, y_back, cx, cz, role="dark", segments=28, wall=0.006, M=None):
        """Watertight thick-walled cylindrical armored vault drum liner open at y_front and capped at y_back."""
        bm = bmesh.new()
        ri, ro = radius, radius + wall
        if_r, ib_r, of_r, ob_r = [], [], [], []
        for i in range(segments):
            a = math.tau * i / segments
            ca, sa = math.cos(a), math.sin(a)
            if_r.append(bm.verts.new((cx + ri * ca, y_front, cz + ri * sa)))
            ib_r.append(bm.verts.new((cx + ri * ca, y_back, cz + ri * sa)))
            of_r.append(bm.verts.new((cx + ro * ca, y_front, cz + ro * sa)))
            ob_r.append(bm.verts.new((cx + ro * ca, y_back + wall, cz + ro * sa)))
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((if_r[i], if_r[j], ib_r[j], ib_r[i]))
            bm.faces.new((of_r[i], ob_r[i], ob_r[j], of_r[j]))
            bm.faces.new((of_r[i], of_r[j], if_r[j], if_r[i]))
        bm.faces.new(list(reversed(ib_r)))
        bm.faces.new(ob_r)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add("vault_liner", bm, role, M or Matrix.Identity(4))

    def shield_plaque(self, loc, w, h, role="dark", border_role="light", accent_role="gold", direction=(0, -1, 0), M=None):
        """Sculpted street-art badge shield medallion for mounting mascots cleanly."""
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        hw, hh = w * 0.5, h * 0.5
        outer = [
            (0.0, -hh),
            (hw * 0.78, -hh * 0.58),
            (hw, 0.12 * hh),
            (hw * 0.88, hh * 0.88),
            (0.0, hh),
            (-hw * 0.88, hh * 0.88),
            (-hw, 0.12 * hh),
            (-hw * 0.78, -hh * 0.58),
        ]
        outer = smooth_pts(resample(outer, max(0.025, (w + h) / 28.0)), passes=2, closed=True)
        inner = inset_outline(outer, min(w, h) * 0.10, smooth=2)
        self.shape(outer, -0.016, 0.014, border_role, bevel=0.008, M=base)
        self.shape(inner, -0.024, 0.006, role, bevel=0.005, M=base)
        for sx in (-1, 1):
            self.cyl(min(w, h) * 0.045, 0.012, (sx * hw * 0.64, -0.024, hh * 0.66), accent_role, axis="Y", segments=8, M=base)

    def swoosh_arc(self, center, radius, start_deg, end_deg, tube_r, role="primary", tilt=(0, 0, 0), lift=0.0, steps=18, seg=8, M=None):
        """Sleek tapered 3D orbiting graffiti swoosh arc with pointed tips."""
        group = (M or Matrix.Identity(4)) @ Matrix.Translation(center) @ trs((0, 0, 0), tilt)
        bm = bmesh.new()
        rings = []
        pts = []
        for i in range(steps + 1):
            t = i / steps
            a = math.radians(start_deg + (end_deg - start_deg) * t)
            pts.append(Vector((radius * math.cos(a), radius * math.sin(a), (t - 0.5) * lift)))
        for i, p in enumerate(pts):
            t = i / steps
            taper = max(0.08, math.sin(t * math.pi) ** 0.65)
            tang = (pts[min(steps, i + 1)] - pts[max(0, i - 1)]).normalized()
            up = Vector((0, 0, 1))
            if abs(tang.dot(up)) > 0.95:
                up = Vector((1, 0, 0))
            side = tang.cross(up).normalized()
            binorm = side.cross(tang).normalized()
            r_cur = tube_r * taper
            ring = []
            for j in range(seg):
                ang = math.tau * j / seg
                vpos = p + side * (r_cur * 1.15 * math.cos(ang)) + binorm * (r_cur * 0.65 * math.sin(ang))
                ring.append(bm.verts.new(vpos))
            rings.append(ring)
        for i in range(steps):
            r0, r1 = rings[i], rings[i + 1]
            for j in range(seg):
                j1 = (j + 1) % seg
                bm.faces.new((r0[j], r1[j], r1[j1], r0[j1]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add("swoosh", bm, role, group)

    def open_wrench(self, loc, length=0.30, role="metal", grip_role="primary", M=None):
        """3D stylized open-end mechanic wrench for pegboards."""
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
        s = length
        self.box((s * 0.11, s * 0.055, s * 0.64), (0, 0, 0), role, bevel=s * 0.015, segments=1, M=base)
        self.box((s * 0.14, s * 0.072, s * 0.34), (0, 0, -s * 0.06), grip_role, bevel=s * 0.018, segments=1, M=base)
        # Top open jaw (C-shape from 2 prongs + bridge)
        self.box((s * 0.28, s * 0.062, s * 0.09), (0, 0, s * 0.32), role, bevel=s * 0.014, segments=1, M=base)
        for sx in (-1, 1):
            self.box((s * 0.085, s * 0.062, s * 0.16), (sx * s * 0.10, 0, s * 0.42), role, bevel=s * 0.014, segments=1, M=base)
        # Bottom ring end
        self.torus(s * 0.095, s * 0.032, (0, 0, -s * 0.37), role, axis="Y", seg_major=12, seg_minor=5, M=base)

    def craft_scissors(self, loc, length=0.28, role="metal", grip_role="primary", M=None):
        """3D stylized craft scissors for pegboards."""
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
        s = length
        for side in (-1, 1):
            ang = side * 0.15
            bm_m = base @ trs((side * s * 0.02, -side * s * 0.012, s * 0.08), (0, ang, 0))
            self.box((s * 0.055, s * 0.022, s * 0.48), (0, 0, s * 0.10), role, bevel=s * 0.006, segments=1, M=bm_m)
            self.torus(s * 0.085, s * 0.028, (side * s * 0.11, 0, -s * 0.24), grip_role, axis="Y", seg_major=12, seg_minor=5, M=base)
        self.cyl(s * 0.026, s * 0.055, (0, 0, -s * 0.02), "gold", axis="Y", segments=8, M=base)

    def metaball_slime(self, elements, role="accent", resolution=0.024, target_tris=1800, smooth_iters=3, M=None):
        """Sculpt silky, seamless, watertight organic melting slime via Blender Metaballs + Smooth + Decimate."""
        if not elements:
            return None
        if self.low_poly and target_tris:
            target_tris = max(110, int(target_tris * 0.40))
        mb = bpy.data.metaballs.new("pf_slime_mb")
        mb.resolution = resolution
        mb.render_resolution = resolution
        mb.threshold = 0.60
        mb_ob = bpy.data.objects.new("pf_slime_mb", mb)
        self.collection.objects.link(mb_ob)
        for spec in elements:
            etype = spec[0]
            co = spec[1]
            rad = spec[2]
            el = mb.elements.new(type=etype)
            el.co = co
            el.radius = rad
            if etype in ("ELLIPSOID", "CUBE") and len(spec) > 3:
                el.size_x, el.size_y, el.size_z = spec[3]
                if len(spec) > 4 and spec[4] is not None:
                    el.rotation = Euler(spec[4]).to_quaternion()
            elif etype == "CAPSULE" and len(spec) > 3:
                el.size_x = spec[3]
                if len(spec) > 4 and spec[4] is not None:
                    el.rotation = Euler(spec[4]).to_quaternion()
        deps = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(mb_ob.evaluated_get(deps))
        bpy.data.objects.remove(mb_ob, do_unlink=True)
        bpy.data.metaballs.remove(mb)
        raw_tris = sum(len(p.vertices) - 2 for p in me.polygons)
        if raw_tris == 0:
            bpy.data.meshes.remove(me)
            return None
        ob = bpy.data.objects.new("slime_mb", me)
        self.collection.objects.link(ob)
        if smooth_iters > 0:
            sm = ob.modifiers.new("sm", "SMOOTH")
            sm.factor = 0.5
            sm.iterations = smooth_iters
        if target_tris and raw_tris > target_tris:
            dec = ob.modifiers.new("dec", "DECIMATE")
            dec.ratio = max(0.05, min(1.0, float(target_tris) / float(raw_tris)))
        deps = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        bm = bmesh.new()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
        bmesh.ops.dissolve_degenerate(bm, dist=0.0003, edges=bm.edges)
        tiny = [f for f in bm.faces if f.calc_area() < 1e-6]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context="FACES")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add("slime_mb", bm, role, M or Matrix.Identity(4))

    def _add_drip_chain(self, els, x, y, z_top, drop, rad, outward=(0.0, 0.0)):
        # Compensate for metaball threshold=0.60 (~0.63 effective radius) so drips stay plump & continuous!
        eff_r = rad * 1.38
        steps = max(3, int(drop / max(0.028, rad * 0.60)))
        ox, oy = outward
        for k in range(steps + 1):
            t = k / steps
            if t < 0.22:
                r_cur = eff_r * (1.14 - 0.45 * t)
            elif t < 0.72:
                r_cur = eff_r * (0.82 + 0.06 * math.sin(t * math.pi))
            else:
                r_cur = eff_r * (0.82 + 0.34 * ((t - 0.72) / 0.28))
            push = 0.008 * math.sin(t * math.pi)
            els.append(("BALL", (x + ox * push, y + oy * push, z_top - t * drop), r_cur))

    def slime_cap_mb(self, w, d, z_top, role="accent", drips=None, pearls=None, cap_thick=0.068, res=0.025, target_tris=2000, M=None):
        """One-piece seamless melting slime cap — or Fluffy Cloud Pillow Cap when style == 'kawaii_billie'."""
        if self.is_kawaii:
            els = [("CUBE", (0.0, 0.0, z_top + 0.018), 0.105, (w * 0.46, d * 0.46, cap_thick * 0.34))]
            hw, hd = w * 0.46, d * 0.46
            for sx in (-1, 1):
                for sy in (-1, 1):
                    els.append(("BALL", (sx * hw, sy * hd, z_top + 0.018), 0.145))
            for k in range(3):
                t = -0.58 + 0.58 * k
                els.append(("BALL", (t * w, -hd * 1.02, z_top + 0.014), 0.130 + (0.018 if k == 1 else 0.0)))
                els.append(("BALL", (t * w,  hd * 1.02, z_top + 0.014), 0.130 + (0.018 if k == 1 else 0.0)))
            for k in range(2):
                t = -0.34 + 0.68 * k
                els.append(("BALL", (-hw * 1.02, t * d, z_top + 0.014), 0.128))
                els.append(("BALL", ( hw * 1.02, t * d, z_top + 0.014), 0.128))
            return self.metaball_slime(els, role="light", resolution=res, target_tris=min(target_tris, 1100), smooth_iters=4, M=M)
        els = [
            ("CUBE", (0.0, 0.0, z_top + 0.016), 0.095, (w * 0.465, d * 0.465, cap_thick * 0.28)),
        ]
        # Plump rounded corner shoulders wrapping cleanly into the top CUBE blanket
        for sx in (-1, 1):
            for sy in (-1, 1):
                els.append(("BALL", (sx * w * 0.465, sy * d * 0.465, z_top - 0.005), 0.115))
        for x, y, drop, rad, ox, oy in (drips or []):
            self._add_drip_chain(els, x, y, z_top - 0.002, drop, rad, outward=(ox, oy))
        for px, py, pz, prad in (pearls or []):
            els.append(("BALL", (px, py, pz), prad * 1.45))
        return self.metaball_slime(els, role=role, resolution=res, target_tris=target_tris, smooth_iters=4, M=M)

    def slime_frame_mb(self, pts, y_center, tube_r, role="accent", bridge_z=None, bridge_x=None, drips=None, res=0.024, target_tris=1800, M=None):
        """One-piece plump continuous organic frame — clean smooth plush pillow frame without drips in 'kawaii_billie'."""
        els = []
        # Dense overlapping BALL metaballs (effective radius ~0.63*ball_r) guarantee ZERO gaps or pinching!
        ball_r = tube_r * (1.52 if self.is_kawaii else 1.58)
        spts = resample(smooth_pts(pts, passes=2, closed=True), max(0.036, tube_r * 0.85))
        for i, (x, z) in enumerate(spts):
            sw = 1.02 if self.is_kawaii else (1.0 + 0.12 * math.sin(i * 0.55) + (0.08 if z > 0.25 else 0.0))
            els.append(("BALL", (x, y_center, z), ball_r * sw))
        if bridge_z is not None and bridge_x is not None:
            bx0, bx1 = bridge_x
            nb = max(10, int((bx1 - bx0) / max(0.036, tube_r * 0.80)))
            for i in range(nb + 1):
                t = i / nb
                x = bx0 + (bx1 - bx0) * t
                wave = 0.0 if self.is_kawaii else (-0.024 * math.sin(t * math.pi * 2.0))
                r_b = ball_r * (0.94 if self.is_kawaii else (0.92 + 0.12 * math.sin(t * math.pi * 3.0)))
                els.append(("BALL", (x, y_center - 0.006, bridge_z + wave), r_b))
        if not self.is_kawaii:
            for x, y, z_start, drop, rad in (drips or []):
                self._add_drip_chain(els, x, y, z_start, drop, rad)
        return self.metaball_slime(els, role=role, resolution=res, target_tris=target_tris, smooth_iters=4, M=M)

    def slime_skirt_mb(self, w, d, z_base, role="accent", wave_amp=0.070, tube_r=0.056, corner_blobs=True, res=0.024, target_tris=1700, M=None):
        """One-piece continuous wavy skirt — Fluffy Milk-Cream Cloud Cushion Base when style == 'kawaii_billie'."""
        if self.is_kawaii:
            role = "light"
            wave_amp = min(wave_amp, 0.045)
        els = []
        hw, hd = w * 0.5, d * 0.5
        ball_r = tube_r * (1.72 if self.is_kawaii else 1.56)
        step = max(0.038, tube_r * 0.72)
        for s_name, a, b in (
            ("front", (-hw, -hd), (hw, -hd)),
            ("right", (hw, -hd), (hw, hd)),
            ("back", (hw, hd), (-hw, hd)),
            ("left", (-hw, hd), (-hw, -hd)),
        ):
            va, vb = Vector(a), Vector(b)
            cnt = max(8, int((vb - va).length / step))
            for k in range(cnt):
                t = k / cnt
                p = va.lerp(vb, t)
                wave = wave_amp * (0.5 + 0.5 * math.cos(t * math.tau * 2.0))
                els.append(("BALL", (p.x, p.y, z_base + wave * 0.45), ball_r * (0.96 + 0.16 * math.sin(t * math.pi * 2.0))))
                if wave > wave_amp * 0.65:
                    els.append(("BALL", (p.x, p.y, z_base + wave * 0.85), ball_r * 0.88))
        if corner_blobs:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    els.append(("BALL", (sx * hw * 0.99, sy * hd * 0.99, z_base + wave_amp * 0.25), ball_r * 1.32))
        return self.metaball_slime(els, role=role, resolution=res, target_tris=target_tris, smooth_iters=4, M=M)

    def slime_drips_mb(self, chains, role="accent", link_y=None, res=0.018, target_tris=650, M=None):
        """Localized seamless melting slime drip patch — smooth merged cloud tuft when style == 'kawaii_billie'."""
        if self.is_kawaii:
            if not chains:
                return None
            els = []
            for idx, (x, y, z_top, drop, rad) in enumerate(chains):
                pr = max(rad * 2.4, 0.092)
                els.append(("BALL", (x, y, z_top), pr))
                if idx + 1 < len(chains):
                    nx, ny, nz, _, _ = chains[idx + 1]
                    for k in (1, 2):
                        t = k / 3.0
                        els.append(("BALL", (x + (nx - x) * t, y + (ny - y) * t, z_top + (nz - z_top) * t), pr * 0.92))
            return self.metaball_slime(els, role="light", resolution=max(res, 0.020), target_tris=min(target_tris, 420), smooth_iters=4, M=M)
        els = []
        for idx, (x, y, z_top, drop, rad) in enumerate(chains):
            self._add_drip_chain(els, x, y, z_top, drop, rad)
            if idx + 1 < len(chains):
                nx, ny, nz, _, nrad = chains[idx + 1]
                dist = math.hypot(nx - x, nz - z_top)
                if dist < (rad + nrad) * 5.0:
                    for k in range(1, 4):
                        t = k / 4.0
                        els.append(("BALL", (x + (nx - x) * t, (y + ny) * 0.5 if link_y is None else link_y, z_top + (nz - z_top) * t), (rad + nrad) * 0.70))
        return self.metaball_slime(els, role=role, resolution=res, target_tris=target_tris, smooth_iters=3, M=M)

    def slime_collar_mb(self, radius, z_top, role="accent", drips=8, drop_min=0.13, drop_max=0.25, rad=0.050, res=0.024, target_tris=1200, drip_angles=None, M=None):
        """One-piece 360-degree circular collar — lush continuous scalloped Milk-Cream Cloud Ring in 'kawaii_billie'."""
        if self.is_kawaii:
            els = []
            n_puffs = 20
            puff_r = max(rad * 3.10, radius * 0.36)
            for i in range(n_puffs):
                a = math.tau * i / n_puffs
                sw = 1.0 + 0.12 * (1 if i % 2 == 0 else -1)
                els.append(("BALL", (radius * math.cos(a), radius * math.sin(a), z_top + (0.010 if i % 2 == 0 else -0.004)), puff_r * sw))
            return self.metaball_slime(els, role="light", resolution=max(res, 0.024), target_tris=min(target_tris, 950), smooth_iters=5, M=M)
        els = []
        angles = list(drip_angles) if drip_angles is not None else [math.tau * k / drips + (0.18 if k % 2 else 0.0) for k in range(drips)]
        ring_n = max(24, len(angles) * 4)
        ring_r = rad * 1.56
        for i in range(ring_n):
            a = math.tau * i / ring_n
            sw = 1.0 + 0.08 * math.sin(a * max(4, len(angles)))
            els.append(("BALL", (radius * math.cos(a), radius * math.sin(a), z_top), ring_r * sw))
        for k, a in enumerate(angles):
            drop = drop_max if k % 2 == 0 else drop_min
            dr = rad * (1.05 if k % 2 == 0 else 0.90)
            ca, sa = math.cos(a), math.sin(a)
            self._add_drip_chain(els, radius * ca, radius * sa, z_top - 0.004, drop, dr, outward=(ca, sa))
        return self.metaball_slime(els, role=role, resolution=res, target_tris=target_tris, smooth_iters=5, M=M)

    def chamfered_base(self, w, d, h, role="dark", pad_role="primary", glow_role="glow", M=None, collide=True, vents=True):
        pad_h = min(0.045, h * 0.26)
        self.box((w + 0.05, d + 0.05, pad_h), (0, 0, pad_h * 0.5), pad_role, bevel=pad_h * 0.35, M=M)
        top_h = h - pad_h
        bm = bmesh.new()
        bw, bd = w * 0.5, d * 0.5
        tw, td = w * 0.43, d * 0.42
        z0, z1 = pad_h * 0.85, h
        bot = [bm.verts.new((-bw, -bd, z0)), bm.verts.new((bw, -bd, z0)), bm.verts.new((bw, bd, z0)), bm.verts.new((-bw, bd, z0))]
        top = [bm.verts.new((-tw, -td, z1)), bm.verts.new((tw, -td, z1)), bm.verts.new((tw, td, z1)), bm.verts.new((-tw, td, z1))]
        bm.faces.new(list(reversed(bot)))
        bm.faces.new(top)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        world = M or Matrix.Identity(4)
        self.add("base_trap", bm, role, world, bevel=min(0.032, top_h * 0.32), segments=2)
        if collide:
            self.collider_from(world @ Matrix.Translation((0, 0, h * 0.5)), (w, d, h))
        if vents:
            vz = pad_h + top_h * 0.44
            vy = -(bd * 0.56 + td * 0.44) - 0.006
            self.box((w * 0.32, 0.016, top_h * 0.38), (0, vy, vz), "dark" if role != "dark" else "metal", bevel=0.004, M=M)
            for sx in (-1, 1):
                self.box((w * 0.11, 0.016, top_h * 0.24), (sx * w * 0.32, vy, vz), glow_role, bevel=0.005, M=M)
                vx = sx * (bw * 0.56 + tw * 0.44 + 0.006)
                self.box((0.016, d * 0.22, top_h * 0.24), (vx, 0, vz), glow_role, bevel=0.005, M=M)

    def ribbed_handle(self, loc, role="light", side_sign=1, scale=1.0, M=None):
        rot_z = -math.pi * 0.5 if side_sign < 0 else math.pi * 0.5
        hm = (M or Matrix.Identity(4)) @ trs(loc, (0, 0, rot_z))
        s = scale
        self.box((0.30 * s, 0.045 * s, 0.22 * s), (0, -0.015 * s, 0), role, bevel=0.014 * s, segments=1, M=hm)
        self.box((0.20 * s, 0.032 * s, 0.12 * s), (0, -0.028 * s, 0), "dark", bevel=0.006 * s, segments=1, M=hm)
        self.cyl(0.022 * s, 0.18 * s, (0, -0.042 * s, 0), "dark", axis="X", segments=8, M=hm)
        for rx in (-0.055, 0.0, 0.055):
            self.cyl(0.026 * s, 0.014 * s, (rx * s, -0.042 * s, 0), "metal", axis="X", segments=8, M=hm)
        for bx in (-0.115, 0.115):
            for bz in (-0.075, 0.075):
                self.cyl(0.012 * s, 0.018 * s, (bx * s, -0.036 * s, bz * s), "dark", axis="Y", segments=6, M=hm)

    def bolt_cap(self, loc, radius, role="primary", x_role="dark", direction=(0, -1, 0), M=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        self.cyl(radius, radius * 0.55, (0, 0, 0), role, axis="Y", segments=10, M=base)
        for angle in (math.pi / 4, -math.pi / 4):
            self.box((radius * 0.95, radius * 0.22, radius * 0.22), role=x_role, bevel=0.0, matrix=base @ Matrix.Translation((0, -radius * 0.29, 0)) @ Matrix.Rotation(angle, 4, "Y"), segments=1)

    def cash_gold_treasure(self, w, d, z_base, coins=28, float_coins=True, M=None, float_bone=None):
        rng = self.rng
        # Dark plush interior floor + gently domed coin bed (never flat yellow slab)
        self.box((w * 0.86, d * 0.80, 0.018), (0, 0, z_base + 0.004), "dark", bevel=0.006, segments=1, M=M)
        self.sphere(w * 0.34, (0, 0.01, z_base + 0.002), "gold", scale=(1.08, d / w * 1.02, 0.16), u=14, v=6, M=M)
        # Left zone: neatly stacked gold bullion pyramid (x in [-0.25, -0.02])
        bars = [
            (-0.18, 0.06, 0.036, 0.08),
            (-0.18, -0.04, 0.036, -0.05),
            (-0.18, 0.01, 0.080, 0.03),
            (-0.04, 0.08, 0.036, -0.18),
        ]
        for bx, by, bz, rz in bars:
            self.box((0.145, 0.068, 0.040), (bx, by, z_base + bz), "gold", bevel=0.009, segments=2, rot=(0.0, 0.0, rz), M=M)
        # Right zone: neatly stacked banded cash bundles (x in [+0.06, +0.27])
        stacks = [
            (0.17, 0.06, 0.036, 0.12),
            (0.17, -0.04, 0.036, -0.08),
            (0.17, 0.01, 0.074, 0.03),
        ]
        for sx, sy, sz, rz in stacks:
            sm = (M or Matrix.Identity(4)) @ trs((sx, sy, z_base + sz), (0.0, 0.0, rz))
            self.box((0.14, 0.072, 0.034), (0, 0, 0), "light", bevel=0.006, segments=1, M=sm)
            self.box((0.032, 0.076, 0.038), (0, 0, 0), "primary", bevel=0.004, segments=1, M=sm)
        # Coins placed cleanly around front/perimeter & gaps (strictly avoiding cash bundles & bars)
        coin_spots = [
            (-0.28, -0.13, 0.022), (-0.20, -0.15, 0.026), (-0.11, -0.14, 0.028), (-0.02, -0.14, 0.032),
            (0.06, -0.15, 0.028), (0.15, -0.15, 0.024), (0.25, -0.14, 0.022), (0.29, -0.06, 0.024),
            (0.28, 0.05, 0.024), (0.26, 0.14, 0.022), (-0.28, 0.02, 0.024), (-0.27, 0.13, 0.022),
            (-0.04, -0.05, 0.042), (-0.03, 0.01, 0.044), (0.04, 0.02, 0.040), (-0.10, -0.10, 0.036),
            (-0.23, -0.10, 0.030), (0.02, -0.10, 0.036), (0.10, -0.12, 0.032), (0.22, -0.11, 0.028),
            (-0.14, 0.15, 0.026), (0.06, 0.15, 0.026), (0.17, 0.15, 0.024), (-0.05, 0.15, 0.028),
        ]
        for cx, cy, cz in coin_spots[:coins]:
            self.cyl(0.028, 0.008, (cx, cy, z_base + cz), "gold", segments=10, rot=(rng.uniform(-0.22, 0.22), rng.uniform(-0.22, 0.22), rng.uniform(0, 3)), M=M)
        if float_coins:
            with self.use_bone(float_bone or self.current_bone):
                float_pts = [
                    (-0.21, -0.10, 0.19), (0.21, -0.11, 0.23), (0.01, -0.13, 0.28),
                    (-0.10, -0.09, 0.32), (0.14, -0.07, 0.17), (-0.25, -0.08, 0.27),
                ]
                for fx, fy, fz in float_pts:
                    self.cyl(0.026, 0.007, (fx, fy, z_base + fz), "gold", segments=10, rot=(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, 3)), M=M)
                self.star((0.26, -0.12, z_base + 0.30), 0.038, "glowtrim", M=M)
                self.star((-0.24, -0.12, z_base + 0.24), 0.032, "light", M=M)

    def crown(self, loc, radius, height, role="gold", gem_role="primary", tilt=(0, 0, 0), spikes=5, M=None):
        group = (M or Matrix.Identity(4)) @ trs(loc, tilt)
        if self.is_kawaii:
            # Cute Billie School Bear-Ear & Fluffy Cloud Golden Star Crown Finial (straight from logo.png!)
            r = radius
            h = height
            self.sphere(r * 0.56, (-r * 0.62, 0.0, h * 0.24), "light", scale=(1.1, 0.88, 0.82), u=10, v=7, M=group)
            self.sphere(r * 0.64, (0.0, 0.0, h * 0.20), "light", scale=(1.2, 0.92, 0.82), u=10, v=7, M=group)
            self.sphere(r * 0.56, (r * 0.62, 0.0, h * 0.24), "light", scale=(1.1, 0.88, 0.82), u=10, v=7, M=group)
            for sx in (-1, 1):
                self.sphere(r * 0.44, (sx * r * 0.72, 0.0, h * 0.78), "primary", scale=(1.0, 0.68, 1.0), u=10, v=7, M=group)
                self.sphere(r * 0.26, (sx * r * 0.72, -r * 0.16, h * 0.78), "accent", scale=(1.0, 0.55, 1.0), u=8, v=6, M=group)
            self.star((0.0, 0.0, h * 0.94), r * 0.78, role, direction=(0, -1, 0), M=group, crossed=True)
            return
        vt = self.is_stylized
        bm = bmesh.new()
        sub = 2 if self.low_poly else 4
        n = spikes * sub
        bottom = []
        top = []
        for i in range(n):
            a = math.tau * i / n - math.pi / 2
            phase = (i % sub) / float(sub)
            h = height * (0.48 + 0.52 * max(0.0, 1.0 - abs(phase - 0.0 if phase < 0.5 else phase - 1.0) * 3.0))
            bottom.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), 0.0)))
            top.append(bm.verts.new((radius * (1.18 if vt else 1.14) * math.cos(a), radius * (1.18 if vt else 1.14) * math.sin(a), h)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self.add("crown", bm, role, group, solidify=radius * (0.24 if vt else 0.18))
        c_maj = 15
        if vt:
            # Bold comic dark collar tucked cleanly under crown rim + plump glossy torus band wrapping outside
            self.torus(radius * 1.05, height * 0.085, (0, 0, -height * 0.015), "dark", axis="Z", seg_major=c_maj, seg_minor=4, M=group)
            self.torus(radius * 1.08, height * 0.145, (0, 0, height * 0.14), role, axis="Z", seg_major=c_maj, seg_minor=4 if self.low_poly else 5, M=group)
        else:
            self.torus(radius * 1.06, height * 0.14, (0, 0, height * 0.10), role, axis="Z", seg_major=c_maj, seg_minor=4 if self.low_poly else 5, M=group)
        for i in range(spikes):
            a = math.tau * i / spikes - math.pi / 2
            sr = radius * (0.22 if vt else 0.18)
            sp_r = radius * (1.18 if vt else 1.14)
            self.sphere(sr, (sp_r * math.cos(a), sp_r * math.sin(a), height * 1.05), role, u=6 if self.low_poly else 8, v=4 if self.low_poly else 6, M=group)
        gem_m = group @ trs((0, -radius * (1.12 if vt else 1.08), height * 0.45), (0, math.pi * 0.25, 0))
        self.box((radius * (0.46 if vt else 0.40), radius * 0.18, radius * (0.46 if vt else 0.40)), (0, 0.01 * radius, 0), "dark", bevel=0.0, segments=1, M=gem_m)
        self.box((radius * (0.33 if vt else 0.30), radius * 0.20, radius * (0.33 if vt else 0.30)), (0, -0.02 * radius, 0), gem_role, bevel=0.0, segments=1, M=gem_m)

    def x_mark(self, center, direction, size, role="light", M=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(center) @ facing(direction)
        for angle in (math.pi / 4, -math.pi / 4):
            self.box((size, size * 0.3, size * 0.26), role=role, bevel=size * 0.08, matrix=base @ Matrix.Rotation(angle, 4, "Y"), segments=2)

    def star(self, loc, size, role="light", direction=(0, -1, 0), M=None, outline_role="auto", crossed=False):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        if crossed:
            pts = star_outline(size, size * 0.34)
            self.shape(pts, -size * 0.11, size * 0.11, role, bevel=size * 0.025, matrix=base)
            self.shape(pts, -size * 0.11, size * 0.11, role, bevel=size * 0.025, matrix=base @ Matrix.Rotation(math.pi * 0.5, 4, "Z"))
            return
        if outline_role == "auto":
            outline_role = "dark" if self.is_stylized else None
        if outline_role:
            self.shape(star_outline(size * 1.32, size * 0.46), -size * 0.04, size * 0.10, outline_role, bevel=0.0, matrix=base @ Matrix.Translation((0, size * 0.04, 0)))
        self.shape(star_outline(size, size * 0.32), -size * 0.09, size * 0.08, role, bevel=size * 0.02, matrix=base)

    def lightning_bolt(self, loc, size, role="gold", direction=(0, -1, 0), M=None, outline_role="auto"):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        if outline_role == "auto":
            outline_role = "dark" if self.is_stylized else None
        s = size
        pts = [
            (0.18 * s, 1.00 * s),
            (-0.56 * s, 0.02 * s),
            (-0.04 * s, 0.02 * s),
            (-0.26 * s, -1.00 * s),
            (0.58 * s, -0.04 * s),
            (0.06 * s, -0.04 * s),
        ]
        if outline_role:
            pts_o = [(x * 1.24, z * 1.18) for x, z in pts]
            self.shape(pts_o, -s * 0.05, s * 0.11, outline_role, bevel=0.0, matrix=base @ Matrix.Translation((0, s * 0.04, 0)))
        self.shape(pts, -s * 0.10, s * 0.09, role, bevel=s * 0.02, matrix=base)

    def angry_screen_face(self, center, size, role="glow", M=None, eyes_bone=None, mouth_bone=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(center)
        if self.is_kawaii:
            # Cute glowing Kawaii Happy Face (`^  w  ^` + rosy blush dots!)
            with self.use_bone(eyes_bone or self.current_bone):
                for side in (-1, 1):
                    self.sphere(size * 0.22, (side * size * 0.50, 0.0, size * 0.16), role, scale=(1.0, 0.45, 1.15), u=8, v=6, M=base)
                    self.sphere(size * 0.15, (side * size * 0.78, 0.0, -size * 0.14), "trim", scale=(1.2, 0.4, 0.8), u=7, v=5, M=base)
            with self.use_bone(mouth_bone or self.current_bone):
                self.sphere(size * 0.22, (0.0, 0.0, -size * 0.26), role, scale=(1.35, 0.42, 0.75), u=8, v=5, M=base)
            return
        with self.use_bone(eyes_bone or self.current_bone):
            for side in (-1, 1):
                self.box((size * 0.62, 0.012, size * 0.24), role=role, bevel=size * 0.04, matrix=base @ trs((side * size * 0.56, 0, size * 0.2), (0, -side * 0.34, 0)), segments=2)
        with self.use_bone(mouth_bone or self.current_bone):
            self.box((size * 0.95, 0.012, size * 0.16), role=role, bevel=size * 0.03, matrix=base @ trs((0, 0, -size * 0.36), (0, -0.08, 0)), segments=2)

    def billie_bear(self, loc, radius, role="primary", face_role="light", ear_inner="wood", blush_role="trim", direction=(0, -1, 0), M=None, tilt=(0, 0, 0), with_cloud=False, detail="high"):
        """Sculpted 3D Kawaii Chibi Billie Bear-Hood Mascot directly inspired by official BILLIE SCHOOL logo.png!"""
        r = radius
        if ear_inner == role:
            ear_inner = "accent"
        u_s = 22 if detail == "high" else (14 if detail == "med" else 8)
        v_s = 14 if detail == "high" else (9 if detail == "med" else 6)
        u_sub = max(10, u_s - 6) if detail != "low" else 6
        v_sub = max(7, v_s - 4) if detail != "low" else 5
        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0, 0, 0), tilt)

        # 1. Plump Chubby Rounded Bear Hood + Cute Bear Nose Snout on Hood Forehead!
        self.sphere(r * 1.04, (0.0, 0.06 * r, 0.0), role, scale=(1.06, 0.96, 0.98), u=u_s, v=v_s, M=group)
        # Signature Rounded Bear Ears (with cozy warm honey inner-ear pads!)
        for sx in (-1, 1):
            self.sphere(r * 0.40, (sx * r * 0.78, 0.02 * r, r * 0.78), role, scale=(1.0, 0.76, 1.0), u=u_sub, v=v_sub, M=group)
            self.sphere(r * 0.22, (sx * r * 0.78, -r * 0.20, r * 0.78), ear_inner, scale=(1.0, 0.48, 1.0), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)
        # Iconic Tiny Golden-Tangerine Orange perched right on top of the Bear Hood (straight from logo.png!)
        self.sphere(r * 0.27, (0.0, -0.02 * r, r * 1.08), "gold", scale=(1.12, 1.04, 0.84), u=u_sub, v=v_sub, M=group)
        self.cyl(r * 0.042, r * 0.15, (0.0, -0.02 * r, r * 1.29), "dark", segments=6, M=group)
        # Cute Mini Bear Snout Emblem tucked smoothly on front forehead of hood
        self.sphere(r * 0.20, (0.0, -r * 0.65, r * 0.64), ear_inner, scale=(1.20, 0.52, 0.82), u=u_sub, v=v_sub, M=group)
        self.sphere(r * 0.075, (0.0, -r * 0.76, r * 0.67), "dark", scale=(1.2, 0.60, 0.82), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)

        # 2. Adorable Milk-Cream Chibi Face nestled inside the Bear Hood + Plump Curly Honey-Blond Bangs!
        self.sphere(r * 0.84, (0.0, -r * 0.24, -r * 0.08), face_role, scale=(1.02, 0.86, 0.84), u=u_s, v=v_s, M=group)
        for bx, bz, br in ((-0.42, 0.34, 0.21), (0.0, 0.39, 0.25), (0.42, 0.34, 0.21)):
            self.sphere(r * br, (r * bx, -r * 0.74, r * bz), ear_inner, scale=(1.06, 0.62, 0.86), u=u_sub, v=v_sub, M=group)

        # 3. Big Glossy Espresso-Cocoa Kawaii Eyes + Sparkling White Starlight Catchlights + Rosy Cheeks + Happy Smile!
        for sx in (-1, 1):
            ex, ey, ez = sx * r * 0.33, -r * 0.94, -r * 0.06
            self.sphere(r * 0.165, (ex, ey, ez), "dark", scale=(0.95, 0.50, 1.15), u=u_sub, v=v_sub, M=group)
            self.sphere(r * 0.060, (ex - sx * r * 0.045, ey - r * 0.068, ez + r * 0.062), "light", scale=(1.0, 0.6, 1.0), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)
            self.sphere(r * 0.145, (sx * r * 0.52, -r * 0.88, -r * 0.24), blush_role, scale=(1.25, 0.40, 0.72), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)
        self.sphere(r * 0.130, (0.0, -r * 0.95, -r * 0.29), "dark", scale=(1.32, 0.40, 0.78), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)
        self.sphere(r * 0.090, (0.0, -r * 0.99, -r * 0.31), blush_role, scale=(1.20, 0.36, 0.64), u=max(6, u_sub - 2), v=max(4, v_sub - 1), M=group)

        # 4. Optional Fluffy Milk-Cream Cloud Cushion Pillow right underneath (signature `logo.png` cloud!)
        if with_cloud:
            for cx, cy, cz, cr in (
                (0.0, 0.0, -r * 0.98, r * 0.60),
                (-r * 0.66, 0.0, -r * 0.94, r * 0.48),
                ( r * 0.66, 0.0, -r * 0.94, r * 0.48),
                (-r * 0.34, -r * 0.24, -r * 0.98, r * 0.42),
                ( r * 0.34, -r * 0.24, -r * 0.98, r * 0.42),
                (0.0, r * 0.28, -r * 0.95, r * 0.44),
            ):
                self.sphere(cr, (cx, cy, cz), "light", scale=(1.08, 0.92, 0.76), u=14, v=10, M=group)

    def shopping_cart(self, loc, size, role="light", direction=(0, -1, 0), M=None):
        base = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction)
        s = size
        t = s * 0.12
        self.box((s * 0.92, t, t), (0.04 * s, 0, -0.14 * s), role, bevel=t * 0.25, M=base)
        self.box((s * 1.05, t, t), (0.08 * s, 0, 0.30 * s), role, bevel=t * 0.25, M=base)
        self.box((s * 0.98, t, t * 0.85), (0.06 * s, 0, 0.08 * s), role, bevel=t * 0.2, M=base)
        self.box((t, t, s * 0.52), role=role, bevel=t * 0.2, matrix=base @ trs((-0.44 * s, 0, 0.08 * s), (0, 0.16, 0)))
        self.box((t, t, s * 0.50), role=role, bevel=t * 0.2, matrix=base @ trs((0.54 * s, 0, 0.08 * s), (0, -0.18, 0)))
        for x in (-0.12 * s, 0.22 * s):
            self.box((t * 0.8, t, s * 0.44), (x, 0, 0.08 * s), role, bevel=t * 0.2, M=base)
        self.box((s * 0.32, t, t), role=role, bevel=t * 0.25, matrix=base @ trs((-0.57 * s, 0, 0.37 * s), (0, 0.36, 0)))
        self.box((s * 0.78, t, t * 0.9), (0.08 * s, 0, -0.32 * s), role, bevel=t * 0.2, M=base)
        for x in (-0.24 * s, 0.38 * s):
            self.cyl(s * 0.13, t * 1.15, (x, 0, -0.44 * s), role, axis="Y", segments=14, M=base)

    def spray_can(self, loc, radius, role="primary", trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", direction=(0, -1, 0), M=None, face=True, drips=False, puff=False, tilt=(0, 0, 0), detail="high", with_crown=False, collar_drips=False, drip_role=None):
        if self.mascot_style == "billie_bear":
            self.billie_bear(loc, radius * 1.05, role="primary", face_role="light", ear_inner="wood", blush_role="trim", direction=direction, M=M, tilt=tilt, with_cloud=with_crown, detail=detail)
            return
        r = radius
        vt = self.is_stylized
        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0, 0, 0), tilt)
        segs = 18 if detail == "high" else (12 if detail == "med" else 8)
        bev = r * 0.036 if detail == "high" else 0.0
        if detail == "high":
            bm = bmesh.new()
            # Plump chubby vinyl-toy barrel silhouette when vinyl_toy mode is active!
            profile = [(-0.96, 0.90), (-0.64, 1.04), (-0.08, 1.12), (0.38, 1.10), (0.70, 1.04)] if vt else [(-1.02, 0.87), (-0.72, 0.96), (-0.15, 1.04), (0.38, 1.06), (0.74, 1.02)]
            rings = []
            for pz, pr in profile:
                ring = [bm.verts.new((pr * r * math.cos(math.tau * i / segs), pr * r * math.sin(math.tau * i / segs), pz * r)) for i in range(segs)]
                rings.append(ring)
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
            for k in range(len(rings) - 1):
                for i in range(segs):
                    j = (i + 1) % segs
                    bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            self.add("can_body", bm, role, group)
        else:
            self.cyl(r * (0.94 if vt else 0.90), r * 1.66, (0, 0, -0.14 * r), role, segments=segs, radius2=r * (1.08 if vt else 1.04), bevel=bev, M=group)
        bot_z = -1.08 if vt else -1.14
        top_z = 0.82 if vt else 0.86
        self.cyl(r * 0.98, r * 0.25, (0, 0, bot_z * r), trim_role, segments=segs, radius2=r * 0.94, bevel=bev, M=group)
        if detail == "high":
            # Bold thick comic black ink collar rings
            self.cyl(r * 0.94, r * 0.085, (0, 0, (bot_z - 0.14) * r), "dark", segments=segs, M=group)
            self.cyl(r * 1.02, r * 0.075, (0, 0, (bot_z + 0.13) * r), "dark", segments=segs, M=group)
            self.cyl(r * 1.11, r * 0.080, (0, 0, (top_z - 0.13) * r), "dark", segments=segs, M=group)
            self.cyl(r * 1.08, r * 0.075, (0, 0, (top_z + 0.13) * r), "dark", segments=segs, M=group)
        self.cyl(r * 1.13, r * 0.24, (0, 0, top_z * r), trim_role, segments=segs, radius2=r * 1.09, bevel=bev, M=group)
        self.cyl(r * 1.00, r * 0.34, (0, 0, (top_z + 0.28) * r), trim_role, segments=segs, radius2=r * 0.44, bevel=bev, M=group)
        if detail != "low":
            self.cyl(r * 0.43, r * 0.075, (0, 0, (top_z + 0.47) * r), "dark", segments=max(8, segs - 4), M=group)
        nozzle_m = group @ trs((0, 0, (top_z + 0.66) * r), (0.04, 0.05, 0))
        self.cyl(r * 0.32, r * 0.36, (0, 0, 0), nozzle_role, segments=max(8, segs - 4), radius2=r * 0.30, bevel=bev, M=nozzle_m)
        if detail == "high":
            self.cyl(r * 0.35, r * 0.06, (0, 0, -0.15 * r), "dark", segments=max(8, segs - 4), M=nozzle_m)
        if detail != "low":
            self.cyl(r * 0.095, r * 0.07, (0, -0.30 * r, 0.03 * r), "dark", axis="Y", segments=8, M=nozzle_m)
        if with_crown:
            self.crown((0.60 * r, 0.0, (top_z + 0.24) * r), r * 0.32, r * 0.31, role="gold", gem_role=role, tilt=(0.04, 0.42, 0.0), M=group)
        if collar_drips:
            drole = drip_role or ("accent" if role == "primary" else "primary")
            if vt and detail == "high":
                # Keep collar drips on the side/back cheeks so the front angry face & eye star stay 100% clear!
                chains = [
                    (-1.02 * r, -0.35 * r, (top_z - 0.14) * r, 0.42 * r, 0.12 * r),
                    (1.04 * r, -0.28 * r, (top_z - 0.14) * r, 0.36 * r, 0.12 * r),
                    (0.18 * r, 1.02 * r, (top_z - 0.14) * r, 0.44 * r, 0.13 * r),
                ]
                self.slime_drips_mb(chains, role=drole, res=max(0.016, r * 0.08), target_tris=240, M=group)
            else:
                for az, dl in ((-0.75, 0.38), (0.85, 0.42)):
                    self.fat_drip((math.sin(az) * r * 1.08, -math.cos(az) * r * 1.08, 0.72 * r), dl * r, r * 0.12, drole, M=group, pearl=False, detail="low")
        if face:
            r_surf = r * (1.11 if (vt and detail == "high") else (1.05 if detail == "high" else 1.02))
            eu, ev = (9, 5) if detail == "high" else (7, 5)
            eye_scale = 1.18 if vt else 1.0
            for side in (-1, 1):
                az = side * 0.36
                d_vec = Vector((math.sin(az), -math.cos(az), 0.0))
                pos = Vector((d_vec.x * r_surf, d_vec.y * r_surf, 0.14 * r))
                eye_m = group @ Matrix.Translation(pos) @ facing(d_vec)
                ang = -side * 0.28
                self.sphere(r * 0.24 * eye_scale, (0, 0.01 * r, 0), "dark", scale=(1.22, 0.42, 0.86), u=eu, v=ev, rot=(0, ang, 0), M=eye_m)
                self.sphere(r * 0.185 * eye_scale, (0, -0.028 * r, -0.014 * r), eye_role, scale=(1.12, 0.44, 0.72), u=eu, v=ev, rot=(0, ang, 0), M=eye_m)
                self.box((r * 0.50 * eye_scale, r * 0.12, r * 0.115), role="dark", bevel=r * 0.024 if detail == "high" else 0.0, matrix=eye_m @ trs((0, -0.042 * r, 0.125 * r * eye_scale), (0, -side * 0.34, 0)), segments=2 if detail == "high" else 1)
                if detail == "high":
                    self.box((r * 0.50 * eye_scale, r * 0.095, r * 0.090), role=role, bevel=r * 0.02, matrix=eye_m @ trs((0, -0.014 * r, 0.195 * r * eye_scale), (0, -side * 0.32, 0)), segments=2)
            mouth_m = group @ trs((0, -r_surf * 0.99, -0.19 * r), (0, -0.10, 0))
            self.box((r * 0.62, r * 0.11, r * 0.088), (0, -0.020 * r, 0), "dark", bevel=r * 0.026 if detail == "high" else 0.0, segments=2 if detail == "high" else 1, M=mouth_m)
            s_az = 0.72
            s_dir = Vector((math.sin(s_az), -math.cos(s_az), 0.10)).normalized()
            self.star((math.sin(s_az) * r * 1.22, -math.cos(s_az) * r * 1.22, 0.34 * r), r * 0.25, spark_role, direction=s_dir, M=group)
            if detail == "high":
                self.star((math.sin(s_az) * r * 1.26, -math.cos(s_az) * r * 1.26, 0.34 * r), r * 0.11, "light", direction=s_dir, M=group, outline_role=None)
        if drips:
            if vt and detail == "high":
                chains = [
                    (-0.42 * r, -0.82 * r, (bot_z - 0.10) * r, 0.32 * r, 0.12 * r),
                    (0.14 * r, -0.88 * r, (bot_z - 0.10) * r, 0.42 * r, 0.13 * r),
                    (0.56 * r, -0.72 * r, (bot_z - 0.10) * r, 0.25 * r, 0.11 * r),
                ]
                self.slime_drips_mb(chains, role=role, res=max(0.016, r * 0.08), target_tris=240, M=group)
            else:
                for x, y, length in ((-0.35, -0.82, 0.26), (0.14, -0.86, 0.34), (0.50, -0.74, 0.20)):
                    self.fat_drip((x * r, y * r, -1.24 * r), length * r, r * 0.10, role, M=group, detail="low")

    def mascot(self, loc, radius, role="primary", eye_role="light", direction=(0, -1, 0), M=None, drips=True, tongue=True):
        if self.mascot_style == "billie_bear":
            self.billie_bear(loc, radius * 0.88, role=role, face_role="light", ear_inner="wood", blush_role="trim", direction=direction, M=M, with_cloud=False, detail="med")
            return
        if self.mascot_style == "spray_can":
            self.spray_can(
                loc,
                radius * 0.72,
                role=role,
                trim_role="metal",
                nozzle_role="light",
                eye_role=eye_role,
                spark_role="gold",
                direction=direction,
                M=M,
                face=True,
                drips=drips,
                puff=False,
                tilt=(0.06, -0.12, 0.0),
                detail="med",
            )
            return
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

    def curved_pillar(self, sections, role, corner=0.38, segs=3, M=None, collide=False):
        """Loft a smooth organic curved & tapered rounded-rect vinyl pillar through [(cx, cy, z, w, d), ...]."""
        if self.low_poly:
            segs = 2
        bm = bmesh.new()
        rings = []
        for cx, cy, z, w, d in sections:
            hw, hd = w * 0.5, d * 0.5
            r = min(hw, hd) * corner
            pts = []
            corners = [
                (hw - r, -hd + r, -90.0),
                (hw - r, hd - r, 0.0),
                (-hw + r, hd - r, 90.0),
                (-hw + r, -hd + r, 180.0),
            ]
            denom = max(1, segs - 1) if self.low_poly else segs
            for ox, oy, a0 in corners:
                for i in range(segs):
                    a = math.radians(a0 + 90.0 * i / denom)
                    pts.append((cx + ox + r * math.cos(a), cy + oy + r * math.sin(a), z))
            rings.append([bm.verts.new(p) for p in pts])
        n = len(rings[0])
        for s in range(len(rings) - 1):
            r0, r1 = rings[s], rings[s + 1]
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = self.add("curved_pillar", bm, role, M or Matrix.Identity(4))
        if collide:
            lo = Vector((min(cx - w * 0.5 for cx, cy, z, w, d in sections),
                         min(cy - d * 0.5 for cx, cy, z, w, d in sections),
                         min(z for cx, cy, z, w, d in sections)))
            hi = Vector((max(cx + w * 0.5 for cx, cy, z, w, d in sections),
                         max(cy + d * 0.5 for cx, cy, z, w, d in sections),
                         max(z for cx, cy, z, w, d in sections)))
            mat = (M or Matrix.Identity(4)) @ Matrix.Translation((lo + hi) * 0.5)
            self.collider_from(mat, (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z))
        return ob

    def round_column(self, profile, role, segs=24, M=None, collide=False):
        """Lathe-sculpt a 360-degree circular curved vinyl column from [(z, radius), ...]."""
        if self.low_poly:
            segs = max(10, min(segs, 14))
        bm = bmesh.new()
        rings = []
        for z, r in profile:
            ring = []
            for i in range(segs):
                a = math.tau * i / segs
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
            rings.append(ring)
        for s in range(len(rings) - 1):
            r0, r1 = rings[s], rings[s + 1]
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = self.add("round_col", bm, role, M or Matrix.Identity(4))
        if collide:
            z0 = min(z for z, _ in profile)
            z1 = max(z for z, _ in profile)
            rmax = max(r for _, r in profile)
            mat = (M or Matrix.Identity(4)) @ Matrix.Translation((0.0, 0.0, (z0 + z1) * 0.5))
            self.collider_from(mat, (rmax * 1.9, rmax * 1.9, z1 - z0))
        return ob

    def mini_toy_car(self, loc, scale=1.0, body_role="accent", stripe_role="light", M=None):
        """Chubby rounded vinyl-toy sports car topper (facing +X, spinning smoothly over Garage!)."""
        group = (M or Matrix.Identity(4)) @ trs(loc, (0, 0, 0), (scale, scale, scale))
        # Plump rounded sports chassis + front nose splitter + racing stripe
        self.box((0.40, 0.22, 0.105), (0.0, 0.0, 0.068), body_role, bevel=0.036, segments=2, M=group)
        self.box((0.42, 0.20, 0.034), (0.01, 0.0, 0.032), "dark", bevel=0.012, segments=1, M=group)
        self.box((0.36, 0.052, 0.016), (0.01, 0.0, 0.118), stripe_role, bevel=0.006, segments=1, M=group)
        # Bubble coupe cockpit cabin + tinted side/front windshields
        self.box((0.21, 0.175, 0.095), (-0.025, 0.0, 0.145), "dark", bevel=0.034, segments=2, M=group)
        self.box((0.15, 0.145, 0.022), (-0.025, 0.0, 0.190), body_role, bevel=0.008, segments=1, M=group)
        self.box((0.024, 0.125, 0.052), (0.078, 0.0, 0.148), "light", bevel=0.008, segments=1, rot=(0, -0.32, 0), M=group)
        # Sporty rear wing spoiler + uprights
        for sy in (-0.065, 0.065):
            self.box((0.024, 0.018, 0.062), (-0.165, sy, 0.145), "dark", bevel=0.005, segments=1, M=group)
        self.box((0.068, 0.225, 0.020), (-0.180, 0.0, 0.178), stripe_role, bevel=0.007, segments=1, rot=(0, 0.16, 0), M=group)
        # 4 chunky rounded tires + bright chrome/gold rims
        for wx in (-0.125, 0.125):
            for sy in (-1, 1):
                self.cyl(0.054, 0.044, (wx, sy * 0.112, 0.054), "dark", axis="Y", segments=10, bevel=0.010, M=group)
                self.cyl(0.030, 0.050, (wx, sy * 0.114, 0.054), "gold", axis="Y", segments=8, bevel=0.004, M=group)
        # Glowing headlights (+X nose) & crimson taillights (-X rear)
        for sy in (-0.064, 0.064):
            self.sphere(0.022, (0.198, sy, 0.072), "light", scale=(0.6, 1.0, 0.85), u=6, v=4, M=group)
            self.box((0.016, 0.042, 0.024), (-0.200, sy, 0.078), "glow", bevel=0.005, segments=1, M=group)

    def tow_hook_assembly(self, loc, scale=1.0, role="gold", M=None):
        """Chunky stylized 3D impound tow-hook + chain links hanging downward from loc (0,0,0)."""
        group = (M or Matrix.Identity(4)) @ trs(loc, (0, 0, 0), (scale, scale, scale))
        # Upper mounting shackle + 2 chain links
        self.torus(0.036, 0.013, (0, 0, -0.025), "metal", axis="Y", seg_major=10, seg_minor=4, M=group)
        self.torus(0.034, 0.012, (0, 0, -0.078), "dark", axis="X", seg_major=10, seg_minor=4, M=group)
        # Heavy yellow-gold beveled crane pulley block
        self.box((0.095, 0.068, 0.095), (0, 0, -0.155), "dark", bevel=0.020, segments=1, M=group)
        self.box((0.062, 0.074, 0.062), (0, 0, -0.155), "accent", bevel=0.012, segments=1, M=group)
        self.cyl(0.018, 0.084, (0, 0, -0.155), "light", axis="Y", segments=8, M=group)
        # Chunky J-shaped cartoon tow-hook built from clean 2D extruded profile + collar
        self.cyl(0.024, 0.052, (0, 0, -0.220), "metal", segments=8, M=group)
        hook_pts = [
            (-0.022, -0.235), (0.022, -0.235),
            (0.026, -0.275), (0.075, -0.315), (0.082, -0.365),
            (0.048, -0.415), (-0.012, -0.425), (-0.070, -0.398),
            (-0.088, -0.345), (-0.064, -0.312), (-0.038, -0.328),
            (-0.042, -0.356), (-0.012, -0.376), (0.026, -0.368),
            (0.034, -0.335), (0.002, -0.305), (-0.022, -0.278),
        ]
        self.shape(hook_pts, -0.020, 0.020, role, bevel=0.006, M=group)


def build_sign_post(b, p):
    height = p.get("height", 2.08 if b.is_stylized else 2.42)
    board_role = p.get("board", "primary")
    pillar_role = p.get("pillar_role", "primary")
    base_role = p.get("base_role", "light")
    drip_role = p.get("drip_role", board_role)
    mascot_role = p.get("mascot_role", "primary")
    if b.is_stylized and p.get("circular", True):
        # V9 Low-Profile Airdrop-Scale 360-Degree Circular Vinyl Toy-Brand Beacon Pod (ZERO screens! ~1.48m tall matching Airdrop, 360° usable!)
        pad_role = p.get("pad_role", "primary")
        topper = p.get("topper", "")

        # 1. Wide Grounded Stepped Circular Landing Pad (matching 1nfx_ext_airdrop scale & stance!)
        b.cyl(0.64, 0.060, (0, 0, 0.030), "dark", segments=18, bevel=0.014)
        b.torus(0.575, 0.018, (0, 0, 0.062), "glow", axis="Z", seg_major=20, seg_minor=5)
        b.cyl(0.535, 0.060, (0, 0, 0.090), base_role, segments=18, bevel=0.014)
        b.cyl(0.455, 0.048, (0, 0, 0.140), pad_role, segments=18, bevel=0.012)
        for k in range(4):
            ang = k * math.pi * 0.5 + math.pi * 0.25
            pm = trs((0.525 * math.cos(ang), 0.525 * math.sin(ang), 0.088), (0, 0, ang))
            b.box((0.128, 0.122, 0.096), (0, 0, 0), "dark", bevel=0.020, segments=1, M=pm)
            b.box((0.032, 0.070, 0.024), (0.058, 0, 0.010), "glow", bevel=0.005, segments=1, M=pm)
            b.cyl(0.022, 0.020, (0.02, 0, 0.052), drip_role, segments=8, M=pm)
        b.collider_from(Matrix.Translation((0, 0, 0.09)), (1.24, 1.24, 0.18))

        # 2. Compact Low-Slung Curvy Circular Pod Drum (z = 0.14..0.58 — chunky & low matching Airdrop, ZERO screens!)
        col_profile = [
            (0.14, 0.375),
            (0.20, 0.408),
            (0.30, 0.372),
            (0.41, 0.358),
            (0.50, 0.382),
            (0.55, 0.392),
            (0.59, 0.350),
        ]
        b.round_column(col_profile, pillar_role, segs=22, collide=True)

        # 4-Way 360-Degree Compact Armor Ribs + Glowing Crimson Neon Flutes (at 45, 135, 225, 315 deg)
        for k in range(4):
            ang = k * math.pi * 0.5 + math.pi * 0.25
            ca, sa = math.cos(ang), math.sin(ang)
            rm = trs((0.362 * ca, 0.362 * sa, 0.35), (0.0, 0.0, ang))
            b.box((0.058, 0.084, 0.32), (0, 0, 0), "light" if pillar_role != "light" else "dark", bevel=0.015, segments=1, M=rm)
            b.box((0.024, 0.024, 0.23), (0.026, 0, 0), "glow", bevel=0.004, segments=1, M=rm)

        # 4-Way 360-Degree Framed EXTREME COMMUNITY Brand Plaques around the circular pod belly (0, 90, 180, 270 deg)
        if p.get("use_logo", True) and b.logo:
            for k in range(4):
                ang = k * math.pi * 0.5
                ca, sa = math.cos(ang), math.sin(ang)
                bm = trs((0.368 * ca, 0.368 * sa, 0.335), (0.0, 0.0, ang + math.pi * 0.5))
                b.box((0.34, 0.030, 0.21), (0, 0, 0), "dark", bevel=0.011, segments=1, M=bm)
                b.banner_decal(0.285, (0, -0.019, 0), M=bm)

        # 3. Smooth Lush 360-Degree Circular Organic Metaball Melting Paint Collar pouring cleanly in the 8 gaps ABOVE plaques!
        gap_angles = [math.radians(22.5 + k * 45.0) for k in range(8)]
        b.slime_collar_mb(0.392, 0.562, role=drip_role, drip_angles=gap_angles, drop_min=0.075, drop_max=0.125, rad=0.042, res=0.023, target_tris=960 if topper == "tow_siren" else 1200)

        # Compact Chrome & Obsidian Rotary Turntable Hub
        b.cyl(0.280, 0.040, (0, 0, 0.598), "dark", segments=16, bevel=0.010)
        b.torus(0.258, 0.014, (0, 0, 0.622), "glow", axis="Z", seg_major=18, seg_minor=5)
        b.cyl(0.180, 0.048, (0, 0, 0.642), "light", segments=16, bevel=0.010)

        # 4. 360-DEGREE ROTATING DOUBLE-SIDED SCULPTED SIGN HEAD + LOW-SLUNG HERO TOPPERS (~1.48m total matching Airdrop!)
        sz_sign = 0.85
        bw, bh = p.get("board_w", 1.14), 0.40
        sign_grp = Matrix.Translation((0.0, 0.0, sz_sign))

        if b.animate:
            b.define_bone("sign_ring", (0.0, 0.0, sz_sign), parent="root")
            b.define_bone("orbit", (0.0, 0.0, 0.34), parent="root")
            if topper == "car":
                b.define_bone("car", (0.0, 0.0, 1.13), parent="root")
                b.define_bone("crown", (0.0, 0.0, 1.32), parent="root")
            elif topper == "tow_siren":
                b.define_bone("siren", (0.0, 0.0, 1.16), parent="root")
                b.define_bone("crown", (0.0, 0.0, 1.32), parent="root")
                b.define_bone("hook_l", (-bw * 0.5 - 0.05, 0.0, sz_sign - 0.08), parent="sign_ring")
                b.define_bone("hook_r", (bw * 0.5 + 0.05, 0.0, sz_sign - 0.08), parent="sign_ring")
            else:
                b.define_bone("crown", (0.0, 0.0, 1.18), parent="root")

        with b.use_bone("sign_ring"):
            outer = rounded_rect(bw, bh, bh * 0.46, step=0.095)
            b.shape(outer, -0.088, 0.088, "light", bevel=0.026, M=sign_grp, collide=True)
            mid = inset_outline(outer, 0.038, smooth=1)
            b.shape(mid, -0.104, -0.078, "dark", bevel=0.006, M=sign_grp)
            b.shape(mid, 0.078, 0.104, "dark", bevel=0.006, M=sign_grp)
            inner = inset_outline(outer, 0.064, smooth=1)
            b.shape(inner, -0.114, -0.088, board_role, bevel=0.005, M=sign_grp)
            b.shape(inner, 0.088, 0.114, board_role, bevel=0.005, M=sign_grp)
            for sx in (-1, 1):
                b.cyl(0.032, 0.028, (sx * (bw * 0.5 + 0.008), 0, 0), "glow", axis="X", segments=10, bevel=0.005, M=sign_grp)
            text_y = 0.124
            icon = p.get("icon")
            sub = p.get("sub")
            label_x = -0.09 if icon else 0.0
            label_w = bw * (0.56 if icon else 0.78)
            label_h = 0.165 if not sub else 0.142
            label_z = 0.0 if not sub else 0.056
            text_role = p.get("text", "light")
            outline_role = p.get("text_outline", "dark")
            for side, y, rz in ((-1, -text_y, 0.0), (1, text_y, math.pi)):
                gx = label_x * (1 if side < 0 else -1) if icon else label_x
                b.text(p.get("label", "GARAGE"), label_h, (gx, y, label_z), text_role, depth=0.019, max_w=label_w, outline_role=outline_role, rot_z=rz, M=sign_grp)
                if sub:
                    b.box((0.48, 0.020, 0.086), (0.0, y + side * 0.002, -0.084), "dark", bevel=0.020, segments=1, M=sign_grp)
                    b.text(sub + " >>", 0.055, (0.0, y + side * 0.013, -0.084), "light", depth=0.012, max_w=0.39, outline_role=None, rot_z=rz, M=sign_grp)
                if icon == "house":
                    ix = (bw * 0.5 - 0.20) * (-side)
                    house = [(-0.084, -0.078), (0.084, -0.078), (0.084, 0.030), (0.0, 0.098), (-0.084, 0.030)]
                    b.shape(house, y - 0.012, y + 0.012, "light", bevel=0.006, M=sign_grp @ Matrix.Translation((ix, 0, 0.0)))
                    for k in range(3):
                        b.box((0.112, 0.012, 0.017), (ix, y + side * 0.015, -0.045 + k * 0.030), "dark", bevel=0.003, segments=1, M=sign_grp)
            if topper == "car":
                b.cyl(0.185, 0.030, (0, 0, bh * 0.5 + 0.015), "dark", segments=16, bevel=0.008, M=sign_grp)
                b.cyl(0.145, 0.018, (0, 0, bh * 0.5 + 0.030), "light", segments=16, bevel=0.005, M=sign_grp)
                b.torus(0.150, 0.010, (0, 0, bh * 0.5 + 0.038), "glow", axis="Z", seg_major=16, seg_minor=4, M=sign_grp)
            elif topper == "tow_siren":
                b.cyl(0.104, 0.038, (0, 0, bh * 0.5 + 0.019), "dark", segments=14, bevel=0.008, M=sign_grp)
                b.cyl(0.084, 0.022, (0, 0, bh * 0.5 + 0.044), "light", segments=14, bevel=0.005, M=sign_grp)
                b.cyl(0.066, 0.105, (0, 0, bh * 0.5 + 0.105), "glow", segments=14, bevel=0.012, M=sign_grp)
                b.cyl(0.074, 0.018, (0, 0, bh * 0.5 + 0.166), "dark", segments=14, bevel=0.005, M=sign_grp)
                for sx in (-1, 1):
                    b.box((0.11, 0.058, 0.054), (sx * (bw * 0.5 + 0.018), 0, -0.07), "dark", bevel=0.012, segments=1, M=sign_grp)
                    b.cyl(0.022, 0.068, (sx * (bw * 0.5 + 0.05), 0, -0.08), "metal", axis="Y", segments=8, M=sign_grp)

        if topper == "car":
            with b.use_bone("car"):
                b.mini_toy_car((0.0, 0.0, 1.09), scale=0.94, body_role="accent", stripe_role="light")
            with b.use_bone("crown"):
                b.crown((0.0, 0.0, 1.32), 0.114, 0.110, role="gold", gem_role="accent", tilt=(0.04, 0.14, 0.0))
        elif topper == "tow_siren":
            with b.use_bone("siren"):
                b.torus(0.085, 0.012, (0.0, 0.0, 1.16), "gold", axis="Z", seg_major=14, seg_minor=4)
                for k in range(4):
                    a = k * math.pi * 0.5
                    wm = trs((0.088 * math.cos(a), 0.088 * math.sin(a), 1.16), (0.0, 0.0, a))
                    b.box((0.028, 0.014, 0.070), (0, 0, 0), "light", bevel=0.005, segments=1, M=wm)
            with b.use_bone("crown"):
                b.crown((0.0, 0.0, 1.32), 0.112, 0.108, role="gold", gem_role="accent", tilt=(0.04, 0.14, 0.0))
            with b.use_bone("hook_l"):
                b.tow_hook_assembly((-bw * 0.5 - 0.05, 0.0, sz_sign - 0.08), scale=0.62, role="gold")
            with b.use_bone("hook_r"):
                b.tow_hook_assembly((bw * 0.5 + 0.05, 0.0, sz_sign - 0.08), scale=0.62, role="gold")
        else:
            with b.use_bone("crown"):
                b.crown((0.0, 0.0, 1.18), 0.120, 0.116, role="gold", gem_role="accent", tilt=(0.04, 0.14, 0.0))

        # 5. Orbiting Chubby Mini Spray Cans + 4 Crossed 3D Sparkle Stars cleanly outside pad & below hooks!
        with b.use_bone("orbit"):
            orb_r = 0.72 if topper == "tow_siren" else 0.66
            cz_base = 0.30 if topper == "tow_siren" else 0.36
            for k, (ang, cz, crole) in enumerate((
                (0.0, cz_base + 0.025, mascot_role),
                (math.pi, cz_base - 0.025, "light" if mascot_role != "light" else "accent"),
            )):
                cm = trs((orb_r * math.cos(ang), orb_r * math.sin(ang), cz), (0.0, 0.0, ang + math.pi * 0.5))
                b.spray_can((0, 0, 0), 0.052, role=crole, trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", face=True, drips=False, with_crown=False, tilt=(0.06, -0.12, 0.0), detail="low", M=cm)
            for k in range(4):
                ang = k * math.pi * 0.5 + math.pi * 0.25
                srole = "gold" if k % 2 == 0 else "light"
                sz = cz_base + (0.07 if k % 2 == 0 else -0.05)
                b.star((orb_r * math.cos(ang), orb_r * math.sin(ang), sz), 0.044, srole, direction=(math.cos(ang), math.sin(ang), 0.0), crossed=True)

        if b.animate:
            tracks = {
                "sign_ring": {"kind": "marker_spin", "amp_z": 0.018, "spin_deg": 360.0, "tilt_x": 1.6},
                "crown": {"kind": "crown_hover", "amp_z": 0.040, "rock_y": 8.0, "twist_z": 16.0},
                "orbit": {"kind": "marker_orbit", "amp_z": 0.032, "spin_deg": -360.0, "tilt_x": 3.0},
            }
            if topper == "car":
                tracks["car"] = {"kind": "marker_spin", "amp_z": 0.034, "spin_deg": -360.0, "tilt_x": 4.5}
            elif topper == "tow_siren":
                tracks["siren"] = {"kind": "siren_spin", "spin_deg": 720.0, "amp_z": 0.010}
                tracks["hook_l"] = {"kind": "hook_swing", "swing_deg": 18.0}
                tracks["hook_r"] = {"kind": "hook_swing", "swing_deg": -18.0}
            b.set_anim(frames=181, fps=30, tracks=tracks)
        return
    if b.is_stylized:
        # Legacy directional V7 Vinyl Toy-Brand Street-Mecha Sign Post (when circular=False)
        pad_role = p.get("pad_role", "primary")
        topper = p.get("topper", "")
        # 1. Chunky Sculpted Pedestal Base + Glowing Thruster Vents + Organic Melting Paint Splash
        b.chamfered_base(0.92, 0.66, 0.24, base_role, pad_role=pad_role, glow_role="glow", collide=True, vents=True)
        b.slime_drips_mb([
            (-0.14, -0.27, 0.245, 0.11, 0.042),
            (0.01, -0.29, 0.245, 0.14, 0.048),
            (0.14, -0.26, 0.245, 0.10, 0.038),
        ], role=drip_role, res=0.022, target_tris=220)

        # 2. Dynamic Curved S-Sweep Tapered Vinyl Pillar (ZERO stiff vertical rectangle!)
        z_base = 0.22
        z_neck = height - 0.72
        span = max(0.75, z_neck - z_base)

        def spine(u):
            # Muscular wide stance -> subtle playful S-curve lean left -> dynamic forward-right swoop into sign head
            cx = -0.055 * math.sin(u * math.pi) + 0.045 * (u ** 1.6)
            cy = 0.030 * math.sin(u * math.pi) - 0.025 * (u ** 1.4)
            z = z_base + span * u
            w = 0.44 - 0.10 * math.sin(u * math.pi * 0.82) + 0.03 * u
            d = 0.34 - 0.07 * math.sin(u * math.pi * 0.82) + 0.02 * u
            return cx, cy, z, w, d

        sec_us = [0.0, 0.04, 0.20, 0.42, 0.64, 0.84, 0.96, 1.0]
        core_secs = []
        cheek_secs = []
        for idx, u in enumerate(sec_us):
            cx, cy, z, w, d = spine(u)
            sc = 0.90 if idx in (0, len(sec_us) - 1) else 1.0
            core_secs.append((cx, cy, z, w * sc, d * sc))
            if 0.03 <= u <= 0.96:
                cheek_secs.append((cx + w * 0.38, cy, z, 0.105 * sc, (d + 0.025) * sc))
        b.curved_pillar(core_secs, pillar_role, corner=0.42, segs=3, collide=True)
        b.curved_pillar(cheek_secs, "light", corner=0.45, segs=2)

        # Glowing segmented neon spine channel + 4 dynamic angled aero chevrons following the curved belly
        for k in range(5):
            uk = 0.14 + k * 0.155
            cx, cy, z, w, d = spine(uk)
            next_cx, next_cy, next_z, _, _ = spine(min(1.0, uk + 0.08))
            ang_y = -math.atan2(next_cx - cx, next_z - z)
            ang_x = math.atan2(next_cy - cy, next_z - z)
            seg_m = trs((cx - w * 0.24, cy - d * 0.50 - 0.005, z), (ang_x, ang_y, 0.0))
            b.box((0.068, 0.022, span * 0.135), (0, 0, 0), "dark", bevel=0.008, segments=1, M=seg_m)
            b.box((0.024, 0.024, span * 0.105), (0, -0.010, 0), "glow", bevel=0.004, segments=1, M=seg_m)
        for k in range(4):
            uk = 0.52 + k * 0.075
            cx, cy, z, w, d = spine(uk)
            b.box((0.082, 0.020, 0.022), role=drip_role, bevel=0.005, matrix=trs((cx + w * 0.34, cy - d * 0.51, z), (0.0, 0.42, 0.0)), segments=1)

        # Cute tilted glowing monitor perched on upper curved chest + melting chin drips (animated subtly!)
        mcx, mcy, mz, mw, md = spine(0.84)
        mon_m = trs((mcx, mcy - md * 0.46 - 0.04, mz), (-0.10, -0.05, 0.0))
        use_screen_logo = bool(p.get("screen_logo", p.get("use_logo", True)) and b.logo)
        if b.animate:
            mon_pivot = (mcx, mcy - md * 0.46, mz)
            b.define_bone("monitor", mon_pivot, parent="root")
            if use_screen_logo:
                logo_pivot = tuple(mon_m @ Vector((0.0, -0.094, -0.004)))
                b.define_bone("screen_logo", logo_pivot, parent="monitor")
            else:
                eyes_pivot = tuple(mon_m @ Vector((0.0, -0.090, 0.021)))
                mouth_pivot = tuple(mon_m @ Vector((0.0, -0.090, -0.038)))
                b.define_bone("face_eyes", eyes_pivot, parent="monitor")
                b.define_bone("face_mouth", mouth_pivot, parent="monitor")
        with b.use_bone("monitor"):
            if use_screen_logo:
                b.box((0.36, 0.145, 0.26), (0, 0, 0), "light", bevel=0.042, M=mon_m)
                b.box((0.30, 0.020, 0.205), (0, -0.072, 0), "dark", bevel=0.016, M=mon_m)
                b.box((0.265, 0.016, 0.176), (0, -0.081, 0), "screen", bevel=0.010, M=mon_m)
                b.box((0.215, 0.008, 0.009), (0, -0.091, 0.076), "glow", bevel=0.003, segments=1, M=mon_m)
                with b.use_bone("screen_logo"):
                    b.logo_decal(0.224, (0, -0.095, -0.009), M=mon_m, shader="emissive_alpha.sps")
            else:
                b.box((0.33, 0.145, 0.25), (0, 0, 0), "light", bevel=0.042, M=mon_m)
                b.box((0.265, 0.020, 0.195), (0, -0.072, 0), "dark", bevel=0.016, M=mon_m)
                b.box((0.225, 0.016, 0.155), (0, -0.081, 0), "screen", bevel=0.010, M=mon_m)
                b.angry_screen_face((0, -0.090, 0), 0.105, "glowtrim" if board_role == "light" else "glow", M=mon_m, eyes_bone="face_eyes", mouth_bone="face_mouth")
            b.slime_drips_mb([
                (-0.082, -0.068, -0.108, 0.095, 0.032),
                (0.012, -0.072, -0.108, 0.125, 0.036),
                (0.090, -0.064, -0.108, 0.078, 0.028),
            ], role=drip_role, res=0.018, target_tris=220, M=mon_m)

        # Lower pillar chubby animated Spray Can Mascot peeking out of sculpted tilted comic shield
        scx, scy, sz, sw, sd = spine(0.36)
        b.shield_plaque((scx, scy - sd * 0.50 - 0.016, sz), 0.30, 0.37, role="dark", border_role="light", accent_role="accent")
        mascot_pos = (scx, scy - sd * 0.50 - 0.082, sz - 0.01)
        if b.animate:
            b.define_bone("mascot", mascot_pos, parent="root")
        with b.use_bone("mascot"):
            b.spray_can(mascot_pos, 0.088, role=mascot_role, trim_role="metal", nozzle_role="light", spark_role="gold", face=True, with_crown=True, tilt=(0.06, -0.12, 0.0), detail="low")

        # 3. Articulated Glossy Rubber Shock-Collar Neck Joint (visually grounds the bouncing/swaying sign head!)
        ncx, ncy, nz, nw, nd = spine(1.0)
        b.cyl(0.145, 0.055, (ncx, ncy, nz + 0.01), "dark", segments=16, bevel=0.012)
        b.torus(0.132, 0.022, (ncx, ncy, nz + 0.048), "accent", axis="Z", seg_major=16, seg_minor=6)
        b.cyl(0.125, 0.060, (ncx, ncy, nz + 0.078), "dark", segments=14, bevel=0.010)

        # 4. Dynamic Living Sculpted Sign Head (`head` bone rocks & floats playfully!)
        head_pivot = (ncx, ncy, nz + 0.068)
        bx = p.get("board_x", 0.22)
        bw, bh = p.get("board_w", 1.50), 0.64
        bz = nz + 0.36
        # Jaunty comic tilt (-2.6 deg) kills all rigid CAD boxiness!
        tilt_y = math.radians(-2.6)
        group = trs((bx, ncy, bz), (0.0, tilt_y, 0.0))

        if b.animate:
            b.define_bone("head", head_pivot, parent="root")
            crown_local = Vector((bw * 0.5 - 0.24, 0.0, bh * 0.5 + 0.055))
            crown_world = group @ crown_local
            b.define_bone("crown", tuple(crown_world), parent="head")
            if topper == "car":
                car_local = Vector((-bw * 0.16, 0.0, bh * 0.5 + 0.145))
                b.define_bone("car", tuple(group @ car_local), parent="head")
            elif topper == "tow_siren":
                siren_local = Vector((-bw * 0.24, 0.0, bh * 0.5 + 0.140))
                hook_local = Vector((-bw * 0.5 - 0.18, 0.0, -0.06))
                b.define_bone("siren", tuple(group @ siren_local), parent="head")
                b.define_bone("hook", tuple(group @ hook_local), parent="head")

        with b.use_bone("head"):
            outer = sculpted_sign_outline(bw, bh, arch=0.055, wave=0.036, chamfer=0.26, nose_r=0.28, step=0.105)
            b.shape(outer, -0.118, 0.118, "light", bevel=0.036, M=group, collide=True)
            mid = inset_outline(outer, 0.052, smooth=2)
            b.shape(mid, -0.136, -0.106, "dark", bevel=0.008, M=group)
            b.shape(mid, 0.106, 0.136, "dark", bevel=0.008, M=group)
            inner = inset_outline(outer, 0.090, smooth=2)
            b.shape(inner, -0.148, -0.118, board_role, bevel=0.006, M=group)
            b.shape(inner, 0.118, 0.148, board_role, bevel=0.006, M=group)
            # Twin glowing crimson mecha vents on the left chamfered thruster hood
            for vz in (-0.065, 0.060):
                b.box((0.030, 0.135, 0.044), (-bw * 0.5 - 0.006, 0, vz - 0.035), "dark", bevel=0.007, segments=1, M=group)
                b.box((0.016, 0.085, 0.020), (-bw * 0.5 - 0.020, 0, vz - 0.035), "glow", bevel=0.004, segments=1, M=group)
            text_y = 0.160
            icon = p.get("icon")
            sub = p.get("sub")
            label_x = -0.10 if icon else 0.02
            label_w = bw * (0.56 if icon else 0.76)
            label_h = 0.215 if not sub else 0.178
            label_z = 0.015 if not sub else 0.082
            text_role = p.get("text", "light")
            outline_role = p.get("text_outline", "dark")
            for side, y, rz in ((-1, -text_y, 0.0), (1, text_y, math.pi)):
                gx = label_x * (1 if side < 0 else -1) if icon else label_x
                b.text(p.get("label", "GARAGE"), label_h, (gx, y, label_z), text_role, depth=0.028, max_w=label_w, outline_role=outline_role, rot_z=rz, M=group)
                if sub:
                    sx_pos = gx + 0.03 * (1 if side < 0 else -1)
                    b.box((0.60, 0.024, 0.122), (sx_pos, y + side * 0.002, -0.118), "dark", bevel=0.030, segments=2, M=group)
                    b.text(sub + " >>", 0.074, (sx_pos, y + side * 0.015, -0.118), "light", depth=0.016, max_w=0.49, outline_role=None, rot_z=rz, M=group)
                b.star((-bw * 0.5 + 0.18 if side < 0 else bw * 0.5 - 0.18, y + side * 0.006, bh * 0.5 - 0.20), 0.042, "gold" if board_role != "light" else "accent", (0, side, 0), M=group)
                if icon:
                    ix = (bw * 0.5 - 0.27) * (-side)
                    if icon == "house":
                        house = [(-0.120, -0.110), (0.120, -0.110), (0.120, 0.042), (0.0, 0.140), (-0.120, 0.042)]
                        b.shape(house, y - 0.015, y + 0.015, "light", bevel=0.007, M=group @ Matrix.Translation((ix, 0, 0.01)))
                        for k in range(3):
                            b.box((0.160, 0.014, 0.025), (ix, y + side * 0.017, -0.060 + k * 0.043), "dark", bevel=0.004, segments=1, M=group)
                    elif icon == "hook":
                        # Chunky stylized 3D tow-hook icon matching the white garage-house icon scale
                        b.cyl(0.042, 0.030, (ix, y, 0.105), "light", axis="Y", segments=10, bevel=0.006, M=group)
                        b.cyl(0.018, 0.036, (ix, y, 0.105), "dark", axis="Y", segments=8, M=group)
                        hpts = [
                            (-0.028, 0.075), (0.028, 0.075),
                            (0.032, 0.028), (0.095, -0.018), (0.104, -0.075),
                            (0.060, -0.132), (-0.015, -0.142), (-0.088, -0.112),
                            (-0.108, -0.052), (-0.078, -0.015), (-0.046, -0.034),
                            (-0.052, -0.068), (-0.015, -0.090), (0.034, -0.080),
                            (0.042, -0.042), (0.002, -0.008), (-0.028, 0.022),
                        ]
                        b.shape(hpts, y - 0.015, y + 0.015, "light", bevel=0.006, M=group @ Matrix.Translation((ix, 0, 0.01)))
                    elif icon == "p_circle":
                        # Crisp white circular parking badge with bold P
                        b.cyl(0.128, 0.028, (ix, y, 0.01), "light", axis="Y", segments=16, bevel=0.008, M=group)
                        b.cyl(0.098, 0.034, (ix, y, 0.01), "dark", axis="Y", segments=14, bevel=0.005, M=group)
                        b.text("P", 0.138, (ix, y + side * 0.020, 0.006), "light", depth=0.014, max_w=0.115, outline_role=None, rot_z=rz, M=group)
            # Lush Organic Metaball Melting Paint Drips (bottom-right overhang + top-left corner, crisp smooth tips!)
            b.slime_drips_mb([
                (0.18, -0.115, -bh * 0.5 + 0.055, 0.17, 0.052),
                (0.33, -0.118, -bh * 0.5 + 0.065, 0.23, 0.058),
                (0.49, -0.112, -bh * 0.5 + 0.085, 0.14, 0.048),
            ], role=drip_role, res=0.025, target_tris=330, M=group)
            b.slime_drips_mb([
                (-bw * 0.5 + 0.28, -0.110, bh * 0.5 + 0.005, 0.12, 0.042),
                (-bw * 0.5 + 0.40, -0.112, bh * 0.5 + 0.020, 0.095, 0.038),
            ], role=drip_role, res=0.024, target_tris=150, M=group)

            # Static mounting hardware on head for signature toppers
            if topper == "car":
                # Glowing crimson circular holo-pad on top-left crest of Garage sign
                pad_pos = (-bw * 0.16, 0.0, bh * 0.5 + 0.052)
                b.cyl(0.18, 0.038, pad_pos, "dark", segments=16, bevel=0.010, M=group)
                b.cyl(0.14, 0.024, (pad_pos[0], 0.0, pad_pos[2] + 0.018), "light", segments=16, bevel=0.006, M=group)
                b.torus(0.145, 0.012, (pad_pos[0], 0.0, pad_pos[2] + 0.028), "glow", axis="Z", seg_major=18, seg_minor=5, M=group)
            elif topper == "tow_siren":
                # Tow-truck roof strobe siren base + left mini crane boom arm
                sp = (-bw * 0.24, 0.0, bh * 0.5 + 0.050)
                b.cyl(0.088, 0.046, sp, "dark", segments=14, bevel=0.010, M=group)
                b.cyl(0.072, 0.026, (sp[0], 0.0, sp[2] + 0.030), "light", segments=14, bevel=0.006, M=group)
                b.cyl(0.056, 0.118, (sp[0], 0.0, sp[2] + 0.095), "glow", segments=14, bevel=0.014, M=group)
                b.cyl(0.062, 0.022, (sp[0], 0.0, sp[2] + 0.162), "dark", segments=14, bevel=0.006, M=group)
                # Chunky angled mini tow-crane davit arm projecting off the outer-left cheek (100% clear of pillar!)
                b.box((0.24, 0.075, 0.078), (-bw * 0.5 - 0.085, 0.0, -0.04), "dark", bevel=0.018, segments=2, rot=(0, -0.18, 0), M=group)
                b.box((0.18, 0.042, 0.032), (-bw * 0.5 - 0.095, -0.028, -0.038), "accent", bevel=0.008, segments=1, rot=(0, -0.18, 0), M=group)
                b.cyl(0.032, 0.096, (-bw * 0.5 - 0.18, 0.0, -0.06), "metal", axis="Y", segments=10, bevel=0.006, M=group)

        with b.use_bone("crown"):
            b.crown((bw * 0.5 - 0.24, 0.0, bh * 0.5 + 0.055), 0.135, 0.135, role="gold", gem_role="accent", tilt=(0.05, 0.22, 0.0), M=group)

        if topper == "car":
            with b.use_bone("car"):
                b.mini_toy_car((-bw * 0.16, 0.0, bh * 0.5 + 0.115), scale=0.92, body_role="accent", stripe_role="light", M=group)
        elif topper == "tow_siren":
            with b.use_bone("siren"):
                sp = (-bw * 0.24, 0.0, bh * 0.5 + 0.145)
                b.torus(0.072, 0.013, sp, "gold", axis="Z", seg_major=16, seg_minor=5, M=group)
                for sgn in (-1, 1):
                    b.box((0.028, 0.015, 0.074), (sp[0] + sgn * 0.076, 0.0, sp[2]), "light", bevel=0.005, segments=1, M=group)
            with b.use_bone("hook"):
                b.tow_hook_assembly((-bw * 0.5 - 0.18, 0.0, -0.06), scale=0.90, role="gold", M=group)

        if b.animate:
            tracks = {
                "monitor": {"kind": "screen_wiggle", "amp_z": 0.005, "rock_y": 4.2, "yaw_z": 5.5, "nod_x": 2.4},
                "head": {"kind": "sign_sway", "amp_z": 0.016, "rock_y": 2.6, "rock_x": 1.2},
                "crown": {"kind": "crown_hover", "amp_z": 0.050, "rock_y": 8.5, "twist_z": 16.0},
                "mascot": {"kind": "mascot_nod", "amp_z": 0.020, "rock_y": 7.5},
            }
            if use_screen_logo:
                tracks["screen_logo"] = {"kind": "face_eyes", "amp_x": 0.006, "amp_z": 0.005, "tilt_y": 4.2}
            else:
                tracks["face_eyes"] = {"kind": "face_eyes", "amp_x": 0.015, "amp_z": 0.005, "tilt_y": 6.5}
                tracks["face_mouth"] = {"kind": "face_mouth", "amp_x": 0.007, "amp_z": 0.005, "tilt_y": 8.0}
            if topper == "car":
                tracks["car"] = {"kind": "marker_spin", "amp_z": 0.048, "spin_deg": 360.0, "tilt_x": 5.5}
            elif topper == "tow_siren":
                tracks["siren"] = {"kind": "siren_spin", "spin_deg": 720.0, "amp_z": 0.014}
                tracks["hook"] = {"kind": "hook_swing", "swing_deg": 22.0}
            b.set_anim(frames=121, fps=30, tracks=tracks)
        return
    aaa = b.mascot_style == "spray_can" or p.get("detail_tier") == "aaa"
    if aaa:
        b.chamfered_base(0.84, 0.62, 0.24, base_role, pad_role=pillar_role, glow_role="glowtrim", collide=True, vents=True)
    else:
        b.box((0.8, 0.58, 0.05), (0, 0, 0.025), pillar_role, bevel=0.02)
        b.box((0.76, 0.54, 0.12), (0, 0, 0.11), base_role, bevel=0.035, collide=True)
        b.box((0.62, 0.44, 0.1), (0, 0, 0.21), base_role, bevel=0.03)
        b.box((0.24, 0.01, 0.05), (0, -0.276, 0.11), "dark", bevel=0.005)
        for x in (-0.07, 0.0, 0.07):
            b.box((0.035, 0.012, 0.03), (x, -0.282, 0.11), "glowtrim", bevel=0.004)
    pillar_top = height - 0.58
    ph = pillar_top - 0.24
    pz = 0.24 + ph / 2
    b.box((0.32, 0.28, ph), (0, 0, pz), pillar_role, bevel=0.035, collide=True)
    b.box((0.075, 0.014, ph * 0.84), (0.10, -0.141, pz - ph * 0.04), "light", bevel=0.008)
    b.box((0.06, 0.014, ph * 0.78), (-0.088, -0.141, pz - ph * 0.05), "dark", bevel=0.006)
    b.box((0.018, 0.016, ph * 0.68), (-0.088, -0.149, pz - ph * 0.05), "glow", bevel=0.004)
    b.box((0.32, 0.014, 0.032), (0, -0.141, 0.35), "trim", bevel=0.004)
    if aaa:
        for k in range(4):
            b.box((0.075, 0.014, 0.018), role=drip_role, bevel=0.004, matrix=trs((0.10, -0.150, pillar_top - 0.52 - k * 0.048), (0, 0.42, 0)), segments=1)
    sz = pillar_top - (0.25 if aaa else 0.2)
    b.box((0.32, 0.14, 0.27), (0, -0.12, sz), "light", bevel=0.036)
    b.box((0.25, 0.014, 0.19), (0, -0.192, sz), "screen", bevel=0.012)
    if b.mascot_style == "spray_can":
        b.angry_screen_face((0, -0.200, sz), 0.11, "glow")
        # Clean armored monitor collar + twin status LEDs (zero awkward lump under screen)
        b.box((0.28, 0.065, 0.036), (0, -0.142, sz - 0.146), "dark", bevel=0.010, segments=2)
        for sx in (-1, 1):
            b.cyl(0.012, 0.014, (sx * 0.115, -0.193, sz - 0.112), "glowtrim", axis="Y", segments=8)
        b.shield_plaque((0, -0.155, 0.80), 0.26, 0.34, role="dark", border_role="light", accent_role="gold")
        if b.animate:
            b.define_bone("mascot", (0.0, -0.222, 0.79))
        with b.use_bone("mascot"):
            b.mascot((0, -0.222, 0.79), 0.105, mascot_role, "light", drips=False)
    else:
        b.x_mark((-0.055, -0.198, sz + 0.02), (0, -1, 0), 0.06, "glow")
        b.x_mark((0.055, -0.198, sz + 0.02), (0, -1, 0), 0.06, "glow")
        b.box((0.07, 0.01, 0.014), (0.01, -0.199, sz - 0.05), "glow", bevel=0.004)
        b.mascot((0, -0.17, 0.78), 0.085, mascot_role, "light", drips=False)
        b.crown((0, -0.17, 0.85), 0.05, 0.05, tilt=(0.2, 0, 0.15))
    bx = p.get("board_x", 0.22)
    bw, bh = p.get("board_w", 1.48), 0.58
    bz = height - 0.3
    group = Matrix.Translation((bx, 0, bz))
    outer = arrow_outline(bw, bh, 0.24, 0.13)
    b.shape(outer, -0.11, 0.11, "light", bevel=0.035, M=group, collide=True)
    if p.get("dark_border") or aaa:
        mid = arrow_outline(bw - 0.09, bh - 0.09, 0.20, 0.10)
        b.shape(mid, -0.125, -0.102, "dark", bevel=0.008, M=group)
        b.shape(mid, 0.102, 0.125, "dark", bevel=0.008, M=group)
        inner = arrow_outline(bw - 0.155, bh - 0.155, 0.165, 0.078)
        b.shape(inner, -0.136, -0.112, board_role, bevel=0.008, M=group)
        b.shape(inner, 0.112, 0.136, board_role, bevel=0.008, M=group)
        text_y = 0.148
    else:
        inner = arrow_outline(bw - 0.12, bh - 0.12, 0.17, 0.08)
        b.shape(inner, -0.118, -0.095, board_role, bevel=0.01, M=group)
        b.shape(inner, 0.095, 0.118, board_role, bevel=0.01, M=group)
        text_y = 0.128
    for z in (0.065, -0.065):
        b.box((0.02, 0.13, 0.035), (-bw / 2 - 0.004, 0, z), "dark", bevel=0.005, M=group)
    icon = p.get("icon")
    label_x = -0.1 if icon else 0.02
    label_w = bw * (0.58 if icon else 0.8)
    sub = p.get("sub")
    label_h = 0.205 if not sub else 0.172
    label_z = 0.0 if not sub else 0.068
    text_role = p.get("text", "light")
    outline_role = p.get("text_outline", "dark")
    for side, y, rz in ((-1, -text_y, 0.0), (1, text_y, math.pi)):
        gx = label_x * (1 if side < 0 else -1) if icon else label_x
        b.text(p.get("label", "GARAGE"), label_h, (gx, y, label_z), text_role, depth=0.026, max_w=label_w, outline_role=outline_role, rot_z=rz, M=group)
        if sub:
            sx_pos = gx + 0.04 * (1 if side < 0 else -1)
            if aaa:
                b.box((0.56, 0.022, 0.112), (sx_pos, y + side * 0.002, -0.128), "dark", bevel=0.032, M=group)
                sub_txt_role = "gold" if p.get("sub_role") in (None, "dark") else p.get("sub_role")
                b.text(sub + "  >>", 0.068, (sx_pos, y + side * 0.014, -0.128), sub_txt_role, depth=0.016, max_w=0.46, outline_role="dark", rot_z=rz, M=group)
            else:
                b.text(sub + "  >>", 0.078, (gx + 0.08 * (1 if side < 0 else -1), y, -0.13), p.get("sub_role", "primary" if board_role != "primary" else "accent"), depth=0.02, max_w=label_w * 0.6, outline_role=p.get("sub_outline", "light"), rot_z=rz, M=group)
        if aaa:
            b.star((-bw / 2 + 0.14 if side < 0 else bw / 2 - 0.14, y + side * 0.004, bh / 2 - 0.12), 0.036, "gold", (0, side, 0), M=group)
    if icon:
        ix = bw / 2 - 0.24
        house = [(-0.11, -0.1), (0.11, -0.1), (0.11, 0.04), (0.0, 0.13), (-0.11, 0.04)]
        b.shape(house, -text_y - 0.012, -text_y + 0.012, "light", bevel=0.006, M=group @ Matrix.Translation((ix, 0, 0)))
        for k in range(3):
            b.box((0.15, 0.01, 0.022), (ix, -text_y - 0.014, -0.065 + k * 0.04), board_role, bevel=0.003, M=group)
    if aaa:
        # Clean molten paint drip ONLY under overhanging right arrow wing (100% clear of neck monitor!)
        b.fat_curtain(0.18, bw / 2 - 0.06, -bh / 2 + 0.045, -0.115, drip_role, thick=0.032, max_drop=0.13, drops=2, M=group, pearls=False)
        if b.animate:
            b.define_bone("crown", (bx + bw / 2 - 0.22, 0.0, bz + bh / 2 + 0.01))
        with b.use_bone("crown"):
            b.crown((bw / 2 - 0.22, 0, bh / 2 + 0.01), 0.125, 0.125, role="gold", gem_role="primary", tilt=(0.04, 0.20, 0), M=group)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.048, "rock_y": 8.0, "twist_z": 16.0},
                "mascot": {"kind": "mascot_nod", "amp_z": 0.016, "rock_y": 6.5},
            })
    else:
        b.curtain(-bw / 2 + 0.15, bw / 2 - 0.1, -bh / 2 + 0.02, -0.1, drip_role, max_drop=0.17, drops=3, M=group)
        b.crown((bw / 2 - 0.22, 0, bh / 2 - 0.01), 0.1, 0.1, tilt=(0, 0.18, 0), M=group)


def build_kiosk_sign(b, p):
    frame_role = p.get("frame_role", "accent")
    panel_role = p.get("panel_role", "primary")
    body_role = p.get("body_role", panel_role)
    use_logo = p.get("use_logo", False) and bool(b.logo)
    if b.is_stylized:
        # V5 Vinyl Toy-Brand 3-Peak Crown Kiosk with 2-Chamber Organic Metaball Melting Slime Frame (matches sec_16!)
        b.chamfered_base(1.02, 0.48, 0.16, "dark", pad_role="dark", glow_role="glowtrim", collide=True, vents=True)
        pw, ph = 0.98, 1.18
        pz = 0.16 + ph / 2 + 0.01
        group = Matrix.Translation((0, 0, pz))
        outer_pts = crown_wave_outline(pw + 0.06, ph + 0.02, peak_h=0.22, side_h=0.10, corner=0.18, step=0.072)
        b.shape(outer_pts, -0.076, 0.076, body_role, bevel=0.028, M=group, collide=True)
        # Subtle recessed glossy inner face for deep comic contrast
        inner_pts = inset_outline(outer_pts, 0.056, smooth=2)
        b.shape(inner_pts, -0.088, -0.066, panel_role, bevel=0.006, M=group)
        b.shape(inner_pts, 0.066, 0.088, panel_role, bevel=0.006, M=group)
        frame_pts = inset_outline(outer_pts, 0.044, smooth=2)
        # 2-Chamber Organic Melting Gold Slime Frame (front & back!) proudly unbroken & juicy (matches sec_16!)
        for sy in (-1, 1):
            yf = sy * 0.090
            drips = [
                (-pw * 0.41, yf + sy * 0.008, 0.25, 0.19, 0.044),
                (pw * 0.41, yf + sy * 0.008, 0.25, 0.21, 0.046),
                (-pw * 0.34, yf + sy * 0.008, 0.24, 0.045, 0.032),
                (pw * 0.35, yf + sy * 0.008, 0.24, 0.045, 0.032),
            ]
            b.slime_frame_mb(frame_pts, yf, 0.046, role=frame_role, bridge_z=0.25, bridge_x=(-pw * 0.44, pw * 0.44), drips=drips, res=0.026, target_tris=1250, M=group)
        for side_sign, y, rz in ((-1, -0.104, 0.0), (1, 0.104, math.pi)):
            # Bold white "SHOP" with thick comic dark outline inside top crown-wave chamber
            b.text(p.get("label", "SHOP"), 0.165, (0, y, 0.43), "light", depth=0.028, max_w=pw * 0.62, outline_role="dark", rot_z=rz, M=group)
            # Giant EXTREME COMMUNITY logo filling center chamber cleanly
            b.logo_decal(0.76, (0, y + side_sign * 0.002, -0.03), rot=(math.pi / 2, 0, rz), M=group)
            if p.get("icon") == "cart":
                b.shopping_cart((0, y + side_sign * 0.008, -0.39), 0.19, p.get("cart_role", "light"), direction=(0, side_sign, 0), M=group)
                for sx in (-1, 1):
                    b.box((0.065, 0.012, 0.016), role="glow", bevel=0.003, matrix=group @ trs((sx * 0.20, y + side_sign * 0.004, -0.36), (0, sx * 0.35, rz)), segments=1)
                    b.box((0.055, 0.012, 0.016), role="glow", bevel=0.003, matrix=group @ trs((sx * 0.20, y + side_sign * 0.004, -0.43), (0, -sx * 0.35, rz)), segments=1)
            # Comic-outlined glossy white & gold 4-point sparkles
            b.star((0.36 * (-side_sign), y + side_sign * 0.004, 0.10), 0.044, "light", (0, side_sign, 0), M=group)
            b.star((-0.37 * (-side_sign), y + side_sign * 0.004, -0.22), 0.042, "light", (0, side_sign, 0), M=group)
            b.star((0.34 * (-side_sign), y + side_sign * 0.004, -0.42), 0.038, "gold", (0, side_sign, 0), M=group)
        if b.animate:
            b.define_bone("crown", (0.28, 0.0, pz + ph / 2 + 0.095))
        with b.use_bone("crown"):
            b.crown((0.28, 0, ph / 2 + 0.095), 0.110, 0.110, role="gold", gem_role="accent", tilt=(0.05, 0.24, 0), M=group)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.050, "rock_y": 9.0, "twist_z": 18.0},
            })
        return
    aaa = use_logo or p.get("detail_tier") == "aaa"
    if aaa:
        b.chamfered_base(0.98, 0.48, 0.16, "dark", pad_role="primary", glow_role="glow", collide=True, vents=True)
        pw, ph = 0.98, 1.18
        pz = 0.16 + ph / 2 + 0.01
        group = Matrix.Translation((0, 0, pz))
        # ONE shared scalloped contour for outer shell, glossy white tube frame, and dark inner panel (zero mismatch!)
        outer_pts = blob_outline(pw + 0.05, ph + 0.07, b.rng, wobble=0.013, lobes=3, lobe_amp=0.082, corner=0.15, step=0.084)
        frame_pts = inset_outline(outer_pts, 0.042, smooth=2)
        inner_pts = inset_outline(outer_pts, 0.062, smooth=2)
        b.shape(outer_pts, -0.072, 0.072, body_role, bevel=0.024, M=group, collide=True)
        b.shape(inner_pts, -0.092, -0.062, panel_role, bevel=0.008, M=group)
        b.shape(inner_pts, 0.062, 0.092, panel_role, bevel=0.008, M=group)
        b.tube_along_outline(frame_pts, -0.080, 0.044, frame_role, swell=0.07, seg=8, M=group)
        b.tube_along_outline(frame_pts, 0.080, 0.044, frame_role, swell=0.07, seg=8, M=group)
        for side_sign, y, rz in ((-1, -0.102, 0.0), (1, 0.102, math.pi)):
            b.text(p.get("label", "SHOP"), 0.165, (0, y, ph / 2 - 0.20), "light", depth=0.028, max_w=pw * 0.62, outline_role="dark", rot_z=rz, M=group)
            b.logo_decal(0.70, (0, y + side_sign * 0.002, 0.03), rot=(math.pi / 2, 0, rz), M=group)
            if p.get("icon") == "cart":
                b.shopping_cart((0, y + side_sign * 0.006, -0.34), 0.18, "light", direction=(0, side_sign, 0), M=group)
                b.box((0.42, 0.010, 0.018), (0, y + side_sign * 0.004, -0.475), "glow", bevel=0.004, M=group)
                for sx in (-1, 1):
                    b.star((sx * 0.27, y + side_sign * 0.004, -0.34), 0.040, "gold", (0, side_sign, 0), M=group)
                    b.box((0.06, 0.012, 0.016), role="light", bevel=0.003, matrix=group @ trs((sx * 0.19, y + side_sign * 0.004, -0.31), (0, sx * 0.35, rz)), segments=1)
                    b.box((0.05, 0.012, 0.016), role="light", bevel=0.003, matrix=group @ trs((sx * 0.19, y + side_sign * 0.004, -0.38), (0, -sx * 0.35, rz)), segments=1)
            b.star((0.33 * (-side_sign), y, 0.25), 0.044, "gold", (0, side_sign, 0), M=group)
            b.star((-0.34 * (-side_sign), y, -0.14), 0.034, "glowtrim", (0, side_sign, 0), M=group)
        if b.animate:
            b.define_bone("crown", (0.24, 0.0, pz + ph / 2 + 0.09))
        with b.use_bone("crown"):
            b.crown((0.24, 0, ph / 2 + 0.09), 0.105, 0.105, role="gold", gem_role="primary", tilt=(0.04, 0.20, 0), M=group)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.050, "rock_y": 9.0, "twist_z": 18.0},
            })
        return
    b.box((0.92, 0.42, 0.12), (0, 0, 0.06), "dark", bevel=0.03, collide=True)
    b.box((0.94, 0.44, 0.02), (0, 0, 0.125), "trim", bevel=0.008)
    for x in (-0.36, 0.36):
        b.box((0.08, 0.012, 0.03), (x, -0.215, 0.06), "glow", bevel=0.004)
    pw, ph = 0.96, 1.16
    pz = 0.14 + ph / 2 + 0.02
    group = Matrix.Translation((0, 0, pz))
    b.shape(blob_outline(pw, ph, b.rng, wobble=0.014, lobes=3, lobe_amp=0.075), -0.07, 0.07, frame_role, bevel=0.022, M=group, collide=True)
    inner = rounded_rect(pw - 0.15, ph - 0.19, 0.08)
    b.shape(inner, -0.088, -0.06, panel_role, bevel=0.008, M=group @ Matrix.Translation((0, 0, -0.02)))
    b.shape(inner, 0.06, 0.088, panel_role, bevel=0.008, M=group @ Matrix.Translation((0, 0, -0.02)))
    for side_sign, y, rz in ((-1, -0.094, 0.0), (1, 0.094, math.pi)):
        b.text(p.get("label", "SHOP"), 0.16, (0, y, ph / 2 - 0.21), "light", depth=0.024, max_w=pw * 0.66, rot_z=rz, M=group)
        b.text(b.brand_short, 0.13, (0, y, 0.0), "accent", depth=0.022, max_w=pw * 0.62, rot_z=rz, M=group)
        b.star((0.3 * (-side_sign), y, 0.14), 0.04, "light", (0, side_sign, 0), M=group)
    b.mascot((0, -0.1, -0.27), 0.11, "primary", "light", drips=False, M=group)
    if b.mascot_style != "spray_can":
        b.crown((0, -0.1, -0.18), 0.055, 0.05, tilt=(0.2, 0, -0.2), M=group)


def build_atm(b, p):
    frame_role = p.get("frame_role", "accent")
    panel_role = p.get("panel_role", "primary")
    body_role = p.get("body_role", panel_role)
    use_logo = p.get("use_logo", False) and bool(b.logo)
    if b.is_stylized:
        # V5 Vinyl Toy-Brand 3-Peak Crown ATM with Organic Melting Gold Slime Frame & Side Drips (matches sec_16 & sec_22!)
        b.chamfered_base(1.02, 0.78, 0.18, "dark", pad_role="dark", glow_role="glowtrim", collide=True, vents=True)
        w, d, h = 0.88, 0.66, 1.54
        zc = 0.18 + h / 2
        group = Matrix.Translation((0, 0, zc))
        outer_pts = crown_wave_outline(w + 0.04, h + 0.02, peak_h=0.20, side_h=0.09, corner=0.16, step=0.055)
        b.shape(outer_pts, -d / 2, d / 2, body_role, bevel=0.036, M=group, collide=True)
        frame_pts = inset_outline(outer_pts, 0.044, smooth=2)
        # Organic Melting Gold Slime Frame around 3-peak contour + plump unbroken divider below "ATM" (100% clear of screen!)
        front_drips = [
            (-w * 0.40, -d / 2 - 0.022, 0.47, 0.16, 0.042),
            (w * 0.40, -d / 2 - 0.022, 0.47, 0.18, 0.044),
            (-w * 0.39, -d / 2 - 0.022, -0.05, 0.13, 0.038),
            (w * 0.39, -d / 2 - 0.022, -0.10, 0.15, 0.040),
        ]
        b.slime_frame_mb(frame_pts, -d / 2 - 0.020, 0.046, role=frame_role, bridge_z=0.47, bridge_x=(-w * 0.42, w * 0.42), drips=front_drips, res=0.025, target_tris=1850, M=group)
        # Lush Organic Melting Slime Flowing Seamlessly Off Both Rounded Side Shoulders above side logos!
        side_x = max(abs(px) for px, pz in outer_pts if abs(pz + 0.10) < 0.34)
        for side_sign, rz in ((-1, -math.pi / 2), (1, math.pi / 2)):
            sx = side_sign * (side_x - 0.016)
            b.slime_drips_mb([
                (sx, -0.22, h / 2 - 0.02, 0.25, 0.048),
                (sx, -0.06, h / 2 + 0.01, 0.33, 0.054),
                (sx, 0.10, h / 2 + 0.00, 0.22, 0.046),
                (sx, 0.22, h / 2 - 0.03, 0.29, 0.050),
            ], role=frame_role, res=0.022, target_tris=580, M=group)
            b.logo_decal(0.52, (side_sign * (side_x + 0.010), 0, -0.16), rot=(math.pi / 2, 0, rz), M=group)
        # Bold "ATM" inside top wavy golden arch
        b.text(p.get("label", "ATM"), 0.162, (0, -d / 2 - 0.032, 0.62), "light", depth=0.026, max_w=w * 0.52, outline_role="dark", M=group)
        # Recessed Dark Console Bay (Screen + Card Reader + Keypad + Contactless + Cash Dispenser)
        sz = 0.20
        b.box((0.58, 0.06, 0.36), (0, -d / 2 - 0.014, sz), "dark", bevel=0.024, M=group)
        b.box((0.42, 0.014, 0.27), (-0.04, -d / 2 - 0.046, sz + 0.004), "screen", bevel=0.006, M=group)
        b.box((0.36, 0.010, 0.014), (-0.04, -d / 2 - 0.054, sz + 0.115), "glowtrim", bevel=0.003, M=group)
        b.box((0.066, 0.022, 0.17), (0.22, -d / 2 - 0.042, sz + 0.002), "metal", bevel=0.008, M=group)
        b.box((0.016, 0.014, 0.11), (0.22, -d / 2 - 0.055, sz + 0.002), "dark", bevel=0.003, M=group)
        b.box((0.048, 0.014, 0.016), (0.22, -d / 2 - 0.052, sz + 0.115), "glowtrim", bevel=0.004, M=group)
        if b.animate:
            b.define_bone("screen_fx", (-0.04, -d / 2 - 0.056, zc + sz + 0.018))
        with b.use_bone("screen_fx"):
            b.banner_decal(0.27, (-0.04, -d / 2 - 0.056, sz + 0.018), M=group, shader="decal.sps" if b.is_kawaii else "emissive_alpha.sps")
        for k, x in enumerate((-0.15, -0.04, 0.07)):
            b.box((0.072, 0.01, 0.042), (x, -d / 2 - 0.054, sz - 0.088), "glowtrim" if k == 1 else "glow", bevel=0.005, M=group)
        kz = -0.12
        b.box((0.58, 0.055, 0.23), (0, -d / 2 - 0.014, kz), "dark", bevel=0.020, M=group)
        for r in range(4):
            for c in range(3):
                b.box((0.034, 0.02, 0.032), (-0.21 + c * 0.044, -d / 2 - 0.046, kz + 0.07 - r * 0.044), "light", bevel=0.006, segments=1, M=group)
        for k, role in enumerate(("accent", "metal", "light")):
            b.box((0.068, 0.022, 0.038), (-0.01, -d / 2 - 0.046, kz + 0.062 - k * 0.058), role, bevel=0.006, segments=2, M=group)
        b.box((0.145, 0.075, 0.17), (0.175, -d / 2 - 0.022, kz), "metal", bevel=0.022, M=group)
        b.box((0.105, 0.012, 0.125), (0.175, -d / 2 - 0.060, kz), "dark", bevel=0.008, M=group)
        for i in range(3):
            b.torus(0.013 + i * 0.013, 0.0032, (0.175, -d / 2 - 0.067, kz), "light", seg_major=12, seg_minor=4, M=group)
        # Cash Dispenser Bay with Peeking Crimson-Banded Cash Bills!
        b.box((0.54, 0.06, 0.12), (0, -d / 2 - 0.012, -0.43), "dark", bevel=0.020, M=group)
        b.box((0.40, 0.02, 0.052), (0, -d / 2 - 0.038, -0.43), "screen", bevel=0.006, M=group)
        b.box((0.36, 0.012, 0.014), (0, -d / 2 - 0.048, -0.408), "glow", bevel=0.003, M=group)
        cash_m = group @ trs((0.0, -d / 2 - 0.056, -0.440), (0.16, 0.0, 0.03))
        b.box((0.18, 0.075, 0.024), (0, 0, 0), "light", bevel=0.004, segments=1, M=cash_m)
        b.box((0.038, 0.078, 0.028), (0, 0, 0), "accent", bevel=0.003, segments=1, M=cash_m)
        if b.animate:
            b.define_bone("crown", (0.28, -0.02, zc + h / 2 + 0.17))
            b.define_bone("stars", (0.0, -d / 2 - 0.042, zc))
        with b.use_bone("crown"):
            b.crown((0.28, -0.02, h / 2 + 0.17), 0.105, 0.105, role="gold", gem_role="accent", tilt=(0.05, 0.22, 0.0), M=group)
        with b.use_bone("stars"):
            b.star((-0.31, -d / 2 - 0.042, -0.55), 0.042, "light", M=group)
            b.star((0.31, -d / 2 - 0.042, 0.36), 0.038, "light", M=group)
            b.star((side_x + 0.012, -0.14, 0.12), 0.046, "light", direction=(1, 0, 0), M=group)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.045, "rock_y": 8.0, "twist_z": 16.0},
                "screen_fx": {"kind": "crown_hover", "amp_z": 0.014, "rock_y": 3.5, "twist_z": 0.0},
                "stars": {"kind": "crown_hover", "amp_z": 0.026, "rock_y": 4.0, "twist_z": 0.0},
            })
        return
    aaa = use_logo or p.get("detail_tier") == "aaa"
    if aaa:
        b.chamfered_base(1.02, 0.80, 0.18, "dark", pad_role="primary", glow_role="glow", collide=True, vents=True)
        w, d, h = 0.86, 0.66, 1.56
        zc = 0.18 + h / 2
        group = Matrix.Translation((0, 0, zc))
        # ONE shared contour for red outer body, glossy white tube frame, and recessed dark panel (zero screen clipping!)
        outer_pts = blob_outline(w + 0.04, h + 0.06, b.rng, wobble=0.012, lobes=3, lobe_amp=0.075, corner=0.15, step=0.055)
        frame_pts = inset_outline(outer_pts, 0.044, smooth=2)
        inner_pts = inset_outline(outer_pts, 0.066, smooth=2)
        b.shape(outer_pts, -d / 2, d / 2, body_role, bevel=0.032, M=group, collide=True)
        b.shape(inner_pts, -d / 2 - 0.016, -d / 2 + 0.024, panel_role, bevel=0.010, M=group)
        b.tube_along_outline(frame_pts, -d / 2 - 0.012, 0.045, frame_role, swell=0.06, seg=10, M=group)
        # Sleek recessed side cooling vents + flush EXTREME side logos (zero detached side blobs!)
        side_x = max(abs(px) for px, pz in outer_pts if abs(pz + 0.14) < 0.28)
        for side_sign, rz in ((-1, -math.pi / 2), (1, math.pi / 2)):
            vx = side_sign * (side_x - 0.002)
            b.box((0.024, 0.36, 0.13), (vx, 0.0, h / 2 - 0.26), "dark", bevel=0.012, segments=2, M=group)
            for k in (-1, 0, 1):
                b.box((0.012, 0.26, 0.018), (vx + side_sign * 0.010, 0.0, h / 2 - 0.26 + k * 0.032), "glowtrim" if k == 0 else "glow", bevel=0.004, segments=1, M=group)
            b.logo_decal(0.50, (side_sign * (side_x + 0.008), 0, -0.14), rot=(math.pi / 2, 0, rz), M=group)
        b.text(p.get("label", "ATM"), 0.155, (0, -d / 2 - 0.030, h / 2 - 0.18), "light", depth=0.024, max_w=w * 0.50, outline_role="dark", M=group)
        sz = 0.21
        b.box((0.58, 0.06, 0.38), (0, -d / 2 - 0.014, sz), "dark", bevel=0.022, M=group)
        b.box((0.42, 0.014, 0.29), (-0.04, -d / 2 - 0.046, sz + 0.004), "screen", bevel=0.006, M=group)
        b.box((0.36, 0.010, 0.014), (-0.04, -d / 2 - 0.054, sz + 0.125), "glow", bevel=0.003, M=group)
        b.box((0.065, 0.022, 0.18), (0.22, -d / 2 - 0.042, sz + 0.005), "metal", bevel=0.008, M=group)
        b.box((0.016, 0.014, 0.12), (0.22, -d / 2 - 0.055, sz + 0.005), "dark", bevel=0.003, M=group)
        b.box((0.048, 0.014, 0.016), (0.22, -d / 2 - 0.052, sz + 0.125), "glowtrim", bevel=0.004, M=group)
        if b.animate:
            b.define_bone("screen_fx", (-0.04, -d / 2 - 0.056, zc + sz + 0.038))
        with b.use_bone("screen_fx"):
            b.logo_decal(0.26, (-0.04, -d / 2 - 0.056, sz + 0.038), M=group, shader="emissive_alpha.sps")
        for k, x in enumerate((-0.15, -0.04, 0.07)):
            b.box((0.072, 0.01, 0.044), (x, -d / 2 - 0.054, sz - 0.088), "glowtrim" if k == 1 else "glow", bevel=0.005, M=group)
        kz = -0.12
        b.box((0.58, 0.055, 0.23), (0, -d / 2 - 0.014, kz), "dark", bevel=0.018, M=group)
        for r in range(4):
            for c in range(3):
                b.box((0.034, 0.02, 0.032), (-0.21 + c * 0.044, -d / 2 - 0.046, kz + 0.07 - r * 0.044), "light", bevel=0.006, segments=1, M=group)
        for k, role in enumerate(("primary", "gold", "light")):
            b.box((0.068, 0.022, 0.038), (-0.01, -d / 2 - 0.046, kz + 0.062 - k * 0.058), role, bevel=0.006, segments=2, M=group)
        b.box((0.145, 0.075, 0.17), (0.175, -d / 2 - 0.022, kz), "metal", bevel=0.022, M=group)
        b.box((0.105, 0.012, 0.125), (0.175, -d / 2 - 0.060, kz), "dark", bevel=0.008, M=group)
        for i in range(3):
            b.torus(0.013 + i * 0.013, 0.0032, (0.175, -d / 2 - 0.067, kz), "light", seg_major=12, seg_minor=4, M=group)
        # Cash dispenser bay with peeking banded cash stack!
        b.box((0.52, 0.06, 0.115), (0, -d / 2 - 0.012, -0.43), "dark", bevel=0.018, M=group)
        b.box((0.40, 0.02, 0.052), (0, -d / 2 - 0.038, -0.43), "screen", bevel=0.006, M=group)
        b.box((0.36, 0.012, 0.014), (0, -d / 2 - 0.048, -0.408), "glow", bevel=0.003, M=group)
        cash_m = group @ trs((0.0, -d / 2 - 0.056, -0.440), (0.16, 0.0, 0.03))
        b.box((0.17, 0.075, 0.022), (0, 0, 0), "light", bevel=0.004, segments=1, M=cash_m)
        b.box((0.036, 0.078, 0.026), (0, 0, 0), "primary", bevel=0.003, segments=1, M=cash_m)
        if b.animate:
            b.define_bone("crown", (0.24, -0.02, zc + h / 2 + 0.09))
            b.define_bone("stars", (0.0, -d / 2 - 0.036, zc))
        with b.use_bone("crown"):
            b.crown((0.24, -0.02, h / 2 + 0.09), 0.105, 0.105, role="gold", gem_role="primary", tilt=(0.05, 0.22, 0.0), M=group)
        with b.use_bone("stars"):
            b.star((-0.30, -d / 2 - 0.036, -0.52), 0.040, "gold", M=group)
            b.star((0.30, -d / 2 - 0.036, 0.44), 0.038, "glowtrim", M=group)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.045, "rock_y": 8.0, "twist_z": 16.0},
                "screen_fx": {"kind": "crown_hover", "amp_z": 0.014, "rock_y": 3.5, "twist_z": 0.0},
                "stars": {"kind": "crown_hover", "amp_z": 0.028, "rock_y": 4.0, "twist_z": 0.0},
            })
        return
    b.box((0.96, 0.76, 0.14), (0, 0, 0.07), "dark", bevel=0.035, collide=True)
    for x in (-0.38, 0.38):
        b.box((0.08, 0.012, 0.03), (x, -0.382, 0.07), "glow", bevel=0.004)
    w, d, h = 0.84, 0.64, 1.54
    zc = 0.14 + h / 2
    group = Matrix.Translation((0, 0, zc))
    b.shape(blob_outline(w, h, b.rng, wobble=0.016, lobes=3, lobe_amp=0.085, corner=0.16), -d / 2, d / 2, frame_role, bevel=0.035, M=group, collide=True)
    front = blob_outline(w - 0.15, h - 0.21, b.rng, wobble=0.01, lobes=2, lobe_amp=0.03, corner=0.12)
    b.shape(front, -d / 2 - 0.012, -d / 2 + 0.03, panel_role, bevel=0.01, M=group @ Matrix.Translation((0, 0, -0.04)))
    for x in (-w / 2 - 0.012, w / 2 + 0.012):
        b.box((0.012, d - 0.16, h - 0.36), (x, 0, -0.06), panel_role, bevel=0.006, M=group)
    for side_sign, x, rz in ((-1, -w / 2 - 0.022, -math.pi / 2), (1, w / 2 + 0.022, math.pi / 2)):
        b.text(b.brand_short, 0.1, (x, 0, -0.1), "accent", depth=0.018, max_w=d * 0.7, rot_z=rz, M=group)
    b.text(p.get("label", "ATM"), 0.16, (0, -d / 2 - 0.022, h / 2 - 0.15), "light", depth=0.026, max_w=w * 0.6, M=group)
    sz = 0.20
    b.box((0.54, 0.05, 0.37), (0, -d / 2 - 0.01, sz), "dark", bevel=0.02, M=group)
    b.box((0.46, 0.012, 0.29), (0, -d / 2 - 0.04, sz + 0.005), "screen", bevel=0.006, M=group)
    b.text(b.brand, 0.05, (0, -d / 2 - 0.05, sz + 0.05), "glow", depth=0.006, max_w=0.3, outline_role=None, M=group)
    for k, x in enumerate((-0.12, 0.0, 0.12)):
        b.box((0.075, 0.008, 0.045), (x, -d / 2 - 0.048, sz - 0.088), "glowtrim" if k == 1 else "glow", bevel=0.004, M=group)
    kz = -0.12
    b.box((0.54, 0.05, 0.22), (0, -d / 2 - 0.01, kz), "dark", bevel=0.015, M=group)
    for r in range(4):
        for c in range(3):
            b.box((0.032, 0.018, 0.03), (-0.2 + c * 0.042, -d / 2 - 0.042, kz + 0.07 - r * 0.042), "light", bevel=0.006, segments=2, M=group)
    for k, role in enumerate(("accent", "gold", "light")):
        b.box((0.06, 0.02, 0.035), (0.0, -d / 2 - 0.042, kz + 0.06 - k * 0.055), role, bevel=0.006, segments=2, M=group)
    b.box((0.13, 0.07, 0.16), (0.17, -d / 2 - 0.02, kz), "light", bevel=0.02, M=group)
    b.box((0.08, 0.012, 0.012), (0.17, -d / 2 - 0.058, kz + 0.04), "dark", bevel=0.003, M=group)
    for i in range(3):
        b.torus(0.012 + i * 0.012, 0.003, (0.17, -d / 2 - 0.058, kz - 0.025), "dark", seg_major=12, seg_minor=4, M=group)
    b.box((0.48, 0.05, 0.08), (0, -d / 2 - 0.01, -0.38), "dark", bevel=0.015, M=group)
    b.box((0.36, 0.012, 0.014), (0, -d / 2 - 0.04, -0.38), "glow", bevel=0.004, M=group)
    b.star((-w / 2 + 0.04, -d / 2 - 0.03, -0.48), 0.038, "light", M=group)


def build_safe(b, p):
    use_logo = p.get("use_logo", False) and bool(b.logo)
    aaa = use_logo or p.get("detail_tier") == "aaa"
    w, d, h = p.get("w", 1.08 if aaa else 1.0), p.get("d", 0.90 if aaa else 0.86), p.get("h", 1.20 if aaa else 0.95)
    body_role = p.get("body_role", "primary")
    cap_role = p.get("cap_role", "accent")
    spoke_role = p.get("spoke_role", "primary")
    for x in (-w / 2 + 0.12, w / 2 - 0.12):
        for y in (-d / 2 + 0.12, d / 2 - 0.12):
            b.cyl(0.075, 0.06, (x, y, 0.03), "dark", segments=14, bevel=0.014)
    if aaa and b.animate:
        if b.is_stylized:
            # V5 Vinyl Toy-Brand Seamless Vault with Lush One-Piece Metaball Melting Gold Slime Cap (matches sec_10!)
            dz = 0.05 + (h - 0.05) * 0.405
            fy = -d / 2
            dx = -0.05
            hole_r = 0.272
            wheel_r = 0.238
            hx = dx - hole_r - 0.048
            b.collider_from(Matrix.Translation((0, 0, 0.05 + (h - 0.05) / 2)), (w, d, h - 0.05))
            b.hollow_vault_shell(w, d, 0.05, h, dx, dz, hole_r, role=body_role, per_side=7, bevel=0.068, lip_depth=0.045)
            b.open_cyl_liner(hole_r - 0.006, fy + 0.032, d / 2 - 0.085, dx, dz, role="dark", segments=28, wall=0.005)
            b.box((0.22, 0.036, 0.016), (dx, -0.14, dz + 0.218), "glowtrim", bevel=0.004, segments=1)
            z_floor = dz - 0.168
            shelf_z = dz - 0.005
            cav_d = d - 0.19
            cav_y = 0.02
            b.box((0.37, cav_d, 0.020), (dx, cav_y, z_floor), "metal", bevel=0.005, segments=1)
            b.box((0.49, cav_d, 0.022), (dx, cav_y, shelf_z), "metal", bevel=0.005, segments=1)
            for bx, by, bz, rz in (
                (dx - 0.095, -0.09, z_floor + 0.030, 0.08),
                (dx - 0.095, 0.03, z_floor + 0.030, -0.06),
                (dx - 0.095, -0.03, z_floor + 0.070, 0.03),
            ):
                b.box((0.130, 0.064, 0.036), (bx, by, bz), "gold", bevel=0.008, segments=1, rot=(0, 0, rz))
            for cx, cy, cz, rz in (
                (dx + 0.095, -0.09, z_floor + 0.028, -0.09),
                (dx + 0.095, 0.03, z_floor + 0.028, 0.07),
                (dx + 0.095, -0.03, z_floor + 0.064, -0.02),
            ):
                sm = trs((cx, cy, cz), (0, 0, rz))
                b.box((0.125, 0.066, 0.032), (0, 0, 0), "light", bevel=0.005, segments=1, M=sm)
                b.box((0.028, 0.070, 0.036), (0, 0, 0), "primary", bevel=0.004, segments=1, M=sm)
            for cx, cy, cz, rz in (
                (dx - 0.10, -0.08, shelf_z + 0.029, 0.10),
                (dx - 0.10, 0.04, shelf_z + 0.029, -0.08),
                (dx - 0.095, -0.02, shelf_z + 0.065, 0.03),
            ):
                sm = trs((cx, cy, cz), (0, 0, rz))
                b.box((0.125, 0.066, 0.032), (0, 0, 0), "light", bevel=0.005, segments=1, M=sm)
                b.box((0.028, 0.070, 0.036), (0, 0, 0), "primary", bevel=0.004, segments=1, M=sm)
            for bx, by, bz, rz in (
                (dx + 0.095, -0.09, shelf_z + 0.030, -0.08),
                (dx + 0.095, 0.03, shelf_z + 0.030, 0.06),
                (dx + 0.095, -0.03, shelf_z + 0.070, -0.02),
            ):
                b.box((0.130, 0.064, 0.036), (bx, by, bz), "gold", bevel=0.008, segments=1, rot=(0, 0, rz))
            # ONE-PIECE Organic Metaball Melting Electric-Gold Slime Cap pouring over all 4 edges (clear of front logo!)
            safe_drips = [
                (-w * 0.46, fy - 0.004, 0.28, 0.074, 0.0, -1.0),
                (-w * 0.35, fy - 0.006, 0.17, 0.062, 0.0, -1.0),
                (w * 0.35, fy - 0.006, 0.19, 0.064, 0.0, -1.0),
                (w * 0.46, fy - 0.004, 0.32, 0.076, 0.0, -1.0),
                (w * 0.49, -0.25, 0.22, 0.068, 1.0, 0.0),
                (w * 0.49, 0.04, 0.28, 0.072, 1.0, 0.0),
                (w * 0.49, 0.30, 0.18, 0.062, 1.0, 0.0),
                (-w * 0.49, -0.22, 0.25, 0.068, -1.0, 0.0),
                (-w * 0.49, 0.08, 0.20, 0.064, -1.0, 0.0),
                (-w * 0.49, 0.32, 0.27, 0.070, -1.0, 0.0),
                (-0.28, d * 0.49, 0.24, 0.068, 0.0, 1.0),
                (0.06, d * 0.49, 0.30, 0.074, 0.0, 1.0),
                (0.32, d * 0.49, 0.20, 0.064, 0.0, 1.0),
            ]
            safe_pearls = [
                (-w * 0.46, fy - 0.012, h - 0.355, 0.036),
                (w * 0.46, fy - 0.012, h - 0.395, 0.038),
            ]
            b.slime_cap_mb(w + 0.02, d + 0.02, h + 0.002, role=cap_role, drips=safe_drips, pearls=safe_pearls, cap_thick=0.066, res=0.026, target_tris=2200)
            # Rigged Circular Vault Door with Electric-Gold outer rim + 3 chrome deadbolts + child Wheel
            b.define_bone("door", (hx, fy - 0.036, dz), parent="root")
            b.define_bone("wheel", (dx, fy - 0.072, dz), parent="door")
            b.define_bone("crown", (w / 2 - 0.20, -0.06, h + 0.096), parent="root")
            wheel_rim_role = p.get("wheel_rim_role", "light")
            with b.use_bone("door"):
                b.cyl(hole_r + 0.016, 0.046, (dx, fy - 0.010, dz), body_role, axis="Y", segments=28, bevel=0.014)
                b.cyl(hole_r - 0.014, 0.038, (dx, fy + 0.030, dz), "dark", axis="Y", segments=26, bevel=0.008)
                for bz in (dz - 0.12, dz, dz + 0.12):
                    b.cyl(0.018, 0.060, (dx + hole_r - 0.012, fy + 0.030, bz), "metal", axis="X", segments=8)
                b.cyl(wheel_r + 0.028, 0.028, (dx, fy - 0.024, dz), "dark", axis="Y", segments=26)
                b.cyl(wheel_r - 0.022, 0.024, (dx, fy - 0.036, dz), body_role, axis="Y", segments=24)
                b.torus(wheel_r, 0.044, (dx, fy - 0.044, dz), wheel_rim_role, seg_major=28, seg_minor=8)
                for k in range(8):
                    ra = k * math.tau / 8
                    b.cyl(0.015, 0.022, (dx + wheel_r * math.cos(ra), fy - 0.082, dz + wheel_r * math.sin(ra)), "dark", axis="Y", segments=8)
            with b.use_bone("wheel"):
                for k in range(3):
                    a = k * math.tau / 3 + math.pi / 6
                    sm = trs((dx, fy - 0.074, dz), (0, a, 0))
                    b.box((0.18, 0.034, 0.066), (0.115, 0, 0), "dark", bevel=0.015, segments=2, M=sm)
                    b.box((0.138, 0.022, 0.038), (0.115, -0.015, 0), cap_role, bevel=0.008, segments=2, M=sm)
                b.cyl(0.098, 0.078, (dx, fy - 0.062, dz), "dark", axis="Y", segments=20, bevel=0.014)
                b.cyl(0.076, 0.054, (dx, fy - 0.086, dz), "light", axis="Y", segments=18, bevel=0.010)
                if b.mascot_style == "spray_can":
                    b.spray_can((dx, fy - 0.128, dz), 0.042, role=cap_role, trim_role="metal", nozzle_role="light", spark_role="gold", face=True, detail="low")
            # Heavy hinge column, keypad, decals, dripping golden-hugged "SAFE" plinth + comic white stars (sec_10!)
            b.cyl(0.022, 0.34, (hx, fy - 0.036, dz), "light", segments=12)
            for z in (dz - 0.125, dz + 0.125):
                b.box((0.100, 0.060, 0.086), (hx + 0.015, fy - 0.018, z), "metal", bevel=0.015, segments=2)
                b.box((0.110, 0.064, 0.022), (hx + 0.015, fy - 0.018, z), "dark", bevel=0.005, segments=1)
            kx = w / 2 - 0.135
            b.box((0.165, 0.042, 0.29), (kx, fy - 0.012, dz + 0.01), "dark", bevel=0.022)
            b.box((0.140, 0.032, 0.26), (kx, fy - 0.022, dz + 0.01), "light", bevel=0.018)
            b.box((0.105, 0.012, 0.044), (kx, fy - 0.040, dz + 0.095), "screen", bevel=0.005)
            for r in range(3):
                for c in range(3):
                    b.box((0.022, 0.012, 0.020), (kx - 0.030 + c * 0.030, fy - 0.040, dz + 0.03 - r * 0.035), "glowtrim", bevel=0.004, segments=1)
            b.box((0.082, 0.012, 0.036), (kx, fy - 0.039, dz - 0.086), "dark", bevel=0.006, segments=1)
            b.logo_decal(0.50, (0.0, fy - 0.008, h - 0.225))
            for side_sign, x, rz in ((-1, -w / 2 - 0.008, -math.pi / 2), (1, w / 2 + 0.008, math.pi / 2)):
                b.logo_decal(0.60, (x, 0, h * 0.42), rot=(math.pi / 2, 0, rz))
            # Curved dark "SAFE" plinth hugged on both ends by lush golden slime blobs (sec_10!)
            b.box((0.48, 0.032, 0.118), (dx + 0.03, fy - 0.014, 0.128), "dark", bevel=0.038, segments=2)
            b.slime_drips_mb([
                (dx - 0.21, fy - 0.020, 0.165, 0.075, 0.046),
                (dx + 0.27, fy - 0.020, 0.165, 0.075, 0.046),
            ], role=cap_role, res=0.016, target_tris=380)
            b.text(p.get("label", "SAFE"), 0.078, (dx + 0.03, fy - 0.034, 0.128), "light", depth=0.016, max_w=0.35, outline_role="dark")
            b.star((-w / 2 + 0.12, fy - 0.014, dz + 0.29), 0.048, "light")
            b.star((w / 2 - 0.13, fy - 0.014, dz + 0.25), 0.044, "light")
            b.star((w / 2 - 0.14, fy - 0.014, 0.19), 0.044, "light")
            with b.use_bone("crown"):
                b.crown((w / 2 - 0.20, -0.06, h + 0.096), 0.132, 0.130, role="gold", gem_role="accent", tilt=(0.06, -0.14, 0.22))
            b.set_anim(frames=181, fps=30, tracks={
                "door": {"kind": "safe_door", "open_deg": -104.0},
                "wheel": {"kind": "safe_wheel", "spin_deg": 360.0},
                "crown": {"kind": "crown_hover", "amp_z": 0.042, "rock_y": 7.0, "twist_z": 14.0},
            })
            return
        dz = 0.05 + (h - 0.05) * 0.405
        fy = -d / 2
        dx = -0.05
        hole_r = 0.270
        wheel_r = 0.236
        hx = dx - hole_r - 0.048
        # Single seamless beveled hollow safe cabinet with circular vault opening (ZERO multi-box seams!)
        b.collider_from(Matrix.Translation((0, 0, 0.05 + (h - 0.05) / 2)), (w, d, h - 0.05))
        b.hollow_vault_shell(w, d, 0.05, h, dx, dz, hole_r, role=body_role, per_side=7, bevel=0.050, lip_depth=0.045)
        # Watertight dark cylindrical armored drum liner + interior glowing crimson LED strip
        b.open_cyl_liner(hole_r - 0.006, fy + 0.032, d / 2 - 0.085, dx, dz, role="dark", segments=28, wall=0.005)
        b.box((0.22, 0.036, 0.016), (dx, -0.14, dz + 0.218), "glow", bevel=0.004, segments=1)
        # Interior fitted floor & middle shelf cleanly clipped inside the circular drum
        z_floor = dz - 0.168
        shelf_z = dz - 0.005
        cav_d = d - 0.19
        cav_y = 0.02
        b.box((0.37, cav_d, 0.020), (dx, cav_y, z_floor), "metal", bevel=0.005, segments=1)
        b.box((0.49, cav_d, 0.022), (dx, cav_y, shelf_z), "metal", bevel=0.005, segments=1)
        # Lower shelf: gleaming gold bullion stack on left + crimson-banded cash stacks on right
        for bx, by, bz, rz in (
            (dx - 0.095, -0.09, z_floor + 0.030, 0.08),
            (dx - 0.095, 0.03, z_floor + 0.030, -0.06),
            (dx - 0.095, -0.03, z_floor + 0.070, 0.03),
        ):
            b.box((0.130, 0.064, 0.036), (bx, by, bz), "gold", bevel=0.008, segments=1, rot=(0, 0, rz))
        for cx, cy, cz, rz in (
            (dx + 0.095, -0.09, z_floor + 0.028, -0.09),
            (dx + 0.095, 0.03, z_floor + 0.028, 0.07),
            (dx + 0.095, -0.03, z_floor + 0.064, -0.02),
        ):
            sm = trs((cx, cy, cz), (0, 0, rz))
            b.box((0.125, 0.066, 0.032), (0, 0, 0), "light", bevel=0.005, segments=1, M=sm)
            b.box((0.028, 0.070, 0.036), (0, 0, 0), "primary", bevel=0.004, segments=1, M=sm)
        # Upper shelf: cash stacks on left + gleaming gold pyramid on right
        for cx, cy, cz, rz in (
            (dx - 0.10, -0.08, shelf_z + 0.029, 0.10),
            (dx - 0.10, 0.04, shelf_z + 0.029, -0.08),
            (dx - 0.095, -0.02, shelf_z + 0.065, 0.03),
        ):
            sm = trs((cx, cy, cz), (0, 0, rz))
            b.box((0.125, 0.066, 0.032), (0, 0, 0), "light", bevel=0.005, segments=1, M=sm)
            b.box((0.028, 0.070, 0.036), (0, 0, 0), "primary", bevel=0.004, segments=1, M=sm)
        for bx, by, bz, rz in (
            (dx + 0.095, -0.09, shelf_z + 0.030, -0.08),
            (dx + 0.095, 0.03, shelf_z + 0.030, 0.06),
            (dx + 0.095, -0.03, shelf_z + 0.070, -0.02),
        ):
            b.box((0.130, 0.064, 0.036), (bx, by, bz), "gold", bevel=0.008, segments=1, rot=(0, 0, rz))
        # Smooth pillowy molten paint cap seamlessly merged into side & corner drapes (zero gap line, zero front logo overlap!)
        b.box((w + 0.036, d + 0.036, 0.092), (0, 0, h + 0.010), cap_role, bevel=0.044, segments=3)
        for side_sign, rz in ((-1, -math.pi / 2), (1, math.pi / 2)):
            side_m = trs((side_sign * (w * 0.5 - 0.006), 0.0, 0.0), (0, 0, rz))
            b.fat_curtain(-d * 0.42, d * 0.42, h + 0.016, -0.004, cap_role, thick=0.034, max_drop=0.19, drops=2, M=side_m, pearls=False)
        back_m = trs((0.0, d * 0.5 - 0.006, 0.0), (0, 0, math.pi))
        b.fat_curtain(-w * 0.42, w * 0.42, h + 0.016, -0.004, cap_role, thick=0.034, max_drop=0.19, drops=2, M=back_m, pearls=False)
        b.fat_curtain(-w / 2 + 0.04, -0.34, h + 0.016, -d / 2 + 0.002, cap_role, thick=0.032, max_drop=0.14, drops=1, pearls=False)
        b.fat_curtain(0.34, w / 2 - 0.04, h + 0.016, -d / 2 + 0.002, cap_role, thick=0.032, max_drop=0.14, drops=1, pearls=False)
        # Rigged Circular Vault Door (pivots on left hinge) + child Vault Wheel
        b.define_bone("door", (hx, fy - 0.036, dz), parent="root")
        b.define_bone("wheel", (dx, fy - 0.072, dz), parent="door")
        b.define_bone("crown", (w / 2 - 0.20, -0.06, h + 0.060), parent="root")
        with b.use_bone("door"):
            # Circular beveled crimson vault door + dark circular inner steel plug + 3 chrome deadbolts
            b.cyl(hole_r + 0.015, 0.046, (dx, fy - 0.010, dz), body_role, axis="Y", segments=28, bevel=0.014)
            b.cyl(hole_r - 0.014, 0.038, (dx, fy + 0.030, dz), "dark", axis="Y", segments=26, bevel=0.008)
            for bz in (dz - 0.12, dz, dz + 0.12):
                b.cyl(0.018, 0.060, (dx + hole_r - 0.012, fy + 0.030, bz), "metal", axis="X", segments=8)
            b.cyl(wheel_r + 0.024, 0.028, (dx, fy - 0.024, dz), "dark", axis="Y", segments=26)
            b.cyl(wheel_r - 0.024, 0.024, (dx, fy - 0.036, dz), body_role, axis="Y", segments=24)
            b.torus(wheel_r, 0.042, (dx, fy - 0.044, dz), "light", seg_major=28, seg_minor=8)
            for k in range(8):
                ra = k * math.tau / 8
                b.cyl(0.014, 0.022, (dx + wheel_r * math.cos(ra), fy - 0.080, dz + wheel_r * math.sin(ra)), "dark", axis="Y", segments=8)
        with b.use_bone("wheel"):
            for k in range(3):
                a = k * math.tau / 3 + math.pi / 6
                sm = trs((dx, fy - 0.074, dz), (0, a, 0))
                b.box((0.18, 0.032, 0.064), (0.115, 0, 0), "dark", bevel=0.015, segments=2, M=sm)
                b.box((0.138, 0.020, 0.036), (0.115, -0.015, 0), spoke_role, bevel=0.008, segments=2, M=sm)
            b.cyl(0.098, 0.078, (dx, fy - 0.062, dz), "dark", axis="Y", segments=20, bevel=0.014)
            b.cyl(0.076, 0.054, (dx, fy - 0.086, dz), "light", axis="Y", segments=18, bevel=0.010)
            if b.mascot_style == "spray_can":
                b.spray_can((dx, fy - 0.128, dz), 0.042, role="primary", trim_role="metal", nozzle_role="light", spark_role="gold", face=True, detail="low")
        # Heavy machined hinge column, keypad, seamless side/front decals, gold-trimmed SAFE pill
        b.cyl(0.022, 0.34, (hx, fy - 0.036, dz), "light", segments=12)
        for z in (dz - 0.125, dz + 0.125):
            b.box((0.100, 0.060, 0.086), (hx + 0.015, fy - 0.018, z), "metal", bevel=0.015, segments=2)
            b.box((0.110, 0.064, 0.022), (hx + 0.015, fy - 0.018, z), "dark", bevel=0.005, segments=1)
        kx = w / 2 - 0.135
        b.box((0.155, 0.042, 0.28), (kx, fy - 0.012, dz + 0.01), "light", bevel=0.02)
        b.box((0.112, 0.012, 0.046), (kx, fy - 0.035, dz + 0.095), "screen", bevel=0.005)
        for r in range(3):
            for c in range(3):
                b.box((0.024, 0.012, 0.022), (kx - 0.032 + c * 0.032, fy - 0.035, dz + 0.03 - r * 0.036), "glowtrim", bevel=0.004, segments=1)
        b.box((0.085, 0.012, 0.038), (kx, fy - 0.034, dz - 0.088), "dark", bevel=0.006, segments=1)
        b.logo_decal(0.49, (0.0, fy - 0.008, h - 0.225))
        for side_sign, x, rz in ((-1, -w / 2 - 0.008, -math.pi / 2), (1, w / 2 + 0.008, math.pi / 2)):
            b.logo_decal(0.62, (x, 0, h * 0.44), rot=(math.pi / 2, 0, rz))
        # Clean gold-rimmed dark SAFE pill plaque with crisp centered lettering
        b.box((0.44, 0.020, 0.118), (dx + 0.03, fy - 0.005, 0.128), "gold", bevel=0.032, segments=2)
        b.box((0.41, 0.028, 0.096), (dx + 0.03, fy - 0.013, 0.128), "dark", bevel=0.028, segments=2)
        b.text(p.get("label", "SAFE"), 0.066, (dx + 0.03, fy - 0.031, 0.128), "light", depth=0.014, max_w=0.31, outline_role="dark")
        b.star((-w / 2 + 0.12, fy - 0.012, dz + 0.27), 0.042, "gold")
        b.star((w / 2 - 0.13, fy - 0.012, 0.19), 0.038, "glowtrim")
        with b.use_bone("crown"):
            b.crown((w / 2 - 0.20, -0.06, h + 0.060), 0.125, 0.125, role="gold", gem_role="primary", tilt=(0.06, -0.14, 0.22))
        b.set_anim(frames=181, fps=30, tracks={
            "door": {"kind": "safe_door", "open_deg": -104.0},
            "wheel": {"kind": "safe_wheel", "spin_deg": 360.0},
            "crown": {"kind": "crown_hover", "amp_z": 0.042, "rock_y": 7.0, "twist_z": 14.0},
        })
        return
    b.box((w, d, h - 0.05), (0, 0, 0.05 + (h - 0.05) / 2), body_role, bevel=0.075 if aaa else 0.06, collide=True)
    b.box((w + 0.045, d + 0.045, 0.085), (0, 0, h + 0.01), cap_role, bevel=0.04)
    if aaa:
        b.fat_skirt(w + 0.03, d + 0.03, h - 0.015, cap_role, thick=0.052, max_drop=0.26, drops_per_side=2, sides=("back", "left", "right"), corners=True, pearls=True)
        b.fat_curtain(-w / 2 + 0.01, -0.33, h - 0.01, -d / 2 - 0.012, cap_role, thick=0.048, max_drop=0.28, drops=2, pearls=True)
        b.fat_curtain(0.33, w / 2 - 0.01, h - 0.01, -d / 2 - 0.012, cap_role, thick=0.048, max_drop=0.28, drops=2, pearls=True)
        dz = 0.05 + (h - 0.05) * 0.40
        fy = -d / 2
        dx = -0.05
        wheel_r = 0.255
        b.cyl(wheel_r + 0.025, 0.035, (dx, fy - 0.012, dz), "dark", axis="Y", segments=28)
        b.cyl(wheel_r - 0.025, 0.028, (dx, fy - 0.026, dz), body_role, axis="Y", segments=24)
        b.torus(wheel_r, 0.048, (dx, fy - 0.035, dz), "light", seg_major=30, seg_minor=8)
        for k in range(8):
            ra = k * math.tau / 8
            b.cyl(0.016, 0.025, (dx + wheel_r * math.cos(ra), fy - 0.075, dz + wheel_r * math.sin(ra)), "dark", axis="Y", segments=8)
        for k in range(3):
            a = k * math.tau / 3 + math.pi / 6
            sm = trs((dx, fy - 0.068, dz), (0, a, 0))
            b.box((0.20, 0.036, 0.072), (0.125, 0, 0), "dark", bevel=0.018, segments=2, M=sm)
            b.box((0.155, 0.022, 0.042), (0.125, -0.016, 0), spoke_role, bevel=0.010, segments=2, M=sm)
        b.cyl(0.105, 0.085, (dx, fy - 0.056, dz), "dark", axis="Y", segments=20, bevel=0.016)
        b.cyl(0.082, 0.06, (dx, fy - 0.085, dz), "light", axis="Y", segments=18, bevel=0.012)
        if b.mascot_style == "spray_can":
            b.spray_can((dx, fy - 0.13, dz), 0.044, role="primary", trim_role="metal", nozzle_role="light", spark_role="gold", face=True, detail="low")
        hx = dx - wheel_r - 0.065
        b.cyl(0.024, 0.36, (hx, fy - 0.045, dz), "light", segments=10)
        for z in (dz - 0.14, dz + 0.14):
            b.box((0.11, 0.065, 0.095), (hx + 0.015, fy - 0.025, z), "metal", bevel=0.016, segments=2)
            b.box((0.12, 0.07, 0.026), (hx + 0.015, fy - 0.025, z), "dark", bevel=0.005, segments=1)
        kx = w / 2 - 0.14
        b.box((0.16, 0.042, 0.28), (kx, fy - 0.012, dz + 0.01), "light", bevel=0.02)
        b.box((0.115, 0.012, 0.046), (kx, fy - 0.035, dz + 0.095), "screen", bevel=0.005)
        for r in range(3):
            for c in range(3):
                b.box((0.024, 0.012, 0.022), (kx - 0.032 + c * 0.032, fy - 0.035, dz + 0.03 - r * 0.036), "glowtrim", bevel=0.004, segments=1)
        b.box((0.085, 0.012, 0.038), (kx, fy - 0.034, dz - 0.088), "dark", bevel=0.006, segments=1)
        b.logo_decal(0.56, (0.0, fy - 0.010, h - 0.22))
        for side_sign, x, rz in ((-1, -w / 2 - 0.008, -math.pi / 2), (1, w / 2 + 0.008, math.pi / 2)):
            b.logo_decal(0.64, (x, 0, h * 0.46), rot=(math.pi / 2, 0, rz))
        b.box((0.50, 0.032, 0.125), (dx + 0.04, fy - 0.016, 0.115), "dark", bevel=0.038)
        for sx in (-1, 1):
            b.sphere(0.048, (dx + 0.04 + sx * 0.25, fy - 0.022, 0.115), cap_role, scale=(1.1, 0.75, 1.2), u=10, v=6)
            b.sphere(0.028, (dx + 0.04 + sx * 0.29, fy - 0.024, 0.155), cap_role, u=8, v=5)
        b.text(p.get("label", "SAFE"), 0.084, (dx + 0.04, fy - 0.036, 0.115), "light", depth=0.018, max_w=0.38, outline_role="dark")
        b.star((-w / 2 + 0.12, fy - 0.016, dz + 0.25), 0.048, "light")
        b.star((w / 2 - 0.13, fy - 0.016, 0.20), 0.042, "gold")
        b.crown((w / 2 - 0.20, -0.06, h + 0.05), 0.125, 0.125, role="gold", gem_role="primary", tilt=(0.06, -0.14, 0.22))
        return
    b.skirt(w + 0.035, d + 0.035, h - 0.015, cap_role, base=0.032, max_drop=0.22, drops_per_side=2, out=0.013)
    dz = 0.05 + (h - 0.05) * 0.5
    fy = -d / 2
    dx = -0.05
    wheel_r = 0.26
    b.cyl(wheel_r, 0.03, (dx, fy - 0.012, dz), "dark", axis="Y", segments=32)
    b.torus(wheel_r + 0.01, 0.042, (dx, fy - 0.03, dz), "light", seg_major=32, seg_minor=8)
    b.cyl(0.088, 0.08, (dx, fy - 0.05, dz), "light", axis="Y", segments=20, bevel=0.01)
    b.cyl(0.056, 0.05, (dx, fy - 0.09, dz), "primary", axis="Y", segments=16, bevel=0.008)
    for k in range(3):
        a = k * math.pi / 3
        b.box((0.44, 0.035, 0.05), role="light", bevel=0.015, matrix=trs((dx, fy - 0.06, dz), (0, a, 0)))
        for s in (-1, 1):
            b.sphere(0.035, (dx + s * 0.22 * math.cos(a), fy - 0.06, dz - s * 0.22 * math.sin(a)), spoke_role, u=10, v=6)
    for z in (dz - 0.16, dz + 0.16):
        b.cyl(0.032, 0.12, (dx - wheel_r - 0.04, fy - 0.022, z), "dark", segments=10)
    kx = w / 2 - 0.13
    b.box((0.14, 0.032, 0.24), (kx, fy - 0.01, dz + 0.01), "light", bevel=0.015)
    b.box((0.1, 0.008, 0.042), (kx, fy - 0.029, dz + 0.09), "screen", bevel=0.004)
    for r in range(3):
        for c in range(3):
            b.box((0.025, 0.012, 0.022), (kx - 0.03 + c * 0.03, fy - 0.029, dz + 0.02 - r * 0.035), "dark", bevel=0.004, segments=2)
    for x, rz in ((-w / 2 - 0.012, -math.pi / 2), (w / 2 + 0.012, math.pi / 2)):
        b.text(b.brand, 0.13, (x, 0, h * 0.5), "accent", depth=0.022, max_w=d * 0.7, rot_z=rz)
    b.text(p.get("label", "SAFE"), 0.07, (dx, fy - 0.02, 0.11), "light", depth=0.018, max_w=0.3)
    b.star((-w / 2 + 0.11, fy - 0.014, dz + 0.24), 0.045, "light")
    b.star((w / 2 - 0.12, fy - 0.014, 0.19), 0.038, "light")
    b.crown((w / 2 - 0.18, -0.05, h + 0.035), 0.105, 0.105, tilt=(0.06, -0.12, 0.22))


def build_crate(b, p):
    use_logo = p.get("use_logo", False) and bool(b.logo)
    aaa = use_logo or p.get("detail_tier") == "aaa"
    w, d, h = p.get("w", 1.32), p.get("d", 1.08), p.get("h", 1.02)
    body_role = p.get("body_role", "primary")
    bumper_role = p.get("bumper_role", "accent")
    if b.is_stylized:
        # V5 Vinyl Toy-Brand Armored Cargo Stash Crate with Lush Metaball Top Melting Slime & Bottom D-Rings (matches sec_22!)
        for x in (-w / 2 + 0.26, w / 2 - 0.26):
            for y in (-d / 2 + 0.12, d / 2 - 0.12):
                b.box((0.24, 0.14, 0.06), (x, y, 0.03), "dark", bevel=0.02)
            for sy in (-1, 1):
                # Heavy white metal bottom tie-down D-ring bars (sec_22!)
                b.box((0.22, 0.042, 0.075), (x, sy * (d / 2 + 0.012), 0.070), "light", bevel=0.015, segments=2)
                b.box((0.12, 0.022, 0.028), (x, sy * (d / 2 + 0.028), 0.070), "dark", bevel=0.005, segments=1)
        body_h = h - 0.06
        zc = 0.06 + body_h / 2
        b.box((w - 0.06, d - 0.06, body_h - 0.04), (0, 0, zc), body_role, bevel=0.026, collide=True)
        t = 0.12
        for sx in (-1, 1):
            for sy in (-1, 1):
                b.box((t, t, body_h), (sx * (w / 2 - t / 2), sy * (d / 2 - t / 2), zc), "dark", bevel=0.024)
                b.box((0.030, 0.018, body_h * 0.48), (sx * (w / 2 - t * 0.5), sy * (d / 2 + 0.002), zc), "glowtrim", bevel=0.005)
                b.box((0.018, 0.030, body_h * 0.48), (sx * (w / 2 + 0.002), sy * (d / 2 - t * 0.5), zc), "glowtrim", bevel=0.005)
        for z in (0.06 + t / 2, h - t / 2):
            for sy in (-1, 1):
                b.box((w, t, t), (0, sy * (d / 2 - t / 2), z), "dark", bevel=0.022)
            for sx in (-1, 1):
                b.box((t, d, t), (sx * (w / 2 - t / 2), 0, z), "dark", bevel=0.022)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for z in (0.06 + 0.095, h - 0.085):
                    b.box((0.23, 0.23, 0.185), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), z), bumper_role, bevel=0.048)
                    b.cyl(0.017, 0.022, (sx * (w / 2 - 0.06), sy * (d / 2 + 0.034), z), "dark", axis="Y", segments=8)
                    b.cyl(0.017, 0.022, (sx * (w / 2 + 0.034), sy * (d / 2 - 0.06), z), "dark", axis="X", segments=8)
        b.box((w - 0.22, d - 0.22, 0.032), (0, 0, h - 0.01), body_role, bevel=0.012)
        # Lush Continuous Organic Metaball Melting Gold Slime Pooling Across Top Lid & Dripping Down Front/Sides (sec_22!)
        els = []
        for ix in range(-8, 9):
            x = ix * (w * 0.055)
            els.append(("BALL", (x, 0.0, h + 0.014), 0.105))
        for iy in range(-6, 7):
            y = iy * (d * 0.072)
            els.append(("BALL", (0.0, y, h + 0.014), 0.105))
        els.append(("CUBE", (0.0, 0.0, h + 0.016), 0.090, (0.18, 0.16, 0.014)))
        # Organic smooth drips spilling gently over front-center (between latches!) & sides
        for dx_d, dy_d, drp, drad in (
            (-0.14, -d / 2 - 0.010, 0.16, 0.044),
            (0.05, -d / 2 - 0.012, 0.22, 0.050),
            (0.19, -d / 2 - 0.010, 0.12, 0.040),
            (w / 2 + 0.008, -0.04, 0.19, 0.048),
            (-w / 2 - 0.008, 0.06, 0.18, 0.046),
            (0.0, d / 2 + 0.008, 0.19, 0.048),
        ):
            b._add_drip_chain(els, dx_d, dy_d, h + 0.006, drp, drad)
        b.metaball_slime(els, role=bumper_role, resolution=0.028, target_tris=1200, smooth_iters=4)
        fy = -d / 2 + 0.03
        b.banner_decal(0.86, (0, fy - 0.008, zc - 0.04))
        b.banner_decal(0.86, (0, -fy + 0.008, zc - 0.04), rot=(math.pi / 2, 0, math.pi))
        for x in (-0.36, 0.36):
            b.box((0.125, 0.064, 0.165), (x, -d / 2 - 0.004, h - 0.13), "light", bevel=0.018)
            b.box((0.068, 0.024, 0.056), (x, -d / 2 - 0.035, h - 0.15), "dark", bevel=0.006, segments=1)
        b.star((w / 2 - 0.23, fy - 0.016, zc - 0.28), 0.046, "light")
        b.star((-w / 2 + 0.23, fy - 0.016, zc + 0.22), 0.042, "light")
        for side in (-1, 1):
            sx = side * (w / 2 - 0.028)
            b.ribbed_handle((sx, 0, zc + 0.14), role="light", side_sign=side, scale=1.05)
            b.shield_plaque((sx + side * 0.006, 0, zc - 0.20), 0.25, 0.27, role="dark", border_role="light", accent_role="accent", direction=(side, 0, 0))
            b.mascot((sx + side * 0.048, 0, zc - 0.20), 0.084, "light", "light", direction=(side, 0, 0), drips=False)
        return
    for x in (-w / 2 + 0.22, w / 2 - 0.22):
        for y in (-d / 2 + 0.12, d / 2 - 0.12):
            b.box((0.24, 0.14, 0.06), (x, y, 0.03), "dark", bevel=0.02)
            if aaa and y < 0:
                b.box((0.18, 0.035, 0.065), (x, -d / 2 - 0.012, 0.065), "light", bevel=0.012, segments=2)
                b.box((0.10, 0.018, 0.024), (x, -d / 2 - 0.028, 0.065), "dark", bevel=0.004, segments=1)
    body_h = h - 0.06
    zc = 0.06 + body_h / 2
    b.box((w - 0.06, d - 0.06, body_h - 0.04), (0, 0, zc), body_role, bevel=0.022, collide=True)
    t = 0.12
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((t, t, body_h), (sx * (w / 2 - t / 2), sy * (d / 2 - t / 2), zc), "dark", bevel=0.024)
            b.box((0.028, 0.018, body_h * 0.48), (sx * (w / 2 - t * 0.5), sy * (d / 2 + 0.002), zc), "glowtrim" if aaa else "glow", bevel=0.005)
            b.box((0.018, 0.028, body_h * 0.48), (sx * (w / 2 + 0.002), sy * (d / 2 - t * 0.5), zc), "glowtrim" if aaa else "glow", bevel=0.005)
    for z in (0.06 + t / 2, h - t / 2):
        for sy in (-1, 1):
            b.box((w, t, t), (0, sy * (d / 2 - t / 2), z), "dark", bevel=0.022)
        for sx in (-1, 1):
            b.box((t, d, t), (sx * (w / 2 - t / 2), 0, z), "dark", bevel=0.022)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.06 + 0.095, h - 0.085):
                b.box((0.22, 0.22, 0.18), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), z), bumper_role, bevel=0.048)
                if aaa:
                    b.cyl(0.016, 0.02, (sx * (w / 2 - 0.06), sy * (d / 2 + 0.032), z), "dark", axis="Y", segments=8)
                    b.cyl(0.016, 0.02, (sx * (w / 2 + 0.032), sy * (d / 2 - 0.06), z), "dark", axis="X", segments=8)
    b.box((w - 0.22, d - 0.22, 0.032), (0, 0, h - 0.01), body_role, bevel=0.012)
    if aaa:
        # Top straps terminate cleanly into raised circular bolted medallion hub (ZERO coplanar z-fighting!)
        for sx in (-1, 1):
            b.box((w * 0.34, 0.14, 0.038), (sx * (w * 0.27), 0, h + 0.011), bumper_role, bevel=0.015)
        for sy in (-1, 1):
            b.box((0.14, d * 0.31, 0.038), (0, sy * (d * 0.28), h + 0.011), bumper_role, bevel=0.015)
        b.cyl(0.20, 0.050, (0, 0, h + 0.018), "dark", segments=20, bevel=0.012)
        b.cyl(0.155, 0.046, (0, 0, h + 0.028), bumper_role, segments=20, bevel=0.010)
        b.cyl(0.115, 0.022, (0, 0, h + 0.045), body_role, segments=18, bevel=0.005)
        b.star((0, 0, h + 0.060), 0.080, "gold", direction=(0, 0, 1))
    else:
        b.box((w * 0.9, 0.15, 0.04), (0, 0, h + 0.012), bumper_role, bevel=0.018)
        b.box((0.15, d * 0.9, 0.04), (0, 0, h + 0.012), bumper_role, bevel=0.018)
    fy = -d / 2 + 0.03
    if aaa:
        # Clean tactical status header between front latches (removed weird floating white bow-tie blob!)
        b.box((0.46, 0.028, 0.068), (0, -d / 2 - 0.006, h - 0.105), "dark", bevel=0.014, segments=2)
        b.box((0.30, 0.012, 0.020), (0, -d / 2 - 0.020, h - 0.105), "glowtrim", bevel=0.004, segments=1)
        b.logo_decal(0.76, (0, fy - 0.008, zc - 0.04))
        b.logo_decal(0.76, (0, -fy + 0.008, zc - 0.04), rot=(math.pi / 2, 0, math.pi))
        for x in (-0.34, 0.34):
            b.box((0.12, 0.06, 0.16), (x, -d / 2 - 0.002, h - 0.13), "light", bevel=0.018)
            b.box((0.065, 0.024, 0.055), (x, -d / 2 - 0.032, h - 0.15), "dark", bevel=0.006, segments=1)
            b.box((0.052, 0.014, 0.016), (x, -d / 2 - 0.032, h - 0.085), "glow", bevel=0.003, segments=1)
        b.star((w / 2 - 0.23, fy - 0.015, zc - 0.28), 0.045, "gold")
        b.star((-w / 2 + 0.23, fy - 0.015, zc + 0.22), 0.040, "glowtrim")
        for side in (-1, 1):
            sx = side * (w / 2 - 0.028)
            b.ribbed_handle((sx, 0, zc + 0.14), role="light", side_sign=side, scale=1.05)
            b.shield_plaque((sx + side * 0.006, 0, zc - 0.20), 0.25, 0.27, role="dark", border_role="light", accent_role="gold", direction=(side, 0, 0))
            b.mascot((sx + side * 0.048, 0, zc - 0.20), 0.084, "primary" if body_role != "primary" else "light", "light", direction=(side, 0, 0), drips=False)
    else:
        b.curtain(-0.2, 0.25, h - 0.03, -d / 2 + 0.01, bumper_role, max_drop=0.2, drops=2)
        hx = -w / 2 + 0.34
        b.box((0.26, 0.04, 0.05), (hx, fy - 0.03, zc + 0.12), "light", bevel=0.015)
        b.box((0.26, 0.04, 0.05), (hx, fy - 0.03, zc - 0.06), "light", bevel=0.015)
        for x in (hx - 0.11, hx + 0.11):
            b.box((0.05, 0.04, 0.23), (x, fy - 0.03, zc + 0.03), "light", bevel=0.015)
        b.box((0.16, 0.03, 0.14), (hx, fy - 0.015, zc + 0.03), "dark", bevel=0.01)
        b.mascot((hx, fy - 0.01, zc - 0.25), 0.11, "primary", "light", drips=False)
        b.text(b.brand, 0.17, (0.22, fy - 0.03, zc - 0.05), "accent", depth=0.025, max_w=0.62)
        if b.mascot_style != "spray_can":
            b.crown((hx, fy - 0.04, zc - 0.165), 0.055, 0.055, tilt=(0.25, 0, 0.2))
        for x in (-w / 2 + 0.26, w / 2 - 0.26):
            b.box((0.1, 0.05, 0.08), (x, -d / 2 + 0.01, h - 0.08), "light", bevel=0.015)
        b.star((w / 2 - 0.22, fy - 0.02, zc - 0.3), 0.04, "light")
        for side in (-1, 1):
            sx = side * (w / 2 - 0.03)
            b.box((0.04, 0.26, 0.05), (sx + side * 0.03, 0, zc + 0.1), "light", bevel=0.015)
            b.box((0.04, 0.26, 0.05), (sx + side * 0.03, 0, zc - 0.05), "light", bevel=0.015)
            for y in (-0.11, 0.11):
                b.box((0.04, 0.05, 0.2), (sx + side * 0.03, y, zc + 0.025), "light", bevel=0.015)


def build_chest(b, p):
    use_logo = p.get("use_logo", False) and bool(b.logo)
    aaa = use_logo or p.get("detail_tier") == "aaa"
    w, d, h = p.get("w", 0.80), p.get("d", 0.56), p.get("h", 0.44)
    body_role = p.get("body_role", "primary")
    trim_role = p.get("trim_role", "accent")
    if b.is_stylized:
        # V5 Vinyl Toy-Brand Plump Loot Chest with Lush Bottom-Pooling Metaball Gold Slime & Clean Dark Rim (matches sec_28!)
        for sx in (-1, 1):
            for sy in (-1, 1):
                b.cyl(0.068, 0.065, (sx * (w * 0.40), sy * (d * 0.37), 0.032), trim_role, segments=14, bevel=0.018)
        b.box((w, d, h - 0.055), (0, 0, 0.055 + (h - 0.055) / 2), body_role, bevel=0.062, collide=True)
        # Clean dark beveled upper lip rim (ZERO icing on top -> zero clipping with clasps!)
        b.box((w + 0.022, d + 0.022, 0.048), (0, 0, h - 0.018), "dark", bevel=0.018)
        b.box((w - 0.07, d - 0.07, 0.014), (0, 0, h + 0.004), "dark", bevel=0.004)
        # Lush One-Piece Organic Melting Gold Slime Wrapping Entire BOTTOM Skirt & Corner Feet (EXACT sec_28 silhouette!)
        b.slime_skirt_mb(w + 0.024, d + 0.024, 0.072, role=trim_role, wave_amp=0.085, tube_r=0.056, corner_blobs=True, res=0.022, target_tris=1850)
        # Chunky Chrome-White Side Handles + Twin Front Clasps + Bold EXTREME Logo + Comic White Stars
        hw_role = p.get("hardware_role", "light")
        for side in (-1, 1):
            b.ribbed_handle((side * (w / 2 + 0.006), 0, h * 0.58), role=hw_role, side_sign=side, scale=0.72)
        for sx in (-0.24, 0.24):
            b.box((0.088, 0.036, 0.112), (sx, -d / 2 - 0.014, h - 0.085), "dark", bevel=0.014, segments=2)
            b.box((0.062, 0.032, 0.082), (sx, -d / 2 - 0.022, h - 0.085), hw_role, bevel=0.010, segments=2)
            b.box((0.026, 0.016, 0.028), (sx, -d / 2 - 0.038, h - 0.088), "dark", bevel=0.004, segments=1)
        b.logo_decal(0.42, (0.0, -d / 2 - 0.010, h * 0.52))
        for sx in (-0.32, 0.32):
            b.star((sx, -d / 2 - 0.014, h * 0.44), 0.034, "light")
        angle = math.radians(p.get("open", 66))
        if b.animate:
            b.define_bone("lid", (0.0, d / 2, h))
            b.define_bone("coins", (0.0, 0.0, h + 0.24))
        lid = Matrix.Translation((0, d / 2, h)) @ Matrix.Rotation(-angle, 4, "X") @ Matrix.Translation((0, -d / 2, 0.04))
        with b.use_bone("lid"):
            b.box((w + 0.030, d + 0.030, 0.082), role=body_role, bevel=0.038, M=lid)
            b.box((w + 0.044, d + 0.044, 0.032), (0, 0, -0.028), trim_role, bevel=0.014, M=lid)
            b.box((w - 0.05, d - 0.05, 0.012), (0, 0, -0.044), "dark", bevel=0.004, M=lid)
            b.box((w - 0.12, d - 0.12, 0.014), (0, 0, -0.048), body_role, bevel=0.006, M=lid)
            for sy in (-1, 1):
                b.box((w - 0.09, 0.020, 0.016), (0, sy * (d * 0.5 - 0.055), -0.050), "gold", bevel=0.005, segments=1, M=lid)
            for sx in (-1, 1):
                b.box((0.020, d - 0.09, 0.016), (sx * (w * 0.5 - 0.055), 0, -0.050), "gold", bevel=0.005, segments=1, M=lid)
            b.star((0, 0, -0.058), 0.068, "gold", direction=(0, 0, -1), M=lid)
            b.logo_decal(0.44, (0, 0, 0.046), rot=(0, 0, math.pi), M=lid)
        b.cash_gold_treasure(w, d, h, coins=p.get("coins", 28), float_coins=p.get("float_coins", True), float_bone="coins")
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "lid": {"kind": "chest_lid", "close_deg": 24.0, "wide_deg": -12.0},
                "coins": {"kind": "chest_coins", "amp_z": 0.12, "spin_deg": 360.0},
            })
        return
    if aaa:
        for sx in (-1, 1):
            for sy in (-1, 1):
                b.cyl(0.06, 0.06, (sx * (w * 0.40), sy * (d * 0.38), 0.03), "dark", segments=12, bevel=0.012)
        b.box((w + 0.04, d + 0.04, 0.09), (0, 0, 0.075), trim_role, bevel=0.04)
        b.box((w, d, h - 0.06), (0, 0, 0.06 + (h - 0.06) / 2), body_role, bevel=0.055, collide=True)
        # Inset dark rim so glossy white drip skirt wraps cleanly OUTSIDE with ZERO corner poke-through!
        b.box((w + 0.004, d + 0.004, 0.044), (0, 0, h - 0.024), "dark", bevel=0.016)
        b.box((w - 0.08, d - 0.08, 0.014), (0, 0, h + 0.004), "dark", bevel=0.004)
        b.fat_skirt(w + 0.034, d + 0.034, h - 0.008, trim_role, thick=0.026, max_drop=0.068, drops_per_side=2, corners=False, pearls=False)
        for side in (-1, 1):
            b.ribbed_handle((side * (w / 2 + 0.008), 0, h * 0.56), role="light", side_sign=side, scale=0.68)
        # Ornate gold + white keyhole lock clasp sitting proud & completely clear of the white rim!
        b.box((0.128, 0.032, 0.114), (0, -d / 2 - 0.032, h - 0.062), "gold", bevel=0.016, segments=2)
        b.box((0.098, 0.034, 0.088), (0, -d / 2 - 0.040, h - 0.062), "light", bevel=0.012, segments=2)
        b.cyl(0.016, 0.014, (0, -d / 2 - 0.058, h - 0.052), "dark", axis="Y", segments=10)
        b.box((0.016, 0.014, 0.028), (0, -d / 2 - 0.058, h - 0.072), "dark", bevel=0.003, segments=1)
        b.logo_decal(0.40, (0.0, -d / 2 - 0.010, h * 0.44))
        for sx in (-0.29, 0.29):
            b.star((sx, -d / 2 - 0.014, h * 0.52), 0.034, "gold")
        angle = math.radians(p.get("open", 62))
        if b.animate:
            b.define_bone("lid", (0.0, d / 2, h))
            b.define_bone("coins", (0.0, 0.0, h + 0.25))
        lid = Matrix.Translation((0, d / 2, h)) @ Matrix.Rotation(-angle, 4, "X") @ Matrix.Translation((0, -d / 2, 0.04))
        with b.use_bone("lid"):
            b.box((w + 0.03, d + 0.03, 0.085), role=body_role, bevel=0.038, M=lid)
            b.box((w + 0.046, d + 0.046, 0.032), (0, 0, -0.028), trim_role, bevel=0.014, M=lid)
            # Plush decorated inside of open lid: dark recessed liner + crimson padded cushion + gold trim frame + gold star!
            b.box((w - 0.05, d - 0.05, 0.012), (0, 0, -0.044), "dark", bevel=0.004, M=lid)
            b.box((w - 0.13, d - 0.13, 0.014), (0, 0, -0.048), body_role, bevel=0.006, M=lid)
            for sy in (-1, 1):
                b.box((w - 0.09, 0.022, 0.016), (0, sy * (d * 0.5 - 0.055), -0.050), "gold", bevel=0.005, segments=1, M=lid)
            for sx in (-1, 1):
                b.box((0.022, d - 0.09, 0.016), (sx * (w * 0.5 - 0.055), 0, -0.050), "gold", bevel=0.005, segments=1, M=lid)
            b.star((0, 0, -0.058), 0.068, "gold", direction=(0, 0, -1), M=lid)
            b.logo_decal(0.44, (0, 0, 0.048), rot=(0, 0, math.pi), M=lid)
        b.cash_gold_treasure(w, d, h, coins=p.get("coins", 30), float_coins=p.get("float_coins", True), float_bone="coins")
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "lid": {"kind": "chest_lid", "close_deg": 24.0, "wide_deg": -12.0},
                "coins": {"kind": "chest_coins", "amp_z": 0.12, "spin_deg": 360.0},
            })
        return
    b.box((w + 0.05, d + 0.05, 0.07), (0, 0, 0.035), trim_role, bevel=0.03)
    b.box((w, d, h - 0.05), (0, 0, 0.05 + (h - 0.05) / 2), body_role, bevel=0.04, collide=True)
    b.box((w - 0.06, d - 0.06, 0.012), (0, 0, h + 0.004), "dark", bevel=0.004)
    b.skirt(w + 0.006, d + 0.006, h - 0.005, trim_role, base=0.018, max_drop=0.12, drops_per_side=2, out=0.01, thick=0.016)
    for side in (-1, 1):
        sx = side * (w / 2 + 0.02)
        b.box((0.03, 0.2, 0.035), (sx, 0, h * 0.62), "light", bevel=0.01)
        for y in (-0.085, 0.085):
            b.box((0.03, 0.03, 0.09), (sx, y, h * 0.55), "light", bevel=0.01)
    b.box((0.1, 0.03, 0.08), (0, -d / 2 - 0.012, h - 0.06), "light", bevel=0.012)
    b.box((0.03, 0.01, 0.03), (0, -d / 2 - 0.03, h - 0.07), "dark", bevel=0.004)
    b.text(b.brand, 0.07, (0.12, -d / 2 - 0.012, h * 0.42), "accent", depth=0.016, max_w=w * 0.45)
    b.mascot((-0.2, -d / 2 - 0.005, h * 0.45), 0.065, "primary", "light", drips=False)
    angle = math.radians(p.get("open", 46))
    lid = Matrix.Translation((0, d / 2, h)) @ Matrix.Rotation(-angle, 4, "X") @ Matrix.Translation((0, -d / 2, 0.035))
    b.box((w + 0.02, d + 0.02, 0.07), role=body_role, bevel=0.03, M=lid)
    b.box((w - 0.04, d - 0.04, 0.01), (0, 0, -0.037), trim_role, bevel=0.004, M=lid)
    b.box((w + 0.04, 0.04, 0.03), (0, -d / 2, 0.0), trim_role, bevel=0.012, M=lid)
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
    use_logo = p.get("use_logo", False) and bool(b.logo)
    aaa = use_logo or p.get("detail_tier") == "aaa"
    w, d, top = p.get("w", 1.98 if b.is_stylized else 2.04), p.get("d", 0.84 if b.is_stylized else 0.86), p.get("top", 0.88 if b.is_stylized else 0.96)
    drawer_a = p.get("drawer_a", "primary")
    drawer_b = p.get("drawer_b", "accent")
    lip_role = p.get("lip_role", "primary")
    if b.is_stylized:
        # V5 Chunky Squat Vinyl-Toy Crafting Workbench (matches sec_04 & sec_42 proportions, melting slime & center mascot!)
        for sx in (-1, 1):
            for sy in (-1, 1):
                b.box((0.125, 0.125, top - 0.06), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), (top - 0.06) / 2 + 0.055), "light", bevel=0.028)
                b.box((0.20, 0.20, 0.075), (sx * (w / 2 - 0.08), sy * (d / 2 - 0.08), 0.0375), "dark", bevel=0.026)
            b.bolt_cap((sx * (w / 2 - 0.08), -d / 2 - 0.010, 0.115), 0.058, "accent", "dark")
        # Chunky Cream-White Tabletop + Lush Continuous Melting Gold Slime Lip Across Entire Front & Corners (sec_42!)
        b.box((w, d, 0.085), (0, 0, top - 0.042), "light", bevel=0.030, collide=True)
        lip_els = []
        nx = 24
        for i in range(nx + 1):
            t = i / nx
            x = -w * 0.50 + (w * 1.00) * t
            lip_els.append(("BALL", (x, -d / 2 - 0.012, top - 0.034), 0.082))
        for sx in (-1, 1):
            for iy in range(6):
                y = -d / 2 + 0.04 + iy * 0.065
                lip_els.append(("BALL", (sx * (w * 0.50 + 0.004), y, top - 0.034), 0.078))
        # Organic drops strictly ABOVE drawers (top of upper drawer = 0.675, lowest drip stops at 0.72!)
        for dx_l, drp, drad in (
            (-0.88, 0.095, 0.038), (-0.54, 0.075, 0.034), (-0.28, 0.105, 0.040),
            (0.02, 0.085, 0.036), (0.30, 0.105, 0.040), (0.62, 0.075, 0.034), (0.88, 0.095, 0.038),
        ):
            b._add_drip_chain(lip_els, dx_l, -d / 2 - 0.018, top - 0.042, drp, drad)
        b.metaball_slime(lip_els, role=lip_role, resolution=0.028, target_tris=1150, smooth_iters=4)
        # Gridded Dark Cutting Mat + Organic Paint Splatter + 3D Craft Knife + Blueprint + Yellow Tape Roll
        b.box((w * 0.50, d * 0.54, 0.014), (0, -0.05, top + 0.007), "dark", bevel=0.005)
        b.box((w * 0.50 + 0.024, 0.014, 0.018), (0, -0.05 - d * 0.27, top + 0.009), "glow", bevel=0.004)
        for gx in (-0.40, -0.20, 0.0, 0.20, 0.40):
            b.box((0.008, d * 0.48, 0.005), (gx, -0.05, top + 0.015), "metal", bevel=0.0, segments=1)
        for gy in (-0.20, -0.05, 0.10):
            b.box((w * 0.46, 0.008, 0.005), (0, gy, top + 0.015), "metal", bevel=0.0, segments=1)
        bp_m = trs((0.18, -0.02, top + 0.017), (0, 0, -0.14))
        b.box((0.24, 0.18, 0.006), (0, 0, 0), "light", bevel=0.002, segments=1, M=bp_m)
        b.box((0.16, 0.028, 0.004), (0, 0.045, 0.004), "primary", bevel=0.001, segments=1, M=bp_m)
        kn_m = trs((-0.14, -0.09, top + 0.023), (0, 0, 0.42))
        b.box((0.16, 0.030, 0.018), (0, 0, 0), "primary", bevel=0.005, segments=1, M=kn_m)
        b.box((0.070, 0.018, 0.006), (0.105, 0, 0), "metal", bevel=0.002, segments=1, M=kn_m)
        b.cyl(0.050, 0.042, (-0.33, 0.04, top + 0.035), "gold", segments=14, bevel=0.006)
        b.cyl(0.030, 0.046, (-0.33, 0.04, top + 0.035), "dark", segments=12)
        # Side Outer Panels with Giant 3D Gold Crown (sec_04!)
        crown_2d = [(-0.14, -0.09), (0.14, -0.09), (0.16, 0.08), (0.07, 0.01), (0.0, 0.11), (-0.07, 0.01), (-0.16, 0.08)]
        for side in (-1, 1):
            sx = side * (w / 2 - 0.04)
            b.box((0.04, d - 0.22, 0.56), (sx, 0, 0.41), "dark", bevel=0.015)
            b.box((0.048, d - 0.30, 0.44), (sx + side * 0.012, 0, 0.42), "primary", bevel=0.020)
            b.shape(crown_2d, -0.016, 0.016, "gold", bevel=0.004, matrix=trs((sx + side * 0.044, 0, 0.43), (0, 0, side * math.pi * 0.5)))
        # Asymmetric Playful Lower Drawers (sec_42: Blood-Crimson & Blazing-Red drawers + crisp white handles + gold crowns!)
        for sx in (-1, 1):
            cx = sx * (w / 2 - 0.37)
            b.box((0.50, d - 0.14, 0.62), (cx, 0, 0.09 + 0.31), "dark", bevel=0.022, collide=True)
            for k in range(2):
                z = 0.24 + k * 0.29
                role = drawer_a if (sx < 0 or k == 1) else drawer_b
                b.box((0.44, 0.036, 0.24), (cx, -d / 2 + 0.056, z), role, bevel=0.022)
                b.box((0.18, 0.036, 0.034), (cx, -d / 2 + 0.028, z + 0.050), "light", bevel=0.012)
                if (sx < 0 and k == 0) or (sx > 0 and k == 1):
                    b.shape(crown_2d, -0.010, 0.010, "gold", bevel=0.003, matrix=trs((cx, -d / 2 + 0.034, z - 0.042), (0, 0, 0), (0.36, 1.0, 0.36)))
        # Center Hero Bay: Dark Comic Shield + HUGE Chubby Blazing-Red Vinyl Spray Can Mascot & Gold Crown (sec_42!)
        b.box((w - 1.22, d - 0.20, 0.035), (0, 0.04, 0.13), "light", bevel=0.012)
        b.box((w - 1.24, 0.035, 0.60), (0, -d / 2 + 0.095, 0.41), "dark", bevel=0.012)
        b.shield_plaque((0, -d / 2 + 0.072, 0.40), 0.48, 0.48, role="primary", border_role="light", accent_role="accent")
        if b.animate:
            b.define_bone("mascot", (0.0, -d / 2 - 0.028, 0.38))
        with b.use_bone("mascot"):
            b.spray_can((0, -d / 2 - 0.028, 0.38), 0.120, role="accent", trim_role="metal", nozzle_role="light", spark_role="gold", face=True, with_crown=True, tilt=(0.05, -0.10, 0.0), detail="low")
        # Compact Chunky Pegboard + Dark Armored Corner Posts with Big Blazing-Red X-Bolt Caps (sec_42!)
        by = d / 2 - 0.07
        bh = 0.68
        bz = top + bh / 2
        b.box((w - 0.16, 0.055, bh), (0, by, bz), "wood", bevel=0.015, collide=True)
        b.box((w - 0.08, 0.075, 0.055), (0, by, top + bh), "dark", bevel=0.018)
        for r in range(4):
            for c in range(8):
                b.cyl(0.009, 0.01, (-w / 2 + 0.24 + c * ((w - 0.48) / 7.0), by - 0.030, top + 0.13 + r * (0.38 / 3.0)), "dark", axis="Y", segments=5)
        for sx in (-1, 1):
            x = sx * (w / 2 - 0.055)
            b.box((0.105, 0.105, bh + 0.12), (x, by, top + (bh + 0.12) / 2), "dark", bevel=0.026)
            b.bolt_cap((x, by - 0.056, top + bh + 0.06), 0.068, "accent", "dark")
        # Left 2-Tier Spray Can Shelf + Tabletop Accessories + Pinned Notes + 3D Pegboard Tools
        b.box((0.50, 0.18, 0.026), (-0.60, by - 0.10, top + 0.48), "light", bevel=0.008)
        b.box((0.50, 0.18, 0.026), (-0.60, by - 0.10, top + 0.24), "light", bevel=0.008)
        for sx in (-0.84, -0.36):
            b.box((0.028, 0.18, 0.38), (sx, by - 0.10, top + 0.38), "dark", bevel=0.008)
        for k, role in enumerate(("accent", "light", "primary", "dark")):
            b.spray_can((-0.78 + k * 0.12, by - 0.10, top + 0.545), 0.034, role=role, face=False, detail="low")
        for k, role in enumerate(("accent", "light")):
            b.spray_can((-0.72 + k * 0.18, by - 0.10, top + 0.305), 0.034, role=role, face=False, detail="low")
        b.box((0.17, 0.13, 0.11), (-0.74, -0.14, top + 0.055), "primary", bevel=0.020)
        b.cyl(0.044, 0.14, (-0.74, -0.14, top + 0.075), "dark", axis="X", segments=10)
        b.cyl(0.050, 0.11, (-0.56, -0.02, top + 0.055), "dark", segments=12, bevel=0.008)
        for k, (ax, role) in enumerate(((-0.22, "accent"), (0.0, "light"), (0.20, "primary"))):
            b.cyl(0.011, 0.15, (-0.56 + k * 0.018 - 0.018, -0.02, top + 0.13), role, segments=6, rot=(0.15, ax, 0))
        b.box((0.25, 0.17, 0.12), (0.66, 0.02, top + 0.060), "dark", bevel=0.020)
        b.box((0.27, 0.18, 0.024), (0.66, 0.02, top + 0.118), "accent", bevel=0.008)
        b.spray_can((0.83, -0.15, top + 0.080), 0.048, role="accent", face=True, detail="low")
        b.spray_can((0.70, -0.21, top + 0.065), 0.040, role="light", face=False, detail="low")
        for nx, nz, nr in ((-0.12, top + 0.36, 0.12), (0.14, top + 0.35, -0.10)):
            nm = trs((nx, by - 0.036, nz), (0, nr, 0))
            b.box((0.17, 0.008, 0.20), (0, 0, 0), "light", bevel=0.003, segments=1, M=nm)
            b.box((0.095, 0.010, 0.075), (0, -0.005, 0.02), "accent", bevel=0.003, segments=1, M=nm)
            b.cyl(0.014, 0.014, (0, -0.008, 0.085), "dark", axis="Y", segments=8, M=nm)
        ty = by - 0.046
        b.box((0.032, 0.022, 0.25), (0.37, ty, top + 0.31), "dark", bevel=0.008)
        b.box((0.038, 0.028, 0.12), (0.37, ty, top + 0.24), "accent", bevel=0.009)
        b.box((0.15, 0.044, 0.052), (0.37, ty, top + 0.44), "metal", bevel=0.010)
        b.open_wrench((0.55, ty, top + 0.34), length=0.27, role="metal", grip_role="accent")
        b.craft_scissors((0.70, ty, top + 0.33), length=0.23, role="metal", grip_role="accent")
        b.cyl(0.012, 0.16, (0.83, ty, top + 0.37), "metal", segments=8)
        b.cyl(0.024, 0.105, (0.83, ty, top + 0.24), "accent", segments=10, bevel=0.006)
        # Sculpted 3-Peak Contoured Toy-Brand Header with Lush Melting Paint & Framed EXTREME Banner (sec_42!)
        hz = top + bh + 0.30
        head = Matrix.Translation((0, by - 0.02, hz))
        hpts = crown_wave_outline(1.50, 0.56, peak_h=0.14, side_h=0.065, corner=0.16, step=0.078)
        b.shape(hpts, -0.058, 0.058, "primary", bevel=0.020, M=head)
        b.shape(inset_outline(hpts, 0.050, smooth=2), -0.070, -0.048, "dark", bevel=0.006, M=head)
        b.tube_along_outline(inset_outline(hpts, 0.038, smooth=2), -0.064, 0.036, "accent", swell=0.08, seg=8, M=head)
        b.slime_drips_mb([
            (-0.68, -0.072, -0.22, 0.14, 0.038),
            (-0.52, -0.074, -0.24, 0.10, 0.034),
            (0.52, -0.074, -0.24, 0.11, 0.034),
            (0.68, -0.072, -0.22, 0.15, 0.038),
        ], role="accent", res=0.022, target_tris=320, M=head)
        b.banner_decal(0.74, (0, -0.078, 0.012), M=head)
        for sx in (-1, 1):
            b.star((sx * 0.54, -0.076, 0.08), 0.052, "light", M=head)
            b.star((sx * 0.50, -0.076, -0.10), 0.036, "gold", M=head)
        if b.animate:
            b.define_bone("crown", (0.02, by - 0.02, hz + 0.38))
        with b.use_bone("crown"):
            b.crown((0.02, 0, 0.38), 0.120, 0.115, role="gold", gem_role="accent", tilt=(0.04, 0.16, 0), M=head)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.048, "rock_y": 8.0, "twist_z": 16.0},
                "mascot": {"kind": "mascot_nod", "amp_z": 0.016, "rock_y": 7.0},
            })
        return
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.11, 0.11, top - 0.06), (sx * (w / 2 - 0.075), sy * (d / 2 - 0.075), (top - 0.06) / 2 + 0.05), "light", bevel=0.022)
            b.box((0.18, 0.18, 0.065), (sx * (w / 2 - 0.075), sy * (d / 2 - 0.075), 0.0325), "primary", bevel=0.022)
        if aaa:
            b.bolt_cap((sx * (w / 2 - 0.075), -d / 2 - 0.008, 0.11), 0.052, "light", "dark")
    b.box((w, d, 0.08), (0, 0, top - 0.04), "light", bevel=0.026, collide=True)
    b.box((w + 0.02, 0.042, 0.062), (0, -d / 2 - 0.008, top - 0.04), lip_role, bevel=0.016)
    b.box((w * 0.50, d * 0.54, 0.014), (0, -0.05, top + 0.007), "dark" if aaa else "primary", bevel=0.005)
    b.box((w * 0.50 + 0.024, 0.014, 0.018), (0, -0.05 - d * 0.27, top + 0.009), "glow", bevel=0.004)
    if aaa:
        for gx in (-0.42, -0.21, 0.0, 0.21, 0.42):
            b.box((0.008, d * 0.50, 0.005), (gx, -0.05, top + 0.015), "metal", bevel=0.0, segments=1)
        for gy in (-0.22, -0.05, 0.12):
            b.box((w * 0.48, 0.008, 0.005), (0, gy, top + 0.015), "metal", bevel=0.0, segments=1)
        # Clean 3D craft tools & blueprint card on cutting mat (replaced flat red pancake!)
        bp_m = trs((0.16, -0.02, top + 0.017), (0, 0, -0.14))
        b.box((0.26, 0.19, 0.006), (0, 0, 0), "light", bevel=0.002, segments=1, M=bp_m)
        b.box((0.18, 0.030, 0.004), (0, 0.05, 0.004), "primary", bevel=0.001, segments=1, M=bp_m)
        b.box((0.14, 0.018, 0.004), (-0.02, -0.02, 0.004), "dark", bevel=0.001, segments=1, M=bp_m)
        kn_m = trs((-0.14, -0.09, top + 0.023), (0, 0, 0.42))
        b.box((0.17, 0.032, 0.018), (0, 0, 0), "primary", bevel=0.005, segments=1, M=kn_m)
        b.box((0.075, 0.020, 0.006), (0.11, 0, 0), "metal", bevel=0.002, segments=1, M=kn_m)
        b.cyl(0.052, 0.042, (-0.34, 0.04, top + 0.036), "gold", segments=14, bevel=0.006)
        b.cyl(0.032, 0.046, (-0.34, 0.04, top + 0.036), "dark", segments=12)
        # Compact front lip paint drips strictly ABOVE drawers & center shield (zero overlap!)
        b.fat_curtain(-w * 0.45, w * 0.45, top - 0.048, -d / 2 - 0.022, lip_role, thick=0.030, max_drop=0.068, drops=5, pearls=False)
        crown_2d = [(-0.14, -0.09), (0.14, -0.09), (0.16, 0.08), (0.07, 0.01), (0.0, 0.11), (-0.07, 0.01), (-0.16, 0.08)]
        for side in (-1, 1):
            sx = side * (w / 2 - 0.04)
            b.box((0.04, d - 0.20, 0.62), (sx, 0, 0.44), "dark", bevel=0.015)
            b.box((0.048, d - 0.30, 0.48), (sx + side * 0.012, 0, 0.45), "primary", bevel=0.02)
            b.shape(crown_2d, -0.016, 0.016, "gold", bevel=0.004, matrix=trs((sx + side * 0.044, 0, 0.46), (0, 0, side * math.pi * 0.5)))
    else:
        b.curtain(-0.42, 0.42, top - 0.06, -d / 2 - 0.02, lip_role, max_drop=0.17, drops=4)
    for sx in (-1, 1):
        cx = sx * (w / 2 - 0.38)
        b.box((0.52, d - 0.14, 0.68), (cx, 0, 0.1 + 0.34), "light", bevel=0.024, collide=True)
        for k in range(2):
            z = 0.27 + k * 0.32
            role = drawer_a if k == 0 else drawer_b
            b.box((0.46, 0.035, 0.27), (cx, -d / 2 + 0.06, z), role, bevel=0.022)
            handle_role = "light" if role != "light" else "dark"
            b.box((0.18, 0.036, 0.036), (cx, -d / 2 + 0.032, z + 0.055), handle_role, bevel=0.012)
            if aaa and k == 0:
                b.star((cx, -d / 2 + 0.040, z - 0.055), 0.036, "gold")
    b.box((w - 1.24, d - 0.20, 0.035), (0, 0.04, 0.14), "light", bevel=0.012)
    b.box((w - 1.26, 0.035, 0.64), (0, -d / 2 + 0.10, 0.45), "dark" if aaa else "primary", bevel=0.012)
    if aaa and b.mascot_style == "spray_can":
        b.shield_plaque((0, -d / 2 + 0.082, 0.44), 0.45, 0.46, role="dark", border_role="light", accent_role="gold")
        if b.animate:
            b.define_bone("mascot", (0.0, -d / 2 - 0.030, 0.43))
        with b.use_bone("mascot"):
            b.mascot((0, -d / 2 - 0.030, 0.43), 0.135, "primary", "light", drips=False)
    else:
        blob = blob_outline(0.50, 0.42, b.rng, wobble=0.014, lobes=2, lobe_amp=0.048)
        plaque_role = "light" if aaa else lip_role
        b.shape(blob, -d / 2 + 0.05, -d / 2 + 0.085, plaque_role, bevel=0.012, loc=(0, 0, 0.45))
        b.mascot((0, -d / 2 + 0.02, 0.5), 0.13, "primary", "light", drips=False)
        b.crown((0.03, -d / 2 + 0.02, 0.6), 0.07, 0.065, tilt=(0.25, 0, -0.2))
    by = d / 2 - 0.07
    bh = 0.80
    bz = top + bh / 2
    b.box((w - 0.16, 0.055, bh), (0, by, bz), "wood", bevel=0.015, collide=True)
    b.box((w - 0.08, 0.075, 0.05), (0, by, top + bh), "primary", bevel=0.016)
    peg_rows, peg_cols = (4, 8) if aaa else (5, 14)
    for r in range(peg_rows):
        for c in range(peg_cols):
            b.cyl(0.009, 0.01, (-w / 2 + 0.24 + c * ((w - 0.48) / (peg_cols - 1)), by - 0.030, top + 0.15 + r * (0.44 / (peg_rows - 1))), "dark", axis="Y", segments=5)
    for sx in (-1, 1):
        x = sx * (w / 2 - 0.055)
        b.box((0.095, 0.095, bh + 0.14), (x, by, top + (bh + 0.14) / 2), "primary", bevel=0.024)
        if aaa:
            b.bolt_cap((x, by - 0.052, top + bh + 0.09), 0.062, "primary", "dark")
        else:
            b.sphere(0.06, (x, by, top + bh + 0.16), "primary", u=12, v=8)
            b.sphere(0.025, (x, by - 0.045, top + bh + 0.16), "accent", u=8, v=6)
    if aaa:
        b.box((0.52, 0.19, 0.026), (-0.62, by - 0.11, top + 0.56), "light", bevel=0.008)
        b.box((0.52, 0.19, 0.026), (-0.62, by - 0.11, top + 0.30), "light", bevel=0.008)
        for sx in (-0.87, -0.37):
            b.box((0.028, 0.19, 0.44), (sx, by - 0.11, top + 0.45), "primary", bevel=0.008)
        for k, role in enumerate(("primary", "light", "dark", "gold")):
            b.spray_can((-0.80 + k * 0.12, by - 0.11, top + 0.625), 0.036, role=role, face=False, detail="low")
        for k, role in enumerate(("primary", "light")):
            b.spray_can((-0.74 + k * 0.18, by - 0.11, top + 0.365), 0.036, role=role, face=False, detail="low")
        b.box((0.18, 0.14, 0.12), (-0.76, -0.14, top + 0.06), "primary", bevel=0.022)
        b.cyl(0.048, 0.15, (-0.76, -0.14, top + 0.08), "dark", axis="X", segments=10)
        b.cyl(0.055, 0.12, (-0.58, -0.02, top + 0.06), "dark", segments=12, bevel=0.008)
        for k, (ax, role) in enumerate(((-0.22, "primary"), (0.0, "gold"), (0.20, "light"))):
            b.cyl(0.012, 0.16, (-0.58 + k * 0.018 - 0.018, -0.02, top + 0.14), role, segments=6, rot=(0.15, ax, 0))
        b.box((0.26, 0.18, 0.13), (0.68, 0.02, top + 0.065), "primary", bevel=0.022)
        b.box((0.28, 0.19, 0.025), (0.68, 0.02, top + 0.125), "light", bevel=0.008)
        b.spray_can((0.86, -0.16, top + 0.082), 0.050, role="primary", face=True, detail="low")
        b.spray_can((0.72, -0.22, top + 0.068), 0.042, role="light", face=False, detail="low")
        b.torus(0.045, 0.016, (0.36, -0.02, top + 0.045), "gold", axis="X", seg_major=14, seg_minor=6)
        for nx, nz, nr, nrole in ((-0.12, top + 0.42, 0.12, "light"), (0.14, top + 0.40, -0.10, "light")):
            nm = trs((nx, by - 0.036, nz), (0, nr, 0))
            b.box((0.18, 0.008, 0.21), (0, 0, 0), nrole, bevel=0.003, segments=1, M=nm)
            b.box((0.10, 0.010, 0.08), (0, -0.005, 0.02), "primary", bevel=0.003, segments=1, M=nm)
            b.cyl(0.014, 0.014, (0, -0.008, 0.09), "gold", axis="Y", segments=8, M=nm)
    else:
        b.box((w - 0.3, 0.16, 0.025), (0, by - 0.1, top + 0.62), "light", bevel=0.008)
        jar_roles = ("primary", "accent", "trim", "light", "primary", "accent")
        for k, role in enumerate(jar_roles):
            x = -w / 2 + 0.3 + k * 0.26
            b.cyl(0.035, 0.08, (x, by - 0.1, top + 0.672), role, segments=12, bevel=0.006)
            b.cyl(0.038, 0.015, (x, by - 0.1, top + 0.72), "light", segments=12)
    ty = by - 0.046
    if aaa:
        # 3D sculpted pegboard tools: red-handled hammer, open-end wrench, craft scissors, screwdriver
        b.box((0.034, 0.024, 0.27), (0.37, ty, top + 0.34), "dark", bevel=0.008)
        b.box((0.040, 0.030, 0.13), (0.37, ty, top + 0.26), "primary", bevel=0.009)
        b.box((0.16, 0.046, 0.056), (0.37, ty, top + 0.48), "metal", bevel=0.010)
        b.open_wrench((0.55, ty, top + 0.38), length=0.29, role="metal", grip_role="primary")
        b.craft_scissors((0.71, ty, top + 0.37), length=0.25, role="metal", grip_role="primary")
        b.cyl(0.013, 0.17, (0.85, ty, top + 0.41), "metal", segments=8)
        b.cyl(0.025, 0.115, (0.85, ty, top + 0.27), "primary", segments=10, bevel=0.006)
        b.cyl(0.027, 0.018, (0.85, ty, top + 0.33), "dark", segments=10)
    else:
        b.box((0.035, 0.022, 0.28), (-0.55, ty, top + 0.34), "dark", bevel=0.008)
        b.box((0.16, 0.045, 0.058), (-0.55, ty, top + 0.48), "metal", bevel=0.01)
        b.box((0.034, 0.018, 0.24), (-0.3, ty, top + 0.34), "metal", bevel=0.006)
        b.torus(0.044, 0.014, (-0.3, ty, top + 0.48), "metal", seg_major=12, seg_minor=6)
        b.cyl(0.014, 0.18, (0.32, ty, top + 0.40), "metal", segments=8)
        b.cyl(0.026, 0.11, (0.32, ty, top + 0.26), "accent", segments=10, bevel=0.006)
    hz = top + bh + (0.35 if aaa else 0.24)
    head = Matrix.Translation((0, by - 0.02, hz))
    if use_logo:
        # ONE shared contour for top header shell, glossy white tube frame, and dark inner panel (zero mismatch!)
        hpts = blob_outline(1.52, 0.62, b.rng, wobble=0.012, lobes=3, lobe_amp=0.075, corner=0.15, step=0.05)
        b.shape(hpts, -0.055, 0.055, "primary", bevel=0.020, M=head)
        b.shape(inset_outline(hpts, 0.054, smooth=2), -0.068, -0.046, "dark", bevel=0.007, M=head)
        b.tube_along_outline(inset_outline(hpts, 0.038, smooth=2), -0.062, 0.036, "light", swell=0.06, seg=10, M=head)
        b.logo_decal(0.92, (0, -0.076, 0.0), M=head)
        if b.animate:
            b.define_bone("crown", (0.02, by - 0.02, hz + 0.35))
        with b.use_bone("crown"):
            b.crown((0.02, 0, 0.35), 0.115, 0.11, role="gold", gem_role="primary", tilt=(0.04, 0.14, 0), M=head)
        for sx in (-1, 1):
            b.star((sx * 0.60, -0.074, 0.15), 0.052, "gold", M=head)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "crown": {"kind": "crown_hover", "amp_z": 0.048, "rock_y": 8.0, "twist_z": 16.0},
                "mascot": {"kind": "mascot_nod", "amp_z": 0.018, "rock_y": 7.0},
            })
    else:
        b.shape(blob_outline(1.2, 0.38, b.rng, wobble=0.012, lobes=3, lobe_amp=0.06), -0.05, 0.05, "accent", bevel=0.015, M=head)
        b.shape(rounded_rect(1.06, 0.26, 0.06), -0.062, -0.045, "primary", bevel=0.006, M=head @ Matrix.Translation((0, 0, -0.01)))
        b.text(b.brand, 0.17, (0, -0.066, -0.01), "light", depth=0.022, max_w=0.8, M=head)
        b.crown((0, 0, 0.2), 0.08, 0.08, M=head)
        for sx in (-1, 1):
            b.star((sx * 0.52, -0.066, 0.1), 0.04, "accent", M=head)


def build_mascot_marker(b, p):
    if b.mascot_style == "billie_bear":
        # V10 Kawaii Billie Bear Chibi Head perched on a Fluffy Milk-Cream Cloud Cushion + Orbiting Golden Stars!
        r = p.get("radius", 0.30)
        zc = r * 1.48
        if b.animate:
            b.define_bone("mascot", (0.0, 0.0, zc))
            b.define_bone("streaks", (0.0, 0.0, zc))
        with b.use_bone("mascot"):
            b.billie_bear((0.0, 0.0, zc), r, role=p.get("role", "primary"), face_role="light", ear_inner="wood", blush_role="trim", tilt=(0.04, -0.06, 0.0), with_cloud=True, detail="high")
        with b.use_bone("streaks"):
            b.star((-r * 1.68, -r * 0.12, zc + r * 0.90), r * 0.28, "gold", crossed=True)
            b.star(( r * 1.62, -r * 0.10, zc + r * 1.05), r * 0.26, "gold", crossed=True)
            b.star((-r * 1.80, -r * 0.14, zc - r * 0.55), r * 0.22, "glow", crossed=True)
            b.star(( r * 1.72, -r * 0.14, zc - r * 0.42), r * 0.24, "light", crossed=True)
            for dx, dy, dz_p, dr, drole in (
                (-r * 1.48,  r * 0.30, zc + r * 0.16, r * 0.14, "light"),
                ( r * 1.52,  r * 0.26, zc + r * 0.32, r * 0.13, "trim"),
                ( 0.0,       r * 1.52, zc + r * 0.45, r * 0.15, "light"),
                (-r * 0.65,  r * 1.40, zc - r * 0.35, r * 0.12, "accent"),
            ):
                b.sphere(dr, (dx, dy, dz_p), drole, scale=(1.1, 0.95, 0.88), u=8, v=6)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "mascot": {"kind": "marker_spin", "amp_z": 0.10, "spin_deg": 360.0, "tilt_x": 4.5},
                "streaks": {"kind": "marker_orbit", "amp_z": 0.06, "spin_deg": -360.0, "tilt_x": 6.0},
            })
        return
    if b.style == "vinyl_toy" and b.mascot_style == "spray_can":
        # V5 Chubby Ultra-Glossy Collectible Vinyl-Toy Spray Can with Melting Drips & Tight Collectible Aura (matches sec_22!)
        r = p.get("radius", 0.27)
        zc = r * 1.54
        if b.animate:
            b.define_bone("mascot", (0.0, 0.0, zc))
            b.define_bone("streaks", (0.0, 0.0, zc))
        with b.use_bone("mascot"):
            b.spray_can(
                (0.0, 0, zc),
                r,
                role=p.get("role", "accent"),
                trim_role="metal",
                nozzle_role="light",
                eye_role="light",
                spark_role="gold",
                face=True,
                drips=True,
                puff=False,
                with_crown=True,
                collar_drips=True,
                drip_role=p.get("drip_role", "light"),
                tilt=(0.05, -0.14, 0.06),
                detail="high",
            )
        with b.use_bone("streaks"):
            # Tightly orbiting comic-outlined sparkle stars & glossy paint droplets (matching sec_22 vinyl aura!)
            b.star((-r * 1.72, -r * 0.12, zc + r * 0.95), r * 0.27, "light")
            b.star((r * 1.65, -r * 0.10, zc + r * 1.10), r * 0.25, "gold")
            b.star((-r * 1.88, -r * 0.15, zc - r * 0.72), r * 0.22, "glow")
            b.star((r * 1.68, -r * 0.15, zc - r * 0.45), r * 0.24, "light")
            drops = [
                (-r * 1.52, r * 0.25, zc + r * 0.18, r * 0.11, "accent"),
                (r * 1.56, r * 0.22, zc + r * 0.35, r * 0.10, "light"),
                (-r * 1.28, r * 0.75, zc - r * 0.35, r * 0.095, "light"),
                (r * 1.32, r * 0.72, zc - r * 0.80, r * 0.10, "accent"),
                (0.0, r * 1.55, zc + r * 0.55, r * 0.11, "light"),
                (-r * 0.60, r * 1.42, zc - r * 0.45, r * 0.09, "accent"),
            ]
            for dx, dy, dz_p, dr, drole in drops:
                b.sphere(dr, (dx, dy, dz_p), drole, scale=(0.95, 0.95, 1.38), u=7, v=5)
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "mascot": {"kind": "marker_spin", "amp_z": 0.11, "spin_deg": 360.0, "tilt_x": 5.5},
                "streaks": {"kind": "marker_orbit", "amp_z": 0.06, "spin_deg": -360.0, "tilt_x": 7.0},
            })
        return
    if b.mascot_style == "spray_can":
        r = p.get("radius", 0.25)
        zc = r * 1.48
        if b.animate:
            b.define_bone("mascot", (0.0, 0.0, zc))
            b.define_bone("streaks", (0.0, 0.0, zc))
        with b.use_bone("mascot"):
            b.spray_can(
                (0.02, 0, zc),
                r,
                role=p.get("role", "primary"),
                trim_role="metal",
                nozzle_role="light",
                eye_role="light",
                spark_role="glowtrim",
                face=True,
                drips=False,
                puff=False,
                with_crown=True,
                collar_drips=False,
                tilt=(0.05, -0.14, 0.08),
                detail="high",
            )
        with b.use_bone("streaks"):
            # Two sleek tapered 3D orbiting graffiti swoosh arcs framing sides/back (100% OPEN front face window!)
            b.swoosh_arc((0.0, 0.0, zc - r * 0.35), r * 1.72, -68, 120, r * 0.105, role="primary", tilt=(0.28, -0.22, 0.0), lift=r * 0.55, steps=15, seg=7)
            b.swoosh_arc((0.0, 0.0, zc + r * 0.28), r * 1.66, 108, 248, r * 0.088, role="gold", tilt=(-0.24, 0.20, 0.0), lift=-r * 0.45, steps=14, seg=7)
            b.star((-r * 2.02, 0.0, zc + r * 1.25), r * 0.26, "glowtrim")
            b.star((r * 1.85, 0.0, zc + r * 1.32), r * 0.25, "gold")
            b.star((-r * 1.85, -r * 0.22, zc - r * 0.70), r * 0.22, "light")
            b.star((r * 2.02, -r * 0.15, zc - r * 0.42), r * 0.22, "gold")
        if b.animate:
            b.set_anim(frames=121, fps=30, tracks={
                "mascot": {"kind": "marker_spin", "amp_z": 0.11, "spin_deg": 360.0, "tilt_x": 5.5},
                "streaks": {"kind": "marker_orbit", "amp_z": 0.06, "spin_deg": -360.0, "tilt_x": 7.0},
            })
        return
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


def build_airdrop(b, p):
    """Vinyl Toy-Brand Supply Airdrop: stepped beacon pad, open armored cage, melting paint cap, spinning mascot core, gyro rings, crown & orbiting mini spray cans."""
    body_role = p.get("body_role", "primary")
    accent_role = p.get("accent_role", "accent")
    core_role = p.get("core_role", accent_role)
    w = p.get("w", 0.94)
    h = p.get("h", 0.96)
    z0 = 0.20
    zc = z0 + h * 0.50
    z_top = z0 + h

    # 1. Grounded Stepped Circular Vinyl Landing Pad + Neon Beacon Ring + 4 Anchor Clamps
    b.cyl(0.68, 0.08, (0, 0, 0.04), "dark", segments=18, bevel=0.016)
    b.torus(0.61, 0.020, (0, 0, 0.084), "glow", axis="Z", seg_major=20, seg_minor=5)
    b.cyl(0.57, 0.07, (0, 0, 0.115), "light", segments=18, bevel=0.014)
    b.cyl(0.49, 0.055, (0, 0, 0.172), body_role, segments=16, bevel=0.012)
    for k in range(4):
        ang = k * math.pi * 0.5 + math.pi * 0.25
        cm = trs((0.57 * math.cos(ang), 0.57 * math.sin(ang), 0.11), (0, 0, ang))
        b.box((0.15, 0.14, 0.13), (0, 0, 0), "dark", bevel=0.020, segments=2, M=cm)
        b.cyl(0.026, 0.030, (0.04, 0, 0.068), accent_role, segments=8, M=cm)
    b.collider_from(Matrix.Translation((0, 0, 0.62)), (1.16, 1.16, 1.24))

    # 2. Open 4-Window Armored Drop Cage (shows glowing spinning reactor core inside!)
    b.box((w - 0.04, w - 0.04, 0.11), (0, 0, z0 + 0.055), body_role, bevel=0.022, segments=2)
    b.box((w - 0.14, w - 0.14, 0.03), (0, 0, z0 + 0.115), "dark", bevel=0.008, segments=1)
    b.torus(0.24, 0.018, (0, 0, z0 + 0.138), "glow", axis="Z", seg_major=18, seg_minor=5)
    b.box((w - 0.02, w - 0.02, 0.11), (0, 0, z_top - 0.055), body_role, bevel=0.022, segments=2)
    b.box((w - 0.14, w - 0.14, 0.03), (0, 0, z_top - 0.115), "dark", bevel=0.008, segments=1)
    b.torus(0.24, 0.016, (0, 0, z_top - 0.132), "glow", axis="Z", seg_major=16, seg_minor=5)

    # 4 corner armor pillars + glowing vertical corner beacon strips + 8 chunky accent corner bumpers
    pt = 0.145
    off = w * 0.5 - pt * 0.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((pt, pt, h), (sx * off, sy * off, zc), "dark", bevel=0.022, segments=2)
            b.box((0.028, 0.016, h * 0.50), (sx * off, sy * (w * 0.5 + 0.004), zc), "glow", bevel=0.004, segments=1)
            b.box((0.016, 0.028, h * 0.50), (sx * (w * 0.5 + 0.004), sy * off, zc), "glow", bevel=0.004, segments=1)
            for zb in (z0 + 0.095, z_top - 0.090):
                b.box((0.20, 0.20, 0.165), (sx * (w * 0.5 - 0.075), sy * (w * 0.5 - 0.075), zb), accent_role, bevel=0.038, segments=2)

    # 4 Lower Armored Aprons + Upper Lintel Rails framing the 4 open viewing windows cleanly
    for sy in (-1, 1):
        b.box((w - 0.22, 0.075, 0.19), (0, sy * (w * 0.5 - 0.036), z0 + 0.135), "dark", bevel=0.016, segments=1)
        b.box((w - 0.26, 0.045, 0.055), (0, sy * (w * 0.5 - 0.022), z0 + 0.225), "light", bevel=0.012, segments=1)
        b.box((w - 0.26, 0.055, 0.075), (0, sy * (w * 0.5 - 0.028), z_top - 0.125), "light", bevel=0.014, segments=1)
    for sx in (-1, 1):
        b.box((0.075, w - 0.22, 0.19), (sx * (w * 0.5 - 0.036), 0, z0 + 0.135), "dark", bevel=0.016, segments=1)
        b.box((0.045, w - 0.26, 0.055), (sx * (w * 0.5 - 0.022), 0, z0 + 0.225), "light", bevel=0.012, segments=1)
        b.box((0.055, w - 0.26, 0.075), (sx * (w * 0.5 - 0.028), 0, z_top - 0.125), "light", bevel=0.014, segments=1)

    # Front & back lower brand plaques with EXTREME COMMUNITY framed banner logo
    if p.get("use_logo", True) and b.logo:
        for sy, rz in ((-1, 0.0), (1, math.pi)):
            b.box((0.50, 0.030, 0.30), (0, sy * (w * 0.5 + 0.008), z0 + 0.145), "dark", bevel=0.014, segments=1)
            b.banner_decal(0.42, (0, sy * (w * 0.5 + 0.028), z0 + 0.145), rot=(math.pi / 2, 0, rz))
        for sx, rz in ((-1, -math.pi / 2), (1, math.pi / 2)):
            b.box((0.030, 0.50, 0.30), (sx * (w * 0.5 + 0.008), 0, z0 + 0.145), "dark", bevel=0.014, segments=1)
            b.banner_decal(0.42, (sx * (w * 0.5 + 0.028), 0, z0 + 0.145), rot=(math.pi / 2, 0, rz))

    # 3. Lush Organic Metaball Melting Spray-Paint Cap draping cleanly over roof corners (clear of open windows!)
    ad_drips = [
        (-w * 0.44, -w * 0.49, 0.22, 0.062, 0.0, -1.0),
        (w * 0.44, -w * 0.49, 0.24, 0.064, 0.0, -1.0),
        (-w * 0.18, -w * 0.49, 0.12, 0.048, 0.0, -1.0),
        (w * 0.18, -w * 0.49, 0.13, 0.048, 0.0, -1.0),
        (-w * 0.44, w * 0.49, 0.22, 0.062, 0.0, 1.0),
        (w * 0.44, w * 0.49, 0.24, 0.064, 0.0, 1.0),
        (w * 0.49, -w * 0.24, 0.18, 0.056, 1.0, 0.0),
        (w * 0.49, w * 0.24, 0.20, 0.058, 1.0, 0.0),
        (-w * 0.49, -w * 0.24, 0.18, 0.056, -1.0, 0.0),
        (-w * 0.49, w * 0.24, 0.20, 0.058, -1.0, 0.0),
    ]
    b.slime_cap_mb(w + 0.02, w + 0.02, z_top + 0.004, role=accent_role, drips=ad_drips, cap_thick=0.060, res=0.030, target_tris=1200)

    # Top circular beacon socket + 4 corner parachute-harness tie-down D-ring lugs!
    b.cyl(0.24, 0.055, (0, 0, z_top + 0.052), "dark", segments=16, bevel=0.012)
    b.cyl(0.19, 0.040, (0, 0, z_top + 0.072), "light", segments=16, bevel=0.008)
    b.cyl(0.14, 0.026, (0, 0, z_top + 0.088), "glow", segments=14, bevel=0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ang = math.atan2(sy, sx)
            lm = trs((sx * (w * 0.36), sy * (w * 0.36), z_top + 0.056), (0, 0, ang))
            b.box((0.085, 0.068, 0.032), (0, 0, 0), "dark", bevel=0.008, segments=1, M=lm)
            b.torus(0.036, 0.011, (0, 0, 0.024), "metal", axis="Y", seg_major=10, seg_minor=5, M=lm)

    # 4. ANIMATED BONES: core (spinning hero mascot), gyro (counter-spinning dual energy rings), crown, orbit (4 mini cans + stars)
    core_z = zc + 0.03
    if b.animate:
        b.define_bone("core", (0.0, 0.0, core_z), parent="root")
        b.define_bone("gyro", (0.0, 0.0, core_z), parent="root")
        b.define_bone("crown", (0.0, 0.0, z_top + 0.148), parent="root")
        b.define_bone("orbit", (0.0, 0.0, core_z), parent="root")

    with b.use_bone("core"):
        b.cyl(0.16, 0.024, (0, 0, core_z - 0.195), "gold", segments=14, bevel=0.006)
        b.cyl(0.12, 0.018, (0, 0, core_z - 0.180), "glow", segments=12, bevel=0.004)
        b.spray_can((0, 0, core_z + 0.015), 0.152, role=core_role, trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", face=True, drips=False, with_crown=False, tilt=(0.04, -0.08, 0.0), detail="low")

    with b.use_bone("gyro"):
        m1 = Matrix.Translation((0, 0, core_z)) @ Euler((math.radians(32), 0, 0)).to_matrix().to_4x4()
        b.torus(0.272, 0.016, (0, 0, 0), "gold", axis="Z", seg_major=18, seg_minor=5, M=m1)
        for k in range(4):
            a = k * math.pi * 0.5
            b.sphere(0.025, (0.272 * math.cos(a), 0.272 * math.sin(a), 0.0), "glow", u=6, v=4, M=m1)
        m2 = Matrix.Translation((0, 0, core_z)) @ Euler((0, math.radians(-32), 0)).to_matrix().to_4x4()
        b.torus(0.246, 0.013, (0, 0, 0), "light", axis="Z", seg_major=16, seg_minor=5, M=m2)

    with b.use_bone("crown"):
        b.crown((0, 0, z_top + 0.148), 0.145, 0.140, role="gold", gem_role=accent_role, tilt=(0.04, 0.16, 0.0))

    with b.use_bone("orbit"):
        orb_r = 0.86
        for k in range(4):
            ang = k * math.pi * 0.5
            cx = orb_r * math.cos(ang)
            cy = orb_r * math.sin(ang)
            cz = core_z + (-0.11 if k % 2 == 0 else 0.12)
            crole = accent_role if k % 2 == 0 else "light"
            # Outward-facing chubby mini spray cans orbiting the airdrop (100% clear of 0.70m corners)
            cm = trs((cx, cy, cz), (0.0, 0.0, ang + math.pi * 0.5))
            b.spray_can((0, 0, 0), 0.064, role=crole, trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", face=True, drips=False, with_crown=False, tilt=(0.08, -0.14, 0.0), detail="low", M=cm)
        for k in range(4):
            ang = k * math.pi * 0.5 + math.pi * 0.25
            sx = (orb_r - 0.01) * math.cos(ang)
            sy = (orb_r - 0.01) * math.sin(ang)
            sz = core_z + (0.22 if k % 2 == 0 else -0.14)
            srole = "gold" if k % 2 == 0 else "light"
            b.star((sx, sy, sz), 0.056, srole, direction=(math.cos(ang), math.sin(ang), 0.0))
            b.sphere(0.030, ((orb_r - 0.03) * math.cos(ang + 0.25), (orb_r - 0.03) * math.sin(ang + 0.25), sz - 0.12), accent_role if k % 2 == 0 else "light", scale=(0.95, 0.95, 1.35), u=6, v=4)

    if b.animate:
        b.set_anim(frames=181, fps=30, tracks={
            "core": {"kind": "marker_spin", "amp_z": 0.055, "spin_deg": 360.0, "tilt_x": 4.5},
            "gyro": {"kind": "airdrop_gyro", "spin_deg": -360.0, "wobble_deg": 18.0},
            "crown": {"kind": "crown_hover", "amp_z": 0.058, "rock_y": 9.0, "twist_z": 18.0},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.075, "spin_deg": 360.0, "tilt_x": 4.0},
        })


def build_powerbox(b, p):
    """Vinyl Toy-Brand Electrical Power Box (ตู้ไฟ / Blackout): armored cabinet, melting paint cap, flipping twin breaker levers, fast rotating roof sirens, glowing voltage display, keypad, conduits, crown & orbiting bolts/cans."""
    body_role = p.get("body_role", "primary")
    accent_role = p.get("accent_role", "accent")
    w = p.get("w", 0.94)
    d = p.get("d", 0.62)
    h = p.get("h", 1.36)
    z0 = 0.18
    zc = z0 + h * 0.5
    z_top = z0 + h
    fy = -d * 0.5

    # 1. Heavy Industrial Chamfered Base + Armored Mounting Feet
    b.chamfered_base(w + 0.14, d + 0.14, z0, "dark", pad_role=body_role, glow_role="glow", collide=True, vents=True)
    for sx in (-1, 1):
        b.box((0.14, d * 0.62, 0.06), (sx * (w * 0.5 + 0.04), 0, 0.03), "light", bevel=0.015)

    # 2. Plump Rounded Blood-Crimson Cabinet + Dark Armored Corner Rails + Neon Vertical Warning Strips
    b.box((w, d, h), (0, 0, zc), body_role, bevel=0.052, collide=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.085, 0.085, h - 0.04), (sx * (w * 0.5 - 0.035), sy * (d * 0.5 - 0.035), zc), "dark", bevel=0.020)
            b.box((0.020, 0.016, h * 0.54), (sx * (w * 0.5 - 0.035), sy * (d * 0.5 + 0.012), zc - 0.04), "glow", bevel=0.004)
            b.box((0.016, 0.020, h * 0.54), (sx * (w * 0.5 + 0.012), sy * (d * 0.5 - 0.035), zc - 0.04), "glow", bevel=0.004)

    # 3. Front Recessed Control Door (Chrome-White armored bezel + Obsidian control face + corner hex bolts)
    b.box((w - 0.16, 0.044, h - 0.18), (0, fy - 0.012, zc - 0.01), "light", bevel=0.024)
    b.box((w - 0.26, 0.032, h - 0.28), (0, fy - 0.024, zc - 0.01), "dark", bevel=0.016)
    for sx in (-1, 1):
        for sz in (z0 + 0.15, zc, z_top - 0.17):
            b.cyl(0.016, 0.022, (sx * (w * 0.5 - 0.115), fy - 0.034, sz), "metal", axis="Y", segments=6)

    # Top-left: Glowing Neon-Red Voltage Display ("888V") + Top-right: Power Meter Port + 3 Status LEDs
    vz = z_top - 0.28
    b.box((0.38, 0.026, 0.18), (-0.11, fy - 0.036, vz), "screen", bevel=0.010)
    b.box((0.34, 0.010, 0.014), (-0.11, fy - 0.050, vz + 0.070), "glow", bevel=0.003)
    b.text(p.get("voltage", "240V"), 0.094, (-0.11, fy - 0.052, vz - 0.012), "glow", depth=0.010, max_w=0.33, outline_role=None)
    b.box((0.19, 0.026, 0.18), (0.205, fy - 0.036, vz), "metal", bevel=0.010)
    b.box((0.125, 0.016, 0.075), (0.205, fy - 0.048, vz + 0.025), "dark", bevel=0.005)
    for k, lrole in enumerate(("glow", "gold", "glow")):
        b.cyl(0.014, 0.014, (0.155 + k * 0.050, fy - 0.050, vz - 0.048), lrole, axis="Y", segments=8)

    # Middle-left: Heavy Mechanical Breaker Switch Bay (with 2 ANIMATED flipping levers!)
    sw_z = zc + 0.04
    b.box((0.28, 0.022, 0.26), (-0.17, fy - 0.036, sw_z), "light", bevel=0.012)
    for lx in (-0.23, -0.11):
        b.box((0.068, 0.018, 0.17), (lx, fy - 0.046, sw_z), "dark", bevel=0.006)
        b.box((0.048, 0.012, 0.014), (lx, fy - 0.048, sw_z + 0.105), "glow", bevel=0.003)
        b.box((0.048, 0.012, 0.014), (lx, fy - 0.048, sw_z - 0.105), "metal", bevel=0.003)

    # Middle-right: Tactile 4x4 Security Keypad inside Blazing-Red housing
    kp_x, kp_z = 0.16, zc + 0.03
    b.box((0.26, 0.034, 0.29), (kp_x, fy - 0.038, kp_z), accent_role, bevel=0.016)
    b.box((0.21, 0.016, 0.24), (kp_x, fy - 0.050, kp_z), "dark", bevel=0.008)
    for r in range(4):
        for c in range(3):
            brole = "glow" if (r == 3 and c == 2) else "light"
            b.box((0.040, 0.018, 0.036), (kp_x - 0.055 + c * 0.055, fy - 0.058, kp_z + 0.078 - r * 0.052), brole, bevel=0.005, segments=1)

    # Lower Front Bay: Framed EXTREME COMMUNITY Background Logo + Gold High-Voltage Lightning Badge
    if p.get("use_logo", True) and b.logo:
        b.banner_decal(0.52, (-0.05, fy - 0.044, z0 + 0.34))
        for side_sign, rz in ((-1, -math.pi / 2), (1, math.pi / 2)):
            b.logo_decal(0.46, (side_sign * (w * 0.5 + 0.008), 0.0, zc + 0.10), rot=(math.pi / 2, 0, rz))
        b.logo_decal(0.56, (0.0, d * 0.5 + 0.008, zc + 0.06), rot=(math.pi / 2, 0, math.pi))
    b.lightning_bolt((0.265, fy - 0.050, z0 + 0.25), 0.076, "gold")

    # Left Industrial Ribbed Handle + Right High-Voltage Conduit Box & Thick Insulated Power Cables (zero overlap!)
    b.ribbed_handle((-w * 0.5 + 0.006, 0.0, zc - 0.28), role="light", side_sign=-1, scale=0.82)
    b.box((0.12, 0.24, 0.30), (w * 0.5 + 0.05, 0.02, z0 + 0.32), "dark", bevel=0.020)
    b.box((0.04, 0.16, 0.20), (w * 0.5 + 0.10, 0.02, z0 + 0.32), "metal", bevel=0.010)
    for idx, (cy, crole) in enumerate(((-0.06, accent_role), (0.10, "dark"))):
        b.cyl(0.026, 0.24, (w * 0.5 + 0.06, cy, z0 + 0.10), crole, segments=10, bevel=0.006)
        b.torus(0.065, 0.024, (w * 0.5 + 0.01, cy, z0 + 0.48), crole, axis="Y", seg_major=12, seg_minor=6)

    # Back ventilation louvers
    for k in range(5):
        b.box((0.52, 0.024, 0.030), (0, d * 0.5 + 0.006, z0 + 0.20 + k * 0.055), "dark", bevel=0.006)
    b.box((0.46, 0.014, 0.24), (0, d * 0.5 + 0.002, z0 + 0.31), "glow", bevel=0.003)

    # 4. Lush Organic Metaball Melting Spray-Paint Roof Cap draping down outer corners (100% clear of front displays!)
    pb_drips = [
        (-w * 0.45, fy - 0.006, 0.26, 0.066, 0.0, -1.0),
        (w * 0.45, fy - 0.006, 0.28, 0.068, 0.0, -1.0),
        (w * 0.49, -0.14, 0.24, 0.064, 1.0, 0.0),
        (w * 0.49, 0.16, 0.28, 0.066, 1.0, 0.0),
        (-w * 0.49, -0.14, 0.26, 0.064, -1.0, 0.0),
        (-w * 0.49, 0.16, 0.22, 0.060, -1.0, 0.0),
        (-0.24, d * 0.49, 0.24, 0.064, 0.0, 1.0),
        (0.24, d * 0.49, 0.26, 0.066, 0.0, 1.0),
    ]
    b.slime_cap_mb(w + 0.02, d + 0.02, z_top + 0.002, role=accent_role, drips=pb_drips, cap_thick=0.058, res=0.028, target_tris=1650)

    # 5. Roof Hardware: Left Emergency Cutoff Mushroom Button + Center Twin Strobe Siren Bases + Clear Space for Crown!
    b.box((0.20, 0.20, 0.052), (-0.32, -0.02, z_top + 0.056), "dark", bevel=0.014)
    b.cyl(0.072, 0.034, (-0.32, -0.02, z_top + 0.090), "light", segments=14, bevel=0.008)
    b.cyl(0.056, 0.042, (-0.32, -0.02, z_top + 0.114), "glow", segments=14, bevel=0.012)

    siren_specs = (("siren_l", -0.10, 720.0), ("siren_r", 0.08, -720.0))
    for _, sx, _ in siren_specs:
        b.cyl(0.060, 0.046, (sx, 0.0, z_top + 0.056), "dark", segments=14, bevel=0.009)
        b.cyl(0.048, 0.026, (sx, 0.0, z_top + 0.086), "light", segments=14, bevel=0.006)
        b.cyl(0.040, 0.112, (sx, 0.0, z_top + 0.152), "glow", segments=14, bevel=0.012)
        b.cyl(0.044, 0.018, (sx, 0.0, z_top + 0.214), "dark", segments=14, bevel=0.005)

    # 6. ANIMATED BONES: switch_a, switch_b (flipping breakers), siren_l & siren_r (counter-spinning strobe rings), crown, orbit (cans + lightning bolts)
    if b.animate:
        b.define_bone("switch_a", (-0.23, fy - 0.046, sw_z), parent="root")
        b.define_bone("switch_b", (-0.11, fy - 0.046, sw_z), parent="root")
        for bname, sx, _ in siren_specs:
            b.define_bone(bname, (sx, 0.0, z_top + 0.152), parent="root")
        b.define_bone("crown", (0.34, -0.02, z_top + 0.135), parent="root")
        b.define_bone("orbit", (0.0, 0.0, zc), parent="root")

    for bname, lx in (("switch_a", -0.23), ("switch_b", -0.11)):
        with b.use_bone(bname):
            b.cyl(0.020, 0.044, (lx, fy - 0.052, sw_z), "metal", axis="X", segments=8)
            lm = trs((lx, fy - 0.052, sw_z), (math.radians(-30.0), 0.0, 0.0))
            b.box((0.022, 0.084, 0.022), (0, -0.044, 0), "metal", bevel=0.005, segments=1, M=lm)
            b.box((0.068, 0.034, 0.040), (0, -0.088, 0), accent_role, bevel=0.011, segments=2, M=lm)

    for bname, sx, _ in siren_specs:
        with b.use_bone(bname):
            # External rotating armored warning strobe collar & twin beacon wings spinning IN PLACE around each siren dome
            b.torus(0.054, 0.010, (sx, 0.0, z_top + 0.152), "gold", axis="Z", seg_major=14, seg_minor=5)
            for sgn in (-1, 1):
                b.box((0.020, 0.012, 0.064), (sx + sgn * 0.058, 0.0, z_top + 0.152), "light", bevel=0.004, segments=1)

    with b.use_bone("crown"):
        b.crown((0.34, -0.02, z_top + 0.135), 0.106, 0.104, role="gold", gem_role=accent_role, tilt=(0.05, -0.14, 0.18))

    with b.use_bone("orbit"):
        orb_r = 0.78
        for k, (ang, cz, crole) in enumerate((
            (0.0, zc + 0.18, accent_role),
            (math.pi, zc + 0.02, "light"),
        )):
            cx = orb_r * math.cos(ang)
            cy = orb_r * math.sin(ang)
            cm = trs((cx, cy, cz), (0.0, 0.0, ang + math.pi * 0.5))
            b.spray_can((0, 0, 0), 0.062, role=crole, trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", face=True, drips=False, with_crown=False, tilt=(0.08, -0.14, 0.0), detail="low", M=cm)
        for k, (ang, cz, brole) in enumerate((
            (math.radians(58), zc + 0.34, "gold"),
            (math.radians(128), zc - 0.18, "glow"),
            (math.radians(238), zc + 0.28, "gold"),
            (math.radians(308), zc - 0.20, "glow"),
        )):
            bx = (orb_r - 0.01) * math.cos(ang)
            by = (orb_r - 0.01) * math.sin(ang)
            b.lightning_bolt((bx, by, cz), 0.095, brole, direction=(math.cos(ang), math.sin(ang), 0.0))
        for ang, cz in ((math.radians(92), zc + 0.10), (math.radians(272), zc + 0.06)):
            b.star((orb_r * math.cos(ang), orb_r * math.sin(ang), cz), 0.052, "light", direction=(math.cos(ang), math.sin(ang), 0.0))

    if b.animate:
        b.set_anim(frames=121, fps=30, tracks={
            "switch_a": {"kind": "breaker_flip", "flip_deg": 56.0, "t0": 0.10, "t1": 0.48},
            "switch_b": {"kind": "breaker_flip", "flip_deg": 56.0, "t0": 0.52, "t1": 0.90},
            "siren_l": {"kind": "siren_spin", "spin_deg": 720.0, "amp_z": 0.014},
            "siren_r": {"kind": "siren_spin", "spin_deg": -720.0, "amp_z": 0.014},
            "crown": {"kind": "crown_hover", "amp_z": 0.048, "rock_y": 9.0, "twist_z": 18.0},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.070, "spin_deg": 360.0, "tilt_x": 4.0},
        })


def build_parking(b, p):
    """V9 Low-Profile Airdrop-Scale 360-Degree Circular Parking Beacon Pod (ZERO screens! ~1.54m tall matching Airdrop, twin lifting barrier arms + 4-way diagonal logo plaques with ZERO overlap + 360 rotating PARKING sign + circular P medallion + crown + orbit)."""
    body_role = p.get("body_role", "primary")
    accent_role = p.get("accent_role", "accent")
    base_role = p.get("base_role", "light")

    # 1. Wide Grounded Stepped Circular Landing Pad (matching 1nfx_ext_airdrop scale & stance!)
    b.cyl(0.65, 0.060, (0, 0, 0.030), "dark", segments=16, bevel=0.014)
    b.torus(0.585, 0.018, (0, 0, 0.062), "glow", axis="Z", seg_major=18, seg_minor=4)
    b.cyl(0.545, 0.060, (0, 0, 0.090), base_role, segments=16, bevel=0.014)
    b.cyl(0.465, 0.048, (0, 0, 0.140), body_role, segments=16, bevel=0.012)
    for k in range(4):
        ang = k * math.pi * 0.5 + math.pi * 0.25
        pm = trs((0.535 * math.cos(ang), 0.535 * math.sin(ang), 0.088), (0, 0, ang))
        b.box((0.128, 0.122, 0.096), (0, 0, 0), "dark", bevel=0.020, segments=1, M=pm)
        b.box((0.032, 0.070, 0.024), (0.058, 0, 0.010), "glow", bevel=0.005, segments=1, M=pm)
        b.cyl(0.022, 0.020, (0.02, 0, 0.052), accent_role, segments=8, M=pm)
    b.collider_from(Matrix.Translation((0, 0, 0.09)), (1.26, 1.26, 0.18))

    # 2. Compact Low-Slung Curvy Circular Pod Drum (z = 0.14..0.60 — chunky & low matching Airdrop, ZERO screens!)
    col_profile = [
        (0.14, 0.390),
        (0.20, 0.422),
        (0.31, 0.388),
        (0.43, 0.376),
        (0.52, 0.398),
        (0.57, 0.408),
        (0.61, 0.365),
    ]
    b.round_column(col_profile, body_role, segs=20, collide=True)

    # 2 Symmetric Front/Back Chrome Ribs + Neon Flutes + Round Tactile Park Buttons cleanly at ±Y (90 & 270 deg)
    for ang in (math.pi * 0.5, math.pi * 1.5):
        ca, sa = math.cos(ang), math.sin(ang)
        rm = trs((0.378 * ca, 0.378 * sa, 0.36), (0.0, 0.0, ang))
        b.box((0.058, 0.086, 0.33), (0, 0, 0), "light", bevel=0.015, segments=1, M=rm)
        b.box((0.024, 0.024, 0.24), (0.026, 0, 0), "glow", bevel=0.004, segments=1, M=rm)
        b.cyl(0.036, 0.026, (0.034, 0, 0.03), "dark", axis="X", segments=8, bevel=0.005, M=rm)
        b.cyl(0.024, 0.020, (0.046, 0, 0.03), accent_role, axis="X", segments=8, bevel=0.004, M=rm)

    # 4-Way Diagonal Framed EXTREME COMMUNITY Brand Plaques at 45, 135, 225, 315 deg (100% CLEAR of ±X barrier gearboxes AND ±Y ribs!)
    if p.get("use_logo", True) and b.logo:
        for k in range(4):
            ang = k * math.pi * 0.5 + math.pi * 0.25
            ca, sa = math.cos(ang), math.sin(ang)
            bm = trs((0.386 * ca, 0.386 * sa, 0.34), (0.0, 0.0, ang + math.pi * 0.5))
            b.box((0.285, 0.028, 0.185), (0, 0, 0), "dark", bevel=0.010, segments=1, M=bm)
            b.banner_decal(0.242, (0, -0.018, 0), M=bm)

    # 3. Smooth Lush 360-Degree Circular Organic Metaball Melting Paint Collar pouring cleanly in the 8 gaps ABOVE plaques & gearboxes!
    gap_angles = [math.radians(22.5 + k * 45.0) for k in range(8)]
    b.slime_collar_mb(0.408, 0.582, role=accent_role, drip_angles=gap_angles, drop_min=0.072, drop_max=0.120, rad=0.042, res=0.025, target_tris=1080)

    # Compact Chrome & Obsidian Rotary Turntable Hub
    b.cyl(0.290, 0.040, (0, 0, 0.618), "dark", segments=14, bevel=0.009)
    b.torus(0.268, 0.014, (0, 0, 0.642), "glow", axis="Z", seg_major=16, seg_minor=4)
    b.cyl(0.188, 0.052, (0, 0, 0.664), "light", segments=14, bevel=0.009)

    # 4. Twin Symmetric 180-Degree Opposite Barrier Gearboxes cleanly at ±X (0 & 180 deg, z = 0.34 -> lifted +42 deg tips reach z=0.637, 4.5cm+ clear below sign_ring!)
    gx, gz = 0.415, 0.34
    for sx in (-1, 1):
        b.cyl(0.096, 0.11, (sx * (gx - 0.045), 0.0, gz), "dark", axis="X", segments=12, bevel=0.014)
        b.cyl(0.078, 0.085, (sx * gx, 0.0, gz), "light", axis="X", segments=12, bevel=0.012)
        b.torus(0.070, 0.011, (sx * (gx + 0.030), 0.0, gz), "glow", axis="X", seg_major=12, seg_minor=4)

    # 5. ANIMATED BONES (7 bones): sign_ring, gate_l, gate_r, p_badge, crown, orbit (~1.54m total matching Airdrop!)
    sz_sign = 0.89
    sw, sh = 1.12, 0.38
    sign_grp = Matrix.Translation((0.0, 0.0, sz_sign))
    p_pos = (0.0, 0.0, 1.22)
    c_pos = (0.0, 0.0, 1.40)

    if b.animate:
        b.define_bone("sign_ring", (0.0, 0.0, sz_sign), parent="root")
        b.define_bone("gate_l", (-gx - 0.01, 0.0, gz), parent="root")
        b.define_bone("gate_r", (gx + 0.01, 0.0, gz), parent="root")
        b.define_bone("p_badge", p_pos, parent="root")
        b.define_bone("crown", c_pos, parent="root")
        b.define_bone("orbit", (0.0, 0.0, 0.90), parent="root")

    with b.use_bone("sign_ring"):
        s_out = rounded_rect(sw, sh, sh * 0.46, step=0.098)
        b.shape(s_out, -0.086, 0.086, "light", bevel=0.024, M=sign_grp, collide=True)
        b.shape(inset_outline(s_out, 0.038, smooth=1), -0.102, -0.076, "dark", bevel=0.005, M=sign_grp)
        b.shape(inset_outline(s_out, 0.038, smooth=1), 0.076, 0.102, "dark", bevel=0.005, M=sign_grp)
        b.shape(inset_outline(s_out, 0.064, smooth=1), -0.112, -0.086, body_role, bevel=0.005, M=sign_grp)
        b.shape(inset_outline(s_out, 0.064, smooth=1), 0.086, 0.112, body_role, bevel=0.005, M=sign_grp)
        for sx in (-1, 1):
            b.cyl(0.030, 0.026, (sx * (sw * 0.5 + 0.008), 0, 0), "glow", axis="X", segments=8, bevel=0.005, M=sign_grp)
        for side, y, rz in ((-1, -0.122, 0.0), (1, 0.122, math.pi)):
            b.text(p.get("label", "PARKING"), 0.148, (0.0, y, 0.004), "light", depth=0.018, max_w=sw * 0.78, outline_role="dark", rot_z=rz, M=sign_grp)

    for bname, sx in (("gate_l", -1), ("gate_r", 1)):
        with b.use_bone(bname):
            px = sx * (gx + 0.01)
            b.cyl(0.060, 0.096, (px, 0.0, gz), "dark", axis="Y", segments=10, bevel=0.010)
            b.cyl(0.036, 0.110, (px, 0.0, gz), accent_role, axis="Y", segments=8, bevel=0.007)
            b.box((0.092, 0.074, 0.076), (px + sx * 0.055, 0.0, gz), "dark", bevel=0.014, segments=1)
            seg_w = 0.072
            for k in range(4):
                srole = accent_role if k % 2 == 0 else "light"
                b.box((seg_w + 0.005, 0.054, 0.062), (px + sx * (0.130 + k * seg_w), 0.0, gz), srole, bevel=0.012, segments=1)
            b.sphere(0.036, (px + sx * (0.130 + 4 * seg_w - 0.01), 0.0, gz), "glow", scale=(1.15, 0.85, 0.92), u=7, v=5)

    with b.use_bone("p_badge"):
        b.cyl(0.154, 0.074, p_pos, "gold", axis="Y", segments=16, bevel=0.014)
        b.cyl(0.120, 0.084, p_pos, body_role, axis="Y", segments=14, bevel=0.009)
        b.torus(0.136, 0.010, (p_pos[0], p_pos[1] - 0.042, p_pos[2]), "glow", axis="Y", seg_major=14, seg_minor=4)
        b.torus(0.136, 0.010, (p_pos[0], p_pos[1] + 0.042, p_pos[2]), "glow", axis="Y", seg_major=14, seg_minor=4)
        pm = Matrix.Translation(p_pos)
        for side, y, rz in ((-1, -0.049, 0.0), (1, 0.049, math.pi)):
            b.text("P", 0.172, (0.0, y, -0.004), "light", depth=0.015, max_w=0.145, outline_role=None, rot_z=rz, M=pm)

    with b.use_bone("crown"):
        b.crown(c_pos, 0.108, 0.106, role="gold", gem_role=accent_role, tilt=(0.04, 0.14, 0.0))

    with b.use_bone("orbit"):
        # Orbit cleanly around upper sign band (z = 0.91, r = 0.72 -> 14cm outside sign & 20cm+ ABOVE raised barrier arms!)
        orb_r = 0.72
        for k, (ang, cz, crole) in enumerate((
            (0.0, 0.94, accent_role),
            (math.pi, 0.87, "light"),
        )):
            cm = trs((orb_r * math.cos(ang), orb_r * math.sin(ang), cz), (0.0, 0.0, ang + math.pi * 0.5))
            b.spray_can((0, 0, 0), 0.052, role=crole, trim_role="metal", nozzle_role="light", eye_role="light", spark_role="gold", face=True, drips=False, with_crown=False, tilt=(0.06, -0.12, 0.0), detail="low", M=cm)
        for k in range(4):
            ang = k * math.pi * 0.5 + math.pi * 0.25
            b.star((orb_r * math.cos(ang), orb_r * math.sin(ang), 1.00 if k % 2 == 0 else 0.83), 0.044, "gold" if k % 2 == 0 else "light", direction=(math.cos(ang), math.sin(ang), 0.0), crossed=True)

    if b.animate:
        b.set_anim(frames=181, fps=30, tracks={
            "sign_ring": {"kind": "marker_spin", "amp_z": 0.018, "spin_deg": 360.0, "tilt_x": 1.6},
            "gate_l": {"kind": "gate_lift", "lift_deg": 42.0, "sign": 1.0},
            "gate_r": {"kind": "gate_lift", "lift_deg": 42.0, "sign": -1.0},
            "p_badge": {"kind": "marker_spin", "amp_z": 0.034, "spin_deg": -360.0, "tilt_x": 4.5},
            "crown": {"kind": "crown_hover", "amp_z": 0.040, "rock_y": 8.0, "twist_z": 16.0},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.034, "spin_deg": -360.0, "tilt_x": 3.0},
        })


def build_redbox(b, p):
    """V10 Cute Toy-Brand Rolling 5-Drawer Trunk Cabinet (`imp_prop_tool_draw_01e` 1:1 silhouette & footprint: ~1.06m x 0.56m x 1.06m)!"""
    body_role = p.get("body_role", "primary")
    drawer_role = p.get("drawer_role", "light")
    accent_role = p.get("accent_role", "accent")
    w = p.get("w", 1.04)
    d = p.get("d", 0.54)
    h = p.get("h", 0.98)
    z_base = 0.11

    # 1. 4 Swivel Caster Wheels + Espresso-Cocoa Lower Roll Chassis (authentic `imp_prop_tool_draw_01e` rolling stance!)
    b.box((w - 0.02, d - 0.02, 0.055), (0, 0, z_base + 0.025), "dark", bevel=0.014, segments=2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            wx, wy = sx * (w * 0.41), sy * (d * 0.36)
            b.box((0.085, 0.085, 0.026), (wx, wy, z_base - 0.012), "metal", bevel=0.006, segments=1)
            b.cyl(0.048, 0.046, (wx, wy, 0.048), "dark", axis="X", segments=14, bevel=0.010)
            b.cyl(0.024, 0.052, (wx, wy, 0.048), "gold", axis="X", segments=10, bevel=0.004)
    b.collider_from(Matrix.Translation((0, 0, h * 0.52)), (w + 0.06, d + 0.04, h + 0.04))

    # 2. Main Rounded Beveled Steel Cabinet Body + Crisp Espresso-Cocoa `.bbu-frame` Corner Bumpers
    cab_h = h - z_base - 0.03
    cab_zc = z_base + 0.03 + cab_h * 0.5
    b.box((w, d, cab_h), (0, 0, cab_zc), body_role, bevel=0.032, segments=2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.068, 0.068, cab_h + 0.01), (sx * (w * 0.5 - 0.020), sy * (d * 0.5 - 0.020), cab_zc), "dark", bevel=0.020, segments=2)
    # Recessed front dark cabinet frame opening cleanly housing all 5 drawers
    b.box((w - 0.14, 0.032, cab_h - 0.09), (0, -d * 0.5 + 0.008, cab_zc - 0.01), "dark", bevel=0.012, segments=1)

    # 3. Tubular Curved Side Push-Handle on Right Side (`+X`, iconic `imp_prop_tool_draw_01e` mechanic roll-cab feature!)
    hz = z_base + cab_h - 0.08
    for sy in (-1, 1):
        b.cyl(0.018, 0.095, (w * 0.5 + 0.042, sy * (d * 0.32), hz), "metal", axis="X", segments=10, bevel=0.004)
        b.cyl(0.028, 0.020, (w * 0.5 + 0.004, sy * (d * 0.32), hz), "dark", axis="X", segments=10, bevel=0.004)
    b.cyl(0.022, d * 0.68, (w * 0.5 + 0.085, 0, hz), "dark", axis="Y", segments=12, bevel=0.008)
    b.cyl(0.025, d * 0.42, (w * 0.5 + 0.085, 0, hz), "gold", axis="Y", segments=12, bevel=0.006)
    # Cute Side Brand Plaque on Left Side (`-X`)
    if p.get("use_logo", True) and b.logo:
        b.box((0.024, 0.38, 0.24), (-w * 0.5 - 0.006, 0, cab_zc), "dark", bevel=0.010, segments=1)
        b.banner_decal(0.32, (-w * 0.5 - 0.022, 0, cab_zc), rot=(math.pi / 2, 0, -math.pi / 2))

    # 4. 5 Stacked Drawers (Top drawer rigged for cute peek animation; bottom deep drawer carries framed BILLIE SCHOOL logo!)
    dw = w - 0.19
    y_front = -d * 0.5 - 0.006
    z_top_cab = z_base + 0.03 + cab_h
    if b.animate:
        b.define_bone("top_drawer", (0.0, y_front, z_top_cab - 0.11), parent="root")
        b.define_bone("crown", (0.0, 0.0, z_top_cab + 0.14), parent="root")
        b.define_bone("orbit", (0.0, 0.0, z_top_cab + 0.14), parent="root")

    # Animated Top Drawer (`z = z_top_cab - 0.165 .. z_top_cab - 0.055`)
    with b.use_bone("top_drawer"):
        tz = z_top_cab - 0.112
        b.box((dw, 0.036, 0.096), (0, y_front, tz), drawer_role, bevel=0.012, segments=2)
        b.box((dw - 0.03, 0.22, 0.072), (0, y_front + 0.12, tz - 0.006), "dark", bevel=0.008, segments=1)
        # Cute golden coins / mini tools peeking inside when drawer slides out!
        for cx in (-0.18, 0.0, 0.18):
            b.cyl(0.044, 0.022, (cx, y_front + 0.08, tz + 0.016), "gold", segments=10, bevel=0.005)
        b.box((dw * 0.52, 0.026, 0.022), (0, y_front - 0.026, tz), "gold", bevel=0.007, segments=1)
        b.star((0.0, y_front - 0.038, tz), 0.030, "gold")

    # 3 Middle Pull Drawers + 1 Deep Bottom Hero Drawer
    lower_specs = [
        (z_top_cab - 0.232, 0.096, accent_role, False),
        (z_top_cab - 0.352, 0.096, drawer_role, False),
        (z_top_cab - 0.486, 0.122, accent_role, False),
        (z_base + 0.180,    0.220, drawer_role, True),
    ]
    for dz, dh, drole, is_bottom in lower_specs:
        b.box((dw, 0.034, dh), (0, y_front, dz), drole, bevel=0.012, segments=2)
        b.box((dw * 0.52, 0.024, 0.020), (0, y_front - 0.025, dz + (dh * 0.32 if is_bottom else 0.0)), "gold", bevel=0.006, segments=1)
        if is_bottom and p.get("use_logo", True) and b.logo:
            b.box((0.40, 0.016, 0.155), (0, y_front - 0.020, dz - 0.022), "dark", bevel=0.008, segments=1)
            b.banner_decal(0.32, (0, y_front - 0.032, dz - 0.022), rot=(math.pi / 2, 0, 0))
        elif not is_bottom:
            b.box((0.048, 0.018, 0.018), (0, y_front - 0.026, dz), "dark", bevel=0.004, segments=1)

    # Top Key-Lock Cylinder + Raised Protective Top Tray Lip + Fluffy Cloud/Trim Rim
    b.cyl(0.018, 0.020, (dw * 0.42, y_front - 0.016, z_top_cab - 0.032), "gold", axis="Y", segments=10, bevel=0.004)
    b.box((w + 0.03, d + 0.03, 0.042), (0, 0, z_top_cab + 0.016), "dark", bevel=0.016, segments=2)
    b.box((w - 0.04, d - 0.04, 0.026), (0, 0, z_top_cab + 0.032), drawer_role, bevel=0.010, segments=1)
    # Recessed back & side tray rails (authentic rolling tool-drawer top lip!)
    b.box((w + 0.01, 0.036, 0.060), (0, d * 0.5 - 0.010, z_top_cab + 0.056), body_role, bevel=0.012, segments=1)
    for sx in (-1, 1):
        b.box((0.036, d - 0.02, 0.060), (sx * (w * 0.5 - 0.010), 0, z_top_cab + 0.056), body_role, bevel=0.012, segments=1)

    # Cute Top Mascot Plush + Hovering Golden Stars (`crown` & `orbit` bones!)
    with b.use_bone("crown"):
        b.mascot((0.0, 0.02, z_top_cab + 0.195), 0.165, role=p.get("mascot_role", "primary"), eye_role="light", drips=False)
    with b.use_bone("orbit"):
        b.star((-0.34, -0.14, z_top_cab + 0.24), 0.048, "gold", crossed=True)
        b.star(( 0.34, -0.14, z_top_cab + 0.26), 0.044, "gold", crossed=True)
        b.star(( 0.0,   0.18, z_top_cab + 0.38), 0.038, "glow", crossed=True)

    if b.animate:
        b.set_anim(frames=151, fps=30, tracks={
            "top_drawer": {"kind": "drawer_peek", "pull_y": -0.155},
            "crown": {"kind": "mascot_nod", "amp_z": 0.026, "rock_y": 6.5},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.036, "spin_deg": 360.0, "tilt_x": 3.5},
        })


def build_waterpipe(b, p):
    """V10 Cute Toy-Brand Pressurized Water Valve Manifold (`1nfx_waterpipe` Waterpipe Repair Activity Prop)!"""
    body_role = p.get("body_role", "primary")
    pipe_role = p.get("pipe_role", "accent")
    base_role = p.get("base_role", "light")

    # 1. Stepped Circular Cloud-Collared Base Pad
    b.cyl(0.56, 0.065, (0, 0, 0.032), "dark", segments=18, bevel=0.014)
    b.torus(0.50, 0.016, (0, 0, 0.066), "glow", axis="Z", seg_major=20, seg_minor=5)
    b.cyl(0.46, 0.065, (0, 0, 0.095), base_role, segments=18, bevel=0.014)
    b.slime_collar_mb(0.42, 0.145, role="light", rad=0.044, res=0.026, target_tris=720)
    b.collider_from(Matrix.Translation((0, 0, 0.68)), (1.06, 0.78, 1.36))

    # 2. Twin Vertical Pressurized Columns + Upper Arch Bridge + Bolted Flanges
    for sx in (-1, 1):
        px = sx * 0.28
        b.cyl(0.145, 0.055, (px, 0, 0.165), "dark", segments=16, bevel=0.010)
        b.cyl(0.112, 0.88, (px, 0, 0.62), pipe_role, segments=16, bevel=0.014)
        for fz in (0.36, 0.86):
            b.cyl(0.150, 0.056, (px, 0, fz), "dark", segments=16, bevel=0.012)
            b.cyl(0.136, 0.030, (px, 0, fz), "gold", segments=16, bevel=0.006)
        b.sphere(0.125, (px, 0, 1.06), pipe_role, u=12, v=8)
    # Upper Horizontal Manifold Bridge & Center Junction Tank
    b.cyl(0.108, 0.56, (0, 0, 1.06), pipe_role, axis="X", segments=16, bevel=0.012)
    b.cyl(0.195, 0.36, (0, 0, 0.62), body_role, segments=18, bevel=0.026)
    b.cyl(0.215, 0.050, (0, 0, 0.45), "dark", segments=18, bevel=0.012)
    b.cyl(0.215, 0.050, (0, 0, 0.79), "dark", segments=18, bevel=0.012)
    b.cyl(0.100, 0.56, (0, 0, 0.62), pipe_role, axis="X", segments=14, bevel=0.010)

    # Top Pressure Gauge Dial (`z = 1.24`, facing -Y) + Front Brand Plaque
    b.cyl(0.032, 0.12, (0, 0, 1.14), "metal", segments=10, bevel=0.005)
    b.cyl(0.118, 0.072, (0, 0, 1.27), "dark", axis="Y", segments=16, bevel=0.012)
    b.cyl(0.094, 0.078, (0, -0.004, 1.27), "light", axis="Y", segments=16, bevel=0.005)
    b.box((0.016, 0.014, 0.068), (0.018, -0.048, 1.285), "trim", bevel=0.003, segments=1, rot=(0, -0.45, 0))
    b.cyl(0.022, 0.020, (0, -0.048, 1.27), "gold", axis="Y", segments=10)
    if p.get("use_logo", True) and b.logo:
        b.box((0.44, 0.032, 0.26), (0, -0.22, 0.30), "dark", bevel=0.012, segments=1)
        b.banner_decal(0.36, (0, -0.242, 0.30), rot=(math.pi / 2, 0, 0))

    # 3. Animated 4-Spoke Golden Valve Handwheel (`valve`), Cute Mascot (`crown`) & Sparkles (`orbit`)
    if b.animate:
        b.define_bone("valve", (0.0, -0.26, 0.64), parent="root")
        b.define_bone("crown", (0.28, 0.0, 1.24), parent="root")
        b.define_bone("orbit", (0.0, 0.0, 0.72), parent="root")

    with b.use_bone("valve"):
        b.cyl(0.048, 0.14, (0, -0.21, 0.64), "metal", axis="Y", segments=12, bevel=0.008)
        b.torus(0.185, 0.028, (0, -0.28, 0.64), "gold", axis="Y", seg_major=20, seg_minor=6)
        for ang in (0.0, math.pi * 0.5):
            vm = trs((0, -0.28, 0.64), (0, ang, 0))
            b.cyl(0.018, 0.34, (0, 0, 0), "dark", axis="X", segments=8, bevel=0.004, M=vm)
        b.cyl(0.050, 0.040, (0, -0.295, 0.64), "dark", axis="Y", segments=12, bevel=0.008)
        b.star((0, -0.320, 0.64), 0.036, "gold")

    with b.use_bone("crown"):
        b.mascot((0.28, 0.0, 1.28), 0.145, role="primary", eye_role="light", drips=False)
        b.crown((-0.28, 0.0, 1.18), 0.095, 0.090, role="gold", gem_role=body_role)

    with b.use_bone("orbit"):
        for k in range(4):
            a = k * math.pi * 0.5 + math.pi * 0.25
            b.star((0.62 * math.cos(a), 0.62 * math.sin(a), 0.76 + (0.14 if k % 2 == 0 else -0.10)), 0.048, "gold" if k % 2 == 0 else "glow", crossed=True)

    if b.animate:
        b.set_anim(frames=151, fps=30, tracks={
            "valve": {"kind": "valve_spin", "spin_deg": 360.0},
            "crown": {"kind": "mascot_nod", "amp_z": 0.028, "rock_y": 7.0},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.048, "spin_deg": -360.0, "tilt_x": 4.0},
        })


def build_gachapon(b, p):
    """V10 Kawaii Billie Capsule Gachapon Vending Machine (`1nfx_gachapon` / Lucky Capsule Event Prop)!"""
    body_role = p.get("body_role", "primary")
    accent_role = p.get("accent_role", "accent")
    w = p.get("w", 0.84)
    d = p.get("d", 0.74)

    # 1. Grounded `.bbu-frame` Stepped Base + Chunky Lower Vending Cabinet (`z = 0..0.94m`)
    b.chamfered_base(w + 0.08, d + 0.08, 0.14, role="dark", pad_role=body_role, glow_role="glow", collide=True)
    b.box((w, d, 0.78), (0, 0, 0.53), body_role, bevel=0.045, segments=2, collide=True)
    b.box((w - 0.10, 0.036, 0.66), (0, -d * 0.5 - 0.004, 0.54), "light", bevel=0.020, segments=2)
    b.box((w - 0.16, 0.020, 0.60), (0, -d * 0.5 - 0.016, 0.54), "dark", bevel=0.012, segments=1)
    b.box((w - 0.20, 0.018, 0.56), (0, -d * 0.5 - 0.022, 0.54), accent_role, bevel=0.010, segments=1)

    # Dispenser Chute with a Cute Prize Capsule Sitting Inside (`z = 0.34m`) + Coin Slot!
    b.box((0.28, 0.08, 0.18), (0, -d * 0.5 - 0.010, 0.34), "dark", bevel=0.016, segments=1)
    b.sphere(0.056, (0, -d * 0.5 - 0.015, 0.31), "trim", u=10, v=7)
    b.sphere(0.056, (0, -d * 0.5 - 0.015, 0.31), "light", scale=(1.02, 1.02, 0.52), u=10, v=6)
    b.box((0.065, 0.024, 0.095), (0.24, -d * 0.5 - 0.030, 0.60), "metal", bevel=0.008, segments=1)
    b.box((0.014, 0.016, 0.046), (0.24, -d * 0.5 - 0.040, 0.60), "dark", bevel=0.002, segments=1)
    if p.get("use_logo", True) and b.logo:
        b.box((0.48, 0.024, 0.20), (0, -d * 0.5 - 0.024, 0.78), "dark", bevel=0.010, segments=1)
        b.banner_decal(0.40, (0, -d * 0.5 - 0.040, 0.78), rot=(math.pi / 2, 0, 0))

    # 2. Big Plump Capsule Showcase Chamber (`z = 0.94..1.52m`) Packed with Colorful 4-School Gacha Balls!
    b.cyl(0.42, 0.060, (0, 0, 0.94), "dark", segments=20, bevel=0.014)
    b.cyl(0.39, 0.046, (0, 0, 0.98), "light", segments=20, bevel=0.012)
    # 4 Curved Showcase Corner Ribs framing the open capsule globe
    for k in range(4):
        a = k * math.pi * 0.5 + math.pi * 0.25
        rm = trs((0.35 * math.cos(a), 0.35 * math.sin(a), 1.24), (0, 0, a))
        b.box((0.052, 0.052, 0.52), (0, 0, 0), "dark", bevel=0.014, segments=1, M=rm)
        b.box((0.024, 0.020, 0.44), (0.020, 0, 0), "glow", bevel=0.004, segments=1, M=rm)
    # 14 Plump Colorful Gacha Capsules nestled neatly inside the globe (Brown, Blush Pink, Gold, Cream, Accent!)
    cap_roles = ("primary", "trim", "gold", "accent", "light")
    caps = [
        (-0.18, -0.14, 1.09), (0.00, -0.19, 1.08), (0.18, -0.14, 1.09),
        (-0.20,  0.08, 1.09), (0.00,  0.04, 1.08), (0.20,  0.08, 1.09),
        (-0.10,  0.20, 1.09), (0.12,  0.19, 1.09),
        (-0.14, -0.10, 1.24), (0.08, -0.12, 1.24), (-0.04, 0.08, 1.25),
        ( 0.16,  0.06, 1.24), (-0.16, 0.10, 1.24), (0.00, -0.02, 1.36),
    ]
    for ci, (cx, cy, cz) in enumerate(caps):
        b.sphere(0.082, (cx, cy, cz), cap_roles[ci % len(cap_roles)], u=10, v=7)
        b.torus(0.081, 0.009, (cx, cy, cz), "light", axis="Z", seg_major=12, seg_minor=4)

    # Top Dome Cap + Fluffy Cloud Trim Ring + Collider
    b.cyl(0.41, 0.056, (0, 0, 1.50), "dark", segments=20, bevel=0.014)
    b.slime_collar_mb(0.39, 1.53, role="light", rad=0.046, res=0.026, target_tris=720)
    b.cyl(0.36, 0.090, (0, 0, 1.57), body_role, segments=20, bevel=0.024)
    b.collider_from(Matrix.Translation((0, 0, 1.28)), (0.86, 0.82, 0.72))

    # 3. Animated Golden Star Turn-Crank (`crank`), Hero Topper (`crown`) & Orbiting Stars (`orbit`)
    if b.animate:
        b.define_bone("crank", (0.0, -d * 0.5 - 0.055, 0.58), parent="root")
        b.define_bone("crown", (0.0, 0.0, 1.76), parent="root")
        b.define_bone("orbit", (0.0, 0.0, 1.28), parent="root")

    with b.use_bone("crank"):
        b.cyl(0.088, 0.036, (0, -d * 0.5 - 0.040, 0.58), "dark", axis="Y", segments=16, bevel=0.008)
        b.cyl(0.072, 0.024, (0, -d * 0.5 - 0.055, 0.58), "light", axis="Y", segments=14, bevel=0.006)
        b.box((0.175, 0.036, 0.042), (0, -d * 0.5 - 0.074, 0.58), "gold", bevel=0.012, segments=2)
        b.star((0, -d * 0.5 - 0.095, 0.58), 0.042, "gold")

    with b.use_bone("crown"):
        b.mascot((0.0, 0.0, 1.78), 0.185, role="primary", eye_role="light", drips=False)

    with b.use_bone("orbit"):
        for k in range(4):
            a = k * math.pi * 0.5
            b.star((0.56 * math.cos(a), 0.56 * math.sin(a), 1.32 + (0.14 if k % 2 == 0 else -0.12)), 0.050, "gold" if k % 2 == 0 else "glow", crossed=True)

    if b.animate:
        b.set_anim(frames=151, fps=30, tracks={
            "crank": {"kind": "crank_turn", "spin_deg": 360.0},
            "crown": {"kind": "mascot_nod", "amp_z": 0.032, "rock_y": 6.5},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.050, "spin_deg": 360.0, "tilt_x": 4.0},
        })


def build_washmoney(b, p):
    """V10 Kawaii Billie Coin Laundry Money-Washer (`washmoney` Activity Prop — spinning cash & bubbles inside round porthole drum)!"""
    body_role = p.get("body_role", "light")
    accent_role = p.get("accent_role", "primary")
    w = p.get("w", 0.98)
    d = p.get("d", 0.84)
    h = p.get("h", 1.18)

    # 1. Grounded Stepped Base + Chunky Rounded Milk-Cream & Espresso-Cocoa Washer Cabinet
    b.chamfered_base(w + 0.06, d + 0.06, 0.13, role="dark", pad_role=accent_role, glow_role="glow", collide=True)
    b.box((w, d, h - 0.13), (0, 0, 0.13 + (h - 0.13) * 0.5), body_role, bevel=0.048, segments=2, collide=True)
    # Crisp Espresso-Cocoa side accent stripes & vertical `.bbu-frame` edge trim
    for sx in (-1, 1):
        b.box((0.036, d - 0.12, h - 0.24), (sx * (w * 0.5 + 0.004), 0, 0.13 + (h - 0.13) * 0.5), accent_role, bevel=0.014, segments=1)
        b.box((0.058, 0.058, h - 0.12), (sx * (w * 0.5 - 0.018), -d * 0.5 + 0.018, 0.13 + (h - 0.13) * 0.5), "dark", bevel=0.016, segments=1)

    # Upper Control Console Band (`z = 0.94..1.16m`) — Detergent Tray + Glowing Status Buttons + Coin Slot + Brand Logo
    b.box((w - 0.08, 0.044, 0.22), (0, -d * 0.5 - 0.006, 1.03), "dark", bevel=0.016, segments=2)
    b.box((w - 0.14, 0.030, 0.17), (0, -d * 0.5 - 0.016, 1.03), accent_role, bevel=0.012, segments=1)
    # Left Detergent Pull-Drawer + Right Dial & Cute Glowing Dots
    b.box((0.20, 0.028, 0.11), (-0.28, -d * 0.5 - 0.026, 1.03), "light", bevel=0.008, segments=1)
    b.box((0.11, 0.016, 0.022), (-0.28, -d * 0.5 - 0.042, 1.03), "gold", bevel=0.005, segments=1)
    b.cyl(0.046, 0.032, (0.28, -d * 0.5 - 0.030, 1.03), "gold", axis="Y", segments=14, bevel=0.008)
    for ki, bx in enumerate((0.14, 0.19, 0.24)):
        b.sphere(0.015, (bx - 0.02, -d * 0.5 - 0.034, 1.075), "glow" if ki == 0 else "trim", u=7, v=5)
    if p.get("use_logo", True) and b.logo:
        b.banner_decal(0.28, (-0.01, -d * 0.5 - 0.034, 1.03), rot=(math.pi / 2, 0, 0))

    # 2. Iconic Round Espresso-Cocoa & Gold Porthole Frame (`z = 0.54m`) + Deep Recessed Drum Cavity
    dz = 0.54
    b.cyl(0.32, 0.06, (0, -d * 0.5 + 0.02, dz), "dark", axis="Y", segments=22, bevel=0.010)
    b.torus(0.315, 0.044, (0, -d * 0.5 - 0.024, dz), "dark", axis="Y", seg_major=24, seg_minor=7)
    b.torus(0.315, 0.024, (0, -d * 0.5 - 0.050, dz), accent_role, axis="Y", seg_major=24, seg_minor=6)
    b.box((0.046, 0.040, 0.13), (0.315, -d * 0.5 - 0.046, dz), "gold", bevel=0.010, segments=1)  # Door latch!

    # Fluffy Cloud Cushion Top + Cute Laundry Detergent Box
    b.slime_cap_mb(w, d, h + 0.002, role="light", cap_thick=0.055, res=0.028, target_tris=800)
    b.box((0.20, 0.14, 0.24), (-0.28, 0.06, h + 0.16), "trim", bevel=0.018, segments=1, rot=(0, 0, 0.18))
    b.box((0.14, 0.02, 0.12), (-0.28, -0.01, h + 0.16), "light", bevel=0.006, segments=1, rot=(0, 0, 0.18))

    # 3. Animated Spinning Inner Drum with Swirling Cash, Gold Coins & Bubbles (`drum`), Sitting Mascot (`crown`), Floating Bubbles (`orbit`)
    if b.animate:
        b.define_bone("drum", (0.0, -d * 0.5 - 0.01, dz), parent="root")
        b.define_bone("crown", (0.12, 0.0, h + 0.22), parent="root")
        b.define_bone("orbit", (0.0, 0.0, h + 0.10), parent="root")

    with b.use_bone("drum"):
        # Inner backlit pastel sky-blue bubbly soapy water disc + swirling folded banknotes, gold coins & soap bubbles!
        b.cyl(0.268, 0.018, (0, -d * 0.5 - 0.016, dz), "screen", axis="Y", segments=22)
        for k in range(4):
            a = k * math.pi * 0.5
            bx = 0.145 * math.cos(a)
            bz = dz + 0.145 * math.sin(a)
            bm = trs((bx, -d * 0.5 - 0.032, bz), (0.0, a + 0.35, 0.0))
            b.box((0.125, 0.022, 0.066), (0, 0, 0), "gold" if k % 2 == 0 else "glow", bevel=0.008, segments=1, M=bm)
            b.box((0.028, 0.026, 0.070), (0, 0, 0), "light", bevel=0.004, segments=1, M=bm)
        for k in range(6):
            a = k * math.tau / 6.0 + 0.4
            rr = 0.08 + (0.12 if k % 2 == 0 else 0.03)
            b.sphere(0.038 if k % 2 == 0 else 0.028, (rr * math.cos(a), -d * 0.5 - 0.042, dz + rr * math.sin(a)), "light" if k % 3 != 0 else "trim", u=10, v=7)

    with b.use_bone("crown"):
        b.mascot((0.12, 0.0, h + 0.24), 0.185, role="primary", eye_role="light", drips=False)

    with b.use_bone("orbit"):
        for bx, by, bz, br, brole in (
            (-0.56, -0.22, 1.24, 0.055, "light"),
            ( 0.56, -0.20, 1.32, 0.048, "trim"),
            ( 0.48,  0.22, 1.48, 0.042, "light"),
            (-0.46,  0.26, 1.42, 0.046, "gold"),
        ):
            b.sphere(br, (bx, by, bz), brole, u=8, v=6)
        b.star((-0.52, -0.26, 1.46), 0.046, "gold", crossed=True)
        b.star(( 0.54, -0.24, 1.12), 0.042, "gold", crossed=True)

    if b.animate:
        b.set_anim(frames=121, fps=30, tracks={
            "drum": {"kind": "drum_spin", "spin_deg": 360.0},
            "crown": {"kind": "mascot_nod", "amp_z": 0.030, "rock_y": 6.0},
            "orbit": {"kind": "marker_orbit", "amp_z": 0.055, "spin_deg": -360.0, "tilt_x": 4.0},
        })


ARCHETYPES = {
    "sign_post": build_sign_post,
    "kiosk_sign": build_kiosk_sign,
    "atm": build_atm,
    "safe": build_safe,
    "crate": build_crate,
    "chest": build_chest,
    "workbench": build_workbench,
    "mascot_marker": build_mascot_marker,
    "airdrop": build_airdrop,
    "powerbox": build_powerbox,
    "parking": build_parking,
    "redbox": build_redbox,
    "waterpipe": build_waterpipe,
    "gachapon": build_gachapon,
    "washmoney": build_washmoney,
}


def apply_and_join(b):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rigged = b.animate and len(b.bones) > 1
    for ob in b.parts:
        if ob.modifiers:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
            old = ob.data
            ob.modifiers.clear()
            ob.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
        if rigged:
            bname = ob.get("prop_forge_bone", "root")
            vg = ob.vertex_groups.get(bname) or ob.vertex_groups.new(name=bname)
            if ob.data.vertices:
                vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
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
    if not rigged:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
    bmesh.ops.dissolve_degenerate(bm, dist=0.00012, edges=bm.edges)
    tiny = [f for f in bm.faces if f.calc_area() < 1e-7]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    for f in bm.faces:
        f.smooth = True
    crease_rad = math.radians(50 if b.low_poly else 38)
    for e in bm.edges:
        if not e.is_manifold or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > crease_rad):
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
    glossy = bool(b.prop.get("glossy", b.spec.get("glossy", False)))
    rebuild_materials(b, root, roles, image, glossy=glossy)
    return path


def rebuild_materials(b, root, roles, image, glossy=False):
    diffuse = new_game_material(b.id + "_diffuse", image, emissive=False, glossy=glossy)
    emissive = None
    remap = []
    for role in roles:
        if role in EMISSIVE_ROLES:
            if emissive is None:
                emissive = new_game_material(b.id + "_emissive", image, emissive=True, glossy=False)
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


def new_game_material(name, image, emissive, glossy=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    tex.location = (-400, 200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.26 if glossy else 0.38
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.45 if glossy else 0.2
    if emissive:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
    mat["prop_forge_shader"] = "emissive.sps" if emissive else ("default_spec.sps" if glossy else "default.sps")
    if glossy and not emissive:
        mat["prop_forge_spec_int"] = 0.48
        mat["prop_forge_spec_falloff"] = 48.0
        mat["prop_forge_spec_fresnel"] = 0.88
    return mat


def _vinyl_toy_colors(role, hex_val):
    """Return hue-aware hyper-saturated linear (bot_rgba, top_rgba, rim_rgba) for hand-painted vinyl toy baking."""
    sr, sg, sb = hex_rgb(hex_val)
    r, g, b = srgb_to_linear(sr), srgb_to_linear(sg), srgb_to_linear(sb)
    h, s, v = colorsys.rgb_to_hsv(sr, sg, sb)

    def _lin_hsv(hh, ss, vv):
        rr, gg, bb = colorsys.hsv_to_rgb(hh % 1.0, max(0.0, min(1.0, ss)), max(0.0, min(1.0, vv)))
        return (srgb_to_linear(rr), srgb_to_linear(gg), srgb_to_linear(bb), 1.0)

    if role == "gold":
        # Rich mango-amber shadow -> radiant collector gold -> sparkling pale-gold highlight
        bot = (min(1.0, r * 0.90), g * 0.34, 0.002, 1.0)
        top = (1.0, min(1.0, g * 1.02 + 0.02), 0.010, 1.0)
        rim = (1.0, 0.93, 0.16, 1.0)
    elif role == "light":
        bot = (r * 0.74, g * 0.77, b * 0.86, 1.0)
        top = (1.0, 1.0, 1.0, 1.0)
        rim = (1.0, 1.0, 1.0, 1.0)
    elif role == "dark":
        # Sculpted crimson-obsidian graphite (crisp visible bevels, never flat muddy black!)
        bot = (r * 0.45, g * 0.40, b * 0.48, 1.0)
        top = (min(1.0, r * 2.4 + 0.012), min(1.0, g * 2.1 + 0.009), min(1.0, b * 2.4 + 0.013), 1.0)
        rim = (min(1.0, r * 6.0 + 0.085), min(1.0, g * 5.2 + 0.068), min(1.0, b * 5.8 + 0.082), 1.0)
    elif role == "metal":
        bot = (r * 0.42, g * 0.46, b * 0.60, 1.0)
        top = (min(1.0, r * 1.12 + 0.06), min(1.0, g * 1.12 + 0.06), min(1.0, b * 1.16 + 0.08), 1.0)
        rim = (0.98, 0.99, 1.0, 1.0)
    elif role in ("primary", "accent", "trim"):
        if v < 0.58:
            # Deep saturated collector shell (e.g., EXTREME Blood-Crimson or Royal Purple)
            bot = _lin_hsv(h - 0.015, min(1.0, s * 1.06), max(0.08, v * 0.44))
            top = _lin_hsv(h, min(1.0, s * 1.03), min(0.92, v * 1.38))
            rim = _lin_hsv(h + 0.008, max(0.45, s * 0.76), min(1.0, v * 1.85 + 0.16))
        else:
            # Ultra-bright electric pop vinyl (e.g., Blazing Neon-Red, Acid-Lime, Electric Gold)
            # Slight warm shift in shadows keeps reds ruby, yellows mango, limes emerald!
            is_red = (h < 0.05 or h > 0.92)
            h_shift = -0.025 if (0.04 < h < 0.22) else (-0.010 if is_red else 0.020)
            bot = _lin_hsv(h + h_shift, min(1.0, s * 1.08), max(0.28, v * 0.54))
            top = _lin_hsv(h, min(1.0, s * 1.04), min(1.0, v * 1.02))
            rim = _lin_hsv(h + 0.004, max(0.74, s * 0.86) if is_red else max(0.32, s * 0.52), 1.0)
    else:
        bot = (r * 0.68, g * 0.68, b * 0.72, 1.0)
        top = (min(1.0, r * 1.06 + 0.02), min(1.0, g * 1.06 + 0.02), min(1.0, b * 1.06 + 0.02), 1.0)
        rim = (min(1.0, r + 0.16), min(1.0, g + 0.16), min(1.0, b + 0.18), 1.0)
    return bot, top, rim


def bake_finish(b, root, out_dir, size, ao_strength=0.34, ao_dist=0.28):
    import numpy as np

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    roles = [slot.material.get("prop_forge_role", "primary") for slot in root.material_slots]
    me = root.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = root
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == root)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.012 if b.low_poly else 0.008, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    color_img = bpy.data.images.new(b.id + "_atlas", size, size, alpha=True)
    color_img.pixels.foreach_set(np.zeros(size * size * 4, dtype=np.float32))

    if b.style in ("vinyl_toy", "kawaii_billie"):
        # Stylized Hand-Painted Toy Cycles Baker (Comic Ink for vinyl_toy; Soft Cozy Espresso-Cocoa Cream for kawaii_billie!)
        scene.cycles.samples = 16
        is_kb = (b.style == "kawaii_billie")
        ink_col = (0.044, 0.022, 0.013, 1.0) if is_kb else (0.007, 0.002, 0.004, 1.0)
        for slot, role in zip(root.material_slots, roles):
            nt = slot.material.node_tree
            nt.nodes.clear()
            out_n = nt.nodes.new("ShaderNodeOutputMaterial")
            emit = nt.nodes.new("ShaderNodeEmission")
            tex_n = nt.nodes.new("ShaderNodeTexImage")
            tex_n.image = color_img
            nt.nodes.active = tex_n
            hex_val = b.palette.get(role, "#FF00FF")
            if role in EMISSIVE_ROLES:
                sr, sg, sb = hex_rgb(hex_val)
                emit.inputs["Color"].default_value = (srgb_to_linear(sr), srgb_to_linear(sg), srgb_to_linear(sb), 1.0)
            else:
                if is_kb:
                    sr, sg, sb = hex_rgb(hex_val)
                    r0, g0, b0 = srgb_to_linear(sr), srgb_to_linear(sg), srgb_to_linear(sb)
                    if role == "light":
                        # Creamy Warm Milk-Cream `#FFFBF4` — never bluish or muddy!
                        bot = (r0 * 0.86, g0 * 0.80, b0 * 0.74, 1.0)
                        top = (min(1.0, r0 * 1.01), min(1.0, g0 * 1.00), min(1.0, b0 * 0.99), 1.0)
                        rim = (1.0, 0.992, 0.970, 1.0)
                    elif role == "dark":
                        # Rich Warm Espresso Cocoa `#3B281E` with sculpted bevel highlights!
                        bot = (r0 * 0.58, g0 * 0.52, b0 * 0.48, 1.0)
                        top = (min(1.0, r0 * 1.45), min(1.0, g0 * 1.38), min(1.0, b0 * 1.32), 1.0)
                        rim = (min(1.0, r0 * 2.4 + 0.04), min(1.0, g0 * 2.1 + 0.03), min(1.0, b0 * 1.9 + 0.02), 1.0)
                    elif role == "gold":
                        bot = (min(1.0, r0 * 0.82), g0 * 0.52, b0 * 0.22, 1.0)
                        top = (1.0, min(1.0, g0 * 1.05 + 0.02), min(1.0, b0 * 1.05 + 0.01), 1.0)
                        rim = (1.0, 0.96, 0.48, 1.0)
                    else:
                        # Soft cozy plush pastel-caramel vertical warmth!
                        bot = (r0 * 0.72, g0 * 0.65, b0 * 0.60, 1.0)
                        top = (min(1.0, r0 * 1.08 + 0.01), min(1.0, g0 * 1.07 + 0.01), min(1.0, b0 * 1.06 + 0.01), 1.0)
                        rim = (min(1.0, r0 * 1.28 + 0.08), min(1.0, g0 * 1.26 + 0.07), min(1.0, b0 * 1.24 + 0.06), 1.0)
                else:
                    bot, top, rim = _vinyl_toy_colors(role, hex_val)
                tc = nt.nodes.new("ShaderNodeTexCoord")
                sep = nt.nodes.new("ShaderNodeSeparateXYZ")
                nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
                # Vertical rich gradient
                mr_z = nt.nodes.new("ShaderNodeMapRange")
                mr_z.clamp = True
                mr_z.inputs["From Min"].default_value = 0.05
                mr_z.inputs["From Max"].default_value = 0.92
                nt.links.new(sep.outputs["Z"], mr_z.inputs["Value"])
                mix_grad = nt.nodes.new("ShaderNodeMix")
                mix_grad.data_type = "RGBA"
                mix_grad.clamp_result = True
                mix_grad.inputs[6].default_value = bot
                mix_grad.inputs[7].default_value = top
                nt.links.new(mr_z.outputs["Result"], mix_grad.inputs[0])
                # Painted top-front glossy vinyl sheen (Normal dot key light)
                geom = nt.nodes.new("ShaderNodeNewGeometry")
                vdot = nt.nodes.new("ShaderNodeVectorMath")
                vdot.operation = "DOT_PRODUCT"
                vdot.inputs[1].default_value = (-0.30, -0.58, 0.75)
                nt.links.new(geom.outputs["Normal"], vdot.inputs[0])
                mr_gloss = nt.nodes.new("ShaderNodeMapRange")
                mr_gloss.clamp = True
                mr_gloss.inputs["From Min"].default_value = 0.62
                mr_gloss.inputs["From Max"].default_value = 0.98
                mr_gloss.inputs["To Min"].default_value = 0.0
                mr_gloss.inputs["To Max"].default_value = (0.18 if is_kb else 0.24) if role in ("accent", "gold", "primary", "trim") else 0.14
                nt.links.new(vdot.outputs["Value"], mr_gloss.inputs["Value"])
                mix_gloss = nt.nodes.new("ShaderNodeMix")
                mix_gloss.data_type = "RGBA"
                mix_gloss.clamp_result = True
                mix_gloss.inputs[7].default_value = rim
                nt.links.new(mr_gloss.outputs["Result"], mix_gloss.inputs[0])
                nt.links.new(mix_grad.outputs[2], mix_gloss.inputs[6])
                # Convex Pointiness painted cartoon rim-light pop
                mr_rim = nt.nodes.new("ShaderNodeMapRange")
                mr_rim.clamp = True
                mr_rim.inputs["From Min"].default_value = 0.522
                mr_rim.inputs["From Max"].default_value = 0.585
                mr_rim.inputs["To Min"].default_value = 0.0
                mr_rim.inputs["To Max"].default_value = (0.15 if is_kb else 0.20) if role != "dark" else 0.12
                nt.links.new(geom.outputs["Pointiness"], mr_rim.inputs["Value"])
                mix_rim = nt.nodes.new("ShaderNodeMix")
                mix_rim.data_type = "RGBA"
                mix_rim.clamp_result = True
                mix_rim.inputs[7].default_value = rim
                nt.links.new(mr_rim.outputs["Result"], mix_rim.inputs[0])
                nt.links.new(mix_gloss.outputs[2], mix_rim.inputs[6])
                # Crisp Comic Ink / Soft Espresso-Cocoa Crevice AO
                ao_n = nt.nodes.new("ShaderNodeAmbientOcclusion")
                ao_n.samples = 16
                ao_n.inputs["Distance"].default_value = 0.18 if is_kb else 0.22
                mr_ao = nt.nodes.new("ShaderNodeMapRange")
                mr_ao.clamp = True
                mr_ao.inputs["From Min"].default_value = 0.18
                mr_ao.inputs["From Max"].default_value = 0.85
                mr_ao.inputs["To Min"].default_value = (0.42 if is_kb else 0.80) if role != "dark" else (0.24 if is_kb else 0.42)
                mr_ao.inputs["To Max"].default_value = 0.0
                nt.links.new(ao_n.outputs["AO"], mr_ao.inputs["Value"])
                mr_crev = nt.nodes.new("ShaderNodeMapRange")
                mr_crev.clamp = True
                mr_crev.inputs["From Min"].default_value = 0.435
                mr_crev.inputs["From Max"].default_value = 0.488
                mr_crev.inputs["To Min"].default_value = (0.28 if is_kb else 0.58) if role != "dark" else 0.16
                mr_crev.inputs["To Max"].default_value = 0.0
                nt.links.new(geom.outputs["Pointiness"], mr_crev.inputs["Value"])
                ink_max = nt.nodes.new("ShaderNodeMath")
                ink_max.operation = "MAXIMUM"
                ink_max.use_clamp = True
                nt.links.new(mr_ao.outputs["Result"], ink_max.inputs[0])
                nt.links.new(mr_crev.outputs["Result"], ink_max.inputs[1])
                mix_ink = nt.nodes.new("ShaderNodeMix")
                mix_ink.data_type = "RGBA"
                mix_ink.clamp_result = True
                mix_ink.inputs[7].default_value = ink_col
                nt.links.new(ink_max.outputs["Value"], mix_ink.inputs[0])
                nt.links.new(mix_rim.outputs[2], mix_ink.inputs[6])
                nt.links.new(mix_ink.outputs[2], emit.inputs["Color"])
            nt.links.new(emit.outputs["Emission"], out_n.inputs["Surface"])
        scene.render.bake.margin = 16
        bpy.ops.object.bake(type="EMIT", margin=16, use_clear=True)
    else:
        scene.cycles.samples = 1
        for slot in root.material_slots:
            nt = slot.material.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            if bsdf and "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = 0.0
            node = nt.nodes.new("ShaderNodeTexImage")
            node.image = color_img
            nt.nodes.active = node
        scene.render.bake.use_pass_direct = False
        scene.render.bake.use_pass_indirect = False
        scene.render.bake.use_pass_color = True
        scene.render.bake.margin = 8
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8, use_clear=True)
        if ao_strength > 0:
            ao_img = bpy.data.images.new(b.id + "_ao_tmp", size, size, alpha=False)
            scene.cycles.samples = 16
            for slot, role in zip(root.material_slots, roles):
                nt = slot.material.node_tree
                out_n = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
                emit = nt.nodes.new("ShaderNodeEmission")
                if role in EMISSIVE_ROLES:
                    emit.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
                else:
                    ao_n = nt.nodes.new("ShaderNodeAmbientOcclusion")
                    ao_n.samples = 16
                    ao_n.inputs["Distance"].default_value = ao_dist
                    nt.links.new(ao_n.outputs["AO"], emit.inputs["Color"])
                if out_n:
                    nt.links.new(emit.outputs["Emission"], out_n.inputs["Surface"])
                tex_n = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
                if tex_n:
                    tex_n.image = ao_img
                    nt.nodes.active = tex_n
            bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
            n_px = size * size * 4
            c_buf = np.empty(n_px, dtype=np.float32)
            a_buf = np.empty(n_px, dtype=np.float32)
            color_img.pixels.foreach_get(c_buf)
            ao_img.pixels.foreach_get(a_buf)
            c_arr = c_buf.reshape((size, size, 4))
            a_arr = a_buf.reshape((size, size, 4))[:, :, 0:1]
            shade = (1.0 - ao_strength) + ao_strength * np.power(np.clip(a_arr, 0.0, 1.0), 1.15)
            c_arr[:, :, :3] = np.clip(c_arr[:, :, :3] * shade, 0.0, 1.0)
            color_img.pixels.foreach_set(c_arr.ravel())
            bpy.data.images.remove(ao_img)
    # Flood-fill bleed nearest UV island color into all unbaked background pixels (ZERO black seam bleed at any mip level!)
    px_buf = np.empty(size * size * 4, dtype=np.float32)
    color_img.pixels.foreach_get(px_buf)
    px = px_buf.reshape((size, size, 4))
    valid = (px[..., 3] > 0.5) & (px[..., :3].max(axis=-1) > 0.002)
    if valid.any() and not valid.all():
        rgb = px[..., :3]
        for _ in range(max(24, size // 8)):
            if valid.all():
                break
            acc = np.zeros_like(rgb)
            cnt = np.zeros(valid.shape, dtype=np.float32)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                sr = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                sv = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
                if dy == -1:
                    sv[-1, :] = False
                elif dy == 1:
                    sv[0, :] = False
                if dx == -1:
                    sv[:, -1] = False
                elif dx == 1:
                    sv[:, 0] = False
                m = sv.astype(np.float32)
                acc += sr * m[..., None]
                cnt += m
            fill = (~valid) & (cnt > 0)
            if not fill.any():
                break
            rgb[fill] = acc[fill] / cnt[fill, None]
            valid[fill] = True
        px[..., :3] = rgb
    px[..., 3] = 1.0
    color_img.pixels.foreach_set(px.ravel())
    color_img.alpha_mode = "NONE"
    path = os.path.join(out_dir, b.id + "_atlas.png")
    color_img.filepath_raw = path
    color_img.file_format = "PNG"
    color_img.save()
    glossy = bool(b.prop.get("glossy", b.spec.get("glossy", True)))
    rebuild_materials(b, root, roles, color_img, glossy=glossy)
    for mat in root.data.materials:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.interpolation = "Linear"
    return path


def add_decals(b, root, decals, spec_dir, shift=None):
    lo, hi = bbox(root)
    shift_m = Matrix.Translation(shift) if shift is not None else Matrix.Identity(4)
    entries = []
    for dec in b.pending_decals:
        entries.append({
            "image": dec["image"],
            "width": dec["width"],
            "height": dec.get("height"),
            "matrix": shift_m @ dec["matrix"],
            "shader": dec.get("shader", "decal.sps"),
            "bone": dec.get("bone", "root"),
        })
    for dec in (decals or []):
        side = dec.get("side", "front")
        cu, cz = dec.get("center", [0.0, (lo.z + hi.z) / 2])
        gap = dec.get("offset", 0.004)
        place = {
            "front": ((cu, dec.get("y", lo.y) - gap, cz), (math.pi / 2, 0, 0)),
            "back": ((cu, dec.get("y", hi.y) + gap, cz), (math.pi / 2, 0, math.pi)),
            "left": ((dec.get("x", lo.x) - gap, cu, cz), (math.pi / 2, 0, -math.pi / 2)),
            "right": ((dec.get("x", hi.x) + gap, cu, cz), (math.pi / 2, 0, math.pi / 2)),
            "top": ((cu, cz, dec.get("z", hi.z) + gap), (0, 0, 0)),
        }[side]
        entries.append({
            "image": dec["image"],
            "width": dec.get("width", 0.4),
            "height": dec.get("height"),
            "matrix": trs(place[0], place[1]),
            "shader": dec.get("shader", "decal.sps"),
        })
    if not entries:
        return
    made = []
    mat_cache = {}
    for i, dec in enumerate(entries):
        img_path = dec["image"] if os.path.isabs(dec["image"]) else os.path.join(spec_dir, dec["image"])
        if not os.path.exists(img_path):
            b.warnings.append("decal image missing: " + img_path)
            continue
        image = bpy.data.images.load(img_path, check_existing=True)
        aspect = image.size[1] / max(1, image.size[0])
        width = dec["width"]
        height = dec["height"] if dec["height"] else width * aspect
        shader = dec["shader"]
        key = (os.path.abspath(img_path).lower(), shader)
        mat = mat_cache.get(key)
        if mat is None:
            mat_name = "{}_decal_{}".format(b.id, len(mat_cache))
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            nt = mat.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = image
            tex.extension = "CLIP"
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
            bsdf.inputs["Roughness"].default_value = 0.32
            if "emissive" in shader:
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = 1.6
            try:
                mat.blend_method = "BLEND"
            except Exception:
                pass
            mat["prop_forge_shader"] = shader
            mat_cache[key] = mat
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(width, height, 1), verts=bm.verts)
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for loop in f.loops:
                loop[uv].uv = (loop.vert.co.x / width + 0.5, loop.vert.co.y / height + 0.5)
        me = bpy.data.meshes.new("{}_decal_mesh_{}".format(b.id, i))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = dec["matrix"]
        me.materials.append(mat)
        if b.animate and len(b.bones) > 1:
            bname = dec.get("bone", "root")
            vg = ob.vertex_groups.get(bname) or ob.vertex_groups.new(name=bname)
            vg.add(list(range(len(me.vertices))), 1.0, "REPLACE")
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


def _smoothstep(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def eval_anim_track(track, u):
    """Evaluate bone pose delta (loc Vector, rot Euler XYZ) at normalized phase u in [0, 1]."""
    kind = track.get("kind", "")
    loc = Vector((0.0, 0.0, 0.0))
    rx = ry = rz = 0.0

    if kind == "safe_wheel":
        deg = float(track.get("spin_deg", 360.0))
        if u < 0.08:
            ang = 0.0
        elif u < 0.24:
            ang = deg * _smoothstep(0.08, 0.24, u)
        elif u < 0.82:
            ang = deg
        elif u < 0.96:
            ang = deg * (1.0 - _smoothstep(0.82, 0.96, u))
        else:
            ang = 0.0
        ry = math.radians(ang)

    elif kind == "safe_door":
        deg = float(track.get("open_deg", -104.0))
        if u < 0.24:
            ang = 0.0
        elif u < 0.42:
            ang = deg * _smoothstep(0.24, 0.42, u)
        elif u < 0.66:
            ang = deg
        elif u < 0.82:
            ang = deg * (1.0 - _smoothstep(0.66, 0.82, u))
        else:
            ang = 0.0
        rz = math.radians(ang)

    elif kind == "marker_spin":
        amp_z = float(track.get("amp_z", 0.14))
        spin_deg = float(track.get("spin_deg", 360.0))
        tilt_x = float(track.get("tilt_x", 5.5))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau))
        rx = math.radians(tilt_x * math.sin(u * math.tau))
        ry = math.radians(tilt_x * 0.65 * math.sin(u * math.tau * 2.0))
        rz = math.radians(spin_deg * u)

    elif kind == "marker_orbit":
        amp_z = float(track.get("amp_z", 0.08))
        spin_deg = float(track.get("spin_deg", -360.0))
        tilt_x = float(track.get("tilt_x", 7.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        rx = math.radians(tilt_x * math.sin(u * math.tau))
        rz = math.radians(spin_deg * u)

    elif kind == "chest_lid":
        close_deg = float(track.get("close_deg", 26.0))
        wide_deg = float(track.get("wide_deg", -12.0))
        if u < 0.24:
            ang = close_deg * _smoothstep(0.0, 0.24, u)
        elif u < 0.36:
            ang = close_deg
        elif u < 0.58:
            t = _smoothstep(0.36, 0.58, u)
            ang = close_deg * (1.0 - t) + wide_deg * t
        elif u < 0.74:
            t = _smoothstep(0.58, 0.74, u)
            ang = wide_deg * (1.0 - t) + 3.0 * math.sin(t * math.pi)
        else:
            ang = 0.0
        rx = math.radians(ang)

    elif kind == "chest_coins":
        amp_z = float(track.get("amp_z", 0.12))
        spin_deg = float(track.get("spin_deg", 360.0))
        if u < 0.24:
            dz = -0.07 * _smoothstep(0.0, 0.24, u)
        elif u < 0.36:
            dz = -0.07
        elif u < 0.60:
            t = _smoothstep(0.36, 0.60, u)
            dz = -0.07 * (1.0 - t) + amp_z * t
        elif u < 0.86:
            t = (u - 0.60) / 0.26
            dz = amp_z * (1.0 - 0.45 * t) + 0.02 * math.sin(t * math.tau)
        else:
            t = _smoothstep(0.86, 1.0, u)
            dz = amp_z * 0.55 * (1.0 - t)
        loc.z = dz
        rz = math.radians(spin_deg * u)

    elif kind == "crown_hover":
        amp_z = float(track.get("amp_z", 0.065))
        rock_y = float(track.get("rock_y", 8.0))
        twist_z = float(track.get("twist_z", 15.0))
        lift = 0.5 * (1.0 - math.cos(u * math.tau))
        loc.z = amp_z * lift
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rz = math.radians(twist_z * math.sin(u * math.tau))

    elif kind == "airdrop_gyro":
        spin_deg = float(track.get("spin_deg", -360.0))
        wobble_deg = float(track.get("wobble_deg", 18.0))
        rx = math.radians(wobble_deg * math.sin(u * math.tau))
        ry = math.radians(wobble_deg * 0.7 * math.sin(u * math.tau * 2.0))
        rz = math.radians(spin_deg * u)

    elif kind == "breaker_flip":
        flip_deg = float(track.get("flip_deg", 56.0))
        t0 = float(track.get("t0", 0.10))
        t1 = float(track.get("t1", 0.50))
        span = max(0.08, t1 - t0)
        if u <= t0 or u >= t1:
            ang = 0.0
        else:
            p = (u - t0) / span
            if p < 0.28:
                ang = flip_deg * _smoothstep(0.0, 0.28, p)
            elif p < 0.68:
                ang = flip_deg
            else:
                ang = flip_deg * (1.0 - _smoothstep(0.68, 1.0, p))
        rx = math.radians(ang)

    elif kind == "siren_spin":
        spin_deg = float(track.get("spin_deg", 720.0))
        amp_z = float(track.get("amp_z", 0.016))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 4.0))
        rz = math.radians(spin_deg * u)

    elif kind == "mascot_nod":
        amp_z = float(track.get("amp_z", 0.022))
        rock_y = float(track.get("rock_y", 6.5))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        ry = math.radians(rock_y * math.sin(u * math.tau))

    elif kind == "sign_sway":
        amp_z = float(track.get("amp_z", 0.016))
        rock_y = float(track.get("rock_y", 2.6))
        rock_x = float(track.get("rock_x", 1.2))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rx = math.radians(rock_x * math.sin(u * math.tau * 2.0))

    elif kind == "gate_lift":
        lift_deg = float(track.get("lift_deg", 62.0))
        sign = float(track.get("sign", -1.0))
        # Rest horizontal -> smooth lift UP (+Z) -> hold open -> gentle bounce -> smooth lower
        if u < 0.08:
            ang = 0.0
        elif u < 0.34:
            t = _smoothstep(0.08, 0.34, u)
            ang = lift_deg * t
        elif u < 0.66:
            p = (u - 0.34) / 0.32
            ang = lift_deg + 2.5 * math.sin(p * math.tau)
        elif u < 0.90:
            t = _smoothstep(0.66, 0.90, u)
            ang = lift_deg * (1.0 - t)
        else:
            ang = 0.0
        ry = sign * math.radians(ang)

    elif kind == "hook_swing":
        swing_deg = float(track.get("swing_deg", 22.0))
        ry = math.radians(swing_deg * math.sin(u * math.tau))
        rx = math.radians(swing_deg * 0.25 * math.sin(u * math.tau * 2.0))

    elif kind == "screen_wiggle":
        amp_z = float(track.get("amp_z", 0.005))
        rock_y = float(track.get("rock_y", 4.2))
        yaw_z = float(track.get("yaw_z", 5.5))
        nod_x = float(track.get("nod_x", 2.4))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        rx = math.radians(nod_x * math.sin(u * math.tau * 2.0))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rz = math.radians(yaw_z * math.sin(u * math.tau))

    elif kind == "face_eyes":
        amp_x = float(track.get("amp_x", 0.015))
        amp_z = float(track.get("amp_z", 0.005))
        tilt_y = float(track.get("tilt_y", 6.5))
        # Glance smoothly left -> right -> center with subtle playful brow tilt flush along screen plane
        dx = amp_x * math.sin(u * math.tau)
        dz = amp_z * math.sin(u * math.tau * 2.0)
        loc.x = dx
        loc.z = dz
        loc.y = dz * math.sin(-0.10) - dx * math.sin(-0.05)
        ry = math.radians(tilt_y * math.sin(u * math.tau * 2.0))

    elif kind == "face_mouth":
        amp_x = float(track.get("amp_x", 0.007))
        amp_z = float(track.get("amp_z", 0.005))
        tilt_y = float(track.get("tilt_y", 8.0))
        # Subtle grumble smirk & chatter wobble flush along screen plane
        dx = -amp_x * math.sin(u * math.tau)
        dz = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 3.0))
        loc.x = dx
        loc.z = dz
        loc.y = dz * math.sin(-0.10) - dx * math.sin(-0.05)
        ry = math.radians(tilt_y * math.sin(u * math.tau * 2.0 + 0.9))

    elif kind == "drawer_peek":
        pull_y = float(track.get("pull_y", -0.15))
        if u < 0.14:
            t = 0.0
        elif u < 0.36:
            t = _smoothstep(0.14, 0.36, u)
        elif u < 0.64:
            t = 1.0
        elif u < 0.86:
            t = 1.0 - _smoothstep(0.64, 0.86, u)
        else:
            t = 0.0
        loc.y = pull_y * t

    elif kind == "valve_spin":
        deg = float(track.get("spin_deg", 360.0))
        if u < 0.10:
            ang = 0.0
        elif u < 0.42:
            ang = deg * _smoothstep(0.10, 0.42, u)
        elif u < 0.58:
            ang = deg
        elif u < 0.90:
            ang = deg * (1.0 - _smoothstep(0.58, 0.90, u))
        else:
            ang = 0.0
        ry = math.radians(ang)

    elif kind == "crank_turn":
        deg = float(track.get("spin_deg", 360.0))
        if u < 0.12:
            ang = 0.0
        elif u < 0.52:
            ang = deg * _smoothstep(0.12, 0.52, u)
        else:
            ang = deg
        ry = math.radians(ang)

    elif kind == "drum_spin":
        deg = float(track.get("spin_deg", 360.0))
        ry = math.radians(deg * u)

    return loc, Euler((rx, ry, rz), "XYZ").to_quaternion()


def build_rig_and_action(b, root, shift):
    """Build Blender Armature `<id>_rig`, bind via ARMATURE modifier, and bake smooth Action."""
    if not (b.animate and b.anim_config and len(b.bones) > 1):
        return None
    fps = int(b.anim_config.get("fps", 30))
    frames = int(b.anim_config.get("frames", 121))
    tracks = b.anim_config.get("tracks", {})

    # Topological order: root first, then parents before children
    ordered = ["root"]
    remaining = [k for k in b.bones if k != "root"]
    while remaining:
        progressed = False
        for k in list(remaining):
            parent = b.bones[k].get("parent") or "root"
            if parent in ordered:
                ordered.append(k)
                remaining.remove(k)
                progressed = True
        if not progressed:
            ordered.extend(remaining)
            break

    arm_data = bpy.data.armatures.new(b.id + "_rig")
    rig = bpy.data.objects.new(b.id + "_rig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = (0.0, 0.0, 0.0)

    bpy.context.view_layer.objects.active = rig
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == rig)
    bpy.ops.object.mode_set(mode="EDIT")
    eb_map = {}
    for bname in ordered:
        info = b.bones[bname]
        eb = arm_data.edit_bones.new(bname)
        head = Vector((0.0, 0.0, 0.0)) if bname == "root" else (Vector(info["pivot"]) + shift)
        eb.head = head
        eb.tail = head + Vector((0.0, 0.05, 0.0))
        eb.roll = 0.0
        parent_name = info.get("parent")
        if parent_name and parent_name in eb_map:
            eb.parent = eb_map[parent_name]
        eb_map[bname] = eb
    bpy.ops.object.mode_set(mode="OBJECT")

    # Bind mesh to armature via modifier (keep root.parent is None so validate_prop passes cleanly)
    mod = root.modifiers.new("prop_forge_rig", "ARMATURE")
    mod.object = rig

    # Create Action with per-frame smooth keyframes on every bone
    rig.animation_data_create()
    action = bpy.data.actions.new(b.id + "_action")
    rig.animation_data.action = action
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"

    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames

    denom = max(1, frames - 1)
    for bname in ordered:
        pb = rig.pose.bones[bname]
        track = tracks.get(bname)
        data_loc = 'pose.bones["{}"].location'.format(bname)
        data_rot = 'pose.bones["{}"].rotation_quaternion'.format(bname)
        fcs_loc = [action.fcurves.new(data_loc, index=i, action_group=bname) for i in range(3)]
        fcs_rot = [action.fcurves.new(data_rot, index=i, action_group=bname) for i in range(4)]

        loc_vals = [[], [], []]
        rot_vals = [[], [], [], []]
        prev_q = Quaternion((1.0, 0.0, 0.0, 0.0))
        for f in range(frames):
            u = f / denom
            if track:
                loc, q = eval_anim_track(track, u)
            else:
                loc, q = Vector((0.0, 0.0, 0.0)), Quaternion((1.0, 0.0, 0.0, 0.0))
            if prev_q.dot(q) < 0.0:
                q = -q
            prev_q = q.copy()
            bf = float(f + 1)
            for i in range(3):
                loc_vals[i].extend((bf, loc[i]))
            for i in range(4):
                rot_vals[i].extend((bf, q[i]))

        for i in range(3):
            fcs_loc[i].keyframe_points.add(frames)
            fcs_loc[i].keyframe_points.foreach_set("co", loc_vals[i])
            fcs_loc[i].update()
        for i in range(4):
            fcs_rot[i].keyframe_points.add(frames)
            fcs_rot[i].keyframe_points.foreach_set("co", rot_vals[i])
            fcs_rot[i].update()

    scene.frame_set(1)
    return {
        "rig_name": rig.name,
        "action_name": action.name,
        "fps": fps,
        "frames": frames,
        "duration": round((frames - 1) / fps, 4),
        "bones": ordered,
        "auto_start": True,
    }


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
    b = PropBuilder(spec, prop, spec_dir=spec_dir)
    ARCHETYPES[archetype](b, prop)
    part_count = len(b.parts)
    root = apply_and_join(b)
    shift = recentre(root, archetype)
    if args.bake:
        texture = bake_finish(b, root, out_dir, args.bake)
    else:
        texture = palette_finish(b, root, out_dir)
    if b.pending_decals or prop.get("decals"):
        add_decals(b, root, prop.get("decals"), spec_dir, shift=shift)
    anim_meta = build_rig_and_action(b, root, shift)
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
    if anim_meta:
        meta["anim"] = anim_meta
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
        # Clear armature modifier in static lineup so moved mesh never lever-arms around origin rig
        for mod in list(ob.modifiers):
            if mod.type == "ARMATURE":
                ob.modifiers.remove(mod)
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
