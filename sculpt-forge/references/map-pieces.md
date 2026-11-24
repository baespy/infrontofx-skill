# Map Pieces: ชิ้นแมพโค้งด้วย SweepBuilder

`scripts/blender/sculpt_sweep.py` ปั้นชิ้นสถาปัตยกรรมโค้งขนาด 3-40 m ที่ SDF ทำไม่ไหว (grid หนาแน่นใช้ได้ถึงราว 3 m ที่ voxel 1 cm): ลานขอบมน บันไดโค้งและบันไดตรงจมูกมน ราวจับ ซุ้มโค้ง กระบะต้นไม้ ขอบทางวงแหวน และเส้นไฟฝังพื้น ทุกชิ้นสร้างสองระดับคือ dense (ละเอียดมาก) กับ game (ตามงบ) แล้วโอน normals จาก dense ลง game พร้อม hard-edge guard ผลเป็น shell `.ydr` ตามสัญญา hero shell ของ map-forge ไฟล์นี้ใช้แค่ bpy, bmesh, mathutils, numpy และ stdlib ไม่ import จาก `sculpt_forge.py` หรือ map-forge

## 1. ขั้นตอน

1. วางแผนแมพตาม `map-forge/SKILL.md`: ชนิดแมพ, anchor, งบ, ตำแหน่ง prop GTA แท้ ต้นไม้ ม้านั่ง ไฟถนนใช้ prop แท้ ไม่ปั้นเอง
2. เขียน builder Python (class + `main()`) ด้วย `SweepBuilder` หนึ่ง `begin_shell` ต่อหนึ่ง `.ydr` ทุก shell ใช้ origin ร่วมกันที่ผิวเดิน z = 0
3. `finish(props_dir, lamps)` ได้ `<props>/<shell>.blend` และ report อ่าน `tris`, `reduce.over_budget`, `dihedral`, `floor`, `colliders`, `vcol` ของทุก shell
4. `map_spec()` แล้วแก้ anchor, ตำแหน่ง และ prop vanilla ตาม map-forge
5. `export_map.py` (ไม่ใส่ `--factory-startup`) ต้องได้ `MAP_EXPORT_PASS ... fail=0` แล้ว `inspect_map.py` ต้องได้ `MAP_INSPECT_PASS fail=0` นี่คือประตูของชิ้นแมพ
6. (แนะนำ) `validate_sculpt.py --blend <props>` และ `render_sculpt.py` ดูภาพ clay/zebra/colour ผลของ target map เป็นข้อมูลประกอบ ไม่ใช่ประตู (หัวข้อ 9)
7. รายงานว่ายังไม่ได้ทดสอบในเกม รายการลองในเกม: เดินบนลานและบันไดทุกขั้น (กล่องชนเป็นขั้นบันได ไม่ใช่ทางลาด), ดูตอน 23:00 ว่าพื้นไม่เรืองแสง, เส้นไฟและไฟฝังติดเฉพาะกลางคืน

## 2. demo

```powershell
& $blender -b --factory-startup -P "$sf\sculpt_sweep.py" -- --demo --out '<project>\work\sweep' --export
```

ตัวเลือก: `--demo` (ต้องมี ไม่งั้นพิมพ์แค่ `SWEEP_USAGE` จึง exec ผ่าน MCP ได้ปลอดภัย), `--out <dir>`, `--export` (รัน `export_map.py` และ `inspect_map.py` ให้แบบไม่ใส่ `--factory-startup`), `--no-render`, `--quick`, `--map-forge <dir>` (ค่าเริ่มหาที่ `../../../map-forge/scripts/blender`), `--blender <exe>`, `--prefix <p>` (ค่าเริ่ม `1nfx_sweep`), `--samples <n>` (AO, ค่าเริ่ม 48) `--demo` ลบ object ทั้งหมดในไฟล์ปัจจุบันก่อน ใช้กับ CLI เท่านั้น

