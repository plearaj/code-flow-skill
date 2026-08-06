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
