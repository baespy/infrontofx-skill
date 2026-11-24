# Recipes: ของกลม (ถ้วย ฐาน puck โคม ไห marker)

`scripts/blender/recipes/rounds.py` คือ builder ของทรงหมุนรอบแกน z: ฐาน puck ซ้อนชั้นมีห่วงคาด, ถ้วยรางวัลบนฐานเลข, เหรียญ, ห่วงชูชีพ, กลองบุนวม, โคมไฟ, ไหน้ำผึ้งมีน้ำเชื่อมไหลและฝา, วงแหวน marker ที่พื้น ทุกชิ้นเป็น `lathe`/`round_cyl`/`torus` ใน SDF ที่ fillet เข้าหากัน งานนูน (โล่ ใบลอเรล ป้าย) เดินตามผิวโค้งของ lathe ไม่ใช่แผ่นแบนแปะ ตัวเลขทรงทั่วไปอยู่ใน `references/smooth-craft.md` ไฟล์นี้บอกค่าที่ recipe ใช้และผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| แท่นกลม ฐานรางวัล ฐานวางของ หลายชั้นมีห่วงคาด | `pedestal` (หรือ `puck`, `torus_trim`) |
| ถ้วยรางวัลบนฐานมีเลข โล่ ใบลอเรล | `trophy` (หรือ `trophy_cup`, `numbered_plinth`, `shield_relief`, `laurel`) |
| เหรียญหนาขอบมน มีห่วงขอบและลายนูนสองหน้า | `coin` |
| ห่วงชูชีพลายสลับ | `lifebuoy` |
| กลองหรือถังบุนวมเป็นลอนตั้ง มีเบาะบนและห่วงคาด | `padded_drum` (หรือ `fluted_drum`, `cushion`) |
| โคมไฟตั้งพื้นหรือแขวน แก้วเรืองแสง | `lantern` |
| ไห โถ แจกัน น้ำเชื่อมไหลรอบปาก ฝามีปุ่ม | `vase` + `pour_glaze` + `lid` |
| วงแหวน marker ที่พื้น ไม่มีกล่องชน | `ring_marker` |

ไม่ใช้ตระกูลนี้เมื่อ:

- วงกลมใหญ่ระดับแมพ (ลานกลม บันไดวง ขอบทาง) ใช้ `SweepBuilder` (`references/map-pieces.md`) หรือ `references/recipes-mapkit.md`
- ภาชนะทรงกล่อง ใช้ `references/recipes-containers.md`
- ของกลมเล็กเป็นชิ้นส่วนของ prop อื่น เรียก `puck`/`coin` ใน builder เดียวกับชิ้นนั้นได้เลย

recipe เรียกได้จาก Python เท่านั้น สเปก JSON ของ `forge_sculpt.py` เรียก recipe ไม่ได้

## 2. โครงร่วมของตระกูล

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `RoundsRecipes(engine=None, engine_dir=None)` | โหลด `sculpt_forge` เอง (`self.sf`) ทุก method รับ builder `b` เป็นอาร์กิวเมนต์แรก |
| `RoundsPalette.roles()` | 10 role: 9 role บ้าน (`honey` และ `gold` เป็น gloss) + `glow` (`#FFE9B8` emissive) |
| `RoundsPalette.scheme("house" / "pastel")` | slot `body`, `accent`, `dark`, `metal`, `warm`, `glow`, `stripe`, `drum`, `band`, `soft`, `roof` → role |
| `rim` ของ puck | สัดส่วนของความสูงที่เป็นรัศมีขอบ: 0.5 = โค้งเต็ม (กฎ puck 50%), 0.25-0.35 = ท็อปแบนกว่า |
| lathe + Chaikin | `dome`, `bulge`, `recess` ทำให้ puck เปลี่ยนจาก `round_cyl` เป็น `lathe` ที่ profile ผ่าน Chaikin `smooth` รอบ (ค่าเริ่ม 2) |
| งานนูนบนผิวโค้ง | `lathe_relief`/`laurel`/`pour_glaze` สร้างเปลือกที่ offset จาก profile ของ lathe แล้ว intersect กับ outline ที่ยื่นตาม `azimuth` (-90 = ด้านหน้า -Y) งานนูนจึงหนาเท่ากันทั้งแผ่นและโค้งตามผิว |
| ลายสีบนทรงเดิม | `paint_band` (แถบสีเรียบเสมอผิว), `raised_band` (แถบนูน 3 mm), `paint_sectors` (ลายสลับเป็นเสี้ยว) ทำจากสำเนาที่ขยาย 0.05-2 mm แล้วตัดด้วย `cut` |
| ค่าที่คืน | dict ที่มี `node`, `top`, `radius`, `profile`/`outer` (เส้น profile สำหรับวางงานนูน) ใช้ต่อชิ้นถัดไปได้ |

