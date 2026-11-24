# QA: ตรวจความเนียนด้วยตัวเลขและด้วยตา

## 1. ประตู QA

1. `forge_sculpt.py` (หรือ builder ของเรา) ได้ `SCULPT_DONE ... "validate": {"fail": 0, "warn": 0}` = ผ่านสัญญา prop ของ prop-forge
2. `scripts/blender/validate_sculpt.py` ทีละไฟล์พร้อม `--high` ได้ `SCULPT_QA fail=0` และ WARN ทุกตัวอธิบายได้
3. `scripts/blender/render_sculpt.py` แล้วเปิดดู clay, zebra, turntable และ colour ทุกชิ้นด้วยตา
4. prop-forge `validate_prop.py` ได้ `RESULT fail=0 warn=0` แล้วจึง `export_prop.py` ชิ้นแมพใช้ `MAP_INSPECT_PASS fail=0` ของ map-forge เป็นประตูสุดท้าย (`references/map-pieces.md`)

ตัวเลขผ่านแต่ภาพไม่สวยถือว่าไม่ผ่าน ภาพสวยแต่มี FAIL ต้องแก้หรือบันทึกเหตุผลว่าเป็นข้อจำกัดของ metric (หัวข้อ 6)

## 2. `validate_sculpt.py`

```powershell
& $blender -b --factory-startup -P "$sf\validate_sculpt.py" -- --blend <ไฟล์หรือโฟลเดอร์> [--high <out>\_high\<id>_high.blend] [--high-object <name>] [--no-high] [--target auto|prop|map|library] [--budget N] [--json <qa.json>] [--prop-validator <path>]
```

| ตัวเลือก | ความหมาย |
| --- | --- |
| `--blend` | ไฟล์ `.blend` หรือโฟลเดอร์ (ข้ามไฟล์ที่ลงท้าย `_high.blend`) ว่าง = ฉากที่เปิดอยู่ |
| `--high` | ไฟล์ high-poly สำหรับเทียบ normals และผิว ค่าเริ่มหา `<stem>_high.blend` ข้างไฟล์ แต่ sculpt-forge เก็บ high ไว้ใน `_high/` จึงต้องส่งเองทีละไฟล์ |
| `--high-object` | ชื่อ object ใน high (ค่าเริ่มลอง `<id>_high`) |
| `--no-high` | ข้ามการเทียบ high |
| `--target` | `auto` = `map` ถ้ามี `map_forge` meta หรือ material มี `map_forge_shader` ไม่งั้น `prop`, `library` ใช้เกณฑ์ความเนียนแบบ prop แต่ไม่ตรวจสัญญา |
| `--budget` | งบ tris ให้ `validate_prop` (ค่าเริ่มอ่านจาก meta) |
| `--json` | เขียนผลเป็น JSON (ใช้ต่อกับ `render_sculpt.py --qa`) |
| `--prop-validator` | พาธ `validate_prop.py` เมื่อหาเองไม่เจอ (exec ผ่าน MCP) |

drawable ที่ตรวจ: object ชื่อเดียวกับไฟล์ ถ้าไม่มีใช้ mesh ที่มี `prop_forge`/`map_forge` meta ถ้าไม่มีอีกใช้ mesh ที่มองเห็นทั้งหมด กล่องชน (`_col_` หรือ `prop_forge_collision`) ไม่นับ วัด mesh หลัง modifier โดยปิด ARMATURE

รูปแบบผล: บรรทัดหัว `== <file> :: <drawable> [<target>]`, ตามด้วยหนึ่งบรรทัดต่อการตรวจ `LEVEL key: ข้อความ` (LEVEL = `OK`, `INFO`, `WARN`, `FAIL`), `RESULT <drawable> fail=N warn=M`, สรุป `SCULPT_QA_SUMMARY drawables=N files=M` และบรรทัดสุดท้าย `SCULPT_QA fail=N warn=M` headless คืน exit code 1 เมื่อมี FAIL JSON มีรูป `{"drawables": [{"file", "drawable", "target", "fail", "warn", "checks": [{"level", "key", "text"}], "metrics": {...}}], "fail", "warn"}`

