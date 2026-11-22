"""map-forge: Universal PyMateria binary forensic inspector & QA validator for FiveM maps.

Run with Blender 4.2.3 (WITHOUT --factory-startup so Sollumz + PyMateria load):
  blender.exe -b -P inspect_map.py -- --dir <stream_dir> [--spec <map-spec.json>] [--json <out.json>] [--interior]
"""

import argparse
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np


def _safe_str(val):
    s = getattr(val, "string", None)
    return s if s else str(val)


def _ydr_bounds(d, pmg):
    chunks = []
    if pmg.LodType.HIGH not in d.lods:
        return None
    for m in d.lods[pmg.LodType.HIGH].models:
        for g in m.geometries:
            pos = g.vb.buffer["POSITION"]
            if len(pos) > 0:
                chunks.append(np.asarray(pos, dtype=np.float64)[:, :3])
    if not chunks:
        return None
    pts = np.concatenate(chunks, axis=0)
    lo = pts.min(axis=0)
    hi = pts.max(axis=0)
    return [round(float(x), 3) for x in lo], [round(float(x), 3) for x in hi], [round(float(hi[i] - lo[i]), 2) for i in range(3)]


def inspect_stream(stream_dir, spec_path=None, is_interior=False):
    import pymateria.gta5 as pmg
    import pymateria.gta5.gen8 as pmg8
    from mathutils import Quaternion, Vector

    spec = None
    if spec_path:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

    budgets = (spec or {}).get("budgets", {})
    max_total_tris = int(budgets.get("max_total_tris", 60000))
    max_ytd_vram_mb = float(budgets.get("max_ytd_vram_mb", 8.0))
    max_disk_mb = float(budgets.get("max_disk_mb", 12.0))
    max_outdoor_vcol_g = float(budgets.get("max_outdoor_vcol_g", 45.0))

    fails = []
    warns = []
    report = {
        "stream_dir": stream_dir,
        "has_fxap_in_parent": False,
        "total_disk_mb": 0.0,
        "ytd": [],
        "ydr": [],
        "ybn": [],
        "ytyp": [],
        "ymap": [],
        "ymf": [],
        "summary": {},
        "warns": warns,
        "fails": fails,
    }

    parent_dir = os.path.dirname(os.path.normpath(stream_dir))
    if os.path.isfile(os.path.join(parent_dir, ".fxap")):
        report["has_fxap_in_parent"] = True
        warns.append("Parent resource contains .fxap (escrow protected) — DO NOT modify or redistribute.")

    all_files = []
    for root_d, _, fnames in os.walk(stream_dir):
        for fn in sorted(fnames):
            all_files.append(os.path.join(root_d, fn))

    if not all_files:
        fails.append(f"No files found in {stream_dir}")
        return report

    bin_exts = (".ydr", ".ytd", ".ybn", ".ytyp", ".ymap")
    total_bytes = 0
    for fp in all_files:
        total_bytes += os.path.getsize(fp)
        ext = os.path.splitext(fp)[1].lower()
        if ext in bin_exts:
            with open(fp, "rb") as fh:
                magic = fh.read(4)
            if magic != b"RSC7":
                fails.append(f"{os.path.basename(fp)}: invalid RSC7 magic ({magic!r})")

    report["total_disk_mb"] = round(total_bytes / (1024 * 1024), 2)
    if report["total_disk_mb"] > max_disk_mb:
        warns.append(f"Total stream disk size {report['total_disk_mb']} MB exceeds budget {max_disk_mb} MB")

    # 1. YTD Inspection
    ytd_names = set()
    total_vram_mb = 0.0
    total_tex = 0
    for fp in [p for p in all_files if p.lower().endswith(".ytd")]:
        fn = os.path.basename(fp)
        stem = os.path.splitext(fn)[0]
        ytd_names.add(stem.lower())
        try:
            txd = pmg8.TextureDictionary.import_rsc(fp).result
        except Exception as exc:
            fails.append(f"YTD {fn}: failed to parse ({exc})")
            continue
        raw_bytes = 0
        fmts = {}
        res_counts = {}
        no_mip_cnt = 0
        for tname, tex in txd.textures.items():
            tbytes = sum(len(layer) for mip in tex.mips for layer in mip.layers)
            raw_bytes += tbytes
            fmt = str(tex.format).split(".")[-1]
            fmts[fmt] = fmts.get(fmt, 0) + 1
            res = f"{tex.width}x{tex.height}"
            res_counts[res] = res_counts.get(res, 0) + 1
            if max(tex.width, tex.height) >= 64 and len(tex.mips) <= 1:
                no_mip_cnt += 1
        vram_mb = round(raw_bytes / (1024 * 1024), 2)
        total_vram_mb += vram_mb
        total_tex += len(txd.textures)
        if no_mip_cnt > 0:
            warns.append(f"YTD {fn}: {no_mip_cnt} texture(s) >=64px have <=1 mip level (will shimmer in-game)")
        report["ytd"].append({
            "file": fn,
            "disk_kb": round(os.path.getsize(fp) / 1024.0, 1),
            "vram_mb": vram_mb,
            "count": len(txd.textures),
            "formats": fmts,
            "resolutions": res_counts,
        })

    if total_vram_mb > max_ytd_vram_mb:
        warns.append(
            f"Total YTD VRAM {total_vram_mb:.2f} MB exceeds budget {max_ytd_vram_mb:.2f} MB "
            "(consider 512px tiled diffuse, 4x4-32x32 micro-swatches, PCA DXT1 opaque)"
        )

    # 2. YDR Inspection
    custom_model_names = set()
    total_tris = 0
    total_lights = 0
    for fp in [p for p in all_files if p.lower().endswith(".ydr")]:
        fn = os.path.basename(fp)
        stem = os.path.splitext(fn)[0]
        custom_model_names.add(stem.lower())
        try:
            d = pmg8.Drawable.import_rsc(fp).result
        except Exception as exc:
            warns.append(f"YDR {fn}: PyMateria parse error ({exc})")
            continue

        if pmg.LodType.HIGH not in d.lods:
            fails.append(f"YDR {fn}: missing HIGH LOD")
            continue

        shaders = []
        if getattr(d, "shader_group", None) and getattr(d.shader_group, "shaders", None):
            for sh in d.shader_group.shaders:
                shaders.append(_safe_str(sh.basis_material))

        needs_tangent = any(("normal" in s.lower() or "glass_env" in s.lower()) for s in shaders)
        tris = 0
        geoms = 0
        tangent_geoms = 0
        vcol_chunks = []
        missing_uv = False
        missing_vcol = False
        for m in d.lods[pmg.LodType.HIGH].models:
            for g in m.geometries:
                geoms += 1
                tris += len(g.ib.indices) // 3
                buf = g.vb.buffer
                names = set(buf.dtype.names or ())
                if "TEXTURE0" not in names:
                    missing_uv = True
                sh_obj = getattr(g, "shader", None)
                sh_name = _safe_str(sh_obj.basis_material).lower() if sh_obj is not None else ""
                if "DIFFUSE" in names and len(buf["DIFFUSE"]) > 0:
                    if "emissive" not in sh_name:
                        vcol_chunks.append(np.asarray(buf["DIFFUSE"], dtype=np.float32))
                else:
                    if not sh_name.startswith("water_"):
                        missing_vcol = True
                if "TANGENT0" in names or "TANGENT" in names:
                    tangent_geoms += 1

        if missing_uv:
            fails.append(f"YDR {fn}: geometry missing TEXTURE0 UV stream")
        if missing_vcol:
            warns.append(f"YDR {fn}: geometry missing DIFFUSE (Color 1) vertex color stream")
        if needs_tangent and tangent_geoms == 0:
            fails.append(f"YDR {fn}: uses normal/glass shader but has 0 geometries with TANGENT0 stream")

        vcol_mean = None
        if vcol_chunks:
            vc = np.concatenate(vcol_chunks, axis=0)
            vcol_mean = [round(float(x), 1) for x in vc.mean(axis=0)]
            if len(vcol_mean) >= 3:
                if vcol_mean[0] < 90.0 and not is_interior:
                    warns.append(f"YDR {fn}: low DIFFUSE.R ({vcol_mean[0]}) — exterior mesh will look dark in daylight")
                all_emissive = bool(shaders) and all("emissive" in s.lower() for s in shaders)
                if (not is_interior) and (not all_emissive) and vcol_mean[1] > max_outdoor_vcol_g:
                    warns.append(
                        f"YDR {fn}: high outdoor DIFFUSE.G ({vcol_mean[1]} > {max_outdoor_vcol_g}) — "
                        "exterior surfaces will glow unnaturally at night (use #FF00FF / G=0 baseline)"
                    )

        bounds_info = _ydr_bounds(d, pmg)
        n_lights = len(d.lights) if getattr(d, "lights", None) is not None else 0
        total_lights += n_lights
        total_tris += tris
        has_bound = d.bound is not None
        emb_tex = len(d.shader_group.texture_dictionary.textures) if (
            getattr(d, "shader_group", None) and getattr(d.shader_group, "texture_dictionary", None)
        ) else 0

        if tris > 45000:
            warns.append(f"YDR {fn}: {tris} tris in a single drawable (studio ceiling <= 40,000 tris for high FPS)")

        report["ydr"].append({
            "file": fn,
            "kb": round(os.path.getsize(fp) / 1024.0, 1),
            "tris": tris,
            "geoms": geoms,
            "dims": bounds_info[2] if bounds_info else None,
            "has_bound": has_bound,
            "emb_tex": emb_tex,
            "lights": n_lights,
            "tangent_geoms": tangent_geoms,
            "vcol_mean_rgba": vcol_mean,
            "shaders": sorted(set(shaders)),
        })

    if total_tris > max_total_tris:
        warns.append(f"Total custom YDR tris {total_tris} exceeds budget {max_total_tris}")

    # 3. YTYP Inspection
    mlo_count = 0
    for fp in [p for p in all_files if p.lower().endswith(".ytyp")]:
        fn = os.path.basename(fp)
        try:
            mt = pmg8.MapTypes.import_rsc(fp).result
        except Exception as exc:
            fails.append(f"YTYP {fn}: failed to parse ({exc})")
            continue
        arch_rows = []
        for arch in mt.archetypes:
            atype = type(arch).__name__
            is_mlo = "Mlo" in atype
            if is_mlo:
                mlo_count += 1
            td = _safe_str(arch.texture_dictionary)
            lod_d = round(float(arch.lod_distance), 1)
            hd_d = round(float(arch.hd_texture_distance), 1)
            if (not is_mlo) and lod_d > 0 and hd_d < lod_d * 0.85:
                warns.append(f"YTYP {fn} archetype {arch.name}: hd_texture_distance ({hd_d}) < lod_distance ({lod_d}) may blur textures")
            row = {
                "name": _safe_str(arch.name),
                "type": atype,
                "tex_dict": td,
                "lod_dist": lod_d,
                "hd_tex_dist": hd_d,
            }
            if is_mlo:
                row["rooms"] = len(getattr(arch, "rooms", []))
                row["portals"] = len(getattr(arch, "portals", []))
                row["entities"] = len(getattr(arch, "entities", []))
            arch_rows.append(row)
        report["ytyp"].append({"file": fn, "count": len(arch_rows), "archetypes": arch_rows})

    # 4. YBN Inspection
    req_flags = (
        pmg.CollisionFlags.MAP_TYPE_MOVER
        | pmg.CollisionFlags.MAP_TYPE_WEAPON
        | pmg.CollisionFlags.MAP_TYPE_COVER
        | pmg.CollisionFlags.MAP_TYPE_VEHICLE
    )
    expected_zs = list((spec or {}).get("anchor", {}).get("expected_floor_z", []))
    found_zs = {z: False for z in expected_zs}
    ybn_stems = set()
    for fp in [p for p in all_files if p.lower().endswith(".ybn")]:
        fn = os.path.basename(fp)
        ybn_stems.add(os.path.splitext(fn)[0].lower())
        try:
            b = pmg.Bound.import_rsc(fp).result
        except Exception as exc:
            fails.append(f"YBN {fn}: failed to parse ({exc})")
            continue
        children = list(getattr(b, "bounds", []))
        prims = 0
        flags_ok = True
        for ch in children:
            if (ch.type_flags & req_flags) != req_flags:
                flags_ok = False
            bad_inc = (
                pmg.CollisionFlags.MAP_TYPE_MOVER
                | pmg.CollisionFlags.MAP_TYPE_WEAPON
                | pmg.CollisionFlags.MAP_TYPE_COVER
                | pmg.CollisionFlags.MAP_TYPE_VEHICLE
            )
            if bool(ch.include_flags & bad_inc):
                warns.append(f"YBN {fn}: child include_flags contains MAP_TYPE_* (causes static-vs-static broadphase noise)")
            cb = ch.bound
            if hasattr(cb, "primitives"):
                prims += len(cb.primitives)
            if expected_zs and hasattr(cb, "vertices"):
                cpos_z = float(cb.position.z)
                for v in cb.vertices:
                    vz1 = float(v.position.z) + cpos_z
                    vz2 = float(v.position.z)
                    for tz in expected_zs:
                        if abs(vz1 - tz) < 0.05 or abs(vz2 - tz) < 0.05:
                            found_zs[tz] = True
        if not flags_ok:
            warns.append(f"YBN {fn}: one or more child bounds missing full MOVER|WEAPON|COVER|VEHICLE flags")
        report["ybn"].append({
            "file": fn,
            "kb": round(os.path.getsize(fp) / 1024.0, 1),
            "children": len(children),
            "prims": prims,
            "pos": [round(float(b.position.x), 2), round(float(b.position.y), 2), round(float(b.position.z), 2)],
        })

    for tz, ok_z in found_zs.items():
        if not ok_z:
            fails.append(f"Static YBN missing expected walkable floor Z={tz:.2f}m (tolerance 0.05m)")

    # 5. YMAP Inspection
    total_ents = 0
    total_custom_ents = 0
    total_vanilla_ents = 0
    for fp in [p for p in all_files if p.lower().endswith(".ymap")]:
        fn = os.path.basename(fp)
        try:
            md = pmg.MapData.import_rsc(fp).result
        except Exception as exc:
            fails.append(f"YMAP {fn}: failed to parse ({exc})")
            continue
        n_ent = len(md.entities)
        cust = 0
        bad_flags_ents = 0
        for e in md.entities:
            an = _safe_str(e.archetype_name).lower()
            if an in custom_model_names:
                cust += 1
            if (int(e.flags) & (524288 | 1048576)) != 0:
                bad_flags_ents += 1
        if bad_flags_ents > 0:
            warns.append(f"YMAP {fn}: {bad_flags_ents} entities use pool-heavy flags (524288|1048576); prefer flags=32 to avoid Pool-256 crash")
        van = n_ent - cust
        total_ents += n_ent
        total_custom_ents += cust
        total_vanilla_ents += van
        cf = int(md.content_flags)
        pdicts = [_safe_str(p) for p in md.physics_dictionaries]
        if ybn_stems and (cf & 64) == 0:
            warns.append(f"YMAP {fn}: static .ybn exists in stream but content_flags={cf} lacks HAS_PHYSICS (64)")

        # Spec-level exact verification (warp point extents, quaternion round-trip, zone sphere)
        arena_list = (spec or {}).get("arenas") or ([(spec or {}).get("anchor")] if (spec or {}).get("anchor") else [])
        matched_anchor = next((a for a in arena_list if a and os.path.splitext(fn)[0].lower() == a.get("ymap_name", "").lower()), None)
        if matched_anchor:
            anchor = matched_anchor
            wp = anchor.get("warp_point")
            if wp:
                wx, wy, wz = wp[0], wp[1], wp[2]
                if not (
                    md.streaming_extents_min.x < wx < md.streaming_extents_max.x
                    and md.streaming_extents_min.y < wy < md.streaming_extents_max.y
                    and md.streaming_extents_min.z < wz < md.streaming_extents_max.z
                ):
                    fails.append(f"YMAP {fn}: warp_point ({wx},{wy},{wz}) is OUTSIDE streaming_extents!")
            spec_ents = spec.get("entities", [])
            if len(spec_ents) == len(md.entities):
                sc = anchor.get("zone_sphere_center")
                sr = anchor.get("zone_sphere_radius")
                for idx, (e, item) in enumerate(zip(md.entities, spec_ents)):
                    q_raw = Quaternion((e.rotation.w, e.rotation.x, e.rotation.y, e.rotation.z))
                    yaw_rt = math.degrees(q_raw.inverted().to_euler("XYZ").z) % 360.0
                    exp_yaw = float(item.get("yaw_deg", 0.0)) % 360.0
                    diff = min(abs(yaw_rt - exp_yaw), 360.0 - abs(yaw_rt - exp_yaw))
                    if diff > 0.08:
                        fails.append(f"YMAP {fn} ent#{idx} ({item['model']}): yaw round-trip mismatch {yaw_rt:.2f} vs {exp_yaw:.2f}")
                    if sc and sr:
                        dist = (Vector((e.position.x, e.position.y, e.position.z)) - Vector(sc)).length
                        if dist > float(sr):
                            warns.append(f"YMAP {fn} ent#{idx} ({item['model']}): distance {dist:.1f}m exceeds zone_sphere_radius {sr}m")

        report["ymap"].append({
            "file": fn,
            "entities": n_ent,
            "custom": cust,
            "vanilla": van,
            "content_flags": cf,
            "physics_dictionaries": pdicts,
        })

    # 6. _manifest.ymf Inspection
    ymf_files = [p for p in all_files if p.lower().endswith(".ymf")]
    if not ymf_files and report["ymap"]:
        warns.append("Missing _manifest.ymf in stream directory (custom/vanilla ytyp dependencies may not pre-load)")
    for fp in ymf_files:
        fn = os.path.basename(fp)
        with open(fp, "rb") as fh:
            hdr = fh.read(8)
        if hdr.startswith(b"PSIN") or hdr.startswith(b"RSC7"):
            report["ymf"].append({"file": fn, "format": "BINARY_PSO"})
            continue
        try:
            tree = ET.parse(fp)
            root = tree.getroot()
            deps = {}
            for item in root.findall("./imapDependencies_2/Item"):
                imap = item.findtext("imapName") or ""
                ityps = [el.text for el in item.findall("./itypDepArray/Item") if el.text]
                deps[imap] = ityps
            report["ymf"].append({"file": fn, "format": "XML", "imap_deps": deps})
        except Exception as exc:
            fails.append(f"YMF {fn}: XML parse failed ({exc})")

    report["summary"] = {
        "disk_mb": report["total_disk_mb"],
        "ytd_count": len(report["ytd"]),
        "textures": total_tex,
        "vram_mb": round(total_vram_mb, 2),
        "ydr_count": len(report["ydr"]),
        "total_tris": total_tris,
        "embedded_lights": total_lights,
        "ybn_count": len(report["ybn"]),
        "ytyp_count": len(report["ytyp"]),
        "mlo_count": mlo_count,
        "ymap_count": len(report["ymap"]),
        "entities_total": total_ents,
        "entities_custom": total_custom_ents,
        "entities_vanilla": total_vanilla_ents,
        "vanilla_ratio_pct": round(100.0 * total_vanilla_ents / max(total_ents, 1), 1),
    }
    return report


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Inspect and validate FiveM map binary stream files")
    ap.add_argument("--dir", required=True, help="Path to stream directory")
    ap.add_argument("--spec", default="", help="Optional map-spec.json for strict floor-Z/warp/quaternion checks")
    ap.add_argument("--json", dest="json_out", default="", help="Optional JSON report output path")
    ap.add_argument("--interior", action="store_true", help="Treat map as interior (relaxes outdoor DIFFUSE.G check)")
    args = ap.parse_args(argv)

    rep = inspect_stream(args.dir, spec_path=args.spec or None, is_interior=args.interior)
    s = rep["summary"]
    print(
        f"SUMMARY disk={s['disk_mb']}MB | vram={s['vram_mb']}MB ({s['textures']}tx) | "
        f"ydr={s['ydr_count']} ({s['total_tris']} tris, {s['embedded_lights']} lights) | "
        f"ybn={s['ybn_count']} | ytyp={s['ytyp_count']} (mlo={s['mlo_count']}) | "
        f"ymap={s['ymap_count']} ({s['entities_total']} ents: {s['entities_custom']} custom + {s['entities_vanilla']} vanilla [{s['vanilla_ratio_pct']}%])",
        flush=True,
    )
    for w in rep["warns"]:
        print("WARN " + w, flush=True)
    for fl in rep["fails"]:
        print("FAIL " + fl, flush=True)

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)

    if rep["fails"]:
        print(f"MAP_INSPECT_FAIL fail={len(rep['fails'])} warn={len(rep['warns'])}", flush=True)
        os._exit(1)
    print(f"MAP_INSPECT_PASS fail=0 warn={len(rep['warns'])}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
