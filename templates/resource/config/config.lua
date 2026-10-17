sec = 1000
min = 60 * sec

Config = {}

Config.General = {
    debug = false,
    interact = { key = 38, distance = 2.0, draw_distance = 10.0 },
    throttle_ms = { open = 1000, buy = 500 },
    max_amount = 50,
    blip = { enabled = true },
}

Config.Text = {
    prompt_open = "[E] เปิดร้านค้า",
    too_far = "คุณอยู่ไกลจากร้านเกินไป",
    invalid_item = "ไม่พบสินค้านี้",
    invalid_amount = "จำนวนไม่ถูกต้อง",
    not_enough_money = "เงินไม่พอ",
    inventory_full = "กระเป๋าเต็ม",
    busy = "กรุณารอสักครู่",
    purchased = "ซื้อ %s x%d สำเร็จ",
}

