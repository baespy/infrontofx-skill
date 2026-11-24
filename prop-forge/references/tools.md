# Tools and steps (full text)

The original intro, step list, commands, script options and tool catalog, moved here from `SKILL.md` on 2026-11-24. `SKILL.md` keeps the short Quick path. Machine paths are written as `<blender-4.2.3>` and `<project>`.

## Original intro

สร้างชุด prop ประจำเซิร์ฟเวอร์ที่ทุกชิ้นดูเป็นแบรนด์เดียวกัน (สีชุดเดียว มาสคอต มงกุฎ สไลม์ไหล ตัวหนังสือแบบสติกเกอร์) จากสเปก JSON ไฟล์เดียว ได้ `.blend` ต่อชิ้น, ภาพ preview, texture palette ของทั้งชุด, กล่องชน และรายงาน tris ทุกชิ้นสร้างจาก primitive ที่ bevel แล้ว รวมเป็น mesh เดียว origin อยู่กลางพื้น ด้านหน้าหัน -Y หน่วยเมตร

แนวที่ผู้ใช้ต้องการถอดมาจากคลิปอ้างอิงของผู้ใช้ (2026-11-11) อธิบายเป็นตัวหนังสือใน `references/style-toybrand.md` ส่วนภาพเป้าหมายที่ใช้ได้คือผลงานของเราเองใน `references/targets/` (ชุดตัวอย่าง GOO LAB) ไม่มีภาพจากคลิปอยู่ใน skill

## Original step list

