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
from mathutils import Euler, Matrix


class EngineLocator:
    @staticmethod
    def candidates(explicit=None):
        roots = []
        if explicit:
            roots.append(explicit)
        if os.environ.get("SCULPT_FORGE_DIR"):
            roots.append(os.environ["SCULPT_FORGE_DIR"])
        here = globals().get("__file__")
        if here:
            roots.append(os.path.dirname(os.path.abspath(here)))
        roots.append(os.path.join(os.path.expanduser("~"), ".claude", "skills", "infrontofx", "sculpt-forge", "scripts", "blender"))
        found = []
        for root in roots:
            found.extend([root, os.path.join(root, ".."), os.path.join(root, "scripts", "blender")])
        return found

    @staticmethod
    def folder(explicit=None):
        for path in EngineLocator.candidates(explicit):
            if path and os.path.isfile(os.path.join(path, "sculpt_forge.py")):
                return os.path.normpath(os.path.abspath(path))
        raise RuntimeError("sculpt_forge.py not found; pass engine_dir=<skill>/sculpt-forge/scripts/blender or set SCULPT_FORGE_DIR")

    @staticmethod
    def load(explicit=None):
        folder = EngineLocator.folder(explicit)
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module("sculpt_forge")


class RoundsMath:
    @staticmethod
    def matrix(rot):
        return np.array(Euler([math.radians(float(a)) for a in rot], "XYZ").to_matrix(), np.float64)

    @staticmethod
    def euler_from_axes(x_axis, y_axis, z_axis):
        m = Matrix((tuple(float(v) for v in x_axis), tuple(float(v) for v in y_axis), tuple(float(v) for v in z_axis))).transposed()
        return tuple(math.degrees(a) for a in m.to_euler("XYZ"))

    @staticmethod
    def unit(v):
        v = np.asarray(v, np.float64)
        return v / max(float(np.linalg.norm(v)), 1e-12)

    @staticmethod
    def scaled(points, sx, sz, z0=0.0):
        pts = np.asarray(points, np.float64).copy()
        pts[:, 0] *= float(sx)
        pts[:, 1] = pts[:, 1] * float(sz) + float(z0)
        return pts

    @staticmethod
    def outer_curve(profile):
        prof = np.asarray(profile, np.float64)
        return prof[:int(np.argmax(prof[:, 1])) + 1].copy()

    @staticmethod
    def side_curve(profile, fraction=0.6):
        prof = np.asarray(profile, np.float64)
        return prof[prof[:, 0] >= float(fraction) * float(prof[:, 0].max())].copy()

    @staticmethod
    def arc(cx, cz, radius, a0_deg, a1_deg, count):
        a = np.radians(np.linspace(float(a0_deg), float(a1_deg), int(count)))
        return [(cx + radius * math.cos(t), cz + radius * math.sin(t)) for t in a]

    @staticmethod
    def puck_profile(radius, height, rim=0.5, dome=0.0, bulge=0.0, recess=0.0, z=0.0, samples=6):
        r = float(radius)
        h = float(height)
        e = max(1e-4, min(0.5, float(rim)) * h)
        flat = r - e
        pts = [(0.0, z + float(recess))]
        if recess:
            pts.append((0.55 * flat, z + 0.62 * float(recess)))
        pts.append((flat, z))
        pts += RoundsMath.arc(flat, z + e, e, -90.0, 0.0, samples)[1:]
        side = h - 2.0 * e
        if side > 1e-4:
            pts += [(r + float(bulge) * math.sin(math.pi * t), z + e + side * t) for t in (0.25, 0.5, 0.75)]
        pts += RoundsMath.arc(flat, z + h - e, e, 0.0, 90.0, samples)[1:]
        if dome:
            pts += [(flat * (1.0 - k), z + h + float(dome) * (1.0 - (1.0 - k) ** 2)) for k in (0.4, 0.75)]
        pts.append((0.0, z + h + float(dome)))
        return pts

    @staticmethod
    def coin_profile(radius, thickness, edge=0.3, dome=0.0, samples=6):
        r = float(radius)
        t = float(thickness)
        e = max(1e-4, min(0.5, float(edge)) * t)
        flat = r - e
        d = float(dome)
        pts = [(0.0, -0.5 * t - d), (0.6 * flat, -0.5 * t - 0.64 * d), (flat, -0.5 * t)]
        pts += RoundsMath.arc(flat, -0.5 * t + e, e, -90.0, 0.0, samples)[1:]
        if t - 2.0 * e > 1e-4:
            pts.append((r, 0.0))
        pts += RoundsMath.arc(flat, 0.5 * t - e, e, 0.0, 90.0, samples)[1:]
        pts += [(0.6 * flat, 0.5 * t + 0.64 * d), (0.0, 0.5 * t + d)]
        return pts

    @staticmethod
    def curve_normals(points):
        pts = np.asarray(points, np.float64)
        t = np.empty_like(pts)
        t[1:-1] = pts[2:] - pts[:-2]
        t[0] = pts[1] - pts[0]
        t[-1] = pts[-1] - pts[-2]
        n = np.stack([t[:, 1], -t[:, 0]], axis=1)
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    @staticmethod
    def offset_curve(points, distance):
        pts = np.asarray(points, np.float64)
        out = pts + RoundsMath.curve_normals(pts) * float(distance)
        out[:, 0] = np.maximum(out[:, 0], 0.0)
        return out

    @staticmethod
    def window(points, zlo, zhi, step=0.004):
        pts = np.asarray(points, np.float64)
        order = np.argsort(pts[:, 1], kind="stable")
        zs = pts[order, 1]
        rs = pts[order, 0]
        lo = max(float(zlo), float(zs[0]))
        hi = min(float(zhi), float(zs[-1]))
        count = max(3, int(math.ceil((hi - lo) / float(step))) + 1)
        z = np.unique(np.concatenate([np.linspace(lo, hi, count), zs[(zs > lo) & (zs < hi)]]))
        return np.stack([np.interp(z, zs, rs), z], axis=1)

    @staticmethod
    def shell(curve, outer, inner):
        up = RoundsMath.offset_curve(curve, outer)
        down = RoundsMath.offset_curve(curve, -float(inner))[::-1]
        return np.vstack([up, down])

    @staticmethod
    def lathe_point(curve, u, v, azimuth=-90.0):
        c = np.asarray(curve, np.float64)
        order = np.argsort(c[:, 1], kind="stable")
        zs = c[order, 1]
        rho = float(np.interp(v, zs, c[order, 0]))
        normals = RoundsMath.curve_normals(c)[order]
        nr = float(np.interp(v, zs, normals[:, 0]))
        nz = float(np.interp(v, zs, normals[:, 1]))
        length = max(math.hypot(nr, nz), 1e-9)
        a = math.radians(float(azimuth))
        facing = np.array([math.cos(a), math.sin(a), 0.0])
        lateral = np.array([-math.sin(a), math.cos(a), 0.0])
        x = float(np.clip(u, -0.97 * rho, 0.97 * rho))
        depth = math.sqrt(max(rho * rho - x * x, 1e-12))
        planar = lateral * x + facing * depth
        point = planar + np.array([0.0, 0.0, float(v)])
        normal = planar / max(rho, 1e-9) * (nr / length) + np.array([0.0, 0.0, nz / length])
        return point, RoundsMath.unit(normal), lateral

    @staticmethod
    def bezier2(p0, p1, p2, t):
        a = np.asarray(p0, np.float64)
        b = np.asarray(p1, np.float64)
        c = np.asarray(p2, np.float64)
        point = (1.0 - t) ** 2 * a + 2.0 * (1.0 - t) * t * b + t * t * c
        tangent = 2.0 * (1.0 - t) * (b - a) + 2.0 * t * (c - b)
        return point, RoundsMath.unit(tangent)

    @staticmethod
    def bezier3(p0, p1, p2, p3, count):
        t = np.linspace(0.0, 1.0, int(count))[:, None]
        pts = [np.asarray(p, np.float64) for p in (p0, p1, p2, p3)]
        return (1 - t) ** 3 * pts[0] + 3 * (1 - t) ** 2 * t * pts[1] + 3 * (1 - t) * t * t * pts[2] + t ** 3 * pts[3]

    @staticmethod
    def cup_profile():
        return [
            (0.000, 0.000), (0.205, 0.000), (0.222, 0.012), (0.222, 0.030), (0.200, 0.046), (0.140, 0.064), (0.090, 0.090),
            (0.066, 0.130), (0.060, 0.190), (0.075, 0.215), (0.098, 0.240), (0.098, 0.265), (0.075, 0.290), (0.060, 0.315),
            (0.068, 0.350), (0.120, 0.395), (0.210, 0.445), (0.300, 0.520), (0.360, 0.620), (0.392, 0.740), (0.405, 0.860),
            (0.410, 0.950), (0.406, 0.985), (0.380, 0.985), (0.372, 0.930), (0.360, 0.800), (0.330, 0.670), (0.270, 0.570),
            (0.180, 0.505), (0.080, 0.470), (0.000, 0.462),
        ]

    @staticmethod
    def cup_handle():
        return [(0.410, 0.885), (0.505, 0.905), (0.585, 0.835), (0.585, 0.705), (0.500, 0.605), (0.290, 0.530)]

    @staticmethod
    def shield_outline(width, height, shoulder=0.40, samples=12):
        w = 0.5 * float(width)
        top = 0.5 * float(height)
        bottom = -0.5 * float(height)
        side = top - float(shoulder) * float(height)
        curve = RoundsMath.bezier3((w, side), (w, side - 0.48 * (side - bottom)), (0.40 * w, bottom + 0.10 * float(height)), (0.0, bottom), samples)
        right = np.vstack([[(w, top)], curve])
        left = right[::-1][1:].copy()
        left[:, 0] *= -1.0
        return np.vstack([right, left])

    @staticmethod
    def leaf_outline(length, width, angle_deg, center, samples=9, belly=0.18):
        half = 0.5 * float(length)
        xs = np.linspace(-half, half, int(samples))
        hw = 0.5 * float(width) * (1.0 - (xs / half) ** 2) * (1.0 - float(belly) * xs / half)
        pts = np.vstack([np.stack([xs, hw], axis=1), np.stack([xs[::-1][1:-1], -hw[::-1][1:-1]], axis=1)])
        a = math.radians(float(angle_deg))
        rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        return pts @ rot.T + np.asarray(center, np.float64)

    @staticmethod
    def drip_outline(width, length, bulb=0.48, neck=0.7, samples=10):
        w = 0.5 * float(width)
        top = 0.5 * float(length)
        rb = float(bulb) * float(width)
        cb = -top + rb
        arc = [(rb * math.cos(a), cb + rb * math.sin(a)) for a in np.linspace(0.0, -math.pi, int(samples))]
        right = [(w, top), (w * 0.98, 0.2 * top), (float(neck) * w, cb + 1.3 * rb)]
        left = [(-x, y) for x, y in reversed(right)]
        return np.array(right + arc + left)

    @staticmethod
    def fluted_outline(radius, staves, bulge, sharpness=0.55, samples=12):
        n = int(staves) * int(samples)
        groove = -0.5 * math.pi - math.pi / float(staves)
        a = groove + np.arange(n) * (2.0 * math.pi / n)
        t = (np.arange(n) % int(samples)) / float(samples)
        bump = np.sin(np.pi * t) ** float(sharpness)
        r = float(radius) - float(bulge) + float(bulge) * bump
        return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)

    @staticmethod
    def rounded_triangle(width, height, divisions=3):
        corners = np.array([(-0.5 * width, 0.5 * height), (0.0, -0.5 * height), (0.5 * width, 0.5 * height)], np.float64)
        pts = []
        for k in range(3):
            a = corners[k]
            b = corners[(k + 1) % 3]
            for j in range(int(divisions)):
                pts.append(a + (b - a) * (j / float(divisions)))
        return np.array(pts)

    @staticmethod
    def vase_profile(height, belly_radius, foot_radius, neck_radius, lip_radius, belly_at=0.44, shoulder_at=0.86):
        h = float(height)
        br = float(belly_radius)
        fr = float(foot_radius)
        nr = float(neck_radius)
        lr = float(lip_radius)
        return [
            (0.0, 0.0), (fr, 0.0), (fr * 1.06, 0.026 * h), (fr * 1.03, 0.058 * h), (fr * 0.96, 0.078 * h),
            (0.5 * (fr + br) * 1.02, 0.16 * h), (br * 0.97, (belly_at - 0.13) * h), (br, belly_at * h),
            (br * 0.97, (belly_at + 0.14) * h), (0.5 * (br + nr) * 1.04, (0.5 * (belly_at + shoulder_at) + 0.06) * h),
            (nr * 1.04, shoulder_at * h), (nr, (shoulder_at + 0.05) * h), (lr * 0.99, 0.95 * h), (lr, h), (0.0, h),
        ]

    @staticmethod
    def lid_profile(radius, z, dome, lip=0.035):
        r = float(radius)
        d = float(dome)
        return [
            (0.0, z), (r * 0.97, z), (r, z + 0.4 * lip), (r * 0.98, z + lip), (r * 0.8, z + lip + 0.45 * d),
            (r * 0.48, z + lip + 0.85 * d), (r * 0.18, z + lip + d), (0.0, z + lip + 1.02 * d),
        ]

    @staticmethod
    def cushion_profile(radius, z, thickness, dome):
        r = float(radius)
        t = float(thickness)
        return [
            (0.0, z), (r * 0.86, z), (r * 0.97, z + 0.16 * t), (r, z + 0.45 * t), (r * 0.96, z + 0.80 * t),
            (r * 0.80, z + t), (r * 0.40, z + t + 0.75 * dome), (0.0, z + t + dome),
        ]

    @staticmethod
    def lantern_profiles():
        base = [(0.0, 0.050), (0.255, 0.050), (0.262, 0.082), (0.238, 0.118), (0.224, 0.160), (0.232, 0.192), (0.0, 0.192)]
        roof = [(0.0, 0.652), (0.238, 0.652), (0.300, 0.672), (0.312, 0.698), (0.282, 0.716), (0.180, 0.790), (0.104, 0.848), (0.076, 0.884), (0.082, 0.902), (0.060, 0.926), (0.0, 0.932)]
        return base, roof

    @staticmethod
    def sector_normals(rot, a0_deg, a1_deg):
        m = RoundsMath.matrix(rot)
        a0 = math.radians(float(a0_deg))
        a1 = math.radians(float(a1_deg))
        n0 = m @ np.array([math.sin(a0), -math.cos(a0), 0.0])
        n1 = m @ np.array([-math.sin(a1), math.cos(a1), 0.0])
        return n0, n1

    @staticmethod
    def ring_path(radius, z, xy=(0.0, 0.0)):
        return {"shape": "circle", "r": float(radius), "plane": "XY", "at": [float(xy[0]), float(xy[1]), float(z)]}


