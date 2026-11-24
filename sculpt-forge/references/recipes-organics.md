# Recipes: ออร์แกนิก (เมฆ สไลม์ มาสคอตก้อน ต้นไม้ ขนม)

`scripts/blender/recipes/organics.py` คือ builder ทรงออร์แกนิกที่หลอมจากก้อนพื้นฐานของ SDF (ทรงรี แคปซูล กรวยมน torus lathe) ด้วย fillet: เมฆหลายลอน, ฐานเมฆ, กระถางต้นไม้มีใบ ดอก ผลห้อย, ถาดขนม (คัพเค้ก โดนัท ขนมปัง), ฟิกเกอร์ chibi ใส่ฮู้ด, มาสคอตสไลม์มีมงกุฎและแอ่ง, ต้นสนหิมะ ทุกชิ้นเป็น mesh เดียวไม่มีรอยทิ่ม ตัวเลขทรงทั่วไปอยู่ใน `references/smooth-craft.md` ไฟล์นี้บอกค่าที่ recipe ใช้และผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| เมฆลอย ป้ายเมฆ ไล่สีตามแกน | `cloud` |
| ฐานเมฆรองฟิกเกอร์หรือของตั้ง | `cloud_skirt` |
| กระถางต้นไม้ ใบพอง ดอก ผลห้อยข้ามขอบ | `potted_plant` (หรือ `pot`, `leaf`, `stem`, `flower`, `berry`) |
| ถาดขนมมีคัพเค้ก โดนัท ขนมปัง | `pastry_stand` (หรือ `cake_stand`, `cupcake`, `donut`, `bread`, `frosting_swirl`) |
| ฟิกเกอร์ตัวเล็กหัวโต ใส่ฮู้ดหูสัตว์ ยืนบนฐานเมฆ | `chibi` |
| มาสคอตก้อนสไลม์ หยดไหล แอ่งที่พื้น มงกุฎ | `blob_mascot` (หรือ `puddle`, `drip_runs`, `crown`) |
| ต้นสนหิมะ ชั้นลอนหิมะ ดาวบนยอด ก้อนหิมะรอบโคน | `cone_tree` (หรือ `snowballs`) |

ไม่ใช้ตระกูลนี้เมื่อ:

- ต้นไม้ พุ่มไม้ หรือดอกไม้ประกอบแมพ ใช้ prop vanilla ของเกมตาม map-forge
- ฟิกเกอร์ที่ต้องเหมือนตัวละครจริงหรือมาสคอตทางการแบบ quad-flow ใช้เส้นทางของ prop-forge ห้ามลอกตัวละครของคนอื่น
- ชิ้นใหญ่เกิน ~3 m (grid หนาแน่นของ SDF ใช้ได้ถึงราว 3 m)

recipe เรียกได้จาก Python เท่านั้น สเปก JSON ของ `forge_sculpt.py` เรียก recipe ไม่ได้

## 2. โครงร่วมของตระกูล

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `OrganicsRecipes(builder, seed=0)` | ผูกกับ builder ตัวเดียว ทุก method เพิ่ม node ลง `self.b` `seed` คุมการสุ่มขนาดลอน มุมใบ และตำแหน่งหยด |
| role ค่าเริ่ม | `chibi_roles`, `blob_roles`, `plant_roles`, `pastry_roles`, `tree_roles` แมปส่วน (เช่น `hood`, `skin`, `leaf`, `frosting`) ไปเป็น role `roles=` ทับเฉพาะ key ที่ส่ง |
| `OrganicsDemo.palette_roles` | palette 10 role: 9 role บ้าน + `snow` (`#FFFBF4` matte) และ `cocoa` (`#4A3327` matte) แทน outline สร้างด้วย `engine.SetPalette(set, roles, 32)` |
| group ต่อชิ้น | ทุก builder ห่อชิ้นใน `group` ของตัวเอง fillet ของ group = การหลอมกับของที่สร้างก่อนหน้า ชิ้นที่สร้างทีหลังผสมกับทุกอย่างก่อนหน้า ลำดับจึงสำคัญ |
| `detail=True` | ตา ประกาย แก้ม ปาก มือ หูใน และ sprinkles กันความหนาแน่นตอนย่อ ถ้า node `detail` กินผิวเกิน `detail_share` (0.35) engine เตือนและเลิกกัน |
| `ground(z=0.0, fillet=0.02)` | `cut` ใต้พื้นให้ฐานเรียบ เรียกหลังสร้างชิ้นทั้งหมด |
| กล่องชน | recipe ไม่ตั้งเอง demo เรียก `b.collider(center, size)` ครอบตัว |

