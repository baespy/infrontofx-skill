# Recipes: ตู้และเครื่อง

`scripts/blender/recipes/cabinets.py` คือ builder ตู้ทรงของเล่นที่ตั้งพื้น ขนาด 0.7-2.5 m: ตู้ ATM, ตู้คีบ/กาชา, kiosk ร้านค้ามีหลังคาและกันสาด, เคาน์เตอร์ทรง flight case และตู้เค้กสองบาน ทุกตัวเป็นตัว `pillow_box` ขอบมนจริงบนฐานมน แผงหน้าเป็นโมดูลนูนหรือร่องที่ fillet เข้ากับตัว ไม่มีกรอบเส้นเข้มรอบแผง ตัวเลขทรงทั่วไปอยู่ใน `references/smooth-craft.md` ไฟล์นี้บอกค่าที่ recipe ใช้และผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| ตู้ ATM จอจม ปุ่มกด ช่องบัตร ช่องเงิน คำพอง ฝาไอซิ่งหยด | `atm` |
| ตู้คีบหรือกาชา โดมแก้วบนตัวตู้ มือหมุน ช่องหยอดเหรียญ | `claw_machine` |
| kiosk ร้านค้า เคาน์เตอร์ เสาสี่ต้น หลังคาเบาะ กันสาดลายทาง ป้ายคำ | `market_kiosk` |
| เคาน์เตอร์ร้าน ทรงกล่องเดินทาง มีขอบกันกระแทก มุมครอบ หูจับ | `flight_case` |
| ตู้สองบาน ฐานขา มงกุฎหมอน แถวลูกปัด | `cake_cabinet` |
| ตู้แบบอื่น | ประกอบเองจากส่วนในหัวข้อ 4 |

ไม่ใช้ตระกูลนี้เมื่อ:

- ตู้เซฟ ใช้ `vault_safe` ใน `references/recipes-containers.md`
- ชุด archetype ทรงคม low-poly 2,400-4,800 tris ที่ไม่ต้องเนียน ใช้ prop-forge
- ชิ้นสูงเกิน ~3 m หรือชิ้นสถาปัตย์ ใช้ `SweepBuilder` (`references/map-pieces.md`)

recipe เรียกได้จาก Python เท่านั้น สเปก JSON ของ `forge_sculpt.py` เรียก recipe ไม่ได้

## 2. โครงร่วมของตระกูล

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `CabinetsRecipes(theme="house", roles=None, font=None)` | `theme` `house` (cream/caramel/ink + honey/gold) หรือ `pastel` (pink/mint/sky) แมป slot เช่น `shell`, `body`, `panel`, `trim`, `base`, `screen`, `glass`, `key` ไปเป็น role `roles` ทับ slot ทีละตัว |
| `palette(cell_px=32)` | palette ของชุด 11 role: 9 role บ้านใน `references/smooth-craft.md` + `glass` (`#D6EAF4` gloss) + `screen` (`#FFE9BC` emissive) |
| `EngineLoader.builder_class(engine, hold=True)` | คืน `CabinetSculptBuilder` (`PlanarHoldMixin` + `SculptBuilder`) ถ้า signature ของ `reduce`, `protection`, `clean_collapse`, `snap_role_lines`, `relabel_faces`, `discard` ใน engine ตรงกับที่ mixin ต้องการ ไม่ตรงจะคืน `SculptBuilder` ธรรมดาโดยไม่เตือน |
| `PlanarHoldMixin` | หลังย่อขั้นกลาง: `dissolve_limit` 2° หาแผงแบน ≥ 0.01 m², เลื่อน vertex ขอบแผงเข้าหาผิวที่แบนจริง (เอียง ≤ 1°) ไม่เกิน 2 cm, triangulate แล้วปักหมุด vertex ไม่เกิน 15% ของงบ ย่อรอบจริงเลี่ยงหมุด แผงหน้าจึงแบนและขอบแผงตรง ผลอยู่ใน `planar_hold` ของ report (`regions`, `pins`, `snapped`) |
| `group` ต่อโซน | ทุก builder แบ่ง group ตามรอยต่อ: ตัวกับฐาน, แผงหน้า, ป้ายคำ, ไอซิ่ง เพื่อให้แต่ละโซนมี fillet ของตัวเอง (หัวข้อ 5) |
| กล่องชน | `add_collider` เพิ่มกล่องรอบตัวและหลังคา/โดม ทุก builder คืน `parts["colliders"]` |
| `suggest_budget(area_m2, density=560.0, extra=0.15, minimum=1800)` | งบจากพื้นที่ผิว: area × 1.15 × 560 ปัดหลักร้อย |

