"""V17 Pure Quad-Flow Studio Library: 4 Official Billie School Mascots, Silky Toy Clouds & Crisp Mini Props.

Designed specifically to eliminate the GTA V RAGE 'jelly/mush' (วุ้น) look caused by Voxel-Remesh + Collapse-Decimate
triangle soup and cramped Smart-UV scraps:
  - 100% clean, regular quad-flow lofts & lathes with `organic_smooth=True` (ZERO 32-deg edge-split faceting,
    ZERO pinched decimate triangles, ZERO muddy UV smudges!)
  - Direct crisp color swatches from `billie_master_pal.png` (Row 2 official 4-house pastel palette!) +
    direct 512x512 per-house razor-sharp anime face projection from `billie_faces_v7.png`!
  - All 4 Billie School House Mascots (`brown` Bear, `pink` Lop-Bunny, `skyblue` Floppy-Puppy, `grey` Tabby-Kitty)
    in `full`, `head`, and `peek` poses!
  - Seamless 1-piece smooth sculpted Cumulus Toy Clouds (eliminates garlic-bulb overlapping spheres!)
  - 18 detailed, crisp miniature studio props & gimmicks to replace cluttered 2D posters!
"""

import math
import os
import bmesh
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MASCOT_DIR = os.path.join(SKILL_ROOT, "assets", "mascots")
FACES_V8_PNG = os.path.join(MASCOT_DIR, "billie_faces_v8.png")
FACES_V7_PNG = FACES_V8_PNG if os.path.exists(FACES_V8_PNG) else os.path.join(MASCOT_DIR, "billie_faces_v7.png")

# Exact 2x2 quadrants inside 1024x1024 billie_faces_v7.png (OpenGL V=0 bottom, V=1 top!)
HOUSE_FACE_UV = {
    "brown":   (0.01, 0.51, 0.49, 0.99),  # Top-Left: Chocolate-Amber starry eyes
    "pink":    (0.51, 0.51, 0.99, 0.99),  # Top-Right: Berry-Rose starry eyes
    "skyblue": (0.01, 0.01, 0.49, 0.49),  # Bot-Left: Sapphire-Sky starry eyes
    "grey":    (0.51, 0.01, 0.99, 0.49),  # Bot-Right: Onyx-Silver starry eyes
}


def _trs(loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    return (
        Matrix.Translation(Vector(loc))
        @ Euler(rot, "XYZ").to_matrix().to_4x4()
        @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    )


def _facing(direction=(0.0, -1.0, 0.0)):
    d = Vector(direction)
    if d.length < 1e-6:
        return Matrix.Identity(4)
    d.normalize()
    q = Vector((0.0, -1.0, 0.0)).rotation_difference(d)
    return q.to_matrix().to_4x4()


def _lathe_z(builder, profile_rz, segs, role, world_m, name="lathe", sx=1.0, sy=1.0, organic=True):
    """Build a watertight smooth quad-flow Z-revolved mesh from [(r, z), ...]."""
    n_s = max(6, int(segs))
    bm = bmesh.new()
    rings = []
    for rad, zp in profile_rz:
        if rad < 1e-5:
            rings.append([bm.verts.new((0.0, 0.0, zp))])
        else:
            ring = []
            for i in range(n_s):
                a = math.tau * i / float(n_s)
                ring.append(bm.verts.new((rad * sx * math.cos(a), rad * sy * math.sin(a), zp)))
            rings.append(ring)
    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        if len(r0) == 1 and len(r1) == 1:
            continue
        elif len(r0) == 1:
            for i in range(n_s):
                j = (i + 1) % n_s
                bm.faces.new((r0[0], r1[j], r1[i]))
        elif len(r1) == 1:
            for i in range(n_s):
                j = (i + 1) % n_s
                bm.faces.new((r0[i], r0[j], r1[0]))
        else:
            for i in range(n_s):
                j = (i + 1) % n_s
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    return builder._add_bm(name, bm, role, world_m, uv_kind="cyl", organic_smooth=organic)


def _smooth_tube(builder, path_pts, segs, role, world_m, name="tube", cap_ends=True, oval=(1.0, 1.0), organic=True):
    """Build a twist-free smooth swept quad tube along [(Vector, radius), ...] using a rotation-minimizing frame."""
    n_s = max(6, int(segs))
    bm = bmesh.new()
    rings = []
    prev_n = None
    prev_t = None
    pts = [Vector(p) for p, _ in path_pts]
    rads = [float(r) for _, r in path_pts]
    for idx, (pt, rad) in enumerate(zip(pts, rads)):
        if idx == 0:
            tang = (pts[1] - pts[0]).normalized()
        elif idx == len(pts) - 1:
            tang = (pts[-1] - pts[-2]).normalized()
        else:
            t_in = (pts[idx] - pts[idx - 1]).normalized()
            t_out = (pts[idx + 1] - pts[idx]).normalized()
            tang = t_in + t_out
            if tang.length < 1e-5:
                tang = t_out
            else:
                tang.normalize()
        if prev_n is None:
            ref = Vector((0.0, 0.0, 1.0)) if abs(tang.z) < 0.90 else Vector((1.0, 0.0, 0.0))
            n1 = tang.cross(ref).normalized()
        else:
            q_rot = prev_t.rotation_difference(tang)
            n1 = q_rot @ prev_n
            n1 = n1 - tang * n1.dot(tang)
            if n1.length < 1e-5:
                ref = Vector((0.0, 0.0, 1.0)) if abs(tang.z) < 0.90 else Vector((1.0, 0.0, 0.0))
                n1 = tang.cross(ref)
            n1.normalize()
        n2 = tang.cross(n1).normalized()
        prev_n = n1
        prev_t = tang
        ring = []
        for i in range(n_s):
            a = math.tau * i / float(n_s)
            p = pt + (n1 * (math.cos(a) * oval[0]) + n2 * (math.sin(a) * oval[1])) * rad
            ring.append(bm.verts.new(p))
        rings.append(ring)

    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(n_s):
            j = (i + 1) % n_s
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))

    if cap_ends and len(rings) >= 2:
        t0 = (pts[1] - pts[0]).normalized()
        c0 = bm.verts.new(pts[0] - t0 * (rads[0] * 0.45))
        t1 = (pts[-1] - pts[-2]).normalized()
        c1 = bm.verts.new(pts[-1] + t1 * (rads[-1] * 0.45))
        for i in range(n_s):
            j = (i + 1) % n_s
            bm.faces.new((c0, rings[0][j], rings[0][i]))
            bm.faces.new((c1, rings[-1][i], rings[-1][j]))

    return builder._add_bm(name, bm, role, world_m, uv_kind="cyl", organic_smooth=organic)


def _smooth_ellipsoid(builder, loc, radii, role, world_m, rot=(0.0, 0.0, 0.0), u_seg=14, v_seg=8, name="ell", organic=True):
    bm = bmesh.new()
    mat = _trs(loc, rot, radii)
    bmesh.ops.create_uvsphere(bm, u_segments=u_seg, v_segments=v_seg, radius=1.0, matrix=mat)
    return builder._add_bm(name, bm, role, world_m, uv_kind="cyl", organic_smooth=organic)


def _smooth_torus(builder, loc, major_r, minor_rx, minor_rz, role, world_m, rot=(0.0, 0.0, 0.0), u_seg=16, v_seg=8, name="tor", organic=True):
    bm = bmesh.new()
    m = _trs(loc, rot)
    rings = []
    for i in range(u_seg):
        a = math.tau * i / float(u_seg)
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for j in range(v_seg):
            b = math.tau * j / float(v_seg)
            cb, sb = math.cos(b), math.sin(b)
            rr = major_r + minor_rx * cb
            ring.append(bm.verts.new(m @ Vector((rr * ca, rr * sa, minor_rz * sb))))
        rings.append(ring)
    for i in range(u_seg):
        ni = (i + 1) % u_seg
        for j in range(v_seg):
            nj = (j + 1) % v_seg
            bm.faces.new((rings[i][j], rings[ni][j], rings[ni][nj], rings[i][nj]))
    return builder._add_bm(name, bm, role, world_m, uv_kind="cyl", organic_smooth=organic)


def _add_heart_3d(builder, loc, size, thick, role, world_m, rot=(0.0, 0.0, 0.0), name="heart", segs=12):
    """Smooth sculpted plump 3D heart badge (faces -Y)."""
    bm = bmesh.new()
    m = _trs(loc, rot)
    ring_f = []
    ring_b = []
    for i in range(segs):
        t = math.tau * i / float(segs)
        hx = 16.0 * (math.sin(t) ** 3) / 16.0
        hz = (13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t)) / 16.0
        px = hx * size
        pz = hz * size
        ring_f.append(bm.verts.new(m @ Vector((px, -thick * 0.30, pz))))
        ring_b.append(bm.verts.new(m @ Vector((px, +thick * 0.30, pz))))
    cf = bm.verts.new(m @ Vector((0.0, -thick * 0.72, size * 0.05)))
    cb = bm.verts.new(m @ Vector((0.0, +thick * 0.50, size * 0.05)))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((cf, ring_f[j], ring_f[i]))
        bm.faces.new((cb, ring_b[i], ring_b[j]))
        bm.faces.new((ring_f[i], ring_f[j], ring_b[j], ring_b[i]))
    return builder._add_bm(name, bm, role, world_m, uv_kind="box", organic_smooth=True)


def _add_blossom_4petal(builder, loc, size, thick, role, world_m, rot=(0.0, 0.0, 0.0), name="blossom"):
    """Cute plump rounded 4-petal white cloud-flower hairclip matching official mascots!"""
    bm = bmesh.new()
    m = _trs(loc, rot)
    n_s = 8
    ring_f = []
    for i in range(n_s):
        a = math.tau * i / float(n_s)
        rr = size * (0.98 if (i % 2 == 1) else 0.58)
        ring_f.append(bm.verts.new(m @ Vector((rr * math.cos(a), 0.0, rr * math.sin(a)))))
    cf = bm.verts.new(m @ Vector((0.0, -thick * 0.65, 0.0)))
    cb = bm.verts.new(m @ Vector((0.0, +thick * 0.35, 0.0)))
    for i in range(n_s):
        j = (i + 1) % n_s
        bm.faces.new((cf, ring_f[j], ring_f[i]))
        bm.faces.new((cb, ring_f[i], ring_f[j]))
    return builder._add_bm(name, bm, role, world_m, uv_kind="box", organic_smooth=True)


def _add_star5_3d(builder, loc, size, thick, role, world_m, rot=(0.0, 0.0, 0.0), name="star5"):
    """Plump sculpted 5-pointed kawaii star (exact match to Skyblue Puppy's golden hip star & accents!)."""
    bm = bmesh.new()
    m = _trs(loc, rot)
    ring = []
    for i in range(10):
        a = math.pi * 0.5 + math.tau * i / 10.0
        rr = size * (1.00 if (i % 2 == 0) else 0.48)
        ring.append(bm.verts.new(m @ Vector((rr * math.cos(a), 0.0, rr * math.sin(a)))))
    cf = bm.verts.new(m @ Vector((0.0, -thick * 0.62, 0.0)))
    cb = bm.verts.new(m @ Vector((0.0, +thick * 0.38, 0.0)))
    for i in range(10):
        j = (i + 1) % 10
        bm.faces.new((cf, ring[j], ring[i]))
        bm.faces.new((cb, ring[i], ring[j]))
    return builder._add_bm(name, bm, role, world_m, uv_kind="box", organic_smooth=True)


# ---------------------------------------------------------------------------
# 1. V8 ULTRA-DETAILED PURE QUAD-FLOW 4-HOUSE BILLIE SCHOOL MASCOTS (1:1 OFFICIAL!)
# ---------------------------------------------------------------------------

