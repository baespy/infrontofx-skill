# Pipeline: เครื่องยนต์ SculptBuilder

ไฟล์หลักคือ `scripts/blender/sculpt_forge.py` (library ล้วน รันตรงได้แค่ `--selftest`) และ `scripts/blender/forge_sculpt.py` (CLI อ่านสเปก JSON) ใช้แค่ bpy, bmesh, mathutils, numpy และ pyopenvdb ที่มากับ Blender 4.2.3 ไม่ต้องลง add-on ตอนปั้น Sollumz ใช้เฉพาะตอน export

## 1. ลำดับ stage

| # | stage | ทำอะไร | key ใน `timings` |
| --- | --- | --- | --- |
| 1 | prepare | band = max(3·voxel, 1.25·fillet สูงสุด + 2·voxel, abs(iso) + 3·voxel), probe band = max(band, 1.1·`ao_distance`), สร้าง raster 2D ของ `lathe`/`extrude2d` ที่ voxel/2 และ level set ของ `text`/`mesh_part` | `prepare` |
| 2 | evaluate | grid float32 หนาแน่นครอบทุก node union + band + 2 voxel ประเมินด้วย numpy เป็นแผ่นตามแกน z (~4 M voxel ต่อแผ่น) แล้ว `copyFromArray` ลง pyopenvdb `FloatGrid` แบบ level set | `evaluate` |
| 3 | mesh | `convertToPolygons(isovalue=iso, adaptivity=0)` ได้ tris + quads ตรวจทิศหน้าจาก 512 หน้าเทียบ field แล้วกลับถ้าหันเข้า | `mesh` |
| 4 | roles | role ต่อหน้า = node ที่ใกล้ที่สุด (argmin) ที่จุดกลางหน้า, majority filter 3 รอบ, ถ้า `smooth_roles` เกลี่ยเส้นแบ่งสี 4 รอบ (น้ำหนัก 0.5) แล้วฉายกลับลงผิว SDF | `roles` |
| 5 | high | object `<id>_high` (material `sf_role_<role>` ต่อ role) smooth ทั้งตัว | `high_object` |
| 6 | reduce | ดูหัวข้อถัดไป | `reduce` |
| 7 | normals | smooth ทุกหน้า ลบ `sharp_edge`/`sharp_face` แล้ว `DATA_TRANSFER` (`CUSTOM_NORMAL`, `POLYINTERP_NEAREST`, REPLACE 1.0) จาก high แล้ว apply นี่คือขั้นสุดท้ายของ geometry | `normals` |
| 8 | poly parts | `bevel_box`/`poly_part`: smooth + `WEIGHTED_NORMAL` (FACE_AREA, 50, keep_sharp) + `TRIANGULATE` (BEAUTY, keep_custom_normals) apply แล้ว join เข้า low | |
| 9 | recentre | จุดต่ำสุด z = 0, กลางกล่อง XY = 0 (ย้าย high ไปด้วย ค่าที่ย้ายเก็บเป็น `shift`) | |
| 10 | surface | palette UV ชั้นเดียวชื่อ `UVMap` หรือ atlas bake, material หนึ่งตัวต่อ finish ที่ใช้จริง เรียง satin, matte, gloss, emissive | `surface` |
| 11 | `Color 1` | SDF AO จาก probe 5 จุดถึง `ao_distance` (น้ำหนักลดครึ่งทุกจุด นับพื้นที่ z ต่ำสุดด้วย) เขียนเป็น BYTE_COLOR / CORNER เทา R ≥ 194, G/B ≥ 192 หน้า emissive = 255 โหมด atlas ย้าย AO ไปไว้ใน texture | `surface` |
| 12 | rig | เฉพาะ target prop ที่มี `set_anim` และกระดูก: `<id>_rig`, vertex group, ARMATURE modifier, `<id>_action` | |
| 13 | colliders | เฉพาะ target prop: กล่อง `<id>_col_N` ใน collection `<id>_collision` (WIRE, `hide_render`, `prop_forge_collision` = `box`) | |
| 14 | measure | `QualityProbe.measure` (ดูหัวข้อ 8) | `measure` |
| 15 | save | เขียน high (ย่อเหลือ `high_tris` ถ้าเกิน) ลง `_high/<id>_high.blend`, ลบ high, purge orphan, บันทึก `<id>.blend` (CLI ใช้ `save_as_mainfile`, GUI/MCP ใช้ `bpy.data.libraries.write` เฉพาะ root, rig และ collision) | `save` |

### ขั้น reduce

1. สำรอง tris ของ poly part ไว้ก่อน: limit = max(500, (budget - tris ของ poly part) × 0.985)
2. ย่อขั้นกลางด้วย COLLAPSE ไปที่ limit × `stage_ratio` (1 รอบ) แล้ว repair
3. ถ้า node `detail=True` กินผิวไม่เกิน `detail_share` จะกันความหนาแน่นของ node เหล่านั้น เกินแล้วขึ้น warning และไม่กัน
4. ย่อจริงไปที่ limit สูงสุด 3 รอบ รอบหลังกันบริเวณที่พังในรอบก่อน (รัศมี 2.5·√(2·พื้นที่ / เป้า)) แล้วเก็บรอบที่ flipped + folds น้อยที่สุด
5. repair แต่ละรอบ (สูงสุด 4 pass): ครั้งแรกทิ้ง speck (ขนาด < max(4·voxel, 15 mm) หรือ shell ที่ปริมาตรติดลบ เช่นโพรงภายใน), tidy (dissolve degenerate, triangulate, ลบ vertex ลอย), หาหน้าที่พลิก (normal ไม่ตรงกับ SDF) และขอบที่พับ > 120°, ยุบกลุ่มเสียขนาดเล็ก (≤ max(4·voxel, 12 mm)) แล้ว relax ลงผิว, หมุนขอบที่พับ (ถอยกลับถ้าแย่ลง)
6. ถ้า `crisp_roles`: snap vertex บนเส้นแบ่งสีของ low ไปเส้นแบ่งสีเดียวกันของ high (ภายใน 0.6 เท่าของขอบสั้นสุดของ vertex นั้น, ถอยกลับถ้า normal ของหน้าหมุนเกิน ~53°) แล้วโหวตสีใหม่ให้หน้าที่คร่อมเส้น (4 จุดต่อหน้า) ไม่เพิ่ม tris

