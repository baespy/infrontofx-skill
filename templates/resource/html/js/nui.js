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

