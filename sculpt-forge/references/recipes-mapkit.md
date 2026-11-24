# Recipes: ชุดชิ้นแมพ (mapkit)

`scripts/blender/recipes/mapkit.py` คือชุดชิ้นแมพโค้งบน `SweepBuilder` สำหรับลานและสวน: ลานขอบมนมีเส้นทองฝัง, แถบโค้งฝังพื้น, แท่นกลมมีบันไดรอบและเส้นไฟทุกขั้น, กระบะต้นไม้รูปไตมีไฟใต้ขอบ, ม้านั่งไม้โค้ง, ม้านั่งพอง, เสาไฟเตี้ย, ราวกันตกมีโครงซี่โค้ง, ซุ้มโค้งไหลต่อเป็นกำแพงลอน, หลังคาใบไม้ และโคมประดับจาก SDF ทุก `begin()` คือ shell `.ydr` หนึ่งตัวที่วางได้หลายตำแหน่ง ผลผ่านสัญญา hero shell ของ map-forge และ export ด้วย `export_map.py` เนื้อหาเรื่อง `SweepBuilder`, path, profile, hard-edge guard และ UV อยู่ใน `references/map-pieces.md` ไฟล์นี้บอกเฉพาะสิ่งที่ kit เพิ่มและผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| ลานใหญ่ขอบ bullnose มีเส้นทองฝังรอบ | `plaza_slab` |
| แถบโค้งฝังพื้นมีเส้นขอบสองข้าง | `inlaid_band` (เส้นทางจาก `s_curve` หรือ `figure_eight`) |
| แท่นกลมมีบันไดรอบ เส้นไฟทุกขั้น ไฟฝังลูกตั้ง | `dais_steps` |
| กระบะต้นไม้รูปไต ไฟใต้ขอบปาก ไฟจริงรอบกระบะ | `kidney_planter` |
| ม้านั่งไม้ระแนงโค้ง ขาท่อ | `curved_bench` |
| ม้านั่งพองโค้ง เส้นไฟที่ฐาน | `puffy_bench` |
| เสาไฟเตี้ย แท่งเรืองแสง ไฟจริงที่หัว | `light_post` |
| ราวกันตกโค้ง ขอบหิน โครงซี่โค้งออก ลูกกรง | `ribcage_rail` |
| ซุ้มโค้งที่ไหลต่อเป็นกำแพงลอน เส้นไฟใต้ซุ้มและใต้ฝา | `arch_wave_wall` |
| หลังคาใบไม้บิดบนเสาเอียงคู่ | `leaf_canopy` |
| เครื่องประดับเนียนจาก SDF วางใน shell | `ornament_lantern` |
| ทรงอื่น | `sweep`, `tube`, `trim`, `slab`, `prism_collider`, `wall_collider` |

ไม่ใช้ kit นี้เมื่อ:

- prop เนียนเล็กกว่า ~3 m ที่ผู้เล่นเดินเข้าใกล้ ใช้ตระกูล `SculptBuilder` (`references/recipes-signs.md` ถึง `references/recipes-rounds.md`)
- ต้นไม้ พุ่มไม้ ไฟถนน ม้านั่งทั่วไปที่มี prop vanilla ของเกมอยู่แล้ว ใช้ prop vanilla ตาม map-forge (demo วางพุ่มไม้ vanilla 3 ต้นในกระบะผ่าน `map_spec`)
- ผังแมพทั้งผืน anchor หรือ MLO ใช้ map-forge (`map-forge/SKILL.md`)

