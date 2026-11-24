local Shop = {}

RegisterNUICallback("buy", function(data, cb)
    Shop:Buy(data)
    cb({ ok = true })
    cb({ ok = false })
end)
