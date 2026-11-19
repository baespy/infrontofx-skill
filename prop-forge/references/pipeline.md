# Pipeline

## สัญญาพิกัด

| ข้อ | ค่า |
| --- | --- |
| หน่วย | เมตร, Z ขึ้น |
| origin | กลาง X/Y ของ prop, จุดต่ำสุดที่ z = 0 (marker ก็วางที่ z = 0 แล้วให้ Lua ยกขึ้น) |
| ด้านหน้า | หัน -Y ใน Blender ถ้าในเกมหันกลับด้าน ให้บวก heading 180 ในโค้ด spawn ห้ามหมุน mesh หลังเชื่อมระบบแล้ว |
| object | mesh เดียวชื่อเดียวกับไฟล์ ไม่มี parent, transform apply แล้ว |
| กล่องชน | object แยก `<id>_col_N` ใน collection `<id>_collision` แสดงแบบ wire ไม่ render |
| metadata | custom property `prop_forge` บน mesh เก็บ JSON (archetype, ขนาด, tris, งบ, shader, lodDist) |

## Finish: palette หรือ bake

**Palette (ค่าเริ่มต้น).** ทุกหน้าถูก map ไปกลางช่องสีของ texture 256x256 (ช่องละ 32 px, 64 ช่อง) ชื่อ `<set>_palette` ทั้งชุดใช้ไฟล์เดียวกัน สีคมไม่เบลอ ใช้หน่วยความจำน้อยมาก (DXT1 ราว 32 KB ต่อทั้งชุด) UV ถูกขยับเล็กน้อยภายในช่องเพื่อไม่ให้สามเหลี่ยมมี UV พื้นที่ศูนย์ (ตัว export คำนวณ tangent แล้วได้ NaN) วัสดุที่ได้: `<id>_diffuse` (`default.sps`) และ `<id>_emissive` (`emissive.sps`) ถ้ามีจอหรือแถบไฟ

**Bake (`--bake 1024` หรือ `2048`).** smart UV project แล้วอบสี diffuse ลง `<id>_atlas.png` ใช้เมื่อจะวาดทับ texture ต่อ (ลายกราฟฟิตี้ รอยเปื้อนสไลม์) ใน Photoshop/Krita ใช้หน่วยความจำมากกว่าและขอบตัวหนังสือจะนุ่มลง ชิ้นสูงเกิน 2 เมตรใช้ 2048

## Decal จาก AI

ลายที่ปั้นเป็นเรขาคณิตไม่ได้ (โลโก้กราฟฟิตี้, สติกเกอร์มาสคอตลายเส้น, หน้าจอ ATM) ให้เจนเป็นภาพแล้วแปะเป็นแผ่น decal:

1. เจนภาพด้วยสคริปต์ของ `poster-forge` (`../poster-forge/scripts/agy-gen.ps1` ผ่าน Antigravity หรือ `../poster-forge/scripts/codex-gen.ps1` ผ่าน Codex) สั่งให้วาดบนพื้นเขียว `#00FF00` เรียบ ๆ ขอบชัด ไม่มีเงาตกพื้น
2. ตัดพื้นด้วย `../poster-forge/scripts/cutout.ps1` ให้ได้ PNG พื้นใส ย่อเป็นยกกำลังสอง (256 หรือ 512)
3. ใส่ใน `decals` ของสเปก แล้วรันใหม่ แต่ละ decal กลายเป็นวัสดุ `<id>_decal_N` (`decal.sps` หรือ `cutout.sps` ตอน export)

พรอมต์ตั้งต้น (แก้ชื่อแบรนด์และสี):

```text
Flat vector sticker logo for a toy brand called "GOO LAB": bubbly rounded letters in acid lime #C9F31D with a thick dark #221E28 outline, a round purple #8E2DE2 mascot head with X eyes and a tiny gold crown, slime drips under the letters, small 4-point sparkles. Centered, no text other than GOO LAB, no shadow, no gradient background, solid pure green #00FF00 background, crisp edges, 1:1.
```

ห้ามสั่งให้ AI เลียนโลโก้หรือมาสคอตของคนอื่น และอย่าใส่รูปจากคลิปอ้างอิงเป็น `-Ref` ตอนเจนโลโก้

## Collision

- กล่องชนสร้างจากชิ้นที่ใส่ `collide=True` เป็นกล่องตามขอบเขตโลก (axis aligned) พอสำหรับ prop ตั้งพื้นทั่วไป
- ชิ้นที่ผู้เล่นต้องยืนชิด (ตู้ ATM, ตู้เซฟ, โต๊ะ) ต้องมีกล่องชนครอบตัวหลัก ไม่อย่างนั้นผู้เล่นจะเดินทะลุและ `PlaceObjectOnGroundProperly` จะวางผิด
- marker ไม่มีชน ตั้ง `SetEntityCollision(entity, false, false)` ในโค้ดด้วย

## LOD

