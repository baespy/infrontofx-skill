# Architect mode

Optimize the design, not the line. Before touching code, ask whether the work should exist, at what rate, for whom, and in which process. Borrowed from how AAA engines stay fast (Unreal Significance Manager, Animation Budget Allocator, Replication Graph, tick aggregation, LOD) and translated to FiveM APIs that exist, checked against the runtime facts in `references/lua-unconventional.md` and `references/engine-protocol.md`. Use for: a system that feels heavy, a new system before it is built, a "rewrite for performance" request, or `/perf-architect`.

## Contents

- The seven questions
- Process
- Technique catalog (AAA to FiveM)
- Decision matrix
- Output template
- Worked example: 200 bots
- Guard rails

## The seven questions

Ask them in order; the first "no" usually beats every micro-optimization below it.

1. **Should this work exist at all?** Delete features nobody sees, debug paths, duplicate systems, work for players who are not looking.
2. **Who needs the result?** Only players in range, in the bucket, with the UI open, or in the vehicle. Everyone else gets nothing.
3. **How often does it really change?** Compute on change (event, state bag, dirty flag), not on a timer; a timer only when nothing announces the change.
4. **How precise must it look?** Players perceive smoothness, not exact values: send less, interpolate locally, update far things rarely.
5. **Can it be computed once?** At load, at build time, in SQL, cached until invalidated.
6. **Where is it cheapest?** Engine (natives, culling, scope), C side (json, msgpack, natives), NUI (CSS transitions), database (indexed query), or a shared lib service; Lua per frame is the most expensive place.
7. **Can the cost be spread?** Same total work across frames or ticks, never stacked into one frame.

## Process

1. **Frame the problem**: what players feel, the scenario card (`references/measure.md` -> Scenario card), and the current cost from a scan or capture (`scripts/perf-scan.mjs`, `profiler resource <name>`, resmon, network log). No number yet: say so and get one cheaply first.
2. **Read the real system**: every file of the resource, its events, exports, state bags, NUI actions, DB queries, and who calls it (grep the project). Map data flow: who produces, who consumes, how often, how big.
3. **Kill list first**: list work that can be deleted outright (question 1-2). Deleting is the biggest and safest gain.
4. **Generate at least five alternatives**, from different families in the catalog below (at least three families). Include one radical option (move the work to another layer or process) and the "do nothing" baseline.
5. **Score them** with the decision matrix. Reject any option that moves authority to the client, loses data, or breaks a contract without a migration.
6. **Prove before building**: a `luabench` case, a reduced prototype, or a static count (events per second x bytes x recipients). Pick by evidence, not by elegance.
7. **Build in house style** (pack root `SKILL.md`, `dev-flow` verify), one resource at a time, contracts kept.
8. **Measure after** with the same scenario; report gain, visible change, risk, and what still needs an in-game test.

## Technique catalog (AAA to FiveM)