ผ่าน MCP: `ns = runpy.run_path(r"<skill>\sculpt-forge\scripts\blender\validate_sculpt.py", run_name="mcp")` แล้ว `ns["SculptValidator"](ns["CommandLine"].parse([])).run()` ตรวจฉากที่เปิดอยู่ ใน UI ห้ามส่ง `--blend` ไฟล์อื่น (จะเปิดทับฉากหรือปฏิเสธเมื่อยังไม่ save)

## 3. ทุกเช็ก เกณฑ์ และวิธีแก้

ค่าในวงเล็บ [map] คือเกณฑ์ของ target map ที่ต่างจาก prop/library

| key | วัดอะไร | WARN | FAIL | แก้ |
| --- | --- | --- | --- | --- |
| `contract` (prop) | บรรทัดจาก `validate_prop.validate_scene`: ชื่อ, mesh เดียว, transform, จุดต่ำสุด z = 0, กลาง XY, ขนาด, tris เทียบงบ, NaN, degenerate, vertex ลอย, UV, material 1-4, texture ยกกำลังสอง, กล่องชน, orphan | ตาม validate_prop | ตาม validate_prop | ตามข้อความ engine ทำให้อยู่แล้ว ถ้าพังมักเกิดจากแก้ไฟล์เองหลัง build |
| `color1` (prop) | `Color 1` ต้องเป็น BYTE_COLOR / CORNER | ไม่มี `Color 1` (export เขียนขาวล้วน ไม่มี AO) | ชนิดหรือโดเมนผิด (export ลบทิ้ง) | ใช้ค่าจาก engine ห้ามสร้างใหม่เป็น FLOAT/POINT |
| `uv_layers` (prop) | จำนวนชั้น UV | มีหลายชั้น | ไม่มี UV (ไม่มี TEXTURE0 prop ดำ) | เหลือชั้นเดียว export เปลี่ยนชื่อเป็น `UVMap 0` |
| `normal_maps` (prop) | node NORMAL_MAP/BUMP หรือ `BumpSampler` | พบ | | prop export ไม่ bind normal map ปั้น bevel จริง |
| `density` | tris / m² | > 3,000 เมื่อ ≥ 8,000 tris หรือ < 60 เมื่อ ≥ 500 tris [map = INFO] | | ใช้งบกับโค้งและ silhouette ไม่ใช่ความหนาแน่นทั้งตัว |
| `triangles` | หน้าที่ไม่ใช่สามเหลี่ยม | quad ที่ไม่มี custom normals | quad ที่มี custom normals (Sollumz triangulate แล้วเลื่อน 20°) | triangulate ก่อนโอน normals |
| `custom_normals` | มี custom split normals | ไม่มี | | โอนจาก high หรือ Weighted Normal เป็นขั้นสุดท้าย |
| `shells` | จำนวน shell | > 8 [map = INFO] | | หลอมชิ้นด้วย fillet แทนวางซ้อน |
| `interpenetration` | shell ที่ทะลุกัน (BVH overlap) | มี | | fillet หรือปลอกปิดรอยต่อ ชิ้น polygon และชิ้นแมพที่แยกส่วนโดยตั้งใจจะเตือนเสมอ |
| `split_edges` | สัดส่วนขอบที่แยก normal | > 2% [map 40%] | > 10% [map ไม่ FAIL] | smooth ทั้งตัว แยกเฉพาะมุมสถาปัตย์ ≥ 60-90° |
| `soft_splits` (map) | ขอบแยกที่มุม < 45° | > max(20, 10% ของขอบแยก) | | ให้โค้งและ bevel smooth |
| `topology` | ขอบเปิดหรือ non-manifold หลัง weld 0.1 mm | INFO | | ตรวจเมื่อไม่ได้ตั้งใจให้มีขอบเปิด |
| `dihedral` | มุมระหว่างหน้าบนขอบ smooth | p90 > 30°, > 12% เกิน 30°, > 6% เกิน 45° | p90 > 45°, > 25% เกิน 30° [map ลดเป็น WARN] | เพิ่มงบ ลดรายละเอียดเล็กที่ไม่จำเป็น เพิ่ม fillet ที่ร่องเล็ก |
| `folds` | ขอบ smooth ที่พับ > 120° และหน้าข้างเคียงที่พลิก | มี (หรือขอบแข็ง > 120°) | > 24 ขอบ หรือ > 0.1% ของผิว | เพิ่ม fillet ที่รอยต่อแคบเป็น 1.2-1.6 เท่าของ r ชิ้นเล็ก (ไม่ใช่เพิ่มงบ) |
| `sagitta` | 500 × ความกว้างหน้า × tan(θ/4) ต่อขอบโค้ง 2-60° ถ่วงตามความยาว | p99 > 3 mm [map 32] | p99 > 9 mm [map 120] | เพิ่มงบหรือ segment ตามตารางใน `references/smooth-craft.md` |
| `flat_panels` | ความเอียงของ corner normals บนแผงแบนใหญ่ | normals แบบ weighted: p95 > 1.5° / แบบโอน: mean > 12° | | แบบโอนเป็น INFO ได้ (เงาหมอน) ถ้าต้องการแผงคมใช้ชิ้น polygon + Weighted Normal |
| `lumpiness` | shading wobble (เศษของ normal field บนผิว smooth < 12°) และ surface roughness (เศษของ quadric บนผิว < 40°) ถ่วงพื้นที่ ข้ามแผงแบน | median > 1.0° / > 1.6° | median > 1.6° / > 3.0° | ดู zebra ก่อน ลอนที่ออกแบบไว้ทำให้ค่าสูง (หัวข้อ 6) ก้อนจริงแก้ที่ต้นทาง ลด voxel หรือย่อน้อยลง |
| `split_ratio` | export vertex (ตำแหน่ง + normal + UV + สี) ต่อ vertex ที่ weld | > 2.5 [map 2.8] | > 3.0 [map 3.5] (~3 = triangle soup) | weld และ smooth, UV ต่อเนื่อง |
| `high_poly` | กล่องของ high เทียบ low | ต่างเกิน max(5 mm, 2% ของเส้นทแยง) | | ต่างเกิน max(2 cm, 25%) ถือว่าคนละรูปและข้ามการเทียบ ตรวจ `--high`/`--high-object` |
| `normal_error` | corner normals เทียบ normal ของ high ที่จุดใกล้สุด | mean > 1° หรือ max > 10° | mean > 2° หรือ p99 > 10° | max สูงจุดเดียวที่ร่องลึกเป็นเรื่องปกติ ดู p99 |
| `deviation` | ระยะผิวสองทิศถ่วงพื้นที่ (p95) | p95 > 1 mm หรือจุดเดียว > 5 mm [map 5 / 40 mm] | p95 > 3 mm [map 15] | max high → low สูงมักเป็น speck หรือโพรงที่ repair ทิ้ง ดูภาพว่าหายส่วนที่มองเห็นไหม |
| `modifiers` | modifier ที่ยังไม่ apply | มี | | apply ก่อน export |
| `drawable`, `mesh`, `exception` | หา mesh ไม่เจอ, mesh ว่าง, error | | ทุกกรณี | ดูข้อความ |

