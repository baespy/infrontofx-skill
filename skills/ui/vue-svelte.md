# Vue And Svelte NUI

Read nui-bridge.md and design-system.md first. Preserve an established frontend framework unless a migration is requested. React, Vue and Svelte share the same Lua bridge and server authority contract.

## Build Boundary

- Keep source and dependencies in interface-dev. Ship only compiled html assets with a relative Vite asset base and explicit manifest files.
- Keep fonts, icons and runtime dependencies local. Never ship server configuration or credentials through Vite environment variables; exposed frontend variables are public.
- Use the project's existing package lock and framework version. Avoid adding state libraries for one screen.

## Vue

- Register one named message listener in onMounted; remove that exact function in onUnmounted. Cancel pending visual work and release references on cleanup.
- Model screen visibility and data in reactive state. Use computed values for derived presentation rather than duplicating authoritative state.
- Use interpolation and text bindings for player content. Do not use v-html with untrusted values.
- Keep callback submission state explicit. Prevent duplicate user submissions while an operation is pending, but enforce idempotency and mutation locks on the server too.

## Svelte

- Register the message listener in onMount and return the cleanup function. Remove listeners, timers and observers on unmount.
- Follow the project's established Svelte version. Do not mix incompatible reactivity styles during a narrow change.
- Use escaped text interpolation for player content, never raw HTML rendering.
- Update only the state required by the incoming action; do not rebuild complete inventories for one changed item.

## Shared Bridge And Validation

- Resolve callback URLs with GetParentResourceName and HTTPS. Match each action to an explicit payload shape.
- Messages use { action, data }. Send uiReady after the page listener is installed, then accept the authoritative snapshot from Lua.
- Lua calls cb exactly once on success and rejection. Escape/close must release focus through Lua and clear transient UI state.
- Do not assume a successful fetch means a game mutation succeeded; inspect the response contract.
- Test open/close, duplicate input, stale responses, Lua resource restart, UI reload, focus release and scaling in FiveM CEF.

Sources checked 2026-10-22:

- https://docs.fivem.net/docs/scripting-manual/nui-development/nui-callbacks/
- https://vuejs.org/api/composition-api-lifecycle.html
- https://svelte.dev/docs/svelte/lifecycle-hooks
