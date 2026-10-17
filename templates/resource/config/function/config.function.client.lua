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

FC.ShowTextUI = function(text)
    exports["1nfx_textui"]:ShowHelpNotificationToggle(text)
end

FC.HideTextUI = function()
    exports["1nfx_textui"]:ClearHelpNotification()
end

FC.CanOpenShop = function(shop)
    return not IsPedDeadOrDying(cache.ped, true) and not IsPedInAnyVehicle(cache.ped, false)
end

FC.OnPurchased = function(shop, item, amount)
end
