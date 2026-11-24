---
name: sculpt-forge
description: ปั้นเนียน prop และชิ้นแมพสไตล์ designer toy ใน Blender 4.2.3 ด้วย SDF (signed distance field) ทั้งทรงพอง pillow ผสานชิ้นด้วย fillet รายรอยต่อ ตัวอักษรพองซ้อนชั้น ป้ายพองขอบหยัก ท่อขอบ ลูกปัด ครีมหยัก หยดสไลม์ ถ้วย lathe และของออร์แกนิก แล้วย่อเป็น low-poly ตามงบโดยโอน custom normals จาก high-poly ให้ยังเนียน ตรวจความเนียนด้วยตัวเลข (dihedral, sagitta, folds, lumpiness) และภาพ clay/zebra ก่อน export ผ่าน prop-forge ส่วนชิ้นแมพโค้งขนาดใหญ่ (ลานขอบมน บันไดโค้ง ราวโค้ง ซุ้มโค้ง เส้นไฟ) ปั้นด้วย SweepBuilder แล้ว export ผ่าน map-forge ใช้เมื่อผู้ใช้พิมพ์ "ปั้นเนียน", "เนียน", "ทรงพอง", "ตัวอักษรพอง", "ป้ายพอง", "หยดสไลม์", "fillet", "SDF", "sculpt", "smooth prop", "ปั้นออร์แกนิก", "ราวโค้ง", "บันไดโค้ง", "ซุ้มโค้ง", "ลดโพลีแต่ยังเนียน" หรือบ่นว่า prop ดูเป็นกล่องต่อกัน ขอบเป็นแถบเหลี่ยม เงาเป็นวุ้น ชิ้นส่วนทิ่มกัน
---

# Sculpt Forge

ปั้นของให้เนียนแบบ designer toy: ทรงพอง ขอบมนต่อเนื่อง ชิ้นส่วนไหลเข้าหากันด้วย fillet ไม่มีรอยทิ่ม ไม่มีขอบเป็นแถบ แต่ยังเบาพอสำหรับ FiveM เครื่องยนต์คำนวณรูปทรงเป็น SDF บน grid ละเอียด สร้าง mesh ด้วย OpenVDB ที่มากับ Blender ย่อด้วย collapse ตามงบ แล้วโอน normals จาก high-poly ลง low-poly เป็นขั้นสุดท้ายของ geometry ไฟล์ที่ได้ผ่านสัญญา prop ของ prop-forge (`validate_prop.py` fail=0 warn=0) และ export ด้วย `export_prop.py` ได้ทันที

ชิ้นแมพที่ใหญ่เกิน ~3 m ใช้ `SweepBuilder` (sweep โปรไฟล์มนตามเส้นทาง) แทน SDF แล้ว export ผ่าน map-forge

## เนียนวัดอย่างไร

ความเนียนมาจาก geometry โค้งจริง + normals เรียบทั้งตัว + สีแบนจาก swatch ไม่ใช่ normal map เกณฑ์ด้านล่างคือของ `scripts/blender/validate_sculpt.py` (target prop/library) ซึ่งถอดจาก prop ฮีโร่ของสตูดิโอที่วัดด้วย PyMateria

| ตัวชี้วัด | เป้า | FAIL เมื่อ | key |
| --- | --- | --- | --- |
| sagitta ของเหลี่ยมบนโค้ง | p99 ≤ 3 mm (ฮีโร่ 2-3 mm) | p99 > 9 mm | `sagitta` |
| มุมระหว่างหน้าบนขอบ smooth | p90 ≤ 30°, ≤ 12% เกิน 30°, ≤ 6% เกิน 45° | p90 > 45° หรือ > 25% เกิน 30° | `dihedral` |
| ขอบที่แยก normal | ≤ 2% | > 10% | `split_edges` |
| fold (พับ > 120° หรือหน้าพลิก) | 0 | > 24 ขอบ หรือ > 0.1% ของผิว | `folds` |
| normal เทียบ high-poly | mean ≤ 1°, max ≤ 10° | mean > 2° หรือ p99 > 10° | `normal_error` |
| ผิวเทียบ high-poly | p95 ≤ 1 mm, จุดเดียว ≤ 5 mm | p95 > 3 mm | `deviation` |
| ความเป็นก้อน | median ≤ 1.0° (shading), ≤ 1.6° (ผิว) | > 1.6° / > 3.0° | `lumpiness` |
| export vertex ต่อ vertex ที่ weld | ≤ 2.5 | > 3.0 (triangle soup) | `split_ratio` |
| ความหนาแน่น | ฮีโร่ 2-4 m ราว 200-320 tris/m², ชิ้นเล็กหนากว่าได้ | ไม่มี FAIL (WARN > 3,000 เมื่อ ≥ 8,000 tris หรือ < 60) | `density` |
| สถานะ mesh | สามเหลี่ยมทั้งหมด, มี custom normals, `Color 1` BYTE_COLOR/CORNER, UV ชั้นเดียว | quad ที่มี custom normals, `Color 1` ผิดชนิด | `triangles`, `color1` |

