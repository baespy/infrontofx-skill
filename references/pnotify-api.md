# pNotify API

Always call through `FC.Notify`.

## Payload

```lua
{
    text = "ข้อความ",
    type = "info",
    timeout = 5000,
    layout = "topCenter",
    queue = "global",
}
```

| Field | Values |
| --- | --- |
| `type` | `"success"`, `"error"`, `"warning"` / `"alert"`, `"info"` |
| `timeout` | ms, optional |
| `layout` | `topLeft`, `topCenter`, `topRight`, `centerLeft`, `center`, `centerRight`, `bottomLeft`, `bottomCenter`, `bottomRight` (optional) |
| `queue` | queue name to group/stack (optional) |

## Client

```lua
TriggerEvent("pNotify:SendNotification", { text = label, type = notifyType })
```

## Server

```lua
TriggerClientEvent("pNotify:SendNotification", source, { text = label, type = notifyType })
```

## Rules

- Player-facing text comes from `Config.Text`.
- pNotify renders HTML. Never pass raw player-controlled strings (names, renamed labels) without stripping `<` and `>`:
  ```lua
  local safe = tostring(value):gsub("[<>]", "")
  ```
- Avoid `-1` broadcasts except for rare server-wide announcements.

