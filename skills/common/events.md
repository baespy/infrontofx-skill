# Events, Callbacks, Exports

## Naming

```lua
scriptname .. ":SV:collect"
scriptname .. ":SV:getShop"
scriptname .. ":CL:syncState"
scriptname .. ":CL:removeEntity"
```

- `:SV:` = handled on server, `:CL:` = handled on client. Action in camelCase.
- Always build from `scriptname`; never hardcode the resource name, so a renamed resource keeps working and names never collide.
- Third-party events keep their own names (`pNotify:SendNotification`, `esx:playerLoaded`).

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

- Callback bodies stay one line: capture `src`, delegate to a controller method that returns `success, data`.
- Use `lib.callback.await` inside threads/NUI callbacks; avoid nested callback pyramids.

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

- Target a source or a session set. `-1` only for rare global announcements.
- For many recipients loop `self.ServerState.playerSessions` (players that actually need the data).
- Large snapshots: encode with the dictionary wire (`memory/patterns.md` -> Wire Encoding).

## Validation Order In Every Server Handler

1. `local src = source` (first line, before any yield).
2. Throttle: `if self:IsThrottled(src, "buy", Config.General.throttle_ms.buy) then return false end`.
3. Shape: `type(payload) == "table"`, each field type, string length, numeric range, integer.
4. Lookup in server catalog (`Config.Shops[shopId]`) - reject unknown ids.
5. Player state: alive, distance to the interaction, routing bucket, job/permission.
6. Hook: `FC.CanXxx(src, ...)`.
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
function GetPlantCount(identifier)
    return GrowthGardenServer:GetPlantCount(identifier)
end
exports("GetPlantCount", GetPlantCount)
```

- Global wrapper with the same name, delegating to the controller. Keep wrappers in `core/sv_exports.lua` / `core/cl_exports.lua` when there are several.
- List them in `fxmanifest.lua` (`server_exports {}` / `exports {}`).
- Validate export input like a net event; other resources are not trusted to pass correct types.
- Return plain data (no controller tables, no functions).

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

