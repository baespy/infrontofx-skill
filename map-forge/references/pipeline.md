# Map Forge Pipeline (Blender 4.2.3 + Sollumz 2.9 + PyMateria GEN8)

คู่มือเทคนิคตั้งแต่โครงสร้าง `.blend` จนถึงแพ็กเกจ FiveM `stream/` และเช็กลิสต์ตรวจสอบทุกจุดที่มักพังในเกมจริง

## 1. สัญญาของไฟล์ `.blend` ต่อชิ้น (`.ydr` Contract)

1. **ชื่อไฟล์ = ชื่อ mesh หลัก:** `<id>.blend` ต้องมี mesh ชื่อ `<id>` (`[a-z0-9_]`, ตัวพิมพ์เล็กเท่านั้น) ที่ apply Transform แล้ว (`location=(0,0,0)`, `rotation=(0,0,0)`, `scale=(1,1,1)`)
2. **Origin ที่ระดับพื้นวางจริง (`z = 0`):** จุดที่ต้องแตะพื้นทางเดินอยู่ `z = 0.0` (สำหรับลานหลัก sky island ระดับพื้นเดินหลักอยู่ที่ `z = 0.0` ส่วนโครงฐาน/คานใต้เกาะยื่นลงด้านล่าง `z < 0` ได้ตามจริง เพื่อให้คำนวณพิกัดวาง prop และจุดวาร์ปง่ายและแม่นยำ 100%)
3. **Attributes บังคับของ RAGE:**
   - UV Layer ชื่อ **`"UVMap 0"`** (World-Scale Tiled UV, 1 UV unit = 1.5–3.0m)
   - Vertex Color Layer ชื่อ **`"Color 1"`** (`BYTE_COLOR`, `CORNER`) — ตั้งตามกฎ `#FF00FF` + Cycles AO ใน `shaders-lighting-vcol.md` (ห้ามปล่อยว่าง ไม่งั้นสีเพี้ยนหรือมืดสนิทตอนกลางวัน)
4. **Custom Properties บน Material (ให้ `export_map.py` อ่านอัตโนมัติ):**
   - `map_forge_shader` (หรือ `prop_forge_shader`): ชื่อ `.sps` เช่น `"normal_spec.sps"`, `"default.sps"`, `"emissive.sps"`, `"emissivenight.sps"`, `"glass_env.sps"`, `"cutout.sps"`, `"water_fountain.sps"`
   - `map_forge_bumpiness` (ค่าเริ่ม `1.0`)
   - `map_forge_spec_int` (ค่าเริ่ม `0.25`)
   - `map_forge_spec_falloff` (ค่าเริ่ม `40.0`)
   - `map_forge_spec_fresnel` (ค่าเริ่ม `0.85`)
   - `map_forge_emissive_mult` (ค่าเริ่ม `2.0`)
   - Node ภาพใน Shader Tree ตั้งชื่อ node เป็น `"DiffuseSampler"`, `"BumpSampler"`, `"SpecSampler"` (หรือ `"DetailSampler"`) เพื่อให้ converter ผูกตรงกับ Sollumz shader node อัตโนมัติ
5. **Custom Properties บน Object หลัก (`root["map_forge"]` หรือ `root["prop_forge"]` JSON string):**
   - `"collision_material"`: เช่น `"CONCRETE"`, `"WOOD_SOLID_MEDIUM"`, `"METAL_SOLID_MEDIUM"`, `"STONE"`, `"GRASS"`, `"GLASS_SHOOT_THROUGH"`
   - `"lights"`: (ตัวเลือก) ลิสต์ไฟที่จะฝังลง `Drawable.lights` โดยตรง (ดูรูปแบบใน `templates/map-spec.example.json`)
6. **กล่องชนแยก (`<id>_col_0`, `<id>_col_1`, ...):**
   - mesh สะอาดไม่มี non-manifold หรือสามเหลี่ยมพื้นที่ศูนย์, normals ชี้ออกนอก (`recalc_face_normals`)
   - พื้นเดินและบันไดต้องตรงระดับพื้นจริง (ความต่าง `< 0.02m` ที่จุดวาร์ปและทางเดิน)
   - ชิ้นตกแต่งขนาดเล็กหรือรั้วเตี้ยไม่จำเป็นต้องใช้ mesh ละเอียด ให้ใช้กล่องครอบสะอาด (box/slab colliders)