เช็กเพิ่มของ target map: ชื่อ shell / mesh / ไฟล์ตรงกันและเป็นตัวเล็ก (ไม่ตรงไฟล์ = WARN, ผิดรูป = FAIL), transform apply แล้วและไม่มี parent (FAIL), `walk_surface` (ผิวหงายที่ z = 0 ≥ 5% ของผิวหงายหรือ ≥ 0.5 m² หรือจุดต่ำสุดอยู่ภายใน 2 cm ไม่งั้น WARN), `uv_layers` (ไม่มี UV หรือ UV คงที่ = FAIL, > 8 m ต่อ UV unit, หลายชั้น หรือชื่ออื่นนอกจาก `UVMap 0`/`UVMap` = WARN), `color1` (R เฉลี่ยบนหน้าไม่เรืองแสง < 90, G > 45 กลางแจ้ง, B < 90, A < 250 = WARN; ชนิดผิด = FAIL), `materials` (ไม่มี material หรือ texture หายจากดิสก์ = FAIL; ไม่มี `map_forge_shader`, shader นอกชุด, ไม่มี `DiffuseSampler`, shader normal/glass ไม่มี `BumpSampler` = WARN), `metadata` (`collision_material` นอกชุด = WARN), `colliders` (ไม่มี = WARN, เปิด non-manifold หรือปริมาตร ≤ 0 = FAIL), tris > 40,000 = FAIL