1. **รับโจทย์ & เจน Concept Art ก่อนปั้น (V11 Concept-First):** กำหนดชื่อชุด (`set` ขึ้นต้น `1nfx_`), แบรนด์, พาเลตต์หลัก และรายการ prop จากนั้นเจนภาพ Concept Art 3/4 สไตล์ Pop-Mart / Vinyl Toy ของทุกชิ้นก่อน (ตรวจเทียบโลโก้และมาสคอตทางการของเซิร์ฟเวอร์ให้ตรง 100%) เพื่อใช้เป็นแบบอ้างอิงให้ช่างปั้น 3D และ QA ตรวจเทียบ 1:1 ห้ามลอกชื่อ โลโก้ หรือมาสคอตของคนอื่น
2. **เลือกเครื่องมือปั้น:**
   - **งานสายสตรีทไวนิล/สเปก JSON (`vinyl_toy`):** คัดลอก `templates/prop-spec.example.json` ไปไว้ `<งาน>/source/props.json` แล้วรัน `scripts/blender/forge_prop.py`
   - **งานสายคาวาอิ/ป๊อปอาร์ต Low-Poly คมกริบ + มาสคอต Pure Quad-Flow 4 บ้านความละเอียดสูง + สถาปัตยกรรม 3D ไร้ป้ายแบน (`kawaii_studio.py` V18 + `billie_v7_assets.py` — แนะนำสำหรับธีม Kawaii / Billie School):** เขียนสคริปต์ปั้นรายชิ้นด้วย `KawaiiBuilder(..., low_poly=True)` ใน `scripts/blender/kawaii_studio.py` ร่วมกับคลังโมเดล Quad-Flow ใน `scripts/blender/billie_v7_assets.py` — ตัวตู้/เครื่องมือใช้ **Anti-Playdough Crisp Engine** (`crease_deg=32.0`, Matte Collectible Vinyl `spec_int=0.05–0.09` กันแสงแดด GTA V เงาเป็นวุ้น + Crevice Vertex AO `Color 1`), ชิ้นส่วนออร์แกนิกติด `organic_smooth=True` (`68°`) พร้อม **มาสคอต Pure Quad-Flow ความละเอียดสูงตรงต้นฉบับ 4 บ้าน 1:1** (`brown` Bear, `pink` Lop-Bunny + ผมเปีย 2 ข้าง, `skyblue` Floppy-Puppy + คอปกแดง-น้ำเงิน + ดาว 5 แฉก, `grey` Monster-Kitty + เขี้ยวขาว 2 ซี่ + ลายเสือ; มีหูคนโผล่ข้างแก้ม, ผมหน้าม้า 3 ลอนฟู + กิ๊บโคลเวอร์ 4 แฉก 2 ชิ้น, อุ้งมือชมพู+นิ้วมือปั้นครบ 3 ท่า `full` `3,648–4,472t` / `peek` `2,648–3,208t` / `head` `2,248–3,000t`), แผ่นหน้าอนิเมะ V8 `1024x1024` (`assets/mascots/billie_faces_v8.png`, `512x512` ต่อบ้าน ตาโตเป็นประกาย + จมูกชมพูละมุน + เงาหน้าม้า), พาเลตต์ผ้าขนนุ่ม Micro-Fleece (`billie_master_pal.png`), ก้อนเมฆ Cumulus ชิ้นเดียว (`add_sculpted_cloud_v7`), และคลังกิมมิก/สถาปัตยกรรม 3D ไร้ป้ายสติกเกอร์แบน (หลังคาผ้าใบคาเฟ่, โคมไฟคองู, เหรียญตรา 3D, สายยางม้วน, ครัวซองต์, เครื่องมือ 18 ชิ้น) ช่วยลด `billie_prop_tex.ytd` เหลือเพียง **5 เท็กซ์เจอร์ (`212 KB` / VRAM `2.21 MB`)**!
   - **งานออร์แกนิกจากรูป (Image-to-3D — มาสคอตตัวเต็ม, ฟิกเกอร์บนฐาน, เมฆ, โลโก้ 3D, ตู้ทรงสัตว์):** ทำตาม `references/image-to-3d.md` ผู้ใช้ไม่ใช้ Tripo และไม่มีบริการ image-to-3D ประจำ ค่าเริ่มต้นคือปั้นออร์แกนิกเองด้วย Antigravity + Blender MCP (ทรงรีหลายก้อน + voxel remesh + palette) ตามหัวข้อ "ปั้นออร์แกนิกเองด้วย Antigravity + Blender MCP" ในไฟล์นั้น ใช้บริการ image-to-3D ภายนอกเมื่อผู้ใช้สั่งเท่านั้น โดยเจน concept sheet ชิ้นเดียวพื้นขาว -> `.glb` -> `scripts/blender/import_ai_prop.py` (ย่อ tris + อบ atlas ใหม่ + origin + กล่องชน ให้ผ่านสัญญาเดียวกับสายอื่น) ชุดระดับสตูดิโอผสมสองสาย: ตัวถังจาก builder, มาสคอตและมงกุฎจากสายออร์แกนิก
