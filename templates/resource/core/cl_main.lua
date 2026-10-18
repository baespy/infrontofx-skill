ESX = exports["es_extended"]:getSharedObject()
local scriptname = GetCurrentResourceName()

Template = {
    ServerState = {},
    PlayerState = {
        busy = false,
        uiOpen = false,
        uiReady = false,
        shopId = nil,
        nearShopId = nil,
    },
    Points = {},
    Blips = {},
    PendingNUI = {},
}

function Template:PostNUI(action, data)
    local message = { action = action, data = data }
    if not self.PlayerState.uiReady then
        for index = #self.PendingNUI, 1, -1 do
            if self.PendingNUI[index].action == action then
                self.PendingNUI[index] = message
                return
            end
        end
        if #self.PendingNUI >= Config.General.nui_queue_limit then
            table.remove(self.PendingNUI, 1)
        end
        self.PendingNUI[#self.PendingNUI + 1] = message
        return
    end
    SendNUIMessage(message)
end

function Template:Init()
    for _, shop in pairs(Config.Shops) do
        self:CreatePoint(shop)
        if Config.General.blip.enabled and shop.blip then
            self:CreateBlip(shop)
        end
    end
end

function Template:CreatePoint(shop)
    local point = lib.points.new({
        coords = shop.coords,
        distance = Config.General.interact.draw_distance,
        shopId = shop.id,
    })

    function point:onExit()
        Template:SetPrompt(self.shopId, false)
    end

    function point:nearby()
        local inRange = self.currentDistance <= Config.General.interact.distance
        Template:SetPrompt(self.shopId, inRange)
        if inRange and IsControlJustReleased(0, Config.General.interact.key) then
            Template:OpenShop(self.shopId)
        end
    end

    self.Points[#self.Points + 1] = point
end

function Template:CreateBlip(shop)
    local blip = AddBlipForCoord(shop.coords.x, shop.coords.y, shop.coords.z)
    SetBlipSprite(blip, shop.blip.sprite)
    SetBlipColour(blip, shop.blip.color)
    SetBlipScale(blip, shop.blip.scale + 0.0)
    SetBlipAsShortRange(blip, true)
    BeginTextCommandSetBlipName("STRING")
    AddTextComponentSubstringPlayerName(shop.label)
    EndTextCommandSetBlipName(blip)
    self.Blips[#self.Blips + 1] = blip
end

function Template:SetPrompt(shopId, visible)
    if visible and not self.PlayerState.uiOpen then
        if self.PlayerState.nearShopId ~= shopId then
            self.PlayerState.nearShopId = shopId
            FC.ShowTextUI(Config.Text.prompt_open)
        end
    elseif self.PlayerState.nearShopId == shopId then
        self.PlayerState.nearShopId = nil
        FC.HideTextUI()
    end
end

function Template:OpenShop(shopId)
    if self.PlayerState.busy or self.PlayerState.uiOpen then
        return
    end
    local shop = Config.Shops[shopId]
    if not shop or not FC.CanOpenShop(shop) then
        return
    end
    self.PlayerState.busy = true
    lib.callback(scriptname .. ":SV:getShop", false, function(ok, result)
        Template.PlayerState.busy = false
        if not ok then
            FC.Notify(result, "error")
            return
        end
        Template.PlayerState.shopId = shopId
        Template:SetUI(true, result)
    end, shopId)
end

function Template:SetUI(open, data)
    self.PlayerState.uiOpen = open
    SetNuiFocus(open, open)
    if open then
        if self.PlayerState.nearShopId then
            self.PlayerState.nearShopId = nil
            FC.HideTextUI()
        end
        self:PostNUI("open", data)
    else
        self.PlayerState.shopId = nil
        self:PostNUI("close")
    end
end

function Template:Buy(itemName, amount)
    local shopId = self.PlayerState.shopId
    if not shopId then
        return false
    end
    local ok, result = lib.callback.await(scriptname .. ":SV:buy", false, {
        shopId = shopId,
        item = itemName,
        amount = amount,
    })
    result = type(result) == "table" and result or {}
    FC.Notify(result.message, ok and "success" or "error")
    if ok then
        local shop = Config.Shops[shopId]
        FC.OnPurchased(shop, shop.itemIndex[itemName], result.amount)
    end
    return ok == true, result.money
end

function Template:Destroy()
    for _, point in ipairs(self.Points) do
        point:remove()
    end
    for _, blip in ipairs(self.Blips) do
        if DoesBlipExist(blip) then
            RemoveBlip(blip)
        end
    end
    self.Points, self.Blips = {}, {}
    self.PendingNUI = {}
    if self.PlayerState.nearShopId then
        FC.HideTextUI()
    end
    SetNuiFocus(false, false)
end

RegisterNUICallback("uiReady", function(_, cb)
    if not Template.PlayerState.uiReady then
        Template.PlayerState.uiReady = true
        for index = 1, #Template.PendingNUI do
            SendNUIMessage(Template.PendingNUI[index])
        end
        Template.PendingNUI = {}
    end
    cb({ ok = true })
end)

RegisterNUICallback("close", function(_, cb)
    Template:SetUI(false)
    cb({ ok = true })
end)

RegisterNUICallback("buy", function(data, cb)
    if type(data) ~= "table" or type(data.item) ~= "string" or #data.item > 64 then
        cb({ ok = false })
        return
    end
    local ok, money = Template:Buy(data.item, math.floor(tonumber(data.amount) or 0))
    cb({ ok = ok, money = money })
end)

AddEventHandler("esx:onPlayerDeath", function()
    if Template.PlayerState.uiOpen then
        Template:SetUI(false)
    end
end)

CreateThread(function()
    while not ESX.IsPlayerLoaded() do
        Wait(500)
    end
    Template:Init()
end)

AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    Template:Destroy()
end)

