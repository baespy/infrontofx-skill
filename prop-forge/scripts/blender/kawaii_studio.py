"""prop-forge V11: Kawaii Plush Artisan Studio toolkit for BILLIE SCHOOL FiveM props.

Provides smooth Subdivision-Surface, Lathe, Swept-Tube, Scalloped Cafe Awning,
Plush Cloud, Pillowy 5-Point Star, Sculpted/Illustrated 3D Billie Bear Mascot,
Crisp Billie-UI Decal/Banner Generator, Cycles Soft Plush AO Baker, Smooth Rest-Exact
YCD Bone Rigging, and Studio Beauty Preview Rendering.

100% compatible with:
  - validate_prop.py (guarantees fail=0 warn=0: <=4 materials, pow2 <=512 textures,
    origin at floor z=0 centered X/Y, clean UVMap, zero NaN/degenerate/loose/orphans)
  - export_prop.py --format native --max-res 512 --shared-ytd 1nfx_billie_tex

Zero external dependencies beyond Blender 4.2 built-in bpy, bmesh, mathutils, numpy.
"""

from contextlib import contextmanager
import hashlib
import json
import math
import os
import random
import re
import zlib

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FONT_DIR = os.path.join(SKILL_ROOT, "assets", "fonts")
DEFAULT_FONT = os.path.join(FONT_DIR, "TitanOne-Regular.ttf")
WORKSPACE_ROOT = os.path.normpath(os.path.join(SKILL_ROOT, "..", "..", "..", ".."))
THEME_DIR = os.path.join(
    WORKSPACE_ROOT, "resources", "[resources]", "[1nfx]", "1nfx_assetsimg", "theme"
)
DEFAULT_ART_DIR = os.path.join(WORKSPACE_ROOT, "work", "1nfx_prop_billie_v2", "art")

# Official BILLIE SCHOOL / billie-ui Cohesive Plush Palette
BILLIE_PALETTE = {
    # Core surfaces
    "cream": "#FFFBF4",
    "light": "#FFFBF4",
    "latte": "#FAF0E2",
    "latte_deep": "#F2E2CD",
    "white": "#FFFFFF",
    # Brand caramel & cocoa
    "caramel": "#C8966B",
    "primary": "#C8966B",
    "caramel_deep": "#A8744B",
    "honey": "#E9BC8C",
    "wood": "#E9BC8C",
    "cocoa": "#3B281E",
    "dark": "#3B281E",
    "cocoa_soft": "#6F5444",
    # Accents
    "gold": "#FFD147",
    "amber": "#F5A623",
    "orange": "#FFA34F",
    "pink": "#F4A7B9",
    "trim": "#F4A7B9",
    "pink_soft": "#FCE0E8",
    "sky": "#86C5E8",
    "accent": "#86C5E8",
    "sky_deep": "#5BA8D6",
    "sage": "#82C48D",
    "mint": "#82C48D",
    "berry": "#D95162",
    "redbox": "#D95162",
    "grey": "#B8BEC8",
    "cat": "#B8BEC8",
    "metal": "#D6CEC6",
    "skin": "#FFF0E1",
    "glass": "#D8F1FC",
    # Procedural diagonal café stripe roles (baked directly into atlas — 0 extra slots!)
    "stripe_caramel": "#C8966B",
    "stripe_pink": "#F4A7B9",
    "stripe_sky": "#86C5E8",
    "stripe_sage": "#82C48D",
    "stripe_amber": "#F5A623",
    "stripe_berry": "#D95162",
    # Emissive glow roles
    "glow": "#FFE169",
    "glow_amber": "#FFAC33",
    "glow_pink": "#FFB6C8",
    "glow_sky": "#9BE0FF",
    "glow_cream": "#FFFDF5",
    "glowtrim": "#FFB6C8",
    "screen": "#FFF8EC",
}

STRIPE_ROLES = {
    "stripe_caramel": ("#C8966B", "#FFFBF4"),
    "stripe_pink": ("#F4A7B9", "#FFFBF4"),
    "stripe_sky": ("#86C5E8", "#FFFBF4"),
    "stripe_sage": ("#82C48D", "#FFFBF4"),
    "stripe_amber": ("#F5A623", "#FFFBF4"),
    "stripe_berry": ("#D95162", "#FFFBF4"),
}

EMISSIVE_ROLES = {
    "glow",
    "glow_amber",
    "glow_pink",
    "glow_sky",
    "glow_cream",
    "glowtrim",
    "screen",
}


# ---------------------------------------------------------------------------
# Color & Math Helpers
# ---------------------------------------------------------------------------


def srgb_to_linear(c):
    c = max(0.0, min(1.0, float(c)))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = max(0.0, min(1.0, float(c)))
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def hex_rgb(value):
    v = str(value).lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    return (int(v[0:2], 16) / 255.0, int(v[2:4], 16) / 255.0, int(v[4:6], 16) / 255.0)


def hex_rgba_lin(value, alpha=1.0):
    r, g, b = hex_rgb(value)
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), float(alpha))


