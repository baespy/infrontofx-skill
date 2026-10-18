---
name: infrontofx-skill
description: Build, review, debug, refactor, or optimize infrontofx FiveM Lua resources and NUI/DUI interfaces using the house controller, Config, FC adapter, security, performance, and UI conventions.
---

# infrontofx FiveM Standard

Use this skill for FiveM Lua and in-game UI work in the `infrontofx` ecosystem. Inspect the target resource first, preserve sound local patterns, and load only the references required by the task.

## Workflow

1. Identify the affected side: manifest, shared, client, server, config, NUI, DUI, database, or cross-resource.
2. Read the local implementation and its manifest load order before editing.
3. Open only the matching references below.
4. Treat client-reachable events, callbacks, commands, exports, and NUI callbacks as untrusted boundaries.
5. Write direct, minimal code. Do not add speculative helpers, comments, fallback chains, formatting bloat, wrappers, or guards.
6. Verify behavior, lifecycle cleanup, event names, server authority, and hot paths. Run `node scripts/lint-resource.mjs <resource>`.
7. Add only verified recurring quirks to `memory/`, including date and game build.

## Routing

| Surface | Read |
| --- | --- |
| New resource, layout, manifest | `skills/common/architecture.md`, `checklists/new-resource.md` |
| Controller, naming, formatting, guard policy | `skills/common/style.md` |
| Config structure | `skills/common/config.md` |
| ESX, pNotify, owner hooks, `FC` | `skills/common/fc-adapters.md`, `references/esx-api.md`, `references/pnotify-api.md` |
| Events, callbacks, commands, exports | `skills/common/events.md` |
| Threads, yields, source lifetime, resource restarts | `skills/common/runtime.md` |
| Rewards, money, items, permissions, hostile input | `skills/common/security.md` |
| Profiling, loops, queues, caching, streaming, sync cost | `skills/common/performance.md` |
| Entities, net IDs, buckets, state bags | `skills/common/networking.md` |
| oxmysql or KVP | `skills/common/database.md` |
| Natives and entity calls | `skills/common/natives.md`, `memory/native-gotchas.md` |
| ox_lib | `skills/common/ox-lib.md` |
| Diagnosis | `skills/common/debugging.md` |
| NUI bridge and focus | `skills/ui/nui-bridge.md` |
| UI styling and scaling | `skills/ui/design-system.md` |
| Vanilla UI | `skills/ui/vanilla-ui.md` |
| React, Vite, TypeScript | `skills/ui/react-vite.md` |
| World-space DUI | `skills/ui/dui.md` |
| Cross-resource integration | `rules/contracts.md` |
| Review | `checklists/review.md` |

## House Contract

### Files And Controllers

Every client/server Lua file starts with:

```lua
ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()
```

- Use one global controller table per side, named from the resource without its author prefix: `Shop` and `ShopServer`.
- Client shape: `Name = { ServerState = {}, PlayerState = {} }`. Server shape: `NameServer = { ServerState = {} }`.
- Put runtime maps on the controller. Define behavior with colon methods and use `self`.
- `FC` is the only additional global table and exists only as the integration/customization boundary.

### Config And Integrations

- `config/config.lua` defines `Config`, `Config.General`, and `Config.Text` with snake_case keys.
- Put large domain datasets in `config/config.<domain>.lua` only when needed. Do not create `core/sh_config.lua` or config normalization layers; read `Config.General.*` and `Config.Text.*` directly.
- Framework, inventory, notification, progress, text UI, logging, and owner hooks belong in `config/function/config.function.client.lua` or `.server.lua` as `FC.*`.
- Core code never calls ESX inventory/account methods or pNotify directly.

### Events And Authority

- Use `scriptname .. ":SV:actionName"` for server endpoints and `scriptname .. ":CL:actionName"` for client endpoints.
- Capture `local src = source` before any yield in every server handler. Never accept identity from payload data.
- Prefer `lib.callback` for request/response. Clients send intent; the server resolves values and permissions.
- Bound and validate external payloads. Re-derive items, prices, rewards, ownership, distance, and routing bucket server-side.
- Throttle public actions and lock value mutations against concurrent execution. Revalidate identity after a yield.

### Style, Directness, And Guard Policy

- Use 4 spaces, double quotes, trailing commas in multi-line tables, multi-line `if`, and no comments in produced Lua or UI code.
- Write direct, minimal code. Read `Config.General.x`, `Config.Text.x`, and `cache.ped` / `cache.coords` directly; never write `(Config.General and Config.General.x) or default` or `cache.ped or PlayerPedId()` fallback chains.
- Do not clutter Lua with manual string-formatting gymnastics (such as `string.format("WORLD %02d", ...)`, `:upper():gsub("_", " ")`, or multi-branch time string builders) when raw values or `FC` / `Config` labels can be passed directly.
- Add guards only at trust boundaries and before unsafe native/framework operations.
- Do not add nil/empty guards to internal values already guaranteed by config, a caller contract, or prior validation.
- Do not create one-line wrapper methods, unused callbacks, dead code, or helpers used once.

### Performance And Lifecycle

- Use `lib.points`, `lib.zones` (`onEnter`, `inside`, `onExit`), and `cache.*` instead of manual polling loops.
- Use `Wait(0)` only for active frame work. Send state only when it changes.
- Do not claim an optimization without comparable before/after `resmon` or profiler evidence.
- Scope frequent client events; do not broadcast with `-1` unless every player genuinely needs the update.
- Clean entities, blips, points, zones, DUI, focus, timers, and controller maps on stop/drop.

### ox_lib And UI

- Allowed ox_lib areas: callback, points, zones, cache, table, array, cron, DUI, streaming requests, and keybinds.
- Do not use ox_lib notify, progress, text UI, menu, context, or dialog modules. Route those through `FC` or the resource NUI.
- NUI messages use `{ action, data }`; the page sends `uiReady`; each NUI callback calls `cb` once.
- Resolve the NUI resource with `GetParentResourceName()`. Never hardcode it.
- Render player-controlled strings with `textContent` or framework text binding. Keep runtime assets local.

## Package Tools

- `templates/resource/` is the canonical working example.
- `scripts/new-resource.mjs` creates a resource from that template.
- `scripts/lint-resource.mjs` checks house rules and common security/performance mistakes.
- `scripts/validate-skill.mjs` validates this package before publishing.
