# Memory

Confirmed engine quirks, exploit classes, and reusable patterns discovered while building resources.

## Files

- `memory/native-gotchas.md` - native return types, subtype quirks, crash triggers.
- `memory/security-exploits.md` - exploit classes and fixes.
- `memory/patterns.md` - reusable implementation patterns.

## Adding An Entry

Every entry needs `Date:` and `Game build:` so stale workarounds can be retired when FXServer updates:

```markdown
### Short title

- Date: 2026-10-18
- Game build: 3258
- Symptom: what went wrong
- Cause: why
- Fix: exact code or rule
```
