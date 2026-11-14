# Architecture

Standard layout and load order for an `infrontofx` FiveM resource.

## Layout

```text
<resource_name>/
├── fxmanifest.lua
├── install.sql                       (only when the resource owns tables)
├── config/
│   ├── config.lua                    Config = {}, Config.General, Config.Text
│   ├── config.<domain>.lua           Config.<Domain> datasets (optional)
│   └── config.server.lua             server-only values (rewards, drop rates, webhooks) - optional
├── core/
│   ├── cl_main.lua                   client module table + methods
│   ├── cl_<domain>.lua               independent client subsystem on the same table (multi-system resources only)
│   ├── sv_main.lua                   server module table + methods (including DB, timers, exports)
│   └── sv_<domain>.lua               independent server subsystem on the same table (multi-system resources only)
├── html/                             NUI (ui_page)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── dui/                              DUI pages rendered on world entities (optional)
```

- `core/` holds logic, `config/` holds what server owners edit. Owners should never need to open `core/`.
- There is no `config/function/` folder and no `FC` table. Integration code (notify, inventory, money, text UI, progress, logs) is written directly inside `core/` as methods of the module table (`Module:Notify(...)`, `Module:GetMoney(...)`). See `skills/common/core-api.md`.
- Do not create `core/sh_config.lua` or `core/sh_wire.lua`. Read `Config` directly from `config/*.lua`.
- Keep all client logic in `core/cl_main.lua` and all server logic in `core/sv_main.lua` for single-system resources. Do not fragment a single feature into tiny files (`cl_nui.lua`, `cl_zone.lua`, `sv_db.lua`, `sv_exports.lua`, `sv_eventschedule.lua`).
- Split `core/cl_<domain>.lua` and `core/sv_<domain>.lua` only when a resource genuinely bundles multiple independent subsystems (e.g., an all-in-one menu with gangs, mailbox, twitter, and online rewards). Keep shared lifecycle, DB methods, and exports in `cl_main.lua` / `sv_main.lua`.
- The file that creates the module table loads first on its side (`cl_main.lua` / `sv_main.lua`).

## Manifest

```lua
fx_version "cerulean"
game "gta5"
lua54 "yes"

ui_page "html/index.html"

shared_scripts {
    "@ox_lib/init.lua",
    "@1nfx_core/imports.lua",
    "config/config.lua",
    "config/config.shop.lua",
}

client_scripts {
    "core/cl_main.lua",
}

server_scripts {
    "@oxmysql/lib/MySQL.lua",
    "config/config.server.lua",
    "core/sv_main.lua",
}

files {
    "html/**",
}

dependencies {
    "ox_lib",
    "1nfx_core",
}
```

Load order rules:

1. `@ox_lib/init.lua` first in shared, then `@1nfx_core/imports.lua` (provides the global `Core`).
2. `config/config.lua` before any `config/config.<domain>.lua`.
3. Config files before `core/*` on each side.
4. Server-only config (`config.server.lua`) in `server_scripts` so clients never download it.
5. Exports declared with `exports("Name", function(...) ... end)` in code need no manifest entry; list in `exports {}` / `server_exports {}` only when other tooling needs them.
6. `lua54 "yes"` is set in the manifest (required for `+=` and `//`).
7. Do not enable experimental OAL by default. Add it only after auditing native signatures and vector arguments for that resource.

## Responsibilities

| Layer | Owns |
| --- | --- |
| `config/*.lua` | values server owners tune |
| `core/cl_*` | input, points/zones, rendering, local props, NUI/DUI, notify/text UI/progress calls |
| `core/sv_*` | authority: validation, economy, persistence, sync, inventory/money calls, logs |
| `html/` | display only, sends intent |

## Lifecycle Skeleton

Client:

```lua
CreateThread(function()
    while not Core.IsPlayerLoaded() do
        Wait(500)
    end
    Name:Init()
end)

AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    Name:Destroy()
end)
```

Server:

```lua
CreateThread(function()
    NameServer:Init()
end)

AddEventHandler("playerDropped", function()
    local src = source
    NameServer:ClearPlayer(src)
end)

AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    NameServer:SaveAll()
end)
```

## Cross-file Sharing

- A resource whose module spans several files exposes one module global (`NameServer`), so `sv_main.lua` and any `sv_<domain>.lua` subsystem files share it without exports. A single-file module stays `local`.
- Globals are per resource in FXServer; they do not leak to other resources. Other resources use exports or events only (`rules/contracts.md`).
- The only globals a resource owns are `Config` and, for multi-file modules, that one module global.
