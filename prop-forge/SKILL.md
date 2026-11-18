---
name: prop-forge
description: ปั้น prop FiveM สไตล์ของเล่นแบรนด์เซิร์ฟเวอร์ (toy-brand props) เป็นชุดเดียวกันทั้งเซ็ต เช่น ป้าย Garage/Pound แบบเสาลูกศร, ป้าย Shop, ตู้ ATM, ตู้เซฟ, กล่อง stash, หีบ loot เปิดฝามีเหรียญ, โต๊ะคราฟต์, หัวมาสคอตลอยเป็น marker ด้วย Blender (CLI หรือ Antigravity + Blender MCP) จากสเปก JSON แล้วตรวจ ตั้งชนและเตรียม export เป็น .ydr/.ytd/.ytyp ใช้เมื่อผู้ใช้ขอปั้น prop, ทำ prop เซิร์ฟเวอร์, ทำป้าย, ทำตู้ ATM/ตู้เซฟ/กล่อง/โต๊ะคราฟต์, ทำ marker, ทำ prop ตามคลิปหรือรูปอ้างอิง, เปลี่ยนสี/แบรนด์ของชุด prop, หรือเพิ่ม prop ใหม่เข้า 1nfx_prop (prop modeling, custom prop, ytyp, stream prop, Sollumz, slime, mascot, Antigravity)
---

# Prop Forge

สร้างชุด prop ประจำเซิร์ฟเวอร์ที่ทุกชิ้นดูเป็นแบรนด์เดียวกัน (สีชุดเดียว มาสคอต มงกุฎ สไลม์ไหล ตัวหนังสือแบบสติกเกอร์) จากสเปก JSON ไฟล์เดียว ได้ `.blend` ต่อชิ้น, ภาพ preview, texture palette ของทั้งชุด, กล่องชน และรายงาน tris ทุกชิ้นสร้างจาก primitive ที่ bevel แล้ว รวมเป็น mesh เดียว origin อยู่กลางพื้น ด้านหน้าหัน -Y หน่วยเมตร

แนวที่ผู้ใช้ต้องการถอดมาจากคลิปอ้างอิงของผู้ใช้ (2026-11-11) อธิบายเป็นตัวหนังสือใน `references/style-toybrand.md` ส่วนภาพเป้าหมายที่ใช้ได้คือผลงานของเราเองใน `references/targets/` (ชุดตัวอย่าง GOO LAB) ไม่มีภาพจากคลิปอยู่ใน skill

## ขั้นตอน

1. **รับโจทย์:** ชื่อชุด (`set` ขึ้นต้น `1nfx_`), ชื่อแบรนด์, สี 5 สีหลัก, รายการ prop และหน้าที่ในเกม (จุดเบิกรถ, จุดพาวด์, ร้าน, ATM, stash, loot, คราฟต์, marker) ถ้าผู้ใช้ส่งรูปหรือคลิป ให้ถอดเป็น 5 แกนตาม "ถอดสไตล์ใหม่" ใน `references/style-toybrand.md` ก่อน ห้ามลอกชื่อ โลโก้ หรือมาสคอตของคนอื่น
2. **เขียนสเปก:** คัดลอก `templates/prop-spec.example.json` ไปไว้ `<งาน>/source/props.json` เลือก archetype จาก `references/archetypes.md` ถ้าไม่มีแบบที่ต้องการ ให้เขียน builder ใหม่ตามหัวข้อ "เพิ่ม archetype ใหม่" ในไฟล์เดียวกัน
3. **ปั้นรอบแรก:** รัน `scripts/blender/forge_prop.py` (ดูคำสั่งด้านล่าง) เปิดดู `lineup.png` และ `<id>_preview.png` ทุกชิ้นด้วยตา เทียบ "เกณฑ์ตรวจหน้าตา" ใน `references/style-toybrand.md` และภาพใน `references/targets/`
4. **แก้จนลงตัว:** แก้สเปก (สี ป้าย พารามิเตอร์) แล้วรันซ้ำด้วย `--only <id>` ถ้าต้องปั้นแก้ละเอียดแบบโต้ตอบ ใช้ Antigravity + Blender MCP ตาม `references/antigravity.md`
5. **ลวดลายพิเศษ (ถ้ามี):** โลโก้กราฟฟิตี้หรือสติกเกอร์ที่ปั้นเป็นเรขาคณิตไม่ได้ ให้เจนเป็น PNG พื้นใสตาม "Decal จาก AI" ใน `references/pipeline.md` แล้วใส่ใน `decals` ของสเปก
6. **ตรวจสัญญา:** รัน `scripts/blender/validate_prop.py` จนได้ `fail=0` และอ่าน `WARN` ทุกบรรทัด
7. **Export:** ทำตาม `references/pipeline.md` หัวข้อ Export (Sollumz) ถ้าเครื่องยังไม่มี Sollumz ให้ถามผู้ใช้ก่อนติดตั้ง ห้ามติดตั้งเอง
8. **เชื่อมเข้าเซิร์ฟเวอร์:** ทำตาม `references/integration.md` (stream, `data_file "DLC_ITYP_REQUEST"`, โค้ด spawn ที่ปล่อยหน่วยความจำ) สำรองไฟล์ก่อนแก้ resource จริงทุกครั้ง
9. **ซิงก์และรายงาน:** ถ้าแก้ไฟล์ใน skill ให้รัน `scripts/sync-antigravity.ps1` รายงานผู้ใช้แยกให้ชัดว่าอะไรตรวจแล้ว อะไรยังไม่ได้ลองในเกม

