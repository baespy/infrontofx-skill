import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector, geometry


class EngineLoader:
    def __init__(self, engine_dir=None):
        self.engine_dir = EngineLoader.locate(engine_dir)

    @staticmethod
    def locate(explicit):
        candidates = []
        if explicit:
            candidates.append(explicit)
        if os.environ.get("SCULPT_FORGE_DIR"):
            candidates.append(os.environ["SCULPT_FORGE_DIR"])
        here = globals().get("__file__")
        if here:
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(here)), ".."))
        for path in candidates:
            path = os.path.abspath(path)
            for folder in (path, os.path.join(path, "scripts", "blender"), os.path.join(path, "sculpt-forge", "scripts", "blender")):
                if os.path.isfile(os.path.join(folder, "sculpt_forge.py")):
                    return os.path.normpath(folder)
        raise RuntimeError("sculpt_forge.py not found; pass --engine-dir <sculpt-forge>/scripts/blender or set SCULPT_FORGE_DIR")

    def module(self):
        if self.engine_dir not in sys.path:
            sys.path.insert(0, self.engine_dir)
        return importlib.import_module("sculpt_forge")

    def script(self, name):
        return os.path.join(self.engine_dir, name)

    def prop_forge(self, *parts):
        return os.path.normpath(os.path.join(self.engine_dir, "..", "..", "..", "prop-forge", *parts))

    def font(self, explicit=None):
        for path in (explicit, os.environ.get("SCULPT_FORGE_FONT"), self.prop_forge("assets", "fonts", "TitanOne-Regular.ttf")):
            if path and os.path.isfile(path):
                return os.path.normpath(path)
        return None


