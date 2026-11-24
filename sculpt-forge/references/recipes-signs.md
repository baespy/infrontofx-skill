# Recipes: ป้ายและตัวอักษรพอง

`scripts/blender/recipes/signs.py` คือ builder ป้ายพองสำเร็จรูป 6 แบบบน `SculptBuilder` ทุกแบบจบเป็น prop ชิ้นเดียวที่ผ่านสัญญา prop-forge: แผ่นป้ายขอบมนจริง, คำหลักพองสามชั้น (plaque → outline → ตัวอักษร), piping ที่เดินตาม outline, เสาและฐานที่ fillet เข้าหากัน, กล่องชนตั้งให้แล้ว ตัวเลขทรงทั่วไปอยู่ใน `references/smooth-craft.md` ไฟล์นี้บอกเฉพาะค่าที่ recipe ใช้และผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| ป้ายร้านหัวเมฆบนเสาคู่ คำหลักคำเดียว | `lobed_plaque_sign` |
| ป้ายจุดจอด หัวโค้งบนเสาเดี่ยว มีป้ายกลมกลางเสา | `stop_sign` |
| เสาป้ายชี้ทาง หัวลูกศร มีจอเล็กบนเสา | `arrow_pillar` |
| totem ข้อมูล จอใหญ่จมในตัว มีแผ่น sticker บนหัว | `totem` |
| ป้ายร้านทรง squircle หัวหยัก มีไอคอนใต้คำ | `squircle_sign` |
| ป้ายตั้งโต๊ะ ตัวเขียนเส้นเดียว (monoline) | `script_plaque` |

ไม่ใช้ตระกูลนี้เมื่อ:

- ป้ายใหญ่เกิน ~3 m หรือเป็นส่วนของแมพ ใช้ `SweepBuilder` ตาม `references/map-pieces.md`
- ข้อความรองหลายบรรทัด ทำเป็น texture บนโมดูลนูน ตัวอักษร 3D ใช้แค่คำหลักคำเดียว (`references/smooth-craft.md` หัวข้อ 5)
- ป้ายทรงคม low-poly ที่ไม่ต้องเนียน ใช้ archetype ของ prop-forge

recipe เรียกได้จาก Python เท่านั้น (CLI หรือ MCP) สเปก JSON ของ `forge_sculpt.py` เรียก recipe ไม่ได้

