# โครงสร้าง .ypt และข้อมูลอ้างอิง

อ่านไฟล์นี้เมื่อต้องเขียนสเปกระดับล่างเอง, แปลผลจาก `inspect`, แก้เครื่องมือใน `scripts/ptfx/`, หรือหาชื่อ texture ของเกม งานออกแบบทั่วไปใช้ `particles.md` พอ

## เครื่องมือ

ทั้งหมดอยู่ใน `scripts/ptfx/` เป็น C# ที่ PowerShell คอมไพล์ให้เองครั้งแรก (เก็บ DLL ไว้ใน `%TEMP%\weapon-forge-ptfx`) ไม่ต้องติดตั้งอะไร

| คำสั่ง | หน้าที่ |
| --- | --- |
| `ptfx.ps1 themes` | รายการธีมสำเร็จรูป 20 ธีม |
| `ptfx.ps1 new -Theme t -Name id -Out <folder> [-Colors "primary=#.."]` | เขียน design ของชุดใหม่จากธีม |
| `ptfx.ps1 recipes` | รายการสูตร layer, รูปทรง sprite และ sheet สำเร็จรูป |
| `ptfx.ps1 sprites [-Spec design.json] -Out x.png` | ภาพรวม sprite ทุกแบบ หรือเฉพาะของ design |
| `ptfx.ps1 build -Spec design.json -Out <folder> [-Core core.ypt]` | สร้าง `<dict>.ypt`, อ่านกลับมาตรวจ, lint, ภาพ preview และ sprite |
| `ptfx.ps1 preview -Spec design.json` หรือ `-Path x.ypt` | ภาพจำลอง 8 ช่วงเวลามองจากข้าง และหนึ่งภาพมองจากบน ต่อ effect |
| `ptfx.ps1 lint -Path x.ypt` | ตรวจไฟล์ใดก็ได้ด้วยเกณฑ์เดียวกับ build |
| `ptfx.ps1 textures -Path x.ypt -Out <folder> [-Name tex]` | ถอด texture ที่ฝังอยู่เป็น PNG (DXT1/3/5, ATI1/2, ARGB, A8, L8) |
| `ptfx.ps1 inspect -Path x.ypt` | สรุปทุก effect เป็นข้อความ |
| `ptfx.ps1 decompile -Path x.ypt -Out x.json [-Full]` | แตกเป็นสเปกระดับล่าง `-Full` แสดงทุกช่องรวมค่าเริ่มต้น |
| `ptfx.ps1 census -Path x.ypt` หรือ `-Roots a,b` | ตรวจว่าอ่านครบทุกไบต์ ไม่มี pointer หลุด |
| `ptfx.ps1 roundtrip -Roots a,b` | แตกแล้วประกอบกลับ เทียบทุก struct ใช้ทดสอบหลังแก้เครื่องมือ |
| `ptfx.ps1 defaults -Roots a,b` | สร้าง `ptfx-defaults.json` ใหม่จากไฟล์จริง |
| `ptfx.ps1 ranges -Roots a,b` | สร้าง `ptfx-ranges.json` ใหม่จากไฟล์จริง |
| `ptfx.ps1 stats -Roots a,b -Out x.txt` | สถิติของทั้งคลัง |

หลังแก้ไฟล์ `.cs` ให้รันสามอย่าง: `roundtrip` กับโฟลเดอร์ที่มี `.ypt` จริง ผลต้องไม่แย่กว่า `pass=158 fail=5` (ห้าไฟล์นั้นต้นฉบับผิดปกติเอง), `census` ต้องได้ `clean=162 failed=0`, และ build ธีมทั้ง 20 ธีมต้องได้ `RESULT ok ... errors=0 warnings=0` ทุกตัว ตัวสแกนโฟลเดอร์ข้าม resource ที่มี `.fxap`

ไฟล์ข้อมูล

