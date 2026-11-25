# Beyond Lua: engine, protocol and runtime levers

When the Lua is already gated, faster Lua buys nothing. The remaining gains come from making the engine do the work, sending fewer bytes, and controlling the runtime itself. Facts were checked against citizenfx/fivem master and the native reference on 2026-11-25. Tags: **[src]** confirmed in source or docs, **[unk]** signature confirmed but effect undocumented (benchmark before relying on it), **[inf]** inference.

## Contents

- A. Let the engine render less
- B. Significance budgets in script
- C. Protocol: fewer bytes, fewer sends
- D. Runtime control
- E. Clock and weather without loops
- F. Server threads
- G. When not to redesign

## A. Let the engine render less

Set-once engine switches beat any per-frame script. Tie them to the graphics owner's presets or an adaptive tier; never add a second owner.

- **Vanilla performance timecycle modifiers** [src: base-game modifier dump]: the game ships modifiers its authors made to cut cost, usable with one call: `LODmult_global_reduce`, `LODmult_global_reduce_NOHD`, `LODmult_HD_orphan_reduce`, `LODmult_LOD_reduce`, `LODmult_SLOD1_reduce` (2, 3), `reducelightingcost`, `ReduceSSAO`, `reducewaterREF`, `WATER_refmap_off` (`verylow`, `low`), `NoPedLight`, `LIGHTSreduceFALLOFF`. `SetTimecycleModifier(name)` + `SetTimecycleModifierStrength(x)` and one extra slot (`SetExtraTimecycleModifier`). Only two script slots exist, so they collide with screen effects from other resources (death, drugs): route every use through one owner. Visual effect of each is undocumented: look at each before shipping.
- **Runtime modifiers without a file** [src]: `CreateTimecycleModifier(name)`, `SetTimecycleModifierVar(mod, var, v1, v2)`, and `GetTimecycleVarCount` + `GetTimecycleVarNameByIndex` to list the real variable names in game. Enumerate first; names quoted on forums are not all real. A file route also exists (`data_file "TIMECYCLEMOD_FILE"`).
- **Set-once render toggles** [src]: `DisableWorldhorizonRendering(true)` (far horizon LODs; empty skyline from height), `SetFogVolumeRenderDisabled(true)`, `SetVisualSettingFloat(name, value)` (runtime override of visualsettings values).
- **Population** [src]: `SetRoutingBucketPopulationEnabled(bucket, false)` on the server removes ambient peds and traffic for a bucket with one call; then delete every client loop that calls `Set*DensityMultiplierThisFrame`.
- **Culling radius** [src]: `SetPlayerCullingRadius(src, r)` is persistent; outside it the entity is not created on that client at all, the only real cap on remote players and their sync. Default 424, no minimum. Both culling natives are marked deprecated with "known, unfixable issues" (ghost vehicles, ownership) when reduced: prefer routing buckets for hard separation, and test any density mode in game.
- **Conceal** [unk]: `NetworkConcealPlayer(player, toggle, allowDamage)` hides a player locally the way the game hides players in MP interiors. Purely local (server sync unchanged), asymmetric (they still see you), so only for non-PvP areas; FPS gain is not documented anywhere. Benchmark before adopting.
- **Per-entity LOD** [unk]: `SetPedLodMultiplier`, `SetVehicleLodMultiplier`, `SetEntityLodDist` (uint16) are local and must be re-applied when a clone is recreated; whether they persist is undocumented. No native caps rendered peds.
- **Static props**: a script-created object takes an object pool slot and a script handle; a networked one also a net object and server sync. Entities placed in a streamed ymap are streamed by the engine with its LOD and need neither [src for the pools, inf for the saving]. Bake decoration that never changes; keep script spawning for things that change per player or state. `FreezeEntityPosition` and `SetEntityCollision(false)` are persistent toggles with no documented cost effect.
- **NPC peds** [unk]: flags (`SetBlockingOfNonTemporaryEvents`, `FreezeEntityPosition`, `SetPedCanRagdoll`) cut AI reactions, not draw cost. The structural lever is the real one: local, non-networked, spawned only inside a radius.
- **Decals and particles** [src]: nothing caps their count. `SetParticleFxLoopedFarClipDist(handle, range)` per looped effect, `RemoveParticleFxInRange` and `RemoveDecalsInRange` as one-shots; the per-frame decal switch needs a frame loop and hides evidence RP may rely on.

## B. Significance budgets in script

For anything multiplied by the number of nearby players (attached props, name tags, effects), a distance gate is not enough in a crowd: 300 players inside the radius all pass it.

1. Collect the candidates that pass the distance gate.
2. Score each: `distance x (already shown and 0.8 or 1.0) x (IsEntityOnScreen(ped) and 1.0 or 2.0)`. The first factor is hysteresis so the set does not flicker; the second prefers what the camera sees.
3. If the count is over the budget, sort and keep the best N; the local player is never cut.
4. Apply once per second, not per frame; reuse scratch tables.

