# Integration

`scripts/new-skin.ps1` สร้างโฟลเดอร์ `weapon_<id>` พร้อม `patches/` และ `assets/effect/` โดยไม่แตะไฟล์ใช้งานจริง ขั้นตอนด้านล่างเป็นการนำเข้าระบบ

ก่อนแก้ไฟล์ระบบ ให้สำรองไว้นอก `resources` ตามแนวทางใน `weapon_core/README.components.md` เช่น `.codex-backups/<timestamp>_<id>/`

## พาธใน `mainserver` และกฎ PowerShell `-LiteralPath`

ใน workspace `mainserver` ไฟล์ระบบจัดวางดังนี้:

- ทรัพยากรระบบ `[1nfx]`: `resources\[resources]\[1nfx]\1nfx_weaponskin`, `1nfx_inventory`, `1nfx_assetsimg`
- ทรัพยากรอาวุธ `[weapon]`: `resources\[resources]\[weapon]\weapon_core`, `weapon_<id>`
- ทะเบียนไอเทมหลัก: `resources\[core]\1nfx_core\items.json` (หรือ `es_extended/items.json` ในเซิร์ฟเวอร์รุ่นเก่า — `check-skin.ps1` รองรับทั้งคู่โดยอัตโนมัติ)

**กฎบังคับสำหรับ PowerShell บน Windows:**
- พาธที่มี `[resources]`, `[1nfx]`, `[weapon]` หรือ `[core]` **ต้องส่งผ่าน `-LiteralPath` เสมอ** เพราะ `-Path` ตีความ `[...]` เป็น wildcard และจะคืนค่าว่างโดยไม่แจ้ง error
- **ห้ามใช้ `Copy-Item -LiteralPath "$src\*"`** เมื่อ `$src` มีวงเล็บเหลี่ยม (ล้มเหลวเงียบใน PowerShell 5.1 เพราะ `*` ไม่ถูกกระจายในโหมด `-LiteralPath`) ให้สำรองหรือคัดลอกโฟลเดอร์ด้วย `robocopy $src $dst /E` หรือคัดลอกรายไฟล์ด้วย `[System.IO.File]::Copy($srcFile, $dstFile, $true)`

| # | ไฟล์ปลายทาง | การกระทำ | ข้อมูลจาก |
| --- | --- | --- | --- |
| 1 | `[weapon]/weapon_<id>/stream/` | วาง `.ydr` และ `.ytd` ชื่อตรง `<Model>` | Sollumz หรือ `export_ydr.py` |
| 2 | `[weapon]/weapon_core/data/weaponcomponents.meta` | แทรกต่อจาก `COMPONENT_SKIN_*` อันสุดท้าย | `weaponcomponents.insert.xml` |
| 3 | `[weapon]/weapon_core/data/weapons/weapon<ช่อง>.meta` | แทรกในบล็อก `<AttachBone>gun_root</AttachBone>` อันสุดท้ายที่ยังมี `<Item>` ไม่เกิน 11 ตัว (**ห้ามเกิน 12 ตัวต่อบล็อก** หากเต็ม 12 ให้เปิดบล็อก `<AttachBone>gun_root</AttachBone>` ใหม่ต่อท้าย และ **ห้ามแทรกใน `WAPClip` เด็ดขาด!** สำหรับ `revolver` ต้องเพิ่มใน `weapons_revolver_mk2.meta` ด้วย และสำหรับ `bat` อยู่ใน `weapons.meta` ใต้ `WEAPON_BAT`) | `weapon<ช่อง>.attach.insert.xml` |
| 4 | `[weapon]/weapon_core/data/weaponarchetypes.meta` | แทรกใน `<InitDatas>` ถัดจาก `wm_elys_*` | `weaponarchetypes.insert.xml` |
| 5 | `[1nfx]/1nfx_weaponskin/config/weapons/<ช่อง>.lua` | เติมใน `skins` (หากเปิดช่องใหม่เช่น `bat` ต้องสร้าง `config/weapons/bat.lua`, เพิ่มใน `fxmanifest.lua`, ตั้ง `hidden_weapons.Bat = false` ใน `config.mixing.lua`, และตั้ง `WEAPON_BAT = true` ใน `1nfx_inventory/config/config.weaponskin.lua`) | `weapon_config.insert.lua` |
| 6 | `[1nfx]/1nfx_weaponskin/config/skins/<id>.lua` + `fxmanifest.lua` | คัดลอกไฟล์สกิน และ **ต้องเพิ่ม `"config/skins/<id>.lua"` ใน `shared_scripts` ของ `1nfx_weaponskin/fxmanifest.lua` ก่อนบรรทัด `"core/sh_mixing.lua"` เสมอ** (ไม่ได้ใช้ glob!) | `<id>.skin.lua` |
| 7 | `[1nfx]/1nfx_weaponskin/html/img/effect/` และ `html/sound/` | คัดลอกภาพเต็มจอ `1920×1080` (`center alpha = 0`) ลง `html/img/effect/` และวางไฟล์เสียง `.wav` ไว้ทั้งใน `html/sound/` และ `html/img/effect/` เพื่อให้ทั้ง `1nfx_weaponskin` NUI และ `1nfx_preview` โหลดเสียงได้ครบ | `assets/effect/` |
| 8 | ตาราง `items` ใน DB | รัน SQL โดยผู้ใช้เป็นคนยืนยัน | `<id>.items.sql` |
| 9 | `[core]/1nfx_core/items.json` (หรือ `es_extended/items.json`) | เติมรายการ ระวัง JSON comma | `es_extended.items.insert.json` |
| 10 | `[1nfx]/1nfx_assetsimg/items/` | ไอคอนคู่ `96×96` RGBA พื้นโปร่งใสทั้ง 2 ชุดชื่อ: (1) ไอคอนไอเทมแพ็กการ์ด `skin_<prefix>_<id>.png` (เช่น `skin_b_lego.png`, `skin_p_lego.png`, `skin_k_lego.png`, `skin_m_lego.png`, `skin_r_lego.png`, `skin_bat_lego.png`) และ (2) ไอคอนอาวุธ `COMPONENT_SKIN_<SLOT>_<ID>.png` (ห้ามนำภาพเต็มจอ `1920×1080` มาวางทับเด็ดขาด!) | `icon_<slot>.png` / เรนเดอร์คู่ `96×96` |
| 11 | `[1nfx]/1nfx_inventory/config/config.item.lua` | เติมทั้งใน `action.use` และ `action.give` เพื่อให้ไอเทมกดใช้และส่งต่อในกระเป๋าได้ครบ | `inventory_use.insert.lua` |

