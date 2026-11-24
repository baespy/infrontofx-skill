# Poly Haven CC0: Texture PBR และ HDRI พรีวิวสำหรับ map-forge

ดึง texture PBR ฟรี CC0 จาก Poly Haven มาทำผิว **World-Scale Tiled PBR** ของแมพ (`normal_spec.sps`) ด้วย `scripts/blender/fetch_polyhaven.py` ซึ่งรันบน Python ของ Blender 4.2.3 เอง (stdlib `urllib` ล้วน ไม่ต้องลง add-on ไม่ต้องใช้ MCP ตัวที่สอง และไม่เปิด socket) เงื่อนไข license, ToS และตัวเลขทุกตัวในไฟล์นี้ตรวจกับ API และหน้าเว็บจริงเมื่อ **2026-11-24**

## 1. Poly Haven คืออะไร และ map-forge ใช้ส่วนไหน

- คลัง HDRI, texture และโมเดล 3D ฟรี ทุกชิ้นเป็น **CC0** และทำโดยคน ไม่ใช้ generative AI (ตาม `llms.txt` ของเว็บ)
- มี public API ที่ `https://api.polyhaven.com` ไม่ต้องมี key ไม่ต้องสมัคร ไฟล์จริงเสิร์ฟจาก `https://dl.polyhaven.org`
- ณ 2026-11-24 มี texture **871 ชุด** ในนั้น **634 ชุด** มีขนาดจริง 1.5–4 m (ด้านสั้น ≥ 1.5 m และด้านยาว ≤ 4 m) และ **349 ชุด** ในกลุ่มนี้ติด `surface_use` เป็น `floor`, `paving` หรือ `ground`
- map-forge ใช้แค่ 2 อย่าง: **texture PBR** (ship ลง Shared `.ytd`) และ **HDRI** (ส่องไฟพรีวิวใน Blender เท่านั้น) ส่วนโมเดล 3D สคริปต์ปฏิเสธ เพราะ map-forge ตกแต่งด้วย prop แท้ GTA V ตามกฎทองข้อ 1

| Endpoint | สคริปต์ใช้ทำอะไร | Cache ของสคริปต์ |
| --- | --- | --- |
| `/assets?type=textures` (+ `category`, attribute) | รายการ asset + metadata ทั้งหมดในครั้งเดียว | 12 ชม. |
| `/search?q=...&t=textures` | ค้นแบบ semantic + keyword (API ระบุว่าค้นได้ทุกภาษา) เรียงตามความเกี่ยวข้อง | 12 ชม. |
| `/taxonomy/textures`, `/taxonomy/hdris` | ต้นไม้ category และค่าที่ใช้กรองได้ของแต่ละ attribute | 12 ชม. |
| `/info/<id>` | ขนาดจริง (`dimensions` เป็นมม.), category, authors | ถามสดทุกครั้ง |
| `/files/<id>` | URL, ขนาดไฟล์, md5 แยกตาม map, ความละเอียด และ format | ถามสดทุกครั้ง |

## 2. License ของ asset และเงื่อนไขการใช้ API (ตรวจสด 2026-11-24)

### 2.1 ตัว asset เป็น CC0 (หน้า `https://polyhaven.com/license`)

- ทุก asset เป็น CC0 มีผลเท่ากับ public domain แม้ในประเทศที่กฎหมายไม่รองรับ public domain
- **ใช้ได้ทุกวัตถุประสงค์ รวมงานเชิงพาณิชย์** (เซิร์ฟเวอร์ที่มีรายได้หรือรับโดเนทก็ใช้ได้)
- **ไม่ต้องให้เครดิต** (เขาแค่ยินดีถ้าให้) แจกต่อได้ รวมไว้ในงานของเราได้ รวมในสินค้าที่ขายก็ได้ จึงฝังลง `.ytd` ของแมพที่แจกหรือขายได้เลย
- คำขอ (ไม่บังคับ): ถ้าได้ประโยชน์ทางการเงินหรือใช้บ่อย ให้พิจารณาสนับสนุนผ่าน Patreon
- ข้อควรระวัง: โลโก้ ข้อความ และรูปตัวอย่างบนเว็บ (asset example renders) **ไม่ใช่** CC0 (Website ToS ข้อ 4) ใช้ได้เฉพาะไฟล์ asset ที่ดาวน์โหลด

### 2.2 API Terms of Service (`ToS.md` ใน repo `Poly-Haven/Public-API` ลิงก์เดียวกับ header `terms-of-service` ที่ API ตอบกลับมา)