## 2. โครงของ kit

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `MapKitRecipes(prefix="1nfx_mk", tex_dir=None, palette="house", engine_dir=None, turn_deg=4.0, embed=0.015)` | โหลด `sculpt_sweep` สร้าง `SweepBuilder(prefix)` และ role 15 ตัวพร้อม texture ใน `tex_dir` `embed` 1.5 cm คือความลึกที่ขา ผนัง และฐานจมใต้ z = 0 กันช่องลอย `turn_deg` คือมุมเลี้ยวสูงสุดต่อคอร์ดของเส้นทาง game |
| role | `paving` (`normal_spec.sps` อิฐ 1.2 × 0.6 m tile 2.4 m 512 px), `stone`, `step`, `band`, `shell`, `cushion`, `soil` (`default.sps` ลายหิน 256 px), `wood` (ลายไม้ tile 1.2 m), `slat` (`normal_spec.sps` ระแนง D/N/S 256 px), `gold`, `metal`, `post`, `panel` (swatch 16 px), `glow` (`emissivenight.sps` × 1.6, `#E8B04B`), `lamp` (`emissivenight.sps` × 2.2, `#FFF1D6`) role ที่เดินได้: `paving`, `step`, `band` `palette="pastel"` เปลี่ยนสี band, panel, cushion, wood, step, slat, gold |
| `begin(name, collision="CONCRETE", budget=12000, lod=200.0, placements=None)` | เริ่ม shell `<prefix>_<name>` (`placements` = list ของ ((x, y, z), yaw องศา) ค่าเริ่มหนึ่งจุดที่ศูนย์) คำสั่งหลังจากนี้ลง shell นี้ shell เดียววางซ้ำได้หลายจุด (demo เสาไฟ 4 จุด) |
| `add_light(light, lamp)` | เพิ่ม `Drawable.lights` ของ shell และโคมสำหรับคำนวณช่อง G |
| `MapKitLight.point(pos, intensity=2.0, falloff=4.0, color=(255, 199, 122), exponent=32.0, corona=0.35)` | ไฟ POINT สีอุ่น `#FFC77A` (2700-3000 K) `time_flags` NIGHT ไม่ทำเงา static |
| `MapKitLight.lamp(pos, radius=3.5, g=0.35, self_radius=None, self_g=None)` | โคมของช่อง G: `self_radius`/`self_g` ใช้กับ shell เจ้าของ `radius`/`g` ใช้กับ shell ข้างเคียง |
| `finish(props_dir, ao=True, ao_distance=1.6, ao_samples=48, save=True, high=True)` | ปิด shell ทุกตัวด้วย `SweepBuilder.finish` (ไม่ทำ AO) แล้ววางทุก shell ตามตำแหน่งจริง bake AO รวมกันด้วย Cycles เขียน `Color 1` (หัวข้อ 4) meta `style` = `sculpt_mapkit_v1` บันทึก `<props>/<shell>.blend` และ `<props>/<shell>_high.blend` (dense รวมชิ้น ใช้กับ `validate_sculpt`) คืน report ต่อ shell |
| `map_spec(map_name, center=(0, 0, 520), warp=None, vanilla=None, budgets=None)` | สเปก map-forge: entity หนึ่งตัวต่อ placement + prop vanilla, `archetype_type` = `plaza_kit` |
| `export(out_dir, spec_path, props_dir, tex_dir, blender=None, map_forge=None)` | รัน `export_map.py` และ `inspect_map.py` แบบไม่ใส่ `--factory-startup` |
| `validate(props_dir, json_path)`, `qa_renders(props_dir, out_dir, qa_json)` | `validate_sculpt.py --target map` และ `render_sculpt.py` |

## 3. builder และค่าที่ใช้

ตัวเลขในวงเล็บคือค่าเริ่มเป็นเมตร

