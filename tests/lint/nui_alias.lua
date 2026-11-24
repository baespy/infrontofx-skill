local Shop = {}

RegisterNUICallback("close", function(data, cb)
    local reply = cb
    Shop:Close()
end)