def add_billie_mascot_v7(
    builder,
    house="brown",
    pose="full",
    loc=(0.0, 0.0, 0.0),
    radius=0.22,
    rot=(0.0, 0.0, 0.0),
    direction=(0.0, -1.0, 0.0),
    M=None,
    with_cloud=False,
):
    """Build any of the 4 official Billie School mascots (`brown` Bear, `pink` Lop-Bunny, `skyblue` Floppy-Puppy, `grey` Tabby-Kitty)
    in `full`, `head`, or `peek` pose with V8 Pop-Mart / Nendoroid high-detail pure smooth quad topology!

    Anchor conventions (100% compatible with existing prop placement):
      - pose='head': centered at head center `loc`, hood width ≈ 2.1 * radius
      - pose='full': head center at `loc`, feet planted solidly at Z = loc.z - 1.96 * radius
      - pose='peek': resting rim (top of sign/pipe/arch) at `loc.z`, head peeking above, arms draping forward over `-Y`
    """
    h = str(house).lower()
    if h not in ("brown", "pink", "skyblue", "grey"):
        h = "brown"
    pk = str(pose).lower()
    if pk not in ("full", "head", "peek"):
        pk = "full"

    r = float(radius)
    base_m = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ _facing(direction) @ _trs((0.0, 0.0, 0.0), rot)

    if pk == "peek":
        body_m = base_m @ Matrix.Translation((0.0, 0.0, 0.84 * r)) @ Matrix.Diagonal((r, r, r, 1.0))
        head_m = body_m
    elif pk == "full":
        body_m = base_m @ Matrix.Diagonal((r, r, r, 1.0))
        # Cheerful subtle kawaii head tilt (+4.2 deg) on full-body figurine just like official mascot-*.png!
        head_m = body_m @ _trs((0.0, 0.0, 0.02), (0.0, math.radians(-4.2), 0.0))
    else:
        body_m = base_m @ Matrix.Diagonal((r, r, r, 1.0))
        head_m = body_m

    # Official 4-House Palette Mapping (Row 2 cozy plush fleece swatches in billie_master_pal.png)
    house_pal = {
        "brown":   ("m_brown", "m_brown_belly", "m_brown_cuff", "m_brown_hair", "m_brown_belly"),
        "pink":    ("m_pink",  "m_pink_in",     "m_pink_cuff",  "m_pink_hair",  "m_pink_in"),
        "skyblue": ("m_sky",   "m_sky_in",      "m_sky_cuff",   "m_sky_hair",   "m_sky_cuff"),
        "grey":    ("m_grey",  "m_sky_in",      "m_grey_dark",  "m_brown_hair", "m_grey_belly"),
    }
    hood_role, ear_in_role, cuff_role, hair_role, belly_role = house_pal[h]

    # ------------------------------------------------------------------
    # A. SILKY 20-SEG WIDE CHUBBY MOCHI PLUSH HOOD WITH DEEP ROLLED LIP!
    # ------------------------------------------------------------------
    bm_h = bmesh.new()
    u_seg = 20
    hood_profile = [
        (0.000, +0.940),  # smooth back crown pole
        (0.420, +0.865),
        (0.760, +0.620),
        (0.995, +0.200),
        (1.075, -0.140),  # wide chubby mochi plush cheeks!
        (1.025, -0.490),
        (0.905, -0.710),  # outer plush roll around wide face window
        (0.810, -0.805),  # plump front crest of rolled fleece lip
        (0.735, -0.755),  # tucking softly inward around cheeks
        (0.695, -0.520),  # deep cozy shadow cavity hugging chibi face
    ]
    rings_h = []
    for rad, yp in hood_profile:
        if rad < 1e-5:
            rings_h.append([bm_h.verts.new((0.0, yp, 0.02))])
        else:
            ring = []
            for i in range(u_seg):
                a = math.tau * i / float(u_seg)
                ca, sa = math.cos(a), math.sin(a)
                # Wider horizontal mochi oval (1.10x wide, extra soft chubby lower cheeks)
                sx = 1.09 + 0.075 * max(0.0, -sa) - 0.025 * max(0.0, sa)
                sz = 0.965 - 0.035 * max(0.0, -sa)
                z_off = -0.045 if yp < -0.50 else -0.010
                ring.append(bm_h.verts.new((rad * sx * ca, yp, rad * sz * sa + z_off)))
            rings_h.append(ring)
    for k in range(len(rings_h) - 1):
        r0, r1 = rings_h[k], rings_h[k + 1]
        if len(r0) == 1:
            for i in range(u_seg):
                j = (i + 1) % u_seg
                bm_h.faces.new((r0[0], r1[i], r1[j]))
        else:
            for i in range(u_seg):
                j = (i + 1) % u_seg
                bm_h.faces.new((r0[i], r1[i], r1[j], r0[j]))
    builder._add_bm("m_hood", bm_h, hood_role, head_m, uv_kind="cyl", organic_smooth=True)

    # ------------------------------------------------------------------
    # B. HIGH-DETAIL 12x10 SCULPTED 3D MOCHI FACE + CUTE PEEKING HUMAN EARS!
    # ------------------------------------------------------------------
    _smooth_ellipsoid(builder, (0.0, -0.30, -0.05), (0.73, 0.28, 0.63), "skin", head_m, u_seg=12, v_seg=5, name="m_faceback")
    face_m = head_m @ Matrix.Translation((0.0, -0.59, -0.065))
    builder.pending_cards.append({
        "kind": "mochi_face",
        "image": FACES_V7_PNG,
        "uv_rect": HOUSE_FACE_UV[h],
        "rx": 0.775,
        "rz": 0.665,
        "ry": 0.255,
        "matrix": face_m,
        "emissive": False,
        "transparent": False,
        "bone": builder.current_bone,
    })
    # Adorable sculpted 3D human baby ears with soft pink inner dimples peeking beside the cheeks!
    for sx in (-1.0, 1.0):
        em_h = head_m @ _trs((sx * 0.72, -0.58, -0.17), (0.05, 0.0, sx * -0.26))
        _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.125, 0.095, 0.160), "skin", em_h, u_seg=8, v_seg=4, name="m_hum_ear")
        _smooth_ellipsoid(builder, (sx * 0.015, -0.068, -0.010), (0.065, 0.042, 0.090), "blush", em_h, u_seg=6, v_seg=3, name="m_hum_ear_i")

    # ------------------------------------------------------------------
    # C. HUGE LUSH 3-LOBE SCALLOPED CLOUD BANGS + TEMPLE LOCKS + TWIN 4-PETAL CLOVER CLIPS!
    # ------------------------------------------------------------------
    _smooth_ellipsoid(builder, (0.0, -0.45, 0.44), (0.76, 0.44, 0.33), hair_role, head_m, u_seg=12, v_seg=5, name="m_hair_cap")
    # Lush overlapping plump hair pillows matching exact 3-lobe scalloped bangs in mascot-*.png!
    bang_puffs = [
        ((-0.03, -0.71, 0.31), (0.37, 0.24, 0.30), (0.22, -0.10, 0.02)),   # huge plush center cloud puff
        ((+0.39, -0.64, 0.28), (0.31, 0.22, 0.27), (0.20, +0.26, -0.24)),  # lush right scallop lobe
        ((-0.41, -0.64, 0.27), (0.30, 0.22, 0.26), (0.20, -0.28, +0.24)),  # lush left scallop lobe
        ((-0.65, -0.54, 0.08), (0.19, 0.17, 0.25), (0.10, -0.34, +0.36)),  # cute left temple lock over human ear
        ((+0.65, -0.54, 0.08), (0.19, 0.17, 0.25), (0.10, +0.34, -0.36)),  # cute right temple lock over human ear
    ]
    for b_loc, b_rad, b_rot in bang_puffs:
        _smooth_ellipsoid(builder, b_loc, b_rad, hair_role, head_m, rot=b_rot, u_seg=10, v_seg=5, name="m_bang")

    # Crisp 4-petal white clover hair clips perched cleanly ON the front bang curve (zero petal-center Z-fighting!)
    for c_loc, c_rad, c_rot in (
        ((-0.46, -0.855, 0.15), 0.095, (0.18, -0.34, 0.40)),
        ((+0.44, -0.865, 0.25), 0.108, (0.18, +0.32, -0.34)),
    ):
        cm = head_m @ _trs(c_loc, c_rot)
        for pk_i in range(4):
            pa = math.radians(45.0 + 90.0 * pk_i)
            _smooth_ellipsoid(
                builder,
                (c_rad * 0.58 * math.cos(pa), 0.0, c_rad * 0.58 * math.sin(pa)),
                (c_rad * 0.50, c_rad * 0.28, c_rad * 0.50),
                "white", cm, u_seg=5, v_seg=3, name="m_clover_p"
            )
        _smooth_ellipsoid(builder, (0.0, -c_rad * 0.28, 0.0), (c_rad * 0.32, c_rad * 0.28, c_rad * 0.32), "cream", cm, u_seg=5, v_seg=3, name="m_clover_c")

    # ------------------------------------------------------------------
    # D. OFFICIAL HOUSE-SPECIFIC SCULPTED 3D ANIMAL HOOD DETAILS!
    # ------------------------------------------------------------------
    if h == "brown":
        # Thick two-tone cupped plush bear ears (16-seg silky!)
        for sx in (-1.0, 1.0):
            em = head_m @ _trs((sx * 0.82, -0.06, 0.76), (0.08, sx * -0.54, sx * -0.14))
            _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.37, 0.22, 0.36), "m_brown_cuff", em, u_seg=16, v_seg=7, name="m_bear_ear_o")
            _smooth_ellipsoid(builder, (0.0, -0.13, -0.02), (0.24, 0.11, 0.23), "m_brown_belly", em, u_seg=12, v_seg=5, name="m_bear_ear_i")
        # Plump sculpted bear snout muzzle + recessed Y nose/smile + sleepy cocoa brows
        _smooth_ellipsoid(builder, (0.0, -0.75, 0.70), (0.24, 0.16, 0.17), "m_brown_cuff", head_m, rot=(-0.34, 0.0, 0.0), u_seg=14, v_seg=6, name="m_bear_muz")
        _smooth_ellipsoid(builder, (0.0, -0.90, 0.73), (0.056, 0.034, 0.034), "cocoa", head_m, u_seg=8, v_seg=4, name="m_bear_n0")
        _smooth_tube(builder, [(Vector((0.0, -0.89, 0.66)), 0.020), (Vector((0.0, -0.91, 0.73)), 0.022)], 8, "cocoa", head_m, cap_ends=False, name="m_bear_ny")
        for sx in (-1.0, 1.0):
            _smooth_tube(builder, [(Vector((0.0, -0.91, 0.73)), 0.020), (Vector((sx * 0.072, -0.87, 0.77)), 0.018)], 8, "cocoa", head_m, cap_ends=False, name="m_bear_narm")
            _smooth_ellipsoid(builder, (sx * 0.38, -0.71, 0.76), (0.090, 0.048, 0.040), "m_brown_cuff", head_m, rot=(-0.30, sx * -0.26, sx * -0.22), u_seg=8, v_seg=4, name="m_bear_brow")
        # Silky 8-lobed plump tangerine (16x6 quads!) with curved stem & arched leaf pair
        bm_t = bmesh.new()
        u_t, v_t = 16, 6
        t_rings = []
        for iv in range(1, v_t):
            phi = math.pi * iv / float(v_t)
            sp, cp = math.sin(phi), math.cos(phi)
            dimp = -0.050 * math.exp(-((phi / 0.42) ** 2))
            ring = []
            for iu in range(u_t):
                th = math.tau * iu / float(u_t)
                lobe = 1.0 + 0.048 * (sp ** 1.4) * math.cos(8.0 * th)
                ring.append(bm_t.verts.new((0.28 * lobe * sp * math.cos(th), 0.27 * lobe * sp * math.sin(th) - 0.06, 1.04 + 0.18 * cp + dimp)))
            t_rings.append(ring)
        vt = bm_t.verts.new((0.0, -0.06, 1.04 + 0.18 - 0.050))
        vb = bm_t.verts.new((0.0, -0.06, 1.04 - 0.18))
        for iu in range(u_t):
            nu = (iu + 1) % u_t
            bm_t.faces.new((vt, t_rings[0][iu], t_rings[0][nu]))
            bm_t.faces.new((vb, t_rings[-1][nu], t_rings[-1][iu]))
        for iv in range(len(t_rings) - 1):
            for iu in range(u_t):
                nu = (iu + 1) % u_t
                bm_t.faces.new((t_rings[iv][iu], t_rings[iv + 1][iu], t_rings[iv + 1][nu], t_rings[iv][nu]))
        builder._add_bm("m_tang", bm_t, "tangerine", head_m, uv_kind="cyl", organic_smooth=True)
        _smooth_tube(builder, [(Vector((0.0, -0.06, 1.16)), 0.024), (Vector((0.015, -0.07, 1.26)), 0.018)], 8, "sage_deep", head_m, name="m_tstem")
        _smooth_ellipsoid(builder, (+0.11, -0.07, 1.23), (0.120, 0.052, 0.026), "leaf_fresh", head_m, rot=(0.14, -0.28, -0.15), u_seg=8, v_seg=4, name="m_tleaf_r")
        _smooth_ellipsoid(builder, (-0.10, -0.06, 1.22), (0.105, 0.048, 0.024), "leaf_fresh", head_m, rot=(0.12, +0.30, +0.18), u_seg=8, v_seg=4, name="m_tleaf_l")

    elif h == "pink":
        # Graceful sweeping 7-point 12-seg velvety lop-bunny ears curving organically past cheeks!
        for sx in (-1.0, 1.0):
            ear_pts = [
                (Vector((sx * 0.42, -0.04, 0.90)), 0.24),
                (Vector((sx * 0.78, -0.06, 0.78)), 0.29),
                (Vector((sx * 1.08, -0.08, 0.50)), 0.30),
                (Vector((sx * 1.24, -0.10, 0.12)), 0.28),
                (Vector((sx * 1.22, -0.11, -0.24)), 0.25),
                (Vector((sx * 1.12, -0.11, -0.50)), 0.19),
            ]
            _smooth_tube(builder, ear_pts, 12, "m_pink", head_m, oval=(0.64, 1.18), name="m_bun_ear")
            in_pts = [
                (Vector((sx * 0.72, -0.21, 0.72)), 0.14),
                (Vector((sx * 1.03, -0.25, 0.44)), 0.17),
                (Vector((sx * 1.14, -0.26, 0.06)), 0.16),
                (Vector((sx * 1.09, -0.25, -0.34)), 0.12),
            ]
            _smooth_tube(builder, in_pts, 10, "m_pink_in", head_m, oval=(0.50, 0.92), name="m_bun_ear_i")
            # Signature twin 3D braided pink hood pigtails dangling cleanly at lower-left/right of hood behind arms!
            for bi, (bx, by, bz, br) in enumerate((
                (sx * 0.78, -0.14, -0.68, 0.102),
                (sx * 0.90, -0.16, -0.77, 0.092),
                (sx * 0.99, -0.18, -0.85, 0.080),
            )):
                _smooth_ellipsoid(builder, (bx, by, bz), (br * 1.15, br * 0.95, br), "m_pink_in" if bi == 1 else "m_pink", head_m, rot=(0.0, 0.0, sx * 0.45), u_seg=6, v_seg=3, name="m_bun_braid")
        # Plump sculpted rounded bunny top pom-pom tuft
        _smooth_ellipsoid(builder, (0.0, -0.24, 1.02), (0.35, 0.29, 0.26), "m_pink", head_m, u_seg=14, v_seg=6, name="m_bun_pom")

    elif h == "skyblue":
        # Graceful sweeping 7-point 12-seg velvety floppy puppy ears with soft pink inner lining!
        for sx in (-1.0, 1.0):
            ear_pts = [
                (Vector((sx * 0.48, -0.05, 0.88)), 0.24),
                (Vector((sx * 0.84, -0.07, 0.74)), 0.29),
                (Vector((sx * 1.12, -0.09, 0.42)), 0.30),
                (Vector((sx * 1.24, -0.11, 0.02)), 0.28),
                (Vector((sx * 1.18, -0.12, -0.36)), 0.22),
            ]
            _smooth_tube(builder, ear_pts, 12, "m_sky", head_m, oval=(0.64, 1.18), name="m_pup_ear")
            in_pts = [
                (Vector((sx * 0.76, -0.22, 0.68)), 0.14),
                (Vector((sx * 1.04, -0.26, 0.34)), 0.17),
                (Vector((sx * 1.12, -0.27, -0.04)), 0.16),
                (Vector((sx * 1.08, -0.25, -0.28)), 0.12),
            ]
            _smooth_tube(builder, in_pts, 10, "m_sky_in", head_m, oval=(0.50, 0.92), name="m_pup_ear_i")
            # Cute pastel-pink oval cheek spots on hood forehead!
            _smooth_ellipsoid(builder, (sx * 0.42, -0.71, 0.74), (0.110, 0.052, 0.054), "m_sky_in", head_m, rot=(-0.28, sx * -0.24, 0.0), u_seg=8, v_seg=4, name="m_pup_blush")
        _smooth_ellipsoid(builder, (0.0, -0.26, 1.02), (0.36, 0.30, 0.27), "m_sky", head_m, u_seg=14, v_seg=6, name="m_pup_pom")

    elif h == "grey":
        # Lush 14-seg rounded-triangle plush cat ears with concave soft-pink inner fur!
        for sx in (-1.0, 1.0):
            em = head_m @ _trs((sx * 0.70, -0.04, 0.76), (0.06, sx * -0.44, sx * -0.10))
            _lathe_z(
                builder,
                [(0.0, -0.14), (0.40, 0.00), (0.35, 0.28), (0.22, 0.54), (0.09, 0.68), (0.0, 0.71)],
                14, "m_grey", em, name="m_cat_ear_o", sx=1.08, sy=0.62
            )
            _lathe_z(
                builder,
                [(0.0, 0.00), (0.26, 0.06), (0.21, 0.30), (0.11, 0.50), (0.0, 0.55)],
                10, "m_sky_in", em @ Matrix.Translation((0.0, -0.14, 0.0)), name="m_cat_ear_i", sx=1.02, sy=0.46
            )
        # Signature thick rolled light-grey fleece brow cuff arching cleanly above bangs!
        _smooth_tube(
            builder,
            [
                (Vector((-0.66, -0.66, 0.38)), 0.115),
                (Vector((-0.36, -0.78, 0.57)), 0.145),
                (Vector((0.00,  -0.83, 0.65)), 0.155),
                (Vector((+0.36, -0.78, 0.57)), 0.145),
                (Vector((+0.66, -0.66, 0.38)), 0.115),
            ],
            12, "m_grey_belly", head_m, name="m_cat_lip"
        )
        # Two adorable crisp sculpted tiny white monster-kitty fangs peeking clearly down over the bangs!
        for sx in (-1.0, 1.0):
            fm = head_m @ Matrix.Translation((sx * 0.24, -0.89, 0.51))
            _lathe_z(builder, [(0.0, -0.145), (0.050, 0.0), (0.056, 0.05), (0.0, 0.06)], 6, "white", fm, name="m_cat_fang")
        # Clean fitted dark-grey tabby stripes: 3 forehead stripes + 2 pairs of side cheek stripes!
        _smooth_ellipsoid(builder, (0.0, -0.62, 0.91), (0.065, 0.17, 0.048), "m_grey_dark", head_m, rot=(0.45, 0.0, 0.0), u_seg=8, v_seg=4, name="m_cat_st0")
        for sx in (-1.0, 1.0):
            _smooth_ellipsoid(builder, (sx * 0.26, -0.68, 0.83), (0.135, 0.052, 0.040), "m_grey_dark", head_m, rot=(-0.35, sx * -0.22, 0.0), u_seg=8, v_seg=4, name="m_cat_st1")
            _smooth_ellipsoid(builder, (sx * 1.03, -0.22, 0.22), (0.052, 0.15, 0.044), "m_grey_dark", head_m, rot=(0.0, sx * -0.22, 0.0), u_seg=8, v_seg=4, name="m_cat_st2a")
            _smooth_ellipsoid(builder, (sx * 1.07, -0.24, 0.02), (0.052, 0.16, 0.044), "m_grey_dark", head_m, rot=(0.0, sx * -0.10, 0.0), u_seg=8, v_seg=4, name="m_cat_st2b")

    # ------------------------------------------------------------------
    # E. SIGNATURE 3D SCULPTED COLLAR CHARMS (on `head` and `full`!)
    # ------------------------------------------------------------------
    if h == "brown" and pk in ("head", "full"):
        # Plump sculpted pleated chocolate bow-tie!
        _smooth_ellipsoid(builder, (0.0, -0.56, -0.94), (0.115, 0.095, 0.105), "m_brown_cuff", body_m, u_seg=10, v_seg=5, name="m_bow_k")
        for sx in (-1.0, 1.0):
            wm_b = body_m @ _trs((sx * 0.21, -0.54, -0.94), (0.10, sx * -0.20, sx * 0.22))
            _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.19, 0.090, 0.145), "m_brown_cuff", wm_b, u_seg=10, v_seg=5, name="m_bow_w")
            _smooth_ellipsoid(builder, (sx * 0.06, -0.055, 0.0), (0.09, 0.032, 0.030), "cocoa", wm_b, u_seg=6, v_seg=3, name="m_bow_pl")
    elif h == "skyblue" and pk in ("head", "full"):
        # Iconic sculpted 3D Split RED + ROYAL-BLUE Sailor Collar Triangles with twin crisp white pom-poms!
        for sx, cr in ((-1.0, "m_sky_red"), (+1.0, "m_sky_blue")):
            bm_sc = bmesh.new()
            # Clean sculpted curved collar triangle hugging chest front
            v0 = bm_sc.verts.new((0.0, -0.53, -0.89))
            v1 = bm_sc.verts.new((sx * 0.30, -0.49, -0.90))
            v2 = bm_sc.verts.new((sx * 0.29, -0.57, -1.11))
            v3 = bm_sc.verts.new((0.0, -0.58, -1.03))
            v0b = bm_sc.verts.new((0.0, -0.46, -0.89))
            v1b = bm_sc.verts.new((sx * 0.30, -0.42, -0.90))
            v2b = bm_sc.verts.new((sx * 0.29, -0.49, -1.11))
            v3b = bm_sc.verts.new((0.0, -0.50, -1.03))
            if sx > 0:
                bm_sc.faces.new((v0, v3, v2, v1))
                bm_sc.faces.new((v0b, v1b, v2b, v3b))
                bm_sc.faces.new((v0, v1, v1b, v0b))
                bm_sc.faces.new((v1, v2, v2b, v1b))
                bm_sc.faces.new((v2, v3, v3b, v2b))
                bm_sc.faces.new((v3, v0, v0b, v3b))
            else:
                bm_sc.faces.new((v0, v1, v2, v3))
                bm_sc.faces.new((v0b, v3b, v2b, v1b))
                bm_sc.faces.new((v0, v0b, v1b, v1))
                bm_sc.faces.new((v1, v1b, v2b, v2))
                bm_sc.faces.new((v2, v2b, v3b, v3))
                bm_sc.faces.new((v3, v3b, v0b, v0))
            builder._add_bm("m_sky_col", bm_sc, cr, body_m, uv_kind="box", organic_smooth=False)
            _smooth_ellipsoid(builder, (sx * 0.31, -0.58, -1.12), (0.064, 0.064, 0.064), "white", body_m, u_seg=8, v_seg=4, name="m_sky_pom")

    # ------------------------------------------------------------------
    # F. POSE='FULL': ULTRA-CUTE SILKY QUAD BODY + OPEN PAW-PAD WAVING HAND!
    # ------------------------------------------------------------------
    if pk == "full":
        torso_prof = [
            (0.000, -1.62), (0.430, -1.56), (0.595, -1.38), (0.605, -1.16),
            (0.515, -0.92), (0.375, -0.74), (0.000, -0.68),
        ]
        _lathe_z(builder, torso_prof, 16, hood_role, body_m, name="m_torso", sx=1.03, sy=0.90)

        if h == "brown":
            _smooth_ellipsoid(builder, (0.0, -0.47, -1.25), (0.36, 0.14, 0.37), "m_brown_belly", body_m, u_seg=12, v_seg=6, name="m_belly")
            _smooth_ellipsoid(builder, (0.0, -0.54, -1.07), (0.078, 0.044, 0.155), "m_brown_cuff", body_m, u_seg=8, v_seg=4, name="m_plack")
            for bz in (-1.01, -1.11):
                _smooth_ellipsoid(builder, (0.0, -0.58, bz), (0.034, 0.020, 0.034), "white", body_m, rot=(0.0, math.pi * 0.25, 0.0), u_seg=6, v_seg=3, name="m_btn")
        elif h == "pink":
            _add_heart_3d(builder, (0.0, -0.54, -1.20), 0.27, 0.088, "m_pink_cuff", body_m, name="m_pink_heart", segs=18)
            _add_heart_3d(builder, (0.0, -0.52, -1.20), 0.315, 0.068, "m_pink_in", body_m, name="m_pink_heart_rim", segs=18)
        elif h == "skyblue":
            _smooth_ellipsoid(builder, (0.0, -0.47, -1.25), (0.36, 0.13, 0.35), "m_sky_cuff", body_m, u_seg=12, v_seg=6, name="m_sky_belly")
            # Real 5-pointed plump golden star sewn onto lower-left hip (exact match to mascot-skyblue.png!)
            _add_star5_3d(builder, (-0.21, -0.58, -1.32), 0.165, 0.065, "gold", body_m, rot=(0.12, 0.20, 0.16), name="m_sky_star")
        elif h == "grey":
            _smooth_ellipsoid(builder, (0.0, -0.47, -1.25), (0.36, 0.14, 0.37), "m_grey_belly", body_m, u_seg=12, v_seg=6, name="m_grey_belly")

        # Chubby separated 10-seg plush legs + thick ankle cuffs + padded rounded booties
        for sx in (-1.0, 1.0):
            leg_pts = [
                (Vector((sx * 0.29,  0.00, -1.40)), 0.270),
                (Vector((sx * 0.34, -0.02, -1.61)), 0.232),
                (Vector((sx * 0.37, -0.04, -1.78)), 0.205),
            ]
            _smooth_tube(builder, leg_pts, 10, hood_role, body_m, cap_ends=False, name="m_leg")
            _smooth_torus(builder, (sx * 0.37, -0.04, -1.80), 0.172, 0.060, 0.058, cuff_role, body_m, u_seg=10, v_seg=5, name="m_acuff")
            foot_prof = [(0.0, -1.96), (0.198, -1.96), (0.224, -1.89), (0.186, -1.80), (0.0, -1.78)]
            _lathe_z(builder, foot_prof, 10, cuff_role, body_m @ Matrix.Translation((sx * 0.37, -0.08, 0.0)), name="m_foot", sx=1.00, sy=1.24)
            if h == "grey":
                _smooth_torus(builder, (sx * 0.36, -0.03, -1.67), 0.202, 0.038, 0.038, "m_grey_dark", body_m, u_seg=8, v_seg=4, name="m_cat_legst")

        # Raised joyful waving left arm (+X) with OPEN CHIBI PALM, 4 sculpted fingers + pink heart pad & 3 toe beans!
        l_arm = [
            (Vector((0.37, -0.02, -0.94)), 0.225),
            (Vector((0.63, -0.08, -0.76)), 0.195),
            (Vector((0.92, -0.18, -0.46)), 0.165),
        ]
        _smooth_tube(builder, l_arm, 10, hood_role, body_m, cap_ends=False, name="m_larm")
        _smooth_torus(builder, (0.92, -0.18, -0.46), 0.145, 0.058, 0.054, cuff_role, body_m, rot=(0.22, 0.78, -0.22), u_seg=10, v_seg=5, name="m_lcuff")
        hm_l = body_m @ _trs((1.05, -0.21, -0.33), (0.14, 0.66, -0.26))
        _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.170, 0.118, 0.172), "skin", hm_l, u_seg=8, v_seg=5, name="m_lhand")
        for (fx, fz, fr) in ((-0.135, 0.03, 0.056), (-0.060, 0.148, 0.050), (0.030, 0.155, 0.050), (0.115, 0.112, 0.046)):
            _smooth_ellipsoid(builder, (fx, -0.01, fz), (fr, fr * 0.85, fr * 1.15), "skin", hm_l, u_seg=5, v_seg=3, name="m_lfing")
        # Adorable pink central paw pad + 3 tiny pink toe beans right on the open waving palm!
        _smooth_ellipsoid(builder, (0.00, -0.112, -0.025), (0.075, 0.024, 0.060), "paw_pink", hm_l, u_seg=6, v_seg=3, name="m_lpad")
        for (tx, tz) in ((-0.068, 0.065), (0.000, 0.088), (+0.068, 0.065)):
            _smooth_ellipsoid(builder, (tx, -0.110, tz), (0.030, 0.018, 0.030), "paw_pink", hm_l, u_seg=5, v_seg=3, name="m_lbean")

        # Cute extended right arm (-X) with contrasting cuff + sculpted chibi hand & tiny fingers!
        r_arm = [
            (Vector((-0.37, -0.02, -0.95)), 0.225),
            (Vector((-0.60, -0.06, -1.10)), 0.192),
            (Vector((-0.82, -0.10, -1.26)), 0.168),
        ]
        _smooth_tube(builder, r_arm, 10, hood_role, body_m, cap_ends=False, name="m_rarm")
        _smooth_torus(builder, (-0.82, -0.10, -1.26), 0.140, 0.054, 0.052, cuff_role, body_m, rot=(0.15, 0.84, 0.18), u_seg=10, v_seg=5, name="m_rcuff")
        hm_r = body_m @ _trs((-0.94, -0.12, -1.36), (0.15, 0.82, 0.18))
        _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.145, 0.112, 0.148), "skin", hm_r, u_seg=8, v_seg=4, name="m_rhand")
        for (fx, fz) in ((-0.09, -0.08), (0.00, -0.12), (+0.09, -0.08)):
            _smooth_ellipsoid(builder, (fx, -0.01, fz), (0.044, 0.040, 0.048), "skin", hm_r, u_seg=5, v_seg=3, name="m_rfing")

        # Plush tail behind!
        if h == "grey":
            t_pts = [
                (Vector((0.0, 0.45, -1.44)), 0.115),
                (Vector((0.0, 0.74, -1.34)), 0.125),
                (Vector((0.0, 0.82, -1.02)), 0.105),
            ]
            _smooth_tube(builder, t_pts, 10, "m_grey", body_m, name="m_cat_tail")
            for ty, tz in ((0.64, -1.38), (0.79, -1.16)):
                _smooth_torus(builder, (0.0, ty, tz), 0.110, 0.032, 0.032, "m_grey_dark", body_m, rot=(0.95, 0.0, 0.0), u_seg=10, v_seg=4, name="m_cat_tst")
        else:
            tail_r = "white" if h == "pink" else hood_role
            _smooth_ellipsoid(builder, (0.0, 0.54, -1.42), (0.18, 0.17, 0.17), tail_r, body_m, u_seg=10, v_seg=5, name="m_tail")

    # ------------------------------------------------------------------
    # G. POSE='PEEK': SILKY 10-SEG CURVED ARMS & PLUMP PAW-PAD HANDS GRIPPING RIM!
    # ------------------------------------------------------------------
    elif pk == "peek":
        _smooth_ellipsoid(builder, (0.0, 0.18, -1.04), (0.68, 0.30, 0.27), hood_role, head_m, u_seg=8, v_seg=4, name="m_peek_sh")
        for sx in (-1.0, 1.0):
            p_arm = [
                (Vector((sx * 0.58,  0.18, -1.02)), 0.21),
                (Vector((sx * 0.83, -0.02, -0.82)), 0.185),
                (Vector((sx * 0.85, -0.45, -0.74)), 0.158),
            ]
            _smooth_tube(builder, p_arm, 8, hood_role, head_m, cap_ends=False, name="m_peek_arm")
            _smooth_torus(builder, (sx * 0.85, -0.45, -0.74), 0.140, 0.054, 0.052, cuff_role, head_m, rot=(1.55, 0.0, sx * 0.14), u_seg=8, v_seg=4, name="m_peek_cuff")
            pm = head_m @ _trs((sx * 0.84, -0.60, -0.77), (0.20, 0.0, sx * 0.12))
            _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.175, 0.160, 0.125), "skin", pm, u_seg=8, v_seg=4, name="m_peek_paw")
            for fx in (-0.088, 0.0, +0.088):
                _smooth_ellipsoid(builder, (fx, -0.115, -0.035), (0.048, 0.048, 0.054), "skin", pm, rot=(0.45, 0.0, 0.0), u_seg=5, v_seg=3, name="m_peek_fg")
            _smooth_ellipsoid(builder, (0.0, -0.04, -0.105), (0.072, 0.056, 0.025), "paw_pink", pm, u_seg=5, v_seg=3, name="m_peek_pad")

    if with_cloud:
        cz = (-1.96 * r - 0.12 * r) if pk == "full" else (-0.98 * r)
        add_sculpted_cloud_v7(builder, loc=(0.0, 0.0, cz), rx=r * 1.45, ry=r * 1.15, rz=r * 0.42, lobes=6, role="cream", M=base_m)


