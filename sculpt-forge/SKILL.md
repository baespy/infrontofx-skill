---
name: sculpt-forge
description: Smooth designer-toy sculpting in Blender 4.2.3 with SDF (puffy bodies, filleted joins, inflated letters, drips, organics) plus curved map hero pieces, reduced to low-poly with transferred normals and numeric QA. Use for ปั้นเนียน, ทรงพอง, ตัวอักษรพอง, ป้ายพอง, หยดสไลม์, ราวโค้ง, บันไดโค้ง, ซุ้มโค้ง, or props that look boxy or blobby. Not for export or ytyp (use prop-forge, map-forge).
---

# Sculpt Forge

Moulded, not assembled: puffy forms, round edges, fillets between parts, light enough for FiveM. SDF on a fine grid, meshed by Blender's OpenVDB, collapsed to budget, high-poly normals transferred last. Props meet the prop-forge contract; map pieces over ~3 m use `SweepBuilder` and map-forge. Paths are relative to this folder.

## Quick path

```powershell
$blender = '<blender-4.2.3>\blender.exe'
$skill = '<project>\.claude\skills\infrontofx'
$sf = "$skill\sculpt-forge\scripts\blender"
$work = '<project>\work\<set>'
& $blender -b --factory-startup -P "$sf\forge_sculpt.py" -- --spec "$work\source\sculpt.json" --out $work
& $blender -b --factory-startup -P "$sf\validate_sculpt.py" -- --blend $work --json "$work\qa.json"
& $blender -b --factory-startup -P "$sf\render_sculpt.py" -- --blend $work --out "$work\renders" --qa "$work\qa.json"
& $blender -b --factory-startup -P "$skill\prop-forge\scripts\blender\validate_prop.py" -- --blend $work
& $blender -b -P "$skill\prop-forge\scripts\blender\export_prop.py" -- --blend $work --out "$work\stream" --format native --max-res 512 --shared-ytd <set>_tex
```

1. Brief: id `1nfx_<set>_<name>` (`^[a-z0-9_]{3,60}$`), real size in metres, Z up, front -Y, floor z = 0, colour roles (house palette in `references/smooth-craft.md`), `size_class` budget.
2. Plan the shape in numbers before code with `references/smooth-craft.md` and the family recipe: edge radii, puff, tubes, letter layers, a fillet for every joint.
3. Copy `templates/sculpt-spec.example.json` to `<project>/work/<set>/source/sculpt.json` (node `type` = method name, other keys = kwargs), or write a Python builder per `references/pipeline.md`.
4. Build: the `SCULPT_DONE` line must show `"validate": {"fail": 0, "warn": 0}` and tris within budget.
5. QA the output folder (finds `_high/<id>_high.blend` itself) until `SCULPT_QA fail=0`; explain every WARN. Gate v2 counts only decimation faults (folds absent from the high-poly, lumps vs the high-poly, length-weighted dihedral); all recipe demos pass. Details: `references/qa.md`.
6. Render and open every `<id>_clay.png`, `<id>_zebra.png`, `<id>_turntable.png`, `<id>_colour.png`; numbers alone never pass.
7. Loop 4-6 until numbers and eyes both pass.
8. Props: `validate_prop.py` `RESULT fail=0 warn=0`, then `export_prop.py --format native` without `--factory-startup` -> `RESULT ok=<n> fail=0`. Map pieces: `SweepBuilder.finish()`, then map-forge `export_map.py` and `inspect_map.py` until `MAP_INSPECT_PASS fail=0`.
9. Wire in per `prop-forge/references/integration.md`; report Blender, QA and export checks apart from what is untested in game. Skill edited: sync with `scripts/sync-antigravity.ps1`, confirm with `-Check`.

## Choose

| Task | Use |
| --- | --- |
| smooth prop 0.2-3 m (puffy body or sign, letters, cream, drips, lathe cup, lump) | `SculptBuilder` (`scripts/blender/sculpt_forge.py`) via `scripts/blender/forge_sculpt.py` or Python |
| smooth part for prop-forge's `KawaiiBuilder` | `--target library` -> `sculpt_mesh` card |
| curved map piece 3-40 m (plaza rim, arc stairs, rail, arch, planter, light line) | `SweepBuilder` (`scripts/blender/sculpt_sweep.py`), map-forge export |
| flat sharp panel or hard part in a smooth piece (screen, metal rim) | `bevel_box` / `poly_part` (Weighted Normal, no SDF fillet) |
| family ready-made (signs, cabinets, containers, organics, rounds, map kit) | `scripts/blender/recipes/` + its recipe doc |
| sharp low-poly archetypes 2,400-4,800 tris (ATM, sign post, safe, workbench) | prop-forge `forge_prop.py` / `kawaii_studio.py` |
| map layout ymap/ybn/ytyp, GTA props, lights | map-forge |
| budget | `size_class` hero 12,000 / medium 6,000 / small 3,000 tris; `budget` overrides |
| live Blender MCP | exec `sculpt_forge.py` with `__name__ == "__main__"`, call `ns["SculptBuilder"](...)`, `font=` as a full path; 5.x scenes are rebuilt by the 4.2.3 CLI before export |