## 3. builder และค่าที่ใช้

| method | ทำอะไร | พารามิเตอร์หลัก (ค่าเริ่ม) | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `cloud(center, size, roles, gradient, crease, flat, seed, fillet, collide, name)` | ซาลาเปาฐานเตี้ยกว้าง + ลอนกลมแถวหน้า 5 ลอนเรียงจังหวะเล็ก-กลาง-ใหญ่-กลาง-เล็ก (ลอนใหญ่แตะยอด) + ลอนหลัง 2 ลอน ทุกลอนนั่งบนก้นแบน | `size` (1.9, 1.05, 0.95), `roles` ("snow",), `gradient` "x"/"z"/None, `crease` 0.22, `flat` 0.1 | รัศมีลอนหน้า 22/33/45/35/24% ของความสูง ลอนหลัง 30-31% (`cloud_lobes(width, depth, height, rng, flat=0.1)`), ลอนเป็นทรงกลม (ไม่ใช่ทรงรีแบน) เส้นรอบนอกจึงอ่านเป็นก้อนเมฆชัด ไม่ใช่มันฝรั่งยับ, fillet ลอน = `crease` × รัศมีลอนเฉลี่ย (≈ 6 cm) ให้เห็นร่องระหว่างลอน (`crease` 0.3 ทำ wobble แย่ลง 2.6°), ก้นตัดที่ 10% ของความสูง มน 0.6 × ระยะตัด, ไล่สีแบ่ง role เท่าๆ กันตามแกน |
| `cloud_skirt(center, radius=0.5, height=0.22, roles, gradient, count, crease=0.3, ...)` | วงลอนรอบแผ่นทรงรี ตัดก้น | | ลอน r 0.92 × ความสูง จำนวนตามเส้นรอบวง / 1.3r, fillet 0.3r คืน `radius` และ `top` ไว้วางของบน |
| `pot(center, height=0.5, radius=0.34, base_ratio=0.74, wall=0.04, rim=None, soil_drop=0.07, bulge=None, band=True, ...)` | กระถาง lathe ท้องป่อง ขอบ torus แถบคาด ดิน | | ขอบปาก minor 8.5% ของความสูง (4.3 cm) fillet 0.45 × ขอบ, ท้องป่อง 8% ของรัศมีปาก, ผนัง 4 cm |
| `leaf(base, length=0.36, width=0.22, yaw, pitch=30, roll, thickness=None, vein=True, shape=0.62, fillet=0.02, ...)` | ใบพองหนา ร่องเส้นกลางใบ | | หนา max(3.2 cm, 17% ของความกว้าง), ขอบมน 48% ของความหนา, โดม 26%, ร่อง r 7.5% ของความกว้าง (subtract fillet 0.45r) |
| `stem(points, radius=0.015, taper=0.75, ...)`, `flower(center, radius=0.09, petals=5, facing, cup=14, ...)`, `berry(top, size=0.09, kind="strawberry", hang, ...)` | ก้าน ดอก 5 กลีบ ผลสตรอว์เบอร์รี/บลูเบอร์รี/ผลกลม | | ก้านเรียว 75%, กลีบหนา max(1.8 cm, 22% ของ r) งุ้ม 14° |
| `potted_plant(center, pot_height=0.5, pot_radius=0.34, leaves=8, leaf_length=0.4, leaf_width=0.25, flowers=3, berries=3, ...)` | กระถาง + กอใบ (62% ล่างเอียง ~12°, ที่เหลือเอียง 55°) + ดอกบนก้าน + ผลห้อยข้ามขอบ | | ก้านดอก r 2.1 cm ก้านผล r 1.8 cm, ผล 12.5 cm, กอทั้งกอใน group fillet 0.03 |
| `pastry_stand(center, radius=0.52, height=0.36, sprinkles=0, ..., scores=3, ribs=12)` | ถาดขาตั้ง lathe + คัพเค้ก + โดนัทเอียง + ขนมปังมีรอยกรีด | | piping ขอบถาด torus minor 2.6 cm (กฎ 2.5-3.5 cm), ขนมแต่ละชิ้นวางตามระดับก้นจาน (`dish_height`), `scores` จำนวนรอยกรีดขนมปัง `ribs` จำนวนจีบถ้วย (2 และ 8 ยังไม่แก้ fold วัดแล้ว) |
| `cupcake(base, radius=0.17, height=0.52, ribs=12, turns=2.5, cherry=True, ...)` | ถ้วยกระดาษ lathe + จีบ 12 แคปซูล + เนื้อเค้ก + ครีมเกลียว + เชอร์รี่ | | จีบ r 16% ของรัศมี fillet 0.9 × จีบ, ครีมเป็นท่อหนึ่งเส้นต่อรอบ เรียวลง 42% |
| `donut(center, major=0.13, minor=0.066, icing=True, sprinkles=0, rot, ...)` | torus + ไอซิ่งตัดครึ่งบน + ลอนไอซิ่งย้อย + sprinkles | | major : minor ≈ 2 : 1, ลอนย้อย 10 ต่อเมตร ห้อย 0.36 × minor |
| `bread(center, size=(0.4, 0.22, 0.17), yaw=0, scores=3, ...)` | ก้อนขนมปังรี + ท้องโป่ง + รอยกรีดแคปซูล subtract | | รอยกรีดกว้าง 16% ของความกว้าง มน 0.6 × ร่อง |
| `chibi(center, height=1.3, ears="bear", hood=True, base="cloud", ...)` | ฐานเมฆ, ลำตัวกรวยมน, ขา รองเท้า แขน มือ, หัวทรงรี, หน้า (ตา ประกาย แก้ม ปาก ผม 3 ปอย), เชือกฮู้ด, ฮู้ดมีขอบท่อและหู | `ears` "bear"/"bunny"/"cat"/None | หัว r 0.235 × ความสูง (หัวโตแบบ chibi), ตัว fillet 0.03 × ความสูง, ฮู้ด fillet 0.014 × ความสูง ขอบฮู้ด r 0.085 × รัศมีหัว, ฐานเมฆ R 0.3 × สูง 0.13 × ความสูง |
| `blob_mascot(center, radius=0.36, crown=True, puddle=True, drips=5, blush=False, ...)` | ตัวก้อนทรงรี + แอ่งสไลม์ + สายหยดรอบตัว + ตา ปาก + มงกุฎเอียง 14° (`crown=False` ได้จุกแทน) | | ตัวหลอมแอ่ง fillet 0.26R, สายหยดหนา 0.1R fillet 0.06R ปลายลูกกลม 1.22 เท่า เว้นหน้า ±40°, แอ่งรัศมี 1.55R สูง 0.17R |
| `puddle(center, radius=0.5, height=0.06, lobes=7, amp=0.12, rim=None, satellites=3, ...)` | แอ่งขอบหยัก โดมเตี้ย หยดดาวเทียมรอบแอ่ง | | ขอบ 35% ของความสูง, หยดดาวเทียม r 0.9-1.4 × ความสูง fillet 0.8r |
| `crown(base, radius=0.12, height=0.11, prongs=5, tilt=(0, 12, 0), ...)` | แถบมงกุฎ ขอบ torus กำมะหยี่ แฉกกรวยมนปลายลูกกลม อัญมณี | | แฉก 0.25r → 0.12r ปลาย 0.19r |
| `cone_tree(center, height=1.7, radius=0.52, tiers=3, star=True, drape=True, ground=True, ...)` | แอ่งหิมะ + ก้อนหิมะ 4 ลูก, ลำต้น, ชั้นสน lathe 3 ชั้น, หิมะคลุมแต่ละชั้น (torus + ลอน), ยอดหิมะ, ดาว | | ชั้นที่ i รัศมี R(1 - 0.25i), ลอนหิมะ 6.5 ต่อเมตร หนา 5 cm (กฎฝาหิมะ 4-6 cm), ดาวและลำต้น r 0.075 × ความสูง, ทั้งต้น group fillet 0.05 |

