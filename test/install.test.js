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
  return execFileSync(
    process.execPath,
    [installer, "--target", target, "--tool", tool],
    { stdio: "pipe" }
  ).toString();
}

export function tempTarget() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "code-flow-test-"));
}

// Every path this installer can write — nothing missing, nothing extra. Both
// installers (this one and src/code_flow_skill/cli.py) are asserted against the
// same literal list, which is what keeps them in lockstep.
const SHARED = [
  ".code-flow/bundle.template.html",
  ".code-flow/index.template.html",
  ".code-flow/report.template.html",
  ".code-flow/theme.css",
  ".code-flow/tracers/README.md",
  ".code-flow/tracers/_common.py",
  ".code-flow/tracers/trace_c_family.py",
  ".code-flow/tracers/trace_java.py",
  ".code-flow/tracers/trace_python.py",
  ".code-flow/tracers/trace_rust.py",
  ".code-flow/tracers/trace_typescript.mjs",
  ".code-flow/viewer.template.html",
];
const CLAUDE = [
  ".claude/commands/code-flow.map.md",
  ".claude/commands/code-flow.quality.md",
  ".claude/skills/code-flow-map/SKILL.md",
  ".claude/skills/code-flow-quality/SKILL.md",
];
const AGENTS = [
  ".agents/skills/code-flow-map/SKILL.md",
  ".agents/skills/code-flow-map/agents/openai.yaml",
  ".agents/skills/code-flow-quality/SKILL.md",
  ".agents/skills/code-flow-quality/agents/openai.yaml",
];
const GEMINI = [
  ".gemini/commands/code-flow.map.toml",
  ".gemini/commands/code-flow.quality.toml",
];
const COPILOT = [
  ".github/prompts/code-flow.map.prompt.md",
  ".github/prompts/code-flow.quality.prompt.md",
];

// One row per --tool value. This is the contract the two installers are held
// to, and the identical table lives in tests/test_installer_python.py.
const EXPECTED_BY_TOOL = {
  claude: [...CLAUDE, ...SHARED].sort(),
  copilot: [...AGENTS, ...COPILOT, ...SHARED].sort(),
  codex: [...AGENTS, ...SHARED].sort(),
  antigravity: [...AGENTS, ...SHARED].sort(),
  gemini: [...AGENTS, ...GEMINI, ...SHARED].sort(),
};

const EXPECTED_ALL = [...CLAUDE, ...AGENTS, ...GEMINI, ...COPILOT, ...SHARED].sort();
const EXPECTED_WITHOUT_GEMINI = EXPECTED_ALL.filter((p) => !p.startsWith(".gemini/"));

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

// Gemini CLI was retired for individual users on 2026-06-18 and Antigravity
// does not read `.gemini/commands/`, so writing those two files into every
// project would leave a dead directory in almost all of them. The licence
// remnant is real, though, so a project already using Gemini CLI still gets
// them without anyone passing a flag.
test("--tool all skips gemini when the project shows no sign of it", () => {
  const target = tempTarget();
  runInstaller(target, "all");
  assert.deepEqual(installedPaths(target), EXPECTED_WITHOUT_GEMINI);
});

test("--tool all installs gemini when the project already uses it", () => {
  const target = tempTarget();
  fs.mkdirSync(path.join(target, ".gemini"));
  runInstaller(target, "all");
  assert.deepEqual(installedPaths(target), EXPECTED_ALL);
});

