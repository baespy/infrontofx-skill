import argparse
import importlib
import json
import math
import os
import random
import subprocess
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector


class EngineLoader:
    @staticmethod
    def folder(explicit=None):
        candidates = [explicit] if explicit else []
        here = globals().get("__file__")
        if here:
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(here)), ".."))
        candidates.append(os.environ.get("SCULPT_FORGE_SCRIPTS", ""))
        for path in candidates:
            if path and os.path.isfile(os.path.join(path, "sculpt_forge.py")):
                return os.path.normpath(os.path.abspath(path))
        raise RuntimeError("sculpt_forge.py not found: pass engine=<skill>/sculpt-forge/scripts/blender or set SCULPT_FORGE_SCRIPTS")

    @staticmethod
    def load(explicit=None):
        folder = EngineLoader.folder(explicit)
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module("sculpt_forge")


class ContainerMath:
    @staticmethod
    def extents(size):
        if np.isscalar(size):
            return float(size), float(size), float(size)
        return float(size[0]), float(size[1]), float(size[2])

    @staticmethod
    def at(loc, x=0.0, y=0.0, z=0.0):
        return (float(loc[0]) + float(x), float(loc[1]) + float(y), float(loc[2]) + float(z))

    @staticmethod
    def bolster_radius(seam_gap, groove):
        radius = max(seam_gap / 1.6, groove * 1.2)
        for _ in range(60):
            c = min(max(1.0 - groove / radius, -1.0), 1.0)
            radius = max(seam_gap / (1.0 + math.sqrt(max(0.0, 1.0 - c * c))), groove * 1.05)
        return radius

    @staticmethod
    def pillow_lift(offset, half, radius):
        inner = max(half - radius, 1e-5)
        t = min((offset / inner) ** 2, 1.0)
        return (1.0 - t) ** 2

    @staticmethod
    def stripe_centres(span, width):
        count = max(1, int((span + 0.5 * width) // (2.0 * width)))
        return [(k - 0.5 * (count - 1)) * 2.0 * width for k in range(count)]

    @staticmethod
    def hinge_matrix(deg):
        return Euler((math.radians(deg), 0.0, 0.0), "XYZ").to_matrix()

    @staticmethod
    def hinge_point(point, pivot, deg):
        out = ContainerMath.hinge_matrix(deg) @ (Vector(point) - Vector(pivot)) + Vector(pivot)
        return (out.x, out.y, out.z)

    @staticmethod
    def hinge_rot(deg, rot=(0.0, 0.0, 0.0)):
        m = ContainerMath.hinge_matrix(deg) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix()
        return tuple(math.degrees(a) for a in m.to_euler("XYZ"))

    @staticmethod
    def hinge_box(lo, hi, pivot, deg):
        corners = np.array([ContainerMath.hinge_point((x, y, z), pivot, deg) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        low = corners.min(axis=0)
        high = corners.max(axis=0)
        return tuple(((low + high) * 0.5).tolist()), tuple((high - low).tolist())

    @staticmethod
    def tilt_to(normal, spin=0.0):
        n = Vector(normal).normalized()
        m = Vector((0.0, 0.0, 1.0)).rotation_difference(n).to_matrix() @ Euler((0.0, 0.0, math.radians(spin)), "XYZ").to_matrix()
        return tuple(math.degrees(a) for a in m.to_euler("XYZ"))

    @staticmethod
    def arch(width, side, dome, corner, samples=40, drop=0.0):
        half = 0.5 * float(width)
        r = max(1e-3, min(float(corner), 0.45 * half, float(side)))
        pts = []
        for i in range(7):
            a = math.radians(-90.0 + 15.0 * i)
            pts.append((half - r + r * math.cos(a), r + r * math.sin(a)))
        for i in range(int(samples) + 1):
            t = math.pi * i / float(samples)
            pts.append((half * math.cos(t), float(side) + float(dome) * math.sin(t)))
        for i in range(7):
            a = math.radians(180.0 + 15.0 * i)
            pts.append((-half + r + r * math.cos(a), r + r * math.sin(a)))
        out = np.array(pts, np.float64)
        out[:, 1] -= float(drop)
        return out

    @staticmethod
    def keyhole(radius, samples=24):
        c = 0.7 * radius
        pts = []
        for i in range(int(samples) + 1):
            a = math.radians(-60.0 + 300.0 * i / float(samples))
            pts.append((radius * math.cos(a), c + radius * math.sin(a)))
        pts.append((-0.78 * radius, c - 2.4 * radius))
        pts.append((0.78 * radius, c - 2.4 * radius))
        return np.array(pts, np.float64)

    @staticmethod
    def tail(length, width, notch):
        return np.array([(0.0, -0.5 * width), (length, -0.5 * width), (length - notch, 0.0), (length, 0.5 * width), (0.0, 0.5 * width)], np.float64)

    @staticmethod
    def scatter(rng, count, rx, ry, spacing, fill=0.82, tries=4000):
        points = []
        for _ in range(int(tries)):
            if len(points) >= int(count):
                break
            u = rng.uniform(-1.0, 1.0)
            v = rng.uniform(-1.0, 1.0)
            if u * u + v * v > fill:
                continue
            p = (u * rx, v * ry)
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= spacing * spacing for q in points):
                points.append(p)
        return points

    @staticmethod
    def area_key(item):
        return item["area"]

    @staticmethod
    def components(count, first, second):
        labels = np.arange(count)
        if len(first) == 0:
            return labels
        for _ in range(1024):
            low = np.minimum(labels[first], labels[second])
            new = labels.copy()
            np.minimum.at(new, first, low)
            np.minimum.at(new, second, low)
            new = new[new]
            if np.array_equal(new, labels):
                break
            labels = new
        return labels

    @staticmethod
    def dome_point(x, y, radii):
        rx, ry, rz = radii
        s = max(0.0, 1.0 - (x / rx) ** 2 - (y / ry) ** 2)
        z = rz * math.sqrt(s)
        n = Vector((x / (rx * rx), y / (ry * ry), z / (rz * rz) if z > 1e-6 else 1e-6))
        return z, n.normalized()


class PanelHoldMixin:
    hold_reserve = 0.07
    hold_width = 0.014
    hold_min_area = 0.004
    hold_tilt = 4.0
    hold_coplanar = 3.0
    hold_spread = 2.0

    def reduce(self, high, owners):
        budget = self.budget
        self.budget = max(500, int(round(budget * (1.0 - self.hold_reserve))))
        try:
            low, report = super().reduce(high, owners)
        finally:
            self.budget = budget
        report["panel_hold"] = self.hold_panels(low.data)
        return low, report

    def panel_regions(self, bm):
        faces = list(bm.faces)
        normals = np.array([f.normal[:] for f in faces], np.float64).reshape(-1, 3)
        areas = np.array([f.calc_area() for f in faces], np.float64)
        mats = np.array([f.material_index for f in faces], np.int64)
        index = {f: i for i, f in enumerate(faces)}
        pairs = np.array([(index[e.link_faces[0]], index[e.link_faces[1]]) for e in bm.edges if len(e.link_faces) == 2], np.int64).reshape(-1, 2)
        dots = (normals[pairs[:, 0]] * normals[pairs[:, 1]]).sum(axis=1)
        keep = (dots > math.cos(math.radians(self.hold_coplanar))) & (mats[pairs[:, 0]] == mats[pairs[:, 1]])
        labels = ContainerMath.components(len(faces), pairs[keep, 0], pairs[keep, 1])
        floor = max(self.hold_min_area, 4.0 * float(np.median(areas)))
        regions = []
        for label in np.unique(labels):
            members = np.nonzero(labels == label)[0]
            area = float(areas[members].sum())
            if area < floor:
                continue
            mean = (normals[members] * areas[members, None]).sum(axis=0)
            mean /= max(float(np.linalg.norm(mean)), 1e-12)
            if float(np.degrees(np.arccos(np.clip(normals[members] @ mean, -1.0, 1.0))).max()) > self.hold_spread:
                continue
            regions.append({"faces": [faces[i] for i in members], "area": area, "normal": mean})
        return regions

    def hold_candidates(self, bm):
        picked = []
        for number, region in enumerate(self.panel_regions(bm)):
            members = set(region["faces"])
            rim = list({e for f in region["faces"] for e in f.edges if any(g not in members for g in e.link_faces)})
            verts = list({v for e in rim for v in e.verts})
            if not rim or not verts:
                continue
            co = np.array([v.co[:] for v in verts], np.float32)
            tilt = np.degrees(np.arccos(np.clip(self.probe_field.normals(co, self.voxel * 0.5) @ region["normal"].astype(np.float32), -1.0, 1.0)))
            if float(tilt.max()) < self.hold_tilt:
                continue
            perimeter = sum(e.calc_length() for e in rim)
            width = 2.0 * region["area"] / max(perimeter, 1e-9)
            thickness = min(self.hold_width, 0.2 * width)
            if thickness < 0.004 or min(e.calc_length() for e in rim) < 0.6 * thickness:
                continue
            region.update({"id": number, "rim": len(rim), "thickness": thickness})
            picked.append(region)
        picked.sort(key=ContainerMath.area_key, reverse=True)
        return picked

    def hold_attempt(self, me, skip):
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.normal_update()
        room = self.budget - sum(len(f.verts) - 2 for f in bm.faces)
        added = 0
        owners = {}
        for region in self.hold_candidates(bm):
            cost = 2 * region["rim"]
            if region["id"] in skip or added + cost > room or any(not f.is_valid for f in region["faces"]):
                continue
            before = set(bm.verts)
            bmesh.ops.inset_region(bm, faces=region["faces"], use_boundary=True, use_even_offset=True, use_interpolate=True, use_relative_offset=False, use_edge_rail=False, thickness=region["thickness"], depth=0.0, use_outset=False)
            for v in bm.verts:
                if v not in before:
                    owners[v] = region["id"]
            added += cost
        if not owners:
            bm.free()
            return {"panels": 0, "added_tris": 0}, set()
        fresh = list(owners)
        co = np.array([v.co[:] for v in fresh], np.float32)
        moved = self.probe_field.project(co, self.voxel * 0.5, 2, 4.0 * self.voxel)
        for v, p in zip(fresh, moved):
            v.co = p.tolist()
        big = [f for f in bm.faces if len(f.verts) > 3]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.normal_update()
        touched = list({f for v in fresh if v.is_valid for f in v.link_faces})
        areas = np.array([f.calc_area() for f in touched])
        agree = self.face_agreement(touched)
        bad = set()
        for f, area, dot in zip(touched, areas, agree):
            if area < 1e-7 or dot < 0.2:
                bad.update(owners[v] for v in f.verts if v in owners)
        if bad:
            bm.free()
            return None, bad
        bm.to_mesh(me)
        bm.free()
        me.update()
        return {"panels": len(set(owners.values())), "added_tris": int(added)}, set()

    def hold_panels(self, me):
        skip = set()
        for _ in range(5):
            result, bad = self.hold_attempt(me, skip)
            if result is not None:
                result["skipped"] = len(skip)
                return result
            skip |= bad
        return {"panels": 0, "added_tris": 0, "skipped": len(skip)}


class ContainersRecipes:
    colors = {
        "cream": ("#FFFBF4", "satin"),
        "caramel": ("#C48E62", "satin"),
        "ink": ("#3B281E", "matte"),
        "outline": ("#4A3327", "matte"),
        "honey": ("#E8B04B", "gloss"),
        "pink": ("#F2B8C6", "satin"),
        "mint": ("#A8D8C8", "satin"),
        "sky": ("#A9CBEA", "satin"),
        "gold": ("#D9A441", "gloss"),
    }
    themes = {
        "house": {"body": "cream", "trim": "caramel", "wood": "caramel", "ink": "ink", "line": "outline", "accent": "honey", "metal": "gold", "frost": "cream", "stripe": "caramel", "wrap": "cream", "ribbon": "caramel", "knot": "gold", "cherry": "honey", "sprinkles": ("honey", "gold", "caramel")},
        "pastel": {"body": "cream", "trim": "pink", "wood": "pink", "ink": "ink", "line": "outline", "accent": "honey", "metal": "gold", "frost": "cream", "stripe": "pink", "wrap": "pink", "ribbon": "mint", "knot": "gold", "cherry": "pink", "sprinkles": ("pink", "mint", "sky")},
    }

    def __init__(self, theme="house", roles=None, seed=7):
        self.theme = dict(self.themes.get(theme, self.themes["house"]))
        self.theme.update(roles or {})
        self.seed = int(seed)

    def slots(self, roles=None):
        out = dict(self.theme)
        out.update(roles or {})
        return out

    def palette(self, cell_px=32):
        return {"cell_px": int(cell_px), "roles": {name: {"color": spec[0], "finish": spec[1]} for name, spec in self.colors.items()}}

    @staticmethod
    def builder_class(sf, hold=True):
        if not hold:
            return sf.SculptBuilder
        return type("ContainerSculptBuilder", (PanelHoldMixin, sf.SculptBuilder), {})

    @staticmethod
    def suggest_budget(size, density=600.0, extra=0.2, minimum=1500):
        w, d, h = ContainerMath.extents(size)
        area = 2.0 * (w * d + w * h + d * h) * (1.0 + float(extra))
        return max(int(minimum), int(round(area * float(density) / 100.0)) * 100)

    @staticmethod
    def add_collider(b, center, size, store):
        b.collider(center, size)
        store.append((tuple(float(v) for v in center), tuple(float(v) for v in size)))

    @staticmethod
    def conformal(b, hosts, cutter, role, rim=0.006, join=0.005, name="conformal"):
        with b.group(name, fillet=join) as node:
            for kind, args in hosts:
                getattr(b, kind)(role=role, **args)
            kind, args = cutter
            getattr(b, kind)(role=role, op="intersect", fillet=rim, **args)
        return node

    @staticmethod
    def pillow_host(size, radius, bulge, loc, rise):
        return ("pillow_box", {"size": tuple(v + 2.0 * rise for v in size), "radius": radius + rise, "puff": (bulge, bulge, bulge), "loc": loc})

    def padded_cube(self, b, size=0.9, puff=0.06, seam=0.22, groove=0.012, crease=0.016, spread=0.5, tag=True, patch="star", roles=None, loc=(0.0, 0.0, 0.0)):
        r = self.slots(roles)
        w, d, h = ContainerMath.extents(size)
        hx, hy, hz = 0.5 * w, 0.5 * d, 0.5 * h
        hmin = min(hx, hy, hz)
        rb = ContainerMath.bolster_radius(seam * hmin, groove)
        cx, cy, cz = ContainerMath.at(loc, 0.0, 0.0, hz)
        bulge = puff * 2.0 * hmin + groove
        ex, ey, ez = hx - rb, hy - rb, hz - rb
        core_r = max(groove * 1.5, spread * rb)
        parts = {"bolsters": [], "colliders": []}
        core_size = (2.0 * (hx - groove), 2.0 * (hy - groove), 2.0 * (hz - groove))
        with b.group("padded_cube") as root:
            with b.group("bolsters"):
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        parts["bolsters"].append(b.capsule((cx + sx * ex, cy + sy * ey, cz - ez), (cx + sx * ex, cy + sy * ey, cz + ez), rb, role=r["body"]))
                for sy in (-1.0, 1.0):
                    for sz in (-1.0, 1.0):
                        parts["bolsters"].append(b.capsule((cx - ex, cy + sy * ey, cz + sz * ez), (cx + ex, cy + sy * ey, cz + sz * ez), rb, role=r["body"]))
                for sx in (-1.0, 1.0):
                    for sz in (-1.0, 1.0):
                        parts["bolsters"].append(b.capsule((cx + sx * ex, cy - ey, cz + sz * ez), (cx + sx * ex, cy + ey, cz + sz * ez), rb, role=r["body"]))
            seam_gap = seam * hmin
            parts["core"] = b.pillow_box(core_size, radius=core_r, puff=(bulge, bulge, bulge), loc=(cx, cy, cz), role=r["body"], fillet=crease)
            if patch:
                disc = 0.14 * min(w, h)
                if patch == "heart":
                    icon = {"shape": "heart", "size": 1.25 * disc}
                else:
                    icon = {"shape": "star", "r_out": 0.68 * disc, "r_in": 0.36 * disc, "points": 5, "smooth": 3}
                parts["patch"] = self.conformal(b, [self.pillow_host(core_size, core_r, bulge, (cx, cy, cz), 0.012)], ("round_cyl", {"radius": disc, "height": 1.2 * hy, "edge": 0.0, "loc": (cx, cy - hy, cz), "rot": (90.0, 0.0, 0.0)}), r["trim"], rim=0.01, join=0.012, name="patch")
                parts["icon"] = self.conformal(b, [self.pillow_host(core_size, core_r, bulge, (cx, cy, cz), 0.026)], ("extrude2d", {"outline": icon, "depth": 1.2 * hy, "plane": "XZ", "loc": (cx, cy - hy, cz)}), r["accent"], rim=0.007, join=0.006, name="patch_icon")
            if tag:
                tx = cx + 0.45 * hx
                tz = cz + hz - seam_gap - 0.07
                label = {"shape": "rounded_rect", "w": 0.11, "h": 0.15, "r": 0.032}
                heart = {"shape": "heart", "size": 0.05}
                parts["tag"] = self.conformal(b, [self.pillow_host(core_size, core_r, bulge, (cx, cy, cz), 0.012)], ("extrude2d", {"outline": label, "depth": 1.2 * hy, "plane": "XZ", "loc": (tx, cy - hy, tz), "rot": (0.0, 7.0, 0.0)}), r["accent"], rim=0.006, join=0.008, name="tag")
                parts["tag_icon"] = self.conformal(b, [self.pillow_host(core_size, core_r, bulge, (cx, cy, cz), 0.021)], ("extrude2d", {"outline": heart, "depth": 1.2 * hy, "plane": "XZ", "loc": (tx + 0.002, cy - hy, tz - 0.01), "rot": (0.0, 7.0, 0.0)}), r["body"], rim=0.004, join=0.004, name="tag_icon")
            b.cut(point=(cx, cy, cz - hz + 0.006), fillet=0.008)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (cx, cy, cz), (w, d, h), parts["colliders"])
        parts["size"] = (w, d, h)
        return parts

    def striped_box(self, b, size=(0.95, 0.72, 0.72), radius=0.07, stripe=0.085, rise=0.007, skirt=0.07, frost=0.06, overhang=0.022, per_m=8.0, drop=0.08, drips=5, label="STASH", sprinkles=10, cherry=True, roles=None, loc=(0.0, 0.0, 0.0), seed=None):
        r = self.slots(roles)
        rng = random.Random(self.seed if seed is None else seed)
        w, d, h = ContainerMath.extents(size)
        x0, y0, z0 = ContainerMath.at(loc)
        rad = radius * min(w, d, h)
        body_h = h - 0.5 * skirt
        parts = {"stripes": [], "sprinkles": [], "colliders": []}
        with b.group("striped_box") as root:
            parts["skirt"] = b.round_box((w + 0.03, d + 0.03, skirt), radius=min(0.03, 0.45 * skirt), loc=(x0, y0, z0 + 0.5 * skirt), role=r["trim"])
            parts["body"] = b.round_box((w, d, body_h), radius=rad, loc=(x0, y0, z0 + 0.5 * skirt + 0.5 * body_h), role=r["body"], fillet=0.012)
            zs0 = z0 + skirt + 0.012
            zs1 = z0 + h - 0.03
            hs = zs1 - zs0
            zc = 0.5 * (zs0 + zs1)
            e = rise + 0.005
            edge = min(0.95 * e, 0.45 * stripe)
            with b.group("stripes", fillet=0.006):
                for c in ContainerMath.stripe_centres(w - 2.0 * rad, stripe):
                    for sy in (-1.0, 1.0):
                        parts["stripes"].append(b.round_box((stripe, 2.0 * e, hs), radius=edge, loc=(x0 + c, y0 + sy * (0.5 * d + rise - e), zc), role=r["stripe"]))
                for c in ContainerMath.stripe_centres(d - 2.0 * rad, stripe):
                    for sx in (-1.0, 1.0):
                        parts["stripes"].append(b.round_box((2.0 * e, stripe, hs), radius=edge, loc=(x0 + sx * (0.5 * w + rise - e), y0 + c, zc), role=r["stripe"]))
            cap_z = z0 + h + 0.15 * frost
            cap_r = 0.45 * frost
            cap_puff = 0.022
            with b.group("frosting", fillet=0.01):
                parts["frost_cap"] = b.pillow_box((w + 2.0 * overhang, d + 2.0 * overhang, frost), radius=cap_r, puff=(0.0, 0.0, cap_puff), loc=(x0, y0, cap_z), role=r["frost"])
                rim = {"shape": "rounded_rect", "w": w + 0.012, "h": d + 0.012, "r": rad + 0.006, "plane": "XY", "at": (x0, y0, z0 + h - 0.012)}
                parts["scallops"] = b.scallops(rim, drop=drop, thickness=0.036, per_m=per_m, role=r["frost"], fillet=0.012)
                if drips:
                    low = dict(rim)
                    low["at"] = (x0, y0, z0 + h - 0.75 * drop)
                    parts["drips"] = b.drips(low, int(drips), length=(0.07, 0.15), radius=(0.018, 0.026), seed=rng.randint(0, 9999), sink=0.0, role=r["frost"], fillet=0.01)
            top_z = cap_z + 0.5 * frost
            half_x = 0.5 * w + overhang
            half_y = 0.5 * d + overhang
            if sprinkles:
                tones = r["sprinkles"] if isinstance(r["sprinkles"], (list, tuple)) else (r["sprinkles"],)
                spots = ContainerMath.scatter(rng, int(sprinkles), 0.68 * half_x, 0.68 * half_y, 0.09, fill=0.9)
                for k, (sx, sy) in enumerate(spots):
                    if sx * sx + sy * sy < 0.11 * 0.11 and cherry:
                        continue
                    lift = cap_puff * ContainerMath.pillow_lift(abs(sx), half_x, cap_r) * ContainerMath.pillow_lift(abs(sy), half_y, cap_r)
                    zz = top_z + lift + 0.004
                    a = rng.uniform(0.0, math.pi)
                    dx = 0.022 * math.cos(a)
                    dy = 0.022 * math.sin(a)
                    parts["sprinkles"].append(b.capsule((x0 + sx - dx, y0 + sy - dy, zz), (x0 + sx + dx, y0 + sy + dy, zz), 0.011, role=tones[k % len(tones)], fillet=0.004))
            if cherry:
                cz = top_z + cap_puff + 0.042
                parts["cherry"] = b.sphere(0.05, loc=(x0, y0, cz), role=r["cherry"], fillet=0.012)
                parts["stem"] = b.tube([(x0, y0, cz + 0.035), (x0 + 0.012, y0, cz + 0.075), (x0 + 0.04, y0, cz + 0.1)], 0.011, ends=1.0, role=r["trim"], fillet=0.006)
            if label:
                ly = y0 - 0.5 * d - rise
                lz = z0 + skirt + 0.5 * (h - skirt - drop)
                plate_y = ly - 0.012
                parts["plaque"] = b.extrude2d({"shape": "rounded_rect", "w": 0.42, "h": 0.13, "r": 0.064}, 0.03, edge=0.012, puff=0.004, plane="XZ", loc=(x0, plate_y, lz), role=r["accent"], fillet=0.008)
                front = plate_y - 0.019
                parts["letters_outline"] = b.text(label, height=0.07, max_width=0.33, depth=0.012, puff=0.009, plane="XZ", loc=(x0, front + 0.002, lz), role=r["ink"], fillet=0.004)
                parts["letters"] = b.text(label, height=0.07, max_width=0.33, depth=0.02, puff=0.004, plane="XZ", loc=(x0, front - 0.009, lz), role=r["body"], fillet=0.003)
            b.cut(point=(x0, y0, z0 + 0.004), fillet=0.006)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (x0, y0, z0 + 0.5 * (h + frost)), (w + 2.0 * overhang, d + 2.0 * overhang, h + frost), parts["colliders"])
        parts["size"] = (w + 2.0 * overhang, d + 2.0 * overhang, top_z + cap_puff - z0)
        return parts

    def loot_chest(self, b, size=(0.9, 0.6, 0.48), radius=0.07, lid=0.24, open_deg=105.0, wall=0.045, bolster=0.04, straps=True, lock=True, coins=24, spill=7, stars=True, roles=None, loc=(0.0, 0.0, 0.0), seed=None):
        r = self.slots(roles)
        rng = random.Random(self.seed + 11 if seed is None else seed)
        w, d, h = ContainerMath.extents(size)
        x0, y0, z0 = ContainerMath.at(loc)
        rad = radius * min(w, d, h)
        top = z0 + h
        front = y0 - 0.5 * d
        pivot = (x0, y0 + 0.5 * d - 0.012, top)
        angle = -abs(float(open_deg))
        is_open = abs(angle) > 1.0
        lid_side = 0.05
        lid_dome = max(0.04, lid - lid_side)
        strap_x = (-0.3 * w, 0.3 * w) if straps else ()
        coin_r = 0.04
        coin_t = 0.014
        parts = {"coins": [], "straps": [], "colliders": []}
        with b.group("loot_chest") as root:
            with b.group("body"):
                parts["body"] = b.round_box((w, d, h), radius=rad, loc=(x0, y0, z0 + 0.5 * h), role=r["wood"])
                panel_w = 0.44 * w
                panel_h = 0.4 * h
                panel_z = z0 + 0.42 * h
                b.round_box((panel_w, 0.04, panel_h), radius=0.02, loc=(x0, front, panel_z), role=r["ink"], op="subtract", fillet=0.01)
                parts["panel"] = b.round_box((panel_w - 0.022, 0.034, panel_h - 0.022), radius=0.014, loc=(x0, front + 0.033, panel_z), role=r["body"], fillet=0.004)
                if is_open:
                    b.round_box((w - 2.0 * wall, d - 2.0 * wall, 0.3), radius=0.03, loc=(x0, y0, top - 0.12 + 0.15), role=r["wood"], op="subtract", fillet=0.012)
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    px = x0 + sx * (0.5 * w - 0.4 * bolster)
                    py = y0 + sy * (0.5 * d - 0.4 * bolster)
                    b.capsule((px, py, z0 + bolster), (px, py, top - 0.6 * bolster), bolster, role=r["body"], fillet=0.012)
            parts["rim"] = b.tube({"shape": "rounded_rect", "w": w + 0.004, "h": d + 0.004, "r": rad, "plane": "XY", "at": (x0, y0, top - 0.02)}, 0.022, role=r["body"], fillet=0.01)
            parts["base"] = b.tube({"shape": "rounded_rect", "w": w + 0.004, "h": d + 0.004, "r": rad, "plane": "XY", "at": (x0, y0, z0 + 0.03)}, 0.024, role=r["body"], fillet=0.01)
            for sx in strap_x:
                for sy in (-1.0, 1.0):
                    parts["straps"].append(b.round_box((0.07, 0.03, h - 0.09), radius=0.012, loc=(x0 + sx, y0 + sy * (0.5 * d - 0.006), z0 + 0.5 * h + 0.01), role=r["metal"], fillet=0.006))
            if stars:
                for sx in (-1.0, 1.0):
                    parts.setdefault("stars", []).append(b.extrude2d({"shape": "star", "r_out": 0.075, "r_in": 0.038, "points": 5, "smooth": 3}, 0.03, edge=0.011, puff=0.004, plane="YZ", loc=(x0 + sx * (0.5 * w + 0.004), y0, z0 + 0.5 * h), rot=(0.0, 0.0, 0.0 if sx < 0 else 180.0), role=r["metal"], fillet=0.006))
            if lock:
                lz = top - 0.11
                parts["lock"] = b.extrude2d({"shape": "heart", "size": 0.13}, 0.036, edge=0.012, puff=0.005, plane="XZ", loc=(x0, front - 0.014, lz), role=r["metal"], fillet=0.006)
                parts["shackle"] = b.torus(0.036, 0.011, loc=(x0, front - 0.012, lz + 0.068), rot=(90.0, 0.0, 0.0), role=r["metal"], fillet=0.005)
                b.extrude2d(ContainerMath.keyhole(0.013), 0.04, plane="XZ", loc=(x0, front - 0.036, lz + 0.006), role=r["ink"], op="subtract", fillet=0.003)
            if is_open:
                mound = (0.5 * w - wall - 0.004, 0.5 * d - wall - 0.004, 0.11)
                mound_c = (x0, y0, top - 0.05)
                parts["hoard"] = b.ellipsoid(mound, loc=mound_c, role=r["metal"], fillet=0.01)
                spots = ContainerMath.scatter(rng, int(coins), mound[0] * 0.92, mound[1] * 0.92, 2.1 * coin_r, fill=0.86)
                for sx, sy in spots:
                    dz, n = ContainerMath.dome_point(sx, sy, mound)
                    if mound_c[2] + dz < top - 0.01:
                        continue
                    tilt = Vector((n.x + rng.uniform(-0.25, 0.25), n.y + rng.uniform(-0.25, 0.25), n.z)).normalized()
                    c = (mound_c[0] + sx + tilt.x * 0.004, mound_c[1] + sy + tilt.y * 0.004, mound_c[2] + dz + 0.002)
                    parts["coins"].append(b.round_cyl(coin_r, coin_t, edge=0.48 * coin_t, loc=c, rot=ContainerMath.tilt_to(tilt), role=r["metal"], fillet=0.003))
            if spill:
                heap = (0.17, 0.1, 0.05)
                heap_c = (x0 + 0.2 * w, front - 0.06, z0)
                parts["spill"] = b.ellipsoid(heap, loc=heap_c, role=r["metal"], fillet=0.015)
                for k, (sx, sy) in enumerate(ContainerMath.scatter(rng, max(0, int(spill) - 2), heap[0] * 0.85, heap[1] * 0.8, 1.9 * coin_r, fill=0.8)):
                    dz, n = ContainerMath.dome_point(sx, sy, heap)
                    tilt = Vector((n.x + rng.uniform(-0.3, 0.3), n.y + rng.uniform(-0.3, 0.3), n.z)).normalized()
                    parts["coins"].append(b.round_cyl(coin_r, coin_t, edge=0.48 * coin_t, loc=(heap_c[0] + sx, heap_c[1] + sy, heap_c[2] + dz + 0.002), rot=ContainerMath.tilt_to(tilt), role=r["metal"], fillet=0.003))
                for k in range(min(2, int(spill))):
                    cxk = x0 + (0.02 + 0.075 * k) * w - 0.05
                    parts["coins"].append(b.round_cyl(coin_r, coin_t, edge=0.48 * coin_t, loc=(cxk, front - 0.016, z0 + coin_r * 0.95), rot=(72.0 + 6.0 * k, 0.0, 8.0 - 14.0 * k), role=r["metal"], fillet=0.003))
            with b.group("lid"):
                base = (x0, y0, top - 0.002)
                rot = ContainerMath.hinge_rot(angle)
                parts["lid"] = b.extrude2d(ContainerMath.arch(d + 0.008, lid_side, lid_dome, 0.03), w + 0.008, edge=0.035, plane="YZ", loc=ContainerMath.hinge_point(base, pivot, angle), rot=rot, role=r["wood"])
                for sx in strap_x:
                    parts["straps"].append(b.extrude2d(ContainerMath.arch(d + 0.03, lid_side, lid_dome + 0.015, 0.035), 0.07, edge=0.022, plane="YZ", loc=ContainerMath.hinge_point((x0 + sx, y0, top - 0.002), pivot, angle), rot=rot, role=r["metal"], fillet=0.006))
                if is_open:
                    inner_wall = 0.035
                    b.extrude2d(ContainerMath.arch(d - 2.0 * inner_wall, lid_side + 0.08, lid_dome - inner_wall, 0.02, drop=0.08), w - 2.0 * inner_wall, edge=0.015, plane="YZ", loc=ContainerMath.hinge_point(base, pivot, angle), rot=rot, role=r["wood"], op="subtract", fillet=0.01)
            b.cut(point=(x0, y0, z0 + 0.003), fillet=0.006)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (x0, y0, z0 + 0.5 * h), (w + 0.01, d + 0.01, h), parts["colliders"])
        lid_center, lid_size = ContainerMath.hinge_box((x0 - 0.5 * w, y0 - 0.5 * d, top), (x0 + 0.5 * w, y0 + 0.5 * d, top + lid), pivot, angle)
        ContainersRecipes.add_collider(b, lid_center, lid_size, parts["colliders"])
        parts["size"] = (w, d, h + lid)
        return parts

    def vault_safe(self, b, size=(0.9, 0.78, 1.0), radius=0.085, plinth=0.08, ring=0.2, tube=0.03, studs=12, stud=0.017, spokes=3, keypad=True, piping=True, roles=None, loc=(0.0, 0.0, 0.0)):
        r = self.slots(roles)
        w, d, h = ContainerMath.extents(size)
        x0, y0, z0 = ContainerMath.at(loc)
        rad = radius * min(w, d, h)
        body_h = h - plinth
        body_z0 = z0 + plinth - 0.02
        zb = body_z0 + 0.5 * (body_h + 0.02)
        zd = z0 + plinth + 0.5 * body_h
        front = y0 - 0.5 * d
        parts = {"studs": [], "spokes": [], "colliders": []}
        with b.group("vault_safe") as root:
            parts["plinth"] = b.round_box((w + 0.05, d + 0.05, plinth + 0.02), radius=0.45 * (plinth + 0.02), loc=(x0, y0, z0 + 0.5 * (plinth + 0.02)), role=r["trim"])
            parts["body"] = b.pillow_box((w, d, body_h + 0.02), radius=rad, puff=(0.012, 0.012, 0.016), loc=(x0, y0, zb), role=r["body"], fillet=0.015)
            if piping:
                parts["piping"] = b.tube({"shape": "rounded_rect", "w": w - 0.1, "h": body_h - 0.1, "r": 0.07, "plane": "XZ", "at": (x0, front - 0.009, zd)}, 0.018, role=r["trim"], fillet=0.008)
            with b.group("door"):
                b.round_cyl(ring - 0.012, 0.05, edge=0.015, loc=(x0, front, zd), rot=(90.0, 0.0, 0.0), role=r["trim"], op="subtract", fillet=0.012)
                ring_y = front - 0.45 * tube
                parts["ring"] = b.torus(ring, tube, loc=(x0, ring_y, zd), rot=(90.0, 0.0, 0.0), role=r["metal"], fillet=0.01)
                for k in range(int(studs)):
                    a = 2.0 * math.pi * (k + 0.5) / float(studs)
                    parts["studs"].append(b.sphere(stud, loc=(x0 + ring * math.cos(a), ring_y - 0.8 * tube, zd + ring * math.sin(a)), role=r["metal"], fillet=0.004))
                parts["hub"] = b.round_cyl(0.075, 0.06, edge=0.022, loc=(x0, front - 0.005, zd), rot=(90.0, 0.0, 0.0), role=r["metal"], fillet=0.008)
                parts["hub_cap"] = b.sphere(0.032, loc=(x0, front - 0.035, zd), role=r["accent"], fillet=0.006)
                reach = 0.62 * ring
                for k in range(int(spokes)):
                    a = math.radians(90.0 + 360.0 * k / float(spokes))
                    end = (x0 + reach * math.cos(a), front - 0.03, zd + reach * math.sin(a))
                    parts["spokes"].append(b.capsule((x0, front - 0.03, zd), end, 0.02, role=r["metal"], fillet=0.006))
                    parts["spokes"].append(b.sphere(0.034, loc=end, role=r["accent"], fillet=0.006))
                hinge_x = x0 - ring - tube - 0.045
                for s in (-1.0, 1.0):
                    hz = zd + s * ring * 0.45
                    b.capsule((hinge_x, front - 0.012, hz - 0.045), (hinge_x, front - 0.012, hz + 0.045), 0.024, role=r["metal"], fillet=0.006)
                    b.round_box((0.07, 0.03, 0.045), radius=0.012, loc=(x0 - ring - tube - 0.01, front - 0.012, hz), role=r["metal"], fillet=0.006)
            if keypad:
                kx = x0 + ring + tube + 0.09
                kz = zd + 0.02
                parts["keypad"] = b.round_box((0.11, 0.035, 0.2), radius=0.014, loc=(kx, front - 0.006, kz), role=r["ink"], fillet=0.006)
                parts["screen"] = b.round_box((0.075, 0.012, 0.028), radius=0.005, loc=(kx, front - 0.023, kz + 0.068), role=r["accent"], fillet=0.003)
                for i in range(2):
                    for j in range(3):
                        b.round_cyl(0.0135, 0.016, edge=0.0075, loc=(kx + (i - 0.5) * 0.04, front - 0.024, kz - 0.058 + 0.04 * j), rot=(90.0, 0.0, 0.0), role=r["body"], fillet=0.003)
            b.cut(point=(x0, y0, z0 + 0.003), fillet=0.006)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (x0, y0, z0 + 0.5 * h), (w + 0.05, d + 0.05, h), parts["colliders"])
        parts["size"] = (w + 0.05, d + 0.05, h + 0.016)
        return parts

    def corner_crate(self, b, size=(0.95, 0.75, 0.7), rail=0.07, cap=1.65, inset=0.02, lid_puff=0.035, brace=True, handles=True, roles=None, loc=(0.0, 0.0, 0.0)):
        r = self.slots(roles)
        w, d, h = ContainerMath.extents(size)
        x0, y0, z0 = ContainerMath.at(loc)
        t = float(rail)
        c = cap * t
        ax, ay = 0.5 * w - 0.5 * t, 0.5 * d - 0.5 * t
        zl, zh = z0 + 0.5 * t, z0 + h - 0.5 * t
        parts = {"rails": [], "caps": [], "colliders": []}
        with b.group("corner_crate") as root:
            parts["panels"] = b.round_box((w - 2.0 * inset, d - 2.0 * inset, h - 0.02), radius=0.03, loc=(x0, y0, z0 + 0.5 * h - 0.01), role=r["body"])
            with b.group("rails", fillet=0.012):
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        parts["rails"].append(b.round_box((t, t, h), radius=0.4 * t, loc=(x0 + sx * ax, y0 + sy * ay, z0 + 0.5 * h), role=r["trim"]))
                for sy in (-1.0, 1.0):
                    for zz in (zl, zh):
                        parts["rails"].append(b.round_box((w, t, t), radius=0.4 * t, loc=(x0, y0 + sy * ay, zz), role=r["trim"]))
                for sx in (-1.0, 1.0):
                    for zz in (zl, zh):
                        parts["rails"].append(b.round_box((t, d, t), radius=0.4 * t, loc=(x0 + sx * ax, y0, zz), role=r["trim"]))
            if brace:
                span_w = w - 2.0 * t
                span_h = h - 2.0 * t
                tilt = math.degrees(math.atan2(span_h, span_w))
                length = math.hypot(span_w, span_h) + 0.4 * t
                for sy in (-1.0, 1.0):
                    parts.setdefault("braces", []).append(b.round_box((length, 0.55 * t, 0.75 * t), radius=0.25 * t, loc=(x0, y0 + sy * (0.5 * d - 0.3 * inset - 0.275 * t), z0 + 0.5 * h), rot=(0.0, -tilt * sy, 0.0), role=r["trim"], fillet=0.01))
            lid_size = (w - 2.0 * t + 0.03, d - 2.0 * t + 0.03, 0.09)
            parts["lid"] = b.pillow_box(lid_size, radius=0.04, puff=(0.004, 0.004, lid_puff), loc=(x0, y0, z0 + h - 0.01), role=r["accent"], fillet=0.012)
            with b.group("caps", fillet=0.008):
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        for zz in (zl, zh):
                            parts["caps"].append(b.pillow_box((c, c, c), radius=0.32 * c, puff=0.006, loc=(x0 + sx * ax, y0 + sy * ay, zz), role=r["metal"]))
            if handles:
                hz = z0 + 0.6 * h
                for sx in (-1.0, 1.0):
                    hx = x0 + sx * (0.5 * w - inset + 0.005)
                    parts.setdefault("handles", []).append(b.round_box((0.03, 0.26, 0.11), radius=0.014, loc=(hx, y0, hz), role=r["trim"], fillet=0.006))
                    b.capsule((hx + sx * 0.016, y0 - 0.075, hz), (hx + sx * 0.016, y0 + 0.075, hz), 0.024, role=r["ink"], op="subtract", fillet=0.004)
            b.cut(point=(x0, y0, z0 + 0.003), fillet=0.006)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (x0, y0, z0 + 0.5 * h + 0.02), (w + 0.04, d + 0.04, h + 0.04), parts["colliders"])
        parts["size"] = (w + (c - t), d + (c - t), h + 0.08)
        return parts

    def gift_box(self, b, size=(0.8, 0.8, 0.62), radius=0.06, lid=0.14, overhang=0.028, ribbon=0.09, rise=0.008, bow=1.0, tails=True, roles=None, loc=(0.0, 0.0, 0.0)):
        r = self.slots(roles)
        w, d, h = ContainerMath.extents(size)
        x0, y0, z0 = ContainerMath.at(loc)
        rad = radius * min(w, d, h)
        hb = h - 0.55 * lid
        lid_r = 0.4 * lid
        lid_puff = 0.014
        box = {"size": (w, d, hb), "radius": rad, "loc": (x0, y0, z0 + 0.5 * hb)}
        cover = {"size": (w + 2.0 * overhang, d + 2.0 * overhang, lid), "radius": lid_r, "puff": (0.0, 0.0, lid_puff), "loc": (x0, y0, z0 + h - 0.5 * lid)}
        parts = {"ribbons": [], "loops": [], "colliders": []}
        with b.group("gift_box") as root:
            parts["box"] = b.round_box(role=r["wrap"], **box)
            parts["lid"] = b.pillow_box(role=r["wrap"], fillet=0.006, **cover)
            hosts = [("round_box", {"size": tuple(v + 2.0 * rise for v in box["size"]), "radius": rad + rise, "loc": box["loc"]}), ("pillow_box", {"size": tuple(v + 2.0 * rise for v in cover["size"]), "radius": lid_r + rise, "puff": cover["puff"], "loc": cover["loc"]})]
            for slab in ((ribbon, d + 0.5, h + 0.5), (w + 0.5, ribbon, h + 0.5)):
                parts["ribbons"].append(self.conformal(b, hosts, ("round_box", {"size": slab, "radius": 0.0, "loc": (x0, y0, z0 + 0.5 * h)}), r["ribbon"], rim=0.006, join=0.004, name="ribbon"))
            top = z0 + h + lid_puff
            if tails:
                tail_hosts = [("pillow_box", {"size": tuple(v + 2.0 * (rise + 0.008) for v in cover["size"]), "radius": lid_r + rise + 0.008, "puff": cover["puff"], "loc": cover["loc"]})]
                for a in (-40.0, 220.0):
                    outline = ContainerMath.tail(0.25 * bow, 0.075 * bow, 0.04 * bow)
                    parts.setdefault("tails", []).append(self.conformal(b, tail_hosts, ("extrude2d", {"outline": outline, "depth": 0.5, "plane": "XY", "loc": (x0, y0, top), "rot": (0.0, 0.0, a)}), r["ribbon"], rim=0.005, join=0.004, name="tail"))
            parts["knot"] = b.ellipsoid((0.058 * bow, 0.05 * bow, 0.046 * bow), loc=(x0, y0, top + 0.022 * bow), role=r["knot"], fillet=0.012)
            loop = ((0.03, 0.02, 0.0), (0.08, 0.09, -0.02), (0.16, 0.14, -0.035), (0.23, 0.12, -0.03), (0.25, 0.06, -0.01), (0.2, 0.025, 0.012), (0.1, 0.012, 0.012))
            radii = [0.022 * bow, 0.026 * bow, 0.032 * bow, 0.035 * bow, 0.033 * bow, 0.028 * bow, 0.024 * bow]
            for s in (-1.0, 1.0):
                path = [(x0 + s * u * bow, y0 + yy * bow, top + v * bow) for u, v, yy in loop]
                parts["loops"].append(b.tube(path, radii, closed=True, role=r["ribbon"], fillet=0.014))
            b.cut(point=(x0, y0, z0 + 0.002), fillet=0.006)
        parts["root"] = root
        ContainersRecipes.add_collider(b, (x0, y0, z0 + 0.5 * h), (w + 2.0 * overhang, d + 2.0 * overhang, h), parts["colliders"])
        parts["size"] = (w + 2.0 * overhang, d + 2.0 * overhang, h + 0.2 * bow)
        return parts