class RoundsPalette:
    @staticmethod
    def roles():
        return {
            "cream": {"color": "#FFFBF4", "finish": "satin"},
            "caramel": {"color": "#C48E62", "finish": "satin"},
            "ink": {"color": "#3B281E", "finish": "matte"},
            "outline": {"color": "#4A3327", "finish": "matte"},
            "honey": {"color": "#E8B04B", "finish": "gloss"},
            "gold": {"color": "#D9A441", "finish": "gloss"},
            "pink": {"color": "#F2B8C6", "finish": "satin"},
            "mint": {"color": "#A8D8C8", "finish": "satin"},
            "sky": {"color": "#A9CBEA", "finish": "satin"},
            "glow": {"color": "#FFE9B8", "finish": "emissive"},
        }

    @staticmethod
    def scheme(variant="house"):
        if variant == "pastel":
            return {"body": "cream", "accent": "pink", "dark": "outline", "metal": "gold", "warm": "honey", "glow": "glow", "stripe": "pink", "drum": "sky", "band": "mint", "soft": "mint", "roof": "pink"}
        return {"body": "cream", "accent": "caramel", "dark": "ink", "metal": "gold", "warm": "honey", "glow": "glow", "stripe": "caramel", "drum": "cream", "band": "caramel", "soft": "caramel", "roof": "caramel"}