demo สร้าง builder ด้วย `size_class="hero"`, `stage_ratio=2.0`, `lod_dist` 120 (kiosk 150) และงบเฉพาะชิ้น

## 3. builder สำเร็จรูป

ตัวเลขในวงเล็บคือค่าเริ่มเป็นเมตร รัศมีตัวตู้ = `radius_pct` × ด้านที่สั้นที่สุด (ขั้นต่ำ 12 mm)

| method | ทำอะไร | พารามิเตอร์หลัก | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `atm(b, ...)` | ฐาน, ตัวตู้, จอจม, แป้น 3 × 4 + ปุ่มข้าง 3 ปุ่ม, ช่องบัตร, ช่องเงิน, หัวใจนูน, คำพอง, ฝาไอซิ่งหยัก หยด และสายไหลสองข้าง | `width` 0.78, `depth` 0.6, `height` 1.62, `plinth` 0.12, `radius_pct` 0.09, `label` "ATM", `beads` False, `seed` 5 | ขอบตัว 9% ของความลึก = 5.4 cm (กฎ ATM 4-5 cm, ตู้ 7-10%), จอ 0.44 × 0.30 ใน bezel 4 cm, คำสูง 0.16 m outline 1.1 cm (6.9%, กฎ 5-8%), ฝาไอซิ่งหนา 5.2 cm ยื่น 3 cm ลอน 2.2 cm 6 ลอนต่อเมตร (กฎ 4-6 / 2-4 / 2-4 cm), หยดยาว 10-22 cm r 2.3-3.2 cm |
| `claw_machine(b, ...)` | ตัวตู้ฐานมน, ช่องรับของจม, โดมแก้ว, ปลอกคอ torus, ฝา, ปุ่มบน, ก้านหมุน, ช่องเหรียญ, ดาวนูนสองข้าง | `width` 0.72, `depth` 0.66, `base_h` 0.9, `dome` 0.31, `plinth` 0.09, `radius_pct` 0.12 | ขอบ 12% = 7.9 cm (กึ่งตู้กับบล็อกของเล่น), ปลอกคอ minor 3.4 cm ปิดรอยต่อโดมกับตัว (กฎปลอก torus 1.5-3 cm), ฝาขอบมน 42% ของความสูงฝา, กล่องชนสองกล่อง (ตัว + โดม) |
| `market_kiosk(b, ...)` | ฐาน, เคาน์เตอร์, ท็อป, ร่องหน้ามีแผงหมอนและดาว, เสา 4 ต้นมีลูกกลมที่โคน, หลังคาหมอน, ป้ายคำบนหลังคา, กันสาด, แถวลูกปัด | `width` 1.36, `depth` 0.76, `counter` 1.0, `roof_z` 2.06, `roof_h` 0.16, `plinth` 0.1, `stripes` 9, `label` "SHOP", `beads` True | ขอบตัว 6.5 cm (8.5%), ท็อปหนา 7.5 cm ขอบ 3.3 cm (44%, กฎ slab 35-50%), เสา Ø 8.4 cm (กฎ 8-10 cm), หลังคาโป่งบน 2 cm, ป้ายหนา 8 cm ขอบ 42%, ลูกปัด Ø 3.8 cm (กฎ 3-4 cm), demo ใช้ voxel 0.006 เพราะสูง 2.5 m |
| `flight_case(b, ...)` | ตัวกล่อง, ขอบกันกระแทกทุกสันและแถบกลาง, มุมครอบ 8 มุม, ร่องหน้าแผงหมอนดาว, latch สองตัว, หมุด, หลุมจับข้าง + หูจับ | `width` 1.2, `depth` 0.62, `height` 0.96, `lift` 0.03, `radius_pct` 0.06 | ขอบตัว 6% = 3.7 cm เพราะขอบกันกระแทก 8 cm (มน 2.4 cm) ครอบสันอยู่แล้ว, มุมครอบ 13 cm มน 4.5 cm ยื่น 1.8 cm, แถบกลางที่ 0.76 × ความสูง |
| `cake_cabinet(b, ...)` | ตัวตู้บนขากลม, มงกุฎหมอน, ร่องประตูสองบาน, ประตูหมอน, หัวใจนูน, ลูกบิด, แถวลูกปัดใต้มงกุฎ | `width` 0.84, `depth` 0.58, `height` 1.36, `feet` 0.08, `radius_pct` 0.1, `beads` True | ขอบ 10% = 5.8 cm, ร่องประตูลึก 1.8 cm fillet 0.8 cm (กฎร่อง 1-2.5 cm, fillet 0.8-1.2 cm), ประตูโป่ง 1.6 cm, มงกุฎโป่งบน 1.2 cm |