| method | ทำอะไร | พารามิเตอร์หลัก | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `plaza_slab(outline, thickness=1.0, rim_radius=0.3, rim_segments=6, top_role="paving", rim_role="stone", bottom_role="stone", spacing=1.25, edge_inset=0.55, edge_width=0.05, edge_role="gold")` | ลานหนา ขอบ bullnose ฝาบน Delaunay มีจุดทุก 1.25 m ให้ AO, เส้นทองห่างขอบ 0.55 m | | ขอบ 30% ของความหนา (กฎ slab แมพ 25-35%), เส้นขอบ 5 cm |
| `inlaid_band(path, width=1.6, closed=False, line_width=0.05, z=0.0, band_role="band", line_role="gold", height=0.003, embed=0.004)` | แถบเรียบฝังพื้น + เส้นขอบสองข้าง ตัดเส้นที่ทับตัวเองตรงโค้งแคบ | demo กว้าง 1.5 m | เส้นขอบ 5 cm, แถบนูน 3 mm ฝัง 4 mm (studio ใช้แถบ 2.5-3 m) |
| `dais_steps(radius=1.9, steps=4, rise=0.15, run=0.40, nosing=0.04, back=0.30, strip_w=0.055, strip_setback=0.06, pad_every=1.7, pad_len=0.12, pad_h=0.06, ...)` | แผ่นบนกลมสูง `steps` × `rise`, บันไดวงรอบจมูกมน, เส้นไฟ `glow` ทุกขั้น, ไฟฝังลูกตั้ง `lamp`, กล่องชนเป็นขั้น | | จมูก 4 cm (ของจริง 2-3 cm, ของเล่น 5-8 cm), เส้นไฟ 5.5 cm ห่างจมูก 6 cm (กฎ 5-6 cm), ไฟลูกตั้ง 12 × 6 cm ทุก 1.7 m (studio 1.5-2 m) |
| `kidney_planter(length=4.6, width=2.3, dent=0.38, height=0.55, wall=0.10, lip_r=0.045, overhang=0.06, soil_drop=0.09, glow_w=0.03, lights=2, light_radius=3.2, ...)` | ผนังรูปไต ปากยื่นมน แผ่นดิน CDT ทุก 0.45 m, เส้นไฟใต้ปาก หันออก, ไฟจริงรอบกระบะ, กล่องชน prism | | ปากมน 4.5 cm ยื่น 6 cm, เส้นไฟ 3 cm (กฎใต้ฝา 3-5 cm), ไฟ 1.6 × 3.2 m วางห่างขอบ 0.32 m สูง 0.30 m (studio ไฟหนึ่งดวงต่อกระบะ 4-6 m ระยะ 3-4 m) |
| `curved_bench(radius=3.0, length=2.4, seat_h=0.45, depth=0.46, slats=4, slat_t=0.045, gap=0.018, supports=2, support_r=0.028, ...)` | ระแนง 4 แผ่นตามวงโค้ง, ขาท่อรูป U หักมุมมน 7 cm, กล่องชนผนังบาง | demo ยาว 2.6 m | ระแนงหนา 4.5 cm มน 45%, ขาท่อ r 2.8 cm 12 ด้าน |
| `puffy_bench(radius=4.0, length=2.6, seat_h=0.44, depth=0.52, crown=0.03, top_r=0.13, glow=True, ...)` | หน้าตัดเบาะโป่ง 3 cm ขอบบนมน 13 cm ปลายโดม, เส้นไฟ 3 cm สูง 5.5 cm | demo ยาว 2.8 m | ขอบบน 25% ของความลึก |
| `light_post(height=1.9, size=0.24, corner=0.035, bar_w=0.045, bar_gap=0.05, head_h=0.16, cap=0.06, intensity=2.0, falloff=4.0, ...)` | ฐานมน, เสาเหลี่ยมมน, แท่ง `lamp` สองแท่งทะลุหน้าหลัง, หัวเรืองแสง, ฝา, ไฟ POINT ที่กลางหัว | | เสา 1.6-2.0 m แท่ง 4-5 cm ตามกฎ, ไฟ 2.0 ระยะ 4 m |
| `ribcage_rail(path, height=1.05, top_r=0.035, curb_w=0.2, curb_h=0.1, baluster_r=0.015, pitch=0.28, rib_every=3.4, rib_r=(0.10, 0.05), rib_rise=0.85, rib_bend=1.25, rib_sweep=105, side=1.0, glow=True, ...)` | ขอบหิน bullnose, ท่อราวบนปลายโดม, ซี่ตั้งเรียว 10 → 5 cm โค้งออกรัศมี 1.25 m, ลูกกรงทุก 28 cm, เส้นไฟ 2.5 cm ที่ขอบหิน, กล่องชนผนัง 16 cm | | ราวแมพ r 3.5 cm (กฎ ≥ 3.5 cm), ลูกกรง r 1.5 cm 12 ด้าน |
| `arch_wave_wall(span=3.6, height=4.2, arch=(0.52, 0.62, 0.16), cap=(0.26, 0.44, 0.10), wall_t=0.22, wall_len=7.2, wall_z=(2.1, 3.0), waves=3, fillet=0.9, end_fillet=0.7, intrados_w=0.06, intrados_from=1.0, cap_glow_w=0.035, light=True, ...)` | เส้นทางเดียว: ขาซุ้ม → ครึ่งวง → ลง → โค้งเข้า 0.9 m → ฝาคลื่น 3 ช่วง → โค้งลง 0.7 m → เท้า หน้าตัดค่อยๆ เปลี่ยนจาก 0.52 × 0.62 เป็น 0.26 × 0.44, ผนังระแนงใต้ฝา, เส้นไฟใต้ฝาและใต้ซุ้ม, ไฟที่ซุ้ม | | ไม่มีรอยต่อระหว่างซุ้มกับกำแพงเพราะเป็น sweep เดียว, ไฟ 2.2 ระยะ 5 m |
| `leaf_canopy(length=8.0, width=2.6, height=3.1, droop=0.35, bow=0.5, twist=14, sag=0.10, edge_r=0.05, rib_every=0.8, spine_r=0.045, posts=(0.32, 0.68), post_r=0.07, lean=0.35, panel_t=0.024, glow=True, light=True, ...)` | ท่อขอบใบ, แผ่นใบสองหน้าหนา 2.4 cm, ซี่ทุก 0.8 m, แกนกลาง, เสาเอียงคู่ฐานกลม, เส้นไฟใต้แกน, ไฟใต้ใบ | | ใบบิด 14° ตกท้องช้าง 0.35 m |
| `ornament_lantern(loc=(0, 0, 0), height=1.6, work_dir=None, voxel=0.007, budget=2200, high_tris=150000)` | ปั้นโคมด้วย `SculptBuilder` (target library) แล้วนำ low เข้า game และ high เข้า dense ของ shell พร้อมกล่องชน prism | | สะพานจาก SDF เข้า shell, demo 2,156 tris 4.6 วินาที ผิดจาก dense ไม่เกิน 0.052° |

ส่วนช่วย: `sweep(path, profile, ..., turn=None, profile_b=None, mix=None, scale=None)` (เปลี่ยนหน้าตัดตามระยะด้วย `profile_b` + `mix` หรือย่อขยายด้วย `scale` เช่น `Taper`), `trim(path, width=0.05, face="up"/"in"/"out", height=0.003, embed=0.004, role="glow")`, `tube(path, radius, caps="round", segments=None, taper=None)`, `slab(outline, thickness, edge_radius=0.3, ...)`, `prism_collider`, `wall_collider`, `figure_eight`, `s_curve` และคลาส `KidneyOutline`, `Taper`, `Blend`, `LeafShape`

