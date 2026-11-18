# Bone Integrity & Streaming Memory Safety

เอกสารนี้เป็น **เกณฑ์บังคับสูงสุด (Mandatory Gate)** ของ `weapon-forge` เพื่อป้องกันปัญหา 2 อันดับแรกที่ทำให้เซิร์ฟเวอร์ FiveM รวนและไคลเอนต์ผู้เล่นแครช:
1. **Bone Bugs** — อาวุธบิดผิดมุม `~78°` ในมือ, โมเดลช่อง `Bottle` ไม่ติดมือ, จุดยอดยืดเป็นเส้นทะลุแมพไป `(0, 0, 0)`, เอฟเฟกต์เกาะกระดูกพ่นผิดทิศตามการแกว่งแขน, หรือส่ง `boneIndex = -1` เข้า native จนเกมแครช
2. **Client Memory Leaks & Pool Exhaustion** — โหลด `.ypt` / `.ydr` / `Kill.Prop` สะสมโดยไม่คืน RAM (`ERR_MEM_EMBEDDEDALLOC_ALLOC` / ถนนหาย), ทิ้ง looped PTFX handle ค้างจนโควตาเอฟเฟกต์ทั้งเกมดับ, หรือปล่อย Blender datablock ค้างระหว่างปั้นชุดใหญ่

ทุกสกินที่สร้างหรือแก้ไข **ต้องผ่านสัญญาทั้ง 3 ส่วนด้านล่างครบ 100%** ก่อนส่งงาน

---

## 1. สัญญาโครงกระดูก 3D และไฟล์ไบนารี `.ydr` (`crSkeletonData` & Skinning Contract)

### 1.1 ลำดับชั้นกระดูกและกฎ `Gun_Root` / `Gun_GripR` รายช่องอาวุธ

ระบบสกินอาวุธของ `[1nfx]` สวมโมเดลทุกช่องเป็น Component (`COMPONENT_SKIN_<SLOT>_<ID>`) เข้ากับ `<AttachBone>gun_root</AttachBone>` ของอาวุธฐาน ดังนั้น **ทุกช่องอาวุธรวมถึง `Bottle` ต้องมี Armature และกระดูก `Gun_Root` เสมอ** (ห้ามส่งออกเป็น static mesh ไร้ skeleton เด็ดขาด)

| ช่องอาวุธ (`slot`) | จำนวนกระดูก | ลำดับชั้นกระดูกบังคับ (`Parent -> Child`) | กฎเฉพาะช่อง |
| --- | ---: | --- | --- |
| `bottle`, `knife`, `machete`, `knuckle`, `bat` | **3** | `Gun_Root (0)` → `Gun_GripR (1)` → `Gun_Main_Bone (2)` | จุดยอดทั้งหมดผูกน้ำหนักเข้า `Gun_Main_Bone` (`idx = 2`) |
| `poolcue` | **4** | `Gun_Root (0)` → `Gun_GripR (1)` → `Gun_Main_Bone (2)` และ `Gun_Root (0)` → `Gun_GripL (3)` | `Gun_GripL` อยู่ที่ `(0, 0, 0.412707)` เพื่อให้มือซ้ายจับตรงก้านไม้คิว/หอก |
| `revolver` | **10** | `Gun_Root (0)` → `Gun_GripR (1)` → `Gun_Main_Bone (2)` → `gun_crane (3)` [→ `gun_cylinder (4)` → `Gun_VFX_Eject (5)`, `WAPClip (6)`], `Gun_Muzzle (7)`, `Gun_Trigger_Pr (8)`, `Gun_Hammer (9)` | ปากกระบอกชี้ `+X`, `Gun_Muzzle` อยู่ที่ `(0.246804, 0, 0.038900)` เพื่อยิงไฟปากกระบอกและวิถีกระสุนตรงแนวลำกล้อง |

**กฎเหล็ก 3 ข้อของเมทริกซ์กระดูกใน `.ydr`:**
1. **`Gun_Root` ต้องเป็น Identity ที่จุดกำเนิดโลกเสมอ**: `trans = (0, 0, 0)`, `rot = (0, 0, 0, 1)`, `scale = (1, 1, 1)`, `parent = -1`, `BoneTag = 0` ห้ามเลื่อน origin ของ `Gun_Root` เด็ดขาด
2. **`Gun_GripR` ห้ามมีค่าหมุนเป็น Identity `(0, 0, 0, 1)`**:
   - **Melee & Poolcue**: `Gun_GripR` ต้องมี `rot = (0.61895925, -0.10611998, 0.01775410, 0.77801865)`, `trans = (-0.045597, 0.002018, 0.012259)` และ `Gun_Main_Bone` ต้องมีค่าหมุนผกผัน `(-0.61895937, 0.10611984, -0.01775388, 0.77801860)`, `trans = (0.04245601, -0.019481, -0.007166)`
   - **Revolver**: `Gun_GripR` ต้องมี `rot = (0.6552223, -0.00313912, 0.03807334, 0.7544696)`, `trans = (-0.094846, -0.016669, -0.061423)` และ `Gun_Main_Bone` หมุนผกผัน `(-0.6552227, 0.00313903, -0.03807351, 0.7544692)`, `trans = (0.09881397, 0.05718302, -0.00352000)`
   - *เหตุผลเชิงวิศวกรรม:* การจับคู่นี้ทำให้ World Matrix และ `TransformationsInverted[2]` ของ `Gun_Main_Bone` ตัดกันกลับมาเป็น **Identity Matrix พอดี** หากเผลอใส่ `Gun_GripR.qw = 1.0` อาวุธจะบิดเอียงผิดมุม `~78°` ทันทีที่ผู้เล่นถือในมือ (`inspect-ydr.ps1` ตีเป็น `FAIL` ทันที)
