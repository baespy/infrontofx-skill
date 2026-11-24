# Playbook

Levers ordered by how much players feel them on a typical custom-content server. Each lever: why it works, how, risk. Evidence tags: **[src]** read in cfx source or docs, **[std]** standard RAGE/Chromium practice, **[inf]** inference, measure before keeping. Checked 2026-11-24 against citizenfx/fivem master; recheck when the artifact changes.

## Contents

- A. Streamed assets
- B. NUI and CEF
- C. Lua runtime
- D. Shared services
- E. Network and OneSync
- F. Server and database
- G. Adaptive quality
- H. Join time
- I. Perceived smoothness
- Not worth it

## A. Streamed assets

The game has a fixed streaming and texture budget. When custom assets overflow it, the engine drops detail: textures turn blurry or vanish, models pop in late, and each load stalls the frame. This is the most common cause of "the server stutters" on content-heavy servers, and Lua work cannot fix it.

**Memory per asset** [src]: an RSC7 file header holds two page-flag words. FXServer decodes them with the same formula as CodeWalker (`ConvertRSC7Size`, `ResourceStreamComponent.cpp`) and prints `Asset <res>/<name> uses X MiB of physical|virtual memory` above 16 MiB, with stronger colors above 32 and 64 MiB and the "Oversized assets can and WILL lead to streaming issues" text above 48 MiB. Target: every asset at or below 16 MiB physical and virtual. `scripts/stream-audit.mjs` reproduces this offline for every file.

**Texture checks** (`stream-audit` reads every texture header inside each ytd):
- 4096 on any side -> 2048 or 1024. A 4K DXT5 with mips is about 21 MiB; 2K is 5.3 MiB; 1K is 1.3 MiB. [std]
- Uncompressed (`A8R8G8B8`) at 512+ -> DXT1 (opaque) or DXT5/BC7 (alpha). Uncompressed is 4 bytes per pixel, DXT1 is 0.5: an 8x cut with mostly invisible loss. [std]
- `mips=1` at 256+ -> generate the full mip chain. Without mips the GPU samples the full-size texture at every distance (shimmer, memory bandwidth). [std] RAGE streams whole dictionaries; distance detail comes from separate `+hi`/`_hi` dictionaries, not from single mips.
- Non power of two (or not a multiple of 4) -> resize to the nearest power of two; block compression needs multiples of 4 and GTA tools expect powers of two. [std]
- Vehicle livery and clothing ytd are the usual offenders (one car at 80-140 MiB is common in packs). Fix the 20 biggest first; the tail rarely matters.

**Fake LODs** [std]: a vehicle ships `name_hi.yft` (L0, used close) and `name.yft` (L1 and lower, used at range). When `name.yft` is about the same size as `_hi`, the far model is probably the full one, so distant cars cost full detail. A base around 30-50% of `_hi` is a rough guide [inf]: file size is a weak proxy (embedded textures differ), so confirm LOD levels and vertex counts in Sollumz or CodeWalker before rebuilding real L1/L2 LODs (Blender decimate, then Sollumz export) for the worst pairs.

**Duplicates** [src for conflict]: the same file name streamed by two resources conflicts, and only one copy wins (load order). Byte-identical files under different names can each be resident separately. Download cost is likely deduplicated by the client cache, which keys files by content hash [inf]. Keep one owner and delete or rename the rest after grepping for the name in Lua (`RequestAnimDict`, model names, ptfx assets). Many same-resource copies are intentional aliases (minimap variants, logo slots); leave those.

**Always-resident overrides**: overriding a vanilla dictionary (`core.ypt`, `mapzoom` minimap tiles, timecycle) keeps the custom copy resident for the whole session. Trim emitters and textures inside it, or load a separately named dictionary on demand (`lib.requestNamedPtfxAsset` then `RemoveNamedPtfxAsset`).

**Interiors and IPLs** [std]: a generic IPL loader enabling dozens of vanilla interiors on a custom map costs streaming memory and idle threads for places nobody visits. Whitelist only interiors players reach.

**Map lighting**: shadow-casting lights are the most expensive light type; custom maps with many shadowed point lights cost GPU every frame. Use `map-forge` light rules (few shadow casters, emissive textures for small fixtures).