# ---------------------------------------------------------------------------
# 2. SEAMLESS SILKY 1-PIECE STUDIO TOY CLOUDS (ZERO LUMPY GARLIC BULBS!)
# ---------------------------------------------------------------------------

def add_sculpted_cloud_v7(
    builder,
    loc=(0.0, 0.0, 0.0),
    rx=0.45,
    ry=0.35,
    rz=0.18,
    lobes=6,
    role="cream",
    rot=(0.0, 0.0, 0.0),
    M=None,
    flat_bottom=True,
    name="cloud_v7",
):
    """Build ONE silky-smooth fluffy 2-tier Sanrio/Pop-Mart cumulus toy cloud (ZERO lumpy garlic spheres!).
    Smooth multi-scallop pillowy rim + plump domed cumulus center crest (~240 tris, 100% organic_smooth)."""
    bm = bmesh.new()
    n_l = max(5, int(lobes))
    u_seg = n_l * 4  # 4 smooth quads per scallop lobe -> zero polygonal corners!
    if flat_bottom:
        prof = [
            (0.00, 0.00, 0.00, 0.00),
            (0.76, 0.00, 0.12, 0.00),
            (1.00, 0.22, 0.16, 0.04),
            (0.98, 0.50, 0.16, 0.12),
            (0.74, 0.72, 0.12, 0.14),
            (0.48, 0.88, 0.05, 0.08),
            (0.24, 1.02, 0.02, 0.03),
            (0.00, 1.08, 0.00, 0.00),
        ]
    else:
        prof = [
            (0.00, -0.34, 0.00, 0.00),
            (0.74, -0.20, 0.12, 0.00),
            (1.00,  0.14, 0.16, 0.04),
            (0.96,  0.48, 0.16, 0.12),
            (0.72,  0.72, 0.12, 0.14),
            (0.46,  0.88, 0.05, 0.08),
            (0.22,  1.02, 0.02, 0.03),
            (0.00,  1.08, 0.00, 0.00),
        ]

    rings = []
    for rf, zf, la, da in prof:
        if rf < 1e-5:
            rings.append([bm.verts.new((0.0, 0.0, zf * rz))])
        else:
            ring = []
            for i in range(u_seg):
                a = math.tau * i / float(u_seg)
                w1 = math.cos(n_l * a)
                w2 = math.cos(2 * n_l * a)
                # Rounded cumulus scallop lobes (flatter crests, soft tucked dimples — true kawaii cloud!)
                scallop = 1.0 + la * (0.72 * w1 - 0.22 * w2)
                z_bump = da * (0.5 + 0.5 * w1)
                ring.append(bm.verts.new((rx * rf * scallop * math.cos(a), ry * rf * scallop * math.sin(a), (zf + z_bump) * rz)))
            rings.append(ring)

    for k in range(len(rings) - 1):
        r0, r1 = rings[k], rings[k + 1]
        if len(r0) == 1:
            for i in range(u_seg):
                j = (i + 1) % u_seg
                bm.faces.new((r0[0], r1[j], r1[i]))
        elif len(r1) == 1:
            for i in range(u_seg):
                j = (i + 1) % u_seg
                bm.faces.new((r0[i], r0[j], r1[0]))
        else:
            for i in range(u_seg):
                j = (i + 1) % u_seg
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))

    world_m = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    return builder._add_bm(name, bm, role, world_m, uv_kind="cyl", organic_smooth=True)