lumpiness ข้ามบริเวณ smooth ที่เล็กกว่า 2% ของผิว และข้ามทั้งหมดถ้าวัดได้ไม่ถึง 5% ค่าที่ใช้ตัดสินคือ median ถ่วงพื้นที่ ก้อนที่กินผิวไม่ถึงครึ่งจึงผ่านได้ ให้ใช้ zebra ตัดสินร่วมเสมอ ค่าอ้างอิง: mesh ดีอยู่ที่ ≤ 0.75° (fine) และ ≤ 1.01° (coarse) เช่น high จาก SDF 0.38, metaball 0.27, voxel ที่ corrective smooth แล้ว 0.55; mesh เสียอยู่ที่ 1.15-1.74° (fine) หรือ 2.33-3.99° (coarse)

## 4. `render_sculpt.py`

```powershell
& $blender -b --factory-startup -P "$sf\render_sculpt.py" -- --blend <ไฟล์หรือโฟลเดอร์> --out <dir> [--views 4] [--res 900] [--qa <qa.json>] [--samples 32] [--engine auto|workbench|eevee|cycles] [--no-zebra] [--no-lineup]
```

| ผลลัพธ์ | เนื้อหา |
| --- | --- |
| `<name>_clay.png` | ดินเหนียวเทาด้วยไฟ studio ของ Workbench มุม 3/4 หน้าซ้าย สูง 24° |
| `<name>_zebra.png` | matcap ลายม้าลาย 14 แถบ (เส้นสะท้อน) |
| `<name>_colour.png` | material จริงคูณ `Color 1` (map ใช้ช่อง R) ใน Eevee Next |
| `<name>_turntable.png` | clay หลายมุม (`--views` 4 = ตาราง 2 × 2) |
| `lineup_clay.png`, `lineup_colour.png`, `lineup_zebra.png` | รวมทุกชิ้นในโฟลเดอร์ (≥ 2 ชิ้น) ป้ายใต้ภาพมี `F<n> W<n>` เมื่อส่ง `--qa` |
| `render_manifest.json`, `_tiles/` | รายการไฟล์ engine ที่ใช้ และไฟล์ชั่วคราว (matcap EXR, ภาพแต่ละมุม) |

ลำดับ engine: clay ใช้ Workbench → Eevee → Cycles CPU, colour ใช้ Eevee → Cycles → Workbench, zebra ใช้ Workbench เท่านั้น บรรทัดผล `RENDER <name> clay=ok colour=ok zebra=ok turntable=ok engines={...} 0.8s` และ `SCULPT_RENDER drawables=N rendered=N failed=N lineup=... out=...` exit code 1 เมื่อมีชิ้นที่ไม่ได้ภาพเลย ใช้เวลา ~0.5-0.9 วินาทีต่อชิ้น render ในฉากชั่วคราวแล้วลบทิ้ง ใน UI จะแก้ค่า solid light และ studio light ของ preferences ชั่วคราวแล้วคืนค่าเดิม

ผ่าน MCP: `ns = runpy.run_path(r"<skill>\sculpt-forge\scripts\blender\render_sculpt.py", run_name="mcp")` แล้ว `ns["SculptRenderer"](ns["RenderOptions"].parse(["--out", r"<dir>"])).run()`

## 5. อ่านภาพ

ต้องเปิดดูภาพจริงทุกใบ (อ่านไฟล์ PNG) ก่อนบอกว่าผ่าน

