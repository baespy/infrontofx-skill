local scriptname = GetCurrentResourceName()

local Template = {
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
}

function Template:Notify(label, notifyType)
    TriggerEvent("pNotify:SendNotification", {
        text = label,
        type = notifyType or "info",
    })
end

function Template:PostNUI(action, data)
    if not self.PlayerState.uiReady then
        return
    end
    SendNUIMessage({
        action = action,
        data = data,
    })
end

function Template:Start()
    while not Core.IsPlayerLoaded() do
        Wait(500)
    end
    for shopId, shop in pairs(Config.Shops) do
        self:CreatePoint(shopId, shop)
        if Config.General.blip.enabled and shop.blip then
            self:CreateBlip(shop)
        end
    end
end

function Template:CreatePoint(shopId, shop)
    local point = lib.points.new({
        coords = shop.coords,
        distance = Config.General.interact.draw_distance,
        shopId = shopId,
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
            BeginTextCommandDisplayHelp("STRING")
            AddTextComponentSubstringPlayerName(Config.Text.prompt_open)
            EndTextCommandDisplayHelp(0, false, true, -1)
        end
    elseif self.PlayerState.nearShopId == shopId then
        self.PlayerState.nearShopId = nil
        ClearAllHelpMessages()
    end
end

function Template:OpenShop(shopId)
    if self.PlayerState.busy or self.PlayerState.uiOpen then
        return
    end
    if IsPedDeadOrDying(cache.ped, true) or IsPedInAnyVehicle(cache.ped, false) then
        return
    end
    self.PlayerState.busy = true
    lib.callback(scriptname .. ":SV:getShop", false, function(ok, result)
        Template.PlayerState.busy = false
        if not ok then
            Template:Notify(result, "error")
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
            ClearAllHelpMessages()
        end
        TriggerScreenblurFadeIn(250)
        self:PostNUI("open", data)
    else
        self.PlayerState.shopId = nil
        TriggerScreenblurFadeOut(250)
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
    self:Notify(result.message, ok and "success" or "error")
    return ok == true, result.money
end

function Template:OnReady(cb)
    self.PlayerState.uiReady = true
    cb({ ok = true })
end

function Template:OnClose(cb)
    self:SetUI(false)
    cb({ ok = true })
end

function Template:OnBuy(data, cb)
    if type(data) ~= "table" or type(data.item) ~= "string" or #data.item > 64 then
        cb({ ok = false })
        return
    end
    local ok, money = self:Buy(data.item, math.floor(tonumber(data.amount) or 0))
    cb({ ok = ok, money = money })
end

function Template:OnDeath()
    if self.PlayerState.uiOpen then
        self:SetUI(false)
    end
end

function Template:OnStop(resource)
    if resource ~= scriptname then
        return
    end
    for _, point in ipairs(self.Points) do
        point:remove()
    end
    for _, blip in ipairs(self.Blips) do
        if DoesBlipExist(blip) then
            RemoveBlip(blip)
        end
    end
    self.Points, self.Blips = {}, {}
    if self.PlayerState.nearShopId then
        ClearAllHelpMessages()
    end
    TriggerScreenblurFadeOut(0)
    SetNuiFocus(false, false)
end

RegisterNUICallback("uiReady", function(_, cb)
    Template:OnReady(cb)
end)

RegisterNUICallback("close", function(_, cb)
    Template:OnClose(cb)
end)

RegisterNUICallback("buy", function(data, cb)
    Template:OnBuy(data, cb)
end)

AddEventHandler("1nfx_core:onPlayerDeath", function()
    Template:OnDeath()
end)

AddEventHandler("onResourceStop", function(resource)
    Template:OnStop(resource)
end)

CreateThread(function()
    Template:Start()
end)