demo สร้าง builder ด้วย `SculptBuilder("<set>_<key>", budget, lod_dist, colliders, set_name, archetype, voxel, palette, default_role)` งบเฉพาะชิ้น

## 3. builder และค่าที่ใช้

| method | ทำอะไร | พารามิเตอร์หลัก (ค่าเริ่ม) | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `puck(b, radius, height, rim=0.5, z=0, xy=(0, 0), dome=0, bulge=0, recess=0, role, fillet, op, collide, detail, smooth=2)` | แผ่นกลมขอบมน | | ขอบ `rim` × ความสูง, `dome` โป่งบน, `bulge` ข้างป่อง, `recess` ก้นเว้า |
| `torus_trim(b, host_radius, z, minor=0.025, sink=0.3, ...)` | ห่วงคาดรอบ host | | ฝัง 30% ของ minor (กฎปลอก 30-50%), minor 2.5 cm (กฎห่วง torus 1.5-3 cm) |
| `pedestal(b, tiers, z=0, trim_role=None, trim_minor=0.025, trim_sink=0.3, joint_fillet=0.02, trim_fillet=0.01, collide=True)` | puck ซ้อนตาม `tiers` แต่ละชั้นเริ่มที่ไหล่ชั้นล่างลบขอบของตัวเอง ห่วงคาดทุกรอยต่อ | `tiers` = list ของ dict (`radius`, `height`, `rim`, `dome`, `bulge`, `recess` เฉพาะชั้นแรก, `role`) | demo: ชั้นล่าง r 0.60 สูง 0.24 rim 0.35 ชั้นบน r 0.49 สูง 0.30 rim 0.25, ห่วง minor 2.6 cm |
| `numbered_plinth(b, digit="1", radius=0.31, height=0.32, base_radius=0.36, base_height=0.13, rim=0.25, base_rim=0.5, ...)` | ฐานสองชั้น + ป้ายนูนตามผิว + เลขพอง | `plaque_size` (0.2, 0.135), `plaque_relief` 0.014, `digit_height` 0.1, `digit_relief` 0.016, `digit_depth` 0.035 | ป้ายนูน 1.4 cm (กฎ relief 1-2 cm), เลขยื่นจากป้าย 1.6 cm |
| `trophy(b, cup_height=1.15, digit="1", z=0, ..., plinth=True, handles=True, shield=True, laurel=True, font=None, leaves=6)` | ฐานเลข + ถ้วย lathe มีขอบปาก torus + หูสองข้าง + โล่นูนสามชั้น + กิ่งลอเรลสองข้าง | ทุกขนาดคูณจาก `cup_height` (h) | ฐาน r 0.35h ชั้นล่าง r 0.40h, หู r 0.032h (3.7 cm) fillet 0.022, ขอบปาก minor 0.026h, โล่ 0.27h × 0.30h นูน 0.014h, ใบลอเรล 0.085h × 0.034h นูน 0.012h |
| `coin(b, radius, thickness, center, rot=(90, 0, 0), edge=0.3, dome=None, rim=True, emblem="star", emblem_size=0.48, double_sided=True, ...)` | เหรียญ lathe โป่งสองหน้า ห่วงขอบ ลายดาว หัวใจ หรือข้อความ | | ขอบ 30% ของความหนา, โป่ง 3% ของ r, ห่วง minor 0.075r ห่างขอบ 0.15r, ลายนูน 0.16 × หนา + 0.85 × โป่ง |
| `lifebuoy(b, major=0.2, minor=0.062, center, rot=(90, 0, 0), segments=8, role, stripe_role, fillet=0.012)` | ห่วง torus + ลายสลับ `segments` เสี้ยว | | ลายใช้ `paint_sectors` (ขยาย 2 mm ขอบ 1.5 mm) |
| `padded_drum(b, radius=0.52, height=0.62, base_radius=0.78, base_height=0.14, staves=16, bulge=0.045, buoy=True, buoy_azimuth=-128, ...)` | ฐาน puck + กลองลอนตั้ง + ห่วงคาดล่างบน + เบาะ + ห่วงชูชีพพิงข้างเอียง 9° | | ลอน 16 ลอนป่อง 4.5% ของ R (กฎ 14-18 ลอน, 4-5%), กลองหลอมฐาน 0.025, ห่วงคาด minor 3-3.4 cm ฝัง 42% |
| `fluted_drum(b, radius=0.5, height=0.6, staves=16, bulge=0.045, sharpness=0.55, edge=None, ...)` | ทรงกระบอกลอนตั้งจาก outline ยืด | | ขอบ min(0.1R, 0.12 × ความสูง) |
| `lantern(b, height=1.12, z=0, bars=6, frame_role, glass_role, roof_role, metal_role, foot_role, hanger=True, collide=True)` | ฐาน puck, ฐานโคม lathe, แก้วเรืองแสง, แถบรัดบนล่าง, ซี่ 6 ซี่, หลังคา lathe, ลูกยอด, ห่วงแขวน | ทุกขนาดคูณ `height` / 1.12 | ซี่ r 2.4 cm, แก้ว rim 0.06 (ขอบเกือบคม) ป่อง 2.2 cm, emissive เฉพาะแก้ว |
| `vase(b, height=0.78, belly_radius=0.42, foot_radius=None, neck_radius=None, lip_radius=None, belly_at=0.44, shoulder_at=0.86, lip=True, ...)` | ไห lathe ท้องป่อง ไหล่ คอ ปาก | ค่าเริ่มตีน 0.58, คอ 0.72, ปาก 0.80 × รัศมีท้อง | คืน `outer` (เส้นผิวนอก) ให้ `pour_glaze` และ `lathe_relief` |
| `pour_glaze(b, curve, z_top, z_edge, thickness=0.018, depth_in=0.025, drips=7, drip_length=(0.08, 0.17), drip_width=(0.05, 0.075), seed=3, ..., drip_fillet=0.022)` | เปลือกน้ำเชื่อมหนา 1.8 cm คลุมบน `z_edge` มีหยดย้อย | | หยดกว้าง 5-7.5 cm (กฎ 5-8 cm) ยาว 8-17 cm, หยดหลอมขอบเปลือก 0.022 |
| `lid(b, radius, z, dome=0.11, knob_radius=0.06, role, knob_role, fillet=0.012)` | ฝาโดม + คอปุ่ม + ปุ่มกลม | | ปุ่มหลอมฝา 0.022 |
| `ring_marker(b, radius=0.72, tube=0.05, disc=0.036, inner=0.62, dome=0.014, recess=0.018, pad=0.02, icon="star", icon_size=0.24, arrow=True, ...)` | แผ่นกลม + แผ่นในสีอ่อน + ห่วง torus + ไอคอนนูน + แท็บลูกศร | | ห่วง R 0.72 minor 5 cm (กฎห่วงพื้น R 0.6-0.8 m minor 4-5 cm), demo ตั้ง `ring_role` และ `arrow_role` เป็น `glow` |

