# Changelog

## 2.0.0 - 2026-10-18

- Rebuilt the package into the standard skill layout (`SKILL.md` routing, `AGENTS.md`, `CLAUDE.md`, `skills/`, `references/`, `memory/`, `rules/`, `checklists/`, `templates/`, `scripts/`).
- Standardized `FC` adapters on direct `ESX` (`ESX.GetPlayerData` on client, `exports["es_extended"]:RunStaticPlayerMethod` on server) + `pNotify:SendNotification` without requiring `1nfx_utilities`.
- Added FC adapters for `1nfx_textui`, `1nfx_processbar`, `1nfx_serverlogs`, and documented gameplay hooks.
- Added UI skills: NUI bridge, 1nfx design system, vanilla class UI, React/Vite, DUI pool.
- Added performance and networking guides based on `1nfx_growth_garden` streaming, wire encoding, KVP snapshot.
- Added working template resource (shop + NUI), scaffolder, linter, validator, CI workflow, and out-of-the-box support for Antigravity, Claude Code, and OpenAI Codex.

## 1.0.0

- Initial draft.
