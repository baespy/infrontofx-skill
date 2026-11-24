import argparse
import json
import math
import os
import re
import runpy
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


class QALimits:
    def __init__(self, target):
        self.target = target
        self.values = self.table(target)

    def __getitem__(self, key):
        return self.values[key]

    @staticmethod
    def table(target):
        values = {
            "weld_m": 1e-4,
            "split_tol_deg": 0.5,
            "fold_deg": 120.0,
            "fold_area_fail": 0.001,
            "fold_count_fail": 24,
            "split_share_warn": 0.02,
            "split_share_fail": 0.10,
            "soft_split_deg": 45.0,
            "dihedral_p90_warn": 30.0,
            "dihedral_p90_fail": 45.0,
            "over30_warn": 0.12,
            "over30_fail": 0.25,
            "over45_warn": 0.06,
            "sagitta_curve_min_deg": 2.0,
            "sagitta_curve_max_deg": 60.0,
            "sagitta_warn_mm": 3.0,
            "sagitta_fail_mm": 9.0,
            "panel_min_area_m2": 0.0025,
            "panel_min_width_m": 0.025,
            "panel_min_share": 0.02,
            "panel_warn_deg": 1.5,
            "panel_pillow_warn_deg": 12.0,
            "panel_crease_deg": 10.0,
            "normal_mean_warn_deg": 1.0,
            "normal_max_warn_deg": 10.0,
            "normal_mean_fail_deg": 2.0,
            "normal_p99_fail_deg": 10.0,
            "deviation_warn_mm": 1.0,
            "deviation_fail_mm": 3.0,
            "deviation_local_mm": 5.0,
            "split_ratio_warn": 2.5,
            "split_ratio_fail": 3.0,
            "shells_warn": 8,
            "density_low": 60.0,
            "density_high": 3000.0,
            "lump_fine_deg": 12.0,
            "lump_coarse_deg": 40.0,
            "lump_region_share": 0.02,
            "lump_min_coverage": 0.05,
            "lump_fine_warn": 1.0,
            "lump_fine_fail": 1.6,
            "lump_coarse_warn": 1.6,
            "lump_coarse_fail": 3.0,
            "max_tris": 0,
        }
        if target == "map":
            values.update({
                "split_share_warn": 0.40,
                "split_share_fail": 1.01,
                "dihedral_p90_fail": 1e9,
                "over30_fail": 1e9,
                "sagitta_warn_mm": 32.0,
                "sagitta_fail_mm": 120.0,
                "deviation_warn_mm": 5.0,
                "deviation_fail_mm": 15.0,
                "deviation_local_mm": 40.0,
                "split_ratio_warn": 2.8,
                "split_ratio_fail": 3.5,
                "shells_warn": 1000000,
                "max_tris": 40000,
            })
        return values


class QAReport:
    def __init__(self, file_path, drawable, target):
        self.file_path = file_path
        self.drawable = drawable
        self.target = target
        self.entries = []
        self.metrics = {}

    def add(self, level, key, text):
        self.entries.append({"level": level, "key": key, "text": text})

    def count(self, level):
        return sum(1 for entry in self.entries if entry["level"] == level)

    def lines(self):
        return ["{:<4} {}: {}".format(entry["level"], entry["key"], entry["text"]) for entry in self.entries]

    def to_dict(self):
        return {"file": self.file_path, "drawable": self.drawable, "target": self.target, "fail": self.count("FAIL"), "warn": self.count("WARN"), "checks": self.entries, "metrics": self.metrics}

    @staticmethod
    def grade(value, warn_limit, fail_limit):
        if fail_limit is not None and value > fail_limit:
            return "FAIL"
        if warn_limit is not None and value > warn_limit:
            return "WARN"
        return "OK"


class Statistics:
    @staticmethod
    def weighted_percentile(values, weights, quantile):
        if len(values) == 0:
            return 0.0
        order = np.argsort(values)
        cumulative = np.cumsum(weights[order]) / max(float(weights.sum()), 1e-30)
        return float(values[order][min(len(order) - 1, int(np.searchsorted(cumulative, quantile)))])

    @staticmethod
    def weighted_mean(values, weights):
        return float((values * weights).sum() / max(float(weights.sum()), 1e-30)) if len(values) else 0.0


class Components:
    @staticmethod
    def label(count, first, second):
        parent = np.arange(count, dtype=np.int64)
        if count == 0 or len(first) == 0:
            return parent
        while True:
            root_a = parent[first]
            root_b = parent[second]
            low = np.minimum(root_a, root_b)
            hooked = parent.copy()
            np.minimum.at(hooked, root_a, low)
            np.minimum.at(hooked, root_b, low)
            while True:
                jumped = hooked[hooked]
                if np.array_equal(jumped, hooked):
                    break
                hooked = jumped
            if np.array_equal(hooked, parent):
                break
            parent = hooked
        return np.unique(parent, return_inverse=True)[1].reshape(-1)


class MeshArrays:
    def __init__(self, ob):
        self.ob = ob
        self.mesh = ob.data
        me = self.mesh
        matrix = np.array(ob.matrix_world, dtype=np.float64)
        self.linear = matrix[:3, :3]
        self.offset = matrix[:3, 3]
        self.n_verts = len(me.vertices)
        self.n_loops = len(me.loops)
        self.n_polys = len(me.polygons)
        local = self.read(me.vertices, "co", np.float32, 3).astype(np.float64)
        self.co = local @ self.linear.T + self.offset
        self.loop_vert = self.read(me.loops, "vertex_index", np.int32, 1).astype(np.int64)
        self.poly_start = self.read(me.polygons, "loop_start", np.int32, 1).astype(np.int64)
        self.poly_total = self.read(me.polygons, "loop_total", np.int32, 1).astype(np.int64)
        self.poly_material = self.read(me.polygons, "material_index", np.int32, 1).astype(np.int64)
        self.poly_smooth = self.read_smooth(me)
        self.loop_poly = np.repeat(np.arange(self.n_polys, dtype=np.int64), self.poly_total)
        offsets = np.arange(self.n_loops, dtype=np.int64) - self.poly_start[self.loop_poly]
        self.loop_next = self.poly_start[self.loop_poly] + (offsets + 1) % np.maximum(self.poly_total[self.loop_poly], 1)
        self.compute_polygons()
        self.corner_normal = self.read_corner_normals(me)
        self.compute_triangles(me)

    @staticmethod
    def read(collection, attribute, dtype, width):
        buffer = np.empty(len(collection) * width, dtype=dtype)
        if len(collection):
            collection.foreach_get(attribute, buffer)
        return buffer.reshape(-1, width) if width > 1 else buffer

    @staticmethod
    def read_smooth(me):
        flags = np.ones(len(me.polygons), dtype=bool)
        try:
            me.polygons.foreach_get("use_smooth", flags)
            return flags
        except (AttributeError, TypeError, RuntimeError):
            pass
        attribute = me.attributes.get("sharp_face")
        if attribute is not None and attribute.domain == "FACE":
            sharp = np.zeros(len(me.polygons), dtype=bool)
            attribute.data.foreach_get("value", sharp)
            return ~sharp
        return flags

    @staticmethod
    def per_poly_sum(index, values, count):
        return np.stack([np.bincount(index, weights=values[:, axis], minlength=count) for axis in range(3)], axis=1)

    def compute_polygons(self):
        points = self.co[self.loop_vert]
        counts = np.maximum(self.poly_total, 1).astype(np.float64)
        centroid = self.per_poly_sum(self.loop_poly, points, self.n_polys) / counts[:, None]
        relative = points - centroid[self.loop_poly]
        cross = np.cross(relative, relative[self.loop_next])
        area_vector = 0.5 * self.per_poly_sum(self.loop_poly, cross, self.n_polys)
        self.poly_area = np.linalg.norm(area_vector, axis=1) if self.n_polys else np.zeros(0)
        self.poly_normal = area_vector / np.maximum(self.poly_area, 1e-30)[:, None] if self.n_polys else np.zeros((0, 3))
        self.poly_centroid = centroid
        self.total_area = float(self.poly_area.sum())

    def read_corner_normals(self, me):
        buffer = np.zeros(self.n_loops * 3, dtype=np.float32)
        if self.n_loops:
            source = getattr(me, "corner_normals", None)
            if source is not None and len(source) == self.n_loops:
                source.foreach_get("vector", buffer)
            else:
                if hasattr(me, "calc_normals_split"):
                    me.calc_normals_split()
                me.loops.foreach_get("normal", buffer)
        normals = buffer.reshape(-1, 3).astype(np.float64)
        if abs(np.linalg.det(self.linear)) > 1e-12:
            normals = normals @ np.linalg.inv(self.linear)
        length = np.linalg.norm(normals, axis=1)
        return normals / np.maximum(length, 1e-30)[:, None]

    def compute_triangles(self, me):
        me.calc_loop_triangles()
        count = len(me.loop_triangles)
        self.tri_loops = self.read(me.loop_triangles, "loops", np.int32, 3).astype(np.int64) if count else np.zeros((0, 3), np.int64)
        self.tri_poly = self.read(me.loop_triangles, "polygon_index", np.int32, 1).astype(np.int64) if count else np.zeros(0, np.int64)
        self.tri_verts = self.loop_vert[self.tri_loops] if count else np.zeros((0, 3), np.int64)

    def uv(self):
        layers = self.mesh.uv_layers
        if not layers:
            return None
        layer = layers.get("UVMap 0") or layers.get("UVMap") or layers[0]
        buffer = np.zeros(self.n_loops * 2, dtype=np.float32)
        try:
            layer.uv.foreach_get("vector", buffer)
        except (AttributeError, TypeError, RuntimeError):
            layer.data.foreach_get("uv", buffer)
        return buffer.reshape(-1, 2).astype(np.float64)

    def colors(self, name):
        attribute = self.mesh.color_attributes.get(name)
        if attribute is None or attribute.domain not in ("CORNER", "POINT"):
            return None
        buffer = np.zeros(len(attribute.data) * 4, dtype=np.float32)
        try:
            attribute.data.foreach_get("color_srgb", buffer)
        except (AttributeError, TypeError, RuntimeError):
            attribute.data.foreach_get("color", buffer)
        values = buffer.reshape(-1, 4).astype(np.float64)
        if attribute.domain == "POINT":
            values = values[self.loop_vert]
        return np.clip(np.round(values * 255.0), 0.0, 255.0)

    def bounds(self):
        if self.n_verts == 0:
            return np.zeros(3), np.zeros(3)
        used = self.co[np.unique(self.loop_vert)] if self.n_loops else self.co
        return used.min(axis=0), used.max(axis=0)


