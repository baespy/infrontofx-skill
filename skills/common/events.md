# Events, Callbacks, Exports

## Naming

```lua
scriptname .. ":SV:execute"
scriptname .. ":SV:getShop"
scriptname .. ":CL:syncState"
scriptname .. ":CL:removeEntity"
```

- `:SV:` = handled on server, `:CL:` = handled on client. Action in camelCase.
- Always build from `scriptname` (`local scriptname = GetCurrentResourceName()`); never hardcode the resource name, so a renamed resource keeps working and names never collide.
- Third-party events keep their own names (`pNotify:SendNotification`). Framework events use the `1nfx_core:*` names (`1nfx_core:playerLoaded`, `1nfx_core:setJob`); legacy `esx:*` names still fire locally for old resources but new code listens to `1nfx_core:*`.

## Request / Response - lib.callback

Client:

```lua
local ok, result = lib.callback.await(scriptname .. ":SV:buy", false, {
    shopId = shopId,
    item = itemName,
    amount = amount,
})
```

Server:

```lua
lib.callback.register(scriptname .. ":SV:buy", function(source, payload)
    local src = source
    return TemplateServer:Buy(src, payload)
end)
```

- Callback bodies stay one line: capture `src`, delegate to a module method that returns `success, data`.
- Use `lib.callback.await` inside threads/NUI callbacks; avoid nested callback pyramids.
- Request/response uses `lib.callback`, not a pair of events going back and forth.

## Fire-and-forget Server Events

```lua
RegisterNetEvent(scriptname .. ":SV:setTarget", function(entityId)
    local src = source
    if type(entityId) ~= "number" then
        return
    end
    NameServer:SetTarget(src, entityId)
end)
```

## Server -> Client

```lua
TriggerClientEvent(scriptname .. ":CL:syncState", src, payload)
```

- Target a source or a session set. `-1` only for rare global announcements, and coalesce those into rounds (debounce).
- For many recipients loop `self.ServerState.playerSessions` (players that actually need the data).
- Large snapshots: encode with the dictionary wire (`memory/patterns.md` -> Wire Encoding).

## Validation Order In Every Server Handler

1. `local src = source` (first line, before any yield).
2. Throttle: `if self:IsThrottled(src, "buy", Config.General.throttle_ms.buy) then return false end`.
3. Shape: `type(payload) == "table"`, each field type, string length, numeric range, integer.
4. Lookup in server catalog (`Config.Shops[shopId]`) - reject unknown ids.
5. Player state: alive, distance to the interaction, routing bucket, job/permission.
6. Owner gate: a module method such as `self:CanPurchase(src, ...)` when the owner needs a veto point.
7. In-flight lock -> check balance/inventory -> mutate -> release lock.
8. Respond / notify / log.

Full hardening detail: `skills/common/security.md`.

## Throttle Method

```lua
function NameServer:IsThrottled(src, key, limit)
    local now = GetGameTimer()
    local bucket = self.ServerState.throttle[src]
    if not bucket then
        bucket = {}
        self.ServerState.throttle[src] = bucket
    end
    if now - (bucket[key] or 0) < limit then
        return true
    end
    bucket[key] = now
    return false
end
```

Clear `self.ServerState.throttle[src]` on `playerDropped`.

## Exports

```lua
exports("GetZoneState", function(zoneId)
    return NameServer:GetZoneState(zoneId)
end)
```

- Declare the export inline with `exports("Name", function(...) ... end)` delegating to a module method. Do not leave a global wrapper function behind (`function Name() ... end` followed by `exports("Name", Name)`); convert it to the inline form.
- Several exports can sit together at the bottom of `core/sv_main.lua` / `core/cl_main.lua`.
- Validate export input like a net event; other resources are not trusted to pass correct types.
- Return plain data (no module tables, no functions).
- Never rename an export that other resources or JS call through `exports[scriptname]`.

## Commands

```lua
RegisterCommand(Config.General.commands.save, function(source)
    local src = source
    if src ~= 0 and not IsPlayerAceAllowed(src, "command." .. Config.General.commands.save) then
        return
    end
    NameServer:SaveAll()
end, true)
```

- Restricted (`true`) for admin commands, plus ACE check for player sources.
- Command names come from `Config.General.commands` so owners can rename them.

## Client Key Binds

Use `lib.addKeybind` or `RegisterKeyMapping` + command so players can rebind; read `IsControlJustReleased` only inside `point:nearby()` or an active-state loop.
