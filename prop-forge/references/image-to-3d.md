# Image-to-3D: เจนรูปแล้วปั้นออกมาเป็น prop

สายที่สามของ prop-forge ใช้เมื่อชิ้นงานเป็นทรงออร์แกนิกที่ primitive ทำไม่ถึง: มาสคอตตุ๊กตา, ฟิกเกอร์นั่งบนตู้, เมฆ, หัวสัตว์ครอบตู้, โลโก้ 3D ตัวหนา, เครื่องเล่นทรงสัตว์ ส่วนทรงกล่อง/ป้าย/ตู้เรียบยังปั้นด้วย `forge_prop.py` หรือ `kawaii_studio.py` เหมือนเดิมเพราะคมกว่าและเบากว่า

```text
โจทย์ + พาเลตต์แบรนด์
  -> 1. Concept sheet (image gen)         รูป 3/4 พื้นขาว ชิ้นเดียว ไม่มีพื้น
  -> 2. Image-to-3D (บริการหรือโมเดลโลคัลตัวใดก็ได้)       ได้ .glb พร้อม texture
  -> 3. import_ai_prop.py (Blender 4.2.3 CLI)             ย่อ tris + อบ atlas ใหม่ + origin + ชน
  -> 4. แต่งใน Blender 5.3 สดผ่าน MCP (ถ้าจำเป็น)          แยกชิ้นขยับ ใส่ emissive/decal
  -> 5. validate_prop.py -> export_prop.py -> 1nfx_prop    .ydr + .ytyp (+ .ycd) + shared .ytd
```

## เลือกสาย

ผู้ใช้ปั้นด้วย Antigravity + Blender MCP และ **ไม่ใช้ Tripo** (ถอด Tripo Bridge ออกจาก Blender 5.3 แล้วเมื่อ 2026-11-23) ไม่มีบริการ image-to-3D ประจำ ให้เลือกสายตามลำดับนี้ทุกครั้ง:

| ระดับ | ใช้เมื่อ | เครื่องมือ | ค่าใช้จ่าย |
| --- | --- | --- | --- |
| A. Builder ล้วน | ตู้ ป้าย กล่อง โต๊ะ เสา และมาสคอตทรงง่าย (หัวกลม หมี เมฆ ดาว หัวใจ สายฟ้า) | `forge_prop.py` / `kawaii_studio.py` ผ่าน Antigravity | 0 |
| B. ปั้นออร์แกนิกเองใน Blender (สายหลักของงานออร์แกนิก) | มาสคอตตัวเต็มหรือทรงสัตว์ที่ builder ไม่มี | Antigravity + Blender MCP: ทรงรีหลายก้อน + voxel remesh ตามหัวข้อ "ปั้นออร์แกนิกเอง" | 0 |
| C. บริการ image-to-3D ภายนอก (เมื่อผู้ใช้สั่งใช้เท่านั้น) | ชิ้นฮีโร่ที่ทรง B ไม่ถึง เช่น ฟิกเกอร์ไดโอรามาละเอียด | บริการใดก็ได้ที่ export `.glb` -> `import_ai_prop.py` | ตามบริการ ผู้ใช้เป็นคนสมัครและใส่ key เอง |
| D. โมเดลโลคัล (ตัวเลือก) | อยากได้ image-to-3D ไม่จำกัดโดยไม่เสียเครดิต | Hunyuan3D-2 mini / TripoSR บนเครื่อง (RTX 5070 12 GB พอสำหรับรุ่นเล็ก) | 0 แต่ต้องติดตั้ง Python + PyTorch ก่อน ยังไม่ได้ติดตั้ง |

กฎ:

- ตัวตู้ ป้าย โต๊ะ กล่อง ปั้นด้วย builder เสมอ คมกว่า เบากว่า และแก้สีได้ ไม่ส่งเข้า image-to-3D
- มาสคอตตัวเต็มทำตัวเดียวต่อชุดแล้ววางซ้ำบนทุกชิ้นด้วยการหมุน ย่อ และตัดครึ่งตัว ไม่ปั้นมาสคอตใหม่ต่อชิ้น
- ตรวจรูป concept ให้ผ่านเกณฑ์ข้อ 1 ก่อนส่งเข้าสายใดก็ตาม
- ชุดสีสลับทำด้วยการแก้ atlas หรือ palette ไม่เจนใหม่
- เก็บ `.glb` ต้นทางทุกไฟล์ไว้ใน `work/<set>/ai/` และคลังกลาง `work/_library/ai/` เพื่อใช้ซ้ำข้ามชุด

## MCP ที่ใช้

| MCP | หน้าที่ | สถานะเครื่องนี้ (2026-11-22) |
| --- | --- | --- |
| `blender` (Blender Foundation, 26 เครื่องมือ, `<home>\blender-mcp`) | คุม Blender 5.3 สด: `execute_blender_code`, `get_objects_summary`, `render_viewport_to_path`, ค้นคู่มือ API | ติดตั้งแล้วทั้ง Antigravity (`%USERPROFILE%\.gemini\config\mcp_config.json`) และ Claude Code |
| `fivem-mcp` | ค้น native, ตรวจ `fxmanifest.lua`, รีวิว Lua ตอนเชื่อม prop เข้า resource | ติดตั้งแล้ว (`.mcp.json` ของโปรเจกต์) |
| `meshy` (`@meshy-ai/meshy-mcp-server`, ทางการ) | image-to-3D, multi-image-to-3D, remesh, retexture, rig, download ลง `meshy_output/` | **ยังไม่ติดตั้ง** ต้องมี Node >= 18 ใน PATH และ API key (Pro ขึ้นไป) |
| ตัวเจนรูปใน Antigravity | Concept sheet และ decal | มีในตัว ไม่ต้องใช้ MCP (`../poster-forge/scripts/agy-gen.ps1`) |

ขั้นต่ำที่ทำงานได้ครบคือ `blender` MCP + ตัวเจนรูปของ Antigravity (สาย A และ B ไม่ต้องใช้บริการภายนอกเลย) ถ้าผู้ใช้เลือกใช้บริการ image-to-3D ให้โหลด `.glb` มาวางใน `work/<set>/ai/` MCP ของ Meshy แค่ทำให้ agent สั่งเจนและโหลดเองได้

เพิ่ม Meshy ใน `mcp_config.json` ของ Antigravity (เปิดจาก Manage MCP Servers > View raw config) ผู้ใช้ใส่ key เอง agent ห้ามสร้างบัญชี ห้ามพิมพ์ key ลงไฟล์ใน repo:

```json
{
  "mcpServers": {
    "meshy": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@meshy-ai/meshy-mcp-server"],
      "env": { "MESHY_API_KEY": "<ใส่เอง>" }
    }
  }
}
```

## 1. Concept sheet

กฎของรูปที่ image-to-3D อ่านออกดี:

- ชิ้นเดียวต่อรูป เต็มเฟรม 80% มุม 3/4 ด้านหน้า กล้องสูงระดับอก ไม่ใช่มุมเงยหรือมุมก้ม
- พื้นหลังขาวหรือเทาเรียบ ไม่มีพื้น ไม่มีเงาตก ไม่มีฉาก ไม่มีตัวละครอื่น
- แสงนุ่มทั่วชิ้น ไม่มี rim light จัด ไม่มี bloom ไม่มี depth of field (เงาและแสงในรูปจะถูกอบติดลง texture)
- ทรงหนา อ้วน ขอบมน ไม่มีเส้นบาง ลวด สายเคเบิล ใบไม้แผ่นเดียว หรือของโปร่งใส (สิ่งพวกนี้ออกมาเป็นก้อนเละ ให้เติมเองใน Blender)
- ตัวหนังสือและโลโก้บนตัว prop ให้เว้นเป็นป้ายเปล่า แล้วแปะ decal ที่เจนแยกทีหลัง (AI 3D ทำตัวหนังสือเบี้ยวทุกครั้ง)
- ชิ้นที่ต้องขยับ (ฝา แขน ธนบัตร มงกุฎลอย) เจนเป็นรูปแยกชิ้น หรือเจนท่าเปิดให้เห็นรอยต่อชัด