ผลอยู่ใน `metrics.folds`: `flipped`, `folds`, `merged_verts`, `relaxed_verts`, `speck_faces`, `attempts`, `role_line_snapped`, `role_faces_relabelled`, `stage` (ผลของขั้นกลาง)

## 2. ไฟล์ผลลัพธ์

```text
<out>/
  <id>.blend               mesh <id> + กล่อง <id>_col_N ใน <id>_collision (+ <id>_rig ถ้ามีแอนิเมชัน)
  _high/<id>_high.blend    object <id>_high ตำแหน่งตรงกับ low ใช้กับ validate_sculpt --high
  <set>_pal.png            palette ของชุด (ถ้ามีไฟล์ชื่อเดิมที่สีไม่ตรงจะเขียน <set>_pal_<sha8>.png แทน)
  <id>_atlas.png           เฉพาะโหมด atlas
  <id>_card.json           เฉพาะ target library
  <id>_sheet.png           forge_sculpt: 6 ช่อง (สี 3 มุม + clay 3 มุม)
  <id>_preview.png         forge_sculpt: ภาพ 3/4 แบบ studio ของ prop-forge
  report.json              forge_sculpt: ผลทุกชิ้น
```

high อยู่ในโฟลเดอร์ย่อย `_high` โดยตั้งใจ เพื่อไม่ให้ `validate_prop.py` และ `export_prop.py` แบบโฟลเดอร์หยิบไปด้วย หลัง export จะมี `<set>_pal.dds` เพิ่มข้าง palette

## 3. `SculptBuilder(...)`

```python
SculptBuilder(prop_id, budget=None, size_class="hero", lod_dist=None, colliders="auto", set_name="sculpt_set", style="sculpt_forge_v1", target="prop", archetype="sculpt", voxel=0.005, palette=None, default_role=None, reset_scene=None, iso=0.0, ao_distance=0.18, ao_strength=1.0, atlas=0, keep_high=True, high_tris=400000, smooth_roles=True, font=None, stage_ratio=3.0, detail_share=0.35, uv_spread=0.2, crisp_roles=True)
```

| พารามิเตอร์ | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `prop_id` | ต้องใส่ | ชื่อ mesh และไฟล์ target prop ต้องตรง `^[a-z0-9_]{3,60}$` |
| `budget` | ตาม `size_class` | tris สูงสุดรวม poly part |
| `size_class` | `"hero"` | `hero` 12,000 / 150 m, `medium` 6,000 / 120 m, `small` 3,000 / 80 m (budget / lod_dist) |
| `lod_dist` | ตาม `size_class` | ระยะ LOD ใน meta, export ใช้เป็น `lodDist` และ `hdTextureDist` ของ ytyp |
| `colliders` | `"auto"` | `"auto"` = กล่องรอบ node ที่ `collide=True` (ขั้นต่ำ 0.12 m ต่อแกน) หรือกล่อง bbox ทั้งตัว, list ของ `{"center": [...], "size": [...]}` หรือ `(center, size)`, `0` หรือ `[]` = ไม่มีกล่อง |
| `set_name` | `"sculpt_set"` | ชื่อชุด ใช้ตั้ง `<set>_pal.png` และ meta `set` |
| `style` | `"sculpt_forge_v1"` | meta `style` |
| `target` | `"prop"` | `"prop"` หรือ `"library"` |
| `archetype` | `"sculpt"` | meta `archetype` (`mascot_marker` ไม่บังคับกล่องชนใน `validate_prop`) |
| `voxel` | 0.005 | ขนาด grid เป็นเมตร ใช้ 0.003-0.008 กับ prop ถึง ~2.5 m, ชิ้นใหญ่กว่าใช้ 0.008-0.01 |
| `palette` | None | `SetPalette`, `{role: "#hex"}`, `{role: {"color": "#hex", "finish": "satin"}}` หรือ `{"roles": {...}, "cell_px": 32}` |
| `default_role` | role แรกของ palette (ไม่มีเลยใช้ `"body"`) | role ของ node ที่ไม่ใส่ `role` |
| `reset_scene` | None = `bpy.app.background` | CLI ล้างฉากด้วย `read_factory_settings` ตอนสร้าง builder, GUI/MCP ไม่ล้าง |
| `iso` | 0.0 | isovalue ของ mesher ค่าบวกทำให้ทั้งชิ้นพองเท่ากัน |
| `ao_distance` | 0.18 | ระยะ probe AO (m) |
| `ao_strength` | 1.0 | คูณความเข้ม AO ใน `Color 1` |
| `atlas` | 0 | 0 = palette, 512 หรือ 1024 = smart UV + Cycles CPU bake สี role × AO พร้อม flood-fill |
| `keep_high` | True | เขียน `_high/<id>_high.blend` |
| `high_tris` | 400000 | high ที่ใหญ่กว่านี้ถูกย่อก่อนเขียนไฟล์ high |
| `smooth_roles` | True | เกลี่ยเส้นแบ่งสีของ high ให้เรียบบนผิว SDF |
| `font` | None | TTF ค่าเริ่มของ `text()` |
| `stage_ratio` | 3.0 | เป้าของการย่อขั้นกลาง = budget × ratio |
| `detail_share` | 0.35 | สัดส่วนผิวสูงสุดของ node `detail=True` ที่ยังกันความหนาแน่นให้ |
| `uv_spread` | 0.2 | ช่วง UV ภายในช่องสีของ palette (0.01-0.8) กัน UV คงที่ซึ่ง `verify_native_ydr` ตีตก |
| `crisp_roles` | True | snap เส้นสีของ low ไปเส้นสีของ high และโหวตสีใหม่ให้หน้าที่คร่อมเส้น |

## 4. kwargs ร่วมของทุก node

```python
role=None, fillet=0.0, op="union", mirror_x=False, bone=None, detail=False, collide=False
```