**Unused resources**: a folder under `resources/` that is not ensured costs players nothing, but one accidental `ensure` adds its full size. Move dead content to `_dev`.

## B. NUI and CEF

FiveM runs one windowless CEF browser at the monitor refresh rate with accelerated shared-texture paint; every resource `ui_page` is a full-screen iframe inside one root page [src: `NUIWindow.cpp`, `NUIInitialize.cpp`, full-screen NUI docs]. Chromium produces a new frame only when something is damaged [std]. So one always-running animation, `requestAnimationFrame` loop or video in any loaded frame, even an invisible one, can keep the whole NUI layer repainting at 144 Hz [inf: measure with `nui_devtools` Performance while every UI is closed].

- **Idle must be zero**: with every UI closed, a 10 s Performance capture shows no scripting and no paint. `perf-scan` flags `nui-infinite`, `nui-raf`, `nui-interval` as candidates only: on one 55-page server, 140 static infinite-animation hits held 1 real idle cost. Confirm with `scripts/nui-idle.cjs` (closed state, then open and close with the real actions) before editing. The usual real case: a panel hidden with `opacity: 0` for its fade-out while a child keeps an infinite shimmer; fix with `.panel.hidden .child { animation-play-state: paused; }`.
- **Infinite animations**: add an idle class after the fade-out that sets `animation: none` (or `animation-play-state: paused`) and `display: none` on the root. `opacity: 0` and `visibility: hidden` keep painting.
- **Blur**: `backdrop-filter` and `filter: blur()` re-render the area behind them on every frame that changes underneath, which is every game frame for a HUD. Use flat `rgba` or a pre-blurred image. Theme files that force `backdrop-filter: none` must load last.
- **Timers**: start `setInterval` and rAF loops on open, clear them on close; skip DOM writes when the value did not change.
- **Frame count** [inf]: each iframe has its own document, JS heap, fonts and framework copy. Moving small no-focus UIs into the existing HUD hub (`NUI_DUI.md`, export-fed) removes a frame each. Do not merge focus-taking apps that own their own routing.
- **Images**: an icon shown at 128 px does not need a 2000 px PNG. Resize to 2x display size and encode webp; PNG 2-4 MB -> webp 30-150 KB is typical. Animated effects: webp or a sprite sheet, never a GIF.
- **Fonts**: one copy served by the lib (`nui://1nfx_lib/html/...`) instead of a copy per resource; woff2, subset to Thai + Latin.
- **Audio**: wav -> ogg/opus 96-128 kbps; one folder per resource, no duplicates.
- **Frameworks**: a 500 KB React bundle per small UI is a parse and heap cost per frame; share a vendor chunk or use vanilla for tiny UIs (`skills/ui/vanilla-ui.md`).
- **Debug UIs**: library debug pages (database UI, editors) should not ship `ui_page` to every player in production.
- **DUI**: a DUI is a full extra browser. Create it when needed, destroy on close; never at boot pointing at a remote URL.
- **Client convar** [src]: `nui_useInProcessGpu` defaults to true on current builds (also disables the CEF GPU watchdog); any lag benefit is [inf]. ReShade older than 5.9.1 is blocked while it is on: players should update ReShade rather than turn the convar off. A server cannot set it.

## C. Lua runtime

The deep, source-verified Lua levers (state bag and export allocations, per-handler event cost, OAL natives, the process-wide timer list, state bag handler filters, lmprof, CfxLua table helpers, staggering and script LOD) live in `references/lua-unconventional.md`; this section is the short version.

