# CLAUDE.md - infrontofx

repo นี้ (และ workspace FiveM ที่ติดตั้งไว้) ใช้ `infrontofx` เป็นมาตรฐานเขียน resource FiveM Lua และ NUI/DUI อ่าน `SKILL.md` ก่อนแล้วเปิดไฟล์ที่ชี้ไปตามงาน

## กฎที่ห้ามผ่อน

1. หัวไฟล์ client/server ทุกไฟล์: `local scriptname = GetCurrentResourceName()` (ถ้าไฟล์นั้นใช้) และตารางโมดูลเดียว `local Name = {}` หรือ global ชื่อโมดูลเดียวถ้ามีหลายไฟล์ framework เรียกผ่าน global `Core` จาก `shared_script "@1nfx_core/imports.lua"` ไม่เรียก `es_extended` ตรงๆ
2. OOP เท่านั้น: ทุกฟังก์ชันเป็น method `function Module:Method()` ไม่มี `local function` ระดับไฟล์ ไม่มีค่าคงที่ระดับไฟล์ (`local X_Y = 1`) ไม่ย่อชื่อ resource เป็นตัวแปร event handler และ thread เรียก method เท่านั้น
3. ไม่มีตาราง `FC` และไม่มี `config/function/` เขียนการเรียก export/event ตรงๆ ใน method ของ `core/`
4. `Config` อยู่ใน `config/config.lua` (`Config.General`, `Config.Text`) อ่านตรงๆ ไม่ย่อเป็น local ระดับไฟล์
5. ไม่มี comment ในโค้ดทุกภาษา (Lua, JS, CSS, HTML)
6. event: `scriptname .. ":SV:action"` / `scriptname .. ":CL:action"` บรรทัดแรกของ handler ฝั่ง server คือ `local src = source`
7. ox_lib ใช้ได้กับ callback, points, zones, cache, table, array, cron, dui, requestModel/AnimDict/NamedPtfxAsset, addKeybind ห้าม `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI` ใช้ UI export ของเซิร์ฟเวอร์แทน
8. server ตัดสินทุกค่า (ของ เงิน ราคา รางวัล cooldown ระยะ routing bucket) ตรวจ payload, throttle, กันซ้ำ
9. NUI: `{ action, data }`, handshake `uiReady`, เรียก `cb` ครั้งเดียวต่อ callback, ใช้ `textContent`, ย่อขยายด้วย `--px` บนกรอบ 1920x1080
10. ล้างให้ครบใน `onResourceStop` และ `playerDropped`
11. secret อยู่ในไฟล์ฝั่ง server เท่านั้น ไม่ลงใน repo