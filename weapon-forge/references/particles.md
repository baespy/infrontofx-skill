# Particles

Particle คือสิ่งที่ทำให้สกินหนึ่งดูต่างจากอีกสกิน ให้เวลากับส่วนนี้มากที่สุด ไฟล์นี้ครอบคลุม: เลือกทางทำ, ธีมสำเร็จรูป, ออกแบบเอง, หลักออกแบบ, สิ่งที่พิสูจน์แล้วกับที่ยังไม่ได้พิสูจน์, และ config ฝั่ง Lua โครงสร้างไฟล์ `.ypt`, หน่วยของค่า และ texture ของเกมอยู่ใน `ptfx-format.md`

## เลือกทาง

| ทาง | ใช้เมื่อ | ได้อะไร |
| --- | --- | --- |
| A1. เริ่มจากธีม | มีธีมใกล้เคียงกับชุด (26 ธีม) | Hold/Hit/Kill ครบในคำสั่งเดียว พร้อม screen กับ sound ที่เข้าชุด แล้วแก้ต่อได้ทุกค่า |
| A2. ออกแบบเอง | ชุดมีเอกลักษณ์ที่ธีมไม่มี | `.ypt` ต้นฉบับ ควบคุมสี จังหวะ รูปทรง และ sprite เองทั้งหมด |
| B. เรียก effect ของเกม | ต้องการเร็ว หรือ effect ของเกมตรงโจทย์ (EMP, พลุ, ไฟ) | ไม่มีไฟล์เพิ่ม ปรับได้แค่ `scale` `color` `alpha` |
| C. ศึกษาของที่มีอยู่ | อยากรู้ว่า effect ที่ชอบประกอบจากอะไร | ข้อความสรุป ภาพ preview และภาพ texture ใช้เป็นความรู้เท่านั้น |

ทุกทางผสมกันในสกินเดียวได้ งานขายควรจบที่ A2 เสมอ: เริ่มจากธีมแล้วเปลี่ยนอย่างน้อยหนึ่ง layer เป็นของชุดเอง (sprite จาก `glyph`, sheet ของชุด, หรือภาพของผู้ใช้)

## A1. ธีมสำเร็จรูป

```powershell
scripts\ptfx\ptfx.ps1 themes                                   # รายการธีม
scripts\ptfx\ptfx.ps1 new -Theme inferno -Name emberfang -Out <โฟลเดอร์> -Colors "primary=#ff5a14"
scripts\ptfx\ptfx.ps1 build -Spec <โฟลเดอร์>\emberfang.ptfx.json -Out <weapon_x\stream>
```

`new` เขียน design ที่มี dictionary `<name>_fx` และ effect `<name>_hold` (looped), `<name>_hit`, `<name>_kill` แก้ palette กับ layer ในไฟล์นั้นได้เลย หรือใส่ใน skin spec แล้วให้ `new-skin.ps1` ทำทั้งสาย:

```json
"fx": { "theme": "inferno", "theme_colors": "primary=#ff5a14,accent=#ff2a2a" }
```

เมื่อใส่ `fx.theme` โดยไม่ระบุอย่างอื่น `new-skin.ps1` จะสร้าง design ไว้ที่ `source\ptfx.design.json` (ครั้งเดียว รอบถัดไปใช้ไฟล์เดิมเพื่อไม่ทับที่แก้มือ), build `.ypt`, เติม `Hold`/`Hit`/`Kill` ใน Lua และเลือก preset ของ screen กับ sound ตามตาราง ค่าที่ระบุเองใน `fx.screen` `fx.sound` `fx.hold` `fx.hit` `fx.kill` ชนะค่าของธีมเสมอ ตัวอย่าง: `templates/skin-spec.theme.example.json`

| ธีม | หน้าตา | screen ตี / ฆ่า | sound ตี / ฆ่า |
| --- | --- | --- | --- |
| `inferno` | เปลวไฟเคลื่อนไหว, รอยฟันไฟ, วงไฟรอบศพ | dragon / dragon | blade / dragon_roar |
| `frost` | หิมะ, ผลึกแตก, คลื่นเย็นบนพื้น | frost / shatter | chime / shatter_glass |
| `storm` | สายฟ้าแลบที่อาวุธ, ฟ้าผ่าสองสาย, พื้นร้าว | bolt / bolt | thunder / thunder |
| `holy` | ประกาย, รัศมี, วงรูน, ลำแสง, ปีก, วงแหวนเหนือหัว | gothic / holy_halo | bell / holy_choir |
| `abyss` | เกลียวหมุน, รอยฟันม่วง, วังวนดูดศพ | nebula / nebula | cosmic / cosmic |
| `toxic` | ฟองและไอพิษ, รอยสาด, หัวกะโหลกลอยจากแอ่ง | drip / drip | slime / slime |
| `sakura` | กลีบร่วง, ฟันกากบาท, พายุกลีบ | sakura_slash / sakura_slash | blade / katana_sheathe |
| `cosmos` | กาแล็กซีจิ๋ว, ฝนดาว, วังวนเนบิวลา | nebula / nebula | chime / cosmic |
| `cyber` | บล็อกข้อมูลกะพริบ, โล่หกเหลี่ยม, ภาพแตกดิจิทัล | circuit / cyber_hud | glitch / cyber_blast |
| `kawaii` | หัวใจลอย, ไอคอน 16 แบบ, คอนเฟตตี้ | hearts / hearts | toy / chime |
| `casino` | ดอกไพ่ลอย, โยนไพ่, แจ็กพอตเหรียญ | pixel / holy_halo | coin / coin |
| `blood` | สะเก็ดแดง, รอยฟันเปียก, กากบาทดาบกับพื้นร้าว | gothic / drip | blade / chain_whip |
| `ocean` | ฟองและหยดน้ำ, วงน้ำ, น้ำพุ | bubbles / bubbles | splash / splash |
| `gold` | ประกายทอง, แฟลร์, รัศมี, มงกุฎ, เหรียญ | holy_halo / holy_halo | coin / holy_choir |
| `beast` | สะเก็ดร้อน, รอยกรงเล็บสามเส้น, ขย้ำสองครั้ง | dragon / dragon | blade / dragon_roar |
| `arcane` | อักษรรูนลอย, วงเวทตั้ง, วงเวทสองชั้นหมุนสวนกัน | nebula / holy_halo | chime / cosmic |
| `phantom` | ไอวิญญาณ, ผีตัวเล็กหลุดออก, วิญญาณลอยจากวังวน | gothic / nebula | chime / cosmic |
| `nature` | ใบไม้ร่วง, ลมใบไม้, มันดาลาดอกบัว, สปอร์ | bubbles / sakura_slash | chime / bell |
| `arcade` | บิตพิกเซล, รอยชนการ์ตูน, เหรียญกับคอนเฟตตี้ | pixel / pixel | toy / glitch |
| `oni` | ไฟแดง, ตราโทโมเอะหมุน, ผนึกโทโมเอะกับวงไฟและหัวกะโหลก | oni / oni | oni / oni |
| `lantern` | ดาวกะพริบ 3 จังหวะ, รอยฟันพัดกลีบ, ตราดอกบัวเด้งเปิด, โคมลอยไฟไหวในวงแหวน, กลีบดอกไม้พุ่งจังหวะสอง | holy_halo / sakura_slash | chime / bell |
| `butterfly` | ริบบิ้นสองชั้น (แกนคม + ปลอกฟุ้ง) กับผีเสื้อ, เศษผลึกแตก, เสาแสงปริซึมและฝูงผีเสื้อลอยขึ้น | frost / shatter | chime / shatter_glass |
| `velvet` | ริบบิ้นไหมบานเย็นกับสะเก็ดพิษ, รอยฟันสาดพิษ, ควันดำตัดพื้น + วงไฟเลือดนก + แสงส่องพื้น | gothic / drip | blade / chain_whip |
| `pirate` | ไอหมอกเขียวมรกต, รอยฟันสมอเรือและน้ำเค็ม, วังวนทะเลต้องสาป + สมอ/กะโหลก/เหรียญทอง | bubbles / gothic | splash / thunder |
| `spooky` | ไอม่วงและค้างคาว, ฟักทองและลูกกวาดแตกกระจาย, ตราฟักทองเด้งเปิดพร้อมฝูงค้างคาว | gothic / oni | toy / dragon_roar |
| `sweet` | ลูกกวาด/หัวใจ/ตัว Z ลอยเอื่อย, เกล็ดน้ำตาลและครีมสาด, ตราดอกไม้ + คอนเฟตตี้ + ฟองสบู่ | hearts / hearts | toy / chime |