class EdgeGraph:
    def __init__(self, arrays, limits):
        self.arrays = arrays
        self.limits = limits
        self.weld()
        self.group_edges()
        self.edge_geometry()

    def weld(self):
        a = self.arrays
        if a.n_verts == 0:
            self.weld_id = np.zeros(0, np.int64)
            self.n_weld = 0
            self.weld_co = np.zeros((0, 3))
            return
        keys = np.floor(a.co / self.limits["weld_m"] + 0.5).astype(np.int64)
        inverse = np.unique(keys, axis=0, return_inverse=True)[1].reshape(-1)
        self.weld_id = inverse
        self.n_weld = int(inverse.max()) + 1
        counts = np.bincount(inverse, minlength=self.n_weld).astype(np.float64)
        self.weld_co = MeshArrays.per_poly_sum(inverse, a.co, self.n_weld) / np.maximum(counts, 1.0)[:, None]

    def group_edges(self):
        a = self.arrays
        self.loop_start_weld = self.weld_id[a.loop_vert] if a.n_loops else np.zeros(0, np.int64)
        self.loop_end_weld = self.weld_id[a.loop_vert[a.loop_next]] if a.n_loops else np.zeros(0, np.int64)
        valid = np.flatnonzero(self.loop_start_weld != self.loop_end_weld)
        low = np.minimum(self.loop_start_weld, self.loop_end_weld)
        high = np.maximum(self.loop_start_weld, self.loop_end_weld)
        key = low * np.int64(max(self.n_weld, 1)) + high
        order = valid[np.argsort(key[valid], kind="stable")]
        self.collapsed_loops = int(a.n_loops - len(valid))
        if len(order) == 0:
            self.edge_u = self.edge_w = self.edge_loop_count = self.la = self.lb = self.boundary_loops = np.zeros(0, np.int64)
            self.boundary_edges = self.nonmanifold_edges = self.edge_count = 0
            return
        sorted_key = key[order]
        first = np.flatnonzero(np.r_[True, sorted_key[1:] != sorted_key[:-1]])
        counts = np.diff(np.r_[first, len(order)])
        self.edge_count = int(len(first))
        self.edge_u = low[order[first]]
        self.edge_w = high[order[first]]
        self.edge_loop_count = counts
        manifold = first[counts == 2]
        loop_a = order[manifold]
        loop_b = order[manifold + 1]
        keep = a.loop_poly[loop_a] != a.loop_poly[loop_b]
        self.la = loop_a[keep]
        self.lb = loop_b[keep]
        self.boundary_loops = order[first[counts == 1]]
        self.boundary_edges = int((counts == 1).sum())
        self.nonmanifold_edges = int((counts > 2).sum())

    @staticmethod
    def angle_deg(first, second):
        return np.degrees(np.arccos(np.clip((first * second).sum(axis=1), -1.0, 1.0)))

    def edge_geometry(self):
        a = self.arrays
        la, lb = self.la, self.lb
        self.face_a = a.loop_poly[la]
        self.face_b = a.loop_poly[lb]
        self.u = self.loop_start_weld[la]
        self.w = self.loop_end_weld[la]
        self.consistent = self.loop_start_weld[la] != self.loop_start_weld[lb]
        normal_a = a.poly_normal[self.face_a]
        normal_b = a.poly_normal[self.face_b]
        self.dihedral = self.angle_deg(normal_a, normal_b)
        self.length = np.linalg.norm(self.weld_co[self.u] - self.weld_co[self.w], axis=1)
        middle = (self.weld_co[self.u] + self.weld_co[self.w]) * 0.5
        self.convex = ((a.poly_centroid[self.face_b] - middle) * normal_a).sum(axis=1) <= 0.0
        safe_length = np.maximum(self.length, 1e-12)
        width_a = np.where(a.poly_total[self.face_a] == 3, 2.0, 1.0) * a.poly_area[self.face_a] / safe_length
        width_b = np.where(a.poly_total[self.face_b] == 3, 2.0, 1.0) * a.poly_area[self.face_b] / safe_length
        self.width = np.minimum(width_a, width_b)
        corner_a_u = a.corner_normal[la]
        corner_a_w = a.corner_normal[a.loop_next[la]]
        corner_b_first = a.corner_normal[lb]
        corner_b_second = a.corner_normal[a.loop_next[lb]]
        consistent = self.consistent[:, None]
        corner_b_u = np.where(consistent, corner_b_second, corner_b_first)
        corner_b_w = np.where(consistent, corner_b_first, corner_b_second)
        self.split_angle = np.maximum(self.angle_deg(corner_a_u, corner_b_u), self.angle_deg(corner_a_w, corner_b_w))
        self.split = self.split_angle > self.limits["split_tol_deg"]
        min_area = np.minimum(a.poly_area[self.face_a], a.poly_area[self.face_b])
        self.degenerate = min_area < np.maximum(1e-10, (self.length * 0.02) ** 2)
        self.smooth = (~self.split) & self.consistent

    def vertex_normals(self):
        a = self.arrays
        normals = np.zeros((self.n_weld, 3))
        weighted = a.poly_normal[a.loop_poly] * a.poly_area[a.loop_poly][:, None] / np.maximum(a.poly_total[a.loop_poly], 1)[:, None]
        np.add.at(normals, self.loop_start_weld, weighted)
        return normals / np.maximum(np.linalg.norm(normals, axis=1), 1e-30)[:, None]

    def vertex_area(self):
        a = self.arrays
        area = np.zeros(self.n_weld)
        np.add.at(area, self.loop_start_weld, a.poly_area[a.loop_poly] / np.maximum(a.poly_total[a.loop_poly], 1))
        return area

    def face_shells(self):
        a = self.arrays
        if a.n_polys == 0:
            return np.zeros(0, np.int64)
        labels = Components.label(self.n_weld, self.edge_u, self.edge_w)
        return np.unique(labels[self.weld_id[a.loop_vert[a.poly_start]]], return_inverse=True)[1].reshape(-1)


