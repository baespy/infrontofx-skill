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
from mathutils import Vector
from mathutils import geometry as mgeometry
from mathutils.bvhtree import BVHTree


class SweepPath:
    @staticmethod
    def array(points):
        p = np.asarray(points, dtype=np.float64)
        if p.ndim == 1:
            p = p.reshape(1, -1)
        if p.shape[1] == 2:
            p = np.hstack([p, np.zeros((len(p), 1))])
        return p[:, :3].copy()

    @staticmethod
    def unit(v):
        v = np.asarray(v, dtype=np.float64)
        return v / max(float(np.linalg.norm(v)), 1e-12)

    @staticmethod
    def smoothstep(e0, e1, x):
        t = np.clip((np.asarray(x, dtype=np.float64) - e0) / max(e1 - e0, 1e-12), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def clean(points, closed=False, eps=1e-7):
        p = SweepPath.array(points)
        if len(p) < 2:
            return p
        keep = np.ones(len(p), dtype=bool)
        keep[1:] = np.linalg.norm(np.diff(p, axis=0), axis=1) > eps
        p = p[keep]
        if closed and len(p) > 2 and np.linalg.norm(p[0] - p[-1]) <= eps:
            p = p[:-1]
        return p

    @staticmethod
    def segments(points, closed=False):
        p = SweepPath.array(points)
        if closed:
            return np.roll(p, -1, axis=0) - p
        return p[1:] - p[:-1]

    @staticmethod
    def cumulative(points, closed=False):
        seg = SweepPath.segments(points, closed)
        return np.concatenate([[0.0], np.cumsum(np.linalg.norm(seg, axis=1))])

    @staticmethod
    def length(points, closed=False):
        return float(SweepPath.cumulative(points, closed)[-1])

    @staticmethod
    def tangents(points, closed=False):
        p = SweepPath.array(points)
        seg = SweepPath.segments(p, closed)
        d = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-12)
        if closed:
            t = d + np.roll(d, 1, axis=0)
        else:
            t = np.empty_like(p)
            t[1:-1] = d[1:] + d[:-1]
            t[0] = d[0]
            t[-1] = d[-1]
            if len(p) > 2:
                e0 = 4.0 * (p[1] - p[0]) - (p[2] - p[0])
                e1 = 4.0 * (p[-1] - p[-2]) - (p[-1] - p[-3])
                if d[0] @ d[1] > 0.9 and e0 @ d[0] > 0.0:
                    t[0] = e0
                if d[-1] @ d[-2] > 0.9 and e1 @ d[-1] > 0.0:
                    t[-1] = e1
        bad = np.linalg.norm(t, axis=1) < 1e-9
        if np.any(bad):
            t[bad] = d[np.minimum(np.nonzero(bad)[0], len(d) - 1)]
        return t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)

    @staticmethod
    def turns(points, closed=False):
        p = SweepPath.array(points)
        seg = SweepPath.segments(p, closed)
        d = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-12)
        out = np.zeros(len(p))
        if closed:
            out[:] = np.arccos(np.clip((np.roll(d, 1, axis=0) * d).sum(axis=1), -1.0, 1.0))
        elif len(p) > 2:
            out[1:-1] = np.arccos(np.clip((d[:-1] * d[1:]).sum(axis=1), -1.0, 1.0))
        return out

    @staticmethod
    def catmull_rom(points, closed=False, alpha=0.5, step=0.01, z=None):
        p = SweepPath.clean(points, closed)
        if z is not None:
            p[:, 2] = z
        n = len(p)
        if n < 3:
            return p
        if closed:
            ext = np.vstack([p[-1:], p, p[:2]])
            spans = n
        else:
            ext = np.vstack([2.0 * p[0] - p[1], p, 2.0 * p[-1] - p[-2]])
            spans = n - 1
        out = []
        for i in range(spans):
            p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
            t0 = 0.0
            t1 = t0 + max(np.linalg.norm(p1 - p0) ** alpha, 1e-9)
            t2 = t1 + max(np.linalg.norm(p2 - p1) ** alpha, 1e-9)
            t3 = t2 + max(np.linalg.norm(p3 - p2) ** alpha, 1e-9)
            k = max(4, int(math.ceil(np.linalg.norm(p2 - p1) / max(step, 1e-5))))
            t = np.linspace(t1, t2, k, endpoint=False)[:, None]
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
        if not closed:
            out.append(p[-1:])
        return np.vstack(out)

    @staticmethod
    def bezier(anchors, handles_out, handles_in, closed=False, step=0.01):
        a = SweepPath.array(anchors)
        ho = SweepPath.array(handles_out)
        hi = SweepPath.array(handles_in)
        n = len(a)
        spans = n if closed else n - 1
        out = []
        for i in range(spans):
            j = (i + 1) % n
            p0, p1, p2, p3 = a[i], ho[i], hi[j], a[j]
            approx = np.linalg.norm(p1 - p0) + np.linalg.norm(p2 - p1) + np.linalg.norm(p3 - p2)
            k = max(4, int(math.ceil(approx / max(step, 1e-5))))
            t = np.linspace(0.0, 1.0, k, endpoint=False)[:, None]
            mt = 1.0 - t
            out.append(mt ** 3 * p0 + 3.0 * mt * mt * t * p1 + 3.0 * mt * t * t * p2 + t ** 3 * p3)
        if not closed:
            out.append(a[-1:])
        return np.vstack(out)

    @staticmethod
    def line(p0, p1, step=0.05):
        a = SweepPath.array([p0])[0]
        b = SweepPath.array([p1])[0]
        k = max(1, int(math.ceil(np.linalg.norm(b - a) / max(step, 1e-5))))
        t = np.linspace(0.0, 1.0, k + 1)[:, None]
        return a + (b - a) * t

    @staticmethod
    def arc(center, radius, start_deg, end_deg, z=None, step_deg=0.25):
        c = SweepPath.array([center])[0]
        zz = c[2] if z is None else float(z)
        span = end_deg - start_deg
        k = max(2, int(math.ceil(abs(span) / max(step_deg, 1e-3))))
        a = np.radians(np.linspace(start_deg, end_deg, k + 1))
        return np.stack([c[0] + radius * np.cos(a), c[1] + radius * np.sin(a), np.full(len(a), zz)], axis=1)

    @staticmethod
    def rounded_rect(center, width, depth, radius, z=None, step_deg=0.5):
        c = SweepPath.array([center])[0]
        zz = c[2] if z is None else float(z)
        r = max(1e-4, min(radius, width * 0.5 - 1e-4, depth * 0.5 - 1e-4))
        hx, hy = width * 0.5 - r, depth * 0.5 - r
        out = []
        for cx, cy, a0 in ((hx, -hy, -90.0), (hx, hy, 0.0), (-hx, hy, 90.0), (-hx, -hy, 180.0)):
            out.append(SweepPath.arc((c[0] + cx, c[1] + cy, zz), r, a0, a0 + 90.0, zz, step_deg))
        return SweepPath.clean(np.vstack(out), closed=True)

    @staticmethod
    def blob(points, z=None, step=0.01, alpha=0.5):
        p = SweepPath.array(points)
        if z is not None:
            p[:, 2] = z
        return SweepPath.ccw(SweepPath.clean(SweepPath.catmull_rom(p, True, alpha, step), closed=True))

    @staticmethod
    def blob_radial(center, radii, start_deg=0.0, z=None, step=0.01):
        c = SweepPath.array([center])[0]
        zz = c[2] if z is None else float(z)
        r = np.asarray(radii, dtype=np.float64)
        a = np.radians(start_deg) + np.linspace(0.0, 2.0 * math.pi, len(r), endpoint=False)
        pts = np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a), np.full(len(r), zz)], axis=1)
        return SweepPath.blob(pts, zz, step)

    @staticmethod
    def radial(center, radius_fn, z=None, step=0.02):
        c = SweepPath.array([center])[0]
        zz = c[2] if z is None else float(z)
        probe = np.linspace(0.0, 2.0 * math.pi, 361)[:-1]
        rmax = max(float(radius_fn(a)) for a in probe)
        n = max(64, int(math.ceil(2.0 * math.pi * rmax / max(step, 1e-4))))
        a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
        r = np.array([float(radius_fn(t)) for t in a])
        return SweepPath.ccw(np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a), np.full(n, zz)], axis=1))

    @staticmethod
    def area2d(points):
        p = SweepPath.array(points)
        x, y = p[:, 0], p[:, 1]
        return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    @staticmethod
    def ccw(points):
        p = SweepPath.array(points)
        return p if SweepPath.area2d(p) >= 0.0 else p[::-1].copy()

    @staticmethod
    def lifted(points, z=None, dz=0.0):
        p = SweepPath.array(points)
        if z is not None:
            p[:, 2] = z
        p[:, 2] += dz
        return p

    @staticmethod
    def transform2d(points, angle_deg=0.0, offset=(0.0, 0.0, 0.0)):
        p = SweepPath.array(points)
        a = math.radians(angle_deg)
        c, s = math.cos(a), math.sin(a)
        o = SweepPath.array([offset])[0]
        return np.stack([p[:, 0] * c - p[:, 1] * s + o[0], p[:, 0] * s + p[:, 1] * c + o[1], p[:, 2] + o[2]], axis=1)

    @staticmethod
    def concat(*paths):
        out = []
        for path in paths:
            p = SweepPath.array(path)
            if out and np.linalg.norm(out[-1][-1] - p[0]) < 1e-6:
                p = p[1:]
            if len(p):
                out.append(p)
        return np.vstack(out)

    @staticmethod
    def extend(points, d0, d1):
        p = SweepPath.array(points)
        t0 = SweepPath.unit(p[1] - p[0])
        t1 = SweepPath.unit(p[-1] - p[-2])
        out = []
        if d0 > 0.0:
            out.append((p[0] - t0 * d0)[None])
        out.append(p)
        if d1 > 0.0:
            out.append((p[-1] + t1 * d1)[None])
        return np.vstack(out)

    @staticmethod
    def offset(points, distance, closed=True, z=None):
        p = SweepPath.clean(points, closed)
        seg = SweepPath.segments(p, closed)[:, :2]
        d = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-12)
        nr = np.stack([d[:, 1], -d[:, 0]], axis=1)
        if closed:
            n_prev, n_next = np.roll(nr, 1, axis=0), nr
        else:
            n_prev = np.vstack([nr[:1], nr])
            n_next = np.vstack([nr, nr[-1:]])
        m = n_prev + n_next
        m /= np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)
        cos_half = np.clip((m * n_next).sum(axis=1), 0.35, 1.0)
        q = p.copy()
        q[:, :2] += m * (distance / cos_half)[:, None]
        for _ in range(6):
            old = SweepPath.segments(p, closed)[:, :2]
            new = SweepPath.segments(q, closed)[:, :2]
            flip = (old * new).sum(axis=1) <= 0.0
            if not np.any(flip):
                break
            drop = np.zeros(len(q), dtype=bool)
            idx = np.nonzero(flip)[0]
            drop[(idx + 1) % len(q) if closed else np.minimum(idx + 1, len(q) - 2)] = True
            p, q = p[~drop], q[~drop]
        if z is not None:
            q[:, 2] = z
        return q

    @staticmethod
    def sector(points, center, start_deg, end_deg):
        p = SweepPath.ccw(SweepPath.clean(points, closed=True))
        c = SweepPath.array([center])[0]
        span = (end_deg - start_deg) % 360.0 or 360.0
        rel = (np.degrees(np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0])) - start_deg) % 360.0
        n = len(p)
        first = int(np.argmin(rel))
        prev = (first - 1) % n
        gap = (360.0 - rel[prev]) + rel[first]
        f = (360.0 - rel[prev]) / max(gap, 1e-12)
        out = [p[prev] + (p[first] - p[prev]) * f]
        i = first
        for _ in range(n):
            if rel[i] > span:
                last = (i - 1) % n
                g = rel[i] - rel[last]
                f = (span - rel[last]) / max(g, 1e-12)
                out.append(p[last] + (p[i] - p[last]) * f)
                break
            out.append(p[i])
            i = (i + 1) % n
        return SweepPath.clean(np.array(out))

    @staticmethod
    def point_at(points, s, closed=False):
        p = SweepPath.array(points)
        if closed:
            p = np.vstack([p, p[:1]])
        cum = SweepPath.cumulative(p)
        s = float(np.clip(s, 0.0, cum[-1]))
        k = int(np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(p) - 2))
        seg = p[k + 1] - p[k]
        f = (s - cum[k]) / max(cum[k + 1] - cum[k], 1e-12)
        return p[k] + seg * f, seg / max(np.linalg.norm(seg), 1e-12)

    @staticmethod
    def trim(points, s0, s1):
        p = SweepPath.array(points)
        cum = SweepPath.cumulative(p)
        s0, s1 = max(0.0, s0), min(cum[-1], s1)
        a, _ = SweepPath.point_at(p, s0)
        b, _ = SweepPath.point_at(p, s1)
        inner = p[(cum > s0 + 1e-9) & (cum < s1 - 1e-9)]
        return np.vstack([a[None], inner, b[None]])

    @staticmethod
    def resample(points, closed=False, max_turn_deg=5.0, max_len=1.0, max_sagitta=None, corner_deg=25.0, min_segments=1):
        p = SweepPath.clean(points, closed)
        n = len(p)
        if n < 2:
            return p
        if n == 2:
            k = max(min_segments, int(math.ceil(np.linalg.norm(p[1] - p[0]) / max(max_len, 1e-6) - 1e-9)))
            t = np.linspace(0.0, 1.0, k + 1)[:, None]
            return p[0] + (p[1] - p[0]) * t
        seg = SweepPath.segments(p, closed)
        slen = np.maximum(np.linalg.norm(seg, axis=1), 1e-12)
        turn = SweepPath.turns(p, closed)
        corner = turn > math.radians(corner_deg)
        smooth_turn = np.where(corner, 0.0, turn)
        nseg = len(seg)
        start_turn = smooth_turn[np.arange(nseg)]
        end_turn = smooth_turn[(np.arange(nseg) + 1) % n]
        half = 0.5 * (start_turn + end_turn)
        cost = np.maximum(half / math.radians(max_turn_deg), slen / max(max_len, 1e-6))
        if max_sagitta:
            kappa = half / slen
            allow = np.sqrt(8.0 * max_sagitta / np.maximum(kappa, 1e-12))
            cost = np.maximum(cost, slen / allow)
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
            need = 3 if (closed and len(bounds) == 2) else min_segments
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

    @staticmethod
    def frames(points, closed=False, up=(0.0, 0.0, 1.0)):
        p = SweepPath.array(points)
        t = SweepPath.tangents(p, closed)
        if isinstance(up, str):
            return SweepPath.rmf(p, t, closed)
        u0 = np.asarray(up, dtype=np.float64)
        u = u0[None, :] - (t @ u0)[:, None] * t
        norm = np.linalg.norm(u, axis=1)
        for i in range(len(u)):
            if norm[i] < 1e-6:
                u[i] = u[i - 1] if i > 0 else np.cross(t[i], np.array([1.0, 0.0, 0.0]))
        u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-12)
        s = np.cross(t, u)
        s /= np.maximum(np.linalg.norm(s, axis=1, keepdims=True), 1e-12)
        u = np.cross(s, t)
        return t, s, u

    @staticmethod
    def rmf(p, t, closed):
        n = len(p)
        z = np.array([0.0, 0.0, 1.0])
        r0 = z - (t[0] @ z) * t[0]
        if np.linalg.norm(r0) < 1e-6:
            r0 = np.cross(t[0], np.array([1.0, 0.0, 0.0]))
        r = np.zeros_like(p)
        r[0] = r0 / np.linalg.norm(r0)
        steps = n if closed else n - 1
        rr = r[0]
        out_last = None
        for i in range(steps):
            j = (i + 1) % n
            v1 = p[j] - p[i]
            c1 = max(v1 @ v1, 1e-18)
            rl = rr - (2.0 / c1) * (v1 @ rr) * v1
            tl = t[i] - (2.0 / c1) * (v1 @ t[i]) * v1
            v2 = t[j] - tl
            c2 = v2 @ v2
            rr = rl - (2.0 / c2) * (v2 @ rl) * v2 if c2 > 1e-18 else rl
            rr /= max(np.linalg.norm(rr), 1e-12)
            if j == 0:
                out_last = rr
            else:
                r[j] = rr
        if closed and out_last is not None:
            ang = math.atan2(np.cross(out_last, r[0]) @ t[0], out_last @ r[0])
            s_cum = SweepPath.cumulative(p, True)
            for i in range(1, n):
                a = ang * s_cum[i] / s_cum[-1]
                k = t[i]
                v = r[i]
                r[i] = v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1.0 - math.cos(a))
        s = np.cross(t, r)
        s /= np.maximum(np.linalg.norm(s, axis=1, keepdims=True), 1e-12)
        u = np.cross(s, t)
        return t, s, u

    @staticmethod
    def arc_segments(radius, angle_rad, sagitta=0.003, min_count=1, max_count=64):
        if radius <= 1e-9 or angle_rad <= 1e-9:
            return max(1, min_count)
        c = 1.0 - min(sagitta / radius, 1.0)
        step = 2.0 * math.acos(max(-1.0, min(1.0, c)))
        k = int(math.ceil(angle_rad / max(step, 1e-6) - 1e-9))
        return int(max(min_count, min(max_count, k)))

    @staticmethod
    def arch_curve(center, axis, half_span, height, z_start, step=0.01):
        c = SweepPath.array([center])[0]
        ax = SweepPath.unit(np.array([axis[0], axis[1], 0.0]))
        r = float(half_span)
        zs = float(height) - r
        if zs > z_start + 1e-6:
            left = np.stack([np.full(2, -r), np.array([z_start, zs])], axis=1)
            a = np.radians(np.linspace(180.0, 0.0, max(8, int(math.ceil(180.0 / 0.25))) + 1))
            top = np.stack([r * np.cos(a), zs + r * np.sin(a)], axis=1)
            right = np.stack([np.full(2, r), np.array([zs, z_start])], axis=1)
            local = np.vstack([left[:1], SweepPath.line(np.append(left[0], 0.0), np.append(left[1], 0.0), step)[1:-1, :2], top, SweepPath.line(np.append(right[0], 0.0), np.append(right[1], 0.0), step)[1:, :2]])
        else:
            h = float(height) - z_start
            big = (r * r + h * h) / (2.0 * h)
            zc = float(height) - big
            a0 = math.degrees(math.atan2(z_start - zc, -r))
            a1 = math.degrees(math.atan2(z_start - zc, r))
            a = np.radians(np.linspace(a0, a1, max(8, int(math.ceil(abs(a0 - a1) / 0.25))) + 1))
            local = np.stack([big * np.cos(a), zc + big * np.sin(a)], axis=1)
        xy = c[None, :2] + local[:, :1] * ax[None, :2]
        return SweepPath.clean(np.stack([xy[:, 0], xy[:, 1], local[:, 1]], axis=1))

    @staticmethod
    def inside(points2d, polygon2d):
        q = np.asarray(points2d, dtype=np.float64)[:, :2]
        poly = np.asarray(polygon2d, dtype=np.float64)[:, :2]
        x, y = q[:, 0][:, None], q[:, 1][:, None]
        x0, y0 = poly[:, 0][None, :], poly[:, 1][None, :]
        x1, y1 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
        cond = (y0 > y) != (y1 > y)
        xin = x0 + (y - y0) * (x1 - x0) / np.where(np.abs(y1 - y0) < 1e-15, 1e-15, y1 - y0)
        return (np.sum(cond & (x < xin), axis=1) % 2) == 1

    @staticmethod
    def distance_to(points2d, polyline2d, closed=True):
        q = np.asarray(points2d, dtype=np.float64)[:, :2]
        poly = np.asarray(polyline2d, dtype=np.float64)[:, :2]
        a = poly if closed else poly[:-1]
        b = np.roll(poly, -1, axis=0) if closed else poly[1:]
        best = np.full(len(q), np.inf)
        for k in range(0, len(a), 256):
            aa, bb = a[k:k + 256][None], b[k:k + 256][None]
            ab = bb - aa
            t = np.clip(((q[:, None, :] - aa) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-18), 0.0, 1.0)
            d = np.linalg.norm(q[:, None, :] - (aa + ab * t[..., None]), axis=-1)
            best = np.minimum(best, d.min(axis=1))
        return best