ผลลัพธ์: `props/<shell>.blend`, `textures/` (PNG + DDS), `renders/` (clay, tex, vcol, normal และภาพ heat ของ normal ที่ต่าง), `map-spec.json`, `sweep_report.json`, `sweep_demo_all.blend` (รวม dense), `pkg/stream/` และ `inspect_report.json`

ผลที่วัด (Blender 4.2.3, 2026-11-24): รวม 10.6 วินาที (geometry, normals, AO และ save 1.6 วินาที)

| shell | tris (dense) | ผลหลัก |
| --- | --- | --- |
| `1nfx_sweep_plaza` ลาน 12 m ขอบแปรผัน + กระบะ + เส้นทอง | 4,504 (60,188) | dihedral p90 15.0°, floor ตรง 100% (465 จุด) |
| `1nfx_sweep_stairs` บันไดโค้งหนึ่งในสี่วง 8 ขั้น + เส้นไฟ | 4,732 (50,228) | dihedral p90 22.5°, ขั้นที่ซ่อนใต้ลาน 34 จุดถูกข้าม |
| `1nfx_sweep_rail` ราวโค้ง 120° | 7,898 (277,712) | ไม่มีเส้นไฟ, G = 0 |
| `1nfx_sweep_arch` ซุ้ม 4 m + ฐาน + โคมไฟ | 5,568 (98,556) | G เฉลี่ย 19 ใกล้โคม, ไฟ `Drawable.lights` 1 ดวง |

export: `MAP_EXPORT_PASS ydr_ok=4 fail=0 textures=10`, `.ybn` 4,508 prims, shared `.ytd` 10 texture (VRAM 0.21 MB), `.ymap` `content_flags` 65 inspect: `MAP_INSPECT_PASS fail=0 warn=0` normals ระดับ vertex ต่างจาก dense ไม่เกิน 0.21-0.56° เทียบภาพ normal บนจอ (low กับ dense มุมกล้องเดียวกัน): stairs mean 0.24° p99 2.40°, rail 0.24° / 3.68°, ขอบลาน 0.11° / 0.99°, ซุ้ม 0.35° / 2.89° พิกเซลที่ต่างเกิน 5° 0.03-0.6%

## 3. ตัวอย่าง builder

รันจริงแล้ว: build 0.8 วินาที, ลาน 4,714 tris + บันได 340 tris, `MAP_EXPORT_PASS ydr_ok=2 fail=0`, `MAP_INSPECT_PASS fail=0 warn=0`

```python
import importlib
import json
import os
import sys


class CafePlaza:
    def __init__(self, skill, out_dir):
        self.skill = skill
        self.out_dir = out_dir

    def library(self):
        folder = os.path.join(self.skill, "sculpt-forge", "scripts", "blender")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        return importlib.import_module("sculpt_sweep")

    def build(self):
        ss = self.library()
        path = ss.SweepPath
        profile = ss.SweepProfile
        b = ss.SweepBuilder("1nfx_cafe")
        b.standard_roles(os.path.join(self.out_dir, "textures"))
        outline = path.blob_radial((0.0, 0.0, 0.0), [6.0, 6.5, 6.2, 6.6, 6.0, 6.3], start_deg=0.0)
        b.begin_shell("1nfx_cafe_plaza", collision_material="CONCRETE", budget=30000, lod_dist=300.0)
        b.rounded_slab(outline, thickness=0.6, edge_radius=0.18, top_z=0.0, top_role="paving", rim_role="stone", name="plaza")
        b.trim_line(path.offset(outline, -0.45, True, 0.0), width=0.05, closed=True, role="gold", name="plaza_trim")
        b.ring((0.0, 0.0, 0.0), 1.2, profile.bullnose_curb(0.25, 0.3, 0.08, role="stone"), role="stone", name="curb", collide=True)
        b.planter((3.2, 2.0, 0.0), radius=0.7, height=0.5, name="planter")
        b.begin_shell("1nfx_cafe_steps", collision_material="CONCRETE", budget=20000, lod_dist=300.0)
        b.straight_stairs((0.0, -5.6, 0.0), -90.0, 2.4, steps=4, rise=0.15, run=0.4, nosing_radius=0.05)
        report = b.finish(os.path.join(self.out_dir, "props"), lamps=[{"pos": [3.2, 2.0, 1.2], "radius": 3.0, "g": 0.35}])
        spec = b.map_spec("1nfx_cafe_map")
        with open(os.path.join(self.out_dir, "map-spec.json"), "w", encoding="utf-8") as handle:
            json.dump(spec, handle, indent=1)
        return report


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    report = CafePlaza(argv[0], argv[1]).build()
    print("CAFE_PLAZA " + json.dumps({k: v["tris"] for k, v in report["shells"].items()}), flush=True)


if __name__ == "__main__":
    main()
```