3. **ปั้นรอบแรกและตรวจด้วยตาเทียบ Concept:** เปิดดู `<id>_preview.png` ทุกชิ้นเทียบข้างกับภาพ Concept Art และ "เกณฑ์ตรวจหน้าตา" ใน `references/style-toybrand.md` ห้ามปล่อยงานทรงกล่องแข็ง หน้าลูกกลมแปะ หูคลิป/กรอบเบี้ยว หรือชิ้นที่ถูก decimate จนบุบ
4. **แก้จนลงตัว:** ขัดสัดส่วน/แสง/ตำแหน่งดาว/หู/กันสาด/ขอบทุกชิ้นจนผ่านเกณฑ์ความน่ารักและไม่เกินงบ low-poly (`2,400-4,800` tris) โดยไม่ต้อง auto-decimate จากนั้นเรนเดอร์ `lineup.png` (`2400x1200`) รวมทุกชิ้น
5. **ลวดลายพิเศษ (ถ้ามี):** ใช้ `prepare_billie_art_v4()` / `ART_UV_V4` / `make_text_banner(..., width=1024, height=512)` / `v4_art_panel()` / `v4_art_medallion()` / `decal_disc()` / `decal_region()` / `billie_logo_badge()` ของ `kawaii_studio.py` (เจนป้ายฟอนต์ TitanOne + pop-art halftone ขอบสติกเกอร์เนียน 100% ภายใน Blender ด้วย NumPy โดยไม่ต้องลง PIL) หรือเจน PNG พื้นใสตาม `references/pipeline.md`
6. **ตรวจสัญญา:** รัน `scripts/blender/validate_prop.py` จนได้ `fail=0 warn=0` ทุกไฟล์
7. **Export:** รัน `scripts/blender/export_prop.py` (ไม่ใส่ `--factory-startup`) ด้วย `--format native --max-res 1024 --shared-ytd <ชื่อ>_tex` (หรือ `--max-res 512` สำหรับชุดที่เน้นลด VRAM) ได้ `.ydr` + `.ytyp` + `.ycd` + shared `.ytd` ไฟล์เดียวพร้อมตรวจ PyMateria FVF อัตโนมัติ (หมายเหตุ: PyMateria มีสัญญาอนุญาตกับ Take-Two/Rockstar ห้ามติดตั้งแทนผู้ใช้)
8. **เชื่อมเข้าเซิร์ฟเวอร์:** ทำตาม `references/integration.md` (stream, `data_file "DLC_ITYP_REQUEST"`, โค้ด spawn ที่ปล่อยหน่วยความจำ) สำรองไฟล์ก่อนแก้ resource จริงทุกครั้ง
9. **ซิงก์และรายงาน:** ถ้าแก้ไฟล์ใน skill ให้รัน `scripts/sync-antigravity.ps1 -Force` และตรวจด้วย `-Check` รายงานผู้ใช้แยกให้ชัดว่าอะไรตรวจแล้ว อะไรยังไม่ได้ลองในเกม