ทั้ง 26 ธีม build ผ่านและผ่าน lint โดยไม่มี error หรือ warning (ไฟล์ละ 60–490 KB) ดูสูตรเบื้องหลังคีย์เฟรมได้ที่ `references/vfx-weapon-field-study.md`

## A2. ออกแบบเอง

1. `scripts\ptfx\ptfx.ps1 recipes` ดูสูตร layer, รูปทรง sprite และ sheet ที่มี
2. เขียน design ต่อจาก `templates/ptfx-design.example.json` หรือจากไฟล์ที่ `new` สร้าง ตั้ง `dict` เป็นชื่อใหม่ที่ยังไม่มีใน `server-catalog.md`
3. `scripts\ptfx\ptfx.ps1 build -Spec <design.json> -Out <weapon_x\stream>`
4. เปิด `<dict>.preview.png` และ `<dict>.sprites.png` **ทุกครั้ง** (อยู่ใน `source/` เมื่อปลายทางเป็น `stream/`) แก้ design จนจังหวะ สี และสัดส่วนลงตัว
5. เติม `fx.hold` `fx.hit` `fx.kill` ให้ชี้ `dict` กับชื่อจากบรรทัด `callable effect`
6. ให้ผู้ใช้ดูในเกม แล้วปรับจากสิ่งที่เห็นจริง

### อ่านผล build

| บรรทัด | ความหมาย | ต้องทำอะไร |
| --- | --- | --- |
| `RESULT ok` | ไฟล์อ่านกลับได้ครบ ไม่มี pointer หลุด และ lint ไม่มี error | ไปขั้นดูภาพ |
| `RESULT FAILED-lint` | มี `ERROR` อย่างน้อยหนึ่งข้อ | แก้ก่อน ห้ามส่งไฟล์นี้ |
| `ERROR ...` | สิ่งที่จะวาดไม่ออกหรือชนกับเกม: texture ไม่มีอยู่, ขนาดหรือ alpha เป็นศูนย์, ชื่อซ้ำกับ effect ของเกม, เกิน 7 layer, คีย์เฟรมเรียงผิด | แก้ตามข้อความ |
| `WARN ...` | ค่าที่ไม่เคยพบในไฟล์จริงเลย หรือการตั้งค่าที่น่าจะผิด | อ่านทุกข้อ แก้หรืออธิบายได้ว่าตั้งใจ |
| `NOTE ...` | ข้อสังเกตด้านงบและหน้าตา | พิจารณา |
| `LINT fields=N` | จำนวนค่าตัวเลขของไฟล์ที่ถูกเทียบกับช่วงค่าจากไฟล์จริง 183 ไฟล์ | ไม่ต้องทำอะไร |

`RESULT ok` ไม่ได้แปลว่าหน้าตาในเกมถูกต้อง แปลว่าโครงสร้างถูกและทุกค่าอยู่ในช่วงที่ไฟล์จริงใช้

## Design JSON

```json
{
  "dict": "myset_fx",
  "palette": { "core": "#ffffff", "primary": "#ff4a3a", "secondary": "#ff9a2a" },
  "sheets": { "marks": { "grid": "2x2", "cells": ["skull", "bone", "fang", "claw"] } },
  "effects": [
    { "name": "myset_hit", "duration": 0.6, "layers": [
        { "use": "flash", "color": "core", "size": 0.7 },
        { "use": "energy_slash", "color": "core", "color2": "primary" },
        { "use": "shape_burst", "texture": "marks", "color": "secondary", "burst": 10 }
    ] }
  ]
}
```

ระดับ effect: `name` (ชื่อที่ Lua เรียก), `loop` (true = looped สำหรับ `isLoop = true`), `duration` วินาที, `scale` คูณทุก layer, `cullDist` ระยะที่เลิกวาด (ค่าเริ่ม 60 m), `layers` **ไม่เกิน 7**

ระดับ layer: `use` เลือกสูตรแล้วเขียนทับเฉพาะค่าที่อยากเปลี่ยน หรือไม่ใส่ `use` แล้วกำหนดเองทั้งหมด `name` ตั้งชื่อ rule เมื่อใช้สูตรเดียวกันสองครั้งใน effect เดียว

