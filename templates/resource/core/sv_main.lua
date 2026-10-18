ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()
local tonumber = tonumber
local type = type
local math_floor = math.floor
local GetGameTimer = GetGameTimer

TemplateServer = {
    ServerState = {
        throttle = {},
        inFlight = {},
    },
}

function TemplateServer:IsThrottled(src, key, limit)
    local now = GetGameTimer()
    local bucket = self.ServerState.throttle[src]
    if not bucket then
        bucket = {}
        self.ServerState.throttle[src] = bucket
    end
    if now - (bucket[key] or 0) < limit then
        return true
    end
    bucket[key] = now
    return false
end

function TemplateServer:IsNearShop(src, shop)
    local ped = GetPlayerPed(src)
    if not ped or ped == 0 then
        return false
    end
    return #(GetEntityCoords(ped) - shop.coords) <= Config.General.interact.distance + 3.0
end

function TemplateServer:FindItem(shop, itemName)
    for _, item in ipairs(shop.items) do
        if item.name == itemName then
            return item
        end
    end
    return nil
end

function TemplateServer:GetShop(src, shopId)
    if self:IsThrottled(src, "open", Config.General.throttle_ms.open) then
        return false, Config.Text.busy
    end
    local shop = type(shopId) == "string" and Config.Shops[shopId]
    if not shop then
        return false, Config.Text.invalid_item
    end
    if not self:IsNearShop(src, shop) then
        return false, Config.Text.too_far
    end
    local items = {}
    for index, item in ipairs(shop.items) do
        items[index] = {
            name = item.name,
            label = FC.GetItemLabel(src, item.name) or item.name,
            price = item.price,
            account = item.account,
        }
    end
    return true, {
        id = shopId,
        label = shop.label,
        items = items,
        money = FC.GetMoney(src, "money"),
        maxAmount = Config.General.max_amount,
    }
end

function TemplateServer:Buy(src, payload)
    if self:IsThrottled(src, "buy", Config.General.throttle_ms.buy) then
        return false, { message = Config.Text.busy }
    end
    if type(payload) ~= "table" or type(payload.shopId) ~= "string" or type(payload.item) ~= "string" then
        return false, { message = Config.Text.invalid_item }
    end
    local amount = tonumber(payload.amount)
    if not amount or amount ~= amount then
        return false, { message = Config.Text.invalid_amount }
    end
    amount = math_floor(amount)
    if amount <= 0 or amount > Config.General.max_amount then
        return false, { message = Config.Text.invalid_amount }
    end
    local shop = Config.Shops[payload.shopId]
    local item = shop and self:FindItem(shop, payload.item)
    if not item then
        return false, { message = Config.Text.invalid_item }
    end
    if not self:IsNearShop(src, shop) then
        return false, { message = Config.Text.too_far }
    end
    if not FC.CanPurchase(src, shop, item, amount) then
        return false, {}
    end
    if self.ServerState.inFlight[src] then
        return false, { message = Config.Text.busy }
    end
    self.ServerState.inFlight[src] = true
    local cost = item.price * amount
    if not FC.CheckMoney(src, item.account, cost) then
        self.ServerState.inFlight[src] = nil
        return false, { message = Config.Text.not_enough_money }
    end
    if not FC.CanCarryItem(src, item.name, amount) then
        self.ServerState.inFlight[src] = nil
        return false, { message = Config.Text.inventory_full }
    end
    FC.RemoveMoney(src, item.account, cost)
    FC.AddItem(src, item.name, amount)
    self.ServerState.inFlight[src] = nil
    FC.OnPurchased(src, shop, item, amount, cost)
    return true, {
        message = Config.Text.purchased:format(FC.GetItemLabel(src, item.name) or item.name, amount),
        amount = amount,
        money = FC.GetMoney(src, "money"),
    }
end

function TemplateServer:ClearPlayer(src)
    self.ServerState.throttle[src] = nil
    self.ServerState.inFlight[src] = nil
end

lib.callback.register(scriptname .. ":SV:getShop", function(source, shopId)
    local src = source
    return TemplateServer:GetShop(src, shopId)
end)

lib.callback.register(scriptname .. ":SV:buy", function(source, payload)
    local src = source
    return TemplateServer:Buy(src, payload)
end)

AddEventHandler("playerDropped", function()
    local src = source
    TemplateServer:ClearPlayer(src)
end)