| kwarg | ความหมาย |
| --- | --- |
| `role` | ชื่อ role สี None = `default_role` role ที่ไม่อยู่ใน palette ถูกเพิ่มด้วยสีอัตโนมัติพร้อม warning |
| `fillet` | k ของ smooth-min (เมตร) ผสม node นี้กับทุกอย่างที่เพิ่มก่อนหน้าใน group เดียวกัน กับ `subtract`/`intersect` คือรัศมีมนของรอยตัด |
| `op` | `"union"`, `"subtract"` หรือ `"intersect"` |
| `mirror_x` | เพิ่มคู่สะท้อนแกน X (คู่ union กันแบบคม) แล้วรวมคู่นั้นเข้าที่ด้วย op และ fillet ของ node |
| `bone` | ชื่อกระดูกจาก `define_bone` หน้าที่เป็นของ node นี้ได้น้ำหนัก 1.0 ที่กระดูกนั้น |
| `detail` | กันความหนาแน่นตอนย่อ (`text` เป็น True โดยค่าเริ่ม) |
| `collide` | ให้ `colliders="auto"` สร้างกล่องรอบ node นี้ |

กฎ:

- พิกัดเป็นเมตร Z ขึ้น ด้านหน้า -Y พื้นที่ z = 0 (engine recentre ให้อีกครั้งตอนจบ) `rot` เป็นองศา Euler XYZ ทุก method คืน node
- union ใช้ smin(ผลสะสม, node, k) ลำดับจึงสำคัญ node ที่เพิ่มทีหลังผสมกับทุกอย่างก่อนหน้า
- `with b.group(name, fillet, op):` node ข้างในผสมกันด้วย fillet ของตัวเอง แล้วผลของทั้ง group ผสมเข้า parent ด้วย fillet และ op ของ group ใช้กำหนด k ต่างกันต่อรอยต่อ
- สีของจุดบนผิว = node ที่ใกล้ที่สุด node `subtract`/`intersect` ที่ไม่มี `role` ไม่ระบายสี ถ้าใส่ `role` ผิวรอยตัดจะเป็นสีนั้น (ร่องสี mint ของ kiosk ตัวอย่าง)
- `intersect` (รวม `cut`) ตัดทุกอย่างที่สะสมใน group เดียวกันนอกขอบเขตของมัน ใส่ `cut` ไว้ท้าย group ที่ต้องการตัดเท่านั้น

## 5. node ทั้งหมด

| method | ลายเซ็น | ความหมาย |
| --- | --- | --- |
| `sphere` | `sphere(radius, loc=(0,0,0), **common)` | ทรงกลม |
| `ellipsoid` | `ellipsoid(radii, loc, rot, **common)` | ทรงรี รัศมี x, y, z |
| `capsule` | `capsule(a, b, radius, **common)` | แคปซูลจากจุดโลก a ถึง b (ไม่มี loc/rot) |
| `round_cone` | `round_cone(a, b, radius_a, radius_b, **common)` | กรวยปลายมน จุดโลก a, b |
| `round_box` | `round_box(size, radius=0.0, loc, rot, **common)` | กล่องขอบมน `size` = ขนาดเต็ม, `radius` ถูกจำกัดไม่เกินครึ่งด้านสั้น |
| `pillow_box` | `pillow_box(size, radius=None, puff=0.03, loc, rot, **common)` | กล่องหน้าโป่ง `radius` ค่าเริ่ม 0.1 × ด้านสั้น, `puff` สเกลาร์หรือ (px, py, pz) โป่งกลางหน้าแบบ (1 - t²)² |
| `round_cyl` | `round_cyl(radius, height, edge=None, loc, rot, **common)` | ทรงกระบอกแกน z ท้องถิ่น `edge` ค่าเริ่ม min(0.3·r, 0.25·h), `edge` = 0.5·h ได้ puck โค้งเต็ม |
| `torus` | `torus(major, minor, loc, rot, **common)` | ห่วงในระนาบ XY ท้องถิ่น |
| `lathe` | `lathe(profile, loc, rot, smooth=2, **common)` | หมุนรอบแกน z ท้องถิ่น `profile` = polygon ปิดของ (r, z) ถ้าจุดแรกและจุดท้าย r = 0 จะตัน `smooth` = รอบ Chaikin |
| `extrude2d` | `extrude2d(outline, depth, edge=0.0, puff=0.0, puff_width=None, holes=None, plane="XZ", back_puff=True, loc, rot, **common)` | ยืด outline 2D (list หรือ `Shapes` dict) มีรู `holes` ได้ `edge` = มนขอบ (≤ depth/2), `puff` = โดมหน้า (smoothstep กว้าง `puff_width` ค่าเริ่ม max(3·edge, 0.25 × ด้านสั้นของ outline)), `back_puff=False` โดมเฉพาะหน้า |
| `tube` | `tube(path, radius, closed=None, step=None, ends=0.0, **common)` | ท่อกลมตาม Catmull-Rom ผ่านจุด `path` (list เปิด หรือ `Shapes` dict ปิดโดยค่าเริ่ม) `radius` สเกลาร์, list ตามจุดควบคุม หรือฟังก์ชันของ t 0..1, `step` ค่าเริ่ม 0.6 × r เล็กสุด (4-15 mm), `ends` = ลูกกลมปลายท่อ × r |
| `beads` | `beads(path, radius, spacing=None, count=None, closed=None, jitter=0.0, seed=0, blend=0.0, **common)` | ลูกปัดทุก `spacing` (ค่าเริ่ม 2r) `blend` = smooth-min ระหว่างลูก |
| `drips` | `drips(path, count, length=(0.06, 0.16), radius=(0.025, 0.035), closed=None, seed=0, jitter=0.35, sink=0.01, **common)` | หยดห้อยลง -Z จากตำแหน่งสุ่มบนเส้น (คอ 0.62r ลูกปลาย 0.95r) `length`/`radius` เป็นช่วง (min, max), `sink` ยกยอดหยดขึ้น (ค่าลบจมลง) |
| `scallops` | `scallops(path, drop=0.08, thickness=0.03, per_m=8.0, count=None, overlap=1.12, outward=0.0, up=None, blend=None, closed=None, **common)` | ลอนครึ่งทรงรีห้อย -Z ตามเส้น `per_m` ลอนต่อเมตร (หรือ `count`), กว้างลอน = pitch × `overlap`, `up` = ความสูงยอดลอน (ค่าเริ่ม thickness/2), `blend` ค่าเริ่ม 0.35 × thickness ใช้เส้นแนวนอนทวนเข็มให้ `outward` ชี้ออก |
| `text` | `text(body, font=None, height=0.25, size=None, max_width=None, depth=0.04, puff=0.01, plane="XZ", spacing=1.0, resolution=5, loc, rot, role, fillet, op, mirror_x, bone, detail=True, collide)` | TTF → mesh ตัวอักษร → level set แล้วพองด้วย `puff` จัดกึ่งกลางที่ `loc`, `height` สเกลความสูงกล่องของทั้งคำ (ตัวพิมพ์ใหญ่ = cap height) เว้นแต่ใส่ `size` (ขนาดฟอนต์เป็นเมตร), `max_width` จำกัดความกว้าง, `depth` ความหนาก่อนพอง |
| `mesh_part` | `mesh_part(source, puff=0.0, **common)` | mesh ใดๆ เป็นชิ้น SDF ที่ fillet ได้ `source` = Object (ใช้ค่า evaluated และ world matrix) หรือ `{"blend": path, "object": name}` |
| `cut` | `cut(point=(0,0,0), normal=(0,0,-1), fillet=0.0, role=None, mirror_x=False)` | intersect กับครึ่งปริภูมิ ลบฝั่งที่ normal ชี้ไป ค่าเริ่มตัดทุกอย่างใต้ `point.z` ได้ฐานเรียบ |
| `group` | `with b.group(name="group", fillet=0.0, op="union"):` | ดูหัวข้อ 4 |
| `bevel_box` | `bevel_box(size, radius=0.02, segments=4, loc, rot, role=None, bone=None, collide=False)` | กล่อง polygon bevel จริง (นอก SDF) |
| `poly_part` | `poly_part(source, role=None, bone=None, collide=False, weighted=True)` | Mesh หรือ Object (ใช้ world matrix) เป็นชิ้น polygon |
| `collider` | `collider(center, size)` | กล่องชนเพิ่มเอง พิกัดเดียวกับ node ย้ายตาม recentre |
| `define_bone` | `define_bone(name, pivot, parent="root")` | ลงทะเบียนกระดูกก่อนให้ node อ้าง |
| `set_anim` | `set_anim(frames=121, fps=30, tracks=None, auto_start=True)` | แอนิเมชันวนของกระดูก |
| `build` | `build(out_dir)` | รันทั้ง pipeline คืน dict (หัวข้อ 8) |

