# VFX & Weapon Field Study

เอกสารนี้สรุปเทคนิคเชิงวิศวกรรมที่สกัดจากการผ่าไฟล์จริงของชุดอาวุธและแพ็กเอฟเฟกต์ขนาดใหญ่ (`.ypt` ที่เปิดอ่านได้รวม **`254` dictionaries / `1,498` effects / `2,923` particle rules**, สคริปต์ Lua กว่า `3,724` ไฟล์, โมเดล `.ydr`/`.ytd`/`.ytyp`/`.ycd` กว่า `240` ชิ้น และระบบเล่นเอฟเฟกต์ใน `1nfx_weaponskin` โดยไม่แตะไฟล์ `.fxap`) เพื่อนำสูตรจังหวะ เส้นโค้งคีย์เฟรม โครงสร้าง Shader และการผูก Prop 3D มาสร้างงานต้นฉบับของเราเองอย่างปลอดภัยต่อหน่วยความจำไคลเอนต์

---

## 1. สถาปัตยกรรมสกินอาวุธระดับพรีเมียม (4 ชั้นประสานกัน)

ชุดอาวุธที่ดูมีชีวิตและมีราคาแพงในเกมไม่ได้พึ่งแค่โมเดลหรือ particle อย่างใดอย่างหนึ่ง แต่แบ่งหน้าที่เป็น 4 ชั้นชัดเจน:

| ชั้น | ไฟล์ | หน้าที่หลัก |
| --- | --- | --- |
| **1. ตัวอาวุธหลัก** | `w_me_<id>_<slot>.ydr` + `.ytd` | รูปทรงหลัก วัสดุ PBR (`normal_spec`) + ร่องเรืองแสง (`normal_spec_emissive`) หรือครอบแก้วใส (`glass`) |
| **2. เปลือกพลังงาน / ชิ้นส่วนขยับบนอาวุธ** | Mesh ชั้นนอกใน `.ydr` หรือ `.ytyp` + `clip@<model>.ycd` | เลื่อนแถบแสง UV รอบใบมีด (`emissive_additive_uv_alpha`) หรือหมุนวงแหวน/ปีกบนตัวอาวุธอัตโนมัติ |
| **3. Particle 3 จังหวะ (`Hold` / `Hit` / `Kill`)** | `<id>_fx.ypt` (สร้างด้วย `ptfx.ps1 build`) | เส้นริบบิ้นตามมือ ประกายระยิบ รอยฟัน ตราเวทเด้งเปิด โคมลอย และพายุกลีบจังหวะสอง |
| **4. 3D Finisher Prop & Screen/Sound** | `Kill.Prop` (`.ydr` โพลีต่ำ + `.ycd`) + `.png`/`.wav` | เสาดาบยักษ์ ผลึกคริสตัล โลงศพ หรือวงเวท 3D ผุดขึ้น ณ จุดตาย พร้อมภาพขอบจอและเสียงสังเคราะห์แยกตี/ฆ่า |

---

## 2. หกสูตรคีย์เฟรม Particle (`.ypt`) ที่ยกระดับงานให้ดูแพง

สูตรทั้งหมดด้านล่างถูกเพิ่มเข้าตัวสร้าง `scripts/ptfx/` เรียบร้อยแล้ว สามารถเรียกใช้ผ่าน `use` ใน Design JSON หรือเริ่มจากธีมใหม่ (`lantern`, `butterfly`, `velvet`, `pirate`, `spooky`, `sweet`) ได้ทันที

### 2.1 ดาวกะพริบหลายจังหวะในอายุเดียว (`twinkle_glints`)
แทนที่จะปล่อยอนุภาคถี่ ๆ ซึ่งเปลืองงบ `alive` ให้ตั้งอายุอนุภาคยาวขึ้น (`1.1–1.7 s`) แล้วบังคับ `alphaKeys` ให้สว่าง-หรี่สลับกัน 3 รอบในหนึ่งชีวิต:

```json
{
  "use": "twinkle_glints",
  "color": "primary",
  "color2": "accent",
  "rate": 6,
  "alphaKeys": [[0, 0], [0.06, 1], [0.22, 1], [0.27, 0.08], [0.36, 0.08], [0.42, 1], [0.58, 1], [0.64, 0.1], [0.73, 0.1], [0.79, 0.95], [0.9, 0.85], [1, 0]]
}
```

### 2.2 แสงเทียนไหวในวงแหวนกลวง (`lantern_float` + `emissiveKeys`)
ใช้กับโคมลอย วิญญาณ หรือลูกไฟศักดิ์สิทธิ์ที่ลอยล้อมศพโดยไม่บังตัวละครตรงกลาง:
- เกิดในทรงกระบอกกลวง (`shape: "cylinder"`, `radius: 1.85`, `inner: 1.15`) ทำให้ตรงกลางโปร่งโล่ง
- ใช้คีย์ใหม่ `emissiveKeys` สั่นค่า `EmissiveIntensityKFP` ขึ้นลงเหมือนเปลวเทียนต้องลม:

```json
{
  "use": "lantern_float",
  "texture": "lantern",
  "color": "#ffd478",
  "emissiveKeys": [[0, 3.2], [0.22, 4.6], [0.45, 3.3], [0.7, 4.5], [0.88, 3.5], [1, 0]]
}
```

### 2.3 เอฟเฟกต์จังหวะสองแบบซ่อนตัว (`delayed_petal_burst` + `accelKeys`)
ใน `.ypt` แบบ `one-shot` หากต้องการให้ตราบนพื้นบานออกมาก่อน (`0.0–1.2 s`) แล้วค่อยมีพายุกลีบดอกไม้หรือเศษวิญญาณพุ่งสวนขึ้นฟ้าในช่วงครึ่งหลัง โดยไม่ต้องแยกเป็น 2 effect ใน Lua:
- ปล่อยอนุภาคตั้งแต่ `t = 0` แต่กด `alphaKeys` เป็น `0` จนถึง `t = 0.56`
- ใช้คีย์ใหม่ `accelKeys` ให้ความเร่งเป็น `0` ในช่วงแรก แล้วเปิดแรงลมยกตัวขึ้นพร้อมกับดีด `alpha` ขึ้นที่ `t = 0.58`:

```json
{
  "use": "delayed_petal_burst",
  "texture": "petal",
  "color": "#ff9ec6",
  "alphaKeys": [[0, 0], [0.56, 0], [0.62, 0.95], [0.88, 0.85], [1, 0]],
  "accelKeys": [[0, 0, 0, 0], [0.56, 0, 0, 0], [0.58, 0.25, 0.25, 1.35], [1, 0.35, 0.35, 1.6]]
}
```

### 2.4 ตราประทับพื้นเด้งเกินขนาดแล้วหดกลับ (`pop_seal`)
วงเวท ดอกบัว หรือตราฟักทองบนพื้นจะดูมีแรงกระแทกทันทีเมื่อ `sizeKeys` ขยายเลยขนาดจริงไปที่ `1.12x` ในเสี้ยววินาทีแรกแล้วหดกลับลงมาที่ `0.98x -> 1.02x`:

```json
{
  "use": "pop_seal",
  "texture": "lotus",
  "color": "secondary",
  "size": 2.1,
  "sizeKeys": [[0, 0.3], [0.16, 1.12], [0.25, 0.98], [1, 1.02]]
}
```

### 2.5 เส้นริบบิ้นสองชั้น แกนคม + ปลอกแสงฟุ้ง (`ribbon_trail` + `ribbon_halo`)
เคล็ดลับของเส้นแสงตามมือที่ดูนุ่มเหมือนผ้าไหมแต่เห็นแกนชัด:
- ชั้นที่ 1: `ribbon_trail` (`blend: "normal"`, `size: 0.10`, `emissive: 2.5`) รักษาสีแท้ไม่ขาวโพลนตอนกลางวัน
- ชั้นที่ 2: `ribbon_halo` (`blend: "add"`, `size: 0.20`, `alpha: 0.22`, `emissive: 6`) คลุมรอบนอกเป็นรัศมีเรืองแสง
- ชั้นที่ 3: `shape_float` (`butterfly`, `petal`, หรือ `sparkle`) อัตราต่ำ (`rate: 3–4`) ทิ้งไว้ตามแนวเหวี่ยง