## 2. โครงร่วมของตระกูล

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `SignsBuilder.create(engine, prop_id, panel_tilt=9.0, hold=None, **kwargs)` | สร้าง subclass ของ `SculptBuilder` ที่รัน `PanelNormals.flatten` หลังโอน normals: หาแผงแบน (หน้าติดกันเอียงกัน ≤ 0.75°, พื้นที่ ≥ 0.003 m² หรือ 0.2% ของผิว) แล้วดึง corner normal ที่เอียงจากแผง ≤ `panel_tilt` ให้ตรงกับแผง หน้าป้ายจึงแบนคมขึ้น ส่ง `panel_tilt=0` และ `hold=None` ได้ `SculptBuilder` ธรรมดา `hold` (dict) ต่อ `PlanarHold` เข้าไปด้วย kwargs อื่นส่งต่อให้ `SculptBuilder` ทั้งหมด |
| `PlanarHold` (`hold={...}`) | ตัวเดียวกับ `PlanarHoldMixin` ของ cabinets: หลังย่อขั้นแรก (stage) รวมหน้าที่เอียงกัน ≤ `hold_angle` 2° เป็น n-gon, แผงที่ใหญ่ ≥ `hold_area` 0.01 m² ถูกตรึง vertex ขอบแผง (สุ่มให้ไม่เกิน `hold_share` 15% ของงบ) และเมื่อ `hold_reach` > 0 (ค่าเริ่ม 0.02) เลื่อนขอบแผงเข้าไปถึงจุดที่ผิวแบนจริง (`hold_tilt` 1°) แล้วจึงย่อขั้นสุดท้าย หน้าแผ่นจึงไม่เหลือสามเหลี่ยมยาวที่แผ่เป็นพัดจากโคนตัวอักษร `hold_flat` (m) ตรึงเฉพาะ n-gon ที่แบนไม่เกินค่านี้ key ที่รับ: `hold_angle`, `hold_area`, `hold_share`, `hold_reach`, `hold_tilt`, `hold_flat` ถ้า engine ไม่มี method ที่ต้องใช้ (`reduce`, `protection`, `clean_collapse`, `snap_role_lines`, `relabel_faces`, `discard`) จะข้ามไปเอง |
| `Field2D(blend, offset)` | outline 2D แบบ SDF หลายรูป union กันด้วย smooth-min `blend` (ลอนหัวเมฆหลอมกับตัวแผ่นแบบมน) `grown(d)` ขยายทั้ง field (ใช้ทำแผ่น outline ของคำ), `contour(-inset)` หาเส้นที่ห่างขอบเท่ากัน (ใช้เป็นเส้นทาง piping) |
| `slab(b, field, depth, edge, puff, ...)` | ยืด `Field2D` เป็นแผ่น SDF ผ่าน `primitive("extrude", ...)` ของ engine `edge` = รัศมีขอบแผ่น, `puff` = โดมหน้า |
| `layered_word(...)` | คำพองสามชั้น: แผ่น outline = ตัวอักษรขยาย `outline` × cap height ยื่น `plate_proud` แล้วตัวอักษรยื่นต่อ `letter_proud` ทั้งสองชั้นฝังลงชั้นล่าง `embed` |
| `Frame(origin, rot)` | วางทั้งป้ายด้วย `base` และหมุนด้าน (`turned(180)` ใช้ทำด้านหลัง) |
| `roles` | dict ทับ role ต่อส่วน key ตาม `SignsRecipes.families` เช่น lobed: `plaque`, `outline`, `letters`, `piping`, `post`, `foot` |
| `face_puff` | ค่าเริ่ม 0.0 หน้าแผ่นแบน ใส่ค่าบวกเพื่อโดมหน้าแผ่น demo ไม่ใช้แล้วเพราะ `hold` ทำหน้าแผ่นเรียบโดยไม่ต้องโป่ง |
| `ground=True` | `cut` ใต้ z = 0 fillet 0.012 ฐานเรียบวางพื้นได้ |
| `collide=True` | กล่องชนตั้งเองตามตัวป้ายและเสา (ไม่พึ่ง `colliders="auto"`) |
| `PartStats.tris(b, prop_id, parts)` | นับ tris ต่อส่วนหลัง build ใช้ดูว่าชิ้นไหนกินงบ (demo พิมพ์เป็น `SIGNS_PARTS`) |

ฟอนต์: ตัวอักษรของตระกูลนี้มาจาก `GlyphOutlines` (TTF → outline 2D → `Field2D`) ไม่ใช่ `text()` ของ engine `SignsRecipes(font)` รับพาธ TTF ส่ง `None` จะได้ฟอนต์ค่าเริ่มของ Blender ให้ใช้ `EngineLoader.font()` ที่หาจากอาร์กิวเมนต์, env `SCULPT_FORGE_FONT` แล้ว TitanOne ใน `prop-forge/assets/fonts/` ใต้ MCP ส่งพาธเต็ม

## 3. builder และค่าที่ใช้

ตัวเลขในวงเล็บคือค่าเริ่มเป็นเมตร