## 4. RAGE vertex colour (`Color 1`)

| ช่อง | ค่าที่ kit เขียน |
| --- | --- |
| R และ B | 0.58 + 0.42 × AO (Cycles, ระยะ 1.6 m, 48 sample, ทุก shell วางที่ตำแหน่งจริงและบังกัน) หน้าที่ซ่อนได้ R 148 |
| G | 0 กลางแจ้ง ใกล้โคม = g × (1 - smoothstep(0, radius, d)) เลือกค่ามากสุดของทุกโคม |
| A | 255 |
| หน้า role emissive (`glow`, `lamp`) | 255 ทุกช่อง |

กฎ:

1. กลางแจ้ง G = 0 เสมอ G 0.25-0.45 เฉพาะในรัศมีโคมเท่านั้น RAGE ใช้ช่อง G เป็นแสงประดิษฐ์ตอนกลางคืน ผิวที่ G สูงจะสว่างเองทั้งคืน
2. `inspect_map` เตือนเมื่อ G เฉลี่ยกลางแจ้งของ drawable เกิน 45 (สเปก `max_outdoor_vcol_g` 45)
3. shell ที่วางจุดเดียวได้ G จากโคมของตัวเอง (`self_radius`/`self_g`) และโคมของ shell อื่นที่รัศมีถึงกล่องของมัน shell ที่วางหลายจุดใช้ drawable เดียวกันทุกจุด จึงได้แค่โคมของตัวเอง
4. รัศมีโคมของ kit: เสาไฟ 3.6 m / 0.35 (ตัวเอง 0.55 m / 0.30), กระบะ 3.2 m / 0.32 (ตัวเอง 1.92 m / 0.22), ซุ้มและหลังคาใบไม้ 4.0 m / 0.30 (ตัวเอง 2.0 / 1.5 m, 0.22 / 0.20)
5. วาง shell กลางแจ้งให้พ้นรัศมีโคมของ shell อื่น หรือลด `light_radius`/`g` ของโคม ห้ามแก้ด้วยการเขียนสีทับหลัง `finish`

ผลใน demo (G เฉลี่ยกลางแจ้ง 0-255): ลาน 2.8, แท่น 0, กระบะ 12.8, ม้านั่งระแนง 67.3, ม้านั่งพอง 0, เสาไฟ 29.6, ราว 0, ซุ้ม 3.7, หลังคาใบไม้ 2.2 ม้านั่งระแนงวางห่างกระบะ 1.2 m เกือบทั้งตัวอยู่ในรัศมีโคมกระบะสองดวง `inspect_map` จึงเตือน `high outdoor DIFFUSE.G (65.3 > 45.0)`

## 5. เสาไฟและเส้นไฟ

- ไฟจริงเก็บเป็น `Drawable.lights` ใน `map_forge` meta ของ shell และ export ลง `.ydr` (demo 5 ดวง: กระบะ 2, เสาไฟ 1, ซุ้ม 1, หลังคาใบไม้ 1) สี `#FFC77A` NIGHT ระยะ 3.2-5 m
- `light_post` สูง 1.9 m แท่ง `lamp` 4.5 cm สองแท่งทะลุหน้าหลังตั้งแต่ 0.32 m ถึงใต้หัว หัวเรืองแสง 16 cm ไฟ POINT ที่กลางหัว ความเข้ม 2.0 ระยะ 4 m studio วางเสาทุก 12-15 m demo วาง 4 ต้นรอบลาน 30 × 22 m
- เส้นไฟทุกเส้นเป็น `trim` (แถบนูน 3 mm ฝัง 4 mm มีแค่ระดับ game ไม่ถูกย่อ normals อัตโนมัติ) ใน kit: ขั้นแท่น 5.5 cm, ไฟลูกตั้ง 12 × 6 cm, ใต้ปากกระบะ 3 cm, ฐานม้านั่งพอง 3 cm, ขอบหินของราว 2.5 cm, ใต้ฝากำแพง 3.5 cm, ใต้ซุ้ม 6 cm (`lamp` เริ่มที่ z ≥ 1 m), ใต้แกนหลังคา 2 cm
- `glow` และ `lamp` ใช้ `emissivenight.sps` ติดเฉพาะกลางคืน กลางวันเป็นสีอ่อนธรรมดา เส้นทองของลานและแถบเป็น `gold` (`default.sps` swatch) ไม่เรืองแสง
- ซ่อนเส้นไฟใต้จมูก ใต้ฝา ใต้ปาก พื้นคงมืด และให้พื้นที่เรืองแสง 5-15% ของผิว (`references/smooth-craft.md` หัวข้อ 13-14) shader และการตั้งไฟละเอียดอยู่ใน `map-forge/references/shaders-lighting-vcol.md`

## 6. กฎคอร์ดของเส้นโค้ง

เส้นทางระดับ game ของทุกชิ้นใน kit ผ่าน `MapKitShape.resample_chord` (ระดับ dense ใช้ dense ของ `SweepBuilder`: 0.75° และ 8 cm, กล่องชน 10° และ 1.5 m)

