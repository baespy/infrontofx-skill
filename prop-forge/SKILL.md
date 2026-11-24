---
name: prop-forge
description: Builds toy-brand FiveM prop sets (signs, ATM, safe, stash crate, loot chest, workbench, mascot marker) in Blender, validates, exports .ydr/.ytd/.ytyp/.ycd and wires them into 1nfx_prop. Use for ปั้น prop, ทำป้าย, ytyp, stream prop, spawn code, props from a clip or image, rebranding a set, exporting sculpt-forge output. Not for smooth organic shapes (use sculpt-forge) or maps (use map-forge).
---

# Prop Forge

Builds a server prop set where every piece reads as one brand (one palette, mascot, crowns, dripping slime, sticker wordmarks): a `.blend` per piece, previews, a shared palette texture, colliders and a tris report; one mesh per piece, origin at floor centre, front -Y, metres. Paths are relative to this folder.

## Quick path

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$pf = '<project>\.claude\skills\infrontofx\prop-forge\scripts\blender'
& $blender -b --factory-startup -P "$pf\forge_prop.py" -- --spec work\source\props.json --out work\build --lineup
& $blender -b --factory-startup -P "$pf\validate_prop.py" -- --blend work\build
& $blender -b -P "$pf\export_prop.py" -- --blend work\build --out work\stream --format native --max-res 1024 --shared-ytd <set>_tex
```

1. Brief: set name (`set` starts with `1nfx_`), brand, main palette, prop list. Make a 3/4 Pop-Mart/vinyl concept image of every piece first, matching the server's official logo and mascots exactly; it is the 1:1 reference for modeling and QA.
2. Pick the builder (Choose). JSON route: copy `templates/prop-spec.example.json` to `<job>/source/props.json`.
3. Build -> `RESULT props=<n> warnings=0`; `--only <id>` rebuilds one piece.
4. Open every `<id>_preview.png` beside its concept and the look criteria in `references/style-toybrand.md`. Reject boxy bodies, stuck-on round faces, crooked clip ears or frames, decimation dents. Refine proportions, light, stars, ears, awnings and edges inside the low-poly budget (2,400-4,800 tris) without auto-decimate; `--lineup` renders `lineup.png` (2400x1200).
5. Optional art: the text and art helpers of `scripts/blender/kawaii_studio.py` or transparent PNG decals per `references/pipeline.md`.
6. Validate -> `RESULT fail=0 warn=0` for every file.
7. Export (no `--factory-startup`; `--max-res 512` for VRAM-tight sets) -> `.ydr`, `.ytyp`, `.ycd`, one shared `.ytd`, PyMateria FVF auto-check -> `RESULT ok=<n> fail=0`.
8. Wire in per `references/integration.md` (stream, `data_file "DLC_ITYP_REQUEST"`, spawn code that frees memory); back up every live file first.
9. Skill edited: `scripts/sync-antigravity.ps1`, then `-Check` (exit 0); if it refuses because the `.agents` copy changed, move those edits into the source first (`-Force` discards them). Report what was checked and what is untested in game.

## Choose

| Situation | Use |
| --- | --- |
| JSON spec set, street vinyl look | `scripts/blender/forge_prop.py`: 15 archetypes, `"style": "vinyl_toy"` or `"kawaii_billie"`, `"low_poly": true`, `"animate": true` rigs, `--bake 512` for game use |
| Kawaii / Billie School theme: crisp low-poly, 4-house mascots, 3D architecture instead of flat signs | `KawaiiBuilder(..., low_poly=True)` in `scripts/blender/kawaii_studio.py` + `scripts/blender/billie_v7_assets.py` (settings in `references/tools.md`) |
| organic piece from an image (full mascot, figure on a base, cloud, 3D logo, animal cabinet) | default: build it in Antigravity + Blender MCP (ellipsoids, voxel remesh, palette) per `references/image-to-3d.md`; external image-to-3D only when the owner orders it, then `scripts/blender/import_ai_prop.py` |
| designer-toy smooth surface (puffy, filleted, inflated letters, drips) | `sculpt-forge`, then `validate_prop.py` and `export_prop.py` here |
| studio-grade set | body from a builder, mascot and crown from the organic route |
| animation preview; `.ycd` without CodeWalker | `scripts/blender/render_anim_preview.py`; `scripts/blender/ycd_rsc7.py` |
| a whole map or map pieces | `map-forge` |

## Hard rules

- **Originality**: reference clips belong to other servers or creators, style direction only. Never feed clip frames, real toy photos or copyrighted characters to image-to-3D; never use their brand names, logos, mascots or textures. Every set has our own brand name in the spec; no real trademarks on props.
- **Coordinate contract**: one mesh named like the file (`[a-z0-9_]`), transforms applied, lowest point at z = 0 centred on X/Y, front -Y, metres, colliders `<id>_col_N` (markers have none). Never rename or move the origin once it is wired into the server.
- **Budget**: tris within `references/archetypes.md`; at most 4 materials (diffuse, emissive, decal); power-of-two textures up to 2048; one shared palette per set; details under 2 cm are decals, not geometry.
- **System files**: never touch `.fxap` resources. Editing `fxmanifest.lua`, another resource's config, or restarting the server needs a backup and the owner's OK.
- **Tools**: Blender 4.2.3 only to build and check, no add-ons or separate Python; Sollumz only at export, run without `--factory-startup`. PyMateria has a licence with Take-Two/Rockstar: never install it for the owner.
- **Collaboration**: Antigravity, Codex and Claude Code edit this folder too. Edit only `.claude/skills/infrontofx/prop-forge`, never `.agents/skills/prop-forge`; one set per agent; never two agents driving one live Blender.
- **Honest report**: `RESULT fail=0` means the `.blend` meets the contract; previews are Eevee renders. Until the owner exports and sees it in game, say it is untested in game; record the owner's in-game results under "สิ่งที่พิสูจน์แล้ว" in `references/integration.md`.
- **Lua** (spawn, interaction): root `SKILL.md` rules, OOP module table, no comments, no file-level `local function`, 4 spaces, double quotes, trailing commas, `lib.spawn.pointProp` from `1nfx_lib`.

## Done when

- [ ] Concept art made and matched 1:1; our own brand name in the spec
- [ ] Every preview checked against the look criteria; `lineup.png` rendered
- [ ] Tris within budget, at most 4 materials, power-of-two textures, one palette
- [ ] `validate_prop.py` `RESULT fail=0 warn=0` for every file
- [ ] Export `RESULT ok=<n> fail=0`; `.ydr`, `.ytyp`, shared `.ytd` written (`.ycd` when animated)
- [ ] Live files backed up and wired per `references/integration.md`
- [ ] Skill edits synced (`-Check` exit 0); report names what is untested in game

## References

| Need | Open |
| --- | --- |
| Art direction, colours, proportions, composition rules, look criteria, vinyl and kawaii standards, new style from images | `references/style-toybrand.md` |
| Image to prop: MCPs, concept sheet prompt, image-to-3D settings, `import_ai_prop.py`, budgets, moving parts | `references/image-to-3d.md` |
| 8 studied studio brand sets: standard pieces, shape languages, piece recipes, animation, checklist | `references/showcase-study.md` |
| Archetypes, sizes, parameters, tris budgets, spec schema, new archetypes, KawaiiBuilder | `references/archetypes.md` |
| Coordinate contract, palette and bake, AI decals, collision, LOD, Sollumz export, ytyp, `.ycd` | `references/pipeline.md` |
| Antigravity + Blender MCP, `.blend` 4.2 vs 5.3, other agents | `references/antigravity.md` |
| fxmanifest, stream names, spawn code, marker spin and float, in-game QA, proven facts | `references/integration.md` |
| Every script and option, kawaii engine details, original Thai steps and rules | `references/tools.md` |
| Sample set targets | `references/targets/` |
