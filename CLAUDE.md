# CLAUDE.md — infrontofx-skill

This repository (and any FiveM workspace where it is installed) uses `infrontofx-skill` as the authoritative coding standard for FiveM Lua resources and NUI/DUI interfaces.

Read `SKILL.md` first and open the routed files in `skills/`, `references/`, `rules/`, `memory/`, and `checklists/` for the task at hand.

## Non-Negotiable Rules

1. Every client and server Lua file starts with:
   ```lua
   ESX = exports["es_extended"]:getSharedObject()
   local scriptname = GetCurrentResourceName()
   ```
2. Single-table OOP controller per side in PascalCase without author prefix (`shop` -> `Shop` / `ShopServer`). Client holds `ServerState` + `PlayerState`; server holds `ServerState`. All methods use colon syntax `function Name:Method(...)`.
3. `Config` lives in `config/config.lua` (`Config.General`, `Config.Text`), domain tables in `config/config.<domain>.lua`, normalized once in `core/sh_config.lua`.
4. All framework/external calls and customizable hooks live in `config/function/config.function.client.lua` and `config/function/config.function.server.lua` on the global `FC` table (wrapping standard `ESX`, `pNotify`, text UI, progress bar, and server logs).
5. Dynamic events: `scriptname .. ":SV:action"` and `scriptname .. ":CL:action"`. First line of every server handler: `local src = source`.
6. `ox_lib` allowed only for `callback`, `points`, `zones`, `cache`, `table`, `array`, `cron`, `dui`, `requestModel`/`AnimDict`/`NamedPtfxAsset`, `addKeybind`. Never use `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI`.
7. Multi-line `if` statements only. Zero comments (`--`) in produced Lua code. 4-space indentation, double quotes.
8. Server authority on all items, money, prices, rewards, cooldowns, distance, and routing buckets.
9. NUI uses `{ action, data }`, `uiReady` handshake, calls `cb(...)` once per `RegisterNUICallback`, renders untrusted text with `textContent`, and scales with `--px` tokens on a 1920x1080 artboard.
10. Full cleanup on `onResourceStop` and `playerDropped`.
