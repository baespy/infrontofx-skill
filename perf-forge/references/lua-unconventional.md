# Lua: unconventional levers

Costs most FiveM scripts never see, because they live inside the runtime glue (`citizen/scripting/lua/scheduler.lua`, `natives_loader.lua`, shipped with every FXServer artifact and read for this file on 2026-11-24) or inside the engine. Each lever names the mechanism, the house-style fix, the `perf-scan` rule that finds it, and the `luabench` group that measures it on the real runtime. Code follows the pack root rules: methods only, no comments, no file-level locals; a hot method may pull locals.

## Contents

- Measure on the real runtime
- A. Hidden allocations in the runtime glue
- B. Events: pay per handler, not per event
- C. Natives: the call boundary
- D. Engine events instead of polling
- E. Frame budget: spread work, do not just shrink it
- F. Memory and garbage collector
- G. Data layout
- Not worth it

## Measure on the real runtime

Copy `templates/luabench/` to `resources/[dev]/1nfx_luabench` on a test server, `ensure 1nfx_luabench`, then type `luabench` in the server console and `luabench_cl` in F8. Each row prints ns per operation and the ratio to the first variant of its group, on the exact CfxLua build the server runs. The client clock is `GetGameTimer()` (1 ms), so client cases run long loops; trust ratios over 10% only. Remove the resource afterwards. Every lever below names its group, so a claim in a report can cite a measured ratio instead of folklore.

`perf-scan` rules for this file: `statebag-hot`, `export-hot`, `nui-send-hot`, `getplayers-hot`, `string-hash-arg`, `pack-per-target`, `event-fanout`, `self-event`, plus the older `frame-*` rules.

## A. Hidden allocations in the runtime glue

