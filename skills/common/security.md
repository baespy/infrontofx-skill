# Security

Every client is hostile. A mod menu can call any `RegisterNetEvent`, any `lib.callback`, any NUI callback, with any arguments, at any rate. The server is the only authority.

## Contents

- Trust Boundary
- Give-Value Hardening
- Give-Value Checklist
- Payload Bounds
- Entity, Coords, And Buckets
- Permissions
- Secrets
- Atomicity And Yields
- Built-in Client Events
- Logging
- Third-party Resources

## Trust Boundary

| Untrusted (validate) | Trusted (server-held) |
| --- | --- |
| net event / callback args | `source` |
| NUI callback data | `Config` read on the server |
| export args from other resources | ESX player via `RunStaticPlayerMethod` |
| client-sent coords, net IDs, entity handles | server registries (`ServerState.entities`) |
| state bag writes from clients | identifiers from `GetPlayerIdentifierByType(src, "license")` |

- Recipient of any value is `src`. Never accept a target id from the client unless the action is admin and ACE-gated.
- `source` is `0` for server-originated calls and can be `65535` in some paths; reject `src <= 0` in client-only handlers.

## Give-Value Hardening

Applies to buy, sell, craft, harvest, reward, trade, drop, pickup, payout.

Vulnerable:

```lua
RegisterNetEvent(scriptname .. ":SV:buy", function(item, price)
    local src = source
    FC.RemoveMoney(src, "money", price)
    FC.AddItem(src, item, 1)
end)
```

Hardened:

```lua
function TemplateServer:Buy(src, payload)
    if self:IsThrottled(src, "buy", Config.General.throttle_ms.buy) then
        return false
    end
    if type(payload) ~= "table" or type(payload.shopId) ~= "string" or type(payload.item) ~= "string" then
        return false
    end
    local amount = math.floor(tonumber(payload.amount) or 0)
    if amount <= 0 or amount > Config.General.max_amount then
        return false
    end
    local shop = Config.Shops[payload.shopId]
    local item = shop and shop.itemIndex[payload.item]
    if not item then
        return false
    end
    if #(GetEntityCoords(GetPlayerPed(src)) - shop.coords) > Config.General.interact.distance + 3.0 then
        return false
    end
    if not FC.CanPurchase(src, shop, item, amount) then
        return false
    end
    if self.ServerState.inFlight[src] then
        return false
    end
    self.ServerState.inFlight[src] = true
    local cost = item.price * amount
    if not FC.CheckMoney(src, item.account, cost) then
        self.ServerState.inFlight[src] = nil
        return false, Config.Text.not_enough_money
    end
    if not FC.CanCarryItem(src, item.name, amount) then
        self.ServerState.inFlight[src] = nil
        return false, Config.Text.inventory_full
    end
    FC.RemoveMoney(src, item.account, cost)
    FC.AddItem(src, item.name, amount)
    self.ServerState.inFlight[src] = nil
    FC.OnPurchased(src, shop, item, amount, cost)
    return true
end
```

## Give-Value Checklist

1. Identity = `src` only.
2. Item, price, account, limits come from server `Config` / DB, never from the payload.
3. Quantity = positive bounded integer (`math.floor`, reject `<= 0`, NaN, `> max`).
4. Proximity / state check (distance, alive, bucket, job, cooldown).
5. Affordability and carry checks right before the mutation.
6. In-flight lock or single DB transaction around check + mutate.
7. Throttle per source; one-shot rewards stored server-side as claimed.
8. Audit log through `FC.Log`.

## Payload Bounds

- Strings: `type(s) == "string" and #s > 0 and #s <= 64` (or the documented max).
- Numbers: `tonumber`, then `value == value` (NaN check), range check, `math.floor` for counts.
- Tables: check `type`, cap list length (`#list <= 50`), never iterate an unbounded client table.
- Reject unknown enum values: `if not Config.Shops[shopId] then return false end`.

## Entity, Coords, And Buckets

```lua
local entity = NetworkGetEntityFromNetworkId(netId)
if not entity or entity == 0 or not DoesEntityExist(entity) then
    return false
end
if GetEntityRoutingBucket(entity) ~= GetPlayerRoutingBucket(src) then
    return false
end
if #(GetEntityCoords(GetPlayerPed(src)) - GetEntityCoords(entity)) > 5.0 then
    return false
end
```

- Prefer server ids from your own registry (`self.ServerState.entities[id]`) over client net IDs.
- Never trust client-sent coords for rewards; read the ped coords on the server.

## Permissions

- Admin actions: `IsPlayerAceAllowed(src, "1nfx.admin")` on the server.
- Job gates: read job on the server (`FC.GetJob(src)`), never from the payload.
- A UI flag like `isAdmin` means nothing; the server re-checks.

## Secrets

- `set name_webhook "https://..."` in `server.cfg` (not `setr`/`sets`), read with `GetConvar("name_webhook", "")` server-side.
- Never place secrets in shared config, NUI files, or client Lua.

## Atomicity And Yields

- `MySQL.*.await`, `lib.callback.await`, `Wait`, `Citizen.Await` yield. After a yield, re-validate the player (`FC.GetIdentifier(src) == identifier`) before mutating RAM state - source ids are recycled.
- For DB economies use `MySQL.transaction.await` or conditional updates (`UPDATE ... SET money = money - ? WHERE identifier = ? AND money >= ?`).

## Built-in Client Events

`weaponDamageEvent`, `explosionEvent`, `startProjectileEvent`, `ptFxEvent`, `clearPedTasksEvent`, `giveWeaponEvent`, `removeWeaponEvent` are client-originated. Validate or `CancelEvent()` them in anti-cheat resources; never use them as proof of a gameplay action.

## Logging

- Log every value mutation with who, what, amount, and where via `FC.Log`.
- Do not log secrets or full payloads from clients without truncating.

## Third-party Resources

Red flags: obfuscated Lua, `load()` of HTTP responses, `PerformHttpRequest` to unknown hosts, `os.execute`, `io.popen`, large base64 blobs. Do not run leaked resources.

