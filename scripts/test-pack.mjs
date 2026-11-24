#!/usr/bin/env node
import { readFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const failures = [];
let passed = 0;

function findBash() {
    if (process.env.BASH_PATH) {
        return process.env.BASH_PATH;
    }
    if (process.platform !== "win32") {
        return "bash";
    }
    const candidates = [
        join(process.env.ProgramFiles || "C:\\Program Files", "Git", "bin", "bash.exe"),
        join(process.env.LOCALAPPDATA || "", "Programs", "Git", "bin", "bash.exe"),
    ];
    const git = spawnSync("where", ["git"], { encoding: "utf8" });
    if (git.status === 0) {
        const first = git.stdout.split(/\r?\n/)[0].trim();
        candidates.push(join(dirname(dirname(first)), "bin", "bash.exe"));
    }
    const found = candidates.find((path) => path && existsSync(path));
    if (!found) {
        console.log("bash not found; set BASH_PATH to Git Bash");
        process.exit(2);
    }
    return found;
}

function check(name, ok, detail) {
    if (ok) {
        passed++;
    } else {
        failures.push(`${name}: ${detail}`);
    }
}

function skillsFrom(text) {
    const match = /load (.*) before acting/.exec(text);
    if (!match) {
        return [];
    }
    return match[1].split(", ").map((item) => item.replace(/ \(.*\)$/, "")).sort();
}

function runRouter(bash, payload, tmp) {
    const result = spawnSync(bash, [join(ROOT, "hooks", "skill-router.sh")], {
        input: JSON.stringify(payload),
        encoding: "utf8",
        env: { ...process.env, TMPDIR: tmp },
    });
    return result.stdout;
}

function testHooks() {
    const bash = findBash();
    const tmp = mkdtempSync(join(tmpdir(), "infrontofx-hook-"));
    const rows = readFileSync(join(ROOT, "tests", "hooks", "cases.tsv"), "utf8").replace(/\r\n/g, "\n").split("\n").filter((row) => row.length > 0);
    rows.forEach((row, index) => {
        const [prompt, expected = ""] = row.split("\t");
        const want = expected.split(",").map((item) => item.trim()).filter(Boolean).sort();
        const id = `case-${index}`;
        const claude = runRouter(bash, { session_id: id, hook_event_name: "UserPromptSubmit", prompt }, tmp);
        const got = skillsFrom(claude);
        check(`hook claude "${prompt}"`, JSON.stringify(got) === JSON.stringify(want), `want [${want}] got [${got}]`);
        if (want.length > 0) {
            let shape = false;
            try {
                shape = JSON.parse(claude).hookSpecificOutput.hookEventName === "UserPromptSubmit";
            } catch {
                shape = false;
            }
            check(`hook claude json "${prompt}"`, shape, `bad JSON: ${claude}`);
        } else {
            check(`hook claude silent "${prompt}"`, claude === "", `expected no output, got ${claude}`);
        }
        const again = runRouter(bash, { session_id: id, hook_event_name: "UserPromptSubmit", prompt }, tmp);
        check(`hook claude repeat "${prompt}"`, again === "", `repeat should print nothing, got ${again}`);
        const agy = runRouter(bash, { conversationId: id, hookEventName: "PreInvocation", invocationNum: 1, lastUserInput: prompt }, tmp);
        let agyGot = [];
        let agyShape = false;
        try {
            const parsed = JSON.parse(agy);
            if (want.length > 0) {
                const text = parsed.injectSteps[0].systemMessage.systemMessage;
                agyGot = skillsFrom(text);
                agyShape = true;
            } else {
                agyShape = Object.keys(parsed).length === 0;
            }
        } catch {
            agyShape = false;
        }
        check(`hook antigravity "${prompt}"`, agyShape && JSON.stringify(agyGot) === JSON.stringify(want), `want [${want}] got ${agy}`);
        const agyAgain = runRouter(bash, { conversationId: id, hookEventName: "PreInvocation", invocationNum: 2, lastUserInput: prompt }, tmp);
        check(`hook antigravity repeat "${prompt}"`, agyAgain === "{}", `repeat should print {}, got ${agyAgain}`);
    });
    rmSync(tmp, { recursive: true, force: true });
}

function testLint() {
    const dir = join(ROOT, "tests", "lint");
    const cases = JSON.parse(readFileSync(join(dir, "cases.json"), "utf8"));
    for (const item of cases) {
        const result = spawnSync(process.execPath, [join(ROOT, "scripts", "lint-resource.mjs"), join(dir, item.file)], { encoding: "utf8" });
        const rules = new Set([...result.stdout.matchAll(/\[(?:error|warn|info)\] ([\w-]+)/g)].map((match) => match[1]));
        for (const rule of item.expect || []) {
            check(`lint ${item.file} finds ${rule}`, rules.has(rule), `missing ${rule}; output:\n${result.stdout}`);
        }
        for (const rule of item.forbid || []) {
            check(`lint ${item.file} skips ${rule}`, !rules.has(rule), `unexpected ${rule}; output:\n${result.stdout}`);
        }
    }
    const template = spawnSync(process.execPath, [join(ROOT, "scripts", "lint-resource.mjs"), join(ROOT, "templates", "resource")], { encoding: "utf8" });
    check("lint template has no errors", template.status === 0, template.stdout);
}

testHooks();
testLint();
for (const failure of failures) {
    console.log(`FAIL ${failure}`);
}
console.log(`\n${passed} passed, ${failures.length} failed`);
process.exit(failures.length > 0 ? 1 : 0);