`plane` ของ `extrude2d` และ `text`: `"XZ"` (u → X, v → Z, หน้า -Y ค่าเริ่ม เหมาะกับป้ายและงานนูน), `"XY"` (u → X, v → Y, หน้า +Z), `"YZ"` (u → -Y, v → Z, หน้า -X) แล้วหมุน `rot` ต่อ

## 6. `Shapes` (outline และ path)

ใช้เป็น `outline`/`holes` ของ `extrude2d` และ `path` ของ `tube`, `beads`, `drips`, `scallops` ใน JSON เขียนเป็น dict:

```json
{"shape": "rounded_rect", "w": 1.2, "h": 0.54, "r": 0.11, "plane": "XZ", "at": [0.0, -0.064, 1.32], "smooth": 0, "offset": 0.0, "closed": true}
```

| shape | อาร์กิวเมนต์ |
| --- | --- |
| `rounded_rect` | `w, h, r, corner_segments=None` |
| `scalloped_rect` | `w, h, r, lobes_per_m=8.0, amp=0.03, lobes=None, samples=12` |
| `circle` | `r, segments=None` (ค่าเริ่มจาก sagitta 2 mm) |
| `lobed_circle` | `r, lobes=8, amp=0.03, samples=12` |
| `star` | `r_out, r_in, points=5, smooth=3, rotation=90.0` |
| `heart` | `size, smooth=1, samples=96` |
| `squircle` | `w, h, exponent=4.0, top_lobes=0, amp=0.0, samples=128` (`amp` เป็นสัดส่วน โป่งเฉพาะด้านบน) |
| `points` | `"points": [[u, v], ...]` |

- key ร่วม: `smooth` = Chaikin เพิ่มหลังสร้างรูป, `offset` = ขยายออกเป็นเมตร (หดเข้าเมื่อลบ), `plane`/`at` = วาง path ในโลก, `closed`
- `smooth` ใน dict เป็นรอบเพิ่มจาก `smooth` ของตัว generator เอง (`star` 3, `heart` 1) ซึ่งตั้งจาก JSON ไม่ได้ เช่น `{"shape": "star", "smooth": 3}` ได้ Chaikin รวม 6 รอบ
- path จาก dict ปิดโดยค่าเริ่ม path ที่เป็น list เปิดเว้นแต่ `closed=True` จุด 2 มิติใน list ถูกวางบน XY
- path ใน plane `"YZ"` วาง u → +Y ซึ่งกลับด้านกับ `extrude2d` plane `"YZ"` (u → -Y) รูปที่ไม่สมมาตรซ้ายขวาจะกลับด้าน
- `Shapes.segments_for_radius(radius, sagitta=0.002, minimum=8)` คืนจำนวนด้านทวีคูณ 4 ตามกฎ sagitta

## 7. ชิ้น polygon, กล่องชน, กระดูก, แอนิเมชัน