| ไฟล์ | เนื้อหา | แก้มือได้ไหม |
| --- | --- | --- |
| `ptfx-defaults.json` | ค่าที่พบบ่อยที่สุดของทุกช่องในทุก struct และชุด shader variable ของแต่ละ technique ตัวสร้างเริ่มจากค่าเหล่านี้แล้วเขียนทับด้วยสเปก จึงไม่ได้คัดลอก effect ของใคร | ไม่ สร้างใหม่ด้วย `defaults` |
| `ptfx-ranges.json` | ช่วงค่า (ต่ำสุด สูงสุด p1 p99 และชุดค่าที่พบเมื่อมีไม่เกิน 24 ค่า) ของ 2,730 ช่องจาก 183 ไฟล์, ชื่อ texture 107 ตัวและ effect 964 ตัวของ `core.ypt` | ไม่ สร้างใหม่ด้วย `ranges` |
| `ptfx-archetypes.json` | สูตร layer 60 แบบ | ได้ |
| `ptfx-sheets.json` | sheet สำเร็จรูป 18 ชุด | ได้ |
| `ptfx-themes.json` | ธีม 20 ธีม พร้อม preset ของ screen และ sound ที่เข้าชุด | ได้ |

ซอร์ส: `YptCore.cs` (อ่าน/เขียน resource และตาราง struct), `YptSpec.cs` (สเปกระดับล่าง), `YptDesign.cs` (design → สเปก), `YptTex.cs` กับ `YptTexFx.cs` (ตัววาด sprite และ sheet), `YptTexDecode.cs` (ถอด texture), `YptLint.cs` (ช่วงค่าและตัวตรวจ), `YptPreview.cs` (ตัวจำลอง), `YptBuild.cs` (คำสั่งระดับบน), `YptInspect.cs`, `YptStats.cs`, `YptJson.cs`

### Lint ตรวจอะไร

รอบโครงสร้าง: ทุกค่าตัวเลขของไฟล์ที่ build แล้ว (ราว 20,000 ค่าต่อไฟล์) เทียบกับ `ptfx-ranges.json` ค่าที่อยู่นอกช่วงของทุกไฟล์จริง หรือเป็นค่าจำนวนเต็มที่ไม่เคยมีไฟล์ใดใช้ จะเป็น `WARN` รอบนี้คือสิ่งที่จับได้ว่า effect ไม่ควรมีเกิน 7 layer

รอบออกแบบ: texture ที่อ้างต้องฝังอยู่หรือเป็นของ `core.ypt`, เฟรมที่ขอต้องไม่เกินตารางของ sheet, ขนาดและ alpha ต้องไม่เป็นศูนย์ทุกคีย์, เวลาของคีย์เฟรมต้องเรียงจาก 0 ถึง 1, `start` ต้องน้อยกว่า `end`, layer แบบ `rate` ต้องปล่อยได้อย่างน้อยหนึ่งชิ้น, sprite แบบ `velocity` ต้องมีความเร็ว, ชื่อ dictionary และ effect ต้องไม่ชนกับของเกม, จำนวนชิ้นพร้อมกันเทียบกับงบ

รัน `lint` กับไฟล์ของผู้สร้างอื่นจะเจอ error จำนวนมาก (rule ที่ไม่ได้ใช้, คีย์เฟรมซ้ำเวลา) ซึ่งเกมทนได้ เกณฑ์นี้ตั้งไว้เข้มกว่าที่เกมต้องการเพื่อให้ไฟล์ที่เราสร้างสะอาด

## ลำดับชั้น

```
ptxFxList (ไฟล์)
├─ texture dictionary        ภาพที่ฝังมา
├─ drawable dictionary       โมเดลของ ptfx_model (ตัวสร้างเว้นว่าง)
├─ effect rules              ชื่อที่ Lua เรียก
│   └─ event emitters        ช่วงเวลา StartRatio–EndRatio ของแต่ละ layer
│       ├─ emitter rule      เกิดที่ไหน กี่ชิ้น อายุเท่าไร เร็วแค่ไหน
│       │   └─ domains       creation (จุดเกิด), target (ทิศ), attractor
│       └─ particle rule     หน้าตาและพฤติกรรม
│           ├─ behaviours    Age, Velocity, Size, Colour, Rotation, ...
│           └─ shader vars   texture และค่าของ shader
```

Emitter rule กับ particle rule ใช้ร่วมกันได้หลาย event ทุก dictionary เรียงตาม joaat ของชื่อจากน้อยไปมาก

## สเปกระดับล่าง