```powershell
$mf = "$skill\map-forge\scripts\blender"
$out = '<project>\work\cafe_map'
& $blender -b --factory-startup -P '<project>\work\cafe_map\cafe_plaza.py' -- $skill $out
& $blender -b -P "$mf\export_map.py" -- --spec "$out\map-spec.json" --props "$out\props" --textures "$out\textures" --out "$out\pkg"
& $blender -b -P "$mf\inspect_map.py" -- --dir "$out\pkg\stream" --spec "$out\map-spec.json" --json "$out\inspect_report.json"
```

ผ่าน MCP: exec `sculpt_sweep.py` เข้า namespace ที่ `__name__ == "__main__"` (พิมพ์แค่ usage) แล้วใช้ `ns["SweepBuilder"]`, `ns["SweepPath"]`, `ns["SweepProfile"]` ผลใน 5.3 เหมือน 4.2.3 ทุกตัวเลข แต่ต้องบันทึก shell ด้วย 4.2.3 ก่อน export

## 4. role, shell และ builder

`SweepBuilder(prefix="sweep", tex_dir=None)` เก็บ role, shell และคุณภาพสามระดับ (`SweepBuilder.Path` = `SweepPath`, `SweepBuilder.Profile` = `SweepProfile`)

`standard_roles(tex_dir, tile_size=256)` สร้าง texture ชั่วคราวและ role:

| role | shader | texture | tile | เดินได้ |
| --- | --- | --- | --- | --- |
| `paving` | `normal_spec.sps` (bumpiness 0.9, spec 0.3 / 48 / 0.9) | Diffuse + Bump + Spec 256 px ลายอิฐ 1.2 × 0.6 m | 2.4 m | ใช่ |
| `stone` | `default.sps` | 256 px | 2.0 m | ใช่ |
| `step` | `default.sps` | 256 px | 2.0 m | ใช่ |
| `arch`, `metal`, `soil` | `default.sps` | swatch 16 px | | |
| `gold` | `emissive.sps` (mult 1.6) | swatch `#F2B860` | | |
| `glow` | `emissive.sps` (mult 2.0) | swatch `#FFF1D6` | | |

`add_role(name, shader="default.sps", color="#cccccc", tile=2.0, emissive=False, textures=None, params=None, swatch=None, walkable=False)` `textures` แมพ `DiffuseSampler`/`BumpSampler`/`SpecSampler` ไปยัง PNG, `params` (`bumpiness`, `spec_int`, `spec_falloff`, `spec_fresnel`, `emissive_mult`, `wetness`) กลายเป็น `map_forge_*` ของ material ชื่อ `<prefix>_<role>` ไฟล์ diffuse ที่ขึ้นต้น `swatch_` หรือ `trim_` ถือเป็น swatch (UV ยุบเป็นจุด) role ที่เดินได้ใช้ตรวจพื้นกับกล่องชน

`begin_shell(shell_id, collision_material="CONCRETE", budget=40000, lod_dist=300.0, lights=None)` เริ่ม `.ydr` ใหม่ (id เป็นตัวเล็ก งบถูกตัดที่ 40,000) `lights` คือรายการ `Drawable.lights` ที่เก็บใน `map_forge` meta ทุกคำสั่งหลังจากนี้เพิ่มชิ้นและกล่องชนลง shell นี้

