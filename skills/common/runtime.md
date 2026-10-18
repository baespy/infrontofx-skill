# CFX Runtime

Read this file for threads, yields, `source`, dependency restarts, and resource lifecycle.

## Threads And Waits

- Every long-running loop must yield. A loop without `Wait` stalls its Lua runtime.
- `Wait(0)` resumes next frame and is reserved for active drawing or control reads. Idle work sleeps or stops.
- Start loops only when needed and give them an explicit state-based exit path.
- Do not yield inside `entityCreating`. Move slow work outside the creation gate.

## Source Lifetime

- `source` is meaningful only inside the current event/callback handler. Capture `local src = source` before a yield.
- A server ID can be recycled after a disconnect. Before a valuable mutation following `Wait`, `MySQL.*.await`, `lib.callback.await`, or another async call, confirm the player still exists and the current identifier matches the identifier captured before the yield.
- Identity comes from runtime `source` and server-side framework state, never from the client payload.

## Dependencies And Exports

- Declare mandatory providers in `fxmanifest.lua`; do not hide load-order races with arbitrary waits.
- An object returned by an export can become stale when its provider restarts. Re-acquire restart-sensitive objects or handle the provider start/stop events.
- Call an export through its runtime proxy when practical. Cache immutable data, not opaque provider state.
- Use `GetResourceState` only for optional integrations. Mandatory dependencies should fail clearly.

## Yield Boundaries

- Avoid yielding between validation and mutation. If a yield is required, keep the per-player in-flight lock and repeat identity, permission, state, and proximity checks afterward.
- Run `MySQL.*.await` inside a coroutine context, not a non-yieldable load path.
- Use connection deferrals for asynchronous checks in `playerConnecting`, and call `done` exactly once.

## Lifecycle

- Initialize from the resource lifecycle or a deliberate player-ready path, not timing guesses.
- On provider restart, clear pending requests and refresh dependent state.
- On `onResourceStop`, release focus and destroy owned entities, blips, points, zones, DUI objects, timers, and subscriptions.
- On `playerDropped`, clear every controller map keyed by `src`.

## Review

- Confirm every loop yields and sleeps when idle.
- Find every yield and inspect the state used after it.
- Find cached export results and decide whether provider restart makes them stale.
- Confirm initialization and cleanup can run exactly once without relying on fixed delays.
