"""prop-forge V15: Anti-Playdough Crisp Designer-Vinyl Low-Poly Kawaii Studio toolkit for BILLIE SCHOOL FiveM props.

V15 Upgrades (Anti-Playdough Crisp Engine + Re-Sculpted 3D Billie Bear + Detailed Mini Car & Workshop Tools):
  - Global Anti-Playdough Engine:
    * Hard-edge auto-crease tightened (`crease_deg=32.0`) so mechanical bevels, trims, cuffs,
      soles, tool edges, and moldings stay razor-sharp while curved domes stay silky.
    * Designer Satin-Matte Vinyl Shader (`Roughness=0.46`, `Coat Weight=0.12`,
      `prop_forge_spec_int=0.22`, `prop_forge_spec_falloff=64.0`, `prop_forge_spec_fresnel=0.72`).
    * Deeper Crisp Crevice Vertex AO (`Color 1`, `ao_dist=0.22`, `[192..255]`, `mean ~236`,
      `min >= 190` on diffuse body / `255` on emissive & decals).
    * Crisp Anime Chibi Face Sheet (`billie_art_faces.png` `1024x1024`): loads freshly
      generated `billie_face_crisp_v5.png` into the `brown` quadrant (`512x512`) with edge
      harmonization to `#FCEBD9` + subtle unsharp boost.
  - Re-Sculpted Pop-Mart Designer 3D Billie Bear (`billie_bear_plush()` V15):
    * Unified tailored hood shell + crisp dark-espresso inner piping trim (`seg_major=18`),
      cupped sculpted bear ears (outer contour trim + concave recessed cream inner ear),
      authentic hood forehead face (`• ᴥ •`), 6-lobe ribbed tangerine with stem & 2 sharp
      angled leaves, 5 sculpted 3D layered honey hair bangs + 2 white 4-point sparkle clips,
      crisp `7x6` convex face dome, pleated espresso/walnut bow-tie, and tailored onesie body
      (neckline cuff, cream belly placket + 2 gold buttons, cuffed sleeves + waving paw with
      blush pad, adorable bear-face slippers with flat espresso soles, tiny bear tail).
    * Strict low-poly targets: `detail="low"` ~900t head / ~1,450t full body;
      `detail="high"` ~1,090t head / ~1,720t full body.
  - Detailed Designer Mini Sports Car (`plush_car()` V15, ~920 tris) & Sharpened Workshop Tools
    (`craft_hammer`, `craft_screwdriver`, `craft_toolbox`, `craft_tape_dispenser`).

100% compatible with:
  - validate_prop.py (guarantees fail=0 warn=0: <=4 materials, pow2 <=2048 textures,
    origin at floor z=0 centered X/Y, clean UVMap, zero NaN/degenerate/loose/orphans)
  - export_prop.py --format native --max-res 1024 --shared-ytd billie_prop_tex

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
from mathutils.bvhtree import BVHTree
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
FONT_DIR = os.path.join(SKILL_ROOT, "assets", "fonts")
DEFAULT_FONT = os.path.join(FONT_DIR, "TitanOne-Regular.ttf")
WORKSPACE_ROOT = os.path.normpath(os.path.join(SKILL_ROOT, "..", "..", "..", ".."))
THEME_DIR = os.path.join(
    WORKSPACE_ROOT, "resources", "[resources]", "[1nfx]", "1nfx_assetsimg", "theme"
)
SELECT_IMG_DIR = os.path.join(
    WORKSPACE_ROOT, "resources", "[resources]", "[1nfx]", "1nfx_selectschool", "html", "img"
)
DEFAULT_ART_DIR = os.path.join(WORKSPACE_ROOT, "work", "billie_prop_v4", "art")
DEFAULT_ART_RAW_DIR = os.path.join(WORKSPACE_ROOT, "work", "billie_prop_v4", "art_raw")

# ---------------------------------------------------------------------------
# V13 Unified Warm-Brown BILLIE SCHOOL Studio Palette (Master Palette Cells)
# ---------------------------------------------------------------------------

# Ordered canonical solid colors placed into top half of billie_master_pal.png (16x8 = 128 cells of 64x64)
MASTER_SOLID_COLORS = [
    # Row 0: Core Milk-Cream, Latte, Biscuit, Honey, Caramel, Walnut & Espresso
    ("cream", "#FFFBF4"),
    ("latte", "#FAF0E2"),
    ("biscuit", "#F0DEC6"),
    ("honey", "#E5B98A"),
    ("caramel", "#C8966B"),
    ("caramel_deep", "#A67248"),
    ("walnut", "#7C4F32"),
    ("cocoa", "#3B281E"),
    ("espresso", "#2B1B13"),
    ("cocoa_soft", "#6B4834"),
    ("hair_brown", "#8C5A3C"),
    ("skin", "#FCEBD9"),
    ("blush", "#EFA49B"),
    ("white", "#FFFFFF"),
    ("metal_warm", "#D4C4B4"),
    ("yellow_soft", "#FFF0B4"),
    # Row 1: Warm Roasted Chestnut (Redbox), Sunny Gold, Amber, Tangerine & Muted Organic Accents
    ("chestnut", "#A84438"),
    ("chestnut_soft", "#C86454"),
    ("chestnut_deep", "#7E2F26"),
    ("gold", "#FFD147"),
    ("gold_deep", "#D99B26"),
    ("amber", "#F5A623"),
    ("orange", "#FFA34F"),
    ("sage_warm", "#8BB084"),
    ("sage_deep", "#5E8058"),
    ("aqua_cream", "#C6DDE6"),
    ("aqua_deep", "#9AC0D0"),
    # Row 2: V17 Official 4-House Billie Mascot Swatches (Brown Bear, Pink Bunny, Skyblue Puppy, Grey Kitty) & Crisp Mini-Prop Accents
    ("m_brown", "#CFA07A"),
    ("m_brown_hair", "#F0CFA9"),
    ("m_brown_cuff", "#8B6651"),
    ("m_brown_belly", "#F5E2CC"),
    ("m_pink", "#F6C4D3"),
    ("m_pink_in", "#EE94B0"),
    ("m_pink_hair", "#F5B4C8"),
    ("m_pink_cuff", "#FCE2EA"),
    ("m_sky", "#B5D5F5"),
    ("m_sky_in", "#F5B8C8"),
    ("m_sky_hair", "#9EC4F0"),
    ("m_sky_cuff", "#EFF6FD"),
    ("m_sky_red", "#DF554B"),
    ("m_sky_blue", "#3765C4"),
    ("m_grey", "#B9BCC4"),
    ("m_grey_dark", "#787D8A"),
    ("m_grey_belly", "#E5E7EE"),
    ("water_clear", "#8AD1F0"),
    ("water_hi", "#DFF6FF"),
    ("boba_tea", "#D8A676"),
    ("berry_glaze", "#EE8AA6"),
    ("tangerine", "#F5A152"),
    ("leaf_fresh", "#7FC064"),
    ("paw_pink", "#F2A2AA"),
]

SOLID_ROLE_ALIASES = {
    "light": "cream",
    "primary": "caramel",
    "wood": "honey",
    "dark": "cocoa",
    "trim": "walnut",
    "accent": "gold",
    "latte_deep": "biscuit",
    "metal": "metal_warm",
    "glass": "aqua_cream",
    "mint": "sage_warm",
    "mint_soft": "cream",
    "mint_deep": "sage_deep",
    "sage": "sage_warm",
    "redbox": "chestnut",
    "redbox_deep": "chestnut_deep",
    "berry": "chestnut",
    "berry_ink": "cocoa",
    # Harmonized warm-brown fallbacks for legacy V12 4-house role names (ZERO neon/off-tone leaks!)
    "pink": "blush",
    "pink_soft": "latte",
    "pink_mid": "chestnut_soft",
    "pink_deep": "cocoa",
    "hair_pink": "honey",
    "sky": "aqua_cream",
    "sky_soft": "cream",
    "sky_deep": "aqua_deep",
    "navy": "cocoa",
    "hair_navy": "walnut",
    "red_collar": "chestnut",
    "blue_collar": "walnut",
    "grey": "metal_warm",
    "grey_soft": "latte",
    "grey_deep": "walnut",
    "slate": "espresso",
    "hair_grey": "metal_warm",
    "cat": "metal_warm",
    "lavender": "honey",
    "lavender_soft": "biscuit",
    "purple_bag": "walnut",
}

# Bottom half of billie_master_pal.png (8 horizontal strips of 1024x64)
MASTER_STRIPS = [
    ("stripe_caramel", ("#C8966B", "#FFFBF4")),
    ("stripe_walnut", ("#7C4F32", "#FAF0E2")),
    ("stripe_honey", ("#E5B98A", "#FFFBF4")),
    ("stripe_chestnut", ("#A84438", "#FAF0E2")),
    ("stripe_gold", ("#FFD147", "#FFFBF4")),
    ("stripe_cocoa", ("#3B281E", "#FAF0E2")),
    ("stripe_biscuit", ("#F0DEC6", "#FFFBF4")),
    ("halftone_brown", ("#FFFBF4", "#B8845A")),
]

STRIPE_ROLE_ALIASES = {
    "stripe_amber": "stripe_gold",
    "stripe_berry": "stripe_chestnut",
    "stripe_redbox": "stripe_chestnut",
    "stripe_pink": "stripe_honey",
    "stripe_sky": "stripe_biscuit",
    "stripe_mint": "stripe_honey",
    "stripe_sage": "stripe_honey",
    "stripe_grey": "stripe_walnut",
    "halftone_cream": "halftone_brown",
}

# 4x4 grid (16 cells of 64x64) in billie_glow_pal.png (256x256 opaque)
MASTER_GLOW_COLORS = [
    ("glow", "#FFE169"),
    ("glow_amber", "#FFAC33"),
    ("glow_cream", "#FFFDF5"),
    ("glow_honey", "#FFD080"),
    ("glow_chestnut", "#F07864"),
    ("screen", "#FFF8EC"),
    ("glow_gold", "#FFD84D"),
    ("glow_white", "#FFFFFF"),
]

GLOW_ROLE_ALIASES = {
    "glowtrim": "glow_honey",
    "glow_pink": "glow_honey",
    "glow_sky": "glow_cream",
    "glow_mint": "glow_cream",
    "glow_lavender": "glow_honey",
    "glow_red": "glow_chestnut",
}

# Fast lookup tables
SOLID_CELL_INDEX = {name: idx for idx, (name, _) in enumerate(MASTER_SOLID_COLORS)}
STRIP_INDEX = {name: idx for idx, (name, _) in enumerate(MASTER_STRIPS)}
GLOW_CELL_INDEX = {name: idx for idx, (name, _) in enumerate(MASTER_GLOW_COLORS)}

STRIPE_ROLES = {name: pair for name, pair in MASTER_STRIPS if name.startswith("stripe_")}
for _alias, _canon in STRIPE_ROLE_ALIASES.items():
    if _canon in STRIPE_ROLES:
        STRIPE_ROLES[_alias] = STRIPE_ROLES[_canon]

PATTERN_ROLES = set(STRIP_INDEX.keys()) | set(STRIPE_ROLE_ALIASES.keys())
EMISSIVE_ROLES = set(GLOW_CELL_INDEX.keys()) | set(GLOW_ROLE_ALIASES.keys())

# Flat BILLIE_PALETTE dict for backwards compatibility & Blender viewport previews
BILLIE_PALETTE = {}
for _k, _v in MASTER_SOLID_COLORS:
    BILLIE_PALETTE[_k] = _v
for _a, _c in SOLID_ROLE_ALIASES.items():
    BILLIE_PALETTE[_a] = BILLIE_PALETTE[_c]
for _k, _pair in MASTER_STRIPS:
    BILLIE_PALETTE[_k] = _pair[0]
for _a, _c in STRIPE_ROLE_ALIASES.items():
    BILLIE_PALETTE[_a] = BILLIE_PALETTE[_c]
for _k, _v in MASTER_GLOW_COLORS:
    BILLIE_PALETTE[_k] = _v
for _a, _c in GLOW_ROLE_ALIASES.items():
    BILLIE_PALETTE[_a] = BILLIE_PALETTE[_c]


def _quad_uv(qx, qy, pad_px=4, size=1024):
    """OpenGL bottom-up UV rect (u0, v0, u1, v1) for 2x2 quadrant (qx in 0..1, qy in 0..1 top-down)."""
    half = size // 2
    inset = pad_px + 0.5
    x0 = qx * half + inset
    x1 = (qx + 1) * half - inset
    y0 = qy * half + inset
    y1 = (qy + 1) * half - inset
    return (x0 / float(size), 1.0 - y1 / float(size), x1 / float(size), 1.0 - y0 / float(size))


# V13 Fresh Unified Warm-Brown Pop-Art 2x2 Shared Sheet Lookup: key -> (sheet_key, uv_rect)
ART_UV_V4 = {
    # billie_v4_art_a.png (1024x1024)
    "garage": ("art_a", _quad_uv(0, 0, pad_px=4, size=1024)),
    "pound": ("art_a", _quad_uv(1, 0, pad_px=4, size=1024)),
    "parking": ("art_a", _quad_uv(0, 1, pad_px=4, size=1024)),
    "shop": ("art_a", _quad_uv(1, 1, pad_px=4, size=1024)),
    # billie_v4_art_b.png (1024x1024)
    "atm": ("art_b", _quad_uv(0, 0, pad_px=4, size=1024)),
    "crafting": ("art_b", _quad_uv(1, 0, pad_px=4, size=1024)),
    "redbox": ("art_b", _quad_uv(0, 1, pad_px=4, size=1024)),
    "airdrop": ("art_b", _quad_uv(1, 1, pad_px=4, size=1024)),
    # billie_v4_art_c.png (1024x1024)
    "powerbox": ("art_c", _quad_uv(0, 0, pad_px=4, size=1024)),
    "waterpipe": ("art_c", _quad_uv(1, 0, pad_px=4, size=1024)),
    "gachapon": ("art_c", _quad_uv(0, 1, pad_px=4, size=1024)),
    "washmoney": ("art_c", _quad_uv(1, 1, pad_px=4, size=1024)),
    # billie_v4_art_d.png (1024x1024)
    "loot": ("art_d", _quad_uv(0, 0, pad_px=4, size=1024)),
    "crest": ("art_d", _quad_uv(1, 0, pad_px=4, size=1024)),
    "logo_panel": ("art_d", _quad_uv(0, 1, pad_px=4, size=1024)),
    "campus": ("art_d", _quad_uv(1, 1, pad_px=4, size=1024)),
}

# Shared 2x2 UV quadrant lookup (faces + V4 art sheets by sheet key)
ART_UV = {
    "faces": {
        "brown": _quad_uv(0, 0, pad_px=4, size=1024),
        "pink": _quad_uv(1, 0, pad_px=4, size=1024),
        "skyblue": _quad_uv(0, 1, pad_px=4, size=1024),
        "grey": _quad_uv(1, 1, pad_px=4, size=1024),
    },
    "art_a": {k: uv for k, (sk, uv) in ART_UV_V4.items() if sk == "art_a"},
    "art_b": {k: uv for k, (sk, uv) in ART_UV_V4.items() if sk == "art_b"},
    "art_c": {k: uv for k, (sk, uv) in ART_UV_V4.items() if sk == "art_c"},
    "art_d": {k: uv for k, (sk, uv) in ART_UV_V4.items() if sk == "art_d"},
}


def resolve_role(role):
    """Map any role alias to its canonical V13 unified warm-brown role name."""
    r = str(role or "cream").lower()
    if r in SOLID_ROLE_ALIASES:
        return SOLID_ROLE_ALIASES[r]
    if r in STRIPE_ROLE_ALIASES:
        return STRIPE_ROLE_ALIASES[r]
    if r in GLOW_ROLE_ALIASES:
        return GLOW_ROLE_ALIASES[r]
    if r in SOLID_CELL_INDEX or r in STRIP_INDEX or r in GLOW_CELL_INDEX:
        return r
    return "caramel"


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


def plush_rounded_rect_pts(w, h, r, segs_corner=4):
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
    """Load PNG/WEBP via Blender into float32 sRGB numpy array (H, W, 4), row 0 = top."""
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


def _unsharp_rgba(rgba, amount=0.30):
    """Crisp 3x3 unsharp boost on RGB channels without touching alpha."""
    if amount <= 0.0 or rgba.shape[0] < 4 or rgba.shape[1] < 4:
        return rgba
    out = rgba.copy()
    rgb = out[..., :3]
    p = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
    blur = (
        p[0:-2, 0:-2] + 2.0 * p[0:-2, 1:-1] + p[0:-2, 2:]
        + 2.0 * p[1:-1, 0:-2] + 4.0 * p[1:-1, 1:-1] + 2.0 * p[1:-1, 2:]
        + p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + p[2:, 2:]
    ) * (1.0 / 16.0)
    out[..., :3] = np.clip(rgb + (rgb - blur) * float(amount), 0.0, 1.0)
    return out


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
    new_w, new_h = max(1, int(new_w)), max(1, int(new_h))
    if w == new_w and h == new_h:
        return arr.copy()
    cur = arr.astype(np.float32)
    while cur.shape[0] >= new_h * 2 and cur.shape[1] >= new_w * 2:
        ch, cw = cur.shape[0] & ~1, cur.shape[1] & ~1
        c = cur[:ch, :cw]
        a = c[..., 3:4]
        prem = c[..., :3] * a
        prem_d = prem.reshape(ch // 2, 2, cw // 2, 2, 3).mean(axis=(1, 3))
        a_d = a.reshape(ch // 2, 2, cw // 2, 2, 1).mean(axis=(1, 3))
        rgb_d = np.where(
            a_d > 1e-4,
            prem_d / np.maximum(a_d, 1e-4),
            c[..., :3].reshape(ch // 2, 2, cw // 2, 2, 3).mean(axis=(1, 3)),
        )
        cur = np.concatenate((rgb_d, a_d), axis=-1)
    sh, sw, _ = cur.shape
    if sw == new_w and sh == new_h:
        return cur
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


def _edge_pad_rect(sheet, x0, y0, w, h, pad=4):
    """Replicate edge pixels outward by `pad` px around (x0, y0, w, h) inside sheet."""
    sh, sw, _ = sheet.shape
    for k in range(1, int(pad) + 1):
        if y0 - k >= 0:
            sheet[y0 - k, x0:x0 + w] = sheet[y0, x0:x0 + w]
        if y0 + h - 1 + k < sh:
            sheet[y0 + h - 1 + k, x0:x0 + w] = sheet[y0 + h - 1, x0:x0 + w]
    y_a = max(0, y0 - int(pad))
    y_b = min(sh, y0 + h + int(pad))
    for k in range(1, int(pad) + 1):
        if x0 - k >= 0:
            sheet[y_a:y_b, x0 - k] = sheet[y_a:y_b, x0]
        if x0 + w - 1 + k < sw:
            sheet[y_a:y_b, x0 + w - 1 + k] = sheet[y_a:y_b, x0 + w - 1]


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
    t = a_loc / (sector * 0.5)
    r_bound = r_out * (1.0 - t) + r_in * t
    if points == 4:
        r_bound = r_in + (r_out - r_in) * np.power(np.clip(1.0 - t, 0.0, 1.0), 1.65)
    dist = rad - r_bound
    if outline_hex:
        canvas = _paint_sdf(canvas, dist - outline_w, outline_hex, aa=1.4)
    canvas = _paint_sdf(canvas, dist, color_hex, aa=1.4)
    return canvas


def _paint_halftone_corners(canvas, xx, yy, clip_sdf, color_hex, pitch=18.0, max_r=5.2, alpha=0.22):
    """Paint 1nfx_selectschool manga pop-art halftone dot bursts fading from the 4 inner corners."""
    h, w, _ = canvas.shape
    c_dist = np.minimum(
        np.minimum(np.hypot(xx, yy), np.hypot(w - xx, yy)),
        np.minimum(np.hypot(xx, h - yy), np.hypot(w - xx, h - yy)),
    )
    radius_falloff = np.clip(1.0 - c_dist / (min(w, h) * 0.62), 0.0, 1.0)
    inv_s2 = 0.70710678 / float(pitch)
    u = (xx + yy) * inv_s2
    v = (xx - yy) * inv_s2
    du = u - np.round(u)
    dv = v - np.round(v)
    dot_d = np.hypot(du, dv) * float(pitch)
    dot_r = float(max_r) * radius_falloff
    d_dots = np.maximum(dot_d - dot_r, clip_sdf + 3.0)
    d_dots = np.where(radius_falloff > 0.12, d_dots, 99.0)
    return _paint_sdf(canvas, d_dots, color_hex, alpha=alpha, aa=1.2)


def _dilate_alpha_disc(alpha, radius_px):
    """Smooth circular morphological dilation of 2D float alpha mask (H, W)."""
    r = max(1, int(round(float(radius_px))))
    h, w = alpha.shape
    out = alpha.copy()
    r2 = float(radius_px) * float(radius_px)
    offsets = []
    step = 1 if r <= 5 else 2
    for dy in range(-r, r + 1, step):
        for dx in range(-r, r + 1, step):
            d2 = dx * dx + dy * dy
            if 0 < d2 <= r2 + 0.5:
                offsets.append((dy, dx))
    if step > 1:
        for deg in range(0, 360, 12):
            a = math.radians(deg)
            offsets.append((int(round(math.sin(a) * radius_px)), int(round(math.cos(a) * radius_px))))
    for dy, dx in set(offsets):
        sy0, sy1 = max(0, -dy), min(h, h - dy)
        sx0, sx1 = max(0, -dx), min(w, w - dx)
        dy0, dy1 = max(0, dy), min(h, h + dy)
        dx0, dx1 = max(0, dx), min(w, w + dx)
        np.maximum(out[dy0:dy1, dx0:dx1], alpha[sy0:sy1, sx0:sx1], out=out[dy0:dy1, dx0:dx1])
    p = np.pad(out, ((1, 1), (1, 1)), mode="edge")
    out = (
        p[0:-2, 0:-2] + 2.0 * p[0:-2, 1:-1] + p[0:-2, 2:]
        + 2.0 * p[1:-1, 0:-2] + 4.0 * p[1:-1, 1:-1] + 2.0 * p[1:-1, 2:]
        + p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + p[2:, 2:]
    ) * (1.0 / 16.0)
    return np.clip(out * 1.12, 0.0, 1.0)


def _render_text_layer(
    text,
    width,
    height,
    text_hex="#3B281E",
    outline_hex="#FFFBF4",
    outline_px=9.0,
    font_path=None,
    scale_fill=0.80,
    y_offset=0.0,
):
    """Render razor-sharp anti-aliased TTF text + silky circular sticker outline."""
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
# V13 Unified Warm-Brown Shared Master Palette + Crisp 45-deg Stripe Sheet
# ---------------------------------------------------------------------------


def build_master_palette_textures(art_dir, force=False):
    """Generate crisp shared `billie_master_pal.png` (1024x1024) & `billie_glow_pal.png` (256x256)."""
    os.makedirs(art_dir, exist_ok=True)
    pal_path = os.path.join(art_dir, "billie_master_pal.png")
    glow_path = os.path.join(art_dir, "billie_glow_pal.png")

    if force or not os.path.isfile(pal_path):
        size = 1024
        cell = 64
        guard = 12
        inner = cell - 2 * guard
        arr = np.ones((size, size, 4), dtype=np.float32)
        cr, cg, cb = hex_rgb("#FFFBF4")
        arr[..., 0], arr[..., 1], arr[..., 2] = cr, cg, cb

        t_inner = np.linspace(0.0, 1.0, inner, dtype=np.float32)
        t_col = np.empty(cell, dtype=np.float32)
        t_col[:guard] = 0.0
        t_col[guard:guard + inner] = t_inner
        t_col[guard + inner:] = 1.0
        t_2d = t_col[:, None]

        plush_names = {
            "m_brown", "m_brown_cuff", "m_brown_belly", "m_brown_hair",
            "m_pink", "m_pink_in", "m_pink_cuff", "m_pink_hair",
            "m_sky", "m_sky_in", "m_sky_cuff", "m_sky_hair",
            "m_grey", "m_grey_dark", "m_grey_belly",
        }
        py_c, px_c = np.mgrid[0:cell, 0:cell].astype(np.float32)
        # Subtle multi-frequency cozy plush fleece micro-grain (+-3.4% brightness -> tactile softness, zero DXT noise!)
        fleece_grain = (
            0.50 * np.sin(px_c * 1.45 + np.sin(py_c * 0.95) * 1.8)
            + 0.35 * np.cos(py_c * 1.65 - np.cos(px_c * 1.10) * 1.6)
            + 0.15 * np.sin((px_c + py_c) * 2.35)
        ) * 0.034

        for idx, (name, hex_val) in enumerate(MASTER_SOLID_COLORS):
            gx = idx % 16
            gy = idx // 16
            x0, y0 = gx * cell, gy * cell
            r, g, b = hex_rgb(hex_val)
            luma = 0.299 * r + 0.587 * g + 0.114 * b

            if name in ("cream", "white", "latte", "biscuit", "skin"):
                top = (min(1.0, r * 1.012), min(1.0, g * 1.006), min(1.0, b * 1.00))
                bot = (r * 0.945, g * 0.920, b * 0.892)
            elif luma < 0.30:
                top = (min(1.0, r * 1.18 + 0.028), min(1.0, g * 1.15 + 0.022), min(1.0, b * 1.12 + 0.018))
                bot = (r * 0.88, g * 0.86, b * 0.84)
            elif name in ("gold", "gold_deep", "amber", "orange", "yellow_soft"):
                top = (min(1.0, r * 1.045 + 0.02), min(1.0, g * 1.04 + 0.015), min(1.0, b * 1.02 + 0.01))
                bot = (r * 0.92, g * 0.83, b * 0.72)
            elif name in plush_names:
                top = (min(1.0, r * 1.045 + 0.020), min(1.0, g * 1.040 + 0.018), min(1.0, b * 1.035 + 0.016))
                bot = (r * 0.89, g * 0.865, b * 0.850)
            else:
                top = (min(1.0, r * 1.055 + 0.022), min(1.0, g * 1.05 + 0.018), min(1.0, b * 1.04 + 0.016))
                bot = (r * 0.90, g * 0.87, b * 0.845)

            c0 = top[0] * (1.0 - t_2d) + bot[0] * t_2d
            c1 = top[1] * (1.0 - t_2d) + bot[1] * t_2d
            c2 = top[2] * (1.0 - t_2d) + bot[2] * t_2d
            if name in plush_names:
                mod = 1.0 + fleece_grain
                c0 = np.clip(c0 * mod, 0.0, 1.0)
                c1 = np.clip(c1 * mod, 0.0, 1.0)
                c2 = np.clip(c2 * mod, 0.0, 1.0)
            arr[y0:y0 + cell, x0:x0 + cell, 0] = c0
            arr[y0:y0 + cell, x0:x0 + cell, 1] = c1
            arr[y0:y0 + cell, x0:x0 + cell, 2] = c2

        yy_s, xx_s = np.mgrid[0:64, 0:1024].astype(np.float32)
        for s_idx, (sname, (col_a, col_b)) in enumerate(MASTER_STRIPS):
            y0 = 512 + s_idx * 64
            ra, ga, ba = hex_rgb(col_a)
            rb, gb, bb = hex_rgb(col_b)
            if sname == "halftone_brown":
                pitch = 16.0
                fx = (xx_s % pitch) / pitch
                fy = (yy_s % pitch) / pitch
                d0 = np.hypot((fx - 0.25) * pitch, (fy - 0.25) * pitch)
                d1 = np.hypot((fx - 0.75) * pitch, (fy - 0.75) * pitch)
                dist = np.minimum(d0, d1) - 2.85
                m = np.clip(0.5 - dist / 1.15, 0.0, 1.0) * 0.52
                arr[y0:y0 + 64, :, 0] = ra * (1.0 - m) + rb * m
                arr[y0:y0 + 64, :, 1] = ga * (1.0 - m) + gb * m
                arr[y0:y0 + 64, :, 2] = ba * (1.0 - m) + bb * m
            else:
                phase = ((xx_s + yy_s) / 64.0) % 1.0
                edge = 1.6 / 64.0
                m1 = np.clip((phase - 0.5) / edge + 0.5, 0.0, 1.0)
                m2 = np.clip((1.0 - phase) / edge, 0.0, 1.0)
                m = m1 * np.minimum(m2, 1.0)
                near_zero = phase < edge * 0.5
                m = np.where(near_zero, 0.5 - phase / edge, m)
                m = np.clip(m, 0.0, 1.0)
                arr[y0:y0 + 64, :, 0] = ra * (1.0 - m) + rb * m
                arr[y0:y0 + 64, :, 1] = ga * (1.0 - m) + gb * m
                arr[y0:y0 + 64, :, 2] = ba * (1.0 - m) + bb * m

        arr[..., 3] = 1.0
        _save_rgba_topdown(arr, pal_path, alpha=False)

    if force or not os.path.isfile(glow_path):
        gsize = 256
        gcell = 64
        guard = 12
        inner = gcell - 2 * guard
        garr = np.ones((gsize, gsize, 4), dtype=np.float32)
        t_inner = np.linspace(0.0, 1.0, inner, dtype=np.float32)
        t_col = np.empty(gcell, dtype=np.float32)
        t_col[:guard] = 0.0
        t_col[guard:guard + inner] = t_inner
        t_col[guard + inner:] = 1.0
        t_2d = t_col[:, None]
        for idx, (_, hex_val) in enumerate(MASTER_GLOW_COLORS):
            gx = idx % 4
            gy = idx // 4
            x0, y0 = gx * gcell, gy * gcell
            r, g, b = hex_rgb(hex_val)
            top = (min(1.0, r * 1.04 + 0.04), min(1.0, g * 1.04 + 0.04), min(1.0, b * 1.04 + 0.04))
            bot = (r * 0.96, g * 0.96, b * 0.96)
            garr[y0:y0 + gcell, x0:x0 + gcell, 0] = top[0] * (1.0 - t_2d) + bot[0] * t_2d
            garr[y0:y0 + gcell, x0:x0 + gcell, 1] = top[1] * (1.0 - t_2d) + bot[1] * t_2d
            garr[y0:y0 + gcell, x0:x0 + gcell, 2] = top[2] * (1.0 - t_2d) + bot[2] * t_2d
        garr[..., 3] = 1.0
        _save_rgba_topdown(garr, glow_path, alpha=False)

    return pal_path, glow_path


# ---------------------------------------------------------------------------
# Public Art & Texture Generators (V13 Unified Warm-Brown 1024px Pipeline)
# ---------------------------------------------------------------------------


def striped_pbr_tex(out_path, col_a="#C8966B", col_b="#FFFBF4", size=256, stripes=6, angle_deg=45.0):
    """Generate a crisp seamless power-of-two diagonal/vertical café stripe PNG texture."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32) / float(s)
    rad = math.radians(angle_deg)
    if abs(angle_deg - 45.0) < 1.0:
        phase = (xx + yy) * stripes
    elif abs(angle_deg - 90.0) < 1.0:
        phase = yy * stripes
    elif abs(angle_deg) < 1.0:
        phase = xx * stripes
    else:
        phase = (xx * math.cos(rad) + yy * math.sin(rad)) * stripes
    frac = phase - np.floor(phase)
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
    width=1024,
    height=512,
    stars=True,
    halftone=True,
    icon_path=None,
):
    """Generate an ultra-crisp 1024x512 unified warm-brown BILLIE SCHOOL pop-art signboard PNG."""
    w, h = int(width), int(height)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    canvas = np.zeros((h, w, 4), dtype=np.float32)
    br, bg_c, bb = hex_rgb(border_hex)
    canvas[..., 0] = br
    canvas[..., 1] = bg_c
    canvas[..., 2] = bb
    canvas[..., 3] = 1.0

    pad = max(14.0, min(w, h) * 0.048)
    cr = min(w, h) * 0.16
    d_inner = _sdf_rounded_rect(xx, yy, w * 0.5, h * 0.5, w * 0.5 - pad, h * 0.5 - pad, cr)
    canvas = _paint_sdf(canvas, d_inner, bg_hex, aa=1.5)

    # Subtle warm latte bottom tint for studio depth
    grad = np.clip(yy / float(h), 0.0, 1.0)
    lr, lg, lb = hex_rgb("#F4E4CE")
    grad_src = np.zeros_like(canvas)
    grad_src[..., 0], grad_src[..., 1], grad_src[..., 2] = lr, lg, lb
    grad_src[..., 3] = (d_inner < -2.0).astype(np.float32) * (grad * 0.32)
    canvas = _alpha_over(canvas, grad_src)

    if striped:
        stripe_phase = ((xx + yy) / max(32.0, min(w, h) * 0.19)) % 1.0
        sm = ((stripe_phase < 0.44) & (d_inner < -3.0)).astype(np.float32) * 0.14
        ar, ag, ab = hex_rgb(accent_hex)
        src = np.zeros_like(canvas)
        src[..., 0], src[..., 1], src[..., 2], src[..., 3] = ar, ag, ab, sm
        canvas = _alpha_over(canvas, src)

    if halftone:
        canvas = _paint_halftone_corners(
            canvas, xx, yy, d_inner, accent_hex or border_hex,
            pitch=max(14.0, min(w, h) * 0.036),
            max_r=max(4.2, min(w, h) * 0.0115),
            alpha=0.32,
        )

    d_top = _sdf_rounded_rect(xx, yy, w * 0.5, pad + h * 0.11, w * 0.5 - pad * 1.8, h * 0.085, cr * 0.45)
    canvas = _paint_sdf(canvas, np.maximum(d_top, d_inner + 4.0), "#FFFFFF", alpha=0.45, aa=2.0)

    if accent_hex:
        pill_h = h * (0.285 if subtitle else 0.34)
        pill_cy = h * (0.415 if subtitle else 0.50)
        d_pill = _sdf_rounded_rect(xx, yy, w * 0.5, pill_cy, w * 0.415, pill_h, pill_h * 0.85)
        canvas = _paint_sdf(canvas, d_pill - max(6.5, h * 0.019), border_hex, aa=1.6)
        canvas = _paint_sdf(canvas, d_pill, accent_hex, aa=1.6)
        d_pill_gold = np.abs(d_pill + max(7.0, h * 0.016)) - max(2.2, h * 0.0055)
        canvas = _paint_sdf(canvas, d_pill_gold, "#FFD147", alpha=0.65, aa=1.3)
        d_pill_hi = np.maximum(d_pill + 3.0, (yy - pill_cy))
        canvas = _paint_sdf(canvas, d_pill_hi, "#FFFFFF", alpha=0.18, aa=2.2)

    # Crisp double gold-and-espresso inner pinstripe frame
    d_ring = np.abs(d_inner + pad * 0.52) - max(2.6, h * 0.0075)
    canvas = _paint_sdf(canvas, d_ring, "#D99B26", alpha=0.78, aa=1.3)

    if stars:
        s_r = min(w, h) * 0.082
        ow = max(2.8, min(w, h) * 0.0085)
        for sx, sy, pts in (
            (pad + s_r * 1.35, pad + s_r * 1.22, 4),
            (w - pad - s_r * 1.35, pad + s_r * 1.22, 5),
            (pad + s_r * 1.45, h - pad - s_r * 1.18, 5),
            (w - pad - s_r * 1.45, h - pad - s_r * 1.18, 4),
        ):
            canvas = _paint_star_2d(canvas, xx, yy, sx, sy, s_r, s_r * 0.44, pts, "#FFD147", border_hex, ow)

    if icon_path and os.path.isfile(icon_path):
        ic = _load_rgba_topdown(icon_path)
        ic_s = int(min(w, h) * 0.44)
        ic = _resize_rgba(ic, ic_s, ic_s)
        _paste_rgba(canvas, ic, int(pad * 1.1), int((h - ic_s) * 0.5))

    txt_y = 0.085 if subtitle else 0.0
    txt_scale = 0.68 if icon_path else 0.74
    txt_layer = _render_text_layer(
        text,
        w,
        h,
        text_hex=text_hex,
        outline_hex=text_outline_hex,
        outline_px=max(9.0, w * 0.014),
        scale_fill=txt_scale,
        y_offset=txt_y,
    )
    canvas = _alpha_over(canvas, txt_layer)

    if subtitle:
        sub_layer = _render_text_layer(
            subtitle,
            w,
            h,
            text_hex=border_hex,
            outline_hex="#FFFBF4",
            outline_px=max(5.5, w * 0.0075),
            scale_fill=0.46,
            y_offset=-0.275,
        )
        canvas = _alpha_over(canvas, sub_layer)

    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _make_atm_screen(out_path, size=1024):
    """Generate razor-sharp 1024x1024 unified warm caramel-cream-gold BILLIE BANK smiling bear ATM screen."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    canvas = np.ones((s, s, 4), dtype=np.float32)
    r0, g0, b0 = hex_rgb("#FFFBF4")
    r1, g1, b1 = hex_rgb("#F4E4CE")
    grad = yy / float(s)
    canvas[..., 0] = r0 * (1.0 - grad) + r1 * grad
    canvas[..., 1] = g0 * (1.0 - grad) + g1 * grad
    canvas[..., 2] = b0 * (1.0 - grad) + b1 * grad

    d_screen = _sdf_rounded_rect(xx, yy, s * 0.5, s * 0.5, s * 0.46, s * 0.46, s * 0.04)
    canvas = _paint_halftone_corners(canvas, xx, yy, d_screen, "#C8966B", pitch=s * 0.028, max_r=s * 0.0085, alpha=0.34)

    # Warm caramel header pill with thick espresso border & golden pinstripe
    d_hdr = _sdf_rounded_rect(xx, yy, s * 0.5, s * 0.115, s * 0.435, s * 0.072, s * 0.036)
    canvas = _paint_sdf(canvas, d_hdr - s * 0.0095, "#3B281E", aa=1.8)
    canvas = _paint_sdf(canvas, d_hdr, "#C8966B", aa=1.8)
    d_hdr_gold = np.abs(d_hdr + s * 0.011) - s * 0.003
    canvas = _paint_sdf(canvas, d_hdr_gold, "#FFD147", alpha=0.72, aa=1.4)
    d_hdr_hi = np.maximum(d_hdr + 3.0, yy - s * 0.115)
    canvas = _paint_sdf(canvas, d_hdr_hi, "#FFFFFF", alpha=0.22, aa=2.0)

    hdr_txt = _render_text_layer(
        "BILLIE BANK", s, s, text_hex="#FFFBF4", outline_hex="#3B281E",
        outline_px=s * 0.0115, scale_fill=0.58, y_offset=0.385,
    )
    canvas = _alpha_over(canvas, hdr_txt)

    # Cute subtle kawaii bear silhouette medallion framing the smiling bear face
    f_cx, f_cy = s * 0.5, s * 0.445
    for sx in (-1.0, 1.0):
        eax, eay = f_cx + sx * s * 0.215, f_cy - s * 0.145
        d_eo = np.hypot(xx - eax, yy - eay) - s * 0.068
        d_ei = np.hypot(xx - eax, yy - eay) - s * 0.038
        canvas = _paint_sdf(canvas, d_eo - s * 0.008, "#3B281E", aa=1.8)
        canvas = _paint_sdf(canvas, d_eo, "#C8966B", aa=1.8)
        canvas = _paint_sdf(canvas, d_ei, "#FAF0E2", aa=1.8)
    d_head = np.hypot((xx - f_cx) / (s * 0.305), (yy - f_cy) / (s * 0.225)) * (s * 0.26) - s * 0.26
    canvas = _paint_sdf(canvas, d_head - s * 0.009, "#3B281E", aa=2.0)
    canvas = _paint_sdf(canvas, d_head, "#FFF7EC", aa=2.0)

    # Glossy starry espresso eyes + rosy cheeks
    for sx in (-1.0, 1.0):
        ex = s * (0.5 + sx * 0.145)
        ey = s * 0.425
        d_eye = np.hypot((xx - ex) / (s * 0.056), (yy - ey) / (s * 0.068)) * (s * 0.062) - s * 0.062
        canvas = _paint_sdf(canvas, d_eye, "#3B281E", aa=2.0)
        d_iris = np.maximum(d_eye + s * 0.010, -(yy - (ey + s * 0.016)))
        canvas = _paint_sdf(canvas, d_iris, "#C8966B", alpha=0.72, aa=2.0)
        d_hi1 = np.hypot(xx - (ex - sx * s * 0.015), yy - (ey - s * 0.021)) - s * 0.021
        d_hi2 = np.hypot(xx - (ex + sx * s * 0.018), yy - (ey + s * 0.022)) - s * 0.010
        canvas = _paint_sdf(canvas, d_hi1, "#FFFFFF", aa=1.5)
        canvas = _paint_sdf(canvas, d_hi2, "#FFFFFF", aa=1.5)
        bx = s * (0.5 + sx * 0.222)
        by = s * 0.500
        d_blush = np.hypot((xx - bx) / (s * 0.062), (yy - by) / (s * 0.036)) * (s * 0.048) - s * 0.048
        canvas = _paint_sdf(canvas, d_blush, "#EFA49B", alpha=0.86, aa=8.0)

    # Cute oval bear nose + `:3` smiling mouth
    d_nose = np.hypot((xx - s * 0.5) / (s * 0.026), (yy - s * 0.468) / (s * 0.018)) * (s * 0.022) - s * 0.022
    canvas = _paint_sdf(canvas, d_nose, "#3B281E", aa=1.6)
    for sx in (-1.0, 1.0):
        mx = s * (0.5 + sx * 0.038)
        my = s * 0.500
        d_arc = np.abs(np.hypot(xx - mx, yy - my) - s * 0.038) - s * 0.0085
        d_arc = np.where(yy >= my, d_arc, 99.0)
        canvas = _paint_sdf(canvas, d_arc, "#3B281E", aa=1.8)
    d_tng = np.hypot(xx - s * 0.5, yy - s * 0.548) - s * 0.018
    canvas = _paint_sdf(canvas, d_tng, "#EFA49B", aa=1.8)

    # Warm sunny-gold stars with espresso comic ink outlines
    canvas = _paint_star_2d(canvas, xx, yy, s * 0.115, s * 0.34, s * 0.048, s * 0.019, 4, "#FFD147", "#3B281E", s * 0.0055)
    canvas = _paint_star_2d(canvas, xx, yy, s * 0.885, s * 0.34, s * 0.048, s * 0.019, 4, "#FFD147", "#3B281E", s * 0.0055)
    canvas = _paint_star_2d(canvas, xx, yy, s * 0.500, s * 0.235, s * 0.032, s * 0.014, 5, "#FFD147", "#3B281E", s * 0.0045)

    # Warm-sage DEPOSIT & honey-gold WITHDRAW buttons with crisp espresso outlines
    for sx, bcol in ((-0.235, "#8BB084"), (0.235, "#FFD147")):
        bcx, bcy = s * (0.5 + sx), s * 0.79
        d_btn = _sdf_rounded_rect(xx, yy, bcx, bcy, s * 0.205, s * 0.086, s * 0.046)
        canvas = _paint_sdf(canvas, d_btn - s * 0.0095, "#3B281E", aa=1.8)
        canvas = _paint_sdf(canvas, d_btn, bcol, aa=1.8)
        d_hi = np.maximum(d_btn + 3.0, yy - bcy)
        canvas = _paint_sdf(canvas, d_hi, "#FFFFFF", alpha=0.25, aa=2.0)

    shift_px = int(s * 0.235)
    btn_l = _render_text_layer(
        "DEPOSIT", s, s, text_hex="#FFFBF4", outline_hex="#3B281E",
        outline_px=s * 0.0075, scale_fill=0.31, y_offset=-0.29,
    )
    btn_l_s = np.roll(btn_l, -shift_px, axis=1)
    btn_l_s[:, -shift_px:] = 0.0
    canvas = _alpha_over(canvas, btn_l_s)

    btn_r = _render_text_layer(
        "WITHDRAW", s, s, text_hex="#3B281E", outline_hex="#FFFBF4",
        outline_px=s * 0.0070, scale_fill=0.33, y_offset=-0.29,
    )
    btn_r_s = np.roll(btn_r, shift_px, axis=1)
    btn_r_s[:, :shift_px] = 0.0
    canvas = _alpha_over(canvas, btn_r_s)

    # Crisp double espresso + warm gold outer frame
    d_gold_ring = np.abs(_sdf_rounded_rect(xx, yy, s * 0.5, s * 0.5, s * 0.464, s * 0.464, s * 0.040)) - s * 0.004
    canvas = _paint_sdf(canvas, d_gold_ring, "#D99B26", alpha=0.85, aa=1.5)
    d_border = np.abs(_sdf_rounded_rect(xx, yy, s * 0.5, s * 0.5, s * 0.482, s * 0.482, s * 0.048)) - s * 0.014
    canvas = _paint_sdf(canvas, d_border, "#3B281E", aa=1.8)
    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _make_gauge_dial(out_path, size=512):
    """Generate a razor-sharp unified warm caramel-gold-espresso smiling `:3` round pressure gauge dial (512x512)."""
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    cx = cy = s * 0.5
    dx = xx - cx
    dy = yy - cy
    rad = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)

    canvas = np.ones((s, s, 4), dtype=np.float32)
    r0, g0, b0 = hex_rgb("#FFFBF4")
    canvas[..., 0], canvas[..., 1], canvas[..., 2] = r0, g0, b0

    d_soft = rad - s * 0.43
    canvas = _paint_sdf(canvas, d_soft, "#F5E6D2", alpha=0.65, aa=3.0)

    rel = ((ang - math.radians(135.0)) % math.tau) / math.radians(270.0)
    in_arc = (rel >= 0.0) & (rel <= 1.0)
    d_ring = np.abs(rad - s * 0.365) - s * 0.044
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel < 0.45), d_ring, 99.0), "#E5B98A")
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel >= 0.45) & (rel < 0.78), d_ring, 99.0), "#FFD147")
    canvas = _paint_sdf(canvas, np.where(in_arc & (rel >= 0.78), d_ring, 99.0), "#A84438")

    for k in range(11):
        a = math.radians(135.0 + 270.0 * k / 10.0)
        ca, sa = math.cos(a), math.sin(a)
        px0, py0 = cx + ca * s * 0.265, cy + sa * s * 0.265
        px1, py1 = cx + ca * s * 0.34, cy + sa * s * 0.34
        vx, vy = px1 - px0, py1 - py0
        t = np.clip(((xx - px0) * vx + (yy - py0) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
        dt = np.hypot(xx - (px0 + t * vx), yy - (py0 + t * vy)) - (5.5 if k % 5 == 0 else 3.2)
        canvas = _paint_sdf(canvas, dt, "#3B281E")

    for sx in (-1.0, 1.0):
        ex = cx + sx * s * 0.105
        ey = cy + s * 0.145
        canvas = _paint_sdf(canvas, np.hypot(xx - ex, yy - ey) - s * 0.030, "#3B281E")
        canvas = _paint_sdf(canvas, np.hypot(xx - (ex - sx * 5.0), yy - (ey - 6.0)) - s * 0.011, "#FFFFFF")
        canvas = _paint_sdf(canvas, np.hypot(xx - (ex + sx * s * 0.054), yy - (ey + s * 0.032)) - s * 0.030, "#EFA49B", alpha=0.84, aa=4.0)
        mx = cx + sx * s * 0.027
        my = cy + s * 0.175
        d_sm = np.abs(np.hypot(xx - mx, yy - my) - s * 0.027) - s * 0.008
        canvas = _paint_sdf(canvas, np.where(yy >= my, d_sm, 99.0), "#3B281E")

    na = math.radians(-38.0)
    ca, sa = math.cos(na), math.sin(na)
    nx1, ny1 = cx + ca * s * 0.31, cy + sa * s * 0.31
    vx, vy = nx1 - cx, ny1 - cy
    t = np.clip(((xx - cx) * vx + (yy - cy) * vy) / (vx * vx + vy * vy), 0.0, 1.0)
    d_ndl = np.hypot(xx - (cx + t * vx), yy - (cy + t * vy)) - (12.0 * (1.0 - 0.65 * t))
    canvas = _paint_sdf(canvas, d_ndl - 3.2, "#3B281E")
    canvas = _paint_sdf(canvas, d_ndl, "#A84438")
    canvas = _paint_sdf(canvas, rad - s * 0.072, "#3B281E")
    canvas = _paint_sdf(canvas, rad - s * 0.052, "#FFD147")
    canvas = _paint_sdf(canvas, np.abs(rad - s * 0.440) - 4.0, "#D99B26", alpha=0.88)
    canvas = _paint_sdf(canvas, np.abs(rad - s * 0.465) - 11.0, "#3B281E")
    canvas[..., 3] = 1.0
    return _save_rgba_topdown(canvas, out_path, alpha=False)


def _paint_tile_espresso_border(tile, border_px=6, border_hex="#3B281E"):
    """Stamp a razor-sharp solid espresso comic border around a square RGBA tile."""
    h, w, _ = tile.shape
    bp = max(1, int(border_px))
    r, g, b = hex_rgb(border_hex)
    out = tile.copy()
    out[:bp, :, 0], out[:bp, :, 1], out[:bp, :, 2] = r, g, b
    out[-bp:, :, 0], out[-bp:, :, 1], out[-bp:, :, 2] = r, g, b
    out[:, :bp, 0], out[:, :bp, 1], out[:, :bp, 2] = r, g, b
    out[:, -bp:, 0], out[:, -bp:, 1], out[:, -bp:, 2] = r, g, b
    out[..., 3] = 1.0
    return out


def _pack_v4_2x2_sheet(out_path, quad_tiles, border_px=6, pad_px=4):
    """Pack 4 tiles [(qx, qy, arr_rgba), ...] into a 1024x1024 opaque sheet with 6px espresso border & 4px bleed."""
    sheet = np.ones((1024, 1024, 4), dtype=np.float32)
    er, eg, eb = hex_rgb("#3B281E")
    sheet[..., 0], sheet[..., 1], sheet[..., 2] = er, eg, eb
    inner = 512 - 2 * int(pad_px)
    for qx, qy, raw in quad_tiles:
        if raw is None:
            continue
        sub = _unsharp_rgba(_resize_rgba(raw, inner, inner), amount=0.22)
        sub[..., 3] = 1.0
        sub = _paint_tile_espresso_border(sub, border_px=border_px, border_hex="#3B281E")
        x0, y0 = qx * 512 + int(pad_px), qy * 512 + int(pad_px)
        sheet[y0:y0 + inner, x0:x0 + inner] = sub
        _edge_pad_rect(sheet, x0, y0, inner, inner, pad=pad_px)
    sheet[..., 3] = 1.0
    return _save_rgba_topdown(sheet, out_path, alpha=False)


def prepare_billie_art_v4(out_dir=None, raw_dir=None, force=False):
    """Generate & cache V13 unified warm-brown 1024px shared art sheets (a/b/c/d), palettes, UI screens & 14 signs."""
    art_dir = os.path.abspath(out_dir or DEFAULT_ART_DIR)
    src_raw_dir = os.path.abspath(raw_dir or DEFAULT_ART_RAW_DIR)
    os.makedirs(art_dir, exist_ok=True)
    arts = {}

    def _need(path):
        return bool(force or not os.path.isfile(path) or os.path.getsize(path) < 128)

    pal_path, glow_path = build_master_palette_textures(art_dir, force=force)
    arts["master_pal"] = pal_path
    arts["glow_pal"] = glow_path

    # 1. Pack 4 crisp 1024x1024 2x2 V4 art sheets (504x504 inner + 6px espresso border + 4px bleed pad)
    def _load_raw_art(fname):
        p = os.path.join(src_raw_dir, fname)
        return _load_rgba_topdown(p) if os.path.isfile(p) else None

    sheet_specs = [
        ("art_a", "billie_v4_art_a.png", [
            (0, 0, "art_garage.png"),
            (1, 0, "art_pound.png"),
            (0, 1, "art_parking.png"),
            (1, 1, "art_shop.png"),
        ]),
        ("art_b", "billie_v4_art_b.png", [
            (0, 0, "art_atm.png"),
            (1, 0, "art_crafting.png"),
            (0, 1, "art_redbox.png"),
            (1, 1, "art_airdrop.png"),
        ]),
        ("art_c", "billie_v4_art_c.png", [
            (0, 0, "art_powerbox.png"),
            (1, 0, "art_waterpipe.png"),
            (0, 1, "art_gachapon.png"),
            (1, 1, "art_washmoney.png"),
        ]),
    ]
    for skey, sname, items in sheet_specs:
        out_p = os.path.join(art_dir, sname)
        if _need(out_p):
            tiles = [(qx, qy, _load_raw_art(fn)) for (qx, qy, fn) in items]
            _pack_v4_2x2_sheet(out_p, tiles, border_px=6, pad_px=4)
        arts[skey] = out_p

    # Sheet D: loot, crest, logo_panel (from 2000px logo-bg.png), campus (from campus-screenprint.webp)
    art_d_out = os.path.join(art_dir, "billie_v4_art_d.png")
    if _need(art_d_out):
        logo_bg_src = os.path.join(THEME_DIR, "logo-bg.png")
        logo_tile = None
        if os.path.isfile(logo_bg_src):
            raw_lg = _load_rgba_topdown(logo_bg_src)
            lh, lw, _ = raw_lg.shape
            logo_tile = raw_lg[int(lh * 0.03):int(lh * 0.97), int(lw * 0.03):int(lw * 0.97)].copy()

        campus_src = os.path.join(SELECT_IMG_DIR, "campus-screenprint.webp")
        campus_tile = None
        if os.path.isfile(campus_src):
            raw_cp = _load_rgba_topdown(campus_src)
            rh, rw, _ = raw_cp.shape
            can = np.ones((504, 504, 4), dtype=np.float32)
            r0, g0, b0 = hex_rgb("#F7ECDC")
            can[..., 0], can[..., 1], can[..., 2] = r0, g0, b0
            sc = min(472.0 / float(max(1, rw)), 472.0 / float(max(1, rh)))
            tw, th = max(4, int(round(rw * sc))), max(4, int(round(rh * sc)))
            res_cp = _resize_rgba(raw_cp, tw, th)
            res_cp[..., 3] = 1.0
            ox, oy = (504 - tw) // 2, (504 - th) // 2
            can[oy:oy + th, ox:ox + tw] = res_cp
            campus_tile = can

        _pack_v4_2x2_sheet(
            art_d_out,
            [
                (0, 0, _load_raw_art("art_loot.png")),
                (1, 0, _load_raw_art("art_crest.png")),
                (0, 1, logo_tile),
                (1, 1, campus_tile),
            ],
            border_px=6,
            pad_px=4,
        )
    arts["art_d"] = art_d_out

    # 2. billie_art_faces.png (1024x1024 opaque — V15 razor-sharp 512x512 anime chibi face in brown (0,0)!)
    faces_out = os.path.join(art_dir, "billie_art_faces.png")
    if _need(faces_out):
        sheet = np.ones((1024, 1024, 4), dtype=np.float32)
        face_specs = [
            ("brown", 0, 0, "brown.png", (0.280, 0.250, 0.720, 0.600), "#FCEBD9", 0.26),
            ("pink", 1, 0, "pink.png", (0.275, 0.220, 0.725, 0.590), "#F6EAE0", 0.30),
            ("skyblue", 0, 1, "skyblue.png", (0.275, 0.220, 0.725, 0.595), "#F5ECE2", 0.30),
            ("grey", 1, 1, "gray.png", (0.275, 0.235, 0.725, 0.595), "#F4E9DF", 0.30),
        ]
        pad = 4
        inner = 512 - 2 * pad
        crisp_v5_path = os.path.join(src_raw_dir, "billie_face_crisp_v5.png")
        for sch_key, qx, qy, fname, box, skin_hex, sharp_amt in face_specs:
            bg = np.ones((inner, inner, 4), dtype=np.float32)
            r, g, b = hex_rgb(skin_hex)
            bg[..., 0], bg[..., 1], bg[..., 2] = r, g, b

            if sch_key == "brown" and os.path.isfile(crisp_v5_path):
                raw_v5 = _load_rgba_topdown(crisp_v5_path)
                sub = _resize_rgba(raw_v5, inner, inner)
                comp = _alpha_over(bg, sub)
                # Gentle edge-color harmonization toward #FCEBD9 around outer 10px border
                yy_f, xx_f = np.mgrid[0:inner, 0:inner].astype(np.float32)
                edge_d = np.minimum(
                    np.minimum(xx_f, (inner - 1) - xx_f),
                    np.minimum(yy_f, (inner - 1) - yy_f),
                )
                w_harm = np.clip((10.0 - edge_d) / 10.0, 0.0, 1.0)[..., None]
                comp[..., :3] = comp[..., :3] * (1.0 - w_harm) + bg[..., :3] * w_harm
                comp = _unsharp_rgba(comp, amount=sharp_amt)
            else:
                src_p = os.path.join(THEME_DIR, "mascots", fname)
                if not os.path.isfile(src_p):
                    continue
                raw = _load_rgba_topdown(src_p)
                h, w, _ = raw.shape
                ix0, iy0 = max(0, int(w * box[0])), max(0, int(h * box[1]))
                ix1, iy1 = min(w, int(w * box[2])), min(h, int(h * box[3]))
                sub = _resize_rgba(raw[iy0:iy1, ix0:ix1].copy(), inner, inner)
                comp = _unsharp_rgba(_alpha_over(bg, sub), amount=sharp_amt)

            comp[..., 3] = 1.0
            x0, y0 = qx * 512 + pad, qy * 512 + pad
            sheet[y0:y0 + inner, x0:x0 + inner] = comp
            _edge_pad_rect(sheet, x0, y0, inner, inner, pad=pad)
        sheet[..., 3] = 1.0
        _save_rgba_topdown(sheet, faces_out, alpha=False)
    arts["faces"] = faces_out

    # 3. billie_art_logo.png (1024x512 opaque framed badge cropped directly from 2000x2000 logo-bg.png!)
    logo_out = os.path.join(art_dir, "billie_art_logo.png")
    logo_bg_src = os.path.join(THEME_DIR, "logo-bg.png")
    if _need(logo_out) and os.path.isfile(logo_bg_src):
        raw = _load_rgba_topdown(logo_bg_src)
        h, w, _ = raw.shape
        ix0, ix1 = int(w * 0.015), int(w * 0.985)
        iy0, iy1 = int(h * 0.180), int(h * 0.745)
        crop = _unsharp_rgba(_resize_rgba(raw[iy0:iy1, ix0:ix1].copy(), 1024, 512), amount=0.26)
        crop[..., 3] = 1.0
        yy, xx = np.mgrid[0:512, 0:1024].astype(np.float32)
        d_outer = _sdf_rounded_rect(xx, yy, 512.0, 256.0, 498.0, 242.0, 36.0)
        d_gold_ring = np.abs(d_outer + 12.0) - 3.0
        d_in_ring = np.abs(d_outer + 6.0) - 2.8
        crop = _paint_sdf(crop, d_gold_ring, "#FFD147", alpha=0.88, aa=1.4)
        crop = _paint_sdf(crop, d_in_ring, "#FFFBF4", alpha=0.88, aa=1.4)
        crop = _paint_sdf(crop, -d_outer, "#3B281E", alpha=1.0, aa=1.5)
        crop[..., 3] = 1.0
        _save_rgba_topdown(crop, logo_out, alpha=False)
    arts["logo_badge"] = logo_out
    arts["logo"] = logo_out

    # 4. Special Unified Warm-Brown Kawaii UI Screens (prefer custom illustrated master asset if present!)
    atm_out = os.path.join(art_dir, "billie_atm_screen.png")
    atm_master = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "mascots", "billie_atm_screen.png")
    if _need(atm_out):
        if os.path.exists(atm_master):
            import shutil
            shutil.copy2(atm_master, atm_out)
        else:
            _make_atm_screen(atm_out, 1024)
    arts["atm_screen"] = atm_out

    shop_sign_out = os.path.join(art_dir, "billie_shop_sign.png")
    shop_sign_master = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "mascots", "billie_shop_sign.png")
    if _need(shop_sign_out) and os.path.exists(shop_sign_master):
        import shutil
        shutil.copy2(shop_sign_master, shop_sign_out)
    if os.path.exists(shop_sign_out):
        arts["shop_sign"] = shop_sign_out

    gauge_out = os.path.join(art_dir, "billie_gauge_dial.png")
    if _need(gauge_out):
        _make_gauge_dial(gauge_out, 512)
    arts["gauge_dial"] = gauge_out

    # 5. Crisp 1024x512 Unified Warm-Brown BILLIE SCHOOL Pop-Art Sign Banners (all 14!)
    sign_specs = [
        ("sign_garage", "GARAGE", "BILLIE SCHOOL", "#FFFBF4", "#C8966B", "#3B281E"),
        ("sign_pound", "POUND", "BILLIE IMPOUND", "#FFFBF4", "#7C4F32", "#3B281E"),
        ("sign_parking", "PARKING", "BILLIE ZONE", "#FFFBF4", "#A67248", "#3B281E"),
        ("sign_shop", "SHOP", "BILLIE CAFE", "#FFFBF4", "#C8966B", "#3B281E"),
        ("sign_atm", "ATM", "BILLIE BANK", "#FFFBF4", "#7C4F32", "#3B281E"),
        ("sign_crafting", "CRAFTING", "BILLIE STUDIO", "#FFFBF4", "#A67248", "#3B281E"),
        ("sign_airdrop", "AIRDROP", "BILLIE SUPPLY", "#FFFBF4", "#C8966B", "#3B281E"),
        ("sign_redbox", "REDBOX", "BILLIE TOOL", "#FFFBF4", "#A84438", "#3B281E"),
        ("sign_powerbox", "240V", "POWER BOX", "#FFFBF4", "#7C4F32", "#3B281E"),
        ("sign_waterpipe", "WATER", "PRESSURE VALVE", "#FFFBF4", "#A67248", "#3B281E"),
        ("sign_gachapon", "GACHA", "BILLIE LUCKY", "#FFFBF4", "#C8966B", "#3B281E"),
        ("sign_washmoney", "LAUNDRY", "BILLIE WASH", "#FFFBF4", "#A67248", "#3B281E"),
        ("sign_loot", "LOOT", "BILLIE GIFT", "#FFFBF4", "#A84438", "#3B281E"),
        ("sign_billie", "BILLIE", "SCHOOL", "#FFFBF4", "#C8966B", "#3B281E"),
    ]
    for key, title, sub, bg_h, acc_h, bdr_h in sign_specs:
        sp = os.path.join(art_dir, key + ".png")
        if _need(sp):
            make_text_banner(
                title,
                sp,
                bg_hex=bg_h,
                border_hex=bdr_h,
                text_hex="#FFFBF4",
                text_outline_hex=bdr_h,
                accent_hex=acc_h,
                subtitle=sub,
                striped=True,
                width=1024,
                height=512,
                stars=True,
                halftone=True,
            )
        arts[key] = sp

    return arts


prepare_billie_art = prepare_billie_art_v4
prepare_billie_art_v3 = prepare_billie_art_v4


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
# KawaiiBuilder V12 — Sharp Pop-Art Low-Poly Artisan Builder
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


def _assign_part_uvs(ob, role, uv_kind="box", stripe_freq=3.6):
    """Assign razor-sharp palette/stripe UVs directly in part-local space BEFORE joining!

    - Solid roles: inner [0.25..0.75] of 64x64 cell in billie_master_pal.png (ZERO bleed!).
    - Emissive roles: inner [0.25..0.75] of 64x64 cell in billie_glow_pal.png.
    - stripe_* roles:
        * Cylinders/lathes: seamless cylindrical spiral with quantized integer repeats around circumference!
        * Boxes/bevels: smooth continuous (x + y + z) projection (ZERO zig-zagging across rounded corners!)
      with v strictly clamped inside [v0 + 0.26*h .. v1 - 0.26*h] (16.6px guard on top & bottom!).
    - halftone_cream: clean aspect-matched triplanar dots inside [v0 + 0.22*h .. v1 - 0.22*h].
    """
    me = ob.data
    if not me.polygons:
        return
    canon = resolve_role(role)
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    uv_layer = me.uv_layers[0] if me.uv_layers else me.uv_layers.new(name="UVMap")
    uv_layer.name = "UVMap"
    me.uv_layers.active = uv_layer

    verts = [v.co for v in me.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    dx = max(1e-4, x_max - x_min)
    dy = max(1e-4, y_max - y_min)
    dz = max(1e-4, z_max - z_min)
    uv_data = uv_layer.data

    # 1. Emissive palette (256x256, 4x4 of 64x64)
    if canon in GLOW_CELL_INDEX:
        idx = GLOW_CELL_INDEX[canon]
        gx, gy = idx % 4, idx // 4
        cw = 64.0 / 256.0
        u0 = gx * cw
        v_bot = 1.0 - (gy + 1) * cw
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                nx = (co.x - x_min) / dx
                nz = (co.z - z_min) / dz
                uv_data[li].uv = (u0 + (0.28 + 0.44 * nx) * cw, v_bot + (0.25 + 0.50 * nz) * cw)
        return

    # 2. Pattern strips (bottom half of 1024x1024: 8 strips of 1024x64)
    if canon in STRIP_INDEX:
        s_idx = STRIP_INDEX[canon]
        h_strip = 64.0 / 1024.0
        v_top = 1.0 - (512.0 + s_idx * 64.0) / 1024.0
        v_bot = v_top - h_strip

        if canon == "halftone_brown":
            v_lo = v_bot + 0.22 * h_strip
            v_span = 0.56 * h_strip
            scale_m = max(dx, dy, dz, 0.25)
            for poly in me.polygons:
                n = poly.normal
                ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
                for li in poly.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    if az >= ax and az >= ay:
                        pu, pv = (co.x - x_min) / scale_m, (co.y - y_min) / dy
                    elif ay >= ax:
                        pu, pv = (co.x - x_min) / scale_m, (co.z - z_min) / dz
                    else:
                        pu, pv = (co.y - y_min) / scale_m, (co.z - z_min) / dz
                    vv = v_lo + max(0.0, min(1.0, pv)) * v_span
                    uu = pu * (v_span * 16.0 * (scale_m / max(0.25, dz if az < max(ax, ay) else dy)))
                    uv_data[li].uv = (uu, vv)
            return

        v_lo = v_bot + 0.26 * h_strip
        v_span = 0.48 * h_strip
        sx, sy, sz = ob.matrix_world.to_scale()
        w_scale_xy = max(0.05, 0.5 * (abs(sx) + abs(sy)))
        w_scale_z = max(0.05, abs(sz))

        is_cyl = uv_kind in ("cyl", "lathe", "tube", "torus")
        if is_cyl:
            cx = 0.5 * (x_min + x_max)
            cy = 0.5 * (y_min + y_max)
            r_avg = max(0.03, 0.25 * (dx + dy) * w_scale_xy)
            circum = math.tau * r_avg
            n_circ = max(2, int(round(circum * stripe_freq)))
            for poly in me.polygons:
                n = poly.normal
                if abs(n.z) > 0.78:
                    for li in poly.loop_indices:
                        co = me.vertices[me.loops[li].vertex_index].co
                        pv = (co.y - y_min) / dy
                        vv = v_lo + max(0.0, min(1.0, pv)) * v_span
                        w_phase = (co.x * abs(sx) + co.y * abs(sy)) * stripe_freq
                        uu = (w_phase - (v_top - vv) / h_strip) / 16.0
                        uv_data[li].uv = (uu, vv)
                else:
                    cos_l = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
                    angs = [math.atan2(c.y - cy, c.x - cx) for c in cos_l]
                    a0 = angs[0]
                    unwrapped = []
                    for a in angs:
                        da = a - a0
                        while da > math.pi:
                            da -= math.tau
                        while da < -math.pi:
                            da += math.tau
                        unwrapped.append(a0 + da)
                    for li, co, ang in zip(poly.loop_indices, cos_l, unwrapped):
                        pv = (co.z - z_min) / dz
                        vv = v_lo + max(0.0, min(1.0, pv)) * v_span
                        w_phase = (ang / math.tau) * n_circ + (co.z * w_scale_z) * stripe_freq
                        uu = (w_phase - (v_top - vv) / h_strip) / 16.0
                        uv_data[li].uv = (uu, vv)
        else:
            # Continuous (x + y + z) diagonal projection across ALL faces & rounded bevels (ZERO zig-zag!)
            for poly in me.polygons:
                for li in poly.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    pv = (co.z - z_min) / dz
                    vv = v_lo + max(0.0, min(1.0, pv)) * v_span
                    w_phase = (co.x * abs(sx) + co.y * abs(sy) + co.z * abs(sz)) * stripe_freq
                    uu = (w_phase - (v_top - vv) / h_strip) / 16.0
                    uv_data[li].uv = (uu, vv)
        return

    # 3. Solid diffuse vinyl palette (top half of 1024x1024: 16x8 of 64x64)
    idx = SOLID_CELL_INDEX.get(canon, SOLID_CELL_INDEX["caramel"])
    gx, gy = idx % 16, idx // 16
    cw = 64.0 / 1024.0
    u0 = gx * cw
    v_bot = 1.0 - (gy + 1) * cw
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            nx = (co.x - x_min) / dx
            nz = (co.z - z_min) / dz
            uv_data[li].uv = (u0 + (0.28 + 0.44 * nx) * cw, v_bot + (0.25 + 0.50 * nz) * cw)


def _fibonacci_hemisphere(n=16):
    """Return n evenly distributed unit vectors on the +Z hemisphere for smooth BVH AO."""
    dirs = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 0.14 + 0.84 * ((i + 0.5) / float(n))
        r = math.sqrt(max(0.0, 1.0 - z * z))
        theta = golden * i
        dirs.append((r * math.cos(theta), r * math.sin(theta), z))
    return dirs


_HEMI_DIRS_16 = _fibonacci_hemisphere(16)


class KawaiiBuilder:
    """V13 Unified Warm-Brown Edge-Craft Low-Poly 3D Prop Builder with Master Palette UVs & Soft Vertex AO."""

    def __init__(
        self,
        prop_id,
        archetype="custom",
        budget=4500,
        lod_dist=80,
        collision=True,
        animate=True,
        palette=None,
        art_dir=None,
        set_name="billie_prop",
        reset_scene=True,
        low_poly=True,
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
        self.low_poly = bool(low_poly)
        self.palette = dict(BILLIE_PALETTE)
        if palette:
            self.palette.update(palette)
        self.art_dir = os.path.abspath(art_dir or DEFAULT_ART_DIR)
        self.art = prepare_billie_art_v4(self.art_dir, force=False)
        self.art_uv = ART_UV
        self.art_uv_v4 = ART_UV_V4
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
        canon = resolve_role(role)
        if canon in self.materials:
            return self.materials[canon]
        mname = "{}_{}".format(self.id, canon)
        mat = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
        mat.use_nodes = True
        hex_val = self.palette.get(canon, "#C8966B")
        lin = hex_rgba_lin(hex_val, 1.0)
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = lin
            bsdf.inputs["Roughness"].default_value = 0.46
            if canon in EMISSIVE_ROLES:
                bsdf.inputs["Emission Color"].default_value = lin
                bsdf.inputs["Emission Strength"].default_value = 1.6
        mat.diffuse_color = lin
        mat["prop_forge_role"] = canon
        self.materials[canon] = mat
        return mat

    def _add_bm(
        self,
        name,
        bm,
        role,
        matrix=None,
        bevel=0.0,
        bevel_segs=2,
        subsurf=0,
        solidify=0.0,
        uv_kind="box",
        stripe_freq=3.6,
        organic_smooth=False,
    ):
        self._part_idx += 1
        me = bpy.data.meshes.new("{}_{}".format(name, self._part_idx))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        if organic_smooth and len(me.polygons) > 0:
            org_attr = me.attributes.new(name="organic_smooth", type="INT", domain="FACE")
            org_attr.data.foreach_set("value", [1] * len(me.polygons))
            for p in me.polygons:
                p.use_smooth = True
        ob = bpy.data.objects.new(me.name, me)
        self.collection.objects.link(ob)
        ob.matrix_world = matrix if matrix is not None else Matrix.Identity(4)
        canon = resolve_role(role)
        me.materials.append(self._get_role_mat(canon))
        ob["prop_forge_bone"] = self.current_bone
        ob["prop_forge_role"] = canon
        ob["prop_forge_uv_kind"] = str(uv_kind)
        ob["prop_forge_stripe_freq"] = float(stripe_freq)

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

    # ---- Smooth Low-Poly Pop-Art Artisan Primitives ----

    def plush_box(
        self,
        size,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        r_bevel=None,
        subsurf=None,
        bevel_segs=None,
        rot=(0.0, 0.0, 0.0),
        M=None,
        puff=0.032,
        collide=False,
        stripe_freq=3.6,
    ):
        """Silky pillowy rounded-corner Pop-Mart toy body (low_poly: subsurf=0, bevel_segs=2!)."""
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        min_d = max(1e-4, min(sx, sy, sz))
        rb = min(min_d * 0.44, float(r_bevel) if r_bevel is not None else min_d * 0.22)
        if subsurf is None:
            ss_lvl = 0 if self.low_poly else 1
        else:
            ss_lvl = min(0 if self.low_poly else 2, max(0, int(subsurf)))
        if bevel_segs is None:
            b_segs = 2 if (self.low_poly or ss_lvl <= 1) else 1
        else:
            b_segs = max(1, int(bevel_segs))

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
        if rb > 1e-4:
            bmesh.ops.bevel(
                bm,
                geom=list(bm.edges),
                offset=rb,
                offset_type="OFFSET",
                segments=b_segs,
                profile=0.55,
                affect="EDGES",
                clamp_overlap=True,
            )
        if puff > 0.0:
            hx, hy, hz = max(1e-4, sx * 0.5), max(1e-4, sy * 0.5), max(1e-4, sz * 0.5)
            for v in bm.verts:
                nx = v.co.x / hx
                ny = v.co.y / hy
                nz = v.co.z / hz
                w_x = (1.0 - ny * ny * 0.5) * (1.0 - nz * nz * 0.5)
                w_y = (1.0 - nx * nx * 0.5) * (1.0 - nz * nz * 0.5)
                w_z = (1.0 - nx * nx * 0.5) * (1.0 - ny * ny * 0.5)
                v.co.x *= 1.0 + puff * w_x
                v.co.y *= 1.0 + puff * w_y
                v.co.z *= 1.0 + puff * w_z
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        ob = self._add_bm("pbox", bm, role, world, subsurf=ss_lvl, uv_kind="box", stripe_freq=stripe_freq)
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
        segs=None,
        collide=False,
        stripe_freq=3.6,
    ):
        """Smooth rounded candy-pill / capsule / lozenge (buttons, handles, legs, arches)."""
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        dims = [sx, sy, sz]
        axis_i = int(np.argmax(dims))
        r_cross = [dims[j] * 0.5 for j in range(3) if j != axis_i]
        r_end = min(r_cross)
        half_len = max(0.0, dims[axis_i] * 0.5 - r_end)

        s_eff = int(segs) if segs is not None else (8 if self.low_poly else 18)
        if self.low_poly and segs is not None:
            s_eff = min(s_eff, 12)
        u_seg = max(6, s_eff)
        v_seg = max(4, (u_seg // 2) if self.low_poly else ((u_seg // 2) * 2))

        bm = bmesh.new()
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
        ob = self._add_bm("ppill", bm, role, world, uv_kind="box", stripe_freq=stripe_freq)
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
        segs=None,
        r_top=None,
        axis="Z",
        rot=(0.0, 0.0, 0.0),
        M=None,
        collide=False,
        stripe_freq=3.6,
    ):
        """Smooth rounded-cap cylinder / tapered pedestal / drum / coin / wheel (V13: hero rims default segs=20!)."""
        r1 = float(r)
        r2 = float(r_top) if r_top is not None else r1
        hh = float(h)
        if segs is not None:
            s_eff = min(36, max(5, int(segs)))
        else:
            s_eff = (20 if max(r1, r2) >= 0.14 else 14) if self.low_poly else 28
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=max(5, s_eff),
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
                    segments=1 if self.low_poly else 3,
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
        ob = self._add_bm("pcyl", bm, role, world, uv_kind="cyl", stripe_freq=stripe_freq)
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
        u=None,
        v=None,
        M=None,
        stripe_freq=3.6,
    ):
        """Smooth low-poly UV sphere (low_poly default: u=14, v=9!)."""
        u_eff = int(u) if u is not None else (14 if self.low_poly else 22)
        v_eff = int(v) if v is not None else (9 if self.low_poly else 14)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=max(6, u_eff), v_segments=max(3, v_eff), radius=float(r))
        if scale != (1.0, 1.0, 1.0):
            bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        return self._add_bm("psph", bm, role, world, uv_kind="cyl", stripe_freq=stripe_freq)

    def lathe(
        self,
        profile,
        loc=(0.0, 0.0, 0.0),
        role="caramel",
        segs=None,
        rot=(0.0, 0.0, 0.0),
        smooth_profile=0,
        cap_bottom=True,
        cap_top=True,
        M=None,
        collide=False,
        stripe_freq=3.6,
    ):
        """Revolve a 2D profile [(radius, z), ...] smoothly 360 deg around Z axis (V13: hero default segs=20!)."""
        pts = [(max(0.0, float(r)), float(z)) for (r, z) in profile]
        sp = min(int(smooth_profile), 1) if self.low_poly else int(smooth_profile)
        if sp > 0:
            pts = _chaikin_open(pts, iters=sp)
        max_r = max((p[0] for p in pts), default=0.0)
        if segs is not None:
            s_eff = min(36, max(8, int(segs)))
        else:
            s_eff = (20 if max_r >= 0.14 else 14) if self.low_poly else 28
        n_seg = max(8, s_eff)
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
        ob = self._add_bm("plathe", bm, role, world, uv_kind="lathe", stripe_freq=stripe_freq)
        if collide and pts:
            rmax = max(p[0] for p in pts)
            z0 = min(p[1] for p in pts)
            z1 = max(p[1] for p in pts)
            self.collider_from(
                world @ Matrix.Translation((0.0, 0.0, (z0 + z1) * 0.5)),
                (rmax * 2.0, rmax * 2.0, max(0.05, z1 - z0)),
            )
        return ob

    def plush_torus(
        self,
        major_r,
        minor_r,
        loc=(0.0, 0.0, 0.0),
        role="cocoa",
        axis="Z",
        rot=(0.0, 0.0, 0.0),
        seg_major=None,
        seg_minor=None,
        arc_deg=360.0,
        M=None,
        stripe_freq=3.6,
    ):
        """Smooth low-poly torus ring OR curved elbow/arch when arc_deg < 360 (V13: hero default seg_major=20!)."""
        R, r = float(major_r), float(minor_r)
        if seg_major is not None:
            nm = min(36, max(6, int(seg_major)))
        else:
            nm = (20 if R >= 0.12 else 14) if self.low_poly else 28
        nn = max(5, int(seg_minor) if seg_minor is not None else (8 if self.low_poly else 14))
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

        for i in range(nm):
            r0 = rings[i]
            r1 = rings[(i + 1) % len(rings)]
            for j in range(nn):
                jn = (j + 1) % nn
                bm.faces.new((r0[j], r1[j], r1[jn], r0[jn]))

        if not closed:
            for idx_end, flip in ((0, True), (-1, False)):
                ring = rings[idx_end]
                bm.faces.new(list(reversed(ring)) if flip else ring)

        axis_rot = {
            "Z": Matrix.Identity(4),
            "X": Matrix.Rotation(math.pi * 0.5, 4, "Y"),
            "Y": Matrix.Rotation(math.pi * 0.5, 4, "X"),
        }.get(str(axis).upper(), Matrix.Identity(4))
        world = (M or Matrix.Identity(4)) @ trs(loc, rot) @ axis_rot
        return self._add_bm("ptorus", bm, role, world, uv_kind="torus", stripe_freq=stripe_freq)

    def plush_tube(
        self,
        points,
        radius,
        role="caramel",
        segs=None,
        closed=False,
        cap_ends=True,
        smooth_steps=1,
        M=None,
        stripe_freq=3.6,
    ):
        """Sweep a smooth circular tube along 3D polyline points=[(x,y,z), ...] with parallel transport."""
        pts = [tuple(float(c) for c in p) for p in points]
        st = min(int(smooth_steps), 1) if self.low_poly else int(smooth_steps)
        if st > 0 and len(pts) >= 3:
            pts = _chaikin_closed(pts, st) if closed else _chaikin_open(pts, st)
        vecs = [Vector(p) for p in pts]
        n_pts = len(vecs)
        if n_pts < 2:
            return None
        nn = max(5, int(segs) if segs is not None else (8 if self.low_poly else 14))
        r = float(radius)

        tangents = []
        for i in range(n_pts):
            if closed:
                t = vecs[(i + 1) % n_pts] - vecs[(i - 1) % n_pts]
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
            c0 = bm.verts.new(vecs[0] - tangents[0] * (r * 0.68))
            c1 = bm.verts.new(vecs[-1] + tangents[-1] * (r * 0.68))
            for j in range(nn):
                jn = (j + 1) % nn
                bm.faces.new((c0, rings[0][jn], rings[0][j]))
                bm.faces.new((c1, rings[-1][j], rings[-1][jn]))

        world = M or Matrix.Identity(4)
        return self._add_bm("ptube", bm, role, world, uv_kind="box", stripe_freq=stripe_freq)

    def plush_extrude(
        self,
        pts_2d,
        depth,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        bevel=0.016,
        bevel_segs=None,
        rot=(0.0, 0.0, 0.0),
        M=None,
        stripe_freq=3.6,
    ):
        """Extrude a 2D silhouette [(x, z), ...] along Y (-depth/2..+depth/2) with rounded bevel."""
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
        b_segs = int(bevel_segs) if bevel_segs is not None else (1 if self.low_poly else 3)
        if bev > 1e-4:
            cap_edges = [e for e in bm.edges if abs(e.verts[0].co.y - e.verts[1].co.y) < 1e-4]
            if cap_edges:
                bmesh.ops.bevel(
                    bm,
                    geom=cap_edges,
                    offset=bev,
                    offset_type="OFFSET",
                    segments=max(1, b_segs),
                    profile=0.55,
                    affect="EDGES",
                    clamp_overlap=True,
                )
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        return self._add_bm("pext", bm, role, world, uv_kind="box", stripe_freq=stripe_freq)

    def plush_frame(
        self,
        w,
        h,
        depth=0.045,
        thickness=0.030,
        loc=(0.0, 0.0, 0.0),
        role="cocoa",
        r_corner=None,
        segs_corner=4,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """Smooth rounded-pill .bbu-frame hollow border ring in XZ plane facing -Y (V13: segs_corner=4!)."""
        rc = float(r_corner) if r_corner is not None else min(w, h) * 0.16
        c_segs = max(2, int(segs_corner))
        t_segs = 8 if self.low_poly else 12
        pts2 = plush_rounded_rect_pts(w, h, rc, segs_corner=c_segs)
        pts3 = [(x, 0.0, z) for (x, z) in pts2]
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        ob = self.plush_tube(pts3, radius=float(thickness) * 0.5, role=role, segs=t_segs, closed=True, smooth_steps=0, M=world)
        if ob and depth > 0.0 and abs(depth - thickness) > 1e-3:
            sy = float(depth) / max(1e-4, float(thickness))
            for v in ob.data.vertices:
                v.co.y *= sy
            ob.data.update()
        return ob

    def _exact_rrect_pts(self, w, h, r, segs_corner=2):
        """Return exact fixed-count 4*(segs_corner+1) CCW rounded rectangle points in 2D."""
        hw, hh = float(w) * 0.5, float(h) * 0.5
        rc = max(0.0015, min(float(r), hw * 0.90, hh * 0.90))
        n = max(1, int(segs_corner))
        pts = []
        corners = (
            (hw - rc, -hh + rc, -90.0),
            (hw - rc, hh - rc, 0.0),
            (-hw + rc, hh - rc, 90.0),
            (-hw + rc, -hh + rc, 180.0),
        )
        for cx, cy, a0 in corners:
            for i in range(n + 1):
                a = math.radians(a0 + 90.0 * i / float(n))
                pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
        return pts

    def _add_mitered_molding_slab(self, w, d, h, z_center, chamfer, r_corner, role, world, invert_bevel=False):
        """Build a crisp watertight 68-tri architectural mitered molding slab (base plinth or crown cornice)."""
        ch = max(0.002, min(float(chamfer), float(h) * 0.42, min(w, d) * 0.14))
        rc = max(ch + 0.004, min(float(r_corner), min(w, d) * 0.42))
        pts_o = self._exact_rrect_pts(w, d, rc, segs_corner=2)
        pts_i = self._exact_rrect_pts(w - 2.0 * ch, d - 2.0 * ch, max(0.002, rc - ch), segs_corner=2)
        n = len(pts_o)
        z0 = float(z_center) - float(h) * 0.5
        z1 = float(z_center) + float(h) * 0.5

        bm = bmesh.new()
        if not invert_bevel:
            # Base plinth: flat bottom footing on z0, outer wall, crisp 45-deg top shoulder bevel into cabinet
            r0 = [bm.verts.new((x, y, z0)) for (x, y) in pts_o]
            r1 = [bm.verts.new((x, y, z1 - ch)) for (x, y) in pts_o]
            r2 = [bm.verts.new((x, y, z1)) for (x, y) in pts_i]
        else:
            # Top cornice: crisp 45-deg bottom shoulder bevel, outer cornice fascia, clean flat top cap
            r0 = [bm.verts.new((x, y, z0)) for (x, y) in pts_i]
            r1 = [bm.verts.new((x, y, z0 + ch)) for (x, y) in pts_o]
            r2 = [bm.verts.new((x, y, z1)) for (x, y) in pts_o]

        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
            bm.faces.new((r1[i], r1[j], r2[j], r2[i]))
        bm.faces.new(list(reversed(r0)))
        bm.faces.new(r2)
        return self._add_bm("molding", bm, role, world, uv_kind="box")

    def edge_piped_box(
        self,
        size,
        loc=(0.0, 0.0, 0.0),
        body_role="latte",
        trim_role="cocoa",
        accent_role="gold",
        trim_r=0.020,
        base_molding=True,
        crown_molding=True,
        vertical_rails=True,
        corner_studs=True,
        rot=(0.0, 0.0, 0.0),
        r_bevel=None,
        puff=0.018,
        collide=False,
        stripe_freq=3.6,
        M=None,
    ):
        """V13 Edge-Craft Cabinet: bevelled body + mitered plinth/cornice moldings + 4 corner bumper rails + gold studs (~380-420 tris!)."""
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        min_d = max(0.04, min(sx, sy, sz))
        tr = max(0.008, min(float(trim_r), min_d * 0.16))
        rb = float(r_bevel) if r_bevel is not None else min(min_d * 0.16, tr * 2.4)
        world = (M or Matrix.Identity(4)) @ trs(loc, rot)

        # 1. Clean bevelled cabinet body (~108 tris)
        body_ob = self.plush_box(
            (sx, sy, sz),
            (0.0, 0.0, 0.0),
            role=body_role,
            r_bevel=rb,
            bevel_segs=2,
            puff=puff,
            collide=collide,
            stripe_freq=stripe_freq,
            M=world,
        )

        mold_h = tr * 1.95
        mold_out = tr * 1.25
        mold_rc = rb + mold_out * 0.55

        # 2. Mitered bottom plinth molding (~68 tris)
        if base_molding and trim_role:
            self._add_mitered_molding_slab(
                sx + mold_out,
                sy + mold_out,
                mold_h,
                z_center=-sz * 0.5 + mold_h * 0.5,
                chamfer=tr * 0.62,
                r_corner=mold_rc,
                role=trim_role,
                world=world,
                invert_bevel=False,
            )

        # 3. Mitered top cornice molding (~68 tris)
        if crown_molding and trim_role:
            self._add_mitered_molding_slab(
                sx + mold_out,
                sy + mold_out,
                mold_h,
                z_center=sz * 0.5 - mold_h * 0.5,
                chamfer=tr * 0.62,
                r_corner=mold_rc,
                role=trim_role,
                world=world,
                invert_bevel=True,
            )

        # 4. 4 rounded vertical corner bumper rails spanning plinth-to-cornice (combined watertight bmesh, ~80 tris)
        if vertical_rails and trim_role:
            bm_r = bmesh.new()
            r_col = tr * 0.72
            z_lo = -sz * 0.5 + (mold_h * 0.70 if base_molding else tr * 0.35)
            z_hi = sz * 0.5 - (mold_h * 0.70 if crown_molding else tr * 0.35)
            if z_hi > z_lo + 0.01:
                cx_off = max(0.01, sx * 0.5 - rb * 0.30)
                cy_off = max(0.01, sy * 0.5 - rb * 0.30)
                n_s = 6
                for sgn_x in (-1.0, 1.0):
                    for sgn_y in (-1.0, 1.0):
                        px, py = sgn_x * cx_off, sgn_y * cy_off
                        bot_ring = [
                            bm_r.verts.new((px + r_col * math.cos(math.tau * i / n_s), py + r_col * math.sin(math.tau * i / n_s), z_lo))
                            for i in range(n_s)
                        ]
                        top_ring = [
                            bm_r.verts.new((px + r_col * math.cos(math.tau * i / n_s), py + r_col * math.sin(math.tau * i / n_s), z_hi))
                            for i in range(n_s)
                        ]
                        for i in range(n_s):
                            j = (i + 1) % n_s
                            bm_r.faces.new((bot_ring[i], bot_ring[j], top_ring[j], top_ring[i]))
                        bm_r.faces.new(list(reversed(bot_ring)))
                        bm_r.faces.new(top_ring)
                self._add_bm("erails", bm_r, trim_role, world, uv_kind="box")
            else:
                bm_r.free()

        # 5. 8 gleaming sunny-gold domed corner studs on plinth & cornice corners (combined watertight bmesh, ~80 tris)
        if corner_studs and accent_role:
            bm_s = bmesh.new()
            stud_r = max(0.007, tr * 0.58)
            stud_h = stud_r * 0.82
            z_levels = []
            if base_molding:
                z_levels.append(-sz * 0.5 + mold_h * 0.48)
            if crown_molding:
                z_levels.append(sz * 0.5 - mold_h * 0.48)
            if not z_levels:
                z_levels = [-sz * 0.5 + tr * 1.1, sz * 0.5 - tr * 1.1]
            sx_pos = max(0.01, (sx + mold_out) * 0.5 - mold_rc * 0.28)
            sy_pos = max(0.01, (sy + mold_out) * 0.5 - mold_rc * 0.28)
            n_st = 6
            for zs in z_levels:
                for sgn_x in (-1.0, 1.0):
                    for sgn_y in (-1.0, 1.0):
                        ndir = Vector((sgn_x, sgn_y, 0.0)).normalized()
                        t1 = Vector((-ndir.y, ndir.x, 0.0))
                        t2 = Vector((0.0, 0.0, 1.0))
                        base_c = Vector((sgn_x * sx_pos, sgn_y * sy_pos, zs)) - ndir * (stud_h * 0.22)
                        ring = [
                            bm_s.verts.new(base_c + (t1 * math.cos(math.tau * i / n_st) + t2 * math.sin(math.tau * i / n_st)) * stud_r)
                            for i in range(n_st)
                        ]
                        apex = bm_s.verts.new(base_c + ndir * stud_h)
                        for i in range(n_st):
                            j = (i + 1) % n_st
                            bm_s.faces.new((ring[i], ring[j], apex))
                        bm_s.faces.new(list(reversed(ring)))
            self._add_bm("estuds", bm_s, accent_role, world, uv_kind="box")

        return body_ob

    def smooth_bezel_ring(
        self,
        r_outer,
        r_inner,
        depth,
        loc=(0.0, 0.0, 0.0),
        outer_role="cocoa",
        inner_role="gold",
        axis="Y",
        segs=24,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """V13 Silky 24-segment bevelled outer bezel ring + stepped inner golden accent ring (ZERO octagonal jaggedness!)."""
        r_out = max(0.015, float(r_outer))
        r_in = max(0.005, min(float(r_inner), r_out * 0.90))
        rw = max(0.004, r_out - r_in)
        d = max(0.008, float(depth))
        hd = d * 0.5
        n_seg = min(36, max(12, int(segs)))

        axis_rot = {
            "Z": Matrix.Identity(4),
            "X": Matrix.Rotation(math.pi * 0.5, 4, "Y"),
            "Y": Matrix.Rotation(math.pi * 0.5, 4, "X"),
        }.get(str(axis).upper(), Matrix.Identity(4))
        world = (M or Matrix.Identity(4)) @ trs(loc, rot) @ axis_rot

        def _revolve_closed_profile(prof_rz, tag, role):
            bm = bmesh.new()
            m = len(prof_rz)
            rings = []
            for i in range(n_seg):
                a = math.tau * i / float(n_seg)
                ca, sa = math.cos(a), math.sin(a)
                rings.append([bm.verts.new((rad * ca, rad * sa, z)) for (rad, z) in prof_rz])
            for i in range(n_seg):
                r0 = rings[i]
                r1 = rings[(i + 1) % n_seg]
                for k in range(m):
                    kn = (k + 1) % m
                    bm.faces.new((r0[k], r1[k], r1[kn], r0[kn]))
            return self._add_bm(tag, bm, role, world, uv_kind="cyl")

        r_mid = r_in + rw * (0.42 if inner_role else 0.0)
        bev = min((r_out - r_mid) * 0.34, hd * 0.42)
        outer_prof = [
            (r_mid, -hd),
            (r_out - bev, -hd),
            (r_out, -hd + bev),
            (r_out, hd - bev),
            (r_out - bev, hd),
            (r_mid, hd),
        ]
        outer_ob = _revolve_closed_profile(outer_prof, "bezel_out", outer_role)

        if inner_role:
            hd_in = hd * 0.76
            r_ov = min(r_out - bev * 0.5, r_mid + rw * 0.08)
            inner_prof = [
                (r_in, -hd_in),
                (r_ov, -hd_in),
                (r_ov, hd_in),
                (r_in, hd_in),
            ]
            _revolve_closed_profile(inner_prof, "bezel_in", inner_role)

        return outer_ob

    def plush_cloud(
        self,
        pts_r,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        smooth_iters=2,
        scale=(1.0, 1.0, 1.0),
        rot=(0.0, 0.0, 0.0),
        flat_bottom=True,
        squash_z=0.78,
        u_seg=None,
        v_seg=None,
        M=None,
    ):
        """Smooth silky puffy low-poly studio cloud cushion from [(x, y, z, r), ...]."""
        world = (M or Matrix.Identity(4)) @ trs(loc, rot, scale)
        if not pts_r:
            return None
        z_floor = min(p[2] - p[3] * squash_z for p in pts_r)
        z_cut = z_floor + min(p[3] for p in pts_r) * 0.22
        if u_seg is None:
            u_s = 10 if self.low_poly else (14 if smooth_iters >= 2 else 12)
        else:
            u_s = max(6, int(u_seg))
        if v_seg is None:
            v_s = 6 if self.low_poly else (10 if smooth_iters >= 2 else 8)
        else:
            v_s = max(4, int(v_seg))

        bm = bmesh.new()
        for px, py, pz, pr in pts_r:
            sub = bmesh.new()
            bmesh.ops.create_uvsphere(sub, u_segments=u_s, v_segments=v_s, radius=float(pr))
            bmesh.ops.scale(sub, vec=(1.05, 0.96, float(squash_z)), verts=sub.verts)
            bmesh.ops.translate(sub, vec=(float(px), float(py), float(pz)), verts=sub.verts)
            if flat_bottom:
                for v in sub.verts:
                    if v.co.z < z_cut:
                        v.co.z = z_cut - (z_cut - v.co.z) * 0.18
            me_tmp = bpy.data.meshes.new("_ks_cld_tmp")
            sub.to_mesh(me_tmp)
            sub.free()
            bm.from_mesh(me_tmp)
            bpy.data.meshes.remove(me_tmp)
        return self._add_bm("pcloud", bm, role, world, uv_kind="box")

    def plush_cloud_pillow(
        self,
        w,
        d,
        h=0.20,
        loc=(0.0, 0.0, 0.0),
        role="cream",
        puffs=None,
        flat_bottom=True,
        M=None,
    ):
        """Ready-made lush oval/rectangular studio cloud cushion base (low_poly: 6-7 puffs u=10,v=6!)."""
        hw, hd = float(w) * 0.5, float(d) * 0.5
        base_r = max(0.08, float(h) * 0.72)
        n = int(puffs) if puffs is not None else (6 if self.low_poly else 10)
        if self.low_poly:
            n = max(5, min(n, 8))
        else:
            n = max(6, n)
        pts = [(0.0, 0.0, base_r * 0.45, max(base_r * 1.15, min(hw, hd) * 0.62))]
        for i in range(n):
            a = math.tau * i / float(n)
            sw = 1.0 + 0.14 * math.cos(i * 2.0)
            rx = max(0.02, hw - base_r * 0.52) * math.cos(a)
            ry = max(0.02, hd - base_r * 0.52) * math.sin(a)
            pr = base_r * (0.88 + 0.12 * (1 if i % 2 == 0 else -1)) * sw
            pz = base_r * (0.48 + 0.08 * (1 if i % 2 == 0 else 0))
            pts.append((rx, ry, pz, pr))
        return self.plush_cloud(
            pts, loc=loc, role=role, flat_bottom=flat_bottom, squash_z=0.76,
            u_seg=10 if self.low_poly else None, v_seg=6 if self.low_poly else None, M=M,
        )

    def plush_cloud_ring(
        self,
        radius,
        z=0.0,
        puff_r=0.14,
        n_puffs=None,
        role="cream",
        flat_bottom=False,
        M=None,
    ):
        """360-degree scalloped fluffy cloud ring (low_poly: 8 puffs u=8, v=6 ~ 640 tris!)."""
        n = int(n_puffs) if n_puffs is not None else (8 if self.low_poly else 12)
        if self.low_poly:
            n = max(6, min(n, 10))
        else:
            n = max(6, n)
        pts = []
        for i in range(n):
            a = math.tau * i / float(n)
            sw = 1.08 if i % 2 == 0 else 0.94
            dz = puff_r * (0.08 if i % 2 == 0 else -0.04)
            pts.append((float(radius) * math.cos(a), float(radius) * math.sin(a), float(z) + dz, float(puff_r) * sw))
        return self.plush_cloud(
            pts, role=role, flat_bottom=flat_bottom, squash_z=0.80,
            u_seg=8 if self.low_poly else None, v_seg=6 if self.low_poly else None, M=M,
        )

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
        """Clean low-poly plump pillowy 5-pointed Pop-Mart star (~60 tris in low_poly!)."""
        s = float(size)
        th = float(thick) if thick is not None else s * 0.44
        n_pts = max(4, int(points))
        r_out = s
        r_in = s * (0.48 if n_pts == 5 else 0.40)

        if self.low_poly:
            ring_pts = []
            half_step = math.pi / float(n_pts)
            for i in range(n_pts):
                a_tip = math.pi * 0.5 + math.tau * i / float(n_pts)
                a_l = a_tip - half_step * 0.18
                a_r = a_tip + half_step * 0.18
                a_v = a_tip + half_step
                ring_pts.append((r_out * 0.95 * math.cos(a_l), r_out * 0.95 * math.sin(a_l)))
                ring_pts.append((r_out * 0.95 * math.cos(a_r), r_out * 0.95 * math.sin(a_r)))
                ring_pts.append((r_in * math.cos(a_v), r_in * math.sin(a_v)))
            m = len(ring_pts)
            bm = bmesh.new()
            eq_f = [bm.verts.new((x, -th * 0.22, z)) for (x, z) in ring_pts]
            eq_b = [bm.verts.new((x, th * 0.22, z)) for (x, z) in ring_pts]
            apex_f = bm.verts.new((0.0, -th * 0.52, 0.0))
            apex_b = bm.verts.new((0.0, th * 0.52, 0.0))
            for i in range(m):
                j = (i + 1) % m
                bm.faces.new((eq_b[i], eq_b[j], eq_f[j], eq_f[i]))
                bm.faces.new((eq_f[i], eq_f[j], apex_f))
                bm.faces.new((eq_b[j], eq_b[i], apex_b))
        else:
            raw = []
            for i in range(n_pts * 2):
                a = math.pi * 0.5 + math.pi * i / float(n_pts)
                r = r_out if i % 2 == 0 else r_in
                raw.append((r * math.cos(a), r * math.sin(a)))
            ring_pts = _chaikin_closed(raw, iters=2)
            m = len(ring_pts)
            bm = bmesh.new()
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
        return self._add_bm("pstar", bm, role, world, uv_kind="box")

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
        """Plump low-poly pillowy 3D heart charm (~56 tris in low_poly!)."""
        s = float(size)
        th = float(thick) if thick is not None else s * 0.48
        m = 14 if self.low_poly else 28
        ring_pts = []
        for i in range(m):
            t = math.tau * i / float(m)
            x = 16.0 * (math.sin(t) ** 3)
            z = 13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t)
            ring_pts.append((x * s / 17.0, (z + 1.5) * s / 17.0))

        bm = bmesh.new()
        if self.low_poly:
            eq_f = [bm.verts.new((x, -th * 0.24, z)) for (x, z) in ring_pts]
            eq_b = [bm.verts.new((x, th * 0.24, z)) for (x, z) in ring_pts]
            apex_f = bm.verts.new((0.0, -th * 0.54, s * 0.06))
            apex_b = bm.verts.new((0.0, th * 0.54, s * 0.06))
            for i in range(m):
                j = (i + 1) % m
                bm.faces.new((eq_b[i], eq_b[j], eq_f[j], eq_f[i]))
                bm.faces.new((eq_f[i], eq_f[j], apex_f))
                bm.faces.new((eq_b[j], eq_b[i], apex_b))
        else:
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
        return self._add_bm("pheart", bm, role, world, uv_kind="box")

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
        return self.plush_extrude(pts, depth=th, role=role, bevel=th * 0.30, bevel_segs=1, M=world)

    def cafe_awning(
        self,
        w,
        d,
        h,
        loc=(0.0, 0.0, 0.0),
        stripe_role="caramel",
        alt_role="cream",
        trim_role="cocoa",
        bead_role="gold",
        scallops=6,
        rot=(0.0, 0.0, 0.0),
        M=None,
    ):
        """V13 Edge-Craft Curved Café Canopy + Espresso-Cocoa Edge Piping + Golden Scalloped Trim Beads."""
        ww, dd, hh = float(w), float(d), float(h)
        n = max(4, int(scallops))
        if stripe_role in STRIPE_ROLES:
            col_role_a = resolve_role(stripe_role.replace("stripe_", ""))
            col_role_b = resolve_role(alt_role)
        else:
            col_role_a = resolve_role(stripe_role)
            col_role_b = resolve_role(alt_role)

        world = (M or Matrix.Identity(4)) @ trs(loc, rot)
        rib_w = ww / float(n)
        t_roof = max(0.016, min(dd, hh) * 0.085)
        t_valance = max(0.012, t_roof * 0.72)
        petal_h = max(0.055, min(rib_w * 0.52, hh * 0.44))

        def _arch_yz(u):
            ang = u * math.pi * 0.5
            y = dd * 0.5 - dd * math.sin(ang)
            z = -hh * 0.5 + hh * math.cos(ang)
            ny = -math.cos(ang) * hh
            nz = math.sin(ang) * dd
            ln = max(1e-5, math.hypot(ny, nz))
            return y, z, (ny / ln, nz / ln)

        bms = {col_role_a: bmesh.new(), col_role_b: bmesh.new()}
        n_u = 5
        n_arc = 6
        y_front = -dd * 0.5 - t_valance * 0.5
        y_back = -dd * 0.5 + t_valance * 0.5
        z_eave = -hh * 0.5 + t_roof * 0.15

        bead_centers = []
        for i in range(n):
            role = col_role_a if (i % 2 == 0) else col_role_b
            bm = bms[role]
            x0 = -ww * 0.5 + i * rib_w
            x1 = x0 + rib_w
            xm = 0.5 * (x0 + x1)

            top_rows = []
            bot_rows = []
            for iu in range(n_u):
                u = iu / float(n_u - 1)
                yc, zc, (ny, nz) = _arch_yz(u)
                r_t = []
                r_b = []
                for ix, x in enumerate((x0, xm, x1)):
                    crown = t_roof * 0.28 if ix == 1 else 0.0
                    r_t.append(bm.verts.new((x, yc + ny * (t_roof * 0.5 + crown), zc + nz * (t_roof * 0.5 + crown))))
                    r_b.append(bm.verts.new((x, yc - ny * (t_roof * 0.5), zc - nz * (t_roof * 0.5))))
                top_rows.append(r_t)
                bot_rows.append(r_b)

            for iu in range(n_u - 1):
                for ix in range(2):
                    bm.faces.new((top_rows[iu][ix], top_rows[iu][ix + 1], top_rows[iu + 1][ix + 1], top_rows[iu + 1][ix]))
                    bm.faces.new((bot_rows[iu][ix + 1], bot_rows[iu][ix], bot_rows[iu + 1][ix], bot_rows[iu + 1][ix + 1]))
            if i == 0:
                for iu in range(n_u - 1):
                    bm.faces.new((bot_rows[iu][0], top_rows[iu][0], top_rows[iu + 1][0], bot_rows[iu + 1][0]))
            if i == n - 1:
                for iu in range(n_u - 1):
                    bm.faces.new((top_rows[iu][-1], bot_rows[iu][-1], bot_rows[iu + 1][-1], top_rows[iu + 1][-1]))
            for ix in range(2):
                bm.faces.new((bot_rows[0][ix], bot_rows[0][ix + 1], top_rows[0][ix + 1], top_rows[0][ix]))

            rad_x = rib_w * 0.495
            arc_pts = []
            for k in range(n_arc + 1):
                a = math.pi * (1.0 - k / float(n_arc))
                arc_pts.append((xm + rad_x * math.cos(a), z_eave - petal_h * math.sin(a)))

            f_top_l = bm.verts.new((x0, y_front, z_eave))
            f_top_m = bm.verts.new((xm, y_front, z_eave))
            f_top_r = bm.verts.new((x1, y_front, z_eave))
            b_top_l = bm.verts.new((x0, y_back, z_eave))
            b_top_m = bm.verts.new((xm, y_back, z_eave))
            b_top_r = bm.verts.new((x1, y_back, z_eave))

            f_arc = [bm.verts.new((px, y_front, pz)) for (px, pz) in arc_pts]
            b_arc = [bm.verts.new((px, y_back, pz)) for (px, pz) in arc_pts]
            for k in range(n_arc):
                bm.faces.new((f_top_m, f_arc[k], f_arc[k + 1]))
                bm.faces.new((b_top_m, b_arc[k + 1], b_arc[k]))
                bm.faces.new((f_arc[k], b_arc[k], b_arc[k + 1], f_arc[k + 1]))
            bm.faces.new((f_top_l, f_arc[0], f_top_m))
            bm.faces.new((f_top_m, f_arc[-1], f_top_r))
            bm.faces.new((b_top_m, b_arc[0], b_top_l))
            bm.faces.new((b_top_r, b_arc[-1], b_top_m))
            bead_centers.append((xm, -dd * 0.5 - t_valance * 0.25, z_eave - petal_h))

        for role, bm in bms.items():
            if len(bm.faces) > 0:
                self._add_bm("awning_" + role, bm, role, world, uv_kind="box")
            else:
                bm.free()

        # Crisp Espresso-Cocoa top rod, front eave trim rail & curved side piping rails
        if trim_role:
            rod_r = max(0.013, t_roof * 0.72)
            self.plush_cyl(
                rod_r,
                ww + rod_r * 2.4,
                loc=(0.0, dd * 0.5, hh * 0.5 + rod_r * 0.22),
                role=trim_role,
                bevel=rod_r * 0.35,
                segs=8,
                axis="X",
                M=world,
            )
            # Front eave espresso piping rail neatly dividing the arched canopy from the scalloped valance!
            self.plush_cyl(
                rod_r * 0.68,
                ww + rod_r * 2.2,
                loc=(0.0, -dd * 0.5 - t_valance * 0.35, z_eave + rod_r * 0.12),
                role=trim_role,
                bevel=rod_r * 0.28,
                segs=8,
                axis="X",
                M=world,
            )
            for sx in (-1.0, 1.0):
                pts_side = []
                for iu in range(n_u):
                    yc, zc, _ = _arch_yz(iu / float(n_u - 1))
                    pts_side.append((sx * (ww * 0.5 + rod_r * 0.22), yc, zc))
                self.plush_tube(pts_side, rod_r * 0.78, role=trim_role, segs=6, smooth_steps=0, M=world)

        # Gleaming Sunny-Gold scalloped trim beads along the front arched café valance (combined bmesh!)
        if bead_role and bead_centers:
            bead_r = max(0.013, min(petal_h * 0.24, rib_w * 0.13))
            bm_b = bmesh.new()
            for bx, by, bz in bead_centers:
                sub = bmesh.new()
                bmesh.ops.create_uvsphere(sub, u_segments=6, v_segments=4, radius=bead_r)
                bmesh.ops.translate(sub, vec=(bx, by, bz), verts=sub.verts)
                mt = bpy.data.meshes.new("_ks_bead_tmp")
                sub.to_mesh(mt)
                sub.free()
                bm_b.from_mesh(mt)
                bpy.data.meshes.remove(mt)
            self._add_bm("awning_beads", bm_b, bead_role, world, uv_kind="box")

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
        detail="low",
        pose=None,
        use_sculpted=True,
    ):
        """V16 True Organic Sculpted 3D Billie Bear (`full` / `head` / `peek`) with Cycles-baked 1024px plush-vinyl atlas!
        Falls back to procedural builder only if sculpted library is unavailable or non-brown recolor requested."""
        r = float(radius)
        sch = str(school).lower()
        if sch not in ("brown", "pink", "skyblue", "grey"):
            sch = "brown"

        group = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0.0, 0.0, 0.0), rot)

        # V17: Pure Quad-Flow 4-House Billie School Mascots (`brown` Bear, `pink` Lop-Bunny, `skyblue` Floppy-Puppy, `grey` Tabby-Kitty)!
        # ZERO voxel-decimate jelly soup, ZERO blurry Smart-UV scraps, direct 512px per-house crisp face!
        if use_sculpted:
            import billie_v7_assets as _v7
            pose_key = str(pose).lower() if pose else ("full" if with_body else "head")
            _v7.add_billie_mascot_v7(
                self,
                house=sch,
                pose=pose_key,
                loc=loc,
                radius=r,
                rot=rot,
                direction=direction,
                M=M,
                with_cloud=with_cloud,
            )
            return

        pal_map = {
            "brown": ("caramel", "latte", "walnut", "honey", "blush"),
            "pink": ("pink", "pink_soft", "pink_mid", "hair_pink", "blush"),
            "skyblue": ("sky", "pink_soft", "sky_deep", "sky_soft", "blush"),
            "grey": ("grey", "pink_soft", "slate", "honey", "blush"),
        }
        hood_role, ear_in_role, trim_role, bangs_role, blush_role = pal_map[sch]
        is_high = str(detail).lower() == "high"
        lp = not is_high

        def _add_revolved_y(profile_ry, sx_s, sz_s, offset, segs, role, tag, world_m):
            """Build a watertight Y-revolved mesh from [(rad, y), ...] (rad=0 ends form pole caps)."""
            n_s = max(6, int(segs))
            bm = bmesh.new()
            rings = []
            ox, oy, oz = offset
            for rad, yp in profile_ry:
                if rad < 1e-5:
                    rings.append([bm.verts.new((ox, oy + yp, oz))])
                else:
                    ring = []
                    for i in range(n_s):
                        a = math.tau * i / float(n_s)
                        ring.append(bm.verts.new((ox + rad * sx_s * math.cos(a), oy + yp, oz + rad * sz_s * math.sin(a))))
                    rings.append(ring)
            for k in range(len(rings) - 1):
                r0, r1 = rings[k], rings[k + 1]
                if len(r0) == 1 and len(r1) == 1:
                    continue
                elif len(r0) == 1:
                    for i in range(n_s):
                        j = (i + 1) % n_s
                        bm.faces.new((r0[0], r1[i], r1[j]))
                elif len(r1) == 1:
                    for i in range(n_s):
                        j = (i + 1) % n_s
                        bm.faces.new((r0[i], r1[0], r0[j]))
                else:
                    for i in range(n_s):
                        j = (i + 1) % n_s
                        bm.faces.new((r0[i], r1[i], r1[j], r0[j]))
            return self._add_bm(tag, bm, role, world_m, uv_kind="cyl")

        def _add_sparkle_4pt(center, size, thick, role, rot_eul, world_m):
            """Build a crisp 16-tri 3D faceted 4-point white sparkle / flower hairclip."""
            bm = bmesh.new()
            r_o = float(size)
            r_i = r_o * 0.34
            th = float(thick) * 0.5
            ring = []
            for k in range(8):
                a = math.pi * 0.25 * k
                rad = r_o if (k % 2 == 0) else r_i
                ring.append(bm.verts.new((rad * math.cos(a), 0.0, rad * math.sin(a))))
            vf = bm.verts.new((0.0, -th, 0.0))
            vb = bm.verts.new((0.0, th, 0.0))
            for k in range(8):
                kn = (k + 1) % 8
                bm.faces.new((ring[k], ring[kn], vf))
                bm.faces.new((ring[kn], ring[k], vb))
            wm = world_m @ trs(center, rot_eul)
            return self._add_bm("hclip", bm, role, wm, uv_kind="box")

        def _add_sharp_leaf(world_m, length, width, thick, role):
            """Build a crisp 8-tri 3D sculpted diamond-lanceolate leaf blade."""
            bm = bmesh.new()
            v_base = bm.verts.new((0.0, 0.0, 0.0))
            v_tip = bm.verts.new((length, 0.0, length * 0.14))
            v_l = bm.verts.new((length * 0.42, -width * 0.5, length * 0.12))
            v_r = bm.verts.new((length * 0.42, width * 0.5, length * 0.12))
            v_top = bm.verts.new((length * 0.44, 0.0, length * 0.14 + thick * 0.60))
            v_bot = bm.verts.new((length * 0.44, 0.0, length * 0.10 - thick * 0.45))
            bm.faces.new((v_base, v_l, v_top))
            bm.faces.new((v_base, v_top, v_r))
            bm.faces.new((v_tip, v_top, v_l))
            bm.faces.new((v_tip, v_r, v_top))
            bm.faces.new((v_base, v_bot, v_l))
            bm.faces.new((v_base, v_r, v_bot))
            bm.faces.new((v_tip, v_l, v_bot))
            bm.faces.new((v_tip, v_bot, v_r))
            return self._add_bm("bleaf", bm, role, world_m, uv_kind="box")

        # Face opening center & dome geometry (generous forehead above for bear face, snug chin below)
        z_face = -0.065 * r
        y_face_base = -0.605 * r
        rx_dome = 0.725 * r
        rz_dome = 0.640 * r
        ry_dome = 0.210 * r

        def _face_dome_y(x_pos, z_pos):
            ux = x_pos / max(1e-5, rx_dome)
            uz = (z_pos - z_face) / max(1e-5, rz_dome)
            r2 = min(0.98, ux * ux + uz * uz)
            return y_face_base - ry_dome * math.sqrt(max(0.0, 1.0 - 0.96 * r2))

        # 1. Unified Silky Tailored Hood Shell (smooth profile angles < 26 deg -> silky vinyl under crease_deg=32!)
        n_hood = 18 if is_high else 14
        if is_high:
            hood_prof = [
                (0.0, 0.96 * r, 0.0),
                (0.46 * r, 0.87 * r, 0.0),
                (0.82 * r, 0.60 * r, 0.0),
                (1.01 * r, 0.22 * r, -0.01 * r),
                (1.04 * r, -0.16 * r, -0.025 * r),
                (0.94 * r, -0.50 * r, -0.050 * r),
                (0.75 * r, -0.66 * r, -0.065 * r),
                (0.0, -0.42 * r, -0.065 * r),
            ]
        else:
            hood_prof = [
                (0.0, 0.96 * r, 0.0),
                (0.54 * r, 0.83 * r, 0.0),
                (0.94 * r, 0.42 * r, 0.0),
                (1.04 * r, -0.06 * r, -0.020 * r),
                (0.93 * r, -0.48 * r, -0.050 * r),
                (0.75 * r, -0.66 * r, -0.065 * r),
                (0.0, -0.42 * r, -0.065 * r),
            ]
        bm_h = bmesh.new()
        h_rings = []
        for rad, yp, z_sh in hood_prof:
            if rad < 1e-5:
                h_rings.append([bm_h.verts.new((0.0, 0.06 * r + yp, z_sh))])
            else:
                ring = []
                for i in range(n_hood):
                    a = math.tau * i / float(n_hood)
                    ring.append(bm_h.verts.new((
                        rad * 1.05 * math.cos(a),
                        0.06 * r + yp,
                        z_sh + rad * 0.96 * math.sin(a),
                    )))
                h_rings.append(ring)
        for k in range(len(h_rings) - 1):
            r0, r1 = h_rings[k], h_rings[k + 1]
            if len(r0) == 1:
                for i in range(n_hood):
                    j = (i + 1) % n_hood
                    bm_h.faces.new((r0[0], r1[i], r1[j]))
            elif len(r1) == 1:
                for i in range(n_hood):
                    j = (i + 1) % n_hood
                    bm_h.faces.new((r0[i], r1[0], r0[j]))
            else:
                for i in range(n_hood):
                    j = (i + 1) % n_hood
                    bm_h.faces.new((r0[i], r1[i], r1[j], r0[j]))
        self._add_bm("bhood", bm_h, hood_role, group, uv_kind="cyl")

        # 2. Sleek Dark-Espresso Inner Piping Trim Collar (seg_major=18 high / 14 low, r_minor=0.055*r, crisp rim!)
        n_pipe = 18 if is_high else 14
        pipe_rx = 0.745 * r
        pipe_rz = 0.665 * r
        p_rad = 0.055 * r
        pipe_cs = [
            (0.85 * p_rad, -0.82 * p_rad),
            (-0.88 * p_rad, -0.88 * p_rad),
            (0.05 * p_rad, 0.95 * p_rad),
        ]
        bm_p = bmesh.new()
        p_rings = []
        for i in range(n_pipe):
            a = math.tau * i / float(n_pipe)
            ca, sa = math.cos(a), math.sin(a)
            ring = []
            for dr, dy in pipe_cs:
                ring.append(bm_p.verts.new((
                    (pipe_rx + dr) * ca,
                    -0.610 * r + dy,
                    z_face + (pipe_rz + dr) * sa,
                )))
            p_rings.append(ring)
        for i in range(n_pipe):
            r0 = p_rings[i]
            r1 = p_rings[(i + 1) % n_pipe]
            for c_i in range(len(pipe_cs)):
                c_n = (c_i + 1) % len(pipe_cs)
                bm_p.faces.new((r0[c_i], r1[c_i], r1[c_n], r0[c_n]))
        pipe_role = "espresso" if sch == "brown" else trim_role
        self._add_bm("bpipe", bm_p, pipe_role, group, uv_kind="torus")

        # 3. REAL SCULPTED 3D LAYERED HAIR BANGS (sealed 100% INSIDE espresso hood rim -> sweeping down into lush sculpted locks!)
        if sch == "brown" or face_mode != "illustrated":
            bm_bg = bmesh.new()
            # (ang_top_deg, mid_x, mid_z, bot_x, bot_z, mid_loft, bot_loft)
            bang_cols = [
                (172.0, -0.66, 0.06, -0.63, -0.05, 0.025, 0.018),   # 0: Left outer edge sealed into rim
                (156.0, -0.57, 0.16, -0.56, -0.03, 0.055, 0.032),   # 1: Left temple lock tip
                (142.0, -0.45, 0.28, -0.42, 0.19, 0.042, 0.020),    # 2: Notch
                (122.0, -0.28, 0.30, -0.26, 0.095, 0.078, 0.036),   # 3: Left-center bang tip (above left eye!)
                (104.0, -0.11, 0.33, -0.10, 0.21, 0.050, 0.022),    # 4: Part notch
                (88.0, 0.03, 0.31, 0.02, 0.075, 0.086, 0.040),      # 5: Hero center wavy bang tip (between eyes!)
                (70.0, 0.18, 0.33, 0.17, 0.21, 0.050, 0.022),       # 6: Part notch
                (54.0, 0.32, 0.30, 0.30, 0.105, 0.078, 0.036),      # 7: Right-center bang tip (above right eye!)
                (38.0, 0.46, 0.27, 0.43, 0.19, 0.042, 0.020),       # 8: Notch
                (24.0, 0.57, 0.16, 0.56, -0.03, 0.055, 0.032),      # 9: Right temple lock tip
                (8.0, 0.66, 0.06, 0.63, -0.05, 0.025, 0.018),       # 10: Right outer edge sealed into rim
            ]
            top_f, mid_f, bot_f = [], [], []
            top_b, bot_b = [], []
            for ang_d, mx, mz, bx, bz, ml, bl in bang_cols:
                a = math.radians(ang_d)
                # Top hairline seals cleanly INTO the espresso piping center (`0.735*r, 0.655*r`, ZERO skin sliver!)
                tx = 0.735 * r * math.cos(a)
                tz = z_face + 0.655 * r * math.sin(a)
                yt = _face_dome_y(tx, tz)
                yt_f = max(yt - 0.016 * r, -0.636 * r)
                top_f.append(bm_bg.verts.new((tx, yt_f, tz)))
                top_b.append(bm_bg.verts.new((tx, yt + 0.038 * r, tz)))

                ym = _face_dome_y(mx * r, mz * r)
                mid_f.append(bm_bg.verts.new((mx * r, ym - ml * r, mz * r)))

                yb = _face_dome_y(bx * r, bz * r)
                bot_f.append(bm_bg.verts.new((bx * r, yb - bl * r, bz * r)))
                bot_b.append(bm_bg.verts.new((bx * r, yb + 0.026 * r, bz * r)))

            nc = len(bang_cols) - 1
            for i in range(nc):
                bm_bg.faces.new((top_f[i], mid_f[i], mid_f[i + 1], top_f[i + 1]))
                bm_bg.faces.new((mid_f[i], bot_f[i], bot_f[i + 1], mid_f[i + 1]))
                bm_bg.faces.new((top_b[i + 1], bot_b[i + 1], bot_b[i], top_b[i]))
                bm_bg.faces.new((top_f[i + 1], top_b[i + 1], top_b[i], top_f[i]))
                bm_bg.faces.new((bot_f[i], bot_b[i], bot_b[i + 1], bot_f[i + 1]))
            bm_bg.faces.new((top_f[0], top_b[0], bot_b[0], bot_f[0], mid_f[0]))
            bm_bg.faces.new((top_f[-1], mid_f[-1], bot_f[-1], bot_b[-1], top_b[-1]))
            self._add_bm("bbangs", bm_bg, bangs_role, group, uv_kind="box")

            # 2 cute tiny 3D white 4-point sparkle/flower hairclips perched cleanly on the bangs!
            for cx_s, cz_s, c_sz, rot_z_c in (
                (0.31, 0.33, 0.105, 0.20),
                (-0.29, 0.36, 0.078, -0.22),
            ):
                cy_s = _face_dome_y(cx_s * r, cz_s * r) - 0.088 * r
                _add_sparkle_4pt(
                    (cx_s * r, cy_s, cz_s * r),
                    size=c_sz * r,
                    thick=0.044 * r,
                    role="white",
                    rot_eul=(-0.28, rot_z_c, -cx_s * 0.40),
                    world_m=group,
                )

        # 4. Signature Ears, Hood Forehead Face (`• ᴥ •`), Ribbed Tangerine & Pleated Bow-Tie
        if sch == "brown":
            # A. Cupped Sculpted Bear Ears (espresso contour rim + caramel cup + full concave cream inner ear!)
            ear_segs = 12 if is_high else 10
            for sx in (-1.0, 1.0):
                em = group @ trs((sx * r * 0.77, r * 0.04, r * 0.76), (-0.10, sx * 0.28, 0.0))
                _add_revolved_y(
                    [
                        (0.0, 0.10 * r),
                        (0.378 * r, 0.015 * r),
                        (0.372 * r, -0.055 * r),
                        (0.0, 0.015 * r),
                    ],
                    sx_s=1.04,
                    sz_s=0.96,
                    offset=(0.0, 0.0, 0.0),
                    segs=ear_segs,
                    role="espresso",
                    tag="bear_trim",
                    world_m=em,
                )
                _add_revolved_y(
                    [
                        (0.0, 0.165 * r),
                        (0.348 * r, 0.045 * r),
                        (0.348 * r, -0.082 * r),
                        (0.235 * r, -0.098 * r),
                        (0.0, -0.012 * r),
                    ],
                    sx_s=1.04,
                    sz_s=0.96,
                    offset=(0.0, 0.0, 0.0),
                    segs=ear_segs,
                    role=hood_role,
                    tag="bear_cup",
                    world_m=em,
                )
                _add_revolved_y(
                    [
                        (0.0, -0.024 * r),
                        (0.228 * r, -0.096 * r),
                        (0.0, -0.062 * r),
                    ],
                    sx_s=1.02,
                    sz_s=0.94,
                    offset=(0.0, 0.0, 0.0),
                    segs=ear_segs,
                    role=ear_in_role,
                    tag="bear_in",
                    world_m=em,
                )

            # B. Authentic Bear Hood Forehead Face (`• ᴥ •`): smooth oval walnut snout + cute crisp espresso T-nose + 2 glossy bead eyes!
            snout_m = group @ trs((0.0, -0.535 * r, 0.760 * r), (-0.54, 0.0, 0.0))
            _add_revolved_y(
                [
                    (0.0, 0.04 * r),
                    (0.185 * r, 0.0),
                    (0.165 * r, -0.068 * r),
                    (0.0, -0.092 * r),
                ],
                sx_s=1.22,
                sz_s=0.88,
                offset=(0.0, 0.0, 0.0),
                segs=12 if is_high else 10,
                role=trim_role,
                tag="bsnout",
                world_m=snout_m,
            )
            # Cute crisp espresso T-nose (dainty nose cap + slim vertical stem)
            self.plush_box(
                (0.092 * r, 0.034 * r, 0.044 * r),
                (0.0, -0.092 * r, 0.032 * r),
                "espresso",
                r_bevel=0.0,
                puff=0.0,
                M=snout_m,
            )
            self.plush_box(
                (0.024 * r, 0.030 * r, 0.084 * r),
                (0.0, -0.088 * r, -0.018 * r),
                "espresso",
                r_bevel=0.0,
                puff=0.0,
                M=snout_m,
            )
            # 2 cute tiny glossy espresso bead eyes flanking the snout (`• ᴥ •`)
            for sx in (-1.0, 1.0):
                self.plush_sphere(
                    r * 0.060,
                    (sx * r * 0.285, -0.495 * r, 0.775 * r),
                    "espresso",
                    scale=(1.0, 0.72, 1.05),
                    u=6,
                    v=3,
                    M=group,
                )

            # C. Sculpted 6-Segment Fluted/Ribbed Tangerine Topper seated SNUG on hood crown + Tiny Dark Stem + 2 Sharp Angled Leaf Blades!
            if with_orange:
                tm = group @ Matrix.Translation((0.0, -0.015 * r, 0.905 * r))
                bm_t = bmesh.new()
                n_rib = 12
                if is_high:
                    t_prof = [
                        (0.0, 0.0, 0.0),
                        (0.205 * r, 0.045 * r, 0.07),
                        (0.268 * r, 0.145 * r, 0.09),
                        (0.242 * r, 0.245 * r, 0.09),
                        (0.140 * r, 0.310 * r, 0.06),
                        (0.0, 0.282 * r, 0.0),
                    ]
                else:
                    t_prof = [
                        (0.0, 0.0, 0.0),
                        (0.245 * r, 0.090 * r, 0.09),
                        (0.255 * r, 0.215 * r, 0.09),
                        (0.140 * r, 0.308 * r, 0.06),
                        (0.0, 0.282 * r, 0.0),
                    ]
                t_rings = []
                for rad, zp, rib_amp in t_prof:
                    if rad < 1e-5:
                        t_rings.append([bm_t.verts.new((0.0, 0.0, zp))])
                    else:
                        ring = []
                        for i in range(n_rib):
                            a = math.tau * i / float(n_rib)
                            flute = 1.0 + rib_amp if (i % 2 == 0) else (1.0 - rib_amp)
                            ring.append(bm_t.verts.new((rad * flute * math.cos(a), rad * flute * math.sin(a), zp)))
                        t_rings.append(ring)
                for k in range(len(t_rings) - 1):
                    r0, r1 = t_rings[k], t_rings[k + 1]
                    if len(r0) == 1:
                        for i in range(n_rib):
                            j = (i + 1) % n_rib
                            bm_t.faces.new((r0[0], r1[j], r1[i]))
                    elif len(r1) == 1:
                        for i in range(n_rib):
                            j = (i + 1) % n_rib
                            bm_t.faces.new((r0[i], r0[j], r1[0]))
                    else:
                        for i in range(n_rib):
                            j = (i + 1) % n_rib
                            bm_t.faces.new((r0[i], r0[j], r1[j], r1[i]))
                self._add_bm("btang", bm_t, "orange", tm, uv_kind="cyl")
                self.plush_cyl(r * 0.024, r * 0.095, (0.0, 0.0, r * 0.320), "espresso", bevel=0.0, r_top=r * 0.015, segs=5, M=tm)
                for sx, yaw in ((-1.0, -0.22), (1.0, 0.26)):
                    lm = tm @ trs((0.0, 0.0, r * 0.330), (0.14, -0.34 if sx > 0 else 0.34, yaw + (math.pi if sx < 0 else 0.0)))
                    _add_sharp_leaf(lm, length=0.26 * r, width=0.125 * r, thick=0.040 * r, role="sage_warm")

            # D. Crisp Sculpted Pleated Bow-Tie (2 angled trapezoid wings + crisp central espresso knot + 2 short ribbon tails!)
            bow_m = group @ Matrix.Translation((0.0, -0.575 * r, -0.895 * r))
            bm_bw = bmesh.new()
            for sx in (-1.0, 1.0):
                x_in = sx * 0.035 * r
                x_out = sx * 0.255 * r
                y_f = -0.052 * r
                y_b = 0.034 * r
                v_it = bm_bw.verts.new((x_in, y_f * 0.65, 0.055 * r))
                v_ib = bm_bw.verts.new((x_in, y_f * 0.65, -0.055 * r))
                v_ibk_t = bm_bw.verts.new((x_in, y_b, 0.048 * r))
                v_ibk_b = bm_bw.verts.new((x_in, y_b, -0.048 * r))
                v_ot = bm_bw.verts.new((x_out, y_f, 0.118 * r))
                v_om = bm_bw.verts.new((x_out * 0.94, y_f * 0.42, 0.0))
                v_ob = bm_bw.verts.new((x_out, y_f, -0.112 * r))
                v_obk_t = bm_bw.verts.new((x_out, y_b, 0.105 * r))
                v_obk_b = bm_bw.verts.new((x_out, y_b, -0.100 * r))
                bm_bw.faces.new((v_it, v_ot, v_om, v_ib))
                bm_bw.faces.new((v_ib, v_om, v_ob))
                bm_bw.faces.new((v_ibk_t, v_ibk_b, v_obk_b, v_obk_t))
                bm_bw.faces.new((v_it, v_ibk_t, v_obk_t, v_ot))
                bm_bw.faces.new((v_ib, v_ob, v_obk_b, v_ibk_b))
                bm_bw.faces.new((v_ot, v_obk_t, v_obk_b, v_om))
                bm_bw.faces.new((v_om, v_obk_b, v_ob))
                bm_bw.faces.new((v_it, v_ib, v_ibk_b, v_ibk_t))
                t_m = trs((sx * 0.072 * r, -0.010 * r, -0.095 * r), (0.0, sx * 0.34, 0.0))
                t_verts = [
                    t_m @ Vector((-0.036 * r, -0.018 * r, 0.060 * r)),
                    t_m @ Vector((0.036 * r, -0.018 * r, 0.060 * r)),
                    t_m @ Vector((0.048 * r, -0.018 * r, -0.055 * r)),
                    t_m @ Vector((-0.048 * r, -0.018 * r, -0.055 * r)),
                    t_m @ Vector((-0.036 * r, 0.018 * r, 0.060 * r)),
                    t_m @ Vector((0.036 * r, 0.018 * r, 0.060 * r)),
                    t_m @ Vector((0.048 * r, 0.018 * r, -0.055 * r)),
                    t_m @ Vector((-0.048 * r, 0.018 * r, -0.055 * r)),
                ]
                tv = [bm_bw.verts.new(p) for p in t_verts]
                bm_bw.faces.new((tv[0], tv[1], tv[2], tv[3]))
                bm_bw.faces.new((tv[5], tv[4], tv[7], tv[6]))
                bm_bw.faces.new((tv[0], tv[4], tv[5], tv[1]))
                bm_bw.faces.new((tv[3], tv[2], tv[6], tv[7]))
                bm_bw.faces.new((tv[1], tv[5], tv[6], tv[2]))
                bm_bw.faces.new((tv[4], tv[0], tv[3], tv[7]))
            self._add_bm("bbow", bm_bw, trim_role, bow_m, uv_kind="box")
            self.plush_box(
                (0.112 * r, 0.090 * r, 0.106 * r),
                (0.0, -0.016 * r, 0.0),
                "espresso",
                r_bevel=0.0,
                puff=0.0,
                M=bow_m,
            )

        elif sch == "pink":
            for sx in (-1.0, 1.0):
                self.plush_sphere(r * 0.28, (sx * r * 0.82, r * 0.02, r * 0.48), hood_role, scale=(0.92, 0.72, 0.82), u=8, v=5, M=group)
                em = group @ trs((sx * r * 1.02, r * 0.02, -r * 0.06), (0.06, -sx * 0.26, -sx * 0.08))
                self.plush_pill((r * 0.42, r * 0.26, r * 1.24), (0.0, 0.0, 0.0), hood_role, segs=8 if lp else 12, M=em)
                self.plush_pill((r * 0.22, r * 0.14, r * 0.90), (0.0, -r * 0.10, -r * 0.06), ear_in_role, segs=6 if lp else 10, M=em)
            self.plush_sphere(r * 0.29, (0.0, 0.0, r * 1.06), "pink_soft", scale=(1.10, 0.96, 0.88), u=10, v=6, M=group)
            for sx in (-1.0, 1.0):
                self.plush_sphere(r * 0.15, (sx * r * 0.16, -r * 0.56, -r * 0.92), "pink_mid", scale=(1.30, 0.50, 0.82), rot=(0.0, sx * 0.22, 0.0), u=6, v=3, M=group)
            self.plush_sphere(r * 0.085, (0.0, -r * 0.61, -r * 0.92), "pink_deep", u=6, v=3, M=group)

        elif sch == "skyblue":
            for sx in (-1.0, 1.0):
                self.plush_sphere(r * 0.29, (sx * r * 0.84, r * 0.02, r * 0.48), hood_role, scale=(0.95, 0.75, 0.85), u=8, v=5, M=group)
                em = group @ trs((sx * r * 1.04, r * 0.02, r * 0.02), (0.05, -sx * 0.32, -sx * 0.06))
                self.plush_pill((r * 0.46, r * 0.28, r * 1.08), (0.0, 0.0, 0.0), hood_role, segs=8 if lp else 12, M=em)
                self.plush_pill((r * 0.24, r * 0.14, r * 0.76), (0.0, -r * 0.11, -r * 0.04), ear_in_role, segs=6 if lp else 10, M=em)
            self.plush_sphere(r * 0.28, (-r * 0.04, -r * 0.06, r * 1.04), hood_role, scale=(1.22, 0.92, 0.86), rot=(0.0, 0.28, 0.0), u=10, v=6, M=group)
            self.plush_box((r * 0.26, r * 0.10, r * 0.18), (-r * 0.14, -r * 0.56, -r * 0.94), "red_collar", r_bevel=r * 0.03, bevel_segs=1, rot=(0.0, -0.18, 0.0), M=group)
            self.plush_box((r * 0.26, r * 0.10, r * 0.18), (r * 0.14, -r * 0.56, -r * 0.94), "blue_collar", r_bevel=r * 0.03, bevel_segs=1, rot=(0.0, 0.18, 0.0), M=group)

        else:
            for sx in (-1.0, 1.0):
                em = group @ trs((sx * r * 0.72, 0.0, r * 0.80), (0.0, sx * 0.28, 0.0))
                self.plush_cyl(r * 0.34, r * 0.54, (0.0, 0.0, 0.0), hood_role, bevel=r * 0.10, r_top=r * 0.10, segs=10 if lp else 14, M=em)
                self.plush_cyl(r * 0.20, r * 0.34, (0.0, -r * 0.13, -r * 0.02), ear_in_role, bevel=r * 0.05, r_top=r * 0.05, segs=8 if lp else 10, M=em)
            self.plush_star((-r * 0.42, -r * 0.76, r * 0.52), r * 0.17, role="gold", thick=r * 0.08, rot=(0.15, 0.18, 0.20), M=group)
            for sx in (-1.0, 1.0):
                self.plush_sphere(r * 0.15, (sx * r * 0.16, -r * 0.56, -r * 0.92), "lavender", scale=(1.28, 0.50, 0.84), rot=(0.0, sx * 0.20, 0.0), u=6, v=3, M=group)
            self.plush_sphere(r * 0.085, (0.0, -r * 0.62, -r * 0.92), "gold", u=6, v=3, M=group)

        # 5. Crisp 7x6 Convex Face Dome mapping billie_face_crisp_v5.png cleanly below 3D bangs & inside espresso piping!
        faces_sheet = self.art.get("faces")
        if face_mode == "illustrated" and faces_sheet and os.path.isfile(faces_sheet):
            face_m = group @ Matrix.Translation((0.0, y_face_base, z_face))
            self._add_curved_face_dome(faces_sheet, ART_UV["faces"][sch], rx_dome, rz_dome, ry_dome, face_m)
        else:
            self.plush_sphere(r * 0.72, (0.0, -r * 0.34, z_face), "skin", scale=(1.02, 0.76, 0.88), u=14, v=8, M=group)
            for sx in (-1.0, 1.0):
                ex, ey, ez = sx * r * 0.28, -r * 0.84, z_face - r * 0.08
                self.plush_sphere(r * 0.14, (ex, ey, ez), "espresso", scale=(0.98, 0.38, 1.12), u=6, v=3, M=group)
                self.plush_sphere(r * 0.052, (ex - sx * r * 0.04, ey - r * 0.05, ez + r * 0.052), "white", scale=(1.0, 0.45, 1.0), u=6, v=3, M=group)
                self.plush_sphere(r * 0.12, (sx * r * 0.46, -r * 0.79, z_face - r * 0.22), blush_role, scale=(1.25, 0.28, 0.68), u=6, v=3, M=group)

        # 6. Tailored Designer Onesie Body (`with_body=True` — ZERO stubby sausages! Bottom of slipper soles at z = -1.96*r!)
        if with_body:
            # A. Smooth silky tapered hoodie body + sculpted espresso neckline cuff
            body_prof = [
                (0.0, -r * 1.92),
                (r * 0.48, -r * 1.90),
                (r * 0.62, -r * 1.66),
                (r * 0.56, -r * 1.24),
                (r * 0.42, -r * 0.90),
                (0.0, -r * 0.84),
            ]
            torso_segs = 12 if is_high else 10
            self.lathe(body_prof, role=hood_role, segs=torso_segs, smooth_profile=0, M=group)

            # Crisp sculpted espresso neckline collar cuff wrapping neck cleanly
            self.plush_cyl(
                r * 0.46,
                r * 0.080,
                loc=(0.0, -r * 0.02, -r * 0.895),
                role="espresso" if sch == "brown" else trim_role,
                bevel=0.0,
                r_top=r * 0.42,
                segs=torso_segs,
                M=group,
            )

            # B. Smooth Taper-Matched Cream Belly Patch (proud, ZERO bottom hip clipping!) + Crisp Espresso Placket + 2 Golden Buttons!
            if sch == "brown":
                belly_m = group @ trs((0.0, -r * 0.580, -r * 1.38), (0.11, 0.0, 0.0))
                _add_revolved_y(
                    [
                        (0.0, 0.05 * r),
                        (0.285 * r, -0.012 * r),
                        (0.0, -0.068 * r),
                    ],
                    sx_s=0.94,
                    sz_s=0.94,
                    offset=(0.0, 0.0, 0.0),
                    segs=10 if is_high else 8,
                    role="latte",
                    tag="bbelly",
                    world_m=belly_m,
                )
                # Crisp espresso vertical center placket strip matching belly slope cleanly
                self.plush_box(
                    (r * 0.080, r * 0.042, r * 0.50),
                    (0.0, -r * 0.062, 0.01 * r),
                    "espresso",
                    r_bevel=0.0,
                    puff=0.0,
                    M=belly_m,
                )
                # 2 gleaming golden round shirt buttons!
                for bz in (0.12, -0.09):
                    self.plush_cyl(
                        r * 0.052,
                        r * 0.028,
                        loc=(0.0, -r * 0.090, r * bz),
                        role="gold",
                        bevel=0.0,
                        segs=6 if is_high else 5,
                        axis="Y",
                        M=belly_m,
                    )
            elif sch == "pink":
                self.plush_heart((0.0, -r * 0.60, -r * 1.42), r * 0.25, role="pink_soft", thick=r * 0.11, M=group)
            elif sch == "skyblue":
                self.plush_star((-r * 0.14, -r * 0.60, -r * 1.48), r * 0.17, role="gold", thick=r * 0.08, M=group)
            else:
                self.plush_sphere(r * 0.37, (0.0, -r * 0.46, -r * 1.40), "grey_soft", scale=(0.88, 0.46, 0.86), u=8, v=4, M=group)

            # C. Tailored Cuffed Sleeves + Expressive Waving Right Hand (with blush paw-pad!)
            cuff_role = "espresso" if sch == "brown" else {"pink": "white", "skyblue": "white", "grey": "espresso"}[sch]
            arm_segs = 8 if is_high else 6
            # Left arm: relaxed gracefully downward-forward
            am_l = group @ trs((-r * 0.56, -r * 0.10, -r * 1.24), (0.34, 0.52, 0.0))
            self.plush_cyl(r * 0.138, r * 0.44, (0.0, 0.0, 0.0), hood_role, bevel=0.0, r_top=r * 0.162, segs=arm_segs, M=am_l)
            self.plush_cyl(r * 0.150, r * 0.085, (0.0, 0.0, -r * 0.21), cuff_role, bevel=0.0, segs=arm_segs, M=am_l)
            self.plush_sphere(r * 0.122, (0.0, -r * 0.01, -r * 0.305), "skin", scale=(1.0, 0.86, 0.96), u=6, v=3, M=am_l)

            # Right arm: happily raised waving UP & OUT to the right!
            am_r = group @ trs((r * 0.58, -r * 0.14, -r * 1.12), (-0.28, 0.92, -0.08))
            self.plush_cyl(r * 0.162, r * 0.46, (0.0, 0.0, 0.0), hood_role, bevel=0.0, r_top=r * 0.138, segs=arm_segs, M=am_r)
            self.plush_cyl(r * 0.150, r * 0.085, (0.0, 0.0, r * 0.22), cuff_role, bevel=0.0, segs=arm_segs, M=am_r)
            self.plush_sphere(r * 0.134, (0.0, -r * 0.01, r * 0.325), "skin", scale=(1.08, 0.78, 1.02), u=6, v=3, M=am_r)
            # Cute little thumb nub on inner side of waving hand
            self.plush_sphere(r * 0.054, (-r * 0.105, -r * 0.02, r * 0.305), "skin", scale=(1.1, 0.85, 0.9), u=5, v=3, M=am_r)
            # Tiny rosy blush paw-pad cleanly on the front waving palm!
            self.plush_cyl(r * 0.064, r * 0.026, (0.0, -r * 0.095, r * 0.330), blush_role, bevel=0.0, segs=5, axis="Y", M=am_r)

            # D. Adorable Sculpted Bear-Face Slippers (flat espresso soles at z = -1.96*r + smooth honey uppers + twin bear ears + mini snout dot!)
            sole_segs = 8 if is_high else 6
            upper_role = "honey" if sch == "brown" else {"pink": "pink_mid", "skyblue": "sky_deep", "grey": "metal_warm"}[sch]
            sole_role = "espresso" if sch == "brown" else trim_role
            for sx in (-1.0, 1.0):
                sm = group @ trs((sx * r * 0.33, -r * 0.42, -r * 1.96), (0.0, 0.0, sx * 0.16))
                bm_sl = bmesh.new()
                s_bot = []
                s_top = []
                for i in range(sole_segs):
                    a = math.tau * i / float(sole_segs)
                    px = r * 0.215 * math.cos(a)
                    py = r * 0.285 * math.sin(a)
                    s_bot.append(bm_sl.verts.new((px, py, 0.0)))
                    s_top.append(bm_sl.verts.new((px * 0.97, py * 0.97, r * 0.072)))
                for i in range(sole_segs):
                    j = (i + 1) % sole_segs
                    bm_sl.faces.new((s_bot[i], s_bot[j], s_top[j], s_top[i]))
                bm_sl.faces.new(list(reversed(s_bot)))
                bm_sl.faces.new(s_top)
                self._add_bm("bslip_sole", bm_sl, sole_role, sm, uv_kind="box")

                bm_up = bmesh.new()
                u_r0 = []
                u_r1 = []
                for i in range(sole_segs):
                    a = math.tau * i / float(sole_segs)
                    px = r * 0.198 * math.cos(a)
                    py = r * 0.265 * math.sin(a)
                    u_r0.append(bm_up.verts.new((px, py, r * 0.068)))
                    u_r1.append(bm_up.verts.new((px * 0.72, py * 0.70 + r * 0.03, r * 0.220)))
                for i in range(sole_segs):
                    j = (i + 1) % sole_segs
                    bm_up.faces.new((u_r0[i], u_r0[j], u_r1[j], u_r1[i]))
                bm_up.faces.new(list(reversed(u_r0)))
                bm_up.faces.new(u_r1)
                self._add_bm("bslip_up", bm_up, upper_role, sm, uv_kind="box")

                # Tiny twin bear ears perched on top of each slipper toe (compact 5-seg crisp discs!)
                for ex_s in (-1.0, 1.0):
                    self.plush_cyl(
                        r * 0.066,
                        r * 0.044,
                        loc=(ex_s * r * 0.118, -r * 0.095, r * 0.235),
                        role=upper_role,
                        bevel=0.0,
                        segs=5,
                        axis="Y",
                        rot=(0.0, ex_s * 0.28, 0.0),
                        M=sm,
                    )
                # Mini espresso bear snout dot on each slipper toe
                self.plush_box(
                    (r * 0.062, r * 0.040, r * 0.044),
                    (0.0, -r * 0.255, r * 0.145),
                    "espresso",
                    r_bevel=0.0,
                    puff=0.0,
                    M=sm,
                )

            # E. Cute tiny caramel bear tail on the back!
            self.plush_sphere(
                r * 0.155,
                (0.0, r * 0.62, -r * 1.66),
                hood_role if sch == "brown" else "white",
                scale=(1.05, 0.90, 0.96),
                u=6,
                v=3,
                M=group,
            )

        # 7. Optional Fluffy Cloud Cushion Underneath
        if with_cloud:
            z_cl = -r * 2.02 if with_body else -r * 1.02
            cw = r * (2.25 if with_body else 2.10)
            self.plush_cloud_pillow(cw, r * 1.55, h=r * 0.70, loc=(0.0, 0.0, z_cl), role="cream", puffs=6, flat_bottom=True, M=group)

    def _add_curved_face_dome(self, img_path, uv_rect, rx, rz, ry, matrix):
        """Register a crisp 7x6 convex squircle-mapped 3D chibi face dome into billie_art_faces.png."""
        self.pending_cards.append({
            "kind": "face_dome",
            "image": os.path.abspath(img_path),
            "uv_rect": tuple(float(v) for v in uv_rect),
            "rx": float(rx),
            "rz": float(rz),
            "ry": float(ry),
            "matrix": matrix.copy(),
            "emissive": False,
            "transparent": False,
            "bone": self.current_bone,
        })

    def _build_stepped_plaque_frame(
        self,
        w,
        h,
        depth,
        frame_thick,
        cr,
        frame_role,
        inner_trim_role,
        double_sided,
        segs_corner,
        world,
    ):
        """Build V13 double-stepped Espresso-Cocoa outer bevel frame + inner Gold/Cream recessed trim lip (segs_corner=6!)."""
        hd = max(0.010, float(depth) * 0.5)
        ft = max(0.010, float(frame_thick))
        c_segs = max(2, int(segs_corner))

        cr_i = max(0.004, min(float(cr), min(w, h) * 0.44))
        cr_m = cr_i + ft * 0.20
        cr_o = cr_i + ft * 0.68

        pts_o = self._exact_rrect_pts(w + ft * 1.48, h + ft * 1.48, cr_o, segs_corner=c_segs)
        pts_m = self._exact_rrect_pts(w + ft * 0.44, h + ft * 0.44, cr_m, segs_corner=c_segs)
        pts_i = self._exact_rrect_pts(w, h, cr_i, segs_corner=c_segs)
        n = len(pts_o)

        y_rim = hd + 0.0096
        y_bev = hd + 0.0024
        y_floor = hd - 0.0055
        y_quad = hd + 0.0010
        y_gold_hi = hd + 0.0062
        y_gold_lo = hd + 0.0022

        # 1. Unified watertight outer Espresso-Cocoa stepped bevel plaque
        bm_f = bmesh.new()
        if double_sided:
            loops = [
                [bm_f.verts.new((x, -y_floor, z)) for (x, z) in pts_m],
                [bm_f.verts.new((x, -y_rim, z)) for (x, z) in pts_m],
                [bm_f.verts.new((x, -y_bev, z)) for (x, z) in pts_o],
                [bm_f.verts.new((x, y_bev, z)) for (x, z) in pts_o],
                [bm_f.verts.new((x, y_rim, z)) for (x, z) in pts_m],
                [bm_f.verts.new((x, y_floor, z)) for (x, z) in pts_m],
            ]
        else:
            loops = [
                [bm_f.verts.new((x, -y_floor, z)) for (x, z) in pts_m],
                [bm_f.verts.new((x, -y_rim, z)) for (x, z) in pts_m],
                [bm_f.verts.new((x, -y_bev, z)) for (x, z) in pts_o],
                [bm_f.verts.new((x, hd, z)) for (x, z) in pts_o],
            ]
        for k in range(len(loops) - 1):
            a_l, b_l = loops[k], loops[k + 1]
            for i in range(n):
                j = (i + 1) % n
                bm_f.faces.new((a_l[i], a_l[j], b_l[j], b_l[i]))
        bm_f.faces.new(loops[0])
        bm_f.faces.new(list(reversed(loops[-1])))
        self._add_bm("pframe", bm_f, frame_role, world, uv_kind="box")

        # 2. Inner Honey-Gold / Cream recessed trim lip hugging the decal perimeter cleanly
        if inner_trim_role:
            bm_g = bmesh.new()
            sides = (-1.0, 1.0) if double_sided else (-1.0,)
            for sgn in sides:
                g0 = [bm_g.verts.new((x, sgn * y_floor, z)) for (x, z) in pts_m]
                g1 = [bm_g.verts.new((x, sgn * y_gold_hi, z)) for (x, z) in pts_m]
                g2 = [bm_g.verts.new((x, sgn * y_gold_lo, z)) for (x, z) in pts_i]
                for i in range(n):
                    j = (i + 1) % n
                    if sgn < 0.0:
                        bm_g.faces.new((g0[i], g0[j], g1[j], g1[i]))
                        bm_g.faces.new((g1[i], g1[j], g2[j], g2[i]))
                        bm_g.faces.new((g2[i], g2[j], g0[j], g0[i]))
                    else:
                        bm_g.faces.new((g0[j], g0[i], g1[i], g1[j]))
                        bm_g.faces.new((g1[j], g1[i], g2[i], g2[j]))
                        bm_g.faces.new((g2[j], g2[i], g0[i], g0[j]))
            self._add_bm("ptrim", bm_g, inner_trim_role, world, uv_kind="box")

        return y_quad, cr_i, c_segs

    def decal_region(
        self,
        sheet_path,
        uv_rect,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role="cocoa",
        mat_role="cream",
        inner_trim_role="gold",
        frame_thick=0.022,
        depth=0.030,
        emissive=False,
        transparent=False,
        double_sided=False,
        corner_r=None,
        segs_corner=6,
        M=None,
    ):
        """Place a razor-sharp sub-region (uv_rect=(u0,v0,u1,v1)) with V13 double-stepped cocoa+gold plaque frame!"""
        if not sheet_path or not os.path.isfile(sheet_path):
            self.warnings.append("decal sheet missing: {}".format(sheet_path))
            return
        u0, v0, u1, v1 = [float(x) for x in uv_rect]
        if height is None:
            tmp = bpy.data.images.load(sheet_path, check_existing=True)
            iw = max(1.0, float(tmp.size[0]) * max(1e-4, abs(u1 - u0)))
            ih = max(1.0, float(tmp.size[1]) * max(1e-4, abs(v1 - v0)))
            height = float(width) * (ih / iw)
        w, h = float(width), float(height)
        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0.0, 0.0, 0.0), rot)
        cr = float(corner_r) if corner_r is not None else min(w, h) * 0.11

        y_off = 0.0
        card_kind = "quad"
        card_cr = 0.0
        card_c_segs = max(2, int(segs_corner))
        if frame_role:
            lip_role = inner_trim_role if inner_trim_role is not None else mat_role
            y_off, card_cr, card_c_segs = self._build_stepped_plaque_frame(
                w=w,
                h=h,
                depth=max(0.018, float(depth)),
                frame_thick=frame_thick,
                cr=cr,
                frame_role=frame_role,
                inner_trim_role=lip_role,
                double_sided=double_sided,
                segs_corner=card_c_segs,
                world=world,
            )
            card_kind = "rrect"

        entry = {
            "kind": card_kind,
            "image": os.path.abspath(sheet_path),
            "uv_rect": (u0, v0, u1, v1),
            "width": w,
            "height": h,
            "corner_r": card_cr,
            "segs_corner": card_c_segs,
            "matrix": world @ Matrix.Translation((0.0, -y_off, 0.0)),
            "emissive": bool(emissive),
            "transparent": bool(transparent),
            "bone": self.current_bone,
        }
        self.pending_cards.append(entry)
        if double_sided:
            back_entry = dict(entry)
            back_entry["matrix"] = world @ Matrix.Translation((0.0, y_off, 0.0)) @ Matrix.Rotation(math.pi, 4, "Z")
            self.pending_cards.append(back_entry)

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
        inner_trim_role="gold",
        frame_thick=0.022,
        depth=0.030,
        emissive=False,
        transparent=False,
        double_sided=False,
        corner_r=None,
        segs_corner=6,
        M=None,
    ):
        """Place a full standalone image (sign banner, logo badge, ATM screen) with V13 double-stepped cocoa+gold frame."""
        return self.decal_region(
            sheet_path=img_path,
            uv_rect=(0.0, 0.0, 1.0, 1.0),
            width=width,
            height=height,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            mat_role=mat_role,
            inner_trim_role=inner_trim_role,
            frame_thick=frame_thick,
            depth=depth,
            emissive=emissive,
            transparent=transparent,
            double_sided=double_sided,
            corner_r=corner_r,
            segs_corner=segs_corner,
            M=M,
        )

    def decal_disc(
        self,
        sheet_path,
        uv_rect,
        radius,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        outer_role="cocoa",
        inner_role="gold",
        backing_role="cream",
        depth=0.052,
        bezel_width=None,
        dome_depth=0.0,
        segs=24,
        emissive=False,
        transparent=False,
        double_sided=False,
        M=None,
    ):
        """Place a silky 24-seg circular/domed UV-mapped decal disc wrapped in `smooth_bezel_ring` (ZERO square corners!)."""
        if not sheet_path or not os.path.isfile(sheet_path):
            self.warnings.append("decal disc sheet missing: {}".format(sheet_path))
            return
        r = max(0.02, float(radius))
        n_seg = min(36, max(16, int(segs)))
        d = max(0.014, float(depth))
        hd = d * 0.5
        bw = float(bezel_width) if bezel_width is not None else max(0.020, r * 0.14)
        world = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ facing(direction) @ trs((0.0, 0.0, 0.0), rot)

        y_off = 0.0
        r_disc = r
        if outer_role:
            self.smooth_bezel_ring(
                r_outer=r + bw,
                r_inner=r - bw * 0.06,
                depth=d,
                loc=(0.0, 0.0, 0.0),
                outer_role=outer_role,
                inner_role=inner_role,
                axis="Y",
                segs=n_seg,
                M=world,
            )
            if backing_role and not double_sided:
                # Slim backing disc closing the rear opening of single-sided medallions/gauges
                self.plush_cyl(
                    r + bw * 0.20,
                    d * 0.36,
                    loc=(0.0, d * 0.10, 0.0),
                    role=backing_role,
                    bevel=0.0,
                    segs=n_seg,
                    axis="Y",
                    M=world,
                )
            y_off = d * 0.22 + 0.0025
            r_disc = r + bw * 0.02

        entry = {
            "kind": "disc",
            "image": os.path.abspath(sheet_path),
            "uv_rect": tuple(float(x) for x in uv_rect),
            "radius": r_disc,
            "segs": n_seg,
            "dome_depth": max(0.0, float(dome_depth)),
            "matrix": world @ Matrix.Translation((0.0, -y_off, 0.0)),
            "emissive": bool(emissive),
            "transparent": bool(transparent),
            "bone": self.current_bone,
        }
        self.pending_cards.append(entry)
        if double_sided:
            back_entry = dict(entry)
            back_entry["matrix"] = world @ Matrix.Translation((0.0, y_off, 0.0)) @ Matrix.Rotation(math.pi, 4, "Z")
            self.pending_cards.append(back_entry)

    def v4_art_panel(
        self,
        art_key,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role="cocoa",
        mat_role="cream",
        inner_trim_role="gold",
        frame_thick=0.020,
        depth=0.028,
        double_sided=False,
        corner_r=None,
        segs_corner=6,
        M=None,
    ):
        """One-liner: place any fresh V4 unified warm-brown illustration from `ART_UV_V4` in a crisp double-stepped plaque!"""
        key = str(art_key).lower().replace("art_", "")
        if key not in ART_UV_V4:
            key = "crest"
        sheet_key, uv_rect = ART_UV_V4[key]
        h = float(height) if height is not None else float(width)
        return self.decal_region(
            sheet_path=self.art[sheet_key],
            uv_rect=uv_rect,
            width=width,
            height=h,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            mat_role=mat_role,
            inner_trim_role=inner_trim_role,
            frame_thick=frame_thick,
            depth=depth,
            emissive=False,
            transparent=False,
            double_sided=double_sided,
            corner_r=corner_r,
            segs_corner=segs_corner,
            M=M,
        )

    def v4_art_medallion(
        self,
        art_key,
        radius,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        outer_role="cocoa",
        inner_role="gold",
        backing_role="cream",
        depth=0.055,
        bezel_width=None,
        dome_depth=0.0,
        segs=24,
        double_sided=False,
        M=None,
    ):
        """One-liner: place any fresh V4 unified warm-brown illustration inside a silky 24-seg `smooth_bezel_ring` medallion!"""
        key = str(art_key).lower().replace("art_", "")
        if key not in ART_UV_V4:
            key = "crest"
        sheet_key, uv_rect = ART_UV_V4[key]
        return self.decal_disc(
            sheet_path=self.art[sheet_key],
            uv_rect=uv_rect,
            radius=radius,
            loc=loc,
            rot=rot,
            direction=direction,
            outer_role=outer_role,
            inner_role=inner_role,
            backing_role=backing_role,
            depth=depth,
            bezel_width=bezel_width,
            dome_depth=dome_depth,
            segs=segs,
            emissive=False,
            transparent=False,
            double_sided=double_sided,
            M=M,
        )

    def house_poster(
        self,
        school,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role="cocoa",
        mat_role="cream",
        double_sided=False,
        M=None,
    ):
        """Backwards-compat: routes to unified V4 `crest` art panel."""
        return self.v4_art_panel(
            "crest",
            width=width,
            height=height,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            mat_role=mat_role,
            double_sided=double_sided,
            M=M,
        )

    def mascot_sticker(
        self,
        school,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role=None,
        double_sided=False,
        M=None,
    ):
        """Backwards-compat: routes to unified V4 `crest` art panel."""
        return self.v4_art_panel(
            "crest",
            width=width,
            height=height,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            double_sided=double_sided,
            M=M,
        )

    def billie_logo_badge(
        self,
        width,
        height=None,
        loc=(0.0, 0.0, 0.0),
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        frame_role="cocoa",
        mat_role="cream",
        inner_trim_role="gold",
        double_sided=False,
        segs_corner=6,
        M=None,
    ):
        """Convenience: place the ultra-crisp 1024x512 BILLIE SCHOOL cloud logo badge (2:1 aspect)."""
        h = float(height) if height is not None else float(width) * 0.5
        return self.decal_card(
            self.art["logo_badge"],
            width=width,
            height=h,
            loc=loc,
            rot=rot,
            direction=direction,
            frame_role=frame_role,
            mat_role=mat_role,
            inner_trim_role=inner_trim_role,
            transparent=False,
            double_sided=double_sided,
            segs_corner=segs_corner,
            M=M,
        )

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
        inner_trim_role="gold",
        double_sided=False,
        rot=(0.0, 0.0, 0.0),
        direction=(0.0, -1.0, 0.0),
        M=None,
    ):
        """Generate a cached razor-sharp 1024x512 unified warm-brown banner PNG and place as V13 framed decal_card."""
        h = float(height) if height is not None else float(width) * 0.5
        sig = "v13|{}|{}|{}|{}|{}|{}|{}|{}".format(
            text, subtitle, bg_hex, border_hex, text_hex, text_outline_hex, accent_hex, int(striped)
        )
        slug = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:16] or "sign"
        hsh = hashlib.md5(sig.encode("utf-8")).hexdigest()[:6]
        tex_w, tex_h = (1024, 512) if (float(width) / max(0.01, h)) >= 1.35 else (1024, 1024)
        out_png = os.path.join(self.art_dir, "custom_{}_{}.png".format(slug, hsh))
        if not os.path.isfile(out_png):
            make_text_banner(
                text,
                out_png,
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
                halftone=True,
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
            inner_trim_role=inner_trim_role,
            emissive=emissive,
            transparent=False,
            double_sided=double_sided,
            M=M,
        )
        return out_png

    # ---- Adorable Low-Poly Ready-Made Kawaii Toy Miniatures ----

    def plush_car(self, loc=(0.0, 0.0, 0.0), scale=1.0, body_role="caramel", roof_role="cream", rot=(0.0, 0.0, 0.0), M=None):
        """V15 Anti-Playdough Designer Mini Sports Car (~920 tris): chamfered body, recessed windows w/ espresso pillars, slatted gold grille, round headlight bezels, wheel arches, 18-seg tires w/ gold rims, chrome-gold bumpers & mirrors."""
        s = float(scale)
        cm = (M or Matrix.Identity(4)) @ trs(loc, rot)

        # 1. Chamfered sculpted lower sports body (front faces +X, sleek sloped hood & rear deck!)
        body_pts = [
            (-0.275 * s, 0.072 * s),
            (0.280 * s, 0.072 * s),
            (0.285 * s, 0.145 * s),
            (0.250 * s, 0.175 * s),
            (0.110 * s, 0.198 * s),
            (-0.245 * s, 0.205 * s),
            (-0.280 * s, 0.175 * s),
        ]
        self.plush_extrude(body_pts, depth=0.315 * s, loc=(0.0, 0.0, 0.0), role=body_role, bevel=0.0, M=cm)
        # Crisp cream hood racing stripe
        self.plush_box((0.145 * s, 0.068 * s, 0.012 * s), (0.178 * s, 0.0, 0.186 * s), "cream", r_bevel=0.0, puff=0.0, rot=(0.0, 0.16, 0.0), M=cm)

        # 2. Sleek Tapered Cabin: Recessed aqua_cream Windshield & Side Windows + Espresso A/B/C Pillars + Chamfered Roof!
        bm_gl = bmesh.new()
        bx0, bx1, tx0, tx1 = -0.195 * s, 0.112 * s, -0.140 * s, 0.042 * s
        by, ty = 0.132 * s, 0.106 * s
        zb, zt = 0.196 * s, 0.305 * s
        g_bot = [
            bm_gl.verts.new((bx0, -by, zb)),
            bm_gl.verts.new((bx1, -by, zb)),
            bm_gl.verts.new((bx1, by, zb)),
            bm_gl.verts.new((bx0, by, zb)),
        ]
        g_top = [
            bm_gl.verts.new((tx0, -ty, zt)),
            bm_gl.verts.new((tx1, -ty, zt)),
            bm_gl.verts.new((tx1, ty, zt)),
            bm_gl.verts.new((tx0, ty, zt)),
        ]
        bm_gl.faces.new(list(reversed(g_bot)))
        bm_gl.faces.new(g_top)
        for i in range(4):
            j = (i + 1) % 4
            bm_gl.faces.new((g_bot[i], g_bot[j], g_top[j], g_top[i]))
        self._add_bm("car_glass", bm_gl, "aqua_cream", cm, uv_kind="box")

        # Sleek chamfered trapezoid hardtop roof cap overhanging the recessed glass cleanly (12 tris!)
        bm_rf = bmesh.new()
        rf_b = [
            bm_rf.verts.new((-0.155 * s, -0.122 * s, 0.302 * s)),
            bm_rf.verts.new((0.056 * s, -0.122 * s, 0.302 * s)),
            bm_rf.verts.new((0.056 * s, 0.122 * s, 0.302 * s)),
            bm_rf.verts.new((-0.155 * s, 0.122 * s, 0.302 * s)),
        ]
        rf_t = [
            bm_rf.verts.new((-0.138 * s, -0.106 * s, 0.332 * s)),
            bm_rf.verts.new((0.038 * s, -0.106 * s, 0.332 * s)),
            bm_rf.verts.new((0.038 * s, 0.106 * s, 0.332 * s)),
            bm_rf.verts.new((-0.138 * s, 0.106 * s, 0.332 * s)),
        ]
        bm_rf.faces.new(list(reversed(rf_b)))
        bm_rf.faces.new(rf_t)
        for i in range(4):
            j = (i + 1) % 4
            bm_rf.faces.new((rf_b[i], rf_b[j], rf_t[j], rf_t[i]))
        self._add_bm("car_roof", bm_rf, roof_role, cm, uv_kind="box")

        # Crisp Espresso A/B/C Pillars + Window Beltline Trim framing the recessed glass!
        bm_pil = bmesh.new()

        def _add_strut(p0, p1, half_w):
            v0, v1 = Vector(p0), Vector(p1)
            d = (v1 - v0).normalized()
            ref = Vector((0.0, 1.0, 0.0)) if abs(d.y) < 0.8 else Vector((1.0, 0.0, 0.0))
            u1 = d.cross(ref).normalized() * half_w
            u2 = d.cross(u1).normalized() * half_w
            r0 = [bm_pil.verts.new(v0 + u1 + u2), bm_pil.verts.new(v0 - u1 + u2), bm_pil.verts.new(v0 - u1 - u2), bm_pil.verts.new(v0 + u1 - u2)]
            r1 = [bm_pil.verts.new(v1 + u1 + u2), bm_pil.verts.new(v1 - u1 + u2), bm_pil.verts.new(v1 - u1 - u2), bm_pil.verts.new(v1 + u1 - u2)]
            bm_pil.faces.new(list(reversed(r0)))
            bm_pil.faces.new(r1)
            for k in range(4):
                kn = (k + 1) % 4
                bm_pil.faces.new((r0[k], r0[kn], r1[kn], r1[k]))

        for sy in (-1.0, 1.0):
            _add_strut((0.114 * s, sy * 0.136 * s, 0.194 * s), (0.044 * s, sy * 0.110 * s, 0.306 * s), 0.0105 * s)
            _add_strut((-0.045 * s, sy * 0.136 * s, 0.194 * s), (-0.045 * s, sy * 0.110 * s, 0.306 * s), 0.0095 * s)
            _add_strut((-0.196 * s, sy * 0.136 * s, 0.194 * s), (-0.142 * s, sy * 0.110 * s, 0.306 * s), 0.0115 * s)
        self._add_bm("car_pillars", bm_pil, "espresso", cm, uv_kind="box")
        self.plush_box((0.328 * s, 0.286 * s, 0.012 * s), (-0.040 * s, 0.0, 0.200 * s), "espresso", r_bevel=0.0, puff=0.0, M=cm)

        # 3. Front Espresso Recessed Grille with 3 Golden Horizontal Slats!
        self.plush_box((0.022 * s, 0.138 * s, 0.062 * s), (0.278 * s, 0.0, 0.120 * s), "espresso", r_bevel=0.0, puff=0.0, M=cm)
        for gz in (0.102, 0.120, 0.138):
            self.plush_box((0.012 * s, 0.124 * s, 0.0085 * s), (0.287 * s, 0.0, gz * s), "gold", r_bevel=0.0, puff=0.0, M=cm)

        # 4. 2 Round Espresso Headlight Bezels with Glowing Warm Lenses + Crisp Rear Taillights (>= 6mm relief!)
        for sy in (-0.106, 0.106):
            self.plush_cyl(0.036 * s, 0.024 * s, (0.272 * s, sy * s, 0.152 * s), "espresso", bevel=0.0, r_top=0.033 * s, segs=8, axis="X", M=cm)
            self.plush_cyl(0.025 * s, 0.016 * s, (0.282 * s, sy * s, 0.152 * s), "glow", bevel=0.0, r_top=0.021 * s, segs=6, axis="X", M=cm)
            self.plush_box((0.020 * s, 0.062 * s, 0.034 * s), (-0.276 * s, sy * s, 0.156 * s), "espresso", r_bevel=0.0, puff=0.0, M=cm)
            self.plush_box((0.014 * s, 0.048 * s, 0.022 * s), (-0.286 * s, sy * s, 0.156 * s), "chestnut", r_bevel=0.0, puff=0.0, M=cm)

        # 5. Sculpted Wheel Arches (crisp 4-seg triangular-section fender flares!) + 18-Seg Cocoa Tires with Gleaming Golden Rims & Hubcaps!
        bm_arch = bmesh.new()
        n_arc = 4
        r_a_in = 0.092 * s
        r_a_out = 0.112 * s
        a_thick = 0.028 * s
        for sx in (-0.162, 0.162):
            for sy_s in (-1.0, 1.0):
                y_in = sy_s * 0.146 * s
                y_out = sy_s * (0.146 * s + a_thick)
                ar_in_f, ar_out_m, ar_in_b = [], [], []
                for k in range(n_arc + 1):
                    ang = math.pi * (k / float(n_arc))
                    ca, sa = math.cos(ang), math.sin(ang)
                    ar_in_f.append(bm_arch.verts.new((sx * s + r_a_in * ca, y_in, 0.084 * s + r_a_in * sa)))
                    ar_out_m.append(bm_arch.verts.new((sx * s + r_a_out * ca, y_out, 0.084 * s + r_a_out * sa)))
                    ar_in_b.append(bm_arch.verts.new((sx * s + r_a_in * ca, y_out, 0.084 * s + r_a_in * sa)))
                for k in range(n_arc):
                    bm_arch.faces.new((ar_in_f[k], ar_out_m[k], ar_out_m[k + 1], ar_in_f[k + 1]))
                    bm_arch.faces.new((ar_out_m[k], ar_in_b[k], ar_in_b[k + 1], ar_out_m[k + 1]))
                    bm_arch.faces.new((ar_in_b[k], ar_in_f[k], ar_in_f[k + 1], ar_in_b[k + 1]))
                bm_arch.faces.new((ar_in_f[0], ar_in_b[0], ar_out_m[0]))
                bm_arch.faces.new((ar_out_m[-1], ar_in_b[-1], ar_in_f[-1]))
        self._add_bm("car_arches", bm_arch, "espresso", cm, uv_kind="box")

        bm_hub = bmesh.new()
        for sx in (-0.162, 0.162):
            for sy_s in (-1.0, 1.0):
                wy = sy_s * 0.158 * s
                # Crisp 18-seg cocoa tire (bottom touching z=0.0!)
                self.plush_cyl(0.084 * s, 0.056 * s, (sx * s, wy, 0.084 * s), "cocoa", bevel=0.0, segs=18, axis="Y", M=cm)
                # Gleaming golden recessed rim disc (6-seg crisp alloy rim!)
                self.plush_cyl(0.048 * s, 0.062 * s, (sx * s, wy, 0.084 * s), "gold", bevel=0.0, segs=6, axis="Y", M=cm)
                # Sleek domed cream center hubcap cone (5-seg compact cap!)
                n_hc = 5
                y_hb = wy + sy_s * 0.029 * s
                y_ha = wy + sy_s * 0.042 * s
                hc_ring = [
                    bm_hub.verts.new((sx * s + 0.022 * s * math.cos(math.tau * i / n_hc), y_hb, 0.084 * s + 0.022 * s * math.sin(math.tau * i / n_hc)))
                    for i in range(n_hc)
                ]
                hc_apex = bm_hub.verts.new((sx * s, y_ha, 0.084 * s))
                for i in range(n_hc):
                    j = (i + 1) % n_hc
                    bm_hub.faces.new((hc_ring[i], hc_ring[j], hc_apex))
                bm_hub.faces.new(list(reversed(hc_ring)))
        self._add_bm("car_hubs", bm_hub, "cream", cm, uv_kind="box")

        # 6. Front & Rear Chrome-Gold Bumpers + Overriders + Cute Tiny Side Mirrors!
        for bx_s in (1.0, -1.0):
            bx = bx_s * 0.292 * s
            self.plush_box((0.026 * s, 0.305 * s, 0.028 * s), (bx, 0.0, 0.078 * s), "gold", r_bevel=0.0, puff=0.0, M=cm)
            for sy_o in (-0.085, 0.085):
                self.plush_box((0.022 * s, 0.018 * s, 0.042 * s), (bx + bx_s * 0.006 * s, sy_o * s, 0.084 * s), "espresso", r_bevel=0.0, puff=0.0, M=cm)
        for sy_s in (-1.0, 1.0):
            self.plush_box((0.014 * s, 0.030 * s, 0.012 * s), (0.095 * s, sy_s * 0.155 * s, 0.208 * s), "espresso", r_bevel=0.0, puff=0.0, M=cm)
            self.plush_box((0.026 * s, 0.036 * s, 0.024 * s), (0.090 * s, sy_s * 0.178 * s, 0.214 * s), body_role, r_bevel=0.0, puff=0.0, rot=(0.0, 0.0, -sy_s * 0.22), M=cm)

    def plush_coin(self, loc=(0.0, 0.0, 0.0), radius=0.045, thick=0.014, role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """Chunky rounded sunny-gold collectible coin."""
        return self.plush_cyl(radius, thick, loc=loc, role=role, bevel=thick * 0.30, segs=16 if self.low_poly else 20, rot=rot, M=M)

    def plush_banknote(self, loc=(0.0, 0.0, 0.0), w=0.14, h=0.068, thick=0.018, role="sage_warm", band_role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """Chunky banded cash bundle / banknote stack (warm-sage & sunny-gold!)."""
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        self.plush_box((w, h, thick), (0.0, 0.0, 0.0), role, r_bevel=min(w, h, thick) * 0.22, bevel_segs=1, puff=0.01, M=bm_m)
        self.plush_box((w * 0.24, h * 1.05, thick * 1.12), (0.0, 0.0, 0.0), band_role, r_bevel=thick * 0.16, bevel_segs=1, puff=0.01, M=bm_m)

    def plush_basket(self, loc=(0.0, 0.0, 0.0), size=0.30, body_role="caramel", trim_role="cream", handle_role="cocoa", rot=(0.0, 0.0, 0.0), M=None):
        """Cute chunky caramel café wicker shopping basket with curved handle (for SHOP!)."""
        s = float(size)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        self.plush_box((s, s * 0.72, s * 0.56), (0.0, 0.0, s * 0.28), body_role, r_bevel=s * 0.11, puff=0.04, M=bm_m)
        self.plush_frame(s * 1.04, s * 0.76, depth=s * 0.10, thickness=s * 0.09, loc=(0.0, 0.0, s * 0.54), role=trim_role, rot=(math.pi * 0.5, 0.0, 0.0), M=bm_m)
        h_pts = [
            (-s * 0.34, 0.0, s * 0.54),
            (-s * 0.30, 0.0, s * 0.86),
            (0.0, 0.0, s * 0.96),
            (s * 0.30, 0.0, s * 0.86),
            (s * 0.34, 0.0, s * 0.54),
        ]
        self.plush_tube(h_pts, s * 0.040, role=handle_role, segs=8 if self.low_poly else 12, smooth_steps=1, M=bm_m)

    # ---- V15 Sharpened Workshop & Crafting Low-Poly Detail Helpers ----

    def bolt_cap_x(self, loc=(0.0, 0.0, 0.0), radius=0.052, thick=0.024, body_role="caramel", x_role="cocoa", segs=16, rot=(0.0, 0.0, 0.0), M=None):
        """Chunky rounded toy rivet cap with non-overlapping 1-piece extruded X-slot facing -Y (~72 tris, ZERO Z-fighting!)."""
        r = float(radius)
        th = float(thick)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        self.plush_cyl(r, th, (0.0, 0.0, 0.0), role=body_role, bevel=min(th * 0.30, r * 0.22), segs=int(segs), axis="Y", M=bm_m)
        hl = r * 0.59
        hw = r * 0.12
        # Build 1-piece 12-corner plus-cross rotated 45 deg (zero coplanar crossing bars!)
        y_back = -th * 0.22
        y_front = -th * 0.72
        c45 = math.sqrt(0.5)
        raw_pts = [
            (hw, hw), (hl, hw), (hl, -hw), (hw, -hw),
            (hw, -hl), (-hw, -hl), (-hw, -hw), (-hl, -hw),
            (-hl, hw), (-hw, hw), (-hw, hl), (hw, hl),
        ]
        pts = [(px * c45 - pz * c45, px * c45 + pz * c45) for (px, pz) in raw_pts]
        bm = bmesh.new()
        vf = [bm.verts.new((px, y_front, pz)) for (px, pz) in pts]
        vb = [bm.verts.new((px, y_back, pz)) for (px, pz) in pts]
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((vf[i], vf[j], vb[j], vb[i]))
        # Convex decomposition of cross cap into center square + 4 arms
        for quad in ((0, 3, 6, 9), (0, 1, 2, 3), (3, 4, 5, 6), (6, 7, 8, 9), (9, 10, 11, 0)):
            bm.faces.new([vf[k] for k in reversed(quad)])
            bm.faces.new([vb[k] for k in quad])
        self._add_bm("bolt_x", bm, x_role, bm_m, uv_kind="box")

    def craft_toolbox(self, loc=(0.0, 0.0, 0.0), scale=1.0, body_role="caramel", lid_role="honey", trim_role="cocoa", clasp_role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """V15 Sharpened 2-tone mechanic toolbox with chamfered pitched lid, corner trim guards, dual clasp & bracketed handle (~195 tris)."""
        s = float(scale)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Crisp chamfered lower box (zero dough puff!)
        self.plush_box((0.280 * s, 0.160 * s, 0.130 * s), (0.0, 0.0, 0.065 * s), role=body_role, r_bevel=0.010 * s, bevel_segs=1, puff=0.0, M=bm_m)
        # 4 sharp vertical espresso corner trim guards (combined crisp bmesh!)
        bm_c = bmesh.new()
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                sub = bmesh.new()
                bmesh.ops.create_cube(sub, size=1.0)
                bmesh.ops.scale(sub, vec=(0.022 * s, 0.022 * s, 0.134 * s), verts=sub.verts)
                bmesh.ops.translate(sub, vec=(sx * 0.135 * s, sy * 0.075 * s, 0.067 * s), verts=sub.verts)
                mt = bpy.data.meshes.new("_ks_tbc_tmp")
                sub.to_mesh(mt)
                sub.free()
                bm_c.from_mesh(mt)
                bpy.data.meshes.remove(mt)
        self._add_bm("tb_corners", bm_c, trim_role, bm_m, uv_kind="box")
        # Crisp center seam lip
        self.plush_box((0.296 * s, 0.176 * s, 0.020 * s), (0.0, 0.0, 0.134 * s), role=trim_role, r_bevel=0.0, puff=0.0, M=bm_m)
        # Tapered trapezoid mechanic lid (real crisp pitched bevel silhouette!)
        bm_lid = bmesh.new()
        l_bot = [
            bm_lid.verts.new((-0.140 * s, -0.080 * s, 0.144 * s)),
            bm_lid.verts.new((0.140 * s, -0.080 * s, 0.144 * s)),
            bm_lid.verts.new((0.140 * s, 0.080 * s, 0.144 * s)),
            bm_lid.verts.new((-0.140 * s, 0.080 * s, 0.144 * s)),
        ]
        l_top = [
            bm_lid.verts.new((-0.114 * s, -0.056 * s, 0.198 * s)),
            bm_lid.verts.new((0.114 * s, -0.056 * s, 0.198 * s)),
            bm_lid.verts.new((0.114 * s, 0.056 * s, 0.198 * s)),
            bm_lid.verts.new((-0.114 * s, 0.056 * s, 0.198 * s)),
        ]
        bm_lid.faces.new(list(reversed(l_bot)))
        bm_lid.faces.new(l_top)
        for i in range(4):
            j = (i + 1) % 4
            bm_lid.faces.new((l_bot[i], l_bot[j], l_top[j], l_top[i]))
        self._add_bm("tb_lid", bm_lid, lid_role, bm_m, uv_kind="box")
        # Crisp dual-piece golden clasp latch (upper hasp + lower catch plate!)
        self.plush_box((0.050 * s, 0.020 * s, 0.026 * s), (0.0, -0.086 * s, 0.146 * s), role=clasp_role, r_bevel=0.0, puff=0.0, M=bm_m)
        self.plush_box((0.036 * s, 0.024 * s, 0.030 * s), (0.0, -0.088 * s, 0.118 * s), role=clasp_role, r_bevel=0.0, puff=0.0, M=bm_m)
        # Bracketed top handle with grooved espresso grip bar
        for sx in (-0.072, 0.072):
            self.plush_box((0.016 * s, 0.022 * s, 0.052 * s), (sx * s, 0.0, 0.220 * s), role=clasp_role, r_bevel=0.0, puff=0.0, M=bm_m)
        self.plush_cyl(0.015 * s, 0.156 * s, (0.0, 0.0, 0.246 * s), role=trim_role, bevel=0.0, segs=6, axis="X", M=bm_m)

    def craft_tape_dispenser(self, loc=(0.0, 0.0, 0.0), scale=1.0, body_role="walnut", roll_role="cream", core_role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """V15 Sharpened weighted studio tape dispenser with side cheeks, chamfered core, tape bridge & metallic cutter (~145 tris)."""
        s = float(scale)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Sculpted stepped weighted base with crisp angled front nose
        base_pts = [
            (-0.080 * s, 0.0),
            (0.082 * s, 0.0),
            (0.082 * s, 0.056 * s),
            (0.048 * s, 0.068 * s),
            (-0.065 * s, 0.068 * s),
            (-0.080 * s, 0.042 * s),
        ]
        self.plush_extrude(base_pts, depth=0.074 * s, loc=(0.0, 0.0, 0.0), role=body_role, bevel=0.004 * s, bevel_segs=1, M=bm_m)
        # Crisp side axle cheeks framing the roll cleanly
        for sy in (-0.036, 0.036):
            self.plush_box((0.042 * s, 0.008 * s, 0.058 * s), (-0.015 * s, sy * s, 0.082 * s), role="espresso", r_bevel=0.0, puff=0.0, M=bm_m)
        # Clean 14-seg tape roll + chamfered golden hub core
        self.plush_cyl(0.068 * s, 0.054 * s, (-0.015 * s, 0.0, 0.098 * s), role=roll_role, bevel=0.0, segs=14, axis="Y", M=bm_m)
        self.plush_cyl(0.032 * s, 0.068 * s, (-0.015 * s, 0.0, 0.098 * s), role=core_role, bevel=0.0, segs=10, axis="Y", M=bm_m)
        # Crisp tape strip feeding forward onto beveled golden cutter blade!
        self.plush_box((0.068 * s, 0.050 * s, 0.006 * s), (0.042 * s, 0.0, 0.092 * s), role=roll_role, r_bevel=0.0, puff=0.0, rot=(0.0, 0.42, 0.0), M=bm_m)
        self.plush_box((0.022 * s, 0.058 * s, 0.014 * s), (0.072 * s, 0.0, 0.066 * s), role=core_role, r_bevel=0.0, puff=0.0, rot=(0.0, 0.45, 0.0), M=bm_m)

    def craft_hammer(self, loc=(0.0, 0.0, 0.0), scale=1.0, head_role="caramel", handle_role="honey", grip_role="cocoa", rot=(0.0, 0.0, 0.0), M=None):
        """V15 Sharpened low-poly claw hammer with grooved grip rings, metallic neck collar, chamfered head & angled claw (~195 tris)."""
        s = float(scale)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # Tapered wooden handle shaft + sharp-edged golden metallic neck ferrule collar
        self.plush_cyl(0.016 * s, 0.285 * s, (0.0, 0.0, -0.025 * s), role=handle_role, bevel=0.0, r_top=0.019 * s, segs=6, M=bm_m)
        self.plush_cyl(0.024 * s, 0.022 * s, (0.0, 0.0, 0.088 * s), role="gold", bevel=0.0, segs=6, M=bm_m)
        # Grooved rubber cocoa grip (core + 2 crisp tactile grip ridges!)
        self.plush_cyl(0.021 * s, 0.115 * s, (0.0, 0.0, -0.116 * s), role=grip_role, bevel=0.0, segs=6, M=bm_m)
        for gz in (-0.145, -0.090):
            self.plush_cyl(0.025 * s, 0.015 * s, (0.0, 0.0, gz * s), role="espresso", bevel=0.0, segs=6, M=bm_m)
        # Crisp octagonal chamfered hammer head + beveled golden striking bell
        self.plush_cyl(0.032 * s, 0.104 * s, (-0.010 * s, 0.0, 0.126 * s), role=head_role, bevel=0.0, segs=8, axis="X", M=bm_m)
        self.plush_cyl(0.036 * s, 0.024 * s, (-0.072 * s, 0.0, 0.126 * s), role="gold", bevel=0.0, r_top=0.031 * s, segs=8, axis="X", M=bm_m)
        # Crisp bifurcated angled claw prongs on right
        for sy in (-0.010, 0.010):
            self.plush_box((0.068 * s, 0.011 * s, 0.020 * s), (0.066 * s, sy * s, 0.112 * s), role=head_role, r_bevel=0.0, puff=0.0, rot=(0.0, 0.44, 0.0), M=bm_m)

    def craft_screwdriver(self, loc=(0.0, 0.0, 0.0), scale=1.0, handle_role="caramel", shaft_role="metal_warm", collar_role="gold", rot=(0.0, 0.0, 0.0), M=None):
        """V15 Sharpened low-poly mechanic screwdriver with 6-fluted ergonomic grip, hex ferrule collar & chamfered chisel tip (~128 tris)."""
        s = float(scale)
        bm_m = (M or Matrix.Identity(4)) @ trs(loc, rot)
        # 6-fluted grooved ergonomic mechanic handle (custom fluted lathe — ZERO playdough pill!)
        bm_sh = bmesh.new()
        n_fl = 12
        h_prof = [
            (0.0, 0.012 * s, 0.0),
            (0.020 * s, 0.024 * s, 0.08),
            (0.026 * s, 0.056 * s, 0.14),
            (0.022 * s, 0.095 * s, 0.10),
            (0.027 * s, 0.132 * s, 0.12),
            (0.0, 0.148 * s, 0.0),
        ]
        rings = []
        for rad, zp, amp in h_prof:
            if rad < 1e-5:
                rings.append([bm_sh.verts.new((0.0, 0.0, zp))])
            else:
                ring = []
                for i in range(n_fl):
                    a = math.tau * i / float(n_fl)
                    fl = 1.0 + amp if (i % 2 == 0) else (1.0 - amp)
                    ring.append(bm_sh.verts.new((rad * fl * math.cos(a), rad * fl * math.sin(a), zp)))
                rings.append(ring)
        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            if len(r0) == 1:
                for i in range(n_fl):
                    j = (i + 1) % n_fl
                    bm_sh.faces.new((r0[0], r1[j], r1[i]))
            elif len(r1) == 1:
                for i in range(n_fl):
                    j = (i + 1) % n_fl
                    bm_sh.faces.new((r0[i], r0[j], r1[0]))
            else:
                for i in range(n_fl):
                    j = (i + 1) % n_fl
                    bm_sh.faces.new((r0[i], r0[j], r1[j], r1[i]))
        self._add_bm("sd_handle", bm_sh, handle_role, bm_m, uv_kind="cyl")
        # Sharp-edged hexagonal metallic golden collar ferrule
        self.plush_cyl(0.023 * s, 0.024 * s, (0.0, 0.0, 0.002 * s), role=collar_role, bevel=0.0, segs=6, M=bm_m)
        # Crisp 6-sided steel shaft + tapered chisel blade tip!
        self.plush_cyl(0.0095 * s, 0.142 * s, (0.0, 0.0, -0.076 * s), role=shaft_role, bevel=0.0, segs=6, M=bm_m)
        bm_tip = bmesh.new()
        tb_t = [
            bm_tip.verts.new((-0.008 * s, -0.007 * s, -0.142 * s)),
            bm_tip.verts.new((0.008 * s, -0.007 * s, -0.142 * s)),
            bm_tip.verts.new((0.008 * s, 0.007 * s, -0.142 * s)),
            bm_tip.verts.new((-0.008 * s, 0.007 * s, -0.142 * s)),
        ]
        tb_b = [
            bm_tip.verts.new((-0.014 * s, -0.0025 * s, -0.175 * s)),
            bm_tip.verts.new((0.014 * s, -0.0025 * s, -0.175 * s)),
            bm_tip.verts.new((0.014 * s, 0.0025 * s, -0.175 * s)),
            bm_tip.verts.new((-0.014 * s, 0.0025 * s, -0.175 * s)),
        ]
        bm_tip.faces.new(tb_t)
        bm_tip.faces.new(list(reversed(tb_b)))
        for i in range(4):
            j = (i + 1) % 4
            bm_tip.faces.new((tb_t[i], tb_b[i], tb_b[j], tb_t[j]))
        self._add_bm("sd_tip", bm_tip, shaft_role, bm_m, uv_kind="box")

    # ---- V12 Crisp Palette UV Assignment, Soft Vertex AO, Smart Card Packing & Saving ----

    def _apply_uvs_and_join_parts(self):
        """Evaluate modifiers, assign crisp per-part palette/stripe UVs BEFORE join, then join."""
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
            role = ob.get("prop_forge_role", "caramel")
            uv_kind = ob.get("prop_forge_uv_kind", "box")
            s_freq = float(ob.get("prop_forge_stripe_freq", 3.6))
            _assign_part_uvs(ob, role, uv_kind=uv_kind, stripe_freq=s_freq)

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

        self._clean_mesh_bmesh(root, rigged=rigged, crease_deg=32.0)
        return root

    def _clean_mesh_bmesh(self, ob, rigged=False, crease_deg=32.0):
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
        org_lay = bm.faces.layers.int.get("organic_smooth")
        cr_hard = math.radians(crease_deg)
        cr_org = math.radians(68.0)
        for e in bm.edges:
            if not e.is_manifold:
                e.smooth = False
            elif len(e.link_faces) == 2:
                is_org = bool(org_lay is not None and e.link_faces[0][org_lay] == 1 and e.link_faces[1][org_lay] == 1)
                thresh = cr_org if is_org else cr_hard
                if e.calc_face_angle(0.0) > thresh:
                    e.smooth = False
        bm.to_mesh(ob.data)
        bm.free()
        if "organic_smooth" in ob.data.attributes:
            ob.data.attributes.remove(ob.data.attributes["organic_smooth"])
        ob.data.update()

    def _enforce_budget(self, root, reserve_tris=0):
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

    def _assign_crisp_palette_uvs(self, root):
        """Bind shared `billie_master_pal.png` & `billie_glow_pal.png` and bake bright warm Vertex AO (`Color 1`)."""
        me = root.data
        roles = [resolve_role(slot.material.get("prop_forge_role", "caramel")) for slot in root.material_slots]
        old_idx = [p.material_index for p in me.polygons]
        used_idx = set(old_idx)
        has_diff = any(i in used_idx and roles[i] not in EMISSIVE_ROLES for i in range(len(roles)))
        has_emit = any(i in used_idx and roles[i] in EMISSIVE_ROLES for i in range(len(roles)))

        pal_img = bpy.data.images.load(self.art["master_pal"], check_existing=True)
        glow_img = bpy.data.images.load(self.art["glow_pal"], check_existing=True)

        diff_mat = (
            self._new_game_mat(
                self.id + "_diffuse", pal_img, shader="default_spec.sps",
                transparent=False, use_vcol=True, repeat=True,
            )
            if has_diff
            else None
        )
        emit_mat = (
            self._new_game_mat(
                self.id + "_emissive", glow_img, shader="emissive.sps",
                transparent=False, use_vcol=False, repeat=False,
            )
            if has_emit
            else None
        )

        me.materials.clear()
        diff_slot = emit_slot = 0
        if diff_mat is not None:
            diff_slot = len(me.materials)
            me.materials.append(diff_mat)
        if emit_mat is not None:
            emit_slot = len(me.materials)
            me.materials.append(emit_mat)

        poly_is_emissive = []
        for poly, oi in zip(me.polygons, old_idx):
            is_em = roles[oi] in EMISSIVE_ROLES
            poly.material_index = emit_slot if (is_em and emit_mat is not None) else diff_slot
            poly_is_emissive.append(bool(is_em))

        for m in list(bpy.data.materials):
            if m.users == 0:
                bpy.data.materials.remove(m)

        self._bake_vertex_ao(me, poly_is_emissive)
        return self.art["master_pal"]

    def _bake_vertex_ao(self, me, poly_is_emissive):
        """V15 Crisp Crevice BVHTree 16-ray AO + warm studio top-light into `Color 1` [192..255] (mean ~236, min >= 190)."""
        col_name = "Color 1"
        existing = me.color_attributes.get(col_name)
        if existing is not None:
            me.color_attributes.remove(existing)
        col_attr = me.color_attributes.new(name=col_name, type="BYTE_COLOR", domain="CORNER")
        me.color_attributes.active_color = col_attr

        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.normal_update()
        bvh = BVHTree.FromBMesh(bm)

        max_dist = 0.22
        eps = 0.0040
        lo_floor = 192.0 / 255.0
        lo_r_floor = 194.0 / 255.0
        zs = [v.co.z for v in bm.verts]
        z_min = min(zs) if zs else 0.0
        z_span = max(0.20, (max(zs) - z_min) if zs else 1.0)

        vert_rgb = []
        z_up = Vector((0.0, 0.0, 1.0))
        x_alt = Vector((1.0, 0.0, 0.0))
        for v in bm.verts:
            n = v.normal.normalized() if v.normal.length > 1e-6 else z_up
            ref = z_up if abs(n.z) < 0.92 else x_alt
            t1 = n.cross(ref).normalized()
            t2 = n.cross(t1).normalized()
            orig = v.co + n * eps

            occ_sum = 0.0
            for dx, dy, dz in _HEMI_DIRS_16:
                rdir = t1 * dx + t2 * dy + n * dz
                hit_loc, _, _, hit_d = bvh.ray_cast(orig, rdir, max_dist)
                if hit_loc is not None and hit_d is not None:
                    occ_sum += 1.0 - (hit_d / max_dist)
            occ = occ_sum / float(len(_HEMI_DIRS_16))

            up_fac = 0.5 + 0.5 * n.z
            z_fac = max(0.0, min(1.0, (v.co.z - z_min) / z_span))
            val = (1.0 - 0.195 * occ) * (0.930 + 0.056 * up_fac + 0.014 * z_fac)
            vr = max(lo_r_floor, min(1.0, val + 0.012 * occ))
            vg = max(lo_floor, min(1.0, val))
            vb = max(lo_floor, min(1.0, val - 0.012 * occ))
            vert_rgb.append((vr, vg, vb))
        bm.free()

        n_loops = len(me.loops)
        buf = np.ones((n_loops, 4), dtype=np.float32)
        for poly, is_em in zip(me.polygons, poly_is_emissive):
            if is_em:
                continue
            for li in poly.loop_indices:
                r, g, b = vert_rgb[me.loops[li].vertex_index]
                buf[li, 0] = r
                buf[li, 1] = g
                buf[li, 2] = b
        col_attr.data.foreach_set("color_srgb", buf.ravel())
        me.update()

    def _new_game_mat(
        self, name, image, shader="default_spec.sps", transparent=False, use_vcol=False, repeat=False, emissive_mult=None
    ):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        tex.extension = "REPEAT" if repeat else ("CLIP" if transparent else "EXTEND")

        is_emissive = shader in ("emissive.sps", "emissive_alpha.sps")
        if is_emissive:
            # Pure self-lit screen/LED (matches GTA V emissive.sps instead of double-lighting diffuse + emission in Eevee)
            bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        elif use_vcol and shader == "default_spec.sps":
            vcol = nt.nodes.new("ShaderNodeVertexColor")
            vcol.layer_name = "Color 1"
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(tex.outputs["Color"], mix.inputs[6])
            nt.links.new(vcol.outputs["Color"], mix.inputs[7])
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        else:
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

        if transparent:
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
            try:
                mat.blend_method = "BLEND"
            except Exception:
                pass
        # V17 Soft Collectible Matte Designer Vinyl (eliminates wet jelly/wax glare in GTA V desert sun!)
        bsdf.inputs["Roughness"].default_value = 0.62
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0 if is_emissive else 0.25
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.0
        if is_emissive:
            em_val = 1.45 if emissive_mult is None else float(emissive_mult)
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = em_val
            mat["prop_forge_emissive_mult"] = em_val
        elif shader == "default_spec.sps":
            mat["prop_forge_spec_int"] = 0.09
            mat["prop_forge_spec_falloff"] = 28.0
            mat["prop_forge_spec_fresnel"] = 0.32
        mat["prop_forge_shader"] = shader
        return mat

    def _crop_uv_region(self, img_path, uv_rect, img_cache):
        """Load image (cached) and crop exact pixel sub-region corresponding to OpenGL uv_rect."""
        ap = os.path.abspath(img_path)
        if ap not in img_cache:
            img_cache[ap] = _load_rgba_topdown(ap)
        arr = img_cache[ap]
        h, w, _ = arr.shape
        u0, v0, u1, v1 = uv_rect
        if abs(u0) < 1e-4 and abs(v0) < 1e-4 and abs(u1 - 1.0) < 1e-4 and abs(v1 - 1.0) < 1e-4:
            return arr.copy()
        x0 = max(0, min(w - 1, int(round(u0 * w))))
        x1 = max(x0 + 1, min(w, int(round(u1 * w))))
        y0 = max(0, min(h - 1, int(round((1.0 - v1) * h))))
        y1 = max(y0 + 1, min(h, int(round((1.0 - v0) * h))))
        return arr[y0:y1, x0:x1].copy()

    def _pack_image_group(self, regions, out_png, alpha=True, size=1024):
        """Aspect-aware 1024px region packer — NEVER squishes 2:1 banners into 244x244 squares!"""
        norm_keys = []
        str_mode = False
        for item in regions:
            if isinstance(item, str):
                str_mode = True
                norm_keys.append((os.path.abspath(item), (0.0, 0.0, 1.0, 1.0)))
            else:
                norm_keys.append((os.path.abspath(item[0]), tuple(float(v) for v in item[1])))

        img_cache = {}
        crops = []
        for k in norm_keys:
            c = self._crop_uv_region(k[0], k[1], img_cache)
            ch, cw, _ = c.shape
            crops.append((k, c, float(cw) / max(1.0, float(ch))))

        n = len(crops)
        s = int(size)
        pad = 6

        wide_idx = [i for i, (_, _, ar) in enumerate(crops) if ar >= 1.35]
        sq_idx = [i for i, (_, _, ar) in enumerate(crops) if ar < 1.35]

        sheet_w, sheet_h = s, s
        placements = []

        if n == 1:
            _, _, ar = crops[0]
            if ar >= 1.4:
                sheet_w, sheet_h = s, s // 2
            placements = [(0, 0, 0, sheet_w, sheet_h)]
        elif n == 2:
            if len(wide_idx) == 2:
                sheet_w, sheet_h = s, s
                placements = [
                    (wide_idx[0], 0, 0, s, s // 2),
                    (wide_idx[1], 0, s // 2, s, s // 2),
                ]
            elif len(sq_idx) == 2:
                sheet_w, sheet_h = s, s // 2
                placements = [
                    (sq_idx[0], 0, 0, s // 2, s // 2),
                    (sq_idx[1], s // 2, 0, s // 2, s // 2),
                ]
            else:
                sheet_w, sheet_h = s, s
                placements = [
                    (wide_idx[0], 0, 0, s, s // 2),
                    (sq_idx[0], 0, s // 2, s // 2, s // 2),
                ]
        elif n == 3:
            sheet_w, sheet_h = s, s
            if len(wide_idx) == 1:
                placements = [
                    (wide_idx[0], 0, 0, s, s // 2),
                    (sq_idx[0], 0, s // 2, s // 2, s // 2),
                    (sq_idx[1], s // 2, s // 2, s // 2, s // 2),
                ]
            elif len(wide_idx) == 2:
                placements = [
                    (wide_idx[0], 0, 0, s, s // 2),
                    (wide_idx[1], 0, s // 2, s // 2, s // 2),
                    (sq_idx[0], s // 2, s // 2, s // 2, s // 2),
                ]
            else:
                placements = [
                    (0, 0, 0, s // 2, s // 2),
                    (1, s // 2, 0, s // 2, s // 2),
                    (2, 0, s // 2, s // 2, s // 2),
                ]
        else:
            cols = 2 if n <= 4 else 3
            rows = int(math.ceil(n / float(cols)))
            cw_b = s // cols
            ch_b = s // rows
            placements = [(i, (i % cols) * cw_b, (i // cols) * ch_b, cw_b, ch_b) for i in range(n)]

        sheet = np.zeros((sheet_h, sheet_w, 4), dtype=np.float32)
        if not alpha:
            sheet[..., :3] = 0.96
            sheet[..., 3] = 1.0

        uv_rects = {}
        for ci, bx, by, bw, bh in placements:
            key, crop, ar = crops[ci]
            avail_w = max(8, bw - pad * 2)
            avail_h = max(8, bh - pad * 2)
            if (avail_w / float(avail_h)) >= ar:
                th = avail_h
                tw = max(8, min(avail_w, int(round(th * ar))))
            else:
                tw = avail_w
                th = max(8, min(avail_h, int(round(tw / max(0.05, ar)))))
            ox = bx + (bw - tw) // 2
            oy = by + (bh - th) // 2
            res = _resize_rgba(crop, tw, th)
            if not alpha:
                res[..., 3] = 1.0
                sheet[oy:oy + th, ox:ox + tw] = res
                _edge_pad_rect(sheet, ox, oy, tw, th, pad=min(4, pad - 1))
            else:
                cell_buf = np.zeros((bh, bw, 4), dtype=np.float32)
                lx, ly = ox - bx, oy - by
                cell_buf[ly:ly + th, lx:lx + tw] = res
                if res[..., 3].min() > 0.98:
                    _edge_pad_rect(cell_buf, lx, ly, tw, th, pad=min(4, pad - 1))
                else:
                    cell_buf = _bleed_rgb(cell_buf, passes=10)
                sheet[by:by + bh, bx:bx + bw] = cell_buf

            u0 = (ox + 0.5) / float(sheet_w)
            u1 = (ox + tw - 0.5) / float(sheet_w)
            v1 = 1.0 - (oy + 0.5) / float(sheet_h)
            v0 = 1.0 - (oy + th - 0.5) / float(sheet_h)
            uv_rects[key] = (u0, v0, u1, v1)
            if str_mode:
                uv_rects[key[0]] = (u0, v0, u1, v1)

        _save_rgba_topdown(sheet, out_png, alpha=alpha)
        return uv_rects

    def _build_and_join_cards(self, root, shift, out_dir):
        """Build all decal cards, shared-sheet regions & 6x6 curved face domes (STRICT <= 4 materials!)."""
        if not self.pending_cards:
            return
        shift_m = Matrix.Translation(shift)
        rigged = self.animate and len(self.bones) > 1
        base_slots = len(root.data.materials)
        avail_slots = max(1, 4 - base_slots)

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
        if len(active_keys) > avail_slots and buckets["card"] and buckets["decal"]:
            buckets["decal"].extend(buckets["card"])
            buckets["card"] = []
            active_keys = [k for k in ("card", "decal", "emit") if buckets[k]]
        if len(active_keys) > avail_slots and buckets["card"] and buckets["emit"]:
            buckets["decal"].extend(buckets["card"])
            buckets["card"] = []
            active_keys = [k for k in ("decal", "emit") if buckets[k]]

        plan = []
        extra_slots = max(0, avail_slots - len(active_keys))

        for bkey in active_keys:
            items = buckets[bkey]
            is_alpha = bkey == "decal"
            if bkey == "emit":
                shader = "emissive_alpha.sps" if any(it["transparent"] for it in items) else "emissive.sps"
                is_alpha = shader == "emissive_alpha.sps"
            elif bkey == "decal":
                shader = "decal.sps"
            else:
                shader = "default_spec.sps"

            by_img = {}
            img_order = []
            for it in items:
                ap = os.path.abspath(it["image"])
                if ap not in by_img:
                    by_img[ap] = []
                    img_order.append(ap)
                by_img[ap].append(it)

            s_avail = 1 + extra_slots
            if len(img_order) <= s_avail:
                extra_slots -= (len(img_order) - 1)
                for si, ap in enumerate(img_order):
                    tag = bkey if si == 0 else "{}_{}".format(bkey, si)
                    plan.append((tag, shader, is_alpha, by_img[ap], True))
            elif s_avail >= 2:
                def _img_aspect(ap_path):
                    it0 = by_img[ap_path][0]
                    u0, v0, u1, v1 = it0["uv_rect"]
                    tmp = bpy.data.images.load(ap_path, check_existing=True)
                    rw = max(1.0, tmp.size[0] * abs(u1 - u0))
                    rh = max(1.0, tmp.size[1] * abs(v1 - v0))
                    return rw / rh

                def _is_shared_sheet(ap_path):
                    bn = os.path.basename(ap_path).lower()
                    return bn.startswith("billie_v4_art_") or bn.startswith("billie_art_") or bn.startswith("billie_char_") or bn.startswith("billie_faces_")

                wide_imgs = [ap for ap in img_order if _img_aspect(ap) >= 1.35]
                sq_imgs = [ap for ap in img_order if _img_aspect(ap) < 1.35]
                slots_used = 0
                if wide_imgs and sq_imgs:
                    w_items = [it for ap in wide_imgs for it in by_img[ap]]
                    plan.append((bkey + "_wide", shader, is_alpha, w_items, len(wide_imgs) == 1))
                    slots_used += 1
                    rem_slots = s_avail - 1
                    sq_sorted = sorted(sq_imgs, key=lambda p: (0 if _is_shared_sheet(p) else 1, img_order.index(p)))
                    if len(sq_sorted) <= rem_slots:
                        for si, ap in enumerate(sq_sorted):
                            tag = bkey + "_sq" if si == 0 else "{}_sq{}".format(bkey, si)
                            plan.append((tag, shader, is_alpha, by_img[ap], True))
                            slots_used += 1
                    else:
                        n_direct = max(0, rem_slots - 1)
                        for si, ap in enumerate(sq_sorted[:n_direct]):
                            plan.append(("{}_d{}".format(bkey, si), shader, is_alpha, by_img[ap], True))
                            slots_used += 1
                        pack_items = [it for ap in sq_sorted[n_direct:] for it in by_img[ap]]
                        plan.append((bkey + "_sq", shader, is_alpha, pack_items, False))
                        slots_used += 1
                else:
                    ordered_imgs = sorted(img_order, key=lambda p: (0 if _is_shared_sheet(p) else 1, img_order.index(p)))
                    n_direct = max(0, s_avail - 1)
                    for si, ap in enumerate(ordered_imgs[:n_direct]):
                        plan.append(("{}_d{}".format(bkey, si), shader, is_alpha, by_img[ap], True))
                        slots_used += 1
                    pack_items = [it for ap in ordered_imgs[n_direct:] for it in by_img[ap]]
                    plan.append((bkey + "_pk", shader, is_alpha, pack_items, False))
                    slots_used += 1
                extra_slots = max(0, extra_slots - max(0, slots_used - 1))
            else:
                plan.append((bkey, shader, is_alpha, items, False))

        made_objs = []
        nx_face = 7 if self.low_poly else 10
        nz_face = 6 if self.low_poly else 10

        for slot_tag, shader, is_alpha, items, direct_single in plan:
            if direct_single:
                img_path = os.path.abspath(items[0]["image"])
                uv_lookup = {
                    (os.path.abspath(it["image"]), tuple(float(v) for v in it["uv_rect"])): tuple(float(v) for v in it["uv_rect"])
                    for it in items
                }
            else:
                uniq_regions = []
                for it in items:
                    rk = (os.path.abspath(it["image"]), tuple(float(v) for v in it["uv_rect"]))
                    if rk not in uniq_regions:
                        uniq_regions.append(rk)
                sheet_path = os.path.join(out_dir, "{}_{}.png".format(self.id, slot_tag))
                uv_lookup = self._pack_image_group(uniq_regions, sheet_path, alpha=is_alpha, size=1024)
                img_path = sheet_path

            bl_img = bpy.data.images.load(img_path, check_existing=True)
            card_em = 0.88 if shader in ("emissive.sps", "emissive_alpha.sps") else None
            mat = self._new_game_mat(
                "{}_{}".format(self.id, slot_tag),
                bl_img,
                shader=shader,
                transparent=is_alpha,
                use_vcol=False,
                repeat=False,
                emissive_mult=card_em,
            )
            if any(it.get("kind") in ("sculpt_mesh", "mochi_face") for it in items) and shader == "default_spec.sps":
                bsdf_m = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
                if bsdf_m:
                    bsdf_m.inputs["Roughness"].default_value = 0.68
                    if "Coat Weight" in bsdf_m.inputs:
                        bsdf_m.inputs["Coat Weight"].default_value = 0.0
                    if "Specular IOR Level" in bsdf_m.inputs:
                        bsdf_m.inputs["Specular IOR Level"].default_value = 0.20
                mat["prop_forge_spec_int"] = 0.05
                mat["prop_forge_spec_falloff"] = 20.0
                mat["prop_forge_spec_fresnel"] = 0.22

            for idx, it in enumerate(items):
                rk = (os.path.abspath(it["image"]), tuple(float(v) for v in it["uv_rect"]))
                u0, v0, u1, v1 = uv_lookup[rk]
                bm = bmesh.new()
                uv_layer = bm.loops.layers.uv.new("UVMap")
                kind = it["kind"]
                if kind == "sculpt_mesh":
                    # Load pre-sculpted silky-smooth organic character mesh (ZERO 32-deg crease faceting!)
                    src_me = None
                    with bpy.data.libraries.load(it["blend_path"], link=False) as (df, dt):
                        if it["mesh_name"] in df.meshes:
                            dt.meshes = [it["mesh_name"]]
                    if dt.meshes and dt.meshes[0] is not None:
                        src_me = dt.meshes[0]
                    if src_me is None:
                        bm.free()
                        continue
                    bm.free()
                    bm = bmesh.new()
                    bm.from_mesh(src_me)
                    bpy.data.meshes.remove(src_me)
                    loose_s = [v for v in bm.verts if not v.link_faces]
                    if loose_s:
                        bmesh.ops.delete(bm, geom=loose_s, context="VERTS")
                    sc_f = float(it.get("scale", 1.0))
                    if abs(sc_f - 1.0) > 1e-5:
                        bmesh.ops.transform(bm, matrix=Matrix.Diagonal((sc_f, sc_f, sc_f, 1.0)), verts=bm.verts)
                    uv_layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
                    du, dv = (u1 - u0), (v1 - v0)
                    for f in bm.faces:
                        f.smooth = True
                        for lp in f.loops:
                            ou, ov = lp[uv_layer].uv
                            lp[uv_layer].uv = (u0 + ou * du, v0 + ov * dv)
                    for e in bm.edges:
                        e.smooth = True
                elif kind == "mochi_face":
                    # V18 High-Detail Sculpted 3D Mochi-Cheek Chibi Face Dome (12x10 silky quads, chubby baby cheeks + soft nose curve, 1:1 512px house face!)
                    rx, rz, ry = float(it["rx"]), float(it["rz"]), float(it["ry"])
                    nx_m, nz_m = 12, 10
                    grid_v = []
                    grid_uv = []
                    for iz in range(nz_m + 1):
                        tz = -1.0 + 2.0 * iz / float(nz_m)  # -1 (chin) to +1 (forehead)
                        row_v = []
                        row_uv = []
                        for ix in range(nx_m + 1):
                            tx = -1.0 + 2.0 * ix / float(nx_m)
                            px = tx * math.sqrt(max(0.0, 1.0 - 0.5 * tz * tz))
                            pz = tz * math.sqrt(max(0.0, 1.0 - 0.5 * tx * tx))
                            r2 = min(0.995, px * px + pz * pz)
                            # Extra-plump chubby baby lower cheeks around pz = -0.26, cute rounded chin
                            cheek_w = 1.0 + 0.11 * math.exp(-((pz + 0.26) / 0.44) ** 2) - 0.08 * max(0.0, -pz - 0.58)
                            # Forward 3D fullness: fuller soft cheeks + adorable tiny center nose button swell
                            cheek_bulge = 0.11 * math.exp(-((abs(px) - 0.44) / 0.30) ** 2 - ((pz + 0.24) / 0.32) ** 2)
                            nose_bump = 0.048 * math.exp(-((px / 0.11) ** 2 + ((pz + 0.14) / 0.09) ** 2))
                            yy = -ry * (math.sqrt(max(0.0, 1.0 - 0.94 * r2)) + cheek_bulge + nose_bump)
                            row_v.append(bm.verts.new((px * rx * cheek_w, yy, pz * rz)))
                            uu = u0 + (u1 - u0) * (0.5 + 0.47 * px)
                            vv = v0 + (v1 - v0) * (0.49 + 0.46 * pz)
                            row_uv.append((uu, vv))
                        grid_v.append(row_v)
                        grid_uv.append(row_uv)
                    for iz in range(nz_m):
                        for ix in range(nx_m):
                            f = bm.faces.new((
                                grid_v[iz][ix],
                                grid_v[iz][ix + 1],
                                grid_v[iz + 1][ix + 1],
                                grid_v[iz + 1][ix],
                            ))
                            f.smooth = True
                            for lp, uv_val in zip(f.loops, (
                                grid_uv[iz][ix],
                                grid_uv[iz][ix + 1],
                                grid_uv[iz + 1][ix + 1],
                                grid_uv[iz + 1][ix],
                            )):
                                lp[uv_layer].uv = uv_val
                elif kind == "face_dome":
                    rx, rz, ry = it["rx"], it["rz"], it["ry"]
                    grid_v = []
                    grid_uv = []
                    for iz in range(nz_face + 1):
                        nz = -1.0 + 2.0 * iz / float(nz_face)
                        row_v = []
                        row_uv = []
                        for ix in range(nx_face + 1):
                            nx = -1.0 + 2.0 * ix / float(nx_face)
                            px = nx * math.sqrt(max(0.0, 1.0 - 0.5 * nz * nz))
                            pz = nz * math.sqrt(max(0.0, 1.0 - 0.5 * nx * nx))
                            r2 = min(1.0, px * px + pz * pz)
                            y = -ry * math.sqrt(max(0.0, 1.0 - 0.96 * r2))
                            row_v.append(bm.verts.new((px * rx, y, pz * rz)))
                            uu = u0 + (u1 - u0) * (0.5 + 0.48 * px)
                            vv = v0 + (v1 - v0) * (0.5 + 0.48 * pz)
                            row_uv.append((uu, vv))
                        grid_v.append(row_v)
                        grid_uv.append(row_uv)
                    for iz in range(nz_face):
                        for ix in range(nx_face):
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
                elif kind == "disc":
                    rad = float(it["radius"])
                    n_seg = max(16, int(it.get("segs", 24)))
                    dome = max(0.0, float(it.get("dome_depth", 0.0)))
                    uc = 0.5 * (u0 + u1)
                    vc = 0.5 * (v0 + v1)
                    ru = 0.485 * (u1 - u0)
                    rv = 0.485 * (v1 - v0)
                    vcen = bm.verts.new((0.0, -dome, 0.0))
                    if dome > 1e-4:
                        r_mid = rad * 0.56
                        y_mid = -dome * 0.72
                        mid_v = []
                        mid_uv = []
                        rim_v = []
                        rim_uv = []
                        for i in range(n_seg):
                            a = math.tau * i / float(n_seg)
                            ca, sa = math.cos(a), math.sin(a)
                            mid_v.append(bm.verts.new((r_mid * ca, y_mid, r_mid * sa)))
                            mid_uv.append((uc + ru * 0.56 * ca, vc + rv * 0.56 * sa))
                            rim_v.append(bm.verts.new((rad * ca, 0.0, rad * sa)))
                            rim_uv.append((uc + ru * ca, vc + rv * sa))
                        for i in range(n_seg):
                            j = (i + 1) % n_seg
                            f1 = bm.faces.new((vcen, mid_v[i], mid_v[j]))
                            f1.smooth = True
                            for lp, uv_val in zip(f1.loops, ((uc, vc), mid_uv[i], mid_uv[j])):
                                lp[uv_layer].uv = uv_val
                            f2 = bm.faces.new((mid_v[i], rim_v[i], rim_v[j], mid_v[j]))
                            f2.smooth = True
                            for lp, uv_val in zip(f2.loops, (mid_uv[i], rim_uv[i], rim_uv[j], mid_uv[j])):
                                lp[uv_layer].uv = uv_val
                    else:
                        rim_v = []
                        rim_uv = []
                        for i in range(n_seg):
                            a = math.tau * i / float(n_seg)
                            ca, sa = math.cos(a), math.sin(a)
                            rim_v.append(bm.verts.new((rad * ca, 0.0, rad * sa)))
                            rim_uv.append((uc + ru * ca, vc + rv * sa))
                        for i in range(n_seg):
                            j = (i + 1) % n_seg
                            f = bm.faces.new((vcen, rim_v[i], rim_v[j]))
                            f.smooth = False
                            for lp, uv_val in zip(f.loops, ((uc, vc), rim_uv[i], rim_uv[j])):
                                lp[uv_layer].uv = uv_val
                elif kind == "rrect":
                    w_c = max(1e-4, float(it["width"]))
                    h_c = max(1e-4, float(it["height"]))
                    cr_c = float(it.get("corner_r", min(w_c, h_c) * 0.11))
                    cs_c = max(2, int(it.get("segs_corner", 6)))
                    pts_r = self._exact_rrect_pts(w_c, h_c, cr_c, segs_corner=cs_c)
                    r_verts = [bm.verts.new((px, 0.0, pz)) for (px, pz) in pts_r]
                    f = bm.faces.new(r_verts)
                    f.smooth = False
                    for lp, (px, pz) in zip(f.loops, pts_r):
                        uu = u0 + (u1 - u0) * (px / w_c + 0.5)
                        vv = v0 + (v1 - v0) * (pz / h_c + 0.5)
                        lp[uv_layer].uv = (uu, vv)
                else:
                    hw, hh = it["width"] * 0.5, it["height"] * 0.5
                    v0b = bm.verts.new((-hw, 0.0, -hh))
                    v1b = bm.verts.new((hw, 0.0, -hh))
                    v2b = bm.verts.new((hw, 0.0, hh))
                    v3b = bm.verts.new((-hw, 0.0, hh))
                    f = bm.faces.new((v0b, v1b, v2b, v3b))
                    f.smooth = False
                    for lp, uv_val in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                        lp[uv_layer].uv = uv_val

                me_c = bpy.data.meshes.new("{}_{}_m{}".format(self.id, slot_tag, idx))
                bm.normal_update()
                bm.to_mesh(me_c)
                bm.free()
                ca = me_c.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
                ca.data.foreach_set("color_srgb", [1.0] * (len(me_c.loops) * 4))
                me_c.color_attributes.active_color = ca

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
            cols = [
                (
                    (lo + hi) * 0.5 - shift,
                    Vector((max(0.12, hi.x - lo.x), max(0.12, hi.y - lo.y), max(0.12, hi.z - lo.z))),
                )
            ]
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

    def finalize_and_save(
        self,
        out_dir,
        bake_res=1024,
        render_preview=True,
        preview_samples=32,
        auto_decimate=False,
    ):
        """Join parts with crisp palette UVs, center at z=0 facing -Y, bake soft vertex AO,
        attach 1024px shared/packed decals, rig, save `.blend` & render studio preview."""
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        part_count = len(self.parts)
        if part_count == 0:
            raise RuntimeError("KawaiiBuilder({}) has no parts to finalize".format(self.id))

        root = self._apply_uvs_and_join_parts()

        face_tris = 84 if self.low_poly else 200
        def _card_t(c):
            k = c["kind"]
            if k == "sculpt_mesh":
                return int(c.get("est_tris", 1400))
            if k == "mochi_face":
                return 240
            if k == "face_dome":
                return face_tris
            if k == "disc":
                ns = int(c.get("segs", 24))
                return ns * 3 if c.get("dome_depth", 0.0) > 1e-4 else ns
            if k == "rrect":
                return max(2, 4 * (int(c.get("segs_corner", 6)) + 1) - 2)
            return 2

        card_tris = sum(_card_t(c) for c in self.pending_cards)
        if auto_decimate:
            self._enforce_budget(root, reserve_tris=card_tris + 20)

        lo, hi = mesh_bbox(root)
        shift = Vector((-(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5, -lo.z))
        root.data.transform(Matrix.Translation(shift))

        pal_path = self._assign_crisp_palette_uvs(root)
        self._build_and_join_cards(root, shift, out_dir)

        lo2, hi2 = mesh_bbox(root)
        delta_z = -lo2.z if abs(lo2.z) > 0.005 else 0.0
        if abs(delta_z) > 1e-4:
            root.data.transform(Matrix.Translation((0.0, 0.0, delta_z)))
            shift = shift + Vector((0.0, 0.0, delta_z))

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

        ca = root.data.color_attributes.get("Color 1")
        if ca is not None:
            root.data.color_attributes.active_color = ca

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
            "style": "kawaii_studio_v17",
            "low_poly": self.low_poly,
            "size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
            "tris": tris,
            "budget": self.budget,
            "parts": part_count,
            "materials": [m.name for m in root.data.materials],
            "shaders": [m.get("prop_forge_shader", "") for m in root.data.materials],
            "texture": os.path.basename(pal_path),
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
    """Balanced bright cozy Pop-Mart toy studio lighting (crisp pop-art colors, zero blown highlights!)."""
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
        scene.view_settings.exposure = 0.22
    except Exception:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = -0.15

    world = bpy.data.worlds.new("_ks_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = hex_rgba_lin("#EFE6DA", 1.0)
    bg.inputs["Strength"].default_value = 0.85
    scene.world = world

    helpers = []
    sun_d = bpy.data.lights.new("_ks_key", "SUN")
    sun_d.energy = 2.10
    sun_d.color = (1.0, 0.98, 0.94)
    sun_d.angle = math.radians(12)
    sun = bpy.data.objects.new("_ks_key", sun_d)
    sun.rotation_euler = (math.radians(46), math.radians(10), math.radians(-30))
    scene.collection.objects.link(sun)
    helpers.append(sun)

    fill_d = bpy.data.lights.new("_ks_fill", "AREA")
    fill_d.energy = 180.0
    fill_d.size = 6.0
    fill_d.color = (1.0, 0.96, 0.98)
    fill = bpy.data.objects.new("_ks_fill", fill_d)
    fill.location = (4.5, -5.5, 3.8)
    fill.rotation_euler = Vector((4.5, -5.5, 3.8)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(fill)
    helpers.append(fill)

    rim_d = bpy.data.lights.new("_ks_rim", "AREA")
    rim_d.energy = 155.0
    rim_d.size = 5.0
    rim_d.color = (1.0, 0.97, 0.90)
    rim = bpy.data.objects.new("_ks_rim", rim_d)
    rim.location = (-3.0, 4.5, 4.5)
    rim.rotation_euler = Vector((-3.0, 4.5, 4.5)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(rim)
    helpers.append(rim)

    gme = bpy.data.meshes.new("_ks_ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60.0)
    bm.to_mesh(gme)
    bm.free()
    ground = bpy.data.objects.new("_ks_ground", gme)
    gmat = bpy.data.materials.new("_ks_ground")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = hex_rgba_lin("#DFD2C2", 1.0)
    gb.inputs["Roughness"].default_value = 0.86
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


def render_lineup(blend_paths, out_png, samples=48, res=(2400, 1200), rows=2, spacing=0.55, back_riser=0.48):
    """Render all props in a bright warm Pop-Mart showcase studio lineup (zero front/back overlap!)."""
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
    row_depth = 2.75
    objs = []
    max_row_w = 0.0
    for r_idx in range(n_rows):
        chunk = loaded[r_idx * per_row:(r_idx + 1) * per_row]
        if not chunk:
            continue
        total_w = sum(item[1] for item in chunk) + spacing * max(0, len(chunk) - 1)
        max_row_w = max(max_row_w, total_w)
        x = -total_w * 0.5
        y = r_idx * row_depth
        z_lift = float(back_riser) * r_idx
        for ob, w, d, h in chunk:
            ob.location = (x + w * 0.5, y, z_lift)
            x += w + spacing
            objs.append(ob)

    risers = []
    if n_rows > 1 and back_riser > 0.01:
        for r_idx in range(1, n_rows):
            rh = float(back_riser) * r_idx
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=(max_row_w + 1.4, 2.2, rh), verts=bm.verts)
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(0.06, rh * 0.2), segments=2, affect="EDGES", clamp_overlap=True)
            me = bpy.data.meshes.new("_ks_riser_{}".format(r_idx))
            bm.to_mesh(me)
            bm.free()
            rob = bpy.data.objects.new(me.name, me)
            rob.location = (0.0, r_idx * row_depth, rh * 0.5)
            rmat = bpy.data.materials.new("_ks_riser_mat_{}".format(r_idx))
            rmat.use_nodes = True
            rb = rmat.node_tree.nodes.get("Principled BSDF")
            rb.inputs["Base Color"].default_value = hex_rgba_lin("#EFE3D3", 1.0)
            rb.inputs["Roughness"].default_value = 0.72
            me.materials.append(rmat)
            bpy.context.scene.collection.objects.link(rob)
            risers.append(rob)

    bpy.context.view_layer.update()
    direction = (0.0, -1.0, 0.36 if n_rows > 1 else 0.24)
    res_path = render_studio_preview(objs, out_png, samples=samples, res=res, direction=direction, fit=0.94)
    for rob in risers:
        if rob.name in bpy.data.objects:
            bpy.data.objects.remove(rob, do_unlink=True)
    purge_orphans()
    return res_path


# ---------------------------------------------------------------------------
# V13 Self-Test CLI (verifies V4 art packaging, warm brown palette, edge-craft helpers, low-poly & validate)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import sys

    art = prepare_billie_art_v4(DEFAULT_ART_DIR, force=("--force-art" in sys.argv))
    print("PREPARED_ART_V4 count={} dir={}".format(len(art), DEFAULT_ART_DIR), flush=True)
    if "--selftest" in sys.argv:
        test_out = os.path.join(WORKSPACE_ROOT, "work", "billie_prop_v4", "_selftest")
        b = KawaiiBuilder(
            "billie_v13_selftest",
            archetype="kiosk_sign",
            budget=2800,
            collision=True,
            animate=True,
            low_poly=True,
        )
        # V13 Edge-Craft Cabinet (mitered espresso plinth/cornice + 4 corner bumper rails + 8 gold corner studs!)
        b.edge_piped_box(
            (0.96, 0.54, 0.94),
            (0.0, 0.0, 0.47),
            body_role="stripe_caramel",
            trim_role="cocoa",
            accent_role="gold",
            trim_r=0.022,
            collide=True,
        )
        # V13 Upgraded Café Awning with Espresso-Cocoa edge piping + Sunny-Gold scalloped trim beads!
        b.cafe_awning(
            1.08,
            0.40,
            0.22,
            loc=(0.0, -0.27, 1.00),
            stripe_role="caramel",
            alt_role="cream",
            trim_role="cocoa",
            bead_role="gold",
            scallops=6,
        )
        # V13 Double-Stepped Espresso+Gold Plaque Frame (segs_corner=6!) + Crisp 1024x512 Warm-Brown Sign!
        b.decal_card(
            b.art["sign_shop"],
            0.76,
            0.38,
            loc=(0.0, -0.285, 0.44),
            frame_role="cocoa",
            inner_trim_role="gold",
            segs_corner=6,
        )
        # Fresh V4 Custom Warm-Brown Pop-Art Panel on Left Side (double-stepped frame!)
        b.v4_art_panel(
            "shop",
            0.40,
            0.40,
            loc=(-0.49, 0.0, 0.46),
            direction=(-1.0, 0.0, 0.0),
            frame_role="cocoa",
            inner_trim_role="gold",
            segs_corner=6,
        )
        # Animated V13 Topper: Silky 24-seg Double-Sided Smooth Bezel Medallion + Crisp Warm Golden & Glowing Stars!
        b.define_bone("topper", (0.0, 0.0, 1.24))
        with b.use_bone("topper"):
            b.v4_art_medallion(
                "crest",
                0.22,
                loc=(0.0, 0.0, 1.40),
                outer_role="cocoa",
                inner_role="gold",
                depth=0.055,
                segs=24,
                double_sided=True,
            )
            b.plush_star((-0.38, -0.05, 1.46), 0.095, role="gold")
            b.plush_star((0.38, -0.05, 1.46), 0.095, role="glow")
        b.set_anim(frames=121, fps=30, tracks={"topper": {"kind": "crown_hover", "amp_z": 0.06, "rock_y": 6.0}})
        meta = b.finalize_and_save(test_out, render_preview=True, preview_samples=32)
        print("SELFTEST_OK", json.dumps(meta), flush=True)

    if "--test-mascot" in sys.argv:
        test_out = os.path.join(WORKSPACE_ROOT, "work", "billie_prop_v4", "_selftest")
        b = KawaiiBuilder("billie_v13_mascot_test", archetype="mascot_showcase", budget=2800, collision=False, animate=False, low_poly=True)
        b.billie_bear_plush((0.0, 0.0, 0.54), radius=0.26, school="brown", face_mode="illustrated", with_body=True, with_cloud=False)
        meta_m = b.finalize_and_save(test_out, render_preview=True, preview_samples=32)
        print("MASCOT_OK", json.dumps(meta_m), flush=True)
