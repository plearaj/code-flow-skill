#!/usr/bin/env node
/**
 * Release gate for the two HTML scaffolds.
 *
 * No test in this repository executes either scaffold's rendering — they are
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
];

const CHECKLIST = `
Release checklist — the rendering neither test suite covers
===========================================================

  ${SCAFFOLDS.join("\n  ")}

Both are checked for what they say, never for how a browser draws them. A
malformed substitution would blank the page in a user's browser and every
test here would still pass.

  1. Run /code-flow.map and /code-flow.quality against any project. Open the
     resulting Code_Flows/<flow>.html and Code_Flows/quality-report.html in a
     browser. Confirm each draws its diagram or its findings — not a blank
     page, not a raw JSON dump.

  2. Corrupt the embedded JSON in each (change a character inside the
     <script type="application/json"> block so it no longer parses) and
     reload. Confirm the red error card appears rather than a blank page.

Do this for BOTH files. A change to either scaffold's rendering re-opens the
gap, and the suites will not tell you.
`;

console.log(CHECKLIST);

if (process.env.CODE_FLOW_RELEASE_CHECKED === "1") {
  console.log("CODE_FLOW_RELEASE_CHECKED=1 — checklist acknowledged, publishing.\n");
  process.exit(0);
}

console.error(
  `Publish blocked: the checklist above has not been acknowledged.

Once you have actually opened both pages, re-run with:

  CODE_FLOW_RELEASE_CHECKED=1 npm publish --access public

The same checklist governs the PyPI release, which has no equivalent hook —
run \`npm run release-check\` by hand before \`uv publish\`.
`,
);
process.exit(1);