class SweepProfile:
    def __init__(self, points, radii=0.0, closed=True, roles=None, corner_roles=None, name="profile", segments=None):
        self.points = np.asarray(points, dtype=np.float64)[:, :2].copy()
        k = len(self.points)
        self.radii = np.broadcast_to(np.asarray(radii, dtype=np.float64), (k,)).copy()
        self.closed = bool(closed)
        edges = k if self.closed else k - 1
        self.roles = list(roles) if roles is not None else [None] * edges
        self.corner_roles = list(corner_roles) if corner_roles is not None else [None] * k
        self.segments = list(segments) if isinstance(segments, (list, tuple)) else [segments] * k
        self.name = name

    @staticmethod
    def custom(points, radii=0.0, closed=True, role=None, segments=None, name="custom"):
        k = len(points)
        edges = k if closed else k - 1
        return SweepProfile(points, radii, closed, [role] * edges, [role] * k, name, segments)

    @staticmethod
    def round(radius, center=(0.0, 0.0), role=None, segments=None):
        cx, cy = center
        r = float(radius)
        pts = [(cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx - r, cy - r)]
        return SweepProfile(pts, r, True, [role] * 4, [role] * 4, "round", segments)

    @staticmethod
    def half_round(radius, base=0.0, role=None, segments=None):
        r = float(radius)
        pts = [(-r, base), (r, base), (r, base + r), (-r, base + r)]
        return SweepProfile(pts, [0.0, 0.0, r, r], True, [role] * 4, [role] * 4, "half_round", segments)

    @staticmethod
    def rounded_rect(width, height, radius, center=(0.0, 0.0), role=None, segments=None):
        cx, cy = center
        w, h = width * 0.5, height * 0.5
        pts = [(cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h), (cx - w, cy - h)]
        return SweepProfile(pts, radius, True, [role] * 4, [role] * 4, "rounded_rect", segments)

    @staticmethod
    def bullnose_curb(width, height, front_radius, back_radius=0.01, anchor=0.5, role=None, segments=None):
        x0 = -width * anchor
        pts = [(x0, 0.0), (x0 + width, 0.0), (x0 + width, height), (x0, height)]
        return SweepProfile(pts, [0.0, 0.0, front_radius, back_radius], True, [role] * 4, [role] * 4, "bullnose_curb", segments)

    @staticmethod
    def handrail(width, height, bottom_radius=None, role=None, segments=None):
        w, h = width * 0.5, height * 0.5
        rb = width * 0.22 if bottom_radius is None else bottom_radius
        pts = [(-w, -h), (w, -h), (w, h), (-w, h)]
        return SweepProfile(pts, [rb, rb, w, w], True, [role] * 4, [role] * 4, "handrail", segments)

    @staticmethod
    def band(width, height=0.003, embed=0.004, face="up", role=None):
        w = width * 0.5
        if face == "up":
            pts = [(-w, -embed), (w, -embed), (w, height), (-w, height)]
        elif face == "in":
            pts = [(-height, -w), (embed, -w), (embed, w), (-height, w)]
        else:
            pts = [(-embed, -w), (height, -w), (height, w), (-embed, w)]
        return SweepProfile(pts, 0.0, True, [role] * 4, [role] * 4, "band")

    @staticmethod
    def slab_edge(thickness, top_radius, bottom_radius=0.0, role=None, bottom_role=None, top_segments=None):
        rt = max(float(top_radius), 0.0)
        rb = max(float(bottom_radius), 0.0)
        inset = max(rb * 1.15 + 0.01, min(0.12, thickness * 0.5))
        top = rt * 1.15 + 0.02
        pts = [(-inset, -thickness), (0.0, -thickness), (0.0, 0.0), (-top, 0.0)]
        return SweepProfile(pts, [0.0, rb, rt, 0.0], False, [bottom_role or role, role, role], [role] * 4, "slab_edge", [None, None, top_segments, None])

    @staticmethod
    def stairs(steps, rise, run, nosing_radius, top_z=0.0, back=0.3, embed=0.02, top_nosing=False, role=None, nose_role=None, nose_segments=4):
        n = max(2, int(steps))
        x_last = (n - 1) * run
        z_b = top_z - n * rise - embed
        pts = [(-back, z_b), (x_last, z_b)]
        rad = [0.0, 0.0]
        for k in range(n - 1, 0, -1):
            zk = top_z - k * rise
            pts.append((k * run, zk))
            rad.append(nosing_radius)
            pts.append(((k - 1) * run, zk))
            rad.append(0.0)
        if top_nosing:
            pts.append((0.0, top_z))
            rad.append(nosing_radius)
            pts.append((-back, top_z))
            rad.append(0.0)
        else:
            pts[-1] = (-back, top_z - rise)
        corner_roles = [(nose_role or role) if r > 0.0 else role for r in rad]
        segs = [nose_segments if r > 0.0 else None for r in rad]
        return SweepProfile(pts, rad, True, [role] * len(pts), corner_roles, "stairs", segs)

    def with_radius(self, index, radius):
        r = self.radii.copy()
        r[index] = radius
        return SweepProfile(self.points, r, self.closed, self.roles, self.corner_roles, self.name, self.segments)

    def mirrored_x(self, pivot=0.0):
        pts = self.points.copy()
        pts[:, 0] = 2.0 * pivot - pts[:, 0]
        k = len(pts)
        if self.closed:
            order = [0] + list(range(k - 1, 0, -1))
            edge_roles = [self.roles[(i - 1) % k] for i in order]
        else:
            order = list(range(k - 1, -1, -1))
            edge_roles = list(reversed(self.roles))
        return SweepProfile(pts[order], self.radii[order], self.closed, edge_roles, [self.corner_roles[i] for i in order], self.name, [self.segments[i] for i in order])

    def shifted(self, dx=0.0, dy=0.0):
        return SweepProfile(self.points + np.array([dx, dy]), self.radii, self.closed, self.roles, self.corner_roles, self.name, self.segments)

    def max_radius(self):
        return float(self.radii.max()) if len(self.radii) else 0.0

    def corners(self):
        p = self.points
        k = len(p)
        info = []
        for i in range(k):
            info.append({"arc": False, "sharp": False, "t": 0.0, "phi": 0.0})
            if not self.closed and (i == 0 or i == k - 1):
                continue
            d1 = p[i] - p[i - 1]
            d2 = p[(i + 1) % k] - p[i]
            l1, l2 = np.linalg.norm(d1), np.linalg.norm(d2)
            if l1 < 1e-12 or l2 < 1e-12:
                continue
            d1, d2 = d1 / l1, d2 / l2
            cross = d1[0] * d2[1] - d1[1] * d2[0]
            phi = math.atan2(abs(cross), float(d1 @ d2))
            info[i].update({"phi": phi, "left": cross > 0.0, "d1": d1, "d2": d2, "sharp": phi > 1e-3})
            if self.radii[i] > 0.0 and phi > 1e-4:
                info[i]["t"] = self.radii[i] * math.tan(phi * 0.5)
        edges = k if self.closed else k - 1
        scale = np.ones(k)
        for e in range(edges):
            a, b = e, (e + 1) % k
            length = float(np.linalg.norm(p[b] - p[a]))
            s = info[a]["t"] + info[b]["t"]
            if s > length + 1e-12:
                f = length / s
                scale[a] = min(scale[a], f)
                scale[b] = min(scale[b], f)
        for i in range(k):
            c = info[i]
            if c["t"] <= 0.0:
                continue
            t = c["t"] * scale[i]
            r = t / math.tan(c["phi"] * 0.5)
            d1 = c["d1"]
            n1 = np.array([-d1[1], d1[0]]) if c["left"] else np.array([d1[1], -d1[0]])
            entry = p[i] - d1 * t
            centre = entry + n1 * r
            a0 = math.atan2(entry[1] - centre[1], entry[0] - centre[0])
            c.update({"arc": True, "sharp": False, "r": r, "centre": centre, "a0": a0, "dir": 1.0 if c["left"] else -1.0})
        return info

    def push(self, pts, sharp, roles, q, is_sharp, role):
        if pts and np.linalg.norm(pts[-1] - q) < 1e-9:
            sharp[-1] = sharp[-1] or is_sharp
            return
        if pts:
            roles.append(role)
        pts.append(np.asarray(q, dtype=np.float64))
        sharp.append(bool(is_sharp))

    def sample(self, count_fn, counts=None):
        p = self.points
        k = len(p)
        info = self.corners()
        pts, sharp, roles, used = [], [], [], []
        for i in range(k):
            c = info[i]
            incoming = self.roles[(i - 1) % k] if (self.closed or i > 0) else None
            if c["arc"]:
                n = counts[len(used)] if counts is not None else max(1, int(count_fn(c["r"], c["phi"], self.segments[i])))
                used.append(n)
                ang = c["a0"] + c["dir"] * c["phi"] * np.linspace(0.0, 1.0, n + 1)
                arc = c["centre"][None, :] + c["r"] * np.stack([np.cos(ang), np.sin(ang)], axis=1)
                corner_role = self.corner_roles[i] if self.corner_roles[i] is not None else incoming
                for j, q in enumerate(arc):
                    self.push(pts, sharp, roles, q, False, incoming if j == 0 else corner_role)
            else:
                self.push(pts, sharp, roles, p[i], c["sharp"], incoming)
        if self.closed:
            if len(pts) > 2 and np.linalg.norm(pts[-1] - pts[0]) < 1e-9:
                sharp[0] = sharp[0] or sharp[-1]
                pts.pop()
                sharp.pop()
            else:
                roles.append(self.roles[k - 1])
        return np.array(pts), roles, np.array(sharp, dtype=bool), used


