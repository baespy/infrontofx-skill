# infrontofx-skill Agent Guide

Whenever you create, edit, refactor, review, debug, or optimize a FiveM Lua resource or its NUI/DUI, follow `SKILL.md` in this package. It is the single source of truth and routes you to the right file per task.

## Non-negotiables

1. Header in every client/server file:
   ```lua
   ESX = exports["es_extended"]:getSharedObject()
   local scriptname = GetCurrentResourceName()
   ```
2. One controller table per side, PascalCase from the resource name without author prefix: `GrowthGarden` / `GrowthGardenServer`. Fields `ServerState`, `PlayerState`. Colon methods only.
3. `Config` in `config/config.lua` (`Config.General`, `Config.Text`), datasets in `config/config.<domain>.lua`, validation in `core/sh_config.lua`.
4. All framework/external calls and owner hooks in `config/function/config.function.client.lua` / `config.function.server.lua` via `FC` (wrapping standard `ESX` + `pNotify` + UI/log exports). Client `FC.Notify(label, type)`, server `FC.Notify(source, label, type)`.
5. Events: `scriptname .. ":SV:action"` / `scriptname .. ":CL:action"`. `local src = source` first line of every server handler.
6. ox_lib allowed for callback/points/zones/cache/table/cron/dui. Forbidden: `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI`.
7. Multi-line `if` only. No comments in Lua. 4 spaces. Double quotes.
8. Server decides every value; validate payloads, throttle, in-flight lock, distance + bucket checks.
9. NUI: `{ action, data }`, `uiReady` handshake, `cb` once, `textContent` only, `--px` design tokens.
10. Clean up on `onResourceStop` and `playerDropped`.

## Repository Map

- `skills/common/` - Lua rules (style, architecture, config, FC, events, security, performance, networking, database, natives, ox_lib, debugging).
- `skills/ui/` - NUI bridge, design system, vanilla UI, React/Vite, DUI.
- `references/` - APIs of ESX (`references/esx-api.md`), 1nfx UI resources, pNotify, external links.
- `rules/contracts.md` - cross-resource rules.
- `memory/` - learned quirks, exploits, patterns (Date + Game build per entry).
- `checklists/` - new resource and review checklists.
- `templates/resource/` - complete resource in house style.
- `scripts/` - `lint-resource.mjs`, `new-resource.ps1`, `validate-skill.mjs`.

## Working Rules

- Prefer the existing resource's patterns when they do not break the non-negotiables.
- Run `node scripts/lint-resource.mjs <resource>` after edits.
- Add new learned facts to `memory/`, not to `skills/`.
- Run `node scripts/validate-skill.mjs` before publishing changes to this package.
