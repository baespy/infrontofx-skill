"""Pure-Python GTA V ClipDictionary (.ycd, RSC7 v46) compiler & decompiler.

Converts between CodeWalker/Sollumz `.ycd.xml` and native binary `.ycd` (RSC7 v46)
matching CodeWalker's `ClipDictionary` / `Animation` / `Sequence` / `ClipAnimation`
binary layout so props exported by `prop-forge` stream natively in FiveM without
requiring CodeWalker GUI.
"""

from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

RSC7_MAGIC = b"RSC7"
YCD_VERSION = 46
SYS_VBASE = 0x50000000
GFX_VBASE = 0x60000000

CHAN_STATIC_QUAT = 0
CHAN_STATIC_VEC3 = 1
CHAN_STATIC_FLOAT = 2
CHAN_RAW_FLOAT = 3
CHAN_QUANTIZE_FLOAT = 4
CHAN_INDIRECT_QUANTIZE_FLOAT = 5
CHAN_LINEAR_FLOAT = 6
CHAN_CACHED_QUAT_1 = 7
CHAN_CACHED_QUAT_2 = 8

CHAN_NAME_TO_ID = {
    "StaticQuaternion": CHAN_STATIC_QUAT,
    "StaticVector3": CHAN_STATIC_VEC3,
    "StaticFloat": CHAN_STATIC_FLOAT,
    "RawFloat": CHAN_RAW_FLOAT,
    "QuantizeFloat": CHAN_QUANTIZE_FLOAT,
    "IndirectQuantizeFloat": CHAN_INDIRECT_QUANTIZE_FLOAT,
    "LinearFloat": CHAN_LINEAR_FLOAT,
    "CachedQuaternion1": CHAN_CACHED_QUAT_1,
    "CachedQuaternion2": CHAN_CACHED_QUAT_2,
}
CHAN_ID_TO_NAME = {v: k for k, v in CHAN_NAME_TO_ID.items()}

HASH_BUCKET_PRIMES = [
    (11, 11), (29, 29), (59, 59), (107, 107), (191, 191), (331, 331),
    (563, 563), (953, 953), (1609, 1609), (2729, 2729), (4621, 4621),
    (7841, 7841), (13297, 13297), (22571, 22571), (38351, 38351),
    (65167, 65167),
]


