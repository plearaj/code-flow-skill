import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPT = path.join(repoRoot, "scripts", "prepublish-check.js");

// The gate is only a gate if npm actually runs it. A checklist nobody is
// forced to read is the situation this script exists to replace, so the wiring
// is pinned as tightly as the behavior.
const WIRED_COMMAND = "node scripts/prepublish-check.js";

function run(env) {
  return spawnSync(process.execPath, [SCRIPT], {
    encoding: "utf8",
    // Inherit PATH etc., but control the one variable under test so a value
    // set in the developer's own shell cannot make this test lie.
    env: { ...process.env, CODE_FLOW_RELEASE_CHECKED: "", ...env },
  });
}

test("prepublish check blocks the publish when the checklist is unacknowledged", () => {
  const r = run({});
  assert.equal(r.status, 1, "an unacknowledged checklist must fail the publish");
  assert.match(r.stderr, /Publish blocked/);
  assert.match(
    r.stderr,
    /CODE_FLOW_RELEASE_CHECKED=1/,
    "the failure must say how to proceed, or it is an obstacle rather than a gate"
  );
});

test("prepublish check passes once the checklist is acknowledged", () => {
  const r = run({ CODE_FLOW_RELEASE_CHECKED: "1" });
  assert.equal(r.status, 0, `expected exit 0, got ${r.status}: ${r.stderr}`);
  assert.match(r.stdout, /checklist acknowledged/);
  assert.equal(r.stderr, "", "a passing gate must not write to stderr");
});

test("prepublish check names both scaffolds and both manual steps", () => {
  const r = run({ CODE_FLOW_RELEASE_CHECKED: "1" });
  // Named individually rather than counted: a checklist that covers one
  // scaffold and silently drops the other is the exact failure this guards.
  assert.match(r.stdout, /templates\/shared\/viewer\.template\.html/);
  assert.match(r.stdout, /templates\/shared\/report\.template\.html/);
  assert.match(r.stdout, /blank\s+page/i, "step 1 must name the failure it looks for");
  assert.match(r.stdout, /error card/i, "step 2 must name the failure it looks for");
});

test("npm runs the gate on publish, and it is runnable by hand for the PyPI release", () => {
  const pkg = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "package.json"), "utf8")
  );
  assert.equal(
    pkg.scripts.prepublishOnly,
    WIRED_COMMAND,
    "npm publish must run the gate"
  );
  assert.equal(
    pkg.scripts["release-check"],
    WIRED_COMMAND,
    "`uv publish` has no equivalent hook, so the gate must be runnable by hand"
  );
});

test("the gate ships to nobody", () => {
  const pkg = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "package.json"), "utf8")
  );
  assert.ok(
    !pkg.files.includes("scripts"),
    "scripts/ is a maintainer tool and must stay out of the published package"
  );
});
