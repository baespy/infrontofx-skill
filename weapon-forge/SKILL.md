---
name: weapon-forge
description: ปั้นสกินอาวุธ FiveM ใหม่พร้อม particle, screen effect และ sound ตามตระกูลสไตล์ที่อธิบายไว้ใน references/style-families.md แล้วเชื่อมเข้าระบบ 1nfx_weaponskin ใช้เมื่อผู้ใช้ขอปั้นอาวุธ ทำสกินอาวุธ ออกแบบ weapon set ทำ weapon skin, ออกแบบ particle ใหม่หรือสร้างไฟล์ .ypt (ptfx, effect ตอนถือ ตอนตี ตอนฆ่า), ศึกษาหรือแกะดู particle ของสกินอื่น, hit/kill screen, เสียงตี/เสียงฆ่า, Blender weapon model, หรือเพิ่มสกินเข้า [weapon] และ 1nfx_weaponskin รวมถึงงานปั้นอาวุธ GTA V ผ่าน Antigravity หรือ Blender MCP, export และตรวจไฟล์ .ydr/.ytd, ดูรายการสกินทั้งหมดในเซิร์ฟเวอร์ และแยกโมเดล AI จาก Tripo หรือ Meshy ที่ปั้นมาทั้งชุดในไฟล์เดียวออกเป็นอาวุธแต่ละชิ้น (GTA V weapon modeling, Antigravity, Blender MCP, Sollumz)
---

# Weapon Forge

สร้างชุดอาวุธใหม่สำหรับเซิร์ฟเวอร์ `[1nfx]` จากสเปกเดียว ได้โมเดล, texture, ไอคอน, particle (`.ypt` ที่ออกแบบเอง), ภาพเต็มจอ, เสียง และไฟล์เชื่อมระบบ

Particle คือส่วนที่ผู้ใช้ให้ความสำคัญที่สุดและต้องการงานละเอียด ทุกชุดต้องมี effect ของตัวเองอย่างน้อย Hold, Hit และ Kill ที่ออกแบบตาม `references/particles.md` มีอย่างน้อยหนึ่ง layer ที่เป็นเอกลักษณ์ของชุด build ต้องได้ `RESULT ok` โดยไม่เหลือ `WARN` ที่อธิบายไม่ได้ และต้องเปิดดูภาพ preview กับภาพ sprite ด้วยตาก่อนส่งงานทุกครั้ง

## ขั้นตอน

ก่อนเริ่ม รัน `scripts/doctor.ps1` แล้วดู `references/server-catalog.md` เพื่อกันชื่อซ้ำและหาสกินใกล้เคียงที่เปิดศึกษาได้

1. **รับโจทย์:** ชื่อชุด, อาวุธที่ต้องการ, สไตล์ ถ้าผู้ใช้ไม่ระบุสไตล์ให้เสนอจาก `references/style-families.md` ซึ่งอธิบายรูปทรง วัสดุ ลวดลาย สี และ FX ของแต่ละตระกูลเป็นตัวหนังสือ ถ้าผู้ใช้ขอแนวใหม่หรือส่งรูปมาในแชต ให้ถอดเป็นคำอธิบาย 5 แกนตามหัวข้อ "ถอดสไตล์ใหม่จากคำอธิบาย" แล้วทำงานจากคำอธิบายนั้น
2. **เขียนสเปก:** คัดลอก `templates/skin-spec.example.json` ไปไว้ `weapon_<id>/source/spec.json`
3. **ตรวจความเป็นต้นฉบับ:** ทำตาม "กฎที่ห้ามข้าม" ด้านล่าง
4. **ปั้น:** รัน `forge_weapon.py` แบบไม่ bake เปิดดู `<id>_sheet.png` เทียบกับ DNA ของ family และ "เกณฑ์ตรวจหน้าตา" ใน `style-families.md` แก้แล้วรันซ้ำ จนลงตัวจึง `--bake 1024 --icons` ถ้าต้องปั้นต่อแบบโต้ตอบ ใช้ Antigravity กับ Blender MCP ตาม `references/antigravity.md` และตรวจด้วย `validate_model.py` ก่อน bake ทุกครั้ง ถ้าผู้ใช้มีโมเดลจาก AI อยู่แล้ว ไม่ว่าจะชิ้นเดียวหรือทั้งชุดในไฟล์เดียว ให้ใช้ `split_ai_set.py` แทนการปั้นด้วย forge และเปิดดู preview ก่อน bake
5. **Particle:** อ่าน `references/particles.md` ก่อน แล้วเริ่มจากธีมที่ใกล้ที่สุด (`scripts/ptfx/ptfx.ps1 themes` แล้ว `new -Theme <t> -Name <id>`) หรือเขียน design ต่อจาก `templates/ptfx-design.example.json` ปรับ palette ให้ตรงชุด เพิ่ม layer เอกลักษณ์ของชุด (sheet ของชุด, `glyph`, ภาพของผู้ใช้) รัน `ptfx.ps1 build` อ่านทุกบรรทัด `ERROR` `WARN` `NOTE` เปิดดู `<dict>.preview.png` กับ `<dict>.sprites.png` แก้แล้วรันซ้ำจนจังหวะ สี และขนาดลงตัว
6. **FX และไฟล์เชื่อม:** ใส่ design ไว้ที่ `fx.ptfx` ของสเปก (หรือ `fx.theme` เมื่อใช้ธีมตรง ๆ ซึ่งเลือก preset ของ screen กับ sound ที่เข้าชุดให้ด้วย) แล้วรัน `scripts/new-skin.ps1` ได้ `.ypt`, ภาพเต็มจอ, เสียงตีและเสียงฆ่าแยกไฟล์, Lua, meta, SQL ดูภาพที่ได้ทุกครั้ง
7. **Export:** ทาง A ใช้ Sollumz ถ้าเครื่องยังไม่มี ให้ถามผู้ใช้ก่อนติดตั้ง ทาง B ใช้ `export_ydr.py` โดยอ่านจุดที่ต้องแก้ใน `references/modeling-pipeline.md` ก่อน แล้วตรวจผลด้วย `inspect-ydr.ps1` จนไม่มี FAIL
8. **เชื่อมระบบ:** สำรองไฟล์แล้วทำตาม `references/integration.md`
9. **ตรวจ:** รัน `scripts/check-skin.ps1` จนไม่มี FAIL แล้วให้ผู้ใช้ทำ QA ในเกม

