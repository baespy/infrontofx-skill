# Recipes: กล่อง หีบ และตู้เซฟ

`scripts/blender/recipes/containers.py` คือ builder ของเก็บของทรงกล่องขนาด 0.7-1.1 m: กล่องบุนวม, กล่อง stash ลายทางมีฝาครีม, หีบสมบัติเปิดฝามีเหรียญ, ตู้เซฟวงล้อ, ลังมุมครอบ และกล่องของขวัญ ทุกตัวเป็น SDF ชิ้นเดียว ขอบม้วนจริง ของที่แปะบนผิว (ริบบิ้น แผ่นแปะ ป้าย) ใช้ `conformal` ให้แนบผิวหมอนแทนการวางแผ่นแบน ตัวเลขทรงทั่วไปอยู่ใน `references/smooth-craft.md` ไฟล์นี้บอกค่าที่ recipe ใช้และผลที่วัดได้

## 1. ใช้เมื่อไร

| โจทย์ | builder |
| --- | --- |
| กล่องบุนวม ขอบม้วนเป็นหมอน ร่องตะเข็บ แผ่นแปะและป้ายห้อย | `padded_cube` |
| กล่อง stash ลายทางนูน ฝาครีมหยัก หยด sprinkles เชอร์รี่ ป้ายคำ | `striped_box` |
| หีบสมบัติ ฝาโค้งเปิดได้ เหรียญกองในหีบและล้นหน้า กุญแจหัวใจ | `loot_chest` |
| ตู้เซฟ ประตูวงแหวนหมุด วงล้อก้าน บานพับ แป้นกด | `vault_safe` |
| ลังโครงเหล็ก มุมครอบ คานทแยง ฝาหมอน หูจับ | `corner_crate` |
| กล่องของขวัญ ฝายื่น ริบบิ้นสองทาง โบว์ | `gift_box` |

ไม่ใช้ตระกูลนี้เมื่อ:

- ตู้ตั้งพื้นสูงที่มีจอหรือหลังคา (ATM, kiosk, ตู้คีบ) ใช้ `references/recipes-cabinets.md`
- ภาชนะทรงกลม (ไห โถ ถ้วย กลอง) ใช้ `references/recipes-rounds.md`
- ลัง low-poly ทรงคมสำหรับฉากหลัง ใช้ archetype `crate`/`chest` ของ prop-forge

recipe เรียกได้จาก Python เท่านั้น สเปก JSON ของ `forge_sculpt.py` เรียก recipe ไม่ได้

## 2. โครงร่วมของตระกูล

| ส่วน | ทำงานอย่างไร |
| --- | --- |
| `ContainersRecipes(theme="house", roles=None, seed=7)` | `theme` `house` หรือ `pastel` แมป slot (`body`, `trim`, `wood`, `accent`, `metal`, `frost`, `stripe`, `wrap`, `ribbon`, `knot`, `cherry`, `sprinkles`) ไปเป็น role `seed` คุมตำแหน่งสุ่มของ sprinkles เหรียญ และหยด |
| `palette(cell_px=32)` | 9 role บ้าน `honey` เป็น gloss ในตระกูลนี้ (ตระกูลอื่นเป็น satin) ถ้ารวมหลายตระกูลในชุดเดียวให้ใช้ palette ชุดเดียวกันทั้งหมด |
| `builder_class(sf, hold=True)` | คืน `ContainerSculptBuilder` (`PanelHoldMixin` + `SculptBuilder`) `hold=False` ได้ `SculptBuilder` ธรรมดา |
| `PanelHoldMixin` | กันงบ 7% (`hold_reserve`) ย่อไปที่ 93% ของงบ แล้วหาแผงแบน (หน้า material เดียวกันเอียงกัน ≤ 3°, ≥ max(0.004 m², 4 เท่าของหน้ากลาง)) ที่ normal ขอบแผงเอียง ≥ 4° ใส่วง holding loop หนา min(14 mm, 0.2 × ความกว้างแผง) ฉายลงผิว SDF และยกเลิกแผงที่ทำให้หน้าพลิก (ลองสูงสุด 5 รอบ) ผลเก็บใน `panel_hold` ของ report การย่อ |
| `conformal(b, hosts, cutter, role, rim=0.006, join=0.005, name)` | ผิวที่แนบ host: ขยาย host (`round_box`/`pillow_box`) ออก `rise` แล้ว intersect กับ cutter (แผ่น ริบบิ้น ป้าย) ได้ชิ้นที่โค้งตามหมอนจริง หนาเท่า `rise` |
| `pillow_host(size, radius, bulge, loc, rise)` | host สำหรับ `conformal` บนผิว `pillow_box` |
| `suggest_budget(size, density=600.0, extra=0.2, minimum=1500)` | งบจากพื้นที่กล่อง: 2(wd + wh + dh) × 1.2 × 600 ปัดหลักร้อย |
| `loc` | ทุก builder วางที่ `loc` (พื้นของกล่อง) และคืน `colliders`, `size`, `root` |