| method | ทำอะไร | พารามิเตอร์หลัก | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `lobed_plaque_sign(b, text="CAFE", base, ...)` | แผ่นหัวเมฆ 3 ลอนบนเสาคู่ + piping เปิดด้านล่าง + คำพอง | `width` 1.9, `height` 0.88, `thickness` 0.15, `lobes` 3, `lobe_amp` 0.13, `corner` 0.2, `lift` 1.12, `letter_height` 0.36, `piping_radius` 0.042, `piping_inset` 0.096, `piping_gap` 0.5, `post_spacing` 0.54, `post_radius` 0.058, `foot_radius` 0.16 | ขอบแผ่น 0.45 × หนา = 6.8 cm (กฎ slab 35-50%), piping r 4.2 cm = 2.2% ของความกว้าง (กฎ 1.5-3%) ห่างขอบ 2.3r ปลายท่อจบลูกกลม 1.35r, ฐานเสา Ø 32 cm ≈ 2.8 เท่าของ Ø เสา (กฎ 2.5-3 เท่า) |
| `stop_sign(b, text="BUS", base, ...)` | ฐานกลมสองชั้น เสาแคปซูล ป้ายกลมมีห่วงขอบ ซุ้มหัวโค้งมีท่อขอบสองหน้า ยอดหัวใจหรือดาว | `height` 2.75, `arch_width` 0.68, `arch_height` 0.86, `arch_depth` 0.12, `disc_radius` 0.32, `disc_z` 1.62, `post_radius` 0.05, `letter_height` 0.2, `finial` "heart"/"star"/None, `icon` "star"/"heart", `double_sided` True, `text_back` True | เสา Ø 10 cm (กฎ 8-10 cm), ขอบซุ้ม 0.4 × หนา = 4.8 cm, ท่อขอบ r 2.7 cm (ขอบสี 2-3.5 cm) ห่างขอบ 5.6 cm, ฐานมน 44-46% ของความสูงฐาน |
| `arrow_pillar(b, text="PARK", base, ...)` | ฐานสองชั้น เสาเหลี่ยมมน จอจมใน frame หัวลูกศรพอง แถบรัด คำสองหน้า ดาวบนหัว | `pillar_height` 1.86, `pillar_size` (0.34, 0.3), `head_length` 1.34, `head_height` 0.46, `head_depth` 0.27, `head_offset` 0.26, `direction` 1.0 (ลบ = ชี้ซ้าย), `letter_height` 0.2, `back_text` True, `screen` True, `finial` "star" | เสามน 22% ของด้านสั้น (บล็อกของเล่น 15-20%+), ขอบหัว 0.34 × หนา = 9.2 cm, จอ 0.17 × 0.13 จมหลัง frame มน (emissive แค่จอ), หัวต่อเสา fillet 0.035 |
| `totem(b, text="INFO", base, ...)` | ตู้ `pillow_box` จอใหญ่จมใน recess ท่อทองรอบจอ คำล่าง sticker เมฆบนหัว | `width` 0.86, `depth` 0.36, `height` 1.62, `screen` (0.6, 0.66), `letter_height` 0.16, `sticker` True, `puff` (0, 0, 0) | ตัวมน r 9 cm = 25% ของความลึก, ท่อทอง r 2.4 cm เดินตามผิวหมอนห่างจอ 6.8 cm, sticker ขอบ 3 cm หนา 5 cm (กฎ die-cut ขอบ 1.5-2.5 cm หรือ 3-5% ของความกว้าง) |
| `squircle_sign(b, text="MART", base, ...)` | แผ่น squircle หัว 5 ลอน ท่อขอบ เส้นแบ่ง คำบน ไอคอนล่าง | `width` 1.0, `height` 1.3, `lobes` 5, `lobe_amp` 0.07, `exponent` 5.0, `thickness` 0.18, `letter_height` 0.19, `rim_inset` 0.094, `rim_radius` 0.04, `icon` "bag"/"star"/None | ลอนสูง 7 cm = 5.4% ของความสูง (กฎ 4-6%), ขอบแผ่น 0.44 × หนา = 7.9 cm, ท่อขอบ r 4 cm ห่างขอบ 2.35r, เส้นแบ่ง r 3.2 cm เหนือกึ่งกลางแผ่น 17% ของความสูง แยกโซนคำกับไอคอน |
| `script_plaque(b, word="hello", base, ...)` | ฐานหมอน แผ่นเอนหลัง 8° ขอบท่อหนา ตัวเขียนเส้นเดียวจากท่อ ไอคอนหัวใจ | `width` 1.3, `height` 0.66, `thickness` 0.08, `corner` 0.16, `rim_radius` 0.05, `x_height` 0.19, `tube_radius` 0.021, `tilt` 8.0, `icon` "heart"/None | ขอบแผ่น 0.42 × หนา = 3.4 cm, ตัวเขียนเป็นท่อ Ø 4.2 cm ฝังลงหน้า 45% ของ r (กฎ 30-50%) จุด i/j เป็นลูกกลม 1.3r, ฟอนต์เส้นเดียวมีแค่ a-z 0-9 `-` `!` `.` และเว้นวรรค |

ทุก builder รับ `face_puff`, `roles`, `ground`, `collide` และคืน dict ของ node แต่ละส่วน

ส่วนประกอบที่เรียกเองได้:

| method | ทำอะไร | ค่าที่ใช้ |
| --- | --- | --- |
| `layered_word(b, text, frame, face, height=0.3, max_width=None, centre=(0, 0), outline=0.075, plate_proud=0.016, letter_proud=0.026, embed=0.011, puff=0.0, roles=None, fillets=(0.015, 0.01))` | คำพองสามชั้นบนหน้า `face` (ค่า y ของผิวหน้าใน frame) | outline 7.5% ของ cap height (กฎ 5-8%), แผ่นยื่น 1.6 cm (1-2 cm), ตัวอักษรยื่น 2.6 cm (2-3 cm), ขอบตัวอักษร min(0.46 × ความหนาชั้น, 7.5% ของ cap) ใส่ `max_width` เสมอกันคำชนท่อขอบ |
| `piping(b, frame, path2d, depth_y, radius, closed=False, terminals=1.35, role=None, fillet=None)` | ท่อตามเส้น 2D บนระนาบ XZ ของ frame | fillet ค่าเริ่ม 0.42r, ปลายเปิดจบลูกกลม 1.35r |
| `disc_sign(b, frame, centre, radius=0.32, depth=0.12, rim=0.07, icon="star", icon_scale=0.5, double_sided=True)` | ป้ายกลม ห่วงขอบ ไอคอนนูนสองหน้า | ขอบป้าย 0.3 × หนา, ไอคอนหนา 4.6 cm ยื่น 2.6 cm |
| `sticker_plate(b, frame, art, centre, border=0.022, thickness=0.04, art_lift=0.0045, double_sided=True)` | แผ่น die-cut ขยายจาก `art` (Field2D) ด้วย `border` + ช่องรูปนูน 4.5 mm | คืน `slot` (centre, size, plane, role) ไว้วางรูปภายหลัง ตอนนี้ช่องเป็นสี role `art` ล้วน |
| `post(b, frame, x, top, radius=0.058, foot_radius=0.16, foot_height=0.12, fillet=0.032)` | เสาแคปซูลบนฐานกลมขอบมน 45% | fillet เสาเข้าแผ่น 0.55r |
| `script_word(b, word, frame, face, x_height=0.19, tube_radius=0.021, embed=0.45, fillet=0.007)` | ตัวเขียนเส้นเดียวจาก `tube` ใน group เดียว | ปลายเส้นลูกกลม 1.0r |
| `bag_icon`, `cloud_art(width=0.5, star=True)`, `cloud_top_field`, `lobed_squircle_field` | ไอคอนถุง, รูปเมฆสำหรับ sticker, outline หัวเมฆ, outline squircle หยัก | |

## 4. fillet ต่อรอยต่อที่ recipe ใช้

| รอยต่อ | k |
| --- | --- |
| แผ่น outline ของคำเข้าแผ่นป้าย | 0.014-0.016 |
| ตัวอักษรเข้าแผ่น outline | 0.009-0.011 |
| piping เข้าหน้าแผ่น | 0.3-0.42r (ป้ายเมฆ 0.018 บน r 0.042) |
| เสาเข้าแผ่นและฐาน | 0.032-0.034 |
| ซุ้มเข้าเสา / ป้ายกลมเข้าเสา | 0.028 / 0.024 |
| หัวลูกศรเข้าเสา | 0.035 |
| ตัว totem และ squircle เข้าฐาน | 0.035 |
| recess จอ (subtract) | 0.010-0.014 |
| ไอคอนนูน | 0.010 |
| ตัวเขียนเส้นเดียว (group / ท่อ / จุด) | 0.007 / 0.005 / 0.004 |
| ตัดพื้น | 0.012 |

## 5. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): 3,920 tris, `SCULPT_QA fail=0 warn=5`, `validate_prop` fail=0 warn=0 ถ้าลดงบเหลือ 3,000 (2,940 tris) คำ SHOP ได้ `deviation` p95 4.83 mm (FAIL) และ `flat_panels` tilt mean 38.5° เทียบกับ 14.7° ที่งบ 4,000

```python
import importlib
import os
import sys


class ShopSign:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        signs = self.module("signs")
        loader = signs.EngineLoader()
        engine = loader.module()
        recipes = signs.SignsRecipes(loader.font())
        b = signs.SignsBuilder.create(engine, "1nfx_cafe_shop", budget=4000, lod_dist=120.0, set_name="1nfx_cafe", archetype="sign", palette=dict(signs.DemoSet.palette), default_role="cream", voxel=0.005)
        recipes.squircle_sign(b, text="SHOP")
        return b.build(self.out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = ShopSign(argv[0], argv[1]).build()
    print("SHOP_SIGN tris={} blend={}".format(result["tris"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -t 6 -P '<project>\work\cafe\shop_sign.py' -- '<skill>' '<project>\work\cafe\build'
```

