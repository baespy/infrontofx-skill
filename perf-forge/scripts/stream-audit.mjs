#!/usr/bin/env node
import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, basename, extname, dirname, resolve } from "node:path";
import { inflateRawSync } from "node:zlib";
import { createHash } from "node:crypto";

const args = process.argv.slice(2);
const root = args.find((a) => !a.startsWith("--")) || "resources";
const jsonOut = (args.find((a) => a.startsWith("--json=")) || "").slice(7);
const top = Number((args.find((a) => a.startsWith("--top=")) || "--top=25").slice(6));
const MIB = 1024 * 1024;
const STREAM_EXT = new Set([".ytd", ".ydr", ".yft", ".ydd", ".ybn", ".ymap", ".ytyp", ".ycd", ".ypt", ".awc"]);
const SKIP = new Set(["node_modules", "_backup", "_dev", "cache", ".git", "html-dev"]);

const FORMATS = {
    0x31545844: ["DXT1", 0.5],
    0x33545844: ["DXT3", 1],
    0x35545844: ["DXT5", 1],
    0x31495441: ["ATI1", 0.5],
    0x32495441: ["ATI2", 1],
    0x20374342: ["BC7", 1],
    0x20354342: ["BC5", 1],
    0x20344342: ["BC4", 0.5],
    0x20364342: ["BC6", 1],
    21: ["A8R8G8B8", 4],
    22: ["X8R8G8B8", 4],
    32: ["A8B8G8R8", 4],
    25: ["A1R5G5B5", 2],
    23: ["R5G6B5", 2],
    28: ["A8", 1],
    50: ["L8", 1],
    113: ["A16B16G16R16F", 8],
    116: ["A32B32G32R32F", 16],
    114: ["R32F", 4],
};

function pageSize(flags) {
    const s0 = ((flags >>> 27) & 0x1) << 0;
    const s1 = ((flags >>> 26) & 0x1) << 1;
    const s2 = ((flags >>> 25) & 0x1) << 2;
    const s3 = ((flags >>> 24) & 0x1) << 3;
    const s4 = ((flags >>> 17) & 0x7f) << 4;
    const s5 = ((flags >>> 11) & 0x3f) << 5;
    const s6 = ((flags >>> 7) & 0xf) << 6;
    const s7 = ((flags >>> 5) & 0x3) << 7;
    const s8 = ((flags >>> 4) & 0x1) << 8;
    const base = 0x200 << (flags & 0xf);
    return base * (s0 + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8);
}

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
        else if (STREAM_EXT.has(extname(e.name).toLowerCase())) list.push(full);
    }
    return list;
}

const owners = new Map();
function resourceOf(path) {
    const top = resolve(root);
    let d = dirname(resolve(path));
    const seen = [];
    let found = null;
    while (d.length >= top.length) {
        if (owners.has(d)) {
            found = owners.get(d);
            break;
        }
        seen.push(d);
        if (existsSync(join(d, "fxmanifest.lua")) || existsSync(join(d, "__resource.lua"))) {
            found = basename(d);
            break;
        }
        const up = dirname(d);
        if (up === d) break;
        d = up;
    }
    const r = found || basename(dirname(path));
    for (const x of seen) owners.set(x, r);
    return r;
}

function isPow2(n) {
    return n > 0 && (n & (n - 1)) === 0;
}

function textureBytes(w, h, levels, bpp, block) {
    let total = 0;
    let cw = w;
    let ch = h;
    for (let i = 0; i < Math.max(1, levels); i++) {
        const bw = block ? Math.max(4, Math.ceil(cw / 4) * 4) : cw;
        const bh = block ? Math.max(4, Math.ceil(ch / 4) * 4) : ch;
        total += bw * bh * bpp;
        cw = Math.max(1, cw >> 1);
        ch = Math.max(1, ch >> 1);
    }
    return total;
}