### 2.6 แฟลชส่องพื้นจริงคู่ควันดำตัดขอบ (`light_flash` + `shadow_smoke`)
บนพื้นถนนสีเทาสว่างตอนเที่ยงของ GTA V เอฟเฟกต์แบบ `add` ล้วนจะจมหายไปกับแดด การใส่ `shadow_smoke` (`blend: "normal"` สีเข้ม) รองพื้นด้านล่างคู่กับ `light_flash` ที่มีพอยต์ไลต์ส่องฉากจริง (`intensity: 4.5`, `range: 3.8 m`) ทำให้ทั้งจังหวะมืดตัดขอบและแสงสะท้อนบนตัวละครรอบข้างชัดเจนทุกสภาพอากาศ

### 2.7 ก้อนบล็อก/ชิ้นส่วนดีดตัวขึ้นเป็นวิถีพาราโบลาแล้วตกกระทบพื้น (`brick_pop_arc` + `accelKeys` + Multi-Color Sheet)
สำหรับสกินแนวพลาสติกประกอบร่าง (`brick_modular` / ธีม `brick` / `lego`), เหรียญคาสิโน หรือเศษคริสตัลที่ต้องการให้ชิ้นส่วนหลายสีพุ่งโค้งขึ้นแล้วร่วงลงพื้นตามแรงโน้มถ่วงจริง:
- **ห้ามใช้ `IsLit = 1` + `SuperAlpha = 20`:** ผลผ่า `lego.ypt` รุ่นเก่าพบว่าค่าดังกล่าวทำให้บล็อกสีสดกลายเป็นก้อนสีขาวด้านกลางแดด ต้องใช้ `blend: "normal"` (`BlendSet = 0`), `IsLit = 0`, `LightingMode = 0`, `SuperAlpha = 1.0`, `emissive: 2.25–2.4`
- **หลากสีสดใน 1 Emitter ด้วย Sheet ใต้ชื่อช่องเกม:** วาดบล็อก ABS 16 ชิ้นแยกสีลงใน sheet `4x4` (`ptfx_insects_rgb` เช่น `sheet_lego_bricks` / `sheet_brick`: ก้อน `2×4` แดง `#e3242b`, `2×2` เหลือง `#ffd500`, `1×2` น้ำเงิน `#006cb7`, คาน Technic เทา `#2f353d`, นีออนฟ้า `#00eeff`, มะนาว `#9dff00`) และปุ่มกลม `1×1` ลงใน sheet `2x2` (`ptfx_fishes`) แล้วตั้ง `color: "#ffffff"` พร้อมสุ่มเฟรมเริ่ม (`frames: [0, 15]`) จะได้ชิ้นส่วนคละสีแท้ครบทั้งชุดใน 1 layer!
- **กฎวิถีโค้งพาราโบลาที่ตรงกันทั้งในเกมและใน `YptPreview` (`YptPreview.cs:265`):** ตัวจำลอง `.preview.png` อ่านค่าความเร่งที่ `t = 0` ดังนั้น **ให้ส่งแรงยกตัวขาขึ้นผ่านความเร็วต้น (`dir: [0.0, 0.0, 0.45..0.88]`, `spread: 0.95..1.25`, `speed: [2.2, 5.8]`) และตั้ง `accelKeys` แกน Z ให้ติดลบทุกระยะ (`-7.2 → -11.5 → -13.2`)** จะได้วิถีโค้งพุ่งขึ้นแล้วร่วงลงบนตราพื้นจริงทั้งในเกมและในภาพ preview:

```json
{
  "texture": "sheet_lego_bricks",
  "frames": [0, 15],
  "blend": "normal",
  "burst": 12,
  "life": [0.34, 0.52],
  "shape": "sphere",
  "radius": 0.07,
  "dir": [0.0, 0.0, 0.45],
  "spread": 1.25,
  "speed": [2.2, 4.2],
  "accelKeys": [
    [0.00, 0.0, 0.0,  -7.5],
    [0.40, 0.0, 0.0, -11.5],
    [1.00, 0.0, 0.0, -13.2]
  ],
  "drag": 1.15,
  "spin": [-420, 420],
  "size": [0.13, 0.20],
  "sizeKeys": [[0.0, 0.45], [0.14, 1.08], [0.75, 0.95], [1.0, 0.30]],
  "color": "#ffffff",
  "alphaKeys": [[0.0, 0.0], [0.06, 0.98], [0.72, 0.94], [1.0, 0.0]],
  "emissive": 2.35
}
```

- **ข้อสังเกตสคีมา `YptDesign.cs`:** คีย์ระดับบนสุด `"effects"` ต้องเป็น JSON array (`[...]`), ทรงกลม/ทรงกระบอกกลวงใช้คีย์ `"shape"` คู่กับ `"inner"` (ไม่ใช่ `spawn`/`innerRadius`), และ `"textures"` รองรับ `"width"`/`"height"` แยกกัน (เช่น `512` × `128` สำหรับริบบิ้นไร้รอยต่อที่เว้นขอบบน-ล่าง `alpha = 0`)

### 2.8 พิมพ์เขียวอ้างอิง 4 เอฟเฟกต์ของตระกูล `brick_modular` (`weapon_lego/stream/lego.ypt`, `331 KB`, `0 WARN / 0 ERR`)
โครงสร้างจริงที่ผ่าน `ptfx.ps1 lint` (`fields=27301 errors=0 warnings=0 notes=0`, `textures=8` POT DXT5 ครบ mipmaps, `gfx=1.5 MB`):
- **`lego_hold` (`loop: true`, `1.20 s`, 4 layers, `~37 alive`):** (1) `snap_ribbon` เส้นพลังงานปุ่มตัวต่อ `512×128` (`rateOverDist: 20`, `attach: [[0,0.55],[0.22,0],[1,0]]`), (2) `floating_studs` ปุ่มกลม `2x2` ลอยขึ้นฟ้าด้วย `gravity: -0.24` (`attach: 0`), (3) `micro_bricks` ก้อนตัวต่อ `4x4` หมุนช้า (`gravity: -0.18`, `attach: 0`), (4) `plastic_glints` ประกาย `twinkle_glints`
- **`lego_hit` (`loop: false`, `0.58 s`, 5 layers, `~39 alive`):** (1) `snap_flash` แฟลชปะทะ `0.14–0.20 s`, (2) `shock_ring` วงคลื่นกระแทก, (3) `scatter_bricks` ก้อนตัวต่อ `12` ชิ้นดีดโค้งด้วย `accelKeys` (`-7.5 → -13.2`), (4) `scatter_studs` ปุ่มกลม `14` เม็ดตกด้วย `gravity: 10.2`, (5) `click_sparks` เส้นประกาย
- **`lego_kill` (`loop: false`, `1.95 s`, 7 layers, `~89 alive`):** (1) `baseplate_ground_seal` แป้นตัวต่อแปดเหลี่ยม + รูสลัก Technic บนพื้น (`z = -0.90`, `pop_seal`), (2) `toy_flash_core` แสงศูนย์กลางพร้อม dynamic `Light`, (3) `multi_stage_shock_ring`, (4) `brick_fountain_main` น้ำพุตัวต่อ `26` ชิ้นตกลงบนแป้นซีล, (5) `stud_geyser_shower` ปุ่มกลม `28` เม็ด, (6) `second_stage_brick_pop` ระเบิดซ้ำที่ `start: 0.24`, (7) `celebration_stud_sparkles`
- **`lego` เดี่ยว (`loop: false`, `0.78 s`, 3 layers, `~25 alive`):** one-shot ขนาดกะทัดรัดที่ `ZoomScalar = 100` คงไว้เพื่อรองรับ EffectMix เก่าที่เรียก `particleName = "lego"` โดยไม่พัง

---