def trs(loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    return Matrix.LocRotScale(Vector(loc), Euler(rot).to_quaternion(), Vector(scale))


def facing(direction):
    d = Vector(direction)
    if d.length < 1e-6:
        return Matrix.Identity(4)
    return d.normalized().to_track_quat("-Y", "Z").to_matrix().to_4x4()


def plush_rounded_rect_pts(w, h, r, segs_corner=6):
    """Return smooth 2D rounded rectangle contour [(x, z), ...] centered at (0, 0)."""
    hw, hh = w * 0.5, h * 0.5
    r = max(0.0, min(float(r), hw * 0.96, hh * 0.96))
    pts = []
    corners = [
        (hw - r, -hh + r, -90.0),
        (hw - r, hh - r, 0.0),
        (-hw + r, hh - r, 90.0),
        (-hw + r, -hh + r, 180.0),
    ]
    n = max(2, int(segs_corner))
    for cx, cz, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    # Remove duplicate seam vertices
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-5:
        out.pop()
    return out


def _chaikin_open(pts, iters=1):
    cur = list(pts)
    for _ in range(max(0, int(iters))):
        if len(cur) < 3:
            break
        nxt = [cur[0]]
        for i in range(len(cur) - 1):
            p0, p1 = cur[i], cur[i + 1]
            nxt.append(tuple(0.75 * a + 0.25 * b for a, b in zip(p0, p1)))
            nxt.append(tuple(0.25 * a + 0.75 * b for a, b in zip(p0, p1)))
        nxt.append(cur[-1])
        cur = nxt
    return cur


def _chaikin_closed(pts, iters=1):
    cur = list(pts)
    for _ in range(max(0, int(iters))):
        n = len(cur)
        if n < 3:
            break
        nxt = []
        for i in range(n):
            p0, p1 = cur[i], cur[(i + 1) % n]
            nxt.append(tuple(0.75 * a + 0.25 * b for a, b in zip(p0, p1)))
            nxt.append(tuple(0.25 * a + 0.75 * b for a, b in zip(p0, p1)))
        cur = nxt
    return cur


# ---------------------------------------------------------------------------
# Pure-NumPy 2D Image & Raster Helpers (Zero PIL Dependency)
# ---------------------------------------------------------------------------


def _load_rgba_topdown(path):
    """Load PNG via Blender into float32 sRGB numpy array (H, W, 4), row 0 = top."""
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        arr = np.clip(buf.reshape((h, w, 4))[::-1, :, :], 0.0, 1.0).copy()
        return arr
    finally:
        bpy.data.images.remove(img)


def _save_rgba_topdown(arr, path, alpha=True):
    """Save float32 sRGB numpy array (H, W, 4) (row 0 = top) to PNG via Blender."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    h, w, _ = arr.shape
    flipped = np.clip(arr[::-1, :, :], 0.0, 1.0).astype(np.float32)
    if not alpha:
        flipped[:, :, 3] = 1.0
    img = bpy.data.images.new("_ks_save_tmp", w, h, alpha=bool(alpha))
    try:
        img.pixels.foreach_set(flipped.ravel())
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)
    return path


def _bleed_rgb(rgba, passes=12):
    """Flood-fill RGB of near-transparent pixels from opaque neighbors (kills dark halos)."""
    arr = rgba.copy()
    valid = arr[..., 3] > 0.05
    if valid.all() or not valid.any():
        return arr
    rgb = arr[..., :3]
    for _ in range(passes):
        if valid.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(valid.shape, dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sr = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            sv = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
            if dy == -1:
                sv[-1, :] = False
            elif dy == 1:
                sv[0, :] = False
            if dx == -1:
                sv[:, -1] = False
            elif dx == 1:
                sv[:, 0] = False
            m = sv.astype(np.float32)
            acc += sr * m[..., None]
            cnt += m
        fill = (~valid) & (cnt > 0)
        if not fill.any():
            break
        rgb[fill] = acc[fill] / cnt[fill, None]
        valid[fill] = True
    arr[..., :3] = rgb
    return arr


def _resize_rgba(arr, new_w, new_h):
    """High-quality area/bilinear resize of float32 RGBA array (H, W, 4)."""
    h, w, _ = arr.shape
    if w == new_w and h == new_h:
        return arr.copy()
    # Multi-step 2x box pre-downsample for crisp anti-aliasing when shrinking strongly
    cur = arr.astype(np.float32)
    while cur.shape[0] >= new_h * 2 and cur.shape[1] >= new_w * 2:
        ch, cw = cur.shape[0] & ~1, cur.shape[1] & ~1
        c = cur[:ch, :cw]
        a = c[..., 3:4]
        prem = c[..., :3] * a
        prem_d = prem.reshape(ch // 2, 2, cw // 2, 2, 3).mean(axis=(1, 3))
        a_d = a.reshape(ch // 2, 2, cw // 2, 2, 1).mean(axis=(1, 3))
        rgb_d = np.where(a_d > 1e-4, prem_d / np.maximum(a_d, 1e-4), c[..., :3].reshape(ch // 2, 2, cw // 2, 2, 3).mean(axis=(1, 3)))
        cur = np.concatenate((rgb_d, a_d), axis=-1)
    sh, sw, _ = cur.shape
    if sw == new_w and sh == new_h:
        return cur
    # Vectorized bilinear resample in premultiplied alpha space
    ys = (np.arange(new_h, dtype=np.float32) + 0.5) * (sh / float(new_h)) - 0.5
    xs = (np.arange(new_w, dtype=np.float32) + 0.5) * (sw / float(new_w)) - 0.5
    ys = np.clip(ys, 0.0, sh - 1.0)
    xs = np.clip(xs, 0.0, sw - 1.0)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, sh - 1)
    x1 = np.minimum(x0 + 1, sw - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]
    prem = np.concatenate((cur[..., :3] * cur[..., 3:4], cur[..., 3:4]), axis=-1)
    top = prem[y0][:, x0] * (1.0 - wx) + prem[y0][:, x1] * wx
    bot = prem[y1][:, x0] * (1.0 - wx) + prem[y1][:, x1] * wx
    res = top * (1.0 - wy) + bot * wy
    a = np.clip(res[..., 3:4], 0.0, 1.0)
    rgb = np.where(a > 1e-4, res[..., :3] / np.maximum(a, 1e-4), 0.0)
    return np.clip(np.concatenate((rgb, a), axis=-1), 0.0, 1.0)


def _alpha_over(dst, src):
    """Porter-Duff src over dst, both (H, W, 4) float32 sRGB."""
    sa = src[..., 3:4]
    da = dst[..., 3:4]
    out_a = sa + da * (1.0 - sa)
    out_rgb = (src[..., :3] * sa + dst[..., :3] * da * (1.0 - sa)) / np.maximum(out_a, 1e-5)
    return np.clip(np.concatenate((out_rgb, out_a), axis=-1), 0.0, 1.0)


def _paste_rgba(dst, src, x0, y0):
    """Composite src onto dst at integer top-left (x0, y0)."""
    dh, dw, _ = dst.shape
    sh, sw, _ = src.shape
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(dw, x0 + sw), min(dh, y0 + sh)
    if dx1 <= dx0 or dy1 <= dy0:
        return dst
    sx0, sy0 = dx0 - x0, dy0 - y0
    sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)
    dst[dy0:dy1, dx0:dx1] = _alpha_over(dst[dy0:dy1, dx0:dx1], src[sy0:sy1, sx0:sx1])
    return dst


def _crop_alpha_bbox(arr, pad_ratio=0.04, thresh=0.04):
    """Crop RGBA array tight to non-transparent bounding box with proportional padding."""
    mask = arr[..., 3] > thresh
    if not mask.any():
        return arr
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    h, w, _ = arr.shape
    py = int((y1 - y0) * pad_ratio)
    px = int((x1 - x0) * pad_ratio)
    return arr[max(0, y0 - py):min(h, y1 + py), max(0, x0 - px):min(w, x1 + px)].copy()


def _sdf_rounded_rect(xx, yy, cx, cy, hw, hh, r):
    dx = np.abs(xx - cx) - max(0.0, hw - r)
    dy = np.abs(yy - cy) - max(0.0, hh - r)
    outside = np.hypot(np.maximum(dx, 0.0), np.maximum(dy, 0.0))
    inside = np.minimum(np.maximum(dx, dy), 0.0)
    return outside + inside - r


def _paint_sdf(canvas, dist, color_hex, alpha=1.0, aa=1.5):
    """Anti-aliased SDF fill onto canvas (H, W, 4)."""
    cov = np.clip(0.5 - dist / max(0.5, float(aa)), 0.0, 1.0) * float(alpha)
    if cov.max() <= 1e-4:
        return canvas
    r, g, b = hex_rgb(color_hex)
    src = np.empty_like(canvas)
    src[..., 0] = r
    src[..., 1] = g
    src[..., 2] = b
    src[..., 3] = cov
    return _alpha_over(canvas, src)


def _paint_star_2d(canvas, xx, yy, cx, cy, r_out, r_in, points, color_hex, outline_hex=None, outline_w=2.0):
    """Paint a crisp anti-aliased 4- or 5-point sparkle/star onto 2D canvas."""
    dx = xx - cx
    dy = yy - cy
    rad = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx) + math.pi * 0.5
    sector = math.tau / points
    a_loc = np.abs(((ang + sector * 0.5) % sector) - sector * 0.5)
    # Smoothly interpolate radius between tip (a=0) and valley (a=sector/2)
    t = a_loc / (sector * 0.5)
    r_bound = r_out * (1.0 - t) + r_in * t
    if points == 4:
        # Extra crisp concave 4-point sparkle curve
        r_bound = r_in + (r_out - r_in) * np.power(np.clip(1.0 - t, 0.0, 1.0), 1.65)
    dist = rad - r_bound
    if outline_hex:
        canvas = _paint_sdf(canvas, dist - outline_w, outline_hex, aa=1.4)
    canvas = _paint_sdf(canvas, dist, color_hex, aa=1.4)
    return canvas


def _dilate_alpha_disc(alpha, radius_px):
    """Smooth circular morphological dilation of 2D float alpha mask (H, W) — zero curve-offset glitches!"""
    r = max(1, int(round(float(radius_px))))
    h, w = alpha.shape
    out = alpha.copy()
    # Two-pass circular disc dilation via integer offsets (super fast at 512x256/512x512!)
    r2 = float(radius_px) * float(radius_px)
    # Sample perimeter + interior ring offsets sparsely for speed when r > 4
    offsets = []
    step = 1 if r <= 5 else 2
    for dy in range(-r, r + 1, step):
        for dx in range(-r, r + 1, step):
            d2 = dx * dx + dy * dy
            if 0 < d2 <= r2 + 0.5:
                offsets.append((dy, dx))
    # Also ensure outer ring is fully covered when step > 1
    if step > 1:
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            offsets.append((int(round(math.sin(a) * radius_px)), int(round(math.cos(a) * radius_px))))
    for dy, dx in set(offsets):
        sy0, sy1 = max(0, -dy), min(h, h - dy)
        sx0, sx1 = max(0, -dx), min(w, w - dx)
        dy0, dy1 = max(0, dy), min(h, h + dy)
        dx0, dx1 = max(0, dx), min(w, w + dx)
        np.maximum(out[dy0:dy1, dx0:dx1], alpha[sy0:sy1, sx0:sx1], out=out[dy0:dy1, dx0:dx1])
    # Gentle 3x3 smoothing pass for silky anti-aliased outline edge
    p = np.pad(out, ((1, 1), (1, 1)), mode="edge")
    out = (
        p[0:-2, 0:-2] + 2.0 * p[0:-2, 1:-1] + p[0:-2, 2:]
        + 2.0 * p[1:-1, 0:-2] + 4.0 * p[1:-1, 1:-1] + 2.0 * p[1:-1, 2:]
        + p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + p[2:, 2:]
    ) * (1.0 / 16.0)
    return np.clip(out * 1.12, 0.0, 1.0)


def _render_text_layer(text, width, height, text_hex="#3B281E", outline_hex="#FFFBF4",
                       outline_px=6.0, font_path=None, scale_fill=0.82, y_offset=0.0):
    """Render razor-sharp anti-aliased TTF text + silky circular sticker outline (~20ms)."""
    prev_scene = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    sc = bpy.data.scenes.new("_ks_txt_scene")
    created_objs = []
    created_curves = []
    created_mats = []
    cam_data = None
    tmp_path = os.path.join(bpy.app.tempdir, "_ks_txt_{}.png".format(os.getpid()))
    try:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 12
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.render.resolution_x = int(width)
        sc.render.resolution_y = int(height)
        sc.render.resolution_percentage = 100
        sc.render.film_transparent = True
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.view_settings.exposure = 0.0

        ortho_w = 4.0
        ortho_h = ortho_w * (height / float(width))
        cam_data = bpy.data.cameras.new("_ks_txt_cam")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho_w
        cam_ob = bpy.data.objects.new("_ks_txt_cam", cam_data)
        sc.collection.objects.link(cam_ob)
        cam_ob.location = (0.0, 0.0, 5.0)
        sc.camera = cam_ob
        created_objs.append(cam_ob)

        fpath = font_path or DEFAULT_FONT
        bfont = bpy.data.fonts.load(fpath, check_existing=True) if os.path.isfile(fpath) else None

        m = bpy.data.materials.new("_ks_txt_m_fill")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out_n = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs["Emission"], out_n.inputs["Surface"])
        created_mats.append(m)

        fd = bpy.data.curves.new("_ks_txt_fill", "FONT")
        fd.body = str(text)
        fd.align_x = "CENTER"
        fd.align_y = "CENTER"
        fd.size = 1.0
        fd.space_character = 1.05
        if bfont:
            fd.font = bfont
        fo = bpy.data.objects.new("_ks_txt_fill", fd)
        sc.collection.objects.link(fo)
        created_curves.append(fd)
        created_objs.append(fo)

        if bpy.context.window:
            bpy.context.window.scene = sc
        bpy.context.view_layer.update()
        bb = [Vector(c) for c in fo.bound_box]
        raw_w = max(0.25, max(c.x for c in bb) - min(c.x for c in bb))
        raw_h = max(0.25, max(c.y for c in bb) - min(c.y for c in bb))
        fit_scale = min((ortho_w * scale_fill) / raw_w, (ortho_h * 0.72) / raw_h)
        fd.size = fit_scale
        fo.location = (0.0, y_offset * ortho_h, 0.05)
        fd.materials.append(m)

        sc.render.filepath = tmp_path
        bpy.ops.render.render(write_still=True, scene=sc.name)
        mask_arr = _load_rgba_topdown(tmp_path)
        fill_a = np.clip(mask_arr[..., 3], 0.0, 1.0)

        h_px, w_px = fill_a.shape
        out_img = np.zeros((h_px, w_px, 4), dtype=np.float32)
        if outline_hex and outline_px > 0.0:
            dil_a = _dilate_alpha_disc(fill_a, outline_px)
            orr, og, ob = hex_rgb(outline_hex)
            out_img[..., 0] = orr
            out_img[..., 1] = og
            out_img[..., 2] = ob
            out_img[..., 3] = dil_a
        fr, fg, fb = hex_rgb(text_hex)
        fill_img = np.zeros((h_px, w_px, 4), dtype=np.float32)
        fill_img[..., 0] = fr
        fill_img[..., 1] = fg
        fill_img[..., 2] = fb
        fill_img[..., 3] = fill_a
        return _alpha_over(out_img, fill_img)
    finally:
        if bpy.context.window and prev_scene:
            bpy.context.window.scene = prev_scene
        for ob in created_objs:
            if ob.name in bpy.data.objects:
                bpy.data.objects.remove(ob, do_unlink=True)
        for cu in created_curves:
            if cu.name in bpy.data.curves:
                bpy.data.curves.remove(cu)
        for m in created_mats:
            if m.name in bpy.data.materials:
                bpy.data.materials.remove(m)
        if cam_data and cam_data.name in bpy.data.cameras:
            bpy.data.cameras.remove(cam_data)
        if sc.name in bpy.data.scenes:
            bpy.data.scenes.remove(sc)
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public Art & Texture Generators
# ---------------------------------------------------------------------------


def striped_pbr_tex(out_path, col_a="#C8966B", col_b="#FFFBF4", size=256, stripes=6, angle_deg=45.0):
    """Generate a crisp seamless power-of-two diagonal/vertical café stripe PNG texture."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) / float(s)
    rad = math.radians(angle_deg)
    # Periodic projection compatible with seamless tiling when angle is 0, 45, 90
    if abs(angle_deg - 45.0) < 1.0:
        phase = (xx + yy) * stripes
    elif abs(angle_deg - 90.0) < 1.0:
        phase = yy * stripes
    elif abs(angle_deg) < 1.0:
        phase = xx * stripes
    else:
        phase = (xx * math.cos(rad) + yy * math.sin(rad)) * stripes
    frac = phase - np.floor(phase)
    # Smooth anti-aliased edge
    edge = max(0.015, 1.5 * stripes / float(s))
    m = np.clip((frac - 0.5) / edge + 0.5, 0.0, 1.0)
    m2 = np.clip((1.0 - frac) / edge, 0.0, 1.0)
    m = m * m2
    ra, ga, ba = hex_rgb(col_a)
    rb, gb, bb = hex_rgb(col_b)
    arr = np.ones((s, s, 4), dtype=np.float32)
    arr[..., 0] = ra * (1.0 - m) + rb * m
    arr[..., 1] = ga * (1.0 - m) + gb * m
    arr[..., 2] = ba * (1.0 - m) + bb * m
    arr[..., 3] = 1.0
    return _save_rgba_topdown(arr, out_path, alpha=False)


def make_text_banner(
    text,
    out_path,
    bg_hex="#FFFBF4",
    border_hex="#3B281E",
    text_hex="#FFFBF4",
    text_outline_hex="#3B281E",
    accent_hex="#C8966B",
    subtitle="",
    striped=True,
    width=512,
    height=256,
    stars=True,
    icon_path=None,
):
    """Generate a crisp power-of-two billie-ui style rounded signboard graphic PNG."""
    w, h = int(width), int(height)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    canvas = np.zeros((h, w, 4), dtype=np.float32)
    # Fill outer canvas with border color so mipmaps never bleed black
    br, bg_c, bb = hex_rgb(border_hex)
    canvas[..., 0] = br
    canvas[..., 1] = bg_c
    canvas[..., 2] = bb
    canvas[..., 3] = 1.0

    # Inner rounded cream/pastel panel
    pad = max(10.0, min(w, h) * 0.048)
    cr = min(w, h) * 0.16
    d_inner = _sdf_rounded_rect(xx, yy, w * 0.5, h * 0.5, w * 0.5 - pad, h * 0.5 - pad, cr)
    canvas = _paint_sdf(canvas, d_inner, bg_hex, aa=1.5)

    # Optional cozy diagonal stripe wash inside panel
    if striped:
        stripe_phase = ((xx + yy) / max(24.0, min(w, h) * 0.22)) % 1.0
        sm = ((stripe_phase < 0.44) & (d_inner < -2.0)).astype(np.float32) * 0.18
        ar, ag, ab = hex_rgb(accent_hex)
        src = np.zeros_like(canvas)
        src[..., 0], src[..., 1], src[..., 2], src[..., 3] = ar, ag, ab, sm
        canvas = _alpha_over(canvas, src)

    # Top glossy highlight ribbon inside panel (bbu 2-tone sheen!)
    d_top = _sdf_rounded_rect(xx, yy, w * 0.5, pad + h * 0.12, w * 0.5 - pad * 1.8, h * 0.09, cr * 0.45)
    canvas = _paint_sdf(canvas, np.maximum(d_top, d_inner + 4.0), "#FFFFFF", alpha=0.45, aa=2.0)

    # Accent header pill bar behind text for high legibility
    if accent_hex:
        pill_h = h * (0.28 if subtitle else 0.34)
        pill_cy = h * (0.42 if subtitle else 0.50)
        d_pill = _sdf_rounded_rect(xx, yy, w * 0.5, pill_cy, w * 0.41, pill_h, pill_h * 0.85)
        canvas = _paint_sdf(canvas, d_pill - 5.0, border_hex, aa=1.5)
        canvas = _paint_sdf(canvas, d_pill, accent_hex, aa=1.5)
        # Soft glossy top half of pill
        d_pill_hi = np.maximum(d_pill + 2.0, (yy - pill_cy))
        canvas = _paint_sdf(canvas, d_pill_hi, "#FFFFFF", alpha=0.18, aa=2.0)

    # Inner decorative dashed/dotted border frame
    d_ring = np.abs(d_inner + pad * 0.55) - 2.2
    canvas = _paint_sdf(canvas, d_ring, accent_hex or border_hex, alpha=0.45, aa=1.2)

    # Golden Billie stars in corners
    if stars:
        s_r = min(w, h) * 0.085
        for sx, sy, pts in (
            (pad + s_r * 1.35, pad + s_r * 1.25, 4),
            (w - pad - s_r * 1.35, pad + s_r * 1.25, 5),
            (pad + s_r * 1.45, h - pad - s_r * 1.20, 5),
            (w - pad - s_r * 1.45, h - pad - s_r * 1.20, 4),
        ):
            canvas = _paint_star_2d(canvas, xx, yy, sx, sy, s_r, s_r * 0.44, pts, "#FFD147", border_hex, 2.2)

    # Optional cute corner mascot icon
    if icon_path and os.path.isfile(icon_path):
        ic = _load_rgba_topdown(icon_path)
        ic_s = int(min(w, h) * 0.44)
        ic = _resize_rgba(ic, ic_s, ic_s)
        _paste_rgba(canvas, ic, int(pad * 1.1), int((h - ic_s) * 0.5))

    # Render crisp TitanOne main text
    txt_y = 0.08 if subtitle else 0.0
    txt_scale = 0.68 if icon_path else 0.74
    txt_layer = _render_text_layer(
        text, w, h,
        text_hex=text_hex,
        outline_hex=text_outline_hex,
        outline_px=max(5.5, w * 0.015),
        scale_fill=txt_scale,
        y_offset=txt_y,
    )
    canvas = _alpha_over(canvas, txt_layer)

    if subtitle:
        sub_layer = _render_text_layer(
            subtitle, w, h,
            text_hex=border_hex,
            outline_hex="#FFFBF4",
            outline_px=max(3.5, w * 0.008),
            scale_fill=0.48,
            y_offset=-0.27,
        )
        canvas = _alpha_over(canvas, sub_layer)

    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _make_atm_screen(out_path, size=512):
    """Generate super-cute glowing BILLIE BANK kawaii smiling ATM screen (512x512)."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    canvas = np.ones((s, s, 4), dtype=np.float32)
    r0, g0, b0 = hex_rgb("#FFFBF4")
    canvas[..., 0], canvas[..., 1], canvas[..., 2] = r0, g0, b0

    # Soft latte subtle top-to-bottom warmth
    grad = (yy / float(s))[:, :, None]
    r1, g1, b1 = hex_rgb("#FAF0E2")
    canvas[..., 0] = r0 * (1.0 - grad[..., 0]) + r1 * grad[..., 0]
    canvas[..., 1] = g0 * (1.0 - grad[..., 0]) + g1 * grad[..., 0]
    canvas[..., 2] = b0 * (1.0 - grad[..., 0]) + b1 * grad[..., 0]

    # Top caramel header bar
    d_hdr = _sdf_rounded_rect(xx, yy, s * 0.5, s * 0.11, s * 0.44, s * 0.075, s * 0.035)
    canvas = _paint_sdf(canvas, d_hdr - 4.0, "#3B281E")
    canvas = _paint_sdf(canvas, d_hdr, "#C8966B")
    hdr_txt = _render_text_layer("BILLIE BANK", s, s, text_hex="#FFFBF4", outline_hex="#3B281E",
                                 outline_px=5.0, scale_fill=0.58, y_offset=0.39)
    canvas = _alpha_over(canvas, hdr_txt)

    # Big smiling kawaii face in center!
    for sx in (-1.0, 1.0):
        ex = s * (0.5 + sx * 0.175)
        ey = s * 0.41
        # Glossy espresso-cocoa oval eyes
        d_eye = np.hypot((xx - ex) / (s * 0.068), (yy - ey) / (s * 0.082)) * (s * 0.075) - s * 0.075
        canvas = _paint_sdf(canvas, d_eye, "#3B281E")
        # Big white sparkle catchlight + mini lower catchlight
        d_hi1 = np.hypot(xx - (ex - sx * s * 0.018), yy - (ey - s * 0.025)) - s * 0.024
        d_hi2 = np.hypot(xx - (ex + sx * s * 0.022), yy - (ey + s * 0.028)) - s * 0.011
        canvas = _paint_sdf(canvas, d_hi1, "#FFFFFF")
        canvas = _paint_sdf(canvas, d_hi2, "#FFFFFF")
        # Rosy blush cheek oval
        bx = s * (0.5 + sx * 0.275)
        by = s * 0.505
        d_blush = np.hypot((xx - bx) / (s * 0.078), (yy - by) / (s * 0.044)) * (s * 0.06) - s * 0.06
        canvas = _paint_sdf(canvas, d_blush, "#F4A7B9", alpha=0.82, aa=6.0)

    # Cute 'w' cat-bear smile (two rounded lower arcs)
    for sx in (-1.0, 1.0):
        mx = s * (0.5 + sx * 0.046)
        my = s * 0.495
        d_arc = np.abs(np.hypot(xx - mx, yy - my) - s * 0.046) - s * 0.010
        d_arc = np.where(yy >= my, d_arc, 99.0)
        canvas = _paint_sdf(canvas, d_arc, "#3B281E")
    # Rosy tiny open tongue dot under smile
    d_tng = np.hypot(xx - s * 0.5, yy - s * 0.552) - s * 0.022
    canvas = _paint_sdf(canvas, d_tng, "#F4A7B9")

    # Sparkle stars flanking face
    canvas = _paint_star_2d(canvas, xx, yy, s * 0.13, s * 0.34, s * 0.045, s * 0.018, 4, "#FFD147", "#3B281E", 2.0)
    canvas = _paint_star_2d(canvas, xx, yy, s * 0.87, s * 0.34, s * 0.045, s * 0.018, 4, "#FFD147", "#3B281E", 2.0)

    # Two cute bbu-style 2-tone pill buttons at bottom
    for sx, bcol, lbl in ((-0.23, "#82C48D", "DEPOSIT"), (0.23, "#FFD147", "CASH")):
        bcx, bcy = s * (0.5 + sx), s * 0.78
        d_btn = _sdf_rounded_rect(xx, yy, bcx, bcy, s * 0.19, s * 0.082, s * 0.045)
        canvas = _paint_sdf(canvas, d_btn - 4.5, "#3B281E")
        canvas = _paint_sdf(canvas, d_btn, bcol)
        d_hi = np.maximum(d_btn + 2.0, yy - bcy)
        canvas = _paint_sdf(canvas, d_hi, "#FFFFFF", alpha=0.25)

    btn_l = _render_text_layer("DEPOSIT", s, s, text_hex="#3B281E", outline_hex="#FFFBF4",
                               outline_px=3.0, scale_fill=0.30, y_offset=-0.28)
    # Shift left/right for two buttons
    shift_px = int(s * 0.23)
    btn_l_s = np.roll(btn_l, -shift_px, axis=1)
    btn_l_s[:, -shift_px:] = 0.0
    canvas = _alpha_over(canvas, btn_l_s)

    btn_r = _render_text_layer("CASH", s, s, text_hex="#3B281E", outline_hex="#FFFBF4",
                               outline_px=3.0, scale_fill=0.22, y_offset=-0.28)
    btn_r_s = np.roll(btn_r, shift_px, axis=1)
    btn_r_s[:, :shift_px] = 0.0
    canvas = _alpha_over(canvas, btn_r_s)

    # Outer cocoa frame border
    d_border = np.abs(_sdf_rounded_rect(xx, yy, s * 0.5, s * 0.5, s * 0.48, s * 0.48, s * 0.05)) - 6.0
    canvas = _paint_sdf(canvas, d_border, "#3B281E")
    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _make_gauge_dial(out_path, size=512):
    """Generate a super-cute round pressure gauge dial (512x512) for waterpipe/powerbox."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    cx = cy = s * 0.5
    dx = xx - cx
    dy = yy - cy
    rad = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)  # -pi..pi, top = -pi/2

    canvas = np.ones((s, s, 4), dtype=np.float32)
    r0, g0, b0 = hex_rgb("#FFFBF4")
    canvas[..., 0], canvas[..., 1], canvas[..., 2] = r0, g0, b0

    # Colored pressure arc ring (from 135 deg bottom-left clockwise through top to 45 deg bottom-right)
    # In screen coords (y down): bottom-left = +135 deg (+2.356), top = -90 deg (-1.571), bottom-right = +45 deg (+0.785)
    # Map angle so bottom-left = 0.0, top = 0.5, bottom-right = 1.0
    rel = ((ang - math.radians(135.0)) % math.tau) / math.radians(270.0)
    in_arc = (rel >= 0.0) & (rel <= 1.0)
    d_ring = np.abs(rad - s * 0.365) - s * 0.042
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel < 0.45), d_ring, 99.0), "#86C5E8")
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel >= 0.45) & (rel < 0.78), d_ring, 99.0), "#FFD147")
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel >= 0.78), d_ring, 99.0), "#D95162")

    # Tick marks
    for k in range(11):
        a = math.radians(135.0 + 270.0 * k / 10.0)
        ca, sa = math.cos(a), math.sin(a)
        px0, py0 = cx + ca * s * 0.27, cy + sa * s * 0.27
        px1, py1 = cx + ca * s * 0.34, cy + sa * s * 0.34
        vx, vy = px1 - px0, py1 - py0
        t = np.clip(((xx - px0) * vx + (yy - py0) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
        dt = np.hypot(xx - (px0 + t * vx), yy - (py0 + t * vy)) - (5.0 if k % 5 == 0 else 3.0)
        canvas = _paint_sdf(canvas, dt, "#3B281E")

    # Cute mini kawaii eyes, rosy blush & 'w' smile in lower half
    for sx in (-1.0, 1.0):
        ex = cx + sx * s * 0.105
        ey = cy + s * 0.145
        canvas = _paint_sdf(canvas, np.hypot(xx - ex, yy - ey) - s * 0.028, "#3B281E")
        canvas = _paint_sdf(canvas, np.hypot(xx - (ex - sx * 5.0), yy - (ey - 6.0)) - s * 0.010, "#FFFFFF")
        canvas = _paint_sdf(canvas, np.hypot(xx - (ex + sx * s * 0.052), yy - (ey + s * 0.032)) - s * 0.028, "#F4A7B9", alpha=0.80, aa=3.5)
        mx = cx + sx * s * 0.026
        my = cy + s * 0.175
        d_sm = np.abs(np.hypot(xx - mx, yy - my) - s * 0.026) - s * 0.007
        canvas = _paint_sdf(canvas, np.where(yy >= my, d_sm, 99.0), "#3B281E")

    # Berry-red indicator needle pointing toward upper-right
    na = math.radians(-38.0)
    ca, sa = math.cos(na), math.sin(na)
    nx1, ny1 = cx + ca * s * 0.31, cy + sa * s * 0.31
    vx, vy = nx1 - cx, ny1 - cy
    t = np.clip(((xx - cx) * vx + (yy - cy) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
    d_ndl = np.hypot(xx - (cx + t * vx), yy - (cy + t * vy)) - (12.0 * (1.0 - 0.65 * t))
    canvas = _paint_sdf(canvas, d_ndl - 3.0, "#3B281E")
    canvas = _paint_sdf(canvas, d_ndl, "#D95162")
    # Center golden hub
    canvas = _paint_sdf(canvas, rad - s * 0.068, "#3B281E")
    canvas = _paint_sdf(canvas, rad - s * 0.052, "#FFD147")
    # Outer cocoa dial ring
    canvas = _paint_sdf(canvas, np.abs(rad - s * 0.46) - 10.0, "#3B281E")
    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _crop_mascot_face(src_path, out_path, crop_box, bg_hex="#FFF0E1", size=512):
    """Extract crisp 512x512 face+bangs oval texture from 2048px official Billie mascot PNG."""
    arr = _load_rgba_topdown(src_path)
    h, w, _ = arr.shape
    x0, y0, x1, y1 = crop_box
    ix0, iy0 = max(0, int(w * x0)), max(0, int(h * y0))
    ix1, iy1 = min(w, int(w * x1)), min(h, int(h * y1))
    sub = arr[iy0:iy1, ix0:ix1].copy()
    sub = _resize_rgba(sub, size, size)
    # Fill any transparent pixels cleanly with warm chibi skin color so opaque dome has zero edge seams
    bg = np.ones((size, size, 4), dtype=np.float32)
    r, g, b = hex_rgb(bg_hex)
    bg[..., 0], bg[..., 1], bg[..., 2] = r, g, b
    comp = _alpha_over(bg, sub)
    comp[..., 3] = 1.0
    return _save_rgba_topdown(comp, out_path, alpha=False)


def prepare_billie_art(out_dir=None, force=False):
    """Generate and cache all power-of-two Billie School decals, faces, screens & signs.

    Returns dict mapping short art keys -> absolute PNG filepaths.
    """
    art_dir = os.path.abspath(out_dir or DEFAULT_ART_DIR)
    os.makedirs(art_dir, exist_ok=True)
    arts = {}

    def _need(path):
        return bool(force or not os.path.isfile(path))

    # 1. Official BILLIE SCHOOL logo (tight-cropped 512x256 transparent RGBA with RGB bleed)
    logo_out = os.path.join(art_dir, "billie_logo.png")
    logo_src = os.path.join(THEME_DIR, "logo.png")
    if _need(logo_out) and os.path.isfile(logo_src):
        raw = _crop_alpha_bbox(_load_rgba_topdown(logo_src), pad_ratio=0.04)
        rh, rw, _ = raw.shape
        # Fit into 512x256 preserving aspect ratio
        scale = min(504.0 / max(1, rw), 248.0 / max(1, rh))
        tw, th = max(4, int(round(rw * scale))), max(4, int(round(rh * scale)))
        resized = _resize_rgba(raw, tw, th)
        can = np.zeros((256, 512, 4), dtype=np.float32)
        _paste_rgba(can, resized, (512 - tw) // 2, (256 - th) // 2)
        can = _bleed_rgb(can, passes=14)
        _save_rgba_topdown(can, logo_out, alpha=True)
    arts["logo"] = logo_out

    # 2. Official logo-bg.png & bg.png -> crisp 512x512 opaque
    for key, src_name, dst_name in (
        ("logo_bg", "logo-bg.png", "billie_logo_bg.png"),
        ("bg", "bg.png", "billie_bg.png"),
    ):
        dst = os.path.join(art_dir, dst_name)
        src = os.path.join(THEME_DIR, src_name)
        if _need(dst) and os.path.isfile(src):
            arr = _resize_rgba(_load_rgba_topdown(src), 512, 512)
            arr[..., 3] = 1.0
            _save_rgba_topdown(arr, dst, alpha=False)
        arts[key] = dst

    # 3. 4-School Plush Mascot Portraits (from 2048px theme/mascots/*.png -> 512x512 RGBA)
    #    PLUS Waving Mascots (from theme/mascot-*.png -> 256x256 RGBA)
    #    PLUS Tight Face+Bangs Textures (512x512 opaque for 3D billie_bear_plush curved face dome!)
    face_crops = {
        "brown": ("brown.png", (0.285, 0.235, 0.715, 0.600), "#F6E9D8"),
        "pink": ("pink.png", (0.280, 0.215, 0.720, 0.590), "#F6EAE0"),
        "skyblue": ("skyblue.png", (0.280, 0.220, 0.720, 0.590), "#F6ECE2"),
        "grey": ("gray.png", (0.280, 0.230, 0.720, 0.590), "#F5EAE0"),
    }
    for school, (fname, box, skin_hex) in face_crops.items():
        hi_src = os.path.join(THEME_DIR, "mascots", fname)
        port_out = os.path.join(art_dir, "mascot_{}.png".format(school))
        if _need(port_out) and os.path.isfile(hi_src):
            arr = _resize_rgba(_load_rgba_topdown(hi_src), 512, 512)
            arr = _bleed_rgb(arr, passes=12)
            _save_rgba_topdown(arr, port_out, alpha=True)
        arts["mascot_" + school] = port_out

        face_out = os.path.join(art_dir, "bear_face_{}.png".format(school))
        if _need(face_out) and os.path.isfile(hi_src):
            _crop_mascot_face(hi_src, face_out, box, bg_hex=skin_hex, size=512)
        arts["bear_face_" + school] = face_out

        w_src = os.path.join(THEME_DIR, "mascot-{}.png".format(school))
        w_out = os.path.join(art_dir, "mascot_wave_{}.png".format(school))
        if _need(w_out) and os.path.isfile(w_src):
            arr = _resize_rgba(_load_rgba_topdown(w_src), 256, 256)
            arr = _bleed_rgb(arr, passes=10)
            _save_rgba_topdown(arr, w_out, alpha=True)
        arts["mascot_wave_" + school] = w_out

    # 4. Special Kawaii UI Screens
    atm_out = os.path.join(art_dir, "billie_atm_screen.png")
    if _need(atm_out):
        _make_atm_screen(atm_out, 512)
    arts["atm_screen"] = atm_out

    gauge_out = os.path.join(art_dir, "billie_gauge_dial.png")
    if _need(gauge_out):
        _make_gauge_dial(gauge_out, 512)
    arts["gauge_dial"] = gauge_out

    # 5. Seamless Striped Café Textures
    for s_name, (ca, cb) in STRIPE_ROLES.items():
        sp = os.path.join(art_dir, s_name + ".png")
        if _need(sp):
            striped_pbr_tex(sp, ca, cb, size=256, stripes=6, angle_deg=45.0)
        arts[s_name] = sp

    # 6. Official Crisp Pre-Rendered Sign Banners (512x256)
    sign_specs = [
        ("sign_garage", "GARAGE", "BILLIE SCHOOL", "#FFFBF4", "#86C5E8"),
        ("sign_pound", "POUND", "BILLIE IMPOUND", "#FFFBF4", "#F5A623"),
        ("sign_parking", "PARKING", "BILLIE ZONE", "#FFFBF4", "#82C48D"),
        ("sign_shop", "SHOP", "BILLIE CAFE", "#FFFBF4", "#F4A7B9"),
        ("sign_atm", "ATM", "BILLIE BANK", "#FFFBF4", "#C8966B"),
        ("sign_crafting", "CRAFTING", "BILLIE STUDIO", "#FFFBF4", "#C8966B"),
        ("sign_airdrop", "AIRDROP", "BILLIE SUPPLY", "#FFFBF4", "#F5A623"),
        ("sign_redbox", "REDBOX", "BILLIE TOOL", "#FFFBF4", "#D95162"),
        ("sign_powerbox", "240V", "POWER BOX", "#FFFBF4", "#F5A623"),
        ("sign_waterpipe", "WATER", "PRESSURE VALVE", "#FFFBF4", "#86C5E8"),
        ("sign_gachapon", "GACHA", "BILLIE LUCKY", "#FFFBF4", "#F4A7B9"),
        ("sign_washmoney", "LAUNDRY", "BILLIE WASH", "#FFFBF4", "#86C5E8"),
        ("sign_loot", "LOOT", "BILLIE GIFT", "#FFFBF4", "#FFD147"),
        ("sign_billie", "BILLIE", "SCHOOL", "#FFFBF4", "#C8966B"),
    ]
    for key, title, sub, bg_h, acc_h in sign_specs:
        sp = os.path.join(art_dir, key + ".png")
        if _need(sp):
            make_text_banner(
                title, sp,
                bg_hex=bg_h,
                border_hex="#3B281E",
                text_hex="#FFFBF4",
                text_outline_hex="#3B281E",
                accent_hex=acc_h,
                subtitle=sub,
                striped=True,
                width=512,
                height=256,
                stars=True,
            )
        arts[key] = sp

    return arts


# ---------------------------------------------------------------------------
# Smooth Animation Track Evaluator (Exact Rest Pose at u=0.0 & Smooth Loop!)
# ---------------------------------------------------------------------------


def _smoothstep(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def eval_anim_track(track, u):
    """Evaluate bone pose delta (loc Vector, rot Quaternion) at u in [0, 1].
    GUARANTEES exact rest pose at u=0.0 (loc=(0,0,0), rot=identity)!"""
    kind = track.get("kind", "")
    loc = Vector((0.0, 0.0, 0.0))
    rx = ry = rz = 0.0

    if kind == "spin_z":
        spin_deg = float(track.get("spin_deg", 360.0))
        amp_z = float(track.get("amp_z", 0.0))
        tilt_x = float(track.get("tilt_x", 0.0))
        cycles = float(track.get("cycles", 1.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * cycles))
        rx = math.radians(tilt_x * math.sin(u * math.tau))
        rz = math.radians(spin_deg * u)

    elif kind == "spin_y":
        spin_deg = float(track.get("spin_deg", 360.0))
        ry = math.radians(spin_deg * u)

    elif kind == "spin_x":
        spin_deg = float(track.get("spin_deg", 360.0))
        rx = math.radians(spin_deg * u)

    elif kind in ("plush_bounce", "bob_rock"):
        amp_z = float(track.get("amp_z", 0.045))
        rock_y = float(track.get("rock_y", 7.0))
        rock_x = float(track.get("rock_x", 3.0))
        twist_z = float(track.get("twist_z", 0.0))
        cycles = float(track.get("cycles", 2.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * cycles))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rx = math.radians(rock_x * math.sin(u * math.tau * cycles))
        rz = math.radians(twist_z * math.sin(u * math.tau))

    elif kind == "marker_spin":
        amp_z = float(track.get("amp_z", 0.12))
        spin_deg = float(track.get("spin_deg", 360.0))
        tilt_x = float(track.get("tilt_x", 5.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau))
        rx = math.radians(tilt_x * math.sin(u * math.tau))
        ry = math.radians(tilt_x * 0.6 * math.sin(u * math.tau * 2.0))
        rz = math.radians(spin_deg * u)

    elif kind in ("orbit", "marker_orbit"):
        amp_z = float(track.get("amp_z", 0.07))
        spin_deg = float(track.get("spin_deg", -360.0))
        tilt_x = float(track.get("tilt_x", 6.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        rx = math.radians(tilt_x * math.sin(u * math.tau))
        rz = math.radians(spin_deg * u)

    elif kind == "crown_hover":
        amp_z = float(track.get("amp_z", 0.06))
        rock_y = float(track.get("rock_y", 7.0))
        twist_z = float(track.get("twist_z", 14.0))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rz = math.radians(twist_z * math.sin(u * math.tau))

    elif kind == "mascot_nod":
        amp_z = float(track.get("amp_z", 0.024))
        rock_y = float(track.get("rock_y", 7.0))
        rock_x = float(track.get("rock_x", 3.5))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rx = math.radians(rock_x * math.sin(u * math.tau * 2.0))

    elif kind == "sign_sway":
        amp_z = float(track.get("amp_z", 0.014))
        rock_y = float(track.get("rock_y", 2.8))
        rock_x = float(track.get("rock_x", 1.2))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau))
        ry = math.radians(rock_y * math.sin(u * math.tau))
        rx = math.radians(rock_x * math.sin(u * math.tau * 2.0))

    elif kind == "gate_lift":
        lift_deg = float(track.get("lift_deg", 62.0))
        sign = float(track.get("sign", -1.0))
        if u < 0.08:
            ang = 0.0
        elif u < 0.34:
            ang = lift_deg * _smoothstep(0.08, 0.34, u)
        elif u < 0.66:
            p = (u - 0.34) / 0.32
            ang = lift_deg + 2.2 * math.sin(p * math.tau)
        elif u < 0.90:
            ang = lift_deg * (1.0 - _smoothstep(0.66, 0.90, u))
        else:
            ang = 0.0
        ry = sign * math.radians(ang)

    elif kind == "hook_swing":
        swing_deg = float(track.get("swing_deg", 22.0))
        ry = math.radians(swing_deg * math.sin(u * math.tau))
        rx = math.radians(swing_deg * 0.25 * math.sin(u * math.tau * 2.0))

    elif kind in ("drawer_peek", "cash_peek"):
        pull_y = float(track.get("pull_y", -0.14))
        if u < 0.14:
            t = 0.0
        elif u < 0.36:
            t = _smoothstep(0.14, 0.36, u)
        elif u < 0.64:
            t = 1.0
        elif u < 0.86:
            t = 1.0 - _smoothstep(0.64, 0.86, u)
        else:
            t = 0.0
        loc.y = pull_y * t

    elif kind == "chest_lid":
        close_deg = float(track.get("close_deg", 24.0))
        wide_deg = float(track.get("wide_deg", -14.0))
        if u < 0.24:
            ang = close_deg * _smoothstep(0.0, 0.24, u)
        elif u < 0.36:
            ang = close_deg
        elif u < 0.58:
            t = _smoothstep(0.36, 0.58, u)
            ang = close_deg * (1.0 - t) + wide_deg * t
        elif u < 0.74:
            t = _smoothstep(0.58, 0.74, u)
            ang = wide_deg * (1.0 - t) + 2.5 * math.sin(t * math.pi)
        else:
            ang = 0.0
        rx = math.radians(ang)

    elif kind == "chest_coins":
        amp_z = float(track.get("amp_z", 0.11))
        spin_deg = float(track.get("spin_deg", 360.0))
        if u < 0.24:
            dz = -0.05 * _smoothstep(0.0, 0.24, u)
        elif u < 0.36:
            dz = -0.05
        elif u < 0.60:
            t = _smoothstep(0.36, 0.60, u)
            dz = -0.05 * (1.0 - t) + amp_z * t
        elif u < 0.86:
            t = (u - 0.60) / 0.26
            dz = amp_z * (1.0 - 0.45 * t) + 0.02 * math.sin(t * math.tau)
        else:
            t = _smoothstep(0.86, 1.0, u)
            dz = amp_z * 0.55 * (1.0 - t)
        loc.z = dz
        rz = math.radians(spin_deg * u)

    elif kind == "airdrop_gyro":
        spin_deg = float(track.get("spin_deg", -360.0))
        wobble_deg = float(track.get("wobble_deg", 16.0))
        amp_z = float(track.get("amp_z", 0.04))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 2.0))
        rx = math.radians(wobble_deg * math.sin(u * math.tau))
        ry = math.radians(wobble_deg * 0.65 * math.sin(u * math.tau * 2.0))
        rz = math.radians(spin_deg * u)

    elif kind == "breaker_flip":
        flip_deg = float(track.get("flip_deg", 56.0))
        t0 = float(track.get("t0", 0.10))
        t1 = float(track.get("t1", 0.50))
        span = max(0.08, t1 - t0)
        if u <= t0 or u >= t1:
            ang = 0.0
        else:
            p = (u - t0) / span
            if p < 0.28:
                ang = flip_deg * _smoothstep(0.0, 0.28, p)
            elif p < 0.68:
                ang = flip_deg
            else:
                ang = flip_deg * (1.0 - _smoothstep(0.68, 1.0, p))
        rx = math.radians(ang)

    elif kind == "siren_spin":
        spin_deg = float(track.get("spin_deg", 720.0))
        amp_z = float(track.get("amp_z", 0.014))
        loc.z = amp_z * 0.5 * (1.0 - math.cos(u * math.tau * 4.0))
        rz = math.radians(spin_deg * u)

    elif kind == "valve_spin":
        deg = float(track.get("spin_deg", 360.0))
        if u < 0.10:
            ang = 0.0
        elif u < 0.42:
            ang = deg * _smoothstep(0.10, 0.42, u)
        elif u < 0.58:
            ang = deg
        elif u < 0.90:
            ang = deg * (1.0 - _smoothstep(0.58, 0.90, u))
        else:
            ang = 0.0
        ry = math.radians(ang)

    elif kind == "crank_turn":
        deg = float(track.get("spin_deg", 360.0))
        if u < 0.12:
            ang = 0.0
        elif u < 0.54:
            ang = deg * _smoothstep(0.12, 0.54, u)
        else:
            ang = deg
        ry = math.radians(ang)

    elif kind == "drum_spin":
        deg = float(track.get("spin_deg", 360.0))
        ry = math.radians(deg * u)

    elif kind == "pendulum_x":
        deg = float(track.get("deg", 16.0))
        rx = math.radians(deg * math.sin(u * math.tau))

    elif kind == "pendulum_y":
        deg = float(track.get("deg", 16.0))
        ry = math.radians(deg * math.sin(u * math.tau))

    return loc, Euler((rx, ry, rz), "XYZ").to_quaternion()


# ---------------------------------------------------------------------------
# KawaiiBuilder — Smooth Pop-Mart / Animal-Crossing 3D Plush Artisan Class
# ---------------------------------------------------------------------------


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def purge_orphans():
    try:
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass


def mesh_bbox(ob):
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def tris_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


class KawaiiBuilder:
    """High-craft smooth plush 3D prop builder with automatic billie-ui Cycles baking & rigging."""

    def __init__(
        self,
        prop_id,
        archetype="custom",
        budget=14000,
        lod_dist=80,
        collision=True,
        animate=True,
        palette=None,
        art_dir=None,
        set_name="1nfx_billie",
        reset_scene=True,
    ):
        if reset_scene:
            clean_scene()
        self.id = str(prop_id)
        self.archetype = str(archetype)
        self.budget = int(budget)
        self.lod_dist = float(lod_dist)
        self.collision = bool(collision)
        self.animate = bool(animate)
        self.set_name = str(set_name)
        self.palette = dict(BILLIE_PALETTE)
        if palette:
            self.palette.update(palette)
        self.art_dir = os.path.abspath(art_dir or DEFAULT_ART_DIR)
        self.art = prepare_billie_art(self.art_dir, force=False)
        self.rng = random.Random(zlib.crc32(self.id.encode("utf-8")))

        self.parts = []
        self.colliders = []
        self.pending_cards = []
        self.materials = {}
        self.warnings = []
        self._part_idx = 0

        self.collection = bpy.data.collections.new(self.id + "_parts")
        bpy.context.scene.collection.children.link(self.collection)

        self.current_bone = "root"
        self.bones = {"root": {"pivot": (0.0, 0.0, 0.0), "parent": None}}
        self.anim_config = None

    # ---- Rigging & Collision API ----

    def define_bone(self, name, pivot, parent="root"):
        if name not in self.bones:
            self.bones[name] = {
                "pivot": tuple(float(v) for v in pivot),
                "parent": parent,
            }
        return name

    @contextmanager
    def use_bone(self, name):
        prev = self.current_bone
        self.current_bone = name if (self.animate and name in self.bones) else "root"
        try:
            yield
        finally:
            self.current_bone = prev

    def set_anim(self, frames=121, fps=30, tracks=None):
        if not self.animate:
            return
        self.anim_config = {
            "fps": int(fps),
            "frames": int(frames),
            "tracks": dict(tracks or {}),
        }

    def collider_from(self, loc_or_matrix, size):
        """Register an axis-aligned collision box from center tuple/Vector or 4x4 Matrix."""
        if isinstance(loc_or_matrix, Matrix):
            center = loc_or_matrix.translation.copy()
        else:
            center = Vector(loc_or_matrix)
        self.colliders.append((center, Vector(size)))

    # ---- Internal Material & Object Management ----

    def _get_role_mat(self, role):
        role = str(role)
        if role in self.materials:
            return self.materials[role]
        mname = "{}_{}".format(self.id, role)
        mat = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
        mat.use_nodes = True
        hex_val = self.palette.get(role, "#C8966B")
        lin = hex_rgba_lin(hex_val, 1.0)
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = lin
            bsdf.inputs["Roughness"].default_value = 0.38
            if role in EMISSIVE_ROLES:
                bsdf.inputs["Emission Color"].default_value = lin
                bsdf.inputs["Emission Strength"].default_value = 2.0
        mat.diffuse_color = lin
        mat["prop_forge_role"] = role
        self.materials[role] = mat
        return mat

    def _add_bm(self, name, bm, role, matrix=None, bevel=0.0, bevel_segs=2, subsurf=0, solidify=0.0):
        self._part_idx += 1
        me = bpy.data.meshes.new("{}_{}".format(name, self._part_idx))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        self.collection.objects.link(ob)
        ob.matrix_world = matrix if matrix is not None else Matrix.Identity(4)
        me.materials.append(self._get_role_mat(role))
        ob["prop_forge_bone"] = self.current_bone

        if solidify > 0.0:
            smod = ob.modifiers.new("Solidify", "SOLIDIFY")
            smod.thickness = float(solidify)
            smod.offset = 0.0
        if bevel > 0.0:
            bmod = ob.modifiers.new("Bevel", "BEVEL")
            bmod.width = float(bevel)
            bmod.segments = max(1, int(bevel_segs))
            bmod.limit_method = "ANGLE"
            bmod.angle_limit = math.radians(32)
            bmod.use_clamp_overlap = True
        if subsurf > 0:
            ss = ob.modifiers.new("Subsurf", "SUBSURF")
            ss.levels = min(2, int(subsurf))
            ss.render_levels = min(2, int(subsurf))

        self.parts.append(ob)
        return ob

    # ---- Smooth Plush Artisan Primitives ----

    def plush_box(
        self,
        size,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        r_bevel=None,
        subsurf=1,
        rot=(0.0, 0.0, 0.0),
        M=None,
        puff=0.035,
        collide=False,
    ):
        """Silky pillowy rounded-corner Pop-Mart toy body (NEVER sharp industrial boxes!)."""
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        min_d = max(1e-4, min(sx, sy, sz))
        rb = min(min_d * 0.44, float(r_bevel) if r_bevel is not None else min_d * 0.22)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
        if rb > 1e-4:
            bmesh.ops.bevel(
                bm,
                geom=list(bm.edges),
                offset=rb,
                offset_type="OFFSET",
                segments=2 if subsurf <= 1 else 1,
                profile=0.55,
                affect="EDGES",
                clamp_overlap=True,
            )
        if puff > 0.0:
            # Gentle vinyl pillow swell outward from center
            hx, hy, hz = max(1e-4, sx * 0.5), max(1e-4, sy * 0.5), max(1e-4, sz * 0.5)
            for v in bm.verts:
                nx = v.co.x / hx
                ny = v.co.y / hy
                nz = v.co.z / hz
                # Swell faces more than corners
                w_x = (1.0 - ny * ny * 0.5) * (1.0 - nz * nz * 0.5)
                w_y = (1.0 - nx * nx * 0.5) * (1.0 - nz * nz * 0.5)
                w_z = (1.0 - nx * nx * 0.5) * (1.0 - ny * ny * 0.5)
                v.co.x *= 1.0 + puff * w_x
                v.co.y *= 1.0 + puff * w_y
                v.co.z *= 1.0 + puff * w_z
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        ob = self._add_bm("pbox", bm, role, world, subsurf=min(2, max(0, int(subsurf))))
        if collide:
            self.collider_from(world, (sx, sy, sz))
        return ob

    def plush_pill(
        self,
        size,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        rot=(0.0, 0.0, 0.0),
        M=None,
        segs=18,
        collide=False,
    ):
        """Smooth rounded candy-pill / capsule / lozenge (buttons, handles, legs, arches)."""
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        # Build capsule along longest axis using smooth UV sphere stretched cleanly at equator
        dims = [sx, sy, sz]
        axis_i = int(np.argmax(dims))
        r_cross = [dims[j] * 0.5 for j in range(3) if j != axis_i]
        r_end = min(r_cross)
        half_len = max(0.0, dims[axis_i] * 0.5 - r_end)

        bm = bmesh.new()
        u_seg = max(12, int(segs))
        v_seg = max(8, int(segs // 2) * 2)
        bmesh.ops.create_uvsphere(bm, u_segments=u_seg, v_segments=v_seg, radius=1.0)
        for v in bm.verts:
            vx, vy, vz = v.co.x, v.co.y, v.co.z
            if axis_i == 0:
                v.co.x = vx * r_end + (half_len if vx >= 0 else -half_len)
                v.co.y = vy * (sy * 0.5)
                v.co.z = vz * (sz * 0.5)
            elif axis_i == 1:
                v.co.x = vx * (sx * 0.5)
                v.co.y = vy * r_end + (half_len if vy >= 0 else -half_len)
                v.co.z = vz * (sz * 0.5)
            else:
                v.co.x = vx * (sx * 0.5)
                v.co.y = vy * (sy * 0.5)
                v.co.z = vz * r_end + (half_len if vz >= 0 else -half_len)
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        ob = self._add_bm("ppill", bm, role, world)
        if collide:
            self.collider_from(world, (sx, sy, sz))
        return ob

    def plush_cyl(
        self,
        r,
        h,
        loc=(0.0, 0.0, 0.0),
        role="caramel",
        bevel=None,
        segs=28,
        r_top=None,
        axis="Z",
        rot=(0.0, 0.0, 0.0),
        M=None,
        collide=False,
    ):
        """Smooth rounded-cap cylinder / tapered pedestal / drum / coin / wheel."""
        r1 = float(r)
        r2 = float(r_top) if r_top is not None else r1
        hh = float(h)
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=max(10, int(segs)),
            radius1=r1,
            radius2=r2,
            depth=hh,
        )
        bev = min(min(r1, r2) * 0.42, hh * 0.38, float(bevel) if bevel is not None else min(r1, r2, hh) * 0.16)
        if bev > 1e-4:
            cap_edges = [e for e in bm.edges if len(e.link_faces) == 2 and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-4]
            if cap_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=cap_edges,
                    offset=bev,
                    offset_type="OFFSET",
                    segments=3,
                    profile=0.55,
                    affect="EDGES",
                    clamp_overlap=True,
                )
        axis_rot = {
            "Z": Matrix.Identity(4),
            "X": Matrix.Rotation(math.pi * 0.5, 4, "Y"),
            "Y": Matrix.Rotation(math.pi * 0.5, 4, "X"),
        }.get(str(axis).upper(), Matrix.Identity(4))
        world = (M or Matrix.Identity(4)) @ trs(loc, rot) @ axis_rot
        ob = self._add_bm("pcyl", bm, role, world)
        if collide:
            rmax = max(r1, r2) * 2.0
            sz_box = (rmax, rmax, hh) if axis.upper() == "Z" else ((hh, rmax, rmax) if axis.upper() == "X" else (rmax, hh, rmax))
            self.collider_from(world, sz_box)
        return ob

    def plush_sphere(
        self,
        r,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        scale=(1.0, 1.0, 1.0),
        rot=(0.0, 0.0, 0.0),
        u=22,
        v=14,
        M=None,
    ):
        """Smooth high-segment UV sphere for plush domes, capsules, bubbles, pearls."""
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=max(10, int(u)), v_segments=max(6, int(v)), radius=float(r))
        if scale != (1.0, 1.0, 1.0):
            bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        return self._add_bm("psph", bm, role, world)

    def lathe(
        self,
        profile,
        loc=(0.0, 0.0, 0.0),
        role="caramel",
        segs=28,
        rot=(0.0, 0.0, 0.0),
        smooth_profile=0,
        cap_bottom=True,
        cap_top=True,
        M=None,
        collide=False,
    ):
        """Revolve a 2D profile [(radius, z), ...] smoothly 360 deg around Z axis."""
        pts = [(max(0.0, float(r)), float(z)) for (r, z) in profile]
        if smooth_profile > 0:
            pts = _chaikin_open(pts, iters=smooth_profile)
        n_seg = max(10, int(segs))
        bm = bmesh.new()
        rings = []
        for rad, z in pts:
            if rad < 1e-5:
                v = bm.verts.new((0.0, 0.0, z))
                rings.append([v])
            else:
                ring = [
                    bm.verts.new((rad * math.cos(math.tau * i / n_seg), rad * math.sin(math.tau * i / n_seg), z))
                    for i in range(n_seg)
                ]
                rings.append(ring)

        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            if len(r0) == 1 and len(r1) == 1:
                continue
            elif len(r0) == 1:
                for i in range(n_seg):
                    j = (i + 1) % n_seg
                    bm.faces.new((r0[0], r1[j], r1[i]))
            elif len(r1) == 1:
                for i in range(n_seg):
                    j = (i + 1) % n_seg
                    bm.faces.new((r0[i], r0[j], r1[0]))
            else:
                for i in range(n_seg):
                    j = (i + 1) % n_seg
                    bm.faces.new((r0[i], r0[j], r1[j], r1[i]))

        if cap_bottom and len(rings[0]) > 1:
            bm.faces.new(list(reversed(rings[0])))
        if cap_top and len(rings[-1]) > 1:
            bm.faces.new(rings[-1])

        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        ob = self._add_bm("plathe", bm, role, world)
        if collide and pts:
            rmax = max(p[0] for p in pts)
            z0 = min(p[1] for p in pts)
            z1 = max(p[1] for p in pts)
            self.collider_from(world @ Matrix.Translation((0.0, 0.0, (z0 + z1) * 0.5)), (rmax * 2.0, rmax * 2.0, max(0.05, z1 - z0)))
        return ob

    def plush_torus(
        self,
        major_r,
        minor_r,
        loc=(0.0, 0.0, 0.0),
        role="cocoa",
        axis="Z",
        rot=(0.0, 0.0, 0.0),
        seg_major=28,
        seg_minor=14,
        arc_deg=360.0,
        M=None,
    ):
        """Smooth torus ring OR curved elbow/arch when arc_deg < 360 (pipes, hooks, frames!)."""
        R, r = float(major_r), float(minor_r)
        nm = max(8, int(seg_major))
        nn = max(8, int(seg_minor))
        closed = abs(float(arc_deg)) >= 359.5
        arc_rad = math.tau if closed else math.radians(float(arc_deg))
        steps = nm if closed else (nm + 1)

        bm = bmesh.new()
        rings = []
        for i in range(steps):
            u = arc_rad * (i / float(nm))
            cu, su = math.cos(u), math.sin(u)
            ring = []
            for j in range(nn):
                v = math.tau * j / float(nn)
                cv, sv = math.cos(v), math.sin(v)
                rad = R + r * cv
                ring.append(bm.verts.new((rad * cu, rad * su, r * sv)))
            rings.append(ring)

        n_link = nm if closed else nm
        for i in range(n_link):
            r0 = rings[i]
            r1 = rings[(i + 1) % len(rings)]
            for j in range(nn):
                jn = (j + 1) % nn
                bm.faces.new((r0[j], r1[j], r1[jn], r0[jn]))

        if not closed:
            # Smooth hemispherical end caps on open elbows/arches
            for idx_end, flip in ((0, True), (-1, False)):
                ring = rings[idx_end]
                bm.faces.new(list(reversed(ring)) if flip else ring)

        axis_rot = {
            "Z": Matrix.Identity(4),
            "X": Matrix.Rotation(math.pi * 0.5, 4, "Y"),
            "Y": Matrix.Rotation(math.pi * 0.5, 4, "X"),
        }.get(str(axis).upper(), Matrix.Identity(4))
        world = (M or Matrix.Identity(4)) @ trs(loc, rot) @ axis_rot
        return self._add_bm("ptorus", bm, role, world)

    def plush_tube(
        self,
        points,
        radius,
        role="sky",
        segs=14,
        closed=False,
        cap_ends=True,
        smooth_steps=1,
        M=None,
    ):
        """Sweep a smooth circular tube along 3D polyline points=[(x,y,z), ...] with parallel transport."""
        pts = [tuple(float(c) for c in p) for p in points]
        if smooth_steps > 0 and len(pts) >= 3:
            pts = _chaikin_closed(pts, smooth_steps) if closed else _chaikin_open(pts, smooth_steps)
        vecs = [Vector(p) for p in pts]
        n_pts = len(vecs)
        if n_pts < 2:
            return None
        nn = max(6, int(segs))
        r = float(radius)

        # Compute tangents & parallel-transport frames (zero twist!)
        tangents = []
        for i in range(n_pts):
            if closed:
                t = (vecs[(i + 1) % n_pts] - vecs[(i - 1) % n_pts])
            elif i == 0:
                t = vecs[1] - vecs[0]
            elif i == n_pts - 1:
                t = vecs[-1] - vecs[-2]
            else:
                t = vecs[i + 1] - vecs[i - 1]
            tangents.append(t.normalized() if t.length > 1e-6 else Vector((0.0, 0.0, 1.0)))

        t0 = tangents[0]
        ref = Vector((0.0, 0.0, 1.0)) if abs(t0.z) < 0.9 else Vector((1.0, 0.0, 0.0))
        norm = t0.cross(ref).normalized()
        binorm = t0.cross(norm).normalized()

        bm = bmesh.new()
        rings = []
        for i in range(n_pts):
            if i > 0:
                q = tangents[i - 1].rotation_difference(tangents[i])
                norm = (q @ norm).normalized()
                binorm = tangents[i].cross(norm).normalized()
            c = vecs[i]
            ring = []
            for j in range(nn):
                a = math.tau * j / float(nn)
                p = c + (norm * math.cos(a) + binorm * math.sin(a)) * r
                ring.append(bm.verts.new(p))
            rings.append(ring)

        n_seg = n_pts if closed else (n_pts - 1)
        for i in range(n_seg):
            r0 = rings[i]
            r1 = rings[(i + 1) % n_pts]
            for j in range(nn):
                jn = (j + 1) % nn
                bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))

        if not closed and cap_ends:
            # Smooth rounded dome end caps
            c0 = bm.verts.new(vecs[0] - tangents[0] * (r * 0.72))
            c1 = bm.verts.new(vecs[-1] + tangents[-1] * (r * 0.72))
            for j in range(nn):
                jn = (j + 1) % nn
                bm.faces.new((c0, rings[0][jn], rings[0][j]))
                bm.faces.new((c1, rings[-1][j], rings[-1][jn]))

        world = M or Matrix.Identity(4)
        return self._add_bm("ptube", bm, role, world)

    def plush_extrude(
        self,
        pts_2d,
        depth,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        bevel=0.018,
        bevel_segs=3,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """Extrude a 2D silhouette [(x, z), ...] along Y (-depth/2..+depth/2) with silky rounded bevel."""
        bm = bmesh.new()
        hd = float(depth) * 0.5
        front = [bm.verts.new((float(x), -hd, float(z))) for (x, z) in pts_2d]
        back = [bm.verts.new((float(x), hd, float(z))) for (x, z) in pts_2d]
        bm.faces.new(front)
        bm.faces.new(list(reversed(back)))
        n = len(front)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((front[i], back[i], back[j], front[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bev = min(hd * 0.85, float(bevel))
        if bev > 1e-4:
            cap_edges = [e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-4]
            if cap_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=cap_edges,
                    offset=bev,
                    offset_type="OFFSET",
                    segments=max(1, int(bevel_segs)),
                    profile=0.55,
                    affect="EDGES",
                    clamp_overlap=True,
                )
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        return self._add_bm("pext", bm, role, world)

    def plush_frame(
        self,
        w,
        h,
        depth=0.05,
        thickness=0.032,
        loc=(0.0, 0.0, 0.0),
        role="cocoa",
        r_corner=None,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """Smooth rounded-pill .bbu-frame hollow border ring in XZ plane facing -Y."""
        rc = float(r_corner) if r_corner is not None else min(w, h) * 0.16
        pts2 = plush_rounded_rect_pts(w, h, rc, segs_corner=5)
        pts3 = [(x, 0.0, z) for (x, z) in pts2]
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Sweep rounded elliptical cross-section with thickness & depth
        ob = self.plush_tube(pts3, radius=float(thickness) * 0.5, role=role, segs=12, closed=True, smooth_steps=0, M=world)
        if ob and depth > 0.0 and abs(depth - thickness) > 1e-3:
            sy = float(depth) / max(1e-4, float(thickness))
            # Scale local Y depth of frame smoothly
            for v in ob.data.vertices:
                v.co.y *= sy
            ob.data.update()
        return ob

    def plush_cloud(
        self,
        pts_r,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        smooth_iters=3,
        scale=(1.0, 1.0, 1.0),
        rot=(0.0, 0.0, 0.0),
        flat_bottom=True,
        squash_z=0.78,
        M=None,
    ):
        """Smooth silky puffy Pop-Mart studio cloud cushion from [(x, y, z, r), ...]."""
        world = (M or Matrix.Identity(4)) @ trs(loc, rot, scale)
        if not pts_r:
            return None
        z_floor = min(p[2] - p[3] * squash_z for p in pts_r)
        z_cut = z_floor + min(p[3] for p in pts_r) * 0.22
        u_seg = 14 if smooth_iters >= 2 else 12
        v_seg = 10 if smooth_iters >= 2 else 8

        bm = bmesh.new()
        for px, py, pz, pr in pts_r:
            sub = bmesh.new()
            bmesh.ops.create_uvsphere(sub, u_segments=u_seg, v_segments=v_seg, radius=float(pr))
            bmesh.ops.scale(sub, vec=(1.05, 0.96, float(squash_z)), verts=sub.verts)
            bmesh.ops.translate(sub, vec=(float(px), float(py), float(pz)), verts=sub.verts)
            if flat_bottom:
                for v in sub.verts:
                    if v.co.z < z_cut:
                        # Soft cosine pillow cushion flattening at bottom
                        v.co.z = z_cut - (z_cut - v.co.z) * 0.18
            # Copy sub into combined cloud bmesh
            me_tmp = bpy.data.meshes.new("_ks_cld_tmp")
            sub.to_mesh(me_tmp)
            sub.free()
            bm.from_mesh(me_tmp)
            bpy.data.meshes.remove(me_tmp)
        return self._add_bm("pcloud", bm, role, world)

    def plush_cloud_pillow(
        self,
        w,
        d,
        h=0.20,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        puffs=10,
        flat_bottom=True,
        M=None,
    ):
        """Ready-made lush oval/rectangular studio cloud cushion base of size (w, d, h)."""
        hw, hd = float(w) * 0.5, float(d) * 0.5
        base_r = max(0.08, float(h) * 0.72)
        n = max(6, int(puffs))
        pts = [(0.0, 0.0, base_r * 0.45, max(base_r * 1.15, min(hw, hd) * 0.62))]
        for i in range(n):
            a = math.tau * i / float(n)
            sw = 1.0 + 0.16 * math.cos(i * 2.0)
            rx = max(0.02, hw - base_r * 0.55) * math.cos(a)
            ry = max(0.02, hd - base_r * 0.55) * math.sin(a)
            pr = base_r * (0.86 + 0.14 * (1 if i % 2 == 0 else -1)) * sw
            pz = base_r * (0.48 + 0.10 * (1 if i % 2 == 0 else 0))
            pts.append((rx, ry, pz, pr))
        return self.plush_cloud(pts, loc=loc, role=role, flat_bottom=flat_bottom, squash_z=0.76, M=M)

    def plush_cloud_ring(
        self,
        radius,
        z=0.0,
        puff_r=0.14,
        n_puffs=12,
        role="cream",
        flat_bottom=False,
        M=None,
    ):
        """360-degree scalloped fluffy cloud ring (pedestal collar, floating halo, awning cloud)."""
        n = max(6, int(n_puffs))
        pts = []
        for i in range(n):
            a = math.tau * i / float(n)
            sw = 1.08 if i % 2 == 0 else 0.92
            dz = puff_r * (0.08 if i % 2 == 0 else -0.04)
            pts.append((float(radius) * math.cos(a), float(radius) * math.sin(a), float(z) + dz, float(puff_r) * sw))
        return self.plush_cloud(pts, role=role, flat_bottom=flat_bottom, squash_z=0.80, M=M)

    def plush_star(
        self,
        loc,
        size,
        role="gold",
        thick=None,
        points=5,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
    ):
        """Plump pillowy rounded 5-pointed Pop-Mart star (Kirby / Billie School style!)."""
        s = float(size)
        th = float(thick) if thick is not None else s * 0.44
        n_pts = max(4, int(points))
        r_out = s
        r_in = s * (0.48 if n_pts == 5 else 0.40)

        # Build smooth rounded-tip star perimeter using Chaikin subdivision on 2*n_pts vertices
        raw = []
        for i in range(n_pts * 2):
            a = math.pi * 0.5 + math.pi * i / float(n_pts)
            r = r_out if i % 2 == 0 else r_in
            raw.append((r * math.cos(a), r * math.sin(a)))
        ring_pts = _chaikin_closed(raw, iters=2)
        m = len(ring_pts)

        bm = bmesh.new()
        # 3 concentric pillow rings (outer equator, mid domed front/back, center apex front/back)
        eq = [bm.verts.new((x, 0.0, z)) for (x, z) in ring_pts]
        mid_f = [bm.verts.new((x * 0.62, -th * 0.40, z * 0.62)) for (x, z) in ring_pts]
        mid_b = [bm.verts.new((x * 0.62, th * 0.40, z * 0.62)) for (x, z) in ring_pts]
        apex_f = bm.verts.new((0.0, -th * 0.52, 0.0))
        apex_b = bm.verts.new((0.0, th * 0.52, 0.0))

        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((eq[i], eq[j], mid_f[j], mid_f[i]))
            bm.faces.new((mid_f[i], mid_f[j], apex_f))
            bm.faces.new((eq[j], eq[i], mid_b[i], mid_b[j]))
            bm.faces.new((mid_b[j], mid_b[i], apex_b))

        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0, 0, 0), rot)
        return self._add_bm("pstar", bm, role, world)

    def plush_heart(
        self,
        loc,
        size,
        role="pink",
        thick=None,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
    ):
        """Plump pillowy 3D heart charm."""
        s = float(size)
        th = float(thick) if thick is not None else s * 0.48
        m = 28
        ring_pts = []
        for i in range(m):
            t = math.tau * i / float(m)
            x = 16.0 * (math.sin(t) ** 3)
            z = 13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t)
            ring_pts.append((x * s / 17.0, (z + 1.5) * s / 17.0))

        bm = bmesh.new()
        eq = [bm.verts.new((x, 0.0, z)) for (x, z) in ring_pts]
        mid_f = [bm.verts.new((x * 0.58, -th * 0.42, z * 0.58)) for (x, z) in ring_pts]
        mid_b = [bm.verts.new((x * 0.58, th * 0.42, z * 0.58)) for (x, z) in ring_pts]
        apex_f = bm.verts.new((0.0, -th * 0.54, s * 0.06))
        apex_b = bm.verts.new((0.0, th * 0.54, s * 0.06))
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((eq[i], eq[j], mid_f[j], mid_f[i]))
            bm.faces.new((mid_f[i], mid_f[j], apex_f))
            bm.faces.new((eq[j], eq[i], mid_b[i], mid_b[j]))
            bm.faces.new((mid_b[j], mid_b[i], apex_b))

        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0, 0, 0), rot)
        return self._add_bm("pheart", bm, role, world)

    def plush_lightning(
        self,
        loc,
        size,
        role="gold",
        thick=None,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
    ):
        """Chunky rounded kawaii comic lightning bolt badge (for powerbox!)."""
        s = float(size)
        th = float(thick) if thick is not None else s * 0.28
        raw = [
            (0.20 * s, 1.00 * s),
            (-0.56 * s, 0.04 * s),
            (-0.04 * s, 0.04 * s),
            (-0.24 * s, -1.00 * s),
            (0.58 * s, -0.04 * s),
            (0.06 * s, -0.04 * s),
        ]
        pts = _chaikin_closed(raw, iters=1)
        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0, 0, 0), rot)
        return self.plush_extrude(pts, depth=th, role=role, bevel=th * 0.32, bevel_segs=2, M=world)

    def cafe_awning(
        self,
        w,
        d,
        h,
        loc=(0.0, 0.0, 0.0),
        stripe_role="caramel",
        alt_role="cream",
        trim_role="cocoa",
        scallops=6,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """Adorable Billie School scalloped café awning with curved plump alternating stripes!

        Local coordinates: centered in X, back edge at y=+d/2, front scalloped overhang at y=-d/2,
        top back at z=+h/2, front eave at z=-h/2 (with plump scallops hanging slightly below).
        """
        ww, dd, hh = float(w), float(d), float(h)
        n = max(3, int(scallops))
        # Normalize stripe_role if user passed "stripe_caramel" -> use base color + cream alternating 3D ribs!
        if stripe_role in STRIPE_ROLES:
            col_role_a = stripe_role.replace("stripe_", "")
            col_role_b = alt_role
        else:
            col_role_a = stripe_role
            col_role_b = alt_role

        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        rib_w = ww / float(n)
        t_thick = max(0.022, min(dd, hh) * 0.14)
        flap_h = max(0.065, hh * 0.36)

        for i in range(n):
            role = col_role_a if (i % 2 == 0) else col_role_b
            x0 = -ww * 0.5 + i * rib_w
            x1 = x0 + rib_w
            xm = (x0 + x1) * 0.5
            # Curved plump rib canopy strip from back-top (+d/2, +h/2) to front-eave (-d/2, -h/2)
            bm = bmesh.new()
            n_u = 5
            n_v = 4
            top_grid = []
            bot_grid = []
            for iu in range(n_u):
                u = iu / float(n_u - 1)  # 0 = back-top, 1 = front-eave
                # Gentle convex café awning curve
                y = dd * 0.5 - dd * u
                z_base = hh * 0.5 - hh * (u ** 1.38) + hh * 0.08 * math.sin(u * math.pi)
                row_t = []
                row_b = []
                for iv in range(n_v):
                    v = iv / float(n_v - 1)  # 0..1 across single rib width
                    x = x0 + rib_w * v
                    # Plump pillowy arch across each stripe rib
                    puff = t_thick * 0.42 * math.sin(v * math.pi)
                    row_t.append(bm.verts.new((x, y, z_base + t_thick * 0.5 + puff)))
                    row_b.append(bm.verts.new((x, y, z_base - t_thick * 0.5)))
                top_grid.append(row_t)
                bot_grid.append(row_b)

            for iu in range(n_u - 1):
                for iv in range(n_v - 1):
                    bm.faces.new((top_grid[iu][iv], top_grid[iu][iv + 1], top_grid[iu + 1][iv + 1], top_grid[iu + 1][iv]))
                    bm.faces.new((bot_grid[iu][iv + 1], bot_grid[iu][iv], bot_grid[iu + 1][iv], bot_grid[iu + 1][iv + 1]))
            # Cap edges of rib
            for iu in range(n_u - 1):
                bm.faces.new((bot_grid[iu][0], top_grid[iu][0], top_grid[iu + 1][0], bot_grid[iu + 1][0]))
                bm.faces.new((top_grid[iu][-1], bot_grid[iu][-1], bot_grid[iu + 1][-1], top_grid[iu + 1][-1]))
            for iv in range(n_v - 1):
                bm.faces.new((bot_grid[0][iv], bot_grid[0][iv + 1], top_grid[0][iv + 1], top_grid[0][iv]))
                bm.faces.new((top_grid[-1][iv], top_grid[-1][iv + 1], bot_grid[-1][iv + 1], bot_grid[-1][iv]))

            self._add_bm("awning_rib", bm, role, world)

            # Seamless rounded hanging scallop valence tucked flush under the front eave
            sc_r = rib_w * 0.50
            sc_z = -hh * 0.5 - flap_h * 0.14
            self.plush_cyl(
                sc_r,
                t_thick * 1.05,
                loc=(xm, -dd * 0.5 + t_thick * 0.36, sc_z),
                role=role,
                bevel=t_thick * 0.32,
                segs=14,
                axis="Y",
                M=world,
            )

        # Cute Espresso-Cocoa rounded top header rod & side trim bars
        if trim_role:
            rod_r = max(0.016, t_thick * 0.62)
            self.plush_pill((ww + rod_r * 2.4, rod_r * 2.2, rod_r * 2.2), (0.0, dd * 0.5, hh * 0.5 + rod_r * 0.35), trim_role, M=world)
            for sx in (-1.0, 1.0):
                pts_side = [
                    (sx * (ww * 0.5 + rod_r * 0.35), dd * 0.5 - dd * (k / 5.0), hh * 0.5 - hh * ((k / 5.0) ** 1.38) + hh * 0.08 * math.sin((k / 5.0) * math.pi))
                    for k in range(6)
                ]
                self.plush_tube(pts_side, rod_r * 0.82, role=trim_role, segs=10, smooth_steps=0, M=world)

    def billie_bear_plush(
        self,
        loc=(0.0, 0.0, 0.0),
        radius=0.26,
        school="brown",
        face_mode="illustrated",
        with_body=False,
        with_cloud=False,
        with_orange=True,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
        detail="high",
    ):
        """HIGH-CRAFT smooth Pop-Mart 3D Chibi Billie School Mascot (brown/pink/skyblue/grey).

        - Smooth Subsurf/UV plush onesie hood with sculpted collar frame & indented ears
        - Cute 3D tangerine orange + sage leaves on brown bear hood (straight from logo.png!)
        - face_mode='illustrated' (default): smooth curved 3D face dome UV-mapped with the
          official 2048px-sourced Billie School chibi face + starry eyes + blush + bangs!
        - face_mode='sculpted': pure 3D sculpted smooth chibi features (zero decal slots!)
        - with_body=True: adds adorable sitting plush onesie body with bowtie/heart & paws!
        - with_cloud=True: cradles mascot in a silky fluffy Milk-Cream cloud pillow!
        """
        r = float(radius)
        sch = str(school).lower()
        if sch not in ("brown", "pink", "skyblue", "grey"):
            sch = "brown"

        pal_map = {
            "brown": ("caramel", "latte", "cocoa_soft", "honey", "pink"),
            "pink": ("pink", "pink_soft", "pink", "pink_soft", "pink"),
            "skyblue": ("sky", "pink_soft", "sky_deep", "sky", "pink"),
            "grey": ("grey", "pink_soft", "cocoa_soft", "honey", "pink"),
        }
        hood_role, ear_in_role, trim_role, bangs_role, blush_role = pal_map[sch]
        u_s = 20 if detail == "high" else 14
        v_s = 14 if detail == "high" else 10
        u_sub = 14 if detail == "high" else 10
        v_sub = 9 if detail == "high" else 7

        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0.0, 0.0, 0.0), rot)

        # 1. Silky Plump Bear/Bunny/Cat Hood Outer Shell (tucked cleanly behind face dome — ZERO clipping!)
        self.plush_sphere(r * 1.06, (0.0, r * 0.20, 0.0), hood_role, scale=(1.08, 0.86, 0.99), u=u_s, v=v_s, M=group)
        # Sculpted sleek plush hood-opening torus collar hugging the chibi face cleanly!
        self.plush_torus(
            r * 0.78,
            r * 0.18,
            loc=(0.0, -r * 0.60, -r * 0.06),
            role=hood_role,
            axis="Y",
            seg_major=u_s,
            seg_minor=10,
            M=group,
        )

        # 2. Signature School Ears (smooth rounded + soft indented inner ear pads!)
        if sch == "brown":
            for sx in (-1.0, 1.0):
                em = group @ trs((sx * r * 0.78, r * 0.02, r * 0.78), (0.0, sx * 0.24, 0.0))
                self.plush_sphere(r * 0.38, (0.0, 0.0, 0.0), trim_role, scale=(1.06, 0.62, 0.96), u=u_sub, v=v_sub, M=em)
                self.plush_sphere(r * 0.24, (0.0, -r * 0.14, 0.0), ear_in_role, scale=(1.00, 0.42, 0.88), u=12, v=8, M=em)
            # Cute Bear Snout Badge on Hood Forehead + tiny Y-nose + brow pips
            self.plush_sphere(r * 0.22, (0.0, -r * 0.68, r * 0.72), trim_role, scale=(1.18, 0.56, 0.88), u=u_sub, v=v_sub, M=group)
            self.plush_sphere(r * 0.075, (0.0, -r * 0.80, r * 0.76), "cocoa", scale=(1.35, 0.55, 0.82), u=10, v=8, M=group)
            for sx in (-1.0, 1.0):
                self.plush_pill((r * 0.16, r * 0.06, r * 0.06), (sx * r * 0.34, -r * 0.64, r * 0.80), trim_role, rot=(0.0, sx * 0.18, 0.0), segs=10, M=group)
            # Iconic Plump Tangerine Orange + Two Sage Green Leaves perched right on top!
            if with_orange:
                self.plush_sphere(r * 0.28, (0.0, -r * 0.02, r * 1.09), "orange", scale=(1.18, 1.08, 0.82), u=u_sub, v=v_sub, M=group)
                for sx in (-1.0, 1.0):
                    self.plush_pill(
                        (r * 0.22, r * 0.10, r * 0.06),
                        (sx * r * 0.10, -r * 0.02, r * 1.32),
                        "sage",
                        rot=(0.0, -sx * 0.22, sx * 0.18),
                        segs=10,
                        M=group,
                    )
        elif sch in ("pink", "skyblue"):
            # Adorable floppy/curved plush bunny ears + soft top pom-pom
            for sx in (-1.0, 1.0):
                em = group @ trs((sx * r * 0.88, 0.0, r * 0.52), (0.0, sx * 0.58, 0.0))
                self.plush_pill((r * 0.54, r * 0.34, r * 1.05), (0.0, 0.0, 0.0), hood_role, segs=16, M=em)
                self.plush_pill((r * 0.30, r * 0.18, r * 0.76), (0.0, -r * 0.11, -r * 0.04), ear_in_role, segs=12, M=em)
            self.plush_sphere(r * 0.30, (0.0, 0.0, r * 1.08), hood_role, scale=(1.12, 0.96, 0.88), u=u_sub, v=v_sub, M=group)
        else:
            # Cute rounded plush grey cat ears
            for sx in (-1.0, 1.0):
                em = group @ trs((sx * r * 0.72, 0.0, r * 0.80), (0.0, sx * 0.28, 0.0))
                self.plush_cyl(r * 0.36, r * 0.56, (0.0, 0.0, 0.0), hood_role, bevel=r * 0.14, r_top=r * 0.16, segs=16, M=em)
                self.plush_cyl(r * 0.22, r * 0.36, (0.0, -r * 0.13, -r * 0.02), ear_in_role, bevel=r * 0.08, r_top=r * 0.08, segs=12, M=em)

        # 3. Smooth 3D Chibi Face Oval (Illustrated Official Texture OR Ultra-Clean Sculpted!)
        face_key = "bear_face_" + sch
        face_img = self.art.get(face_key)
        if face_mode == "illustrated" and face_img and os.path.isfile(face_img):
            # Build smooth convex squircle-mapped 3D chibi face dome nestled cleanly in front of hood shell!
            rx = r * 0.76
            rz = r * 0.73
            ry = r * 0.32
            face_m = group @ Matrix.Translation((0.0, -r * 0.64, -r * 0.06))
            self._add_curved_face_dome(face_img, rx, rz, ry, face_m)
        else:
            # Pure 3D smooth sculpted Pop-Mart face (high-segment, zero lumpy low-poly balls!)
            self.plush_sphere(r * 0.78, (0.0, -r * 0.28, -r * 0.08), "skin", scale=(1.04, 0.82, 0.86), u=u_s, v=v_s, M=group)
            for bx, bz, br in ((-0.38, 0.34, 0.22), (0.0, 0.39, 0.26), (0.38, 0.34, 0.22)):
                self.plush_sphere(r * br, (r * bx, -r * 0.72, r * bz), bangs_role, scale=(1.12, 0.58, 0.86), u=u_sub, v=v_sub, M=group)
            for sx in (-1.0, 1.0):
                ex, ey, ez = sx * r * 0.31, -r * 0.89, -r * 0.08
                self.plush_sphere(r * 0.155, (ex, ey, ez), "cocoa", scale=(0.98, 0.38, 1.12), u=14, v=10, M=group)
                self.plush_sphere(r * 0.055, (ex - sx * r * 0.04, ey - r * 0.052, ez + r * 0.055), "white", scale=(1.0, 0.45, 1.0), u=10, v=6, M=group)
                self.plush_sphere(r * 0.14, (sx * r * 0.49, -r * 0.83, -r * 0.24), blush_role, scale=(1.25, 0.28, 0.68), u=12, v=8, M=group)
            # Cute curved 'w' smile tube
            smile_pts = [
                (-r * 0.11, -r * 0.91, -r * 0.26),
                (-r * 0.055, -r * 0.92, -r * 0.31),
                (0.0, -r * 0.93, -r * 0.27),
                (r * 0.055, -r * 0.92, -r * 0.31),
                (r * 0.11, -r * 0.91, -r * 0.26),
            ]
            self.plush_tube(smile_pts, r * 0.022, role="berry", segs=8, smooth_steps=1, M=group)

        # 4. Optional Adorable Sitting Plush Onesie Body
        if with_body:
            # Chubby pear-shaped torso
            body_prof = [
                (0.0, -r * 1.98),
                (r * 0.52, -r * 1.96),
                (r * 0.72, -r * 1.72),
                (r * 0.66, -r * 1.32),
                (r * 0.46, -r * 0.94),
                (0.0, -r * 0.86),
            ]
            self.lathe(body_prof, role=hood_role, segs=u_sub, smooth_profile=1, M=group)
            # Soft belly patch (cream oval or pink heart)
            if sch == "pink":
                self.plush_heart((0.0, -r * 0.64, -r * 1.46), r * 0.26, role="pink_soft", thick=r * 0.12, M=group)
            else:
                self.plush_sphere(r * 0.42, (0.0, -r * 0.44, -r * 1.48), "latte", scale=(0.94, 0.58, 1.05), u=14, v=10, M=group)
            # Cute cocoa bow tie at neck
            for sx in (-1.0, 1.0):
                self.plush_sphere(r * 0.15, (sx * r * 0.16, -r * 0.54, -r * 0.98), trim_role, scale=(1.25, 0.55, 0.85), rot=(0.0, sx * 0.18, 0.0), u=10, v=8, M=group)
            self.plush_sphere(r * 0.09, (0.0, -r * 0.59, -r * 0.98), trim_role, u=10, v=6, M=group)
            # Cute chubby arms (right arm happily raised waving!)
            for sx, az_rot, z_arm in ((-1.0, 0.48, -1.28), (1.0, -0.78, -1.16)):
                am = group @ trs((sx * r * 0.66, -r * 0.08, r * z_arm), (0.28, az_rot, 0.0))
                self.plush_pill((r * 0.32, r * 0.32, r * 0.64), (0.0, 0.0, 0.0), hood_role, segs=12, M=am)
                self.plush_sphere(r * 0.14, (0.0, -r * 0.02, -r * 0.30 if sx < 0 else r * 0.30), "skin", u=10, v=8, M=am)
            # Cute stubby sitting legs tucked forward
            for sx in (-1.0, 1.0):
                lm = group @ trs((sx * r * 0.36, -r * 0.48, -r * 1.82), (math.pi * 0.46, sx * 0.18, 0.0))
                self.plush_pill((r * 0.34, r * 0.34, r * 0.60), (0.0, 0.0, 0.0), hood_role, segs=12, M=lm)
                self.plush_cyl(r * 0.16, r * 0.08, (0.0, 0.0, -r * 0.28), trim_role, bevel=r * 0.03, segs=12, M=lm)

        # 5. Optional Fluffy Milk-Cream Cloud Cushion Underneath
        if with_cloud:
            z_cl = -r * 2.02 if with_body else -r * 1.02
            cw = r * (2.25 if with_body else 2.10)
            self.plush_cloud_pillow(cw, r * 1.55, h=r * 0.72, loc=(0.0, 0.0, z_cl), role="cream", puffs=8, flat_bottom=True, M=group)

    def _add_curved_face_dome(self, img_path, rx, rz, ry, matrix):
        """Register a smooth convex squircle-mapped 3D chibi face dome for card/atlas material."""
        self.pending_cards.append({
            "kind": "face_dome",
            "image": os.path.abspath(img_path),
            "rx": float(rx),
            "rz": float(rz),
            "ry": float(ry),
            "matrix": matrix.copy(),
            "emissive": False,
            "transparent": False,
            "bone": self.current_bone,
        })

    def decal_card(
        self,
        img_path,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role="cocoa",
        mat_role="cream",
        frame_thick=0.024,
        depth=0.034,
        emissive=False,
        transparent=False,
        double_sided=False,
        corner_r=None,
        M=None,
    ):
        """Place a razor-sharp official logo, mascot portrait, UI screen, or sign banner facing -Y!

        - If frame_role is set (e.g. 'cocoa'): builds a smooth rounded .bbu-frame border + plump backing slab.
        - If frame_role is None: places a clean floating sticker/decal plane directly at loc.
        - double_sided=True puts the artwork cleanly on BOTH front (-Y) and back (+Y) sides.
        """
        if not img_path or not os.path.isfile(img_path):
            self.warnings.append("decal image missing: {}".format(img_path))
            return
        # Determine natural aspect if height is omitted
        if height is None:
            tmp = bpy.data.images.load(img_path, check_existing=True)
            iw, ih = tmp.size[0], tmp.size[1]
            height = float(width) * (float(ih) / max(1.0, float(iw)))
        w, h = float(width), float(height)
        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0.0, 0.0, 0.0), rot)
        cr = float(corner_r) if corner_r is not None else min(w, h) * 0.14

        y_off = 0.0
        if frame_role:
            # Smooth rounded backing slab + tubular cocoa .bbu-frame border!
            d_slab = max(0.016, float(depth))
            pts_slab = plush_rounded_rect_pts(w + frame_thick * 0.5, h + frame_thick * 0.5, cr, segs_corner=5)
            self.plush_extrude(pts_slab, depth=d_slab, role=mat_role, bevel=min(d_slab * 0.35, 0.012), bevel_segs=2, M=world)
            self.plush_frame(w + frame_thick * 0.8, h + frame_thick * 0.8, depth=d_slab * 1.18,
                             thickness=frame_thick, role=frame_role, r_corner=cr * 1.08, M=world)
            y_off = d_slab * 0.5 + 0.0045

        self.pending_cards.append({
            "kind": "quad",
            "image": os.path.abspath(img_path),
            "width": w,
            "height": h,
            "matrix": world @ Matrix.Translation((0.0, -y_off, 0.0)),
            "emissive": bool(emissive),
            "transparent": bool(transparent),
            "bone": self.current_bone,
        })
        if double_sided:
            back_m = world @ Matrix.Translation((0.0, y_off, 0.0)) @ Matrix.Rotation(math.pi, 4, "Z")
            self.pending_cards.append({
                "kind": "quad",
                "image": os.path.abspath(img_path),
                "width": w,
                "height": h,
                "matrix": back_m,
                "emissive": bool(emissive),
                "transparent": bool(transparent),
                "bone": self.current_bone,
            })

    def text_sign(
        self,
        text,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        bg_hex="#FFFBF4",
        border_hex="#3B281E",
        text_hex="#FFFBF4",
        text_outline_hex="#3B281E",
        accent_hex="#C8966B",
        subtitle="",
        striped=True,
        emissive=False,
        frame_role="cocoa",
        double_sided=False,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
    ):
        """Generate a cached crisp billie-ui graphic banner PNG and place it as a framed decal_card."""
        h = float(height) if height is not None else float(width) * 0.5
        sig = "{}|{}|{}|{}|{}|{}|{}|{}".format(
            text, subtitle, bg_hex, border_hex, text_hex, text_outline_hex, accent_hex, int(striped)
        )
        slug = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:16] or "sign"
        hsh = hashlib.md5(sig.encode("utf-8")).hexdigest()[:6]
        tex_w, tex_h = (512, 256) if (float(width) / max(0.01, h)) >= 1.35 else (512, 512)
        out_png = os.path.join(self.art_dir, "custom_{}_{}.png".format(slug, hsh))
        if not os.path.isfile(out_png):
            make_text_banner(
                text, out_png,
                bg_hex=bg_hex,
                border_hex=border_hex,
                text_hex=text_hex,
                text_outline_hex=text_outline_hex,
                accent_hex=accent_hex,
                subtitle=subtitle,
                striped=striped,
                width=tex_w,
                height=tex_h,
                stars=True,
            )
        self.decal_card(
            out_png,
            width=width,
            height=h,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            mat_role="cream",
            emissive=emissive,
            transparent=False,
            double_sided=double_sided,
            M=M,
        )
        return out_png

    # ---- Adorable Ready-Made Kawaii Toy Props & Miniatures ----

    def plush_car(self, loc=(0.0, 0.0, 0.0), scale=1.0, body_role="sky", roof_role="cream", rot=(0.0, 0.0, 0.0), M=None):
        """Chubby Pop-Mart toy beetle car topper (ideal for GARAGE sign!)."""
        s = float(scale)
        cm = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Plump rounded lower body
        self.plush_box((0.52 * s, 0.34 * s, 0.16 * s), (0.0, 0.0, 0.13 * s), body_role, r_bevel=0.065 * s, subsurf=1, puff=0.06, M=cm)
        # Cute domed cabin roof
        self.plush_box((0.30 * s, 0.28 * s, 0.15 * s), (-0.02 * s, 0.0, 0.25 * s), roof_role, r_bevel=0.065 * s, subsurf=1, puff=0.08, M=cm)
        # Cute sky-glass windshield & side windows
        self.plush_box((0.24 * s, 0.29 * s, 0.085 * s), (-0.01 * s, 0.0, 0.255 * s), "glass", r_bevel=0.022 * s, subsurf=0, M=cm)
        # 4 chunky cocoa wheels with golden hubcaps
        for sx in (-0.16, 0.16):
            for sy in (-0.16, 0.16):
                self.plush_cyl(0.082 * s, 0.065 * s, (sx * s, sy * s, 0.082 * s), "cocoa", bevel=0.018 * s, segs=18, axis="Y", M=cm)
                self.plush_cyl(0.042 * s, 0.072 * s, (sx * s, sy * s, 0.082 * s), "gold", bevel=0.010 * s, segs=14, axis="Y", M=cm)
        # Glowing round headlights + cute cream bumper
        for sy in (-0.095, 0.095):
            self.plush_sphere(0.042 * s, (0.255 * s, sy * s, 0.145 * s), "glow", scale=(0.6, 1.0, 1.0), u=12, v=8, M=cm)
            self.plush_sphere(0.030 * s, (-0.255 * s, sy * s, 0.145 * s), "berry", scale=(0.6, 1.0, 1.0), u=10, v=6, M=cm)
        self.plush_pill((0.06 * s, 0.30 * s, 0.055 * s), (0.26 * s, 0.0, 0.085 * s), "cream", segs=12, M=cm)
        self.plush_pill((0.06 * s, 0.30 * s, 0.055 * s), (-0.26 * s, 0.0, 0.085 * s), "cream", segs=12, M=cm)

    def plush_coin(self, loc=(0.0, 0.0, 0.0), radius=0.045, thick=0.014, role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """Chunky rounded sunny-gold collectible coin."""
        return self.plush_cyl(radius, thick, loc=loc, role=role, bevel=thick * 0.32, segs=16, rot=rot, M=M)

    def plush_banknote(self, loc=(0.0, 0.0, 0.0), w=0.14, h=0.068, thick=0.018, role="sage", band_role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """Chunky banded cash bundle / banknote stack."""
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        self.plush_box((w, h, thick), (0.0, 0.0, 0.0), role, r_bevel=min(w, h, thick) * 0.25, subsurf=0, puff=0.02, M=bm_m)
        self.plush_box((w * 0.24, h * 1.05, thick * 1.12), (0.0, 0.0, 0.0), band_role, r_bevel=thick * 0.18, subsurf=0, puff=0.01, M=bm_m)

    def plush_basket(self, loc=(0.0, 0.0, 0.0), size=0.30, body_role="caramel", trim_role="cream", handle_role="cocoa", rot=(0.0, 0.0, 0.0), M=None):
        """Cute chunky café shopping basket with curved handle (for SHOP!)."""
        s = float(size)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Tapered rounded basket body
        self.plush_box((s, s * 0.72, s * 0.56), (0.0, 0.0, s * 0.28), body_role, r_bevel=s * 0.12, subsurf=1, puff=0.05, M=bm_m)
        # Rim collar
        self.plush_frame(s * 1.04, s * 0.76, depth=s * 0.11, thickness=s * 0.10, loc=(0.0, 0.0, s * 0.54), role=trim_role, rot=(math.pi * 0.5, 0.0, 0.0), M=bm_m)
        # Cute curved carry handle arch
        h_pts = [
            (-s * 0.34, 0.0, s * 0.54),
            (-s * 0.30, 0.0, s * 0.86),
            (0.0, 0.0, s * 0.96),
            (s * 0.30, 0.0, s * 0.86),
            (s * 0.34, 0.0, s * 0.54),
        ]
        self.plush_tube(h_pts, s * 0.042, role=handle_role, segs=10, smooth_steps=1, M=bm_m)

    # ---- Baking, Card Auto-Packing, Rigging, Saving & Studio Preview ----

    def _apply_and_join_parts(self):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        rigged = self.animate and len(self.bones) > 1
        for ob in self.parts:
            if ob.modifiers:
                me = bpy.data.meshes.new_from_object(
                    ob.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph
                )
                old = ob.data
                ob.modifiers.clear()
                ob.data = me
                if old.users == 0:
                    bpy.data.meshes.remove(old)
            if rigged:
                bname = ob.get("prop_forge_bone", "root")
                vg = ob.vertex_groups.get(bname) or ob.vertex_groups.new(name=bname)
                if ob.data.vertices:
                    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
        root = self.parts[0]
        with bpy.context.temp_override(
            active_object=root,
            object=root,
            selected_objects=self.parts,
            selected_editable_objects=self.parts,
        ):
            bpy.ops.object.join()
        root.data.transform(root.matrix_world)
        root.matrix_world = Matrix.Identity(4)
        root.name = self.id
        root.data.name = self.id
        for coll in list(root.users_collection):
            coll.objects.unlink(root)
        bpy.context.scene.collection.objects.link(root)
        if self.collection.name in bpy.data.collections:
            bpy.data.collections.remove(self.collection)

        self._clean_mesh_bmesh(root, rigged=rigged, crease_deg=44.0)
        return root

    def _clean_mesh_bmesh(self, ob, rigged=False, crease_deg=44.0):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        if not rigged:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00018)
        bmesh.ops.dissolve_degenerate(bm, dist=0.00012, edges=bm.edges)
        tiny = [f for f in bm.faces if f.calc_area() < 1e-7]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        for f in bm.faces:
            f.smooth = True
        cr = math.radians(crease_deg)
        for e in bm.edges:
            if not e.is_manifold or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > cr):
                e.smooth = False
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()

    def _enforce_budget(self, root, reserve_tris=0):
        """Gently keep geometry strictly within budget if sculptor slightly overshot."""
        max_body = max(500, self.budget - int(reserve_tris))
        cur = tris_count(root.data)
        if cur <= max_body:
            return
        ratio = max(0.35, (max_body * 0.96) / float(cur))
        mod = root.modifiers.new("BudgetCap", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = False
        deps = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(root.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
        old = root.data
        root.modifiers.clear()
        root.data = me
        me.name = self.id
        if old.users == 0:
            bpy.data.meshes.remove(old)
        self._clean_mesh_bmesh(root, rigged=(self.animate and len(self.bones) > 1))

    def _bake_plush_atlas(self, root, out_dir, size=512):
        """Cycles Soft Plush AO + Cozy Satin-Vinyl + Procedural Café Stripe Baker."""
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.cycles.use_denoising = False

        roles = [slot.material.get("prop_forge_role", "caramel") for slot in root.material_slots]
        me = root.data
        # Guarantee single UV layer named "UVMap"
        while len(me.uv_layers) > 1:
            me.uv_layers.remove(me.uv_layers[-1])
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        else:
            me.uv_layers[0].name = "UVMap"
        me.uv_layers.active = me.uv_layers["UVMap"]

        bpy.context.view_layer.objects.active = root
        for ob in bpy.context.view_layer.objects:
            ob.select_set(ob == root)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.010, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")

        color_img = bpy.data.images.new(self.id + "_atlas", size, size, alpha=True)
        color_img.pixels.foreach_set(np.zeros(size * size * 4, dtype=np.float32))

        # Cozy Warm Espresso-Cocoa Crevice AO color (NEVER muddy grey or harsh black!)
        cocoa_ao = hex_rgba_lin("#4A2E1E", 1.0)

        for slot, role in zip(root.material_slots, roles):
            nt = slot.material.node_tree
            nt.nodes.clear()
            out_n = nt.nodes.new("ShaderNodeOutputMaterial")
            emit = nt.nodes.new("ShaderNodeEmission")
            tex_n = nt.nodes.new("ShaderNodeTexImage")
            tex_n.image = color_img
            nt.nodes.active = tex_n

            hex_val = self.palette.get(role, "#C8966B")
            if role in EMISSIVE_ROLES:
                emit.inputs["Color"].default_value = hex_rgba_lin(hex_val, 1.0)
            else:
                sr, sg, sb = hex_rgb(hex_val)
                r0, g0, b0 = srgb_to_linear(sr), srgb_to_linear(sg), srgb_to_linear(sb)

                if role in ("cream", "light", "white", "latte", "skin"):
                    bot = (r0 * 0.88, g0 * 0.83, b0 * 0.78, 1.0)
                    top = (min(1.0, r0 * 1.01), min(1.0, g0 * 1.00), min(1.0, b0 * 0.99), 1.0)
                    rim = (1.0, 0.994, 0.978, 1.0)
                elif role in ("cocoa", "dark"):
                    bot = (r0 * 0.62, g0 * 0.56, b0 * 0.52, 1.0)
                    top = (min(1.0, r0 * 1.42), min(1.0, g0 * 1.36), min(1.0, b0 * 1.30), 1.0)
                    rim = (min(1.0, r0 * 2.2 + 0.04), min(1.0, g0 * 1.9 + 0.03), min(1.0, b0 * 1.7 + 0.02), 1.0)
                elif role in ("gold", "amber", "orange"):
                    bot = (min(1.0, r0 * 0.84), g0 * 0.56, b0 * 0.24, 1.0)
                    top = (1.0, min(1.0, g0 * 1.05 + 0.02), min(1.0, b0 * 1.05 + 0.01), 1.0)
                    rim = (1.0, 0.97, 0.55, 1.0)
                else:
                    # Silky Pop-Mart plush vertical warmth
                    bot = (r0 * 0.76, g0 * 0.70, b0 * 0.66, 1.0)
                    top = (min(1.0, r0 * 1.07 + 0.01), min(1.0, g0 * 1.06 + 0.01), min(1.0, b0 * 1.05 + 0.01), 1.0)
                    rim = (min(1.0, r0 * 1.24 + 0.08), min(1.0, g0 * 1.22 + 0.07), min(1.0, b0 * 1.20 + 0.06), 1.0)

                tc = nt.nodes.new("ShaderNodeTexCoord")
                sep = nt.nodes.new("ShaderNodeSeparateXYZ")
                nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])

                mr_z = nt.nodes.new("ShaderNodeMapRange")
                mr_z.clamp = True
                mr_z.inputs["From Min"].default_value = 0.04
                mr_z.inputs["From Max"].default_value = 0.94
                nt.links.new(sep.outputs["Z"], mr_z.inputs["Value"])

                mix_grad = nt.nodes.new("ShaderNodeMix")
                mix_grad.data_type = "RGBA"
                mix_grad.clamp_result = True
                mix_grad.inputs[6].default_value = bot
                mix_grad.inputs[7].default_value = top
                nt.links.new(mr_z.outputs["Result"], mix_grad.inputs[0])
                base_out = mix_grad.outputs[2]

                # Procedural diagonal stripes for stripe_* roles!
                if role in STRIPE_ROLES:
                    ca_hex, cb_hex = STRIPE_ROLES[role]
                    wave = nt.nodes.new("ShaderNodeTexWave")
                    wave.wave_type = "BANDS"
                    wave.bands_direction = "DIAGONAL"
                    wave.wave_profile = "SAW"
                    wave.inputs["Scale"].default_value = 5.5
                    wave.inputs["Distortion"].default_value = 0.0
                    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
                    mr_st = nt.nodes.new("ShaderNodeMapRange")
                    mr_st.clamp = True
                    mr_st.inputs["From Min"].default_value = 0.46
                    mr_st.inputs["From Max"].default_value = 0.54
                    nt.links.new(wave.outputs["Fac"], mr_st.inputs["Value"])
                    mix_st = nt.nodes.new("ShaderNodeMix")
                    mix_st.data_type = "RGBA"
                    mix_st.clamp_result = True
                    mix_st.inputs[6].default_value = hex_rgba_lin(ca_hex, 1.0)
                    mix_st.inputs[7].default_value = hex_rgba_lin(cb_hex, 1.0)
                    nt.links.new(mr_st.outputs["Result"], mix_st.inputs[0])
                    base_out = mix_st.outputs[2]

                # Creamy soft key-light satin wrap highlight
                geom = nt.nodes.new("ShaderNodeNewGeometry")
                vdot = nt.nodes.new("ShaderNodeVectorMath")
                vdot.operation = "DOT_PRODUCT"
                vdot.inputs[1].default_value = (-0.30, -0.58, 0.75)
                nt.links.new(geom.outputs["Normal"], vdot.inputs[0])

                mr_gloss = nt.nodes.new("ShaderNodeMapRange")
                mr_gloss.clamp = True
                mr_gloss.inputs["From Min"].default_value = 0.55
                mr_gloss.inputs["From Max"].default_value = 0.98
                mr_gloss.inputs["To Min"].default_value = 0.0
                mr_gloss.inputs["To Max"].default_value = 0.17 if role not in ("cocoa", "dark") else 0.12
                nt.links.new(vdot.outputs["Value"], mr_gloss.inputs["Value"])

                mix_gloss = nt.nodes.new("ShaderNodeMix")
                mix_gloss.data_type = "RGBA"
                mix_gloss.clamp_result = True
                mix_gloss.inputs[7].default_value = rim
                nt.links.new(mr_gloss.outputs["Result"], mix_gloss.inputs[0])
                nt.links.new(base_out, mix_gloss.inputs[6])

                # Gentle warm Espresso-Cocoa Ambient Occlusion (cozy studio plush depth!)
                ao_n = nt.nodes.new("ShaderNodeAmbientOcclusion")
                ao_n.samples = 16
                ao_n.inputs["Distance"].default_value = 0.18
                mr_ao = nt.nodes.new("ShaderNodeMapRange")
                mr_ao.clamp = True
                mr_ao.inputs["From Min"].default_value = 0.15
                mr_ao.inputs["From Max"].default_value = 0.88
                mr_ao.inputs["To Min"].default_value = 0.36 if role not in ("cocoa", "dark") else 0.20
                mr_ao.inputs["To Max"].default_value = 0.0
                nt.links.new(ao_n.outputs["AO"], mr_ao.inputs["Value"])

                mix_ao = nt.nodes.new("ShaderNodeMix")
                mix_ao.data_type = "RGBA"
                mix_ao.clamp_result = True
                mix_ao.inputs[7].default_value = cocoa_ao
                nt.links.new(mr_ao.outputs["Result"], mix_ao.inputs[0])
                nt.links.new(mix_gloss.outputs[2], mix_ao.inputs[6])
                nt.links.new(mix_ao.outputs[2], emit.inputs["Color"])

            nt.links.new(emit.outputs["Emission"], out_n.inputs["Surface"])

        scene.render.bake.margin = 16
        bpy.ops.object.bake(type="EMIT", margin=16, use_clear=True)

        # 100% Flood-fill margin dilation into every unbaked background pixel (ZERO black seams!)
        px_buf = np.empty(size * size * 4, dtype=np.float32)
        color_img.pixels.foreach_get(px_buf)
        px = px_buf.reshape((size, size, 4))
        valid = (px[..., 3] > 0.5) & (px[..., :3].max(axis=-1) > 0.002)
        if valid.any() and not valid.all():
            rgb = px[..., :3]
            for _ in range(max(28, size // 6)):
                if valid.all():
                    break
                acc = np.zeros_like(rgb)
                cnt = np.zeros(valid.shape, dtype=np.float32)
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    sr = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                    sv = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
                    if dy == -1:
                        sv[-1, :] = False
                    elif dy == 1:
                        sv[0, :] = False
                    if dx == -1:
                        sv[:, -1] = False
                    elif dx == 1:
                        sv[:, 0] = False
                    m = sv.astype(np.float32)
                    acc += sr * m[..., None]
                    cnt += m
                fill = (~valid) & (cnt > 0)
                if not fill.any():
                    break
                rgb[fill] = acc[fill] / cnt[fill, None]
                valid[fill] = True
            px[..., :3] = rgb
        px[..., 3] = 1.0
        color_img.pixels.foreach_set(px.ravel())
        color_img.alpha_mode = "NONE"

        atlas_path = os.path.join(out_dir, self.id + "_atlas.png")
        color_img.filepath_raw = atlas_path
        color_img.file_format = "PNG"
        color_img.save()

        # Rebuild into clean 1 or 2 game materials (diffuse default_spec.sps + optional emissive.sps)
        old_idx = [p.material_index for p in me.polygons]
        used_idx = set(old_idx)
        has_diff = any(i in used_idx and roles[i] not in EMISSIVE_ROLES for i in range(len(roles)))
        has_emit = any(i in used_idx and roles[i] in EMISSIVE_ROLES for i in range(len(roles)))

        diff_mat = self._new_game_mat(self.id + "_diffuse", color_img, shader="default_spec.sps") if has_diff else None
        emit_mat = self._new_game_mat(self.id + "_emissive", color_img, shader="emissive.sps") if has_emit else None

        me.materials.clear()
        diff_slot = emit_slot = 0
        if diff_mat is not None:
            diff_slot = len(me.materials)
            me.materials.append(diff_mat)
        if emit_mat is not None:
            emit_slot = len(me.materials)
            me.materials.append(emit_mat)

        for poly, oi in zip(me.polygons, old_idx):
            is_em = roles[oi] in EMISSIVE_ROLES
            poly.material_index = emit_slot if (is_em and emit_mat is not None) else diff_slot

        for m in list(bpy.data.materials):
            if m.users == 0:
                bpy.data.materials.remove(m)

        return atlas_path

    def _new_game_mat(self, name, image, shader="default_spec.sps", transparent=False):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        tex.extension = "CLIP" if transparent else "EXTEND"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if transparent:
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
            try:
                mat.blend_method = "BLEND"
            except Exception:
                pass
        bsdf.inputs["Roughness"].default_value = 0.34
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.25
        if shader in ("emissive.sps", "emissive_alpha.sps"):
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 1.6
            mat["prop_forge_emissive_mult"] = 1.6
        elif shader == "default_spec.sps":
            mat["prop_forge_spec_int"] = 0.38
            mat["prop_forge_spec_falloff"] = 38.0
            mat["prop_forge_spec_fresnel"] = 0.82
        mat["prop_forge_shader"] = shader
        return mat

    def _pack_image_group(self, unique_paths, out_png, alpha=True, size=512):
        """Pack multiple card/decal PNGs into a single 512x512 sheet; return {path: (u0, v0, u1, v1)}."""
        n = len(unique_paths)
        cols = 1 if n == 1 else (2 if n <= 4 else 3)
        rows = int(math.ceil(n / float(cols)))
        cell_w = size // cols
        cell_h = size // rows
        pad = 6
        sheet = np.zeros((size, size, 4), dtype=np.float32)
        if not alpha:
            sheet[..., :3] = 0.96
            sheet[..., 3] = 1.0
        uv_rects = {}
        for idx, p in enumerate(unique_paths):
            gx, gy = idx % cols, idx // cols
            cx0, cy0 = gx * cell_w + pad, gy * cell_h + pad
            iw, ih = max(8, cell_w - pad * 2), max(8, cell_h - pad * 2)
            arr = _resize_rgba(_load_rgba_topdown(p), iw, ih)
            if not alpha:
                arr[..., 3] = 1.0
            sheet[cy0:cy0 + ih, cx0:cx0 + iw] = arr
            # Edge-pad 3px around cell to kill mipmap seam bleed between cards
            for k in range(1, min(4, pad)):
                sheet[cy0 - k, cx0:cx0 + iw] = arr[0]
                sheet[cy0 + ih - 1 + k, cx0:cx0 + iw] = arr[-1]
                sheet[cy0:cy0 + ih, cx0 - k] = arr[:, 0]
                sheet[cy0:cy0 + ih, cx0 + iw - 1 + k] = arr[:, -1]
            # Convert top-down pixel rect to OpenGL bottom-up UV rect (u0, v0, u1, v1)
            u0 = cx0 / float(size)
            u1 = (cx0 + iw) / float(size)
            v1 = 1.0 - (cy0 / float(size))
            v0 = 1.0 - ((cy0 + ih) / float(size))
            uv_rects[p] = (u0, v0, u1, v1)
        if alpha:
            sheet = _bleed_rgb(sheet, passes=10)
        _save_rgba_topdown(sheet, out_png, alpha=alpha)
        return uv_rects

    def _build_and_join_cards(self, root, shift, out_dir):
        """Build all decal cards & curved 3D face domes, guaranteeing total prop materials <= 4!"""
        if not self.pending_cards:
            return
        shift_m = Matrix.Translation(shift)
        rigged = self.animate and len(self.bones) > 1
        base_slots = len(root.data.materials)
        avail_slots = max(1, 4 - base_slots)

        # Group cards into buckets: 'emit', 'decal' (transparent), 'card' (opaque)
        buckets = {"emit": [], "decal": [], "card": []}
        for c in self.pending_cards:
            if not os.path.isfile(c["image"]):
                continue
            if c["emissive"]:
                buckets["emit"].append(c)
            elif c["transparent"]:
                buckets["decal"].append(c)
            else:
                buckets["card"].append(c)

        active_keys = [k for k in ("card", "decal", "emit") if buckets[k]]
        # If active buckets exceed remaining slots (max 4 total!), merge opaque 'card' into 'decal' (decal.sps supports alpha=1 cleanly!)
        if len(active_keys) > avail_slots and buckets["card"] and buckets["decal"]:
            buckets["decal"].extend(buckets["card"])
            buckets["card"] = []
            active_keys = [k for k in ("card", "decal", "emit") if buckets[k]]
        if len(active_keys) > avail_slots and buckets["card"] and buckets["emit"]:
            # Rare fallback: pack into decal.sps
            buckets["decal"].extend(buckets["card"])
            buckets["card"] = []
            active_keys = [k for k in ("decal", "emit") if buckets[k]]

        made_objs = []
        # If there is spare slot room and only 2 unique images across 1 bucket, we can still keep them separate or packed
        for bkey in active_keys:
            items = buckets[bkey]
            uniq = []
            for it in items:
                p = os.path.abspath(it["image"])
                if p not in uniq:
                    uniq.append(p)
            is_alpha = (bkey == "decal")
            if bkey == "emit":
                shader = "emissive_alpha.sps" if any(it["transparent"] for it in items) else "emissive.sps"
                is_alpha = (shader == "emissive_alpha.sps")
            elif bkey == "decal":
                shader = "decal.sps"
            else:
                shader = "default_spec.sps"

            if len(uniq) == 1:
                img_path = uniq[0]
                uv_map = {img_path: (0.0, 0.0, 1.0, 1.0)}
            else:
                sheet_path = os.path.join(out_dir, "{}_{}.png".format(self.id, bkey))
                uv_map = self._pack_image_group(uniq, sheet_path, alpha=is_alpha, size=512)
                img_path = sheet_path

            bl_img = bpy.data.images.load(img_path, check_existing=True)
            mat = self._new_game_mat("{}_{}".format(self.id, bkey), bl_img, shader=shader, transparent=is_alpha)

            for idx, it in enumerate(items):
                u0, v0, u1, v1 = uv_map[os.path.abspath(it["image"])]
                bm = bmesh.new()
                uv_layer = bm.loops.layers.uv.new("UVMap")
                if it["kind"] == "face_dome":
                    # Smooth 10x10 squircle-to-disc convex 3D chibi face dome!
                    n_g = 10
                    rx, rz, ry = it["rx"], it["rz"], it["ry"]
                    grid_v = []
                    grid_uv = []
                    for iz in range(n_g + 1):
                        nz = -1.0 + 2.0 * iz / float(n_g)
                        row_v = []
                        row_uv = []
                        for ix in range(n_g + 1):
                            nx = -1.0 + 2.0 * ix / float(n_g)
                            px = nx * math.sqrt(max(0.0, 1.0 - 0.5 * nz * nz))
                            pz = nz * math.sqrt(max(0.0, 1.0 - 0.5 * nx * nx))
                            r2 = min(1.0, px * px + pz * pz)
                            y = -ry * math.sqrt(max(0.0, 1.0 - 0.86 * r2))
                            row_v.append(bm.verts.new((px * rx, y, pz * rz)))
                            uu = u0 + (u1 - u0) * (0.5 + 0.48 * px)
                            vv = v0 + (v1 - v0) * (0.5 + 0.48 * pz)
                            row_uv.append((uu, vv))
                        grid_v.append(row_v)
                        grid_uv.append(row_uv)
                    for iz in range(n_g):
                        for ix in range(n_g):
                            f = bm.faces.new((
                                grid_v[iz][ix],
                                grid_v[iz][ix + 1],
                                grid_v[iz + 1][ix + 1],
                                grid_v[iz + 1][ix],
                            ))
                            f.smooth = True
                            uvs_f = (
                                grid_uv[iz][ix],
                                grid_uv[iz][ix + 1],
                                grid_uv[iz + 1][ix + 1],
                                grid_uv[iz + 1][ix],
                            )
                            for lp, uv_val in zip(f.loops, uvs_f):
                                lp[uv_layer].uv = uv_val
                else:
                    # Crisp front-facing (-Y) quad with upright un-mirrored UVs!
                    hw, hh = it["width"] * 0.5, it["height"] * 0.5
                    v0b = bm.verts.new((-hw, 0.0, -hh))
                    v1b = bm.verts.new((hw, 0.0, -hh))
                    v2b = bm.verts.new((hw, 0.0, hh))
                    v3b = bm.verts.new((-hw, 0.0, hh))
                    f = bm.faces.new((v0b, v1b, v2b, v3b))
                    f.smooth = False
                    for lp, uv_val in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                        lp[uv_layer].uv = uv_val

                me_c = bpy.data.meshes.new("{}_{}_m{}".format(self.id, bkey, idx))
                bm.normal_update()
                bm.to_mesh(me_c)
                bm.free()
                ob_c = bpy.data.objects.new(me_c.name, me_c)
                bpy.context.scene.collection.objects.link(ob_c)
                ob_c.matrix_world = shift_m @ it["matrix"]
                me_c.materials.append(mat)
                if rigged:
                    bname = it.get("bone", "root")
                    vg = ob_c.vertex_groups.get(bname) or ob_c.vertex_groups.new(name=bname)
                    vg.add(list(range(len(me_c.vertices))), 1.0, "REPLACE")
                made_objs.append(ob_c)

        if made_objs:
            objs = [root] + made_objs
            with bpy.context.temp_override(
                active_object=root,
                object=root,
                selected_objects=objs,
                selected_editable_objects=objs,
            ):
                bpy.ops.object.join()
            root.data.transform(root.matrix_world)
            root.matrix_world = Matrix.Identity(4)

    def _build_rig_and_action(self, root, shift):
        if not (self.animate and self.anim_config and len(self.bones) > 1):
            return None
        fps = int(self.anim_config.get("fps", 30))
        frames = int(self.anim_config.get("frames", 121))
        tracks = self.anim_config.get("tracks", {})

        # Topological sort: root first, parents before children
        ordered = ["root"]
        remaining = [k for k in self.bones if k != "root"]
        while remaining:
            progressed = False
            for k in list(remaining):
                parent = self.bones[k].get("parent") or "root"
                if parent in ordered:
                    ordered.append(k)
                    remaining.remove(k)
                    progressed = True
            if not progressed:
                ordered.extend(remaining)
                break

        arm_data = bpy.data.armatures.new(self.id + "_rig")
        rig = bpy.data.objects.new(self.id + "_rig", arm_data)
        bpy.context.scene.collection.objects.link(rig)
        rig.location = (0.0, 0.0, 0.0)

        bpy.context.view_layer.objects.active = rig
        for ob in bpy.context.view_layer.objects:
            ob.select_set(ob == rig)
        bpy.ops.object.mode_set(mode="EDIT")
        eb_map = {}
        for bname in ordered:
            info = self.bones[bname]
            eb = arm_data.edit_bones.new(bname)
            head = Vector((0.0, 0.0, 0.0)) if bname == "root" else (Vector(info["pivot"]) + shift)
            eb.head = head
            eb.tail = head + Vector((0.0, 0.05, 0.0))
            eb.roll = 0.0
            pname = info.get("parent")
            if pname and pname in eb_map:
                eb.parent = eb_map[pname]
            eb_map[bname] = eb
        bpy.ops.object.mode_set(mode="OBJECT")

        # Guarantee every mesh vertex belongs to a valid rig bone group
        valid_names = set(ordered)
        for vg in list(root.vertex_groups):
            if vg.name not in valid_names:
                root.vertex_groups.remove(vg)
        root_vg = root.vertex_groups.get("root") or root.vertex_groups.new(name="root")
        unassigned = [v.index for v in root.data.vertices if not v.groups]
        if unassigned:
            root_vg.add(unassigned, 1.0, "REPLACE")

        mod = root.modifiers.new("prop_forge_rig", "ARMATURE")
        mod.object = rig

        rig.animation_data_create()
        action = bpy.data.actions.new(self.id + "_action")
        rig.animation_data.action = action
        for pb in rig.pose.bones:
            pb.rotation_mode = "QUATERNION"

        scene = bpy.context.scene
        scene.render.fps = fps
        scene.frame_start = 1
        scene.frame_end = frames
        denom = max(1, frames - 1)

        for bname in ordered:
            track = tracks.get(bname)
            d_loc = 'pose.bones["{}"].location'.format(bname)
            d_rot = 'pose.bones["{}"].rotation_quaternion'.format(bname)
            fcs_loc = [action.fcurves.new(d_loc, index=i, action_group=bname) for i in range(3)]
            fcs_rot = [action.fcurves.new(d_rot, index=i, action_group=bname) for i in range(4)]
            loc_vals = [[], [], []]
            rot_vals = [[], [], [], []]
            prev_q = Quaternion((1.0, 0.0, 0.0, 0.0))
            for f in range(frames):
                u = f / float(denom)
                if f == 0:
                    loc, q = Vector((0.0, 0.0, 0.0)), Quaternion((1.0, 0.0, 0.0, 0.0))
                elif track:
                    loc, q = eval_anim_track(track, u)
                else:
                    loc, q = Vector((0.0, 0.0, 0.0)), Quaternion((1.0, 0.0, 0.0, 0.0))
                if prev_q.dot(q) < 0.0:
                    q = -q
                prev_q = q.copy()
                bf = float(f + 1)
                for i in range(3):
                    loc_vals[i].extend((bf, loc[i]))
                for i in range(4):
                    rot_vals[i].extend((bf, q[i]))
            for i in range(3):
                fcs_loc[i].keyframe_points.add(frames)
                fcs_loc[i].keyframe_points.foreach_set("co", loc_vals[i])
                fcs_loc[i].update()
            for i in range(4):
                fcs_rot[i].keyframe_points.add(frames)
                fcs_rot[i].keyframe_points.foreach_set("co", rot_vals[i])
                fcs_rot[i].update()

        scene.frame_set(1)
        return {
            "rig_name": rig.name,
            "action_name": action.name,
            "fps": fps,
            "frames": frames,
            "duration": round((frames - 1) / float(fps), 4),
            "bones": ordered,
            "auto_start": True,
        }

    def _build_colliders(self, root, shift):
        if not self.collision:
            return []
        cols = list(self.colliders)
        if not cols:
            lo, hi = mesh_bbox(root)
            cols = [((lo + hi) * 0.5 - shift, Vector((max(0.12, hi.x - lo.x), max(0.12, hi.y - lo.y), max(0.12, hi.z - lo.z))))]
        coll = bpy.data.collections.new(self.id + "_collision")
        bpy.context.scene.collection.children.link(coll)
        made = []
        for i, (center, size) in enumerate(cols):
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=size, verts=bm.verts)
            me = bpy.data.meshes.new("{}_col_{}".format(self.id, i))
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(me.name, me)
            coll.objects.link(ob)
            ob.location = center + shift
            ob.display_type = "WIRE"
            ob.hide_render = True
            ob["prop_forge_collision"] = "box"
            made.append(ob)
        return made

    def finalize_and_save(self, out_dir, bake_res=512, render_preview=True, preview_samples=32):
        """Join parts, center at z=0 facing -Y, bake soft plush atlas, attach cards, rig, save & render preview."""
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        part_count = len(self.parts)
        if part_count == 0:
            raise RuntimeError("KawaiiBuilder({}) has no parts to finalize".format(self.id))

        root = self._apply_and_join_parts()

        # Estimate reserve tris for pending cards (quad=2 tris, face_dome=288 tris)
        card_tris = sum(288 if c["kind"] == "face_dome" else 2 for c in self.pending_cards)
        self._enforce_budget(root, reserve_tris=card_tris + 20)

        # Normalize origin: centered in X/Y, lowest point at z=0.0
        lo, hi = mesh_bbox(root)
        shift = Vector((-(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5, -lo.z))
        root.data.transform(Matrix.Translation(shift))

        atlas_path = self._bake_plush_atlas(root, out_dir, size=int(bake_res))
        self._build_and_join_cards(root, shift, out_dir)

        # Re-normalize strictly in case cards slightly extended bbox bottom/center
        lo2, hi2 = mesh_bbox(root)
        delta_z = -lo2.z if abs(lo2.z) > 0.005 else 0.0
        if abs(delta_z) > 1e-4:
            root.data.transform(Matrix.Translation((0.0, 0.0, delta_z)))
            shift = shift + Vector((0.0, 0.0, delta_z))

        # Remove any unused material slots (guarantees zero WARN in validate_prop.py)
        used_m = {p.material_index for p in root.data.polygons}
        if len(used_m) < len(root.data.materials):
            remap = {}
            new_mats = []
            for oi, m in enumerate(root.data.materials):
                if oi in used_m and m is not None:
                    remap[oi] = len(new_mats)
                    new_mats.append(m)
            for p in root.data.polygons:
                p.material_index = remap[p.material_index]
            root.data.materials.clear()
            for m in new_mats:
                root.data.materials.append(m)

        anim_meta = self._build_rig_and_action(root, shift)
        colliders = self._build_colliders(root, shift)

        lo, hi = mesh_bbox(root)
        tris = tris_count(root.data)
        if tris > self.budget:
            self.warnings.append("tris {} over budget {}".format(tris, self.budget))

        meta = {
            "id": self.id,
            "archetype": self.archetype,
            "set": self.set_name,
            "style": "kawaii_studio_v11",
            "size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
            "tris": tris,
            "budget": self.budget,
            "parts": part_count,
            "materials": [m.name for m in root.data.materials],
            "shaders": [m.get("prop_forge_shader", "") for m in root.data.materials],
            "texture": os.path.basename(atlas_path),
            "colliders": len(colliders),
            "lod_dist": self.lod_dist,
            "warnings": self.warnings,
        }
        if anim_meta:
            meta["anim"] = anim_meta
        root["prop_forge"] = json.dumps(meta)

        purge_orphans()
        blend_path = os.path.join(out_dir, self.id + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=False)

        if render_preview:
            prev_path = os.path.join(out_dir, self.id + "_preview.png")
            render_studio_preview([root], prev_path, samples=int(preview_samples))

        meta["blend"] = os.path.basename(blend_path)
        print("KAWAII_PROP " + json.dumps(meta), flush=True)
        return meta


# ---------------------------------------------------------------------------
# Bright Warm Pop-Mart Studio Beauty Preview & Unified Lineup Renderer
# ---------------------------------------------------------------------------


def _setup_kawaii_studio(scene, samples, res):
    """Balanced warm cozy Pop-Mart toy studio lighting (rich Milk-Cream & pastel contrast, ZERO blown highlights!)."""
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.eevee.taa_render_samples = samples
        scene.eevee.use_shadows = True
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y = int(res[0]), int(res[1])
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.view_settings.exposure = 0.25
    except Exception:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = -0.20

    world = bpy.data.worlds.new("_ks_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    # Cheerful bright warm latte-cream Pop-Mart studio backdrop (Milk-Cream clouds still pop crisply!)
    bg.inputs["Color"].default_value = hex_rgba_lin("#EFE5D8", 1.0)
    bg.inputs["Strength"].default_value = 0.82
    scene.world = world

    helpers = []
    # Warm Key Sun from front-left-top
    sun_d = bpy.data.lights.new("_ks_key", "SUN")
    sun_d.energy = 2.15
    sun_d.color = (1.0, 0.97, 0.92)
    sun_d.angle = math.radians(14)
    sun = bpy.data.objects.new("_ks_key", sun_d)
    sun.rotation_euler = (math.radians(46), math.radians(10), math.radians(-30))
    scene.collection.objects.link(sun)
    helpers.append(sun)

    # Cozy Blush-Cream Fill Area from front-right
    fill_d = bpy.data.lights.new("_ks_fill", "AREA")
    fill_d.energy = 175.0
    fill_d.size = 6.0
    fill_d.color = (1.0, 0.95, 0.96)
    fill = bpy.data.objects.new("_ks_fill", fill_d)
    fill.location = (4.5, -5.5, 3.8)
    fill.rotation_euler = Vector((4.5, -5.5, 3.8)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(fill)
    helpers.append(fill)

    # Soft Back-Top Rim Light for silky plush silhouette pop
    rim_d = bpy.data.lights.new("_ks_rim", "AREA")
    rim_d.energy = 155.0
    rim_d.size = 5.0
    rim_d.color = (1.0, 0.97, 0.88)
    rim = bpy.data.objects.new("_ks_rim", rim_d)
    rim.location = (-3.0, 4.5, 4.5)
    rim.rotation_euler = Vector((-3.0, 4.5, 4.5)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(rim)
    helpers.append(rim)

    # Warm Soft-Latte studio tabletop floor for crisp soft shadows & bright cream pop!
    gme = bpy.data.meshes.new("_ks_ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60.0)
    bm.to_mesh(gme)
    bm.free()
    ground = bpy.data.objects.new("_ks_ground", gme)
    gmat = bpy.data.materials.new("_ks_ground")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = hex_rgba_lin("#DFD0BE", 1.0)
    gb.inputs["Roughness"].default_value = 0.88
    gme.materials.append(gmat)
    scene.collection.objects.link(ground)
    helpers.append(ground)
    return helpers


def render_studio_preview(objs, path, samples=32, res=(900, 900), direction=(-0.56, -1.0, 0.34), fit=0.92):
    """Render a bright warm Pop-Mart toy studio 3/4 beauty preview PNG."""
    scene = bpy.context.scene
    helpers = _setup_kawaii_studio(scene, samples, res)
    pts = []
    for ob in objs:
        lo, hi = mesh_bbox(ob)
        pts += [lo, hi]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) * 0.5
    radius = max(0.15, (hi - lo).length * 0.5)

    cam_d = bpy.data.cameras.new("_ks_cam")
    cam_d.lens = 55.0
    cam = bpy.data.objects.new("_ks_cam", cam_d)
    scene.collection.objects.link(cam)
    aspect = res[0] / float(res[1])
    fov = 2.0 * math.atan(cam_d.sensor_width * 0.5 / cam_d.lens)
    if aspect < 1.0:
        fov *= aspect
    dist = radius / math.sin(fov * 0.5) * (fit if aspect >= 1.0 else 1.05)
    d = Vector(direction).normalized()
    cam.location = center + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_d.clip_end = dist * 5.0
    scene.camera = cam
    scene.render.filepath = path

    try:
        bpy.ops.render.render(write_still=True)
    except Exception:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = max(16, int(samples))
        bpy.ops.render.render(write_still=True)

    for ob in helpers + [cam]:
        if ob.name in bpy.data.objects:
            bpy.data.objects.remove(ob, do_unlink=True)
    purge_orphans()
    return path


def render_lineup(blend_paths, out_png, samples=48, res=(2100, 1080), rows=2, spacing=0.55):
    """Render all props in a bright warm Pop-Mart showcase studio lineup."""
    clean_scene()
    loaded = []
    for bp in blend_paths:
        stem = os.path.splitext(os.path.basename(bp))[0]
        with bpy.data.libraries.load(bp, link=False) as (src, dst):
            if stem in src.objects:
                dst.objects = [stem]
        if not dst.objects:
            continue
        ob = dst.objects[0]
        bpy.context.scene.collection.objects.link(ob)
        for mod in list(ob.modifiers):
            if mod.type == "ARMATURE":
                ob.modifiers.remove(mod)
        lo, hi = mesh_bbox(ob)
        loaded.append((ob, hi.x - lo.x, hi.y - lo.y, hi.z - lo.z))

    if not loaded:
        raise RuntimeError("render_lineup: no props loaded")

    n_rows = max(1, int(rows))
    per_row = int(math.ceil(len(loaded) / float(n_rows)))
    row_depth = 2.6
    objs = []
    for r_idx in range(n_rows):
        chunk = loaded[r_idx * per_row:(r_idx + 1) * per_row]
        if not chunk:
            continue
        total_w = sum(item[1] for item in chunk) + spacing * max(0, len(chunk) - 1)
        x = -total_w * 0.5
        y = r_idx * row_depth
        z_lift = 0.0
        for ob, w, d, h in chunk:
            ob.location = (x + w * 0.5, y, z_lift)
            x += w + spacing
            objs.append(ob)

    bpy.context.view_layer.update()
    direction = (0.0, -1.0, 0.34 if n_rows > 1 else 0.24)
    return render_studio_preview(objs, out_png, samples=samples, res=res, direction=direction, fit=0.98)


# ---------------------------------------------------------------------------
# Self-Test CLI (verifies art generation, primitives, bake, rig, preview & validate)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys

    art = prepare_billie_art(DEFAULT_ART_DIR, force=("--force-art" in sys.argv))
    print("PREPARED_ART count={} dir={}".format(len(art), DEFAULT_ART_DIR), flush=True)
    if "--selftest" in sys.argv:
        test_out = os.path.join(WORKSPACE_ROOT, "work", "1nfx_prop_billie_v2", "_selftest")
        b = KawaiiBuilder("1nfx_billie_selftest", archetype="kiosk_sign", budget=12000, collision=True, animate=True)
        b.plush_cloud_pillow(1.20, 0.90, h=0.22, loc=(0, 0, 0.0), role="cream")
        b.plush_box((0.92, 0.52, 0.92), (0, 0, 0.58), role="latte", r_bevel=0.10, subsurf=1, collide=True)
        b.cafe_awning(1.06, 0.42, 0.24, loc=(0, -0.34, 1.08), stripe_role="pink", alt_role="cream", trim_role="cocoa", scallops=6)
        b.decal_card(b.art["sign_shop"], 0.72, 0.36, loc=(0, -0.28, 0.62), frame_role="cocoa", mat_role="cream")
        b.decal_card(b.art["logo"], 0.52, 0.26, loc=(0, -0.27, 0.28), frame_role=None, transparent=True)
        b.define_bone("topper", (0.0, 0.0, 1.38))
        with b.use_bone("topper"):
            b.billie_bear_plush((0.0, 0.0, 1.48), radius=0.24, school="brown", face_mode="illustrated", with_body=False, with_cloud=False)
            b.plush_star((-0.34, -0.06, 1.56), 0.10, role="gold")
            b.plush_star((0.34, -0.06, 1.56), 0.10, role="glow")
        b.set_anim(frames=121, fps=30, tracks={"topper": {"kind": "crown_hover", "amp_z": 0.06, "rock_y": 6.0}})
        meta = b.finalize_and_save(test_out, bake_res=512, render_preview=True, preview_samples=24)
        print("SELFTEST_OK", json.dumps(meta), flush=True)
