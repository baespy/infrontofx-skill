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
- Game build: tested on recent builds (source: b3sty memory)
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
- Resource: 1nfx_growth_garden
- Symptom: hitch when many plants play effects.
- Fix: cache loaded assets on the controller (`LoadedPtfxAssets`) and re-request only when `HasNamedPtfxAssetLoaded` is false.

