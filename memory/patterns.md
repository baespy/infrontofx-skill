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
- Hook-gated Actions

## Wire Encoding

Large snapshots repeat the same keys thousands of times. Replace string keys with negative indexes plus a key dictionary; decode on the client. Falls back to plain events when encoding is not smaller.

- Use when: snapshot of 100+ entities with identical shape.

```lua
ResourceWire = {}

function ResourceWire.Encode(value)
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
function GetZoneState(zoneId)
    return NameServer:GetZoneState(zoneId)
end
exports("GetZoneState", GetZoneState)
```

## Hook-gated Actions

Core asks `FC` before and after every owner-customizable action:

```lua
if not FC.CanExecute(src, entity) then
    return false
end
local rewards = self:RollRewards(entity)
FC.OnExecuted(src, entity, rewards)
```
