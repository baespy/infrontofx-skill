# Vanilla UI

Default for small and medium menus: plain HTML + one CSS file + ES class per app. No build step, zero framework cost, instant load.

## Files

```text
html/
├── index.html
├── css/style.css
├── js/nui.js       bridge (post + message router)
├── js/app.js       one class per app
└── fonts/
```

`index.html` loads scripts with `defer`, in order `nui.js` then `app.js`.

## Bridge

```js
const Nui = {
    resource: typeof GetParentResourceName === "function" ? GetParentResourceName() : "dev",
    handlers: {},
    async post(name, data = {}) {
        const response = await fetch(`https://${this.resource}/${name}`, {
            method: "POST",
            headers: { "Content-Type": "application/json; charset=UTF-8" },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            throw new Error(`NUI ${name} failed`);
        }
        return response.json();
    },
    on(action, handler) {
        this.handlers[action] = handler;
    },
};

window.addEventListener("message", ({ data }) => {
    const handler = data && Nui.handlers[data.action];
    if (handler) {
        handler(data.data);
    }
});
```

One `message` listener for the whole page, routing by `action`.

## App Class

```js
class ShopMenu {
    constructor() {
        this.root = document.getElementById("shop");
        this.list = document.getElementById("item-list");
        this.items = [];
        this.busy = false;
        Nui.on("open", (data) => this.open(data));
        Nui.on("close", () => this.hide());
        document.getElementById("close").addEventListener("click", () => this.close());
        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !this.root.hidden && !this.busy) {
                event.preventDefault();
                this.close();
            }
        });
        this.ready();
    }

    async ready() {
        try {
            await Nui.post("uiReady");
        } catch {
            setTimeout(() => this.ready(), 1000);
        }
    }

    open(data) {
        if (!data || !Array.isArray(data.items)) {
            return;
        }
        this.items = data.items;
        this.root.hidden = false;
        this.render();
    }

    render() {
        this.list.replaceChildren(...this.items.map((item) => this.row(item)));
    }

    row(item) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "row";
        const name = document.createElement("strong");
        name.textContent = item.label;
        button.append(name);
        button.addEventListener("click", () => this.buy(item));
        return button;
    }

    hide() {
        this.root.hidden = true;
        this.items = [];
    }

    async close() {
        await Nui.post("close").catch(() => null);
        this.hide();
    }
}

new ShopMenu();
```

## Rules

- One class per app; state as fields; methods `open / render / hide / close` plus actions.
- Build DOM with `createElement` + `textContent`. Template strings only for static markup without data.
- `busy` flag around every server round trip; disable buttons while busy.
- `render()` rebuilds a list with `replaceChildren` - cheap for < 200 rows. For bigger lists, update rows in place by id.
- Never trust numbers from Lua blindly in math: `Number(x) || 0`.
- Format dates with `toLocaleString("th-TH", {...})`, guard invalid dates.
- Keep files unminified in the repo; minify only at release if needed.

## Dev Without FiveM

Open `html/index.html` in a browser; `Nui.resource` falls back to `"dev"` and `post` rejects. Dispatch fake messages from devtools:

```js
window.postMessage({ action: "open", data: { items: [{ name: "bread", label: "Bread", price: 50 }] } });
```