| builder | ลายเซ็น (ย่อ) | ทำอะไร |
| --- | --- | --- |
| `sweep` | `sweep(path, profile, closed=False, caps="flat"\|"round"\|"none", frame=(0,0,1)\|"rmf", role=None, name="sweep", collide=False, vary=None, part=None, cap_role=None, collider_profile=None, normal_mode="transfer")` | กวาดโปรไฟล์ 2D ตามเส้น ฝาโดมได้ `vary=(corner, fn(point, s), rmax)` ให้รัศมีมุมหนึ่งแปรตามระยะทาง |
| `lathe` | `lathe(profile, center=(0,0,0), start_deg=0, end_deg=360, role=None, name="lathe", caps=True, collide=False, part=None, collider_profile=None, normal_mode="transfer")` | หมุนโปรไฟล์ (x = รัศมี, y = z) ขั้วที่ r = 0 เป็นพัดลมทิศถูก |
| `rounded_slab` | `rounded_slab(outline, thickness, edge_radius=0.3, edge_segments=None, bottom_radius=0.0, top_z=0.0, top_role="paving", rim_role="stone", bottom_role=None, top_spacing=1.25, radius_fn=None, name="slab", collide=True)` | ลานหรือแท่นขอบมน ฝาบน/ล่างเป็น Delaunay, game มีจุดในทุก 1.25 m ให้ AO, `radius_fn(point, s)` เปลี่ยนรัศมีขอบ (เช่นลดเป็นจมูกบันได), ผิวบนของกล่องชนอยู่ที่ `top_z` พอดี |
| `arc_stairs` | `arc_stairs(center, inner_radius, start_deg, end_deg, steps=8, rise=0.15, run=None, outer_radius=None, nosing_radius=0.04, top_z=0.0, back=0.3, embed=0.02, descend="out"\|"in", top_nosing=False, role="step", nose_role=None, trims=True, trim_width=0.05, trim_setback=0.05, trim_inset=0.12, trim_role="gold", name="stairs", collide=True)` | บันไดโค้งจมูกมน (game 4 segment ต่อ 90°) มุมหลังคม 90° เส้นไฟหนึ่งเส้นต่อขั้น กล่องชนเป็นขั้น `run` ค่าเริ่ม (outer - inner) / (steps - 1) |
| `straight_stairs` | `straight_stairs(origin, yaw_deg, width, steps=6, rise=0.15, run=0.4, nosing_radius=0.04, top_z=None, back=0.3, embed=0.02, top_nosing=False, role="step", nose_role=None, trims=True, ...)` | บันไดตรงโปรไฟล์เดียวกัน `yaw_deg` = ทิศที่เดินลง ขั้นแรกต่ำกว่า `top_z` หนึ่ง rise และยื่น `back` เข้าใต้ลาน |
| `rail` | `rail(path, height=1.0, post_spacing=1.5, post_radius=0.028, top_profile=None, mid_rails=(0.36, 0.68), mid_radius=0.014, foot_radius=None, foot_height=0.014, embed=0.02, overhang=0.06, role="metal", foot_role=None, name="rail", collide=True, collider_width=0.12)` | ราวจับรูป D ปลายโดม เสากลมระยะเท่ากันพร้อมแผ่นรองมน ราวกลาง กล่องชนเป็นผนังบางตามเส้น |
| `arch` | `arch(center, span=4.0, height=4.4, thickness=0.45, depth=0.6, corner_radius=0.12, yaw_deg=0.0, foot_z=0.0, embed=0.05, profile=None, role="arch", trim=True, trim_width=0.06, trim_role="glow", trim_from=0.35, plinth=(0.8, 0.9, 0.24, 0.06), plinth_role="stone", name="arch", collide=True)` | ซุ้มหัวครึ่งวงกลม (ต่ำกว่า span/2 เป็นโค้งส่วน) หน้าตัด rounded rect, เส้นไฟใต้โค้ง, ฐานขอบมนสองข้าง |
| `planter` | `planter(center, radius=0.85, height=0.55, wall=0.09, soil_drop=0.08, role="stone", soil_role="soil", embed=0.02, name="planter", collide=True)` | กระบะ lathe ขอบ bullnose แผ่นดิน กล่องชนทรงกระบอก |
| `ring` | `ring(center, radius, profile, role="stone", name="ring", collide=False)` | หมุนโปรไฟล์ที่รัศมีหนึ่ง เช่นขอบทางวงแหวน |
| `trim_line` | `trim_line(path, width=0.05, closed=False, frame=(0,0,1), face="up"\|"in"\|"out", height=0.003, embed=0.004, role="gold", name="trim", part=None, caps="flat")` | แถบบางยื่น 3 mm ฝัง 4 mm สำหรับเส้นไฟหรือเส้นทอง เป็นชิ้น game อย่างเดียว (normals อัตโนมัติ) ไม่ถูกย่อ |

