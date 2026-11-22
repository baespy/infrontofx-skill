# Pipeline

## สัญญาพิกัด

| ข้อ | ค่า |
| --- | --- |
| หน่วย | เมตร, Z ขึ้น |
| origin | กลาง X/Y ของ prop, จุดต่ำสุดที่ z = 0 (marker ก็วางที่ z = 0 แล้วให้ Lua ยกขึ้น) |
| ด้านหน้า | หัน -Y ใน Blender ถ้าในเกมหันกลับด้าน ให้บวก heading 180 ในโค้ด spawn ห้ามหมุน mesh หลังเชื่อมระบบแล้ว |
| object | mesh เดียวชื่อเดียวกับไฟล์ ไม่มี parent, transform apply แล้ว |
| กล่องชน | object แยก `<id>_col_N` ใน collection `<id>_collision` แสดงแบบ wire ไม่ render |
| metadata | custom property `prop_forge` บน mesh เก็บ JSON (archetype, ขนาด, tris, งบ, shader, lodDist) |

## Finish: palette หรือ bake

**Palette (เร็ว / เทสต์ทรง).** ทุกหน้าถูก map ไปกลางช่องสีของ texture 256x256 (ช่องละ 32 px, 64 ช่อง) ชื่อ `<set>_palette` ทั้งชุดใช้ไฟล์เดียวกัน สีคมไม่เบลอ ใช้หน่วยความจำน้อยมาก เหมาะสำหรับเทสต์ทรงรอบแรก (`--no-render` หรือเรนเดอร์เร็ว) วัสดุที่ได้: `<id>_diffuse` (`default.sps` หรือ `default_spec.sps` เมื่อตั้ง `"glossy": true`) และ `<id>_emissive` (`emissive.sps`)

**Bake + Cycles AO + Flood-Fill กันขอบดำ (`--bake 512` แนะนำสำหรับงานเกม FiveM ลื่นและคมไม่วุ้น; `--bake 1024` สำหรับงานโชว์ใกล้พิเศษ).** smart UV project (`island_margin=0.012`, `margin=16`) แล้วอบทั้งสี diffuse และ **Cycles Ambient Occlusion (`distance=0.28m`)** ผสมลง `<id>_atlas.png` ตามด้วย **Vectorized Flood-Fill Dilation เต็มพื้นที่ 100%** (ไม่มีช่องว่างสีดำ `#000000` ระหว่าง UV islands เหลือเลย เพื่อป้องกันดำซึม/ภาพวุ้นเวลามองไกลตอน GPU อ่าน mipmap ระดับล่าง) (สำคัญ: ก่อนอบ `DIFFUSE` ต้องตั้ง `Metallic = 0.0` ชั่วคราวทุกวัสดุ ไม่อย่างนั้นวัสดุ `gold` และ `metal` จะอบออกมาเป็นสีน้ำตาล/เทาดำมืด; และเก็บหน้า emissive ให้สว่างเต็ม 100% ไม่มืดตาม AO) เมื่อเปิด `"glossy": true` สคริปต์จะใช้ shader **`default_spec.sps`** (พร้อมตั้ง `specularIntensityMult=0.48`, `specularFalloffMult=48.0`, `specularFresnel=0.88` ใน `export_prop.py`)

**Low-Poly Mode (`"low_poly": true`) & Sharp PCA DDS Codec (`dds_codec.py`).** เปิด `"low_poly": true` ใน `props.json` เพื่อลดจำนวนสามเหลี่ยมลง ~50% (ลด bevel segment เป็น 1, ตัด micro-bevel ของชิ้น <3.2 ซม., ลด metaball target tris, ตั้ง crease angle 50° ให้ผิวไวนิลยังโค้งเนียน) ตอน export สคริปต์ `dds_codec.py` จะเข้ารหัสด้วย **PCA principal-axis + exact RGB565 Euclidean argmin**: atlas ทึบใช้ **`DXT1` (4 bpp)** ประหยัด VRAM ครึ่งหนึ่งเมื่อเทียบกับ DXT5 (PSNR ~32.5 dB, ล็อก solid block ไม่ให้เกิด carry overflow) ส่วน decal พื้นใสใช้ **`DXT5` (8 bpp)** + RGB bleed รอบขอบใส + linear premultiplied-alpha mipmaps + unsharp preservation `0.20` บน mip 1-3 เพื่อไม่ให้ตัวหนังสือและโลโก้เบลอ ("วุ้น") ในระยะกลาง