พรอมต์ตั้งต้น (แก้ชื่อชิ้น ธีม และ hex สี):

```text
Single collectible vinyl toy prop, [ATM kiosk shaped like a candy shop with a striped awning and a plush bunny mascot hugging its side], chunky rounded proportions, thick soft bevels, smooth matte plastic with subtle gloss, pastel palette [#F7C6D9 pink, #FFF6EC cream, #F2B84B gold], blank sign plate with no text, three-quarter front view, eye-level camera, centered, full object visible, plain white background, soft even studio light, no ground shadow, no scene, no extra objects, no text, no watermark.
```

เจนทั้งชุดด้วยพรอมต์โครงเดียวกัน เปลี่ยนเฉพาะวงเล็บแรก เพื่อให้ทุกชิ้นได้ภาษาทรงและสีชุดเดียว ถ้าใช้ multi-image-to-3D ให้เจนเพิ่มมุมหลังและด้านข้างด้วยคำสั่ง "same object, back view" จากรูปแรก

ห้ามใช้เฟรมจากคลิปอ้างอิง รูปสินค้าของเล่นจริง หรือตัวละครมีลิขสิทธิ์เป็นภาพตั้งต้นของ image-to-3D ทุกชิ้นต้องมาจาก concept ที่เจนใหม่ด้วยมาสคอตและชื่อแบรนด์ของเซิร์ฟเวอร์เอง

## 2. Image-to-3D

เครื่องนี้ไม่มี `node`/`npx`/`uv` ใน PATH ถ้าจะใช้ MCP ของ Meshy ต้องลง Node LTS ก่อนและรีสตาร์ต Antigravity หลังแก้ config

### ค่ากลางสำหรับบริการภายนอก (สาย C)

| ตั้งค่า | ค่าที่ใช้ |
| --- | --- |
| โหมด | image-to-3D จากรูปเดียว หรือ multi-image เมื่อด้านหลังสำคัญ |
| Meshy | `ai_model: "latest"`, `texture_resolution: "2k"`, เปิด PBR; ถ้าใช้ `model_type: "smart-topology"` ตั้ง `target_polycount` 15000-30000 |
| Polycount ตอนเจน | เอาละเอียดไว้ก่อน (30k-300k) แล้วให้ `import_ai_prop.py` ย่อ ห้ามให้บริการย่อเหลือ 3k เพราะรอยอบจะหยาบ |
| ท่า | ตัวละครที่ต้องริกเอง: A-pose; ตัวละครที่เป็นรูปปั้นนิ่ง: ท่าจบเลย |
| รูปแบบไฟล์ | `.glb` (texture ฝังในไฟล์) |

เก็บไฟล์ต้นทางไว้ที่ `work/<set>/ai/<id>.glb` พร้อมรูป concept `work/<set>/concept/<id>.png` ห้ามแก้ทับ

ตรวจก่อนรับ: หน้าตามาสคอตไม่เพี้ยน, ไม่มีรูทะลุ, ด้านหลังไม่แบนเป็นกระดาษ, ไม่มีฐานหรือพื้นติดมา ถ้าไม่ผ่านให้แก้รูป concept แล้วเจนใหม่ ถูกกว่าซ่อม mesh เสมอ

## ปั้นออร์แกนิกเองด้วย Antigravity + Blender MCP (สาย B)