| กลุ่ม | คีย์ | ความหมาย |
| --- | --- | --- |
| เวลา | `start`, `end` | สัดส่วนของ `duration` ที่ layer เริ่มและหยุดปล่อย |
| จำนวน | `burst`, `rate`, `rateOverDist` | `burst` ปล่อยครั้งเดียวเป็นจำนวนชิ้น, `rate` ต่อเนื่องเป็นชิ้น/วินาที, `rateOverDist` ปล่อยตามระยะทางที่มือ/อาวุธขยับ (ชิ้น/เมตร สำหรับเส้น `ribbon_trail`) |
| อายุ | `life` | วินาที `[min, max]` |
| จุดเกิด | `shape`, `radius`, `inner`, `offset` | `sphere` `box` `cylinder` (แกนทรงกระบอกคือ Y), เมตร, `offset` นับจากจุดที่ Lua วาง effect |
| ทิศ | `dir`, `spread`, `distance`, `speed` | `out` `in` `up` `down` `none` หรือเวกเตอร์, `speed` เป็น m/s |
| ฟิสิกส์ | `gravity`, `accel`, `accelKeys`, `drag`, `noise` | `gravity` บวกคือตก ลบคือลอยขึ้น **ในแกนโลก**, `accelKeys` คีย์ความเร่งตามอายุ `[[t, x, y, z], ...]` สำหรับจังหวะลมยกตัวช่วงท้าย, `drag` ยิ่งมากยิ่งหยุดเร็ว |
| การเกาะ | `attach` | 1 = ตามมือไปตลอด, 0 หรือไม่ใส่ = ทิ้งไว้ในโลก (เส้น `trail` ห้ามใส่ `attach` เพื่อให้ลอยค้างตามทางวิ่ง) |
| เส้นริบบิ้น | `trail`, `tessU`, `tessV`, `smoothness`, `trailWrap` | `trail: true` ใช้ shader `ptfx_trail` เชื่อมอนุภาคของ emitter เดียวเป็นเส้นโค้งต่อเนื่อง 1 เส้น (`tessU: 2`, `tessV: 4`, `trailWrap: 1`) |
| ภาพ | `texture`, `sprite`, `blend`, `technique`, `lit`, `frames`, `anim` | ดูหัวข้อ Texture |
| สี | `color`, `color2`, `colorEnd`, `alpha`, `fadeIn`, `fadeOut`, `alphaKeys`, `emissive`, `emissiveKeys` | `color2` สุ่มสีต่อชิ้นระหว่างสองค่า, `colorEnd` สีตอนสิ้นอายุ, `emissiveKeys` สั่นความสว่างตามอายุ `[[t, val], ...]` (เช่น แสงเทียนโคมลอย) |
| ขนาด | `size`, `aspect`, `grow`, `sizeKeys`, `stretch` | `size` กว้างเป็นเมตร, `aspect` = สูง÷กว้าง, `sizeKeys` ตัวคูณตามอายุ `[[t, x], ...]` |
| หมุน | `rot`, `spin` | องศาเริ่มต้น (−180 ถึง 180) และองศาต่อวินาที |
| จัดแนว | `align`, `axis` | `camera` หันหากล้อง, `velocity` ด้านสูงของภาพชี้ตามทิศวิ่ง, `ground` นอนราบในแกนโลก |
| แสง | `light` | `{ "intensity": 2, "range": 2.5, "color": "primary" }` แสงส่องฉากจริง ไฟล์จริงใช้ intensity 0.2–3 กับของเล็ก 15–200 กับระเบิด |

สีใช้ชื่อใน `palette` หรือ `#rrggbb` ทั้งใน layer และใน `sprite`

### Texture

| ค่าใน `texture` | ผล |
| --- | --- |
| ชื่อรูปทรง เช่น `glow` `energy_slash` `magic_circle` | สร้าง sprite ใหม่ฝังในไฟล์ ชื่อ `<dict>_<shape>` ปรับด้วย `sprite: { ... }` |
| ชื่อ sheet (`sheet_*` หรือชื่อใน `sheets` ของ design) | texture หลายเฟรม ดูหัวข้อ Sheet |
| ชื่อ texture ของเกม เช่น `ptfx_smoke_wispy_anim` | อ้างจาก `core.ypt` ของเกม ไม่เพิ่มขนาดไฟล์ รายชื่อและตารางเฟรมอยู่ใน `ptfx-format.md` |
| ชื่อที่ประกาศใน `textures` ของ design | ภาพของผู้ใช้: `{ "name": "x", "file": "art.png", "size": 256 }` |

Sprite ที่สร้างเป็นสีขาวบน alpha แล้วย้อมด้วย `color` ของ layer ถ้าอยากได้หลายสีในภาพเดียวให้อบสีด้วย `sprite.color` (ขอบ) `sprite.mid` (กลาง) `sprite.core` (แกน) แล้วปล่อย `color` ของ layer เป็นขาว

**รูปทรง 82 แบบ** รัน `ptfx.ps1 sprites -Out x.png` เพื่อดูทั้งหมด

| กลุ่ม | รูปทรง |
| --- | --- |
| แสงและพลังงาน | `glow` `disc` `ring` `sparkle` `streak` `comet` `flare` `beam` `nova` `plasma` `fire` `wisp` `smoke` `swirl` `shockwave` `ripple` `impact` `energy_slash` `slash` `bolt` `crack` `ribbon_line` |
| เวทและสัญลักษณ์ | `magic_circle` `rune` `tomoe` `holy_cross` `eye` `sun` `crescent` `star` `burst` `glyph` `lantern` |
| อาวุธและสัตว์ร้าย | `sword` `claw` `fang` `skull` `bone` `bat` `web` `chain` `shuriken` `wing` `wings` `feather` `anchor` |
| ธรรมชาติ | `petal` `leaf` `flower` `sakura` `lotus` `clover` `butterfly` `snowflake` `drop` `bubble` `flame` `paw` |
| น่ารักและเกม | `heart` `note` `cat` `ghost` `crown` `zap` `arrow` `coin` `dice` `card` `spade` `club` `diamond` `pumpkin` `candy` |
| เรขาคณิตและดิจิทัล | `hex` `hexgrid` `triangle` `square` `cross` `shard` `splat` `gear` `glitch` `pixel` |

