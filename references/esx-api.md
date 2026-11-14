# ESX-compatible API (Core)

Source selection: `1nfx_core` is the server's own framework and exposes an ESX-compatible surface as the global `Core`. The API shapes below come from ESX (verify against the official https://github.com/esx-framework/esx_core repository and the installed `1nfx_core`). On 2026-10-22 the former docs.esx-legacy.com URL returned a parked-domain page; do not use it as API evidence. A local or newer fork may have different return shapes and integration ownership.

All framework calls live inside `core/` methods of the module (`skills/common/core-api.md`). There is no `FC` layer.

## Bootstrap

Resources load the framework through the manifest:

```lua
shared_scripts {
    "@ox_lib/init.lua",
    "@1nfx_core/imports.lua",
}
```

This provides the global `Core`. Do not use `exports["es_extended"]:getSharedObject()` or `TriggerEvent("esx:getSharedObject", ...)`. Where older documentation says `ESX.X`, use `Core.X`.

## Server Player Methods (`xPlayer = Core.GetPlayerFromId(source)`)

Resolve `local xPlayer = Core.GetPlayerFromId(source)` once per job, nil-check it, and use the standard ESX methods so the resource stays compatible:

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
| `Core.GetPlayerFromId(source)` | `xPlayer` object or nil |
| `Core.GetExtendedPlayers(key?, val?)` | list of online `xPlayer` objects (`Core.GetExtendedPlayers("job", "police")`) |
| `Core.GetItemLabel(itemName)` | item label string |
| `Core.GetWeaponLabel(weaponName)` | weapon label string |
| `Core.RegisterUsableItem(itemName, cb)` | registers usable item callback `function(source)` |

## Client Shared Object Helpers

| Call | Returns |
| --- | --- |
| `Core.IsPlayerLoaded()` | boolean |
| `Core.GetPlayerData()` | `{ inventory, accounts, job, loadout, identifier, ... }` |
| `Core.GetItemLabel(itemName)` | item label string |
| `Core.GetWeaponLabel(weaponName)` | weapon label string |

Client values from `Core.GetPlayerData()` are a local cache for UX display only. Never trust client item counts, money, or job on the server.

## Framework Events (Listen Only)

Names are `1nfx_core:*`. Legacy `esx:*` names still fire locally for old resources, but new code listens to the `1nfx_core:*` names.

- Client: `1nfx_core:playerLoaded`, `1nfx_core:onPlayerLogout`, `1nfx_core:setJob`, `1nfx_core:onPlayerDeath`, `1nfx_core:onPlayerSpawn`
- Server: `1nfx_core:playerLoaded`, `1nfx_core:playerDropped`, `1nfx_core:setJob`

The `1nfx_core:*` names above are the ESX event names with the prefix swapped; confirm each against the installed `1nfx_core` before depending on it.
