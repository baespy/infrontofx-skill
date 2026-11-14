# infrontofx-skill

Skill สำหรับ Claude Code / agent อื่น เพื่อเขียนและรีไรต์ resource FiveM (Lua 5.4, ox_lib, NUI/DUI) ตามมาตรฐานเดียวกันทั้งเซิร์ฟเวอร์

- ไม่มี comment ในโค้ด
- OOP เท่านั้น: ไม่มี `local function` ระดับไฟล์ ไม่มีค่าคงที่ระดับไฟล์ ไม่มีตาราง `FC`
- optimize โดยคงพฤติกรรมเดิม
- secret อยู่ฝั่ง server เท่านั้น

## ไฟล์

| ไฟล์ | ใช้เมื่อ |
| --- | --- |
| `SKILL.md` | กฎหลักทุกงาน |
| `NUI_DUI.md` | ออกแบบหรือแก้ UI ของ FiveM |
| `TOOLING.md` | เลือกเครื่องมือเสริม MCP และวิธีประหยัด token |

## ติดตั้ง (Claude Code)

```bash
git clone https://github.com/baespy/infrontofx-skill.git .claude/skills/infrontofx
```

## License

MIT
