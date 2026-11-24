LuaBenchShared = {
    sink = 0,
}

function LuaBenchShared:Measure(group, variant, fn, cap)
    local limit = math.min(cap or Config.General.max_ops, Config.General.max_ops)
    local n = 1000
    local elapsed = 0.0
    while true do
        collectgarbage("collect")
        local start = self:Clock()
        fn(n)
        elapsed = self:Clock() - start
        if elapsed >= Config.General.target_ms or n >= limit then
            break
        end
        local grow = elapsed > 0.5 and math.ceil(n * Config.General.target_ms * 1.1 / elapsed) or n * 8
        n = math.min(limit, math.max(n * 2, grow))
    end
    return { group = group, variant = variant, n = n, ms = elapsed, ns = elapsed * 1000000 / n }
end

function LuaBenchShared:SharedCases()
    local cases = {}
    local array = {}
    for i = 1, 1000 do
        array[i] = i
    end
    local payload = { action = "updateHud", data = { health = 87, armour = 40, hunger = 63.5, thirst = 71.25, voice = 2, talking = false } }
    local encoded = json.encode(payload)
    local holder = { PlayerState = { hud = { health = 87 } } }
    local reuse = {}

    cases[#cases + 1] = { "loop baseline", "empty numeric for", function(n)
        for _ = 1, n do
        end
    end }
    cases[#cases + 1] = { "native lookup", "global GetGameTimer() each call", function(n)
        for _ = 1, n do
            GetGameTimer()
        end
    end }
    cases[#cases + 1] = { "native lookup", "local getTimer = GetGameTimer in method", function(n)
        local getTimer = GetGameTimer
        for _ = 1, n do
            getTimer()
        end
    end }
    cases[#cases + 1] = { "hash", "GetHashKey(\"WEAPON_PISTOL\")", function(n)
        local h = 0
        for _ = 1, n do
            h = GetHashKey("WEAPON_PISTOL")
        end
        self.sink = h
    end }
    cases[#cases + 1] = { "hash", "backtick `WEAPON_PISTOL`", function(n)
        local h = 0
        for _ = 1, n do
            h = `WEAPON_PISTOL`
        end
        self.sink = h
    end }
    cases[#cases + 1] = { "json", "json.encode(hud payload) each send", function(n)
        local s
        for _ = 1, n do
            s = json.encode(payload)
        end
        self.sink = #s
    end }
    cases[#cases + 1] = { "json", "reuse encoded string when unchanged", function(n)
        local s
        for _ = 1, n do
            s = encoded
        end
        self.sink = #s
    end }
    cases[#cases + 1] = { "event pack", "msgpack.pack_args per target", function(n)
        local s
        for _ = 1, n do
            s = msgpack.pack_args(payload)
        end
        self.sink = #s
    end }
    cases[#cases + 1] = { "event pack", "pack once, reuse bytes", function(n)
        local s = msgpack.pack_args(payload)
        local t
        for _ = 1, n do
            t = s
        end
        self.sink = #t
    end }
    cases[#cases + 1] = { "alloc", "new table per iteration", function(n)
        local t
        for i = 1, n do
            t = { x = i, y = i, z = i }
        end
        self.sink = t.x
    end }
    cases[#cases + 1] = { "alloc", "reuse one table", function(n)
        local t = reuse
        for i = 1, n do
            t.x, t.y, t.z = i, i, i
        end
        self.sink = t.x
    end }
    cases[#cases + 1] = { "table reuse x16", "new scratch table per pass", function(n)
        local t
        for _ = 1, math.max(1, n // 16) do
            t = {}
            for k = 1, 16 do
                t[k] = k
            end
        end
        self.sink = #t
    end }
    if table.wipe then
        cases[#cases + 1] = { "table reuse x16", "table.wipe(scratch) per pass", function(n)
            local t = {}
            for _ = 1, math.max(1, n // 16) do
                table.wipe(t)
                for k = 1, 16 do
                    t[k] = k
                end
            end
            self.sink = #t
        end }
    end
    cases[#cases + 1] = { "presize x64", "grow {} by appends", function(n)
        local t
        for _ = 1, math.max(1, n // 64) do
            t = {}
            for k = 1, 64 do
                t[k] = k
            end
        end
        self.sink = #t
    end }
    if table.create then
        cases[#cases + 1] = { "presize x64", "table.create(64, 0) then fill", function(n)
            local t
            for _ = 1, math.max(1, n // 64) do
                t = table.create(64, 0)
                for k = 1, 64 do
                    t[k] = k
                end
            end
            self.sink = #t
        end }
    end
    cases[#cases + 1] = { "event name", "scriptname .. \":SV:name\" per call", function(n)
        local s
        local prefix = self.prefix
        for _ = 1, n do
            s = prefix .. ":SV:benchName"
        end
        self.sink = #s
    end }
    cases[#cases + 1] = { "event name", "cached name in module field", function(n)
        local s
        for _ = 1, n do
            s = self.cachedName
        end
        self.sink = #s
    end }
    cases[#cases + 1] = { "array walk x1000", "pairs", function(n)
        local sum = 0
        for _ = 1, math.max(1, n // 1000) do
            for _, v in pairs(array) do
                sum += v
            end
        end
        self.sink = sum
    end }
    cases[#cases + 1] = { "array walk x1000", "ipairs", function(n)
        local sum = 0
        for _ = 1, math.max(1, n // 1000) do
            for _, v in ipairs(array) do
                sum += v
            end
        end
        self.sink = sum
    end }
    cases[#cases + 1] = { "array walk x1000", "numeric for", function(n)
        local sum = 0
        for _ = 1, math.max(1, n // 1000) do
            for i = 1, #array do
                sum += array[i]
            end
        end
        self.sink = sum
    end }
    cases[#cases + 1] = { "distance", "#(a - b) on vector3", function(n)
        local a, b = vector3(10.0, 20.0, 30.0), vector3(13.0, 24.0, 30.0)
        local d = 0.0
        for _ = 1, n do
            d = #(a - b)
        end
        self.sink = d
    end }
    cases[#cases + 1] = { "distance", "math.sqrt on {x,y,z} tables", function(n)
        local a, b = { x = 10.0, y = 20.0, z = 30.0 }, { x = 13.0, y = 24.0, z = 30.0 }
        local d = 0.0
        for _ = 1, n do
            local dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
        end
        self.sink = d
    end }
    cases[#cases + 1] = { "field access", "self.PlayerState.hud.health", function(n)
        local v = 0
        for _ = 1, n do
            v = holder.PlayerState.hud.health
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "field access", "local hud pulled once", function(n)
        local v = 0
        local hud = holder.PlayerState.hud
        for _ = 1, n do
            v = hud.health
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "closure", "new closure per iteration", function(n)
        local f
        for i = 1, n do
            f = function()
                return i
            end
        end
        self.sink = f()
    end }
    cases[#cases + 1] = { "closure", "one method reused", function(n)
        local f
        for _ = 1, n do
            f = self.Measure
        end
        self.sink = f and 1 or 0
    end }
    cases[#cases + 1] = { "pcall", "direct call", function(n)
        local f = math.abs
        local v = 0
        for i = 1, n do
            v = f(-i)
        end
        self.sink = v
    end }
    cases[#cases + 1] = { "pcall", "pcall(fn, ...)", function(n)
        local f = math.abs
        local ok, v = true, 0
        for i = 1, n do
            ok, v = pcall(f, -i)
        end
        self.sink = ok and v or 0
    end }
    cases[#cases + 1] = { "export", "exports[res]:Echo(1) each call", function(n)
        local res = self.resource
        for i = 1, n do
            exports[res]:Echo(i)
        end
    end, 200000 }
    cases[#cases + 1] = { "export", "cached exports[res] proxy", function(n)
        local ex = exports[self.resource]
        for i = 1, n do
            ex:Echo(i)
        end
    end, 200000 }
    cases[#cases + 1] = { "export", "direct method call", function(n)
        for i = 1, n do
            self:Echo(i)
        end
    end }
    cases[#cases + 1] = { "local event", "TriggerEvent to 1 handler", function(n)
        local name = self.pingOne
        for i = 1, n do
            TriggerEvent(name, i)
        end
    end, 200000 }
    cases[#cases + 1] = { "local event", "TriggerEvent to 5 handlers", function(n)
        local name = self.pingFive
        for i = 1, n do
            TriggerEvent(name, i)
        end
    end, 200000 }
    cases[#cases + 1] = { "local event", "direct method call", function(n)
        for i = 1, n do
            self:Echo(i)
        end
    end }
    cases[#cases + 1] = { "thread", "CreateThread per job", function(n)
        for _ = 1, n do
            CreateThread(self.noop)
        end
    end, 20000 }
    cases[#cases + 1] = { "thread", "queue job in a table", function(n)
        local q = {}
        for i = 1, n do
            q[i] = self.noop
        end
        self.sink = #q
    end, 20000 }
    return cases
end

function LuaBenchShared:Echo(v)
    return v
end

function LuaBenchShared:Setup(resource, side)
    self.resource = resource
    self.prefix = resource
    self.cachedName = resource .. ":SV:benchName"
    self.pingOne = resource .. ":" .. side .. ":benchPingOne"
    self.pingFive = resource .. ":" .. side .. ":benchPingFive"
    self.noop = function()
    end
    exports("Echo", function(v)
        return v
    end)
    AddEventHandler(self.pingOne, function()
    end)
    for _ = 1, 5 do
        AddEventHandler(self.pingFive, function()
        end)
    end
end

function LuaBenchShared:GcPause(mode)
    collectgarbage("collect")
    collectgarbage(mode)
    local keep = {}
    local worst, total = 0.0, 0.0
    for b = 1, Config.General.gc_batches do
        local start = self:Clock()
        for i = 1, Config.General.gc_batch_size do
            local t = { b, i, tostring(i) }
            if i % 50 == 0 then
                keep[#keep + 1] = t
            end
        end
        if #keep > 2000 then
            keep = {}
        end
        local spent = self:Clock() - start
        total += spent
        if spent > worst then
            worst = spent
        end
    end
    collectgarbage("incremental")
    collectgarbage("collect")
    return { group = "gc " .. mode, variant = ("%d batches x %d allocs"):format(Config.General.gc_batches, Config.General.gc_batch_size), total = total, worst = worst }
end

function LuaBenchShared:Report(side, rows, gc)
    print(("^5luabench %s^7  (%s, target %d ms per case)"):format(side, self.resource, Config.General.target_ms))
    local base = {}
    for i = 1, #rows do
        local r = rows[i]
        if not base[r.group] then
            base[r.group] = r.ns
        end
        local ratio = base[r.group] > 0 and r.ns / base[r.group] or 1
        print(("%-20s %-44s %10.1f ns/op  x%-6.2f n=%d"):format(r.group, r.variant, r.ns, ratio, r.n))
    end
    for i = 1, #gc do
        local g = gc[i]
        print(("%-20s %-44s total %8.2f ms  worst batch %6.3f ms"):format(g.group, g.variant, g.total, g.worst))
    end
end
