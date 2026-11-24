# Debug

หาต้นเหตุก่อนแก้เสมอ แก้ที่อาการโดยไม่รู้ต้นเหตุคือการเดา เปิดตารางอาการกับต้นเหตุในไฟล์ `skills/common/debugging.md` ของ infrontofx ก่อน ถ้าอาการตรงแถวไหน เริ่มจากต้นเหตุในแถวนั้น บั๊กเรื่องกระตุก FPS หรือ network ให้วัด baseline ตามหัวข้อ Measuring ในไฟล์ `skills/common/performance.md` ของ infrontofx ก่อนเปลี่ยนอะไร

## ลำดับ

1. **ทำอาการให้เกิดซ้ำ** เขียนขั้นที่น้อยที่สุดที่ทำให้พัง เกิดฝั่งไหน (client, server, NUI) เกิดทุกครั้งหรือบางครั้ง เริ่มเกิดตั้งแต่เมื่อไร
2. **อ่าน error ตัวแรก** ไม่ใช่ตัวท้าย ตัวที่ตามมามักเป็นผลพวงของตัวแรก
   - client: F8
   - server: server console หรือ Live Console ของ txAdmin หา `SCRIPT ERROR` ตัวแรกหลัง `ensure`
   - NUI: devtools (`nui_devtools` ใน F8 หรือ `http://localhost:13172`) แท็บ Console และ Network
   - error ของ Lua บอก `@<resource>/<ไฟล์>.lua:<บรรทัด>` คัดลอกบรรทัดนั้นตามจริงลงรายงาน
3. **ดูว่าเพิ่งเปลี่ยนอะไร** เทียบกับ backup ล่าสุดด้วย `git -c core.autocrlf=false diff --no-index <backup> <resource>` และเทียบกับ resource [1nfx] ที่ทำงานคล้ายกันแต่ไม่พัง ไล่ทุกจุดที่ต่าง
4. **สร้างวงทดสอบที่เร็ว** ให้ยิงซ้ำได้ด้วยคำสั่งเดียว เลือกตัวที่เร็วที่สุดที่ใช้ได้:
   - `restart <resource>` แล้วทำตามขั้นในข้อ 1
   - คำสั่ง debug ชั่วคราวใน server console หรือ F8 ที่ยิงเส้นทางที่พังโดยตรงแล้ว print ผล
   - สคริปต์ node ที่ยิง payload NUI หรือ HTTP ที่จับไว้ซ้ำ
   - Blender headless ตรวจ asset (`prop-forge/scripts/blender/validate_prop.py`, `map-forge/scripts/blender/inspect_map.py`)
   - ขั้นที่ต้องใช้คนในเกม เขียนเป็นเลขข้อ ข้อละหนึ่งการกระทำ ให้เจ้าของทำแล้ววางผลกลับมา
   วงทดสอบใช้ได้เมื่อรันแล้วเห็นอาการเดิมอย่างน้อยหนึ่งครั้ง
5. **ตั้งสมมติฐาน 3-5 ข้อ** เรียงจากเป็นไปได้มากที่สุด แต่ละข้อเขียนแบบ `ถ้า X เป็นต้นเหตุ เมื่อดูหรือเปลี่ยน Y ต้องเห็น Z` ทดสอบทีละข้อ เปลี่ยนทีละอย่าง
6. **ใส่ตัวพิมพ์ให้น้อยที่สุด** หนึ่งจุดต่อรอยต่อของเส้นทางในหัวข้อถัดไป หาจุดแรกที่ค่าผิด แล้วไล่ย้อนไปหาที่ที่ค่านั้นเกิด
7. **เขียนต้นเหตุก่อนแก้** หนึ่งประโยค `<อาการ> เพราะ <ต้นเหตุ> ที่ <ไฟล์:บรรทัด>` แล้วแก้ตรงต้นเหตุ ห้ามโปรย nil check หรือ `pcall` ไปทั่วเพื่อกลบอาการ ค่าจาก client ตรวจครั้งเดียวที่ server ตรงจุดรับ event พร้อม throttle ไม่ซ้อนหลายชั้น
8. **ปิดงาน** วงทดสอบไม่เกิดอาการแล้ว, ตัวพิมพ์ถูกถอดหมด, lint `0 error(s)` แล้วเขียนต้นเหตุลงรายงาน ถ้าเป็นพฤติกรรมของ engine หรือ native ที่เจอได้ทุกเซิร์ฟ ให้จดลง `memory/` ของ infrontofx ตาม `references/handoff.md`

## เส้นทางที่ต้องไล่

```text
JS fetch -> RegisterNUICallback -> TriggerServerEvent หรือ lib.callback.await -> handler ฝั่ง server -> DB
-> TriggerClientEvent -> handler ฝั่ง client -> SendNUIMessage -> JS
```

จุดแรกที่ค่าผิดบอกว่าต้นเหตุอยู่ก่อนจุดนั้น

## ตัวพิมพ์ชั่วคราว