## Hard rules

- **Custom normals are the last geometry step**: reduce, triangulate, transfer normals. Afterwards only UV, colour, material, move, rotate, uniform scale and join. Never run kawaii `_clean_mesh_bmesh` (sharp marks over 32° bend normals 79.5°), smooth, subsurf, decimate, remesh, Weighted Normal, `set_sharp_from_angle` or non-uniform scale (10.4°). Always triangulate before transfer (Sollumz re-triangulates quads, up to 20.5° drift).
- **Save with 4.2.3**: `export_prop.py` and `export_map.py` in 4.2.3 cannot open 5.x files; work built over MCP on 5.x is rebuilt with the 4.2.3 CLI before export (the engine warns `saved by Blender ...; rebuild with the 4.2.3 CLI`).
- **One CLI process per set**: in `-b` every `SculptBuilder()` calls `read_factory_settings` and clears the scene; never hold objects across builders; use `forge_sculpt.py` or `SpecRunner`.
- **Budget**: props by `size_class`; 1-4 materials (one per finish); power-of-two textures up to 2048 and one shared palette per set; map shell at most 40,000 tris. No normal maps for smoothness; no mesher adaptivity, octree remesh, Laplacian smooth or Decimate symmetry.
- **Copyright**: clips and reference files are other creators' work; use only shape language and numbers. Never copy names, logos, characters, mascots, 1:1 layouts or textures, or write their brand names into files, specs, roles or docs. Every set uses our own brand (`1nfx_`).
- **Coordinate contract**: one mesh named like the file, transforms applied, lowest point z = 0 centred on X/Y (engine does it), colliders `<id>_col_N`. Never rename or move the origin once wired in; turn it with the spawn heading.
- **Honest report**: `SCULPT_QA fail=0` and renders are Blender results; say untested in game until the owner sees it.
- **Python**: builders are classes with methods; no comments, docstrings, lambdas or nested functions; only `main()` under `if __name__ == "__main__"`; only bpy, bmesh, mathutils, numpy, pyopenvdb, stdlib; explicit path arguments so MCP exec works (never only `__file__`).
- **Source**: edit only `.claude/skills/infrontofx/sculpt-forge`, never `.agents/skills/sculpt-forge`; sync with `scripts/sync-antigravity.ps1` (`-Check` checks, `-Force` overwrites).

## Done when

- [ ] `SCULPT_DONE` validate fail 0 warn 0, tris within budget
- [ ] `SCULPT_QA fail=0` on the output folder; every WARN explained (gate v2 targets in `references/qa.md`)
- [ ] Clay, zebra, turntable and colour renders opened: no lumps, folds, banded edges or poking parts
- [ ] Props `RESULT fail=0 warn=0` and export `RESULT ok=<n> fail=0`; map pieces `MAP_INSPECT_PASS fail=0`
- [ ] Normals transferred last; files saved by the 4.2.3 CLI
- [ ] Report splits checked from untested in game; skill edits synced

## References

| Need | Open |
| --- | --- |
| Shape numbers (radii, puff, tubes, letters, drips, fillets, sagitta, tris/m², normals, colour, night, don'ts) | `references/smooth-craft.md` |
| Engine: stages, parameters, nodes, spec schema, Python and MCP, library target, speed, fixes | `references/pipeline.md` |
| QA checks, thresholds, fixes, renders, baselines | `references/qa.md` |
| Map pieces: `SweepBuilder`, paths, profiles, budgets, vertex colour, UV tiling | `references/map-pieces.md` |
| Recipes: signs, cabinets, containers, organics, rounds, map kit | `references/recipes-signs.md`, `references/recipes-cabinets.md`, `references/recipes-containers.md`, `references/recipes-organics.md`, `references/recipes-rounds.md`, `references/recipes-mapkit.md` |
| Metric table, command options and timings, original Thai steps and rules | `references/details.md` |
