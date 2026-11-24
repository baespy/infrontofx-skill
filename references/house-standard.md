# House standard (full text)

The owner's full rule text, examples and lessons, moved here from `SKILL.md` on 2026-11-24. `SKILL.md` keeps the short form under Hard rules and loads first; this file is the long form. When a rule changes, update both.

## Principles

1. เขียนใหม่ด้วยวิธีที่ดีที่สุดและลื่นที่สุด โดยพฤติกรรมที่ผู้เล่นเห็นต้องเท่าเดิม
2. ทุกบทเรียนและคำสั่งใหม่ของเจ้าของต้องถูกบันทึกลง skill
3. แยกสคริปที่รวมกันและมีระบบซ้ำกัน โดยการทำงานต้องเหมือนเดิม
4. ไม่มี comment ในโค้ด
5. ไม่ใช้โฟลเดอร์ `config/function` และไม่มีตาราง `FC` เขียนลงใน `core/` โดยตรง
6. ห้ามตั้งตัวแปรย่อชื่อ resource, ห้ามมี `local function` ระดับไฟล์, ต้องเป็น OOP (method ของโมดูล)
7. ห้ามมีค่าคงที่ระดับไฟล์ เขียนค่าจริงตรงจุดที่ใช้
8. optimize ทุก resource โดยคงการทำงานเดิม
9. secret ต้องอยู่ฝั่ง server เท่านั้น ไม่ส่งให้ client
10. ช่องโหว่และจุดช้าที่ตรวจยืนยันจากโค้ดแล้ว แก้ได้เลยไม่ต้องถาม แล้วรายงานหลังแก้พร้อมพฤติกรรมที่เปลี่ยน ยกเว้นเรื่องที่ต้องมีข้อมูลใหม่หรือต้องตัดสินใจเชิงดีไซน์ (เจ้าของสั่ง 2026-11-23)
11. ใช้ sub agent พร้อมกันไม่เกิน 1-2 ตัว ห้ามให้ agent แตก agent ย่อยเอง และห้าม workflow ขนาดใหญ่ เพราะใช้ usage limit หมดกลางงาน (เจ้าของสั่ง 2026-11-23)

## Per-resource steps

1. อ่านทุกไฟล์ของ resource และ grep หาผู้ใช้ภายนอก: ชื่อ resource, exports, ชื่อ event, NUI callback
2. สำรองไปที่ `_backup/<YYYY-MM-DD>/<resource>` ก่อนแก้ (โปรเจกต์ไม่มี git)
3. เขียนใหม่ตามกฎด้านล่าง ห้ามเปลี่ยนสิ่งที่คนอื่นเรียกใช้: ชื่อ export, ชื่อ event, key ใน `Config`, รูปแบบ payload ของ NUI, ชื่อตาราง/คอลัมน์ DB
4. optimize ตามหัวข้อ "Optimize"
5. ลบของตาย (ไฟล์ที่ไม่ถูกโหลด, callback ที่ไม่มีใครเรียก, โหมด preview/mock) หลังยืนยันด้วย grep แล้วเท่านั้น
6. ตรวจซ้ำ: ทุก event/export/callback เดิมยังอยู่ครบ, `\bFC\b` = 0, `^local function` = 0, ไม่มี `--`, จำนวน `function|if|do|repeat` เท่ากับ `end|until`, วงเล็บเปิดปิดเท่ากัน
7. อัปเดตบันทึกความคืบหน้า แล้วทำตัวถัดไปต่อ

## File layout

```
fxmanifest.lua
config/config.lua     ค่าที่เจ้าของเซิร์ฟปรับ
core/cl_main.lua
core/sv_main.lua
```