class RoundsRecipes:
    def __init__(self, engine=None, engine_dir=None):
        self.sf = engine if engine is not None else EngineLocator.load(engine_dir)

    def smooth_profile(self, profile, iterations=2):
        prof = np.asarray(profile, np.float64)
        if not iterations:
            return prof.copy()
        on_axis = prof[0, 0] < 1e-6 and prof[-1, 0] < 1e-6
        return self.sf.Polygon2D.chaikin(prof, int(iterations), not on_axis)

    def puck(self, b, radius, height, rim=0.5, z=0.0, xy=(0.0, 0.0), dome=0.0, bulge=0.0, recess=0.0, role=None, fillet=0.0, op="union", collide=False, detail=False, smooth=2):
        edge = float(np.clip(rim, 0.0, 0.5)) * float(height)
        parts = {"z": float(z), "top": float(z) + float(height) + float(dome), "shoulder": float(z) + float(height), "radius": float(radius), "height": float(height), "edge": edge, "xy": tuple(xy), "dome": float(dome)}
        if dome or bulge or recess:
            prof = self.smooth_profile(RoundsMath.puck_profile(radius, height, rim, dome, bulge, recess, z), smooth)
            parts.update({"kind": "lathe", "params": {"profile": prof}, "loc": (xy[0], xy[1], 0.0), "profile": prof, "side": RoundsMath.side_curve(prof)})
            parts["node"] = b.lathe(prof, loc=(xy[0], xy[1], 0.0), smooth=0, role=role, fillet=fillet, op=op, collide=collide, detail=detail)
        else:
            loc = (xy[0], xy[1], float(z) + 0.5 * float(height))
            parts.update({"kind": "round_cyl", "params": {"radius": float(radius), "height": float(height), "edge": edge}, "loc": loc, "side": np.array([(float(radius), float(z) + edge), (float(radius), float(z) + float(height) - edge)])})
            parts["node"] = b.round_cyl(float(radius), float(height), edge=edge, loc=loc, role=role, fillet=fillet, op=op, collide=collide, detail=detail)
        return parts

    def torus_trim(self, b, host_radius, z, minor=0.025, sink=0.3, xy=(0.0, 0.0), role=None, fillet=0.01, rot=(0.0, 0.0, 0.0)):
        major = float(host_radius) + float(minor) * (1.0 - 2.0 * float(sink))
        node = b.torus(major, float(minor), loc=(xy[0], xy[1], float(z)), rot=rot, role=role, fillet=fillet)
        return {"node": node, "major": major, "minor": float(minor), "z": float(z)}

    def pedestal(self, b, tiers, z=0.0, xy=(0.0, 0.0), trim_role=None, trim_minor=0.025, trim_sink=0.3, joint_fillet=0.02, trim_fillet=0.01, collide=True):
        made = []
        trims = []
        previous = None
        for index, tier in enumerate(tiers):
            height = float(tier["height"])
            rim = float(tier.get("rim", 0.5))
            start = float(z) if previous is None else previous["shoulder"] - rim * height
            part = self.puck(b, tier["radius"], height, rim=rim, z=start, xy=xy, dome=tier.get("dome", 0.0), bulge=tier.get("bulge", 0.0), recess=tier.get("recess", 0.0) if previous is None else 0.0, role=tier.get("role"), fillet=0.0 if previous is None else joint_fillet, collide=collide and index == 0)
            if previous is not None and trim_role is not None:
                trims.append(self.torus_trim(b, part["radius"], previous["shoulder"] + 0.6 * previous["dome"], minor=trim_minor, sink=trim_sink, xy=xy, role=trim_role, fillet=trim_fillet))
            made.append(part)
            previous = part
        return {"tiers": made, "trims": trims, "top": previous["top"], "radius": previous["radius"]}

    def raised_band(self, b, part, role, z0, z1, rise=0.003, edge=0.002, fillet=0.002, name="band"):
        params = dict(part["params"])
        with b.group(name, fillet=fillet) as group:
            self.grown(b, part["kind"], params, role, part["loc"], (0.0, 0.0, 0.0), rise)
            b.cut(point=(0.0, 0.0, float(z0)), normal=(0.0, 0.0, -1.0), fillet=edge)
            b.cut(point=(0.0, 0.0, float(z1)), normal=(0.0, 0.0, 1.0), fillet=edge)
        return group

    def grown(self, b, kind, params, role, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), grow=5e-5):
        g = float(grow)
        if kind == "torus":
            return b.torus(params["major"], params["minor"] + g, loc=loc, rot=rot, role=role)
        if kind == "round_cyl":
            return b.round_cyl(params["radius"] + g, params["height"] + 2.0 * g, edge=params.get("edge", 0.0) + g, loc=loc, rot=rot, role=role)
        if kind == "sphere":
            return b.sphere(params["radius"] + g, loc=loc, role=role)
        if kind == "round_cone":
            return b.round_cone(params["a"], params["b"], params["radius_a"] + g, params["radius_b"] + g, role=role)
        if kind == "lathe":
            return b.lathe(self.sf.Shapes.offset(np.asarray(params["profile"], np.float64), g), loc=loc, rot=rot, smooth=0, role=role)
        raise ValueError("cannot grow node kind {}".format(kind))

    def paint_sectors(self, b, kind, params, role, segments=8, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), offset_deg=0.0, grow=0.002, edge=0.0015, fillet=0.0015, name="paint"):
        step = 360.0 / float(segments)
        made = []
        for k in range(0, int(segments), 2):
            a0 = float(offset_deg) + k * step
            n0, n1 = RoundsMath.sector_normals(rot, a0, a0 + step)
            with b.group("{}_{}".format(name, k), fillet=fillet) as group:
                self.grown(b, kind, params, role, loc, rot, grow)
                b.cut(point=loc, normal=tuple(n0), fillet=edge)
                b.cut(point=loc, normal=tuple(n1), fillet=edge)
            made.append(group)
        return made

    def paint_band(self, b, kind, params, role, z0, z1, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), grow=5e-5, name="band"):
        with b.group(name) as group:
            self.grown(b, kind, params, role, loc, rot, grow)
            b.cut(point=(0.0, 0.0, float(z0)), normal=(0.0, 0.0, -1.0))
            b.cut(point=(0.0, 0.0, float(z1)), normal=(0.0, 0.0, 1.0))
        return group

    def lathe_relief(self, b, curve, outline, relief, center, azimuth=-90.0, depth_in=0.02, role=None, edge=0.006, fillet=0.008, xy=(0.0, 0.0), detail=False, name="relief"):
        loops = self.sf.Shapes.resolve2d(outline)
        vlo = float(center[1] + loops[:, 1].min())
        vhi = float(center[1] + loops[:, 1].max())
        margin = max(0.03, 3.0 * float(relief))
        win = RoundsMath.window(curve, vlo - margin, vhi + margin)
        shell = RoundsMath.shell(win, relief, depth_in)
        reach = float(win[:, 0].max()) + float(relief) + 0.05
        theta = float(azimuth) + 90.0
        m = RoundsMath.matrix((0.0, 0.0, theta))
        loc = m @ np.array([float(center[0]), -0.5 * reach, 0.0]) + np.array([xy[0], xy[1], float(center[1])])
        with b.group(name, fillet=fillet) as group:
            b.lathe(shell, loc=(xy[0], xy[1], 0.0), smooth=0, role=role, detail=detail)
            b.extrude2d(loops, depth=reach, edge=0.0, plane="XZ", loc=tuple(loc), rot=(0.0, 0.0, theta), op="intersect", fillet=edge)
        return group

    def numbered_plinth(self, b, digit="1", radius=0.31, height=0.32, base_radius=0.36, base_height=0.13, z=0.0, rim=0.25, base_rim=0.5, bulge=0.012, dome=0.008, recess=0.02, role=None, trim_role=None, plaque_role=None, digit_role=None, plaque_size=(0.2, 0.135), plaque_relief=0.014, digit_height=0.1, digit_relief=0.016, digit_depth=0.035, digit_puff=0.006, font=None, trim_minor=0.022, collide=True, name="plinth"):
        with b.group(name):
            tiers = [{"radius": base_radius, "height": base_height, "rim": base_rim, "recess": recess, "dome": 0.5 * float(dome), "role": role}, {"radius": radius, "height": height, "rim": rim, "bulge": bulge, "dome": dome, "role": role}]
            stack = self.pedestal(b, tiers, z=z, trim_role=trim_role, trim_minor=trim_minor, collide=collide)
            top = stack["tiers"][-1]
            low = max(top["z"] + top["edge"], stack["tiers"][0]["shoulder"] + 2.0 * float(trim_minor))
            zc = 0.5 * (low + top["shoulder"] - top["edge"])
            face = float(radius) + float(bulge)
            plaque = None
            if plaque_role is not None and plaque_size:
                outline = {"shape": "rounded_rect", "w": float(plaque_size[0]), "h": float(plaque_size[1]), "r": 0.24 * min(plaque_size)}
                plaque = self.lathe_relief(b, top["side"], outline, plaque_relief, (0.0, zc), role=plaque_role, edge=0.006, fillet=0.007, name=name + "_plaque")
                face += float(plaque_relief)
            digit_node = None
            if digit:
                thick = float(digit_depth) + 2.0 * float(digit_puff)
                y = -(face + float(digit_relief) - 0.5 * thick)
                digit_node = b.text(str(digit), font=font, height=digit_height, depth=digit_depth, puff=digit_puff, plane="XZ", loc=(0.0, y, zc), role=digit_role, fillet=0.005)
        return {"stack": stack, "plaque": plaque, "digit": digit_node, "top": stack["top"], "radius": float(radius), "digit_z": zc}

    def trophy_cup(self, b, height=0.95, z=0.0, width=1.0, role=None, lip=True, lip_role=None, handles=True, handle_role=None, handle_radius=0.028, smooth=2, fillet=0.0, collide=True):
        h = float(height)
        prof = self.smooth_profile(RoundsMath.scaled(RoundsMath.cup_profile(), h * float(width), h, z), smooth)
        parts = {"profile": prof, "outer": RoundsMath.outer_curve(prof), "height": h, "z": float(z), "width": float(width)}
        parts["cup"] = b.lathe(prof, smooth=0, role=role, fillet=fillet, collide=collide)
        if lip:
            parts["lip"] = b.torus(0.394 * h * float(width), 0.026 * h, loc=(0.0, 0.0, float(z) + 0.972 * h), role=lip_role or role, fillet=0.012)
        if handles:
            path = [(x * h * float(width), 0.0, float(z) + v * h) for x, v in RoundsMath.cup_handle()]
            parts["handles"] = b.tube(path, float(handle_radius) * h, closed=False, role=handle_role or role, fillet=0.022, mirror_x=True)
        return parts

    def shield_relief(self, b, curve, center, width=0.27, height=0.29, relief=0.016, inset=0.022, inner_relief=0.026, role=None, inner_role=None, emblem_role=None, emblem_size=0.32, azimuth=-90.0, name="shield"):
        outline = {"shape": "points", "points": RoundsMath.shield_outline(width, height).tolist(), "smooth": 2}
        parts = {"plate": self.lathe_relief(b, curve, outline, relief, center, azimuth=azimuth, role=role, edge=0.006, fillet=0.008, name=name)}
        if inner_role is not None:
            inner = dict(outline)
            inner["offset"] = -float(inset)
            parts["field"] = self.lathe_relief(b, curve, inner, inner_relief, center, azimuth=azimuth, role=inner_role, edge=0.005, fillet=0.005, name=name + "_field")
        if emblem_role is not None:
            star = {"shape": "star", "r_out": float(emblem_size) * 0.5 * float(width), "r_in": float(emblem_size) * 0.25 * float(width), "points": 5, "smooth": 3}
            parts["emblem"] = self.lathe_relief(b, curve, star, inner_relief + 0.012, (center[0], center[1] + 0.06 * float(height)), azimuth=azimuth, role=emblem_role, edge=0.005, fillet=0.004, name=name + "_emblem")
        return parts

    def laurel(self, b, curve, base, control, tip, leaves=6, length=0.09, width=0.036, relief=0.014, spread=34.0, taper=0.25, depth_in=0.02, azimuth=-90.0, role=None, edge=0.006, fillet=0.008, mirror=True, xy=(0.0, 0.0), name="laurel"):
        outlines = []
        for k in range(int(leaves)):
            t = (k + 0.5) / float(leaves)
            (u, v), tangent = RoundsMath.bezier2(base, control, tip, t)
            side = 1.0 if k % 2 == 0 else -1.0
            angle = math.degrees(math.atan2(tangent[1], tangent[0])) + float(spread) * side
            scale = 1.0 - float(taper) * t
            heading = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
            centre = np.array([u, v]) + heading * (0.42 * float(length) * scale)
            outlines.append(RoundsMath.leaf_outline(float(length) * scale, float(width) * scale, angle, centre))
        every = np.vstack(outlines)
        margin = max(0.03, 3.0 * float(relief))
        win = RoundsMath.window(curve, float(every[:, 1].min()) - margin, float(every[:, 1].max()) + margin)
        shell = RoundsMath.shell(win, relief, depth_in)
        reach = float(win[:, 0].max()) + float(relief) + 0.05
        theta = float(azimuth) + 90.0
        loc = RoundsMath.matrix((0.0, 0.0, theta)) @ np.array([0.0, -0.5 * reach, 0.0]) + np.array([xy[0], xy[1], 0.0])
        leaves_made = []
        with b.group(name, fillet=fillet) as group:
            b.lathe(shell, loc=(xy[0], xy[1], 0.0), smooth=0, role=role)
            with b.group(name + "_mask", op="intersect", fillet=edge):
                for pts in outlines:
                    leaves_made.append(b.extrude2d({"shape": "points", "points": pts.tolist(), "smooth": 1}, depth=reach, edge=0.0, plane="XZ", loc=tuple(loc), rot=(0.0, 0.0, theta), mirror_x=mirror))
        return {"group": group, "leaves": leaves_made, "outlines": outlines}

    def trophy(self, b, cup_height=1.15, digit="1", z=0.0, cup_role=None, plinth_role=None, trim_role=None, plaque_role=None, digit_role=None, shield_role=None, shield_inner_role=None, emblem_role=None, laurel_role=None, plinth=True, handles=True, shield=True, laurel=True, font=None, leaves=6):
        h = float(cup_height)
        parts = {}
        seat = float(z)
        if plinth:
            lip = 0.41 * h
            parts["plinth"] = self.numbered_plinth(b, digit=digit, radius=0.85 * lip, height=0.31 * h, base_radius=0.98 * lip, base_height=0.13 * h, z=z, rim=0.2, role=plinth_role, trim_role=trim_role, plaque_role=plaque_role, digit_role=digit_role, plaque_size=(0.21 * h, 0.145 * h), plaque_relief=0.012 * h, digit_height=0.105 * h, digit_relief=0.014 * h, digit_depth=0.032 * h, trim_minor=0.021 * h, font=font)
            seat = parts["plinth"]["top"] - 0.012
        with b.group("cup", fillet=0.02):
            cup = self.trophy_cup(b, height=h, z=seat, role=cup_role, handles=handles, handle_radius=0.032)
            parts["cup"] = cup
            if shield:
                parts["shield"] = self.shield_relief(b, cup["outer"], (0.0, seat + 0.705 * h), width=0.27 * h, height=0.30 * h, relief=0.014 * h, inset=0.02 * h, inner_relief=0.022 * h, role=shield_role or cup_role, inner_role=shield_inner_role, emblem_role=emblem_role)
            if laurel:
                parts["laurel"] = self.laurel(b, cup["outer"], (0.05 * h, seat + 0.545 * h), (0.215 * h, seat + 0.57 * h), (0.262 * h, seat + 0.875 * h), leaves=leaves, length=0.085 * h, width=0.034 * h, relief=0.012 * h, role=laurel_role or cup_role)
        parts["top"] = seat + 0.998 * h
        return parts

    def coin(self, b, radius, thickness, center, rot=(90.0, 0.0, 0.0), edge=0.3, dome=None, rim=True, rim_minor=None, rim_inset=None, emblem="star", emblem_size=0.48, emblem_relief=None, double_sided=True, role=None, rim_role=None, emblem_role=None, font=None, fillet=0.0, collide=False, smooth=2):
        r = float(radius)
        t = float(thickness)
        d = float(dome if dome is not None else 0.03 * r)
        m = RoundsMath.matrix(rot)
        c = np.asarray(center, np.float64)
        prof = self.smooth_profile(RoundsMath.coin_profile(r, t, edge, d), smooth)
        parts = {"profile": prof, "body": b.lathe(prof, loc=tuple(c), rot=rot, smooth=0, role=role, fillet=fillet, collide=collide)}
        minor = float(rim_minor if rim_minor is not None else 0.075 * r)
        inset = float(rim_inset if rim_inset is not None else 0.15 * r)
        sides = (1.0, -1.0) if double_sided else (1.0,)
        if rim:
            parts["rims"] = [b.torus(r - inset, minor, loc=tuple(c + m @ np.array([0.0, 0.0, s * (0.5 * t - 0.55 * minor + 0.12 * d)])), rot=rot, role=rim_role or role, fillet=0.008) for s in sides]
        relief = float(emblem_relief if emblem_relief is not None else 0.16 * t) + 0.85 * d
        if emblem:
            depth = t + 2.0 * relief if double_sided else 0.5 * t + relief
            loc = c if double_sided else c + m @ np.array([0.0, 0.0, 0.25 * t + 0.5 * relief])
            size = float(emblem_size) * (r - inset - minor)
            if emblem in ("star", "heart"):
                shape = {"shape": "star", "r_out": size, "r_in": 0.5 * size, "points": 5, "smooth": 3} if emblem == "star" else {"shape": "heart", "size": 1.7 * size, "smooth": 2}
                parts["emblem"] = b.extrude2d(shape, depth=depth, edge=min(0.35 * relief + 0.004, 0.45 * depth), puff=0.25 * relief, plane="XY", loc=tuple(loc), rot=rot, role=emblem_role or rim_role or role, fillet=0.006)
            else:
                parts["emblem"] = b.text(str(emblem), font=font, height=1.25 * size, depth=depth - 0.012, puff=0.006, plane="XY", loc=tuple(loc), rot=rot, role=emblem_role or rim_role or role, fillet=0.005)
        return parts

    def lifebuoy(self, b, major=0.2, minor=0.062, center=(0.0, 0.0, 0.0), rot=(90.0, 0.0, 0.0), segments=8, role=None, stripe_role=None, fillet=0.012, offset_deg=None):
        parts = {"ring": b.torus(float(major), float(minor), loc=tuple(center), rot=rot, role=role, fillet=fillet)}
        if stripe_role is not None and segments >= 2:
            offset = float(offset_deg) if offset_deg is not None else -0.5 * 360.0 / float(segments)
            parts["stripes"] = self.paint_sectors(b, "torus", {"major": float(major), "minor": float(minor)}, stripe_role, segments, tuple(center), rot, offset, name="buoy")
        return parts

    def fluted_drum(self, b, radius=0.5, height=0.6, staves=16, bulge=0.045, sharpness=0.55, edge=None, z=0.0, xy=(0.0, 0.0), samples=12, smooth=2, role=None, fillet=0.0, collide=False):
        outline = RoundsMath.fluted_outline(radius, staves, float(bulge) * float(radius), sharpness, samples)
        e = float(edge if edge is not None else min(0.1 * float(radius), 0.12 * float(height)))
        node = b.extrude2d({"shape": "points", "points": outline.tolist(), "smooth": int(smooth)}, depth=float(height), edge=e, plane="XY", loc=(xy[0], xy[1], float(z) + 0.5 * float(height)), role=role, fillet=fillet, collide=collide)
        return {"node": node, "z": float(z), "top": float(z) + float(height), "radius": float(radius), "groove": float(radius) * (1.0 - float(bulge)), "edge": e}

    def cushion(self, b, radius, z, thickness=0.14, dome=0.035, role=None, fillet=0.0, smooth=2):
        prof = RoundsMath.cushion_profile(radius, z, thickness, dome)
        return {"node": b.lathe(prof, smooth=smooth, role=role, fillet=fillet), "top": float(z) + float(thickness) + float(dome)}

    def padded_drum(self, b, radius=0.52, height=0.62, base_radius=0.78, base_height=0.14, staves=16, bulge=0.045, z=0.0, base_role=None, drum_role=None, collar_role=None, cushion_role=None, buoy=True, buoy_role=None, buoy_stripe_role=None, buoy_azimuth=-128.0, collide=True):
        parts = {"base": self.puck(b, base_radius, base_height, rim=0.5, z=z, dome=0.012, recess=0.02, role=base_role, collide=collide)}
        parts["base"]["top"] = parts["base"]["shoulder"]
        drum_z = parts["base"]["top"] - 0.04
        parts["drum"] = self.fluted_drum(b, radius, height, staves=staves, bulge=bulge, z=drum_z, role=drum_role, fillet=0.025, collide=collide)
        top = parts["drum"]["top"]
        if collar_role is not None:
            parts["collar_low"] = self.torus_trim(b, radius, parts["base"]["top"] + 0.004, minor=0.03, sink=0.42, role=collar_role, fillet=0.012)
        if cushion_role is not None:
            parts["cushion"] = self.cushion(b, radius - 0.015, top - 0.035, thickness=0.14, dome=0.035, role=cushion_role, fillet=0.02)
        if collar_role is not None:
            parts["collar_top"] = self.torus_trim(b, radius, top - 0.012, minor=0.034, sink=0.42, role=collar_role, fillet=0.012)
        if buoy:
            major = 0.19
            minor = 0.062
            a = math.radians(float(buoy_azimuth))
            radial = np.array([math.cos(a), math.sin(a), 0.0])
            tangent = np.array([-math.sin(a), math.cos(a), 0.0])
            lean = math.radians(9.0)
            normal = RoundsMath.unit(radial * math.cos(lean) + np.array([0.0, 0.0, math.sin(lean)]))
            up = np.cross(normal, tangent)
            centre = radial * (float(radius) + minor + 0.02) + np.array([0.0, 0.0, parts["base"]["top"] + major + minor - 0.012])
            rot = RoundsMath.euler_from_axes(tangent, up, normal)
            parts["buoy"] = self.lifebuoy(b, major, minor, tuple(centre), rot, 8, role=buoy_role, stripe_role=buoy_stripe_role, fillet=0.014)
        parts["top"] = parts["cushion"]["top"] if "cushion" in parts else top
        return parts

    def lantern(self, b, height=1.12, z=0.0, bars=6, frame_role=None, glass_role=None, roof_role=None, metal_role=None, foot_role=None, hanger=True, collide=True):
        s = float(height) / 1.12
        base, roof = RoundsMath.lantern_profiles()
        parts = {"foot": self.puck(b, 0.30 * s, 0.08 * s, rim=0.5, z=z, dome=0.006 * s, recess=0.012 * s, role=foot_role or roof_role, collide=collide)}
        parts["base"] = b.lathe(RoundsMath.scaled(base, s, s, z), smooth=2, role=frame_role, fillet=0.02)
        parts["glass"] = self.puck(b, 0.186 * s, 0.50 * s, rim=0.06, z=z + 0.172 * s, bulge=0.022 * s, role=glass_role, fillet=0.01, collide=collide)
        parts["bands"] = [b.round_cyl(0.238 * s, 0.056 * s, edge=0.024 * s, loc=(0.0, 0.0, z + zc * s), role=frame_role, fillet=0.014) for zc in (0.206, 0.640)]
        parts["bars"] = []
        for k in range(int(bars)):
            a = math.radians(-90.0 + 360.0 / float(bars) * (k + 0.5))
            direction = (math.cos(a), math.sin(a))
            path = [(rr * s * direction[0], rr * s * direction[1], z + zz * s) for rr, zz in ((0.214, 0.215), (0.232, 0.422), (0.214, 0.630))]
            parts["bars"].append(b.tube(path, 0.024 * s, closed=False, role=frame_role, fillet=0.014))
        parts["roof"] = b.lathe(RoundsMath.scaled(roof, s, s, z), smooth=2, role=roof_role, fillet=0.016)
        parts["finial"] = b.sphere(0.05 * s, loc=(0.0, 0.0, z + 0.96 * s), role=metal_role, fillet=0.02)
        if hanger:
            parts["hanger"] = b.torus(0.066 * s, 0.021 * s, loc=(0.0, 0.0, z + 1.06 * s), rot=(90.0, 0.0, 0.0), role=metal_role, fillet=0.014)
        parts["top"] = z + (1.147 if hanger else 1.01) * s
        return parts

    def vase(self, b, height=0.78, belly_radius=0.42, foot_radius=None, neck_radius=None, lip_radius=None, belly_at=0.44, shoulder_at=0.86, z=0.0, role=None, lip=True, lip_role=None, lip_minor=None, smooth=2, collide=True):
        br = float(belly_radius)
        fr = float(foot_radius if foot_radius is not None else 0.58 * br)
        nr = float(neck_radius if neck_radius is not None else 0.72 * br)
        lr = float(lip_radius if lip_radius is not None else 0.80 * br)
        prof = self.smooth_profile(RoundsMath.scaled(RoundsMath.vase_profile(height, br, fr, nr, lr, belly_at, shoulder_at), 1.0, 1.0, z), smooth)
        parts = {"profile": prof, "outer": RoundsMath.outer_curve(prof), "top": float(z) + float(height), "lip_radius": lr}
        parts["body"] = b.lathe(prof, smooth=0, role=role, collide=collide)
        if lip:
            minor = float(lip_minor if lip_minor is not None else 0.045 * br)
            parts["lip"] = b.torus(lr - 0.4 * minor, minor, loc=(0.0, 0.0, float(z) + float(height) - 0.35 * minor), role=lip_role or role, fillet=0.01)
        return parts

    def lid(self, b, radius, z, dome=0.11, knob_radius=0.06, role=None, knob_role=None, fillet=0.012):
        prof = RoundsMath.lid_profile(radius, z, dome)
        parts = {"lid": b.lathe(prof, smooth=2, role=role, fillet=fillet)}
        top = float(z) + 0.035 + float(dome)
        if knob_radius:
            parts["neck"] = b.round_cyl(0.45 * float(knob_radius), 0.6 * float(knob_radius), edge=0.15 * float(knob_radius), loc=(0.0, 0.0, top + 0.1 * float(knob_radius)), role=knob_role or role, fillet=0.02)
            parts["knob"] = b.sphere(float(knob_radius), loc=(0.0, 0.0, top + 0.95 * float(knob_radius)), role=knob_role or role, fillet=0.022)
            top += 1.95 * float(knob_radius)
        parts["top"] = top
        return parts

    def pour_glaze(self, b, curve, z_top, z_edge, thickness=0.018, depth_in=0.025, drips=7, drip_length=(0.08, 0.17), drip_width=(0.05, 0.075), seed=3, role=None, edge=0.008, fillet=0.012, drip_fillet=0.022, xy=(0.0, 0.0), name="glaze"):
        rng = random.Random(int(seed))
        z_low = float(z_edge) - float(max(drip_length)) - 0.04
        win = RoundsMath.window(curve, z_low, z_top)
        shell = RoundsMath.shell(win, thickness, depth_in)
        reach = float(win[:, 0].max()) + float(thickness) + 0.05
        band = float(z_top) - float(z_edge) + 0.1
        parts = {"drips": []}
        with b.group(name, fillet=fillet) as group:
            parts["shell"] = b.lathe(shell, loc=(xy[0], xy[1], 0.0), smooth=0, role=role)
            with b.group(name + "_mask", op="intersect", fillet=edge):
                parts["band"] = b.round_box((2.0 * reach + 0.2, 2.0 * reach + 0.2, band), radius=0.0, loc=(xy[0], xy[1], float(z_edge) + 0.5 * band))
                for k in range(int(drips)):
                    azimuth = 360.0 / float(drips) * (k + rng.uniform(-0.28, 0.28)) - 90.0
                    length = rng.uniform(drip_length[0], drip_length[1]) + 0.04
                    width = rng.uniform(drip_width[0], drip_width[1])
                    theta = azimuth + 90.0
                    loc = RoundsMath.matrix((0.0, 0.0, theta)) @ np.array([0.0, -0.5 * reach, 0.0]) + np.array([xy[0], xy[1], float(z_edge) + 0.04 - 0.5 * length])
                    outline = {"shape": "points", "points": RoundsMath.drip_outline(width, length).tolist(), "smooth": 2}
                    parts["drips"].append(b.extrude2d(outline, depth=reach, edge=0.0, plane="XZ", loc=tuple(loc), rot=(0.0, 0.0, theta), fillet=drip_fillet))
        parts["group"] = group
        return parts

    def ring_marker(self, b, radius=0.72, tube=0.05, disc=0.036, inner=0.62, z=0.0, dome=0.014, recess=0.018, pad=0.02, ring_role=None, disc_role=None, inner_role=None, icon="star", icon_size=0.24, icon_role=None, icon_relief=0.016, arrow=True, arrow_role=None):
        r = float(radius)
        t = float(tube)
        parts = {"disc": self.puck(b, r - 0.7 * t, disc, rim=0.42, z=z, dome=dome, recess=recess, role=disc_role)}
        top = parts["disc"]["top"]
        if inner_role is not None:
            parts["pad"] = self.puck(b, float(inner) * r, float(pad) + float(dome), rim=0.45, z=parts["disc"]["shoulder"] - 0.006, dome=0.7 * float(dome), role=inner_role, fillet=0.006)
            top = parts["pad"]["top"]
        parts["ring"] = b.torus(r - t, t, loc=(0.0, 0.0, z + t), role=ring_role, fillet=0.018)
        if icon:
            size = float(icon_size) * r
            depth = 0.036
            loc = (0.0, 0.0, top + float(icon_relief) - 0.5 * depth)
            if icon == "heart":
                shape = {"shape": "heart", "size": 1.7 * size, "smooth": 2}
            else:
                shape = {"shape": "star", "r_out": size, "r_in": 0.52 * size, "points": 5, "smooth": 3}
            parts["icon"] = b.extrude2d(shape, depth=depth, edge=0.013, puff=0.006, plane="XY", loc=loc, role=icon_role, fillet=0.01)
        if arrow:
            w = 0.24 * r
            h = 0.2 * r
            outline = {"shape": "points", "points": RoundsMath.rounded_triangle(w, h).tolist(), "smooth": 3}
            loc = (0.0, r - t, z + 2.0 * t + 0.5 * h - 0.03)
            parts["arrow"] = b.extrude2d(outline, depth=0.06, edge=0.024, puff=0.008, plane="XZ", loc=loc, role=arrow_role or ring_role, fillet=0.016)
        return parts


