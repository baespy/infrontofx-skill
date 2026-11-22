# Archetypes

ทุก archetype อยู่ใน `scripts/blender/forge_prop.py` (`ARCHETYPES`) ขนาดเป็นเมตร ด้านหน้าหัน -Y ภาพตัวอย่างอยู่ใน `targets/`

| archetype | ใช้ในเกม | ขนาดเริ่มต้น (กว้าง x ลึก x สูง) | งบ tris | ชน | พารามิเตอร์ในสเปก |
| --- | --- | --- | --- | --- | --- |
| `sign_post` | จุดเบิกรถ, จุดพาวด์, ป้ายบอกทาง (V9 แท่นวงกลมเตี้ย 360° ไร้จอ สเกลเดียวกับ Airdrop + ป้ายสองหน้าหมุน 360° + Topper เฉพาะทาง) | 1.44 x 1.28 x 1.48 | 15000 | ไม่มีเมื่อตั้ง `collision: false` (เดิน/ขับรถทะลุได้) หรือฐาน+เสา+ป้าย | `circular` (`true` ค่าเริ่ม = วงกลมเตี้ย 360° ไร้จอ), `collision` (`false` เพื่อทำ prop ทะลุได้ทั้ง `.ydr` และ config), `label`, `sub`, `icon` (`house`), `topper` (`car` รถสปอร์ตไวนิลหมุน 360° บน Garage, `tow_siren` ไซเรน 720° + ตะขอลากทองคู่แกว่งบน Pound), `board`, `text`, `use_logo` (5-7 bones, 181f = 6.0s) |
| `parking` | จุดจอด/เก็บรถ (V9 แท่นวงกลมเตี้ย 360° ไร้จอ สเกลเดียวกับ Airdrop + ป้าย `PARKING` หมุน 360° + ไม้กั้นรถคู่ยกขึ้น-ลง + เหรียญ `"P"` กลมหมุน 360°) | 1.74 x 1.30 x 1.55 | 15000 | ไม่มีเมื่อตั้ง `collision: false` (เดิน/ขับรถทะลุได้) หรือฐาน+เสา+ป้าย | `collision` (`false` = ทะลุได้), `label`, `body_role`, `accent_role`, `base_role`, `text_resolution`, `use_logo` (7 bones: `root`, `sign_ring`, `gate_l`, `gate_r`, `p_badge`, `crown`, `orbit` 181f = 6.0s) |
| `kiosk_sign` | ป้ายร้านตั้งพื้น | 0.96 x 0.44 x 1.35 | 11000 | ฐาน แผ่นป้าย | `label` |
| `atm` | ATM / ตู้ฝากถอน | 0.96 x 0.77 x 1.71 | 12000 | ฐาน ตัวตู้ | `label` |
| `safe` | ตู้เซฟ, ตู้เก็บของบ้าน | 1.10 x 1.02 x 1.11 | 14000 | ตัวตู้ | `label`, `w`, `d`, `h` |
| `crate` | stash, airdrop, กล่องรางวัล | 1.34 x 1.17 x 1.03 | 12000 | ตัวกล่อง | `w`, `d`, `h` |
| `chest` | loot, หีบสมบัติเปิดฝา | 0.81 x 0.61 x 0.80 | 10000 | ตัวหีบ | `open` (องศา 0 = ปิด), `coins`, `w`, `d`, `h` |
| `workbench` | โต๊ะคราฟต์ | 2.02 x 0.92 x 2.26 | 18000 | โต๊ะ ตู้ลิ้นชัก แผงหลัง | `w`, `d`, `top` |
| `mascot_marker` | marker ลอยเหนือจุด interaction | 1.00 x 0.64 x 0.91 | 5000 | ไม่มี | `radius` |
| `airdrop` | กล่อง Airdrop ของตกพร้อมแอนิเมชัน | 1.87 x 1.87 x 1.51 | 15000 | ตัวกรง + แท่นฐาน | `body_role`, `accent_role`, `core_role`, `w`, `h`, `use_logo` (5 bones: `root`, `core`, `gyro`, `crown`, `orbit` 181f = 6.0s) |
| `powerbox` | ตู้ไฟ / ตู้ควบคุม Blackout พร้อมสับเบรกเกอร์และไซเรนหมุน | 1.71 x 1.57 x 1.82 | 15000 | ฐาน + ตัวตู้ | `body_role`, `accent_role`, `voltage`, `w`, `d`, `h`, `text_resolution`, `use_logo` (7 bones: `root`, `switch_a`, `switch_b`, `siren_l`, `siren_r`, `crown`, `orbit` 121f = 4.0s) |
| `redbox` | ตู้แดงท้ายรถ / กล่องเครื่องมือล้อเลื่อน (แทน `imp_prop_tool_draw_01e` สเกล 1:1) | 1.14 x 0.60 x 1.32 | 13000 | ตัวตู้ | `body_role`, `drawer_role`, `accent_role`, `mascot_role`, `w`, `d`, `h`, `use_logo` (4 bones: `root`, `top_drawer` เลื่อนแง้มโชว์ของ, `crown` มาสคอตบนถาด, `orbit` ดาวหมุน 151f = 5.0s) |
| `waterpipe` | ท่อน้ำกิจกรรมซ่อมท่อประปา (แทน `1nfx_waterpipe`) | 1.07 x 1.12 x 1.45 | 13000 | แท่น + ท่อ | `body_role`, `pipe_role`, `base_role`, `use_logo` (4 bones: `root`, `valve` พวงมาลัยวาล์วทองหมุน 360°, `crown`, `orbit` 151f = 5.0s) |
| `gachapon` | ตู้กาชาปองหมุนไข่กิจกรรม (`1nfx_gachapon` / Lucky Event) | 1.22 x 1.22 x 2.00 | 14000 | ฐาน + ตู้ + โหลไข่ | `body_role`, `accent_role`, `w`, `d`, `use_logo` (4 bones: `root`, `crank` มือหมุนดาวทอง 360°, `crown`, `orbit` 151f = 5.0s) |
| `washmoney` | เครื่องซักผ้ากิจกรรมฟอกเงิน (`washmoney` dropoff) | 1.27 x 0.98 x 1.64 | 14000 | ฐาน + ตัวเครื่อง | `body_role`, `accent_role`, `w`, `d`, `h`, `use_logo` (4 bones: `root`, `drum` ถังซักปั่นปึกเงินและฟองสบู่ 360°, `crown`, `orbit` 121f = 4.0s) |