ใช้กับมาสคอตและทรงสัตว์ทุกชิ้นที่ builder ไม่มี ผลลัพธ์เป็นทรงของเล่นไวนิลเรียบ ๆ ซึ่งตรงกับสไตล์ชุด prop อยู่แล้ว ไม่เหมาะกับขน ผ้ายับ หรือหน้าคนสมจริง

**ขั้นที่ 0 ลอง builder ก่อน.** `kawaii_studio.py` มี `billie_bear_plush`, `plush_cloud`, `plush_cloud_pillow`, `plush_star`, `plush_heart`, `plush_lightning`, `plush_pill`, `plush_sphere`, `plush_tube`, `plush_coin`, `plush_banknote`; `forge_prop.py` มี `mascot`, `billie_bear`, `metaball_slime`, `slime_cap_mb`, `fat_drip` ถ้าประกอบจากพวกนี้ได้ให้จบที่สาย A

**ขั้นที่ 1 แตกรูป concept เป็นก้อน.** ให้ Antigravity ดูรูป concept แล้วเขียนรายการก้อนเป็นตาราง: ชื่อส่วน, ทรง (ทรงกลม/แคปซูล/วงรี), ตำแหน่ง, รัศมีสามแกน, สี มาสคอตตัวเต็มหนึ่งตัวใช้ 14-22 ก้อน: หัว 1, แก้ม 2, หู 2-4, ลำตัว 1, แขน 2 (แคปซูล), มือ 2, ขา 2, เท้า 2, หาง 1, ของประดับ 2-4 สัดส่วนของเล่น: หัวสูง 45-55% ของตัว, ไม่มีคอ, แขนขาสั้นอ้วน

**ขั้นที่ 2 สร้างก้อนเป็นทรงรีแล้วหลอมด้วย voxel remesh.** ผ่าน `execute_blender_code` (หรือ CLI): ใช้ `bmesh.ops.create_uvsphere(radius=1, u_segments=24, v_segments=16)` ต่อก้อน แล้ว transform ด้วย `Translation @ Rotation @ Diagonal(rx, ry, rz)` ตามตาราง ขนาดที่ได้ตรงกับตัวเลขในตารางพอดี รวมทุกก้อนใน mesh เดียวแล้วตั้ง `mesh.remesh_voxel_size = 0.012` และ `bpy.ops.object.voxel_remesh()` ก้อนที่ซ้อนกันจะหลอมเป็นผิวเดียว ส่วนที่ต้องเชื่อมเนียน (แขนกับตัว, หูกับหัว) ให้จมเข้ากัน 30-40% ของรัศมี ส่วนที่ต้องมีรอยต่อคม (ฮู้ดกับหน้า, ของถือในมือ) ให้ทำเป็น object แยกแล้ว join หลังเกลาผิว

อย่าใช้ MetaBall object สำหรับงานนี้: ผิวที่ได้เล็กกว่า `radius` ราว 0.575 เท่า (ที่ `threshold = 0.6`) และ `size_x/y/z` ของ `ELLIPSOID`/`CAPSULE` ไม่ใช่สเกลตรง ๆ ทำให้หูหลุดจากหัวและแขนยาวเกิน (ลองแล้ว 2026-11-23) metaball ใช้ผ่าน builder สไลม์ของ `forge_prop.py` ที่ปรับค่าไว้แล้วเท่านั้น

**ขั้นที่ 3 เกลาผิว.** `Smooth` modifier 8 รอบ factor 0.5, แล้ว Decimate ให้เหลือ 2,500-5,000 tris, `shade_smooth` ห้ามเปิด Sculpt mode ผ่าน MCP (brush stroke ต้องมี viewport จริงและทำซ้ำไม่ได้) ใช้ modifier และ `bmesh` เท่านั้น

ตารางตั้งต้นของมาสคอตกระต่ายยืนสูง 1.2 ม. (ตำแหน่ง, รัศมี x/y/z, เอียงรอบ Y) ที่ลองแล้วได้ทรงอ่านออกใน 4,000 tris ย่อขยายทั้งตารางตามความสูงที่ต้องการ:

| ส่วน | ตำแหน่ง | รัศมี | เอียง |
| --- | --- | --- | --- |
| หัว | 0, 0, 0.66 | 0.30, 0.28, 0.27 | 0 |
| ตัว | 0, 0, 0.27 | 0.21, 0.18, 0.22 | 0 |
| แขน | ±0.22, 0, 0.30 | 0.07, 0.07, 0.13 | ±40 |
| เท้า | ±0.10, -0.03, 0.06 | 0.09, 0.11, 0.06 | 0 |
| หู | ±0.13, 0, 1.02 | 0.07, 0.05, 0.20 | ±8 |
| หาง | 0, 0.19, 0.22 | 0.07, 0.07, 0.07 | 0 |

**ขั้นที่ 4 หน้าตาและรายละเอียด.** ตา ปาก แก้มแดง จมูก ลายเสื้อ ทำเป็น geometry แผ่นโดมบาง (`decal_disc` / ทรงกลมแบนฝังผิว 1-2 มม.) หรือ decal PNG ที่เจนด้วย Antigravity ตาม `pipeline.md` ตาต้องเป็นทรงนูนจริงอย่างน้อยหนึ่งชั้นเพื่อให้มีประกายตอนหมุน

**ขั้นที่ 5 ลงสี.** ให้ทุกส่วนชี้ UV ไปช่องสีใน palette ของชุด (`<set>_palette` หรือ master palette ของ `kawaii_studio.py`) ตามสีในตารางขั้นที่ 1 ไม่ต้องอบ texture ใหม่ จึงเข้าชุดกับตัวตู้ทันทีและกิน VRAM เพิ่ม 0

**ขั้นที่ 6 ตรวจเทียบ concept.** เรนเดอร์หน้า ข้าง 3/4 ด้วย `render_viewport_to_path` เปิดดูเทียบรูป concept ทุกรอบ แก้ตารางก้อนแล้วรันขั้น 2-3 ซ้ำจนซิลูเอตต์ตรง เมื่อผ่านให้ย้ายโค้ดเป็น method ใหม่ใน `kawaii_studio.py` (เช่น `bunny_plush`) เพื่อให้ชุดถัดไปเรียกใช้ได้โดยไม่ต้องปั้นใหม่

คำสั่งตั้งต้นให้ Antigravity:

```text
ใช้ skill prop-forge อ่าน references/image-to-3d.md หัวข้อ "ปั้นออร์แกนิกเองด้วย Antigravity + Blender MCP" แล้วปั้นมาสคอตตามรูป work/<set>/concept/<id>.png ด้วย Blender MCP: เขียนตารางก้อนก่อน สร้างทรงรีแล้วหลอมด้วย voxel remesh เกลาด้วย smooth+decimate ลงสีด้วย palette ของชุด เรนเดอร์ 3 มุมเทียบ concept ทุกรอบ งบ 4,000 tris ห้ามใช้ Sculpt mode
```

### ตัวเลือก D: image-to-3D บนเครื่อง

เครื่องนี้มี RTX 5070 12 GB + RAM 31 GB รันโมเดลเปิดขนาดเล็กได้ (Hunyuan3D-2 mini หรือ TripoSR) ผลลัพธ์หยาบกว่าบริการเสียเงิน แต่ไม่จำกัดจำนวน ไฟล์ที่ได้เข้า `import_ai_prop.py` เหมือนกันทุกประการ ยังไม่ได้ติดตั้ง: ต้องลง Python 3.10+, PyTorch รุ่นที่รองรับการ์ดซีรีส์ 50 และโหลดน้ำหนักโมเดลหลาย GB ให้ผู้ใช้สั่งก่อนจึงติดตั้ง

## 3. import_ai_prop.py