| ข้อ | ใจความ | สคริปต์ทำอย่างไร |
| --- | --- | --- |
| 2.1–2.3 | API ฟรีสำหรับทุกคนทุกวัตถุประสงค์ รวมเชิงพาณิชย์และหารายได้ ไม่มีวันเรียกเงิน ไลเซนส์ หรือ key | ไม่มี key ไม่มีบัญชี |
| 2.4 | ทุก call **ต้อง** ส่ง User-Agent หรือ Referer ที่ไม่ซ้ำและตรงกับชื่อซอฟต์แวร์ เพื่อให้เขารวม request ของแอปเดียวกันได้ | ส่ง `map-forge-fetch-polyhaven/1.0` ทุก request รวมตอนดาวน์โหลดไฟล์ ไม่มีชื่อคน อีเมล ชื่อเซิร์ฟเวอร์ ชื่อเครื่อง หรือ URL repo และไม่มี flag ให้แก้ |
| 2.5 | เครดิตบังคับ **เฉพาะ** การใช้ live API แสดงเนื้อหาให้ผู้ใช้เห็น ทำเป็น label เมนู ปุ่มที่ระบุชื่อ Poly Haven หรือข้อความ "Powered by Poly Haven" ต้องเบา และห้ามสื่อว่าผลงานเราเป็นของหรือได้รับการรับรองจาก Poly Haven ส่วน asset ที่ดาวน์โหลดแล้วไม่ต้องเครดิตเลยตลอดไป | ทุกคำสั่งที่เรียก API พิมพ์บรรทัดเครดิตที่ขึ้นต้น `Poly Haven (https://polyhaven.com)` และลิงก์หน้า asset ทุกแถว |
| 2.6 | ห้ามใช้งานที่รบกวนหรือทำให้ API ช้าลง (DoS, spam, ใช้ในทางร้าย) | cache, backoff, ดาวน์โหลดทีละไฟล์ (ดูหัวข้อ 2.3 ด้านล่าง) |
| 2.7 | บริษัทที่พึ่ง API ใน production เลือกสนับสนุนเงินได้ ไม่บังคับ | - |
| 3 | Poly Haven ถือสิทธิ์ในตัว API ข้อมูล และเนื้อหา (ตัว asset ยังเป็น CC0) | - |
| 4 | เปลี่ยน ระงับ หรือปิด API ได้โดยไม่แจ้ง ไม่มี uptime guarantee | endpoint เปลี่ยนเมื่อไรสคริปต์จะจบด้วย `POLYHAVEN_FAIL` ไม่เดาต่อ |
| 7–8 | ใช้กฎหมายแอฟริกาใต้ และแก้ ToS ได้ทุกเมื่อ | เปิดลิงก์ ToS ตรวจใหม่ก่อนเผยแพร่ skill รอบถัดไป |
| Website ToS 3.2 | ห้าม web scraping หรือ data mining เว็บโดยไม่ได้รับอนุญาต ให้ใช้ API แทน | อ่านเฉพาะ JSON จาก API ไม่แตะ HTML |
| หน้า `our-api` | ถ้าฝัง API ไว้ในเครื่องมือฝั่งผู้ใช้ เขาขอให้ติดต่อแจ้ง (เป็นคำขอ ไม่ใช่เงื่อนไข) | ทางเลือกตอนเผยแพร่ skill สาธารณะ |

### 2.3 มารยาทเรื่องความถี่ (Rate Etiquette)

- ToS และ spec ไม่ได้ประกาศตัวเลข rate limit ของ endpoint หลักหรือการดาวน์โหลดไฟล์ และ endpoint ของ API ที่ตรวจไม่ส่ง header rate-limit กลับมา
- spec OpenAPI 1.0.0 ระบุว่า `/search` ตอบ **429** พร้อม `Retry-After` เมื่อถี่เกิน ตอบ **503** แปลว่าให้ไปจับคำเอง ให้ส่ง `q` แบบตัดช่องว่างและเป็นตัวพิมพ์เล็กเพื่อใช้ cache ร่วมกัน และ `/v2/search` จำกัด 150 ครั้งต่อนาทีต่อ IP
- `/assets`, `/search`, `/info`, `/files` ตอบ `Cache-Control: max-age=43200` (12 ชม.) และส่ง JSON แบบ gzip ได้
- สิ่งที่สคริปต์ทำให้อัตโนมัติ:
  - เก็บ cache `/assets`, `/taxonomy`, `/search` 12 ชม. ไว้ที่ `work\<map>\source\polyhaven\.cache` (ถ้าไม่ใส่ `--work` จะเก็บใน temp ของระบบ) ส่วน `/info` กับ `/files` ถามสดเพื่อให้ md5 เป็นค่าล่าสุด
  - ขอ JSON แบบ gzip และลองใหม่สูงสุด 3 ครั้งเมื่อเจอ 429/5xx หรือ timeout โดยรอตาม `Retry-After` (สูงสุด 60 วินาที) หรือ 2/4/6 วินาที ส่วน `/search` ลองใหม่เฉพาะ 429 ถ้าเจอ 503 จะจับคำในชื่อ tag และ category เอง
  - ดาวน์โหลดทีละไฟล์ (ชิ้นละ 1 MiB) ตรวจ md5 ระหว่างเขียน ไม่ตรงลบทิ้งทันที ไฟล์เดิมที่ md5 ตรงจะไม่โหลดซ้ำ
  - ปฏิเสธ URL ที่ไม่ใช่ `https` หรือไม่ใช่โดเมน `polyhaven.com`/`polyhaven.org` รวมถึงหลัง redirect
- อย่าเขียนลูปดึงทั้งคลัง เลือก 6–10 ชุดต่อแมพก็พอ (งบ VRAM ในหัวข้อ 6)

## 3. เลือก texture ให้เข้ากับ World-Scale Tiled PBR

