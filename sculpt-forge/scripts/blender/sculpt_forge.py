import hashlib
import importlib
import json
import math
import os
import random
import sys
import time
from contextlib import contextmanager

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.kdtree import KDTree


class SdfMath:
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
    def combine(acc_d, acc_o, d, o, op, k):
        if op == "union":
            return SdfMath.smin(acc_d, d, k), np.where(d < acc_d, o, acc_o)
        if op == "subtract":
            return SdfMath.smax(acc_d, -d, k), np.where((-d > acc_d) & (np.asarray(o) >= 0), o, acc_o)
        return SdfMath.smax(acc_d, d, k), np.where((d > acc_d) & (np.asarray(o) >= 0), o, acc_o)

    @staticmethod
    def norm(q):
        return np.sqrt(np.einsum("ij,ij->i", q, q))

    @staticmethod
    def rotation(rot):
        return np.array(Euler([math.radians(float(a)) for a in rot], "XYZ").to_matrix(), dtype=np.float32)

    @staticmethod
    def plane_rotation(plane):
        if plane == "XZ":
            return SdfMath.rotation((90.0, 0.0, 0.0))
        if plane == "YZ":
            return SdfMath.rotation((90.0, 0.0, -90.0))
        return np.eye(3, dtype=np.float32)

    @staticmethod
    def frame(plane, rot):
        return SdfMath.rotation(rot) @ SdfMath.plane_rotation(plane)


class SdfPrimitives:
    @staticmethod
    def sphere(p, radius):
        return SdfMath.norm(p) - radius

    @staticmethod
    def ellipsoid(p, radii):
        r = np.asarray(radii, np.float32)
        k0 = SdfMath.norm(p / r)
        k1 = SdfMath.norm(p / (r * r))
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

    @staticmethod
    def capsule(p, a, b, radius):
        a = np.asarray(a, np.float32)
        b = np.asarray(b, np.float32)
        pa = p - a
        ba = b - a
        h = np.clip((pa @ ba) / max(float(ba @ ba), 1e-12), 0.0, 1.0)
        return SdfMath.norm(pa - h[:, None] * ba) - radius

    @staticmethod
    def round_cone(p, a, b, radius_a, radius_b):
        a = np.asarray(a, np.float32)
        b = np.asarray(b, np.float32)
        ba = b - a
        l2 = float(ba @ ba)
        rr = float(radius_a - radius_b)
        a2 = l2 - rr * rr
        if l2 < 1e-12 or a2 <= 1e-12:
            if radius_a >= radius_b:
                return SdfMath.norm(p - a) - radius_a
            return SdfMath.norm(p - b) - radius_b
        il2 = 1.0 / l2
        pa = p - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - y[:, None] * ba
        x2 = np.einsum("ij,ij->i", xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = math.copysign(1.0, rr) * rr * rr * x2
        res = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - radius_a
        res = np.where(np.sign(y) * a2 * y2 < k, np.sqrt(x2 + y2) * il2 - radius_a, res)
        return np.where(np.sign(z) * a2 * z2 > k, np.sqrt(x2 + z2) * il2 - radius_b, res)

    @staticmethod
    def round_box(p, size, radius):
        b = np.asarray(size, np.float32) * 0.5
        r = float(min(max(radius, 0.0), float(b.min()) - 1e-4))
        q = np.abs(p) - (b - r)
        return SdfMath.norm(np.maximum(q, 0.0)) + np.minimum(q.max(axis=1), 0.0) - r

    @staticmethod
    def pillow_box(p, size, radius, puff):
        b = np.asarray(size, np.float32) * 0.5
        r = float(min(max(radius, 0.0), float(b.min()) - 1e-4))
        inner = np.maximum(b - r, 1e-5)
        t = np.minimum((p / inner) ** 2, 1.0)
        f = (1.0 - t) ** 2
        bulge = np.asarray(puff, np.float32) * np.ones(3, np.float32)
        h = np.empty_like(p)
        h[:, 0] = inner[0] + bulge[0] * f[:, 1] * f[:, 2]
        h[:, 1] = inner[1] + bulge[1] * f[:, 0] * f[:, 2]
        h[:, 2] = inner[2] + bulge[2] * f[:, 0] * f[:, 1]
        q = np.abs(p) - h
        return SdfMath.norm(np.maximum(q, 0.0)) + np.minimum(q.max(axis=1), 0.0) - r

    @staticmethod
    def round_cyl(p, radius, height, edge):
        e = float(min(max(edge, 0.0), radius - 1e-4, height * 0.5 - 1e-4))
        d0 = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - radius + e
        d1 = np.abs(p[:, 2]) - height * 0.5 + e
        return np.minimum(np.maximum(d0, d1), 0.0) + np.sqrt(np.maximum(d0, 0.0) ** 2 + np.maximum(d1, 0.0) ** 2) - e

    @staticmethod
    def torus(p, major, minor):
        q = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2) - major
        return np.sqrt(q * q + p[:, 2] ** 2) - minor

    @staticmethod
    def lathe(p, raster):
        rho = np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2)
        return raster.sample(np.stack([rho, p[:, 2]], axis=1))

    @staticmethod
    def extrude(p, raster, depth, rounding, puff, puff_width, back_puff):
        d2 = raster.sample(p[:, :2])
        r = float(rounding)
        dome = 0.0
        if puff > 0.0:
            t = np.clip((-d2 - r) / max(puff_width, 1e-4), 0.0, 1.0)
            dome = puff * t * t * (3.0 - 2.0 * t)
            if not back_puff:
                dome = np.where(p[:, 2] > 0.0, dome, 0.0)
        wx = d2 + r
        wy = np.abs(p[:, 2]) - (depth * 0.5 - r + dome)
        return np.minimum(np.maximum(wx, wy), 0.0) + np.sqrt(np.maximum(wx, 0.0) ** 2 + np.maximum(wy, 0.0) ** 2) - r


class Polygon2D:
    @staticmethod
    def signed_distance(points, loops):
        pts = np.asarray(points, np.float64)
        best = np.full(len(pts), np.inf)
        inside = np.zeros(len(pts), bool)
        for start in range(0, len(pts), 32768):
            px = pts[start:start + 32768, 0][:, None]
            py = pts[start:start + 32768, 1][:, None]
            block_best = np.full(len(px), np.inf)
            crossings = np.zeros(len(px), np.int64)
            for loop in loops:
                ring = np.asarray(loop, np.float64)
                nxt = np.roll(ring, -1, axis=0)
                for e0 in range(0, len(ring), 64):
                    ax = ring[e0:e0 + 64, 0][None, :]
                    ay = ring[e0:e0 + 64, 1][None, :]
                    ex = nxt[e0:e0 + 64, 0][None, :] - ax
                    ey = nxt[e0:e0 + 64, 1][None, :] - ay
                    wx = px - ax
                    wy = py - ay
                    ee = np.maximum(ex * ex + ey * ey, 1e-18)
                    h = np.clip((wx * ex + wy * ey) / ee, 0.0, 1.0)
                    dx = wx - ex * h
                    dy = wy - ey * h
                    block_best = np.minimum(block_best, (dx * dx + dy * dy).min(axis=1))
                    by = ay + ey
                    straddle = (ay > py) != (by > py)
                    safe = np.where(np.abs(ey) < 1e-18, 1e-18, ey)
                    xint = ax + (py - ay) * ex / safe
                    crossings += (straddle & (px < xint)).sum(axis=1)
            best[start:start + 32768] = block_best
            inside[start:start + 32768] = (crossings % 2) == 1
        d = np.sqrt(best)
        return np.where(inside, -d, d)

    @staticmethod
    def chaikin(points, iterations, closed):
        pts = np.asarray(points, np.float64)
        for _ in range(int(iterations)):
            if closed:
                nxt = np.roll(pts, -1, axis=0)
                out = np.empty((len(pts) * 2, pts.shape[1]))
                out[0::2] = 0.75 * pts + 0.25 * nxt
                out[1::2] = 0.25 * pts + 0.75 * nxt
                pts = out
            else:
                a = pts[:-1]
                b = pts[1:]
                mid = np.empty((len(a) * 2, pts.shape[1]))
                mid[0::2] = 0.75 * a + 0.25 * b
                mid[1::2] = 0.25 * a + 0.75 * b
                pts = np.vstack([pts[:1], mid, pts[-1:]])
        return pts

    @staticmethod
    def signed_area(points):
        pts = np.asarray(points, np.float64)
        nxt = np.roll(pts, -1, axis=0)
        return 0.5 * float(np.sum(pts[:, 0] * nxt[:, 1] - nxt[:, 0] * pts[:, 1]))


class Raster2D:
    def __init__(self, loops, step, margin):
        allp = np.vstack([np.asarray(l, np.float64) for l in loops])
        self.lo = allp.min(axis=0) - margin
        hi = allp.max(axis=0) + margin
        self.step = float(step)
        self.count = (np.ceil((hi - self.lo) / self.step).astype(np.int64) + 1)
        self.hi = self.lo + (self.count - 1) * self.step
        us = self.lo[0] + np.arange(self.count[0]) * self.step
        vs = self.lo[1] + np.arange(self.count[1]) * self.step
        grid = np.stack(np.meshgrid(us, vs, indexing="ij"), axis=-1).reshape(-1, 2)
        self.values = Polygon2D.signed_distance(grid, loops).reshape(int(self.count[0]), int(self.count[1])).astype(np.float32)

    def sample(self, uv):
        uv = np.asarray(uv, np.float32)
        f = (uv - self.lo.astype(np.float32)) / self.step
        top = (self.count - 1).astype(np.float32) - 1e-3
        fc = np.clip(f, 0.0, top)
        i = np.floor(fc).astype(np.int64)
        t = fc - i
        v = self.values
        v00 = v[i[:, 0], i[:, 1]]
        v10 = v[i[:, 0] + 1, i[:, 1]]
        v01 = v[i[:, 0], i[:, 1] + 1]
        v11 = v[i[:, 0] + 1, i[:, 1] + 1]
        tx = t[:, 0]
        ty = t[:, 1]
        value = (v00 * (1 - tx) + v10 * tx) * (1 - ty) + (v01 * (1 - tx) + v11 * tx) * ty
        outside = uv - np.clip(uv, self.lo.astype(np.float32), self.hi.astype(np.float32))
        return value + np.sqrt((outside * outside).sum(axis=1))


class RasterSource:
    def __init__(self, loops):
        self.loops = [np.asarray(l, np.float64) for l in loops]
        self.raster = None
        self.key = None

    def build(self, step, margin):
        key = (round(float(step), 7), round(float(margin), 7))
        if self.raster is None or self.key != key:
            self.raster = Raster2D(self.loops, step, margin)
            self.key = key
        return self.raster

    def bounds(self):
        allp = np.vstack(self.loops)
        return allp.min(axis=0), allp.max(axis=0)


