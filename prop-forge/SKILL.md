---
name: prop-forge
description: ปั้น prop FiveM สไตล์ของเล่นแบรนด์เซิร์ฟเวอร์ (toy-brand props) เป็นชุดเดียวกันทั้งเซ็ต เช่น ป้าย Garage/Pound แบบเสาลูกศร, ป้าย Shop, ตู้ ATM, ตู้เซฟ, กล่อง stash, หีบ loot เปิดฝามีเหรียญ, โต๊ะคราฟต์, หัวมาสคอตลอยเป็น marker ด้วย Blender (CLI หรือ Antigravity + Blender MCP) จากสเปก JSON แล้วตรวจ ตั้งชนและเตรียม export เป็น .ydr/.ytd/.ytyp ใช้เมื่อผู้ใช้ขอปั้น prop, ทำ prop เซิร์ฟเวอร์, ทำป้าย, ทำตู้ ATM/ตู้เซฟ/กล่อง/โต๊ะคราฟต์, ทำ marker, ทำ prop ตามคลิปหรือรูปอ้างอิง, เปลี่ยนสี/แบรนด์ของชุด prop, หรือเพิ่ม prop ใหม่เข้า 1nfx_prop (prop modeling, custom prop, ytyp, stream prop, Sollumz, slime, mascot, Antigravity)
---

# Prop Forge

สร้างชุด prop ประจำเซิร์ฟเวอร์ที่ทุกชิ้นดูเป็นแบรนด์เดียวกัน (สีชุดเดียว มาสคอต มงกุฎ สไลม์ไหล ตัวหนังสือแบบสติกเกอร์) จากสเปก JSON ไฟล์เดียว ได้ `.blend` ต่อชิ้น, ภาพ preview, texture palette ของทั้งชุด, กล่องชน และรายงาน tris ทุกชิ้นสร้างจาก primitive ที่ bevel แล้ว รวมเป็น mesh เดียว origin อยู่กลางพื้น ด้านหน้าหัน -Y หน่วยเมตร

แนวที่ผู้ใช้ต้องการถอดมาจากคลิปอ้างอิงของผู้ใช้ (2026-11-11) อธิบายเป็นตัวหนังสือใน `references/style-toybrand.md` ส่วนภาพเป้าหมายที่ใช้ได้คือผลงานของเราเองใน `references/targets/` (ชุดตัวอย่าง GOO LAB) ไม่มีภาพจากคลิปอยู่ใน skill

## ขั้นตอน

1. **รับโจทย์ & เจน Concept Art ก่อนปั้น (V11 Concept-First):** กำหนดชื่อชุด (`set` ขึ้นต้น `1nfx_`), แบรนด์, พาเลตต์หลัก และรายการ prop จากนั้นเจนภาพ Concept Art 3/4 สไตล์ Pop-Mart / Vinyl Toy ของทุกชิ้นก่อน (ตรวจเทียบโลโก้และมาสคอตทางการของเซิร์ฟเวอร์ให้ตรง 100%) เพื่อใช้เป็นแบบอ้างอิงให้ช่างปั้น 3D และ QA ตรวจเทียบ 1:1 ห้ามลอกชื่อ โลโก้ หรือมาสคอตของคนอื่น
2. **เลือกเครื่องมือปั้น:**
   - **งานสายสตรีทไวนิล/สเปก JSON (`vinyl_toy`):** คัดลอก `templates/prop-spec.example.json` ไปไว้ `<งาน>/source/props.json` แล้วรัน `scripts/blender/forge_prop.py`
   - **งานสายคาวาอิ/ของเล่นนุ่มนิ่ม Pop-Mart (`kawaii_studio.py` V11 — แนะนำสำหรับธีม Kawaii / Billie School):** เขียนสคริปต์ปั้นรายชิ้นด้วย `KawaiiBuilder` ใน `scripts/blender/kawaii_studio.py` (Subsurf/Bevel/Lathe/Swept-Tube, กันสาดหยัก, หมอนเมฆเนียน, หน้ามาสคอต 2D ทางการบนโดมโค้ง 3D, แพ็ก decal ไม่เกิน 4 วัสดุอัตโนมัติ) พร้อมริก `.ycd`
