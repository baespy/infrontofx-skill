#!/usr/bin/env node
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, basename, extname, sep } from "node:path";

const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "vendor", "stream", "fonts"]);
const LUA_THIRD_PARTY_EVENTS = /^(pNotify|esx|esx_|mythic_progbar|ox_lib|ox_inventory|txAdmin|chat|baseevents|playerSpawned|onResource|onClientResource|gameEventTriggered|populationPedCreating|entityCreated|entityRemoved|explosionEvent|weaponDamageEvent)/;
const FORBIDDEN_OXLIB = /\blib\.(notify|progressBar|progressCircle|progressActive|cancelProgress|showTextUI|hideTextUI|isTextUIOpen|registerContext|showContext|inputDialog|alertDialog)\b/;

const findings = [];

function add(file, line, severity, rule, message) {
    findings.push({ file, line, severity, rule, message });
}

function walk(target, files = []) {
    const stat = statSync(target);
    if (stat.isFile()) {
        files.push(target);
        return files;
    }
    for (const entry of readdirSync(target)) {
        if (SKIP_DIRS.has(entry)) {
            continue;
        }
        walk(join(target, entry), files);
    }
    return files;
}

function scanLua(src) {
    const comments = new Set();
    let out = "";
    let line = 1;
    let i = 0;
    const n = src.length;
    const longOpen = (at) => /^\[(=*)\[/.exec(src.slice(at, at + 24));
    while (i < n) {
        const c = src[i];
        if (c === "-" && src[i + 1] === "-") {
            comments.add(line);
            const long = longOpen(i + 2);
            if (long) {
                const close = "]" + long[1] + "]";
                const end = src.indexOf(close, i + 2 + long[0].length);
                const stop = end === -1 ? n : end + close.length;
                for (let k = i; k < stop; k++) {
                    if (src[k] === "\n") {
                        line++;
                        comments.add(line);
                        out += "\n";
                    } else {
                        out += " ";
                    }
                }
                i = stop;
                continue;
            }
            while (i < n && src[i] !== "\n") {
                out += " ";
                i++;
            }
            continue;
        }
        if (c === "\"" || c === "'") {
            out += c;
            i++;
            while (i < n && src[i] !== c && src[i] !== "\n") {
                if (src[i] === "\\") {
                    out += "  ";
                    i += 2;
                    continue;
                }
                out += " ";
                i++;
            }
            if (src[i] === c) {
                out += c;
                i++;
            }
            continue;
        }
        if (c === "[") {
            const long = longOpen(i);
            if (long) {
                const close = "]" + long[1] + "]";
                const end = src.indexOf(close, i + long[0].length);
                const stop = end === -1 ? n : end + close.length;
                out += "\"";
                for (let k = i + 1; k < stop - 1; k++) {
                    if (src[k] === "\n") {
                        line++;
                        out += "\n";
                    } else {
                        out += " ";
                    }
                }
                out += "\"";
                i = stop;
                continue;
            }
        }
        if (c === "\n") {
            line++;
        }
        out += c;
        i++;
    }
    return { comments, code: out.split("\n") };
}

function sideOf(rel) {
    const name = basename(rel).toLowerCase();
    const parts = rel.toLowerCase().split(/[\\/]/);
    if (name.startsWith("sv_") || name.includes(".server.") || name === "server.lua" || parts.includes("server")) {
        return "server";
    }
    if (name.startsWith("cl_") || name.includes(".client.") || name === "client.lua" || parts.includes("client")) {
        return "client";
    }
    if (name.startsWith("sh_") || parts.includes("shared")) {
        return "shared";
    }
    return "unknown";
}

function lintLua(file, rel) {
    const src = readFileSync(file, "utf8");
    const raw = src.split("\n");
    const { comments, code } = scanLua(src);
    const side = sideOf(rel);
    const isFc = /config[\\/]function[\\/]/i.test(rel);
    const isManifest = basename(rel).toLowerCase() === "fxmanifest.lua";
    const isCore = /(^|[\\/])core[\\/]/i.test(rel) || /^(cl|sv)_/i.test(basename(rel));

    for (const lineNo of comments) {
        add(rel, lineNo, "error", "no-comments", "comments are not allowed in produced Lua");
    }

    code.forEach((line, index) => {
        const ln = index + 1;
        const original = raw[index] || "";

        if (/^\t+/.test(original)) {
            add(rel, ln, "warn", "indent", "use 4 spaces, not tabs");
        }
        if (/^\s*(else)?if\b.*\bthen\b\s*\S.*\bend\b[\s,)]*$/.test(line)) {
            add(rel, ln, "error", "single-line-if", "write if blocks across multiple lines");
        }
        if (FORBIDDEN_OXLIB.test(line)) {
            add(rel, ln, "error", "forbidden-oxlib", "use FC.Notify / FC.Progress / FC.ShowTextUI instead of ox_lib UI modules");
        }
        if (!isFc && /["']pNotify:SendNotification["']/.test(original) && !comments.has(ln)) {
            add(rel, ln, "warn", "use-fc", "use FC.Notify instead of triggering pNotify directly");
        }
        const literalEvent = /(RegisterNetEvent|TriggerServerEvent|TriggerClientEvent|TriggerLatentClientEvent|lib\.callback\.register|lib\.callback\.await|lib\.callback)\s*\(\s*["']([^"']+)["']/.exec(original);
        if (literalEvent && !comments.has(ln) && !LUA_THIRD_PARTY_EVENTS.test(literalEvent[2])) {
            add(rel, ln, "warn", "event-name", `build event names from scriptname (scriptname .. ":SV:x"), found "${literalEvent[2]}"`);
        }
        if (/scriptname\s*\.\.\s*["']:(?!SV:|CL:)/.test(original) && !comments.has(ln)) {
            add(rel, ln, "warn", "event-side", "event names need a :SV: or :CL: side marker");
        }
        if (/RegisterNetEvent\s*\([^)]*function\s*\(\s*(source|src|playerId|identifier|license|xPlayer)\b/i.test(line)) {
            add(rel, ln, "error", "client-identity", "never accept identity/source from the client; use the implicit source");
        }
        if (/TriggerServerEvent\s*\(.*\b(price|cost|money|reward|balance)\b/i.test(line)) {
            add(rel, ln, "warn", "client-economy", "client should send intent only; compute prices and rewards on the server");
        }
        if (/\bGetResourceState\s*\(/.test(line)) {
            add(rel, ln, "warn", "resource-state", "call exports directly (rules/contracts.md)");
        }
        if (/TriggerClientEvent\s*\([^,]+,\s*-1\b/.test(line)) {
            add(rel, ln, "warn", "broadcast", "avoid -1 broadcasts; scope to sessions or a source");
        }
        if (/MySQL\.\w+(\.\w+)?\s*\(\s*["'][^"']*["']\s*\.\./.test(original) || /["'][^"']*\b(SELECT|UPDATE|INSERT|DELETE)\b[^"']*["']\s*\.\./i.test(original)) {
            add(rel, ln, "error", "sql-concat", "use ? placeholders instead of string concatenation");
        }
        if (/ExecuteCommand\s*\(\s*[^"'\s)]/.test(line)) {
            add(rel, ln, "warn", "dynamic-command", "do not pass dynamic strings to ExecuteCommand");
        }
        if (/GetEntityCoords\s*\(\s*PlayerPedId\s*\(\s*\)\s*\)/.test(line)) {
            add(rel, ln, "info", "cache-ped", "prefer cache.ped / cache.coords");
        }
        if (/discord(app)?\.com\/api\/webhooks\//i.test(original)) {
            add(rel, ln, "error", "secret", "webhook URL in code; load it from a server convar");
        }
        if (/\bwhile\s+true\s+do\b/.test(line)) {
            const ahead = code.slice(index + 1, index + 5).join("\n");
            if (/\b(Wait|Citizen\.Wait)\s*\(\s*0\s*\)/.test(ahead) && !/\b(Wait|Citizen\.Wait)\s*\(\s*(sleep|wait|delay|interval)/i.test(code.slice(index + 1, index + 30).join("\n"))) {
                add(rel, ln, "warn", "wait-zero", "frame loop at idle; use lib.points/zones or adaptive waits");
            }
        }
        if (side === "server" && /(RegisterNetEvent|lib\.callback\.register)\s*\(.*function\s*\(/.test(line)) {
            const body = code.slice(index + 1, index + 4).join("\n");
            if (!/local\s+\w+\s*=\s*source\b/.test(body)) {
                add(rel, ln, "warn", "capture-source", "capture local src = source on the first line of the handler");
            }
        }
        if (/RegisterNUICallback\s*\(/.test(line)) {
            let depth = 0;
            let found = false;
            for (let k = index; k < Math.min(code.length, index + 200); k++) {
                const segment = code[k];
                if (/\bcb\s*\(/.test(segment) && k > index) {
                    found = true;
                }
                depth += (segment.match(/\b(function|do|then)\b/g) || []).length;
                depth -= (segment.match(/\bend\b/g) || []).length;
                if (k > index && depth <= 0) {
                    break;
                }
            }
            if (!found) {
                add(rel, ln, "error", "nui-cb", "RegisterNUICallback must call cb exactly once");
            }
        }
    });

    if (isCore && (side === "client" || side === "server") && !isManifest) {
        const head = raw.slice(0, 8).join("\n");
        if (/^(cl|sv)_main\.lua$/i.test(basename(rel)) && (!/getSharedObject\s*\(\s*\)/.test(head) || !/GetCurrentResourceName\s*\(\s*\)/.test(head))) {
            add(rel, 1, "info", "header", "start with ESX = exports[\"es_extended\"]:getSharedObject() and local scriptname = GetCurrentResourceName()");
        }
    }

    if (isManifest) {
        lintManifest(rel, src);
    }
}

function lintManifest(rel, src) {
    if (!/lua54\s*\(?\s*["']yes["']/.test(src)) {
        add(rel, 1, "warn", "manifest-lua54", "set lua54 \"yes\"");
    }
    if (/ui_page/.test(src) && !/files\s*\(?\s*\{/.test(src)) {
        add(rel, 1, "error", "manifest-files", "ui_page needs a files { } block listing UI assets");
    }
    const oxIndex = src.indexOf("@ox_lib/init.lua");
    const shared = /shared_scripts?\s*\(?\s*\{([\s\S]*?)\}/.exec(src);
    if (oxIndex !== -1 && shared && !/^\s*["']@ox_lib\/init\.lua["']/.test(shared[1])) {
        add(rel, 1, "warn", "manifest-order", "@ox_lib/init.lua should be the first shared script");
    }
    for (const block of ["client_scripts", "server_scripts"]) {
        const match = new RegExp(block + "\\s*\\(?\\s*\\{([\\s\\S]*?)\\}").exec(src);
        if (!match) {
            continue;
        }
        const body = match[1];
        const fc = body.search(/["']config\/function\//);
        const core = body.search(/["']core\//);
        if (fc !== -1 && core !== -1 && fc > core) {
            add(rel, 1, "warn", "manifest-order", `${block}: load config/function before core`);
        }
    }
}

function lintWeb(file, rel) {
    if (/\.min\.(js|css)$/.test(rel) || /vue\.global|react\.production/.test(rel)) {
        return;
    }
    const raw = readFileSync(file, "utf8").split("\n");
    raw.forEach((line, index) => {
        const ln = index + 1;
        if (/\.innerHTML\s*[+]?=|insertAdjacentHTML|document\.write\s*\(|dangerouslySetInnerHTML|v-html=|\{@html/.test(line)) {
            add(rel, ln, "warn", "xss-sink", "render data with textContent / text bindings");
        }
        if (/<script[^>]+src=["']https?:/i.test(line) || /<link[^>]+href=["']https?:/i.test(line)) {
            add(rel, ln, "warn", "remote-asset", "ship JS/CSS locally; no CDN at runtime");
        }
        if (/discord(app)?\.com\/api\/webhooks\//i.test(line)) {
            add(rel, ln, "error", "secret", "webhook URL in UI code");
        }
    });
}

const targets = process.argv.slice(2);
if (targets.length === 0) {
    console.log("usage: node scripts/lint-resource.mjs <resource-folder> [more folders or files]");
    process.exit(2);
}

for (const target of targets) {
    for (const file of walk(target)) {
        const rel = relative(process.cwd(), file) || file;
        const ext = extname(file).toLowerCase();
        if (ext === ".lua") {
            lintLua(file, rel);
        } else if ([".js", ".ts", ".tsx", ".jsx", ".html", ".vue", ".svelte"].includes(ext)) {
            lintWeb(file, rel);
        }
    }
}

const order = { error: 0, warn: 1, info: 2 };
findings.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line || order[a.severity] - order[b.severity]);
for (const f of findings) {
    console.log(`${f.file.split(sep).join("/")}:${f.line} [${f.severity}] ${f.rule} - ${f.message}`);
}
const count = (s) => findings.filter((f) => f.severity === s).length;
console.log(`\n${count("error")} error(s), ${count("warn")} warning(s), ${count("info")} info`);
process.exit(count("error") > 0 ? 1 : 0);
