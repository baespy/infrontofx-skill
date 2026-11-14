# Core API

How a resource reaches the framework, notifications, text UI, progress, logs, and other shared exports. All of it is written directly inside `core/` as methods of the module table. There is no integration layer: the old `FC` table and the `config/function/` folder were removed, and resources that still have them are migrated by moving each used entry into `core/` (one-line wrappers are replaced by the real call at the use site; entries with logic become module methods).

## Reaching The Framework

- Every resource lists `"@1nfx_core/imports.lua"` in `shared_scripts` (after `"@ox_lib/init.lua"`); do not add a `dependencies` block, start order is set in `server.cfg`.
- The import provides a global `Core`. It is ESX-compatible: `Core.GetPlayerFromId`, `Core.GetExtendedPlayers`, `Core.RegisterUsableItem`, `Core.GetItemLabel`, `Core.IsPlayerLoaded` (client), `Core.GetPlayerData` (client), and the usual `xPlayer` methods (`xPlayer.getIdentifier()`, `xPlayer.addInventoryItem(name, count)`, ...). The method list is in `references/esx-api.md`.
- Do not write `local ESX = exports["es_extended"]:getSharedObject()` and do not call `TriggerEvent("esx:getSharedObject", ...)`.
- Framework events are named `1nfx_core:*` (`1nfx_core:playerLoaded`, `1nfx_core:setJob`, ...). Legacy `esx:*` names still fire locally for old resources, but new code listens to `1nfx_core:*`. Listen to framework events; never re-trigger them.
- Resolve `xPlayer` once per job, nil-check it, and do not keep it across a yield.

## Where The Methods Live

The methods below belong to the same module table as the rest of the logic (`Shop` / `ShopServer`). Write only the ones the resource actually calls. Names must not collide with existing methods; grep the module before adding one.

A method exists only when it carries logic or is used in several places. A one-line wrapper around an export or event is not written: put `exports["1nfx_processbar"]:getIsDoingAction()` where it is needed.

## Client Methods

```lua
function Shop:Notify(label, notifyType)
    TriggerEvent("pNotify:SendNotification", {
        text = label,
        type = notifyType or "info",
    })
end

function Shop:GetItem(itemName)
    for _, item in pairs(Core.GetPlayerData().inventory) do
        if item.name == itemName then
            return item
        end
    end
    return nil
end

function Shop:GetItemCount(itemName)
    local item = self:GetItem(itemName)
    return item and item.count or 0
end

function Shop:GetMoney(accountName)
    for _, account in pairs(Core.GetPlayerData().accounts) do
        if account.name == accountName then
            return account.money
        end
    end
    return 0
end

function Shop:ShowTextUI(text)
    BeginTextCommandDisplayHelp("STRING")
    AddTextComponentSubstringPlayerName(text)
    EndTextCommandDisplayHelp(0, false, true, -1)
end

function Shop:HideTextUI()
    ClearAllHelpMessages()
end
```

- Client values from `Core.GetPlayerData()` are a local cache for display only. They never prove inventory, money, job, permission, elapsed time, ownership, or reward eligibility to the server.
- Progress bars and text UI of the server are separate resources (`1nfx_processbar`, `1nfx_textui`): call their exports in full at the use site, for example `exports["1nfx_processbar"]:getIsDoingAction()`. Never use `lib.progressBar` or `lib.showTextUI` (see `skills/common/ox-lib.md`).

## Server Methods

```lua
function ShopServer:Notify(src, label, notifyType)
    TriggerClientEvent("pNotify:SendNotification", src, {
        text = label,
        type = notifyType or "info",
    })
end

function ShopServer:GetIdentifier(src)
    local xPlayer = Core.GetPlayerFromId(src)
    return xPlayer and xPlayer.getIdentifier() or nil
end

function ShopServer:GetMoney(src, accountName)
    local xPlayer = Core.GetPlayerFromId(src)
    if not xPlayer then
        return 0
    end
    return xPlayer.getAccount(accountName).money
end

function ShopServer:CanCarryItem(src, itemName, count)
    local xPlayer = Core.GetPlayerFromId(src)
    return xPlayer ~= nil and xPlayer.canCarryItem(itemName, count) == true
end

function ShopServer:AddItem(src, itemName, count)
    local xPlayer = Core.GetPlayerFromId(src)
    if not xPlayer then
        return false
    end
    xPlayer.addInventoryItem(itemName, count)
    return true
end

function ShopServer:RemoveMoney(src, accountName, amount)
    local xPlayer = Core.GetPlayerFromId(src)
    if not xPlayer then
        return false
    end
    xPlayer.removeAccountMoney(accountName, amount)
    return true
end
```

- It is valid to nil-check `xPlayer` before calling a framework method: disconnects and post-yield source reuse are runtime failures.
- Mutation methods return an explicit success when the caller must react to failure. The caller validates names, counts, amounts, permissions, distance, bucket, cooldown, and ownership before calling a mutation method; the method does not invent default counts or amounts.
- Do not add `if not label or label == "" then return end` to `Notify`: the caller owns the value.
- Keep a framework fallback only when the supported versions genuinely differ.
- Do not catch and hide errors unless the integration is explicitly optional.

## Logs

Webhook URLs and tokens are secrets: they live in `config/config.server.lua` (server-only), never in shared config and never sent to a client.

```lua
function ShopServer:Log(src, event, content)
    PerformHttpRequest(Config.Webhooks.shop, nil, "POST", json.encode({
        username = event,
        content = ("[%s] %s"):format(self:GetIdentifier(src), content),
    }), { ["Content-Type"] = "application/json" })
end
```

- Log every value mutation with who, what, amount, and where. Truncate client-supplied text and never log secrets.
- For frequent events, batch through one bounded queue instead of one request per event (`skills/common/performance.md`).

## Owner Gates And Reactions

When a server owner needs a veto or a hook point, write it as a method of the module with a clear name and call it from the flow:

- Gate: `ShopServer:CanPurchase(src, shop, item, amount)` returns a boolean and the caller respects it. Call it before the in-flight lock is set.
- Reaction: `ShopServer:OnPurchased(...)` runs only after success and does not change authority.
- Only server methods may grant value. Client methods affect presentation only.
- Business flow stays in the module; there is no separate dispatcher layer.

## Usable Items

```lua
function ShopServer:RegisterItems()
    Core.RegisterUsableItem("bandage", function(src)
        self:UseBandage(src)
    end)
end
```

## Rules Recap

- All framework, notify, text UI, progress, and log calls are module methods or direct calls at the use site.
- Resource names are written in full; no alias variables.
- No comments, no file-level constants, no top-level `local function`.
- Swapping a notify or inventory provider means editing the one method that talks to it.

See `references/esx-api.md` (ESX-compatible `Core` surface) and `references/pnotify-api.md` (notification payload).
