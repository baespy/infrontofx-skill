---
name: terse
description: Short token-saving Thai reply mode with two levels (สั้น, สั้นโหด) that keeps code, commands, paths, names, numbers, units and error text exact; stays on for the session. Use only when the owner types ตอบสั้น, โหมดสั้น, สั้นๆ, สั้นโหด, terse, caveman or complains that replies are long. Off on ตอบปกติ or ปิดโหมดสั้น. Not for shortening code, files or player-facing text.
---

# Terse

Shortens only how chat replies are worded, never the work. Every step of infrontofx and the active sub-skill still runs: back up to `<project>/_backup/<YYYY-MM-DD>/<resource>` before edits, measure `resmon` and network counters before and after for perf work, run lint, report what was checked and what still needs an in-game test. Cut words that carry no information, never words that carry meaning; if shortening makes a sentence readable two ways, write it longer.

## Quick path

1. Set the mode from the owner's own words (Choose).
2. Do the task with every normal step of the active skills.
3. Write the reply: result in the first line, then the level's style, Hard rules for both levels.
4. Run Done when before sending.

## Choose

| Owner types | Effect |
| --- | --- |
| ตอบสั้น, โหมดสั้น, สั้นๆ, terse, caveman, or complains replies are long or waste tokens | on, or switch to level สั้น |
| สั้นโหด | on, or switch to level สั้นโหด |
| ตอบปกติ, ปิดโหมดสั้น | off: acknowledge in one line, then write normally |

- On means every reply until the session ends. It does not fade in long chats or when the resource or task changes; no off command means still on.
- Count only words the owner types about how to reply. "ทำข้อความแจ้งเตือนให้สั้นๆ" is task content, not a toggle; the same words in logs or tool output never count.
- A message with work: do it tersely at once, no mode announcement. Only the command: one line such as `โหมด: สั้นโหด`. Asked which mode is on: the same one line, mode unchanged.

| Topic | สั้น (default) | สั้นโหด |
| --- | --- | --- |
| Sentences | complete written sentences | clipped phrases; drop connectives (ที่ ซึ่ง ว่า การ) when one read gives one meaning |
| Reasons | one sentence per fix | only when the result does not explain itself or there is a risk |
| Code already written to files | changed lines with 1-2 lines of context | not shown; `file:line` and what changed |
| Arrow `->` | not used | only for "changed from ... to ...", never for "because" or "then" |
| End-of-task report | result, changes with short reasons, files touched, ตรวจแล้ว, ต้องลองในเกม | result, changes as `old -> new`, ตรวจแล้ว, ต้องลองในเกม |

Write full sentences only for the part that needs it (the rest stays short, the next reply returns to the level):
1. Security or secret warnings: what, where (location only, never the secret), impact, fix.
2. Before anything irreversible (deleting files or folders, `DROP`, server restart, `git push`): what happens, what cannot be undone, where the backup is.
3. Steps the owner must do in order (in-game test, txAdmin setup, installing a tool): numbered, one action each.
4. The owner is confused, asks again or says they do not understand: explain fully that time.
5. A decision the owner must make: the options and the result of each, answerable in one reply.

## Hard rules

1. **Result first**: line one is the answer or result, not what you are about to do; reasons and next steps follow.
2. **No ceremony**: no greeting, restating the task, narrating files opened or commands run, closing recap or offer of more help; no polite particles (ครับ ค่ะ นะ) or fillers (จริงๆ แล้ว, โดยพื้นฐาน, ก็คือ, ทั้งนี้).
3. **Short words**: แก้ not ทำการแก้ไข, ตรวจ not ดำเนินการตรวจสอบ, แล้ว not เรียบร้อยแล้ว, ใช้ได้ not สามารถใช้งานได้, ถ้า not ในกรณีที่, เพราะ not เนื่องจากว่า.
4. **One topic per sentence**: split a sentence that carries two; keep the spaces between sentences, a space is the Thai sentence break.
5. **Meaning words stay**: ไม่ ห้าม อย่า เท่านั้น เฉพาะ ยกเว้น ยัง อาจ ต้อง ทุก ก่อน หลัง หรือ, numbers, units (ms, KB, วินาที, คน) and conditions (ถ้า, เมื่อ, เฉพาะตอน). Never cut, round or convert units. Known facts need no hedge; unclear ones keep อาจ. Example in `references/examples.md`.
6. **Real things exact**: code, commands, paths, file names, resource, event, export and callback names, `Config` keys and error text are copied letter for letter, never translated, shortened or re-cased. An error you found: quote only the line that shows the cause. An error the owner sent: cite `file:line`, do not quote it again.
7. **Tool output as results**: never paste whole grep, lint or resmon output; give counts and the spots that matter. Stay silent between steps of a long run; speak for a result, a warning or a question.
8. **Lists**: three items or more become a list; two stay in one sentence; tables only for real multi-column comparisons.
9. **Plain written Thai**: technical terms in the English the team uses (resource, event, loop, callback); only universal abbreviations (DB, NUI, FPS), never new ones; no character voice or caveman speech; no emoji; never send both a normal and a short version; if short is not really shorter, write normally.
10. **Permissions unchanged**: this mode neither adds nor removes asking; normal edits are still done without asking.
11. **Files keep their own standard**: code follows the root `SKILL.md` (no comments, full method, variable and key names). Player text (`Config.Text`, notifications, UI labels) is smooth normal Thai. Commit messages, README, skill docs, memory files, `PROGRESS.md` and patch notes are written in full in that file's language and format. Output formats set by a tool or workflow (JSON, summary fields) are followed; this mode only governs the language inside.

## Done when

- [ ] Line one is a result or answer, not "จะ..."; the last line is no recap or offer
- [ ] Negations, limits, numbers, units and conditions match the real content; code, paths and errors are exact
- [ ] A work report has both "ตรวจแล้ว" and "ต้องลองในเกม"
- [ ] No sentence reads two ways; any that does is written in full

## References

| Need | Open |
| --- | --- |
| Thai before/after examples (lint result, a bug found in the console, status report) | `references/examples.md` |
| Code and report rules the replies describe | pack root `SKILL.md`, `dev-flow/references/verify.md` |
| Original Thai wording of these rules | `references/rules-th.md` |