ทุก builder รับ `roles` (ทับ slot) และคืน dict ของ node พร้อม `colliders`

## 4. ส่วนประกอบสำหรับประกอบเอง

`face_y` คือ y ของผิวหน้า (ด้านหน้า -Y) ส่วนนูนวางหน้า `face_y` ส่วนฝังลงผิว `embed`

| method | ทำอะไร | ค่าเริ่มและเหตุผล |
| --- | --- | --- |
| `body(b, size, base_z=0.0, center=(0, 0), radius=None, radius_pct=0.085, puff=0.0, role=None, fillet=0.0, collide=False)` | ตัวตู้ `pillow_box` | รัศมี max(12 mm, `radius_pct` × ด้านสั้น) ตามกฎตู้ 7-10% และขอบที่เห็นได้ ≥ 12 mm |
| `plinth(b, size, base_z=0.0, center=(0, 0), roll=0.45, role=None, fillet=0.0)` | ฐาน `round_box` | ขอบ 45% ของด้านสั้น (ฐานโค้งเกือบเต็ม) |
| `panel(b, center, size, face_y, depth=0.02, corner=0.03, edge=None, puff=0.0, embed=0.015, role=None, fillet=0.01, op="union", detail=False)` | แผงนูน rounded rect บนระนาบ XZ | ยื่น 2 cm ฝัง 1.5 cm ขอบ 0.45 × ความยื่น |
| `pocket(b, center, size, floor_y, corner=0.03, rim=0.008, role=None, op="subtract")` | ร่องลึกถึง `floor_y` | ขอบร่องมน 8 mm (กฎ 0.8-1.2 cm) |
| `recessed_screen(b, center, size, face_y, depth=0.02, bezel=0.04, bezel_depth=0.028, corner=0.03, rim=0.008, gap=0.012, roles=None, fillet=0.012)` | bezel + ร่อง + จอ emissive | จอจมหลัง bezel มน แสงอยู่แค่ในจอ (emissive 5-15% ของผิว) |
| `keypad(b, center, face_y, cols=3, rows=4, key=(0.054, 0.036), gap=0.012, key_depth=0.016, plate_depth=0.022, side_keys=3, side_key=(0.07, 0.042), roles=None, fillet=0.01)` | แผ่นรองและปุ่มใน group `keys` (fillet 0.004, `detail=True`) | ปุ่มยื่น 1.6 cm มน 0.48 × min(สูง, 2 × ยื่น) ปุ่มข้างใช้ slot `ok`/`clear`/`cancel` |
| `slot_module(b, center, face_y, size=(0.12, 0.07), depth=0.026, slit=(0.08, 0.012), slit_depth=0.016, corner=None, roles=None, fillet=0.01)` | ขอบนูน + ช่องผ่า | โมดูลยื่น 2.6 cm (กฎ 2-4 cm) |
| `letters(b, body, center, face_y, height=0.15, depth=0.026, puff=0.010, outline=0.014, outline_depth=0.012, lift=0.013, rise=0.022, max_width=None, roles=None, fillet=0.006)` | คำพองสองชั้นด้วย `text` | ตัวอักษรยื่นจาก outline 2.2 cm (กฎ 2-3 cm) ใส่ `max_width` เสมอ |
| `beads(b, points, radius=0.019, closed=False, pitch=1.9, blend=0.3, role=None, fillet=0.008)` | แถวลูกปัด | Ø 3.8 cm ห่าง 1.9r หลอมกัน 0.3r |
| `relief(b, shape, center, face_y, depth=0.024, edge=0.01, puff=0.006, embed=0.01, role=None, fillet=0.008, plane="XZ", rot=(0, 0, 0))` | ไอคอนนูนจาก `Shapes` dict | ยื่น 2.4 cm ขอบ 42% ของความยื่น |
| `icing_cap(b, size, top_z, center=(0, 0), thickness=0.052, overhang=0.03, sink=0.012, lobes_per_m=6.0, amp=0.022, dome=0.01, roles=None, fillet=0.02)` | ฝาไอซิ่ง `scalloped_rect` | ตามกฎฝาคลุมบน หนา 4-6 cm ยื่น 2-4 cm ลอน 2-4 cm |
| `edge_drips(b, size, top_z, center=(0, 0), offset=0.012, front=(2, 0.34), sides=3, back=3, length=(0.10, 0.22), radius=(0.023, 0.032), seed=5, roles=None, fillet=0.016)` | หยดรอบขอบฝา `front` = (จำนวน, ช่องว่างกลาง) | fillet ค่าเริ่ม 0.016 ต่ำกว่ากฎ 1.2-1.6r ของหยด ประกอบเองให้ส่ง `fillet=0.035` (kiosk ใน `references/qa.md`: 39 → 0 folds) |
| `cape_runs(b, size, top_z, center=(0, 0), drop=(0.62, 0.5), radius=(0.036, 0.03, 0.025), inset=0.014, roles=None, fillet=0.018)` | สายไหลยาวสองมุมหน้า | รัศมีเรียว 3.6 → 2.5 cm ปลายลูกกลม 1.2r |
| `awning(b, width, top_z, front_y, depth_back, stripes=9, length=0.27, thickness=0.05, tilt=24.0, wrap=2, puff=0.014, roll=0.0, roles=None, fillet=0.003)` | กันสาดแถบตัว U สลับสี อ้อมข้างละ `wrap` แถบ | หนา 5 cm โป่ง 1.4 cm (กฎ 4-5 cm, 1-1.5 cm) แถบกว้าง = ความกว้าง / `stripes` |
| `corner_caps(b, size, base_z, center=(0, 0), cap=0.13, radius=0.045, proud=0.018, levels=("bottom", "top"), role=None, fillet=0.01)` | มุมครอบหมอน 4 หรือ 8 มุม | |
| `edge_guards(b, size, base_z, center=(0, 0), guard=0.08, proud=0.012, cap=0.13, rails=True, mid=None, role=None, fillet=0.008)` | ขอบกันกระแทกสันตั้ง สันนอน และแถบกลาง `mid` | มน 0.3 × `guard` |
| `rivets(b, points, radius=0.012, sink=0.4, normal=(0, -1, 0), role=None, mirror_x=True, fillet=0.004)` | หมุดฝัง 40% ของ r | |

