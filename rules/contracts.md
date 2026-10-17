# Inter-Resource Contracts

## Exports

- Call exports directly inside `FC` adapters: `ESX = exports["es_extended"]:getSharedObject()`.
- Do not wrap calls in `GetResourceState` checks. Declare the provider in `dependencies {}` and fix start order in `server.cfg` instead.
- Call exports at use time, not once at load (a cached export reference goes stale when the provider restarts).
- All external exports are reached through `FC` adapters, so a provider swap touches only `config/function/*`.

## Providing Exports

- Global wrapper + `exports("Name", Name)` delegating to the controller.
- Declare in `fxmanifest.lua` `exports {}` (client) / `server_exports {}` (server).
- Validate arguments; return plain data only.
- Treat a published export signature as a contract: add optional trailing params instead of changing order.

## Events Between Resources

- Own events use `scriptname .. ":SV:x"` / `":CL:x"`; names never collide because the resource name is the prefix.
- To react to another resource, listen to its documented event names; do not trigger another resource's `:SV:` events from your server code - call its export.
- Framework events (`esx:playerLoaded`, `esx:setJob`) are listened to, never re-triggered.

## Start Order (`server.cfg`)

```text
ensure oxmysql
ensure ox_lib
ensure es_extended
ensure pNotify
```