- `bevel_box` / `poly_part` ไม่อยู่ใน SDF จึงไม่ fillet เข้าชิ้นอื่น ไม่บังแสงใน AO ของ SDF และไม่ถูกนับใน metric ของ field tris ของมันถูกกันออกจากงบก่อนย่อ เป็น shell แยก (`validate_sculpt` อาจเตือน `shells`/`interpenetration`) ใช้กับแผงแบนคมที่ต้องการ Weighted Normal โหมด atlas อบสี role ของมันให้ด้วย
- กล่องชน: ตั้ง `colliders` ที่ builder หรือเรียก `collider(center, size)` ตู้หรือป้ายที่ผู้เล่นเดินชนต้องมีกล่องรอบตัวหลัก target library ไม่มีกล่อง
- กระดูก: `define_bone(name, pivot, parent)` ก่อนแล้วใส่ `bone=name` ให้ node กระดูกยาว 0.05 m ตาม +Y น้ำหนักแบบแข็งต่อ vertex (vertex ที่หน้าหลายกระดูกใช้ร่วมไปอยู่กับกระดูก index สูงกว่า) จึงควรแยก node ที่ขยับออกจาก node นิ่ง ไม่ fillet ติดกัน
- `set_anim(tracks={bone: {...}})` key ของ track: `kind`, `cycles`, `amp_z`, `spin_deg`, `tilt_x`, `rock_y`, `twist_z`

| `kind` | ค่าเริ่ม |
| --- | --- |
| `bob_rock` (ค่าเริ่ม) | 2 รอบ, ลอยขึ้นลง `amp_z` 0.03 m, โยก `rock_y` 4° |
| `spin_z` | 1 รอบ, หมุน 360°, ไม่ลอย ไม่โยก |
| `marker_spin` | 1 รอบ, หมุน 360°, ลอย 0.03 m |
| `sign_sway`, `crown_hover` | 1 รอบ, ลอย 0.03 m, โยก 4° |

meta `prop_forge["anim"]` มี `rig_name`, `action_name`, `fps`, `frames`, `duration`, `bones`, `auto_start` ซึ่ง `validate_prop.py` และ `export_prop.py` อ่านต่อ (export เป็น `.ycd`)

## 8. ผลของ `build()` และ metadata

`build()` คืน key ของ meta (`id`, `archetype`, `set`, `style`, `low_poly`, `size_m`, `tris`, `budget`, `parts`, `materials`, `shaders`, `texture`, `colliders`, `lod_dist`, `warnings`, `anim`) และ `blend`, `high_blend`, `metrics`, `timings`, `target`, `card` (เฉพาะ library) แล้วพิมพ์ `SCULPT_PROP {...}`

| metric | ความหมาย |
| --- | --- |
| `tris`, `verts`, `all_triangles`, `has_custom_normals` | สถานะ mesh |
| `surface_m2`, `tris_per_m2` | พื้นที่ผิวและความหนาแน่น |
| `shells`, `degenerate_tris`, `flipped_faces`, `inverted_faces` | topology |
| `dihedral_deg` | `p50`, `p90`, `max`, `over30`, `over45`, `folds_over120` ของทุกขอบ |
| `normal_error_deg` | เทียบ gradient ของ SDF (finite difference) จึงพองที่ร่องลึก ใช้ `normal_error` ของ `validate_sculpt.py` ตัดสินแทน |
| `surface_dev_mm` | ระยะ vertex ถึงผิว SDF |
| `high_tris`, `boundary_vertices_smoothed`, `folds`, `color1` | ขนาด high, จำนวน vertex ที่เกลี่ยเส้นสี, ผล repair, ค่า `Color 1` (`min`, `mean` ของช่อง R) |

metadata บน object:

- `root["prop_forge"]` (เฉพาะ target prop) = สัญญา prop: `id`, `archetype`, `set`, `style` = `sculpt_forge_v1`, `low_poly` False, `size_m`, `tris`, `budget`, `parts`, `materials`, `shaders`, `texture`, `colliders`, `lod_dist`, `warnings`, `anim`
- `root["sculpt_forge"]` (ทุก target) = `version`, `target`, `size_class`, `voxel`, `band`, `iso`, `atlas`, `ao_distance`, `palette`, `finishes`, `nodes` (role, bone, detail, collide, kind), `shift`, `metrics`, `timings`, `log`, `uv_spread`, `blender`, `high_blend` (`_high/<id>_high.blend`), `high_object`, `normals` = `transfer`, `weighted_parts`

## 9. สเปก JSON (`forge_sculpt.py`)

| key ระดับบน | ความหมาย |
| --- | --- |
| `set` | ชื่อชุด (ชื่อ palette และ meta `set`) |
| `about` | ข้อความอธิบาย (ไม่ถูกอ่าน) |
| `voxel` | voxel ค่าเริ่มของทุกชิ้น ใช้เมื่อไม่มีที่อื่นกำหนด |
| `defaults` | kwargs ของ builder ที่ใช้กับทุกชิ้น |
| `palette` | `{"cell_px": 32, "roles": {"frost": {"color": "#FFF2E4", "finish": "satin"}, ...}}` |
| `props` | รายการชิ้น |

key ของแต่ละชิ้น: `id` (ต้องมี), kwargs ของ builder (`budget`, `size_class`, `lod_dist`, `colliders`, `style`, `target`, `archetype`, `voxel`, `default_role`, `iso`, `ao_distance`, `ao_strength`, `atlas`, `keep_high`, `high_tris`, `smooth_roles`, `font`, `stage_ratio`, `detail_share`, `uv_spread`, `crisp_roles`), `bones` (`[{"name", "pivot", "parent"}]`), `anim` (kwargs ของ `set_anim`), `nodes`

node คือ `{"type": "<ชื่อ method>", ...kwargs}` ชนิดที่ใช้ได้: `sphere`, `ellipsoid`, `capsule`, `round_cone`, `round_box`, `pillow_box`, `round_cyl`, `torus`, `lathe`, `extrude2d`, `tube`, `beads`, `drips`, `scallops`, `text`, `mesh_part`, `cut`, `bevel_box` และ group `{"type": "group", "name": "roof", "fillet": 0.03, "op": "union", "nodes": [...]}` key `name` และ `note` ของ node ถูกข้าม (ใช้จดบันทึกได้) tuple เขียนเป็น list ส่วน `poly_part`, ฟังก์ชันรัศมี และ Object ใช้ได้เฉพาะ Python

ลำดับความสำคัญ: `defaults` < ค่าของชิ้น < ตัวเลือก CLI (ค่า None ถูกข้าม) palette ของชุดสร้างครั้งเดียวก่อน build โดยรวมทุก role ที่ node ใช้ ทุกชิ้นจึงใช้ PNG แผ่นเดียวกัน