## 5. fillet ต่อรอยต่อที่ recipe ใช้

| รอยต่อ | k |
| --- | --- |
| ตัวตู้กับฐาน (group `shell`/`base`/`counter`) | 0.024-0.026 |
| โมดูลหน้า (group `front`) | 0.012 |
| ปุ่มกันเอง (group `keys`) | 0.004 |
| คำพอง (group `label`) | 0.006 (ตัวหน้า 0.8 × ของ outline) |
| ไอซิ่ง (group `icing`) / หยด / สายไหล | 0.02 / 0.016 / 0.018 |
| ร่อง subtract (ช่องรับของ, ร่องหน้า, ร่องประตู) | 0.008-0.012 |
| โดม ฝา ปุ่ม ของตู้คีบ | 0.012-0.022 |
| เสาและลูกกลมโคนเสา | 0.02 |
| หลังคาและป้ายบนหลังคา | 0.024 / 0.03 |
| แถบกันสาดกันเอง | 0.003 |
| ขอบกันกระแทกและมุมครอบ (group `case`) | 0.008-0.012 |
| ลูกปัด / หมุด | 0.008 / 0.004 |

## 6. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): 3,136 tris, builder `CabinetSculptBuilder`, `SCULPT_QA fail=0 warn=3`, `validate_prop` fail=0 warn=0