**หลักใหญ่: 1 UV = ขนาดจริงของ scan** (`dimensions` ใน API แสดงเป็นช่อง `size_m`) และต้องอยู่ช่วง **1.5–4 m** (ช่อง `1.5-4m` = `ok`) แล้วตั้ง `"UVMap 0"` ให้ 1 หน่วย UV เท่ากับ `tile_m` ใน manifest ทั้งสองแกน

- scan เล็กกว่า 1.5 m (เช่น `brown_planks_03` 1.00 m, `corrugated_iron` 1.12 m) จะเห็นลายซ้ำเป็นตารางทุกเมตรบนลาน 60–120 m และถ้ายืด UV ให้ใหญ่ขึ้นแผ่นไม้หรือลอนเหล็กจะโตผิดสัดส่วน ใช้ได้กับชิ้นเล็กหรือผนังสั้นเท่านั้น
- scan ใหญ่กว่า 4 m (ภาพถ่าย aerial เช่น `aerial_asphalt_01` 30 m) ได้ px/m ต่ำเกินไปสำหรับพื้นเดิน
- ขนาดภาพตามระดับใน `references/studio-benchmarks.md`:

| ระดับ | ขนาด | ใช้กับ |
| --- | --- | --- |
| Primary Architectural Tiled | `512x512` | หินปูพื้น ไม้ระแนง คอนกรีตสถาปัตย์ หินอ่อน หญ้า |
| Secondary Tiled | `256x256` | ดินกระบะ ปูนฉาบ หลังคา ขอบถนน และ Normal/Spec เสริม |
| Hero Surface | `1024x1024` สูงสุด | พื้นฮีโร่กลางลานเท่านั้น ไม่เกิน 1–3 ใบต่อแมพ |

- เป้า texel density: พื้นทางเดิน **200–340 px/m** (`512` คลุม 1.5–2.5 m), ผนัง/เสา `512` คลุม 1.5–3 m คำนวณง่ายๆ ว่า px/m = ขนาดภาพ ÷ ขนาดจริง

| ขนาดจริงของ scan | ที่ `512` px | ที่ `1024` px | เหมาะกับ |
| --- | --- | --- | --- |
| 1.5 m | 341 px/m | 683 px/m | พื้นเดินระยะประชิด |
| 2.0 m | 256 px/m | 512 px/m | พื้นลานหลัก (ขนาดที่พบบ่อยที่สุดในคลัง 239 จาก 871 ชุด) |
| 2.5 m | 205 px/m | 410 px/m | พื้นลานกว้าง |
| 3.0 m | 171 px/m | 341 px/m | ผนัง เสา หรือพื้นฮีโร่ที่ `1024` |
| 4.0 m | 128 px/m | 256 px/m | ผนังสูง ดิน หรือพื้นไกล |

- กรองให้ตรงงานก่อนดูทีละชุด: `--attr surface_use=floor` (หรือ `paving`, `ground`, `wall`, `roof`), `--attr setting=outdoor`, `--attr condition=worn,weathered` (หลายค่าใน key เดียวคือ OR และต่าง key คือ AND), `--category stone/cobblestone-paving` (ใช้ slug path จากคำสั่ง `categories` ครอบลูกทั้งหมด) และ `--min-m 1.5 --max-m 4`
- `/search` คืนผลที่ใกล้ที่สุดเสมอแม้ไม่มีของที่ตรง ให้ดูช่อง `size_m`, `use` และ `category` ประกอบทุกครั้ง
- ลานกว้างควรเลือก `condition` แบบ `clean` หรือ `worn` ที่ลายสม่ำเสมอ ชุดที่มีรอยแตกหรือคราบเด่นจุดเดียว (`cracked`, `damaged`) จะฟ้องการซ้ำลายบนพื้นที่ใหญ่ ให้เก็บไว้ใช้ในโซนเล็ก
- ตัวอย่างผล `list --query "concrete floor" --min-m 1.5 --max-m 4` จาก API จริง:

```text
id                      size_m     1.5-4m  px/m@512  use    setting  condition                       category
concrete_floor          2.08x2.08  ok      246       floor  outdoor  weathered,worn                  Concrete/Cast Walls & Floors/Bare Cast
concrete_floor_worn_02  2.00x2.00  ok      256       floor  outdoor  weathered,cracked,damaged,worn  Concrete/Cast Walls & Floors/Bare Cast
concrete_floor_01       2.00x2.00  ok      256       floor  outdoor  weathered,worn                  Concrete/Cast Walls & Floors/Exposed Aggregate
```

- **Spec class อัตโนมัติจาก category** (แก้เองได้ด้วย `--spec-class`):

| category ขึ้นต้นด้วย | spec class | ช่วงค่า `_s.png` |
| --- | --- | --- |
| `Metal/` | `metal` (ถ้ามี map `Metal` ฐานเป็น `matte` แล้วใช้ mask ดันจุดโลหะขึ้นช่วงโลหะ ถ้าไม่มีถือเป็นโลหะทาสี ใช้ `varnish`) | 0.65–0.90 |
| `Ceramic/Glazed`, `Ceramic/Terrazzo`, `Stone/Slabs & Tiles/Marble`, `.../Polished`, `.../Granite` | `glazed` | 0.45–0.70 |
| `Wood/Boards & Planks/Finished`, `.../Parquet`, `.../Painted`, `Wood/Veneer`, `Wood/Engineered Wood/Laminate`, `Plastic & Rubber/Plastic`, `.../Vinyl` | `varnish` | 0.25–0.45 |
| อื่นๆ ทั้งหมด (คอนกรีต อิฐ ดิน หิน ไม้ผุ ผ้า) | `matte` | 0.12–0.28 |

