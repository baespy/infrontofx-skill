# Review Checklist

Review in this order: authority -> boundaries -> lifecycle -> performance -> style.

## Authority

- [ ] Every value (item, money, price, reward, cooldown, ownership) decided on the server.
- [ ] Recipient is always `src`.
- [ ] Give-value actions pass the checklist in `skills/common/security.md` -> Give-Value Checklist.

## Boundaries

- [ ] Each `RegisterNetEvent` / `lib.callback.register` captures `local src = source` first.
- [ ] Payload type, length, range, integer checks before use.
- [ ] Unknown ids rejected via server config/registry lookup.
- [ ] Distance + routing bucket checks for world interactions.
- [ ] Throttle on spammable handlers; in-flight lock on value handlers.
- [ ] NUI callbacks validate and call `cb` once; UI cannot choose shop/target ids.
- [ ] No secrets in shared config / UI; secret files are in `server_scripts` only and never reach `files`.
- [ ] SQL parameterized.

## Lifecycle

- [ ] `onResourceStop` removes points, zones, blips, local entities, DUI, focus, text UI.
- [ ] `playerDropped` clears every `[src]` map (throttle, inFlight, sessions, caches).
- [ ] Re-validation after every yield before mutating RAM.
- [ ] Restarting the resource twice leaves no duplicates.

## Performance

- [ ] Before/after captures use the same scenario, player count, duration, and profiler/resmon method.
- [ ] No idle `Wait(0)` loops; points/zones used for proximity.
- [ ] `cache.ped` / `cache.coords` instead of repeated natives in loops.
- [ ] Indexes instead of list scans in hot paths.
- [ ] Inventory indexes preserve array consumers, zero-count/unknown-item behavior, persistence, and provider semantics; no name-only map for distinct metadata slots.
- [ ] Event counts, encoded bytes, recipient counts, and latency measured separately; batching has bounded bytes and delay.
- [ ] Prepared batches are not assumed atomic; zero affected rows cannot grant a purchase, and saves have one persistence owner.
- [ ] No generic full-pool sweeps or unregister/delete of entities the resource does not own.
- [ ] No awaited query per row/player; queries select required columns and use matching indexes.
- [ ] Scoped `TriggerClientEvent`; snapshots only on join/bucket change.
- [ ] State bag keys are small and granular; no repeated large-table getter in a hot loop.
- [ ] External HTTP/stream queues, retries, callbacks, and NUI buffers are bounded and cleaned up.
- [ ] NUI messages only on change; no large `backdrop-filter` / blur areas in the page.

## Style

- [ ] Header & manifest: `@1nfx_lib/init.lua` first in `shared_scripts` (no legacy `@ox_lib/init.lua`, `@er_lib/init.lua`, or standalone `cfxlua-require`), followed by `@1nfx_core/imports.lua` for global `Core` (no `exports["es_extended"]:getSharedObject()`); file header contains only `local scriptname = GetCurrentResourceName()` and the module table.
- [ ] Single module table per side, PascalCase without prefix, every function a method (`function Module:Name()`).
- [ ] No top-level `local function`; closures inside a method are allowed.
- [ ] No file-level constants (`local NAME = value`); literals written at the use site, shared tables are module fields.
- [ ] No adapter or wrapper tables; integration code (notify, money, items, logs) lives in `core/` methods.
- [ ] Zero comments in Lua, JS, CSS and HTML.
- [ ] No abbreviated resource-name variables; `exports["1nfx_processbar"]:...` written in full.
- [ ] Handlers, callbacks and threads only call methods.
- [ ] Events `scriptname .. ":SV:x"` / `":CL:x"`; legacy `esx:*` names are not used in new code (`1nfx_core:*`).
- [ ] No single-line `if`; 4 spaces; double quotes.
- [ ] No forbidden UI bridge calls in gameplay scripts (`lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI`, `lib.registerContext`, `lib.inputDialog`, `lib.alertDialog`); call server UI exports directly.
- [ ] Player strings in `Config.Text`.
- [ ] `lua54 "yes"` in the manifest.
- [ ] Shared pure logic used by both client and server lives once in `core/sh_<domain>.lua` under `shared_scripts` (`<Module>Shared` inherited via `__index`); zero copy-pasted `cl_<x>.lua` + `sv_<x>.lua` twins and zero single-side helpers placed in `sh_*.lua`.
- [ ] `Config = {}` declared once in `config/config.lua` with direct sub-table assignments (`Config.General = { ... }`); no `Config.X = Config.X or {}`, no `if not Config.X then Config.X = {} end`, and no default-merging loops in config files.
- [ ] Zero dead or fake configs: every `Config` key and file is read by `core/` (no unused keys, no orphaned dataset files, and no separate preview/internal constant dumps).
- [ ] No redundant standalone micro-resources for single-caller helpers and no duplicate individual `ensure <resource>` in `server.cfg` when covered by an ensured `[category]` folder (unless strict pre-category boot order requires it).

Automate the mechanical part: `node scripts/lint-resource.mjs <resource>`.
