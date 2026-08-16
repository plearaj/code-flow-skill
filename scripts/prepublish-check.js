#!/usr/bin/env node
/**
 * Release gate for the HTML scaffolds.
 *
 * No test in this repository executes any scaffold's rendering — they are
 * checked for what their content says, never for how a browser draws it. That
 * gap is accepted (docs/superpowers/specs/2026-08-07-phase3b-report-viewer-design.md,
 * Decision 1) on the condition that a human closes it by hand before each
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
];

const CHECKLIST = `
Release checklist — the rendering neither test suite covers
===========================================================

  ${SCAFFOLDS.join("\n  ")}

Each is checked for what it says, never for how a browser draws it. A
malformed substitution would blank the page in a user's browser and every
test here would still pass.

  1. Run /code-flow.map and /code-flow.quality against any project. Open the
     resulting Code_Flows/index.html, Code_Flows/<flow>.html and
     Code_Flows/quality-report.html in a browser. Confirm each draws its
     flow list, its diagram or its findings — not a blank page, not a raw
     JSON dump.

  2. Corrupt the embedded JSON in each (change a character inside the
     <script type="application/json"> block so it no longer parses) and
     reload. Confirm the red error card appears rather than a blank page.

  3. Walk the round trip: from index.html open a flow, use the flow page's
     Flows link to come back, and confirm you land on the index again. These
     are plain links between separately generated files — nothing in either
     suite follows one.

  4. Install into a scratch project with --tool all and open one host. Confirm
     /code-flow-map appears in its slash menu, and that Copilot — which reads
     both .claude/skills/ and .agents/skills/ — lists it once rather than
     twice. An invalid or duplicated skill name does not warn; the skill just
     silently does not load, or loads twice. No test here can see either.

Do this for ALL THREE files, and do step 4 for at least one host. A change to
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

Once you have actually opened all three pages, re-run with:

  CODE_FLOW_RELEASE_CHECKED=1 npm publish --access public

The same checklist governs the PyPI release, which has no equivalent hook —
run \`npm run release-check\` by hand before \`uv publish\`.
`,
);
process.exit(1);