class Shapes:
    generators = ("rounded_rect", "scalloped_rect", "circle", "lobed_circle", "star", "heart", "squircle", "points")

    @staticmethod
    def segments_for_radius(radius, sagitta=0.002, minimum=8):
        if radius <= sagitta * 2.0:
            return minimum
        n = math.pi / math.acos(max(-1.0, 1.0 - sagitta / radius))
        return max(minimum, int(math.ceil(n / 4.0)) * 4)

    @staticmethod
    def rounded_rect(w, h, r, corner_segments=None):
        r = max(1e-4, min(float(r), w * 0.5 - 1e-4, h * 0.5 - 1e-4))
        quarter = int(corner_segments or max(3, Shapes.segments_for_radius(r) // 4))
        pts = []
        for cx, cy, a0 in ((w * 0.5 - r, -h * 0.5 + r, -90.0), (w * 0.5 - r, h * 0.5 - r, 0.0), (-w * 0.5 + r, h * 0.5 - r, 90.0), (-w * 0.5 + r, -h * 0.5 + r, 180.0)):
            for i in range(quarter + 1):
                a = math.radians(a0 + 90.0 * i / quarter)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return np.array(pts)

    @staticmethod
    def resample_closed(points, count):
        pts = np.asarray(points, np.float64)
        ring = np.vstack([pts, pts[:1]])
        seg = np.linalg.norm(np.diff(ring, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        s = np.linspace(0.0, cum[-1], int(count), endpoint=False)
        out = np.stack([np.interp(s, cum, ring[:, k]) for k in range(pts.shape[1])], axis=1)
        return out, float(cum[-1])

    @staticmethod
    def outward_normals(points):
        pts = np.asarray(points, np.float64)
        t = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
        n = np.stack([t[:, 1], -t[:, 0]], axis=1)
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    @staticmethod
    def ccw(points):
        pts = np.asarray(points, np.float64)
        return pts[::-1].copy() if Polygon2D.signed_area(pts) < 0 else pts

    @staticmethod
    def scalloped_rect(w, h, r, lobes_per_m=8.0, amp=0.03, lobes=None, samples=12):
        base = Shapes.rounded_rect(w, h, r, corner_segments=16)
        dense, perimeter = Shapes.resample_closed(base, 2048)
        n_lobes = int(lobes or max(3, int(round(perimeter * float(lobes_per_m)))))
        pts, _ = Shapes.resample_closed(dense, n_lobes * int(samples))
        normals = Shapes.outward_normals(pts)
        u = (np.arange(len(pts)) / float(samples)) % 1.0
        bump = float(amp) * np.sqrt(np.clip(np.sin(np.pi * u), 0.0, 1.0))
        return pts + normals * bump[:, None]

    @staticmethod
    def circle(r, segments=None):
        n = int(segments or Shapes.segments_for_radius(r))
        a = np.linspace(0.0, math.tau, n, endpoint=False)
        return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)

    @staticmethod
    def lobed_circle(r, lobes=8, amp=0.03, samples=12):
        n = int(lobes) * int(samples)
        a = np.linspace(0.0, math.tau, n, endpoint=False)
        rad = r + float(amp) * np.sqrt(np.abs(np.sin(a * lobes * 0.5)))
        return np.stack([rad * np.cos(a), rad * np.sin(a)], axis=1)

    @staticmethod
    def star(r_out, r_in, points=5, smooth=3, rotation=90.0):
        n = int(points) * 2
        a = np.radians(float(rotation)) + np.arange(n) * math.pi / int(points)
        rad = np.where(np.arange(n) % 2 == 0, float(r_out), float(r_in))
        pts = np.stack([rad * np.cos(a), rad * np.sin(a)], axis=1)
        return Polygon2D.chaikin(pts, int(smooth), True)

    @staticmethod
    def heart(size, smooth=1, samples=96):
        t = np.linspace(0.0, math.tau, int(samples), endpoint=False)
        x = 16.0 * np.sin(t) ** 3
        y = 13.0 * np.cos(t) - 5.0 * np.cos(2 * t) - 2.0 * np.cos(3 * t) - np.cos(4 * t)
        pts = np.stack([x, y], axis=1)
        pts -= (pts.min(axis=0) + pts.max(axis=0)) * 0.5
        pts *= float(size) / float(pts[:, 1].max() - pts[:, 1].min())
        return Shapes.ccw(Polygon2D.chaikin(pts, int(smooth), True))

    @staticmethod
    def squircle(w, h, exponent=4.0, top_lobes=0, amp=0.0, samples=128):
        a = np.linspace(0.0, math.tau, int(samples), endpoint=False)
        c = np.cos(a)
        s = np.sin(a)
        e = 2.0 / float(exponent)
        x = np.sign(c) * np.abs(c) ** e * w * 0.5
        y = np.sign(s) * np.abs(s) ** e * h * 0.5
        if top_lobes and amp:
            weight = np.clip((s - 0.25) / 0.35, 0.0, 1.0)
            scale = 1.0 + float(amp) * weight * np.abs(np.sin(a * top_lobes))
            x = x * scale
            y = y * scale
        return np.stack([x, y], axis=1)

    @staticmethod
    def offset(points, dist):
        pts = Shapes.ccw(points)
        return pts + Shapes.outward_normals(pts) * float(dist)

    @staticmethod
    def embed(points2d, plane="XY", at=(0.0, 0.0, 0.0)):
        pts = np.asarray(points2d, np.float64)
        o = np.asarray(at, np.float64)
        out = np.tile(o, (len(pts), 1))
        if plane == "XZ":
            out[:, 0] += pts[:, 0]
            out[:, 2] += pts[:, 1]
        elif plane == "YZ":
            out[:, 1] += pts[:, 0]
            out[:, 2] += pts[:, 1]
        else:
            out[:, 0] += pts[:, 0]
            out[:, 1] += pts[:, 1]
        return out

    @staticmethod
    def resolve2d(spec):
        if isinstance(spec, dict):
            kind = spec.get("shape", "points")
            if kind not in Shapes.generators:
                raise ValueError("unknown outline shape {}".format(kind))
            if kind == "points":
                pts = np.asarray(spec["points"], np.float64)
            else:
                args = {k: v for k, v in spec.items() if k not in ("shape", "plane", "at", "offset", "smooth", "closed", "holes")}
                pts = np.asarray(getattr(Shapes, kind)(**args), np.float64)
            if spec.get("smooth"):
                pts = Polygon2D.chaikin(pts, int(spec["smooth"]), True)
            if spec.get("offset"):
                pts = Shapes.offset(pts, float(spec["offset"]))
            return pts
        return np.asarray(spec, np.float64)

    @staticmethod
    def resolve3d(spec, closed=None):
        if isinstance(spec, dict):
            pts = Shapes.embed(Shapes.resolve2d(spec), spec.get("plane", "XY"), spec.get("at", (0.0, 0.0, 0.0)))
            return pts, (True if closed is None and spec.get("closed") is None else bool(spec.get("closed", closed)))
        pts = np.asarray(spec, np.float64)
        if pts.shape[1] == 2:
            pts = Shapes.embed(pts)
        return pts, bool(closed)


class CatmullRom:
    @staticmethod
    def sample(points, closed, step, alpha=0.5):
        pts = np.asarray(points, np.float64)
        n = len(pts)
        if n < 2:
            return pts.copy(), np.zeros(n)
        if closed:
            ext = np.vstack([pts[-1:], pts, pts[:2]])
            segments = n
        else:
            ext = np.vstack([2.0 * pts[0] - pts[1], pts, 2.0 * pts[-1] - pts[-2]])
            segments = n - 1
        out = []
        par = []
        for i in range(segments):
            p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
            t1 = max(float(np.linalg.norm(p1 - p0)) ** alpha, 1e-6)
            t2 = t1 + max(float(np.linalg.norm(p2 - p1)) ** alpha, 1e-6)
            t3 = t2 + max(float(np.linalg.norm(p3 - p2)) ** alpha, 1e-6)
            m = max(1, int(math.ceil(float(np.linalg.norm(p2 - p1)) / max(step, 1e-4))))
            u = np.arange(m) / float(m)
            t = (t1 + (t2 - t1) * u)[:, None]
            a1 = (t1 - t) / t1 * p0 + t / t1 * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / t2 * a1 + t / t2 * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
            par.append(i + u)
        if not closed:
            out.append(pts[-1:])
            par.append(np.array([n - 1.0]))
        return np.vstack(out), np.concatenate(par)

    @staticmethod
    def along(values, param, count, closed):
        vals = np.asarray(values, np.float64).reshape(-1)
        if len(vals) == 1:
            return np.full(len(param), float(vals[0]))
        if closed:
            return np.interp(param, np.arange(len(vals) + 1), np.concatenate([vals, vals[:1]]))
        return np.interp(param, np.linspace(0.0, count - 1.0, len(vals)), vals)

    @staticmethod
    def arc_frames(samples, closed):
        ring = np.vstack([samples, samples[:1]]) if closed else samples
        seg = np.linalg.norm(np.diff(ring, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        return ring, cum

    @staticmethod
    def point_at(ring, cum, s):
        return np.array([np.interp(s, cum, ring[:, k]) for k in range(ring.shape[1])], np.float64)

    @staticmethod
    def tangent_at(ring, cum, s, closed):
        total = float(cum[-1])
        h = max(1e-4, 0.002 * total)
        if closed:
            a = CatmullRom.point_at(ring, cum, (s - h) % total)
            b = CatmullRom.point_at(ring, cum, (s + h) % total)
        else:
            a = CatmullRom.point_at(ring, cum, max(0.0, s - h))
            b = CatmullRom.point_at(ring, cum, min(total, s + h))
        t = b - a
        return t / max(float(np.linalg.norm(t)), 1e-12)


class GridDomain:
    def __init__(self, ijk0, shape, voxel):
        self.ijk0 = np.asarray(ijk0, np.int64)
        self.shape = tuple(int(v) for v in shape)
        self.voxel = float(voxel)

    def full(self, value, dtype):
        return np.full(self.shape, value, dtype=dtype)

    def points(self):
        nx, ny, nz = self.shape
        pts = np.empty((nx, ny, nz, 3), np.float32)
        pts[..., 0] = ((np.arange(nx) + self.ijk0[0]) * self.voxel).astype(np.float32)[:, None, None]
        pts[..., 1] = ((np.arange(ny) + self.ijk0[1]) * self.voxel).astype(np.float32)[None, :, None]
        pts[..., 2] = ((np.arange(nz) + self.ijk0[2]) * self.voxel).astype(np.float32)[None, None, :]
        return pts.reshape(-1, 3)

    def reshape(self, values):
        return values.reshape(self.shape)

    def sub(self, region):
        if region is None:
            return self, (slice(None), slice(None), slice(None))
        lo, hi = region
        a = np.maximum(np.ceil(np.asarray(lo, np.float64) / self.voxel - 1e-6).astype(np.int64), self.ijk0)
        b = np.minimum(np.floor(np.asarray(hi, np.float64) / self.voxel + 1e-6).astype(np.int64), self.ijk0 + np.asarray(self.shape) - 1)
        if np.any(b < a):
            return None, None
        rel = tuple(slice(int(a[k] - self.ijk0[k]), int(b[k] - self.ijk0[k] + 1)) for k in range(3))
        return GridDomain(a, b - a + 1, self.voxel), rel


class PointDomain:
    def __init__(self, points):
        self.pts = np.ascontiguousarray(points, np.float32).reshape(-1, 3)
        self.shape = (len(self.pts),)

    def full(self, value, dtype):
        return np.full(self.shape, value, dtype=dtype)

    def points(self):
        return self.pts

    def reshape(self, values):
        return values.reshape(self.shape)

    def sub(self, region):
        if region is None:
            return self, slice(None)
        lo, hi = region
        mask = np.all((self.pts >= np.asarray(lo, np.float32)) & (self.pts <= np.asarray(hi, np.float32)), axis=1)
        idx = np.nonzero(mask)[0]
        if idx.size == 0:
            return None, None
        return PointDomain(self.pts[idx]), idx


class SdfNode:
    def __init__(self, owner, op, fillet):
        self.owner = int(owner)
        self.op = str(op)
        self.fillet = float(fillet)
        self.is_group = False

    def region(self, band):
        bounds = self.world_bounds()
        if bounds is None:
            return None
        pad = band + self.fillet
        return bounds[0] - pad, bounds[1] + pad

    def prepare(self, voxel, band):
        return None

    def max_fillet(self):
        return self.fillet


class PrimitiveNode(SdfNode):
    world_kinds = ("capsule", "round_cone")

    def __init__(self, owner, op, fillet, kind, params, extent, loc=(0.0, 0.0, 0.0), rot=None, raster_source=None):
        super().__init__(owner, op, fillet)
        self.kind = kind
        self.params = dict(params)
        self.extent = (np.asarray(extent[0], np.float32), np.asarray(extent[1], np.float32))
        self.loc = np.asarray(loc, np.float32)
        self.rot = np.eye(3, dtype=np.float32) if rot is None else np.asarray(rot, np.float32)
        self.raster_source = raster_source

    def world_bounds(self):
        lo, hi = self.extent
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], np.float32)
        world = corners @ self.rot.T + self.loc
        return world.min(axis=0), world.max(axis=0)

    def prepare(self, voxel, band):
        if self.raster_source is not None:
            self.params["raster"] = self.raster_source.build(voxel * 0.5, band + self.fillet + voxel * 2.0)

    def distance(self, domain, band):
        local = (domain.points() - self.loc) @ self.rot
        d = getattr(SdfPrimitives, self.kind)(local, **self.params)
        return domain.reshape(np.clip(d, -band, band).astype(np.float32, copy=False))

    def mirrored(self):
        flip = np.diag(np.array([-1.0, 1.0, 1.0], np.float32))
        if self.kind in self.world_kinds:
            params = dict(self.params)
            params["a"] = flip @ np.asarray(params["a"], np.float32)
            params["b"] = flip @ np.asarray(params["b"], np.float32)
            lo, hi = self.extent
            ext = (np.minimum(flip @ lo, flip @ hi), np.maximum(flip @ lo, flip @ hi))
            return PrimitiveNode(self.owner, "union", 0.0, self.kind, params, ext)
        return PrimitiveNode(self.owner, "union", 0.0, self.kind, self.params, self.extent, flip @ self.loc, flip @ self.rot, self.raster_source)


class ChainNode(SdfNode):
    def __init__(self, owner, op, fillet, elements, blend=0.0):
        super().__init__(owner, op, fillet)
        self.elements = elements
        self.blend = float(blend)

    def world_bounds(self):
        return np.min([e["lo"] for e in self.elements], axis=0), np.max([e["hi"] for e in self.elements], axis=0)

    def distance(self, domain, band):
        out = domain.full(band, np.float32)
        for start in range(0, len(self.elements), 8):
            chunk = self.elements[start:start + 8]
            lo = np.min([e["lo"] for e in chunk], axis=0) - band - self.blend
            hi = np.max([e["hi"] for e in chunk], axis=0) + band + self.blend
            sub, rel = domain.sub((lo, hi))
            if sub is None:
                continue
            pts = sub.points()
            d = None
            for e in chunk:
                de = ChainNode.element_distance(e, pts)
                d = de if d is None else SdfMath.smin(d, de, self.blend)
            out[rel] = SdfMath.smin(out[rel], sub.reshape(np.clip(d, -band, band).astype(np.float32)), self.blend)
        return out

    @staticmethod
    def element_distance(e, pts):
        if e["kind"] == "cone":
            if abs(e["ra"] - e["rb"]) < 1e-6:
                return SdfPrimitives.capsule(pts, e["a"], e["b"], e["ra"])
            return SdfPrimitives.round_cone(pts, e["a"], e["b"], e["ra"], e["rb"])
        if e["kind"] == "sphere":
            return SdfPrimitives.sphere(pts - e["c"], e["r"])
        if e["kind"] == "lobe":
            local = (pts - e["c"]) @ e["rot"]
            radii = np.empty_like(local)
            radii[:, 0] = e["radii"][0]
            radii[:, 1] = e["radii"][1]
            radii[:, 2] = np.where(local[:, 2] > 0.0, e["up"], e["radii"][2])
            k0 = SdfMath.norm(local / radii)
            k1 = SdfMath.norm(local / (radii * radii))
            return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        top = e["top"]
        length = e["length"]
        r = e["r"]
        rb = 0.95 * r
        bulb = top - np.array([0.0, 0.0, length - rb], np.float32)
        neck = top - np.array([0.0, 0.0, 0.75 * (length - rb)], np.float32)
        d1 = SdfPrimitives.round_cone(pts, top, neck, r, 0.62 * r)
        return SdfMath.smin(d1, SdfPrimitives.sphere(pts - bulb, rb), 0.6 * r)

    def mirrored(self):
        flip = np.array([-1.0, 1.0, 1.0], np.float32)
        twins = []
        for e in self.elements:
            t = dict(e)
            for key in ("a", "b", "c", "top"):
                if key in t:
                    t[key] = t[key] * flip
            if "rot" in t:
                t["rot"] = (np.diag(flip) @ t["rot"]).astype(np.float32)
            lo = e["lo"] * flip
            hi = e["hi"] * flip
            t["lo"] = np.minimum(lo, hi)
            t["hi"] = np.maximum(lo, hi)
            twins.append(t)
        return ChainNode(self.owner, "union", 0.0, twins, self.blend)


class LevelSetNode(SdfNode):
    def __init__(self, owner, op, fillet, points, tris, puff):
        super().__init__(owner, op, fillet)
        self.points = np.ascontiguousarray(points, np.float32)
        self.tris = np.ascontiguousarray(tris, np.int32)
        self.puff = float(puff)
        self.array = None
        self.origin = None
        self.background = 0.0
        self.voxel = 0.0

    def world_bounds(self):
        pad = max(self.puff, 0.0)
        return self.points.min(axis=0) - pad, self.points.max(axis=0) + pad

    def prepare(self, voxel, band):
        if self.array is not None and abs(self.voxel - voxel) < 1e-12:
            return
        vdb = VdbBridge.module()
        half = int(math.ceil((band + abs(self.puff)) / voxel)) + 3
        grid = VdbBridge.level_set(vdb, self.points, self.tris, voxel, half)
        box = grid.evalActiveVoxelBoundingBox()
        i0 = np.array(box[0], np.int64)
        i1 = np.array(box[1], np.int64)
        background = float(half * voxel)
        arr = np.full(tuple(int(v) for v in (i1 - i0 + 1)), background, np.float32)
        grid.copyToArray(arr, ijk=tuple(int(v) for v in i0))
        self.array = arr
        self.origin = i0
        self.background = background
        self.voxel = float(voxel)

    def distance(self, domain, band):
        if isinstance(domain, GridDomain) and abs(domain.voxel - self.voxel) < 1e-12:
            values = self.lookup(domain)
        else:
            values = domain.reshape(self.sample(domain.points()))
        return np.clip(values - self.puff, -band, band).astype(np.float32)

    def lookup(self, domain):
        idx = []
        ok = []
        for axis in range(3):
            raw = domain.ijk0[axis] + np.arange(domain.shape[axis]) - self.origin[axis]
            ok.append((raw >= 0) & (raw < self.array.shape[axis]))
            idx.append(np.clip(raw, 0, self.array.shape[axis] - 1))
        values = self.array[np.ix_(idx[0], idx[1], idx[2])]
        mask = ok[0][:, None, None] & ok[1][None, :, None] & ok[2][None, None, :]
        return np.where(mask, values, self.background)

    def sample(self, pts):
        f = pts / self.voxel - self.origin.astype(np.float32)
        top = np.array(self.array.shape, np.float32) - 1.0
        inside = np.all((f >= 0.0) & (f <= top), axis=1)
        fc = np.clip(f, 0.0, top - 1e-3)
        i = np.floor(fc).astype(np.int64)
        t = (fc - i).astype(np.float32)
        a = self.array
        x0, y0, z0 = i[:, 0], i[:, 1], i[:, 2]
        x1 = np.minimum(x0 + 1, a.shape[0] - 1)
        y1 = np.minimum(y0 + 1, a.shape[1] - 1)
        z1 = np.minimum(z0 + 1, a.shape[2] - 1)
        tx, ty, tz = t[:, 0], t[:, 1], t[:, 2]
        c00 = a[x0, y0, z0] * (1 - tx) + a[x1, y0, z0] * tx
        c10 = a[x0, y1, z0] * (1 - tx) + a[x1, y1, z0] * tx
        c01 = a[x0, y0, z1] * (1 - tx) + a[x1, y0, z1] * tx
        c11 = a[x0, y1, z1] * (1 - tx) + a[x1, y1, z1] * tx
        value = (c00 * (1 - ty) + c10 * ty) * (1 - tz) + (c01 * (1 - ty) + c11 * ty) * tz
        return np.where(inside, value, self.background)

    def mirrored(self):
        pts = self.points.copy()
        pts[:, 0] *= -1.0
        return LevelSetNode(self.owner, "union", 0.0, pts, self.tris[:, ::-1].copy(), self.puff)


class HalfSpaceNode(SdfNode):
    def __init__(self, owner, op, fillet, point, normal):
        super().__init__(owner, op, fillet)
        n = np.asarray(normal, np.float32)
        self.normal = n / max(float(np.linalg.norm(n)), 1e-9)
        self.point = np.asarray(point, np.float32)

    def world_bounds(self):
        return None

    def distance(self, domain, band):
        d = (domain.points() - self.point) @ self.normal
        return domain.reshape(np.clip(d, -band, band).astype(np.float32))

    def mirrored(self):
        flip = np.array([-1.0, 1.0, 1.0], np.float32)
        return HalfSpaceNode(self.owner, "union", 0.0, self.point * flip, self.normal * flip)


class GroupNode(SdfNode):
    def __init__(self, name, op, fillet):
        super().__init__(-1, op, fillet)
        self.name = str(name)
        self.children = []
        self.is_group = True

    def world_bounds(self):
        boxes = [c.world_bounds() for c in self.children if c.op == "union"]
        boxes = [b for b in boxes if b is not None]
        if not boxes:
            return None
        return np.min([b[0] for b in boxes], axis=0), np.max([b[1] for b in boxes], axis=0)

    def prepare(self, voxel, band):
        for child in self.children:
            child.prepare(voxel, band)

    def max_fillet(self):
        return max([self.fillet] + [c.max_fillet() for c in self.children])

    def leaves(self):
        out = []
        for child in self.children:
            out.extend(child.leaves() if child.is_group else [child])
        return out


class FieldEvaluator:
    def __init__(self, root, band):
        self.root = root
        self.band = float(band)

    def evaluate(self, domain):
        return self.group_field(self.root, domain)

    def group_field(self, group, domain):
        band = self.band
        acc_d = domain.full(band, np.float32)
        acc_o = domain.full(-1, np.int32)
        for child in group.children:
            sub, rel = domain.sub(child.region(band))
            if sub is None:
                if child.op == "intersect":
                    acc_d.fill(band)
                    acc_o.fill(-1)
                continue
            if child.is_group:
                d, o = self.group_field(child, sub)
            else:
                d = child.distance(sub, band)
                o = child.owner
            nd, no = SdfMath.combine(acc_d[rel], acc_o[rel], d, o, child.op, child.fillet)
            if child.op == "intersect":
                acc_d.fill(band)
                acc_o.fill(-1)
            acc_d[rel] = np.clip(nd, -band, band)
            acc_o[rel] = no
        return acc_d, acc_o

    def distances(self, points):
        return self.evaluate(PointDomain(points))[0]

    def owners(self, points):
        return self.evaluate(PointDomain(points))[1]

    def gradient(self, points, h):
        pts = np.asarray(points, np.float32)
        g = np.zeros_like(pts)
        for axis in range(3):
            step = np.zeros(3, np.float32)
            step[axis] = h
            g[:, axis] = (self.distances(pts + step) - self.distances(pts - step)) / (2.0 * h)
        return g

    def normals(self, points, h):
        g = self.gradient(points, h)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)

    def project(self, points, h, steps=2, limit=None):
        pts = np.asarray(points, np.float32).copy()
        reach = float(limit if limit is not None else 6.0 * h)
        for _ in range(int(steps)):
            d = self.distances(pts)
            g = self.gradient(pts, h)
            length = np.linalg.norm(g, axis=1)
            ok = length > 0.35
            move = np.clip(d, -reach, reach) / np.maximum(length, 1e-6)
            pts[ok] -= (move[ok] / np.maximum(length[ok], 1e-6))[:, None] * g[ok]
        return pts


class VdbBridge:
    @staticmethod
    def module():
        for name in ("pyopenvdb", "openvdb"):
            try:
                return importlib.import_module(name)
            except ImportError:
                continue
        raise RuntimeError("this Blender build has no OpenVDB python module (pyopenvdb or openvdb)")

    @staticmethod
    def float_grid(vdb, background, voxel):
        try:
            grid = vdb.FloatGrid(background=float(background))
        except TypeError:
            grid = vdb.FloatGrid(float(background))
        grid.transform = vdb.createLinearTransform(voxelSize=float(voxel))
        try:
            grid.gridClass = vdb.GridClass.LEVEL_SET
        except (AttributeError, TypeError):
            pass
        return grid

    @staticmethod
    def level_set(vdb, points, tris, voxel, half_width):
        xf = vdb.createLinearTransform(voxelSize=float(voxel))
        try:
            return vdb.FloatGrid.createLevelSetFromPolygons(np.ascontiguousarray(points, np.float32), triangles=np.ascontiguousarray(tris, np.int32), transform=xf, halfWidth=float(half_width))
        except TypeError:
            return vdb.FloatGrid.createLevelSetFromPolygons(np.ascontiguousarray(points, np.float32), triangles=np.ascontiguousarray(tris, np.uint32), transform=xf, halfWidth=float(half_width))


class MeshArrays:
    @staticmethod
    def vertices(me):
        a = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", a)
        return a.reshape(-1, 3)

    @staticmethod
    def set_vertices(me, verts):
        me.vertices.foreach_set("co", np.ascontiguousarray(verts, np.float32).reshape(-1))
        me.update()

    @staticmethod
    def build(name, verts, faces, sizes):
        me = bpy.data.meshes.new(name)
        loops = faces[faces >= 0].astype(np.int32)
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", np.ascontiguousarray(verts, np.float32).reshape(-1))
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(sizes))
        me.polygons.foreach_set("loop_start", starts)
        try:
            me.polygons.foreach_set("loop_total", np.ascontiguousarray(sizes, np.int32))
        except (AttributeError, TypeError, RuntimeError):
            pass
        me.update(calc_edges=True)
        me.validate(clean_customdata=False)
        return me

    @staticmethod
    def faces(me):
        n = len(me.polygons)
        sizes = np.empty(n, np.int32)
        me.polygons.foreach_get("loop_total", sizes)
        starts = np.empty(n, np.int32)
        me.polygons.foreach_get("loop_start", starts)
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        width = int(sizes.max()) if n else 3
        out = np.full((n, max(width, 3)), -1, np.int64)
        for k in range(out.shape[1]):
            valid = sizes > k
            out[valid, k] = lv[starts[valid] + k]
        return out, sizes

    @staticmethod
    def polygon_vectors(me, attr):
        a = np.empty(len(me.polygons) * 3, np.float32)
        me.polygons.foreach_get(attr, a)
        return a.reshape(-1, 3)

    @staticmethod
    def polygon_ints(me, attr):
        a = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get(attr, a)
        return a

    @staticmethod
    def corner_normals(me):
        a = np.empty(len(me.loops) * 3, np.float32)
        me.corner_normals.foreach_get("vector", a)
        return a.reshape(-1, 3)

    @staticmethod
    def loop_vertex(me):
        a = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", a)
        return a

    @staticmethod
    def loop_face(me):
        sizes = MeshArrays.polygon_ints(me, "loop_total")
        return np.repeat(np.arange(len(sizes), dtype=np.int64), sizes)

    @staticmethod
    def tris(me):
        return int(sum(len(p.vertices) - 2 for p in me.polygons))

    @staticmethod
    def half_edges(faces, sizes):
        rows = np.arange(len(sizes))
        fa = []
        sl = []
        va = []
        vb = []
        for s in range(faces.shape[1]):
            valid = sizes > s
            r = rows[valid]
            nxt = np.where(sizes[valid] > s + 1, s + 1, 0)
            fa.append(r)
            sl.append(np.full(len(r), s))
            va.append(faces[r, s])
            vb.append(faces[r, nxt])
        return np.concatenate(fa), np.concatenate(sl), np.concatenate(va), np.concatenate(vb)

    @staticmethod
    def face_pairs(faces, sizes, nverts):
        f, s, a, b = MeshArrays.half_edges(faces, sizes)
        key = np.minimum(a, b).astype(np.int64) * int(nverts) + np.maximum(a, b)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        same = np.nonzero(ks[:-1] == ks[1:])[0]
        h1 = order[same]
        h2 = order[same + 1]
        return f[h1], s[h1], f[h2], s[h2], a[h1], b[h1]

    @staticmethod
    def smooth_all(me):
        if hasattr(me, "shade_smooth"):
            me.shade_smooth()
        else:
            me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
        for name in ("sharp_edge", "sharp_face"):
            attribute = me.attributes.get(name)
            if attribute is not None:
                me.attributes.remove(attribute)
        me.update()

    @staticmethod
    def apply_modifiers(ob):
        deps = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
        old = ob.data
        name = old.name
        ob.modifiers.clear()
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        me.name = name
        return ob

    @staticmethod
    def triangulate(me):
        bm = bmesh.new()
        bm.from_mesh(me)
        big = [f for f in bm.faces if len(f.verts) > 3]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(me)
        bm.free()
        me.update()

    @staticmethod
    def edge_dihedral(me):
        fn = MeshArrays.polygon_vectors(me, "normal")
        faces, sizes = MeshArrays.faces(me)
        f1, _, f2, _, _, _ = MeshArrays.face_pairs(faces, sizes, len(me.vertices))
        dots = np.clip((fn[f1] * fn[f2]).sum(axis=1), -1.0, 1.0)
        return np.degrees(np.arccos(dots)), f1, f2

    @staticmethod
    def shells(me):
        n = len(me.vertices)
        if n == 0:
            return 0
        ev = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        labels = np.arange(n)
        for _ in range(256):
            m = np.minimum(labels[ev[:, 0]], labels[ev[:, 1]])
            new = labels.copy()
            np.minimum.at(new, ev[:, 0], m)
            np.minimum.at(new, ev[:, 1], m)
            new = new[new]
            if np.array_equal(new, labels):
                break
            labels = new
        used = np.zeros(n, bool)
        used[MeshArrays.loop_vertex(me)] = True
        return int(len(np.unique(labels[used])))


class RoleField:
    @staticmethod
    def neighbours(faces, sizes, nverts):
        f1, s1, f2, s2, _, _ = MeshArrays.face_pairs(faces, sizes, nverts)
        nb = np.full((len(sizes), faces.shape[1]), -1, np.int64)
        nb[f1, s1] = f2
        nb[f2, s2] = f1
        return nb

    @staticmethod
    def majority(roles, nb, iterations=3):
        roles = roles.copy()
        valid = nb >= 0
        rows = np.arange(len(roles))
        for _ in range(int(iterations)):
            rn = np.where(valid, roles[np.maximum(nb, 0)], -1)
            counts = np.zeros(nb.shape, np.int64)
            for j in range(nb.shape[1]):
                counts[:, j] = ((rn == rn[:, j:j + 1]) & valid).sum(axis=1)
            counts = np.where(valid, counts, -1)
            best_j = np.argmax(counts, axis=1)
            best_r = rn[rows, best_j]
            best_c = counts[rows, best_j]
            own_c = ((rn == roles[:, None]) & valid).sum(axis=1)
            switch = (best_r != roles) & (best_r >= 0) & ((best_c >= 3) | ((own_c == 0) & (best_c >= 2)))
            if not switch.any():
                break
            roles[switch] = best_r[switch]
        return roles

    @staticmethod
    def boundary_chain(faces, sizes, roles, nverts):
        f1, _, f2, _, va, vb = MeshArrays.face_pairs(faces, sizes, nverts)
        cut = roles[f1] != roles[f2]
        return va[cut], vb[cut]

    @staticmethod
    def smooth_boundaries(verts, faces, sizes, roles, evaluator, voxel, iterations=4, weight=0.5):
        va, vb = RoleField.boundary_chain(faces, sizes, roles, len(verts))
        if len(va) == 0:
            return verts, 0
        n = len(verts)
        count = np.bincount(np.concatenate([va, vb]), minlength=n)
        chain = np.nonzero(count == 2)[0]
        if len(chain) == 0:
            return verts, 0
        pts = verts.astype(np.float64).copy()
        for _ in range(int(iterations)):
            acc = np.zeros((n, 3))
            np.add.at(acc, va, pts[vb])
            np.add.at(acc, vb, pts[va])
            target = acc[chain] * 0.5
            moved = pts[chain] + weight * (target - pts[chain])
            pts[chain] = evaluator.project(moved.astype(np.float32), voxel * 0.5, 1)
        return pts.astype(np.float32), int(len(chain))


class SetPalette:
    finishes = {
        "matte": {"shader": "default_spec.sps", "spec": (0.06, 18.0, 0.22), "roughness": 0.72},
        "satin": {"shader": "default_spec.sps", "spec": (0.18, 40.0, 0.30), "roughness": 0.50},
        "gloss": {"shader": "default_spec.sps", "spec": (0.52, 96.0, 0.70), "roughness": 0.26},
        "emissive": {"shader": "emissive.sps", "mult": 1.5, "roughness": 0.50},
    }
    default_colors = ("#F4E6D4", "#E9A2B6", "#94D6C2", "#FFD772", "#97C6EE", "#6E4B3B", "#C9B3F0", "#F2BE52")

    def __init__(self, name, roles=None, cell_px=32):
        self.name = str(name)
        self.cell_px = int(cell_px)
        self.roles = {}
        self.path = None
        for role, spec in (roles or {}).items():
            if isinstance(spec, str):
                self.add(role, spec)
            else:
                self.add(role, spec.get("color", "#F4E6D4"), spec.get("finish", "satin"))

    @classmethod
    def from_spec(cls, name, spec):
        if isinstance(spec, SetPalette):
            return spec
        spec = spec or {}
        if "roles" in spec:
            return cls(spec.get("name", name), spec["roles"], spec.get("cell_px", 32))
        return cls(name, spec)

    def add(self, role, color=None, finish="satin"):
        if finish not in self.finishes:
            raise ValueError("unknown finish {} for role {}".format(finish, role))
        if color is None:
            color = self.default_colors[len(self.roles) % len(self.default_colors)]
        self.roles[str(role)] = {"color": str(color), "finish": str(finish)}
        self.path = None

    def ensure(self, role):
        if role not in self.roles:
            self.add(role)
            return False
        return True

    def grid(self):
        g = 2
        while g * g < max(1, len(self.roles)):
            g *= 2
        return g

    def index(self, role):
        return list(self.roles).index(role)

    def cell_box(self, role):
        g = self.grid()
        i = self.index(role)
        cx, cy = i % g, i // g
        return cx / g, cy / g, (cx + 1) / g, (cy + 1) / g

    @staticmethod
    def rgb(hex_value):
        h = hex_value.lstrip("#")
        return tuple(int(h[k:k + 2], 16) / 255.0 for k in (0, 2, 4))

    def save(self, out_dir):
        g = self.grid()
        size = g * self.cell_px
        px = np.ones((size, size, 4), np.float32)
        for role in self.roles:
            i = self.index(role)
            cx, cy = i % g, i // g
            px[cy * self.cell_px:(cy + 1) * self.cell_px, cx * self.cell_px:(cx + 1) * self.cell_px, :3] = self.rgb(self.roles[role]["color"])
        path = os.path.join(os.path.abspath(out_dir), self.name + "_pal.png")
        if os.path.isfile(path) and not SetPalette.same_pixels(path, px):
            digest = hashlib.sha1(json.dumps(self.roles, sort_keys=True).encode("utf-8")).hexdigest()[:8]
            path = os.path.join(os.path.abspath(out_dir), "{}_pal_{}.png".format(self.name, digest))
        img = bpy.data.images.new(self.name + "_pal_tmp", size, size, alpha=False)
        img.pixels.foreach_set(px.reshape(-1))
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
        self.path = path
        return path

    @staticmethod
    def same_pixels(path, px):
        img = bpy.data.images.load(path, check_existing=False)
        try:
            if tuple(img.size) != (px.shape[1], px.shape[0]):
                return False
            old = np.empty(px.size, np.float32)
            img.pixels.foreach_get(old)
            return bool(np.abs(old.reshape(px.shape)[..., :3] - px[..., :3]).max() < 2.0 / 255.0)
        finally:
            bpy.data.images.remove(img)

    def image(self, out_dir):
        if not self.path or not os.path.isfile(self.path) or os.path.dirname(self.path) != os.path.abspath(out_dir):
            self.save(out_dir)
        return bpy.data.images.load(self.path, check_existing=True)


class MaterialFactory:
    @staticmethod
    def role_material(name, hex_value, role):
        mat = bpy.data.materials.new(name)
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        srgb = SetPalette.rgb(hex_value)
        lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = lin + (1.0,)
        mat.diffuse_color = srgb + (1.0,)
        mat["sculpt_forge_role"] = role
        return mat

    @staticmethod
    def socket(node, name, kind):
        for s in node.inputs:
            if s.name == name and s.type == kind:
                return s
        return None

    @staticmethod
    def create(name, image, finish):
        info = SetPalette.finishes[finish]
        mat = bpy.data.materials.new(name)
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        tex.extension = "EXTEND"
        tex.location = (-700, 200)
        if finish == "emissive":
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 1.4
            mat["prop_forge_emissive_mult"] = float(info["mult"])
        else:
            vcol = nt.nodes.new("ShaderNodeVertexColor")
            vcol.layer_name = "Color 1"
            vcol.location = (-700, -80)
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.location = (-380, 120)
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(tex.outputs["Color"], MaterialFactory.socket(mix, "A", "RGBA"))
            nt.links.new(vcol.outputs["Color"], MaterialFactory.socket(mix, "B", "RGBA"))
            out = next(s for s in mix.outputs if s.type == "RGBA")
            nt.links.new(out, bsdf.inputs["Base Color"])
            spec = info["spec"]
            mat["prop_forge_spec_int"] = float(spec[0])
            mat["prop_forge_spec_falloff"] = float(spec[1])
            mat["prop_forge_spec_fresnel"] = float(spec[2])
        bsdf.inputs["Roughness"].default_value = float(info["roughness"])
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.3 if finish != "gloss" else 0.55
        mat["prop_forge_shader"] = info["shader"]
        mat["sculpt_forge_finish"] = finish
        return mat


class AmbientOcclusion:
    @staticmethod
    def occlusion(points, normals, evaluator, distance, floor_z, steps=5):
        occ = np.zeros(len(points), np.float64)
        total = 0.0
        for i in range(1, int(steps) + 1):
            h = distance * i / float(steps)
            probe = points + normals * h
            d = evaluator.distances(probe).astype(np.float64)
            d = np.minimum(d, probe[:, 2] - floor_z + 0.004)
            w = 1.0 / (2.0 ** (i - 1))
            occ += w * np.clip((h - d) / h, 0.0, 1.0)
            total += w
        return occ / total

    @staticmethod
    def write(me, occ, normals, points, emissive_faces, strength=1.0):
        occ = np.clip(occ * 1.35 * float(strength), 0.0, 1.0)
        zmin = float(points[:, 2].min())
        span = max(0.2, float(points[:, 2].max()) - zmin)
        up = 0.5 + 0.5 * normals[:, 2]
        zf = np.clip((points[:, 2] - zmin) / span, 0.0, 1.0)
        val = (1.0 - 0.195 * occ) * (0.930 + 0.056 * up + 0.014 * zf)
        r = np.clip(val + 0.012 * occ, 194.0 / 255.0, 1.0)
        g = np.clip(val, 192.0 / 255.0, 1.0)
        b = np.clip(val - 0.012 * occ, 192.0 / 255.0, 1.0)
        lv = MeshArrays.loop_vertex(me)
        lf = MeshArrays.loop_face(me)
        buf = np.ones((len(lv), 4), np.float32)
        lit = ~emissive_faces[lf]
        buf[lit, 0] = r[lv[lit]]
        buf[lit, 1] = g[lv[lit]]
        buf[lit, 2] = b[lv[lit]]
        old = me.color_attributes.get("Color 1")
        if old is not None:
            me.color_attributes.remove(old)
        ca = me.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
        ca.data.foreach_set("color_srgb", buf.reshape(-1))
        me.color_attributes.active_color = ca
        try:
            me.color_attributes.render_color_index = me.color_attributes.find("Color 1")
        except (AttributeError, TypeError):
            pass
        return {"min": int(round(float(buf[lit, 0].min()) * 255)) if lit.any() else 255, "mean": int(round(float(buf[lit, 0].mean()) * 255)) if lit.any() else 255}


class AnimTrack:
    @staticmethod
    def pose(track, u):
        kind = track.get("kind", "bob_rock")
        cycles = float(track.get("cycles", 1.0 if kind in ("spin_z", "sign_sway", "crown_hover", "marker_spin") else 2.0))
        amp_z = float(track.get("amp_z", 0.0 if kind == "spin_z" else 0.03))
        spin = float(track.get("spin_deg", 360.0 if kind in ("spin_z", "marker_spin") else 0.0))
        tilt = float(track.get("tilt_x", track.get("rock_x", 0.0)))
        rock = float(track.get("rock_y", 0.0 if kind in ("spin_z", "marker_spin") else 4.0))
        twist = float(track.get("twist_z", 0.0))
        loc = Vector((0.0, 0.0, amp_z * 0.5 * (1.0 - math.cos(u * math.tau * cycles))))
        rx = math.radians(tilt * math.sin(u * math.tau * cycles))
        ry = math.radians(rock * math.sin(u * math.tau))
        rz = math.radians(spin * u + twist * math.sin(u * math.tau))
        return loc, Euler((rx, ry, rz), "XYZ").to_quaternion()


class RigBuilder:
    @staticmethod
    def build(prop_id, root, bones, anim, shift, vertex_bones):
        ordered = ["root"]
        remaining = [k for k in bones if k != "root"]
        while remaining:
            moved = False
            for k in list(remaining):
                if (bones[k].get("parent") or "root") in ordered:
                    ordered.append(k)
                    remaining.remove(k)
                    moved = True
            if not moved:
                ordered.extend(remaining)
                break
        arm = bpy.data.armatures.new(prop_id + "_rig")
        rig = bpy.data.objects.new(prop_id + "_rig", arm)
        bpy.context.scene.collection.objects.link(rig)
        for ob in bpy.context.view_layer.objects:
            ob.select_set(ob == rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        made = {}
        for name in ordered:
            eb = arm.edit_bones.new(name)
            head = Vector((0.0, 0.0, 0.0)) if name == "root" else Vector(bones[name]["pivot"]) + shift
            eb.head = head
            eb.tail = head + Vector((0.0, 0.05, 0.0))
            eb.roll = 0.0
            parent = bones[name].get("parent") if name != "root" else None
            if parent and parent in made:
                eb.parent = made[parent]
            made[name] = eb
        bpy.ops.object.mode_set(mode="OBJECT")
        for name in ordered:
            members = np.nonzero(vertex_bones == ordered.index(name))[0]
            vg = root.vertex_groups.new(name=name)
            if len(members):
                vg.add([int(i) for i in members], 1.0, "REPLACE")
        mod = root.modifiers.new("sculpt_forge_rig", "ARMATURE")
        mod.object = rig
        fps = int(anim.get("fps", 30))
        frames = int(anim.get("frames", 121))
        tracks = anim.get("tracks", {})
        rig.animation_data_create()
        action = bpy.data.actions.new(prop_id + "_action")
        rig.animation_data.action = action
        for pb in rig.pose.bones:
            pb.rotation_mode = "QUATERNION"
        scene = bpy.context.scene
        scene.render.fps = fps
        scene.frame_start = 1
        scene.frame_end = frames
        for name in ordered:
            track = tracks.get(name)
            locs = [[], [], []]
            rots = [[], [], [], []]
            prev = None
            for f in range(frames):
                u = f / float(max(1, frames - 1))
                if f == 0 or not track:
                    loc, q = Vector((0.0, 0.0, 0.0)), Euler((0.0, 0.0, 0.0)).to_quaternion()
                else:
                    loc, q = AnimTrack.pose(track, u)
                if prev is not None and prev.dot(q) < 0.0:
                    q = -q
                prev = q.copy()
                for i in range(3):
                    locs[i].extend((float(f + 1), loc[i]))
                for i in range(4):
                    rots[i].extend((float(f + 1), q[i]))
            for i in range(3):
                fc = action.fcurves.new('pose.bones["{}"].location'.format(name), index=i, action_group=name)
                fc.keyframe_points.add(frames)
                fc.keyframe_points.foreach_set("co", locs[i])
                fc.update()
            for i in range(4):
                fc = action.fcurves.new('pose.bones["{}"].rotation_quaternion'.format(name), index=i, action_group=name)
                fc.keyframe_points.add(frames)
                fc.keyframe_points.foreach_set("co", rots[i])
                fc.update()
        scene.frame_set(1)
        return rig, {"rig_name": rig.name, "action_name": action.name, "fps": fps, "frames": frames, "duration": round((frames - 1) / float(fps), 4), "bones": ordered, "auto_start": bool(anim.get("auto_start", True))}


class AtlasBaker:
    @staticmethod
    def dilate(values, covered, passes):
        values = np.array(values, np.float32, copy=True)
        covered = np.array(covered, bool, copy=True)
        if not covered.any():
            return np.full_like(values, 0.5)
        for _ in range(int(passes)):
            if covered.all():
                break
            weight = covered.astype(np.float32)
            acc = np.zeros_like(values)
            cnt = np.zeros(covered.shape, np.float32)
            for axis in (0, 1):
                for shift in (1, -1):
                    acc += np.roll(values * weight[..., None], shift, axis=axis)
                    cnt += np.roll(weight, shift, axis=axis)
            grow = (~covered) & (cnt > 0.0)
            values[grow] = acc[grow] / cnt[grow][:, None]
            covered |= grow
        if not covered.all():
            values[~covered] = values[covered].mean(axis=0)
        return values

    @staticmethod
    def bake(builder, root, high, size, out_dir, extra=()):
        scene = bpy.context.scene
        me = root.data
        while len(me.uv_layers) > 1:
            me.uv_layers.remove(me.uv_layers[-1])
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        me.uv_layers[0].name = "UVMap"
        for ob in bpy.context.view_layer.objects:
            ob.select_set(False)
        root.select_set(True)
        bpy.context.view_layer.objects.active = root
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.012)
        bpy.ops.object.mode_set(mode="OBJECT")
        color_img = bpy.data.images.new(root.name + "_bake_color", size, size, alpha=True)
        ao_img = bpy.data.images.new(root.name + "_bake_ao", size, size, alpha=True, float_buffer=True)
        for img in (color_img, ao_img):
            img.pixels.foreach_set(np.zeros(size * size * 4, np.float32))
        bake_mat = bpy.data.materials.new(root.name + "_bake_target")
        if hasattr(bake_mat, "use_nodes") and not bake_mat.use_nodes:
            bake_mat.use_nodes = True
        node = bake_mat.node_tree.nodes.new("ShaderNodeTexImage")
        bake_mat.node_tree.nodes.active = node
        saved_mats = list(me.materials)
        saved_index = MeshArrays.polygon_ints(me, "material_index")
        me.materials.clear()
        me.materials.append(bake_mat)
        me.polygons.foreach_set("material_index", np.zeros(len(me.polygons), np.int32))
        engine = scene.render.engine
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 32
        scene.render.bake.use_selected_to_active = True
        extent = float(max(root.dimensions))
        scene.render.bake.cage_extrusion = max(0.004, 0.006 * extent)
        scene.render.bake.max_ray_distance = max(0.01, 0.02 * extent)
        scene.render.bake.margin = max(4, size // 64)
        try:
            scene.render.bake.target = "IMAGE_TEXTURES"
        except (AttributeError, TypeError):
            pass
        for ob in bpy.context.view_layer.objects:
            ob.select_set(False)
        high.hide_render = False
        high.select_set(True)
        for ob in extra:
            ob.hide_render = False
            ob.select_set(True)
        root.select_set(True)
        bpy.context.view_layer.objects.active = root
        node.image = color_img
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_clear=False, use_selected_to_active=True)
        node.image = ao_img
        bpy.ops.object.bake(type="AO", use_clear=False, use_selected_to_active=True)
        scene.render.engine = engine
        color = np.empty(size * size * 4, np.float32)
        color_img.pixels.foreach_get(color)
        ao = np.empty(size * size * 4, np.float32)
        ao_img.pixels.foreach_get(ao)
        color = color.reshape(size, size, 4)
        ao = ao.reshape(size, size, 4)
        covered = color[..., 3] > 0.5
        rgb = AtlasBaker.dilate(color[..., :3], covered, max(16, size // 16))
        occ = AtlasBaker.dilate(ao[..., :1], ao[..., 3] > 0.5, max(16, size // 16))[..., 0]
        shade = 0.6 + 0.4 * np.clip(occ, 0.0, 1.0)
        out = np.ones((size, size, 4), np.float32)
        out[..., :3] = np.clip(rgb * shade[..., None], 0.0, 1.0)
        builder.log.append({"atlas_coverage": round(float(covered.mean()), 4)})
        path = os.path.join(out_dir, root.name + "_atlas.png")
        final = bpy.data.images.new(root.name + "_atlas", size, size, alpha=False)
        final.pixels.foreach_set(out.reshape(-1))
        final.filepath_raw = path
        final.file_format = "PNG"
        final.save()
        bpy.data.images.remove(final)
        for img in (color_img, ao_img):
            bpy.data.images.remove(img)
        me.materials.clear()
        for m in saved_mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", saved_index)
        bpy.data.materials.remove(bake_mat)
        return bpy.data.images.load(path, check_existing=True)


class QualityProbe:
    @staticmethod
    def measure(me, evaluator, voxel, shift, field_faces=None):
        dihedral, _, _ = MeshArrays.edge_dihedral(me)
        verts = MeshArrays.vertices(me).astype(np.float32)
        lv = MeshArrays.loop_vertex(me)
        lf = MeshArrays.loop_face(me)
        mask = np.ones(len(me.polygons), bool) if field_faces is None else np.asarray(field_faces, bool)
        loops = np.nonzero(mask[lf])[0]
        step = max(1, len(loops) // 12000)
        sample = loops[::step]
        corner = MeshArrays.corner_normals(me)
        cn = corner[sample]
        exact = evaluator.normals(verts[lv[sample]] - shift, voxel * 0.5)
        err = np.degrees(np.arccos(np.clip((cn * exact).sum(axis=1), -1.0, 1.0)))
        used = np.unique(lv[loops])
        dev = np.abs(evaluator.distances(verts[used] - shift)) * 1000.0
        centres = MeshArrays.polygon_vectors(me, "center")
        face_normals = MeshArrays.polygon_vectors(me, "normal")
        agree = (face_normals[mask] * evaluator.normals(centres[mask] - shift, voxel * 0.5)).sum(axis=1)
        mean_corner = np.zeros_like(face_normals)
        np.add.at(mean_corner, lf, corner)
        mean_corner /= np.maximum(np.linalg.norm(mean_corner, axis=1, keepdims=True), 1e-9)
        inverted = int(((mean_corner * face_normals).sum(axis=1) < 0.0).sum())
        me.calc_loop_triangles()
        areas = np.empty(len(me.loop_triangles), np.float32)
        me.loop_triangles.foreach_get("area", areas)
        area = float(areas.sum())
        sizes = MeshArrays.polygon_ints(me, "loop_total")
        return {
            "tris": MeshArrays.tris(me),
            "verts": len(me.vertices),
            "all_triangles": bool(sizes.max() == 3) if len(sizes) else True,
            "has_custom_normals": bool(me.has_custom_normals),
            "surface_m2": round(area, 3),
            "tris_per_m2": round(MeshArrays.tris(me) / max(area, 1e-6), 1),
            "shells": MeshArrays.shells(me),
            "degenerate_tris": int((areas < 1e-9).sum()),
            "flipped_faces": int((agree < 0.05).sum()),
            "inverted_faces": inverted,
            "dihedral_deg": {
                "p50": round(float(np.percentile(dihedral, 50)), 2),
                "p90": round(float(np.percentile(dihedral, 90)), 2),
                "max": round(float(dihedral.max()), 2),
                "over30": round(float((dihedral > 30).mean()), 4),
                "over45": round(float((dihedral > 45).mean()), 4),
                "folds_over120": int((dihedral > 120).sum()),
            },
            "normal_error_deg": {"mean": round(float(err.mean()), 3), "p95": round(float(np.percentile(err, 95)), 3), "max": round(float(err.max()), 3)},
            "surface_dev_mm": {"mean": round(float(dev.mean()), 3), "p95": round(float(np.percentile(dev, 95)), 3), "max": round(float(dev.max()), 3)},
        }


class SurfaceRefiner:
    def __init__(self, field, voxel, tau=0.002, strain_deg=20.0, strain_weight=4.0, strain_cap_deg=60.0):
        self.field = field
        self.voxel = float(voxel)
        self.h = 0.5 * float(voxel)
        self.tau = float(tau)
        self.strain_free = math.radians(float(strain_deg))
        self.strain_weight = float(strain_weight)
        self.strain_cap = math.radians(float(strain_cap_deg))

    @staticmethod
    def face_frame(verts, tris):
        n = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
        length = np.linalg.norm(n, axis=1)
        return n / np.maximum(length, 1e-20)[:, None], 0.5 * length

    @staticmethod
    def halfedges(tris):
        return tris.reshape(-1), tris[:, [1, 2, 0]].reshape(-1), tris[:, [2, 0, 1]].reshape(-1)

    @staticmethod
    def twins(start, end, count):
        key = np.minimum(start, end).astype(np.int64) * int(count) + np.maximum(start, end)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        first = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]])
        size = np.diff(np.r_[first, len(ks)])
        pair = first[size == 2]
        h1 = order[pair]
        h2 = order[pair + 1]
        good = (start[h1] == end[h2]) & (end[h1] == start[h2])
        twin = np.full(len(start), -1, np.int64)
        twin[h1[good]] = h2[good]
        twin[h2[good]] = h1[good]
        return twin, key

    @staticmethod
    def angle(n1, n2):
        return np.arccos(np.clip((n1 * n2).sum(axis=1), -1.0, 1.0))

    @staticmethod
    def unit(v):
        return v / np.maximum(np.linalg.norm(v, axis=1), 1e-20)[:, None]

    @staticmethod
    def dedupe(tris):
        ordered = np.sort(tris, axis=1)
        valid = np.flatnonzero((ordered[:, 0] != ordered[:, 1]) & (ordered[:, 1] != ordered[:, 2]))
        keep = np.zeros(len(tris), bool)
        keep[valid[np.unique(ordered[valid], axis=0, return_index=True)[1]]] = True
        return keep

    def distances(self, points):
        return self.field.distances(np.ascontiguousarray(points, np.float32)).astype(np.float64)

    def normals(self, points):
        g = self.field.gradient(np.ascontiguousarray(points, np.float32), self.h).astype(np.float64)
        return g / np.maximum(np.linalg.norm(g, axis=1), 1e-12)[:, None]

    def strain(self, normal, corners, vnorm):
        tilt = np.stack([self.angle(normal, vnorm[c]) for c in corners], axis=1)
        return (np.maximum(tilt - self.strain_free, 0.0) ** 2).sum(axis=1) * self.strain_weight, tilt.max(axis=1)

    def flip_cost(self, n1, n2, outer, sides, dev, strain):
        cost = self.angle(n1, n2) ** 2
        for o, side in zip(outer, sides):
            term = np.zeros(len(n1))
            term[o[1]] = self.angle(side[o[1]], o[0][o[1]]) ** 2
            cost = cost + term
        return cost + ((dev / self.tau) ** 2).sum(axis=1) + strain

    def flip(self, verts, tris, mats, rounds=8):
        flips = 0
        count = len(verts)
        vnorm = self.normals(verts)
        for _ in range(int(rounds)):
            start, end, apex = self.halfedges(tris)
            twin, key = self.twins(start, end, count)
            h1 = np.flatnonzero(twin > np.arange(len(twin)))
            h2 = twin[h1]
            t1 = h1 // 3
            t2 = h2 // 3
            a = start[h1]
            b = end[h1]
            c = apex[h1]
            d = apex[h2]
            new_key = np.minimum(c, d).astype(np.int64) * count + np.maximum(c, d)
            pick = np.flatnonzero((mats[t1] == mats[t2]) & (c != d) & ~np.isin(new_key, key))
            if not len(pick):
                break
            h1, h2, t1, t2, a, b, c, d, new_key = h1[pick], h2[pick], t1[pick], t2[pick], a[pick], b[pick], c[pick], d[pick], new_key[pick]
            fn, area = self.face_frame(verts, tris)
            n1 = fn[t1]
            n2 = fn[t2]
            pa, pb, pc, pd = verts[a], verts[b], verts[c], verts[d]
            m1 = np.cross(pa - pc, pd - pc)
            m2 = np.cross(pb - pd, pc - pd)
            area1 = 0.5 * np.linalg.norm(m1, axis=1)
            area2 = 0.5 * np.linalg.norm(m2, axis=1)
            m1 = self.unit(m1)
            m2 = self.unit(m2)
            k1 = h1 % 3
            k2 = h2 % 3
            outer = []
            for h in (3 * t1 + (k1 + 1) % 3, 3 * t1 + (k1 + 2) % 3, 3 * t2 + (k2 + 1) % 3, 3 * t2 + (k2 + 2) % 3):
                tw = twin[h]
                outer.append((fn[np.maximum(tw, 0) // 3], tw >= 0, np.where(tw >= 0, tw // 3, -1)))
            m = len(pick)
            samples = np.concatenate([(pa + pb + pc) / 3.0, (pa + pb + pd) / 3.0, 0.5 * (pa + pb), (pc + pa + pd) / 3.0, (pd + pb + pc) / 3.0, 0.5 * (pc + pd)])
            dist = self.distances(samples).reshape(6, m).T
            nq = self.normals(0.25 * (pa + pb + pc + pd))
            s_old1, x_old1 = self.strain(n1, (a, b, c), vnorm)
            s_old2, x_old2 = self.strain(n2, (b, a, d), vnorm)
            s_new1, x_new1 = self.strain(m1, (c, a, d), vnorm)
            s_new2, x_new2 = self.strain(m2, (d, b, c), vnorm)
            old = self.flip_cost(n1, n2, outer, (n1, n1, n2, n2), dist[:, :3], s_old1 + s_old2)
            new = self.flip_cost(m1, m2, outer, (m2, m1, m1, m2), dist[:, 3:], s_new1 + s_new2)
            floor = 1e-4 * float(np.median(area)) + 1e-12
            worst = np.maximum(np.maximum(x_old1, x_old2), self.strain_cap)
            safe = ((m1 * nq).sum(axis=1) > 0.2) & ((m2 * nq).sum(axis=1) > 0.2) & (area1 > floor) & (area2 > floor) & (np.maximum(x_new1, x_new2) <= worst)
            gain = old - new
            good = np.flatnonzero(safe & (gain > 1e-3 + 0.02 * old))
            if not len(good):
                break
            used = np.zeros(len(tris), bool)
            made = set()
            done = 0
            for i in good[np.argsort(-gain[good])]:
                faces = [t1[i], t2[i]] + [o[2][i] for o in outer if o[2][i] >= 0]
                if used[faces].any() or int(new_key[i]) in made:
                    continue
                used[faces] = True
                made.add(int(new_key[i]))
                tris[t1[i]] = (c[i], a[i], d[i])
                tris[t2[i]] = (d[i], b[i], c[i])
                done += 1
            flips += done
            if done == 0:
                break
        return tris, flips


class StageClock:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.stages = {}

    def mark(self, name):
        t = time.perf_counter()
        self.stages[name] = round(t - self.t0, 3)
        self.t0 = t


class SculptBuilder:
    size_classes = {
        "hero": {"budget": 12000, "lod_dist": 150.0},
        "medium": {"budget": 6000, "lod_dist": 120.0},
        "small": {"budget": 3000, "lod_dist": 80.0},
    }

    def __init__(self, prop_id, budget=None, size_class="hero", lod_dist=None, colliders="auto", set_name="sculpt_set", style="sculpt_forge_v1", target="prop", archetype="sculpt", voxel=0.005, palette=None, default_role=None, reset_scene=None, iso=0.0, ao_distance=0.18, ao_strength=1.0, atlas=0, keep_high=True, high_tris=400000, smooth_roles=True, font=None, stage_ratio=3.0, detail_share=0.35, uv_spread=0.2, crisp_roles=True):
        if target not in ("prop", "library"):
            raise ValueError("target must be 'prop' or 'library'")
        if size_class not in self.size_classes:
            raise ValueError("size_class must be one of {}".format(", ".join(self.size_classes)))
        self.reset_scene = bpy.app.background if reset_scene is None else bool(reset_scene)
        if self.reset_scene:
            bpy.ops.wm.read_factory_settings(use_empty=True)
        self.id = str(prop_id)
        self.size_class = size_class
        self.budget = int(budget or self.size_classes[size_class]["budget"])
        self.lod_dist = float(lod_dist or self.size_classes[size_class]["lod_dist"])
        self.colliders_spec = colliders
        self.set_name = str(set_name)
        self.style = str(style)
        self.target = target
        self.archetype = str(archetype)
        self.voxel = float(voxel)
        self.palette = SetPalette.from_spec(self.set_name, palette)
        self.default_role = default_role or (next(iter(self.palette.roles)) if self.palette.roles else "body")
        self.palette.ensure(self.default_role)
        self.iso = float(iso)
        self.ao_distance = float(ao_distance)
        self.ao_strength = float(ao_strength)
        self.atlas = int(atlas or 0)
        self.keep_high = bool(keep_high)
        self.high_tris = int(high_tris)
        self.smooth_roles = bool(smooth_roles)
        self.font = font
        self.stage_ratio = float(stage_ratio)
        self.detail_share = float(detail_share)
        self.uv_spread = float(min(max(uv_spread, 0.01), 0.8))
        self.crisp_roles = bool(crisp_roles)
        self.root = GroupNode("root", "union", 0.0)
        self.current = self.root
        self.owners = []
        self.poly_parts = []
        self.colliders = []
        self.bones = {"root": {"pivot": (0.0, 0.0, 0.0), "parent": None}}
        self.anim = None
        self.warnings = []
        self.log = []
        self.clock = StageClock()
        self.shift = np.zeros(3, np.float32)

    def register(self, node, role, bone, detail, collide, kind, mirror_x):
        if mirror_x:
            pair = GroupNode(kind + "_mirror", node.op, node.fillet)
            twin_src = node
            node.op = "union"
            node.fillet = 0.0
            pair.children = [twin_src, twin_src.mirrored()]
            self.current.children.append(pair)
            bounds = pair.world_bounds()
        else:
            self.current.children.append(node)
            bounds = node.world_bounds()
        if node.owner >= 0:
            self.owners[node.owner]["bounds"] = bounds
        return node

    def new_owner(self, role, bone, detail, collide, kind, needs_role=True):
        if role is None and not needs_role:
            return -1
        role = str(role or self.default_role)
        if not self.palette.ensure(role):
            self.warnings.append("role {} was not in the palette; added {}".format(role, self.palette.roles[role]["color"]))
        if bone and bone not in self.bones:
            raise ValueError("bone {} is not defined; call define_bone first".format(bone))
        self.owners.append({"role": role, "bone": bone or "root", "detail": bool(detail), "collide": bool(collide), "kind": kind, "bounds": None})
        return len(self.owners) - 1

    def primitive(self, kind, params, extent, loc, rot, plane, role, fillet, op, mirror_x, bone, detail, collide, raster_source=None):
        if op not in ("union", "subtract", "intersect"):
            raise ValueError("op must be union, subtract or intersect")
        owner = self.new_owner(role, bone, detail, collide, kind, needs_role=(op == "union"))
        node = PrimitiveNode(owner, op, fillet, kind, params, extent, loc, SdfMath.frame(plane, rot), raster_source)
        return self.register(node, role, bone, detail, collide, kind, mirror_x)

    def sphere(self, radius, loc=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        r = float(radius)
        return self.primitive("sphere", {"radius": r}, ((-r, -r, -r), (r, r, r)), loc, (0, 0, 0), "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def ellipsoid(self, radii, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        r = np.asarray(radii, np.float32)
        return self.primitive("ellipsoid", {"radii": r}, (-r, r), loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def capsule(self, a, b, radius, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        a = np.asarray(a, np.float32)
        b = np.asarray(b, np.float32)
        r = float(radius)
        ext = (np.minimum(a, b) - r, np.maximum(a, b) + r)
        return self.primitive("capsule", {"a": a, "b": b, "radius": r}, ext, (0, 0, 0), (0, 0, 0), "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def round_cone(self, a, b, radius_a, radius_b, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        a = np.asarray(a, np.float32)
        b = np.asarray(b, np.float32)
        r = float(max(radius_a, radius_b))
        ext = (np.minimum(a, b) - r, np.maximum(a, b) + r)
        return self.primitive("round_cone", {"a": a, "b": b, "radius_a": float(radius_a), "radius_b": float(radius_b)}, ext, (0, 0, 0), (0, 0, 0), "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def round_box(self, size, radius=0.0, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        s = np.asarray(size, np.float32)
        return self.primitive("round_box", {"size": s, "radius": float(radius)}, (-s * 0.5, s * 0.5), loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def pillow_box(self, size, radius=None, puff=0.03, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        s = np.asarray(size, np.float32)
        r = float(radius if radius is not None else 0.1 * float(s.min()))
        bulge = np.asarray(puff, np.float32) * np.ones(3, np.float32)
        return self.primitive("pillow_box", {"size": s, "radius": r, "puff": bulge}, (-s * 0.5 - bulge, s * 0.5 + bulge), loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def round_cyl(self, radius, height, edge=None, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        r = float(radius)
        h = float(height)
        e = float(edge if edge is not None else min(0.3 * r, 0.25 * h))
        return self.primitive("round_cyl", {"radius": r, "height": h, "edge": e}, ((-r, -r, -h * 0.5), (r, r, h * 0.5)), loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def torus(self, major, minor, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        R = float(major)
        r = float(minor)
        return self.primitive("torus", {"major": R, "minor": r}, ((-R - r, -R - r, -r), (R + r, R + r, r)), loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide)

    def lathe(self, profile, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), smooth=2, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        prof = np.asarray(profile, np.float64)
        prof[:, 0] = np.maximum(prof[:, 0], 0.0)
        on_axis = prof[0, 0] < 1e-6 and prof[-1, 0] < 1e-6
        if smooth:
            prof = Polygon2D.chaikin(prof, int(smooth), not on_axis)
        source = RasterSource([prof])
        rmax = float(prof[:, 0].max())
        ext = ((-rmax, -rmax, float(prof[:, 1].min())), (rmax, rmax, float(prof[:, 1].max())))
        return self.primitive("lathe", {}, ext, loc, rot, "XY", role, fillet, op, mirror_x, bone, detail, collide, source)

    def extrude2d(self, outline, depth, edge=0.0, puff=0.0, puff_width=None, holes=None, plane="XZ", back_puff=True, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        loops = [Shapes.resolve2d(outline)] + [Shapes.resolve2d(h) for h in (holes or [])]
        source = RasterSource(loops)
        lo, hi = source.bounds()
        depth = float(depth)
        r = float(min(max(edge, 0.0), depth * 0.5 - 1e-4))
        width = float(puff_width if puff_width is not None else max(3.0 * r, 0.25 * float(min(hi - lo))))
        params = {"depth": depth, "rounding": r, "puff": float(puff), "puff_width": width, "back_puff": bool(back_puff)}
        half = depth * 0.5 + max(float(puff), 0.0)
        ext = ((lo[0], lo[1], -half), (hi[0], hi[1], half))
        return self.primitive("extrude", params, ext, loc, rot, plane, role, fillet, op, mirror_x, bone, detail, collide, source)

    def chain(self, elements, role, fillet, op, mirror_x, bone, detail, collide, kind, blend=0.0):
        if not elements:
            raise ValueError("{} produced no elements".format(kind))
        owner = self.new_owner(role, bone, detail, collide, kind, needs_role=(op == "union"))
        node = ChainNode(owner, op, fillet, elements, blend)
        return self.register(node, role, bone, detail, collide, kind, mirror_x)

    def tube(self, path, radius, closed=None, step=None, ends=0.0, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        pts, closed = Shapes.resolve3d(path, closed)
        span = float(len(pts) if closed else max(1, len(pts) - 1))
        if callable(radius):
            radii = np.array([float(radius(t)) for t in np.linspace(0.0, 1.0, 65)], np.float64)
        else:
            radii = np.asarray(radius, np.float64).reshape(-1)
        step = float(step or max(0.004, min(0.015, 0.6 * float(radii.min()))))
        samples, par = CatmullRom.sample(pts, closed, step)
        if callable(radius):
            rs = np.array([float(radius(float(t))) for t in np.clip(par / span, 0.0, 1.0)], np.float64)
        else:
            rs = CatmullRom.along(radii, par, len(pts), closed)
        count = len(samples)
        pairs = count if closed else count - 1
        elements = []
        for i in range(pairs):
            j = (i + 1) % count
            a = samples[i].astype(np.float32)
            b = samples[j].astype(np.float32)
            ra = float(rs[i])
            rb = float(rs[j])
            m = max(ra, rb)
            elements.append({"kind": "cone", "a": a, "b": b, "ra": ra, "rb": rb, "lo": np.minimum(a, b) - m, "hi": np.maximum(a, b) + m})
        if ends and not closed:
            for k in (0, count - 1):
                c = samples[k].astype(np.float32)
                r = float(rs[k]) * float(ends)
                elements.append({"kind": "sphere", "c": c, "r": r, "lo": c - r, "hi": c + r})
        return self.chain(elements, role, fillet, op, mirror_x, bone, detail, collide, "tube")

    def beads(self, path, radius, spacing=None, count=None, closed=None, jitter=0.0, seed=0, blend=0.0, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        pts, closed = Shapes.resolve3d(path, closed)
        samples, _ = CatmullRom.sample(pts, closed, 0.004)
        ring, cum = CatmullRom.arc_frames(samples, closed)
        length = float(cum[-1])
        r0 = float(radius)
        n = int(count or max(2, int(round(length / float(spacing or 2.0 * r0)))))
        rng = random.Random(int(seed))
        s = (np.arange(n) + (0.5 if closed else 0.0)) * (length / (n if closed else max(1, n - 1)))
        elements = []
        for sk in s:
            c = np.array([np.interp(sk, cum, ring[:, k]) for k in range(3)], np.float32)
            r = r0 * (1.0 + float(jitter) * rng.uniform(-1.0, 1.0))
            elements.append({"kind": "sphere", "c": c, "r": r, "lo": c - r, "hi": c + r})
        return self.chain(elements, role, fillet, op, mirror_x, bone, detail, collide, "beads", blend)

    def drips(self, path, count, length=(0.06, 0.16), radius=(0.025, 0.035), closed=None, seed=0, jitter=0.35, sink=0.01, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        pts, closed = Shapes.resolve3d(path, closed)
        samples, _ = CatmullRom.sample(pts, closed, 0.004)
        ring, cum = CatmullRom.arc_frames(samples, closed)
        total = float(cum[-1])
        rng = random.Random(int(seed))
        lmin, lmax = (float(length), float(length)) if np.isscalar(length) else (float(length[0]), float(length[1]))
        rmin, rmax = (float(radius), float(radius)) if np.isscalar(radius) else (float(radius[0]), float(radius[1]))
        n = int(count)
        elements = []
        for k in range(n):
            sk = ((k + 0.5 + float(jitter) * rng.uniform(-1.0, 1.0)) / n) * total if closed else (k + 0.5 * rng.uniform(0.6, 1.4)) / n * total
            sk = min(max(sk, 0.0), total)
            top = np.array([np.interp(sk, cum, ring[:, a]) for a in range(3)], np.float32)
            top[2] += float(sink)
            r = rng.uniform(rmin, rmax)
            ln = max(rng.uniform(lmin, lmax), 1.3 * r)
            elements.append({"kind": "drip", "top": top, "length": float(ln), "r": float(r), "lo": top - np.array([r, r, ln], np.float32), "hi": top + np.array([r, r, r], np.float32)})
        return self.chain(elements, role, fillet, op, mirror_x, bone, detail, collide, "drips")

    def scallops(self, path, drop=0.08, thickness=0.03, per_m=8.0, count=None, overlap=1.12, outward=0.0, up=None, blend=None, closed=None, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        pts, closed = Shapes.resolve3d(path, closed)
        samples, _ = CatmullRom.sample(pts, closed, 0.004)
        ring, cum = CatmullRom.arc_frames(samples, closed)
        length = float(cum[-1])
        n = int(count or max(1, int(round(length * float(per_m)))))
        pitch = length / float(n)
        top = float(up if up is not None else 0.5 * float(thickness))
        radii = np.array([0.5 * pitch * float(overlap), 0.5 * float(thickness), float(drop)], np.float32)
        reach = float(max(radii.max(), top))
        vertical = np.array([0.0, 0.0, 1.0])
        elements = []
        for k in range(n):
            s = (k + 0.5) * pitch
            t = CatmullRom.tangent_at(ring, cum, s, closed)
            t = t - vertical * float(t @ vertical)
            t /= max(float(np.linalg.norm(t)), 1e-9)
            side = np.cross(t, vertical)
            c = (CatmullRom.point_at(ring, cum, s) + side * float(outward)).astype(np.float32)
            rot = np.stack([t, side, vertical], axis=1).astype(np.float32)
            elements.append({"kind": "lobe", "c": c, "rot": rot, "radii": radii, "up": top, "lo": c - reach, "hi": c + reach})
        soft = float(blend if blend is not None else 0.35 * float(thickness))
        return self.chain(elements, role, fillet, op, mirror_x, bone, detail, collide, "scallops", soft)

    def text(self, body, font=None, height=0.25, size=None, max_width=None, depth=0.04, puff=0.01, plane="XZ", spacing=1.0, resolution=5, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=True, collide=False):
        cu = bpy.data.curves.new("sf_text", "FONT")
        cu.body = str(body)
        path = font or self.font or SculptBuilder.default_font()
        if path:
            cu.font = bpy.data.fonts.load(path, check_existing=True)
        cu.size = float(size or 1.0)
        cu.extrude = float(depth) * 0.5
        cu.bevel_depth = 0.0
        cu.resolution_u = int(resolution)
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.space_character = float(spacing)
        ob = bpy.data.objects.new("sf_text", cu)
        bpy.context.scene.collection.objects.link(ob)
        deps = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.curves.remove(cu)
        verts, tris = SculptBuilder.mesh_triangles(me, Matrix.Identity(4))
        bpy.data.meshes.remove(me)
        if len(tris) == 0:
            raise ValueError("text {!r} produced no geometry".format(body))
        lo = verts.min(axis=0)
        hi = verts.max(axis=0)
        verts[:, :2] -= (lo[:2] + hi[:2]) * 0.5
        scale = 1.0
        if size is None and height:
            scale = float(height) / max(float(hi[1] - lo[1]), 1e-6)
        if max_width:
            scale = min(scale, float(max_width) / max(float(hi[0] - lo[0]) * 1.0, 1e-6))
        verts[:, :2] *= scale
        world = verts @ SdfMath.frame(plane, rot).T + np.asarray(loc, np.float32)
        return self.level_set(world, tris, puff, role, fillet, op, mirror_x, bone, detail, collide, "text")

    def mesh_part(self, source, puff=0.0, role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False):
        if isinstance(source, dict):
            with bpy.data.libraries.load(bpy.path.abspath(source["blend"]), link=False) as (src, dst):
                dst.objects = [source["object"]]
            ob = dst.objects[0]
            verts, tris = SculptBuilder.mesh_triangles(ob.data, ob.matrix_world)
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
        else:
            deps = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(source.evaluated_get(deps), depsgraph=deps)
            verts, tris = SculptBuilder.mesh_triangles(me, source.matrix_world)
            bpy.data.meshes.remove(me)
        return self.level_set(verts, tris, puff, role, fillet, op, mirror_x, bone, detail, collide, "mesh_part")

    def level_set(self, verts, tris, puff, role, fillet, op, mirror_x, bone, detail, collide, kind):
        if op not in ("union", "subtract", "intersect"):
            raise ValueError("op must be union, subtract or intersect")
        owner = self.new_owner(role, bone, detail, collide, kind, needs_role=(op == "union"))
        node = LevelSetNode(owner, op, fillet, verts, tris, puff)
        return self.register(node, role, bone, detail, collide, kind, mirror_x)

    def cut(self, point=(0.0, 0.0, 0.0), normal=(0.0, 0.0, -1.0), fillet=0.0, role=None, mirror_x=False):
        owner = self.new_owner(role, None, False, False, "cut", needs_role=False)
        node = HalfSpaceNode(owner, "intersect", fillet, point, normal)
        return self.register(node, role, None, False, False, "cut", mirror_x)

    @contextmanager
    def group(self, name="group", fillet=0.0, op="union"):
        node = GroupNode(name, op, float(fillet))
        self.current.children.append(node)
        previous = self.current
        self.current = node
        try:
            yield node
        finally:
            self.current = previous

    def bevel_box(self, size, radius=0.02, segments=4, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), role=None, bone=None, collide=False):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if radius > 0.0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=float(radius), offset_type="OFFSET", segments=int(segments), profile=0.5, affect="EDGES", clamp_overlap=True)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4(), verts=bm.verts)
        me = bpy.data.meshes.new(self.id + "_poly")
        bm.to_mesh(me)
        bm.free()
        return self.poly_part(me, role=role, bone=bone, collide=collide)

    def poly_part(self, source, role=None, bone=None, collide=False, weighted=True):
        if isinstance(source, bpy.types.Object):
            deps = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(source.evaluated_get(deps), depsgraph=deps)
            me.transform(source.matrix_world)
        else:
            me = source
        owner = self.new_owner(role, bone, False, collide, "poly_part")
        verts = MeshArrays.vertices(me)
        self.owners[owner]["bounds"] = (verts.min(axis=0), verts.max(axis=0))
        self.poly_parts.append({"mesh": me, "owner": owner, "weighted": bool(weighted)})
        return me

    def collider(self, center, size):
        self.colliders.append((Vector(center), Vector(size)))

    def define_bone(self, name, pivot, parent="root"):
        if name not in self.bones:
            self.bones[name] = {"pivot": tuple(float(v) for v in pivot), "parent": parent}
        return name

    def set_anim(self, frames=121, fps=30, tracks=None, auto_start=True):
        self.anim = {"frames": int(frames), "fps": int(fps), "tracks": dict(tracks or {}), "auto_start": bool(auto_start)}

    @staticmethod
    def default_font():
        candidates = [os.environ.get("SCULPT_FORGE_FONT", "")]
        here = globals().get("__file__")
        if here:
            base = os.path.dirname(os.path.abspath(here))
            candidates.append(os.path.join(base, "..", "..", "assets", "fonts", "TitanOne-Regular.ttf"))
            candidates.append(os.path.join(base, "..", "..", "..", "prop-forge", "assets", "fonts", "TitanOne-Regular.ttf"))
        if bpy.data.filepath:
            candidates.append(os.path.join(os.path.dirname(bpy.data.filepath), "TitanOne-Regular.ttf"))
        for path in candidates:
            if path and os.path.isfile(path):
                return os.path.normpath(path)
        return None

    @staticmethod
    def mesh_triangles(me, matrix):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.transform(matrix)
        bm.verts.ensure_lookup_table()
        verts = np.array([v.co[:] for v in bm.verts], np.float32).reshape(-1, 3)
        tris = np.array([[v.index for v in f.verts] for f in bm.faces], np.int32).reshape(-1, 3)
        bm.free()
        return verts, tris

    def band(self):
        return max(3.0 * self.voxel, 1.25 * self.root.max_fillet() + 2.0 * self.voxel, abs(self.iso) + 3.0 * self.voxel)

    def prepare(self):
        if not self.root.children:
            raise RuntimeError("SculptBuilder({}) has no SDF nodes".format(self.id))
        self.grid_band = self.band()
        self.probe_band = max(self.grid_band, self.ao_distance * 1.1)
        self.root.prepare(self.voxel, self.probe_band)
        self.grid_field = FieldEvaluator(self.root, self.grid_band)
        self.probe_field = FieldEvaluator(self.root, self.probe_band)
        self.owner_role = np.array([self.palette.index(o["role"]) for o in self.owners] + [self.palette.index(self.default_role)], np.int64)
        self.clock.mark("prepare")

    def mesh_field(self):
        vdb = VdbBridge.module()
        bounds = self.root.world_bounds()
        if bounds is None:
            raise RuntimeError("SculptBuilder({}) has no bounded union nodes".format(self.id))
        vs = self.voxel
        pad = self.grid_band + 2.0 * vs
        lo = np.floor((bounds[0] - pad) / vs).astype(np.int64)
        hi = np.ceil((bounds[1] + pad) / vs).astype(np.int64)
        dims = hi - lo + 1
        grid = VdbBridge.float_grid(vdb, self.grid_band, vs)
        slab = max(4, int(4.0e6 // max(1, int(dims[0] * dims[1]))))
        for k in range(0, int(dims[2]), slab):
            dom = GridDomain((lo[0], lo[1], lo[2] + k), (dims[0], dims[1], min(slab, int(dims[2]) - k)), vs)
            d, _ = self.grid_field.evaluate(dom)
            grid.copyFromArray(np.ascontiguousarray(d, np.float32), ijk=tuple(int(v) for v in dom.ijk0), tolerance=0.0)
        self.clock.mark("evaluate")
        pts, tris, quads = grid.convertToPolygons(isovalue=float(self.iso), adaptivity=0.0)
        pts = np.asarray(pts, np.float32)
        tris = np.asarray(tris, np.int64).reshape(-1, 3)
        quads = np.asarray(quads, np.int64).reshape(-1, 4)
        faces = np.full((len(tris) + len(quads), 4), -1, np.int64)
        faces[:len(tris), :3] = tris
        faces[len(tris):] = quads
        sizes = np.concatenate([np.full(len(tris), 3), np.full(len(quads), 4)]).astype(np.int32)
        if len(sizes) == 0:
            raise RuntimeError("SculptBuilder({}) meshed to an empty surface".format(self.id))
        pick = np.linspace(0, len(sizes) - 1, min(512, len(sizes))).astype(np.int64)
        f = faces[pick]
        v0 = pts[f[:, 0]]
        v1 = pts[f[:, 1]]
        v2 = pts[f[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        c = (v0 + v1 + v2) / 3.0
        outside = self.grid_field.distances(c + n * (0.75 * vs)) > 0.0
        if outside.mean() < 0.5:
            tri_rows = sizes == 3
            faces[tri_rows, :3] = faces[tri_rows, 2::-1]
            faces[~tri_rows] = faces[~tri_rows, ::-1]
        self.clock.mark("mesh")
        return pts, faces, sizes

    def face_roles(self, verts, faces, sizes):
        safe = np.where(faces >= 0, faces, faces[:, :1])
        centres = verts[safe].sum(axis=1) / sizes[:, None]
        owners = self.probe_field.owners(centres)
        roles = self.owner_role[np.where(owners >= 0, owners, len(self.owners))]
        nb = RoleField.neighbours(faces, sizes, len(verts))
        roles = RoleField.majority(roles, nb, 3)
        moved = 0
        if self.smooth_roles and len(np.unique(roles)) > 1:
            verts, moved = RoleField.smooth_boundaries(verts, faces, sizes, roles, self.probe_field, self.voxel)
        self.clock.mark("roles")
        return verts, roles, owners, moved

    def high_object(self, verts, faces, sizes, roles):
        me = MeshArrays.build(self.id + "_high", verts, faces, sizes)
        for role in self.palette.roles:
            me.materials.append(MaterialFactory.role_material("sf_role_" + role, self.palette.roles[role]["color"], role))
        me.polygons.foreach_set("material_index", roles.astype(np.int32))
        MeshArrays.smooth_all(me)
        ob = bpy.data.objects.new(self.id + "_high", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.hide_render = True
        self.clock.mark("high_object")
        return ob

    def copy_object(self, source, name):
        me = source.data.copy()
        me.name = name
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def relabel_faces(self, me):
        faces, sizes = MeshArrays.faces(me)
        if int(sizes.max()) != 3:
            return 0
        verts = MeshArrays.vertices(me)
        corners = verts[faces[:, :3]]
        centre = corners.mean(axis=1)
        samples = [centre] + [0.6 * corners[:, k] + 0.2 * corners[:, (k + 1) % 3] + 0.2 * corners[:, (k + 2) % 3] for k in range(3)]
        votes = np.stack([self.owner_role[np.where(o >= 0, o, len(self.owners))] for o in (self.probe_field.owners(s) for s in samples)], axis=1)
        labels = MeshArrays.polygon_ints(me, "material_index").astype(np.int64)
        same = (votes == labels[:, None]).sum(axis=1)
        best = np.array([np.bincount(row).argmax() for row in votes])
        best_count = (votes == best[:, None]).sum(axis=1)
        change = (best != labels) & (best_count >= 3) & (same <= 1)
        if change.any():
            labels[change] = best[change]
            me.polygons.foreach_set("material_index", labels.astype(np.int32))
            me.update()
        return int(change.sum())

    def snap_role_lines(self, me, high):
        hf, hs = MeshArrays.faces(high.data)
        hroles = MeshArrays.polygon_ints(high.data, "material_index").astype(np.int64)
        hv = MeshArrays.vertices(high.data)
        f1, _, f2, _, va, vb = MeshArrays.face_pairs(hf, hs, len(hv))
        cut = hroles[f1] != hroles[f2]
        if not cut.any():
            return 0
        hkey = np.minimum(hroles[f1][cut], hroles[f2][cut]) * 4096 + np.maximum(hroles[f1][cut], hroles[f2][cut])
        a = hv[va[cut]]
        b = hv[vb[cut]]
        samples = np.concatenate([a, 0.5 * (a + b), b])
        skeys = np.concatenate([hkey, hkey, hkey])
        trees = {}
        for k in np.unique(skeys):
            pts = samples[skeys == k]
            tree = KDTree(len(pts))
            for i, p in enumerate(pts):
                tree.insert(p.tolist(), i)
            tree.balance()
            trees[int(k)] = tree
        lf, ls = MeshArrays.faces(me)
        lroles = MeshArrays.polygon_ints(me, "material_index").astype(np.int64)
        lv = MeshArrays.vertices(me).astype(np.float64)
        g1, _, g2, _, wa, wb = MeshArrays.face_pairs(lf, ls, len(lv))
        lcut = lroles[g1] != lroles[g2]
        lkey = np.minimum(lroles[g1][lcut], lroles[g2][lcut]) * 4096 + np.maximum(lroles[g1][lcut], lroles[g2][lcut])
        ends = np.concatenate([wa[lcut], wb[lcut]])
        ekeys = np.concatenate([lkey, lkey])
        ev = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        elen = np.linalg.norm(lv[ev[:, 0]] - lv[ev[:, 1]], axis=1)
        shortest = np.full(len(lv), np.inf)
        np.minimum.at(shortest, ev[:, 0], elen)
        np.minimum.at(shortest, ev[:, 1], elen)
        order = np.argsort(ends, kind="stable")
        ends = ends[order]
        ekeys = ekeys[order]
        starts = np.concatenate([[0], np.nonzero(np.diff(ends))[0] + 1])
        target = lv.copy()
        moved = np.zeros(len(lv), bool)
        for s, e in zip(starts, np.concatenate([starts[1:], [len(ends)]])):
            vid = int(ends[s])
            keys = np.unique(ekeys[s:e])
            if len(keys) != 1 or int(keys[0]) not in trees:
                continue
            co, _, dist = trees[int(keys[0])].find(lv[vid].tolist())
            if co is None or dist > 0.6 * shortest[vid]:
                continue
            target[vid] = co[:]
            moved[vid] = True
        if not moved.any():
            return 0
        before = MeshArrays.polygon_vectors(me, "normal").astype(np.float64)
        sizes = ls
        rows = np.repeat(np.arange(len(sizes)), sizes)
        loops = MeshArrays.loop_vertex(me)
        for _ in range(4):
            MeshArrays.set_vertices(me, np.where(moved[:, None], target, lv))
            after = MeshArrays.polygon_vectors(me, "normal").astype(np.float64)
            bad = (before * after).sum(axis=1) < 0.6
            if not bad.any():
                break
            culprits = np.zeros(len(lv), bool)
            culprits[loops[np.isin(rows, np.nonzero(bad)[0])]] = True
            moved &= ~culprits
        MeshArrays.set_vertices(me, np.where(moved[:, None], target, lv))
        return int(moved.sum())

    def protection(self, me, points, radius, detail_owners):
        verts = MeshArrays.vertices(me)
        mask = np.zeros(len(verts), bool)
        if len(detail_owners):
            mask |= np.isin(self.probe_field.owners(verts), detail_owners)
        for start in range(0, len(points), 64):
            block = np.asarray(points[start:start + 64], np.float32)
            d2 = ((verts[:, None, :] - block[None, :, :]) ** 2).sum(axis=2).min(axis=1)
            mask |= d2 < radius * radius
        return np.nonzero(mask)[0]

    def collapse(self, ob, target, points=(), radius=0.0, detail_owners=()):
        for attempt in range(3):
            current = MeshArrays.tris(ob.data)
            if current <= target:
                break
            protect = self.protection(ob.data, points, radius, detail_owners) if attempt == 0 else []
            mod = ob.modifiers.new("sf_decimate", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = max(1e-4, min(1.0, target * (0.995 - 0.01 * attempt) / float(current)))
            mod.use_collapse_triangulate = True
            if len(protect):
                vg = ob.vertex_groups.new(name="sf_keep")
                vg.add([int(i) for i in protect], 1.0, "REPLACE")
                mod.vertex_group = vg.name
                mod.invert_vertex_group = True
                mod.vertex_group_factor = 1.0
            MeshArrays.apply_modifiers(ob)
            for vg in list(ob.vertex_groups):
                ob.vertex_groups.remove(vg)
        MeshArrays.triangulate(ob.data)

    def clean_collapse(self, source, target, radius, detail_owners, attempts):
        points = []
        best = None
        for attempt in range(int(attempts)):
            ob = self.copy_object(source, self.id + "_try")
            self.collapse(ob, target, points, radius, detail_owners)
            report, bad = self.repair(ob.data)
            report["attempts"] = attempt + 1
            score = report["flipped"] + report["folds"]
            if best is None or score < best[0]:
                if best is not None:
                    self.discard(best[1])
                best = (score, ob, report)
            else:
                self.discard(ob)
            if score == 0:
                break
            points.extend(bad)
        return best[1], best[2]

    def reduce(self, high, owners):
        poly_tris = sum(MeshArrays.tris(part["mesh"]) for part in self.poly_parts)
        limit = max(500, int((self.budget - poly_tris) * 0.985))
        high.data.calc_loop_triangles()
        areas = np.empty(len(high.data.loop_triangles), np.float32)
        high.data.loop_triangles.foreach_get("area", areas)
        area = float(areas.sum())
        stage_target = int(limit * self.stage_ratio)
        stage, stage_report = self.clean_collapse(high, stage_target, 2.5 * math.sqrt(2.0 * area / max(1, stage_target)), np.zeros(0, np.int64), 1)
        detail_owners = np.array([i for i, o in enumerate(self.owners) if o["detail"]], np.int64)
        if len(detail_owners):
            centres = MeshArrays.polygon_vectors(stage.data, "center")
            share = float(np.isin(self.probe_field.owners(centres), detail_owners).mean())
            if share > self.detail_share:
                self.warnings.append("detail nodes cover {:.0%} of the surface (> {:.0%}); detail density not protected".format(share, self.detail_share))
                detail_owners = np.zeros(0, np.int64)
        low, report = self.clean_collapse(stage, limit, 2.5 * math.sqrt(2.0 * area / max(1, limit)), detail_owners, 3)
        report["role_line_snapped"] = self.snap_role_lines(low.data, high) if self.crisp_roles else 0
        report["role_faces_relabelled"] = self.relabel_faces(low.data) if self.crisp_roles else 0
        report["stage"] = stage_report
        self.discard(stage)
        low.name = self.id
        low.data.name = self.id
        self.clock.mark("reduce")
        return low, report

    def fold_report(self, bm, limit):
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        centres = np.array([f.calc_center_median()[:] for f in bm.faces], np.float32).reshape(-1, 3)
        normals = np.array([f.normal[:] for f in bm.faces], np.float32).reshape(-1, 3)
        areas = np.array([f.calc_area() for f in bm.faces], np.float64)
        surface = self.probe_field.project(centres, self.voxel * 0.5, 2, 4.0 * self.voxel)
        agree = (normals * self.probe_field.normals(surface, self.voxel * 0.5)).sum(axis=1)
        visible = areas > 1e-6
        flipped = np.nonzero((agree < 0.05) & visible)[0]
        folds = [e for e in bm.edges if len(e.link_faces) == 2 and all(visible[f.index] for f in e.link_faces) and math.degrees(e.calc_face_angle(0.0)) > limit and min(agree[f.index] for f in e.link_faces) < 0.5]
        return flipped, folds

    @staticmethod
    def tidy(bm):
        bmesh.ops.dissolve_degenerate(bm, dist=2e-5, edges=bm.edges[:])
        big = [f for f in bm.faces if len(f.verts) > 3]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.normal_update()

    def bad_clusters(self, faces):
        faces = list(faces)
        index = {f: i for i, f in enumerate(faces)}
        parent = list(range(len(faces)))
        for f in faces:
            for v in f.verts:
                for g in v.link_faces:
                    j = index.get(g)
                    if j is None:
                        continue
                    a = index[f]
                    while parent[a] != a:
                        a = parent[a]
                    while parent[j] != j:
                        j = parent[j]
                    if a != j:
                        parent[j] = a
        groups = {}
        for f in faces:
            a = index[f]
            while parent[a] != a:
                a = parent[a]
            groups.setdefault(a, []).append(f)
        small = []
        large = []
        for members in groups.values():
            co = np.array([v.co[:] for f in members for v in f.verts], np.float64)
            size = float(np.linalg.norm(co.max(axis=0) - co.min(axis=0)))
            (small if size <= max(4.0 * self.voxel, 0.012) else large).extend(members)
        return small, large

    def relax(self, verts, iterations=2, weight=0.5):
        verts = [v for v in verts if v.is_valid and v.link_edges]
        if not verts:
            return 0
        for _ in range(int(iterations)):
            co = np.array([v.co[:] for v in verts], np.float32)
            mean = np.array([np.mean([e.other_vert(v).co[:] for e in v.link_edges], axis=0) for v in verts], np.float32)
            moved = self.probe_field.project((1.0 - weight) * co + weight * mean, self.voxel * 0.5, 2)
            for v, p in zip(verts, moved):
                v.co = p.tolist()
        return len(verts)

    def face_agreement(self, faces):
        if not faces:
            return np.zeros(0)
        centres = np.array([f.calc_center_median()[:] for f in faces], np.float32)
        normals = np.array([f.normal[:] for f in faces], np.float32)
        surface = self.probe_field.project(centres, self.voxel * 0.5, 2, 4.0 * self.voxel)
        return (normals * self.probe_field.normals(surface, self.voxel * 0.5)).sum(axis=1)

    def rotate_folds(self, bm, edges):
        pick = []
        used = set()
        for e in edges:
            if not e.is_valid or len(e.link_faces) != 2:
                continue
            pair = tuple(e.link_faces)
            if pair[0] in used or pair[1] in used:
                continue
            used.update(pair)
            pick.append(e)
        if not pick:
            return 0
        quads = [frozenset(v for f in e.link_faces for v in f.verts) for e in pick]
        before = self.face_agreement([f for e in pick for f in e.link_faces]).reshape(-1, 2).min(axis=1)
        score = dict(zip(quads, before.tolist()))
        out = bmesh.ops.rotate_edges(bm, edges=pick, use_ccw=False)
        rotated = [e for e in out.get("edges", []) if e.is_valid and len(e.link_faces) == 2]
        if not rotated:
            return 0
        for e in rotated:
            for f in e.link_faces:
                f.normal_update()
        after = self.face_agreement([f for e in rotated for f in e.link_faces]).reshape(-1, 2).min(axis=1)
        worse = [e for e, a in zip(rotated, after.tolist()) if a <= score.get(frozenset(v for f in e.link_faces for v in f.verts), -2.0)]
        if worse:
            back = bmesh.ops.rotate_edges(bm, edges=worse, use_ccw=True)
            for e in back.get("edges", []):
                for f in e.link_faces:
                    f.normal_update()
        return len(rotated) - len(worse)

    @staticmethod
    def drop_specks(bm, size):
        seen = set()
        doomed = []
        for start in bm.faces:
            if start in seen:
                continue
            seen.add(start)
            stack = [start]
            comp = []
            while stack:
                f = stack.pop()
                comp.append(f)
                for e in f.edges:
                    for g in e.link_faces:
                        if g not in seen:
                            seen.add(g)
                            stack.append(g)
            co = np.array([v.co[:] for f in comp for v in f.verts], np.float64)
            extent = float(np.linalg.norm(co.max(axis=0) - co.min(axis=0)))
            volume = 0.0
            for f in comp:
                vs = [v.co for v in f.verts]
                for k in range(1, len(vs) - 1):
                    volume += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
            if extent < size or volume <= 0.0:
                doomed.extend(comp)
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context="VERTS")
        return len(doomed)

    def repair(self, me, limit=120.0, passes=4):
        merged = 0
        relaxed = 0
        flipped = []
        folds = []
        points = []
        specks = 0
        for step in range(int(passes) + 1):
            bm = bmesh.new()
            bm.from_mesh(me)
            if step == 0:
                specks = SculptBuilder.drop_specks(bm, max(4.0 * self.voxel, 0.015))
            SculptBuilder.tidy(bm)
            flipped, folds = self.fold_report(bm, limit)
            bm.faces.ensure_lookup_table()
            points = [bm.faces[int(i)].calc_center_median()[:] for i in flipped] + [((e.verts[0].co + e.verts[1].co) * 0.5)[:] for e in folds]
            if step == int(passes) or (not len(flipped) and not folds):
                bm.to_mesh(me)
                bm.free()
                break
            faces = {bm.faces[int(i)] for i in flipped}
            for e in folds:
                faces.update(e.link_faces)
            small, large = self.bad_clusters(faces)
            edges = list({e for f in small for e in f.edges})
            verts = list({v for e in edges for v in e.verts})
            fold_edges = [e for e in folds if all(f in large for f in e.link_faces)]
            if edges:
                bmesh.ops.collapse(bm, edges=edges, uvs=False)
            alive = [v for v in verts if v.is_valid]
            merged += len(verts) - len(alive)
            relaxed += self.relax(alive, 1, 0.0)
            relaxed += self.rotate_folds(bm, [e for e in fold_edges if e.is_valid])
            SculptBuilder.tidy(bm)
            bm.to_mesh(me)
            bm.free()
        me.update()
        return {"flipped": int(len(flipped)), "folds": len(folds), "merged_verts": merged, "relaxed_verts": relaxed, "speck_faces": specks}, points

    def refine(self, low):
        me = low.data
        faces, sizes = MeshArrays.faces(me)
        if len(sizes) == 0 or int(sizes.max()) != 3:
            return {"skipped": "not triangles"}
        verts = MeshArrays.vertices(me).astype(np.float64)
        tris = np.ascontiguousarray(faces[:, :3], np.int64)
        mats = MeshArrays.polygon_ints(me, "material_index").astype(np.int64)
        tris, flips = SurfaceRefiner(self.grid_field, self.voxel).flip(verts, tris, mats)
        report = {"flips": int(flips)}
        keep = SurfaceRefiner.dedupe(tris)
        if not keep.all():
            report["dropped_faces"] = int((~keep).sum())
            tris = tris[keep]
            mats = mats[keep]
        new = MeshArrays.build(me.name + "_refined", verts, tris, np.full(len(tris), 3, np.int32))
        if len(new.polygons) != len(tris) or len(new.vertices) != len(verts):
            bpy.data.meshes.remove(new)
            report["rejected"] = True
            return report
        new.polygons.foreach_set("material_index", mats.astype(np.int32))
        for m in me.materials:
            new.materials.append(m)
        name = me.name
        low.data = new
        if me.users == 0:
            bpy.data.meshes.remove(me)
        new.name = name
        MeshArrays.smooth_all(new)
        report["repair"] = self.repair(new)[0]
        self.clock.mark("refine")
        return report

    def transfer_normals(self, low, high):
        MeshArrays.smooth_all(high.data)
        MeshArrays.smooth_all(low.data)
        mod = low.modifiers.new("sf_normals", "DATA_TRANSFER")
        mod.object = high
        mod.use_loop_data = True
        mod.data_types_loops = {"CUSTOM_NORMAL"}
        mod.loop_mapping = "POLYINTERP_NEAREST"
        mod.mix_mode = "REPLACE"
        mod.mix_factor = 1.0
        MeshArrays.apply_modifiers(low)
        self.clock.mark("normals")

    def finish_poly_parts(self):
        made = []
        for part in self.poly_parts:
            me = part["mesh"]
            ob = bpy.data.objects.new(self.id + "_part", me)
            bpy.context.scene.collection.objects.link(ob)
            MeshArrays.smooth_all(me)
            if part["weighted"]:
                wn = ob.modifiers.new("sf_weighted", "WEIGHTED_NORMAL")
                wn.mode = "FACE_AREA"
                wn.weight = 50
                wn.keep_sharp = True
                tri = ob.modifiers.new("sf_tri", "TRIANGULATE")
                tri.quad_method = "BEAUTY"
                tri.ngon_method = "BEAUTY"
                if hasattr(tri, "keep_custom_normals"):
                    tri.keep_custom_normals = True
                MeshArrays.apply_modifiers(ob)
            else:
                MeshArrays.triangulate(me)
            role = self.palette.index(self.owners[part["owner"]]["role"])
            ob.data.attributes.new("sf_role", "INT", "FACE").data.foreach_set("value", np.full(len(ob.data.polygons), role, np.int32))
            ob.data.attributes.new("sf_owner", "INT", "FACE").data.foreach_set("value", np.full(len(ob.data.polygons), part["owner"], np.int32))
            made.append(ob)
        return made

    def join(self, root, parts):
        if not parts:
            return root
        objs = [root] + parts
        with bpy.context.temp_override(active_object=root, object=root, selected_objects=objs, selected_editable_objects=objs):
            bpy.ops.object.join()
        root.data.name = self.id
        return root

    def recentre(self, root, high):
        verts = MeshArrays.vertices(root.data)
        lo = verts.min(axis=0)
        hi = verts.max(axis=0)
        shift = np.array([-(lo[0] + hi[0]) * 0.5, -(lo[1] + hi[1]) * 0.5, -lo[2]], np.float32)
        m = Matrix.Translation(Vector(shift.tolist()))
        root.data.transform(m)
        high.data.transform(m)
        root.data.update()
        self.shift = shift
        return shift

    def poly_bake_source(self, root, roles, face_owner, high):
        owners = [part["owner"] for part in self.poly_parts]
        keep = np.isin(face_owner, owners)
        if not keep.any():
            return None
        me = root.data.copy()
        me.name = self.id + "_polybake"
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep[f.index]], context="FACES")
        bm.to_mesh(me)
        bm.free()
        me.materials.clear()
        for m in high.data.materials:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", np.asarray(roles, np.int32)[keep])
        me.update()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def surface_uvs(self, root, roles, out_dir, high, face_owner):
        me = root.data
        finishes = []
        for role in self.palette.roles:
            fin = self.palette.roles[role]["finish"]
            if fin not in finishes:
                finishes.append(fin)
        role_names = list(self.palette.roles)
        face_finish = np.array([self.palette.roles[role_names[r]]["finish"] for r in roles])
        used = [f for f in ("satin", "matte", "gloss", "emissive") if (face_finish == f).any()]
        if self.atlas:
            extra = self.poly_bake_source(root, roles, face_owner, high)
            image = AtlasBaker.bake(self, root, high, self.atlas, out_dir, [extra] if extra is not None else [])
            if extra is not None:
                self.discard(extra)
            texture = os.path.basename(image.filepath)
        else:
            image = self.palette.image(out_dir)
            texture = os.path.basename(self.palette.path)
            while len(me.uv_layers) > 1:
                me.uv_layers.remove(me.uv_layers[-1])
            layer = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name="UVMap")
            layer.name = "UVMap"
            verts = MeshArrays.vertices(me)
            lo = verts.min(axis=0)
            span = np.maximum(verts.max(axis=0) - lo, 1e-4)
            lv = MeshArrays.loop_vertex(me)
            lf = MeshArrays.loop_face(me)
            boxes = np.array([self.palette.cell_box(r) for r in role_names], np.float64)
            box = boxes[roles[lf]]
            nu = (verts[lv, 0] - lo[0]) / span[0] * 0.6 + (verts[lv, 1] - lo[1]) / span[1] * 0.4
            nv = (verts[lv, 2] - lo[2]) / span[2]
            lo_t = 0.5 - 0.5 * self.uv_spread
            u = box[:, 0] + (lo_t + self.uv_spread * np.clip(nu, 0.0, 1.0)) * (box[:, 2] - box[:, 0])
            v = box[:, 1] + (lo_t + self.uv_spread * np.clip(nv, 0.0, 1.0)) * (box[:, 3] - box[:, 1])
            uv = np.stack([u, v], axis=1).astype(np.float32)
            layer.data.foreach_set("uv", uv.reshape(-1))
        me.uv_layers.active = me.uv_layers[0]
        me.materials.clear()
        slot = {}
        for fin in used:
            slot[fin] = len(me.materials)
            me.materials.append(MaterialFactory.create("{}_{}".format(self.id, fin), image, fin))
        me.polygons.foreach_set("material_index", np.array([slot[f] for f in face_finish], np.int32))
        return texture, used, face_finish == "emissive"

    def vertex_ao(self, root, emissive_faces):
        me = root.data
        verts = MeshArrays.vertices(me).astype(np.float64)
        field_pts = (verts - self.shift).astype(np.float32)
        normals = np.zeros_like(verts)
        np.add.at(normals, MeshArrays.loop_vertex(me), MeshArrays.corner_normals(me).astype(np.float64))
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
        floor = float(field_pts[:, 2].min())
        occ = AmbientOcclusion.occlusion(field_pts.astype(np.float64), normals, self.probe_field, self.ao_distance, floor)
        if self.atlas:
            occ = occ * 0.0
        return AmbientOcclusion.write(me, occ, normals, verts, emissive_faces, self.ao_strength)

    def vertex_bones(self, root, face_owner):
        bone_names = list(self.bones)
        owner_bone = np.array([bone_names.index(o["bone"]) for o in self.owners] + [0], np.int64)
        fb = owner_bone[np.where(face_owner >= 0, face_owner, len(self.owners))]
        lv = MeshArrays.loop_vertex(root.data)
        lf = MeshArrays.loop_face(root.data)
        vb = np.zeros(len(root.data.vertices), np.int64)
        np.maximum.at(vb, lv, fb[lf])
        return vb

    def collider_boxes(self):
        if self.colliders_spec == 0 or self.colliders_spec == []:
            return []
        boxes = list(self.colliders)
        if isinstance(self.colliders_spec, (list, tuple)):
            for c in self.colliders_spec:
                if isinstance(c, dict):
                    boxes.append((Vector(c["center"]), Vector(c["size"])))
                else:
                    boxes.append((Vector(c[0]), Vector(c[1])))
        if not boxes:
            flagged = [o["bounds"] for o in self.owners if o["collide"] and o["bounds"] is not None]
            for lo, hi in flagged:
                boxes.append((Vector(((lo + hi) * 0.5).tolist()), Vector(np.maximum(hi - lo, 0.12).tolist())))
        return boxes

    def build_colliders(self, root):
        boxes = self.collider_boxes()
        if self.colliders_spec in (0, []):
            return []
        if not boxes:
            verts = MeshArrays.vertices(root.data)
            lo = verts.min(axis=0)
            hi = verts.max(axis=0)
            boxes = [(Vector(((lo + hi) * 0.5 - self.shift).tolist()), Vector(np.maximum(hi - lo, 0.12).tolist()))]
        coll = bpy.data.collections.new(self.id + "_collision")
        bpy.context.scene.collection.children.link(coll)
        made = []
        for i, (center, size) in enumerate(boxes):
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=size, verts=bm.verts)
            me = bpy.data.meshes.new("{}_col_{}".format(self.id, i))
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(me.name, me)
            coll.objects.link(ob)
            ob.location = center + Vector(self.shift.tolist())
            ob.display_type = "WIRE"
            ob.hide_render = True
            ob["prop_forge_collision"] = "box"
            made.append(ob)
        return made

    def save_high(self, high, out_dir):
        if not self.keep_high:
            return None
        folder = os.path.join(out_dir, "_high")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, self.id + "_high.blend")
        source = high
        if MeshArrays.tris(high.data) > self.high_tris:
            me = high.data.copy()
            source = bpy.data.objects.new(self.id + "_high", me)
            high.name = self.id + "_high_full"
            source.name = self.id + "_high"
            bpy.context.scene.collection.objects.link(source)
            mod = source.modifiers.new("sf_cap", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = self.high_tris / float(MeshArrays.tris(me))
            mod.use_collapse_triangulate = True
            MeshArrays.apply_modifiers(source)
            MeshArrays.smooth_all(source.data)
        scene = bpy.data.scenes.new(self.id + "_high")
        scene.collection.objects.link(source)
        bpy.data.libraries.write(path, {scene}, path_remap="NONE", compress=True)
        bpy.data.scenes.remove(scene)
        if source is not high:
            data = source.data
            bpy.data.objects.remove(source, do_unlink=True)
            bpy.data.meshes.remove(data)
            high.name = self.id + "_high"
        return path

    def discard(self, ob):
        data = ob.data
        mats = list(data.materials)
        bpy.data.objects.remove(ob, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
        for m in mats:
            if m is not None and m.users == 0:
                bpy.data.materials.remove(m)

    def save_file(self, path, objects, collections):
        if self.reset_scene:
            if bpy.app.background:
                bpy.context.preferences.filepaths.save_version = 0
            bpy.ops.wm.save_as_mainfile(filepath=path, compress=False, relative_remap=True)
            return
        scene = bpy.data.scenes.new(self.id)
        for ob in objects:
            scene.collection.objects.link(ob)
        for coll in collections:
            scene.collection.children.link(coll)
        bpy.data.libraries.write(path, {scene}, path_remap="RELATIVE", compress=False)
        bpy.data.scenes.remove(scene)

    def build(self, out_dir):
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        self.prepare()
        verts, faces, sizes = self.mesh_field()
        verts, roles, owners, moved = self.face_roles(verts, faces, sizes)
        high = self.high_object(verts, faces, sizes, roles)
        high_tris = int((sizes - 2).sum())
        low, folds = self.reduce(high, owners)
        folds["refine"] = self.refine(low)
        self.transfer_normals(low, high)
        low_roles = MeshArrays.polygon_ints(low.data, "material_index")
        low.data.attributes.new("sf_role", "INT", "FACE").data.foreach_set("value", low_roles)
        centres = MeshArrays.polygon_vectors(low.data, "center")
        low.data.attributes.new("sf_owner", "INT", "FACE").data.foreach_set("value", self.probe_field.owners(centres).astype(np.int32))
        parts = self.finish_poly_parts()
        root = self.join(low, parts)
        root.name = self.id
        root.data.name = self.id
        shift = self.recentre(root, high)
        face_role = np.empty(len(root.data.polygons), np.int32)
        root.data.attributes["sf_role"].data.foreach_get("value", face_role)
        face_owner = np.empty(len(root.data.polygons), np.int32)
        root.data.attributes["sf_owner"].data.foreach_get("value", face_owner)
        for name in ("sf_role", "sf_owner"):
            root.data.attributes.remove(root.data.attributes[name])
        texture, finishes, emissive_faces = self.surface_uvs(root, face_role.astype(np.int64), out_dir, high, face_owner)
        ao = self.vertex_ao(root, emissive_faces)
        self.clock.mark("surface")
        anim_meta = None
        rig = None
        if self.target == "prop" and self.anim and len(self.bones) > 1:
            rig, anim_meta = RigBuilder.build(self.id, root, self.bones, self.anim, Vector(shift.tolist()), self.vertex_bones(root, face_owner))
        colliders = self.build_colliders(root) if self.target == "prop" else []
        poly_owners = np.array([part["owner"] for part in self.poly_parts], np.int64)
        metrics = QualityProbe.measure(root.data, self.probe_field, self.voxel, shift, ~np.isin(face_owner, poly_owners))
        metrics["high_tris"] = high_tris
        metrics["boundary_vertices_smoothed"] = moved
        metrics["folds"] = folds
        metrics["color1"] = ao
        self.clock.mark("measure")
        verts_final = MeshArrays.vertices(root.data)
        lo = verts_final.min(axis=0)
        hi = verts_final.max(axis=0)
        if metrics["tris"] > self.budget:
            self.warnings.append("tris {} over budget {}".format(metrics["tris"], self.budget))
        if bpy.app.version[:2] != (4, 2):
            self.warnings.append("saved by Blender {}; rebuild with the 4.2.3 CLI before export_prop".format(bpy.app.version_string))
        meta = {
            "id": self.id,
            "archetype": self.archetype,
            "set": self.set_name,
            "style": self.style,
            "low_poly": False,
            "size_m": [round(float(hi[i] - lo[i]), 3) for i in range(3)],
            "tris": metrics["tris"],
            "budget": self.budget,
            "parts": len(self.owners),
            "materials": [m.name for m in root.data.materials],
            "shaders": [m.get("prop_forge_shader", "") for m in root.data.materials],
            "texture": texture,
            "colliders": len(colliders),
            "lod_dist": self.lod_dist,
            "warnings": list(self.warnings),
        }
        if anim_meta:
            meta["anim"] = anim_meta
        build_info = {
            "version": 1,
            "target": self.target,
            "size_class": self.size_class,
            "voxel": self.voxel,
            "band": round(self.grid_band, 5),
            "iso": self.iso,
            "atlas": self.atlas,
            "ao_distance": self.ao_distance,
            "palette": {"name": self.palette.name, "roles": self.palette.roles, "cell_px": self.palette.cell_px},
            "finishes": finishes,
            "nodes": [{k: v for k, v in o.items() if k != "bounds"} for o in self.owners],
            "shift": [round(float(v), 5) for v in shift],
            "metrics": metrics,
            "timings": dict(self.clock.stages),
            "log": list(self.log),
            "uv_spread": self.uv_spread,
            "blender": bpy.app.version_string,
        }
        high_path = self.save_high(high, out_dir)
        build_info["high_blend"] = os.path.relpath(high_path, out_dir).replace(os.sep, "/") if high_path else None
        build_info["high_object"] = self.id + "_high" if high_path else None
        build_info["normals"] = "transfer"
        build_info["weighted_parts"] = len(self.poly_parts)
        if self.target == "prop":
            root["prop_forge"] = json.dumps(meta)
        root["sculpt_forge"] = json.dumps(build_info)
        self.discard(high)
        try:
            bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        except (AttributeError, TypeError, RuntimeError):
            pass
        blend_path = os.path.join(out_dir, self.id + ".blend")
        keep = [root] + ([rig] if rig is not None else [])
        coll = [bpy.data.collections[self.id + "_collision"]] if colliders else []
        self.save_file(blend_path, keep, coll)
        self.clock.mark("save")
        result = dict(meta)
        result.update({"blend": blend_path, "high_blend": high_path, "metrics": metrics, "timings": dict(self.clock.stages), "target": self.target})
        if self.target == "library":
            card = {"kind": "sculpt_mesh", "blend_path": blend_path, "mesh_name": self.id, "image": os.path.join(out_dir, texture), "uv_rect": [0.0, 0.0, 1.0, 1.0], "scale": 1.0, "est_tris": metrics["tris"], "emissive": False, "transparent": False}
            card_path = os.path.join(out_dir, self.id + "_card.json")
            with open(card_path, "w", encoding="utf-8") as fh:
                json.dump(card, fh, indent=1)
            result["card"] = card_path
        print("SCULPT_PROP " + json.dumps({k: result[k] for k in ("id", "tris", "budget", "blend", "texture", "colliders")}), flush=True)
        return result


class SpecRunner:
    node_types = ("sphere", "ellipsoid", "capsule", "round_cone", "round_box", "pillow_box", "round_cyl", "torus", "lathe", "extrude2d", "tube", "beads", "drips", "scallops", "text", "mesh_part", "cut", "bevel_box")
    prop_keys = ("budget", "size_class", "lod_dist", "colliders", "style", "target", "archetype", "voxel", "default_role", "iso", "ao_distance", "ao_strength", "atlas", "keep_high", "high_tris", "smooth_roles", "font", "stage_ratio", "detail_share", "uv_spread", "crisp_roles")

    @staticmethod
    def load(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def apply(builder, nodes):
        for spec in nodes:
            spec = dict(spec)
            kind = spec.pop("type")
            if kind == "group":
                children = spec.pop("nodes", [])
                with builder.group(spec.get("name", "group"), spec.get("fillet", 0.0), spec.get("op", "union")):
                    SpecRunner.apply(builder, children)
                continue
            if kind not in SpecRunner.node_types:
                raise ValueError("unknown node type {}".format(kind))
            spec.pop("name", None)
            spec.pop("note", None)
            getattr(builder, kind)(**spec)

    @staticmethod
    def builder(spec, prop, palette, overrides=None):
        args = {}
        for source in (spec.get("defaults", {}), prop, overrides or {}):
            for key in SpecRunner.prop_keys:
                if key in source and source[key] is not None:
                    args[key] = source[key]
        if "voxel" not in args and "voxel" in spec:
            args["voxel"] = spec["voxel"]
        b = SculptBuilder(prop["id"], set_name=spec.get("set", "sculpt_set"), palette=palette, **args)
        for bone in prop.get("bones", []):
            b.define_bone(bone["name"], bone["pivot"], bone.get("parent", "root"))
        if prop.get("anim"):
            b.set_anim(**prop["anim"])
        SpecRunner.apply(b, prop.get("nodes", []))
        return b

    @staticmethod
    def roles(nodes, found):
        for spec in nodes:
            if spec.get("type") == "group":
                SpecRunner.roles(spec.get("nodes", []), found)
            elif spec.get("role"):
                found.append(str(spec["role"]))
        return found

    @staticmethod
    def palette(spec):
        palette = SetPalette.from_spec(spec.get("set", "sculpt_set"), spec.get("palette"))
        for prop in spec.get("props", []):
            for role in SpecRunner.roles(prop.get("nodes", []), [prop["default_role"]] if prop.get("default_role") else []):
                palette.ensure(role)
        return palette

    @staticmethod
    def run(spec, out_dir, only=None, overrides=None):
        palette = SpecRunner.palette(spec)
        results = []
        for prop in spec.get("props", []):
            if only and prop["id"] not in only:
                continue
            b = SpecRunner.builder(spec, prop, palette, overrides)
            results.append(b.build(out_dir))
        return results


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--selftest" not in argv:
        return
    out = argv[argv.index("--selftest") + 1] if len(argv) > argv.index("--selftest") + 1 else os.path.join(bpy.app.tempdir, "sculpt_forge_selftest")
    b = SculptBuilder("sf_selftest", budget=3000, size_class="small", palette={"body": "#F4E6D4", "trim": {"color": "#E9A2B6", "finish": "gloss"}}, colliders="auto")
    b.pillow_box((0.5, 0.4, 0.5), radius=0.05, puff=0.02, loc=(0.0, 0.0, 0.25), role="body", collide=True)
    b.torus(0.16, 0.025, loc=(0.0, 0.0, 0.5), role="trim", fillet=0.02)
    b.sphere(0.12, loc=(0.0, 0.0, 0.62), role="trim", fillet=0.03)
    print(json.dumps(b.build(out)["metrics"]))


if __name__ == "__main__":
    main()