- **One Lua state per resource** [src]: every resource with client scripts is its own `lua_State` with its own scheduler, its own copy of every imported lib module and its own garbage collector. Collapsing tiny client-only helpers into their real owner removes a state; never split a system into micro-resources.
- **Natives are not free** [src]: each call marshals arguments into a native context, crosses a guarded call and pushes results. Read once per frame or tick and reuse (`cache.*`, `lib.onCache`), never the same native several times in one frame.
- **Backtick hashes** [src]: `` `WEAPON_PISTOL` `` is hashed at compile time; `GetHashKey("WEAPON_PISTOL")` hashes at runtime (now on a fast C path, still a call plus string work). Use backticks for literals, cache `GetHashKey(prefix .. name)` results in a table at load.
- **GC is stock Lua 5.4 incremental** [src]: the runtime never steps or tunes GC (one exception: a full collect when the profiler stops); collection is paced by allocation. Per-frame tables, string concatenation, closures and `json.encode` drive GC pauses that show as random hitches. Remove allocation from frame loops first. `collectgarbage("generational")` is not blocked and can cut pause times for allocation-heavy resources, but has no FiveM measurements [inf]: try it in one resource, compare resmon memory and worst frame over the same scenario, keep it only with a measured win.
- **Exports copy**: arguments and results cross runtimes by serialization; never call an export per frame or per player when one bulk call or a cached value works (`memory/performance-research.md` -> Lessons From The 2026-11-23 [1nfx] + [core] Pass).
- **Frame loops**: one `Wait(0)` loop per resource at most, alive only while something needs it; startup "wait for Core" loops use `Wait(100)` or the imports global.
- **Time slicing**: big client jobs (spawning 200 props, applying 700 texture replacements) run in slices per frame, then `Wait(0)`, never in one frame. Client Lua has no `os` library [src], so budget with `GetGameTimer()` (millisecond steps: allow 1-2 ms) or a job count per frame; `os.clock()` exists only in server scripts.
- **Distance math**: `#(a - b)` on native vectors is one VM op in CfxLua; squared distance pays off only where coordinates are already split into x, y, z (`memory/performance-research.md`).

## D. Shared services

When the same per-frame pattern lives in several resources, each runs its own thread every frame. Moving it into one lib service turns N threads into 1 and makes the cost visible in one place. Designs and contracts: `references/shared-services.md`.

| Copied pattern | Service |
| --- | --- |
| `DisableControlAction` loops while in zones, menus, vehicles | control-block registry: callers add and remove named blocks, one frame loop applies the union, sleeps when empty |
| own `lib.points`/`lib.zones` scanner per resource | point broker: one scanner in the lib resource, owners get enter/exit events |
| hand-written time slicing | frame-budget queue: `lib.budget.push(name, fn)` jobs share a per-frame budget |
| fixed graphics preset chosen by hand | adaptive quality governor on top of the existing preset owner |

## E. Network and OneSync

Convar facts [src, `ServerGameState.cpp`, server docs]:

| Convar | Fact | Do |
| --- | --- | --- |
| `onesync_population` | read-only, default true; false removes all ambient ped/vehicle sync | false on servers without ambient AI |
| `onesync_distanceCulling` | false makes every entity relevant to every client | keep default true |
| `onesync_radiusFrequency` | default true; for peds, objects and empty vehicles: 50 ms normal, 150 ms off-screen, 250 ms past 250 m, 500 ms past 500 m, a quarter of that within 35 m. Players and occupied vehicles always sync at 50 ms (12.5 ms within 35 m) | keep default true |
| `onesync_distanceCullVehicles` | only matters outside big mode; little effect with `onesync on` | harmless, not a lever |
| `onesync_workaround763185` | registered but never read | remove |
| `onesync_enableBeyond` | internal, forced on with `onesync on` | do not add |
| `sv_experimentalStateBagsHandler`, `sv_experimentalOneSyncPopulation`, `sv_experimentalNetGameEventHandler` | default true on current artifacts (8510+, 8823+, 9149+) | do not add; older artifacts may still need them |
| `sv_useAccurateSends` | default true (send every 10 ms net tick); false batches sends on a 25 ms timer | keep default |
| `sv_filterRequestControl` | 0 off; 2 blocks control requests for player-controlled entities; 3 adds settled non-player entities; lockdown modes need it non-zero | 2 stops ownership ping-pong (rubber-banding); scripts that request control of player entities stop working |

- **Routing buckets**: `SetRoutingBucketPopulationEnabled(bucket, false)` and `SetRoutingBucketEntityLockdownMode(bucket, mode)` per instance (lobby, event arena) cut sync and stop client-spawned entity spam there. `relaxed` blocks networked entities that client scripts create (including networked `CreateObject` props); `strict` blocks every client-created entity; local non-networked props (`lib.spawn`) are unaffected. Lockdown is enforced only when `sv_filterRequestControl` is not 0.
- **Culling radius by context**: a per-player culling radius smaller in dense safe areas and larger in vehicles reduces entities each client simulates. Extend the existing owner, do not add a second one.
- **Latent events** [src]: `bps` is bytes per second per target (default 25000); sending to `-1` costs bps x players. Use for large one-off snapshots only.
- **Event budget**: events/s x bytes x recipients; snapshot once, then deltas; coalesce replaceable values; send only to viewers (`memory/performance-research.md` -> Event, Payload, And Log Budgets).
- **State bags**: granular keys, never written per frame; a replicated key changing 30 times per second floods every client in range.