รัศมีขอบของ `striped_box`, `loot_chest`, `vault_safe`, `gift_box` เป็นสัดส่วนของด้านที่สั้นที่สุด (`radius=0.07` บนด้าน 0.72 m = 5 cm) demo สร้างด้วย `size_class="medium"`, `lod_dist` 100

## 3. builder และค่าที่ใช้

| method | ทำอะไร | พารามิเตอร์หลัก (ค่าเริ่ม) | ทำไมค่านี้ |
| --- | --- | --- | --- |
| `padded_cube(b, ...)` | ท่อหมอน 12 สันตามขอบ + ตัวหมอนกลาง + ร่องตะเข็บ + แผ่นแปะดาวหรือหัวใจ + ป้ายห้อยหัวใจ | `size` 0.9, `puff` 0.06, `seam` 0.22, `groove` 0.012, `crease` 0.016, `spread` 0.5, `tag` True, `patch` "star"/"heart"/None | หน้าโป่ง `puff` × ด้าน = 5.4 cm (กฎกล่องบุนวม 5-7%), ตะเข็บห่างขอบ 22% ของครึ่งด้าน (กฎ 20-25%), ท่อขอบ r ≈ 6.2 cm คำนวณจากระยะตะเข็บและร่อง 1.2 cm, `crease` คือ fillet ตัวกลางกับท่อขอบ |
| `striped_box(b, ...)` | ฐาน skirt, ตัวกล่อง, ลายทางนูนสี่ด้าน, ฝาครีมหมอน, ลอนครีม, หยด, sprinkles, เชอร์รี่, ป้ายคำบนแผ่น | `size` (0.95, 0.72, 0.72), `radius` 0.07, `stripe` 0.085, `rise` 0.007, `skirt` 0.07, `frost` 0.06, `overhang` 0.022, `per_m` 8, `drop` 0.08, `drips` 5, `label` "STASH", `sprinkles` 10, `cherry` True | ขอบ 7% = 5 cm (กล่อง stash ~7%), ฝาหนา 6 cm ยื่น 2.2 cm (กฎ 4-6 / 2-4 cm), ลอน 8 ต่อเมตรห้อย 8 cm หนา 3.6 cm (กฎ 8 ต่อเมตร 6-10 cm), ลายทางกว้าง 8.5 cm ยื่น 7 mm |
| `loot_chest(b, ...)` | ตัวหีบ, แผงหน้าจม, ท่อขอบบนล่าง, ท่อหมอน 4 มุม, สายรัด, ดาวข้าง, กุญแจหัวใจ ห่วง รูกุญแจ, ฝาโค้งหมุนรอบบานพับ, กองเหรียญในหีบ, เหรียญล้นหน้าหีบ | `size` (0.9, 0.6, 0.48), `radius` 0.07, `lid` 0.24, `open_deg` 105, `wall` 0.045, `bolster` 0.04, `straps` True, `lock` True, `coins` 24, `spill` 7, `stars` True | ขอบ 7% = 3.4 cm (หีบ ~7%), เหรียญ r 4 cm หนา 1.4 cm ขอบมน 48%, `open_deg` 0 = ปิดฝา (ไม่มีโพรงและกองเหรียญ), กล่องชนสองกล่อง (ตัว + ฝาที่หมุนแล้ว) |
| `vault_safe(b, ...)` | ฐาน, ตัวหมอน, piping หน้า, ประตูจม, วงแหวน + หมุด, ดุม, ก้านวงล้อปลายลูกกลม, บานพับ, แป้นกดมีจอ | `size` (0.9, 0.78, 1.0), `radius` 0.085, `plinth` 0.08, `ring` 0.2, `tube` 0.03, `studs` 12, `stud` 0.017, `spokes` 3, `keypad` True, `piping` True | ขอบ 8.5% = 6.6 cm (ตู้เซฟ 5-7 cm บนตัว 0.8 m), ตัวโป่ง 1.2-1.6 cm, piping r 1.8 cm, วงแหวน minor 3 cm ฝัง 45% |
| `corner_crate(b, ...)` | แผงตัว, คานขอบ 12 เส้น, คานทแยงหน้าหลัง, ฝาหมอน, มุมครอบ 8 มุม, หูจับข้างมีร่องมือ | `size` (0.95, 0.75, 0.7), `rail` 0.07, `cap` 1.65, `inset` 0.02, `lid_puff` 0.035, `brace` True, `handles` True | คานมน 0.4 × `rail` = 2.8 cm, มุมครอบ 1.65 × `rail` = 11.6 cm มน 32%, ฝาโป่ง 3.5 cm |
| `gift_box(b, ...)` | กล่อง, ฝาหมอนยื่น, ริบบิ้นสองทางแนบผิว, หางริบบิ้น, ปมรี, ห่วงโบว์สองข้าง | `size` (0.8, 0.8, 0.62), `radius` 0.06, `lid` 0.14, `overhang` 0.028, `ribbon` 0.09, `rise` 0.008, `bow` 1.0, `tails` True | ขอบ 6% = 3.7 cm, ฝามน 0.4 × ความหนาฝา, ริบบิ้นกว้าง 9 cm หนา 8 mm แนบผิวด้วย `conformal`, ห่วงโบว์ท่อปิด r 2.2-3.5 cm × `bow` |

