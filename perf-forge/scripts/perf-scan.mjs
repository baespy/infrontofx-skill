#!/usr/bin/env node
import { readdirSync, readFileSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, extname, basename, dirname } from "node:path";

const args = process.argv.slice(2);
const root = args.find((a) => !a.startsWith("--")) || "resources";
const jsonOut = (args.find((a) => a.startsWith("--json=")) || "").slice(7);
const top = Number((args.find((a) => a.startsWith("--top=")) || "--top=20").slice(6));
const SKIP_ALL = new Set(["node_modules", "_backup", "_dev", "cache", ".git", "html-dev", "stream"]);
const UI_SRC = /[\\/](html|web|ui|nui)([\\/]|$)/i;
const VENDOR = /(^|\/)vendor\/|\.min\.(js|css)$|jquery|bootstrap|popper|vue\.global|perfect-scrollbar|countdowntime/i;
const BOOT_RE = /^(.*[.:])?(Ensure|Migrat|Schema|Init|Setup|Boot|Bootstrap|Install|OnStart|LoadAll|Create(Table|Index))/i;
const LOAD_WAIT = /\bwhile\s+not\s+(Has\w+Loaded|IsScreenFaded\w*|HasCollisionLoaded\w*|NetworkDoesNetworkIdExist|NetworkHasControlOfEntity|DoesEntityExist|Core\b|ESX\b|lib\b)|\bwhile\s+[\w.]+\s*==\s*nil\b/;
const KB = 1024;

const RULES = {
    "frame-thread": [5, "CreateThread inside a Wait(0) loop starts a thread every frame"],
    "frame-export": [5, "export call inside a Wait(0) loop; read once on change (cache, state bag, event) and reuse"],
    "frame-json": [5, "json.encode/decode inside a Wait(0) loop"],
    "frame-net": [5, "TriggerServerEvent or callback inside a Wait(0) loop; send on change only"],
    "frame-pool": [5, "GetGamePool or entity enumeration inside a Wait(0) loop"],
    "frame-hash": [4, "GetHashKey with a literal inside a Wait(0) loop; use a backtick literal `name` (hashed at compile time)"],
    "frame-alloc": [2, "table or string building inside a Wait(0) loop; build once outside and reuse"],
    "frame-text": [2, "per-frame 2D/3D text natives; gate by distance with lib.points or move to the hologram/textui export"],
    "frame-many": [3, "several Wait(0) loops in one resource; merge into one frame loop that runs only while something is active"],
    "loop-sql": [5, "database call inside a loop; batch with IN (...) or one multi-row write"],
    "loop-broadcast": [4, "TriggerClientEvent to -1 inside a loop or interval; coalesce, send to interested players only"],
    "loop-thread": [4, "CreateThread inside a loop; one scheduler or queue owns the work"],
    "players-export": [4, "export or xPlayer call per player inside a GetPlayers loop; use one bulk query (Core.GetExtendedPlayers) or a cache"],
    "loop-json": [3, "json.encode inside a loop or interval; cache encoded rows keyed by their mutable fields"],
    "hash-literal": [1, "GetHashKey with a literal; a backtick literal `name` is free at runtime"],
    "statebag-hot": [4, "LocalPlayer.state / Entity(x).state / Player(x).state inside a loop: every .state access builds 2 tables and a bag id, every read deserializes; hold the bag in a field and mirror values with AddStateBagChangeHandler"],
    "export-hot": [3, "exports[res] inside a loop: each access builds a proxy table and a closure, then pcall and a serialized function-ref call; hold the proxy in a field, call once per pass, or push changes to a cache"],
    "nui-send-hot": [3, "SendNUIMessage inside a Wait(0) loop json-encodes every frame; send on change and reuse the encoded string (SendNuiMessage)"],
    "getplayers-hot": [3, "GetPlayers() inside a loop or interval builds a new table with one native per player; keep a set updated on playerJoining/playerDropped"],
    "string-hash-arg": [2, "string model or weapon name passed to a hash native; the wrapper calls GetHashKey on every call, pass a backtick hash"],
    "pack-per-target": [3, "TriggerClientEvent per target in a loop packs the payload every time; msgpack.pack_args once and TriggerClientEventInternal(name, target, payload, #payload)"],
    "event-fanout": [2, "same event has several AddEventHandler/RegisterNetEvent handlers in this resource; each handler costs debug.getinfo, string.format and a coroutine per dispatch, use one handler that calls methods"],
    "statebag-handler-nofilter": [3, "AddStateBagChangeHandler with a nil key filter: C++ filters by exact key before calling Lua, nil matches every change of every bag in scope (serialize, Lua call, unpack each); pass the key"],
    "cleartimeout": [1, "ClearTimeout only finds timers created in the current callback (runtime source, untested in game); cancel with a generation token checked inside the callback"],
    "self-event": [2, "TriggerEvent to an event this resource handles itself; pack, unpack and a coroutine for what a direct method call does"],
    "model-leak": [2, "RequestModel without SetModelAsNoLongerNeeded in the same file"],
    "nui-infinite": [1, "infinite CSS animation not behind a state class; costs only if it runs while the UI is closed, confirm with nui-idle.cjs before editing"],
    "nui-blur": [3, "backdrop-filter or filter blur; expensive in CEF, use a pre-blurred image or flat rgba"],
    "nui-raf": [2, "self-rescheduling requestAnimationFrame loop; stop it while hidden"],
    "nui-interval": [2, "setInterval in NUI; run timers only while the UI is open"],
    "nui-image": [2, "large NUI image; resize to display size and use webp"],
    "nui-audio": [2, "large NUI audio; trim and encode ogg/opus at 96-128 kbps"],
    "nui-font": [1, "large NUI font; subset to the glyphs used (Thai + Latin) and use woff2"],
    "nui-sourcemap": [1, "source map shipped with the UI; drop .map from the build output"],
};

