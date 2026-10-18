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
- [ ] No secrets in shared config / UI.
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
- [ ] No generic full-pool sweeps or unregister/delete of entities the resource does not own.
- [ ] No awaited query per row/player; queries select required columns and use matching indexes.
- [ ] Scoped `TriggerClientEvent`; snapshots only on join/bucket change.
- [ ] State bag keys are small and granular; no repeated large-table getter in a hot loop.
- [ ] External HTTP/stream queues, retries, callbacks, and NUI buffers are bounded and cleaned up.
- [ ] NUI messages only on change.

## Style

- [ ] Header: `ESX = exports["es_extended"]:getSharedObject()` + `local scriptname = GetCurrentResourceName()`.
- [ ] Single controller table per side, PascalCase without prefix, colon methods.
- [ ] Events `scriptname .. ":SV:x"` / `":CL:x"`.
- [ ] External calls only through `FC`.
- [ ] No single-line `if`; no comments; 4 spaces; double quotes.
- [ ] No forbidden ox_lib modules (`lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI`).
- [ ] Player strings in `Config.Text`.

Automate the mechanical part: `node scripts/lint-resource.mjs <resource>`.

