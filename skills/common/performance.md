# Performance

Optimize measured work, not code appearance. A skill update does not speed up running resources; a resource becomes faster only after its hot paths are changed and verified under the same scenario.

## Priority

1. Remove blocking or non-yielding work.
2. Stop idle per-frame work.
3. Reduce full scans, serialization, database round trips, and network fan-out.
4. Bound queues and concurrent work so bursts cannot grow without limit.
5. Reduce allocations and localize globals only inside confirmed hot paths.

Do not claim a performance improvement without before/after evidence from the same player count, location, feature state, and capture duration.

## Threads And Waits

| State | Behavior |
| --- | --- |
| inactive | no thread, event-driven, or `Wait(1000+)` |
| coarse maintenance | one scheduler with a long configurable interval |
| nearby | point/zone callbacks or `Wait(100-500)` |
| drawing or reading controls | `Wait(0)` only while active |

- Every loop yields on every path.
- Do not start a thread per event, log entry, entity, or player when one scheduler or queue can own the work.
- Do not use arbitrary startup waits to solve dependency order.
- Spread large maintenance work across ticks with a batch size or time budget.
- Use generation/version fields to make delayed callbacks ignore stale state when the runtime has no cancellation handle.

## Spatial And Entity Work

- Use `lib.points` or `lib.zones` instead of scanning every configured location.
- Keep `point:nearby()` limited to the native calls required for the current frame.
- Render decorative, preview, attached, and reconstructible props locally. Network only entities whose shared physics or ownership matters.
- For large local worlds, index entries into grid cells and scan nearby cells instead of the full dataset.
- Use a larger retain distance than spawn distance to prevent boundary churn.
- Never add global `GetGamePool` sweeps as a generic optimization. Pool scans and unregistering entities can create cost, ownership bugs, and incompatibility; use them only for a measured, resource-owned problem.

## Caches And Indexes

- Prefer `cache.ped`, `cache.coords`, `cache.vehicle`, and `lib.onCache` over repeated player natives.
- Build maps by stable id during config normalization or initialization.
- Cache reads, not authority. Invalidate on mutation, player drop, provider restart, and resource stop.
- Give remote/profile lookups a bounded TTL. Do not use a cache to hide a missing SQL index.
- Do not retain `xPlayer`, entity handles, or opaque export results across yields or provider restarts.

## Allocations And Serialization

- Do not build tables, concatenate strings, call `json.encode`, or format unchanged text every frame.
- Reuse stable payloads and recompute only the fields that changed.
- Compute hashes/digests only when cheaper than encoding or sending the payload they replace.
- Avoid copying large tables between controller layers. Send ids and narrow DTOs.
- Move measured CPU-heavy browser work such as image/video encoding to a Web Worker; do not add workers to ordinary menus.

## Network And State

- Send an initial snapshot once, then narrow create/update/remove deltas.
- Maintain interested sessions by bucket/feature/range instead of broadcasting frequent updates.
- Use latent events for multi-kilobyte transfers. Set a deliberate per-target bandwidth and avoid `-1` because total bandwidth multiplies by player count.
- Keep state bag keys granular. Reading a nested state value deserializes the bag, and mutating a nested table does not replicate unless the top-level key is set again.
- Coalesce replaceable updates such as position, progress, or balance so only the newest unsent value remains.

## NUI And DUI

- `SendNUIMessage` only on state change. Batch high-frequency bridge traffic once per frame or at a feature-appropriate interval.
- Bound pre-ready and request queues. Coalesce replaceable actions instead of allowing an unlimited backlog.
- Stop timers, animation frames, media, observers, and expensive renders while hidden.
- Pool DUI instances and reuse runtime textures. Destroy them on stop.
- Use CSS transitions for ordinary motion. Profile canvas/WebGL/filters in Chromium devtools before keeping them.

## Database

- Keep active gameplay state in controller memory and persist dirty rows in bounded batches.
- Never run one awaited query per row in a loop. Fetch/bulk-write once or use one transaction containing the batch.
- Select only required columns. Paginate large histories with indexed ids/timestamps rather than loading all rows.
- Use prepared statements for repeated hot queries and duplicate-key upserts instead of select-then-insert races.
- Investigate slow-query warnings and query plans before adding a cache.
- Do not enable verbose SQL/debug logging in production.

## HTTP, Webhooks, And External Streams

- Keep external I/O off the gameplay mutation path unless its result is required for authority.
- Use one bounded queue per integration, a concurrency cap, and a defined overflow policy.
- Batch non-critical logs. Do not create one thread or unbounded request per event.
- Retry only transient failures with exponential backoff, jitter, and a maximum delay/attempt count.
- Apply payload, client, and buffered-byte limits. One stalled consumer must not grow server memory indefinitely.
- Close timers, sockets, workers, and pending ownership records when either the consumer or provider resource stops.

## Measuring

1. Record the exact reproduction: player count, location, action, duration, and whether UI/entities are active.
2. Capture a baseline with `resmon true` and `profiler record 500`; use `profiler status`, then `profiler view` or `profiler saveJSON <file>`.
3. Inspect spikes, not only averages. Find the resource, thread, file, and line owning the work.
4. For NUI, use `nui_devtools` or the Chromium remote debugger and inspect Performance, Memory, Network, and listener/timer growth.
5. For database/network issues, correlate slow queries, payload sizes, recipient counts, and event frequency with the hitch timestamp.
6. Change one cause, repeat the same capture, and report the before/after observation.

Fixed universal millisecond budgets are misleading across hardware and scenarios. Treat consistent idle work, growing memory, burst spikes, and server hitch warnings as defects; use measurements to set a budget for the specific resource.
