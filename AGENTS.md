# infrontofx Agent Guide

ทุกครั้งที่สร้าง แก้ รีไรต์ รีวิว ดีบัก หรือ optimize resource FiveM Lua และ NUI/DUI ให้ทำตาม `SKILL.md` ในชุดนี้ ซึ่งเป็นแหล่งความจริงเดียวและชี้ไปยังไฟล์ตามงาน

## กฎที่ห้ามผ่อน

1. หัวไฟล์ client/server ทุกไฟล์: `local scriptname = GetCurrentResourceName()` (ถ้าไฟล์นั้นใช้) และตารางโมดูลเดียว `local Name = {}` หรือ global ชื่อโมดูลเดียวถ้ามีหลายไฟล์ framework เรียกผ่าน global `Core` จาก `shared_script "@1nfx_core/imports.lua"` ไม่เรียก `es_extended` ตรงๆ
2. OOP เท่านั้น: ทุกฟังก์ชันเป็น method `function Module:Method()` ไม่มี `local function` ระดับไฟล์ ไม่มีค่าคงที่ระดับไฟล์ (`local X_Y = 1`) ไม่ย่อชื่อ resource เป็นตัวแปร event handler และ thread เรียก method เท่านั้น
3. ไม่มีตาราง `FC` และไม่มี `config/function/` เขียนการเรียก export/event ตรงๆ ใน method ของ `core/`
4. `Config` อยู่ใน `config/config.lua` (`Config.General`, `Config.Text`) อ่านตรงๆ ไม่ย่อเป็น local ระดับไฟล์ สร้างแต่ละตารางครั้งเดียวด้วย `Config = {}` ไม่เขียน `X = X or {}` ซ้ำในไฟล์อื่น และไม่มี global สถานะ
5. ไม่มี comment ในโค้ดทุกภาษา (Lua, JS, CSS, HTML)
6. event: `scriptname .. ":SV:action"` / `scriptname .. ":CL:action"` บรรทัดแรกของ handler ฝั่ง server คือ `local src = source`
7. ox_lib ใช้ได้กับ callback, points, zones, cache, table, array, cron, dui, requestModel/AnimDict/NamedPtfxAsset, addKeybind ห้าม `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI` ใช้ UI export ของเซิร์ฟเวอร์แทน
8. server ตัดสินทุกค่า (ของ เงิน ราคา รางวัล cooldown ระยะ routing bucket) ตรวจ payload, throttle, กันซ้ำ
9. NUI: `{ action, data }`, handshake `uiReady`, เรียก `cb` ครั้งเดียวต่อ callback, ใช้ `textContent`, ย่อขยายด้วย `--px` บนกรอบ 1920x1080
10. ล้างให้ครบใน `onResourceStop` และ `playerDropped`
11. secret อยู่ในไฟล์ฝั่ง server เท่านั้น ไม่ลงใน repo
12. manifest ห้ามมี `dependencies`/`dependency` และ `escrow_ignore` ห้ามมีไฟล์ `sh_*.lua`
13. UI ใช้สไตล์ 1nfx ใน `skills/ui/design-system.md` (ไม่มีขอบ dark layered panel ปุ่ม crimson `#632524`)

## แผนที่ repo

- `SKILL.md` กฎหลักและตัวเลือกเส้นทาง
- `NUI_DUI.md`, `TOOLING.md` UI และเครื่องมือเสริม
- `skills/common/` กฎ Lua (style, architecture, config, core-api, events, runtime, security, performance, networking, database, natives, ox-lib, debugging)
- `skills/ui/` NUI bridge, design system, vanilla, React/Vite, Vue/Svelte, DUI
- `references/` API ของ Core (ESX-compatible), pNotify, infrontofx-fivem
- `rules/contracts.md` กติกาข้าม resource
- `memory/` ข้อควรระวังและงานวิจัยที่เรียนรู้มา (ใส่ Date และ Game build ทุกรายการ)
- `checklists/` เช็กลิสต์สร้างใหม่และรีวิว
- `templates/resource/` resource ตัวอย่างตามมาตรฐาน
- `scripts/` `lint-resource.mjs`, `new-resource.mjs`, `validate-skill.mjs`
- `poster-forge/` ทำโปสเตอร์ Support/Welfare (อ่าน `poster-forge/SKILL.md`)
- `weapon-forge/` ทำสกิน/โมเดลอาวุธ ptfx เสียง (อ่าน `weapon-forge/SKILL.md`)

## วิธีทำงาน

- ใช้แพตเทิร์นเดิมของ resource ถ้าไม่ขัดกับกฎข้างบน
- รัน `node scripts/lint-resource.mjs <resource>` หลังแก้ ต้องไม่มี error
- ข้อเท็จจริงที่เรียนรู้ใหม่ให้เพิ่มใน `memory/` ไม่ใช่ `skills/`
- รัน `node scripts/validate-skill.mjs` ก่อนเผยแพร่การเปลี่ยนแปลง
