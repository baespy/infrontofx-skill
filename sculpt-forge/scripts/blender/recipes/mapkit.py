import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector


class MapKitEngine:
    @staticmethod
    def candidates(explicit=None):
        roots = []
        if explicit:
            roots.append(explicit)
        if os.environ.get("SCULPT_FORGE_DIR"):
            roots.append(os.environ["SCULPT_FORGE_DIR"])
        here = globals().get("__file__")
        if here:
            roots.append(os.path.dirname(os.path.dirname(os.path.abspath(here))))
        starts = [os.getcwd()]
        if bpy.data.filepath:
            starts.append(os.path.dirname(bpy.data.filepath))
        for start in starts:
            folder = os.path.abspath(start)
            for _ in range(8):
                roots.append(os.path.join(folder, ".claude", "skills", "infrontofx", "sculpt-forge", "scripts", "blender"))
                roots.append(os.path.join(folder, "sculpt-forge", "scripts", "blender"))
                parent = os.path.dirname(folder)
                if parent == folder:
                    break
                folder = parent
        roots.append(os.path.join(os.path.expanduser("~"), ".claude", "skills", "infrontofx", "sculpt-forge", "scripts", "blender"))
        found = []
        for root in roots:
            found.extend([root, os.path.join(root, ".."), os.path.join(root, "scripts", "blender")])
        return found

    @staticmethod
    def folder(explicit=None):
        for path in MapKitEngine.candidates(explicit):
            if path and os.path.isfile(os.path.join(path, "sculpt_sweep.py")):
                return os.path.normpath(os.path.abspath(path))
        raise RuntimeError("sculpt_sweep.py not found; pass engine_dir=<skill>/sculpt-forge/scripts/blender or set SCULPT_FORGE_DIR")

    @staticmethod
    def load(name, explicit=None):
        folder = MapKitEngine.folder(explicit)
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)


class MapKitPalette:
    @staticmethod
    def colors(variant="house"):
        table = {
            "paving": "#D3C5B1",
            "stone": "#EEE4D5",
            "step": "#6A5143",
            "band": "#C48E62",
            "gold": "#D9A441",
            "shell": "#F7EFE4",
            "wood": "#C48E62",
            "slat": "#6B4E3E",
            "metal": "#4A3327",
            "post": "#3B281E",
            "soil": "#4B3B2E",
            "panel": "#E0BE92",
            "cushion": "#C48E62",
            "glow": "#E8B04B",
            "lamp": "#FFF1D6",
        }
        if variant == "pastel":
            table.update({"band": "#A8D8C8", "panel": "#A9CBEA", "cushion": "#F2B8C6", "wood": "#DDB08A", "step": "#7C6A70", "slat": "#857480", "gold": "#E8B04B"})
        return table

    @staticmethod
    def specs():
        return {
            "paving": ("normal_spec.sps", 2.4, False, {"bumpiness": 0.9, "spec_int": 0.3, "spec_falloff": 48.0, "spec_fresnel": 0.9}, True, "paver"),
            "stone": ("default.sps", 2.0, False, {}, False, "stone"),
            "step": ("default.sps", 2.0, False, {}, True, "stone"),
            "band": ("default.sps", 2.0, False, {}, True, "stone"),
            "shell": ("default.sps", 2.0, False, {}, False, "stone"),
            "cushion": ("default.sps", 2.0, False, {}, False, "stone"),
            "wood": ("default.sps", 1.2, False, {}, False, "wood"),
            "slat": ("normal_spec.sps", 1.2, False, {"bumpiness": 1.0, "spec_int": 0.2, "spec_falloff": 32.0, "spec_fresnel": 0.85}, False, "slat"),
            "soil": ("default.sps", 1.0, False, {}, False, "stone"),
            "gold": ("default.sps", 2.0, False, {}, False, "swatch"),
            "metal": ("default.sps", 2.0, False, {}, False, "swatch"),
            "post": ("default.sps", 2.0, False, {}, False, "swatch"),
            "panel": ("default.sps", 2.0, False, {}, False, "swatch"),
            "glow": ("emissivenight.sps", 2.0, True, {"emissive_mult": 1.6}, False, "swatch"),
            "lamp": ("emissivenight.sps", 2.0, True, {"emissive_mult": 2.2}, False, "swatch"),
        }

    @staticmethod
    def grains():
        return {"stone": (0.04, 5), "step": (0.06, 7), "band": (0.05, 13), "shell": (0.022, 17), "cushion": (0.02, 23), "soil": (0.14, 19)}


