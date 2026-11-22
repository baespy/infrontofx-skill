"""prop-forge: High-quality vectorized PCA DXT1 (BC1) & DXT5 (BC3) DDS encoder with sharp linear mipmaps.

Eliminates blurry / muddy ("วุ้น") textures and minimizes FiveM streaming VRAM:
- Opaque atlases encode as DXT1 (4 bpp = half the VRAM of DXT5) using per-block PCA principal-axis endpoints
  and exact 4-color RGB565 Euclidean argmin matching.
- Transparent decals bleed RGB into empty alpha pixels before linear premultiplied-alpha mipmapping to
  prevent dark border halos, then encode as DXT5 (8 bpp).
- Mild unsharp preservation on mip levels 1-3 keeps signs and logos crisp at mid-distance in GTA V / FiveM.
"""

import struct
import numpy as np


def _bleed_rgb_into_transparent(rgba, passes=8):
    """Fill RGB of alpha~0 pixels from neighboring opaque pixels to kill dark mipmap halos."""
    arr = rgba.copy()
    valid = arr[..., 3] > 0.04
    if valid.all() or not valid.any():
        return arr
    rgb = arr[..., :3]
    for _ in range(passes):
        if valid.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(valid.shape, dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            s_rgb = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            s_val = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
            if dy == -1:
                s_val[-1, :] = False
            elif dy == 1:
                s_val[0, :] = False
            if dx == -1:
                s_val[:, -1] = False
            elif dx == 1:
                s_val[:, 0] = False
            m = s_val.astype(np.float32)
            acc += s_rgb * m[..., None]
            cnt += m
        fill = (~valid) & (cnt > 0)
        if not fill.any():
            break
        rgb[fill] = acc[fill] / cnt[fill, None]
        valid[fill] = True
    arr[..., :3] = rgb
    return arr


def _unsharp_rgb(rgb_f, amount=0.20):
    """Gentle 3x3 unsharp mask on RGB to keep mip levels 1-3 crisp without ringing."""
    if rgb_f.shape[0] < 4 or rgb_f.shape[1] < 4 or amount <= 0.0:
        return rgb_f
    p = np.pad(rgb_f, ((1, 1), (1, 1), (0, 0)), mode="edge")
    blur = (
        p[0:-2, 0:-2] + 2.0 * p[0:-2, 1:-1] + p[0:-2, 2:]
        + 2.0 * p[1:-1, 0:-2] + 4.0 * p[1:-1, 1:-1] + 2.0 * p[1:-1, 2:]
        + p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + p[2:, 2:]
    ) * (1.0 / 16.0)
    return np.clip(rgb_f + (rgb_f - blur) * amount, 0.0, 1.0)


def _pad_to_blocks(rgba_u8):
    h, w, _ = rgba_u8.shape
    pad_h = max(4, (h + 3) & ~3)
    pad_w = max(4, (w + 3) & ~3)
    if pad_h == h and pad_w == w:
        return rgba_u8
    padded = np.zeros((pad_h, pad_w, 4), dtype=np.uint8)
    padded[:h, :w] = rgba_u8
    for y in range(h, pad_h):
        padded[y, :w] = rgba_u8[h - 1, :w]
    for x in range(w, pad_w):
        padded[:, x] = padded[:, w - 1]
    return padded


def _decode_rgb565(c565):
    r = ((c565 >> 11) & 31).astype(np.float32)
    g = ((c565 >> 5) & 63).astype(np.float32)
    b = (c565 & 31).astype(np.float32)
    r = (r * 255.0) / 31.0
    g = (g * 255.0) / 63.0
    b = (b * 255.0) / 31.0
    return np.stack((r, g, b), axis=-1)


def _encode_rgb565(rgb_f):
    r = np.clip(np.round(rgb_f[..., 0] * (31.0 / 255.0)), 0, 31).astype(np.uint32)
    g = np.clip(np.round(rgb_f[..., 1] * (63.0 / 255.0)), 0, 63).astype(np.uint32)
    b = np.clip(np.round(rgb_f[..., 2] * (31.0 / 255.0)), 0, 31).astype(np.uint32)
    return (r << 11) | (g << 5) | b


def _compress_color_blocks(blocks_rgb_u8):
    """PCA principal-axis + exact 4-entry RGB565 Euclidean argmin DXT1 color block compressor (8 bytes/block)."""
    n = blocks_rgb_u8.shape[0]
    rgb = blocks_rgb_u8.astype(np.float32)
    # Perceptual luminance weighting (R=0.299, G=0.587, B=0.114 -> sqrt weights for L2)
    w_l2 = np.array([0.55, 0.77, 0.34], dtype=np.float32)[None, None, :]

    mu = rgb.mean(axis=1, keepdims=True)
    xc = rgb - mu
    # 3x3 covariance matrix per block: (n, 3, 3)
    cov = np.einsum("nki,nkj->nij", xc, xc)
    # Power iteration initialized from diagonal span
    span = rgb.max(axis=1) - rgb.min(axis=1)
    axis = span + np.array([1e-3, 2e-3, 1.5e-3], dtype=np.float32)[None, :]
    for _ in range(4):
        axis = np.einsum("nij,nj->ni", cov, axis)
        norm = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = np.where(norm > 1e-6, axis / np.maximum(norm, 1e-6), np.array([0.577, 0.577, 0.577], dtype=np.float32))

    proj = np.einsum("nki,ni->nk", xc, axis)
    idx_min = np.argmin(proj, axis=1)
    idx_max = np.argmax(proj, axis=1)
    arange_n = np.arange(n)
    p0 = rgb[arange_n, idx_max]
    p1 = rgb[arange_n, idx_min]

    # Gentle 4% inset avoids outlier-driven banding across smooth vinyl gradients
    inset = (p0 - p1) * 0.03
    e0 = np.clip(p0 - inset, 0.0, 255.0)
    e1 = np.clip(p1 + inset, 0.0, 255.0)

    c0 = _encode_rgb565(e0)
    c1 = _encode_rgb565(e1)

    swap = c0 < c1
    c0_f = np.where(swap, c1, c0)
    c1_f = np.where(swap, c0, c1)
    same = c0_f == c1_f
    # Keep 4-color opaque mode (c0 > c1) without altering the exact selected solid color:
    # - if solid color > 0: keep c0_f exact, set c1_f = c0_f - 1, pick code 0 (pal0 == exact color)
    # - if solid color == 0: set c0_f = 1, keep c1_f = 0 exact, pick code 1 (pal1 == exact black)
    same_nz = same & (c0_f > 0)
    same_z = same & (c0_f == 0)
    c1_f = np.where(same_nz, c0_f - 1, c1_f)
    c0_f = np.where(same_z, np.uint32(1), c0_f)

    pal0 = _decode_rgb565(c0_f)
    pal1 = _decode_rgb565(c1_f)
    pal2 = (2.0 * pal0 + pal1) * (1.0 / 3.0)
    pal3 = (pal0 + 2.0 * pal1) * (1.0 / 3.0)
    # Palette ordered by DXT1 index code: 0=c0, 1=c1, 2=(2c0+c1)/3, 3=(c0+2c1)/3
    pal = np.stack((pal0, pal1, pal2, pal3), axis=1)  # (n, 4, 3)

    # Exact weighted Euclidean distance to all 4 palette entries -> (n, 16, 4)
    diff = (rgb[:, :, None, :] - pal[:, None, :, :]) * w_l2[:, :, None, :]
    dist2 = np.sum(diff * diff, axis=-1)
    codes = np.argmin(dist2, axis=-1).astype(np.uint32)
    codes[same_nz] = 0
    codes[same_z] = 1

    shifts = (np.arange(16, dtype=np.uint32) * 2)[None, :]
    packed = np.bitwise_or.reduce(codes << shifts, axis=1)

    out = np.zeros((n, 8), dtype=np.uint8)
    out[:, 0] = (c0_f & 0xFF).astype(np.uint8)
    out[:, 1] = ((c0_f >> 8) & 0xFF).astype(np.uint8)
    out[:, 2] = (c1_f & 0xFF).astype(np.uint8)
    out[:, 3] = ((c1_f >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        out[:, 4 + b] = ((packed >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)
    return out


def _compress_alpha_blocks(blocks_alpha_u8):
    """Exact 8-level DXT5 alpha block compressor (8 bytes/block)."""
    n = blocks_alpha_u8.shape[0]
    alpha = blocks_alpha_u8.astype(np.int32)
    a_max = alpha.max(axis=1)
    a_min = alpha.min(axis=1)

    out = np.zeros((n, 8), dtype=np.uint8)
    out[:, 0] = a_max.astype(np.uint8)
    out[:, 1] = a_min.astype(np.uint8)
    span_a = np.maximum(1, a_max - a_min)[:, None]
    pos_a = np.clip(np.round((a_max[:, None] - alpha) * 7.0 / span_a).astype(np.int32), 0, 7)
    lut_a = np.array([0, 2, 3, 4, 5, 6, 7, 1], dtype=np.uint64)
    codes_a = lut_a[pos_a]
    codes_a[a_max == a_min] = 0
    shifts_a = (np.arange(16, dtype=np.uint64) * 3)[None, :]
    packed_a = np.bitwise_or.reduce(codes_a << shifts_a, axis=1)
    for b in range(6):
        out[:, 2 + b] = ((packed_a >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)
    return out


def compress_dxt1_grid(rgba_u8):
    padded = _pad_to_blocks(rgba_u8)
    h, w, _ = padded.shape
    blocks = padded.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    return _compress_color_blocks(blocks[:, :, :3]).tobytes()


def compress_dxt5_grid(rgba_u8):
    padded = _pad_to_blocks(rgba_u8)
    h, w, _ = padded.shape
    blocks = padded.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    a_out = _compress_alpha_blocks(blocks[:, :, 3])
    c_out = _compress_color_blocks(blocks[:, :, :3])
    return np.concatenate((a_out, c_out), axis=1).tobytes()


def _downsample_2x(rgba_f, has_alpha):
    """Linear-light premultiplied-alpha 2x2 box downsampler (zero darkening / zero haloing)."""
    h, w, _ = rgba_f.shape
    nh = max(1, h // 2)
    nw = max(1, w // 2)
    sh = 2 if h > 1 else 1
    sw = 2 if w > 1 else 1
    lin_rgb = np.power(np.clip(rgba_f[..., :3], 0.0, 1.0), 2.2)
    alpha = np.clip(rgba_f[..., 3:4], 0.0, 1.0)
    if has_alpha:
        prem = lin_rgb * alpha
        prem_d = prem.reshape(nh, sh, nw, sw, 3).mean(axis=(1, 3))
        a_d = alpha.reshape(nh, sh, nw, sw, 1).mean(axis=(1, 3))
        rgb_d = np.where(a_d > 1e-4, prem_d / np.maximum(a_d, 1e-4), lin_rgb.reshape(nh, sh, nw, sw, 3).mean(axis=(1, 3)))
    else:
        rgb_d = lin_rgb.reshape(nh, sh, nw, sw, 3).mean(axis=(1, 3))
        a_d = np.ones((nh, nw, 1), dtype=np.float32)
    srgb = np.power(np.clip(rgb_d, 0.0, 1.0), 1.0 / 2.2)
    out = np.concatenate((srgb, a_d), axis=-1)
    if has_alpha:
        out = _bleed_rgb_into_transparent(out, passes=3)
    return out


def write_dds(path, width, height, mip_count, payload, fourcc=b"DXT1"):
    bpb = 8 if fourcc == b"DXT1" else 16
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000
    pitch = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * bpb
    caps1 = 0x1000 | 0x8 | 0x400000
    ddspf = struct.pack("<II4sIIIII", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
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
        fh.write(b"DDS " + header + payload)


def encode_image_to_dds(img, dds_path, max_res=512, force_format="auto", sharpen_mips=0.20):
    """Encode a Blender Image to crisp DXT1 (opaque) or DXT5 (alpha) DDS with sharp linear mipmaps."""
    w, h = img.size
    if w == 0 or h == 0:
        img.reload()
        w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    rgba = np.clip(buf.reshape((h, w, 4))[::-1, :, :], 0.0, 1.0)

    has_alpha = bool(rgba[..., 3].min() < 0.98)
    if force_format == "DXT1":
        has_alpha = False
    elif force_format == "DXT5":
        has_alpha = True

    if has_alpha:
        rgba = _bleed_rgb_into_transparent(rgba, passes=8)

    while max_res and (w > max_res or h > max_res) and w >= 2 and h >= 2:
        rgba = _downsample_2x(rgba, has_alpha)
        h, w = rgba.shape[0], rgba.shape[1]

    fourcc = b"DXT5" if has_alpha else b"DXT1"
    compress = compress_dxt5_grid if has_alpha else compress_dxt1_grid

    mips = []
    cur = rgba
    level = 0
    while True:
        cur_u8 = np.clip(np.round(cur * 255.0), 0, 255).astype(np.uint8)
        mips.append(compress(cur_u8))
        if cur.shape[0] <= 1 and cur.shape[1] <= 1:
            break
        cur = _downsample_2x(cur, has_alpha)
        level += 1
        if 1 <= level <= 3 and sharpen_mips > 0.0 and cur.shape[0] >= 16 and cur.shape[1] >= 16:
            cur = cur.copy()
            cur[..., :3] = _unsharp_rgb(cur[..., :3], amount=sharpen_mips)

    payload = b"".join(mips)
    write_dds(dds_path, w, h, len(mips), payload, fourcc=fourcc)
    return {
        "width": w,
        "height": h,
        "format": fourcc.decode("ascii"),
        "mips": len(mips),
        "bytes": len(payload),
    }
