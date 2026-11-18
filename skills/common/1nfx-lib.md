# 1nfx_lib

`1nfx_lib` is the single first-party shared runtime for `infrontofx` resources (`"@1nfx_lib/init.lua"` first in `shared_scripts`). It replaces external `ox_lib`, `er_lib`, and `cfxlua-require`. Use it for RPC, spatial indexing, caching, server guards, client entity spawning, and data structures — never for gameplay UI.

## Runtime Globals

Loading `"@1nfx_lib/init.lua"` provides:

| Global | Purpose |
| --- | --- |
| `lib` | first-party runtime module namespace |
| `cache` | client state cache (`ped`, `coords`, `vehicle`, `seat`, `weapon`, `playerId`, `serverId`, `pauseActive`) |
| `require` | cached Lua module loader (replaces standalone `cfxlua-require`) |
| `SetInterval` / `ClearInterval` | managed interval timers (`local id = SetInterval(fn, ms)` / `ClearInterval(id)`) |

## Allowed Modules

| Module | Side | Use for |
| --- | --- | --- |
| `lib.callback` / `lib.callback.await` / `lib.callback.register` | shared | 1-packet client <-> server RPC without dual-event boilerplate |
| `lib.points` | client | per-location `onEnter` / `onExit` / `nearby` (stationary-skip + squared-distance filtering) |
| `lib.zones` (`box`, `sphere`, `poly`) | shared | area triggers with stationary-skip + squared-distance filtering |
| `lib.grid` | shared | 2D spatial cell index for large point/entity worlds |
| `cache.*` + `lib.onCache` | client | cached player/client state (`ped`, `coords`, `vehicle`, `seat`, `weapon`, `playerId`, `serverId`, `pauseActive`) |
| `lib.guard` | server | `throttle`, `isThrottled`, `lock`, `unlock`, `withLock`, `toAmount`, `isNear` |
| `lib.spawn` | client | `prop`, `ped`, `blip`, `pointProp`, `pointPed`, `clearAll` |
| `lib.lru`, `lib.heap`, `lib.ringbuffer` | shared | bounded LRU cache, min/max priority heap, fixed-size O(1) circular buffer |
| `lib.table`, `lib.array` | shared | table helpers (`deepclone`, `contains`, `matches`, `merge`) and array helpers |
| `lib.cron` | server | scheduled server jobs |
| `lib.dui` | client | world-space DUI rendering (`skills/ui/dui.md`) |
| `lib.requestModel`, `lib.requestAnimDict`, `lib.requestNamedPtfxAsset` | client | streaming asset loaders with timeout |
| `lib.drawText.text2D(text, x, y, style, scale, r, g, b, a, font)` / `text3D(coords, text, style, ...)` / `text3DAt(x, y, z, text, style, ...)` | client | in-resource text drawing; `style` is a module-level table (`scale`, `scaleX`, `font`, `colour`, `dropShadow`, `edge`, `dropShadowFlag`, `outline`, `centre`, `proportional`, `origin`) so nothing is allocated per frame; the trailing args override per call |
| `lib.addKeybind` | client | rebindable keys |
| `lib.raycast` | client | camera/world raycasts for placement and targeting |

### Server Guards (`lib.guard`)

Use `lib.guard` inside `core/sv_*.lua` methods to standardize boundary checks without per-resource boilerplate:

- `lib.guard.throttle(src, key, ms)` / `lib.guard.isThrottled(src, key, ms)` — per-player rate limiting.
- `lib.guard.lock(src, key)` / `lib.guard.unlock(src, key)` / `lib.guard.withLock(src, key, fn)` — per-player in-flight mutex around checks and mutations (prefer `withLock` when yielding so locks always unwind).
- `lib.guard.toAmount(value, max)` — validates and floors a positive integer amount within `1..max` (rejects `nil`, `NaN`, `<= 0`, or `> max`).
- `lib.guard.isNear(src, coords, maxDist)` — verifies the player ped exists on the server and is within `maxDist` using squared distance.

### Client Spawning (`lib.spawn`)

Use `lib.spawn` inside `core/cl_*.lua` methods for local world props, peds, and blips:

- `lib.spawn.prop(opts)`, `lib.spawn.ped(opts)`, `lib.spawn.blip(opts)` — creates tracked local entities/blips and releases streamed models automatically.
- `lib.spawn.pointProp(opts)`, `lib.spawn.pointPed(opts)` — binds local prop/ped creation and deletion to spatial proximity (`lib.points`) so entities exist only while nearby.
- `lib.spawn.clearAll()` — deletes all tracked entities and blips owned by the resource; call in `onResourceStop`.

## Internal Performance Rules (for editing 1nfx_lib itself)

- `lib.grid.getNearbyEntries` caches per `filter` (points and zones each keep their own cache); never go back to a single shared cache slot, because the two scanners evict each other every 300ms.
- Build hot-path arrays as plain tables, then `setmetatable(t, lib.array)`; `lib.array:new()` runs the class constructor and `__newindex` fires on every append.
- Comparators for `table.sort` in scan loops are module fields, not closures created each step.
- `lib.class` private access caches misses as well as hits (`classMethods[func] = false`), so a non-method caller doesn't trigger a `pairs` scan over the class on every access.
- Keybind release: if a key was pressed, always deliver `onReleased`, even when the release happens inside the pause menu or while disabled, so the key never gets stuck as pressed.

## Forbidden UI Bridges In Gameplay Scripts

`1nfx_lib` may bridge `ox_lib`-named UI functions for legacy compatibility, but gameplay scripts must call the server's UI exports directly (`scripts/lint-resource.mjs` enforces `forbidden-oxlib` everywhere outside `1nfx_lib`):

| Do not use | Use instead |
| --- | --- |
| `lib.notify` | `Module:Notify` (`pNotify:SendNotification`, see `skills/common/core-api.md`) |
| `lib.progressBar`, `lib.progressCircle`, `lib.progressActive`, `lib.cancelProgress` | `exports["1nfx_processbar"]:...` |
| `lib.showTextUI`, `lib.hideTextUI`, `lib.isTextUIOpen` | `exports["1nfx_textui"]:...` |
| `lib.registerContext`, `lib.showContext`, `lib.inputDialog`, `lib.alertDialog` | the resource's own NUI |

## Points & Lifecycle Cleanup

Store every point/zone on the module and remove on stop (and call `lib.spawn.clearAll()` when `lib.spawn` is used):

```lua
self.Points[#self.Points + 1] = point
```

```lua
for _, point in ipairs(self.Points) do
    point:remove()
end
self.Points = {}
lib.spawn.clearAll()
```

Inside `lib.points` callbacks (`nearby`, `onEnter`, `onExit`) `self` is the point, not the module: call methods through the module name.

## Provided Names And Third-Party Resources

- `1nfx_lib` declares `provide "ox_lib"` and `provide "er_lib"`, so a third-party resource that includes `@er_lib/init.lua` (for example `errorism.optimize`, which is obfuscated and cannot be audited) loads `1nfx_lib/init.lua` instead. The real `er_lib` folder must not exist in `resources/` (it was moved to `_backup/2026-11-15/er_lib`), otherwise the real resource wins and demands `ensure er_lib`.
- `er_lib` only exposes UI that `1nfx_lib` does not bridge: radial menu, `registerMenu`, `setNuiFocus`/`resetNuiFocus`, `setLocale`. No resource outside `er_lib` calls them. If an obfuscated resource turns out to need one, add it to `1nfx_lib` instead of restoring `er_lib`.
- `er_lib:notify`, `er_lib:defaultNotify`, `er_lib:alertDialog` are aliased to the 1nfx UI in `core/cl_ui.lua`.
- The `ox_lib:cache:*` alias event was removed: every cache change triggers each event in every resource that registered it, and no listener existed.
- Rollback: move `_backup/2026-11-15/er_lib` back to `resources/[resources]/[errorism]/er_lib`, add `ensure er_lib` before `ensure errorism.optimize`, and delete `provide "er_lib"`.

## Replay Capture Is Always On (1nfx_replay)

- The owner wants the killer-side capture running continuously while alive. Do not gate it behind a combat window. Cut cost through `low_end_*` quality (960x540, 24 fps) and by avoiding per-frame GPU `readPixels`.
- Packet loss is read on the server with `GetPlayerPeerStatistics(src, 0) / 65536 * 100` (percent), sampled at kill time into `replay.net`, because the statistic only refreshes about every 10 seconds. Ping comes from `GetPlayerPing`.