class MapKitTextures:
    def __init__(self, sweep_module, prefix, tex_dir):
        self.SweepBuilder = sweep_module.SweepBuilder
        self.prefix = prefix
        self.tex_dir = tex_dir

    def stem(self, name):
        return os.path.join(self.tex_dir, self.prefix + "_" + name)

    def wood(self, name, base, size=256, seed=3):
        rng = np.random.default_rng(seed)
        rows = (np.arange(size, dtype=np.float64) + 0.5) / size
        noise = self.SweepBuilder.periodic_noise(size, 8, rng) * 0.6 + self.SweepBuilder.periodic_noise(size, 32, rng) * 0.4
        grain = np.sin(2.0 * math.pi * (rows[:, None] * 11.0 + 0.45 * noise))
        streak = self.SweepBuilder.periodic_noise(size, 64, rng)
        rgb = np.array(self.SweepBuilder.hex_rgb(base))[None, None, :] * (1.0 + 0.05 * grain[..., None] + 0.03 * noise[..., None] + 0.02 * streak[..., None])
        return self.SweepBuilder.save_png(self.stem(name) + "_d.png", np.concatenate([rgb, np.ones((size, size, 1))], -1))

    def slats(self, name, base, size=256, boards=8, groove=0.07, seed=9):
        rng = np.random.default_rng(seed)
        cols = (np.arange(size, dtype=np.float64) + 0.5) / size * boards
        frac = cols - np.floor(cols)
        edge = np.minimum(frac, 1.0 - frac)
        h = np.clip((edge - groove * 0.5) / groove, 0.0, 1.0)
        h = h * h * (3.0 - 2.0 * h)
        tone = rng.uniform(-0.05, 0.05, boards)[np.floor(cols).astype(int) % boards]
        noise = self.SweepBuilder.periodic_noise(size, 16, rng) * 0.5 + self.SweepBuilder.periodic_noise(size, 64, rng) * 0.5
        base_rgb = np.array(self.SweepBuilder.hex_rgb(base))
        shade = (0.55 + 0.45 * h)[None, :] * (1.0 + tone[None, :] + 0.035 * noise)
        rgb = base_rgb[None, None, :] * shade[..., None]
        height = np.broadcast_to(h[None, :], (size, size)) + 0.01 * noise
        gx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
        gy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
        nrm = np.stack([-gx * 4.0, -gy * 4.0, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        spec = 0.10 + 0.14 * height
        ones = np.ones((size, size, 1))
        stem = self.stem(name)
        return {
            "DiffuseSampler": self.SweepBuilder.save_png(stem + "_d.png", np.concatenate([rgb, ones], -1)),
            "BumpSampler": self.SweepBuilder.save_png(stem + "_n.png", np.concatenate([nrm * 0.5 + 0.5, ones], -1)),
            "SpecSampler": self.SweepBuilder.save_png(stem + "_s.png", np.concatenate([np.repeat(spec[..., None], 3, -1), ones], -1)),
        }


class KidneyOutline:
    def __init__(self, length, width, dent=0.36, spread=0.8):
        self.a = length * 0.5
        self.b = width * 0.5
        self.dent = dent
        self.spread = spread

    def radius(self, theta):
        c, s = math.cos(theta), math.sin(theta)
        ellipse = self.a * self.b / math.sqrt((self.b * c) ** 2 + (self.a * s) ** 2)
        d = (theta - math.pi * 0.5 + math.pi) % (2.0 * math.pi) - math.pi
        return ellipse * (1.0 - self.dent * math.exp(-(d / self.spread) ** 2))


class Taper:
    def __init__(self, r0, r1, hold=0.0, power=1.0):
        self.r0 = float(r0)
        self.r1 = float(r1)
        self.hold = float(hold)
        self.power = float(power)
        self.rmax = max(self.r0, self.r1)

    def __call__(self, s):
        x = min(max((s - self.hold) / max(1.0 - self.hold, 1e-9), 0.0), 1.0) ** self.power
        return (self.r0 + (self.r1 - self.r0) * x) / self.rmax


class Blend:
    def __init__(self, s0, s1):
        self.s0 = float(s0)
        self.s1 = float(s1)

    def __call__(self, s):
        t = min(max((s - self.s0) / max(self.s1 - self.s0, 1e-9), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)


class LeafShape:
    def __init__(self, length, width, height, droop, bow, twist_deg, sag):
        self.length = float(length)
        self.width = float(width)
        self.height = float(height)
        self.droop = float(droop)
        self.bow = float(bow)
        self.twist = math.radians(twist_deg)
        self.sag = float(sag)

    def centre(self, s):
        u = 2.0 * s - 1.0
        return np.array([(s - 0.5) * self.length, self.bow * (1.0 - u * u), self.height - self.droop * u * u])

    def axes(self, s):
        h = 1e-4
        t = self.centre(min(s + h, 1.0)) - self.centre(max(s - h, 0.0))
        t /= max(np.linalg.norm(t), 1e-12)
        n0 = np.array([-t[1], t[0], 0.0])
        n0 /= max(np.linalg.norm(n0), 1e-12)
        a = self.twist * (2.0 * s - 1.0)
        n = n0 * math.cos(a) + np.cross(t, n0) * math.sin(a)
        up = np.cross(t, n)
        up /= max(np.linalg.norm(up), 1e-12)
        return t, n, up

    def half_width(self, s):
        return self.width * 0.5 * max(math.sin(math.pi * min(max(s, 0.0), 1.0)), 0.0) ** 0.7

    def point(self, s, v, lift=0.0):
        t, n, up = self.axes(s)
        hw = self.half_width(s)
        dip = self.sag * (hw / max(self.width * 0.5, 1e-9)) * (1.0 - v * v)
        return self.centre(s) + n * hw * v + up * (lift - dip)


class MapKitLight:
    @staticmethod
    def point(pos, intensity=2.0, falloff=4.0, color=(255, 199, 122), exponent=32.0, corona=0.35):
        return {"type": "POINT", "position": [round(float(v), 4) for v in pos], "color": [int(c) for c in color], "intensity": float(intensity), "falloff": float(falloff), "falloff_exponent": float(exponent), "corona_size": float(corona), "corona_intensity": 0.35, "time_flags": "NIGHT", "cast_static_shadows": False}

    @staticmethod
    def lamp(pos, radius=3.5, g=0.35, self_radius=None, self_g=None):
        return {"pos": [float(v) for v in pos], "radius": float(radius), "g": float(g), "self_radius": float(radius if self_radius is None else self_radius), "self_g": float(g if self_g is None else self_g)}


class MapKitShape:
    def __init__(self, path_class):
        self.Path = path_class

    @staticmethod
    def matrix(pos, yaw_deg):
        return Matrix.Translation(Vector((float(pos[0]), float(pos[1]), float(pos[2])))) @ Matrix.Rotation(math.radians(float(yaw_deg)), 4, "Z")

    @staticmethod
    def to_world(points, pos, yaw_deg):
        p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        a = math.radians(float(yaw_deg))
        c, s = math.cos(a), math.sin(a)
        return np.stack([p[:, 0] * c - p[:, 1] * s + pos[0], p[:, 0] * s + p[:, 1] * c + pos[1], p[:, 2] + pos[2]], axis=1)

    @staticmethod
    def to_local(points, pos, yaw_deg):
        p = np.asarray(points, dtype=np.float64).reshape(-1, 3) - np.asarray(pos, dtype=np.float64)[None, :]
        a = -math.radians(float(yaw_deg))
        c, s = math.cos(a), math.sin(a)
        return np.stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c, p[:, 2]], axis=1)

    @staticmethod
    def circle(radius, z, count, center=(0.0, 0.0)):
        a = np.linspace(0.0, 2.0 * math.pi, int(count), endpoint=False)
        return np.stack([center[0] + radius * np.cos(a), center[1] + radius * np.sin(a), np.full(len(a), float(z))], axis=1)

    @staticmethod
    def chord_limit(radius, straight=1.5):
        r = np.asarray(radius, dtype=np.float64)
        return np.where(r <= 10.0, 0.25, np.where(r <= 30.0, 0.5, straight))

    @staticmethod
    def turn_limit(radius, turn_deg=4.0, sagitta=0.001):
        r = np.maximum(np.asarray(radius, dtype=np.float64), 1e-9)
        sag_angle = 2.0 * np.arccos(np.clip(1.0 - sagitta / r, -1.0, 1.0))
        return np.maximum(math.radians(turn_deg), sag_angle)

    @staticmethod
    def chord_count(radius, span_deg, turn_deg=4.0, minimum=3):
        span = math.radians(abs(span_deg))
        n_turn = math.ceil(span / float(MapKitShape.turn_limit(radius, turn_deg)) - 1e-9)
        n_len = math.ceil(span * radius / float(MapKitShape.chord_limit(radius)) - 1e-9)
        return int(max(minimum, n_turn, n_len))

    def resample_chord(self, points, closed=False, turn_deg=4.0, straight=1.5, corner_deg=25.0, sagitta=0.001):
        P = self.Path
        p = P.clean(points, closed)
        n = len(p)
        if n < 2:
            return p
        if n == 2:
            k = max(1, int(math.ceil(np.linalg.norm(p[1] - p[0]) / straight - 1e-9)))
            t = np.linspace(0.0, 1.0, k + 1)[:, None]
            return p[0] + (p[1] - p[0]) * t
        seg = P.segments(p, closed)
        slen = np.maximum(np.linalg.norm(seg, axis=1), 1e-12)
        turn = P.turns(p, closed)
        corner = turn > math.radians(corner_deg)
        smooth_turn = np.where(corner, 0.0, turn)
        nseg = len(seg)
        half = 0.5 * (smooth_turn[np.arange(nseg)] + smooth_turn[(np.arange(nseg) + 1) % n])
        radius = slen / np.maximum(half, 1e-12)
        cost = np.maximum(half / self.turn_limit(radius, turn_deg, sagitta), slen / self.chord_limit(radius, straight))
        corners = np.nonzero(corner)[0].tolist()
        if closed:
            if corners:
                shift = corners[0]
                p = np.roll(p, -shift, axis=0)
                seg = np.roll(seg, -shift, axis=0)
                cost = np.roll(cost, -shift)
                corners = [(c - shift) % n for c in corners]
                bounds = sorted(corners) + [n]
            else:
                bounds = [0, n]
        else:
            bounds = [0] + [c for c in corners if 0 < c < n - 1] + [n - 1]
        out = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            cs = np.concatenate([[0.0], np.cumsum(cost[a:b])])
            total = cs[-1]
            need = 3 if (closed and len(bounds) == 2) else 1
            k = max(need, int(math.ceil(total - 1e-9)))
            targets = np.linspace(0.0, total, k + 1)[1:-1]
            out.append(p[a % n][None])
            if len(targets):
                idx = np.clip(np.searchsorted(cs, targets, side="right") - 1, 0, b - a - 1)
                f = (targets - cs[idx]) / np.maximum(cs[idx + 1] - cs[idx], 1e-12)
                out.append(p[(a + idx) % n] + seg[(a + idx) % len(seg)] * f[:, None])
        if not closed:
            out.append(p[-1:])
        return np.vstack(out)

    def fillet_polyline(self, points, radius, step=0.01):
        p = np.asarray(points, dtype=np.float64)
        n = len(p)
        out = [p[0]]
        for i in range(1, n - 1):
            d1 = p[i] - p[i - 1]
            d2 = p[i + 1] - p[i]
            l1 = float(np.linalg.norm(d1))
            l2 = float(np.linalg.norm(d2))
            d1 /= max(l1, 1e-12)
            d2 /= max(l2, 1e-12)
            phi = math.acos(min(max(float(d1 @ d2), -1.0), 1.0))
            if phi < 1e-4:
                out.append(p[i])
                continue
            t = radius * math.tan(phi * 0.5)
            t = min(t, l1 * (0.5 if i > 1 else 0.95), l2 * (0.5 if i < n - 2 else 0.95))
            r = t / math.tan(phi * 0.5)
            a = p[i] - d1 * t
            b = p[i] + d2 * t
            bis = d2 - d1
            bis /= max(np.linalg.norm(bis), 1e-12)
            c = p[i] + bis * (r / math.cos(phi * 0.5))
            v0, v1 = a - c, b - c
            k = max(2, int(math.ceil(phi * r / step)))
            sp = math.sin(phi)
            for j in range(k + 1):
                tau = j / k
                out.append(c + v0 * (math.sin((1.0 - tau) * phi) / sp) + v1 * (math.sin(tau * phi) / sp))
        out.append(p[-1])
        return self.Path.clean(np.array(out))

    def right_normals(self, points, closed=False):
        t = self.Path.tangents(points, closed)
        n = np.stack([t[:, 1], -t[:, 0], np.zeros(len(t))], axis=1)
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def offset_open(self, points, distance, closed=False):
        p = self.Path.array(points)
        return p + self.right_normals(p, closed) * float(distance)

    def horizontal_frames(self, points, closed=False, fallback=(1.0, 0.0, 0.0)):
        p = self.Path.array(points)
        t = self.Path.tangents(p, closed)
        h = t[:, :2].copy()
        good = np.linalg.norm(h, axis=1) > 0.2
        if not good.any():
            fb = np.asarray(fallback[:2], dtype=np.float64)
            h[:] = fb / max(np.linalg.norm(fb), 1e-12)
        else:
            known = np.nonzero(good)[0]
            for i in np.nonzero(~good)[0]:
                h[i] = h[known[int(np.argmin(np.abs(known - i)))]]
        h /= np.maximum(np.linalg.norm(h, axis=1, keepdims=True), 1e-12)
        u = np.stack([-h[:, 1], h[:, 0], np.zeros(len(h))], axis=1)
        s = np.cross(t, u)
        s /= np.maximum(np.linalg.norm(s, axis=1, keepdims=True), 1e-12)
        u = np.cross(s, t)
        u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-12)
        return t, s, u

    def inside_other(self, centre, points, closed, limit, exclude):
        c = np.asarray(centre, dtype=np.float64)[:, :2]
        q = np.asarray(points, dtype=np.float64)[:, :2]
        cum = self.Path.cumulative(centre, closed)
        total = float(cum[-1])
        cum = cum[:len(c)]
        out = np.zeros(len(q), dtype=bool)
        for start in range(0, len(q), 256):
            block = q[start:start + 256]
            own = cum[start:start + 256]
            dist = np.linalg.norm(block[:, None, :] - c[None, :, :], axis=-1)
            gap = np.abs(own[:, None] - cum[None, :])
            if closed:
                gap = np.minimum(gap, total - gap)
            dist = np.where(gap > exclude, dist, np.inf)
            out[start:start + 256] = dist.min(axis=1) < limit
        return out

    @staticmethod
    def runs(mask, closed=False):
        m = np.asarray(mask, dtype=bool)
        n = len(m)
        if n == 0 or not m.any():
            return []
        if m.all():
            return [np.arange(n)]
        starts = [i for i in range(n) if m[i] and not m[i - 1]] if closed else [i for i in range(n) if m[i] and (i == 0 or not m[i - 1])]
        out = []
        for s in starts:
            idx = []
            i = s
            while m[i % n] and len(idx) < n:
                idx.append(i % n)
                i += 1
                if not closed and i >= n:
                    break
            out.append(np.array(idx))
        return out