# ---------------------------------------------------------------------------
# 3. CRISP MINIATURE STUDIO PROPS & 3D GIMMICKS (REPLACE CRUDE BLOCKS & 2D POSTER CLUTTER!)
# ---------------------------------------------------------------------------

def add_water_drop_v7(builder, loc, radius=0.044, height=0.115, role="water_clear", rot=(0.0, 0.0, 0.0), M=None):
    """Silky smooth lathed 3D teardrop water droplet (ZERO 6-sided diamond spinning top!)."""
    prof = [
        (0.000, 0.000),
        (0.55 * radius, 0.06 * height),
        (0.92 * radius, 0.20 * height),
        (1.00 * radius, 0.36 * height),
        (0.84 * radius, 0.54 * height),
        (0.56 * radius, 0.72 * height),
        (0.26 * radius, 0.88 * height),
        (0.06 * radius, 0.97 * height),
        (0.000, 1.00 * height),
    ]
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    return _lathe_z(builder, prof, 14, role, wm, name="drop_v7", organic=True)


def add_paint_jar_v7(builder, loc, radius=0.040, height=0.145, paint_role="caramel", label_role="cream", lid_role="walnut", M=None):
    """Detailed studio paint/craft jar: smooth 10-seg body, tapered glass shoulder, screw neck, rimmed lid & wrap label."""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    # Main jar body + tapered shoulder + neck
    jar_prof = [
        (0.00, 0.00),
        (radius * 0.92, 0.00),
        (radius, height * 0.06),
        (radius, height * 0.68),
        (radius * 0.86, height * 0.78),
        (radius * 0.68, height * 0.84),
        (radius * 0.68, height * 0.89),
        (0.00, height * 0.89),
    ]
    _lathe_z(builder, jar_prof, 10, paint_role, wm, name="jar_body", organic=True)
    # Crisp protruding paper wrap label band around middle of jar
    lbl_prof = [
        (radius * 1.03, height * 0.22),
        (radius * 1.045, height * 0.24),
        (radius * 1.045, height * 0.56),
        (radius * 1.03, height * 0.58),
    ]
    _lathe_z(builder, lbl_prof, 10, label_role, wm, name="jar_lbl", organic=True)
    # Rimmed screw-top lid with chamfered cap
    lid_prof = [
        (radius * 0.68, height * 0.84),
        (radius * 0.78, height * 0.85),
        (radius * 0.78, height * 0.97),
        (radius * 0.70, height * 1.00),
        (0.00, height * 1.00),
    ]
    _lathe_z(builder, lid_prof, 10, lid_role, wm, name="jar_lid", organic=False)