3. **`TransformationsInverted` (ที่ `skel + 0x28`) ต้องมีคอลัมน์ `w = 0.0` ทุกแถว (`3x4` affine columns ในบล็อก `0x40` ไบต์)**: ค่าขยะในช่อง `w` ทำให้สกินยืดบิดเบี้ยวเป็นเศษโพลีกอนเต็มจอ

### 1.2 สูตรคำนวณ `BoneTag` 16-bit (`ElfHashUpperCase`)

GTA V **ไม่ได้ใช้ `joaat`** ในการแปลงชื่อกระดูกเป็น `BoneTag` แต่ใช้ `ElfHashUpperCase(name) % 0xFE8F + 0x170` (ยกเว้นกระดูกราก `Gun_Root` ที่มีค่าเป็น `0` เสมอ):

| ชื่อกระดูก (`crBoneData.Name`) | `BoneTag` (uint16) | Hex | ใช้ในช่อง |
| --- | ---: | --- | --- |
| `Gun_Root` | `0` | `0x0000` | ทุกช่อง (ต้องอยู่ใน `BoneHashTable` ที่ `idx=0` ด้วย) |
| `Gun_GripR` | `18308` | `0x4784` | ทุกช่อง |
| `Gun_Main_Bone` | `3360` | `0x0D20` | ทุกช่อง |
| `Gun_GripL` | `18302` | `0x477E` | `poolcue` |
| `gun_crane` | `18771` | `0x4953` | `revolver` |
| `gun_cylinder` | `3562` | `0x0DEA` | `revolver` |
| `Gun_VFX_Eject` | `28405` | `0x6EF5` | `revolver` |
| `WAPClip` | `1477` | `0x05C5` | `revolver` |
| `Gun_Muzzle` | `17833` | `0x45A9` | `revolver` |
| `Gun_Trigger_Pr` | `56099` | `0xDB23` | `revolver` |
| `Gun_Hammer` | `24730` | `0x609A` | `revolver` |

### 1.3 ป้องกันไคลเอนต์แครชใน `crSkeleton::Update()` (`ChildParentIndices` SIMD Lanes)

RAGE คำนวณเมทริกซ์กระดูกทีละ **4 คู่ขนานด้วยคำสั่ง SIMD** (`4 × (child_u16, parent_u16) = 8 uint16 = 16 bytes` ต่อระดับความลึกของต้นไม้กระดูก):
- พอยน์เตอร์ `ChildParentIndices` ที่ `skel + 0x40` ห้ามเป็น `NULL`
- จำนวนกระดูก `NumBones` ต้องเขียนที่ออฟเซ็ต **`skel + 0x5E`** (`uint16`)
- ฟิลด์ `ChildParentIndicesCount` ที่ `skel + 0x60` เก็บ **จำนวน `uint16` (`= จำนวนคู่ × 2`)** ซึ่งต้องหารด้วย `8` ลงตัวเสมอ (`16` สำหรับอาวุธ 3–4 กระดูก = 8 คู่; `40` สำหรับ `revolver` 10 กระดูก = 20 คู่ โดยซ้ำคู่สุดท้ายให้ครบเลน SIMD)
- ทุกคู่ `(child, parent)` ต้องอยู่ในช่วง `0 .. NumBones - 1` และตรงกับ `ParentIndices[child]` ทุกตัว หากเขียนจำนวนที่ `+0x60` เกินข้อมูลจริง `crSkeleton::Update()` จะอ่านล้นเข้าไปในตาราง `BoneHashTable` ถัดไปและเขียนเมทริกซ์ทับหน่วยความจำ heap จนเกมแครชทันทีที่สวมสกิน

### 1.4 สัญญา Mesh Skinning, Applied Transforms, Normals, Bounds & Blender RAM

1. **Applied Transforms (`loc=0, rot=0, scale=1`)**:
   - ทั้ง `Armature` และ `Mesh` ต้องมีความคลาดเคลื่อนของ `location` และ `rotation_euler` `< 1e-5` และ `scale` เท่ากับ `(1.0, 1.0, 1.0)` ก่อน bake และ export เสมอ
   - สเกลติดลบ (`negative scale`) ตอน mirror ชิ้นส่วนจะพลิกทิศ `normal` เข้าด้านใน ทำให้ผิวอาวุธแหว่งทะลุในเกม ต้องสั่ง `Apply All Transforms` แล้ว `Recalculate Outside` ทุกครั้ง
2. **`BlendWeights` & `BlendIndices` Normalized 100%**:
   - ในโครงจุดยอด 44 ไบต์ของอาวุธ (`Position float3` + `BlendWeights u8[4]` + `BlendIndices u8[4]` + `Normal float3` + `Colour u8[4]` + `TexCoord float2`), ค่า `BlendWeights` ทั้ง 4 ช่องต้องรวมกันได้ **`255` พอดี** ทุกจุดยอด (เช่น `(0, 0, 255, 0)` คู่กับ `BlendIndices = (0, 0, 2, 0)` สำหรับการผูกเข้า `Gun_Main_Bone`)
   - **ห้ามมีจุดยอดไร้กลุ่มน้ำหนัก (`0 unweighted vertices`)**: จุดยอดที่น้ำหนักรวมเป็น `0` จะถูกดึงกลับไปที่จุดกำเนิดโลก `(0, 0, 0)` กลายเป็นเส้นแหลมยืดยาวข้ามแผนที่
   - ทุกดัชนีใน `BlendIndices` ต้อง `< NumBones` และไม่เกินเพดาน skinning matrix palette ของ geometry chunk (แต่ละ chunk จำกัดสูงสุด `65,535` indices / `21,845` tris โดย `export_ydr.py` แบ่ง chunk อัตโนมัติ)