const findings = [];
const resources = new Map();

function add(res, file, line, rule, extra = "", low = "") {
    const weight = low ? 1 : RULES[rule][0];
    findings.push({ resource: res, file, line, rule, weight, message: RULES[rule][1], extra: [extra, low].filter(Boolean).join(", ") });
    const r = resources.get(res);
    if (r) r.score += weight;
}

function walk(dir, list = []) {
    let entries;
    try {
        entries = readdirSync(dir, { withFileTypes: true });
    } catch {
        return list;
    }
    for (const e of entries) {
        if (SKIP_ALL.has(e.name)) continue;
        if (e.name === "src" && UI_SRC.test(dir)) continue;
        const full = join(dir, e.name);
        if (e.isDirectory()) walk(full, list);
        else list.push(full);
    }
    return list;
}

function findResources(dir, list = []) {
    let entries;
    try {
        entries = readdirSync(dir, { withFileTypes: true });
    } catch {
        return list;
    }
    if (entries.some((e) => e.isFile() && e.name === "fxmanifest.lua")) {
        list.push(dir);
        return list;
    }
    for (const e of entries) if (e.isDirectory() && !SKIP_ALL.has(e.name)) findResources(join(dir, e.name), list);
    return list;
}

function sideOf(rel) {
    const low = rel.toLowerCase();
    if (/(^|\/)(client|cl_)|\/cl_[^/]*$|client\.lua$/.test(low)) return "client";
    if (/(^|\/)(server|sv_)|\/sv_[^/]*$|server\.lua$/.test(low)) return "server";
    return "shared";
}

