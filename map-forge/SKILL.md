---
name: map-forge
description: Designs, builds, checks and exports 144-200 FPS FiveM maps (Sky AFK, lobby, warzone, garage hub, outpost, MLO) with shared PBR .ytd, day/night vertex colour, embedded lights and real GTA V props. Use for ปั้นแมพ, ทำแมพ, ymap, ybn, ytyp, MLO, afk zone, or maps players fall through, glowing at night or stuttering. Not for single props (use prop-forge) or smooth curved pieces (use sculpt-forge).
---

# Map Forge

Studio-grade FiveM maps: realistic, sharp, 144-200 FPS, minimal disk and VRAM. Formula: clean hero shell + world-scale tiled PBR + RAGE day/night vertex colour + embedded lights + real GTA V props. Budgets come from binary analysis of 12 production maps in 6 types; no mesh, texture or logo of another map is in this skill. Paths are relative to this folder.

## Quick path

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$mf = '<project>\.claude\skills\infrontofx\map-forge\scripts\blender'
& $blender -b -P "$mf\export_map.py" -- --spec work\<map>\source\map-spec.json --props work\<map>\build\props --textures work\<map>\build\textures --out work\<map>\<map>_pkg
& $blender -b -P "$mf\inspect_map.py" -- --dir work\<map>\<map>_pkg\stream --spec work\<map>\source\map-spec.json
```

1. Brief: map type (Sky AFK, Spawn Lobby, Airdrop/Warzone, Garage/Hub, Rebel/Outpost, City/MLO), brand and palette, world coordinates `(x, y, z)`, warp points, zone bounds, target budgets from `references/studio-benchmarks.md`.
2. New map: concept images from 2 views (3/4 overview, player eye level); the owner approves look and layout before any 3D.
3. Copy `templates/map-spec.example.json` to `work/<map>/source/map-spec.json`: `anchor`, architecture pieces (modular or hero shell), GTA V props from `references/gta-prop-catalog.md`, `Drawable.lights`, `vanilla_ytyps`.
4. Build with the Blender 4.2.3 CLI (saves `BLENDER-v402`, opens in 4.2.3 and 5.3): real architecture (columns, beams, plinths, trusses, roofs, awnings, stairs, fences, planter rims), no bare boxes or cartoon lumps. World-scale tiled UV on `"UVMap 0"`, shaders per `references/shaders-lighting-vcol.md`, Cycles AO baked into `"Color 1"` with `G = 0` outdoors (raise `G` only under lamps or indoors). Separate collider `<id>_col_0` on the real floor (under 0.02 m off at warp points).
5. Visual QA in at least 6 views (3/4 overview, top-down, player POV at the warp, hero close-up, seating or walkway detail, underside and edges), rendered in 4.2.3 or live in Steam Blender 5.3 MCP per `references/antigravity.md`; open every image.
6. Export without `--factory-startup` (Sollumz and PyMateria must load) -> `.ydr`, shared `.ytd`, static world `.ybn`, `.ytyp`, `.ymap`, `_manifest.ymf`, resource folder with `fxmanifest.lua` -> `MAP_EXPORT_PASS ydr_ok=<n> fail=0`.
7. Inspect `stream/` until `MAP_INSPECT_PASS fail=0` (RSC7 headers, FVF `TEXTURE0`/`TANGENT0`/`DIFFUSE`, YTD VRAM and mips, YBN floor Z and `CollisionFlags`, YMAP `content_flags`, quaternions, extents, `_manifest.ymf`).
8. Deliver: place the resource, back up config first, report Blender/PyMateria checks apart from what waits for the owner's server test. Skill edited: `scripts/sync-antigravity.ps1`.

## Choose

| Situation | Use |
| --- | --- |
| layout | patterns in `references/studio-benchmarks.md`: single hero shell + vanilla dressing (fastest), modular kit + shared PBR YTD, multi-YMAP + MLO, enclosed sky arena, organic island plaza for themed props |
| model or place | model only the hero shell (5-15%: plaza, rims, stairs, pavilion, roof, arch, brand sign, fountain); trees, bushes, flowers, street lamps, benches, bins, bollards, fences are GTA V props in the `.ymap` (85-95%, 0 MB extra VRAM, wind, auto night lamps) |
| large floors | world-scale tiled PBR (`1 UV = 1.5-4.0 m`) with `normal_spec.sps` (diffuse, DirectX `-Y` normal, specular) for 250-500 px/m; never one smart-UV atlas on a 60-120 m plaza (~10 px/m, blurry plastic) |
| texture sizes | swatches `4x4`-`32x32` for flat colour and trim, tiles `256` or `512`, `1024` only for the main logo or hero floor; PCA DXT1 opaque, DXT5 only alpha or decals; one shared `.ytd` (0.6-5 MB VRAM) |
| vertex colour `Color 1` | R daylight ambient + AO, G night artificial light, B indirect AO; outdoor base `(255, 0, 255, 255)`, AO multiplied into R and B |
| night light | `Drawable.lights` (warm `POINT`, `SPOT` on signs, 12-tri invisible emitter) with `time_flags = NIGHT`, plus GTA lamps `prop_streetlight_11c`, `prop_wall_light_15a`, `prop_ind_light_03c` |
| sky map (no falling) | embedded `BoundGeometryBVH` in the `.ydr` and a static world `.ybn`; `.ymap` `content_flags = 65` (HAS_ENTITIES_HD + HAS_PHYSICS), `physics_dictionaries = [ybn_name]` |
| free textures and HDRI | `scripts/blender/fetch_polyhaven.py` (`--dry-run` first) per `references/polyhaven-cc0.md` |
| curved hero pieces (round rims, arc stairs, sweeping rails, arches, planters, islands) | `sculpt-forge`, then `export_map.py` here |
| single props | `prop-forge` |

## Hard rules

- **Golden rules**: the model/place split, tiled PBR, texture tiers, `G = 0` outdoors, night lights and sky-map dual collision in Choose are the studio standard (full text in `references/details.md`).
- **100% original**: never copy meshes, textures, `.ydr`, `.ytd`, logos or layouts from other studios' maps; use only engineering principles and standard proportions.
- **Never touch `.fxap`**: never edit, delete or try to open a resource with `.fxap`; if the map overlaps one, ask the owner to move or disable it in `server.cfg`.
- **Blender**: build and export with the 4.2.3 CLI; Windows paths with `[ ]` use `-LiteralPath` (`references/antigravity.md`).
- **Source**: edit only `.claude/skills/infrontofx/map-forge`, never `.agents/skills/map-forge`; sync after edits.
- **Honest report**: `MAP_INSPECT_PASS fail=0` and EEVEE renders prove file structure and first look, not a FiveM test; say it is not walked in game until the owner tests and confirms.
- **Lua** (warp points, AFK zones): root `SKILL.md` only: OOP module table, no comments, no file-level `local function`, 4 spaces, double quotes, trailing commas.

## Done when

- [ ] New map: concept approved; budgets from `references/studio-benchmarks.md` met
- [ ] Six QA views opened and clean
- [ ] `MAP_EXPORT_PASS ... fail=0` and `MAP_INSPECT_PASS fail=0`; no outdoor `G > 40` warning
- [ ] Collider within 0.02 m of the floor at warp points; sky maps have both collisions
- [ ] Resource placed, config backed up, no `.fxap` touched
- [ ] Report splits Blender/PyMateria checks from the owner's in-game test; skill edits synced

## References

| Need | Open |
| --- | --- |
| Budgets per map type, layout patterns, shell vs modular vs MLO, what looks expensive or cheap | `references/studio-benchmarks.md` |
| 15 RAGE shaders with real values, vertex colour `#FF00FF`, DirectX `-Y` normals, `Drawable.lights`, 12-tri emitter | `references/shaders-lighting-vcol.md` |
| Real GTA V props, Z offsets, `_manifest.ymf`, `h4_*` Cayo caution | `references/gta-prop-catalog.md` |
| Export, collision, YMAP/YTYP/YBN/YMF, MLO, inverted quaternions, shared YTD, install, QA, proven log | `references/pipeline.md` |
| Antigravity + Blender MCP (4.2.3 vs 5.3 `BLENDER17`), `-LiteralPath`, 6-view checklist | `references/antigravity.md` |
| Poly Haven CC0 PBR and HDRI: choose, convert normals, roughness to spec, pow2, DDS, shared `.ytd` | `references/polyhaven-cc0.md` |
| Golden rules in full, commands, tool catalog, original Thai steps and rules | `references/details.md` |