- resource ใหญ่ให้แตก `core/` ตามหน้าที่ (`cl_<feature>.lua`, `sv_<feature>.lua`) ไฟล์ละเรื่องเดียว
- manifest: `lua54 "yes"`, รายการแรกใน `shared_scripts` คือ `"@1nfx_lib/init.lua"` ตามด้วย `"@1nfx_core/imports.lua"` (แทนที่ `ox_lib`, `er_lib`, `cfxlua-require`), `files` ใส่เฉพาะไฟล์ที่หน้าเว็บอ้างถึงจริง ห้ามมี `dependencies`/`dependency` และห้ามมี `escrow_ignore` ลำดับ start ตั้งใน `server.cfg`
- ตรรกะบริสุทธิ์ที่ใช้ร่วมกันทั้ง client และ server จริงๆ (เช่น คำนวณโซน, แปลงเวลา, codec, normalize สูตร) ให้แยกไว้ใน `core/sh_<domain>.lua` ภายใต้ `shared_scripts` เป็น `<Module>Shared = {}` แล้วผูก `setmetatable(Module, { __index = <Module>Shared })` ทั้งสองฝั่ง ห้ามก๊อปไฟล์เหมือนกันเป็นคู่แฝด `cl_<x>.lua` + `sv_<x>.lua` และห้ามเอา helper ที่ใช้แค่ฝั่งเดียวไปใส่ `sh_*.lua`
- ห้ามแยกตารางเทียบค่าหรือ helper เล็กๆ ออกเป็น resource แยกต่างหากเมื่อโมดูลหลักมีอยู่แล้ว และห้าม `ensure <resource>` รายตัวซ้ำใน `server.cfg` เมื่ออยู่ในโฟลเดอร์ `[category]` ที่ถูก `ensure` แล้ว เว้นแต่ต้องบังคับลำดับเปิดก่อนหมวดนั้นจริงๆ
- export ที่ประกาศด้วย `exports("name", fn)` ในโค้ดแล้ว ไม่ต้องซ้ำใน manifest

## OOP only

ห้ามเขียนแบบนี้:

```lua
local TEXTUI = "1nfx_textui"
local HEAD_BONE = 31086

local function showHold(options)
    return exports[TEXTUI]:ShowHold(options)
end
```

ให้เขียนแบบนี้:

```lua
local Airdrop = {
    ServerState = {},
    PlayerState = {},
}

function Airdrop:Notify(label, notifyType)
    TriggerEvent("pNotify:SendNotification", { text = label, type = notifyType or "info" })
end

function Airdrop:Open()
    if exports["1nfx_processbar"]:getIsDoingAction() then
        return
    end
    self:Notify("...", "error")
end
```

- ห้ามตั้งตัวแปรย่อชื่อ resource เขียนชื่อเต็มตรงจุดที่เรียก
- ห้ามมีค่าคงที่ระดับไฟล์ เช่น `local REFRESH_INTERVAL = 1000` ให้เขียน `Wait(1000)` ตรงจุดที่ใช้
- ห้ามย่อ Config ระดับไฟล์ เขียน `Config.General.x` ตรงจุดที่ใช้ ถ้าใช้ถี่ใน loop ให้ดึงเป็น local ภายใน method นั้น
- ตารางข้อมูลที่ใช้ร่วมหลาย method เป็น field ของโมดูล (`Module.Kinds = {...}`) ไม่ใช่ `local` ระดับไฟล์
- บนหัวไฟล์มี `local` ได้แค่: ตัวแปร framework, `scriptname`, ตารางโมดูล
- ห้ามมี `local function` ระดับไฟล์ ทุกฟังก์ชันเป็น method เรียกด้วย `self:` หรือชื่อโมดูล
- ตัวห่อบรรทัดเดียว (เรียก export หรือ event ตรงๆ) ไม่ต้องมี เขียนคำสั่งจริงตรงที่ใช้
- ทำเป็น method เมื่อมีตรรกะจริง (pcall, เช็ก nil, เช็ก `GetResourceState`, คำนวณ) และใช้มากกว่าหนึ่งที่
- `local function` ซ้อนใน method (closure) ใช้ได้
- โมดูลหลักเป็น table เดียว มี `ServerState` (ข้อมูลจาก server) กับ `PlayerState` (สถานะฝั่งตัวเอง)
- event handler และ thread เป็นแค่ตัวเรียก method ไม่ใส่ตรรกะไว้ใน handler
- ใน callback ของ `lib.points` (`nearby`, `onEnter`, `onExit`) `self` คือตัว point ไม่ใช่โมดูล ให้เรียกผ่านชื่อโมดูล

## Lua rules

