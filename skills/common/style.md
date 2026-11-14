# Style

House style for every `infrontofx` Lua file. Match it exactly to keep all resources consistent and readable.

## Core Principles

- Direct, minimal, readable code. One clear flow per method.
- OOP only: one module table per side; every behaviour is a method (`function Module:Name()`).
- No comments anywhere in code (Lua, JS, CSS, HTML).
- No file-level constants and no top-level `local function`.
- Performance is a requirement, not cleanup.
- Do not over-engineer: never write speculative fallback chains, unnecessary string formatting, unused helpers, or extra files.
- Add a method only when it carries real logic (pcall, nil check, `GetResourceState` check, calculation) and is used in more than one place. A one-line wrapper around an export or event is not written; write the real call at the use site.
- No framework layers, dispatchers, or class hierarchies inside a resource.

## File Header

```lua
local scriptname = GetCurrentResourceName()
```

- Framework access is the global `Core`, provided by `shared_script "@1nfx_core/imports.lua"`. Do not write `local ESX = exports["es_extended"]:getSharedObject()`.
- Top-of-file `local` is allowed only for: `scriptname`, the module table, and (anticheat resources only) stored native references.
- Globals allowed: `Config`, and one module global when the module spans several files.
- Do not localize hot globals (`local tonumber = tonumber`, `local math_floor = math.floor`) at file level. Pull a value into a local inside the method that needs it.

## Module Naming

| Resource | Client table | Server table |
| --- | --- | --- |
| `shop` | `Shop` | `ShopServer` |
| `airdrop` | `Airdrop` | `AirdropServer` |
| `serverlogs` | `ServerLogs` | `ServerLogsServer` |
| `defender` | `Defender` | `DefenderServer` |

- Strip any author prefix, split on `_` / `-`, PascalCase each word.
- Never prepend author tags or use generic names like `Main`.

## Module Shape

```lua
local Shop = {
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
- Other top-level fields = runtime registries (points, blips, pools, caches, indexes) and shared data tables (`Module.Kinds = { ... }`), never file-level `local` tables.
- Server tables use `ServerState` only (`playerSessions`, `throttle`, `inFlight`, `entities`).
- The module is `local` when it lives in one file; a module split over several files is the one allowed module global.
- Event handlers and threads only call methods.
- A `local function` nested inside a method (closure) is allowed; a top-level `local function` is not.
- Do not declare a `local function` before the module table and then assign the table later: the module table goes at the very top, and the assignment would overwrite methods already added.

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

Produced code contains no `--` or `--[[ ]]` in Lua, no `//` or `/* */` in JS or CSS, and no `<!-- -->` in HTML. If a block needs a comment, rename variables or extract a well-named method instead. Documentation lives in this skill and the resource README, not in code.

### Functions

- Methods: `function Name:Method(arg)`.
- Exports: `exports("Name", function(...) return Module:Method(...) end)` (see `skills/common/events.md`).
- Integration calls (notify, inventory, money, text UI, progress, logs) are methods of the module: `function Module:Notify(label, notifyType)` (see `skills/common/core-api.md`).
- Resource names are never abbreviated into variables; write `exports["1nfx_processbar"]:...` in full at the call site.

### Directness And Guards

- Write direct code without defensive clutter:
  - Read `Config.General.x` and `Config.Text.x` directly at the use site; never write `(Config.General and Config.General.x) or default`, and do not alias `Config` into file-level locals.
  - Use `cache.ped` and `cache.coords` directly; never write `cache.ped or PlayerPedId()`.
  - Pass raw numbers and item labels / `Config` labels directly to NUI instead of formatting strings in Lua with `string.format("WORLD %02d", ...)`, `:upper():gsub("_", " ")`, or multi-branch time string builders.
- Guard data where trust changes: net events, callbacks, commands, exports, NUI input, database decode, and native/entity handles.
- Guard framework/native results only when failure is expected and the next operation would be unsafe.
- Do not repeat a validation already guaranteed by the caller or `Config`.
- Do not add empty-string checks to `Notify`, text UI, or logging methods when the caller owns the value.
- Keep guard clauses inline in the method that owns the boundary. Do not create generic `ValidatePlayer`, `SafeCall`, or `EnsureValue` wrappers.
- Remove multi-layer fallbacks that are not needed; keep the one path the server's framework actually provides.

## CfxLua Operators

- `+=`, `-=`, `*=`, `/=`, `|=`, `&=` are allowed in FiveM Lua when clearer; they require `lua54 "yes"` in the manifest, as does `//`.
- Never `++` / `--` increment (does not exist; `--` starts a comment).

## Naming

- Locals camelCase, methods PascalCase (`self:GetFreeDUISlot()`).
- Config keys: snake_case (`render_distance`, `interval_sec`).
- Data keys sent to NUI: camelCase (`ownerName`, `maxAmount`).
- No `UPPER_SNAKE` constants at file level. Write the literal at the use site (`Wait(1000)`, `31086`); data shared by several methods becomes a module field.
- Event names: `scriptname .. ":SV:<name>"` / `scriptname .. ":CL:<name>"`.

## Return Shape

- Server methods used by callbacks return `success, messageOrData`:
  ```lua
  return false, Config.Text.not_enough_money
  return true, { count = count, limit = limit }
  ```
- NUI callbacks respond with `{ ok = boolean, ... }`.
