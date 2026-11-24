import argparse
import importlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector


class EngineLoader:
    @staticmethod
    def folder(explicit=None):
        if explicit:
            return os.path.abspath(explicit)
        here = globals().get("__file__")
        if not here:
            raise RuntimeError("no __file__ under exec: pass the sculpt-forge scripts/blender folder to EngineLoader.load(path) or --engine")
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(here)), ".."))

    @staticmethod
    def load(explicit=None):
        folder = EngineLoader.folder(explicit)
        if not os.path.isfile(os.path.join(folder, "sculpt_forge.py")):
            raise RuntimeError("sculpt_forge.py not found in {}".format(folder))
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module("sculpt_forge")


class OrganicMath:
    golden_deg = 137.50776405

    @staticmethod
    def rotation(rot):
        return np.array(Euler([math.radians(float(a)) for a in rot], "XYZ").to_matrix(), np.float64)

    @staticmethod
    def euler(matrix):
        return tuple(math.degrees(a) for a in Matrix(np.asarray(matrix, np.float64).tolist()).to_euler("XYZ"))

    @staticmethod
    def unit(vector):
        v = np.asarray(vector, np.float64)
        return v / max(float(np.linalg.norm(v)), 1e-12)

    @staticmethod
    def frame(normal, up=(0.0, 0.0, 1.0)):
        z = OrganicMath.unit(normal)
        helper = np.asarray(up, np.float64)
        if abs(float(z @ OrganicMath.unit(helper))) > 0.97:
            helper = np.array([0.0, 1.0, 0.0]) if abs(z[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        x = OrganicMath.unit(np.cross(helper, z))
        y = np.cross(z, x)
        return np.stack([x, y, z], axis=1)

    @staticmethod
    def place(origin, matrix, local):
        return tuple(float(v) for v in np.asarray(origin, np.float64) + np.asarray(matrix, np.float64) @ np.asarray(local, np.float64))

    @staticmethod
    def direction(azimuth_deg, elevation_deg):
        a = math.radians(azimuth_deg)
        e = math.radians(elevation_deg)
        return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)], np.float64)

    @staticmethod
    def ring(center, radius, count, z=None, phase_deg=0.0):
        c = np.asarray(center, np.float64)
        a = math.radians(phase_deg) + np.linspace(0.0, math.tau, int(count), endpoint=False)
        height = c[2] if z is None else float(z)
        return np.stack([c[0] + radius * np.cos(a), c[1] + radius * np.sin(a), np.full(len(a), height)], axis=1)

    @staticmethod
    def leaf_outline(length, width, shape=0.75, samples=28):
        u = np.linspace(0.0, 1.0, int(samples))
        half = 0.5 * float(width) * np.sin(np.pi * u ** float(shape)) ** 0.8
        top = np.stack([u * float(length), half], axis=1)
        bottom = np.stack([u[::-1] * float(length), -half[::-1]], axis=1)
        return np.vstack([top, bottom[1:-1]])

    @staticmethod
    def blob_outline(radius, lobes, amp, rng, samples=120):
        a = np.linspace(0.0, math.tau, int(samples), endpoint=False)
        wave = np.zeros_like(a)
        for k, weight in ((int(lobes), 0.62), (int(lobes) + 2, 0.24), (2, 0.14)):
            wave += weight * np.sin(k * a + rng.uniform(0.0, math.tau))
        r = float(radius) * (1.0 + float(amp) * wave)
        return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)

    @staticmethod
    def outline_radius(outline, angle):
        pts = np.asarray(outline, np.float64)
        ang = np.arctan2(pts[:, 1], pts[:, 0])
        diff = np.abs((ang - angle + math.pi) % math.tau - math.pi)
        return float(np.linalg.norm(pts[int(np.argmin(diff))]))

    @staticmethod
    def spiral(center, radius, top_radius, height, turns, per_turn=14, start_deg=0.0):
        c = np.asarray(center, np.float64)
        n = int(max(8, round(float(turns) * per_turn))) + 1
        t = np.linspace(0.0, 1.0, n)
        a = math.radians(start_deg) + math.tau * float(turns) * t
        r = float(radius) + (float(top_radius) - float(radius)) * t
        z = float(height) * t ** 0.92
        return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a), c[2] + z], axis=1), t

    @staticmethod
    def arc(points, count=8):
        pts = np.asarray(points, np.float64)
        if len(pts) < 3:
            return pts
        t = np.linspace(0.0, 1.0, int(count))
        a, b, c = pts[0], pts[1], pts[2]
        return np.array([(1 - s) ** 2 * a + 2 * (1 - s) * s * b + s * s * c for s in t])


