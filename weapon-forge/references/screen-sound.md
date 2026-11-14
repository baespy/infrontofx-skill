# Screen and Sound

## ใครเห็นอะไร

จาก `HandleWeaponDamage` ใน `core/cl_main.lua`

| คน | ได้รับ |
| --- | --- |
| เหยื่อ (ถูกตี/ถูกฆ่า) | **ภาพเต็มจอ + เสียง** จาก `Screen` |
| คนฆ่า | **เสียงอย่างเดียว** จาก `Kill.Screen.sound` ไม่มีภาพ |
| คนรอบข้าง | เห็น particle เท่านั้น |

ภาพจึงเป็นสิ่งที่เหยื่อเห็น ต้องไม่บังการมองเห็นจนเล่นไม่ได้

## สัญญาของ NUI

```lua
Screen = { image = "x.png", sound = "x.mp3", duration = 2000, volume = 0.3 }
```

| ส่วน | ค่า |
| --- | --- |
| ตำแหน่งไฟล์ | `1nfx_weaponskin/html/img/effect/` |
| ชื่อไฟล์ | ต้องผ่าน `^[\w.-]+$` ห้ามเว้นวรรคหรือภาษาไทย |
| `duration` | client บีบ 100–5000 ms ค่าที่เจอบ่อยคือ 2000 และ 3000 |
| `volume` | 0–1 ค่าเริ่มต้น 0.3 ส่วนใหญ่ใช้ 0.3 |
| การแสดงผล | `#warpper` เต็มจอ `background-size: cover` |
| Animation | opacity 0 → **0.8** ช่วง 20–70% → 0 |

## สเปกภาพ

- 1920×1080 พื้นโปร่งใส
- **เว้นกลางจอ 50–60%** ให้ความสำคัญอยู่ตามขอบ
- ห้ามวางของสำคัญใกล้ขอบเกิน 8% เพราะ `cover` จะตัดบนจอที่ไม่ใช่ 16:9
- ทึบสูงสุดจะเหลือ 80% เพราะ animation
- WebP แบบเคลื่อนไหวใช้ได้ (`thunderx_anim.webp`, `elys.webp`)

ไฟล์เดิม: PNG 41 ไฟล์ เฉลี่ย 1.7 MB, WebP 4 ไฟล์ เฉลี่ย 365 KB ควรคุม PNG ไว้ไม่เกิน 2 MB และถ้ามีเครื่องมือแปลงให้เป็น WebP

### make-screen.ps1

```powershell
scripts\make-screen.ps1 -OutFile x.png -Preset gothic -Primary '#f5efe2' -Secondary '#0b0b10' -Glow '#ffe9b8' -Seed 7
```

Preset (17 แบบ): `gothic` `bolt` `drip` `hearts` `frost` `circuit` `pixel` `bubbles` `nebula` `tactical` `oni` `dragon` `chains` `shatter` `cyber_hud` `sakura_slash` `holy_halo`

`oni` วาดรอยฟันสี่มุม กลีบซากุระ ประกายไฟ และตัวอักษร 鬼影 กลางล่าง (ใช้ `[char]0x9B3C` + `[char]0x5F71` ไม่ฝังคันจิในไฟล์ .ps1 เพราะ PowerShell 5.1 อ่านเป็น ANSI) ต้องมีฟอนต์ Yu Gothic หรือ MS Gothic ตอนสร้างภาพ

ใช้เฉพาะ `System.Drawing` ไม่ต้องลงอะไรเพิ่ม ผลออกมาราว 350 KB–2 MB ใช้สำหรับต้นแบบเร็วหรือสกินแนว 2D กราฟิก แต่**ห้ามใช้ภาพวาด 2D แบน ๆ กับสกินแนวสมจริง / คาร์บอน / โลหะ / ดาร์กแฟนตาซี** เพราะในเกมจะดูเหมือนคลิปอาร์ตการ์ตูน ให้ใช้ `render_fx_assets.py` ด้านล่างแทน