## 2. Shared `.ytd` & PCA DXT1/DXT5 Compression

- **รวมทุก texture ลง `.ytd` เดียว** (เช่น `<map>_tex.ytd`) และตั้ง `node.texture_properties.embedded = False` ในทุก `.ydr`
- **ตั้งค่า `hdTextureDist = lodDist` ใน `.ytyp`:** ป้องกันเกมลด mipmap เหลือภาพเบลอ ("วุ้น") เมื่อผู้เล่นยืนห่างออกไป 20–40 เมตร
- **DXT1 vs DXT5:**
  - พื้นผิวทึบทั้งหมด (`Diffuse`, `Normal`, `Spec`) เข้ารหัสเป็น **DXT1 (BC1, 4 bpp)** — กิน VRAM ครึ่งหนึ่งของ DXT5 และคมมากเมื่อใช้ PCA endpoint fitting (`dds_codec.py`)
  - ใช้ **DXT5 (BC3, 8 bpp)** เฉพาะแผ่นที่มีความโปร่งใสจริง (`decal`, `cutout`, `glass_env`, `emissive_alpha`) พร้อม RGB bleed 8 รอบเพื่อกันขอบดำรอบตัวอักษร
- **DirectX Normal Flip:** ไฟล์ที่ชื่อลงท้าย `_n.png` จะถูกกลับช่องสีเขียว (`G = 1.0 - G`) ก่อนเข้ารหัส `.dds` ทุกครั้ง

## 3. Dual Collision System (กันผู้เล่นวาร์ปตกฟ้า 100%)

Sky Map หรือ Custom Island ที่ลอยสูงกลางอากาศ (`z = 200..800m`) มักเจอปัญหา **วาร์ปมาถึงก่อนที่ prop entity จะสตรีม collision เสร็จแล้วร่วงตกพื้น** วิธีแก้ระดับโปรดักชันคือทำ **Dual Collision**:

1. **Embedded Collision ใน `.ydr`:** ฝัง `BoundComposite -> BoundGeometryBVH` ไว้ในทุก `.ydr`
2. **Static World Collision (`.ybn`):** รวมกล่องชนของโครงสร้างเดินได้ทั้งหมด (ในพิกัดโลกจริง `origin + item["pos"]` หมุนตาม `yaw_deg`) แยกตามวัสดุชน (`CONCRETE`, `WOOD`, `STONE`, `GRASS`) แล้ว export เป็น `<map>_col.ybn` เพียงไฟล์เดียว
3. **ผูก `.ybn` ใน `.ymap`:**
   - `md.content_flags = 1 | 64` (= `65`, คือ `HAS_ENTITIES_HD | HAS_PHYSICS`)
   - `md.physics_dictionaries = [CombinedHashString(ybn_name)]`
   - ตรวจ `CollisionFlags` ของทุก child bound ให้ครบ: `MAP_TYPE_MOVER | MAP_TYPE_WEAPON | MAP_TYPE_COVER | MAP_TYPE_VEHICLE`

## 4. กฎ YMAP, Quaternion กลับด้าน และ Extents

- **CRITICAL — GTA V YMAP Quaternion Convention:** GTA V เก็บ quaternion ของ entity ใน `.ymap` แบบ **Inverted (`q.inverted()`)** เมื่อเทียบกับ Blender `Euler -> Quaternion`!
  - เขียนลง `.ymap`: `q_gtav = Euler((rx, ry, rz), "XYZ").to_quaternion().inverted()`
  - อ่านกลับเพื่อตรวจ: `q_raw = Quaternion((e.rotation.w, e.rotation.x, e.rotation.y, e.rotation.z))` แล้ว `q_raw.inverted().to_euler("XYZ")`
  - หากลืม `.inverted()` ทุกชิ้นที่หมุนไม่สมมาตร (เช่น ศาลา ป้าย ม้านั่ง) จะหันกลับด้านซ้าย-ขวาหมด!