## เลือกอ่าน

| งาน | อ่าน |
| --- | --- |
| เลือกสไตล์, สี, ลวดลาย, ค่าใน `style` | `references/style-families.md` |
| ขนาด, งบ tris, bone, ช่องอาวุธ | `references/weapon-anatomy.md` |
| ปั้น, bake, shader, export | `references/modeling-pipeline.md` |
| แยกโมเดล AI เป็นอาวุธ, ค่าของแต่ละทรง, ปัญหาที่เคยเจอ | `references/modeling-pipeline.md` หัวข้อ `split_ai_set.py` และ `templates/ai-set.example.json` |
| ธีม particle, ออกแบบเอง, สูตร layer, sprite และ sheet หลายเฟรม, กฎ Hold/Hit/Kill, แกนของแต่ละช่วง, สิ่งที่พิสูจน์แล้ว, config ฝั่ง Lua | `references/particles.md` |
| สูตรคีย์เฟรมขั้นสูงจากไฟล์จริง (`twinkle_glints`, `emissiveKeys`, `accelKeys`, ริบบิ้น 2 ชั้น), กฎ `DamagePlayback` รายช่อง, `Kill.Prop` 3D Finisher, 4 ระดับ Shader/UV-Scroll (`.ycd`), และข้อผิดพลาดที่ห้ามทำซ้ำ | `references/vfx-weapon-field-study.md` |
| โครงสร้าง `.ypt`, หน่วยของค่า, ตารางเฟรมของ sheet, lint ตรวจอะไร, สเปกระดับล่าง, รายชื่อ texture ของเกม, คำสั่งทั้งหมดของ `ptfx.ps1` | `references/ptfx-format.md` |
| ภาพเต็มจอและเสียง | `references/screen-sound.md` |
| เชื่อมเข้าระบบและ QA | `references/integration.md` |
| ปั้นผ่าน Antigravity, Blender MCP, โมเดลจาก AI | `references/antigravity.md` |
| สกินทั้งหมดในเซิร์ฟเวอร์, ชื่อที่ใช้แล้ว, สถิติจริง | `references/server-catalog.md` (รายการเต็มใน `server-catalog.json`) |

## เครื่องมือ