## เลือกเครื่องมือ

| โจทย์ | ใช้ |
| --- | --- |
| prop 0.2-3 m ที่ต้องเนียน: ตัวถังพอง ป้ายพอง ตัวอักษรพอง ครีม/หยด ถ้วย lathe ก้อนออร์แกนิก | `SculptBuilder` ใน `scripts/blender/sculpt_forge.py` ผ่านสเปก JSON (`scripts/blender/forge_sculpt.py`) หรือสคริปต์ Python |
| ชิ้นเนียนที่จะไปประกอบใน `KawaiiBuilder` ของ prop-forge | `--target library` ได้ card `sculpt_mesh` |
| ชิ้นแมพโค้ง 3-40 m: ลานขอบมน บันไดโค้ง ราว ซุ้ม กระบะต้นไม้ เส้นไฟ | `SweepBuilder` ใน `scripts/blender/sculpt_sweep.py` แล้ว export ด้วย map-forge |
| แผงแบนคมหรือชิ้นแข็ง (จอ ขอบโลหะ) ในตัวที่ปั้นเนียน | `bevel_box` / `poly_part` ของ `SculptBuilder` (Weighted Normal, ไม่ fillet เข้า SDF) |
| ชุด archetype สำเร็จรูปทรงคม low-poly 2,400-4,800 tris (ATM เสาป้าย ตู้เซฟ โต๊ะคราฟต์) | prop-forge `forge_prop.py` / `kawaii_studio.py` |
| ผังแมพ ymap/ybn/ytyp, prop GTA แท้, ไฟ | map-forge |

builder สำเร็จรูปแยกตระกูล (ป้าย ตู้ ภาชนะ ออร์แกนิก ของกลม ชุดแมพ) อยู่ใน `scripts/blender/recipes/` คู่กับเอกสาร recipe ในตารางเลือกอ่าน

## ขั้นตอน

1. **รับโจทย์:** id `1nfx_<set>_<name>` (ตรง `^[a-z0-9_]{3,60}$`), ขนาดจริงเป็นเมตร, Z ขึ้น, ด้านหน้า -Y, พื้น z = 0, รายการ role สี (palette บ้านใน `references/smooth-craft.md`), งบ (`size_class` hero 12,000 / medium 6,000 / small 3,000 tris)
2. **ร่างทรงด้วยตัวเลขก่อนเขียนโค้ด:** เปิด `references/smooth-craft.md` และ recipe ตระกูลที่ตรง กำหนดรัศมีขอบ ค่าพอง ท่อ ชั้นตัวอักษร และ fillet ของทุกรอยต่อ
3. **เขียนสเปก:** คัดลอก `templates/sculpt-spec.example.json` ไปไว้ `<project>/work/<set>/source/sculpt.json` (`type` ของ node = ชื่อ method, key อื่น = kwargs) หรือเขียน builder Python ตาม `references/pipeline.md`
4. **build:** รัน `forge_sculpt.py` อ่านบรรทัด `SCULPT_DONE` ต้องได้ `"validate": {"fail": 0, "warn": 0}` และ tris ไม่เกินงบ
5. **QA ตัวเลข:** รัน `validate_sculpt.py` ทีละไฟล์พร้อม `--high <out>/_high/<id>_high.blend` จนได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว สเปกตัวอย่างเองยังไม่ผ่านครบทุกชิ้น ดู baseline และวิธีแก้ใน `references/qa.md`
6. **ดูภาพด้วยตา:** รัน `render_sculpt.py` แล้วเปิดอ่าน `<id>_clay.png`, `<id>_zebra.png`, `<id>_turntable.png`, `<id>_colour.png` ทุกใบ ห้ามผ่านจากตัวเลขอย่างเดียว
7. **แก้แล้ววนข้อ 4-6** จนผ่านทั้งตัวเลขและตา
8. **export:** prop รัน prop-forge `validate_prop.py` (fail=0 warn=0) แล้ว `export_prop.py --format native` โดยไม่ใส่ `--factory-startup` ชิ้นแมพรัน `SweepBuilder.finish()` แล้ว `export_map.py` + `inspect_map.py` จนได้ `MAP_INSPECT_PASS fail=0`
9. **ส่งงาน:** เชื่อมเข้าเซิร์ฟเวอร์ตาม `prop-forge/references/integration.md` รายงานแยกสิ่งที่ตรวจแล้ว (Blender, QA, export) กับสิ่งที่ยังไม่ได้ลองในเกม ถ้าแก้ไฟล์ใน skill ให้รัน `scripts/sync-antigravity.ps1 -Check`

