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
    return exports["es_extended"]:RunStaticPlayerMethod(source, "getIdentifier")
end

FC.GetItem = function(source, itemName)
    return exports["es_extended"]:RunStaticPlayerMethod(source, "getInventoryItem", itemName)
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
    return exports["es_extended"]:RunStaticPlayerMethod(source, "getAccount", accountName or "money")
end

FC.GetMoney = function(source, accountName)
    local account = FC.GetAccount(source, accountName)
    return account and (account.money or 0) or 0
end

FC.CheckMoney = function(source, accountName, amount)
    return FC.GetMoney(source, accountName) >= (amount or 1)
end

FC.CanCarryItem = function(source, itemName, count)
    return exports["es_extended"]:RunStaticPlayerMethod(source, "canCarryItem", itemName, count or 1) == true
end

FC.AddItem = function(source, itemName, count)
    return exports["es_extended"]:RunStaticPlayerMethod(source, "addInventoryItem", itemName, count)
end

FC.RemoveMoney = function(source, accountName, amount)
    return exports["es_extended"]:RunStaticPlayerMethod(source, "removeAccountMoney", accountName or "money", amount)
end

FC.Log = function(source, event, content)
end

FC.CanPurchase = function(source, shop, item, amount)
    return true
end

FC.OnPurchased = function(source, shop, item, amount, cost)
    FC.Log(source, "Shop", ("%s x%d (%d %s) @ %s"):format(item.name, amount, cost, item.account, shop.id))
end
