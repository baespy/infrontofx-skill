"""weapon-forge: Headless Blender 4.2 Cycles 3D VFX Sprite & 3D Screen Overlay Generator.

Sculpts genuine 3D multi-material meshes (chopped/woven Forged Carbon Fiber with automotive
clearcoat, cold brushed Gunmetal Titanium chamfers, Antique Samurai Gold accents, and deep
Blood-Ruby / HDR Crimson veins) and raytraces RGBA assets:
  1. 1920x1080 RGBA Hit & Kill Screen Overlays (strictly clear center alpha=0, continuous 3D
     stepped Forged-Carbon perimeter bezel + volumetric obsidian smoke + 3D Oni horns/shards)
  2. 512x512 / 256x256 RGBA 3D PTFX Sprites & 2x2 Flipbook Sheet Cells (slashes, shards, blades, ground seal)
  3. 512x128 RGBA Seamless Single-Line Ribbon Trail Texture (U along length, V across width)

Usage:
  blender -b --factory-startup -P render_fx_assets.py -- \
      --prefix onikage \
      --out-screen "path/to/effect_dir" \
      --out-ptfx "path/to/weapon_source_dir" \
      [--primary "#dc0008"] [--secondary "#c4913a"] [--dark "#07070a"] [--samples 44]
"""

import argparse
import math
import os
import random
import struct
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector


def hex_to_linear_rgb(h):
    s = h.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    sr, sg, sb = (int(s[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def to_lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (to_lin(sr), to_lin(sg), to_lin(sb))


def hex_to_srgb_float(h):
    s = h.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return (
        int(s[0:2], 16) / 255.0,
        int(s[2:4], 16) / 255.0,
        int(s[4:6], 16) / 255.0,
    )


def save_rgba_png(path, rgba_u8):
    """Write top-down (H, W, 4) uint8 RGBA numpy array directly to an optimized PNG file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    h, w, _ = rgba_u8.shape
    raw_rows = b"".join(b"\x00" + rgba_u8[y].tobytes() for y in range(h))
    compressed = zlib.compress(raw_rows, level=6)

    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png_bytes = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png_bytes)
    return len(png_bytes)


def box_blur_2d(img, radius):
    if radius < 1:
        return img
    k = 2 * radius + 1
    pad_y = np.pad(img, ((radius, radius), (0, 0), (0, 0)), mode="edge")
    cs_y = np.cumsum(np.pad(pad_y, ((1, 0), (0, 0), (0, 0)), mode="constant"), axis=0)
    blur_y = (cs_y[k:] - cs_y[:-k]) / float(k)
    pad_x = np.pad(blur_y, ((0, 0), (radius, radius), (0, 0)), mode="edge")
    cs_x = np.cumsum(np.pad(pad_x, ((0, 0), (1, 0), (0, 0)), mode="constant"), axis=1)
    return (cs_x[:, k:] - cs_x[:, :-k]) / float(k)


def gaussian_approx(img, radius):
    if radius < 1:
        return img
    return box_blur_2d(box_blur_2d(img, radius), max(1, radius // 2))


def fbm_smoke_2d(h, w, seed=42, base_grid=(9, 16), octaves=5):
    """Fast vectorized multi-octave value-noise FBM for organic volumetric carbon smoke."""
    rng = np.random.RandomState(seed)
    acc = np.zeros((h, w), dtype=np.float32)
    amp = 0.52
    tot = 0.0
    gy, gx = base_grid
    yy = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    for _ in range(octaves):
        grid = rng.uniform(0.0, 1.0, size=(gy + 2, gx + 2)).astype(np.float32)
        fy = yy * gy
        fx = xx * gx
        iy = fy.astype(np.int32)
        ix = fx.astype(np.int32)
        ty = fy - iy
        tx = fx - ix
        sy = ty * ty * (3.0 - 2.0 * ty)
        sx = tx * tx * (3.0 - 2.0 * tx)
        v00 = grid[iy, ix]
        v10 = grid[iy, ix + 1]
        v01 = grid[iy + 1, ix]
        v11 = grid[iy + 1, ix + 1]
        val = (v00 * (1.0 - sx) + v10 * sx) * (1.0 - sy) + (v01 * (1.0 - sx) + v11 * sx) * sy
        acc += val * amp
        tot += amp
        amp *= 0.52
        gy = min(h // 2, gy * 2 + 1)
        gx = min(w // 2, gx * 2 + 1)
    return acc / max(tot, 1e-5)


def reset_scene(samples=44, res_x=512, res_y=512):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.018
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 5
    sc.cycles.glossy_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.transmission_bounces = 3
    sc.render.film_transparent = True
    sc.render.resolution_x = res_x
    sc.render.resolution_y = res_y
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"

    world = bpy.data.worlds.new("FXWorld")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.005, 0.006, 0.009, 1.0)
    bg.inputs["Strength"].default_value = 0.25
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return sc


def build_materials(primary_hex="#dc0008", secondary_hex="#c4913a", dark_hex="#07070a"):
    p_lin = hex_to_linear_rgb(primary_hex)
    s_lin = hex_to_linear_rgb(secondary_hex)
    d_lin = hex_to_linear_rgb(dark_hex)

    # 1. Authentic Chopped & Woven Forged Carbon Fiber (ZERO orange Voronoi cracks; pure dark luxury carbon!)
    mat_carbon = bpy.data.materials.new("ForgedCarbon")
    mat_carbon.use_nodes = True
    nt = mat_carbon.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.84
    bsdf.inputs["IOR"].default_value = 1.58
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.035

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 34.0
    vor.inputs["Randomness"].default_value = 0.96
    nt.links.new(tex_coord.outputs["Object"], vor.inputs["Vector"])

    # Perturb wave vector per Voronoi cell so each chopped carbon tow has its own fiber angle!
    vec_mad = nt.nodes.new("ShaderNodeVectorMath")
    vec_mad.operation = "MULTIPLY_ADD"
    vec_mad.inputs[1].default_value = (4.5, 4.5, 4.5)
    nt.links.new(vor.outputs["Color"], vec_mad.inputs[0])
    nt.links.new(tex_coord.outputs["Object"], vec_mad.inputs[2])

    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = 88.0
    wave.inputs["Distortion"].default_value = 0.45
    nt.links.new(vec_mad.outputs["Vector"], wave.inputs["Vector"])

    # Pitch-black obsidian to dark graphite specular carbon chips (strictly dark!)
    ramp_col = nt.nodes.new("ShaderNodeValToRGB")
    ramp_col.color_ramp.interpolation = "CONSTANT"
    ramp_col.color_ramp.elements[0].position = 0.0
    ramp_col.color_ramp.elements[0].color = (
        max(0.0025, d_lin[0] * 0.45),
        max(0.0025, d_lin[1] * 0.45),
        max(0.0035, d_lin[2] * 0.55),
        1.0,
    )
    e_mid = ramp_col.color_ramp.elements.new(0.42)
    e_mid.color = (0.010, 0.011, 0.014, 1.0)
    ramp_col.color_ramp.elements[-1].position = 0.76
    ramp_col.color_ramp.elements[-1].color = (0.026, 0.028, 0.034, 1.0)
    nt.links.new(vor.outputs["Color"], ramp_col.inputs["Fac"])
    nt.links.new(ramp_col.outputs["Color"], bsdf.inputs["Base Color"])

    # Sharp per-chip roughness contrast so individual forged carbon flakes catch light at different angles
    ramp_rgh = nt.nodes.new("ShaderNodeValToRGB")
    ramp_rgh.color_ramp.elements[0].position = 0.15
    ramp_rgh.color_ramp.elements[0].color = (0.075, 0.075, 0.075, 1.0)
    ramp_rgh.color_ramp.elements[1].position = 0.85
    ramp_rgh.color_ramp.elements[1].color = (0.29, 0.29, 0.29, 1.0)
    nt.links.new(vor.outputs["Color"], ramp_rgh.inputs["Fac"])
    nt.links.new(ramp_rgh.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.008
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # 2. Cold Brushed Gunmetal Titanium (for precision CNC chamfers & katana blade bevels!)
    mat_steel = bpy.data.materials.new("GunmetalTitanium")
    mat_steel.use_nodes = True
    nts = mat_steel.node_tree
    nts.nodes.clear()
    outs = nts.nodes.new("ShaderNodeOutputMaterial")
    bsdfs = nts.nodes.new("ShaderNodeBsdfPrincipled")
    bsdfs.inputs["Base Color"].default_value = (0.115, 0.122, 0.140, 1.0)
    bsdfs.inputs["Metallic"].default_value = 0.97
    bsdfs.inputs["Roughness"].default_value = 0.15
    tcs = nts.nodes.new("ShaderNodeTexCoord")
    wvs = nts.nodes.new("ShaderNodeTexWave")
    wvs.inputs["Scale"].default_value = 120.0
    nts.links.new(tcs.outputs["Object"], wvs.inputs["Vector"])
    bmps = nts.nodes.new("ShaderNodeBump")
    bmps.inputs["Strength"].default_value = 0.08
    bmps.inputs["Distance"].default_value = 0.004
    nts.links.new(wvs.outputs["Fac"], bmps.inputs["Height"])
    nts.links.new(bmps.outputs["Normal"], bsdfs.inputs["Normal"])
    nts.links.new(bsdfs.outputs["BSDF"], outs.inputs["Surface"])

    # 3. Restrained Antique Samurai Gold / Bronze (never clips to neon lemon yellow!)
    mat_gold = bpy.data.materials.new("AntiqueSamuraiGold")
    mat_gold.use_nodes = True
    ntg = mat_gold.node_tree
    ntg.nodes.clear()
    outg = ntg.nodes.new("ShaderNodeOutputMaterial")
    bsdfg = ntg.nodes.new("ShaderNodeBsdfPrincipled")
    bsdfg.inputs["Base Color"].default_value = (
        min(0.42, s_lin[0] * 0.72),
        min(0.21, s_lin[1] * 0.56),
        min(0.045, s_lin[2] * 0.40),
        1.0,
    )
    bsdfg.inputs["Metallic"].default_value = 0.96
    bsdfg.inputs["Roughness"].default_value = 0.23
    tcg = ntg.nodes.new("ShaderNodeTexCoord")
    nsg = ntg.nodes.new("ShaderNodeTexNoise")
    nsg.inputs["Scale"].default_value = 75.0
    nsg.inputs["Detail"].default_value = 5.0
    ntg.links.new(tcg.outputs["Object"], nsg.inputs["Vector"])
    bmpg = ntg.nodes.new("ShaderNodeBump")
    bmpg.inputs["Strength"].default_value = 0.12
    bmpg.inputs["Distance"].default_value = 0.005
    ntg.links.new(nsg.outputs["Fac"], bmpg.inputs["Height"])
    ntg.links.new(bmpg.outputs["Normal"], bsdfg.inputs["Normal"])
    ntg.links.new(bsdfg.outputs["BSDF"], outg.inputs["Surface"])

    # 4. Faceted Blood-Ruby Crystal (dark crimson metallic-glass facets + deep inner ruby glow, zero orange!)
    mat_ruby = bpy.data.materials.new("BloodRubyCrystal")
    mat_ruby.use_nodes = True
    ntr = mat_ruby.node_tree
    ntr.nodes.clear()
    outr = ntr.nodes.new("ShaderNodeOutputMaterial")
    bsdfr = ntr.nodes.new("ShaderNodeBsdfPrincipled")
    bsdfr.inputs["Base Color"].default_value = (max(0.22, p_lin[0] * 0.35), 0.002, 0.006, 1.0)
    bsdfr.inputs["Metallic"].default_value = 0.42
    bsdfr.inputs["Roughness"].default_value = 0.065
    bsdfr.inputs["IOR"].default_value = 1.77
    if "Coat Weight" in bsdfr.inputs:
        bsdfr.inputs["Coat Weight"].default_value = 1.0
        bsdfr.inputs["Coat Roughness"].default_value = 0.02
    lwr = ntr.nodes.new("ShaderNodeLayerWeight")
    lwr.inputs["Blend"].default_value = 0.42
    rr = ntr.nodes.new("ShaderNodeValToRGB")
    rr.color_ramp.elements[0].position = 0.0
    rr.color_ramp.elements[0].color = (p_lin[0], 0.001, 0.004, 1.0)
    rr.color_ramp.elements[1].position = 0.78
    rr.color_ramp.elements[1].color = (p_lin[0] * 0.12, 0.0, 0.001, 1.0)
    ntr.links.new(lwr.outputs["Facing"], rr.inputs["Fac"])
    if "Emission Color" in bsdfr.inputs:
        ntr.links.new(rr.outputs["Color"], bsdfr.inputs["Emission Color"])
        bsdfr.inputs["Emission Strength"].default_value = 1.45
    ntr.links.new(bsdfr.outputs["BSDF"], outr.inputs["Surface"])

    # 5. Pure Razor Blood-Crimson Plasma (strictly G~0, B~0 so it NEVER shifts orange or salmon pink!)
    mat_plasma = bpy.data.materials.new("CrimsonPlasma")
    mat_plasma.use_nodes = True
    ntp = mat_plasma.node_tree
    ntp.nodes.clear()
    outp = ntp.nodes.new("ShaderNodeOutputMaterial")
    lw = ntp.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.30
    rp = ntp.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].position = 0.0
    rp.color_ramp.elements[0].color = (min(1.0, p_lin[0] * 1.1), 0.002, 0.006, 1.0)
    rp.color_ramp.elements[1].position = 0.88
    rp.color_ramp.elements[1].color = (p_lin[0] * 0.42, 0.0, 0.002, 1.0)
    ntp.links.new(lw.outputs["Facing"], rp.inputs["Fac"])
    emit = ntp.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 2.35
    ntp.links.new(rp.outputs["Color"], emit.inputs["Color"])
    ntp.links.new(emit.outputs["Emission"], outp.inputs["Surface"])

    return {
        "carbon": mat_carbon,
        "steel": mat_steel,
        "gold": mat_gold,
        "ruby": mat_ruby,
        "plasma": mat_plasma,
    }


def add_studio_lights(sc, primary_hex="#dc0008"):
    p_lin = hex_to_linear_rgb(primary_hex)

    def mk_area(name, loc, rot_deg, energy, size, col):
        ld = bpy.data.lights.new(name, type="AREA")
        ld.energy = energy
        ld.size = size
        ld.color = col
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = Euler([math.radians(a) for a in rot_deg], "XYZ")
        sc.collection.objects.link(ob)
        return ob

    # Calibrated high-contrast automotive carbon lighting (highlights carbon clearcoat & steel chamfers cleanly!)
    mk_area("KeyCoolSilver", (-2.1, -1.8, 3.8), (28, -26, 0), 62.0, 2.6, (0.88, 0.93, 1.0))
    mk_area("FillSlate", (2.3, -1.4, 3.1), (30, 34, 0), 38.0, 2.5, (0.95, 0.92, 0.88))
    mk_area("RimCrimson", (0.0, 2.4, 2.1), (-50, 0, 0), 85.0, 3.2, (p_lin[0], 0.004, 0.012))
    mk_area("EdgeSpecKick", (0.0, -2.8, 2.4), (46, 0, 0), 32.0, 2.0, (0.94, 0.96, 1.0))


def link_mesh_object(sc, name, bm, mats, smooth=False, bevel_width=0.0, bevel_segs=2, subsurf=0):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for poly in me.polygons:
        poly.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    if bevel_width > 0:
        bev = ob.modifiers.new("Bevel", "BEVEL")
        bev.width = bevel_width
        bev.segments = bevel_segs
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(28.0)
    if subsurf > 0:
        sub = ob.modifiers.new("Subsurf", "SUBSURF")
        sub.levels = subsurf
        sub.render_levels = subsurf
    return ob


def add_beveled_plate(bm, pts_2d, z_bot, z_top, inset=0.018, mat_top=0, mat_bevel=1, mat_slit=None):
    """Append a 3D CNC-chamfered polygonal armor plate into bmesh."""
    cx = sum(p[0] for p in pts_2d) / len(pts_2d)
    cy = sum(p[1] for p in pts_2d) / len(pts_2d)
    outer_v = [bm.verts.new((p[0], p[1], z_bot)) for p in pts_2d]
    mid_v = [bm.verts.new((p[0], p[1], z_top - inset * 0.7)) for p in pts_2d]
    inner_v = []
    for x, y in pts_2d:
        dx, dy = x - cx, y - cy
        d = max(1e-5, math.hypot(dx, dy))
        k = max(0.25, (d - inset) / d)
        inner_v.append(bm.verts.new((cx + dx * k, cy + dy * k, z_top)))

    bm.faces.new(inner_v).material_index = mat_top
    bm.faces.new(reversed(outer_v)).material_index = mat_top
    n = len(pts_2d)
    for i in range(n):
        inext = (i + 1) % n
        f_chamfer = bm.faces.new((mid_v[i], mid_v[inext], inner_v[inext], inner_v[i]))
        f_chamfer.material_index = mat_bevel
        f_side = bm.faces.new((outer_v[i], outer_v[inext], mid_v[inext], mid_v[i]))
        f_side.material_index = mat_slit if (mat_slit is not None and i == 0) else mat_top


def create_corner_bezel_cluster(sc, mats, sx, sy, is_kill=False):
    """Build stepped 3D Forged-Carbon mechanical gill plates & tactical border rails like carbon.png."""
    bm = bmesh.new()
    mat_list = [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]]

    # 5 stepped overlapping forged-carbon chevron gill plates locking into corner (sx * 1.78, sy * 1.00)
    n_gills = 5 if is_kill else 4
    for g in range(n_gills):
        # Step inward from extreme corner along both X and Y borders
        ox = 1.79 - g * 0.105
        oy = 1.01 - g * 0.068
        span_x = 0.44 - g * 0.035
        span_y = 0.34 - g * 0.025
        thick_band = 0.072
        pts = [
            (sx * ox, sy * (oy - span_y)),
            (sx * (ox - thick_band), sy * (oy - span_y + 0.03)),
            (sx * (ox - thick_band * 1.25), sy * (oy - thick_band * 1.15)),
            (sx * (ox - span_x + 0.03), sy * (oy - thick_band)),
            (sx * (ox - span_x), sy * oy),
            (sx * ox, sy * oy),
        ]
        if sx * sy < 0:
            pts = list(reversed(pts))
        z0 = g * 0.028
        z1 = z0 + 0.034
        # Alternate subtle steel and antique-gold chamfers; innermost gill gets a razor crimson slit!
        bev_m = 2 if (g == 1) else 1
        slit_m = 4 if (g in (2, n_gills - 1)) else None
        add_beveled_plate(bm, pts, z0, z1, inset=0.013, mat_top=0, mat_bevel=bev_m, mat_slit=slit_m)

    # Diagonal tactical carbon armor cheek plate bridging horizontal & vertical border
    cheek = [
        (sx * 1.79, sy * 0.50),
        (sx * 1.66, sy * 0.58),
        (sx * 1.24, sy * 0.90),
        (sx * 1.14, sy * 1.01),
        (sx * 1.79, sy * 1.01),
    ]
    if sx * sy < 0:
        cheek = list(reversed(cheek))
    add_beveled_plate(bm, cheek, -0.02, 0.018, inset=0.016, mat_top=0, mat_bevel=1, mat_slit=4)

    # Horizontal outer rail segment extending toward top/bottom center
    h_rail = [
        (sx * 1.18, sy * 1.015),
        (sx * 0.34, sy * 1.015),
        (sx * 0.40, sy * 0.958),
        (sx * 1.12, sy * 0.942),
    ]
    if sx * sy < 0:
        h_rail = list(reversed(h_rail))
    add_beveled_plate(bm, h_rail, -0.01, 0.022, inset=0.010, mat_top=0, mat_bevel=1, mat_slit=4 if is_kill else None)

    # Vertical outer rail segment extending toward left/right mid-height
    v_rail = [
        (sx * 1.795, sy * 0.54),
        (sx * 1.715, sy * 0.46),
        (sx * 1.732, sy * 0.08),
        (sx * 1.795, sy * 0.02),
    ]
    if sx * sy < 0:
        v_rail = list(reversed(v_rail))
    add_beveled_plate(bm, v_rail, -0.01, 0.022, inset=0.010, mat_top=0, mat_bevel=1, mat_slit=None)

    return link_mesh_object(sc, f"CornerBezel_{sx}_{sy}", bm, mat_list, smooth=False, bevel_width=0.004, bevel_segs=2)


def create_top_bottom_center_vents(sc, mats, is_kill=False):
    """Build sleek top/bottom center Forged-Carbon precision chevron vents (like carbon.png top/bottom)."""
    bm = bmesh.new()
    mat_list = [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]]
    for sy in (-1.0, 1.0):
        # Center V-shield plate
        c_plate = [
            (-0.34, sy * 1.012),
            (0.34, sy * 1.012),
            (0.26, sy * 0.952),
            (0.0, sy * 0.934),
            (-0.26, sy * 0.952),
        ]
        if sy > 0:
            c_plate = list(reversed(c_plate))
        add_beveled_plate(bm, c_plate, 0.01, 0.040, inset=0.010, mat_top=0, mat_bevel=2, mat_slit=4)

        # 6 precision louvered carbon/crimson micro-vents flanking center
        for side in (-1.0, 1.0):
            for v_i in range(5):
                vx0 = side * (0.06 + v_i * 0.042)
                vx1 = vx0 + side * 0.024
                vent = [
                    (vx0, sy * 0.992),
                    (vx1, sy * 0.992),
                    (vx1 + side * 0.012, sy * 0.962),
                    (vx0 + side * 0.012, sy * 0.962),
                ]
                if side * sy > 0:
                    vent = list(reversed(vent))
                m_top = 4 if (is_kill and v_i % 2 == 0) else (2 if v_i == 0 else 1)
                add_beveled_plate(bm, vent, 0.038, 0.052, inset=0.003, mat_top=m_top, mat_bevel=1)

    return link_mesh_object(sc, "CenterVents", bm, mat_list, smooth=False, bevel_width=0.002, bevel_segs=1)


def create_katana_blade(sc, mats, name="Katana", length=1.35, width=0.105, curve=0.12, thickness=0.036, with_guard=True):
    """Sculpt a high-detail 3D Forged-Carbon + Cold Gunmetal Steel + Blood-Crimson Fuller Katana."""
    bm = bmesh.new()
    stations = 64
    rings = []
    for i in range(stations):
        t = i / float(stations - 1)
        x = (t - 0.22) * length
        bend_y = curve * (t * t)
        if t > 0.82:
            tip_f = max(0.015, math.sin((1.0 - t) / 0.18 * (math.pi * 0.5)) ** 0.9)
        else:
            tip_f = 1.0 - 0.12 * t
        w = width * tip_f
        th = thickness * (0.42 + 0.58 * tip_f)
        pts = [
            (x, bend_y - w * 0.46, 0.0),                         # 0: mune spine
            (x, bend_y - w * 0.24, th * 0.50),                   # 1: forged-carbon shinogi-ji +Z
            (x, bend_y - w * 0.16, th * 0.16),                   # 2: thin recessed blood-crimson bo-hi fuller +Z
            (x, bend_y - w * 0.06, th * 0.46),                   # 3: shinogi ridge +Z
            (x, bend_y + w * 0.42, th * 0.18),                   # 4: cold steel yakiba bevel +Z
            (x, bend_y + w * 0.54, 0.0),                         # 5: razor cutting edge
            (x, bend_y + w * 0.42, -th * 0.18),                  # 6: cold steel yakiba bevel -Z
            (x, bend_y - w * 0.06, -th * 0.46),                  # 7: shinogi ridge -Z
            (x, bend_y - w * 0.16, -th * 0.16),                  # 8: recessed blood-crimson fuller -Z
            (x, bend_y - w * 0.24, -th * 0.50),                  # 9: forged-carbon shinogi-ji -Z
        ]
        rings.append([bm.verts.new(p) for p in pts])

    # Materials: [0: carbon, 1: steel, 2: gold, 3: ruby, 4: plasma]
    for i in range(stations - 1):
        t = i / float(stations - 1)
        r0, r1 = rings[i], rings[i + 1]
        for k in range(10):
            kn = (k + 1) % 10
            f = bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            if k in (1, 8) and 0.06 <= t <= 0.80:
                f.material_index = 4  # Thin crimson bo-hi fuller line
            elif k in (3, 6):
                f.material_index = 1  # Cold gunmetal titanium blade bevel
            elif k in (4, 5):
                f.material_index = 4 if t > 0.12 else 1  # Thin crimson razor edge gleam
            else:
                f.material_index = 0  # Forged-carbon spine & flat
    bm.faces.new(reversed(rings[0])).material_index = 0
    bm.faces.new(rings[-1]).material_index = 4

    if with_guard:
        # Antique Gold Habaki collar
        hx0, hx1 = -0.22 * length, -0.15 * length
        hw, hth = width * 0.54, thickness * 0.72
        hab0 = [bm.verts.new((hx0, -hw, -hth)), bm.verts.new((hx0, hw, -hth)), bm.verts.new((hx0, hw, hth)), bm.verts.new((hx0, -hw, hth))]
        hab1 = [
            bm.verts.new((hx1, -hw * 0.90, -hth * 0.88)),
            bm.verts.new((hx1, hw * 0.90, -hth * 0.88)),
            bm.verts.new((hx1, hw * 0.90, hth * 0.88)),
            bm.verts.new((hx1, -hw * 0.90, hth * 0.88)),
        ]
        for k in range(4):
            kn = (k + 1) % 4
            bm.faces.new((hab0[k], hab0[kn], hab1[kn], hab1[k])).material_index = 2
        bm.faces.new(reversed(hab0)).material_index = 2
        bm.faces.new(hab1).material_index = 2

        # Forged-Carbon + Gold Fanged Tsuba Guard
        tx0, tx1 = -0.252 * length, -0.222 * length
        segs = 16
        ts0, ts1 = [], []
        for s in range(segs):
            ang = (2.0 * math.pi * s) / segs
            spike = 1.42 if (s % 4 == 0) else (1.08 if s % 2 == 0 else 0.88)
            ry = width * 1.42 * spike * math.cos(ang)
            rz = width * 1.18 * spike * math.sin(ang)
            ts0.append(bm.verts.new((tx0, ry, rz)))
            ts1.append(bm.verts.new((tx1, ry, rz)))
        for s in range(segs):
            sn = (s + 1) % segs
            bm.faces.new((ts0[s], ts0[sn], ts1[sn], ts1[s])).material_index = 2 if (s % 4 == 0) else 1
        bm.faces.new(reversed(ts0)).material_index = 0
        bm.faces.new(ts1).material_index = 0

        # Wrapped Forged-Carbon Tsuka Handle with Ruby/Gold Menuki
        kx0, kx1 = -0.50 * length, -0.252 * length
        k_steps = 12
        k_rings = []
        for ks in range(k_steps + 1):
            kt = ks / float(k_steps)
            kx = kx0 + (kx1 - kx0) * kt
            bulge = 1.07 if (ks % 2 == 1) else 0.94
            kr = []
            for s in range(12):
                ang = (2.0 * math.pi * s) / 12.0
                kr.append(bm.verts.new((kx, width * 0.40 * bulge * math.cos(ang), thickness * 0.56 * bulge * math.sin(ang))))
            k_rings.append(kr)
        for ks in range(k_steps):
            for s in range(12):
                sn = (s + 1) % 12
                m_i = 2 if (ks in (0, k_steps - 1)) else (3 if (ks % 3 == 1 and s in (2, 8)) else 0)
                bm.faces.new((k_rings[ks][s], k_rings[ks][sn], k_rings[ks + 1][sn], k_rings[ks + 1][s])).material_index = m_i
        bm.faces.new(reversed(k_rings[0])).material_index = 2

    return link_mesh_object(
        sc,
        name,
        bm,
        [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]],
        smooth=False,
        bevel_width=0.0025,
        bevel_segs=1,
    )


def create_oni_horn(sc, mats, name="OniHorn", length=0.88, base_r=0.105, bend=0.40, twist=0.65):
    """Sculpt a high-resolution fluted Forged-Carbon & Gunmetal Oni Horn with subtle crimson groove & gold bands."""
    bm = bmesh.new()
    stations = 52
    radial = 20
    rings = []
    for i in range(stations):
        t = i / float(stations - 1)
        ang_b = bend * (t ** 1.32) * math.pi
        cx = length * t * math.cos(ang_b * 0.45)
        cy = length * t * math.sin(ang_b * 0.65)
        cz = 0.06 * math.sin(t * math.pi)
        taper = max(0.008, (1.0 - t) ** 0.84)
        ridge = 1.0 + 0.09 * max(0.0, math.cos(t * math.pi * 14.0)) * (1.0 - t * 0.65)
        r_cur = base_r * taper * ridge
        ring_v = []
        for s in range(radial):
            a = (2.0 * math.pi * s) / radial + twist * t
            flute = 0.80 if s in (4, 14) else (1.10 if s % 4 == 0 else 0.96)
            ring_v.append(bm.verts.new((cx, cy + r_cur * flute * math.cos(a), cz + r_cur * flute * math.sin(a))))
        rings.append((t, ring_v))

    for i in range(stations - 1):
        t, r0 = rings[i]
        _, r1 = rings[i + 1]
        is_gold_collar = i in (3, 4, 15, 16)
        for s in range(radial):
            sn = (s + 1) % radial
            f = bm.faces.new((r0[s], r0[sn], r1[sn], r1[s]))
            if s in (4, 14) and 0.14 < t < 0.84:
                f.material_index = 4  # Thin recessed blood-crimson vein
            elif is_gold_collar:
                f.material_index = 2  # Antique gold collar ring
            elif s % 4 == 0:
                f.material_index = 1  # Gunmetal specular ridge
            elif t > 0.88:
                f.material_index = 3  # Blood-ruby tip
            else:
                f.material_index = 0  # Forged-carbon body
    bm.faces.new(reversed(rings[0][1])).material_index = 0
    bm.faces.new(rings[-1][1]).material_index = 3
    return link_mesh_object(
        sc,
        name,
        bm,
        [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]],
        smooth=True,
    )


def create_slash_crescent(sc, mats, name="SlashArc", radius=0.66, sweep_deg=155.0, width=0.22, thickness=0.030):
    """Sculpt a ultra-smooth 96-station 3D aerodynamic Forged-Carbon + Cold Steel + Crimson Katana Slash."""
    bm = bmesh.new()
    stations = 96
    sweep = math.radians(sweep_deg)
    a0 = -sweep * 0.5
    rings = []
    for i in range(stations):
        t = i / float(stations - 1)
        ang = a0 + sweep * t
        env = math.sin(math.pi * (t ** 0.84)) ** 1.25
        wake_mod = 1.0 + 0.14 * math.sin(t * math.pi * 11.0) * math.sin(t * math.pi)
        w = max(0.002, width * env * wake_mod)
        th = max(0.0015, thickness * env)
        ca, sa = math.cos(ang), math.sin(ang)
        radii_z = [
            (radius + w * 0.18, 0.0),           # 0: razor blood-crimson leading lip
            (radius + w * 0.09, th * 0.48),     # 1: cold gunmetal steel flash +Z
            (radius - w * 0.28, th * 0.34),     # 2: pitch-black forged-carbon body +Z
            (radius - w * 0.82, 0.0),           # 3: sharp trailing carbon wake edge
            (radius - w * 0.28, -th * 0.34),    # 4: pitch-black forged-carbon body -Z
            (radius + w * 0.09, -th * 0.48),    # 5: cold gunmetal steel flash -Z
        ]
        rings.append([bm.verts.new((rr * ca, rr * sa, zz)) for (rr, zz) in radii_z])

    for i in range(stations - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(6):
            kn = (k + 1) % 6
            f = bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            if k in (0, 5):
                f.material_index = 4  # Thin pure blood-crimson razor edge
            elif k in (1, 4):
                f.material_index = 1  # Cold gunmetal steel gleam (ZERO yellow/orange stripes!)
            else:
                f.material_index = 0  # Deep forged-carbon aerodynamic wake
    bm.faces.new(reversed(rings[0])).material_index = 4
    bm.faces.new(rings[-1]).material_index = 4
    return link_mesh_object(
        sc,
        name,
        bm,
        [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]],
        smooth=True,
    )


def create_carbon_shard(sc, mats, name="Shard", seed=1, radius=0.22, thickness=0.044, is_ruby_crystal=False):
    """Sculpt a sharp angular 3D Forged-Carbon armor shard or Faceted Blood-Ruby crystal."""
    rng = random.Random(seed)
    bm = bmesh.new()
    n_pts = rng.randint(5, 8)
    elong = rng.uniform(1.6, 2.5)
    top_v, bot_v, mid_v = [], [], []
    for i in range(n_pts):
        a = (2.0 * math.pi * i) / n_pts + rng.uniform(-0.18, 0.18)
        r = radius * (1.28 if i in (0, n_pts // 2) else rng.uniform(0.48, 0.92))
        px = r * elong * math.cos(a)
        py = r * math.sin(a)
        inset = 0.72 if is_ruby_crystal else 0.84
        z_pk = thickness * (0.72 if is_ruby_crystal else 0.48)
        top_v.append(bm.verts.new((px * inset, py * inset, z_pk)))
        bot_v.append(bm.verts.new((px * inset, py * inset, -z_pk)))
        mid_v.append(bm.verts.new((px, py, 0.0)))

    main_mat = 3 if is_ruby_crystal else 0
    bm.faces.new(top_v).material_index = main_mat
    bm.faces.new(reversed(bot_v)).material_index = main_mat
    for i in range(n_pts):
        inext = (i + 1) % n_pts
        f1 = bm.faces.new((top_v[i], mid_v[i], mid_v[inext], top_v[inext]))
        f2 = bm.faces.new((mid_v[i], bot_v[i], bot_v[inext], mid_v[inext]))
        if is_ruby_crystal:
            edge_mat = 4 if (i == 0) else 3
        else:
            edge_mat = 4 if (i == 0) else (2 if (i == 2) else 1)
        f1.material_index = edge_mat
        f2.material_index = edge_mat

    return link_mesh_object(
        sc,
        name,
        bm,
        [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]],
        smooth=False,
        bevel_width=0.004,
        bevel_segs=2,
    )


def render_to_float_rgba(sc, tmp_png_path):
    sc.render.filepath = tmp_png_path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp_png_path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    rgba = buf.reshape((h, w, 4))[::-1, :, :].copy()
    rgb = np.clip(rgba[..., :3], 0.0, None)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * (np.maximum(rgb, 1e-8) ** (1.0 / 2.4)) - 0.055)
    out = np.empty_like(rgba)
    out[..., :3] = np.clip(srgb, 0.0, 1.0)
    out[..., 3] = np.clip(rgba[..., 3], 0.0, 1.0)
    return out


def add_selective_bloom(rgba, primary_srgb, strength=0.45):
    """Add tight blood-crimson glow around emissive slits/edges without washing out dark forged carbon."""
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]
    prem = rgb * alpha
    red_dom = np.clip(prem[..., 0] - 0.85 * (prem[..., 1] + prem[..., 2]), 0.0, 1.0)
    spec_hi = np.clip((0.2126 * prem[..., 0] + 0.7152 * prem[..., 1] + 0.0722 * prem[..., 2] - 0.72) * 1.6, 0.0, 1.0)
    hot_mask = np.clip(red_dom * 2.1 + spec_hi * 0.45, 0.0, 1.0)[..., None]
    hot_src = prem * hot_mask

    h = rgba.shape[0]
    b1 = gaussian_approx(hot_src, max(2, h // 160))
    b2 = gaussian_approx(hot_src, max(5, h // 52))
    p_col = np.array([primary_srgb[0], 0.02, 0.04], dtype=np.float32).reshape((1, 1, 3))
    bloom_tinted = (b1 * 0.65 + b2 * 0.45) * strength * (0.35 + 0.65 * p_col)
    bloom_a = np.clip(np.max(bloom_tinted, axis=-1, keepdims=True) * 1.15, 0.0, 0.82)

    new_a = np.clip(alpha + bloom_a * (1.0 - alpha), 0.0, 1.0)
    new_prem = np.clip(prem + bloom_tinted, 0.0, 1.0)
    safe_a = np.maximum(new_a, 1e-5)
    out = np.empty_like(rgba)
    out[..., :3] = np.where(new_a > 1e-4, np.clip(new_prem / safe_a, 0.0, 1.0), 0.0)
    out[..., 3:4] = new_a
    return out


def setup_ortho_camera(sc, ortho_scale=3.5556, z_dist=4.5):
    cam_data = bpy.data.cameras.new("OrthoCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_ob = bpy.data.objects.new("OrthoCam", cam_data)
    cam_ob.location = (0.0, 0.0, z_dist)
    cam_ob.rotation_euler = (0.0, 0.0, 0.0)
    sc.collection.objects.link(cam_ob)
    sc.camera = cam_ob
    return cam_ob


def render_screen_overlay(mode, out_path, tmp_dir, primary_hex, secondary_hex, dark_hex, samples=44):
    """Sculpt & raytrace a 1920x1080 3D Forged-Carbon Oni perimeter frame (matching carbon.png + royalblood.png)."""
    is_kill = mode == "kill"
    sc = reset_scene(samples=samples, res_x=1920, res_y=1080)
    mats = build_materials(primary_hex, secondary_hex, dark_hex)
    add_studio_lights(sc, primary_hex)
    setup_ortho_camera(sc, ortho_scale=3.5556, z_dist=5.0)

    rng = random.Random(909 if is_kill else 404)

    # 1. Full 360-degree 3D Stepped Forged-Carbon Corner Bezels & Tactical Top/Bottom Rails
    create_top_bottom_center_vents(sc, mats, is_kill=is_kill)
    corners = [(-1.0, 1.0), (1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)]
    for idx, (sx, sy) in enumerate(corners):
        create_corner_bezel_cluster(sc, mats, sx, sy, is_kill=is_kill)

        # Sweeping 3D aerodynamic Forged-Carbon + Crimson Razor Arc hugging each corner
        if sx < 0 and sy > 0:
            slash_ang = math.radians(-42.0)
        elif sx > 0 and sy > 0:
            slash_ang = math.radians(-138.0)
        elif sx < 0 and sy < 0:
            slash_ang = math.radians(42.0)
        else:
            slash_ang = math.radians(138.0)

        sl = create_slash_crescent(
            sc,
            mats,
            name=f"CornerArc_{idx}",
            radius=0.50 if is_kill else 0.42,
            sweep_deg=108.0 if is_kill else 92.0,
            width=0.076 if is_kill else 0.050,
            thickness=0.022,
        )
        sl.location = (sx * (1.60 if is_kill else 1.66), sy * (0.86 if is_kill else 0.90), 0.22)
        sl.rotation_euler = Euler((math.radians(16.0 * sy), math.radians(-16.0 * sx), slash_ang + math.pi), "XYZ")

        if is_kill:
            # Kill Exclusive: Sculpted Fluted 3D Forged-Carbon & Gold Oni Horn sweeping from each corner!
            horn = create_oni_horn(
                sc,
                mats,
                name=f"CornerHorn_{idx}",
                length=0.68,
                base_r=0.088,
                bend=0.36,
                twist=0.55 * sx * sy,
            )
            horn.location = (sx * 1.72, sy * 0.94, 0.28)
            if sy < 0:
                horn.scale = (1.0, -1.0, 1.0)
            hz = math.atan2(-sy * 0.26, -sx * 0.96)
            horn.rotation_euler = Euler((math.radians(20.0 * sy), math.radians(-14.0 * sx), hz), "XYZ")

        # Faceted 3D Blood-Ruby Crystals & Shattered Forged-Carbon Armor Shards along outer border
        shard_n = 11 if is_kill else 5
        for s_i in range(shard_n):
            is_ruby = (s_i % 2 == 0) if is_kill else (s_i == 0)
            sh = create_carbon_shard(
                sc,
                mats,
                name=f"BorderCrystal_{idx}_{s_i}",
                seed=idx * 47 + s_i * 13 + (200 if is_kill else 0),
                radius=rng.uniform(0.036, 0.082 if is_kill else 0.052),
                thickness=0.026,
                is_ruby_crystal=is_ruby,
            )
            if s_i % 3 == 0:
                px = sx * rng.uniform(1.48 if is_kill else 1.58, 1.76)
                py = sy * rng.uniform(0.18, 0.92)
            else:
                px = sx * rng.uniform(0.68, 1.72)
                py = sy * rng.uniform(0.80 if is_kill else 0.87, 0.98)
            sh.location = (px, py, rng.uniform(0.16, 0.36))
            sh.rotation_euler = Euler((rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9), rng.uniform(-3.14, 3.14)), "XYZ")

    tmp_png = os.path.join(tmp_dir, f"_raw_screen_{mode}.png")
    rgba = render_to_float_rgba(sc, tmp_png)
    p_srgb = hex_to_srgb_float(primary_hex)
    rgba = add_selective_bloom(rgba, p_srgb, strength=0.58 if is_kill else 0.42)

    # Composite organic billowing dark carbon-smoke border (like carbon.png!) + fine crimson embers,
    # while strictly zeroing out alpha across the central gameplay viewport!
    h, w, _ = rgba.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx + 0.5) / w * 2.0 - 1.0
    ny = (yy + 0.5) / h * 2.0 - 1.0

    rx_clear = 0.79 if is_kill else 0.84
    ry_clear = 0.77 if is_kill else 0.83
    p_exp = 3.6
    r_sup = ((np.abs(nx) / rx_clear) ** p_exp + (np.abs(ny) / ry_clear) ** p_exp) ** (1.0 / p_exp)

    keep_mask = np.clip((r_sup - 0.92) / 0.13, 0.0, 1.0)
    keep_mask = keep_mask * keep_mask * (3.0 - 2.0 * keep_mask)

    # Domain-warped FBM billowing obsidian carbon smoke along left/right/top/bottom edges
    n1 = fbm_smoke_2d(h, w, seed=101 if is_kill else 51, base_grid=(8, 14), octaves=5)
    n2 = fbm_smoke_2d(h, w, seed=202 if is_kill else 77, base_grid=(13, 22), octaves=4)
    smoke_billow = np.clip(n1 * 0.68 + n2 * 0.32, 0.0, 1.0)

    r_warped = r_sup + (smoke_billow - 0.48) * (0.18 if is_kill else 0.13)
    smoke_env = np.clip((r_warped - 0.96) / 0.28, 0.0, 1.0) ** 1.35
    smoke_a = smoke_env * (0.86 if is_kill else 0.68) * keep_mask

    # Shading inside the billowing carbon smoke: pitch-black charcoal base + subtle cool rim wisps + crimson ember glow
    wisp_hi = np.clip((smoke_billow - 0.56) * 2.2, 0.0, 1.0)
    smoke_rgb = (
        np.array([0.018, 0.018, 0.022], dtype=np.float32)[None, None, :]
        + np.array([0.095, 0.098, 0.110], dtype=np.float32)[None, None, :] * (wisp_hi[..., None] * (0.55 if not is_kill else 0.35))
    )
    if is_kill:
        crimson_mist = np.clip((n2 - 0.60) * 2.5, 0.0, 1.0) * smoke_env
        smoke_rgb += np.array([p_srgb[0] * 0.42, 0.008, 0.016], dtype=np.float32)[None, None, :] * crimson_mist[..., None]

    # Crisp fine crimson/gold micro-sparks strictly in the outer border zone
    spark_rng = np.random.RandomState(888 if is_kill else 333)
    spark_layer = np.zeros((h, w, 4), dtype=np.float32)
    n_sparks = 85 if is_kill else 36
    for _ in range(n_sparks):
        # Pick random border angle
        ang = spark_rng.uniform(0.0, 2.0 * math.pi)
        rad = spark_rng.uniform(1.03, 1.24)
        sx_p = int((0.5 + 0.5 * np.clip(rx_clear * rad * math.cos(ang), -0.99, 0.99)) * w)
        sy_p = int((0.5 + 0.5 * np.clip(ry_clear * rad * math.sin(ang), -0.99, 0.99)) * h)
        sr = spark_rng.randint(2, 5 if is_kill else 4)
        y0, y1 = max(0, sy_p - sr * 2), min(h, sy_p + sr * 2 + 1)
        x0, x1 = max(0, sx_p - sr * 2), min(w, sx_p + sr * 2 + 1)
        py_g, px_g = np.mgrid[y0:y1, x0:x1]
        dd = np.sqrt(((px_g - sx_p) / float(sr)) ** 2 + ((py_g - sy_p) / float(sr)) ** 2)
        sa = np.exp(-(dd ** 1.8) * 1.4) * spark_rng.uniform(0.55, 0.95)
        is_gold_sp = spark_rng.rand() < 0.25
        scol = np.array([0.92, 0.68, 0.26] if is_gold_sp else [1.0, 0.08, 0.10], dtype=np.float32)
        cur_a = spark_layer[y0:y1, x0:x1, 3]
        na = np.maximum(cur_a, sa)
        spark_layer[y0:y1, x0:x1, :3] = np.where(sa[..., None] > cur_a[..., None], scol, spark_layer[y0:y1, x0:x1, :3])
        spark_layer[y0:y1, x0:x1, 3] = na

    fg_rgb = rgba[..., :3]
    fg_a = rgba[..., 3] * keep_mask

    # Composite: Smoke base -> 3D Cycles Forged-Carbon Bezel/Horns/Crystals -> Fine Border Sparks
    c1_a = fg_a + smoke_a * (1.0 - fg_a)
    c1_prem = fg_rgb * fg_a[..., None] + smoke_rgb * (smoke_a * (1.0 - fg_a))[..., None]
    c1_rgb = np.where(c1_a[..., None] > 1e-5, c1_prem / np.maximum(c1_a[..., None], 1e-5), 0.0)

    sp_a = spark_layer[..., 3] * keep_mask
    comp_a = sp_a + c1_a * (1.0 - sp_a)
    comp_prem = spark_layer[..., :3] * sp_a[..., None] + c1_rgb * (c1_a * (1.0 - sp_a))[..., None]
    out_rgb = np.where(comp_a[..., None] > 1e-5, comp_prem / np.maximum(comp_a[..., None], 1e-5), 0.0)

    comp_a = np.where(r_sup <= 0.92, 0.0, np.clip(comp_a, 0.0, 1.0))
    out_rgb = np.where(comp_a[..., None] > 0.0, np.clip(out_rgb, 0.0, 1.0), 0.0)

    out_u8 = np.empty((h, w, 4), dtype=np.uint8)
    out_u8[..., :3] = np.clip(np.round(out_rgb * 255.0), 0, 255).astype(np.uint8)
    out_u8[..., 3] = np.clip(np.round(comp_a * 255.0), 0, 255).astype(np.uint8)

    nbytes = save_rgba_png(out_path, out_u8)
    center_box = out_u8[int(h * 0.25) : int(h * 0.75), int(w * 0.25) : int(w * 0.75), 3]
    print(
        f"@@FX_SCREEN mode={mode} path={out_path} size_kb={round(nbytes/1024,1)} "
        f"center50_max_alpha={int(center_box.max())} border_max_alpha={int(out_u8[...,3].max())}"
    )


def render_ptfx_assets(prefix, out_dir, tmp_dir, primary_hex, secondary_hex, dark_hex, samples=40):
    """Sculpt & raytrace all 3D Blender PTFX sprites, 2x2 sheet cells, and seamless single-line ribbon texture."""
    os.makedirs(out_dir, exist_ok=True)
    p_srgb = hex_to_srgb_float(primary_hex)

    def save_sprite(rgba_float, out_name, bloom_strength=0.48, edge_pad=0.06, bottom_fade=0.0):
        rgba_b = add_selective_bloom(rgba_float, p_srgb, strength=bloom_strength)
        h, w, _ = rgba_b.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        if edge_pad > 0:
            ux = np.abs((xx + 0.5) / w * 2.0 - 1.0)
            uy = np.abs((yy + 0.5) / h * 2.0 - 1.0)
            b = np.maximum(ux, uy)
            rgba_b[..., 3] *= np.clip((1.0 - b) / edge_pad, 0.0, 1.0)
        if bottom_fade > 0:
            # Darken & feather bottom so ground-impaling blades/spikes emerge naturally out of earth shadow
            vy = (yy + 0.5) / h  # 0 top .. 1 bottom
            bf = np.clip((1.0 - vy) / bottom_fade, 0.0, 1.0)
            bf_smooth = bf * bf * (3.0 - 2.0 * bf)
            rgba_b[..., :3] *= np.clip((1.0 - vy) / (bottom_fade * 1.4), 0.12, 1.0)[..., None]
            rgba_b[..., 3] *= bf_smooth
        u8 = np.clip(np.round(rgba_b * 255.0), 0, 255).astype(np.uint8)
        u8[u8[..., 3] == 0, :3] = 0
        p = os.path.join(out_dir, out_name)
        kb = round(save_rgba_png(p, u8) / 1024.0, 1)
        print(f"@@FX_PTFX sprite={out_name} res={w}x{h} size_kb={kb}")

    # --- 1. 3D Katana Crescent Slash (512x512): Smooth dark forged-carbon wake + gunmetal flash + blood-crimson lip ---
    sc = reset_scene(samples=samples, res_x=512, res_y=512)
    mats = build_materials(primary_hex, secondary_hex, dark_hex)
    add_studio_lights(sc, primary_hex)
    setup_ortho_camera(sc, ortho_scale=1.76, z_dist=4.0)
    sl = create_slash_crescent(sc, mats, "MainSlash", radius=0.64, sweep_deg=162.0, width=0.22, thickness=0.040)
    sl.rotation_euler = Euler((math.radians(16.0), math.radians(-12.0), math.radians(36.0)), "XYZ")
    sl2 = create_slash_crescent(sc, mats, "InnerRazor", radius=0.52, sweep_deg=126.0, width=0.065, thickness=0.018)
    sl2.location = (-0.03, 0.02, 0.07)
    sl2.rotation_euler = Euler((math.radians(-10.0), math.radians(14.0), math.radians(42.0)), "XYZ")
    save_sprite(render_to_float_rgba(sc, os.path.join(tmp_dir, "_ptfx_slash.png")), f"{prefix}_3d_slash.png", bloom_strength=0.58)

    # --- 2. 3D Forged-Carbon Tactical Demon Ground Seal (512x512): 64-seg precision carbon bezel + 8 katana fangs ---
    sc = reset_scene(samples=samples, res_x=512, res_y=512)
    mats = build_materials(primary_hex, secondary_hex, dark_hex)
    add_studio_lights(sc, primary_hex)
    setup_ortho_camera(sc, ortho_scale=2.04, z_dist=4.5)

    bm = bmesh.new()
    for r_in, r_out, z_h, segs, mat_i in [
        (0.70, 0.85, 0.048, 64, 0),
        (0.675, 0.70, 0.056, 64, 1),
        (0.848, 0.862, 0.032, 64, 4),
        (0.45, 0.53, 0.042, 48, 0),
        (0.528, 0.540, 0.030, 48, 4),
        (0.435, 0.450, 0.048, 48, 2),
    ]:
        ra, rb, rc, rd = [], [], [], []
        for s in range(segs):
            a = (2.0 * math.pi * s) / segs
            ca, sa = math.cos(a), math.sin(a)
            ra.append(bm.verts.new((r_in * ca, r_in * sa, 0.0)))
            rb.append(bm.verts.new((r_out * ca, r_out * sa, 0.0)))
            rc.append(bm.verts.new(((r_out - 0.008) * ca, (r_out - 0.008) * sa, z_h)))
            rd.append(bm.verts.new(((r_in + 0.008) * ca, (r_in + 0.008) * sa, z_h)))
        for s in range(segs):
            sn = (s + 1) % segs
            for quad in [
                (rd[s], rc[s], rc[sn], rd[sn]),
                (rb[s], rb[sn], rc[sn], rc[s]),
                (ra[sn], ra[s], rd[s], rd[sn]),
            ]:
                bm.faces.new(quad).material_index = mat_i

    # 8 thin razor-sharp crimson sigil spokes + 8 stepped forged-carbon armor lugs (no fat orange bars!)
    for k in range(8):
        ang = (2.0 * math.pi * k) / 8.0
        ca, sa = math.cos(ang), math.sin(ang)
        nx, ny = -sa * 0.007, ca * 0.007
        v0 = bm.verts.new((0.45 * ca - nx, 0.45 * sa - ny, 0.034))
        v1 = bm.verts.new((0.45 * ca + nx, 0.45 * sa + ny, 0.034))
        v2 = bm.verts.new((0.85 * ca + nx, 0.85 * sa + ny, 0.034))
        v3 = bm.verts.new((0.85 * ca - nx, 0.85 * sa - ny, 0.034))
        bm.faces.new((v0, v1, v2, v3)).material_index = 4

        # Stepped carbon-steel lug bridging inner and outer ring
        ang2 = ang + math.pi / 8.0
        c2, s2 = math.cos(ang2), math.sin(ang2)
        px, py = -s2 * 0.048, c2 * 0.048
        lug = [
            (0.52 * c2 - px, 0.52 * s2 - py),
            (0.52 * c2 + px, 0.52 * s2 + py),
            (0.73 * c2 + px * 0.65, 0.73 * s2 + py * 0.65),
            (0.73 * c2 - px * 0.65, 0.73 * s2 - py * 0.65),
        ]
        add_beveled_plate(bm, lug, 0.01, 0.062, inset=0.010, mat_top=0, mat_bevel=1, mat_slit=4)

    link_mesh_object(sc, "GroundSealRings", bm, [mats["carbon"], mats["steel"], mats["gold"], mats["ruby"], mats["plasma"]], smooth=False)

    for k in range(8):
        ang = (2.0 * math.pi * k) / 8.0
        fang = create_oni_horn(sc, mats, f"SealFang_{k}", length=0.34, base_r=0.048, bend=0.20, twist=0.25)
        fang.location = (0.83 * math.cos(ang), 0.83 * math.sin(ang), 0.055)
        fang.rotation_euler = Euler((math.radians(10.0), 0.0, ang + math.radians(155.0)), "XYZ")

    seal_rgba = render_to_float_rgba(sc, os.path.join(tmp_dir, "_ptfx_seal.png"))
    # Organic smoky ring shadow ONLY underneath the ring annulus (hollow center so no flat gray sticker!)
    sh_h, sh_w, _ = seal_rgba.shape
    yy, xx = np.mgrid[0:sh_h, 0:sh_w].astype(np.float32)
    rr = np.sqrt(((xx + 0.5) / sh_w * 2.0 - 1.0) ** 2 + ((yy + 0.5) / sh_h * 2.0 - 1.0) ** 2)
    ring_shadow = np.exp(-(((rr - 0.66) / 0.24) ** 2.0)) * 0.58 * np.clip((0.95 - rr) / 0.14, 0.0, 1.0)
    fg_a = seal_rgba[..., 3]
    comb_a = fg_a + ring_shadow * (1.0 - fg_a)
    scorch_rgb = np.array([0.016, 0.014, 0.018], dtype=np.float32).reshape((1, 1, 3))
    comb_prem = seal_rgba[..., :3] * fg_a[..., None] + scorch_rgb * (ring_shadow * (1.0 - fg_a))[..., None]
    seal_rgba[..., :3] = np.where(comb_a[..., None] > 1e-5, comb_prem / np.maximum(comb_a[..., None], 1e-5), 0.0)
    seal_rgba[..., 3] = comb_a
    save_sprite(seal_rgba, f"{prefix}_3d_seal.png", bloom_strength=0.52)

    # --- 3. 3D Crossed Forged-Carbon Katanas & Oni Horns Finisher Crest (512x512) ---
    sc = reset_scene(samples=samples, res_x=512, res_y=512)
    mats = build_materials(primary_hex, secondary_hex, dark_hex)
    add_studio_lights(sc, primary_hex)
    setup_ortho_camera(sc, ortho_scale=1.92, z_dist=4.5)

    for sign, z_off in [(-1.0, -0.04), (1.0, 0.04)]:
        kb = create_katana_blade(sc, mats, f"CrossKat_{sign}", length=1.34, width=0.098, curve=0.09 * sign, thickness=0.036, with_guard=True)
        kb.location = (-0.08 * sign, -0.06, z_off)
        kb.rotation_euler = Euler((math.radians(22.0), math.radians(-16.0 * sign), math.radians(48.0 * sign)), "XYZ")
    for sign in (-1.0, 1.0):
        hn = create_oni_horn(sc, mats, f"CrestHorn_{sign}", length=0.56, base_r=0.082, bend=0.40, twist=0.45 * sign)
        hn.location = (0.11 * sign, -0.05, 0.14)
        if sign < 0:
            hn.scale = (-1.0, 1.0, 1.0)
        hn.rotation_euler = Euler((math.radians(18.0), 0.0, math.radians(52.0 * sign)), "XYZ")
    ring_sl = create_slash_crescent(sc, mats, "CrestSlash", radius=0.62, sweep_deg=215.0, width=0.072, thickness=0.020)
    ring_sl.location = (0.0, 0.02, -0.10)
    ring_sl.rotation_euler = Euler((math.radians(24.0), 0.0, math.radians(90.0)), "XYZ")
    save_sprite(render_to_float_rgba(sc, os.path.join(tmp_dir, "_ptfx_cross.png")), f"{prefix}_3d_katana_cross.png", bloom_strength=0.52)

    # --- 4. 4x 3D Ground-Impaling Katanas & Erupting Carbon-Ruby Spikes (256x256 each for 2x2 sheet) ---
    for i in range(4):
        sc = reset_scene(samples=max(28, samples - 8), res_x=256, res_y=256)
        mats = build_materials(primary_hex, secondary_hex, dark_hex)
        add_studio_lights(sc, primary_hex)
        setup_ortho_camera(sc, ortho_scale=1.54, z_dist=4.0)
        if i % 2 == 0:
            # Execution Katana plunged DOWNWARD into the ground (handle/tsuba up, tip buried in dark earth shadow!)
            b_ob = create_katana_blade(
                sc,
                mats,
                f"ImpaleKat_{i}",
                length=1.24,
                width=0.105,
                curve=0.08 * (1 if i == 0 else -1),
                thickness=0.040,
                with_guard=True,
            )
            b_ob.location = (0.0, 0.06, 0.0)
            b_ob.rotation_euler = Euler(
                (math.radians(20.0), math.radians(16.0 * (1 if i == 0 else -1)), math.radians(-90.0 + (7 if i == 0 else -7))),
                "XYZ",
            )
        else:
            # Jagged Forged-Carbon & Blood-Ruby Spike erupting UPWARD out of shadow base!
            h_ob = create_oni_horn(
                sc,
                mats,
                f"EruptSpike_{i}",
                length=1.18,
                base_r=0.145,
                bend=0.16 * (1 if i == 1 else -1),
                twist=0.6,
            )
            h_ob.location = (0.0, -0.54, 0.0)
            h_ob.rotation_euler = Euler((math.radians(16.0), math.radians(-14.0), math.radians(84.0)), "XYZ")
        save_sprite(
            render_to_float_rgba(sc, os.path.join(tmp_dir, f"_ptfx_blade_{i}.png")),
            f"{prefix}_3d_blade_{i}.png",
            bloom_strength=0.46,
            bottom_fade=0.20,
        )

    # --- 5. 4x 3D Shattered Forged-Carbon & Faceted Blood-Ruby Shards (256x256 each for 2x2 sheet) ---
    for i in range(4):
        sc = reset_scene(samples=max(28, samples - 8), res_x=256, res_y=256)
        mats = build_materials(primary_hex, secondary_hex, dark_hex)
        add_studio_lights(sc, primary_hex)
        setup_ortho_camera(sc, ortho_scale=1.32, z_dist=3.5)
        sh = create_carbon_shard(
            sc,
            mats,
            f"CellShard_{i}",
            seed=950 + i * 23,
            radius=0.22,
            thickness=0.052,
            is_ruby_crystal=(i == 3),
        )
        sh.rotation_euler = Euler((0.45 + i * 0.38, -0.35 + i * 0.30, i * 0.82), "XYZ")
        save_sprite(render_to_float_rgba(sc, os.path.join(tmp_dir, f"_ptfx_shard_{i}.png")), f"{prefix}_3d_shard_{i}.png", bloom_strength=0.42)

    # --- 6. Sleek Single-Line Aerodynamic Ribbon Texture (512x128: X=along length, Y=across width) ---
    rw, rh = 512, 128
    yy, xx = np.mgrid[0:rh, 0:rw].astype(np.float32)
    u01 = (xx + 0.5) / rw
    v_signed = (yy + 0.5) / rh * 2.0 - 1.0
    ang_u = u01 * 2.0 * math.pi

    # Ultra-clean aerodynamic flow (almost zero vertical wobble so the single ribbon line glides smoothly!)
    sway = 0.008 * np.sin(ang_u * 2.0)
    ad = np.abs(v_signed - sway)

    # Subtle carbon-silk sheen along U
    silk = 0.92 + 0.08 * np.sin(ang_u * 6.0 + v_signed * 4.0)

    # Cross-section:
    #   - Smooth dark forged-obsidian aura sheath (contrasts cleanly on bright noon concrete)
    #   - Rich pure blood-crimson silk body (G=0, B~0 so zero pink washout!)
    #   - Pinpoint razor center filament
    sheath = np.exp(-((ad / 0.38) ** 2.1)) * np.clip((0.84 - ad) / 0.22, 0.0, 1.0)
    crimson_core = np.exp(-((ad / 0.145) ** 2.0)) * silk
    hot_filament = np.exp(-((ad / 0.042) ** 2.0))

    rib_a = np.clip(sheath * 0.72 + crimson_core * 0.94 + hot_filament, 0.0, 1.0)
    rib_a *= np.clip((0.92 - np.abs(v_signed)) / 0.18, 0.0, 1.0) ** 1.6

    dark_sheath_rgb = np.array([0.018, 0.014, 0.018], dtype=np.float32)
    crimson_rgb = np.array([p_srgb[0], 0.008, 0.018], dtype=np.float32)
    filament_rgb = np.array([1.0, 0.14, 0.12], dtype=np.float32)

    w_c = np.clip(crimson_core * 1.18, 0.0, 1.0)[..., None]
    w_f = np.clip(hot_filament * 0.78, 0.0, 1.0)[..., None]
    rib_rgb = dark_sheath_rgb * (1.0 - w_c) + crimson_rgb * w_c
    rib_rgb = rib_rgb * (1.0 - w_f) + filament_rgb * w_f

    rib_u8 = np.zeros((rh, rw, 4), dtype=np.uint8)
    rib_u8[..., :3] = np.clip(np.round(rib_rgb * 255.0), 0, 255).astype(np.uint8)
    rib_u8[..., 3] = np.clip(np.round(rib_a * 255.0), 0, 255).astype(np.uint8)
    rib_u8[rib_u8[..., 3] == 0, :3] = 0
    rib_path = os.path.join(out_dir, f"{prefix}_ribbon_tex.png")
    r_kb = round(save_rgba_png(rib_path, rib_u8) / 1024.0, 1)
    print(f"@@FX_PTFX sprite={prefix}_ribbon_tex.png res={rw}x{rh} size_kb={r_kb}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True, help="Asset prefix / skin id in lowercase (e.g., onikage)")
    ap.add_argument("--out-screen", default="", help="Output folder for <prefix>.png and <prefix>_kill.png")
    ap.add_argument("--out-ptfx", default="", help="Output folder for 3D PTFX sprite PNGs")
    ap.add_argument("--primary", default="#dc0008", help="Primary HDR emission hex color")
    ap.add_argument("--secondary", default="#c4913a", help="Secondary metallic trim hex color")
    ap.add_argument("--dark", default="#07070a", help="Dark forged-carbon base hex color")
    ap.add_argument("--samples", type=int, default=44, help="Cycles raytracing samples")
    args = ap.parse_args(argv)

    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="wf_fx3d_")
    if args.out_screen:
        os.makedirs(args.out_screen, exist_ok=True)
        render_screen_overlay(
            "hit",
            os.path.join(args.out_screen, f"{args.prefix}.png"),
            tmp_dir,
            args.primary,
            args.secondary,
            args.dark,
            samples=args.samples,
        )
        render_screen_overlay(
            "kill",
            os.path.join(args.out_screen, f"{args.prefix}_kill.png"),
            tmp_dir,
            args.primary,
            args.secondary,
            args.dark,
            samples=args.samples,
        )
    if args.out_ptfx:
        render_ptfx_assets(
            args.prefix,
            args.out_ptfx,
            tmp_dir,
            args.primary,
            args.secondary,
            args.dark,
            samples=args.samples,
        )


if __name__ == "__main__":
    main()
