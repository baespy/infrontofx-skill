---
name: perf-architect
description: Outside-the-box performance architect for FiveM. Questions whether work should exist, weighs 5+ AAA-style designs (significance, budgets, interest management, event-driven, amortization, perceptual tricks), scores them, proves the pick with numbers, builds it in house style. Use as /perf-architect audit <path> or design <idea>, or for คิดนอกกรอบ, ออกแบบให้เบา. Not for one-line fixes (use perf-forge).
---

# Perf Architect

Command entry for the architect mode of `perf-forge`. The method lives there; this file picks the mode. Paths are relative to the pack root (the folder above this one).

## Quick path

1. Read `perf-forge/SKILL.md` (Quick path, Hard rules), then `perf-forge/references/architect.md` (seven questions, catalog, decision matrix, output template).
2. Pick the mode from the argument (Choose).
3. Open only the references `architect.md` routes to (`perf-forge/references/lua-unconventional.md`, `perf-forge/references/playbook.md`, `perf-forge/references/shared-services.md`, `perf-forge/references/measure.md`), and the pack root `SKILL.md` before editing any resource.
4. Reply with the output template from `architect.md`, in Thai.

## Choose

| Argument | Do |
| --- | --- |
| `audit <path>` (resource or `[category]` folder) | run `perf-forge/scripts/perf-scan.mjs`, `perf-forge/scripts/oal-audit.mjs` and, for streamed assets, `perf-forge/scripts/stream-audit.mjs` on that path; read the top resources; answer the seven questions; decision matrix per heavy system; build the picks that keep behaviour and contracts, propose the rest |
| `design <idea>` | no code: data flow, seven questions, 5+ alternatives from 3+ families, matrix, chosen design, proof plan, house-style file layout |
| free text | the closest mode from the wording |

## Hard rules

- Every gain carries a number or a named source; unmeasured gains go under ต้องลองในเกม.
- Server authority, contracts, one owner per shared system, backup, lint and `dev-flow` verify are never skipped.
- Owner holds and exclusions recorded in the project (`PROGRESS.md`, project memory) win over this file.
- Server-specific findings go to the project (`_dev/perf/`, `PROGRESS.md`), never into this pack.

## Done when

- [ ] Seven questions answered with evidence; kill list written
- [ ] At least five alternatives from three families plus the baseline, scored
- [ ] Pick justified by a number; build done one resource at a time with lint and verify, or a proof plan if design mode
- [ ] Report in Thai with ต้องลองในเกม
