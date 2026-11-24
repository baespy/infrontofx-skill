---
name: infrontofx
description: FiveM 1nfx_* coding standard and pack router. Use for any edit to resources/**.lua, fxmanifest.lua, config/, NUI html/ or DUI (เขียนใหม่, รีไรต์, optimize, แยกสคริป, สร้าง resource, ทำ UI), always with dev-flow. Not for props, maps, posters or weapon skins (use the forge skills; load this for them only if those are not listed).
---

# infrontofx

FiveM `1nfx_*` house standard (Lua 5.4, `1nfx_lib`, `1nfx_core`, NUI/DUI) and pack router. Goal: same behaviour, less and faster code, no duplicates. Paths are relative to this folder (a sub-skill's to its own).

## Auto-route

Pick skills yourself (the owner never names them); else read `<name>/SKILL.md` here. Load only matching rows.

| Task signal | Load |
| --- | --- |
| Edit `resources/**` Lua, `fxmanifest.lua`, NUI `html/`, DUI, forge Lua (เขียนใหม่, รีไรต์, optimize, แยกสคริป) | this file, then `dev-flow/SKILL.md` verify before saying done |
| New system or unclear task (ออกแบบระบบใหม่, วางแผน) | `dev-flow` think-first + plan, then this file |
| Bug, error, F8 or server log (บั๊ก, ไม่ทำงาน) | `dev-flow` debug, then this file to fix |
| Review, audit, session end (รีวิว, ตรวจงาน, สรุปส่งต่อ) | `dev-flow` review-audit (+ `checklists/review.md`) or handoff |
| Smooth or organic prop, puffy letters, drips (ปั้นเนียน) | `sculpt-forge/SKILL.md`, then `prop-forge` to export and wire in |
| Boxy archetype prop, sign, ATM, ytyp, stream, spawn code (ปั้น prop) | `prop-forge/SKILL.md` |
| Map, ymap, ybn, MLO, map lights (ปั้นแมพ) | `map-forge/SKILL.md`; curved hero pieces from `sculpt-forge` |
| Weapon skin, `.ypt` ptfx, hit/kill screen or sound (สกินอาวุธ) | `weapon-forge/SKILL.md` |
| Support or welfare poster (โปสเตอร์) | `poster-forge/SKILL.md` |
| Lag, FPS, stutter (แลค); outside-the-box design (คิดนอกกรอบ) | `perf-forge/SKILL.md`; `perf-architect/SKILL.md` |
| Which skills exist (มี skill อะไรบ้าง) | `help-inf-skills/SKILL.md` |
| Owner asks for short replies (ตอบสั้น) | `terse/SKILL.md` (stays on) |

## Quick path

1. One resource at a time. Read every file of the resource; grep the whole project (html builds, tests) for its name, exports, events, NUI callbacks.
2. Back up to `<project>/_backup/<YYYY-MM-DD>/<resource>` before the first edit (no git).
3. Rewrite to Hard rules. Keep every contract: export names and parameter order, event names, `lib.callback` names, commands, `Config` keys, NUI `action` and `data` shape, DB tables and columns, state bag keys, JS exports Lua calls.
4. Optimize; delete dead code (unloaded files, uncalled callbacks, preview or mock modes) only after grep proves no caller.
5. `node scripts/lint-resource.mjs <resource>` (node not on PATH: `<project>\.tools\node\node.exe`). Pass = `0 error(s)`, exit 0, each warning fixed or explained.
6. Diff contracts against the backup with `dev-flow/references/verify.md`: no unexplained `<=`, every called method defined.
7. Report in Thai with that file's template (ตรวจแล้ว, ต้องลองในเกม included), append to `PROGRESS.md`, go on to the next resource if the owner said so.

## Choose

| If | Then |
| --- | --- |
| core files under ~30 KB total | rewrite them whole |
| big resource in standard layout | keep logic, move it into methods, cut dead code, fix real slow or wrong spots, report what stayed |
| obfuscated or `.fxap` resource | touch neither files nor manifest |
| `FC` or `config/function` present | `references/house-standard.md` -> FC migration |
| pure logic both sides need (zones, time, codec) | `core/sh_<domain>.lua` in `shared_scripts` as `<Module>Shared = {}` + `setmetatable(Module, { __index = <Module>Shared })` both sides |
| UI: no mouse / focus (`SetNuiFocus`) | host in the HUD hub fed by export / own `ui_page` (`NUI_DUI.md`) |
| state that must vanish on leave (round picks) | `ServerState` + `Player(src).state`, clear on `1nfx_core:playerLoaded`, re-read from online players on start; no DB |

## Hard rules

**Owner orders**: same player-visible behaviour, every change reported. Fix verified holes and slow spots unasked, report after (ask only for new facts or a design call). Record each new owner rule or lesson (long text in `references/house-standard.md`, facts in `memory/`). Split merged duplicate systems; one owner per cross-resource system (culling, graphics), grep first. Max 1-2 sub-agents, none spawning agents, no large workflows.

**Manifest and layout**
- `fxmanifest.lua`, `config/config.lua` (owner-tuned values), `core/cl_main.lua`, `core/sv_main.lua`; big resources split `core/` into `cl_<feature>.lua`/`sv_<feature>.lua`, one topic each.
- `lua54 "yes"` (needed by `+=`, `//`). `shared_scripts` starts `"@1nfx_lib/init.lua"`, `"@1nfx_core/imports.lua"` (never `ox_lib`, `er_lib`, `cfxlua-require`); config files in load order, no glob.
- No `dependencies`/`dependency`, no `escrow_ignore`; start order lives in `server.cfg`. `files` only what the page loads (drop unused images, sounds, svg; keep globs for `Config` image names), never `stream/`; `exports("name", fn)` needs no manifest line.
- `core/sh_*.lua` only as in Choose; never twin `cl_x`/`sv_x` copies or one-side helpers in `sh_`.
- No micro-resource for tables or helpers the main module owns; no extra `ensure` inside an ensured `[category]` unless order must be forced.

**OOP and Lua**
- No comments in any language. No `FC` table or `config/function/`; integrations are methods in `core/`.
- One module table per side with `ServerState` and `PlayerState`; every function is a method (`function Module:Name()`) called via `self:` or the module name (closures inside methods are fine). A method needs real logic (pcall, nil check, `GetResourceState`, math) used 2+ times; else inline the call.
- Nothing at file level: `local function`, constants (`(?m)^local [A-Z][A-Z0-9_]* = ` finds none; `Wait(1000)` in place), resource-name aliases, `Config` shortcuts (a hot method may pull a local), one-line wrappers. Shared data tables are module fields.
- File top: framework variable, `local scriptname = GetCurrentResourceName()`, module table only. Globals: `Config`, module tables, `<Module>Shared`.
- Events `scriptname .. ":SV:<name>"` / `":CL:<name>"`; handlers and threads only call methods. Server `RegisterNetEvent` handlers start `local src = source`; `lib.callback.register` passes `src`. In `lib.points` callbacks `self` is the point, not the module.
- Framework via global `Core` (`@1nfx_core/imports.lua`), never `es_extended` directly. `xPlayer` once per action, nil-checked. One real code path, no fallback chains.
- `1nfx_lib` is the only runtime; gameplay scripts never call `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI` (use the server UI exports).

**Config**: `Config = {}` once in `config/config.lua`, then direct sub-tables (`Config.General`, `Config.Text`). Never `Config.X = Config.X or {}`, `if not Config.X`, merge loops, dead keys or files, tuning or mock config files, global state or `scriptname` in config.

**Server and cleanup**: the server decides every value (items, money, prices, rewards, cooldowns, distance, routing bucket), validates payloads, throttles client events, blocks duplicates; clean all in `onResourceStop` and `playerDropped`.

**Optimize** (measure first, same scenario before/after; lag or FPS: `perf-forge`)
- Client: `lib.zones`/`points`/`grid`, `lib.spawn`, no distance loops; `Wait(0)` only while needed, else the longest equal wait; interval-gate heavy work; `cache` not repeated natives; invariants out of loops; release models, anim dicts, entities on leave and stop. NUI: send on change only, from one loop.
- Server: no DB query in loops (cache, write-back); one central loop, per-topic counters, ticks in `pcall`, idle sleep woken by a `promise`; one-packet `lib.callback`; `lib.guard`, `lru`, `heap`, `ringbuffer`; send only to players using the feature, batched.

**UI**: 1nfx style per `skills/ui/design-system.md`. NUI `{ action, data }`, `uiReady` handshake, `cb` once per callback, `textContent`, `--px` scaling on 1920x1080.

**Secrets**: secret files only in `server_scripts`, never shared, client or `files` (globs like `config/**` too; split a shared config, leave its value empty); never sent to clients; report a found one by location, never its value; never committed (gitignore the config).

**DB**: read the real schema first; add only missing indexes (check left prefixes) with `ALGORITHM=INPLACE, LOCK=NONE` after a schema backup; ship `indexes.sql` (`ADD INDEX IF NOT EXISTS`).

**Tools**: `-LiteralPath` for PowerShell paths with `[ ]`; UTF-8 without BOM; more in `references/house-standard.md` -> Field lessons.

## Done when

- [ ] Backup at `_backup/<YYYY-MM-DD>/<resource>`
- [ ] Lint `0 error(s)`, exit 0, warnings handled
- [ ] Contracts intact, called methods defined, behaviour unchanged or each change reported
- [ ] `dev-flow` verify after the last edit; report has ตรวจแล้ว, ต้องลองในเกม
- [ ] New owner rule or lesson recorded in this pack
- [ ] Pack edited: `node scripts/validate-skill.mjs` prints `infrontofx validation passed.`

## References

| Need | Open |
| --- | --- |
| Full Thai rule text, OOP examples, FC migration, field lessons | `references/house-standard.md` |
| New resource; review | `checklists/new-resource.md`, `templates/resource/`, `scripts/new-resource.mjs`; `checklists/review.md`, `rules/contracts.md` |
| Topics: architecture, config, events, networking, core-api, database, performance, natives, runtime, 1nfx-lib, security, debugging, style | `skills/common/<topic>.md` |
| Framework API, notify; field gotchas | `references/esx-api.md`, `references/pnotify-api.md`; `memory/` |
| UI: design-system, nui-bridge, dui, vanilla-ui, react-vite, vue-svelte; tokens, MCP | `NUI_DUI.md`, then `skills/ui/<name>.md`; `TOOLING.md` |
