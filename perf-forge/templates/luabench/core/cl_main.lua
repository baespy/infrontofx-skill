local scriptname = GetCurrentResourceName()

local LuaBench = {
    PlayerState = {
        running = false,
        mirror = {},
    },
}

setmetatable(LuaBench, { __index = LuaBenchShared })

function LuaBench:Clock()
    return GetGameTimer() + 0.0
end

function LuaBench:ClientCases()
    local cases = {}
    local mirror = self.PlayerState.mirror
    cases[#cases + 1] = { "local state bag", "LocalPlayer.state.luabench each read", function(n)
        local v
        for _ = 1, n do
            v = LocalPlayer.state.luabench
        end
        self.sink = v
    end, 2000000 }
    cases[#cases + 1] = { "local state bag", "bag = LocalPlayer.state once, bag.luabench", function(n)
        local v
        local bag = LocalPlayer.state
        for _ = 1, n do
            v = bag.luabench
        end
        self.sink = v
    end, 2000000 }
    cases[#cases + 1] = { "local state bag", "mirror table filled by change handler", function(n)
        local v
        for _ = 1, n do
            v = mirror.luabench
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "entity state bag", "Entity(ped).state.luabench each read", function(n)
        local v
        local ped = PlayerPedId()
        for _ = 1, n do
            v = Entity(ped).state.luabench
        end
        self.sink = v
    end, 1000000 }
    cases[#cases + 1] = { "player ped", "PlayerPedId() each call", function(n)
        local v
        for _ = 1, n do
            v = PlayerPedId()
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "player ped", "cache.ped", function(n)
        local v
        for _ = 1, n do
            v = cache.ped
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "player coords", "GetEntityCoords(PlayerPedId())", function(n)
        local v
        for _ = 1, n do
            v = GetEntityCoords(PlayerPedId())
        end
        self.sink = v.x
    end }
    cases[#cases + 1] = { "player coords", "GetEntityCoords(ped) with ped pulled once", function(n)
        local v
        local ped = PlayerPedId()
        for _ = 1, n do
            v = GetEntityCoords(ped)
        end
        self.sink = v.x
    end }
    cases[#cases + 1] = { "model hash arg", "RequestModel-style string arg IsModelValid(\"adder\")", function(n)
        local v
        for _ = 1, n do
            v = IsModelValid("adder")
        end
        self.sink = v and 1 or 0
    end }
    cases[#cases + 1] = { "model hash arg", "backtick IsModelValid(`adder`)", function(n)
        local v
        for _ = 1, n do
            v = IsModelValid(`adder`)
        end
        self.sink = v and 1 or 0
    end }
    return cases
end

function LuaBench:Run()
    if self.PlayerState.running then
        return
    end
    self.PlayerState.running = true
    LocalPlayer.state:set("luabench", 5, false)
    self.PlayerState.mirror.luabench = 5
    local rows = {}
    local cases = self:SharedCases()
    local extra = self:ClientCases()
    for i = 1, #extra do
        cases[#cases + 1] = extra[i]
    end
    for i = 1, #cases do
        local c = cases[i]
        rows[#rows + 1] = self:Measure(c[1], c[2], c[3], c[4])
        Wait(0)
    end
    local gc = { self:GcPause("incremental"), self:GcPause("generational") }
    self:Report("client (GetGameTimer, 1 ms resolution)", rows, gc)
    LocalPlayer.state:set("luabench", nil, false)
    self.PlayerState.running = false
end

LuaBench:Setup(scriptname, "CL")

RegisterCommand(Config.General.command .. "_cl", function()
    CreateThread(function()
        LuaBench:Run()
    end)
end, false)

AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    LocalPlayer.state:set("luabench", nil, false)
end)