class Frame:
    def __init__(self, origin=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
        self.origin = Vector(tuple(float(v) for v in origin))
        self.rot = tuple(float(a) for a in rot)
        self.matrix = Euler([math.radians(a) for a in self.rot], "XYZ").to_matrix()

    def point(self, local):
        return tuple(self.origin + self.matrix @ Vector(tuple(float(v) for v in local)))

    def points(self, local):
        pts = np.asarray(local, np.float64).reshape(-1, 3)
        return pts @ np.array(self.matrix, np.float64).T + np.array(self.origin, np.float64)

    def euler(self, local_rot=(0.0, 0.0, 0.0)):
        m = self.matrix @ Euler([math.radians(a) for a in local_rot], "XYZ").to_matrix()
        return tuple(math.degrees(a) for a in m.to_euler("XYZ"))

    def moved(self, local):
        return Frame(self.point(local), self.rot)

    def turned(self, yaw):
        m = self.matrix @ Euler((0.0, 0.0, math.radians(yaw)), "XYZ").to_matrix()
        return Frame(self.origin, tuple(math.degrees(a) for a in m.to_euler("XYZ")))


class Outline:
    @staticmethod
    def ccw(points):
        pts = np.asarray(points, np.float64)
        nxt = np.roll(pts, -1, axis=0)
        area = 0.5 * float(np.sum(pts[:, 0] * nxt[:, 1] - nxt[:, 0] * pts[:, 1]))
        return pts[::-1].copy() if area < 0.0 else pts

    @staticmethod
    def dedupe(points, tolerance=1e-6, closed=True):
        pts = np.asarray(points, np.float64)
        if len(pts) < 2:
            return pts
        keep = np.ones(len(pts), bool)
        keep[1:] = np.linalg.norm(np.diff(pts, axis=0), axis=1) > tolerance
        pts = pts[keep]
        if closed and len(pts) > 2 and np.linalg.norm(pts[0] - pts[-1]) <= tolerance:
            pts = pts[:-1]
        return pts

    @staticmethod
    def arc(cx, cy, rx, ry, a0, a1, step=0.004, minimum=4):
        span = math.radians(float(a1) - float(a0))
        n = max(int(minimum), int(math.ceil(abs(span) * max(rx, ry) / max(step, 1e-5))))
        a = math.radians(float(a0)) + span * np.arange(n + 1) / float(n)
        return np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], axis=1)

    @staticmethod
    def circle(radius, centre=(0.0, 0.0), step=0.004):
        n = max(24, int(math.ceil(math.tau * radius / max(step, 1e-5))))
        a = np.linspace(0.0, math.tau, n, endpoint=False)
        return np.stack([centre[0] + radius * np.cos(a), centre[1] + radius * np.sin(a)], axis=1)

    @staticmethod
    def rounded_rect(width, height, radius, centre=(0.0, 0.0), step=0.004):
        r = max(1e-4, min(float(radius), width * 0.5 - 1e-4, height * 0.5 - 1e-4))
        hw = width * 0.5 - r
        hh = height * 0.5 - r
        parts = [Outline.arc(hw, -hh, r, r, -90.0, 0.0, step), Outline.arc(hw, hh, r, r, 0.0, 90.0, step), Outline.arc(-hw, hh, r, r, 90.0, 180.0, step), Outline.arc(-hw, -hh, r, r, 180.0, 270.0, step)]
        pts = Outline.dedupe(np.vstack(parts))
        return pts + np.asarray(centre, np.float64)

    @staticmethod
    def arch_top(width, height, corner, centre=(0.0, 0.0), step=0.004):
        half = width * 0.5
        r = max(1e-4, min(float(corner), half - 1e-4, (height - half) * 0.5))
        spring = height * 0.5 - half
        parts = [Outline.arc(half - r, -height * 0.5 + r, r, r, -90.0, 0.0, step), Outline.arc(0.0, spring, half, half, 0.0, 180.0, step), Outline.arc(-half + r, -height * 0.5 + r, r, r, 180.0, 270.0, step)]
        return Outline.dedupe(np.vstack(parts)) + np.asarray(centre, np.float64)

    @staticmethod
    def squircle(width, height, exponent=5.0, centre=(0.0, 0.0), count=320):
        a = np.linspace(0.0, math.tau, int(count), endpoint=False)
        c = np.cos(a)
        s = np.sin(a)
        e = 2.0 / float(exponent)
        pts = np.stack([np.sign(c) * np.abs(c) ** e * width * 0.5, np.sign(s) * np.abs(s) ** e * height * 0.5], axis=1)
        return pts + np.asarray(centre, np.float64)

    @staticmethod
    def squircle_top(width, height, exponent, x):
        t = min(abs(2.0 * x / width), 1.0)
        return height * 0.5 * (1.0 - t ** exponent) ** (1.0 / exponent)

    @staticmethod
    def fillet(points, radii, step=0.004):
        pts = np.asarray(points, np.float64)
        n = len(pts)
        rad = np.broadcast_to(np.asarray(radii, np.float64), (n,))
        out = []
        for i in range(n):
            p = pts[i]
            prev = pts[i - 1]
            nxt = pts[(i + 1) % n]
            a = prev - p
            b = nxt - p
            la = float(np.linalg.norm(a))
            lb = float(np.linalg.norm(b))
            if la < 1e-9 or lb < 1e-9 or rad[i] <= 0.0:
                out.append(p[None, :])
                continue
            ua = a / la
            ub = b / lb
            phi = math.acos(max(-1.0, min(1.0, float(ua @ ub))))
            if phi > math.pi - 1e-3 or phi < 1e-3:
                out.append(p[None, :])
                continue
            t = min(rad[i] / math.tan(phi * 0.5), 0.5 * la, 0.5 * lb)
            r = t * math.tan(phi * 0.5)
            bis = ua + ub
            bis /= max(float(np.linalg.norm(bis)), 1e-12)
            centre = p + bis * (r / math.sin(phi * 0.5))
            t1 = p + ua * t
            t2 = p + ub * t
            v1 = t1 - centre
            v2 = t2 - centre
            start = math.atan2(v1[1], v1[0])
            sweep = math.atan2(v1[0] * v2[1] - v1[1] * v2[0], float(v1 @ v2))
            m = max(2, int(math.ceil(abs(sweep) * r / max(step, 1e-5))))
            ang = start + sweep * np.arange(m + 1) / float(m)
            out.append(np.stack([centre[0] + r * np.cos(ang), centre[1] + r * np.sin(ang)], axis=1))
        return Outline.dedupe(np.vstack(out))

    @staticmethod
    def arrow(length, height, head, tail_radius, corner, tip, direction=1.0, centre=(0.0, 0.0), step=0.004):
        x0 = -length * 0.5
        x1 = length * 0.5 - head
        x2 = length * 0.5
        h = height * 0.5
        poly = np.array([[x0, -h], [x1, -h], [x2, 0.0], [x1, h], [x0, h]], np.float64)
        pts = Outline.fillet(poly, [tail_radius, corner, tip, corner, tail_radius], step)
        pts[:, 0] *= 1.0 if direction >= 0.0 else -1.0
        return Outline.ccw(pts) + np.asarray(centre, np.float64)

    @staticmethod
    def star(outer, inner, points=5, rotation=90.0, tip=None, valley=None, centre=(0.0, 0.0), step=0.003):
        n = int(points) * 2
        a = np.radians(float(rotation)) + np.arange(n) * math.pi / int(points)
        rad = np.where(np.arange(n) % 2 == 0, float(outer), float(inner))
        poly = np.stack([rad * np.cos(a), rad * np.sin(a)], axis=1)
        radii = np.where(np.arange(n) % 2 == 0, float(tip if tip is not None else 0.22 * outer), float(valley if valley is not None else 0.12 * outer))
        return Outline.ccw(Outline.fillet(poly, radii, step)) + np.asarray(centre, np.float64)

    @staticmethod
    def heart(size, centre=(0.0, 0.0), count=160):
        t = np.linspace(0.0, math.tau, int(count), endpoint=False)
        x = 16.0 * np.sin(t) ** 3
        y = 13.0 * np.cos(t) - 5.0 * np.cos(2.0 * t) - 2.0 * np.cos(3.0 * t) - np.cos(4.0 * t)
        pts = np.stack([x, y], axis=1)
        pts -= (pts.min(axis=0) + pts.max(axis=0)) * 0.5
        pts *= float(size) / float(pts[:, 1].max() - pts[:, 1].min())
        return Outline.ccw(pts) + np.asarray(centre, np.float64)

    @staticmethod
    def resample(points, spacing, closed=True):
        pts = np.asarray(points, np.float64)
        ring = np.vstack([pts, pts[:1]]) if closed else pts
        seg = np.linalg.norm(np.diff(ring, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        total = float(cum[-1])
        count = max(8 if closed else 2, int(math.ceil(total / max(spacing, 1e-5))))
        s = np.linspace(0.0, total, count, endpoint=not closed)
        return np.stack([np.interp(s, cum, ring[:, k]) for k in range(pts.shape[1])], axis=1)

    @staticmethod
    def area(points):
        pts = np.asarray(points, np.float64)
        nxt = np.roll(pts, -1, axis=0)
        return 0.5 * float(np.sum(pts[:, 0] * nxt[:, 1] - nxt[:, 0] * pts[:, 1]))


class FieldRaster:
    def __init__(self, lo, step, count, values):
        self.lo = np.asarray(lo, np.float64)
        self.step = float(step)
        self.count = np.asarray(count, np.int64)
        self.hi = self.lo + (self.count - 1) * self.step
        self.values = np.ascontiguousarray(values, np.float32)

    def sample(self, uv):
        uv = np.asarray(uv, np.float32)
        f = (uv - self.lo.astype(np.float32)) / self.step
        top = (self.count - 1).astype(np.float32) - 1e-3
        fc = np.clip(f, 0.0, top)
        i = np.floor(fc).astype(np.int64)
        t = fc - i
        v = self.values
        tx = t[:, 0]
        ty = t[:, 1]
        a = v[i[:, 0], i[:, 1]] * (1.0 - tx) + v[i[:, 0] + 1, i[:, 1]] * tx
        b = v[i[:, 0], i[:, 1] + 1] * (1.0 - tx) + v[i[:, 0] + 1, i[:, 1] + 1] * tx
        outside = uv - np.clip(uv, self.lo.astype(np.float32), self.hi.astype(np.float32))
        return a * (1.0 - ty) + b * ty + np.sqrt((outside * outside).sum(axis=1))


class Field2D:
    def __init__(self, blend=0.0, offset=0.0, entries=None):
        self.blend = float(blend)
        self.offset = float(offset)
        self.entries = list(entries or [])

    def add(self, loops, op="union", rule="nonzero"):
        if isinstance(loops, np.ndarray) and loops.ndim == 2:
            loops = [loops]
        self.entries.append({"loops": [np.asarray(l, np.float64) for l in loops], "op": str(op), "rule": str(rule)})
        return self

    def grown(self, extra):
        return Field2D(self.blend, self.offset + float(extra), self.entries)

    def bounds(self):
        pts = np.vstack([l for e in self.entries if e["op"] == "union" for l in e["loops"]])
        pad = max(self.offset, 0.0) + 0.25 * self.blend
        return pts.min(axis=0) - pad, pts.max(axis=0) + pad

    def raster(self, step, margin, reach):
        lo, hi = self.bounds()
        lo = lo - margin
        hi = hi + margin
        count = (np.ceil((hi - lo) / step).astype(np.int64) + 1)
        reach = float(reach) + max(self.offset, 0.0) + 0.25 * self.blend
        values = None
        for entry in self.entries:
            d = Field2D.signed_band(entry["loops"], entry["rule"], lo, step, count, reach)
            if values is None:
                values = d if entry["op"] == "union" else -d
            elif entry["op"] == "union":
                values = Field2D.smin(values, d, self.blend)
            else:
                values = Field2D.smax(values, -d, self.blend)
        return FieldRaster(lo, step, count, values - self.offset)

    @staticmethod
    def smin(a, b, k):
        if k <= 0.0:
            return np.minimum(a, b)
        h = np.maximum(k - np.abs(a - b), 0.0) / k
        return np.minimum(a, b) - h * h * (k * 0.25)

    @staticmethod
    def smax(a, b, k):
        if k <= 0.0:
            return np.maximum(a, b)
        h = np.maximum(k - np.abs(a - b), 0.0) / k
        return np.maximum(a, b) + h * h * (k * 0.25)

    @staticmethod
    def edges(loops):
        starts = []
        ends = []
        for loop in loops:
            ring = np.asarray(loop, np.float64)
            if len(ring) < 3:
                continue
            starts.append(ring)
            ends.append(np.roll(ring, -1, axis=0))
        return np.vstack(starts), np.vstack(ends)

    @staticmethod
    def signed_band(loops, rule, lo, step, count, reach):
        a, b = Field2D.edges(loops)
        inside = Field2D.fill(a, b, lo, step, count, rule)
        dist = Field2D.band(a, b, lo, step, count, reach)
        return np.where(inside, -dist, dist).astype(np.float32)

    @staticmethod
    def fill(a, b, lo, step, count, rule):
        cu, cv = int(count[0]), int(count[1])
        us = lo[0] + np.arange(cu) * step
        ay = a[:, 1]
        by = b[:, 1]
        ymin = np.minimum(ay, by)
        ymax = np.maximum(ay, by)
        j0 = np.maximum(np.ceil((ymin - lo[1]) / step - 1e-9).astype(np.int64), 0)
        j1 = np.minimum(np.ceil((ymax - lo[1]) / step - 1e-9).astype(np.int64) - 1, cv - 1)
        valid = np.nonzero((np.abs(by - ay) > 1e-12) & (j1 >= j0))[0]
        inside = np.zeros((cu, cv), bool)
        if len(valid) == 0:
            return inside
        spans = j1[valid] - j0[valid] + 1
        edge = np.repeat(valid, spans)
        first = np.repeat(np.cumsum(spans) - spans, spans)
        rows = np.repeat(j0[valid], spans) + (np.arange(int(spans.sum())) - first)
        v = lo[1] + rows * step
        t = (v - ay[edge]) / (by[edge] - ay[edge])
        x = a[edge, 0] + t * (b[edge, 0] - a[edge, 0])
        direction = np.where(by[edge] > ay[edge], 1, -1)
        order = np.lexsort((x, rows))
        rows = rows[order]
        x = x[order]
        direction = direction[order]
        cuts = np.concatenate([[0], np.nonzero(np.diff(rows))[0] + 1, [len(rows)]])
        for s, e in zip(cuts[:-1], cuts[1:]):
            k = np.searchsorted(x[s:e], us, side="right")
            if rule == "evenodd":
                inside[:, rows[s]] = (k % 2) == 1
            else:
                wind = np.concatenate([[0], np.cumsum(direction[s:e])])
                inside[:, rows[s]] = wind[k] != 0
        return inside

    @staticmethod
    def band(a, b, lo, step, count, reach):
        cu, cv = int(count[0]), int(count[1])
        us = lo[0] + np.arange(cu) * step
        vs = lo[1] + np.arange(cv) * step
        dist = np.full((cu, cv), float(reach), np.float64)
        ilo = np.clip(np.floor((np.minimum(a[:, 0], b[:, 0]) - reach - lo[0]) / step).astype(np.int64), 0, cu - 1)
        ihi = np.clip(np.ceil((np.maximum(a[:, 0], b[:, 0]) + reach - lo[0]) / step).astype(np.int64), 0, cu - 1)
        jlo = np.clip(np.floor((np.minimum(a[:, 1], b[:, 1]) - reach - lo[1]) / step).astype(np.int64), 0, cv - 1)
        jhi = np.clip(np.ceil((np.maximum(a[:, 1], b[:, 1]) + reach - lo[1]) / step).astype(np.int64), 0, cv - 1)
        for k in range(len(a)):
            i0, i1, j0, j1 = int(ilo[k]), int(ihi[k]) + 1, int(jlo[k]), int(jhi[k]) + 1
            px = us[i0:i1][:, None] - a[k, 0]
            py = vs[j0:j1][None, :] - a[k, 1]
            ex = b[k, 0] - a[k, 0]
            ey = b[k, 1] - a[k, 1]
            h = np.clip((px * ex + py * ey) / max(ex * ex + ey * ey, 1e-18), 0.0, 1.0)
            dx = px - ex * h
            dy = py - ey * h
            block = dist[i0:i1, j0:j1]
            np.minimum(block, np.sqrt(dx * dx + dy * dy), out=block)
        return dist

    def contour(self, level, angles=None, centre=(0.0, 0.0), count=360, step=0.004):
        lo, hi = self.bounds()
        raster = self.raster(step, step * 4.0, abs(level) + step * 6.0)
        if angles is None:
            angles = np.linspace(0.0, 360.0, int(count), endpoint=False)
        a = np.radians(np.asarray(angles, np.float64))
        dirs = np.stack([np.cos(a), np.sin(a)], axis=1)
        c = np.asarray(centre, np.float64)
        span = float(np.linalg.norm(np.maximum(np.abs(lo - c), np.abs(hi - c)))) * 1.3
        r_in = np.zeros(len(a))
        r_out = np.full(len(a), span)
        for _ in range(42):
            mid = 0.5 * (r_in + r_out)
            inside = raster.sample(c + dirs * mid[:, None]) < level
            r_in = np.where(inside, mid, r_in)
            r_out = np.where(inside, r_out, mid)
        return c + dirs * (0.5 * (r_in + r_out))[:, None]

    def width_at(self, level, v, centre_u=0.0, step=0.003):
        lo, hi = self.bounds()
        raster = self.raster(step, step * 4.0, abs(level) + step * 6.0)
        us = np.linspace(lo[0], hi[0], int(math.ceil((hi[0] - lo[0]) / (step * 0.5))) + 1)
        values = raster.sample(np.stack([us, np.full(len(us), float(v))], axis=1))
        inside = np.nonzero(values < level)[0]
        if len(inside) == 0:
            return centre_u, centre_u
        return float(us[inside[0]]), float(us[inside[-1]])


class FieldSource:
    def __init__(self, field, inner=0.0, cap=0.10):
        self.field = field
        self.inner = float(inner)
        self.cap = float(cap)
        self.cache = {}

    def build(self, step, margin):
        key = (round(float(step), 7), round(float(margin), 7))
        if key not in self.cache:
            reach = min(float(margin), max(self.inner, self.cap)) + 2.0 * float(step)
            self.cache = {key: self.field.raster(float(step), float(margin), reach)}
        return self.cache[key]

    def bounds(self):
        return self.field.bounds()


class GlyphOutlines:
    def __init__(self, font=None, resolution=8, spacing=0.018):
        self.font = font
        self.resolution = int(resolution)
        self.spacing = float(spacing)

    @staticmethod
    def sample_spline(spline, resolution):
        pts = []
        if spline.type == "BEZIER":
            bp = spline.bezier_points
            n = len(bp)
            segments = n if spline.use_cyclic_u else n - 1
            for i in range(segments):
                p0 = bp[i]
                p1 = bp[(i + 1) % n]
                chunk = geometry.interpolate_bezier(p0.co, p0.handle_right, p1.handle_left, p1.co, int(resolution) + 1)
                pts.extend((v.x, v.y) for v in chunk[:-1])
        else:
            pts = [(p.co.x, p.co.y) for p in spline.points]
        return Outline.dedupe(np.array(pts, np.float64).reshape(-1, 2), 1e-7)

    def contours(self, body, spacing=1.0):
        curve = bpy.data.curves.new("signs_glyphs", "FONT")
        curve.body = str(body)
        if self.font and os.path.isfile(self.font):
            curve.font = bpy.data.fonts.load(self.font, check_existing=True)
        curve.size = 1.0
        curve.space_character = float(spacing)
        curve.align_x = "LEFT"
        ob = bpy.data.objects.new("signs_glyphs", curve)
        bpy.context.scene.collection.objects.link(ob)
        deps = bpy.context.evaluated_depsgraph_get()
        evaluated = ob.evaluated_get(deps)
        loops = []
        try:
            shape = evaluated.to_curve(deps)
            for spline in shape.splines:
                pts = GlyphOutlines.sample_spline(spline, self.resolution)
                if len(pts) >= 3 and abs(Outline.area(pts)) > 1e-8:
                    loops.append(pts)
        finally:
            evaluated.to_curve_clear()
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.curves.remove(curve)
        if not loops:
            raise ValueError("text {!r} produced no outlines".format(body))
        return loops

    def layout(self, body, height=0.25, max_width=None, spacing=1.0, centre=(0.0, 0.0)):
        loops = self.contours(body, spacing)
        allp = np.vstack(loops)
        lo = allp.min(axis=0)
        hi = allp.max(axis=0)
        scale = float(height) / max(float(hi[1] - lo[1]), 1e-6)
        if max_width:
            scale = min(scale, float(max_width) / max(float(hi[0] - lo[0]), 1e-6))
        mid = (lo + hi) * 0.5
        out = []
        for loop in loops:
            pts = (loop - mid) * scale + np.asarray(centre, np.float64)
            out.append(Outline.resample(pts, self.spacing * max(float(height), 0.05)))
        return out, {"width": float(hi[0] - lo[0]) * scale, "height": float(hi[1] - lo[1]) * scale, "scale": scale}


class MonolineFont:
    glyphs = {
        "a": (("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0), ("line", 0.84, 1.0, 0.84, 0.0)),
        "b": (("line", 0.0, 1.5, 0.0, 0.0), ("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0)),
        "c": (("ell", 0.42, 0.5, 0.42, 0.5, 42.0, 318.0),),
        "d": (("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0), ("line", 0.84, 1.5, 0.84, 0.0)),
        "e": (("path", (("line", 0.02, 0.5, 0.84, 0.5), ("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 318.0))),),
        "f": (("path", (("ell", 0.6, 1.22, 0.26, 0.28, 25.0, 180.0), ("line", 0.34, 1.22, 0.34, 0.0))), ("line", 0.06, 0.92, 0.64, 0.92)),
        "g": (("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0), ("path", (("line", 0.84, 1.0, 0.84, -0.18), ("ell", 0.42, -0.18, 0.42, 0.32, 0.0, -165.0)))),
        "h": (("line", 0.0, 1.5, 0.0, 0.0), ("path", (("ell", 0.4, 0.55, 0.4, 0.45, 180.0, 0.0), ("line", 0.8, 0.55, 0.8, 0.0)))),
        "i": (("line", 0.0, 1.0, 0.0, 0.0), ("dot", 0.0, 1.36)),
        "j": (("path", (("line", 0.22, 1.0, 0.22, -0.22), ("ell", -0.04, -0.22, 0.26, 0.28, 0.0, -160.0))), ("dot", 0.22, 1.36)),
        "k": (("line", 0.0, 1.5, 0.0, 0.0), ("line", 0.7, 1.0, 0.04, 0.4), ("line", 0.26, 0.6, 0.76, 0.0)),
        "l": (("path", (("line", 0.0, 1.5, 0.0, 0.2), ("ell", 0.2, 0.2, 0.2, 0.2, 180.0, 270.0))),),
        "m": (("line", 0.0, 1.0, 0.0, 0.0), ("path", (("ell", 0.35, 0.6, 0.35, 0.4, 180.0, 0.0), ("line", 0.7, 0.6, 0.7, 0.0))), ("path", (("ell", 1.05, 0.6, 0.35, 0.4, 180.0, 0.0), ("line", 1.4, 0.6, 1.4, 0.0)))),
        "n": (("line", 0.0, 1.0, 0.0, 0.0), ("path", (("ell", 0.4, 0.55, 0.4, 0.45, 180.0, 0.0), ("line", 0.8, 0.55, 0.8, 0.0)))),
        "o": (("ell", 0.44, 0.5, 0.44, 0.5, 0.0, 360.0),),
        "p": (("line", 0.0, 1.0, 0.0, -0.55), ("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0)),
        "q": (("ell", 0.42, 0.5, 0.42, 0.5, 0.0, 360.0), ("line", 0.84, 1.0, 0.84, -0.55)),
        "r": (("line", 0.0, 1.0, 0.0, 0.0), ("ell", 0.42, 0.55, 0.42, 0.45, 180.0, 55.0)),
        "s": (("poly", ((0.74, 0.86), (0.5, 1.0), (0.2, 0.95), (0.07, 0.76), (0.22, 0.57), (0.52, 0.47), (0.75, 0.3), (0.68, 0.08), (0.4, 0.0), (0.04, 0.1))),),
        "t": (("path", (("line", 0.24, 1.36, 0.24, 0.2), ("ell", 0.44, 0.2, 0.2, 0.2, 180.0, 270.0), ("line", 0.44, 0.0, 0.6, 0.0))), ("line", 0.0, 0.95, 0.56, 0.95)),
        "u": (("path", (("line", 0.0, 1.0, 0.0, 0.45), ("ell", 0.4, 0.45, 0.4, 0.45, 180.0, 360.0))), ("line", 0.8, 1.0, 0.8, 0.0)),
        "v": (("poly", ((0.0, 1.0), (0.4, 0.0), (0.8, 1.0))),),
        "w": (("poly", ((0.0, 1.0), (0.3, 0.0), (0.6, 0.85), (0.9, 0.0), (1.2, 1.0))),),
        "x": (("line", 0.0, 1.0, 0.8, 0.0), ("line", 0.8, 1.0, 0.0, 0.0)),
        "y": (("line", 0.0, 1.0, 0.42, 0.04), ("poly", ((0.82, 1.0), (0.34, -0.28), (0.2, -0.46), (0.0, -0.5))),),
        "z": (("poly", ((0.0, 1.0), (0.8, 1.0), (0.0, 0.0), (0.8, 0.0))),),
        "0": (("ell", 0.45, 0.7, 0.45, 0.7, 0.0, 360.0),),
        "1": (("poly", ((0.08, 1.12), (0.4, 1.4), (0.4, 0.0))),),
        "2": (("path", (("ell", 0.42, 1.0, 0.4, 0.4, 160.0, -25.0), ("poly", ((0.0, 0.0), (0.86, 0.0))))),),
        "3": (("path", (("ell", 0.4, 1.05, 0.36, 0.35, 150.0, -90.0), ("ell", 0.4, 0.36, 0.42, 0.36, 90.0, -150.0))),),
        "4": (("poly", ((0.62, 0.0), (0.62, 1.4), (0.0, 0.42), (0.9, 0.42))),),
        "5": (("path", (("poly", ((0.8, 1.4), (0.12, 1.4), (0.06, 0.82))), ("ell", 0.42, 0.46, 0.44, 0.46, 125.0, -145.0))),),
        "6": (("ell", 0.44, 0.45, 0.44, 0.45, 0.0, 360.0), ("poly", ((0.02, 0.48), (0.2, 1.1), (0.58, 1.4)))),
        "7": (("poly", ((0.0, 1.4), (0.86, 1.4), (0.3, 0.0))),),
        "8": (("ell", 0.42, 1.07, 0.33, 0.33, 0.0, 360.0), ("ell", 0.42, 0.38, 0.42, 0.38, 0.0, 360.0)),
        "9": (("ell", 0.44, 0.95, 0.44, 0.45, 0.0, 360.0), ("poly", ((0.88, 0.9), (0.7, 0.3), (0.32, 0.0)))),
        "-": (("line", 0.0, 0.5, 0.5, 0.5),),
        "!": (("line", 0.0, 1.5, 0.0, 0.5), ("dot", 0.0, 0.0)),
        ".": (("dot", 0.0, 0.0),),
        " ": (),
    }

    @staticmethod
    def primitive_points(spec, step):
        kind = spec[0]
        if kind == "ell":
            cx, cy, rx, ry, a0, a1 = spec[1:]
            pts = Outline.arc(cx, cy, rx, ry, a0, a1, step)
            if abs(a1 - a0) >= 359.999:
                return pts[:-1], True
            return pts, False
        if kind == "line":
            x0, y0, x1, y1 = spec[1:]
            n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / max(step * 3.0, 1e-4))))
            t = np.linspace(0.0, 1.0, n + 1)[:, None]
            return np.array([x0, y0]) * (1.0 - t) + np.array([x1, y1]) * t, False
        if kind == "poly":
            return np.asarray(spec[1], np.float64), False
        if kind == "path":
            chunks = [MonolineFont.primitive_points(part, step)[0] for part in spec[1]]
            return Outline.dedupe(np.vstack(chunks), 1e-6, closed=False), False
        raise ValueError("unknown monoline primitive {}".format(kind))

    def glyph(self, char, step):
        spec = self.glyphs.get(char, self.glyphs.get(char.lower()))
        if spec is None:
            raise ValueError("monoline font has no glyph for {!r}".format(char))
        strokes = []
        dots = []
        for part in spec:
            if part[0] == "dot":
                dots.append((float(part[1]), float(part[2])))
                continue
            pts, closed = MonolineFont.primitive_points(part, step)
            strokes.append((pts, closed))
        return strokes, dots

    def layout(self, word, x_height, tube_radius, spacing=1.0, step=0.05):
        cursor = 0.0
        strokes = []
        dots = []
        gap = 0.34 * float(spacing) + 2.2 * float(tube_radius) / float(x_height)
        for char in str(word):
            if char == " ":
                cursor += 0.55 * float(spacing)
                continue
            glyph_strokes, glyph_dots = self.glyph(char, step)
            xs = [p[:, 0] for p, _ in glyph_strokes] + [np.array([d[0]]) for d in glyph_dots]
            left = float(min(x.min() for x in xs))
            right = float(max(x.max() for x in xs))
            shift = cursor - left
            for pts, closed in glyph_strokes:
                strokes.append((pts + np.array([shift, 0.0]), closed))
            for d in glyph_dots:
                dots.append((d[0] + shift, d[1]))
            cursor += (right - left) + gap
        cursor -= gap
        allp = np.vstack([p for p, _ in strokes] + ([np.array(dots)] if dots else []))
        lo = allp.min(axis=0)
        hi = allp.max(axis=0)
        mid = np.array([(lo[0] + hi[0]) * 0.5, 0.5])
        scale = float(x_height)
        placed = [((p - mid) * scale, closed) for p, closed in strokes]
        placed_dots = [((d[0] - mid[0]) * scale, (d[1] - mid[1]) * scale) for d in dots]
        return placed, placed_dots, {"width": float(hi[0] - lo[0]) * scale, "top": float(hi[1] - 0.5) * scale, "bottom": float(lo[1] - 0.5) * scale}


class SignsRecipes:
    families = {
        "lobed": {"plaque": "caramel", "outline": "ink", "letters": "cream", "piping": "gold", "post": "cream", "foot": "caramel"},
        "stop": {"base": "caramel", "base_top": "cream", "post": "cream", "arch": "honey", "arch_rim": "cream", "outline": "ink", "letters": "cream", "disc": "cream", "disc_rim": "caramel", "icon": "honey", "finial": "pink"},
        "disc": {"disc": "cream", "disc_rim": "caramel", "icon": "honey"},
        "arrow": {"plinth": "ink", "plinth_top": "caramel", "pillar": "caramel", "head": "honey", "band": "cream", "outline": "ink", "letters": "cream", "screen_frame": "cream", "bezel": "ink", "screen": "glow", "finial": "gold"},
        "totem": {"plinth": "ink", "plinth_top": "caramel", "body": "cream", "bezel": "ink", "screen": "glow", "trim": "gold", "outline": "ink", "letters": "honey", "plate": "cream", "art": "sky"},
        "sticker": {"plate": "cream", "art": "sky"},
        "squircle": {"plinth": "ink", "body": "caramel", "trim": "cream", "outline": "ink", "letters": "cream", "icon": "honey"},
        "script": {"stand": "mint", "plaque": "pink", "rim": "mint", "letters": "cream", "icon": "sky"},
        "word": {"outline": "ink", "letters": "cream"},
    }

    def __init__(self, font=None, resolution=8):
        self.glyphs = GlyphOutlines(font, resolution)
        self.monoline = MonolineFont()

    def role(self, family, roles, part):
        return (roles or {}).get(part) or self.families[family][part]

    @staticmethod
    def face_height(depth, edge, puff, puff_width, inset):
        r = min(max(float(edge), 0.0), float(depth) * 0.5 - 1e-4)
        s = max(float(inset), 0.0)
        cap = math.sqrt(max(r * r - (r - min(s, r)) ** 2, 0.0))
        t = min(max((s - r) / max(float(puff_width), 1e-4), 0.0), 1.0)
        return float(depth) * 0.5 - r + cap + float(puff) * t * t * (3.0 - 2.0 * t)

    @staticmethod
    def pillow_face(size, radius, puff, x, z):
        half = np.asarray(size, np.float64) * 0.5
        r = min(float(radius), float(half.min()) - 1e-4)
        inner = np.maximum(half - r, 1e-5)
        fx = (1.0 - min((x / inner[0]) ** 2, 1.0)) ** 2
        fz = (1.0 - min((z / inner[2]) ** 2, 1.0)) ** 2
        return inner[1] + float(puff) * fx * fz + r

    def slab(self, b, field, depth, edge=0.0, puff=0.0, puff_width=None, frame=None, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), plane="XZ", back_puff=True, role=None, fillet=0.0, op="union", detail=False, collide=False):
        frame = frame or Frame()
        lo, hi = field.bounds()
        depth = float(depth)
        r = float(min(max(edge, 0.0), depth * 0.5 - 1e-4))
        width = float(puff_width if puff_width is not None else max(3.0 * r, 0.25 * float(min(hi - lo))))
        params = {"depth": depth, "rounding": r, "puff": float(puff), "puff_width": width, "back_puff": bool(back_puff)}
        half = depth * 0.5 + max(float(puff), 0.0)
        extent = ((float(lo[0]), float(lo[1]), -half), (float(hi[0]), float(hi[1]), half))
        source = FieldSource(field, r + width + 0.01)
        return b.primitive("extrude", params, extent, frame.point(loc), frame.euler(rot), plane, role, fillet, op, False, None, detail, collide, source)

    def ground(self, b, fillet=0.012):
        return b.cut(point=(0.0, 0.0, 0.0), normal=(0.0, 0.0, -1.0), fillet=fillet)

    def word_field(self, text, height, max_width=None, spacing=1.0):
        loops, info = self.glyphs.layout(text, height=height, max_width=max_width, spacing=spacing)
        return Field2D().add(loops), info

    def layered_word(self, b, text, frame, face, height=0.3, max_width=None, centre=(0.0, 0.0), spacing=1.0, outline=0.075, plate_proud=0.016, letter_proud=0.026, embed=0.011, puff=0.0, roles=None, fillets=(0.015, 0.01), detail=False):
        letters, info = self.word_field(text, height, max_width, spacing)
        cap = info["height"]
        plate = letters.grown(outline * cap)
        plate_depth = plate_proud + embed
        plate_front = face - plate_proud
        plate_node = self.slab(b, plate, plate_depth, edge=0.42 * plate_depth, puff=0.0, frame=frame, loc=(centre[0], plate_front + plate_depth * 0.5, centre[1]), back_puff=False, role=self.role("word", roles, "outline"), fillet=fillets[0], detail=detail)
        letter_depth = letter_proud + embed
        letter_front = plate_front - letter_proud
        edge = min(0.46 * letter_depth, 0.075 * cap)
        lift = float(puff)
        letter_node = self.slab(b, letters, letter_depth, edge=edge, puff=lift, puff_width=0.085 * cap, frame=frame, loc=(centre[0], letter_front + letter_depth * 0.5, centre[1]), back_puff=False, role=self.role("word", roles, "letters"), fillet=fillets[1], detail=detail)
        return {"outline": plate_node, "letters": letter_node, "width": info["width"] + 2.0 * outline * cap, "height": cap * (1.0 + 2.0 * outline), "front": letter_front - lift}

    def piping(self, b, frame, path2d, depth_y, radius, closed=False, terminals=1.35, role=None, fillet=None):
        pts = np.asarray(path2d, np.float64)
        local = np.stack([pts[:, 0], np.broadcast_to(np.asarray(depth_y, np.float64), (len(pts),)), pts[:, 1]], axis=1)
        return b.tube(frame.points(local), radius, closed=closed, ends=0.0 if closed else terminals, role=role, fillet=0.42 * radius if fillet is None else fillet)

    def post(self, b, frame, x, top, radius=0.058, foot_radius=0.16, foot_height=0.12, y=0.0, roles=None, family="lobed", fillet=0.032):
        foot = b.round_cyl(foot_radius, foot_height, edge=0.45 * foot_height, loc=frame.point((x, y, 0.0)), rot=frame.euler(), role=self.role(family, roles, "foot"))
        stem = b.capsule(frame.point((x, y, 0.0)), frame.point((x, y, top)), radius, role=self.role(family, roles, "post"), fillet=fillet)
        return {"foot": foot, "post": stem}

    def cloud_top_field(self, width, height, lobes=3, amp=0.13, corner=0.2, blend=0.06):
        field = Field2D(blend=blend).add(Outline.rounded_rect(width, height, corner))
        pitch = (width - 1.2 * corner) / float(lobes)
        radius = 0.62 * pitch
        cy = height * 0.5 + amp - radius
        for i in range(int(lobes)):
            cx = -width * 0.5 + 0.6 * corner + pitch * (i + 0.5)
            field.add(Outline.circle(radius, (cx, cy)))
        return field

    def lobed_squircle_field(self, width, height, lobes=5, amp=0.07, exponent=5.0, blend=0.05):
        field = Field2D(blend=blend).add(Outline.squircle(width, height, exponent))
        span = 0.86 * width
        pitch = span / float(lobes)
        radius = 0.6 * pitch
        for i in range(int(lobes)):
            cx = -span * 0.5 + pitch * (i + 0.5)
            cy = Outline.squircle_top(width, height, exponent, cx) + amp - radius
            field.add(Outline.circle(radius, (cx, cy)))
        return field

    def lobed_plaque_sign(self, b, text="CAFE", base=(0.0, 0.0, 0.0), width=1.9, height=0.88, lobes=3, lobe_amp=0.13, corner=0.2, thickness=0.15, lift=1.12, letter_height=0.36, post_spacing=0.54, post_radius=0.058, foot_radius=0.16, piping_radius=0.042, piping_inset=0.096, piping_gap=0.5, face_puff=0.0, roles=None, ground=True, collide=True):
        frame = Frame(base)
        field = self.cloud_top_field(width, height, lobes, lobe_amp, corner)
        edge = 0.45 * thickness
        puff = face_puff
        width_puff = 0.16
        cz = lift + height * 0.5
        plaque = self.slab(b, field, thickness, edge, puff, width_puff, frame, (0.0, 0.0, cz), role=self.role("lobed", roles, "plaque"))
        face = -self.face_height(thickness, edge, puff, width_puff, 1.0)
        word = self.layered_word(b, text, frame, face, height=letter_height, max_width=width - 2.0 * piping_inset - 0.24, centre=(0.0, cz - 0.02), outline=0.075, plate_proud=0.018, letter_proud=0.03, embed=0.012, roles={"outline": self.role("lobed", roles, "outline"), "letters": self.role("lobed", roles, "letters")}, fillets=(0.016, 0.011))
        half_gap = math.degrees(math.atan2(piping_gap * 0.5, height * 0.5))
        path = field.contour(-piping_inset, np.linspace(-90.0 + half_gap, 270.0 - half_gap, 360))
        path = Outline.resample(path, 0.025, closed=False) + np.array([0.0, cz])
        tube_y = -self.face_height(thickness, edge, puff, width_puff, piping_inset) - 0.45 * piping_radius
        piping = self.piping(b, frame, path, tube_y, piping_radius, closed=False, role=self.role("lobed", roles, "piping"))
        posts = []
        for x in (-post_spacing * width * 0.5, post_spacing * width * 0.5):
            posts.append(self.post(b, frame, x, lift + 0.14, post_radius, foot_radius, roles=roles, family="lobed"))
        parts = {"plaque": plaque, "word": word, "piping": piping, "posts": posts}
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.0, cz + lobe_amp * 0.5)), (width, thickness + 0.05, height + lobe_amp))
            b.collider(frame.point((0.0, 0.0, lift * 0.5)), (post_spacing * width + 2.0 * foot_radius, 2.0 * foot_radius, lift))
        return parts

    def disc_sign(self, b, frame, centre, radius=0.32, depth=0.12, rim=0.07, icon="star", icon_scale=0.5, double_sided=True, roles=None, fillet=0.024):
        family = "disc"
        disc = b.round_cyl(radius, depth, edge=0.3 * depth, loc=frame.point(centre), rot=frame.euler((90.0, 0.0, 0.0)), role=self.role(family, roles, "disc"), fillet=fillet)
        ring = b.torus(radius, rim, loc=frame.point(centre), rot=frame.euler((90.0, 0.0, 0.0)), role=self.role(family, roles, "disc_rim"), fillet=0.014)
        icons = []
        sides = [frame, frame.turned(180.0)] if double_sided else [frame]
        local = np.asarray(centre, np.float64)
        for index, side in enumerate(sides):
            shape = Outline.star(icon_scale * radius, 0.5 * icon_scale * radius) if icon == "star" else Outline.heart(1.3 * icon_scale * radius)
            icon_depth = 0.046
            front = -depth * 0.5 - 0.026
            ux = local[0] if index == 0 else -local[0]
            uy = local[1] if index == 0 else -local[1]
            icons.append(self.slab(b, Field2D().add(shape), icon_depth, edge=0.45 * icon_depth, puff=0.008, puff_width=0.04, frame=side, loc=(ux, uy + front + icon_depth * 0.5, local[2]), back_puff=False, role=self.role(family, roles, "icon"), fillet=0.01))
        return {"disc": disc, "rim": ring, "icons": icons}

    def stop_sign(self, b, text="BUS", base=(0.0, 0.0, 0.0), height=2.75, arch_width=0.68, arch_height=0.86, arch_depth=0.12, disc_radius=0.32, disc_z=1.62, post_radius=0.05, letter_height=0.2, finial="heart", icon="star", double_sided=True, text_back=True, face_puff=0.0, roles=None, ground=True, collide=True):
        frame = Frame(base)
        za = height - arch_height * 0.5
        base_low = b.round_cyl(0.27, 0.16, edge=0.07, loc=frame.point((0.0, 0.0, 0.0)), rot=frame.euler(), role=self.role("stop", roles, "base"))
        base_high = b.round_cyl(0.17, 0.12, edge=0.055, loc=frame.point((0.0, 0.0, 0.1)), rot=frame.euler(), role=self.role("stop", roles, "base_top"), fillet=0.03)
        post = b.capsule(frame.point((0.0, 0.0, 0.1)), frame.point((0.0, 0.0, za - arch_height * 0.5 + 0.18)), post_radius, role=self.role("stop", roles, "post"), fillet=0.034)
        disc = self.disc_sign(b, frame, (0.0, 0.0, disc_z), disc_radius, icon=icon, double_sided=double_sided, roles={"disc": self.role("stop", roles, "disc"), "disc_rim": self.role("stop", roles, "disc_rim"), "icon": self.role("stop", roles, "icon")})
        field = Field2D().add(Outline.arch_top(arch_width, arch_height, 0.1))
        edge = 0.4 * arch_depth
        puff = face_puff
        width_puff = 0.08
        arch = self.slab(b, field, arch_depth, edge, puff, width_puff, frame, (0.0, 0.0, za), role=self.role("stop", roles, "arch"), fillet=0.028)
        rim_inset = 0.056
        rim_r = 0.027
        ring = field.contour(-rim_inset, np.linspace(0.0, 360.0, 300, endpoint=False))
        ring = Outline.resample(ring, 0.02) + np.array([0.0, za])
        rim_y = -self.face_height(arch_depth, edge, puff, width_puff, rim_inset) - 0.4 * rim_r
        face = -self.face_height(arch_depth, edge, puff, width_puff, 1.0)
        sides = [frame, frame.turned(180.0)] if double_sided else [frame]
        rims = []
        words = []
        for index, side in enumerate(sides):
            rims.append(self.piping(b, side, ring, rim_y, rim_r, closed=True, role=self.role("stop", roles, "arch_rim"), fillet=0.01))
            if index > 0 and not text_back:
                continue
            words.append(self.layered_word(b, text, side, face, height=letter_height, max_width=arch_width - 2.0 * rim_inset - 0.12, centre=(0.0, za - 0.08), outline=0.08, plate_proud=0.015, letter_proud=0.026, embed=0.011, roles={"outline": self.role("stop", roles, "outline"), "letters": self.role("stop", roles, "letters")}, fillets=(0.014, 0.009)))
        parts = {"base": [base_low, base_high], "post": post, "disc": disc, "arch": arch, "rims": rims, "words": words}
        if finial == "heart":
            parts["finial"] = self.slab(b, Field2D().add(Outline.heart(0.2)), 0.08, edge=0.034, puff=0.01, puff_width=0.05, frame=frame, loc=(0.0, 0.0, height + 0.085), role=self.role("stop", roles, "finial"), fillet=0.028)
        elif finial == "star":
            parts["finial"] = self.slab(b, Field2D().add(Outline.star(0.11, 0.058)), 0.065, edge=0.028, puff=0.01, puff_width=0.05, frame=frame, loc=(0.0, 0.0, height + 0.09), role=self.role("stop", roles, "finial"), fillet=0.024)
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.0, height * 0.5)), (2.0 * disc_radius + 0.16, 0.54, height))
        return parts

    def arrow_pillar(self, b, text="PARK", base=(0.0, 0.0, 0.0), pillar_height=1.86, pillar_size=(0.34, 0.3), head_length=1.34, head_height=0.46, head_depth=0.27, head_offset=0.26, direction=1.0, letter_height=0.2, back_text=True, screen=True, finial="star", face_puff=0.0, roles=None, ground=True, collide=True):
        frame = Frame(base)
        sign = 1.0 if direction >= 0.0 else -1.0
        plinth = b.round_box((0.84, 0.7, 0.2), 0.06, loc=frame.point((0.0, 0.0, 0.0)), rot=frame.euler(), role=self.role("arrow", roles, "plinth"))
        plinth_top = b.round_box((0.64, 0.54, 0.1), 0.045, loc=frame.point((0.0, 0.0, 0.13)), rot=frame.euler(), role=self.role("arrow", roles, "plinth_top"), fillet=0.02)
        w, d = pillar_size
        bottom = 0.16
        top = bottom + pillar_height
        pillar = b.round_box((w, d, pillar_height), 0.22 * min(w, d), loc=frame.point((0.0, 0.0, bottom + pillar_height * 0.5)), rot=frame.euler(), role=self.role("arrow", roles, "pillar"), fillet=0.03)
        parts = {"plinth": [plinth, plinth_top], "pillar": pillar}
        if screen:
            zs = top - 0.4
            block_front = -d * 0.5 - 0.06
            floor = block_front + 0.022
            parts["screen_frame"] = b.round_box((0.26, 0.09, 0.22), 0.04, loc=frame.point((0.0, block_front + 0.045, zs)), rot=frame.euler(), role=self.role("arrow", roles, "screen_frame"), fillet=0.018)
            parts["screen_recess"] = b.round_box((0.19, 0.08, 0.15), 0.035, loc=frame.point((0.0, floor - 0.04, zs)), rot=frame.euler(), role=self.role("arrow", roles, "bezel"), op="subtract", fillet=0.01)
            parts["screen"] = b.round_box((0.17, 0.014, 0.13), 0.007, loc=frame.point((0.0, floor - 0.005, zs)), rot=frame.euler(), role=self.role("arrow", roles, "screen"), fillet=0.005)
        zh = top + head_height * 0.5 - 0.12
        cx = sign * head_offset
        field = Field2D().add(Outline.arrow(head_length, head_height, 0.26, head_height * 0.42, 0.07, 0.07, sign))
        edge = 0.34 * head_depth
        puff = face_puff
        width_puff = 0.1
        head = self.slab(b, field, head_depth, edge, puff, width_puff, frame, (cx, 0.0, zh), role=self.role("arrow", roles, "head"), fillet=0.035)
        tail_x = cx - sign * head_length * 0.5
        band_x = tail_x + sign * 0.2
        band = b.round_box((0.13, head_depth + 0.04, head_height + 0.04), 0.055, loc=frame.point((band_x, 0.0, zh)), rot=frame.euler(), role=self.role("arrow", roles, "band"), fillet=0.015)
        face = -self.face_height(head_depth, edge, puff, width_puff, 1.0)
        tip_x = cx + sign * (head_length * 0.5 - 0.2)
        text_x = 0.5 * (band_x + sign * 0.08 + tip_x)
        text_room = abs(tip_x - (band_x + sign * 0.08)) - 0.04
        sides = [(frame, text_x)] + ([(frame.turned(180.0), -text_x)] if back_text else [])
        words = []
        for side, x in sides:
            words.append(self.layered_word(b, text, side, face, height=letter_height, max_width=text_room, centre=(x, zh), outline=0.08, plate_proud=0.015, letter_proud=0.025, embed=0.011, roles={"outline": self.role("arrow", roles, "outline"), "letters": self.role("arrow", roles, "letters")}, fillets=(0.014, 0.01)))
        parts.update({"head": head, "band": band, "words": words})
        if finial == "star":
            parts["finial"] = self.slab(b, Field2D().add(Outline.star(0.11, 0.058)), 0.065, edge=0.028, puff=0.01, puff_width=0.05, frame=frame, loc=(band_x, 0.0, zh + head_height * 0.5 + 0.1), role=self.role("arrow", roles, "finial"), fillet=0.024)
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.0, top * 0.5)), (0.84, 0.7, top))
            b.collider(frame.point((cx, 0.0, zh)), (head_length, head_depth + 0.05, head_height + 0.05))
        return parts

    def sticker_plate(self, b, frame, art, centre, border=0.022, thickness=0.04, art_lift=0.0045, edge=None, double_sided=True, roles=None, fillet=0.0):
        plate_field = art.grown(border)
        plate = self.slab(b, plate_field, thickness, edge=0.36 * thickness if edge is None else edge, frame=frame, loc=centre, role=self.role("sticker", roles, "plate"), fillet=fillet)
        if double_sided:
            art_depth = thickness + 2.0 * art_lift
            art_loc = tuple(centre)
        else:
            art_depth = 0.5 * thickness + art_lift
            art_loc = (centre[0], centre[1] - 0.5 * thickness - art_lift + 0.5 * art_depth, centre[2])
        slot = self.slab(b, art, art_depth, edge=min(0.0035, 0.45 * art_depth), frame=frame, loc=art_loc, back_puff=double_sided, role=self.role("sticker", roles, "art"), fillet=0.002)
        lo, hi = art.bounds()
        info = {"centre": frame.point((centre[0] + 0.5 * (lo[0] + hi[0]), centre[1], centre[2] + 0.5 * (lo[1] + hi[1]))), "size": [float(hi[0] - lo[0]), float(hi[1] - lo[1])], "plane": "XZ", "double_sided": bool(double_sided), "role": self.role("sticker", roles, "art")}
        return {"plate": plate, "art": slot, "slot": info}

    def cloud_art(self, width=0.5, star=True):
        s = width / 0.5
        field = Field2D(blend=0.022 * s)
        field.add(Outline.rounded_rect(0.42 * s, 0.14 * s, 0.07 * s, (-0.01 * s, -0.06 * s)))
        field.add(Outline.circle(0.09 * s, (-0.13 * s, -0.005 * s)))
        field.add(Outline.circle(0.12 * s, (0.015 * s, 0.04 * s)))
        field.add(Outline.circle(0.08 * s, (0.145 * s, -0.015 * s)))
        if star:
            field.add(Outline.star(0.092 * s, 0.046 * s, centre=(0.2 * s, 0.115 * s), rotation=98.0, tip=0.16 * 0.092 * s, valley=0.08 * 0.092 * s))
        return field

    def totem(self, b, text="INFO", base=(0.0, 0.0, 0.0), width=0.86, depth=0.36, height=1.62, screen=(0.6, 0.66), letter_height=0.16, sticker=True, puff=(0.0, 0.0, 0.0), roles=None, ground=True, collide=True):
        frame = Frame(base)
        plinth = b.round_box((width + 0.2, depth + 0.2, 0.18), 0.06, loc=frame.point((0.0, 0.0, 0.0)), rot=frame.euler(), role=self.role("totem", roles, "plinth"))
        plinth_top = b.round_box((width + 0.1, depth + 0.1, 0.08), 0.035, loc=frame.point((0.0, 0.0, 0.12)), rot=frame.euler(), role=self.role("totem", roles, "plinth_top"), fillet=0.018)
        bottom = 0.15
        size = (width, depth, height)
        radius = 0.09
        cz = bottom + height * 0.5
        body = b.pillow_box(size, radius, puff, loc=frame.point((0.0, 0.0, cz)), rot=frame.euler(), role=self.role("totem", roles, "body"), fillet=0.035)
        sw, sh = screen
        zs = bottom + height - 0.12 - sh * 0.5 - 0.06
        floor = -depth * 0.5 + 0.014
        recess = b.round_box((sw + 0.06, 0.16, sh + 0.06), 0.055, loc=frame.point((0.0, floor - 0.08, zs)), rot=frame.euler(), role=self.role("totem", roles, "bezel"), op="subtract", fillet=0.014)
        glow = b.round_box((sw, 0.018, sh), 0.02, loc=frame.point((0.0, floor - 0.002, zs)), rot=frame.euler(), role=self.role("totem", roles, "screen"), fillet=0.006)
        trim_r = 0.024
        path = Outline.resample(Outline.rounded_rect(sw + 0.135, sh + 0.135, 0.1), 0.02)
        trim_y = np.array([-SignsRecipes.pillow_face(size, radius, puff[1], p[0], p[1] + zs - cz) - 0.4 * trim_r for p in path])
        local = np.stack([path[:, 0], trim_y, path[:, 1] + zs], axis=1)
        trim = b.tube(frame.points(local), trim_r, closed=True, role=self.role("totem", roles, "trim"), fillet=0.009)
        zw = bottom + 0.25
        face = -SignsRecipes.pillow_face(size, radius, puff[1], 0.0, zw - cz) + 0.002
        word = self.layered_word(b, text, frame, face, height=letter_height, max_width=width - 0.24, centre=(0.0, zw), outline=0.085, plate_proud=0.015, letter_proud=0.025, embed=0.013, roles={"outline": self.role("totem", roles, "outline"), "letters": self.role("totem", roles, "letters")}, fillets=(0.015, 0.01))
        parts = {"plinth": [plinth, plinth_top], "body": body, "recess": recess, "screen": glow, "trim": trim, "word": word}
        if sticker:
            art = self.cloud_art(0.7)
            parts["sticker"] = self.sticker_plate(b, frame, art, (0.0, -0.04, bottom + height + 0.08), border=0.03, thickness=0.05, roles={"plate": self.role("totem", roles, "plate"), "art": self.role("totem", roles, "art")}, fillet=0.024)
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.0, (bottom + height) * 0.5)), (width + 0.2, depth + 0.2, bottom + height))
        return parts

    def squircle_sign(self, b, text="MART", base=(0.0, 0.0, 0.0), width=1.0, height=1.3, lobes=5, lobe_amp=0.07, exponent=5.0, thickness=0.18, letter_height=0.19, rim_inset=0.094, rim_radius=0.04, icon="bag", face_puff=0.0, roles=None, ground=True, collide=True):
        frame = Frame(base)
        plinth = b.round_box((width + 0.08, 0.46, 0.2), 0.06, loc=frame.point((0.0, 0.0, 0.0)), rot=frame.euler(), role=self.role("squircle", roles, "plinth"))
        field = self.lobed_squircle_field(width, height, lobes, lobe_amp, exponent)
        edge = 0.44 * thickness
        puff = face_puff
        width_puff = 0.17
        cz = 0.07 + height * 0.5
        body = self.slab(b, field, thickness, edge, puff, width_puff, frame, (0.0, 0.0, cz), role=self.role("squircle", roles, "body"), fillet=0.035)
        ring = field.contour(-rim_inset, np.linspace(0.0, 360.0, 360, endpoint=False))
        ring = Outline.resample(ring, 0.02) + np.array([0.0, cz])
        tube_y = -self.face_height(thickness, edge, puff, width_puff, rim_inset) - 0.42 * rim_radius
        rim = self.piping(b, frame, ring, tube_y, rim_radius, closed=True, role=self.role("squircle", roles, "trim"), fillet=0.012)
        divider_v = 0.17 * height
        left, right = field.width_at(-rim_inset, divider_v)
        divider_r = 0.8 * rim_radius
        divider_y = -self.face_height(thickness, edge, puff, width_puff, 0.25) - 0.42 * divider_r
        divider = self.piping(b, frame, np.array([[left, divider_v + cz], [right, divider_v + cz]]), divider_y, divider_r, closed=False, terminals=0.0, role=self.role("squircle", roles, "trim"), fillet=0.016)
        face = -self.face_height(thickness, edge, puff, width_puff, 1.0)
        top_v = Outline.squircle_top(width, height, exponent, 0.0) - rim_inset - rim_radius
        word = self.layered_word(b, text, frame, face, height=letter_height, max_width=right - left - 0.14, centre=(0.0, cz + 0.5 * (divider_v + divider_r + top_v) - 0.005), outline=0.08, plate_proud=0.016, letter_proud=0.026, roles={"outline": self.role("squircle", roles, "outline"), "letters": self.role("squircle", roles, "letters")}, fillets=(0.015, 0.01))
        parts = {"plinth": plinth, "body": body, "rim": rim, "divider": divider, "word": word}
        if icon == "bag":
            parts["icon"] = self.bag_icon(b, frame, (0.0, face, cz - 0.17 * height), 0.32, role=self.role("squircle", roles, "icon"))
        elif icon == "star":
            parts["icon"] = self.slab(b, Field2D().add(Outline.star(0.16, 0.084)), 0.042, edge=0.019, puff=0.009, puff_width=0.05, frame=frame, loc=(0.0, face - 0.026 + 0.021, cz - 0.17 * height), back_puff=False, role=self.role("squircle", roles, "icon"), fillet=0.01)
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.0, 0.5 * (cz + height * 0.5 + lobe_amp))), (width + 0.08, 0.46, cz + height * 0.5 + lobe_amp))
        return parts

    def bag_icon(self, b, frame, anchor, width, role=None):
        x, face, z = anchor
        body_h = 0.78 * width
        depth = 0.046
        proud = 0.028
        corners = np.array([[-0.5 * width, -0.5 * body_h], [0.5 * width, -0.5 * body_h], [0.42 * width, 0.5 * body_h], [-0.42 * width, 0.5 * body_h]])
        field = Field2D().add(Outline.fillet(corners, [0.05, 0.05, 0.04, 0.04]))
        body = self.slab(b, field, depth, edge=0.02, puff=0.009, puff_width=0.05, frame=frame, loc=(x, face - proud + depth * 0.5, z), back_puff=False, role=role, fillet=0.01)
        radius = 0.24 * width
        handle_r = 0.015
        arc = Outline.arc(x, z + 0.5 * body_h - 0.012, radius, radius * 1.1, 0.0, 180.0, 0.012)
        handle = self.piping(b, frame, arc, face - 0.4 * handle_r, handle_r, closed=False, terminals=0.0, role=role, fillet=0.007)
        return {"body": body, "handle": handle}

    def script_word(self, b, word, frame, face, x_height=0.19, tube_radius=0.021, centre=(0.0, 0.0), spacing=1.0, embed=0.45, role=None, fillet=0.007):
        strokes, dots, info = self.monoline.layout(word, x_height, tube_radius, spacing)
        y = face - (1.0 - embed) * tube_radius
        nodes = []
        with b.group("script_" + str(word), fillet=fillet):
            for pts, closed in strokes:
                path = Outline.resample(pts, 0.008, closed=closed) + np.asarray(centre, np.float64)
                local = np.stack([path[:, 0], np.full(len(path), y), path[:, 1]], axis=1)
                nodes.append(b.tube(frame.points(local), tube_radius, closed=closed, ends=1.0 if not closed else 0.0, role=role, fillet=0.005))
            for dx, dz in dots:
                nodes.append(b.sphere(1.3 * tube_radius, loc=frame.point((dx + centre[0], y, dz + centre[1])), role=role, fillet=0.004))
        return {"tubes": nodes, "width": info["width"], "top": info["top"], "bottom": info["bottom"]}

    def script_plaque(self, b, word="hello", base=(0.0, 0.0, 0.0), width=1.3, height=0.66, thickness=0.08, corner=0.16, rim_radius=0.05, x_height=0.19, tube_radius=0.021, tilt=8.0, icon="heart", face_puff=0.0, roles=None, ground=True, collide=True):
        frame = Frame(base)
        stand = b.pillow_box((width * 0.84, 0.36, 0.16), 0.06, (0.0, 0.0, 0.01), loc=frame.point((0.0, 0.03, 0.0)), rot=frame.euler(), role=self.role("script", roles, "stand"))
        panel = Frame(frame.point((0.0, 0.0, 0.05)), (-float(tilt), 0.0, 0.0))
        field = Field2D().add(Outline.rounded_rect(width, height, corner))
        edge = 0.42 * thickness
        puff = face_puff
        width_puff = 0.1
        plaque = self.slab(b, field, thickness, edge, puff, width_puff, panel, (0.0, 0.0, height * 0.5), role=self.role("script", roles, "plaque"), fillet=0.028)
        rim_inset = 0.9 * rim_radius
        ring = Outline.resample(field.contour(-rim_inset, np.linspace(0.0, 360.0, 320, endpoint=False)), 0.02) + np.array([0.0, height * 0.5])
        rim_y = -self.face_height(thickness, edge, puff, width_puff, rim_inset) - 0.3 * rim_radius
        rim = self.piping(b, panel, ring, rim_y, rim_radius, closed=True, role=self.role("script", roles, "rim"), fillet=0.014)
        face = -self.face_height(thickness, edge, puff, width_puff, 1.0)
        layout_width = self.monoline.layout(word, x_height, tube_radius)[2]["width"]
        icon_room = 0.2 if icon else 0.0
        letters = self.script_word(b, word, panel, face, x_height, tube_radius, centre=(-0.5 * icon_room, height * 0.5 - 0.03 * height), role=self.role("script", roles, "letters"))
        parts = {"stand": stand, "plaque": plaque, "rim": rim, "letters": letters}
        if icon == "heart":
            hx = 0.5 * layout_width - 0.5 * icon_room + 0.14
            parts["icon"] = self.slab(b, Field2D().add(Outline.heart(0.13)), 0.042, edge=0.018, puff=0.008, puff_width=0.035, frame=panel, loc=(hx, face - 0.024 + 0.021, height * 0.5 + 0.012), back_puff=False, role=self.role("script", roles, "icon"), fillet=0.01)
        if ground:
            parts["ground"] = self.ground(b)
        if collide:
            b.collider(frame.point((0.0, 0.03, 0.5 * (height + 0.06))), (width + 0.06, 0.38, height + 0.06))
        return parts