class ToolRunner:
    def __init__(self, engine_dir, blender=None):
        self.engine_dir = engine_dir
        self.blender = blender or bpy.app.binary_path
        self.validate_sculpt = os.path.join(engine_dir, "validate_sculpt.py")
        self.render_sculpt = os.path.join(engine_dir, "render_sculpt.py")
        self.validate_prop = os.path.normpath(os.path.join(engine_dir, "..", "..", "..", "prop-forge", "scripts", "blender", "validate_prop.py"))

    def call(self, script, args, factory=True, timeout=1200):
        command = [self.blender, "-b"] + (["--factory-startup"] if factory else []) + ["-P", script, "--"] + [str(a) for a in args]
        started = time.perf_counter()
        try:
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            output = (done.stdout or "") + (done.stderr or "")
            code = done.returncode
        except subprocess.TimeoutExpired as error:
            output = "timeout: {}".format(error)
            code = -1
        return {"code": code, "output": output, "seconds": round(time.perf_counter() - started, 1)}

    @staticmethod
    def counts(text, tag):
        found = re.findall(r"{} fail=(\d+) warn=(\d+)".format(re.escape(tag)), text)
        if not found:
            return None, None
        return int(found[-1][0]), int(found[-1][1])

    def sculpt_qa(self, blend, high, json_path):
        args = ["--blend", blend, "--json", json_path]
        if high and os.path.isfile(high):
            args += ["--high", high]
        run = self.call(self.validate_sculpt, args)
        fail, warn = self.counts(run["output"], "SCULPT_QA")
        lines = [line for line in run["output"].splitlines() if line[:5] in ("OK   ", "WARN ", "FAIL ", "INFO ")]
        return {"fail": fail, "warn": warn, "seconds": run["seconds"], "code": run["code"], "lines": lines, "json": json_path}

    def prop_contract(self, folder):
        run = self.call(self.validate_prop, ["--blend", folder])
        results = {}
        current = None
        for line in run["output"].splitlines():
            if line.startswith("== "):
                current = os.path.splitext(os.path.basename(line[3:].strip()))[0]
                results[current] = {"lines": []}
            elif current is not None and line.startswith("RESULT "):
                fail, warn = self.counts(line, "RESULT")
                results[current].update({"fail": fail, "warn": warn})
            elif current is not None and line[:4] in ("OK  ", "WARN", "FAIL"):
                results[current]["lines"].append(line)
        return {"files": results, "seconds": run["seconds"], "code": run["code"]}

    def render(self, folder, out, qa_json, views=4, res=900):
        run = self.call(self.render_sculpt, ["--blend", folder, "--out", out, "--qa", qa_json, "--views", views, "--res", res], timeout=2400)
        summary = [line for line in run["output"].splitlines() if line.startswith("SCULPT_RENDER") or line.startswith("RENDER")]
        manifest = os.path.join(out, "render_manifest.json")
        data = {}
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as handle:
                data = json.load(handle)
        return {"lines": summary, "seconds": run["seconds"], "code": run["code"], "manifest": data}