- ไม่มี comment
- `local scriptname = GetCurrentResourceName()` และชื่อ event เป็น `scriptname .. ":SV:<name>"` / `scriptname .. ":CL:<name>"`
- global มีได้แค่ `Config` และตารางโมดูลของ resource เท่านั้น (`Module` / `ModuleServer` และ `<Module>Shared` ใน `core/sh_*.lua` กรณีมีตรรกะร่วมสองฝั่ง)
- ประกาศ `Config = {}` ครั้งเดียวใน `config/config.lua` แล้วกำหนดแต่ละตารางย่อยตรงๆ (`Config.General = { ... }`, `Config.Text = { ... }`) ห้ามเขียน `Config.X = Config.X or {}`, `if not Config.X then Config.X = {} end` หรือ loop รวมค่า default ซ้อนในไฟล์ config และต้องระบุไฟล์ config ใน manifest เรียงตามลำดับโหลดจริง ไม่ใช้ glob
- ห้ามทิ้ง key หรือไฟล์ตายใน `config/` ที่ `core/` ไม่ได้อ่านจริง และห้ามสร้างไฟล์ config แยกสำหรับค่า tuning ภายในหรือโหมดจำลองที่ไม่ได้ให้เจ้าของเซิร์ฟปรับจริง
- ห้ามมีตัวแปร global ของสถานะ เช่น `itemCount = itemCount or {}` หรือ `scriptname = GetCurrentResourceName()` ในไฟล์ config ให้เก็บเป็น field ของโมดูล (`Module.PlayerState.itemCount`) และให้แต่ละไฟล์ที่ใช้ประกาศ `local scriptname` เอง
- ตรวจค่าคงที่ระดับไฟล์ด้วย regex `(?m)^local [A-Z][A-Z0-9_]* = ` ต้องไม่เจอ
- ดึง `xPlayer` ครั้งเดียวต่อหนึ่งงาน แล้วเช็ก nil ก่อนใช้
- ลบ fallback หลายชั้นที่ไม่จำเป็น เหลือทางเดียวที่ framework ของเซิร์ฟมีจริง
- server ตรวจเองเสมอ (ตำแหน่ง, ของในตัว, cooldown) ไม่เชื่อค่าที่ client ส่งมา และ throttle event ที่ client ยิงได้
- โค้ดที่ใช้ `+=` หรือ `//` ต้องมี `lua54 "yes"` ใน manifest

## Optimize

ผลลัพธ์ที่ผู้เล่นเห็นต้องเหมือนเดิม ถ้า optimize แล้วพฤติกรรมเปลี่ยน ต้องเขียนในรายงาน

Client:

- ใช้ `lib.zones` / `lib.points` / `lib.grid` (stationary-skip + กำลังสองระยะ) และ `lib.spawn` (`prop`, `ped`, `blip`, `pointProp`, `pointPed`, `clearAll`) แทน loop วัดระยะและจัดการ entity เอง
- `Wait(0)` มีได้เฉพาะตอนที่ต้องใช้จริง (อยู่ในโซน, เปิดเมนู, ต้อง disable ปุ่ม) นอกนั้นใช้ช่วงเวลาที่ยาวที่สุดที่ยังได้ผลเท่าเดิม
- งานหนักใน loop ต่อเฟรม (หาของในตัว, นับ entity, เรียก export) ต้องมี interval คุม
- ส่ง NUI เฉพาะตอนค่าเปลี่ยน และห้ามส่งข้อมูลเดียวกันจากสอง loop
- ห้ามสร้าง thread ใหม่ทุกครั้งที่ส่ง NUI
- ใช้ `cache` ของ `1nfx_lib` (`ped`, `coords`, `vehicle`, `seat`, `weapon`, `playerId`, `serverId`, `pauseActive`) แทนการเรียก native ซ้ำ
- ค่าที่ไม่เปลี่ยนใน loop (config, label, hash) ดึงมาเก็บนอก loop
- เปรียบเทียบระยะด้วยค่ากำลังสอง ไม่ใช้ `#(a - b)` ใน loop ถี่
- โหลด model/anim แล้วต้อง `SetModelAsNoLongerNeeded` / `RemoveAnimDict` และลบ entity เมื่อออกจากพื้นที่หรือ resource หยุด

Server:

- ไม่ query DB ใน loop ใช้ cache ในหน่วยความจำแล้วเขียนกลับเป็นช่วง
- รวม `while true` หลายตัวเป็น loop กลางตัวเดียว ใช้ตัวนับต่อหัวข้อ แล้วพักยาวเมื่อไม่มีงาน (`next(sessions)` เป็น nil) ปลุกด้วย `promise` จากจุดที่สร้าง state
- เรียกแต่ละ tick ของ loop รวมผ่าน `pcall` และ print ชื่อ tick เมื่อล้มเหลว
- broadcast ถึงทุกคนใช้ `TriggerClientEvent(event, -1, ...)` และรวมเป็นรอบ (debounce)
- request/response ใช้ 1-packet `lib.callback` แทนคู่ event ไป-กลับ และใช้ `lib.guard` (`throttle`, `isThrottled`, `lock`/`unlock`/`withLock`, `toAmount`, `isNear`) กับโครงสร้างข้อมูล (`lru`, `heap`, `ringbuffer`) ของ `1nfx_lib`
- ตารางต่อผู้เล่นต้องล้างใน `playerDropped`
- ก่อนแก้เรื่อง FPS/network ให้วัดก่อนเสมอ (`resmon`, ตัวนับ network ต่อ resource) แล้วเทียบก่อน-หลังในสถานการณ์เดียวกัน

ไฟล์:

- เอารูป เสียง svg ที่ไม่มีใครอ้างออกจาก `files`
- ถ้าชื่อรูปมาจาก `Config` ที่เจ้าของแก้ได้ ให้คง glob ไว้ ห้ามเปลี่ยนเป็นรายชื่อตายตัว

## Edit levels

- resource เล็ก (core รวมไม่เกินราว 30KB): เขียนไฟล์ core ใหม่ทั้งไฟล์
- resource ใหญ่ที่อยู่ในโครงมาตรฐานแล้ว: ไม่พิมพ์ตรรกะใหม่ทั้งหมด ย้ายของเดิมเข้า core เป็น method, ลบของตาย, optimize จุดที่ช้าหรือผิดจริง แล้วระบุในรายงานว่าส่วนไหนคงเดิม
- resource ที่ถูก obfuscate ห้ามแตะทั้งไฟล์และ manifest

## FC migration

1. หา `FC.*` ที่ core เรียกจริงด้วย regex `\bFC\.\w+` ตัวที่ไม่มีใครเรียก ลบทิ้ง
2. ตัวห่อบรรทัดเดียว แทนที่จุดเรียกด้วยคำสั่งจริง ตัวที่มีตรรกะ ย้ายเป็น method ของโมดูล
3. ก่อนตั้งชื่อ method เช็กว่าไม่ชนกับ method ที่มีอยู่
4. เวลาแทนที่ด้วย regex ใช้ `(?<![\w.:])name\(` กันไปโดนชื่อ field หรือ method อื่น
5. ลบโฟลเดอร์ `config/function` และเอาออกจาก `fxmanifest.lua`

## Field lessons

- ก่อนลบ callback/event/export ให้ grep ทั้งโปรเจกต์ รวมไฟล์ build ของหน้าเว็บและไฟล์ test
- เทียบรายการ `RegisterNetEvent` / `AddEventHandler` / `RegisterNUICallback` / `lib.callback.register` / `RegisterCommand` / `exports(` กับ backup ก่อนและหลังแก้ ตรวจว่า method ที่ถูกเรียกมีนิยามครบ
- ถ้า `local function` ถูกประกาศก่อนตารางโมดูล ให้ย้ายตารางขึ้นบนสุดก่อน ห้ามใส่ `local X = {}` ซ้ำ เพราะการ assign ตารางทีหลังจะทับ method ทิ้ง
- `function Name() ... end` ตามด้วย `exports("Name", Name)` แปลงเป็น `exports("Name", function(...) ... end)` ได้ เพื่อไม่ทิ้ง global
- เปลี่ยน global ชื่อโมดูลเป็น `local` ได้เมื่อโมดูลมีไฟล์เดียวและไม่มีใครอ้างข้าม resource (grep `loadfile` และชื่อไฟล์ core ก่อน)
- JS export ที่ Lua เรียกผ่าน `exports[scriptname]` ห้ามเปลี่ยนชื่อ
- การนับ keyword ตอนตรวจ ต้องตัด string literal และ comment ออกก่อน
- แก้เป็นชุดด้วยสคริปต์ที่ `Replace` แบบ exact และ throw ถ้าไม่พบหรือจำนวนไม่ตรง ก่อนเขียนไฟล์ให้เช็กว่าข้อความไม่ใช่ null
- ไฟล์ Lua อาจมีทั้ง CRLF และ LF ปนกัน ให้ normalize เป็น LF ก่อน `.Replace` ข้อความหลายบรรทัด
- ใน PowerShell: path ที่มี `[ ]` ใช้ `-LiteralPath` เสมอ, ห้ามตั้งชื่อฟังก์ชันตัวช่วยชนกับ alias (`rd`, `mv`, `R`), ใช้ `[IO.File]::WriteAllText(path, text, [Text.UTF8Encoding]::new($false))` เพื่อไม่ให้มี BOM
- ก่อนเปลี่ยนไฟล์ stream ที่โหลดอัตโนมัติ (`stream/`) ไม่ต้องใส่ใน `files`
- ระบบที่ซ้ำกันหลาย resource (culling, กราฟิก/FPS) ให้มีเจ้าของที่เดียว ก่อนเพิ่มระบบ sync ใหม่ให้ grep หาระบบเดิมก่อน