class PanelNormals:
    @staticmethod
    def labels(count, fa, fb):
        labels = np.arange(count)
        for _ in range(512):
            m = np.minimum(labels[fa], labels[fb])
            new = labels.copy()
            np.minimum.at(new, fa, m)
            np.minimum.at(new, fb, m)
            new = new[new]
            if np.array_equal(new, labels):
                break
            labels = new
        return labels

    @staticmethod
    def flatten(me, coplanar_deg=0.75, max_tilt_deg=9.0, min_area=0.003, min_share=0.002):
        n = len(me.polygons)
        if n == 0 or not me.has_custom_normals:
            return {"panels": 0, "loops": 0}
        normals = np.empty(n * 3, np.float64)
        me.polygons.foreach_get("normal", normals)
        normals = normals.reshape(-1, 3)
        areas = np.empty(n, np.float64)
        me.polygons.foreach_get("area", areas)
        sizes = np.empty(n, np.int32)
        me.polygons.foreach_get("loop_total", sizes)
        loop_face = np.repeat(np.arange(n), sizes)
        loop_edge = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("edge_index", loop_edge)
        loop_vert = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", loop_vert)
        order = np.argsort(loop_edge, kind="stable")
        edges = loop_edge[order]
        faces = loop_face[order]
        same = np.nonzero(edges[:-1] == edges[1:])[0]
        fa = faces[same]
        fb = faces[same + 1]
        flat = (normals[fa] * normals[fb]).sum(axis=1) > math.cos(math.radians(coplanar_deg))
        labels = PanelNormals.labels(n, fa[flat], fb[flat])
        region_area = np.bincount(labels, weights=areas, minlength=n)
        big = region_area >= max(float(min_area), float(min_share) * float(areas.sum()))
        region_normal = np.zeros((n, 3))
        np.add.at(region_normal, labels, normals * areas[:, None])
        region_normal /= np.maximum(np.linalg.norm(region_normal, axis=1, keepdims=True), 1e-12)
        corner = np.empty(len(me.loops) * 3, np.float64)
        me.corner_normals.foreach_get("vector", corner)
        corner = corner.reshape(-1, 3)
        face_region = labels[loop_face]
        member = big[face_region]
        vertex_region = np.full(len(me.vertices), -1, np.int64)
        vertex_count = np.zeros(len(me.vertices), np.int64)
        if member.any():
            pairs = np.unique(np.stack([loop_vert[member], face_region[member]], axis=1), axis=0)
            np.add.at(vertex_count, pairs[:, 0], 1)
            vertex_region[pairs[:, 0]] = pairs[:, 1]
        target_region = np.where(member, face_region, np.where(vertex_count[loop_vert] == 1, vertex_region[loop_vert], -1))
        valid = target_region >= 0
        target = region_normal[np.maximum(target_region, 0)]
        close = (corner * target).sum(axis=1) >= math.cos(math.radians(max_tilt_deg))
        change = valid & close
        corner[change] = target[change]
        me.normals_split_custom_set(corner.tolist())
        me.update()
        return {"panels": int(len(np.unique(labels[big[labels]]))), "loops": int(change.sum()), "panel_share": round(float(areas[big[labels]].sum() / max(areas.sum(), 1e-12)), 4)}


