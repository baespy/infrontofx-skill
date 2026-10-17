# Architecture

Standard layout and load order for an `infrontofx` FiveM resource.

## Layout

```text
<resource_name>/
├── fxmanifest.lua
├── install.sql                       (only when the resource owns tables)
├── config/
│   ├── config.lua                    Config = {}, Config.General, Config.Text
│   ├── config.<domain>.lua           Config.<Domain> datasets (shops, zones, items)
│   ├── config.server.lua             server-only values (rewards, drop rates) - optional
│   └── function/
│       ├── config.function.client.lua   FC client adapters + hooks
│       └── config.function.server.lua   FC server adapters + hooks
├── core/
│   ├── sh_config.lua                 validate + normalize Config once
│   ├── cl_main.lua                   client controller table + methods
│   ├── cl_<feature>.lua              more client methods on the same table
│   ├── sv_main.lua                   server controller table + methods
│   ├── sv_db.lua                     persistence methods on the same table
│   └── sv_exports.lua / cl_exports.lua  export wrappers
├── html/                             NUI (ui_page)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── dui/                              DUI pages rendered on world entities (optional)
```

- `core/` holds logic, `config/` holds what server owners edit. Owners should never need to open `core/`.
- The file that creates the controller table loads first on its side (`cl_main.lua` / `sv_main.lua` or `sv_db.lua`).

## Manifest

```lua
fx_version "cerulean"
game "gta5"
lua54 "yes"
use_experimental_fxv2_oal "yes"

name "infrontofx_template"
author "infrontofx"
version "1.0.0"

ui_page "html/index.html"

shared_scripts {
    "@ox_lib/init.lua",
    "config/config.lua",
    "config/config.shop.lua",
    "core/sh_config.lua",
}

client_scripts {
    "config/function/config.function.client.lua",
    "core/cl_main.lua",
}

server_scripts {
    "@oxmysql/lib/MySQL.lua",
    "config/config.server.lua",
    "config/function/config.function.server.lua",
    "core/sv_main.lua",
}

files {
    "html/**",
}

dependencies {
    "ox_lib",
    "es_extended",
}
```

Load order rules:

1. `@ox_lib/init.lua` first in shared.
2. Config files before `core/sh_config.lua`.
3. `config/function/*` before `core/*` on each side (core calls `FC` at load).
4. Server-only config (`config.server.lua`) in `server_scripts` so clients never download it.
5. Declare exports in `exports {}` / `server_exports {}` when other resources consume them.
6. `use_experimental_fxv2_oal "yes"` for the faster native call path.

## Responsibilities

| Layer | Owns |
| --- | --- |
| `config/*.lua` | values server owners tune |
| `config/function/*` (`FC`) | framework/inventory/notify/textui/progress/log calls + gameplay hooks |
| `core/sh_*` | validation, normalization, shared pure helpers |
| `core/cl_*` | input, points/zones, rendering, local props, NUI/DUI |
| `core/sv_*` | authority: validation, economy, persistence, sync |
| `html/` | display only, sends intent |

## Lifecycle Skeleton

Client:

```lua
CreateThread(function()
    while not ESX.IsPlayerLoaded() do
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

- The controller table is global inside the resource environment, so `sv_db.lua` and `sv_main.lua` share `NameServer` without exports.
- Globals are per resource in FXServer; they do not leak to other resources. Other resources use exports or events only (`rules/contracts.md`).
