# Style

House style for every `infrontofx` Lua file. Match it exactly to keep all resources consistent and readable.

## Core Principles

- Direct, readable code. One clear flow per method.
- One controller table per side; every behaviour is a method on it.
- Performance is a requirement, not cleanup.
- Add a helper only when it removes real duplication (used 3+ times) or hides unsafe complexity.
- No framework layers, dispatchers, or class hierarchies inside a resource.

## File Header

```lua
ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()
```

Heavy server or client files may localize hot globals right after the header:

```lua
local tonumber = tonumber
local type = type
local math_floor = math.floor
local GetGameTimer = GetGameTimer
```

## Controller Naming

| Resource | Client table | Server table |
| --- | --- | --- |
| `shop` | `Shop` | `ShopServer` |
| `airdrop` | `Airdrop` | `AirdropServer` |
| `serverlogs` | `ServerLogs` | `ServerLogsServer` |
| `defender` | `Defender` | `DefenderServer` |

- Strip any author prefix, split on `_` / `-`, PascalCase each word.
- Never prepend author tags or use generic names like `Main`.

## Controller Shape

```lua
Shop = {
    ServerState = {
        entities = {},
        serverTimeOffset = 0,
    },
    PlayerState = {
        busy = false,
        targetEntity = nil,
    },
    Points = {},
    Blips = {},
}

function Shop:GetServerTime()
    return GetCloudTimeAsInt() + self.ServerState.serverTimeOffset
end
```

- `ServerState` = data that came from (or mirrors) the server.
- `PlayerState` = local player/session state (busy flags, UI open, target).
- Other top-level fields = runtime registries (points, blips, pools, caches, indexes).
- Server tables use `ServerState` only (`playerSessions`, `throttle`, `inFlight`, `entities`).

## Formatting

- 4 spaces, no tabs.
- Double quotes for Lua strings.
- Spaces after commas and around operators.
- Trailing comma on the last row of multi-line tables.
- `("%s:%d"):format(a, b)` for string building in hot paths instead of long `..` chains.

### Multi-line `if` (mandatory)

```lua
if not entity or not entity.owner then
    return false
end

if count <= 0 then
    return
elseif count > Config.General.max_amount then
    count = Config.General.max_amount
end
```

Never:

```lua
if not entity then return end
```

Long conditions break after `if` with each clause on its own line:

```lua
if
    self.PlayerState.targetEntity
    and self.PlayerState.targetEntity.dui
    and self.PlayerState.targetEntity.uiShow
then
    self:CloseUI(self.PlayerState.targetEntity)
end
```

### No comments

Produced Lua contains no `--` or `--[[ ]]`. If a block needs a comment, rename variables or extract a well-named method instead. Documentation lives in this skill and the resource README, not in code.

### Functions

- Methods: `function Name:Method(arg)`.
- `FC` entries: `FC.Name = function(arg) ... end`.
- Exports: global wrapper + `exports("Name", Name)` (see `skills/common/events.md`).
- Local helpers only for pure, file-private math or encoding in `sh_config.lua`.

## CfxLua Operators

- `+=`, `-=`, `*=`, `/=`, `|=`, `&=` are allowed in FiveM Lua when clearer.
- Never `++` / `--` increment (does not exist; `--` starts a comment).

## Naming

- Locals and methods: camelCase locals, PascalCase methods (`self:GetFreeDUISlot()`).
- Config keys: snake_case (`render_distance`, `interval_sec`).
- Data keys sent to NUI: camelCase (`ownerName`, `maxAmount`).
- Constants: `UPPER_SNAKE` locals (`local KVP_SNAPSHOT = "resource:entities_snapshot:v1"`).

## Return Shape

- Server methods used by callbacks return `success, messageOrData`:
  ```lua
  return false, Config.Text.not_enough_money
  return true, { count = count, limit = limit }
  ```
- NUI callbacks respond with `{ ok = boolean, ... }`.
