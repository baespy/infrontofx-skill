# Integration

## ไฟล์ที่ต้องมีในเกม

| ไฟล์ | มาจาก |
| --- | --- |
| `<id>.ydr` | Sollumz export (mesh + collision แบบ embedded) |
| `<set>_txd.ytd` หรือ `<id>.ytd` | texture palette หรือ atlas (DXT1/DXT5) |
| `<set>.ytyp` หรือ `<id>.ytyp` | archetype ของทุกชิ้นในชุด (`lodDist`, `textureDictionary`) |
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

data_file "DLC_ITYP_REQUEST" "stream/1nfx_goo.ytyp"
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
| - | export ผ่าน Sollumz และโหลดในเกม | ยังไม่ได้ทดสอบ |
