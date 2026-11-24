# Measure

No number, no claim. Every perf-forge change carries a before and after from the same scenario. Paths are relative to `perf-forge/`; pack root paths start at the pack root.

## Contents

- Scenario card
- Static scans (no game needed)
- Client capture
- Server capture
- Network capture
- NUI capture
- Report template

## Scenario card

Write this before the first capture and repeat it exactly after the change.

```
scenario: <place, e.g. lobby spawn / school ground / warzone>
players: <count online, bots or real>
action: <idle 60 s | open inventory | drive 60 s loop | 10 airdrop joins>
duration: <seconds>
client: <GPU, VRAM, settings preset, resolution>
build: <sv_enforceGameBuild value>, resources changed: <list>
```

## Static scans (no game needed)

Run from the project root (node not on PATH: `.tools\node\node.exe`):

| Command | Finds |
| --- | --- |
| `node .claude/skills/infrontofx/perf-forge/scripts/stream-audit.mjs resources --top=25 --json=<out>.json` | streamed memory per resource and asset (RSC7 page flags), oversized assets, 4K and uncompressed textures, missing mips, non power of two, same name streamed twice, byte-identical copies; escrowed (FXAP) files are listed but their memory is unknown |
| `node .claude/skills/infrontofx/perf-forge/scripts/perf-scan.mjs resources --top=25 --json=<out>.json` | weighted per-resource list: exports, hashes, json, net, pools inside `Wait(0)` loops; SQL, broadcasts, threads inside loops; per-player exports; NUI timers, infinite animations, blur, heavy images, audio, fonts, source maps; client runtime and `ui_page` counts |
| `node .claude/skills/infrontofx/scripts/lint-resource.mjs <resource>` | house rules, `wait-zero`, `pool-scan`, `latent-broadcast` per resource |

Scanner output is a candidate list, not a verdict. Open each hit: startup-only code (schema creation, boot waits) and code behind a rare admin command are low value. Fix what runs per frame, per player, or per tick first.

## Client capture

1. `resmon 1` in F8: note ms and memory of the top 10 resources after 30 s idle in the scenario.
2. `profiler record 300` (300 frames) then `profiler view`, which opens the Chrome DevTools Performance timeline. Find the resource, thread and function of every spike over 2 ms. The profiler runs a full Lua GC when it stops; ignore the hitch right after a capture.
3. One resource in depth: `profiler resource <name> 300` runs lmprof (instrument plus memory) on that resource only; `profiler view` then shows time and bytes allocated per Lua function. Works in F8 and the server console. Use it to find GC churn before guessing.
4. Frame time, not FPS: `cl_drawPerf true` shows FPS, CPU, GPU and VRAM but no frame times. For the average and the 1% low use the framework's frame-time recorder if it has one (a `GetFrameTime` sampler command), or PresentMon, CapFrameX or the RTSS frame-time graph on the test PC. Stutter is the worst frames, not the average.
5. Streaming: `strmem true` (streaming memory), `strlist true` (what is loaded) and `strdbg true` while driving the scenario route; note texture loss (blurry or missing textures). Task Manager GPU tab dedicated memory is the fallback for VRAM.
6. Repeat 3 runs, take the median.

## Server capture

1. `profiler record 500` (500 ticks) on the server console, then `profiler saveJSON server.json` and load it in Chrome DevTools Performance (Load profile), or `profiler view`.
2. Watch the console for `server thread hitch warning` and `network thread hitch warning` (over 150 ms) and `sync thread hitch warning` (over 100 ms, tied to OneSync load). Shorter stalls never print; find them in the profiler. Write the timestamp and what was happening.
3. Server `resmon` is an ImGui window (server GUI only); the txAdmin web console cannot show it. Use the profiler and txAdmin's own performance charts.
4. oxmysql: `mysql_slow_query_warning` defaults to 200 ms; set 50-100 during a capture to see medium queries, then restore. Collect every slow query line during the scenario.

## Network capture

1. `neteventlog true` (client F8) opens a live list of script events with sizes; read the counts off it during 60 s of the scenario.
2. Count per event: calls/s, bytes/call, recipients. Egress = calls/s x bytes x recipients.
3. `netgraph 1` for ping, loss and in/out bandwidth per client.
4. State bags: count `SetState`/`state.x =` writes per second in the scenario; a replicated key written every frame is a bug.

## NUI capture

0. Without the game: `scripts/nui-idle.cjs <resources dir> <port>` serves every `ui_page` with a probe (stubs `GetParentResourceName`, NUI fetches, `nui://game/ui/jquery.js`, `https://cfx-nui-<res>/`) and a harness page. Start it as a preview server (`.claude/launch.json`), open `/`, run `measure(await fetch('/__list').then(r => r.json()))` in batches, and check `/__control.html` first (expects 2 running, 1 visible). It counts running CSS animations per page in the closed state, including invisible ones (`opacity: 0`, `visibility: hidden`) that still repaint. For the open then closed state, post each resource's real open and close actions (read its message handler; generic guesses miss, e.g. `setVisible` with `false`). rAF counts are throttled in the preview pane; read JS timers in code instead.
1. `nui_devtools` (F8) or Chrome at `http://localhost:13172` (works unless the server sets `nui_enableDevtools false`): Performance tab, record 10 s idle with every UI closed.
2. Any scripting or painting while every UI is closed is a defect (timers, rAF, infinite animation, hidden video).
3. Memory tab: heap snapshot after open/close of each UI 5 times; growth means a leak.
4. Layers panel: count composited layers; full-screen blur or shadow layers repaint the whole screen.

## Report template

```
ผล: <one line, e.g. FPS lobby 92 -> 118, worst frame 41 ms -> 18 ms>
ฉาก: <scenario card one line>
ก่อน: <numbers>
หลัง: <numbers>
เปลี่ยน: <files and what>
ตรวจแล้ว: <static scans, lint, contracts>
ต้องลองในเกม: <what only a live test proves>
ตัดสินใจเอง: <what> เพราะ <why> ถ้าผิดเสีย <cost>
```
