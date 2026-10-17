# Natives

## Name Conversion

- Docs `GET_ENTITY_COORDS` -> Lua `GetEntityCoords`.
- Leading underscore names drop the underscore.
- Hash-only natives: `Citizen.InvokeNative(0x1234ABCD, ...)`. Name the call site through a controller method (`self:SetPedFlagX(ped)`) instead of a comment.
- Official reference: https://docs.fivem.net/natives/

## Return Values

- `Citizen.InvokeNative` BOOL returns `1` / `0`. `0` is truthy in Lua: compare `== 1`.
- Some natives return `false` or `0` for missing entities; always check `entity ~= 0 and DoesEntityExist(entity)`.

## Floats

- Float params must be float-subtype numbers: `1.0`, not `1`. Coerce computed values: `heading + 0.0`.
- Vectors: `vector3(x + 0.0, y + 0.0, z + 0.0)` when building from integers.

## Hashes

- `` `prop_box_wood01a` `` (compile-time joaat) or `joaat("prop_box_wood01a")`.
- Compare hashes to hashes. Material hashes and model hashes can be negative ints; store them as given in config.

## Asset Loading

```lua
lib.requestModel(model, 5000)
lib.requestAnimDict(dict, 5000)
lib.requestNamedPtfxAsset(asset, 5000)
```

- Release after use: `SetModelAsNoLongerNeeded(model)`, `RemoveAnimDict(dict)`, `RemoveNamedPtfxAsset(asset)` when the resource no longer needs them.
- Cache loaded ptfx assets on the controller to avoid re-requesting every effect.

## Entities

- Local prop: `CreateObject(model, x, y, z, false, false, false)` then `FreezeEntityPosition(obj, true)`, `SetEntityCollision` as needed.
- Ground placement: `GetGroundZFor_3dCoord(x, y, z + 1.0, false)` or a shape test; validate material against `Config` material hash sets.
- Delete: `if DoesEntityExist(obj) then DeleteEntity(obj) end` (multi-line in real code).

## Server-side Natives

Server Lua has a reduced native set (OneSync server natives): `GetEntityCoords`, `GetPlayerPed`, `GetEntityRoutingBucket`, `SetEntityRoutingBucket`, `CreateObjectNoOffset`, `DeleteEntity`, `GetPlayerIdentifierByType`, `IsPlayerAceAllowed`. Do not call client-only natives on the server.

## Verify Before Use

When unsure of a native's parameters or game-build availability, check https://docs.fivem.net/natives/ and record confirmed quirks in `memory/native-gotchas.md`.
