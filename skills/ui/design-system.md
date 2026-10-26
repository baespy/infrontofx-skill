# Design System

The `infrontofx` visual language: borderless dark layered panels, matte crimson action surfaces (`#632524`), sharp red indicator pills (`#ff1a1a`), Bai Jamjuree typography, and smooth spring micro-animations scaled from a 1920x1080 artboard.

## Resolution Scaling

All sizes are multiples of `--px` (or `--scale-factor`), so the UI looks identical on 1080p, 1440p, 4K, and ultrawide:

```css
:root {
    --px: min(calc(100vw / 1920), calc(100vh / 1080));
    --scale-factor: var(--px);
}

.panel {
    width: calc(480 * var(--px));
    padding: calc(20 * var(--px)) calc(24 * var(--px));
    border-radius: calc(12 * var(--px));
}
```

Design in Figma at 1920x1080 and copy the pixel numbers straight into `calc(N * var(--px))`.

## Tokens

```css
:root {
    --px: min(calc(100vw / 1920), calc(100vh / 1080));
    --panel: rgba(18, 20, 24, 0.86);
    --panel-blur: rgba(18, 20, 24, 0.78);
    --surface: rgba(255, 255, 255, 0.025);
    --card-bg: rgba(255, 255, 255, 0.04);
    --card-bg-hover: rgba(255, 255, 255, 0.08);
    --card-solid: rgba(28, 31, 38, 0.76);
    --input-bg: rgba(0, 0, 0, 0.35);
    --btn-red: #632524;
    --btn-red-hover: #7a2e2d;
    --btn-red-active: #521e1d;
    --btn-secondary: rgba(255, 255, 255, 0.06);
    --btn-secondary-hover: rgba(255, 255, 255, 0.12);
    --red: #ff1a1a;
    --red-soft: rgba(255, 26, 26, 0.15);
    --blue: #1369c4;
    --blue-pill: #1d4b7a;
    --blue-stripe: #29b6ff;
    --green: #10b981;
    --yellow: #f5ab0b;
    --text: #ffffff;
    --text2: rgba(255, 255, 255, 0.55);
    --text3: rgba(255, 255, 255, 0.35);
    --shadow: 0 calc(24 * var(--px)) calc(64 * var(--px)) rgba(0, 0, 0, 0.84);
    --ease: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### Color & Surface Rules

- **Borderless hierarchy**: Never use `1px solid` borders on panels, cards, inputs, or buttons (`border: none`). Separate layers using background luminance steps (`--panel` -> `--surface` -> `--card-bg` -> `--card-bg-hover`).
- **Matte crimson actions (`#632524`)**: Primary buttons, active tabs, selected cards, and keybind action pills use `--btn-red` (`#632524`) with `#ffffff` bold text and hover `--btn-red-hover` (`#7a2e2d`).
- **Pure red accents (`#ff1a1a`)**: Reserve bright `--red` (`#ff1a1a`) for small visual anchors only:
  - Header vertical pill (`3.5 * var(--px)` wide, `18-24 * var(--px)` tall, `border-radius: 999px`)
  - Active sidebar/card indicator bar (`3 * var(--px)` wide)
  - Progress bar fills (`linear-gradient(90deg, #ff1a1a, #ff5252)`)
  - Eyebrow kicker labels and price/reward highlights

## FiveM CEF Blur & Backdrop Rule

- **Never apply `backdrop-filter: blur(...)` to full-screen NUI wrappers** (`body`, `#app`, `.modal-backdrop`, `body::before`) over a transparent page. In FiveM CEF, blurring the root transparent backbuffer renders as an opaque pitch-black screen.
- **Blurring the game world**: Call `TriggerScreenblurFadeIn(250)` when opening a full menu and `TriggerScreenblurFadeOut(250)` when closing (plus `TriggerScreenblurFadeOut(0)` in `onResourceStop`). Pair it with `--panel-blur` (`rgba(18, 20, 24, 0.78)`) on the window and a soft radial vignette (`radial-gradient(circle at 50% 45%, rgba(10, 12, 16, 0.25) 0%, rgba(6, 8, 12, 0.55) 100%)`) with `backdrop-filter: none !important;` on the full-screen wrapper.
- **Inner popovers only**: CSS `backdrop-filter: blur(12px)` is allowed only on floating dropdown menus positioned over an already-opaque NUI panel.
- **Floating HUD / notification wrappers**: Outer containers for corner HUDs and item notifications must use `background: transparent !important; box-shadow: none !important; overflow: visible !important;` so card shadows are never hard-clipped into dark rectangular bands.

## Typography & Copy