class RoundsDemo:
    def __init__(self, out_dir, engine_dir=None, only=None, set_name="1nfx_round", variant="house", voxel=None, budget_scale=1.0, qa=True, render=True, views=4, res=900):
        self.out = os.path.abspath(out_dir)
        self.recipes = RoundsRecipes(engine_dir=engine_dir)
        self.engine_dir = os.path.dirname(os.path.abspath(self.recipes.sf.__file__))
        self.only = [k for k in (only or []) if k]
        self.set_name = str(set_name)
        self.variant = str(variant)
        self.scheme = RoundsPalette.scheme(self.variant)
        self.voxel = voxel
        self.budget_scale = float(budget_scale)
        self.qa = bool(qa)
        self.render = bool(render)
        self.views = int(views)
        self.res = int(res)
        self.palette = self.recipes.sf.SetPalette(self.set_name, RoundsPalette.roles())

    def catalog(self):
        return [
            ("trophy", self.build_trophy),
            ("pedestal", self.build_pedestal),
            ("drum", self.build_drum),
            ("lantern", self.build_lantern),
            ("honeypot", self.build_honeypot),
            ("marker", self.build_marker),
        ]

    def builder(self, key, budget, voxel, default_role, archetype, colliders="auto", lod_dist=120.0):
        return self.recipes.sf.SculptBuilder("{}_{}".format(self.set_name, key), budget=max(500, int(round(budget * self.budget_scale))), lod_dist=lod_dist, colliders=colliders, set_name=self.set_name, archetype=archetype, voxel=float(self.voxel or voxel), palette=self.palette, default_role=default_role)

    def build_trophy(self):
        s = self.scheme
        b = self.builder("trophy", 4000, 0.005, s["metal"], "trophy", lod_dist=150.0)
        self.recipes.trophy(b, cup_height=1.15, digit="1", cup_role=s["metal"], plinth_role=s["dark"], trim_role=s["metal"], plaque_role=s["body"], digit_role=s["metal"], shield_inner_role=s["body"], laurel_role=s["metal"])
        return b

    def build_pedestal(self):
        s = self.scheme
        b = self.builder("pedestal", 2600, 0.005, s["body"], "pedestal")
        stack = self.recipes.pedestal(b, [{"radius": 0.60, "height": 0.24, "rim": 0.35, "role": s["body"]}, {"radius": 0.49, "height": 0.30, "rim": 0.25, "role": s["body"]}], trim_role=s["metal"], trim_minor=0.026)
        base = stack["tiers"][0]
        self.recipes.paint_band(b, "round_cyl", {"radius": base["radius"], "height": base["height"], "edge": base["edge"]}, s["band"], 0.096, 0.146, loc=(0.0, 0.0, 0.5 * base["height"]))
        with b.group("coin", fillet=0.03):
            self.recipes.coin(b, 0.30, 0.10, (0.0, 0.0, stack["top"] - 0.05 + 0.30), role=s["warm"], rim_role=s["metal"], emblem="star", emblem_role=s["body"], collide=True)
        return b

    def build_drum(self):
        s = self.scheme
        b = self.builder("drum", 3600, 0.005, s["drum"], "drum")
        self.recipes.padded_drum(b, base_role=s["accent"], drum_role=s["drum"], collar_role=s["warm"], cushion_role=s["soft"] if self.variant == "pastel" else s["accent"], buoy_role=s["body"], buoy_stripe_role=s["stripe"] if self.variant == "pastel" else "pink")
        return b

    def build_lantern(self):
        s = self.scheme
        b = self.builder("lantern", 2200, 0.004, s["dark"], "lantern")
        self.recipes.lantern(b, frame_role=s["dark"], glass_role=s["glow"], roof_role=s["roof"], metal_role=s["metal"], foot_role=s["roof"])
        return b

    def build_honeypot(self):
        s = self.scheme
        b = self.builder("honeypot", 2600, 0.004, s["body"], "pot")
        pot = self.recipes.vase(b, height=0.78, belly_radius=0.42, foot_radius=0.25, neck_radius=0.30, lip_radius=0.335, belly_at=0.43, shoulder_at=0.86, role=s["body"], lip=False)
        self.recipes.pour_glaze(b, pot["outer"], 0.77, 0.56, role=s["warm"])
        self.recipes.lid(b, 0.35, 0.745, dome=0.11, knob_radius=0.062, role=s["accent"], knob_role=s["metal"])
        return b

    def build_marker(self):
        s = self.scheme
        b = self.builder("marker", 1500, 0.005, s["accent"], "marker", colliders=0, lod_dist=100.0)
        self.recipes.ring_marker(b, ring_role=s["glow"], disc_role=s["accent"], inner_role=s["body"], icon="star", icon_role=s["warm"], arrow_role=s["glow"])
        return b

    def run(self):
        os.makedirs(self.out, exist_ok=True)
        report = {"out": self.out, "set": self.set_name, "variant": self.variant, "blender": bpy.app.version_string, "engine": self.engine_dir, "props": []}
        for key, method in self.catalog():
            if self.only and key not in self.only:
                continue
            started = time.perf_counter()
            entry = {"key": key}
            try:
                result = method().build(self.out)
                metrics = result["metrics"]
                entry.update({"id": result["id"], "blend": result["blend"], "high_blend": result["high_blend"], "tris": result["tris"], "budget": result["budget"], "size_m": result["size_m"], "materials": result["materials"], "colliders": result["colliders"], "warnings": result["warnings"], "surface_m2": metrics["surface_m2"], "tris_per_m2": metrics["tris_per_m2"], "dihedral_deg": metrics["dihedral_deg"], "surface_dev_mm": metrics["surface_dev_mm"], "flipped_faces": metrics["flipped_faces"], "inverted_faces": metrics["inverted_faces"], "shells": metrics["shells"], "timings": result["timings"]})
            except Exception as error:
                entry["error"] = "{}: {}".format(type(error).__name__, error)
                print("ROUNDS_FAIL {} {}".format(key, entry["error"]), flush=True)
            entry["seconds"] = round(time.perf_counter() - started, 2)
            report["props"].append(entry)
            print("ROUNDS_PROP " + json.dumps({k: entry.get(k) for k in ("id", "tris", "budget", "surface_m2", "tris_per_m2", "seconds", "error")}), flush=True)
        built = [e for e in report["props"] if "error" not in e]
        runner = ToolRunner(self.engine_dir)
        if self.qa and built:
            qa_dir = os.path.join(self.out, "qa")
            os.makedirs(qa_dir, exist_ok=True)
            merged = {"drawables": [], "fail": 0, "warn": 0}
            for entry in built:
                path = os.path.join(qa_dir, entry["id"] + ".json")
                entry["sculpt_qa"] = runner.sculpt_qa(entry["blend"], entry["high_blend"], path)
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as handle:
                        data = json.load(handle)
                    merged["drawables"].extend(data.get("drawables", []))
                    merged["fail"] += int(data.get("fail", 0))
                    merged["warn"] += int(data.get("warn", 0))
                print("ROUNDS_QA {} SCULPT_QA fail={} warn={}".format(entry["id"], entry["sculpt_qa"]["fail"], entry["sculpt_qa"]["warn"]), flush=True)
                for line in entry["sculpt_qa"]["lines"]:
                    if line.startswith("WARN") or line.startswith("FAIL"):
                        print("  " + line, flush=True)
            report["qa_json"] = os.path.join(qa_dir, "qa_all.json")
            with open(report["qa_json"], "w", encoding="utf-8") as handle:
                json.dump(merged, handle, indent=1)
            contract = runner.prop_contract(self.out)
            report["contract_seconds"] = contract["seconds"]
            for entry in built:
                entry["contract"] = contract["files"].get(entry["id"], {"fail": None, "warn": None, "lines": []})
                print("ROUNDS_CONTRACT {} RESULT fail={} warn={}".format(entry["id"], entry["contract"].get("fail"), entry["contract"].get("warn")), flush=True)
        if self.render and built:
            render_dir = os.path.join(self.out, "renders")
            rendered = runner.render(self.out, render_dir, report.get("qa_json", ""), self.views, self.res)
            report["render"] = {"dir": render_dir, "lines": rendered["lines"], "seconds": rendered["seconds"], "lineup": rendered["manifest"].get("lineup", {})}
            for line in rendered["lines"]:
                print(line, flush=True)
        failures = sum(1 for e in report["props"] if "error" in e)
        qa_fail = sum((e.get("sculpt_qa", {}).get("fail") or 0) for e in built)
        qa_warn = sum((e.get("sculpt_qa", {}).get("warn") or 0) for e in built)
        contract_fail = sum((e.get("contract", {}).get("fail") or 0) for e in built)
        contract_warn = sum((e.get("contract", {}).get("warn") or 0) for e in built)
        report["summary"] = {"props": len(report["props"]), "build_fail": failures, "qa_fail": qa_fail, "qa_warn": qa_warn, "contract_fail": contract_fail, "contract_warn": contract_warn}
        report_path = os.path.join(self.out, "rounds_report.json")
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        print("ROUNDS_RESULT props={} build_fail={} qa_fail={} qa_warn={} contract_fail={} contract_warn={} report={}".format(len(report["props"]), failures, qa_fail, qa_warn, contract_fail, contract_warn, report_path), flush=True)
        return failures + qa_fail + contract_fail