ทุก builder รับ `roles` (ทับ slot) และ `loc` ตัวแปรสุ่มใช้ `seed` ของ `ContainersRecipes` (หรือ `seed=` ของ `striped_box`/`loot_chest`)

## 4. fillet ต่อรอยต่อที่ recipe ใช้

| รอยต่อ | k |
| --- | --- |
| ตัวหมอนกลางกับท่อขอบ (`crease`) | 0.016 |
| แผ่นแปะ / ไอคอน / ป้าย `conformal` (rim, join) | 0.006-0.01, 0.004-0.012 |
| ตัวกล่องกับ skirt / ฐาน | 0.012 / 0.015 |
| ลายทาง (group) | 0.006 |
| ฝาครีม (group) / ลอน / หยด | 0.01 / 0.012 / 0.01 |
| sprinkles / เชอร์รี่ / ก้าน | 0.004 / 0.012 / 0.006 |
| ท่อหมอนมุมหีบ / ท่อขอบ / สายรัด | 0.012 / 0.01 / 0.006 |
| กุญแจ / ห่วง / รูกุญแจ | 0.006 / 0.005 / 0.003 |
| เหรียญ / กองเหรียญ / กองหน้าหีบ | 0.003 / 0.01 / 0.015 |
| ประตูเซฟ (subtract) / วงแหวน / หมุด / ดุม / ก้าน | 0.012 / 0.01 / 0.004 / 0.008 / 0.006 |
| คานลัง (group) / มุมครอบ (group) / คานทแยง | 0.012 / 0.008 / 0.01 |
| ห่วงโบว์ / ปม | 0.014 / 0.012 |
| ตัดพื้น | 0.006-0.008 |

หยดของ `striped_box` ใช้ fillet 0.01 ต่ำกว่ากฎ 1.2-1.6r ของหยด (r 1.8-2.6 cm) และหมุดหรือปุ่มเล็กใช้ 0.003-0.004 ทั้งสองจุดเป็นรอยต่อแคบที่เกิด fold ได้

## 5. เรียกจาก Python

ตัวอย่างนี้รันจริงแล้ว (Blender 4.2.3): 4,234 tris, `SCULPT_QA fail=0 warn=4`, `validate_prop` fail=0 warn=0 ที่งบ 3,300 ของ demo ได้ `folds` FAIL (หัวข้อ 7)

```python
import importlib
import os
import sys


class VaultBox:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def module(self, name):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender", "recipes")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module(name)

    def build(self):
        ctr = self.module("containers")
        engine = ctr.EngineLoader.load()
        recipes = ctr.ContainersRecipes(theme="house", seed=7)
        builder = ctr.ContainersRecipes.builder_class(engine)
        b = builder("1nfx_cafe_safe", budget=4500, voxel=0.004, size_class="medium", lod_dist=100.0, set_name="1nfx_cafe", archetype="vault_safe", palette=recipes.palette(), default_role="cream")
        recipes.vault_safe(b)
        return b.build(self.out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    result = VaultBox(argv[0], argv[1]).build()
    print("VAULT_BOX tris={} blend={}".format(result["tris"], result["blend"]), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
& $blender -b --factory-startup -P '<project>\work\cafe\vault_box.py' -- '<skill>' '<project>\work\cafe\build'
```

