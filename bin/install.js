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

// Gemini CLI stopped serving free, Pro, Ultra and individual Code Assist users
// on 2026-06-18. Its successor, Antigravity, does not read `.gemini/commands/`
// at all — it reads the same skill paths the other hosts do. The TOML commands
// still matter to Gemini Code Assist Standard/Enterprise licence holders and to
// paid API-key users, so they still ship; installing them into every project
// would just leave a dead directory in the overwhelming majority of them.
//
// The signal is the *target's own* `.gemini/` directory. Both Antigravity
// surfaces keep their workspace files under `.agents/`, and their globals under
// `~/.gemini/antigravity/` and `~/.gemini/antigravity-cli/` — so a
// project-level `.gemini/` is specific to Gemini CLI in a way that `~/.gemini/`
// is emphatically not. Checking the home directory would misfire on every
// Antigravity user.
function geminiIsInUse(dir) {
  return fs.existsSync(path.join(dir, ".gemini"));
}

// `--tool gemini` is an explicit request and always installs. A heuristic must
// never overrule someone who said exactly what they wanted.
const explicit = tool !== "all";
let skippedGemini = false;
let selected;
if (explicit) {
  selected = [tool];
} else if (geminiIsInUse(target)) {
  selected = ["claude", "gemini", "copilot"];
} else {
  selected = ["claude", "copilot"];
  skippedGemini = true;
}

// Both scaffolds are tool-agnostic: every command template references one of
// them, so both install regardless of --tool. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests
// in both languages are what holds them there.
const sharedFiles = [
  ["viewer.template.html", "interactive viewer"],
  ["report.template.html", "quality report viewer"],
  ["index.template.html", "flow index"],
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

if (skippedGemini) {
  // Say what was skipped and how to get it. A silent omission would look
  // identical to a broken install to anyone who does use Gemini CLI.
  console.log(
    `\nSkipped the Gemini CLI templates: no .gemini/ directory in ${target}.\n` +
      `Gemini CLI was retired for individual users on 2026-06-18, and Antigravity\n` +
      `reads the same skill paths as the other hosts. If you use Gemini CLI on a\n` +
      `Code Assist Standard or Enterprise licence, install them with:\n\n` +
      `  npx @htst/code-flow-skill --tool gemini\n`,
  );
}

installShared();