## คำสั่ง

`<skill>` คือโฟลเดอร์ชุด `infrontofx` (เช่น `<project>\.claude\skills\infrontofx`) และ `<blender-4.2.3>` คือโฟลเดอร์ Blender 4.2.3 LTS

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\puff'

& $blender -b --factory-startup -P "$sf\forge_sculpt.py" -- --spec "$skill\sculpt-forge\templates\sculpt-spec.example.json" --out $work
& $blender -b --factory-startup -P "$sf\validate_sculpt.py" -- --blend $work --json "$work\qa.json"
& $blender -b --factory-startup -P "$sf\validate_sculpt.py" -- --blend "$work\1nfx_puff_trophy.blend" --high "$work\_high\1nfx_puff_trophy_high.blend"
& $blender -b --factory-startup -P "$sf\render_sculpt.py" -- --blend $work --out "$work\renders" --qa "$work\qa.json"
& $blender -b --factory-startup -P "$skill\prop-forge\scripts\blender\validate_prop.py" -- --blend $work
& $blender -b -P "$skill\prop-forge\scripts\blender\export_prop.py" -- --blend $work --out "$work\stream" --format native --max-res 512 --shared-ytd 1nfx_puff_tex
& $blender -b --factory-startup -P "$sf\sculpt_sweep.py" -- --demo --out '<project>\work\sweep' --export
```

ตัวเลือก `forge_sculpt.py`: `--only id1,id2`, `--voxel 0.004`, `--budget N`, `--atlas 512|1024`, `--target prop|library` (ทับทุก prop), `--no-render`, `--no-validate`, `--tile 640`, `--samples 24` ชุดตัวอย่าง 3 ชิ้นใช้ ~46 วินาที (kiosk 25 s, sign 16 s, trophy 6 s) รวม sheet และ preview

ผ่าน Blender MCP: exec `sculpt_forge.py` เข้า namespace ที่ `__name__ == "__main__"` แล้วเรียก `ns["SculptBuilder"](...)` ส่ง `font=` เป็นพาธเต็มเสมอ และสร้างใหม่ด้วย CLI 4.2.3 ก่อน export ถ้าฉากเป็น 5.x วิธีเต็มอยู่ใน `references/pipeline.md`

## เลือกอ่าน

| งาน | อ่าน |
| --- | --- |
| ตัวเลขทรง: รัศมีขอบตามชนิด, ค่าพอง, ท่อ, ตัวอักษรซ้อนชั้น, ครีม/หยด, งานนูน, fillet, sagitta/segment, tris/m², normals, สีและ texture, emissive, กลางคืน, สิ่งห้ามทำ | `references/smooth-craft.md` |
| เครื่องยนต์: ลำดับ stage, พารามิเตอร์ `SculptBuilder` ทุกตัว, node ทุกชนิด, สคีมาสเปก JSON, Python/MCP, target library, export, ความเร็ว, แก้ปัญหา | `references/pipeline.md` |
| QA: `validate_sculpt.py` ทุกเช็กพร้อมเกณฑ์และวิธีแก้, `render_sculpt.py`, วิธีอ่าน clay/zebra/colour, baseline ที่วัดแล้ว | `references/qa.md` |
| ชิ้นแมพ: `SweepBuilder`, path/profile, งบ, hard-edge guard, RAGE vertex colour, UV world tiling, `export_map`/`inspect_map` | `references/map-pieces.md` |
| สูตรป้ายและตัวอักษรพอง | `references/recipes-signs.md` |
| สูตรตู้และเครื่อง (ATM ตู้เซฟ kiosk ตู้ขาย) | `references/recipes-cabinets.md` |
| สูตรกล่อง หีบ ภาชนะ | `references/recipes-containers.md` |
| สูตรออร์แกนิก (เมฆ สไลม์ มาสคอตก้อน ต้นไม้) | `references/recipes-organics.md` |
| สูตรของกลม (ถ้วย ฐาน puck โคม ชิ้น lathe) | `references/recipes-rounds.md` |
| สูตรชุดชิ้นแมพ | `references/recipes-mapkit.md` |

## กฎที่ห้ามข้าม

**Custom normals เป็นขั้นสุดท้ายของ geometry.** ลำดับคือ ย่อ, triangulate แล้วโอน normals หลังโอนทำได้แค่ UV, สี, material, ย้าย/หมุน/สเกลเท่ากันทุกแกน และ join ห้ามรัน `_clean_mesh_bmesh` ของ kawaii (mark sharp > 32° ทำ normals เพี้ยน 79.5°), smooth, subsurf, decimate, remesh, Weighted Normal, `set_sharp_from_angle` หรือสเกลไม่เท่ากันทุกแกน (เพี้ยน 10.4°) ต้อง triangulate ก่อนโอนเสมอ เพราะ Sollumz triangulate quad ใหม่แล้ว normals เลื่อนได้ถึง 20.5°

**บันทึกด้วย 4.2.3.** `export_prop.py` และ `export_map.py` ใน 4.2.3 เปิดไฟล์ที่บันทึกจาก 5.x ไม่ได้ งานที่ปั้นผ่าน MCP บน 5.x ต้อง build ซ้ำด้วย CLI 4.2.3 ก่อน export (engine เตือน `saved by Blender ...; rebuild with the 4.2.3 CLI`)

**CLI หนึ่ง process ต่อชุด.** ตอน `-b` ทุก `SculptBuilder()` เรียก `read_factory_settings` ล้างฉาก ห้ามถือ object ข้าม builder ใช้ `forge_sculpt.py` หรือ `SpecRunner` ที่สร้างทีละชิ้นให้แล้ว

**งบ.** prop ต่อชิ้นตาม `size_class` (hero 12,000, medium 6,000, small 3,000 tris, `budget` ทับได้), material 1-4 ตัว (หนึ่งตัวต่อ finish), texture ยกกำลังสองไม่เกิน 2048 และ palette ร่วมทั้งชุดไฟล์เดียว, shell แมพไม่เกิน 40,000 tris ไม่ใช้ normal map ทำความเนียน ไม่ใช้ mesher adaptivity, octree remesh, Laplacian smooth หรือ Decimate symmetry

**ลิขสิทธิ์.** คลิปและไฟล์อ้างอิงเป็นงานของผู้สร้างอื่น ใช้ได้แค่ภาษาทรงและตัวเลข ห้ามลอกชื่อ โลโก้ ตัวละคร มาสคอต layout แบบ 1:1 หรือ texture และห้ามเขียนชื่อแบรนด์ของเขาลงไฟล์ สเปก role หรือเอกสาร ทุกชุดใช้ชื่อแบรนด์ของเราเอง (`1nfx_`)

**สัญญาพิกัด.** mesh เดียวชื่อเดียวกับไฟล์, transform apply แล้ว, จุดต่ำสุด z = 0 กลาง X/Y (engine จัดให้), กล่องชน `<id>_col_N` ห้ามแก้ชื่อหรือ origin หลังเชื่อมเข้าเซิร์ฟเวอร์แล้ว แก้ทิศด้วย heading ในโค้ด spawn

**รายงานตามจริง.** `SCULPT_QA fail=0` และภาพ render คือผลใน Blender ไม่ใช่ในเกม จนกว่าผู้ใช้จะเห็นในเกมให้บอกว่ายังไม่ได้ทดสอบในเกม

**โค้ด Python.** สคริปต์ builder ใหม่เขียนเป็น class + method, ไม่มี comment/docstring, ไม่มี lambda หรือ nested function, มีแค่ `main()` ใต้ `if __name__ == "__main__"`, ใช้แค่ bpy, bmesh, mathutils, numpy, pyopenvdb และ stdlib และรับพาธแบบ explicit เพื่อให้ exec ผ่าน MCP ได้ (ไม่พึ่ง `__file__` อย่างเดียว)

**ที่เก็บต้นฉบับ.** แก้ที่ `.claude/skills/infrontofx/sculpt-forge` เท่านั้น ห้ามแก้สำเนาใน `.agents/skills/sculpt-forge` โดยตรง ซิงก์ด้วย `scripts/sync-antigravity.ps1` (`-Check` ตรวจ, `-Force` เขียนทับ)