## 3. กฎการเล่นจริงและฟิลด์ลับของ `1nfx_weaponskin`

ตรวจยืนยันตรงจาก `core/sh_mixing.lua:304–352` (`DamagePlayback`) และ `core/cl_effects.lua` ของเซิร์ฟเวอร์ `[1nfx]`:

### 3.1 ตารางพฤติกรรมรายช่องอาวุธ (สำคัญมากเมื่อออกแบบเซ็ต)

| ช่องอาวุธ | ตี/ยิงโดน (ยังไม่ตาย `not died`) | ฆ่าตายสำเร็จ (`died`) | ข้อควรระวังในการออกแบบ |
| --- | --- | --- | --- |
| `Poolcue`, `Bottle` | เล่น `Hit.Effect` + `Hit.Screen` (แต่ถ้าไม่ตั้ง `Hit.Effect` จะ **ไม่** ดึง `Kill.Effect` มาเล่นแทน และไม่สปอว์น `Kill.Prop`) | เล่น `Kill.Effect` (ถ้าไม่มี fallback ไป `Hit.Effect`) + `Kill.Prop` + `Kill.Screen` | ต้องกำหนด `Hit.Effect` ไว้ให้ครบทุกช่องเพื่อให้จังหวะฟันโดนมี feedback ทันที และทุ่มจุดเด่นชุดใหญ่ไว้ที่ `Kill.Effect` |
| `Revolver` | เข้า `phase = "hit"` เสมอ: เล่น `Hit.Effect` (ถ้าไม่มีจะ fallback ไป `Kill.Effect`) + `Hit.Screen` | ใช้เส้นทางเดียวกับ `hit` เสมอ (แม้กระสุนนัดนั้นจะฆ่าตาย!) | `Hit.Effect.Revolver` ต้องคมชัดที่ `scale = 1.0` และถ้ามี `Kill.Prop` บน `Revolver` **ต้องใส่ `on_hit = true` ใน prop ตัวแรกของ `Revolver`** มิฉะนั้น prop จะไม่ถูกเรียกเลย |
| `Knuckle`, `Machete`, `Knife`, `Bat` | เล่น `Hit.Effect` + `Hit.Screen` ครบ | เล่น `Kill.Effect` + `Kill.Prop` + `Kill.Screen` ครบ | `Hit.Effect` ต้องกระชับ (`0.50–0.65 s`) ไม่บังเป้าเล็งต่อเนื่อง |

### 3.2 ฟิลด์ขั้นสูงใน `Effect` ของ Lua (`cl_main.lua`)

นอกเหนือจาก `scale`, `offset`, `rot`, `bone`, `attach`, `delay` ระบบ `1nfx_weaponskin` รองรับคีย์ควบคุมการเคลื่อนไหวเพิ่มเติมดังนี้ (และ `new-skin.ps1` รองรับการส่งผ่านจาก `spec.json` แล้ว):

- `ground = true`: ก่อนวาง particle ระบบจะยิง `GetGroundZFor_3dCoord` หาพื้นจริงใต้จุดเกิด เหมาะกับเอฟเฟกต์ `Kill` ที่ไม่อยากให้วงเวทลอยค้างระดับเอวเมื่อศพกำลังล้ม
- `orbit_turns = 1.5`: สำหรับ looped particle (`isLoop = true` และกำหนด `duration` เป็น ms) ระบบจะหมุนจุดเกิดเป็นวงกลมรอบตัวละครทุก `33 ms` จนครบจำนวนรอบภายใน `duration` โดยใช้ `offset.x`/`offset.y` เป็นรัศมีวงโคจร
- `growScale = 2.2`, `growSteps = 12`, `growStepTime = 80`: ค่อย ๆ ขยายขนาดของ looped particle จาก `scale` เริ่มต้นไปยัง `growScale` ทีละขั้นด้วย `SetParticleFxLoopedScale`

---

## 4. สถาปัตยกรรม `Kill.Prop` (3D Finisher) และโมเดลอาวุธมีชีวิต