function parseYtd(data, sysSize) {
    const ptr = (p) => {
        const hi = Number(p >> 28n);
        const off = Number(p & 0x0fffffffn);
        if (hi === 5) return off;
        if (hi === 6) return sysSize + off;
        return -1;
    };
    const cstr = (off) => {
        if (off < 0 || off >= data.length) return "?";
        let end = off;
        while (end < data.length && data[end] !== 0 && end - off < 128) end++;
        return data.toString("latin1", off, end);
    };
    if (data.length < 0x40) return null;
    const count = data.readUInt16LE(0x38);
    if (count === 0) return [];
    const listPtr = ptr(data.readBigUInt64LE(0x30));
    if (listPtr < 0 || count > 4096 || listPtr + count * 8 > data.length) return null;
    const textures = [];
    for (let i = 0; i < count; i++) {
        const t = ptr(data.readBigUInt64LE(listPtr + i * 8));
        if (t < 0 || t + 0x90 > data.length) continue;
        const name = cstr(ptr(data.readBigUInt64LE(t + 0x28)));
        const width = data.readUInt16LE(t + 0x50);
        const height = data.readUInt16LE(t + 0x52);
        const fmtCode = data.readUInt32LE(t + 0x58);
        const levels = data.readUInt8(t + 0x5d);
        const [format, bpp] = FORMATS[fmtCode] || [`0x${fmtCode.toString(16)}`, 4];
        const block = /^(DXT|ATI|BC)/.test(format);
        textures.push({ name, width, height, format, levels, bytes: textureBytes(width, height, levels, bpp, block), compressed: block });
    }
    return textures;
}

const files = walk(root);
const assets = [];
const byName = new Map();
const byHash = new Map();
const issues = [];

for (const file of files) {
    const buf = readFileSync(file);
    const rel = relative(root, file).split("\\").join("/");
    const res = resourceOf(file);
    const ext = extname(file).toLowerCase();
    const name = basename(file).toLowerCase();
    const hash = createHash("sha1").update(buf).digest("hex");
    const asset = { file: rel, resource: res, ext, disk: buf.length, physical: 0, virtual: 0, textures: null, escrow: false };
    if (buf.length >= 4 && buf.readUInt32LE(0) === 0x50415846) {
        asset.escrow = true;
        if (buf.length > 8 * MIB) issues.push({ sev: 2, file: rel, why: `escrowed (FXAP) ${(buf.length / MIB).toFixed(1)} MiB on disk, real memory unknown` });
    }
    if (buf.length >= 16 && buf.readUInt32LE(0) === 0x37435352) {
        asset.virtual = pageSize(buf.readUInt32LE(8));
        asset.physical = pageSize(buf.readUInt32LE(12));
        if (ext === ".ytd") {
            try {
                const data = inflateRawSync(buf.subarray(16));
                asset.textures = parseYtd(data, asset.virtual);
            } catch {
                asset.textures = null;
            }
        }
    }
    assets.push(asset);
    if (!byName.has(name)) byName.set(name, []);
    byName.get(name).push(asset);
    if (!byHash.has(hash)) byHash.set(hash, []);
    byHash.get(hash).push(asset);

    const mem = asset.physical + asset.virtual;
    if (asset.physical > 16 * MIB || asset.virtual > 16 * MIB) issues.push({ sev: 3, file: rel, why: `oversized: physical ${(asset.physical / MIB).toFixed(1)} MiB, virtual ${(asset.virtual / MIB).toFixed(1)} MiB` });
    else if (mem >= 8 * MIB) issues.push({ sev: 2, file: rel, why: `heavy: ${(mem / MIB).toFixed(1)} MiB in memory` });
    for (const t of asset.textures || []) {
        const tag = `${t.name} ${t.width}x${t.height} ${t.format} mips=${t.levels}`;
        if (Math.max(t.width, t.height) >= 4096) issues.push({ sev: 3, file: rel, why: `4K texture ${tag}` });
        else if (Math.max(t.width, t.height) >= 2048 && !t.compressed) issues.push({ sev: 3, file: rel, why: `2K uncompressed ${tag}` });
        else if (!t.compressed && Math.max(t.width, t.height) >= 512) issues.push({ sev: 2, file: rel, why: `uncompressed ${tag}` });
        if (t.levels <= 1 && Math.max(t.width, t.height) >= 256) issues.push({ sev: 1, file: rel, why: `no mipmaps ${tag}` });
        if (!isPow2(t.width) || !isPow2(t.height)) issues.push({ sev: 1, file: rel, why: `non power of two ${tag}` });
    }
}

