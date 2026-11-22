# infrontofx Agent Guide

ทุกครั้งที่สร้าง แก้ รีไรต์ รีวิว ดีบัก หรือ optimize resource FiveM Lua และ NUI/DUI ให้ทำตาม `SKILL.md` ในชุดนี้ ซึ่งเป็นแหล่งความจริงเดียวและชี้ไปยังไฟล์ตามงาน

## กฎที่ห้ามผ่อน

1. หัวไฟล์ client/server ทุกไฟล์: `local scriptname = GetCurrentResourceName()` (ถ้าไฟล์นั้นใช้) และตารางโมดูลเดียว `local Name = {}` หรือ global ชื่อโมดูลเดียวถ้ามีหลายไฟล์ (ถ้ามีตรรกะบริสุทธิ์ที่ใช้ร่วมกันทั้งสองฝั่งจริงๆ ให้แยกไว้ที่ `core/sh_<domain>.lua` ใน `shared_scripts` เป็น `<Name>Shared = {}` แล้วสืบทอดด้วย `setmetatable(..., { __index = <Name>Shared })` ห้ามก๊อปไฟล์แฝด `cl_<x>.lua` + `sv_<x>.lua`) โหลด `"@1nfx_lib/init.lua"` เป็นตัวแรกใน `shared_scripts` แล้วตามด้วย `"@1nfx_core/imports.lua"` (เรียก framework ผ่าน global `Core` ไม่เรียก `es_extended` ตรงๆ และไม่ใช้ `@ox_lib/init.lua` หรือ `@er_lib/init.lua`)
2. OOP เท่านั้น: ทุกฟังก์ชันเป็น method `function Module:Method()` ไม่มี `local function` ระดับไฟล์ ไม่มีค่าคงที่ระดับไฟล์ (`local X_Y = 1`) ไม่ย่อชื่อ resource เป็นตัวแปร event handler และ thread เรียก method เท่านั้น
3. ไม่มีตาราง `FC` และไม่มี `config/function/` เขียนการเรียก export/event ตรงๆ ใน method ของ `core/`
4. `Config` อยู่ใน `config/config.lua` (`Config.General`, `Config.Text`) อ่านตรงๆ ไม่ย่อเป็น local ระดับไฟล์ ประกาศ `Config = {}` ครั้งเดียวและกำหนดตารางย่อยตรงๆ ห้ามเขียน `Config.X = Config.X or {}`, `if not Config.X then Config.X = {} end` หรือ loop merge ค่า default ในไฟล์ config ไม่มี global สถานะ และห้ามทิ้ง key/ไฟล์ config ตายที่ `core/` ไม่ได้อ่านจริง
5. ไม่มี comment ในโค้ดทุกภาษา (Lua, JS, CSS, HTML)
6. event: `scriptname .. ":SV:action"` / `scriptname .. ":CL:action"` บรรทัดแรกของ handler ฝั่ง server คือ `local src = source`
7. `1nfx_lib` (`@1nfx_lib/init.lua`) เป็น shared runtime มาตรฐานตัวเดียว (`lib`, `cache`, `require`, `SetInterval`, `ClearInterval` แทน `ox_lib` / `er_lib` / `cfxlua-require`) ใช้ได้กับ 1-packet `callback`, `points`/`zones`/`grid`, `cache`, `guard` (server), `spawn` (client), `lru`/`heap`/`ringbuffer`, `table`/`array`, `cron`, `dui`, `requestModel`/`AnimDict`/`NamedPtfxAsset`, `addKeybind` ห้ามเรียก `lib.notify`, `lib.progressBar`, `lib.progressCircle`, `lib.showTextUI`, `lib.hideTextUI` ในสคริปต์ระบบเกม ให้ใช้ UI export ของเซิร์ฟเวอร์ตรงๆ แทน
8. server ตัดสินทุกค่า (ของ เงิน ราคา รางวัล cooldown ระยะ routing bucket) ตรวจ payload, throttle, กันซ้ำ
9. NUI: `{ action, data }`, handshake `uiReady`, เรียก `cb` ครั้งเดียวต่อ callback, ใช้ `textContent`, ย่อขยายด้วย `--px` บนกรอบ 1920x1080
10. ล้างให้ครบใน `onResourceStop` และ `playerDropped`
11. secret อยู่ในไฟล์ฝั่ง server เท่านั้น ไม่ลงใน repo
12. manifest ห้ามมี `dependencies`/`dependency` และ `escrow_ignore` ไฟล์ `core/sh_*.lua` ใช้เฉพาะตรรกะบริสุทธิ์ที่ใช้ร่วมทั้งสองฝั่งและต้องอยู่ใน `shared_scripts` เท่านั้น ห้ามแยก micro-resource ย่อยซ้ำซ้อนเมื่อโมดูลหลักจัดการอยู่แล้ว และห้าม `ensure <resource>` รายตัวซ้ำใน `server.cfg` ถ้าอยู่ในโฟลเดอร์ `[category]` ที่ `ensure` แล้ว (เว้นแต่ต้องบังคับลำดับเปิดก่อนหมวดนั้น)
13. UI ใช้สไตล์ 1nfx ใน `skills/ui/design-system.md` (ไม่มีขอบ dark layered panel ปุ่ม crimson `#632524`)

## แผนที่ repo

- `SKILL.md` กฎหลักและตัวเลือกเส้นทาง
- `NUI_DUI.md`, `TOOLING.md` UI และเครื่องมือเสริม
- `skills/common/` กฎ Lua (style, architecture, config, core-api, events, runtime, security, performance, networking, database, natives, 1nfx-lib, debugging)
- `skills/ui/` NUI bridge, design system, vanilla, React/Vite, Vue/Svelte, DUI
- `references/` API ของ Core (ESX-compatible), pNotify, infrontofx-fivem
- `rules/contracts.md` กติกาข้าม resource
- `memory/` ข้อควรระวังและงานวิจัยที่เรียนรู้มา (ใส่ Date และ Game build ทุกรายการ)
- `checklists/` เช็กลิสต์สร้างใหม่และรีวิว
- `templates/resource/` resource ตัวอย่างตามมาตรฐาน
- `scripts/` `lint-resource.mjs`, `new-resource.mjs`, `validate-skill.mjs`
- `poster-forge/` ทำโปสเตอร์ Support/Welfare (อ่าน `poster-forge/SKILL.md`)
- `weapon-forge/` ทำสกิน/โมเดลอาวุธ ptfx เสียง (อ่าน `weapon-forge/SKILL.md`)
- `prop-forge/` ปั้น prop สไตล์ของเล่นแบรนด์เซิร์ฟเวอร์ (อ่าน `prop-forge/SKILL.md`)
- `map-forge/` ปั้นและ export แมพ FiveM 144-200 FPS (อ่าน `map-forge/SKILL.md`)

## วิธีทำงาน

- ใช้แพตเทิร์นเดิมของ resource ถ้าไม่ขัดกับกฎข้างบน
- รัน `node scripts/lint-resource.mjs <resource>` หลังแก้ ต้องไม่มี error
- ข้อเท็จจริงที่เรียนรู้ใหม่ให้เพิ่มใน `memory/` ไม่ใช่ `skills/`
- รัน `node scripts/validate-skill.mjs` ก่อนเผยแพร่การเปลี่ยนแปลง
