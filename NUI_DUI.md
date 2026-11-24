# NUI / DUI สำหรับ resource 1nfx_*

อ่านไฟล์นี้เมื่อต้องสร้างหรือแก้หน้า UI ใน FiveM กฎ OOP/ไม่มี comment/ไม่มีค่าคงที่ระดับไฟล์ใน `SKILL.md` ใช้กับ JS ด้วย (ไม่มี comment, ค่าจริงเขียนตรงจุดใช้)

## เลือกใช้อะไร

- NUI: เมนู หน้าต่าง HUD ที่ผู้เล่นโต้ตอบหรือดูบนหน้าจอ
- DUI: วาดหน้าเว็บลงเป็น texture บนโมเดลหรือพื้นผิวในโลก (จอ ป้าย กล้อง) ผู้เล่นไม่ได้ควบคุมด้วยเมาส์โดยตรง
- ถ้าแค่แสดงข้อความสั้นหรือ prompt ใช้ `1nfx_textui` / `1nfx_notify` ที่มีอยู่ ไม่สร้าง NUI ใหม่

## โครง

```
fxmanifest.lua   ui_page "web/dist/index.html" และ files เฉพาะที่หน้าอ้างถึงจริง
core/cl_nui.lua  โมดูล method ทั้งหมดของ NUI
web/             ซอร์ส (Vite)
web/dist/        ผลลัพธ์ build ที่ส่งให้ผู้เล่น
```

- HTML/CSS/JS ธรรมดาได้ถ้าหน้าเล็ก ใช้ React + Vite เมื่อมีหลายหน้าหรือสถานะซับซ้อน ส่งเฉพาะ `dist` ใน `files` ไม่ส่งซอร์สและ `node_modules`
- รูป ฟอนต์ เสียงต้องอยู่ในเครื่อง ห้ามโหลดจาก CDN (ผู้เล่นออฟไลน์/บล็อกโดเมนแล้วหน้าพัง)

## Lua ↔ NUI

- Lua ส่ง: `SendNUIMessage({ action = "open", data = payload })` ส่งเมื่อค่าเปลี่ยนเท่านั้น (ตรงกับกฎใน "Optimize")
- JS ส่งกลับ: `fetch("https://" + GetParentResourceName() + "/<name>", { method: "POST", body: JSON.stringify(data) })` ใช้ helper กลางที่เดียวใน JS
- `RegisterNUICallback("<name>", function(data, cb) ... cb({}) end)` ต้องเรียก `cb` ทุกเส้นทาง รวมทั้งตอน error ไม่งั้นคำขอค้าง
- ชื่อ action/callback เป็นสัญญากับ resource อื่น ห้ามเปลี่ยนชื่อเดิม (กฎข้อ 3 ของ "ขั้นตอนต่อหนึ่ง resource")
- ตรวจข้อมูลจาก NUI เหมือนข้อมูลจาก client ทั่วไป: action ที่แตะเงิน/ของ/ตำแหน่ง ต้องส่งต่อ server และให้ server ตรวจ

## Focus และการปิด

- เปิด: `SetNuiFocus(true, true)` ปิด: `SetNuiFocus(false, false)` ทุกทางออกต้องผ่าน method ปิดตัวเดียว (ปุ่ม ESC, ปุ่มปิด, ตาย, ถูกลาก, เปลี่ยน routing bucket)
- `AddEventHandler("onResourceStop", ...)` ต้องปล่อย focus และ `SendNUIMessage` ปิดหน้า ไม่งั้นเมาส์ค้างเมื่อ restart resource
- ใช้ `SetNuiFocusKeepInput(true)` เมื่อต้องเดินได้ระหว่างเปิด UI แล้ว disable ปุ่มที่ชนกันใน loop เฉพาะตอนเปิด
- ESC: ให้ JS จับแล้วเรียก callback ปิด หรือ Lua จับ `IsControlJustReleased` ตอนเปิดอยู่เท่านั้น

## ออกแบบ UI

