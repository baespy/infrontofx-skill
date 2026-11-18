# Server Catalog

สร้างจาก `scripts/catalog-weapons.ps1` อย่าแก้มือ รันใหม่เมื่อเพิ่มหรือลบสกิน รายละเอียดทุก component อยู่ใน `server-catalog.json`

Resource 33 ตัว (เปิดได้ 11, ล็อก .fxap 22) | Component สกิน 166 | ชื่อสกินไม่ซ้ำ 48 | ไฟล์ 475 ไฟล์ 367.1 MB

ตัวเลข tris, shader และ texture อ่านจากไฟล์ใน resource ที่ไม่ล็อกเท่านั้น ส่วนที่ล็อกดูแค่ชื่อและขนาดไฟล์

## แยกตามช่อง

| ช่อง | ทั้งหมด | เปิดได้ | ล็อก | ไม่พบไฟล์ | โมเดลปั้นเอง (>=2k tris) | tris ต่ำสุด | ค่ากลาง | สูงสุด |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BAT | 4 | 2 | 2 | 0 | 2 | 21986 | 22464 | 22464 |
| BOTTLE | 32 | 12 | 20 | 0 | 11 | 5300 | 12598 | 22406 |
| KNIFE | 3 | 0 | 2 | 1 | 0 |  |  |  |
| KNUCKLE | 28 | 9 | 19 | 0 | 9 | 5786 | 14165 | 19745 |
| MACHETE | 23 | 7 | 16 | 0 | 7 | 5073 | 16812 | 27008 |
| POOLCUE | 47 | 26 | 21 | 0 | 17 | 3900 | 16774 | 40054 |
| REVOLVER | 29 | 9 | 20 | 0 | 9 | 9584 | 15379 | 24500 |

## Shader ที่ใช้จริง

| shader | จำนวนโมเดล |
| --- | ---: |
| `emissive` | 56 |
| `weapon_emissivestrong_alpha` | 10 |
| `emissivenight` | 8 |
| `default` | 1 |
| `normal_spec_reflect` | 1 |
| `normal_spec` | 1 |

## Texture ที่ใช้จริง

| ขนาดและฟอร์แมต | จำนวน |
| --- | ---: |
| 1024x1024 DXT5 | 135 |
| 1024x256 A8R8G8B8 | 9 |
| 1024x256 DXT1 | 7 |
| 2000x500 A8R8G8B8 | 6 |
| 512x512 DXT5 | 5 |
| 1024x256 DXT5 | 3 |
| 2048x4096 DXT1 | 3 |
| 64x64 DXT1 | 2 |
| 2048x2048 DXT1 | 2 |
| 2048x512 DXT5 | 2 |
| 2048x512 DXT1 | 2 |
| 1024x1536 DXT1 | 1 |
| 1024x1536 DXT5 | 1 |
| 4x4 DXT1 | 1 |
| 2500x500 A8R8G8B8 | 1 |

## Resource ทั้งหมด