class OrganicsRecipes:
    chibi_roles = {"cloth": "caramel", "hood": "caramel", "skin": "cream", "hair": "cocoa", "eye": "ink", "shine": "cream", "blush": "pink", "inner_ear": "pink", "mouth": "ink", "shoes": "cocoa", "cord": "honey"}
    blob_roles = {"body": "pink", "eye": "ink", "shine": "cream", "blush": "honey", "mouth": "ink", "crown": "gold", "tips": "honey", "gem": "cream", "velvet": "pink"}
    plant_roles = {"pot": "caramel", "rim": "cream", "soil": "cocoa", "leaf": "mint", "stem": "mint", "berry": "pink", "calyx": "mint", "petal": "cream", "heart": "honey"}
    pastry_roles = {"stand": "cream", "piping": "gold", "liner": "caramel", "cake": "honey", "frosting": "cream", "cherry": "pink", "stalk": "cocoa", "dough": "honey", "icing": "pink", "crust": "caramel", "crumb": "cream", "sprinkles": ("cream", "sky", "mint")}
    tree_roles = {"needles": "mint", "snow": "snow", "trunk": "cocoa", "star": "gold", "ground": "snow"}

    def __init__(self, builder, seed=0):
        self.b = builder
        self.seed = int(seed)

    def rng(self, seed=None):
        return random.Random(self.seed if seed is None else int(seed))

    def ground(self, z=0.0, fillet=0.02):
        return self.b.cut(point=(0.0, 0.0, float(z)), normal=(0.0, 0.0, -1.0), fillet=fillet)

    @staticmethod
    def band_role(roles, u):
        names = [roles] if isinstance(roles, str) else list(roles)
        index = int(min(len(names) - 1, max(0, math.floor(float(u) * len(names)))))
        return names[index]

    @staticmethod
    def merged(defaults, overrides):
        roles = dict(defaults)
        roles.update(overrides or {})
        return roles

    @staticmethod
    def cloud_lobes(width, depth, height, rng):
        lobes = []
        base_count = max(4, int(round(width / (0.44 * height))))
        for i in range(base_count):
            u = -0.4 + 0.8 * i / (base_count - 1)
            edge = abs(u) / 0.4
            r = height * (0.27 - 0.05 * edge) * rng.uniform(0.93, 1.07)
            v = (0.19 if i % 2 else -0.19) + rng.uniform(-0.04, 0.04)
            lobes.append({"loc": (u * width, v * depth, 0.04 * height + r), "radii": (1.18 * r, min(r, 0.36 * depth), r), "tier": 0})
        mid_count = max(3, base_count - 1)
        for i in range(mid_count):
            u = -0.29 + 0.58 * i / (mid_count - 1) + rng.uniform(-0.02, 0.02)
            edge = min(1.0, abs(u) / 0.29)
            r = height * (0.36 - 0.06 * edge) * rng.uniform(0.95, 1.05)
            v = rng.uniform(-0.06, 0.06)
            lobes.append({"loc": (u * width, v * depth, height * (0.46 + 0.03 * (1.0 - edge))), "radii": (1.1 * r, min(r, 0.42 * depth), r), "tier": 1})
        peak = rng.uniform(-0.1, 0.04)
        r = 0.33 * height
        lobes.append({"loc": (peak * width, rng.uniform(-0.04, 0.04) * depth, height - r), "radii": (1.12 * r, min(r, 0.4 * depth), r), "tier": 2})
        r = 0.26 * height
        lobes.append({"loc": ((peak + 0.21) * width, rng.uniform(-0.04, 0.04) * depth, 0.9 * height - r), "radii": (1.1 * r, min(r, 0.38 * depth), r), "tier": 2})
        return lobes

    def cloud(self, center=(0.0, 0.0, 0.0), size=(1.9, 1.05, 0.95), roles=("snow",), gradient="x", crease=0.22, flat=0.1, seed=None, fillet=0.0, collide=False, name="cloud"):
        rng = self.rng(seed)
        width, depth, height = (float(v) for v in size)
        cx, cy, cz = (float(v) for v in center)
        lobes = OrganicsRecipes.cloud_lobes(width, depth, height, rng)
        k = float(crease) * float(np.mean([lobe["radii"][2] for lobe in lobes]))
        nodes = []
        with self.b.group(name, fillet=fillet) as group:
            core = self.b.ellipsoid((0.38 * width, 0.34 * depth, 0.3 * height), loc=(cx, cy, cz + 0.4 * height), role=OrganicsRecipes.band_role(roles, 0.5), collide=collide)
            for lobe in lobes:
                lx, ly, lz = lobe["loc"]
                if gradient == "x":
                    u = lx / width + 0.5
                elif gradient == "z":
                    u = lz / height
                else:
                    u = 0.5
                nodes.append(self.b.ellipsoid(lobe["radii"], loc=(cx + lx, cy + ly, cz + lz), role=OrganicsRecipes.band_role(roles, u), fillet=k))
            if flat:
                self.b.cut(point=(cx, cy, cz + flat * height), normal=(0.0, 0.0, -1.0), fillet=0.6 * flat * height)
        lo = (cx - 0.5 * width, cy - 0.5 * depth, cz + float(flat) * height)
        hi = (cx + 0.5 * width, cy + 0.5 * depth, cz + height)
        return {"group": group, "core": core, "lobes": nodes, "bounds": (lo, hi), "fillet": k}

    def cloud_skirt(self, center=(0.0, 0.0, 0.0), radius=0.5, height=0.22, roles=("snow",), gradient=None, count=None, crease=0.3, seed=None, fillet=0.0, collide=False, name="cloud_skirt"):
        rng = self.rng(seed)
        cx, cy, cz = (float(v) for v in center)
        r = 0.92 * float(height)
        n = int(count or max(6, int(round(math.tau * float(radius) / (1.3 * r)))))
        nodes = []
        with self.b.group(name, fillet=fillet) as group:
            fill = self.b.ellipsoid((float(radius), float(radius), 0.78 * float(height)), loc=(cx, cy, cz), role=OrganicsRecipes.band_role(roles, 0.5), collide=collide)
            for i in range(n):
                a = math.tau * (i + rng.uniform(-0.18, 0.18)) / n
                rr = r * rng.uniform(0.84, 1.1)
                if gradient == "x":
                    u = 0.5 + 0.5 * math.cos(a)
                elif gradient == "angle":
                    u = i / float(n)
                else:
                    u = 0.5
                loc = (cx + float(radius) * math.cos(a), cy + float(radius) * math.sin(a), cz + 0.36 * rr)
                nodes.append(self.b.ellipsoid((1.28 * rr, 1.0 * rr, 0.9 * rr), loc=loc, rot=(0.0, 0.0, math.degrees(a) + 90.0), role=OrganicsRecipes.band_role(roles, u), fillet=float(crease) * r))
            self.b.cut(point=(cx, cy, cz), normal=(0.0, 0.0, -1.0), fillet=0.2 * r)
        return {"group": group, "fill": fill, "lobes": nodes, "radius": float(radius) + 1.28 * r, "top": cz + 1.26 * r}

    def pot(self, center=(0.0, 0.0, 0.0), height=0.5, radius=0.34, base_ratio=0.74, wall=0.04, rim=None, soil_drop=0.07, bulge=None, band=True, roles=None, name="pot"):
        roles = OrganicsRecipes.merged(self.plant_roles, roles)
        cx, cy, cz = (float(v) for v in center)
        h = float(height)
        rt = float(radius)
        rb = float(base_ratio) * rt
        lip = float(rim or 0.085 * h)
        top = h - lip
        soil = h - float(soil_drop)
        swell = float(bulge if bulge is not None else 0.08 * rt)
        profile = [(0.0, 0.0), (rb - 0.03, 0.0), (rb, 0.025), (rb + 0.25 * (rt - rb) + 0.8 * swell, 0.3 * top), (rb + 0.62 * (rt - rb) + swell, 0.66 * top), (rt, top), (rt - wall, top), (rt - 1.15 * wall, soil - 0.02), (0.0, soil - 0.02)]
        with self.b.group(name, fillet=0.0) as group:
            body = self.b.lathe(profile, loc=(cx, cy, cz), smooth=3, role=roles["pot"], collide=True)
            lip_node = self.b.torus(rt - 0.45 * wall, lip, loc=(cx, cy, cz + top), role=roles["rim"], fillet=0.45 * lip)
            band_node = None
            if band:
                ring_r = rb + 0.25 * (rt - rb) + 0.75 * swell
                band_node = self.b.torus(ring_r, 0.5 * lip, loc=(cx, cy, cz + 0.3 * top), role=roles["rim"], fillet=0.4 * lip)
            soil_node = self.b.ellipsoid((rt - 1.1 * wall, rt - 1.1 * wall, 0.05), loc=(cx, cy, cz + soil - 0.02), role=roles["soil"], fillet=0.015)
        return {"group": group, "body": body, "rim": lip_node, "band": band_node, "soil": soil_node, "soil_z": cz + soil + 0.03, "rim_z": cz + top, "rim_radius": rt + lip}

    def leaf(self, base, length=0.36, width=0.22, yaw=0.0, pitch=30.0, roll=0.0, thickness=None, vein=True, role="mint", shape=0.62, fillet=0.02, name="leaf"):
        t = float(thickness or max(0.032, 0.17 * float(width)))
        edge = 0.48 * t
        puff = 0.26 * t
        rot = (float(roll), -float(pitch), float(yaw))
        m = OrganicMath.rotation(rot)
        outline = OrganicMath.leaf_outline(length, width, shape)
        groove = None
        with self.b.group(name, fillet=fillet) as group:
            blade = self.b.extrude2d(outline, depth=t, edge=edge, puff=puff, puff_width=0.5 * float(width), plane="XY", loc=tuple(base), rot=rot, role=role)
            if vein:
                radius = 0.075 * float(width)
                top = 0.5 * t + puff
                a = OrganicMath.place(base, m, (0.14 * length, 0.0, top + 0.12 * radius))
                b = OrganicMath.place(base, m, (0.78 * length, 0.0, top - 0.45 * radius))
                groove = self.b.round_cone(a, b, radius, 0.45 * radius, op="subtract", fillet=0.45 * radius)
        return {"group": group, "blade": blade, "groove": groove, "tip": OrganicMath.place(base, m, (length, 0.0, 0.0)), "thickness": t}

    def stem(self, points, radius=0.015, taper=0.75, role="mint", fillet=0.012):
        pts = [tuple(float(c) for c in p) for p in points]
        return self.b.tube(pts, [float(radius), float(radius) * float(taper)], closed=False, role=role, fillet=fillet)

    def berry(self, top, size=0.09, kind="strawberry", hang=(0.0, 0.0, -1.0), role="pink", cap_role="mint", fillet=0.01, name="berry"):
        d = OrganicMath.unit(hang)
        t = np.asarray(top, np.float64)
        s = float(size)
        parts = {}
        with self.b.group(name, fillet=fillet) as group:
            if kind == "strawberry":
                parts["body"] = self.b.round_cone(tuple(t + d * 0.4 * s), tuple(t + d * 1.05 * s), 0.5 * s, 0.17 * s, role=role)
                cap = OrganicMath.frame(-d)
                outline = {"shape": "star", "r_out": 0.52 * s, "r_in": 0.3 * s, "points": 5, "smooth": 3}
                depth = max(0.018, 0.2 * s)
                parts["calyx"] = self.b.extrude2d(outline, depth=depth, edge=0.42 * depth, puff=0.12 * depth, plane="XY", loc=tuple(t + d * 0.05 * s), rot=OrganicMath.euler(cap), role=cap_role, fillet=0.01)
            elif kind == "blueberry":
                parts["body"] = self.b.sphere(0.5 * s, loc=tuple(t + d * 0.5 * s), role=role)
                parts["crown"] = self.b.sphere(0.16 * s, loc=tuple(t + d * 1.02 * s), op="subtract", fillet=0.05 * s)
            else:
                parts["body"] = self.b.sphere(0.5 * s, loc=tuple(t + d * 0.48 * s), role=role)
                parts["dimple"] = self.b.sphere(0.12 * s, loc=tuple(t + d * 0.02 * s), op="subtract", fillet=0.06 * s)
        parts["group"] = group
        parts["bottom"] = tuple(t + d * 1.22 * s)
        return parts

    def flower(self, center, radius=0.09, petals=5, facing=(0.0, 0.0, 1.0), spin=0.0, cup=14.0, roles=("cream", "honey"), thickness=None, fillet=0.008, name="flower"):
        face = OrganicMath.frame(facing)
        r = float(radius)
        t = float(thickness or max(0.018, 0.22 * r))
        nodes = []
        with self.b.group(name, fillet=fillet) as group:
            for i in range(int(petals)):
                m = face @ OrganicMath.rotation((0.0, -float(cup), float(spin) + 360.0 * i / int(petals)))
                loc = OrganicMath.place(center, m, (0.5 * r, 0.0, 0.0))
                nodes.append(self.b.ellipsoid((0.52 * r, 0.36 * r, 0.5 * t), loc=loc, rot=OrganicMath.euler(m), role=roles[0], fillet=0.5 * t))
            heart = self.b.ellipsoid((0.32 * r, 0.32 * r, 0.22 * r), loc=OrganicMath.place(center, face, (0.0, 0.0, 0.3 * t)), rot=OrganicMath.euler(face), role=roles[1], fillet=0.4 * t)
        return {"group": group, "petals": nodes, "heart": heart}

    def potted_plant(self, center=(0.0, 0.0, 0.0), pot_height=0.5, pot_radius=0.34, leaves=8, leaf_length=0.4, leaf_width=0.25, flowers=3, berries=3, roles=None, seed=None, name="plant"):
        roles = OrganicsRecipes.merged(self.plant_roles, roles)
        rng = self.rng(seed)
        cx, cy, cz = (float(v) for v in center)
        pot = self.pot(center, pot_height, pot_radius, roles=roles, name=name + "_pot")
        soil = pot["soil_z"]
        crown = np.array([cx, cy, soil + 0.02])
        lower = max(3, int(round(int(leaves) * 0.62)))
        upper = max(1, int(leaves) - lower)
        result = {"pot": pot, "leaves": [], "flowers": [], "berries": []}
        with self.b.group(name + "_bush", fillet=0.03) as bush:
            result["mound"] = self.b.ellipsoid((0.14, 0.14, 0.09), loc=tuple(crown), role=roles["stem"])
            for i in range(lower):
                yaw = 360.0 * i / lower + rng.uniform(-9.0, 9.0)
                a = math.radians(yaw)
                base = crown + np.array([0.07 * math.cos(a), 0.07 * math.sin(a), 0.04])
                result["leaves"].append(self.leaf(tuple(base), float(leaf_length) * rng.uniform(0.94, 1.06), float(leaf_width) * rng.uniform(0.94, 1.05), yaw=yaw, pitch=12.0 + rng.uniform(-4.0, 5.0), roll=rng.uniform(-7.0, 7.0), role=roles["leaf"], name="{}_leaf{}".format(name, i)))
            for i in range(upper):
                yaw = 360.0 * i / upper + 180.0 / lower + rng.uniform(-12.0, 12.0)
                a = math.radians(yaw)
                base = crown + np.array([0.035 * math.cos(a), 0.035 * math.sin(a), 0.1])
                result["leaves"].append(self.leaf(tuple(base), 0.8 * float(leaf_length), 0.9 * float(leaf_width), yaw=yaw, pitch=55.0 + rng.uniform(-6.0, 6.0), roll=rng.uniform(-6.0, 6.0), role=roles["leaf"], name="{}_leaf{}".format(name, lower + i)))
            for i in range(int(flowers)):
                a = math.radians(360.0 * i / max(1, int(flowers)) + 50.0 + rng.uniform(-10.0, 10.0))
                out = 0.12 + 0.04 * rng.random()
                head = crown + np.array([out * math.cos(a), out * math.sin(a), 0.44 + 0.05 * rng.random()])
                mid = crown + np.array([0.25 * out * math.cos(a), 0.25 * out * math.sin(a), 0.26])
                self.stem([tuple(crown + np.array([0.0, 0.0, 0.06])), tuple(mid), tuple(head)], radius=0.021, taper=0.85, role=roles["stem"], fillet=0.016)
                facing = (0.45 * math.cos(a), 0.45 * math.sin(a), 1.0)
                result["flowers"].append(self.flower(tuple(head), 0.105, facing=facing, spin=rng.uniform(0.0, 72.0), roles=(roles["petal"], roles["heart"]), name="{}_flower{}".format(name, i)))
            for i in range(int(berries)):
                a = math.radians(360.0 * (i + 0.5) / max(1, int(berries)) + 180.0 / lower + rng.uniform(-8.0, 8.0))
                out = np.array([math.cos(a), math.sin(a), 0.0])
                rim = np.array([cx, cy, pot["rim_z"]])
                start = crown + out * 0.08 + np.array([0.0, 0.0, 0.03])
                peak = crown + out * (0.68 * float(pot_radius)) + np.array([0.0, 0.0, 0.1])
                over = rim + out * (pot["rim_radius"] + 0.025) + np.array([0.0, 0.0, 0.06])
                hang = rim + out * (pot["rim_radius"] + 0.065) + np.array([0.0, 0.0, -0.02])
                self.stem([tuple(start), tuple(peak), tuple(over), tuple(hang)], radius=0.018, taper=0.85, role=roles["stem"], fillet=0.014)
                result["berries"].append(self.berry(tuple(hang), 0.125, "strawberry", hang=(0.3 * out[0], 0.3 * out[1], -1.0), role=roles["berry"], cap_role=roles["calyx"], name="{}_berry{}".format(name, i)))
        result["bush"] = bush
        return result

    def cake_stand(self, center=(0.0, 0.0, 0.0), radius=0.52, height=0.36, dish_depth=0.035, roles=None, name="stand"):
        roles = OrganicsRecipes.merged(self.pastry_roles, roles)
        cx, cy, cz = (float(v) for v in center)
        r = float(radius)
        h = float(height)
        foot = 0.36 * r
        neck = 0.12 * r
        plate = 0.06
        dish = float(dish_depth)
        profile = [(0.0, 0.0), (foot - 0.03, 0.0), (foot, 0.03), (foot - 0.035, 0.07), (neck + 0.07, 0.12), (neck + 0.01, 0.19), (neck, h - plate - 0.07), (neck + 0.08, h - plate - 0.01), (0.55 * r, h - plate + 0.005), (r - 0.05, h - plate + 0.02), (r, h - 0.03), (r - 0.012, h + 0.012), (r - 0.06, h + 0.004), (0.6 * r, h - 0.55 * dish), (0.0, h - dish)]
        with self.b.group(name, fillet=0.0) as group:
            body = self.b.lathe(profile, loc=(cx, cy, cz), smooth=3, role=roles["stand"], collide=True)
            piping = self.b.torus(r - 0.018, 0.026, loc=(cx, cy, cz + h - 0.008), role=roles["piping"], fillet=0.012)
            foot_ring = self.b.torus(foot - 0.03, 0.02, loc=(cx, cy, cz + 0.04), role=roles["piping"], fillet=0.01)
        return {"group": group, "body": body, "piping": piping, "foot": foot_ring, "top": cz + h, "dish": dish, "radius": r}

    @staticmethod
    def dish_height(stand, x, y):
        u = min(1.0, math.hypot(x, y) / max(stand["radius"] - 0.06, 1e-6))
        return stand["top"] - stand["dish"] * (1.0 - u * u)

    def frosting_swirl(self, base, radius=0.17, height=0.24, turns=2.6, tube=0.06, role="cream", fillet=0.016, name="swirl"):
        pts, t = OrganicMath.spiral(base, float(radius), 0.18 * float(radius), float(height), float(turns), 14, 25.0)
        per = max(4, int(round(len(pts) / float(turns))))
        nodes = []
        with self.b.group(name, fillet=0.0) as group:
            start = 0
            while start < len(pts) - 1:
                end = min(len(pts), start + per + 1)
                seg = pts[start:end]
                r0 = float(tube) * (1.0 - 0.42 * float(t[start]))
                r1 = float(tube) * (1.0 - 0.42 * float(t[end - 1]))
                nodes.append(self.b.tube([tuple(p) for p in seg], [r0, r1], closed=False, role=role, fillet=fillet))
                start = end - 1
            tip_base = pts[-1]
            tip = np.array([float(base[0]), float(base[1]), tip_base[2] + 0.55 * float(tube)])
            nodes.append(self.b.round_cone(tuple(tip_base), tuple(tip), 0.58 * float(tube), 0.2 * float(tube), role=role, fillet=0.6 * fillet))
        return {"group": group, "coils": nodes, "top": tuple(tip)}

    def cupcake(self, base=(0.0, 0.0, 0.0), radius=0.17, height=0.52, ribs=12, turns=2.5, cherry=True, roles=None, name="cupcake"):
        roles = OrganicsRecipes.merged(self.pastry_roles, roles)
        cx, cy, cz = (float(v) for v in base)
        rt = float(radius)
        rb = 0.8 * rt
        hl = 0.36 * float(height)
        pleat = 0.16 * rt
        result = {}
        with self.b.group(name + "_liner", fillet=0.0) as liner:
            result["liner"] = self.b.lathe([(0.0, 0.0), (rb - 0.025, 0.0), (rb, 0.022), (0.5 * (rb + rt) + 0.012, 0.5 * hl), (rt, hl), (0.0, hl)], loc=(cx, cy, cz), smooth=2, role=roles["liner"], collide=True)
            for i in range(int(ribs)):
                a = math.tau * (i + 0.5) / int(ribs)
                p0 = (cx + (rb - 0.3 * pleat) * math.cos(a), cy + (rb - 0.3 * pleat) * math.sin(a), cz + 0.035)
                p1 = (cx + (rt - 0.3 * pleat) * math.cos(a), cy + (rt - 0.3 * pleat) * math.sin(a), cz + hl - 0.02)
                self.b.capsule(p0, p1, pleat, role=roles["liner"], fillet=0.9 * pleat)
        result["liner_group"] = liner
        result["cake"] = self.b.ellipsoid((1.1 * rt, 1.1 * rt, 0.44 * rt), loc=(cx, cy, cz + hl + 0.01), role=roles["cake"], fillet=0.02)
        swirl = self.frosting_swirl((cx, cy, cz + hl + 0.05), 0.95 * rt, 0.44 * float(height), turns, 0.36 * rt, role=roles["frosting"], name=name + "_swirl")
        result["swirl"] = swirl
        if cherry:
            top = np.asarray(swirl["top"], np.float64)
            cr = 0.32 * rt
            result["cherry"] = self.b.sphere(cr, loc=(top[0], top[1], top[2] + 0.72 * cr), role=roles["cherry"], fillet=0.012)
            result["stalk"] = self.b.tube([(top[0], top[1], top[2] + 1.5 * cr), (top[0] + 0.35 * cr, top[1], top[2] + 2.3 * cr), (top[0] + 0.9 * cr, top[1] + 0.1 * cr, top[2] + 2.9 * cr)], [0.012, 0.01], closed=False, role=roles["stalk"], fillet=0.008)
        return result

    def donut(self, center=(0.0, 0.0, 0.0), major=0.13, minor=0.066, icing=True, sprinkles=0, rot=(0.0, 0.0, 0.0), roles=None, seed=None, name="donut"):
        roles = OrganicsRecipes.merged(self.pastry_roles, roles)
        rng = self.rng(seed)
        c = np.asarray(center, np.float64)
        m = OrganicMath.rotation(rot)
        R = float(major)
        r = float(minor)
        result = {"dough": self.b.torus(R, r, loc=tuple(c), rot=rot, role=roles["dough"], fillet=0.02)}
        if icing:
            with self.b.group(name + "_icing", fillet=0.006) as group:
                result["icing"] = self.b.torus(R, r + 0.01, loc=tuple(c), rot=rot, role=roles["icing"])
                self.b.cut(point=OrganicMath.place(c, m, (0.0, 0.0, 0.08 * r)), normal=tuple(m @ np.array([0.0, 0.0, -1.0])), fillet=0.008)
                path = [OrganicMath.place(c, m, (p[0], p[1], 0.06 * r)) for p in OrganicMath.ring((0.0, 0.0, 0.0), R + 0.97 * r, 48)]
                result["drape"] = self.b.scallops(path, drop=0.36 * r, thickness=0.3 * r, per_m=10.0, outward=0.05 * r, role=roles["icing"], fillet=0.006, closed=True)
            result["icing_group"] = group
            dots = []
            names = [roles["sprinkles"]] if isinstance(roles["sprinkles"], str) else list(roles["sprinkles"])
            for i in range(int(sprinkles)):
                a = math.tau * (i + rng.uniform(-0.3, 0.3)) / max(1, int(sprinkles))
                v = math.radians(rng.uniform(25.0, 80.0))
                ring = R + (r + 0.008) * math.cos(v)
                p = np.array([ring * math.cos(a), ring * math.sin(a), (r + 0.008) * math.sin(v)])
                tangent = np.array([-math.sin(a + 0.6 * rng.uniform(-1, 1)), math.cos(a + 0.6 * rng.uniform(-1, 1)), 0.0]) * 0.022
                p0 = OrganicMath.place(c, m, p - tangent)
                p1 = OrganicMath.place(c, m, p + tangent)
                dots.append(self.b.capsule(p0, p1, 0.011, role=names[i % len(names)], fillet=0.004, detail=True))
            result["sprinkles"] = dots
        return result

    def bread(self, center=(0.0, 0.0, 0.0), size=(0.4, 0.22, 0.17), yaw=0.0, scores=3, roles=None, name="bread"):
        roles = OrganicsRecipes.merged(self.pastry_roles, roles)
        length, width, height = (float(v) for v in size)
        c = np.asarray(center, np.float64)
        m = OrganicMath.rotation((0.0, 0.0, float(yaw)))
        result = {}
        with self.b.group(name, fillet=0.0) as group:
            result["loaf"] = self.b.ellipsoid((0.5 * length, 0.5 * width, height), loc=tuple(c), rot=(0.0, 0.0, float(yaw)), role=roles["crust"], collide=True)
            result["belly"] = self.b.ellipsoid((0.44 * length, 0.52 * width, 0.55 * height), loc=OrganicMath.place(c, m, (0.0, 0.0, 0.18 * height)), rot=(0.0, 0.0, float(yaw)), role=roles["crust"], fillet=0.04)
            cuts = []
            groove = 0.16 * width
            for i in range(int(scores)):
                u = (i - 0.5 * (int(scores) - 1)) * (0.6 * length / max(1, int(scores)))
                z = height * math.sqrt(max(1.0 - (2.0 * u / length) ** 2, 0.05)) + 0.4 * groove
                a = OrganicMath.place(c, m, (u - 0.14 * width, -0.36 * width, z))
                b = OrganicMath.place(c, m, (u + 0.14 * width, 0.36 * width, z))
                cuts.append(self.b.capsule(a, b, groove, op="subtract", role=roles["crumb"], fillet=0.6 * groove))
            result["scores"] = cuts
        result["group"] = group
        return result

    def pastry_stand(self, center=(0.0, 0.0, 0.0), radius=0.52, height=0.36, sprinkles=0, roles=None, seed=None, name="pastry"):
        roles = OrganicsRecipes.merged(self.pastry_roles, roles)
        cx, cy, cz = (float(v) for v in center)
        stand = self.cake_stand(center, radius, height, roles=roles, name=name + "_stand")
        r = float(radius)
        result = {"stand": stand}
        spots = {"cupcake": (0.0, 0.2 * r), "donut": (-0.42 * r, -0.33 * r), "bread": (0.42 * r, -0.3 * r)}
        floor = {key: OrganicsRecipes.dish_height(stand, x, y) for key, (x, y) in spots.items()}
        result["cupcake"] = self.cupcake((cx + spots["cupcake"][0], cy + spots["cupcake"][1], floor["cupcake"] - 0.008), 0.32 * r, 1.0 * r, roles=roles, name=name + "_cupcake")
        result["donut"] = self.donut((cx + spots["donut"][0], cy + spots["donut"][1], floor["donut"] + 0.1 * r), 0.24 * r, 0.12 * r, rot=(9.0, -12.0, 0.0), sprinkles=sprinkles, roles=roles, seed=seed, name=name + "_donut")
        result["bread"] = self.bread((cx + spots["bread"][0], cy + spots["bread"][1], floor["bread"] - 0.012), (0.74 * r, 0.44 * r, 0.3 * r), yaw=32.0, roles=roles, name=name + "_bread")
        return result

    def chibi(self, center=(0.0, 0.0, 0.0), height=1.3, ears="bear", hood=True, base="cloud", roles=None, seed=None, name="chibi"):
        roles = OrganicsRecipes.merged(self.chibi_roles, roles)
        cx, cy, ground = (float(v) for v in center)
        h = float(height)
        parts = {}
        cz = ground
        if base == "cloud":
            parts["base"] = self.cloud_skirt((cx, cy, ground), 0.3 * h, 0.13 * h, roles=("snow",), seed=seed, fillet=0.035 * h, collide=True, name=name + "_skirt")
            cz = ground + 0.07 * h
        rh = 0.235 * h
        head_c = np.array([cx, cy, cz + h - 0.97 * rh])
        with self.b.group(name + "_figure", fillet=0.03 * h) as figure:
            parts["torso"] = self.b.round_cone((cx, cy, cz + 0.17 * h), (cx, cy, cz + 0.45 * h), 0.168 * h, 0.118 * h, role=roles["cloth"], collide=True)
            for side in (-1.0, 1.0):
                self.b.round_cone((cx + side * 0.078 * h, cy, cz + 0.2 * h), (cx + side * 0.088 * h, cy - 0.006 * h, cz + 0.075 * h), 0.068 * h, 0.058 * h, role=roles["cloth"], fillet=0.035 * h)
                self.b.ellipsoid((0.068 * h, 0.094 * h, 0.052 * h), loc=(cx + side * 0.09 * h, cy - 0.026 * h, cz + 0.05 * h), role=roles["shoes"], fillet=0.03 * h)
                self.b.round_cone((cx + side * 0.125 * h, cy, cz + 0.4 * h), (cx + side * 0.2 * h, cy - 0.065 * h, cz + 0.27 * h), 0.056 * h, 0.05 * h, role=roles["cloth"], fillet=0.032 * h)
                self.b.sphere(0.062 * h, loc=(cx + side * 0.208 * h, cy - 0.078 * h, cz + 0.232 * h), role=roles["skin"], fillet=0.026 * h, detail=True)
            parts["head"] = self.b.ellipsoid((rh, 1.05 * rh, 0.98 * rh), loc=tuple(head_c), role=roles["skin"], fillet=0.05 * h)
            parts["face"] = self.face(head_c, rh, roles, h)
            for side in (-1.0, 1.0):
                top = (cx + side * 0.058 * h, cy - 0.132 * h, cz + 0.47 * h)
                low = (cx + side * 0.064 * h, cy - 0.142 * h, cz + 0.36 * h)
                self.b.tube([top, low], [0.014 * h, 0.014 * h], closed=False, role=roles["cord"], fillet=0.008 * h)
                self.b.sphere(0.026 * h, loc=(low[0], low[1] - 0.006 * h, low[2] - 0.014 * h), role=roles["cord"], fillet=0.008 * h)
        parts["figure"] = figure
        if hood:
            parts["hood"] = self.hood(head_c, rh, ears, roles, h, name + "_hood")
        return parts

    def face(self, head_c, rh, roles, h):
        feats = {"eyes": [], "cheeks": []}
        surface = np.array([1.0, 1.05, 0.98]) * rh
        for side in (-1.0, 1.0):
            d = OrganicMath.direction(side * 24.0, -9.0)
            f = OrganicMath.frame(d * np.array([1.0, 0.95, 1.0]))
            eye_c = head_c + d * surface * 0.985
            feats["eyes"].append(self.b.ellipsoid((0.105 * rh, 0.15 * rh, 0.06 * rh), loc=tuple(eye_c), rot=OrganicMath.euler(f), role=roles["eye"], fillet=0.008 * h, detail=True))
            shine = OrganicMath.place(eye_c, f, (-side * 0.03 * rh, 0.06 * rh, 0.05 * rh))
            self.b.sphere(0.042 * rh, loc=shine, role=roles["shine"], fillet=0.004 * h, detail=True)
            dc = OrganicMath.direction(side * 43.0, -22.0)
            fc = OrganicMath.frame(dc)
            feats["cheeks"].append(self.b.ellipsoid((0.13 * rh, 0.085 * rh, 0.035 * rh), loc=tuple(head_c + dc * surface * 0.995), rot=OrganicMath.euler(fc), role=roles["blush"], fillet=0.012 * h, detail=True))
        dm = OrganicMath.direction(0.0, -27.0)
        fm = OrganicMath.frame(dm)
        feats["mouth"] = self.b.ellipsoid((0.085 * rh, 0.05 * rh, 0.07 * rh), loc=tuple(head_c + dm * surface * 1.02), rot=OrganicMath.euler(fm), op="subtract", role=roles["mouth"], fillet=0.012 * h, detail=True)
        for az, el in ((-30.0, 34.0), (0.0, 39.0), (30.0, 34.0)):
            dh = OrganicMath.direction(az, el)
            fh = OrganicMath.frame(dh)
            self.b.ellipsoid((0.27 * rh, 0.2 * rh, 0.13 * rh), loc=tuple(head_c + dh * surface * 0.985), rot=OrganicMath.euler(fh), role=roles["hair"], fillet=0.035 * rh)
        return feats

    def hood(self, head_c, rh, ears, roles, h, name):
        hood_c = head_c + np.array([0.0, 0.1 * rh, 0.04 * rh])
        outer = 1.12 * rh
        open_c = head_c + np.array([0.0, -1.0 * rh, -0.08 * rh])
        ax, az = 0.84 * rh, 0.8 * rh
        parts = {}
        with self.b.group(name, fillet=0.014 * h) as group:
            parts["shell"] = self.b.sphere(outer, loc=tuple(hood_c), role=roles["hood"])
            parts["drape"] = self.b.ellipsoid((0.95 * rh, 0.9 * rh, 0.55 * rh), loc=tuple(head_c + np.array([0.0, 0.16 * rh, -0.62 * rh])), role=roles["hood"], fillet=0.12 * rh)
            parts["opening"] = self.b.ellipsoid((ax, 0.55 * rh, az), loc=tuple(open_c), op="subtract", fillet=0.05 * rh)
            rim = []
            for a in np.linspace(0.0, math.tau, 40, endpoint=False):
                x = ax * 0.97 * math.cos(a)
                z = az * 0.97 * math.sin(a)
                px = hood_c[0] + x
                pz = open_c[2] + z
                inside = outer * outer - x * x - (pz - hood_c[2]) ** 2
                py = hood_c[1] - math.sqrt(max(inside, 1e-6)) + 0.01 * rh
                rim.append((px, py, pz))
            parts["rim"] = self.b.tube(rim, 0.085 * rh, closed=True, role=roles["hood"], fillet=0.03 * rh)
            parts["ears"] = self.ears(hood_c, outer, rh, ears, roles)
        parts["group"] = group
        return parts

    def ears(self, hood_c, outer, rh, kind, roles):
        made = []
        if not kind:
            return made
        for side in (-1.0, 1.0):
            if kind == "bunny":
                tilt = 16.0
                d = np.array([side * math.sin(math.radians(tilt)), 0.1, math.cos(math.radians(tilt))])
                loc = hood_c + OrganicMath.unit(d) * (outer + 0.36 * rh)
                radii = (0.17 * rh, 0.1 * rh, 0.6 * rh)
                inner = (0.09 * rh, 0.045 * rh, 0.42 * rh)
            elif kind == "cat":
                tilt = 30.0
                d = np.array([side * math.sin(math.radians(tilt)), 0.05, math.cos(math.radians(tilt))])
                loc = hood_c + OrganicMath.unit(d) * (outer + 0.02 * rh)
                radii = (0.26 * rh, 0.12 * rh, 0.34 * rh)
                inner = (0.14 * rh, 0.05 * rh, 0.2 * rh)
            else:
                tilt = 40.0
                d = np.array([side * math.sin(math.radians(tilt)), 0.12, math.cos(math.radians(tilt))])
                loc = hood_c + OrganicMath.unit(d) * (0.94 * outer)
                radii = (0.31 * rh, 0.14 * rh, 0.29 * rh)
                inner = (0.19 * rh, 0.06 * rh, 0.175 * rh)
            rot = (0.0, side * tilt, 0.0)
            m = OrganicMath.rotation(rot)
            made.append(self.b.ellipsoid(radii, loc=tuple(loc), rot=rot, role=roles["hood"], fillet=0.06 * rh))
            made.append(self.b.ellipsoid(inner, loc=OrganicMath.place(loc, m, (0.0, -0.105 * rh, -0.01 * rh)), rot=rot, role=roles["inner_ear"], fillet=0.012 * rh, detail=True))
        return made

    def puddle(self, center=(0.0, 0.0, 0.0), radius=0.5, height=0.06, lobes=7, amp=0.12, rim=None, satellites=3, role="pink", seed=None, fillet=0.0, name="puddle"):
        rng = self.rng(seed)
        cx, cy, cz = (float(v) for v in center)
        outline = OrganicMath.blob_outline(radius, lobes, amp, rng)
        edge_t = float(rim or 0.35 * float(height))
        parts = {"satellites": []}
        with self.b.group(name, fillet=fillet) as group:
            parts["pool"] = self.b.extrude2d(outline, depth=2.0 * edge_t, edge=0.95 * edge_t, puff=float(height) - edge_t, puff_width=float(radius), plane="XY", loc=(cx, cy, cz), role=role)
            for i in range(int(satellites)):
                a = math.tau * (i + rng.uniform(0.1, 0.9)) / max(1, int(satellites))
                rs = float(height) * rng.uniform(0.9, 1.4)
                reach = OrganicMath.outline_radius(outline, a) + 0.55 * rs
                parts["satellites"].append(self.b.ellipsoid((rs, rs, 0.75 * rs), loc=(cx + reach * math.cos(a), cy + reach * math.sin(a), cz), role=role, fillet=0.8 * rs))
            self.b.cut(point=(cx, cy, cz), normal=(0.0, 0.0, -1.0), fillet=0.6 * edge_t)
        parts["group"] = group
        parts["outline"] = outline
        return parts

    def crown(self, base, radius=0.12, height=0.11, prongs=5, tilt=(0.0, 12.0, 0.0), roles=None, fillet=0.012, name="crown"):
        roles = OrganicsRecipes.merged(self.blob_roles, roles)
        m = OrganicMath.rotation(tilt)
        r = float(radius)
        h = float(height)
        parts = {"prongs": [], "tips": []}
        with self.b.group(name, fillet=fillet) as group:
            parts["band"] = self.b.round_cyl(r, 0.42 * h, edge=0.1 * h, loc=OrganicMath.place(base, m, (0.0, 0.0, 0.21 * h)), rot=tilt, role=roles["crown"])
            parts["rim"] = self.b.torus(r, 0.085 * h, loc=OrganicMath.place(base, m, (0.0, 0.0, 0.05 * h)), rot=tilt, role=roles["crown"], fillet=0.03 * h)
            parts["velvet"] = self.b.ellipsoid((0.86 * r, 0.86 * r, 0.42 * h), loc=OrganicMath.place(base, m, (0.0, 0.0, 0.42 * h)), rot=tilt, role=roles["velvet"], fillet=0.03 * h)
            for i in range(int(prongs)):
                a = math.radians(-90.0 + 360.0 * i / int(prongs))
                p0 = OrganicMath.place(base, m, (0.9 * r * math.cos(a), 0.9 * r * math.sin(a), 0.3 * h))
                p1 = OrganicMath.place(base, m, (1.1 * r * math.cos(a), 1.1 * r * math.sin(a), 0.96 * h))
                parts["prongs"].append(self.b.round_cone(p0, p1, 0.25 * r, 0.12 * r, role=roles["crown"], fillet=0.05 * r))
                parts["tips"].append(self.b.sphere(0.19 * r, loc=OrganicMath.place(base, m, (1.12 * r * math.cos(a), 1.12 * r * math.sin(a), 1.06 * h)), role=roles["tips"], fillet=0.04 * r))
            parts["gem"] = self.b.ellipsoid((0.16 * r, 0.08 * r, 0.16 * r), loc=OrganicMath.place(base, m, (0.0, -1.02 * r, 0.22 * h)), rot=tilt, role=roles["gem"], fillet=0.025 * r, detail=True)
        parts["group"] = group
        return parts

    def drip_runs(self, center, radii, count=5, start=26.0, end=-60.0, thickness=0.035, avoid=40.0, role="pink", seed=None, fillet=0.02):
        rng = self.rng(seed)
        c = np.asarray(center, np.float64)
        rad = np.asarray(radii, np.float64)
        t = float(thickness)
        runs = []
        n = int(count)
        for i in range(n):
            az = float(avoid) + (360.0 - 2.0 * float(avoid)) * (i + rng.uniform(0.25, 0.75)) / n
            els = np.linspace(float(start) + rng.uniform(-6.0, 6.0), float(end) * rng.uniform(0.8, 1.02), 6)
            pts = [tuple(c + OrganicMath.direction(az, el) * rad) for el in els]
            tail = OrganicMath.direction(az, els[-1])
            runs.append(self.b.tube(pts, [0.42 * t, 0.58 * t, 0.7 * t, 0.82 * t, 0.92 * t, t], closed=False, role=role, fillet=fillet))
            runs.append(self.b.sphere(1.22 * t, loc=tuple(np.asarray(pts[-1]) + tail * 0.45 * t), role=role, fillet=0.6 * fillet))
        return runs

    def blob_mascot(self, center=(0.0, 0.0, 0.0), radius=0.36, crown=True, puddle=True, drips=5, blush=False, roles=None, seed=None, name="blob"):
        roles = OrganicsRecipes.merged(self.blob_roles, roles)
        cx, cy, cz = (float(v) for v in center)
        R = float(radius)
        radii = np.array([R, 0.94 * R, 0.97 * R])
        body_c = np.array([cx, cy, cz + 0.99 * R])
        parts = {}
        if puddle:
            parts["puddle"] = self.puddle((cx, cy, cz), 1.55 * R, 0.17 * R, lobes=7, amp=0.11, role=roles["body"], seed=seed, name=name + "_puddle")
        with self.b.group(name, fillet=0.26 * R if puddle else 0.0) as group:
            parts["body"] = self.b.ellipsoid(tuple(radii), loc=tuple(body_c), role=roles["body"], collide=True)
            if not crown:
                parts["tuft"] = self.b.round_cone((cx, cy, cz + 1.6 * R), (cx + 0.12 * R, cy, cz + 2.05 * R), 0.3 * R, 0.08 * R, role=roles["body"], fillet=0.14 * R)
            if drips:
                parts["drips"] = self.drip_runs(body_c, radii, int(drips), thickness=0.1 * R, role=roles["body"], seed=seed, fillet=0.06 * R)
            for side in (-1.0, 1.0):
                d = OrganicMath.direction(side * 23.0, 3.0)
                f = OrganicMath.frame(d)
                eye_c = body_c + d * radii * 0.985
                self.b.ellipsoid((0.1 * R, 0.15 * R, 0.065 * R), loc=tuple(eye_c), rot=OrganicMath.euler(f), role=roles["eye"], fillet=0.01, detail=True)
                self.b.sphere(0.042 * R, loc=OrganicMath.place(eye_c, f, (-side * 0.03 * R, 0.06 * R, 0.05 * R)), role=roles["shine"], fillet=0.004, detail=True)
                if blush:
                    dc = OrganicMath.direction(side * 44.0, -14.0)
                    fc = OrganicMath.frame(dc)
                    self.b.ellipsoid((0.12 * R, 0.08 * R, 0.035 * R), loc=tuple(body_c + dc * radii * 0.995), rot=OrganicMath.euler(fc), role=roles["blush"], fillet=0.012, detail=True)
            dm = OrganicMath.direction(0.0, -17.0)
            fm = OrganicMath.frame(dm)
            parts["mouth"] = self.b.ellipsoid((0.12 * R, 0.075 * R, 0.09 * R), loc=tuple(body_c + dm * radii * 1.01), rot=OrganicMath.euler(fm), op="subtract", role=roles["mouth"], fillet=0.016, detail=True)
        parts["group"] = group
        if crown:
            top = body_c + np.array([0.1 * R, 0.0, 0.88 * R])
            parts["crown"] = self.crown(tuple(top), 0.42 * R, 0.4 * R, tilt=(0.0, 14.0, 0.0), roles=roles, fillet=0.03 * R, name=name + "_crown")
        return parts

    def snowballs(self, center, count=4, radius=0.1, spread=0.5, role="snow", seed=None, fillet=0.03, name="snowballs"):
        rng = self.rng(seed)
        cx, cy, cz = (float(v) for v in center)
        made = []
        for i in range(int(count)):
            a = math.tau * (i + rng.uniform(-0.25, 0.25)) / max(1, int(count)) + 0.4
            r = float(radius) * rng.uniform(0.7, 1.15)
            d = float(spread) * rng.uniform(0.85, 1.0)
            made.append(self.b.sphere(r, loc=(cx + d * math.cos(a), cy + d * math.sin(a), cz + 0.72 * r), role=role, fillet=fillet))
        return made

    def cone_tree(self, center=(0.0, 0.0, 0.0), height=1.7, radius=0.52, tiers=3, star=True, drape=True, ground=True, roles=None, seed=None, name="tree"):
        roles = OrganicsRecipes.merged(self.tree_roles, roles)
        cx, cy, cz = (float(v) for v in center)
        H = float(height)
        R = float(radius)
        trunk_h = 0.15 * H
        star_r = 0.075 * H if star else 0.0
        body_h = H - trunk_h - 1.6 * star_r
        parts = {"tiers": [], "drapes": []}
        if ground:
            parts["ground"] = self.puddle((cx, cy, cz), 1.18 * R, 0.07, lobes=6, amp=0.09, satellites=0, role=roles["ground"], seed=seed, name=name + "_ground")
            parts["snowballs"] = self.snowballs((cx, cy, cz + 0.04), 4, 0.075 * H, 0.95 * R, role=roles["snow"], seed=seed, fillet=0.03)
        with self.b.group(name, fillet=0.05) as group:
            parts["trunk"] = self.b.round_cyl(0.075 * H, trunk_h + 0.12, edge=0.03, loc=(cx, cy, cz + 0.5 * (trunk_h + 0.12) - 0.04), role=roles["trunk"], collide=True)
            step = body_h / (int(tiers) + 0.6)
            for i in range(int(tiers)):
                ri = R * (1.0 - 0.25 * i)
                hi = 1.55 * step * (1.0 - 0.08 * i)
                zb = cz + trunk_h + i * step
                profile = [(0.0, -0.04 * hi), (0.6 * ri, -0.015 * hi), (0.96 * ri, 0.02 * hi), (ri, 0.075 * hi)]
                profile += [(0.97 * ri * (1.0 - s) ** 0.72, s * hi) for s in (0.16, 0.34, 0.52, 0.7, 0.86, 0.96)]
                profile.append((0.0, hi))
                parts["tiers"].append(self.b.lathe(profile, loc=(cx, cy, zb), smooth=2, role=roles["needles"], fillet=0.04))
                if drape:
                    ring = [tuple(p) for p in OrganicMath.ring((cx, cy, zb), 0.95 * ri, 64, z=zb + 0.1 * hi, phase_deg=17.0 * i)]
                    parts["drapes"].append(self.b.torus(0.9 * ri, 0.04 + 0.01 * (2 - i), loc=(cx, cy, zb + 0.11 * hi), role=roles["snow"], fillet=0.02))
                    parts["drapes"].append(self.b.scallops(ring, drop=0.075 - 0.012 * i, thickness=0.05, per_m=6.5, outward=0.012, role=roles["snow"], fillet=0.015, closed=True))
            top_z = cz + trunk_h + (int(tiers) - 1) * step + 1.55 * step * (1.0 - 0.08 * (int(tiers) - 1))
            parts["cap"] = self.b.ellipsoid((0.12 * R, 0.12 * R, 0.09 * R), loc=(cx, cy, top_z - 0.06 * R), role=roles["snow"], fillet=0.04)
            if star:
                outline = {"shape": "star", "r_out": star_r, "r_in": 0.5 * star_r, "points": 5, "smooth": 3}
                parts["star"] = self.b.extrude2d(outline, depth=0.42 * star_r, edge=0.18 * star_r, puff=0.08 * star_r, plane="XZ", loc=(cx, cy, top_z + 0.75 * star_r), role=roles["star"], fillet=0.03)
        parts["group"] = group
        parts["top"] = top_z + (1.75 * star_r if star else 0.0)
        return parts


