import argparse
import datetime
import gzip
import hashlib
import importlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np


class PolyHavenForge:
    Api = "https://api.polyhaven.com"
    Site = "https://polyhaven.com"
    Terms = "https://github.com/Poly-Haven/Public-API/blob/master/ToS.md"
    License = "https://polyhaven.com/license"
    Agent = "map-forge-fetch-polyhaven/1.0"
    Kinds = {0: "hdris", 1: "textures", 2: "models"}
    Retry = (429, 500, 502, 503, 504)
    TextureMaps = (
        ("diffuse", ("Diffuse",), True),
        ("normal", ("nor_gl", "nor_dx"), True),
        ("rough", ("Rough",), False),
        ("ao", ("AO",), False),
        ("metal", ("Metal",), False),
    )
    FileRoles = {
        "diff": "diffuse",
        "nor_gl": "normal",
        "nor_dx": "normal_dx",
        "rough": "rough",
        "ao": "ao",
        "metal": "metal",
        "arm": "arm",
    }
    Magic = {
        "png": (b"\x89PNG\r\n\x1a\n",),
        "jpg": (b"\xff\xd8\xff",),
        "hdr": (b"#?RADIANCE", b"#?RGBE"),
        "exr": (b"\x76\x2f\x31\x01",),
    }
    SpecClasses = {
        "matte": {"range": (0.12, 0.28), "intensity": 0.15, "fresnel": 0.80},
        "varnish": {"range": (0.25, 0.45), "intensity": 0.30, "fresnel": 0.85},
        "glazed": {"range": (0.45, 0.70), "intensity": 0.45, "fresnel": 0.90},
        "metal": {"range": (0.65, 0.90), "intensity": 0.65, "fresnel": 0.95},
    }
    GlazedPaths = (
        "ceramic/glazed",
        "ceramic/terrazzo",
        "stone/slabs & tiles/marble",
        "stone/slabs & tiles/polished",
        "stone/slabs & tiles/granite",
    )
    VarnishPaths = (
        "wood/boards & planks/finished",
        "wood/boards & planks/parquet",
        "wood/boards & planks/painted",
        "wood/veneer",
        "wood/engineered wood/laminate",
        "plastic & rubber/plastic",
        "plastic & rubber/vinyl",
    )

    def __init__(self, args):
        self.args = args
        self.work = os.path.abspath(args.work) if args.work else ""
        self.codec_module = None
        self.bpy_module = None

    def say(self, text):
        print(text, flush=True)

    def credit(self):
        self.say("Poly Haven (" + self.Site + ") | assets CC0 | API terms " + self.Terms)

    def run(self):
        if self.args.command != "convert":
            self.credit()
        try:
            {
                "list": self.command_list,
                "categories": self.command_categories,
                "fetch": self.command_fetch,
                "convert": self.command_convert,
            }[self.args.command]()
        except Exception as err:
            self.say("POLYHAVEN_FAIL " + type(err).__name__ + ": " + str(err))
            return 1
        return 0

    def now(self):
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def check_host(self, url):
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not (host in ("polyhaven.org", "polyhaven.com") or host.endswith((".polyhaven.org", ".polyhaven.com"))):
            raise RuntimeError("refusing URL outside Poly Haven: " + url)

    def retry_after(self, value, attempt):
        try:
            return min(60.0, max(1.0, float(value)))
        except (TypeError, ValueError):
            return 2.0 * (attempt + 1)

    def http(self, url, target="", limit=0.0, retry=None):
        self.check_host(url)
        codes = retry or self.Retry
        headers = {"User-Agent": self.Agent, "Accept": "*/*" if target else "application/json"}
        if not target:
            headers["Accept-Encoding"] = "gzip"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                    self.check_host(response.geturl())
                    if target:
                        return self.stream(response, url, target, limit)
                    body = response.read()
                    if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
                        body = gzip.decompress(body)
                    return body
            except urllib.error.HTTPError as err:
                if err.code in codes and attempt < 3:
                    time.sleep(self.retry_after(err.headers.get("Retry-After"), attempt))
                    continue
                raise RuntimeError("HTTP " + str(err.code) + " " + url)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                if attempt < 3:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise RuntimeError("network error " + str(getattr(err, "reason", err)) + " " + url)
        raise RuntimeError("gave up on " + url)

    def stream(self, response, url, target, limit):
        digest = hashlib.md5()
        total = 0
        try:
            with open(target, "wb") as fh:
                while True:
                    chunk = response.read(1048576)
                    if not chunk:
                        break
                    total += len(chunk)
                    if limit and total > limit:
                        raise RuntimeError("download exceeds --max-mb: " + url)
                    digest.update(chunk)
                    fh.write(chunk)
        except BaseException:
            if os.path.isfile(target):
                os.remove(target)
            raise
        return digest.hexdigest()

    def cache_dir(self):
        if self.work:
            return os.path.join(self.work, "source", "polyhaven", ".cache")
        return os.path.join(tempfile.gettempdir(), "map-forge-polyhaven")

    def api(self, path, params=None, hours=0.0, retry=None):
        query = urllib.parse.urlencode(params or {})
        url = self.Api + "/" + path + ("?" + query if query else "")
        cache_file = os.path.join(self.cache_dir(), hashlib.sha1(url.encode("utf-8")).hexdigest()[:20] + ".json") if hours else ""
        if cache_file and os.path.isfile(cache_file) and time.time() - os.path.getmtime(cache_file) < hours * 3600.0:
            try:
                with open(cache_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                pass
        data = json.loads(self.http(url, retry=retry).decode("utf-8"))
        if cache_file:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(cache_file + ".tmp", cache_file)
        return data

    def valid_slug(self, slug):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", slug or ""):
            raise RuntimeError("asset id must match [A-Za-z0-9_-]{1,80}: " + repr(slug))
        return slug

    def stem_of(self, text):
        stem = re.sub(r"[^a-z0-9_]+", "_", str(text).lower()).strip("_")[:48].strip("_")
        if not stem:
            raise RuntimeError("empty texture name")
        if stem.endswith(("_n", "_s")):
            raise RuntimeError("texture name " + stem + " must not end with _n or _s: export_map.py reads those endings as normal and spec maps")
        return stem

    def rel(self, path):
        if not self.work:
            return path.replace("\\", "/")
        try:
            return os.path.relpath(path, self.work).replace("\\", "/")
        except ValueError:
            return path.replace("\\", "/")

    def res_rank(self, res):
        match = re.fullmatch(r"(\d+)k", str(res or "").lower())
        return int(match.group(1)) if match else 0

    def res_label(self, pixels):
        return str(max(1, int(round(pixels / 1024.0)))) + "k"

    def want_res(self, default):
        res = (self.args.res or default).lower()
        if not re.fullmatch(r"[1-9]\d?k", res):
            raise RuntimeError("--res must look like 1k, 2k or 4k: " + res)
        return res

    def tile_m(self, info, fallback):
        dims = info.get("dimensions") or []
        if len(dims) >= 2 and dims[0] and dims[1]:
            return (round(float(dims[0]) / 1000.0, 3), round(float(dims[1]) / 1000.0, 3))
        return (max(0.0, float(fallback)), max(0.0, float(fallback)))

    def parse_attrs(self):
        params = {}
        for pair in self.args.attr:
            if not re.fullmatch(r"[a-z_]+=[a-z0-9_,-]+", pair):
                raise RuntimeError("--attr must look like key=value: " + pair)
            key, value = pair.split("=", 1)
            params[key] = value
        return params

    def table(self, headers, rows):
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        self.say("  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
        for row in rows:
            self.say("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())

    def haystack(self, slug, record):
        return " ".join([slug, str(record.get("name") or ""), str(record.get("category") or "")] + [str(w) for w in (record.get("tags") or []) + (record.get("categories") or [])]).lower()

    def ranked(self, query, kind, assets, order):
        try:
            found = self.api("search", {"q": query, "t": kind}, 12.0, (429,))
        except RuntimeError as err:
            if not str(err).startswith("HTTP 503"):
                raise
            self.say("note search answered 503, using a keyword match on name, tags and category instead")
            words = query.split()
            return [slug for slug in order if all(word in self.haystack(slug, assets[slug]) for word in words)]
        return [r.get("slug") for r in found.get("results") or [] if r.get("slug") in assets]

    def command_list(self):
        kind = self.args.kind
        params = {"type": kind}
        if self.args.category:
            params["category"] = self.args.category
        params.update(self.parse_attrs())
        assets = self.api("assets", params, 12.0)
        order = [slug for _, slug in sorted((-int(record.get("download_count") or 0), slug) for slug, record in assets.items())]
        query = " ".join(self.args.query.split()).lower()[:100]
        if query:
            order = self.ranked(query, kind, assets, order)
        tags = [t.strip().lower() for t in self.args.tags.split(",") if t.strip()]
        rows = []
        for slug in order:
            record = assets[slug]
            words = {str(w).strip().lower() for w in (record.get("tags") or []) + (record.get("categories") or [])}
            if any(t not in words for t in tags):
                continue
            attrs = record.get("attributes") or {}
            page = self.Site + "/a/" + slug
            if kind == "textures":
                tile = self.tile_m(record, 0.0)
                if self.args.min_m and min(tile) < self.args.min_m:
                    continue
                if self.args.max_m and max(tile) > self.args.max_m:
                    continue
                condition = attrs.get("condition") or []
                rows.append([
                    slug,
                    f"{tile[0]:.2f}x{tile[1]:.2f}",
                    "ok" if tile[0] and 1.5 <= min(tile) and max(tile) <= 4.0 else "--",
                    int(round(self.args.size / max(tile))) if max(tile) else 0,
                    attrs.get("surface_use") or "-",
                    attrs.get("setting") or "-",
                    ",".join(condition) if isinstance(condition, list) else str(condition),
                    record.get("category") or "-",
                    page,
                ])
            else:
                peak = (record.get("max_resolution") or [0])[0]
                rows.append([
                    slug,
                    attrs.get("time_of_day") or "-",
                    attrs.get("weather") or "-",
                    attrs.get("environment") or "-",
                    attrs.get("sky_view") or "-",
                    self.res_label(peak) if peak else "-",
                    record.get("category") or "-",
                    page,
                ])
            if len(rows) >= max(1, self.args.limit):
                break
        if kind == "textures":
            self.table(["id", "size_m", "1.5-4m", "px/m@" + str(self.args.size), "use", "setting", "condition", "category", "page"], rows)
        else:
            self.table(["id", "time", "weather", "env", "sky", "max", "category", "page"], rows)
        self.say(f"POLYHAVEN_LIST kind={kind} results={len(rows)} fail=0")

    def command_categories(self):
        data = self.api("taxonomy/" + self.args.kind, None, 12.0)
        rows = []
        stack = [(node, 1) for node in reversed(data.get("categories") or [])]
        while stack:
            node, depth = stack.pop()
            rows.append(["  " * (depth - 1) + str(node.get("slugPath") or ""), str(node.get("path") or "")])
            if depth < self.args.depth:
                stack.extend((child, depth + 1) for child in reversed(node.get("children") or []))
        self.table(["category (use with --category)", "path"], rows)
        for key, spec in (data.get("attributes") or {}).items():
            values = spec.get("enum") or []
            self.say("attr " + key + " (" + str(spec.get("type") or "") + "): " + (",".join(str(v) for v in values) if values else "true/false"))
        self.say(f"POLYHAVEN_CATEGORIES kind={self.args.kind} nodes={len(rows)} fail=0")

    def pick(self, files, keys, res, formats):
        want = self.res_rank(res)
        for key in keys:
            by_res = files.get(key)
            if not isinstance(by_res, dict) or not by_res:
                continue
            for _, _, found in sorted((abs(self.res_rank(r) - want), self.res_rank(r), r) for r in by_res if self.res_rank(r)):
                by_fmt = by_res.get(found) or {}
                for fmt in formats:
                    entry = by_fmt.get(fmt) if isinstance(by_fmt, dict) else None
                    if isinstance(entry, dict) and entry.get("url"):
                        return dict(entry, key=key, res=found, format=fmt)
        return None

    def plan_item(self, slug, role, entry, folder):
        name = os.path.basename(urllib.parse.urlsplit(entry["url"]).path)
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", urllib.parse.unquote(name))
        if not name.lower().startswith(slug.lower()):
            name = slug + "_" + name
        return {
            "role": role,
            "key": entry["key"],
            "res": entry["res"],
            "format": entry["format"],
            "url": entry["url"],
            "md5": entry.get("md5") or "",
            "size": int(entry.get("size") or 0),
            "dest": os.path.join(self.work, folder, name) if self.work else os.path.join(folder, name),
        }

    def plan_texture(self, slug, files):
        res = self.want_res("1k")
        fmt = self.args.format or "jpg"
        if fmt not in ("png", "jpg"):
            raise RuntimeError("textures support --format png or jpg")
        formats = (fmt, "jpg" if fmt == "png" else "png")
        folder = os.path.join("source", "polyhaven", slug)
        plan = []
        missing = []
        for role, keys, required in self.TextureMaps:
            if role == "ao" and self.args.ao_strength <= 0:
                continue
            entry = self.pick(files, keys, res, formats)
            if entry is None:
                if required:
                    raise RuntimeError("asset has no " + "/".join(keys) + " map")
                if role in ("rough", "ao"):
                    missing.append(role)
                continue
            plan.append(self.plan_item(slug, "normal_dx" if entry["key"] == "nor_dx" else role, entry, folder))
        if missing:
            entry = self.pick(files, ("arm",), res, formats)
            if entry is not None:
                plan.append(self.plan_item(slug, "arm", entry, folder))
        return plan

    def plan_hdri(self, slug, files):
        res = self.want_res("2k")
        fmt = self.args.format or "hdr"
        if fmt not in ("hdr", "exr"):
            raise RuntimeError("HDRIs support --format hdr or exr")
        entry = self.pick(files, ("hdri",), res, (fmt, "exr" if fmt == "hdr" else "hdr"))
        if entry is None:
            raise RuntimeError("asset has no hdri files")
        return [self.plan_item(slug, "hdri", entry, os.path.join("preview", "hdri"))]

    def estimate_dims(self, info, res):
        peak = info.get("max_resolution") or [0, 0]
        wide = self.res_rank(res) * 1024
        if len(peak) < 2 or not peak[0] or not peak[1] or not wide:
            return (wide, wide)
        return (wide, max(1, int(round(wide * peak[1] / float(peak[0])))))

    def command_fetch(self):
        slug = self.valid_slug(self.args.id)
        info = self.api("info/" + urllib.parse.quote(slug))
        kind = self.Kinds.get(info.get("type"))
        if kind not in ("textures", "hdris"):
            raise RuntimeError("asset type " + str(kind) + " is out of scope: map-forge dresses maps with native GTA V props")
        files = self.api("files/" + urllib.parse.quote(slug))
        plan = self.plan_texture(slug, files) if kind == "textures" else self.plan_hdri(slug, files)
        self.say("asset " + slug + " | " + str(info.get("name") or "") + " | " + self.Site + "/a/" + slug)
        self.say("category " + str(info.get("category") or "-") + " | authors " + (", ".join((info.get("authors") or {}).keys()) or "-"))
        total = sum(item["size"] for item in plan)
        self.table(
            ["role", "map", "res", "fmt", "MB", "md5", "url"],
            [[i["role"], i["key"], i["res"], i["format"], f"{i['size'] / 1048576.0:.2f}", i["md5"] or "-", i["url"]] for i in plan],
        )
        for item in plan:
            self.say("download -> " + self.rel(item["dest"]))
        if kind == "textures":
            self.preview_outputs(slug, info, plan)
        else:
            self.say("preview only: the HDRI lights Blender look-dev renders and is never packed into a .ytd or stream/")
        if self.args.dry_run:
            self.say("dry run: metadata only, nothing was downloaded or written")
            self.say("to download, run this again without --dry-run, or save the files above by hand into " + self.rel(os.path.dirname(plan[0]["dest"])) + (" and run convert" if kind == "textures" else ""))
            self.say(f"POLYHAVEN_DRYRUN id={slug} kind={kind} files={len(plan)} download_mb={total / 1048576.0:.2f} fail=0")
            return
        if kind == "textures":
            self.bpy()
        local = self.download(plan)
        entry = self.base_entry(slug, info, kind, plan)
        entry["fetched_utc"] = self.now()
        if kind == "textures":
            entry.update(self.build_maps(slug, local, info))
            path = self.write_manifest("textures", entry["stem"], entry)
            self.say(f"POLYHAVEN_FETCH_PASS id={slug} stem={entry['stem']} vram_kb={entry['vram_kb']} manifest={self.rel(path)} fail=0")
        else:
            entry["ship"] = False
            entry["preview_file"] = self.rel(local["hdri"])
            path = self.write_manifest("hdris", slug, entry)
            self.say(f"POLYHAVEN_FETCH_PASS id={slug} hdri={self.rel(local['hdri'])} ship=false manifest={self.rel(path)} fail=0")

    def download(self, plan):
        if not self.work:
            raise RuntimeError("--work is required to download")
        limit = self.args.max_mb * 1048576.0
        for item in plan:
            if item["size"] > limit:
                raise RuntimeError(item["key"] + " is " + f"{item['size'] / 1048576.0:.1f}" + " MB, above --max-mb")
        local = {}
        for item in plan:
            os.makedirs(os.path.dirname(item["dest"]), exist_ok=True)
            if os.path.isfile(item["dest"]) and item["md5"] and self.md5_of(item["dest"]) == item["md5"]:
                self.say("cached " + self.rel(item["dest"]))
            else:
                part = item["dest"] + ".part"
                digest = self.http(item["url"], part, limit)
                if item["md5"] and digest != item["md5"]:
                    os.remove(part)
                    raise RuntimeError("md5 mismatch for " + os.path.basename(item["dest"]))
                os.replace(part, item["dest"])
                self.say("saved " + self.rel(item["dest"]) + (" md5 ok" if item["md5"] else " (no md5 published)"))
            self.check_magic(item["dest"], item["format"])
            local[item["role"]] = item["dest"]
        return local

    def preview_outputs(self, slug, info, plan):
        stem = self.stem_of(self.args.name or slug)
        tile = self.tile_m(info, self.args.tile_m)
        res = next((i["res"] for i in plan if i["role"] == "diffuse"), "1k")
        src_w, src_h = self.estimate_dims(info, res)
        dims = {role: self.target_dims(src_w, src_h, size) for role, size in self.output_sizes().items()}
        self.say(f"real size {tile[0]:.2f} x {tile[1]:.2f} m | source ~{src_w}x{src_h} | spec class {self.spec_class(info)}")
        vram = 0
        for role, suffix in (("diffuse", ""), ("normal", "_n"), ("spec", "_s")):
            w, h = dims[role]
            vram += self.dxt1_bytes(w, h)
            self.say(f"output -> build/textures/{stem}{suffix}.png {w}x{h} px_per_m={self.density(w, h, tile)} dxt1_kb={self.dxt1_bytes(w, h) / 1024.0:.1f}")
        self.say(f"set vram_kb={vram / 1024.0:.1f} as DXT1 with full mips")
        for note in self.notes(info, stem, tile, dims["diffuse"], (src_w, src_h)):
            self.say("note " + note)

    def output_sizes(self):
        size = self.args.size
        return {
            "diffuse": size,
            "normal": self.args.normal_size or min(size, 512),
            "spec": self.args.spec_size or min(size, 256),
        }

    def density(self, w, h, tile):
        if not tile[0] or not tile[1]:
            return 0
        return int(round(min(w / tile[0], h / tile[1])))

    def notes(self, info, stem, tile, dims, src):
        found = []
        if not (1.5 <= min(tile) and max(tile) <= 4.0):
            found.append(f"tile {tile[0]:.2f}x{tile[1]:.2f} m is outside the 1.5-4 m world-scale range")
        px = self.density(dims[0], dims[1], tile)
        if px and px < 200:
            found.append(f"{px} px/m is below the 200-340 px/m floor target; use it for walls or far ground, or pick --size 1024 for a hero floor")
        if max(dims) > 512:
            found.append(f"{max(dims)} px is for 1-3 hero floors per map; export_map.py halves diffuse maps above texture_rules.default_diffuse_max_res (512) unless the name starts with a texture_rules.hero_prefixes entry")
        if stem.startswith(("swatch_", "trim_")):
            found.append("export_map.py cuts names starting with swatch_ or trim_ to 32 px")
        if src[0] and src[1]:
            squash = abs((dims[0] / float(dims[1])) / (src[0] / float(src[1])) - 1.0)
            if squash > 0.03:
                found.append(f"pow2 resize changes the aspect by {squash * 100:.1f}%; keep UV at the real size per axis")
            if tile[0] and tile[1] and abs((src[0] / float(src[1])) / (tile[0] / tile[1]) - 1.0) > 0.05:
                found.append(f"source pixels {src[0]}x{src[1]} do not match the real size {tile[0]:.2f}x{tile[1]:.2f} m; check the asset page before trusting the tile size")
        if str(info.get("category") or "").lower().startswith("glass"):
            found.append("glass needs glass_env.sps with a DXT5 alpha diffuse; this route writes opaque normal_spec.sps maps")
        return found

    def dxt1_bytes(self, w, h):
        total = 0
        while True:
            total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
            if w <= 1 and h <= 1:
                return total
            w = max(1, w // 2)
            h = max(1, h // 2)

    def md5_of(self, path):
        digest = hashlib.md5()
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1048576)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def check_magic(self, path, fmt):
        with open(path, "rb") as fh:
            head = fh.read(16)
        if not head.startswith(self.Magic.get(fmt, (b"",))):
            raise RuntimeError("file does not look like " + fmt + ": " + os.path.basename(path))

    def base_entry(self, slug, info, kind, plan):
        page = self.Site + "/a/" + slug
        return {
            "asset_id": slug,
            "name": info.get("name") or slug,
            "kind": kind,
            "page": page,
            "license": "CC0-1.0",
            "license_url": self.License,
            "credit": "Poly Haven (CC0): " + page,
            "authors": info.get("authors") or {},
            "category": info.get("category") or "",
            "tags": info.get("tags") or [],
            "categories": info.get("categories") or [],
            "dimensions_mm": [round(float(v), 1) for v in (info.get("dimensions") or [])][:2],
            "files_hash": info.get("files_hash") or "",
            "downloads": [
                {
                    "role": i["role"],
                    "map": i["key"],
                    "res": i["res"],
                    "format": i["format"],
                    "url": i["url"],
                    "md5": i["md5"],
                    "bytes": i["size"],
                    "file": self.rel(i["dest"]),
                }
                for i in plan
            ],
        }

    def command_convert(self):
        slug = self.valid_slug(self.args.id)
        if not self.work:
            raise RuntimeError("--work is required")
        self.bpy()
        src = os.path.abspath(self.args.src) if self.args.src else os.path.join(self.work, "source", "polyhaven", slug)
        local = self.local_sources(slug, src)
        known = self.known_entry(slug)
        if known:
            info = {
                "name": known.get("name") or slug,
                "category": known.get("category") or "",
                "tags": known.get("tags") or [],
                "categories": known.get("categories") or [],
                "dimensions": known.get("dimensions_mm") or [],
            }
            entry = dict(known)
        else:
            info = self.lookup(slug)
            entry = self.base_entry(slug, info, "textures", [])
            entry["downloads"] = [{"role": role, "file": self.rel(path)} for role, path in sorted(local.items())]
        entry["converted_utc"] = self.now()
        entry.update(self.build_maps(slug, local, info))
        path = self.write_manifest("textures", entry["stem"], entry)
        self.say(f"POLYHAVEN_CONVERT_PASS id={slug} stem={entry['stem']} vram_kb={entry['vram_kb']} manifest={self.rel(path)} fail=0")

    def local_sources(self, slug, src):
        if not os.path.isdir(src):
            raise RuntimeError("source folder not found: " + src)
        pattern = re.compile(re.escape(slug) + r"_(diff|nor_gl|nor_dx|rough|ao|metal|arm)_(\d+k)\.(png|jpg)", re.IGNORECASE)
        want = self.res_rank(self.want_res("1k")) if self.args.res else 0
        found = {}
        for name in sorted(os.listdir(src)):
            match = pattern.fullmatch(name)
            if not match:
                continue
            role = self.FileRoles[match.group(1).lower()]
            rank = self.res_rank(match.group(2))
            if want and rank != want:
                continue
            if role not in found or rank > found[role][0]:
                found[role] = (rank, os.path.join(src, name), match.group(3).lower())
        if "normal" in found:
            found.pop("normal_dx", None)
        if "diffuse" not in found or not ("normal" in found or "normal_dx" in found):
            raise RuntimeError("need " + slug + "_diff_<res> and " + slug + "_nor_gl_<res> (png or jpg) in " + src)
        for _, path, fmt in found.values():
            self.check_magic(path, fmt)
        self.say("sources " + ", ".join(role + "=" + os.path.basename(value[1]) for role, value in sorted(found.items())))
        return {role: value[1] for role, value in found.items()}

    def lookup(self, slug):
        if self.args.offline:
            self.say("note offline: tile size from --tile-m and spec class from --spec-class (auto falls back to matte)")
            return {}
        self.credit()
        try:
            info = self.api("info/" + urllib.parse.quote(slug))
        except RuntimeError as err:
            self.say("note metadata lookup failed (" + str(err) + "); tile size from --tile-m and spec class from --spec-class (auto falls back to matte)")
            return {}
        if self.Kinds.get(info.get("type")) != "textures":
            raise RuntimeError(slug + " is not a Poly Haven texture")
        self.say("metadata " + slug + " | " + str(info.get("name") or "") + " | " + self.Site + "/a/" + slug)
        return info

    def known_entry(self, slug):
        path = os.path.join(self.work, "source", "polyhaven", "manifest.json")
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in (data.get("textures") or {}).values():
            if entry.get("asset_id") == slug and entry.get("downloads"):
                return entry
        return {}

    def bpy(self):
        if self.bpy_module is None:
            try:
                self.bpy_module = importlib.import_module("bpy")
            except ImportError:
                raise RuntimeError("conversion runs inside Blender: blender -b --factory-startup -P fetch_polyhaven.py -- <command> ...")
        return self.bpy_module

    def codec(self):
        if self.codec_module is None:
            here = os.path.dirname(os.path.abspath(__file__))
            if here not in sys.path:
                sys.path.insert(0, here)
            self.codec_module = importlib.import_module("dds_codec")
        return self.codec_module

    def load(self, path):
        bpy = self.bpy()
        image = bpy.data.images.load(path, check_existing=False)
        try:
            image.colorspace_settings.name = "Non-Color"
            image.reload()
            w, h = image.size
            if not w or not h:
                raise RuntimeError("cannot decode " + os.path.basename(path))
            buf = np.empty(w * h * 4, dtype=np.float32)
            image.pixels.foreach_get(buf)
            return buf.reshape(h, w, 4)
        finally:
            bpy.data.images.remove(image)

    def save_png(self, rgb, path):
        bpy = self.bpy()
        h, w = rgb.shape[:2]
        image = bpy.data.images.new(os.path.basename(path)[:60], width=w, height=h, alpha=False, float_buffer=False)
        try:
            rgba = np.concatenate((np.clip(rgb[..., :3], 0.0, 1.0), np.ones((h, w, 1), dtype=np.float32)), axis=2)
            image.pixels.foreach_set(rgba.astype(np.float32).ravel())
            image.filepath_raw = path
            image.file_format = "PNG"
            image.save()
        finally:
            bpy.data.images.remove(image)

    def to_linear(self, c):
        c = np.clip(c, 0.0, 1.0)
        return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4)).astype(np.float32)

    def to_srgb(self, c):
        c = np.clip(c, 0.0, 1.0)
        return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055).astype(np.float32)

    def pow2_floor(self, n):
        return 1 << (max(1, int(n)).bit_length() - 1)

    def pow2_round(self, x):
        return 1 << max(0, int(round(np.log2(max(1.0, float(x))))))

    def target_dims(self, w, h, size):
        cap = min(size, self.pow2_floor(max(w, h)))
        if w >= h:
            return (max(4, cap), max(4, min(self.pow2_round(cap * h / float(w)), self.pow2_floor(h), cap)))
        return (max(4, min(self.pow2_round(cap * w / float(h)), self.pow2_floor(w), cap)), max(4, cap))

    def weights(self, n, m):
        edges = np.arange(m + 1, dtype=np.float64) * (n / float(m))
        src = np.arange(n, dtype=np.float64)
        lo = np.maximum(src[None, :], edges[:-1, None])
        hi = np.minimum(src[None, :] + 1.0, edges[1:, None])
        w = np.clip(hi - lo, 0.0, None)
        return (w / np.maximum(w.sum(axis=1, keepdims=True), 1e-12)).astype(np.float32)

    def resample(self, arr, tw, th):
        cur = arr.astype(np.float32)
        while cur.shape[0] % 2 == 0 and cur.shape[1] % 2 == 0 and cur.shape[0] >= th * 4 and cur.shape[1] >= tw * 4:
            h, w, c = cur.shape
            cur = cur.reshape(h // 2, 2, w // 2, 2, c).mean(axis=(1, 3))
        h, w, c = cur.shape
        if (h, w) == (th, tw):
            return cur
        across = np.matmul(cur.transpose(0, 2, 1), self.weights(w, tw).T).transpose(0, 2, 1)
        down = np.matmul(self.weights(h, th), across.reshape(h, tw * c))
        return down.reshape(th, tw, c)

    def match(self, arr, w, h):
        if arr.shape[0] == h and arr.shape[1] == w:
            return arr
        return self.resample(arr, w, h)

    def spec_class(self, info):
        if self.args.spec_class != "auto":
            return self.args.spec_class
        path = str(info.get("category") or "").strip().strip("/").lower()
        if path:
            path += "/"
            if path.startswith("metal/"):
                return "metal"
            if path.startswith(self.GlazedPaths):
                return "glazed"
            if path.startswith(self.VarnishPaths):
                return "varnish"
            return "matte"
        words = {str(w).strip().lower() for w in (info.get("tags") or []) + (info.get("categories") or [])}
        if "metal" in words:
            return "metal"
        if words & {"marble", "polished", "glazed", "terrazzo", "porcelain"}:
            return "glazed"
        if words & {"varnished", "lacquered", "laminate", "parquet"}:
            return "varnish"
        return "matte"

    def halve(self, level, role):
        h, w, c = level.shape
        sh = 2 if h > 1 else 1
        sw = 2 if w > 1 else 1
        if role == "diffuse":
            return self.to_srgb(self.to_linear(level).reshape(h // sh, sh, w // sw, sw, c).mean(axis=(1, 3)))
        if role == "normal":
            vectors = (level * 2.0 - 1.0).reshape(h // sh, sh, w // sw, sw, c).mean(axis=(1, 3))
            return (vectors / np.maximum(np.linalg.norm(vectors, axis=2, keepdims=True), 1e-6) * 0.5 + 0.5).astype(np.float32)
        return level.reshape(h // sh, sh, w // sw, sw, c).mean(axis=(1, 3)).astype(np.float32)

    def mip_levels(self, data, role):
        levels = [data.astype(np.float32)]
        while levels[-1].shape[0] > 1 or levels[-1].shape[1] > 1:
            level = self.halve(levels[-1], role)
            if role == "diffuse" and len(levels) <= 3 and min(level.shape[0], level.shape[1]) >= 16:
                level = self.codec()._unsharp_rgb(level, amount=0.20).astype(np.float32)
            levels.append(level)
        return levels

    def encode_dds(self, data, role, path):
        codec = self.codec()
        levels = self.mip_levels(data, role)
        blocks = []
        for level in levels:
            rgb = level[::-1].copy()
            if role == "normal":
                rgb[..., 1] = 1.0 - rgb[..., 1]
            pixels = np.clip(np.round(rgb * 255.0), 0, 255).astype(np.uint8)
            blocks.append(codec.compress_dxt1_grid(np.concatenate((pixels, np.full(pixels.shape[:2] + (1,), 255, dtype=np.uint8)), axis=2)))
        payload = b"".join(blocks)
        codec.write_dds(path, data.shape[1], data.shape[0], len(levels), payload, fourcc=b"DXT1")
        result = {"format": "DXT1", "mips": len(levels), "bytes": len(payload)}
        if role == "normal":
            result["convention"] = "DirectX -Y"
        return result

    def build_maps(self, slug, local, info):
        stem = self.stem_of(self.args.name or slug)
        out_dir = os.path.join(self.work, "build", "textures")
        os.makedirs(out_dir, exist_ok=True)
        tile = self.tile_m(info, self.args.tile_m)
        cls = self.spec_class(info)
        sizes = self.output_sizes()
        arm = self.load(local["arm"]) if "arm" in local else None
        source = self.load(local["diffuse"])
        diffuse = source[..., :3]
        h, w = diffuse.shape[:2]
        if float(source[..., 3].min()) < 0.98:
            self.say("note the diffuse has transparent pixels; this route writes opaque DXT1, alpha surfaces need cutout.sps or decal.sps with DXT5")
        ao = self.load(local["ao"])[..., :1] if "ao" in local else (arm[..., 0:1] if arm is not None else None)
        rough = self.load(local["rough"])[..., :1] if "rough" in local else (arm[..., 1:2] if arm is not None else None)
        metal = self.load(local["metal"])[..., :1] if "metal" in local else None
        if metal is None and arm is not None and float(arm[..., 2].max()) > 0.02:
            metal = arm[..., 2:3]
        if rough is None:
            self.say("note no roughness map found, the spec map is flat")
        linear = self.to_linear(diffuse)
        if ao is not None and self.args.ao_strength > 0:
            strength = min(1.0, self.args.ao_strength)
            linear = linear * ((1.0 - strength) + strength * np.clip(self.match(ao, w, h), 0.0, 1.0))
        if metal is not None and self.args.metal_darken > 0:
            linear = linear * (1.0 - min(1.0, self.args.metal_darken) * np.clip(self.match(metal, w, h), 0.0, 1.0))
        dw, dh = self.target_dims(w, h, sizes["diffuse"])
        diffuse_out = self.to_srgb(self.resample(linear, dw, dh))
        vectors = self.load(local.get("normal") or local["normal_dx"])[..., :3] * 2.0 - 1.0
        if "normal" not in local:
            vectors[..., 1] = -vectors[..., 1]
        nw, nh = self.target_dims(vectors.shape[1], vectors.shape[0], sizes["normal"])
        vectors = self.resample(vectors, nw, nh)
        normal_gl = vectors / np.maximum(np.linalg.norm(vectors, axis=2, keepdims=True), 1e-6) * 0.5 + 0.5
        gloss = 1.0 - np.clip(rough, 0.0, 1.0) if rough is not None else np.full((h, w, 1), 0.4, dtype=np.float32)
        gh, gw = gloss.shape[:2]
        base = cls
        if cls == "metal" and metal is not None:
            base = "matte"
        elif cls == "metal" and self.args.spec_class == "auto":
            base = "varnish"
        lo, hi = self.SpecClasses[base]["range"]
        spec = lo + (hi - lo) * gloss
        metal_share = 0.0
        if metal is not None:
            mask = np.clip(self.match(metal, gw, gh), 0.0, 1.0)
            mlo, mhi = self.SpecClasses["metal"]["range"]
            spec = spec * (1.0 - mask) + (mlo + (mhi - mlo) * gloss) * mask
            metal_share = float(mask.mean())
        sw, sh = self.target_dims(gw, gh, sizes["spec"])
        spec_out = np.repeat(np.clip(self.resample(spec, sw, sh), 0.0, 1.0), 3, axis=2)
        material_class = "metal" if metal_share >= 0.5 else base
        outputs = {}
        vram = 0
        for role, suffix, data in (
            ("diffuse", "", diffuse_out),
            ("normal", "_n", normal_gl),
            ("spec", "_s", spec_out),
        ):
            png = os.path.join(out_dir, stem + suffix + ".png")
            self.save_png(data, png)
            ow, oh = data.shape[1], data.shape[0]
            record = {
                "file": self.rel(png),
                "width": ow,
                "height": oh,
                "px_per_m": self.density(ow, oh, tile),
                "dxt1_kb": round(self.dxt1_bytes(ow, oh) / 1024.0, 1),
            }
            if role == "normal":
                record["convention"] = "OpenGL +Y in the PNG; export_map.py flips *_n.png to DirectX -Y when it encodes the DDS"
            if self.args.dds:
                dds = os.path.join(out_dir, stem + suffix + ".dds")
                record["dds"] = dict(self.encode_dds(data, role, dds), file=self.rel(dds))
            vram += self.dxt1_bytes(ow, oh)
            outputs[role] = record
            self.say(f"wrote {record['file']} {ow}x{oh} px_per_m={record['px_per_m']}" + (" dds=" + record["dds"]["file"] + " mips=" + str(record["dds"]["mips"]) if "dds" in record else ""))
        for note in self.notes(info, stem, tile, (dw, dh), (w, h)):
            self.say("note " + note)
        return {
            "stem": stem,
            "tile_m": list(tile),
            "uv": "1 UV = tile_m metres on each axis",
            "source_px": [w, h],
            "spec_class": cls,
            "metal_share": round(metal_share, 3),
            "ao_in_diffuse": round(min(1.0, self.args.ao_strength) if ao is not None and self.args.ao_strength > 0 else 0.0, 3),
            "material": {
                "map_forge_shader": "normal_spec.sps",
                "map_forge_bumpiness": 1.0,
                "map_forge_spec_int": self.SpecClasses[material_class]["intensity"],
                "map_forge_spec_falloff": round(25.0 + 75.0 * float(gloss.mean()), 1),
                "map_forge_spec_fresnel": self.SpecClasses[material_class]["fresnel"],
            },
            "samplers": {
                "DiffuseSampler": outputs["diffuse"]["file"],
                "BumpSampler": outputs["normal"]["file"],
                "SpecSampler": outputs["spec"]["file"],
            },
            "outputs": outputs,
            "vram_kb": int(round(vram / 1024.0)),
            "ship": True,
        }

    def write_manifest(self, group, key, entry):
        path = os.path.join(self.work, "source", "polyhaven", "manifest.json")
        data = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        data["source"] = "Poly Haven"
        data["site"] = self.Site
        data["license"] = "CC0-1.0"
        data["license_url"] = self.License
        data["api_terms"] = self.Terms
        data["attribution"] = "not required for CC0 assets; the credit lines are an optional thank-you"
        data.setdefault("textures", {})
        data.setdefault("hdris", {})
        data[group][key] = entry
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(path + ".tmp", path)
        return path


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ([] if "bpy" in sys.modules else sys.argv[1:])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--work", default="")
    shaping = argparse.ArgumentParser(add_help=False)
    shaping.add_argument("--size", type=int, default=512, choices=(128, 256, 512, 1024))
    shaping.add_argument("--normal-size", type=int, default=0, choices=(0, 128, 256, 512, 1024))
    shaping.add_argument("--spec-size", type=int, default=0, choices=(0, 128, 256, 512, 1024))
    shaping.add_argument("--name", default="")
    shaping.add_argument("--spec-class", default="auto", choices=("auto", "matte", "varnish", "glazed", "metal"))
    shaping.add_argument("--ao-strength", type=float, default=0.42)
    shaping.add_argument("--metal-darken", type=float, default=0.35)
    shaping.add_argument("--tile-m", type=float, default=2.0)
    shaping.add_argument("--dds", action="store_true")
    parser = argparse.ArgumentParser(prog="fetch_polyhaven.py", description="Poly Haven CC0 textures and preview HDRIs for map-forge")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", parents=[common])
    listing.add_argument("--kind", default="textures", choices=("textures", "hdris"))
    listing.add_argument("--query", default="")
    listing.add_argument("--category", default="")
    listing.add_argument("--attr", action="append", default=[])
    listing.add_argument("--tags", default="")
    listing.add_argument("--min-m", type=float, default=0.0)
    listing.add_argument("--max-m", type=float, default=0.0)
    listing.add_argument("--size", type=int, default=512, choices=(128, 256, 512, 1024))
    listing.add_argument("--limit", type=int, default=20)
    tree = sub.add_parser("categories", parents=[common])
    tree.add_argument("--kind", default="textures", choices=("textures", "hdris"))
    tree.add_argument("--depth", type=int, default=2)
    fetch = sub.add_parser("fetch", parents=[common, shaping])
    fetch.add_argument("--id", required=True)
    fetch.add_argument("--res", default="")
    fetch.add_argument("--format", default="", choices=("", "png", "jpg", "hdr", "exr"))
    fetch.add_argument("--max-mb", type=float, default=200.0)
    fetch.add_argument("--dry-run", action="store_true")
    convert = sub.add_parser("convert", parents=[common, shaping])
    convert.add_argument("--id", required=True)
    convert.add_argument("--src", default="")
    convert.add_argument("--res", default="")
    convert.add_argument("--offline", action="store_true")
    sys.exit(PolyHavenForge(parser.parse_args(argv)).run())


if __name__ == "__main__":
    main()