`glyph` รับตัวอักษรหรือสัญลักษณ์ใดก็ได้จากฟอนต์ในเครื่อง (`text`, `font`) ใช้ทำอักษรคันจิ ตัวเลข หรือโลโก้ตัวอักษรของชุด ฟอนต์เริ่มต้น `Segoe UI Symbol` มีสัญลักษณ์และอักษรรูน แต่ไม่มีอักษรเอเชีย ให้ระบุฟอนต์เอง: ญี่ปุ่น `MS Gothic` หรือ `Yu Gothic`, จีน `Microsoft YaHei`, ไทย `Leelawadee UI` (ทดสอบแล้วทั้งสี่บน Windows Server 2019) ถ้าฟอนต์ไม่มีอักขระนั้นจะได้กล่องสี่เหลี่ยม ให้ดู `.sprites.png` ทุกครั้ง

คีย์ของ `sprite`

| กลุ่ม | คีย์ |
| --- | --- |
| พื้นฐาน | `size` (ยกกำลังสอง 16–2048), `seed`, `rotation`, `aspect`, `fit` |
| รูปทรง | `points`, `inner`, `thickness`, `radius`, `sweep`, `jag`, `branches`, `twist`, `rings`, `detail`, `sharp`, `text`, `font`, `glyphs`, `face`, `slit` |
| สี | `color`, `mid`, `core`, `corePower`, `glow`, `glowStrength`, `hollow`, `softness`, `edgeFade` |
| ตัวแปลงภาพ (ใช้ได้กับทุกรูปทรง) | `erode` 0–1 กัดขอบด้วย noise ให้ดูเป็นพลังงาน, `warp` 0–0.3 บิดรูปให้ดูเป็นธรรมชาติ, `streaks` 0–1 เส้นริ้ว (`streakMode`: `linear` `radial` `ring`, `streakAngle`), `fade` (`top` `bottom` `left` `right` `out` `in`), `toon` 2–4 ระดับสีแบบการ์ตูน, `mirror` (`x` `y` `both`), `kaleido` N ทำสมมาตรหมุน N แฉกจากรูปใดก็ได้ |

ตัวอย่าง: หัวกะโหลกที่ขอบเป็นไฟ `{ "use": "flash", "texture": "skull", "sprite": { "erode": 0.5, "warp": 0.06, "color": "#ff2a00", "core": "#ffe9a8" } }` มันดาลาจากกลีบ `{ "texture": "petal", "sprite": { "kaleido": 8, "size": 256 } }`

### Sheet (texture หลายเฟรม)

Texture ที่ตั้งชื่อใหม่ถูกเกมวาดเป็นเฟรมเดียวเสมอ ทางเดียวที่จะได้หลายเฟรมคือฝัง sheet ของเราไว้ใต้**ชื่อ texture ของเกมที่มีตารางเฟรมอยู่แล้ว** ตัวสร้างทำเรื่องนี้ให้: ประกาศ sheet แล้วใช้ชื่อมันใน `texture` ตัวสร้างจะเลือกชื่อเกมที่ตารางตรงกันและยังว่างให้เอง

```json
"sheets": {
  "marks":  { "grid": "2x2", "cells": ["skull", "bone", "fang", { "shape": "glyph", "text": "鬼", "font": "MS Gothic" }] },
  "myfire": { "grid": "5x5", "size": 512, "loop": 1,
              "flipbook": { "shape": "fire", "color": "deep", "mid": "primary", "core": "hot" },
              "animate": { "phase": [0, 1] } }
}
```

| แบบ | เขียน | ผลกับ layer |
| --- | --- | --- |
| ไอคอนสุ่ม | `cells: [...]` | แต่ละชิ้นได้ภาพสุ่มหนึ่งช่อง ไม่เล่นภาพเคลื่อนไหว |
| ภาพเคลื่อนไหว | `flipbook` + `animate` (+ `loop: 1`) | เล่นวนด้วย `anim` แบบ `loop` ถ้าไม่ใส่ `loop` จะเล่นครั้งเดียวจบพร้อมอายุ |
| ชุดสุ่มจากรูปเดียว | `flipbook` + `animate: { "seed": 1 }` | แต่ละช่องคือรูปเดียวกันคนละ seed (สายฟ้า 4 แบบ, รอยร้าว 4 แบบ) |

ตารางที่ใช้ได้: `2x2` `3x3` `4x4` `5x5` `6x6` `7x7` Dictionary หนึ่งมีได้ 2–5 sheet ต่อตาราง `animate` ไล่ค่าคีย์ใดของ sprite ก็ได้จากเฟรมแรกถึงเฟรมสุดท้าย เช่น `{ "rotation": [0, 90], "erode": [0, 0.9] }` รูปทรง `fire` `plasma` `wisp` `swirl` `ripple` รับ `phase` 0–1 และวนรอบได้เนียน

`anim` ของ layer: `"loop"` เล่นวนที่ 18–28 เฟรมต่อวินาที เริ่มเฟรมสุ่ม, `"once"` เล่นจบพอดีอายุแล้วค้างเฟรมสุดท้าย, `"random"` สุ่มเฟรมใหม่ 15 ครั้งต่อวินาที, `"smoke"` คลี่ช้าตามอายุ (ใช้กับ sheet ควันของเกม) หรือเขียนเป็น `{ "mode": "loop", "fps": [10, 14], "last": 24 }`

**Sheet สำเร็จรูป 22 ชุด** ใช้ชื่อใน `texture` ได้เลย

| ชื่อ | ตาราง | เนื้อหา |
| --- | --- | --- |
| `sheet_fire` | 5x5 วน | เปลวไฟ 25 เฟรม ย้อมได้ทุกสี |
| `sheet_energy` | 5x5 วน | ลูกพลาสมามีเส้นใยไหล |
| `sheet_vortex` | 4x4 วน | เกลียวที่แขนไหลเข้าศูนย์กลาง |
| `sheet_wisps` | 4x4 วน | เส้นควันส่ายไปมา |
| `sheet_arcs` `sheet_cracks` `sheet_puffs` `sheet_splats` | 2x2 | สายฟ้า, รอยร้าว, ก้อนควัน, รอยสาด อย่างละ 4 แบบ |
| `sheet_shards` `sheet_suits` `sheet_stars` `sheet_petals` | 2x2 | เศษผลึก, ดอกไพ่, ดาว, กลีบและใบ |
| `sheet_runes` | 4x4 | อักษรรูน 16 ตัว |
| `sheet_kawaii` `sheet_gothic` `sheet_casino` `sheet_tech` `sheet_nature` | 4x4 | ไอคอน 16 แบบตามหมวด |
| `sheet_festival` `sheet_spooky` `sheet_pirate` `sheet_sweet` | 4x4 | โคมลอยและดอกบัว, ฮาโลวีนและค้างคาว, สมอเรือและเหรียญต้องสาป, ลูกกวาดและตัว Z ฝันหวาน |