class SweepMesh:
    def __init__(self, name="mesh"):
        self.name = name
        self.verts = []
        self.count = 0
        self.chunks = []
        self.sharp = []

    def add_verts(self, arr):
        a = np.asarray(arr, dtype=np.float64).reshape(-1, 3)
        base = self.count
        self.verts.append(a)
        self.count += len(a)
        return base

    def add_faces(self, idx, roles, uvs=None, period=(0.0, 0.0)):
        idx = np.asarray(idx, dtype=np.int64)
        if idx.ndim == 1:
            idx = idx[None, :]
        if len(idx) == 0:
            return
        roles = list(roles) if isinstance(roles, (list, tuple, np.ndarray)) else [roles] * len(idx)
        uv = np.zeros(idx.shape + (2,)) if uvs is None else np.asarray(uvs, dtype=np.float64).reshape(idx.shape + (2,))
        self.chunks.append((idx, roles, uv, (float(period[0] or 0.0), float(period[1] or 0.0))))

    def add_sharp(self, pairs):
        p = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
        if len(p):
            self.sharp.append(p)

    def tri_count(self):
        return int(sum((c[0].shape[1] - 2) * len(c[0]) for c in self.chunks))

    def positions(self):
        return np.vstack(self.verts) if self.verts else np.zeros((0, 3))

    def add_rings(self, grid, closed_path, closed_prof, seg_roles, sharp_pts, flip=False):
        n, m = grid.shape[0], grid.shape[1]
        base = self.add_verts(grid.reshape(-1, 3))
        idx = base + np.arange(n * m).reshape(n, m)
        rows = np.concatenate([grid, grid[:1]], axis=0) if closed_path else grid
        u = np.concatenate([np.zeros((1, m)), np.cumsum(np.linalg.norm(np.diff(rows, axis=0), axis=-1), axis=0)], axis=0)
        pu = 0.0
        if closed_path:
            lref = float(u[-1].mean())
            u = u * (lref / np.maximum(u[-1:], 1e-9))
            pu = lref
        cols = np.concatenate([grid, grid[:, :1]], axis=1) if closed_prof else grid
        v = np.concatenate([np.zeros((n, 1)), np.cumsum(np.linalg.norm(np.diff(cols, axis=1), axis=-1), axis=1)], axis=1)
        pv = float(v[:, -1].mean()) if closed_prof else 0.0
        ni = n if closed_path else n - 1
        mj = m if closed_prof else m - 1
        if ni <= 0 or mj <= 0:
            return idx, u, v
        ii, jj = np.meshgrid(np.arange(ni), np.arange(mj), indexing="ij")
        i1, j1 = (ii + 1) % n, (jj + 1) % m
        a, b, c, d = idx[ii, jj], idx[i1, jj], idx[i1, j1], idx[ii, j1]
        uva = np.stack([u[ii, jj], v[ii, jj]], -1)
        uvb = np.stack([u[ii + 1, jj], v[i1, jj]], -1)
        uvc = np.stack([u[ii + 1, j1], v[i1, jj + 1]], -1)
        uvd = np.stack([u[ii, j1], v[ii, jj + 1]], -1)
        if flip:
            quads = np.stack([a, d, c, b], -1).reshape(-1, 4)
            uvs = np.stack([uva, uvd, uvc, uvb], -2).reshape(-1, 4, 2)
        else:
            quads = np.stack([a, b, c, d], -1).reshape(-1, 4)
            uvs = np.stack([uva, uvb, uvc, uvd], -2).reshape(-1, 4, 2)
        roles = np.asarray(seg_roles, dtype=object)[jj].reshape(-1).tolist()
        self.add_faces(quads, roles, uvs, (pu, pv))
        for j in np.nonzero(np.asarray(sharp_pts, dtype=bool))[0]:
            self.add_sharp(np.stack([idx[np.arange(ni), j], idx[(np.arange(ni) + 1) % n, j]], -1))
        return idx, u, v

    def add_cap(self, ids, uvs, role, sharp=True):
        ids = np.asarray(ids, dtype=np.int64)
        self.add_faces(ids[None, :], [role], np.asarray(uvs, dtype=np.float64)[None, :, :2])
        if sharp:
            self.add_sharp(np.stack([ids, np.roll(ids, -1)], -1))

    def add_fan(self, apex, ring, apex_uv, ring_uv, role, reverse=False):
        ring = np.asarray(ring, dtype=np.int64)
        k = len(ring)
        j = np.arange(k)
        j1 = (j + 1) % k
        ruv = np.asarray(ring_uv, dtype=np.float64)
        uv1 = ruv[j + 1] if ruv.shape[0] == k + 1 else ruv[j1]
        auv = np.broadcast_to(np.asarray(apex_uv, dtype=np.float64), (k, 2))
        if reverse:
            tris = np.stack([np.full(k, apex), ring[j1], ring[j]], -1)
            uvs = np.stack([auv, uv1, ruv[j]], -2)
        else:
            tris = np.stack([np.full(k, apex), ring[j], ring[j1]], -1)
            uvs = np.stack([auv, ruv[j], uv1], -2)
        self.add_faces(tris, [role] * k, uvs)

    def add_cdt(self, ids, xy, z, up=True, spacing=None, role=None):
        ids = np.asarray(ids, dtype=np.int64)
        pts = np.asarray(xy, dtype=np.float64)[:, :2]
        k = len(pts)
        extra = np.zeros((0, 2))
        if spacing:
            lo, hi = pts.min(axis=0), pts.max(axis=0)
            gx = np.arange(lo[0] + spacing * 0.5, hi[0], spacing)
            gy = np.arange(lo[1] + spacing * 0.5, hi[1], spacing)
            if len(gx) and len(gy):
                g = np.stack(np.meshgrid(gx, gy, indexing="ij"), -1).reshape(-1, 2)
                g = g[SweepPath.inside(g, pts)]
                if len(g):
                    g = g[SweepPath.distance_to(g, pts, True) > spacing * 0.55]
                extra = g
        coords = [Vector((float(p[0]), float(p[1]))) for p in np.vstack([pts, extra])]
        res = mgeometry.delaunay_2d_cdt(coords, [], [list(range(k))], 1, 1e-7, True)
        vo, fo, ov = res[0], res[2], res[3]
        mapping = np.full(len(vo), -1, dtype=np.int64)
        new_xy = []
        for o in range(len(vo)):
            orig = ov[o]
            if orig and orig[0] < k:
                mapping[o] = ids[orig[0]]
            else:
                new_xy.append((o, float(vo[o][0]), float(vo[o][1])))
        if new_xy:
            base = self.add_verts(np.array([[x, y, z] for _, x, y in new_xy]))
            for n_i, item in enumerate(new_xy):
                mapping[item[0]] = base + n_i
        tris, uvs = [], []
        for f in fo:
            if len(f) != 3:
                continue
            a, b, c = (np.array([vo[i][0], vo[i][1]]) for i in f)
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            order = list(f) if (area > 0.0) == up else [f[0], f[2], f[1]]
            tris.append([mapping[i] for i in order])
            uvs.append([[vo[i][0], vo[i][1]] for i in order])
        if tris:
            self.add_faces(np.array(tris, dtype=np.int64), [role] * len(tris), np.array(uvs))

    @staticmethod
    def fit_tile(period, tile):
        if not period or tile <= 0.0:
            return tile
        return period / max(1.0, round(period / tile))

    def to_mesh(self, name=None, uv_name="UVMap 0", role_uv=None, smooth=True):
        name = name or self.name
        co = self.positions()
        idx_all, roles_all, uv_all, sizes = [], [], [], []
        for idx, roles, uvs, period in self.chunks:
            idx_all.append(idx.reshape(-1))
            roles_all.extend(roles)
            uv = uvs.copy()
            if role_uv is not None:
                rarr = np.array([str(r) for r in roles], dtype=object)
                for r in set(rarr.tolist()):
                    mask = rarr == r
                    tile, swatch = role_uv.get(r, (2.0, False))
                    if swatch:
                        uv[mask] = 0.5
                    else:
                        uv[mask, :, 0] /= SweepMesh.fit_tile(period[0], tile)
                        uv[mask, :, 1] /= SweepMesh.fit_tile(period[1], tile)
            uv_all.append(uv.reshape(-1, 2))
            sizes.append(np.full(len(idx), idx.shape[1], dtype=np.int64))
        loops = np.concatenate(idx_all).astype(np.int32)
        totals = np.concatenate(sizes)
        starts = np.concatenate([[0], np.cumsum(totals)[:-1]]).astype(np.int32)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(co))
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(totals))
        me.polygons.foreach_set("loop_start", starts)
        me.update(calc_edges=True)
        if uv_name:
            uv = me.uv_layers.new(name=uv_name)
            uv.data.foreach_set("uv", np.concatenate(uv_all).astype(np.float32).ravel())
        order = []
        for r in roles_all:
            if r not in order:
                order.append(r)
        lookup = {r: i for i, r in enumerate(order)}
        me.polygons.foreach_set("material_index", np.array([lookup[r] for r in roles_all], dtype=np.int32))
        if smooth:
            SweepMesh.smooth(me)
        if self.sharp:
            SweepMesh.mark_sharp_pairs(me, np.vstack(self.sharp))
        me.update()
        return me, order

    @staticmethod
    def smooth(me):
        if hasattr(me, "shade_smooth"):
            me.shade_smooth()
        else:
            me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))

    @staticmethod
    def sharp_layer(me):
        attr = me.attributes.get("sharp_edge")
        if attr is None:
            attr = me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
        return attr

    @staticmethod
    def edge_keys(me):
        ev = np.empty(len(me.edges) * 2, dtype=np.int64)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        return np.minimum(ev[:, 0], ev[:, 1]) * (len(me.vertices) + 1) + np.maximum(ev[:, 0], ev[:, 1])

    @staticmethod
    def mark_sharp_pairs(me, pairs):
        if len(pairs) == 0 or len(me.edges) == 0:
            return 0
        keys = SweepMesh.edge_keys(me)
        order = np.argsort(keys)
        sk = keys[order]
        pk = np.minimum(pairs[:, 0], pairs[:, 1]) * (len(me.vertices) + 1) + np.maximum(pairs[:, 0], pairs[:, 1])
        pos = np.clip(np.searchsorted(sk, pk), 0, len(sk) - 1)
        hit = sk[pos] == pk
        attr = SweepMesh.sharp_layer(me)
        flags = np.zeros(len(me.edges), dtype=bool)
        attr.data.foreach_get("value", flags)
        flags[order[pos[hit]]] = True
        attr.data.foreach_set("value", flags)
        return int(hit.sum())


class SweepQuality:
    def __init__(self, name, fine=False, path_turn=4.0, path_len=0.6, path_sagitta=None, sagitta=0.0025, arc_step_deg=None, min_quarter=4, max_quarter=8, lathe_sagitta=0.0025, lathe_chord=0.25, lathe_turn=None):
        self.name = name
        self.fine = fine
        self.path_turn = path_turn
        self.path_len = path_len
        self.path_sagitta = path_sagitta
        self.sagitta = sagitta
        self.arc_step_deg = arc_step_deg
        self.min_quarter = min_quarter
        self.max_quarter = max_quarter
        self.lathe_sagitta = lathe_sagitta
        self.lathe_chord = lathe_chord
        self.lathe_turn = lathe_turn

    def arc(self, radius, phi, fixed=None):
        quarter = phi / (math.pi * 0.5)
        if self.arc_step_deg:
            n = max(1, int(math.ceil(math.degrees(phi) / self.arc_step_deg - 1e-9)))
            if fixed is not None:
                n = max(n, int(math.ceil(fixed * quarter - 1e-6)))
            return n
        if fixed is not None and not self.fine:
            return max(1, int(math.ceil(fixed * quarter - 1e-6)))
        lo = max(1, int(math.ceil(self.min_quarter * quarter - 1e-6)))
        hi = max(lo, int(math.ceil(self.max_quarter * quarter - 1e-6)))
        return SweepPath.arc_segments(radius, phi, self.sagitta, lo, hi)

    def path_sag(self, detail=None):
        sag = self.path_sagitta
        if sag and detail and not self.fine:
            sag = min(sag, max(0.0015, 0.05 * detail))
        return sag

    def path(self, points, closed=False, detail=None):
        return SweepPath.resample(points, closed, self.path_turn, self.path_len, self.path_sag(detail))

    def arc_path_count(self, radius, span_rad, detail=None):
        n_turn = math.ceil(math.degrees(span_rad) / self.path_turn - 1e-9)
        n_len = math.ceil(span_rad * radius / self.path_len - 1e-9)
        n_sag = SweepPath.arc_segments(radius, span_rad, self.path_sag(detail) or self.sagitta, 1, 100000)
        return int(max(2, n_turn, n_len, n_sag))

    def lathe(self, sweep_rad, rmax):
        full = sweep_rad >= 2.0 * math.pi - 1e-6
        n_min = 4 * self.min_quarter if full else max(2, int(math.ceil(self.min_quarter * sweep_rad / (math.pi * 0.5) - 1e-6)))
        n_sag = SweepPath.arc_segments(max(rmax, 1e-4), sweep_rad, self.lathe_sagitta, 1, 100000)
        n_chord = int(math.ceil(sweep_rad * max(rmax, 0.0) / self.lathe_chord - 1e-9))
        n = max(n_min, n_sag, n_chord)
        if self.lathe_turn:
            n = max(n, int(math.ceil(math.degrees(sweep_rad) / self.lathe_turn - 1e-9)))
        if full:
            n = int(math.ceil(n / 4.0) * 4)
        return int(n)


