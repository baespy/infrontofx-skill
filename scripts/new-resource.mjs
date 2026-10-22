#!/usr/bin/env node
import { cpSync, existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TEMPLATE = join(ROOT, "templates", "resource");
const args = process.argv.slice(2);
const name = args[0];

function option(key) {
    const index = args.indexOf(key);
    return index === -1 ? undefined : args[index + 1];
}

function pascalCase(value) {
    return value
        .replace(/^(?:infrontofx|1nfx)[_-]/i, "")
        .split(/[_\-\s]+/)
        .filter(Boolean)
        .map((part) => part[0].toUpperCase() + part.slice(1))
        .join("");
}

function files(path, output = []) {
    for (const entry of readdirSync(path)) {
        const full = join(path, entry);
        if (statSync(full).isDirectory()) {
            files(full, output);
        } else {
            output.push(full);
        }
    }
    return output;
}

if (!name) {
    console.error("usage: node scripts/new-resource.mjs <name> [--destination path] [--controller Name]");
    process.exit(2);
}

if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(name)) {
    throw new Error("Resource name must contain only lowercase letters, digits, underscores or hyphens, with no paths.");
}

const destination = resolve(option("--destination") || process.cwd());
const controller = option("--controller") || pascalCase(name);
const target = join(destination, basename(name));

if (!/^[A-Z][A-Za-z0-9]*$/.test(controller)) {
    throw new Error(`Controller name must be PascalCase: ${controller}`);
}

if (existsSync(target)) {
    throw new Error(`Target already exists: ${target}`);
}

cpSync(TEMPLATE, target, { recursive: true, errorOnExist: true });

const textExtensions = new Set([".lua", ".html", ".js", ".css", ".md", ".sql"]);
for (const file of files(target)) {
    if (!textExtensions.has(extname(file))) {
        continue;
    }
    const source = readFileSync(file, "utf8");
    const output = source
        .replaceAll("TemplateServer", `${controller}Server`)
        .replace(/\bTemplate\b/g, controller)
        .replaceAll("infrontofx_template", name);
    writeFileSync(file, output, "utf8");
}

console.log(`Created ${target}`);
console.log(`Client controller: ${controller}`);
console.log(`Server controller: ${controller}Server`);