class PlanarHold:
    settings = ("hold_angle", "hold_area", "hold_share", "hold_reach", "hold_tilt", "hold_flat")
    needs = ("reduce", "protection", "clean_collapse", "snap_role_lines", "relabel_faces", "discard")
    hold_angle = 2.0
    hold_area = 0.01
    hold_share = 0.15
    hold_reach = 0.02
    hold_tilt = 1.0
    hold_flat = None
    hold_pins = None
    hold_count = -1

    @staticmethod
    def compatible(engine):
        cls = getattr(engine, "SculptBuilder", None)
        return cls is not None and hasattr(engine, "MeshArrays") and all(hasattr(cls, name) for name in PlanarHold.needs)

    def planar_enough(self, face):
        if self.hold_flat is None:
            return True
        n = np.array(face.normal[:], np.float64)
        co = np.array([v.co[:] for v in face.verts], np.float64)
        return float(np.abs((co - co.mean(axis=0)) @ n).max()) <= float(self.hold_flat)

    def protection(self, me, points, radius, detail_owners):
        base = np.asarray(super().protection(me, points, radius, detail_owners), np.int64)
        if self.hold_pins is None or len(self.hold_pins) == 0 or len(me.vertices) != self.hold_count:
            return base
        return np.union1d(base, self.hold_pins)

    @staticmethod
    def thin(points, cap):
        if len(points) <= cap:
            return np.arange(len(points))
        lo = points.min(axis=0)
        step = max(float((points.max(axis=0) - lo).max()), 1e-6) / 1024.0
        first = np.arange(len(points))
        for _ in range(40):
            cells = np.floor((points - lo) / step).astype(np.int64)
            first = np.unique(cells, axis=0, return_index=True)[1]
            if len(first) <= cap:
                break
            step *= 1.3
        return np.sort(first)

    def snap_boundary(self, owners):
        verts = []
        inward = []
        normal = []
        for v, loops in owners.items():
            if len(loops) != 1:
                continue
            loop = loops[0]
            n = np.array(loop.face.normal[:], np.float64)
            t = np.array(loop.link_loop_next.vert.co[:], np.float64) - np.array(loop.link_loop_prev.vert.co[:], np.float64)
            d = np.cross(n, t)
            length = float(np.linalg.norm(d))
            if length < 1e-9:
                continue
            verts.append(v)
            inward.append(d / length)
            normal.append(n)
        if not verts:
            return 0
        steps = np.linspace(0.0, 1.0, 9)
        start = np.array([v.co[:] for v in verts], np.float64)
        inward = np.array(inward)
        normal = np.array(normal)
        probe = start[:, None, :] + inward[:, None, :] * (self.hold_reach * steps)[None, :, None]
        flat = self.probe_field.project(probe.reshape(-1, 3).astype(np.float32), self.voxel * 0.5, 2, 4.0 * self.voxel).reshape(len(verts), len(steps), 3).astype(np.float64)
        tilt = np.degrees(np.arccos(np.clip((self.probe_field.normals(flat.reshape(-1, 3).astype(np.float32), self.voxel * 0.5).reshape(len(verts), len(steps), 3) * normal[:, None, :]).sum(axis=2), -1.0, 1.0)))
        off_plane = np.abs(((flat - start[:, None, :]) * normal[:, None, :]).sum(axis=2))
        good = (tilt <= self.hold_tilt) & (off_plane <= max(0.002, 0.4 * self.voxel))
        pick = np.where(good.any(axis=1), good.argmax(axis=1), -1)
        moved = 0
        for i, v in enumerate(verts):
            if pick[i] > 0:
                v.co = flat[i, pick[i]].tolist()
                moved += 1
        return moved

    def planar_hold(self, ob, limit):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        before = len(bm.faces)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(self.hold_angle), use_dissolve_boundaries=False, verts=bm.verts[:], edges=bm.edges[:], delimit={"MATERIAL"})
        ngons = [f for f in bm.faces if len(f.verts) > 3]
        held = set()
        owners = {}
        regions = 0
        for face in ngons:
            if face.calc_area() >= self.hold_area and self.planar_enough(face):
                regions += 1
                held.update(face.verts)
                for loop in face.loops:
                    owners.setdefault(loop.vert, []).append(loop)
        snapped = self.snap_boundary(owners) if self.hold_reach > 0.0 else 0
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        index = np.array(sorted(v.index for v in held if v.is_valid), np.int64)
        if len(index):
            coords = np.array([bm.verts[int(i)].co[:] for i in index], np.float64).reshape(-1, 3)
            index = index[PlanarHold.thin(coords, max(16, int(self.hold_share * limit)))]
        after = len(bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
        self.hold_pins = index
        self.hold_count = len(ob.data.vertices)
        return {"faces_before": before, "faces_after": after, "regions": regions, "pins": int(len(index)), "snapped": int(snapped)}

    def reduce(self, high, owners):
        arrays = self.engine.MeshArrays
        poly_tris = sum(arrays.tris(part["mesh"]) for part in self.poly_parts)
        limit = max(500, int((self.budget - poly_tris) * 0.985))
        high.data.calc_loop_triangles()
        areas = np.empty(len(high.data.loop_triangles), np.float32)
        high.data.loop_triangles.foreach_get("area", areas)
        area = float(areas.sum())
        stage_target = int(limit * self.stage_ratio)
        stage, stage_report = self.clean_collapse(high, stage_target, 2.5 * math.sqrt(2.0 * area / max(1, stage_target)), np.zeros(0, np.int64), 1)
        hold = self.planar_hold(stage, limit)
        detail_owners = np.array([i for i, o in enumerate(self.owners) if o["detail"]], np.int64)
        if len(detail_owners):
            centres = arrays.polygon_vectors(stage.data, "center")
            share = float(np.isin(self.probe_field.owners(centres), detail_owners).mean())
            if share > self.detail_share:
                self.warnings.append("detail nodes cover {:.0%} of the surface (> {:.0%}); detail density not protected".format(share, self.detail_share))
                detail_owners = np.zeros(0, np.int64)
        low, report = self.clean_collapse(stage, limit, 2.5 * math.sqrt(2.0 * area / max(1, limit)), detail_owners, 3)
        self.hold_pins = None
        self.hold_count = -1
        report["role_line_snapped"] = self.snap_role_lines(low.data, high) if self.crisp_roles else 0
        report["role_faces_relabelled"] = self.relabel_faces(low.data) if self.crisp_roles else 0
        report["stage"] = stage_report
        report["planar_hold"] = hold
        self.log.append("planar_hold " + json.dumps(hold))
        self.discard(stage)
        low.name = self.id
        low.data.name = self.id
        self.clock.mark("reduce")
        return low, report


class SignsBuilder:
    @staticmethod
    def create(engine, prop_id, panel_tilt=9.0, hold=None, **kwargs):
        bases = (engine.SculptBuilder,)
        attrs = {"engine": engine}
        if hold is not None and PlanarHold.compatible(engine):
            bases = (PlanarHold, engine.SculptBuilder)
            attrs.update({key: value for key, value in hold.items() if key in PlanarHold.settings})
        if panel_tilt is not None and panel_tilt > 0.0:
            attrs.update({"transfer_normals": SignsBuilder.transfer_normals, "panel_tilt": float(panel_tilt)})
        if len(bases) == 1 and "panel_tilt" not in attrs:
            return engine.SculptBuilder(prop_id, **kwargs)
        cls = type("SignsSculptBuilder", bases, attrs)
        return cls(prop_id, **kwargs)

    @staticmethod
    def transfer_normals(builder, low, high):
        builder.engine.SculptBuilder.transfer_normals(builder, low, high)
        builder.log.append({"panel_normals": PanelNormals.flatten(low.data, max_tilt_deg=builder.panel_tilt)})


class PartStats:
    @staticmethod
    def collect(parts, prefix, found):
        if isinstance(parts, dict):
            for key, value in parts.items():
                PartStats.collect(value, prefix + "/" + str(key) if prefix else str(key), found)
        elif isinstance(parts, (list, tuple)):
            for index, value in enumerate(parts):
                PartStats.collect(value, "{}/{}".format(prefix, index), found)
        elif hasattr(parts, "owner") and int(getattr(parts, "owner", -1)) >= 0:
            found[int(parts.owner)] = prefix
        return found

    @staticmethod
    def tris(b, prop_id, parts):
        ob = bpy.data.objects.get(prop_id)
        field = getattr(b, "probe_field", None)
        if ob is None or field is None or ob.type != "MESH":
            return {}
        me = ob.data
        centres = np.empty(len(me.polygons) * 3, np.float32)
        me.polygons.foreach_get("center", centres)
        centres = centres.reshape(-1, 3) - np.asarray(b.shift, np.float32)
        owners = field.owners(centres)
        names = PartStats.collect(parts, "", {})
        counts = {}
        for owner, count in zip(*np.unique(owners, return_counts=True)):
            name = names.get(int(owner), "other")
            counts[name] = counts.get(name, 0) + int(count)
        return dict(sorted(counts.items(), key=PartStats.order))

    @staticmethod
    def order(item):
        return -item[1]


class DemoSet:
    palette = {
        "cream": {"color": "#FFFBF4", "finish": "satin"},
        "caramel": {"color": "#C48E62", "finish": "satin"},
        "ink": {"color": "#3B281E", "finish": "matte"},
        "outline": {"color": "#4A3327", "finish": "matte"},
        "honey": {"color": "#E8B04B", "finish": "satin"},
        "pink": {"color": "#F2B8C6", "finish": "satin"},
        "mint": {"color": "#A8D8C8", "finish": "satin"},
        "sky": {"color": "#A9CBEA", "finish": "satin"},
        "gold": {"color": "#D9A441", "finish": "gloss"},
        "glow": {"color": "#FFF3DC", "finish": "emissive"},
    }
    props = (
        {"id": "1nfx_sign_word", "recipe": "lobed_plaque_sign", "budget": 3900, "kwargs": {"text": "CAFE", "piping_radius": 0.05}, "hold": {}},
        {"id": "1nfx_sign_stop", "recipe": "stop_sign", "budget": 2500, "kwargs": {"text": "BUS", "text_back": False}, "hold": {}},
        {"id": "1nfx_sign_arrow", "recipe": "arrow_pillar", "budget": 3700, "kwargs": {"text": "PARK"}, "hold": {"hold_reach": 0.0, "hold_share": 0.08}},
        {"id": "1nfx_sign_totem", "recipe": "totem", "budget": 3950, "kwargs": {"text": "INFO"}, "hold": {"hold_reach": 0.0, "hold_share": 0.08, "hold_flat": 0.001}},
        {"id": "1nfx_sign_shop", "recipe": "squircle_sign", "budget": 3000, "kwargs": {"text": "MART", "rim_radius": 0.048}, "hold": {}},
        {"id": "1nfx_sign_script", "recipe": "script_plaque", "budget": 1950, "kwargs": {"word": "hello"}, "hold": {}},
    )

    def __init__(self, engine, recipes, out_dir, set_name="1nfx_sign", voxel=0.005):
        self.engine = engine
        self.recipes = recipes
        self.out_dir = os.path.abspath(out_dir)
        self.set_name = set_name
        self.voxel = float(voxel)

    def build(self, spec, budget=None):
        started = time.perf_counter()
        b = SignsBuilder.create(self.engine, spec["id"], hold=spec.get("hold"), budget=int(budget or spec["budget"]), lod_dist=120.0, set_name=self.set_name, archetype="sign", palette=dict(self.palette), default_role="cream", voxel=float(spec.get("voxel", self.voxel)), colliders="auto")
        parts = getattr(self.recipes, spec["recipe"])(b, **spec["kwargs"])
        result = b.build(self.out_dir)
        result["seconds"] = round(time.perf_counter() - started, 2)
        result["recipe"] = spec["recipe"]
        result["part_tris"] = PartStats.tris(b, spec["id"], parts)
        result["art_slots"] = [parts["sticker"]["slot"]] if isinstance(parts.get("sticker"), dict) else []
        if not bpy.app.background:
            DemoSet.release(spec["id"])
        return result

    @staticmethod
    def release(prop_id):
        for name in (prop_id, prop_id + "_rig"):
            ob = bpy.data.objects.get(name)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        coll = bpy.data.collections.get(prop_id + "_collision")
        if coll is not None:
            for ob in list(coll.objects):
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(coll)


class QARunner:
    def __init__(self, loader, out_dir, blender=None):
        self.loader = loader
        self.out_dir = os.path.abspath(out_dir)
        self.blender = blender or bpy.app.binary_path
        self.qa_dir = os.path.join(self.out_dir, "qa")
        os.makedirs(self.qa_dir, exist_ok=True)

    def run(self, script, args, factory=True, timeout=900):
        cmd = [self.blender, "-b"] + (["--factory-startup"] if factory else []) + ["-t", str(max(1, int(bpy.context.scene.render.threads)))] + ["-P", script, "--"] + [str(a) for a in args]
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return done.returncode, done.stdout + done.stderr

    @staticmethod
    def tail(text, prefix):
        found = [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]
        return found[-1] if found else ""

    @staticmethod
    def counts(line):
        fail = int(line.split("fail=")[1].split()[0]) if "fail=" in line else -1
        warn = int(line.split("warn=")[1].split()[0]) if "warn=" in line else -1
        return fail, warn

    def sculpt_qa(self, prop_id):
        blend = os.path.join(self.out_dir, prop_id + ".blend")
        high = os.path.join(self.out_dir, "_high", prop_id + "_high.blend")
        report = os.path.join(self.qa_dir, prop_id + ".json")
        args = ["--blend", blend, "--target", "prop", "--json", report]
        if os.path.isfile(high):
            args += ["--high", high]
        code, text = self.run(self.loader.script("validate_sculpt.py"), args)
        with open(os.path.join(self.qa_dir, prop_id + ".log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        line = QARunner.tail(text, "SCULPT_QA fail=")
        fail, warn = QARunner.counts(line)
        issues = [l.strip() for l in text.splitlines() if l.startswith("WARN") or l.startswith("FAIL")]
        return {"id": prop_id, "line": line, "fail": fail, "warn": warn, "issues": issues, "json": report, "exit": code}

    def merge(self, results):
        drawables = []
        for item in results:
            if os.path.isfile(item["json"]):
                with open(item["json"], encoding="utf-8") as handle:
                    drawables.extend(json.load(handle).get("drawables", []))
        merged = {"drawables": drawables, "fail": sum(max(r["fail"], 0) for r in results), "warn": sum(max(r["warn"], 0) for r in results)}
        path = os.path.join(self.qa_dir, "sculpt_qa.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=1)
        return path, merged

    def prop_qa(self):
        script = self.loader.prop_forge("scripts", "blender", "validate_prop.py")
        if not os.path.isfile(script):
            return {"line": "validate_prop.py not found", "files": []}
        code, text = self.run(script, ["--blend", self.out_dir])
        with open(os.path.join(self.qa_dir, "validate_prop.log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        files = []
        current = None
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("== "):
                current = os.path.basename(line[3:])
            elif line.startswith("RESULT fail=") and current:
                fail, warn = QARunner.counts(line)
                files.append({"file": current, "fail": fail, "warn": warn})
        return {"line": QARunner.tail(text, "TOTAL"), "files": files, "exit": code}

    def render(self, qa_json, res=900, views=4):
        renders = os.path.join(self.out_dir, "renders")
        code, text = self.run(self.loader.script("render_sculpt.py"), ["--blend", self.out_dir, "--out", renders, "--qa", qa_json, "--res", res, "--views", views])
        with open(os.path.join(self.qa_dir, "render.log"), "w", encoding="utf-8") as handle:
            handle.write(text)
        return {"line": QARunner.tail(text, "SCULPT_RENDER"), "folder": renders, "exit": code}


class DemoCli:
    def __init__(self, argv):
        parser = argparse.ArgumentParser(prog="signs.py")
        parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "sculpt_forge_signs"))
        parser.add_argument("--only", default="")
        parser.add_argument("--engine-dir", dest="engine_dir", default="")
        parser.add_argument("--font", default="")
        parser.add_argument("--voxel", type=float, default=0.005)
        parser.add_argument("--budget", type=int, default=0)
        parser.add_argument("--no-qa", dest="no_qa", action="store_true")
        parser.add_argument("--no-render", dest="no_render", action="store_true")
        parser.add_argument("--res", type=int, default=900)
        self.args = parser.parse_args(argv)

    def run(self):
        loader = EngineLoader(self.args.engine_dir or None)
        engine = loader.module()
        recipes = SignsRecipes(loader.font(self.args.font or None))
        out_dir = os.path.abspath(self.args.out)
        os.makedirs(out_dir, exist_ok=True)
        demo = DemoSet(engine, recipes, out_dir, voxel=self.args.voxel)
        only = [s.strip() for s in self.args.only.split(",") if s.strip()]
        report = {"out": out_dir, "blender": bpy.app.version_string, "props": [], "font": recipes.glyphs.font}
        built = []
        for spec in DemoSet.props:
            if only and spec["id"] not in only:
                continue
            result = demo.build(spec, self.args.budget or None)
            metrics = result["metrics"]
            entry = {"id": spec["id"], "recipe": spec["recipe"], "tris": metrics["tris"], "budget": result["budget"], "surface_m2": metrics["surface_m2"], "tris_per_m2": metrics["tris_per_m2"], "size_m": result["size_m"], "seconds": result["seconds"], "timings": result["timings"], "dihedral": metrics["dihedral_deg"], "folds": metrics["folds"], "warnings": result["warnings"], "art_slots": result["art_slots"], "part_tris": result["part_tris"], "blend": result["blend"]}
            report["props"].append(entry)
            built.append(spec["id"])
            print("SIGNS_PROP " + json.dumps({k: entry[k] for k in ("id", "tris", "budget", "surface_m2", "tris_per_m2", "seconds", "size_m")}), flush=True)
            print("SIGNS_PARTS {} {}".format(spec["id"], json.dumps(entry["part_tris"])), flush=True)
        if not self.args.no_qa and built:
            runner = QARunner(loader, out_dir)
            results = [runner.sculpt_qa(prop_id) for prop_id in built]
            for item in results:
                print("SIGNS_QA {} {}".format(item["id"], item["line"]), flush=True)
            qa_json, merged = runner.merge(results)
            report["sculpt_qa"] = results
            prop = runner.prop_qa()
            report["validate_prop"] = prop
            print("PROP_QA {}".format(prop["line"]), flush=True)
            if not self.args.no_render:
                report["render"] = runner.render(qa_json, self.args.res)
                print("SIGNS_RENDER {}".format(report["render"]["line"]), flush=True)
            print("SCULPT_QA fail={} warn={}".format(merged["fail"], merged["warn"]), flush=True)
        path = os.path.join(out_dir, "signs_report.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        print("SIGNS_DONE props={} report={}".format(len(built), path), flush=True)
        return report


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    report = DemoCli(argv).run()
    if bpy.app.background:
        sys.stdout.flush()
        failed = any(item.get("fail", 0) != 0 for item in report.get("sculpt_qa", []))
        os._exit(1 if failed else 0)
    return report


if __name__ == "__main__":
    main()