## 4. แปลงให้เป็นสิ่งที่ shader GTA V ต้องการ (`normal_spec.sps`)

| map ของ Poly Haven | สคริปต์ทำอะไร | ไฟล์ที่ได้ใน `build/textures` | Sampler |
| --- | --- | --- | --- |
| `Diffuse` (sRGB) | คูณ AO ใน linear light (`--ao-strength 0.42`), กดสีจุดโลหะลง 35% (`--metal-darken 0.35`), ย่อ pow2 | `<stem>.png` | `DiffuseSampler` |
| `nor_gl` (OpenGL `+Y`) | ย่อแบบเฉลี่ยเวกเตอร์แล้ว normalize ใหม่ **เก็บเป็น OpenGL** | `<stem>_n.png` | `BumpSampler` |
| `nor_dx` | ใช้เฉพาะเมื่อไม่มี `nor_gl` และกลับเป็น OpenGL ก่อนเขียน PNG | `<stem>_n.png` | `BumpSampler` |
| `Rough` (หรือช่อง G ของ `arm`) | gloss = 1 − rough แล้ว map เข้าช่วงของ spec class | `<stem>_s.png` (grayscale) | `SpecSampler` |
| `AO` (หรือช่อง R ของ `arm`) | คูณลง Diffuse (AO ก้อนใหญ่ยังใช้ Vertex Color `Color 1` ตาม `references/shaders-lighting-vcol.md`) | - | - |
| `Metal` (หรือช่อง B ของ `arm` ถ้ามีค่า > 0.02) | mask จุดโลหะ | - | - |
| `Displacement`, `Bump`, `spec`, `spec_ior`, `anisotropy_*`, `blend`, `gltf`, `mtlx` | ไม่โหลด (`normal_spec.sps` ไม่มีช่อง height และ map-forge คุมค่า spec จาก roughness ให้อยู่ช่วงเดียวกันทุกชุด) | - | - |

- **Normal (DirectX `-Y`):** RAGE ใช้ DirectX แต่ `_n.png` ต้องเป็น **OpenGL** เพราะ `scripts/blender/export_map.py` กลับช่องเขียว `G = 1.0 - G` ให้ทุกไฟล์ที่ชื่อลงท้าย `_n.png` ตอนเข้ารหัส DDS (`references/pipeline.md` ข้อ 2) และ Normal Map node ของ Blender ก็ต้องการ OpenGL อยู่แล้ว ห้ามเอา `nor_dx` มาตั้งชื่อเป็น `_n.png` เอง ไม่งั้นโดนกลับสองรอบแล้วร่องนูนกลายเป็นบุ๋ม ทดสอบแล้ว: ส่ง `_n.png` จากสคริปต์เข้า encoder ของ `export_map.py` ได้ G = 0.302 จากต้นทาง OpenGL 0.70 คือกลับครั้งเดียวถูกต้อง
- **Roughness เป็น Spec:** `spec = lo + (hi - lo) × (1 - rough)` ตามช่วงของ class ในหัวข้อ 3 (ตรงกับตาราง spec ใน `references/shaders-lighting-vcol.md` ข้อ 3) ไม่มี roughness จะได้ spec เรียบที่ gloss 0.4
- **ค่า material** ที่ต้องตั้งเป็น custom property บน material ใน Blender (สคริปต์เขียนไว้ใน manifest ช่อง `material`):

| Custom property | ค่า |
| --- | --- |
| `map_forge_shader` | `normal_spec.sps` |
| `map_forge_bumpiness` | `1.0` |
| `map_forge_spec_int` | matte `0.15`, varnish `0.30`, glazed `0.45`, metal `0.65` (ใช้ metal เมื่อ mask โลหะคลุม ≥ 50%) |
| `map_forge_spec_falloff` | `25 + 75 × ค่าเฉลี่ย gloss` (อยู่ในช่วง 25–100) |
| `map_forge_spec_fresnel` | matte `0.80`, varnish `0.85`, glazed `0.90`, metal `0.95` |

- **ย่อเป็น pow2:** ด้านยาวเท่า `--size` (128/256/512/1024) ด้านสั้นปัดเป็น pow2 ที่ใกล้สัดส่วนจริง ไม่ขยายเกินภาพต้นทาง ใช้ area filter โดย Diffuse เฉลี่ยใน linear light (sRGB จริง), Normal เฉลี่ยเวกเตอร์แล้ว normalize, Spec/AO/Metal เฉลี่ยตรงๆ ค่าเริ่มต้น Diffuse `512`, Normal `min(size, 512)`, Spec `min(size, 256)` ถ้าสัดส่วนเปลี่ยนเกิน 3% หรือสัดส่วนพิกเซลไม่ตรงกับขนาดจริง (เช่น `beige_wall_002` เป็น 32767x8192 px แต่ระบุ 3x3 m) สคริปต์จะขึ้น `note` ให้ตรวจหน้า asset
- **ความละเอียดและ format ที่โหลด:** ป้ายความละเอียดของ Poly Haven นับตาม **ความกว้าง** (`japanese_cedar_bark` สูงสุด 8192x16384 ป้าย `1k` คือ 1024x2048) ค่าเริ่ม `--res 1k` แบบ `jpg` พอสำหรับผลลัพธ์ `512` (มีพิกเซลเกิน 2 เท่าให้ย่อ) ใช้ `--res 2k` เมื่อทำ `--size 1024` ส่วน `--format png` เป็น 16-bit lossless แต่ใหญ่กว่า jpg หลายเท่า (`bi_stretch` Diffuse 1k: jpg 0.63 MB, png 5.6 MB) ทั้งที่ปลายทางเป็น DXT1 อยู่ดี