| ตัวเลือก CLI | ความหมาย |
| --- | --- |
| `--spec <json>` `--out <dir>` | ต้องใส่ |
| `--only id1,id2` | build เฉพาะชิ้น |
| `--voxel`, `--budget`, `--atlas`, `--target` | ทับค่าของทุกชิ้น |
| `--no-render` | ไม่ทำ `<id>_sheet.png` และ `<id>_preview.png` |
| `--no-validate` | ไม่รัน `validate_scene` ของ prop-forge ในตัว |
| `--tile 640`, `--samples 24` | ขนาดช่องและ sample ของ sheet |

บรรทัดผล: `SCULPT_PROP {...}` ต่อชิ้นจาก `build()`, `SCULPT_DONE {"id", "tris", "budget", "seconds", "error", "validate": {"fail", "warn"}}`, `SCULPT_FAIL <id> <error>` เมื่อพัง และ `RESULT props=N fail=N report=<path>` ท้ายสุด exit code 1 เมื่อมีชิ้นพังหรือ validate fail `validate` ในบรรทัดนี้คือสัญญา prop ของ `validate_prop.py` เท่านั้น ประตูความเนียนคือ `validate_sculpt.py` ที่รันแยก `report.json` เก็บ `spec`, `out`, `set`, `blender`, `palette` และ `props` (ผล `build()` ทั้งหมด + `validate.lines`, `sheet`, `preview`, `seconds` หรือ `error`/`trace`)

`forge_sculpt.py` หา `sculpt_forge.py` และ prop-forge จาก `__file__` จึงใช้ได้เฉพาะ CLI ผ่าน MCP ให้เรียก `SpecRunner.run(spec, out_dir, only=None, overrides=None)` แทน (ไม่มี validate และ render ในตัว)

## 10. เขียน builder ด้วย Python (CLI)

ตัวอย่างนี้รันจริงแล้ว: 5,880 / 6,000 tris, build 3.6 วินาที, `SCULPT_QA fail=0 warn=2`

```python
import importlib
import os
import sys


class CafeSign:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def library(self):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module("sculpt_forge")

    def build(self):
        sf = self.library()
        palette = {"caramel": "#C48E62", "cream": "#FFFBF4", "ink": {"color": "#3B281E", "finish": "matte"}, "honey": {"color": "#E8B04B", "finish": "gloss"}}
        b = sf.SculptBuilder("1nfx_cafe_sign", size_class="medium", set_name="1nfx_cafe", palette=palette)
        with b.group("plate", fillet=0.02):
            b.pillow_box((1.0, 0.14, 0.56), radius=0.05, puff=(0.0, 0.015, 0.0), loc=(0.0, 0.0, 0.28), role="caramel", collide=True)
            b.tube({"shape": "rounded_rect", "w": 0.86, "h": 0.42, "r": 0.1, "plane": "XZ", "at": (0.0, -0.063, 0.28)}, radius=0.02, role="honey", fillet=0.012)
        b.text("CAFE", height=0.22, max_width=0.66, depth=0.016, puff=0.018, plane="XZ", loc=(0.0, -0.075, 0.28), role="ink", fillet=0.006)
        b.text("CAFE", height=0.22, max_width=0.66, depth=0.03, puff=0.008, plane="XZ", loc=(0.0, -0.098, 0.28), role="cream", fillet=0.005)
        b.cut(point=(0.0, 0.0, 0.02))
        return b.build(self.out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = CafeSign(argv[0], argv[1]).build()
    print("CAFE_SIGN tris={} blend={}".format(result["tris"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -P '<project>\work\cafe\cafe_sign.py' -- '<skill>' '<project>\work\cafe\build'
```

ตัวเลขในตัวอย่างตามกฎใน `references/smooth-craft.md`: ขอบแผ่น 0.05 บนหนา 0.14 (36%), piping r 0.02 ฝัง 7 mm (0.35r), outline ยื่นจากแผ่น 1.6 cm และตัวอักษรยื่นจาก outline 2 cm, ขอบ outline 1 cm (≈ 5% ของตัวสูง 0.22 m)

## 11. ผ่าน Blender MCP

```python
import runpy

ns = {"__name__": "__main__"}
with open(r"<skill>\sculpt-forge\scripts\blender\sculpt_forge.py", encoding="utf-8") as handle:
    exec(compile(handle.read(), "sculpt_forge", "exec"), ns)
b = ns["SculptBuilder"]("1nfx_cafe_badge", size_class="small", font=r"<skill>\prop-forge\assets\fonts\TitanOne-Regular.ttf", palette={"caramel": "#C48E62", "honey": {"color": "#E8B04B", "finish": "gloss"}})
b.pillow_box((0.5, 0.12, 0.32), radius=0.04, puff=(0.0, 0.012, 0.0), loc=(0.0, 0.0, 0.2), role="caramel", collide=True)
result = b.build(r"<project>\work\cafe\mcp")
qa = runpy.run_path(r"<skill>\sculpt-forge\scripts\blender\validate_sculpt.py", run_name="mcp")
qa["SculptValidator"](qa["CommandLine"].parse([])).run()
rs = runpy.run_path(r"<skill>\sculpt-forge\scripts\blender\render_sculpt.py", run_name="mcp")
rs["SculptRenderer"](rs["RenderOptions"].parse(["--out", r"<project>\work\cafe\mcp\renders"])).run()
```