ทุก prop รับ `seed` (เปลี่ยนรูปหยดสไลม์และลอน), `palette` (ทับสีเฉพาะชิ้น ชิ้นนั้นจะได้ texture ของตัวเอง), `style` (`"vinyl_toy"` สำหรับ V5-V9 สตรีทไวนิลสไลม์+ขอบหมึกดำ หรือ **`"kawaii_billie"`** สำหรับ V10 คาวาอิครีม-คาราเมล-โกโก้: เปลี่ยนสไลม์หยดเป็นเมฆฟูไร้รอยต่อ, มงกุฎเป็นดาวทอง+หูหมีบนก้อนเมฆ, หน้าจอยิ้มคาวาอิ และ Cycles Baker เงาโกโก้นุ่ม `#3B281E`), `low_poly` (`true` ที่ระดับชุดหรือรายชิ้น เพื่อลดโพลีกอน ~50% สำหรับเซิร์ฟเวอร์ FiveM ลื่นๆ โดยคงเงา smooth-shaded ไว้ครบ), `budget`, `lod_dist`, `collision: false`, `decals`, `text_resolution` (ความละเอียดตัวหนังสือ ค่าเริ่ม 2; ใช้ `1` เมื่อต้องการประหยัด tris บนป้ายสองหน้า), `mascot_style` (`"slime"`, `"spray_can"`, หรือ **`"billie_bear"`** หัวมาสคอตน้องหมีฮู้ดน้ำตาลติดส้ม+หน้าครีมแก้มชมพูบนก้อนเมฆ), `glossy` (`true` เพื่อใช้ `default_spec.sps` ผิวเงาไวนิล), `logo`, `logo_aspect` (อัตราส่วนกว้าง/สูงจริงของโลโก้), `use_logo` (`true` เพื่อวางโลโก้แบรนด์อัตโนมัติในตำแหน่งมาตรฐานและเปิดรายละเอียดระดับ AAA), `detail_tier` (`"aaa"`), `icon` (`"house"` บน `sign_post`, `"cart"` บน `kiosk_sign`), `float_coins` (`true` บน `chest`), `dark_border` (`true` บน `sign_post`)

## สคีมาสเปก

