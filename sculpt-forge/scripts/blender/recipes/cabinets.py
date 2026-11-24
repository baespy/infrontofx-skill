import argparse
import importlib
import inspect
import json
import math
import os
import subprocess
import sys
import time

import bmesh
import bpy
import numpy as np


class EngineLoader:
    @staticmethod
    def folder(explicit=None):
        candidates = []
        if explicit:
            path = os.path.abspath(explicit)
            candidates.append(os.path.dirname(path) if path.lower().endswith(".py") else path)
        here = globals().get("__file__")
        if here:
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(here)), ".."))
        candidates.append(os.environ.get("SCULPT_FORGE_SCRIPTS", ""))
        candidates.append(os.path.join(os.path.expanduser("~"), ".claude", "skills", "infrontofx", "sculpt-forge", "scripts", "blender"))
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

    @staticmethod
    def compatible(engine):
        needs = {
            "reduce": ("high", "owners"),
            "protection": ("me", "points", "radius", "detail_owners"),
            "clean_collapse": ("source", "target", "radius", "detail_owners", "attempts"),
            "snap_role_lines": ("me", "high"),
            "relabel_faces": ("me",),
            "discard": ("ob",),
        }
        cls = getattr(engine, "SculptBuilder", None)
        if cls is None or not hasattr(engine, "MeshArrays"):
            return False
        for name, params in needs.items():
            method = getattr(cls, name, None)
            if method is None:
                return False
            found = tuple(inspect.signature(method).parameters)[1:1 + len(params)]
            if found != params:
                return False
        return True

    @staticmethod
    def builder_class(engine, hold=True, settings=None):
        if not hold or not EngineLoader.compatible(engine):
            return engine.SculptBuilder
        attrs = {"engine": engine}
        attrs.update({key: value for key, value in (settings or {}).items() if key in PlanarHoldMixin.settings})
        return type("CabinetSculptBuilder", (PlanarHoldMixin, engine.SculptBuilder), attrs)


class PlanarHoldMixin:
    settings = ("hold_angle", "hold_area", "hold_share", "hold_reach", "hold_tilt", "hold_flat")
    hold_angle = 2.0
    hold_area = 0.01
    hold_share = 0.15
    hold_reach = 0.02
    hold_tilt = 1.0
    hold_flat = None
    hold_pins = None
    hold_count = -1

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
            index = index[PlanarHoldMixin.thin(coords, max(16, int(self.hold_share * limit)))]
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


class CabinetMath:
    @staticmethod
    def edge_radius(size, pct, floor=0.012):
        return max(float(floor), float(pct) * float(min(size)))

    @staticmethod
    def rect(w, h, r, at, plane="XY"):
        return {"shape": "rounded_rect", "w": float(w), "h": float(h), "r": float(max(0.002, min(r, 0.5 * w - 0.002, 0.5 * h - 0.002))), "plane": plane, "at": [float(v) for v in at]}

    @staticmethod
    def u_outline(width, length, samples=14, lift=0.03):
        r = 0.5 * float(width)
        straight = max(float(length) - r, 0.002)
        pts = [(-r, float(lift)), (-r, -straight)]
        for i in range(1, samples):
            a = math.pi + math.pi * i / float(samples)
            pts.append((r * math.cos(a), -straight + r * math.sin(a)))
        pts.append((r, -straight))
        pts.append((r, float(lift)))
        return [[round(u, 6), round(v, 6)] for u, v in pts]

    @staticmethod
    def arc_points(center, radius, a0, a1, count, z):
        out = []
        for i in range(int(count) + 1):
            a = math.radians(a0 + (a1 - a0) * i / float(count))
            out.append((center[0] + radius * math.cos(a), center[1] + radius * math.sin(a), z))
        return out

    @staticmethod
    def wrap_path(width, front_y, back_y, z, corner):
        half = 0.5 * float(width)
        pts = [(-half, back_y, z)]
        pts.extend(CabinetMath.arc_points((-half + corner, front_y + corner), corner, 180.0, 270.0, 3, z))
        pts.extend(CabinetMath.arc_points((half - corner, front_y + corner), corner, 270.0, 360.0, 3, z))
        pts.append((half, back_y, z))
        return pts

    @staticmethod
    def grid_centres(count, size, gap):
        span = count * size + (count - 1) * gap
        return [-0.5 * span + 0.5 * size + i * (size + gap) for i in range(int(count))]

    @staticmethod
    def surface_area(size, extra=0.0):
        w, d, h = (float(v) for v in size)
        return 2.0 * (w * d + w * h + d * h) * (1.0 + float(extra))


