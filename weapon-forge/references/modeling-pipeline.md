# Modeling Pipeline

## เครื่องมือในเครื่องนี้

รัน `scripts/doctor.ps1` ก่อนเริ่มงาน เพราะสถานะเปลี่ยนได้ ผลตรวจล่าสุดเมื่อ 2026-11-15:

| เครื่องมือ | สถานะ |
| --- | --- |
| Blender 4.2.3 (CLI & Export) | มี: `C:\Tools\blender-4.2.3-windows-x64\blender.exe` (ใช้บันทึก `.blend` ฟอร์แมต `BLENDER-v402` ที่เปิดได้ทั้งใน 4.2.3 CLI และ 5.3 GUI — ห้ามเซฟทับเป็น `BLENDER17` ของ 5.0+ ลง `source/*.blend`!) |
| Steam Blender 5.3 (Live GUI + MCP) | มี: `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe` พร้อม `bl_ext.lab_blender_org.mcp` (`localhost:9876`, ดูวิธีรันใน `references/antigravity.md`) |
| Antigravity CLI & `blender` MCP | **มีและพร้อมใช้งาน (`READY`):** `agy 1.5.9` + `<home>\blender-mcp\uv.exe` เชื่อมต่อ 26 tools (ทั้งโหมด CLI headless `*_for_cli` และโหมด Live GUI ดูคู่มือครบใน `references/antigravity.md`) |
| Sollumz, PyMateria | **ไม่มี** (ใช้ `scripts/blender/export_ydr.py` คอมไพล์ RSC7 `.ydr`/`.ytd` ได้โดยตรง) |
| CodeWalker | **ไม่มี** (ใช้ `scripts/inspect-ydr.ps1` และ `scripts/ptfx/ptfx.ps1` ตรวจโครงสร้างไบนารีแทน) |
| Python ระบบ, Node, ffmpeg, texconv | ไม่มีใน PATH ใช้ Blender Python (`bpy`) กับ PowerShell 5.1 แทน (`python.exe` ใน WindowsApps เป็นทางลัดไป Microsoft Store) |
| GTA V | ขึ้นกับเครื่อง (ถ้าไม่มี ให้ดึงขนาดและตำแหน่งกระดูกมาตรฐานจาก `references/weapon-anatomy.md` และ `validate_model.py`) |

