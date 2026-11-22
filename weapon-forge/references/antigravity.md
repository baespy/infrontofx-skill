# Antigravity & Blender MCP

ใช้เมื่อทำงานผ่าน Google Antigravity หรือเชื่อม Blender เข้ากับ agent ผ่าน MCP ข้อมูลตรวจยืนยันล่าสุดเมื่อ 2026-11-16 รัน `scripts/doctor.ps1` เพื่อดูสถานะปัจจุบันทุกครั้ง

## สถานะในเครื่องนี้

| รายการ | สถานะจริงบนเซิร์ฟเวอร์ |
| --- | --- |
| Antigravity CLI | `agy 1.5.9` ที่ `%USERPROFILE%\.gemini\bin\agy.exe` |
| ต้นฉบับ Skill (Source of Truth) | `.claude\skills\infrontofx\weapon-forge\` (**แก้ไฟล์ที่นี่เท่านั้น**) |
| สำเนา Skill ของ Antigravity | `.agents\skills\weapon-forge\` (ซิงก์ด้วย `scripts\sync-antigravity.ps1`) |
| Blender 4.2.3 (Headless CLI & Export) | `4.2.3` ที่ `C:\Tools\blender-4.2.3-windows-x64\blender.exe` (ฟอร์แมต `BLENDER-v402` เปิดได้ทั้ง 4.2.3 และ 5.3) |
| Steam Blender 5.3 (Live GUI + MCP) | `5.3` ที่ `C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe` พร้อม extension ทางการ `bl_ext.lab_blender_org.mcp` บน `localhost:9876` |
| `uv` สำหรับ Blender MCP | `<home>\blender-mcp\uv.exe` |
| MCP Config ที่เชื่อมต่ออยู่ | `%USERPROFILE%\.gemini\antigravity\mcp_config.json` (server ชื่อ `"blender"`) |
| สคีมาเครื่องมือ MCP ทั้ง 26 ตัว | `%USERPROFILE%\.gemini\antigravity\mcp\blender\*.json` และ `instructions.md` |

## กฎบังคับสำหรับโฟลเดอร์ที่มี `[...]` (`[resources]`, `[weapon]`, `[1nfx]`) ทั้งใน PowerShell และ Python

ทั้งพารามิเตอร์ `-Path` ของ Windows PowerShell 5.1 **และ `glob.glob` ของ Python** ต่างตีความวงเล็บเหลี่ยม `[resources]`, `[weapon]`, `[1nfx]`, `[core]` เป็น **Wildcard Character Class** ทำให้หาไฟล์ไม่เจอเงียบ ๆ:
- **ใน PowerShell ใช้ `-LiteralPath` เสมอ** (`Get-ChildItem`, `Get-Item`, `Get-Content`, `Set-Content`, `Test-Path`, `Resolve-Path`, `Remove-Item`, `Select-String`) และห้ามใช้ `Copy-Item -LiteralPath "$src\*"` ให้ใช้ **`robocopy $src $dst /E`** หรือ `[IO.File]::Copy($srcFile, $dstFile, $true)` แทนเสมอ
- **ใน Python / Blender `bpy` ห้ามใช้ `glob.glob(path)` ตรง ๆ กับพาธที่มี `[resources]` หรือ `[weapon]`:** ให้ใช้ **`os.listdir(d)`** หรือ **`glob.glob(glob.escape(d) + "/*.blend")`** เสมอ!

## การเปิด Live Steam Blender 5.3 GUI คู่กับ Official `mcp` Extension (`localhost:9876`) และกฎความเข้ากันได้ของไฟล์ `.blend`

### 1. วิธีเปิด Live GUI + `bl_ext.lab_blender_org.mcp`
บนเครื่องนี้ติดตั้ง extension MCP ทางการจาก `https://lab.blender.org/` (`bl_ext.lab_blender_org.mcp`, ตั้ง `prefs.use_autostart = True` แล้ว) บน Steam Blender 5.3 เมื่อต้องการเปิดหน้าต่าง GUI สดให้รับคำสั่ง MCP ทันทีบน `localhost:9876` ให้รัน:

```powershell
& 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe' --online-mode --python-expr "import bpy; bpy.context.preferences.system.use_online_access = True; bpy.ops.blmcp.server_start()"
```