## 5. DXT1/DXT5 และ mip เต็มชุด

| ขนาด | DXT1 + mip เต็มชุด | DXT5 + mip เต็มชุด |
| --- | --- | --- |
| `1024x1024` | 682.7 KiB | 1365.4 KiB |
| `512x512` | 170.7 KiB | 341.4 KiB |
| `256x256` | 42.7 KiB | 85.4 KiB |
| `128x128` | 10.7 KiB | 21.4 KiB |

- ผิวทึบทุกช่อง (Diffuse, Normal, Spec) ใช้ **DXT1 (BC1, 4 bpp)** ชุดค่าเริ่มต้น 512/512/256 กิน **384 KiB** ต่อชุด
- **DXT5 (BC3, 8 bpp)** ใช้เฉพาะแผ่นที่โปร่งใสจริง (`decal`, `cutout`, `glass_env`, `emissive_alpha`) texture PBR ของ Poly Haven ทึบทั้งหมด สคริปต์จึงเขียน DXT1 เสมอ ถ้า Diffuse มี alpha จะขึ้น `note` ให้ไปทำเป็น `cutout.sps`/`decal.sps` ผ่าน `export_map.py` (ฝั่งนั้นเลือก DXT5 ให้เมื่อเจอ alpha) และหมวด Glass ต้องใช้ `glass_env.sps` ไม่ใช่เส้นทางนี้
- **mip ต้องครบถึง 1x1** (`512` = 10 ชั้น, `256` = 9 ชั้น) ไม่มี mip ภาพไกลจะกระพริบเป็นลายมัวเร คู่กับ `hdTextureDist = lodDist` ใน `.ytyp` ตาม `references/pipeline.md` ข้อ 2 เพื่อไม่ให้เกมลด mip จนเบลอ
- `--dds` เขียน `<stem>.dds`, `<stem>_n.dds`, `<stem>_s.dds` ข้าง PNG ด้วยตัวเข้ารหัส PCA DXT1 และตัวเขียน header ของ `scripts/blender/dds_codec.py` แต่สร้าง mip ตามชนิดของ map: Diffuse เฉลี่ยใน linear light + unsharp เบาๆ ที่ mip 1–3 แบบเดียวกับ codec, Normal เฉลี่ยเวกเตอร์ + normalize + กลับเป็น DirectX `-Y`, Spec เฉลี่ยตรงๆ ทดสอบด้วย normal ลายเส้นสลับ ±X แล้ว mip 2 ได้ normal ตั้งตรง (R 0.516 ซึ่งเป็นค่า RGB565 ที่ใกล้ 0.5 ที่สุด, B 1.0) ขณะที่ทาง gamma-space เดิมได้ R 0.645, B 0.903 คือเอียงราว 20 องศาและไม่ normalize
- `export_map.py` เข้ารหัส PNG ทุกไฟล์ใน `--textures` ใหม่ทุกครั้งและเขียนทับ `.dds` ชื่อเดียวกัน ดังนั้น `--dds` มีไว้เช็ก VRAM/หน้าตา หรือแพ็ก `.ytd` เองด้วยมือ (เช่นเพิ่มเข้า `.ytd` เดิมใน CodeWalker) ไฟล์ที่ ship จริงมาจาก `export_map.py`

## 6. รวมลง Shared `.ytd`

