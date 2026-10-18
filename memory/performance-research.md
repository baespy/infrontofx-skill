# ESX Performance Research

- Date: 2026-10-18
- Game build: not supplied; source inspection only, no live FXServer benchmark.
- Scope: reusable design decisions from public source and a local client-only sample. No capacity, hitch reduction, or security certification.

## Inventory Lookup And Compatibility

The screenshot's load loop constructs an array containing every registered item, including count zero, and sorts it by label. That is initialization work: O(N) construction plus O(N log N) sorting. It does not establish the implementation or cost of getInventoryItem. Inspect the actual class and active inventory override before changing it.

For an array-scanning getter, N is the number of entries in that player's inventory representation, not necessarily every item registered on the server. If C calls inspect N entries, worst-case lookup work is O(CN). A persistent name index gives expected O(1) lookup and O(N) initialization. It does not remove serialization, hooks, SQL, entity replication, or network costs, and cannot prove support for 1,000 players.

Choose based on the existing contract:

| Option | Use and cost |
| --- | --- |
| Existing array plus internal name index | Usually least disruptive for legacy ESX. Index points to the same item tables; adds O(N) references, avoids duplicate mutable counts. |
| Canonical name map plus array projection | Suitable when all consumers are known. Build ordered arrays only at API/UI boundaries; getInventory still scans/allocates. |
| Sparse owned counts plus shared definitions | Reduces per-player state and transfer size, but requires a compatibility layer for valid unowned items, labels, weight/limits, and UI arrays. |

Build/rebuild indexes on load, inventory replacement, provider reload, and definition refresh. Mutate the canonical entry; do not let an array and map contain independent mutable copies. Do not rebuild the entire index inside each getter. Sorting an array of item references does not require rebuilding a reference index; a numeric-position index does.

Preserve getInventory, minimal persistence output, add/remove/set, carry checks, weight or limit semantics, hooks, and event argument meanings. Distinguish a registered item with count zero from an unknown name. Never put a mutable count on the globally shared ESX.Items definition. A sparse design must still support adding a valid item not previously owned.

Audit direct xPlayer.inventory access, ipairs, #inventory, sorting, exports, imports, and NUI consumers. A name map makes # and ipairs unsuitable. If the active provider supports slots or metadata, name alone is not a unique stack key; use that provider's APIs through FC. Optimize accounts/loadout only when their measured frequency and size justify the change.

Compatibility checks before a future implementation: first acquisition, zero count, unknown item, removal to zero then reacquisition, full capacity/weight, concurrent mutations, restart/reconnect persistence, shared definitions refresh, existing array consumers, and slot/metadata behavior where applicable.

## Public Fork Findings

Inspected jxeqoz/es_extended at commit `840dfb392e641cd9e61e79ad4328a5a42a1794bd`:

- The player constructor converts inventory/accounts/loadout into maps by name.
- getInventoryItem reads the map; getInventory creates an array or a minimal positive-count map.
- Player loading still builds all server item entries. Only positive-count compact entries are put in the client inventory list. This is not a sparse server inventory.
- Account lookup also uses a map. SavePlayers sends bounded prepared parameter batches. Neither proves a capacity claim or atomic multi-player persistence.
- This fork uses item limits; do not copy it over a weight-based server without checking behavior.
- Inventory methods merit separate boundary review: add does not itself enforce carry limits or a positive finite amount; setting an unchanged count can reach remove with zero. Adopt the indexing idea, not the whole implementation without compatibility/security review.