class OrganicsDemo:
    set_name = "1nfx_organic"
    palette_roles = {
        "cream": {"color": "#FFFBF4", "finish": "satin"},
        "snow": {"color": "#FFFBF4", "finish": "matte"},
        "caramel": {"color": "#C48E62", "finish": "satin"},
        "ink": {"color": "#3B281E", "finish": "matte"},
        "cocoa": {"color": "#4A3327", "finish": "matte"},
        "honey": {"color": "#E8B04B", "finish": "satin"},
        "pink": {"color": "#F2B8C6", "finish": "satin"},
        "mint": {"color": "#A8D8C8", "finish": "satin"},
        "sky": {"color": "#A9CBEA", "finish": "satin"},
        "gold": {"color": "#D9A441", "finish": "gloss"},
    }
    props = (
        {"id": "1nfx_org_cloud", "kind": "cloud", "archetype": "cloud", "budget": 3600, "voxel": 0.006, "lod": 150.0, "ao": 0.24, "seed": 7},
        {"id": "1nfx_org_plant", "kind": "plant", "archetype": "plant", "budget": 4200, "voxel": 0.005, "lod": 120.0, "ao": 0.18, "seed": 3},
        {"id": "1nfx_org_pastry", "kind": "pastry", "archetype": "pastry_stand", "budget": 4200, "voxel": 0.005, "lod": 120.0, "ao": 0.18, "seed": 5},
        {"id": "1nfx_org_chibi", "kind": "chibi", "archetype": "figure", "budget": 6000, "voxel": 0.005, "lod": 150.0, "ao": 0.2, "seed": 11},
        {"id": "1nfx_org_blob", "kind": "blob", "archetype": "mascot", "budget": 3600, "voxel": 0.005, "lod": 120.0, "ao": 0.2, "seed": 2},
        {"id": "1nfx_org_snowtree", "kind": "snowtree", "archetype": "tree", "budget": 4200, "voxel": 0.006, "lod": 150.0, "ao": 0.22, "seed": 9},
    )

    def __init__(self, engine, out_dir, voxel=None, budget_scale=1.0):
        self.sf = engine
        self.out = os.path.abspath(out_dir)
        self.voxel = voxel
        self.budget_scale = float(budget_scale)
        self.palette = engine.SetPalette(self.set_name, self.palette_roles, 32)

    def spec(self, prop_id):
        for spec in self.props:
            if spec["id"] == prop_id:
                return spec
        raise ValueError("unknown demo prop {}".format(prop_id))

    def builder(self, spec):
        return self.sf.SculptBuilder(spec["id"], budget=int(round(spec["budget"] * self.budget_scale)), lod_dist=spec["lod"], set_name=self.set_name, archetype=spec["archetype"], voxel=float(self.voxel or spec["voxel"]), palette=self.palette, default_role="cream", ao_distance=spec["ao"])

    def make_cloud(self, recipes, b):
        recipes.cloud(size=(1.9, 1.05, 0.95), roles=("pink", "snow", "sky"), gradient="x")
        b.collider((0.0, 0.0, 0.5), (1.72, 0.86, 0.8))

    def make_plant(self, recipes, b):
        recipes.potted_plant()
        recipes.ground()
        b.collider((0.0, 0.0, 0.3), (0.66, 0.66, 0.6))

    def make_pastry(self, recipes, b):
        recipes.pastry_stand()
        recipes.ground()
        b.collider((0.0, 0.0, 0.25), (1.06, 1.06, 0.5))

    def make_chibi(self, recipes, b):
        recipes.chibi(height=1.3, ears="bear")
        recipes.ground()
        b.collider((0.0, 0.0, 0.7), (0.7, 0.6, 1.4))

    def make_blob(self, recipes, b):
        recipes.blob_mascot(radius=0.36)
        recipes.ground()
        b.collider((0.0, 0.0, 0.36), (0.74, 0.7, 0.72))

    def make_snowtree(self, recipes, b):
        recipes.cone_tree()
        recipes.ground()
        b.collider((0.0, 0.0, 0.8), (0.9, 0.9, 1.6))

    def build(self, prop_id):
        spec = self.spec(prop_id)
        started = time.perf_counter()
        b = self.builder(spec)
        recipes = OrganicsRecipes(b, seed=spec["seed"])
        getattr(self, "make_" + spec["kind"])(recipes, b)
        result = b.build(self.out)
        metrics = result["metrics"]
        entry = {"id": spec["id"], "kind": spec["kind"], "tris": metrics["tris"], "budget": result["budget"], "surface_m2": metrics["surface_m2"], "tris_per_m2": metrics["tris_per_m2"], "size_m": result["size_m"], "dihedral_p90": metrics["dihedral_deg"]["p90"], "dev_p95_mm": metrics["surface_dev_mm"]["p95"], "high_tris": metrics["high_tris"], "seconds": round(time.perf_counter() - started, 2), "blend": result["blend"], "high_blend": result["high_blend"], "timings": result["timings"], "warnings": result["warnings"]}
        print("ORGANICS_BUILD " + json.dumps({k: entry[k] for k in ("id", "tris", "budget", "surface_m2", "tris_per_m2", "dihedral_p90", "dev_p95_mm", "seconds")}), flush=True)
        return entry