```python
import importlib
import os
import sys


class ClawCabinet:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        cab = self.module("cabinets")
        engine = cab.EngineLoader.load()
        recipes = cab.CabinetsRecipes(theme="pastel")
        builder = cab.EngineLoader.builder_class(engine)
        b = builder("1nfx_cafe_claw", budget=3200, voxel=0.005, stage_ratio=2.0, lod_dist=120.0, set_name="1nfx_cafe", archetype="gacha", palette=recipes.palette(), default_role="pink")
        recipes.claw_machine(b)
        result = b.build(self.out_dir)
        result["builder"] = builder.__name__
        return result


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = ClawCabinet(argv[0], argv[1]).build()
    print("CLAW_CABINET tris={} builder={} blend={}".format(result["tris"], result["builder"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -P '<project>\work\cafe\claw_cabinet.py' -- '<skill>' '<project>\work\cafe\build'
```

- `SculptBuilder` ไม่มี `finish()` จบด้วย `b.build(out_dir)` (ผลตาม `references/pipeline.md` หัวข้อ 8)
- พิมพ์ชื่อ builder ทุกครั้ง ถ้าได้ `SculptBuilder` แปลว่า engine เปลี่ยน signature และ planar hold ไม่ทำงาน
- `EngineLoader.load(explicit=None)` หา `sculpt_forge.py` จากอาร์กิวเมนต์, โฟลเดอร์แม่ของ recipe, env `SCULPT_FORGE_SCRIPTS` ใต้ MCP ให้ส่งโฟลเดอร์ `scripts/blender` ตรงๆ หรือโหลดด้วย `runpy.run_path(..., run_name="cabinets_recipes")` (ห้าม `__main__`)
- ตู้หลายชิ้นในชุดเดียวใช้ `recipes.palette()` ชุดเดียวกันทุกชิ้น ไม่งั้น engine เขียน `<set>_pal_<sha8>.png` เพิ่ม

## 7. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\cabinets'

& $blender -b --factory-startup -P "$sf\recipes\cabinets.py" -- --out $work
& $blender -b --factory-startup -P "$sf\recipes\cabinets.py" -- --out $work --only atm --budget 5200 --no-render
& $blender -b --factory-startup -P "$sf\recipes\cabinets.py" -- --out "$work\pastel" --theme pastel --only claw_machine,cake_cabinet
```

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--out <dir>` | ต้องใส่ (ไม่ใส่พิมพ์ `CABINETS_USAGE` แล้วจบ) | โฟลเดอร์ผล |
| `--only a,b` | ทุกชิ้น | id ของ demo หรือชื่อ method (`atm`, `claw_machine`, `market_kiosk`, `flight_case`, `cake_cabinet`) |
| `--theme` | `house` | `house` หรือ `pastel` |
| `--engine <dir>` | หาเอง | โฟลเดอร์ที่มี `sculpt_forge.py` |
| `--font <ttf>` | ฟอนต์ค่าเริ่มของ engine | ฟอนต์ของคำพอง |
| `--budget N`, `--voxel V` | ค่าของแต่ละชิ้น | ทับทุกชิ้นที่ build |
| `--plain` | | ปิด planar hold ใช้ `SculptBuilder` ธรรมดา |
| `--no-qa` | | ข้าม `validate_sculpt` และ `validate_prop` (ยัง render) |
| `--no-render` | | ข้าม `render_sculpt.py` |