- `lod_dist` ใน `report.json` (80 สำหรับชิ้นเล็ก 120 สำหรับป้ายและโต๊ะ) ใช้ใส่ `lodDist` ของ archetype ใน ytyp
- ชิ้นที่วางซ้ำหลายจุดทั่วแมป (ป้าย Garage, ATM) ควรมี LOD กลาง: duplicate mesh, ใส่ Decimate (Collapse 0.4) แล้วใช้เป็น Med LOD ใน Sollumz ถ้าเกมกระตุกตอนเข้าใกล้จุดที่มี prop เยอะ ให้ลด `lodDist` ก่อนลด geometry

## Export (Sollumz)

`scripts/blender/export_prop.py` ทำงาน Sollumz ทั้งหมดให้อัตโนมัติจาก `.blend` ของ `forge_prop.py`:

1. แปลง texture ของวัสดุเป็น `.dds` (DXT5 + mipmaps ด้วยตัวเข้ารหัสของ `../weapon-forge/scripts/blender/export_ydr.py`) เพราะ Sollumz ฝังได้เฉพาะ DDS
2. แปลงวัสดุเป็น Sollumz shader ตาม `prop_forge_shader` (`default.sps`, `emissive.sps`, `decal.sps`) และฝัง texture ไว้ใน `.ydr`
3. รวม `<id>_col_N` เป็น Bound Composite (GeometryBVH) วัสดุชนเป็น `PLASTIC` (เปลี่ยนด้วย `--collision`) แล้ว parent เข้า Drawable เป็น embedded collision
4. แปลง mesh เป็น Drawable ชื่อ `<id>` สร้าง ytyp `<id>` ที่มี archetype `<id>` (`lodDist` จาก `report.json`, bbox คำนวณให้)
5. Export ด้วย `sollumz.export_assets` (GEN8 สำหรับ FiveM) ทีละชิ้นใน process แยก

```powershell
& 'C:\Tools\blender-4.2.3-windows-x64\blender.exe' -b -P "$skill\scripts\blender\export_prop.py" -- --blend work\build --out work\stream --format cwxml
```

ต้องรัน **ไม่ใส่** `--factory-startup` ไม่อย่างนั้น Sollumz ไม่โหลด ผลลัพธ์ต่อชิ้น: `<id>.ydr` + `<id>.ytyp` (native) หรือ `<id>.ydr.xml` + `<id>.ytyp.xml` + โฟลเดอร์ `<id>\` ที่มี `.dds` (cwxml) บรรทัด `EXPORT {...}` บอกวัสดุ จำนวนกล่องชน และไฟล์ที่เขียน จบด้วย `RESULT ok=<n> fail=<n>`

| `--format` | ต้องมี | ได้ |
| --- | --- | --- |
| `native` (ค่าเริ่ม) | Sollumz + szio + PyMateria (ส่วนเสริมของ Cfx.re มีสัญญาอนุญาตกับ Take-Two/Rockstar ผู้ใช้ต้องยอมรับเอง ห้าม agent ติดตั้งแทน) | `.ydr` `.ytyp` ไบนารีพร้อม stream |
| `cwxml` | Sollumz + szio | XML ที่ต้องนำเข้า CodeWalker เพื่อแปลงเป็นไบนารีก่อน stream (FiveM โหลด `.xml` ไม่ได้) |

สถานะเครื่องนี้ (2026-11-19): Sollumz 2.9.1 + szio 1.4.0 + PyMateria 0.2.1 ติดตั้งแล้วทั้ง Blender 4.2.3 และ Steam 5.3 (ผู้ใช้ยอมรับสัญญา PyMateria เองแล้ว) ใช้ `--format native` ได้เลย ยังไม่มี CodeWalker

ข้อควรรู้:

- Blender 4.2.3 แครชตอนปิดโปรแกรมหลัง export (`EXCEPTION_ACCESS_VIOLATION` ใน `node_free_node`) ไฟล์เขียนเสร็จแล้วก่อนแครช สคริปต์จึงพิมพ์ผลแบบ flush แล้วออกด้วย `os._exit` และแยก process ต่อชิ้น ห้ามเอาสองอย่างนี้ออก
- ytyp เป็นหนึ่งไฟล์ต่อหนึ่ง prop (`<id>.ytyp`) แบบเดียวกับ `1nfx_prop` ที่มีอยู่ ต้องเพิ่ม `data_file "DLC_ITYP_REQUEST"` ทีละไฟล์
- texture ฝังใน `.ydr` ของแต่ละชิ้น (palette 256x256 DXT5 ราว 90 KB ต่อชิ้น) archetype จึงมี `textureDictionary` = `<id>` ถ้าอยากใช้ ytd ร่วมทั้งชุดต้องแก้ใน Sollumz เอง
- ชื่อ model ห้ามซ้ำกับ prop อื่นทั้งเซิร์ฟเวอร์ ค้นใน `resources` ก่อนตั้งชื่อ