ส่วนช่วยอื่น: `smooth_profile(profile, iterations=2)`, `raised_band`, `paint_band`, `paint_sectors`, `lathe_relief`, `shield_relief`, `laurel`, `trophy_cup`, `cushion` และ `RoundsMath` (`puck_profile`, `coin_profile`, `cup_profile`, `vase_profile`, `lid_profile`, `shield_outline`, `drip_outline`, `fluted_outline`)

## 4. fillet ต่อรอยต่อที่ recipe ใช้

| รอยต่อ | k |
| --- | --- |
| ชั้น pedestal / ห่วงคาด | 0.02 / 0.01 |
| เหรียญบนแท่น (group demo) / ห่วงขอบเหรียญ / ลายเหรียญ | 0.03 / 0.008 / 0.006 |
| ถ้วยกับฐาน (group `cup`) / ขอบปาก / หู | 0.02 / 0.012 / 0.022 |
| โล่ / พื้นในโล่ / ดาวในโล่ / ลอเรล | 0.008 / 0.005 / 0.004 / 0.008 |
| ป้ายบนฐาน / เลข | 0.007 / 0.005 |
| กลองกับฐาน / ห่วงคาด / เบาะ / ห่วงชูชีพ | 0.025 / 0.012 / 0.02 / 0.014 |
| ฐานโคม / แก้ว / แถบ / ซี่ / หลังคา / ยอด / ห่วงแขวน | 0.02 / 0.01 / 0.014 / 0.014 / 0.016 / 0.02 / 0.014 |
| น้ำเชื่อม (group) / หยด / ขอบ mask | 0.012 / 0.022 / 0.008 |
| ฝา / คอปุ่ม / ปุ่ม | 0.012 / 0.02 / 0.022 |
| แผ่นใน marker / ห่วง / ไอคอน / ลูกศร | 0.006 / 0.018 / 0.01 / 0.016 |

