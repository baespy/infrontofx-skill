# Patterns

Proven implementations for high-performance FiveM resources. Copy the shape, keep house style.

## Contents

- Wire Encoding
- KVP Snapshot With Signature
- Owner Name TTL Cache
- Player Sessions And Scoped Sync
- Server Time Offset
- DUI Pool
- Exports Wrapper
- Gated Actions
- World-anchored prompt without per-frame NUI (2026-11-14)
- Skip NUI resend when data is unchanged (2026-11-14)
- Sorted Texture Override Catalog Slices (2026-11-15)

## Wire Encoding

Large snapshots repeat the same keys thousands of times. Replace string keys with negative indexes plus a key dictionary; decode on the client. Falls back to plain events when encoding is not smaller.

- Use when: snapshot of 100+ entities with identical shape.

```lua
ResourceWire = {}

function ResourceWire:Encode(value)
    local keys, indexes = {}, {}
    local function encode(node)
        if type(node) ~= "table" or getmetatable(node) then
            return node
        end
        local result = {}
        for key, child in pairs(node) do
            local encodedKey = key
            if type(key) == "string" then
                local index = indexes[key]
                if not index then
                    index = #keys + 1
                    keys[index], indexes[key] = key, index
                end
                encodedKey = -index
            end
            result[encodedKey] = encode(child)
        end
        return result
    end
    return encode(value), keys
end
```

Server sends `scriptname .. ":wireSnapshot"` with `(event, encoded, keys)`; client decodes and re-fires the original event locally, accepting only events prefixed with `scriptname .. ":"`.

## KVP Snapshot With Signature

Fast restart without a full table scan.

1. On change, encode all entities to JSON and `SetResourceKvp(KVP_SNAPSHOT, encoded)` only if the string changed.
2. Store a signature `count:stateSum:maxTimestamp` when every entity is clean, otherwise `"dirty"`.
3. On start: if signature is `"dirty"`, trust the snapshot. Otherwise compare against `SELECT COUNT(*), SUM(state), MAX(timestamp)`; equal -> load snapshot, different -> full SELECT.

## Owner Name TTL Cache

```lua
function NameServer:GetOwnerName(identifier)
    local cache = self.ServerState.ownerNameCache
    local now, cached = GetGameTimer(), cache[identifier]
    if cached and now < cached.expires then
        return cached.name
    end
    local name = self:ResolveOwnerName(identifier)
    cache[identifier] = { name = name, expires = now + 30000 }
    return name
end
```

Persist last known names in KVP so offline owners still show a name.

## Player Sessions And Scoped Sync

- `ServerState.playerSessions[src] = { identifier, bucket }` created on `:SV:ready`, removed on drop.
- All pushes iterate sessions (and filter by bucket) instead of `-1`.

## Server Time Offset

Server sends `os.time()` with the snapshot; client stores `serverTimeOffset = serverTime - GetCloudTimeAsInt()` and computes countdowns locally with `GetCloudTimeAsInt() + offset`.

## DUI Pool

See `skills/ui/dui.md`.

## Exports Wrapper

```lua
exports("GetZoneState", function(zoneId)
    return NameServer:GetZoneState(zoneId)
end)
```

An export declared with `exports("Name", function(...) ... end)` needs no global function and no manifest entry.

## Gated Actions

Owner-customizable decisions are methods of the server module, written directly in `core/`; the action asks them before and after it runs:

```lua
function NameServer:Execute(src, entity)
    if not self:CanExecute(src, entity) then
        return false
    end
    local rewards = self:RollRewards(entity)
    self:OnExecuted(src, entity, rewards)
    return true
end
```

Keep the owner-tunable values in `Config`; the methods hold the logic.

## World-anchored prompt without per-frame NUI (2026-11-14)

`1nfx_textuihologram` draws its prompt from one shared DUI (`html/index.html`, 1024x128, created on first use, removed after 60 s idle) with `SetDrawOrigin` + `DrawSprite` every frame. The DUI gets a message only when text/key changes (`set`) or when a hold starts/ends (`hold` with `elapsed`/`duration`, `release`); the ring animates in JS. Readiness comes from NUI callback `duiReady` (page posts to `https://<resource>/duiReady`, resource name passed in the query string) with a 2 s fallback. The old `1nfx_statushud` hub module for the hologram was removed. Use this pattern for any marker that follows a world position instead of sending screen X/Y to NUI each frame.

## Skip NUI resend when data is unchanged (2026-11-14)

`1nfx_allmenu` `AllMenu:ReplaceData(key, value)` compares `json.encode` of old/new before pushing a fetched section (events, gangsList, cooldowns, gangStory, playtimeLeaderboard). Only use it for sections that every other writer pushes or marks dirty; `MyGangData` is excluded because `ResolveCurrentPlayerGang` writes it silently.

## Sorted Texture Override Catalog Slices (2026-11-15)

- Date: 2026-11-15
- Game build: 3095
- Symptom: Streaming texture overrides flickered across LOD transitions when 3D drawable meshes and their `+hi`/`+hidr` dictionaries landed in different scanner slices, and native call ring-buffer tracing wasted frame time when left enabled in production.
- Cause: Grouping drawables separately from texture dictionaries placed paired base and high-detail entries hundreds of indices apart, and native call tracing defaulted on.
- Fix: Sort compiled catalog entries by target source name during startup catalog compilation so paired drawables and `+hi`/`+hidr` dictionaries sit in the same scan slice, free the raw config table (`Config.<Catalog> = nil`) once Structure-of-Arrays tables are populated, and default native call tracing to `false`.