class RoundsCli:
    @staticmethod
    def parse(argv):
        parser = argparse.ArgumentParser(prog="rounds.py")
        parser.add_argument("--out", required=True)
        parser.add_argument("--only", default="")
        parser.add_argument("--engine-dir", dest="engine_dir", default="")
        parser.add_argument("--set", dest="set_name", default="1nfx_round")
        parser.add_argument("--variant", default="house", choices=["house", "pastel"])
        parser.add_argument("--voxel", type=float, default=None)
        parser.add_argument("--budget-scale", dest="budget_scale", type=float, default=1.0)
        parser.add_argument("--no-qa", dest="no_qa", action="store_true")
        parser.add_argument("--no-render", dest="no_render", action="store_true")
        parser.add_argument("--views", type=int, default=4)
        parser.add_argument("--res", type=int, default=900)
        return parser.parse_args(argv)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = RoundsCli.parse(argv)
    demo = RoundsDemo(args.out, engine_dir=args.engine_dir or None, only=[k.strip() for k in args.only.split(",")], set_name=args.set_name, variant=args.variant, voxel=args.voxel, budget_scale=args.budget_scale, qa=not args.no_qa, render=not args.no_render, views=args.views, res=args.res)
    failures = demo.run()
    if bpy.app.background:
        sys.stdout.flush()
        os._exit(1 if failures else 0)
    return failures


if __name__ == "__main__":
    main()
