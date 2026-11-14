"""weapon-forge: Direct GTA V / FiveM RSC7 .ydr, .ytd & .dds compiler + Sollumz property tagger.

Works inside Blender 4.2+ using bundled Python + numpy (no Sollumz or CodeWalker required to export .ydr/.ytd,
and also tags .blend files with full Sollumz 2.6+ Drawable / Bound / Shader properties for GUI editing).

Usage from CLI:
  blender -b --factory-startup -P export_ydr.py -- --blend model.blend --out stream_dir [--hi]
"""

import argparse
import math
import os
import struct
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


def joaat(text):
    h = 0
    for c in text.lower().encode("ascii", "ignore"):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def enhance_baked_image(rgba, bloom_strength=0.42, contrast=1.08):
    """Add soft emissive bloom halo around bright/glowing texels and boost micro-contrast for emissive.sps."""
    arr = rgba.astype(np.float32)
    rgb = arr[..., :3]
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    sat = rgb.max(axis=-1) - rgb.min(axis=-1)
    bright_mask = np.clip((lum - 0.52) * 2.2 + (sat * lum - 0.28) * 1.8, 0.0, 1.0)[..., None]
    emit = rgb * bright_mask

    def box_blur_2d(img, radius):
        if radius < 1:
            return img
        k = 2 * radius + 1
        pad_y = np.pad(img, ((radius, radius), (0, 0), (0, 0)), mode="edge")
        cs_y = np.cumsum( np.pad(pad_y, ((1, 0), (0, 0), (0, 0)), mode="constant"), axis=0 )
        blur_y = (cs_y[k:] - cs_y[:-k]) / float(k)
        pad_x = np.pad(blur_y, ((0, 0), (radius, radius), (0, 0)), mode="edge")
        cs_x = np.cumsum( np.pad(pad_x, ((0, 0), (1, 0), (0, 0)), mode="constant"), axis=1 )
        return (cs_x[:, k:] - cs_x[:, :-k]) / float(k)

    h = arr.shape[0]
    r1 = max(2, h // 128)
    r2 = max(6, h // 36)
    bloom = box_blur_2d(box_blur_2d(emit, r1), r1) * 0.65 + box_blur_2d(box_blur_2d(emit, r2), r2) * 0.55

    # Local unsharp mask for crisp bevel/engraving edges
    detail_blur = box_blur_2d(rgb, max(1, h // 512))
    sharpened = rgb + (rgb - detail_blur) * 0.35
    mid = (sharpened - 0.5) * contrast + 0.5
    combined = np.clip(mid + bloom * bloom_strength, 0.0, 1.0)
    out = np.empty_like(arr)
    out[..., :3] = combined
    out[..., 3] = arr[..., 3]
    return out


def compress_dxt5_block_grid(rgba_u8):
    """Vectorized numpy DXT5 (BC3) compressor for an (H, W, 4) uint8 RGBA array."""
    h, w, _ = rgba_u8.shape
    pad_h = max(4, (h + 3) & ~3)
    pad_w = max(4, (w + 3) & ~3)
    if pad_h != h or pad_w != w:
        padded = np.zeros((pad_h, pad_w, 4), dtype=np.uint8)
        padded[:h, :w] = rgba_u8
        for y in range(h, pad_h):
            padded[y, :w] = rgba_u8[h - 1, :w]
        for x in range(w, pad_w):
            padded[:, x] = padded[:, w - 1]
        rgba_u8 = padded
        h, w = pad_h, pad_w

    blocks = rgba_u8.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    n = blocks.shape[0]
    out = np.zeros((n, 16), dtype=np.uint8)

    # --- Alpha block (8 bytes) ---
    alpha = blocks[:, :, 3].astype(np.int32)
    a_max = alpha.max(axis=1)
    a_min = alpha.min(axis=1)
    out[:, 0] = a_max.astype(np.uint8)
    out[:, 1] = a_min.astype(np.uint8)
    span_a = np.maximum(1, a_max - a_min)[:, None]
    # 8-alpha interpolation: 0=max, 1=min, 2..7 = (6*max+1*min)/7 .. (1*max+6*min)/7
    pos_a = np.clip(np.round((a_max[:, None] - alpha) * 7.0 / span_a).astype(np.int32), 0, 7)
    lut_a = np.array([0, 2, 3, 4, 5, 6, 7, 1], dtype=np.uint64)
    codes_a = lut_a[pos_a]
    equal_mask = (a_max == a_min)
    codes_a[equal_mask] = 0
    shifts_a = (np.arange(16, dtype=np.uint64) * 3)[None, :]
    packed_a = np.bitwise_or.reduce(codes_a << shifts_a, axis=1)
    for b in range(6):
        out[:, 2 + b] = ((packed_a >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)

    # --- Color block (8 bytes, DXT1 4-color mode c0 > c1) ---
    rgb = blocks[:, :, :3].astype(np.float32)
    c_min = rgb.min(axis=1)
    c_max = rgb.max(axis=1)

    r0 = np.clip(np.round(c_max[:, 0] * 31.0 / 255.0), 0, 31).astype(np.uint32)
    g0 = np.clip(np.round(c_max[:, 1] * 63.0 / 255.0), 0, 63).astype(np.uint32)
    b0 = np.clip(np.round(c_max[:, 2] * 31.0 / 255.0), 0, 31).astype(np.uint32)
    c0_565 = (r0 << 11) | (g0 << 5) | b0

    r1 = np.clip(np.round(c_min[:, 0] * 31.0 / 255.0), 0, 31).astype(np.uint32)
    g1 = np.clip(np.round(c_min[:, 1] * 63.0 / 255.0), 0, 63).astype(np.uint32)
    b1 = np.clip(np.round(c_min[:, 2] * 31.0 / 255.0), 0, 31).astype(np.uint32)
    c1_565 = (r1 << 11) | (g1 << 5) | b1

    swap = c0_565 < c1_565
    c0_final = np.where(swap, c1_565, c0_565)
    c1_final = np.where(swap, c0_565, c1_565)
    same = c0_final == c1_final
    bump = same & (c0_final < 0xFFFF)
    c0_final = np.where(bump, c0_final + 1, c0_final)
    drop = same & ~bump
    c1_final = np.where(drop, c1_final - 1, c1_final)

    out[:, 8] = (c0_final & 0xFF).astype(np.uint8)
    out[:, 9] = ((c0_final >> 8) & 0xFF).astype(np.uint8)
    out[:, 10] = (c1_final & 0xFF).astype(np.uint8)
    out[:, 11] = ((c1_final >> 8) & 0xFF).astype(np.uint8)

    p_max = np.where(swap[:, None], c_min, c_max)
    p_min = np.where(swap[:, None], c_max, c_min)
    axis = p_max - p_min
    len_sq = np.sum(axis * axis, axis=1, keepdims=True)
    len_sq = np.maximum(len_sq, 1e-4)
    proj = np.sum((rgb - p_min[:, None, :]) * axis[:, None, :], axis=2) / len_sq
    step = np.clip(np.round((1.0 - proj) * 3.0).astype(np.int32), 0, 3)
    lut_c = np.array([0, 2, 3, 1], dtype=np.uint32)
    codes_c = lut_c[step]
    codes_c[same] = 0
    shifts_c = (np.arange(16, dtype=np.uint32) * 2)[None, :]
    packed_c = np.bitwise_or.reduce(codes_c << shifts_c, axis=1)
    for b in range(4):
        out[:, 12 + b] = ((packed_c >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)

    return out.tobytes()


def build_dxt5_mipchain(rgba_float_flipped):
    """Build full DXT5 mipmap chain from top-to-bottom (H, W, 4) float32 [0..1] array."""
    h, w, _ = rgba_float_flipped.shape
    cur = np.clip(np.round(rgba_float_flipped * 255.0), 0, 255).astype(np.uint8)
    mips = []
    while True:
        mips.append(compress_dxt5_block_grid(cur))
        if cur.shape[0] <= 1 and cur.shape[1] <= 1:
            break
        nh = max(1, cur.shape[0] // 2)
        nw = max(1, cur.shape[1] // 2)
        cur = cur.reshape(nh, 2, nw, 2, 4).mean(axis=(1, 3)).astype(np.uint8)
    return b"".join(mips), len(mips)


def write_dds_dxt5(path, width, height, mip_count, dxt5_bytes):
    """Write standard DirectDraw Surface (.dds) file with DXT5 header and mipmaps."""
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000
    pitch = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 16
    caps1 = 0x1000 | 0x8 | 0x400000
    ddspf = struct.pack("<II4sIIIII", 32, 0x4, b"DXT5", 0, 0, 0, 0, 0)
    header = struct.pack(
        "<IIIIIII44s32sIIIII",
        124,
        flags,
        height,
        width,
        pitch,
        0,
        mip_count,
        b"\x00" * 44,
        ddspf,
        caps1,
        0,
        0,
        0,
        0,
    )
    with open(path, "wb") as fh:
        fh.write(b"DDS " + header + dxt5_bytes)


def image_to_dxt5(img, dds_path=None, bloom=False, max_res=1024):
    """Extract pixels from a Blender bpy.types.Image, flip Y to DirectX top-down, optionally bloom, and encode DXT5."""
    w, h = img.size
    if w == 0 or h == 0:
        img.reload()
        w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    rgba = buf.reshape((h, w, 4))[::-1, :, :]
    if bloom and not img.get("bloomed"):
        rgba = enhance_baked_image(rgba, bloom_strength=0.18, contrast=1.02)
        img["bloomed"] = True
    while max_res and (w > max_res or h > max_res) and w >= 2 and h >= 2:
        rgba = 0.25 * (rgba[0::2, 0::2] + rgba[1::2, 0::2] + rgba[0::2, 1::2] + rgba[1::2, 1::2])
        h, w = rgba.shape[0], rgba.shape[1]
    dxt5_bytes, mip_count = build_dxt5_mipchain(rgba)
    if dds_path:
        write_dds_dxt5(dds_path, w, h, mip_count, dxt5_bytes)
    return w, h, mip_count, dxt5_bytes


def elf_bone_tag(name):
    """Compute GTA V crBoneData 16-bit bone tag from bone name (0 for root bone Gun_Root)."""
    if name == "Gun_Root":
        return 0
    h = 0
    for ch in name.upper():
        h = ((h << 4) + ord(ch)) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return (h % 0xFE8F + 0x170) & 0xFFFF


BONE_TAGS = {
    "Gun_Root": 0,
    "Gun_GripR": 18308,
    "Gun_Main_Bone": 3360,
    "Gun_GripL": 18302,
    "gun_crane": 18771,
    "gun_cylinder": 3562,
    "Gun_VFX_Eject": 28405,
    "WAPClip": 1477,
    "Gun_Muzzle": 17833,
    "Gun_Trigger_Pr": 56099,
    "Gun_Hammer": 24730,
}


def attach_sollumz_hierarchy(rig, ob, slot, dds_path=None):
    """Populate Sollumz custom properties + collision Bound Composite / Bound Box on a Blender rig & mesh."""
    sc = rig.users_scene[0] if rig.users_scene else bpy.context.scene

    rig["sollum_type"] = 7
    rig["drawable_properties"] = {
        "lod_dist_high": 9998.0,
        "lod_dist_med": 9998.0,
        "lod_dist_low": 9998.0,
        "lod_dist_vlow": 9998.0,
    }
    rig.data.name = f"{rig.name}.skel"
    for b in rig.data.bones:
        b["bone_properties"] = {
            "manual_tag": BONE_TAGS.get(b.name, elf_bone_tag(b.name)),
            "use_manual_tag": 0,
            "flags": [
                {"name": "RotX"},
                {"name": "RotY"},
                {"name": "RotZ"},
                {"name": "TransX"},
                {"name": "TransY"},
                {"name": "TransZ"},
            ],
        }

    ob["sollum_type"] = 8
    ob["sz_lods"] = {
        "high": {"has_mesh": 1, "mesh_ref": None},
        "very_high": {},
        "active_lod_level": 0,
        "active_lod_level_prev": 0,
    }
    ob.data.name = "Gun_Root_high"
    ob.data["drawable_model_properties"] = {"render_mask": 255}

    for mat in ob.data.materials:
        if not mat:
            continue
        mat["sollum_type"] = 1
        mat["shader_properties"] = {
            "name": "emissive",
            "filename": "emissive.sps",
            "renderbucket": 0,
            "index": 0,
        }
        mat["animation_tracks"] = {}
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.bl_idname == "ShaderNodeTexImage":
                    node.name = "DiffuseSampler"
                    node.label = "DiffuseSampler"
                    node["is_sollumz"] = 1
                    node["texture_properties"] = {"embedded": 1}

    # Create <model>.col Bound Composite + Bound Box if not already present
    col_name = f"{rig.name}.col"
    existing_col = next((c for c in rig.children if c.name == col_name), None)
    if existing_col is None:
        col_empty = bpy.data.objects.new(col_name, None)
        col_empty["sollum_type"] = 20
        col_empty.parent = rig
        sc.collection.objects.link(col_empty)

        verts = [Vector(c) for c in ob.bound_box]
        lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
        hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
        center = (lo + hi) * 0.5
        ext = Vector((max(0.016, hi.x - lo.x), max(0.016, hi.y - lo.y), max(0.016, hi.z - lo.z)))

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=ext, verts=bm.verts)
        bmesh.ops.translate(bm, vec=center, verts=bm.verts)
        bme = bpy.data.meshes.new("Bound Box")
        bm.to_mesh(bme)
        bm.free()

        mat_name = "METAL_SOLID_SMALL" if slot in ("machete", "knife", "knuckle", "revolver", "bottle") else "WOOD_SOLID_SMALL"
        col_idx = 55 if mat_name == "METAL_SOLID_SMALL" else 69
        cmat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
        cmat.use_nodes = True
        cmat["sollum_type"] = 2
        cmat["collision_properties"] = {
            "collision_index": col_idx,
            "procedural_id": 0,
            "room_id": 0,
            "ped_density": 0,
            "material_color_index": 0,
        }
        cmat["collision_flags"] = {
            "stairs": 0, "not_climbable": 0, "see_through": 0, "shoot_through": 0,
            "not_cover": 0, "walkable_path": 0, "no_cam_collision": 0, "shoot_through_fx": 0,
            "no_decal": 0, "no_navmesh": 0, "no_ragdoll": 0, "vehicle_wheel": 0,
            "no_ptfx": 0, "too_steep_for_player": 0, "no_network_spawn": 0,
            "no_cam_collision_allow_clipping": 0,
        }
        bme.materials.append(cmat)

        b_ob = bpy.data.objects.new("Bound Box", bme)
        b_ob["sollum_type"] = 12
        b_ob["composite_flags1"] = {
            "map_weapon": 1, "map_dynamic": 1, "map_animal": 1, "map_cover": 1, "map_vehicle": 1,
        }
        b_ob["composite_flags2"] = {
            "vehicle_not_bvh": 1, "vehicle_bvh": 1, "ped": 1, "ragdoll": 1,
            "animal": 1, "animal_ragdoll": 1, "object": 1, "plant": 1,
            "projectile": 1, "explosion": 1, "forklift_forks": 1, "test_weapon": 1,
            "test_camera": 1, "test_ai": 1, "test_script": 1, "test_vehicle_wheel": 1, "glass": 1,
        }
        b_ob.parent = col_empty
        sc.collection.objects.link(b_ob)


def extract_geometry_chunks(ob, bone_index=2):
    """Extract triangulated 44-byte GTA V vertices and 16-bit index chunks (max 65535 indices / 21845 tris per chunk)."""
    me = ob.data
    me.calc_loop_triangles()
    uv_layer = me.uv_layers.active.data if me.uv_layers.active else None

    chunks = []
    vert_map = {}
    verts_list = []
    indices_list = []
    min_co = [1e9, 1e9, 1e9]
    max_co = [-1e9, -1e9, -1e9]

    def flush_chunk():
        nonlocal vert_map, verts_list, indices_list, min_co, max_co
        if not indices_list:
            return
        chunks.append({
            "vbytes": b"".join(verts_list),
            "vcnt": len(verts_list),
            "ibytes": struct.pack(f"<{len(indices_list)}H", *indices_list),
            "icnt": len(indices_list),
            "tcnt": len(indices_list) // 3,
            "min": tuple(min_co),
            "max": tuple(max_co),
        })
        vert_map = {}
        verts_list = []
        indices_list = []
        min_co = [1e9, 1e9, 1e9]
        max_co = [-1e9, -1e9, -1e9]

    bw = bytes((0, 0, 255, 0))
    bi = bytes((0, 0, bone_index, 0))
    col = bytes((255, 255, 255, 255))

    for tri in me.loop_triangles:
        if len(indices_list) + 3 > 65532 or len(verts_list) + 3 > 65530:
            flush_chunk()
        for loop_idx in tri.loops:
            loop = me.loops[loop_idx]
            v = me.vertices[loop.vertex_index]
            co = v.co
            no = loop.normal if loop.normal.length_squared > 1e-6 else v.normal
            if uv_layer:
                uv = uv_layer[loop_idx].uv
                u, tv = float(uv.x), float(1.0 - uv.y)
            else:
                u, tv = 0.5, 0.5
            key = (
                round(co.x, 5), round(co.y, 5), round(co.z, 5),
                round(no.x, 4), round(no.y, 4), round(no.z, 4),
                round(u, 5), round(tv, 5),
            )
            idx = vert_map.get(key)
            if idx is None:
                idx = len(verts_list)
                vert_map[key] = idx
                verts_list.append(
                    struct.pack(
                        "<fff4s4sfff4sff",
                        co.x, co.y, co.z,
                        bw, bi,
                        no.x, no.y, no.z,
                        col,
                        u, tv,
                    )
                )
                for a in range(3):
                    if co[a] < min_co[a]:
                        min_co[a] = co[a]
                    if co[a] > max_co[a]:
                        max_co[a] = co[a]
            indices_list.append(idx)

    flush_chunk()
    return chunks


class SysAlloc:
    def __init__(self, size=0x100000, start=0xD0):
        self.buf = bytearray(size)
        self.cur = start

    def align(self, a=16):
        self.cur = (self.cur + (a - 1)) & ~(a - 1)
        return self.cur

    def alloc(self, n, align=16):
        self.align(align)
        off = self.cur
        if off + n > len(self.buf):
            new_buf = bytearray(len(self.buf) * 2)
            new_buf[: len(self.buf)] = self.buf
            self.buf = new_buf
        self.cur += n
        return off

    def write(self, data, align=16):
        off = self.alloc(len(data), align)
        self.buf[off : off + len(data)] = data
        return off

    def cstr(self, text, align=1):
        return self.write(text.encode("ascii") + b"\x00", align)

    def ptr(self, off):
        return (0x50000000 | off) if off else 0


def _quat_to_rot33(qx, qy, qz, qw):
    """Convert quaternion (x, y, z, w) to 3x3 rotation matrix (row-major)."""
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def build_skeleton_block(mem, slot):
    """Write crSkeletonData + crBoneData + Transform matrices + BoneIds hash table into mem."""
    if slot == "revolver":
        bones = [
            ("Gun_Root", -1, -1, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 0x1077),
            ("Gun_GripR", 0, -1, (0.6552223, -0.00313911936, 0.0380733423, 0.7544696), (-0.094846, -0.0166690014, -0.061423), 0x1077),
            ("Gun_Main_Bone", 1, -1, (-0.6552227, 0.00313902716, -0.0380735062, 0.7544692), (0.0988139659, 0.0571830161, -0.00351999863), 0x1077),
            ("gun_crane", 2, 7, (7.458738e-07, -0.999997437, -3.58321444e-07, 0.00227101077), (0.071621, 0.004608009, -0.0003860057), 0x1077),
            ("gun_cylinder", 3, -1, (0.0, 0.0, 0.0, 1.0), (0.066057004, -0.004556007, -0.0259360019), 0x1077),
            ("Gun_VFX_Eject", 4, 6, (-0.999997437, -6.616358e-05, -0.00227101077, 1.96963429e-05), (0.0, 0.0, 0.0), 0x0077),
            ("WAPClip", 4, -1, (-1.39582562e-06, 0.999997437, 3.0943184e-07, 0.00227101077), (0.0, -8.90046358e-05, 0.0), 0x0077),
            ("Gun_Muzzle", 2, 8, (0.0, 0.0, 0.0, 1.0), (0.246804088, -3.60012054e-05, 0.03889999), 0x0077),
            ("Gun_Trigger_Pr", 2, 9, (0.8786764, -8.338794e-06, -0.4774178, 9.656311e-07), (0.006651002, -3.60012054e-05, -0.006707006), 0x0077),
            ("Gun_Hammer", 2, -1, (-0.00227100216, 0.0, 0.999997437, 0.0), (-0.0273350049, -3.599748e-05, 0.036532), 0x0077),
        ]
        cparent_pairs = [
            (1, 0), (1, 0), (1, 0), (1, 0),
            (2, 1), (2, 1), (2, 1), (2, 1),
            (3, 2), (7, 2), (8, 2), (9, 2),
            (4, 3), (4, 3), (4, 3), (4, 3),
            (5, 4), (6, 4), (6, 4), (6, 4),
        ]
        sig0, sig1, sig2 = 0x6AB68E4A, 0xF7CEE102, 0xAEB6BDFE
    elif slot == "poolcue":
        bones = [
            ("Gun_Root", -1, -1, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 0x1077),
            ("Gun_GripR", 0, 3, (0.618959248, -0.106119975, 0.0177541021, 0.778018653), (-0.045597, 0.002018001, 0.012259), 0x1077),
            ("Gun_Main_Bone", 1, -1, (-0.618959367, 0.106119841, -0.01775388, 0.7780186), (0.0424560122, -0.019481, -0.007166001), 0x0077),
            ("Gun_GripL", 0, -1, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.412707), 0x0077),
        ]
        cparent_pairs = [
            (1, 0), (3, 0), (3, 0), (3, 0),
            (2, 1), (2, 1), (2, 1), (2, 1),
        ]
        sig0, sig1, sig2 = 0x01D4CD98, 0x20F65128, 0xDC0CDC4B
    else:
        bones = [
            ("Gun_Root", -1, -1, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 0x1077),
            ("Gun_GripR", 0, -1, (0.618959248, -0.106119975, 0.0177541021, 0.778018653), (-0.045597, 0.002018001, 0.012259), 0x1077),
            ("Gun_Main_Bone", 1, -1, (-0.618959367, 0.106119841, -0.01775388, 0.7780186), (0.0424560122, -0.019481, -0.007166001), 0x0077),
        ]
        cparent_pairs = [
            (1, 0), (1, 0), (1, 0), (1, 0),
            (2, 1), (2, 1), (2, 1), (2, 1),
        ]
        sig0, sig1, sig2 = 0xC0FA28DD, 0x68C0B487, 0x5BA11D78

    nb = len(bones)
    name_ptrs = [mem.ptr(mem.cstr(b[0], 4)) for b in bones]

    bones_off = mem.alloc(nb * 0x50, 16)
    for idx, (bname, parent_idx, next_idx, rot, trans, flags) in enumerate(bones):
        bo = bones_off + idx * 0x50
        tag = BONE_TAGS.get(bname, elf_bone_tag(bname))
        struct.pack_into("<ffff", mem.buf, bo + 0x00, rot[0], rot[1], rot[2], rot[3])
        struct.pack_into("<ffff", mem.buf, bo + 0x10, trans[0], trans[1], trans[2], 0.0)
        struct.pack_into("<ffff", mem.buf, bo + 0x20, 1.0, 1.0, 1.0, 1.0)
        struct.pack_into("<hhI", mem.buf, bo + 0x30, next_idx, parent_idx, 0)
        struct.pack_into("<Q", mem.buf, bo + 0x38, name_ptrs[idx])
        struct.pack_into("<HHHHQ", mem.buf, bo + 0x40, flags, idx, tag, idx, 0)

    transf_off = mem.alloc(nb * 0x40, 16)
    inv_off = mem.alloc(nb * 0x40, 16)
    world_mats = []
    for idx, (_, parent_idx, _, rot, trans, _) in enumerate(bones):
        r_mat = _quat_to_rot33(*rot)
        t_vec = np.array(trans, dtype=np.float64)
        m_local = np.eye(4, dtype=np.float64)
        m_local[:3, :3] = r_mat
        m_local[:3, 3] = t_vec
        m_world = m_local if parent_idx < 0 else (world_mats[parent_idx] @ m_local)
        world_mats.append(m_world)

        # Snap near-identity world matrices (such as Gun_Main_Bone) to exact identity
        if idx == 2 or np.allclose(m_world, np.eye(4), atol=1e-5):
            r_inv = np.eye(3, dtype=np.float64)
            t_inv = np.zeros(3, dtype=np.float64)
        else:
            r_w = m_world[:3, :3]
            t_w = m_world[:3, 3]
            r_inv = r_w.T
            t_inv = -r_inv @ t_w

        to = transf_off + idx * 0x40
        struct.pack_into("<ffff", mem.buf, to + 0x00, float(r_mat[0, 0]), float(r_mat[1, 0]), float(r_mat[2, 0]), 0.0)
        struct.pack_into("<ffff", mem.buf, to + 0x10, float(r_mat[0, 1]), float(r_mat[1, 1]), float(r_mat[2, 1]), 0.0)
        struct.pack_into("<ffff", mem.buf, to + 0x20, float(r_mat[0, 2]), float(r_mat[1, 2]), float(r_mat[2, 2]), 0.0)
        struct.pack_into("<ffff", mem.buf, to + 0x30, float(t_vec[0]), float(t_vec[1]), float(t_vec[2]), 0.0)

        io = inv_off + idx * 0x40
        struct.pack_into("<ffff", mem.buf, io + 0x00, float(r_inv[0, 0]), float(r_inv[1, 0]), float(r_inv[2, 0]), 0.0)
        struct.pack_into("<ffff", mem.buf, io + 0x10, float(r_inv[0, 1]), float(r_inv[1, 1]), float(r_inv[2, 1]), 0.0)
        struct.pack_into("<ffff", mem.buf, io + 0x20, float(r_inv[0, 2]), float(r_inv[1, 2]), float(r_inv[2, 2]), 0.0)
        struct.pack_into("<ffff", mem.buf, io + 0x30, float(t_inv[0]), float(t_inv[1]), float(t_inv[2]), 0.0)

    parents_off = mem.alloc(((nb * 2) + 15) & ~15, 16)
    for idx, (_, parent_idx, _, _, _, _) in enumerate(bones):
        struct.pack_into("<h", mem.buf, parents_off + idx * 2, parent_idx)

    if len(cparent_pairs) % 4 != 0:
        raise RuntimeError(f"ChildParentIndices pairs ({len(cparent_pairs)}) must be a multiple of 4 SIMD lanes")
    for ch_i, pr_i in cparent_pairs:
        if not (0 <= ch_i < nb and 0 <= pr_i < nb) or bones[ch_i][1] != pr_i:
            raise RuntimeError(f"Invalid ChildParentIndices pair ({ch_i}, {pr_i}) for bone count {nb}")
    num_cparent_u16 = len(cparent_pairs) * 2
    cparents_off = mem.alloc(((len(cparent_pairs) * 4) + 15) & ~15, 16)
    for idx, (ch_i, pr_i) in enumerate(cparent_pairs):
        struct.pack_into("<HH", mem.buf, cparents_off + idx * 4, ch_i, pr_i)

    # Bone hash table (11 buckets, including Gun_Root at idx=0 -> tag=0)
    buckets = 11
    btable_off = mem.alloc(buckets * 8, 16)
    for idx in range(nb):
        bname = bones[idx][0]
        tag = BONE_TAGS.get(bname, elf_bone_tag(bname))
        b_idx = tag % buckets
        prev_ptr = struct.unpack_from("<Q", mem.buf, btable_off + b_idx * 8)[0]
        node_off = mem.alloc(16, 16)
        struct.pack_into("<IIQ", mem.buf, node_off, tag, idx, prev_ptr)
        struct.pack_into("<Q", mem.buf, btable_off + b_idx * 8, mem.ptr(node_off))

    skel_off = mem.alloc(0x70, 16)
    struct.pack_into("<QQ", mem.buf, skel_off + 0x00, 0x0000000140613CA0, 0)
    struct.pack_into("<QHHBBBB", mem.buf, skel_off + 0x10, mem.ptr(btable_off), buckets, nb, 0, 0, 0, 1)
    struct.pack_into("<QQ", mem.buf, skel_off + 0x20, mem.ptr(bones_off), mem.ptr(inv_off))
    struct.pack_into("<QQ", mem.buf, skel_off + 0x30, mem.ptr(transf_off), mem.ptr(parents_off))
    struct.pack_into("<QQ", mem.buf, skel_off + 0x40, mem.ptr(cparents_off), 0)
    struct.pack_into("<IIIHH", mem.buf, skel_off + 0x50, sig0, sig1, sig2, 1, nb)
    struct.pack_into("<QQ", mem.buf, skel_off + 0x60, num_cparent_u16, 0)
    return skel_off, nb


def build_bound_block(mem, bmin, bmax, slot):
    """Write phBoundComposite + phBoundBox collision hierarchy into mem."""
    cx = (bmin[0] + bmax[0]) * 0.5
    cy = (bmin[1] + bmax[1]) * 0.5
    cz = (bmin[2] + bmax[2]) * 0.5
    dx = max(0.016, (bmax[0] - bmin[0]) * 0.5)
    dy = max(0.016, (bmax[1] - bmin[1]) * 0.5)
    dz = max(0.016, (bmax[2] - bmin[2]) * 0.5)
    radius = math.sqrt(dx * dx + dy * dy + dz * dz)
    margin = min(0.004, min(dx, dy, dz) * 0.25)
    mat_id = 55 if slot in ("machete", "knife", "knuckle", "revolver", "bottle") else 69

    box_off = mem.alloc(0x70, 16)
    struct.pack_into("<QQ", mem.buf, box_off + 0x00, 0x000000014062DD58, 0)
    struct.pack_into("<BBHfff", mem.buf, box_off + 0x10, 3, 0, 0, radius, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, box_off + 0x20, bmax[0], bmax[1], bmax[2], margin)
    struct.pack_into("<fffI", mem.buf, box_off + 0x30, bmin[0], bmin[1], bmin[2], 1)
    struct.pack_into("<fffI", mem.buf, box_off + 0x40, cx, cy, cz, mat_id)
    struct.pack_into("<fffI", mem.buf, box_off + 0x50, cx, cy, cz, 0)
    struct.pack_into("<ffff", mem.buf, box_off + 0x60, 0.01, 0.01, 0.01, 0.01)

    child_ptrs = mem.alloc(16, 16)
    struct.pack_into("<QQ", mem.buf, child_ptrs, mem.ptr(box_off), 0)

    c_mats = mem.alloc(0x40, 16)
    struct.pack_into("<fffI", mem.buf, c_mats + 0x00, 1.0, 0.0, 0.0, 0)
    struct.pack_into("<fffI", mem.buf, c_mats + 0x10, 0.0, 1.0, 0.0, 1)
    struct.pack_into("<fffI", mem.buf, c_mats + 0x20, 0.0, 0.0, 1.0, 1)
    struct.pack_into("<fffI", mem.buf, c_mats + 0x30, 0.0, 0.0, 0.0, 0)

    c_boxes = mem.alloc(0x20, 16)
    struct.pack_into("<fffI", mem.buf, c_boxes + 0x00, bmin[0], bmin[1], bmin[2], 1)
    struct.pack_into("<ffff", mem.buf, c_boxes + 0x10, bmax[0], bmax[1], bmax[2], margin)

    c_flags = mem.alloc(16, 16)
    struct.pack_into("<IIQ", mem.buf, c_flags, 0x3E, 0x07F3BEC0, 0)

    comp_off = mem.alloc(0xB0, 16)
    struct.pack_into("<QQ", mem.buf, comp_off + 0x00, 0x000000014062BAA8, 0)
    struct.pack_into("<BBHfff", mem.buf, comp_off + 0x10, 10, 0, 0, radius, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, comp_off + 0x20, bmax[0], bmax[1], bmax[2], margin)
    struct.pack_into("<fffI", mem.buf, comp_off + 0x30, bmin[0], bmin[1], bmin[2], 1)
    struct.pack_into("<ffff", mem.buf, comp_off + 0x40, cx, cy, cz, 0.0)
    struct.pack_into("<ffff", mem.buf, comp_off + 0x50, cx, cy, cz, 0.0)
    struct.pack_into("<ffff", mem.buf, comp_off + 0x60, 0.02, 0.02, 0.02, 0.01)
    struct.pack_into("<QQ", mem.buf, comp_off + 0x70, mem.ptr(child_ptrs), mem.ptr(c_mats))
    struct.pack_into("<QQ", mem.buf, comp_off + 0x80, mem.ptr(c_mats), mem.ptr(c_boxes))
    struct.pack_into("<QQ", mem.buf, comp_off + 0x90, mem.ptr(c_flags), mem.ptr(c_flags))
    struct.pack_into("<HHII", mem.buf, comp_off + 0xA0, 1, 1, 0, 0)
    return comp_off


def build_shader_and_txd_block(mem, model_name, tex_w, tex_h, mip_count):
    """Write grmShaderGroup + pgDictionary<grcTextureDX11> + grcTextureDX11 + emissive.sps shader."""
    tex_name_off = mem.cstr(model_name, 4)

    tex_off = mem.alloc(0x90, 16)
    struct.pack_into("<QQ", mem.buf, tex_off + 0x00, 0x00007FFDEA9A3660, 0)
    struct.pack_into("<QQ", mem.buf, tex_off + 0x28, mem.ptr(tex_name_off), 0x00800001)
    struct.pack_into("<Q", mem.buf, tex_off + 0x40, 0x20155580)
    struct.pack_into("<HHHH", mem.buf, tex_off + 0x50, tex_w, tex_h, 1, tex_w)
    struct.pack_into("<4sBBH", mem.buf, tex_off + 0x58, b"DXT5", 0, mip_count, 0)
    struct.pack_into("<Q", mem.buf, tex_off + 0x70, 0x60000000)

    hash_arr_off = mem.alloc(16, 16)
    struct.pack_into("<IIQ", mem.buf, hash_arr_off, joaat(model_name), 0, 0)

    tex_ptr_arr = mem.alloc(16, 16)
    struct.pack_into("<QQ", mem.buf, tex_ptr_arr, mem.ptr(tex_off), 0)

    txd_off = mem.alloc(0x40, 16)
    struct.pack_into("<QQ", mem.buf, txd_off + 0x00, 0x00007FFDEA9A0C20, 0)
    struct.pack_into("<QQ", mem.buf, txd_off + 0x10, 0, 1)
    struct.pack_into("<QHHI", mem.buf, txd_off + 0x20, mem.ptr(hash_arr_off), 1, 1, 0)
    struct.pack_into("<QHHI", mem.buf, txd_off + 0x30, mem.ptr(tex_ptr_arr), 1, 1, 0)

    # emissive.sps shader parameters (1 sampler + 6 float4 vectors)
    params_off = mem.alloc(0xF0, 16)
    vec_base = params_off + 0x70
    struct.pack_into("<QQ", mem.buf, params_off + 0x00, 0, mem.ptr(tex_off))
    for i in range(6):
        struct.pack_into("<QQ", mem.buf, params_off + 0x10 * (i + 1), 1, mem.ptr(vec_base + i * 0x10))
    # Default emissive.sps parameter values:
    # param[1]=(1,0,0,1), globalAnimUV0=(1,0,0,0), param[3]=(0,0,0,0), param[4]=(0.75,0,0,0), globalAnimUV1=(0,1,0,0), emissiveMultiplier=(1,0,0,0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x00, 1.0, 0.0, 0.0, 1.0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x10, 1.0, 0.0, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x20, 0.0, 0.0, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x30, 0.75, 0.0, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x40, 0.0, 1.0, 0.0, 0.0)
    struct.pack_into("<ffff", mem.buf, vec_base + 0x50, 1.0, 0.0, 0.0, 0.0)
    struct.pack_into("<QQ", mem.buf, vec_base + 0x60, 0x948A54F2F1FE2B71, 0x4620A35DE9437406)
    struct.pack_into("<QQ", mem.buf, vec_base + 0x70, 0xBA54C1905EEBED48, 0x00000000D79BFC1E)

    shader_off = mem.alloc(0x30, 16)
    struct.pack_into("<QI", mem.buf, shader_off + 0x00, mem.ptr(params_off), joaat("emissive"))
    struct.pack_into("<I", mem.buf, shader_off + 0x0C, 0)
    struct.pack_into("<QQ", mem.buf, shader_off + 0x10, 0x011000D080000007, 0x000000009D183303)
    struct.pack_into("<QQ", mem.buf, shader_off + 0x20, 0x010000000000FF01, 0)

    shader_ptr_arr = mem.alloc(16, 16)
    struct.pack_into("<QQ", mem.buf, shader_ptr_arr, mem.ptr(shader_off), 0)

    sg_off = mem.alloc(0x40, 16)
    struct.pack_into("<QQ", mem.buf, sg_off + 0x00, 0x00007FFDEA9ACA38, mem.ptr(txd_off))
    struct.pack_into("<QHHI", mem.buf, sg_off + 0x10, mem.ptr(shader_ptr_arr), 1, 1, 0)
    struct.pack_into("<QQ", mem.buf, sg_off + 0x30, 7, 0)
    return sg_off


def export_ydr_from_objects(rig, ob, slot, out_dir, make_hi=True, dds_out_dir=None):
    """Compile a Blender rig + mesh into RSC7 .ydr (version 165) and .ytd (version 13) files."""
    os.makedirs(out_dir, exist_ok=True)
    model_name = rig.name

    # Find baked texture image
    img = None
    for mat in ob.data.materials:
        if mat and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.bl_idname == "ShaderNodeTexImage" and n.image:
                    img = n.image
                    break
        if img:
            break
    if img is None:
        img = bpy.data.images.get(f"{model_name}_d")
    if img is None:
        raise RuntimeError(f"No baked image found on {model_name}; run with --bake first")

    dds_dir = dds_out_dir or out_dir
    dds_path = os.path.join(dds_dir, f"{model_name}_d.dds")
    tex_w, tex_h, mip_count, dxt5_bytes = image_to_dxt5(img, dds_path=dds_path, bloom=True)
    attach_sollumz_hierarchy(rig, ob, slot, dds_path=dds_path)

    bone_idx = 2
    chunks = extract_geometry_chunks(ob, bone_index=bone_idx)
    if not chunks:
        raise RuntimeError(f"Mesh {ob.name} has 0 triangles")

    # Estimate required system segment size (1 MB = 0x100000 or 2 MB = 0x200000)
    total_vb_ib = sum(len(c["vbytes"]) + len(c["ibytes"]) for c in chunks)
    use_2mb_sys = (total_vb_ib + 0x10000) > 0x100000
    sys_size = 0x200000 if use_2mb_sys else 0x100000
    sys_flags = 0xA0000014 if use_2mb_sys else 0xA0000013

    use_8mb_gfx = len(dxt5_bytes) > 0x200000
    gfx_size = 0x800000 if use_8mb_gfx else 0x200000
    gfx_flags = 0x50000016 if use_8mb_gfx else 0x50000014

    mem = SysAlloc(size=sys_size, start=0xD0)

    # 1. Write all VertexData and IndexData buffers first
    for c in chunks:
        c["v_off"] = mem.write(c["vbytes"], align=16)
    for c in chunks:
        c["i_off"] = mem.write(c["ibytes"], align=16)

    # Overall bounding box
    bmin = (
        min(c["min"][0] for c in chunks),
        min(c["min"][1] for c in chunks),
        min(c["min"][2] for c in chunks),
    )
    bmax = (
        max(c["max"][0] for c in chunks),
        max(c["max"][1] for c in chunks),
        max(c["max"][2] for c in chunks),
    )
    bc = ((bmin[0] + bmax[0]) * 0.5, (bmin[1] + bmax[1]) * 0.5, (bmin[2] + bmax[2]) * 0.5)
    br = math.sqrt(sum((bmax[a] - bc[a]) ** 2 for a in range(3)))

    # 2. Skeleton, Bounds, ShaderGroup
    skel_off, num_bones = build_skeleton_block(mem, slot)
    bound_off = build_bound_block(mem, bmin, bmax, slot)
    sg_off = build_shader_and_txd_block(mem, model_name, tex_w, tex_h, mip_count)

    # 3. Vertex declaration & BoneIds array
    vdecl_off = mem.alloc(16, 16)
    struct.pack_into("<IIQ", mem.buf, vdecl_off, 0x0000005F, 0x0600002C, 0x7755555555996996)

    bone_ids_off = mem.alloc(((num_bones * 2) + 15) & ~15, 16)
    for bi_idx in range(num_bones):
        struct.pack_into("<H", mem.buf, bone_ids_off + bi_idx * 2, bi_idx)

    # 4. Geometries (grmGeometryQB + VertexBuffer + IndexBuffer)
    geom_ptrs = []
    for c in chunks:
        vb_off = mem.alloc(0x80, 16)
        struct.pack_into("<QQ", mem.buf, vb_off + 0x00, 0x00007FFDEA9A16F0, 44)
        struct.pack_into("<QQ", mem.buf, vb_off + 0x10, mem.ptr(c["v_off"]), c["vcnt"])
        struct.pack_into("<QQ", mem.buf, vb_off + 0x20, mem.ptr(c["v_off"]), 0)
        struct.pack_into("<QQ", mem.buf, vb_off + 0x30, mem.ptr(vdecl_off), 0)

        ib_off = mem.alloc(0x50, 16)
        struct.pack_into("<QQ", mem.buf, ib_off + 0x00, 0x00007FFDEA9A7B90, c["icnt"])
        struct.pack_into("<QQ", mem.buf, ib_off + 0x10, mem.ptr(c["i_off"]), 0)

        g_off = mem.alloc(0x98, 16)
        struct.pack_into("<QQ", mem.buf, g_off + 0x00, 0x00007FFDEA9A1960, 0)
        struct.pack_into("<QQ", mem.buf, g_off + 0x18, mem.ptr(vb_off), 0)
        struct.pack_into("<QQ", mem.buf, g_off + 0x38, mem.ptr(ib_off), 0)
        struct.pack_into("<II", mem.buf, g_off + 0x58, c["icnt"], c["tcnt"])
        struct.pack_into("<HHI", mem.buf, g_off + 0x60, c["vcnt"], 3, 0)
        struct.pack_into("<Q", mem.buf, g_off + 0x68, mem.ptr(bone_ids_off))
        struct.pack_into("<HHI", mem.buf, g_off + 0x70, 44, num_bones, 0)
        struct.pack_into("<Q", mem.buf, g_off + 0x78, mem.ptr(c["v_off"]))
        geom_ptrs.append(mem.ptr(g_off))

    gcnt = len(geom_ptrs)
    geom_list_off = mem.alloc(max(16, gcnt * 8), 16)
    for i, gp in enumerate(geom_ptrs):
        struct.pack_into("<Q", mem.buf, geom_list_off + i * 8, gp)

    # Model AABB array (1 overall + gcnt per-geometry if gcnt > 1, or 1 if gcnt == 1)
    aabb_count = (gcnt + 1) if gcnt > 1 else 1
    aabbs_off = mem.alloc(aabb_count * 0x20, 16)
    struct.pack_into("<ffff", mem.buf, aabbs_off + 0x00, bmin[0], bmin[1], bmin[2], 0.0)
    struct.pack_into("<ffff", mem.buf, aabbs_off + 0x10, bmax[0], bmax[1], bmax[2], 0.0)
    if gcnt > 1:
        for i, c in enumerate(chunks):
            ao = aabbs_off + (i + 1) * 0x20
            struct.pack_into("<ffff", mem.buf, ao + 0x00, c["min"][0], c["min"][1], c["min"][2], 0.0)
            struct.pack_into("<ffff", mem.buf, ao + 0x10, c["max"][0], c["max"][1], c["max"][2], 0.0)

    shader_map_off = mem.alloc(16, 16)
    for i in range(gcnt):
        struct.pack_into("<H", mem.buf, shader_map_off + i * 2, 0)

    dm_off = mem.alloc(0x30, 16)
    struct.pack_into("<QQ", mem.buf, dm_off + 0x00, 0x00007FFDEA9A1B38, mem.ptr(geom_list_off))
    struct.pack_into("<HHQ", mem.buf, dm_off + 0x10, gcnt, gcnt, 0)
    struct.pack_into("<QQ", mem.buf, dm_off + 0x18, mem.ptr(aabbs_off), mem.ptr(shader_map_off))
    struct.pack_into("<BBHHH", mem.buf, dm_off + 0x28, num_bones, 1, 0, 0x01FF, gcnt)

    model_ptr_arr = mem.alloc(16, 16)
    struct.pack_into("<QQ", mem.buf, model_ptr_arr, mem.ptr(dm_off), 0)

    models_high_off = mem.alloc(16, 16)
    struct.pack_into("<QHH", mem.buf, models_high_off, mem.ptr(model_ptr_arr), 1, 1)

    pagemap_off = mem.alloc(0x20, 16)
    struct.pack_into("<QQ", mem.buf, pagemap_off, 0, 0x0101)

    drawable_name_off = mem.cstr(model_name, 4)

    # 5. Root gtaDrawable header at 0x00..0xCF
    struct.pack_into("<QQ", mem.buf, 0x00, 0x0000000140573178, mem.ptr(pagemap_off))
    struct.pack_into("<QQ", mem.buf, 0x10, mem.ptr(sg_off), mem.ptr(skel_off))
    struct.pack_into("<ffff", mem.buf, 0x20, bc[0], bc[1], bc[2], br)
    struct.pack_into("<ffff", mem.buf, 0x30, bmin[0], bmin[1], bmin[2], 0.0)
    struct.pack_into("<ffff", mem.buf, 0x40, bmax[0], bmax[1], bmax[2], 0.0)
    struct.pack_into("<QQ", mem.buf, 0x50, mem.ptr(models_high_off), 0)
    struct.pack_into("<QQ", mem.buf, 0x60, 0, 0)
    struct.pack_into("<ffff", mem.buf, 0x70, 9998.0, 9998.0, 9998.0, 9998.0)
    struct.pack_into("<QQ", mem.buf, 0x80, 0xFF01, 0)
    struct.pack_into("<QQ", mem.buf, 0x90, 0, 0x00120000)
    struct.pack_into("<QQ", mem.buf, 0xA0, mem.ptr(models_high_off), mem.ptr(drawable_name_off))
    struct.pack_into("<QQ", mem.buf, 0xB0, 0, 0)
    struct.pack_into("<QQ", mem.buf, 0xC0, 0, mem.ptr(bound_off))

    # 6. Graphics segment
    gfx_buf = bytearray(gfx_size)
    gfx_buf[: len(dxt5_bytes)] = dxt5_bytes

    comp = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=-15)
    compressed = comp.compress(bytes(mem.buf) + bytes(gfx_buf)) + comp.flush()
    rsc7_hdr = struct.pack("<4sIII", b"RSC7", 165, sys_flags, gfx_flags)
    ydr_bytes = rsc7_hdr + compressed

    ydr_path = os.path.join(out_dir, f"{model_name}.ydr")
    with open(ydr_path, "wb") as fh:
        fh.write(ydr_bytes)

    if make_hi:
        hi_path = os.path.join(out_dir, f"{model_name}_hi.ydr")
        with open(hi_path, "wb") as fh:
            fh.write(ydr_bytes)

    # 7. Write companion .ytd (version 13) with full grcTextureDX11 + DXT5 physical segment
    ytd_sys = bytearray(0x2000)
    struct.pack_into("<QQ", ytd_sys, 0x0000, 0x0000000100000000, 0x50000040)
    struct.pack_into("<QQ", ytd_sys, 0x0010, 0, 1)
    struct.pack_into("<QHHI", ytd_sys, 0x0020, 0x50001120, 1, 1, 0)
    struct.pack_into("<QHHI", ytd_sys, 0x0030, 0x50001110, 1, 1, 0)
    struct.pack_into("<QQ", ytd_sys, 0x0040, 0, 0x0101)
    struct.pack_into("<QQ", ytd_sys, 0x1060, 0x0000000100000000, 0)
    struct.pack_into("<QQ", ytd_sys, 0x1088, 0x500010F0, 1)
    struct.pack_into("<HHHH", ytd_sys, 0x10B0, tex_w, tex_h, 1, tex_w)
    struct.pack_into("<4sBBH", ytd_sys, 0x10B8, b"DXT5", 0, mip_count, 0)
    struct.pack_into("<Q", ytd_sys, 0x10D0, 0x60000000)
    name_bytes = model_name.encode("ascii")[:31] + b"\x00"
    ytd_sys[0x10F0 : 0x10F0 + len(name_bytes)] = name_bytes
    struct.pack_into("<QQ", ytd_sys, 0x1110, 0x50001060, 0)
    struct.pack_into("<IIQ", ytd_sys, 0x1120, joaat(model_name), 0, 0)

    ytd_gfx_flags = 0xD0000206 if use_8mb_gfx else 0xD0000086
    comp_ytd = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=-15)
    ytd_payload = comp_ytd.compress(bytes(ytd_sys) + bytes(gfx_buf)) + comp_ytd.flush()
    ytd_bytes = struct.pack("<4sIII", b"RSC7", 13, 0x00020000, ytd_gfx_flags) + ytd_payload
    ytd_path = os.path.join(out_dir, f"{model_name}.ytd")
    with open(ytd_path, "wb") as fh:
        fh.write(ytd_bytes)
    hi_ytd_path = os.path.join(out_dir, f"{model_name}_hi.ytd")
    if os.path.exists(hi_ytd_path):
        try:
            os.remove(hi_ytd_path)
        except OSError:
            pass

    return {
        "ydr": ydr_path,
        "ytd": ytd_path,
        "dds": dds_path,
        "size_kb": round(len(ydr_bytes) / 1024, 1),
        "geometries": gcnt,
        "vertices": sum(c["vcnt"] for c in chunks),
        "triangles": sum(c["tcnt"] for c in chunks),
    }


def detect_slot_from_name(name):
    low = name.lower()
    for s in ("poolcue", "bottle", "machete", "knife", "knuckle", "revolver", "bat"):
        if s in low:
            return s
    return "machete"


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True, help="Path to .blend file or directory of .blend files")
    ap.add_argument("--out", required=True, help="Target stream/ directory for .ydr and .ytd")
    ap.add_argument("--slot", default="", help="Override weapon slot")
    ap.add_argument("--no-hi", action="store_true", help="Do not write _hi.ydr copy")
    args = ap.parse_args(argv)

    src = os.path.abspath(args.blend)
    blend_files = (
        [os.path.join(src, f) for f in sorted(os.listdir(src)) if f.endswith(".blend")]
        if os.path.isdir(src)
        else [src]
    )

    for bf in blend_files:
        bpy.ops.wm.open_mainfile(filepath=bf)
        rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        ob = next((o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("Bound")), None)
        if not rig or not ob:
            print(f"@@YDR skip {bf}: missing armature or mesh")
            continue
        slot = args.slot or detect_slot_from_name(rig.name)
        info = export_ydr_from_objects(
            rig,
            ob,
            slot,
            os.path.abspath(args.out),
            make_hi=not args.no_hi,
            dds_out_dir=os.path.dirname(bf),
        )
        print("@@YDR exported", info)


if __name__ == "__main__":
    main()