class SmoothnessAnalyzer:
    def __init__(self, arrays, graph, limits, report, target, hints):
        self.arrays = arrays
        self.graph = graph
        self.limits = limits
        self.report = report
        self.target = target
        self.hints = hints
        self.toy = target != "map"
        self.panel_cache = None

    def run(self):
        self.check_tris()
        self.check_triangulation()
        self.check_custom_normals()
        self.check_shells()
        self.check_split_edges()
        self.check_dihedral()
        self.check_folds()
        self.check_sagitta()
        self.check_flat_panels()
        self.check_lumpiness()
        self.check_split_ratio()

    def put(self, key, value):
        self.report.metrics[key] = value

    def check_tris(self):
        a = self.arrays
        tris = int(np.clip(a.poly_total - 2, 0, None).sum())
        area = a.total_area
        density = tris / area if area > 1e-9 else 0.0
        self.put("tris", tris)
        self.put("surface_m2", round(area, 4))
        self.put("tris_per_m2", round(density, 1))
        level = "OK"
        note = "studio hero toys 200-320/m2 at 2-4 m, small props run denser"
        if tris >= 8000 and density > self.limits["density_high"]:
            level = "WARN"
            note = "brute-force density; spend tris on bevels and silhouette instead"
        elif tris >= 500 and density < self.limits["density_low"]:
            level = "WARN"
            note = "too coarse for curved toy forms"
        if not self.toy:
            level = "INFO"
            note = "map shell"
        self.report.add(level, "density", "{} tris over {:.2f} m2 = {:.0f} tris/m2 ({})".format(tris, area, density, note))

    def check_triangulation(self):
        a = self.arrays
        non_tri = int((a.poly_total != 3).sum())
        has_custom = bool(a.mesh.has_custom_normals)
        self.put("non_triangle_faces", non_tri)
        if non_tri == 0:
            self.report.add("OK", "triangles", "all {} faces are triangles".format(a.n_polys))
        elif has_custom:
            self.report.add("FAIL", "triangles", "{} quads/n-gons carry custom normals; Sollumz re-triangulates and shifts them up to 20 deg (triangulate, then transfer)".format(non_tri))
        else:
            self.report.add("WARN", "triangles", "{} quads/n-gons; sculpt-forge ends geometry with triangulate, then the normal transfer".format(non_tri))

    def check_custom_normals(self):
        has_custom = bool(self.arrays.mesh.has_custom_normals)
        self.put("has_custom_normals", has_custom)
        if has_custom:
            self.report.add("OK", "custom_normals", "custom split normals present")
        else:
            self.report.add("WARN", "custom_normals", "no custom normals; expected Data Transfer from the high-poly (or Weighted Normal on hard-surface) as the last geometry step")

    def check_shells(self):
        g = self.graph
        a = self.arrays
        if a.n_polys == 0:
            return
        face_shell = g.face_shells()
        shell_area = np.bincount(face_shell, weights=a.poly_area)
        count = int(len(shell_area))
        main_share = float(shell_area.max() / max(shell_area.sum(), 1e-30))
        crossing_shells, crossing_pairs = self.interpenetration(face_shell)
        self.put("shells", count)
        self.put("main_shell_area_share", round(main_share, 3))
        self.put("interpenetrating_shells", crossing_shells)
        self.put("interpenetrating_tri_pairs", crossing_pairs)
        level = "OK" if count <= self.limits["shells_warn"] else "WARN"
        if not self.toy:
            level = "INFO"
        self.report.add(level, "shells", "{} shell(s), main shell {:.0%} of the surface{}".format(count, main_share, "" if count <= self.limits["shells_warn"] else " (kitbash of separate parts; fuse junctions into one sculpted shell)"))
        if crossing_shells == 0:
            self.report.add("OK", "interpenetration", "no separate shells cut through each other")
        else:
            self.report.add("WARN", "interpenetration", "{} of {} shells intersect another shell ({} triangle pairs): hard intersection lines instead of fillets".format(crossing_shells, count, crossing_pairs))

    def interpenetration(self, face_shell):
        a = self.arrays
        if len(np.unique(face_shell)) < 2 or len(a.tri_verts) == 0:
            return 0, 0
        tree = BVHTree.FromPolygons(a.co.tolist(), a.tri_verts.tolist(), all_triangles=True)
        pairs = np.array(tree.overlap(tree), dtype=np.int64).reshape(-1, 2)
        if len(pairs) == 0:
            return 0, 0
        tri_shell = face_shell[a.tri_poly]
        crossing = pairs[(tri_shell[pairs[:, 0]] != tri_shell[pairs[:, 1]]) & (pairs[:, 0] < pairs[:, 1])]
        if len(crossing) == 0:
            return 0, 0
        shells = np.unique(np.concatenate([tri_shell[crossing[:, 0]], tri_shell[crossing[:, 1]]]))
        return int(len(shells)), int(len(crossing))

    def check_split_edges(self):
        g = self.graph
        manifold = len(g.la)
        split = int(g.split.sum())
        share = split / manifold if manifold else 0.0
        soft = int((g.split & (g.dihedral < self.limits["soft_split_deg"])).sum())
        self.put("manifold_edges", manifold)
        self.put("boundary_edges", g.boundary_edges)
        self.put("nonmanifold_edges", g.nonmanifold_edges)
        self.put("split_edges", split)
        self.put("split_edge_share", round(share, 4))
        self.put("soft_split_edges", soft)
        level = QAReport.grade(share, self.limits["split_share_warn"], self.limits["split_share_fail"])
        rule = "toy props <= {:.0%}".format(self.limits["split_share_warn"]) if self.toy else "architecture splits only on 60-90 deg corners"
        detail = ", {} of them on soft angles under {:.0f} deg (faceted bevels/curves)".format(soft, self.limits["soft_split_deg"]) if soft else ""
        self.report.add(level, "split_edges", "{} of {} edges split the normals = {:.1%} ({}){}".format(split, manifold, share, rule, detail))
        if not self.toy and soft > max(20, 0.1 * split):
            self.report.add("WARN", "soft_splits", "{} split edges under {:.0f} deg: curves and bevels should stay smooth".format(soft, self.limits["soft_split_deg"]))
        if g.boundary_edges or g.nonmanifold_edges:
            self.report.add("INFO", "topology", "{} open boundary edges, {} non-manifold edges after a 0.1 mm weld".format(g.boundary_edges, g.nonmanifold_edges))

    def smooth_dihedrals(self):
        g = self.graph
        return g.dihedral[g.smooth & ~g.degenerate]

    def check_dihedral(self):
        values = self.smooth_dihedrals()
        if len(values) == 0:
            self.report.add("WARN", "dihedral", "no smooth edges to measure")
            return
        stats = {
            "p50": round(float(np.percentile(values, 50)), 2),
            "p90": round(float(np.percentile(values, 90)), 2),
            "max": round(float(values.max()), 2),
            "over20": round(float((values > 20).mean()), 4),
            "over30": round(float((values > 30).mean()), 4),
            "over45": round(float((values > 45).mean()), 4),
        }
        self.put("smooth_dihedral", stats)
        level_p90 = QAReport.grade(stats["p90"], self.limits["dihedral_p90_warn"], self.limits["dihedral_p90_fail"])
        level_30 = QAReport.grade(stats["over30"], self.limits["over30_warn"], self.limits["over30_fail"])
        level_45 = QAReport.grade(stats["over45"], self.limits["over45_warn"], None)
        order = ["OK", "WARN", "FAIL"]
        level = order[max(order.index(level_p90), order.index(level_30), order.index(level_45))]
        if not self.toy and level == "FAIL":
            level = "WARN"
        self.report.add(level, "dihedral", "smooth-edge angle p50 {p50:.1f} p90 {p90:.1f} max {max:.1f} deg; {o20:.1%} over 20, {o30:.1%} over 30, {o45:.1%} over 45 (target p90 <= 30, <= 12% over 30, <= 6% over 45)".format(p50=stats["p50"], p90=stats["p90"], max=stats["max"], o20=stats["over20"], o30=stats["over30"], o45=stats["over45"]))

    def check_folds(self):
        g = self.graph
        a = self.arrays
        flipped = (~g.consistent) & ~g.degenerate
        sharp_fold = g.consistent & (g.dihedral > self.limits["fold_deg"]) & ~g.degenerate
        smooth_fold = sharp_fold & ~g.split
        split_fold = sharp_fold & g.split
        bad = smooth_fold | flipped
        smaller = np.where(a.poly_area[g.face_a] <= a.poly_area[g.face_b], g.face_a, g.face_b)
        fold_faces = np.unique(smaller[bad])
        fold_area = float(a.poly_area[fold_faces].sum()) if len(fold_faces) else 0.0
        share = fold_area / max(a.total_area, 1e-30)
        count = int(bad.sum())
        self.put("fold_edges_smooth", int(smooth_fold.sum()))
        self.put("fold_edges_split", int(split_fold.sum()))
        self.put("flipped_edges", int(flipped.sum()))
        self.put("fold_area_share", round(share, 6))
        if count == 0:
            text = "no smooth folds over {:.0f} deg and no flipped neighbours".format(self.limits["fold_deg"])
            if split_fold.any():
                self.report.add("WARN", "folds", text + "; {} hard edges over {:.0f} deg (knife edges or folds)".format(int(split_fold.sum()), self.limits["fold_deg"]))
            else:
                self.report.add("OK", "folds", text)
            return
        worst = float(g.dihedral[smooth_fold].max()) if smooth_fold.any() else 180.0
        level = "FAIL" if share > self.limits["fold_area_fail"] or count > self.limits["fold_count_fail"] else "WARN"
        self.report.add(level, "folds", "{} smooth folds over {:.0f} deg and {} flipped neighbours on {} faces (worst {:.0f} deg, folded faces {:.3%} of the surface; fail above {:.2%} or {} edges): re-decimate or fix before the normal transfer".format(int(smooth_fold.sum()), self.limits["fold_deg"], int(flipped.sum()), len(fold_faces), worst, share, self.limits["fold_area_fail"], self.limits["fold_count_fail"]))

    def check_sagitta(self):
        g = self.graph
        low, high = self.limits["sagitta_curve_min_deg"], self.limits["sagitta_curve_max_deg"]
        curved = g.consistent & ~g.degenerate & (g.dihedral > low) & (g.dihedral < high)
        if not self.toy:
            curved &= ~g.split
        if not curved.any():
            self.report.add("INFO", "sagitta", "no curved edges between {:.0f} and {:.0f} deg".format(low, high))
            return
        theta = np.radians(g.dihedral[curved])
        width = g.width[curved]
        weight = g.length[curved]
        sagitta_mm = 500.0 * width * np.tan(theta * 0.25)
        p95 = Statistics.weighted_percentile(sagitta_mm, weight, 0.95)
        p99 = Statistics.weighted_percentile(sagitta_mm, weight, 0.99)
        worst_index = int(np.argmax(sagitta_mm))
        radius_mm = 1000.0 * width[worst_index] / max(2.0 * math.sin(theta[worst_index] * 0.5), 1e-9)
        segments = 2.0 * math.pi / max(theta[worst_index], 1e-9)
        over = float(weight[sagitta_mm > self.limits["sagitta_warn_mm"]].sum() / weight.sum())
        self.put("sagitta_mm", {"p95": round(p95, 2), "p99": round(p99, 2), "max": round(float(sagitta_mm.max()), 2), "share_over_limit": round(over, 4), "worst_radius_mm": round(radius_mm, 1), "worst_segments": round(segments, 1)})
        level = QAReport.grade(p99, self.limits["sagitta_warn_mm"], self.limits["sagitta_fail_mm"])
        self.report.add(level, "sagitta", "facet sagitta p95 {:.2f} p99 {:.2f} max {:.1f} mm; {:.1%} of curved edge length over {:.0f} mm; worst facet ~R {:.0f} mm at ~{:.0f} segments/circle (target <= {:.0f} mm)".format(p95, p99, float(sagitta_mm.max()), over, self.limits["sagitta_warn_mm"], radius_mm, segments, self.limits["sagitta_warn_mm"]))

    def panel_regions(self):
        if self.panel_cache is None:
            g = self.graph
            a = self.arrays
            coplanar = g.consistent & (g.dihedral < 0.5)
            labels = Components.label(a.n_polys, g.face_a[coplanar], g.face_b[coplanar])
            count = int(labels.max()) + 1 if len(labels) else 0
            region_area = np.bincount(labels, weights=a.poly_area, minlength=count)
            perimeter = np.zeros(count)
            rim = labels[g.face_a] != labels[g.face_b]
            np.add.at(perimeter, labels[g.face_a[rim]], g.length[rim])
            np.add.at(perimeter, labels[g.face_b[rim]], g.length[rim])
            if len(g.boundary_loops):
                ends = a.loop_vert[a.loop_next[g.boundary_loops]]
                starts = a.loop_vert[g.boundary_loops]
                np.add.at(perimeter, labels[a.loop_poly[g.boundary_loops]], np.linalg.norm(a.co[ends] - a.co[starts], axis=1))
            width = 2.0 * region_area / np.maximum(perimeter, 1e-9)
            median_face = float(np.median(a.poly_area)) if a.n_polys else 0.0
            floor = max(self.limits["panel_min_area_m2"], 4.0 * median_face, 0.0005 * a.total_area)
            big_regions = (region_area >= floor) & (width >= self.limits["panel_min_width_m"])
            designed = big_regions & (region_area >= max(self.limits["panel_min_area_m2"], 0.01 * a.total_area))
            self.panel_cache = (labels, region_area, big_regions, designed)
        return self.panel_cache

    def check_flat_panels(self):
        a = self.arrays
        labels, region_area, big_regions = self.panel_regions()[:3]
        member = big_regions[labels]
        share = float(a.poly_area[member].sum() / max(a.total_area, 1e-30))
        self.put("flat_panel_area_share", round(share, 4))
        if share < self.limits["panel_min_share"]:
            self.report.add("INFO", "flat_panels", "no large flat panels ({:.1%} of the surface)".format(share))
            return
        region_normal = np.zeros((len(region_area), 3))
        np.add.at(region_normal, labels, a.poly_normal * a.poly_area[:, None])
        region_normal /= np.maximum(np.linalg.norm(region_normal, axis=1), 1e-30)[:, None]
        loop_member = member[a.loop_poly]
        loops = np.flatnonzero(loop_member)
        deviation = EdgeGraph.angle_deg(a.corner_normal[loops], region_normal[labels[a.loop_poly[loops]]])
        face_max = np.zeros(a.n_polys)
        np.maximum.at(face_max, a.loop_poly[loops], deviation)
        faces = np.flatnonzero(member)
        weights = a.poly_area[faces]
        p95 = Statistics.weighted_percentile(face_max[faces], weights, 0.95)
        mean = Statistics.weighted_mean(face_max[faces], weights)
        crisp = float(weights[face_max[faces] <= self.limits["panel_warn_deg"]].sum() / max(weights.sum(), 1e-30))
        expected, reason = self.weighted_normals_expected(crisp)
        self.put("flat_panel_corner_dev_deg", {"mean": round(mean, 3), "p95": round(p95, 3), "max": round(float(deviation.max()), 3), "panels": int(big_regions.sum()), "crisp_share": round(crisp, 3), "weighted_expected": expected})
        text = "{} flat panels cover {:.0%} of the surface; corner normal tilt mean {:.2f} p95 {:.2f} max {:.1f} deg, {:.0%} crisp".format(int(big_regions.sum()), share, mean, p95, float(deviation.max()), crisp)
        if expected:
            level = "OK" if p95 <= self.limits["panel_warn_deg"] else "WARN"
            hint = " ({}; target p95 <= {:.1f})".format(reason, self.limits["panel_warn_deg"]) if level == "OK" else " ({}: smeared 'playdough' panels; Weighted Normal FACE_AREA weight 50 keep_sharp, or a holding loop, keeps them flat; target p95 <= {:.1f})".format(reason, self.limits["panel_warn_deg"])
            self.report.add(level, "flat_panels", text + hint)
            return
        level = "WARN" if mean > self.limits["panel_pillow_warn_deg"] else "INFO"
        crease = "; big two-triangle panels will show a diagonal shading crease, keep a holding loop near the bevel or flatten panel interiors" if p95 >= self.limits["panel_crease_deg"] else ""
        self.report.add(level, "flat_panels", text + " ({}: pillow shading from the transfer, studio hero median 8.9 deg; warn above mean {:.0f}{})".format(reason, self.limits["panel_pillow_warn_deg"], crease))

    def weighted_normals_expected(self, crisp):
        mode = str(self.hints.get("normals", "")).lower()
        if "weight" in mode:
            return True, "metadata declares weighted normals"
        if "transfer" in mode:
            return False, "metadata declares transferred normals"
        if not self.arrays.mesh.has_custom_normals:
            return True, "default smooth normals"
        if crisp >= 0.6:
            return True, "custom normals look weighted"
        return False, "custom normals look transferred"

    def smooth_zone(self, cap_deg):
        g = self.graph
        bad = np.zeros(g.n_weld, dtype=bool)
        rough = (~g.smooth) | g.degenerate | (g.dihedral >= cap_deg)
        bad[g.u[rough]] = True
        bad[g.w[rough]] = True
        open_edges = g.edge_loop_count != 2
        bad[g.edge_u[open_edges]] = True
        bad[g.edge_w[open_edges]] = True
        used = np.zeros(g.n_weld, dtype=bool)
        used[g.loop_start_weld] = True
        return used & ~bad

    def shading_normals(self):
        g = self.graph
        a = self.arrays
        normals = np.zeros((g.n_weld, 3))
        np.add.at(normals, g.loop_start_weld, a.corner_normal)
        return normals / np.maximum(np.linalg.norm(normals, axis=1), 1e-30)[:, None]

    def check_lumpiness(self):
        g = self.graph
        a = self.arrays
        labels, designed = self.panel_regions()[0], self.panel_regions()[3]
        touched = np.zeros(g.n_weld, dtype=bool)
        touched[g.loop_start_weld[designed[labels][a.loop_poly]]] = True
        probe = LumpinessProbe(g, a, self.limits)
        fine_zone = self.smooth_zone(self.limits["lump_fine_deg"]) & ~touched
        fine = probe.measure(fine_zone, self.limits["lump_fine_deg"], self.shading_normals(), "field")
        coarse = probe.measure(self.smooth_zone(self.limits["lump_coarse_deg"]) & ~touched, self.limits["lump_coarse_deg"], g.vertex_normals(), "quadric")
        self.put("lumpiness_deg", {"shading_wobble": fine, "surface_roughness": coarse})
        if fine is None and coarse is None:
            self.report.add("INFO", "lumpiness", "no large smooth organic regions to measure (flat panels and hard edges excluded)")
            return
        order = ["OK", "WARN", "FAIL"]
        level_fine = QAReport.grade(fine["p50"], self.limits["lump_fine_warn"], self.limits["lump_fine_fail"]) if fine is not None else "OK"
        level_coarse = QAReport.grade(coarse["p50"], self.limits["lump_coarse_warn"], self.limits["lump_coarse_fail"]) if coarse is not None else "OK"
        level = order[max(order.index(level_fine), order.index(level_coarse))]
        parts = []
        if fine is not None:
            parts.append("shading wobble median {:.2f} (p75 {:.2f}, p90 {:.2f}) deg over {:.0%} of the surface (target median <= {:.1f})".format(fine["p50"], fine["p75"], fine["p90"], fine["coverage"], self.limits["lump_fine_warn"]))
        if coarse is not None:
            parts.append("surface roughness median {:.2f} (p75 {:.2f}, p90 {:.2f}) deg over {:.0%} (target median <= {:.1f})".format(coarse["p50"], coarse["p75"], coarse["p90"], coarse["coverage"], self.limits["lump_coarse_warn"]))
        hints = []
        if level_coarse != "OK":
            hints.append("'playdough' lumps in the surface itself: smooth the source, raise voxel resolution or decimate less")
        if level_fine != "OK":
            hints.append("uneven shading normals (lumps or ripples; Weighted Normal run after triangulation ripples on curves): transfer normals from a smooth high-poly, keep curved parts plain smooth")
        self.report.add(level, "lumpiness", "; ".join(parts) + ("" if not hints else " (" + "; ".join(hints) + ")"))

    def check_split_ratio(self):
        a = self.arrays
        if a.n_loops == 0:
            return
        position_key = self.graph.loop_start_weld[:, None]
        normal_key = np.round(a.corner_normal * 1000.0).astype(np.int64)
        uv = a.uv()
        uv_key = np.round(uv * 16384.0).astype(np.int64) if uv is not None else np.zeros((a.n_loops, 2), np.int64)
        color = a.colors("Color 1")
        color_key = color.astype(np.int64) if color is not None else np.zeros((a.n_loops, 4), np.int64)
        rows = np.concatenate([position_key, normal_key, uv_key, color_key], axis=1)
        raw = int(len(np.unique(rows, axis=0)))
        welded = int(len(np.unique(position_key)))
        ratio = raw / max(welded, 1)
        normal_rows = np.concatenate([position_key, normal_key], axis=1)
        normal_only = int(len(np.unique(normal_rows, axis=0)))
        self.put("export_vertices", raw)
        self.put("welded_vertices", welded)
        self.put("split_ratio", round(ratio, 3))
        self.put("normal_split_ratio", round(normal_only / max(welded, 1), 3))
        level = QAReport.grade(ratio, self.limits["split_ratio_warn"], self.limits["split_ratio_fail"])
        self.report.add(level, "split_ratio", "{} export vertices / {} welded positions = {:.2f} (normals alone {:.2f}; <= {:.1f}, about 3 means triangle soup)".format(raw, welded, ratio, normal_only / max(welded, 1), self.limits["split_ratio_warn"]))