| กฎ | ค่า |
| --- | --- |
| มุมเลี้ยวต่อคอร์ด | ≤ `turn_deg` 4° หรือมุมที่ให้ sagitta 1 mm ถ้ามากกว่า (R เล็กกว่า ~1.6 m เลี้ยวได้มากกว่า 4°) |
| ความยาวคอร์ด | ≤ 0.25 m เมื่อ R ≤ 10 m, ≤ 0.5 m เมื่อ R ≤ 30 m, ≤ 1.5 m (`straight`) เมื่อเกินนั้นหรือเส้นตรง |
| มุมหัก | จุดที่เลี้ยว > 25° คงเป็นมุม ไม่ถูกเกลี่ย |
| วงเต็ม | `chord_count(R, 360, turn_deg, minimum)` = max(ขั้นต่ำ, 360° / มุมเลี้ยว, เส้นรอบวง / คอร์ด) |

ตัวเลขที่ได้: วงบันไดแท่น R 3.1 m = 90 คอร์ด, มุมลาน R 5 m ช่วง 90° = 32 คอร์ด (2.8° ต่อคอร์ด), วงเต็ม R 10 m = 252, R 30 m = 377 กฎนี้ตรงกับ `references/smooth-craft.md` หัวข้อ 9 (คอร์ด ≤ 0.25 m ที่ R ≤ 10 m, ≤ 0.5 m ที่ R ≤ 30 m) ขอบที่ผู้เล่นยืนต้องได้ ~64 ด้านต่อรอบเมื่อมองจากระยะ ≥ R ห้ามส่ง `turn=` ที่หยาบกว่า 4° ให้ขอบลานหรือบันได (ขาม้านั่งใช้ `turn=10` เพราะเป็นท่อเล็กมุมหัก)

## 7. งบ shell

| เรื่อง | ค่า |
| --- | --- |
| งบต่อ shell | `begin(..., budget)` เพดาน 40,000 (`SweepBuilder` ตัดให้) `inspect_map` เตือนเกิน 45,000 ต่อ drawable |
| งบ demo | ลาน 16,000, แท่น 16,000, ราว / ซุ้ม / หลังคาใบไม้ 12,000, กระบะ 8,000, ม้านั่งระแนง 4,000, ม้านั่งพอง 3,000, เสาไฟ 2,400 |
| งบรวมแมพ | demo `max_total_tris` 48,000, `max_ytd_vram_mb` 4, `max_disk_mb` 8 งบตามชนิดแมพใน `map-forge/references/studio-benchmarks.md` |
| ความยาวราว | ราว demo 7,804 tris บน 15.9 m (≈ 490 tris/m: ขอบหิน 1,008, ท่อบน 1,344 ≈ 84 tris/m, ซี่ 6 ซี่ 4,020, ลูกกรง 51 ต้น 1,224 = 24 ต่อต้น, เส้นไฟ 208) |
| `lod` | ลานและซุ้ม 400, หลังคาใบไม้ 300, แท่น 250, ราว 200, กระบะและเสาไฟ 150, ม้านั่ง 120 (ytyp `lodDist` = `hdTextureDist`) |

งบคือเพดาน จำนวน tris มาจากกฎคอร์ดและหน้าตัด ไม่ใช่จากงบ demo ไม่มี shell ไหนต้องย่อ (`collapse_ratio` 1, `over_budget` false) ถ้า `over_budget` เป็น true ให้ลดคุณภาพหรือแยก shell อย่าพึ่ง COLLAPSE (`references/map-pieces.md` หัวข้อ 6)

## 8. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): กระบะ 3,857 tris (G เฉลี่ย 12.8), เสาไฟ 1,048 tris วาง 2 จุด (G 29.6), `MAP_EXPORT_PASS ydr_ok=2 fail=0 textures=19`, `MAP_INSPECT_PASS fail=0 warn=0`

```python
import importlib
import json
import os
import sys


class CafeCorner:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        mk = self.module("mapkit")
        kit = mk.MapKitRecipes("1nfx_cafe", os.path.join(self.out_dir, "textures"), "house")
        kit.begin("planter", "STONE", 8000, 150.0, [((0.0, 0.0, 0.0), 0.0)])
        kit.kidney_planter(4.6, 2.3, 0.38, lights=2, light_radius=3.2)
        kit.begin("post", "METAL_SOLID_MEDIUM", 2400, 150.0, [((-6.0, 3.0, 0.0), 0.0), ((6.0, 3.0, 0.0), 0.0)])
        kit.light_post(1.9)
        report = kit.finish(os.path.join(self.out_dir, "props"))
        spec = kit.map_spec("1nfx_cafe_map", (0.0, 0.0, 520.0), [0.0, -4.0, 520.5, 0.0])
        with open(os.path.join(self.out_dir, "map-spec.json"), "w", encoding="utf-8") as handle:
            json.dump(spec, handle, indent=1)
        return report


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    report = CafeCorner(argv[0], argv[1]).build()
    print("CAFE_CORNER " + json.dumps({sid: [v["tris"], v["vcol"]["G_mean_outdoor"]] for sid, v in report["shells"].items()}), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
$mf  = "$skill\map-forge\scripts\blender"
$out = '<project>\work\cafe_map'
& $blender -b --factory-startup -t 6 -P '<project>\work\cafe_map\cafe_corner.py' -- $skill $out
& $blender -b -t 6 -P "$mf\export_map.py" -- --spec "$out\map-spec.json" --props "$out\props" --textures "$out\textures" --out "$out\pkg"
& $blender -b -t 6 -P "$mf\inspect_map.py" -- --dir "$out\pkg\stream" --spec "$out\map-spec.json" --json "$out\inspect_report.json"
& $blender -b --factory-startup -t 6 -P "$skill\sculpt-forge\scripts\blender\validate_sculpt.py" -- --blend "$out\props" --target map
```