```powershell
& 'C:\Tools\blender-4.2.3-windows-x64\blender.exe' -b --factory-startup -P "$skill\scripts\blender\import_ai_prop.py" -- --src work\ai\bunny_atm.glb --id 1nfx_brand_atm --out work\build --height 1.9 --tris 6000 --bake 1024 --glossy
```

| ตัวเลือก | ความหมาย | ค่าเริ่ม |
| --- | --- | --- |
| `--height` / `--width` | ขนาดจริงเป็นเมตร (สูง Z หรือกว้าง X) ใส่อย่างใดอย่างหนึ่ง | สูง 1.6 |
| `--tris` | งบสามเหลี่ยมหลังย่อ | 6000 |
| `--bake` | ขนาด atlas (256-2048 ยกกำลังสอง) | 1024 |
| `--yaw` | หมุนรอบ Z (องศา) ให้หน้าหัน -Y | 0 |
| `--rot x,y,z` | หมุนเพิ่มเมื่อโมเดลนอนหรือคว่ำ | 0,0,0 |
| `--strip-islands` | ลบเศษลอยที่เล็กกว่าสัดส่วนนี้ของชิ้นใหญ่สุด (วัดเส้นทแยง) 0 = ปิด | 0.04 |
| `--ao` | น้ำหนัก AO ที่อบผสมลงสี 0-1 | 0.45 |
| `--glossy` | ใช้ `default_spec.sps` ผิวไวนิลเงา | ปิด |
| `--colliders` | จำนวนกล่องชนซ้อนตามแนวสูง 0 = ไม่มีชน (marker) | 3 |
| `--lod-dist` | `lodDist` ใน ytyp | 100 |

ได้ `<id>.blend`, `<id>_atlas.png`, `<id>_preview.png`, `<id>_import.json` สิ่งที่สคริปต์ทำ: รวม mesh, เชื่อมจุดซ้ำแล้วลบเศษลอย, ย่อขนาดและวางกลางพื้น z = 0, weld + decimate, smart UV ใหม่, อบสีจากโมเดลละเอียดลง atlas เดียว (ตั้ง Metallic = 0 ก่อนอบกันสีมืด), ผสม AO, เติมพื้นที่ว่างของ atlas ด้วยสีเฉลี่ยกันขอบดำ, สร้างกล่องชน `<id>_col_N`, เขียน metadata `prop_forge`

งบแนะนำ:

| ชิ้น | tris | atlas |
| --- | --- | --- |
| marker / ของลอยขนาดเล็ก (< 0.6 ม.) | 1,500-3,000 | 512 |
| มาสคอตยืน, กล่อง, ตู้เซฟ (0.6-1.4 ม.) | 3,000-6,000 | 1024 |
| ATM, ตู้คีบ, เครื่องเล่น (1.4-2.4 ม.) | 6,000-9,000 | 1024 |
| โต๊ะคราฟต์, ป้ายรถเมล์, ซุ้ม (> 2.4 ม.) | 9,000-14,000 | 1024 สองใบ (แยกตัวถังกับป้าย) |

เปิด `<id>_preview.png` ดูทุกครั้ง ถ้าหน้ามาสคอตบุบให้เพิ่ม `--tris` ทีละ 1,500 ก่อนเพิ่มขนาด atlas ถ้า `atlas_coverage` ใน `_import.json` ต่ำกว่า 0.6 แปลว่าชิ้นมีเกาะ UV เล็กมากเกินไป ให้เพิ่ม `--weld` เป็น 0.001

## 4. แต่งต่อใน Blender 5.3 ผ่าน MCP

ทำเฉพาะที่จำเป็น และจดลง `source/manual-edits.md`:

