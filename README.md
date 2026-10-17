# infrontofx-skill

มาตรฐานการเขียน **FiveM Lua + NUI/DUI** สำหรับ `infrontofx` ใช้เป็น Skill ให้ AI (**Antigravity**, **Claude Code**, **OpenAI Codex**) เขียนโค้ดออกมาเป็นสไตล์เดียวกันทุกตัว: OOP table เดียว, `Config` + `config/function` (`FC` ครอบ ESX มาตรฐาน + pNotify), ปลอดภัย, ลื่น, UI สวยและเบา

---

## ติดตั้ง (รองรับ Antigravity + Claude Code + Codex)

### Windows (คลิกเดียว)

```powershell
git clone https://github.com/baespy/infrontofx-skill.git
cd infrontofx-skill
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

ตัวติดตั้งจะวาง Skill ให้ครบทั้ง 3 ตัวอัตโนมัติ:

| Agent | ตำแหน่ง Global | ตำแหน่งในโปรเจกต์ (`-Project`) |
| --- | --- | --- |
| **Antigravity** | `%USERPROFILE%\.gemini\config\skills\infrontofx-skill`<br>`%USERPROFILE%\.gemini\antigravity\skills\infrontofx-skill` | `.agents\skills\infrontofx-skill` + `AGENTS.md` |
| **Claude Code** | `%USERPROFILE%\.claude\skills\infrontofx-skill` | `.claude\skills\infrontofx-skill` + `CLAUDE.md` |
| **OpenAI Codex** | `%USERPROFILE%\.codex\skills\infrontofx-skill` | `.agents\skills\infrontofx-skill` + `AGENTS.md` |

ใส่ `-Project "C:\path\to\server\resources"` เพื่อวางทั้ง `.agents/skills/infrontofx-skill`, `.claude/skills/infrontofx-skill`, `AGENTS.md`, และ `CLAUDE.md` ลงในโปรเจกต์ (AI ทั้ง 3 ตัวจะโหลดกฎอัตโนมัติทันทีเมื่อเปิดโฟลเดอร์นั้น)

### Claude Code (plugin marketplace)

```text
/plugin marketplace add baespy/infrontofx-skill
/plugin install infrontofx-skill@infrontofx
```

### OpenAI Codex (skill-installer)

```text
Use $skill-installer to install from repo baespy/infrontofx-skill path . with name infrontofx-skill
```

---

## กฎหลัก (สรุป)

| หัวข้อ | มาตรฐาน |
| --- | --- |
| Header | `ESX = exports["es_extended"]:getSharedObject()` + `local scriptname = GetCurrentResourceName()` |
| OOP | Table เดียวต่อฝั่ง: `Shop = { ServerState = {}, PlayerState = {} }` / `ShopServer = { ServerState = {} }` ใช้ `function Shop:Method()` ชื่อไม่ใส่ prefix ผู้เขียน |
| Config | `config/config.lua` → `Config.General` (snake_case), `Config.Text` (ข้อความทั้งหมด), ข้อมูลใหญ่แยก `config/config.<domain>.lua`, ตรวจ+สร้าง index ใน `core/sh_config.lua` |
| config.function | `FC` ใน `config/function/config.function.client.lua` / `.server.lua` = จุดเดียวที่เรียก `ESX` (`ESX.GetPlayerData`, `RunStaticPlayerMethod`), `pNotify` และ hook (`FC.CanXxx`, `FC.OnXxx`) |
| Event | `scriptname .. ":SV:action"` / `scriptname .. ":CL:action"`, ใช้ `lib.callback` เป็นหลัก, `local src = source` บรรทัดแรก |
| ox_lib | ใช้ได้: callback, points, zones, cache, table, cron, dui — **ห้าม**: `lib.notify`, `lib.progressBar/Circle`, `lib.showTextUI/hideTextUI` |
| รูปแบบโค้ด | `if` หลายบรรทัดเสมอ, **ไม่มีคอมเมนต์** ใน Lua, 4 spaces, double quotes |
| ความปลอดภัย | Server ตัดสินทุกอย่าง (ราคา/ของ/เงิน), ตรวจ type/range/ระยะ/bucket, throttle, in-flight lock, log |
| ความลื่น | ไม่มี `Wait(0)` ตอน idle, ใช้ `lib.points`, `cache.ped`, index แทน loop, ส่ง event แบบ scoped, ล้างทุกอย่างตอน stop |
| UI | `{ action, data }`, handshake `uiReady`, `cb` ครั้งเดียว, `textContent` (กัน XSS), สเกล `--px` 1920x1080, ธีมแดง-ดำ |

รายละเอียดเต็มอยู่ใน [SKILL.md](SKILL.md) และโฟลเดอร์ `skills/`

---

## โครงสร้าง

```text
infrontofx-skill/
├── SKILL.md                 จุดเริ่มของ Skill (Antigravity / Claude Code / Codex)
├── AGENTS.md                กฎอัตโนมัติสำหรับ Antigravity และ Codex
├── CLAUDE.md                กฎอัตโนมัติสำหรับ Claude Code
├── .claude-plugin/          Plugin manifest สำหรับ Claude Code
├── agents/openai.yaml       Agent manifest สำหรับ OpenAI Codex
├── skills/
│   ├── common/              style, architecture, config, fc-adapters, events, security,
│   │                        performance, networking, database, natives, ox-lib, debugging
│   └── ui/                  nui-bridge, design-system, vanilla-ui, react-vite, dui
├── references/              API ของ ESX (esx-api.md) และ pNotify (pnotify-api.md)
├── rules/contracts.md       กฎการเรียกข้าม resource
├── memory/                  บันทึกบั๊ก native / ช่องโหว่ / pattern ที่พิสูจน์แล้ว
├── checklists/              เช็กลิสต์สร้าง resource ใหม่ + รีวิวโค้ด
├── templates/resource/      resource ตัวอย่างครบชุด (ร้านค้า + NUI) ตามมาตรฐาน
└── scripts/
    ├── new-resource.ps1     สร้าง resource ใหม่จาก template (ตั้งชื่อ controller ให้อัตโนมัติ)
    ├── lint-resource.mjs    ตรวจโค้ดตามกฎ + ช่องโหว่ + จุดกินเครื่อง
    └── validate-skill.mjs   ตรวจความครบของ skill ก่อน push
```

---

## เครื่องมือ

สร้าง resource ใหม่:

```powershell
.\scripts\new-resource.ps1 -Name fishing -Destination "C:\server\resources"
```

ได้ `Fishing` / `FishingServer` พร้อม config, FC (ESX + pNotify), NUI ใช้งานได้ทันที

ตรวจโค้ด (ต้องมี Node.js):

```powershell
node .\scripts\lint-resource.mjs "C:\server\resources\fishing"
```

---

## License

MIT — ดู [LICENSE](LICENSE)
