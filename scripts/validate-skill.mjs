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
];
const FORBIDDEN = [
    "skills/common/fc-adapters.md",
    "skills/common/ox-lib.md",
    "templates/resource/config/function",
];
const LINK_PREFIXES = ["skills/", "memory/", "references/", "rules/", "checklists/", "templates/", "scripts/", "agents/"];
const SKIP_MARKDOWN_DIRS = new Set(["node_modules", ".git", "templates", "poster-forge", "weapon-forge", "prop-forge", "map-forge"]);
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

for (const forge of ["poster-forge", "weapon-forge", "prop-forge", "map-forge"]) {
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
