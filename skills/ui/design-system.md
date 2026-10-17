# Design System

The 1nfx visual language: dark glass panels, one red accent, Bai Jamjuree, everything scaled from a 1920x1080 artboard.

## Resolution Scaling

All sizes are multiples of `--px`, so the UI looks identical on 1080p, 1440p, 4K, and ultrawide:

```css
:root {
    --px: min(calc(100vw / 1920), calc(100vh / 1080));
}

.panel {
    width: calc(480 * var(--px));
    padding: calc(20 * var(--px)) calc(24 * var(--px));
    border-radius: calc(10 * var(--px));
}
```

Design in Figma at 1920x1080 and copy the pixel numbers straight into `calc(N * var(--px))`.

## Tokens

```css
:root {
    --background: rgba(20, 22, 25, 0.96);
    --background-2: rgba(30, 32, 36, 0.9);
    --background-3: rgba(40, 40, 40, 0.45);
    --background-4: rgba(0, 0, 0, 0.25);
    --background-card-hover: rgba(255, 255, 255, 0.08);
    --border-white: rgba(255, 255, 255, 0.08);
    --border-card-hover: rgba(255, 255, 255, 0.22);
    --red: #ff1a1a;
    --red-soft: rgba(255, 26, 26, 0.06);
    --red-border: rgba(255, 26, 26, 0.25);
    --green: #3ddc84;
    --yellow: #ffc83d;
    --text: #ffffff;
    --text2: rgba(255, 255, 255, 0.5);
    --text3: rgba(255, 255, 255, 0.28);
    --shadow: 0 calc(10 * var(--px)) calc(35 * var(--px)) rgba(0, 0, 0, 0.65);
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
}
```

Change the accent per resource by overriding `--red` only.

## Typography

```css
@font-face {
    font-family: "Bai Jamjuree";
    src: url("../fonts/BaiJamjuree-600.ttf") format("truetype");
    font-weight: 600;
    font-display: swap;
}
```

- Ship 400/500/600/700 locally in `html/fonts/` (Thai + Latin coverage).
- Sizes: title 15, body 12-13, meta 10.5 (all `* var(--px)`).
- Titles uppercase with letter-spacing `calc(1 * var(--px))`.

## Base Reset

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    -webkit-font-smoothing: antialiased;
    user-select: none;
}

[hidden] {
    display: none !important;
}

html,
body {
    background: transparent !important;
    overflow: hidden;
    font-family: "Bai Jamjuree", sans-serif;
    color: var(--text);
}
```

Body must be transparent; the game renders behind it.

## Components

| Component | Recipe |
| --- | --- |
| Panel | `--background`, 1px `--border-white`, radius 10, `--shadow`, centered with `translate(-50%, -50%)` |
| Brand header | red pill (3.5 x 14, radius 2) + uppercase title + close `x` button in `--text2` |
| Divider | 1px dashed `--border-white` |
| Row / card | `--background-3`, radius 6, hover `--background-card-hover` + `--border-card-hover`, selected `--red-soft` + `--red-border` |
| Primary button | text `--red`, bg `--red-soft`, border `--red-border`; hover text white, stronger red |
| Secondary button | text `--text2`, bg white 4%, border `--border-white` |
| Scrollbar | 4px, track white 2%, thumb red 25% |
| Confirm dialog | absolute overlay inside the panel, dark backdrop, card with two-column actions |
| Error line | `#ffaaa8`, 11px, under the action |

## Motion

- Transitions 150 ms on background/border/color only.
- Open animation: `opacity 0 -> 1` and `scale(0.98) -> 1` over 180 ms with `--ease`.
- Animate `transform` and `opacity` only (GPU). Never animate `width`, `top`, `box-shadow` per frame.
- No infinite animations while hidden.

## Accessibility And UX

- Every interactive element is a `<button type="button">`.
- `:focus-visible` outline in red at 65% alpha.
- ESC closes dialogs first, then the panel. Tab cycles inside an open dialog.
- Disable buttons while `busy`; show progress text ("กำลังลบ...").
- Thai copy for player text; numbers formatted with `toLocaleString("th-TH")`.

## Performance

- One stylesheet, no CSS frameworks at runtime unless the UI is built (Tailwind via Vite build is fine).
- Prefer `hidden` toggles to unmounting heavy lists; use `replaceChildren()` for list re-render.
- Images as SVG where possible; set explicit width/height.