class MapKitRecipes:
    def __init__(self, prefix="1nfx_mk", tex_dir=None, palette="house", engine_dir=None, turn_deg=4.0, embed=0.015):
        self.engine_dir = MapKitEngine.folder(engine_dir)
        self.sweep_module = MapKitEngine.load("sculpt_sweep", self.engine_dir)
        self.Path = self.sweep_module.SweepPath
        self.Profile = self.sweep_module.SweepProfile
        self.Mesh = self.sweep_module.SweepMesh
        self.prefix = prefix.lower()
        self.b = self.sweep_module.SweepBuilder(self.prefix, tex_dir)
        self.shape = MapKitShape(self.Path)
        self.palette = palette
        self.colors = MapKitPalette.colors(palette)
        self.turn_deg = float(turn_deg)
        self.straight = 1.5
        self.embed = float(embed)
        self.placements = {}
        self.lamps = {}
        self.notes = {}
        self.tex_dir = None
        if tex_dir:
            self.setup_roles(tex_dir)

    def setup_roles(self, tex_dir):
        os.makedirs(tex_dir, exist_ok=True)
        self.tex_dir = tex_dir
        self.b.tex_dir = tex_dir
        textures = MapKitTextures(self.sweep_module, self.prefix, tex_dir)
        grains = MapKitPalette.grains()
        for role, spec in MapKitPalette.specs().items():
            shader, tile, emissive, params, walkable, kind = spec
            color = self.colors[role]
            if kind == "paver":
                maps = self.b.paver_textures(tex_dir, 512, 2.4, (1.2, 0.6), 0.012, 0.012, color, 11)
            elif kind == "stone":
                grain, seed = grains.get(role, (0.04, 29))
                maps = {"DiffuseSampler": self.b.stone_texture(tex_dir, role, color, 256, grain, seed)}
            elif kind == "wood":
                maps = {"DiffuseSampler": textures.wood(role, color)}
            elif kind == "slat":
                maps = textures.slats(role, color)
            else:
                maps = {"DiffuseSampler": self.b.swatch(tex_dir, role, color)}
            self.b.add_role(role, shader, color, tile, emissive, maps, params, False, walkable)
        return self.b.roles

    def begin(self, name, collision="CONCRETE", budget=12000, lod=200.0, placements=None):
        sid = (self.prefix + "_" + name).lower()
        self.b.begin_shell(sid, collision, budget, lod, [])
        places = placements or [((0.0, 0.0, 0.0), 0.0)]
        self.placements[sid] = [(tuple(float(v) for v in pos), float(yaw)) for pos, yaw in places]
        self.lamps[sid] = []
        self.notes[sid] = {}
        return sid

    def current(self):
        return self.b.shell()["id"]

    def note(self, data):
        self.notes.setdefault(self.current(), {}).update(data)

    def add_light(self, light, lamp):
        sid = self.current()
        self.b.shells[sid]["lights"].append(light)
        self.lamps.setdefault(sid, []).append(lamp)
        return light

    @staticmethod
    def detail(*profiles):
        radii = [float(r) for p in profiles if p is not None for r in p.radii if r > 0.0]
        return min(radii) if radii else None

    def game_path(self, path, closed=False, turn=None):
        return self.shape.resample_chord(path, closed, turn or self.turn_deg, self.straight)

    def level_path(self, level, q, path, closed=False, detail=None, turn=None):
        if level == "game":
            return self.game_path(path, closed, turn)
        return q.path(path, closed, detail)

    def frames(self, pts, closed, frame):
        if isinstance(frame, str) and frame == "horizontal":
            return self.shape.horizontal_frames(pts, closed)
        return self.Path.frames(pts, closed, frame)

    def dome_rows(self, pts, P, t, s, u, q, end):
        sign = -1.0 if end == 0 else 1.0
        ring = P[end]
        c2 = ring.mean(axis=0)
        reff = max(float(np.linalg.norm(ring - c2, axis=1).mean()), 1e-4)
        k = max(2, q.arc(reff, math.pi * 0.5))
        phis = np.linspace(0.0, math.pi * 0.5, k + 1)[1:-1]
        order = phis[::-1] if end == 0 else phis
        rows = []
        for phi in order:
            rr = ring * math.cos(phi) + c2 * (1.0 - math.cos(phi))
            rows.append(pts[end] + rr[:, 0:1] * s[end] + rr[:, 1:2] * u[end] + sign * t[end] * reff * math.sin(phi))
        apex = pts[end] + c2[0] * s[end] + c2[1] * u[end] + sign * t[end] * reff
        return np.array(rows).reshape(-1, P.shape[1], 3), apex

    def rings(self, mesh, pts, profile, closed, caps, frame, q, role=None, profile_b=None, mix=None, scale=None):
        pts = self.Path.array(pts)
        n = len(pts)
        t, s, u = self.frames(pts, closed, frame)
        P0, roles, sharp, counts = profile.sample(q.arc)
        roles = [r if r is not None else role for r in roles]
        cum = self.Path.cumulative(pts, closed)
        sn = cum[:n] / max(float(cum[-1]), 1e-9)
        P = np.broadcast_to(P0, (n,) + P0.shape).copy()
        if profile_b is not None and mix is not None:
            Pb = profile_b.sample(q.arc, counts)[0]
            w = np.array([float(mix(x)) for x in sn])
            P = (1.0 - w)[:, None, None] * P0[None] + w[:, None, None] * Pb[None]
        if scale is not None:
            f = np.array([scale(x) for x in sn], dtype=np.float64).reshape(n, -1)
            P = P * f[:, None, :]
        grid = pts[:, None, :] + P[..., 0:1] * s[:, None, :] + P[..., 1:2] * u[:, None, :]
        ends = tuple(caps) if isinstance(caps, (tuple, list)) else (caps, caps)
        domes = [ends[0] == "round" and profile.closed and not closed, ends[1] == "round" and profile.closed and not closed]
        apex = [None, None]
        lead = 0
        if domes[0]:
            rows, apex[0] = self.dome_rows(pts, P, t, s, u, q, 0)
            lead = len(rows)
            grid = np.concatenate([rows, grid], axis=0)
        if domes[1]:
            rows, apex[1] = self.dome_rows(pts, P, t, s, u, q, -1)
            grid = np.concatenate([grid, rows], axis=0)
        idx, uu, vv = mesh.add_rings(grid, closed, profile.closed, roles, sharp)
        cap_role = roles[0]
        m = P.shape[1]
        cols = list(range(m)) + [0]
        if domes[0]:
            ring0 = np.stack([uu[0, cols], vv[0, :m + 1]], -1)
            d0 = float(np.linalg.norm(apex[0] - grid[0].mean(axis=0)))
            a0 = mesh.add_verts(apex[0][None])
            mesh.add_fan(a0, idx[0], (uu[0].mean() - d0, vv[0].mean()), ring0, cap_role, False)
        elif ends[0] == "flat" and not closed:
            mesh.add_cap(idx[0], P[0], cap_role)
        if domes[1]:
            ring1 = np.stack([uu[-1, cols], vv[-1, :m + 1]], -1)
            d1 = float(np.linalg.norm(apex[1] - grid[-1].mean(axis=0)))
            a1 = mesh.add_verts(apex[1][None])
            mesh.add_fan(a1, idx[-1], (uu[-1].mean() + d1, vv[-1].mean()), ring1, cap_role, True)
        elif ends[1] == "flat" and not closed:
            mesh.add_cap(idx[-1][::-1], P[-1][::-1], cap_role)
        return {"points": pts, "idx": idx, "grid": grid, "frames": (t, s, u), "profile": P, "lead": lead}

    def sweep(self, path, profile, closed=False, caps="flat", frame=(0.0, 0.0, 1.0), role=None, name="sweep", part=None, normal_mode="transfer", collide=False, collider_profile=None, turn=None, profile_b=None, mix=None, scale=None, dissolve=None):
        pt = part or self.b.new_part(name, normal_mode, True, dissolve)
        detail = self.detail(profile, profile_b)
        for level, q, mesh in self.b.levels(pt):
            pts = self.level_path(level, q, path, closed, detail, turn)
            self.rings(mesh, pts, profile, closed, caps, frame, q, role, profile_b, mix, scale)
        if collide:
            cm = self.Mesh(name + "_col")
            cp = collider_profile or profile
            self.rings(cm, self.b.coll.path(path, closed), cp, closed, "flat", frame, self.b.coll, role, None if collider_profile is not None else profile_b, mix, scale)
            self.b.add_collider(cm)
        return pt

    def band_profile(self, width, height=0.003, embed=0.004, face="up", role=None):
        w = width * 0.5
        if face == "up":
            pts = [(w, -embed), (w, height), (-w, height), (-w, -embed)]
        elif face == "out":
            pts = [(-embed, -w), (height, -w), (height, w), (-embed, w)]
        else:
            pts = [(embed, w), (-height, w), (-height, -w), (embed, -w)]
        return self.Profile.custom(pts, 0.0, False, role, None, "band")

    def trim(self, path, width=0.05, closed=False, frame=(0.0, 0.0, 1.0), face="up", height=0.003, embed=0.004, role="glow", name="trim", part=None, turn=None):
        pts = self.game_path(path, closed, turn)
        if len(pts) < 2:
            return part
        pt = part or self.b.new_part(name, "auto", False)
        self.rings(pt["game"], pts, self.band_profile(width, height, embed, face, role), closed, "none" if closed else "flat", frame, self.b.game, role)
        return pt

    def tube(self, path, radius, closed=False, caps="round", role="shell", name="tube", part=None, segments=None, taper=None, frame="rmf", collide=False, turn=None):
        prof = self.Profile.round(radius, role=role, segments=segments)
        return self.sweep(path, prof, closed, caps, frame, role, name, part, "transfer", collide, None, turn, None, None, taper)

    def slab(self, outline, thickness, edge_radius=0.3, edge_segments=None, bottom_radius=0.0, top_z=0.0, top_role="paving", rim_role="stone", bottom_role=None, top_spacing=1.25, name="slab", collide=True, turn=None):
        loop = self.Path.ccw(self.Path.lifted(outline, top_z))
        bottom = bottom_role or rim_role
        prof = self.Profile.slab_edge(thickness, edge_radius, bottom_radius, rim_role, bottom, edge_segments)
        pt = self.b.new_part(name, "transfer", True, [bottom])
        detail = self.detail(prof)
        for level, q, mesh in self.b.levels(pt):
            res = self.rings(mesh, self.level_path(level, q, loop, True, detail, turn), prof, True, "none", (0.0, 0.0, 1.0), q, rim_role)
            mesh.add_cdt(res["idx"][:, -1], res["grid"][:, -1, :2], top_z, True, top_spacing if level == "game" else None, top_role)
            mesh.add_cdt(res["idx"][:, 0], res["grid"][:, 0, :2], top_z - thickness, False, None, bottom)
        if collide:
            cm = self.Mesh(name + "_col")
            res = self.rings(cm, self.b.coll.path(loop, True), prof, True, "none", (0.0, 0.0, 1.0), self.b.coll, rim_role)
            cm.add_cdt(res["idx"][:, -1], res["grid"][:, -1, :2], top_z, True, None, rim_role)
            cm.add_cdt(res["idx"][:, 0], res["grid"][:, 0, :2], top_z - thickness, False, None, rim_role)
            self.b.add_collider(cm)
        return pt

    def prism_collider(self, outline, z0, z1, inset=0.04, name="prism"):
        loop = self.Path.ccw(self.Path.lifted(outline, z1))
        prof = self.Profile.custom([(-inset, z0 - z1), (0.0, z0 - z1), (0.0, 0.0), (-inset, 0.0)], 0.0, False, "stone")
        cm = self.Mesh(name + "_col")
        res = self.rings(cm, self.b.coll.path(loop, True), prof, True, "none", (0.0, 0.0, 1.0), self.b.coll, "stone")
        cm.add_cdt(res["idx"][:, -1], res["grid"][:, -1, :2], z1, True, None, "stone")
        cm.add_cdt(res["idx"][:, 0], res["grid"][:, 0, :2], z0, False, None, "stone")
        self.b.add_collider(cm)
        return cm

    def wall_collider(self, path, width, z0, z1, name="wall"):
        ground = self.Path.lifted(path, 0.0)
        w = width * 0.5
        prof = self.Profile.custom([(-w, z0), (w, z0), (w, z1), (-w, z1)], 0.0, True, "stone")
        cm = self.Mesh(name + "_col")
        self.rings(cm, self.b.coll.path(ground, False), prof, False, "flat", (0.0, 0.0, 1.0), self.b.coll, "stone")
        self.b.add_collider(cm)
        return cm

    def plaza_slab(self, outline, thickness=1.0, rim_radius=0.3, rim_segments=6, top_role="paving", rim_role="stone", bottom_role="stone", spacing=1.25, edge_inset=0.55, edge_width=0.05, edge_role="gold", name="plaza"):
        loop = self.Path.ccw(self.Path.lifted(outline, 0.0))
        pt = self.slab(loop, thickness, rim_radius, rim_segments, 0.0, 0.0, top_role, rim_role, bottom_role, spacing, name, True)
        if edge_inset:
            self.trim(self.Path.offset(loop, -edge_inset, True, 0.0), edge_width, True, (0.0, 0.0, 1.0), "up", 0.003, 0.004, edge_role, name + "_edge")
        self.note({"plaza": {"perimeter_m": round(self.Path.length(loop, True), 2), "thickness": thickness, "rim_radius": rim_radius}})
        return pt

    def inlaid_band(self, path, width=1.6, closed=False, line_width=0.05, z=0.0, band_role="band", line_role="gold", height=0.003, embed=0.004, name="band"):
        fine = self.Path.resample(self.Path.lifted(path, z), closed, 0.5, 0.04)
        band = self.b.new_part(name, "auto", False, [band_role])
        self.rings(band["game"], self.game_path(fine, closed), self.band_profile(width, height, embed, "up", band_role), closed, "none" if closed else "flat", (0.0, 0.0, 1.0), self.b.game, band_role)
        lines = None
        cut = 0
        for side in (1.0, -1.0):
            edge = self.shape.offset_open(fine, side * (width * 0.5 - line_width * 0.5), closed)
            edge[:, 2] = z + height
            keep = ~self.shape.inside_other(fine, edge, closed, width * 0.5 - line_width * 0.25, width * 3.0)
            cut += int((~keep).sum())
            for run in self.shape.runs(keep, closed):
                whole = closed and len(run) == len(edge)
                pts = edge[run]
                if len(pts) < 3 or self.Path.length(pts, whole) < 0.1:
                    continue
                lines = self.trim(pts, line_width, whole, (0.0, 0.0, 1.0), "up", height, embed + height, line_role, name + "_lines", lines)
        self.note({"band": {"width": width, "length_m": round(self.Path.length(fine, closed), 2), "closed": bool(closed), "edge_samples_cut": cut}})
        return band

    def figure_eight(self, center, length, width, z=0.0, step=0.02):
        count = max(64, int(math.ceil(2.0 * math.pi * max(length, width) / step)))
        t = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
        return np.stack([center[0] + length * 0.5 * np.sin(t), center[1] + width * np.sin(t) * np.cos(t), np.full(count, float(z))], axis=1)

    def s_curve(self, points, z=0.0, step=0.02):
        return self.Path.catmull_rom(points, False, 0.5, step, z)

    def curved_bench(self, radius=3.0, length=2.4, seat_h=0.45, depth=0.46, slats=4, slat_t=0.045, gap=0.018, supports=2, support_r=0.028, slat_role="wood", frame_role="post", name="bench", collide=True):
        e = self.embed
        half = math.degrees(length / (2.0 * radius))
        path = self.Path.arc((0.0, radius, 0.0), radius, -90.0 - half, -90.0 + half, seat_h - slat_t * 0.5, 0.2)
        w = (depth - (slats - 1) * gap) / slats
        prof = self.Profile.rounded_rect(w, slat_t, min(w, slat_t) * 0.45, role=slat_role, segments=2)
        part = self.b.new_part(name + "_slats")
        for i in range(slats):
            d = -depth * 0.5 + w * 0.5 + i * (w + gap)
            self.sweep(self.shape.offset_open(path, d), prof, False, "flat", (0.0, 0.0, 1.0), slat_role, name + "_slat", part)
        frames = self.b.new_part(name + "_frames")
        total = self.Path.length(path)
        reach = depth * 0.5 - 0.05
        z_top = seat_h - slat_t - support_r
        for k in range(supports):
            f = 0.16 + 0.68 * k / max(supports - 1, 1)
            p, d = self.Path.point_at(path, total * f)
            n = np.array([d[1], -d[0], 0.0])
            n /= max(np.linalg.norm(n), 1e-12)
            a = p[:2] - n[:2] * reach
            c = p[:2] + n[:2] * reach
            line = self.shape.fillet_polyline([(a[0], a[1], -e), (a[0], a[1], z_top), (c[0], c[1], z_top), (c[0], c[1], -e)], 0.07, 0.01)
            self.sweep(line, self.Profile.round(support_r, role=frame_role, segments=3), False, "flat", (float(d[0]), float(d[1]), 0.0), frame_role, name + "_frame", frames, turn=10.0)
        if collide:
            self.wall_collider(path, depth, -e, seat_h, name)
        self.note({"bench": {"kind": "slats", "radius": radius, "length": length, "seat_h": seat_h, "depth": depth, "slats": slats, "supports": supports}})
        return part

    def puffy_bench(self, radius=4.0, length=2.6, seat_h=0.44, depth=0.52, crown=0.03, top_r=0.13, shell_role="shell", cushion_role="cushion", glow=True, name="puffy", collide=True):
        e = self.embed
        half = math.degrees(length / (2.0 * radius))
        path = self.Path.arc((0.0, radius, 0.0), radius, -90.0 - half, -90.0 + half, 0.0, 0.2)
        d = depth * 0.5
        top = seat_h - 0.03
        pts = [(-d, -e), (d, -e), (d, top), (0.0, seat_h + crown), (-d, top)]
        radii = [0.0, 0.0, top_r, 0.8, top_r]
        roles = [shell_role, shell_role, cushion_role, cushion_role, shell_role]
        corner_roles = [shell_role, shell_role, cushion_role, cushion_role, cushion_role]
        prof = self.Profile(pts, radii, True, roles, corner_roles, "puffy_seat")
        part = self.sweep(path, prof, False, "round", (0.0, 0.0, 1.0), shell_role, name, collide=False)
        if glow:
            run = self.Path.trim(path, 0.25, self.Path.length(path) - 0.25)
            strip = self.shape.offset_open(run, d)
            strip[:, 2] = 0.055
            self.trim(strip, 0.03, False, (0.0, 0.0, 1.0), "out", 0.003, 0.004, "glow", name + "_glow")
        if collide:
            self.wall_collider(path, depth, -e, seat_h, name)
        self.note({"bench": {"kind": "puffy", "radius": radius, "length": length, "seat_h": seat_h, "depth": depth, "crown": crown}})
        return part

    def light_post(self, height=1.9, size=0.24, corner=0.035, bar_w=0.045, bar_gap=0.05, head_h=0.16, cap=0.06, body_role="post", lamp_role="lamp", intensity=2.0, falloff=4.0, name="post"):
        e = self.embed
        plinth = self.Path.rounded_rect((0.0, 0.0, 0.0), size + 0.10, size + 0.10, 0.07, 0.0, 1.0)
        self.slab(plinth, 0.08 + e, 0.025, 3, 0.0, 0.08, body_role, body_role, body_role, None, name + "_plinth", True)
        z_col = height - head_h - cap
        col = self.Profile.rounded_rect(size, size, corner, role=body_role)
        self.sweep(self.Path.line((0.0, 0.0, 0.06), (0.0, 0.0, z_col), 0.05), col, False, "flat", (0.0, -1.0, 0.0), body_role, name + "_column", collide=True)
        bars = self.b.new_part(name + "_bars", "auto", False)
        for side in (-1.0, 1.0):
            x = side * (bar_gap * 0.5 + bar_w * 0.5)
            bar = self.Profile.rounded_rect(bar_w, size + 0.02, 0.008, role=lamp_role)
            self.sweep(self.Path.line((x, 0.0, 0.32), (x, 0.0, z_col - 0.06), 0.05), bar, False, "flat", (0.0, -1.0, 0.0), lamp_role, name + "_bar", bars)
        head = self.Profile.rounded_rect(size - 0.012, size - 0.012, corner * 0.8, role=lamp_role)
        self.sweep(self.Path.line((0.0, 0.0, z_col - 0.002), (0.0, 0.0, height - cap + 0.004), 0.05), head, False, "flat", (0.0, -1.0, 0.0), lamp_role, name + "_head", normal_mode="auto")
        hat = self.Path.rounded_rect((0.0, 0.0, 0.0), size + 0.06, size + 0.06, 0.06, 0.0, 1.0)
        self.slab(hat, cap, 0.025, 3, 0.012, height, body_role, body_role, body_role, None, name + "_cap", False)
        pos = (0.0, 0.0, height - cap - head_h * 0.5)
        light = self.add_light(MapKitLight.point(pos, intensity, falloff), MapKitLight.lamp(pos, falloff * 0.9, 0.35, 0.55, 0.3))
        self.note({"post": {"height": height, "size": size, "bar_w": bar_w, "light": light}})
        return light

    def kidney_planter(self, length=4.6, width=2.3, dent=0.38, height=0.55, wall=0.10, lip_r=0.045, overhang=0.06, soil_drop=0.09, glow_w=0.03, lights=2, light_radius=3.2, role="shell", soil_role="soil", glow_role="glow", name="planter"):
        e = self.embed
        outline = self.Path.radial((0.0, 0.0, 0.0), KidneyOutline(length, width, dent).radius, 0.0, 0.02)
        lip = 2.0 * lip_r
        soil_z = height - soil_drop
        pts = [(-wall, -e), (0.0, -e), (0.0, height - lip), (overhang, height - lip), (overhang, height), (-wall, height), (-wall, soil_z)]
        radii = [0.0, 0.0, 0.008, lip_r, lip_r, 0.02, 0.0]
        prof = self.Profile(pts, radii, True, [role] * 7, [role] * 7, "planter", [None, None, 2, None, None, 2, None])
        part = self.b.new_part(name, "transfer", True, [soil_role])
        detail = self.detail(prof)
        for level, q, mesh in self.b.levels(part):
            res = self.rings(mesh, self.level_path(level, q, outline, True, detail), prof, True, "none", (0.0, 0.0, 1.0), q, role)
            j = int(np.argmin(np.linalg.norm(res["profile"][0] - np.array([-wall, soil_z]), axis=1)))
            mesh.add_cdt(res["idx"][:, j], res["grid"][:, j, :2], soil_z, True, 0.45 if level == "game" else None, soil_role)
        glow_z = height - lip - 0.012 - glow_w * 0.5
        self.trim(self.Path.lifted(outline, glow_z), glow_w, True, (0.0, 0.0, 1.0), "out", 0.003, 0.004, glow_role, name + "_glow")
        ring = self.Path.offset(outline, overhang + 0.32, True, 0.30)
        perimeter = self.Path.length(ring, True)
        made = []
        for k in range(max(0, int(lights))):
            p, _ = self.Path.point_at(ring, perimeter * (k + 0.5) / lights, True)
            made.append(self.add_light(MapKitLight.point(p, 1.6, light_radius), MapKitLight.lamp(p, light_radius, 0.32, light_radius * 0.6, 0.22)))
        self.prism_collider(self.Path.offset(outline, overhang, True, 0.0), -e, height, 0.05, name)
        self.note({"planter": {"length": length, "width": width, "dent": dent, "height": height, "lip_r": lip_r, "overhang": overhang, "glow_w": glow_w, "perimeter_m": round(self.Path.length(outline, True), 2), "lights": len(made)}})
        return part

    def dais_steps(self, radius=1.9, steps=4, rise=0.15, run=0.40, nosing=0.04, back=0.30, top_role="paving", step_role="step", strip_w=0.055, strip_setback=0.06, strip_role="glow", pad_every=1.7, pad_len=0.12, pad_h=0.06, pad_role="lamp", name="dais"):
        e = self.embed
        top_z = steps * rise
        disc = self.shape.circle(radius, 0.0, max(96, self.shape.chord_count(radius, 360.0, 1.0)))
        self.slab(disc, top_z + e, nosing, 4, 0.0, top_z, top_role, step_role, step_role, 0.9, name + "_top", True)
        prof = self.Profile.stairs(steps, rise, run, nosing, top_z, back, e, False, step_role, step_role, 4)
        r_out = radius + (steps - 1) * run
        part = self.b.new_part(name + "_steps", "transfer", True, [step_role])
        for level, q, mesh in self.b.levels(part):
            if level == "game":
                count = self.shape.chord_count(r_out, 360.0, self.turn_deg, 24)
            else:
                count = int(max(math.ceil(360.0 / 0.75), math.ceil(2.0 * math.pi * r_out / 0.08)))
            self.rings(mesh, self.shape.circle(radius, top_z, count), prof, True, "none", (0.0, 0.0, 1.0), q, step_role)
        cm = self.Mesh(name + "_steps_col")
        self.rings(cm, self.shape.circle(radius, top_z, 40), prof, True, "none", (0.0, 0.0, 1.0), self.b.coll, step_role)
        self.b.add_collider(cm)
        strips = None
        for k in range(steps):
            rad = radius + k * run - strip_setback - strip_w * 0.5
            loop = self.shape.circle(rad, top_z - k * rise, max(128, int(math.ceil(2.0 * math.pi * rad / 0.02))))
            strips = self.trim(loop, strip_w, True, (0.0, 0.0, 1.0), "up", 0.003, 0.004, strip_role, name + "_strips", strips)
        pads = None
        count_pads = 0
        for k in range(1, steps + 1):
            r_k = radius + (k - 1) * run
            zc = top_z - k * rise + rise * 0.42
            count = max(3, int(math.floor(2.0 * math.pi * r_k / pad_every)))
            phase = 0.5 if k % 2 == 0 else 0.0
            half = math.degrees(pad_len * 0.5 / r_k)
            for j in range(count):
                ang = 360.0 * (j + phase) / count
                arc = self.Path.arc((0.0, 0.0, 0.0), r_k, ang - half, ang + half, zc, 0.5)
                pads = self.trim(arc, pad_h, False, (0.0, 0.0, 1.0), "out", 0.003, 0.004, pad_role, name + "_pads", pads)
                count_pads += 1
        self.note({"dais": {"radius": radius, "outer_radius": round(r_out, 3), "steps": steps, "rise": rise, "run": run, "nosing": nosing, "top_z": top_z, "strip_w": strip_w, "pads": count_pads, "pad_size": [pad_len, pad_h]}})
        return part

    def ribcage_rail(self, path, height=1.05, top_r=0.035, curb_w=0.2, curb_h=0.1, baluster_r=0.015, pitch=0.28, rib_every=3.4, rib_r=(0.10, 0.05), rib_rise=0.85, rib_bend=1.25, rib_sweep=105.0, side=1.0, rib_role="shell", baluster_role="metal", curb_role="stone", glow=True, name="rail"):
        e = self.embed
        base = self.Path.resample(self.Path.lifted(path, 0.0), False, 1.0, 0.02)
        total = self.Path.length(base)
        curb = self.Profile.bullnose_curb(curb_w, curb_h + e, curb_h * 0.5, curb_h * 0.5, 0.5, role=curb_role).shifted(0.0, -e)
        self.sweep(base, curb, False, "round", (0.0, 0.0, 1.0), curb_role, name + "_curb")
        top = self.Path.extend(self.Path.lifted(base, height), 0.08, 0.08)
        self.tube(top, top_r, False, "round", rib_role, name + "_top")
        count_ribs = max(2, int(round(total / rib_every)) + 1)
        rib_s = [total * k / (count_ribs - 1) for k in range(count_ribs)]
        ribs = self.b.new_part(name + "_ribs")
        for s in rib_s:
            p, d = self.Path.point_at(base, s)
            n = np.array([d[1], -d[0], 0.0]) * side
            n /= max(np.linalg.norm(n), 1e-12)
            vertical = self.Path.line(p - np.array([0.0, 0.0, e]), p + np.array([0.0, 0.0, rib_rise]), 0.02)
            a = np.radians(np.linspace(180.0, 180.0 - rib_sweep, int(math.ceil(rib_sweep / 0.5)) + 1))
            centre = p + n * rib_bend + np.array([0.0, 0.0, rib_rise])
            bend = centre[None, :] + rib_bend * (np.cos(a)[:, None] * n[None, :] + np.sin(a)[:, None] * np.array([0.0, 0.0, 1.0])[None, :])
            line = self.Path.concat(vertical, bend)
            lengths = self.Path.length(vertical) / max(self.Path.length(line), 1e-9)
            self.tube(line, rib_r[0], False, ("flat", "round"), rib_role, name + "_rib", ribs, 3, Taper(rib_r[0], rib_r[1], lengths * 0.9, 1.2), (float(d[0]), float(d[1]), 0.0))
        balusters = self.b.new_part(name + "_balusters")
        count_bal = 0
        s = pitch * 0.5
        while s < total - pitch * 0.25:
            if min(abs(s - r) for r in rib_s) > 0.14:
                p, _ = self.Path.point_at(base, s)
                line = self.Path.line(p + np.array([0.0, 0.0, curb_h - 0.02]), p + np.array([0.0, 0.0, height]), 2.0)
                self.tube(line, baluster_r, False, "none", baluster_role, name + "_baluster", balusters, 3)
                count_bal += 1
            s += pitch
        if glow:
            strip = self.shape.offset_open(base, -side * curb_w * 0.5)
            strip[:, 2] = curb_h * 0.32
            if side > 0:
                strip = strip[::-1].copy()
            run = self.Path.trim(strip, 0.12, self.Path.length(strip) - 0.12)
            self.trim(run, 0.025, False, (0.0, 0.0, 1.0), "out", 0.003, 0.004, "glow", name + "_glow")
        self.wall_collider(base, 0.16, -e, height + 0.05, name)
        self.note({"rail": {"length_m": round(total, 2), "height": height, "top_r": top_r, "ribs": count_ribs, "balusters": count_bal, "pitch": pitch, "rib_r": list(rib_r)}})
        return ribs

    def arch_wall_path(self, span, height, wall_len, wall_z, waves, fillet, end_fillet, step=0.02):
        e = self.embed
        r = span * 0.5
        zw, amp = float(wall_z[0]), float(wall_z[1]) - float(wall_z[0])
        zs = max(height - r, zw + fillet + 0.25)
        legs = self.Path.line((-r, 0.0, -e), (-r, 0.0, zs), step)
        a = np.radians(np.linspace(180.0, 0.0, int(math.ceil(180.0 / 0.5)) + 1))
        top = np.stack([r * np.cos(a), np.zeros(len(a)), zs + r * np.sin(a)], axis=1)
        down = self.Path.line((r, 0.0, zs), (r, 0.0, zw + fillet), step)
        a = np.radians(np.linspace(180.0, 270.0, int(math.ceil(90.0 / 0.5)) + 1))
        into = np.stack([r + fillet + fillet * np.cos(a), np.zeros(len(a)), zw + fillet + fillet * np.sin(a)], axis=1)
        x0 = r + fillet
        u = np.linspace(0.0, 1.0, int(math.ceil(wall_len / step)) + 1)
        wave = np.stack([x0 + wall_len * u, np.zeros(len(u)), zw + amp * (1.0 - np.cos(waves * math.pi * u)) * 0.5], axis=1)
        x1 = x0 + wall_len
        z_end = zw + amp * (1.0 - math.cos(waves * math.pi)) * 0.5
        a = np.radians(np.linspace(90.0, 0.0, int(math.ceil(90.0 / 0.5)) + 1))
        out = np.stack([x1 + end_fillet * np.cos(a), np.zeros(len(a)), z_end - end_fillet + end_fillet * np.sin(a)], axis=1)
        foot = self.Path.line((x1 + end_fillet, 0.0, z_end - end_fillet), (x1 + end_fillet, 0.0, -e), step)
        pieces = [legs, top, down, into, wave, out, foot]
        lengths = [self.Path.length(p) for p in pieces]
        path = self.Path.concat(*pieces)
        total = self.Path.length(path)
        marks = np.cumsum([0.0] + lengths)
        return path, {"r": r, "zs": zs, "x0": x0, "x1": x1, "z_end": z_end, "total": total, "marks": marks.tolist(), "wall": self.Path.concat(into, wave, out), "arch": self.Path.concat(legs, top, down), "end_x": x1 + end_fillet}

    def arch_wave_wall(self, span=3.6, height=4.2, arch=(0.52, 0.62, 0.16), cap=(0.26, 0.44, 0.10), wall_t=0.22, wall_len=7.2, wall_z=(2.1, 3.0), waves=3, fillet=0.9, end_fillet=0.7, intrados_w=0.06, intrados_from=1.0, cap_glow_w=0.035, tube_role="shell", wall_role="slat", glow_role="glow", lamp_role="lamp", light=True, name="archwall"):
        e = self.embed
        path, m = self.arch_wall_path(span, height, wall_len, wall_z, waves, fillet, end_fillet)
        total = m["total"]
        marks = m["marks"]
        blend = Blend((marks[3] - 0.3) / total, (marks[4] + 1.0) / total)
        prof_a = self.Profile.rounded_rect(arch[0], arch[1], arch[2], role=tube_role)
        prof_b = self.Profile.rounded_rect(cap[0], cap[1], cap[2], role=tube_role)
        self.sweep(path, prof_a, False, "flat", "horizontal", tube_role, name + "_tube", profile_b=prof_b, mix=blend)
        stations = self.game_path(m["wall"], False)
        stations = stations[stations[:, 0] <= m["end_x"] + 1e-6]
        wall = self.b.new_part(name + "_wall", "auto", False, [wall_role])
        mesh = wall["game"]
        t = wall_t * 0.5
        rows = []
        for x, _, z in stations:
            rows.append([(x, -t, z), (x, t, z), (x, t, -e), (x, -t, -e)])
        grid = np.array(rows, dtype=np.float64)
        base = mesh.add_verts(grid.reshape(-1, 3))
        ids = base + np.arange(len(grid) * 4).reshape(-1, 4)
        front, back, uv_front, uv_back = [], [], [], []
        for i in range(len(grid) - 1):
            front.append([ids[i, 3], ids[i + 1, 3], ids[i + 1, 0], ids[i, 0]])
            uv_front.append([[grid[i, 3, 0], grid[i, 3, 2]], [grid[i + 1, 3, 0], grid[i + 1, 3, 2]], [grid[i + 1, 0, 0], grid[i + 1, 0, 2]], [grid[i, 0, 0], grid[i, 0, 2]]])
            back.append([ids[i, 2], ids[i, 1], ids[i + 1, 1], ids[i + 1, 2]])
            uv_back.append([[-grid[i, 2, 0], grid[i, 2, 2]], [-grid[i, 1, 0], grid[i, 1, 2]], [-grid[i + 1, 1, 0], grid[i + 1, 1, 2]], [-grid[i + 1, 2, 0], grid[i + 1, 2, 2]]])
        mesh.add_faces(np.array(front + back, dtype=np.int64), [wall_role] * (len(front) + len(back)), np.array(uv_front + uv_back, dtype=np.float64))
        cm = self.Mesh(name + "_wall_col")
        coll = self.b.coll.path(m["wall"], False)
        coll = coll[coll[:, 0] <= m["end_x"] + 1e-6]
        hw = cap[1] * 0.5
        crow = np.array([[(x, -hw, z), (x, hw, z), (x, hw, -e), (x, -hw, -e)] for x, _, z in coll], dtype=np.float64)
        cidx, _, _ = cm.add_rings(crow, False, True, ["stone"] * 4, [True] * 4)
        cm.add_cap(cidx[0], np.zeros((4, 2)), "stone")
        cm.add_cap(cidx[-1][::-1], np.zeros((4, 2)), "stone")
        self.b.add_collider(cm)
        self.prism_collider(self.Path.rounded_rect((-m["r"], 0.0, 0.0), arch[0], arch[1], arch[2], 0.0, 2.0), -e, m["zs"], 0.05, name + "_leg")
        wave = m["wall"]
        sel = (wave[:, 0] >= m["x0"] + 0.25) & (wave[:, 0] <= m["x1"] - 0.25)
        glow = wave[sel].copy()
        glow[:, 1] = -t
        glow[:, 2] -= cap[0] * 0.5 / 0.9 + 0.012 + cap_glow_w * 0.5
        self.trim(glow, cap_glow_w, False, (0.0, 0.0, 1.0), "out", 0.003, 0.004, glow_role, name + "_capglow")
        arch_line = m["arch"]
        ss = self.shape.horizontal_frames(arch_line, False)[1]
        inner = arch_line + ss * (-arch[0] * 0.5)
        along = self.Path.cumulative(arch_line)[:len(arch_line)]
        keep = (inner[:, 2] >= intrados_from) & (along <= marks[3] - 0.45)
        self.trim(inner[keep], intrados_w, False, "horizontal", "in", 0.003, 0.004, lamp_role, name + "_intrados")
        lit = None
        if light:
            pos = (0.0, 0.0, m["zs"] + m["r"] * 0.35)
            lit = self.add_light(MapKitLight.point(pos, 2.2, 5.0), MapKitLight.lamp(pos, 4.0, 0.3, 2.0, 0.22))
        self.note({"archwall": {"span": span, "height": height, "arch_section": list(arch), "cap_section": list(cap), "wall_len": wall_len, "wall_z": list(wall_z), "waves": waves, "path_m": round(total, 2), "light": lit}})
        return wall

    def leaf_canopy(self, length=8.0, width=2.6, height=3.1, droop=0.35, bow=0.5, twist=14.0, sag=0.10, edge_r=0.05, rib_every=0.8, rib_d=0.06, rib_w=0.04, spine_r=0.045, posts=(0.32, 0.68), post_r=0.07, lean=0.35, panel_t=0.024, edge_role="shell", panel_role="panel", rib_role="wood", post_role="post", glow=True, light=True, name="canopy"):
        e = self.embed
        leaf = LeafShape(length, width, height, droop, bow, twist, sag)
        fine_s = np.linspace(0.0, 1.0, int(math.ceil(length / 0.02)) + 1)
        edges = self.b.new_part(name + "_edges")
        for v in (1.0, -1.0):
            line = np.array([leaf.point(s, v) for s in fine_s])
            self.tube(line, edge_r, False, "round", edge_role, name + "_edge", edges)
        panel = self.b.new_part(name + "_panel")
        for level, q, mesh in self.b.levels(panel):
            if level == "game":
                count_s = max(12, int(math.ceil(length / 0.25)))
                count_v = 9
            else:
                count_s = max(80, int(math.ceil(length / 0.04)))
                count_v = 41
            ss = np.linspace(0.006, 0.994, count_s + 1)
            vv = np.linspace(-1.0, 1.0, count_v)
            for lift, flip in ((panel_t * 0.5, False), (-panel_t * 0.5, True)):
                grid = np.array([[leaf.point(s, v, lift) for v in vv] for s in ss])
                mesh.add_rings(grid, False, False, [panel_role] * (count_v - 1), [False] * count_v, flip)
        ribs = self.b.new_part(name + "_ribs")
        count_ribs = max(2, int(round(length / rib_every)) - 1)
        prof = self.Profile.rounded_rect(rib_d, rib_w, min(rib_d, rib_w) * 0.35, role=rib_role, segments=2)
        for k in range(count_ribs):
            s = (k + 1) / (count_ribs + 1)
            t, n, up = leaf.axes(s)
            line = np.array([leaf.point(s, v, -(panel_t * 0.5 + rib_d * 0.5)) for v in np.linspace(-0.97, 0.97, 49)])
            self.sweep(line, prof, False, "flat", (float(t[0]), float(t[1]), float(t[2])), rib_role, name + "_rib", ribs)
        spine_drop = panel_t * 0.5 + rib_d + spine_r * 0.5
        spine = np.array([leaf.point(s, 0.0, -spine_drop) for s in np.linspace(0.07, 0.93, 200)])
        self.tube(spine, spine_r, False, "round", rib_role, name + "_spine")
        stand = self.b.new_part(name + "_posts")
        feet = []
        for k, sp in enumerate(posts):
            top = leaf.point(sp, 0.0, -spine_drop)
            sign = -1.0 if sp < 0.5 else 1.0
            foot = np.array([top[0] + sign * lean, top[1], -e])
            line = self.Path.line(foot, top, 0.05)
            self.tube(line, post_r, False, "flat", post_role, name + "_post", stand, collide=True)
            feet.append(foot)
        for k, foot in enumerate(feet):
            disc = self.shape.circle(post_r + 0.08, 0.0, 48, (float(foot[0]), float(foot[1])))
            self.slab(disc, 0.05, 0.018, 3, 0.0, 0.035, post_role, post_role, post_role, None, name + "_foot", False)
        if glow:
            under = spine - np.array([leaf.axes(s)[2] for s in np.linspace(0.07, 0.93, 200)]) * spine_r
            run = self.Path.trim(under, 0.3, self.Path.length(under) - 0.3)
            self.trim(run, 0.02, False, (0.0, 0.0, -1.0), "up", 0.003, 0.004, "glow", name + "_glow")
        lit = None
        if light:
            pos = leaf.point(0.5, 0.0, -0.75)
            lit = self.add_light(MapKitLight.point(pos, 2.0, 4.5), MapKitLight.lamp(pos, 4.0, 0.3, 1.5, 0.2))
        self.note({"canopy": {"length": length, "width": width, "height": height, "twist_deg": twist, "edge_r": edge_r, "ribs": count_ribs, "posts": len(posts), "light": lit}})
        return panel

    def ornament_lantern(self, loc=(0.0, 0.0, 0.0), height=1.6, work_dir=None, voxel=0.007, budget=2200, high_tris=150000, name="lantern"):
        sf = MapKitEngine.load("sculpt_forge", self.engine_dir)
        work = work_dir or os.path.join(tempfile.gettempdir(), "mapkit_ornament")
        os.makedirs(work, exist_ok=True)
        oid = (self.prefix + "_" + name + "_src").lower()
        k = height / 1.6
        palette = {"body": {"color": self.colors["shell"], "finish": "satin"}, "trim": {"color": self.colors["gold"], "finish": "gloss"}, "glow": {"color": self.colors["glow"], "finish": "emissive"}, "base": {"color": self.colors["stone"], "finish": "matte"}, "stem": {"color": self.colors["wood"], "finish": "satin"}}
        mapping = {"body": "shell", "trim": "gold", "glow": "glow", "base": "stone", "stem": "wood"}
        started = time.perf_counter()
        sb = sf.SculptBuilder(oid, budget=budget, target="library", voxel=voxel, palette=palette, reset_scene=False, keep_high=True, high_tris=high_tris, colliders=0, set_name=oid)
        sb.round_cyl(0.40 * k, 0.16 * k, edge=0.07 * k, loc=(0.0, 0.0, 0.08 * k), role="base")
        sb.round_cone((0.0, 0.0, 0.12 * k), (0.0, 0.0, 0.72 * k), 0.17 * k, 0.075 * k, role="stem", fillet=0.05 * k)
        sb.torus(0.105 * k, 0.032 * k, loc=(0.0, 0.0, 0.70 * k), role="trim", fillet=0.02 * k)
        bud = [(0.0, 0.66), (0.16, 0.72), (0.29, 0.86), (0.33, 1.02), (0.27, 1.20), (0.14, 1.36), (0.05, 1.46), (0.0, 1.50)]
        sb.lathe([(r * k, z * k) for r, z in bud], role="body", smooth=2, fillet=0.045 * k)
        sb.torus(0.322 * k, 0.022 * k, loc=(0.0, 0.0, 1.02 * k), role="glow", fillet=0.01 * k)
        sb.capsule((0.0, 0.0, 1.45 * k), (0.0, 0.0, 1.53 * k), 0.022 * k, role="trim", fillet=0.015 * k)
        sb.sphere(0.055 * k, loc=(0.0, 0.0, 1.57 * k), role="trim", fillet=0.02 * k)
        res = sb.build(work)
        low = bpy.data.objects.get(oid)
        if low is None:
            with bpy.data.libraries.load(res["blend"], link=False) as (src, dst):
                dst.objects = [n for n in src.objects if n == oid]
            low = bpy.data.objects.get(oid)
        with bpy.data.libraries.load(res["high_blend"], link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n == oid + "_high"]
        high = bpy.data.objects.get(oid + "_high")
        self.b.triangulate(low)
        self.b.triangulate(high)
        names = list(sb.palette.roles)
        grid = sb.palette.grid()
        co, lv, ls, lt, _ = self.b.mesh_arrays(low.data)
        uv = np.empty(len(low.data.loops) * 2, np.float64)
        low.data.uv_layers[0].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        poly_of = np.repeat(np.arange(len(ls)), lt)
        mean_uv = np.zeros((len(ls), 2))
        np.add.at(mean_uv, poly_of, uv)
        mean_uv /= lt[:, None]
        cell = np.clip(np.floor(mean_uv * grid).astype(int), 0, grid - 1)
        index = cell[:, 1] * grid + cell[:, 0]
        roles = [mapping.get(names[i], "shell") if i < len(names) else "shell" for i in index]
        shift = np.asarray(loc, dtype=np.float64)
        part = self.b.new_part(name, "transfer", False)
        game = part["game"]
        vbase = game.add_verts(co + shift)
        tris = lv.reshape(-1, 3) + vbase
        corners = co[lv.reshape(-1, 3)]
        normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        pick = np.array([[1, 2], [0, 2], [0, 1]])[np.argmax(np.abs(normal), axis=1)]
        rows = np.arange(len(corners))[:, None]
        cols = np.arange(3)[None, :]
        uvs = np.stack([corners[rows, cols, pick[:, 0:1]], corners[rows, cols, pick[:, 1:2]]], -1)
        game.add_faces(tris, roles, uvs)
        hco, hlv, _, hlt, _ = self.b.mesh_arrays(high.data)
        hb = part["dense"].add_verts(hco + shift)
        part["dense"].add_faces(hlv.reshape(-1, 3) + hb, ["shell"] * int(len(hlv) // 3))
        lantern_tris = int(len(lv) // 3)
        high_count = int(len(hlv) // 3)
        for ob in (low, high):
            data = ob.data
            mats = list(data.materials)
            bpy.data.objects.remove(ob, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
            for mat in mats:
                if mat is not None and mat.users == 0:
                    bpy.data.materials.remove(mat)
        for img in list(bpy.data.images):
            if img.users == 0 and img.name.startswith(oid):
                bpy.data.images.remove(img)
        self.prism_collider(self.shape.circle(0.40 * k, 0.0, 32, (float(shift[0]), float(shift[1]))), float(shift[2]), float(shift[2]) + 1.5 * k, 0.05, name)
        self.note({"ornament": {"kind": "lantern", "height": height, "tris": lantern_tris, "high_tris": high_count, "voxel": voxel, "seconds": round(time.perf_counter() - started, 1)}})
        return part

    def world_lamps(self):
        out = []
        for sid in self.b.order:
            for pos, yaw in self.placements.get(sid, [((0.0, 0.0, 0.0), 0.0)]):
                for lamp in self.lamps.get(sid, []):
                    w = self.shape.to_world([lamp["pos"]], pos, yaw)[0]
                    out.append({"sid": sid, "pos": w, "radius": lamp["radius"], "g": lamp["g"]})
        return out

    def local_lamps(self, sid, world):
        own = [{"pos": list(l["pos"]), "radius": l["self_radius"], "g": l["self_g"]} for l in self.lamps.get(sid, [])]
        places = self.placements.get(sid, [((0.0, 0.0, 0.0), 0.0)])
        if len(places) > 1:
            return own
        root = self.b.roots[sid]
        co = np.empty(len(root.data.vertices) * 3, np.float64)
        root.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(axis=0), co.max(axis=0)
        pos, yaw = places[0]
        for lamp in world:
            if lamp["sid"] == sid:
                continue
            p = self.shape.to_local([lamp["pos"]], pos, yaw)[0]
            gap = float(np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0)))
            if gap < lamp["radius"]:
                own.append({"pos": p.tolist(), "radius": lamp["radius"], "g": lamp["g"]})
        return own

    def place_objects(self, include_dense=False):
        record = {"moved": [], "created": [], "low": [], "high": []}
        for sid in self.b.order:
            root = self.b.roots.get(sid)
            if root is None:
                continue
            places = self.placements.get(sid, [((0.0, 0.0, 0.0), 0.0)])
            groups = [("low", [root])]
            if include_dense:
                groups.append(("high", list(self.b.dense_objects.get(sid, []))))
            for kind, obs in groups:
                for ob in obs:
                    record["moved"].append((ob, ob.matrix_world.copy()))
                    ob.matrix_world = MapKitShape.matrix(places[0][0], places[0][1])
                    record[kind].append(ob)
                    for k, (pos, yaw) in enumerate(places[1:]):
                        dup = bpy.data.objects.new("{}_inst{}".format(ob.name, k + 1), ob.data)
                        for coll in ob.users_collection:
                            coll.objects.link(dup)
                        dup.matrix_world = MapKitShape.matrix(pos, yaw)
                        dup.hide_render = ob.hide_render
                        record["created"].append(dup)
                        record[kind].append(dup)
        bpy.context.view_layer.update()
        return record

    def unplace(self, record):
        for dup in record["created"]:
            bpy.data.objects.remove(dup, do_unlink=True)
        for ob, matrix in record["moved"]:
            ob.matrix_world = matrix
        bpy.context.view_layer.update()

    def save_high(self, sid, props_dir):
        obs = list(self.b.dense_objects.get(sid, []))
        if not obs:
            return None
        cos, lvs, lts, cns = [], [], [], []
        base = 0
        for ob in obs:
            co, lv, _, lt, cn = self.b.mesh_arrays(ob.data)
            cos.append(co)
            lvs.append(lv + base)
            lts.append(lt)
            cns.append(cn)
            base += len(co)
        name = sid + "_high"
        stale = bpy.data.objects.get(name)
        if stale is not None:
            bpy.data.objects.remove(stale, do_unlink=True)
        co = np.vstack(cos)
        lv = np.concatenate(lvs)
        lt = np.concatenate(lts)
        cn = np.vstack(cns)
        cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-12)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(co))
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.loops.add(len(lv))
        me.loops.foreach_set("vertex_index", lv.astype(np.int32))
        me.polygons.add(len(lt))
        me.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(lt)[:-1]]).astype(np.int32))
        me.update(calc_edges=True)
        self.Mesh.smooth(me)
        me.update()
        me.normals_split_custom_set(cn.tolist())
        me.update()
        ob = bpy.data.objects.new(name, me)
        scene = bpy.data.scenes.new(name + "_export")
        scene.collection.objects.link(ob)
        path = os.path.join(props_dir, name + ".blend")
        bpy.data.libraries.write(path, {scene}, path_remap="NONE", fake_user=False, compress=True)
        bpy.data.scenes.remove(scene)
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        return path

    def finish(self, props_dir, ao=True, ao_distance=1.6, ao_samples=48, save=True, high=True):
        started = time.perf_counter()
        report = self.b.finish(props_dir, None, False, ao_distance, ao_samples, False)
        world = self.world_lamps()
        aos = {}
        if ao:
            record = self.place_objects(False)
            roots = [self.b.roots[sid] for sid in self.b.order]
            hidden = [o for objs in self.b.dense_objects.values() for o in objs]
            aos = self.b.bake_ao(roots, hidden, ao_distance, ao_samples)
            self.unplace(record)
        for sid in self.b.order:
            root = self.b.roots[sid]
            rep = report["shells"][sid]
            lamps = self.local_lamps(sid, world)
            values = aos.get(root.name)
            if values is None:
                values = np.ones(len(root.data.loops))
            rep["vcol"] = self.b.write_vcol(root, values, lamps)
            rep["vcol_lamps"] = len(lamps)
            rep["placements"] = [[list(p), y] for p, y in self.placements.get(sid, [])]
            rep["kit"] = self.notes.get(sid, {})
            meta = json.loads(root["map_forge"])
            meta.update({"style": "sculpt_mapkit_v1", "normals": "transfer", "palette": self.palette, "placements": rep["placements"], "kit": rep["kit"]})
            root["map_forge"] = json.dumps(meta, default=str)
            if save:
                rep["blend"] = self.b.save_shell(sid, props_dir)
            if high:
                rep["high_blend"] = self.save_high(sid, props_dir)
        report["mapkit_seconds"] = round(time.perf_counter() - started, 2)
        report["world_lights"] = len(world)
        return report

    def map_spec(self, map_name, center=(0.0, 0.0, 520.0), warp=None, vanilla=None, budgets=None):
        spec = self.b.map_spec(map_name, center, warp, [0.0], None, budgets)
        entities = []
        for sid in self.b.order:
            for pos, yaw in self.placements.get(sid, [((0.0, 0.0, 0.0), 0.0)]):
                entities.append({"model": sid, "pos": [round(float(v), 4) for v in pos], "yaw_deg": round(float(yaw), 4), "static_col": True, "vanilla": False})
        for item in vanilla or []:
            entities.append(dict(item, vanilla=True))
        spec["entities"] = entities
        spec["archetype_type"] = "plaza_kit"
        spec["vanilla_ytyps"] = ["v_bush"] if vanilla else []
        return spec

    @staticmethod
    def run_tool(blender, script, args, factory=False, tags=("PASS", "FAIL", "WARN"), timeout=2400):
        cmd = [blender, "-b"] + (["--factory-startup"] if factory else []) + ["-t", str(max(1, int(bpy.context.scene.render.threads)))] + ["-P", script, "--"] + [str(a) for a in args]
        started = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        lines = [line for line in proc.stdout.splitlines() if line.startswith(tuple(tags))]
        return {"code": proc.returncode, "seconds": round(time.perf_counter() - started, 1), "lines": lines, "tail": (proc.stderr or proc.stdout)[-1500:] if proc.returncode else ""}

    def map_forge_dir(self, explicit=None):
        return explicit or os.path.normpath(os.path.join(self.engine_dir, "..", "..", "..", "map-forge", "scripts", "blender"))

    def export(self, out_dir, spec_path, props_dir, tex_dir, blender=None, map_forge=None):
        exe = blender or bpy.app.binary_path
        mf = self.map_forge_dir(map_forge)
        pkg = os.path.join(out_dir, "pkg")
        tags = ("YDR_EXPORT", "YBN_EXPORT", "YTYP_EXPORT", "YMAP_EXPORT", "SHARED_YTD", "PACKAGE_READY", "MAP_EXPORT", "DDS_PREENCODED", "FAIL", "WARN", "MAP_INSPECT", "SUMMARY")
        exported = self.run_tool(exe, os.path.join(mf, "export_map.py"), ["--spec", spec_path, "--props", props_dir, "--textures", tex_dir, "--out", pkg], False, tags)
        inspected = self.run_tool(exe, os.path.join(mf, "inspect_map.py"), ["--dir", os.path.join(pkg, "stream"), "--spec", spec_path, "--json", os.path.join(out_dir, "inspect_report.json")], False, tags)
        return {"export": exported, "inspect": inspected, "pkg": pkg}

    def validate(self, props_dir, json_path, blender=None):
        exe = blender or bpy.app.binary_path
        return self.run_tool(exe, os.path.join(self.engine_dir, "validate_sculpt.py"), ["--blend", props_dir, "--target", "map", "--json", json_path], True, ("SCULPT_QA", "RESULT", "FAIL", "WARN", "  "))

    def qa_renders(self, props_dir, out_dir, qa_json, blender=None, views=4, res=700):
        exe = blender or bpy.app.binary_path
        return self.run_tool(exe, os.path.join(self.engine_dir, "render_sculpt.py"), ["--blend", props_dir, "--out", out_dir, "--qa", qa_json, "--views", views, "--res", res], True, ("SCULPT_RENDER", "RENDER"))


