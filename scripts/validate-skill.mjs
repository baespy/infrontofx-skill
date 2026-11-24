#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REQUIRED = [
    "SKILL.md",
    "NUI_DUI.md",
    "TOOLING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "LICENSE",
    "agents/openai.yaml",
    ".claude-plugin/marketplace.json",
    ".claude-plugin/plugin.json",
    ".github/workflows/validate.yml",
    "skills/common/style.md",
    "skills/common/architecture.md",
    "skills/common/config.md",
    "skills/common/core-api.md",
    "skills/common/events.md",
    "skills/common/runtime.md",
    "skills/common/security.md",
    "skills/common/performance.md",
    "skills/common/networking.md",
    "skills/common/database.md",
    "skills/common/natives.md",
    "skills/common/1nfx-lib.md",
    "skills/common/debugging.md",
    "skills/ui/nui-bridge.md",
    "skills/ui/design-system.md",
    "skills/ui/vanilla-ui.md",
    "skills/ui/react-vite.md",
    "skills/ui/vue-svelte.md",
    "skills/ui/dui.md",
    "references/esx-api.md",
    "references/pnotify-api.md",
    "references/infrontofx-fivem.md",
    "rules/contracts.md",
    "memory/README.md",
    "memory/native-gotchas.md",
    "memory/security-exploits.md",
    "memory/patterns.md",
    "memory/performance-research.md",
    "checklists/new-resource.md",
    "checklists/review.md",
    "templates/resource/fxmanifest.lua",
    "templates/resource/config/config.lua",
    "templates/resource/core/cl_main.lua",
    "templates/resource/core/sv_main.lua",
    "templates/resource/html/index.html",
    "scripts/lint-resource.mjs",
    "scripts/new-resource.mjs",
    "poster-forge/SKILL.md",
    "weapon-forge/SKILL.md",
    "prop-forge/SKILL.md",
    "map-forge/SKILL.md",
    "map-forge/references/polyhaven-cc0.md",
    "map-forge/scripts/blender/fetch_polyhaven.py",
    "sculpt-forge/SKILL.md",
    "sculpt-forge/scripts/blender/sculpt_forge.py",
    "sculpt-forge/scripts/blender/validate_sculpt.py",
    "sculpt-forge/scripts/blender/sculpt_sweep.py",
    "dev-flow/SKILL.md",
    "terse/SKILL.md",
    "hooks/hooks.json",
    "hooks/skill-router.sh",
    "hooks/skill-routes.tsv",
    "scripts/test-pack.mjs",
    "scripts/install-agents.ps1",
    "tests/hooks/cases.tsv",
    "tests/lint/cases.json",
    "GEMINI.md",
    "gemini-extension.json",
    ".cursor/rules/infrontofx.mdc",
    ".github/copilot-instructions.md",
];
const FORBIDDEN = [
    "skills/common/fc-adapters.md",
    "skills/common/ox-lib.md",
    "templates/resource/config/function",
];
const LINK_PREFIXES = ["skills/", "memory/", "references/", "rules/", "checklists/", "templates/", "scripts/", "agents/"];
const SUB_SKILLS = ["poster-forge", "weapon-forge", "prop-forge", "map-forge", "sculpt-forge", "dev-flow", "terse"];
const SKIP_MARKDOWN_DIRS = new Set(["node_modules", ".git", "templates", ...SUB_SKILLS]);
const failures = [];

const read = (path) => readFileSync(join(ROOT, path), "utf8");

function markdownFiles(dir, list = []) {
    for (const entry of readdirSync(dir)) {
        if (SKIP_MARKDOWN_DIRS.has(entry)) {
            continue;
        }
        const full = join(dir, entry);
        if (statSync(full).isDirectory()) {
            markdownFiles(full, list);
        } else if (entry.endsWith(".md")) {
            list.push(full);
        }
    }
    return list;
}