| สคริปต์ | หน้าที่ |
| --- | --- |
| `scripts/blender/forge_weapon.py` | สร้างโมเดล 7 ช่อง 20 สไตล์ จากสเปก (รองรับใบมีด 3D หลายคม + ร่องเลือด, มังกร 3D, หน้ากากโอนิโค้ง 3D, อาร์คีไทป์ช่อง Bottle/Knuckle/Revolver และ `--ydr`) |
| `scripts/blender/render_fx_assets.py` | ปั้นและเรนเดอร์ 3D VFX ด้วย Blender Cycles (CPU + OpenImageDenoise): กรอบจอ 3D Forged-Carbon/Gold/Ruby `1920x1080` (`center alpha = 0`), 3D PTFX sprites/sheets (`slash`, `seal`, `katana_cross`, `blades`, `shards`) และ `512x128` seamless ribbon texture |
| `scripts/blender/import_ai_model.py` | แปลงโมเดลจากภายนอก (AI/ซื้อ: glb, fbx, obj) เป็นโมเดลช่องอาวุธ: จัดทิศ (`--pca`) ลบเศษลอย (`--strip-islands`) ปรับขนาด ลดโพลี bake texture (`--bake-mode lit|color`) ใส่ skeleton และ `--ydr` ดู `references/modeling-pipeline.md` |
| `scripts/blender/split_ai_set.py` | แยกโมเดล AI ทั้งชุดในไฟล์เดียว (หรือชิ้นเดียว) เป็นโมเดลช่องอาวุธ: นับชิ้น จัดแกนจากรูปทรง วางจุดจับ ลดโพลี bake พร้อมแสงและวัสดุ ปรับสี ใส่ skeleton |
| `scripts/ptfx/ptfx.ps1 themes`, `new -Theme t -Name id` | ธีม particle 26 ธีม (Hold/Hit/Kill ครบ) และคำสั่งเขียน design ของชุดใหม่จากธีม |
| `scripts/ptfx/ptfx.ps1 build -Spec design.json -Out <stream>` | สร้าง `.ypt` ต้นฉบับจาก design: sprite ที่วาดเอง 82 แบบ, sheet สำเร็จรูป 22 ชุด, สูตร layer 67 แบบ (รองรับ `emissiveKeys` และ `accelKeys`) แล้วอ่านกลับมาตรวจ, เทียบทุกค่ากับไฟล์จริง (lint) และออกภาพ preview |
| `scripts/ptfx/ptfx.ps1 recipes`, `sprites`, `preview` | ดูสูตร layer กับ sheet สำเร็จรูป, ดู sprite ทุกแบบ, จำลองภาพ effect จาก design หรือจาก `.ypt` ใดก็ได้ (มองข้าง 8 ช่วงเวลา + มองบน) |
| `scripts/ptfx/ptfx.ps1 inspect`, `textures`, `lint`, `decompile`, `census` | สรุป effect เป็นข้อความ, ถอด texture เป็น PNG, ตรวจไฟล์ด้วยเกณฑ์ของ build, แตกเป็น JSON, ตรวจโครงไฟล์ ใช้ศึกษา particle ที่มีอยู่ |
| `scripts/new-skin.ps1 -Spec x.json -OutRoot <[weapon]>` | สร้าง resource, particle จาก `fx.ptfx` หรือ `fx.theme`, ภาพ, เสียงตีและเสียงฆ่า, Lua, patch |
| `scripts/make-screen.ps1` | ภาพเต็มจอ 17 แบบ |
| `scripts/make-sound.ps1` | เสียงสังเคราะห์ 18 แบบ |
| `scripts/check-skin.ps1 -SkinType X -Root <[1nfx] or [weapon]>` | ตรวจความครบทุกจุด (รองรับทั้งโหมดเต็มเซิร์ฟเวอร์และโหมดตรวจแพ็กเกจ `[weapon]` เดี่ยว) |
| `scripts/doctor.ps1` | บอกว่าเครื่องมือไหนพร้อมและขาดอะไร |
| `scripts/catalog-weapons.ps1 -WeaponRoot <[weapon]> -OutMd references/server-catalog.md -OutJson references/server-catalog.json` | อ่านสกินทั้งเซิร์ฟเวอร์ใหม่ รันเมื่อเพิ่มหรือลบสกิน |
| `scripts/blender/validate_model.py` | ตรวจ `.blend` กับสัญญาของช่องอาวุธ ใช้ได้ทั้ง headless และใน Blender สด |
| `scripts/blender/export_ydr.py` | สร้าง `.ydr` (RSC7 v165) / `.ytd` (v13) / `.dds` (DXT5 + mipmaps) โดยไม่ใช้ Sollumz ผ่าน `inspect-ydr.ps1` ทุกข้อและพิสูจน์โหลดในเกมจริงแล้ว |
| `scripts/inspect-ydr.ps1 -Path x.ydr -Slot knife` | ตรวจโครงไฟล์ `.ydr` เทียบกฎจากโมเดลจริง |
| `scripts/sync-antigravity.ps1` | คัด skill ไป `.agents/skills/` รันทุกครั้งหลังแก้ skill |

เครื่องมือ particle, ภาพ และเสียงใช้แค่ PowerShell 5.1 ที่มากับ Windows ส่วนงานโมเดลต้องมี Blender (`doctor.ps1` บอกตำแหน่งที่เจอ ค่าเดิมคือ `C:\Tools\blender-4.2.3-windows-x64\blender.exe`) อย่าเขียนสคริปต์ที่ต้องใช้ Python หรือ Node เพราะบางเครื่องไม่มี