### 4.1 การประกอบ `Kill.Prop` แบบหลายชิ้น (Parent Ground + Child Billboard/Anim)
`WeaponSkinProps:Play` (`cl_main.lua:3295–3463`) รองรับทั้งการใส่ตารางเดียวใช้ทุกอาวุธ หรือแยกตารางตามชื่ออาวุธ (`Poolcue = { ... }, Revolver = { ... }`) โดยจำกัดสูงสุด `12` ชิ้นพร้อมกันในระยะ `15 m`:

```lua
Prop = {
    Poolcue = {
        {
            model = "w_fx_lotus_altar",
            duration = 2600,
            delay = 0,
            ground = true,
            scale = 1.0,
            offset = { x = 0.0, y = 0.0, z = 0.0 },
            rotation = { x = 0.0, y = 0.0, z = 0.0 },
            animDict = "clip@w_fx_lotus_altar",
            animName = "bloom_open",
            animSpeed = 1.0,
            animHoldLastFrame = true,
        },
        {
            model = "w_fx_lotus_halo",
            duration = 2400,
            delay = 180,
            ground = true,
            billboard = true,
            scale = 1.15,
            offset = { x = 0.0, y = 0.0, z = 1.35 },
        },
    },
    Revolver = {
        {
            model = "w_fx_lotus_altar",
            on_hit = true,
            cooldown = 1500,
            duration = 2200,
            ground = true,
            scale = 0.9,
        },
    },
},
```

- **งบโพลีกอนของ `Kill.Prop`:** ควรอยู่ที่ **`150–4,000 tris`** เท่านั้น (ตัวอย่างคริสตัลระเบิดพื้นในงานจริงใช้เพียง `160 tris` แต่ดูคมกริบเพราะรูปทรงเหลี่ยมชัด + shader `emissive`)
- `scale` ใน `Kill.Prop` ทำงานจริงผ่านการคูณ basis vectors ใน `SetEntityMatrix` ทุกเฟรม จึงย่อ/ขยายโมเดล prop เดียวกันให้ต่างขนาดตามช่องอาวุธได้

### 4.2 สี่ระดับ Shader ที่ใช้ในโมเดลอาวุธและ 3D FX

| ระดับ | Shader ใน GTA V / Sollumz | การใช้งานจริง |
| --- | --- | --- |
| **Tier 1: Flat Glow** | `emissive` / `emissivestrong` / `emissivenight` | เส้นเรืองแสง คริสตัล วงเวท 3D หรือใบมีดพลังงานล้วน |
| **Tier 2: PBR + Glow** | `normal_spec` คู่กับ `normal_spec_emissive` | มาตรฐานหลักของอาวุธคุณภาพสูง: ตัวเรือนโลหะ/คาร์บอนรับแสงฉากคมชัด แยก material เฉพาะร่องรูนหรือดวงตาให้เรืองแสง |
| **Tier 3: UV-Scroll Aura Shell** | `emissive_additive_uv_alpha` + texture แถบไล่สี `1024x8` (DXT5) | สร้างเปลือก mesh บาง ๆ คลุมห่างผิวใบมีด `2–4 mm` แล้วใช้ `.ycd` เลื่อน UV ตลอดเวลา ทำให้เห็นคลื่นพลังงานวิ่งไหลไปตามคมดาบหรือเสาแสงตอนฆ่า |
| **Tier 4: Glass Enclosure** | `glass` + `spec` ห่อแกน `emissive` ด้านใน | ขวดแก้ว โคมแก้ว หรือคทาที่มองทะลุเห็นของเหลว/หัวใจเรืองแสงข้างใน |

### 4.3 การทำโมเดลอาวุธขยับเองด้วย `.ytyp` + `.ycd`
เมื่อต้องการให้ชิ้นส่วนบนอาวุธ (เช่น วงแหวนเวท ปีกผีเสื้อ ฟันเฟือง หรือแถบแสง UV) ขยับเองตลอดเวลาโดยไม่ต้องเขียนสคริปต์ Lua คุมทีละเฟรม:
1. แยก bone ย่อยของชิ้นส่วนที่ขยับไว้ใต้ `Gun_Root` ใน `.ydr`
2. ส่งออก animation clip เป็น `clip@<model>.ycd`
3. ผูก `<clipDictionary>clip@<model></clipDictionary>` ในไฟล์ `<model>.ytyp` และประกาศ `data_file "DLC_ITYP_REQUEST" "stream/<model>.ytyp"` ใน `fxmanifest.lua`

