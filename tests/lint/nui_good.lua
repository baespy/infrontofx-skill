local Shop = {}

RegisterNUICallback("buy", function(data, cb)
    if not data.item then
        return cb({ ok = false })
    end
    if data.amount > 0 then
        cb({ ok = Shop:Buy(data.item, data.amount) })
    else
        cb({ ok = false })
    end
end)

RegisterNUICallback("close", function(_, reply)
    Shop:Close()
    reply("ok")
end)

function Shop:Total(items)
    local total =
        items.a + items.b
    return total
end