def add_parts_bin_v7(builder, loc, size=(0.155, 0.165, 0.095), bin_role="honey", trim_role="cocoa", M=None):
    """Detailed angled open-front workshop parts bin with brass label plate & nested hardware inside."""
    w, d, h = size
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    # Outer tapered bin walls + lowered scoop front lip
    bm = bmesh.new()
    hw, hd = w * 0.5, d * 0.5
    # Hollow open-top bin built cleanly with non-overlapping base & raised walls (ZERO Z-fighting!)
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.0, h * 0.26)) @ Matrix.Diagonal((w, d, h * 0.52, 1.0)))
    builder._add_bm("bin_base", bm, bin_role, wm)
    # Back & side raised walls seated cleanly ON TOP of base (z = 0.52*h .. 1.0*h, zero coplanar outer overlap!)
    bm2 = bmesh.new()
    side_t = 0.020
    back_t = d * 0.16
    bmesh.ops.create_cube(bm2, size=1.0, matrix=Matrix.Translation((0.0, hd - back_t * 0.5, h * 0.76)) @ Matrix.Diagonal((w - side_t * 2.0 - 0.002, back_t, h * 0.48, 1.0)))
    for sx in (-1.0, 1.0):
        bmesh.ops.create_cube(bm2, size=1.0, matrix=Matrix.Translation((sx * (hw - side_t * 0.5), 0.04 * d, h * 0.74)) @ Matrix.Diagonal((side_t, d * 0.86, h * 0.44, 1.0)))
    builder._add_bm("bin_walls", bm2, bin_role, wm)
    # Crisp dark trim rail + brass label holder stepped cleanly proud on front scoop (>= 5mm separation!)
    bm3 = bmesh.new()
    bmesh.ops.create_cube(bm3, size=1.0, matrix=Matrix.Translation((0.0, -hd - 0.005, h * 0.30)) @ Matrix.Diagonal((w * 0.62, 0.010, h * 0.28, 1.0)))
    builder._add_bm("bin_tag", bm3, trim_role, wm)
    bm4 = bmesh.new()
    bmesh.ops.create_cube(bm4, size=1.0, matrix=Matrix.Translation((0.0, -hd - 0.013, h * 0.30)) @ Matrix.Diagonal((w * 0.48, 0.006, h * 0.18, 1.0)))
    builder._add_bm("bin_card", bm4, "cream", wm)
    # 2 miniature brass hex nuts/bolts peeking inside the open bin!
    for nx in (-w * 0.20, w * 0.18):
        _lathe_z(builder, [(0.0, h * 0.58), (0.022, h * 0.58), (0.022, h * 0.82), (0.0, h * 0.82)], 6, "gold", wm @ Matrix.Translation((nx, 0.0, 0.0)), name="bin_nut", organic=False)


def add_tape_dispenser_v7(builder, loc, scale=1.0, body_role="walnut", tape_role="cream", core_role="gold", M=None):
    """Crisp sculpted curved waterfall desk tape dispenser with hollow tape reel & serrated metal cutter!"""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    # Sculpted curved waterfall dispenser cradle (clean stepped base + arched reel cheeks + front cutter bridge)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.0, 0.022)) @ Matrix.Diagonal((0.155, 0.072, 0.044, 1.0)))
    for sy in (-0.032, 0.032):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((-0.020, sy, 0.068)) @ Matrix.Diagonal((0.088, 0.014, 0.070, 1.0)))
    # Sloped front cutting platform
    bmesh.ops.create_cube(bm, size=1.0, matrix=_trs((0.056, 0.0, 0.040), (0.0, 0.32, 0.0), (0.054, 0.064, 0.032)))
    builder._add_bm("td_body", bm, body_role, wm, bevel=0.005, bevel_segs=1)
    # Smooth 12-seg hollow tape roll + golden center hub + dark metal serrated cutter blade!
    _smooth_torus(builder, (-0.020, 0.0, 0.082), 0.038, 0.016, 0.022, tape_role, wm, rot=(math.pi * 0.5, 0.0, 0.0), u_seg=12, v_seg=6, name="td_roll", organic=True)
    _lathe_z(builder, [(0.0, -0.026), (0.024, -0.026), (0.024, 0.026), (0.0, 0.026)], 10, core_role, wm @ _trs((-0.020, 0.0, 0.082), (math.pi * 0.5, 0.0, 0.0)), name="td_hub", organic=False)
    bm_cut = bmesh.new()
    bmesh.ops.create_cube(bm_cut, size=1.0, matrix=_trs((0.080, 0.0, 0.050), (0.0, 0.32, 0.0), (0.012, 0.056, 0.014)))
    builder._add_bm("td_blade", bm_cut, "metal_warm", wm)


def add_pencil_cup_v7(builder, loc, scale=1.0, cup_role="caramel", M=None):
    """Smooth rimmed desktop organizer cup with actual sharpened wooden pencils (cone tips + colored leads) & mini ruler!"""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    # Smooth tapered cup with non-overlapping golden lip rim seated cleanly on top!
    cup_prof = [
        (0.00, 0.00), (0.044, 0.00), (0.048, 0.01), (0.052, 0.118),
        (0.043, 0.118), (0.041, 0.02), (0.00, 0.02),
    ]
    _lathe_z(builder, cup_prof, 10, cup_role, wm, name="pcup", organic=True)
    _smooth_torus(builder, (0.0, 0.0, 0.123), 0.050, 0.009, 0.008, "gold", wm, u_seg=10, v_seg=5, name="pcup_rim", organic=True)
    # 3 sharpened pencils with cleanly segmented shaft / wooden cone / graphite tip (zero overlapping cones!)
    pencils = [
        ((-0.018, -0.008, 0.06), (0.14, -0.18, 0.0), "chestnut"),
        ((+0.014, -0.010, 0.06), (-0.10, +0.16, 0.2), "gold"),
        ((-0.002, +0.016, 0.06), (-0.18, -0.06, -0.2), "m_sky_blue"),
    ]
    for ploc, prot, prole in pencils:
        pm = wm @ _trs(ploc, prot)
        _lathe_z(builder, [(0.0, 0.0), (0.0075, 0.0), (0.0075, 0.124), (0.0, 0.124)], 6, prole, pm, name="pencil", organic=False)
        _lathe_z(builder, [(0.0075, 0.124), (0.0032, 0.152)], 6, "biscuit", pm, name="pcone", organic=False)
        _lathe_z(builder, [(0.0032, 0.152), (0.0, 0.168)], 5, "cocoa", pm, name="plead", organic=False)
    # Miniature wooden workshop ruler peeking out the back
    bm_r = bmesh.new()
    bmesh.ops.create_cube(bm_r, size=1.0, matrix=_trs((0.022, 0.014, 0.115), (-0.08, 0.14, 0.25), (0.026, 0.006, 0.165)))
    builder._add_bm("pruler", bm_r, "honey", wm)


def add_claw_hammer_v7(builder, loc, length=0.38, rot=(0.0, 0.0, 0.0), M=None):
    """Crisp sculpted carpenter claw hammer: contoured rubberized grip, flared collar, forged curved claw & beveled face."""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    # Contoured wooden shaft + dark rubberized lower grip
    shaft_prof = [
        (0.00, -length * 0.56), (0.021, -length * 0.54), (0.023, -length * 0.36),
        (0.019, -length * 0.18), (0.017, +length * 0.12), (0.019, +length * 0.34), (0.00, +length * 0.36),
    ]
    _lathe_z(builder, shaft_prof, 10, "honey", wm, name="ham_shaft", sx=1.12, sy=0.84, organic=True)
    grip_prof = [
        (0.00, -length * 0.57), (0.024, -length * 0.54), (0.026, -length * 0.36),
        (0.022, -length * 0.18), (0.00, -length * 0.17),
    ]
    _lathe_z(builder, grip_prof, 10, "cocoa", wm, name="ham_grip", sx=1.14, sy=0.88, organic=True)
    # Forged head center cheek + chamfered cylindrical strike face (-X) + graceful curved claw (+X)!
    head_z = length * 0.28
    bm_h = bmesh.new()
    bmesh.ops.create_cube(bm_h, size=1.0, matrix=Matrix.Translation((0.0, 0.0, head_z)) @ Matrix.Diagonal((0.068, 0.044, 0.048, 1.0)))
    builder._add_bm("ham_cheek", bm_h, "walnut", wm, bevel=0.006, bevel_segs=1)
    # Cylindrical neck + gleaming gold-brass strike face (-X)
    _lathe_z(
        builder,
        [(0.0, 0.0), (0.019, 0.0), (0.024, 0.036), (0.027, 0.044), (0.027, 0.066), (0.022, 0.072), (0.0, 0.072)],
        10, "gold", wm @ _trs((-0.028, 0.0, head_z), (0.0, -math.pi * 0.5, 0.0)), name="ham_face", organic=False
    )
    # Curved twin forged claw arcing cleanly downward (+X)!
    claw_pts = [
        (Vector((0.030, 0.0, head_z + 0.004)), 0.019),
        (Vector((0.068, 0.0, head_z + 0.002)), 0.016),
        (Vector((0.102, 0.0, head_z - 0.018)), 0.011),
        (Vector((0.120, 0.0, head_z - 0.044)), 0.005),
    ]
    _smooth_tube(builder, claw_pts, 8, "walnut", wm, oval=(1.0, 0.72), name="ham_claw", organic=True)


def add_box_wrench_v7(builder, loc, length=0.38, role="gold", rot=(0.0, 0.0, 0.0), M=None):
    """Crisp combination spanner: recessed I-beam shaft, smooth C-jaw open end (top) & chamfered ring box end (bottom)."""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    # Recessed I-beam shaft
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((0.036, 0.018, length * 0.66, 1.0)))
    builder._add_bm("wr_shaft", bm, role, wm, bevel=0.004, bevel_segs=1)
    bm_in = bmesh.new()
    bmesh.ops.create_cube(bm_in, size=1.0, matrix=Matrix.Translation((0.0, -0.006, 0.0)) @ Matrix.Diagonal((0.016, 0.010, length * 0.54, 1.0)))
    builder._add_bm("wr_groove", bm_in, "cocoa", wm)
    # Smooth C-jaw open end at top (+Z)
    jaw_pts = [
        (Vector((-0.038, 0.0, length * 0.44)), 0.014),
        (Vector((-0.044, 0.0, length * 0.36)), 0.018),
        (Vector((0.000,  0.0, length * 0.30)), 0.022),
        (Vector((+0.044, 0.0, length * 0.36)), 0.018),
        (Vector((+0.038, 0.0, length * 0.44)), 0.014),
    ]
    _smooth_tube(builder, jaw_pts, 8, role, wm, oval=(0.95, 0.65), name="wr_jaw", organic=True)
    # Smooth ring box-end at bottom (-Z)
    _smooth_torus(builder, (0.0, 0.0, -length * 0.37), 0.034, 0.014, 0.012, role, wm, rot=(math.pi * 0.5, 0.0, 0.0), u_seg=10, v_seg=5, name="wr_ring", organic=True)


def add_screwdriver_v7(builder, loc, length=0.34, handle_role="caramel", rot=(0.0, 0.0, 0.0), M=None):
    """Smooth ergonomically contoured screwdriver with rounded pommel, brass ferrule, chrome shaft & flat chisel blade!"""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    # Ergonomic rounded-pommel grip (+Z half)
    h_prof = [
        (0.00, 0.020), (0.016, 0.022), (0.026, 0.040), (0.022, 0.068),
        (0.028, 0.115), (0.027, 0.155), (0.018, 0.174), (0.00, 0.180),
    ]
    _lathe_z(builder, h_prof, 10, handle_role, wm, name="sd_hdl", organic=True)
    # Brass collar ferrule
    _lathe_z(builder, [(0.0, 0.004), (0.017, 0.004), (0.018, 0.024), (0.0, 0.024)], 8, "gold", wm, name="sd_ferr", organic=False)
    # Sleek chrome shaft + flared flat blade tip (-Z half)
    _lathe_z(builder, [(0.0, -0.145), (0.007, -0.145), (0.007, 0.006), (0.0, 0.006)], 8, "metal_warm", wm, name="sd_sh", organic=False)
    bm_tip = bmesh.new()
    bmesh.ops.create_cube(bm_tip, size=1.0, matrix=Matrix.Translation((0.0, 0.0, -0.156)) @ Matrix.Diagonal((0.018, 0.005, 0.026, 1.0)))
    builder._add_bm("sd_tip", bm_tip, "metal_warm", wm)