for (const path of REQUIRED) {
    if (!existsSync(join(ROOT, path))) {
        failures.push(`missing required path: ${path}`);
    }
}
for (const path of FORBIDDEN) {
    if (existsSync(join(ROOT, path))) {
        failures.push(`removed path must not exist: ${path}`);
    }
}

const skill = read("SKILL.md").replace(/\r\n/g, "\n");
const front = /^---\n([\s\S]*?)\n---\n/.exec(skill);
if (!front) {
    failures.push("SKILL.md missing YAML frontmatter");
} else {
    if (!/^name:\s*infrontofx\s*$/m.test(front[1])) {
        failures.push("SKILL.md frontmatter must contain name: infrontofx");
    }
    if (!/^description:\s*\S/m.test(front[1])) {
        failures.push("SKILL.md frontmatter must contain description");
    }
}

for (const forge of SUB_SKILLS) {
    if (!existsSync(join(ROOT, forge, "SKILL.md"))) {
        continue;
    }
    const text = read(`${forge}/SKILL.md`).replace(/\r\n/g, "\n");
    const header = /^---\n([\s\S]*?)\n---\n/.exec(text);
    if (!header || !new RegExp(`^name:\\s*${forge}\\s*$`, "m").test(header[1])) {
        failures.push(`${forge}/SKILL.md frontmatter must contain name: ${forge}`);
    }
    if (!skill.includes(`${forge}/SKILL.md`)) {
        failures.push(`SKILL.md must route to ${forge}/SKILL.md`);
    }
}

