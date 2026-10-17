# Database And Persistence

## Defaults

- oxmysql only: `"@oxmysql/lib/MySQL.lua"` in `server_scripts`.
- Parameterized queries with `?` always. Never concatenate values into SQL.
- Async on gameplay paths (`MySQL.insert`, `MySQL.update`, `MySQL.query` with callback) or `.await` inside a dedicated thread.
- Keep live data in RAM (`ServerState`), mark dirty, save in batches.
- Ship `install.sql` with `CREATE TABLE IF NOT EXISTS` and the indexes your queries use.

## API Shape

```lua
local rows = MySQL.query.await("SELECT id, owner, type FROM 1nfx_growth_garden WHERE owner = ?", { identifier })
local row = MySQL.single.await("SELECT money FROM users WHERE identifier = ?", { identifier })
local id = MySQL.insert.await("INSERT INTO 1nfx_growth_garden (owner, type) VALUES (?, ?)", { identifier, plantType })
local affected = MySQL.update.await("UPDATE 1nfx_growth_garden SET feed = ? WHERE id = ?", { feed, id })
local ok = MySQL.transaction.await({
    { query = "UPDATE users SET money = money - ? WHERE identifier = ? AND money >= ?", values = { cost, identifier, cost } },
    { query = "INSERT INTO purchases (identifier, item, amount) VALUES (?, ?, ?)", values = { identifier, item, amount } },
})
```

Use `MySQL.prepare` for hot repeated statements.

## Dirty Save Pattern

```lua
function NameServer:MarkDirty(entity)
    entity.dirty = true
    self.ServerState.dirtyCount = (self.ServerState.dirtyCount or 0) + 1
end

function NameServer:SaveDirty()
    local batch = {}
    for _, entity in pairs(self.ServerState.entities) do
        if entity.dirty then
            batch[#batch + 1] = { query = "UPDATE 1nfx_name SET data = ? WHERE id = ?", values = { json.encode(entity.data), entity.id } }
            entity.dirty = false
        end
    end
    if #batch > 0 then
        MySQL.transaction(batch, function(ok)
            if not ok then
                NameServer:RequeueBatch(batch)
            end
        end)
    end
end
```

- Autosave interval from config (`Config.General.save.interval_sec`).
- Save the player's rows on `playerDropped` when `on_player_dropped = true`.
- On `onResourceStop` use `.await` so writes finish before teardown.
- Deleted rows go to `ServerState.deletedEntities` and are removed in the same batch.

## Resource KVP

Good for: fast-start snapshots, small server caches (owner names), client UI preferences.

```lua
local KVP_SNAPSHOT = "growth_garden:plants_snapshot:v1"

local ok, encoded = pcall(json.encode, list)
if ok and encoded and self.ServerState.lastSnapshot ~= encoded then
    SetResourceKvp(KVP_SNAPSHOT, encoded)
    self.ServerState.lastSnapshot = encoded
end
```

- Version keys (`:v1`) and bump when the shape changes.
- `pcall(json.decode, raw)` and type-check the result.
- Skip writes when the encoded string did not change.
- Pair a snapshot with a signature (`count:feedSum:maxTimestamp`) and compare against a cheap `SELECT COUNT(*) ...` on start to decide whether the snapshot is still valid (see `memory/patterns.md` -> KVP Snapshot With Signature).
- Never store authority (money, items) only in client KVP.

## Schema

- Use `INT UNSIGNED AUTO_INCREMENT` ids, `VARCHAR(60)` identifiers, index every `WHERE` column.
- Timestamps as `INT` unix seconds when compared in Lua (`os.time()`).
- Store flexible data as `LONGTEXT` JSON only when it is never queried by field.

