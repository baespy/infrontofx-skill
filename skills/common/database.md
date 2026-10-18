# Database And Persistence

## Defaults

- oxmysql only: `"@oxmysql/lib/MySQL.lua"` in `server_scripts`.
- Parameterized queries with `?` always. Never concatenate values into SQL.
- Async on gameplay paths (`MySQL.insert`, `MySQL.update`, `MySQL.query` with callback) or `.await` inside a dedicated thread.
- Keep live data in RAM (`ServerState`), mark dirty, save in batches.
- Ship `install.sql` with `CREATE TABLE IF NOT EXISTS` and the indexes your queries use.

## API Shape

```lua
local rows = MySQL.query.await("SELECT id, owner, state FROM resource_entities WHERE owner = ?", { identifier })
local row = MySQL.single.await("SELECT money FROM users WHERE identifier = ?", { identifier })
local id = MySQL.insert.await("INSERT INTO resource_entities (owner, state) VALUES (?, ?)", { identifier, state })
local affected = MySQL.update.await("UPDATE resource_entities SET state = ? WHERE id = ?", { state, id })
local ok = MySQL.transaction.await({
    { query = "UPDATE users SET money = money - ? WHERE identifier = ? AND money >= ?", values = { cost, identifier, cost } },
    { query = "INSERT INTO purchases (identifier, item, amount) VALUES (?, ?, ?)", values = { identifier, item, amount } },
})
```

Use `MySQL.prepare` for hot repeated statements.

## Query Shape And Throughput

- Select only the columns the caller consumes. Avoid `SELECT *` in gameplay and UI paths.
- Never await one query per row or player. Fetch with one bounded `IN (...)` query, join, transaction, or prepared batch.
- Use keyset pagination (`WHERE id > ? ORDER BY id LIMIT ?`) for large tables. Offset pagination is acceptable only for small admin views.
- Use `INSERT ... ON DUPLICATE KEY UPDATE` for atomic upserts. Do not use `REPLACE` when deleting and recreating the row would break relations or metadata.
- Keep transactions short. Do not call exports, HTTP, callbacks, or `Wait` while a transaction is open.
- Bound batch sizes from config. Split large saves so one autosave cannot monopolize the database queue.
- Inspect slow queries with the database slow-query log and `EXPLAIN`; add composite indexes in the same order used by `WHERE` and `ORDER BY`.

## Dirty Save Pattern

```lua
function NameServer:MarkDirty(entity)
    entity.revision = (entity.revision or 0) + 1
    entity.dirty = true
end

function NameServer:SaveDirty()
    local batch = {}
    local revisions = {}
    for id, entity in pairs(self.ServerState.entities) do
        if entity.dirty then
            batch[#batch + 1] = { query = "UPDATE resource_entities SET data = ? WHERE id = ?", values = { json.encode(entity.data), entity.id } }
            revisions[id] = entity.revision
            if #batch >= Config.General.save.batch_size then
                break
            end
        end
    end
    if #batch > 0 then
        MySQL.transaction(batch, function(ok)
            if ok then
                for id, revision in pairs(revisions) do
                    local entity = NameServer.ServerState.entities[id]
                    if entity and entity.revision == revision then
                        entity.dirty = false
                    end
                end
            end
        end)
    end
end
```

- Autosave interval from config (`Config.General.save.interval_sec`).
- Autosave processes a bounded batch and carries remaining dirty entries into the next run.
- Save the player's rows on `playerDropped` when `on_player_dropped = true`.
- On `onResourceStop` use `.await` so writes finish before teardown.
- Deleted rows go to `ServerState.deletedEntities` and are removed in the same batch.
- Clear an entity's dirty revision only after its matching write succeeds. If it changed during the write, leave the newer revision dirty.

## Resource KVP

Good for: fast-start snapshots, small server caches (owner names), client UI preferences.

```lua
local KVP_SNAPSHOT = "resource:entities_snapshot:v1"

local ok, encoded = pcall(json.encode, list)
if ok and encoded and self.ServerState.lastSnapshot ~= encoded then
    SetResourceKvp(KVP_SNAPSHOT, encoded)
    self.ServerState.lastSnapshot = encoded
end
```

- Version keys (`:v1`) and bump when the shape changes.
- `pcall(json.decode, raw)` and type-check the result.
- Skip writes when the encoded string did not change.
- Pair a snapshot with a signature (`count:stateSum:maxTimestamp`) and compare against a cheap `SELECT COUNT(*) ...` on start to decide whether the snapshot is still valid (see `memory/patterns.md` -> KVP Snapshot With Signature).
- Never store authority (money, items) only in client KVP.

## Schema

- Use `INT UNSIGNED AUTO_INCREMENT` ids, `VARCHAR(60)` identifiers, index every `WHERE` column.
- Timestamps as `INT` unix seconds when compared in Lua (`os.time()`).
- Store flexible data as `LONGTEXT` JSON only when it is never queried by field.
- Use a unique key for every upsert identity and foreign keys only when their delete/update behavior is deliberate.