### สูตร layer 67 แบบ

| กลุ่ม | สูตร |
| --- | --- |
| วาบและแสง | `flash` `light_flash` `core_glint` `glints` `twinkle_glints` `lens_flare` `nova_rays` `star_flare` `impact_star` |
| ออร่าตอนถือ | `glow_pulse` `aura_swirl` `motes` `ember_rise` `flames` `wisp_rise` `bubbles` `shape_float` `dream_float` `rune_glyphs` `arc_crackle` `snow` `petals` |
| รอยตี | `slash_arc` `energy_slash` `claw_marks` `spark_burst` `speed_lines` `arc_bolts` `electric_arcs` `glitch_bits` `hex_shield` `ink_splats` `plasma_orb` |
| วงและคลื่น | `shock_ring` `shockwave` `ground_ring` `ground_shock` `ripples` `halo` |
| บนพื้น | `rune_circle` `magic_circle` `pop_seal` `vortex` `ground_crack` `fire_ring` `mist` |
| ตั้งตรงและลอยขึ้น | `pillar` `light_beam` `bolt_strike` `wings` `magic_circle_air` `lantern_float` |
| เศษกระจาย | `shape_burst` `icon_burst` `card_throw` `star_shower` `petal_storm` `delayed_petal_burst` `crystal_break` `shards` `confetti` |
| ควันและเกริ่น | `implode` `smoke_puff` `soft_smoke` `shadow_smoke` `energy_wisp` |
| เส้นริบบิ้นเคลื่อนที่ | `ribbon` `ribbon_trail` `ribbon_halo` (คู่กับรูปทรง `ribbon_line` หรือภาพ PNG ขนาด `512x128`) |

คำอธิบายของแต่ละสูตรอยู่ในผลของ `ptfx.ps1 recipes` เพิ่มสูตรของชุดเองได้ใน `"archetypes": { ... }` ของ design

## หลักออกแบบ

**โครงของแต่ละช่วง**

| ช่วง | layer | เวลา | องค์ประกอบ |
| --- | --- | --- | --- |
| Hold | 2–3 | loop 1–1.3 s | ออร่าหนึ่งชั้น + ของลอยหนึ่งชั้น ต้องไม่บังอาวุธและไม่รบกวนตอนเล็ง |
| Hit | 3–5 | 0.5–0.7 s | วาบ → รูปทรงหลัก (รอยฟัน, รอยชน) → เศษกระจาย → วงคลื่น ต้องจบเร็วเพราะเกิดถี่ |
| Kill | 6–7 ต่อ effect | 2–2.3 s | เกริ่น (ดูดเข้า) → วาบ → ของบนพื้น → ของตั้งตรง → เศษ → สิ่งที่ค้าง |

**7 layer คือเพดาน.** ไม่มี effect ใดในไฟล์จริง 2,021 ตัว รวมทั้ง `core.ypt` ของเกม ที่มีเกิน 7 ตัวสร้างจะไม่ยอม build ถ้าเกิน Kill ที่ต้องการมากกว่านั้นให้แยกเป็นสอง effect (`x_kill`, `x_kill_veil`) แล้วเรียกทั้งคู่ใน `fx.kill` ดูตัวอย่างใน `templates/ptfx-design.example.json`

**แกนของแต่ละช่วงไม่เหมือนกัน.** นี่คือข้อที่ทำให้ effect ดูผิดบ่อยที่สุด

| ช่วง | Lua วางที่ | ผลต่อการออกแบบ |
| --- | --- | --- |
| Hold | กระดูกมือ (`57005` หรือ `28422`) เกาะตลอด | แกนของ effect หมุนตามมือ **ห้ามใช้ `dir: "up"`/`"down"` และ `offset` เพื่อบอกทิศบน-ล่าง** ให้ของลอยขึ้นด้วย `gravity` ติดลบ ตกด้วย `gravity` บวก ซึ่งทำงานในแกนโลก สูตรกลุ่มออร่าตอนถือทำแบบนี้อยู่แล้ว |
| Hit | กระดูกหัวของเหยื่อ (`31086`) | เหมือน Hold ใช้ของที่สมมาตรรอบจุด (วาบ, รอยฟัน, ประกายพุ่งออก, วงคลื่นหันกล้อง) |
| Kill | ตัวเหยื่อ `bone = 0` ไม่เกาะ | แกน Z ชี้ขึ้นจริง ใช้ `offset` ได้: จุดกำเนิดอยู่ราวสะโพก พื้นอยู่ที่ z ≈ −0.95, หัวอยู่ที่ z ≈ +0.75 |

Sprite แบบ `camera` ตั้งตรงตามจอเสมอไม่ว่ากระดูกจะหมุนอย่างไร และ `ground` นอนราบตามแกนโลกเสมอ ทั้งสองจึงใช้ได้ทุกช่วง

**ลำดับเวลา.** ให้ layer เริ่มเหลื่อมกัน 0.02–0.2 ของ `duration` ด้วย `start` ของที่สว่างที่สุดควรสั้นที่สุด (0.1–0.2 s) ของที่ค้างนานควรจางและช้า Kill ควรมี 0.15 ของเวลาเป็นช่วงเกริ่นก่อนวาบ

**สี.** ใช้ไม่เกินสามสีต่อ effect: แกนสว่าง (เกือบขาว) สีหลัก และสีเงาสำหรับช่วงจาง `colorEnd` ไปทางสีเข้มทำให้ประกายดูเหมือนเย็นลง Layer แบบ `add` ซ้อนกันมากจะกลายเป็นขาวล้วน ให้ลด `alpha` หรือ `emissive` ของชั้นใหญ่ ไฟล์จริงใช้ `emissive` median 14, p90 120

