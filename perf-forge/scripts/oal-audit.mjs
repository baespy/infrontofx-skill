#!/usr/bin/env node
import { readdirSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { join, relative, basename } from "node:path";

const args = process.argv.slice(2);
const root = args.find((a) => !a.startsWith("--")) || "resources";
const jsonOut = (args.find((a) => a.startsWith("--json=")) || "").slice(7);
const only = (args.find((a) => a.startsWith("--only=")) || "").slice(7).split(",").filter(Boolean);
const SKIP = new Set(["node_modules", "_backup", "_dev", "cache", ".git", "html", "html-dev", "stream", "web", "ui", "nui"]);
const NOT_NATIVE = new Set(["CreateThread", "CreateThreadNow", "Wait", "SetTimeout", "ClearTimeout", "AddEventHandler", "RemoveEventHandler", "RegisterNetEvent", "RegisterServerEvent", "TriggerEvent", "TriggerServerEvent", "TriggerClientEvent", "TriggerLatentServerEvent", "TriggerLatentClientEvent", "RegisterCommand", "RegisterNUICallback", "RegisterNuiCallback", "SendNUIMessage", "Entity", "Player", "GetPlayers", "GetPlayerIdentifiers", "GetPlayerTokens", "PerformHttpRequest", "PerformHttpRequestAwait", "SetInterval", "ClearInterval", "Citizen", "LocalPlayer", "GlobalState", "Config", "Core", "ESX", "MySQL"]);
const VECTOR_CALL = /^(vector[234]|vec[234]?|quat|GetEntityCoords|GetOffsetFromEntityInWorldCoords|GetOffsetFromEntityGivenWorldCoords|GetGameplayCamCoords?|GetGameplayCamRot|GetFinalRenderedCamCoord|GetFinalRenderedCamRot|GetEntityRotation|GetEntityVelocity|GetEntityForwardVector|GetWorldPositionOfEntityBone|GetPedBoneCoords|GetBlipCoords|GetBlipInfoIdCoord|GetCamCoord|GetCamRot|GetEntityBonePosition_2|GetPlayerCoords|GetCoords)\s*\(/;
const VECTOR_NAME = /(^|[.\s(])(cache\.coords|[A-Za-z_]*(coords|Coords|COORDS|pos|Pos|position|Position|offset|Offset|rotation|Rotation|vec|Vec|vector|Vector|location|Location|loc|Loc|dest|Dest|center|Center|centre|origin|Origin|heading3|velocity|Velocity))\s*$/;
const DUI = /\b(CreateDui|GetDuiHandle|CreateRuntimeTextureFromDuiHandle|SendDuiMessage|DestroyDui)\b/;

function walk(dir, list = []) {
    let entries;
    try {
        entries = readdirSync(dir, { withFileTypes: true });
    } catch {
        return list;
    }
    for (const e of entries) {
        if (SKIP.has(e.name)) continue;
        const full = join(dir, e.name);
        if (e.isDirectory()) walk(full, list);
        else if (e.name.endsWith(".lua")) list.push(full);
    }
    return list;
}

function resourcesUnder(dir, list = []) {
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
    for (const e of entries) if (e.isDirectory() && !["node_modules", "_backup", "stream"].includes(e.name)) resourcesUnder(join(dir, e.name), list);
    return list;
}

function strip(text) {
    return text
        .replace(/--\[(=*)\[[\s\S]*?\]\1\]/g, (m) => m.replace(/[^\n]/g, " "))
        .replace(/\[(=*)\[[\s\S]*?\]\1\]/g, (m) => m.replace(/[^\n]/g, " "))
        .replace(/"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'/g, (m) => '"' + " ".repeat(Math.max(0, m.length - 2)) + '"')
        .replace(/--[^\n]*/g, (m) => " ".repeat(m.length));
}

function splitArgs(src, open) {
    let depth = 0;
    let cur = "";
    const out = [];
    for (let i = open + 1; i < src.length; i++) {
        const ch = src[i];
        if (ch === "(" || ch === "{" || ch === "[") depth++;
        if (ch === ")" || ch === "}" || ch === "]") {
            if (depth === 0) {
                if (cur.trim()) out.push(cur.trim());
                return { args: out, end: i };
            }
            depth--;
        }
        if (ch === "," && depth === 0) {
            out.push(cur.trim());
            cur = "";
            continue;
        }
        cur += ch;
    }
    return { args: out, end: src.length };
}

function isVectorArg(a, vars) {
    if (/\.(xy|xz|yz|xyz|xyzw|zyx|yx)\s*$/.test(a)) return true;
    if (/\.(x|y|z|w)\s*$|\[\s*[1-4]\s*\]\s*$/.test(a)) return false;
    if (VECTOR_CALL.test(a)) return true;
    const parts = a.split(/[+\-*/]/).map((p) => p.trim());
    return parts.some((p) => VECTOR_CALL.test(p) || VECTOR_NAME.test(" " + p) || vars.has(p));
}

function vectorVars(t) {
    const vars = new Set();
    for (let pass = 0; pass < 3; pass++) {
        for (const m of t.matchAll(/\b(?:local\s+)?([A-Za-z_][\w.]*)\s*=\s*([^\n]+)/g)) {
            const rhs = m[2].trim();
            if (/^[=~]/.test(rhs)) continue;
            const head = rhs.split(/\s+(?:or|and)\s+/)[0];
            if (VECTOR_CALL.test(head) || vars.has(head.replace(/[\s)]+$/, "")) || /^cache\.coords\b/.test(head)) vars.add(m[1]);
        }
    }
    return vars;
}

const targets = resourcesUnder(root).filter((d) => !only.length || only.includes(basename(d)));
const report = [];
for (const dir of targets) {
    const name = basename(dir);
    const manifest = readFileSync(join(dir, "fxmanifest.lua"), "utf8");
    const oal = /use_experimental_fxv2_oal/.test(manifest);
    const lua54 = /lua54\s*['"]yes['"]/.test(manifest);
    const fxap = existsSync(join(dir, ".fxap"));
    const files = walk(dir);
    const defined = new Set();
    const texts = files.map((f) => ({ f, t: strip(readFileSync(f, "utf8")) }));
    for (const { t } of texts) for (const m of t.matchAll(/\bfunction\s+([A-Z]\w*)\s*\(|\b([A-Z]\w*)\s*=\s*function\b|\blocal\s+function\s+([A-Z]\w*)/g)) defined.add(m[1] || m[2] || m[3]);
    const natives = new Map();
    const hazards = [];
    for (const { f, t } of texts) {
        const rel = relative(root, f).split("\\").join("/");
        const client = /(^|\/)(client|cl_)|\/cl_[^/]*$/i.test(rel) || /shared|sh_/.test(rel);
        const lines = t.split("\n");
        const lineAt = (idx) => t.slice(0, idx).split("\n").length;
        const vars = vectorVars(t);
        for (const m of t.matchAll(/(^|[^.:\w])([A-Z][A-Za-z0-9_]*)\s*\(/g)) {
            const fn = m[2];
            if (NOT_NATIVE.has(fn) || defined.has(fn) || /^[A-Z0-9_]+$/.test(fn)) continue;
            const prev = t.slice(Math.max(0, m.index - 10), m.index + m[1].length);
            if (/function\s*$/.test(prev)) continue;
            natives.set(fn, (natives.get(fn) || 0) + 1);
            const open = m.index + m[0].length - 1;
            const { args: callArgs } = splitArgs(t, open);
            const vec = callArgs.filter((a) => isVectorArg(a, vars));
            if (vec.length) hazards.push({ file: rel, line: lineAt(m.index), native: fn, kind: "vector-arg", detail: vec.join(" | ").slice(0, 120), client });
        }
        lines.forEach((l, i) => {
            const multi = /\blocal\s+[\w_]+\s*,\s*[\w_]+[\w\s,]*=\s*([A-Z][A-Za-z0-9_]*)\s*\(/.exec(l);
            if (multi && !NOT_NATIVE.has(multi[1]) && !defined.has(multi[1])) hazards.push({ file: rel, line: i + 1, native: multi[1], kind: "multi-return", detail: "out-pointer results: bools become true/false under OAL", client });
            const cmp = /\b(hit|didHit|isHit|found|exists|success|onScreen|visible|valid|retval|ok|result|blocked|collided|inside|isFound|ground|groundFound|foundGround)\s*([=~]=)\s*([01])\b/.exec(l);
            if (cmp && !/==\s*true\s+or\s+\w+\s*==\s*1|==\s*1\s+or\s+\w+\s*==\s*true/.test(l)) hazards.push({ file: rel, line: i + 1, native: cmp[1], kind: "bool-compare", detail: `${cmp[1]} ${cmp[2]} ${cmp[3]}: an out-pointer BOOL becomes true/false under OAL, test both (== true or == 1)`, client });
            if (DUI.test(l)) hazards.push({ file: rel, line: i + 1, native: DUI.exec(l)[1], kind: "dui", detail: "handle natives changed under OAL once; test DUI in game", client });
        });
    }
    const calls = [...natives.values()].reduce((s, v) => s + v, 0);
    report.push({ resource: name, dir: relative(root, dir).split("\\").join("/"), oal, lua54, fxap, natives: natives.size, calls, vector: hazards.filter((h) => h.kind === "vector-arg").length, multi: hazards.filter((h) => h.kind === "multi-return").length, boolcmp: hazards.filter((h) => h.kind === "bool-compare").length, dui: hazards.filter((h) => h.kind === "dui").length, hazards });
}

report.sort((a, b) => b.calls - a.calls);
console.log(`oal-audit ${root}: ${report.length} resources`);
console.log("resource".padEnd(30), "oal  lua54 natives calls vector multi bool dui");
for (const r of report) {
    if (r.fxap || !r.calls) continue;
    console.log(r.resource.padEnd(30), (r.oal ? "on " : "off").padEnd(4), (r.lua54 ? "yes" : "NO ").padEnd(5), String(r.natives).padStart(7), String(r.calls).padStart(5), String(r.vector).padStart(6), String(r.multi).padStart(5), String(r.boolcmp).padStart(4), String(r.dui).padStart(3));
}
if (only.length) {
    for (const r of report) for (const h of r.hazards.filter((x) => x.kind !== "multi-return")) console.log(`  [${h.kind}] ${h.file}:${h.line} ${h.native}(${h.detail})`);
}
if (jsonOut) writeFileSync(jsonOut, JSON.stringify(report, null, 2));