- **Entity Flags มาตรฐาน (CRITICAL — กันแคช `Error GTA5_b3889.exe+93C0B2 — Pool Full, Size == 256`!):**
  - ใช้ **`flags = 32`** (`FLAG_STATIC_PROP`) เป็นค่ามาตรฐานทุก entity (ยืนยันตรงกันทั้ง 4 แมพสตูดิโอจริงใน `sadddsa`: `ubbu_airdrop`, `ubbu_afk`, `ubbu_mainschool`, `ubbu_warzone_freeforall` ซึ่งใช้ `[32]` หรือ `[32, 33]` เท่านั้น)
  - **ห้าม** ใส่บิต `524288 | 1048576` (`flags = 1572896`) กับ entity ทั่วไปใน `.ymap` เพราะจะจอง slot ใน reflection/dynamic proxy pool ขนาด 256 เต็มทันทีเมื่อแมพมี 200+ entities ใกล้พื้นที่เมือง/ชายฝั่ง
  - `lod_level = ORPHANHD`, `priority_level = REQUIRED`, `parent_index = -1`
  - `ambient_occlusion_multiplier = 255`, `artificial_ambient_occlusion = 255`
- **Collision `include_flags` มาตรฐาน Rockstar (กัน static-vs-static broadphase noise):**
  - `type_flags` ของ static `.ybn` / `.ydr` ใช้ `MAP_TYPE_MOVER | MAP_TYPE_WEAPON | MAP_TYPE_COVER | MAP_TYPE_VEHICLE` (และ `MAP_TYPE_HORSE`)
  - **`include_flags` ห้ามใส่ `MAP_TYPE_*` ปนเข้าไปเด็ดขาด** — ใช้ canonical 17-flag mask ของ Rockstar (`PED_TYPE | RAGDOLL_TYPE | VEHICLE_BVH_TYPE | VEHICLE_NON_BVH_TYPE | OBJECT_TYPE | PLANT_TYPE | PROJECTILE_TYPE | EXPLOSION_TYPE | WEAPON_TEST | CAMERA_TEST | AI_TEST | SCRIPT_TEST | WHEEL_TEST | GLASS_TYPE | HORSE_* | FORKLIFT_FORKS_TYPE`)
- **Single-Sided Backface Culling บนป้ายโลโก้/โปสเตอร์ (CRITICAL):**
  - แผ่นป้ายแบบ quad เดี่ยว (`explicit_uvs`) **ห้าม** ผ่าน `bmesh.ops.recalc_face_normals()` เพราะ Blender จะกลับ normal ของ open sheet เข้าด้านใน ทำให้ใน Blender EEVEE (double-sided) มองเห็นปกติ แต่ใน GTA V / CodeWalker โดน backface cull หายทั้งแผ่น!
  - ให้แยก `explicit_uvs` ออกจาก `recalc_face_normals()`, เปิด `mat.use_backface_culling = True` ในสคริปต์เรนเดอร์พรีวิว และตรวจ outward vertex normal ใน `.ydr` เสมอ
- **Anti-Jump Sky Barrier (กันโดดตกขอบฟ้า 100%):**
  - ขอบแมพลอยฟ้า (Lobby / AFK / Sky Airdrop) ให้ทำกรอบกันตกที่มองเห็นสูงแค่ `1.2–1.3m` (หรือกำแพงสนาม `14–16m`) แต่ทำ **กล่องชนล่องหน (invisible collision wall)** หนา `0.65m` สูงจากใต้พื้น `-2.8m` ขึ้นไปถึง `+14.0m..+24.0m` เหลื่อมมุมชนกันสนิททั้ง 4 ด้าน + พื้นหนา `2.75–3.35m` กันวาร์ปทะลุพื้น