3. **ปั้นรอบแรกและตรวจด้วยตาเทียบ Concept:** เปิดดู `<id>_preview.png` ทุกชิ้นเทียบข้างกับภาพ Concept Art และ "เกณฑ์ตรวจหน้าตา" ใน `references/style-toybrand.md` ห้ามปล่อยงานทรงกล่องแข็ง หน้าลูกกลมแปะ หรือชิ้นที่ถูก decimate จนบุบ
4. **แก้จนลงตัว:** ขัดสัดส่วน/แสง/ตำแหน่งดาว/หู/กันสาดจนทุกชิ้นผ่านเกณฑ์ความน่ารักและไม่เกินงบ tris โดยไม่ต้อง decimate จากนั้นเรนเดอร์ `lineup.png` รวมทุกชิ้น
5. **ลวดลายพิเศษ (ถ้ามี):** ใช้ `prepare_billie_art()` / `make_text_banner()` / `decal_card()` ของ `kawaii_studio.py` (เจนป้ายฟอนต์ TitanOne ขอบสติกเกอร์เนียน 100% ภายใน Blender ด้วย NumPy โดยไม่ต้องลง PIL) หรือเจน PNG พื้นใสตาม `references/pipeline.md`
6. **ตรวจสัญญา:** รัน `scripts/blender/validate_prop.py` จนได้ `fail=0 warn=0` ทุกไฟล์
7. **Export:** รัน `scripts/blender/export_prop.py` (ไม่ใส่ `--factory-startup`) ด้วย `--format native --max-res 512 --shared-ytd <ชื่อ>_tex` ได้ `.ydr` + `.ytyp` + `.ycd` + shared `.ytd` ไฟล์เดียวพร้อมตรวจ PyMateria FVF อัตโนมัติ (หมายเหตุ: PyMateria มีสัญญาอนุญาตกับ Take-Two/Rockstar ห้ามติดตั้งแทนผู้ใช้)
8. **เชื่อมเข้าเซิร์ฟเวอร์:** ทำตาม `references/integration.md` (stream, `data_file "DLC_ITYP_REQUEST"`, โค้ด spawn ที่ปล่อยหน่วยความจำ) สำรองไฟล์ก่อนแก้ resource จริงทุกครั้ง
9. **ซิงก์และรายงาน:** ถ้าแก้ไฟล์ใน skill ให้รัน `scripts/sync-antigravity.ps1 -Force` และตรวจด้วย `-Check` รายงานผู้ใช้แยกให้ชัดว่าอะไรตรวจแล้ว อะไรยังไม่ได้ลองในเกม

