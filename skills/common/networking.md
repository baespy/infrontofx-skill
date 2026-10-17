# Networking And OneSync

## Sides

- Server: authority, registries, routing buckets, persistence.
- Client: rendering, input, local props, UI.
- Networked entities migrate owners; ownership is not authority.

## Handles Vs Net IDs

- Entity handles are local to one machine. Send net IDs across the network: `NetworkGetNetworkIdFromEntity(entity)` / `NetworkGetEntityFromNetworkId(netId)`.
- Prefer your own stable ids (`entity.id` from DB/registry) for gameplay objects; render them as local props on each client.

## Local Vs Networked Props

| Use local props (`CreateObject(..., false, false, false)`) | Use server-created networked entities |
| --- | --- |
| plants, decorations, markers, previews, attached cosmetics | vehicles, pickups that must collide for everyone, mission peds |
| anything rebuilt from server state | anything whose physics must be shared |

Local props are cheaper (no sync) and cannot be abused as network entities. The server keeps the state; each client renders.

## Server-created Entities

```lua
local entity = CreateObjectNoOffset(model, coords.x, coords.y, coords.z, true, true, false)
while not DoesEntityExist(entity) do
    Wait(0)
end
SetEntityRoutingBucket(entity, bucket)
self.ServerState.spawned[NetworkGetNetworkIdFromEntity(entity)] = { owner = identifier }
```

Delete with `DeleteEntity` on cleanup and drop from the registry.

## Routing Buckets

- Store `bucket` on every server entity and session.
- Filter syncs by bucket: players only receive entities in their bucket.
- On bucket change (`1nfx_dimension`), resend the snapshot for the new bucket.
- Validate `GetPlayerRoutingBucket(src)` against the entity bucket in every interaction.

## Sending To Clients

- One player: `TriggerClientEvent(name, src, ...)`.
- Interested players: iterate `self.ServerState.playerSessions` (players who have the feature loaded / are near).
- Everyone: `-1`, only for rare global events.
- `TriggerLatentClientEvent(name, src, bps, ...)` for big one-off payloads (initial snapshot) so the net thread is not flooded.

## State Bags

- Server writes: `Player(src).state:set("isVip", true, true)`; entity: `Entity(entity).state:set("owner", identifier, true)`.
- Client reads: `LocalPlayer.state.isVip`, `AddStateBagChangeHandler("isVip", nil, fn)`.
- Enable `setr sv_stateBagStrictMode true` so clients cannot write replicated bags.
- Keep values small (flags, ids, short strings).

## Player Sessions

Maintain on the server:

```lua
RegisterNetEvent(scriptname .. ":SV:ready", function()
    local src = source
    NameServer:AddSession(src)
end)

AddEventHandler("playerDropped", function()
    local src = source
    NameServer:RemoveSession(src)
end)
```

Clients fire `:SV:ready` after `ESX.IsPlayerLoaded()` and their own init, so the server never pushes data to a client that is not ready.

## Time

- Server time is authority: send `os.time()` once and keep `serverTimeOffset` on the client (`GetCloudTimeAsInt()` + offset) for countdowns.
- Never trust client time for cooldowns or growth.

