# RAGE Shaders, Vertex Color Lighting & Embedded Lights

สูตรวัสดุ แสง และ Vertex Color ทั้งหมดด้านล่างผ่านการตรวจสอบจากไฟล์ binary `.ydr` จริงของแมพโปรดักชัน 12 ชุด

## 1. ความลับของ RAGE Vertex Color (`Color 1` / `DIFFUSE`)

ใน GTA V / FiveM ช่องสี `RGBA` ของ vertex color (`Color 1`, type `BYTE_COLOR`, domain `CORNER`) **ไม่ได้** เอาไปคูณสีพื้นผิวตรงๆ เหมือนเกมทั่วไป แต่ถูก RAGE engine แยกควบคุมระบบแสงกลางวัน/กลางคืน:

| ช่อง | หน้าที่ใน GTA V RAGE Engine | ค่าแนะนำสำหรับผิวนอกอาคาร (Exterior) | ค่าแนะนำสำหรับในร่ม/ใต้โคมไฟ (Interior / Under Lamp) |
| --- | --- | --- | --- |
| **R (Red)** | **Natural Daylight / Sky Ambient** | `160–255` (เอา Cycles AO คูณลงช่องนี้!) | `20–90` (มืดจากแสงฟ้าข้างนอก) |
| **G (Green)** | **Artificial Night Ambient** | **`0` เสมอ!** (ห้ามใส่ 255 ไม่งั้นกลางคืนผนังเรืองแสงหลอกตา) | `80–200` (ไล่สว่างเฉพาะจุดใต้โคมไฟหรือในห้อง) |
| **B (Blue)** | **General AO / Indirect Bounce** | `160–255` (เอา Cycles AO คูณลงช่องนี้!) | `140–255` |
| **A (Alpha)** | **Tint / Blend Mask** | `255` (ทึบเต็ม) | `255` |

### กฎเหล็ก `#FF00FF` สำหรับแมพกลางแจ้ง
- ค่ามาตรฐานที่สตูดิโอระดับโปรใช้กับงานสถาปัตยกรรมกลางแจ้ง (`tops_uptown_garagejob`, `tops_v2_rebel`, `id1_33_hospital`, `id1_33_ground`) คือ **`RGBA = (255, 0, 255, 255)`** (`#FF00FF`)
- **สูตรอัปเกรดระดับ AAA (Cycles AO + RAGE Split):**
  1. อบ Ambient Occlusion ด้วย Cycles (เช่น 32–64 samples) ได้ค่า `ao` ในช่วง `0.0..1.0`
  2. บีบช่วงให้ไม่ดำมิด: `ao_soft = 0.58 + 0.42 * ao` (ซอกมุมอยู่ราว `148`, ที่โล่ง `255`)
  3. เขียนลง `"Color 1"` ต่อ vertex corner:
     - **ผิวนอกอาคารทั่วไป:** `R = ao_soft`, `G = 0.0`, `B = ao_soft`, `A = 1.0`
     - **ผิวใต้หลังคาศาลาที่มีโคมไฟ:** `R = ao_soft * 0.75`, `G = 0.25–0.45` (เฉพาะใกล้โคมไฟ), `B = ao_soft`, `A = 1.0`
     - **ผิวถนน/ลานที่มีไฟถนนส่อง:** ไล่ `G` เป็นวงกลมอ่อนๆ `0.0 -> 0.40` ใต้ตำแหน่งเสาไฟเท่านั้น
- **เมื่อไหร่ใช้ขาวล้วน `(255, 255, 255, 255)`?** เฉพาะวัสดุ `emissive*.sps` หรือสเปกที่ผู้ใช้ขอให้สว่างจ้าตลอด 24 ชม. (แต่แมพสมจริงไม่ควรใช้กับพื้น/ผนังทั้งเกาะ เพราะตอนกลางคืนจะดูแบนและสว่างหลอกตา)

## 2. สูตร RAGE Shaders ที่ใช้จริง (Verified Production Presets)

เรียงตามความถี่การใช้งานจริงในแมพโปรดักชัน พร้อมค่าพารามิเตอร์ที่ผ่านการยืนยันแล้ว:

| Shader | ใช้กับ | Samplers ที่ต้องมี | พารามิเตอร์สำคัญ (Verified Defaults) |
| --- | --- | --- | --- |
| **`normal_spec.sps`** | **งานหลัก!** หินปูพื้น, ไม้, คอนกรีต, อิฐ, โลหะ, หินอ่อน | `DiffuseSampler`, `BumpSampler` (DX `-Y`), `SpecSampler` | `bumpiness=0.8..1.2`, `specMapIntMask=1.0`, `specularIntensityMult=0.15..0.55` (หินด้าน 0.15, ไม้เคลือบ 0.30, โลหะ 0.65), `specularFalloffMult=25..100`, `specularFresnel=0.75..0.97` |
| **`normal.sps`** | ผิวด้านที่ไม่ต้องคุมความเงาแยก (ปูนฉาบ, ดิน, หญ้า) | `DiffuseSampler`, `BumpSampler` | `bumpiness=1.0`, `specularIntensityMult=0.125`, `specularFalloffMult=100.0`, `specularFresnel=0.97` |
| **`default.sps`** | สีพื้นเรียบ, micro-swatch `4x4`, ชิ้นรอง/ใต้ฐาน | `DiffuseSampler` | `wetnessMultiplier=1.0` |
| **`normal_spec_detail.sps`** | ผืนพื้นหรือผนังขนาดใหญ่ที่อยากได้เกรนละเอียดระยะประชิด | `DiffuseSampler`, `DetailSampler`, `BumpSampler`, `SpecSampler` | `detailSettings=[0.6, 0.6, 8.0, 8.0]`, `bumpiness=0.5..1.0`, `specularIntensityMult=0.5..1.0`, `specularFalloffMult=30.0`, `specularFresnel=0.8` |
| **`decal.sps`** / **`normal_spec_decal.sps`** | โลโก้พื้น, เส้นจราจร, รอยคราบ, ป้ายแปะผนัง | `DiffuseSampler` (DXT5 alpha) [+ `Bump`/`Spec`] | วางสูงกว่าพื้น `0.008–0.015m` กัน Z-fighting, `specularIntensityMult=0.125`, `specularFalloffMult=100.0` |
| **`glass_env.sps`** | กระจกหลังคา Skylight, กระจกอาคาร, ราวกันตกกระจก | `DiffuseSampler` (DXT5 alpha 20–45%), `BumpSampler`, `SpecSampler` | `bumpiness=1.0`, `specularIntensityMult=0.125..0.5`, `specularFalloffMult=400.0`, `specularFresnel=0.97` |
| **`cutout.sps`** / **`cutout_fence.sps`** | รั้วตะแกรง, เหล็กดัดฉลุ, ใบไม้/เถาวัลย์ | `DiffuseSampler` (DXT5 hard alpha) | `HardAlphaBlend=1.0`, `wetnessMultiplier=1.0` |
| **`emissive.sps`** | โคมไฟ, ป้ายไฟเรืองแสงทั้งวัน | `DiffuseSampler` | `emissiveMultiplier=1.5..3.5` (อย่าเกิน 5.0 ไม่งั้น bloom แตก) |
| **`emissivenight.sps`** | **แนะนำสุดสำหรับหน้าต่าง/ป้ายไฟกลางแจ้ง!** สว่างเฉพาะกลางคืน | `DiffuseSampler` | `emissiveMultiplier=1.0..2.5` (กลางวันไม่เรืองแสง) |
| **`emissive_alpha.sps`** / **`emissivestrong_alpha.sps`** | ตัวอักษรไฟนีออนพื้นใส, สัญลักษณ์เรืองแสง | `DiffuseSampler` (DXT5 alpha) | `emissiveMultiplier=1.0..2.5` |
| **`water_fountain.sps`** / **`water_poolenv.sps`** | บ่อน้ำพุ, สระสะท้อนเงา, ลำธารตกแต่ง | (Water shader ไม่ใช้ diffuse ปกติ) | **สูตรน้ำพุรีสอร์ตใส (`dt1_13_fountainwater.ydr`):** `FogColor=[0.46, 0.78, 0.86, 0.16]`, `SpecularFalloff=2000.0`, `SpecularIntensity=10.0`, `RippleScale=0.20`, `RippleBumpiness=0.55` + ปูพื้นอ่างด้วยหินสีสว่าง (`CREAM`) + ผูก PTFX `core` (`ent_amb_fountain_double`, `ent_amb_fountain_pour`, `ent_amb_water_splash_wide`) ใน `client/fountain.lua` (สตรีมตามระยะ 0.00ms) |

### สูตร Floodlit 24/7 PvP Stadium Vertex Color (สำหรับ Airdrop / Warzone ที่แข่งตอนกลางคืน `21:30 / 23:00 / 01:00`)
- แทนการใช้ `emissive.sps` แบนๆ ทั้งสนาม (ซึ่งทำให้กลางวันไร้เงาดูเป็นของเล่น) ให้ใช้ **`normal_spec.sps` / `default.sps`** คู่ **Floodlit Stadium VCol**:
  - `R = ao_soft` (`0.72..1.0` ให้แดดกลางวันมีเงาซอกสมจริง)
  - **`G = 0.56..0.66` (`145..168`)** แทน `0` เพื่อให้ตอนกลางคืนสนามสว่างเท่ากันทั่วผืนหญ้าแบบสนามกีฬาเปิดสปอตไลต์ เห็นศัตรูชัด 100% โดยไม่เรืองแสงหลอกตา (ตั้ง `budgets.max_outdoor_vcol_g = 175` ใน `map-spec.json`)
  - ฝังไฟ `POINT` ความแรงสูงบนเสาสปอตไลต์ 8 ต้นรอบขอบสนามเสริมเงาแสงอบอุ่นตอนกลางคืน

