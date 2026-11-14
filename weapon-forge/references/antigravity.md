# Antigravity

ใช้เมื่อทำงานผ่าน Google Antigravity หรือเชื่อม Blender เข้ากับ agent ผ่าน MCP ข้อมูลตรวจเมื่อ 2026-11-08 รัน `scripts/doctor.ps1` เพื่อดูสถานะล่าสุด

## สถานะในเครื่องนี้

| รายการ | สถานะ |
| --- | --- |
| Antigravity CLI | `agy` 1.5.3 ที่ `%USERPROFILE%\.gemini\bin\agy.exe` (ไม่อยู่ใน PATH) |
| Skill ของ workspace | `.agents/skills/` |
| MCP config | `%USERPROFILE%\.gemini\config\mcp_config.json` ยังไม่มี server |
| `uv` / `uvx` | ไม่มี ต้องใช้กับ `mcp-for-blender` |

**ยังไม่ได้ทดสอบ:** Antigravity โหลด skill นี้จริง และการต่อ Blender ผ่าน MCP บนเครื่องนี้

## ที่อยู่ของ skill

[เอกสาร Antigravity](https://antigravity.google/docs/skills) กำหนดให้ skill ของ workspace อยู่ที่ `.agents/skills/<ชื่อ>/` (`.agent/skills` ยังใช้ได้เพื่อความเข้ากันได้) และ skill รวมอยู่ที่ `~/.gemini/config/skills/` ใน `SKILL.md` ต้องมี `description` ส่วน `name` ใส่หรือไม่ก็ได้ ไฟล์นี้จึงใช้ร่วมกับ Claude Code ได้โดยไม่ต้องแก้

ต้นฉบับอยู่ที่ `.claude/skills/weapon-forge` แก้ที่นี่เท่านั้น แล้วรัน:

```powershell
.claude\skills\weapon-forge\scripts\sync-antigravity.ps1
```

สคริปต์จะคัดลอกไป `.agents/skills/weapon-forge` และหยุดถ้าสำเนานั้นมีการแก้ที่จะหายไป ใช้สำเนาแทน junction เพราะเอกสารไม่ได้ระบุว่า Antigravity ตาม junction บน Windows

[Rules](https://antigravity.google/docs/rules) จำกัด 24,000 bytes ต่อไฟล์ และ [Workflows ถูกประกาศเลิกใช้แล้ว](https://antigravity.google/docs/ide/workflows) อย่าสร้าง workflow ใหม่สำหรับงานนี้ ให้ใช้ skill

## แบ่งงานกัน

| งาน | ใช้ |
| --- | --- |
| ฐานโมเดลที่สเกลและโครงถูก | `forge_weapon.py` |
| รูปทรงละเอียด แก้ทีละจุดแล้วดูผล | Antigravity + Blender MCP |
| โมเดลจาก AI ทั้งชุดหรือชิ้นเดียว | `split_ai_set.py` |
| ลองโมเดลจาก AI หรือที่ซื้อมาแบบเร็ว ๆ | `import_ai_model.py` |
| ตรวจก่อน export | `validate_model.py` |
| สร้าง `.ydr` และตรวจไฟล์ | ดู `modeling-pipeline.md` และ `inspect-ydr.ps1` |
| เชื่อมระบบและ QA | `integration.md` |

**หนึ่งสกิน หนึ่ง agent.** Antigravity, Codex และ Claude Code เขียนโฟลเดอร์เดียวกันได้พร้อมกัน ถ้าสองตัวทำ `weapon_<id>` เดียวกันไฟล์จะทับกัน ก่อนเริ่มให้ดูเวลาแก้ล่าสุดในโฟลเดอร์นั้น

## ต่อ Blender ผ่าน MCP

แนะนำ [`ahujasid/mcp-for-blender`](https://github.com/ahujasid/blender-mcp) (เดิมชื่อ `blender-mcp`, MIT, อัปเดต พ.ย. 2026) เพราะมีตัวอย่าง config สำหรับ Antigravity และยังดูแลอยู่ ส่วน [`kc0ed/Blender-MCP-For-Antigravity`](https://glama.ai/mcp/servers/@kc0ed/Blender-MCP-For-Antigravity) กับ [`MITHRAN-BALACHANDER/Blender-MCP-antigravity`](https://glama.ai/mcp/servers/@MITHRAN-BALACHANDER/Blender-MCP-antigravity) ทำมาเฉพาะ Antigravity แต่ Glama แสดงสถานะ Inactive

การติดตั้งเปลี่ยนแปลงเครื่องของผู้ใช้ ต้องถามก่อน:

1. ติดตั้ง `uv` จากตัวติดตั้งทางการ (README เตือนว่าอย่าใช้ `pip install uv`)
2. รัน `uvx mcp-for-blender install-addon`
3. เปิด Blender เปิด add-on `Interface: MCP for Blender` แล้วกดเริ่ม server จาก N-panel
4. เพิ่มใน `%USERPROFILE%\.gemini\config\mcp_config.json` ([รูปแบบ](https://antigravity.google/docs/mcp)):

```json
{
  "mcpServers": {
    "blender-mcp": {
      "command": "<user-home>\\.local\\bin\\uvx.exe",
      "args": ["mcp-for-blender"],
      "env": {
        "BLENDER_HOST": "localhost",
        "BLENDER_PORT": "9876",
        "BLENDER_MCP_SAFE_MODE": "1"
      }
    }
  }
}
```

ใส่ path เต็มของ `uvx` ตามที่ติดตั้งจริง เพราะ README เตือนเรื่อง `spawn uvx ENOENT` บน Windows

**ความปลอดภัย.** socket ของ add-on ไม่มีการยืนยันตัวตนและไม่เข้ารหัส ใครเข้าถึงพอร์ตได้ก็รัน Python ใน Blender ได้ ให้ใช้เฉพาะ `localhost` อย่าเปิดพอร์ตออกอินเทอร์เน็ต เครื่องนี้เป็น Windows Server ที่รันงานจริง จึงควรเปิด add-on เฉพาะตอนปั้น และอ่านหัวข้อ telemetry ใน README

| เครื่องมือ MCP | ใช้ทำอะไร |
| --- | --- |
| `get_scene_info` | ดูวัตถุในฉาก |
| `execute_blender_code` | รัน Python ใน Blender |
| `look` | ดูภาพจาก viewport หลายมุม |
| `generate_3d` | สร้างโมเดลด้วย Tripo, Hunyuan3D, Rodin หรือ Meshy |
| `search_assets`, `import_asset` | ดึงจาก Poly Haven, Sketchfab, Poly Pizza |

## วงจรปั้นผ่าน MCP

1. เปิด `weapon_<id>/source/<model>.blend` แล้ว `get_scene_info`
2. แก้ทีละอย่างด้วย `execute_blender_code`
3. `look` อย่างน้อยด้านข้าง ด้านหน้า และมุม 3/4 เทียบกับ DNA ของ family ใน `style-families.md`
4. ตรวจสัญญาของช่องอาวุธ:

```python
import runpy
path = r"<skill-dir>\scripts\blender\validate_model.py"
print(runpy.run_path(path)["validate_scene"]("knife"))
```

5. ไม่มี FAIL แล้วจึงบันทึก `.blend` จากนั้น bake และ export ตาม `modeling-pipeline.md`

ห้ามเปลี่ยนชื่อ armature หรือ bone, ห้ามขยับ origin ของ `Gun_Root`, ห้ามทิ้ง transform ค้างที่ armature หรือ mesh และห้ามให้ MCP แก้ไฟล์ใน `weapon_core` หรือ resource ที่มี `.fxap`

## ข้อความเริ่มงานใน Antigravity

```text
ใช้ skill weapon-forge ปั้น <ช่องอาวุธ> ของสกิน <id> ตามสไตล์ <family> ใน style-families.md
รัน scripts/doctor.ps1 ก่อน และห้ามแตะ resource ที่มี .fxap
เปิด weapon_<id>/source/<model>.blend แก้ทีละอย่าง ดูผลด้วย look ทุกรอบ
ก่อนบันทึกต้องผ่าน validate_model.py ไม่มี FAIL หยุดรอผมดูรูปก่อน bake
```

## โมเดลจาก AI

ทุกบริการต้องตรวจเงื่อนไขล่าสุดจากหน้าทางการของผู้ให้บริการก่อนใช้ เพราะข้อมูลด้านล่างมาจากบทความรีวิวและบางแหล่งขัดกันเอง

| บริการ | เงื่อนไขเท่าที่พบ | จุดเด่น |
| --- | --- | --- |
| Tripo | แผนจ่ายเงินใช้เชิงพาณิชย์ได้ แผนฟรีแหล่งข้อมูลขัดกัน | retopology ดี |
| Meshy | แผนฟรีเพื่อส่วนตัวและการศึกษาเท่านั้น | ใช้ง่าย |
| Rodin | แหล่งข้อมูลขัดกันเรื่องแผนฟรี | ออกแบบ quad ได้ เก่งงานตัวละคร |
| Hunyuan3D | โอเพนซอร์ส แต่สัญญามีข้อจำกัดเรื่องพื้นที่และจำนวนผู้ใช้ | รันเองได้ |

ที่มา: [cinevva](https://app.cinevva.com/guides/ai-3d-model-generators), [3daistudio](https://www.3daistudio.com/blog/rodin-2-5-vs-tripo-vs-hunyuan-3d-comparison)

ผลจาก AI ต้องผ่าน `split_ai_set.py` หรือ `import_ai_model.py` เสมอเพื่อจัดทิศ ลดโพลี และ bake และคำสั่งที่ส่งให้ AI ต้องไม่ลอกงานของผู้สร้างอื่น ตามกฎต้นฉบับใน `SKILL.md`