```json
{
    "set": "1nfx_ext",
    "brand": { "name": "EXTREME COMMUNITY", "short": "EXTREME" },
    "font": "TitanOne-Regular.ttf",
    "style": "vinyl_toy",
    "mascot_style": "spray_can",
    "glossy": true,
    "animate": true,
    "logo": "art/extreme_logo_glow.png",
    "logo_aspect": 1.5277,
    "logo_bg": "art/extreme_logo_bg.png",
    "logo_bg_aspect": 1.5277,
    "palette": { "primary": "#660B16", "accent": "#FF1926", "light": "#F7F9FC", "dark": "#140B0F", "gold": "#FFD024", "trim": "#C81022" },
    "props": [
        { "id": "1nfx_ext_garage", "archetype": "sign_post", "label": "GARAGE", "icon": "house", "dark_border": true },
        { "id": "1nfx_ext_shop", "archetype": "kiosk_sign", "label": "SHOP", "icon": "cart", "use_logo": true },
        { "id": "1nfx_ext_atm", "archetype": "atm", "use_logo": true }
    ]
}
```

- `set`: ชื่อชุด ใช้เป็นชื่อ texture palette ร่วม (`<set>_palette`) และชื่อวัสดุก่อน finish
- `brand.name` ใช้กับ wordmark ใหญ่ `brand.short` ใช้กับที่แคบ (ป้าย Shop, ข้างตู้ ATM)
- `font`: ชื่อไฟล์ใน `assets/fonts/` หรือพาธเต็ม
- role ของสีที่ใช้ได้: `primary`, `accent`, `light`, `dark`, `gold`, `trim`, `metal`, `screen`, `glow`, `glowtrim`, `wood` (`screen`, `glow`, `glowtrim` จะไปอยู่ในวัสดุ emissive)
- `decals[].side`: `front`, `back`, `left`, `right`, `top`; `center` คือ [แนวนอนของหน้านั้น, ความสูง z] เป็นเมตร; `width`; `height` (ไม่ใส่ = ตามสัดส่วนรูป); `offset` ระยะลอยจากผิว (ค่าเริ่ม 4 มม.) วางบนหน้าเรียบเท่านั้น

## เพิ่ม archetype ใหม่

เขียนฟังก์ชัน `build_<ชื่อ>(b, p)` ใน `forge_prop.py` แล้วเพิ่มเข้า `ARCHETYPES` และ `TRIS_BUDGET` สร้างทุกชิ้นด้วยเมธอดของ `PropBuilder` (`b`):