3. **ห้ามมี `NaN` หรือเวกเตอร์ความยาวศูนย์ใน `Normal` / `UV`**:
   - สามเหลี่ยมพื้นที่ศูนย์ (`degenerate triangles` จากการ boolean หรือ decimate หนัก) ทำให้ `loop.normal` เป็น `(0, 0, 0)` หรือ `NaN` ส่งผลให้แสงระเบิดเป็นจุดดำกะพริบบนจอ ต้องเชื่อมจุดซ้อน (`Merge by Distance 0.0001m`), ลบหน้าพื้นที่ศูนย์ และเช็ก `normal.length_squared > 1e-6` ก่อนเขียนบัฟเฟอร์เสมอ
4. **ความแม่นยำของ Bounding Box, Bounding Sphere และ `phBoundBox`**:
   - ต้องคำนวณ `bmin`, `bmax`, จุดศูนย์กลาง `bc` และรัศมีทรงกลม `br` ใหม่จากพิกัดจุดยอดจริงเสมอ (**ห้ามอ่าน `ob.bound_box` ใน Blender ทันทีหลังแก้ `bmesh`/`mesh.transform`** เพราะ Blender ยังไม่อัปเดต depsgraph) หากรัศมีแคบกว่าตัวอาวุธจริง เกมจะสั่งซ่อนอาวุธทันทีที่หันมุมกล้องเฉียง (`frustum culling bug`)
   - ใน `phBoundBox + 0x4C` ต้องเขียน `MaterialId` เป็นจำนวนเต็ม `uint32` (`55` = โลหะ หรือ `69` = ไม้) ห้ามเขียนค่า `float` ลงช่องนี้เด็ดขาด
5. **การกวาดล้าง Orphan Datablocks ใน Blender (ป้องกัน Blender กิน RAM ค้าง)**:
   - การลบ `bpy.data.objects` ในสคริปต์หรือผ่าน Blender MCP **ไม่ได้ลบ** `Mesh`, `Image`, `Material` หรือ `Armature` datablock ที่ผูกอยู่ เมื่อวนสร้างหรือเรนเดอร์หลายชิ้นในเซสชันเดียวต้องรันคำสั่งด้านล่างก่อนบันทึก `.blend` ทุกครั้ง:

```python
import bpy

for block_collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures):
    for block in list(block_collection):
        if block.users == 0:
            block_collection.remove(block)

bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
```

---

## 2. สัญญาการเกาะกระดูกฝั่ง FiveM Lua (`Ped BoneTag` vs `BoneIndex` Contract)

### 2.1 แยกแยะ `BoneTag` (16-bit ID) กับ `BoneIndex` (ดัชนีอาเรย์ `0 .. N-1`) ให้ขาด!

สาเหตุอันดับ 1 ที่ทำให้สคริปต์เอฟเฟกต์พังหรือทำให้ไคลเอนต์แครชเมื่อเจอร่างตัวละครแต่งพิเศษ (`addon ped`) คือการส่ง **`BoneTag` (`57005`)** เข้าฟังก์ชันที่ต้องการ **`BoneIndex` (`0 .. GetEntityBoneCount(ped)-1`)** หรือส่งค่า **`-1`** จากกระดูกที่หาไม่เจอเข้า native โดยไม่ตรวจเช็ก!

| Native ของ FiveM / GTA V | ชนิดค่ากระดูกที่รับ | วิธีเตรียมค่าที่ถูกต้อง และอาการพังเมื่อส่งผิด |
| --- | --- | --- |
| `StartParticleFxLoopedOnEntityBone` | **`boneIndex`** (`0 .. N-1`) | แปลงด้วย `GetPedBoneIndex(ped, boneTag)` หรือ `GetEntityBoneIndexByName(ent, name)` แล้วตรวจ `>= 0 and < GetEntityBoneCount(ent)` (ถ้าส่ง `57005` หรือ `-1` จะอ่านเมทริกซ์เกินขอบเขต เอฟเฟกต์หลุดไป `(0,0,0)`) |
| `StartParticleFxNonLoopedOnEntityBone` | **`boneIndex`** (`0 .. N-1`) | แปลงด้วย `GetEntityBoneIndexByName(ent, name)` แล้วตรวจ `>= 0 and < GetEntityBoneCount(ent)` |
| `AttachEntityToEntity` | **`boneIndex`** (`0 .. N-1`) | แปลงด้วย `GetPedBoneIndex` / `GetEntityBoneIndexByName` แล้วตรวจ `>= 0` (ห้ามส่ง `-1` เด็ดขาด) |
| `GetWorldPositionOfEntityBone` | **`boneIndex`** (`0 .. N-1`) | แปลงด้วย `GetPedBoneIndex` / `GetEntityBoneIndexByName` แล้วตรวจ `>= 0` (ถ้าส่ง `-1` จะคืน `(0.0, 0.0, 0.0)`) |
| `StartParticleFxLoopedOnPedBone` | **`boneTag`** (`uint16` ID) | ส่งเลข `boneTag` ดิบ (`57005`, `28422`, `31086`) **ห้ามส่ง `boneIndex`** (ถ้าส่ง `~71` เอนจินจะไปหา tag `71` ที่ไม่มีอยู่จริง) แต่ต้องตรวจ `GetPedBoneIndex(ped, boneTag) ~= -1` ก่อนเรียกเสมอ! |
| `StartParticleFxNonLoopedOnPedBone` | **`boneTag`** (`uint16` ID) | ส่งเลข `boneTag` ดิบ (`57005`, `28422`, `31086`, `24818`) หลังตรวจ `GetPedBoneIndex(ped, boneTag) ~= -1` |
| `GetPedBoneCoords` | **`boneTag`** (`uint16` ID) | ส่งเลข `boneTag` ดิบ (ถ้าส่ง `boneIndex` จะคืนพิกัดกึ่งกลางลำตัวแทนกระดูก!) |
| `StartNetworkedParticleFxNonLoopedOnPedBone` | **`boneTag`** *(ห้ามใช้ในลูปสกิน!)* | กระจายแพ็กเก็ต OneSync `ptFxEvent` ไปหาผู้เล่นทุกคนในเซิร์ฟเวอร์ เสี่ยงโดนเตะ rate-limit ให้ใช้ local PTFX คู่กับ statebag เสมอ |