## Commands and options

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill   = '<project>\.claude\skills\infrontofx\prop-forge'
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --lineup
& $blender -b --factory-startup -P "$skill\scripts\blender\forge_prop.py" -- --spec work\source\props.json --out work\build --only 1nfx_goo_atm
& $blender -b --factory-startup -P "$skill\scripts\blender\validate_prop.py" -- --blend work\build
```

ตัวเลือกของ `forge_prop.py`: `--only id1,id2` สร้างเฉพาะชิ้น, `--lineup` เรนเดอร์ทุกชิ้นเรียงกัน, `--bake 512` (แนะนำสำหรับงานเกมจริง: เร็ว + ลื่น + ชัดไม่วุ้น ด้วย flood-fill 0% ขอบดำ) หรือ `--bake 1024`, เปิด `"low_poly": true` ในสเปกเพื่อลด tris ลง ~50% โดยยังคงผิวเงา smooth-shaded ไวนิล, `--no-render` ไม่เรนเดอร์, `--samples 24`, `--list` ดู archetype และ role ของสี ทั้งชุด 12 ชิ้นใช้เวลาราวครึ่งนาที

ตัวเลือกของ `export_prop.py`: `--format native` (ค่าเริ่ม), `--max-res 512` (ย่อและเข้ารหัส DDS ด้วย PCA DXT1 สำหรับ atlas ทึบ / DXT5 + RGB bleed + unsharp mip สำหรับ decal พื้นใส), `--shared-ytd <ชื่อ>` (เช่น `1nfx_ext_tex` รวมทุก texture แบบไม่ซ้ำลง `.ytd` ไฟล์เดียว ลด VRAM ~90% และตั้ง `hdTextureDist = lodDist` เพื่อไม่ให้เกมลดความละเอียดจนเบลอ)

## Tools

| ไฟล์ | หน้าที่ |
| --- | --- |
| `scripts/blender/forge_prop.py` | สร้าง prop จากสเปก JSON: **15 archetype** (`sign_post`, `parking`, `kiosk_sign`, `atm`, `safe`, `crate`, `chest`, `workbench`, `mascot_marker`, `airdrop`, `powerbox`, `redbox`, `waterpipe`, `gachapon`, `washmoney`) พร้อมโหมด `"style": "vinyl_toy"` และ `"style": "kawaii_billie"`, ริกกระดูก + animation (`"animate": true`), รวม mesh, ล้างเศษ, decal, กล่องชน, preview, lineup, `report.json` |
| `scripts/blender/kawaii_studio.py` | **V17 Dual-Threshold (`32°` Hard / `68°` Organic) Matte Vinyl + Anti-Playdough Studio Engine (`KawaiiBuilder`, `low_poly=True` default)** สำหรับปั้นคอลเลกชัน Pop-Mart / Billie School: แยกความเนียนของชิ้นส่วนออร์แกนิก (`organic_smooth=True`, `68°`) ออกจากขอบสถาปัตยกรรม (`32°`), ปรับค่าสเปกูลาร์แบบ Matte Collectible Vinyl (`spec_int=0.05–0.09`) กันอาการเงาเป็นวุ้นกลางแดด GTA V, รองรับ `kind="mochi_face"` (`9×8` โดมแก้มนูนแมป 1:1 กับ `billie_faces_v7.png`), Shared Master Palette `1024x1024` (Row 1 โทนอุ่น + Row 2 สี 4 บ้านและของจิ๋ว), รถ `plush_car()` V15, ริก `.ycd` และ `render_lineup` |
| `scripts/blender/billie_v7_assets.py` | **V17 Pure Quad-Flow 4-House Mascot, Seamless Cloud & 18 Crisp Mini-Prop Library**: ปั้นมาสคอต 4 บ้าน (`brown`, `pink`, `skyblue`, `grey`) × 3 ท่า (`full`, `head`, `peek`) จาก Quad Loft/Lathe แท้ (ปลอด Voxel-Decimate วุ้น 100%) + ก้อนเมฆ Cumulus ชิ้นเดียวไร้รอยต่อ (`add_sculpted_cloud_v7`) + ของจิ๋ว/เครื่องมือ/กิมมิก 3D คมชัด 18 ชิ้น (ขวดสี, กล่องน็อต, แท่นเทป, แก้วดินสอ, ค้อนหงอน, ประแจ, ไขควง, กล่องเครื่องมือ, ปากกาจับชิ้นงาน, ชานมไข่มุก, โดนัท, ถุงของขวัญ, แกลลอนน้ำยาซักผ้า, กรวยจราจร, ประแจคอม้า, หยดน้ำ, กองเหรียญและอัญมณี) |
| `scripts/blender/import_ai_prop.py` | แปลงโมเดลจาก AI (`.glb`/`.gltf`/`.fbx`/`.obj`) เป็น prop `.blend` ตามสัญญา: รวม mesh, ลบเศษลอย, ย่อขนาดเป็นเมตรและวางกลางพื้น, weld + decimate ตามงบ `--tris`, smart UV + อบสีและ AO ลง atlas เดียว (`--bake`), เติมพื้นที่ว่างกันขอบดำ, กล่องชนซ้อนตามความสูง (`--colliders`), metadata `prop_forge`, preview |
| `scripts/blender/validate_prop.py` | ตรวจ `.blend` ทีละไฟล์หรือทั้งโฟลเดอร์: ชื่อ, transform, origin ที่พื้น, ขนาด, tris เทียบงบ, NaN, สามเหลี่ยมเสีย, UV, วัสดุ, texture ยกกำลังสอง, กล่องชน, ริกกระดูก/vertex group/keyframes (เมื่อมี animation), orphan ใช้ได้ทั้ง headless และใน Blender สดผ่าน MCP |
| `scripts/blender/export_prop.py` | ใช้ Sollumz แปลง `.blend` เป็น Drawable (นิ่งหรือ Armature ริกกระดูก) + บังคับ `UVMap 0` และ `Color 1` สีขาว (255) + embedded collision + ytyp (ตั้ง `clipDictionary`, `flag10`/`flag20`/`flag30`, `textureDictionary` และ `hdTextureDist = lodDist` อัตโนมัติ) + `.ycd` ไบนารี (`--format native`) หรือ `.ycd.xml` (`cwxml`) + รวม shared `.ytd` ไฟล์เดียวด้วย `--shared-ytd <name>` และตรวจ PyMateria FVF อัตโนมัติหลัง export |
| `scripts/blender/dds_codec.py` | ตัวเข้ารหัส DDS แบบ vectorized PCA DXT1 (BC1, 4 bpp) / DXT5 (BC3, 8 bpp) พร้อม linear premultiplied-alpha mipmaps, RGB bleed กันขอบดำ และ unsharp mip ระดับ 1-3 เพื่อภาพคมไม่วุ้นและประหยัด VRAM สูงสุด |
| `scripts/blender/ycd_rsc7.py` | คอมไพเลอร์/ดีคอมไพเลอร์ `.ycd` ไบนารี (`RSC7 v46`) ล้วนด้วย Python สำหรับแปลง `.ycd.xml` ของ Sollumz เป็น `.ycd` พร้อมสตรีมใน FiveM โดยไม่ต้องใช้ CodeWalker GUI (มีตัวตรวจ round-trip ด้วย) |
| `scripts/blender/render_anim_preview.py` | เรนเดอร์พรีวิวแอนิเมชันจาก `.blend` ที่ริกแล้วเป็น GIF วนลูปและวิดีโอ H.264 MP4 รวมทุกช็อต (Lineup, Airdrop, Power Box ตู้ไฟ, Safe เปิด-ปิด, Marker หมุนเหนือ Stash, Loot Chest) |
| `scripts/sync-antigravity.ps1` | ซิงก์ skill ไป `.agents/skills/prop-forge` ให้ Antigravity ใช้ (`-Check` ตรวจอย่างเดียว, `-Force` เขียนทับ) |
| `templates/prop-spec.example.json` | สเปกชุดตัวอย่าง GOO LAB ครบ 9 ชิ้น |
| `assets/fonts/` | ฟอนต์ OFL (Titan One, Russo One) สำหรับตัวหนังสือบน prop |

ใช้แค่ Blender 4.2.3 (`<blender-4.2.3>\blender.exe`) ไม่ต้องลง add-on หรือ Python แยกตอนปั้นและตรวจ Sollumz ใช้เฉพาะตอน export

## Original reading table

| งาน | อ่าน |
| --- | --- |
| แนวศิลป์ สี สัดส่วน ลวดลาย กฎองค์ประกอบ เกณฑ์ตรวจหน้าตา โหมด V5 Vinyl Toy-Brand ถอดสไตล์ใหม่จากรูป/คลิป | `references/style-toybrand.md` |
| เจนรูปแล้วปั้นเป็น prop: MCP ที่ต้องใช้, พรอมต์ concept sheet, ตั้งค่า image-to-3D, `import_ai_prop.py`, งบ tris/atlas, แยกชิ้นขยับ | `references/image-to-3d.md` |
| บทถอดชุด prop ธีมแบรนด์ระดับสตูดิโอ 8 ชุด (2026-11-22): รายการชิ้นมาตรฐาน, ภาษาทรง 5 แนว, สูตรองค์ประกอบรายชิ้น, แอนิเมชัน, เช็กลิสต์ก่อนส่ง | `references/showcase-study.md` |
| archetype ทั้ง 11 แบบ ขนาด พารามิเตอร์ งบ tris สคีมาสเปก และวิธีเพิ่ม archetype ใหม่ | `references/archetypes.md` |
| สัญญาพิกัด, palette กับ bake, decal จาก AI, collision, LOD, export ด้วย Sollumz, ytyp | `references/pipeline.md` |
| ปั้นผ่าน Antigravity + Blender MCP, ไฟล์ .blend 4.2 กับ 5.3, ทำงานร่วมกับ agent อื่น | `references/antigravity.md` |
| fxmanifest, ชื่อไฟล์ stream, โค้ด spawn, marker หมุน/ลอย, QA ในเกม | `references/integration.md` |
| ภาพเป้าหมายของชุดตัวอย่าง | `references/targets/` |
| ต้องการผิวเนียนแบบ designer toy: ทรงพอง ผสานชิ้นแบบมี fillet ตัวอักษร/ป้ายพอง หยดสไลม์ ของออร์แกนิก (builder ในโฟลเดอร์นี้ได้ทรงกล่องเหลี่ยม bevel บาง) | skill `sculpt-forge` ของ infrontofx (ไฟล์ `sculpt-forge/SKILL.md` ในโฟลเดอร์แม่) ผลลัพธ์ผ่าน `scripts/blender/validate_prop.py` และ export ด้วย `scripts/blender/export_prop.py` ของโฟลเดอร์นี้ได้ทันที |

## Original hard rules

**ต้นฉบับ.** คลิปอ้างอิงเป็นของเซิร์ฟเวอร์หรือผู้สร้างอื่น ใช้ได้แค่ทิศทางสไตล์ ห้ามป้อนเฟรมจากคลิป รูปของเล่นจริง หรือตัวละครมีลิขสิทธิ์เข้า image-to-3D ห้ามใช้ชื่อแบรนด์ โลโก้ มาสคอต หรือ texture ของเขา ทุกชุดต้องมีชื่อแบรนด์ของเราเองในสเปก ห้ามใส่เครื่องหมายการค้าจริงลงบน prop

**สัญญาพิกัด.** mesh เดียวชื่อเดียวกับไฟล์ (`[a-z0-9_]`), transform apply แล้ว, จุดต่ำสุดอยู่ที่ z = 0 กลาง X/Y, ด้านหน้าหัน -Y, หน่วยเมตร, กล่องชนชื่อ `<id>_col_N` (marker ไม่มีชน) ห้ามแก้ชื่อหรือ origin หลังจากเชื่อมเข้าเซิร์ฟเวอร์แล้ว

**งบ.** tris ไม่เกินงบใน `references/archetypes.md`, วัสดุไม่เกิน 4 (diffuse, emissive, decal), texture ยกกำลังสองไม่เกิน 2048 ทั้งชุดใช้ palette ร่วมกันไฟล์เดียว รายละเอียดที่เล็กกว่า 2 ซม. ให้ใส่เป็น decal ไม่ใช่ geometry

**ไฟล์ระบบ.** ห้ามแตะ resource ที่มี `.fxap` การแก้ `fxmanifest.lua`, config ของ resource อื่น และการรีสตาร์ตเซิร์ฟเวอร์ ต้องสำรองไฟล์ก่อนและให้ผู้ใช้ยืนยัน

**ทำงานร่วมกัน.** Antigravity, Codex และ Claude Code แก้โฟลเดอร์นี้ได้พร้อมกัน ต้นฉบับอยู่ที่ `.claude/skills/infrontofx/prop-forge` ห้ามแก้สำเนาใน `.agents/skills/prop-forge` โดยตรง หนึ่งชุด prop หนึ่ง agent และห้ามสอง agent ยิงคำสั่งเข้า Blender สดตัวเดียวกันพร้อมกัน

**รายงานตามจริง.** `RESULT fail=0` แปลว่าโครงไฟล์ `.blend` ผ่านสัญญา ภาพ preview เป็นการเรนเดอร์ Eevee ไม่ใช่ภาพในเกม จนกว่าผู้ใช้จะ export และเห็นในเกมเอง ให้บอกว่ายังไม่ได้ทดสอบในเกม เมื่อผู้ใช้รายงานผลในเกม ให้บันทึกลง "สิ่งที่พิสูจน์แล้ว" ใน `references/integration.md`

## Original code style

Lua ที่เขียนเพิ่ม (spawn, interaction) ให้ทำตาม `infrontofx` ใน `SKILL.md` ระดับบนของแพ็กนี้: OOP module table, ไม่มี comment, ไม่มี `local function` ระดับไฟล์, 4 ช่องว่าง, double quotes, trailing comma, ใช้ `lib.spawn.pointProp` ของ `1nfx_lib`