1. สคริปต์วาง PNG ไว้ที่ `work\<map>\build\textures\` ซึ่งเป็นโฟลเดอร์เดียวกับที่ส่งให้ `export_map.py --textures`
2. ใน Blender ตั้ง material ของชิ้นที่ใช้ผิวนี้: Image Texture node ชื่อ **`DiffuseSampler`**, **`BumpSampler`**, **`SpecSampler`** ชี้ไป `<stem>.png`, `<stem>_n.png`, `<stem>_s.png` (Diffuse เป็น sRGB, อีกสองช่องเป็น Non-Color) ใส่ custom property จากช่อง `material` ใน manifest และ unwrap `"UVMap 0"` ให้ 1 หน่วย = `tile_m` เมตร
3. รัน `export_map.py` (ไม่ใส่ `--factory-startup`) ระบบจะเข้ารหัส DXT1 + mip แล้วรวมทุกช่องลง `<shared_ytd>.ytd` ไฟล์เดียว และตั้ง `embedded = False` ในทุก `.ydr`
4. ตรวจ VRAM, mip และ format ด้วย `scripts/blender/inspect_map.py` จนผ่าน `MAP_INSPECT_PASS fail=0`

**เพดานขนาดของ `export_map.py`** (ตั้งใน `texture_rules` ของ `map-spec.json` ดู `templates/map-spec.example.json`):

| กฎ | ค่าเมื่อไม่ตั้ง | ผลกับ texture จาก Poly Haven |
| --- | --- | --- |
| `default_diffuse_max_res` | `512` | Diffuse `1024` จะถูกย่อเหลือ `512` |
| `hero_diffuse_max_res` + `hero_prefixes` | `1024` + `logo_`, `sign_`, `brand_` | พื้นฮีโร่ `1024` ต้องเพิ่ม prefix เช่น `hero_` ลงใน `hero_prefixes` แล้วรันด้วย `--name hero_<ชื่อ>` |
| `normal_max_res` / `spec_max_res` | `256` (เทมเพลตตั้ง `512`) | Normal `512` จะถูกย่อเหลือ `256` ถ้า `map-spec.json` ไม่ได้ตั้งกฎนี้ (ทดสอบแล้วทั้งสองแบบ) |
| `swatch_prefixes` | `swatch_`, `trim_` → `32` px | ห้ามตั้งชื่อผิว tile ขึ้นต้นแบบนี้ |

- ชื่อ texture เป็น `[a-z0-9_]` ไม่เกิน 48 ตัว ไม่ซ้ำกันใน `.ytd` เดียว และชื่อ Diffuse **ห้ามลงท้าย `_n` หรือ `_s`** เพราะ `export_map.py` จะอ่านเป็น Normal/Spec (สคริปต์ปฏิเสธชื่อแบบนี้ให้)
- texture ชุดเดียวใช้ได้กับทุก `.ydr` ใน `.ytd` เดียวกันและนับ VRAM ครั้งเดียว งบ Shared `.ytd` 0.6–5 MB รับได้ราว 6–10 ชุดที่ 384 KiB (2.3–3.8 MB) สีเรียบ ขอบเหล็ก และ trim ยังใช้ micro-swatch `4x4`–`32x32` เหมือนเดิม

## 7. HDRI: ใช้พรีวิวใน Blender เท่านั้น ห้าม ship

- HDRI คือภาพสภาพแวดล้อม 360° แบบ HDR ใช้ส่องไฟและเป็นฉากหลังให้ภาพเรนเดอร์ look-dev ใน Blender (EEVEE/Cycles) เพื่อดูวัสดุและทำ Visual QA 6 มุมตาม `references/antigravity.md` ภายใต้แสงกลางวันที่ใกล้เกม
- **ไม่ ship ลงเกม:** GTA V ไม่ใช้ไฟล์ HDRI ส่องแมพ ท้องฟ้าและแดดมาจาก timecycle/weather ส่วนแสงในแมพมาจาก Vertex Color `Color 1` และ `Drawable.lights` ไฟล์ `.hdr`/`.exr` ไม่ใช่ format texture ของ GTA และกินพื้นที่ 1.4–20 MB เปล่าๆ
- สคริปต์โหลด HDRI ไว้ที่ `work\<map>\preview\hdri\` เท่านั้น และจดใน manifest ช่อง `hdris` เป็น `ship: false` ห้ามคัดลอกเข้า `build\textures`, `stream` หรือ `.ytd`
- เลือก: `--attr time_of_day=midday --attr weather=clear` สำหรับ QA กลางวัน และ `sunset`/`dusk` สำหรับดูโทนเย็น (แสงกลางคืนในเกมจริงยังมาจาก vcol ช่อง G + `Drawable.lights`) ความละเอียด `1k` (~1.4–1.6 MB) พอสำหรับส่องไฟ ค่าเริ่ม `2k` (~5–6 MB) เหมาะเมื่อเห็นฉากหลังในภาพ ใช้ `.hdr` เป็นหลัก `.exr` เมื่อจำเป็น
- ต่อใน Blender: World → Environment Texture (โหลด `.hdr` ปล่อย color space ตามที่โหลดมา) → Background → World Output และไม่ต้อง pack ภาพลง `.blend`

## 8. คำสั่ง

สคริปต์นี้รันด้วย `--factory-startup` ได้เพราะไม่ต้องใช้ Sollumz (ต่างจาก `export_map.py`) และคำสั่ง `list`, `categories`, `fetch --dry-run` รันด้วย Python ธรรมดาที่มี numpy ก็ได้ แต่การแปลงภาพ (`fetch` จริงและ `convert`) ต้องรันใน Blender

ตั้งตัวแปร:

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
$skill   = '<project>\.claude\skills\infrontofx\map-forge'
$ph      = "$skill\scripts\blender\fetch_polyhaven.py"
```

ดู category และค่าที่ใช้กรองได้ ค้นหา และดูแผนแบบ metadata ล้วน (agent รันเองได้):

```powershell
& $blender -b --factory-startup -P $ph -- categories --kind textures --depth 2
& $blender -b --factory-startup -P $ph -- list --query "concrete floor" --attr surface_use=floor --min-m 1.5 --max-m 4 --limit 15 --work work\my_map
& $blender -b --factory-startup -P $ph -- list --category stone/cobblestone-paving --attr setting=outdoor --min-m 1.5 --max-m 4 --work work\my_map
& $blender -b --factory-startup -P $ph -- fetch --id concrete_floor_worn_02 --dry-run --work work\my_map
& $blender -b --factory-startup -P $ph -- list --kind hdris --attr time_of_day=midday --attr weather=clear --limit 10 --work work\my_map
& $blender -b --factory-startup -P $ph -- fetch --id kloofendal_48d_partly_cloudy_puresky --dry-run --work work\my_map
```