**ตารางเลข `BoneTag` มาตรฐานบนตัวละคร (`mp_m_freemode_01` / `mp_f_freemode_01`):**
- `57005` (`SKEL_R_Hand`) — มือขวาหลัก (ปลอดภัยที่สุด มีในเกือบทุก custom ped)
- `28422` (`PH_R_Hand`) — จุดถือของในมือขวา (ค่าเริ่มต้นของ `Hold` ใน `1nfx_weaponskin` แต่อาจคืน `-1` บนบาง custom ped จึงต้องมี fallback ไป `57005` เสมอ!)
- `18905` (`SKEL_L_Hand`) / `60309` (`PH_L_Hand`) — มือซ้าย
- `31086` (`SKEL_Head`) / `12844` (`IK_Head`) — ศีรษะเหยื่อสำหรับ `Hit.Effect`
- `24818` (`SKEL_Spine3` อก) / `24816` (`SKEL_Spine1` ลำตัว) / `0` (Root Entity ไม่ระบุกระดูก)

### 2.2 รูปแบบโค้ดป้องกัน `boneIndex == -1` และ `DoesEntityExist` (Mandatory Guard Pattern)

ห้ามส่งผลลัพธ์จาก `GetPedBoneIndex` หรือ `GetEntityBoneIndexByName` เข้า native ตรง ๆ โดยไม่ผ่านตัวกรองด้านล่าง:

```lua
function WeaponSkin:ResolveSafePedBone(ped, requestedBoneTag, fallbackBoneTag)
    if not ped or ped == 0 or not DoesEntityExist(ped) or not IsEntityAPed(ped) then
        return nil, nil
    end
    local boneCount = GetEntityBoneCount(ped)
    if type(boneCount) ~= "number" or boneCount <= 0 then
        return nil, nil
    end
    local tag = math.floor(tonumber(requestedBoneTag) or 0)
    if tag > 0 then
        local idx = GetPedBoneIndex(ped, tag)
        if type(idx) == "number" and idx >= 0 and idx < boneCount then
            return idx, tag
        end
    end
    local fbTag = math.floor(tonumber(fallbackBoneTag) or 57005)
    if fbTag > 0 and fbTag ~= tag then
        local fbIdx = GetPedBoneIndex(ped, fbTag)
        if type(fbIdx) == "number" and fbIdx >= 0 and fbIdx < boneCount then
            return fbIdx, fbTag
        end
    end
    return 0, 0
end

function WeaponSkin:ResolveSafeWeaponBone(weaponEntity, boneName)
    if not weaponEntity or weaponEntity == 0 or not DoesEntityExist(weaponEntity) then
        return nil
    end
    local boneCount = GetEntityBoneCount(weaponEntity)
    if type(boneCount) ~= "number" or boneCount <= 0 then
        return 0
    end
    if type(boneName) == "string" and boneName ~= "" then
        local idx = GetEntityBoneIndexByName(weaponEntity, boneName)
        if type(idx) == "number" and idx >= 0 and idx < boneCount then
            return idx
        end
    end
    return 0
end
```

- หาก `ResolveSafePedBone` คืน `boneIndex == 0` (ไม่พบทั้งกระดูกที่ขอและ `57005`) ให้สลับไปเรียก **`StartParticleFxLoopedOnEntity`** หรือ **`StartParticleFxNonLoopedOnEntity`** บนตัว `ped` โดยตรง ห้ามเรียก `*OnEntityBone` ด้วย `-1` เด็ดขาด

### 2.3 แกนหมุนกระดูกกับฟิสิกส์ของ Particle (`World Gravity` vs `Local Bone Axes`)

