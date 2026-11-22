---
name: map-forge
description: ออกแบบ ปั้น วางผัง ตรวจ และ export แมพ FiveM ประสิทธิภาพสูง (144-200 FPS) สไตล์สตูดิโอระดับโปรดักชัน เช่น Sky AFK Zone, Spawn/Select Lobby, Airdrop/Warzone Arena, Garage/Town Hub, Rebel/Outpost และอาคาร/MLO ด้วย Blender 4.2.3 + Blender 5.3 MCP + Sollumz 2.9 + PyMateria GEN8 (`.ydr`, `.ytd`, `.ytyp`, `.ymap`, `.ybn`, `_manifest.ymf`) พร้อมมาตรฐาน RAGE PBR shader (`normal_spec.sps`, `glass_env.sps`, `water_fountain.sps`, `emissive*.sps`), RAGE Vertex Color (`#FF00FF` แยกแสงกลางวัน/กลางคืน), ฝังไฟ `Drawable.lights`, และคลัง prop แท้ของ GTA V (ต้นไม้ พุ่มดอกไม้ ไฟถนน ม้านั่ง รั้ว) เพื่อคุม VRAM ต่ำสุดและสมจริงที่สุด ใช้เมื่อผู้ใช้ขอปั้นแมพ, ทำแมพ FiveM, ทำโซน AFK บนฟ้า, ทำ Lobby, ทำ Airdrop/Warzone, ทำ Garage/โรงพยาบาล/เมือง, วาง YMAP/YBN/YTYP, แก้แมพตกพื้น/สว่างเกินตอนกลางคืน/กระตุก, หรือวิเคราะห์โครงสร้างแมพ (FiveM map, custom map, YMAP, YTYP, YBN, YDR, YTD, MLO, Sollumz, PyMateria, RAGE vertex color, Blender MCP)
---

# Map Forge

สร้างแมพ FiveM คุณภาพระดับสตูดิโอที่ **สมจริง คมชัด ลื่นระดับ 144-200 FPS และคุมขนาดไฟล์/VRAM ต่ำสุด** โดยใช้หลัก **Clean Hero Architecture Shell + World-Scale Tiled PBR + RAGE Day/Night Vertex Color + Embedded Lights + Native GTA V Prop Dressing**

มาตรฐานและตัวเลขงบทั้งหมดใน skill นี้ถอดบทเรียนเชิงวิศวกรรมจากการวิเคราะห์ binary ของแมพโปรดักชัน 12 ชุด ครอบคลุม 6 ประเภท (Sky AFK, Spawn Lobby, Airdrop/Warzone, Garage/Hub, Rebel/Outpost, Hospital/MLO) ไม่มี mesh, texture หรือโลโก้ของแมพอื่นอยู่ใน skill นี้

## กฎทองของแมพระดับสตูดิโอ (สรุป 6 ข้อที่เปลี่ยนจากงานดู "กาก/การ์ตูน" เป็นงานโปร)