class QaRunner:
    def __init__(self, blender, folder, out_dir, timeout=1200):
        self.blender = blender
        self.folder = folder
        self.out = out_dir
        self.timeout = int(timeout)

    def script(self, name):
        return os.path.join(self.folder, name)

    def prop_validator(self):
        return os.path.normpath(os.path.join(self.folder, "..", "..", "..", "prop-forge", "scripts", "blender", "validate_prop.py"))

    def run(self, script, args):
        command = [self.blender, "-b", "--factory-startup", "-P", script, "--"] + [str(a) for a in args]
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def sculpt_qa(self, entry):
        folder = os.path.join(self.out, "qa")
        os.makedirs(folder, exist_ok=True)
        report = os.path.join(folder, entry["id"] + "_qa.json")
        args = ["--blend", entry["blend"], "--json", report]
        if entry.get("high_blend"):
            args += ["--high", entry["high_blend"]]
        validator = self.prop_validator()
        if os.path.isfile(validator):
            args += ["--prop-validator", validator]
        code, text = self.run(self.script("validate_sculpt.py"), args)
        with open(os.path.join(folder, entry["id"] + "_qa.log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        found = re.findall(r"SCULPT_QA fail=(\d+) warn=(\d+)", text)
        fail, warn = (int(found[-1][0]), int(found[-1][1])) if found else (1, 0)
        notes = [line.strip() for line in text.splitlines() if line.startswith("WARN") or line.startswith("FAIL")]
        return {"id": entry["id"], "fail": fail, "warn": warn, "notes": notes, "json": report, "exit": code}

    def prop_qa(self):
        code, text = self.run(self.prop_validator(), ["--blend", self.out])
        with open(os.path.join(self.out, "qa", "validate_prop.log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        results = {}
        current = None
        for line in text.splitlines():
            if line.startswith("== "):
                current = os.path.splitext(os.path.basename(line[3:].strip()))[0]
            match = re.match(r"RESULT fail=(\d+) warn=(\d+)", line)
            if match and current:
                results[current] = {"fail": int(match.group(1)), "warn": int(match.group(2))}
        return results

    def merge(self, reports):
        merged = {"drawables": [], "fail": 0, "warn": 0}
        for report in reports:
            if not os.path.isfile(report["json"]):
                continue
            with open(report["json"], encoding="utf-8") as handle:
                data = json.load(handle)
            merged["drawables"].extend(data.get("drawables", []))
            merged["fail"] += int(data.get("fail", 0))
            merged["warn"] += int(data.get("warn", 0))
        path = os.path.join(self.out, "qa", "sculpt_qa.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=1)
        return path

    def render(self, qa_json, views=4, res=900):
        renders = os.path.join(self.out, "renders")
        code, text = self.run(self.script("render_sculpt.py"), ["--blend", self.out, "--out", renders, "--qa", qa_json, "--views", views, "--res", res])
        with open(os.path.join(self.out, "qa", "render.log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        summary = re.findall(r"SCULPT_RENDER .*", text)
        return {"exit": code, "folder": renders, "summary": summary[-1] if summary else "SCULPT_RENDER missing"}


class OrganicsCli:
    def __init__(self, argv):
        parser = argparse.ArgumentParser(prog="organics.py")
        parser.add_argument("--out", default="")
        parser.add_argument("--engine", default="")
        parser.add_argument("--only", default="")
        parser.add_argument("--voxel", type=float, default=None)
        parser.add_argument("--budget-scale", dest="budget_scale", type=float, default=1.0)
        parser.add_argument("--blender", default="")
        parser.add_argument("--no-qa", dest="no_qa", action="store_true")
        parser.add_argument("--no-render", dest="no_render", action="store_true")
        parser.add_argument("--views", type=int, default=4)
        parser.add_argument("--res", type=int, default=900)
        self.args = parser.parse_args(argv)

    def run(self):
        if not self.args.out:
            print("usage: blender -b --factory-startup -P organics.py -- --out <dir> [--only id1,id2] [--voxel 0.005] [--budget-scale 1.0] [--no-qa] [--no-render] [--engine <sculpt-forge/scripts/blender>]", flush=True)
            return 0
        engine = EngineLoader.load(self.args.engine or None)
        folder = os.path.dirname(os.path.abspath(engine.__file__))
        demo = OrganicsDemo(engine, self.args.out, self.args.voxel, self.args.budget_scale)
        os.makedirs(demo.out, exist_ok=True)
        wanted = [s.strip() for s in self.args.only.split(",") if s.strip()]
        entries = []
        failures = 0
        for spec in demo.props:
            if wanted and spec["id"] not in wanted:
                continue
            try:
                entries.append(demo.build(spec["id"]))
            except Exception as error:
                failures += 1
                print("ORGANICS_FAIL {} {}: {}".format(spec["id"], type(error).__name__, error), flush=True)
        report = {"out": demo.out, "blender": bpy.app.version_string, "props": entries, "qa": [], "prop_qa": {}, "render": None}
        if not self.args.no_qa and entries:
            runner = QaRunner(self.args.blender or bpy.app.binary_path, folder, demo.out)
            for entry in entries:
                qa = runner.sculpt_qa(entry)
                report["qa"].append(qa)
                print("ORGANICS_QA " + json.dumps({"id": qa["id"], "fail": qa["fail"], "warn": qa["warn"], "notes": qa["notes"]}), flush=True)
            report["prop_qa"] = runner.prop_qa()
            for prop_id, verdict in sorted(report["prop_qa"].items()):
                print("PROP_QA {} fail={} warn={}".format(prop_id, verdict["fail"], verdict["warn"]), flush=True)
            merged = runner.merge(report["qa"])
            if not self.args.no_render:
                report["render"] = runner.render(merged, self.args.views, self.args.res)
                print(report["render"]["summary"], flush=True)
        qa_fail = sum(q["fail"] for q in report["qa"])
        qa_warn = sum(q["warn"] for q in report["qa"])
        prop_fail = sum(v["fail"] for v in report["prop_qa"].values())
        prop_warn = sum(v["warn"] for v in report["prop_qa"].values())
        path = os.path.join(demo.out, "organics_report.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        print("SCULPT_QA fail={} warn={}".format(qa_fail, qa_warn), flush=True)
        print("ORGANICS_DONE props={} build_fail={} qa_fail={} qa_warn={} prop_fail={} prop_warn={} report={}".format(len(entries), failures, qa_fail, qa_warn, prop_fail, prop_warn, path), flush=True)
        return 1 if failures or qa_fail or prop_fail else 0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    code = OrganicsCli(argv).run()
    if bpy.app.background:
        sys.stdout.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    main()
