local scriptname = GetCurrentResourceName()

local LuaBench = {
    ServerState = {
        running = false,
        mirror = {},
    },
}

setmetatable(LuaBench, { __index = LuaBenchShared })

function LuaBench:Clock()
    return os.clock() * 1000.0
end

function LuaBench:ServerCases()
    local cases = {}
    local mirror = self.ServerState.mirror
    cases[#cases + 1] = { "global state", "GlobalState.luabench read", function(n)
        local v
        for _ = 1, n do
            v = GlobalState.luabench
        end
        self.sink = v
    end, 2000000 }
    cases[#cases + 1] = { "global state", "mirror table filled by change handler", function(n)
        local v
        for _ = 1, n do
            v = mirror.luabench
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "player list", "GetPlayers() each pass", function(n)
        local t
        for _ = 1, n do
            t = GetPlayers()
        end
        self.sink = #t
    end, 2000000 }
    cases[#cases + 1] = { "player list", "set kept by playerJoining/playerDropped", function(n)
        local t
        local set = self.ServerState.mirror
        for _ = 1, n do
            t = set
        end
        self.sink = t and 1 or 0
    end }
    return cases
end

function LuaBench:Run()
    if self.ServerState.running then
        return
    end
    self.ServerState.running = true
    GlobalState.luabench = 5
    self.ServerState.mirror.luabench = 5
    local rows = {}
    local cases = self:SharedCases()
    local extra = self:ServerCases()
    for i = 1, #extra do
        cases[#cases + 1] = extra[i]
    end
    for i = 1, #cases do
        local c = cases[i]
        rows[#rows + 1] = self:Measure(c[1], c[2], c[3], c[4])
        Wait(0)
    end
    local gc = { self:GcPause("incremental"), self:GcPause("generational") }
    self:Report("server", rows, gc)
    GlobalState.luabench = nil
    self.ServerState.running = false
end

LuaBench:Setup(scriptname, "SV")

RegisterCommand(Config.General.command, function(src)
    if src ~= 0 then
        return
    end
    CreateThread(function()
        LuaBench:Run()
    end)
end, true)

AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    GlobalState.luabench = nil
end)
