# Integration

`scripts/new-skin.ps1` สร้างโฟลเดอร์ `weapon_<id>` พร้อม `patches/` และ `assets/effect/` โดยไม่แตะไฟล์ใช้งานจริง ขั้นตอนด้านล่างเป็นการนำเข้าระบบ

ก่อนแก้ไฟล์ระบบ ให้สำรองไว้นอก `resources` ตามแนวทางใน `weapon_core/README.components.md` เช่น `.codex-backups/`

โฟลเดอร์ `[1nfx]` ใน workspace นี้มี `1nfx_weaponskin`, `1nfx_inventory`, `1nfx_assetsimg` และ `[weapon]` พร้อมเชื่อมและตรวจด้วย `check-skin.ps1 -Root ...\[1nfx]` ได้ทันที (ใช้ `-LiteralPath` ใน PowerShell เสมอเพราะชื่อ `[1nfx]` มีวงเล็บเหลี่ยม) หากในเครื่องอื่นไม่มีโฟลเดอร์ระบบครบ `check-skin.ps1` รองรับโหมดตรวจแพ็กเกจ `[weapon]` เดี่ยวด้วย

| # | ไฟล์ปลายทาง | การกระทำ | ข้อมูลจาก |
| --- | --- | --- | --- |
| 1 | `[weapon]/weapon_<id>/stream/` | วาง `.ydr` และ `.ytd` ชื่อตรง `<Model>` | Sollumz |
| 2 | `[weapon]/weapon_core/data/weaponcomponents.meta` | แทรกต่อจาก `COMPONENT_SKIN_*` อันสุดท้าย | `weaponcomponents.insert.xml` |
| 3 | `weapon_core/data/weapons/weapon<ช่อง>.meta` | แทรกในบล็อก `<AttachBone>gun_root</AttachBone>` อันสุดท้ายที่ยังมี `<Item>` ไม่เกิน 11 ตัว (ห้ามเกิน 12 ตัวต่อบล็อก และห้ามแทรกใน `WAPClip` เด็ดขาด! สำหรับ `revolver` ให้เพิ่มใน `weapons_revolver_mk2.meta` ด้วย) | `weapon<ช่อง>.attach.insert.xml` |
| 4 | `weapon_core/data/weaponarchetypes.meta` | แทรกใน `<InitDatas>` ถัดจาก `wm_elys_*` | `weaponarchetypes.insert.xml` |
| 5 | `1nfx_weaponskin/config/weapons/<ช่อง>.lua` | เติมใน `skins` | `weapon_config.insert.lua` |
| 6 | `1nfx_weaponskin/config/skins/<id>.lua` | คัดลอก (ถูกโหลดอัตโนมัติด้วย glob) | `<id>.skin.lua` |
| 7 | `1nfx_weaponskin/html/img/effect/` | คัดลอกภาพและเสียง (`html/**` รวมอัตโนมัติ) | `assets/effect/` |
| 8 | ตาราง `items` ใน DB | รัน SQL โดยผู้ใช้เป็นคนยืนยัน | `<id>.items.sql` |
| 9 | `es_extended/items.json` | เติมรายการ ระวัง JSON comma | `es_extended.items.insert.json` |
| 10 | `1nfx_assetsimg/items/<item>.png` | ไอคอน 96×96 โปร่งใส | `icon_<slot>.png` จาก forge เปลี่ยนชื่อเป็น item |
| 11 | `1nfx_inventory/config/config.item.lua` | เติมใน `action.use` ไม่งั้นไอเทมไม่มีปุ่มใช้ในกระเป๋า | `inventory_use.insert.lua` |

หมายเหตุ:

- ไฟล์สกินแต่ละ resource ไม่ต้องมี `data_file` ยกเว้นมี `.ytyp` (เช่น `Kill.Prop` หรือโมเดลอาวุธที่ผูก `clipDictionary` คู่กับ `clip@<model>.ycd`) ให้เพิ่ม `data_file "DLC_ITYP_REQUEST" "stream/<name>.ytyp"` ใน `fxmanifest.lua`
- ถ้าใช้ `.ypt` ของตัวเอง ให้วางใน `stream/` ของ `weapon_<id>` โดยชื่อ dictionary ภายในต้องตรงกับชื่อไฟล์ (`<id>_fx.ypt`) เสมอ ห้ามเปลี่ยนแค่ชื่อไฟล์ด้านนอก
- กฎการเล่น `DamagePlayback` ของ `1nfx_weaponskin`: ช่อง `Poolcue` และ `Bottle` ตอนตีโดนแต่ยังไม่ตายจะเล่น **เฉพาะ `Hit.Screen`** (ไม่เล่น `Hit.Effect`) ส่วน `Revolver` เข้า `phase = "hit"` เสมอ ดังนั้นถ้ามี 3D Finisher Prop (`Kill.Prop`) บน `Revolver` **ต้องใส่ `on_hit = true` ในรายการแรกของ `Kill.Prop.Revolver`** ดูรายละเอียดเต็มและตัวอย่าง `Kill.Prop` ใน `references/vfx-weapon-field-study.md`
- สกินแก๊งเติม `gang_id` ใน `weaponEffects` ซึ่งจะถูกกันออกจากการ mix
- กันการ mix รายสกินได้ที่ `config/config.mixing.lua`

## โหลดเข้าเกม

`weapon_core` ต้องโหลดก่อน `1nfx_inventory`, `1nfx_utilities`, `1nfx_weaponskin` การแก้ meta ต้อง **restart เซิร์ฟเวอร์เต็มและ reconnect** เพราะ weapon metadata ไม่รีโหลดกลางทาง ตรวจว่า `weapon_<id>` ถูก ensure ตามวิธีที่ `server.cfg` จริงใช้

## ตรวจความครบ

```powershell
scripts\check-skin.ps1 -SkinType <SkinType> -Root '<server>\resources\[1nfx]'
```

ตรวจ: skin config, component ใน meta, attach point, archetype, `.ydr`, texture, item, ปุ่มใช้ในกระเป๋า, ไอคอน, ไฟล์ภาพและเสียง, ชื่อ particle ใน `.ypt`, ค่า scale/volume/duration จบด้วย `RESULT fail=N warn=N` และคืน exit code 1 เมื่อมี FAIL

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
