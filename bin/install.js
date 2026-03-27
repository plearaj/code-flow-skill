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

const toolMap = {
  claude: {
    src: path.join(pkgRoot, "templates", "claude", "code-flow.md"),
    dst: path.join(target, ".claude", "commands", "code-flow.md"),
  },
  gemini: {
    src: path.join(pkgRoot, "templates", "gemini", "code-flow.toml"),
    dst: path.join(target, ".gemini", "commands", "code-flow.toml"),
  },
};

for (const name of selected) {
  if (!["claude", "gemini", "copilot"].includes(name)) {
    console.error(`Unknown --tool value: ${name}`);
    process.exit(1);
  }

  if (name === "copilot") {
    const snippetPath = path.join(pkgRoot, "templates", "copilot", "code-flow.instructions.md");
    const snippet = fs.readFileSync(snippetPath, "utf8");
    const outFile = path.join(target, ".github", "copilot-instructions.md");
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    const existing = fs.existsSync(outFile) ? fs.readFileSync(outFile, "utf8") : "";
    if (!existing.includes("## Code Flow — Documentation Generator")) {
      const merged = existing.trim() ? `${existing.trim()}\n\n${snippet.trim()}\n` : `${snippet.trim()}\n`;
      fs.writeFileSync(outFile, merged, "utf8");
      console.log(`Appended Copilot Code Flow instructions: ${outFile}`);
    } else {
      console.log(`Copilot Code Flow instructions already present: ${outFile}`);
    }
    continue;
  }

  const { src, dst } = toolMap[name];
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  console.log(`Installed ${name} template: ${dst}`);
}