โฟลเดอร์ในพื้นที่งาน: `ex` คือเซิร์ฟเวอร์ของเรา (`ex\[weapon]`, `ex\1nfx_weaponskin`) ส่วน `bb`, `boom`, `ln`, `ms`, `mumu`, `sk` เป็น resource ของเซิร์ฟเวอร์อื่น ใช้ศึกษาแนวทางได้ แต่ห้ามนำไฟล์หรือ effect ของเขามาใส่ในงานของเรา

## กฎที่ห้ามข้าม

**ต้นฉบับ.** แนวสไตล์ใน `style-families.md` มาจากงานของผู้สร้างอื่น (WISHME, LUV TOWN ฯลฯ) ซึ่งหลายชุดระบุ "do not distribute or modify" ใช้ได้แค่ทิศทางสไตล์:

- ห้ามลอกโมเดล, โลโก้, ลายน้ำ, ชื่อชุด หรือมาสคอตเฉพาะของเขา
- ตั้งชื่อใหม่และออกแบบสัญลักษณ์ใหม่ทุกครั้ง ให้ต่างจากต้นแบบอย่างน้อยในรูปทรงหลักและลวดลายเด่น
- ห้ามใช้เครื่องหมายการค้าจริง เช่น ชื่อแบรนด์แฟชั่น, ทัวร์นาเมนต์, ตัวละครเกม

**ไฟล์ที่ล็อก.** Resource ที่มี `.fxap` ถูก Cfx escrow ห้ามถอดรหัส, ดึง หรือแก้ไฟล์ข้างใน ใช้เป็นตัวอ้างอิงได้แค่รายชื่อไฟล์ ตัวอย่างที่เปิดศึกษาได้คือ `weapon_elys`, `weapon_extreme`, `weapon_lego`, `weapon_white_rabbit`, `weapon_eclipse`, `weapon_halloween`, `weapon_flood_bite`, `weapon_effects`, `weapon_core` และห้ามคัดลอก dictionary ของผู้สร้างอื่นมาใช้ในงานใหม่

**ไฟล์ระบบ.** `new-skin.ps1` ไม่แตะไฟล์จริง การแก้ meta, config, `items.json` ต้องสำรองก่อน การรัน SQL และการรีสตาร์ตเซิร์ฟเวอร์ให้ผู้ใช้ยืนยัน

**ทำงานร่วมกัน.** Antigravity, Codex และ Claude Code แก้โฟลเดอร์นี้ได้พร้อมกัน ให้เช็กเวลาแก้ล่าสุดก่อนแก้ไฟล์ อย่าให้สอง agent ทำสกินเดียวกันพร้อมกัน ต้นฉบับ skill อยู่ที่ `.claude/skills/weapon-forge` ห้ามแก้สำเนาใน `.agents/`

**Particle.** สเปกที่ได้จาก `decompile` และภาพที่ได้จาก `textures` เป็นเอกสารศึกษา ห้ามนำ texture ของผู้สร้างอื่นไปใส่ในชุดของเรา และ `build` จะไม่ประกอบสเปกที่ decompile มาเว้นแต่ส่ง `-AllowDerived` ซึ่งใช้ได้กับไฟล์ที่เราสร้างเองเท่านั้น ชื่อ dictionary และชื่อ effect ต้องขึ้นต้นด้วย id ของชุด effect หนึ่งตัวมีได้ไม่เกิน 7 layer Hold กับ Hit เกาะกระดูกที่แกนไม่ตรงกับโลก ให้ใช้ `gravity` แทน `dir: "up"` (ดูตารางแกนใน `particles.md`) ธีมเป็นจุดเริ่ม ไม่ใช่งานสำเร็จ: งานขายต้องมี layer เอกลักษณ์ของชุดเสมอ

**รายงานตามจริง.** แยกให้ชัดว่าอะไรตรวจแล้วและอะไรยังไม่ได้ลองในเกม `.ypt` ที่ build ผ่าน `RESULT ok` คือโครงไฟล์ถูกและทุกค่าอยู่ในช่วงที่ไฟล์จริงใช้ ยังไม่ใช่ผลในเกม: ไฟล์ที่ตัวสร้างนี้ผลิตยังไม่เคยมีใครโหลดในเกม ภาพ preview เป็นการจำลอง เสียงที่สังเคราะห์ยังไม่มีใครฟัง ต้องให้ผู้ใช้ตัดสิน เมื่อผู้ใช้รายงานสิ่งที่เห็นในเกม ให้แก้ค่าเริ่มต้นในสูตรและอัปเดตหัวข้อ "สิ่งที่พิสูจน์แล้ว" ใน `particles.md`

## รูปแบบโค้ด

Lua ที่เขียนเพิ่มให้เป็นไปตาม `infrontofx-skill`: 4 ช่องว่าง, double quotes, trailing comma, ไม่มีคอมเมนต์ใน Lua ที่ผลิต
