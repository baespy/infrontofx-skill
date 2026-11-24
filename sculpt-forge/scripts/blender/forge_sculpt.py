import argparse
import importlib
import json
import math
import os
import runpy
import sys
import time
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector


class PreviewSheet:
    views = (
        ("color", (-0.62, -1.0, 0.42), 1.0),
        ("color", (0.0, -1.0, 0.08), 1.0),
        ("color", (0.80, 0.85, 0.40), 1.0),
        ("clay", (-0.62, -1.0, 0.42), 1.0),
        ("clay", (0.0, -1.0, 0.10), 0.52),
        ("clay", (1.0, -0.12, 0.25), 1.0),
    )

    def __init__(self, tile=640, samples=24):
        self.tile = int(tile)
        self.samples = int(samples)

    @staticmethod
    def engine():
        items = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
        for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            if name in items:
                return name
        return "CYCLES"

    def stage(self, scene):
        scene.render.engine = self.engine()
        if scene.render.engine == "CYCLES":
            scene.cycles.device = "CPU"
            scene.cycles.samples = max(16, self.samples)
        else:
            scene.eevee.taa_render_samples = self.samples
        scene.render.resolution_x = self.tile
        scene.render.resolution_y = self.tile
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        try:
            scene.view_settings.view_transform = "AgX"
        except TypeError:
            scene.view_settings.view_transform = "Standard"
        for look in ("AgX - Base Contrast", "Base Contrast", "None"):
            try:
                scene.view_settings.look = look
                break
            except TypeError:
                continue
        world = bpy.data.worlds.new("_sf_world")
        if hasattr(world, "use_nodes") and not world.use_nodes:
            world.use_nodes = True
        bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
        bg.inputs["Color"].default_value = (0.78, 0.74, 0.70, 1.0)
        bg.inputs["Strength"].default_value = 0.75
        scene.world = world
        helpers = []
        key = bpy.data.lights.new("_sf_key", "SUN")
        key.energy = 3.2
        key.angle = math.radians(8.0)
        key_ob = bpy.data.objects.new("_sf_key", key)
        key_ob.rotation_euler = (math.radians(52.0), math.radians(8.0), math.radians(-38.0))
        scene.collection.objects.link(key_ob)
        helpers.append(key_ob)
        fill = bpy.data.lights.new("_sf_fill", "AREA")
        fill.energy = 220.0
        fill.size = 5.0
        fill_ob = bpy.data.objects.new("_sf_fill", fill)
        fill_ob.location = (4.0, -4.5, 3.0)
        fill_ob.rotation_euler = Vector((4.0, -4.5, 3.0)).to_track_quat("Z", "Y").to_euler()
        scene.collection.objects.link(fill_ob)
        helpers.append(fill_ob)
        gme = bpy.data.meshes.new("_sf_ground")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40.0)
        bm.to_mesh(gme)
        bm.free()
        gmat = bpy.data.materials.new("_sf_ground")
        if hasattr(gmat, "use_nodes") and not gmat.use_nodes:
            gmat.use_nodes = True
        gb = next(n for n in gmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        gb.inputs["Base Color"].default_value = (0.62, 0.58, 0.54, 1.0)
        gb.inputs["Roughness"].default_value = 0.9
        gme.materials.append(gmat)
        ground = bpy.data.objects.new("_sf_ground", gme)
        scene.collection.objects.link(ground)
        helpers.append(ground)
        clay = bpy.data.materials.new("_sf_clay")
        if hasattr(clay, "use_nodes") and not clay.use_nodes:
            clay.use_nodes = True
        cb = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        cb.inputs["Base Color"].default_value = (0.30, 0.30, 0.32, 1.0)
        cb.inputs["Roughness"].default_value = 0.34
        return helpers, clay

    def camera(self, scene, root, direction, fit):
        verts = np.empty(len(root.data.vertices) * 3, np.float32)
        root.data.vertices.foreach_get("co", verts)
        verts = verts.reshape(-1, 3)
        lo = Vector(verts.min(axis=0).tolist())
        hi = Vector(verts.max(axis=0).tolist())
        centre = (lo + hi) * 0.5
        if fit < 1.0:
            centre.z = lo.z + (hi.z - lo.z) * 0.58
        radius = max(0.1, (hi - lo).length * 0.5) * fit
        cam_data = bpy.data.cameras.new("_sf_cam")
        cam_data.lens = 60.0
        cam = bpy.data.objects.new("_sf_cam", cam_data)
        scene.collection.objects.link(cam)
        fov = 2.0 * math.atan(cam_data.sensor_width * 0.5 / cam_data.lens)
        dist = radius / math.sin(fov * 0.5) * 1.02
        d = Vector(direction).normalized()
        cam.location = centre + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam_data.clip_start = 0.01
        cam_data.clip_end = dist * 6.0
        scene.camera = cam
        return cam

    def render(self, root, out_png):
        scene = bpy.context.scene
        helpers, clay = self.stage(scene)
        tiles = []
        folder = os.path.dirname(out_png)
        own = list(root.data.materials)
        for index, (mode, direction, fit) in enumerate(self.views):
            cam = self.camera(scene, root, direction, fit)
            for slot in range(len(own)):
                root.data.materials[slot] = clay if mode == "clay" else own[slot]
            path = os.path.join(folder, "_sf_tile_{}.png".format(index))
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(path, check_existing=False)
            px = np.empty(self.tile * self.tile * 4, np.float32)
            img.pixels.foreach_get(px)
            tiles.append(px.reshape(self.tile, self.tile, 4))
            bpy.data.images.remove(img)
            os.remove(path)
            cam_data = cam.data
            bpy.data.objects.remove(cam, do_unlink=True)
            bpy.data.cameras.remove(cam_data)
        for slot in range(len(own)):
            root.data.materials[slot] = own[slot]
        cols = 3
        rows = int(math.ceil(len(tiles) / float(cols)))
        sheet = np.ones((rows * self.tile, cols * self.tile, 4), np.float32)
        for index, tile in enumerate(tiles):
            r = rows - 1 - index // cols
            c = index % cols
            sheet[r * self.tile:(r + 1) * self.tile, c * self.tile:(c + 1) * self.tile] = tile
        out = bpy.data.images.new("_sf_sheet", cols * self.tile, rows * self.tile, alpha=False)
        out.pixels.foreach_set(sheet.reshape(-1))
        out.filepath_raw = out_png
        out.file_format = "PNG"
        out.save()
        bpy.data.images.remove(out)
        for ob in helpers:
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
        bpy.data.materials.remove(clay)
        return out_png


class ForgeCli:
    def __init__(self, argv):
        parser = argparse.ArgumentParser(prog="forge_sculpt.py")
        parser.add_argument("--spec", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--only", default="")
        parser.add_argument("--voxel", type=float, default=None)
        parser.add_argument("--budget", type=int, default=None)
        parser.add_argument("--atlas", type=int, default=None)
        parser.add_argument("--target", choices=("prop", "library"), default=None)
        parser.add_argument("--no-render", dest="no_render", action="store_true")
        parser.add_argument("--no-validate", dest="no_validate", action="store_true")
        parser.add_argument("--tile", type=int, default=640)
        parser.add_argument("--samples", type=int, default=24)
        self.args = parser.parse_args(argv)
        self.here = os.path.dirname(os.path.abspath(__file__))
        self.prop_forge = os.path.normpath(os.path.join(self.here, "..", "..", "..", "prop-forge", "scripts", "blender"))

    def library(self):
        if self.here not in sys.path:
            sys.path.insert(0, self.here)
        return importlib.import_module("sculpt_forge")

    def studio_preview(self):
        path = os.path.join(self.prop_forge, "kawaii_studio.py")
        if not os.path.isfile(path):
            return None
        if self.prop_forge not in sys.path:
            sys.path.insert(0, self.prop_forge)
        try:
            return importlib.import_module("kawaii_studio").render_studio_preview
        except Exception as error:
            print("SCULPT_WARN studio preview unavailable: {}".format(error), flush=True)
            return None

    def validator(self):
        path = os.path.join(self.prop_forge, "validate_prop.py")
        if self.args.no_validate or not os.path.isfile(path):
            return None
        return runpy.run_path(path)["validate_scene"]

    def run(self):
        sf = self.library()
        spec_path = os.path.abspath(self.args.spec)
        out_dir = os.path.abspath(self.args.out)
        os.makedirs(out_dir, exist_ok=True)
        spec = sf.SpecRunner.load(spec_path)
        only = [s.strip() for s in self.args.only.split(",") if s.strip()]
        overrides = {"voxel": self.args.voxel, "budget": self.args.budget, "atlas": self.args.atlas, "target": self.args.target}
        palette = sf.SpecRunner.palette(spec)
        validate = self.validator()
        studio = None if self.args.no_render else self.studio_preview()
        sheet = None if self.args.no_render else PreviewSheet(self.args.tile, self.args.samples)
        report = {"spec": spec_path, "out": out_dir, "set": spec.get("set"), "blender": bpy.app.version_string, "palette": palette.roles, "props": []}
        failures = 0
        for prop in spec.get("props", []):
            if only and prop["id"] not in only:
                continue
            started = time.perf_counter()
            entry = {"id": prop["id"]}
            try:
                builder = sf.SpecRunner.builder(spec, prop, palette, overrides)
                entry.update(builder.build(out_dir))
                root = bpy.data.objects.get(prop["id"])
                if validate is not None and entry.get("target") == "prop":
                    lines = validate(prop["id"])
                    entry["validate"] = {"lines": lines, "fail": int(lines[-1].split("fail=")[1].split()[0]), "warn": int(lines[-1].split("warn=")[1].split()[0])}
                    failures += entry["validate"]["fail"]
                if sheet is not None and root is not None:
                    entry["sheet"] = sheet.render(root, os.path.join(out_dir, prop["id"] + "_sheet.png"))
                if studio is not None and root is not None:
                    preview = os.path.join(out_dir, prop["id"] + "_preview.png")
                    studio([root], preview, samples=self.args.samples)
                    entry["preview"] = preview
            except Exception as error:
                entry["error"] = "{}: {}".format(type(error).__name__, error)
                entry["trace"] = traceback.format_exc()
                failures += 1
                print("SCULPT_FAIL {} {}".format(prop["id"], entry["error"]), flush=True)
            entry["seconds"] = round(time.perf_counter() - started, 2)
            report["props"].append(entry)
            summary = {k: entry.get(k) for k in ("id", "tris", "budget", "seconds", "error")}
            summary["validate"] = {k: entry["validate"][k] for k in ("fail", "warn")} if "validate" in entry else None
            print("SCULPT_DONE " + json.dumps(summary), flush=True)
        report_path = os.path.join(out_dir, "report.json")
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, default=str)
        print("RESULT props={} fail={} report={}".format(len(report["props"]), failures, report_path), flush=True)
        return failures


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    failures = ForgeCli(argv).run()
    sys.stdout.flush()
    os._exit(1 if failures else 0)


if __name__ == "__main__":
    main()