class LumpinessProbe:
    def __init__(self, graph, arrays, limits):
        self.graph = graph
        self.arrays = arrays
        self.limits = limits

    def measure(self, zone, cap_deg, normals, mode):
        g = self.graph
        a = self.arrays
        keep = zone[g.u] & zone[g.w] & g.smooth & (g.dihedral < cap_deg)
        labels = Components.label(g.n_weld, g.u[keep], g.w[keep])
        vertex_area = g.vertex_area()
        region_area = np.bincount(labels, weights=vertex_area * zone, minlength=int(labels.max()) + 1 if len(labels) else 0)
        member = zone & (region_area >= self.limits["lump_region_share"] * max(a.total_area, 1e-30))[labels]
        if member.sum() < 40:
            return None
        members = np.flatnonzero(member)
        neighbours = 12 if mode == "field" else 18
        centres, table = self.neighbour_table(g.weld_co[members], neighbours)
        own = members[centres]
        valid = table >= 0
        other = members[np.where(valid, table, 0)]
        centre_normal = normals[own]
        cosine = (normals[other] * centre_normal[:, None, :]).sum(axis=2)
        gate = math.cos(math.radians(20.0)) if mode == "field" else 0.5
        mask = valid & (labels[other] == labels[own][:, None]) & (cosine > gate)
        frame_t, frame_b = self.frame(centre_normal)
        offset = g.weld_co[other] - g.weld_co[own][:, None, :]
        x = (offset * frame_t[:, None, :]).sum(axis=2)
        y = (offset * frame_b[:, None, :]).sum(axis=2)
        if mode == "field":
            residual = self.field_residual(mask, x, y, (normals[other] * frame_t[:, None, :]).sum(axis=2), (normals[other] * frame_b[:, None, :]).sum(axis=2))
        else:
            residual = self.quadric_residual(mask, x, y, (offset * centre_normal[:, None, :]).sum(axis=2))
        good = np.isfinite(residual)
        if good.sum() < 20:
            return None
        weights = vertex_area[own][good]
        coverage = float(weights.sum() / max(a.total_area, 1e-30)) * (len(members) / max(len(centres), 1))
        if coverage < self.limits["lump_min_coverage"]:
            return None
        values = np.degrees(residual[good])
        return {"p50": round(Statistics.weighted_percentile(values, weights, 0.5), 3), "p75": round(Statistics.weighted_percentile(values, weights, 0.75), 3), "p90": round(Statistics.weighted_percentile(values, weights, 0.9), 3), "coverage": round(min(coverage, 1.0), 3)}

    @staticmethod
    def neighbour_table(points, neighbours):
        tree = KDTree(len(points))
        for position, co in enumerate(points):
            tree.insert(Vector(co), position)
        tree.balance()
        stride = max(1, len(points) // 30000)
        centres = np.arange(0, len(points), stride)
        table = np.full((len(centres), neighbours), -1, dtype=np.int64)
        for row, position in enumerate(centres):
            picked = [item[1] for item in tree.find_n(Vector(points[position]), neighbours + 1) if item[1] != position][:neighbours]
            table[row, :len(picked)] = picked
        return centres, table

    @staticmethod
    def frame(normal):
        helper = np.where(np.abs(normal[:, 0:1]) < 0.9, np.array([[1.0, 0.0, 0.0]]), np.array([[0.0, 1.0, 0.0]]))
        tangent = np.cross(normal, helper)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1), 1e-30)[:, None]
        return tangent, np.cross(normal, tangent)

    @staticmethod
    def solve(design, values, weight):
        matrix = np.einsum("mki,mkj->mij", design, design) + np.eye(design.shape[2])[None] * 1e-6
        coefficients = np.linalg.solve(matrix, np.einsum("mki,mk->mi", design, values * weight)[..., None])[..., 0]
        return values * weight - np.einsum("mki,mi->mk", design, coefficients)

    def field_residual(self, mask, x, y, normal_x, normal_y):
        weight = mask.astype(np.float64)
        scale = np.maximum(np.sqrt((weight * (x * x + y * y)).sum(axis=1) / np.maximum(weight.sum(axis=1), 1.0)), 1e-9)[:, None]
        design = np.stack([np.ones_like(x), x / scale, y / scale], axis=2) * weight[:, :, None]
        error_x = self.solve(design, normal_x, weight)
        error_y = self.solve(design, normal_y, weight)
        residual = np.sqrt((error_x ** 2 + error_y ** 2).sum(axis=1) / np.maximum(weight.sum(axis=1) - 3.0, 1.0))
        residual[weight.sum(axis=1) < 8] = np.nan
        return residual

    def quadric_residual(self, mask, x, y, z):
        weight = mask.astype(np.float64)
        scale = np.maximum(np.sqrt((weight * (x * x + y * y)).sum(axis=1) / np.maximum(weight.sum(axis=1), 1.0)), 1e-9)[:, None]
        u = x / scale
        v = y / scale
        design = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], axis=2) * weight[:, :, None]
        error = self.solve(design, z, weight)
        residual = np.sqrt((error ** 2).sum(axis=1) / np.maximum(weight.sum(axis=1) - 6.0, 1.0)) / scale[:, 0]
        residual[weight.sum(axis=1) < 10] = np.nan
        return residual