function cleanLua(text) {
    const out = [];
    let longClose = null;
    for (const raw of text.split(/\r?\n/)) {
        let src = raw;
        let code = "";
        while (src.length) {
            if (longClose) {
                const k = src.indexOf(longClose);
                if (k < 0) {
                    src = "";
                    break;
                }
                src = src.slice(k + longClose.length);
                code += '""';
                longClose = null;
                continue;
            }
            const m = /(--)?\[(=*)\[|--|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/.exec(src);
            if (!m) {
                code += src;
                break;
            }
            code += src.slice(0, m.index);
            if (m[0].startsWith('"') || m[0].startsWith("'")) {
                code += '""';
                src = src.slice(m.index + m[0].length);
            } else if (m[0] === "--") {
                break;
            } else {
                longClose = "]" + m[2] + "]";
                src = src.slice(m.index + m[0].length);
            }
        }
        out.push(code);
    }
    return out;
}

function buildBlocks(code, raw) {
    const blocks = [];
    const stack = [];
    let pending = null;
    let lastFn = "";
    const token = /\b(function|if|do|repeat|while|for|end|until)\b|\bWait\s*\(\s*([^()]*?)\s*\)/g;
    code.forEach((c, i) => {
        const ln = i + 1;
        const fnMatch = /function\s+([\w.:]+)\s*\(/.exec(c);
        if (fnMatch) lastFn = fnMatch[1];
        const zero = /\b([A-Za-z_]\w*)\s*=\s*0\b(?!\.)/.exec(c);
        if (zero) {
            for (const b of stack) if (b.loop) b.zeroVars.add(zero[1]);
        }
        let m;
        token.lastIndex = 0;
        while ((m = token.exec(c))) {
            const t = m[1];
            if (!t) {
                const loop = [...stack].reverse().find((b) => b.loop || b.type === "function");
                if (loop && loop.loop) loop.waits.push(m[2]);
                continue;
            }
            if (t === "while" || t === "for") {
                pending = { kind: t, line: ln, text: c.slice(m.index) };
                continue;
            }
            if (t === "end" || t === "until") {
                const b = stack.pop();
                if (b) b.end = ln;
                continue;
            }
            const b = { type: t, start: ln, end: code.length, loop: false, waits: [], zeroVars: new Set(), fn: "", players: false, interval: false, retry: false, cond: "", bootEvt: false, cleanup: false };
            if (t === "do" && pending) {
                b.loop = true;
                b.kind = pending.kind;
                b.cond = pending.text;
                b.players = pending.kind === "for" && /\b(GetPlayers|GetActivePlayers|GetExtendedPlayers)\s*\(/.test(pending.text);
                b.retry = pending.kind === "for" && /\bfor\s+(_|attempt|try|tries|retry|i)\s*=\s*1\s*,\s*\d{1,3}\s+do/.test(pending.text) && /\b(_|attempt|try|tries|retry)\b/.test(pending.text);
                const vars = /\bfor\s+([\w\s,]+?)\s*(?:=|\bin\b)/.exec(pending.text);
                b.vars = vars ? vars[1].split(",").map((v) => v.trim()).filter((v) => v && v !== "_") : [];
                pending = null;
            } else if (t === "repeat") {
                b.loop = true;
                b.kind = "repeat";
            } else if (t === "function") {
                b.fn = fnMatch ? fnMatch[1] : "";
                b.interval = /SetInterval\s*\(/.test(c);
                b.bootEvt = /onResourceStart|onServerResourceStart/.test(raw[i]);
                b.cleanup = /onResourceStop|playerDropped|onClientResourceStop/.test(raw[i]);
            }
            stack.push(b);
            blocks.push(b);
        }
    });
    for (const b of blocks) {
        if (!b.loop) continue;
        const bodyZero = (v) => b.zeroVars.has(v);
        b.frame = b.kind === "while" && b.waits.some((w) => w === "0" || (/^[A-Za-z_]\w*$/.test(w) && bodyZero(w))) && !LOAD_WAIT.test(b.cond);
        b.slow = b.waits.some((w) => /Config\.|^\d{4,}$/.test(w));
    }
    return { blocks, lastFn };
}

const eventMaps = new Map();

function trackEvents(res, rel, raw, code, side) {
    if (!eventMaps.has(res)) eventMaps.set(res, { handlers: new Map(), triggers: [] });
    const map = eventMaps.get(res);
    const keyOf = (selfPrefix, name) => `${side}|${selfPrefix ? "@self" : ""}${name}`;
    raw.forEach((line, i) => {
        if (!code[i] || !/\S/.test(code[i])) return;
        const h = /\b(?:AddEventHandler|RegisterNetEvent)\s*\(\s*(scriptname\s*\.\.\s*)?["']([^"']+)["']\s*,\s*function/.exec(line);
        if (h) {
            const key = keyOf(!!h[1], h[2]);
            if (!map.handlers.has(key)) map.handlers.set(key, []);
            map.handlers.get(key).push({ file: rel, line: i + 1 });
        }
        const t = /\bTriggerEvent\s*\(\s*(scriptname\s*\.\.\s*)?["']([^"']+)["']/.exec(line);
        if (t) map.triggers.push({ key: keyOf(!!t[1], t[2]), file: rel, line: i + 1, name: t[2] });
    });
}

function flushEvents() {
    for (const [res, map] of eventMaps) {
        const lifecycle = /(onResourceStop|onClientResourceStop|onResourceStart|onClientResourceStart|onServerResourceStart|playerDropped|playerJoining|playerConnecting|playerSpawned|playerLoaded|onPlayerSpawn|playerSpawnReady|modelLoaded)$/;
        for (const [key, list] of map.handlers) {
            const name = key.split("|")[1];
            if (list.length > 1) add(res, list[1].file, list[1].line, "event-fanout", `${name} x${list.length}`, lifecycle.test(name) ? "rare lifecycle event, low priority" : "");
        }
        for (const t of map.triggers) {
            const own = t.key.includes("@self") || /:(CL|SV):/.test(t.name);
            if (own && (map.handlers.has(t.key) || map.handlers.has(t.key.replace(/^(client|server)\|/, "shared|")))) add(res, t.file, t.line, "self-event", t.name);
        }
    }
}

function scanLua(res, rel, text) {
    const raw = text.split(/\r?\n/);
    const code = cleanLua(text);
    const side = sideOf(rel);
    trackEvents(res, rel, raw, code, side);
    const { blocks } = buildBlocks(code, raw);
    const frameLoops = blocks.filter((b) => b.frame).length;
    const requestsModel = /RequestModel\s*\(/.test(text);
    const releasesModel = /SetModelAsNoLongerNeeded|lib\.requestModel/.test(text);
    code.forEach((c, i) => {
        const ln = i + 1;
        const around = blocks.filter((b) => b.start <= ln && ln <= b.end);
        const loops = around.filter((b) => b.loop);
        const frame = loops.some((b) => b.frame);
        const inLoop = loops.length > 0;
        const fns = around.filter((b) => b.type === "function");
        const boot = fns.some((b) => (b.fn && BOOT_RE.test(b.fn)) || b.bootEvt) ? "startup path, low priority" : "";
        const cleanup = fns.some((b) => b.cleanup);
        const interval = fns.some((b) => b.interval);
        const players = loops.some((b) => b.players);
        if (/GetHashKey\s*\(\s*["']/.test(raw[i])) add(res, rel, ln, frame ? "frame-hash" : "hash-literal");
        if (frame) {
            if (/CreateThread\s*\(/.test(c)) add(res, rel, ln, "frame-thread");
            if (/exports\s*[\[.]/.test(c)) add(res, rel, ln, "frame-export");
            if (/json\.(encode|decode)\s*\(/.test(c)) add(res, rel, ln, "frame-json");
            if (/TriggerServerEvent|lib\.callback(\.await)?\s*\(|TriggerLatentServerEvent/.test(c)) add(res, rel, ln, "frame-net");
            if (/GetGamePool|FindFirst(Object|Ped|Vehicle)|getNearby(Objects|Peds|Vehicles)/.test(c)) add(res, rel, ln, "frame-pool");
            if (/string\.format\s*\(|\.\.\s*["'(a-zA-Z]|=\s*\{\s*[^}\s]/.test(c)) add(res, rel, ln, "frame-alloc");
            if (side !== "server" && /(SetTextFont|BeginTextCommandDisplayText|DrawText3D|EndTextCommandDisplayText)\s*\(/.test(c)) add(res, rel, ln, "frame-text");
        } else if (inLoop) {
            const guarded = /\b(busy|spawning|loading|pending|running|active)\b/.test(code.slice(Math.max(0, i - 3), i + 1).join(" "));
            if (/CreateThread\s*\(/.test(c) && !guarded) add(res, rel, ln, "loop-thread", "", boot);
            if (/json\.encode\s*\(/.test(c)) add(res, rel, ln, "loop-json", "", boot);
        }
        if (inLoop && /MySQL\.|exports\.oxmysql|exports\[\s*""\s*\]\s*:\s*(query|execute|insert|update|scalar|single|prepare)/.test(c)) {
            const batched = /\bIN\s*\(\s*\?|\bIN\s*\(\s*["']\s*\.\.|table\.concat\(\s*\w*(placeholder|values|rows|params)|VALUES\s*["']\s*\.\./i.test(raw.slice(Math.max(0, i - 12), i + 1).join(" "));
            const retry = loops.some((b) => b.retry);
            if (!batched) add(res, rel, ln, "loop-sql", "", boot || (retry ? "retry loop, low priority" : "") || (cleanup ? "stop/drop cleanup" : ""));
        }
        if ((inLoop || interval) && /TriggerClientEvent\s*\([^,]+,\s*-1/.test(c)) {
            const low = boot || (cleanup ? "stop cleanup, low priority" : "") || (loops.some((b) => b.slow) ? "timed loop, low priority" : "");
            add(res, rel, ln, "loop-broadcast", "", low);
        }
        if (players && /exports\s*[\[.]|Core\.GetPlayerFromId|xPlayer[.:]|GetPlayerFromId/.test(c) && !/==\s*[\w.]+\s+and\s+Core\.GetPlayerFromId/.test(c)) add(res, rel, ln, "players-export", "", boot);
        const slowLoop = !frame && loops.every((b) => b.slow || b.kind === "for" || b.kind === "repeat" || !b.waits.length || b.waits.some((w) => /^\d{3,}$/.test(w) || /sleep|wait|delay|interval/i.test(w)));
        if ((inLoop || frame) && /\b(LocalPlayer|Entity\s*\([^)]*\)|Player\s*\([^)]*\))\s*\.\s*state\b/.test(c)) add(res, rel, ln, "statebag-hot", frame ? "per frame" : "", boot || (slowLoop && !loops.some((b) => b.kind === "for") ? "slow loop, low priority" : ""));
        if (inLoop && !frame && !players && /exports\s*[\[.]/.test(c) && !/MySQL|oxmysql/.test(c)) add(res, rel, ln, "export-hot", "", boot);
        if (/\bAddStateBagChangeHandler\s*\(\s*(nil|""|'')\s*,/.test(raw[i])) add(res, rel, ln, "statebag-handler-nofilter");
        if (/\bClearTimeout\s*\(/.test(c)) add(res, rel, ln, "cleartimeout");
        if (frame && /\bSendNUIMessage\s*\(/.test(c)) {
            const gated = /\bif\b[^\n]*(~=|changed|dirty|last)/.test(code.slice(Math.max(0, i - 4), i).join(" ")) || /\belseif\b/.test(code.slice(Math.max(0, i - 4), i).join(" "));
            add(res, rel, ln, "nui-send-hot", "", gated ? "looks change-gated, check" : "");
        }
        if ((inLoop || interval) && side !== "client" && /\bGetPlayers\s*\(/.test(c) && !loops.some((b) => b.start === ln)) add(res, rel, ln, "getplayers-hot", "", boot);
        if (/\b(RequestModel|HasModelLoaded|IsModelInCdimage|IsModelValid|IsModelAVehicle|IsModelAPed|CreateObject|CreateObjectNoOffset|CreateVehicle|CreatePed|GetClosestObjectOfType)\s*\(\s*["']/.test(raw[i]) || /\b(GiveWeaponToPed|SetCurrentPedWeapon|HasPedGotWeapon|RemoveWeaponFromPed)\s*\([^,]+,\s*["']/.test(raw[i])) add(res, rel, ln, "string-hash-arg", "", inLoop || frame ? "" : "cold path, low priority");
        const tce = /\bTriggerClientEvent\s*\(\s*[^,]+,\s*(?!-1\b)([\w.\[\]]+)\s*,?(.*)$/.exec(c);
        if (inLoop && side !== "client" && tce && !/TriggerClientEventInternal/.test(c)) {
            const loop = loops[loops.length - 1];
            const bodyLocals = new Set(loop.vars || []);
            for (let k = loop.start; k < ln; k++) {
                const m = /\blocal\s+([\w\s,]+?)\s*=/.exec(code[k - 1] || "");
                if (m) m[1].split(",").forEach((v) => bodyLocals.add(v.trim()));
            }
            const args = tce[2] || "";
            const perTarget = [...bodyLocals].some((v) => v && new RegExp(`\\b${v.replace(/[^\w]/g, "")}\\b`).test(args));
            if (!perTarget) add(res, rel, ln, "pack-per-target", "", boot || (cleanup ? "stop/drop cleanup, low priority" : ""));
        }
    });
    if (requestsModel && !releasesModel && side !== "server") add(res, rel, 1, "model-leak");
    return frameLoops;
}

function selectorBefore(lines, i) {
    let j = i;
    while (j >= 0 && !lines[j].includes("{")) j--;
    const parts = [];
    for (let k = j; k >= 0 && k > j - 6; k--) {
        const text = k === j ? lines[k].slice(0, lines[k].indexOf("{")) : lines[k];
        if (k < j && /[;}]\s*$/.test(text)) break;
        parts.unshift(text);
    }
    return parts.join(" ").trim();
}

function scanUi(res, rel, text, ext, siblings) {
    const lines = text.split(/\r?\n/);
    if (lines.length < 3 && text.length > 20000) {
        const count = (re) => (text.match(re) || []).length;
        const blur = count(/backdrop-filter:\s*blur\(\s*[1-9]|[^-]filter:\s*blur\(\s*[1-9]/g);
        if (ext === ".css" && blur) add(res, rel, 1, "nui-blur", `${blur}x in bundle`);
        if (ext === ".css" && count(/infinite/g)) add(res, rel, 1, "nui-infinite", `${count(/infinite/g)}x in bundle, check which are state-gated`);
        if (count(/setInterval\(/g)) add(res, rel, 1, "nui-interval", `${count(/setInterval\(/g)}x in bundle`);
        return;
    }
    const theme = /(^|\/)(billie-)?theme\.css$/i.test(rel);
    lines.forEach((l, i) => {
        if (/setInterval\s*\(/.test(l)) add(res, rel, i + 1, "nui-interval");
        const raf = /requestAnimationFrame\s*\(\s*([\w.$]+)\s*\)/.exec(l);
        if (raf) {
            const name = raf[1].split(".").pop();
            if (new RegExp(`(function\\s+${name}\\b|\\b${name}\\s*=)`).test(text)) add(res, rel, i + 1, "nui-raf");
        }
        if (/^\s*-webkit-backdrop-filter/.test(l)) return;
        if (/backdrop-filter\s*:\s*(?!none\b|initial\b|unset\b)[^;]*\bblur\(\s*[1-9]|(?<![-\w])filter\s*:[^;]*\bblur\(\s*[1-9]/.test(l)) add(res, rel, i + 1, "nui-blur");
        if (ext === ".css" && /animation(-iteration-count)?\s*:[^;]*\binfinite\b/.test(l)) {
            const sel = selectorBefore(lines, i);
            if (/\.is-|\.open\b|\.active\b|\.show\b|\.visible\b|\.playing\b|\[data-|:hover|@keyframes/.test(sel)) return;
            const classes = (sel.match(/\.([A-Za-z_][\w-]*)/g) || []).map((c) => c.slice(1));
            if (classes.length && !classes.some((c) => siblings.some((t) => t.includes(c)))) return;
            add(res, rel, i + 1, "nui-infinite", theme ? "shared theme copy" : "", theme ? "shared theme copy" : "");
        }
    });
}

const manifests = findResources(root);
let clientRuntimes = 0;
let uiPages = 0;
for (const dir of manifests) {
    const name = basename(dir);
    const manifest = readFileSync(join(dir, "fxmanifest.lua"), "utf8");
    const client = /client_scripts?\b/.test(manifest);
    const uiPage = (/^\s*ui_page\s*\(?\s*['"]([^'"]+)['"]/m.exec(manifest) || [])[1];
    const uiRoot = uiPage && !/^https?:/.test(uiPage) ? dirname(uiPage).split("\\").join("/") : null;
    const fxap = existsSync(join(dir, ".fxap"));
    if (client) clientRuntimes++;
    if (uiPage) uiPages++;
    resources.set(name, { resource: name, dir: relative(root, dir).split("\\").join("/"), score: 0, client, ui: !!uiPage, fxap, frameLoops: 0, uiBytes: 0 });
    if (fxap) continue;
    const files = walk(dir);
    const uiFiles = uiRoot ? files.filter((f) => relative(dir, f).split("\\").join("/").startsWith(uiRoot === "." ? "" : uiRoot + "/")) : [];
    const uiTexts = uiFiles.filter((f) => /\.(js|mjs|html|css)$/i.test(f) && statSync(f).size < 4 * 1024 * KB).map((f) => ({ f, t: readFileSync(f, "utf8") }));
    for (const file of files) {
        const rel = relative(root, file).split("\\").join("/");
        if (extname(file).toLowerCase() !== ".lua") continue;
        resources.get(name).frameLoops += scanLua(name, rel, readFileSync(file, "utf8"));
    }
    for (const file of uiFiles) {
        const rel = relative(root, file).split("\\").join("/");
        const ext = extname(file).toLowerCase();
        const size = statSync(file).size;
        resources.get(name).uiBytes += size;
        if (VENDOR.test(rel)) continue;
        if ([".js", ".css", ".html", ".mjs"].includes(ext)) {
            const own = uiTexts.find((u) => u.f === file);
            if (own) scanUi(name, rel, own.t, ext, uiTexts.filter((u) => u.f !== file).map((u) => u.t));
        } else if ([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"].includes(ext) && size > 300 * KB) add(name, rel, 0, "nui-image", `${Math.round(size / KB)} KB`);
        else if ([".mp3", ".wav", ".ogg", ".m4a", ".webm", ".mp4"].includes(ext) && size > 1024 * KB) add(name, rel, 0, "nui-audio", `${Math.round(size / KB)} KB`);
        else if ([".ttf", ".otf", ".woff", ".woff2"].includes(ext) && size > 400 * KB) add(name, rel, 0, "nui-font", `${Math.round(size / KB)} KB`);
        else if (ext === ".map") add(name, rel, 0, "nui-sourcemap", `${Math.round(size / KB)} KB`);
    }
    const r = resources.get(name);
    if (r.frameLoops >= 3) add(name, r.dir, 0, "frame-many", `${r.frameLoops} loops`);
}

flushEvents();
const ranked = [...resources.values()].filter((r) => r.score > 0).sort((a, b) => b.score - a.score);
const byRule = findings.reduce((m, f) => ((m[f.rule] = (m[f.rule] || 0) + 1), m), {});
console.log(`perf-scan ${root}`);
console.log(`resources ${resources.size}, client Lua runtimes ${clientRuntimes}, ui_page frames ${uiPages}, protected (fxap) ${[...resources.values()].filter((r) => r.fxap).length}`);
console.log(`findings ${findings.length}: ${Object.entries(byRule).sort((a, b) => RULES[b[0]][0] - RULES[a[0]][0]).map(([k, v]) => `${k} ${v}`).join(", ")}`);
console.log(`\nTop ${top} resources by weighted score`);
for (const r of ranked.slice(0, top)) console.log(`  ${String(r.score).padStart(5)}  ${r.resource.padEnd(28)} frame-loops ${r.frameLoops}  ui ${Math.round(r.uiBytes / KB)} KB`);
console.log(`\nWorst findings (candidates: open each one, startup and rare paths are low value)`);
const seen = new Set();
for (const f of [...findings].sort((a, b) => b.weight - a.weight)) {
    const key = `${f.file}|${f.rule}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if (seen.size > top * 2) break;
    console.log(`  [${f.weight}] ${f.file}${f.line ? `:${f.line}` : ""} ${f.rule}${f.extra ? ` (${f.extra})` : ""}: ${f.message}`);
}
if (jsonOut) {
    writeFileSync(jsonOut, JSON.stringify({ root, clientRuntimes, uiPages, resources: ranked, findings }, null, 2));
    console.log(`\njson written to ${jsonOut}`);
}
