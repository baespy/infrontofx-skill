#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const asJson = process.argv.includes("--json");

function front(path) {
    if (!existsSync(path)) return null;
    const text = readFileSync(path, "utf8").replace(/\r\n/g, "\n");
    const head = /^---\n([\s\S]*?)\n---\n/.exec(text);
    if (!head) return null;
    const name = (/^name:\s*(.+)$/m.exec(head[1]) || [])[1];
    const description = (/^description:\s*(.+)$/m.exec(head[1]) || [])[1];
    return name ? { name: name.trim(), description: (description || "").trim() } : null;
}

function triggers(description) {
    const m = /Use (?:for|as|when)\s+([^.]+)\./.exec(description);
    return m ? m[1].trim() : "";
}

const plugin = JSON.parse(readFileSync(join(ROOT, ".claude-plugin", "plugin.json"), "utf8"));
const pack = [];
for (const rel of plugin.skills || []) {
    const info = front(join(ROOT, rel, "SKILL.md"));
    if (info) pack.push({ ...info, folder: rel === "./" ? "." : rel.replace(/^\.\//, ""), source: "pack" });
}

const local = [];
const skillsDir = resolve(ROOT, "..");
if (existsSync(skillsDir) && /[\\/]skills$/i.test(skillsDir)) {
    for (const e of readdirSync(skillsDir, { withFileTypes: true })) {
        if (!e.isDirectory() || resolve(skillsDir, e.name) === resolve(ROOT)) continue;
        const info = front(join(skillsDir, e.name, "SKILL.md"));
        if (info) local.push({ ...info, folder: e.name, source: "project" });
    }
}

const routes = existsSync(join(ROOT, "hooks", "skill-routes.tsv"))
    ? readFileSync(join(ROOT, "hooks", "skill-routes.tsv"), "utf8").replace(/\r\n/g, "\n").split("\n").filter(Boolean).map((l) => l.split("\t"))
    : [];
const thaiFor = (name) => routes.filter((r) => r[0] === name).map((r) => r[2]).filter(Boolean).join("|").split("|").slice(0, 8).join(", ");

const all = [...pack, ...local].map((s) => ({
    name: s.name,
    source: s.source,
    folder: s.folder,
    command: s.source === "project" ? `/${s.name}` : `/${plugin.name}:${s.name}`,
    thai: thaiFor(s.name),
    use: triggers(s.description),
    description: s.description,
}));

if (asJson) {
    console.log(JSON.stringify({ pack: plugin.name, version: plugin.version, skills: all }, null, 2));
} else {
    console.log(`${plugin.name} v${plugin.version}: ${pack.length} pack skills, ${local.length} project skills`);
    for (const s of all) {
        console.log(`\n${s.name}  [${s.source}]  ${s.command}`);
        console.log(`  ${s.description}`);
        if (s.thai) console.log(`  auto-route (Thai): ${s.thai}`);
    }
}
