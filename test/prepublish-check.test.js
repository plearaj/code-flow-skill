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
  // The scaffold count lives in two places: the checklist on stdout and this
  // last instruction on stderr. Only the first was pinned, so when the bundle
  // made it four the blocked message kept telling people to open three — the
  // very last thing they read before publishing. The QA scaffold made it five,
  // and this is what kept the two in step that time.
  assert.doesNotMatch(
    r.stderr,
    /all (three|four) pages/i,
    "the blocked message names a stale scaffold count"
  );
  assert.match(r.stderr, /all five pages/i, "the blocked message must name all five scaffolds");
});

test("prepublish check passes once the checklist is acknowledged", () => {
  const r = run({ CODE_FLOW_RELEASE_CHECKED: "1" });
  assert.equal(r.status, 0, `expected exit 0, got ${r.status}: ${r.stderr}`);
  assert.match(r.stdout, /checklist acknowledged/);
  assert.equal(r.stderr, "", "a passing gate must not write to stderr");
});

test("prepublish check names every scaffold and every manual step", () => {
  const r = run({ CODE_FLOW_RELEASE_CHECKED: "1" });
  // Named individually rather than counted: a checklist that covers one
  // scaffold and silently drops another is the exact failure this guards.
  assert.match(r.stdout, /templates\/shared\/viewer\.template\.html/);
  assert.match(r.stdout, /templates\/shared\/report\.template\.html/);
  assert.match(r.stdout, /templates\/shared\/index\.template\.html/);
  assert.match(r.stdout, /blank\s+page/i, "step 1 must name the failure it looks for");
  assert.match(r.stdout, /error card/i, "step 2 must name the failure it looks for");
  // The pages are generated separately and joined only by href. Nothing in
  // either suite loads one page and follows a link to the next, so if the
  // checklist stops asking a human to walk it, nothing checks it at all.
  assert.match(r.stdout, /Flows link/i, "step 3 must name the round trip between pages");
  assert.match(r.stdout, /slash menu/i, "checklist does not cover skill loading");
  assert.match(r.stdout, /rather than\s+twice/i, "checklist does not cover duplicate registration");
  assert.match(r.stdout, /Copilot CLI/i, "checklist does not distinguish the two Copilot surfaces");
  assert.match(r.stdout, /bundle\.template\.html/, "checklist does not name the bundle scaffold");
  assert.match(r.stdout, /qa\.template\.html/, "checklist does not name the QA scaffold");
  assert.match(r.stdout, /theme\.css/, "checklist does not cover a themed render");
  assert.match(r.stdout, /ALL FIVE/i, "checklist names a stale scaffold count");
});

test("README's Before-publishing scaffold list matches the script's SCAFFOLDS", () => {
  // The README carries a hand-written prose mirror of this script's checklist
  // (see "## Publishing" > "### Before publishing"). Nothing ties the two
  // together, which is exactly how that prose fell behind when the bundle
  // scaffold was added: `SCAFFOLDS` grew to four paths and the README kept
  // naming three. Parsed as text, not imported — importing the script would
  // run its top-level checklist print (and a possible process.exit) as a
  // side effect of loading the test file.
  const scriptSource = fs.readFileSync(SCRIPT, "utf8");
  const scaffoldsMatch = scriptSource.match(/const SCAFFOLDS = \[([\s\S]*?)\];/);
  assert.ok(scaffoldsMatch, "could not find the SCAFFOLDS array in prepublish-check.js");
  const scaffolds = [...scaffoldsMatch[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(scaffolds.length > 0, "parsed zero scaffold paths out of SCAFFOLDS");

  const readme = fs.readFileSync(path.join(repoRoot, "README.md"), "utf8");
  const sectionStart = readme.indexOf("### Before publishing");
  const sectionEnd = readme.indexOf("\n## ", sectionStart);
  assert.ok(sectionStart !== -1, "README.md has no '### Before publishing' section");
  const section = readme.slice(sectionStart, sectionEnd === -1 ? undefined : sectionEnd);

  for (const scaffold of scaffolds) {
    assert.ok(
      section.includes(scaffold),
      `README's "Before publishing" section does not name ${scaffold}, but ` +
        `prepublish-check.js's SCAFFOLDS does`
    );
  }
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
