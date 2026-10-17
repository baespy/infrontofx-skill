---
name: infrontofx-skill
description: infrontofx standard for writing, reviewing, refactoring, and optimizing FiveM Lua resources and NUI/DUI UIs. Enforces the single-table OOP controller (Name / NameServer with ServerState and PlayerState), the Config + config/function FC adapter split (config.function.client.lua / config.function.server.lua wrapping ESX, pNotify, and gameplay hooks), dynamic event names (scriptname .. ":SV:action" / ":CL:action"), ESX via exports, ox_lib for callbacks/points/zones/cache only (no lib.notify, progress, textui), server authority and give-value hardening, OneSync validation, oxmysql/KVP persistence, hot-path performance, cleanup, and fast NUI (vanilla JS class or React/Vite) with the infrontofx design system.
---

# infrontofx Skill

Use this skill for any FiveM Lua resource or in-game UI work in the `infrontofx` ecosystem. The defaults below apply to every task. Open the referenced files lazily, only when the task touches that area.

## Operating Workflow

1. Identify the surface before editing: client, server, shared, config, NUI, DUI, database, or cross-resource.
2. Read the local resource first. Follow its existing shape unless it breaks a rule below.
3. Load only the matching files from the routing table.
4. Treat every server event, callback, command, export, and NUI callback as an untrusted boundary.
5. Write code in the house style: single controller table, `FC` adapters, no comments, multi-line `if`.
6. Finish with verification: manifest load order, event names, server validation, cleanup, hot paths. Run `scripts/lint-resource.mjs` on the resource.
7. Record new engine quirks or recurring fixes in `memory/` with Date and Game build.

## Task Routing

| Task touches | Open |
| --- | --- |
| New resource, folder layout, manifest, load order | `skills/common/architecture.md`, `checklists/new-resource.md` |
| Controller table, naming, formatting | `skills/common/style.md` |
| `config.lua`, split config files, `sh_config.lua` | `skills/common/config.md` |
| `config/function/*.lua`, framework calls, hooks | `skills/common/fc-adapters.md`, `references/esx-api.md` |
| Net events, callbacks, exports | `skills/common/events.md` |
| Items, money, rewards, permissions, anti-cheat | `skills/common/security.md` |
| Loops, waits, caching, streaming, big sync payloads | `skills/common/performance.md` |
| Networked entities, routing buckets, state bags | `skills/common/networking.md` |
| oxmysql, KVP, dirty saves | `skills/common/database.md` |
| Native calls, hashes, entities | `skills/common/natives.md`, `memory/native-gotchas.md` |
| ox_lib usage | `skills/common/ox-lib.md` |
| Diagnosing a failure | `skills/common/debugging.md` |
| Any NUI (`ui_page`, `SendNUIMessage`, `RegisterNUICallback`) | `skills/ui/nui-bridge.md` |
| Visual design, CSS, layout, scaling | `skills/ui/design-system.md` |
| Plain HTML/JS UI | `skills/ui/vanilla-ui.md` |
| React / Vite / TypeScript UI | `skills/ui/react-vite.md` |
| 3D world UI via `lib.dui` | `skills/ui/dui.md` |
| Notifications | `references/pnotify-api.md` |
| Cross-resource exports and events | `rules/contracts.md` |
| Code review | `checklists/review.md` |

## Core Defaults

### File Header

Every client and server Lua file of a resource starts with:

```lua
ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()
```

### Single-Table OOP Controller

- One global controller table per side. Name it in PascalCase from the clean resource name without author prefix: `shop` -> `Shop` / `ShopServer`, `airdrop` -> `Airdrop` / `AirdropServer`. Never prefix with author tags.
- Client: `Name = { ServerState = {}, PlayerState = {} }`. Server: `NameServer = { ServerState = {} }`.
- All behaviour is colon methods on that table: `function Name:Method(...)`. Use `self` inside methods.
- Extra runtime maps (caches, indexes, pools) live as fields of the same table, never as loose globals.
- Files of the same side extend the same table (`sv_db.lua` and `sv_main.lua` both add methods to `NameServer`).

