---
name: dev-flow
description: FiveM work discipline - think first, plan per resource, debug to the root cause, verify with fresh evidence, review, audit, hand off. Use for บั๊ก, error, ไม่ทำงาน, F8 or server logs, ออกแบบระบบใหม่, วางแผน, รีวิว, audit, ตรวจงาน, สรุปส่งต่อ, handoff, and before saying any code task is done. Not for code style (use infrontofx) or 3D assets (use the forge skills).
---

# Dev Flow

How to work. How code looks stays in the pack root `SKILL.md` (OOP, no comments, no `FC`, `1nfx_lib`, `1nfx_core`); always use both. `references/` paths are in this folder; `SKILL.md`, `checklists/`, `skills/`, `scripts/` and other sub-skills are at the pack root.

## Quick path

1. Pick the mode in Choose. Small edit (text, one value, one line): read, edit, lint, report with the verify template; skip the rest.
2. Read the real code and grep every caller first (exports, events, callbacks, NUI actions, DB, `Config` keys, state bags).
3. Write the goal as checkable lines `step -> check: <command or observation that can fail>`; loop until each passes.
4. Back up to `<project>/_backup/<YYYY-MM-DD>/<resource>` before the first edit; one resource at a time (no git).
5. Edit with the least code (Hard rules), only lines the task needs.
6. After the last edit run `references/verify.md` checks: `node scripts/lint-resource.mjs <resource>` -> `0 error(s)` and exit 0; contract diff vs backup -> no `<=` line; methods block -> no own method missing; perf work -> before/after numbers.
7. Report in Thai, first line = result, template in `references/verify.md`, always with ตรวจแล้ว and ต้องลองในเกม.
8. Append to `PROGRESS.md` per `references/handoff.md`; if the owner said to keep going, open the next resource at once.

## Choose

| Owner types, or situation | Do | Read |
| --- | --- | --- |
| ออกแบบระบบใหม่, new system or feature, unclear task | read before asking, write a spec, silent self-check | `references/think-first.md` |
| วางแผน, many files or resources, big rewrite | plan per resource, checkable steps, checkpoints | `references/plan.md` |
| บั๊ก, error, ดีบัก, ไม่ทำงาน, log or F8 screenshot | reproduce, find the root cause, fix there | `references/debug.md` |
| ตรวจงาน, ก่อนส่งงาน, before saying done, passed, fixed or faster | fresh evidence, contract diff, before/after, report template | `references/verify.md` |
| รีวิว, audit, whole folder, review received from elsewhere | review vs backup, folder audit, debt ledger, take review | `references/review-audit.md` |
| สรุปส่งต่อ, handoff, session end, context nearly full | write `PROGRESS.md`, pick what goes to `memory/` | `references/handoff.md` |

- Big task order: think-first (new or unclear) -> plan -> step by step -> verify -> handoff. A bug on the way inserts debug.
- Edit depth follows the owner's word: "แก้บั๊ก" touches only the broken path and lists other findings at the end of the report; "รีไรต์" or "optimize" applies the full infrontofx standard (strip comments, delete dead code after grep) with contracts unchanged.

## Hard rules

- **Asking**: normal edits, bugs, perf and vulnerabilities are done first and reported after. Ask only in the Stop list.
- **Think first**: find facts yourself; decisions that change what gets built belong to the owner. At most 3 questions; otherwise write assumptions one per line and continue. If the task reads two ways, show both with what players would see; never pick silently.
- **Least code**: stop at the first rung that works - nothing needed -> already in `1nfx_lib`, `1nfx_core` or another resource -> a native or state bag -> one line -> write it yourself. No single-use abstraction, one-line wrapper, `Config` key nobody tunes, preview or mock mode. If 200 lines can be 50, rewrite. Never cut to look short: server checks, throttles, stop and drop cleanup, server-side secrets, DB writes that prevent loss, anything the owner asked for.
- **Surgical**: every changed line traces to the task. Contracts never change: export names and parameter order, event names, `lib.callback` names and commands, `Config` keys, NUI `action` and `data` shape, DB tables and columns, state bag keys.
- **Evidence**: never say done without fresh evidence from after the last edit. Another agent's report is a claim; open the files and run the checks yourself.
- **Code**: no comments in any language; OOP on `1nfx_lib` and `1nfx_core` per the root rules.
- **Scale**: design for 1,600 players at once; perf work is measured before and after in the same scenario.
- **Results**: the final test is in game; every report separates ตรวจแล้ว from ต้องลองในเกม.
- **Report**: Thai, short, first line is the result. Own decisions go at the end as `ตัดสินใจเอง: <what> เพราะ <why> ถ้าผิดเสีย <cost>`.

**Stop and ask only when**
1. Data loss cannot be undone (`DROP`, `TRUNCATE`, wiping a table, deleting a folder). Retired files go to `_backup` instead of being deleted.
2. A contract must change and there is no other way.
3. It acts outside this machine: restarting the live server with players on it, pushing to a public place.
4. Only the owner can do it, e.g. rotating a leaked token or webhook (give the location, never copy the value).
5. Two options change what players see and code, `memory/` and `PROGRESS.md` cannot decide; or three fixes failed and every option left is a guess.

## Done when

- [ ] The mode's reference was followed (small edits excepted)
- [ ] Checks re-ran after the last edit; full output and exit code read
- [ ] Every claim carries numbers (`lint 0 error(s), 2 warning(s)`)
- [ ] Report follows the template; ตรวจแล้ว and ต้องลองในเกม present; own decisions listed
- [ ] `PROGRESS.md` updated
- [ ] Next resource opened when the owner already said to keep going

## References

| Need | Open |
| --- | --- |
| Mode details | `references/think-first.md`, `references/plan.md`, `references/debug.md`, `references/verify.md`, `references/review-audit.md`, `references/handoff.md` |
| Code rules, per-resource steps, edit levels | pack root `SKILL.md` |
| New resource; review checklist | `checklists/new-resource.md`; `checklists/review.md` |
| Symptom to cause, debug tools | `skills/common/debugging.md` |
| Optimize order and measuring | `skills/common/performance.md` |
| Lint a resource; validate the pack | `scripts/lint-resource.mjs`; `scripts/validate-skill.mjs` |
| Token saving and memory | `TOOLING.md` |
| Original Thai wording of these rules | `references/rules-th.md` |

Open pack-root files from the root; never copy their content here.