def add_toolbox_v7(builder, loc, size=(0.28, 0.17, 0.19), body_role="caramel", lid_role="honey", trim_role="cocoa", M=None):
    """Crisp domed-lid vintage workshop toolbox with corner bumpers, brass latch clasp & arched handle!"""
    w, d, h = size
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    # Lower box with crisp chamfered trim frame
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.0, h * 0.30)) @ Matrix.Diagonal((w, d, h * 0.60, 1.0)))
    builder._add_bm("tb_base", bm, body_role, wm, bevel=0.006, bevel_segs=1)
    # Domed hip-roof lid
    bm_l = bmesh.new()
    hw, hd = w * 0.51, d * 0.51
    z0, z1 = h * 0.59, h * 0.96
    b0 = [bm_l.verts.new((sx * hw, sy * hd, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t0 = [bm_l.verts.new((sx * hw * 0.78, sy * hd * 0.55, z1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm_l.faces.new(b0[::-1])
    bm_l.faces.new(t0)
    for i in range(4):
        j = (i + 1) % 4
        bm_l.faces.new((b0[i], b0[j], t0[j], t0[i]))
    builder._add_bm("tb_lid", bm_l, lid_role, wm)
    # Waist espresso gasket seam + brass front clasp buckle + arched carry handle!
    bm_s = bmesh.new()
    bmesh.ops.create_cube(bm_s, size=1.0, matrix=Matrix.Translation((0.0, 0.0, h * 0.59)) @ Matrix.Diagonal((w * 1.03, d * 1.03, 0.016, 1.0)))
    builder._add_bm("tb_seam", bm_s, trim_role, wm)
    bm_c = bmesh.new()
    bmesh.ops.create_cube(bm_c, size=1.0, matrix=Matrix.Translation((0.0, -d * 0.525, h * 0.58)) @ Matrix.Diagonal((0.044, 0.016, 0.048, 1.0)))
    builder._add_bm("tb_clasp", bm_c, "gold", wm, bevel=0.003, bevel_segs=1)
    # Smooth arched carry handle on top
    h_pts = [
        (Vector((-w * 0.24, 0.0, h * 0.94)), 0.012),
        (Vector((-w * 0.22, 0.0, h * 1.18)), 0.012),
        (Vector((+w * 0.22, 0.0, h * 1.18)), 0.012),
        (Vector((+w * 0.24, 0.0, h * 0.94)), 0.012),
    ]
    _smooth_tube(builder, h_pts, 8, trim_role, wm, name="tb_handle", organic=False)


def add_bench_vise_v7(builder, loc, scale=1.0, body_role="walnut", jaw_role="metal_warm", M=None):
    """Detailed cast workshop bench vise with swivel base, twin grooved jaws, anvil horn & T-bar screw handle!"""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    # Swivel circular base plate
    _lathe_z(builder, [(0.0, 0.0), (0.072, 0.0), (0.068, 0.018), (0.0, 0.018)], 10, "cocoa", wm, name="vise_base", organic=False)
    # Fixed & sliding cast jaws
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.025, 0.056)) @ Matrix.Diagonal((0.115, 0.064, 0.078, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, -0.048, 0.056)) @ Matrix.Diagonal((0.115, 0.036, 0.074, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, -0.012, 0.038)) @ Matrix.Diagonal((0.048, 0.088, 0.034, 1.0)))
    builder._add_bm("vise_body", bm, body_role, wm, bevel=0.004, bevel_segs=1)
    # Metallic jaw plates
    bm_j = bmesh.new()
    bmesh.ops.create_cube(bm_j, size=1.0, matrix=Matrix.Translation((0.0, -0.009, 0.084)) @ Matrix.Diagonal((0.118, 0.010, 0.026, 1.0)))
    bmesh.ops.create_cube(bm_j, size=1.0, matrix=Matrix.Translation((0.0, -0.028, 0.084)) @ Matrix.Diagonal((0.118, 0.010, 0.026, 1.0)))
    builder._add_bm("vise_jaws", bm_j, jaw_role, wm)
    # Brass lead-screw + T-bar spinner with end knobs!
    _lathe_z(builder, [(0.0, 0.0), (0.014, 0.0), (0.014, 0.044), (0.0, 0.044)], 8, "gold", wm @ _trs((0.0, -0.066, 0.044), (math.pi * 0.5, 0.0, 0.0)), name="vise_sc", organic=False)
    _lathe_z(builder, [(0.0, -0.078), (0.008, -0.078), (0.008, 0.078), (0.0, 0.078)], 6, "gold", wm @ _trs((0.0, -0.095, 0.044), (0.0, math.pi * 0.5, 0.0)), name="vise_tbar", organic=False)
    for sx in (-0.082, 0.082):
        _smooth_ellipsoid(builder, (sx, -0.095, 0.044), (0.014, 0.014, 0.014), "gold", wm, u_seg=6, v_seg=4, name="vise_kb")


def add_squeeze_bottle_v7(builder, loc, scale=1.0, body_role="cream", cap_role="gold", M=None):
    """Smooth lathed workshop glue/oil squeeze bottle with conical nozzle cap & label."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    b_prof = [(0.0, 0.0), (0.032, 0.0), (0.035, 0.015), (0.035, 0.092), (0.022, 0.112), (0.016, 0.116), (0.0, 0.116)]
    _lathe_z(builder, b_prof, 10, body_role, wm, name="glue_b", organic=True)
    n_prof = [(0.0, 0.112), (0.018, 0.114), (0.016, 0.128), (0.005, 0.165), (0.0, 0.168)]
    _lathe_z(builder, n_prof, 8, cap_role, wm, name="glue_n", organic=True)


def add_boba_cup_v7(builder, loc, scale=1.0, tea_role="boba_tea", lid_role="cream", straw_role="m_pink_in", M=None):
    """Adorable 3D café milk-tea boba cup with tapered body, boba pearls, domed lid & diagonal straw (for billie_shop!)."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    cup_prof = [(0.0, 0.0), (0.048, 0.0), (0.064, 0.145), (0.070, 0.152), (0.064, 0.158), (0.0, 0.158)]
    _lathe_z(builder, cup_prof, 14, tea_role, wm, name="boba_cup", organic=True)
    # Domed café lid + crisp rim
    lid_prof = [(0.068, 0.150), (0.062, 0.178), (0.044, 0.200), (0.020, 0.208), (0.0, 0.210)]
    _lathe_z(builder, lid_prof, 14, lid_role, wm, name="boba_lid", organic=True)
    # Cute dark boba pearls peeking around lower base rim (lean 6x3 smooth spheres)
    for k in range(5):
        a = math.tau * k / 5.0
        _smooth_ellipsoid(builder, (0.046 * math.cos(a), 0.046 * math.sin(a), 0.016), (0.014, 0.014, 0.013), "cocoa", wm, u_seg=6, v_seg=3, name="boba_p")
    # Diagonal wide boba straw!
    _lathe_z(builder, [(0.0, 0.14), (0.011, 0.14), (0.011, 0.275), (0.0, 0.275)], 8, straw_role, wm @ _trs((0.0, 0.0, 0.0), (0.0, 0.18, 0.0)), name="boba_str", organic=False)


def add_frosted_donut_v7(builder, loc, radius=0.078, glaze_role="berry_glaze", rot=(0.0, 0.0, 0.0), M=None):
    """Silky smooth 3D frosted bakery donut with glossy glaze & cute sprinkles!"""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    _smooth_torus(builder, (0.0, 0.0, 0.0), radius * 0.65, radius * 0.36, radius * 0.34, "honey", wm, u_seg=12, v_seg=7, name="donut_b", organic=True)
    _smooth_torus(builder, (0.0, 0.0, radius * 0.10), radius * 0.65, radius * 0.34, radius * 0.24, glaze_role, wm, u_seg=12, v_seg=6, name="donut_g", organic=True)
    for k, srole in enumerate(("white", "gold", "m_sky", "white", "gold")):
        a = math.tau * k / 5.0 + 0.3
        _smooth_ellipsoid(builder, (radius * 0.66 * math.cos(a), radius * 0.66 * math.sin(a), radius * 0.33), (radius * 0.10, radius * 0.045, radius * 0.035), srole, wm, rot=(0.0, 0.0, a + 0.6), u_seg=5, v_seg=3, name="dspr")


def add_gift_bag_v7(builder, loc, size=(0.14, 0.085, 0.175), bag_role="cream", handle_role="walnut", seal_role="gold", rot=(0.0, 0.0, 0.0), M=None):
    """Crisp boutique shopping gift bag with tapered top, ribbon rope handles & heart/star seal!"""
    w, d, h = size
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    bm = bmesh.new()
    hw, hd = w * 0.5, d * 0.5
    b0 = [bm.verts.new((sx * hw, sy * hd, 0.0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t0 = [bm.verts.new((sx * hw * 0.90, sy * hd * 0.72, h)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new(b0[::-1])
    bm.faces.new(t0)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b0[i], b0[j], t0[j], t0[i]))
    builder._add_bm("gbag", bm, bag_role, wm, bevel=0.004, bevel_segs=1)
    # Cuff collar stripe (cleanly proud around tapered top!) & twin curved rope handles
    bm_c = bmesh.new()
    bmesh.ops.create_cube(bm_c, size=1.0, matrix=Matrix.Translation((0.0, 0.0, h * 0.91)) @ Matrix.Diagonal((w * 0.99, d * 0.88, h * 0.15, 1.0)))
    builder._add_bm("gbag_top", bm_c, "caramel", wm)
    for sy in (-d * 0.32, d * 0.32):
        h_pts = [
            (Vector((-w * 0.22, sy, h * 0.94)), 0.008),
            (Vector((-w * 0.18, sy, h * 1.24)), 0.008),
            (Vector((+w * 0.18, sy, h * 1.24)), 0.008),
            (Vector((+w * 0.22, sy, h * 0.94)), 0.008),
        ]
        _smooth_tube(builder, h_pts, 8, handle_role, wm, name="gbag_hdl", organic=True)
    _add_heart_3d(builder, (0.0, -d * 0.51, h * 0.48), w * 0.24, 0.016, seal_role, wm, name="gbag_seal")


def add_detergent_jug_v7(builder, loc, scale=1.0, body_role="m_sky", cap_role="cocoa", M=None):
    """Smooth contoured laundry detergent bottle with integrated curved handle, ribbed measuring cap & curved wrap label!"""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc) @ Matrix.Diagonal((s, s, s, 1.0))
    # Smooth sculpted oval bottle body
    j_prof = [
        (0.00, 0.00), (0.078, 0.00), (0.088, 0.025), (0.090, 0.145),
        (0.072, 0.185), (0.038, 0.210), (0.032, 0.222), (0.00, 0.222),
    ]
    _lathe_z(builder, j_prof, 12, body_role, wm, name="det_body", sx=1.05, sy=0.72, organic=True)
    # Curved wrap label cleanly proud around middle (>= 5mm clearance)
    l_prof = [(0.095, 0.060), (0.097, 0.068), (0.097, 0.132), (0.095, 0.140)]
    _lathe_z(builder, l_prof, 12, "cream", wm, name="det_lbl", sx=1.05, sy=0.72, organic=True)
    # Smooth ergonomic curved handle loop on -X side!
    hdl_pts = [
        (Vector((-0.068, 0.0, 0.172)), 0.015),
        (Vector((-0.118, 0.0, 0.156)), 0.015),
        (Vector((-0.122, 0.0, 0.082)), 0.015),
        (Vector((-0.082, 0.0, 0.056)), 0.015),
    ]
    _smooth_tube(builder, hdl_pts, 8, body_role, wm, name="det_hdl", organic=True)
    # Measuring spout cap
    _lathe_z(builder, [(0.0, 0.212), (0.038, 0.212), (0.038, 0.252), (0.032, 0.258), (0.0, 0.258)], 10, cap_role, wm, name="det_cap", organic=False)


def add_traffic_cone_v7(builder, loc, height=0.28, cone_role="orange", M=None):
    """Crisp smooth lathed miniature road traffic cone with double cream reflective stripes & chamfered square base."""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.0, 0.014)) @ Matrix.Diagonal((height * 0.62, height * 0.62, 0.028, 1.0)))
    builder._add_bm("cone_b", bm, "cocoa", wm, bevel=0.005, bevel_segs=1)
    _lathe_z(builder, [(0.0, 0.025), (height * 0.26, 0.025), (height * 0.06, height), (0.0, height)], 14, cone_role, wm, name="cone_t", organic=True)
    # Match 14-seg angular phase & expand proudly >= 5mm outside cone wall (zero chord Z-fighting!)
    for z0, z1, r0, r1 in ((0.34, 0.50, 0.228, 0.194), (0.60, 0.74, 0.172, 0.144)):
        _lathe_z(builder, [(height * r0, height * z0), (height * r1, height * z1)], 14, "cream", wm, name="cone_s", organic=True)


def add_pipe_wrench_v7(builder, loc, length=0.42, rot=(0.0, 0.0, 0.0), M=None):
    """Crisp heavy plumber pipe wrench leaning cleanly beside billie_waterpipe!"""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    # Sculpted tapered red-chestnut wrench handle
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.0, 0.0, -length * 0.06)) @ Matrix.Diagonal((0.036, 0.020, length * 0.78, 1.0)))
    builder._add_bm("pw_hdl", bm, "chestnut", wm, bevel=0.004, bevel_segs=1)
    # Forged upper & lower jaws (>= 5mm thicker than handle -> zero Z-fighting!) + brass knurled adjuster nut!
    bm_j = bmesh.new()
    bmesh.ops.create_cube(bm_j, size=1.0, matrix=Matrix.Translation((0.026, 0.0, length * 0.34)) @ Matrix.Diagonal((0.095, 0.032, 0.034, 1.0)))
    bmesh.ops.create_cube(bm_j, size=1.0, matrix=Matrix.Translation((0.024, 0.0, length * 0.25)) @ Matrix.Diagonal((0.082, 0.030, 0.028, 1.0)))
    builder._add_bm("pw_jaws", bm_j, "metal_warm", wm, bevel=0.004, bevel_segs=1)
    _lathe_z(builder, [(0.0, length * 0.18), (0.022, length * 0.18), (0.022, length * 0.23), (0.0, length * 0.23)], 10, "gold", wm @ Matrix.Translation((0.0, 0.0, 0.0)), name="pw_nut", organic=False)