กระดูกมือ (`28422` / `57005`) และกระดูกอาวุธ (`Gun_Root` / `Gun_Muzzle`) หมุนพลิกเกือบ `180°` ระหว่างท่ายืนถือ ท่าวิ่ง และท่าฟัน:
- **ห้ามใช้ `dir: "up"`, `dir: "down"` หรือเวกเตอร์ความเร็วแกนเดียวบน `Hold` และ `Hit` ที่เกาะกระดูก** เพราะทิศทางความเร็วของ emitter หมุนตาม local matrix ของกระดูก ทำให้ตอนทิ้งแขนลง เปลวไฟหรือชิ้นเลโก้จะพุ่งเฉียงออกข้างลำตัวเหมือนท่อรั่ว!
- **วิธีที่ถูกต้อง**:
  1. ปล่อยอนุภาคจากจุดศูนย์กลางแคบ ๆ รอบมือ (`shape: "sphere"`, `radius: 0.04–0.12`, `dir: "out"`, ความเร็วต้นต่ำ `0.05–0.35 m/s` หรือ `speed: 0` สำหรับ `ribbon_trail`)
  2. ใช้ **`gravity` ติดลบ** (ลอยขึ้นฟ้า) หรือ **`gravity` บวก / `accelKeys`** (ร่วงลงพื้นหรือกระเด้งแล้วตก) เนื่องจาก `Acceleration.ReferenceSpace = 0` ใน RAGE ทำงานใน **แกนโลก (`World Z`) เสมอ** ไม่ว่าข้อมือจะบิดไปมุมไหน
  3. ใช้ `align: "camera"` สำหรับสไปรต์ประกาย/ชิ้นส่วนหมุน และ `align: "ground"` สำหรับวงแหวนติดพื้น

### 2.4 กฎ `<AttachBone>gun_root</AttachBone>` และเพดาน 12 Components ใน `.meta`

- ใน `weapon_core/data/weapons/weapon<slot>.meta` (และ `weapons_revolver_mk2.meta` คู่กันเสมอสำหรับ `Revolver`) ต้องใส่ `<Item><Name>COMPONENT_SKIN_...</Name></Item>` ภายในบล็อกที่มี `<AttachBone>gun_root</AttachBone>` เท่านั้น (**ห้าม**ใส่ในบล็อก `WAPClip` หรือ `Gun_GripR`)
- เอนจิน RAGE จำกัดรายการ `<Components>` ต่อหนึ่งบล็อก `<AttachPoints><Item>` ไว้ไม่เกิน **12 ตัว** หากบล็อกเดิมเต็ม 12 ตัวแล้ว ต้องเปิดบล็อก `<Item><AttachBone>gun_root</AttachBone>...</Item>` อันใหม่ต่อท้าย มิฉะนั้นสกินลำดับที่ 13 เป็นต้นไปจะไม่แสดงโมเดลในเกม

---

## 3. สัญญาการคืนหน่วยความจำ Streaming & PTFX (`Memory Release & Pool Budget Contract`)

### 3.1 วงจรชีวิต `.ypt` Dictionary (`RequestNamedPtfxAsset` → `RemoveNamedPtfxAsset`)

การเรียก `RequestNamedPtfxAsset(dict)` โดยไม่ปล่อยคืน (หรือการปักหมุด `pinned[dict] = true` ค้างตลอดเซสชันหลังเล่น non-looped Hit/Kill เพียงครั้งเดียว) ทำให้เท็กซ์เจอร์ใน `.ypt` ทุกสกินที่ผู้เล่นเดินผ่านสะสมค้างในหน่วยความจำกราฟิกของ GTA V จนเกิดอาการแมพแหว่ง (`texture loss`) หรือแครช `ERR_MEM_EMBEDDEDALLOC_ALLOC`

**กฎบังคับ 4 ข้อของการโหลดและปล่อย `.ypt`:**
1. **Bounded Wait Timeout (`2000–8000 ms`) + Failure Cooldown**: ห้ามเขียน `while not HasNamedPtfxAssetLoaded(dict) do Wait(0) end` แบบไร้เส้นตายเด็ดขาด ต้องตรวจเวลาหมดอายุพร้อม `Wait(25)` และเว้นระยะ retry (`30 s`) เมื่อไฟล์ไม่มีอยู่จริง
2. **กฎเหล็ก Same-Tick `UseParticleFxAssetNextCall(dict)`**:
   - ต้องเรียก `UseParticleFxAssetNextCall(dict)` ในบรรทัดก่อนหน้า `StartParticleFx*` **ภายในเฟรม (tick) เดียวกันเสมอ**
   - **ห้าม**มี `Wait(...)`, callback ข้ามเฟรม หรือการเรียกฟังก์ชันที่อาจ yield คั่นระหว่าง `UseParticleFxAssetNextCall` กับ `StartParticleFx*` เพราะสคริปต์อื่นในไคลเอนต์สามารถเปลี่ยน active PTFX dictionary ในเฟรมถัดไปได้ทันที
3. **ห้าม Pin Non-Looped Dictionary ค้างถาวร (`ParticleActiveUntil` Tail-Expiry Pattern)**:
   - สาเหตุที่สคริปต์เก่าใส่ `ParticlePinnedAssets[dict] = true` ตลอดกาลคือกลัวว่า `RemoveNamedPtfxAsset(dict)` จะถูกรันขณะที่หางอนุภาคของ `Hit`/`Kill` ยังลอยค้างกลางอากาศ (ซึ่งจะทำให้สไปรต์กลายเป็นสี่เหลี่ยมสีขาว) แต่การ pin แบบ boolean ถาวรทำให้ทุก `.ypt` ที่เคยเล่นแม้ครั้งเดียวรั่วค้างตลอดเซสชันและไม่ถูกปล่อยแม้ตอน `onResourceStop`!
   - **วิธีแก้ที่ถูกต้อง**: เก็บเวลาหมดอายุของหางอนุภาค (`ParticleActiveUntil[dict] = math.max(..., GetGameTimer() + 8500)`) ซึ่งคลุมอายุสูงสุดของ `Kill` (`~2.3 s` + หางอนุภาค) อย่างปลอดภัย พ้น `8.5 s` แล้วจึงอนุญาตให้ตัวกวาด idle สั่ง `RemoveNamedPtfxAsset(dict)` ได้ตามปกติ:

```lua
if data.isLoop ~= true then
    if not state.ParticleActiveUntil then
        state.ParticleActiveUntil = {}
    end
    state.ParticleActiveUntil[dict] = math.max(
        state.ParticleActiveUntil[dict] or 0,
        GetGameTimer() + 8500
    )
end
```

4. **Ref-Counted / Idle Garbage Collection (`RemoveNamedPtfxAsset`)**:
   - กวาดเช็กทุก `1000–5000 ms`: หาก `dict` ไม่มี active looped handle ใดอ้างถึง, ไม่มีงาน pending กำลังโหลด, `GetGameTimer() >= (state.ParticleActiveUntil[dict] or 0)` และไม่ได้ถูกใช้งานเกิน `15–30 s` ต้องเรียก **`RemoveNamedPtfxAsset(dict)`** และลบออกจากตารางสถานะทันที (และใน `onResourceStop` ต้องเรียก `RemoveNamedPtfxAsset(dict)` กับ **ทุก** `dict` ใน `ParticleAssets` แบบไม่มีข้อยกเว้น!)

### 3.2 การจัดการ Looped PTFX Handles (`StopParticleFxLooped` + `RemoveParticleFx`)

- ตรวจค่าคืนกลับจาก `StartParticleFxLooped*` ทุกครั้งว่า `type(handle) == "number" and handle > 0`
- จำกัดจำนวน looped handles รวมทั้งสคริปต์ (`particle_max_handles <= 20`) หากเต็มให้สั่งลบเอฟเฟกต์ชั่วคราวตัวที่เก่าที่สุดออกก่อนเสมอ
- เมื่อสั่งปิดเอฟเฟกต์ ต้องเรียกครบทั้ง **หยุดปล่อย** และ **ถอดออกจากพูล**:

```lua
function WeaponSkin:ReleaseParticleHandle(handle)
    if type(handle) == "number" and handle > 0 then
        if DoesParticleFxLoopedExist(handle) then
            StopParticleFxLooped(handle, false)
            RemoveParticleFx(handle, false)
        end
    end
    self.PlayerState.ParticleHandles[handle] = nil
end
```

### 3.3 การคืนหน่วยความจำโมเดล 3D (`RequestModel`), `WeaponAsset`, `AnimDict` และ `StreamedTxd`

ทุก native ที่โหลดทรัพยากรเข้า RAM ต้องมีคู่ปล่อยคืนใน **ทุกเส้นทางของโค้ด (รวมกรณี timeout, ยกเลิกกลางคัน, หรือเกิด error)**:

| Native ขาโหลด | Native ขาปล่อยคืน (บังคับ!) | จังหวะที่ต้องเรียกปล่อยคืน |
| --- | --- | --- |
| `RequestNamedPtfxAsset(dict)` | `RemoveNamedPtfxAsset(dict)` | เมื่อไม่มี looped handle / พ้นอายุ non-looped + idle timeout, และใน `onResourceStop` |
| `StartParticleFxLooped*(...)` | `StopParticleFxLooped(h, false)` + `RemoveParticleFx(h, false)` | เมื่อเปลี่ยนอาวุธ, เปลี่ยนสกิน, เปลี่ยนร่าง ped, ตาย, หมด `duration`, และใน `onResourceStop` |
| `RequestModel(model)` | `SetModelAsNoLongerNeeded(model)` | **ทันที** หลัง `CreateObjectNoOffset` / `GiveWeaponComponentToPed` เสร็จ หรือทันทีที่ timeout/ยกเลิก |
| `CreateObject` / `CreateObjectNoOffset` | `if DoesEntityExist(obj) then DeleteEntity(obj) end` | เมื่อครบ `duration` ของ `Kill.Prop`, เปลี่ยนฉาก preview, เป้าหมายหาย, และใน `onResourceStop` |
| `RequestWeaponAsset(hash, 31, 0)` | `RemoveWeaponAsset(hash)` | ทันทีที่สวม component เสร็จหรือยกเลิกใน `FinishApply` / `Cancel` / `onResourceStop` |
| `RequestAnimDict(dict)` | `RemoveAnimDict(dict)` | เมื่อไม่มี `Kill.Prop` ตัวใดกำลังเล่นแอนิเมชันจาก `dict` นั้นอยู่ และใน `onResourceStop` |
| `RequestStreamedTextureDict(txd, false)` | `SetStreamedTextureDictAsNoLongerNeeded(txd)` | ทันทีที่ปิดหน้าต่าง/เลิกวาดสไปรต์ และใน `onResourceStop` |

### 3.4 ห้าจุดเปลี่ยนสถานะที่ต้องกวาดล้างสถานะครบ 100% (`5 Mandatory Teardown Hooks`)