## 4. fillet ต่อรอยต่อที่ recipe ใช้

| รอยต่อ | k |
| --- | --- |
| ลอนเมฆกันเอง | `crease` × รัศมีลอนเฉลี่ย (0.22 → ≈ 6 cm) |
| ลอนฐานเมฆกันเอง | 0.3 × r ลอน |
| ตัว chibi รวมกับฐานเมฆ (group) / ฮู้ด (group) / หัวกับลำตัว | 0.03 / 0.014 / 0.05 × ความสูง |
| ตา ประกาย แก้ม ปาก (subtract) | 0.004-0.012 × ความสูง ตามขนาดชิ้น |
| กอใบ (group) / ใบ / ก้าน / ดอก | 0.03 / 0.02 / 0.012-0.016 / 0.008 |
| ขอบกระถาง / แถบคาด / ดิน | 0.45 × ขอบ / 0.4 × ขอบ / 0.015 |
| จีบถ้วยคัพเค้ก / ครีมเกลียว / เชอร์รี่ | 0.9 × จีบ / 0.016 / 0.012 |
| ถ้วยคัพเค้กและขนมปังกับถาด / โดนัทกับถาด | 0 (หลอมแบบคม) / 0.02 |
| ตัวสไลม์กับแอ่ง / สายหยด / มงกุฎ | 0.26R / 0.06R / 0.03R |
| ชั้นสน / หิมะคลุม / ทั้งต้น | 0.04 / 0.015-0.02 / 0.05 |
| ตัดพื้น | 0.02 |