def add_treasure_hoard_v7(builder, loc, radius=0.28, M=None):
    """Overflowing mound of crisp bevel-rimmed gold coins + sparkling faceted jewels + miniature wrapped gift box!"""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    # Soft golden coin mound base
    _smooth_ellipsoid(builder, (0.0, 0.0, 0.01), (radius, radius * 0.72, 0.075), "gold_deep", wm, u_seg=14, v_seg=6, name="hoard_mound")
    # 7 gleaming crisp gold coins scattered at natural angles on the mound
    coins = [
        ((-0.14, -0.06, 0.065), (0.28, 0.22, 0.0)),
        ((-0.04, -0.08, 0.082), (-0.22, 0.15, 0.4)),
        ((+0.09, -0.05, 0.076), (0.30, -0.24, 0.2)),
        ((+0.16, +0.02, 0.058), (-0.18, -0.32, 0.5)),
        ((-0.10, +0.05, 0.074), (0.16, 0.34, -0.3)),
        ((+0.02, +0.04, 0.088), (-0.12, -0.18, 0.6)),
        ((+0.01, -0.01, 0.094), (0.08, 0.10, 0.1)),
    ]
    for cloc, crot in coins:
        _lathe_z(builder, [(0.0, -0.008), (0.044, -0.008), (0.046, 0.0), (0.044, 0.008), (0.0, 0.008)], 12, "gold", wm @ _trs(cloc, crot), name="h_coin", organic=False)
    # 3 sparkling faceted jewel crystals (Pink / Skyblue / Gold — matching the Billie Houses!)
    for (jloc, jrot, jrole) in (
        ((-0.09, -0.02, 0.105), (0.25, -0.32, 0.2), "m_pink_in"),
        ((+0.11, -0.01, 0.102), (-0.20, 0.28, -0.3), "water_clear"),
        ((+0.00, +0.06, 0.110), (0.15, 0.12, 0.4), "glow_gold"),
    ):
        _lathe_z(builder, [(0.0, -0.036), (0.036, 0.004), (0.022, 0.032), (0.0, 0.040)], 6, jrole, wm @ _trs(jloc, jrot), name="h_gem", organic=False)


# ---------------------------------------------------------------------------
# 4. V8 SIGN-FREE 3D ARCHITECTURAL ORNAMENTS & BOUTIQUE GIMMICKS
# ---------------------------------------------------------------------------

def add_3d_cafe_awning_v8(builder, loc, width=0.92, depth=0.34, drop=0.14, scallops=6, role_a="caramel", role_b="cream", trim_role="cocoa", M=None):
    """Lush 3D striped sloped café awning canopy with rounded scalloped valance domes & dark wood header bar."""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    n = max(4, int(scallops))
    sw = float(width) / float(n)
    # Dark cocoa top mounting cornice bar
    bm_top = bmesh.new()
    bmesh.ops.create_cube(bm_top, size=1.0, matrix=Matrix.Translation((0.0, depth * 0.35, drop * 0.56)) @ Matrix.Diagonal((width + 0.04, 0.065, 0.052, 1.0)))
    builder._add_bm("awn_top", bm_top, trim_role, wm)
    # Alternating caramel & cream sloped awning ribs + scalloped rounded front valance lobes!
    for i in range(n):
        rx = -width * 0.5 + (i + 0.5) * sw
        role = role_a if (i % 2 == 0) else role_b
        bm_r = bmesh.new()
        bmesh.ops.create_cube(bm_r, size=1.0, matrix=_trs((rx, 0.0, drop * 0.25), (0.34, 0.0, 0.0), (sw * 0.99, depth, 0.055)))
        builder._add_bm("awn_rib", bm_r, role, wm, bevel=0.006, bevel_segs=1)
        # Plump rounded front valance scallop hanging smoothly down at -Y edge
        _smooth_ellipsoid(builder, (rx, -depth * 0.48, -drop * 0.05), (sw * 0.49, 0.036, drop * 0.44), role, wm, u_seg=10, v_seg=5, name="awn_sc")
    # Crisp golden piping bead tucked cleanly inside the valance scallops (zero poking ends!)
    bm_g = bmesh.new()
    bmesh.ops.create_cube(bm_g, size=1.0, matrix=Matrix.Translation((0.0, -depth * 0.49, drop * 0.14)) @ Matrix.Diagonal((width - sw * 0.35, 0.020, 0.016, 1.0)))
    builder._add_bm("awn_gold", bm_g, "gold", wm)


def add_3d_crown_medallion_v8(builder, loc, radius=0.16, icon="star", outer_role="cocoa", inner_role="gold", bg_role="cream", rot=(0.0, 0.0, 0.0), M=None):
    """Sculpted 3D beveled circular crest medallion with crisp raised 3D icon (ZERO 2D stickers, >= 6mm layer gaps!)."""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    r = float(radius)
    # Stepped beveled outer cocoa frame (open rear tucked cleanly against wall -> ZERO rear-cap Z-fighting!) + golden bezel + cream dish
    _lathe_z(builder, [(r, -0.008), (r, 0.016), (r * 0.88, 0.024), (0.0, 0.024)], 18, outer_role, wm @ _trs((0.0, 0.0, 0.0), (math.pi * 0.5, 0.0, 0.0)), name="med_o", organic=False)
    _smooth_torus(builder, (0.0, -0.027, 0.0), r * 0.84, r * 0.085, r * 0.085, inner_role, wm, rot=(math.pi * 0.5, 0.0, 0.0), u_seg=18, v_seg=5, name="med_r", organic=True)
    _lathe_z(builder, [(r * 0.80, 0.015), (r * 0.80, 0.030), (0.0, 0.030)], 16, bg_role, wm @ _trs((0.0, 0.0, 0.0), (math.pi * 0.5, 0.0, 0.0)), name="med_bg", organic=False)

    ic = str(icon).lower()
    if ic == "star":
        _add_star5_3d(builder, (0.0, -0.038, 0.0), r * 0.56, r * 0.18, "gold", wm, name="med_star")
    elif ic == "heart":
        _add_heart_3d(builder, (0.0, -0.038, -r * 0.04), r * 0.52, r * 0.16, "m_pink_in", wm, name="med_heart", segs=14)
    elif ic == "paw":
        _smooth_ellipsoid(builder, (0.0, -0.038, -r * 0.14), (r * 0.30, r * 0.11, r * 0.24), "walnut", wm, u_seg=10, v_seg=4, name="mp_c")
        for px, pz in ((-0.32, 0.20), (-0.11, 0.34), (+0.11, 0.34), (+0.32, 0.20)):
            _smooth_ellipsoid(builder, (px * r, -0.038, pz * r), (r * 0.12, r * 0.10, r * 0.14), "gold", wm, u_seg=8, v_seg=4, name="mp_t")
    elif ic == "coin":
        _smooth_torus(builder, (0.0, -0.038, 0.0), r * 0.44, r * 0.11, r * 0.08, "gold", wm, rot=(math.pi * 0.5, 0.0, 0.0), u_seg=14, v_seg=5, name="mc_r", organic=True)
        _add_star5_3d(builder, (0.0, -0.042, 0.0), r * 0.34, r * 0.12, "glow_gold", wm, name="mc_s")
    elif ic == "crown":
        bm_cr = bmesh.new()
        bmesh.ops.create_cube(bm_cr, size=1.0, matrix=Matrix.Translation((0.0, -0.038, -r * 0.18)) @ Matrix.Diagonal((r * 0.96, r * 0.18, r * 0.20, 1.0)))
        for cx, ch in ((-0.36, 0.38), (0.0, 0.52), (+0.36, 0.38)):
            # Spikes sit cleanly ON TOP of crown band (z = -0.08*r .. +) with stepped depth (zero coplanar overlap!)
            bmesh.ops.create_cube(bm_cr, size=1.0, matrix=Matrix.Translation((cx * r, -0.038, (-0.08 + ch * 0.5) * r)) @ Matrix.Diagonal((r * 0.20, r * 0.14, ch * r, 1.0)))
        builder._add_bm("med_cr", bm_cr, "gold", wm, bevel=0.003, bevel_segs=1)
        for cx, cz in ((-0.36, 0.34), (0.0, 0.48), (+0.36, 0.34)):
            _smooth_ellipsoid(builder, (cx * r, -0.044, cz * r), (r * 0.10, r * 0.08, r * 0.10), "glow_gold", wm, u_seg=6, v_seg=4, name="mcr_j")
    elif ic == "p":
        # Crisp sculpted 3D Golden Letter 'P' for billie_parking!
        bm_p = bmesh.new()
        bmesh.ops.create_cube(bm_p, size=1.0, matrix=Matrix.Translation((-r * 0.22, -0.040, 0.0)) @ Matrix.Diagonal((r * 0.22, r * 0.16, r * 1.05, 1.0)))
        builder._add_bm("med_pstem", bm_p, "gold", wm, bevel=0.006, bevel_segs=1)
        p_pts = [
            (Vector((-r * 0.20, -0.042, +r * 0.42)), r * 0.115),
            (Vector((+r * 0.14, -0.042, +r * 0.42)), r * 0.115),
            (Vector((+r * 0.32, -0.042, +r * 0.22)), r * 0.115),
            (Vector((+r * 0.14, -0.042, +r * 0.02)), r * 0.115),
            (Vector((-r * 0.20, -0.042, +r * 0.02)), r * 0.115),
        ]
        _smooth_tube(builder, p_pts, 8, "gold", wm, name="med_pbowl", organic=True)
    elif ic == "gear":
        _smooth_torus(builder, (0.0, -0.039, 0.0), r * 0.40, r * 0.13, r * 0.10, "gold", wm, rot=(math.pi * 0.5, 0.0, 0.0), u_seg=14, v_seg=5, name="mg_r", organic=True)
        for k in range(8):
            a = math.tau * k / 8.0
            bm_t = bmesh.new()
            bmesh.ops.create_cube(bm_t, size=1.0, matrix=_trs((r * 0.54 * math.cos(a), -0.039, r * 0.54 * math.sin(a)), (0.0, -a, 0.0), (r * 0.18, r * 0.14, r * 0.16)))
            builder._add_bm("mg_t", bm_t, "gold", wm)
        _smooth_ellipsoid(builder, (0.0, -0.044, 0.0), (r * 0.16, r * 0.09, r * 0.16), "cocoa", wm, u_seg=8, v_seg=4, name="mg_h")