| ภาพ | ดี | เสีย และสาเหตุ |
| --- | --- | --- |
| clay | silhouette กลมไม่มีขั้น, รอยต่อไหลเป็น fillet, ไฮไลต์ต่อเนื่อง, ตัวอักษรคม | ขั้นเหลี่ยมบนของกลม (งบหรือ segment น้อย), เส้นตัดแข็งที่รอยต่อ (ไม่มี fillet), ไฮไลต์เป็นแถบ (bevel หยาบ), กากบาทบนแผงแบน (แผงสามเหลี่ยมใหญ่ + normals ที่โอนมา), ตัวอักษรยับเป็นก้อน (ตัวเล็กเกิน voxel หรืองบน้อย), ชิ้นเล็กหาย (ถูกทิ้งเป็น speck) |
| zebra | แถบต่อเนื่องโค้งเรียบ หนาแน่นตามความโค้ง | แถบหักเป็นมุมตามแนวขอบ (crease หรือเหลี่ยม), แถบแตกเป็นฟันเลื่อยหรือเม็ดบนผิวเรียบ (ก้อนหรือ normals ไม่เรียบ = `lumpiness`), แถบแผ่เป็นรัศมีจากมุมแผงแบน (normals ที่โอนมาเอียงที่มุม = `flat_panels`) แถบที่วนเป็นระเบียบตามลอนครีม ลูกปัด หรือตัวอักษรคือดีไซน์ ไม่ใช่ตำหนิ |
| colour | เส้นแบ่งสีคม, AO มืดในซอกเบาๆ (`Color 1` ต่ำสุด ~194), ชิ้น emissive เรือง, ขอบ outline ของตัวอักษรเห็นชัด | สีเลอะเป็นฟันเลื่อย (voxel หยาบเทียบเส้นสี), ขอบ outline หาย (puff ของชั้น outline ไม่มากพอ), ทั้งตัวมืดหรือสว่างเกิน |
| turntable | ด้านหลังและด้านข้างเรียบเท่าด้านหน้า | fold หรือหยดที่ซ่อนด้านหลัง, ฐานลอย |
| lineup | ทั้งชุดใช้ภาษาทรงเดียวกัน (รัศมี ค่าพอง palette) ขนาดสมจริงเทียบกัน | ชิ้นหนึ่งดูแข็งหรือหยาบกว่าชิ้นอื่น |

## 6. baseline ที่วัดแล้ว

### สเปกตัวอย่าง (`templates/sculpt-spec.example.json`, Blender 4.2.3, 2026-11-24)

| ชิ้น | tris / งบ | validate_prop | validate_sculpt โฟลเดอร์ | พร้อม `--high` |
| --- | --- | --- | --- | --- |
| `1nfx_puff_kiosk` | 11,760 / 12,000 | 0 / 0 | FAIL `folds` (39 ขอบ พับสุด 178°, 0.013% ของผิว), WARN `dihedral` (p90 35.4°, 14.4% เกิน 30°), WARN `lumpiness` (wobble 1.48°) | fail=1 warn=4: `normal_error` mean 0.73° p99 5.66° max 64.6°, `deviation` p95 0.73 mm (high → low max 41 mm) |
| `1nfx_puff_sign` | 8,820 / 9,000 | 0 / 0 | FAIL `lumpiness` (roughness 4.08°, wobble 1.31°), WARN `folds` (15) | fail=1 warn=3: `normal_error` mean 0.30° p99 2.35°, `deviation` p95 1.14 mm |
| `1nfx_puff_trophy` | 6,860 / 7,000 | 0 / 0 | fail=0 warn=0 | fail=0 warn=2: `normal_error` mean 0.18° p99 0.93° (max 118.8° จุดเดียว), `deviation` p95 0.55 mm (high → low max 90 mm) |

ทั้งโฟลเดอร์ได้ `SCULPT_QA fail=2 warn=3` ที่ผ่านทุกชิ้น: sagitta p99 0.71-1.29 mm, split edges 0%, split ratio 1.04-1.16, 1 shell, ไม่มีชิ้นทะลุกัน, `flat_panels` เป็น INFO (kiosk mean 6.67° p95 13.09°)

การทดลองแก้ที่วัดแล้ว:

| เปลี่ยน | ผล |
| --- | --- |
| kiosk `fillet` ของ scallops และ drips 0.02/0.015 → 0.035 | folds 39 → 0, `SCULPT_QA fail=0 warn=2`, หน้าตาแทบไม่ต่าง, build เร็วขึ้น (19 s) |
| kiosk `--budget 16000` | folds 48 (ยัง FAIL), dihedral p90 32.6° |
| kiosk `stage_ratio` 6 | folds 45 (ยัง FAIL) |
| kiosk `--voxel 0.004` | folds 36 (ยัง FAIL), normal max 14.2°, build 42 s |
| kiosk `--budget 8000` | folds 63, dihedral p90 43.4°, lumpiness FAIL |
| sign `--budget 14000` | lumpiness ยัง FAIL (roughness 2.60°) + density WARN 4,075 tris/m² |
| sign เปลี่ยนขอบหยักเป็น rounded rect | roughness 4.08° → 1.93° (WARN) ค่า FAIL ส่วนใหญ่มาจากลอนที่ออกแบบไว้ |
| sign ตัด puff ของแผ่น / ตัดตัวอักษร | ยัง FAIL (4.83° / 2.39°) |