### render_fx_assets.py (งานขายระดับ 3D Blender Cycles)

สำหรับสกินระดับงานขายในเซิร์ฟเวอร์ `[1nfx]` (เทียบชั้น `carbon.png`, `eclipse.png`, `royalblood.png`) ให้ปั้นและเรนเดอร์กรอบจอ 3D ด้วย Blender Cycles แบบไร้หน้าต่าง:

```powershell
& "C:\Tools\blender-4.2.3-windows-x64\blender.exe" -b --factory-startup -P scripts\blender\render_fx_assets.py -- `
    --prefix onikage `
    --out-screen "<1nfx_weaponskin\html\img\effect>" `
    --out-ptfx "<weapon_onikage\source\fx3d>" `
    --primary "#dc0008" --secondary "#c4913a" --dark "#07070a" --samples 44
```

- สร้างทั้ง `<prefix>.png` (Hit: กรอบเกราะคาร์บอน 3D เฉียบคมรอบขอบจอ) และ `<prefix>_kill.png` (Kill: เกราะคาร์บอน 3D ซ้อนชั้น + เขาโอนิ 3D + คริสตัลทับทิมเลือด + ควันคาร์บอนฟุ้งตามขอบ) พร้อมชุด sprite 3D สำหรับฝังลง `.ypt`
- บังคับพื้นที่กลางจอ 75–82% ให้เป็น `alpha = 0` สนิท (`center50_max_alpha = 0`) ไม่ย้อมสีทับกลางจอและไม่บังเป้าเล็ง
- ใช้ Cycles `CPU` + `OpenImageDenoise` เพื่อหลบปัญหาคอมไพล์ PTX ค้างของการ์ดจอสถาปัตยกรรมใหม่ใน Blender 4.2 (ใช้เวลาเรนเดอร์ทั้งชุดราว 10–15 วินาที)

## สเปกเสียง

ไฟล์เดิม: mp3 39 ไฟล์ เฉลี่ย 71 KB, ogg 4 ไฟล์ เฉลี่ย 30 KB, wav 4 ไฟล์ เฉลี่ย 396 KB

| ช่อง | ความยาว | หมายเหตุ |
| --- | --- | --- |
| Hit | ไม่เกิน 1 วินาที | เล่นบ่อย จึงต้องไม่รำคาญ |
| Kill | 1–2 วินาที | เสียงจบที่ชัดกว่า |

### make-sound.ps1

```powershell
scripts\make-sound.ps1 -OutFile x_hit.wav -Preset bell -Kind hit -Seed 7
```

| Preset | ลักษณะ | RMS ฮิต/คิล (dBFS) | volume แนะนำ |
| --- | --- | --- | --- |
| `bell` | ระฆัง | -18.6 / -16.6 | 0.3 |
| `thunder` | ฟ้าผ่า | -23.1 / -22.0 | 0.4 |
| `chime` | กระดิ่งไล่โน้ต | -14.7 / -18.4 | 0.25 |
| `toy` | ของเล่นเด้ง | -14.5 / -12.7 | 0.25 |
| `glitch` | ดิจิทัลแตก | -14.9 / -14.9 | 0.25 |
| `coin` | เหรียญเกม | -9.8 / -9.8 | 0.12 |
| `splash` | น้ำสาด | -17.7 / -17.4 | 0.3 |
| `slime` | ของเหลวหนืด | -17.9 / -17.5 | 0.3 |
| `cosmic` | กวาดขึ้นมีเอคโค | -13.9 / -16.9 | 0.25 |
| `blade` | ใบมีดเฉือน | -19.8 / -21.5 | 0.35 |
| `gunmetal` | โลหะหนัก | -23.8 / -26.0 | 0.45 |
| `oni` | กลองต่ำ + ดาบเฉือน (kill มีกังวานต่ำ) | -21.0 / -20.8 | 0.35 / 0.4 |
| `dragon_roar` | คำรามมังกรกังวานต่ำ + เสียงลมเฉือน | -19.5 / -18.2 | 0.35 |
| `chain_whip` | โซ่เหล็กสะบัดกระทบกัน | -17.2 / -16.4 | 0.3 |
| `shatter_glass` | กระจก/คริสตัลแตกกระจาย | -16.8 / -15.9 | 0.28 |
| `holy_choir` | คอร์ดประสานเสียงโบสถ์ศักดิ์สิทธิ์ | -18.0 / -16.5 | 0.3 |
| `katana_sheathe` | ดาบซามูไรฟันฉับ + เก็บเข้าฝัก (`chink`) | -18.9 / -17.8 | 0.32 |
| `cyber_blast` | พัลส์เลเซอร์ไซเบอร์ + ซับเบส | -16.1 / -15.4 | 0.25 |

