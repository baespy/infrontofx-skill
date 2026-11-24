---
name: perf-forge
description: Makes a FiveM server feel smooth - FPS, stutter, texture loss, NUI lag, join time, desync, hitches - with measured, unconventional levers and an architect mode that questions the work, weighs 5+ AAA-style designs and proves the pick. Use for ลื่น, แลค, กระตุก, เฟรมดรอป, FPS, โหลดนาน, เท็กซ์เจอร์หาย, performance, เพิ่มประสิทธิภาพ, คิดนอกกรอบ, ออกแบบ performance, /perf-architect, resmon, profiler. Not for routine rewrites (use infrontofx).
---

# Perf Forge

Find what players actually feel, fix the biggest measured cause first, prove it with numbers. Lua tuning is rarely the top lever on a gated codebase: streamed asset memory, CEF frames and duplicated per-resource services usually are. Paths are relative to this folder; `SKILL.md`, `dev-flow/`, `skills/` and `scripts/` sit at the pack root.

## Quick path

0. Designing a system, rewriting a heavy one, or asked to think outside the box (คิดนอกกรอบ, `/perf-architect`): run `references/architect.md` first (seven questions, kill list, 5+ alternatives, decision matrix, proof), then continue here to build and measure.
1. Write the scenario card (`references/measure.md` -> Scenario card) from the owner's words: where, how many players, what they feel.
2. Run both static scans from the project root and keep their JSON: `scripts/stream-audit.mjs` and `scripts/perf-scan.mjs` (commands in `references/measure.md` -> Static scans). They need no game and take seconds.
3. Map the symptom to a layer with Choose, open only that part of `references/playbook.md`.
4. Capture a baseline in game for that layer (client, server, network or NUI capture in `references/measure.md`). If the owner cannot test now, rank by static scan weight and say the gain is unmeasured.
5. Fix one cause at a time, biggest first. Lua and NUI edits follow the pack root `SKILL.md` (backup, OOP, lint) and `dev-flow` verify. Asset edits keep the original in `_backup/<YYYY-MM-DD>/<resource>`.
6. Re-run the same scan and capture; report with the template in `references/measure.md` -> Report template.
7. Server-specific results go to the project (`_dev/perf/`, `PROGRESS.md`), never into this pack; new general lessons go to `memory/performance-research.md`.

## Choose

| Player feels | First lever | Read |
| --- | --- | --- |
| เท็กซ์เจอร์หาย, blurry or missing models, stutter when driving or turning | streamed memory: oversized ytd/yft, 4K and uncompressed textures, no mips, fake LODs, duplicates | `references/playbook.md` -> A. Streamed assets |
| FPS low everywhere, GPU bound | LOD scale and population owner, draw distance, shadows and lights in custom maps, base yft equal to _hi | `references/playbook.md` -> A. Streamed assets, G. Adaptive quality |
| FPS drops only with UI on screen, menu opens slowly, input lag | CEF: idle animations, blur, timers in hidden frames, frame count, image weight | `references/playbook.md` -> B. NUI and CEF |
| Random hitch every few seconds, resmon spikes, Lua tuning (โค้ด Lua) | hidden runtime allocations (state bags, exports, NUI encode), per-handler event cost, polling instead of engine events, aligned timers, GC churn | `references/lua-unconventional.md`, then `references/playbook.md` -> D. Shared services |
| Rubber-banding, cars teleport, other players jitter | ownership ping-pong, sync frequency, event floods | `references/playbook.md` -> E. Network and OneSync |
| Everyone lags at once, server console hitch warnings | server tick: SQL in loops, per-player exports, broadcasts | `references/playbook.md` -> F. Server and database |
| A whole system is heavy or about to be built; owner wants outside-the-box ideas | architecture before code: delete work, significance, interest management, event-driven, amortize, perceptual tricks | `references/architect.md` |
| Long join or download | download size: html images, audio, fonts, duplicate stream files, dead resources | `references/playbook.md` -> H. Join time |
| Feels slow though numbers are fine | perceived latency: snapshot-first UI, prewarm, optimistic updates | `references/playbook.md` -> I. Perceived smoothness |

## Hard rules

- **Numbers or nothing**: no gain is claimed without before and after from the same scenario card. Static scan deltas (MiB, counts, KB) are valid numbers for asset and NUI work; FPS and frame time need an in-game run, otherwise list them under ต้องลองในเกม.
- **Worst frame beats average**: stutter is the 1% low and the hitch log, not mean FPS.
- **One owner per system**: graphics presets, LOD scale, population budgets, culling radius and perf commands already have an owner in the framework; grep for it and extend it. Never add a second resource that sets the same natives (two owners fight every frame).
- **Shared services belong in the lib**: a pattern copied into 3+ resources (control disabling, point scanning, frame budgets) becomes one service in `1nfx_lib`, with contracts kept for current callers.
- **Never trade correctness for speed**: no dropped rewards, purchases, saves or security checks; coalesce only replaceable state.
- **Do not copy folklore configs**: keep `onesync_distanceCulling` and `onesync_radiusFrequency` on; convars that are defaults or never read are removed, not added. Check each convar against `references/playbook.md` -> E. Network and OneSync.
- **Visible changes are reported**: lower LOD, fewer peds, smaller textures, removed animations change what players see; list them in the report.
- **Black boxes stay closed**: obfuscated or `.fxap` resources are measured from outside and tuned only through their public config.
- **Assets**: never overwrite a streamed file without a backup copy; re-run `scripts/stream-audit.mjs` after every asset change and keep the JSON.
- **Agents**: at most 1-2 sub-agents, no large workflows (pack root rule).

## Done when

- [ ] Scenario card written; static scans run before and after, JSON kept under `_dev/perf/`
- [ ] Each change has a before and after number, or is listed under ต้องลองในเกม
- [ ] Lua and NUI edits passed lint and `dev-flow` verify; assets backed up
- [ ] No second owner added for graphics, population, culling or perf tooling
- [ ] Visible changes listed in the report; server-specific notes kept out of this pack
- [ ] Pack edited: `node scripts/validate-skill.mjs` prints `infrontofx validation passed.`

## References

| Need | Open |
| --- | --- |
| Architect mode: seven questions, AAA technique catalog mapped to FiveM, decision matrix, output template | `references/architect.md` |
| Capture steps, scan commands, scenario card, report template | `references/measure.md` |
| Every lever with why it works, how to apply, risk | `references/playbook.md` |
| New lib services: adaptive quality, control blocks, frame budget, point broker | `references/shared-services.md` |
| Streamed memory audit (RSC7 page flags, ytd textures, duplicates) | `scripts/stream-audit.mjs` |
| Lua levers from the runtime source, with house-style fixes | `references/lua-unconventional.md` |
| Measure Lua techniques on the server's own CfxLua | `templates/luabench/` (console `luabench`, F8 `luabench_cl`) |
| Weighted Lua and NUI hotspot ranking | `scripts/perf-scan.mjs` |
| OAL readiness per resource (vector args, swizzles, bool out-pointers, DUI) | `scripts/oal-audit.mjs` |
| Runtime NUI idle check: running animations per `ui_page` while closed | `scripts/nui-idle.cjs` (steps in `references/measure.md` -> NUI capture) |
