class ShopMenu {
    constructor() {
        this.root = document.getElementById("shop");
        this.title = document.getElementById("shop-title");
        this.money = document.getElementById("shop-money");
        this.list = document.getElementById("item-list");
        this.amountInput = document.getElementById("amount-input");
        this.buyButton = document.getElementById("buy-button");
        this.items = [];
        this.selected = null;
        this.maxAmount = 1;
        this.busy = false;

        Nui.on("open", (data) => this.open(data));
        Nui.on("close", () => this.hide());

        document.getElementById("shop-close").addEventListener("click", () => this.close());
        document.getElementById("amount-minus").addEventListener("click", () => this.setAmount(this.amount() - 1));
        document.getElementById("amount-plus").addEventListener("click", () => this.setAmount(this.amount() + 1));
        this.amountInput.addEventListener("change", () => this.setAmount(this.amount()));
        this.buyButton.addEventListener("click", () => this.buy());

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
        this.selected = null;
        this.busy = false;
        this.maxAmount = Math.max(1, Number(data.maxAmount) || 1);
        this.title.textContent = String(data.label || "SHOP");
        this.setMoney(data.money);
        this.setAmount(1);
        this.root.hidden = false;
        this.render();
    }

    render() {
        this.list.replaceChildren(...this.items.map((item) => this.row(item)));
        this.buyButton.disabled = this.selected === null || this.busy;
        if (this.busy) {
            this.buyButton.textContent = "Purchasing...";
        } else {
            this.buyButton.textContent = this.selected === null ? "Select an item" : "Purchase";
        }
    }

    row(item) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "row" + (item.name === this.selected ? " selected" : "");
        button.disabled = this.busy;

        const name = document.createElement("span");
        name.className = "row-name";
        name.textContent = String(item.label || item.name);

        const price = document.createElement("span");
        price.className = "row-price";
        price.textContent = this.formatMoney(item.price);

        button.append(name, price);
        button.addEventListener("click", () => {
            if (this.busy) {
                return;
            }
            this.selected = item.name;
            this.render();
        });
        return button;
    }

    amount() {
        return Math.floor(Number(this.amountInput.value) || 1);
    }

    setAmount(value) {
        this.amountInput.value = String(Math.min(this.maxAmount, Math.max(1, Math.floor(value))));
    }

    setMoney(value) {
        this.money.textContent = this.formatMoney(value);
    }

    formatMoney(value) {
        return "$" + (Number(value) || 0).toLocaleString("en-US");
    }

    async buy() {
        if (this.busy || this.selected === null) {
            return;
        }
        this.busy = true;
        this.render();
        try {
            const result = await Nui.post("buy", { item: this.selected, amount: this.amount() });
            if (result && result.money !== undefined) {
                this.setMoney(result.money);
            }
        } catch {
        } finally {
            this.busy = false;
            this.render();
        }
    }

    hide() {
        this.root.hidden = true;
        this.items = [];
        this.selected = null;
        this.list.replaceChildren();
    }

    async close() {
        if (this.busy || this.root.hidden) {
            return;
        }
        await Nui.post("close").catch(() => null);
        this.hide();
    }
}

new ShopMenu();