---

## 5. แปดข้อผิดพลาดจริงที่ห้ามทำซ้ำ (Forensic Anti-Patterns Checklist)

จากการตรวจสอบไฟล์จริงกว่า `254` `.ypt` dictionaries และสคริปต์ภายนอกกว่า `3,700` ไฟล์ พบข้อผิดพลาดรุนแรงที่ทำให้สกินพังหรือทำให้ไคลเอนต์หน่วยความจำเต็ม ต้องตรวจเช็กทุกครั้งก่อนส่งงาน (ดูสัญญาระดับโค้ดครบใน **`references/bone-and-memory-safety.md`**):

1. **ชื่อ `DICT` ข้างในไฟล์ `.ypt` ไม่ตรงกับชื่อไฟล์ หรือตั้งทับชื่อเกมหลัก (`scr_*`, `cut_*`, `des_*`):**
   - *ปัญหาที่พบ:* แพ็กภายนอก (`bbg_wp10_1.ypt`, `xdoy_efx_heal.ypt`) เปลี่ยนชื่อไฟล์บนดิสก์แต่ข้างในยังเป็นชื่อเก่า หรือตั้งชื่อเป็น `scr_ba_club.ypt` / `cut_martin1.ypt` ไปทับเอฟเฟกต์หลักของ GTA V ทั้งเซิร์ฟเวอร์
   - *วิธีป้องกัน:* สร้างด้วย `ptfx.ps1 build` เสมอ ซึ่งบังคับชื่อภายในและชื่อไฟล์ให้ตรงกัน (`<id>.ypt` หรือ `<id>_fx.ypt`) และผ่านการตรวจซ้ำกับ `server-catalog.md`
2. **ฝังเท็กซ์เจอร์ขยะ 4K ที่ไม่ได้ใช้ (`32 MB` GFX Leak) หรือใช้ภาพไม่บีบอัด `A8R8G8B8`:**
   - *ปัญหาที่พบ:* `spakeffect3.ypt` มีเอฟเฟกต์จริงเพียง `8 KB` แต่ลืมลบเท็กซ์เจอร์ `4096×4096` ที่ไม่มี rule ใดอ้างถึง กินหน้าหน่วยความจำ `gfx` ไป `32 MB` ฟรี ๆ; ส่วน `ice_crystal_staff_2.ypt` และ `xdoy_efx_heal.ypt` ฝังภาพ `A8R8G8B8` 12–14 ใบ (ใหญ่กว่า `DXT5` 4 เท่า)
   - *วิธีป้องกัน:* ใช้เฉพาะ `DXT5`/`DXT1` ขนาดกำลังสอง (`128`–`512 px`) พร้อม mipmaps ครบ และห้ามมี orphan texture/emitter ค้าง (`ptfx.ps1 lint` ตรวจให้อัตโนมัติ)
3. **ตั้งชื่อใหม่เองให้กับ Sprite Sheet หลายเฟรม (`ClipRegions` Failure):**
   - *ปัญหาที่พบ:* ใน `xdoy_efx_heal.ypt` ผู้สร้างฝังตารางหลายเฟรมภายใต้ชื่อใหม่ `electric_blue_hit_neon_splash` ทำให้ GTA V ไม่รู้จักตารางตัดเฟรมและวาดสไปรต์ทั้งแผ่นซ้อนเป็นสี่เหลี่ยมเดียว
   - *วิธีป้องกัน:* ให้ `sheets` ใน `ptfx.ps1 build` ฝังแผ่นหลายเฟรมใต้ชื่อช่องเกมมาตรฐาน (`ptfx_fishes` `2x2`, `ptfx_multi_sheet_002_debris` `4x4` ฯลฯ) เสมอ