### Config And config.function

- `config/config.lua` holds `Config = {}` and `Config.General = { ... }` with snake_case keys. Large datasets go in `config/config.<domain>.lua` as `Config.<Domain> = { ... }`.
- `core/sh_config.lua` validates and normalizes config once at load (asserts, derived seconds, reverse indexes).
- `config/function/config.function.client.lua` and `config.function.server.lua` define the global `FC` table: every framework or third-party call and every customization hook (`FC.OnXxx`, `FC.CanXxx`) lives there. Core files call `FC.*`, never ESX inventory/account methods or `pNotify` directly.

### Events

- Server events and callbacks: `scriptname .. ":SV:actionName"`. Client events: `scriptname .. ":CL:actionName"`. camelCase action names.
- Prefer `lib.callback` for request/response. Capture `local src = source` first line of every server handler.
- The server owns items, money, prices, rewards, cooldowns, ownership, and saved state. Clients send intent only.

### Formatting

- 4 spaces. Double quotes in Lua. Trailing commas in multi-line tables.
- Never write single-line `if`. Always:
  ```lua
  if not xPlayer then
      return false
  end
  ```
- No comments in produced Lua code (`--` or `--[[ ]]`). Names and structure carry the meaning.
- No bloated guard wrappers (`NameServer:Notify`, `NameServer:ValidatePlayer`). Validate inline in the method that needs it; use `FC` for integrations.

### ox_lib

- Allowed: `lib.callback`, `lib.points`, `lib.zones`, `lib.onCache`, `cache.*`, `lib.table`, `lib.array`, `lib.cron`, `lib.dui`, `lib.requestModel` / `lib.requestAnimDict` / `lib.requestNamedPtfxAsset`, `lib.addKeybind`.
- Forbidden: `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI`. Use `FC.Notify`, `FC.Progress`, `FC.ShowTextUI` / `FC.HideTextUI`.

### Security

- Validate every payload field: `type`, range, length, existence in a server-side catalog. Quantities are positive bounded integers.
- Re-derive price, item, recipient, and permission on the server. Throttle per source. Use an in-flight lock for give-value actions.
- Validate client net IDs and coords: existence, distance, routing bucket, ownership registry.
- Secrets only through server convars (`GetConvar`), never in shared config or UI.

### Performance

- No `Wait(0)` unless drawing or reading controls every frame. Stage waits by distance.
- Use `lib.points` / `lib.zones` / `cache.ped` instead of polling distance loops and `PlayerPedId()`.
- Localize hot globals at the top of heavy files (`local tonumber = tonumber`).
- Build reverse indexes once; never scan a list by name in a hot path.
- Scope `TriggerClientEvent` to sessions near the data; avoid `-1` broadcasts for frequent updates.

### NUI

- Message shape `{ action = "name", data = {...} }`. Handshake with a `uiReady` callback before sending.
- Every `RegisterNUICallback` calls `cb` exactly once. Clear focus on close, death, and resource stop.
- Render player-controlled strings with `textContent` / framework text binding only.

### Cleanup

- On `onResourceStop`: delete entities, blips, points, zones, DUI, NUI focus, text UI. On `playerDropped`: clear every `[src]` keyed map.

## Templates And Tools

- `templates/resource/` - complete working resource in house style (manifest, config, FC, client/server controllers, NUI).
- `scripts/new-resource.ps1` - scaffolds a new resource from the template with the correct controller names.
- `scripts/lint-resource.mjs` - static checks for house rules, security, and performance smells.
- `scripts/validate-skill.mjs` - validates this package before publishing.

## Memory

- `memory/native-gotchas.md` - verified native quirks.
- `memory/security-exploits.md` - exploit classes seen in practice.
- `memory/patterns.md` - proven implementation patterns (wire encoding, KVP snapshot, DUI pool, owner cache).