**ขนาดที่ `scale = 1.0`.** จุดลอยตอนถือ 3–7 cm, เปลวไฟที่มือ 15–28 cm, ออร่ามือ 25–40 cm, ประกายไฟกว้าง 1.2–2.4 cm ยาว 9 เท่า, รอยฟัน 1.1–1.3 m, วงคลื่นปลายทาง 1.2–1.5 m, วงเวทบนพื้น 1.6–2.2 m, Kill ทั้งชุดอยู่ในทรงกระบอกกว้าง 2–3 m สูง 2.5 m ออกแบบที่ขนาดจริงแล้วตั้ง `scale = 1.0` ใน Lua

**งบ.** Hold ไม่เกิน 60 ชิ้นพร้อมกัน, Hit 80, Kill 160 (lint เตือนเมื่อเกินสองเท่า) ไฟล์ไม่เกิน 2 MB Sheet 7x7 ขนาด 1024 px หนัก 1.3 MB ให้ใช้ 512 px ถ้าไม่ใช่จุดเด่นของชุด

**เอกลักษณ์.** ชุดที่ดีต้องมีอย่างน้อยหนึ่งอย่างที่ชุดอื่นไม่มี: sheet ของชุดเองจาก `cells`, sprite จาก `glyph` หรือภาพของผู้ใช้, หรือรูปทรงที่ผ่าน `kaleido`/`erode`/`warp` จนเป็นลายเฉพาะ

## สิ่งที่พิสูจน์แล้วและยังไม่ได้พิสูจน์

พิสูจน์จากไฟล์จริง (`254` `.ypt` dictionaries ที่เปิดอ่านได้จากหลายเซิร์ฟเวอร์ รวม `1,498` effects, `2,854` emitters, `2,923` particle rules และ `core.ypt` ของเกม)

| เรื่อง | หลักฐาน |
| --- | --- |
| ตัวอ่านและตัวเขียนถูกต้อง | แตกไฟล์เป็นสเปกแล้วประกอบกลับได้เหมือนเดิมทุกไบต์ของทุก struct 158 จาก 163 ไฟล์ที่ไม่มีโมเดล 3D อีก 5 ไฟล์ต้นฉบับผิดปกติเอง |
| ขนาดเป็นเมตร คูณ `SizeScalar`% ของ emitter และ `Zoom`% ของ effect | effect ของเกมคำนวณแล้วได้ขนาดจริง: น้ำกระเซ็นจากกระสุน 0.43 × 1.7 m, แมลงสาบ 4.5 × 6.7 cm, แสงปากกระบอกปืนพก 0.4 m (ตั้ง `ZoomScalar = 100` และ `SizeScalar = 100` เสมอเพื่อให้ `scale = 1.0` ใน Lua ตรงกับหน่วยเมตรจริง) |
| `velocity`: ด้านสูงของภาพชี้ตามทิศวิ่ง | tracer ของเกมกว้าง 0.6 สูง 500, sheet `ptfx_sparks` กับ `ptfx_bullet_tracer` เป็นแท่งแนวตั้ง |
| `ground` = โหมด 2 แกน (0,0,1) | ฟองน้ำ, แอ่งเลือด, แมลงสาบของเกมใช้ค่านี้ทั้งหมด |
| อ้าง texture ของเกมด้วยชื่อได้ | ไฟล์ของผู้สร้างอื่น 80 จาก 182 ไฟล์ทำแบบนี้ 340 ครั้ง |
| Texture ชื่อใหม่ = เฟรมเดียว (`ClipRegions` ผูกกับชื่อ) | เกมค้นตารางแบ่งเฟรม UV จากชื่อ hash มาตรฐาน (`ptfx_fishes` 2x2, `ptfx_casino_chips` 2x2, `ptfx_multi_sheet_002_debris` 4x4 ฯลฯ) หากตั้งชื่อใหม่เองอย่าง `electric_blue_hit_neon_splash` เกมจะวาดทั้งตารางซ้อนกันในรูปเดียวโดยไม่ตัดเฟรม |
| Sheet ใต้ชื่อเกม | rule 758 ตัวในไฟล์จริงฝัง texture ใต้ชื่อเกม ทั้งขนาดต่างจากของเกม ตารางเฟรมอ่านจากชื่อช่องเกมโดยตรง (จำกัดอยู่เฉพาะใน `.ypt` ของสกินเรา ไม่กระทบของเกมหลัก) |
| เพดาน 7 layer | จาก `1,498` effects จริง ค่าสูงสุดคือ `7` (`0` ไฟล์ที่เกิน 7) |
| `gravity` และ `accelKeys` ทำงานในแกนโลกเสมอ | `93.8%` ของ particle rules ใช้ `Acceleration.ReferenceSpace = 0` จึงใช้บังคับให้บล็อกหรือสะเก็ดพุ่งขึ้นแล้วตกลงพื้นโลกจริงได้แม้เกาะกระดูกมือ `57005` ที่หมุนพลิกตลอดเวลา |
| ค่าการเล่นภาพเคลื่อนไหว | ชุดค่าของ `loop` `once` `random` `smoke` คัดจาก rule ของเกมที่ใช้ชุดค่านั้น |
| `SuperAlpha` บน unlit sprite ต้องเป็น `1.0` | พิสูจน์ในเกม FiveM จริงและใน `lego.ypt` รุ่นเก่า (`SuperAlpha = 20`, `IsLit = 1`, `LightingMode = 2`): ค่าสูงทำให้ขอบฟุ้งและสีพลาสติกกลายเป็นก้อนขาวโพลนตอนกลางวัน `YptDesign` จึงบังคับ `SuperAlpha = 1.0`, `IsLit = 0`, `LightingMode = 0` เสมอ |
| พลาสติกสีสด / บล็อกของเล่น (`brick_modular`) และสกินโทนมืด ต้องใช้ `blend: "normal"` (`BlendSet = 0`) + `emissive: 1.8–3.0` | พิสูจน์ในเกม FiveM จริงตอนเที่ยง: การวาดสีพลาสติก ABS (แดง `#e3242b`, เหลือง `#ffd500`, น้ำเงิน `#006cb7`, เทา `#2f353d`) หรือคาร์บอนแดงเข้มลงในแผ่น sheet (`ptfx_fishes` / `ptfx_multi_sheet_*`) แล้วตั้ง `color: "#ffffff"`, `blend: "normal"`, `IsLit = 0`, `LightingMode = 0`, `emissive: 1.8–3.0` ทำให้ได้ก้อนพลาสติกหลายสีสดชัดใน layer เดียวโดยไม่ขาวซีดกลางแดด และไม่สว่างล้นตอนกลางคืน (ใช้ `blend: "add"` เฉพาะประกายดาวและเส้นแสงนีออน) |
| Hold ต้องเป็นเส้นเดี่ยว (`ribbon_trail`) หรือปุ่ม/สะเก็ดจิ๋วที่หลุดลอยอิสระในโลก (`attach: 0.0`) | พิสูจน์ในเกม FiveM จริง: layer แบบพ่นขึ้นตามแกนกระดูก (`dir: "up"`) จะชี้เฉียงออกข้างสะโพกตอนยืนถือ ส่วน `ribbon_trail` (`rate = 30–36`, `rateOverDist = 20–26`, `attach = 0`) คู่กับชิ้นส่วนลอยช้า ๆ ด้วย `gravity: -0.25..-0.35` ให้มิติที่นิ่งสะอาดตอนยืนและคลี่เส้นสวยตอนฟัน |