## 5. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): 2,548 tris, `SCULPT_QA fail=0 warn=3`, `validate_prop` fail=0 warn=0

```python
import importlib
import os
import sys


class HoneyJar:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        rnd = self.module("rounds")
        recipes = rnd.RoundsRecipes()
        engine = recipes.sf
        s = rnd.RoundsPalette.scheme("house")
        palette = engine.SetPalette("1nfx_cafe", rnd.RoundsPalette.roles())
        b = engine.SculptBuilder("1nfx_cafe_jar", budget=2600, lod_dist=120.0, set_name="1nfx_cafe", archetype="pot", voxel=0.004, palette=palette, default_role=s["body"])
        pot = recipes.vase(b, height=0.78, belly_radius=0.42, foot_radius=0.25, neck_radius=0.30, lip_radius=0.335, role=s["body"], lip=False)
        recipes.pour_glaze(b, pot["outer"], 0.77, 0.56, role=s["warm"])
        recipes.lid(b, 0.35, 0.745, dome=0.11, knob_radius=0.062, role=s["accent"], knob_role=s["metal"])
        return b.build(self.out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = HoneyJar(argv[0], argv[1]).build()
    print("HONEY_JAR tris={} blend={}".format(result["tris"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -P '<project>\work\cafe\honey_jar.py' -- '<skill>' '<project>\work\cafe\build'
```

- `SculptBuilder` ไม่มี `finish()` จบด้วย `b.build(out_dir)` (ผลตาม `references/pipeline.md` หัวข้อ 8)
- `RoundsRecipes(engine_dir=None)` หา `sculpt_forge.py` จากอาร์กิวเมนต์, env `SCULPT_FORGE_DIR` หรือโฟลเดอร์รอบไฟล์ recipe ใต้ MCP ส่ง `engine_dir=r"<skill>\sculpt-forge\scripts\blender"` หรือส่งโมดูล engine ที่โหลดแล้วเป็น `engine=`
- งานนูนต้องใช้เส้น `outer`/`profile` จากชิ้นที่สร้างจริง (ค่าที่ method คืน) ถ้าคำนวณ profile เองแล้วไม่ตรง งานนูนจะลอยหรือจม
- marker ที่ไม่ต้องชนให้ส่ง `colliders=0` ที่ builder `validate_prop` จะขึ้น `no collision (marker / decoration)` เป็น OK
- หลายชิ้นในชุดเดียวใช้ `SetPalette` ชุดเดียวกัน ไม่งั้น engine เขียน `<set>_pal_<sha8>.png` เพิ่ม

## 6. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\rounds'

& $blender -b --factory-startup -P "$sf\recipes\rounds.py" -- --out $work
& $blender -b --factory-startup -P "$sf\recipes\rounds.py" -- --out $work --only pedestal --budget-scale 1.4 --no-render
& $blender -b --factory-startup -P "$sf\recipes\rounds.py" -- --out "$work\pastel" --variant pastel --set 1nfx_roundp
```

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--out <dir>` | ต้องใส่ | โฟลเดอร์ผล |
| `--only a,b` | ทุกชิ้น | key: `trophy`, `pedestal`, `drum`, `lantern`, `honeypot`, `marker` |
| `--engine-dir <dir>` | หาเอง | โฟลเดอร์ที่มี `sculpt_forge.py` |
| `--set` | `1nfx_round` | ชื่อชุด (id เป็น `<set>_<key>`) |
| `--variant` | `house` | `house` หรือ `pastel` |
| `--voxel V` | ค่าของแต่ละชิ้น | ทับทุกชิ้น |
| `--budget-scale` | 1.0 | คูณงบทุกชิ้น (ขั้นต่ำ 500) |
| `--no-qa` | | ข้าม `validate_sculpt` และ `validate_prop` |
| `--no-render` | | ข้าม `render_sculpt.py` |
| `--views`, `--res` | 4, 900 | turntable และขนาดภาพ |

