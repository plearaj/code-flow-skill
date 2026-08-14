import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const installer = path.join(repoRoot, "bin", "install.js");

export function runInstaller(target, tool = "all") {
  execFileSync(process.execPath, [installer, "--target", target, "--tool", tool], {
    stdio: "pipe",
  });
}

export function tempTarget() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "code-flow-test-"));
}

// The exact set `--tool all` must produce — nothing missing, nothing extra.
// Both installers (this one and src/code_flow_skill/cli.py) are asserted
// against the same literal list, which is what keeps them in lockstep.
const EXPECTED_ALL = [
  ".claude/commands/code-flow.map.md",
  ".claude/commands/code-flow.quality.md",
  ".code-flow/index.template.html",
  ".code-flow/report.template.html",
  ".code-flow/viewer.template.html",
  ".gemini/commands/code-flow.map.toml",
  ".gemini/commands/code-flow.quality.toml",
  ".github/prompts/code-flow.map.prompt.md",
  ".github/prompts/code-flow.quality.prompt.md",
];

// Hand-rolled walk rather than readdirSync({ recursive: true }): that option
// landed in Node 18.17 and its Dirent.parentPath in 20.12, both above this
// package's declared engines floor of ">=18". Rather than narrow what we
// support in order to write a test, walk with APIs that have always been there.
function installedPaths(root, prefix = "") {
  return fs
    .readdirSync(path.join(root, prefix), { withFileTypes: true })
    .flatMap((entry) => {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      return entry.isDirectory() ? installedPaths(root, rel) : [rel];
    })
    .sort();
}

test("--tool all installs exactly the expected file set", () => {
  const target = tempTarget();
  runInstaller(target, "all");
  assert.deepEqual(installedPaths(target), EXPECTED_ALL);
});

test("installs the viewer scaffold", () => {
  const target = tempTarget();
  runInstaller(target);
  const viewer = path.join(target, ".code-flow", "viewer.template.html");
  assert.ok(fs.existsSync(viewer));
  assert.match(fs.readFileSync(viewer, "utf8"), /__FLOW_DATA__/);
});

test("tool selection installs only that tool", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  assert.ok(!fs.existsSync(path.join(target, ".claude")));
  assert.ok(fs.existsSync(path.join(target, ".gemini")));
});

test("installs the claude map command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "claude");
  const commands = path.join(target, ".claude", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.map.md")));
  assert.ok(!fs.existsSync(path.join(commands, "code-flow.md")));
});

test("installs the gemini map command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  const commands = path.join(target, ".gemini", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.map.toml")));
  assert.ok(!fs.existsSync(path.join(commands, "code-flow.toml")));
});

test("installs the copilot prompt file", () => {
  const target = tempTarget();
  runInstaller(target, "copilot");
  const prompt = path.join(target, ".github", "prompts", "code-flow.map.prompt.md");
  assert.ok(fs.existsSync(prompt));
});

test("copilot install leaves copilot-instructions.md untouched", () => {
  const target = tempTarget();
  const instructions = path.join(target, ".github", "copilot-instructions.md");
  fs.mkdirSync(path.dirname(instructions), { recursive: true });
  fs.writeFileSync(instructions, "# My own notes\n", "utf8");

  runInstaller(target, "copilot");

  assert.equal(fs.readFileSync(instructions, "utf8"), "# My own notes\n");
});

test("installs the claude quality command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "claude");
  const commands = path.join(target, ".claude", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.quality.md")));
  assert.ok(!fs.existsSync(path.join(commands, "code-flow.md")));
});

test("installs the gemini quality command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  const commands = path.join(target, ".gemini", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.quality.toml")));
});

test("selecting one tool installs both of its commands and neither of another's", () => {
  const target = tempTarget();
  runInstaller(target, "copilot");
  const prompts = path.join(target, ".github", "prompts");
  assert.ok(fs.existsSync(path.join(prompts, "code-flow.map.prompt.md")));
  assert.ok(fs.existsSync(path.join(prompts, "code-flow.quality.prompt.md")));
  assert.ok(!fs.existsSync(path.join(target, ".claude")));
  assert.ok(!fs.existsSync(path.join(target, ".gemini")));
});
