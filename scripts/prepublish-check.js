#!/usr/bin/env node
/**
 * Release gate for the two things no test here can see: whether the HTML
 * scaffolds render, and whether the skills load on a real host.
 *
 * No test in this repository executes any scaffold's rendering — they are
 * checked for what their content says, never for how a browser draws it. Nor
 * does any test start a host and watch it discover a skill: `SKILL.md` and
 * `agents/openai.yaml` are checked for the name, frontmatter and policy the
 * vendors' documentation says to write, never for what a host does with them.
 * Both gaps are accepted (docs/superpowers/specs/2026-08-07-phase3b-report-viewer-design.md,
 * Decision 1) on the condition that a human closes them by hand before each
 * release. A condition recorded only in prose is not a condition, so this runs
 * as `prepublishOnly` and fails the publish until it is acknowledged.
 *
 * Acknowledge with CODE_FLOW_RELEASE_CHECKED=1, matching the CODE_FLOW_ prefix
 * bin/postinstall.js already uses.
 *
 * This is a maintainer tool. It is not in package.json's `files`, so it ships
 * to nobody.
 */
const SCAFFOLDS = [
  "templates/shared/viewer.template.html",
  "templates/shared/report.template.html",
  "templates/shared/index.template.html",
  "templates/shared/bundle.template.html",
];

const CHECKLIST = `
Release checklist — the rendering and the skill loading no test here covers
===========================================================================

Steps 1-3 cover the four HTML scaffolds:

  ${SCAFFOLDS.join("\n  ")}

Each is checked for what it says, never for how a browser draws it. A
malformed substitution would blank the page in a user's browser and every
test here would still pass. templates/shared/bundle.template.html is the one
that most needs opening: it does what the other three do in a single
document, and nothing in either suite renders it.

Step 4 covers the two skills. Their names, frontmatter and Codex policy file
are checked against what the vendors document; nothing here starts a host and
watches it load one.

Step 5 covers the user theme, which nothing in either suite renders either.

  1. Run /code-flow.map and /code-flow.quality against any project. Open the
     resulting Code_Flows/index.html, Code_Flows/<flow>.html and
     Code_Flows/quality-report.html in a browser. Confirm each draws its
     flow list, its diagram or its findings — not a blank page, not a raw
     JSON dump.

     Then open a generated Code_Flows/code-flow.html (run with --output both
     or --output bundle to get one) and walk it: the landing view lists the
     same flows as index.html, opening a flow shows its graph, and the
     quality report is reachable from the same page.

  2. Corrupt the embedded JSON in each (change a character inside the
     <script type="application/json"> block so it no longer parses) and
     reload. Confirm the red error card appears rather than a blank page.

  3. Walk the round trip: from index.html open a flow, use the flow page's
     Flows link to come back, and confirm you land on the index again. These
     are plain links between separately generated files — nothing in either
     suite follows one.

  4. Install into a scratch project with --tool all and open one host. Confirm
     code-flow-map is listed wherever that host lists skills — the slash menu
     on Claude Code, Copilot CLI or Antigravity CLI; \`$code-flow-map\` or the
     /skills menu on Codex; by name on Antigravity IDE, which documents no
     slash syntax at all. An invalid or duplicated skill name does not warn;
     the skill just silently does not load, or loads twice. On Copilot, which
     reads both .claude/skills/ and .agents/skills/, confirm it is listed once
     rather than twice.

     Copilot is two surfaces, not one, and they do not show the same thing.
     VS Code Copilot Chat lists the prompt file as /code-flow.map and — as of
     2026-08-17 — does not list the skill, because Agent Skills there are
     still experimental. The Copilot CLI lists both: /code-flow.map from the
     prompt file and /code-flow-map from the skill, side by side. Checking VS
     Code Chat for /code-flow-map, or the Copilot CLI for only one of the two,
     is not a failed install — confirm each surface against the form it
     actually reads before concluding anything is broken.

     Then pick one host whose row in the README's guarantee table says No —
     Claude Code, Copilot or Codex — and confirm two things there that "it
     showed up in the list" does not tell you: that the host presents the
     skill as explicitly-invoked only, and that it reports no error loading
     the skill or its frontmatter. A host that ignores the field lists the
     skill exactly the same way as one that honours it. Those No rows are
     read out of vendor documentation and have never been observed on a
     running host in this repository; this step is the only thing that ever
     will observe one.

  5. Uncomment one property in a generated project's .code-flow/theme.css,
     regenerate any page, and confirm the colour changed — in both light and
     dark. A user's CSS is inlined into the page verbatim and nothing in
     either suite validates it, so this is the only check theming will ever
     get. Getting this step wrong looks like a broken light/dark toggle, not
     like an error.

Do this for ALL FOUR files, and do step 4 for at least one host. A change to
any scaffold's rendering — or to a skill's name or frontmatter — re-opens the
gap, and the suites will not tell you.
`;

console.log(CHECKLIST);

if (process.env.CODE_FLOW_RELEASE_CHECKED === "1") {
  console.log("CODE_FLOW_RELEASE_CHECKED=1 — checklist acknowledged, publishing.\n");
  process.exit(0);
}

console.error(
  `Publish blocked: the checklist above has not been acknowledged.

Once you have actually opened all four pages, re-run with:

  bash / zsh:
    CODE_FLOW_RELEASE_CHECKED=1 npm publish --access public

  PowerShell (no inline VAR=value prefix — clear it again afterwards, or the
  next publish in this session skips the gate without telling you):
    $env:CODE_FLOW_RELEASE_CHECKED = "1"; npm publish --access public; Remove-Item Env:CODE_FLOW_RELEASE_CHECKED

The same checklist governs the PyPI release, which has no equivalent hook —
run \`npm run release-check\` by hand before \`uv publish\`.
`,
);
process.exit(1);