`decompile` ให้ JSON ที่มี `textures`, `effects`, `emitters`, `particles` ชื่อช่องตรงกับตารางใน `YptCore.cs` (`Schema`) ช่องที่เท่ากับค่าเริ่มต้นจะไม่แสดง `build` รับรูปแบบเดียวกัน จึงเขียนเองได้เมื่อ design ทำไม่ถึง

คีย์เฟรม (KFP) เขียนเป็น `[[t, x, y, z, w], ...]` โดย `t` คือ 0–1 ของอายุ particle (หรือของช่วง emitter) ค่าระหว่างคีย์ไล่เชิงเส้น คู่ Min/Max คือช่วงสุ่มของแต่ละชิ้น

### หน่วยและความหมาย

| ที่ | ช่อง | ค่า |
| --- | --- | --- |
| Effect | `NumLoops` | 0 = เล่นครั้งเดียว, -1 = loop ไม่จบ |
| Effect | `DurationMin/Max` | วินาที |
| Effect | `ZoomScalarKFP` | เปอร์เซ็นต์ (min, max) 100 = ขนาดจริง ย่อทั้ง effect รวมระยะและความเร็ว |
| Effect | `DistanceCullingCullDist`, `...FadeDist` | เมตร |
| Event | `StartRatio`, `EndRatio` | สัดส่วนของ duration |
| Emitter | `IsOneShot` | 1 = ปล่อยครั้งเดียว `SpawnRateOverTimeKFP` คือจำนวนชิ้น, 0 = ชิ้นต่อวินาที |
| Emitter | `ParticleLifeKFP` | (min, max) วินาที |
| Emitter | `SpeedScalarKFP` | (min, max) m/s ตามทิศจากจุดเกิดไปจุดใน target domain |
| Emitter | `SizeScalarKFP`, `AccnScalarKFP`, `DampeningScalarKFP` | เปอร์เซ็นต์ 100 = ไม่เปลี่ยน |
| Domain | `DomainType` | 0 box, 1 sphere, 2 cylinder, 3 attractor |
| Domain | `IsPointRelative` | target นับจากจุดเกิดของแต่ละชิ้น |
| Domain | `SizeOuterKFP`, `SizeInnerKFP` | เมตร ชิ้นเกิดระหว่าง inner กับ outer |
| Size | `WhdMinKFP`, `WhdMaxKFP` | (กว้าง, สูง) เมตร ของ trail ใช้ช่องสูงเป็นความกว้างริบบิ้น |
| Size | `TblrVelScalarKFP` | ยืดตามความเร็ว |
| Colour | `RGBAMinKFP`, `RGBAMaxKFP` | 0–1 ต่อช่อง |
| Colour | `EmissiveIntensityKFP` | ตัวคูณความสว่าง ไฟล์จริง median 14, p90 120 |
| Rotation | `InitialAngle*`, `Angle*` | องศา, องศาต่อวินาที |
| Acceleration | `XYZMin/Max` | m/s² แกน Z ลบคือตก |
| Dampening | `XYZMin/Max` | ยิ่งมากยิ่งหยุดเร็ว ไฟล์จริง median 1 |
| MatrixWeight | `MtxWeightKFP` | 1 = เกาะตาม emitter, 0 = อยู่ในโลก |
| AnimateTexture | `AnimRateKFP`, `LastFrameID`, `LoopMode` | เฟรมต่อวินาที, เฟรมสุดท้าย |
| Particle rule | `TexFrameIDMin/Max` | ช่วงเฟรมเริ่มต้นที่สุ่ม |
| Particle rule | `BlendSet` | 0 ปกติ, 1 additive |
| Particle rule | `DrawType` | 0 sprite, 1 model, 2 trail |
| Sprite | `AlignmentMode` | 0 หันกล้อง (78%), 1 ตามทิศวิ่ง ด้านสูงของภาพชี้ตามความเร็ว (19%), 2 หน้าตั้งฉากกับ `AlignAxis` ในแกนโลก (ของที่นอนบนพื้นหรือผิวน้ำใช้ 0,0,1), 4 เหมือน 2 แต่ในแกนของ emitter (วงไอพ่นท้ายเครื่องบิน) |
| Light | `IntensityKFP`, `RangeKFP` | ความเข้ม (ไฟล์จริง median 64 เพราะส่วนใหญ่เป็นระเบิด ของเล็กใช้ 0.2–3) และระยะเป็นเมตร (median 3) |
| Trail | `TexInfoKFP`, ขนาด | ความกว้างของริบบิ้นอยู่ในช่องสูงของ `Whd` ค่า `TexInfo` ที่พบบ่อยคือ (5,5,11,11) → (5,5,0,0) ริบบิ้นน่าจะเชื่อม particle ของ emitter เดียวกันตามลำดับเกิด (อนุมานจากเปลวเทียนของเกมซึ่งปล่อย 4 ชิ้นต่อวินาทีจากจุดเดียว) ยังไม่เคยเห็นผลในเกม |