หมายเหตุ:

- ไฟล์สกินแต่ละ resource ไม่ต้องมี `data_file` ยกเว้นมี `.ytyp` (เช่น `Kill.Prop` หรือโมเดลอาวุธที่ผูก `clipDictionary` คู่กับ `clip@<model>.ycd`) ให้เพิ่ม `data_file "DLC_ITYP_REQUEST" "stream/<name>.ytyp"` ใน `fxmanifest.lua`
- ถ้าใช้ `.ypt` ของตัวเอง ให้วางใน `stream/` ของ `weapon_<id>` โดยชื่อ dictionary ภายในต้องตรงกับชื่อไฟล์ (`<id>.ypt` หรือ `<id>_fx.ypt`) เสมอ ห้ามเปลี่ยนแค่ชื่อไฟล์ด้านนอก
- **กฎขนาดภาพ NUI และไอคอนคู่ (`Dual 96×96` vs `1920×1080`):** ภาพ `Hit.Screen` / `Kill.Screen` (`*effect.png`) ต้องเป็น `1920×1080` RGBA ที่เว้นโซนกลางจอ `60% × 60%` เป็น `alpha = 0` ส่วนไอคอน `1nfx_assetsimg/items/<item>.png` รวมถึง `skin_b_<id>.png` / `skin_p_<id>.png` ใน `html/img/effect/` (ถ้ามี) **ต้องเป็น `96×96` เท่านั้น** (พบข้อผิดพลาดจริงใน `weapon_lego` รุ่นเก่าที่คัดลอกภาพ `1920×1080` ไปทับ `skin_b_lego.png` และ `skin_p_lego.png` ทำให้ NUI ต้องถอดรหัสพิกเซลเกินความจำเป็นถึง 237 เท่า)
- กฎการเล่น `DamagePlayback` จริงใน `1nfx_weaponskin/core/sh_mixing.lua:304–352`:
  - ช่อง `Poolcue` และ `Bottle` ตอนตีโดนแต่ยังไม่ตาย (`not died`) จะเล่นทั้ง `Hit.Effect` (`effects.hit`) และ `Hit.Screen` แต่จะไม่ดึง `Kill.Effect` มาใช้แทนหาก `Hit.Effect` ว่าง (และไม่สปอว์น `Kill.Prop`) ดังนั้นควรกำหนด `Hit.Effect` ไว้ให้ครบทุกช่องเสมอ
  - ช่อง `Revolver` บังคับ `phase = "hit"` เสมอ (แม้กระสุนนัดนั้นจะฆ่าตาย!) และจะ fallback ไปใช้ `Kill.Effect` ก็ต่อเมื่อไม่ได้ตั้ง `Hit.Effect` ไว้ ดังนั้น `Hit.Effect.Revolver` ต้องออกแบบให้คมชัดที่ `scale = 1.0` และถ้ามี 3D Finisher Prop (`Kill.Prop`) บน `Revolver` **ต้องใส่ `on_hit = true` ในรายการแรกของ `Kill.Prop.Revolver`** ดูรายละเอียดเต็มใน `references/vfx-weapon-field-study.md`
- สกินแก๊งเติม `gang_id` ใน `weaponEffects` ซึ่งจะถูกกันออกจากการ mix
- กันการ mix รายสกินได้ที่ `config/config.mixing.lua`