- **Multi-Arena Instancing (`arenas` ใน `map-spec.json` — ถอดบทเรียนจาก `sadddsa/ubbu_airdrop`):**
  - สำหรับแมพที่มีหลายสนามแยกพิกัด (เช่น Airdrop 3 โซน GANG / FAMILY / CITIZEN ห่างกัน 700m+) ให้ปั้น Hero `.ydr` + Shared `.ytd` + `.ytyp` **เพียงชุดเดียว** แล้วตั้ง `"arenas": [...]` เพื่อ export แยกเป็น `<arena>.ymap` + `<arena>_col.ybn` รายสนาม (โหลดเฉพาะสนามที่ผู้เล่นอยู่ BVH กระชับ กิน VRAM เท่า 1 สนาม และ `inspect_map.py` ตรวจครบทุกสนาม)
- **Extents Calculation:**
  - `entities_extents_min/max`: กล่องครอบ world-space AABB จริงของทุก entity (หลังหมุนด้วย `q` ไม่ใช่ `q_gtav`)
  - `streaming_extents_min/max`: ขยายออกทุกแกนด้วย `lod_distance` ของแต่ละ entity เพื่อให้เกมเริ่มโหลดแมพตั้งแต่ผู้เล่นอยู่ห่าง 250–400 เมตร และต้องคลุมจุดวาร์ป (warp point) ทั้ง X/Y/Z เต็มร้อยเปอร์เซ็นต์

## 5. `_manifest.ymf` & `fxmanifest.lua`

- `_manifest.ymf` ใช้รูปแบบ XML `<CPackFileMetaData>` ประกาศ `imapDependencies_2` เชื่อมชื่อ `.ymap` เข้ากับทุก `.ytyp` ที่ใช้งาน (ทั้ง custom `.ytyp` ของเรา และ vanilla `.ytyp` เช่น `v_trees`, `v_bush`, `v_lighting`, `v_fences`, `h4_prop_h4_bush`)
- `fxmanifest.lua` ใช้โครงสร้างสะอาดตาม `templates/fxmanifest.lua`:
  - ประกาศ `this_is_a_map "yes"`
  - ประกาศ `data_file "DLC_ITYP_REQUEST" "stream/<ytyp_name>.ytyp"`
  - **ห้าม** ใส่ไฟล์ `.ydr`/`.ytd`/`.ymap`/`.ybn` ใน `files { ... }` (FiveM โหลดโฟลเดอร์ `stream/` อัตโนมัติ ใส่เฉพาะ `.ytyp` ถ้าต้องอ้าง หรือปล่อยให้ `DLC_ITYP_REQUEST` อ้างตรง `stream/<ytyp>.ytyp`)

## 6. ภาพรวม MLO (สำหรับอาคารที่มีห้องภายใน)

เมื่อต้องสร้างอาคารที่มีห้องภายใน (Interior เช่น โรงพยาบาล, สภา, คาสิโน):
- ประกาศใน `.ytyp` เป็น `ArchetypeDefinitionMlo` แทน `ArchetypeDefinition`
- แบ่ง `rooms` (`limbo` room index 0 เสมอ + ห้องภายในแต่ละห้อง) และ `portals` (ประตู/หน้าต่างเชื่อมห้องและเชื่อม `limbo` สู่ภายนอก)
- วางของตกแต่งภายในเป็น `mlo.entities` ผูกกับ `attached_objects` ของห้องนั้น เพื่อไม่ให้เกมเรนเดอร์ของในห้องเมื่อผู้เล่นอยู่ข้างนอกอาคาร
- ตั้ง Vertex Color ในห้องให้ `R` ต่ำ (`20–70`) และใช้ `G` (`100–200`) คู่ `Drawable.lights` หรือ `timecycle` ของห้อง เพื่อให้แสงภายในคุมบรรยากาศได้อิสระจากแดดข้างนอก

## 7. ข้อผิดพลาดที่พบบ่อย & วิธีแก้ทันที

