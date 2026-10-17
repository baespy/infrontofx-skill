# Config

How infrontofx resources expose tunable values.

## config/config.lua

```lua
sec = 1000
min = 60 * sec

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
    not_enough_money = "เงินไม่พอ",
    inventory_full = "กระเป๋าเต็ม",
    purchased = "ซื้อ %s x%d สำเร็จ",
}
```

Rules:

- `Config = {}` once, in `config.lua` only. Other config files add keys: `Config.Shops = { ... }`.
- `Config.General` groups by feature with snake_case keys. Short inline tables for small groups.
- Every player-facing string lives in `Config.Text` so owners can translate without touching core.
- Durations: name the unit (`interval_sec`, `growthMinutes`, `lifetimeHours`) or use `sec` / `min` constants.
- Mode switches are strings with documented values (`method = "item" | "statebag"`), not booleans pairs.

## Split Config Files

Large or independent datasets go in `config/config.<domain>.lua`:

```lua
Config.Plants = {
    seed_sunflower = {
        label = "Sunflower",
        models = { "sunflowers_s1", "sunflowers_s2", "sunflowers_s3", "sunflowers_s4" },
        growthMinutes = 60,
        harvest = {
            { item = "sunflower", count = { 1, 1 }, chance = 100 },
            { item = "sunflower_big", count = { 1, 1 }, chance = 30 },
        },
    },
}
```

- Key datasets by their natural id (`seed_sunflower`, `main_market`) so lookups are O(1).
- Keep a dataset in one file; do not spread one table across files.

## core/sh_config.lua - Validate And Normalize Once

```lua
Config = Config or {}

for seed, plant in pairs(Config.Plants) do
    assert(type(plant.models) == "table" and #plant.models >= 4, ("Plant %s needs four models"):format(seed))
    plant.type = seed
    plant.growthTimeSec = plant.growthMinutes * 60
    plant.materialHash = {}
    for _, hash in ipairs(plant.ground or {}) do
        plant.materialHash[hash] = true
    end
end
```

- `assert` bad config at start so the owner sees the error in console instead of a runtime nil.
- Pre-compute derived values (seconds, hash sets, reverse indexes, defaults) here, never per tick.
- Fill defaults with `lib.table.deepclone(Config.Defaults.x)` so rows do not share mutable tables.

## What Must Not Be In Shared Config

Shared config is downloaded by every client. Never put these in `shared_scripts` files:

- Webhook URLs, API keys, tokens, DB credentials -> server convar (`GetConvar("name_webhook", "")`).
- Hidden reward tables, drop rates, anti-cheat thresholds -> `config/config.server.lua` in `server_scripts`.

Prices may be shared for display, but the server always re-reads them from its own `Config` before charging.

## config/function - The FC Layer

`config/function/config.function.client.lua` and `config.function.server.lua` are part of the config surface: owners swap inventory, notify, or framework here. Full contract in `skills/common/fc-adapters.md`.