- Use `"Bai Jamjuree", "Segoe UI", sans-serif` (`weights 400, 500, 600, 700, 800`) for Thai and Latin coverage.
- Sizes: header title `18-22`, section title `14-15`, body/card title `12-13`, meta/eyebrow `9.5-10.5` (all `* var(--px)`).
- Action buttons, badges, and keybind prompts use concise uppercase English (`CONFIRM`, `CANCEL`, `CLOSE`, `OPEN`, `MAX`, `ADD`, `REMOVE`, `READY`) with `font-weight: 700-800` and `letter-spacing: 0.05em`. Titles and descriptions use Thai or bilingual copy.

## Base Reset (No Focus Rings, No Scrollbars)

```css
*,
*::before,
*::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    border: none;
    outline: none !important;
    -webkit-font-smoothing: antialiased;
    user-select: none !important;
    -webkit-user-select: none !important;
    -webkit-user-drag: none;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}

*::-webkit-scrollbar {
    width: 0 !important;
    height: 0 !important;
    display: none !important;
}

*:focus,
*:focus-visible,
button:focus,
button:focus-visible,
input:focus {
    outline: none !important;
    box-shadow: none !important;
}

[hidden] {
    display: none !important;
}

html,
body {
    width: 100vw;
    height: 100vh;
    background: transparent !important;
    backdrop-filter: none !important;
    overflow: hidden;
    font-family: "Bai Jamjuree", "Segoe UI", sans-serif;
    color: var(--text);
    cursor: default !important;
}
```

Prevent `Tab` from leaving browser focus rings on buttons in NUI:

```js
window.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
        event.preventDefault();
        if (document.activeElement && document.activeElement !== document.body) {
            document.activeElement.blur();
        }
    }
}, true);
```

## Components

| Component | Recipe |
| --- | --- |
| Panel / Window | `--panel` (or `--panel-blur` with `TriggerScreenblurFadeIn`), `border: none`, radius `12-14`, `--shadow`, centered |
| Brand header | red pill (`3.5 x 22`, radius `999px`, `--red`) + uppercase eyebrow (`9.5`, `--text3` or `--red`) + bold title (`18-20`) + `CLOSE` button (`--btn-secondary`, hover `--btn-red`) |
| Divider | `1px` solid `rgba(255, 255, 255, 0.06)` (no dashed borders) |
| Row / Card | `--card-bg`, `border: none`, radius `8-10`, hover `--card-bg-hover` + `translateY(-1.5px)` or `translateX(3px)`, selected `--btn-red` (`#632524`) with `#ffffff` text |
| Primary button | bg `--btn-red` (`#632524`), text `#ffffff`, radius `8`, `font-weight: 800`, hover `--btn-red-hover` (`#7a2e2d`) + `translateY(-1.5px)`, active `scale(0.97)` |
| Secondary button | bg `--btn-secondary` (`rgba(255, 255, 255, 0.06)`), text `--text2`, radius `8`, hover `--btn-secondary-hover` + text `#ffffff` |
| Collapsible HUD card | Compact header row with red pill, title, compact timer badge (`--card-solid`), and `[KEY] OPEN/CLOSE` button (`--btn-red`) with dark key badge (`rgba(0, 0, 0, 0.35)`); body collapses via `max-height` + `opacity` |
| Item notify card | Compact `168 x 52` card, `rgba(20, 22, 26, 0.9)`, `box-shadow: none`, `38 x 38` icon box (`rgba(10, 12, 16, 0.68)`), `ADD` (`#1d4b7a`) / `REMOVE` (`#632524`) pill + `xCount`, item label, right accent bar (`#29b6ff` / `#ff1a1a`) |
| Confirm modal | Centered `.modal-box` (`--panel`, radius `12`, `--shadow`), red pill header, info rows (`--card-bg`), two-column `CANCEL` (`--btn-secondary`) + `CONFIRM` (`--btn-red`) buttons |

Never render generic notifications, toasts, or error banners inside menu UIs; route notifications through `FC.Notify` (`pNotify:SendNotification`) on the Lua side. Produced HTML, CSS, JS, TS, TSX, Svelte, and Vue files must contain zero comments.

## Motion

- Panel entrance: `opacity: 0; transform: translateY(12px) scale(0.96)` -> `opacity: 1; transform: translateY(0) scale(1)` over `220ms var(--ease)`.
- Staggered list/grid items: animate cards with `220ms var(--ease) both` and `nth-child(1..8)` delays (`0ms`, `35ms`, `70ms`, `105ms`, `140ms`, ...).
- Hover and press: `160ms var(--ease)` on `transform` and `background-color`.
- Animate `transform` and `opacity` only (GPU). No infinite animations while hidden.

## Accessibility And UX

- Every interactive control is a `<button type="button">` with `cursor: pointer !important`.
- ESC closes open modals/dropdowns first, then posts `close` to Lua.
- Disable action buttons while `busy`; show progress copy on the button.
- Format numbers with `toLocaleString("en-US")` or `"th-TH"` consistently.