เมื่อซ็อกเก็ต `localhost:9876` ทำงานแล้ว เครื่องมือ Live GUI ของเซิร์ฟเวอร์ `"blender"` (`execute_blender_code`, `get_objects_summary`, `get_object_detail_summary`, `render_viewport_to_path`, `get_screenshot_of_blender_window` ฯลฯ) จะเชื่อมเข้ากับฉากสดได้โดยตรง (ห้ามให้สอง agent ยิงเข้าซ็อกเก็ตเดียวกันพร้อมกัน)

### 2. กฎเหล็กความเข้ากันได้ของไฟล์ `.blend`: Blender 5.3 (`BLENDER17`) vs Blender 4.2.3 (`BLENDER-v402`)
- ไฟล์ `.blend` ที่บันทึกจาก **Blender 5.0+ / 5.3** จะเขียน header ฟอร์แมตใหม่ **`BLENDER17`** ซึ่ง **Blender 4.2.3 CLI เปิดไม่ได้** (`Error: File format is not supported ... not a blend file`) ทำให้สคริปต์ CLI อย่าง `validate_model.py` หรือ `export_ydr.py` ที่รันผ่าน `C:\Tools\blender-4.2.3-windows-x64\blender.exe` ล้มเหลวทันที!
- ในทางกลับกัน ไฟล์ `.blend` ที่บันทึกผ่าน **Blender 4.2.3** (`BLENDER-v402` header, `bpy.ops.wm.save_as_mainfile(filepath=...)`) **สามารถเปิดได้สะอาดไร้คำเตือนทั้งใน Blender 4.2.3 CLI และใน Steam Blender 5.3 GUI!**
- **แนวปฏิบัติมาตรฐาน:** สร้าง/บันทึกไฟล์ต้นฉบับ `<model>.blend` ใน `weapon_<id>/source/` ด้วย Blender 4.2.3 (`BLENDER-v402`) เพื่อให้ `validate_model.py` และ `export_ydr.py` รันได้ตลอดเวลา และเปิดไฟล์นั้นขึ้นตรวจ/ปั้นแต่งมุมกล้องแบบโต้ตอบใน Blender 5.3 Live MCP (หากปั้นแก้ใน 5.3 เสร็จและต้องการเก็บไฟล์ถาวรสำหรับ CLI 4.2.3 ให้ส่งออก/บันทึกผ่าน 4.2.3 หรือสคริปต์สร้างฉากของ 4.2.3 เสมอ)

## ที่อยู่ของ Skill และการซิงก์

