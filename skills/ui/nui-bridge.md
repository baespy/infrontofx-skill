# NUI Bridge

NUI is a Chromium page per resource. It is display and input only; it never decides value.

## Manifest

```lua
ui_page "html/index.html"

files {
    "html/**",
}
```

Vite/React builds: `ui_page "web/dist/index.html"` and `files { "web/dist/**" }`, built with `base: "./"`.

## Message Contract

Lua -> UI, always `{ action, data }`:

```lua
SendNUIMessage({ action = "open", data = payload })
```

UI -> Lua, `fetch` POST to `https://<resource>/<callback>` with JSON, response `{ ok = boolean, ... }`.

Resolve `<resource>` at runtime with `GetParentResourceName()`. Never hardcode the resource folder name in JavaScript.

Name UI actions in camelCase, optionally namespaced (`"shopMenu:open"`) when one page hosts several apps.

## Ready Handshake

Messages sent before the page loads are lost. Queue them until the UI announces readiness; do not create one waiting thread per message.

The pending queue must be bounded. Coalesce replaceable state messages by action or stable id and keep ordered entries only for non-replaceable actions. Clear it on stop and UI reload.

Client controller:

```lua
Template = {
    ServerState = {},
    PlayerState = { uiOpen = false, uiReady = false },
    PendingNUI = {},
}

function Template:PostNUI(action, data)
    local message = { action = action, data = data }
    if not self.PlayerState.uiReady then
        for index = #self.PendingNUI, 1, -1 do
            if self.PendingNUI[index].action == action then
                self.PendingNUI[index] = message
                return
            end
        end
        if #self.PendingNUI >= Config.General.nui_queue_limit then
            table.remove(self.PendingNUI, 1)
        end
        self.PendingNUI[#self.PendingNUI + 1] = message
        return
    end
    SendNUIMessage(message)
end

RegisterNUICallback("uiReady", function(_, cb)
    Template.PlayerState.uiReady = true
    for index = 1, #Template.PendingNUI do
        SendNUIMessage(Template.PendingNUI[index])
    end
    Template.PendingNUI = {}
    cb({ ok = true })
end)
```

UI side retries until Lua answers:

```js
async ready() {
    try {
        await Nui.post("uiReady");
    } catch {
        setTimeout(() => this.ready(), 1000);
    }
}
```

## Open / Close

```lua
function Template:SetUI(open, data)
    self.PlayerState.uiOpen = open
    SetNuiFocus(open, open)
    self:PostNUI(open and "open" or "close", data)
end

RegisterNUICallback("close", function(_, cb)
    Template:SetUI(false)
    cb({ ok = true })
end)
```

- Close on: ESC (UI posts `close`), player death, `onResourceStop`, distance exit.
- `SetNuiFocus(true, true)` for menus. `SetNuiFocusKeepInput(true)` only for HUD-like overlays that must keep movement; restore `false` on close.
- Never call `SetNuiFocus` every frame.

## Callbacks Forwarding To Server

```lua
RegisterNUICallback("buy", function(data, cb)
    if type(data) ~= "table" or type(data.item) ~= "string" then
        cb({ ok = false })
        return
    end
    local ok, result = lib.callback.await(scriptname .. ":SV:buy", false, {
        shopId = Template.PlayerState.shopId,
        item = data.item,
        amount = tonumber(data.amount) or 0,
    })
    cb({ ok = ok == true, result = result })
end)
```

- `cb` exactly once on every branch.
- Return a stable shape such as `{ ok, data, error }`; do not make UI code infer success from unrelated fields.
- The shop id comes from Lua state, not the UI, so the UI cannot pick a different shop.
- The server re-validates everything (`skills/common/security.md`).

## Payload Hygiene

- Send only what the UI renders: labels, counts, prices for display, ids.
- No vectors/userdata: convert `coords` to `{ x = c.x, y = c.y, z = c.z }`.
- No secrets, webhook URLs, admin flags, hidden reward data.

## XSS

Any string another player controls (names, custom labels, chat) must be rendered as text:

- Vanilla: `el.textContent = value`. Never `innerHTML` with data.
- React/Vue/Svelte: `{value}` binding. Never `dangerouslySetInnerHTML`, `v-html`, `{@html}` with data.
- Asset paths from data: allowlist characters (`/^[a-z0-9_]+$/`) before building `nui://` or `img` URLs.

Injected script in NUI can call every `RegisterNUICallback` as the victim.

## Performance

- Send on change, not per frame. Batch rapid updates (one message per 100-250 ms max).
- For high-rate telemetry, collect changes and send one frame or interval batch. Cap buffered entries and bytes; discard or coalesce replaceable stale data before memory grows.
- Keep the page idle when hidden: stop timers/animations, `hidden` attribute instead of opacity-only hiding.
- Move encoding or transformation to a Web Worker only after profiling shows it blocks the UI thread; workers add transfer and lifecycle cost.
- All JS/CSS local; no CDN at runtime.
- Never display toasts, notifications, or error banners inside the NUI page; trigger notifications on the Lua side via `FC.Notify`.
- Produced UI files (`HTML`, `CSS`, `JS`, `TS`, `TSX`, `Vue`) contain zero comments.

## Cleanup

```lua
AddEventHandler("onResourceStop", function(resource)
    if resource ~= scriptname then
        return
    end
    SetNuiFocus(false, false)
end)
```

The UI also removes global listeners, intervals, animation frames, observers, workers, media streams, object URLs, and unresolved callback entries when its app is destroyed or reloaded.