## คำสั่ง

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
$skill   = 'C:\Users\Administrator\Desktop\mainserver\.claude\skills\infrontofx\prop-forge'
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --lineup
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --only 1nfx_goo_atm
& $blender -b --factory-startup -P "$skill\scripts\blender\validate_prop.py" -- --blend work\build
```

ตัวเลือกของ `forge_prop.py`: `--only id1,id2` สร้างเฉพาะชิ้น, `--lineup` เรนเดอร์ทุกชิ้นเรียงกัน, `--bake 1024` อบ texture atlas แทน palette, `--no-render` ไม่เรนเดอร์, `--samples 32`, `--list` ดู archetype และ role ของสี ทั้งชุด 9 ชิ้นใช้เวลาราวหนึ่งนาที

## เลือกอ่าน

| งาน | อ่าน |
| --- | --- |
| แนวศิลป์ สี สัดส่วน ลวดลาย กฎองค์ประกอบ เกณฑ์ตรวจหน้าตา ถอดสไตล์ใหม่จากรูป/คลิป | `references/style-toybrand.md` |
| archetype ทั้ง 8 แบบ ขนาด พารามิเตอร์ งบ tris สคีมาสเปก และวิธีเพิ่ม archetype ใหม่ | `references/archetypes.md` |
| สัญญาพิกัด, palette กับ bake, decal จาก AI, collision, LOD, export ด้วย Sollumz, ytyp | `references/pipeline.md` |
| ปั้นผ่าน Antigravity + Blender MCP, ไฟล์ .blend 4.2 กับ 5.3, ทำงานร่วมกับ agent อื่น | `references/antigravity.md` |
| fxmanifest, ชื่อไฟล์ stream, โค้ด spawn, marker หมุน/ลอย, QA ในเกม | `references/integration.md` |
| ภาพเป้าหมายของชุดตัวอย่าง | `references/targets/` |

## เครื่องมือ

| ไฟล์ | หน้าที่ |
| --- | --- |
| `scripts/blender/forge_prop.py` | สร้าง prop จากสเปก: 8 archetype, ตัวช่วยปั้น (กล่อง bevel, ทรงกระบอก, ทรงกลม, ห่วง, รูป 2D ดึงหนา, ตัวหนังสือ mesh มีขอบ, สไลม์ไหลรอบขอบ, ม่านสไลม์, มงกุฎ, หัวมาสคอต, ตา X, ดาว), รวม mesh, ล้างเศษ, palette texture ของชุดหรือ bake, decal, กล่องชน, preview, lineup, `report.json` |
| `scripts/blender/validate_prop.py` | ตรวจ `.blend` ทีละไฟล์หรือทั้งโฟลเดอร์: ชื่อ, transform, origin ที่พื้น, ขนาด, tris เทียบงบ, NaN, สามเหลี่ยมเสีย, UV, วัสดุ, texture ยกกำลังสอง, กล่องชน, orphan ใช้ได้ทั้ง headless และใน Blender สดผ่าน MCP |
| `scripts/sync-antigravity.ps1` | ซิงก์ skill ไป `.agents/skills/prop-forge` ให้ Antigravity ใช้ (`-Check` ตรวจอย่างเดียว, `-Force` เขียนทับ) |
| `templates/prop-spec.example.json` | สเปกชุดตัวอย่าง GOO LAB ครบ 9 ชิ้น |
| `assets/fonts/` | ฟอนต์ OFL (Titan One, Russo One) สำหรับตัวหนังสือบน prop |

ใช้แค่ Blender 4.2.3 (`C:\Tools\blender-4.2.3-windows-x64\blender.exe`) ไม่ต้องลง add-on หรือ Python แยกตอนปั้นและตรวจ Sollumz ใช้เฉพาะตอน export

## กฎที่ห้ามข้าม

**ต้นฉบับ.** คลิปอ้างอิงเป็นของเซิร์ฟเวอร์หรือผู้สร้างอื่น ใช้ได้แค่ทิศทางสไตล์ ห้ามใช้ชื่อแบรนด์ โลโก้ มาสคอต หรือ texture ของเขา ทุกชุดต้องมีชื่อแบรนด์ของเราเองในสเปก ห้ามใส่เครื่องหมายการค้าจริงลงบน prop

**สัญญาพิกัด.** mesh เดียวชื่อเดียวกับไฟล์ (`[a-z0-9_]`), transform apply แล้ว, จุดต่ำสุดอยู่ที่ z = 0 กลาง X/Y, ด้านหน้าหัน -Y, หน่วยเมตร, กล่องชนชื่อ `<id>_col_N` (marker ไม่มีชน) ห้ามแก้ชื่อหรือ origin หลังจากเชื่อมเข้าเซิร์ฟเวอร์แล้ว

**งบ.** tris ไม่เกินงบใน `references/archetypes.md`, วัสดุไม่เกิน 4 (diffuse, emissive, decal), texture ยกกำลังสองไม่เกิน 2048 ทั้งชุดใช้ palette ร่วมกันไฟล์เดียว รายละเอียดที่เล็กกว่า 2 ซม. ให้ใส่เป็น decal ไม่ใช่ geometry

**ไฟล์ระบบ.** ห้ามแตะ resource ที่มี `.fxap` การแก้ `fxmanifest.lua`, config ของ resource อื่น และการรีสตาร์ตเซิร์ฟเวอร์ ต้องสำรองไฟล์ก่อนและให้ผู้ใช้ยืนยัน

**ทำงานร่วมกัน.** Antigravity, Codex และ Claude Code แก้โฟลเดอร์นี้ได้พร้อมกัน ต้นฉบับอยู่ที่ `.claude/skills/infrontofx/prop-forge` ห้ามแก้สำเนาใน `.agents/skills/prop-forge` โดยตรง หนึ่งชุด prop หนึ่ง agent และห้ามสอง agent ยิงคำสั่งเข้า Blender สดตัวเดียวกันพร้อมกัน

**รายงานตามจริง.** `RESULT fail=0` แปลว่าโครงไฟล์ `.blend` ผ่านสัญญา ภาพ preview เป็นการเรนเดอร์ Eevee ไม่ใช่ภาพในเกม จนกว่าผู้ใช้จะ export และเห็นในเกมเอง ให้บอกว่ายังไม่ได้ทดสอบในเกม เมื่อผู้ใช้รายงานผลในเกม ให้บันทึกลง "สิ่งที่พิสูจน์แล้ว" ใน `references/integration.md`

## รูปแบบโค้ด

Lua ที่เขียนเพิ่ม (spawn, interaction) ให้ทำตาม `infrontofx` ใน `SKILL.md` ระดับบนของแพ็กนี้: OOP module table, ไม่มี comment, ไม่มี `local function` ระดับไฟล์, 4 ช่องว่าง, double quotes, trailing comma, ใช้ `lib.spawn.pointProp` ของ `1nfx_lib`