| อาการในเกม / ตอน Export | สาเหตุ | วิธีแก้ |
| --- | --- | --- |
| วาร์ปขึ้น Sky Map แล้วร่วงตกพื้น | ไม่มี static `.ybn` หรือ `content_flags` ไม่ใช่ `65` | สร้าง static world `.ybn` + ตั้ง `content_flags = 65` + ใส่ `physics_dictionaries` |
| แมพกลางแจ้งสว่างจ้าเป็นพลาสติกตอนกลางคืน | Vertex Color `"Color 1"` ช่อง `G = 255` | ตั้ง `Color 1` นอกอาคารเป็น `R=ao, G=0, B=ao, A=255` (`#FF00FF` baseline) |
| พื้น/กำแพงเบลอเป็นวุ้น | ใช้ Smart-UV single atlas หรือลืมตั้ง `hdTextureDist = lodDist` | เปลี่ยนเป็น World-Scale Tiled UV + ตั้ง `hd_texture_distance = lod_distance` |
| ร่องนูน Normal Map กลับด้าน (นูนเป็นบุ๋ม) | ไม่ได้กลับช่อง Green เป็น DirectX `-Y` | ใช้ `export_map.py` (กลับ `G = 1.0 - G` อัตโนมัติสำหรับ `*_n.png`) |
| Prop หมุนผิดมุมซ้าย-ขวา | ลืม `.inverted()` บน quaternion ของ `.ymap` | กลับ quaternion ก่อนเขียน และตรวจ round-trip ด้วย `inspect_map.py` |
| ต้นไม้/พุ่มไม้ `h4_*` ไม่ขึ้นในเกม | เซิร์ฟเวอร์ใช้ game build ต่ำกว่า 2189 หรือขาด `h4_prop_h4_bush` ใน `_manifest.ymf` | เพิ่ม `h4_prop_h4_bush` ใน `vanilla_ytyps` หรือสลับไปใช้ `v_bush` ของ base game |
| Sollumz หายในสคริปต์ headless `-b` | เรียก `bpy.ops.wm.read_factory_settings(use_empty=True)` หรือใส่ `--factory-startup` | ห้ามใส่ `--factory-startup` ตอน export และล้าง scene ด้วย `bpy.data.objects.remove` แทน |
| แมพแคช `<<unknown pool>> Pool Full, Size == 256` | ใส่ `e.flags = 1572896` (`524288\|1048576`) หรือ entity เยอะเกิน 200+ ใกล้โซนเมือง + `MAP_TYPE_*` ปนใน `include_flags` | ใช้ `e.flags = 32` ทุกชิ้น, ตัด `MAP_TYPE_*` ออกจาก `include_flags` และคุม entity ลานลอยฟ้า `<= 180` ชิ้น |
| ป้ายโลโก้เห็นใน Blender แต่หาย/ว่างใน CodeWalker & FiveM | `recalc_face_normals()` กลับ normal ของ open quad หันเข้าด้านใน ทำให้ RAGE ตัดทิ้ง (backface culling) | แยก `explicit_uvs` ออกจาก `recalc_face_normals()`, เช็ก outward normal ใน `.ydr` และเปิด `use_backface_culling = True` ในพรีวิว |
| ไฟล์ `.blend` เปิดใน 4.2.3 ไม่ได้ | บันทึกทับด้วย Steam Blender 5.3 (`BLENDER17`) | บันทึกไฟล์ต้นฉบับด้วย 4.2.3 เสมอ (ดู `antigravity.md`) |

## 8. สิ่งที่พิสูจน์แล้ว (Live In-Game & CodeWalker Verification Log)

- **CodeWalker / FiveM Live Lessons (`billie_map_lobby` & `billie_map_afk`):**
  - ยืนยัน `e.flags = 32` + canonical Rockstar `include_flags` แก้ปัญหา Pool-256 และลด entity จาก 243 → 169
  - ยืนยัน `recalc_face_normals` กับ single-quad sign ทำให้ป้ายหายใน CodeWalker — แยก `explicit_uvs` ออกแก้ขาด 100%
  - ยืนยัน `water_fountain.sps` ค่าเดิม (`FogColor` เข้ม + `SpecularIntensity=1.0`) ดูเป็นสี่เหลี่ยมสีเขียวทึบใน CodeWalker — ปรับเป็นสูตรรีสอร์ต + ปูพื้นอ่างสีสว่าง + PTFX `core` (`client/fountain.lua`) ทำให้น้ำพุใช้งานได้จริงใน FiveM
