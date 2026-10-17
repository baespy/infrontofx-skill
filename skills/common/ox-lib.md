# ox_lib

ox_lib is always present in infrontofx resources (`"@ox_lib/init.lua"` first in `shared_scripts`). Use it for performance primitives, not for UI.

## Allowed

| Module | Use for |
| --- | --- |
| `lib.callback` / `lib.callback.await` / `lib.callback.register` | client <-> server request/response |
| `lib.points` | per-location enter/exit/nearby without distance loops |
| `lib.zones` (`box`, `sphere`, `poly`) | area triggers |
| `cache.ped`, `cache.coords`, `cache.vehicle`, `cache.seat`, `cache.playerId`, `cache.serverId` | cached natives |
| `lib.onCache` | react to cache changes |
| `lib.table.deepclone`, `lib.table.contains`, `lib.array` | table helpers |
| `lib.cron` | scheduled server jobs |
| `lib.dui` | world-space DUI rendering (`skills/ui/dui.md`) |
| `lib.requestModel`, `lib.requestAnimDict`, `lib.requestNamedPtfxAsset` | asset loading with timeout |
| `lib.addKeybind` | rebindable keys |
| `lib.raycast` | camera raycasts for placement |

## Forbidden

| Do not use | Use instead |
| --- | --- |
| `lib.notify` | `FC.Notify` (pNotify) |
| `lib.progressBar`, `lib.progressCircle` | `FC.Progress` (`1nfx_processbar`) |
| `lib.showTextUI`, `lib.hideTextUI` | `FC.ShowTextUI` / `FC.HideTextUI` (`1nfx_textui`) |
| `lib.registerContext`, `lib.inputDialog`, `lib.alertDialog` | resource NUI or `1nfx_dialogui` via `FC` |

## Points Cleanup

Store every point/zone on the controller and remove on stop:

```lua
self.Points[#self.Points + 1] = point
```

```lua
for _, point in ipairs(self.Points) do
    point:remove()
end
self.Points = {}
```

