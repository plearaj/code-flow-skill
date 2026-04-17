#!/usr/bin/env node
/**
 * postinstall hook — copies Code Flow templates into the consuming project.
 *
 * Skipped when:
 *   - npm_config_code_flow_skip_install is set (npm i --code_flow_skip_install)
 *   - CODE_FLOW_SKIP_INSTALL env var is set
 *   - running in a global install (npm i -g)
 *   - no INIT_CWD (not triggered by a consumer install)
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const skip =
  process.env.npm_config_code_flow_skip_install ||
  process.env.CODE_FLOW_SKIP_INSTALL;

if (skip) {
  console.log("code-flow-skill: skipping auto-install (skip flag set)");
  process.exit(0);
}

// npm sets npm_config_global when running a global install
if (process.env.npm_config_global === "true") {
  console.log("code-flow-skill: global install detected — run `code-flow-skill` manually in your project");
  process.exit(0);
}

// INIT_CWD is the directory where the user ran `npm install`
const target = process.env.INIT_CWD;
if (!target) {
  console.log("code-flow-skill: no INIT_CWD — skipping auto-install");
  process.exit(0);
}

const installScript = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "install.js"
);

try {
  execFileSync(process.execPath, [installScript, "--tool", "all", "--target", target], {
    stdio: "inherit",
  });
} catch {
  // Don't fail the parent install if template copy fails
  console.warn("code-flow-skill: auto-install failed — run `code-flow-skill` manually");
}