- **ป้ายและจอ:** ตัดหน้าป้ายเปล่าออก ใส่แผ่น decal (`<id>_decal_0`, `decal.sps`) จากโลโก้ที่เจนแยกตาม `pipeline.md`
- **ส่วนเรืองแสง:** เลือกหน้าไฟ/จอ/นีออน แยกเป็นวัสดุ `<id>_emissive` (`prop_forge_shader = "emissive.sps"`) ชี้ texture เดิม ไม่เกิน 4 วัสดุต่อชิ้น
- **ชิ้นขยับ:** แยกด้วย `mesh.separate` ตามเกาะ (ฝา, แขน, ธนบัตร, มงกุฎ) แล้วอุดรูที่เกิดจากการแยก ริกตามกติกา `.ycd` ใน `pipeline.md` (กระดูกชี้ +Y ยาว 0.05, vertex group น้ำหนัก 1.0, Action อบรายเฟรม) ใส่ `meta["anim"]` ให้ `validate_prop.py` ตรวจ
- **กล่องชน:** กล่องอัตโนมัติเป็นกล่องซ้อนตามความสูง ถ้าชิ้นมีหลังคายื่นหรือโต๊ะมีขา ให้ลบแล้ววางกล่องเองเฉพาะส่วนที่ผู้เล่นชนจริง
- **Med LOD:** ชิ้นที่วางซ้ำทั่วแมพ duplicate แล้ว Decimate 0.4 เป็น LOD กลาง

ไฟล์ที่บันทึกจาก 5.3 เปิดด้วย 4.2.3 CLI ไม่ได้ ให้ validate และ export ต่อใน 5.3 หรือส่งกลับเป็น `.glb` ตาม `antigravity.md`

## 5. ตรวจและ export

```powershell
& $blender -b --factory-startup -P "$skill\scripts\blender\validate_prop.py" -- --blend work\build
& $blender -b -P "$skill\scripts\blender\export_prop.py" -- --blend work\build --out work\stream --format native --max-res 1024 --shared-ytd 1nfx_brand_tex
```

ต้องได้ `RESULT fail=0 warn=0` ก่อน export แล้วเชื่อมเข้าเซิร์ฟเวอร์ตาม `integration.md`

## เกณฑ์ผ่านของชิ้นจาก AI

- มองจาก 5 เมตรอ่านออกทันทีว่าเป็นอะไร และเข้าชุดกับชิ้นอื่น (สี ทรง ความมนเท่ากัน)
- ไม่มีแสงเงาอบติดผิดด้าน (ด้านหนึ่งสว่างด้านหนึ่งมืดถาวร) ถ้ามีให้เจน concept ใหม่ด้วยแสงเรียบ
- ไม่มีตัวหนังสือเบี้ยวจาก AI เหลืออยู่ ตัวหนังสือทุกตัวเป็น decal
- ไม่มีชื่อ โลโก้ หรือตัวละครของคนอื่น
- ฐานแบน วางพื้นแล้วไม่ลอยไม่จม ผู้เล่นยืนชิดได้ไม่ทะลุ
- ทั้งชุดรวม texture ใน `.ytd` เดียว ไม่เกิน 12 MB

## สิ่งที่พิสูจน์แล้ว

- 2026-11-22: `import_ai_prop.py` กับ GLB ทดสอบ 252k tris (วัสดุ Metallic 0.8 + เศษลอย 1 ชิ้น) -> 4,999 tris, atlas 512, กล่องชน 3, `validate_prop.py` `fail=0 warn=0`, `export_prop.py --format native` ได้ `.ydr` + `.ytyp` ผ่าน `verify_native_ydr` ยังไม่ได้ลองกับไฟล์จากบริการ image-to-3D จริง และยังไม่ได้ลองในเกม
- 2026-11-23: สาย B ทรงรี 9 ก้อน + voxel remesh 0.012 + smooth 8 รอบ + decimate บน Blender 4.2.3 headless ได้มาสคอตกระต่ายสูง 1.21 ม. 4,000 tris ซิลูเอตต์อ่านออก ยังไม่ได้ลงสี ใส่หน้า หรือ export
