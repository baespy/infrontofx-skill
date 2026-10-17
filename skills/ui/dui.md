# DUI (World-space UI)

DUI renders a web page into a runtime texture that is drawn in the 3D world (floating plant cards, holograms). Each DUI is a full browser instance: expensive. Pool them.

## Pool Pattern (from 1nfx_growth_garden)

```lua
function GrowthGarden:GetFreeDUISlot()
    local slots = self.PlayerState.duiSlots
    for _, slot in ipairs(slots) do
        if slot.loaded and not slot.entity then
            return slot
        end
    end
    if #slots < Config.General.display.max_dui then
        local id = #slots + 1
        slots[id] = { loaded = false, entity = nil }
        slots[id].dui = lib.dui:new({
            id = ("%s_entity_%s"):format(scriptname, id),
            url = ("https://cfx-nui-%s/dui/index.html?id=%s&resource=%s"):format(scriptname, id, scriptname),
            width = 854,
            height = 580,
            debug = false,
        })
    end
    return nil
end

function GrowthGarden:ReleaseDUISlot(entity)
    local slot = entity.duiSlot
    if slot and slot.entity == entity then
        slot.entity = nil
    end
    entity.duiSlot, entity.dui = nil, nil
end
```

- `max_dui` in config (default 5). Only the nearest N entities get a slot.
- A slot is marked `loaded = true` when its page posts a ready callback with its `id`.
- Reassign slots by distance as the player moves; never create/destroy DUI per entity.

## Messaging

```lua
entity.dui:sendMessage({ action = "update", growth = growthPct })
```

- Throttle per entity (`entity.nextUiUpdate = GetGameTimer() + 1000`).
- Send only when values change.

## Drawing

- Draw with `DrawSprite` on the DUI texture dictionary inside a frame loop that runs only while slots are assigned and within `render_distance`.
- Use `SetDrawOrigin(x, y, z + dui_z_offset, 0)` + `DrawSprite(...)` + `ClearDrawOrigin()`; scale by distance.

## Page Rules

- Same design tokens as NUI (`skills/ui/design-system.md`), fixed artboard (854x580) instead of `--px`.
- Read `id` and `resource` from `location.search` to post the ready callback.
- No pointer events; DUI is display only.

## Cleanup

```lua
for _, slot in ipairs(self.PlayerState.duiSlots) do
    if slot.dui then
        slot.dui:remove()
    end
end
self.PlayerState.duiSlots = {}
```

Run on `onResourceStop`.

