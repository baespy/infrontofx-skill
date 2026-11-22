# Integration

## ไฟล์ที่ต้องมีในเกม

| ไฟล์ | มาจาก |
| --- | --- |
| `<id>.ydr` | `export_prop.py` (mesh + texture + collision แบบ embedded) |
| (ฝังใน `.ydr`) | texture palette หรือ atlas DXT5 ที่ `export_prop.py` ฝังให้ |
| `<id>.ytyp` | archetype ของชิ้นนั้น (`lodDist`, `textureDictionary` = `<id>`) หนึ่งไฟล์ต่อหนึ่ง prop |
| `<id>.ycd` (ถ้ามี) | animation เช่น marker หมุน/ลอย ผูกผ่าน `clipDictionary` ใน ytyp |

## Resource

เซิร์ฟเวอร์มี `resources\[resources]\[1nfx]\1nfx_prop` อยู่แล้ว (airdrop, blackout, pumpkin, waterpipe มีทั้ง `.ydr` `.ytd` `.ytyp` `.ycd`) ชุดใหม่ใส่ได้สองแบบ:

- ชุดเล็กหรือชิ้นเดี่ยว: เพิ่มไฟล์ลง `1nfx_prop\stream` แล้วเพิ่มบรรทัด `data_file` ใน `fxmanifest.lua` ของมัน (สำรองก่อน)
- ชุดใหญ่ของแบรนด์: resource ใหม่ `1nfx_prop_<set>` แยกต่างหาก ปิด/เปิดทั้งชุดได้

```lua
fx_version "cerulean"
game "gta5"
lua54 "yes"

files {
    "stream/*.ytyp",
}

data_file "DLC_ITYP_REQUEST" "stream/1nfx_goo_garage.ytyp"
data_file "DLC_ITYP_REQUEST" "stream/1nfx_goo_atm.ytyp"
```

ทุกคำสั่ง PowerShell ที่อ้าง `[resources]` หรือ `[1nfx]` ต้องใช้ `-LiteralPath` และคัดลอกด้วย `robocopy` หรือ `[IO.File]::Copy` (ดู `../weapon-forge/references/antigravity.md`)

## Spawn

prop ประจำจุด (ป้าย Garage, ATM, โต๊ะคราฟต์) เป็น prop ฝั่ง client ที่ไม่ sync ผ่าน network ให้ใช้ `lib.spawn.pointProp` ของ `1nfx_lib` ซึ่งสร้างเมื่อเข้าใกล้ ลบเมื่อออกห่าง โหลด model แบบมี timeout เรียก `SetModelAsNoLongerNeeded` และลบทุกชิ้นตอน `onResourceStop` ให้เอง

```lua
local scriptname = GetCurrentResourceName()

local PropPoints = {
    Points = {},
}

function PropPoints:Start()
    for index, prop in ipairs(Config.Props) do
        self.Points[index] = lib.spawn.pointProp({
            model = prop.model,
            coords = prop.coords,
            heading = prop.heading,
            distance = prop.distance or 60.0,
            collision = prop.collision ~= false,
        })
    end
end

function PropPoints:Stop()
    for index, point in pairs(self.Points) do
        point:remove()
        self.Points[index] = nil
    end
end

CreateThread(function()
    PropPoints:Start()
end)

AddEventHandler("onResourceStop", function(resourceName)
    if resourceName ~= scriptname then
        return
    end
    PropPoints:Stop()
end)
```

ระบบที่มี interaction อยู่แล้ว (garage, impound, ATM, shop, stash, crafting) ให้เปลี่ยนแค่ชื่อ model ใน config ของ resource นั้น อย่าเขียนจุด interaction ซ้ำ เปิด config ของ resource นั้นดูก่อนว่ารับชื่อ model ได้ไหม

## Marker หมุนและลอย

- ทางที่ดีที่สุด: ทำ animation เป็น `.ycd` (หมุนรอบ Z 360 องศา 4 วินาที + ลอยขึ้นลง 8 ซม.) แล้วผูกใน ytyp แบบที่ `1nfx_airdrop` ใช้ ไม่มีต้นทุนสคริปต์
- ทางสำรองด้วย Lua: หมุนเฉพาะตอนผู้เล่นอยู่ใกล้ (ใน `onEnter`/`onExit` ของ point) ใช้ `SetEntityRotation` ทุกเฟรมเฉพาะ entity นั้น หยุด thread เมื่อออกจาก point ตั้ง `collision = false`
- หยดสไลม์ลอยรอบกล่องทำเป็น particle ได้ด้วยเครื่องมือ `ptfx` ของ weapon-forge (`../weapon-forge/references/particles.md`) โหลดด้วย `lib.requestNamedPtfxAsset` และต้องเรียก `StopParticleFxLooped` + `RemoveNamedPtfxAsset` ตอนออกจากจุด

## QA ในเกม (ให้ผู้ใช้ทำ)