class HighPolyReference:
    def __init__(self, path, object_name, arrays):
        self.path = path
        self.object_name = object_name
        self.arrays = arrays
        triangles = arrays.tri_verts
        self.tree = BVHTree.FromPolygons(arrays.co.tolist(), triangles.tolist(), all_triangles=True)

    @classmethod
    def load(cls, path, wanted_names, current_file):
        if os.path.abspath(path) == os.path.abspath(current_file or ""):
            ob = cls.pick(list(bpy.data.objects), wanted_names)
            if ob is None:
                return None
            return cls(path, ob.name, MeshArrays(ob))
        before = cls.snapshot()
        with bpy.data.libraries.load(path, link=False) as (source, target):
            names = [name for name in wanted_names if name in source.objects]
            if not names:
                target.objects = list(source.objects)
            else:
                target.objects = names[:1]
        loaded = [ob for ob in target.objects if ob is not None]
        chosen = cls.pick(loaded, wanted_names)
        result = None
        if chosen is not None:
            result = cls(path, chosen.name, MeshArrays(chosen))
        for ob in loaded:
            bpy.data.objects.remove(ob, do_unlink=True)
        cls.purge(before)
        return result

    @staticmethod
    def snapshot():
        return {kind: {block.as_pointer() for block in getattr(bpy.data, kind)} for kind in ("meshes", "materials", "images", "textures", "node_groups", "armatures", "actions", "curves")}

    @staticmethod
    def purge(before):
        for _ in range(3):
            for kind, known in before.items():
                collection = getattr(bpy.data, kind)
                for block in list(collection):
                    if block.as_pointer() not in known and block.users == 0:
                        collection.remove(block)

    @staticmethod
    def pick(objects, wanted_names):
        meshes = [ob for ob in objects if ob is not None and ob.type == "MESH" and len(ob.data.polygons) > 0 and "_col_" not in ob.name]
        for name in wanted_names:
            for ob in meshes:
                if ob.name == name:
                    return ob
        largest = None
        for ob in meshes:
            if largest is None or len(ob.data.polygons) > len(largest.data.polygons):
                largest = ob
        return largest

    def nearest(self, points):
        count = len(points)
        location = np.zeros((count, 3))
        triangle = np.zeros(count, dtype=np.int64)
        distance = np.full(count, np.inf)
        find = self.tree.find_nearest
        for index in range(count):
            hit = find(Vector(points[index]))
            if hit[0] is not None:
                location[index] = hit[0]
                triangle[index] = hit[2]
                distance[index] = hit[3]
        return location, triangle, distance

    def normals_at(self, location, triangle):
        a = self.arrays
        corners = a.tri_verts[triangle]
        p0, p1, p2 = a.co[corners[:, 0]], a.co[corners[:, 1]], a.co[corners[:, 2]]
        v0, v1, v2 = p1 - p0, p2 - p0, location - p0
        d00 = (v0 * v0).sum(1)
        d01 = (v0 * v1).sum(1)
        d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1)
        d21 = (v2 * v1).sum(1)
        denominator = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-30, 1e-30, d00 * d11 - d01 * d01)
        b1 = np.clip((d11 * d20 - d01 * d21) / denominator, 0.0, 1.0)
        b2 = np.clip((d00 * d21 - d01 * d20) / denominator, 0.0, 1.0)
        b0 = np.clip(1.0 - b1 - b2, 0.0, 1.0)
        loops = a.tri_loops[triangle]
        normal = a.corner_normal[loops[:, 0]] * b0[:, None] + a.corner_normal[loops[:, 1]] * b1[:, None] + a.corner_normal[loops[:, 2]] * b2[:, None]
        return normal / np.maximum(np.linalg.norm(normal, axis=1), 1e-30)[:, None]


