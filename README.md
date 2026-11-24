# infrontofx-skill

An all-in-one agent skill pack for a FiveM roleplay server (`1nfx_*` resources). It covers writing Lua and NUI/DUI code, building weapon skins, building branded props, building high-FPS maps, and making support posters. It works with Claude Code, Google Antigravity, Codex and other agents that read `SKILL.md` files.

The root `SKILL.md` opens with an auto-routing table (task signal to the skills to load, including chains such as sculpt-forge then prop-forge), so an agent picks the right skills without being told and opens only the files a task needs. Every `SKILL.md` is a short English router in the same order (Quick path, Choose, Hard rules, Done when, References) and keeps long text in its own `references/`. `scripts/validate-skill.mjs` enforces the budgets: descriptions up to 450 characters, the root `SKILL.md` up to 10 KB, each sub-skill up to 8 KB.

| Category | What it does | Start here |
| --- | --- | --- |
| [Coding](#coding) | Write, rewrite, review and optimize Lua 5.4 resources and NUI/DUI pages to the house standard | `SKILL.md` |
| [Work discipline](#work-discipline) | Think first, plan per resource, debug to the root cause, verify with evidence before saying done, lazy-senior review and audit, session handoff | `dev-flow/SKILL.md` |
| [Terse replies](#terse-replies) | Short, token-saving Thai replies that keep every technical fact exact | `terse/SKILL.md` |
| [Weapon modeling](#weapon-modeling) | Weapon skin sets: Blender models, `.ydr`/`.ytd`, custom particles (`.ypt`), hit/kill screens and sounds | `weapon-forge/SKILL.md` |
| [Prop modeling](#prop-modeling) | Branded toy-style props: signs, ATM, safe, crates, loot chest, crafting bench, floating marker | `prop-forge/SKILL.md` |
| [Smooth sculpting](#smooth-sculpting) | Seamless designer-toy forms from signed distance fields: puffy bodies, filleted joins, inflated letters, drips, organics, plus smooth curved map pieces, reduced to game budgets with transferred normals | `sculpt-forge/SKILL.md` |
| [Map building](#map-building) | High-FPS FiveM maps (Sky AFK, lobby, warzone, garage hub, outpost, MLO): shared PBR `.ytd`, vertex-colour day/night, embedded lights, `.ymap`/`.ybn` export and binary inspection | `map-forge/SKILL.md` |
| [Posters](#posters) | Support / welfare / giveaway posters from character art, item icons and a logo | `poster-forge/SKILL.md` |

## Install

Every skill is a plain folder with a `SKILL.md`, so any agent that reads Agent Skills can use it, and every agent gets the same routing table in `AGENTS.md`. You never have to name a skill: the agent picks it from the task.

| Agent | Install | How it picks skills |
| --- | --- | --- |
| Claude Code (plugin, recommended) | `/plugin marketplace add baespy/infrontofx-skill`, then `/plugin install infrontofx-skill@infrontofx` | Automatic. The plugin's `UserPromptSubmit` hook (`hooks/hooks.json`) reads each prompt and tells the model which skills to load (about 20-40 tokens, nothing when no rule matches). It needs bash, which Claude Code on Windows already uses through Git Bash |
| Claude Code (project copy) | `git clone https://github.com/baespy/infrontofx-skill.git .claude/skills/infrontofx` | Skill descriptions. For the hook too, add a `UserPromptSubmit` command hook to `.claude/settings.json` that runs `bash "$CLAUDE_PROJECT_DIR/.claude/skills/infrontofx/hooks/skill-router.sh"` |
| Google Antigravity (all workspaces) | Clone the repo, then `powershell -ExecutionPolicy Bypass -File scripts/install-agents.ps1 -Tool antigravity`. It writes a native plugin to `~/.gemini/config/plugins/infrontofx-skill` with the 8 skills and a `PreInvocation` routing hook, then runs `agy plugin validate`. Run it again after `git pull`; `-Check` reports a stale copy, `-Uninstall` removes it. Do not use `agy plugin install` on this repo: it converts the Claude layout and ends up with 0 skills | Automatic. The plugin hook runs `hooks/skill-router.sh` through Git Bash (found at install time) |
| Google Antigravity (one workspace) | Run each forge's `<forge>/scripts/sync-antigravity.ps1` to copy it into the workspace's `.agents/skills/<name>/` (edit the `.claude/skills` copy, never the `.agents` copy) | `AGENTS.md`, `GEMINI.md` |
| OpenAI Codex (GPT) | `powershell -ExecutionPolicy Bypass -File scripts/install-agents.ps1 -Tool codex`. It copies the pack to `~/.codex/skills/infrontofx` as one folder and moves older copies of these skills to `~/.codex/skills-backup/` so nothing is listed twice | `AGENTS.md` and the root `SKILL.md` table, which point to each sub-skill |
| Gemini CLI | `gemini extensions install https://github.com/baespy/infrontofx-skill` | `GEMINI.md` (imports `AGENTS.md`) |
| Cursor | Keep the pack in the workspace | `.cursor/rules/infrontofx.mdc` |
| GitHub Copilot | Keep the pack in the workspace | `.github/copilot-instructions.md` |

The routing rules live in one data file, `hooks/skill-routes.tsv`, and the same table is written out in `AGENTS.md`; `scripts/validate-skill.mjs` checks that the two agree. Check each tool's own docs if an install command has changed.

How routing behaves: every matching skill is named, with `infrontofx` and `dev-flow` always kept when they match (up to 5 in total); `infrontofx` always brings `dev-flow`; a sculpt request that mentions export or going in game also brings `prop-forge`. The hook speaks both formats: Claude Code and Codex `UserPromptSubmit` (`hookSpecificOutput.additionalContext`) and Antigravity `PreInvocation` (`injectSteps`, `{}` when nothing matches); repeats of the same prompt in a session print nothing.

## Tests

`node scripts/test-pack.mjs` runs every prompt in `tests/hooks/cases.tsv` through the hook in both formats (expected skills, JSON shape, repeat handling) and every fixture in `tests/lint/` through the linter (expected and forbidden rules), then lints the resource template. CI runs it on every push next to the validator. Add a row to `tests/hooks/cases.tsv` whenever a real prompt routes wrong, and a fixture to `tests/lint/` whenever the linter misses or wrongly flags something.

Checked on Windows 10: the Claude Code plugin install, the Antigravity 1.5.16 plugin (`agy plugin validate --strict`: skills 8, hooks 1, hook run through `cmd /c`) and the Codex 0.171 copy. Gemini CLI, Cursor and Copilot entry files are provided but were not run.

---

## Coding

The house standard for FiveM Lua and NUI/DUI. The goal: every resource behaves exactly as before, with shorter, faster code and no duplication.

**Rules in brief**

- OOP only: one module table per side, every function is a method, no file-level `local function`, no file-level constants
- No comments in shipped code (Lua, JS, CSS, HTML)
- No `FC` adapter table and no `config/function/` folder; integrations live in `core/` as methods
- `@1nfx_lib/init.lua` is the shared runtime (points, zones, cache, spawn, callbacks, streaming loaders with timeouts)
- The server decides every value (items, money, prices, cooldowns, distance) and validates and throttles every payload
- Clean up everything in `onResourceStop` and `playerDropped`; secrets stay server-side

**What is inside**

| Path | Contents |
| --- | --- |
| `SKILL.md` | Auto-route table, quick path, decisions, hard rules and owner orders |
| `skills/common/` | Style, architecture, config, core API, events, runtime, security, performance, networking, database, natives, 1nfx_lib, debugging |
| `skills/ui/`, `NUI_DUI.md` | NUI bridge, 1nfx design system, vanilla, React/Vite, Vue/Svelte, DUI |
| `references/` | Core (ESX-compatible) API, pNotify, infrontofx FiveM notes, the full house-standard text with examples (`references/house-standard.md`) |
| `rules/contracts.md` | Cross-resource contracts |
| `memory/` | Gotchas and research learned on the live server (each entry has a date and game build) |
| `checklists/` | New-resource and review checklists |
| `templates/resource/` | A reference resource that passes the linter |
| `TOOLING.md` | Token-saving workflow, cross-session memory, MCP notes |

**Tools** (Node 22+)

```bash
node scripts/lint-resource.mjs <resource-folder>
node scripts/new-resource.mjs <name> --destination <path>
node scripts/validate-skill.mjs
```

The linter checks for comments, balanced blocks, `FC` usage, file-level `local function` and constants, undeclared `scriptname`, string-built SQL, hard-coded webhooks, NUI callbacks that never call `cb`, and manifest problems.

---

## Weapon modeling

`weapon-forge/` builds a complete weapon skin set from one JSON spec: models, textures, icons, original particles, full-screen hit/kill overlays, sounds and the integration files for `1nfx_weaponskin`.

| Area | Highlights |
| --- | --- |
| Style | 21 style families with composition rules; describe a new style from a reference image on 5 axes |
| Modeling | `forge_weapon.py` builds 7 weapon slots in 20+ styles; `split_ai_set.py` and `import_ai_model.py` turn Tripo/Meshy/Hunyuan models into proper weapon slots |
| Export | `export_ydr.py` writes `.ydr` (RSC7), `.ytd` and DXT5 `.dds` without Sollumz; `inspect-ydr.ps1` checks the binary |
| Particles | `ptfx.ps1` builds original `.ypt` files from a design: 27 themes, 82 sprites, 69 layer recipes, lint and preview renders |
| Screen & sound | 17 full-screen overlay styles and 18 synthesized sounds |
| Safety gate | Bone contract, `(0,0,0)` effect guard and streaming-release rules in `weapon-forge/references/bone-and-memory-safety.md` |
| Antigravity | Blender MCP (26 tools) workflow in `weapon-forge/references/antigravity.md` |

Needs Blender 4.2+, Windows PowerShell 5.1 and .NET (bundled with Windows). Run `weapon-forge/scripts/doctor.ps1` to check the machine.

---

## Prop modeling

`prop-forge/` builds a set of server props that share one brand: one palette, a mascot, crowns, dripping slime and sticker-style wordmarks. One JSON spec drives the whole set. Each prop is generated in Blender from bevelled primitives and joined into one mesh, with its origin at floor centre and its front facing -Y. Each prop comes out with collision boxes and a triangle report, and every prop in the set shares one 256x256 palette texture.

| Archetype | In-game use | Default size (m) | Triangle budget |
| --- | --- | --- | --- |
| `sign_post` | Garage / impound point, arrow sign | 1.67 x 0.58 x 2.55 | 14k |
| `kiosk_sign` | Shop sign | 0.96 x 0.44 x 1.35 | 11k |
| `atm` | ATM | 0.96 x 0.77 x 1.71 | 12k |
| `safe` | Safe / house storage | 1.10 x 1.02 x 1.11 | 14k |
| `crate` | Stash, airdrop, reward box | 1.34 x 1.17 x 1.03 | 12k |
| `chest` | Open loot chest with coins | 0.81 x 0.61 x 0.80 | 10k |
| `workbench` | Crafting bench with tool board | 2.02 x 0.92 x 2.26 | 18k |
| `mascot_marker` | Floating marker above an interaction point | 1.00 x 0.64 x 0.91 | 5k |

**Workflow**

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
& $blender -b --factory-startup -P prop-forge\scripts\blender\forge_prop.py -- --spec props.json --out build --lineup
& $blender -b --factory-startup -P prop-forge\scripts\blender\validate_prop.py -- --blend build
& $blender -b -P prop-forge\scripts\blender\export_prop.py -- --blend build --out stream --format cwxml
```

Export needs the Sollumz 2.9+ extension with its szio dependency. Run it without `--factory-startup` so the extension loads. `--format native` writes binary `.ydr`/`.ytyp` directly but also needs Sollumz's optional PyMateria package, which has its own licence agreement. `--format cwxml` writes CodeWalker XML that CodeWalker converts to binary.

1. Copy `prop-forge/templates/prop-spec.example.json` and set the brand, the palette and the list of props
2. Build, then look at `lineup.png` and every `<id>_preview.png`; rebuild single props with `--only <id>`
3. Add AI-generated sticker art as decals when geometry is not enough (uses the poster-forge image scripts)
4. Run `validate_prop.py` until it reports `fail=0`
5. Run `export_prop.py`, which drives Sollumz to write one `.ydr` (texture and collision embedded) and one `.ytyp` per prop, then stream them from a prop resource
6. Spawn props with `lib.spawn.pointProp`, which creates them near the player and releases them when the player leaves

**References:** style DNA and look checklist (`prop-forge/references/style-toybrand.md`), archetypes and how to add one (`prop-forge/references/archetypes.md`), finishes, decals, collision, LOD and Sollumz export (`prop-forge/references/pipeline.md`), Antigravity and Blender MCP (`prop-forge/references/antigravity.md`), resource and spawn code (`prop-forge/references/integration.md`).

**Status:** tested on Blender 4.2.3 with Sollumz 2.9.1. All 9 example props build, validate with `fail=0` and export as native binary `.ydr`/`.ytyp` (RSC7). A re-import in Sollumz shows the mesh, the shaders, the embedded texture and the collision. Loading the props in game is not tested yet.

---

## Map building

`map-forge/` designs, builds, checks and exports FiveM maps that hold 144-200 FPS. It uses a clean hero shell, world-scale tiled PBR textures in one shared `.ytd`, RAGE day/night vertex colour, lights embedded in the drawable, and real GTA V props for dressing instead of hand-made trees and clutter. The budgets per map type (draw calls, triangles, VRAM, disk, entity mix, collision layout) come from studying production maps; see `map-forge/references/studio-benchmarks.md`.

| Map type | Typical layout |
| --- | --- |
| Sky AFK / floating plaza | 1-12 custom `.ydr`, shared `.ytd` 1-5 MB, embedded + static `.ybn` |
| Spawn / select lobby | 1-4 custom `.ydr`, shared `.ytd` under 2.5 MB |
| Airdrop / warzone arena | 1-3 custom `.ydr` reused across zone `.ymap` files |
| Garage / town hub | 4-16 custom `.ydr`, `hi@`/`ma@` collision split |
| Rebel / industrial outpost | 2-5 custom `.ydr`, mostly vanilla dressing |
| Building / hospital / MLO | 5-15 custom `.ydr`, MLO rooms and portals |

**Workflow**

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
& $blender -b -P map-forge\scripts\blender\export_map.py -- --spec work\my_map\source\map-spec.json --props work\my_map\build\props --textures work\my_map\build\textures --out work\my_map\my_map_pkg
& $blender -b -P map-forge\scripts\blender\inspect_map.py -- --dir work\my_map\my_map_pkg\stream --spec work\my_map\source\map-spec.json
```

1. Copy `map-forge/templates/map-spec.example.json` and describe the map: shell pieces, textures, lights, vanilla props and collision
2. Build the hero shell and props in Blender, then export with `export_map.py` (run without `--factory-startup` so Sollumz and PyMateria load)
3. Run `inspect_map.py` on the `stream/` folder until it reports `MAP_INSPECT_PASS fail=0` (RSC7 headers, triangles, vertex formats, vertex colour, lights, `.ybn`, `.ymap` extents and VRAM)
4. Stream the package with `map-forge/templates/fxmanifest.lua`

**References:** pipeline (`map-forge/references/pipeline.md`), shaders, lighting and vertex colour (`map-forge/references/shaders-lighting-vcol.md`), GTA V prop catalog for dressing (`map-forge/references/gta-prop-catalog.md`), Antigravity and Blender MCP (`map-forge/references/antigravity.md`), free CC0 PBR textures from Poly Haven fetched and converted by `map-forge/scripts/blender/fetch_polyhaven.py` (`map-forge/references/polyhaven-cc0.md`). Smooth curved hero pieces (rims, arc stairs, rails, arches) come from `sculpt-forge/`.

**Status:** `inspect_map.py` passes on the exported packages. Blender renders confirm the look. FPS in game has to be measured with the server running.

---

## Smooth sculpting

`sculpt-forge/` makes props look moulded instead of assembled from boxes. Shapes are written as signed distance fields (rounded boxes, pillow boxes, capsules, tori, lathes, extruded outlines with puff, tubes, beads, drips, scallops and TTF text), blended with a fillet radius per junction, meshed with OpenVDB (bundled with Blender), then reduced to a triangle budget. The smooth shading comes from custom normals transferred from the dense mesh, which Sollumz writes into the `.ydr` unchanged.

| Area | Highlights |
| --- | --- |
| Engine | `sculpt-forge/scripts/blender/sculpt_forge.py`: `SculptBuilder` with SDF nodes, groups and per-junction fillets, role palette or baked atlas, `Color 1` AO, colliders and prop metadata; output passes prop-forge `validate_prop.py` and exports with `export_prop.py` |
| Spec runner | `sculpt-forge/scripts/blender/forge_sculpt.py` builds a set from a JSON spec (`sculpt-forge/templates/sculpt-spec.example.json`) |
| Recipes | Ready-made builders by family in `sculpt-forge/scripts/blender/recipes/`: signs and lettering, cabinets and machines, containers, organics, round objects, and a map kit |
| Map pieces | `sculpt-forge/scripts/blender/sculpt_sweep.py`: rounded slabs, arc stairs with rounded nosing, rails, arches and trim lines for maps, exported through map-forge |
| Quality gate | `sculpt-forge/scripts/blender/validate_sculpt.py` (contract plus smoothness: dihedral spread, split edges, folds, lumpiness, normal error against the dense mesh) and `sculpt-forge/scripts/blender/render_sculpt.py` (clay, zebra, colour and turntable renders) |

**Workflow**

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
& $blender -b --factory-startup -P sculpt-forge\scripts\blender\forge_sculpt.py -- --spec sculpt-forge\templates\sculpt-spec.example.json --out work\puff
& $blender -b --factory-startup -P sculpt-forge\scripts\blender\validate_sculpt.py -- --blend work\puff
& $blender -b --factory-startup -P sculpt-forge\scripts\blender\render_sculpt.py -- --blend work\puff --out work\puff\renders
```

Then export with `prop-forge/scripts/blender/export_prop.py` (props) or `map-forge/scripts/blender/export_map.py` (map pieces). The targets come from measuring studio FiveM props: 200-320 triangles per square metre on hero props, round parts with at most 2-3 mm of sagitta, fully smooth normals, and no normal maps used to fake bevels.

---

## Work discipline

`dev-flow/` is how the agent works, not how the code looks (that stays in the root `SKILL.md`). It covers thinking before coding (at most three questions, otherwise state assumptions), the least code that works, surgical changes that keep every export, event, NUI payload and DB contract, systematic debugging from the first error, verification with fresh evidence (lint, contract diff against the backup, before/after measurements, an in-game test list), a lazy-senior review and folder audit, and a handoff note at the end of a session.

---

## Terse replies

`terse/` is an opt-in reply style for Thai sessions. It answers first, drops greetings, restating and closing summaries, and keeps code, commands, paths, names, numbers, units and error text exact. It has two levels (สั้น, สั้นโหด) and switches back to full sentences for security warnings, irreversible actions, step-by-step instructions and decisions the owner must make. Files, code and commits keep their normal standard.

---

## Posters

`poster-forge/` makes support, welfare and giveaway posters for gangs, families, ladies, newcomers and streamers. It takes character art, item icons and a logo. Two approved styles are supported: (A) a large dark character face with film grain and (B) a character pointing a gun at the camera.

| Area | Highlights |
| --- | --- |
| Character art | Green-screen characters generated with Antigravity (`agy-gen.ps1`) or Codex (`codex-gen.ps1`), then cut out, hole-filled and upscaled |
| Layout | HTML/CSS poster engine rendered to PNG, with templates for each tier and for square and wide formats |
| Prompts | Prompt sets that turn a character into semi-realistic AAA 3D art or change its pose to match a reference |

The fonts are OFL (see `poster-forge/engine/fonts/NOTICE.md`). Reference images of other people are not included in the repo.

---

## Ideas adapted from other projects

These projects inspired parts of this pack. Their ideas were rewritten in Thai for FiveM work; no text was copied, and nothing from them needs to be installed.

| Project | Used in | What was adapted |
| --- | --- | --- |
| [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), [superpowers](https://github.com/obra/superpowers), [mattpocock/skills](https://github.com/mattpocock/skills), [ponytail](https://github.com/DietrichGebert/ponytail) | `dev-flow/` | Think first, simplest working code, surgical edits, root-cause debugging, evidence before done, review that hunts code to delete, handoff notes |
| [caveman](https://github.com/JuliusBrussee/caveman) | `terse/` | Answer-first terse replies with exact technical payloads (no proxy or telemetry) |
| [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) | `map-forge/references/polyhaven-cc0.md` | Fetching CC0 textures from Poly Haven with Blender's own Python |

## Notes

- Never commit secrets (webhooks, tokens, passwords).
- Style references from other creators are used for direction only; never copy their names, logos, mascots, models or textures.
- Escrowed resources (`.fxap`) are never decrypted or edited.

## License

MIT
