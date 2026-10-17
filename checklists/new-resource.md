# New Resource Checklist

1. Scaffold: `powershell -File scripts/new-resource.ps1 -Name 1nfx_<name> -Destination <resources folder>`.
2. Rename check: client table `Name`, server table `NameServer`, no author prefix.
3. `fxmanifest.lua`: lua54, `use_experimental_fxv2_oal`, `@ox_lib/init.lua` first, config before `core/sh_config.lua`, `config/function/*` before `core/*`, `files { "html/**" }`.
4. `config/config.lua`: `Config.General` (snake_case), `Config.Text` for every player string, commands configurable.
5. Datasets in `config/config.<domain>.lua`, validated in `core/sh_config.lua` with `assert`, indexes built there.
6. `FC` adapters for every external call; hooks (`FC.CanXxx`, `FC.OnXxx`) at every owner-customizable decision.
7. Server: `ServerState` maps, throttle, in-flight lock for value actions, `lib.callback.register` one-liners delegating to methods.
8. Client: `lib.points` / `lib.zones`, `FC.ShowTextUI` on enter, clear on exit, `uiLoaded` promise + `PostNUI`.
9. NUI: `uiReady` handshake, `{ action, data }`, `cb` once, ESC close, `textContent` only, design tokens + `--px`.
10. Cleanup: `onResourceStop` (points, blips, entities, DUI, focus, text UI) and `playerDropped` (`[src]` maps).
11. Persistence (if any): `install.sql`, dirty save, await on stop.
12. Run `node scripts/lint-resource.mjs <resource>` - zero errors.
13. Test: start, restart twice (no duplicate blips/points), spam the action, disconnect mid-action, wrong bucket, far distance.

