# Debugging

## Flow

1. Reproduce with the smallest steps; note side (client F8 / server console / NUI devtools).
2. Read the first error, not the last. Lua errors print `@resource/path.lua:line`.
3. Check load order in `fxmanifest.lua` (nil `FC` / `Config` / controller = wrong order).
4. Verify event names match exactly on both sides (`scriptname .. ":SV:x"`).
5. Add temporary prints guarded by `Config.General.debug`; remove before shipping (house rule: no debug noise, no comments).
6. Fix, then re-run `node scripts/lint-resource.mjs <resource>`.

## Common Failures

| Symptom | Cause |
| --- | --- |
| `attempt to index a nil value (global 'FC')` | config/function file not listed or listed after core |
| `attempt to call a nil value (method 'X')` | method defined in a file that loads later, or typo in `:` vs `.` |
| callback never returns | server handler errored; check server console; `lib.callback.register` name mismatch |
| UI blank | `ui_page` path wrong, file missing from `files`, JS error (open `http://localhost:13172` NUI devtools) |
| cursor stuck after close | missing `SetNuiFocus(false, false)` on a close path |
| entity flickers / respawns | no retain distance hysteresis, or delete+create on every sync |
| works for host, not others | client-only state, missing server sync, wrong routing bucket |
| export returns nil | provider resource not started before consumer call; export not declared |

## Tools

- `resmon 1` (client ms), `profiler record 500` + `profiler view`.
- `restart <resource>` and `ensure <resource>` in server console; watch for stop/start cleanup leaks (doubled blips/points = missing cleanup).
- NUI devtools: `nui_devtools` or remote debugging port in the FiveM client.

