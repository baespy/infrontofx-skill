---
name: weapon-forge
description: Builds FiveM weapon skin sets for 1nfx_weaponskin (Blender model, .ydr/.ytd, original .ypt hold/hit/kill particles, hit/kill screens, sounds, integration files) and splits AI weapon sets into slots. Use for สกินอาวุธ, weapon skin, ปั้นอาวุธ, ptfx, .ypt, particle, เสียงตี, เสียงฆ่า, or resources/[weapon] work. Not for props or maps (use prop-forge, map-forge).
---

# Weapon Forge

One spec builds a skin set: model, textures, icons, `.ypt` particles, overlays, sounds, integration files. Particles matter most to the owner: every set gets its own Hold, Hit and Kill effects per `references/particles.md` with at least one layer unique to the set. Paths are relative to this folder; `$blender` is Blender 4.2.3 (`scripts/doctor.ps1` prints where).

## Quick path

1. `scripts/doctor.ps1` -> READY or MISSING per tool. `references/server-catalog.md` lists taken names and skins to study.
2. Brief: set name, weapons, style (offer families from `references/style-families.md`; a new style or image is described on its 5 axes first).
3. Copy `templates/skin-spec.example.json` to `weapon_<id>/source/spec.json`; check originality (Hard rules).
4. Model: `& $blender -b --factory-startup -P scripts\blender\forge_weapon.py -- --spec <spec.json> --out <dir>` -> `@@FORGE done`; open `<id>_sheet.png` against the family DNA and look criteria; repeat, then add `--bake 1024 --icons`. AI models: see Choose, preview before bake. Before any bake: `scripts/blender/validate_model.py` `RESULT fail=0` and the bone contract.
5. Particles (read `references/particles.md` and the ceilings in `references/bone-and-memory-safety.md`): `scripts\ptfx\ptfx.ps1 themes`, `new -Theme <t> -Name <id>`, tune palette and signature layer (set sheet, `glyph`, owner image), `build -Spec design.json -Out <stream>`. Pass = `RESULT ok`, every `ERROR`/`WARN`/`NOTE` read, no unexplained `WARN`; open `<dict>.preview.png` and `<dict>.sprites.png`; iterate timing, colour, size.
6. Spec `fx.ptfx` (or `fx.theme`, which also picks screen and sound presets), then `scripts\new-skin.ps1 -Spec <spec.json> -OutRoot <[weapon]>` -> `.ypt`, screens (`center alpha = 0`), hit and kill sounds, Lua, meta, SQL. Look at every image.
7. Export: A) Sollumz (ask before installing) or B) `scripts/blender/export_ydr.py` (read its fixes in `references/modeling-pipeline.md`); `scripts\inspect-ydr.ps1 -Path <x.ydr> -Slot <slot>` until `RESULT fail=0`.
8. Mandatory gate: `references/bone-and-memory-safety.md` item by item on `.ydr`, `.ytd`/`.ypt`, meta (`<AttachBone>gun_root</AttachBone>`, at most 12 per block) and Lua.
9. Back up, integrate per `references/integration.md`, `scripts\check-skin.ps1 -SkinType <X>` until `RESULT fail=0`; then `scripts/catalog-weapons.ps1` (server skins changed) and `scripts/sync-antigravity.ps1` (skill edited). The owner tests in game.

## Choose

| Situation | Use |
| --- | --- |
| standard slots, no source model | `scripts/blender/forge_weapon.py` (7 slots, 20+ styles) |
| AI set or piece in one file | `scripts/blender/split_ai_set.py` + `templates/ai-set.example.json` |
| one bought or AI model for a slot | `scripts/blender/import_ai_model.py` |
| interactive modeling | Antigravity + Blender MCP, `references/antigravity.md` |
| effect near a theme / fully custom | `ptfx.ps1 new -Theme` (27 themes) / `templates/ptfx-design.example.json` |
| study an existing effect | `ptfx.ps1 inspect`, `textures`, `decompile`, `census` |
| sale-grade 3D frames, sprites, ribbons | `scripts/blender/render_fx_assets.py` |
| quick overlays or sounds | `scripts/make-screen.ps1`, `scripts/make-sound.ps1` |

## Hard rules