- สถานะที่ต้องหายเมื่อออกเกม (เช่น เลือกโรงเรียน/ทีมต่อรอบ) ไม่ต้องลง DB เก็บใน `ServerState` + `Player(src).state` ล้างใน `1nfx_core:playerLoaded` และตอน resource start ให้อ่านคืนจาก `Player(src).state` ของผู้เล่นที่ออนไลน์อยู่ จะได้ไม่หายตอนรีสตาร์ต resource
- `theme/ui.js` ที่ใช้ร่วมทุก UI มีแค่ `BillieSound.click`/`hover` เสียงเฉพาะ resource (tick, reveal) ต้องเล่นเองใน class ของหน้านั้น เรียก method ที่ไม่มีจะ throw แล้ว animation ค้าง
- `lib.callback.register(name, function(src, ...))` ได้ `src` เป็นพารามิเตอร์ ไม่ต้องมี `local src = source` (กฎนี้ใช้กับ `RegisterNetEvent` เท่านั้น)
- `provide "x"` ใน manifest ไม่ได้ทำให้ `exports["x"]:fn()` ใช้ได้ เพราะ Lua export ผูกกับชื่อ resource จริงผ่าน event `__cfx_export_<resource>_<name>` ถ้าต้องรับ export แทน resource อื่น (เช่น `es_extended:getSharedObject`) ให้ `AddEventHandler("__cfx_export_es_extended_getSharedObject", function(setCB) setCB(fn) end)`

## UI

- UI ที่ไม่ต้องใช้เมาส์ ควรโฮสต์รวมใน HUD hub ตัวเดียว ส่งข้อมูลผ่าน export แทนการสร้างหน้าเว็บต่อ resource
- resource ที่เปิดเมนูแบบมี focus (`SetNuiFocus`) มี `ui_page` ของตัวเอง
- รายละเอียด NUI/DUI อยู่ที่ `NUI_DUI.md`

## Secrets

- ไฟล์ที่มี secret (webhook, token, รหัสผ่าน, api key) ต้องอยู่ใน `server_scripts` เท่านั้น ห้ามอยู่ใน `shared_scripts` / `client_scripts` / `files` (รวม glob เช่น `config/**`)
- ถ้า config เดิมเป็น shared ให้แยก secret ไปไฟล์ใหม่ฝั่ง server และเหลือค่าว่างในไฟล์ shared
- ห้ามส่งค่า secret ให้ client ผ่าน event/callback/export
- เจอ secret ในโค้ด ห้ามคัดลอกลงรายงาน บอกแค่ตำแหน่ง
- ห้ามเก็บ secret ลง repo สาธารณะ ใส่ไฟล์ config ลง `.gitignore`

## Database

- ตรวจ schema จริงก่อน สร้าง index เฉพาะที่ยังไม่มี (ดู prefix ซ้าย) ด้วย `ALGORITHM=INPLACE, LOCK=NONE` สำรอง schema ก่อนเสมอ
- เก็บสคริปต์ `indexes.sql` ใน resource ด้วย `ADD INDEX IF NOT EXISTS` สำหรับเครื่องอื่น

## Original intro

