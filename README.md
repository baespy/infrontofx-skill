# infrontofx-skill

ชุดเดียวครบสำหรับงาน FiveM: มาตรฐานเขียน resource Lua + NUI/DUI, ทำโปสเตอร์ Support/Welfare และทำสกินอาวุธ/ptfx ใช้กับ Claude Code, Codex และ agent อื่น

## มีอะไรบ้าง

| ส่วน | ทำอะไร | เริ่มที่ |
| --- | --- | --- |
| มาตรฐานโค้ด | เขียน/รีไรต์/optimize resource: OOP, ไม่มี comment, ไม่มี FC, ไม่มีค่าคงที่ระดับไฟล์, server authority | `SKILL.md` |
| UI | NUI/DUI, design system, Vanilla/React/Vue/Svelte | `NUI_DUI.md`, `skills/ui/` |
| ความรู้ | Lua, event, network, DB, security, performance, native, ox_lib และงานวิจัย | `skills/common/`, `memory/` |
| เครื่องมือ | ตรวจโค้ด, สร้าง resource ใหม่, ตรวจ skill | `scripts/*.mjs` (Node 22+) |
| poster-forge | โปสเตอร์ Support/Welfare/แจกของ จากรูปตัวละครและไอคอนไอเทม | `poster-forge/SKILL.md` |
| weapon-forge | สกินอาวุธ โมเดล Blender ptfx (.ypt) เอฟเฟกต์หน้าจอ เสียง | `weapon-forge/SKILL.md` |

`SKILL.md` มีตารางเลือกเส้นทางว่างานแบบไหนให้เปิดไฟล์ไหน agent อ่านเฉพาะที่ต้องใช้

## ติดตั้ง

```bash
git clone https://github.com/baespy/infrontofx-skill.git .claude/skills/infrontofx
```

หรือเป็นปลั๊กอิน: `/plugin marketplace add baespy/infrontofx-skill` แล้ว `/plugin install infrontofx-skill@infrontofx`(ยังไม่ได้ทดสอบกับ Claude Code จริง)

## ตรวจโค้ด

```bash
node scripts/lint-resource.mjs <resource-folder>
node scripts/new-resource.mjs <name> --destination <path>
node scripts/validate-skill.mjs
```

ตัวตรวจ Lua ตรวจ comment, block/วงเล็บสมดุล, `FC`, `local function` และค่าคงที่ระดับไฟล์, scriptname ที่ไม่ได้ประกาศ, SQL ต่อสตริง, webhook ในโค้ด, `cb` ของ NUI callback และ manifest

## หมายเหตุ

- poster-forge: ฟอนต์เป็น OFL ดู `poster-forge/engine/fonts/NOTICE.md` ภาพอ้างอิงของบุคคลอื่นไม่รวมอยู่ใน repo
- weapon-forge ต้องใช้เครื่องมือภายนอก (Blender, PowerShell, .NET) ตามที่เขียนใน `weapon-forge/SKILL.md`; `weapon-forge/scripts/doctor.ps1` ตรวจสภาพแวดล้อม
- ห้ามนำ secret (webhook, token, รหัสผ่าน) ขึ้น repo

## License

MIT