สคริปต์สกินอาวุธต้องผูกการล้าง handle และปล่อย asset ไว้ครบทั้ง 5 เหตุการณ์นี้:
1. **เก็บหรือสลับอาวุธ (`Weapon Switch / Holster` → `WEAPON_UNARMED`)**: หยุด `Hold` ของอาวุธเดิมทันที
2. **สลับสกิน / ถอดสกิน / ปิดเมนู Preview (`Skin Change / Unequip / Preview Exit`)**: เพิ่มเลข `Generation` เพื่อยกเลิก thread ที่กำลังรอ `Wait()` อยู่ทั้งหมด และลบ looped handles + preview props ทันที
3. **เปลี่ยนร่างตัวละคร (`Ped Entity Change` — `cache.ped ~= lastPed`)**: เมื่อผู้เล่นโหลดสกินเสื้อผ้าหรือสลับร่าง `ped` เก่าจะถูกลบแต่ handle ที่ผูกในตาราง Lua อาจค้าง ต้องสั่ง `StopHoldParticles(lastPed)` ทันทีที่ตรวจพบว่า `ped` เปลี่ยนตัว
4. **ตัวละครตายหรือเกิดใหม่ (`IsEntityDead(ped)` / Respawn)**: หยุด `Hold` บนผู้ตายทันที และตั้งเพดานอายุให้เอฟเฟกต์ `Kill` / `Kill.Prop` ลบตัวเองเสมอ
5. **หยุดหรือรีสตาร์ต Resource (`onResourceStop`)**:

```lua
AddEventHandler("onResourceStop", function(resourceName)
    if resourceName ~= GetCurrentResourceName() then
        return
    end
    WeaponSkin.PlayerState.Stopping = true
    WeaponSkin:ClearParticles()
    if WeaponSkin.PropsModule then
        WeaponSkin.PropsModule:Cleanup()
    end
    if WeaponSkin.Appearance then
        WeaponSkin.Appearance:Destroy()
    end
    for dict in pairs(WeaponSkin.PlayerState.ParticleAssets or {}) do
        RemoveNamedPtfxAsset(dict)
    end
    WeaponSkin.PlayerState.ParticleAssets = {}
    WeaponSkin.PlayerState.ParticlePinnedAssets = {}
    WeaponSkin.PlayerState.ParticleActiveUntil = {}
end)
```

### 3.5 กับดักหน่วยความจำและเธรดค้าง 6 รูปแบบที่พบจริงจากการผ่าสคริปต์ (`Field Anti-Patterns`)

จากการตรวจสอบสคริปต์ภายนอกกว่า 3,700 ไฟล์ (`ms`, `xdd`, `sc`) และโค้ดระบบจริง ห้ามเขียนแพตเทิร์นเหล่านี้เด็ดขาด:

1. **ลูปรอโหลดแบบไร้เส้นตาย (`while not HasNamedPtfxAssetLoaded(dict) do Wait(0) end`):** ถ้าพิมพ์ชื่อ `dict` ผิดหรือไฟล์สตรีมช้า เธรดไคลเอนต์จะค้างถาวร ต้องมีเส้นตาย `3000–8000 ms` + `Stopping` check + cooldown `30 s` เสมอ
2. **`UseParticleFxAssetNextCall` คั่นด้วย `Wait()`:** `UseParticleFxAssetNextCall` ตั้งค่า global state ต่อเฟรมเท่านั้น หากมี `Wait(0)` หรือ async call คั่นก่อน `StartParticleFx*` เอนจินจะดีดกลับไปใช้ `"core"` หรือแย่ง `dict` ของสคริปต์อื่น
3. **วนลูปสร้างวงแหวนด้วย `StartParticleFxLooped*` หลายสิบตัว (`Ring-Loop Handle Multiplication`):** พบสคริปต์ภายนอกวน `for i = 1, 36` ซ้อน 4 ชั้น = **144–400+ handles ต่อผู้เล่น 1 คน** จนพูล PTFX ของ GTA V เต็มและไคลเอนต์แครช การเรียงอนุภาคเป็นวงกลมต้องทำใน `.ypt` ด้วย `shape: "cylinder"` (`radiusInner` ใกล้ `radius`) ซึ่งกินเพียง **1 handle**!
4. **ยิง `StartNetworkedParticleFx*` ในลูปไคลเอนต์:** ถล่ม OneSync `ptFxEvent` ไปทั้งเซิร์ฟเวอร์จนผู้เล่นโดนเตะ rate-limit ให้ใช้ local PTFX ขับด้วย statebag หรือ `CEventNetworkEntityDamage` เสมอ
5. **`RequestModel` / `RequestAnimDict` รั่วใน Fast-Path, Remote Ped และ Cancellation Race:**
   - เมื่อเรียก `RequestModel(skinModel)` เพื่อโหลดสกินอาวุธของผู้เล่นข้างเคียง (`EnsureRemoteSkinModel`) หรือโหลดล่วงหน้าก่อน `Apply` หากเข้า fast-path (`HasPedGotWeaponComponent` เป็นจริงอยู่แล้ว) หรือ `lib.requestModel` เกิด timeout ต้องตามเก็บ `SetModelAsNoLongerNeeded(skinModel)` ทุกเส้นทาง!
   - เมื่อรอ `lib.requestAnimDict(animDict, 1000)` แบบ async สำหรับ `Kill.Prop` หากผู้เล่นกดล้างฉาก (`generation ~= self.Generation`) ระหว่างรอ ต้องสั่ง `RemoveAnimDict(animDict)` ทันทีที่ฟังก์ชันโหลดเสร็จ
