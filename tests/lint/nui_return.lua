local Shop = {}

RegisterNUICallback("sell", function(data, cb)
    if not data.item then
        return
    end
    Shop:Sell(data.item)
    cb({ ok = true })
end)