## 5. path และ profile

`SweepPath` (static ทั้งหมด จุดเป็น (x, y, z) จุด 2 มิติได้ z = 0):

| tool | ใช้ทำ |
| --- | --- |
| `catmull_rom(points, closed=False, alpha=0.5, step=0.01, z=None)`, `bezier(anchors, handles_out, handles_in, closed=False, step=0.01)` | เส้นโค้งเรียบผ่านจุด |
| `line(p0, p1, step=0.05)`, `arc(center, radius, start_deg, end_deg, z=None, step_deg=0.25)`, `rounded_rect(center, width, depth, radius, z=None)` | เส้นพื้นฐาน |
| `blob(points, z=None, step=0.01)`, `blob_radial(center, radii, start_deg=0.0, z=None)`, `radial(center, radius_fn, z=None, step=0.02)` | outline ออร์แกนิกปิด (ทวนเข็ม) |
| `offset(points, distance, closed=True, z=None)` | เส้นขนาน (บวก = ออกนอกเมื่อทวนเข็ม) สำหรับขอบทางและเส้นไฟ |
| `sector(points, center, start_deg, end_deg)`, `trim(points, s0, s1)`, `extend(points, d0, d1)`, `point_at(points, s)` | ตัดช่วง ต่อปลาย หาจุดตามระยะ |
| `resample(points, closed, max_turn_deg, max_len, max_sagitta)` | สุ่มจุดใหม่ตามมุม ความยาว และ sagitta |
| `frames(points, closed, up)` | frame ของการ sweep `up=(0,0,1)` ตั้งตรง หรือ `"rmf"` แบบหมุนน้อยสุด |
| `arch_curve(center, axis, half_span, height, z_start)`, `transform2d(points, angle_deg, offset)`, `arc_segments(radius, angle, sagitta)`, `smoothstep(e0, e1, x)` | ตัวช่วย |

`SweepProfile` เป็นรูปตัดในระนาบ (x, y) ของ frame: x ไปทาง `t × up` (นอกเส้นเมื่อเดินทวนเข็ม) และ y ขึ้น มุมรัศมี 0 = มุมคม (แยก normal), มุมที่มีรัศมี = smooth

| profile | ใช้ทำ |
| --- | --- |
| `round(radius)`, `half_round(radius, base=0.0)` | ท่อ ราว ขอบครึ่งวง |
| `rounded_rect(width, height, radius)` | หน้าตัดซุ้มหรือคาน |
| `bullnose_curb(width, height, front_radius, back_radius=0.01, anchor=0.5)` | ขอบทาง |
| `handrail(width, height, bottom_radius=None)` | ราวจับรูป D |
| `band(width, height=0.003, embed=0.004, face="up")` | แถบเส้นไฟ |
| `slab_edge(thickness, top_radius, bottom_radius=0.0, ...)` | ขอบลาน (x = 0 คือขอบนอก) |
| `stairs(steps, rise, run, nosing_radius, top_z=0.0, back=0.3, embed=0.02, top_nosing=False, ...)` | รูปตัดบันได |
| `custom(points, radii=0.0, closed=True, role=None, segments=None)` | กำหนดเอง ใส่รัศมีต่อมุมได้ |
| `with_radius(i, r)`, `mirrored_x()`, `shifted(dx, dy)` | แก้โปรไฟล์ |