1. **แยกหน้าที่ชัดเจน (Hero Shell 5-15% + Native GTA V Props 85-95%):** ปั้น `.ydr` เองเฉพาะโครงสร้างสถาปัตยกรรมหลัก (พื้นลาน ขอบทาง บันได ศาลา หลังคา ซุ้ม ป้ายแบรนด์ น้ำพุ) ส่วนต้นไม้ พุ่มไม้ ดอกไม้ โคมไฟถนน ม้านั่ง ถังขยะ เสาจราจร รั้ว ให้ใช้ **prop แท้ของ GTA V** วางใน `.ymap` (ได้ใบไม้สมจริง, ลมพัด, ไฟถนนเปิดอัตโนมัติตอนกลางคืน และ **กิน VRAM เพิ่ม 0 MB**)
2. **ห้ามใช้ Smart-UV Single Atlas กับลานกว้าง:** ลาน 60-120 เมตรที่ยัดลง atlas เดียวจะได้ความละเอียดแค่ ~10 px/m (ดูเป็นพลาสติกเบลอ/วุ้น) ให้ใช้ **World-Scale Tiled PBR** (`1 UV = 1.5–4.0 เมตร`) คู่ `normal_spec.sps` (Diffuse + DirectX `-Y` Normal + Specular) เพื่อความคมระดับ 250-500 px/m
3. **เทคนิค micro-swatch + Shared YTD คุม VRAM 0.6–5 MB:** สีเรียบ/ขอบเหล็ก/trim ใช้ swatch เล็ก `4x4`–`32x32` px, พื้นผิว tile ใช้ `256x256` หรือ `512x512` (สูงสุด `1024x1024` เฉพาะโลโก้หลักหรือพื้นฮีโร่), เข้ารหัส **PCA DXT1 (4 bpp)** สำหรับผิวทึบและ **DXT5 (8 bpp)** เฉพาะแผ่น alpha/decal รวมลง `.ytd` เดียว
4. **RAGE Vertex Color (`Color 1`) แยกแสงกลางวัน/กลางคืน (`#FF00FF`):** ใน GTA V ช่อง `R` = แสงฟ้ากลางวัน (Natural Ambient + AO), `G` = แสงไฟประดิษฐ์กลางคืน (Artificial Ambient), `B` = Indirect/General AO — ผนัง/พื้นกลางแจ้ง **ต้องตั้ง `G = 0`** (ค่าฐาน `(255, 0, 255, 255)` แล้วคูณ Cycles AO ลง `R` กับ `B`) เพื่อให้กลางวันมีมิติเงาซอกและกลางคืนมืดสมจริงไม่เรืองแสงเป็นพลาสติก
5. **แสงจริงตอนกลางคืน:** ฝังไฟ `Drawable.lights` (`POINT` อบอุ่น / `SPOT` ยิงป้าย / 12-tri invisible emitter) พร้อม `time_flags = NIGHT` คู่กับเสาไฟ GTA V (`prop_streetlight_11c`, `prop_wall_light_15a`, `prop_ind_light_03c`)
6. **กันตกพื้น 100% สำหรับ Sky Map:** ทำ Dual Collision ทั้ง embedded `BoundGeometryBVH` ใน `.ydr` และ **Static World `.ybn`** พิกัดโลกจริง ผูกใน `.ymap` ด้วย `content_flags = 65` (`HAS_ENTITIES_HD | HAS_PHYSICS`) และ `physics_dictionaries = [ybn_name]`

## ขั้นตอนการทำงาน

1. **รับโจทย์และเลือก Archetype:** ระบุประเภทแมพ (Sky AFK / Spawn Lobby / Airdrop-Warzone / Garage-Hub / Rebel-Outpost / City-MLO), แบรนด์และโทนสี (เช่น `billie-ui` หรือ `1nfx-ui`), พิกัดโลก `(x, y, z)`, จุดวาร์ป/ขอบเขตโซน และงบเป้าหมายจาก `references/studio-benchmarks.md`
2. **ออกแบบภาพคอนเซปต์ (ก่อนปั้นทุกครั้งเมื่อเป็นแมพใหม่):** เจนภาพ 2 มุม (Overview 3/4 + Player Eye-Level POV) ให้ผู้ใช้ตรวจและอนุมัติโทน/ผังก่อนเริ่มปั้น 3D
3. **วางสเปกผังแมพ (`map-spec.json`):** คัดลอก `templates/map-spec.example.json` ไปไว้ `work/<map>/source/map-spec.json` กำหนดพิกัด `anchor`, รายการชิ้นสถาปัตยกรรม (modular หรือ hero shell), ตำแหน่ง prop GTA V จาก `references/gta-prop-catalog.md`, ตำแหน่งไฟ `Drawable.lights`, และ `vanilla_ytyps`
4. **ปั้นสถาปัตยกรรมและเตรียม PBR + RAGE Vertex Color:**
   - ปั้นด้วย Blender 4.2.3 CLI (บันทึกเป็น `BLENDER-v402` เพื่อให้เปิดได้ทั้ง 4.2.3 และ 5.3)
   - สร้างทรงสถาปัตยกรรมจริง (เสา คาน บัวพื้น โครงถัก หลังคา กันสาด บันได รั้ว ขอบกระบะต้นไม้) ไม่ใช่กล่องเปล่าหรือก้อนการ์ตูน
   - วาง World-Scale Tiled UV (`"UVMap 0"`), ตั้ง material shader + พารามิเตอร์ตาม `references/shaders-lighting-vcol.md`, อบ Cycles AO ลง `"Color 1"` โดยคง `G = 0` สำหรับผิวนอกอาคาร (หรือไล่ `G` เฉพาะใต้โคมไฟ/ในร่ม)
   - สร้างกล่องชนแยก `<id>_col_0` ที่พอดีระดับพื้นจริง (tolerance `< 0.02m` ที่จุดวาร์ป)
