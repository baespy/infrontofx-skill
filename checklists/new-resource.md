# New Resource Checklist

1. Scaffold: `node scripts/new-resource.mjs <name> --destination <resources folder>`.
2. Rename check: client table `Name`, server table `NameServer`, no author prefix.
3. `fxmanifest.lua`: `@ox_lib/init.lua` first, `config/*.lua` in `shared_scripts`, `config/function/*` before `core/*`, and `files { "html/**" }`. Do not add `core/sh_config.lua`, deprecated `lua54`, or experimental OAL by default.
4. `config/config.lua`: `Config.General` (snake_case), `Config.Text` for every player string, commands configurable.
5. Optional split datasets in `config/config.<domain>.lua` when a dataset is large. Read `Config` directly in `core/*` without fallback chains.
6. `FC` adapters for every external call; hooks (`FC.CanXxx`, `FC.OnXxx`) at every owner-customizable decision.
7. Server: `ServerState` maps, throttle, in-flight lock for value actions, `lib.callback.register` one-liners delegating to methods.
8. Client: `lib.points` / `lib.zones`, `FC.ShowTextUI` on enter, clear on exit, direct `PostNUI`.
9. NUI: `uiReady` handshake, `{ action, data }`, `cb` once, ESC close, `textContent` only, design tokens + `--px`.
10. Cleanup: `onResourceStop` (points, blips, entities, DUI, focus, text UI) and `playerDropped` (`[src]` maps).
11. Persistence (if any): `install.sql`, dirty save, await on stop.
12. Run `node scripts/lint-resource.mjs <resource>` - zero errors.
13. Test: start, restart twice (no duplicate blips/points), spam the action, disconnect mid-action, wrong bucket, far distance.