- ใช้ impeccable (ถ้าติดตั้ง) หรือตรวจเองตามนี้ก่อนส่งงาน: ลำดับตัวอักษรชัด, ขนาดตัวอักษรขั้นต่ำอ่านได้บน 1080p และ 1440p, contrast พอบนฉากเกมที่สว่าง/มืดสลับกัน, สถานะ hover/active/disabled ครบ
- ใช้ธีมและโทเค็นสีชุดเดียวต่อ resource (CSS variable บน `:root`) หน้าตาเดียวกับ UI ตระกูล `1nfx_*` อื่นตาม Hard rules ข้อ UI ใน `SKILL.md`
- ขนาดอิงหน้าจอ 1920x1080 แล้วใช้ `vw`/`vh`/`clamp()` ให้ปรับตามความละเอียด อย่าใช้ px ตายตัวทั้งหน้า
- CEF ของเกมเป็น Chromium รุ่นเก่ากว่าเบราว์เซอร์ปัจจุบัน ฟีเจอร์ CSS/JS ใหม่ต้องลองในเกมก่อนยืนยัน ไม่ใช่แค่ในเบราว์เซอร์

## ประสิทธิภาพ NUI

- animate เฉพาะ `transform` และ `opacity` หลีกเลี่ยง `backdrop-filter`/`filter: blur` บนพื้นที่ใหญ่ และ `box-shadow` ที่เปลี่ยนค่าต่อเฟรม
- ตอนปิด UI ซ่อนด้วย `display: none` (ไม่ใช่แค่ `opacity: 0`) เพื่อหยุดการวาด
- HUD ที่อัปเดตถี่ (ความเร็ว เลือด) รวมเป็นข้อความเดียวต่อรอบ ไม่ส่งแยกทีละค่า และไม่สร้าง DOM ใหม่ทุกครั้งแค่อัปเดตข้อความ/สไตล์ของ node เดิม
- รายการยาว (ช่องเก็บของ ร้านค้า) ใช้ virtual list หรือ render เฉพาะที่เห็น
- รูปเป็น webp/svg ขนาดพอดีกับที่แสดง เอารูปที่ไม่มีใครอ้างออกจาก `files`
- ถอด event listener และ `setInterval` ตอนปิดหน้า

## DUI

- ลำดับ native: `CreateDui(url, width, height)` → `GetDuiHandle` → `CreateRuntimeTxd` → `CreateRuntimeTextureFromDuiHandle` → `AddReplaceTexture(txdOrig, textureOrig, txdNew, textureNew)` ส่งข้อความด้วย `SendDuiMessage(duiObject, json)`
- ใช้ความละเอียดต่ำที่สุดที่ยังอ่านได้ (เช่น 512x256 สำหรับป้าย) DUI แต่ละตัวคือเบราว์เซอร์หนึ่งหน้า ยิ่งมากยิ่งกิน FPS
- สร้างเมื่อผู้เล่นเข้าใกล้ (`lib.points`) และ `DestroyDui` + `RemoveReplaceTexture` เมื่อออกนอกระยะหรือ resource หยุด (`onResourceStop`)
- แชร์ DUI ตัวเดียวถ้าเนื้อหาเหมือนกัน ไม่สร้างต่อหนึ่งจอ
- หน้าเว็บของ DUI ใช้ `ui_page` เดียวกับ NUI ไม่ได้ ให้ใส่ไว้ใน `files` แล้วอ้าง `nui://<resource>/web/dist/<file>.html`

## ตรวจก่อนส่ง

1. เปิด-ปิดซ้ำ 10 ครั้ง เมาส์ไม่ค้าง ไม่มี thread/listener สะสม
2. restart resource ตอนเปิด UI อยู่ ต้องกลับมาปกติ
3. grep `cb(` ทุก `RegisterNUICallback` ครบทุกเส้นทาง
4. grep `--` และ `//` ที่เป็น comment ต้องเป็น 0 (ทั้ง Lua/JS/CSS)
5. `resmon` ตอนเปิด UI แล้วนิ่ง ต้องไม่สูงกว่าตอนปิด
