# ESX API For FC Adapters

All ESX calls live inside `config/function/config.function.client.lua` and `config/function/config.function.server.lua` (`skills/common/fc-adapters.md`). Core files (`core/cl_*.lua`, `core/sv_*.lua`) call `FC.*` instead of touching ESX inventory/account internals directly.

## Bootstrap

Every client and server file initializes ESX at line 1:

```lua
ESX = exports["es_extended"]:getSharedObject()
```

Never use `TriggerEvent("esx:getSharedObject", ...)`.

## Server Static Player Methods

Prefer `exports["es_extended"]:RunStaticPlayerMethod(source, method, ...)` in server `FC` adapters. It runs the method inside `es_extended` without serializing the full `xPlayer` table across resource boundaries.

| Method | Signature | Returns |
| --- | --- | --- |
| `getIdentifier` | `RunStaticPlayerMethod(source, "getIdentifier")` | license/identifier string or nil |
| `getName` | `RunStaticPlayerMethod(source, "getName")` | character name string |
| `getJob` | `RunStaticPlayerMethod(source, "getJob")` | `{ name, label, grade, grade_name, grade_salary }` |
| `getInventory` | `RunStaticPlayerMethod(source, "getInventory")` | array of `{ name, count, label, limit, ... }` |
| `getInventoryItem` | `RunStaticPlayerMethod(source, "getInventoryItem", itemName)` | `{ name, count, label, limit }` or nil |
| `canCarryItem` | `RunStaticPlayerMethod(source, "canCarryItem", itemName, count)` | boolean |
| `addInventoryItem` | `RunStaticPlayerMethod(source, "addInventoryItem", itemName, count)` | - |
| `removeInventoryItem` | `RunStaticPlayerMethod(source, "removeInventoryItem", itemName, count)` | - |
| `getAccounts` | `RunStaticPlayerMethod(source, "getAccounts")` | array of `{ name, money, label }` |
| `getAccount` | `RunStaticPlayerMethod(source, "getAccount", accountName)` | `{ name, money, label }` or nil |
| `addAccountMoney` | `RunStaticPlayerMethod(source, "addAccountMoney", accountName, amount)` | - |
| `removeAccountMoney` | `RunStaticPlayerMethod(source, "removeAccountMoney", accountName, amount)` | - |
| `hasWeapon` | `RunStaticPlayerMethod(source, "hasWeapon", weaponName)` | boolean |
| `getWeapon` | `RunStaticPlayerMethod(source, "getWeapon", weaponName)` | loadNum, weaponTable |

## Server Shared Object Helpers

| Call | Returns |
| --- | --- |
| `ESX.GetPlayerFromId(source)` | full `xPlayer` (use only when multiple fields are needed in one call) |
| `ESX.GetExtendedPlayers(key?, val?)` | list of online `xPlayer` objects (`ESX.GetExtendedPlayers("job", "police")`) |
| `ESX.GetItemLabel(itemName)` | item label string |
| `ESX.GetWeaponLabel(weaponName)` | weapon label string |
| `ESX.RegisterUsableItem(itemName, cb)` | registers usable item callback `function(source)` |

## Client Shared Object Helpers

| Call | Returns |
| --- | --- |
| `ESX.IsPlayerLoaded()` | boolean |
| `ESX.GetPlayerData()` | `{ inventory, accounts, job, loadout, identifier, ... }` |
| `ESX.GetItemLabel(itemName)` | item label string |
| `ESX.GetWeaponLabel(weaponName)` | weapon label string |

Client values from `ESX.GetPlayerData()` are a local cache for UX display only. Never trust client item counts, money, or job on the server.

## Standard ESX Events (Listen Only)

- Client: `esx:playerLoaded`, `esx:onPlayerLogout`, `esx:setJob`, `esx:onPlayerDeath`, `esx:onPlayerSpawn`
- Server: `esx:playerLoaded`, `esx:playerDropped`, `esx:setJob`