## F. Server and database

- FXServer main tick is 50 ms, net 10 ms, sync about 8 ms [src]. The console warns only when the main or network thread stalls past 150 ms or the sync thread past 100 ms; smaller blocks still delay every player's events and only show in the profiler.
- SQL inside loops -> one `IN (...)` read or one multi-row `INSERT ... ON DUPLICATE KEY UPDATE` per 100-200 rows. Startup schema loops are fine.
- Per-player export calls inside `GetPlayers()` loops -> one bulk query (`Core.GetExtendedPlayers`) or a set maintained on load and drop.
- Proximity counts (players near N spots) -> one pass over players bucketed into a grid, not players x spots distance checks.
- Database host: `127.0.0.1`, not `localhost`: Node can resolve `localhost` to `::1` first and fail or slow down when MariaDB listens only on IPv4 [inf]. Size `innodb_buffer_pool_size` to the data set plus headroom when FXServer shares the machine; 70-80% of RAM is advice for a dedicated database host.
- Windows host: FXServer timers are libuv; no evidence that power plans or timer resolution change tick health. Measure before touching OS settings.
- Node `worker_threads` in FXServer JS has no official support and forum reports of crashes on resource restart [inf]; offload heavy CPU to a separate process if ever needed.

## G. Adaptive quality

A fixed preset is wrong for most players: strong PCs waste detail, weak PCs stutter. The governor (`references/shared-services.md` -> Adaptive quality governor) reads frame time over a window and steps the existing preset owner down when the 1% low frame is too slow and up after a long stable period, with hysteresis so it never oscillates.

Levers the presets may use [src, per-frame vs persistent matters]:
- `OverrideLodscaleThisFrame(scale)` per frame from one loop; below 1.0 shortens draw distance.
- `SetPedPopulationBudget(0-3)`, `SetVehiclePopulationBudget(0-3)`, `SetReducePedModelBudget(bool)`, `SetReduceVehicleModelBudget(bool)`, `SetDistantCarsEnabled(bool)`, `DisableVehicleDistantlights(bool)`: set once, persistent. With `onesync_population false` the population budgets matter little; the model budgets and distant cars still do.
- Feature knobs owned by resources: particle counts, decal rendering, prop spawn radius, DUI refresh, NUI animation level. Resources read the tier from cache and scale themselves.
- Player-only setting [src]: `vid_budgetScale` (menu "Extended Texture Budget", multiplier value/12 + 1). A server cannot set it; recommend raising it step by step when players report texture loss and have VRAM to spare.

## H. Join time

- `files` entries (NUI pages, images, audio, fonts) and resource scripts download at join; streamed assets go through the resource cache and may be fetched as the game requests them [inf]. Both are cached afterwards. Big wins: NUI images and audio, fonts copied per resource, source maps, oversized stream files.
- A CDN changes where bytes come from, not how many. Shrink first, then serve fast.
- Loading screens should not load remote media or heavy video.

## I. Perceived smoothness

Players judge by response time to their action, not by resmon.
- **Snapshot first**: open menus instantly from a cached snapshot, refresh in the background; never block opening on a server callback.
- **Optimistic UI**: show the expected result at once, reconcile when the server answers, roll back on reject. Server stays authoritative.
- **Prewarm**: request models, anim dicts, ptfx and NUI images when the player enters the zone, not on the key press. First-use stalls are the hitch players remember.
- **Spread spawns**: entities appear over several frames (time slicing) instead of one frozen frame.
- **Never animate layout**: animate `transform` and `opacity` only; width, top and box-shadow animations force layout and paint.

## Not worth it

- Global `GetGamePool` sweeps "to clean entities": ownership bugs and their own cost.
- Copying "optimized server.cfg" lists: most lines are defaults or dead.
- Micro-optimizing cold code (startup, admin commands) while assets overflow the budget.
- Disabling features players like for a gain nobody measured.
