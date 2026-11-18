# Config

How `infrontofx` resources expose tunable values.

## config/config.lua

```lua
Config = {}

Config.General = {
    debug = false,
    interact = { key = 38, distance = 2.0 },
    streaming = { distance = 250.0, interval = 5000 },
    limits = { normal = 5, vip = 10 },
    vip = { method = "item", item = "vip_card", statebag = "isVip" },
    save = { enabled = true, interval_sec = 600, on_player_dropped = true },
    commands = { open = "shop_open" },
}

Config.Text = {
    not_enough_money = "Not enough money",
    inventory_full = "Inventory is full",
    purchased = "Purchased %s x%d",
}
```

Rules:

- Declare `Config = {}` once in `config/config.lua` and assign each sub-table directly (`Config.General = { ... }`, `Config.Text = { ... }`, `Config.Shops = { ... }`). Never write `Config.X = Config.X or {}`, `if not Config.X then Config.X = {} end`, or default-merging loops inside config files. List config files explicitly in `fxmanifest.lua` in exact load order.
- `Config.General` groups by feature with snake_case keys. Short inline tables for small groups.
- Every player-facing string lives in `Config.Text` so owners can translate without touching core.
- Durations name their unit (`interval_ms`, `cooldown_sec`, `lifetime_hours`). Do not create loose global time constants.
- Mode switches are strings with documented values (`method = "item" | "statebag"`), not boolean pairs.
- Read `Config.General.*` and `Config.Text.*` directly in `core/*` at the use site. Never alias them into file-level locals, never wrap config reads in `(Config.General and Config.General.x) or default` fallback chains, and do not create a `core/sh_config.lua` normalization file. In a hot loop, pull the value into a local inside that method.

## Split Config Files

Large or independent datasets go in `config/config.<domain>.lua`:

```lua
Config.Shops = {
    central_market = {
        label = "Central Market",
        coords = vector3(25.7, -1347.3, 29.5),
        items = {
            { name = "bread", price = 25, account = "money" },
            { name = "water", price = 15, account = "money" },
        },
    },
}
```

- Key datasets by their natural id (`central_market`, `main_garage`) so lookups are O(1).
- Keep a dataset in one file; do not spread one table across files.

## What Must Not Be In Shared Config

Shared config is downloaded by every client. Never put these in `shared_scripts` files (or in `files` globs such as `config/**`):

- Webhook URLs, API keys, tokens, DB credentials -> a server-only config file (`config/config.server.lua`, listed in `server_scripts` only). Secrets stay in server-only config files, not convars. If an old shared config held a secret, move it to a new server-side file and leave an empty value in the shared file.
- Hidden reward tables, drop rates, anti-cheat thresholds -> `config/config.server.lua` in `server_scripts`.
- Add secret-bearing config files to `.gitignore` for any public repo.

Prices may be shared for display, but the server always re-reads them from its own `Config` before charging.

## Zero Dead Or Fake Configs

- Never leave dead `Config` keys or files that `core/` never reads (such as unused timer/interval keys or unused table-name keys when SQL queries use static table names).
- Remove orphaned dataset files whose entries are unused or disabled across the resource.
- Do not split internal engine constants or preview/mock overrides into extra config files; preview modes should consume the real configuration directly.

## No Integration Layer In Config

There is no `config/function/` folder and no `FC` table. Owners tune values in `config/*.lua`; integration calls (inventory, money, notify, text UI, progress, logs) live in `core/` as module methods. See `skills/common/core-api.md`.