อนุมาน (มีเหตุผลรองรับ แต่ไม่มีหลักฐานตรง)

- `gravity` ทำงานในแกนโลก: 2,605 จาก 2,839 rule ใช้ `ReferenceSpace = 0` รวมถึงประกายไฟที่ต้องตกลงพื้นไม่ว่ารถจะหันทางใด
- Sheet ที่เราวาดเองใต้ชื่อเกมจะถูกตัดเฟรมเหมือนของเกม: ตามหลักฐานสองข้อบนรวมกัน

ยังไม่ได้พิสูจน์

- **ไฟล์ที่ออกแบบใหม่ยังไม่เคยโหลดในเกมบนเครื่องนี้** ทุกค่าของทุก struct อยู่ในช่วงที่ไฟล์จริงใช้ แต่ผลบนจอต้องให้ผู้ใช้ยืนยัน ให้บอกผู้ใช้ตรง ๆ ทุกครั้งที่ส่งงาน
- `light` และ `ribbon` สร้างตามโครงที่พบในไฟล์จริง แต่ยังไม่เคยเห็นผล
- ภาพ preview เป็นการจำลอง: ไม่มีแสงของฉาก ไม่มี bloom ไม่มี soft particle ใช้ตัดสินจังหวะ สี รูปทรง และสัดส่วน ไม่ใช่ความสว่างจริง

## ข้อจำกัด

1. การย้อมสีทำได้แค่คูณ Texture ของเกมที่มีสีอบมาแล้ว เช่นไฟสีส้ม ย้อมเป็นสีฟ้าไม่ได้ ให้ใช้ `sheet_fire` ซึ่งเป็นสีขาว
2. `comet` มีหัวกับหาง ยังไม่รู้ว่าปลายไหนของภาพชี้ไปข้างหน้าเมื่อใช้ `velocity` ถ้าในเกมหางนำหน้าให้ใส่ `sprite.rotation` บวก 180
3. Particle แบบโมเดล 3D (`ptfx_model`) อ่านและสรุปได้ แต่ยังสร้างใหม่ไม่ได้
4. ชื่อไฟล์ต้องเท่ากับชื่อ dictionary ชื่อ effect ต้องไม่ซ้ำกับ effect ของเกม (lint ตรวจกับ 964 ชื่อใน `core.ypt`) และควรขึ้นต้นด้วย id ของชุด
5. การดูภาพ preview ของ texture เกมต้องมี `core.ypt` ในเครื่อง ตัวสร้างหาเองในโฟลเดอร์งาน หรือระบุด้วย `-Core <path>` ถ้าไม่มีจะใช้ภาพแทนและบอกในรายงาน

## ศึกษา effect ที่มีอยู่ (ทาง C)

```powershell
scripts\ptfx\ptfx.ps1 inspect -Path <file.ypt>              # สรุปเป็นข้อความ: layer, texture, จังหวะ, ทุกคีย์เฟรม
scripts\ptfx\ptfx.ps1 preview -Path <file.ypt>              # ภาพจำลองด้วย texture จริงของไฟล์นั้น
scripts\ptfx\ptfx.ps1 textures -Path <file.ypt> -Out <โฟลเดอร์>   # ถอด texture ทุกตัวเป็น PNG
scripts\ptfx\ptfx.ps1 lint -Path <file.ypt>                 # ตรวจไฟล์ใดก็ได้ด้วยเกณฑ์เดียวกับ build
scripts\ptfx\ptfx.ps1 decompile -Path <file.ypt> -Out x.json
```

ใช้ได้กับไฟล์ที่เปิดอ่านได้เท่านั้น คำสั่งที่สแกนทั้งโฟลเดอร์และ `textures` ข้าม resource ที่มี `.fxap` สเปกที่ได้จาก `decompile` มี `_source` กำกับ และ `build` จะไม่ยอมประกอบกลับ เพราะนั่นคือการคัดลอกงานของคนอื่น ยกเว้นส่ง `-AllowDerived` เมื่อไฟล์ต้นทางเป็นงานของเราเอง ภาพที่ได้จาก `textures` ใช้ดูเพื่อเข้าใจเทคนิคเท่านั้น ห้ามนำไปใส่ในชุดของเรา

สิ่งที่ควรจดจากการศึกษา: จำนวน layer, ลำดับเวลา, อัตราส่วนขนาด, เส้นโค้ง alpha แล้วนำหลักนั้นไปเขียน design ใหม่ด้วยรูปทรงและสีของเราเอง

## ฝั่ง Lua

### กฎการเล่นจริง

ตรวจตรงจาก `core/sh_mixing.lua:304–352` (`DamagePlayback`) และ `core/cl_effects.lua`

| อาวุธ | ตี/ยิงโดนแต่ไม่ตาย (`not died`) | ฆ่าสำเร็จ (`died`) |
| --- | --- | --- |
| Poolcue, Bottle | เล่น `Hit.Effect` + `Hit.Screen` (แต่ไม่ fallback ไปดึง `Kill.Effect` และไม่เล่น `Kill.Prop`) | `Kill.Effect` (ถ้าไม่มีใช้ `Hit.Effect`) + `Kill.Prop` + `Kill.Screen` |
| Knuckle, Machete, อื่น ๆ | `Hit.Effect` + `Hit.Screen` | `Kill.Effect` (ถ้าไม่มีใช้ `Hit.Effect`) + `Kill.Prop` + `Kill.Screen` |
| Revolver | เข้า `phase = "hit"` เสมอ: เล่น `Hit.Effect` (ถ้าไม่มีใช้ `Kill.Effect`) + `Hit.Screen` | ใช้เส้นทางเดียวกับ `hit` เสมอ (ถ้ามี `Kill.Prop` ต้องใส่ `on_hit = true` ในรายการแรกของ `Revolver`) |