## 5. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): 5,880 tris, `SCULPT_QA fail=0 warn=3`, `validate_prop` fail=0 warn=0

```python
import importlib
import os
import sys


class HoodFigure:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        org = self.module("organics")
        engine = org.EngineLoader.load(os.path.join(self.skill, "sculpt-forge", "scripts", "blender"))
        palette = engine.SetPalette("1nfx_cafe", org.OrganicsDemo.palette_roles, 32)
        b = engine.SculptBuilder("1nfx_cafe_figure", budget=6000, lod_dist=150.0, set_name="1nfx_cafe", archetype="figure", voxel=0.005, palette=palette, default_role="cream", ao_distance=0.2)
        recipes = org.OrganicsRecipes(b, seed=11)
        recipes.chibi(height=1.3, ears="bunny")
        recipes.ground()
        b.collider((0.0, 0.0, 0.7), (0.7, 0.6, 1.4))
        return b.build(self.out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = HoodFigure(argv[0], argv[1]).build()
    print("HOOD_FIGURE tris={} blend={}".format(result["tris"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -t 6 -P '<project>\work\cafe\hood_figure.py' -- '<skill>' '<project>\work\cafe\build'
```

- `SculptBuilder` ไม่มี `finish()` จบด้วย `b.build(out_dir)` (ผลตาม `references/pipeline.md` หัวข้อ 8)
- `EngineLoader.load(explicit)` ของตระกูลนี้ต้องได้พาธเมื่อไม่มี `__file__` (exec ผ่าน MCP) ส่งโฟลเดอร์ `scripts/blender` ทุกครั้งเหมือนตัวอย่าง
- ไม่มีฟังก์ชันกล่องชนใน recipe ต้องเรียก `b.collider` เอง (หรือใส่ `collide=True` ที่ node หลักแล้วใช้ `colliders="auto"`)
- ฟิกเกอร์ 1-1.6 m ตามตาราง `references/smooth-craft.md` หัวข้อ 10 ใช้ 8,000-15,000 tris demo ใช้ 6,000 แล้วผ่าน ถ้าเพิ่มรายละเอียดหน้าให้เพิ่มงบตาม
- หลายชิ้นในชุดเดียวใช้ `SetPalette` ชุดเดียวกัน ไม่งั้น engine เขียน `<set>_pal_<sha8>.png` เพิ่ม