Sollumz รุ่นล่าสุดคือ 2.9.0 (ส.ค. 2026) ต้องใช้ Blender 4.2.0 ขึ้นไปตาม manifest ของรุ่นนี้ และติดตั้งเป็น extension จาก `https://repo.sollumz.org/` ([เอกสารติดตั้ง](https://docs.sollumz.org/getting-started/installation)) ตัว add-on จะโหลด `szio` เองเมื่อเปิดใช้ ส่วน `pymateria` เป็นตัวเลือกเฉพาะ Windows ที่ต้องยอมรับ[สัญญาของ Cfx](https://static.cfx.re/PyMateria-License-Agreement.pdf) ใน preferences การติดตั้งเป็นการเปลี่ยนแปลงในเครื่องผู้ใช้ จึงต้องถามก่อน

## forge_weapon.py

```powershell
$b = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
& $b -b --factory-startup --python-exit-code 1 -P scripts\blender\forge_weapon.py -- --spec spec.json --out DIR --samples 16
```

| ตัวเลือก | ผล |
| --- | --- |
| `--spec` | ไฟล์ spec ดู `templates/skin-spec.example.json` |
| `--out` | โฟลเดอร์ผลลัพธ์ แนะนำ `weapon_<id>\source` |
| `--only poolcue,bat` | สร้างเฉพาะบางช่อง |
| `--bake 1024` | bake texture ทุกชิ้น แล้วเปลี่ยนเป็นวัสดุเดียว |
| `--icons` | render `icon_<slot>.png` ขนาด 96×96 พื้นโปร่งใส |
| `--no-sheet` | ไม่ render ภาพรวม |
| `--focus 0.85,1.0` | ซูมภาพรวมเข้าช่วงความสูงของชิ้น (สัดส่วน 0–1) ใช้ดูรายละเอียดส่วนปลาย |
| `--yaw 55` | หมุนชิ้นรอบแกนยาวก่อน render เพื่อดูมุม 3/4 หรือด้านหน้า (สนับมือหมุนเพิ่ม -90° เสมอ) |
| `--ydr [DIR]` | สร้าง `.ydr` (RSC7 v165) + `.ytd` (v13) + `.dds` (DXT5) ลง `stream/` โดยอัตโนมัติ (ต้องเปิด `--bake` คู่กัน) พร้อมติดแท็ก Sollumz 2.6+ (`sollumz_drawable`, `Bound Composite` + `Bound Box`) ใน `.blend` |

ผลลัพธ์: `<id>_sheet.png`, `<model>.blend`, `<model>_d.png` + `<model>_d.dds` (ถ้า bake), `<model>.ydr` + `<model>.ytd` (ถ้า `--ydr`), `forge_report.json` บอก tris และ bbox

ทั้งชุด 7 ชิ้นพร้อม bake ใช้เวลาหลักสิบวินาทีบนเครื่องนี้ จึงวนแก้ได้หลายรอบ

## วงจรการปั้น

1. เขียน spec แล้วรันแบบไม่ bake
2. **เปิดดู `<id>_sheet.png` ทุกครั้ง** เทียบกับ DNA ของ family และเกณฑ์ตรวจหน้าตาใน `style-families.md`
3. แก้ `style`/`palette` หรือเติมชิ้นใหม่ใน `forge_weapon.py` แล้วรันซ้ำ
4. ดูจนลงตัวแล้วค่อย `--bake 1024 --icons`
5. รัน `validate_model.py` กับทุก `.blend` แก้จนไม่มี FAIL ค่า WARN เรื่องระยะ Z ให้ตัดสินใจเป็นชิ้น ๆ เช่นคะตะนะในช่อง Bottle ตั้งใจให้ยาวเกิน

```powershell
& $b -b --factory-startup --python-exit-code 1 -P scripts\blender\validate_model.py -- --blend model.blend
```

ผล forge คือ **ฐานที่สเกลและโครงถูกต้อง** ยังไม่ใช่งานจบระดับภาพโปรโมต ส่วนที่ต้องต่อด้วยมือหรือด้วยการแก้สคริปต์เพิ่ม: รูปนูนสลัก (พระแม่, มังกรเต็มตัว), ตัวอักษร, สติกเกอร์ลายละเอียด งบ tris ยังเหลือมาก (forge ใช้ราว 1k–9k จาก 25k) จึงเพิ่มรายละเอียดได้

### เพิ่มชิ้นส่วนใหม่

- ลายแบน: เพิ่มใน `motif_loops()` เป็นลูปพิกัด -1…1 ลูปซ้อนในจะกลายเป็นรู
- ชิ้นกลึง: `lathe([(r, z), ...], seg)`
- สาย/เกลียว: `tube(helix(...), radius)`
- วางบนก้าน: `badge_on_shaft()` วางบนใบมีด: `badge_on_face()`
- ส่งเข้าโมเดลด้วย `forge.put(bmesh, key, matrix)` โดย `key` ∈ `primary secondary accent glow grip metal`

## กฎการปั้น Hero Brick / Modular Stud และบทเรียนจากโมเดลจริง

ผลวิเคราะห์เชิงลึกจากชุดภาพอ้างอิง 29 ชุด (`Downloads/weaponphoto`) และการผ่าโครงสร้าง `weapon_lego/source/*.blend` รุ่นเก่า พบบทเรียนสำคัญที่ใช้บังคับกับตระกูล `brick_modular` และงานปั้นโมดูลาร์ทุกชุด:

1. **หลีกเลี่ยงกับดักโพลีจากปุ่มรอบทรงกระบอก (`37,276-tri` Radial Stud Trap):**
   - *ปัญหาจริงที่พบ:* `w_me_lego_poolcue.blend` รุ่นเก่าจำลองก้านไม้คิวด้วยการเรียงปุ่มทรงกระบอก 26 segments รอบก้านกว่า 700 ปุ่มพร้อมฝาปิดก้นปุ่มที่จมอยู่ในเนื้อโมเดล ทำให้พุ่งถึง `37,276 tris` (เกินเพดาน `25,000 tris` ของช่องอาวุธ)
   - *กฎมาตรฐาน Hero Brick:* ขยายสัดส่วนตารางบล็อกขึ้น ~25% เป็น **Hero Pitch `10–12 mm`** (เส้นผ่านศูนย์กลางปุ่ม `6.0 mm`, สูง `2.0–2.2 mm`) เพื่อให้เห็นชัดในระยะบุคคลที่สามของ GTA V สร้างปุ่มทรงกระบอกด้วย **10–12 segments แบบเปิดฐานล่าง (`open-bottom cap`)** ซึ่งใช้เพียง `20–36 tris/ปุ่ม` และวางเฉพาะสันเด่น 1–2 แถวสลับแผ่นเรียบ SNOT (รวมทั้งชิ้น `60–140` ปุ่ม อยู่ในงบ `4,500–14,000 tris` อย่างสบาย)
2. **โซนมือจับเรียบ SNOT (`Gun_GripR` & `Gun_GripL` Hand-Safe Zones):**
   - ห้ามวางปุ่ม stud หนาม หรือครีบคมในรัศมี `±0.055 m` รอบ `Gun_GripR` ของทุกช่อง และรอบ `Gun_GripL` (`Z ≈ +0.29 m`) ของ `poolcue` ให้ใช้แผ่นเรียบ SNOT (`Studs Not On Top`) หรือกริป Technic ลบมุมมน เพื่อไม่ให้นิ้วมือตัวละครจมทะลุปุ่มระหว่างแอนิเมชันถือและเหวี่ยง
3. **ร่องรอยต่อบล็อก (`0.8 mm` Seam Groove) และ Cavity AO ใต้ `emissive.sps`:**
   - เพราะเซิร์ฟเวอร์นิยมใช้ `emissive.sps` เพื่อให้สีสว่างสดทุกสภาพแสง แผ่นพลาสติกสีเดียวกันที่วางชิดกันโดยไม่มีร่องเงาจะละลายติดกันเป็นก้อนแบนทันทีในระยะ `3–8 m` และใน mipmap ระดับไกล ต้องเว้นร่องรอยต่อ (`seam groove` / `chamfer`) กว้าง `0.6–0.8 mm` ระหว่างก้อนบล็อก และ bake เงาซอก **Cavity AO มืดลง `25–35%`** ลงใน `_d.dds` เสมอ (ลวดลายเส้นหลักทุกเส้นต้องกว้าง `>= 4 mm`)
4. **จุดเรืองแสงแบบฝังใน (`Recessed Translucent Cores`):**
   - อย่าวาดแถบนีออนลอยทับผิวเฉยๆ ให้ฝังเม็ดไฟ (`1×1 round plate`, แกนพลังงานใส หรือช่องระบายแสง) ลึกลงไปในร่องเกราะหรือตัวบล็อก `1–2 mm` เพื่อให้ขอบบล็อกทึบช่วยตัดกรอบแสงให้คมชัดเวลาเปิด bloom
5. **เช็กไฟล์ภาพขาด, ซิงก์ `Bound Box`, ระวัง `glob.glob` และล้าง Orphan Datablocks ก่อน Export:**
   - ในสคริปต์ Python ห้ามใช้ `glob.glob` ตรง ๆ กับพาธที่มี `[resources]` หรือ `[weapon]` (เพราะ `glob` ตีความ `[...]` เป็นชุดตัวอักษรเหมือน PowerShell `-Path`) ให้ใช้ `os.listdir(d)` หรือ `glob.escape(d)` เสมอ
   - รัน `get_blendfile_summary_missing_files_for_cli` (หรือตรวจ `bpy.data.images`) เพื่อกันพาธภาพขาดอย่าง `//...\3433.dds` ที่จะเรนเดอร์ออกเป็นสีม่วงสด
   - หลังแก้รูปทรง mesh ทุกครั้ง ต้องคำนวณขนาดและตำแหน่งของ `<model>.col` (`Bound Composite` → `Bound Box`) ใหม่จากพิกัด vertex จริง (ห้ามปล่อย `Bound Box.001` หลุดลอยนอกโมเดล) และรัน `orphans_purge` ตามสัญญาใน `references/bone-and-memory-safety.md`

### หกบทเรียนสำคัญจากการปั้นจริงผ่าน Live Blender MCP (`LegoMocForge` — `weapon_lego` v4.5 Authentic Brick-Built Classic LEGO MOC Edition)

1. **สถาปัตยกรรม `LegoMocForge` True Interlocking Shell-Voxel (ต่อก้อนอิฐ LEGO จริงเฉพาะเปลือกนอก):**
   - เมื่อผู้ใช้ต้องการอาวุธที่ดูเหมือน **ต่อจากก้อนเลโก้สี่เหลี่ยมจริงทั้งชิ้น (`Authentic Brick-Built MOC`)** ห้ามปั้นแท่งเรียบแล้วแปะปุ่มหลอก ให้ย่อยกริดจำนวนเต็ม 3 มิติ (`3D integer stud grid`) ออกเป็นก้อนอิฐประสานสลับรอยต่อแบบก่ออิฐ (`staggered running-bond`: `4×2`, `3×2`, `2×2`, `4×1`, `3×1`, `2×1`, `1×1`) **เฉพาะเปลือกนอก (`outer-shell-only`)** โดยปล่อยโพรงด้านในให้กลวงโล่งเพื่อคุมโพลีทั้งชิ้นให้อยู่ใน `< 28,000 tris`!
   - ใช้ระยะชิด `gap = 0` คู่กับการปาดขอบ **`chamfer` `45°` ขนาด `0.55 mm`** รอบทุกก้อนอิฐ จะเกิดร่องรอยต่อตัว V กว้าง `1.1 mm` ที่คมกริบโดย **ไม่มีรูแสงรั่ว (`zero light leaks`)** และไม่ต้องใส่ก้อนดำซ้อนข้างในที่จะโผล่ทะลุมุมออกมา
   - วางปุ่มสตั๊ดทรงกระบอก 3D แบบ **10 เหลี่ยมเปิดฐานล่าง (`20 tris/stud`)** อัตโนมัติบนทุกขั้นบันไดที่เปิดโล่ง โดยตั้ง **`stud_dir = -1`** สำหรับขวดน้ำเลโก้ที่จับตรงคอขวด (`Bottle` ใน `w_me_<id>_knife`) เพื่อให้ปุ่มบนไหล่ขวดและฝาขวดชี้ขึ้นไปทางฝาขวดอย่างถูกต้องตามธรรมชาติ!
2. **พาเลตต์พลาสติกเงา Classic LEGO ABS แท้ไร้ไฟนีออนไซไฟ (`Pure Classic Glossy ABS`):**
   - เมื่อโจทย์เป็นของเล่นตัวต่อคลาสสิก ห้ามใส่เส้นไฟนีออนไซไฟ (`emit` สีฟ้าเรืองแสง) ให้ใช้สีพลาสติก ABS เงาสดใสของตัวต่อแท้ล้วน ๆ: แดง `#dd1a21`, เหลือง `#fac80a`, น้ำเงิน `#0057a8`, ขาว `#f4f4f2`, เทาอ่อน `#a5aab0`, เทาเข้ม `#4c5157` และดำ `#1b1e23` พร้อมเลือกอาร์คีไทป์ให้ตรงช่องจริง (เช่น `Bottle` = ขวดเลโก้ต่อจากก้อนอิฐจริง, `Poolcue` = ไม้คิวต่อจากก้อนเลโก้ทั้งแท่ง)
3. **วินัยห้ามหนามแหลมและห้ามบล็อกบวมมน (`Anti-Spike & Anti-Blob Discipline`):**
   - ห้ามเติมหนามแหลม ฟันเลื่อย เขี้ยวแวมไพร์ หรือหัวหอกสามง่าม และห้ามใช้ `chaikin` หลายรอบกับก้อนอิฐสี่เหลี่ยม (ซึ่งทำให้บล็อกบวมเป็นไส้กรอก) ให้ใช้การปาดมุมคม (`0.55 mm` `45°` brick chamfer หรือ `chamfer_poly_2d`) เท่านั้น และระวังเส้นรูเจาะด้านในของ `shape2d` ไม่ให้ล้ำเส้นขอบนอก (`EVEN_ODD` fill inversion trap)
4. **กับดัก `shape2d` Symmetric Extrude (`cu.extrude + cu.bevel_depth`):**
   - ใน Blender Curve 2D ค่า `cu.extrude` บวก `cu.bevel_depth` จะดันความหนาออก **ทั้งสองฝั่ง `+Z` และ `-Z`** (`ความหนารวม = 2 × (extrude + bevel_depth)`) เมื่อใช้ทำโครงแกน ต้องคุมความหนาเผื่อทั้งสองฝั่งเสมอ
5. **แก้ Z-Fighting รอบรูนิ้วสนับมือ (`Knuckle` Ring & Brick Stepping):**
   - ไล่ระดับความหนาและรัศมีขอบรูนิ้วแต่ละชั้นไม่ให้มีระนาบซ้อนทับกัน (`zero coplanar Z-fighting`) และจัดก้านฝ่ามือเรียบ SNOT อยู่ฝั่ง `+Y` ส่วนแป้นปุ่มตัวต่อด้านหน้าชี้ไปทาง `-Y`
6. **สัญญาสองช่อง `Knife`/`Bottle` และจุดกึ่งกลางด้ามจับ (`Dual-Slot & Grip Center Contract`):**
   - คุมความสูงของ `w_me_<id>_knife` (เช่น ขวดเลโก้ `Z ∈ [-0.058, +0.205] m`) ให้ผ่าน `validate_model.py` (`fail=0 warn=0`) ได้ **ทั้งสองช่อง** (`--slot bottle` และ `--slot knife`) และรักษาจุดกึ่งกลางโซนจับ `Z ∈ [-0.015, +0.025] m` ให้อยู่ที่ `(0, 0)` พอดี

## นำเข้าโมเดลจากภายนอก (AI สร้าง 3D หรือซื้อมา)

forge ด้วยโค้ดเหมาะกับฐานที่สเกลถูก ถ้าต้องการรูปทรงละเอียดระดับภาพโปรโมต ให้ใช้โมเดลจากภายนอก ถ้าไฟล์มีอาวุธหลายชิ้นต้องใช้ `split_ai_set.py` ตามหัวข้อถัดไป ถ้ามีชิ้นเดียวก็แนะนำตัวเดียวกันเพราะมี preview จุดมือก่อน bake ส่วน `import_ai_model.py` เหมาะกับการลองชิ้นเดียวแบบเร็ว ๆ ถ้าโมเดลวางเอียงให้ใส่ `--pca`

```powershell
& $b -b --factory-startup --python-exit-code 1 -P scripts\blender\import_ai_model.py -- --src bottle.glb --slot bottle --id onikage --out DIR --tris 14000 --bake 1024
```

| ตัวเลือก | ผล |
| --- | --- |
| `--slot` | `poolcue` `bottle` `machete` `knife` `bat` `knuckle` `revolver` กำหนดทิศ ความยาว จุดจับ และงบ tris เริ่มต้น |
| `--length`, `--grip` | ทับความยาวเป้าหมาย (ม.) และตำแหน่งจุดจับ (สัดส่วนจากปลายด้าม) ค่าเริ่มต้นตรงกับขนาดจริงของช่อง ถ้าทรงต่างจากช่อง เช่นคะตะนะในช่อง Bottle ใช้ `--length 0.8 --grip 0.33` หรือคารัมบิตใช้ `--length 0.2 --grip 0.4` |
| `--flip` | กลับหัวท้าย (melee หมุนรอบ X, ปืนหมุนรอบ Z) |
| `--rot x,y,z` | หมุนเพิ่ม (องศา) หลังจัดแกนแล้ว |
| `--pca` | จัดแกนหลักด้วย Principal Component Analysis (SVD) สำหรับโมเดลที่วางเฉียงในไฟล์ |
| `--strip-islands 0.04` | ลบชิ้นลอยขนาดเล็ก (สัดส่วนของปริมาตรรวม) ก่อนรวม mesh ใส่ `0` เพื่อปิด |
| `--bake-mode lit|color` | `lit` (ค่าเริ่มต้น) แปลง PBR Principled BSDF เป็นสตูดิโอ 3-point + Fresnel rim + AO ก่อน bake `EMIT`; `color` เก็บแค่สี |
| `--tris`, `--bake` | งบ tris และขนาด texture (ใช้ 2048 ถ้ามีรายละเอียดเล็กมาก) |
| `--ydr [DIR]` | สร้าง `.ydr` + `.ytd` + `.dds` โดยตรงหลัง bake |

ขั้นตอนในสคริปต์: นำเข้า, รวม mesh, จัดแกนตามขนาดกล่อง (melee ยาวสุด=Z, สนับมือบางสุด=X ยาวสุด=Z, ปืนยาวสุด=X), สเกล, วางจุดจับที่ origin (ปืนวางปากกระบอกที่ x=0.245), decimate, bake สีจาก mesh ละเอียดลง UV ใหม่, ใส่ skeleton, บันทึก `.blend` + sheet + icon ผลลัพธ์ชื่อเหมือน forge จึงใช้ `new-skin.ps1` ต่อได้

ข้อจำกัดที่ทดสอบแล้วและยังไม่ได้ทดสอบ:
- ทดสอบแล้ว: ไฟล์ GLB จำลองจากคะตะนะของ forge เองที่หมุนและขยาย 3 เท่า (ได้ทิศ ขนาด จุดจับ และสีถูก)
- ยังไม่ได้ทดสอบกับไฟล์ AI จริง: ทิศหัว/ท้ายใช้ไม่ได้อัตโนมัติ ต้องดู sheet แล้วใส่ `--flip` ถ้ากลับหัว ถ้ามีหลาย material หรือ texture ผิดปกติอาจต้องปรับ
- `--bake-mode lit` (ค่าเริ่มต้น) ใส่แสงสตูดิโอลง texture ส่วน `color` เก็บแค่สี
- `--strip-islands` ไม่ได้เชื่อมจุดก่อนนับเกาะ กับ GLB จึงลบเศษตามตะเข็บ UV ด้วย (ทดสอบ GLB คารัมบิต: ลบ 465 เกาะ รวม 989 จาก 194,619 tris) ถ้าเห็นรูบนโมเดลให้ใส่ `--strip-islands 0`
- ตรวจสิทธิ์การใช้งานเชิงพาณิชย์ของโมเดลที่ได้ก่อนนำขึ้นเซิร์ฟเวอร์

## แยกโมเดล AI เป็นอาวุธ (`split_ai_set.py`)

ใช้ได้ทั้งไฟล์ที่มีอาวุธทั้งชุดและไฟล์ที่มีชิ้นเดียว รับ glb, gltf, fbx, obj

ทดสอบแล้วกับ FBX จริงจาก Tripo ชุด ONIKAGE (2 ล้าน tris, 7 ชิ้น) ครบทุกโหมด ใช้เวลาทั้งชุดราว 2 นาที และกับ GLB อาวุธชิ้นเดียวที่ตัดจากชุดนั้น ยังไม่เคยลองถือในเกม และยังไม่เคยลอง GLB ที่ออกจากบริการ AI โดยตรง

```powershell
$t = '.claude\skills\infrontofx\weapon-forge\scripts\blender\split_ai_set.py'
& $b -b --factory-startup --python-exit-code 1 -P $t -- --src set.fbx --out DIR --mode inspect --id myset
& $b -b --factory-startup --python-exit-code 1 -P $t -- --src set.fbx --config set.json --out DIR --mode preview
```

| ลำดับ | `--mode` | ได้อะไร | ต้องทำ |
| --- | --- | --- | --- |
| 1 | `inspect` | รายการชิ้น, `overview_front.png` มีเลขกำกับ (+X ขวา, +Z บน), `overview_top.png`, `set.draft.json` | จับคู่เลขกับอาวุธ ถ้าได้น้อยกว่าจำนวนอาวุธแปลว่าชิ้นติดกัน ให้เจนใหม่ |
| 2 | แก้ config | | คัดลอก draft ไว้ที่ `weapon_<id>/source_ai/set.json` ตัวอย่างเต็มคือ `templates/ai-set.example.json` |
| 3 | `preview` | `preview_front.png`, `preview_side.png` ยังไม่ bake | **ดูทุกครั้ง** จุดแดงคือ `Gun_GripR` จุดฟ้าคือปากกระบอกหรือมือซ้าย จุดขาวคือ origin ต้องปรับ `grip` ให้จุดแดงอยู่กลางด้ามจับจริง (อย่าให้อยู่ตรงกระบังดาบหรือโกร่งมีด) |
| 4 | `final` | `.blend`, `_d.png`, `_d.dds`, `_sheet.png`, `icon_<name>.png`, `fit_report.json` (และ `.ydr`/`.ytd` ถ้าใส่ `--ydr`) | ใส่ `--only a,b` เพื่อทำซ้ำเฉพาะชิ้น และใส่ `--ydr STREAM_DIR` เพื่อคอมไพล์ลง `stream/` โดยตรง |
| 5 | `sheet` | `<id>_set_front.png`, `<id>_set_back.png` | เทียบกับ DNA ของ family ทั้งสองด้าน (สีหลัก ลวดลายซ้ำ ของห้อย ต้องเห็นครบทั้งชุด) |
| 6 | `zoom` | `zoom_<name>.png` ซ้ายคือ high-poly ขวาคือผลลัพธ์ | `--zoom name,z0,z1,yaw` ใช้แยกว่ารอยเป็นของเดิมหรือเกิดตอน bake |

จากนั้นรัน `validate_model.py` และ `inspect-ydr.ps1` ทุกชิ้นที่มีช่องอาวุธ **ห้ามรัน `forge_weapon.py --ydr` ทับ `stream/` หลังจากแยกโมเดล AI ด้วย `split_ai_set.py` เด็ดขาด** เพราะจะเอาโมเดล procedural ทับโมเดล AI! แนะนำให้คัดลอก `.blend`, `_d.png`, `icon_*.png` จาก `source_ai`/`source_tripo` ไปไว้ใน `source/` ให้ตรงกันด้วย

| คีย์ใน config | ความหมาย |
| --- | --- |
| `id` | ชื่อชุด ใช้ตั้งชื่อโมเดล `w_me_<id>_<name>` |
| `grade` | `black`, `gamma`, `red` ปรับสีหลัง bake ใส่ `false` เพื่อปิด ชุดที่ไม่ใช่ดำแดงให้ลด `black` และตั้ง `red` เป็น 0 |
| `name` | ชื่อไฟล์ ค่าเริ่มต้นคือ `slot` ชิ้นแถมตั้งเอง เช่น `scabbard` |
| `slot` | กำหนดแกน, prefix, skeleton และค่าเริ่มต้น |
| `center` | จุดกลางจาก inspect จำเป็นเมื่อไฟล์มีหลายชิ้น |
| `main` | ทิศคร่าว ๆ: melee ไปทางปลาย, ปืนไปทางปากกระบอก, สนับมือตามแถวนิ้ว |
| `sec` | melee ไปทางคม (เป็น +X), ปืนไปด้านบน (เป็น +Z), สนับมือไปทางห่วงนิ้ว (เป็น +Y) |
| `range` | คำนวณแกนจากช่วงนี้เท่านั้น 0 คือท้าย 1 คือปลาย เช่นคะตะนะใช้ `[0, 0.3]` เพื่อให้ด้ามตรง |
| `fixed` | ใช้ `main` ตรง ๆ สำหรับทรงโค้งที่คำนวณแกนไม่ได้ เช่นคารัมบิต |
| `flat` | ใช้ด้านบางสุดล็อกการหมุน เปิดกับอาวุธแบน ปิดกับทรงกลม |
| `length`, `grip`, `tris`, `bake` | ความยาว (ม.), จุดจับเป็นสัดส่วนจากท้าย, งบ tris, ขนาด texture |
| `tassel` | เฉพาะปืน ย่อของห้อยใต้ด้ามตามสัดส่วน |
| `light` | ทิศแสงตอน bake ปกติไม่ต้องใส่ |

ค่าที่ใช้ได้จาก ONIKAGE ตรวจจากภาพ render และจุดมาร์กเท่านั้น ยังไม่ได้ลองถือ:

| ทรง | slot | `length` | `grip` | `tris` | `bake` | หมายเหตุ |
| --- | --- | --- | --- | --- | --- | --- |
| ไม้เท้าหัวมังกร | poolcue | 0.95 | 0.20 | 24000 | 2048 | `range [0.2, 0.8]` วัดเฉพาะก้าน มือทั้งสองอยู่บนลายจับ |
| คะตะนะ | bottle | 0.78 | 0.155 | 20000 | 2048 | จุดจับกลางด้ามพันเชือก (tsuka) ใต้กระบังหน้ายักษ์ |
| ดาบด้ามยาว | machete | 0.52 | 0.165 | 18000 | 2048 | จุดจับตรงกลางร่องนิ้วบนด้าม (ไม่ใช่ตรงโกร่งมีด) |
| คารัมบิต | knife | 0.28 | 0.28 | 16000 | 1024 | `fixed` ตามแนวห่วงไปกระบัง จุดจับอยู่กลางร่องนิ้วเหนือห่วง |
| สนับมือมีเขา | knuckle | 0.20 | - | 16000 | 1024 | ความยาวรวมเขา ค่าเริ่มต้น 0.15 สั้นเกิน |
| ปืนพก | revolver | 0.34 | - | 22000 | 2048 | `range [0.45, 1]` วัดจากสไลด์ และจัดด้ามปืนให้ตรง `Gun_GripR` |

สิ่งที่เจอจริงระหว่างงาน:

- **AI วางอาวุธเอียงตามรูปต้นทาง:** จัดแกนตามกล่องขอบเขตจะเอียงผิด เครื่องมือนี้จึงคำนวณแกนจากรูปทรงแล้วใช้ `main`/`sec` บอกทิศ
- **GLB แตกตามตะเข็บ UV:** รูปแบบ glTF ต้องแยก vertex ตามตะเข็บ ถ้าแยกชิ้นตรง ๆ จะแตกหลายร้อยส่วน ต้องเชื่อมจุดที่ซ้อนกันก่อนเสมอ
- **ปืนมีของประดับ:** อย่าวางปืนตามจุดสูงสุดของโมเดล เขาจะดันตำแหน่งเพี้ยน ให้วางตามลำกล้อง ถ้าเขาหรือพู่ทำให้แนวตั้งยาวกว่าปืน `validate_model.py` จะ FAIL ให้แก้โมเดล ไม่ใช่แก้ตัวตรวจ
- **ดาบ/มีดในช่อง `bottle` หรือ `knife` ห้ามยาวเกิน `zMax = 0.45` (แนะนำ `0.32–0.36` ม.):** ถ้าปั้นหรือดึงดาบคาตานะจาก AI ลงช่อง `bottle` ที่ความยาวเต็ม `0.78` ม. ใบมีดจะยาวกว่ามีดอ้างอิง (`flood_bite_knife.ydr`, `Z = -0.053..0.295`) เกือบสองเท่า ให้รักษาสัดส่วนด้ามจับและกระบังมือ (`tsuba`/`habaki`) แบบ 1:1:1 แล้วหดเฉพาะแกน `Z` ของใบมีดเหนือปลอกคอ (`z > +0.098`) ให้ปลายใบมีดอยู่ราว `zMax = 0.26..0.30` (ความยาวรวม `~0.32` ม.)
- **bake แค่สีจะแบน:** shader ของเซิร์ฟเวอร์เป็น emissive ไม่รับแสง จึง bake แบบ COMBINED ใต้แสง gradient เพื่อเก็บโลหะ ความเงา normal map และเงาซอกลง texture
- **สีซีดหลัง bake:** ดำออกเทาและแดงออกชมพู `grade` แก้ตรงนี้ ตัวเร่งแดงต้องกันเงาของทองไว้ ไม่งั้นทองจะกลายเป็นแดง
- **UV ว่างราว 25%:** smart project อย่างเดียวเสียพื้นที่ จึงต้อง `pack_islands` แบบ CONCAVE ต่อ
- **`Object.bound_box` ค้างค่าเก่า** หลัง `mesh.transform` ให้คำนวณจาก vertex จริง
- **อย่าตั้ง path รูปเป็น `//`** ก่อนบันทึก `.blend` ตัวเรนเดอร์จะหารูปไม่เจอและขึ้นสีม่วง
- **เวลาในไฟล์จาก Tripo อาจล้ำหน้าเครื่อง** เพราะ zip เก็บเวลาตามเขตของเซิร์ฟเวอร์ อย่าเทียบเวลาไฟล์เพื่อตรวจ cache
- **`[1nfx]` ใน PowerShell:** `-like` และ `-Path` มองวงเล็บเป็น wildcard ใช้ `-LiteralPath` และ `.StartsWith()`

## วัสดุและ shader

สำรวจจากของจริง:

| รูปแบบ | สกินที่ใช้ | ลักษณะ |
| --- | --- | --- |
| `emissive.sps` ล้วน | elys, extreme, eclipse, halloween | **ทางหลักของเซิร์ฟเวอร์** สว่างคงที่ทุกสภาพแสง เงาถูกวาดลงใน texture |
| `emissive.sps` + `weapon_emissivestrong_alpha` | elys knuckle/machete, white_rabbit | ชิ้นเรืองแสงแยกเป็นอีก geometry |
| `default.sps` + `emissive.sps` | lego | ตัวรับแสงปกติ ชิ้นเรืองแสงแยก texture 64×64 DXT1 |

Texture ที่พบ: 1024×1024 DXT5 เป็นหลัก, 2048 DXT1 บางชิ้น, 64×64 DXT1 สำหรับสีล้วน ฝังใน `.ydr` หรือแยก `.ytd` ชื่อเดียวกับโมเดลก็ได้ ตัวเลขล่าสุดดู `server-catalog.md`

ชุมชน FiveM รายงานเพดานราว 16 MB ต่อไฟล์ `.ytd`/โมเดล แต่[ยังไม่พบเอกสารทางการ](https://forum.cfx.re/t/recent-server-texture-issues/3384555) อาวุธหนึ่งชิ้นที่ใช้ 1024 DXT5 กินราว 1.4 MB จึงห่างจากเพดานมาก ใช้ 2048 เฉพาะเมื่อรายละเอียดจำเป็นจริง

Forge ออกแบบให้ตรงกับทางหลัก: ทุกวัสดุเป็น Emission ที่คำนวณเงาเอง (AO, bevel, matcap) ภาพ render จึงตรงกับที่ `emissive.sps` จะแสดง และการ bake ใช้ `EMIT`

## จาก Blender ไปเป็น .ydr

โครงที่ forge สร้าง เทียบกับ `weapon_lego/source/*.blend` ซึ่งเป็นตัวอย่างเดียวที่เปิดได้:

```
<model>             Armature (Sollumz: Drawable)
├─ Gun_Root         Mesh, vertex group Gun_Root, UV "UVMap 0", color "Color 1"
└─ <model>.col      Empty Bound Composite → Bound Box (attach_sollumz_hierarchy สร้างให้อัตโนมัติ)
```

มีสองทาง (ทาง B ผ่านการพิสูจน์โหลดในเกมจริงบนเซิร์ฟเวอร์ FiveM แล้ว และแก้บั๊กแครช `crSkeletonData` เรียบร้อยเมื่อ 2026-11-12):

| | ทาง A: Sollumz 2.9 | ทาง B: `scripts/blender/export_ydr.py` |
| --- | --- | --- |
| ต้องติดตั้ง | Sollumz + PyMateria | ไม่ต้อง |
| ตัวเขียนไฟล์ | ไลบรารี `szio` และ Materia ของ Cfx | โค้ดประกอบ RSC7 เองทั้งไฟล์ |
| สถานะบนเครื่องนี้ | ยังไม่ได้ติดตั้ง จึงยังไม่ได้ลอง | พิสูจน์ในเกมจริงแล้ว สร้าง `.ydr` + `.ytd` + `.dds` ผ่าน `inspect-ydr.ps1` (`fail=0`) ทุกช่อง |

แนะนำทาง A เมื่อติดตั้ง Sollumz แล้ว และใช้ทาง B ได้ทันทีโดยไม่ต้องลงส่วนเสริม

### ทาง A: Sollumz

อ้างอิงจากซอร์สรุ่น 2.9.0 ส่วนเอกสารหน้า[สร้างอาวุธ](https://docs.sollumz.org/tutorials/creating-weapons-todo)ของ Sollumz ยังว่างอยู่

1. เปิด `<model>.blend` (ซึ่ง `forge_weapon.py` / `export_ydr.py` ตั้งค่า `sollumz_drawable`, `sollumz_drawable_model`, shader `emissive.sps` และ `Bound Composite` → `Bound Box` ไว้ให้แล้ว)
2. ผูก texture เข้า `DiffuseSampler` และเปิด Embedded **ต้องเป็นไฟล์ `.dds` เท่านั้น** Sollumz จะเตือนและไม่ฝัง texture ที่เป็น PNG (ดู `ytd/ytdexport.py`) ไฟล์ DDS มาจาก `source/<model>_d.dds` ของทาง B หรือ `texconv`
3. Export ด้วย Format = **Native** และ Version = **Gen8 อย่างเดียว** ค่าเริ่มต้นเปิดทั้ง Native + CW XML และ Gen8 + Gen9 ซึ่งจะแยกไฟล์ลง `gen8/` กับ `gen9/` ไฟล์ทั้ง 90 ตัวที่เปิดอ่านได้ในเซิร์ฟเวอร์เป็น RSC เวอร์ชัน 165 ทั้งหมด
4. วางใน `weapon_<id>/stream/` ชื่อไฟล์ต้องตรงกับ `<Model>` ใน meta

ถ้ารันจากสคริปต์ operator คือ `bpy.ops.sollumz.export_assets(directory=..., direct_export=True, use_custom_settings=True, target_formats={"NATIVE"}, target_versions={"GEN8"}, limit_to_selected=False)` (อ่านจากซอร์ส ยังไม่เคยรัน) การ import `.ydr` ต้นฉบับใช้ `sollumz.import_assets` เปิดไฟล์ไบนารีได้โดยตรงเมื่อมี PyMateria ถ้าไม่มีต้องใช้ `.ydr.xml` จาก CodeWalker

### ทาง B: export_ydr.py

```powershell
& $b -b --factory-startup --python-exit-code 1 -P scripts\blender\export_ydr.py -- --blend source --out stream
```

จุดที่ตรวจพบและแก้แล้ว:

- **แครชในเกมจาก `ChildParentIndices` (`skel+0x40`) และ `ChildParentIndicesCount` (`skel+0x60`) (พิสูจน์จาก crash dump จริงและแก้แล้ว 2026-11-12):** RAGE `crSkeleton::Update()` คำนวณเมทริกซ์กระดูกเป็นชุด SIMD ละ 4 คู่ (`4 × (child_u16, parent_u16) = 8 uint16 = 16 bytes` ต่อระดับความลึกของต้นไม้กระดูก) และฟิลด์ `skel+0x60` เก็บ **จำนวน `uint16` (`= len(cparent_pairs) * 2`)** ไม่ใช่จำนวนไบต์ (`0x10` = `16 uint16` = 8 คู่ = 32 ไบต์สำหรับอาวุธประชิด 3 กระดูกและ Poolcue 4 กระดูก; `0x28` = `40 uint16` = 20 คู่ = 80 ไบต์สำหรับ Revolver 10 กระดูก) รุ่นเดิมใส่คู่กระดูกไว้เพียงครึ่งเดียวแต่เขียน `0x10`/`0x28` ที่ `+0x60` ทำให้ `crSkeleton::Update()` อ่านล้นเข้าไปในตาราง hash `BoneIds` ที่อยู่ติดกัน นำ pointer 64-bit บน heap มาตีความเป็นดัชนีกระดูก (`0..65535`) แล้วเขียนเมทริกซ์ออกนอกขอบเขตจนเกมแครชทันทีที่ `crSkeletonData` ปัจจุบันคำนวณ `num_cparent_u16 = len(cparent_pairs) * 2` โดยตรงพร้อมตรวจใน `inspect-ydr.ps1` ทุกคู่
- **`phBoundBox` `MaterialId` ที่ `+0x4C` (แก้แล้ว 2026-11-12):** ต้องเขียนเป็น `uint32` (`<fffI`, ค่า `55` หรือ `69`) และ `+0x5C` เป็น `0` ไม่ใช่ `float(mat_id)` (`0x428a0000`)
- **จำนวน bone ที่ `+0x5E` (แก้แล้ว):** `build_skeleton_block` เขียน `<IIIHH` ที่ `+0x50` เพื่อให้ค่า bone count อยู่ตรง `+0x5E` (`01 00 <nb> 00` ที่ `+0x5C`) ตรงกับ `wm_elys_knife` และ `w_me_lego_knife`
- **ป้องกัน bloom สะสม (แก้แล้ว):** `image_to_dxt5` เช็ก `img.get("bloomed")` และตั้ง `img["bloomed"] = True` จึงไม่เบลอซ้ำเมื่อรันซ้ำ
- **`RSC7 PageFlags` (`sys_flags`) ล้นเมื่อ `VertexBuffer + IndexBuffer` เกิน `2 MB` (ตรวจพบใน `w_me_lego_bat` `50,346` split-corner verts และแก้แล้ว 2026-11-16):** เมื่อโมเดลมีมุมปาดคมจำนวนมากจน `SysAlloc` ขยาย `mem.buf` จาก `0x200000` (`2 MB`) เป็น `0x400000` (`4 MB`) รุ่นเดิมคำนวณ `sys_flags` ล่วงหน้าแค่ `0xA0000013` (`1 MB`) / `0xA0000014` (`2 MB`) ทำให้ขนาดคลายบีบอัด (`6 MB`) ไม่ตรงกับ `PageFlags` (`4 MB`) เสี่ยงสตรีมล้นหน่วยความจำ RAGE ปัจจุบัน `export_ydr.py` คำนวณ `sys_flags = 0xA0000010 | (int(round(math.log2(len(mem.buf)))) - 17)` จากขนาด `mem.buf` สุดท้ายก่อนแพ็กส่วนหัว RSC7 เสมอ (`1 MB` → `0xA0000013`, `2 MB` → `0xA0000014`, `4 MB` → `0xA0000015`, `8 MB` → `0xA0000016`)
- **การรักษา `<model>_hi.ytd` คู่กับ `<model>_hi.ydr` (แก้แล้ว 2026-11-16):** หากใน `stream/` มี `<model>_hi.ytd` อยู่แล้วและเปิด `make_hi` ไว้ `export_ydr.py` จะเขียนอัปเดต `<model>_hi.ytd` ให้เป็นพจนานุกรม `1024×1024` DXT5 11 mips ตรงกับ `<model>.ytd` โดยอัตโนมัติ (ไม่ลบทิ้ง และจะลบเฉพาะเมื่อส่ง `--no-hi` เท่านั้น)
- **ป้องกันชื่อ Armature ติดนามสกุล `.001` และ `Bound Box.001` ซ้ำซ้อน:** ในสคริปต์ปั้นต้องเปลี่ยนชื่อ render mesh เป็น `Gun_Root` (และ `Gun_Root_high`) **ก่อน** เรียก `bpy.data.objects.new(model_name, arm)` ทุกครั้ง มิฉะนั้น Blender จะเติม `.001` ต่อท้ายชื่อ Armature ทำให้ได้ไฟล์ขยะ `<model>.001.ydr` โผล่ใน `stream/` และเรียก `attach_sollumz_hierarchy` เพียงครั้งเดียวต่อฉากสะอาดเท่านั้น
- **ทิศทางสนับมือ (`Knuckle`) 180° และพิกัดศูนย์กลางด้ามจับ:** เมื่อปั้น `knuckle` ด้วยโค้ดเอง ให้สร้างลงพิกัดโลก `(X, Y, Z)` โดยตรง (`X ∈ [+0.011, +0.033]`, ก้านฝ่ามือเรียบแบบ SNOT อยู่ฝั่ง `+Y`, รูสอดนิ้วทั้ง 4 และแป้นปุ่มกระแทกหน้าเรียบชี้ไปทาง **`-Y`**) ระวังฟังก์ชันแปลงแกน `to_yz` ที่สลับหน้า-หลัง `180°` หากคัดลอกมาโดยไม่ตรวจ และรักษาโซน `Gun_GripR` (`Z ∈ [-0.035, +0.032]`) กับ `Gun_GripL` (`Z ∈ [+0.352, +0.472]`) ให้ไร้ปุ่มและมีจุดศูนย์กลางอยู่ที่ `(0, 0)` พอดี
- **คุมหน่วยความจำ Cycles ให้คงที่ระดับ `~80 MB` ตลอดการปั้นทั้งชุด:** หลัง bake ลงแผ่นภาพเดียวเสร็จ ให้ถอด procedural bake materials ออกจาก mesh ทันทีแล้วสั่ง `bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)`

ตารางค่าอ้างอิงจริงจากชุด `weapon_lego` **v4.5 Authentic Brick-Built Classic LEGO MOC Edition** ทั้ง 6 ช่อง (`LegoMocForge` ใน `build_lego_showpiece.py`, ต่อจากก้อนอิฐเลโก้เปลือกนอกจริงทั้งชิ้น ไร้ไฟนีออนไซไฟ, ปั้นและตรวจผ่าน Live Blender 5.3 MCP + บันทึกฟอร์แมต `BLENDER-v402` 4.2.3, อบ Cycles `EMIT` → `1024×1024` DXT5 11 mips, ผ่าน `validate_model.py` และ `inspect-ydr.ps1` ด้วย `fail=0 warn=0` ทุกไฟล์):

| ช่อง | โมเดล (อาร์คีไทป์ MOC) | Tris / Geoms / Bones | ช่วงขนาดหลัก | `.ydr` / `_hi.ydr` | `.ytd` / `_hi.ytd` (`1024×1024` DXT5 11 mips) |
| --- | --- | --- | --- | --- | --- |
| `Bottle` + `Knife` | `w_me_lego_knife` (Brick-Built LEGO Bottle) | `16,716` / `1` / `3` | `Z = -0.058 .. +0.205 m` (`stud_dir=-1`, ผ่านทั้ง `bottle` & `knife`) | `820 KB` (`839,249 B`) | `484 KB` (`495,926 B`) |
| `Poolcue` | `w_me_lego_poolcue` (Full Brick-Built Cue Stick) | `18,198` / `1` / `4` (`+Gun_GripL`) | `Z = -0.142 .. +0.705 m` | `796 KB` (`815,360 B`) | `447 KB` (`457,469 B`) |
| `Knuckle` | `w_me_lego_knuckle` (Brick-Built Knuckle Duster) | `9,696` / `1` / `3` | `Z = -0.067 .. +0.067 m` | `683 KB` (`699,517 B`) | `479 KB` (`490,356 B`) |
| `Machete` | `w_me_lego_machete` (Brick-Built LEGO Broadsword) | `9,470` / `1` / `3` | `Z = -0.049 .. +0.439 m` | `679 KB` (`695,444 B`) | `460 KB` (`470,802 B`) |
| `Revolver` | `w_pi_lego_revolver` (4-Stud-Wide Brick Revolver) | `24,186` / `2` / `10` (`+Gun_Muzzle`,`WAPClip`) | `X len = 0.362 m, Z = -0.126 .. +0.067 m` | `993 KB` (`1,017,072 B`) | `459 KB` (`469,721 B`) |
| `Bat` | `w_me_lego_bat` (Brick-Built Baseball Bat) | `27,832` / `2` / `3` | `Z = -0.140 .. +0.575 m` | `1,114 KB` (`1,140,556 B`) | `474 KB` (`485,833 B`) |

### ตรวจไฟล์ที่ได้

```powershell
scripts\inspect-ydr.ps1 -Path stream\model.ydr -Slot knife
```

กฎทุกข้อวัดจากไฟล์จริง: ทดสอบกับ `.ydr` ที่เปิดได้ 90 ไฟล์ ผ่าน 88 ไฟล์ อีก 2 ไฟล์เป็น prop เอฟเฟกต์ `thunderxefx` ที่ไม่ใช่อาวุธและไม่มี skeleton
บางชุดมี `<model>_hi.ydr` เป็นสำเนาเดียวกันสำหรับ high detail (eclipse, lego, extreme poolcue) ชุด elys ไม่มีและใช้งานได้

## UV Animation

ถ้าต้องการลายเลื่อน: `.ycd` ชื่อ `clip@<model>` และ `.ytyp` คู่กัน ลงทะเบียนด้วย `data_file 'DLC_ITYP_REQUEST'` ดู `weapon_white_rabbit` เป็นตัวอย่างที่เปิดได้
