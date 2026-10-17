Config = Config or {}

for shopId, shop in pairs(Config.Shops) do
    assert(type(shop.label) == "string", ("Shop %s needs a label"):format(shopId))
    assert(type(shop.items) == "table" and #shop.items > 0, ("Shop %s needs items"):format(shopId))
    shop.id = shopId
    shop.itemIndex = {}
    for index, item in ipairs(shop.items) do
        assert(type(item.name) == "string" and item.name ~= "", ("Shop %s item %d needs a name"):format(shopId, index))
        assert(type(item.price) == "number" and item.price >= 0, ("Shop %s item %s has an invalid price"):format(shopId, item.name))
        item.account = item.account or "money"
        shop.itemIndex[item.name] = item
    end
end

