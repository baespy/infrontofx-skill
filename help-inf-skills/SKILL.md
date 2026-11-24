---
name: help-inf-skills
description: Lists every skill in the infrontofx pack and in the project, with what each one does, how to call it and the Thai words that load it automatically. Use for /help-inf-skills, มี skill อะไรบ้าง, skill ทั้งหมด, ใช้ skill ยังไง, help skills, or when the owner asks which skill fits a task. Not for doing the task itself (load the listed skill).
---

# Help: infrontofx skills

Answers "what can I use" from the files on disk, never from memory, so the list stays right after skills are added or renamed. Paths are relative to the pack root (the folder above this one).

## Quick path

1. Run `node scripts/list-skills.mjs --json` from the pack root (node not on PATH: `<project>\.tools\node\node.exe`). It reads `.claude-plugin/plugin.json`, every listed `SKILL.md`, project skills next to the pack, and `hooks/skill-routes.tsv`.
2. With no argument, reply in Thai: first line `infrontofx-skill v<version>: <n> skills`, then the groups below, one line per skill (what it does in plain Thai, how to call it, 2-4 Thai trigger words from `thai`).
3. With an argument that names a skill or a task (`/help-inf-skills perf`), show only the matching skills and summarise that skill's Quick path in 3-5 Thai lines.
4. End with how calling works (Calling) in 2-3 lines.

## Groups

| Group (Thai heading) | Skills |
| --- | --- |
| เขียนโค้ด FiveM | `infrontofx`, `dev-flow`, `terse` |
| ความลื่น / performance | `perf-forge`, `perf-architect` |
| ปั้น 3D และแมพ | `sculpt-forge`, `prop-forge`, `map-forge`, `weapon-forge` |
| กราฟิก | `poster-forge` |
| ช่วยเหลือ | `help-inf-skills` |
| อื่นๆ ในโปรเจกต์ | any `source: project` skill the script finds that is not above |

A skill the script finds but the table does not name goes under its closest group; never drop one.

## Calling

- Just type the task in Thai: the routing hook reads the words and loads the right skills (`auto-route (Thai)` column), no command needed.
- Plugin install: `/infrontofx-skill:<name>` (the `command` field). Project skills next to the pack: `/<name>`.
- Project copy without the plugin: the root `infrontofx` skill routes to every sub-skill; sub-skills load when the task matches.

## Done when

- [ ] Every skill from `list-skills.mjs` appears once, none invented, none from memory
- [ ] Reply is Thai, grouped, one line per skill with how to call it and trigger words
- [ ] Calling explained in 2-3 lines