class HighPolyComparison:
    def __init__(self, arrays, reference, limits, report, target):
        self.arrays = arrays
        self.reference = reference
        self.limits = limits
        self.report = report
        self.target = target

    def run(self):
        if self.check_alignment():
            self.check_normals()
            self.check_deviation()

    def check_alignment(self):
        low_min, low_max = self.arrays.bounds()
        high_min, high_max = self.reference.arrays.bounds()
        size = float(np.linalg.norm(low_max - low_min))
        shift = float(max(np.abs(low_min - high_min).max(), np.abs(low_max - high_max).max()))
        self.report.metrics["high_poly"] = {"file": self.reference.path, "object": self.reference.object_name, "tris": int(len(self.reference.arrays.tri_verts)), "bbox_shift_mm": round(shift * 1000.0, 2)}
        level = "OK" if shift <= max(0.005, 0.02 * size) else "WARN"
        matched = shift <= max(0.02, 0.25 * size)
        note = "" if level == "OK" else (" (high-poly not aligned with the low-poly?)" if matched else " (a different shape: normal error and deviation skipped)")
        self.report.add(level, "high_poly", "{} :: {} ({} tris), bounding boxes differ by {:.1f} mm{}".format(os.path.basename(self.reference.path), self.reference.object_name, len(self.reference.arrays.tri_verts), shift * 1000.0, note))
        return matched

    def check_normals(self):
        a = self.arrays
        if a.n_loops == 0:
            return
        sample = np.arange(a.n_loops) if a.n_loops <= 120000 else np.linspace(0, a.n_loops - 1, 120000).astype(np.int64)
        position = a.co[a.loop_vert[sample]]
        towards = a.poly_centroid[a.loop_poly[sample]] - position
        query = position + towards * np.minimum(1.0, 1e-4 / np.maximum(np.linalg.norm(towards, axis=1), 1e-9))[:, None]
        location, triangle, distance = self.reference.nearest(query)
        found = np.isfinite(distance)
        reference = self.reference.normals_at(location[found], triangle[found])
        error = EdgeGraph.angle_deg(a.corner_normal[sample][found], reference)
        if len(error) == 0:
            self.report.add("WARN", "normal_error", "no corners matched the high-poly")
            return
        stats = {"mean": round(float(error.mean()), 3), "p95": round(float(np.percentile(error, 95)), 3), "p99": round(float(np.percentile(error, 99)), 3), "max": round(float(error.max()), 3)}
        self.report.metrics["normal_error_deg"] = stats
        level = "OK"
        if stats["mean"] > self.limits["normal_mean_fail_deg"] or stats["p99"] > self.limits["normal_p99_fail_deg"]:
            level = "FAIL"
        elif stats["mean"] > self.limits["normal_mean_warn_deg"] or stats["max"] > self.limits["normal_max_warn_deg"]:
            level = "WARN"
        self.report.add(level, "normal_error", "corner normals vs high-poly mean {mean:.2f} p95 {p95:.2f} p99 {p99:.2f} max {max:.1f} deg (target mean <= 1, max <= 10)".format(**stats))

    @staticmethod
    def thin(count, limit):
        return np.arange(count) if count <= limit else np.linspace(0, count - 1, limit).astype(np.int64)

    def check_deviation(self):
        a = self.arrays
        if len(a.tri_verts) == 0:
            return
        corners = a.co[a.tri_verts]
        tri_area = 0.5 * np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
        samples = np.concatenate([corners.mean(axis=1), (corners[:, 0] + corners[:, 1]) * 0.5, (corners[:, 1] + corners[:, 2]) * 0.5, (corners[:, 2] + corners[:, 0]) * 0.5], axis=0)
        sample_weight = np.tile(tri_area * 0.25, 4)
        keep = self.thin(len(samples), 160000)
        samples, sample_weight = samples[keep], sample_weight[keep]
        distance_low = self.reference.nearest(samples)[2]
        high = self.reference.arrays
        high_area = np.bincount(high.loop_vert, weights=high.poly_area[high.loop_poly] / np.maximum(high.poly_total[high.loop_poly], 1), minlength=high.n_verts)
        used = np.unique(high.tri_verts)
        used = used[self.thin(len(used), 80000)]
        high_points, high_weight = high.co[used], high_area[used]
        low_tree = BVHTree.FromPolygons(a.co.tolist(), a.tri_verts.tolist(), all_triangles=True)
        distance_high = np.full(len(high_points), np.inf)
        find = low_tree.find_nearest
        for index in range(len(high_points)):
            hit = find(Vector(high_points[index]))
            if hit[0] is not None:
                distance_high[index] = hit[3]
        found_low = np.isfinite(distance_low)
        found_high = np.isfinite(distance_high)
        distance_low, weight_low = distance_low[found_low] * 1000.0, sample_weight[found_low]
        distance_high, weight_high = distance_high[found_high] * 1000.0, high_weight[found_high]
        p95_low = Statistics.weighted_percentile(distance_low, weight_low, 0.95)
        p95_high = Statistics.weighted_percentile(distance_high, weight_high, 0.95)
        max_low = float(distance_low.max()) if len(distance_low) else 0.0
        max_high = float(distance_high.max()) if len(distance_high) else 0.0
        worst = max(p95_low, p95_high)
        stats = {"low_to_high_p95": round(p95_low, 3), "high_to_low_p95": round(p95_high, 3), "low_to_high_max": round(max_low, 3), "high_to_low_max": round(max_high, 3), "mean_low_to_high": round(Statistics.weighted_mean(distance_low, weight_low), 3), "area_weighted": True}
        self.report.metrics["surface_deviation_mm"] = stats
        level = QAReport.grade(worst, self.limits["deviation_warn_mm"], self.limits["deviation_fail_mm"])
        local = max(max_low, max_high) > self.limits["deviation_local_mm"]
        if level == "OK" and local:
            level = "WARN"
        note = "; a local error over {:.0f} mm (lost detail or a fold)".format(self.limits["deviation_local_mm"]) if local else ""
        self.report.add(level, "deviation", "surface vs high-poly area-weighted p95 {:.2f} mm (low->high {:.2f}, high->low {:.2f}; max {:.1f}/{:.1f}) (target p95 <= {:.0f} mm){}".format(worst, p95_low, p95_high, max_low, max_high, self.limits["deviation_warn_mm"], note))


class PropContract:
    def __init__(self, validator_path, report, arrays, ob):
        self.validator_path = validator_path
        self.report = report
        self.arrays = arrays
        self.ob = ob

    def run(self, budget):
        self.run_validate_prop(budget)
        self.check_color_attribute()
        self.check_uv_layers()
        self.check_normal_maps()

    def run_validate_prop(self, budget):
        if not self.validator_path:
            self.report.add("FAIL", "contract", "prop-forge validate_prop.py not found (pass --prop-validator <path>)")
            return
        try:
            validate_scene = runpy.run_path(self.validator_path)["validate_scene"]
            lines = validate_scene(self.ob.name, budget or None)
        except Exception as error:
            self.report.add("FAIL", "contract", "validate_prop.validate_scene raised {}: {}".format(type(error).__name__, error))
            return
        for line in lines:
            level, _, text = line.partition(" ")
            if level in ("OK", "WARN", "FAIL"):
                self.report.add(level, "contract", text)

    def check_color_attribute(self):
        me = self.ob.data
        attribute = me.color_attributes.get("Color 1")
        if attribute is None:
            self.report.add("WARN", "color1", "no 'Color 1': export_prop writes all-255 white, so the prop ships without AO")
            return
        if attribute.domain != "CORNER" or attribute.data_type != "BYTE_COLOR":
            self.report.add("FAIL", "color1", "'Color 1' is {}/{}; export_prop deletes it and writes white (needs BYTE_COLOR / CORNER)".format(attribute.data_type, attribute.domain))
            return
        values = self.arrays.colors("Color 1")
        mean = values.mean(axis=0) if values is not None and len(values) else np.zeros(4)
        low = values[:, :3].min() if values is not None and len(values) else 0
        self.report.metrics["color1_mean"] = [round(float(v), 1) for v in mean]
        self.report.add("OK", "color1", "'Color 1' BYTE_COLOR/CORNER, mean RGBA {:.0f}/{:.0f}/{:.0f}/{:.0f}, darkest {:.0f}".format(mean[0], mean[1], mean[2], mean[3], low))

    def check_uv_layers(self):
        names = [layer.name for layer in self.ob.data.uv_layers]
        if len(names) == 1:
            self.report.add("OK", "uv_layers", "one UV layer '{}' (export renames it 'UVMap 0')".format(names[0]))
        elif not names:
            self.report.add("FAIL", "uv_layers", "no UV layer: no TEXTURE0, the prop renders black")
        else:
            self.report.add("WARN", "uv_layers", "{} UV layers {}; keep exactly one".format(len(names), names))

    def check_normal_maps(self):
        found = []
        for material in self.ob.data.materials:
            if material is None or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type in ("NORMAL_MAP", "BUMP") or node.name == "BumpSampler":
                    found.append("{}:{}".format(material.name, node.name))
        if found:
            self.report.add("WARN", "normal_maps", "normal/bump nodes {}: prop export binds no normal maps, model the bevel instead".format(found[:4]))