Below the budget nothing changes, so normal play looks identical; only crowds degrade, and gracefully. Report it as a visible change.

## C. Protocol: fewer bytes, fewer sends

- **No compression on the wire** [src]: neither side enables ENet compression; every byte you pack is sent.
- **Keys cost more than values** [src: msgpack format]: a map row pays for every key string on every row. `{id, name, price, weight}` is about 35 bytes as a map and 14 positional, about 60% less; columnar (parallel arrays) saves one more header per row. Positional rows couple client and server: change both together and keep a schema version in the payload.
- **Split static from changing** : send name, text, avatar and other constants once per viewer (track a static key per viewer; resend only when the key changes), then a positional tick with only the changing numbers. A client that has no state for the tick's id asks for the full state through a throttled callback.
- **Deadlines, not ticks**: send `endsAt` once and let the client count down; send a growing value's start and rate when the client may know the rule.
- **Coalesce global state**: every `GlobalState` write is a packet to every client. Write on a trailing timer (one write per N seconds with the latest value) unless something reads it server-side immediately.
- **Limits** [src]: client-to-server event data is capped at 384 KiB; rate limiters default to 50 events/s (burst 200) and 128 KiB/s (burst 384 KiB) and drop the client beyond that. Large server-to-client reliable events stall other reliable traffic: use latent events with a sane `bps` above about 16-32 KB.
- **Client KVP as a cache** [src]: client KVP is a local LevelDB, never synced, keyed `res:<resource>:<key>` with no per-server namespace. Send only a version hash; fetch the catalog on mismatch (latent, positional) and store it with `SetResourceKvpNoSync` (the plain setter flushes to disk on every call and can hitch). Treat the stored copy as untrusted: verify its hash, never store secrets.
- **Interest management**: spatial data that only matters nearby (plants, drops, world objects) is replicated by cell: the server indexes entities and subscribers by grid cell, sends changes only to subscribers of nearby cells, and a client resubscribes when it has moved a fraction of the cell size. World-global replication of a spatial set is the shape to remove first.

## D. Runtime control

- **GC by game state** [src]: `collectgarbage("stop")` turns the collector off until `"restart"`; `"step"` runs one bounded step; `"count"` reads KB in use. FiveM sets no memory cap and never kills a resource for memory. Pattern: stop during a short burst that must not hitch (a fight, a cutscene), restart or step when idle, and always guard with a ceiling (`if collectgarbage("count") > limit then collectgarbage("restart") end`) because nothing else will stop the growth.
- **V8 is a JIT, Lua is an interpreter** [src]: the JS runtime runs with JIT enabled on client and server, on the same main thread as Lua. A coarse, pure-compute kernel called rarely with small arguments (sorting or scoring thousands of rows) can run several times faster in JS; every call crosses runtimes through msgpack, so chatty calls and native-heavy loops lose. No parallelism is gained.
- **CEF** [src]: master ships Chromium 144 (older clients 103). A resource cannot hide or throttle its own iframe: the root page keeps it visible. Hiding your root element stops paint but not rAF, timers or framework work. The real saving is a small inert shell that loads the heavy bundle on first open and fully unmounts on close (cancel rAF, intervals, listeners). `content-visibility: auto` and `contain` work on both versions and are a free win on long lists.
- **OAL, state bag caches, export proxies**: `references/lua-unconventional.md`.

## E. Clock and weather without loops

All set-once [src]: `NetworkOverrideClockTime(h, m, s)` holds until cleared; `SetMillisecondsPerGameMinute(ms)` sets the rate and survives the override on current builds; `PauseClock(bool)`; `SetWeatherTypeOvertimePersist(type, seconds)`, `SetWeatherTypeNowPersist`, `SetOverrideWeather`. Publish epoch, rate and weather in one global key, apply once on change and on join; no per-second or per-frame loop is needed. Out-of-range clock values crash the client; other resources that override the clock in loops will fight it.

## F. Server threads

[src: `GameServer.cpp`] Three loops: `svMain` (20 Hz, every resource script, Lua and JS; hitch warning past 150 ms), `svNetwork` (100 Hz), `svSync` (120 Hz timer, real sync work about 40 Hz, fanned out across cores). Scripts are single-threaded; only OneSync uses several cores. The only tick-rate control is `sv_useAccurateSends`: false halves sync frequency and send rate for less CPU and bandwidth at the price of visibly less smooth remote movement. Default true; A/B it with real players before considering it.

## G. When not to redesign

Count before rebuilding. A loop of 15 control-disable natives per frame is about ten microseconds, under 0.1% of a frame: with no persistent native that reproduces the same behaviour, redesigning it adds risk for nothing a player can feel. Spend the effort where cost multiplies: by players in a crowd, by recipients of a broadcast, by rows in a payload.