- `SculptBuilder` ไม่มี `finish()` จบด้วย `b.build(out_dir)` (ผลตาม `references/pipeline.md` หัวข้อ 8)
- `EngineLoader.load(explicit=None)` หา `sculpt_forge.py` จากอาร์กิวเมนต์, โฟลเดอร์แม่ของ recipe หรือ env `SCULPT_FORGE_SCRIPTS` ใต้ MCP ส่งโฟลเดอร์ `scripts/blender` ตรงๆ หรือโหลดด้วย `runpy.run_path(..., run_name="containers_recipes")` (ห้าม `__main__`)
- กล่องหลายใบในชุดเดียวใช้ `recipes.palette()` ชุดเดียวกัน ไม่งั้น engine เขียน `<set>_pal_<sha8>.png` เพิ่ม

## 6. demo CLI

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<skill>'
$sf      = "$skill\sculpt-forge\scripts\blender"
$work    = '<project>\work\containers'

& $blender -b --factory-startup -P "$sf\recipes\containers.py" -- --out $work
& $blender -b --factory-startup -P "$sf\recipes\containers.py" -- --out $work --only gift_box --budget 3400 --no-render
& $blender -b --factory-startup -P "$sf\recipes\containers.py" -- --out "$work\pastel" --theme pastel --seed 11
```

| ตัวเลือก | ค่าเริ่ม | ความหมาย |
| --- | --- | --- |
| `--out <dir>` | ต้องใส่ (ไม่ใส่พิมพ์ `CONTAINERS_USAGE` แล้วจบ) | โฟลเดอร์ผล |
| `--only a,b` | ทุกชิ้น | id ของ demo หรือชื่อ method (`padded_cube`, `striped_box`, `loot_chest`, `vault_safe`, `corner_crate`, `gift_box`) |
| `--theme` | `house` | `house` หรือ `pastel` |
| `--engine <dir>` | หาเอง | โฟลเดอร์ที่มี `sculpt_forge.py` |
| `--budget N`, `--voxel V` | ค่าของแต่ละชิ้น | ทับทุกชิ้นที่ build |
| `--seed` | 7 | seed ของตำแหน่งสุ่ม |
| `--no-qa` | | ข้าม `validate_sculpt` และ `validate_prop` (ยัง render) |
| `--no-render` | | ข้าม `render_sculpt.py` |

CLI ใช้ `PanelHoldMixin` เสมอ ปิดได้เฉพาะจาก Python (`builder_class(sf, hold=False)`)

ผล: `<id>.blend`, `_high/<id>_high.blend`, `1nfx_ctr_pal.png`, `qa/<id>_qa.json` และ `.log`, `qa/containers_qa.json`, `qa/validate_prop.log`, `renders/`, `containers_report.json` บรรทัดที่พิมพ์: `CONTAINERS_BUILD`, `CONTAINERS_QA`, `CONTAINERS_PROP_CONTRACT`, `CONTAINERS_RENDER`, `CONTAINERS_DONE`, `CONTAINERS_FAIL` (build พัง) headless คืน exit code 1 เมื่อ build พังหรือ `SCULPT_QA` fail

## 7. demo ที่วัดแล้ว

Blender 4.2.3, 2026-11-24, theme `house` (กล่องของขวัญใช้ role pastel), builder `ContainerSculptBuilder`, set `1nfx_ctr` (รัน 6 ตระกูลพร้อมกัน เวลาจึงสูงกว่ารันเดี่ยว)

| id | method | voxel | ขนาด (m) | tris / งบ | tris/m² | วินาที | `SCULPT_QA` | `validate_prop` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1nfx_ctr_padded_cube` | `padded_cube` | 0.005 | 1.01 × 1.03 × 0.95 | 2,438 / 2,600 | 525 | 12.7 | fail=1 warn=0: `lumpiness` wobble 1.93° | 0 / 0 |
| `1nfx_ctr_striped_box` | `striped_box` | 0.005 | 1.02 × 0.82 × 0.93 | 2,998 / 3,000 | 729 | 13.7 | fail=1 warn=5: `dihedral` p90 63.0° | 0 / 0 |
| `1nfx_ctr_loot_chest` | `loot_chest` | 0.004 | 0.96 × 1.08 × 1.05 | 3,198 / 3,200 | 594 | 37.2 | fail=2 warn=3: `dihedral` p90 64.8°, `folds` 90 ขอบ | 0 / 0 |
| `1nfx_ctr_vault_safe` | `vault_safe` | 0.004 | 0.95 × 0.87 × 1.01 | 3,054 / 3,300 | 626 | 16.6 | fail=1 warn=3: `folds` 11 ขอบ (0.12% ของผิว) | 0 / 0 |
| `1nfx_ctr_corner_crate` | `corner_crate` | 0.005 | 1.01 × 0.81 × 0.77 | 2,796 / 2,800 | 710 | 6.0 | fail=1 warn=1: `lumpiness` wobble 2.27°, roughness 2.71° | 0 / 0 |
| `1nfx_ctr_gift_box` | `gift_box` | 0.005 | 0.87 × 0.87 × 0.80 | 2,768 / 2,800 | 808 | 4.1 | fail=0 warn=5 | 0 / 1 (degenerate triangles 4) |