## ด่านตรวจกระดูกและหน่วยความจำก่อนนำเข้า (`references/bone-and-memory-safety.md`)

ก่อนสั่งโหลดสกินใหม่เข้าเซิร์ฟเวอร์ ต้องตรวจตาม `references/bone-and-memory-safety.md` ให้ครบทุกข้อ:

1. **โครงกระดูกและเมทริกซ์ `.ydr`:** `inspect-ydr.ps1` ต้องได้ `fail=0` ทุกช่อง (`Gun_Root` identity ที่ `(0,0,0)`, กระดูกลูกไม่ซ้อนทับ origin, `ChildParentIndices` ครบชุดละ 4 คู่, `BlendWeights` ผลรวม = `1.0`)
2. **`AttachPoints` ใน `weapons/*.meta`:** ทุกบล็อก `<AttachBone>gun_root</AttachBone>` มี `<Item>` ไม่เกิน 12 ตัว และไม่เผลอใส่สกินลงบล็อก `WAPClip`
3. **ความปลอดภัยฝั่ง Lua (`1nfx_weaponskin`):** การผูก PTFX/Prop ทุกจุดต้องตรวจ `DoesEntityExist` และ `boneIndex ~= -1` ก่อนเรียก native, แยก `boneIndex` (`StartParticleFxLoopedOnEntityBone`) ออกจาก `boneTag` (`StartParticleFxNonLoopedOnPedBone`), ไม่ค้าง `ParticlePinnedAssets` ถาวรสำหรับ non-looped FX และมี hook ล้าง PTFX/Model/AnimDict ครบทั้งตอนสลับอาวุธ, สลับสกิน, เปลี่ยนร่าง Ped, ตาย และ `onResourceStop`
4. **งบ VRAM และ Particle:** `.ytd` ต่อชิ้นเป็น DXT1/DXT5 พร้อม mipmaps ขนาดไม่เกิน `4 MB`, `.ypt` ไม่เกิน `8 MB` และไม่มีลูป `Wait(0)` ขณะถือสกินนิ่งๆ

## โหลดเข้าเกม

`weapon_core` ต้องโหลดก่อน `1nfx_inventory`, `1nfx_utilities`, `1nfx_weaponskin` การแก้ meta ต้อง **restart เซิร์ฟเวอร์เต็มและ reconnect** เพราะ weapon metadata ไม่รีโหลดกลางทาง ตรวจว่า `weapon_<id>` ถูก ensure ตามวิธีที่ `server.cfg` จริงใช้

## ตรวจความครบ

```powershell
& '.claude\skills\infrontofx\weapon-forge\scripts\check-skin.ps1' -SkinType <SkinType>
```

(หรือระบุ `-Root 'C:\Users\Administrator\Desktop\mainserver\resources\[resources]\[1nfx]'` ก็ได้ สคริปต์ค้นหาโฟลเดอร์คู่ขนาน `[weapon]` และ `[core]\1nfx_core\items.json` ให้อัตโนมัติ)

ตรวจ: skin config, component ใน meta, attach point (รวมถึง `weapons_revolver_mk2.meta`), archetype, `.ydr`, texture, item, ปุ่มใช้ในกระเป๋า, ไอคอน, ไฟล์ภาพและเสียง, ชื่อ particle ใน `.ypt`, ค่า scale/volume/duration จบด้วย `RESULT fail=N warn=N` และคืน exit code 1 เมื่อมี FAIL

ก่อนนำ `.ydr` ใหม่เข้าเกมทุกครั้ง ให้ผ่าน `scripts\inspect-ydr.ps1 -Path <ไฟล์> -Slot <ช่อง>` ซึ่งตรวจโครงไฟล์เทียบกฎที่วัดจากโมเดลจริงในเซิร์ฟเวอร์ ผ่านแล้วไม่ได้แปลว่าเกมโหลดได้แน่นอน แต่ไม่ผ่านแปลว่าไม่ควรนำเข้า

## QA ในเกม

สิ่งที่สคริปต์ตรวจไม่ได้ ต้องดูในเกมจริง:

- [ ] ใส่สกินจากเมนูแล้วโมเดลขึ้น ไม่เป็นก้อนหรือหาย
- [ ] มือจับตรงด้าม ทั้งท่ายืนและท่าตี
- [ ] Poolcue มือซ้ายจับตรง `Gun_GripL`
- [ ] Revolver ปากกระบอกตรง flash ยิงได้ปกติ
- [ ] มองบุคคลที่หนึ่งแล้วไม่บังจอ
- [ ] เมนู Preview เล่น Hold/Hit/Kill ถูก
- [ ] ตีผู้เล่นจริง: เหยื่อเห็นภาพ + เสียง คนฆ่าได้ยินเสียงฆ่า
- [ ] เปลี่ยนสกินไปมาแล้ว particle Hold ไม่ค้าง
- [ ] `resmon` ไม่พุ่งเมื่อมีหลายคนถือสกินนี้
