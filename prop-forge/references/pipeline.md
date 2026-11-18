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

ยังไม่มีตัว export ตรงสำหรับ prop เหมือน `../weapon-forge/scripts/blender/export_ydr.py` (ตัวนั้นทำเฉพาะอาวุธที่มี skeleton) ทาง export ที่ใช้คือ Sollumz ใน Blender ถ้าเครื่องยังไม่มี ให้ถามผู้ใช้ก่อนติดตั้ง ขั้นตอนด้านล่างเขียนตาม Sollumz 2.x ให้ตรวจชื่อเมนูกับเวอร์ชันที่ติดตั้งจริงทุกครั้ง

1. เปิด `<id>.blend` เลือก mesh `<id>` แล้ว Convert เป็น Drawable (Sollumz Tools) ตั้งชื่อ Drawable = `<id>`
2. แปลงวัสดุเป็น Sollumz shader: `<id>_diffuse` เป็น `default.sps` (หรือ `spec.sps` ถ้าอยากได้เงา), `<id>_emissive` เป็น `emissive.sps`, decal เป็น `decal.sps`; ตั้ง texture ของ DiffuseSampler เป็น `<set>_palette` (หรือ `<id>_atlas`) แล้วตั้งให้ไม่ embed ถ้าจะใช้ ytd ร่วมทั้งชุด
3. เลือก `<id>_col_*` ทั้งหมด แปลงเป็น Bound Composite ที่มี Bound Box ลูก แล้ว parent เข้า Drawable (embedded collision) ตั้ง collision material เป็นพลาสติก
4. สร้าง ytyp: เพิ่ม archetype จาก Drawable, `name` = `<id>`, `textureDictionary` = ชื่อ ytd ของชุด (เช่น `1nfx_goo_txd`) หรือ `<id>` ถ้า embed, `lodDist` ตาม `report.json`, asset type = drawable
5. Export `.ydr` และ `.ytyp` (Sollumz บางเวอร์ชันได้ `.ydr.xml`/`.ytyp.xml` ให้นำเข้า CodeWalker เพื่อแปลงเป็นไบนารี) และสร้าง `.ytd` ของชุดที่มี texture palette (DXT1 พอเพราะไม่มี alpha, DXT5 ถ้ามี decal โปร่งใส)
6. ตรวจด้วย CodeWalker ว่าเปิด `.ydr` ได้ เห็น texture และกล่องชน ก่อนส่งให้ผู้ใช้ทดสอบในเกม

ชื่อไฟล์ทั้งหมดต้องตรงกัน: `<id>.ydr`, archetype `<id>` ใน `<set>.ytyp` หรือ `<id>.ytyp`, texture dictionary ตามที่ตั้งใน ytyp ชื่อ model ห้ามซ้ำกับ prop อื่นทั้งเซิร์ฟเวอร์ (ค้นใน `resources` ก่อนตั้งชื่อ)
