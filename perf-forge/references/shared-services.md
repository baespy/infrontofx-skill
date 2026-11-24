# Shared services

Designs for lib-level services that replace per-resource copies. Each turns N frame threads into one. Build them in `1nfx_lib` or in the existing owner inside `1nfx_core`, following the pack root rules (OOP methods, no comments, no file-level locals, `Config` per resource). Read the current lib and core files before building: names below are the intended contract, verify they do not clash.

## Contents

- Adaptive quality governor
- Control-block registry
- Frame-budget queue
- Point broker
- Rollout

## Adaptive quality governor

**Owner**: the framework graphics owner (presets, `/graphics`, preset frame loop). Never a new resource.

**Measure cheaply**: a permanent `Wait(0)` sampler is itself a frame cost. Sample in bursts: every `Config.Graphics.Auto.EveryMs` (10000) run a `SampleMs` (2000) burst recording `GetGameTimer()` deltas per frame (real time; `GetFrameTime()` is the game timestep and changes with time scale), then sleep. When the preset frame loop is already running, sample inside it instead of starting a second thread. Throw a burst away when `cache.pauseActive` was set, the screen was faded out, or the player spawned or teleported in the last 10 s: those stalls are loading, not the preset.

**Decide on the worst frames, not the mean**: per burst compute the 1% low frame time (sort the samples, take the 99th percentile). Step down one preset when it exceeds `DownMs` in 2 bursts in a row; step up when it stays under `UpMs` for `UpBursts` bursts. Starting values such as 25 ms, 12 ms and 6 bursts are guesses [inf]: tune them on real captures. The gap between the thresholds and the burst counts is the hysteresis that stops oscillation.

**Respect the player**: a manual `/graphics <preset>` pins the preset and turns auto off until `/graphics auto`. Store the choice with KVP (`SetResourceKvp`) so it survives reconnects.

**Publish the tier**: resources should scale their own features (particle count, prop radius, DUI refresh, animation level) from one number, 0 (lowest) to 4 (highest). Add `perfTier` to the lib cache: the lib already fires `1nfx_lib:cache:<key>` from its cache setter, so a new lib export `SetCacheValue(key, value)` (to add, allowlisted keys only) lets the owner publish it, and every resource reads `cache.perfTier` or subscribes with `lib.onCache("perfTier", fn)`. No state bag (nothing to replicate), no per-frame reads.

Sketch (method names indicative; `SetCacheValue` does not exist yet):

```lua
function Core:GraphicsAutoBurst()
    local auto = Core.PlayerState.graphicsAuto
    local samples, count = auto.samples, 0
    local last = GetGameTimer()
    local stopAt = last + Config.Graphics.Auto.SampleMs
    while last < stopAt do
        Wait(0)
        local now = GetGameTimer()
        count += 1
        samples[count] = now - last
        last = now
        if cache.pauseActive or IsScreenFadedOut() then
            return nil
        end
    end
    for i = count + 1, #samples do
        samples[i] = nil
    end
    table.sort(samples)
    return samples[math.max(1, math.floor(count * 0.99))] or 0.0
end

function Core:GraphicsAutoStep(low)
    local auto = Core.PlayerState.graphicsAuto
    if not auto.enabled or not low or GetGameTimer() < auto.quietUntil then
        return
    end
    local cfg = Config.Graphics.Auto
    auto.slow = low > cfg.DownMs and auto.slow + 1 or 0
    auto.fast = low < cfg.UpMs and auto.fast + 1 or 0
    if auto.slow >= 2 and auto.index > 1 then
        auto.index -= 1
        auto.slow = 0
    elseif auto.fast >= cfg.UpBursts and auto.index < #cfg.Order then
        auto.index += 1
        auto.fast = 0
    else
        return
    end
    Core.Api.SetGraphics(cfg.Order[auto.index])
    exports["1nfx_lib"]:SetCacheValue("perfTier", auto.index - 1)
end
```

**Report**: changing presets automatically changes what players see; tell the owner which presets the governor may use and the thresholds.

## Control-block registry

**Problem**: zones, menus, vehicles and safe areas each run a `Wait(0)` loop calling `DisableControlAction` and `DisablePlayerFiring`. Five resources mean five frame threads doing overlapping work.

**Service** (client, lib resource): `lib.blockControls(name, spec)` and `lib.unblockControls(name)`. `spec` lists control ids per group (`{ 0, 24 }`), `firing = true`, `weaponWheel = true`. The service keeps a map of active blocks, rebuilds one merged list when the map changes, and runs a single frame loop only while the map is not empty. Blocks owned by a resource are dropped on its `onResourceStop`.

Contract notes: callers keep their own reasons (zone, menu) and only add or remove; the service never decides gameplay. Existing `lib.disableControls` users can stay; migrate frame loops one resource at a time with before and after resmon.

## Frame-budget queue

**Problem**: big client jobs (prop spawning, texture replacement, DUI warm-up) are hand-sliced differently in each resource, or not sliced at all.

**Service**: `lib.budget.push(name, fn)` queues a job; one loop runs queued jobs until the frame budget is spent, then `Wait(0)`; it sleeps when the queue is empty. Client Lua has no `os` library, so the client budget is `GetGameTimer()` based (millisecond steps: 1-2 ms) plus a maximum job count per frame; server scripts may use `os.clock()`. Jobs that return `true` are re-queued (cooperative long jobs). Per-resource queues are cleared on that resource's stop.

Keep it per resource (imported module, runs in the caller's runtime): a cross-resource queue would add export copies per job, which costs more than it saves.

## Point broker

**Problem**: every resource that imports `lib.points` or `lib.zones` runs its own scanner thread (about every 300 ms) and grid query. With about 30 such resources that is about 30 scanners doing the same distance work.

**Service**: the lib resource owns one grid of all registered points; resources register points through an export with an id and radius and receive enter/exit through client events named `<owner resource> .. ":CL:pointEnter"` / `":CL:pointExit"` (house event pattern). Only `nearby` frame callbacks stay in the owning resource, started on enter and stopped on exit.

Trade-off: registration crosses runtimes (export copy) once per point, not per frame. Enter and exit events are local but not free: each event is packed once and unpacked in every resource that listens, so keep the payload to the point id. Measure the combined scanner cost (resmon sum of the 30 resources at idle) before and after; if the sum is already under about 0.1 ms, skip this service.

## Rollout

1. Build the service in the lib with no callers; lint; restart only the lib on a test server.
2. Migrate one heavy caller; before and after resmon in the same scenario card.
3. Migrate the rest one resource at a time; contracts of each caller unchanged.
4. Record the lesson in `memory/performance-research.md` and the API in `skills/common/1nfx-lib.md`.
