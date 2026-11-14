#!/usr/bin/env node
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, basename, extname, sep } from "node:path";

const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "vendor", "stream", "fonts"]);
const LUA_THIRD_PARTY_EVENTS = /^(pNotify|esx|esx_|1nfx_core|mythic_progbar|ox_lib|ox_inventory|txAdmin|chat|baseevents|playerSpawned|onResource|onClientResource|gameEventTriggered|populationPedCreating|entityCreated|entityRemoved|explosionEvent|weaponDamageEvent)/;
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

function scanWebComments(src, kind) {
    const lines = new Set();
    let line = 1;
    let i = 0;
    const n = src.length;
    while (i < n) {
        const c = src[i];
        if (c === "\n") {
            line++;
            i++;
            continue;
        }
        if (kind !== "css" && (c === "\"" || c === "'" || c === "`") && kind !== "markup") {
            i++;
            while (i < n && src[i] !== c) {
                if (src[i] === "\\") {
                    i++;
                } else if (src[i] === "\n") {
                    line++;
                    if (c !== "`") {
                        break;
                    }
                }
                i++;
            }
            i++;
            continue;
        }
        if (kind === "css" && (c === "\"" || c === "'")) {
            i++;
            while (i < n && src[i] !== c && src[i] !== "\n") {
                i++;
            }
            i++;
            continue;
        }
        if (kind === "css" && src.startsWith("url(", i)) {
            const close = src.indexOf(")", i);
            i = close === -1 ? n : close + 1;
            continue;
        }
        if ((kind === "js" || kind === "css") && c === "/" && src[i + 1] === "*") {
            lines.add(line);
            const end = src.indexOf("*/", i + 2);
            const stop = end === -1 ? n : end + 2;
            for (let k = i; k < stop; k++) {
                if (src[k] === "\n") {
                    line++;
                    lines.add(line);
                }
            }
            i = stop;
            continue;
        }
        if (kind === "js" && c === "/" && src[i + 1] === "/") {
            lines.add(line);
            while (i < n && src[i] !== "\n") {
                i++;
            }
            continue;
        }
        if ((kind === "markup") && src.startsWith("<!--", i)) {
            lines.add(line);
            const end = src.indexOf("-->", i + 4);
            const stop = end === -1 ? n : end + 3;
            for (let k = i; k < stop; k++) {
                if (src[k] === "\n") {
                    line++;
                    lines.add(line);
                }
            }
            i = stop;
            continue;
        }
        i++;
    }
    return lines;
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

function lintBalance(rel, code) {
    let blocks = 0;
    let paren = 0;
    let bracket = 0;
    let brace = 0;
    code.forEach((line, index) => {
        for (const match of line.matchAll(/(?<![.\w:])(function|if|do|repeat|end|until)(?![\w])/g)) {
            blocks += match[1] === "end" || match[1] === "until" ? -1 : 1;
            if (blocks < 0) {
                add(rel, index + 1, "error", "unbalanced-blocks", "end/until without a matching block opener");
                blocks = 0;
            }
        }
        for (const ch of line) {
            if (ch === "(") paren++;
            else if (ch === ")") paren--;
            else if (ch === "[") bracket++;
            else if (ch === "]") bracket--;
            else if (ch === "{") brace++;
            else if (ch === "}") brace--;
        }
    });
    if (blocks !== 0) {
        add(rel, code.length, "error", "unbalanced-blocks", `${blocks} block(s) are not closed (function/if/do/repeat versus end/until)`);
    }
    if (paren !== 0 || bracket !== 0 || brace !== 0) {
        add(rel, code.length, "error", "unbalanced-brackets", `unbalanced () ${paren}, [] ${bracket}, {} ${brace}`);
    }
}

function lintLua(file, rel) {
    const src = readFileSync(file, "utf8").replace(/\r\n/g, "\n");
    const raw = src.split("\n");
    const { comments, code } = scanLua(src);
    const side = sideOf(rel);
    if (/^sh_/i.test(basename(rel))) {
        add(rel, 1, "error", "no-sh-file", "no sh_*.lua files; client code in cl_*.lua, server code in sv_*.lua, shared data in config/");
    }
    const isManifest = basename(rel).toLowerCase() === "fxmanifest.lua";

    for (const lineNo of comments) {
        add(rel, lineNo, "error", "no-comments", "comments are not allowed in produced Lua");
    }

    if (/config[\\/]function[\\/]/i.test(rel)) {
        add(rel, 1, "error", "no-config-function", "config/function is removed; write the logic as methods in core/");
    }

    if (!isManifest) {
        lintBalance(rel, code);
    }

    const definesScriptname = code.some((line) => /^local\s+scriptname\s*=/.test(line));
    const usesScriptname = code.some((line) => /\bscriptname\b/.test(line) && !/^local\s+scriptname\s*=/.test(line));
    if (!isManifest && usesScriptname && !definesScriptname) {
        add(rel, 1, "error", "scriptname-undefined", "scriptname is file-local; define local scriptname = GetCurrentResourceName() in every file that uses it");
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
        if (/\bFC\b/.test(line)) {
            add(rel, ln, "error", "no-fc", "the FC table is removed; call the export or event directly inside a module method");
        }
        if (/^local\s+function\b/.test(line)) {
            add(rel, ln, "error", "no-local-function", "no file-level local function; make it a method of the module table");
        }
        if (/^local\s+[A-Z][A-Z0-9_]*\s*=/.test(line)) {
            add(rel, ln, "error", "no-file-constant", "no file-level constants; write the value at the use site or make it a module field");
        }
        const topLocal = /^local\s+(\w+)\s*=\s*(.*)$/.exec(line);
        if (topLocal && topLocal[1] !== "scriptname" && !/^\{/.test(topLocal[2].trim()) && !/^[A-Z][A-Z0-9_]*$/.test(topLocal[1])) {
            add(rel, ln, "warn", "file-local", `file-level local "${topLocal[1]}" is only allowed for scriptname and the module table`);
        }
        if (/^(Config(?:\.\w+)*) = \1 or (\{\}|\d+|"[^"]*"|true|false)\s*$/.test(line)) {
            add(rel, ln, "error", "no-config-guard", "create each Config table once in config/config.lua with plain assignment (Config = {}, Config.General = {}); later files must not repeat X = X or {}");
        }
        if (/^[A-Za-z_]\w* = [A-Za-z_]\w* or \{\}\s*$/.test(line) && !/^Config/.test(line)) {
            add(rel, ln, "error", "no-global-guard", "no global state tables; keep state as fields of the module table (Module.ServerState / Module.PlayerState)");
        }
        if (/exports\s*\[\s*["']es_extended["']\s*\]|exports\.es_extended/.test(original)) {
            add(rel, ln, "error", "legacy-esx", "load @1nfx_core/imports.lua in the manifest and use the global Core instead of es_extended");
        }
        if (FORBIDDEN_OXLIB.test(line)) {
            add(rel, ln, "error", "forbidden-oxlib", "use the server UI exports (pNotify:SendNotification, 1nfx_processbar, 1nfx_textui) instead of ox_lib UI modules");
        }
        if (/\bRunStaticPlayerMethod\b/.test(line)) {
            add(rel, ln, "error", "non-standard-esx", "use Core.GetPlayerFromId(source) instead of RunStaticPlayerMethod");
        }
        const literalEvent = /(RegisterNetEvent|TriggerServerEvent|TriggerClientEvent|TriggerLatentClientEvent|lib\.callback\.register|lib\.callback\.await|lib\.callback)\s*\(\s*["']([^"']+)["']/.exec(original);
        if (literalEvent && !comments.has(ln) && !LUA_THIRD_PARTY_EVENTS.test(literalEvent[2])) {
            const isCrossResourceListen = literalEvent[1] === "RegisterNetEvent" && /^(1nfx_|1NFX:|IFF:)/.test(literalEvent[2]) && !rel.replace(/\\/g, "/").startsWith(literalEvent[2].split(":")[0] + "/");
            if (!isCrossResourceListen) {
                add(rel, ln, "warn", "event-name", `build event names from scriptname (scriptname .. ":SV:x"), found "${literalEvent[2]}"`);
            }
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
        if (/TriggerLatentClientEvent\s*\([^,]+,\s*-1\b/.test(line)) {
            add(rel, ln, "warn", "latent-broadcast", "latent bandwidth is per target; build an interest set before sending a large payload");
        }
        if (/MySQL\.\w+(\.\w+)?\s*\(\s*["'][^"']*["']\s*\.\./.test(original) || /["'][^"']*\b(SELECT|UPDATE|INSERT|DELETE)\b[^"']*["']\s*\.\./i.test(original)) {
            add(rel, ln, "error", "sql-concat", "use ? placeholders instead of string concatenation");
        }
        if (/\bSELECT\s+\*\s+FROM\b/i.test(original) && !comments.has(ln)) {
            add(rel, ln, "warn", "select-star", "select only the columns consumed by the caller");
        }
        if (/ExecuteCommand\s*\(\s*[^"'\s)]/.test(line)) {
            add(rel, ln, "warn", "dynamic-command", "do not pass dynamic strings to ExecuteCommand");
        }
        if (/GetEntityCoords\s*\(\s*PlayerPedId\s*\(\s*\)\s*\)/.test(line)) {
            add(rel, ln, "info", "cache-ped", "prefer cache.ped / cache.coords");
        }
        if (/\bGetGamePool\s*\(/.test(line)) {
            add(rel, ln, "warn", "pool-scan", "avoid generic full-pool sweeps; use owned registries or a measured, infrequent diagnostic path");
        }
        if (/discord(app)?\.com\/api\/webhooks\//i.test(original)) {
            add(rel, ln, "error", "secret", "webhook URL in code; keep it in a server-only config file");
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
                if (/\bcb\b/.test(segment) && k > index) {
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

    if (isManifest) {
        lintManifest(rel, src);
    }
}

function lintManifest(rel, src) {
    if (/^\s*(dependencies|dependency)\b/m.test(src)) {
        add(rel, 1, "error", "no-dependencies", "remove dependencies from the manifest; set start order in server.cfg");
    }
    if (/^\s*escrow_ignore\b/m.test(src)) {
        add(rel, 1, "error", "no-escrow-ignore", "remove escrow_ignore from the manifest");
    }
    if (/config[\\/]function[\\/]|config\/function/.test(src)) {
        add(rel, 1, "error", "no-config-function", "remove config/function from the manifest");
    }
    if (/\buse_experimental_fxv2_oal\s*\(?/.test(src)) {
        add(rel, 1, "warn", "manifest-oal", "enable experimental OAL only after auditing native signatures and vector arguments");
    }
    if (/ui_page/.test(src) && !/files\s*\(?\s*\{/.test(src)) {
        add(rel, 1, "error", "manifest-files", "ui_page needs a files { } block listing UI assets");
    }
    if (/\bexports\s*\{/.test(src) || /server_exports\s*\{/.test(src)) {
        add(rel, 1, "warn", "manifest-exports", "declare exports with exports(\"name\", function) in code instead of the manifest");
    }
    const oxIndex = src.indexOf("@ox_lib/init.lua");
    const shared = /shared_scripts?\s*\(?\s*\{([\s\S]*?)\}/.exec(src);
    if (oxIndex !== -1 && shared && !/^\s*["']@ox_lib\/init\.lua["']/.test(shared[1])) {
        add(rel, 1, "warn", "manifest-order", "@ox_lib/init.lua should be the first shared script");
    }
}

function lintWeb(file, rel) {
    if (/\.min\.(js|css)$/.test(rel) || /vue\.global|react\.production/.test(rel) || /[\\/]assets[\\/][^\\/]+\.[a-z0-9_-]{6,}\.(js|css)$/i.test(rel)) {
        return;
    }
    const ext = extname(file).toLowerCase();
    const src = readFileSync(file, "utf8").replace(/\r\n/g, "\n");
    const kind = ext === ".css" ? "css" : [".html", ".vue", ".svelte"].includes(ext) ? "markup" : "js";
    for (const lineNo of scanWebComments(src, kind)) {
        add(rel, lineNo, "error", "no-comments", "comments are not allowed in produced UI code");
    }
    if (ext === ".css") {
        return;
    }
    const raw = src.split("\n");
    raw.forEach((line, index) => {
        const ln = index + 1;
        if (/\.innerHTML\s*[+]?=|insertAdjacentHTML|document\.write\s*\(|dangerouslySetInnerHTML|v-html=|\{@html/.test(line)) {
            add(rel, ln, "warn", "xss-sink", "render data with textContent / text bindings");
        }
        if (/\$\([^)]*\)\.html\s*\(/.test(line)) {
            add(rel, ln, "warn", "xss-sink", "render data with textContent / text bindings instead of jQuery html()");
        }
        if (/(fetch|\$\.post|axios\.post)\s*\(\s*["'`]https:\/\/[a-z0-9_-]+\//i.test(line)) {
            add(rel, ln, "warn", "hardcoded-nui-resource", "build NUI callback URLs with GetParentResourceName()");
        }
        if (/<script[^>]+src=["']https?:/i.test(line) || /<link[^>]+href=["']https?:/i.test(line)) {
            add(rel, ln, "warn", "remote-asset", "ship JS/CSS locally; no CDN at runtime");
        }
        if (/discord(app)?\.com\/api\/webhooks\//i.test(line)) {
            add(rel, ln, "error", "secret", "webhook URL in UI code");
        }
        if (kind === "js" && /^(const|let|var)\s+[A-Z][A-Z0-9_]*\s*=/.test(line)) {
            add(rel, ln, "warn", "no-file-constant", "no file-level constants; keep values as fields of the app object");
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
        } else if ([".js", ".ts", ".tsx", ".jsx", ".html", ".vue", ".svelte", ".css"].includes(ext)) {
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