def add_3d_gooseneck_lamp_v8(builder, loc, scale=1.0, rot=(0.0, 0.0, 0.0), M=None):
    """Curved vintage brass workshop gooseneck lamp with warm glowing cream dome shade (for billie_crafting!)."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot, (s, s, s))
    _lathe_z(builder, [(0.0, 0.0), (0.055, 0.0), (0.048, 0.026), (0.0, 0.026)], 10, "cocoa", wm, name="lamp_b", organic=False)
    neck = [
        (Vector((0.0, 0.0, 0.02)), 0.015),
        (Vector((0.0, 0.02, 0.22)), 0.014),
        (Vector((0.0, -0.09, 0.34)), 0.014),
        (Vector((0.0, -0.22, 0.27)), 0.014),
    ]
    _smooth_tube(builder, neck, 8, "gold", wm, name="lamp_neck", organic=True)
    sh_m = wm @ _trs((0.0, -0.24, 0.24), (0.42, 0.0, 0.0))
    _lathe_z(builder, [(0.0, 0.05), (0.035, 0.04), (0.095, -0.04), (0.112, -0.065), (0.098, -0.072), (0.0, -0.02)], 12, "walnut", sh_m, name="lamp_sh", organic=True)
    _smooth_ellipsoid(builder, (0.0, 0.0, -0.058), (0.056, 0.056, 0.044), "glow_cream", sh_m, u_seg=8, v_seg=4, name="lamp_bulb")


def add_3d_coiled_hose_v8(builder, loc, radius=0.14, role="m_sky", M=None):
    """Cute 3-loop coiled skyblue garden/pressure hose with brass nozzle (replaces WATER flat sign on waterpipe!)."""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    r = float(radius)
    for k, (rz_off, rad_k) in enumerate(((0.022, r), (0.058, r * 0.94), (0.094, r * 0.88))):
        _smooth_torus(builder, (0.0, 0.0, rz_off), rad_k, 0.022, 0.022, role, wm, u_seg=14, v_seg=5, name="hose_lp", organic=True)
    # Brass spray nozzle perched neatly on top coil!
    _lathe_z(builder, [(0.0, 0.0), (0.024, 0.0), (0.024, 0.055), (0.014, 0.095), (0.0, 0.098)], 10, "gold", wm @ _trs((r * 0.72, -r * 0.45, 0.115), (0.45, 0.55, 0.25)), name="hose_noz", organic=False)


def add_3d_croissant_v8(builder, loc, scale=1.0, rot=(0.0, 0.0, 0.0), M=None):
    """Adorable sculpted golden flaky crescent croissant (for billie_shop 3D bakery showcase!)."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot, (s, s, s))
    pts = [
        (Vector((-0.072, -0.026, 0.020)), 0.018),
        (Vector((-0.044, +0.012, 0.032)), 0.030),
        (Vector((0.000,  +0.026, 0.038)), 0.036),
        (Vector((+0.044, +0.012, 0.032)), 0.030),
        (Vector((+0.072, -0.026, 0.020)), 0.018),
    ]
    _smooth_tube(builder, pts, 8, "honey", wm, oval=(1.0, 0.86), name="crois", organic=True)
    for cx in (-0.032, 0.0, +0.032):
        _smooth_torus(builder, (cx, 0.015, 0.034), 0.032, 0.006, 0.006, "caramel", wm, rot=(0.0, math.pi * 0.5, cx * 4.0), u_seg=8, v_seg=4, name="crois_r", organic=True)


# ---------------------------------------------------------------------------
# V9 Bespoke 3D Diorama Decorations (Replaces generic round medallion boxes!)
# ---------------------------------------------------------------------------


def add_golden_piggy_bank_v9(builder, loc, scale=1.0, rot=(0.0, 0.0, 0.0), M=None):
    """Adorable chubby 3D Golden Piggy Bank with snout, ears, eyes, coin slot & dropping gold coin (for billie_atm!)."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot, (s, s, s))
    # 1. Plump silky butter-gold piggy body (faces -Y toward player, slight cheerful angle!)
    _smooth_ellipsoid(builder, (0.0, 0.0, 0.068), (0.088, 0.076, 0.068), "gold", wm, u_seg=12, v_seg=6, name="pig_body")
    # 2. 4 stubby golden legs seated cleanly on shelf z=0
    for lx in (-0.044, 0.044):
        for ly in (-0.034, 0.034):
            _lathe_z(builder, [(0.0, 0.0), (0.018, 0.0), (0.020, 0.032), (0.0, 0.032)], 8, "honey", wm @ Matrix.Translation((lx, ly, 0.0)), name="pig_leg", organic=True)
    # 3. Cute oval blush-pink snout + 2 crisp espresso nostrils!
    _smooth_ellipsoid(builder, (0.0, -0.072, 0.064), (0.034, 0.018, 0.024), "m_pink_in", wm, u_seg=10, v_seg=5, name="pig_snout")
    for nx in (-0.012, 0.012):
        _smooth_ellipsoid(builder, (nx, -0.089, 0.065), (0.0065, 0.005, 0.0085), "espresso", wm, u_seg=6, v_seg=3, name="pig_nos")
    # 4. 2 glossy dark espresso eyes + rosy cheeks!
    for ex in (-0.036, 0.036):
        _smooth_ellipsoid(builder, (ex, -0.066, 0.092), (0.009, 0.008, 0.010), "espresso", wm, u_seg=6, v_seg=3, name="pig_eye")
        _smooth_ellipsoid(builder, (ex * 1.38, -0.062, 0.070), (0.013, 0.007, 0.009), "blush", wm, u_seg=6, v_seg=3, name="pig_chk")
    # 5. 2 perky floppy piggy ears perched on crown
    for sx in (-1.0, 1.0):
        em = wm @ _trs((sx * 0.048, -0.022, 0.126), (0.18, sx * -0.45, sx * 0.25))
        _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.024, 0.012, 0.028), "gold", em, u_seg=8, v_seg=4, name="pig_ear")
        _smooth_ellipsoid(builder, (0.0, -0.007, -0.002), (0.014, 0.009, 0.018), "m_pink_in", em, u_seg=6, v_seg=3, name="pig_eari")
    # 6. Dark coin slot collar on back + gleaming golden coin half-dropped into slot!
    bm_sl = bmesh.new()
    bmesh.ops.create_cube(bm_sl, size=1.0, matrix=Matrix.Translation((0.0, 0.008, 0.133)) @ Matrix.Diagonal((0.046, 0.012, 0.010, 1.0)))
    builder._add_bm("pig_slot", bm_sl, "espresso", wm)
    _lathe_z(builder, [(0.0, -0.006), (0.028, -0.006), (0.028, 0.006), (0.0, 0.006)], 12, "glow_gold", wm @ _trs((0.0, 0.008, 0.156), (math.pi * 0.5, 0.0, 0.0)), name="pig_coin", organic=False)


def add_mini_succulent_pot_v9(builder, loc, scale=1.0, pot_role="caramel", plant_role="sage_warm", M=None):
    """Cute miniature café workshop potted succulent with tiny pink blossom (for billie_crafting open shelf!)."""
    s = float(scale)
    wm = (M or Matrix.Identity(4)) @ _trs(loc, (0.0, 0.0, 0.0), (s, s, s))
    # Tapered terracotta pot + crisp cream top collar rim + dark soil bed
    _lathe_z(builder, [(0.0, 0.0), (0.036, 0.0), (0.048, 0.068), (0.040, 0.068), (0.0, 0.062)], 10, pot_role, wm, name="suc_pot", organic=False)
    _smooth_torus(builder, (0.0, 0.0, 0.072), 0.048, 0.009, 0.008, "cream", wm, u_seg=10, v_seg=5, name="suc_rim", organic=True)
    # 5 plump pastel sage succulent petals + central rosette bud + tiny pink flower on top!
    for k in range(5):
        a = math.tau * k / 5.0
        lm = wm @ _trs((0.024 * math.cos(a), 0.024 * math.sin(a), 0.090), (0.42 * math.sin(a), -0.42 * math.cos(a), a))
        _smooth_ellipsoid(builder, (0.0, 0.0, 0.0), (0.024, 0.018, 0.028), plant_role, lm, u_seg=6, v_seg=4, name="suc_leaf")
    _smooth_ellipsoid(builder, (0.0, 0.0, 0.112), (0.020, 0.020, 0.024), plant_role, wm, u_seg=6, v_seg=4, name="suc_top")
    _smooth_ellipsoid(builder, (0.0, 0.0, 0.136), (0.013, 0.013, 0.011), "m_pink_in", wm, u_seg=6, v_seg=3, name="suc_flw")


def add_rolled_scroll_v9(builder, loc, length=0.14, radius=0.022, paper_role="cream", tie_role="gold", rot=(0.0, 0.0, 0.0), M=None):
    """Crisp rolled workshop blueprint/fabric scroll with proud golden ribbon tie (ZERO Z-fighting!)."""
    wm = (M or Matrix.Identity(4)) @ _trs(loc, rot)
    hl = float(length) * 0.5
    r = float(radius)
    # Rolled paper cylinder along X axis
    _lathe_z(builder, [(0.0, -hl), (r, -hl), (r, hl), (0.0, hl)], 10, paper_role, wm @ _trs((0.0, 0.0, 0.0), (0.0, math.pi * 0.5, 0.0)), name="scr_p", organic=True)
    # Dark inner spiral ends proudly proud +5mm on ends? No, narrower radius +3mm proud end dots!
    for sx in (-1.0, 1.0):
        _lathe_z(builder, [(0.0, sx * hl), (r * 0.45, sx * hl), (r * 0.45, sx * (hl + 0.005)), (0.0, sx * (hl + 0.005))], 8, "walnut", wm @ _trs((0.0, 0.0, 0.0), (0.0, math.pi * 0.5, 0.0)), name="scr_in", organic=False)
    # Proud golden ribbon tie band (+5mm radial clearance)
    _lathe_z(builder, [(r + 0.005, -0.012), (r + 0.005, 0.012)], 10, tie_role, wm @ _trs((0.0, 0.0, 0.0), (0.0, math.pi * 0.5, 0.0)), name="scr_tie", organic=False)


def add_analog_voltmeter_v9(builder, loc, width=0.16, height=0.11, M=None):
    """Crisp 3D industrial-cute analog voltmeter window with curved scale bar & angled red needle (for billie_powerbox!)."""
    wm = (M or Matrix.Identity(4)) @ Matrix.Translation(loc)
    w, h = float(width), float(height)
    # Stepped espresso bezel -> gold trim -> cream meter face (>= 6mm per step!)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((w, 0.022, h, 1.0)))
    builder._add_bm("vm_out", bm, "cocoa", wm, bevel=0.004, bevel_segs=1)
    bm2 = bmesh.new()
    bmesh.ops.create_cube(bm2, size=1.0, matrix=Matrix.Translation((0.0, -0.008, 0.0)) @ Matrix.Diagonal((w - 0.022, 0.018, h - 0.022, 1.0)))
    builder._add_bm("vm_gld", bm2, "gold", wm)
    bm3 = bmesh.new()
    bmesh.ops.create_cube(bm3, size=1.0, matrix=Matrix.Translation((0.0, -0.015, 0.0)) @ Matrix.Diagonal((w - 0.036, 0.016, h - 0.036, 1.0)))
    builder._add_bm("vm_bg", bm3, "cream", wm)
    # 5 stepped radial scale tick blocks arching across top of voltmeter dial (+6mm proud of cream!)
    for idx, (deg, trole) in enumerate(((-52.0, "sage_warm"), (-26.0, "sage_warm"), (0.0, "gold"), (26.0, "amber"), (52.0, "chestnut"))):
        a = math.radians(deg)
        tx = math.sin(a) * (w * 0.30)
        tz = -h * 0.24 + math.cos(a) * (h * 0.44)
        bm_t = bmesh.new()
        bmesh.ops.create_cube(bm_t, size=1.0, matrix=_trs((tx, -0.026, tz), (0.0, -a, 0.0), (0.016, 0.008, 0.010)))
        builder._add_bm("vm_tk", bm_t, trole, wm)
    # Angled crisp 3D red-chestnut voltmeter pointer needle + espresso pivot hub (+7mm proud of ticks!)
    bm_n = bmesh.new()
    bmesh.ops.create_cube(bm_n, size=1.0, matrix=_trs((0.012, -0.032, 0.002), (0.0, -0.42, 0.0), (0.008, 0.008, h * 0.56)))
    builder._add_bm("vm_ndl", bm_n, "chestnut", wm)
    _lathe_z(builder, [(0.0, -0.008), (0.016, -0.008), (0.016, 0.008), (0.0, 0.008)], 8, "espresso", wm @ _trs((0.0, -0.034, -h * 0.24), (math.pi * 0.5, 0.0, 0.0)), name="vm_hub", organic=False)
