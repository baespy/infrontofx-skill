# Modeling Pipeline

## เครื่องมือในเครื่องนี้

รัน `scripts/doctor.ps1` ก่อนเริ่มงาน เพราะสถานะเปลี่ยนได้ ผลเมื่อ 2026-11-08:

| เครื่องมือ | สถานะ |
| --- | --- |
| Blender 4.2.3 | มี: `C:\Tools\blender-4.2.3-windows-x64\blender.exe` (ไม่อยู่ใน PATH) |
| Sollumz, PyMateria | **ไม่มี** |
| CodeWalker | **ไม่มี** |
| Python, Node, ffmpeg, texconv, uv | ไม่มี ใช้ Blender กับ PowerShell แทน (`python.exe` ใน WindowsApps เป็นแค่ทางลัดไป Microsoft Store) |
| GTA V | มี: `C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V` ใช้ดึงโมเดลต้นฉบับ เช่น `w_pi_revolver` |

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
$t = '.claude\skills\weapon-forge\scripts\blender\split_ai_set.py'
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

### ตรวจไฟล์ที่ได้

```powershell
scripts\inspect-ydr.ps1 -Path stream\model.ydr -Slot knife
```

กฎทุกข้อวัดจากไฟล์จริง: ทดสอบกับ `.ydr` ที่เปิดได้ 90 ไฟล์ ผ่าน 88 ไฟล์ อีก 2 ไฟล์เป็น prop เอฟเฟกต์ `thunderxefx` ที่ไม่ใช่อาวุธและไม่มี skeleton
บางชุดมี `<model>_hi.ydr` เป็นสำเนาเดียวกันสำหรับ high detail (eclipse, lego, extreme poolcue) ชุด elys ไม่มีและใช้งานได้

## UV Animation

ถ้าต้องการลายเลื่อน: `.ycd` ชื่อ `clip@<model>` และ `.ytyp` คู่กัน ลงทะเบียนด้วย `data_file 'DLC_ITYP_REQUEST'` ดู `weapon_white_rabbit` เป็นตัวอย่างที่เปิดได้
