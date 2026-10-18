# infrontofx-skill

An opinionated FiveM Lua and NUI/DUI standard for the `infrontofx` ecosystem. It gives coding agents one consistent resource shape: one controller table per side, centralized `Config`, explicit `FC` integration adapters, server authority, efficient runtime patterns, deterministic cleanup, and a lightweight UI contract.

The skill is English-only and uses progressive disclosure. Agents load [SKILL.md](SKILL.md) first, then only the reference files relevant to the current task.

## Install

Clone the repository into the skill directory used by your agent:

```text
git clone https://github.com/baespy/infrontofx-skill.git
```

For OpenAI Codex, you can also ask:

```text
Use $skill-installer to install from repo baespy/infrontofx-skill path . with name infrontofx-skill
```

For Claude Code:

```text
/plugin marketplace add baespy/infrontofx-skill
/plugin install infrontofx-skill@infrontofx
```

## Core Contract

- Every client/server Lua file uses the ESX export header and dynamic `scriptname`.
- One `Name` / `NameServer` controller owns runtime state and colon methods.
- `Config.General`, `Config.Text`, split datasets, and one-time normalization keep data predictable.
- `FC` is the only framework, pNotify, UI hook, logging, and owner-customization boundary.
- Server endpoints use `scriptname .. ":SV:action"`; client endpoints use `scriptname .. ":CL:action"`.
- External input is validated once at the boundary. Internal values are not wrapped in redundant guards.
- Lua and produced UI code use no comments. Lua uses 4 spaces, double quotes, and multi-line `if` blocks.
- Idle polling, unscoped sync, stale post-yield state, and leaked entities/UI handles are rejected.
- NUI uses `{ action, data }`, an `uiReady` handshake, runtime resource names, and safe text rendering.

## Structure

- `SKILL.md` contains the high-frequency rules and task router.
- `skills/common/` contains focused Lua/runtime/security references.
- `skills/ui/` contains NUI, DUI, React/Vite, vanilla UI, and design rules.
- `references/` contains the ESX and pNotify integration contracts.
- `templates/resource/` is a complete resource example.
- `scripts/lint-resource.mjs` audits a resource.
- `scripts/new-resource.mjs` copies and names the template.
- `scripts/validate-skill.mjs` validates the package.

## Tools

```text
node scripts/new-resource.mjs fishing --destination C:\path\to\resources
node scripts/lint-resource.mjs C:\path\to\resources\fishing
node scripts/validate-skill.mjs
```

The generated controller names are `Fishing` and `FishingServer`. Override with `--controller Name` when needed.

## License

MIT. See [LICENSE](LICENSE).