คุณภาพสามระดับ:

| ระดับ | เส้นทาง | arc ของโปรไฟล์ |
| --- | --- | --- |
| game | หมุนไม่เกิน 4° ต่อช่วง, ช่วงยาวไม่เกิน 0.6 m, sagitta ของคอร์ดไม่เกิน 4 mm (บีบเป็น max(1.5 mm, 5% ของรัศมีโปรไฟล์เล็กสุด)) | sagitta 2.5 mm, 4-8 segment ต่อ 90° (รอบวงอย่างน้อย 16) |
| dense | 0.75°, 8 cm, arc ทีละ 4.5° | ละเอียดมาก (lathe sagitta 0.2 mm) |
| collider | 10°, 1.5 m | 1-2 segment ต่อ 90° |

## 6. `finish()` และ normals

`finish(props_dir, lamps=None, ao=True, ao_distance=1.6, ao_samples=48, save=True)` ทำทีละ shell: สร้าง mesh game และ dense, triangulate, ย่อตามงบ, โอน normals + hard-edge guard, join ด้วย numpy + `normals_split_custom_set`, กล่องชน manifold หันออก แล้ว bake AO ด้วย Cycles CPU (ทุก shell บังกัน) เขียน `Color 1`, meta และบันทึกไฟล์ต่อ shell คืน report

hard-edge guard (`transfer_normals(lo, hi, guard_deg=20.0, nudge=0.0015)`): Data Transfer แบบ `POLYINTERP_NEAREST` ให้ loop บนขอบคม 90° เอา normal จากหน้าฝั่งผิด (110-1,213 loop ต่อชิ้น ผิดถึง 90°) guard จึงสุ่ม normal ใหม่จาก dense ที่จุดเข้าไปในหน้าตัวเอง 1.5 mm ให้ทุก loop บน vertex ของขอบคม และทุก loop ที่ต่างเกิน 20° ค่าที่สุ่มได้ต้องห่างจาก normal ของหน้าไม่เกิน 60° ถ้าเกินจะสุ่มใหม่ที่ 0.1 mm จากมุม แล้วที่ 35% เข้าไปในหน้า ถ้ายังไม่ได้จะคงค่าเดิมหรือใช้ normal ของหน้า (แก้ normal_error ของม้านั่ง p99 16.2° → 8.4°) ห้ามถอด guard ออก

ย่อเมื่อเกินงบ: planar dissolve 0.5° บนหน้าแบนที่ระบุ (ใต้ลาน ตัวขั้นบันได) ก่อน แล้ว COLLAPSE ด้วย ratio ≥ 0.25 เฉพาะชิ้นที่ย่อได้และ > 400 tris (เส้นไฟไม่ถูกย่อ) และ mark ขอบ > 60° เป็นคม ทดสอบงบ 2,600: 5,348 → 2,562 tris ถ้า `over_budget` เป็น true ให้ลดคุณภาพหรือแยก shell อย่าพึ่ง collapse เพราะทำลาย topology แบบ parametric

## 7. RAGE vertex colour และ UV

