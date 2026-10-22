# ESX API For FC Adapters

Source selection: verify APIs against the installed `es_extended` and the official https://github.com/esx-framework/esx_core repository. On 2026-10-22 the former docs.esx-legacy.com URL returned a parked-domain page; do not use it as API evidence. A local or newer fork may have different return shapes and integration ownership.

All ESX calls live inside `config/function/config.function.client.lua` and `config/function/config.function.server.lua` (`skills/common/fc-adapters.md`). Core files (`core/cl_*.lua`, `core/sv_*.lua`) call `FC.*` instead of touching ESX inventory/account internals directly.

## Bootstrap

Every client and server file initializes ESX at line 1:

```lua
ESX = exports["es_extended"]:getSharedObject()
```

Never use `TriggerEvent("esx:getSharedObject", ...)`.

## Server Player Methods (`xPlayer = ESX.GetPlayerFromId(source)`)

Always resolve `local xPlayer = ESX.GetPlayerFromId(source)` in server `FC` adapters using standard ESX methods so the resource works on any standard ESX server:

| Method | Signature | Returns |
| --- | --- | --- |
| `getIdentifier` | `xPlayer.getIdentifier()` | license/identifier string |
| `getName` | `xPlayer.getName()` | character name string |
| `getJob` | `xPlayer.getJob()` | `{ name, label, grade, grade_name, grade_salary }` |
| `getInventory` | `xPlayer.getInventory()` | array of `{ name, count, label, limit, ... }` |
| `getInventoryItem` | `xPlayer.getInventoryItem(itemName)` | `{ name, count, label, limit }` or nil |
| `canCarryItem` | `xPlayer.canCarryItem(itemName, count)` | boolean |
| `addInventoryItem` | `xPlayer.addInventoryItem(itemName, count)` | - |
| `removeInventoryItem` | `xPlayer.removeInventoryItem(itemName, count)` | - |
| `getAccounts` | `xPlayer.getAccounts()` | array of `{ name, money, label }` |
| `getAccount` | `xPlayer.getAccount(accountName)` | `{ name, money, label }` or nil |
| `addAccountMoney` | `xPlayer.addAccountMoney(accountName, amount)` | - |
| `removeAccountMoney` | `xPlayer.removeAccountMoney(accountName, amount)` | - |
| `getMoney` | `xPlayer.getMoney()` | integer |
| `addMoney` | `xPlayer.addMoney(amount)` | - |
| `removeMoney` | `xPlayer.removeMoney(amount)` | - |
| `hasWeapon` | `xPlayer.hasWeapon(weaponName)` | boolean |
| `getWeapon` | `xPlayer.getWeapon(weaponName)` | loadNum, weaponTable |

## Server Shared Object Helpers

| Call | Returns |
| --- | --- |
| `ESX.GetPlayerFromId(source)` | `xPlayer` object or nil |
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