ผล: `<set>_<key>.blend`, `_high/`, `<set>_pal.png`, `qa/<id>.json`, `qa/qa_all.json`, `renders/`, `rounds_report.json` (ต่อชิ้น: `sculpt_qa.lines`, `contract`, `dihedral_deg`, `surface_dev_mm`, `shells` และ `summary`) บรรทัดที่พิมพ์: `ROUNDS_PROP`, `ROUNDS_QA <id> SCULPT_QA fail=N warn=M` ตามด้วยบรรทัด WARN/FAIL, `ROUNDS_CONTRACT <id> RESULT fail=N warn=M`, `SCULPT_RENDER`, `ROUNDS_RESULT`, `ROUNDS_FAIL` (build พัง) headless คืน exit code 1 เมื่อ build พัง หรือ `SCULPT_QA`/`validate_prop` fail

## 7. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, variant `house`, `SculptBuilder` ธรรมดา, set `1nfx_round` (รัน 6 ตระกูลพร้อมกัน เวลาจึงสูงกว่ารันเดี่ยว)

| id | builder | voxel | ขนาด (m) | tris / งบ | tris/m² | วินาที | `SCULPT_QA` | `validate_prop` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1nfx_round_trophy` | `trophy` ถ้วย 1.15 m เลข 1 | 0.005 | 1.44 × 0.97 × 1.58 | 3,920 / 4,000 | 599 | 21.5 | fail=0 warn=5 | 0 / 0 |
| `1nfx_round_pedestal` | `pedestal` 2 ชั้น + `paint_band` + `coin` | 0.005 | 1.20 × 1.20 × 1.01 | 2,548 / 2,600 | 630 | 6.0 | fail=1 warn=4: `deviation` p95 7.10 mm, `sagitta` p99 5.0 mm (WARN) | 0 / 0 |
| `1nfx_round_drum` | `padded_drum` | 0.005 | 1.56 × 1.56 × 0.86 | 3,528 / 3,600 | 511 | 14.0 | fail=1 warn=5: `lumpiness` wobble 2.40° | 0 / 0 |
| `1nfx_round_lantern` | `lantern` | 0.004 | 0.62 × 0.62 × 1.15 | 2,156 / 2,200 | 1,033 | 9.0 | fail=1 warn=5: `lumpiness` roughness 3.81° | 0 / 0 |
| `1nfx_round_honeypot` | `vase` + `pour_glaze` + `lid` | 0.004 | 0.85 × 0.84 × 1.01 | 2,548 / 2,600 | 954 | 9.4 | fail=0 warn=3 | 0 / 0 |
| `1nfx_round_marker` | `ring_marker` (`colliders=0`) | 0.005 | 1.44 × 1.44 × 0.22 | 1,468 / 1,500 | 394 | 3.9 | fail=0 warn=4 | 0 / 0 |

ทั้งชุด `qa_fail=3 qa_warn=26`, `validate_prop` fail=0 warn=0 ทุกไฟล์, render 6/6 ทุกชิ้นเป็น 1 shell

การแก้ที่ลองแล้ว:

| เปลี่ยน | ผล |
| --- | --- |
| pedestal งบ × 1.4 (3,640) | 3,566 tris (880 tris/m²), `fail=0 warn=4` (`deviation` p95 1.07 mm, sagitta ผ่าน), `validate_prop` 0 / 0 |
| drum งบ × 1.4 (5,040) | ยัง FAIL `lumpiness` wobble 2.58° |
| lantern งบ × 1.4 (3,080) | ยัง FAIL `lumpiness` roughness 3.66° |

## 8. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key ที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| clay: ขอบแท่นกว้างเป็นเหลี่ยม ชั้นล่างเป็นคลื่น zebra: แถบหักเป็นขั้น | `deviation` FAIL p95 7.10 mm, `sagitta` WARN (เหลี่ยม R 0.14 m ~8 ด้าน) | ของกลม Ø 1.2 m ที่ 630 tris/m² ได้ด้านไม่พอ (กฎ R 0.5-1 m ต้อง 36-48 ด้าน) | งบ × 1.4 (880 tris/m²) ผ่าน (วัดแล้ว) ของกลม Ø ≥ 1 m เริ่มที่ ~850-900 tris/m² |
| zebra: แถบซิกแซกบนลอนกลองและเบาะ จุดแตกที่ห่วงคาดล่างกับฐาน และที่ห่วงชูชีพแตะกลอง | `lumpiness` FAIL wobble 2.40°, `folds` WARN 18 ขอบ | ลอนตั้ง 16 ลอนบนผิว 6.9 m² normals ส่ายข้ามสามเหลี่ยมใหญ่, fold อยู่ที่ z ≈ 0.15 m (ห่วงคาดล่าง), ≈ 0.54 m (จุดที่ห่วงชูชีพแตะ) และ ≈ 0.7 m (เบาะ) | เพิ่มงบ 40% ไม่พอ (วัดแล้ว) ลองลด `staves` หรือ `bulge` แล้ววัดใหม่ ห้ามส่งโดยไม่ดู zebra |
| clay: ซี่โคมเป็นปล้อง ผิวหลังคามีก้อน | `lumpiness` FAIL roughness 3.81°, `folds` WARN 6 ขอบ | ซี่ r 2.4 cm 6 ซี่บนชิ้นเล็ก fold อยู่ที่ปลายซี่ชนแถบรัดบน (z ≈ 0.6-0.65 m) | เพิ่มงบ 40% ไม่พอ (วัดแล้ว) ลดจำนวน `bars` หรือขยายซี่แล้ววัดใหม่ |
| clay: ใบลอเรลและดาวในโล่เป็นเศษยับบนถ้วย | `dihedral` WARN p90 36.3°, `flat_panels` WARN | งานนูนบาง (1.4-2.5 cm) บนถ้วย 1.58 m ที่ 599 tris/m² | ผ่านเกณฑ์ตัวเลข แต่ดูภาพก่อนส่ง ถ้ายับให้ลด `leaves` หรือตัด `laurel=False` |
| colour: แถบสีบนแท่นเป็นฟันเลื่อย | | `paint_band` เรียบเสมอผิว เส้นแบ่งสีขึ้นกับ voxel | คง `smooth_roles`/`crisp_roles` ของ engine ไว้ หรือใช้ `raised_band` ที่นูน 3 mm ให้เส้นแบ่งเป็นขั้นจริง |
| งานนูนลอยจากผิวหรือหายเข้าไปในเนื้อ | `deviation` | ส่ง `curve` ที่ไม่ใช่ profile ของชิ้นจริง หรือ `azimuth` ผิดด้าน | ใช้ `outer`/`profile` ที่ method คืน และ `azimuth=-90` สำหรับด้านหน้า |
| ส่วนที่ high มีแต่ low ไม่มี | `deviation` high → low max สูง (โคม 205 mm, ไห 57 mm) | speck หรือโพรงที่ repair ทิ้ง | เปิด clay และ turntable ดูว่าหายส่วนที่มองเห็นไหม (ห่วงแขวน ปุ่มฝา) |
| palette หลายแผ่นในโฟลเดอร์เดียว | | หลายสคริปต์ใช้ `set_name` เดียวกันแต่ role ต่างกัน | ใช้ `RoundsPalette.roles()` ชุดเดียวทุกชิ้น |

อ่านภาพตาม `references/qa.md` หัวข้อ 5: แถบที่วนเป็นวงรอบของกลมเป็นเรื่องปกติ แถบที่หักเป็นขั้นตามแนวตั้งคือด้านไม่พอ แถบซิกแซกบนลอนคือ wobble

## 9. ประตู QA

1. build แล้วอ่าน `SCULPT_PROP` (หรือ `ROUNDS_PROP`) tris ต้องไม่เกินงบ
2. `validate_sculpt.py --blend <out>\<id>.blend --high <out>\_high\<id>_high.blend` ต้องได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว ของกลมให้ดู `sagitta` เป็นพิเศษ
3. `render_sculpt.py` แล้วเปิด clay, zebra, colour และ turntable ทุกชิ้น ดู silhouette ของขอบกลมจากด้านข้าง
4. prop-forge `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์
5. export ด้วย `export_prop.py --format native --max-res 512 --shared-ytd <set>_tex` (ไม่ใส่ `--factory-startup`) ตาม `references/pipeline.md` หัวข้อ 13
6. รายงานว่ายังไม่ได้ทดสอบในเกม marker ที่หมุนหรือลอยทำด้วยสคริปต์ spawn ตาม `prop-forge/references/integration.md`

ชิ้น demo ที่ยัง fail (`1nfx_round_pedestal` ที่งบเดิม, `1nfx_round_drum`, `1nfx_round_lantern`) ห้ามส่งตามสภาพนั้น
