ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()
FC = FC or {}

FC.Notify = function(source, label, notifyType)
    TriggerClientEvent("pNotify:SendNotification", source, {
        text = label,
        type = notifyType or "info",
    })
end

FC.GetIdentifier = function(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getIdentifier() or nil
end

FC.GetItem = function(source, itemName)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getInventoryItem(itemName) or nil
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

FC.GetAccount = function(source, accountName)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.getAccount(accountName or "money") or nil
end

FC.GetMoney = function(source, accountName)
    local account = FC.GetAccount(source, accountName)
    return account and (account.money or 0) or 0
end

FC.CheckMoney = function(source, accountName, amount)
    return FC.GetMoney(source, accountName) >= amount
end

FC.CanCarryItem = function(source, itemName, count)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    if xPlayer.canCarryItem then
        return xPlayer.canCarryItem(itemName, count) == true
    end
    local item = xPlayer.getInventoryItem(itemName)
    if not item then
        return false
    end
    local limit = item.limit or -1
    return limit == -1 or (item.count or 0) + count <= limit
end

FC.AddItem = function(source, itemName, count)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then
        return false
    end
    xPlayer.addInventoryItem(itemName, count)
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

FC.Log = function(source, event, content)
end

FC.CanPurchase = function(source, shop, item, amount)
    return true
end

FC.OnPurchased = function(source, shop, item, amount, cost)
    FC.Log(source, "Shop", ("%s x%d (%d %s) @ %s"):format(item.name, amount, cost, item.account, shop.id))
end