class MapContract:
    def __init__(self, ob, arrays, graph, report, limits, stem):
        self.ob = ob
        self.arrays = arrays
        self.graph = graph
        self.report = report
        self.limits = limits
        self.stem = stem
        self.meta = self.read_meta(ob)

    @staticmethod
    def read_meta(ob):
        raw = ob.get("map_forge") or ob.get("prop_forge")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def shader_names():
        return {"normal_spec.sps", "normal.sps", "default.sps", "normal_spec_detail.sps", "decal.sps", "glass_env.sps", "cutout.sps", "emissive.sps", "emissivenight.sps", "emissive_alpha.sps", "water_fountain.sps", "default_spec.sps", "spec.sps"}

    @staticmethod
    def collision_names():
        return {"CONCRETE", "WOOD_SOLID_MEDIUM", "METAL_SOLID_MEDIUM", "STONE", "GRASS", "GLASS_SHOOT_THROUGH"}

    def run(self):
        self.check_name()
        self.check_transform()
        self.check_walk_surface()
        self.check_uv()
        self.check_color()
        self.check_materials()
        self.check_metadata()
        self.check_colliders()
        self.check_tris()

    def check_name(self):
        ob = self.ob
        rule = re.compile(r"^[a-z0-9_]{3,60}$")
        ok = bool(rule.match(ob.name)) and ob.data.name == ob.name
        level = "OK" if ok else "FAIL"
        if ok and self.stem and ob.name != self.stem:
            level = "WARN"
        self.report.add(level, "contract", "shell name {} / mesh {} / file {} (lowercase a-z 0-9 _, all equal)".format(ob.name, ob.data.name, self.stem))

    def check_transform(self):
        ob = self.ob
        ok = ob.location.length < 1e-4 and max(abs(v) for v in ob.rotation_euler) < 1e-4 and max(abs(v - 1.0) for v in ob.scale) < 1e-4
        self.report.add("OK" if ok else "FAIL", "contract", "transforms applied (location 0, rotation 0, scale 1)")
        if ob.parent is not None:
            self.report.add("FAIL", "contract", "shell has a parent ({})".format(ob.parent.name))

    def check_walk_surface(self):
        a = self.arrays
        up = a.poly_normal[:, 2] > 0.9
        low, high = a.bounds()
        grounded = abs(float(low[2])) <= 0.02
        if not up.any():
            self.report.add("OK" if grounded else "WARN", "walk_surface", "no upward faces; lowest point z = {:.2f} m{}".format(float(low[2]), "" if grounded else " (origin must be the walk surface or the ground contact at z = 0)"))
            return
        height = a.poly_centroid[up, 2]
        area = a.poly_area[up]
        at_zero = float(area[np.abs(height) <= 0.02].sum())
        share = at_zero / max(float(area.sum()), 1e-30)
        levels = np.round(height / 0.02).astype(np.int64)
        unique, inverse = np.unique(levels, return_inverse=True)
        level_area = np.bincount(inverse.reshape(-1), weights=area)
        main_level = float(unique[int(np.argmax(level_area))]) * 0.02
        walkable = share >= 0.05 or at_zero >= 0.5
        self.report.metrics["walk_surface"] = {"area_at_z0_m2": round(at_zero, 3), "share_of_up_faces": round(share, 3), "main_walk_z": round(main_level, 3), "lowest_z": round(float(low[2]), 3), "highest_z": round(float(high[2]), 3)}
        if walkable:
            self.report.add("OK", "walk_surface", "{:.2f} m2 of upward faces at z = 0 ({:.0%} of upward area); lowest point z = {:.2f} m (substructure below 0 is allowed)".format(at_zero, share, float(low[2])))
        elif grounded:
            self.report.add("OK", "walk_surface", "sits on the ground at z = 0; largest upward area at z = {:.2f} m".format(main_level))
        else:
            self.report.add("WARN", "walk_surface", "largest upward area is at z = {:.2f} m and only {:.2f} m2 lies at z = 0; lowest point z = {:.2f} m (origin must be the walk surface at z = 0)".format(main_level, at_zero, float(low[2])))

    def check_uv(self):
        names = [layer.name for layer in self.ob.data.uv_layers]
        if not names:
            self.report.add("FAIL", "uv_layers", "no UV layer ('UVMap 0' needed for TEXTURE0 and TANGENT0)")
            return
        level = "OK" if len(names) == 1 and names[0] in ("UVMap 0", "UVMap") else "WARN"
        uv = self.arrays.uv()
        span = float(np.ptp(uv, axis=0).max()) if uv is not None and len(uv) else 0.0
        if span < 1e-4:
            self.report.add("FAIL", "uv_layers", "UVs are constant (ptp {:.1e}); normal shaders need real UVs".format(span))
            return
        scale = self.texel_scale(uv)
        self.report.metrics["uv_m_per_unit"] = round(scale, 3)
        if scale > 8.0:
            level = "WARN"
        self.report.add(level, "uv_layers", "UV layers {}; median {:.2f} m per UV unit (world-tiled 1.5-3.0 m; never one smart-UV atlas on big pieces)".format(names, scale))

    def texel_scale(self, uv):
        a = self.arrays
        if len(a.tri_loops) == 0:
            return 0.0
        t = uv[a.tri_loops]
        uv_area = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
        p = a.co[a.tri_verts]
        world_area = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        good = (uv_area > 1e-12) & (world_area > 1e-10)
        if not good.any():
            return 0.0
        return float(np.median(np.sqrt(world_area[good] / uv_area[good])))

    def emissive_loops(self):
        a = self.arrays
        flags = []
        for material in self.ob.data.materials:
            shader = (material.get("map_forge_shader") or material.get("prop_forge_shader") or "") if material else ""
            flags.append("emissive" in str(shader).lower())
        if not flags:
            return np.zeros(a.n_loops, dtype=bool)
        table = np.array(flags, dtype=bool)
        return table[np.clip(a.poly_material[a.loop_poly], 0, len(table) - 1)]

    def check_color(self):
        me = self.ob.data
        attribute = me.color_attributes.get("Color 1")
        if attribute is None:
            if len(me.color_attributes):
                self.report.add("FAIL", "color1", "no 'Color 1' but {} exists; export_map renames the first attribute without checking type or semantics".format([c.name for c in me.color_attributes]))
            else:
                self.report.add("WARN", "color1", "no 'Color 1'; export_map writes the flat 255/0/255/255 baseline (no AO)")
            return
        if attribute.domain != "CORNER" or attribute.data_type != "BYTE_COLOR":
            self.report.add("FAIL", "color1", "'Color 1' is {}/{}; Sollumz silently drops anything but BYTE_COLOR / CORNER".format(attribute.data_type, attribute.domain))
            return
        values = self.arrays.colors("Color 1")
        lit = ~self.emissive_loops()
        if values is None or not lit.any():
            self.report.add("OK", "color1", "'Color 1' BYTE_COLOR/CORNER (emissive only)")
            return
        mean = values[lit].mean(axis=0)
        interior = bool(self.meta and self.meta.get("interior"))
        self.report.metrics["color1_mean_lit"] = [round(float(v), 1) for v in mean]
        problems = []
        if mean[0] < 90:
            problems.append("R {:.0f} < 90 (dark by day)".format(mean[0]))
        if mean[1] > 45 and not interior:
            problems.append("outdoor G {:.0f} > 45 (glows at night)".format(mean[1]))
        if mean[2] < 90:
            problems.append("B {:.0f} < 90 (AO too dark)".format(mean[2]))
        if mean[3] < 250:
            problems.append("A {:.0f} < 255".format(mean[3]))
        self.report.add("WARN" if problems else "OK", "color1", "RAGE 'Color 1' on lit faces R/G/B/A {:.0f}/{:.0f}/{:.0f}/{:.0f}{}".format(mean[0], mean[1], mean[2], mean[3], ("; " + ", ".join(problems)) if problems else " (R day x AO, G night 0 outdoors, B AO)"))

    def check_materials(self):
        materials = [m for m in self.ob.data.materials if m is not None]
        if not materials:
            self.report.add("FAIL", "materials", "no materials")
            return
        allowed = self.shader_names()
        for material in materials:
            shader = material.get("map_forge_shader")
            if not shader:
                fallback = material.get("prop_forge_shader")
                self.report.add("WARN", "materials", "{} has no map_forge_shader (export falls back to {})".format(material.name, fallback or "default.sps"))
                continue
            if shader not in allowed:
                self.report.add("WARN", "materials", "{} uses {} (not in the map-forge shader set)".format(material.name, shader))
                continue
            nodes = material.node_tree.nodes if material.use_nodes else []
            images = [n for n in nodes if n.type == "TEX_IMAGE" and n.image is not None]
            missing = [n.image.name for n in images if not n.image.packed_file and not (n.image.filepath and os.path.exists(bpy.path.abspath(n.image.filepath)))]
            if missing:
                self.report.add("FAIL", "materials", "{} textures missing on disk: {} (renders magenta; export needs every PNG plus its .dds)".format(material.name, ", ".join(sorted(set(missing))[:6])))
            named = {n.name for n in images}
            notes = []
            if images and "DiffuseSampler" not in named:
                notes.append("no image node named DiffuseSampler")
            if (shader.startswith("normal") or shader.startswith("glass")) and "BumpSampler" not in named:
                notes.append("{} needs a BumpSampler (_n.png)".format(shader))
            self.report.add("WARN" if notes else "OK", "materials", "{} -> {}{}".format(material.name, shader, ("; " + "; ".join(notes)) if notes else ""))

    def check_metadata(self):
        if self.meta is None:
            self.report.add("WARN", "metadata", "no map_forge metadata JSON on the shell")
            return
        material = self.meta.get("collision_material")
        if material in self.collision_names():
            self.report.add("OK", "metadata", "collision_material {}".format(material))
        else:
            self.report.add("WARN", "metadata", "collision_material {} not in {}".format(material, sorted(self.collision_names())))

    def check_colliders(self):
        colliders = [ob for ob in bpy.context.scene.objects if ob.type == "MESH" and ob.name.startswith(self.ob.name + "_col_")]
        if not colliders:
            self.report.add("WARN", "colliders", "no {}_col_N colliders (fine only if a separate .ybn covers the shell)".format(self.ob.name))
            return
        bad = []
        for collider in colliders:
            arrays = MeshArrays(collider)
            graph = EdgeGraph(arrays, self.limits)
            volume = self.signed_volume(arrays)
            if graph.boundary_edges or graph.nonmanifold_edges or volume <= 0:
                bad.append("{} (open {}, non-manifold {}, volume {:.3f})".format(collider.name, graph.boundary_edges, graph.nonmanifold_edges, volume))
        self.report.add("FAIL" if bad else "OK", "colliders", "{} colliders{}".format(len(colliders), (": " + "; ".join(bad)) if bad else " closed with outward normals"))

    @staticmethod
    def signed_volume(arrays):
        if len(arrays.tri_verts) == 0:
            return 0.0
        p = arrays.co[arrays.tri_verts]
        return float((p[:, 0] * np.cross(p[:, 1], p[:, 2])).sum() / 6.0)

    def check_tris(self):
        tris = int(len(self.arrays.tri_verts))
        limit = self.limits["max_tris"]
        self.report.add("OK" if tris <= limit else "FAIL", "contract", "tris {} / shell ceiling {}".format(tris, limit))


