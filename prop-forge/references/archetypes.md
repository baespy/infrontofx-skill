# Archetypes

ทุก archetype อยู่ใน `scripts/blender/forge_prop.py` (`ARCHETYPES`) ขนาดเป็นเมตร ด้านหน้าหัน -Y ภาพตัวอย่างอยู่ใน `targets/`

| archetype | ใช้ในเกม | ขนาดเริ่มต้น (กว้าง x ลึก x สูง) | งบ tris | ชน | พารามิเตอร์ในสเปก |
| --- | --- | --- | --- | --- | --- |
| `sign_post` | จุดเบิกรถ, จุดพาวด์, ป้ายบอกทาง | 1.67 x 0.58 x 2.55 | 14000 | ฐาน เสา แผ่นป้าย | `label`, `sub`, `icon` (`house`), `board` (role ของหน้าป้าย), `text`, `sub_role`, `height`, `board_w`, `board_x` |
| `kiosk_sign` | ป้ายร้านตั้งพื้น | 0.96 x 0.44 x 1.35 | 11000 | ฐาน แผ่นป้าย | `label` |
| `atm` | ATM / ตู้ฝากถอน | 0.96 x 0.77 x 1.71 | 12000 | ฐาน ตัวตู้ | `label` |
| `safe` | ตู้เซฟ, ตู้เก็บของบ้าน | 1.10 x 1.02 x 1.11 | 14000 | ตัวตู้ | `label`, `w`, `d`, `h` |
| `crate` | stash, airdrop, กล่องรางวัล | 1.34 x 1.17 x 1.03 | 12000 | ตัวกล่อง | `w`, `d`, `h` |
| `chest` | loot, หีบสมบัติเปิดฝา | 0.81 x 0.61 x 0.80 | 10000 | ตัวหีบ | `open` (องศา 0 = ปิด), `coins`, `w`, `d`, `h` |
| `workbench` | โต๊ะคราฟต์ | 2.02 x 0.92 x 2.26 | 18000 | โต๊ะ ตู้ลิ้นชัก แผงหลัง | `w`, `d`, `top` |
| `mascot_marker` | marker ลอยเหนือจุด interaction | 1.00 x 0.64 x 0.91 | 5000 | ไม่มี | `radius` |

ทุก prop รับ `seed` (เปลี่ยนรูปหยดสไลม์และลอน), `palette` (ทับสีเฉพาะชิ้น ชิ้นนั้นจะได้ texture ของตัวเอง), `budget`, `lod_dist`, `collision: false`, `decals`, `text_resolution` (ความละเอียดตัวหนังสือ ค่าเริ่ม 2)

## สคีมาสเปก

```json
{
    "set": "1nfx_goo",
    "brand": { "name": "GOO LAB", "short": "GOO" },
    "font": "TitanOne-Regular.ttf",
    "palette": { "primary": "#8E2DE2", "accent": "#C9F31D", "light": "#F4F0E8", "dark": "#221E28", "gold": "#FFC62E" },
    "props": [
        { "id": "1nfx_goo_garage", "archetype": "sign_post", "label": "GARAGE", "icon": "house" },
        { "id": "1nfx_goo_atm", "archetype": "atm", "decals": [{ "image": "art/goo_logo.png", "side": "left", "center": [0.0, 0.9], "width": 0.4 }] }
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
| `b.skirt(w, d, z_top, role, max_drop, drops_per_side, sides)` | สไลม์ไหลรอบขอบบนของกล่อง |
| `b.curtain(x0, x1, z_top, y_front, role, max_drop, drops)` | ม่านสไลม์ไหลจากขอบแนวนอน (ใต้แผ่นป้าย ขอบโต๊ะ) |
| `b.crown(loc, radius, height, tilt)` | มงกุฎ 5 แฉก |
| `b.mascot(loc, radius, role, eye_role, direction, drips)` | หัวมาสคอตตา X |
| `b.x_mark(center, direction, size, role)`, `b.star(loc, size, role, direction)` | ตา X, ดาวประกาย |

- `M` คือ matrix ของกลุ่ม (เช่น `Matrix.Translation((x, 0, z))` ของแผ่นป้าย) ทุกชิ้นในกลุ่มขยับตามกัน
- `collide=True` เพิ่มกล่องชนจากขอบเขตของชิ้นนั้น ใส่เฉพาะชิ้นใหญ่ที่ผู้เล่นเดินชน 1-4 กล่องต่อ prop
- สร้างจากพื้น z = 0 ขึ้นไป หันหน้า -Y สคริปต์จะจัดกึ่งกลาง X/Y และวางจุดต่ำสุดที่ z = 0 ให้เองตอนจบ
- รันด้วย `--only <id> --no-render` ดู tris ใน `report.json` ก่อน แล้วค่อยเรนเดอร์ ตัวหนังสือกิน tris มากที่สุด ถ้าเกินงบให้ลด `text_resolution`, ตัดตัวหนังสือด้านหลัง หรือย่อ `max_w`