- `Color 1` BYTE_COLOR / CORNER: R = B = 0.58 + 0.42·AO (AO จาก Cycles, ระยะ 1.6 m, 48 spp), G = 0 กลางแจ้ง หรือ g × (1 - smoothstep(0, radius, d)) ใกล้โคมจาก `lamps=[{"pos": [x, y, z], "radius": r, "g": 0.25-0.45}]`, loop ของ role emissive = 255 ทุกช่อง, A = 255 เขียนผ่าน `color_srgb` เพราะ Sollumz export `color_srgb` × 255
- รัศมีโคมให้เล็ก `inspect_map` เตือนเมื่อ G เฉลี่ยกลางแจ้ง > 45 (demo ซุ้ม 19, ตัวอย่างลาน 14.9) หน้าที่ซ่อนหรือฝังได้ AO = 0 (R 148) ไม่มีผลต่อภาพ
- UV ชั้นเดียว `UVMap 0` แบบ world tiling: role ที่มี texture ใช้ 1 UV = `tile` เมตร (paving 2.4 m, stone/step 2.0 m) follow ไปตามเส้น sweep, role swatch ยุบ UV เป็นจุด (VRAM ต่ำ) ห้ามใช้ smart UV atlas แผ่นเดียวกับลานใหญ่
- material ชื่อ `<prefix>_<role>` มี `map_forge_shader` และ `map_forge_*` image node ชื่อ `DiffuseSampler`/`BumpSampler`/`SpecSampler` PNG พร้อม DDS ที่เข้ารหัสไว้แล้วอยู่ใน `<out>/textures` ชิ้น `normal_spec.sps` ได้ TANGENT0 จาก `UVMap 0`

## 8. ไฟล์ shell และ map spec

- `<props>/<id>.blend`: ฉาก `<id>_export`, mesh `<id>` (transform เป็นศูนย์, ผิวเดิน z = 0), กล่องชน `<id>_col_N` ใน `<id>_collision` (WIRE, `hide_render`, `map_forge_collision` = `mesh`) บันทึกด้วย `libraries.write` แบบพาธ texture absolute ห้ามย้ายโฟลเดอร์ textures หลัง build (export ใช้ `--textures` อยู่แล้ว)
- `root["map_forge"]` = `id`, `style` (`sculpt_sweep_v1`), `collision_material`, `lights`, `tris`, `budget`, `lod_dist`, `dense_tris`, `parts`, `colliders`
- report ต่อ shell: `tris`, `dense_tris`, `budget`, `reduce` (`before`, `dissolved_faces`, `collapse_ratio`, `after`, `over_budget`), `parts` (`tris`, `guard_fixed`, `modifier_wrong_side`, `vertex_err`, `interior_err`), `normal_drift_after_join_deg`, `colliders` (`non_manifold_edges`, `degenerate`, `volume_m3`), `vcol` (`R_min`, `R_mean`, `G_mean_outdoor`, `G_max`, `emissive_loops`), `dihedral` (`smooth_p50`, `smooth_p90`, `smooth_max`, `frac_over_30`, `frac_over_45`, `hard_share`, `open_edges`), `floor` (`samples`, `hidden`, `missed`, `max_dz_m`, `within_2cm`), `has_custom_normals`, `all_triangles`, `uv_layers`, `color_attrs`, `bbox`, `blend`
- `map_spec(map_name, center=(0,0,520), warp=None, floor_z=None, vanilla=None, budgets=None)` สร้างสเปก map-forge ขั้นต่ำ: `shared_ytd` `<map>_tex`, งบค่าเริ่ม (`max_total_tris` 60,000, `max_ytd_vram_mb` 6, `max_disk_mb` 8, `max_outdoor_vcol_g` 45), anchor (ymap, ybn `<map>_col`, จุดวาร์ปสูงกว่า center 0.5 m, `expected_floor_z`), `texture_rules`, `prop_overrides` ต่อ shell (lod, collision, lights) และ entity หนึ่งตัวต่อ shell ที่ pos 0 แก้ center และเพิ่ม prop vanilla ตาม map-forge ก่อนใช้จริง
- `SweepBuilder.run_tool(blender, script, args, factory=False, timeout=1800)` รัน `export_map.py`/`inspect_map.py` ใน subprocess แล้วเก็บบรรทัดที่มี tag
- `SweepPreview(out_dir, resolution, samples)` render clay/tex/normal/vcol และ `compare_normals(png_a, png_b, heat_path)` วัดมุม normal บนจอระหว่าง low กับ dense