const nameClashes = [...byName.entries()].filter(([, list]) => list.length > 1 && new Set(list.map((a) => a.file)).size > 1);
const crossNames = nameClashes.filter(([, l]) => new Set(l.map((a) => a.resource)).size > 1);
const sameBytes = [...byHash.values()].filter((list) => list.length > 1);
const crossBytes = sameBytes.filter((l) => new Set(l.map((a) => a.resource)).size > 1);
const perResource = new Map();
for (const a of assets) {
    const r = perResource.get(a.resource) || { resource: a.resource, files: 0, disk: 0, memory: 0 };
    r.files++;
    r.disk += a.disk;
    r.memory += a.physical + a.virtual;
    perResource.set(a.resource, r);
}

const mb = (n) => (n / MIB).toFixed(1);
const totalDisk = assets.reduce((s, a) => s + a.disk, 0);
const totalMem = assets.reduce((s, a) => s + a.physical + a.virtual, 0);
const texCount = assets.reduce((s, a) => s + (a.textures ? a.textures.length : 0), 0);
const unparsed = assets.filter((a) => a.ext === ".ytd" && a.textures === null && !a.escrow).length;
const escrowed = assets.filter((a) => a.escrow);
console.log(`stream-audit ${root}`);
console.log(`files ${assets.length}, disk ${mb(totalDisk)} MiB, memory if all resident ${mb(totalMem)} MiB, ytd textures ${texCount}, ytd unparsed ${unparsed}`);
console.log(`escrowed (FXAP, memory unknown, not counted) ${escrowed.length} files, disk ${mb(escrowed.reduce((t, a) => t + a.disk, 0))} MiB`);
console.log(`\nTop ${top} resources by streamed memory`);
for (const r of [...perResource.values()].sort((a, b) => b.memory - a.memory).slice(0, top)) console.log(`  ${mb(r.memory).padStart(8)} MiB  ${String(r.files).padStart(4)} files  ${r.resource}`);
console.log(`\nTop ${top} assets by memory`);
for (const a of [...assets].sort((x, y) => y.physical + y.virtual - (x.physical + x.virtual)).slice(0, top)) console.log(`  ${mb(a.physical + a.virtual).padStart(8)} MiB  ${a.file}`);
const sevName = ["", "low", "mid", "HIGH"];
const counted = issues.reduce((m, i) => ((m[i.sev] = (m[i.sev] || 0) + 1), m), {});
console.log(`\nIssues HIGH ${counted[3] || 0}, mid ${counted[2] || 0}, low ${counted[1] || 0}`);
for (const i of issues.sort((a, b) => b.sev - a.sev).slice(0, top * 2)) console.log(`  [${sevName[i.sev]}] ${i.file}: ${i.why}`);
console.log(`\nSame file name streamed twice (only one copy wins): ${crossNames.length} across resources, ${nameClashes.length - crossNames.length} inside one resource`);
for (const [name, list] of crossNames.slice(0, top)) console.log(`  ${name}: ${list.map((a) => a.resource).join(", ")}`);
const extra = (groups) => groups.reduce((s, list) => s + list.slice(1).reduce((t, a) => t + a.disk, 0), 0);
console.log(`\nByte-identical files under different paths: ${sameBytes.length} groups (${mb(extra(sameBytes))} MiB extra on disk), across resources ${crossBytes.length} groups (${mb(extra(crossBytes))} MiB); each name can be resident separately`);
for (const list of crossBytes.slice(0, top)) console.log(`  ${list.map((a) => a.file).join("  ==  ")}`);
if (jsonOut) {
    writeFileSync(jsonOut, JSON.stringify({ root, totalDisk, totalMem, issues, nameClashes: nameClashes.map(([n, l]) => ({ name: n, files: l.map((a) => a.file), resources: l.map((a) => a.resource) })), sameBytes: sameBytes.map((l) => l.map((a) => a.file)), escrowed: escrowed.map((a) => ({ file: a.file, disk: a.disk })), perResource: [...perResource.values()] }, null, 2));
    console.log(`\njson written to ${jsonOut}`);
}