1. `ensure` resource แล้ว spawn ทีละชิ้นด้วยคำสั่งทดสอบ ดูว่ามี texture (ไม่ใช่ม่วงดำ = ytd ไม่โหลดหรือชื่อ dictionary ผิด)
2. เดินชนทุกด้าน ผู้เล่นต้องไม่ทะลุ (ยกเว้น marker)
3. ดูทิศหน้า: ถ้าหน้าป้ายหันผิดทาง ให้แก้ heading ในโค้ดหรือ config (+180) ไม่ใช่หมุน mesh
4. เดินออกไกลแล้วกลับเข้ามา ดูว่า prop หายและกลับมาตาม `lodDist` และ `distance` ไม่มีชิ้นค้าง
5. `restart` resource สามรอบติด ดูว่าไม่มี prop ซ้อนกันค้างในโลก
6. เปิด `resmon` ตอนอยู่กลางจุดที่มี prop หลายชิ้น resource ต้องไม่กินเวลาค้างเมื่อไม่มีใครอยู่ใกล้

## สิ่งที่พิสูจน์แล้ว

| วันที่ | เรื่อง | ผล |
| --- | --- | --- |
| 2026-11-19 | `forge_prop.py` สร้างชุดตัวอย่าง 9 ชิ้นบน Blender 4.2.3 และ `validate_prop.py` ผ่าน `fail=0` ทุกชิ้น | ผ่าน (ใน Blender เท่านั้น) |
| 2026-11-19 | `export_prop.py` export ทั้ง 9 ชิ้นเป็น CodeWalker XML ผ่าน Sollumz 2.9.1 (`RESULT ok=9`) ได้ ydr.xml, ytyp.xml และ DDS | ผ่าน (ยังไม่ได้แปลงเป็นไบนารี) |
| 2026-11-19 | export native ทั้ง 9 ชิ้น (PyMateria 0.2.1) ได้ `.ydr` และ `.ytyp` หัวไฟล์ RSC7 ครบ, ytyp ขนาด 535-563 ไบต์ใกล้เคียงของ `1nfx_prop` เดิม, นำ `1nfx_goo_atm.ydr` กลับเข้า Sollumz ได้ 9754 tris + collision 2 ชิ้น + shader 2 ตัว + DDS 256x256 | ผ่าน (นอกเกม) |
| 2026-11-19 | `ycd_rsc7.py` คอมไพล์/ดีคอมไพล์ `.ycd` (RSC7 v46) ตรวจ round-trip กับไฟล์จริงทั้ง 4 ตัวใน `1nfx_prop/stream/` (`1nfx_airdrop`, `1nfx_blackout`, `1nfx_waterpipe`, `1nfx_pumpkin`) ได้ `xml_match=True` และนำเข้า Sollumz 2.9.1 ผ่านทุกไฟล์ | ผ่าน (นอกเกม) |
| 2026-11-19 | ชุด `1nfx_prop_extreme` V3 AAA + Animation 9 ชิ้น (`1024x1024` Cycles AO + `default_spec.sps` + 8 `.ycd` native + ตู้เซฟกลวงเปิดประตูโชว์ทอง/เงิน): `validate_prop.py` `fail=0 warn=0`, `export_prop.py --format native` `ok=9 fail=0` (26 ไฟล์ RSC7), round-trip `.ydr`/`.ycd`/`.ytyp` ผ่านใน Sollumz, `lint-resource.mjs` 0 error | ผ่าน (นอกเกม) |
| 2026-11-19 | **ผลทดสอบจริงในเกม FiveM (`1nfx_prop_extreme` V6.1):** โมเดลและแอนิเมชัน `.ycd` (เช่น ประตูตู้เซฟเปิด) ทำงานจริงในเกมที่ 550 FPS แต่ **ทุกชิ้นแสดงผลดำสนิท** ตรวจสอบด้วย PyMateria พบสาเหตุ 100% คือ `export_prop.py` ไม่ได้เปลี่ยนชื่อ `"UVMap"` เป็น `"UVMap 0"` และไม่ได้สร้าง `"Color 1"` `(255,255,255,255)` ทำให้ Sollumz 2.9 ตัด `TEXTURE0` และ `DIFFUSE` ออกจาก vertex buffer แก้ไขแล้วใน `export_prop.py` (`prepare_mesh_attributes` + `verify_native_ydr`), ถอด `stream/*.ydr` และ `stream/*.ycd` ออกจาก `files {}` ใน `fxmanifest.lua` เพื่อไม่ให้แคชซ้ำ, และเปลี่ยน `cl_main.lua` เป็น `lib.spawn.pointProp` + `SetModelAsNoLongerNeeded` + `RemoveAnimDict` บน `onExit`/`Clear`/`onResourceStop` เพื่อคืน memory ครบทุกครั้ง | แก้และตรวจไบนารีผ่านแล้ว (รอผู้ใช้ทดสอบในเกมรอบแก้สีและคืน memory) |