class SweepBuilder:
    Path = SweepPath
    Profile = SweepProfile

    def __init__(self, prefix="sweep", tex_dir=None):
        self.prefix = prefix.lower()
        self.tex_dir = tex_dir
        self.roles = {}
        self.shells = {}
        self.order = []
        self.current = None
        self.dense = SweepQuality("dense", fine=True, path_turn=0.75, path_len=0.08, arc_step_deg=4.5, lathe_sagitta=0.0002, lathe_chord=0.05, lathe_turn=1.0)
        self.game = SweepQuality("game", path_turn=4.0, path_len=0.6, path_sagitta=0.004, sagitta=0.0025, min_quarter=4, max_quarter=8, lathe_sagitta=0.0025, lathe_chord=0.25)
        self.coll = SweepQuality("collider", path_turn=10.0, path_len=1.5, path_sagitta=0.03, sagitta=0.05, min_quarter=1, max_quarter=2, lathe_sagitta=0.03, lathe_chord=0.6)
        self.report = {"shells": {}}
        self.roots = {}
        self.colliders = {}
        self.dense_objects = {}

    def add_role(self, name, shader="default.sps", color="#cccccc", tile=2.0, emissive=False, textures=None, params=None, swatch=None, walkable=False):
        tex = dict(textures or {})
        if swatch is None:
            diff = os.path.basename(tex.get("DiffuseSampler", "")).lower()
            swatch = diff.startswith("swatch_") or diff.startswith("trim_")
        self.roles[name] = {"name": name, "shader": shader, "color": color, "tile": float(tile), "emissive": bool(emissive), "textures": tex, "params": dict(params or {}), "swatch": bool(swatch), "walkable": bool(walkable)}
        return self.roles[name]

    @staticmethod
    def hex_rgb(value):
        v = value.lstrip("#")
        return tuple(int(v[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    @staticmethod
    def srgb_to_linear(c):
        c = np.asarray(c, dtype=np.float64)
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    @staticmethod
    def save_png(path, rgba):
        h, w = rgba.shape[:2]
        img = bpy.data.images.new(os.path.splitext(os.path.basename(path))[0] + "_tmp", w, h, alpha=True)
        img.pixels.foreach_set(np.clip(rgba, 0.0, 1.0).astype(np.float32).ravel())
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
        return path

    @staticmethod
    def periodic_noise(size, cells, rng):
        g = rng.uniform(-1.0, 1.0, (cells, cells))
        t = np.arange(size) * cells / size
        i0 = np.floor(t).astype(int) % cells
        i1 = (i0 + 1) % cells
        f = t - np.floor(t)
        f = f * f * (3.0 - 2.0 * f)
        rows = g[i0] * (1.0 - f)[:, None] + g[i1] * f[:, None]
        return rows[:, i0] * (1.0 - f)[None, :] + rows[:, i1] * f[None, :]

    def paver_textures(self, tex_dir, size=256, tile=2.4, paver=(1.2, 0.6), joint=0.012, bevel=0.012, base="#CEC4B6", seed=11):
        rng = np.random.default_rng(seed)
        ppm = size / tile
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
        u, v = (xx + 0.5) / ppm, (yy + 0.5) / ppm
        row = np.floor(v / paver[1]).astype(int)
        uo = u + (row % 2) * paver[0] * 0.5
        col = np.floor(uo / paver[0]).astype(int)
        lu, lv = uo - col * paver[0], v - row * paver[1]
        d = np.minimum(np.minimum(lu, paver[0] - lu), np.minimum(lv, paver[1] - lv))
        h = np.clip((d - joint * 0.5) / bevel, 0.0, 1.0)
        h = h * h * (3.0 - 2.0 * h)
        rows_n = max(1, int(round(tile / paver[1])))
        cols_n = max(1, int(round(tile / paver[0])))
        tone = rng.uniform(-0.045, 0.045, (rows_n, cols_n))[row % rows_n, col % cols_n]
        noise = self.periodic_noise(size, 16, rng) * 0.6 + self.periodic_noise(size, 64, rng) * 0.4
        b = np.array(self.hex_rgb(base))
        stone = b[None, None, :] * (1.0 + tone[..., None] + 0.03 * noise[..., None])
        grout = b[None, None, :] * 0.6
        col_rgb = grout * (1.0 - h[..., None]) + stone * h[..., None]
        height = h + 0.015 * noise
        gx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
        gy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
        nrm = np.stack([-gx * 3.0, -gy * 3.0, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        spec = 0.08 + 0.2 * h + 0.02 * noise
        ones = np.ones((size, size, 1))
        stem = os.path.join(tex_dir, self.prefix + "_paver")
        return {
            "DiffuseSampler": self.save_png(stem + "_d.png", np.concatenate([col_rgb, ones], -1)),
            "BumpSampler": self.save_png(stem + "_n.png", np.concatenate([nrm * 0.5 + 0.5, ones], -1)),
            "SpecSampler": self.save_png(stem + "_s.png", np.concatenate([np.repeat(spec[..., None], 3, -1), ones], -1)),
        }

    def stone_texture(self, tex_dir, name, base, size=256, grain=0.05, seed=5):
        rng = np.random.default_rng(seed)
        noise = self.periodic_noise(size, 8, rng) * 0.5 + self.periodic_noise(size, 32, rng) * 0.35 + self.periodic_noise(size, 128, rng) * 0.15
        b = np.array(self.hex_rgb(base))
        rgb = b[None, None, :] * (1.0 + grain * noise[..., None])
        return self.save_png(os.path.join(tex_dir, self.prefix + "_" + name + "_d.png"), np.concatenate([rgb, np.ones((size, size, 1))], -1))

    def swatch(self, tex_dir, name, color, size=16):
        px = np.ones((size, size, 4))
        px[..., :3] = np.array(self.hex_rgb(color))
        return self.save_png(os.path.join(tex_dir, "swatch_" + self.prefix + "_" + name + ".png"), px)

    def standard_roles(self, tex_dir, tile_size=256):
        os.makedirs(tex_dir, exist_ok=True)
        self.tex_dir = tex_dir
        self.add_role("paving", "normal_spec.sps", "#CEC4B6", 2.4, False, self.paver_textures(tex_dir, tile_size), {"bumpiness": 0.9, "spec_int": 0.3, "spec_falloff": 48.0, "spec_fresnel": 0.9}, False, True)
        self.add_role("stone", "default.sps", "#D9CFC2", 2.0, False, {"DiffuseSampler": self.stone_texture(tex_dir, "stone", "#D9CFC2", tile_size, 0.05, 5)}, {}, False, True)
        self.add_role("step", "default.sps", "#8E857B", 2.0, False, {"DiffuseSampler": self.stone_texture(tex_dir, "step", "#8E857B", tile_size, 0.06, 7)}, {}, False, True)
        table = (
            ("arch", "#E9E1D4", "default.sps", False, {}),
            ("metal", "#3B3733", "default.sps", False, {}),
            ("soil", "#4B3B2E", "default.sps", False, {}),
            ("gold", "#F2B860", "emissive.sps", True, {"emissive_mult": 1.6}),
            ("glow", "#FFF1D6", "emissive.sps", True, {"emissive_mult": 2.0}),
        )
        for name, color, shader, emissive, params in table:
            self.add_role(name, shader, color, 2.0, emissive, {"DiffuseSampler": self.swatch(tex_dir, name, color)}, params, True)
        return self.roles

    def material(self, role):
        r = self.roles.get(role) or self.add_role(role)
        name = self.prefix + "_" + role
        mat = bpy.data.materials.get(name)
        if mat is not None:
            return mat
        mat = bpy.data.materials.new(name)
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) or nt.nodes.new("ShaderNodeBsdfPrincipled")
        lin = tuple(float(c) for c in self.srgb_to_linear(self.hex_rgb(r["color"])))
        bsdf.inputs["Base Color"].default_value = lin + (1.0,)
        bsdf.inputs["Roughness"].default_value = 0.55
        for k, (sampler, path) in enumerate(r["textures"].items()):
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = sampler
            node.label = sampler
            node.location = (-700, 300 - 280 * k)
            img = bpy.data.images.load(os.path.abspath(path), check_existing=True)
            if sampler != "DiffuseSampler":
                img.colorspace_settings.name = "Non-Color"
            node.image = img
            if sampler == "DiffuseSampler":
                nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
                if r["emissive"]:
                    key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
                    nt.links.new(node.outputs["Color"], bsdf.inputs[key])
            elif sampler == "BumpSampler":
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.location = (-400, -300)
                nt.links.new(node.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        if r["emissive"] and "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = float(r["params"].get("emissive_mult", 2.0))
        mat.diffuse_color = lin + (1.0,)
        mat["map_forge_shader"] = r["shader"]
        keys = {"bumpiness": "map_forge_bumpiness", "spec_int": "map_forge_spec_int", "spec_falloff": "map_forge_spec_falloff", "spec_fresnel": "map_forge_spec_fresnel", "emissive_mult": "map_forge_emissive_mult", "wetness": "map_forge_wetness"}
        for k, v in r["params"].items():
            if k in keys:
                mat[keys[k]] = float(v)
        return mat

    def role_uv(self):
        return {name: (r["tile"], r["swatch"]) for name, r in self.roles.items()}

    def begin_shell(self, shell_id, collision_material="CONCRETE", budget=40000, lod_dist=300.0, lights=None):
        sid = shell_id.lower()
        self.shells[sid] = {"id": sid, "parts": [], "colliders": [], "collision_material": collision_material, "budget": min(int(budget), 40000), "lod_dist": float(lod_dist), "lights": list(lights or [])}
        if sid not in self.order:
            self.order.append(sid)
        self.current = sid
        return self.shells[sid]

    def shell(self):
        if self.current is None:
            self.begin_shell(self.prefix + "_shell")
        return self.shells[self.current]

    def new_part(self, name, normal_mode="transfer", reducible=True, dissolve=None):
        sh = self.shell()
        part = {"name": "%s_%02d_%s" % (sh["id"], len(sh["parts"]), name), "label": name, "dense": SweepMesh(name + "_hi"), "game": SweepMesh(name), "normal_mode": normal_mode, "reducible": reducible, "dissolve": list(dissolve or [])}
        sh["parts"].append(part)
        return part

    def add_collider(self, mesh):
        self.shell()["colliders"].append(mesh)
        return mesh

    def levels(self, part):
        if part["normal_mode"] != "transfer":
            return (("game", self.game, part["game"]),)
        return (("dense", self.dense, part["dense"]), ("game", self.game, part["game"]))

    def sweep_mesh(self, mesh, path, profile, closed, caps, frame, q, role=None, vary=None, cap_role=None, path_pts=None):
        arcs = [r for r in profile.radii if r > 0.0]
        if vary is not None and path is not None:
            probe = SweepPath.array(path)
            probe = probe[np.linspace(0, len(probe) - 1, min(len(probe), 240)).astype(int)]
            arcs.extend(min(float(vary[1](p, k / max(len(probe) - 1, 1))), vary[2]) for k, p in enumerate(probe))
        arcs = [r for r in arcs if r > 0.0]
        detail = min(arcs) if arcs else None
        pts = SweepPath.array(path_pts) if path_pts is not None else q.path(path, closed, detail)
        n = len(pts)
        t, s, u = SweepPath.frames(pts, closed, frame)
        P0, roles, sharp, counts = profile.sample(q.arc)
        roles = [r if r is not None else role for r in roles]
        if vary is not None:
            corner, fn, rmax = vary
            cum = SweepPath.cumulative(pts, closed)
            sn = cum[:n] / max(cum[-1], 1e-9)
            P = np.stack([profile.with_radius(corner, min(float(fn(pts[i], sn[i])), rmax)).sample(q.arc, counts)[0] for i in range(n)])
        else:
            P = np.broadcast_to(P0, (n,) + P0.shape).copy()
        grid = pts[:, None, :] + P[..., 0:1] * s[:, None, :] + P[..., 1:2] * u[:, None, :]
        dome = caps == "round" and profile.closed and not closed
        apex = None
        n_start = 0
        if dome:
            c2 = P[0].mean(axis=0)
            reff = float(np.linalg.norm(P[0] - c2, axis=1).mean())
            k = max(2, q.arc(reff, math.pi * 0.5))
            phis = np.linspace(0.0, math.pi * 0.5, k + 1)[1:-1]
            starts, ends = [], []
            for phi in phis[::-1]:
                ring = P[0] * math.cos(phi) + c2 * (1.0 - math.cos(phi))
                starts.append(pts[0] + ring[:, 0:1] * s[0] + ring[:, 1:2] * u[0] - t[0] * reff * math.sin(phi))
            for phi in phis:
                ring = P[-1] * math.cos(phi) + c2 * (1.0 - math.cos(phi))
                ends.append(pts[-1] + ring[:, 0:1] * s[-1] + ring[:, 1:2] * u[-1] + t[-1] * reff * math.sin(phi))
            n_start = len(starts)
            grid = np.concatenate([np.array(starts).reshape(-1, P.shape[1], 3), grid, np.array(ends).reshape(-1, P.shape[1], 3)], axis=0)
            P = np.concatenate([np.repeat(P[:1], len(starts), 0), P, np.repeat(P[-1:], len(ends), 0)], axis=0)
            apex = (pts[0] + c2[0] * s[0] + c2[1] * u[0] - t[0] * reff, pts[-1] + c2[0] * s[-1] + c2[1] * u[-1] + t[-1] * reff)
        idx, uu, vv = mesh.add_rings(grid, closed, profile.closed, roles, sharp)
        cr = cap_role or roles[0]
        if dome:
            m = P.shape[1]
            cols = list(range(m)) + [0]
            ring0 = np.stack([uu[0, cols], vv[0, :m + 1]], -1)
            ring1 = np.stack([uu[-1, cols], vv[-1, :m + 1]], -1)
            d0 = float(np.linalg.norm(apex[0] - grid[0].mean(axis=0)))
            d1 = float(np.linalg.norm(apex[1] - grid[-1].mean(axis=0)))
            a0 = mesh.add_verts(apex[0][None])
            a1 = mesh.add_verts(apex[1][None])
            mesh.add_fan(a0, idx[0], (uu[0].mean() - d0, vv[0].mean()), ring0, cr, False)
            mesh.add_fan(a1, idx[-1], (uu[-1].mean() + d1, vv[-1].mean()), ring1, cr, True)
        elif caps == "flat" and profile.closed and not closed:
            mesh.add_cap(idx[0], P[0], cr)
            mesh.add_cap(idx[-1][::-1], P[-1][::-1], cr)
        return {"points": pts, "idx": idx, "grid": grid, "frames": (t, s, u), "profile": P, "n_start": n_start}

    def sweep(self, path, profile, closed=False, caps="flat", frame=(0.0, 0.0, 1.0), role=None, name="sweep", collide=False, vary=None, part=None, cap_role=None, collider_profile=None, normal_mode="transfer"):
        pt = part or self.new_part(name, normal_mode)
        for level, q, mesh in self.levels(pt):
            self.sweep_mesh(mesh, path, profile, closed, caps, frame, q, role, vary, cap_role)
        if collide:
            cp = collider_profile or profile
            if cp.closed:
                cm = SweepMesh(name + "_col")
                self.sweep_mesh(cm, path, cp, closed, "flat", frame, self.coll, role, vary if collider_profile is None else None)
                self.add_collider(cm)
        return pt

    def lathe_mesh(self, mesh, profile, center, start_deg, end_deg, q, role=None, caps=True):
        c = SweepPath.array([center])[0]
        P, roles, sharp, counts = profile.sample(q.arc)
        roles = [r if r is not None else role for r in roles]
        span = math.radians(end_deg - start_deg)
        full = abs(end_deg - start_deg) >= 359.999
        k = q.lathe(abs(span), float(P[:, 0].max()))
        th = math.radians(start_deg) + span * np.arange(k + (0 if full else 1)) / k
        pole0 = (not profile.closed) and abs(P[0, 0]) < 1e-9 and full
        pole1 = (not profile.closed) and abs(P[-1, 0]) < 1e-9 and full
        lo, hi = (1 if pole0 else 0), (len(P) - 1 if pole1 else len(P))
        Pm = P[lo:hi]
        rm = roles if profile.closed else roles[lo:hi - 1]
        sm = sharp[lo:hi]
        S = np.stack([np.cos(th), np.sin(th), np.zeros_like(th)], -1)
        grid = c[None, None, :] + Pm[None, :, 0:1] * S[:, None, :] + Pm[None, :, 1:2] * np.array([0.0, 0.0, 1.0])[None, None, :]
        idx, uu, vv = mesh.add_rings(grid, full, profile.closed, rm, sm)
        vfull = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        if pole0:
            e = P[1] - P[0]
            a = mesh.add_verts((c + np.array([0.0, 0.0, P[0, 1]]))[None])
            ring_uv = np.stack([uu[:, 0], np.full(len(uu), vfull[1])], -1)
            mesh.add_fan(a, idx[:, 0], (float(uu[:, 0].mean()), 0.0), ring_uv, roles[0], bool(e[0] > 0.0))
        if pole1:
            e = P[-1] - P[-2]
            a = mesh.add_verts((c + np.array([0.0, 0.0, P[-1, 1]]))[None])
            ring_uv = np.stack([uu[:, -1], np.full(len(uu), vfull[-2])], -1)
            mesh.add_fan(a, idx[:, -1], (float(uu[:, -1].mean()), float(vfull[-1])), ring_uv, roles[-1], bool(e[0] > 0.0))
        if caps and profile.closed and not full:
            mesh.add_cap(idx[0], Pm, roles[0])
            mesh.add_cap(idx[-1][::-1], Pm[::-1], roles[0])
        return {"idx": idx, "theta": th, "profile": P}

    def lathe(self, profile, center=(0.0, 0.0, 0.0), start_deg=0.0, end_deg=360.0, role=None, name="lathe", caps=True, collide=False, part=None, collider_profile=None, normal_mode="transfer"):
        pt = part or self.new_part(name, normal_mode)
        for level, q, mesh in self.levels(pt):
            self.lathe_mesh(mesh, profile, center, start_deg, end_deg, q, role, caps)
        if collide:
            cm = SweepMesh(name + "_col")
            self.lathe_mesh(cm, collider_profile or profile, center, start_deg, end_deg, self.coll, role, True)
            self.add_collider(cm)
        return pt

    def rounded_slab(self, outline, thickness, edge_radius=0.3, edge_segments=None, bottom_radius=0.0, top_z=0.0, top_role="paving", rim_role="stone", bottom_role=None, top_spacing=1.25, radius_fn=None, name="slab", collide=True):
        loop = SweepPath.ccw(SweepPath.lifted(outline, top_z))
        prof = SweepProfile.slab_edge(thickness, edge_radius, bottom_radius, rim_role, bottom_role or rim_role, edge_segments)
        vary = (2, radius_fn, float(edge_radius)) if radius_fn is not None else None
        pt = self.new_part(name, dissolve=[bottom_role or rim_role])
        for level, q, mesh in self.levels(pt):
            res = self.sweep_mesh(mesh, loop, prof, True, "none", (0.0, 0.0, 1.0), q, rim_role, vary)
            idx, grid = res["idx"], res["grid"]
            mesh.add_cdt(idx[:, -1], grid[:, -1, :2], top_z, True, top_spacing if level == "game" else None, top_role)
            mesh.add_cdt(idx[:, 0], grid[:, 0, :2], top_z - thickness, False, None, bottom_role or rim_role)
        if collide:
            cm = SweepMesh(name + "_col")
            res = self.sweep_mesh(cm, loop, prof, True, "none", (0.0, 0.0, 1.0), self.coll, rim_role, vary)
            cm.add_cdt(res["idx"][:, -1], res["grid"][:, -1, :2], top_z, True, None, rim_role)
            cm.add_cdt(res["idx"][:, 0], res["grid"][:, 0, :2], top_z - thickness, False, None, rim_role)
            self.add_collider(cm)
        return pt

    def trim_line(self, path, width=0.05, closed=False, frame=(0.0, 0.0, 1.0), face="up", height=0.003, embed=0.004, role="gold", name="trim", part=None, caps="flat"):
        prof = SweepProfile.band(width, height, embed, face, role)
        pt = part or self.new_part(name, "auto", reducible=False)
        q = self.game
        self.sweep_mesh(pt["game"], path, prof, closed, caps, frame, q, role)
        return pt

    def arc_path(self, center, radius, start_deg, end_deg, z, q, reach=None, detail=None):
        c = SweepPath.array([center])[0]
        span = math.radians(end_deg - start_deg)
        n = q.arc_path_count(max(radius, reach or radius), abs(span), detail)
        a = np.radians(np.linspace(start_deg, end_deg, n + 1))
        return np.stack([c[0] + radius * np.cos(a), c[1] + radius * np.sin(a), np.full(n + 1, float(z))], axis=1)

    def arc_stairs(self, center, inner_radius, start_deg, end_deg, steps=8, rise=0.15, run=None, outer_radius=None, nosing_radius=0.04, top_z=0.0, back=0.3, embed=0.02, descend="out", top_nosing=False, role="step", nose_role=None, trims=True, trim_width=0.05, trim_setback=0.05, trim_inset=0.12, trim_role="gold", name="stairs", collide=True):
        steps = max(2, int(steps))
        if run is None:
            run = (float(outer_radius) - float(inner_radius)) / (steps - 1)
        r_top = float(inner_radius) if descend == "out" else float(outer_radius if outer_radius is not None else inner_radius + run * (steps - 1))
        sign = 1.0 if descend == "out" else -1.0
        r_far = r_top + sign * run * (steps - 1)
        reach = max(r_top, r_far) + back
        prof = SweepProfile.stairs(steps, rise, run, nosing_radius, top_z, back, embed, top_nosing, role, nose_role or role)
        pt = self.new_part(name, dissolve=[role])
        a0, a1 = (start_deg, end_deg) if descend == "out" else (end_deg, start_deg)
        for level, q, mesh in self.levels(pt):
            path = self.arc_path(center, r_top, a0, a1, top_z, q, reach, nosing_radius)
            self.sweep_mesh(mesh, None, prof, False, "flat", (0.0, 0.0, 1.0), q, role, None, role, path)
        if collide:
            cm = SweepMesh(name + "_col")
            path = self.arc_path(center, r_top, a0, a1, top_z, self.coll, reach)
            self.sweep_mesh(cm, None, prof, False, "flat", (0.0, 0.0, 1.0), self.coll, role, None, role, path)
            self.add_collider(cm)
        if trims:
            tp = self.new_part(name + "_trims", "auto", reducible=False)
            span_in = math.degrees(trim_inset / max(min(r_top, r_far), 1e-3))
            first = 0 if not top_nosing else 0
            for k in range(first, steps):
                x = k * run - trim_setback - trim_width * 0.5
                rad = r_top + sign * x
                z = top_z - k * rise
                s0, s1 = start_deg + span_in, end_deg - span_in
                tpath = SweepPath.arc(center, rad, s0, s1, z, 0.25)
                if descend != "out":
                    tpath = tpath[::-1].copy()
                self.trim_line(tpath, trim_width, False, (0.0, 0.0, 1.0), "up", 0.003, 0.004, trim_role, name + "_trim", tp)
        return pt

    def straight_stairs(self, origin, yaw_deg, width, steps=6, rise=0.15, run=0.4, nosing_radius=0.04, top_z=None, back=0.3, embed=0.02, top_nosing=False, role="step", nose_role=None, trims=True, trim_width=0.05, trim_setback=0.05, trim_inset=0.1, trim_role="gold", name="stairs", collide=True):
        o = SweepPath.array([origin])[0]
        tz = float(o[2] if top_z is None else top_z)
        yaw = math.radians(yaw_deg)
        d = np.array([math.cos(yaw), math.sin(yaw), 0.0])
        t = np.array([-d[1], d[0], 0.0])
        prof = SweepProfile.stairs(steps, rise, run, nosing_radius, tz, back, embed, top_nosing, role, nose_role or role)
        p0 = np.array([o[0], o[1], tz]) - t * width * 0.5
        p1 = np.array([o[0], o[1], tz]) + t * width * 0.5
        path = SweepPath.line(p0, p1, 0.05)
        pt = self.sweep(path, prof, False, "flat", (0.0, 0.0, 1.0), role, name, collide)
        pt["dissolve"] = [role]
        if trims:
            tp = self.new_part(name + "_trims", "auto", reducible=False)
            for k in range(0, int(steps)):
                x = k * run - trim_setback - trim_width * 0.5
                z = tz - k * rise
                a = np.array([o[0], o[1], z]) + d * x - t * (width * 0.5 - trim_inset)
                b = np.array([o[0], o[1], z]) + d * x + t * (width * 0.5 - trim_inset)
                self.trim_line(SweepPath.line(a, b, 0.05), trim_width, False, (0.0, 0.0, 1.0), "up", 0.003, 0.004, trim_role, name + "_trim", tp)
        return pt

    def rail(self, path, height=1.0, post_spacing=1.5, post_radius=0.028, top_profile=None, mid_rails=(0.36, 0.68), mid_radius=0.014, foot_radius=None, foot_height=0.014, embed=0.02, overhang=0.06, role="metal", foot_role=None, name="rail", collide=True, collider_width=0.12):
        base = SweepPath.clean(path)
        total = SweepPath.length(base)
        top_prof = top_profile or SweepProfile.handrail(0.07, 0.055, role=role)
        top_path = SweepPath.extend(SweepPath.lifted(base, None, height), overhang, overhang)
        self.sweep(top_path, top_prof, False, "round", (0.0, 0.0, 1.0), role, name + "_top")
        count = max(1, int(round(total / max(post_spacing, 1e-3))))
        posts = self.new_part(name + "_posts")
        feet = self.new_part(name + "_feet")
        rf = foot_radius or post_radius * 2.5
        foot = SweepProfile.custom([(0.0, -embed * 0.5), (rf, -embed * 0.5), (rf, foot_height), (0.0, foot_height)], [0.0, 0.0, foot_height * 0.7, 0.0], False, foot_role or role)
        post = SweepProfile.round(post_radius, role=role)
        for i in range(count + 1):
            p, _ = SweepPath.point_at(base, total * i / count)
            line = SweepPath.line(p - np.array([0.0, 0.0, embed]), p + np.array([0.0, 0.0, height]), 0.05)
            self.sweep(line, post, False, "flat", (1.0, 0.0, 0.0), role, name + "_post", False, None, posts)
            self.lathe(foot, p, 0.0, 360.0, foot_role or role, name + "_foot", True, False, feet)
        cut = post_radius * 0.6
        for h in mid_rails:
            mp = SweepPath.trim(SweepPath.lifted(base, None, h), cut, total - cut)
            self.sweep(mp, SweepProfile.round(mid_radius, role=role), False, "round", (0.0, 0.0, 1.0), role, name + "_mid")
        if collide:
            prof = SweepProfile.custom([(-collider_width * 0.5, -embed), (collider_width * 0.5, -embed), (collider_width * 0.5, height + 0.04), (-collider_width * 0.5, height + 0.04)], 0.0, True, role)
            cm = SweepMesh(name + "_col")
            self.sweep_mesh(cm, base, prof, False, "flat", (0.0, 0.0, 1.0), self.coll, role)
            self.add_collider(cm)
        return posts

    def arch(self, center, span=4.0, height=4.4, thickness=0.45, depth=0.6, corner_radius=0.12, yaw_deg=0.0, foot_z=0.0, embed=0.05, profile=None, role="arch", trim=True, trim_width=0.06, trim_role="glow", trim_from=0.35, plinth=(0.8, 0.9, 0.24, 0.06), plinth_role="stone", name="arch", collide=True):
        c = SweepPath.array([center])[0]
        yaw = math.radians(yaw_deg)
        ax = np.array([math.cos(yaw), math.sin(yaw), 0.0])
        ay = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
        base_z = float(foot_z) + (plinth[2] if plinth else 0.0)
        r = span * 0.5
        path = SweepPath.arch_curve(c, ax, r, height + foot_z, base_z - embed, 0.02)
        prof = profile or SweepProfile.rounded_rect(thickness, depth, corner_radius, role=role)
        pt = self.sweep(path, prof, False, "flat", tuple(ay), role, name)
        if trim:
            ipath = SweepPath.arch_curve(c, ax, r - thickness * 0.5, height + foot_z - thickness * 0.5, base_z - embed, 0.02)
            z = ipath[:, 2]
            keep = np.nonzero(z >= base_z + trim_from)[0]
            if len(keep) > 2:
                ipath = ipath[keep[0]:keep[-1] + 1]
                self.trim_line(ipath, trim_width, False, tuple(ay), "in", 0.003, 0.004, trim_role, name + "_trim")
        if plinth:
            pw, pd, ph, pr = plinth
            for sx in (-1.0, 1.0):
                fc = c[:2] + ax[:2] * r * sx
                outline = SweepPath.transform2d(SweepPath.rounded_rect((0.0, 0.0, 0.0), pw, pd, min(pw, pd) * 0.18), yaw_deg, (fc[0], fc[1], 0.0))
                self.rounded_slab(outline, ph + 0.02, pr, None, 0.0, foot_z + ph, plinth_role, plinth_role, plinth_role, None, None, name + "_plinth", collide)
        if collide:
            cprof = SweepProfile.custom([(thickness * 0.5, -depth * 0.5), (thickness * 0.5, depth * 0.5), (-thickness * 0.5, depth * 0.5), (-thickness * 0.5, -depth * 0.5)], 0.0, True, role)
            cm = SweepMesh(name + "_col")
            self.sweep_mesh(cm, path, cprof, False, "flat", tuple(ay), self.coll, role)
            self.add_collider(cm)
        return pt

    def planter(self, center, radius=0.85, height=0.55, wall=0.09, soil_drop=0.08, role="stone", soil_role="soil", embed=0.02, name="planter", collide=True):
        rin = radius - wall
        lip = wall * 0.5
        prof = SweepProfile([(0.0, -embed), (radius, -embed), (radius, height), (rin, height), (rin, height - soil_drop), (0.0, height - soil_drop)], [0.0, 0.0, lip, lip, 0.0, 0.0], False, [role, role, role, role, soil_role], [role] * 6, "planter")
        cprof = SweepProfile([(0.0, -embed), (radius, -embed), (radius, height), (0.0, height)], 0.0, False, [role] * 3, [role] * 4, "planter_col")
        return self.lathe(prof, center, 0.0, 360.0, role, name, True, collide, None, cprof)

    def ring(self, center, radius, profile, role="stone", name="ring", collide=False):
        return self.lathe(profile.shifted(radius, 0.0), center, 0.0, 360.0, role, name, True, collide)

    def collection(self, name, parent=None):
        col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        parent = parent or bpy.context.scene.collection
        if parent.children.get(col.name) is None:
            parent.children.link(col)
        return col

    def purge_names(self, names):
        for n in names:
            ob = bpy.data.objects.get(n)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
            me = bpy.data.meshes.get(n)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
            elif me is not None:
                me.name = n + "_old"

    def realize(self, mesh, name, collection, with_materials=True):
        self.purge_names([name])
        me, order = mesh.to_mesh(name, "UVMap 0", self.role_uv())
        if with_materials:
            for role in order:
                me.materials.append(self.material(role))
        ob = bpy.data.objects.new(name, me)
        collection.objects.link(ob)
        return ob, order

    @staticmethod
    def tri_count(ob):
        return int(sum(len(p.vertices) - 2 for p in ob.data.polygons))

    @staticmethod
    def triangulate(ob):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        faces = [f for f in bm.faces if len(f.verts) > 3]
        if faces:
            bmesh.ops.triangulate(bm, faces=faces, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()

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

    def dissolve_flat(self, ob, roles, order):
        mids = {i for i, r in enumerate(order) if r in roles}
        if not mids:
            return 0
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        faces = [f for f in bm.faces if f.material_index in mids]
        before = len(bm.faces)
        if faces:
            verts = list({v for f in faces for v in f.verts})
            edges = list({e for f in faces for e in f.edges})
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), use_dissolve_boundaries=False, verts=verts, edges=edges, delimit={"MATERIAL", "SEAM", "SHARP", "UV"})
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
        self.triangulate(ob)
        return before - len(ob.data.polygons)

    def decimate(self, ob, ratio, hard_angle=60.0):
        mod = ob.modifiers.new("reduce", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = float(ratio)
        mod.use_collapse_triangulate = True
        mod.use_symmetry = False
        self.apply_modifiers(ob)
        self.triangulate(ob)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.normal_update()
        limit = math.radians(hard_angle)
        for e in bm.edges:
            if e.smooth and len(e.link_faces) == 2 and e.calc_face_angle(0.0) > limit:
                e.smooth = False
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()

    def reduce(self, shell, items, keep_tris=400, min_ratio=0.25):
        budget = shell["budget"]
        total = sum(self.tri_count(lo) for _, lo, _, _ in items)
        info = {"before": total, "budget": budget, "dissolved_faces": 0, "collapse_ratio": 1.0}
        if total > budget:
            for part, lo, order, _ in items:
                if part["dissolve"]:
                    info["dissolved_faces"] += self.dissolve_flat(lo, part["dissolve"], order)
            total = sum(self.tri_count(lo) for _, lo, _, _ in items)
        if total > budget:
            big = [lo for part, lo, _, _ in items if part["reducible"] and self.tri_count(lo) > keep_tris]
            big_tris = sum(self.tri_count(lo) for lo in big)
            fixed = total - big_tris
            ratio = max(min_ratio, min(1.0, (budget - fixed) / max(big_tris, 1) * 0.985))
            if ratio < 0.999:
                for lo in big:
                    self.decimate(lo, ratio)
            info["collapse_ratio"] = round(ratio, 4)
            info["collapsed_parts"] = len(big)
        info["after"] = sum(self.tri_count(lo) for _, lo, _, _ in items)
        info["over_budget"] = info["after"] > budget
        return info

    @staticmethod
    def mesh_arrays(me):
        v = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", v)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        ls = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("loop_start", ls)
        lt = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("loop_total", lt)
        cn = np.empty(len(me.loops) * 3, np.float64)
        me.corner_normals.foreach_get("vector", cn)
        return v.reshape(-1, 3), lv, ls, lt, cn.reshape(-1, 3)

    @staticmethod
    def sharp_pairs(me):
        attr = me.attributes.get("sharp_edge")
        ev = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", ev)
        ev = ev.reshape(-1, 2)
        if attr is None:
            return np.zeros((0, 2), np.int64)
        flags = np.zeros(len(me.edges), bool)
        attr.data.foreach_get("value", flags)
        return ev[flags]

    def dense_sampler(self, hi):
        me = hi.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        tv = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", tv)
        tl = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get("loops", tl)
        co, _, _, _, cn = self.mesh_arrays(me)
        bvh = BVHTree.FromPolygons([tuple(p) for p in co], tv.reshape(-1, 3).tolist(), all_triangles=True)
        return {"bvh": bvh, "co": co, "tv": tv.reshape(-1, 3), "tl": tl.reshape(-1, 3), "cn": cn}

    @staticmethod
    def sample_normals(sampler, points):
        bvh = sampler["bvh"]
        q = len(points)
        loc = np.zeros((q, 3))
        tri = np.zeros(q, np.int64)
        ok = np.zeros(q, bool)
        dist = np.full(q, np.inf)
        for i in range(q):
            hit = bvh.find_nearest(Vector(points[i]))
            if hit[0] is None:
                continue
            loc[i] = hit[0]
            tri[i] = hit[2]
            dist[i] = hit[3]
            ok[i] = True
        tv = sampler["tv"][tri]
        a, b, c = sampler["co"][tv[:, 0]], sampler["co"][tv[:, 1]], sampler["co"][tv[:, 2]]
        v0, v1, v2 = b - a, c - a, loc - a
        d00 = (v0 * v0).sum(1)
        d01 = (v0 * v1).sum(1)
        d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1)
        d21 = (v2 * v1).sum(1)
        den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-20, 1e-20, d00 * d11 - d01 * d01)
        wv = (d11 * d20 - d01 * d21) / den
        ww = (d00 * d21 - d01 * d20) / den
        wu = 1.0 - wv - ww
        tl = sampler["tl"][tri]
        cn = sampler["cn"]
        n = wu[:, None] * cn[tl[:, 0]] + wv[:, None] * cn[tl[:, 1]] + ww[:, None] * cn[tl[:, 2]]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        return n, ok, dist

    @staticmethod
    def angles(a, b):
        return np.degrees(np.arccos(np.clip((a * b).sum(1), -1.0, 1.0)))

    def transfer_normals(self, lo, hi, guard_deg=20.0, nudge=0.0015):
        mod = lo.modifiers.new("normals", "DATA_TRANSFER")
        mod.object = hi
        mod.use_loop_data = True
        mod.data_types_loops = {"CUSTOM_NORMAL"}
        mod.loop_mapping = "POLYINTERP_NEAREST"
        mod.mix_mode = "REPLACE"
        mod.mix_factor = 1.0
        self.apply_modifiers(lo)
        me = lo.data
        co, lv, ls, lt, cn = self.mesh_arrays(me)
        sampler = self.dense_sampler(hi)
        poly_of = np.repeat(np.arange(len(ls)), lt)
        cent = np.zeros((len(ls), 3))
        np.add.at(cent, poly_of, co[lv])
        cent /= lt[:, None]
        sp = self.sharp_pairs(me)
        on_sharp = np.zeros(len(co), bool)
        if len(sp):
            on_sharp[sp.ravel()] = True
        pos = co[lv].copy()
        hard = on_sharp[lv]
        shift = cent[poly_of] - pos
        sl = np.linalg.norm(shift, axis=1, keepdims=True)
        pos[hard] += shift[hard] * np.minimum(1.0, nudge / np.maximum(sl[hard], 1e-12))
        ref, ok, dist = self.sample_normals(sampler, pos)
        diff = self.angles(cn, ref)
        fix = ok & (hard | (diff > guard_deg))
        out = cn.copy()
        out[fix] = ref[fix]
        if np.any(fix):
            me.normals_split_custom_set(out.tolist())
            me.update()
        _, _, _, _, final = self.mesh_arrays(me)
        err = self.angles(final, ref)[ok]
        tri_cent = cent
        ctr_n = np.zeros((len(ls), 3))
        np.add.at(ctr_n, poly_of, final)
        ctr_n /= np.maximum(np.linalg.norm(ctr_n, axis=1, keepdims=True), 1e-12)
        ref_c, ok_c, _ = self.sample_normals(sampler, tri_cent)
        err_c = self.angles(ctr_n, ref_c)[ok_c]
        return {
            "loops": int(len(lv)),
            "hard_loops": int(hard.sum()),
            "guard_fixed": int(fix.sum()),
            "modifier_wrong_side": int((ok & (diff > 60.0)).sum()),
            "vertex_err": [round(float(err.mean()), 3), round(float(np.percentile(err, 95)), 3), round(float(err.max()), 3)] if len(err) else [0, 0, 0],
            "interior_err": [round(float(err_c.mean()), 3), round(float(np.percentile(err_c, 95)), 3), round(float(err_c.max()), 3)] if len(err_c) else [0, 0, 0],
            "has_custom_normals": bool(me.has_custom_normals),
        }

    def extract(self, ob, order):
        me = ob.data
        co, lv, ls, lt, cn = self.mesh_arrays(me)
        uv = np.empty(len(me.loops) * 2, np.float64)
        me.uv_layers["UVMap 0"].data.foreach_get("uv", uv)
        mi = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("material_index", mi)
        return {"co": co, "lv": lv, "lt": lt, "cn": cn, "uv": uv.reshape(-1, 2), "roles": [order[i] for i in mi], "sharp": self.sharp_pairs(me)}

    def assemble(self, sid, datas, collection):
        self.purge_names([sid])
        order, cos, lvs, lts, cns, uvs, roles, sharps = [], [], [], [], [], [], [], []
        base = 0
        for d in datas:
            for r in d["roles"]:
                if r not in order:
                    order.append(r)
            cos.append(d["co"])
            lvs.append(d["lv"] + base)
            lts.append(d["lt"])
            cns.append(d["cn"])
            uvs.append(d["uv"])
            roles.extend(d["roles"])
            if len(d["sharp"]):
                sharps.append(d["sharp"] + base)
            base += len(d["co"])
        co = np.vstack(cos)
        lv = np.concatenate(lvs)
        lt = np.concatenate(lts)
        cn = np.vstack(cns)
        cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-12)
        me = bpy.data.meshes.new(sid)
        me.vertices.add(len(co))
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.loops.add(len(lv))
        me.loops.foreach_set("vertex_index", lv.astype(np.int32))
        me.polygons.add(len(lt))
        me.polygons.foreach_set("loop_start", np.concatenate([[0], np.cumsum(lt)[:-1]]).astype(np.int32))
        me.update(calc_edges=True)
        uvl = me.uv_layers.new(name="UVMap 0")
        uvl.data.foreach_set("uv", np.vstack(uvs).astype(np.float32).ravel())
        lookup = {r: i for i, r in enumerate(order)}
        me.polygons.foreach_set("material_index", np.array([lookup[r] for r in roles], dtype=np.int32))
        SweepMesh.smooth(me)
        if sharps:
            SweepMesh.mark_sharp_pairs(me, np.vstack(sharps))
        me.update()
        me.normals_split_custom_set(cn.tolist())
        me.update()
        for r in order:
            me.materials.append(self.material(r))
        me.name = sid
        ob = bpy.data.objects.new(sid, me)
        collection.objects.link(ob)
        ob.name = sid
        got = np.empty(len(me.loops) * 3, np.float64)
        me.corner_normals.foreach_get("vector", got)
        drift = self.angles(got.reshape(-1, 3), cn)
        return ob, order, float(drift.max()) if len(drift) else 0.0

    def make_colliders(self, sid, meshes, collection):
        out = []
        checks = []
        for i, cm in enumerate(meshes):
            name = "%s_col_%d" % (sid, i)
            self.purge_names([name])
            me, _ = cm.to_mesh(name, None, None, False)
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            vol = sum(f.verts[0].co.dot(f.verts[1].co.cross(f.verts[2].co)) for f in bm.faces) / 6.0
            if vol < 0.0:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
                vol = -vol
            bad = sum(1 for e in bm.edges if not e.is_manifold)
            tiny = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
            bm.to_mesh(me)
            bm.free()
            me.update()
            ob = bpy.data.objects.new(name, me)
            collection.objects.link(ob)
            ob.display_type = "WIRE"
            ob.hide_render = True
            ob["map_forge_collision"] = "mesh"
            out.append(ob)
            checks.append({"name": name, "tris": len(me.polygons), "non_manifold_edges": bad, "degenerate": tiny, "volume_m3": round(vol, 4)})
        return out, checks

    def bake_ao(self, roots, hidden, distance=1.6, samples=48):
        scene = bpy.context.scene
        engine = scene.render.engine
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = int(samples)
        if scene.world is None:
            scene.world = bpy.data.worlds.new(self.prefix + "_world")
        if hasattr(scene.world, "light_settings"):
            scene.world.light_settings.distance = float(distance)
        scene.render.bake.target = "VERTEX_COLORS"
        saved = [(o, o.hide_render) for o in hidden]
        for o in hidden:
            o.hide_render = True
        result = {}
        for root in roots:
            me = root.data
            tmp = me.color_attributes.new("ao_bake", "FLOAT_COLOR", "CORNER")
            me.color_attributes.active_color = tmp
            for o in [x for x in bpy.context.view_layer.objects if x is not None]:
                o.select_set(False)
            root.select_set(True)
            bpy.context.view_layer.objects.active = root
            ao = np.ones(len(me.loops))
            try:
                res = bpy.ops.object.bake(type="AO", target="VERTEX_COLORS", use_clear=True)
                if "FINISHED" in res:
                    buf = np.empty(len(me.loops) * 4, np.float32)
                    tmp.data.foreach_get("color", buf)
                    ao = np.clip(buf.reshape(-1, 4)[:, 0].astype(np.float64), 0.0, 1.0)
            except RuntimeError as exc:
                self.report.setdefault("warnings", []).append("ao bake failed for %s: %s" % (root.name, str(exc)[:160]))
            me.color_attributes.remove(me.color_attributes["ao_bake"])
            result[root.name] = ao
        for o, h in saved:
            o.hide_render = h
        scene.render.engine = engine
        return result

    def write_vcol(self, root, ao, lamps=None):
        me = root.data
        co, lv, ls, lt, _ = self.mesh_arrays(me)
        soft = 0.58 + 0.42 * np.clip(ao, 0.0, 1.0)
        pos = co[lv]
        g = np.zeros(len(lv))
        for lamp in lamps or []:
            d = np.linalg.norm(pos - np.asarray(lamp["pos"], dtype=np.float64)[None, :], axis=1)
            g = np.maximum(g, float(lamp.get("g", 0.35)) * (1.0 - SweepPath.smoothstep(0.0, float(lamp.get("radius", 4.0)), d)))
        col = np.stack([soft, g, soft, np.ones(len(lv))], axis=1)
        mi = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("material_index", mi)
        emissive = np.array([bool(self.roles.get(self.role_of(m), {}).get("emissive")) for m in me.materials], dtype=bool)
        loop_em = np.repeat(emissive[mi], lt) if len(emissive) else np.zeros(len(lv), bool)
        col[loop_em] = 1.0
        attr = me.color_attributes.get("Color 1")
        if attr is not None:
            me.color_attributes.remove(attr)
        attr = me.color_attributes.new("Color 1", "BYTE_COLOR", "CORNER")
        attr.data.foreach_set("color_srgb", col.astype(np.float32).ravel())
        me.color_attributes.active_color = attr
        try:
            me.color_attributes.render_color_index = list(me.color_attributes).index(attr)
        except (AttributeError, ValueError):
            pass
        lit = ~loop_em
        return {"R_min": int(round(col[lit, 0].min() * 255)) if lit.any() else 255, "R_mean": round(float(col[lit, 0].mean() * 255), 1) if lit.any() else 255.0, "G_mean_outdoor": round(float(col[lit, 1].mean() * 255), 2) if lit.any() else 0.0, "G_max": int(round(col[:, 1].max() * 255)), "emissive_loops": int(loop_em.sum())}

    def role_of(self, mat):
        if mat is None:
            return ""
        return mat.name[len(self.prefix) + 1:] if mat.name.startswith(self.prefix + "_") else mat.name

    def dihedral(self, ob):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.normal_update()
        smooth, sharp_n, total = [], 0, 0
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            total += 1
            if not e.smooth:
                sharp_n += 1
                continue
            smooth.append(math.degrees(e.calc_face_angle(0.0)))
        nm = sum(1 for e in bm.edges if not e.is_manifold)
        bm.free()
        d = np.array(smooth) if smooth else np.zeros(1)
        return {"smooth_p50": round(float(np.percentile(d, 50)), 2), "smooth_p90": round(float(np.percentile(d, 90)), 2), "smooth_max": round(float(d.max()), 2), "frac_over_30": round(float((d > 30.0).mean()), 4), "frac_over_45": round(float((d > 45.0).mean()), 4), "hard_share": round(sharp_n / max(total, 1), 4), "open_edges": nm}

    def floor_check(self, root, colliders, walk_roles):
        me = root.data
        co, lv, ls, lt, _ = self.mesh_arrays(me)
        mi = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get("material_index", mi)
        fn = np.empty(len(me.polygons) * 3, np.float64)
        me.polygons.foreach_get("normal", fn)
        fn = fn.reshape(-1, 3)
        poly_of = np.repeat(np.arange(len(ls)), lt)
        cent = np.zeros((len(ls), 3))
        np.add.at(cent, poly_of, co[lv])
        cent /= lt[:, None]
        walk = np.array([self.role_of(me.materials[i]) in walk_roles for i in mi]) & (fn[:, 2] > 0.999)
        if not colliders or not walk.any():
            return {"samples": 0}
        verts, polys, base = [], [], 0
        for c in colliders:
            cv = np.empty(len(c.data.vertices) * 3, np.float64)
            c.data.vertices.foreach_get("co", cv)
            verts.extend(cv.reshape(-1, 3).tolist())
            polys.extend([[base + i for i in p.vertices] for p in c.data.polygons])
            base += len(c.data.vertices)
        bvh = BVHTree.FromPolygons(verts, polys)
        tri = [list(p.vertices) for p in me.polygons]
        visual = BVHTree.FromPolygons([tuple(v) for v in co], tri)
        pts = cent[walk]
        if len(pts) > 4000:
            pts = pts[np.linspace(0, len(pts) - 1, 4000).astype(int)]
        dz, miss, hidden = [], 0, 0
        down = Vector((0.0, 0.0, -1.0))
        for p in pts:
            top = Vector((p[0], p[1], p[2] + 0.35))
            seen = visual.ray_cast(top, down, 1.0)
            if seen[0] is not None and seen[0].z > p[2] + 0.005:
                hidden += 1
                continue
            hit = bvh.ray_cast(top, down, 1.0)
            if hit[0] is None:
                miss += 1
                continue
            dz.append(abs(hit[0].z - p[2]))
        d = np.array(dz) if dz else np.zeros(1)
        return {"samples": int(len(pts)), "hidden": hidden, "missed": miss, "max_dz_m": round(float(d.max()), 4), "within_2cm": round(float((d <= 0.02).mean()), 4)}

    def finish(self, props_dir, lamps=None, ao=True, ao_distance=1.6, ao_samples=48, save=True):
        t0 = time.perf_counter()
        os.makedirs(props_dir, exist_ok=True)
        work = self.collection(self.prefix + "_work")
        dense_col = self.collection(self.prefix + "_dense")
        shells_col = self.collection(self.prefix + "_shells")
        roots = []
        part_objects = []
        for sid in self.order:
            shell = self.shells[sid]
            items = []
            for part in shell["parts"]:
                lo, order = self.realize(part["game"], part["name"] + "_lo", work)
                hi = None
                if part["normal_mode"] == "transfer":
                    hi, _ = self.realize(part["dense"], part["name"] + "_hi", dense_col)
                    hi.hide_render = True
                    self.dense_objects.setdefault(sid, []).append(hi)
                self.triangulate(lo)
                items.append((part, lo, order, hi))
            dense_tris = sum(self.tri_count(hi) for _, _, _, hi in items if hi is not None)
            red = self.reduce(shell, items)
            datas, stats = [], []
            for part, lo, order, hi in items:
                if hi is None:
                    twin = bpy.data.objects.new(part["name"] + "_hi", lo.data.copy())
                    dense_col.objects.link(twin)
                    twin.hide_render = True
                    self.dense_objects.setdefault(sid, []).append(twin)
                st = self.transfer_normals(lo, hi) if hi is not None else {"loops": len(lo.data.loops), "mode": "auto"}
                st["part"] = part["label"]
                st["tris"] = self.tri_count(lo)
                stats.append(st)
                datas.append(self.extract(lo, order))
                part_objects.append(lo)
            col_coll = self.collection(sid + "_collision", shells_col)
            root, order, drift = self.assemble(sid, datas, shells_col)
            cols, col_checks = self.make_colliders(sid, shell["colliders"], col_coll)
            self.roots[sid] = root
            self.colliders[sid] = cols
            roots.append(root)
            self.report["shells"][sid] = {"tris": self.tri_count(root), "dense_tris": dense_tris, "budget": shell["budget"], "reduce": red, "parts": stats, "roles": order, "normal_drift_after_join_deg": round(drift, 4), "colliders": col_checks}
        for ob in part_objects:
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.context.view_layer.update()
        hidden = [o for objs in self.dense_objects.values() for o in objs]
        aos = self.bake_ao(roots, hidden, ao_distance, ao_samples) if ao else {}
        walk_roles = {n for n, r in self.roles.items() if r.get("walkable")}
        for sid in self.order:
            root = self.roots[sid]
            shell = self.shells[sid]
            rep = self.report["shells"][sid]
            rep["vcol"] = self.write_vcol(root, aos.get(root.name, np.ones(len(root.data.loops))), lamps)
            rep["dihedral"] = self.dihedral(root)
            rep["floor"] = self.floor_check(root, self.colliders[sid], walk_roles)
            rep["has_custom_normals"] = bool(root.data.has_custom_normals)
            rep["all_triangles"] = all(len(p.vertices) == 3 for p in root.data.polygons)
            rep["uv_layers"] = [u.name for u in root.data.uv_layers]
            rep["color_attrs"] = [(c.name, c.domain, c.data_type) for c in root.data.color_attributes]
            dims = np.empty(len(root.data.vertices) * 3, np.float64)
            root.data.vertices.foreach_get("co", dims)
            dims = dims.reshape(-1, 3)
            rep["bbox"] = [[round(float(x), 3) for x in dims.min(0)], [round(float(x), 3) for x in dims.max(0)]]
            vertex_err = [p["vertex_err"] for p in rep["parts"] if "vertex_err" in p]
            interior_err = [p["interior_err"] for p in rep["parts"] if "interior_err" in p]
            if vertex_err:
                rep["normal_err_vertex_max_deg"] = max(e[2] for e in vertex_err)
                rep["normal_err_interior_p95_deg"] = max(e[1] for e in interior_err)
            meta = {"id": sid, "style": "sculpt_sweep_v1", "collision_material": shell["collision_material"], "lights": shell["lights"], "tris": rep["tris"], "budget": shell["budget"], "lod_dist": shell["lod_dist"], "dense_tris": rep["dense_tris"], "parts": [p["part"] for p in rep["parts"]], "colliders": len(self.colliders[sid])}
            root["map_forge"] = json.dumps(meta)
            if save:
                rep["blend"] = self.save_shell(sid, props_dir)
        self.report["seconds"] = round(time.perf_counter() - t0, 2)
        return self.report

    def save_shell(self, sid, props_dir):
        name = sid
        scn = bpy.data.scenes.get(name + "_export") or bpy.data.scenes.new(name + "_export")
        root = self.roots[sid]
        if scn.collection.objects.get(root.name) is None:
            scn.collection.objects.link(root)
        col = bpy.data.collections.get(sid + "_collision")
        if col is not None and scn.collection.children.get(col.name) is None:
            scn.collection.children.link(col)
        path = os.path.join(props_dir, name + ".blend")
        bpy.data.libraries.write(path, {scn}, path_remap="ABSOLUTE", fake_user=False, compress=False)
        return path

    def map_spec(self, map_name, center=(0.0, 0.0, 520.0), warp=None, floor_z=None, vanilla=None, budgets=None):
        c = [float(x) for x in center]
        spec = {
            "map_name": map_name,
            "shared_ytd": map_name + "_tex",
            "ytyp_name": map_name,
            "archetype_type": "sky_afk",
            "budgets": budgets or {"max_total_tris": 60000, "max_ytd_vram_mb": 6.0, "max_disk_mb": 8.0, "max_outdoor_vcol_g": 45},
            "anchor": {"ymap_name": map_name, "ybn_name": map_name + "_col", "center": c, "warp_point": list(warp or [c[0], c[1], c[2] + 0.5, 0.0]), "expected_floor_z": [c[2] + float(z) for z in (floor_z or [0.0])], "zone_sphere_center": c, "zone_sphere_radius": 120.0},
            "texture_rules": {"default_diffuse_max_res": 512, "hero_diffuse_max_res": 1024, "normal_max_res": 256, "spec_max_res": 256, "hero_prefixes": ["logo_", "sign_", "brand_"], "swatch_max_res": 32, "swatch_prefixes": ["swatch_", "trim_"]},
            "vanilla_ytyps": [],
            "prop_overrides": {},
            "entities": [],
        }
        for sid in self.order:
            sh = self.shells[sid]
            spec["prop_overrides"][sid] = {"lod_dist": sh["lod_dist"], "collision_material": sh["collision_material"]}
            if sh["lights"]:
                spec["prop_overrides"][sid]["lights"] = sh["lights"]
            spec["entities"].append({"model": sid, "pos": [0.0, 0.0, 0.0], "yaw_deg": 0.0, "static_col": True, "vanilla": False})
        for item in vanilla or []:
            spec["entities"].append(dict(item, vanilla=True))
        return spec

    @staticmethod
    def run_tool(blender, script, args, factory=False, timeout=1800):
        cmd = [blender, "-b"] + (["--factory-startup"] if factory else []) + ["-P", script, "--"] + list(args)
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        tags = ("YDR_EXPORT", "YBN_EXPORT", "YTYP_EXPORT", "YMAP_EXPORT", "SHARED_YTD", "PACKAGE_READY", "MAP_EXPORT", "DDS_PREENCODED", "FAIL", "WARN", "MAP_INSPECT", "PASS")
        lines = [l for l in proc.stdout.splitlines() if l.startswith(tags)]
        return {"code": proc.returncode, "seconds": round(time.perf_counter() - t0, 1), "lines": lines, "tail": (proc.stderr or proc.stdout)[-1500:] if proc.returncode else ""}


class SweepPreview:
    def __init__(self, out_dir, resolution=(1400, 900), samples=48):
        self.out_dir = out_dir
        self.resolution = resolution
        self.samples = samples
        self.scene = bpy.context.scene
        self.clay = None
        self.camera = None
        os.makedirs(out_dir, exist_ok=True)

    def set_engine(self, kind="eevee"):
        table = {"eevee": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"), "workbench": ("BLENDER_WORKBENCH",), "cycles": ("CYCLES",)}
        for name in table.get(kind, ("CYCLES",)):
            try:
                self.scene.render.engine = name
                return name
            except TypeError:
                continue
        return self.scene.render.engine

    def setup(self):
        sc = self.scene
        engine = self.set_engine("eevee")
        sc.render.resolution_x, sc.render.resolution_y = self.resolution
        sc.render.resolution_percentage = 100
        sc.render.film_transparent = False
        if engine.startswith("BLENDER_EEVEE") and hasattr(sc, "eevee"):
            sc.eevee.taa_render_samples = int(self.samples)
            for attr, val in (("use_gtao", True), ("gtao_distance", 0.6), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8)):
                if hasattr(sc.eevee, attr):
                    try:
                        setattr(sc.eevee, attr, val)
                    except (TypeError, AttributeError):
                        pass
        elif engine == "CYCLES":
            sc.cycles.samples = int(self.samples)
            sc.cycles.device = "CPU"
        for vt in ("AgX", "Filmic", "Standard"):
            try:
                sc.view_settings.view_transform = vt
                break
            except TypeError:
                continue
        if sc.world is None:
            sc.world = bpy.data.worlds.new("preview_world")
        w = sc.world
        if hasattr(w, "use_nodes") and not w.use_nodes:
            w.use_nodes = True
        bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
        if bg is not None:
            bg.inputs["Color"].default_value = (0.32, 0.36, 0.42, 1.0)
            bg.inputs["Strength"].default_value = 0.35
        self.clay = bpy.data.materials.get("preview_clay") or bpy.data.materials.new("preview_clay")
        if hasattr(self.clay, "use_nodes") and not self.clay.use_nodes:
            self.clay.use_nodes = True
        bsdf = next((n for n in self.clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        bsdf.inputs["Base Color"].default_value = (0.42, 0.4, 0.37, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.28
        for key in ("Specular IOR Level", "Specular"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = 0.7
                break
        for name, rot, energy, angle in (("preview_key", (math.radians(62.0), 0.0, math.radians(38.0)), 2.6, 1.0), ("preview_fill", (math.radians(70.0), 0.0, math.radians(-150.0)), 0.35, 8.0)):
            ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, "SUN")
            ld.energy = energy
            ld.angle = math.radians(angle)
            ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, ld)
            if sc.collection.objects.get(ob.name) is None:
                sc.collection.objects.link(ob)
            ob.rotation_euler = rot
        cam = bpy.data.cameras.get("preview_cam") or bpy.data.cameras.new("preview_cam")
        self.camera = bpy.data.objects.get("preview_cam") or bpy.data.objects.new("preview_cam", cam)
        if sc.collection.objects.get(self.camera.name) is None:
            sc.collection.objects.link(self.camera)
        sc.camera = self.camera
        return engine

    def aim(self, location, target, lens=35.0):
        loc = Vector(location)
        self.camera.location = loc
        self.camera.rotation_euler = (Vector(target) - loc).to_track_quat("-Z", "Y").to_euler()
        self.camera.data.lens = lens
        self.camera.data.clip_start = 0.05
        self.camera.data.clip_end = 500.0

    def key_light(self, elevation_deg, azimuth_deg):
        ob = bpy.data.objects.get("preview_key")
        if ob is not None:
            ob.rotation_euler = (math.radians(90.0 - elevation_deg), 0.0, math.radians(azimuth_deg))

    def normal_material(self):
        mat = bpy.data.materials.get("preview_normal") or bpy.data.materials.new("preview_normal")
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        mad = nt.nodes.new("ShaderNodeVectorMath")
        mad.operation = "MULTIPLY_ADD"
        mad.inputs[1].default_value = (0.5, 0.5, 0.5)
        mad.inputs[2].default_value = (0.5, 0.5, 0.5)
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(geo.outputs["Normal"], mad.inputs[0])
        nt.links.new(mad.outputs[0], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        return mat

    def vcol_material(self):
        mat = bpy.data.materials.get("preview_vcol") or bpy.data.materials.new("preview_vcol")
        if hasattr(mat, "use_nodes") and not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Color 1"
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(attr.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        return mat

    def render(self, name, show, location, target, lens=35.0, mode="clay", elevation=28.0, azimuth=38.0):
        vis = {o.name for o in show}
        for ob in self.scene.objects:
            if ob.type == "MESH":
                ob.hide_render = ob.name not in vis
        self.aim(location, target, lens)
        self.key_light(elevation, azimuth)
        swapped = []
        override = {"clay": self.clay, "normal": self.normal_material() if mode == "normal" else None, "vcol": self.vcol_material() if mode == "vcol" else None}.get(mode)
        if override is not None:
            for ob in show:
                for slot in ob.material_slots:
                    swapped.append((slot, slot.link))
                    slot.link = "OBJECT"
                    slot.material = override
        sc = self.scene
        saved = (sc.view_settings.view_transform, sc.render.film_transparent, sc.render.image_settings.color_mode)
        if mode == "normal":
            for vt in ("Raw", "Standard"):
                try:
                    sc.view_settings.view_transform = vt
                    break
                except TypeError:
                    continue
            sc.render.film_transparent = True
            sc.render.image_settings.color_mode = "RGBA"
        path = os.path.join(self.out_dir, name + ".png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        sc.view_settings.view_transform, sc.render.film_transparent, sc.render.image_settings.color_mode = saved
        for slot, link in swapped:
            slot.material = None
            slot.link = link
        return path

    @staticmethod
    def pixels(path):
        img = bpy.data.images.load(path, check_existing=False)
        img.colorspace_settings.name = "Non-Color"
        w, h = img.size
        buf = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(buf)
        bpy.data.images.remove(img)
        return buf.reshape(h, w, 4)

    def compare_normals(self, path_a, path_b, heat_path=None):
        a, b = self.pixels(path_a), self.pixels(path_b)
        mask = (a[..., 3] > 0.99) & (b[..., 3] > 0.99)
        na = a[..., :3] * 2.0 - 1.0
        nb = b[..., :3] * 2.0 - 1.0
        na /= np.maximum(np.linalg.norm(na, axis=-1, keepdims=True), 1e-6)
        nb /= np.maximum(np.linalg.norm(nb, axis=-1, keepdims=True), 1e-6)
        full = np.degrees(np.arccos(np.clip((na * nb).sum(-1), -1.0, 1.0)))
        ang = full[mask]
        if heat_path:
            heat = np.zeros(a.shape, np.float32)
            heat[..., 3] = 1.0
            base = np.clip(a[..., :3].mean(-1) * 0.35, 0.0, 1.0)
            t = np.clip(full / 10.0, 0.0, 1.0)
            heat[..., 0] = np.where(mask, np.maximum(base, t), base)
            heat[..., 1] = np.where(mask, base * (1.0 - t), base)
            heat[..., 2] = np.where(mask, base * (1.0 - t), base)
            SweepBuilder.save_png(heat_path, heat)
        if not len(ang):
            return {"pixels": 0}
        return {"pixels": int(len(ang)), "mean_deg": round(float(ang.mean()), 3), "p50_deg": round(float(np.percentile(ang, 50)), 3), "p95_deg": round(float(np.percentile(ang, 95)), 3), "p99_deg": round(float(np.percentile(ang, 99)), 3), "over_5deg": round(float((ang > 5.0).mean()), 4)}


class SweepDemo:
    def __init__(self, prefix="1nfx_sweep"):
        self.prefix = prefix
        self.base_radius = 5.0
        self.stair_center = -90.0
        self.stair_half = 45.0
        self.thickness = 1.2
        self.steps = 8
        self.rise = 0.15
        self.run = 0.40
        self.nosing = 0.04
        self.rim = 0.30
        self.arch_center = (0.0, -3.0, 0.0)
        self.lamp = {"pos": [0.0, -3.0, 3.95], "radius": 3.5, "g": 0.35}

    def stair_distance(self, a):
        return abs((math.degrees(a) - self.stair_center + 180.0) % 360.0 - 180.0)

    def plaza_radius(self, a):
        w = float(SweepPath.smoothstep(self.stair_half + 6.0, self.stair_half + 36.0, self.stair_distance(a)))
        bump = 0.85 + 0.55 * math.sin(2.0 * a + 0.9) + 0.30 * math.sin(3.0 * a - 0.4)
        return self.base_radius + w * bump

    def rim_radius(self, point, sn):
        d = self.stair_distance(math.atan2(point[1], point[0]))
        return self.nosing + (self.rim - self.nosing) * float(SweepPath.smoothstep(self.stair_half, self.stair_half + 12.0, d))

    def build(self, b, tex_dir):
        b.standard_roles(tex_dir)
        outline = SweepPath.radial((0.0, 0.0, 0.0), self.plaza_radius, 0.0, 0.02)
        b.begin_shell(self.prefix + "_plaza", "CONCRETE", 40000, 300.0)
        b.rounded_slab(outline, self.thickness, self.rim, 6, 0.0, 0.0, "paving", "stone", "stone", 1.25, self.rim_radius, "plaza", True)
        b.trim_line(SweepPath.offset(outline, -0.55, True, 0.0), 0.05, True, (0.0, 0.0, 1.0), "up", 0.003, 0.004, "gold", "plaza_trim")
        b.planter((-2.3, 1.5, 0.0), 0.85, 0.55, 0.09, 0.08, "stone", "soil", 0.02, "planter", True)
        b.begin_shell(self.prefix + "_stairs", "CONCRETE", 40000, 300.0)
        b.arc_stairs((0.0, 0.0, 0.0), self.base_radius, self.stair_center - self.stair_half, self.stair_center + self.stair_half, self.steps, self.rise, self.run, None, self.nosing, 0.0, 0.3, 0.02, "out", False, "step", "step", True, 0.05, 0.05, 0.12, "gold", "stairs", True)
        b.begin_shell(self.prefix + "_rail", "METAL_SOLID_MEDIUM", 40000, 200.0)
        inner = SweepPath.offset(outline, -0.4, True, 0.0)
        b.rail(SweepPath.sector(inner, (0.0, 0.0, 0.0), 25.0, 155.0), 1.0, 1.5, 0.028, None, (0.36, 0.68), 0.014, None, 0.014, 0.02, 0.06, "metal", "metal", "rail", True)
        light = {"type": "POINT", "position": list(self.lamp["pos"]), "color": [255, 224, 168], "intensity": 2.5, "falloff": 18.0, "falloff_exponent": 64.0, "corona_size": 0.6, "corona_intensity": 0.4, "time_flags": "NIGHT", "cast_static_shadows": False}
        b.begin_shell(self.prefix + "_arch", "CONCRETE", 40000, 300.0, [light])
        b.arch(self.arch_center, 4.0, 4.4, 0.45, 0.6, 0.12, 0.0, 0.0, 0.05, None, "arch", True, 0.06, "glow", 0.35, (0.8, 0.9, 0.24, 0.06), "stone", "arch", True)
        return b

    def renders(self, b, out_dir, quick=False):
        pv = SweepPreview(out_dir, (1280, 800) if not quick else (900, 560), 32 if not quick else 16)
        pv.setup()
        roots = [b.roots[s] for s in b.order]
        dense = [o for s in b.order for o in b.dense_objects.get(s, [])]
        views = {
            "overview": ((14.5, -17.0, 9.5), (0.0, -0.8, -0.6), 30.0, 30.0, 38.0),
            "stairs": ((3.6, -8.9, 0.15), (0.6, -5.6, -0.7), 32.0, 22.0, 70.0),
            "rail": ((-3.6, 2.2, 1.9), (0.4, 5.3, 0.55), 30.0, 22.0, 120.0),
            "rim": ((-8.6, -2.6, 0.9), (-4.8, 0.4, -0.25), 30.0, 16.0, 140.0),
            "arch": ((3.4, -7.4, 2.2), (0.0, -3.0, 3.0), 30.0, 35.0, 30.0),
        }
        out = []
        stats = {}
        for name, (loc, tgt, lens, elev, azim) in views.items():
            out.append(pv.render(name + "_lo", roots, loc, tgt, lens, "clay", elev, azim))
            if name != "overview" and not quick:
                out.append(pv.render(name + "_hi", dense, loc, tgt, lens, "clay", elev, azim))
                a = pv.render(name + "_nlo", roots, loc, tgt, lens, "normal", elev, azim)
                c = pv.render(name + "_nhi", dense, loc, tgt, lens, "normal", elev, azim)
                stats[name] = pv.compare_normals(a, c, os.path.join(out_dir, name + "_nerr.png"))
        out.append(pv.render("overview_tex", roots, views["overview"][0], views["overview"][1], 30.0, "tex", 30.0, 38.0))
        out.append(pv.render("overview_vcol", roots, views["overview"][0], views["overview"][1], 30.0, "vcol", 30.0, 38.0))
        return out, stats


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--demo" not in argv:
        print("SWEEP_USAGE blender -b --factory-startup -P sculpt_sweep.py -- --demo --out <dir> [--export] [--no-render] [--quick] [--map-forge <dir>] [--blender <exe>]", flush=True)
        return
    opts = {"--out": os.path.join(tempfile.gettempdir(), "sculpt_sweep_demo"), "--map-forge": "", "--blender": bpy.app.binary_path, "--prefix": "1nfx_sweep", "--samples": "48"}
    for i, a in enumerate(argv):
        if a in opts and i + 1 < len(argv):
            opts[a] = argv[i + 1]
    out = os.path.abspath(opts["--out"])
    props, tex, renders = os.path.join(out, "props"), os.path.join(out, "textures"), os.path.join(out, "renders")
    for d in (props, tex, renders):
        os.makedirs(d, exist_ok=True)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    demo = SweepDemo(opts["--prefix"])
    b = SweepBuilder(opts["--prefix"])
    t0 = time.perf_counter()
    demo.build(b, tex)
    report = b.finish(props, [demo.lamp], True, 1.6, int(opts["--samples"]), True)
    report["build_seconds"] = round(time.perf_counter() - t0, 2)
    spec = b.map_spec(opts["--prefix"] + "_demo")
    spec_path = os.path.join(out, "map-spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    report["spec"] = spec_path
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "sweep_demo_all.blend"), compress=False)
    if "--no-render" not in argv:
        report["renders"], report["screen_normal_lo_vs_dense"] = demo.renders(b, renders, "--quick" in argv)
    if "--export" in argv:
        here = os.path.dirname(os.path.abspath(globals().get("__file__", "") or os.getcwd()))
        mf = opts["--map-forge"] or os.path.normpath(os.path.join(here, "..", "..", "..", "map-forge", "scripts", "blender"))
        pkg = os.path.join(out, "pkg")
        report["export"] = SweepBuilder.run_tool(opts["--blender"], os.path.join(mf, "export_map.py"), ["--spec", spec_path, "--props", props, "--textures", tex, "--out", pkg])
        report["inspect"] = SweepBuilder.run_tool(opts["--blender"], os.path.join(mf, "inspect_map.py"), ["--dir", os.path.join(pkg, "stream"), "--spec", spec_path, "--json", os.path.join(out, "inspect_report.json")])
    with open(os.path.join(out, "sweep_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)
    print("SWEEP_REPORT " + json.dumps({k: (v["tris"], v.get("normal_err_vertex_max_deg"), v.get("normal_err_interior_p95_deg"), v["dihedral"]["smooth_p90"]) for k, v in report["shells"].items()}), flush=True)


if __name__ == "__main__":
    main()