- อยู่ใต้ `Config.General.debug` เท่านั้น ถ้า resource ยังไม่มี key นี้ ให้เพิ่มชั่วคราวและเอาออกพร้อมตัวพิมพ์ ถ้ามีอยู่แล้ว คืนค่าให้เท่า backup
- ทุกบรรทัดมีป้ายเดียวกันที่ไม่ซ้ำกับอะไรในโปรเจกต์ เช่น `dbg7f3a` จะได้ค้นเจอครบตอนถอด
- if เขียนหลายบรรทัดตามกฎ lint

```lua
if Config.General.debug then
    print("[dbg7f3a]", "SV:claim", src, json.encode(data))
end
```

ดูค่า state bag ด้วยคำสั่งชั่วคราวที่จำกัดสิทธิ์ (ป้ายเดียวกัน ถอดพร้อมกัน) ฝั่ง client ใช้ `LocalPlayer.state`, entity ใช้ `Entity(entity).state`, ค่ากลางใช้ `GlobalState`

```lua
RegisterCommand("dbg7f3a", function(src, args)
    ModuleServer:DebugState(tonumber(args[1]) or src)
end, true)

function ModuleServer:DebugState(target)
    print("[dbg7f3a]", target, json.encode(Player(target).state.inZone))
end
```

ถอดแล้วต้องค้นไม่เจอ:

```powershell
Get-ChildItem -LiteralPath "<project>\resources\[resources]\[1nfx]\<resource>" -Recurse -File -Include *.lua, *.js | Select-String -SimpleMatch "dbg7f3a"
```

## กฎสามครั้ง

1. นับเฉพาะการแก้ที่ลงไฟล์แล้ว ทดสอบแล้ว อาการยังอยู่
2. ครบสามครั้ง หยุดแพตช์ คืนไฟล์ที่ลองแก้ให้กลับเป็นสภาพก่อนเริ่มลอง
3. เขียนสั้นๆ ว่าการล้มสามครั้งบอกอะไร เช่น แก้ผิดชั้น, race ระหว่าง await, ลำดับ start ใน `server.cfg`, ข้อมูลใน DB ไม่ตรงกับที่โค้ดคิด หรือโครงของส่วนนั้นผิดตั้งแต่แรก
4. เลือกทางเดียว: ออกแบบส่วนนั้นใหม่ตาม `references/plan.md` หรือรายงานเจ้าของว่าติดตรงไหนพร้อมหลักฐาน กรณีนี้ถือว่าติดจริง ถามได้
5. อาการของ stream, prop หรือแมพ (ตกพื้น texture ดำ normal กลับด้าน กระตุกตอนโหลด) ให้สร้างหรือใช้ตัวตรวจ headless ที่ล้มกับอาการนั้นก่อนแก้รอบที่สอง

## เครื่องมือ

| เครื่องมือ | ใช้หาอะไร | คำสั่ง |
| --- | --- | --- |
| F8 | error ฝั่ง client และผล print | อ่าน error ตัวแรก |
| server console, txAdmin | error ฝั่ง server ลำดับ start การล้างตอน stop | `refresh`, `ensure <resource>`, `restart <resource>` |
| NUI devtools | error ของ JS, payload เข้าออก, timer ที่ค้าง | `nui_devtools` |
| resmon | ms และ memory ฝั่ง client ต่อ resource | `resmon 1` |
| profiler | spike ราย thread ไฟล์ และบรรทัด | `profiler record 500` แล้ว `profiler view` หรือ `profiler saveJSON <file>` |
| restart สองรอบ | ของซ้ำเพราะไม่ล้าง (blip, point, prop, handler) | `restart <resource>` สองครั้ง แล้วนับของในเกม |
| state bag | ค่าที่ sync จริง | คำสั่งชั่วคราว `dbg7f3a` ด้านบน |
| diff กับ backup | เพิ่งเปลี่ยนอะไร | `git -c core.autocrlf=false diff --no-index --stat <backup> <resource>` |
| lint | block ไม่ปิด comment หลงเหลือ กฎโครงสร้าง | ไฟล์ `scripts/lint-resource.mjs` ของ infrontofx |

## อาการที่ไม่อยู่ในตารางของ infrontofx

| อาการ | ต้นเหตุที่พบบ่อย |
| --- | --- |
| `source` เป็นคนอื่นหรือ nil หลัง `Wait` หรือ await | ไม่ได้เก็บ `local src = source` เป็นบรรทัดแรกของ handler |
| `xPlayer` เป็น nil หลัง await | ผู้เล่นออกระหว่างรอ ต้องดึงใหม่และเช็กหลังทุก yield |
| handler ทำงานสองรอบหลัง `restart` | ลงทะเบียนซ้ำใน loop หรือใน event อื่น หรือไม่ล้างตอน stop |
| client ไม่เห็นค่าใหม่ใน state bag | แก้ table ข้างในโดยไม่ set key ระดับบนใหม่ |
| export ใช้ไม่ได้หลัง provider restart | เก็บ reference ของ export ไว้ตอนโหลด ต้องเรียกตอนใช้ |
| ปกติตอนคนน้อย พังหรือกระตุกตอนคนเยอะ | query ต่อคนใน loop, broadcast ถึง `-1` ถี่, ตาราง `[src]` ไม่ถูกล้างใน `playerDropped` |
