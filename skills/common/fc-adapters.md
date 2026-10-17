# FC Adapters

`FC` (Config Function) is the only place a resource touches frameworks, inventories, notifications, text UI, progress bars, logs, or owner-customizable gameplay rules. Core code calls `FC.*` and stays portable.

## Files

- `config/function/config.function.client.lua` - loaded in `client_scripts` before `core/cl_*`.
- `config/function/config.function.server.lua` - loaded in `server_scripts` before `core/sv_*`.

Both start with:

```lua
ESX = exports["es_extended"]:getSharedObject()
FC = FC or {}
```

## Two Kinds Of Entries

1. **Adapters** - thin wrappers over standard ESX and external resources.
2. **Hooks** - owner-editable gameplay decisions. `FC.CanXxx` returns boolean (gate), `FC.OnXxx` reacts (side effect, return ignored unless documented).

Core code always calls hooks at the documented moment and respects the return value:

```lua
if not FC.CanOpenShop(shop) then
    return
end
```

## Standard Client Adapters

```lua
ESX = exports["es_extended"]:getSharedObject()
FC = FC or {}

FC.Notify = function(label, notifyType)
    if not label or label == "" then
        return
    end
    TriggerEvent("pNotify:SendNotification", {
        text = label,
        type = notifyType or "info",
    })
end

FC.GetItem = function(itemName)
    local playerData = ESX.GetPlayerData()
    for _, item in pairs(playerData and playerData.inventory or {}) do
        if item and item.name == itemName then
            return item
        end
    end
    return nil
end

FC.GetItemCount = function(itemName)
    local item = FC.GetItem(itemName)
    return item and (item.count or 0) or 0
end

FC.GetItemLabel = function(itemName)
    if ESX.GetItemLabel then
        local label = ESX.GetItemLabel(itemName)
        if label and label ~= "" then
            return label
        end
    end
    local item = FC.GetItem(itemName)
    return item and item.label or itemName
end

FC.CheckItem = function(itemName, count)
    return FC.GetItemCount(itemName) >= (count or 1)
end

FC.CanCarryItem = function(itemName, count)
    local item = FC.GetItem(itemName)
    if not item then
        return false
    end
    local limit = item.limit or -1
    return limit == -1 or (item.count or 0) + (count or 1) <= limit
end

FC.GetAccount = function(accountName)
    local target = accountName or "money"
    local playerData = ESX.GetPlayerData()
    for _, account in pairs(playerData and playerData.accounts or {}) do
        if account and account.name == target then
            return account
        end
    end
    return nil
end

FC.GetMoney = function(accountName)
    local account = FC.GetAccount(accountName)
    return account and (account.money or 0) or 0
end

FC.CheckMoney = function(accountName, amount)
    return FC.GetMoney(accountName) >= (amount or 1)
end

FC.GetJob = function()
    local playerData = ESX.GetPlayerData()
    return playerData and playerData.job and playerData.job.name or nil
end

FC.ShowTextUI = function(text)
    if not text or text == "" then
        return
    end
    BeginTextCommandDisplayHelp("STRING")
    AddTextComponentSubstringPlayerName(text)
    EndTextCommandDisplayHelp(0, false, true, -1)
end

FC.HideTextUI = function()
    ClearAllHelpMessages()
end

FC.Progress = function(data, onFinish)
    if onFinish then
        onFinish(true)
    end
end
```

## Standard Server Adapters

```lua
ESX = exports["es_extended"]:getSharedObject()
FC = FC or {}

FC.Notify = function(source, label, notifyType)
    if not label or label == "" then
        return
    end
    TriggerClientEvent("pNotify:SendNotification", source, {
        text = label,
        type = notifyType or "info",
    })
end

FC.GetIdentifier = function(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getIdentifier() or nil
end

FC.GetPlayerName = function(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    return (xPlayer and xPlayer.getName()) or GetPlayerName(source) or "Unknown"
end

FC.GetJob = function(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    local job = xPlayer and xPlayer.getJob()
    return job and job.name or nil
end

FC.GetItem = function(source, itemName)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getInventoryItem(itemName) or nil
end

FC.GetItemCount = function(source, itemName)
    local item = FC.GetItem(source, itemName)
    return item and (item.count or 0) or 0
end

FC.GetItemLabel = function(source, itemName)
    if ESX.GetItemLabel then
        local label = ESX.GetItemLabel(itemName)
        if label and label ~= "" then
            return label
        end
    end
    local item = FC.GetItem(source, itemName)
    return item and item.label or itemName
end

FC.CheckItem = function(source, itemName, count)
    return FC.GetItemCount(source, itemName) >= (count or 1)
end

FC.CanCarryItem = function(source, itemName, count)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    if xPlayer.canCarryItem then
        return xPlayer.canCarryItem(itemName, count or 1) == true
    end
    local item = xPlayer.getInventoryItem(itemName)
    if not item then
        return false
    end
    local limit = item.limit or -1
    return limit == -1 or (item.count or 0) + (count or 1) <= limit
end

FC.GetAccount = function(source, accountName)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getAccount(accountName or "money") or nil
end

FC.GetMoney = function(source, accountName)
    local account = FC.GetAccount(source, accountName)
    return account and (account.money or 0) or 0
end

FC.CheckMoney = function(source, accountName, amount)
    return FC.GetMoney(source, accountName) >= (amount or 1)
end

FC.AddItem = function(source, itemName, count)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    xPlayer.addInventoryItem(itemName, count)
    return true
end

FC.RemoveItem = function(source, itemName, count)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    xPlayer.removeInventoryItem(itemName, count)
    return true
end

FC.AddMoney = function(source, accountName, amount)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    xPlayer.addAccountMoney(accountName or "money", amount)
    return true
end

FC.RemoveMoney = function(source, accountName, amount)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    xPlayer.removeAccountMoney(accountName or "money", amount)
    return true
end

FC.CountJob = function(jobName)
    return #ESX.GetExtendedPlayers("job", jobName)
end

FC.Log = function(source, event, content)
end
```

## Hook Examples

Client:

```lua
FC.CanOpenShop = function(shop)
    return not IsPedDeadOrDying(cache.ped, true) and not IsPedInAnyVehicle(cache.ped, false)
end

FC.OnPurchased = function(shop, item, amount)
end
```

Server:

```lua
FC.IsVip = function(source)
    local vip = Config.General.vip
    if vip.method == "statebag" then
        return Player(source).state[vip.statebag] == true
    end
    return FC.GetItemCount(source, vip.item) > 0
end

FC.CanPurchase = function(source, shop, item, amount)
    return true
end

FC.OnPurchased = function(source, shop, item, amount, cost)
    FC.Log(source, "Shop", ("%s x%d (%d)"):format(item.name, amount, cost))
end
```

## Rules

- Argument order: client `FC.Notify(label, notifyType)`, server `FC.Notify(source, label, notifyType)`. Server adapters always take `source` first.
- Use standard `ESX.GetPlayerFromId(source)` inside server `FC` adapters; never use non-standard fork methods like `RunStaticPlayerMethod`.
- Adapters call ESX and exports directly; no `GetResourceState` guards (`rules/contracts.md`).
- Hooks may read the controller table (`Shop:IsOpen()`) but must not mutate core state.
- Server hooks are the only hooks that can grant value. Client hooks are UX only.
- Swapping inventory/notify/textui/progress/logging is done by editing these two files only. See `references/esx-api.md` for the default contract.