class CabinetsRecipes:
    colors = {
        "cream": ("#FFFBF4", "satin"),
        "caramel": ("#C48E62", "satin"),
        "ink": ("#3B281E", "matte"),
        "outline": ("#4A3327", "matte"),
        "honey": ("#E8B04B", "satin"),
        "pink": ("#F2B8C6", "satin"),
        "mint": ("#A8D8C8", "satin"),
        "sky": ("#A9CBEA", "satin"),
        "gold": ("#D9A441", "gloss"),
        "glass": ("#D6EAF4", "gloss"),
        "screen": ("#FFE9BC", "emissive"),
    }
    themes = {
        "house": {"shell": "cream", "body": "caramel", "panel": "caramel", "trim": "caramel", "base": "outline", "frost": "cream", "metal": "gold", "accent": "honey", "ink": "ink", "line": "outline", "glass": "glass", "screen": "screen", "key": "cream", "ok": "mint", "clear": "honey", "cancel": "pink", "stripe_a": "honey", "stripe_b": "cream", "post": "honey", "guard": "cream", "cap": "outline", "letter": "cream", "relief": "honey", "door": "caramel", "collar": "gold", "lid": "caramel"},
        "pastel": {"shell": "cream", "body": "pink", "panel": "pink", "trim": "mint", "base": "outline", "frost": "cream", "metal": "gold", "accent": "honey", "ink": "ink", "line": "outline", "glass": "glass", "screen": "screen", "key": "cream", "ok": "mint", "clear": "honey", "cancel": "pink", "stripe_a": "pink", "stripe_b": "cream", "post": "mint", "guard": "cream", "cap": "outline", "letter": "cream", "relief": "honey", "door": "pink", "collar": "mint", "lid": "sky"},
    }

    def __init__(self, theme="house", roles=None, font=None):
        self.theme = dict(self.themes.get(theme, self.themes["house"]))
        self.theme.update(roles or {})
        self.font = font

    def slots(self, roles=None):
        out = dict(self.theme)
        out.update(roles or {})
        return out

    def palette(self, cell_px=32):
        return {"cell_px": int(cell_px), "roles": {name: {"color": spec[0], "finish": spec[1]} for name, spec in self.colors.items()}}

    @staticmethod
    def suggest_budget(area_m2, density=560.0, extra=0.15, minimum=1800):
        return max(int(minimum), int(round(float(area_m2) * (1.0 + float(extra)) * float(density) / 100.0)) * 100)

    @staticmethod
    def add_collider(b, center, size, store):
        b.collider(center, size)
        store.append({"center": [round(float(v), 4) for v in center], "size": [round(float(v), 4) for v in size]})

    def body(self, b, size, base_z=0.0, center=(0.0, 0.0), radius=None, radius_pct=0.085, puff=0.0, role=None, fillet=0.0, collide=False):
        w, d, h = (float(v) for v in size)
        r = float(radius) if radius is not None else CabinetMath.edge_radius(size, radius_pct)
        return b.pillow_box((w, d, h), radius=r, puff=puff, loc=(center[0], center[1], base_z + 0.5 * h), role=role or self.theme["shell"], fillet=fillet, collide=collide)

    def plinth(self, b, size, base_z=0.0, center=(0.0, 0.0), roll=0.45, role=None, fillet=0.0):
        w, d, h = (float(v) for v in size)
        return b.round_box((w, d, h), radius=roll * min(h, w, d), loc=(center[0], center[1], base_z + 0.5 * h), role=role or self.theme["base"], fillet=fillet)

    def panel(self, b, center, size, face_y, depth=0.02, corner=0.03, edge=None, puff=0.0, embed=0.015, role=None, fillet=0.01, op="union", detail=False):
        x, z = center
        w, h = size
        total = float(depth) + float(embed)
        rim = min(float(edge if edge is not None else 0.45 * depth), 0.5 * total - 0.001)
        y_mid = face_y - float(depth) + 0.5 * total
        return b.extrude2d({"shape": "rounded_rect", "w": float(w), "h": float(h), "r": float(min(corner, 0.5 * w - 0.003, 0.5 * h - 0.003))}, depth=total, edge=rim, puff=puff, back_puff=False, plane="XZ", loc=(x, y_mid, z), role=role, fillet=fillet, op=op, detail=detail)

    def pocket(self, b, center, size, floor_y, corner=0.03, rim=0.008, role=None, op="subtract"):
        x, z = center
        w, h = size
        return b.extrude2d({"shape": "rounded_rect", "w": float(w), "h": float(h), "r": float(min(corner, 0.5 * w - 0.003, 0.5 * h - 0.003))}, depth=0.3, edge=0.0, plane="XZ", loc=(x, floor_y - 0.15, z), role=role or self.theme["ink"], op=op, fillet=rim if op == "subtract" else 0.0)

    def recessed_screen(self, b, center, size, face_y, depth=0.02, bezel=0.04, bezel_depth=0.028, corner=0.03, rim=0.008, gap=0.012, roles=None, fillet=0.012):
        s = self.slots(roles)
        w, h = size
        frame = self.panel(b, center, (w + 2.0 * bezel, h + 2.0 * bezel), face_y, depth=bezel_depth, corner=corner + 0.6 * bezel, edge=0.42 * bezel_depth, embed=0.02, role=s["ink"], fillet=fillet)
        floor_y = face_y - bezel_depth + depth
        cut = self.pocket(b, center, (w, h), floor_y, corner=corner, rim=rim, role=s["ink"])
        glass = self.panel(b, center, (w - 2.0 * gap, h - 2.0 * gap), floor_y, depth=0.006, corner=max(corner - gap, 0.008), edge=0.003, embed=0.006, role=s["screen"], fillet=0.003)
        return {"bezel": frame, "recess": cut, "screen": glass}

    def keypad(self, b, center, face_y, cols=3, rows=4, key=(0.054, 0.036), gap=0.012, key_depth=0.016, margin=0.024, plate_depth=0.022, side_keys=3, side_key=(0.07, 0.042), side_gap=0.024, roles=None, fillet=0.01):
        s = self.slots(roles)
        x, z = center
        kw, kh = key
        block_w = cols * kw + (cols - 1) * gap
        block_h = rows * kh + (rows - 1) * gap
        side_w = side_key[0] if side_keys else 0.0
        side_h = side_keys * side_key[1] + (side_keys - 1) * gap if side_keys else 0.0
        inner_w = block_w + (side_gap + side_w if side_keys else 0.0)
        inner_h = max(block_h, side_h)
        plate = self.panel(b, center, (inner_w + 2.0 * margin, inner_h + 2.0 * margin), face_y, depth=plate_depth, corner=0.03, edge=0.45 * plate_depth, embed=0.02, role=s["panel"], fillet=fillet)
        front = face_y - plate_depth
        left = x - 0.5 * inner_w
        keys = []
        soft = 0.48 * min(kh, 2.0 * key_depth)
        with b.group("keys", fillet=0.004):
            for c, kx in enumerate(CabinetMath.grid_centres(cols, kw, gap)):
                for r, kz in enumerate(CabinetMath.grid_centres(rows, kh, gap)):
                    keys.append(b.round_box((kw, 2.0 * key_depth, kh), radius=soft, loc=(left + 0.5 * block_w + kx, front, z - kz), role=s["key"], detail=True))
            accents = [s["ok"], s["clear"], s["cancel"]]
            side_soft = 0.48 * min(side_key[1], 2.0 * key_depth)
            for i, kz in enumerate(CabinetMath.grid_centres(side_keys, side_key[1], gap)):
                keys.append(b.round_box((side_key[0], 2.0 * key_depth, side_key[1]), radius=side_soft, loc=(left + inner_w - 0.5 * side_w, front, z - kz), role=accents[i % len(accents)], detail=True))
        return {"plate": plate, "keys": keys, "size": (inner_w + 2.0 * margin, inner_h + 2.0 * margin)}

    def slot_module(self, b, center, face_y, size=(0.12, 0.07), depth=0.026, slit=(0.08, 0.012), slit_depth=0.016, corner=None, roles=None, fillet=0.01):
        s = self.slots(roles)
        w, h = size
        lip = self.panel(b, center, (w, h), face_y, depth=depth, corner=corner if corner is not None else 0.45 * h, edge=0.45 * depth, embed=0.015, role=s["accent"], fillet=fillet)
        floor_y = face_y - depth + slit_depth
        cut = self.pocket(b, center, slit, floor_y, corner=0.45 * slit[1], rim=0.003, role=s["ink"])
        return {"lip": lip, "slit": cut}

    def letters(self, b, body, center, face_y, height=0.15, depth=0.026, puff=0.010, outline=0.014, outline_depth=0.012, lift=0.013, rise=0.022, max_width=None, roles=None, fillet=0.006):
        s = self.slots(roles)
        x, z = center
        loc_o = face_y - lift + 0.5 * outline_depth + puff + outline
        loc_l = face_y - lift - rise + 0.5 * depth + puff
        back = b.text(body, font=self.font, height=height, max_width=max_width, depth=outline_depth, puff=puff + outline, plane="XZ", loc=(x, loc_o, z), role=s["line"], fillet=fillet)
        front = b.text(body, font=self.font, height=height, max_width=max_width, depth=depth, puff=puff, plane="XZ", loc=(x, loc_l, z), role=s["letter"], fillet=0.8 * fillet)
        return {"outline": back, "letters": front}

    def beads(self, b, points, radius=0.019, closed=False, pitch=1.9, blend=0.3, role=None, fillet=0.008, detail=False):
        return b.beads([tuple(float(v) for v in p) for p in points], float(radius), spacing=float(pitch) * float(radius), closed=closed, blend=float(blend) * float(radius), role=role or self.theme["metal"], fillet=fillet, detail=detail)

    def relief(self, b, shape, center, face_y, depth=0.024, edge=0.01, puff=0.006, embed=0.01, role=None, fillet=0.008, plane="XZ", rot=(0.0, 0.0, 0.0)):
        x, z = center
        return b.extrude2d(shape, depth=float(depth) + float(embed), edge=float(edge), puff=float(puff), back_puff=False, plane=plane, loc=(x, face_y - 0.5 * (float(depth) - float(embed)), z), rot=rot, role=role or self.theme["relief"], fillet=fillet)

    def icing_cap(self, b, size, top_z, center=(0.0, 0.0), thickness=0.052, overhang=0.03, sink=0.012, lobes_per_m=6.0, amp=0.022, dome=0.01, roles=None, fillet=0.02):
        s = self.slots(roles)
        w, d = size
        corner = min(0.2 * min(w, d), 0.12)
        outline = {"shape": "scalloped_rect", "w": float(w) + 2.0 * overhang, "h": float(d) + 2.0 * overhang, "r": float(corner + overhang), "lobes_per_m": float(lobes_per_m), "amp": float(amp)}
        return b.extrude2d(outline, depth=thickness, edge=0.44 * thickness, puff=dome, back_puff=False, plane="XY", loc=(center[0], center[1], top_z - sink + 0.5 * thickness), role=s["frost"], fillet=fillet)

    def edge_drips(self, b, size, top_z, center=(0.0, 0.0), offset=0.012, front=(2, 0.34), sides=3, back=3, length=(0.10, 0.22), radius=(0.023, 0.032), seed=5, roles=None, fillet=0.016):
        s = self.slots(roles)
        w, d = size
        cx, cy = center
        half_w = 0.5 * float(w) + offset
        half_d = 0.5 * float(d) + offset
        inner = 0.5 * float(w) - 0.08
        runs = []
        count, gap = front
        if count:
            each = max(1, int(count) // 2)
            runs.append(([(cx - inner, cy - half_d, top_z), (cx - 0.5 * gap, cy - half_d, top_z)], each))
            runs.append(([(cx + 0.5 * gap, cy - half_d, top_z), (cx + inner, cy - half_d, top_z)], int(count) - each))
        if sides:
            runs.append(([(cx - half_w, cy - 0.5 * d + 0.08, top_z), (cx - half_w, cy + 0.5 * d - 0.08, top_z)], int(sides)))
            runs.append(([(cx + half_w, cy + 0.5 * d - 0.08, top_z), (cx + half_w, cy - 0.5 * d + 0.08, top_z)], int(sides)))
        if back:
            runs.append(([(cx + inner, cy + half_d, top_z), (cx - inner, cy + half_d, top_z)], int(back)))
        made = []
        for i, (path, n) in enumerate(runs):
            if n > 0:
                made.append(b.drips(path, n, length=length, radius=radius, closed=False, seed=int(seed) + 11 * i, jitter=0.3, sink=0.0, role=s["frost"], fillet=fillet))
        return made

    def cape_runs(self, b, size, top_z, center=(0.0, 0.0), drop=(0.62, 0.5), radius=(0.036, 0.03, 0.025), inset=0.014, roles=None, fillet=0.018):
        s = self.slots(roles)
        w, d = size
        cx, cy = center
        made = []
        for side, length in ((-1.0, drop[0]), (1.0, drop[1])):
            x = cx + side * (0.5 * w - inset)
            y = cy - 0.5 * d + inset
            path = [(x, y, top_z + 0.01), (x + side * 0.004, y - 0.003, top_z - 0.35 * length), (x - side * 0.002, y - 0.002, top_z - 0.7 * length), (x, y, top_z - length)]
            made.append(b.tube(path, list(radius), closed=False, ends=1.2, role=s["frost"], fillet=fillet))
        return made

    def awning(self, b, width, top_z, front_y, depth_back, stripes=9, length=0.27, thickness=0.05, tilt=24.0, wrap=2, puff=0.014, roll=0.0, roles=None, fillet=0.003):
        s = self.slots(roles)
        sw = float(width) / int(stripes)
        outline = CabinetMath.u_outline(sw + 0.006, length)
        rim = 0.42 * thickness
        made = []
        with b.group("awning_front", fillet=fillet):
            for i in range(int(stripes)):
                x = -0.5 * width + sw * (i + 0.5)
                role = s["stripe_a"] if i % 2 == 0 else s["stripe_b"]
                made.append(b.extrude2d(outline, depth=thickness, edge=rim, puff=puff, plane="XZ", rot=(-tilt, 0.0, 0.0), loc=(x, front_y, top_z), role=role))
        if wrap:
            with b.group("awning_sides", fillet=fillet):
                for j in range(int(wrap)):
                    y = front_y + sw * (j + 0.5) + 0.5 * thickness
                    role = s["stripe_b"] if j % 2 == 0 else s["stripe_a"]
                    made.append(b.extrude2d(outline, depth=thickness, edge=rim, puff=puff, plane="YZ", rot=(0.0, tilt, 0.0), loc=(-0.5 * width, y, top_z), role=role, mirror_x=True))
        tube = None
        if roll:
            back = front_y + sw * int(wrap) + thickness
            path = CabinetMath.wrap_path(width + 0.5 * thickness, front_y - 0.35 * thickness, back, top_z - 0.032, 0.07)
            tube = b.tube(path, float(roll), closed=False, ends=1.0, role=s["trim"], fillet=0.01)
        return {"stripes": made, "roll": tube, "stripe_width": sw}

    def corner_caps(self, b, size, base_z, center=(0.0, 0.0), cap=0.13, radius=0.045, proud=0.018, levels=("bottom", "top"), role=None, fillet=0.01):
        w, d, h = (float(v) for v in size)
        cx, cy = center
        x = cx + 0.5 * w - 0.5 * cap + proud
        made = []
        for level in levels:
            z = base_z + (0.5 * cap - proud if level == "bottom" else h - 0.5 * cap + proud)
            for sy in (-1.0, 1.0):
                y = cy + sy * (0.5 * d - 0.5 * cap + proud)
                made.append(b.pillow_box((cap, cap, cap), radius=radius, puff=0.006, loc=(x, y, z), role=role or self.theme["cap"], fillet=fillet, mirror_x=True))
        return made

    def edge_guards(self, b, size, base_z, center=(0.0, 0.0), guard=0.08, proud=0.012, cap=0.13, rails=True, mid=None, role=None, fillet=0.008, roll=0.3):
        w, d, h = (float(v) for v in size)
        cx, cy = center
        r = float(roll) * guard
        role = role or self.theme["guard"]
        made = []
        x = cx + 0.5 * w - 0.5 * guard + proud
        span_z = h - 2.0 * cap + 0.04
        for sy in (-1.0, 1.0):
            y = cy + sy * (0.5 * d - 0.5 * guard + proud)
            made.append(b.round_box((guard, guard, span_z), radius=r, loc=(x, y, base_z + 0.5 * h), role=role, fillet=fillet, mirror_x=True))
        if rails:
            span_x = w - 2.0 * cap + 0.04
            span_y = d - 2.0 * cap + 0.04
            for z in (base_z + 0.5 * guard - proud, base_z + h - 0.5 * guard + proud):
                for sy in (-1.0, 1.0):
                    made.append(b.round_box((span_x, guard, guard), radius=r, loc=(cx, cy + sy * (0.5 * d - 0.5 * guard + proud), z), role=role, fillet=fillet))
                made.append(b.round_box((guard, span_y, guard), radius=r, loc=(cx + 0.5 * w - 0.5 * guard + proud, cy, z), role=role, fillet=fillet, mirror_x=True))
        if mid is not None:
            band = 0.045
            made.append(b.round_box((w + 2.0 * 0.008, d + 2.0 * 0.008, band), radius=0.5 * band - 0.002, loc=(cx, cy, base_z + mid), role=role, fillet=fillet))
        return made

    def rivets(self, b, points, radius=0.012, sink=0.4, normal=(0.0, -1.0, 0.0), role=None, mirror_x=True, fillet=0.004):
        n = np.asarray(normal, np.float64)
        made = []
        for p in points:
            c = np.asarray(p, np.float64) - n * (sink * radius)
            made.append(b.sphere(float(radius), loc=tuple(c.tolist()), role=role or self.theme["metal"], fillet=fillet, mirror_x=mirror_x))
        return made

    def atm(self, b, width=0.78, depth=0.6, height=1.62, plinth=0.12, radius_pct=0.09, label="ATM", beads=False, roles=None, seed=5):
        s = self.slots(roles)
        colliders = []
        top = height - 0.055
        body_h = top - plinth + 0.02
        face_y = -0.5 * depth
        parts = {}
        with b.group("shell", fillet=0.024):
            parts["plinth"] = self.plinth(b, (width + 0.1, depth + 0.1, plinth), role=s["base"])
            parts["body"] = self.body(b, (width, depth, body_h), base_z=plinth - 0.02, radius_pct=radius_pct, role=s["body"], fillet=0.024)
        with b.group("front", fillet=0.012):
            parts["screen"] = self.recessed_screen(b, (0.0, 1.08 * height / 1.62), (0.44, 0.3), face_y, roles=s)
            parts["keypad"] = self.keypad(b, (-0.055, 0.735 * height / 1.62), face_y, roles=s)
            parts["card"] = self.slot_module(b, (0.255, 0.78 * height / 1.62), face_y, size=(0.1, 0.1), slit=(0.064, 0.012), corner=0.03, roles=s)
            parts["cash"] = self.slot_module(b, (0.0, 0.47 * height / 1.62), face_y, size=(0.38, 0.078), slit=(0.3, 0.018), roles=s)
            parts["heart"] = self.relief(b, {"shape": "heart", "size": 0.1, "smooth": 2}, (0.0, plinth + 0.13), face_y, depth=0.022, edge=0.009, puff=0.005, role=s["relief"])
        with b.group("label", fillet=0.006):
            parts["label"] = self.letters(b, label, (0.0, top - 0.165), face_y, height=0.16, depth=0.024, puff=0.008, outline=0.011, max_width=0.46, roles=s)
        with b.group("icing", fillet=0.02):
            parts["cap"] = self.icing_cap(b, (width, depth), top, roles=s)
            parts["drips"] = self.edge_drips(b, (width, depth), top - 0.012, front=(2, 0.5), sides=3, back=3, seed=seed, roles=s)
            parts["cape"] = self.cape_runs(b, (width, depth), top - 0.01, drop=(0.58, 0.46), roles=s)
        if beads:
            parts["beads"] = self.beads(b, [(-0.5 * width + 0.06, face_y - 0.008, plinth + 0.006), (0.5 * width - 0.06, face_y - 0.008, plinth + 0.006)], radius=0.019, role=s["metal"])
        self.add_collider(b, (0.0, 0.0, 0.5 * (height + 0.02)), (width + 0.1, depth + 0.1, height + 0.02), colliders)
        parts["colliders"] = colliders
        return parts

    def claw_machine(self, b, width=0.72, depth=0.66, base_h=0.9, dome=0.31, plinth=0.09, radius_pct=0.12, roles=None):
        s = self.slots(roles)
        colliders = []
        face_y = -0.5 * depth
        top = plinth - 0.02 + base_h
        parts = {}
        with b.group("base", fillet=0.026):
            parts["plinth"] = self.plinth(b, (width + 0.08, depth + 0.08, plinth), role=s["trim"])
            parts["body"] = self.body(b, (width, depth, base_h), base_z=plinth - 0.02, radius_pct=radius_pct, role=s["body"], fillet=0.026)
        chute_z = plinth + 0.2
        with b.group("front", fillet=0.012):
            parts["chute_frame"] = self.panel(b, (0.0, chute_z), (0.32, 0.25), face_y, depth=0.024, corner=0.07, edge=0.011, embed=0.02, role=s["accent"], fillet=0.012)
        with b.group("chute_cut", fillet=0.012, op="subtract"):
            parts["chute"] = self.pocket(b, (0.0, chute_z), (0.24, 0.17), face_y + 0.07, corner=0.05, role=s["ink"], op="union")
        with b.group("globe", fillet=0.02):
            centre_z = top + 0.68 * dome
            parts["dome"] = b.sphere(dome, loc=(0.0, 0.0, centre_z), role=s["glass"])
            ring = math.sqrt(max(dome * dome - (0.68 * dome - 0.012) ** 2, 0.01))
            parts["collar"] = b.torus(ring, 0.034, loc=(0.0, 0.0, top + 0.012), role=s["collar"], fillet=0.012)
            lid_z = centre_z + 0.9 * dome
            parts["lid"] = b.round_cyl(0.5 * dome, 0.085, edge=0.036, loc=(0.0, 0.0, lid_z), role=s["lid"], fillet=0.02)
            parts["lid_ring"] = b.torus(0.5 * dome, 0.022, loc=(0.0, 0.0, lid_z - 0.03), role=s["collar"], fillet=0.01)
            parts["knob"] = b.sphere(0.058, loc=(0.0, 0.0, lid_z + 0.075), role=s["accent"], fillet=0.022)
        with b.group("controls", fillet=0.012):
            parts["flap"] = self.panel(b, (0.0, chute_z + 0.025), (0.21, 0.1), face_y + 0.07, depth=0.02, corner=0.04, edge=0.008, puff=0.006, embed=0.01, role=s["trim"], fillet=0.006)
            crank_z = plinth + 0.52
            parts["crank_disc"] = b.round_cyl(0.088, 0.05, edge=0.018, loc=(0.0, face_y - 0.012, crank_z), rot=(90.0, 0.0, 0.0), role=s["metal"], fillet=0.012)
            parts["crank_bar"] = b.capsule((-0.07, face_y - 0.05, crank_z), (0.07, face_y - 0.05, crank_z), 0.022, role=s["accent"], fillet=0.012)
            parts["crank_hub"] = b.sphere(0.032, loc=(0.0, face_y - 0.058, crank_z), role=s["metal"], fillet=0.01)
            parts["coin"] = self.slot_module(b, (0.235, crank_z + 0.01), face_y, size=(0.075, 0.12), slit=(0.012, 0.06), corner=0.03, roles=s)
        with b.group("sides", fillet=0.01):
            star = {"shape": "star", "r_out": 0.11, "r_in": 0.058, "points": 5, "smooth": 3}
            parts["stars"] = b.extrude2d(star, depth=0.04, edge=0.012, puff=0.006, back_puff=False, plane="YZ", loc=(-0.5 * width - 0.006, 0.0, plinth + 0.47), role=s["relief"], fillet=0.01, mirror_x=True)
        height = top + 1.62 * dome + 0.13
        self.add_collider(b, (0.0, 0.0, 0.5 * (top + 0.02)), (width + 0.08, depth + 0.08, top + 0.02), colliders)
        self.add_collider(b, (0.0, 0.0, 0.5 * (top + height)), (2.0 * dome, 2.0 * dome, height - top), colliders)
        parts["colliders"] = colliders
        return parts

    def market_kiosk(self, b, width=1.36, depth=0.76, counter=1.0, roof_z=2.06, roof_h=0.16, plinth=0.1, stripes=9, label="SHOP", beads=True, roles=None):
        s = self.slots(roles)
        colliders = []
        face_y = -0.5 * depth
        parts = {}
        top_z = counter + 0.07
        with b.group("counter", fillet=0.026):
            parts["plinth"] = self.plinth(b, (width + 0.1, depth + 0.1, plinth), role=s["base"])
            parts["body"] = self.body(b, (width, depth, counter - plinth + 0.04), base_z=plinth - 0.02, radius_pct=0.085, role=s["shell"], fillet=0.026)
            parts["top"] = b.round_box((width + 0.12, depth + 0.12, 0.075), radius=0.033, loc=(0.0, 0.0, counter + 0.035), role=s["trim"], fillet=0.02)
        pz = plinth + 0.5 * (counter - plinth)
        ph = counter - plinth - 0.2
        with b.group("front_cut", fillet=0.009, op="subtract"):
            parts["pocket"] = self.pocket(b, (0.0, pz), (width - 0.26, ph), face_y + 0.016, corner=0.05, role=s["shell"], op="union")
        with b.group("front_panel", fillet=0.01):
            parts["pillow"] = b.pillow_box((width - 0.31, 0.05, ph - 0.05), radius=0.022, puff=(0.0, 0.014, 0.0), loc=(0.0, face_y + 0.012, pz), role=s["panel"], fillet=0.006)
            parts["star"] = self.relief(b, {"shape": "star", "r_out": 0.14, "r_in": 0.08, "points": 5, "smooth": 3}, (0.0, pz), face_y - 0.026, depth=0.024, edge=0.011, puff=0.006, embed=0.02, role=s["relief"], fillet=0.01)
        with b.group("posts", fillet=0.02):
            post_h = roof_z - top_z + 0.04
            for sy in (-1.0, 1.0):
                parts["post_{}".format(int(sy))] = b.round_cyl(0.042, post_h, edge=0.01, loc=(0.5 * width - 0.07, sy * (0.5 * depth - 0.07), top_z + 0.5 * post_h - 0.02), role=s["post"], mirror_x=True)
                parts["foot_{}".format(int(sy))] = b.sphere(0.058, loc=(0.5 * width - 0.07, sy * (0.5 * depth - 0.07), top_z + 0.01), role=s["post"], fillet=0.02, mirror_x=True)
        with b.group("roof", fillet=0.024):
            parts["roof"] = b.pillow_box((width + 0.16, depth + 0.16, roof_h), radius=0.06, puff=(0.006, 0.006, 0.02), loc=(0.0, 0.0, roof_z + 0.5 * roof_h), role=s["trim"])
            sign_z = roof_z + roof_h + 0.15
            parts["sign"] = b.extrude2d({"shape": "rounded_rect", "w": 0.78, "h": 0.28, "r": 0.1}, depth=0.08, edge=0.034, puff=0.008, plane="XZ", loc=(0.0, 0.0, sign_z), role=s["body"], fillet=0.03)
        with b.group("label", fillet=0.006):
            parts["label"] = self.letters(b, label, (0.0, sign_z), -0.04, height=0.15, max_width=0.62, roles=s)
        parts["awning"] = self.awning(b, width + 0.16, roof_z + 0.035, face_y - 0.08, depth + 0.16, stripes=stripes, roles=s)
        if beads:
            y = face_y - 0.044
            parts["beads"] = self.beads(b, [(-0.5 * width - 0.01, y, counter - 0.012), (0.5 * width + 0.01, y, counter - 0.012)], radius=0.019, role=s["metal"])
        self.add_collider(b, (0.0, 0.0, 0.5 * (top_z + 0.005)), (width + 0.12, depth + 0.12, top_z + 0.005), colliders)
        self.add_collider(b, (0.0, -0.04, roof_z + 0.5 * (roof_h + 0.33)), (width + 0.2, depth + 0.28, roof_h + 0.33), colliders)
        parts["colliders"] = colliders
        return parts

    def flight_case(self, b, width=1.2, depth=0.62, height=0.96, lift=0.03, radius_pct=0.06, roles=None, guard_roll=0.42, cap_radius=0.045, guard=0.08, guard_rails=True, rivet_radius=0.018, pin_radius=0.012):
        s = self.slots(roles)
        colliders = []
        face_y = -0.5 * depth
        size = (width, depth, height)
        parts = {}
        with b.group("case", fillet=0.012):
            parts["body"] = self.body(b, size, base_z=lift, radius_pct=radius_pct, role=s["body"])
            parts["guards"] = self.edge_guards(b, size, lift, guard=guard, rails=guard_rails, mid=0.76 * height, role=s["guard"], roll=guard_roll)
            parts["caps"] = self.corner_caps(b, size, lift, radius=cap_radius, role=s["cap"])
        pz = lift + 0.4 * height
        hz = lift + 0.55 * height
        with b.group("cuts", fillet=0.008, op="subtract"):
            parts["pocket"] = self.pocket(b, (0.0, pz), (width - 0.36, 0.42 * height), face_y + 0.014, corner=0.05, role=s["body"], op="union")
            parts["handle_dish"] = b.extrude2d({"shape": "rounded_rect", "w": 0.24, "h": 0.1, "r": 0.045}, depth=0.08, edge=0.0, plane="YZ", loc=(-0.5 * width - 0.022, 0.0, hz), role=s["ink"], mirror_x=True)
        with b.group("front", fillet=0.01):
            parts["pillow"] = b.pillow_box((width - 0.41, 0.05, 0.42 * height - 0.05), radius=0.022, puff=(0.0, 0.016, 0.0), loc=(0.0, face_y + 0.01, pz), role=s["panel"], fillet=0.006)
            parts["star"] = self.relief(b, {"shape": "star", "r_out": 0.13, "r_in": 0.074, "points": 5, "smooth": 3}, (0.0, pz), face_y - 0.03, depth=0.024, edge=0.011, puff=0.006, embed=0.02, role=s["relief"], fillet=0.01)
            lz = lift + 0.76 * height
            parts["latches"] = b.round_box((0.09, 0.05, 0.075), radius=0.02, loc=(0.26 * width, face_y - 0.01, lz), role=s["accent"], fillet=0.008, mirror_x=True)
            parts["latch_pins"] = b.capsule((0.26 * width - 0.03, face_y - 0.038, lz - 0.012), (0.26 * width + 0.03, face_y - 0.038, lz - 0.012), pin_radius, role=s["metal"], fillet=0.004, mirror_x=True)
            rz = [lift + 0.3 * height, lift + 0.5 * height]
            gx = 0.5 * width - guard - 0.032
            parts["rivets"] = self.rivets(b, [(gx, face_y, z) for z in rz], radius=rivet_radius, sink=0.35, role=s["metal"])
        with b.group("handles", fillet=0.01):
            parts["handle_bar"] = b.capsule((-0.5 * width + 0.004, -0.085, hz), (-0.5 * width + 0.004, 0.085, hz), 0.016, role=s["cap"], fillet=0.008, mirror_x=True)
        self.add_collider(b, (0.0, 0.0, 0.5 * (height + 2.0 * lift)), (width + 0.04, depth + 0.04, height + 2.0 * lift), colliders)
        parts["colliders"] = colliders
        return parts

    def cake_cabinet(self, b, width=0.84, depth=0.58, height=1.36, feet=0.08, radius_pct=0.1, beads=True, roles=None, bead_radius=0.03, bead_pitch=2.2, bead_drop=0.04, bead_proud=0.012, bead_detail=False):
        s = self.slots(roles)
        colliders = []
        face_y = -0.5 * depth
        parts = {}
        body_h = height - feet - 0.07
        crown_z = feet + body_h - 0.02
        with b.group("shell", fillet=0.024):
            parts["body"] = self.body(b, (width, depth, body_h), base_z=feet, radius_pct=radius_pct, role=s["shell"], fillet=0.024)
            parts["crown"] = b.pillow_box((width + 0.08, depth + 0.08, 0.09), radius=0.04, puff=(0.0, 0.0, 0.012), loc=(0.0, 0.0, crown_z + 0.045), role=s["trim"], fillet=0.024)
            for sy in (-1.0, 1.0):
                parts["foot_{}".format(int(sy))] = b.round_cyl(0.065, feet + 0.04, edge=0.032, loc=(0.5 * width - 0.11, sy * (0.5 * depth - 0.1), 0.5 * (feet + 0.04)), role=s["trim"], fillet=0.02, mirror_x=True)
        door_w = 0.5 * (width - 0.2) - 0.015
        door_h = body_h - 0.26
        door_z = feet + 0.5 * body_h - 0.01
        with b.group("door_cuts", fillet=0.008, op="subtract"):
            for sx in (-1.0, 1.0):
                x = sx * (0.5 * door_w + 0.022)
                parts["pocket_{}".format(int(sx))] = self.pocket(b, (x, door_z), (door_w, door_h), face_y + 0.018, corner=0.05, role=s["shell"], op="union")
        with b.group("doors", fillet=0.008):
            for sx in (-1.0, 1.0):
                x = sx * (0.5 * door_w + 0.022)
                parts["door_{}".format(int(sx))] = b.pillow_box((door_w - 0.05, 0.05, door_h - 0.05), radius=0.022, puff=(0.0, 0.016, 0.0), loc=(x, face_y + 0.014, door_z), role=s["door"], fillet=0.006)
                parts["heart_{}".format(int(sx))] = self.relief(b, {"shape": "heart", "size": 0.12, "smooth": 2}, (x, door_z + 0.2), face_y - 0.02, depth=0.024, edge=0.01, puff=0.005, embed=0.02, role=s["relief"], fillet=0.008)
            parts["knobs"] = b.sphere(0.026, loc=(0.045, face_y - 0.008, door_z - 0.02), role=s["metal"], fillet=0.008, mirror_x=True)
        if beads:
            y = face_y - float(bead_proud)
            parts["beads_top"] = self.beads(b, [(-0.5 * width + 0.02, y, crown_z - float(bead_drop)), (0.5 * width - 0.02, y, crown_z - float(bead_drop))], radius=bead_radius, pitch=bead_pitch, role=s["metal"], detail=bead_detail)
        self.add_collider(b, (0.0, 0.0, 0.5 * height), (width + 0.08, depth + 0.08, height), colliders)
        parts["colliders"] = colliders
        return parts


class CabinetDemo:
    def __init__(self, sf, recipes, out_dir, engine_dir, theme="house", hold=True):
        self.sf = sf
        self.recipes = recipes
        self.out = os.path.abspath(out_dir)
        self.engine_dir = engine_dir
        self.theme = theme
        self.hold = bool(hold)
        self.builder = EngineLoader.builder_class(sf, hold)
        self.blender = bpy.app.binary_path
        self.validate_script = os.path.join(engine_dir, "validate_sculpt.py")
        self.render_script = os.path.join(engine_dir, "render_sculpt.py")
        self.prop_script = os.path.normpath(os.path.join(engine_dir, "..", "..", "..", "prop-forge", "scripts", "blender", "validate_prop.py"))

    def specs(self):
        pastel = {"body": "pink", "trim": "mint", "collar": "cream", "lid": "mint", "accent": "honey", "relief": "honey", "glass": "glass"}
        return [
            {"id": "1nfx_cab_atm", "method": "atm", "kwargs": {}, "budget": 4200, "voxel": 0.005, "default_role": "caramel", "archetype": "atm", "lod": 120.0},
            {"id": "1nfx_cab_gacha", "method": "claw_machine", "kwargs": {"roles": pastel if self.theme == "house" else {}}, "budget": 3200, "voxel": 0.005, "default_role": "pink", "archetype": "gacha", "lod": 120.0},
            {"id": "1nfx_cab_kiosk", "method": "market_kiosk", "kwargs": {}, "budget": 8200, "voxel": 0.006, "default_role": "cream", "archetype": "kiosk", "lod": 150.0},
            {"id": "1nfx_cab_case", "method": "flight_case", "kwargs": {}, "budget": 3700, "voxel": 0.005, "default_role": "caramel", "archetype": "counter", "lod": 120.0, "hold": {"hold_reach": 0.0}},
            {"id": "1nfx_cab_cake", "method": "cake_cabinet", "kwargs": {}, "budget": 3400, "voxel": 0.005, "default_role": "cream", "archetype": "cabinet", "lod": 120.0, "hold": {"hold_flat": 0.001}},
        ]

    def build(self, spec, overrides):
        started = time.perf_counter()
        args = {"budget": spec["budget"], "voxel": spec["voxel"], "stage_ratio": 2.0}
        args.update({k: v for k, v in overrides.items() if v is not None})
        builder = EngineLoader.builder_class(self.sf, self.hold, spec.get("hold"))
        b = builder(spec["id"], size_class="hero", lod_dist=spec["lod"], set_name="1nfx_cab", archetype=spec["archetype"], palette=self.recipes.palette(), default_role=spec["default_role"], **args)
        parts = getattr(self.recipes, spec["method"])(b, **spec["kwargs"])
        result = b.build(self.out)
        metrics = result["metrics"]
        hold = next((json.loads(line.split(" ", 1)[1]) for line in b.log if line.startswith("planar_hold ")), None)
        entry = {"id": spec["id"], "method": spec["method"], "tris": result["tris"], "budget": result["budget"], "voxel": args["voxel"], "surface_m2": metrics["surface_m2"], "tris_per_m2": metrics["tris_per_m2"], "dihedral_p90": metrics["dihedral_deg"]["p90"], "size_m": result["size_m"], "colliders": parts["colliders"], "planar_hold": hold, "warnings": result["warnings"], "timings": result["timings"], "seconds": round(time.perf_counter() - started, 2), "blend": result["blend"], "high_blend": result["high_blend"]}
        print("CABINETS_BUILD " + json.dumps({k: entry[k] for k in ("id", "tris", "budget", "surface_m2", "tris_per_m2", "dihedral_p90", "seconds")}), flush=True)
        return entry

    def run_blender(self, script, args, log_path):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        cmd = [self.blender, "-b", "--factory-startup", "-t", str(max(1, int(bpy.context.scene.render.threads))), "-P", script, "--"] + [str(a) for a in args]
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
        print("CABINETS_QA {} {} ({}s)".format(prop_id, verdict, seconds), flush=True)
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
        warns = sum(int(f.split("warn=")[1].split()[0]) for f in files if "warn=" in f)
        print("CABINETS_PROP_CONTRACT {} warn={} ({}s)".format(total, warns, seconds), flush=True)
        return {"total": total, "files": files, "warn": warns}

    def render(self, qa_path):
        folder = os.path.join(self.out, "renders")
        args = ["--blend", self.out, "--out", folder]
        if qa_path:
            args += ["--qa", qa_path]
        code, lines, seconds = self.run_blender(self.render_script, args, os.path.join(self.out, "qa", "render.log"))
        verdict = next((line for line in reversed(lines) if line.startswith("SCULPT_RENDER ")), "SCULPT_RENDER missing")
        print("CABINETS_RENDER {} ({}s)".format(verdict, seconds), flush=True)
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
        report = {"out": self.out, "theme": self.theme, "blender": bpy.app.version_string, "builder": self.builder.__name__, "builds": [], "qa": [], "errors": []}
        for spec in self.specs():
            if only and spec["id"] not in only and spec["method"] not in only:
                continue
            try:
                report["builds"].append(self.build(spec, overrides or {}))
            except Exception as error:
                report["errors"].append("{}: {}: {}".format(spec["id"], type(error).__name__, error))
                print("CABINETS_FAIL {} {}: {}".format(spec["id"], type(error).__name__, error), flush=True)
        if qa and report["builds"]:
            merged = {"drawables": [], "fail": 0, "warn": 0}
            for entry in report["builds"]:
                result = self.validate(entry["id"])
                report["qa"].append({k: result[k] for k in ("id", "line", "fail", "warn", "issues")})
                merged["drawables"].extend(result["drawables"])
                merged["fail"] += result["fail"]
                merged["warn"] += result["warn"]
            qa_path = os.path.join(self.out, "qa", "cabinets_qa.json")
            with open(qa_path, "w", encoding="utf-8") as handle:
                json.dump(merged, handle, indent=1, default=str)
            report["qa_total"] = "SCULPT_QA fail={} warn={}".format(merged["fail"], merged["warn"])
            report["prop_contract"] = self.prop_contract()
            if renders:
                report["renders"] = self.render(qa_path)
        elif renders and report["builds"]:
            report["renders"] = self.render("")
        path = os.path.join(self.out, "cabinets_report.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        fails = len(report["errors"]) + sum(item["fail"] for item in report["qa"])
        print("CABINETS_DONE builds={} errors={} {} report={}".format(len(report["builds"]), len(report["errors"]), report.get("qa_total", "SCULPT_QA skipped"), path), flush=True)
        return fails, report


def main(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="cabinets.py")
    parser.add_argument("--out", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--theme", default="house", choices=["house", "pastel"])
    parser.add_argument("--engine", default="")
    parser.add_argument("--font", default="")
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--voxel", type=float, default=None)
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--no-qa", dest="no_qa", action="store_true")
    parser.add_argument("--no-render", dest="no_render", action="store_true")
    args = parser.parse_args(argv)
    if not args.out:
        print("CABINETS_USAGE blender -b --factory-startup -P cabinets.py -- --out <dir> [--only atm,claw_machine,market_kiosk,flight_case,cake_cabinet] [--theme house|pastel] [--plain] [--no-qa] [--no-render]", flush=True)
        return None
    engine_dir = EngineLoader.folder(args.engine or None)
    sf = EngineLoader.load(engine_dir)
    recipes = CabinetsRecipes(theme=args.theme, font=args.font or None)
    demo = CabinetDemo(sf, recipes, args.out, engine_dir, theme=args.theme, hold=not args.plain)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    fails, report = demo.run(only=only, overrides={"budget": args.budget, "voxel": args.voxel}, qa=not args.no_qa, renders=not args.no_render)
    if bpy.app.background:
        sys.stdout.flush()
        sys.exit(1 if fails else 0)
    return report


if __name__ == "__main__":
    main()
