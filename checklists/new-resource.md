# New Resource Checklist

1. Scaffold: `node scripts/new-resource.mjs <name> --destination <resources folder>`.
2. Rename check: client module `Name`, server module `NameServer`, no author prefix. One module table per side, declared as a `local` on the first line after `scriptname`.
3. `fxmanifest.lua`: `lua54 "yes"`, `@ox_lib/init.lua` then `@1nfx_core/imports.lua` first in `shared_scripts`, `config/*.lua` after them, `core/*` in `client_scripts` / `server_scripts`, and `files` listing only the html files the page actually references. No `core/sh_config.lua`, no experimental OAL by default.
4. `config/config.lua`: `Config.General` (snake_case), `Config.Text` for every player string, commands configurable.
5. Optional split datasets in `config/config.<domain>.lua` when a dataset is large. Read `Config` directly in `core/*` without fallback chains.
6. Integration code (notify, text UI, money, items, logs) is written directly inside `core/` as methods of the module (`Module:Notify`, `Module:GetMoney`). Framework access goes through the global `Core` from `@1nfx_core/imports.lua` (ESX-compatible); never `exports["es_extended"]:getSharedObject()`.
7. Server: `ServerState` maps, throttle, in-flight lock for value actions, `lib.callback.register` handlers that only call a method.
8. Client: `lib.points` / `lib.zones`, prompt shown on enter and cleared on exit, direct `PostNUI`. In `lib.points` callbacks `self` is the point, so call the module by name.
9. NUI: `uiReady` handshake, `{ action, data }`, `cb` once on every path, ESC close, `textContent` only, design tokens + `--px`. `RegisterNUICallback` handlers only call a module method.
10. Cleanup: `onResourceStop` (points, blips, entities, DUI, focus, text UI) and `playerDropped` (`[src]` maps), both handlers only calling a method.
11. Persistence (if any): `install.sql`, dirty save, await on stop.
12. Code style: zero comments in Lua/JS/CSS/HTML, only methods (`function Module:Name()`), no top-level `local function`, no file-level constants (literals at the use site, shared tables as module fields), no abbreviated resource-name variables, top-of-file locals limited to `scriptname` and the module table, events named `scriptname .. ":SV:<name>"` / `scriptname .. ":CL:<name>"`.
13. Run `node scripts/lint-resource.mjs <resource>` - zero errors.
14. Test: start, restart twice (no duplicate blips/points), spam the action, disconnect mid-action, wrong bucket, far distance.