**Shared `.ytd` ทั้งชุด (`--shared-ytd <ชื่อ>` เช่น `1nfx_ext_tex`).** ใส่ `--max-res 512 --shared-ytd <name>` ตอนรัน `export_prop.py --format native` เพื่อปิดการฝัง texture ซ้ำใน `.ydr` (`embedded = False`), รวม texture ไม่ซ้ำทั้งหมด (เช่น 12 atlas + 2 โลโก้ = 14 รายการ) ลงไฟล์ `<name>.ytd` ไบนารี (`RSC7`) ไฟล์เดียวผ่าน `pmg8.TextureDictionary.export_rsc`, และตั้ง `texture_dictionary = <name>` พร้อม **`hd_texture_dist = lod_dist`** (`80-120 ม.`) ในทุก `.ytyp` เพื่อไม่ให้เกมลดระดับ mipmap จนภาพวุ้นเร็วเกินไป ลด VRAM ลงได้ถึง ~90% และลดขนาดดาวน์โหลดรวม ~65%

## Decal จาก AI

ลายที่ปั้นเป็นเรขาคณิตไม่ได้ (โลโก้กราฟฟิตี้, สติกเกอร์มาสคอตลายเส้น, หน้าจอ ATM) ให้เจนเป็นภาพแล้วแปะเป็นแผ่น decal:

1. เจนภาพด้วยสคริปต์ของ `poster-forge` (`../poster-forge/scripts/agy-gen.ps1` ผ่าน Antigravity หรือ `../poster-forge/scripts/codex-gen.ps1` ผ่าน Codex) สั่งให้วาดบนพื้นเขียว `#00FF00` เรียบ ๆ ขอบชัด ไม่มีเงาตกพื้น
2. ตัดพื้นด้วย `../poster-forge/scripts/cutout.ps1` ให้ได้ PNG พื้นใส ย่อเป็นยกกำลังสอง (256 หรือ 512)
3. ใส่ใน `decals` ของสเปก แล้วรันใหม่ แต่ละ decal กลายเป็นวัสดุ `<id>_decal_N` (`decal.sps` หรือ `cutout.sps` ตอน export)

พรอมต์ตั้งต้น (แก้ชื่อแบรนด์และสี):

```text
Flat vector sticker logo for a toy brand called "GOO LAB": bubbly rounded letters in acid lime #C9F31D with a thick dark #221E28 outline, a round purple #8E2DE2 mascot head with X eyes and a tiny gold crown, slime drips under the letters, small 4-point sparkles. Centered, no text other than GOO LAB, no shadow, no gradient background, solid pure green #00FF00 background, crisp edges, 1:1.
```

ห้ามสั่งให้ AI เลียนโลโก้หรือมาสคอตของคนอื่น และอย่าใส่รูปจากคลิปอ้างอิงเป็น `-Ref` ตอนเจนโลโก้

## Collision

- กล่องชนสร้างจากชิ้นที่ใส่ `collide=True` เป็นกล่องตามขอบเขตโลก (axis aligned) พอสำหรับ prop ตั้งพื้นทั่วไป
- ชิ้นที่ผู้เล่นต้องยืนชิด (ตู้ ATM, ตู้เซฟ, โต๊ะ) ต้องมีกล่องชนครอบตัวหลัก ไม่อย่างนั้นผู้เล่นจะเดินทะลุและ `PlaceObjectOnGroundProperly` จะวางผิด
- marker ไม่มีชน ตั้ง `SetEntityCollision(entity, false, false)` ในโค้ดด้วย

## LOD

- `lod_dist` ใน `report.json` (80 สำหรับชิ้นเล็ก 120 สำหรับป้ายและโต๊ะ) ใช้ใส่ `lodDist` ของ archetype ใน ytyp
- ชิ้นที่วางซ้ำหลายจุดทั่วแมป (ป้าย Garage, ATM) ควรมี LOD กลาง: duplicate mesh, ใส่ Decimate (Collapse 0.4) แล้วใช้เป็น Med LOD ใน Sollumz ถ้าเกมกระตุกตอนเข้าใกล้จุดที่มี prop เยอะ ให้ลด `lodDist` ก่อนลด geometry

## Export (Sollumz)

`scripts/blender/export_prop.py` ทำงาน Sollumz ทั้งหมดให้อัตโนมัติจาก `.blend` ของ `forge_prop.py`:

1. แปลง texture ของวัสดุเป็น `.dds` ด้วย `scripts/blender/dds_codec.py` (PCA DXT1 4 bpp สำหรับ atlas ทึบ / DXT5 8 bpp + RGB bleed + linear premultiplied-alpha mipmaps + unsharp mip 1-3 สำหรับ decal พื้นใส, จำกัดขนาดด้วย `--max-res 512`) และ re-encode ใหม่ทุกครั้งจาก `.png`
2. แปลงวัสดุเป็น Sollumz shader ตาม `prop_forge_shader` (`default.sps`, `default_spec.sps`, `emissive.sps`, `decal.sps`, `emissive_alpha.sps`) ตั้ง `emissiveMultiplier = 1.6` สำหรับวัสดุเรืองแสง และเมื่อใส่ `--shared-ytd <name>` จะตั้ง `embedded = False` แล้วรวมทุก texture ไม่ซ้ำลง `<name>.ytd` ไฟล์เดียว
3. **บังคับเตรียม `UVMap 0` + `Color 1` สีขาว `(255, 255, 255, 255)` (`prepare_mesh_attributes`):** Sollumz 2.9 (`vertex_buffer_builder.py`) จะอ่านเฉพาะ UV ที่ชื่อ `"UVMap 0"` และ Vertex Color ที่ชื่อ `"Color 1"` (`BYTE_COLOR`, `CORNER`) ถ้าปล่อยเป็น `"UVMap"` เดิมของ Blender หรือไม่มี `"Color 1"` ไฟล์ `.ydr` จะไม่มี `TEXTURE0` และ `DIFFUSE` ทำให้ prop ในเกม GTA V ดำสนิททุกชิ้น หลัง export แบบ `--format native` สคริปต์จะใช้ PyMateria ตรวจซ้ำทันที (`verify_native_ydr`) ว่าทุก geometry มี `TEXTURE0` + `DIFFUSE = 255` + embedded หรือ shared texture ref ครบ
4. รวม `<id>_col_N` เป็น Bound Composite (GeometryBVH) วัสดุชนเป็น `PLASTIC` (เปลี่ยนด้วย `--collision`) แล้ว parent เข้า Drawable เป็น embedded collision
5. แปลง mesh เป็น Drawable ชื่อ `<id>` สร้าง ytyp `<id>` ที่มี archetype `<id>` (`lodDist` จาก `report.json`, `hdTextureDist = lodDist` เมื่อใช้ `--shared-ytd` เพื่อไม่ให้เกมลดความละเอียดจนเบลอ, `textureDictionary = <shared_ytd>` หรือ `<id>`)
6. Export ด้วย `sollumz.export_assets` (GEN8 สำหรับ FiveM) ทีละชิ้นใน process แยก แล้วสร้าง `<shared_ytd>.ytd` ด้วย `pmg8.TextureDictionary.export_rsc` (ถ้าเปิด `--shared-ytd`)

```powershell
& 'C:\Tools\blender-4.2.3-windows-x64\blender.exe' -b -P "$skill\scripts\blender\export_prop.py" -- --blend work\build --out work\stream --format native --max-res 512 --shared-ytd 1nfx_ext_tex
```

