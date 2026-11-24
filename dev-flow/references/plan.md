# Plan

ใช้เมื่องานแตะหลายไฟล์หรือหลาย resource รีไรต์ resource ใหญ่ หรือสร้างระบบใหม่จากสเปก งานแก้จุดเดียวไม่ต้องเขียนแผน

## หาผู้เรียกก่อนวางแผน

ชื่อ resource อยู่ในชื่อ event ทุกตัว (`scriptname .. ":SV:x"`) และในทุกการเรียก export จากที่อื่น ค้นชื่อเดียวจึงเจอผู้เรียกเกือบทั้งหมด

```powershell
$name = "<resource>"
Get-ChildItem -LiteralPath "<project>\resources" -Recurse -File |
    Where-Object { $_.Extension -in ".lua", ".js", ".html", ".json", ".cfg" -and $_.FullName -notlike "*\node_modules\*" } |
    Select-String -SimpleMatch $name |
    Where-Object { $_.Path -notlike "*\$name\*" } |
    ForEach-Object { "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() }
Select-String -LiteralPath "<project>\server.cfg" -SimpleMatch $name
```

จากนั้นรันบล็อก "รายการสัญญา" ใน `references/verify.md` แบบฝั่งเดียวกับโฟลเดอร์ก่อนแก้ ผลที่ได้คือหัวข้อ "สัญญาที่คง" ของแผน

## แผนต่อหนึ่ง resource

เลือกระดับการแก้ตามตาราง Choose ใน `SKILL.md` ของ infrontofx (ฉบับเต็มคือหัวข้อ Edit levels ใน `references/house-standard.md` ของ infrontofx) resource ที่มีไฟล์ `.fxap` (escrow) หรือถูก obfuscate ห้ามแตะทั้งไฟล์และ manifest

```text
resource: <resource>
ระดับ: เขียน core ใหม่ | ย้ายเข้า method + optimize จุดที่วัดแล้วช้า | แก้บั๊กจุดเดียว
backup: _backup/<YYYY-MM-DD>/<resource>
ไฟล์:
  core/sv_main.lua   รวม while true สามตัวเป็น loop กลางตัวเดียว
  core/cl_main.lua   loop วัดระยะ -> lib.points
  config/config.lua  ไม่แตะ
สัญญาที่คง: event <n>, export <n>, callback <n>, command <n>, NUI action <n>, ตาราง <n>
ผู้เรียกภายนอก: <resource อื่น>/core/cl_main.lua:<บรรทัด> exports["<resource>"]:<ชื่อ>
ขั้น:
  1. สำรอง -> ตรวจ: จำนวนไฟล์ใน backup เท่าต้นฉบับ
  2. รวม loop ฝั่ง server -> ตรวจ: เหลือ while true ตัวเดียวใน core/sv_*.lua และ lint 0 error(s)
  3. <ขั้น> -> ตรวจ: <เงื่อนไขที่ล้มได้>
ทดสอบ: ในเครื่อง lint, สัญญา, method ครบ / ในเกม ตามเช็กลิสต์ใน references/verify.md
วัด: resmon 1 ในโซนและนอกโซน อย่างละ 60 วินาที ก่อนและหลัง
```

## ขั้นที่ดี

- ขั้นละเรื่องเดียว จบในตัว ถอยกลับได้จาก backup
- ทุกขั้นมี `ตรวจ:` ที่ล้มจริงถ้างานผิด
- ห้ามมีบรรทัด "TBD", "จัดการ edge case", "ปรับให้ดีขึ้น" ต้องระบุกรณีหรือค่าจริง

| ขั้น | ตรวจ |
| --- | --- |
| สำรอง | `@(Get-ChildItem -LiteralPath <โฟลเดอร์> -Recurse -File).Count` ของ backup เท่ากับของต้นฉบับ |
| ย้าย `FC` เข้า core | lint ไม่เหลือกฎ `no-fc` และ `no-config-function` |
| ล้างค่าคงที่และ helper ระดับไฟล์ | lint ไม่เหลือกฎ `no-file-constant` และ `no-local-function` |
| loop วัดระยะ -> `lib.points` | lint ไม่มี `wait-zero` ในไฟล์นั้น ส่วน resmon นอกโซนอยู่ใน "ต้องลองในเกม" |
| broadcast เฉพาะคนดู | ไม่เหลือ `TriggerClientEvent` ถึง `-1` ใน timer หรือ loop |
| จบ resource | lint `0 error(s)` และ exit 0, รายการสัญญาเทียบ backup ไม่มีบรรทัด `<=`, method ที่เรียกมีนิยามครบ |

## ทำตามแผน

1. ทำทุกขั้นต่อเนื่อง ไม่หยุดถามระหว่างขั้นหรือระหว่าง resource ยกเว้นเข้ากรณี "Stop and ask only when" ใน Hard rules ของ SKILL.md ของ dev-flow
2. จบขั้นไหน รันตัวตรวจของขั้นนั้นทันที ผ่านแล้วจึงไปขั้นถัดไป
3. จบขั้นสำคัญ จด checkpoint บรรทัดเดียวลง `PROGRESS.md` เช่น `<resource>: ขั้น 3/6 เสร็จ (backup _backup/<YYYY-MM-DD>/<resource>, lint 0 error)`
4. หลัง context ถูกบีบอัดหรือเริ่มเซสชันใหม่ เชื่อ `PROGRESS.md` มากกว่าความจำ ขั้นที่จดว่าเสร็จแล้วไม่ทำซ้ำ
5. ตรวจไม่ผ่าน แก้ในขั้นนั้น แก้แล้วยังล้มครบสามครั้ง ใช้กฎสามครั้งใน `references/debug.md`
6. แผนผิดกลางทาง แก้แผน จด `ตัดสินใจเอง:` ว่าเปลี่ยนอะไรเพราะอะไร แล้วทำต่อ
7. output ยาว (lint ทั้งโฟลเดอร์, log ของ Blender) เขียนลง `<project>/_dev/<YYYY-MM-DD>/logs/` แล้วอ่านเฉพาะท้ายไฟล์
8. ใช้ agent ช่วยค้นได้ไม่เกิน 2 ตัวพร้อมกัน ห้ามสอง agent แก้ไฟล์เดียวกัน และตรวจผลของ agent เองก่อนเชื่อ
9. resource หนึ่งตัวต้องตรวจครบและจดลง `PROGRESS.md` ก่อนเปิดตัวถัดไป

## แผนทดสอบ

ทุกแผนมีสามส่วน:

- **ตรวจในเครื่อง** lint, รายการสัญญาเทียบ backup, method ครบ และตัวตรวจ Blender เมื่อมีงาน asset
- **ต้องลองในเกม** เลือกข้อจากเช็กลิสต์ใน `references/verify.md` ให้ตรงงาน และเขียนผลที่ต้องเห็นทุกข้อ
- **สถานการณ์วัด** สำหรับงาน perf: จำนวนผู้เล่น จุดที่ยืน สิ่งที่ทำ ระยะเวลา ใช้ชุดเดียวกันทั้งก่อนและหลัง
