# Antigravity & Blender MCP

การตั้งค่า Antigravity, Blender 4.2.3 / 5.3, เซิร์ฟเวอร์ `blender` MCP (26 เครื่องมือ) และกฎ `-LiteralPath` กับพาธที่มี `[...]` ใช้ชุดเดียวกับ weapon-forge อ่านรายละเอียดใน `../weapon-forge/references/antigravity.md` ไฟล์นี้บอกเฉพาะส่วนที่ต่างสำหรับ prop

## ที่อยู่ของ skill

| รายการ | พาธ |
| --- | --- |
| ต้นฉบับ (แก้ที่นี่เท่านั้น) | `<project>\.claude\skills\infrontofx\prop-forge\` |
| สำเนาของ Antigravity | `<project>\.agents\skills\prop-forge\` |
| ซิงก์ | `& '<project>\.claude\skills\infrontofx\prop-forge\scripts\sync-antigravity.ps1'` |

สคริปต์ซิงก์หยุดและเตือนถ้าไฟล์ฝั่ง `.agents` ถูกแก้ใหม่กว่าต้นฉบับ ให้ย้ายการแก้นั้นกลับมาที่ต้นฉบับก่อน แล้วค่อยซิงก์ (`-Force` เมื่อตั้งใจเขียนทับ)

## แบ่งงาน

| งาน | ใช้ |
| --- | --- |
| สร้างทั้งชุดหรือทีละชิ้นจากสเปก | `forge_prop.py` ผ่าน Blender 4.2.3 CLI |
| ปรับสี ป้าย ขนาด หยดสไลม์ | แก้สเปกแล้วรัน `--only <id>` (เร็วกว่าและทำซ้ำได้) |
| ปั้นแก้รูปทรงเฉพาะจุดที่สเปกทำไม่ได้ | Blender 5.3 สด + `execute_blender_code` แล้วเรนเดอร์ดูด้วย `render_viewport_to_path` |
| ตรวจก่อน export | `validate_prop.py` (headless หรือผ่าน MCP) |
| เพิ่ม archetype ใหม่ให้ใช้ซ้ำได้ | เขียน builder ใน `forge_prop.py` ตาม `archetypes.md` |

ถ้าแก้ชิ้นไหนด้วยมือใน Blender สด ให้จดไว้ใน `source/manual-edits.md` ของงาน เพราะการรัน `forge_prop.py` ซ้ำจะเขียนทับ `.blend` นั้น

## วงจรผ่าน MCP

1. สร้างชิ้นด้วย CLI ก่อน (ได้ `.blend` รูปแบบ 4.2 ที่ทั้ง 4.2.3 และ 5.3 เปิดได้)
2. เปิดไฟล์ใน Blender 5.3 สด ดูโครงด้วย `get_objects_summary` และ `get_object_detail_summary` ของ `<id>`
3. แก้ด้วย `execute_blender_code` ตั้ง mode, active object และ selection เองทุกครั้ง ใช้ `bmesh` แล้ว `bm.to_mesh` + `bm.free` ส่งผลกลับใน `result = {...}`
4. เรนเดอร์ด้านหน้า ด้านข้าง และ 3/4 ด้วย `render_viewport_to_path` แล้วเปิดดูภาพจริงทุกรอบ เทียบเกณฑ์ใน `style-toybrand.md`
5. ตรวจสัญญา:

```python
import runpy
check = runpy.run_path(r"<project>\.claude\skills\infrontofx\prop-forge\scripts\blender\validate_prop.py")["validate_scene"]
result = {"report": check("1nfx_goo_atm")}
```

6. ล้าง orphan แล้วบันทึก ไฟล์ที่บันทึกจาก 5.3 จะเป็นรูปแบบ `BLENDER17` ซึ่ง 4.2.3 CLI เปิดไม่ได้ ถ้าต้องใช้ CLI ต่อ ให้ export ชิ้นนั้นเป็น `.glb` จาก 5.3 แล้วนำเข้าและบันทึกด้วย 4.2.3 หรือทำ validate และ export ต่อใน 5.3 เลย

## กฎเมื่อแก้ผ่าน MCP

- ห้ามเปลี่ยนชื่อ mesh `<id>` หรือ `<id>_col_N` และห้ามย้าย origin ออกจากกลางพื้น
- ห้ามทิ้ง modifier ค้างไว้ตอนส่ง export ให้ apply ก่อน
- วัสดุใหม่ต้องอ้าง texture เดิมของชุด (`<set>_palette`) และ map UV ไปที่ช่องสีที่มีอยู่ ถ้าต้องการสีใหม่ ให้เพิ่ม role ใน `palette` ของสเปกแล้วรันใหม่ แทนการสร้างวัสดุสีเรียบเพิ่ม
- หนึ่งชุด prop หนึ่ง agent และห้ามสอง agent ยิงคำสั่งเข้าซ็อกเก็ต Blender สดตัวเดียวกันพร้อมกัน