### ตัวอย่างอื่นที่รันแล้ว

| ชุด | ผล |
| --- | --- |
| ป้าย CAFE ใน `references/pipeline.md` (5,880 tris) | fail=0 warn=2 (fold จุดเดียว 122°, normal max 20.7°) |
| ป้ายตัวอักษรสูง 0.12 m ที่ 3,000 tris (ตัวอักษรชนขอบ) | fail=1 (lumpiness wobble 2.02°) ตัวอักษรยับใน clay แก้ด้วย `max_width`, ตัวใหญ่ขึ้น และงบ 6,000 |
| probe kiosk จาก SDF 3,000 tris | fail=0 warn=1 (fold 6 ขอบ 164°) dihedral p90 18.0°, sagitta p99 0.59 mm, lumpiness 0.12 / 1.01°, normal mean 0.11° max 1.9°, deviation p95 0.46 mm |
| SDF ย่อเป็น 6,000 / 3,000 / 1,500 tris | 0/0, 0/1 (fold), 0/0 union แบบคม (k = 0) FAIL normal p99 31° deviation 6 mm |
| shell แมพ demo ของ `sculpt_sweep.py` | `SCULPT_QA fail=1 warn=7` (รายละเอียดใน `references/map-pieces.md`) ทั้งที่ `MAP_INSPECT_PASS fail=0 warn=0` |

### ชุดทรงกล่อง low-poly แบบเดิม (14 prop จากเส้นทาง kawaii ก่อนมี sculpt-forge)

`SCULPT_QA fail=28 warn=95` โดยสัญญา prop ผ่านทุกชิ้น: `dihedral` FAIL 14/14 (p90 44.9-52.6°, 31.6-45.7% ของขอบเกิน 30°), `split_edges` FAIL 13 + WARN 1 (9.1-39.5%), `sagitta` WARN 12 + FAIL 1 (p99 2.7-10.3 mm), WARN ทุกชิ้นเรื่องไม่มี custom normals, quad ที่ไม่ triangulate, 56-234 shell และ shell ทะลุกัน, แผงแบนเงาเลอะ 13 ชิ้น, ขอบแข็ง > 120° 11 ชิ้น, ก้อนหยาบ 2 ชิ้น (~2.2°) split ratio ผ่านทุกชิ้น (1.20-2.03) นี่คือภาพของงานที่ดูเป็นกล่องต่อกัน

### ชุดทดสอบสังเคราะห์

| case | ผล |
| --- | --- |
| ก้อนเป็นปุ่ม (lumpy blob) | fail=3: roughness 3.99°, normal mean 6.12°, deviation p95 7.65 mm |
| ทรงกระบอก 8 ด้าน | fail=4: split 38%, dihedral p90 45°, sagitta 19 mm, deviation 19 mm |
| ดินน้ำมัน (playdough) | fail=3: wobble 1.74°, normal mean 3.84°, deviation 4.19 mm |
| triangle soup | fail=2: split 100%, split ratio 5.93 |
| พับ (folded) | fail=1: 12 หน้าพลิก 4.5% ของผิว |
| custom normals บน quad | fail=1 |
| `Color 1` เป็น FLOAT_COLOR/POINT | fail=1 |
| SDF normals ปกติไม่โอน | fail=1: normal max 78.6° |
| มาสคอต voxel | warn=4: roughness 2.33°, แผงเลอะ 14° |
| kitbash | warn=2: 5 shell ทะลุกัน, Weighted Normal หลัง triangulate ระลอก 1.17° |
| กล่อง smooth ธรรมดา | warn=2: แผงเอียง 10.43°, ไม่มี custom normals |
| กล่องมน Weighted Normal, ทรงกระบอกดี | 0 / 0 |