for (const path of ["SKILL.md", ...SUB_SKILLS.map((sub) => `${sub}/SKILL.md`)]) {
    if (!existsSync(join(ROOT, path))) {
        continue;
    }
    const header = /^---\n([\s\S]*?)\n---\n/.exec(read(path).replace(/\r\n/g, "\n"));
    if (!header) {
        failures.push(`${path} missing YAML frontmatter`);
        continue;
    }
    for (const line of header[1].split("\n")) {
        const field = /^([a-z_-]+):\s?(.*)$/.exec(line);
        if (!field || /^["'>|]/.test(field[2])) {
            continue;
        }
        if (/\s#/.test(field[2]) || /:\s/.test(field[2])) {
            failures.push(`${path} frontmatter ${field[1]} has an unquoted " #" or ": " that YAML cuts or rejects`);
        }
    }
}

const DESCRIPTION_LIMIT = 450;
const ROOT_LIMIT = 10 * 1024;
const SUB_LIMIT = 8 * 1024;
for (const path of ["SKILL.md", ...SUB_SKILLS.map((sub) => `${sub}/SKILL.md`)]) {
    if (!existsSync(join(ROOT, path))) {
        continue;
    }
    const raw = readFileSync(join(ROOT, path));
    const limit = path === "SKILL.md" ? ROOT_LIMIT : SUB_LIMIT;
    if (raw.length > limit) {
        failures.push(`${path} is ${raw.length} bytes; the budget is ${limit}, move details into references/`);
    }
    const text = raw.toString("utf8").replace(/\r\n/g, "\n");
    const header = /^---\n([\s\S]*?)\n---\n/.exec(text);
    const description = header ? /^description:\s?(.*)$/m.exec(header[1]) : null;
    const length = description ? [...description[1].trim()].length : 0;
    if (length > DESCRIPTION_LIMIT) {
        failures.push(`${path} description is ${length} characters; the budget is ${DESCRIPTION_LIMIT}`);
    }
    for (const section of ["Quick path", "Done when"]) {
        if (!new RegExp(`^## ${section}\\s*$`, "m").test(text)) {
            failures.push(`${path} needs a "## ${section}" section`);
        }
    }
}

const firstSection = /^## (.+)$/m.exec(skill);
if (!firstSection || firstSection[1].trim() !== "Auto-route") {
    failures.push("SKILL.md must open with the \"## Auto-route\" table");
} else {
    const route = skill.slice(firstSection.index).split(/^## /m)[1];
    for (const sub of SUB_SKILLS) {
        if (!route.includes(sub)) {
            failures.push(`SKILL.md Auto-route must name ${sub}`);
        }
    }
}

const headingCache = new Map();
function headings(path) {
    if (!headingCache.has(path)) {
        const set = new Set(
            readFileSync(path, "utf8")
                .split(/\r?\n/)
                .filter((line) => line.startsWith("#"))
                .map((line) => line.replace(/^#+/, "").trim()),
        );
        headingCache.set(path, set);
    }
    return headingCache.get(path);
}

for (const file of markdownFiles(ROOT)) {
    const rel = relative(ROOT, file).split("\\").join("/");
    const text = readFileSync(file, "utf8");
    for (const match of text.matchAll(/`([^`\s]+)`/g)) {
        const value = match[1].replace(/\\/g, "/");
        if (!LINK_PREFIXES.some((prefix) => value.startsWith(prefix))) {
            continue;
        }
        const clean = value.replace(/[),.;:]+$/, "");
        if (clean.includes("<") || clean.includes("*")) {
            continue;
        }
        if (!existsSync(join(ROOT, clean))) {
            failures.push(`${rel} references missing path: ${clean}`);
        }
    }
    for (const match of text.matchAll(/`((?:skills|memory|references|rules|checklists)\/[^`]+\.md)` -> ([^\n|]+)/g)) {
        const target = join(ROOT, match[1]);
        if (!existsSync(target)) {
            continue;
        }
        const words = match[2].trim().split(" ");
        const known = headings(target);
        let ok = false;
        for (let end = words.length; end > 0; end--) {
            if (known.has(words.slice(0, end).join(" ").replace(/[,.;:)]+$/, ""))) {
                ok = true;
                break;
            }
        }
        if (!ok) {
            failures.push(`${rel} references missing section: ${match[1]} -> ${words.slice(0, 6).join(" ")}`);
        }
    }
    if (/\bFC\.\w+/.test(text.replace(/```[\s\S]*?```/g, "")) && rel !== "skills/common/core-api.md" && rel !== "SKILL.md") {
        failures.push(`${rel} documents FC.* calls; the FC table is removed`);
    }
}

const SUB_LINK_PREFIXES = ["references/", "scripts/", "templates/", "assets/", "engine/"];
for (const sub of SUB_SKILLS) {
    const subRoot = join(ROOT, sub);
    if (!existsSync(subRoot)) {
        continue;
    }
    for (const file of markdownFiles(subRoot)) {
        const rel = relative(ROOT, file).split("\\").join("/");
        const text = readFileSync(file, "utf8").replace(/```[\s\S]*?```/g, "");
        for (const match of text.matchAll(/`([^`\s]+)`/g)) {
            const value = match[1].replace(/\\/g, "/");
            if (!SUB_LINK_PREFIXES.some((prefix) => value.startsWith(prefix))) {
                continue;
            }
            const clean = value.replace(/[),.;:]+$/, "");
            if (clean.includes("<") || clean.includes("*") || clean.includes("{") || clean.endsWith("/")) {
                continue;
            }
            if (!existsSync(join(subRoot, clean)) && !existsSync(join(ROOT, clean))) {
                failures.push(`${rel} references missing path: ${clean}`);
            }
        }
    }
}

const memoryReadme = read("memory/README.md");
if (!memoryReadme.includes("Date:") || !memoryReadme.includes("Game build:")) {
    failures.push("memory/README.md must include Date: and Game build: template fields");
}

try {
    const market = JSON.parse(read(".claude-plugin/marketplace.json"));
    if (!market.name || !market.owner?.name || !(market.plugins || []).some((p) => p.name === "infrontofx-skill")) {
        failures.push(".claude-plugin/marketplace.json must define name, owner.name and the infrontofx-skill plugin");
    }
} catch (error) {
    failures.push(`.claude-plugin/marketplace.json invalid JSON: ${error.message}`);
}

try {
    JSON.parse(read(".claude-plugin/plugin.json"));
} catch (error) {
    failures.push(`.claude-plugin/plugin.json invalid JSON: ${error.message}`);
}

const openai = read("agents/openai.yaml");
if (!openai.includes("display_name:") || !openai.includes("$infrontofx")) {
    failures.push("agents/openai.yaml needs display_name and a default_prompt mentioning $infrontofx");
}

if (existsSync(join(ROOT, "hooks/skill-routes.tsv"))) {
    const agents = existsSync(join(ROOT, "AGENTS.md")) ? read("AGENTS.md") : "";
    const routeLines = read("hooks/skill-routes.tsv").replace(/\r\n/g, "\n").split("\n").filter((line) => line.trim());
    for (const [index, line] of routeLines.entries()) {
        const cells = line.split("\t");
        if (cells.length !== 4 || !cells[0] || !cells[1]) {
            failures.push(`hooks/skill-routes.tsv line ${index + 1} must have 4 tab-separated fields: skill, why, thai, english`);
            continue;
        }
        if (cells[0] !== "infrontofx" && !SUB_SKILLS.includes(cells[0])) {
            failures.push(`hooks/skill-routes.tsv line ${index + 1} routes to unknown skill ${cells[0]}`);
        }
        if (cells[0] !== "infrontofx" && !agents.includes(`\`${cells[0]}\``)) {
            failures.push(`AGENTS.md auto-route table must mention ${cells[0]} like hooks/skill-routes.tsv`);
        }
        for (const pattern of [cells[2], cells[3]]) {
            try {
                if (pattern) {
                    new RegExp(pattern);
                }
            } catch (error) {
                failures.push(`hooks/skill-routes.tsv line ${index + 1} has an invalid pattern: ${error.message}`);
            }
        }
    }
    if (/\r/.test(read("hooks/skill-router.sh")) || /\r/.test(read("hooks/skill-routes.tsv"))) {
        failures.push("hooks/skill-router.sh and hooks/skill-routes.tsv must use LF line endings (bash breaks on CRLF)");
    }
}

try {
    const hooks = JSON.parse(read("hooks/hooks.json"));
    const command = hooks.hooks?.UserPromptSubmit?.[0]?.hooks?.[0]?.command || "";
    if (!command.includes("${CLAUDE_PLUGIN_ROOT}/hooks/skill-router.sh")) {
        failures.push("hooks/hooks.json must run ${CLAUDE_PLUGIN_ROOT}/hooks/skill-router.sh on UserPromptSubmit");
    }
} catch (error) {
    failures.push(`hooks/hooks.json invalid: ${error.message}`);
}

try {
    const gemini = JSON.parse(read("gemini-extension.json"));
    const plugin = JSON.parse(read(".claude-plugin/plugin.json"));
    if (!gemini.contextFileName || !existsSync(join(ROOT, gemini.contextFileName))) {
        failures.push("gemini-extension.json contextFileName must point at an existing file");
    }
    if (gemini.version !== plugin.version) {
        failures.push(`gemini-extension.json version ${gemini.version} must match .claude-plugin/plugin.json version ${plugin.version}`);
    }
} catch (error) {
    failures.push(`gemini-extension.json invalid: ${error.message}`);
}

const lint = spawnSync(process.execPath, [join(ROOT, "scripts/lint-resource.mjs"), join(ROOT, "templates/resource")], { encoding: "utf8" });
if (lint.status !== 0) {
    failures.push(`templates/resource must lint clean:\n${lint.stdout}`);
}

if (failures.length > 0) {
    console.log("infrontofx validation failed:");
    for (const failure of failures) {
        console.log(`- ${failure}`);
    }
    process.exit(1);
}
console.log("infrontofx validation passed.");