- `SculptBuilder` ไม่มี `finish()` จบด้วย `b.build(out_dir)` ซึ่งคืน dict ผล (`tris`, `blend`, `high_blend`, `metrics`, ...) ตาม `references/pipeline.md` หัวข้อ 8
- `EngineLoader(engine_dir=None)` หา `sculpt_forge.py` จากอาร์กิวเมนต์, env `SCULPT_FORGE_DIR` หรือโฟลเดอร์แม่ของ recipe ตามลำดับ
- ผ่าน MCP: โหลดด้วย `runpy.run_path(r"<skill>\sculpt-forge\scripts\blender\recipes\signs.py", run_name="signs_recipes")` ห้ามใช้ `run_name="__main__"` (จะรัน demo ทั้งชุด) ส่งฟอนต์เป็นพาธเต็ม และ build ซ้ำด้วย CLI 4.2.3 ก่อน export ถ้าฉากเป็น 5.x
- ป้ายหลายชิ้นในสคริปต์เดียวกันใช้ `set_name` และ palette ชุดเดียวกัน ถ้า role ต่างกันในโฟลเดอร์เดียว engine เขียน `<set>_pal_<sha8>.png` เพิ่ม (วัดแล้ว) ชุดจะมี palette หลายแผ่น
- ตัวอย่างนี้ไม่ได้ส่ง `hold` จึงยังมีเงาพัดบนหน้าแผ่น ป้ายจริงให้ส่ง `hold={}` แบบ demo ป้ายที่มีเสาเหลี่ยม ฐานขั้น หรือกรอบจอให้ใช้ `hold={"hold_reach": 0.0, "hold_share": 0.08}` (ค่าใน `DemoSet.props` หัวข้อ 7)

## 6. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\signs'

& $blender -b --factory-startup -t 6 -P "$sf\recipes\signs.py" -- --out $work
& $blender -b --factory-startup -t 6 -P "$sf\recipes\signs.py" -- --out $work --only 1nfx_sign_stop --budget 3600 --no-render
```

จำกัดเธรดเสมอ: `QARunner.run` ส่ง `-t <bpy.context.scene.render.threads>` ให้ Blender ลูก (`validate_sculpt`, `validate_prop`, `render_sculpt`) ลูกจึงใช้เธรดเท่าตัวแม่ที่รันด้วย `-t 6` และรันทีละตัวผ่าน `subprocess.run` ห้ามรันหลายตระกูลพร้อมกัน

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--out <dir>` | `<temp>\sculpt_forge_signs` | โฟลเดอร์ผล |
| `--only id1,id2` | ทุกชิ้น | build เฉพาะ id ของ demo |
| `--engine-dir <dir>` | หาเอง | โฟลเดอร์ที่มี `sculpt_forge.py` |
| `--font <ttf>` | TitanOne ของ prop-forge | ฟอนต์ของคำพอง |
| `--voxel` | 0.005 | voxel ทุกชิ้น |
| `--budget` | 0 (ใช้งบของแต่ละชิ้น) | ทับงบทุกชิ้น |
| `--no-qa` | | ข้าม `validate_sculpt`, `validate_prop` และ render |
| `--no-render` | | ข้าม `render_sculpt.py` |
| `--res` | 900 | ขนาดภาพ render |

ผล: `<id>.blend`, `_high/<id>_high.blend`, `1nfx_sign_pal.png`, `qa/<id>.json` และ `.log` (`validate_sculpt --target prop --high`), `qa/sculpt_qa.json`, `qa/validate_prop.log`, `renders/` (clay, zebra, colour, turntable, lineup) และ `signs_report.json` บรรทัดที่พิมพ์: `SIGNS_PROP`, `SIGNS_PARTS`, `SIGNS_QA`, `PROP_QA`, `SIGNS_RENDER`, `SCULPT_QA fail=N warn=M`, `SIGNS_DONE` headless คืน exit code 1 เมื่อมีชิ้นที่ `SCULPT_QA` fail

## 7. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, voxel 0.005, `lod_dist` 120, set `1nfx_sign`, engine ที่มี `SurfaceRefiner`, ประตู QA v2 (`references/qa.md` หัวข้อ 3.1) รันตระกูลเดียว `-t 10` ด้วย `run_seq.ps1` คอลัมน์ `hold` คือค่า `"hold"` ใน `DemoSet.props`