## 9. งบและประตู

| เรื่อง | เกณฑ์ |
| --- | --- |
| tris ต่อ shell | ≤ 40,000 (`inspect_map` เตือนเกิน 45,000 ต่อ drawable) งบรวมตามชนิดแมพใน `map-forge/references/studio-benchmarks.md` |
| export | `MAP_EXPORT_PASS ydr_ok=N fail=0` |
| inspect | `MAP_INSPECT_PASS fail=0` (ตรวจ RSC7, FVF รวม TANGENT0, `DIFFUSE` G กลางแจ้ง, VRAM และ mip ของ ytd, floor Z ใน ybn, `content_flags` ของ ymap) |
| report ของ `finish` | `over_budget` false, `dihedral.frac_over_30` ≈ 0, `floor.within_2cm` 1.0, กล่องชน `non_manifold_edges` 0 และปริมาตรบวก |

`validate_sculpt.py --blend <props>` กับ shell ใช้เกณฑ์ map (หัวข้อ 3 ของ `references/qa.md`) demo ได้ `SCULPT_QA fail=1 warn=7` ทั้งที่ export และ inspect ผ่าน ที่คาดได้คือ: ราว FAIL `uv_layers` เพราะทุก role เป็น swatch (UV คงที่ ซึ่ง default.sps ใช้ได้), WARN `interpenetration` ทุก shell เพราะชิ้นแยกส่วนโดยตั้งใจ, บันได WARN `walk_surface` เพราะลงต่ำจาก z = 0, ลาน WARN `flat_panels` เพราะไม่มี `normals` ใน meta (เครื่องมือเดาว่าเป็น weighted), ราว WARN `soft_splits` 144 ขอบ ตัวอย่างลานในหัวข้อ 3 ได้ fail=0 warn=4 แบบเดียวกัน ใช้ภาพ clay/zebra และ `MAP_INSPECT_PASS` ตัดสิน

## 10. ข้อจำกัดที่รู้

- ยังไม่ได้ทดสอบใน FiveM หรือ CodeWalker สิ่งที่ตรวจแล้วคือภาพใน Blender, `export_map`, `inspect_map` และ round trip ด้วย PyMateria (NORMAL ใน `.ydr` ตรงกับ Blender สูงสุด 0.035°)
- `export_map.py` export แค่ HIGH LOD ไม่มี LOD chain (100/55/27/12%) สำหรับ shell lod ใน ytyp 300 m (ราว 200 m)
- `interior_err` ต่อชิ้นเทียบกับจุดใกล้สุดของ dense จึงเกินจริงบนท่อบาง (ราวกลาง p95 ~6.5°) ใช้การเทียบภาพ normal บนจอ (p99 ≤ 3.7°) เป็นเกณฑ์
- COLLAPSE fallback ทำลาย topology และ ratio ต่ำสุด 0.25
- shell ต้องบันทึกด้วย 4.2.3 สำหรับ `export_map` (5.x เปิดใน 4.2.3 ไม่ได้)
- anchor ของ demo อยู่บนฟ้า (0, 0, 520) บันไดลงไปถึง z -1.2 โดยไม่มีพื้นรับ และไม่มี prop vanilla
- texture เป็น placeholder (อิฐ หิน ขั้นบันได 256 px และ swatch 16 px) เปลี่ยนเป็นของจริงจาก map-forge (เช่น Poly Haven CC0) ก่อนใช้งาน
- กล่องชนบันไดเป็นขั้น ไม่ใช่ทางลาด ความรู้สึกตอนเดินยังไม่ได้ทดสอบ
- `straight_stairs`, `ring`, `bullnose_curb` และ `planter` ผ่าน export/inspect ในตัวอย่างหัวข้อ 3 แล้ว แต่ยังไม่ได้ลองในเกม