class DrawableResolver:
    @staticmethod
    def is_collider(ob):
        return "_col_" in ob.name or "prop_forge_collision" in ob or "map_forge_collision" in ob

    @classmethod
    def drawables(cls, stem, high_names):
        scene_meshes = [ob for ob in bpy.context.scene.objects if ob.type == "MESH" and not cls.is_collider(ob)]
        named = [ob for ob in scene_meshes if ob.name == stem]
        if named:
            return named
        tagged = [ob for ob in scene_meshes if "prop_forge" in ob or "map_forge" in ob]
        if tagged:
            return tagged
        return [ob for ob in scene_meshes if not ob.name.endswith("_high") and ob.name not in high_names and not ob.hide_render and len(ob.data.polygons) > 0]

    @staticmethod
    def evaluated(ob):
        live = [m for m in ob.modifiers if m.type != "ARMATURE" and m.show_viewport]
        if not live:
            return ob, None, []
        muted = []
        for modifier in ob.modifiers:
            if modifier.type == "ARMATURE" and modifier.show_viewport:
                modifier.show_viewport = False
                muted.append(modifier)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mesh = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
        for modifier in muted:
            modifier.show_viewport = True
        proxy = bpy.data.objects.new(ob.name + "_sculptqa_eval", mesh)
        proxy.matrix_world = ob.matrix_world.copy()
        return proxy, mesh, [m.type for m in live]

    @staticmethod
    def release(proxy, mesh):
        if proxy is not None:
            bpy.data.objects.remove(proxy, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


class SculptValidator:
    def __init__(self, options):
        self.options = options
        self.options.blend = os.path.abspath(options.blend) if options.blend else ""
        self.options.high = os.path.abspath(options.high) if options.high else ""
        self.options.json = os.path.abspath(options.json) if options.json else ""
        self.reports = []
        self.prop_validator = self.find_prop_validator(options.prop_validator)

    @staticmethod
    def find_prop_validator(explicit):
        candidates = []
        if explicit:
            candidates.append(explicit)
        here = globals().get("__file__")
        if here:
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(here)), "..", "..", "..", "prop-forge", "scripts", "blender", "validate_prop.py"))
        candidates.append(os.path.join(os.path.expanduser("~"), ".claude", "skills", "infrontofx", "prop-forge", "scripts", "blender", "validate_prop.py"))
        roots = [os.getcwd()]
        if bpy.data.filepath:
            roots.append(os.path.dirname(bpy.data.filepath))
        for root in roots:
            folder = os.path.abspath(root)
            for _ in range(8):
                candidates.append(os.path.join(folder, ".claude", "skills", "infrontofx", "prop-forge", "scripts", "blender", "validate_prop.py"))
                candidates.append(os.path.join(folder, "prop-forge", "scripts", "blender", "validate_prop.py"))
                parent = os.path.dirname(folder)
                if parent == folder:
                    break
                folder = parent
        for path in candidates:
            if path and os.path.isfile(path):
                return os.path.abspath(path)
        return None

    def files(self):
        source = self.options.blend
        if not source:
            return [None]
        if os.path.isdir(source):
            return [os.path.join(source, name) for name in sorted(os.listdir(source)) if name.lower().endswith(".blend") and not name.lower().endswith("_high.blend")]
        return [source]

    def open_file(self, path):
        if path is None:
            return True
        if os.path.abspath(bpy.data.filepath or "") == os.path.abspath(path):
            return True
        if not bpy.app.background and bpy.data.is_dirty:
            print("FAIL open: the current file has unsaved changes; save it or run headless before validating {}".format(path))
            return False
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        return True

    def target_for(self, ob):
        if self.options.target in ("prop", "map", "library"):
            return self.options.target
        if "map_forge" in ob:
            return "map"
        for material in ob.data.materials:
            if material is not None and "map_forge_shader" in material:
                return "map"
        return "prop"

    def high_reference(self, path, stem, ob):
        wanted = [name for name in (self.options.high_object, ob.name + "_high", stem + "_high", ob.name, stem) if name]
        candidates = []
        if self.options.high:
            candidates.append(self.options.high)
        if path:
            candidates.append(os.path.join(os.path.dirname(path), stem + "_high.blend"))
            if ob.name != stem:
                candidates.append(os.path.join(os.path.dirname(path), ob.name + "_high.blend"))
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return HighPolyReference.load(candidate, wanted, path or bpy.data.filepath)
        same_file = bpy.data.objects.get(ob.name + "_high") or bpy.data.objects.get(stem + "_high")
        if same_file is not None and same_file.type == "MESH":
            return HighPolyReference(path or bpy.data.filepath, same_file.name, MeshArrays(same_file))
        return None

    def validate_file(self, path):
        if not self.open_file(path):
            return
        current = path or bpy.data.filepath
        stem = os.path.splitext(os.path.basename(current))[0] if current else ""
        high_names = {self.options.high_object} if self.options.high_object else set()
        drawables = DrawableResolver.drawables(stem, high_names)
        if not drawables:
            report = QAReport(current, stem, self.options.target or "prop")
            report.add("FAIL", "drawable", "no drawable mesh found")
            self.emit(report)
            return
        for ob in drawables:
            self.validate_drawable(current, stem, ob)

    def validate_drawable(self, path, stem, ob):
        target = self.target_for(ob)
        report = QAReport(path, ob.name, target)
        limits = QALimits(target)
        proxy, temporary_mesh, modifiers = DrawableResolver.evaluated(ob)
        try:
            arrays = MeshArrays(proxy)
            graph = EdgeGraph(arrays, limits)
            if modifiers:
                report.add("WARN", "modifiers", "unapplied modifiers {} (measured evaluated; apply before export)".format(modifiers))
            if target == "prop":
                PropContract(self.prop_validator, report, arrays, ob).run(self.options.budget)
            elif target == "map":
                MapContract(ob, arrays, graph, report, limits, stem).run()
            if arrays.n_polys == 0:
                report.add("FAIL", "mesh", "mesh has no faces")
            else:
                SmoothnessAnalyzer(arrays, graph, limits, report, target, self.hints_for(ob)).run()
                self.compare_high(report, arrays, limits, target, path, stem, ob)
        except Exception as error:
            report.add("FAIL", "exception", "{}: {}".format(type(error).__name__, error))
        finally:
            if proxy is not ob:
                DrawableResolver.release(proxy, temporary_mesh)
        self.emit(report)

    @staticmethod
    def hints_for(ob):
        hints = {}
        for key in ("prop_forge", "map_forge", "sculpt_forge"):
            raw = ob.get(key)
            if not raw:
                continue
            try:
                meta = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (TypeError, ValueError):
                continue
            for name in ("normals", "normal_mode"):
                if name in meta:
                    hints["normals"] = meta[name]
        if "sculpt_forge_normals" in ob:
            hints["normals"] = ob["sculpt_forge_normals"]
        return hints

    def compare_high(self, report, arrays, limits, target, path, stem, ob):
        if self.options.no_high:
            report.add("INFO", "high_poly", "high-poly comparison disabled (--no-high)")
            return
        try:
            reference = self.high_reference(path, stem, ob)
        except Exception as error:
            report.add("WARN", "high_poly", "could not load the high-poly: {}: {}".format(type(error).__name__, error))
            return
        if reference is None:
            report.add("INFO", "high_poly", "no {}_high.blend next to the file: normal error and surface deviation skipped".format(stem or ob.name))
        elif reference.object_name == ob.name and os.path.abspath(reference.path) == os.path.abspath(path or ""):
            report.add("INFO", "high_poly", "drawable is its own high-poly reference: skipped")
        else:
            HighPolyComparison(arrays, reference, limits, report, target).run()

    def emit(self, report):
        self.reports.append(report)
        print("== {} :: {} [{}]".format(report.file_path, report.drawable, report.target), flush=True)
        for line in report.lines():
            print(line, flush=True)
        print("RESULT {} fail={} warn={}".format(report.drawable, report.count("FAIL"), report.count("WARN")), flush=True)

    def run(self):
        for path in self.files():
            try:
                self.validate_file(path)
            except Exception as error:
                report = QAReport(path, os.path.basename(path or "scene"), self.options.target or "prop")
                report.add("FAIL", "exception", "{}: {}".format(type(error).__name__, error))
                self.emit(report)
        fails = sum(report.count("FAIL") for report in self.reports)
        warns = sum(report.count("WARN") for report in self.reports)
        if self.options.json:
            folder = os.path.dirname(os.path.abspath(self.options.json))
            os.makedirs(folder, exist_ok=True)
            with open(self.options.json, "w", encoding="utf-8") as handle:
                json.dump({"drawables": [report.to_dict() for report in self.reports], "fail": fails, "warn": warns}, handle, indent=1, default=str)
        print("SCULPT_QA_SUMMARY drawables={} files={}".format(len(self.reports), len(self.files())), flush=True)
        for report in self.reports:
            print("  {:<40} {:<8} fail={} warn={}".format(report.drawable[:40], report.target, report.count("FAIL"), report.count("WARN")), flush=True)
        print("SCULPT_QA fail={} warn={}".format(fails, warns), flush=True)
        return fails, warns


class CommandLine:
    @staticmethod
    def parse(argv):
        parser = argparse.ArgumentParser(prog="validate_sculpt.py")
        parser.add_argument("--blend", default="")
        parser.add_argument("--high", default="")
        parser.add_argument("--high-object", dest="high_object", default="")
        parser.add_argument("--no-high", dest="no_high", action="store_true")
        parser.add_argument("--target", default="auto", choices=["auto", "prop", "map", "library"])
        parser.add_argument("--budget", type=int, default=0)
        parser.add_argument("--json", default="")
        parser.add_argument("--prop-validator", dest="prop_validator", default="")
        return parser.parse_args(argv)

    @staticmethod
    def script_args():
        return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def main():
    options = CommandLine.parse(CommandLine.script_args())
    fails, warns = SculptValidator(options).run()
    if bpy.app.background:
        sys.stdout.flush()
        sys.exit(1 if fails else 0)
    return {"fail": fails, "warn": warns}


if __name__ == "__main__":
    main()