6. **กับดักเท็กซ์เจอร์ขยะ 4K และ `A8R8G8B8` ในไฟล์ `.ypt`:**
   - พบไฟล์จริง (`spakeffect3.ypt`) ที่มีเอฟเฟกต์ประกายไฟเพียง `8 KB` แต่ฝังเท็กซ์เจอร์ `4096×4096 DXT5` ที่ไม่มี emitter ใดเรียกใช้ ทำให้เสียหน้าหน่วยความจำ `gfx` ไปฟรี ๆ ถึง **`32 MB` (`0x2000000`)**!
   - พบไฟล์ตระกูล `xdd` ฝังภาพไม่บีบอัด `A8R8G8B8` (ใหญ่กว่า `DXT5` 4 เท่า), ขนาดไม่ใช่กำลังสอง (`300×300`, `500×500`, `1256×1256`), เปลี่ยนชื่อไฟล์ `.ypt` โดยไม่แก้ `DICT` ข้างใน และตั้งชื่อทับ dictionary มาตรฐานของเกม (`scr_*`, `cut_*`, `des_*`) จนเอฟเฟกต์ระเบิดและคัตซีนทั้งเซิร์ฟเวอร์เพี้ยน

### 3.6 งบประมาณหน่วยความจำของไฟล์สตรีม (`.ydr`, `.ytd`, `.ypt` Budgets)

| ไฟล์ / ระบบ | เกณฑ์ปลอดภัย (Target) | เพดานห้ามเกิน (Hard Cap) | ข้อผิดพลาดร้ายแรงที่ห้ามเกิด |
| --- | --- | --- | --- |
| **โมเดลอาวุธ (`.ydr`)** | `4,500–22,000 tris` (`0.6–1.8 MB`) | `30,000 tris` (`4.0 MB`) | โมเดล AI ดิบ `> 50k tris`, ปุ่มเลโก้ถี่รอบก้าน `37k tris`, ไม่มี skeleton, หรือ `ChildParentIndices` ผิดขนาด |
| **`Kill.Prop` 3D (`.ydr`)** | `150–2,500 tris` | `4,000 tris`, พร้อมกัน `<= 12` ชิ้น | ทิ้ง `CreateObject` ค้างหลังจบเอฟเฟกต์ หรือไม่ปลด `SetModelAsNoLongerNeeded` |
| **เท็กซ์เจอร์อาวุธ (`.ytd` / Embedded)** | `1024×1024` **DXT5** + mipmaps ครบ (`~1.33 MB` ดิบ) | `2048×2048` DXT1/DXT5 (`<= 5.5 MB`) | ไฟล์ `.ytd` เปล่า `66–257 bytes` (`texCount = 0`), ภาพขนาดไม่ใช่กำลังสอง (NPOT), ไม่มี mipmaps, หรือ `A8R8G8B8` ขนาดใหญ่ |
| **ไฟล์ Particle (`.ypt`)** | `80–650 KB` (DXT5 POT sheets `128–512 px` + mips ครบ) | `1.2 MB`, `<= 7 layers` ต่อ effect (`0` จาก `1,498` ไฟล์จริงที่เกิน 7) | ชื่อ `DICT` ข้างในไม่ตรงชื่อไฟล์ `.ypt`, ชน prefix เกม (`scr_*`, `cut_*`, `des_*`), มี orphan texture 4K ค้าง หรือใช้ `A8R8G8B8` |
| **อนุภาคมีชีวิตพร้อมกัน (`Active Alive`)** | Hold `<= 35`, Hit `<= 55`, Kill `<= 120` | Hold `<= 60`, Hit `<= 80`, Kill `<= 160` | ตั้ง `rate > 150/s` หรือ `burst > 100` คู่กับ `life` ยาวบน `Hold` จนพูลอนุภาคกลางของ GTA V เต็มในไฟต์ 10v10 |

---

## 4. รายการตรวจรับก่อนส่งงาน (Mandatory Pre-Ship Gate)

- [ ] **Blender**: รัน `validate_model.py` ผ่าน `RESULT fail=0` ทุกชิ้น (ไม่มี unapplied transform, ครบทุก bone ของช่อง, ไม่มี unweighted vertices, รูปเท็กซ์เจอร์เป็นกำลังสอง, ล้าง orphan datablocks แล้ว)
- [ ] **Binary `.ydr` / `.ytd`**: รัน `scripts/inspect-ydr.ps1` ผ่าน `RESULT fail=0` ทั้งไฟล์หลักและ `_hi.ydr` (`Gun_GripR.qw != 1.0`, `ChildParentIndices` หาร 8 ลงตัว, `BoneTag` ตรงตาราง `ElfHashUpperCase`, `.ytd` มี `texCount >= 1` พร้อม DXT5 mipmaps)
- [ ] **Binary `.ypt`**: รัน `scripts/ptfx/ptfx.ps1 lint` ได้ `RESULT ok` (`0 ERROR`, `0 unexplained WARN`, `<= 7 layers`, ใช้ `gravity` โลกแทน `dir: "up"` บนกระดูกมือ, งบ `alive` ไม่เกินเพดาน)
- [ ] **Client Lua**: ทุกจุดเกาะกระดูกตรวจ `DoesEntityExist` + `boneIndex ~= -1` พร้อม fallback, `UseParticleFxAssetNextCall` อยู่ติดกับ `StartParticleFx*` ใน tick เดียวกัน, ไม่ pin non-looped `.ypt` ค้างถาวร, และปล่อยคืนครบทั้ง `RemoveNamedPtfxAsset`, `StopParticleFxLooped` + `RemoveParticleFx`, `SetModelAsNoLongerNeeded`, `DeleteEntity`, `RemoveAnimDict`, `RemoveWeaponAsset` ในทั้ง 5 จุดเปลี่ยนสถานะรวมถึง `onResourceStop`
- [ ] **System Check**: รัน `scripts/check-skin.ps1 -SkinType <SkinType>` ผ่าน `RESULT fail=0`
