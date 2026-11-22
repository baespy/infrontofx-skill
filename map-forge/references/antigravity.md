# Antigravity & Blender MCP สำหรับงานแมพ

การตั้งค่าหลักของ Antigravity และเซิร์ฟเวอร์ `blender` MCP (26 เครื่องมือ) ใช้ชุดเดียวกับ `prop-forge` และ `weapon-forge` ไฟล์นี้ระบุกฎและขั้นตอนเฉพาะสำหรับงานปั้นแมพ

## 1. ที่อยู่ของ Skill & การซิงก์

| รายการ | พาธ |
| --- | --- |
| ต้นฉบับ (แก้ที่นี่เท่านั้น) | `<project>\.claude\skills\infrontofx\map-forge\` |
| สำเนาของ Antigravity | `<project>\.agents\skills\map-forge\` |
| คำสั่งซิงก์ | `& '<project>\.claude\skills\infrontofx\map-forge\scripts\sync-antigravity.ps1'` |

## 2. Blender 4.2.3 CLI vs Steam Blender 5.3 Live MCP

| โปรแกรม | พาธ | หน้าที่หลัก |
| --- | --- | --- |
| **Blender 4.2.3 CLI** (`BLENDER-v402`) | `C:\Tools\blender-4.2.3-windows-x64\blender.exe` | ปั้นไฟล์ต้นฉบับ, อบ Cycles AO, Export Sollumz 2.9 + PyMateria GEN8, ตรวจ `inspect_map.py`, เรนเดอร์พรีวิว 6 มุม |
| **Bundled Python 4.2** | `C:\Tools\blender-4.2.3-windows-x64\4.2\python\bin\python.exe` | รันสคริปต์วิเคราะห์ JSON/XML/binary ที่ไม่ต้องเปิด Blender (เครื่องนี้ไม่มี system `python` บน PATH และไม่มี Pillow — ใช้ `bpy.data.images` + `numpy`) |
| **Steam Blender 5.3 Live GUI** (`BLENDER17`) | `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe` | เปิดตรวจฉากแบบโต้ตอบผ่าน MCP (`localhost:9876`), จัดมุมกล้องสด, เช็กสัดส่วนกับตัวละคร (1.80m human dummy) |

**วิธีเปิด Blender 5.3 MCP server (กรณีไม่ได้รันอยู่):**
```powershell
& 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe' --online-mode --python-expr "import bpy; bpy.context.preferences.system.use_online_access = True; bpy.ops.blmcp.server_start()"
```

> [!CAUTION]
> **กฎเวอร์ชัน `.blend`:** ไฟล์ที่บันทึกจาก Blender 5.3 จะเป็นรูปแบบ `BLENDER17` ซึ่ง Blender 4.2.3 (ที่มี Sollumz 2.9) **เปิดไม่ได้!** ดังนั้นให้บันทึกไฟล์ต้นฉบับ `.blend` ทั้งหมดด้วย **Blender 4.2.3** เสมอ และใช้ Blender 5.3 เพื่อ inspect/preview แบบ read-only หรือส่งออก `.glb` กลับมาแปลงใน 4.2.3

## 3. กฎสำคัญเมื่อใช้งานบน Windows + MCP

- **พาธที่มีวงเล็บ `[...]`** (เช่น `[map]`, `[resources]`, `[1nfx]`):
  - ใน PowerShell ใช้ **`-LiteralPath`** เสมอ (ห้ามใช้ `-Path` เพราะ `[map]` จะถูกตีความเป็น wildcard แล้วหาไฟล์ไม่เจอ)
  - ใน Python ใช้ **`os.listdir()` / `os.walk()`** (ห้ามใช้ `glob.glob()` กับพาธที่มี `[...]`)
- **MCP `bpy.context.screen` เป็น `None`:** หลังสั่ง `bpy.ops.wm.open_mainfile()` ผ่าน `execute_blender_code` ตัวแปร `bpy.context.screen` มักเป็น `None` ให้วนผ่าน `bpy.context.window_manager.windows` เพื่อเข้าถึง `win.screen.areas` แทน
- **กฎมือขวาสำหรับการหมุนหลังคา/คานเอียง (Right-Hand Rule):**
  - หมุน `+rot_Y` จะทำให้ฝั่ง `+X` เอียง**ลงล่าง**
  - หมุน `-rot_X` จะทำให้ฝั่ง `+Y` เอียง**ลงล่าง**
  - ทุกครั้งที่ทำหลังคาจั่ว (gable), หลังคาปั้นหยา (hip), จันทัน หรือซุ้มโค้ง **ต้องเรนเดอร์มุมใกล้เช็กการเอียงจริง** ห้ามเดาจากเลข

## 4. เช็กลิสต์ตรวจภาพ 6 มุม (Mandatory Visual QA Before Export)

ก่อน export แมพทุกครั้ง ให้เรนเดอร์และเปิดดูภาพจริงครบ 6 มุม (EEVEE + ท้องฟ้าและแสงอาทิตย์จริง + ตัวหุ่นมนุษย์สูง `1.80m` ยืนเทียบสเกลที่จุดวาร์ป):

1. **Overview 3/4 (มุมสูงเฉียง):** เช็กซิลูเอตโดยรวม, การแบ่งโซน, สัดส่วนอาคารต่อลาน, ความสมดุลของต้นไม้
2. **Top-Down Plan (มุมบนตรง):** เช็กแนวทางเดิน (กว้าง >= 4m), ไม่วาง prop ขวางจุดวาร์ป/ทางเชื่อม, ระยะขอบเกาะ
3. **Player Eye-Level POV (มุมสายตาผู้เล่นที่จุดวาร์ป `z + 1.65m`):** เช็กความประทับใจแรก (First Impression), ความคมของพื้นหิน/ไม้ระยะใกล้, ไม่เบลอเป็นพลาสติก
4. **Hero Structure Close-Up:** เช็กรายละเอียดเสา คาน บัวพื้น จันทัน หลังคา ป้ายแบรนด์ ว่าไม่มีรอยต่อหลุดหรือ Z-fighting
5. **Seating / Walkway / Planter Detail:** เช็กขอบกระบะ, การฝังโคนต้นไม้/พุ่มไม้, ระยะม้านั่งกับทางเดิน
6. **Underside / Edge Check (เฉพาะ Sky Map):** เช็กขอบด้านข้างและใต้ฐานเกาะว่าเรียบร้อย ไม่มีหน้ากลับด้าน (backface) หรือแผ่นบางลอยเปลือย
