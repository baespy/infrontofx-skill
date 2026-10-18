# FC Adapters

`FC` is the resource's integration and owner-customization boundary. Core files call `FC.*`; they do not call ESX inventory/account methods, pNotify, progress resources, text UI resources, webhooks, or owner hooks directly.

## Files And Load Order

- `config/function/config.function.client.lua` loads before `core/cl_*`.
- `config/function/config.function.server.lua` loads before `core/sv_*`.
- Both files use the mandatory client/server header, then `FC = FC or {}`.
- Keep `FC` flat. Do not add adapter classes, providers, registries, or dispatchers.

The canonical implementations are in `templates/resource/config/function/`. Read the matching template when creating or replacing an adapter; do not duplicate the complete implementation here.

## Entry Types

Adapters wrap framework or third-party APIs. Hooks expose deliberate owner choices:

| Kind | Shape | Rule |
| --- | --- | --- |
| Adapter | `FC.Notify`, `FC.GetItem`, `FC.AddItem` | Thin translation of one external contract |
| Gate hook | `FC.CanOpenShop`, `FC.CanPurchase` | Returns a boolean; core must respect it |
| Reaction hook | `FC.OnPurchased`, `FC.Log` | Runs after the named action; no hidden authority change |

Do not wrap controller methods in `FC`. Business flow stays on the controller; only integration and customization cross this boundary.

## Client Contract

Use only the entries the resource needs. Common names:

- `FC.Notify(label, type)`
- `FC.GetItem(name)`, `FC.GetItemCount(name)`, `FC.GetItemLabel(name)`
- `FC.GetAccount(name)`, `FC.GetMoney(name)`
- `FC.ShowTextUI(text)`, `FC.HideTextUI()`
- `FC.Progress(data, onFinish)`
- `FC.CanOpenXxx(data)` and `FC.OnXxx(data)`

Client adapters are UX helpers only. They never prove inventory, money, job, permission, elapsed time, ownership, or reward eligibility to the server.

## Server Contract

Common names:

- `FC.Notify(source, label, type)`
- `FC.GetIdentifier(source)`, `FC.GetPlayerName(source)`, `FC.GetJob(source)`
- `FC.GetItem(source, name)`, `FC.GetItemCount(source, name)`, `FC.CanCarryItem(source, name, count)`
- `FC.AddItem(source, name, count)`, `FC.RemoveItem(source, name, count)`
- `FC.GetAccount(source, name)`, `FC.GetMoney(source, name)`, `FC.AddMoney(...)`, `FC.RemoveMoney(...)`
- `FC.Log(source, event, content)`
- `FC.CanXxx(source, data)` and `FC.OnXxx(source, data)`

Server adapters return explicit success when core must react to failure. Core validates names, counts, amounts, permissions, distance, bucket, cooldown, and ownership before calling a mutation adapter.

## Guard Policy

- Do not add `if not label or label == "" then return end` to notify or text adapters. Core owns these values.
- Do not invent default counts or amounts in mutation adapters. Callers pass already validated values.
- It is valid to check `xPlayer` before calling a framework method because disconnects and post-yield source reuse are runtime failures.
- Preserve framework fallbacks only when the supported ESX versions genuinely differ, such as `canCarryItem` versus legacy item limits.
- Do not catch and hide adapter errors unless the external integration is explicitly optional.

## Hooks

- Name gates `FC.CanXxx` and reactions `FC.OnXxx`.
- Call a gate before setting an in-flight mutation state when possible.
- Run reaction hooks only after success.
- Hooks may read controller state but must not mutate controller internals behind its methods.
- Only server hooks may grant value. Client hooks affect presentation only.
- Swap inventory, notifications, progress, text UI, and logging by editing these two files only.

See `references/esx-api.md` and `references/pnotify-api.md` for the supported external contracts.