class MapKitPreview:
    def __init__(self, kit, out_dir, quick=False, samples=32):
        self.kit = kit
        self.out_dir = out_dir
        self.quick = quick
        self.pv = kit.sweep_module.SweepPreview(out_dir, (900, 560), 16 if quick else samples)
        self.created = []

    def emissive_materials(self):
        out = []
        for role, spec in self.kit.b.roles.items():
            if spec.get("emissive"):
                mat = bpy.data.materials.get(self.kit.prefix + "_" + role)
                if mat is not None:
                    out.append(mat)
        return out

    def night(self, name, show, location, target, lens, lights, boost=6.0):
        sc = bpy.context.scene
        bg = next((n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND"), None)
        saved_bg = (tuple(bg.inputs["Color"].default_value), bg.inputs["Strength"].default_value) if bg is not None else None
        if bg is not None:
            bg.inputs["Color"].default_value = (0.010, 0.016, 0.034, 1.0)
            bg.inputs["Strength"].default_value = 1.0
        saved_lights = []
        for key, energy, color in (("preview_key", 0.06, (0.62, 0.72, 1.0)), ("preview_fill", 0.0, (1.0, 1.0, 1.0))):
            ld = bpy.data.lights.get(key)
            if ld is not None:
                saved_lights.append((ld, ld.energy, tuple(ld.color)))
                ld.energy = energy
                ld.color = color
        saved_mats = []
        for mat in self.emissive_materials():
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None and "Emission Strength" in bsdf.inputs:
                saved_mats.append((bsdf, bsdf.inputs["Emission Strength"].default_value))
                bsdf.inputs["Emission Strength"].default_value *= boost
        made = []
        for k, item in enumerate(lights):
            ld = bpy.data.lights.new("mapkit_night_{}".format(k), "POINT")
            rgb = np.array(item["color"], dtype=np.float64) / 255.0
            lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
            ld.color = tuple(float(c) for c in lin)
            ld.energy = 42.0 * float(item["intensity"])
            ld.shadow_soft_size = 0.06
            if hasattr(ld, "use_custom_distance"):
                ld.use_custom_distance = True
                ld.cutoff_distance = float(item["falloff"]) * 1.6
            ob = bpy.data.objects.new(ld.name, ld)
            sc.collection.objects.link(ob)
            ob.location = Vector(item["world"])
            made.append((ob, ld))
        try:
            path = self.pv.render(name, show, location, target, lens, "tex", 40.0, 30.0)
        finally:
            for ob, ld in made:
                bpy.data.objects.remove(ob, do_unlink=True)
                bpy.data.lights.remove(ld)
            for bsdf, value in saved_mats:
                bsdf.inputs["Emission Strength"].default_value = value
            for ld, energy, color in saved_lights:
                ld.energy = energy
                ld.color = color
            if bg is not None and saved_bg is not None:
                bg.inputs["Color"].default_value = saved_bg[0]
                bg.inputs["Strength"].default_value = saved_bg[1]
        return path

    def world_lights(self):
        out = []
        for sid in self.kit.b.order:
            for pos, yaw in self.kit.placements.get(sid, [((0.0, 0.0, 0.0), 0.0)]):
                for light in self.kit.b.shells[sid]["lights"]:
                    w = MapKitShape.to_world([light["position"]], pos, yaw)[0]
                    out.append(dict(light, world=[float(v) for v in w]))
        return out

    def run(self, overview, closeups, night_views):
        self.pv.setup()
        record = self.kit.place_objects(True)
        low, high = record["low"], record["high"]
        outputs = []
        stats = {}
        try:
            loc, tgt, lens = overview
            outputs.append(self.pv.render("overview_clay", low, loc, tgt, lens, "clay", 34.0, 30.0))
            outputs.append(self.pv.render("overview_tex", low, loc, tgt, lens, "tex", 34.0, 30.0))
            if not self.quick:
                outputs.append(self.pv.render("overview_vcol", low, loc, tgt, lens, "vcol", 34.0, 30.0))
            lights = self.world_lights()
            for name, (nloc, ntgt, nlens) in night_views.items():
                outputs.append(self.night(name, low, nloc, ntgt, nlens, lights))
            for name, (cloc, ctgt, clens) in closeups.items():
                outputs.append(self.pv.render(name + "_lo", low, cloc, ctgt, clens, "clay", 30.0, 40.0))
                if not self.quick:
                    outputs.append(self.pv.render(name + "_tex", low, cloc, ctgt, clens, "tex", 30.0, 40.0))
                    outputs.append(self.pv.render(name + "_hi", high, cloc, ctgt, clens, "clay", 30.0, 40.0))
                    a = self.pv.render(name + "_nlo", low, cloc, ctgt, clens, "normal", 30.0, 40.0)
                    b = self.pv.render(name + "_nhi", high, cloc, ctgt, clens, "normal", 30.0, 40.0)
                    stats[name] = self.pv.compare_normals(a, b, os.path.join(self.out_dir, name + "_nerr.png"))
        finally:
            self.kit.unplace(record)
        return outputs, stats


class MapKitDemo:
    def __init__(self, kit):
        self.kit = kit
        self.size = (30.0, 22.0, 5.0)
        self.dais = (6.4, 2.6, 0.0)
        self.planter = (-5.8, -5.6, 0.0)
        self.bench = (-5.8, -4.38, 0.0)
        self.arch = (-8.0, 10.35, 0.0)
        self.canopy = (-12.2, -1.8, 0.0)
        self.posts = [(-13.4, 4.6, 0.0), (-10.6, -9.6, 0.0), (2.2, -10.2, 0.0), (13.4, -4.6, 0.0)]

    def outline(self):
        w, d, r = self.size
        return self.kit.Path.rounded_rect((0.0, 0.0, 0.0), w, d, r, 0.0, 0.5)

    def puffy_place(self):
        a = math.radians(232.0)
        rad = 4.15
        pos = (self.dais[0] + rad * math.cos(a), self.dais[1] + rad * math.sin(a), 0.0)
        return pos, math.degrees(a) + 180.0 - 90.0

    def build(self, work_dir):
        k = self.kit
        outline = self.outline()
        k.begin("plaza", "CONCRETE", 16000, 400.0)
        k.plaza_slab(outline, 1.0, 0.3, 6, "paving", "stone", "stone", 1.25, 0.55, 0.05, "gold", "plaza")
        band = k.s_curve([(-8.0, 9.3), (-8.7, 6.6), (-6.9, 3.9), (-3.4, 2.7), (0.2, 3.3), (2.4, 2.6), (3.9, 2.4)], 0.0)
        k.inlaid_band(band, 1.5, False, 0.05, 0.0, "band", "gold", 0.003, 0.004, "band")
        k.begin("dais", "STONE", 16000, 250.0, [(self.dais, 0.0)])
        k.dais_steps(1.9, 4, 0.15, 0.40, 0.04)
        k.ornament_lantern((0.0, 0.0, 0.6), 1.6, os.path.join(work_dir, "ornament"))
        k.begin("planter", "STONE", 8000, 150.0, [(self.planter, 0.0)])
        k.kidney_planter(4.6, 2.3, 0.38)
        k.begin("bench", "WOOD_SOLID_MEDIUM", 4000, 120.0, [(self.bench, 0.0)])
        k.curved_bench(3.0, 2.6)
        pos, yaw = self.puffy_place()
        k.begin("puffy", "CONCRETE", 3000, 120.0, [(pos, yaw)])
        k.puffy_bench(4.15, 2.8)
        k.begin("post", "METAL_SOLID_MEDIUM", 2400, 150.0, [(p, 0.0) for p in self.posts])
        k.light_post(1.9)
        inner = k.Path.offset(k.Path.ccw(outline), -0.45, True, 0.0)
        rail = k.Path.sector(inner, (0.0, 0.0, 0.0), 8.0, 68.0)
        k.begin("rail", "METAL_SOLID_MEDIUM", 12000, 200.0)
        k.ribcage_rail(rail)
        k.begin("archwall", "CONCRETE", 12000, 400.0, [(self.arch, 0.0)])
        k.arch_wave_wall()
        k.begin("canopy", "METAL_SOLID_MEDIUM", 12000, 300.0, [(self.canopy, 90.0)])
        k.leaf_canopy()
        return self.vanilla()

    def vanilla(self):
        soil = 0.55 - 0.09 - 0.12
        items = []
        for model, local, yaw in (("prop_bush_med_02", (-1.25, -0.15), 20.0), ("prop_bush_med_02", (1.3, -0.2), 140.0), ("prop_plant_fern_02a", (0.0, -0.45), 75.0)):
            w = MapKitShape.to_world([(local[0], local[1], soil)], self.planter, 0.0)[0]
            items.append({"model": model, "pos": [round(float(v), 3) for v in w], "yaw_deg": yaw, "kind": "bush"})
        return items

    def views(self):
        d, p, a, c = self.dais, self.planter, self.arch, self.canopy
        overview = ((21.0, -27.0, 15.5), (0.0, 1.0, 0.0), 28.0)
        night = {
            "night_overview": ((21.0, -27.0, 15.5), (0.0, 1.0, 0.0), 28.0),
            "night_eye": ((-1.0, -12.5, 1.7), (2.0, 4.0, 1.0), 26.0),
        }
        pp, _ = self.puffy_place()
        closeups = {
            "rail": ((10.4, 4.6, 1.7), (13.4, 8.8, 1.2), 30.0),
            "steps": ((d[0] - 1.6, d[1] - 5.6, 1.4), (d[0], d[1] - 2.2, 0.2), 30.0),
            "planter": ((p[0] + 3.4, p[1] - 3.1, 1.3), (p[0] + 1.2, p[1] - 0.7, 0.35), 30.0),
            "archwall": ((a[0] + 3.0, a[1] - 8.4, 2.1), (a[0] + 2.4, a[1], 2.4), 26.0),
            "bench": ((self.bench[0] + 1.6, self.bench[1] + 3.0, 1.3), (self.bench[0], self.bench[1], 0.35), 32.0),
            "puffy": ((pp[0] - 1.6, pp[1] - 2.6, 1.3), (pp[0], pp[1], 0.3), 32.0),
            "canopy": ((c[0] + 5.2, c[1] - 4.6, 1.6), (c[0], c[1], 2.6), 26.0),
            "lantern": ((d[0] - 2.0, d[1] - 3.0, 1.7), (d[0], d[1], 1.3), 34.0),
            "post": ((self.posts[2][0] - 1.6, self.posts[2][1] + 2.2, 1.4), (self.posts[2][0], self.posts[2][1], 1.0), 34.0),
        }
        return overview, closeups, night


class MapKitCli:
    @staticmethod
    def parse(argv):
        parser = argparse.ArgumentParser(prog="mapkit.py")
        parser.add_argument("--demo", action="store_true")
        parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "sculpt_mapkit_demo"))
        parser.add_argument("--prefix", default="1nfx_mk")
        parser.add_argument("--palette", default="house", choices=["house", "pastel"])
        parser.add_argument("--engine-dir", dest="engine_dir", default="")
        parser.add_argument("--map-forge", dest="map_forge", default="")
        parser.add_argument("--blender", default="")
        parser.add_argument("--samples", type=int, default=48)
        parser.add_argument("--export", action="store_true")
        parser.add_argument("--validate", action="store_true")
        parser.add_argument("--qa-renders", dest="qa_renders", action="store_true")
        parser.add_argument("--no-render", dest="no_render", action="store_true")
        parser.add_argument("--quick", action="store_true")
        return parser.parse_args(argv)

    @staticmethod
    def script_args():
        return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def main():
    args = MapKitCli.parse(MapKitCli.script_args())
    if not args.demo:
        print("MAPKIT_USAGE blender -b --factory-startup -P mapkit.py -- --demo --out <dir> [--palette house|pastel] [--export] [--validate] [--qa-renders] [--no-render] [--quick] [--engine-dir <dir>] [--map-forge <dir>] [--blender <exe>] [--prefix 1nfx_mk]", flush=True)
        return
    out = os.path.abspath(args.out)
    props, tex, renders, work = (os.path.join(out, n) for n in ("props", "textures", "renders", "work"))
    for folder in (props, tex, renders, work):
        os.makedirs(folder, exist_ok=True)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    started = time.perf_counter()
    kit = MapKitRecipes(args.prefix, tex, args.palette, args.engine_dir or None)
    demo = MapKitDemo(kit)
    vanilla = demo.build(work)
    build_seconds = round(time.perf_counter() - started, 2)
    report = kit.finish(props, True, 1.6, args.samples, True, True)
    report["build_seconds"] = build_seconds
    spec = kit.map_spec(args.prefix + "_demo", (0.0, 0.0, 520.0), [0.0, -6.0, 520.5, 0.0], vanilla, {"max_total_tris": 48000, "max_ytd_vram_mb": 4.0, "max_disk_mb": 8.0, "max_outdoor_vcol_g": 45})
    spec_path = os.path.join(out, "map-spec.json")
    with open(spec_path, "w", encoding="utf-8") as handle:
        json.dump(spec, handle, indent=1)
    report["spec"] = spec_path
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "mapkit_demo_all.blend"), compress=True)
    if not args.no_render:
        overview, closeups, night = demo.views()
        report["renders"], report["screen_normal_lo_vs_dense"] = MapKitPreview(kit, renders, args.quick, 32).run(overview, closeups, night)
    blender = args.blender or bpy.app.binary_path
    if args.export:
        report["export"] = kit.export(out, spec_path, props, tex, blender, args.map_forge or None)
    if args.validate or args.qa_renders:
        qa_json = os.path.join(out, "sculpt_qa.json")
        report["validate"] = kit.validate(props, qa_json, blender)
        if args.qa_renders:
            report["qa_renders"] = kit.qa_renders(props, os.path.join(out, "qa_renders"), qa_json, blender)
    with open(os.path.join(out, "mapkit_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, default=str)
    summary = {sid: [v["tris"], v["budget"], v["dihedral"]["smooth_p90"], v.get("normal_err_vertex_max_deg"), v["vcol"]["G_mean_outdoor"]] for sid, v in report["shells"].items()}
    print("MAPKIT_REPORT " + json.dumps({"total_tris": sum(v[0] for v in summary.values()), "shells": summary, "seconds": round(time.perf_counter() - started, 1)}), flush=True)
    for key in ("export", "validate"):
        block = report.get(key)
        if isinstance(block, dict):
            for sub in ([block] if "lines" in block else [block.get("export", {}), block.get("inspect", {})]):
                for line in sub.get("lines", [])[-12:]:
                    print("MAPKIT_" + key.upper() + " " + line, flush=True)


if __name__ == "__main__":
    main()