## 3. กฎ DirectX `-Y` Normal Map & Specular Map

- **Normal Map (DirectX Convention):** Blender และเครื่องมือ OpenGL ใช้ `+Y` (Green ขึ้นบน) แต่ GTA V RAGE ใช้ **DirectX (`-Y`)**! ก่อนเข้ารหัส `*_n.dds` ต้องกลับช่องสีเขียวเสมอ: `G = 1.0 - G` (สคริปต์ `export_map.py` จัดการให้อัตโนมัติเมื่อชื่อไฟล์ลงท้าย `_n.png`)
- **TANGENT0 Vertex Stream:** ทุก geometry ที่ใช้ `normal*.sps` หรือ `glass_env.sps` ต้องมี `TANGENT0` ใน Vertex Buffer (Sollumz สร้างให้อัตโนมัติเมื่อ mesh มี `"UVMap 0"` และใช้ shader ตระกูล `normal*` — `inspect_map.py` ตรวจยืนยันให้)
- **Specular Map (`*_s.png`):** เก็บเป็น grayscale/RGB โดยค่าความสว่าง (0.0–1.0) แทนความแรงสะท้อนแสง (หิน/ปูน `0.12–0.28`, ไม้เคลือบ `0.25–0.45`, กระเบื้อง/หินอ่อน `0.45–0.70`, โลหะ/ทองเหลือง `0.65–0.90`)

## 4. สูตรไฟฝัง `Drawable.lights` (Verified Production Recipes)

จากการแกะไฟจริง 49 ดวงในแมพโปรดักชัน มี 4 สูตรหลักที่ใช้ได้ทันที:

| สูตร | `type` | `color` (RGB) | `intensity` | `falloff` (m) | `falloff_exp` | `cone_in / out` | `corona_size / int` | `time_flags` | `flags` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A. Warm Night Plaza Fill** (โคมสวน/ศาลา) | `POINT` | `[255, 224, 168]` | `2.0–3.5` | `18.0–35.0` | `64.0–128.0` | `0 / 0` | `0.6 / 0.4` | `HOUR_18..HOUR_06` | `0` (ประหยัด FPS สูงสุด) |
| **B. Wide Sky Island Ambient** (คลุมลานกว้าง) | `POINT` | `[255, 227, 166]` | `3.0` | `80.0–100.0` | `256.0` | `0 / 0` | `0.0 / 0.0` | `HOUR_18..HOUR_06` | `0` |
| **C. Soft Interior / Porch Lamp** (ใต้ชายคา/ห้อง) | `POINT` | `[255, 250, 240]` | `1.0–1.8` | `5.0–10.0` | `128.0–256.0` | `0 / 0` | `0.0 / 0.8` | `NIGHT` | `CAST_STATIC_GEOM_SHADOWS` |
| **D. Hero Accent Spot** (ส่องป้ายแบรนด์/น้ำพุ) | `SPOT` | ตามสีแบรนด์ หรือ `[255, 238, 200]` | `6.0–12.0` | `6.0–15.0` | `64.0–128.0` | `25 / 75–90` | `0.0 / 0.5` | `HOUR_18..HOUR_06` | `CAST_STATIC_GEOM_SHADOWS` |
| **E. Arena Floodlight** (PvP/Warzone) | `POINT` | `[255, 255, 255]` | `12.0–15.0` | `150.0–200.0` | `100.0` | `0 / 0` | `0.0 / 0.0` | `NIGHT` | `0` |

### เทคนิค "Invisible Light Emitter" 12 Triangles
สตูดิโอระดับโปรสร้าง prop จิ๋ว 1 ชิ้น (กล่องขนาด `0.01m`, 12 tris, ซ่อนไว้ในโคม/ใต้น้ำพุ/หน้าป้าย) ที่ฝัง `SPOT` หรือ `POINT` light ไว้ใน `.ydr` แล้ววางซ้ำกี่จุดก็ได้ผ่าน `.ymap` (ตั้ง `lod_distance = 60..120`, `flags = 537526304` หรือ `32`)
- **ข้อดี:** ปรับมุมไฟ ความสูง และจำนวนดวงได้จาก `map-spec.json` โดยไม่ต้อง re-export shell หลัก และคุมจำนวนไฟที่มี `CAST_DYNAMIC_GEOM_SHADOWS` ไม่ให้เกิน **4–6 ดวงต่อฉาก** เพื่อรักษา 144+ FPS