ขนาดจริงบนจอ = `Whd` × `SizeScalarKFP`/100 ของ emitter × `ZoomScalarKFP`/100 ของ effect เป็นความกว้างเต็มของ sprite ไม่ใช่ครึ่งเดียว KFP ที่ว่างหมายถึงไม่ปรับ ตัวสร้างตั้งทั้งสองเป็น 100 เพื่อให้ `size` ใน design เป็นเมตรตรง ๆ effect ของเกมเกือบทั้งหมดใช้ `Zoom` 5–50 กับ `Whd` ที่ใหญ่กว่าความจริงหลายเท่า เวลาอ่านผล `inspect` ของไฟล์อื่นต้องคูณกลับเสมอ

แกนของ emitter: X ขวา, Y หน้า, Z ขึ้น ทรงกระบอก (`DomainType` 2) มีแกนยาวตาม Y `Acceleration.ReferenceSpace` 0 (92% ของ rule) ใช้ทำแรงโน้มถ่วง จึงถือว่าเป็นแกนโลก

`AnimateTexture` ชุดค่าที่ rule ของเกมใช้

| ใช้กับ | `LoopMode` | `IsScaledOverParticleLife` | `IsHeldOnLastFrame` | `IsRandomised` | `AnimRate` | จำนวน rule ของเกม |
| --- | --- | --- | --- | --- | --- | --- |
| ควันคลี่ตัว | 1 | 1 | 1 | 0 | 6–11 | 253 |
| ไฟ ฟอง (วน) | 1 | 0 | 0 | 0 | 18–30 | 87 |
| เลือด (เล่นจบแล้วค้าง) | 0 | 0 | 1 | 0 | 24–40 | 14 |
| สายฟ้า น้ำกระเซ็น (สุ่มเฟรม) | 0 | 0 | 0 | 1 | 1–15 | 19 |

`TexFrameIDMin/Max` คือช่วงเฟรมเริ่มต้นที่สุ่ม ส่วน `LastFrameID` คือเฟรมสุดท้ายของการเล่น rule ที่ไม่มี `AnimateTexture` จะค้างที่เฟรมเริ่มต้น ซึ่งคือวิธีทำ "ภาพสุ่มต่อชิ้น"

Technique ที่ใช้จริง: `RGBA_lit_soft` 38%, `RGBA_lit` 16%, `RGB_lit_soft` 16%, `RGB_soft` 11%, `RGBA_soft` 5% กลุ่ม `RGB_*` คือ texture ไม่มี alpha มักใช้ additive, `*_lit` รับแสงของฉาก (ควัน เศษ), `*_soft` จางเมื่อตัดกับพื้นผิว

`RandomIndex` ของ KFP เป็นหมายเลขตัวสุ่ม KFP ที่ใช้เลขเดียวกันจะสุ่มไปด้วยกัน ตัวสร้างแจกเลขไม่ซ้ำภายใน rule ให้เอง

## ไฟล์ทรัพยากร

RSC7 เวอร์ชัน 68 ส่วน system เก็บ struct ทั้งหมด ส่วน graphics เก็บพิกเซล ตัวเขียนวางทุกบล็อกไม่ให้คร่อมหน้า ใช้หน้าขนาดเท่ากันไม่เกิน 127 หน้าต่อส่วน และเว้นที่ 4 KB หลัง page map แบบเดียวกับไฟล์จริง Texture ที่สร้างเป็น DXT5 พร้อม mip ลงถึงด้านสั้น 4 px ตั้ง `"format": "argb"` ใน texture เมื่อต้องการไม่บีบอัด

## Texture หลายเฟรม