ต้องรัน **ไม่ใส่** `--factory-startup` ไม่อย่างนั้น Sollumz ไม่โหลด ผลลัพธ์ต่อชิ้น: `<id>.ydr` + `<id>.ytyp` (native) หรือ `<id>.ydr.xml` + `<id>.ytyp.xml` + โฟลเดอร์ `<id>\` ที่มี `.dds` (cwxml) บรรทัด `EXPORT {...}` บอกวัสดุ จำนวนกล่องชน และไฟล์ที่เขียน จบด้วย `RESULT ok=<n> fail=<n>`

| `--format` | ต้องมี | ได้ |
| --- | --- | --- |
| `native` (ค่าเริ่ม) | Sollumz + szio + PyMateria (ส่วนเสริมของ Cfx.re มีสัญญาอนุญาตกับ Take-Two/Rockstar ผู้ใช้ต้องยอมรับเอง ห้าม agent ติดตั้งแทน) | `.ydr` `.ytyp` ไบนารีพร้อม stream |
| `cwxml` | Sollumz + szio | XML ที่ต้องนำเข้า CodeWalker เพื่อแปลงเป็นไบนารีก่อน stream (FiveM โหลด `.xml` ไม่ได้) |

สถานะเครื่องนี้ (2026-11-19): Sollumz 2.9.1 + szio 1.4.0 + PyMateria 0.2.1 ติดตั้งแล้วทั้ง Blender 4.2.3 และ Steam 5.3 (ผู้ใช้ยอมรับสัญญา PyMateria เองแล้ว) ใช้ `--format native` ได้เลย ยังไม่มี CodeWalker

ข้อควรรู้:

- Blender 4.2.3 แครชตอนปิดโปรแกรมหลัง export (`EXCEPTION_ACCESS_VIOLATION` ใน `node_free_node`) ไฟล์เขียนเสร็จแล้วก่อนแครช สคริปต์จึงพิมพ์ผลแบบ flush แล้วออกด้วย `os._exit` และแยก process ต่อชิ้น ห้ามเอาสองอย่างนี้ออก
- ytyp เป็นหนึ่งไฟล์ต่อหนึ่ง prop (`<id>.ytyp`) แบบเดียวกับ `1nfx_prop` ที่มีอยู่ ต้องเพิ่ม `data_file "DLC_ITYP_REQUEST"` ทีละไฟล์
- texture แนะนำใช้ `--max-res 512 --shared-ytd <ชื่อ>` เพื่อรวมทุก texture ไม่ซ้ำลง `.ytd` ไฟล์เดียว (เช่น 12 atlas DXT1 512x512 + 2 โลโก้ DXT5 512x256 = ~2.33 MB VRAM / ~1.31 MB บนดิสก์) แทนการฝังซ้ำใน `.ydr` แต่ละชิ้น (ซึ่งกิน ~24.7 MB VRAM) FiveM สตรีม `stream/*.ytd` อัตโนมัติโดยไม่ต้องเพิ่ม `data_file` พิเศษใน `fxmanifest.lua`
- ชื่อ model ห้ามซ้ำกับ prop อื่นทั้งเซิร์ฟเวอร์ ค้นใน `resources` ก่อนตั้งชื่อ

## Animation & Native `.ycd` (ไม่ต้องใช้ CodeWalker)

เมื่อตั้ง `"animate": true` ในสเปก `props.json` (ระดับชุดหรือรายชิ้น):

1. **การริกใน `forge_prop.py`:** แต่ละชิ้นส่วนที่เคลื่อนไหว (เช่น `door`, `wheel`, `crown` บน Safe; `mascot`, `streaks` บน Marker; `lid`, `coins` บน Loot Chest) ถูกจัดเข้ากลุ่มกระดูกผ่าน `b.define_bone(name, pivot, parent)` + `with b.use_bone(name):` แล้วผูกเป็น Vertex Group น้ำหนัก `1.0` (ห้าม `remove_doubles` ข้ามกลุ่มกระดูก) หลังจัดกึ่งกลางจะสร้าง Armature `<id>_rig` (ทุกกระดูกชี้ `+Y` ยาว `0.05m`, `roll=0` เพื่อให้แกน local ตรงกับแกน prop) ผูกเข้า mesh ด้วย `ARMATURE` modifier (ไม่ตั้ง `root.parent` เพื่อให้ `validate_prop.py` ผ่าน 100%) และอบ Action คีย์เฟรมแบบ per-frame ที่ต่อเชน quaternion ต่อเนื่อง (`dot >= 0`)
2. **กติกาแอนิเมชันไม่จม/ไม่ทะลุ:** มงกุฎลอย (`crown_hover`) และมาสคอตลอย (`marker_spin`) ต้องใช้คลื่นลอยขึ้นด้านบนเท่านั้น (`0.5 * (1 - cos(u * tau))`) เพื่อไม่ให้จมลงเนื้อฝาหรือลัง; ฝาหีบ (`chest_lid`) ต้องประสานมุมปิดกับความสูงเหรียญ (`chest_coins`) ไม่ให้เหรียญทะลุฝา
3. **Export เป็น `.ydr` + `.ycd` + `.ytyp`:** `export_prop.py --format native` จะ:
   - แปลง `<id>_rig` เป็น `sollumz_drawable` Armature ตั้ง `bone_properties.tag = 0, 1, ...` และเปิดครบทั้ง 9 DOF flags (`RotX..Z`, `TransX..Z`, `ScaleX..Z`) — ถ้าไม่เปิด DOF flags GTA V จะล็อกกระดูกนิ่ง
   - ตั้งใน `.ytyp`: `clip_dictionary = <id>`, `flag10 = True` (`Has Anim (YCD)`), `flag20 = True` (`Auto Start Anim`), `flag30 = True` (`Use Ambient Scale`)
   - สร้าง `CLIP_DICTIONARY` ที่มี 2 คลิป (`pack:/<id>.clip` สำหรับเล่นอัตโนมัติทันทีที่ spawn และ `pack:/idle.clip` สำหรับสั่งผ่าน `PlayEntityAnim`), export `.ycd.xml` ด้วย Sollumz แล้วคอมไพล์เป็นไบนารี `.ycd` (`RSC7 v46`, รวม `PageMap + 0x1010`) ด้วย `scripts/blender/ycd_rsc7.py` ทันที
4. **เรนเดอร์พรีวิวแอนิเมชัน:** รัน `scripts/blender/render_anim_preview.py --build work\build --out work\previews --ffmpeg <ffmpeg.exe>` จะได้ GIF วนลูปแยกแต่ละชิ้น + `animations_showcase.mp4` (H.264 `yuv420p` 1280x720 30fps) และภาพตู้เซฟเปิดประตูอัตโนมัติ