- exec ด้วย `__name__ == "__main__"` ปลอดภัย `main()` ทำงานเฉพาะเมื่อมี `--selftest`
- ใน UI `reset_scene` เป็น False ฉากไม่ถูกล้าง object ของผู้ใช้ยังอยู่ ไฟล์ `<id>.blend` เขียนด้วย `libraries.write` เฉพาะ root, rig และกล่องชน
- `parse([])` ตรวจและ render ฉากที่เปิดอยู่ (หา mesh ที่มี `prop_forge` meta) ฉากที่มี mesh อื่นของผู้ใช้จะขึ้น WARN `extra meshes` และไม่มี high ให้เทียบ ผลจริงให้รัน CLI แบบ headless กับไฟล์ที่บันทึกพร้อม `--high result["high_blend"]`
- ใน UI ห้ามส่ง `--blend` ไฟล์อื่น เครื่องมือจะเปิดไฟล์นั้นทับฉากปัจจุบัน หรือปฏิเสธถ้าฉากยังไม่ save
- ไม่มี `__file__` จึงต้องส่ง `font=` (หรือ env `SCULPT_FORGE_FONT`) ให้ `text()` ถ้าเรียก validator ด้วย `exec` แทน `runpy.run_path` ต้องส่ง `--prop-validator <skill>\prop-forge\scripts\blender\validate_prop.py`
- Blender 5.x ใช้ได้ (core ทดสอบบน 5.3.0) แต่ไฟล์ที่ได้เปิดใน 4.2.3 ไม่ได้ engine ใส่ warning `saved by Blender ...` ใน meta ต้อง build ซ้ำด้วย CLI 4.2.3 ก่อน export
- เส้นทางนี้ทดสอบแบบ headless แล้ว (exec + `reset_scene=False` + runpy validate/render ฉากสด) ได้ 2,934 tris, ฉากสด fail=0 warn=4 (รวม WARN `extra meshes: Cube` ของฉากเริ่มต้น) และไฟล์ที่บันทึกตรวจ headless ได้ fail=0

## 12. target library (ชิ้นเนียนใน KawaiiBuilder)

```powershell
& $blender -b --factory-startup -P "$sf\forge_sculpt.py" -- --spec $spec --out $lib --only 1nfx_puff_trophy --target library --budget 4000 --voxel 0.006 --no-render
```

ได้ `<id>.blend` ที่มี custom normals, `UVMap`, `Color 1` แต่ไม่มี `prop_forge` meta และกล่องชน (ตัวอย่างนี้ 3,914 tris, 4 วินาที) กับ `<id>_card.json`:

```json
{"kind": "sculpt_mesh", "blend_path": "<abs>\\<id>.blend", "mesh_name": "<id>", "image": "<abs>\\<set>_pal.png", "uv_rect": [0.0, 0.0, 1.0, 1.0], "scale": 1.0, "est_tris": 3914, "emissive": false, "transparent": false}
```

ใช้ใน `KawaiiBuilder`: โหลด JSON, ตั้ง `card["matrix"]` เป็น `mathutils.Matrix` (สเกลเท่ากันทุกแกนเท่านั้น), ตั้ง `card["bone"] = kb.current_bone` ถ้ามีแอนิเมชัน แล้ว `kb.pending_cards.append(card)` KawaiiBuilder join card หลังขั้น cleanup ของมัน custom normals จึงรอด (วัด 0.033°) UV ถูกแมปเข้า rect ของภาพ card (palette, `uv_rect` [0, 0, 1, 1]) และ card ได้ material ของ kawaii ไม่ใช่ finish ของ sculpt-forge

## 13. export ผ่าน prop-forge