| เมธอด | ใช้ทำ |
| --- | --- |
| `b.box(size, loc, role, bevel, rot, M, matrix, collide)` | กล่อง bevel (bevel ถูกจำกัดไม่เกิน 40% ของด้านที่สั้นที่สุด) |
| `b.cyl(radius, depth, loc, role, axis, segments, radius2, bevel)` | ทรงกระบอก/กรวย แกน `X` `Y` `Z` |
| `b.sphere(radius, loc, role, scale, u, v)` | ทรงกลม บีบด้วย `scale` |
| `b.torus(major, minor, loc, role, axis)` | ห่วง (ขอบประตูเซฟ สัญลักษณ์ contactless) |
| `b.shape(pts, y0, y1, role, bevel, loc, M, collide)` | รูป 2D ในระนาบ X-Z ดึงหนาตามแกน Y ใช้กับ `rounded_rect`, `blob_outline`, `arrow_outline`, `star_outline` |
| `b.text(body, height, loc, role, depth, max_w, outline_role, rot_z, M)` | ตัวหนังสือ mesh หันหน้า -Y มีขอบเข้มด้านหลัง (`rot_z=math.pi` สำหรับด้านหลัง) |
| `b.skirt(w, d, z_top, role, max_drop, drops_per_side, sides)` | สไลม์ไหลรอบขอบบนของกล่อง (แบบบาง) |
| `b.fat_drip(...)`, `b.fat_curtain(...)`, `b.fat_skirt(...)` | หยดสี/สไลม์ 3D อวบกลมทรงแคปซูลพร้อมเม็ดหยดลอย (มาตรฐาน AAA) |
| `b.blob_tube_frame(w, h, y_center, tube_r, role, lobes, lobe_amp)` | กรอบท่อกลม 3D อวบโค้งรอบป้าย Shop / ตู้ ATM / ป้ายหัวโต๊ะ |
| `b.chamfered_base(w, d, h, role, pad_role, glow_role)` | ฐานลาดเอียงสองชั้นพร้อมช่องไฟหน้า-ข้าง |
| `b.ribbed_handle(loc, role, side_sign, scale)` | มือจับอุตสาหกรรมมีนอต 4 มุม ร่องมืด และแกนจับลูกฟูก |
| `b.bolt_cap(loc, radius, role, x_role)` | หัวหมุด/นอตกลมมีกากบาท X บนขาโต๊ะและคาน |
| `b.cash_gold_treasure(w, d, z_base, coins, float_coins)` | แท่งทองเรียงซ้อน + ปึกเงินสด + เหรียญกองและเหรียญลอย |
| `b.crown(loc, radius, height, tilt)` | มงกุฎ 5 แฉกขอบม้วนกลมพร้อมพลอยทรงข้าวหลามตัด |
| `b.mascot(...)`, `b.spray_can(...)` | หัวมาสคอตตา X หรือกระป๋องสเปรย์ไวนิล 3D โค้งอวบพร้อมคิ้วโกรธ ดาวตา ควันสเปรย์ และมงกุฎเอียง |
| `b.shopping_cart(...)`, `b.angry_screen_face(...)` | ไอคอนรถเข็น 3D และใบหน้าตาโกรธเรืองแสงบนจอเสาป้าย |
| `b.decal(...)`, `b.logo_decal(...)` | วางแผ่นสติกเกอร์โลโก้ตามพิกัดกลุ่ม (ใช้ material ร่วมกันอัตโนมัติ รองรับ `decal.sps` และ `emissive_alpha.sps`) |
| `b.x_mark(center, direction, size, role)`, `b.star(loc, size, role, direction, crossed)` | ตา X, ดาวประกาย (`crossed=True` ทำดาว 3D กากบาทสองแกนเห็นสวยครบ 360° ไม่มีสันมืด) |
| `b.lightning_bolt(loc, size, role, direction)` | สายฟ้า 3D ขอบเข้มการ์ตูนสำหรับตู้ไฟ / เอฟเฟกต์พลังงาน |
| `b.curved_pillar(sections, role, corner, segs)` | เสา/ตัวถังทรงโค้ง S-sweep หรือเอวคอดแบบ lofted rounded-rect (แก้ทรงกล่องแข็ง 90°) |
| `b.round_column(profile, role, segs)` | เสาวงกลม 360° ทรงเอวคอดโค้งแบบ lathe สำหรับป้าย/จุดใช้งานรอบทิศทาง 360° |
| `b.slime_collar_mb(radius, z_top, role, drips, drip_angles)` | ปลอกสีสไลม์เมตาบอลไหลรอบวงกลม 360° ไร้ตะเข็บ (`drip_angles` กำหนดมุมหยดให้ลงช่องว่างไม่ทับป้ายโลโก้) |
| `b.mini_toy_car(loc, scale, body_role, stripe_role)` | รถสปอร์ตไวนิลจิ๋ว 3D หมุน 360° สำหรับ topper ป้าย Garage |
| `b.tow_hook_assembly(loc, scale, role)` | ตะขอลากรถพาวด์ + โซ่และรอก 3D แกว่งเพนดูลัมสำหรับป้าย Pound |

- `M` คือ matrix ของกลุ่ม (เช่น `Matrix.Translation((x, 0, z))` ของแผ่นป้าย) ทุกชิ้นในกลุ่มขยับตามกัน
- `collide=True` เพิ่มกล่องชนจากขอบเขตของชิ้นนั้น ใส่เฉพาะชิ้นใหญ่ที่ผู้เล่นเดินชน 1-4 กล่องต่อ prop
- สร้างจากพื้น z = 0 ขึ้นไป หันหน้า -Y สคริปต์จะจัดกึ่งกลาง X/Y และวางจุดต่ำสุดที่ z = 0 ให้เองตอนจบ
- รันด้วย `--only <id> --no-render` ดู tris ใน `report.json` ก่อน แล้วค่อยเรนเดอร์ ตัวหนังสือกิน tris มากที่สุด ถ้าเกินงบให้ลด `text_resolution`, ตัดตัวหนังสือด้านหลัง หรือย่อ `max_w`

## ปั้นคอลเลกชัน Kawaii V11 ด้วย `KawaiiBuilder` (`scripts/blender/kawaii_studio.py`)