Sources: [constructor](https://github.com/jxeqoz/es_extended/blob/840dfb392e641cd9e61e79ad4328a5a42a1794bd/server/classes/player/init.lua), [inventory](https://github.com/jxeqoz/es_extended/blob/840dfb392e641cd9e61e79ad4328a5a42a1794bd/server/classes/player/methods/inventory.lua), [load](https://github.com/jxeqoz/es_extended/blob/840dfb392e641cd9e61e79ad4328a5a42a1794bd/server/modules/player/load.lua), [save](https://github.com/jxeqoz/es_extended/blob/840dfb392e641cd9e61e79ad4328a5a42a1794bd/server/functions/services/players/init.lua).

## Local Client Evidence

Read-only sample root: C:/Users/Administrator/Downloads/plus/plus/89.38.101.136.

- es_extended/client/main.lua:59 receives xPlayer, an unused argument, inventory counts, and inventoryData. Lines 62 onward reconstruct a full array with count defaulting to zero. This shows the expected client contract, not the hidden server representation.
- The same file's add/remove handlers around lines 521/536 still scan the array. An optimized server getter does not remove this client scan.
- nongnut_alljobs/client/main.lua around lines 379-415 builds itemCount/itemLimit/itemLabel once and updates counts from item events. Its completion event at line 351 sends the job index. This supports cached UI reads and a narrow intent payload; server reward validation is unavailable.
- bt_extended/core/client.lua and bt_optimize/client.lua start with FXAP and are not readable Lua. Their names and manifests do not establish optimizer behavior, server logic, or a BT-hosted delivery path. Do not decode protected assets or invent an implementation.
- No server handlers, database plans, hardware profile, or load captures were supplied. Do not infer SQL efficiency or anti-exploit guarantees from these clients.

## Item Catalog Versus Player State

Separate stable public definitions (name, label, icon, display weight) from per-player state (counts, metadata, revisions). Derive dynamic usable flags and changing limits from their actual owner; do not freeze them into an unversioned catalog.

A packaged JSON catalog can avoid repeating definitions in a gameplay join event. It must be declared in the resource packfile and explicitly read/decoded by Lua or NUI; a file does not populate ESX.PlayerData automatically. It still transfers through resource delivery/cache and has a decode/startup cost. Measure cold and warm joins separately.

Generate the catalog from the authoritative registry and version it. Gate inventory readiness until catalog and snapshot match, then reconstruct legacy arrays once if required. On mismatch use a bounded resync/update path; do not silently join stale labels, limits, or definitions to current counts. A client catalog is public presentation data, never authority for rewards, prices, carry checks, or permissions.

The client sample receives definitions in playerLoaded; it does not demonstrate that sending the whole ESX.Items table is required. Keep only consumed public fields and avoid sending definitions on every mutation. CDN/offload is a separate deployment decision that changes delivery origin, not gameplay event frequency or server mutation CPU.

Source: [Cfx resource manifest and packfiles](https://docs.fivem.net/docs/scripting-reference/resource-manifest/).

## Event, Payload, And Log Budgets

Use three distinct counts: gameplay actions, script network events, and audit/log writes. Reducing console output alone does not reduce network traffic. A callback normally includes a request and a response; local TriggerEvent does not cross the network. State bags also consume replication bandwidth and must not become a large inventory transport by default.

Estimate logical egress as events/second x encoded payload bytes x recipient count; record transport overhead separately. A smaller payload broadcast to every player can cost more than a larger targeted message. Count request and response traffic, fan-out, and burst peaks.

- Send server-approved state to its owner or current interested sessions. Bucket/range membership must be implemented explicitly for script events.
- Send a snapshot on readiness, then narrow changed records with revision/session identity. Resync after a gap, restart, or catalog mismatch without allowing request storms.
- Coalesce replaceable state by stable key within a bounded delay/byte budget. Preserve accepted mutations and required audit records; do not drop purchases, rewards, or transfers to reduce event count.
- Preserve whether an ESX event count means the new total or the amount added. Never accumulate new totals as deltas.
- One validated completion request can cause multiple server-calculated rewards, followed by a bounded result/update. Do not make the client send progress ticks or reward amounts.
- Batch only after measuring. A giant batch creates a serialization spike and stale UI; define maximum entries, bytes, delay, in-flight count, and overflow behavior.
- Latent events pace large occasional snapshots; they do not compress them or reduce total bytes. Set per-target bandwidth and a completion/readiness policy.
- Queue external logs with bounded concurrency, bytes, retries, and a deliberate overflow policy. Separate verbose diagnostics from required economy/security audit records; durable records cannot silently disappear.

Sources: [Cfx events and latent bandwidth](https://docs.fivem.net/docs/scripting-manual/working-with-events/triggering-events/), [state bag serialization limits](https://docs.fivem.net/docs/scripting-manual/networking/state-bags/).

## oxmysql And Persistence Decisions

Latest official release checked on the entry date: v2.14.3, published 2026-10-06. Recheck releases at implementation time; this is a historical finding, not a permanent version requirement.

Use `skills/common/database.md` for the API contract. Optimize query count and query plans before adding caches or changing database drivers. Await is cooperative waiting, not a cure for N queries or a reason to create N threads. Prepare reduces repeated statement work; multiple parameter sets still execute multiple statements and do not imply atomicity.

Keep one persistence owner for each value. Do not write ESX inventory/accounts directly to SQL from an unrelated resource while ESX still owns RAM and autosave. Independent resource state can use dirty revisions, one in-flight save per record, bounded/staggered batches, retry on failure, and fair scheduling. Serialize snapshots across ticks as well as batching SQL; batching only the final queries leaves JSON work concentrated on one tick.

Do not allow older saves to finish after newer ones and overwrite them. A successful callback clears only the revision it saved; failures retain dirty state. Define acceptable data loss for deferred saves. For valuable transfers, deduplicate operation ids and coordinate durable success with the persistence owner instead of relying on eventual autosave.

Sources: [release](https://github.com/overextended/oxmysql/releases/tag/v2.14.3), [prepare API and return types](https://overextended.dev/oxmysql/Functions/prepare), [transaction semantics](https://overextended.dev/oxmysql/Functions/transaction), [affected-row update API](https://overextended.dev/oxmysql/Functions/update).

## Measurement Before Implementation

| Cost | Capture | Decision |
| --- | --- | --- |
| Client script CPU | resmon plus client profiler during idle, nearby, active farm, inventory open | Remove measured per-frame scans/allocations; resmon alone cannot establish server health. |
| Server CPU/hitches | Server profiler during simultaneous completions, joins, saves, disconnects | Locate exact hot functions and burst serialization; do not infer from client captures. |
| Script event traffic | Short neteventlog capture with direction, event, size, frequency; net_statsFile for transport | Compare events/sec, bytes/sec, recipients, latency, and burst peaks separately. |
| Database | Query counts per action/autosave, slow log, EXPLAIN, queue/latency observations | Fix N+1, indexes, oversized results, and write contention before caching. |
| Correctness | Reconnect/restart, duplicate requests, overlapping actions, failed saves | Reject optimizations that desync inventory or duplicate/loss money/items. |

Use the same artifact/build, resource versions, hardware, catalog size, owned-item count, player count, duration, and workload before/after. Report tail spikes and action completion latency, not just average CPU. Keep diagnostic logging identical or measure it separately. Client-only source analysis produces hypotheses and an implementation plan, not measured gains.

Sources: [Cfx profiler](https://docs.fivem.net/docs/scripting-manual/debugging/using-profiler/), [Cfx console commands](https://docs.fivem.net/docs/client-manual/console-commands/).
