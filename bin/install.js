#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const HELP = `code-flow-skill install helper\n\nUsage:\n  code-flow-skill [--target PATH] [--tool claude|copilot|codex|antigravity|gemini|all]\n\nDefaults:\n  --target .\n  --tool all\n`;

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

// Every value --tool accepts. Not the same thing as `toolMap` below: a host
// can be selectable without having files of its own. Copilot, Codex and
// Antigravity read `.agents/skills/` and nothing this installer writes
// elsewhere, so they appear here and not there.
const VALID_TOOLS = ["claude", "copilot", "codex", "antigravity", "gemini"];

// The hosts that read `.agents/skills/`. Claude Code is deliberately absent:
// its documented skill locations are `~/.claude/skills/`, `.claude/skills/`
// and plugin directories, with no `.agents/` among them, so a Claude-only
// install that wrote there would leave four files nothing reads.
const AGENTS_HOSTS = ["copilot", "codex", "antigravity", "gemini"];

// `--tool gemini` is an explicit request and always installs. A heuristic must
// never overrule someone who said exactly what they wanted.
const explicit = tool !== "all";
let skippedGemini = false;
let selected;
if (explicit) {
  selected = [tool];
} else if (geminiIsInUse(target)) {
  // Every valid tool. Derived from VALID_TOOLS rather than hand-typed: codex
  // and antigravity own no files of their own (see toolMap below), so a
  // second hardcoded list here would be a literal that nothing observable —
  // not the installed files, not stdout — could distinguish from
  // `["claude", "copilot"]`. Deriving from VALID_TOOLS closes that gap by
  // construction instead of relying on an assertion to catch it.
  selected = [...VALID_TOOLS];
} else {
  // Every valid tool except gemini, for the same reason.
  selected = VALID_TOOLS.filter((name) => name !== "gemini");
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

// One canonical SKILL.md per command, copied unchanged to every directory a
// host discovers skills from.
//
// `.agents/skills/` is the open standard's shared location — Copilot, both
// Antigravity surfaces, OpenAI Codex and the legacy Gemini CLI all read it — so
// it installs regardless of --tool, the way the .code-flow/ scaffolds do. It is
// also the entirety of Codex support: Codex discovers repository skills from
// $CWD/.agents/skills and $REPO_ROOT/.agents/skills and has no --tool value of
// its own. `.claude/skills/` has exactly one consumer no other path serves,
// Claude Code, so it rides on that selection instead; a `--tool gemini` install
// must still leave no `.claude/` behind. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests in
// both languages hold them there.
const skillNames = ["code-flow-map", "code-flow-quality"];

// What one installed skill is made of, per destination. SKILL.md goes to every
// discovery root. `agents/openai.yaml` carries the implicit-invocation policy
// for Codex alone, and Codex reads only `.agents/skills/`, so shipping it under
// `.claude/skills/` would be a file no host there reads — Claude Code and
// Copilot both take that policy from SKILL.md's frontmatter instead.
const SKILL_FILES = ["SKILL.md"];
const AGENTS_SKILL_FILES = ["SKILL.md", "agents/openai.yaml"];

function installSkills(root, files) {
  for (const name of skillNames) {
    for (const rel of files) {
      const src = path.join(pkgRoot, "templates", "shared", name, ...rel.split("/"));
      const dst = path.join(target, root, "skills", name, ...rel.split("/"));
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.copyFileSync(src, dst);
      console.log(`Installed skill file: ${dst}`);
    }
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
  if (!VALID_TOOLS.includes(name)) {
    console.error(`Unknown --tool value: ${name}`);
    process.exit(1);
  }

  // A host with no table entry is served entirely by `.agents/skills/`.
  if (!Object.prototype.hasOwnProperty.call(toolMap, name)) {
    continue;
  }

  for (const [relSrc, relDst] of toolMap[name]) {
    const src = path.join(pkgRoot, "templates", ...relSrc.split("/"));
    const dst = path.join(target, ...relDst.split("/"));
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    console.log(`Installed ${name} template: ${dst}`);
  }
}

if (selected.includes("claude")) {
  installSkills(".claude", SKILL_FILES);
}
if (selected.some((name) => AGENTS_HOSTS.includes(name))) {
  installSkills(".agents", AGENTS_SKILL_FILES);
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