สำหรับงานปั้น bespoke สไตล์ Pop-Mart / Animal-Crossing ที่ต้องการซิลูเอตเฉพาะชิ้นตรงตาม Concept Art 1:1 ให้ import `KawaiiBuilder` จาก `scripts/blender/kawaii_studio.py` (รันด้วย Blender `--factory-startup` ไม่ต้องลง add-on หรือ PIL):

| เมธอด (`KawaiiBuilder`) | ใช้ทำ |
| --- | --- |
| `plush_box(size, loc, role, r_bevel, subsurf, puff, collide)` | ตัวตู้/กล่องทรงหมอนขอบมนพองนุ่มแบบของเล่นไวนิล |
| `plush_pill(size, loc, role, segs, collide)` | แคปซูล/ปุ่มกด/มือจับ/ขา/คานโค้งมน |
| `plush_cyl(r, h, loc, role, bevel, segs, r_top, axis, collide)` | แท่นกลม ล้อ เหรียญ ถังซัก ท่อตรง |
| `plush_sphere(r, loc, role, scale, u, v)` | โหลแก้ว ไข่กาชาปอง ฟองสบู่ ลูกปัด |
| `lathe(profile=[(r,z),...], loc, role, segs, smooth_profile)` | แท่นหมุน 360°, โดมโค้ง, ขวด, กระดิ่ง, เสาเอวคอด |
| `plush_torus(major_r, minor_r, loc, role, axis, arc_deg)` | ห่วงพอร์ตโฮล, ข้องอท่อ 90°/180°, ตะขอลาก, ราวจับโค้ง |
| `plush_tube(points, radius, role, segs, closed, smooth_steps)` | ท่อโค้ง 3 มิติ, ริบบิ้น, สายไฟ, หูตะกร้า |
| `plush_extrude(pts_2d, depth, loc, role, bevel)` / `plush_frame(...)` | ป้ายโค้งมน, เกราะขอบ `.bbu-frame` โกโก้ |
| `plush_cloud(pts_r)` / `plush_cloud_pillow(w, d, h)` / `plush_cloud_ring(r, z)` | หมอนเมฆฟู, ฐานเมฆ, วงแหวนเมฆ 360° |
| `plush_star(loc, size)` / `plush_heart(loc, size)` / `plush_lightning(loc, size)` | ดาว 5 แฉกอ้วนพอง, หัวใจพอง, สายฟ้าการ์ตูน |
| `cafe_awning(w, d, h, loc, stripe_role, alt_role, trim_role, scallops)` | กันสาดคาเฟ่โค้งสลับแถบสีพร้อมชายหยักกลมและโครงโกโก้ |
| `billie_bear_plush(loc, radius, school, face_mode, with_body, with_cloud)` | มาสคอต 3D 4 บ้าน (`brown`/`pink`/`skyblue`/`grey`) หน้าโดมโค้งภาพทางการหรือปั้น 3D ล้วน |
| `decal_card(img_path, w, h, loc, frame_role, emissive, transparent, double_sided)` | วางโลโก้/ป้าย/หน้าจอ/เกจวัด พร้อมกรอบ `.bbu-frame` อัตโนมัติ (แพ็ก `<= 4` วัสดุอัตโนมัติ) |
| `text_sign(text, w, h, loc, ...)` | เจนป้าย `billie-ui` ฟอนต์ TitanOne ขอบสติกเกอร์ลงแคชและวางทันที |
| `plush_car`, `plush_coin`, `plush_banknote`, `plush_basket` | ของจิ๋วสำเร็จรูป (รถของเล่น, เหรียญทอง, ปึกเงิน, ตะกร้าชอปปิ้ง) |
| `define_bone` / `use_bone` / `set_anim` / `collider_from` / `finalize_and_save` | ริกกระดูก rest-exact (`u=0`), กล่องชน, Cycles Soft Plush Baker 512px, บันทึก `.blend` + เรนเดอร์สตูดิโอ `_preview.png` |

> **เคล็ดลับงบ tris (Zero-Decimation Rule):** เลือก segment (`segs`, `u`, `v`, `subsurf`) ให้พอดีตั้งแต่ต้นเพื่อให้จบต่ำกว่างบจริง (`<= budget`) โดยไม่ให้ระบบ auto-decimate ทำงาน จะได้ผิวโค้งไร้รอยบุบ 100% ทุกชิ้น และใช้ `render_lineup(blend_paths, out_png, rows=2)` เรนเดอร์ภาพรวมคอลเลกชันก่อน export จริง
