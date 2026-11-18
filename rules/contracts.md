# Inter-Resource Contracts

## Exports

- Call exports directly at the use site inside `core/` methods, with the full resource name: `exports["1nfx_processbar"]:getIsDoingAction()`. Do not store the resource name in a variable.
- Shared runtime primitives (`lib`, `cache`, `require`, `SetInterval`, `ClearInterval`) come from `shared_script "@1nfx_lib/init.lua"` (replacing external `ox_lib`, `er_lib`, and `cfxlua-require`). The framework is reached through the global `Core` from `shared_script "@1nfx_core/imports.lua"`, not through `exports["es_extended"]`.
- Do not wrap calls in `GetResourceState` checks for mandatory providers. Do not declare `dependencies {}`; fix start order in `server.cfg` instead. `GetResourceState` is for optional integrations only.
- Call exports at use time, not once at load (a cached export reference goes stale when the provider restarts).
- External exports are reached from module methods (`Module:Notify`, `Module:GetMoney`), so a provider swap touches only those methods.

## Providing Exports

- Declare inline: `exports("Name", function(...) return Module:Method(...) end)`; no global wrapper function left behind.
- Declare in `fxmanifest.lua` `exports {}` (client) / `server_exports {}` (server) only when needed by tooling; exports declared in code need no manifest entry.
- Validate arguments; return plain data only.
- Treat a published export signature as a contract: add optional trailing params instead of changing order. Never rename an export, event, `Config` key, NUI payload shape, or DB table/column that other code uses.

## Events Between Resources

- Own events use `scriptname .. ":SV:x"` / `":CL:x"`; names never collide because the resource name is the prefix.
- To react to another resource, listen to its documented event names; do not trigger another resource's `:SV:` events from your server code - call its export.
- Framework events (`1nfx_core:playerLoaded`, `1nfx_core:setJob`) are listened to, never re-triggered. Legacy `esx:*` names still fire locally for old resources.

## Start Order (`server.cfg`)

```text
ensure oxmysql
ensure 1nfx_lib
ensure 1nfx_core
ensure pNotify
```
