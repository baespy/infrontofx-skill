# Terse examples

Thai before/after examples for the rules in `SKILL.md`, moved here on 2026-11-24. Replies to the owner are Thai; match these.

## Meaning words (rule 5)

ตัวอย่าง "อย่ารีสตาร์ตเซิร์ฟ ยังไม่ได้สำรอง DB" ถ้าตัดเหลือ "รีสตาร์ตเซิร์ฟ สำรอง DB" ความหมายกลับด้าน

## Before and after

**1. ผล lint** ก่อน: "รัน lint กับ `1nfx_airdrop` เสร็จเรียบร้อยแล้วครับ จากการตรวจสอบพบว่ามีปัญหาทั้งหมด 3 จุดด้วยกัน จุดแรกอยู่ในไฟล์ `core/sv_main.lua` บรรทัดที่ 88 ซึ่งมีการนำ string มาต่อกันใน SQL query โดยตรง..."

หลัง (สั้น): `1nfx_airdrop` lint 1 error, 2 warn แก้ครบ รันซ้ำได้ 0 error 0 warn
- `core/sv_main.lua:88` `sql-concat` เปลี่ยนเป็น `?` กัน SQL injection
- `core/cl_main.lua:41` `wait-zero` ย้าย loop `Wait(0)` ไป `lib.points` ทำงานเฉพาะตอนอยู่ในโซน ตอนว่างไม่กิน CPU
- `core/sv_main.lua:120` `capture-source` เพิ่ม `local src = source` บรรทัดแรกของ handler กัน `source` เปลี่ยนหลัง yield

**2. อธิบายบั๊กที่เจอเองใน console** ก่อน: "จากที่ผมไล่ดู log มา ดูเหมือนว่าสคริปต์พยายามเข้าถึงข้อมูลผู้เล่นที่ไม่มีอยู่แล้ว ซึ่งก็อาจเกิดได้จากหลายสาเหตุนะครับ ผมจึงลองเปิดไฟล์..."

หลัง (สั้น): `attempt to index a nil value (local 'xPlayer')` ที่ `core/sv_main.lua:96` ผู้เล่นออกเกมระหว่างรอ `MySQL.update.await` ทำให้ `Core.GetPlayerFromId(src)` หลัง await คืน nil แก้แล้ว: เช็ก nil หลัง await ก่อนให้ของ

หลัง (สั้นโหด): `core/sv_main.lua:96` `attempt to index a nil value (local 'xPlayer')` ผู้เล่นออกระหว่าง await แก้: เช็ก nil หลัง await

**3. รายงานสถานะ** ก่อน: "ตอนนี้ผมได้ทำการรีไรต์ `1nfx_airdrop` เสร็จเรียบร้อยแล้วครับ ก่อนเริ่มได้สำรองไฟล์ไว้ก่อน จากนั้นจึงไล่ปรับทีละส่วน... โดยรวมน่าจะลื่นขึ้นมาก หากมีอะไรเพิ่มเติมแจ้งได้เลยนะครับ"

หลัง (สั้นโหด): `1nfx_airdrop` รีไรต์เสร็จ สำรองที่ `_backup/2026-11-23/1nfx_airdrop`
- broadcast `-1` ทุก 500 ms -> ส่งเฉพาะคนในโซนเมื่อค่าเปลี่ยน (เดิม 3,200 ข้อความ/วินาทีที่ 1,600 คน)
- `Wait(0)` ตอนว่าง -> `lib.points`
- ตรวจแล้ว: lint 0 error, event/export/callback ครบเท่า backup
- ต้องลองในเกม: 2 คนเปิดกล่องพร้อมกันแล้วคนหนึ่งออกเกมกลางคัน, `resmon` ก่อน-หลังในโซน