5. **ตรวจหน้าตา 6 มุม (Visual QA):** เรนเดอร์ด้วย Blender 4.2.3 หรือเปิดตรวจแบบสดด้วย Steam Blender 5.3 MCP ตาม `references/antigravity.md` อย่างน้อย 6 มุม: Overview 3/4, Top-Down Layout, Player POV ที่จุดวาร์ป, Hero Structure Close-up, Seating/Walkway Detail, และ Underside/Edge Check — เปิดดูภาพจริงทุกใบก่อนผ่าน
6. **Export เป็นไฟล์เกม GEN8 ไบนารี:** รัน `scripts/blender/export_map.py` (ไม่ใส่ `--factory-startup` เพื่อให้ Sollumz + PyMateria โหลด) ได้ `.ydr`, shared `.ytd`, static world `.ybn`, `.ytyp`, `.ymap`, `_manifest.ymf` และโฟลเดอร์ resource พร้อม `fxmanifest.lua`
7. **ตรวจ binary ครบวงจร:** รัน `scripts/blender/inspect_map.py` บนโฟลเดอร์ `stream/` จนผ่าน `MAP_INSPECT_PASS fail=0` ตรวจครบ: RSC7 header, FVF (`TEXTURE0`/`TANGENT0`/`DIFFUSE` ช่อง R/G/B), YTD VRAM & mipmaps, YBN floor Z & CollisionFlags, YMAP `content_flags`/quaternions/extents, `_manifest.ymf`
8. **ส่งมอบและ QA ในเกม:** วาง resource (ห้ามแตะ/ลบ resource ที่มี `.fxap` เองโดยไม่ให้ผู้ใช้ยืนยัน), สำรอง config ก่อนแก้, รายงานผลแยกชัดเจนระหว่างสิ่งที่ตรวจแล้วใน Blender/PyMateria กับสิ่งที่รอผู้ใช้เทสในเซิร์ฟเวอร์จริง

## คำสั่ง

```powershell
$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
$skill   = '<project>\.claude\skills\infrontofx\map-forge'

# 1. Export แมพทั้งชุดจาก map-spec.json + โฟลเดอร์ build/props/*.blend + build/textures/*.png
& $blender -b -P "$skill\scripts\blender\export_map.py" -- --spec work\my_map\source\map-spec.json --props work\my_map\build\props --textures work\my_map\build\textures --out work\my_map\my_map_pkg

# 2. ตรวจและวิเคราะห์ binary แมพใดก็ได้ (ทั้งแมพที่ปั้นเองหรือแมพในโปรเจกต์)
& $blender -b -P "$skill\scripts\blender\inspect_map.py" -- --dir work\my_map\my_map_pkg\stream --spec work\my_map\source\map-spec.json

# 3. ตรวจเฉพาะโฟลเดอร์ stream (ไม่ต้องมี spec ก็ตรวจงบ VRAM/tris/vcol/lights/YBN/YMAP ได้)
& $blender -b -P "$skill\scripts\blender\inspect_map.py" -- --dir work\my_map\my_map_pkg\stream --json work\my_map\build\inspect_report.json

# 4. ซิงก์ skill ไป .agents\skills\map-forge เมื่อมีการแก้ไข
& "$skill\scripts\sync-antigravity.ps1"
```

## เลือกอ่าน (อ่านเฉพาะไฟล์ที่เกี่ยวข้องกับงาน)

| งาน | อ่าน |
| --- | --- |
| งบ tris, VRAM, disk, โครงสร้าง 6 ประเภทแมพ, Single-Shell vs Modular vs MLO, จุดที่ทำให้แมพดูแพง vs ดูถูก | `references/studio-benchmarks.md` |
| สูตร RAGE Shaders (15 shader หลัก + ค่าพารามิเตอร์จริง), RAGE Vertex Color (`#FF00FF`), DirectX `-Y` Normal, ไฟฝัง `Drawable.lights` และ 12-tri light emitter | `references/shaders-lighting-vcol.md` |
| คลัง prop แท้ GTA V ที่ผ่านการใช้งานจริง (ต้นไม้ พุ่มดอกไม้ ไฟถนน ม้านั่ง รั้ว หิน เฟอร์นิเจอร์), ระยะฝังพื้น Z, `_manifest.ymf` และข้อควรระวัง `h4_*` Cayo DLC | `references/gta-prop-catalog.md` |
| ไปป์ไลน์ Export/Collision/YMAP/YTYP/YBN/YMF/MLO, Quaternion กลับด้านของ GTA V, Shared YTD DXT1/DXT5, การติดตั้ง FiveM และ QA | `references/pipeline.md` |
| การใช้ Antigravity + Blender MCP (4.2.3 vs 5.3 `BLENDER17`), กฎ `-LiteralPath`, เช็กลิสต์ตรวจภาพ 6 มุม | `references/antigravity.md` |