ดาวน์โหลดและแปลง (เจ้าของงานเป็นคนรันเอง ดูหัวข้อ 9 และพื้นฮีโร่ `1024` ต้องเพิ่ม `hero_` ลงใน `hero_prefixes` ก่อน ดูหัวข้อ 6):

```powershell
& $blender -b --factory-startup -P $ph -- fetch --id concrete_floor_worn_02 --work work\my_map --dds
& $blender -b --factory-startup -P $ph -- fetch --id stone_floor --work work\my_map --size 1024 --res 2k --name hero_stone_floor
& $blender -b --factory-startup -P $ph -- convert --id concrete_floor_worn_02 --work work\my_map
& $blender -b --factory-startup -P $ph -- fetch --id kloofendal_48d_partly_cloudy_puresky --res 2k --work work\my_map
```

| Flag | ค่าเริ่ม | ใช้กับ | ความหมาย |
| --- | --- | --- | --- |
| `--work` | - | ทุกคำสั่ง | โฟลเดอร์แมพ เช่น `work\my_map` (บังคับเมื่อดาวน์โหลดหรือแปลง) |
| `--kind` | `textures` | `list`, `categories` | `textures` หรือ `hdris` |
| `--query`, `--category`, `--attr`, `--tags` | - | `list` | ค้นหา, กรอง category (slug path), กรอง attribute (`key=v1,v2` ใส่ซ้ำได้), ต้องมีทุก tag ที่ระบุ |
| `--min-m`, `--max-m` | - | `list` | กรองขนาดจริงเป็นเมตร |
| `--limit`, `--depth` | `20`, `2` | `list`, `categories` | จำนวนแถว และความลึกของต้นไม้ category |
| `--id` | - | `fetch`, `convert` | slug ของ asset (`[A-Za-z0-9_-]`) |
| `--res`, `--format` | `1k` + `jpg` (HDRI `2k` + `hdr`) | `fetch` | ความละเอียดและ format ที่จะโหลด ถ้าไม่มีจะเลือกที่ใกล้ที่สุด |
| `--max-mb` | `200` | `fetch` | ไฟล์ใดใหญ่เกินจะหยุดก่อนเริ่มโหลดทุกไฟล์ |
| `--dry-run` | - | `fetch` | ถามแค่ `/info` + `/files` แล้วแสดงแผน ไม่โหลดและไม่เขียนไฟล์ใดเลย |
| `--size`, `--normal-size`, `--spec-size` | `512`, อัตโนมัติ ≤ 512, อัตโนมัติ ≤ 256 | `fetch`, `convert` | ขนาดด้านยาวของผลลัพธ์แต่ละช่อง |
| `--name` | slug | `fetch`, `convert` | ชื่อ texture ใน `.ytd` |
| `--spec-class` | `auto` | `fetch`, `convert` | `matte`, `varnish`, `glazed`, `metal` |
| `--ao-strength`, `--metal-darken` | `0.42`, `0.35` | `fetch`, `convert` | น้ำหนัก AO ใน Diffuse และการกดสีจุดโลหะ (`0` = ปิด) |
| `--tile-m` | `2.0` | `fetch`, `convert` | ขนาดจริงสำรองเมื่อไม่รู้ขนาดของ asset |
| `--dds` | - | `fetch`, `convert` | เขียน DDS DXT1 + mip เต็มชุดข้าง PNG |
| `--src`, `--offline` | - | `convert` | โฟลเดอร์ไฟล์ที่โหลดเอง และไม่ถาม `/info` |

ผลลัพธ์บรรทัดสุดท้าย: `POLYHAVEN_LIST`, `POLYHAVEN_CATEGORIES`, `POLYHAVEN_DRYRUN`, `POLYHAVEN_FETCH_PASS`, `POLYHAVEN_CONVERT_PASS` (exit 0) หรือ `POLYHAVEN_FAIL` (exit 1)

## 9. เจ้าของงานเป็นคนดาวน์โหลดเอง