4. **เอาเอฟเฟกต์ขนาดยักษ์ (`ZoomScalar != 100`) มาย่อ `scale = 0.02–0.10` ใน Lua:**
   - *ปัญหาที่พบ:* การย่อด้วย `scale` ต่ำมากใน Lua ไม่ได้แก้ `ViewportCullingSphereOffset` ทำให้หันกล้องนิดเดียวเอฟเฟกต์ก็ดับวูบ
   - *วิธีป้องกัน:* ตั้ง `ZoomScalar = 100`, ออกแบบขนาดจริงใน JSON แล้วใช้ `scale = 1.0` ใน Lua เสมอ
5. **วนลูปสปอว์น `StartParticleFxLooped*` เป็นวงกลมใน Lua หรือยิง `StartNetworkedParticleFx*` รัว ๆ:**
   - *ปัญหาที่พบ:* สคริปต์ `XD-JJ` วนลูปสร้าง handle 36 จุด × 4 ชั้น = กว่า 144–400 handles ต่อคนเดียวจนพูล PTFX เต็มและเกมแครช หรือยิง `StartNetworkedParticleFx*` จนโดน OneSync เตะ
   - *วิธีป้องกัน:* ทำวงแหวนด้วย `shape: "cylinder"` ใน `.ypt` (ใช้แค่ 1 handle) และใช้ local PTFX คู่กับระบบจัดการหน่วยความจำใน `references/bone-and-memory-safety.md`
6. **โมเดล Sculpt/AI ดิบไม่ลดโพลี หรือปุ่มเลโก้ถี่รอบก้าน (`37k–398k tris`) และใช้ Texture NPOT:**
   - *ปัญหาที่พบ:* โมเดลขนมเค้ก `398,128 tris` (`7068×2776` NPOT) และไม้คิวเลโก้รุ่นเก่าที่เรียงปุ่ม 26 segments รอบก้าน 700 ปุ่มจนพุ่ง `37,276 tris`
   - *วิธีป้องกัน:* อาวุธทุกชิ้นอยู่ในงบ **`4,500–25,000 tris`** (`Kill.Prop` `<= 4,000 tris`), ปุ่ม Hero Brick ใช้ 10–12 segments เปิดฐานล่าง, โซนมือจับเรียบ SNOT และแผ่นภาพกำลังสอง (`512`–`2048`) DXT1/DXT5 พร้อม mipmaps
7. **วางแกนใบมีดผิดระบบ (`+Y` Addon เทียบกับ `+Z` Component ของ `[1nfx]`):**
   - *ปัญหาที่พบ:* โมเดลอาวุธ Addon เดี่ยวมักหันปลายไปทาง `+Y` ถ้านำมาใส่เป็น `COMPONENT_SKIN_*` โดยไม่หมุนแกน ดาบจะชี้ทะลุหลังมือตั้งฉาก `90°`
   - *วิธีป้องกัน:* อาวุธประชิดวางปลายชี้ **`+Z`** (ระนาบ XZ คมหัน `+X`, สนับมือรูนิ้วชี้ `-Y`, ปืน `Revolver` ปากกระบอกชี้ **`+X`**) และตรวจด้วย `validate_model.py` + `inspect-ydr.ps1` ทุกครั้ง
8. **โมเดลช่อง `Bottle` ไม่มีกระดูก `Gun_Root` หรือส่ง `boneIndex == -1` เข้า Native:**
   - *ปัญหาที่พบ:* โมเดลขวดแบบ static mesh ไม่มี armature ทำให้สวมผ่าน `<AttachBone>gun_root</AttachBone>` ไม่ได้ และสคริปต์ที่ไม่เช็ก `GetPedBoneIndex ~= -1` ทำให้เอฟเฟกต์หลุดไปเกิดที่พิกัดโลก `(0,0,0)`
   - *วิธีป้องกัน:* ทุกช่องทั้ง 7 ช่องต้องมี armature + `Gun_Root` เสมอ และฝั่ง Lua ต้องผ่าน `ResolveSafePedBone` / `DoesEntityExist` ทุกครั้ง
