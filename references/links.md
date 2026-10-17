# Sources And Links

## Upstream References Used To Build This Skill

| Source | What was taken |
| --- | --- |
| https://github.com/b3sty191/b3sty-skill | skill package layout (SKILL.md routing, memory with Date/Game build, validator, plugin manifests), security give-value checklist, NUI rules, native rules, persistence pattern |
| https://github.com/jxeqoz/fivem-mcp | knowledge files (KVP cache, NUI contract, Lua 5.4 perf), static code-review heuristics ported into `scripts/lint-resource.mjs` |
| https://github.com/jxeqoz/csharp-game-server-emulator-skill | skill authoring format |
| https://github.com/HTPH/FiveM-Utilities-NUI-and-Lua | `fetchNui` / `useNuiEvent` React bridge |
| https://github.com/HTPH/Chipo_ , https://github.com/HTPH/Chipo_RobPlayer | resource template layout (Setting/Webhook split, cooldown + token ideas) |
| local `1nfx_growth_garden`, `1nfx_serverlogs` | house style, FC layer, controller tables, design system, DUI pool, wire encoding, KVP snapshot |

## Official Docs

- Natives: https://docs.fivem.net/natives/
- Resource manifest: https://docs.fivem.net/docs/scripting-reference/resource-manifest/resource-manifest/
- Server security: https://docs.fivem.net/docs/developers/server-security/
- NUI callbacks: https://docs.fivem.net/docs/scripting-manual/nui-development/nui-callbacks/
- State bags: https://docs.fivem.net/docs/scripting-manual/networking/state-bags/
- Routing buckets: https://docs.fivem.net/docs/scripting-reference/onesync/
- ox_lib: https://overextended.dev/ox_lib
- oxmysql: https://overextended.dev/oxmysql
- Full native dump with search: b3sty191/b3sty-skill -> references/natives