def joaat(text: str) -> int:
    h = 0
    for b in text.lower().encode("ascii"):
        h = (h + b) & 0xFFFFFFFF
        h = (h + ((h << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + ((h << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return h


def parse_hash(text: str | None) -> int:
    if not text:
        return 0
    s = text.strip()
    if not s:
        return 0
    if s.lower().startswith("hash_"):
        return int(s[5:], 16) & 0xFFFFFFFF
    if s.lower().startswith("0x"):
        return int(s[2:], 16) & 0xFFFFFFFF
    return joaat(s)


def format_hash(h: int) -> str:
    return f"hash_{h & 0xFFFFFFFF:08X}"


def num_hash_buckets(n: int) -> int:
    for limit, buckets in HASH_BUCKET_PRIMES:
        if n < limit:
            return buckets
    return 65521


def bit_count_u32(val: int) -> int:
    return int(val & 0xFFFFFFFF).bit_length()


# ---------------------------------------------------------------------------
# RSC7 Block Allocator / Serializer
# ---------------------------------------------------------------------------

class RscNode:
    __slots__ = ("kind", "data", "refs", "offset")

    def __init__(self, kind: str, data: bytearray):
        self.kind = kind
        self.data = data
        self.refs: list[tuple[int, RscNode, int]] = []
        self.offset = 0

    def add_ref(self, at: int, target: "RscNode | None", add: int = 0):
        if target is not None:
            self.refs.append((at, target, add))


def _collect_reachable(root: RscNode) -> list[RscNode]:
    order: list[RscNode] = []
    seen: set[int] = set()
    stack = [root]
    seen.add(id(root))
    while stack:
        node = stack.pop()
        order.append(node)
        for _, target, _ in reversed(node.refs):
            if target is not None and id(target) not in seen:
                seen.add(id(target))
                stack.append(target)
    return order


def _layout_pages(nodes: list[RscNode], min_page: int = 0x2000) -> tuple[int, int, int]:
    if not nodes:
        return 0, 0, 0
    page = min_page
    for n in nodes:
        sz = len(n.data) + (0x1010 if n.kind == "PageMap" else 0)
        while page < sz:
            page *= 2
    while True:
        pos = 0
        for n in nodes:
            size = (len(n.data) + 15) & ~15
            if n.kind == "PageMap":
                size += 0x1010
            if size == 0:
                size = 16
            room = page - (pos % page)
            if size > room:
                pos += room
            n.offset = pos
            pos += size
        count = (pos + page - 1) // page
        if count <= 127:
            base_size = page >> 4
            shift = 0
            while (0x200 << shift) < base_size:
                shift += 1
            flags = (shift & 0xF) | ((count & 0x7F) << 17)
            return count * page, flags, count
        page *= 2


def pack_rsc7(root: RscNode, version: int = YCD_VERSION) -> bytes:
    nodes = _collect_reachable(root)
    sys_size, sf, sys_pages = _layout_pages(nodes, min_page=0x2000)
    sys_flags = sf | (((version >> 4) & 0xF) << 28)
    gfx_flags = ((version & 0xF) << 28)

    buf = bytearray(sys_size)
    for n in nodes:
        chunk = bytearray(n.data)
        for at, target, add in n.refs:
            ptr = SYS_VBASE + target.offset + add
            struct.pack_into("<Q", chunk, at, ptr)
        if n.kind == "PageMap":
            chunk[8] = sys_pages & 0xFF
            chunk[9] = 0
        buf[n.offset:n.offset + len(chunk)] = chunk

    comp = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    payload = comp.compress(bytes(buf)) + comp.flush()
    header = struct.pack("<4sIII", RSC7_MAGIC, version, sys_flags, gfx_flags)
    return header + payload


def unpack_rsc7(raw: bytes) -> tuple[int, bytes]:
    if len(raw) < 16 or raw[:4] != RSC7_MAGIC:
        raise ValueError("Not an RSC7 file")
    _, version, sys_flags, _ = struct.unpack_from("<4sIII", raw, 0)
    data = zlib.decompress(raw[16:], -15)
    return version, data


# ---------------------------------------------------------------------------
# Sequence Channel Bitstream Reader / Writer (matches CodeWalker Clip.cs)
# ---------------------------------------------------------------------------

def _write_to_bitstream(stream: list[int], offset: int, bits: int, n: int):
    if n <= 0:
        return
    mask = (1 << n) - 1
    bits &= mask
    soff = offset % 32
    sidx = offset // 32
    while sidx >= len(stream):
        stream.append(0)
    stream[sidx] = (stream[sidx] | ((bits << soff) & 0xFFFFFFFF)) & 0xFFFFFFFF
    endbit = (soff + n) - 32
    if endbit > 0:
        eidx = sidx + 1
        while eidx >= len(stream):
            stream.append(0)
        eoff = 32 - soff
        stream[eidx] = (stream[eidx] | ((bits >> eoff) & 0xFFFFFFFF)) & 0xFFFFFFFF


def _get_bits(data: bytes, start_bit: int, length: int) -> int:
    if start_bit < 0 or length <= 0:
        return 0
    start_byte = start_bit // 8
    bit_off = start_bit % 8
    result = 0
    shift = -bit_off
    cur_byte = start_byte
    rem = length
    nbytes = len(data)
    while rem > 0:
        b = data[cur_byte] if cur_byte < nbytes else 0
        cur_byte += 1
        sb = (b >> -shift) if shift < 0 else (b << shift)
        bm = ((1 << min(rem, 8)) - 1) << max(shift, 0)
        result |= (sb & bm)
        rem -= (8 + min(shift, 0))
        shift += 8
    return result & 0xFFFFFFFF


def _quanta(val: float, offset: float, quantum: float) -> int:
    if quantum == 0.0:
        return 0
    q = (val - offset) / quantum
    if q < 0.0:
        q = 0.0
    return int(q + 0.5)


def build_sequence_blob(seq_dict: dict) -> tuple[bytes, dict]:
    """Pack one Sequence dict into binary Data blob + header fields."""
    num_frames = int(seq_dict["frame_count"])
    seq_list = seq_dict["sequence_data"]
    num_seqs = len(seq_list)

    channel_lists: list[list[dict]] = [[] for _ in range(9)]
    for s_idx, s_item in enumerate(seq_list):
        for c_idx, ch in enumerate(s_item["channels"]):
            ctype = ch["type_id"]
            if 0 <= ctype < 9:
                ch_copy = dict(ch)
                ch_copy["sequence"] = s_idx
                if ctype in (CHAN_CACHED_QUAT_1, CHAN_CACHED_QUAT_2):
                    ch_copy["index"] = int(ch.get("quat_index", 0))
                else:
                    ch_copy["index"] = c_idx
                channel_lists[ctype].append(ch_copy)

    main_buf = bytearray()
    chan_list_buf = bytearray()
    chan_item_buf = bytearray()
    quant_bits_total = 0
    indirect_ints_total = 0

    for ctype in range(9):
        clist = channel_lists[ctype]
        ccount = len(clist)
        chan_list_buf += struct.pack("<H", ccount)
        for ch in clist:
            data_bit = ((ch["index"] & 3) | ((ch["sequence"] & 0x3FFF) << 2)) & 0xFFFF
            chan_item_buf += struct.pack("<H", data_bit)
            ch["data_offset"] = len(main_buf) // 4

            if ctype == CHAN_STATIC_QUAT:
                qx, qy, qz, qw = ch["value"]
                if qw < 0.0:
                    qx, qy, qz, qw = -qx, -qy, -qz, -qw
                main_buf += struct.pack("<3f", qx, qy, qz)
                ch["frame_bits"] = 0
            elif ctype == CHAN_STATIC_VEC3:
                vx, vy, vz = ch["value"]
                main_buf += struct.pack("<3f", vx, vy, vz)
                ch["frame_bits"] = 0
            elif ctype == CHAN_STATIC_FLOAT:
                main_buf += struct.pack("<f", ch["value"])
                ch["frame_bits"] = 0
            elif ctype == CHAN_RAW_FLOAT:
                ch["frame_bits"] = 32
            elif ctype == CHAN_QUANTIZE_FLOAT:
                vals = ch["values"]
                off = float(ch["offset"])
                qtm = float(ch["quantum"])
                qlist = [_quanta(v, off, qtm) for v in vals]
                max_q = max(qlist) if qlist else 0
                vbits = max(bit_count_u32(max_q), 1)
                ch["value_bits"] = vbits
                ch["qlist"] = qlist
                ch["frame_bits"] = vbits
                quant_bits_total += vbits
                main_buf += struct.pack("<iff", vbits, qtm, off)
            elif ctype == CHAN_INDIRECT_QUANTIZE_FLOAT:
                vals = ch["values"]
                frames = ch["frames"]
                off = float(ch["offset"])
                qtm = float(ch["quantum"])
                fbits = max(bit_count_u32(len(vals)), 2)
                qlist = [_quanta(v, off, qtm) for v in vals]
                max_q = max(qlist) if qlist else 0
                vbits = max(bit_count_u32(max_q), 3)
                bs: list[int] = []
                bpos = 0
                for qv in qlist:
                    _write_to_bitstream(bs, bpos, qv, vbits)
                    bpos += vbits
                num_ints = len(bs)
                ch["frame_bits"] = fbits
                ch["value_bits"] = vbits
                ch["num_ints"] = num_ints
                indirect_ints_total += num_ints + 5
                main_buf += struct.pack("<iiiff", fbits, vbits, num_ints, qtm, off)
                for w in bs:
                    main_buf += struct.pack("<I", w)
            elif ctype in (CHAN_CACHED_QUAT_1, CHAN_CACHED_QUAT_2):
                ch["frame_bits"] = 0
            else:
                raise ValueError(f"Unsupported channel type {ctype} in compiler")

        rem = ccount % 4
        if rem > 0:
            pad_val = (num_seqs << 2) & 0xFFFF
            for _ in range(4 - rem):
                chan_item_buf += struct.pack("<H", pad_val)

    # Frame bitstreams
    frame_words_list: list[list[int]] = []
    frame_length = 0
    for f in range(num_frames):
        fwords: list[int] = []
        foff = 0
        for ctype in range(9):
            for ch in channel_lists[ctype]:
                if ctype == CHAN_RAW_FLOAT:
                    v = ch["values"][f]
                    bits = struct.unpack("<I", struct.pack("<f", v))[0]
                    _write_to_bitstream(fwords, foff, bits, 32)
                    foff += 32
                elif ctype == CHAN_QUANTIZE_FLOAT:
                    q = ch["qlist"][f]
                    _write_to_bitstream(fwords, foff, q, ch["value_bits"])
                    foff += ch["value_bits"]
                elif ctype == CHAN_INDIRECT_QUANTIZE_FLOAT:
                    idx = int(ch["frames"][f])
                    _write_to_bitstream(fwords, foff, idx, ch["frame_bits"])
                    foff += ch["frame_bits"]
        frame_length = max(frame_length, len(fwords) * 4)
        frame_words_list.append(fwords)

    frame_buf = bytearray()
    frame_u32_count = frame_length // 4
    for fwords in frame_words_list:
        for i in range(frame_u32_count):
            frame_buf += struct.pack("<I", fwords[i] if i < len(fwords) else 0)

    data = bytes(main_buf + frame_buf + chan_list_buf + chan_item_buf)
    meta = {
        "hash": seq_dict["hash"],
        "data_length": len(data),
        "frame_offset": len(main_buf),
        "root_motion_refs_offset": 32 + len(data),
        "num_frames": num_frames,
        "frame_length": frame_length,
        "indirect_quant_ints": indirect_ints_total,
        "quant_value_bits": quant_bits_total,
        "chunk_size": 255,
        "root_motion_ref_counts": 0,
    }
    return data, meta


def parse_sequence_blob(raw_block: bytes, bone_ids: list[tuple[int, int, int]]) -> dict:
    """Parse one Sequence block (header + Data) back into structured dict."""
    (
        seq_hash,
        data_len,
        _u08,
        frame_offset,
        _rm_offset,
        _u14,
        num_frames,
        frame_length,
        _iq_ints,
        _q_bits,
        chunk_size,
        rm_counts,
    ) = struct.unpack_from("<IIIIIHHHHHBB", raw_block, 0)
    data = raw_block[32:32 + data_len]

    pos = 0
    chan_list_off = frame_offset + (frame_length * num_frames)
    chan_data_off = chan_list_off + (9 * 2)

    all_items: list[tuple[int, int, dict]] = []
    chan_lists: list[list[dict]] = []

    for ctype in range(9):
        ccount = struct.unpack_from("<H", data, chan_list_off)[0]
        chan_list_off += 2
        clist: list[dict] = []
        for _ in range(ccount):
            dbit = struct.unpack_from("<H", data, chan_data_off)[0]
            chan_data_off += 2
            seq_idx = dbit >> 2
            idx = dbit & 3
            ch: dict = {"type_id": ctype, "type": CHAN_ID_TO_NAME[ctype]}

            if ctype == CHAN_STATIC_QUAT:
                vx, vy, vz = struct.unpack_from("<3f", data, pos)
                pos += 12
                w = math.sqrt(max(1.0 - (vx * vx + vy * vy + vz * vz), 0.0))
                ch["value"] = (vx, vy, vz, w)
            elif ctype == CHAN_STATIC_VEC3:
                ch["value"] = struct.unpack_from("<3f", data, pos)
                pos += 12
            elif ctype == CHAN_STATIC_FLOAT:
                ch["value"] = struct.unpack_from("<f", data, pos)[0]
                pos += 4
            elif ctype == CHAN_RAW_FLOAT:
                ch["values"] = [0.0] * num_frames
            elif ctype == CHAN_QUANTIZE_FLOAT:
                vbits, qtm, off = struct.unpack_from("<iff", data, pos)
                pos += 12
                ch["value_bits"] = vbits
                ch["quantum"] = qtm
                ch["offset"] = off
                ch["values"] = [0.0] * num_frames
            elif ctype == CHAN_INDIRECT_QUANTIZE_FLOAT:
                fbits, vbits, nints, qtm, off = struct.unpack_from("<iiiff", data, pos)
                pos += 20
                nvals = min((nints * 32) // vbits, (1 << fbits) - 1) if vbits > 0 else 0
                bpos = pos * 8
                vals = []
                for _ in range(nvals):
                    b = _get_bits(data, bpos, vbits)
                    bpos += vbits
                    vals.append(b * qtm + off)
                pos += nints * 4
                ch["frame_bits"] = fbits
                ch["value_bits"] = vbits
                ch["quantum"] = qtm
                ch["offset"] = off
                ch["values"] = vals
                ch["frames"] = [0] * num_frames
            elif ctype == CHAN_LINEAR_FLOAT:
                # LinearFloat (chunked) fallback reader
                vbits, qtm, off = struct.unpack_from("<iff", data, pos)
                pos += 12
                ch["value_bits"] = vbits
                ch["quantum"] = qtm
                ch["offset"] = off
                ch["values"] = [0.0] * num_frames
                # Skip remaining LinearFloat header if present
                num_chunks = (num_frames + max(chunk_size, 1) - 1) // max(chunk_size, 1)
                pos += num_chunks * 4
            elif ctype in (CHAN_CACHED_QUAT_1, CHAN_CACHED_QUAT_2):
                ch["quat_index"] = idx
                idx = 3 if ctype == CHAN_CACHED_QUAT_1 else 4

            clist.append(ch)
            all_items.append((seq_idx, idx, ch))

        rem = ccount % 4
        if rem > 0:
            chan_data_off += (4 - rem) * 2
        chan_lists.append(clist)

    # Read frame bitstreams
    for f in range(num_frames):
        bit_off = (frame_offset + frame_length * f) * 8
        for ctype in range(9):
            for ch in chan_lists[ctype]:
                if ctype == CHAN_RAW_FLOAT:
                    bits = _get_bits(data, bit_off, 32)
                    bit_off += 32
                    ch["values"][f] = struct.unpack("<f", struct.pack("<I", bits))[0]
                elif ctype == CHAN_QUANTIZE_FLOAT:
                    vb = ch["value_bits"]
                    bits = _get_bits(data, bit_off, vb)
                    bit_off += vb
                    ch["values"][f] = bits * ch["quantum"] + ch["offset"]
                elif ctype == CHAN_INDIRECT_QUANTIZE_FLOAT:
                    fb = ch["frame_bits"]
                    bits = _get_bits(data, bit_off, fb)
                    bit_off += fb
                    ch["frames"][f] = bits

    max_seq = max((s for s, _, _ in all_items), default=-1) + 1
    seq_data = []
    for s_idx in range(max_seq):
        items = [(idx, ch) for s, idx, ch in all_items if s == s_idx]
        if not items:
            seq_data.append({"channels": []})
            continue
        max_c = max(idx for idx, _ in items) + 1
        ch_arr: list[dict | None] = [None] * max_c
        for idx, ch in items:
            ch_arr[idx] = ch
        seq_data.append({"channels": [c for c in ch_arr if c is not None]})

    return {
        "hash": seq_hash,
        "frame_count": num_frames,
        "sequence_data": seq_data,
    }


# ---------------------------------------------------------------------------
# XML <-> Dict Conversion (CodeWalker / Sollumz `.ycd.xml`)
# ---------------------------------------------------------------------------

def _child_text(el: ET.Element, tag: str, default: str = "") -> str:
    c = el.find(tag)
    return (c.text or "").strip() if c is not None else default


def _child_attr(el: ET.Element, tag: str, attr: str = "value", default: str = "0") -> str:
    c = el.find(tag)
    return c.attrib.get(attr, default) if c is not None else default


def parse_ycd_xml(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    clips = []
    clips_el = root.find("Clips")
    if clips_el is not None:
        for item in clips_el.findall("Item"):
            ctype = _child_attr(item, "Type", "value", "Animation")
            clip = {
                "hash_str": _child_text(item, "Hash"),
                "hash": parse_hash(_child_text(item, "Hash")),
                "name": _child_text(item, "Name"),
                "type": ctype,
                "unknown30": int(_child_attr(item, "Unknown30", "value", "0")),
            }
            if ctype == "Animation":
                clip["animation_hash"] = parse_hash(_child_text(item, "AnimationHash"))
                clip["start_time"] = float(_child_attr(item, "StartTime", "value", "0"))
                clip["end_time"] = float(_child_attr(item, "EndTime", "value", "0"))
                clip["rate"] = float(_child_attr(item, "Rate", "value", "1"))
            elif ctype == "AnimationList":
                clip["duration"] = float(_child_attr(item, "Duration", "value", "0"))
                entries = []
                anims_el = item.find("Animations")
                if anims_el is not None:
                    for ae in anims_el.findall("Item"):
                        entries.append({
                            "animation_hash": parse_hash(_child_text(ae, "AnimationHash")),
                            "start_time": float(_child_attr(ae, "StartTime", "value", "0")),
                            "end_time": float(_child_attr(ae, "EndTime", "value", "0")),
                            "rate": float(_child_attr(ae, "Rate", "value", "1")),
                        })
                clip["animations"] = entries
            clips.append(clip)

    animations = []
    anims_el = root.find("Animations")
    if anims_el is not None:
        for item in anims_el.findall("Item"):
            bone_ids = []
            bids_el = item.find("BoneIds")
            if bids_el is not None:
                for bi in bids_el.findall("Item"):
                    bone_ids.append((
                        int(_child_attr(bi, "BoneId", "value", "0")),
                        int(_child_attr(bi, "Track", "value", "0")),
                        int(_child_attr(bi, "Unk0", "value", "0")),
                    ))

            seqs = []
            seqs_el = item.find("Sequences")
            if seqs_el is not None:
                for sq in seqs_el.findall("Item"):
                    sdata = []
                    sd_el = sq.find("SequenceData")
                    if sd_el is not None:
                        for sitem in sd_el.findall("Item"):
                            chans = []
                            ch_el = sitem.find("Channels")
                            if ch_el is not None:
                                for citem in ch_el.findall("Item"):
                                    tname = _child_attr(citem, "Type", "value")
                                    tid = CHAN_NAME_TO_ID[tname]
                                    cd: dict = {"type": tname, "type_id": tid}
                                    if tid == CHAN_STATIC_QUAT:
                                        v = citem.find("Value")
                                        cd["value"] = (
                                            float(v.attrib["x"]),
                                            float(v.attrib["y"]),
                                            float(v.attrib["z"]),
                                            float(v.attrib["w"]),
                                        )
                                    elif tid == CHAN_STATIC_VEC3:
                                        v = citem.find("Value")
                                        cd["value"] = (
                                            float(v.attrib["x"]),
                                            float(v.attrib["y"]),
                                            float(v.attrib["z"]),
                                        )
                                    elif tid == CHAN_STATIC_FLOAT:
                                        cd["value"] = float(_child_attr(citem, "Value", "value", "0"))
                                    elif tid == CHAN_RAW_FLOAT:
                                        cd["values"] = [float(x) for x in _child_text(citem, "Values").split()]
                                    elif tid == CHAN_QUANTIZE_FLOAT:
                                        cd["quantum"] = float(_child_attr(citem, "Quantum", "value", "0"))
                                        cd["offset"] = float(_child_attr(citem, "Offset", "value", "0"))
                                        cd["values"] = [float(x) for x in _child_text(citem, "Values").split()]
                                    elif tid == CHAN_INDIRECT_QUANTIZE_FLOAT:
                                        cd["quantum"] = float(_child_attr(citem, "Quantum", "value", "0"))
                                        cd["offset"] = float(_child_attr(citem, "Offset", "value", "0"))
                                        cd["values"] = [float(x) for x in _child_text(citem, "Values").split()]
                                        cd["frames"] = [int(x) for x in _child_text(citem, "Frames").split()]
                                    elif tid in (CHAN_CACHED_QUAT_1, CHAN_CACHED_QUAT_2):
                                        cd["quat_index"] = int(_child_attr(citem, "QuatIndex", "value", "0"))
                                    chans.append(cd)
                            sdata.append({"channels": chans})
                    seqs.append({
                        "hash": parse_hash(_child_text(sq, "Hash")),
                        "frame_count": int(_child_attr(sq, "FrameCount", "value", "0")),
                        "sequence_data": sdata,
                    })

            animations.append({
                "hash_str": _child_text(item, "Hash"),
                "hash": parse_hash(_child_text(item, "Hash")),
                "unknown10": int(_child_attr(item, "Unknown10", "value", "0")),
                "frame_count": int(_child_attr(item, "FrameCount", "value", "0")),
                "sequence_frame_limit": int(_child_attr(item, "SequenceFrameLimit", "value", "0")),
                "duration": float(_child_attr(item, "Duration", "value", "0")),
                "unknown1c": parse_hash(_child_text(item, "Unknown1C")),
                "bone_ids": bone_ids,
                "sequences": seqs,
            })

    return {"clips": clips, "animations": animations}


# ---------------------------------------------------------------------------
# Build Binary ClipDictionary RSC7 v46
# ---------------------------------------------------------------------------

def compile_ycd_dict_to_bytes(ycd: dict) -> bytes:
    """Compile parsed ClipDictionary dict into binary RSC7 v46 `.ycd` bytes."""
    clips = ycd["clips"]
    anims = ycd["animations"]

    # Usage counts: 1 for being in AnimMap + 1 per Clip reference
    usage: dict[int, int] = {}
    for a in anims:
        usage[a["hash"]] = usage.get(a["hash"], 0) + 1
    for c in clips:
        if c["type"] == "Animation":
            ah = c["animation_hash"]
            usage[ah] = usage.get(ah, 0) + 1
        elif c["type"] == "AnimationList":
            for ae in c.get("animations", []):
                ah = ae["animation_hash"]
                usage[ah] = usage.get(ah, 0) + 1

    # 1. Build Animation nodes
    anim_nodes_by_hash: dict[int, RscNode] = {}
    anim_map_entries: list[tuple[int, RscNode]] = []
    for a in anims:
        seq_nodes: list[RscNode] = []
        max_seq_len = 0
        for sq in a["sequences"]:
            blob, meta = build_sequence_blob(sq)
            sblock = bytearray(32 + len(blob))
            struct.pack_into(
                "<IIIIIHHHHHBB",
                sblock,
                0,
                meta["hash"] & 0xFFFFFFFF,
                meta["data_length"],
                0,
                meta["frame_offset"],
                meta["root_motion_refs_offset"],
                0,
                meta["num_frames"],
                meta["frame_length"],
                meta["indirect_quant_ints"],
                meta["quant_value_bits"],
                meta["chunk_size"],
                meta["root_motion_ref_counts"],
            )
            sblock[32:] = blob
            max_seq_len = max(max_seq_len, len(sblock))
            seq_nodes.append(RscNode("Sequence", sblock))

        seq_ptr_arr = RscNode("SequencePtrArray", bytearray(len(seq_nodes) * 8))
        for i, sn in enumerate(seq_nodes):
            seq_ptr_arr.add_ref(i * 8, sn)

        bids = a["bone_ids"]
        bids_buf = bytearray(len(bids) * 4)
        for i, (bid, trk, unk0) in enumerate(bids):
            struct.pack_into("<HBB", bids_buf, i * 4, bid & 0xFFFF, unk0 & 0xFF, trk & 0xFF)
        bids_node = RscNode("BoneIds", bids_buf)

        # Animation block (96 bytes = 0x60)
        abuf = bytearray(96)
        struct.pack_into("<IIII", abuf, 0x00, 0, 1, 0, 0)
        struct.pack_into("<BBHHH", abuf, 0x10, a["unknown10"] & 0xFF, 1, 0, a["frame_count"] & 0xFFFF, a["sequence_frame_limit"] & 0xFFFF)
        struct.pack_into("<fI", abuf, 0x18, float(a["duration"]), a["unknown1c"] & 0xFFFFFFFF)
        struct.pack_into("<II", abuf, 0x38, max_seq_len, usage.get(a["hash"], 1))
        # 0x40: ResourcePointerList64<Sequence> -> ptr(8), count(2), cap(2), pad(4)
        struct.pack_into("<HH", abuf, 0x48, len(seq_nodes), len(seq_nodes))
        # 0x50: ResourceSimpleList64_s<AnimationBoneId> -> ptr(8), count(2), cap(2), pad(4)
        struct.pack_into("<HH", abuf, 0x58, len(bids), len(bids))

        anode = RscNode("Animation", abuf)
        if seq_nodes:
            anode.add_ref(0x40, seq_ptr_arr)
        if bids:
            anode.add_ref(0x50, bids_node)

        anim_nodes_by_hash[a["hash"]] = anode
        anim_map_entries.append((a["hash"], anode))

    # 2. Build AnimationMap (48 bytes) + hash table
    n_abuckets = num_hash_buckets(len(anim_map_entries))
    abuckets: list[list[RscNode]] = [[] for _ in range(n_abuckets)]
    for h, anode in anim_map_entries:
        ebuf = bytearray(32)
        struct.pack_into("<I", ebuf, 0x00, h & 0xFFFFFFFF)
        enode = RscNode("AnimationMapEntry", ebuf)
        enode.add_ref(0x08, anode)
        abuckets[h % n_abuckets].append(enode)

    amap_ptrs = RscNode("AnimMapPtrs", bytearray(n_abuckets * 8))
    for b_idx, bucket in enumerate(abuckets):
        if bucket:
            amap_ptrs.add_ref(b_idx * 8, bucket[0])
            for i in range(len(bucket) - 1):
                bucket[i].add_ref(0x10, bucket[i + 1])

    amap_buf = bytearray(48)
    struct.pack_into("<II", amap_buf, 0x00, 0, 1)
    struct.pack_into("<HHII", amap_buf, 0x20, n_abuckets, len(anim_map_entries), 0x01000000, 1)
    amap_node = RscNode("AnimationMap", amap_buf)
    amap_node.add_ref(0x18, amap_ptrs)

    # 3. Build ClipBase / ClipAnimation / ClipAnimationList nodes + ClipMap
    n_cbuckets = num_hash_buckets(len(clips))
    cbuckets: list[list[RscNode]] = [[] for _ in range(n_cbuckets)]
    for c in clips:
        name_bytes = c["name"].encode("ascii") + b"\x00"
        name_node = RscNode("ClipName", bytearray(name_bytes))

        # Empty ClipTagList (32 bytes, all zeros)
        tags_node = RscNode("ClipTagList", bytearray(32))

        # Empty ClipPropertyMap (16 bytes + 11-slot empty pointer array)
        pmap_slots = num_hash_buckets(0)
        pmap_ptrs = RscNode("ClipPropPtrs", bytearray(pmap_slots * 8))
        pmap_buf = bytearray(16)
        struct.pack_into("<HHI", pmap_buf, 0x08, pmap_slots, 0, 0x01000000)
        pmap_node = RscNode("ClipPropertyMap", pmap_buf)
        pmap_node.add_ref(0x00, pmap_ptrs)

        # ClipBase header (0x00..0x50) + subclass fields (0x50..0x70) = 112 bytes
        cbuf = bytearray(112)
        ctype_int = 1 if c["type"] == "Animation" else 2
        struct.pack_into("<IIIIII", cbuf, 0x00, 0, 1, 0, 0, ctype_int, 0)
        struct.pack_into("<HHI", cbuf, 0x20, len(c["name"]), len(c["name"]) + 1, 0)
        struct.pack_into("<QII", cbuf, 0x28, SYS_VBASE, c["unknown30"] & 0xFFFFFFFF, 0)
        struct.pack_into("<II", cbuf, 0x48, 1, 0)

        cnode = RscNode("Clip", cbuf)
        cnode.add_ref(0x18, name_node)
        cnode.add_ref(0x38, tags_node)
        cnode.add_ref(0x40, pmap_node)

        if ctype_int == 1:
            target_anim = anim_nodes_by_hash.get(c["animation_hash"])
            cnode.add_ref(0x50, target_anim)
            struct.pack_into("<fff", cbuf, 0x58, float(c["start_time"]), float(c["end_time"]), float(c["rate"]))
        else:
            alist = c.get("animations", [])
            arr_buf = bytearray(len(alist) * 24)
            arr_node = RscNode("ClipAnimationsArray", arr_buf)
            for idx, ae in enumerate(alist):
                struct.pack_into("<fffI", arr_buf, idx * 24, float(ae["start_time"]), float(ae["end_time"]), float(ae["rate"]), 0)
                arr_node.add_ref(idx * 24 + 16, anim_nodes_by_hash.get(ae["animation_hash"]))
            if alist:
                cnode.add_ref(0x50, arr_node)
            struct.pack_into("<HHIfI", cbuf, 0x58, len(alist), len(alist), 0, float(c["duration"]), 1)

        # ClipMapEntry (32 bytes)
        ebuf = bytearray(32)
        struct.pack_into("<I", ebuf, 0x00, c["hash"] & 0xFFFFFFFF)
        enode = RscNode("ClipMapEntry", ebuf)
        enode.add_ref(0x08, cnode)
        cbuckets[c["hash"] % n_cbuckets].append(enode)

    cmap_ptrs = RscNode("ClipMapPtrs", bytearray(n_cbuckets * 8))
    for b_idx, bucket in enumerate(cbuckets):
        if bucket:
            cmap_ptrs.add_ref(b_idx * 8, bucket[0])
            for i in range(len(bucket) - 1):
                bucket[i].add_ref(0x10, bucket[i + 1])

    # 4. Root ClipDictionary (64 bytes) + PageMap (16 bytes)
    pagemap_node = RscNode("PageMap", bytearray(16))

    root_buf = bytearray(64)
    struct.pack_into("<II", root_buf, 0x00, 0, 1)
    struct.pack_into("<II", root_buf, 0x20, 0x00000101, 0)
    struct.pack_into("<HHI", root_buf, 0x30, n_cbuckets, len(clips), 0x01000000)
    root_node = RscNode("ClipDictionary", root_buf)
    root_node.add_ref(0x08, pagemap_node)
    root_node.add_ref(0x18, amap_node)
    root_node.add_ref(0x28, cmap_ptrs)

    return pack_rsc7(root_node, version=YCD_VERSION)


def compile_ycd_xml_to_binary(xml_path: Path | str, out_ycd_path: Path | str) -> Path:
    ycd = parse_ycd_xml(Path(xml_path))
    data = compile_ycd_dict_to_bytes(ycd)
    out = Path(out_ycd_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


# ---------------------------------------------------------------------------
# Binary `.ycd` -> Dict & `.ycd.xml` Decompiler (for verification/round-trip)
# ---------------------------------------------------------------------------

def _voff(ptr: int) -> int:
    return ptr - SYS_VBASE if SYS_VBASE <= ptr < GFX_VBASE else -1


def _read_cstr(buf: bytes, off: int) -> str:
    end = buf.find(b"\x00", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("ascii", errors="replace")


def parse_ycd_binary(ycd_path: Path | str) -> dict:
    version, data = unpack_rsc7(Path(ycd_path).read_bytes())
    if version != YCD_VERSION:
        raise ValueError(f"Unexpected YCD RSC7 version {version}")

    anim_map_ptr = struct.unpack_from("<Q", data, 0x18)[0]
    clips_ptr, clips_cap, _clips_cnt = struct.unpack_from("<QHH", data, 0x28)

    # Read Animations
    animations: list[dict] = []
    anim_off_to_hash: dict[int, int] = {}
    am_off = _voff(anim_map_ptr)
    if am_off >= 0:
        aptrs_p, acap, _acnt = struct.unpack_from("<QHH", data, am_off + 0x18)
        aptrs_off = _voff(aptrs_p)
        if aptrs_off >= 0:
            for i in range(acap):
                eptr = struct.unpack_from("<Q", data, aptrs_off + i * 8)[0]
                while eptr:
                    eoff = _voff(eptr)
                    ahash, _, aptr, next_p = struct.unpack_from("<IIQQ", data, eoff)
                    aoff = _voff(aptr)
                    if aoff >= 0:
                        anim_off_to_hash[aoff] = ahash
                        u10, _u11, _u12, frames, seq_lim = struct.unpack_from("<BBHHH", data, aoff + 0x10)
                        dur, u1c = struct.unpack_from("<fI", data, aoff + 0x18)
                        slist_p, scnt, _scap = struct.unpack_from("<QHH", data, aoff + 0x40)
                        blist_p, bcnt, _bcap = struct.unpack_from("<QHH", data, aoff + 0x50)

                        bone_ids = []
                        boff = _voff(blist_p)
                        if boff >= 0:
                            for bi in range(bcnt):
                                bid, unk0, trk = struct.unpack_from("<HBB", data, boff + bi * 4)
                                bone_ids.append((bid, trk, unk0))

                        seqs = []
                        soff = _voff(slist_p)
                        if soff >= 0:
                            for si in range(scnt):
                                sp = struct.unpack_from("<Q", data, soff + si * 8)[0]
                                sqoff = _voff(sp)
                                if sqoff >= 0:
                                    dlen = struct.unpack_from("<I", data, sqoff + 4)[0]
                                    seqs.append(parse_sequence_blob(data[sqoff:sqoff + 32 + dlen], bone_ids))

                        animations.append({
                            "hash": ahash,
                            "unknown10": u10,
                            "frame_count": frames,
                            "sequence_frame_limit": seq_lim,
                            "duration": dur,
                            "unknown1c": u1c,
                            "bone_ids": bone_ids,
                            "sequences": seqs,
                        })
                    eptr = next_p

    # Read Clips
    clips: list[dict] = []
    coff_arr = _voff(clips_ptr)
    if coff_arr >= 0:
        for i in range(clips_cap):
            eptr = struct.unpack_from("<Q", data, coff_arr + i * 8)[0]
            while eptr:
                eoff = _voff(eptr)
                chash, _, cptr, next_p = struct.unpack_from("<IIQQ", data, eoff)
                coff = _voff(cptr)
                if coff >= 0:
                    ctype = struct.unpack_from("<I", data, coff + 0x10)[0]
                    nptr = struct.unpack_from("<Q", data, coff + 0x18)[0]
                    u30 = struct.unpack_from("<I", data, coff + 0x30)[0]
                    cname = _read_cstr(data, _voff(nptr)) if _voff(nptr) >= 0 else ""
                    clip: dict = {
                        "hash": chash,
                        "name": cname,
                        "type": "Animation" if ctype == 1 else "AnimationList",
                        "unknown30": u30,
                    }
                    if ctype == 1:
                        aptr, st, et, rate = struct.unpack_from("<Qfff", data, coff + 0x50)
                        clip["animation_hash"] = anim_off_to_hash.get(_voff(aptr), 0)
                        clip["start_time"] = st
                        clip["end_time"] = et
                        clip["rate"] = rate
                    else:
                        aptr, cnt, _, _, dur = struct.unpack_from("<QHHIf", data, coff + 0x50)
                        clip["duration"] = dur
                        entries = []
                        aoff = _voff(aptr)
                        if aoff >= 0:
                            for ai in range(cnt):
                                st, et, rate, _, anp = struct.unpack_from("<fffIQ", data, aoff + ai * 24)
                                entries.append({
                                    "animation_hash": anim_off_to_hash.get(_voff(anp), 0),
                                    "start_time": st,
                                    "end_time": et,
                                    "rate": rate,
                                })
                        clip["animations"] = entries
                    clips.append(clip)
                eptr = next_p

    return {"clips": clips, "animations": animations}


def write_ycd_xml(ycd: dict, out_xml_path: Path | str) -> Path:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ClipDictionary>"]
    lines.append(" <Clips>")
    for c in ycd["clips"]:
        lines.append("  <Item>")
        lines.append(f"   <Hash>{format_hash(c['hash'])}</Hash>")
        lines.append(f"   <Name>{c['name']}</Name>")
        lines.append(f"   <Type value=\"{c['type']}\" />")
        lines.append(f"   <Unknown30 value=\"{c['unknown30']}\" />")
        lines.append("   <Tags />")
        lines.append("   <Properties />")
        if c["type"] == "Animation":
            lines.append(f"   <AnimationHash>{format_hash(c['animation_hash'])}</AnimationHash>")
            lines.append(f"   <StartTime value=\"{c['start_time']:.8g}\" />")
            lines.append(f"   <EndTime value=\"{c['end_time']:.8g}\" />")
            lines.append(f"   <Rate value=\"{c['rate']:.8g}\" />")
        else:
            lines.append(f"   <Duration value=\"{c['duration']:.8g}\" />")
            lines.append("   <Animations>")
            for ae in c.get("animations", []):
                lines.append("    <Item>")
                lines.append(f"     <AnimationHash>{format_hash(ae['animation_hash'])}</AnimationHash>")
                lines.append(f"     <StartTime value=\"{ae['start_time']:.8g}\" />")
                lines.append(f"     <EndTime value=\"{ae['end_time']:.8g}\" />")
                lines.append(f"     <Rate value=\"{ae['rate']:.8g}\" />")
                lines.append("    </Item>")
            lines.append("   </Animations>")
        lines.append("  </Item>")
    lines.append(" </Clips>")

    lines.append(" <Animations>")
    for a in ycd["animations"]:
        lines.append("  <Item>")
        lines.append(f"   <Hash>{format_hash(a['hash'])}</Hash>")
        lines.append(f"   <Unknown10 value=\"{a['unknown10']}\" />")
        lines.append(f"   <FrameCount value=\"{a['frame_count']}\" />")
        lines.append(f"   <SequenceFrameLimit value=\"{a['sequence_frame_limit']}\" />")
        lines.append(f"   <Duration value=\"{a['duration']:.8g}\" />")
        lines.append(f"   <Unknown1C>{format_hash(a['unknown1c'])}</Unknown1C>")
        lines.append("   <BoneIds>")
        for bid, trk, unk0 in a["bone_ids"]:
            lines.append("    <Item>")
            lines.append(f"     <BoneId value=\"{bid}\" />")
            lines.append(f"     <Track value=\"{trk}\" />")
            lines.append(f"     <Unk0 value=\"{unk0}\" />")
            lines.append("    </Item>")
        lines.append("   </BoneIds>")
        lines.append("   <Sequences>")
        for sq in a["sequences"]:
            lines.append("    <Item>")
            lines.append(f"     <Hash>{format_hash(sq['hash'])}</Hash>")
            lines.append(f"     <FrameCount value=\"{sq['frame_count']}\" />")
            lines.append("     <SequenceData>")
            for sd in sq["sequence_data"]:
                lines.append("      <Item>")
                lines.append("       <Channels>")
                for ch in sd["channels"]:
                    lines.append("        <Item>")
                    lines.append(f"         <Type value=\"{ch['type']}\" />")
                    tid = ch["type_id"]
                    if tid == CHAN_STATIC_QUAT:
                        x, y, z, w = ch["value"]
                        lines.append(f"         <Value x=\"{x:.8g}\" y=\"{y:.8g}\" z=\"{z:.8g}\" w=\"{w:.8g}\" />")
                    elif tid == CHAN_STATIC_VEC3:
                        x, y, z = ch["value"]
                        lines.append(f"         <Value x=\"{x:.8g}\" y=\"{y:.8g}\" z=\"{z:.8g}\" />")
                    elif tid == CHAN_STATIC_FLOAT:
                        lines.append(f"         <Value value=\"{ch['value']:.8g}\" />")
                    elif tid == CHAN_RAW_FLOAT:
                        lines.append("         <Values>" + " ".join(f"{v:.8g}" for v in ch["values"]) + "</Values>")
                    elif tid == CHAN_QUANTIZE_FLOAT:
                        lines.append(f"         <Quantum value=\"{ch['quantum']:.8g}\" />")
                        lines.append(f"         <Offset value=\"{ch['offset']:.8g}\" />")
                        lines.append("         <Values>" + " ".join(f"{v:.8g}" for v in ch["values"]) + "</Values>")
                    elif tid == CHAN_INDIRECT_QUANTIZE_FLOAT:
                        lines.append(f"         <Quantum value=\"{ch['quantum']:.8g}\" />")
                        lines.append(f"         <Offset value=\"{ch['offset']:.8g}\" />")
                        lines.append("         <Values>" + " ".join(f"{v:.8g}" for v in ch["values"]) + "</Values>")
                        lines.append("         <Frames>" + " ".join(str(v) for v in ch["frames"]) + "</Frames>")
                    elif tid in (CHAN_CACHED_QUAT_1, CHAN_CACHED_QUAT_2):
                        lines.append(f"         <QuatIndex value=\"{ch['quat_index']}\" />")
                    lines.append("        </Item>")
                lines.append("       </Channels>")
                lines.append("      </Item>")
            lines.append("     </SequenceData>")
            lines.append("    </Item>")
        lines.append("   </Sequences>")
        lines.append("  </Item>")
    lines.append(" </Animations>")
    lines.append("</ClipDictionary>")

    out = Path(out_xml_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def decompile_ycd_binary_to_xml(ycd_path: Path | str, out_xml_path: Path | str) -> Path:
    return write_ycd_xml(parse_ycd_binary(ycd_path), out_xml_path)