| Family | Engine idea | FiveM translation |
| --- | --- | --- |
| Significance | Unreal Significance Manager: score every object by relevance, give expensive work only to the top N | Score = distance, `IsEntityOnScreen(ent)` or camera dot product (`GetFinalRenderedCamCoord` / `GetFinalRenderedCamRot`), gameplay relevance (target, teammate, quest). Full update for the top N, cheap update for the rest, nothing below a threshold. Recompute scores every 250-500 ms, not every frame |
| Budget allocator | Unreal Animation Budget Allocator: a fixed ms budget per frame, work assigned by significance | One frame loop with a `GetGameTimer`-based budget (1-2 ms) or job count; high-significance jobs first, low ones skip frames (`references/shared-services.md` -> Frame-budget queue) |
| LOD for logic | Model LOD and HLOD, applied to code | Script LOD: update rate by distance band (every frame / every 4th / every 20th / off); far groups become one aggregate (one marker per cluster, one blip per zone) |
| Impostors | Billboards replace far meshes | Far 3D props or text become a blip, a 2D sprite, or nothing; spawn the real prop (`lib.spawn`, local, not networked) only inside the near radius with hysteresis (spawn at 40 m, despawn at 55 m) |
| Interest management | Unreal Replication Graph, net relevancy, dormancy | Send only to interested sessions: viewers set, routing bucket, server-side grid of players, OneSync scope events for small sets; dormant objects send nothing until changed (state bag on change, not on timer) |
| Event-driven | Delegates and tick disabling instead of polling | `RegisterKeyMapping`, `gameEventTriggered`, `AddStateBagChangeHandler` with a key filter, `lib.onCache`, promises; a thread exists only while there is work |
| Tick aggregation | Unreal tick groups and the tick manager | One frame loop per resource running a table of active tasks; one central server loop with per-topic counters; staggered start phases so periodic jobs never align |
| Temporal amortization | Spread work over frames, temporal reprojection | Round-robin sweeps (1/k of the set per tick), time slicing, staggered per-player timers, one timer heap instead of many `SetTimeout` |
| Perceptual tricks | Interpolation, prediction, "fake it where it is not looked at" | Send deadlines not ticks (start time + duration, client counts down); send state at low rate and tween on the client (CSS transition, lerp); optimistic UI with server reconcile; skip work off-screen or behind the camera; reduce precision far away |
| Data-oriented | ECS, struct of arrays, cache-friendly loops | Arrays plus numeric `for`, parallel arrays for hot fields, ids instead of nested objects, `table.wipe`/`table.create` scratch tables, lookup maps built at load |
| Pooling | Object pools instead of spawn and destroy | Reuse props, DUI instances, NUI elements and Lua tables; hide and move instead of delete and create |
| Precompute | Baking lighting, navmesh, build-time tables | Zone polygons to grid cells at load; item catalogs and label maps at load; SQL aggregates kept by write-time counters instead of `COUNT(*)` on request; static NUI payloads pre-encoded |
| Dirty flags and coalescing | Mark dirty, flush once | One flush per tick of everything that changed; replaceable values overwrite in a pending table; batched DB writes (multi-row upsert) |
| Layer substitution | Move work to the cheapest subsystem | Engine natives for spatial tests (`IsPointInAngledArea`, `GetClosestObjectOfType`) over Lua math in hot loops; NUI CSS for animation; SQL for set operations; the shared lib service instead of 30 copies; a separate process only for heavy offline work |
| Native fast path | Direct calls, fewer layers | OAL per resource after `scripts/oal-audit.mjs`; cached state bags and export proxies; backtick hashes |

## Decision matrix

Score each alternative 1-5, then rank by `2 x Gain - Risk - Complexity`, ties broken by Reversibility.

| Option | Family | Gain (who feels it, how much) | Risk (bugs, exploits, contract) | Complexity (files, resources, time) | Visible change | Reversible | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 do nothing | baseline | 0 | 0 | 0 | no | yes | current numbers |

Gain counts every player who pays the cost: per-frame work for all clients beats a rare server path. Evidence is a number or a named source, never "should be faster".

## Output template

```
ปัญหา: <what players feel, scenario card>
ต้นทุนตอนนี้: <numbers and where they came from>
ตัดทิ้งได้: <kill list>
ทางเลือก: <decision matrix, at least 5 rows + baseline>
เลือก: <option> เพราะ <evidence>
แผน: <resources and files, one at a time, contracts kept>
พิสูจน์: <benchmark or capture before and after>
เห็นต่างในเกม: <visible changes or none>
ต้องลองในเกม: <list>
```

## Worked example: 200 bots

Request: a server-side AI loop checks 200 bots against every player every 100 ms.

- Kill list: bots in empty areas think at all; bots out of every player's range keep full AI.
- Alternatives: (1) server grid of players and bots, only bots in occupied cells think; (2) significance tiers: near bots 100 ms, mid 500 ms, far 2 s, none frozen; (3) event-driven aggro from `gameEventTriggered` damage and scope events instead of distance polling; (4) round-robin: 1/10 of bots per tick; (5) layer substitution: let the owning client's game AI drive bots (network ownership), server validates outcomes only; (0) baseline.
- Scoring: (1)+(2)+(4) together cut work by about the empty-area share and spread the rest; (5) has the biggest gain but moves trust to clients for movement, acceptable only for cosmetic behaviour, never for rewards or damage.
- Proof: count checks per second before (200 x players x 10) and after, plus a server `profiler record` during a full lobby.

## Guard rails

- The server keeps every decision that matters (rewards, money, damage, cooldowns, routing); perf never moves authority to the client.
- Perceptual tricks change what players see; report them.
- No redesign when the measured cost is already negligible (an idle resource under 0.02 ms, a path that runs a few times an hour): say so and stop.
- One owner per shared system; architecture changes that touch several resources go one resource at a time with contracts kept and a migration note.