| id | recipe | `hold` | ขนาด (m) | tris / งบ | tris/m² | วินาที | `SCULPT_QA` | `validate_prop` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1nfx_sign_word` | `lobed_plaque_sign` CAFE, `piping_radius` 0.05 | `{}` | 1.90 × 0.33 × 2.13 | 3,820 / 3,900 | 662 | 17.9 | fail=0 warn=3 (`folds` 4 ขอบ, `normal_error`, `deviation` p95 1.42 mm) | 0 / 0 |
| `1nfx_sign_stop` | `stop_sign` BUS, `text_back=False` | `{}` | 0.78 × 0.54 × 2.94 | 2,448 / 2,500 | 697 | 12.6 | fail=0 warn=3 (`dihedral` p90 43.5°, `normal_error`, `deviation` p95 2.58 mm) | 0 / 0 |
| `1nfx_sign_arrow` | `arrow_pillar` PARK | `{"hold_reach": 0.0, "hold_share": 0.08}` | 1.31 × 0.70 × 2.55 | 3,624 / 3,700 | 689 | 8.6 | fail=0 warn=3 (`folds` 11 ขอบ 0.013%, `normal_error`, `deviation` p95 1.06 mm) | 0 / 0 |
| `1nfx_sign_totem` | `totem` INFO | `{"hold_reach": 0.0, "hold_share": 0.08, "hold_flat": 0.001}` | 1.06 × 0.56 × 2.14 | 3,864 / 3,950 | 673 | 11.6 | fail=0 warn=1 (`normal_error`) | 0 / 0 |
| `1nfx_sign_shop` | `squircle_sign` MART, `rim_radius` 0.048 | `{}` | 1.08 × 0.46 × 1.44 | 2,940 / 3,000 | 662 | 19.2 | fail=0 warn=4 (`dihedral` p90 36.5°, `folds` 2 ขอบ, `normal_error`, `deviation` p95 1.93 mm) | 0 / 0 |
| `1nfx_sign_script` | `script_plaque` hello | `{}` | 1.31 × 0.36 × 0.72 | 1,910 / 1,950 | 665 | 16.8 | fail=0 warn=5 (`split_edges` 3.9%, `dihedral` p90 37.5°, `folds` 3 ขอบ, `normal_error`, `deviation` p95 1.25 mm) | 0 / 0 |

ทั้งชุด `SCULPT_QA fail=0 warn=19` (ก่อน `hold` ด้วยประตู v2 fail=0 warn=25, ประตูเดิม fail=1 warn=30), `validate_prop` ทุกไฟล์ fail=0 warn=0, render 6/6 WARN `flat_panels` (เงาพัดสามเหลี่ยมรอบตัวอักษร) หายจากทุกชิ้น ค่าเริ่มของ builder ยังเป็น `face_puff` 0.0 และ demo ไม่ส่ง `face_puff` แล้ว

การแก้ที่วัดแล้ว:

| เปลี่ยน | ผล |
| --- | --- |
| `hold={}` ทุกชิ้น (word/shop/stop ไม่ใส่ `face_puff`) | เงาพัดบนหน้าแผ่นหายทุกป้าย: word warn 5 → 3, shop 5 → 4, stop 4 → 3, script 5 → 5 (`flat_panels` หาย แทนด้วย `dihedral`) แต่ arrow และ totem ได้ `deviation` FAIL p95 4.7 / 4.4 mm (pins ขอบแผงของเสาเหลี่ยม ฐานขั้น และกรอบจอแย่งงบชิ้นเล็ก) |
| arrow / totem `hold_reach` 0 | totem ผ่าน (warn 1) แต่มีสามเหลี่ยมมืดบนแผ่น sticker, arrow ยัง FAIL `deviation` 4.60 mm |
| arrow `hold_share` 0.05 + `hold_area` 0.05 | fail=0 แต่มีสามเหลี่ยมมืดบนหัวเสาใต้ป้าย |
| arrow / totem `hold_reach` 0 + `hold_share` 0.08 (totem + `hold_flat` 0.001) | ผ่านและภาพเรียบ: arrow warn 3 `deviation` 1.06 mm, totem warn 1 (ค่า demo) |
| shop `panel_tilt` 25 | `normal_error` p99 18.9° FAIL จึงไม่ใช้ |

แถวล่างวัดด้วยประตูเดิมก่อนมี `hold`:

| เปลี่ยน | ผล |
| --- | --- |
| word `face_puff` 0.04 + `piping_radius` 0.042 → 0.05 | fail 1 → 0: roughness 3.26 → 2.09° (หน้าแผ่นโป่งเป็นผิวโค้งใหญ่ที่ quadric fit ได้ดี ท่อหนาขึ้นได้ด้านต่อรัศมีมากขึ้น) |
| shop `face_puff` 0.04 + `rim_radius` 0.04 → 0.048 | fail 1 → 0: roughness 3.85 → 2.14° |
| word / shop `face_puff` 0.025 | ยัง FAIL roughness 3.33 / 3.21° |
| stop `face_puff` 0.035 | fail 1 → 0: `deviation` p95 3.19 → 2.98 mm (เส้นฉิวเฉียด) |
| stop `double_sided=False` | fail=0 `deviation` 2.94 mm แต่หลังป้ายเปล่า ไม่ใช้เป็นค่าเริ่ม |
| stop งบ 2,560 | ยัง FAIL `deviation` 3.05 mm |
| script `rim_radius` 0.056, `tube_radius` 0.024, `thickness` 0.1, `face_puff` 0.04/0.06, งบ 2,000 | roughness 3.3-4.5° ยัง FAIL (`face_puff` ทำตัวเขียนลอย/จม `deviation` 3.8-4.8 mm) |
| script `panel_tilt` 20 (ดึง normals หน้าแผ่นให้แบนแรงขึ้น) | หน้าแผ่นหายคลื่นแต่ `normal_error` p99 15.6° FAIL จึงไม่ใช้ |

งบต่อส่วน (`SIGNS_PARTS`) บอกว่างบไปอยู่ที่ไหน: ป้ายเมฆ แผ่น 1,273 / piping 926 / ตัวอักษร 531 + outline 320 / ฐานเสา 507 / เสา 263, totem ตัว 957 / sticker 727 + รูป 432 / ท่อทอง 402 / ตัวอักษร 516 + outline 220 ท่อหนึ่งเส้นรอบป้ายกินงบ 10-25%

งบ demo ตั้งไว้ราว 660-700 tris/m² (เพดานงานนี้ ~700) พอเมื่อใส่ `hold` ให้หน้าแผ่นเรียบและท่อหนา ≥ 4.8 cm คำที่มีตัวโค้งมาก (S, O, C) หรือชิ้นย่อยเยอะ ใส่ `hold` และขยายท่อก่อนเพิ่มงบ

## 8. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key ที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| clay: รอยทแยงเป็นพัดหรือกากบาทบนหน้าแผ่นเรียบ (ใต้เส้นแบ่งของ squircle, หน้า script, หน้าซุ้ม) zebra: แถบแผ่เป็นรัศมีจากมุมแผง | `flat_panels` WARN (tilt mean 15-41°) | แผ่นแบนใหญ่เหลือสามเหลี่ยมใหญ่ไม่กี่ชิ้นที่วิ่งจากโคนตัวอักษรถึงขอบ normals ที่โอนมาเอียงที่มุม | `hold={}` (วัดแล้ว: หายทุกป้ายที่งบเท่าเดิม) ไม่ต้องเพิ่มงบหรือโป่งหน้าแผ่น |
| สามเหลี่ยมมืดบนแผ่นเล็ก (sticker, หัวเสา) หรือขอบเสาเหลี่ยมและกรอบจอเป็นเหลี่ยมหลังใส่ `hold` | `deviation` FAIL p95 4-5 mm | `hold_reach` เลื่อนขอบแผง และ pins 15% ของงบตรึงแผงเล็กจำนวนมาก ชิ้นย่อยเหลืองบน้อย | `{"hold_reach": 0.0, "hold_share": 0.08}` (+ `hold_flat` 0.001 ถ้าแผงโค้งน้อยๆ ถูกตรึง) วัดแล้วกับ arrow และ totem |
| clay: ตัวอักษรยับ ขอบแผ่นและท่อเป็นปล้อง zebra: แถบหักฟันเลื่อย | `lumpiness` (ประตูเดิม FAIL roughness 3.2-3.9°) | ประตูเดิมนับความโค้งของท่อขอบและขอบมนเป็นก้อน ประตู v2 วัดเทียบ high แล้วได้ 0.2-0.3° | ถ้า zebra ยังหักจริงบนผิวใหญ่ให้ขยายท่อขอบ 15-20% ตัวอักษรต้องสูง ≥ ~0.15 m ที่ voxel 5 mm |
| colour: คำที่มีตัวโค้งเป็นเหลี่ยม เส้นสี outline เป็นฟันเลื่อย | `deviation` FAIL, `sagitta` WARN | งบต่อพื้นที่ต่ำ (SHOP ที่ 3,000 = 670 tris/m²: deviation p95 4.83 mm, sagitta p99 5.1 mm) | งบ 4,000 (≈ 890 tris/m²) ผ่าน `fail=0` (วัดแล้ว) |
| clay: ซุ้มและห่วงของ `stop_sign` เป็นเหลี่ยม | `deviation` p95 ~3 mm, `dihedral` p90 43° | 13 ส่วนย่อยแบ่งงบ 2,500 (ท่อขอบสองหน้า, ห่วงป้ายกลม, ดาวสองหน้า) | `hold={}` ได้ 2.58 mm (วัดแล้ว) หรือ `double_sided=False` (2.94 mm แต่หลังป้ายเปล่า) |
| clay: ท่อตัวเขียนเป็นปล้อง หน้าแผ่น script เป็นคลื่นเป็นพัดจากโคนตัวอักษร | `split_edges`, `dihedral` | ตัวเขียนกินงบ 38% ของชิ้น คลื่นบนหน้าแผ่นคือ normals เอียงจาก fillet โคนตัวอักษรกระจายบนสามเหลี่ยมใหญ่ | `hold={}` ทำหน้าแผ่นเรียบ (วัดแล้ว) อย่าใช้ `face_puff` กับ script (ตัวเขียนลอย) แถบที่วนเป็นระเบียบรอบท่อคือดีไซน์ |
| คำชนท่อขอบหรือเลยขอบแผ่น | | ไม่ได้ส่ง `max_width` ตอนเรียก `layered_word` เอง | builder สำเร็จรูปคำนวณ `max_width` ให้แล้ว ถ้าเรียกเองให้ใส่ความกว้างภายในท่อขอบลบ 0.1-0.24 m |
| palette หลายแผ่นในโฟลเดอร์เดียว | | หลายสคริปต์ใช้ `set_name` เดียวกันแต่ role ต่างกัน | หนึ่งชุดหนึ่ง palette (`DemoSet.palette` หรือ dict เดียวกันทุกชิ้น) |

กฎอ่านภาพทั้งหมดอยู่ใน `references/qa.md` หัวข้อ 5 แถบ zebra ที่วนเป็นระเบียบตามลอนหัวป้าย ท่อ และตัวอักษรคือดีไซน์ แถบที่หักกระจายบนแผ่นเรียบคือปัญหา

## 9. ประตู QA

1. build แล้วอ่าน `SCULPT_PROP` (หรือ `SIGNS_PROP`) tris ต้องไม่เกินงบ
2. `validate_sculpt.py --blend <out>\<id>.blend --high <out>\_high\<id>_high.blend` ต้องได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว (demo ทำให้ทุกชิ้นใน `qa/<id>.log`)
3. `render_sculpt.py` แล้วเปิดดู `<id>_clay.png`, `<id>_zebra.png`, `<id>_colour.png`, `<id>_turntable.png` ทุกใบ ดูหน้าแผ่น ตัวอักษร และด้านหลัง (คำและไอคอนสองหน้า)
4. prop-forge `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์
5. export ด้วย `export_prop.py --format native --max-res 512 --shared-ytd <set>_tex` (ไม่ใส่ `--factory-startup`) ตาม `references/pipeline.md` หัวข้อ 13
6. รายงานว่ายังไม่ได้ทดสอบในเกมจนกว่าผู้ใช้จะเห็นเอง ดูตอนกลางคืนด้วย: ป้ายสีน้ำตาลมืดต้องมีจุดเรืองแสงหรือตัวสีอ่อน (`references/smooth-craft.md` หัวข้อ 14)

ทุกชิ้น demo ผ่าน `SCULPT_QA fail=0` (ประตู v2 + `hold`) WARN ที่เหลือ (`normal_error` ที่ร่องตัวอักษร, `deviation` 1-2.6 mm, `dihedral` ของท่อและห่วงเล็ก, `folds` ไม่กี่ขอบ) อธิบายได้ตามหัวข้อ 8 ชิ้นใหม่ที่ได้ FAIL ห้ามส่งตามสภาพนั้น แก้ตามตารางหัวข้อ 8 แล้ววัดใหม่
