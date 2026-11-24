---
name: poster-forge
description: Builds square Support, Welfare and giveaway posters for a FiveM RP server in two approved styles (A big dark face with film grain, B gun pointed at the camera) from character art, item icons and a logo; writes AI character prompts. Use for โปสเตอร์, support, สวัสดิการ, แจกของ, Family/Gang/Lady/Streamer posters or character images sent for a poster. Not for UI, banners, gacha or mascots.
---

# Poster Forge

Composes a poster PNG (green-screen character, grading, rim light, effects, titles, item cards, footer) from the owner's or AI art with an HTML/Canvas engine in headless Chrome on the GPU. PowerShell and Chrome only (no Python, Node, ImageMagick). Paths are relative to this folder.

## Quick path

1. Brief: topic, main image, prize list with counts (if any), server name and contact, size. Ask only what is missing; facts (prices, counts, dates, links) come only from the owner.
2. Job folder `<workdir>\posters\<job>\`; copy every image into `work\src\`; never edit or delete originals.
3. Open every image (pose, facing, colours) and the approved targets `references/targets/approved-*.jpg` before starting.
4. Art when needed: jobs from `templates\gemini-jobs.example.json`, `scripts\agy-gen.ps1 -Batch jobs.json` one stage at a time, each output the next stage's single ref: (ก) hair or headwear fix + green background, (ข) medium close-up head to waist, (ค) outfit if asked, (ง) X-slab background per colour (parallel OK). Hair colour in capitals; open every image before the next stage. The character must be a FiveM face (source order in `references/support-styles.md`).
5. `scripts\hero-prep.ps1 -In <green.png> -Out work\hero_char.png` (cut green, crop, upscale, sharpen). Closed gaps inside the figure (hair to neck, arm loops): `scripts\fill-holes.ps1 -In hero.png -Out hero_f.png -Color <hair colour>` on the unfilled hero.
6. Spec, one tier per poster: copy the template from Choose to `poster.json`; set `theme`/`accent2`, `background.image`, `heroes[0].src`, `title.lines`, `items.list` (fields in `references/spec.md`). No prize list yet: remove `items` and `panel`, ask the owner, never guess counts.
7. `scripts\render.ps1 -Spec poster.json`. Pass = an `OK <png> (WxH)` line and a `GPU` line; `Render failed` = fix and rerun. Handle every `POSTER-WARN`.
8. Open the full PNG, tick Done when, fix the spec and render again; never deliver an unseen first render.
9. Deliver the PNG path plus any warning left (e.g. low-resolution source).

## Choose

| Situation | Use |
| --- | --- |
| style not given | A for most tiers, B for Gang; colours from the logo or outfit |
| Gang, 16-28 items, red | `templates\support-dense.json` (`cols 7`, `aspect .58`) |
| Family, 16-28 items, violet | `templates\support-family.json` |
| Newbie or up to 15 items, blue | `templates\support-face.json` |
| style B | `templates\support-gun.json` (layout `gun-support`) |
| Streamer without an item list (theme `rose`) | `templates\support-streamer-noitems.json`; wide 2:1 `templates\support-streamer-wide-noitems.json` |
| over 28 items | ask before splitting into sheets |
| edit original art (hair, headwear, camera angle, green bg) or make X-slab backgrounds, no API key | `scripts\agy-gen.ps1` |
| whole-body pose or outfit change | `scripts\codex-gen.ps1` with a close face ref |
| paid Gemini API generation | `scripts\generate.ps1` (`GEMINI_API_KEY`) |
| white background plus white shirt | `scripts\cutout-white.ps1` polygon cut, or agy green background + `scripts\cutout.ps1 -Chroma` |
| plain background cutout | `scripts\cutout.ps1`, open `.check.jpg` (magenta = holes, lower `-Tolerance`); busy background: ask for a transparent PNG or use `fade` |
| black hair on a dark background | `rim` .3-.4, `grade` .2, `background.brightness` ~.72 |
| owner wants only a prompt (Semi-Realistic 3D AAA, pose from a reference) | `references/character-prompts.md`; reply with a filled Thai prompt block; no API, no render |

Prompt-only rules: image 1 is the character, image 2 the pose only; a series gets one prompt per poster with the identity and style blocks unchanged; art meant for a poster uses the English green-screen version; when the owner sends the results back, continue from Quick path step 5.

## Hard rules

- **Scope**: only the two square Support styles in `references/support-styles.md` (plus their wide 2:1 variant); for gacha, ranking, mascot or banner say it is out of scope and ask for A or B.
- **AI makes pictures only**: titles, numbers, cards and logos come from the spec. In-game item icons use the real files; generate only missing ones and tell the owner.
- **Cost**: Claude cannot draw; every Gemini API image is paid. Give the estimate first; try poses with `-Model fast` (~$0.05 per 2K image), finish with `-Model pro` (default, ~$0.134); at most `-Count 2` per round; after 3 failed rounds on one image stop and show the owner.
- **API key**: the owner creates it at `https://aistudio.google.com/apikey` with billing (free tier returns 429 "limit: 0") and runs `setx GEMINI_API_KEY "<key>"` himself. Never ask for it in chat, write it to a file or print it.
- **Errors and refusals**: report the script's exact message; change the prompt only for content issues, never resend unchanged. If Codex or agy refuses, no workaround: cut from the original (`scripts\isolate.ps1`, `scripts\erase-white.ps1`). Never `--dangerously-skip-permissions`. Adult-looking characters only.
- **GPU only**: without a hardware GPU `render.ps1` stops; never software rendering or `--disable-gpu`; report the error.
- **Originals**: reference posters belong to other servers, style direction only; never reuse their images, logos, event names or characters. Only the job owner's logo goes on the poster. At most one style ref as `-Ref` for light and mood, and check nothing was copied.
- **Other people's images**: check every source for artist watermarks first; only for that job, never another client's. Real people must not appear to endorse anything. Copyrighted characters or brands and removed watermarks or logos are always reported, with advice to ask permission or credit.
- **Owner files**: never delete originals as "unused" (one was lost that way); work on copies in `work\src\`; on a delete request list each file name to confirm or move it to `_old`; clean only temp files this skill made.
- **Real data**: never invent prizes, counts, prices, dates or links; label placeholder text as such.
- **Honest report**: if effects fall short of hand retouching or the source breaks up, say so and name the source needed.
- **Series** (Family, Gang, Lady): keep `theme`, `layout`, `seed` and logo; change image, title and list; files `<set>-<name>.png`; one spec per aspect ratio, check every size.

## Done when

- [ ] No `POSTER-ERROR`; every warning handled or told to the owner
- [ ] Title readable at phone-feed size
- [ ] Face not covered by text, cards, logo or effects; character reaches the bottom edge; no black band at the bottom
- [ ] Thai vowels and tone marks not clipped, no overlapping lines
- [ ] Names, counts, dates and links match the owner's text exactly; Thai and AD years not mixed up
- [ ] Cutout edges free of old background and holes; cards transparent; footer clear of the cards
- [ ] Lightning and sparkles do not cross text
- [ ] Generated art has no extra fingers, twisted hands, gibberish text, watermarks or stray logos

## References

| Need | Open |
| --- | --- |
| Styles A/B, approved look, card grid, character sources, engine pitfalls; every spec field | `references/support-styles.md`; `references/spec.md` |
| Approved recipe with all values (decorated streamer style, wide layout, outfits, props layout), original Thai steps and rules | `references/recipe.md` |
| Every script and flag; Gemini API, Codex and Antigravity details | `references/tools.md` |
| Image prompt formulas and reference choice | `references/image-prompts.md` |
| Character prompts (Thai blocks, poses, Codex, Gemini edits, backgrounds) | `references/character-prompts.md` |
| Approved targets | `references/targets/` |