class ContainerDemo:
    def __init__(self, sf, recipes, out_dir, engine_dir, theme="house"):
        self.sf = sf
        self.recipes = recipes
        self.out = os.path.abspath(out_dir)
        self.engine_dir = engine_dir
        self.theme = theme
        self.blender = bpy.app.binary_path
        self.validate_script = os.path.join(engine_dir, "validate_sculpt.py")
        self.render_script = os.path.join(engine_dir, "render_sculpt.py")
        self.prop_script = os.path.normpath(os.path.join(engine_dir, "..", "..", "..", "prop-forge", "scripts", "blender", "validate_prop.py"))

    def specs(self):
        pastel = {"wrap": "pink", "ribbon": "mint", "knot": "gold"} if self.theme == "house" else {}
        return [
            {"id": "1nfx_ctr_padded_cube", "method": "padded_cube", "kwargs": {}, "budget": 2600, "voxel": 0.005, "default_role": "cream"},
            {"id": "1nfx_ctr_striped_box", "method": "striped_box", "kwargs": {}, "budget": 3000, "voxel": 0.005, "default_role": "cream"},
            {"id": "1nfx_ctr_loot_chest", "method": "loot_chest", "kwargs": {}, "budget": 3200, "voxel": 0.004, "default_role": "caramel"},
            {"id": "1nfx_ctr_vault_safe", "method": "vault_safe", "kwargs": {}, "budget": 3300, "voxel": 0.004, "default_role": "cream"},
            {"id": "1nfx_ctr_corner_crate", "method": "corner_crate", "kwargs": {}, "budget": 2800, "voxel": 0.005, "default_role": "cream"},
            {"id": "1nfx_ctr_gift_box", "method": "gift_box", "kwargs": {"roles": pastel}, "budget": 2800, "voxel": 0.005, "default_role": "pink"},
        ]

    def build(self, spec, overrides):
        started = time.perf_counter()
        args = {"budget": spec["budget"], "voxel": spec["voxel"]}
        args.update({k: v for k, v in overrides.items() if v is not None})
        b = ContainersRecipes.builder_class(self.sf)(spec["id"], size_class="medium", lod_dist=100.0, set_name="1nfx_ctr", archetype=spec["method"], palette=self.recipes.palette(), default_role=spec["default_role"], **args)
        parts = getattr(self.recipes, spec["method"])(b, **spec["kwargs"])
        result = b.build(self.out)
        metrics = result["metrics"]
        entry = {"id": spec["id"], "method": spec["method"], "tris": result["tris"], "budget": result["budget"], "voxel": args["voxel"], "surface_m2": metrics["surface_m2"], "tris_per_m2": metrics["tris_per_m2"], "dihedral_p90": metrics["dihedral_deg"]["p90"], "size_m": result["size_m"], "colliders": parts["colliders"], "warnings": result["warnings"], "timings": result["timings"], "seconds": round(time.perf_counter() - started, 2), "blend": result["blend"], "high_blend": result["high_blend"]}
        print("CONTAINERS_BUILD " + json.dumps({k: entry[k] for k in ("id", "tris", "budget", "tris_per_m2", "dihedral_p90", "seconds")}), flush=True)
        return entry

    def run_blender(self, script, args, log_path):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        cmd = [self.blender, "-b", "--factory-startup", "-P", script, "--"] + [str(a) for a in args]
        started = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write(proc.stdout or "")
            handle.write(proc.stderr or "")
        return proc.returncode, (proc.stdout or "").splitlines(), round(time.perf_counter() - started, 2)

    def validate(self, prop_id):
        blend = os.path.join(self.out, prop_id + ".blend")
        high = os.path.join(self.out, "_high", prop_id + "_high.blend")
        report = os.path.join(self.out, "qa", prop_id + "_qa.json")
        args = ["--blend", blend, "--json", report]
        if os.path.isfile(high):
            args += ["--high", high]
        code, lines, seconds = self.run_blender(self.validate_script, args, os.path.join(self.out, "qa", prop_id + "_qa.log"))
        verdict = next((line for line in reversed(lines) if line.startswith("SCULPT_QA ")), "SCULPT_QA missing")
        issues = [line for line in lines if line.startswith("WARN") or line.startswith("FAIL")]
        data = {}
        if os.path.isfile(report):
            with open(report, encoding="utf-8") as handle:
                data = json.load(handle)
        print("CONTAINERS_QA {} {} ({}s)".format(prop_id, verdict, seconds), flush=True)
        return {"id": prop_id, "line": verdict, "fail": int(data.get("fail", 1 if "missing" in verdict else 0)), "warn": int(data.get("warn", 0)), "issues": issues, "json": report, "drawables": data.get("drawables", [])}

    def prop_contract(self):
        code, lines, seconds = self.run_blender(self.prop_script, ["--blend", self.out], os.path.join(self.out, "qa", "validate_prop.log"))
        files = []
        current = None
        for line in lines:
            if line.startswith("== "):
                current = os.path.basename(line[3:].strip())
            elif line.startswith("RESULT ") and current:
                files.append("{} {}".format(current, line))
        total = next((line for line in reversed(lines) if line.startswith("TOTAL ")), "TOTAL missing")
        print("CONTAINERS_PROP_CONTRACT {} ({}s)".format(total, seconds), flush=True)
        return {"total": total, "files": files, "warn": sum(int(f.split("warn=")[1].split()[0]) for f in files if "warn=" in f)}

    def render(self, qa_path):
        folder = os.path.join(self.out, "renders")
        code, lines, seconds = self.run_blender(self.render_script, ["--blend", self.out, "--out", folder, "--qa", qa_path], os.path.join(self.out, "qa", "render.log"))
        verdict = next((line for line in reversed(lines) if line.startswith("SCULPT_RENDER ")), "SCULPT_RENDER missing")
        print("CONTAINERS_RENDER {} ({}s)".format(verdict, seconds), flush=True)
        outputs = []
        manifest = os.path.join(folder, "render_manifest.json")
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as handle:
                data = json.load(handle)
            for entry in data.get("drawables", []):
                outputs.extend(sorted(entry.get("outputs", {}).values()))
            outputs.extend(sorted(data.get("lineup", {}).values()))
        return {"line": verdict, "outputs": outputs}

    def run(self, only=None, overrides=None, qa=True, renders=True):
        os.makedirs(self.out, exist_ok=True)
        report = {"out": self.out, "theme": self.theme, "blender": bpy.app.version_string, "builds": [], "qa": [], "errors": []}
        for spec in self.specs():
            if only and spec["id"] not in only and spec["method"] not in only:
                continue
            try:
                report["builds"].append(self.build(spec, overrides or {}))
            except Exception as error:
                report["errors"].append("{}: {}: {}".format(spec["id"], type(error).__name__, error))
                print("CONTAINERS_FAIL {} {}: {}".format(spec["id"], type(error).__name__, error), flush=True)
        if qa and report["builds"]:
            merged = {"drawables": [], "fail": 0, "warn": 0}
            for entry in report["builds"]:
                result = self.validate(entry["id"])
                report["qa"].append({k: result[k] for k in ("id", "line", "fail", "warn", "issues")})
                merged["drawables"].extend(result["drawables"])
                merged["fail"] += result["fail"]
                merged["warn"] += result["warn"]
            qa_path = os.path.join(self.out, "qa", "containers_qa.json")
            with open(qa_path, "w", encoding="utf-8") as handle:
                json.dump(merged, handle, indent=1, default=str)
            report["qa_total"] = "SCULPT_QA fail={} warn={}".format(merged["fail"], merged["warn"])
            report["prop_contract"] = self.prop_contract()
            if renders:
                report["renders"] = self.render(qa_path)
        elif renders and report["builds"]:
            report["renders"] = self.render("")
        path = os.path.join(self.out, "containers_report.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        fails = len(report["errors"]) + sum(item["fail"] for item in report["qa"])
        print("CONTAINERS_DONE builds={} errors={} {} report={}".format(len(report["builds"]), len(report["errors"]), report.get("qa_total", "SCULPT_QA skipped"), path), flush=True)
        return fails, report


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="containers.py")
    parser.add_argument("--out", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--theme", default="house", choices=["house", "pastel"])
    parser.add_argument("--engine", default="")
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--voxel", type=float, default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-qa", dest="no_qa", action="store_true")
    parser.add_argument("--no-render", dest="no_render", action="store_true")
    args = parser.parse_args(argv)
    if not args.out:
        print("CONTAINERS_USAGE blender -b --factory-startup -P containers.py -- --out <dir> [--only padded_cube,vault_safe] [--theme house|pastel] [--no-qa] [--no-render]", flush=True)
        return None
    engine_dir = EngineLoader.folder(args.engine or None)
    sf = EngineLoader.load(engine_dir)
    recipes = ContainersRecipes(theme=args.theme, seed=args.seed)
    demo = ContainerDemo(sf, recipes, args.out, engine_dir, theme=args.theme)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    fails, report = demo.run(only=only, overrides={"budget": args.budget, "voxel": args.voxel}, qa=not args.no_qa, renders=not args.no_render)
    if bpy.app.background:
        sys.stdout.flush()
        sys.exit(1 if fails else 0)
    return report


if __name__ == "__main__":
    main()
