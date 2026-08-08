#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const HELP = `code-flow-skill install helper\n\nUsage:\n  code-flow-skill [--target PATH] [--tool claude|gemini|copilot|all]\n\nDefaults:\n  --target .\n  --tool all\n`;

function parseArg(name, fallback) {
  const idx = process.argv.indexOf(name);
  if (idx === -1 || idx + 1 >= process.argv.length) {
    return fallback;
  }
  return process.argv[idx + 1];
}

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log(HELP);
  process.exit(0);
}

const target = path.resolve(process.cwd(), parseArg("--target", "."));
const tool = parseArg("--tool", "all");
const selected = tool === "all" ? ["claude", "gemini", "copilot"] : [tool];

// Both scaffolds are tool-agnostic: every command template references one of
// them, so both install regardless of --tool. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests
// in both languages are what holds them there.
const sharedFiles = [
  ["viewer.template.html", "interactive viewer"],
  ["report.template.html", "quality report viewer"],
];

function installShared() {
  for (const [name, label] of sharedFiles) {
    const src = path.join(pkgRoot, "templates", "shared", name);
    const dst = path.join(target, ".code-flow", name);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    console.log(`Installed ${label} template: ${dst}`);
  }
}

// Each host installs one file per command. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests
// in both languages are what holds them there.
const toolMap = {
  claude: [
    ["claude/code-flow.map.md", ".claude/commands/code-flow.map.md"],
    ["claude/code-flow.quality.md", ".claude/commands/code-flow.quality.md"],
  ],
  gemini: [
    ["gemini/code-flow.map.toml", ".gemini/commands/code-flow.map.toml"],
    ["gemini/code-flow.quality.toml", ".gemini/commands/code-flow.quality.toml"],
  ],
  copilot: [
    ["copilot/code-flow.map.prompt.md", ".github/prompts/code-flow.map.prompt.md"],
    ["copilot/code-flow.quality.prompt.md", ".github/prompts/code-flow.quality.prompt.md"],
  ],
};

for (const name of selected) {
  if (!Object.prototype.hasOwnProperty.call(toolMap, name)) {
    console.error(`Unknown --tool value: ${name}`);
    process.exit(1);
  }

  for (const [relSrc, relDst] of toolMap[name]) {
    const src = path.join(pkgRoot, "templates", ...relSrc.split("/"));
    const dst = path.join(target, ...relDst.split("/"));
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    console.log(`Installed ${name} template: ${dst}`);
  }
}

installShared();