ไฟล์ออกเป็น WAV 16-bit mono 44.1 kHz ขนาด 69–138 KB peak -1 dBFS ค่า volume ด้านบนคำนวณจากความดัง ยังไม่ได้ฟังจริง จึงต้องให้ผู้ใช้ฟังและตัดสิน

เสียงที่สังเคราะห์เป็นเสียงต้นฉบับ ถ้าผู้ใช้เอาเสียงจากที่อื่นมา ให้ถามที่มาและสิทธิ์การใช้

## ใน skin spec

`new-skin.ps1` สร้างเสียงสองไฟล์เสมอ: `<id>_hit.wav` (สั้น) และ `<id>_kill.wav` (ยาวกว่า มีหาง) จาก `fx.sound.preset` ถ้าอยากให้เสียงฆ่าเป็นคนละแนว ให้ใส่ `fx.sound.kill_preset` ภาพเต็มจอใช้ภาพเดียวทั้ง Hit และ Kill เว้นแต่ใส่ `fx.screen.kill_preset` (และ `kill_primary`, `kill_secondary`, `kill_glow` ถ้าต้องการสีต่าง) จะได้ `<id>_kill.png` เพิ่ม

เลือกเสียงและภาพให้เข้ากับ particle: Hit ที่มี `slash_arc` คู่กับ `blade` หรือ `katana_sheathe`, Kill ที่มี `rune_circle` กับ `pillar` คู่กับ `holy_choir` หรือ `bell`, ธีมไฟฟ้าคู่กับ `thunder` และภาพ `bolt` เป็นต้น จังหวะเสียงฆ่าควรมีจุดเน้นใกล้กับจังหวะ `flash` ของ Kill (ราว 0.3 วินาทีแรก)


### ใช้ธีม

เมื่อสเปกมี `fx.theme` ตัว `new-skin.ps1` จะเติมค่าที่ขาดใน `fx.screen` และ `fx.sound` จากธีม: preset ของภาพตีและภาพฆ่า, preset ของเสียงตีและเสียงฆ่า, และสีของภาพ (primary = สีหลักของธีม, secondary = สีเข้ม, glow = สีรอง รวมค่าที่แก้ผ่าน `theme_colors`) ตารางจับคู่ทั้ง 20 ธีมอยู่ใน `particles.md` หัวข้อ "ธีมสำเร็จรูป" ค่าที่เขียนไว้ในสเปกชนะค่าของธีมเสมอ จึงใส่เฉพาะ `hit_volume` กับ `kill_volume` แล้วปล่อยที่เหลือให้ธีมก็ได้

Preset ของภาพ 17 แบบและเสียง 18 แบบยังเป็นชุดเดิม ธีมบางตัวจึงใช้ preset ที่ใกล้ที่สุดแทนของที่ทำมาเฉพาะ (`casino` ใช้ภาพ `pixel`, `inferno` ใช้เสียงตี `blade`) ถ้าชุดนั้นเป็นงานขาย ให้พิจารณาเพิ่ม preset ใหม่ใน `make-screen.ps1` หรือ `make-sound.ps1`
