# React / Vite UI

Use for large UIs (phone, inventory, MDT, admin panel) where component state pays off. Small menus stay vanilla (`skills/ui/vanilla-ui.md`).

## Layout

```text
web/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── nui/fetchNui.ts
│   ├── nui/useNuiEvent.ts
│   ├── nui/debug.ts
│   └── components/
└── dist/            build output, the only folder shipped
```

Manifest: `ui_page "web/dist/index.html"`, `files { "web/dist/**" }`. Do not ship `node_modules` or `src`.

## vite.config.ts

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    base: "./",
    build: {
        outDir: "dist",
        emptyOutDir: true,
        assetsInlineLimit: 0,
        target: "chrome103",
    },
});
```

`base: "./"` is mandatory; absolute paths break under `https://cfx-nui-<resource>/`.

## fetchNui

```ts
const resourceName = typeof (window as any).GetParentResourceName === "function"
    ? (window as any).GetParentResourceName()
    : "dev";

export async function fetchNui<R = unknown, T = unknown>(eventName: string, data?: T): Promise<R> {
    const response = await fetch(`https://${resourceName}/${eventName}`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=UTF-8" },
        body: JSON.stringify(data ?? {}),
    });
    if (!response.ok) {
        throw new Error(`NUI ${eventName} failed: ${response.status}`);
    }
    return response.json() as Promise<R>;
}
```

Resolve the resource name at runtime instead of hardcoding it (improves on the hardcoded default in HTPH's utility).

## useNuiEvent

```ts
import { useEffect, useRef } from "react";

export function useNuiEvent<T = unknown>(action: string, handler: (data: T) => void) {
    const saved = useRef(handler);

    useEffect(() => {
        saved.current = handler;
    }, [handler]);

    useEffect(() => {
        const listener = (event: MessageEvent) => {
            if (event.data?.action === action) {
                saved.current(event.data.data as T);
            }
        };
        window.addEventListener("message", listener);
        return () => window.removeEventListener("message", listener);
    }, [action]);
}
```

Matches the Lua contract `SendNUIMessage({ action = "...", data = {...} })`.

## Ready + Visibility

```tsx
export default function App() {
    const [visible, setVisible] = useState(false);
    const [shop, setShop] = useState<Shop | null>(null);

    useEffect(() => {
        fetchNui("uiReady").catch(() => null);
    }, []);

    useNuiEvent<Shop>("open", (data) => {
        setShop(data);
        setVisible(true);
    });

    useNuiEvent("close", () => setVisible(false));

    useEffect(() => {
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape" && visible) {
                fetchNui("close").finally(() => setVisible(false));
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [visible]);

    if (!visible || !shop) {
        return null;
    }
    return <ShopPanel shop={shop} />;
}
```

## Dev Mock

```ts
export function debugData<T>(events: { action: string; data: T }[], delay = 300) {
    if (import.meta.env.DEV) {
        events.forEach((event) => setTimeout(() => window.dispatchEvent(new MessageEvent("message", { data: event })), delay));
    }
}
```

## Rules

- State management: React state/context; Zustand for large apps. No Redux boilerplate.
- Styling: Tailwind or CSS modules, using the tokens from `skills/ui/design-system.md` (`--px` scaling).
- Never `dangerouslySetInnerHTML` with game data.
- Memoize big lists (`React.memo`, keyed rows); virtualize > 300 rows.
- Keep the bundle small: no moment.js, no full icon packs (import single icons).
- Build before commit: `npm run build`; commit `web/dist` if the server pulls resources from git.