ทั้งชุด `SCULPT_QA fail=6 warn=17`, `validate_prop` `TOTAL files=6 fail=0` แต่กล่องของขวัญมี warn 1 ไม่มีชิ้นไหนใน demo ผ่านทั้งสองประตูตามค่าเริ่ม

การแก้ที่วัดแล้ว (`validate_prop` ทุกแถว fail=0 warn=0):

| เปลี่ยน | ผล |
| --- | --- |
| `vault_safe` `spokes=0` (งบ 3,300) | 3,134 tris, `fail=0 warn=3` |
| `vault_safe` งบ 4,500 | 4,234 tris, `fail=0 warn=4` (`folds` 20 ขอบ เหลือ WARN 0.03% ของผิว) |
| `gift_box` งบ 3,400 | 3,326 tris, `fail=0 warn=2` ไม่มี degenerate triangle |
| `loot_chest` `coins=8, spill=3` | ยัง fail=2: `dihedral` p90 50.1°, `folds` 56 ขอบ |
| `loot_chest` `open_deg=0, spill=0` (ปิดฝา) | ยัง fail=2: `folds` 40 ขอบ, `normal_error` p99 10.1° |
| `striped_box` `label="", sprinkles=0` | แย่ลง fail=3: `dihedral` p90 49.2°, `folds` 22 ขอบ 0.27%, `deviation` p95 5.0 mm |
| `padded_cube` งบ 3,600 | ยัง FAIL `lumpiness` wobble 1.84° |
| `corner_crate` งบ 3,800 | ยัง FAIL `lumpiness` roughness 4.07° |

## 8. ข้อผิดพลาดที่พบบ่อย