1. `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์ (`TOTAL files=N fail=0`)
2. `export_prop.py --blend <ไฟล์หรือโฟลเดอร์> --out <stream> --format native --max-res 512 [--shared-ytd <set>_tex]` รันโดยไม่ใส่ `--factory-startup` (ต้องโหลด Sollumz 2.9.1 + PyMateria) โฟลเดอร์จะ export ทีละไฟล์ใน subprocess แยก
3. ผลที่วัด: kiosk ไฟล์เดียวได้ `EXPORT {"ok": true, ..., "ydr_check": {"geometries": 1, "embedded_textures": 1}}` (`.ydr` 246 KB + `.ytyp`), ทั้งชุดแบบ shared ได้ `RESULT ok=3 fail=0` + `1nfx_puff_tex.ytd` (palette 128 × 128 DXT1 7 mip, VRAM 10 KB) round trip ด้วย PyMateria: NORMAL ใน `.ydr` ตรงกับ custom normals ใน Blender เฉลี่ย 0.0072° สูงสุด 0.034°
4. เชื่อมเข้าเซิร์ฟเวอร์ตาม `prop-forge/references/integration.md` (stream, `DLC_ITYP_REQUEST`, โค้ด spawn) PyMateria มีสัญญาอนุญาตกับ Take-Two ห้ามติดตั้งแทนผู้ใช้

## 14. ความเร็ว

| งาน | ผลที่วัด (Blender 4.2.3, Ryzen 9 9950X3D) |
| --- | --- |
| ประเมิน SDF กล่องทดสอบ 5 ชิ้น | 8 mm: 1.69 M voxel 0.25 s ได้ 93k tris; 5 mm: 6.82 M voxel 1.15 s ได้ 239k; 4 mm: 13.3 M voxel 2.77 s ได้ 373k; วัตถุ 3 m ที่ 1 cm: 27 M voxel 4.38 s |
| mesher OpenVDB | 0.01-0.05 s |
| COLLAPSE 239k → 3k | ~1 s, ผิวคลาดเฉลี่ย 0.28 mm |
| โอน normals | 0.03-0.13 s |
| kiosk ตัวอย่าง 1.55 × 1.07 × 2.40 m ที่ 5 mm | evaluate 3.5 s, high 1.15 M หน้า, reduce 13.1 s, รวม 24.7 s (ที่ 4 mm รวม 42 s) |
| sign 1.42 × 0.24 × 1.73 m ที่ 5 mm | evaluate 0.45 s, high 333k, reduce 11.7 s, รวม 15.5 s |
| trophy 0.90 × 0.56 × 0.87 m ที่ 4 mm | evaluate 0.48 s, high 361k, reduce 2.7 s, รวม 5.5 s |
| atlas 512 | เพิ่ม ~0.9 s |
| ชุดตัวอย่าง 3 ชิ้นพร้อม sheet + preview | 46 s |
| `validate_sculpt.py` / `render_sculpt.py` | ไม่กี่วินาทีต่อไฟล์ (render 0.5-0.9 s ต่อชิ้น) |

grid หนาแน่นใช้ได้ถึงราว 3 m ที่ voxel 1 cm ชิ้นใหญ่กว่านั้นใช้ `SweepBuilder` (`references/map-pieces.md`) ห้ามแก้ความช้าด้วย mesher adaptivity (fold ถึง 180°, ผิวคลาด 1-2.7 mm)

## 15. แก้ปัญหา

| อาการ | สาเหตุ | แก้ |
| --- | --- | --- |
| `this Blender build has no OpenVDB python module` | Blender ไม่มี pyopenvdb | ใช้ Blender 4.2.3 LTS ทางการ (มี pyopenvdb 11) |
| `has no SDF nodes` / `has no bounded union nodes` | ไม่มี node union เลย | เพิ่ม union อย่างน้อยหนึ่งตัว |
| `meshed to an empty surface` | subtract/cut กินหมด หรือ node ผิดตำแหน่ง | ตรวจ `loc`, `size`, ทิศ `normal` ของ `cut` |
| `text ... produced no geometry` หรือได้ฟอนต์ผิด | ไม่พบ TTF (MCP ไม่มี `__file__`) | ส่ง `font=` หรือตั้ง env `SCULPT_FORGE_FONT` |
| `bone X is not defined` | อ้างกระดูกก่อน `define_bone` | define ก่อนเพิ่ม node |
| `unknown outline shape` / `unknown node type` | ชื่อผิด | ใช้ชื่อในหัวข้อ 5-6 |
| warning `role X was not in the palette` | role ไม่อยู่ใน palette | เพิ่ม role และสีใน `palette` ของสเปก |
| warning `detail nodes cover N% ...` | node `detail` กินผิวเกิน `detail_share` | ใส่ `detail` เฉพาะชิ้นเล็ก หรือเพิ่ม `detail_share` |
| warning `tris N over budget` | poly part กินงบ | ลด segment ของ `bevel_box` หรือเพิ่ม `budget` |
| `folds` FAIL ที่รอยต่อแคบ (คอหยด ร่องลอน) | collapse ทิ้งขอบพับในร่องลึก | เพิ่ม `fillet` ที่รอยต่อนั้นเป็น 1.2-1.6 เท่าของ r (kiosk 0.015 → 0.035: 39 → 0 folds) เพิ่มงบหรือ `stage_ratio` ไม่ช่วย (16,000 tris: 48 folds, `stage_ratio` 6: 45) voxel 4 mm ช่วยนิดเดียว (36) |
| `lumpiness` FAIL บนแผ่นโดมหรือขอบหยัก | แผ่นโดมเตี้ยกว้างเหลือสามเหลี่ยมใหญ่ หรือ metric อ่านลอนที่ออกแบบไว้เป็นก้อน | เปิด zebra: แถบที่วิ่งเป็นระเบียบตามลอนคือดีไซน์ แถบหักกระจายบนแผ่นเรียบคือก้อนจริง เพิ่มงบไม่ช่วย (sign 14,000 tris ยัง FAIL) |
| รอยทแยงกากบาทบนแผงแบน (clay/zebra) | แผงใหญ่เหลือสามเหลี่ยมไม่กี่ชิ้น normals ที่โอนมาเอียงที่มุม | `flat_panels` เป็น INFO รับได้ ถ้าต้องการแผงคมใช้ `bevel_box`/`poly_part` หรือให้แผงพองเล็กน้อยจนเงาดูตั้งใจ |
| เส้นแบ่งสีเป็นฟันเลื่อย | voxel หยาบเทียบกับเส้นสี | คง `smooth_roles`, `crisp_roles` ไว้, ขยายชิ้น หรือลด `voxel` |
| ตัวอักษรเล็กแตกเป็นก้อน | เส้นตัวอักษร < 6-8 voxel หรืองบน้อย | ตัวอักษร ≥ ~0.15 m ที่ 5 mm หรือ `voxel` 0.003-0.004, ใส่ `max_width`, ให้งบตัวอักษร (ป้ายตัวอักษรสูง 0.12 m ที่ 3,000 tris FAIL, ป้ายตัวสูง 0.22 m ที่ 6,000 ผ่าน) |
| ชิ้นเล็กหรือโพรงหาย | shell ที่เล็กกว่า max(4·voxel, 15 mm) และโพรงภายในถูกทิ้งตอน repair | ขยายชิ้นหรือให้ต่อกับตัวหลัก ลด `voxel` |
| สามเหลี่ยมกลับด้านจุดเล็กๆ ที่ร่องเว้า | เหลือหลัง repair (kiosk 8, sign 3, หน้าละไม่กี่ mm²) | backface culling ของเกมอาจเห็นเป็นรูเข็มระยะใกล้ เพิ่ม fillet ที่ร่องนั้น |
| `validate_sculpt` ข้าม `normal_error`/`deviation` | high อยู่ใน `_high/` ไม่ใช่ข้างไฟล์ | ส่ง `--high <out>\_high\<id>_high.blend` ทีละไฟล์ |
| `Warning: Library file, loading empty scene` | ไฟล์ที่เขียนด้วย `libraries.write` (ทาง MCP, `_high`, shell แมพ) ไม่มีข้อมูล UI | ไม่มีผล object โหลดครบ |
| build ช้าหรือแรมเต็ม | grid ใหญ่ | `voxel` 0.008-0.01 สำหรับชิ้น > 2.5 m, ชิ้น > 3 m ใช้ `SweepBuilder` |
| `export_prop.py` เปิดไฟล์ไม่ได้ | บันทึกจาก 5.x | build ซ้ำด้วย CLI 4.2.3 |
| `Sollumz extension is not enabled in this Blender (run without --factory-startup)` | รัน export ด้วย `--factory-startup` | ตัด `--factory-startup` ออกจากคำสั่ง export |
| `native export needs Sollumz's optional PyMateria dependency` หรือ `szio is missing` | ยังไม่ได้ติดตั้ง dependency ของ Sollumz | ให้ผู้ใช้ติดตั้งเองใน Sollumz > Preferences (PyMateria มีสัญญากับ Take-Two ห้ามติดตั้งแทน) |

ข้อจำกัดที่รู้: prop มี LOD เดียว (`lod_dist` ใน meta) ไม่มี LOD chain, ชิ้น polygon ไม่ fillet และไม่อยู่ใน AO ของ SDF, น้ำหนักกระดูกแข็งต่อ vertex, ไม่มี target แมพใน `SculptBuilder` (ชิ้นแมพใช้ `SweepBuilder`)