- ชิ้นแมพจบด้วย `kit.finish(props_dir)` ไม่ใช่ `build()` แล้วตามด้วย `map_spec()` และ export สองคำสั่ง
- วาง shell ซ้ำด้วย `placements` ไม่ต้อง build ซ้ำ ทุกจุดเป็น entity ของ drawable เดียว
- export ห้ามใส่ `--factory-startup` (ต้องโหลด Sollumz + PyMateria) build ต้องเป็น 4.2.3 (5.x ทำได้แต่ไฟล์เปิดใน 4.2.3 ไม่ได้)
- ห้ามย้ายหรือเปลี่ยนชื่อโฟลเดอร์ผลหลัง build: shell เก็บพาธ texture แบบ absolute ทดสอบแล้วได้ `Missing pre-encoded DDS for DiffuseSampler` และ `MAP_EXPORT_FAIL ok=0 fail=2` ให้ build ใหม่ในที่ใหม่แทน
- ผ่าน MCP: `MapKitRecipes(engine_dir=...)` หา `sculpt_sweep.py` จากอาร์กิวเมนต์, env `SCULPT_FORGE_DIR`, `__file__`, โฟลเดอร์ทำงาน และโฟลเดอร์ของ `.blend` ที่เปิด ส่ง `engine_dir` ตรงๆ เมื่อรันจาก exec

## 9. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\mapkit'

& $blender -b --factory-startup -t 6 -P "$sf\recipes\mapkit.py" -- --demo --out $work --export --validate
& $blender -b --factory-startup -t 6 -P "$sf\recipes\mapkit.py" -- --demo --out "$work\pastel" --palette pastel --quick
```

จำกัดเธรดเสมอ: `MapKitRecipes.run_tool` ส่ง `-t <bpy.context.scene.render.threads>` ให้ Blender ลูก (`export_map`, `inspect_map`, `validate_sculpt`, `render_sculpt`) ลูกจึงใช้เธรดเท่าตัวแม่ที่รันด้วย `-t 6` และรันทีละตัวผ่าน `subprocess.run` ภาพ preview ของ kit (`MapKitPreview`) เรนเดอร์ 900 × 560 ทั้งโหมดปกติและ `--quick` (เดิมโหมดปกติ 1280 × 800) AO bake ใช้ Cycles บน CPU

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--demo` | ต้องใส่ (ไม่ใส่พิมพ์ `MAPKIT_USAGE` แล้วจบ จึง exec ผ่าน MCP ได้ปลอดภัย) | build ชุด demo ลบ object ทุกตัวในไฟล์ก่อน ใช้กับ CLI เท่านั้น |
| `--out <dir>` | `<temp>\sculpt_mapkit_demo` | โฟลเดอร์ผล |
| `--prefix` | `1nfx_mk` | prefix ของ shell และ texture |
| `--palette` | `house` | `house` หรือ `pastel` |
| `--engine-dir <dir>` | หาเอง | โฟลเดอร์ที่มี `sculpt_sweep.py` |
| `--map-forge <dir>` | `<skill>\map-forge\scripts\blender` | ที่อยู่ `export_map.py`/`inspect_map.py` |
| `--blender <exe>` | Blender ที่รันอยู่ | ตัวที่ใช้ export และ QA |
| `--samples` | 48 | sample ของ AO |
| `--export` | | รัน `export_map.py` + `inspect_map.py` |
| `--validate` | | รัน `validate_sculpt.py --target map` เขียน `sculpt_qa.json` |
| `--qa-renders` | | รัน `render_sculpt.py` ลง `qa_renders/` (รวม `--validate`) |
| `--no-render` | | ข้ามภาพ preview ของ kit |
| `--quick` | | sample ของ preview 16 และไม่มีภาพ vcol/tex/high/normal ของ close-up (ขนาด 900 × 560 เท่ากันทั้งสองโหมด) |