ดังนั้นทุกสกินควรกำหนดทั้ง `Hold.Effect`, `Hit.Effect` และ `Kill.Effect` ให้ครบ โดยให้ `Hit` และ `Kill` เกิดในพิกัดโลก ณ ตัวเหยื่อ (`attach = false`, `bone = 0`) เพื่อไม่ให้ ragdoll ดึงตราประทับพื้นเอียง ส่วน `Hold` เกาะบนมือขวา `bone = 57005` (`SKEL_R_Hand`) ด้วย `isLoop = true`, `scale = 1.0` (ดูสัญญากระดูกและการปลดหน่วยความจำใน **`references/bone-and-memory-safety.md`**)

### โครง config

```lua
Config.General.weaponEffects["SkinType"] = {
    Hold = { Effect = { {...} } },
    Hit = { Effect = { {...} }, Screen = {...} },
    Kill = { Effect = { {...} }, Screen = {...}, Prop = { {...} } },
}
```

`Effect` เป็น list เดียวใช้ทุกอาวุธ หรือแยกเป็น `Effect = { Poolcue = {...}, Bottle = {...} }` `Screen` แยกต่ออาวุธได้เช่นกัน `Prop` ใช้ได้เฉพาะใต้ `Kill`

| ฟิลด์ | ความหมาย | ขอบเขต |
| --- | --- | --- |
| `particleDictionary`, `particleName` | ชื่อ dictionary และ effect | ต้องมี |
| `scale` | ขนาด | 0.01–4.0 ในไฟล์จริง median 0.5 (p10 0.1, p90 2.0) |
| `offset`, `rot` | ตำแหน่ง/หมุน | offset ±5, rot ±360 |
| `bone` | bone ของ ped | 0 = entity |
| `attach` | ติดตามตัว | `false` = เกิด ณ จุดเดียว |
| `ground` | ยิง raycast วางบนพื้นจริง | `true` เหมาะกับ `Kill.Effect` ที่ต้องการแปะพื้นเสมอ |
| `delay` | หน่วงก่อนเริ่ม ms | 0–10000 |
| `isLoop` | ต้องตรงกับชนิดของ effect | `true` ใช้กับ effect ที่ build ด้วย `"loop": true` เท่านั้น |
| `loop`, `duration` | รอบเล่นซ้ำของแบบไม่ loop, เวลาเล่นของ looped | สูงสุด 10000 |
| `restart` | เริ่มใหม่เป็นรอบตอนถือ | Hold |
| `color`, `alpha` | ย้อมและความทึบ 0–1 | |
| `orbit_turns`, `growScale`, `growSteps`, `growStepTime` | หมุนรอบตัว, ขยายขณะเล่น | looped เท่านั้น |

Hold ทำได้สองแบบ: effect แบบ looped กับ `isLoop = true` หรือ effect แบบ one-shot กับ `isLoop = false` แล้วให้ `loop = <ms>` ยิงซ้ำเป็นจังหวะ แบบหลังให้พัลส์คมและไม่ค้างเมื่อเปลี่ยนสกิน

Bone ที่พบบ่อย: `57005` มือขวา, `28422` PH_R_Hand (ค่าเริ่มของ Hold), `24818` อก, `18905` มือซ้าย, `60309` PH_L_Hand, `31086` หัว, `12844` หัว IK, `24816` ท้อง, `0` entity

ค่าจำกัดใน `Config.General.setting`: `particle_max_handles = 20`, `particle_max_per_second = 60`, `hit_effect_distance = 60`, `hold_effect_distance = 30`, `hold_effect_max_peds = 10`

ปรับรวมผู้เล่น: convar `1nfx_weaponskin_particles`, `1nfx_weaponskin_custom_particles` (เฉพาะ dictionary `1nfx_weapon_effects`) และ export `SetEffectScale`

### การซ้อนชั้นใน Lua

รายการใน `Effect` เล่นพร้อมกันทั้งหมด ใช้ `delay` เหลื่อมเวลา Kill ที่แยกเป็นสอง effect ให้ใส่สองรายการ `delay` เท่ากัน จังหวะภายในอยู่ใน design แล้ว (`start`) ทุกรายการใช้ handle หนึ่งตัวจากเพดาน 20 จึงไม่ควรเกินสามรายการต่อช่วง

### ทาง B: effect ของเกม

ที่ยืนยันแล้วว่าเซิร์ฟเวอร์นี้ใช้อยู่: `veh_xs_vehicle_mods / exp_xs_mine_emp`, `core / ent_ray_heli_aprtmnt_exp`, `core / exp_grd_molotov`, `core / ent_dst_gen_water_spray`

ที่เซิร์ฟเวอร์อื่นใช้บ่อย: `scr_rcbarry2 / scr_exp_clown`, `scr_rcbarry2 / scr_clown_bul`, `scr_rcbarry2 / scr_clown_death`, `scr_rcbarry1 / scr_alien_teleport`, `scr_indep_fireworks / scr_indep_firework_trailburst`, `scr_indep_fireworks / scr_indep_firework_starburst`, `scr_powerplay / sp_powerplay_beast_appear_trails`, `scr_xs_celebration / scr_xs_money_rain`, `scr_ba_club / scr_ba_club_champagne_spray`, `scr_agencyheistb / scr_agency3b_elec_box`, `scr_mp_controller / scr_mp_elec_dst`, `scr_bike_business / scr_bike_cfid_camera_flash`

ห้ามแก้หรือดึงจาก dictionary ของผู้สร้างอื่น เช่น `wishme_*` `withme_*` `wm_*` `plyx_*` และไฟล์ใน resource ที่มี `.fxap`

## Prop (ทางเลือก)

ฟิลด์: `model`, `duration` (200–10000), `delay` (0–2000), `offset`, `rotation`, `relative_rotation`, `scale`, `attach`, `ground`, `billboard`, `distance`, `cooldown`, `animDict`, `animName`, `animLoop`, `animBlend`, `animSpeed`, `animHoldLastFrame`, `on_hit` (เฉพาะ Revolver) จำกัด 12 ชิ้น ระยะ 15 เมตร ตัวอย่างที่อ่านได้: `config/skins/lazy_thunderx.lua`
