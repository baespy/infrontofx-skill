# 1nfx UI Resources API

Call these only from `FC` adapters.

## 1nfx_textui (client)

| Export | Use |
| --- | --- |
| `ShowHelpNotificationToggle(message)` | show persistent prompt (call on point enter) |
| `ClearHelpNotification()` | hide prompt (call on point exit / UI open) |
| `ShowHelpNotification(message)` | per-frame prompt (call every frame while visible) |
| `Show(data)` | press prompt: `{ text, key = 51, keylabel = "E", time = 1000 }` |
| `ShowHold(data)` | hold-to-confirm prompt, same shape as `Show` |

Preferred: toggle on `onEnter`, clear on `onExit` - no per-frame cost.

## 1nfx_processbar (client)

mythic_progbar compatible.

```lua
exports["1nfx_processbar"]:Progress({
    name = "harvest",
    duration = 3000,
    label = "กำลังเก็บเกี่ยว...",
    useWhileDead = false,
    canCancel = true,
    controlDisables = {
        disableMovement = true,
        disableCarMovement = true,
        disableMouse = false,
        disableCombat = true,
    },
    animation = { animDict = "amb@world_human_gardener_plant@male@base", anim = "base", flags = 49 },
    prop = { model = "prop_cs_trowel", bone = 6286, coords = { x = 0.0, y = 0.0, z = 0.0 }, rotation = { x = 0.0, y = 0.0, z = 0.0 } },
}, function(cancelled)
end)
```

Other exports: `ProgressWithStartEvent`, `ProgressWithTickEvent`, `ProgressWithStartAndTick`, `CancelProgress(label)`, `Cleanup()`.

The progress result is client-side UX. The server must still check elapsed time (record start time server-side, reject completion before `duration`).

## 1nfx_textuihologram (client)

`Show(...)`, `Hide(...)` - world-space hologram prompts.

## 1nfx_dialogui (client)

`Open(data)` - generic dialog. Prefer a resource-specific NUI for complex flows.

## 1nfx_serverlogs (server)

```lua
exports["1nfx_serverlogs"]:insertData({
    source = src,
    event = "Shop",
    content = "bread x2 (100)",
    fields = { { name = "Shop", value = "main_market" } },
    color = 3066993,
    options = { public = true },
})
```

| Field | Meaning |
| --- | --- |
| `source` | player id (`0` = system) |
| `event` | log category; must exist in serverlogs config to route to a webhook |
| `content` | main text |
| `fields` | optional embed fields |
| `color` | optional embed color |
| `coords` | optional; auto-read from ped when omitted |
| `image` | optional screenshot url |
| `options.public` | `false` hides identifiers |

## pNotify

See `references/pnotify-api.md`.