## คำสั่ง

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
$skill   = '<project>\.claude\skills\infrontofx\prop-forge'
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --lineup
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --only 1nfx_goo_atm
& $blender -b --factory-startup -P "$skill\scripts\blender\validate_prop.py" -- --blend work\build
```

ตัวเลือกของ `forge_prop.py`: `--only id1,id2` สร้างเฉพาะชิ้น, `--lineup` เรนเดอร์ทุกชิ้นเรียงกัน, `--bake 512` (แนะนำสำหรับงานเกมจริง: เร็ว + ลื่น + ชัดไม่วุ้น ด้วย flood-fill 0% ขอบดำ) หรือ `--bake 1024`, เปิด `"low_poly": true` ในสเปกเพื่อลด tris ลง ~50% โดยยังคงผิวเงา smooth-shaded ไวนิล, `--no-render` ไม่เรนเดอร์, `--samples 24`, `--list` ดู archetype และ role ของสี ทั้งชุด 12 ชิ้นใช้เวลาราวครึ่งนาที

ตัวเลือกของ `export_prop.py`: `--format native` (ค่าเริ่ม), `--max-res 512` (ย่อและเข้ารหัส DDS ด้วย PCA DXT1 สำหรับ atlas ทึบ / DXT5 + RGB bleed + unsharp mip สำหรับ decal พื้นใส), `--shared-ytd <ชื่อ>` (เช่น `1nfx_ext_tex` รวมทุก texture แบบไม่ซ้ำลง `.ytd` ไฟล์เดียว ลด VRAM ~90% และตั้ง `hdTextureDist = lodDist` เพื่อไม่ให้เกมลดความละเอียดจนเบลอ)

## เลือกอ่าน

| งาน | อ่าน |
| --- | --- |
| แนวศิลป์ สี สัดส่วน ลวดลาย กฎองค์ประกอบ เกณฑ์ตรวจหน้าตา โหมด V5 Vinyl Toy-Brand ถอดสไตล์ใหม่จากรูป/คลิป | `references/style-toybrand.md` |
| archetype ทั้ง 11 แบบ ขนาด พารามิเตอร์ งบ tris สคีมาสเปก และวิธีเพิ่ม archetype ใหม่ | `references/archetypes.md` |
| สัญญาพิกัด, palette กับ bake, decal จาก AI, collision, LOD, export ด้วย Sollumz, ytyp | `references/pipeline.md` |
| ปั้นผ่าน Antigravity + Blender MCP, ไฟล์ .blend 4.2 กับ 5.3, ทำงานร่วมกับ agent อื่น | `references/antigravity.md` |
| fxmanifest, ชื่อไฟล์ stream, โค้ด spawn, marker หมุน/ลอย, QA ในเกม | `references/integration.md` |
| ภาพเป้าหมายของชุดตัวอย่าง | `references/targets/` |

## เครื่องมือ

| ไฟล์ | หน้าที่ |
| --- | --- |
| `scripts/blender/forge_prop.py` | สร้าง prop จากสเปก JSON: **15 archetype** (`sign_post`, `parking`, `kiosk_sign`, `atm`, `safe`, `crate`, `chest`, `workbench`, `mascot_marker`, `airdrop`, `powerbox`, `redbox`, `waterpipe`, `gachapon`, `washmoney`) พร้อมโหมด `"style": "vinyl_toy"` และ `"style": "kawaii_billie"`, ริกกระดูก + animation (`"animate": true`), รวม mesh, ล้างเศษ, decal, กล่องชน, preview, lineup, `report.json` |
| `scripts/blender/kawaii_studio.py` | **V11 Kawaii Plush Artisan Studio Toolkit (`KawaiiBuilder`)** สำหรับปั้นคอลเลกชันสไตล์ Pop-Mart / Animal-Crossing / Sanrio แบบ **Concept-First** ระดับพรีเมียม: primitive แบบ Subdivision-Surface / Lathe / Swept-Tube (`plush_box`, `plush_pill`, `plush_cyl`, `lathe`, `plush_torus` รองรับ `arc_deg`, `plush_tube`, `plush_extrude`, `plush_frame`, `plush_cloud*`, `plush_star`, `plush_heart`, `cafe_awning` กันสาดหยักสลับสี), มาสคอต 3D `billie_bear_plush` (รองรับ 4 บ้าน + หน้า 2D ทางการคมชัดบนโดมโค้ง 3D หรือปั้น 3D ล้วน + ตัวตุ๊กตานั่ง + หมอนเมฆ), ตัวเจนป้าย `billie-ui` (`prepare_billie_art`, `make_text_banner`, `decal_card`, `text_sign`, `striped_pbr_tex`) ที่แพ็กวัสดุอัตโนมัติไม่เกิน 4 slot เสมอ, Cycles Soft Plush AO Baker + flood-fill 100%, ริกกระดูก rest-exact (`u=0`), และตัวเรนเดอร์พรีวิว/lineup สตูดิโออุ่น (`render_lineup`) |
| `scripts/blender/validate_prop.py` | ตรวจ `.blend` ทีละไฟล์หรือทั้งโฟลเดอร์: ชื่อ, transform, origin ที่พื้น, ขนาด, tris เทียบงบ, NaN, สามเหลี่ยมเสีย, UV, วัสดุ, texture ยกกำลังสอง, กล่องชน, ริกกระดูก/vertex group/keyframes (เมื่อมี animation), orphan ใช้ได้ทั้ง headless และใน Blender สดผ่าน MCP |
| `scripts/blender/export_prop.py` | ใช้ Sollumz แปลง `.blend` เป็น Drawable (นิ่งหรือ Armature ริกกระดูก) + บังคับ `UVMap 0` และ `Color 1` สีขาว (255) + embedded collision + ytyp (ตั้ง `clipDictionary`, `flag10`/`flag20`/`flag30`, `textureDictionary` และ `hdTextureDist = lodDist` อัตโนมัติ) + `.ycd` ไบนารี (`--format native`) หรือ `.ycd.xml` (`cwxml`) + รวม shared `.ytd` ไฟล์เดียวด้วย `--shared-ytd <name>` และตรวจ PyMateria FVF อัตโนมัติหลัง export |
| `scripts/blender/dds_codec.py` | ตัวเข้ารหัส DDS แบบ vectorized PCA DXT1 (BC1, 4 bpp) / DXT5 (BC3, 8 bpp) พร้อม linear premultiplied-alpha mipmaps, RGB bleed กันขอบดำ และ unsharp mip ระดับ 1-3 เพื่อภาพคมไม่วุ้นและประหยัด VRAM สูงสุด |
| `scripts/blender/ycd_rsc7.py` | คอมไพเลอร์/ดีคอมไพเลอร์ `.ycd` ไบนารี (`RSC7 v46`) ล้วนด้วย Python สำหรับแปลง `.ycd.xml` ของ Sollumz เป็น `.ycd` พร้อมสตรีมใน FiveM โดยไม่ต้องใช้ CodeWalker GUI (มีตัวตรวจ round-trip ด้วย) |
| `scripts/blender/render_anim_preview.py` | เรนเดอร์พรีวิวแอนิเมชันจาก `.blend` ที่ริกแล้วเป็น GIF วนลูปและวิดีโอ H.264 MP4 รวมทุกช็อต (Lineup, Airdrop, Power Box ตู้ไฟ, Safe เปิด-ปิด, Marker หมุนเหนือ Stash, Loot Chest) |
| `scripts/sync-antigravity.ps1` | ซิงก์ skill ไป `.agents/skills/prop-forge` ให้ Antigravity ใช้ (`-Check` ตรวจอย่างเดียว, `-Force` เขียนทับ) |
| `templates/prop-spec.example.json` | สเปกชุดตัวอย่าง GOO LAB ครบ 9 ชิ้น |
| `assets/fonts/` | ฟอนต์ OFL (Titan One, Russo One) สำหรับตัวหนังสือบน prop |

ใช้แค่ Blender 4.2.3 (`C:\Tools\blender-4.2.3-windows-x64\blender.exe`) ไม่ต้องลง add-on หรือ Python แยกตอนปั้นและตรวจ Sollumz ใช้เฉพาะตอน export

## กฎที่ห้ามข้าม

**ต้นฉบับ.** คลิปอ้างอิงเป็นของเซิร์ฟเวอร์หรือผู้สร้างอื่น ใช้ได้แค่ทิศทางสไตล์ ห้ามใช้ชื่อแบรนด์ โลโก้ มาสคอต หรือ texture ของเขา ทุกชุดต้องมีชื่อแบรนด์ของเราเองในสเปก ห้ามใส่เครื่องหมายการค้าจริงลงบน prop

**สัญญาพิกัด.** mesh เดียวชื่อเดียวกับไฟล์ (`[a-z0-9_]`), transform apply แล้ว, จุดต่ำสุดอยู่ที่ z = 0 กลาง X/Y, ด้านหน้าหัน -Y, หน่วยเมตร, กล่องชนชื่อ `<id>_col_N` (marker ไม่มีชน) ห้ามแก้ชื่อหรือ origin หลังจากเชื่อมเข้าเซิร์ฟเวอร์แล้ว

**งบ.** tris ไม่เกินงบใน `references/archetypes.md`, วัสดุไม่เกิน 4 (diffuse, emissive, decal), texture ยกกำลังสองไม่เกิน 2048 ทั้งชุดใช้ palette ร่วมกันไฟล์เดียว รายละเอียดที่เล็กกว่า 2 ซม. ให้ใส่เป็น decal ไม่ใช่ geometry

**ไฟล์ระบบ.** ห้ามแตะ resource ที่มี `.fxap` การแก้ `fxmanifest.lua`, config ของ resource อื่น และการรีสตาร์ตเซิร์ฟเวอร์ ต้องสำรองไฟล์ก่อนและให้ผู้ใช้ยืนยัน

**ทำงานร่วมกัน.** Antigravity, Codex และ Claude Code แก้โฟลเดอร์นี้ได้พร้อมกัน ต้นฉบับอยู่ที่ `.claude/skills/infrontofx/prop-forge` ห้ามแก้สำเนาใน `.agents/skills/prop-forge` โดยตรง หนึ่งชุด prop หนึ่ง agent และห้ามสอง agent ยิงคำสั่งเข้า Blender สดตัวเดียวกันพร้อมกัน

**รายงานตามจริง.** `RESULT fail=0` แปลว่าโครงไฟล์ `.blend` ผ่านสัญญา ภาพ preview เป็นการเรนเดอร์ Eevee ไม่ใช่ภาพในเกม จนกว่าผู้ใช้จะ export และเห็นในเกมเอง ให้บอกว่ายังไม่ได้ทดสอบในเกม เมื่อผู้ใช้รายงานผลในเกม ให้บันทึกลง "สิ่งที่พิสูจน์แล้ว" ใน `references/integration.md`

## รูปแบบโค้ด

Lua ที่เขียนเพิ่ม (spawn, interaction) ให้ทำตาม `infrontofx` ใน `SKILL.md` ระดับบนของแพ็กนี้: OOP module table, ไม่มี comment, ไม่มี `local function` ระดับไฟล์, 4 ช่องว่าง, double quotes, trailing comma, ใช้ `lib.spawn.pointProp` ของ `1nfx_lib`