[เอกสาร Antigravity](https://antigravity.google/docs/skills) กำหนดให้ skill ของ workspace อยู่ที่ `.agents/skills/<ชื่อ>/` ใน `SKILL.md` ต้องมี YAML frontmatter ที่มี `name` และ `description` ครบถ้วนจึงใช้ร่วมกันได้ทั้ง Claude Code และ Antigravity

ต้นฉบับในพื้นที่งานนี้อยู่ที่ `.claude\skills\infrontofx\weapon-forge` ห้ามแก้สำเนาใน `.agents\skills\weapon-forge` โดยตรง เมื่อแก้ไขเอกสารหรือสคริปต์เสร็จทุกครั้งต้องรัน:

```powershell
& '<project>\.claude\skills\infrontofx\weapon-forge\scripts\sync-antigravity.ps1'
```

สคริปต์จะเดินหาโฟลเดอร์ `.claude` อัตโนมัติ คัดลอกไฟล์ทั้งหมดไปยัง `.agents\skills\weapon-forge` และหยุดเตือนทันทีหากพบว่าไฟล์ฝั่ง `.agents` ถูกแก้ไขใหม่กว่าต้นฉบับ (ส่ง `-Check` เพื่อตรวจความตรงกันโดยไม่เขียนทับ หรือ `-Force` เมื่อตั้งใจเขียนทับ)

## แบ่งงานระหว่าง CLI Scripts กับ Blender MCP

| งาน | เครื่องมือที่เหมาะที่สุด |
| --- | --- |
| สร้างฐานโมเดลครบชุดที่แกน ขนาด และกระดูกถูก 100% | `scripts/blender/forge_weapon.py` |
| ปั้นแก้รูปทรงละเอียด ตรวจ datablock หรือเรนเดอร์ดูทีละจุด | Antigravity + `blender` MCP (`execute_blender_code` / `*_for_cli`) |
| แยกโมเดล AI ทั้งชุดในไฟล์เดียวหรือชิ้นเดียว | `scripts/blender/split_ai_set.py` |
| นำเข้าโมเดลภายนอกชิ้นเดียวอย่างรวดเร็ว | `scripts/blender/import_ai_model.py` |
| ตรวจสัญญาช่องอาวุธ กระดูก และความสะอาดหน่วยความจำ | `scripts/blender/validate_model.py` + `references/bone-and-memory-safety.md` |
| คอมไพล์ `.ydr` / `.ytd` (DXT5 + mipmaps) และตรวจไบนารี | `scripts/blender/export_ydr.py` + `scripts/inspect-ydr.ps1` |
| เชื่อมเข้าระบบ `[1nfx]` และตรวจครบวงจร | `references/integration.md` + `scripts/check-skin.ps1` |

**หนึ่งสกิน หนึ่ง agent:** อย่าให้สอง agent เปิดหรือเขียนโฟลเดอร์ `weapon_<id>` เดียวกันหรือยิงคำสั่งเข้า live Blender GUI พร้อมกัน เช็กเวลาแก้ไขไฟล์ล่าสุดก่อนลงมือเสมอ

## เซิร์ฟเวอร์ `blender` MCP ที่เชื่อมต่ออยู่จริง (26 เครื่องมือ)

การตั้งค่าใน `%USERPROFILE%\.gemini\antigravity\mcp_config.json`:

```json
{
  "mcpServers": {
    "blender": {
      "command": "<home>\\blender-mcp\\uv.exe",
      "args": [
        "run",
        "--project",
        "<home>\\blender-mcp",
        "blender-mcp"
      ]
    }
  }
}
```

เครื่องมือของเซิร์ฟเวอร์ `"blender"` แบ่งเป็น **3 กลุ่มหลัก** (รองรับทั้งโหมดต่อ Blender GUI สด และโหมด CLI ไร้หน้าต่างเมื่อไม่ได้เปิด GUI!):

### 1. เครื่องมือโหมด CLI ไร้หน้าต่าง (`*_for_cli` — ใช้ได้ทันทีกับไฟล์ `.blend` บนดิสก์โดยไม่ต้องเปิด Blender GUI)

| เครื่องมือ MCP | พารามิเตอร์หลัก | หน้าที่ |
| --- | --- | --- |
| `execute_blender_code_for_cli` | `blend_file`, `code` | เปิดไฟล์ `.blend` ด้วย `blender --background` แล้วรันโค้ด Python (`bpy`) คืนค่าผ่านตัวแปร `result = {...}` |
| `get_blendfile_summary_datablocks_for_cli` | `blend_file` | สรุปจำนวน datablocks ทุกประเภท, workspace และ render engine ของไฟล์ `.blend` |
| `get_blendfile_summary_missing_files_for_cli` | `blend_file` | ตรวจหาไฟล์ภายนอกที่หลุดหรือหาไม่เจอ (เช่น path รูป `.dds`/`.png` ขาดแบบ `3433.dds` ในสกินเก่า) |
| `get_blendfile_summary_of_linked_libraries_for_cli` | `blend_file` | แสดงโครงสร้าง library ที่ถูก link เข้ามาในไฟล์ |
| `get_blendfile_summary_path_info_for_cli` | `blend_file` | ดู path สถานะการบันทึก อายุไฟล์ และไฟล์สำรอง |
| `get_blendfile_summary_usage_guess_for_cli` | `blend_file` | ประเมินลักษณะการใช้งานหลักของไฟล์ `.blend` |

### 2. เครื่องมือโหมดเชื่อมต่อ Blender GUI สด (Live Interactive Session)

ต้องเปิดโปรแกรม Blender พร้อมเปิดใช้งาน MCP add-on เชื่อมต่อบน `localhost`:

| เครื่องมือ MCP | พารามิเตอร์หลัก | หน้าที่ |
| --- | --- | --- |
| `get_objects_summary` | - | ดูลำดับชั้น Collection และรายชื่อวัตถุทั้งหมดในฉาก (ชื่อ, ชนิด, parent, data, visibility) |
| `get_object_detail_summary` | `name` | ดูรายละเอียดเชิงลึกของวัตถุรายชิ้น (transform, parent/children, modifiers, constraints, materials) |
| `execute_blender_code` | `code` | รันโค้ด Python `bpy` ในหน้าต่าง Blender สด (เก็บข้อมูลส่งกลับในตัวแปร dict ชื่อ `result`) |
| `render_viewport_to_path` | `output_path` | เรนเดอร์ฉากปัจจุบันออกเป็นไฟล์ภาพตาม render settings ปัจจุบัน แล้วเปิดดูด้วย `read_file` |
| `render_thumbnail_to_path` | `output_path` | เรนเดอร์ภาพตัวอย่างขนาดเล็กอย่างรวดเร็วลง `output_path` |
| `get_screenshot_of_area_as_image` | `area_ui_type`, `size_limit_in_bytes` | จับภาพหน้าจอเฉพาะพื้นที่ เช่น `VIEW_3D`, `UV`, `ShaderNodeTree`, `OUTLINER` เป็น PNG |
| `get_screenshot_of_window_as_image` | `size_limit_in_bytes` | จับภาพหน้าต่าง Blender ทั้งหมดเป็น PNG |
| `get_screenshot_of_window_as_json` | - | อ่านโครงหน้าต่าง พื้นที่ย่อย วัตถุที่ active และวัตถุที่ถูกเลือกเป็น JSON |
| `jump_to_view3d_object_by_name` / `..._object_data_by_name` | `name`, `allow_edits` | เลื่อนมุมกล้อง 3D Viewport โฟกัสไปยังวัตถุหรือ datablock ที่ระบุ |
| `jump_to_tab_by_name` / `jump_to_tab_by_space_type` | `name` / `space_type` | สลับแท็บ Workspace ไปยังพื้นที่ทำงานที่ต้องการ |
| `get_blendfile_summary_datablocks` / `_missing_files` / `_of_linked_libraries` / `_path_info` / `_usage_guess` | - | ตรวจสถานะไฟล์ `.blend` ที่เปิดค้างอยู่ใน Blender สด |

### 3. เครื่องมือค้นคู่มือ Blender API แบบออฟไลน์ (ห้ามเดาชื่อพารามิเตอร์ `bpy`)

| เครื่องมือ MCP | พารามิเตอร์หลัก | หน้าที่ |
| --- | --- | --- |
| `get_python_api_docs` | `identifier` | อ่านเอกสาร RST ของ `bpy` / `bmesh` / `mathutils` ตรงตามชื่อ เช่น `"bpy.ops.object.transform_apply"` หรือ `"bmesh.ops.*"` |
| `search_api_docs` | `query`, `context`, `max_results` | ค้นหาแบบเต็มคำใน Blender Python API Reference |
| `search_manual_docs` | `query`, `context`, `max_results` | ค้นหาแนวคิดและขั้นตอนจากคู่มือผู้ใช้ Blender |

**ความปลอดภัย:** Socket ของ Blender MCP ใช้เฉพาะ `localhost` เท่านั้น ห้ามเปิดพอร์ตออกอินเทอร์เน็ตบนเครื่องเซิร์ฟเวอร์จริง และปิด add-on เมื่อจบงานปั้น

## กฎเหล็กเมื่อเขียนโค้ดผ่าน `execute_blender_code` / `execute_blender_code_for_cli`

1. **ส่งข้อมูลกลับผ่านตัวแปร `result` (ไม่ใช่ `print`)**: กำหนด `result = {"ok": True, "tris": ...}` เพื่อให้ MCP ส่ง JSON กลับมาอย่างแม่นยำ
2. **ตั้ง Mode, Active Object และ Selection เองทุกครั้ง**: อย่าเดาสถานะค้างจากคำสั่งก่อนหน้า เช็ก `bpy.ops.object.mode_set(mode="OBJECT")` และตั้ง `bpy.context.view_layer.objects.active = obj` ก่อนรัน `bpy.ops`
3. **ใช้ `bmesh` แล้วต้อง flush กลับเสมอ**: หลังแก้ไขรูปทรงให้เรียก `bm.to_mesh(me)`, `bm.free()`, `me.update()` และอัปเดต depsgraph (`bpy.context.evaluated_depsgraph_get()`) ก่อนอ่านค่าขอบเขตโมเดล
4. **ล้าง Orphan Datablocks และถอดวัสดุ Procedural หลัง Bake ก่อนเซฟทุกครั้ง**: ถอดวัสดุโหนดซับซ้อนที่ใช้ตอน bake ออกจาก mesh หลังรวมเป็นวัสดุเดียว แล้วรัน `bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)` จะคุม RAM ของ Cycles ให้นิ่งอยู่ที่ราว `~80 MB` ตลอดการปั้นทั้ง 6–7 ชิ้น (และเปลี่ยนชื่อเมชเป็น `Gun_Root` ก่อนสร้าง Armature `model_name` เพื่อไม่ให้ชื่อติด `.001`)
5. **ทางเลือกเรียก `blmcp` CLI Helper เมื่อรันใน Sub-Worker ที่ไม่ได้แนบ MCP Socket ตรง**: หาก worker ย่อยไม่มีรายการ MCP tool ติดมาในเซสชัน สามารถเรียกเอนจินเดียวกันของ `blender-mcp` ได้ผ่าน `<home>\blender-mcp\uv.exe run --project <home>\blender-mcp python -c "..."` โดยตั้ง `BLENDER_PATH=C:\Tools\blender-4.2.3-windows-x64\blender.exe` แล้วเรียก `blmcp.tools_helpers.blender_cli.run_blender_cli(blend_file, code)` (กำหนดตัวแปร `result = {...}` แทนการใช้ `return`)
6. **ห้ามทำลายสัญญาโครงกระดูก (`references/bone-and-memory-safety.md`)**:
   - ห้ามเปลี่ยนชื่อ Armature (`w_me_<id>_<slot>` / `w_pi_<id>_revolver`) หรือชื่อกระดูก (`Gun_Root`, `Gun_GripR`, `Gun_Main_Bone`, `Gun_GripL`, `Gun_Muzzle`, `WAPClip` ฯลฯ)
   - ห้ามขยับ origin ของ `Gun_Root` ออกจาก `(0, 0, 0)` และห้ามทิ้ง unapplied transform ไว้บน Armature หรือ Mesh
   - ห้ามแก้ไฟล์ใน resource ที่มี `.fxap`

## วงจรปั้นและตรวจผ่าน MCP

1. สำรวจฉากด้วย `get_objects_summary` / `get_object_detail_summary` (หรือ `get_blendfile_summary_datablocks_for_cli` + `get_blendfile_summary_missing_files_for_cli` ในโหมด CLI)
2. แก้รูปทรงทีละส่วนแล้วเรนเดอร์ตรวจมุมด้านข้าง ด้านหน้า และมุม 3/4 ด้วย `render_viewport_to_path` (เปิดดูภาพจริงด้วย `read_file` ทุกรอบ เทียบกับเกณฑ์ใน `style-families.md`)
3. รันตัวตรวจสัญญาช่องอาวุธ:

```python
import runpy
check = runpy.run_path(r"<project>\.claude\skills\infrontofx\weapon-forge\scripts\blender\validate_model.py")["validate_scene"]
result = {"report": check("knife")}
```

4. กวาดล้าง orphan datablocks บันทึก `.blend` แล้วส่งออก `.ydr` + `.ytd` ด้วย `export_ydr.py` และตรวจไบนารีด้วย `scripts/inspect-ydr.ps1` จนได้ `RESULT fail=0` ทั้งคู่

## โมเดลจาก AI

ตรวจเงื่อนไขสิทธิ์เชิงพาณิชย์ล่าสุดจากหน้าทางการของผู้ให้บริการก่อนใช้งานเสมอ:

| บริการ | เงื่อนไขเท่าที่พบ | จุดเด่น |
| --- | --- | --- |
| Tripo | แผนจ่ายเงินใช้เชิงพาณิชย์ได้ | retopology ดี แยกชิ้นด้วย `split_ai_set.py` ได้สะอาด |
| Meshy | แผนฟรีเพื่อส่วนตัวและการศึกษาเท่านั้น | ใช้ง่าย |
| Rodin | ตรวจเงื่อนไขแผนล่าสุดก่อนขาย | โครง quad ดี |
| Hunyuan3D | โอเพนซอร์ส (มีเงื่อนไขพื้นที่/จำนวนผู้ใช้ในสัญญา) | รันบนเครื่องตัวเองได้ |

ผลลัพธ์จาก AI ต้องผ่าน `split_ai_set.py` หรือ `import_ai_model.py` เพื่อจัดแกนตามมาตรฐาน `[1nfx]`, ลดโพลีให้อยู่ในงบ `8k–25k tris`, ลบเศษเกาะลอย (`--strip-islands`), ผูกกระดูกและอบเท็กซ์เจอร์ DXT5 พร้อมตรวจ `validate_model.py` + `inspect-ydr.ps1` ทุกชิ้นก่อนนำเข้าเซิร์ฟเวอร์
