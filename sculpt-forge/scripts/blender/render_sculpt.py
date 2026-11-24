import argparse
import json
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector


class RenderOptions:
    @staticmethod
    def parse(argv):
        parser = argparse.ArgumentParser(prog="render_sculpt.py")
        parser.add_argument("--blend", default="")
        parser.add_argument("--out", default="")
        parser.add_argument("--views", type=int, default=4)
        parser.add_argument("--res", type=int, default=900)
        parser.add_argument("--qa", default="")
        parser.add_argument("--samples", type=int, default=32)
        parser.add_argument("--engine", default="auto", choices=["auto", "workbench", "eevee", "cycles"])
        parser.add_argument("--no-zebra", dest="no_zebra", action="store_true")
        parser.add_argument("--no-lineup", dest="no_lineup", action="store_true")
        return parser.parse_args(argv)

    @staticmethod
    def script_args():
        return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


class EngineChain:
    def __init__(self, scene, preferred):
        self.scene = scene
        self.preferred = preferred

    def set(self, name):
        try:
            self.scene.render.engine = name
        except TypeError:
            return False
        return self.scene.render.engine == name

    def eevee(self):
        for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            if self.set(name):
                return name
        return None

    def clay_chain(self):
        table = {"workbench": ["BLENDER_WORKBENCH", "EEVEE", "CYCLES"], "eevee": ["EEVEE", "CYCLES", "BLENDER_WORKBENCH"], "cycles": ["CYCLES", "EEVEE", "BLENDER_WORKBENCH"]}
        return table.get(self.preferred, table["workbench"])

    def colour_chain(self):
        table = {"workbench": ["BLENDER_WORKBENCH", "EEVEE", "CYCLES"], "eevee": ["EEVEE", "CYCLES", "BLENDER_WORKBENCH"], "cycles": ["CYCLES", "EEVEE", "BLENDER_WORKBENCH"]}
        return table.get(self.preferred, table["eevee"])

    def resolve(self, name):
        if name == "EEVEE":
            return self.eevee()
        return name if self.set(name) else None


class SolidLightRig:
    def __init__(self):
        self.saved = None

    @staticmethod
    def layout():
        return [
            (True, (-0.55, 0.50, 0.67), (1.00, 0.98, 0.95), (0.35, 0.35, 0.35), 0.0),
            (True, (0.80, 0.05, 0.60), (0.22, 0.23, 0.26), (0.05, 0.05, 0.05), 0.4),
            (True, (0.25, 0.55, -0.80), (0.40, 0.40, 0.42), (0.60, 0.60, 0.62), 0.0),
            (True, (0.05, -0.95, 0.30), (0.08, 0.08, 0.08), (0.0, 0.0, 0.0), 0.6),
        ]

    def apply(self):
        system = bpy.context.preferences.system
        self.saved = {"ambient": tuple(system.light_ambient), "edit": bool(getattr(system, "use_studio_light_edit", False)), "lights": [(light.use, tuple(light.direction), tuple(light.diffuse_color), tuple(light.specular_color), light.smooth) for light in system.solid_lights]}
        for light, (use, direction, diffuse, specular, smooth) in zip(system.solid_lights, self.layout()):
            light.use = use
            light.direction = direction
            light.diffuse_color = diffuse
            light.specular_color = specular
            light.smooth = smooth
        system.light_ambient = (0.06, 0.06, 0.065)

    def edit(self, enabled):
        system = bpy.context.preferences.system
        if hasattr(system, "use_studio_light_edit"):
            system.use_studio_light_edit = bool(enabled)

    def restore(self):
        if self.saved is None:
            return
        system = bpy.context.preferences.system
        system.light_ambient = self.saved["ambient"]
        for light, (use, direction, diffuse, specular, smooth) in zip(system.solid_lights, self.saved["lights"]):
            light.use = use
            light.direction = direction
            light.diffuse_color = diffuse
            light.specular_color = specular
            light.smooth = smooth
        self.edit(self.saved["edit"])
        self.saved = None


