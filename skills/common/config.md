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

- `Config = {}` once, in `config.lua` only. Other config files add keys: `Config.Shops = { ... }`.
- `Config.General` groups by feature with snake_case keys. Short inline tables for small groups.
- Every player-facing string lives in `Config.Text` so owners can translate without touching core.
- Durations name their unit (`interval_ms`, `cooldown_sec`, `lifetime_hours`). Do not create loose global time constants.
- Mode switches are strings with documented values (`method = "item" | "statebag"`), not boolean pairs.
- Read `Config.General.*` and `Config.Text.*` directly in `core/*`. Never wrap config reads in `(Config.General and Config.General.x) or default` fallback chains, and do not create a `core/sh_config.lua` normalization file.

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

Shared config is downloaded by every client. Never put these in `shared_scripts` files:

- Webhook URLs, API keys, tokens, DB credentials -> server convar (`GetConvar("name_webhook", "")`).
- Hidden reward tables, drop rates, anti-cheat thresholds -> `config/config.server.lua` in `server_scripts`.

Prices may be shared for display, but the server always re-reads them from its own `Config` before charging.

## config/function - The FC Layer

`config/function/config.function.client.lua` and `config.function.server.lua` are part of the config surface: owners swap inventory, notify, or framework here. Full contract in `skills/common/fc-adapters.md`.