ผล: `<id>.blend`, `_high/<id>_high.blend`, `1nfx_cab_pal.png`, `qa/<id>_qa.json` และ `.log` (`validate_sculpt --high`), `qa/cabinets_qa.json`, `qa/validate_prop.log`, `qa/render.log`, `renders/` และ `cabinets_report.json` (`builder`, `builds[].planar_hold`, `qa`, `prop_contract`) บรรทัดที่พิมพ์: `CABINETS_BUILD`, `CABINETS_QA`, `CABINETS_PROP_CONTRACT`, `CABINETS_RENDER`, `CABINETS_DONE`, `CABINETS_FAIL` (build พัง) headless คืน exit code 1 เมื่อ build พังหรือ `SCULPT_QA` fail

## 8. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, theme `house`, builder `CabinetSculptBuilder`, set `1nfx_cab` (รัน 6 ตระกูลพร้อมกัน เวลาจึงสูงกว่ารันเดี่ยว)

| id | method | voxel | ขนาด (m) | tris / งบ | tris/m² | วินาที | `SCULPT_QA` | `validate_prop` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1nfx_cab_atm` | `atm` | 0.005 | 0.89 × 0.70 × 1.62 | 4,116 / 4,200 | 701 | 17.8 | fail=1 warn=4: `dihedral` p90 46.4° | 0 / 0 |
| `1nfx_cab_gacha` | `claw_machine` (role pastel) | 0.005 | 0.80 × 0.79 × 1.59 | 3,136 / 3,200 | 693 | 6.7 | fail=0 warn=3 | 0 / 0 |
| `1nfx_cab_kiosk` | `market_kiosk` | 0.006 | 1.77 × 1.05 × 2.51 | 8,036 / 8,200 | 599 | 20.2 | fail=1 warn=4: `folds` 49 ขอบ | 0 / 0 |
| `1nfx_cab_case` | `flight_case` | 0.005 | 1.25 × 0.70 × 1.01 | 3,588 / 3,700 | 677 | 9.6 | fail=3 warn=3: `folds` 14 ขอบ (0.22% ของผิว), `lumpiness` roughness 3.95°, `deviation` p95 5.89 mm | 0 / 0 |
| `1nfx_cab_cake` | `cake_cabinet` | 0.005 | 0.92 × 0.67 × 1.37 | 3,332 / 3,400 | 680 | 7.7 | fail=2 warn=2: `dihedral` p90 54.9°, `folds` 39 ขอบ | 0 / 0 |

ทั้งชุด `SCULPT_QA fail=7 warn=16`, `validate_prop` `TOTAL files=5 fail=0` และ warn 0 ทุกไฟล์, render 5/5 planar hold: atm 36 แผง 394 หมุด, kiosk 99 แผง 475 หมุด, case 47 แผง 373 หมุด, cake 27 แผง 197 หมุด, gacha 17 แผง 175 หมุด

การแก้ที่วัดแล้ว:

| เปลี่ยน | ผล |
| --- | --- |
| atm งบ 4,200 → 5,200 | 5,096 tris, `fail=0 warn=5` (`dihedral` p90 41.4° WARN), `validate_prop` 0 / 0 |
| cake `beads=False` | `dihedral` ผ่าน แต่ `folds` ยัง FAIL (15 ขอบ 0.41% ของผิว) และ `lumpiness` FAIL (wobble 2.79°) |

## 9. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key ที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| colour: latch เป็นสามเหลี่ยมเหลืองแบน แถบกลางเหลือเส้นขาวหยัก clay: รอยยับขวางหน้ากล่อง ไม่เห็น latch | `deviation` FAIL (max 37 mm ≈ ความยื่นของ latch), `lumpiness` FAIL | ชิ้นยื่นบาง (แถบกลางยื่น 8 mm, latch และหมุดเล็ก) บนแผงแบนถูกย่อทิ้งเหลือแต่สี | เพิ่มงบ หรือประกอบเองจาก `edge_guards(mid=None)` และ latch ที่ใหญ่ขึ้น (ยังไม่วัด) ห้ามผ่านจากตัวเลขอย่างเดียว เปิดภาพ colour ทุกครั้ง |
| zebra: แถบหักเป็นจุดที่แถวลูกปัดใต้มงกุฎ ลูกบิดคู่ระหว่างบาน และปลายหัวใจ | `folds`, `dihedral` | ลูกปัด r 1.9 cm หลอมกัน 0.3r และลูกบิดสองลูกห่างกัน 9 cm ชิดขอบร่องประตู เป็นรอยต่อแคบ | ตัดลูกปัด (`beads=False`) แก้ dihedral ได้ (วัดแล้ว) fold ที่เหลืออยู่ที่ลูกบิดและหัวใจ ต้องให้ fillet ≥ 1.2r ของชิ้นเล็กเมื่อประกอบเอง |
| clay: ขอบตัวและไอซิ่งเป็นเหลี่ยมใน ATM | `dihedral` FAIL p90 46.4° | ชิ้นย่อยเยอะ (แป้น 15 ปุ่ม หยด 11 หยด สายไหล 2 เส้น) แบ่งงบ 4,200 | งบ 5,200 ผ่าน `fail=0` (วัดแล้ว) |
| zebra: จุดแตกที่โคนเสา ปลายแถบกันสาด และในคำบนหลังคา kiosk | `folds` FAIL 49 ขอบ | fold อยู่ที่รอยต่อฐานกับตัว (z ≈ 0.1 m), ลูกกลมโคนเสาบนท็อป (z ≈ 1.0 m), ปลายแถบกันสาด (fillet แถบ 0.003) และตัวอักษร | เพิ่ม fillet ของรอยต่อแคบเป็น 1.2-1.6r ของชิ้นเล็กเมื่อประกอบเอง เพิ่มงบอย่างเดียวไม่แก้ fold (`references/qa.md`) |
| clay: แผงหน้ามีรอยทแยงกากบาท | `flat_panels` | planar hold ไม่ทำงาน (builder ตกเป็น `SculptBuilder`) หรือแผงเล็กกว่า 0.01 m² | ดู `builder` ใน `cabinets_report.json` ต้องเป็น `CabinetSculptBuilder` |
| คอหยดไอซิ่งพับ | `folds` WARN (ATM 5 ขอบ) | `edge_drips` fillet 0.016 ต่ำกว่า 1.2r ของหยด | ประกอบเองส่ง `fillet=0.035` |
| palette หลายแผ่นในโฟลเดอร์เดียว | | หลายสคริปต์ใช้ `set_name` เดียวกันแต่ role ต่างกัน | ใช้ `recipes.palette()` ชุดเดียวทุกชิ้น |

อ่านภาพตาม `references/qa.md` หัวข้อ 5: แถบ zebra ที่วนเป็นระเบียบรอบลูกปัด ปุ่ม และลอนไอซิ่งคือดีไซน์ แถบที่หักกระจายบนแผงเรียบคือปัญหา

## 10. ประตู QA

1. build แล้วอ่าน `SCULPT_PROP` (หรือ `CABINETS_BUILD`) tris ต้องไม่เกินงบ และ builder ต้องเป็น `CabinetSculptBuilder` เว้นแต่ตั้งใจใช้ `--plain`
2. `validate_sculpt.py --blend <out>\<id>.blend --high <out>\_high\<id>_high.blend` ต้องได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว
3. `render_sculpt.py` แล้วเปิด clay, zebra, colour และ turntable ทุกชิ้น ดูโมดูลเล็กใน colour ว่ายังเป็นของนูนจริง ไม่ใช่คราบสี
4. prop-forge `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์
5. export ด้วย `export_prop.py --format native --max-res 512 --shared-ytd <set>_tex` (ไม่ใส่ `--factory-startup`) ตาม `references/pipeline.md` หัวข้อ 13
6. รายงานว่ายังไม่ได้ทดสอบในเกม ลองเดินชนตู้ (กล่องชนครอบหลังคาและโดม) และดูจอ emissive ตอนกลางคืน

ชิ้น demo ที่ยัง fail (`1nfx_cab_atm` ที่งบเดิม, `1nfx_cab_kiosk`, `1nfx_cab_case`, `1nfx_cab_cake`) ห้ามส่งตามสภาพนั้น แก้ตามหัวข้อ 9 แล้ววัดใหม่