test("explicit --tool gemini overrules the heuristic", () => {
  // A detector that can silently overrule an explicit request is worse than no
  // detector: it leaves someone who said exactly what they wanted with nothing.
  const target = tempTarget();
  runInstaller(target, "gemini");
  const commands = path.join(target, ".gemini", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.map.toml")));
  assert.ok(fs.existsSync(path.join(commands, "code-flow.quality.toml")));
});

test("skipping gemini says so, and says how to get it", () => {
  // A silent omission is indistinguishable from a broken install.
  const target = tempTarget();
  const out = runInstaller(target, "all");
  assert.match(out, /Skipped the Gemini CLI templates/);
  assert.match(out, /--tool gemini/);
});

test("no skip notice when gemini is actually installed", () => {
  // The inverse: a notice that always printed would satisfy the test above
  // while telling Gemini users their templates were skipped when they weren't.
  const target = tempTarget();
  fs.mkdirSync(path.join(target, ".gemini"));
  const out = runInstaller(target, "all");
  assert.doesNotMatch(out, /Skipped/);
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

test("agent skills install for a host that reads them", () => {
  // `.agents/skills/` is the open standard's shared location — Copilot, both
  // Antigravity surfaces, Codex and the legacy Gemini CLI all read it.
  // Copilot reads it in addition to its own prompt files, so selecting it
  // must still install `.agents/skills/` alongside them.
  const target = tempTarget();
  runInstaller(target, "copilot");
  for (const name of ["code-flow-map", "code-flow-quality"]) {
    assert.ok(
      fs.existsSync(path.join(target, ".agents", "skills", name, "SKILL.md")),
      `.agents/skills/${name}/SKILL.md was not installed`,
    );
  }
});

test("claude skills ride on the claude selection", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  assert.ok(fs.existsSync(path.join(target, ".agents", "skills", "code-flow-map", "SKILL.md")));
  assert.ok(!fs.existsSync(path.join(target, ".claude")));
});

test("the claude selection installs only the claude skill root", () => {
  // Claude Code does not read `.agents/skills/` — its documented skill
  // locations are `~/.claude/skills/`, `.claude/skills/` and plugin
  // directories — so `--tool claude` must not write it.
  const target = tempTarget();
  runInstaller(target, "claude");
  for (const name of ["code-flow-map", "code-flow-quality"]) {
    assert.ok(
      fs.existsSync(path.join(target, ".claude", "skills", name, "SKILL.md")),
      `.claude/skills/${name}/SKILL.md was not installed`,
    );
  }
  assert.ok(!fs.existsSync(path.join(target, ".agents")));
});

test("installed skills are byte-identical to their template", () => {
  const target = tempTarget();
  // .gemini/ makes `--tool all` take the Gemini branch, so the install under
  // test is the full one rather than the reduced set.
  fs.mkdirSync(path.join(target, ".gemini"), { recursive: true });
  runInstaller(target, "all");

  for (const name of ["code-flow-map", "code-flow-quality"]) {
    const source = fs.readFileSync(
      path.join(repoRoot, "templates", "shared", name, "SKILL.md"),
    );
    for (const root of [".claude", ".agents"]) {
      const installed = fs.readFileSync(path.join(target, root, "skills", name, "SKILL.md"));
      assert.deepEqual(
        installed,
        source,
        `${root}/skills/${name}/SKILL.md is not byte-identical to its template`,
      );
    }

    // Codex's policy file, which exists under .agents/ only.
    assert.deepEqual(
      fs.readFileSync(path.join(target, ".agents", "skills", name, "agents", "openai.yaml")),
      fs.readFileSync(path.join(repoRoot, "templates", "shared", name, "agents", "openai.yaml")),
      `.agents/skills/${name}/agents/openai.yaml is not byte-identical to its template`,
    );
    assert.ok(
      !fs.existsSync(path.join(target, ".claude", "skills", name, "agents")),
      `${name}'s Codex policy file must not be installed under .claude/skills/, ` +
        `which Codex never reads`,
    );
  }
});

for (const tool of Object.keys(EXPECTED_BY_TOOL).sort()) {
  test(`--tool ${tool} installs exactly its own set`, () => {
    const target = tempTarget();
    runInstaller(target, tool);
    assert.deepEqual(installedPaths(target), EXPECTED_BY_TOOL[tool]);
  });
}
