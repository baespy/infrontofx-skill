# Extreme x HP Clean UI (default UI style)

This is the default visual language for every `1nfx_*` NUI, HUD and menu: the HP (`stl_*`) clean vibrant look fused with the Extreme (`1NFX`) crimson identity. It overrides any older palette in this pack. Zero white borders, saturated colors, readable type, 60 fps micro-animations and no blur.

## 1. Visual rules

1. **No white borders anywhere.** Panels, modals, cards, slots, chips, inputs and buttons never use white or light-grey borders or rings.
   - Forbidden: `border: 1px solid rgba(255, 255, 255, ...)`, `border-color: #fff`, `box-shadow: inset 0 0 0 1px rgba(255, 255, 255, ...)`, `inset 0 1px 0 rgba(255, 255, 255, ...)`.
   - Separate surfaces with tonal depth (`--ex-panel`, `--ex-card`, `--ex-well`) and a dark drop shadow (`0 20px 54px rgba(0, 0, 0, 0.62)`).
   - A colored border or ring is allowed only for active, selected or semantic states: crimson `rgba(255, 38, 61, 0.45)`, emerald `rgba(46, 229, 157, 0.38)`, gold `rgba(255, 191, 63, 0.38)`, cyan `rgba(56, 189, 248, 0.38)`, or a dark recessed seam `rgba(0, 0, 0, 0.45)`.
2. **Rich, vibrant color. Never pale, never muddy.**
   - Panel: `linear-gradient(180deg, rgba(25, 29, 40, 0.965) 0%, rgba(13, 15, 22, 0.985) 100%)`.
   - Card or slot: `linear-gradient(155deg, rgba(42, 47, 62, 0.78) 0%, rgba(26, 30, 41, 0.88) 100%)`, hover `rgba(56, 63, 82, 0.88)`.
   - Recessed input or bar well: `rgba(9, 11, 17, 0.84)`.
   - Primary crimson: `#ff263d` with `linear-gradient(135deg, #ff364d 0%, #cf1025 100%)` and glow `0 6px 18px rgba(255, 38, 61, 0.36)`. Never use the muddy brown-red `#632524`.
   - Semantic accents: emerald `#2ee59d` for cash, online, success, add (pill fill `rgba(46, 229, 157, 0.16)`); gold `#ffbf3f` for tokens, VIP, rank one, bonus, warning (`rgba(255, 191, 63, 0.16)`); sky cyan `#38bdf8` for armor, shield, police, stamina, info (`rgba(56, 189, 248, 0.16)`).
   - Header icon badge (HP signature): a 36 to 40 px circle or 10 px rounded square, `linear-gradient(135deg, #ff364d 0%, #cf1025 100%)`, `box-shadow: 0 0 0 3px rgba(255, 38, 61, 0.28), 0 6px 16px rgba(207, 16, 37, 0.45)`.
3. **Readable typography.**
   - Load the shared tokens in the `<head>` of every HTML entry: `<link rel="stylesheet" href="https://cfx-nui-1nfx_statushud/Interface/extreme-core.css" />`, and always define the `:root` fallback variables in the resource's own CSS so it never breaks standalone.
   - Main text (Thai and English): `"LINESeedSansTH", "LINESeedSans", "Bai Jamjuree", sans-serif`.
   - Numbers, timers, prices, badges: `"Rajdhani", "LINESeedSans", "Bai Jamjuree", sans-serif` with `font-variant-numeric: tabular-nums`.
   - Sizes: window title 20 to 22 px (700 to 800, `#f8fafc`); card title, item name, button text 13 to 15 px (700, `#f8fafc`); subtitle and label 11.5 to 12.5 px (600 to 700, `#94a3b8`); key values, balances, speed, counters 18 to 28 px (700 to 800, tabular-nums).
   - Spacing: 16 to 24 px window padding, 12 to 16 px card padding, pill (`999px`) or 10 px radius buttons, a 34 to 36 px circular close button top right that turns crimson on hover.
4. **60 fps micro-animations and zero blur.**
   - Never use `backdrop-filter: blur(...)`. Set `backdrop-filter: none !important` on full-screen wrappers. To soften the world behind a full menu use `TriggerScreenblurFadeIn(250)` and `TriggerScreenblurFadeOut(250)` from Lua.
   - Panel entrance: `@keyframes exIn { from { opacity: 0; transform: translateY(10px) scale(0.975); } to { opacity: 1; transform: translateY(0) scale(1); } }` at `240ms cubic-bezier(0.16, 1, 0.3, 1)`.
   - Card or row hover: `translateY(-2px)` and a surface brighten at `160ms cubic-bezier(0.16, 1, 0.3, 1)`.
   - Button: hover `translateY(-1px)` with a vibrant shadow; `:active` `scale(0.96)`.
   - Progress, gauges and tabs: `cubic-bezier(0.22, 1, 0.36, 1)` on width, transform and stroke-dashoffset.
   - Animate only `transform` and `opacity`.

## 2. Redesign safety (UI-only passes)

When a task is a visual redesign only:

1. Do not touch any `.lua` file or `fxmanifest.lua`.
2. Preserve the whole JS to HTML/CSS contract: every `id`, JS-targeted `class`, `data-*` attribute, input `name` or `id`, inline `onclick`, NUI `message` payload field and `fetch`/`$.post` callback URL stays intact.
3. Respect how JS shows and hides the page (`style.display`, jQuery `fadeIn`/`fadeOut`/`show`/`hide`, or classes such as `.active`, `.open`, `.show`, `.hidden`). Never write CSS (for example `display: flex !important` on a hidden root) that keeps a closed NUI page visible.
4. Compiled Vite, React or Vue resources: do not edit the compiled bundle. Read the compiled class names, add an `extreme-theme.css` next to `index.html` (the manifest already globs that folder), link `extreme-core.css` and then `./extreme-theme.css` at the end of `<head>`, and update the CSS under `interface-dev/src/` so the source stays in sync.
5. Save every file as UTF-8 without BOM.
6. Code style still applies to UI files: no comments, no file-level constants.

## 3. Checklist before shipping a UI

- [ ] No white border or ring on any surface; colored rings only for active or semantic states.
- [ ] Palette comes from the tokens above; no `#632524`.
- [ ] No `backdrop-filter: blur`; closed pages hidden with `display: none`.
- [ ] Fonts and icons load locally; `extreme-core.css` linked and `:root` fallbacks defined.
- [ ] Hover, active and disabled states exist for every control.
- [ ] Opening and closing 10 times leaves no stuck focus, listener or timer.