class ZebraMatcap:
    def __init__(self, folder):
        self.folder = folder
        self.light = None
        self.name = None
        self.failed = False

    @staticmethod
    def stripes(size, bands):
        rows, columns = np.mgrid[0:size, 0:size].astype(np.float64)
        x = (columns + 0.5) / size * 2.0 - 1.0
        y = (rows + 0.5) / size * 2.0 - 1.0
        z = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0))
        angle = np.arctan2(2.0 * z * y, 2.0 * z * z - 1.0)
        stripe = 0.5 + 0.5 * np.tanh(np.sin(angle * bands) * 7.0)
        tone = (0.05 + 0.88 * stripe) * (0.55 + 0.45 * z)
        pixels = np.ones((size, size, 4), dtype=np.float32)
        pixels[..., 0] = tone
        pixels[..., 1] = tone
        pixels[..., 2] = tone
        return pixels

    def ensure(self):
        if self.name or self.failed:
            return self.name
        path = os.path.join(self.folder, "_sculpt_zebra_matcap.exr")
        try:
            image = bpy.data.images.new("_sculpt_zebra", 512, 512, alpha=True, float_buffer=True)
            image.pixels.foreach_set(self.stripes(512, 14).ravel())
            image.filepath_raw = path
            image.file_format = "OPEN_EXR"
            image.save()
            bpy.data.images.remove(image)
            self.light = bpy.context.preferences.studio_lights.load(path, "MATCAP")
            self.name = self.light.name if self.light is not None else None
        except Exception as error:
            print("ZEBRA_SKIP {}: {}".format(type(error).__name__, error), flush=True)
            self.failed = True
            self.name = None
        return self.name

    def release(self):
        if self.light is not None:
            try:
                bpy.context.preferences.studio_lights.remove(self.light)
            except Exception:
                pass
        self.light = None
        self.name = None


class MaterialPreview:
    def __init__(self, target):
        self.target = target
        self.copies = {}

    @staticmethod
    def socket(sockets, name, kind):
        for item in sockets:
            if item.name == name and item.type == kind:
                return item
        return None

    @staticmethod
    def principled(tree):
        for node in tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                return node
        return None

    @staticmethod
    def uses_color_attribute(tree):
        return any(node.type == "VERTEX_COLOR" and node.outputs[0].is_linked for node in tree.nodes)

    def preview(self, material):
        if material is None:
            return None
        if material.name in self.copies:
            return self.copies[material.name]
        copy = material.copy()
        copy.name = "_sq_" + material.name
        self.copies[material.name] = copy
        if not copy.use_nodes or copy.node_tree is None:
            return copy
        tree = copy.node_tree
        shader = self.principled(tree)
        if shader is None:
            return copy
        shader_name = str(material.get("prop_forge_shader") or material.get("map_forge_shader") or "")
        if "emissive" in shader_name:
            strength = shader.inputs.get("Emission Strength")
            colour = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
            base = shader.inputs.get("Base Color")
            if colour is not None and not colour.is_linked and base is not None and base.is_linked:
                tree.links.new(base.links[0].from_socket, colour)
            if strength is not None and strength.default_value <= 0.0:
                strength.default_value = float(material.get("prop_forge_emissive_mult") or material.get("map_forge_emissive_mult") or 1.0) * 0.7
            return copy
        if self.uses_color_attribute(tree):
            return copy
        base = shader.inputs.get("Base Color")
        if base is None:
            return copy
        attribute = tree.nodes.new("ShaderNodeVertexColor")
        attribute.layer_name = "Color 1"
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        input_a = self.socket(mix.inputs, "A", "RGBA")
        input_b = self.socket(mix.inputs, "B", "RGBA")
        output = self.socket(mix.outputs, "Result", "RGBA")
        if input_a is None or input_b is None or output is None:
            return copy
        if base.is_linked:
            tree.links.new(base.links[0].from_socket, input_a)
        else:
            input_a.default_value = base.default_value
        if self.target == "map":
            split = tree.nodes.new("ShaderNodeSeparateColor")
            tree.links.new(attribute.outputs[0], split.inputs[0])
            tree.links.new(split.outputs[0], input_b)
        else:
            tree.links.new(attribute.outputs[0], input_b)
        tree.links.new(output, base)
        return copy

    def release(self):
        for copy in self.copies.values():
            if copy.users == 0:
                bpy.data.materials.remove(copy)
        self.copies = {}