ผล: `props/<shell>.blend` + `props/<shell>_high.blend`, `textures/` (PNG ก่อน export, DDS หลัง export), `renders/` (`overview_clay`, `overview_tex`, `overview_vcol`, `night_overview`, `night_eye` และต่อ close-up `_lo`, `_tex`, `_hi`, `_nlo`, `_nhi`, `_nerr`), `map-spec.json`, `mapkit_report.json` (`shells`, `screen_normal_lo_vs_dense`, `export`, `validate`), `mapkit_demo_all.blend`, `work/ornament/`, `pkg/stream/` + `pkg/fxmanifest.lua`, `inspect_report.json`, `sculpt_qa.json` บรรทัดที่พิมพ์: `MAPKIT_REPORT {...}` (ต่อ shell: tris, งบ, dihedral p90, normal err สูงสุด, G เฉลี่ยกลางแจ้ง), `MAPKIT_EXPORT <บรรทัด tag>`, `MAPKIT_VALIDATE <บรรทัด>`

## 10. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, palette `house`, ลาน 30 × 22 m มุม R 5 m, anchor บนฟ้า (0, 0, 520) build 5.8 วินาที, finish (AO + save) 6.7 วินาที, รวม export, validate และภาพ preview 900 × 560 ราว 30 วินาที (`-t 6`, รันตระกูลเดียว)

| shell | ทำจาก | tris / งบ (dense) | วาง | G กลางแจ้ง | dihedral p90 | หมายเหตุ |
| --- | --- | --- | --- | --- | --- | --- |
| `1nfx_mk_plaza` | `plaza_slab` + `inlaid_band` (S-curve 17.4 m) | 6,180 / 16,000 (61,436) | 1 | 2.8 | 15.0° | floor ตรงกล่องชน 100% (957 จุด) |
| `1nfx_mk_dais` | `dais_steps` + `ornament_lantern` | 9,710 / 16,000 (238,316) | 1 | 0 | 22.5° | ไฟลูกตั้ง 35 ดวง, โคม SDF 2,156 tris, floor 100% |
| `1nfx_mk_planter` | `kidney_planter` | 3,857 / 8,000 (99,300) | 1 | 12.8 | 22.5° | ไฟ 2 ดวง |
| `1nfx_mk_bench` | `curved_bench` | 1,992 / 4,000 (123,080) | 1 | 67.3 | 30.2° | G เกิน 45 (หัวข้อ 4) |
| `1nfx_mk_puffy` | `puffy_bench` | 708 / 3,000 (8,190) | 1 | 0 | 18.9° | |
| `1nfx_mk_post` | `light_post` | 1,048 / 2,400 (69,964) | 4 | 29.6 | 22.5° | ไฟ 1 ดวง |
| `1nfx_mk_rail` | `ribcage_rail` 15.9 m | 7,804 / 12,000 (337,260) | 1 | 0 | 30.0° | ซี่ 6, ลูกกรง 51 |
| `1nfx_mk_archwall` | `arch_wave_wall` เส้นทาง 21.8 m | 7,028 / 12,000 (135,908) | 1 | 3.7 | 18.0° | ไฟ 1 ดวง |
| `1nfx_mk_canopy` | `leaf_canopy` 8 m | 7,654 / 12,000 (227,556) | 1 | 2.2 | 22.5° | ไฟ 1 ดวง |

| ประตู | ผล |
| --- | --- |
| export | `MAP_EXPORT_PASS ydr_ok=9 fail=0 textures=19`, `.ybn` 7,448 prims (กล่องชนวาง 20 ชิ้น), shared `.ytd` 19 texture VRAM 0.67 MB, `.ytyp` 9 archetype, `.ymap` 15 entity (kit 12 + vanilla 3) `content_flags` 65, ดิสก์ 1.19 MB, 45,981 tris รวม, ไฟ 5 ดวง |
| inspect | `MAP_INSPECT_PASS fail=0 warn=1` (G ของม้านั่งระแนง) |
| normal บนจอ (low เทียบ dense มุมเดียวกัน) | ราว mean 0.36° p99 4.1°, บันได 0.43° / 5.9°, ซุ้ม 0.09° / 1.5°, ม้านั่งพอง 0.31° / 3.0°, หลังคาใบไม้ 0.34° / 5.1°, เสาไฟ 0.13° / 2.2°, โคม 0.60° / 11.3°, กระบะ 1.46° / 50.8° และม้านั่งระแนง 1.53° / 47.0° (สีแดงใน `_nerr.png` อยู่บนแผ่นดินกระบะและที่หักมุมของขาท่อ) |
| `validate_sculpt --target map` | engine ปัจจุบัน (guard normals ของ sweep): `SCULPT_QA fail=0 warn=18` รันก่อนหน้า `SCULPT_QA fail=5 warn=19` เป็นข้อมูลประกอบ ไม่ใช่ประตู: `normal_error` FAIL ที่ม้านั่งระแนง หลังคาใบไม้ กระบะ ม้านั่งพอง ราว (max ~90° จากการเทียบข้ามขอบคม 90° กับ dense ที่รวมชิ้น), `interpenetration` WARN ทุก shell (ชิ้นแยกส่วนโดยตั้งใจ), `walk_surface` WARN ที่หลังคาใบไม้ (ไม่มีพื้นที่ z = 0) |