| เห็นอะไร | key ที่ขึ้น | สาเหตุ | แก้ |
| --- | --- | --- | --- |
| zebra: แถบหักเป็นจุดรอบปลายก้านวงล้อเซฟและรอบฐาน | `folds` FAIL 11 ขอบ | fold อยู่รอบลูกกลมปลายก้าน (0.09-0.15 m จากศูนย์ประตู) ที่ชิดผิวประตูจม และรอยต่อฐานกับตัว (z ≈ 0.1 m, fillet 0.015) | `spokes=0` หรือเพิ่มงบเป็น 4,500 ผ่านทั้งคู่ (วัดแล้ว) |
| clay: กองเหรียญเป็นก้อนยับ ขอบหีบและฝาเป็นเหลี่ยม zebra: แถบแตกทั่วกอง | `dihedral` FAIL p90 64.8°, `folds` FAIL 90 ขอบ | เหรียญ r 4 cm สูงสุด 31 เหรียญ (24 ในหีบ + 7 หน้าหีบ), กุญแจ, สายรัด และพื้นโพรงที่ z ≈ 0.36 m แบ่งงบ 3,200 fold กระจุกที่พื้นโพรงกับกองเหรียญและโซนกุญแจ | ลดเหรียญหรือปิดฝายังไม่พอ (วัดแล้ว) ต้องเพิ่มงบมากหรือลดชิ้นย่อยหลายจุดพร้อมกัน แล้ววัดใหม่ |
| clay: sprinkles บนฝาเป็นแฉกแหลม มีรอยทแยงแผ่ออกบนฝา ป้าย STASH ยับ | `dihedral` FAIL p90 63.0°, `folds` WARN 24 ขอบ | sprinkles (แคปซูล r 1.1 cm) บนฝาแบน, คำสูงแค่ 7 cm (ต่ำกว่า ~0.15 m ที่ voxel 5 mm), ลายทางชนลอนครีมและหยดที่มุม | ตัดป้ายและ sprinkles ไม่ช่วย (แย่ลง วัดแล้ว) ตัวอักษรจริงจังให้สูง ≥ 0.15 m หรือลด voxel เหลือ 0.003-0.004 แล้ววัดใหม่ |
| zebra: แถบกว้างวนเป็นคลื่นบนหน้าหมอนใหญ่ clay ดูเรียบ | `lumpiness` FAIL shading wobble 1.84-1.93° | หน้าโป่งเตี้ยกว้าง normals ที่โอนมาบนสามเหลี่ยมใหญ่ส่ายเล็กน้อย | เพิ่มงบ 40% ไม่ช่วย (วัดแล้ว) ตัดสินด้วย zebra: แถบที่วนตามโป่งเป็นดีไซน์ ถ้ารับไม่ได้ให้บันทึกเหตุผลตาม `references/qa.md` หัวข้อ 1 |
| clay: คานลังเป็นปล้อง ผิวคานเป็นก้อน | `lumpiness` FAIL roughness 2.71° (งบ 3,800 = 4.07°) | คานยาวหน้าตัดเล็ก (7 cm) 12 เส้น + คานทแยง กินผิวมาก | ยังไม่มีค่าที่วัดแล้วว่าผ่าน ลองลดจำนวนคาน (`brace=False`) แล้ววัด |
| `validate_prop` WARN degenerate triangles | `contract` WARN | ย่อจนเหลือสามเหลี่ยมเสียที่ริบบิ้นหรือโบว์ | งบ 3,400 หายไป (วัดแล้ว) ประตู prop-forge ต้อง warn=0 |
| ริบบิ้นหรือแผ่นแปะลอยห่างผิว หรือจมหาย | | เปลี่ยนขนาดหรือ `puff` ของ host แต่ไม่เปลี่ยน host ใน `conformal` | ส่ง host ที่มีขนาด, รัศมี, `puff` และ `loc` เดียวกับตัวจริงเสมอ (`pillow_host`) |
| palette หลายแผ่นในโฟลเดอร์เดียว | | หลายสคริปต์ใช้ `set_name` เดียวกันแต่ role ต่างกัน | ใช้ `recipes.palette()` ชุดเดียวทุกชิ้น |

อ่านภาพตาม `references/qa.md` หัวข้อ 5: แถบที่วนเป็นระเบียบรอบลอนครีม หมุด และเหรียญเป็นดีไซน์ แถบหักกระจายบนฝาหรือแผงเรียบคือปัญหา

## 9. ประตู QA

1. build แล้วอ่าน `SCULPT_PROP` (หรือ `CONTAINERS_BUILD`) tris ต้องไม่เกินงบ
2. `validate_sculpt.py --blend <out>\<id>.blend --high <out>\_high\<id>_high.blend` ต้องได้ `SCULPT_QA fail=0` และอธิบาย WARN ได้ทุกตัว
3. `render_sculpt.py` แล้วเปิด clay, zebra, colour และ turntable ทุกชิ้น ดูด้านหลังและในหีบด้วย
4. prop-forge `validate_prop.py --blend <out>` ต้องได้ `RESULT fail=0 warn=0` ทุกไฟล์ (กล่องของขวัญที่งบ 2,800 ตกข้อนี้)
5. export ด้วย `export_prop.py --format native --max-res 512 --shared-ytd <set>_tex` (ไม่ใส่ `--factory-startup`) ตาม `references/pipeline.md` หัวข้อ 13
6. รายงานว่ายังไม่ได้ทดสอบในเกม หีบเปิดฝามีกล่องชนของฝาที่หมุนแล้ว ลองเดินชนจากด้านหลัง

ชิ้น demo ที่ยัง fail ห้ามส่งตามสภาพนั้น ใช้ค่าที่วัดแล้วในหัวข้อ 7 หรือแก้แล้ววัดใหม่