| resource | สถานะ | ydr | ytd | ycd | MB | component | ช่อง | particle dictionary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `weapon_8bit` | ล็อก | 5 | 0 | 0 | 7.1 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_bape` | ล็อก | 6 | 0 | 1 | 12.2 | 6 | BAT BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | withme_bape withme_bape_sp |
| `weapon_bearx` | ล็อก | 10 | 11 | 0 | 29.9 | 10 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_boom` | ล็อก | 5 | 0 | 0 | 3.9 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_bubblegum` | ล็อก | 5 | 0 | 0 | 5.8 | 5 | BOTTLE KNUCKLE POOLCUE REVOLVER |  |
| `weapon_core` | เปิดได้ | 63 | 40 | 10 | 65 | 32 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_daffy` | ล็อก | 10 | 0 | 0 | 36.8 | 10 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_eclipse` | เปิดได้ | 2 | 0 | 0 | 2 | 1 | POOLCUE | eclipse_fx |
| `weapon_effects` | เปิดได้ | 0 | 0 | 0 | 24 | 0 |  | 1nfx_weapon_effects eclipse_fx effect_energygreen effect_hw gb_extremr_gang_mad gb_extremr_gang_stepfiaw prticle_stpfiaw starlight_rgb stl_green stl_handrgb |
| `weapon_elys` | เปิดได้ | 6 | 0 | 0 | 11.2 | 6 | BAT BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | wm_elys |
| `weapon_extreme` | เปิดได้ | 6 | 5 | 0 | 4 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | extreme_fx |
| `weapon_flood_bite` | เปิดได้ | 5 | 5 | 0 | 6.5 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | fb_charging plyx_effect_fb3 |
| `weapon_frostburn_lava` | ล็อก | 5 | 0 | 0 | 4.1 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_green` | ล็อก | 6 | 6 | 0 | 5.2 | 6 | BOTTLE KNIFE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_green_dragon` | ล็อก | 5 | 0 | 0 | 4 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_halloween` | เปิดได้ | 3 | 0 | 0 | 2.8 | 3 | BOTTLE POOLCUE REVOLVER |  |
| `weapon_lego` | เปิดได้ | 12 | 12 | 0 | 13.1 | 6 | BAT BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | lego |
| `weapon_lightning_strike` | ล็อก | 1 | 1 | 0 | 1.4 | 1 | POOLCUE |  |
| `weapon_monchhichi_knuckle` | ล็อก | 1 | 1 | 1 | 10.8 | 1 | KNUCKLE |  |
| `weapon_monchhichi_m9` | ล็อก | 1 | 1 | 1 | 3.3 | 1 | BOTTLE |  |
| `weapon_monchhichi_poolcue` | ล็อก | 1 | 1 | 1 | 9.5 | 1 | POOLCUE |  |
| `weapon_monchhichi_revolver` | ล็อก | 1 | 1 | 0 | 6.6 | 1 | REVOLVER |  |
| `weapon_onikage` | เปิดได้ | 10 | 5 | 0 | 14.1 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | onikage_fx |
| `weapon_poker` | ล็อก | 4 | 0 | 0 | 8.1 | 4 | BOTTLE KNUCKLE POOLCUE REVOLVER |  |
| `weapon_rabbit` | ล็อก | 2 | 0 | 0 | 2.2 | 2 | BOTTLE POOLCUE |  |
| `weapon_rainbow` | ล็อก | 1 | 0 | 2 | 0.3 | 1 | KNIFE |  |
| `weapon_rgb` | ล็อก | 5 | 5 | 0 | 23.1 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_royalblood` | ล็อก | 5 | 0 | 0 | 2.9 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |
| `weapon_ryx` | ล็อก | 6 | 0 | 1 | 17.3 | 6 | BAT BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | wishme_ryx |
| `weapon_starlight_wing` | เปิดได้ | 2 | 1 | 0 | 3 | 1 | POOLCUE | starlight_wing_fx |
| `weapon_virex` | ล็อก | 6 | 0 | 1 | 5.6 | 5 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER | wishme_virex |
| `weapon_white_rabbit` | เปิดได้ | 1 | 1 | 1 | 0.4 | 1 | POOLCUE |  |
| `weapon_winter_frost` | ล็อก | 10 | 10 | 0 | 20.9 | 10 | BOTTLE KNUCKLE MACHETE POOLCUE REVOLVER |  |

## ชื่อที่ใช้แล้ว

ห้ามตั้ง `id` หรือ `skinType` ซ้ำกับรายการนี้

BAPE, BEARXBLACK, BEARXWHITE, BOOM, CANDY, CARBON, CHROMIUM, CRYBABY, CUTESTAR, DARKCHOCOLATE, ECLIPSE, EIGHTBIT, ELYS, ENDLESSLOVE, EXTREME, FLOODBITE, GOLDX, GREENDRAGON, HALLOWEEN, JANGWATRADE, KRADIKJUU, LAVA, LEGO, LIGHTNINGSTRIKE, LOOKPRAJAOTAK, MAIDAIDI, MONCHHICHI, MORNING, ONELOVE, ONIKAGE, POKER, PUPPY, QOQO, RABBIT, RAINBOW, RGB, RICH, ROYALBLOOD, RYX, SPLASHROD, STARLIGHT_WING, STEPFIAW, STLGREEN, THUNDERX, VIREX, WHITERABBIT, WINTERFROSTBLACK, WINTERFROSTWHITE

## จุดที่ควรตรวจ

- Component ที่หา `.ydr` ไม่เจอใน `[weapon]`: 1
  - `COMPONENT_SKIN_KNIFE_ONIKAGE` -> `w_me_onikage_knife`
- Component ที่ไม่มี attach point ใน meta อาวุธ: 0
- Model ที่ไม่มีใน `weaponarchetypes.meta`: 0 (เกมใช้ค่า lodDist สำรอง ไม่ใช่ข้อผิดพลาดเสมอไป)
- `.ydr` ที่ไม่มี component หรือ archetype อ้างถึง: 4
  - `lazy_blackhole_fx` ใน `weapon_virex`
  - `thunderxefx` ใน `weapon_core`
  - `thunderxefx_anim` ใน `weapon_core`
  - `w_me_poolcue_rgb` ใน `weapon_core`
- ไฟล์ stream ชื่อซ้ำข้าม resource: 1
  - `eclipse_fx.ypt` ใน weapon_eclipse, weapon_effects