## เครื่องมือ

| ไฟล์ | หน้าที่ |
| --- | --- |
| `scripts/blender/export_map.py` | ส่งออกแมพ FiveM GEN8 อัตโนมัติจาก `map-spec.json` + `.blend` + `.png`: เข้ารหัส Shared `.ytd` (PCA DXT1/DXT5 + กลับช่อง G ของ Normal เป็น DirectX `-Y`), แปลง PBR เป็น Sollumz shader (`normal_spec.sps`/`default.sps`/`emissive.sps`/`emissivenight.sps`/`glass_env.sps`/`cutout.sps`/`water_fountain.sps`), ฝัง `Drawable.lights`, ฝัง collision + สร้าง Static World `.ybn`, สร้าง `.ytyp`, `.ymap` (ผสม custom + vanilla GTA V props), `_manifest.ymf` และ `fxmanifest.lua` |
| `scripts/blender/inspect_map.py` | เครื่องมือตรวจและวิเคราะห์ binary แมพ FiveM ด้วย PyMateria: เช็ก RSC7, นับ tris/geoms/FVF/`TANGENT0`/`DIFFUSE` (เตือนทันทีถ้าแมพกลางแจ้งมี `G > 40` หรือ tris ทะลุงบ), เช็ก VRAM/mips/format ของ `.ytd`, ตรวจระดับพื้น Z และ `CollisionFlags` ของ `.ybn`, ตรวจ `content_flags`/quaternion/streaming extents ของ `.ymap`, ตรวจ `_manifest.ymf` และสรุปผล `MAP_INSPECT_PASS fail=0` |
| `scripts/blender/dds_codec.py` | ตัวเข้ารหัส DDS แบบ vectorized PCA DXT1 (BC1, 4 bpp) / DXT5 (BC3, 8 bpp) พร้อม linear mipmaps, RGB bleed กันขอบดำ และ unsharp mip |
| `scripts/sync-antigravity.ps1` | ซิงก์ skill จาก `.claude/skills/infrontofx/map-forge` ไป `.agents/skills/map-forge` (`-Check`, `-Force`) |
| `templates/map-spec.example.json` | เทมเพลตสเปกผังแมพ (Sky Plaza + Vanilla Props + Embedded Lights) |
| `templates/fxmanifest.lua` | เทมเพลต `fxmanifest.lua` มาตรฐาน `this_is_a_map "yes"` + `DLC_ITYP_REQUEST` |

## กฎที่ห้ามข้าม

- **ต้นฉบับ 100%:** ห้ามคัดลอก mesh, texture, `.ydr`, `.ytd`, โลโก้ หรือเลย์เอาต์ตรงๆ จากแมพของสตูดิโออื่นเด็ดขาด ใช้ได้เฉพาะหลักวิศวกรรมและสัดส่วนมาตรฐาน
- **ห้ามแตะ `.fxap`:** ห้ามแก้ไข ลบ หรือพยายามแกะ resource ใดที่มี `.fxap` โดยเด็ดขาด หากต้องเปลี่ยนแมพในจุดที่มี resource `.fxap` อยู่เดิม ให้แจ้งผู้ใช้ย้าย/ปิดใน `server.cfg` เอง
- **แยกงานซิงก์ให้ถูกที่:** ต้นฉบับของ skill นี้อยู่ที่ `.claude/skills/infrontofx/map-forge` เท่านั้น ห้ามแก้สำเนาใน `.agents/skills/map-forge` โดยตรง แก้เสร็จต้องรัน `scripts/sync-antigravity.ps1`
- **รายงานตามจริง:** `MAP_INSPECT_PASS fail=0` และภาพเรนเดอร์ Blender EEVEE ยืนยันโครงสร้างไฟล์และหน้าตาเบื้องต้น แต่ **ไม่ใช่** การทดสอบในเซิร์ฟเวอร์ FiveM จริง ต้องแจ้งผู้ใช้เสมอว่ายังไม่ได้ลองเดินในเกมจริงจนกว่าผู้ใช้จะเทสและยืนยัน
- **กฎ Lua (ถ้ามีสคริปต์เสริม เช่น จุดวาร์ป/โซน AFK):** เขียนตาม `../SKILL.md` ของ `infrontofx` เท่านั้น (OOP module table, ไม่มี comment, ไม่มี `local function` ระดับไฟล์, 4 spaces, double quotes, trailing comma)