## 6. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\organics'

& $blender -b --factory-startup -t 6 -P "$sf\recipes\organics.py" -- --out $work
& $blender -b --factory-startup -t 6 -P "$sf\recipes\organics.py" -- --out $work --only 1nfx_org_chibi,1nfx_org_blob --budget-scale 1.2 --no-render
```

จำกัดเธรดเสมอ: `QaRunner.run` ส่ง `-t <bpy.context.scene.render.threads>` ให้ Blender ลูก (`validate_sculpt`, `validate_prop`, `render_sculpt`) ลูกจึงใช้เธรดเท่าตัวแม่ที่รันด้วย `-t 6` และรันทีละตัวผ่าน `subprocess.run` ห้ามรันหลายตระกูลพร้อมกัน

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--out <dir>` | ต้องใส่ (ไม่ใส่พิมพ์ usage แล้วจบ) | โฟลเดอร์ผล |
| `--only id1,id2` | ทุกชิ้น | id ของ demo (`1nfx_org_cloud`, `1nfx_org_plant`, `1nfx_org_pastry`, `1nfx_org_chibi`, `1nfx_org_blob`, `1nfx_org_snowtree`) |
| `--engine <dir>` | โฟลเดอร์แม่ของ recipe | โฟลเดอร์ที่มี `sculpt_forge.py` |
| `--voxel V` | ค่าของแต่ละชิ้น | ทับทุกชิ้น |
| `--budget-scale` | 1.0 | คูณงบทุกชิ้น |
| `--blender <exe>` | Blender ที่รันอยู่ | ตัวที่ใช้รัน QA และ render |
| `--no-qa` | | ข้าม QA และ render |
| `--no-render` | | ข้าม `render_sculpt.py` |
| `--views`, `--res` | 4, 900 | turntable และขนาดภาพ |

ผล: `<id>.blend`, `_high/<id>_high.blend`, `1nfx_organic_pal.png`, `qa/<id>_qa.json` และ `.log`, `qa/sculpt_qa.json`, `qa/validate_prop.log`, `qa/render.log`, `renders/`, `organics_report.json` บรรทัดที่พิมพ์: `ORGANICS_BUILD`, `ORGANICS_QA`, `PROP_QA <id> fail=N warn=M`, `SCULPT_RENDER`, `SCULPT_QA`, `ORGANICS_DONE`, `ORGANICS_FAIL` (build พัง) headless คืน exit code 1 เมื่อ build พัง หรือ `SCULPT_QA`/`validate_prop` fail

## 7. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, `SculptBuilder` ธรรมดา, set `1nfx_organic`, engine ที่มี `SurfaceRefiner` รันตระกูลเดียว `-t 6` ด้วย `run_seq.ps1`