**State bags allocate on every access** (luabench: `local state bag`, `entity state bag`, `global state`). `LocalPlayer` is `Player(-1)`; reading `.state` runs `NewStateBag`, which builds a new table and a new metatable, formats `"player:%d"` and calls `GetPlayerServerId(PlayerId())`, every time. `Entity(ent).state` adds `NetworkGetNetworkIdFromEntity` and another `format`. Every `bag.key` read then calls `GetStateBagValue`, which deserializes msgpack. A loop that reads `LocalPlayer.state.isDead` per frame allocates two tables and a string per frame and decodes the value each time.
- Hold the bag object: `self.PlayerState.bag = LocalPlayer.state` once (the local player's server id does not change); per player on the server, `Player(src).state` held in `ServerState.bags[src]`, cleared on `playerDropped`.
- Mirror hot values into a plain table with `AddStateBagChangeHandler(key, bagFilter, fn)` and read the table: zero natives, zero decode.
- **Always pass a key filter** (`statebag-handler-nofilter`): the key and bag filters are exact string compares done in C++ before Lua is called (`ResourceScriptFunctions.cpp`); a `nil` filter matches everything, so a `nil, nil` handler pays a msgpack serialize, a Lua call and an unpack for every state change of every player and entity in scope. Worse, while any handler is registered anywhere, every `SetKey` unpacks the value in C++ (`StateBagComponent.cpp`). Bag names are `player:N` / `entity:N`: there are no wildcards, so the key filter is the cheap one; filter the bag in Lua after.
- Writes are the same: `bag.key = v` packs and sets every time; write only on change.
- `GlobalState.key` reads decode every time: mirror it the same way.

**`exports` allocate per call** (luabench: `export`). `exports.res` returns a fresh proxy table with a metatable; `[name]` builds a fresh closure; the call runs `pcall` with varargs, then crosses runtimes through a serialized function reference.
- Hold the proxy in a field: `self.Inventory = exports["1nfx_inventory"]`, call `self.Inventory:Name(...)`. Safe across provider restarts because the proxy resolves the export at call time.
- Never call an export per frame or per player. Ask once per pass for everything (`GetMany(ids)`), or let the provider push changes into a local cache (event or state bag) and read the cache.
- Do not cache the function returned by `exports.res.name`: after the provider restarts it calls a cleared cache entry.

**`SendNUIMessage` encodes every call** (luabench: `json`). It is `SendNuiMessage(json.encode(message))`. For a HUD updated often: compare the new values with the last sent ones, send only on change, and keep static messages pre-encoded (`SendNuiMessage(self.PlayerState.json.hide)`).

**`GetPlayers()` builds a table per call** (server, luabench: `player list`). It loops `GetNumPlayerIndices` / `GetPlayerFromIndex`, one native per player, and returns strings. Keep `ServerState.players` updated on `playerJoining` and `playerDropped` (and rebuilt once on resource start) and iterate that.

**Event names built per call** (luabench: `event name`). `scriptname .. ":SV:update"` concatenates and hashes a string on every send. Build every event name once into `Module.Events` at load.

## B. Events: pay per handler, not per event

From the event routine in `scheduler.lua`: one dispatch unpacks the payload once per receiving resource, then for **each handler** calls `debug.getinfo`, `string.format` (thread name) and `Citizen.CreateThreadNow` (a new coroutine) (luabench: `local event`).
- **One handler per event per resource** (`event-fanout`): register once, call methods inside. Five handlers on a frequent event cost five coroutines per dispatch.
- **No events to yourself** (`self-event`): `TriggerEvent(scriptname .. ":CL:x")` handled in the same resource packs, unpacks and spawns a coroutine for what `self:X()` does directly.
- **Pack once for many targets** (`pack-per-target`): `TriggerClientEvent(name, target, ...)` runs `msgpack_pack_args` on every call. For the same payload to a list of players:

```lua
function Module:SendToViewers(eventName, ...)
    local payload = msgpack.pack_args(...)
    local size = #payload
    for src in pairs(self.ServerState.viewers) do
        TriggerClientEventInternal(eventName, src, payload, size)
    end
end
```

  Only when every target gets identical arguments. This saves the Lua msgpack work only: C++ still copies the bytes into a new buffer per call, and there is no native list target (`-1` loops all clients in C++). The wrapper `tostring`s the target, so a hot loop can pass string ids. Sends through `TriggerClientEventInternal` bypass Lua-level hooks that wrap `TriggerClientEvent` (network counters in the framework imports); count them separately if those numbers matter.
- **Narrow noisy framework events**: an event that about 70 resources listen to costs about 70 unpacks per fire. Emit narrow events (`<core>:moneyChanged`, `<core>:jobChanged`) that only interested resources register, instead of one broad `setPlayerData`.
- **Payload size**: send ids and changed fields, never whole objects with functions (each function becomes a reference that must be duplicated and freed).

## C. Natives: the call boundary

- **Globals are looked up on every call**. Natives are bound lazily into `_G` by `natives_loader.lua`; each call is a global table lookup, then the native wrapper. In a hot method, pull the natives used in the loop into locals at the top of the method (allowed: locals inside a method) (luabench: `native lookup`).
- **String arguments to hash natives** (`string-hash-arg`): native wrappers call `GetHashKey` when given a string model or weapon name. `RequestModel("adder")` hashes on every call; `` RequestModel(`adder`) `` does not (luabench: `hash`, `model hash arg`).
- **Server natives with a player argument** call `tostring` on the id in the wrapper; pass the string id you already have (from `source` keep both forms if a hot path calls many such natives).
- **One native result per frame**: `PlayerPedId()`, `GetEntityCoords(ped)` and similar are cached by the lib (`cache.ped`, `cache.coords`); read the cache (luabench: `player ped`, `player coords`).
- **OAL: natives as direct C functions** (`use_experimental_fxv2_oal "yes"` in `fxmanifest.lua`, Lua 5.4). With it, `Citizen.LoadNative` returns a `lua_CFunction` for every native in the generated map, so a call skips the Lua wrapper, the `_in` varargs and the `_ts`/`_ch` helpers; on the client it calls the game handler directly, on the server it still goes through the script host (smaller gain). Natives outside the map (no name, `Any*` pointers, `DELETE_*`, `*_AS_NO_LONGER_NEEDED`, `SET_STATE_BAG_VALUE`, `TRIGGER_*_EVENT_INTERNAL`, ped variation and others) keep the wrapper. The flag is read by presence: `"no"` still turns it on. No official benchmark exists; measure with two copies of `luabench`, one with the flag (groups `native lookup`, `player coords`, `model hash arg`).
  Behaviour changes to audit before enabling in a resource (`manifest-oal` lint warns):
  - a `vector3` passed where the native takes x, y, z is not unrolled: the float reads 0 and later arguments shift; pass `v.x, v.y, v.z`;
  - arguments are read by position and type: a non-number to a float becomes 0, a non-number to an int becomes 1 or 0, `nil` or `0` for a string becomes NULL; hashes accept strings and hash them in C++;
  - bool out-pointers return real booleans, multiple results come back as `retval, out1, out2`;
  - handle-returning natives with 64-bit values once broke DUI natives; third-party resources have reported cosmetic bugs and turned it off. Enable per resource, test every native path, keep it only with a measured gain.
  Audit first: `node scripts/oal-audit.mjs resources --only=<res>[,<res>]` lists native calls per resource and flags vector arguments (including swizzles such as `v.xyz`, the classic miss), multi-return natives, numeric compares of out-pointer bools (`hit ~= 1` silently becomes always true), and DUI natives. Fix each flag so it works in both modes (`v.x, v.y, v.z`; `hit == true or hit == 1`), then add the flag on its own line right after `lua54`, matching the manifest's syntax (`lua54("yes")` resources get `use_experimental_fxv2_oal("yes")`), and diff the manifest: an insertion inside `shared_scripts` breaks the resource. Imports run in the consumer's runtime, so lib and framework import code also switches mode in that resource; audit them once.

## D. Engine events instead of polling

A loop that asks the game "did X happen yet?" every frame or every 250 ms costs that work forever. The engine already knows and can tell you once.
- **Input**: `RegisterKeyMapping` + `RegisterCommand("+name")` / `("-name")` instead of `IsControlJustPressed` in a `Wait(0)` loop: zero cost until the key is pressed, and players can rebind it.
- **Damage, death, vehicle entry**: hits that involve the local ped (victim, attacker, or the ped's vehicle as attacker) arrive once through `AddEventHandler("1nfx_core:gameEvent", fn)` with the same `(name, args)` as `gameEventTriggered`. 1nfx_core is the only filter, so a new resource must not register its own `gameEventTriggered` unless it really needs hits between other players (1nfx_weaponskin hit effects). Replace health-polling and `IsPedInAnyVehicle` loops; the lib already raises `cache.vehicle` changes (`lib.onCache("vehicle", fn)`).
- **State instead of polling**: when another resource owns a flag, read it from a state bag change handler, not a timer.
- **Promises instead of wait loops**: `while not ready do Wait(100) end` becomes `local p = promise.new()` resolved by the event that sets `ready`, then `Citizen.Await(p)`: no wakeups at all until it is ready.
- **Server interest sets from OneSync scope**: `playerEnteredScope` / `playerLeftScope` fire (queued) with `{ player = "<id>", ["for"] = "<id>" }` when one player's ped becomes relevant to another client, so the server knows who can see whom without distance loops. Caveats: they depend on culling (default 424 units), buckets and free slots, the docs warn about their scaling cost and prefer state bags, and whether they fire on respawn or model change is unverified. Use them for small sets (an arena, a spectator list), clear your sets on `playerDropped`, never as a global replacement for culling.

## E. Frame budget: spread work, do not just shrink it

Players feel the worst frame. Ten resources that each do 0.3 ms of work every 1000 ms are harmless, unless they all do it in the same frame.
- **Phase-stagger periodic loops**: loops started in the same tick with the same `Wait(1000)` stay aligned and stack into one spike every second. Start each long-period loop with a one-time offset, `Wait(math.random(0, interval))`, then the normal interval. Same idea on the server for per-player timers created in one burst after a restart.
- **Round-robin sweeps**: instead of checking 400 entries every 2 s in one frame, check `ceil(400 / 20)` per 100 ms tick, resuming where the last tick stopped. Same total work, one twentieth of the spike.
- **Script LOD**: update rate by distance like the engine's model LOD: entries within 15 m every frame, 15-60 m every 4th frame, beyond every 20th, nothing past the draw range. Name tags, markers, prop animations and hologram prompts are the usual candidates.
- **Time slicing**: long client jobs stop after about 1-2 ms of work (`GetGameTimer()` budget; client Lua has no `os.clock`) and continue next frame.
- **One frame loop per resource**: a single `Wait(0)` loop that runs a table of active per-frame tasks, started when the first task is added and ending when the table is empty. Five feature loops become one coroutine resume per frame.
- **Timers live in one list for the whole process** [src: `ScriptHost.cpp`]: `CreateThread`, `Wait` and `SetTimeout` are C++; every sleeping thread of every resource is a node in one unsorted list that is walked and compared on every tick. A sleeping thread runs no Lua but costs a compare per tick forever, and each wake of a `Wait(0)` thread costs a registry ref and unref, two boundary submits, a `lua_resume` and a new list node. So 1,600 per-player `SetTimeout`s or a thread per entity make every tick of the whole server slower. For many deadlines (cooldowns, expiries, respawns) keep one `lib.heap` of deadlines and one thread that sleeps until the earliest (luabench: `thread`).
- **`ClearTimeout` caveat** [src, not tested in game]: it only searches timers created in the current callback; a timer created earlier cannot be cancelled and still fires. Cancel with a generation token checked inside the callback (`if self.PlayerState.gen ~= gen then return end`), not with `ClearTimeout`.
- **`Wait(ms)` drops fractions** and treats `nil` as 0: `Wait(sleep)` with an unset variable is a frame loop.

## F. Memory and garbage collector

The runtime is LuaGLM 5.4 (5.4.9 in current master) with its stock incremental GC, one `lua_State` per resource on its own rpmalloc heap, paced only by allocation; FiveM never changes the mode. Every table, closure, string concat and decoded state value is future GC work that lands on some later frame as a hitch.
- **Find the allocators first**: `profiler resource <name> <frames>` (works in F8 and the server console, not in the docs) runs lmprof in instrument plus memory mode for one resource; `profiler view` or `profiler saveJSON` then shows time and bytes allocated per function. Fix the top allocators, not guesses.
- **Zero-allocation hot paths**: reuse tables (`t.x, t.y = ...` instead of `{ x = ..., y = ... }`), use `vector3` values instead of `{x,y,z}` tables: vectors are stored inline in the value slot and never collected (float32 components) (luabench: `distance`, `alloc`); no closures created inside loops (`closure`), no `string.format` per frame unless the text changed.
- **CfxLua table helpers**: `table.wipe(t)` empties a table and keeps its allocated slots for the next fill (reuse scratch tables without new garbage); `table.create(narr, nrec)` pre-sizes a table you are about to fill so it never rehashes while growing; `table.clone(t)` copies in C. Lua 5.4 `<const>` and `<close>` locals work inside methods (luabench: `table reuse`, `presize`).
- **GC mode per resource**: `collectgarbage("generational")` (defaults minor 20, major 100; the generational bugs of 5.4.0-5.4.4 are fixed in 5.4.9) or a tuned incremental (`collectgarbage("incremental", pause, stepmul, stepsize)`, defaults 200, 100, 13) at the top of a resource that allocates many short-lived objects (UI builders, per-frame scanners) can cut the worst pause. `luabench` prints total time and worst batch for both modes on the real runtime. Keep it only with a measured win in that resource (resmon memory, worst frame), never globally by default.
- **GC on quiet frames**: a resource that knows it is idle (menu closed, player in a loading screen, no active tasks) can call `collectgarbage("step", 0)` there, so collection work happens when nobody is looking instead of mid-fight.
- **Do not hold dead references**: per-player and per-entity tables keyed by ids grow forever unless cleared on drop and on entity removal; a growing resmon memory line is the symptom.

## G. Data layout

- Arrays with numeric `for` beat `pairs` over hashed tables for hot walks (luabench: `array walk`).
- Convert config lists to lookup maps once at load (`Module.ItemsByName`), never search a list per call.
- Pull nested fields into a local before a loop (`local hud = self.PlayerState.hud`) (luabench: `field access`).
- Precompute hashes, event names, labels and formatted static strings at load.

## Not worth it

- Rewriting cold code (startup, admin commands, rare events) for nanoseconds.
- Replacing `#(a - b)` on vectors with manual math: it is one VM op in CfxLua.
- Caching export functions or `xPlayer` objects across yields or provider restarts.
- Global GC tuning or `collectgarbage("collect")` on a timer: full collections are the hitch you are trying to avoid.
