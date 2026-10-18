Config = {}

Config.General = {
    debug = false,
    interact = { key = 38, distance = 2.0, draw_distance = 10.0 },
    throttle_ms = { open = 1000, buy = 500 },
    max_amount = 50,
    blip = { enabled = true },
}

Config.Text = {
    prompt_open = "[E] Open shop",
    too_far = "You are too far from the shop",
    invalid_item = "Item not found",
    invalid_amount = "Invalid amount",
    not_enough_money = "Not enough money",
    inventory_full = "Inventory is full",
    busy = "Please wait",
    purchased = "Purchased %s x%d",
}