| id | builder | voxel / `ao_distance` | ขนาด (m) | tris / งบ | tris/m² | วินาที | `SCULPT_QA` | `validate_prop` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1nfx_org_cloud` | `cloud` ไล่ pink → snow → sky | 0.0045 / 0.24 | 1.84 × 0.94 × 0.85 | 2,890 / 2,950 | 699 | 7.9 | fail=0 warn=2 | 0 / 0 |
| `1nfx_org_plant` | `potted_plant` | 0.005 / 0.18 | 0.92 × 0.93 × 1.03 | 4,116 / 4,200 | 1,262 | 13.3 | fail=0 warn=6 | 0 / 0 |
| `1nfx_org_pastry` | `pastry_stand` | 0.005 / 0.18 | 1.06 × 1.06 × 0.98 | 4,112 / 4,200 | 1,321 | 18.2 | fail=1 warn=5: `folds` 29 ขอบ (0.19% ของผิว) | 0 / 0 |
| `1nfx_org_chibi` | `chibi` หูหมี | 0.005 / 0.2 | 1.10 × 1.09 × 1.44 | 5,868 / 6,000 | 1,260 | 13.0 | fail=0 warn=3 | 0 / 0 |
| `1nfx_org_blob` | `blob_mascot` | 0.005 / 0.2 | 1.30 × 1.21 × 0.89 | 3,520 / 3,600 | 1,003 | 18.0 | fail=0 warn=6 | 0 / 0 |
| `1nfx_org_snowtree` | `cone_tree` | 0.006 / 0.22 | 1.30 × 1.22 × 1.60 | 4,116 / 4,200 | 616 | 11.0 | fail=0 warn=6 | 0 / 0 |

ทั้งชุด `SCULPT_QA fail=1 warn=28` (ก่อนแก้ fail=2: เมฆ, ถาดขนม), `validate_prop` fail=0 warn=0 ทุกไฟล์, render 6/6 ความหนาแน่น 616-1,321 tris/m² ชิ้นเล็กหนาแน่นกว่าฮีโร่ 2-4 m เพราะผิวน้อย (`references/smooth-craft.md` หัวข้อ 10) เพดานงานนี้ ~700 tris/m² จึงไม่เพิ่มงบชิ้นที่เกินอยู่แล้ว

การแก้ที่ลองแล้ว:

| เปลี่ยน | ผล |
| --- | --- |
| cloud ทรงใหม่ (ลอนกลม 5 + 2 บนก้นแบน) voxel 0.006 → 0.0045 งบ 3,600 → 2,950 | fail 1 → 0: wobble 3.02 → 1.14° (WARN), 774 → 699 tris/m² |
| cloud ทรงใหม่ voxel 0.006 งบ 3,600 / 3,200 | ยัง FAIL wobble 1.93° / 1.76° |
| cloud ทรงใหม่ `crease` 0.3 | แย่ลง wobble 2.6-2.8° |
| cloud ทรงเดิม งบ × 1.4 / `crease` 0.5, 0.8 / voxel 0.004 (engine เก่า) | ยัง FAIL wobble 2.37 / 2.84, 1.95 / 2.96° |
| pastry `scores` 2, `ribs` 8 | `folds` 24-30 ขอบ 0.18-0.20% ยัง FAIL (รอยพับจริงที่ขอบถาดและขดครีม) |
| pastry งบ × 1.4 (engine เก่า) | แย่ลง: `folds` 37 ขอบ 0.15% และ `lumpiness` wobble 5.56° FAIL |

## 8. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key ที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| เมฆดูเป็นมันฝรั่งยับ zebra: แถบซิกแซกบนลอนกลาง | `lumpiness` FAIL shading wobble ~3° | ทรงเดิมเป็นลอนทรงรีเล็กหลายชั้นสลับหน้าหลัง และ voxel 0.006 | ทรงใหม่ของ `cloud` (ลอนกลมเรียงจังหวะบนก้นแบน) + voxel 0.0045 ผ่าน (วัดแล้ว) อย่าเพิ่ม `crease` เกิน 0.22 |
| zebra: จุดแตกรอบก้นคัพเค้กบนจาน ในขดครีม และที่ขอบถาด clay: จีบถ้วยเป็นปล้อง | `folds` FAIL 29 ขอบ | fold กระจุกที่ก้นถ้วยบนพื้นจาน (z ≈ 0.33 m) ซึ่งถ้วยหลอมกับถาดแบบ k = 0, ในขดครีม (z 0.56-0.69 m) และที่ piping ขอบถาด | เพิ่มงบไม่ช่วย (แย่ลง วัดแล้ว) ประกอบเองโดยห่อขนมใน `with b.group("items", fillet=0.015):` ให้มี fillet กับถาด แล้ววัดใหม่ (ยังไม่วัด) |
| clay: ใบเป็นแผ่นแบน มีรอยทแยงบนใบ | `flat_panels` WARN (92 แผง), `dihedral` p90 44.5° | ใบบาง 3.2 cm ผิวเกือบแบน | ยอมรับได้ถ้าเงาดูเป็นใบโค้ง ถ้าต้องการโค้งชัดเพิ่ม `pitch`/`roll` หรือความหนาใบ |
| ตา แก้ม หรือปากหาย หรือเลอะเป็นก้อน | `deviation` max สูง | node `detail` กินผิวเกิน `detail_share` engine เลิกกันความหนาแน่น หรือชิ้นเล็กกว่า max(4 voxel, 15 mm) ถูกทิ้งเป็น speck | ดู warning `detail nodes cover N%` ใน `SCULPT_PROP` ใส่ `detail` เฉพาะชิ้นหน้า ขยายชิ้นเล็ก |
| zebra: จุดแตกรอบฐานมงกุฎบนหัวสไลม์ | `folds` WARN (blob 9 ขอบ ทั้งหมดที่ z ≈ 0.68 m) | มงกุฎหลอมหัวด้วย fillet 0.03R (1.1 cm) แถบและขอบ torus ชิดผิวหัว | ประกอบเองให้ fillet ของรอยต่อแคบ ≥ 1.2-1.6r ของชิ้นที่บางสุด (ขอบ torus) แล้ววัดใหม่ |
| zebra: จุดแตกที่ขอบล่างชั้นสนชั้นแรกและโคนลำต้น | `folds` WARN (ต้นสน 10 ขอบ) | หิมะคลุมชนขอบล่างชั้นแรก (z ≈ 0.25 m) และลำต้นจมแอ่งหิมะ (z ≈ 0.06 m) | ยอมรับได้เมื่อเป็น WARN ถ้าเห็นในภาพให้เพิ่ม fillet ของหิมะคลุมเมื่อประกอบเอง |
| ส่วนที่ high มีแต่ low ไม่มี | `deviation` high → low max สูง (ต้นสน 278 mm) | speck หรือโพรงที่ repair ทิ้ง | เปิด clay และ turntable ดูว่าหายส่วนที่มองเห็นไหม (ดาว ก้อนหิมะ ปลายหู) |
| palette หลายแผ่นในโฟลเดอร์เดียว | | หลายสคริปต์ใช้ `set_name` เดียวกันแต่ role ต่างกัน | ใช้ `SetPalette` ชุดเดียวทุกชิ้น |

อ่านภาพตาม `references/qa.md` หัวข้อ 5: แถบที่วนเป็นระเบียบตามลอนเมฆ ลอนหิมะ และขดครีมคือดีไซน์ แถบซิกแซกหรือหักบนผิวใหญ่เรียบคือ wobble จริง

## 9. ประตู QA

1. build แล้วอ่าน `SCULPT_PROP` (หรือ `ORGANICS_BUILD`) tris ต้องไม่เกินงบ และไม่มี warning `detail nodes cover`
2. `validate_sculpt.py --blend <out>\<id>.blend --high <out>\_high\<id>_high.blend` ต้องได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว
3. `render_sculpt.py` แล้วเปิด clay, zebra, colour และ turntable ทุกชิ้น ฟิกเกอร์ดูหน้าใน colour (ตา ประกาย แก้ม) และด้านหลังฮู้ด
4. prop-forge `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์
5. export ด้วย `export_prop.py --format native --max-res 512 --shared-ytd <set>_tex` (ไม่ใส่ `--factory-startup`) ตาม `references/pipeline.md` หัวข้อ 13
6. รายงานว่ายังไม่ได้ทดสอบในเกม ดูตอนกลางคืนว่าตัวสีอ่อนอ่านออก (`references/smooth-craft.md` หัวข้อ 14)

ชิ้น demo ที่ยัง fail (`1nfx_org_pastry`: `folds` 29 ขอบ ต้องการงบที่เกินเพดานความหนาแน่น หรือห่อขนมใน group ที่มี fillet กับถาด) ห้ามส่งตามสภาพนั้น