class StudioScene:
    def __init__(self, options):
        self.options = options
        self.scene = bpy.data.scenes.new("_sculpt_studio")
        self.objects = []
        self.helpers = []
        self.materials = []
        self.world = bpy.data.worlds.new("_sculpt_world")
        self.world.use_nodes = True
        self.scene.world = self.world
        camera_data = bpy.data.cameras.new("_sculpt_camera")
        camera_data.lens = 70.0
        self.camera = bpy.data.objects.new("_sculpt_camera", camera_data)
        self.scene.collection.objects.link(self.camera)
        self.scene.camera = self.camera
        self.scene.render.film_transparent = False
        self.scene.render.resolution_percentage = 100
        self.scene.render.image_settings.file_format = "PNG"
        self.scene.render.image_settings.color_mode = "RGBA"
        self.chain = EngineChain(self.scene, options.engine)
        self.centre = Vector((0.0, 0.0, 0.0))
        self.radius = 1.0
        self.floor = 0.0
        self.distance = 1.0
        self.ground = None
        self.lights = []
        self.clay_material = None
        self.ground_material = None

    def add_drawables(self, sources):
        points = []
        for source in sources:
            copy = source.copy()
            copy.parent = None
            copy.matrix_world = source.matrix_world.copy()
            for modifier in list(copy.modifiers):
                if modifier.type == "ARMATURE":
                    copy.modifiers.remove(modifier)
            copy.hide_render = False
            copy.hide_viewport = False
            self.scene.collection.objects.link(copy)
            self.objects.append((copy, source))
            matrix = np.array(source.matrix_world)
            count = len(source.data.vertices)
            if count:
                buffer = np.empty(count * 3, dtype=np.float32)
                source.data.vertices.foreach_get("co", buffer)
                local = buffer.reshape(-1, 3).astype(np.float64)
                points.append(local @ matrix[:3, :3].T + matrix[:3, 3])
        if points:
            allpoints = np.concatenate(points, axis=0)
            low, high = allpoints.min(axis=0), allpoints.max(axis=0)
            self.centre = Vector(((low + high) * 0.5).tolist())
            self.radius = max(float(np.linalg.norm(allpoints - (low + high) * 0.5, axis=1).max()), 0.02)
            self.floor = float(low[2])
        self.build_ground()

    def build_ground(self):
        mesh = bpy.data.meshes.new("_sculpt_ground")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=self.radius * 30.0)
        bm.to_mesh(mesh)
        bm.free()
        self.ground = bpy.data.objects.new("_sculpt_ground", mesh)
        self.ground.location = (self.centre.x, self.centre.y, self.floor - self.radius * 0.002)
        self.scene.collection.objects.link(self.ground)
        self.helpers.append(self.ground)
        self.ground_material = bpy.data.materials.new("_sculpt_ground")
        self.ground_material.use_nodes = True
        shader = MaterialPreview.principled(self.ground_material.node_tree)
        shader.inputs["Base Color"].default_value = (0.30, 0.30, 0.31, 1.0)
        shader.inputs["Roughness"].default_value = 0.9
        mesh.materials.append(self.ground_material)
        self.materials.append(self.ground_material)

    def direction(self, index, views):
        base = math.atan2(-1.0, -0.62)
        angle = base + 2.0 * math.pi * index / max(views, 1)
        elevation = math.radians(24.0)
        return Vector((math.cos(angle) * math.cos(elevation), math.sin(angle) * math.cos(elevation), math.sin(elevation)))

    def aim(self, direction, resolution):
        self.scene.render.resolution_x = int(resolution)
        self.scene.render.resolution_y = int(resolution)
        data = self.camera.data
        fov = 2.0 * math.atan(data.sensor_width * 0.5 / data.lens)
        distance = self.radius / math.sin(fov * 0.5) * 1.04
        self.camera.location = self.centre + direction * distance
        self.camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        data.clip_start = max(distance * 0.01, 0.001)
        data.clip_end = distance * 20.0
        self.distance = distance

    def assign_source(self):
        for copy, source in self.objects:
            for index, slot in enumerate(copy.material_slots):
                slot.link = "OBJECT"
                slot.material = source.material_slots[index].material if index < len(source.material_slots) else None

    def assign_clay(self):
        material = self.clay()
        for copy, source in self.objects:
            for slot in copy.material_slots:
                slot.link = "OBJECT"
                slot.material = material

    def assign_preview(self, preview):
        for copy, source in self.objects:
            for index, slot in enumerate(copy.material_slots):
                slot.link = "OBJECT"
                slot.material = preview.preview(source.material_slots[index].material) if index < len(source.material_slots) else None

    def clay(self):
        if self.clay_material is None:
            self.clay_material = bpy.data.materials.new("_sculpt_clay")
            self.clay_material.use_nodes = True
            shader = MaterialPreview.principled(self.clay_material.node_tree)
            shader.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1.0)
            shader.inputs["Roughness"].default_value = 0.5
            specular = shader.inputs.get("Specular IOR Level") or shader.inputs.get("Specular")
            if specular is not None:
                specular.default_value = 0.4
            self.materials.append(self.clay_material)
        return self.clay_material

    def set_world(self, colour, strength):
        background = self.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs["Color"].default_value = (colour[0], colour[1], colour[2], 1.0)
            background.inputs["Strength"].default_value = strength
        self.world.color = colour

    def clear_lights(self):
        for light in self.lights:
            data = light.data
            bpy.data.objects.remove(light, do_unlink=True)
            bpy.data.lights.remove(data)
        self.lights = []

    def add_light(self, name, direction, energy, size, colour):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.size = size
        data.color = colour
        light = bpy.data.objects.new(name, data)
        offset = Vector(direction).normalized() * self.distance * 0.9
        light.location = self.centre + offset
        light.rotation_euler = (-offset).to_track_quat("-Z", "Y").to_euler()
        self.scene.collection.objects.link(light)
        self.lights.append(light)

    def camera_relative(self, right, up, back):
        forward = (self.centre - self.camera.location).normalized()
        side = forward.cross(Vector((0.0, 0.0, 1.0)))
        if side.length < 1e-6:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        top = side.cross(forward).normalized()
        return side * right + top * up - forward * back

    def lit_rig(self, key, fill, rim, kicker):
        self.clear_lights()
        scale = (self.distance * 0.9) ** 2
        self.add_light("_sculpt_key", self.camera_relative(-0.75, 0.75, 0.55), key * scale, self.radius * 0.9, (1.0, 0.98, 0.95))
        self.add_light("_sculpt_fill", self.camera_relative(0.95, 0.15, 0.6), fill * scale, self.radius * 2.4, (0.92, 0.95, 1.0))
        self.add_light("_sculpt_rim", self.camera_relative(0.35, 0.65, -0.85), rim * scale, self.radius * 0.8, (1.0, 1.0, 1.0))
        if kicker > 0.0:
            self.add_light("_sculpt_kicker", self.camera_relative(-0.98, -0.05, -0.2), kicker * scale, self.radius * 0.5, (1.0, 1.0, 1.0))

    def workbench_base(self):
        shading = self.scene.display.shading
        shading.show_object_outline = False
        shading.show_backface_culling = False
        self.scene.display.render_aa = "16"
        self.set_view_transform("Standard")
        self.clear_lights()
        return shading

    def setup_workbench_clay(self):
        shading = self.workbench_base()
        shading.light = "STUDIO"
        try:
            shading.studio_light = "Default"
        except TypeError:
            pass
        shading.color_type = "OBJECT"
        shading.show_specular_highlight = True
        shading.show_cavity = True
        shading.cavity_type = "BOTH"
        shading.cavity_ridge_factor = 1.0
        shading.cavity_valley_factor = 1.0
        shading.curvature_ridge_factor = 0.8
        shading.curvature_valley_factor = 1.0
        shading.show_shadows = True
        shading.shadow_intensity = 0.45
        self.scene.display.light_direction = (-0.45, -0.35, 0.82)
        self.scene.display.shadow_focus = 0.35
        self.scene.display.matcap_ssao_distance = self.radius * 0.35
        self.scene.display.matcap_ssao_attenuation = 1.0
        self.scene.display.matcap_ssao_samples = 24
        self.set_world((0.13, 0.135, 0.145), 1.0)
        for copy, source in self.objects:
            copy.color = (0.80, 0.80, 0.80, 1.0)
        self.ground.color = (0.30, 0.30, 0.32, 1.0)
        self.ground.hide_render = False

    def setup_workbench_zebra(self, matcap):
        shading = self.workbench_base()
        shading.light = "MATCAP"
        shading.studio_light = matcap
        shading.color_type = "OBJECT"
        shading.show_specular_highlight = False
        shading.show_cavity = False
        shading.show_shadows = False
        self.set_world((0.20, 0.21, 0.23), 1.0)
        for copy, source in self.objects:
            copy.color = (1.0, 1.0, 1.0, 1.0)
        self.ground.hide_render = True

    def setup_lit_clay(self, engine):
        self.assign_clay()
        self.ground.hide_render = False
        self.set_world((0.11, 0.115, 0.125), 0.5)
        self.set_view_transform("Standard")
        scale = 0.55 if engine == "CYCLES" else 1.0
        self.lit_rig(7.0 * scale, 1.6 * scale, 7.0 * scale, 2.5 * scale)
        self.engine_quality(engine)

    def setup_colour(self, engine, preview):
        self.assign_preview(preview)
        self.ground.hide_render = False
        if engine == "BLENDER_WORKBENCH":
            shading = self.workbench_base()
            shading.light = "STUDIO"
            shading.color_type = "TEXTURE"
            shading.show_cavity = False
            shading.show_shadows = True
            shading.show_specular_highlight = True
            self.set_world((0.55, 0.55, 0.56), 1.0)
            self.ground.color = (0.62, 0.61, 0.6, 1.0)
            return
        self.set_world((0.42, 0.42, 0.43), 0.55)
        self.set_view_transform("Standard")
        scale = 0.6 if engine == "CYCLES" else 1.0
        self.lit_rig(13.0 * scale, 3.5 * scale, 9.0 * scale, 0.0)
        self.ground_material.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.55, 0.54, 0.53, 1.0)
        self.engine_quality(engine)

    def engine_quality(self, engine):
        if engine == "CYCLES":
            cycles = self.scene.cycles
            cycles.device = "CPU"
            cycles.samples = max(16, int(self.options.samples))
            cycles.use_denoising = True
            cycles.max_bounces = 4
        elif engine and engine.startswith("BLENDER_EEVEE"):
            eevee = self.scene.eevee
            eevee.taa_render_samples = max(8, int(self.options.samples))
            if hasattr(eevee, "use_gtao"):
                eevee.use_gtao = True
            if hasattr(eevee, "gtao_distance"):
                eevee.gtao_distance = self.radius * 0.3
            if hasattr(eevee, "use_shadows"):
                eevee.use_shadows = True

    def set_view_transform(self, name):
        settings = self.scene.view_settings
        for candidate in (name, "Standard", "Filmic", "AgX"):
            try:
                settings.view_transform = candidate
                break
            except TypeError:
                continue
        try:
            settings.look = "None"
        except TypeError:
            pass
        settings.exposure = 0.0
        settings.gamma = 1.0

    def render(self, path):
        self.scene.render.filepath = path
        if os.path.isfile(path):
            os.remove(path)
        with bpy.context.temp_override(scene=self.scene):
            bpy.ops.render.render(write_still=True, scene=self.scene.name)
        return os.path.isfile(path)

    def dispose(self):
        self.clear_lights()
        for copy, source in self.objects:
            bpy.data.objects.remove(copy, do_unlink=True)
        for helper in self.helpers:
            data = helper.data
            bpy.data.objects.remove(helper, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        camera_data = self.camera.data
        bpy.data.objects.remove(self.camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
        for material in self.materials:
            if material.users == 0:
                bpy.data.materials.remove(material)
        bpy.data.scenes.remove(self.scene)
        if self.world.users == 0:
            bpy.data.worlds.remove(self.world)


class ImageSheet:
    @staticmethod
    def load(path):
        image = bpy.data.images.load(path, check_existing=False)
        width, height = image.size
        buffer = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(buffer)
        bpy.data.images.remove(image)
        return buffer.reshape(height, width, 4)

    @staticmethod
    def save(pixels, path):
        height, width = pixels.shape[:2]
        image = bpy.data.images.new("_sculpt_sheet", width, height, alpha=True)
        image.pixels.foreach_set(np.ascontiguousarray(pixels, dtype=np.float32).ravel())
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)
        return path

    @staticmethod
    def fit(pixels, width, height):
        source_height, source_width = pixels.shape[:2]
        rows = np.clip((np.arange(height) * source_height / max(height, 1)).astype(np.int64), 0, source_height - 1)
        columns = np.clip((np.arange(width) * source_width / max(width, 1)).astype(np.int64), 0, source_width - 1)
        return pixels[rows][:, columns]

    @classmethod
    def grid(cls, tiles, columns, tile_width, tile_height, gap, background):
        rows = int(math.ceil(len(tiles) / float(max(columns, 1))))
        width = columns * tile_width + (columns + 1) * gap
        height = rows * tile_height + (rows + 1) * gap
        sheet = np.empty((height, width, 4), dtype=np.float32)
        sheet[:, :] = background
        for index, tile in enumerate(tiles):
            row, column = index // columns, index % columns
            fitted = cls.fit(tile, tile_width, tile_height)
            top = height - gap - (row + 1) * tile_height - row * gap
            left = gap + column * (tile_width + gap)
            sheet[top:top + tile_height, left:left + tile_width] = fitted
        return sheet


class LabelPainter:
    def paint(self, text, width, height, path):
        scene = bpy.data.scenes.new("_sculpt_label")
        world = bpy.data.worlds.new("_sculpt_label_world")
        scene.world = world
        world.color = (0.07, 0.075, 0.08)
        curve = bpy.data.curves.new("_sculpt_label_text", "FONT")
        curve.body = text
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        curve.size = 1.0
        label = bpy.data.objects.new("_sculpt_label_text", curve)
        label.color = (1.0, 1.0, 1.0, 1.0)
        scene.collection.objects.link(label)
        camera_data = bpy.data.cameras.new("_sculpt_label_camera")
        camera_data.type = "ORTHO"
        aspect = width / float(height)
        camera_data.ortho_scale = max(len(text) * 0.62 + 0.8, aspect * 1.6)
        camera = bpy.data.objects.new("_sculpt_label_camera", camera_data)
        camera.location = (0.0, 0.0, 10.0)
        scene.collection.objects.link(camera)
        scene.camera = camera
        scene.render.resolution_x = int(width)
        scene.render.resolution_y = int(height)
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        result = False
        try:
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.display.shading.light = "FLAT"
            scene.display.shading.color_type = "OBJECT"
            scene.display.render_aa = "8"
            try:
                scene.view_settings.view_transform = "Standard"
            except TypeError:
                pass
            with bpy.context.temp_override(scene=scene):
                bpy.ops.render.render(write_still=True, scene=scene.name)
            result = os.path.isfile(path)
        except Exception:
            result = False
        bpy.data.objects.remove(label, do_unlink=True)
        bpy.data.curves.remove(curve)
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
        bpy.data.scenes.remove(scene)
        bpy.data.worlds.remove(world)
        return result


class DrawablePicker:
    @staticmethod
    def is_collider(ob):
        return "_col_" in ob.name or "prop_forge_collision" in ob or "map_forge_collision" in ob

    @classmethod
    def pick(cls, stem):
        meshes = [ob for ob in bpy.context.scene.objects if ob.type == "MESH" and not cls.is_collider(ob) and len(ob.data.polygons) > 0]
        named = [ob for ob in meshes if ob.name == stem]
        if named:
            return named
        tagged = [ob for ob in meshes if "prop_forge" in ob or "map_forge" in ob]
        if tagged:
            return tagged
        return [ob for ob in meshes if not ob.name.endswith("_high") and not ob.hide_render]

    @staticmethod
    def target(ob):
        if "map_forge" in ob:
            return "map"
        for material in ob.data.materials:
            if material is not None and "map_forge_shader" in material:
                return "map"
        return "prop"


class SculptRenderer:
    def __init__(self, options):
        self.options = options
        self.options.blend = os.path.abspath(options.blend) if options.blend else ""
        default_out = os.path.join(os.path.dirname(self.options.blend if os.path.isfile(self.options.blend) else (self.options.blend or bpy.data.filepath or os.getcwd())), "sculpt_renders")
        self.out = os.path.abspath(options.out) if options.out else default_out
        os.makedirs(self.out, exist_ok=True)
        self.work = os.path.join(self.out, "_tiles")
        os.makedirs(self.work, exist_ok=True)
        self.manifest = []
        self.lights = SolidLightRig()
        self.zebra = ZebraMatcap(self.work)
        self.labels = LabelPainter()
        self.verdicts = self.read_verdicts(options.qa)

    @staticmethod
    def read_verdicts(path):
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        return {item.get("drawable"): (item.get("fail", 0), item.get("warn", 0)) for item in data.get("drawables", [])}

    def files(self):
        source = self.options.blend
        if not source:
            return [None]
        if os.path.isdir(source):
            return [os.path.join(source, name) for name in sorted(os.listdir(source)) if name.lower().endswith(".blend") and not name.lower().endswith("_high.blend")]
        return [source]

    def open_file(self, path):
        if path is None or os.path.abspath(bpy.data.filepath or "") == os.path.abspath(path):
            return True
        if not bpy.app.background and bpy.data.is_dirty:
            print("RENDER_SKIP {} (the open file has unsaved changes; save it or run headless)".format(path), flush=True)
            return False
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        return True

    def prepare(self, studio, engine, mode, preview):
        if mode == "colour":
            self.lights.edit(False)
            studio.setup_colour(engine, preview)
        elif engine == "BLENDER_WORKBENCH":
            self.lights.edit(True)
            studio.assign_source()
            studio.setup_workbench_clay()
        else:
            self.lights.edit(False)
            studio.setup_lit_clay(engine)

    def render_pass(self, studio, chain, path, mode, preview):
        errors = []
        for name in chain:
            engine = studio.chain.resolve(name)
            if engine is None:
                errors.append("{} unavailable".format(name))
                continue
            try:
                self.prepare(studio, engine, mode, preview)
                if studio.render(path):
                    return engine, errors
                errors.append("{} wrote nothing".format(engine))
            except Exception as error:
                errors.append("{}: {}".format(engine, error))
        return None, errors

    def render_zebra(self, studio, path):
        if self.options.no_zebra:
            return None, []
        matcap = self.zebra.ensure()
        if not matcap or studio.chain.resolve("BLENDER_WORKBENCH") is None:
            return None, ["zebra unavailable"]
        try:
            self.lights.edit(False)
            studio.assign_source()
            studio.setup_workbench_zebra(matcap)
            if studio.render(path):
                return "BLENDER_WORKBENCH", []
            return None, ["zebra wrote nothing"]
        except Exception as error:
            return None, ["zebra: {}".format(error)]

    def render_drawable(self, path, ob):
        started = time.perf_counter()
        name = ob.name
        target = DrawablePicker.target(ob)
        studio = StudioScene(self.options)
        preview = MaterialPreview(target)
        entry = {"file": path, "drawable": name, "target": target, "outputs": {}, "engines": {}, "errors": []}
        try:
            studio.add_drawables([ob])
            resolution = max(128, int(self.options.res))
            front = studio.direction(0, self.options.views)
            for mode, chain in (("clay", studio.chain.clay_chain()), ("colour", studio.chain.colour_chain())):
                studio.aim(front, resolution)
                output = os.path.join(self.out, "{}_{}.png".format(name, mode))
                engine, errors = self.render_pass(studio, chain, output, mode, preview)
                entry["engines"][mode] = engine
                entry["errors"] += errors
                if engine:
                    entry["outputs"][mode] = output
            studio.aim(front, resolution)
            output = os.path.join(self.out, name + "_zebra.png")
            engine, errors = self.render_zebra(studio, output)
            entry["errors"] += errors
            if engine:
                entry["engines"]["zebra"] = engine
                entry["outputs"]["zebra"] = output
            tile = max(256, resolution * 2 // 3)
            tiles = []
            for index in range(max(1, self.options.views)):
                studio.aim(studio.direction(index, self.options.views), tile)
                tile_path = os.path.join(self.work, "{}_view{}.png".format(name, index))
                engine, errors = self.render_pass(studio, studio.chain.clay_chain(), tile_path, "clay", preview)
                entry["errors"] += errors
                if engine:
                    tiles.append(ImageSheet.load(tile_path))
            if tiles:
                columns = int(math.ceil(math.sqrt(len(tiles))))
                sheet = ImageSheet.grid(tiles, columns, tile, tile, max(4, tile // 90), np.array([0.05, 0.05, 0.055, 1.0], dtype=np.float32))
                entry["outputs"]["turntable"] = ImageSheet.save(sheet, os.path.join(self.out, name + "_turntable.png"))
        finally:
            studio.dispose()
            preview.release()
        entry["seconds"] = round(time.perf_counter() - started, 2)
        verdict = self.verdicts.get(name)
        entry["label"] = name if verdict is None else "{}  F{} W{}".format(name, verdict[0], verdict[1])
        self.manifest.append(entry)
        print("RENDER {} {} engines={} {:.1f}s{}".format(name, " ".join("{}=ok".format(kind) for kind in entry["outputs"]), entry["engines"], entry["seconds"], (" errors=" + "; ".join(entry["errors"])) if entry["errors"] else ""), flush=True)

    def render_file(self, path):
        if not self.open_file(path):
            return
        current = path or bpy.data.filepath
        stem = os.path.splitext(os.path.basename(current))[0] if current else ""
        drawables = DrawablePicker.pick(stem)
        if not drawables:
            print("RENDER_SKIP {} (no drawable mesh)".format(current), flush=True)
            return
        self.lights.apply()
        try:
            for ob in drawables:
                self.render_drawable(current, ob)
        finally:
            self.lights.restore()

    def lineup(self):
        entries = [entry for entry in self.manifest if entry["outputs"]]
        if len(entries) < 2 or self.options.no_lineup:
            return {}
        columns = int(math.ceil(math.sqrt(len(entries) * 1.6)))
        tile = max(220, int(self.options.res) // 3)
        label_height = max(28, tile // 8)
        results = {}
        for kind in ("clay", "colour", "zebra"):
            if not any(kind in entry["outputs"] for entry in entries):
                continue
            tiles = []
            for entry in entries:
                source = entry["outputs"].get(kind)
                body = ImageSheet.fit(ImageSheet.load(source), tile, tile) if source else np.zeros((tile, tile, 4), dtype=np.float32)
                label_path = os.path.join(self.work, "{}_label.png".format(entry["drawable"]))
                if not os.path.isfile(label_path):
                    self.labels.paint(entry["label"], tile, label_height, label_path)
                strip = ImageSheet.fit(ImageSheet.load(label_path), tile, label_height) if os.path.isfile(label_path) else np.zeros((label_height, tile, 4), dtype=np.float32)
                tiles.append(np.concatenate([strip, body], axis=0))
            sheet = ImageSheet.grid(tiles, columns, tile, tile + label_height, max(4, tile // 60), np.array([0.05, 0.05, 0.055, 1.0], dtype=np.float32))
            results[kind] = ImageSheet.save(sheet, os.path.join(self.out, "lineup_{}.png".format(kind)))
        return results

    def run(self):
        try:
            for path in self.files():
                try:
                    self.render_file(path)
                except Exception as error:
                    print("RENDER_FAIL {}: {}: {}".format(path, type(error).__name__, error), flush=True)
                    self.manifest.append({"file": path, "drawable": os.path.basename(path or "scene"), "outputs": {}, "errors": [str(error)]})
            sheets = self.lineup()
        finally:
            self.zebra.release()
        with open(os.path.join(self.out, "render_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({"drawables": self.manifest, "lineup": sheets, "views": self.options.views, "res": self.options.res}, handle, indent=1)
        produced = sum(1 for entry in self.manifest if entry.get("outputs"))
        missing = sum(1 for entry in self.manifest if not entry.get("outputs"))
        print("SCULPT_RENDER drawables={} rendered={} failed={} lineup={} out={}".format(len(self.manifest), produced, missing, ",".join(sorted(sheets)) or "none", self.out), flush=True)
        return missing


def main():
    options = RenderOptions.parse(RenderOptions.script_args())
    missing = SculptRenderer(options).run()
    if bpy.app.background:
        sys.stdout.flush()
        sys.exit(1 if missing else 0)
    return missing


if __name__ == "__main__":
    main()
