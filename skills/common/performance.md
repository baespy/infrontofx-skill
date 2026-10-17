# Performance

FXServer runs Lua on one thread per side. Every wasted tick is felt by every player on that machine. Target: idle client resource at 0.00-0.01 ms, server resource well under 0.5 ms average.

## Contents

- Waits
- Spatial Logic
- Caching
- Indexes
- Streaming Many World Entities
- Network Payloads
- NUI And DUI
- Server Loops
- Memory And Cleanup
- Measuring

## Waits

| State | Wait |
| --- | --- |
| nothing nearby / idle | event driven, or `Wait(1000+)` |
| something within ~50 m | `Wait(500)` |
| within interaction range | `Wait(100-250)` |
| drawing markers/text or reading controls | `Wait(0)` only while needed |

- Return the wait from the loop body and sleep once: compute `local sleep = 1000`, lower it only when needed.
- Never `while true do Wait(0)` at resource start.

## Spatial Logic

Use `lib.points` / `lib.zones` instead of distance loops:

```lua
local point = lib.points.new({
    coords = shop.coords,
    distance = Config.General.interact.draw_distance,
    shopId = shop.id,
})

function point:onEnter()
    Template:OnEnterShop(self.shopId)
end

function point:onExit()
    Template:OnExitShop(self.shopId)
end

function point:nearby()
    if self.currentDistance <= Config.General.interact.distance and IsControlJustReleased(0, Config.General.interact.key) then
        Template:OpenShop(self.shopId)
    end
end
```

`nearby()` runs every frame only while inside `distance`; keep it tiny.

## Caching

- `cache.ped`, `cache.coords`, `cache.vehicle`, `cache.playerId`, `cache.serverId` instead of `PlayerPedId()` / `GetEntityCoords(PlayerPedId())` in loops.
- `lib.onCache("ped", fn)` to react to ped change.
- Cache asset loads in the controller (`self.LoadedPtfxAssets[asset] = true`) and release on stop.
- Owner-name style lookups: TTL cache (`{ value, expires = GetGameTimer() + 30000 }`).
- Every cache has an owner field on the controller and a cleanup path.

## Indexes

Build once in `sh_config.lua` or `Init`:

```lua
shop.itemIndex = {}
for _, item in ipairs(shop.items) do
    shop.itemIndex[item.name] = item
end
```

Then `shop.itemIndex[name]` instead of a loop. Same for sessions by identifier, entities by id, objects by owner.

## Streaming Many World Entities

- Server keeps all entities in `ServerState.entities`; clients only spawn the ones within `streaming.distance`.
- Grid cells (`cell_size = 150.0`) index entities by `floor(x / cell)`, `floor(y / cell)` so a scan touches 9 cells, not every entity.
- Scan in batches with a time budget (`scan_batch_size = 16`, `scan_budget_ms = 2`) and `Wait(0)` between batches.
- `retain_distance > distance` (hysteresis) so entities do not spawn/despawn every tick on the boundary.
- Local (non-networked) props for visuals: `CreateObject(model, x, y, z, false, false, false)`.

## Network Payloads

- Send ids and deltas, not full objects, on frequent updates.
- Snapshot on join / bucket change only; afterwards push per-entity create/update/remove events.
- Compress large snapshots with dictionary key encoding (`memory/patterns.md` -> Wire Encoding).
- Use digests (`("%s:%d:%.2f"):format(...)`) to skip sending unchanged entities.
- State bags for small visible state; never put large tables in state bags.

## NUI And DUI

- `SendNUIMessage` only on change. Throttle per-entity UI updates (`entity.nextUiUpdate = GetGameTimer() + 1000`).
- Pool DUI instances (`max_dui`) and reuse slots instead of creating a DUI per entity (`skills/ui/dui.md`).
- CSS transitions instead of JS animation loops.

## Server Loops

- One scheduler thread per concern (autosave, expiry), long intervals.
- Spread work: snapshot the dirty set, process with `Wait(50)` between items.
- `lib.cron` for wall-clock jobs.
- Avoid `GetPlayers()` scans every tick; maintain `playerSessions` on join/drop.

## Memory And Cleanup

- Clear `[src]` maps on `playerDropped`.
- Remove points, zones, blips, DUI, local entities, ptfx on `onResourceStop`.
- `SetModelAsNoLongerNeeded` after spawning, `RemoveNamedPtfxAsset` when no longer used.

## Measuring

- `resmon 1` in F8 for client ms; `profiler record 500` / `profiler view` for hot functions.
- Server: `txAdmin` resource monitor or `profiler` in server console.