เกมไม่ได้เก็บตารางเฟรมไว้ในไฟล์ `.ypt` (ไม่มีช่องใดใน particle rule, shader variable หรือ texture ที่บอกจำนวนคอลัมน์และแถว) แต่ผูกไว้กับ**ชื่อ texture** ผลที่ตามมาสองข้อ ซึ่งยืนยันจากไฟล์จริงทั้งคู่:

1. Texture ที่ตั้งชื่อใหม่ถูกวาดทั้งภาพเป็นเฟรมเดียว ไม่ว่า `TexFrameID` หรือ `AnimateTexture` จะตั้งไว้อย่างไร สกินที่ขายจริงหลายตัวฝังภาพเดี่ยว (ไฟ 1024×2048, อุ้งเท้าแมว) ไว้กับค่าเฟรมที่ค้างมาจาก rule ต้นแบบ และภาพก็ออกมาเต็ม
2. Texture ที่ฝังไว้ใต้ชื่อของเกมถูกตัดเฟรมตามตารางของชื่อนั้น ไม่ว่าภาพข้างในหรือขนาดจะต่างจากของเกม (rule 758 ตัวในไฟล์จริงทำแบบนี้ เช่น `ptfx_multi_sheet_002_debris` ที่ 1024 px แทน 256 px ของเกม)

Sheet ของ design ใช้ข้อ 2: ตัวสร้างฝัง sheet ของเราใต้ชื่อเกมที่ตารางตรงกัน เลือกจากรายการนี้ตามลำดับ โดยข้ามชื่อที่ layer อื่นในไฟล์เดียวกันอ้างของเกมอยู่

| ตาราง | ชื่อที่ใช้ได้ (ตามลำดับที่เลือก) |
| --- | --- |
| 2x2 | `ptfx_fishes`, `ptfx_casino_chips`, `ptfx_flower_petals`, `ptfx_rubble`, `ptfx_cig_smoke_sheet` |
| 3x3 | `ptfx_muzzle_core_02`, `ptfx_smoke_static_rgba` |
| 4x4 | `ptfx_insects_rgb`, `ptfx_multi_sheet_004_debris`, `ptfx_multi_sheet_003_debris`, `ptfx_multi_sheet_002_debris` |
| 5x5 | `ptfx_bubbles_trail_anim`, `ptfx_flipbook_fire_rgb` |
| 6x6 | `ptfx_smoke_billow_anim_rgba`, `ptfx_smoke_thin_anim` |
| 7x7 | `ptfx_steam_anim`, `ptfx_blood_spray`, `ptfx_smoke_wispy_anim` |

เฟรมนับจากซ้ายบน ไปทางขวาทีละแถว Sheet ถูกสร้างพร้อม mip เท่าที่ช่องยังกว้างอย่างน้อย 16 px เพื่อไม่ให้เฟรมข้างเคียงซึมเข้าหากัน `Sprite.UVClip` คงเป็น 0 (96% ของไฟล์จริง) เกมจึงวาดเต็มช่องโดยไม่ตัดขอบตามรูปเดิมของเกม

ตารางของ sheet เกม อ่านจากภาพของ texture โดยตรง (`ptfx.ps1 textures -Path core.ypt`)

| ตาราง | texture |
| --- | --- |
| 2x2 | `ptfx_bubbles_sheet` `ptfx_casino_chips` `ptfx_embers_rgb` `ptfx_flower_petals` `ptfx_glow_rgb` `ptfx_sparks` `ptfx_sparks_arcing_anim` `ptfx_water_jets` `ptfx_cig_smoke_sheet` `ptfx_fishes` `ptfx_flare` `ptfx_rubble` `ptfx_smoke_new_plumes` `ptfx_water_splashes_sheet` `ptfx_water_splashes_sheet_b` `ptfx_gloop` `ptfx_glass_dots_sheet` `ptfx_fine_debris_sheet` |
| 4x1 | `ptfx_bullet_tracer` `ptfx_bush_twigs` `ptfx_grass_blades` `ptfx_fire_tail` `ptfx_water_dripping_rgb` |
| 8x1 | `ptfx_blood_spurt` `ptfx_blood_squibs` |
| 1x2 | `ptfx_muzzle_02` |
| 3x3 | `ptfx_smoke_static_rgba` `ptfx_muzzle_core_02` |
| 4x4 | `ptfx_multi_sheet_002_debris` `ptfx_multi_sheet_003_debris` `ptfx_multi_sheet_004_debris` `ptfx_muzzle_core_rgb` `ptfx_insects_rgb` |
| 5x5 | `ptfx_flipbook_fire_rgb` `ptfx_bubbles_trail_anim` |
| 5x10 | `ptfx_fire_v2` |
| 6x6 | `ptfx_smoke_thin_anim` `ptfx_smoke_billow_anim_rgba` `ptfx_water_splash_kick` |
| 7x7 | `ptfx_smoke_wispy_anim` `ptfx_steam_anim` `ptfx_blood_spray` |