## 11. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key หรือบรรทัดที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| `overview_vcol.png` และภาพกลางคืน: ม้านั่งสว่างทั้งตัวทั้งที่ไม่มีไฟ | `inspect_map` WARN `high outdoor DIFFUSE.G (65.3 > 45.0)` | shell วางจุดเดียวอยู่ในรัศมีโคมของ shell อื่นเกือบทั้งตัว | ย้ายออกนอกรัศมีโคม หรือลด `light_radius`/`g` ของโคมข้างเคียง แล้ว `finish` ใหม่ |
| export ล้มทุก drawable | `Missing pre-encoded DDS for DiffuseSampler: <พาธเก่า>`, `MAP_EXPORT_FAIL` | ย้ายหรือเปลี่ยนชื่อโฟลเดอร์ผลหลัง build | build ใหม่ในโฟลเดอร์ปลายทาง |
| ขอบลานหรือบันไดเห็นเป็นเหลี่ยมใน clay ระยะใกล้ | `sagitta` (map) | ส่ง `turn=` หยาบหรือ resample เส้นทางเองก่อนเข้า kit | ใช้ `turn_deg` 4° และกฎคอร์ดค่าเริ่ม ส่งเส้นทางละเอียด (step 0.02 m) ให้ kit resample เอง |
| ขาท่อม้านั่งมีจุดแดงที่หักมุมใน `_nerr.png` | `normal_error` FAIL, screen p99 47° | ท่อ r 2.8 cm 12 ด้านหักมุมรัศมี 7 cm | ยอมรับได้ระยะไกล ถ้าเห็นใกล้ให้ประกอบเองด้วย `tube(segments=4)` (16 ด้าน) แล้ววัดใหม่ |
| แผ่นดินกระบะแดงใน `_nerr.png` | screen p99 50.8° | แผ่นดิน CDT หยาบ (จุดทุก 0.45 m) | วางพุ่มไม้ vanilla ทับ (demo ทำผ่าน `map_spec(vanilla=...)`) |
| ผิวรับแสงกลางคืนเกินหรือพื้นเรืองแสง | `inspect_map` G WARN, ภาพ `night_eye.png` | ตั้ง `g` > 0.45 หรือรัศมีโคมใหญ่เกิน, ใส่ role emissive บนพื้น | G 0.25-0.45 รัศมีเท่าระยะไฟจริง พื้นใช้ role ที่ไม่เรืองแสง |
| `over_budget` เป็น true | report ของ `finish` | shell ใหญ่หรือชิ้นเยอะเกินงบ | ลด `rim_segments`, จำนวนลูกกรง/ซี่ หรือแยก shell |
| ซุ้มกับกำแพงมีรอยต่อแข็ง | | สร้างซุ้มและกำแพงเป็นสอง sweep | ใช้ `arch_wave_wall` (sweep เดียว + `profile_b`/`mix`) หรือทำแบบเดียวกันเอง |
| `validate_sculpt` FAIL `normal_error` max 90° | target map | เทียบ corner normal ข้ามขอบคม 90° กับ dense ที่รวมชิ้น | ตัดสินด้วยภาพ `_nerr.png` และ `MAP_INSPECT_PASS` ตาม `references/map-pieces.md` หัวข้อ 9 |

## 12. ประตู QA

1. อ่าน report ของ `finish` ทุก shell: `reduce.over_budget` false, `floor.within_2cm` 1.0 สำหรับ shell ที่เดินได้, กล่องชน `non_manifold_edges` 0 และปริมาตรบวก, `vcol.G_mean_outdoor` ≤ 45, `dihedral.frac_over_30` ต่ำ (ราว 15.7% และม้านั่งระแนง 11.9% มาจากท่อ 12 ด้าน)
2. `export_map.py` ต้องได้ `MAP_EXPORT_PASS ydr_ok=N fail=0`
3. `inspect_map.py` ต้องได้ `MAP_INSPECT_PASS fail=0` และอ่าน WARN ทุกตัว WARN เรื่อง G ต้องแก้ก่อนส่ง
4. (แนะนำ) เปิดภาพ `overview_clay`, `overview_vcol`, `night_overview`, `night_eye` และ `_nerr.png` ของ close-up ทุกชิ้น และรัน `validate_sculpt.py --target map` เป็นข้อมูลประกอบ
5. รายงานว่ายังไม่ได้ทดสอบในเกม รายการลองในเกม: เดินบนลาน แท่น และบันไดทุกขั้น (กล่องชนเป็นขั้น), ชนราวและม้านั่ง, ดูตอน 23:00 ว่าพื้นไม่เรืองแสง และเส้นไฟกับไฟจริงติดเฉพาะกลางคืน
6. texture ใน kit เป็นลาย procedural เปลี่ยนเป็นของจริงตาม map-forge (เช่น CC0) ก่อนใช้งาน และใส่ prop vanilla ตามผังของ map-forge