ชุดเดียวครบสำหรับเซิร์ฟเวอร์ FiveM ตระกูล `1nfx_*` มี 8 ส่วน: มาตรฐานโค้ด (ไฟล์นี้และโฟลเดอร์ `skills/`), `dev-flow/`, `terse/`, `poster-forge/`, `weapon-forge/`, `prop-forge/`, `sculpt-forge/` และ `map-forge/`
เป้าหมายของมาตรฐานโค้ด: การทำงานในเกมของแต่ละ resource เหมือนเดิมทุกอย่าง โค้ดสั้นลง ลื่นขึ้น ไม่มีของซ้ำ

## Original route table

Superseded by Auto-route and References in `SKILL.md`; kept for the owner's wording.

| งาน | อ่านไฟล์นี้ก่อน |
| --- | --- |
| เขียน/รีไรต์/optimize resource | `SKILL.md` (ไฟล์นี้) แล้วตามด้วยหัวข้อด้านล่าง |
| สร้าง resource ใหม่ | `checklists/new-resource.md`, `templates/resource/`, `scripts/new-resource.mjs` |
| ตรวจ/รีวิวโค้ด | `checklists/review.md`, `scripts/lint-resource.mjs`, `rules/contracts.md` |
| สถาปัตยกรรม, config, event, network | `skills/common/architecture.md`, `config.md`, `events.md`, `networking.md` |
| เรียก framework, แจ้งเตือน, log (ไม่ใช้ FC) | `skills/common/core-api.md`, `references/esx-api.md`, `references/pnotify-api.md` |
| ฐานข้อมูล | `skills/common/database.md` |
| ประสิทธิภาพ, native, 1nfx_lib, runtime | `skills/common/performance.md`, `natives.md`, `skills/common/1nfx-lib.md`, `runtime.md`, `memory/performance-research.md`, `memory/native-gotchas.md` |
| ความปลอดภัย, ดีบัก, สไตล์ | `skills/common/security.md`, `debugging.md`, `style.md`, `memory/security-exploits.md`, `memory/patterns.md` |
| UI (NUI/DUI) | `NUI_DUI.md` แล้วตามด้วย `skills/ui/design-system.md` (สไตล์ 1nfx), `nui-bridge.md`, `dui.md`, `vanilla-ui.md`, `react-vite.md`, `vue-svelte.md` |
| เครื่องมือเสริม MCP ความจำ ประหยัด token | `TOOLING.md` |
| คิดก่อนทำ, วางแผนทีละ resource, ดีบักเป็นระบบ, ตรวจหลักฐานก่อนบอกว่าเสร็จ, รีวิว/ออดิตแบบ lazy senior, สรุปส่งต่อข้ามเซสชัน | `dev-flow/SKILL.md` |
| ตอบสั้นประหยัด token (เปิดค้างทั้งเซสชัน) | `terse/SKILL.md` |
| โปสเตอร์ Support / Welfare / แจกของ | `poster-forge/SKILL.md` |
| สกินอาวุธ, โมเดล, ptfx (.ypt), เอฟเฟกต์หน้าจอ, เสียง | `weapon-forge/SKILL.md` |
| ปั้น prop (ป้าย, ATM, ตู้เซฟ, กล่อง, หีบ, โต๊ะคราฟต์, marker), ytyp, stream prop | `prop-forge/SKILL.md` |
| ปั้นให้เนียน: ทรงพอง ผสานชิ้นแบบมี fillet ตัวอักษร/ป้ายพอง หยดสไลม์ ต้นไม้ เมฆ ฟิกเกอร์ ราว บันได ซุ้มโค้ง แล้วย่อเป็น low-poly ที่ยังเนียน | `sculpt-forge/SKILL.md` |
| ปั้นแมพ FiveM (Sky AFK, Lobby, Airdrop/Warzone, Garage, Outpost, MLO), ymap, ybn, lighting, texture CC0 | `map-forge/SKILL.md` |

เมื่อเข้าเส้นทางของ `dev-flow`, `terse`, `poster-forge`, `weapon-forge`, `prop-forge`, `sculpt-forge` หรือ `map-forge` ให้เปิด `SKILL.md` ของโฟลเดอร์นั้นและทำตามนั้นทั้งหมด พาธใน skill เหล่านั้นอิงจากโฟลเดอร์ของมันเอง งานปั้นที่ต้องการผิวเนียนให้ปั้นด้วย `sculpt-forge` แล้ว export ผ่าน `prop-forge` หรือ `map-forge` ตามชนิดงาน