- agent (Claude/Antigravity) รันได้แค่ `categories`, `list` และ `fetch --dry-run` ซึ่งอ่าน JSON metadata อย่างเดียว ไม่โหลดไฟล์ภาพ แล้วรายงานให้เจ้าของงานดู: id, ขนาดจริง, px/m, ขนาดไฟล์ MB, URL, md5 และ VRAM ที่จะใช้
- การดาวน์โหลดจริง (`fetch` ที่ไม่มี `--dry-run`) **เจ้าของงานเป็นคนสั่งรันเอง** หลังเลือกชุดแล้ว agent ไม่รันแทนจนกว่าเจ้าของจะอนุมัติชัดเจนว่าให้โหลดชุดไหน
- จะโหลดเองจากหน้าเว็บก็ได้: เปิด `https://polyhaven.com/a/<id>` โหลดไฟล์ไปวางที่ `work\<map>\source\polyhaven\<id>\` โดยคงชื่อเดิมของ Poly Haven เช่น `<id>_diff_1k.jpg`, `<id>_nor_gl_1k.jpg`, `<id>_rough_1k.jpg` (มี `_ao_`, `_metal_` หรือ `_arm_` ด้วยก็ได้ รองรับ png และ jpg) แล้วรัน `convert`
- `convert` ไม่โหลดไฟล์ใดเลย ถ้ายังไม่มีข้อมูลชุดนี้ใน manifest จะถาม `/info/<id>` (metadata) เพื่อเอาขนาดจริงและ category ถ้าใส่ `--offline` จะข้ามและใช้ `--tile-m` กับ `--spec-class` แทน

## 10. Manifest แหล่งที่มา

สคริปต์จดทุกชุดลง `work\<map>\source\polyhaven\manifest.json` (path ข้างในเป็น path สัมพัทธ์จาก `--work` จึงไม่มีชื่อผู้ใช้หรือ path เครื่อง ยกเว้นใช้ `--src` ที่อยู่คนละไดรฟ์) ให้เก็บไฟล์นี้ไว้กับต้นฉบับแมพเป็นหลักฐานว่าผิวมาจาก CC0 ไม่ต้องใส่ใน `stream`

| ช่อง | เนื้อหา |
| --- | --- |
| ระดับบน | `source`, `site`, `license` (`CC0-1.0`), `license_url`, `api_terms`, `attribution`, `textures`, `hdris` |
| `asset_id`, `name`, `page`, `credit` | slug, ชื่อ, หน้า asset และบรรทัดเครดิต (ไม่บังคับสำหรับ CC0) |
| `authors`, `category`, `tags`, `dimensions_mm`, `files_hash` | metadata จาก `/info` |
| `downloads` | ต่อไฟล์: `role`, `map`, `res`, `format`, `url`, `md5`, `bytes`, `file` |
| `tile_m`, `uv`, `source_px`, `spec_class`, `metal_share`, `ao_in_diffuse` | ขนาดจริงต่อแกน กฎ UV ขนาดภาพต้นทาง และค่าที่ใช้แปลง |
| `material`, `samplers` | custom property ของ material และ PNG ที่ต้องผูกกับแต่ละ Sampler |
| `outputs` | ต่อช่อง: `file`, `width`, `height`, `px_per_m`, `dxt1_kb` (+ `dds` เมื่อใช้ `--dds`) |
| `vram_kb`, `ship` | VRAM ของชุดเป็น DXT1 + mip และ `true` สำหรับ texture (`false` เสมอสำหรับ HDRI) |
| `fetched_utc` / `converted_utc` | เวลา UTC ที่ดาวน์โหลดหรือแปลง |

## 11. ข้อผิดพลาดที่พบบ่อย & วิธีแก้

| อาการ | สาเหตุ | วิธีแก้ |
| --- | --- | --- |
| ร่องนูนกลับด้านในเกม (นูนเป็นบุ๋ม) | ใช้ `nor_dx` เป็น `_n.png` หรือกลับช่อง G เองก่อน export | ใช้ `_n.png` ที่สคริปต์เขียน (OpenGL) ให้ `export_map.py` กลับครั้งเดียว |
| ลายซ้ำเป็นตารางบนลานกว้าง | scan เล็กกว่า 1.5 m หรือมีรอยเด่นจุดเดียว | เลือกชุดที่ `1.5-4m` = `ok` และ `condition` สม่ำเสมอ แล้วแตกลายด้วย decal หรือ Vertex Color |
| พื้นเบลอเป็นวุ้น | px/m ต่ำกว่า 200 หรือ `export_map.py` ย่อ `1024` เหลือ `512` | ใช้ `--size 1024` + prefix ใน `hero_prefixes` และตั้ง `hdTextureDist = lodDist` |
| พื้นวาวเป็นพลาสติก | spec class ไม่ตรงผิวจริง | ใส่ `--spec-class matte` แล้วแปลงใหม่ |
| `POLYHAVEN_FAIL ... must not end with _n or _s` | ตั้ง `--name` ลงท้าย `_n` หรือ `_s` | เปลี่ยนชื่อ |
| `POLYHAVEN_FAIL ... HTTP 429` | เรียก API ถี่เกินจนลองครบ 3 ครั้ง | เว้นช่วงแล้วรันใหม่ (cache 12 ชม. ช่วยไม่ให้เรียกซ้ำอยู่แล้ว) อย่าวนลูปเรียกหลายชุดติดกัน |
| `POLYHAVEN_FAIL ... md5 mismatch` | ไฟล์เสียระหว่างทาง | รันใหม่ (ไฟล์ที่ไม่ผ่านถูกลบให้แล้ว) |
| `POLYHAVEN_FAIL ... conversion runs inside Blender` | รัน `convert` หรือ `fetch` จริงด้วย Python ธรรมดา | รันผ่าน `blender -b --factory-startup -P` |
| `.ytd` เกินงบ VRAM | ใช้ `1024` หลายชุดหรือ Normal/Spec ใหญ่เกิน | กลับไป `512`/`256` ตั้ง `normal_max_res`/`spec_max_res` เป็น `256` และใช้ micro-swatch กับสีเรียบ |