## Texture ของเกม

อ้างด้วยชื่อใน `texture` ของ layer ได้เลย คอลัมน์ frames คือจำนวนเฟรมที่ rule ของเกมใช้จริง ถ้ามากกว่า 1 ให้ตั้ง `frames` (ช่วงเฟรมเริ่ม) หรือ `anim.last` ไม่เกินค่านี้ลบหนึ่ง ชื่อที่ไม่อยู่ในตารางนี้อ้างไม่ได้ lint จะรายงานเป็น error

| texture | size | format | frames | game rules using it | usual technique |
| --- | --- | --- | --- | --- | --- |
| `ptfx_smoke_wispy_anim` | 1024x1024 | DXT5 | 49 | 418 | RGBA_lit_soft |
| `ptfx_gloop` | 256x256 | DXT5 | 4 | 110 | RGBA_lit_soft |
| `ptfx_multi_sheet_002_debris` | 256x256 | DXT5 | 16 | 95 | RGBA_lit |
| `ptfx_glow_rgb` | 512x512 | DXT1 | 4 | 81 | RGB_lit_soft |
| `ptfx_water_jets` | 256x512 | DXT5 | 3 | 74 | RGBA_lit_soft |
| `ptfx_water_splashes_sheet_b` | 512x512 | DXT5 | 4 | 69 | RGBA_lit_soft |
| `ptfx_multi_sheet_003_debris` | 256x256 | DXT5 | 16 | 57 | RGBA_lit |
| `ptfx_muzzle_core_rgb` | 512x512 | DXT1 | 16 | 51 | RGB_lit |
| `ptfx_glass_dots_sheet` | 128x128 | DXT5 | 4 | 38 | RGBA_lit |
| `ptfx_fire_v2` | 1024x2048 | DXT1 | 50 | 37 | RGB_soft |
| `ptfx_smoke_new_plumes` | 256x256 | DXT5 | 4 | 32 | RGBA_lit_soft |
| `ptfx_water_splashes_sheet` | 512x512 | DXT5 | 4 | 30 | RGBA_lit_soft |
| `ptfx_water_dripping_rgb` | 64x256 | DXT5 | 4 | 28 | RGB_lit |
| `ptfx_embers_rgb` | 256x256 | DXT1 | 4 | 27 | RGB_lit_soft |
| `ptfx_flipbook_fire_rgb` | 1024x1024 | DXT1 | 25 | 25 | RGB_soft |
| `ptfx_smoke_thin_anim` | 512x512 | DXT5 | 36 | 25 | RGBA_lit_soft |
| `ptfx_multi_sheet_004_debris` | 128x128 | DXT5 | 16 | 22 | RGBA_lit |
| `ptfx_glow` | 128x128 | DXT5 | 1 | 20 | RGBA_lit_soft |
| `ptfx_ribbon_solid_pour` | 512x64 | DXT5 | 1 | 19 | RGBA_lit |
| `ptfx_bubbles_sheet` | 512x512 | DXT5 | 4 | 15 | RGBA_lit_soft |
| `_explosion_fireball_rgba` | 2048x1024 | DXT5 | 32 | 15 | RGBA_lit_soft |
| `ptfx_bubbles_trail_anim` | 512x512 | DXT5 | 25 | 15 | RGBA_lit_soft |
| `ptfx_sparks_arcing_anim` | 128x128 | DXT5 | 4 | 14 | RGBA_lit_soft |
| `ptfx_smoke_spikes` | 128x256 | DXT5 | 1 | 14 | RGBA_lit |
| `ptfx_blood_spray` | 512x512 | DXT5 | 49 | 14 | RGBA_lit_soft |
| `ptfx_smoke_billow_anim_rgba` | 1024x1024 | DXT5 | 36 | 14 | RGBA_lit_soft |
| `_explosion_fireball` | 1024x1024 | DXT1 | 36 | 14 | RGB_lit_soft |
| `ptfx_grey_square` | 32x32 | DXT5 | 1 | 13 | RGBA_lit_soft |
| `ptfx_sparks` | 128x128 | DXT5 | 4 | 13 | RGBA |
| `ptfx_ribbon_water_pour` | 512x64 | DXT5 | 1 | 10 | RGBA_lit |
| `ptfx_ribbon_gen_test` | 512x128 | DXT5 | 1 | 10 | RGBA_lit_soft |
| `ptfx_rubble` | 512x512 | DXT5 | 4 | 10 | RGBA_lit_soft |
| `ptfx_muzzle_02` | 512x512 | DXT5 | 2 | 10 | RGB_lit |
| `ptfx_smoke_static_rgba` | 512x512 | DXT5 | 9 | 10 | RGBA_lit_soft |
| `ptfx_smoke_sheet_6` | 2048x2048 | DXT5 | 36 | 9 | RGBA_lit_soft |
| `ptfx_flat_glow_rgb` | 512x256 | DXT1 | 1 | 9 | RGB_lit_soft |
| `ptfx_bullet_tracer` | 128x256 | DXT5 | 4 | 8 | RGBA_lit_soft |
| `ptfx_grass_blades` | 128x128 | DXT5 | 4 | 8 | RGBA_lit |
| `ptfx_insects_rgb` | 1024x1024 | DXT5 | 15 | 7 | RGBA_lit_soft |
| `ptfx_white_wash_uni` | 512x512 | DXT5 | 4 | 7 | RGBA_lit_soft |
| `ptfx_flipbook_fire1_rgb` | 2048x2048 | DXT1 | 25 | 6 | RGB_soft |
| `ptfx_glow_impact_rgb` | 128x128 | DXT1 | 1 | 6 | RGB_lit |
| `ptfx_ribbon_smoke` | 512x128 | DXT5 | 1 | 5 | RGBA_lit_soft |
| `ptfx_liquid_pour` | 32x128 | DXT5 | 1 | 5 | RGBA_lit |
| `ptfx_water_splash_kick` | 512x1024 | DXT5 | 36 | 5 | RGBA_lit_soft |
| `ptfx_cig_smoke_sheet` | 256x256 | DXT5 | 4 | 5 | RGBA_lit_soft |
| `ptfx_water_wake_blur` | 128x256 | DXT5 | 1 | 4 | RGBA_lit_soft |
| `ptfx_fishes` | 512x512 | DXT5 | 4 | 4 | RGBA_lit_soft |
| `ptfx_water_spike` | 512x512 | DXT5 | 4 | 4 | RGBA_lit_soft |
| `ptfx_bush_twigs` | 128x128 | DXT5 | 4 | 4 | RGBA_lit |
| `ptfx_starbursts_rgb` | 256x256 | DXT1 | 1 | 3 | RGB_soft |
| `ptfx_fire_tail` | 512x512 | DXT1 | 4 | 3 | RGB_soft |
| `ptfx_exp_spark_glows` | 128x128 | DXT5 | 1 | 3 | RGBA_lit_soft |
| `ptfx_bubbles` | 512x512 | DXT5 | 4 | 3 | RGBA_lit_soft |
| `ptfx_muzzle_01` | 256x256 | DXT5 | 2 | 3 | RGB_lit |
| `ptfx_blood_spurt` | 1024x512 | DXT5 | 8 | 3 | RGBA_lit_soft |
| `ptfx_bullet_tacer_heat` | 256x1024 | DXT1 | 1 | 3 | RGB_lit_soft |
| `ptfx_muzzle_core_02` | 1024x1024 | DXT5 | 9 | 2 | RGB_lit |
| `ptfx_steam_anim` | 256x256 | DXT5 | 49 | 2 | RGBA_lit_soft |
| `ptfx_multi_sheet_006_mist` | 256x256 | DXT5 | 1 | 2 | RGBA_lit |
| `_explosion_clown_fireball_rgba` | 1024x1024 | DXT5 | 25 | 2 | RGBA_lit_soft |
| `ptfx_ribbon_candle_flame` | 256x128 | DXT5 | 1 | 2 | RGBA |
| `ptfx_casino_chips` | 128x128 | DXT5 | 4 | 2 | RGBA_lit |
| `ptfx_flower_petals` | 256x256 | DXT5 | 4 | 2 | RGB_lit |
| `ptfx_fine_debris_sheet` | 128x128 | DXT5 | 4 | 2 | RGBA_lit |
| `ptfx_lens_mud_splatter` | 512x512 | DXT1 | 4 | 2 | RGB_lit_screen |
| `ptfx_lens_water_drop` | 256x256 | DXT5 | 4 | 2 | RGB_lit_screen_refract_normalspec |
| `ptfx_glow_flat_rgb` | 512x256 | DXT1 | 1 | 2 | RGB_lit_soft |
| `ptfx_smoke_loop` | 512x512 | DXT5 | 1 | 2 | RGBA_lit_soft |
| `ptfx_flare` | 512x1024 | DXT5 | 4 | 1 | RGB_lit_soft |
| `ptfx_lens_water_drop_blurry` | 256x256 | DXT5 | 1 | 1 | RGB_lit_screen_refract_normalspec |
| `ptfx_afterburner_rings_rgb` | 256x256 | DXT1 | 1 | 1 | RGB_lit |
| `ptfx_snow_flake` | 256x256 | DXT5 | 1 | 1 | RGBA |
| `ptfx_model_multi_objects_02` | 256x256 | DXT5 | 1 | 1 | RGB_lit |
| `ptfx_noodles` | 64x64 | DXT5 | 4 | 1 | RGBA_lit |
| `ptfx_blood_squibs` | 512x256 | DXT5 | 8 | 1 | RGBA_lit_soft |
| `ptfx_bullet_tracer_rg` | 128x256 | DXT5 | 3 | 1 | RGBA_soft |
| `ptfx_palm_fronds` | 64x64 | DXT5 | 2 | 1 | RGBA_lit |
| `ptfx_ribbon_solid_liquid` | 256x64 | DXT5 | 1 | 1 | RGBA_lit |
| `ptfx_lens_snow_drop` | 256x256 | DXT5 | 1 | 1 | RGBA_lit_screen |
| `ptfx_firework_flare` | 128x128 | DXT1 | 1 | 1 | RGB_lit |
| `ptfx_ribbon_fire` | 512x128 | DXT5 | 1 | 1 | RGBA_lit |
| `ptfx_fire_v3` | 2048x2048 | DXT1 | 49 | 1 | RGB_lit_soft |
| `ptfx_star_rgb` | 32x32 | DXT1 | 1 | 1 | RGB_soft |
| `ptfx_water_splashes_sheet_c` | 256x256 | DXT5 | 4 | 1 | RGBA_lit |
| `ptfx_model_multi_objects_05` | 256x256 | DXT5 | 4 | 1 | RGBA_lit |
| `ptfx_model_metal_panel` | 128x64 | DXT1 | 1 | 0 |  |
| `ptfx_model_multi_objects_04` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_heathaze_n` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_multi_sheet_004_debris_s` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_gloop_n` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_afterburner` | 128x128 | DXT5 | 1 | 0 |  |
| `ptfx_model_banknote` | 256x256 | DXT5 | 1 | 0 |  |
| `ptfx_muz_distortion_n` | 512x512 | DXT5 | 1 | 0 |  |
| `ptfx_model_pine_cone` | 128x128 | DXT1 | 1 | 0 |  |
| `ptfx_model_shell_ends` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_coins_leaves` | 256x256 | DXT5 | 1 | 0 |  |
| `ptfx_lens_water_running_n` | 1024x1024 | DXT1 | 1 | 0 |  |
| `ptfx_model_feather` | 256x256 | DXT5 | 1 | 0 |  |
| `ptfx_lens_water_drop_n` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_shotgun_shell` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_pistol_shell` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_lens_water_drop_blurry_n` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_snow` | 128x128 | DXT1 | 1 | 0 |  |
| `ptfx_model_paper_torn` | 256x256 | DXT5 | 1 | 0 |  |
| `ptfx_model_multi_objects_01` | 256x256 | DXT1 | 1 | 0 |  |
| `ptfx_model_glass_shard1` | 128x128 | DXT5 | 1 | 0 |  |