- **Bone and memory gate**, never skipped: `.ydr` has `Gun_Root` at (0,0,0) identity, no child bones on the origin, `ChildParentIndices` in groups of 4, `BlendWeights` summing to 1.0, no NaN normals, no orphan datablocks. Lua keeps `boneIndex` (`GetPedBoneIndex`, `GetEntityBoneIndexByName`) apart from `boneTag` (`57005`, `28422`, `31086`), checks `DoesEntityExist` and `boneIndex ~= -1` with a safe fallback before natives, never spawns effects or props at world (0,0,0). Every `Request*` has a timeout and its release (`RemoveNamedPtfxAsset`, `StopParticleFxLooped` + `RemoveParticleFx`, `SetModelAsNoLongerNeeded` + `DeleteEntity`, `RemoveAnimDict`, `RemoveWeaponAsset`, `SetStreamedTextureDictAsNoLongerNeeded`) at weapon switch, skin switch, ped change, death or respawn and `onResourceStop`.
- **Particles**: `decompile` and `textures` output is study material; never ship another creator's textures; `-AllowDerived` only for our own files. Dictionary and effect names start with the set id; at most 7 layers per effect. Hold and Hit ride bones whose axes differ from the world: `gravity`, not `dir: "up"`. A theme is a start; a sold set has its signature layer.
- **Originality**: style families come from other creators (some say "do not distribute or modify"): direction only. Never copy their models, logos, watermarks, set names or mascots; new name and symbol each time, different at least in main shape and signature pattern; no real trademarks.
- **Locked files**: never decrypt, extract or edit `.fxap` (escrow) resources; reference only their file lists. Open for study: `weapon_elys`, `weapon_extreme`, `weapon_lego`, `weapon_white_rabbit`, `weapon_eclipse`, `weapon_halloween`, `weapon_flood_bite`, `weapon_effects`, `weapon_core`. Never copy another creator's dictionary; outside study folders are direction only.
- **System files**: `new-skin.ps1` never touches live files; back up meta, config and `items.json` before edits; SQL and server restarts need the owner's OK.
- **Paths**: PowerShell on `[resources]`, `[weapon]`, `[1nfx]`, `[core]` paths uses `-LiteralPath`; copy bracket folders with `robocopy` or `[System.IO.File]::Copy`, not `Copy-Item -LiteralPath "$src\*"`.
- **Tools**: particles, screens, sounds need only Windows PowerShell 5.1; models need Blender (+ Antigravity `blender` MCP); never add scripts needing a separate Python or Node.
- **Collaboration**: other agents edit this folder too: check modified times first, one agent per skin. Edit only `.claude/skills/infrontofx/weapon-forge`, never `.agents/skills/weapon-forge`; sync after each source edit.
- **Honest report**: split checked from untried in game. `RESULT ok` means valid structure and real-file value ranges, not in-game proof; previews are simulations; synthesized sounds are unheard until the owner judges. Owner in-game results update the recipe defaults and "สิ่งที่พิสูจน์แล้ว" in `references/particles.md`.
- **Lua**: root standard, 4 spaces, double quotes, trailing commas, no comments.

## Done when

- [ ] Name free, originality checked, sheet and icons match the family DNA
- [ ] Particle build `RESULT ok`, no unexplained `WARN`; preview and sprites opened; Hold, Hit, Kill plus a signature layer
- [ ] `inspect-ydr.ps1` and `check-skin.ps1` `RESULT fail=0`; bone and memory gate passed
- [ ] Backups before live edits; SQL and restarts left to the owner; catalog and Antigravity copy updated; report splits checked from untested in game

## References

| Need | Open |
| --- | --- |
| Pre-ship gate; style families and `style` values | `references/bone-and-memory-safety.md`; `references/style-families.md` |
| Sizes, budgets, bones, slots; modeling, bake, export | `references/weapon-anatomy.md`; `references/modeling-pipeline.md` |
| Themes, design JSON, layer recipes, sheets, axes, proven facts, Lua config | `references/particles.md` |
| Advanced keyframes, `Kill.Prop`, shader tiers, past mistakes | `references/vfx-weapon-field-study.md` |
| `.ypt` format, units, lint, game textures, `ptfx.ps1` commands | `references/ptfx-format.md` |
| Screens, sounds; integration, QA; Antigravity MCP | `references/screen-sound.md`; `references/integration.md`; `references/antigravity.md` |
| Server skins and used names | `references/server-catalog.md`, `references/server-catalog.json` |
| Every script, tool locations, original Thai steps and rules | `references/workflow.md` |
