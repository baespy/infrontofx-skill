# Native Gotchas

### InvokeNative BOOL is 1/0

- Date: 2026-10-18
- Game build: any
- Symptom: `if Citizen.InvokeNative(hash, ped) then` always true.
- Cause: BOOL returns numeric `0`/`1`; `0` is truthy in Lua.
- Fix: compare `== 1`.

### Float subtype required

- Date: 2026-10-18
- Game build: any
- Symptom: native ignores value or behaves oddly when passed `1`.
- Cause: integer subtype passed to a float param via InvokeNative.
- Fix: literal `1.0` or `value + 0.0`.

### AddBlipForArea ignores short range

- Date: 2026-10-18
- Game build: any
- Symptom: area blips visible across the map despite `SetBlipAsShortRange(blip, true)`.
- Fix: create/remove area blips by distance from the player.

### SetPedHeadBlendData + mask components crash

- Date: 2026-10-18
- Game build: any
- Symptom: client crash when applying freemode head blend and certain masks in one bulk sequence.
- Fix: apply in steps, gate risky masks, provide fallback.

### HasPedGotWeapon return type

- Date: 2026-10-18
- Game build: any
- Symptom: inconsistent truthiness.
- Fix: `owned == true or type(owned) == "number" and owned ~= 0`.

### Ptfx asset reload cost

- Date: 2026-10-18
- Game build: any
- Symptom: hitch when many world objects play effects simultaneously.
- Fix: cache loaded assets on the controller (`LoadedPtfxAssets`) and re-request only when `HasNamedPtfxAssetLoaded` is false.

### FiveM CEF full-screen backdrop-filter black screen

- Date: 2026-10-26
- Game build: 3095
- Symptom: NUI covers the entire screen with solid pitch-black when opening a menu or HUD overlay.
- Cause: CSS `backdrop-filter: blur(...)` on `body`, `body::before`, or a `position: fixed; inset: 0` wrapper samples the NUI transparent backbuffer instead of the GTA V 3D framebuffer.
- Fix: Set `backdrop-filter: none !important` on full-screen wrappers and use `TriggerScreenblurFadeIn(250)` / `TriggerScreenblurFadeOut(250)` in client Lua to blur the game world behind NUI.

### RegisterKeyMapping ignores updated default key for existing command name

- Date: 2026-10-26
- Game build: 3095
- Symptom: Changing `toggle_key` in `config.lua` (e.g. from `"K"` to `"J"`) does not respond to the new key in-game.
- Cause: FiveM caches keybindings per command name in the player's local `fivem.cfg` on first registration and ignores subsequent default key changes for that same command name.
- Fix: Append the lowercase key to the registered keymapping command name (`local keyCmd = baseCmd .. "_" .. string.lower(key)`) while keeping `baseCmd` registered for manual console/chat use.
