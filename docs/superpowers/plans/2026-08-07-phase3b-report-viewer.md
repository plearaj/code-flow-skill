# Code Flow 1.3.0 — Phase 3b Report Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `Code_Flows/quality-report.html` — a self-contained viewer for the quality report — and, in the same phase, give both HTML scaffolds the validation tests neither has ever had.

**Architecture:** This repository is an *installer*, not an analyzer. Phase 3b has three parts that barely touch. **Installer plumbing** (Task 1) — the shared-scaffold install becomes a list, exactly as Task 1 of phase 3a turned the per-tool install into a list. **A validation harness** (Tasks 2-3) — each viewer's boot logic is refactored so its decision-making is a pure `validate(raw, TOKEN)` function behind sentinel comments, and one Node test drives both. **The viewer itself and the prompt change that writes it** (Tasks 4-5).

**Tech Stack:** Node 24 (`node:test`, built in), Python 3.12 + pytest, hatchling, uv. Vanilla HTML/CSS/JS in a single self-contained file. **No new dependencies of any kind, in either package** — see Global Constraints.

## Global Constraints

- Target version is exactly `1.3.0`, set identically in `package.json` and `pyproject.toml`. Phase 3b is additive within 1.x — it carries no breaking change.
- **No new dependencies, and that includes dev dependencies.** `package.json` has no `devDependencies` key at all and must not gain one. Python's dev group stays exactly `pytest>=8.0`. This is the constraint that shaped the whole design — see [the 3b design doc](../specs/2026-08-07-phase3b-report-viewer-design.md), Decision 1. If a task seems to need `jsdom`, a headless browser, or any test library, **stop and report** rather than adding it.
- Root `templates/` is the single source of truth. `src/code_flow_skill/templates/` must not exist.
- Installers stay **plain file copies**. No read-modify-write, no guard strings, no idempotency logic — copying is idempotent by construction. `--tool` semantics are unchanged.
- The two installers' file lists must stay in step. `test/install.test.js` and `tests/test_installer_python.py` assert the same literal `EXPECTED_ALL` list, and `tests/test_packaging.py` pins the README's "Files written" table to that same list. Change one, change all three, in the same commit.
- **Both scaffolds must remain single self-contained files that work from a `file://` URL with no network.** No external CSS, no CDN, no `import`, no `fetch`. This is why the JS cannot be split into a module and why the sentinel-extraction approach exists.
- Every path written into a generated artifact uses forward slashes and is repo-relative. `meta.root` is the one absolute path.
- Reports say **"catalogued"**, never "all". A report with no findings under partial coverage means "clean within what was mapped" and must say so in words — **in the viewer as well as the markdown.**
- `code-flow.quality` **never writes to source code.** Phase 3b adds a third output file and changes nothing else about what the command touches.
- Windows is the development platform. `npm test` is `node --test "test/**/*.test.js"` — the bare `node --test test/` form fails with MODULE_NOT_FOUND on this machine's Node v24.11.1. Python tests: `uv run --group dev pytest -v`.
- Do not use `git add -A`; stage explicit paths.
- **Contract tests must fail when the rule they name is deleted.** Every task in phase 3a shipped at least one assertion that would have passed with its rule removed, and three shipped assertions that were dead the day they were written — one whose OR branch could never match, one guarding the wrong sentence, one whose whole body never executed because its only fixture took the other branch. Anchor each assertion to its rule with a proximity regex over a `_flatten`-wrapped region; allow `\s+` wherever prose may wrap; check both branches of every OR fire; give any `if` at the top of a test a fixture that takes the other branch. **Where a test in this plan is written loosely, the strengthened form governs** — the test code here is a means, not the requirement.

### Host parity rule (binding on Task 5)

| Host | File | Shape |
|---|---|---|
| Claude | `templates/claude/code-flow.quality.md` | Markdown, `#### N. Title` sections, `$ARGUMENTS` |
| Gemini | `templates/gemini/code-flow.quality.toml` | The same prose inside a TOML `prompt = '''…'''` string |
| Copilot | `templates/copilot/code-flow.quality.prompt.md` | Markdown with `mode: agent` frontmatter, a numbered list |

**Claude and Gemini are byte-identical from `#### 1.` onward — baseline 0 — and must stay there.** Unlike phase 3a this is now enforced automatically: `tests/test_host_parity.py` pins `BASELINE_QUALITY = 0` and `BASELINE_MAP = 27`, so drift fails the suite. You still achieve it by construction:

- **Name no host-specific tool.** Write "write `Code_Flows/quality-report.html`", never "Use the `Write` tool".
- **Use three-backtick fences only.** A four-backtick fence puts the baseline above 0.
- **Write ASCII.** "at least", "up to" — never `∈`, `≥`, `≤`. The em dash is the file's existing convention and is fine.
- **Copilot says the same thing in its own numbered-list register.** Same rules, same field names, same phrasings.
- Task 5 gives its new rule **once**, as canonical text. Apply that one block to all three hosts. Do not draft per-host blocks — that is how phase 1's Copilot template got abridged five times.
- At the end of Task 5, read all three templates **end-to-end** and **derive** — do not assert — that the rule is present in each host. Every historical miss was a rule present in two hosts and absent from the third, and every one was *outside* the section under review.

### What phase 3a already guarantees

- `Code_Flows/quality-report.json` carries `schema: 1`, `meta` (`root`, `generated`, `readCode`, `mapGenerated`, `mapMode`, `mapDetail`), `coverage` (`flowsTraced`, `entryPointsFound`, `functionsCatalogued`, `flowsUnreadable`, `filesChanged`, `findingsDropped`, `detectorsSkipped`), and `findings[]`.
- Each finding carries `id`, `principle`, `detector`, `severity`, `title`, `rationale`, `suggestion`, `confidence`, `effort`, `sites[]`, plus per-detector evidence: `flows` (repeated-sequence), `metric` and `value` (complexity-hotspot), `exported` and `reachedBy` (unreached).
- `sites[]` entries carry `file`, `line`, `symbol`, and `snippet` — the last **conditionally**: a thin map read without `--read-code` has none.
- `severity` is `high`/`medium`/`low`. `principle` is `DRY`/`KISS`/`YAGNI`. `confidence` is `unverified`/`verified`. `reachedBy` is `none`/`tests`.
- The `findings` array is **already ordered** by severity descending, then site count descending, then principle alphabetically, and ids are assigned in that order after step 4's drops.
- `templates/shared/viewer.template.html` is 436 lines, carries exactly one `__FLOW_DATA__` token in a `<script type="application/json" id="flow-data">` block, and already implements a `TOKEN` check, a `JSON.parse` try/catch, a `problems[]` validator and a `fail(title, lines)` error card.
- `examples/sample-report.json` and `examples/sample-report-unverified.json` ship as fixtures and are validated by `tests/test_report_schema.py`.

## A design clarification this plan resolves

The parent spec says the viewer harness should test "a finding citing a missing flow". **That case does not exist for the report viewer**, and pretending otherwise would produce a test asserting nothing.

The flow viewer has a genuine cross-reference to break: an edge's `from`/`to` must match a node `id` in the same document, and its `problems[]` already checks exactly that. The quality report is **self-contained** — it carries no flow registry, so a `flows` entry naming a slug cannot be checked against anything the viewer can see. Cross-checking against `Code_Flows/index.json` would require a second fetch, which the offline single-file constraint forbids.

So the report viewer's equivalent of the dangling-reference case is **internal consistency**: duplicate finding ids, an empty `sites` array, and an out-of-enum `severity`, `principle`, `confidence` or `detector`. Those are real, they are checkable from the document alone, and they are what Task 3 validates. This plan records the substitution rather than silently dropping the requirement.

## File Structure

**Created:**
- `docs/superpowers/plans/2026-08-07-phase3b-report-viewer.md` — this plan
- `templates/shared/report.template.html` — the quality-report viewer
- `test/viewer-validation.test.js` — the shared harness, driving both scaffolds' `validate`

**Modified:**
- `templates/shared/viewer.template.html` — boot logic refactored behind sentinels; **no behavior change**
- `bin/install.js` — `installViewer()` becomes a list of shared files
- `src/code_flow_skill/cli.py` — `_install_viewer` becomes the same
- `test/install.test.js`, `tests/test_installer_python.py` — `EXPECTED_ALL` gains one entry
- `tests/test_packaging.py` — wheel contents gain one file; version assertion moves to `1.3.0`
- `tests/test_template_contracts.py` — report-viewer contract tests; the existing one-token test generalized to both scaffolds
- `templates/{claude,gemini,copilot}/code-flow.quality.*` — step 5 gains the third rendering
- `README.md` — the HTML report, the new installed file, the "Files written" table
- `package.json`, `pyproject.toml`, `uv.lock` — version 1.3.0

**Not modified, deliberately:** `templates/*/code-flow.map.*`, `examples/*.json`, `tests/test_report_schema.py`, `tests/test_host_parity.py` (beyond nothing — its baselines do not move).

**A note on file size.** The flow viewer is 436 lines. The report viewer will land near 400-600, and that is not a defect: a viewer with filters and a theme toggle is a real frontend artifact, and the offline single-file constraint forbids splitting it. Do not split it. Do not inline a framework.

---

### Task 1: Install a second shared scaffold

**Files:**
- Create: `templates/shared/report.template.html` (skeleton only — Tasks 3-4 fill it)
- Modify: `bin/install.js:28-36`, `src/code_flow_skill/cli.py:28-38`
- Modify: `test/install.test.js`, `tests/test_installer_python.py`, `tests/test_packaging.py`
- Modify: `package.json`, `pyproject.toml`, `README.md`

**Interfaces:**
- Produces: `EXPECTED_ALL` with 8 entries (below), asserted identically in both languages; `_SHARED_FILES` (Python) and `sharedFiles` (JS); a `templates/shared/report.template.html` containing exactly one `__REPORT_DATA__` token and the two sentinel markers Task 3 fills between.
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing installer test (both languages)**

In `tests/test_installer_python.py`, replace the `EXPECTED_ALL` literal with:

```python
EXPECTED_ALL = [
    ".claude/commands/code-flow.map.md",
    ".claude/commands/code-flow.quality.md",
    ".code-flow/report.template.html",
    ".code-flow/viewer.template.html",
    ".gemini/commands/code-flow.map.toml",
    ".gemini/commands/code-flow.quality.toml",
    ".github/prompts/code-flow.map.prompt.md",
    ".github/prompts/code-flow.quality.prompt.md",
]
```

Make the identical change to the `EXPECTED_ALL` array in `test/install.test.js`. The two literals must stay character-for-character the same modulo language syntax — that duplication is the mechanism holding the installers in step, and it is a requirement, not a DRY defect.

Add to `tests/test_installer_python.py`, alongside the existing byte-identity map:

```python
def test_both_shared_scaffolds_are_installed_regardless_of_tool(
    tmp_path: Path, run_python_installer
) -> None:
    """The scaffolds are tool-agnostic: every command template references one
    of them, so selecting a single host must still install both."""
    run_python_installer(tmp_path, "--tool", "claude")
    for name in ("viewer.template.html", "report.template.html"):
        assert (tmp_path / ".code-flow" / name).is_file(), f"{name} was not installed"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_installer_python.py -v` and `node --test "test/**/*.test.js"`

Expected: FAIL. The set assertions report `.code-flow/report.template.html` missing; the new test fails on the same file. That is the correct failure — the template does not exist and nothing copies it.

- [ ] **Step 3: Create the skeleton scaffold**

Create `templates/shared/report.template.html`. This is a *skeleton* — Task 3 writes the validator and Task 4 the rendering. It must already be a valid, openable HTML file that fails loudly rather than blankly:

```html
<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Code Flow — Quality Report</title>
<style>
:root { color-scheme: light dark; }
body { margin: 0; font: 14px/1.5 ui-sans-serif, system-ui, sans-serif; }
#err { padding: 24px; }
#err h2 { margin: 0 0 8px; font-size: 16px; }
#err pre { white-space: pre-wrap; margin: 0; }
</style>
</head>
<body>
<div id="err" hidden></div>
<main id="app"></main>
<script type="application/json" id="report-data">__REPORT_DATA__</script>
<script>
(function(){
"use strict";
/* built dynamically so the installer's string replacement cannot touch the check itself */
var TOKEN = "__REPORT" + "_DATA__";
var errBox = document.getElementById("err");
function fail(title, lines){
  errBox.hidden = false;
  errBox.innerHTML = "";
  var card = document.createElement("div");
  var h = document.createElement("h2"); h.textContent = title; card.appendChild(h);
  var pre = document.createElement("pre"); pre.textContent = lines.join("\n"); card.appendChild(pre);
  errBox.appendChild(card);
}

/* ==== validate:start ==== */
function validate(raw, TOKEN){
  return { ok: false, title: "Not implemented", lines: ["Task 3 writes this."] };
}
/* ==== validate:end ==== */

var raw = document.getElementById("report-data").textContent;
var v = validate(raw, TOKEN);
if (!v.ok) { fail(v.title, v.lines); return; }
/* Task 4 renders v.data into #app here. */
})();
</script>
</body>
</html>
```

Note `TOKEN` is reassembled at runtime, copying the flow viewer's trick: if it were written literally, the installer's own string replacement would overwrite the check that detects an unreplaced token.

- [ ] **Step 4: Make both installers copy a list of shared files**

In `bin/install.js`, replace the `installViewer` function (currently a single hard-coded copy) with:

```js
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
```

and change the call site at the bottom of the file from `installViewer();` to `installShared();`.

In `src/code_flow_skill/cli.py`, replace `_install_viewer` with:

```python
# Both scaffolds are tool-agnostic: every command template references one of
# them, so both install regardless of --tool. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages are what holds them there.
_SHARED_FILES = (
    ("viewer.template.html", "interactive viewer"),
    ("report.template.html", "quality report viewer"),
)


def _install_shared(target: Path) -> None:
    """Copy every tool-agnostic scaffold into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    for name, label in _SHARED_FILES:
        out = target / ".code-flow" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path("shared", name), out)
        print(f"Installed {label} template: {out}")
```

and change the call at the end of `main()` from `_install_viewer(target)` to `_install_shared(target)`.

- [ ] **Step 5: Run the installer tests to verify they pass**

Run: `uv run --group dev pytest tests/test_installer_python.py -v` and `node --test "test/**/*.test.js"`

Expected: PASS, both languages.

- [ ] **Step 6: Bump the version and update packaging**

Set `"version": "1.3.0"` in `package.json` and `version = "1.3.0"` in `pyproject.toml`. Run `uv lock` so `uv.lock` records it.

In `tests/test_packaging.py`, rename `test_package_versions_match_and_are_1_2_0` to `test_package_versions_match_and_are_1_3_0` and change the asserted value — the version belongs in the test's **name** as well as its body, so a stale name cannot outlive the assertion. Add `templates/shared/report.template.html` to the expected wheel contents.

- [ ] **Step 7: Update the README's "Files written" table**

`tests/test_packaging.py` pins that table to `EXPECTED_ALL`, so it fails until the table gains the row. Add `.code-flow/report.template.html` with a description naming what it is ("Quality report viewer scaffold"). Also add the file to the manual-install `cp` block, which copies the shared scaffolds explicitly.

- [ ] **Step 8: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Python goes from 215 to 216 (the new shared-scaffold test); Node stays at 10.

- [ ] **Step 9: Commit**

```bash
git add templates/shared/report.template.html bin/install.js src/code_flow_skill/cli.py test/install.test.js tests/test_installer_python.py tests/test_packaging.py package.json pyproject.toml uv.lock README.md
git commit -m "feat: install the quality report viewer scaffold"
```

---

### Task 2: The validation harness, proved against the flow viewer

This task builds the harness and retrofits the *existing* viewer to it. Doing the retrofit first is deliberate: `viewer.template.html` is a known-good artifact that has been in users' hands since 1.0.0, so if the harness disagrees with it, the harness is probably wrong — which is exactly the feedback you want before writing a second viewer against the same contract.

**Files:**
- Create: `test/viewer-validation.test.js`
- Modify: `templates/shared/viewer.template.html:113-148`

**Interfaces:**
- Consumes: the sentinel markers `/* ==== validate:start ==== */` and `/* ==== validate:end ==== */` established in Task 1's skeleton.
- Produces: `extractValidate(templateName)` in `test/viewer-validation.test.js`, returning the scaffold's `validate` function; and the `validate(raw, TOKEN)` contract **both** scaffolds implement.

  The shared part of that contract is the failure shape and the `ok` flag, not the success payload:
  - On failure: `{ok: false, title: string, lines: string[]}` — identical in both scaffolds, because `fail(title, lines)` consumes it in both.
  - On success: `{ok: true, data, …}` where the remaining keys are **scaffold-specific**, being whatever that viewer's rendering needs. The flow viewer returns `meta`, `nodes`, `edges` and `byId`; the report viewer (Task 3) returns `meta`, `coverage` and `findings`. The harness only asserts on `ok`, `title`, `lines`, and the success keys it names per scaffold, so the two need not agree beyond that.

- [ ] **Step 1: Write the failing harness**

Create `test/viewer-validation.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const START = "/* ==== validate:start ==== */";
const END = "/* ==== validate:end ==== */";

// The scaffolds must stay single self-contained files that work from a file://
// URL, so their JS cannot be a module we could import. Instead each marks its
// pure decision logic with sentinels, and we lift that block out and run it.
// Nothing here touches the DOM, because nothing validate() does touches the DOM.
function extractValidate(templateName) {
  const src = fs.readFileSync(
    path.join(repoRoot, "templates", "shared", templateName),
    "utf8"
  );
  const from = src.indexOf(START);
  const to = src.indexOf(END);
  assert.ok(from !== -1, `${templateName} is missing ${START}`);
  assert.ok(to !== -1, `${templateName} is missing ${END}`);
  assert.ok(to > from, `${templateName} has its sentinels in the wrong order`);
  const block = src.slice(from + START.length, to);
  return new Function(`${block}; return validate;`)();
}

const SCAFFOLDS = [
  { file: "viewer.template.html", token: "__FLOW_DATA__" },
  { file: "report.template.html", token: "__REPORT_DATA__" },
];

for (const { file, token } of SCAFFOLDS) {
  test(`${file}: an unreplaced token is reported, not parsed`, () => {
    const validate = extractValidate(file);
    const v = validate(token, token);
    assert.equal(v.ok, false);
    assert.match(v.title + " " + v.lines.join(" "), /placeholder|never replaced/i);
  });

  test(`${file}: malformed JSON is reported with the parser's message`, () => {
    const validate = extractValidate(file);
    const v = validate("{ not json", token);
    assert.equal(v.ok, false);
    assert.match(v.title, /invalid json/i);
    assert.ok(v.lines.length > 0, "the parser's message must reach the user");
  });

  test(`${file}: well-formed JSON of the wrong shape is reported`, () => {
    const validate = extractValidate(file);
    const v = validate(JSON.stringify({ nothing: "useful" }), token);
    assert.equal(v.ok, false);
    assert.ok(v.lines.length > 0, "a shape failure must say what was wrong");
  });

  test(`${file}: an empty document is reported, not silently accepted`, () => {
    const validate = extractValidate(file);
    const v = validate("", token);
    assert.equal(v.ok, false);
  });
}
```

Note what this harness does *not* claim: it never asserts the error card is visible. That is the accepted cost recorded in the design doc, mitigated by opening both scaffolds against a real codebase before a release ships.

- [ ] **Step 2: Run the harness to verify it fails**

Run: `node --test "test/**/*.test.js"`

Expected: FAIL, every case, for both scaffolds — but for two different reasons, and you should see both:

- `viewer.template.html` fails inside `extractValidate` with "is missing `/* ==== validate:start ==== */`". It has the logic but not the sentinels, so the harness cannot reach it.
- `report.template.html` gets past extraction — Task 1 put the sentinels in — and fails on the assertions instead. Its stub returns `{ok:false, title:"Not implemented"}`, so each case satisfies `assert.equal(v.ok, false)` and then fails the message match: the token case wants `/placeholder|never replaced/`, the malformed-JSON case wants `/invalid json/i`.

That second failure mode is the useful one to notice: `ok:false` alone is not evidence a validator works, because a validator that rejects *everything* also returns `ok:false`. The message assertions are what distinguish rejecting-for-the-right-reason from rejecting-by-default.

- [ ] **Step 3: Refactor the flow viewer's boot into a pure `validate`**

In `templates/shared/viewer.template.html`, replace the boot block (currently `var raw = …` through the `edges = edges.filter(…)` line) with a sentinel-wrapped pure function plus a thin call site. **This must not change behavior** — every message string stays byte-identical, including the `</` escaping tip:

```js
/* ==== validate:start ==== */
function validate(raw, TOKEN){
  raw = (raw || "").trim();
  if (raw === TOKEN){
    return { ok:false, title:"No flow data", lines:[
      "The " + TOKEN + " placeholder was never replaced.",
      "This template must be filled with a JSON data block before viewing."
    ]};
  }
  var data;
  try { data = JSON.parse(raw); }
  catch(e){
    return { ok:false, title:"Invalid JSON in #flow-data", lines:[
      String(e.message || e), "",
      "Tip: literal </ inside snippet strings must be escaped as <\\/."
    ]};
  }
  var meta  = (data && typeof data === "object" && data.meta) || {};
  var nodes = Array.isArray(data && data.nodes) ? data.nodes : null;
  var edges = Array.isArray(data && data.edges) ? data.edges : [];
  var problems = [];
  if (!nodes || !nodes.length) problems.push("`nodes` must be a non-empty array.");
  var byId = new Map();
  (nodes || []).forEach(function(n, i){
    if (!n || typeof n.id !== "string" || !n.id) { problems.push("nodes[" + i + "] is missing a string `id`."); return; }
    if (!/^[\w.\-]+$/.test(n.id)) problems.push("node id \"" + n.id + "\" has unexpected characters (want [a-z0-9_]).");
    if (byId.has(n.id)) problems.push("duplicate node id \"" + n.id + "\".");
    byId.set(n.id, n);
  });
  edges.forEach(function(e, i){
    if (!e || typeof e !== "object") { problems.push("edges[" + i + "] is not an object."); return; }
    if (!byId.has(e.from)) problems.push("edge[" + i + "].from \"" + e.from + "\" does not match any node id.");
    if (!byId.has(e.to))   problems.push("edge[" + i + "].to \"" + e.to + "\" does not match any node id.");
  });
  if (problems.length) return { ok:false, title:"Flow data failed validation", lines:problems };
  return { ok:true, data:data, meta:meta, nodes:nodes, byId:byId,
           edges: edges.filter(function(e){ return byId.has(e.from) && byId.has(e.to); }) };
}
/* ==== validate:end ==== */

var v = validate(document.getElementById("flow-data").textContent, TOKEN);
if (!v.ok){ fail(v.title, v.lines); return; }
var data = v.data, meta = v.meta, nodes = v.nodes, edges = v.edges, byId = v.byId;
```

Everything downstream of this point already reads `data`, `meta`, `nodes`, `edges` and `byId`, so it needs no change. Verify that by searching the rest of the file for those names before you commit.

- [ ] **Step 4: Add the flow viewer's own dangling-reference case**

Append to `test/viewer-validation.test.js`, outside the `for` loop — this case is specific to the flow viewer, because the quality report has no cross-document reference to break (see "A design clarification this plan resolves"):

```js
test("viewer.template.html: an edge naming no node is reported", () => {
  const validate = extractValidate("viewer.template.html");
  const v = validate(
    JSON.stringify({
      meta: {},
      nodes: [{ id: "a_handle_request" }],
      edges: [{ from: "a_handle_request", to: "b_validate_email" }],
    }),
    "__FLOW_DATA__"
  );
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /b_validate_email.*does not match any node id/);
});

test("viewer.template.html: a valid flow document produces no problems", () => {
  const validate = extractValidate("viewer.template.html");
  const v = validate(
    JSON.stringify({
      meta: { title: "User login" },
      nodes: [{ id: "a_handle_request" }, { id: "b_validate_email" }],
      edges: [{ from: "a_handle_request", to: "b_validate_email" }],
    }),
    "__FLOW_DATA__"
  );
  assert.equal(v.ok, true, v.ok ? "" : v.title + ": " + (v.lines || []).join(" "));
  assert.equal(v.nodes.length, 2);
  assert.equal(v.edges.length, 1);
});
```

- [ ] **Step 5: Run the harness — the flow viewer must now pass entirely**

Run: `node --test "test/**/*.test.js"`

Expected: every `viewer.template.html` case passes. `report.template.html` still fails its cases — Task 3 fixes that.

**If a flow-viewer case fails, that is a real bug the scaffold has been shipping since 1.0.0.** Fix the scaffold and say so in your task report. Do not adjust the test to match the behavior — the whole point of the retrofit is that nobody has ever checked this.

- [ ] **Step 6: Prove the harness is not vacuous**

Temporarily break one rule in `viewer.template.html` — delete the `if (byId.has(e.from))` check — and re-run. The dangling-reference case must fail. Restore the file exactly, confirm `git diff templates/` shows nothing, and re-run to green. Record both outputs in your task report.

- [ ] **Step 7: Run the full suite and commit**

Run: `uv run --group dev pytest -v && npm test`

```bash
git add test/viewer-validation.test.js templates/shared/viewer.template.html
git commit -m "test: one validation harness, retrofitted to the flow viewer"
```

---

### Task 3: The report viewer's validator

**Files:**
- Modify: `templates/shared/report.template.html` (the block between the sentinels)
- Modify: `test/viewer-validation.test.js`

**Interfaces:**
- Consumes: `extractValidate(templateName)` and the `{ok, title, lines}` / `{ok, data, …}` contract from Task 2.
- Produces: a `validate(raw, TOKEN)` in `report.template.html` returning `{ok:true, data, meta, coverage, findings}` on success; Task 4 renders from exactly those names.

- [ ] **Step 1: Write the failing report-specific tests**

Append to `test/viewer-validation.test.js`:

```js
const VALID_REPORT = {
  schema: 1,
  meta: { root: "C:/Users/example/project", generated: "2026-08-07", readCode: false,
          mapGenerated: "2026-08-06", mapMode: "whole-code-base", mapDetail: "standard" },
  coverage: { flowsTraced: 14, entryPointsFound: 17, functionsCatalogued: 1180,
              flowsUnreadable: 0, filesChanged: 6, findingsDropped: 2, detectorsSkipped: [] },
  findings: [{
    id: "DRY-01", principle: "DRY", detector: "duplicate-intent", severity: "high",
    title: "Email validation is implemented three times",
    rationale: "Three functions normalise and check an address with the same rules.",
    suggestion: "Consolidate on one validator and have the others call it.",
    confidence: "unverified", effort: "small",
    sites: [{ file: "src/auth/validators.py", line: 12, symbol: "validate_email" }],
  }],
};

function report(overrides) {
  return JSON.stringify({ ...VALID_REPORT, ...overrides });
}

test("report.template.html: a valid report produces no problems", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({}), "__REPORT_DATA__");
  assert.equal(v.ok, true, v.ok ? "" : v.title + ": " + (v.lines || []).join(" "));
  assert.equal(v.findings.length, 1);
  assert.equal(v.coverage.flowsTraced, 14);
});

test("report.template.html: an empty findings array is valid, not an error", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ findings: [] }), "__REPORT_DATA__");
  assert.equal(v.ok, true, "a clean report is a real report, not a failure");
  assert.equal(v.findings.length, 0);
});

test("report.template.html: a duplicate finding id is reported", () => {
  const validate = extractValidate("report.template.html");
  const dup = [VALID_REPORT.findings[0], { ...VALID_REPORT.findings[0] }];
  const v = validate(report({ findings: dup }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /duplicate finding id "DRY-01"/);
});

test("report.template.html: a finding with no sites is reported", () => {
  const validate = extractValidate("report.template.html");
  const bare = [{ ...VALID_REPORT.findings[0], sites: [] }];
  const v = validate(report({ findings: bare }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /DRY-01.*at least one site/);
});

test("report.template.html: an out-of-enum severity is reported", () => {
  const validate = extractValidate("report.template.html");
  const bad = [{ ...VALID_REPORT.findings[0], severity: "critical" }];
  const v = validate(report({ findings: bad }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /severity "critical"/);
});

test("report.template.html: a missing coverage block is reported", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ coverage: undefined }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /`coverage`/);
});

test("report.template.html: a wrong schema version is reported", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ schema: 2 }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /schema/i);
});
```

The empty-findings test matters more than it looks: a viewer that treated "no findings" as a failure would hide the single most important honest outcome the command can produce.

- [ ] **Step 2: Run to verify they fail**

Run: `node --test "test/**/*.test.js"`

Expected: FAIL, every report case, against the stub's "Not implemented".

- [ ] **Step 3: Write the validator**

Replace the stub between the sentinels in `templates/shared/report.template.html`:

```js
/* ==== validate:start ==== */
function validate(raw, TOKEN){
  raw = (raw || "").trim();
  if (raw === TOKEN){
    return { ok:false, title:"No report data", lines:[
      "The " + TOKEN + " placeholder was never replaced.",
      "This template must be filled with a JSON data block before viewing."
    ]};
  }
  var data;
  try { data = JSON.parse(raw); }
  catch(e){
    return { ok:false, title:"Invalid JSON in #report-data", lines:[
      String(e.message || e), "",
      "Tip: literal </ inside snippet strings must be escaped as <\\/."
    ]};
  }
  var SEVERITY = { high:1, medium:1, low:1 };
  var PRINCIPLE = { DRY:1, KISS:1, YAGNI:1 };
  var CONFIDENCE = { unverified:1, verified:1 };
  var DETECTOR = { "duplicate-intent":1, "repeated-sequence":1, "complexity-hotspot":1, "unreached":1 };
  var problems = [];
  if (!data || typeof data !== "object" || Array.isArray(data)){
    return { ok:false, title:"Report data failed validation", lines:["The document must be a JSON object."] };
  }
  if (data.schema !== 1) problems.push("`schema` must be 1, got " + JSON.stringify(data.schema) + ".");
  var meta = (data.meta && typeof data.meta === "object") ? data.meta : null;
  if (!meta) problems.push("`meta` must be an object.");
  var coverage = (data.coverage && typeof data.coverage === "object") ? data.coverage : null;
  if (!coverage) problems.push("`coverage` must be an object.");
  var findings = Array.isArray(data.findings) ? data.findings : null;
  if (!findings) problems.push("`findings` must be an array.");
  var seen = {};
  (findings || []).forEach(function(f, i){
    if (!f || typeof f !== "object"){ problems.push("findings[" + i + "] is not an object."); return; }
    var id = typeof f.id === "string" && f.id ? f.id : null;
    if (!id){ problems.push("findings[" + i + "] is missing a string `id`."); return; }
    if (Object.prototype.hasOwnProperty.call(seen, id)) problems.push("duplicate finding id \"" + id + "\".");
    seen[id] = 1;
    if (!SEVERITY[f.severity]) problems.push(id + " has severity " + JSON.stringify(f.severity) + "; want high, medium or low.");
    if (!PRINCIPLE[f.principle]) problems.push(id + " has principle " + JSON.stringify(f.principle) + "; want DRY, KISS or YAGNI.");
    if (!DETECTOR[f.detector]) problems.push(id + " has detector " + JSON.stringify(f.detector) + ".");
    if (!CONFIDENCE[f.confidence]) problems.push(id + " has confidence " + JSON.stringify(f.confidence) + "; want unverified or verified.");
    if (!Array.isArray(f.sites) || !f.sites.length){
      problems.push(id + " must cite at least one site; a finding without file:line evidence is not reportable.");
      return;
    }
    f.sites.forEach(function(s, j){
      if (!s || typeof s !== "object"){ problems.push(id + " site " + j + " is not an object."); return; }
      if (typeof s.file !== "string" || !s.file) problems.push(id + " site " + j + " is missing `file`.");
      else if (s.file.indexOf("\\") !== -1) problems.push(id + " site " + j + " uses backslashes; paths are forward-slash and repo-relative.");
      if (typeof s.line !== "number" || s.line < 1) problems.push(id + " site " + j + " is missing a positive `line`.");
    });
  });
  if (problems.length) return { ok:false, title:"Report data failed validation", lines:problems };
  return { ok:true, data:data, meta:meta, coverage:coverage, findings:findings };
}
/* ==== validate:end ==== */
```

- [ ] **Step 4: Run to verify they pass**

Run: `node --test "test/**/*.test.js"`

Expected: PASS, every case in both scaffolds.

- [ ] **Step 5: Prove each new rule is not vacuous**

For the duplicate-id, empty-sites and out-of-enum-severity rules, delete that rule from the validator one at a time, confirm the matching test fails, and restore. Record the three outputs. A rule whose test still passes with the rule gone is not a rule.

- [ ] **Step 6: Run the full suite and commit**

```bash
git add templates/shared/report.template.html test/viewer-validation.test.js
git commit -m "feat: validate the quality report document"
```

---

### Task 4: Render the report

This is the one task whose deliverable is a frontend artifact rather than a rule. The plan specifies it by contract and by test rather than by inlining 400 lines of markup — writing that markup is the task. Everything the artifact must do is enumerated below; nothing is left to taste except visual detail.

**Files:**
- Modify: `templates/shared/report.template.html`
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `validate()`'s success shape `{data, meta, coverage, findings}` from Task 3.
- Produces: a rendering; no later task consumes anything from it.

- [ ] **Step 1: Write the failing contract tests**

In `tests/test_template_contracts.py`, generalize the existing single-scaffold token test and add the honesty contracts:

```python
SCAFFOLDS = (
    ("viewer.template.html", "__FLOW_DATA__"),
    ("report.template.html", "__REPORT_DATA__"),
)


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_has_exactly_one_token(repo_root: Path, name: str, token: str) -> None:
    """More than one token means the installer's replacement would fill some and
    not others; none means it fills nothing and the page shows the token check."""
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    assert text.count(token) == 1


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_is_self_contained(repo_root: Path, name: str, token: str) -> None:
    """Both scaffolds must render from a file:// URL with no network. An external
    reference would leave a user staring at an unstyled or empty page offline."""
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    assert not re.search(r"""<script[^>]+\bsrc\s*=""", text), f"{name} loads an external script"
    assert not re.search(r"""<link[^>]+\brel\s*=\s*["']stylesheet""", text), f"{name} loads an external stylesheet"
    assert "https://" not in text and "http://" not in text, f"{name} references a remote URL"


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_marks_its_validator_with_sentinels(repo_root: Path, name: str, token: str) -> None:
    """test/viewer-validation.test.js lifts the block between these markers. If a
    scaffold loses them the harness cannot reach its validator at all."""
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    assert text.count("/* ==== validate:start ==== */") == 1
    assert text.count("/* ==== validate:end ==== */") == 1


def test_report_viewer_leads_with_coverage(repo_root: Path) -> None:
    """The same rule the markdown obeys. A prettier rendering makes over-reading
    easier, so the caveat has to be the first thing on screen, not a footnote."""
    text = (repo_root / "templates" / "shared" / "report.template.html").read_text(encoding="utf-8")
    banner = text.index("coverage-banner")
    findings = text.index("findings-list")
    assert banner < findings, "the coverage banner must render before the findings"


def test_report_viewer_never_claims_completeness(repo_root: Path) -> None:
    """'catalogued, never all' binds the viewer exactly as it binds the report."""
    text = (repo_root / "templates" / "shared" / "report.template.html").read_text(encoding="utf-8")
    assert "catalogued" in text
    assert not re.search(r"\ball files\b|\ball functions\b", text, re.IGNORECASE)


def test_report_viewer_states_the_no_findings_caveat(repo_root: Path) -> None:
    """The most dangerous screen in the product. An empty findings array means
    'clean within what was mapped', and the viewer must say so in words rather
    than rendering an empty state that reads as a pass."""
    text = (repo_root / "templates" / "shared" / "report.template.html").read_text(encoding="utf-8")
    assert re.search(r"clean within what was mapped", text, re.IGNORECASE)
    assert re.search(r"no findings.{0,400}clean bill of health", text, re.IGNORECASE | re.DOTALL)


def test_report_viewer_never_instructs_deletion(repo_root: Path) -> None:
    """`unreached` is a candidate, never a verdict, so the viewer offers no delete
    affordance and no copy that reads as an instruction to remove code."""
    text = (repo_root / "templates" / "shared" / "report.template.html").read_text(encoding="utf-8")
    assert re.search(r"candidate", text, re.IGNORECASE)
    assert not re.search(r">\s*(delete|remove)\b", text, re.IGNORECASE), "no delete affordance"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k scaffold` and `-k report_viewer`

Expected: FAIL. The token and sentinel tests pass already (Task 1 put both in place); the coverage-banner, catalogued, no-findings and deletion tests all fail because nothing is rendered yet.

- [ ] **Step 3: Build the rendering**

Write the rendering into `templates/shared/report.template.html`, replacing the `/* Task 4 renders v.data into #app here. */` comment. Required, in order:

1. **A coverage banner**, in an element whose class or id contains `coverage-banner`, rendered **before** the findings list and not collapsible. It carries: `flowsTraced` of `entryPointsFound` flows traced; `functionsCatalogued` functions catalogued; `filesChanged` files changed since mapping; `findingsDropped` findings dropped as stale; `flowsUnreadable` if non-zero; and each entry of `detectorsSkipped` with its reason. Where `flowsTraced` is below `entryPointsFound`, say the map is partial in words.
2. **The word "catalogued"**, never "all files" or "all functions".
3. **When `findings` is empty**, a prominent message reading "No findings — clean within what was mapped" plus a sentence saying that under partial coverage this is not a clean bill of health. No checkmark, no green banner, no empty-state illustration.
4. **A findings list**, in an element whose class or id contains `findings-list`, in the array's existing order. **Never re-sort** — the analysis already ordered them, and a viewer that re-sorted would make two renderings of one file disagree.
5. **Per finding**: `id`, `severity`, `principle`, `detector`, `title`, `rationale`, `suggestion`, `confidence`, `effort`, its evidence fields (`flows`, `metric`/`value`, `exported`/`reachedBy`) when present, and each site's `file:line`, `symbol` and `snippet` when present. A missing `snippet` is normal — a thin map read without `--read-code` has none — so render its absence quietly, not as an error.
6. **Filters** for severity and principle. **No sort controls.**
7. **A light/dark theme toggle** matching the flow viewer's, including its `localStorage` key `codeflow-theme`, so the two artifacts behave alike.
8. **The word "candidate"** in the copy describing `unreached` findings, and no button or link whose label is "Delete" or "Remove".

Use `textContent`, never `innerHTML`, for any value drawn from the report data. Snippets are source code from the analyzed repository and must never be interpreted as markup.

- [ ] **Step 4: Run the contract tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k "scaffold or report_viewer"`

Expected: PASS.

- [ ] **Step 5: Open both scaffolds in a browser**

This is the manual gate the design doc records as the mitigation for what the harness cannot assert. Substitute `examples/sample-report.json` into a copy of the template and open it. Then do the same with `examples/sample-report-unverified.json`, which is a thin map without `--read-code` and therefore has no snippets — confirm the missing-snippet path renders quietly. Then substitute a deliberately malformed document and confirm the error card appears rather than a blank page.

Record what you saw in your task report. If you cannot open a browser in your environment, say so plainly rather than claiming the step — the controller will carry it forward as an open item.

- [ ] **Step 6: Run the full suite and commit**

```bash
git add templates/shared/report.template.html tests/test_template_contracts.py
git commit -m "feat: render the quality report"
```

---

### Task 5: Write the HTML from the quality command

**Files:**
- Modify: `templates/claude/code-flow.quality.md`, `templates/gemini/code-flow.quality.toml`, `templates/copilot/code-flow.quality.prompt.md`
- Modify: `tests/test_template_contracts.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `_output_region` and `_flatten` from `tests/test_template_contracts.py`, and the `_OUTPUT_START` / `_OUTPUT_END` anchors phase 3a established.
- Produces: nothing later consumes.

- [ ] **Step 1: Write the failing contract tests**

Add to `tests/test_template_contracts.py`:

```python
@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_the_html_last(repo_root: Path, host: str, name: str) -> None:
    """The JSON is the data and both renderings come from it. Naming the HTML
    before the JSON would invite writing them as independent transcriptions."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    j = region.index("quality-report.json")
    h = region.index("quality-report.html")
    assert j < h, f"{host} names the HTML before the JSON it renders from"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_the_report_scaffold(repo_root: Path, host: str, name: str) -> None:
    """The command fills a scaffold the installer placed; if it does not name the
    path, the assistant will invent a viewer instead of using the shipped one."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"\.code-flow/report\.template\.html.{0,200}?__REPORT_DATA__",
        region, re.IGNORECASE | re.DOTALL,
    ), f"{host} does not tie the scaffold to its token"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_states_the_html_escaping_rule(repo_root: Path, host: str, name: str) -> None:
    """Findings carry source snippets, which contain `</`. Substituted raw into a
    script block that ends the block early and the page renders as text."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"</.{0,120}?escape", region, re.IGNORECASE | re.DOTALL), (
        f"{host} does not state the </ escaping rule"
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k "html_last or report_scaffold or escaping"`

Expected: FAIL, all three, in all three hosts — step 5 does not mention the HTML yet.

- [ ] **Step 3: Add the canonical block to Claude and Gemini**

Append to step 5 in `templates/claude/code-flow.quality.md`, and the byte-identical text inside the `prompt` string in `templates/gemini/code-flow.quality.toml`:

```markdown
Last, write `Code_Flows/quality-report.html`. Read `.code-flow/report.template.html`
and replace its single `__REPORT_DATA__` token with the exact JSON you just wrote.
Change nothing else in the scaffold.

Escape every literal `</` inside the JSON as `<\/` before substituting. Findings
carry source snippets, and an unescaped `</` closes the script block early — the
page then renders as plain text with no error to explain why.

All three files are renderings of the same data and none may contradict another. If
you cannot read the scaffold, say so and write the other two; a missing viewer is a
missing convenience, not a missing report.
```

- [ ] **Step 4: Add the same rules to Copilot**

Append to the same numbered item in `templates/copilot/code-flow.quality.prompt.md`, in its register:

```markdown
   Last, write `Code_Flows/quality-report.html`: read `.code-flow/report.template.html`
   and replace its single `__REPORT_DATA__` token with the exact JSON you just wrote,
   changing nothing else. Escape every literal `</` in that JSON as `<\/` first —
   findings carry source snippets, and an unescaped `</` closes the script block early,
   leaving the page rendered as plain text with nothing to explain why. All three files
   render the same data and none may contradict another. If the scaffold cannot be read,
   say so and write the other two: a missing viewer is a missing convenience, not a
   missing report.
```

- [ ] **Step 5: Run the tests and the parity check**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality` then `uv run --group dev pytest tests/test_host_parity.py -v`

Expected: PASS, and parity reports `0` for the quality templates. **If parity is above 0, the Claude and Gemini blocks differ — fix the templates, never the baseline.**

- [ ] **Step 6: Prove the new rules are not vacuous**

Delete the escaping paragraph from Claude only, run `-k escaping`, confirm the failure names `claude`, restore exactly, confirm `git diff templates/` is empty, re-run green. Do the same for the scaffold-path rule. Record both outputs.

- [ ] **Step 7: Derive host parity end-to-end**

Read all three quality templates end-to-end, one after another. Confirm in each: the HTML output path, named after the JSON; the scaffold path tied to its token; the `</` escaping rule; the "none may contradict another" rule; and the graceful degradation when the scaffold is unreadable. Record the derivation in your task report — the parity script only compares Claude against Gemini, so Copilot is the one this read exists for.

- [ ] **Step 8: Update the README**

Add `Code_Flows/quality-report.html` to the artifacts the quality command produces, noting it is a self-contained page that opens offline. Do not describe it as tested rendering — the design doc is explicit that the rendering is covered by a pre-release manual pass rather than by the suite.

- [ ] **Step 9: Run the full suite and commit**

Run: `uv run --group dev pytest -v && npm test`

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md tests/test_template_contracts.py README.md
git commit -m "feat: write quality-report.html from the report scaffold"
```

---

## What this phase does not verify

Stated so no one later reads the green suite as a stronger claim than it is.

- **That either page renders correctly in a browser.** No test here executes the rendering code or touches a DOM. This is the accepted cost of Decision 1 in the design doc, and its mitigation is a human opening both scaffolds against a real codebase before a release ships. Two things follow: that manual pass belongs in the release checklist rather than in anyone's memory, and **any future change to either scaffold's rendering re-incurs the gap without the suite saying so.**
- **That the error card is visible.** `validate()` returning `{ok:false}` is asserted; `fail()` writing it to the page is not. Deleting `errBox.hidden = false` would leave the suite green.
- **That the assistant actually produces a well-formed report.** The command runs inside an AI assistant; the templates are prompt text, and prompt text is tested for the rules it states, not for the behavior it induces. The same limitation phases 1, 2 and 3a disclosed, unchanged here.
- **That the substitution the assistant performs escapes `</` correctly.** The rule is stated and its presence is tested. Whether a given run obeys it is not observable from this repository.

---

## Amendments applied during execution

Every task in this plan shipped at least one correction to the plan's own text.
They are recorded here rather than edited silently into the steps above, so the
plan stays readable as what was *asked for* and this section carries what was
*learned*. **Where a step above and this section disagree, the shipped files
govern.**

### Task 1 — the brief's installer-test snippet used a signature that does not exist

Step 1 called `run_python_installer(tmp_path, "--tool", "claude")`. The fixture in
`tests/conftest.py` is `_run(target, tool="all")`, so the positional form would not
have run. Corrected to the keyword form, matching every other test in that file.

The implementer also extended `test_installed_files_are_byte_identical_to_their_templates`
to cover the new `report.template.html`. Not requested, and right: the `EXPECTED_ALL`
set check alone would not catch a CRLF-corrupting regression in the new file.

### Task 2 — the mutation in Step 6 did not break the fixture in Step 4

Step 6 said to delete the `if (byId.has(e.from))` check and watch the dangling-reference
case fail. It would not have: Step 4's fixture has a dangling `to` and a resolvable
`from`, so deleting the `from` check left it green. **The plan's own non-vacuousness
proof was itself vacuous** — the exact defect class this plan's Global Constraints
were written to catch, reproduced by the constraints' author. A `from`-direction
fixture was added and the mutation then failed as intended.

Two shared assertions ("wrong shape", "empty document") were also strengthened: they
passed against Task 1's stub, which rejects everything. `ok:false` is not evidence a
validator works.

### Task 4 — `test_scaffold_is_self_contained` could not pass as written

The drafted blanket check rejects any `http://` or `https://`, and
`viewer.template.html` legitimately contains `http://www.w3.org/2000/svg` twice — an
XML namespace, not a network reference. That one string is excised before the blanket
check; a CDN reference still fails it.

The manual browser pass in Step 5 was performed, and found two copy defects **no test
would have caught**: the `unreached` note duplicated the finding's rationale verbatim
on screen, and the no-findings copy said "the four detectors" when one may have been
skipped. This is the clearest evidence in the phase for why Decision 1's manual
pre-release check is a real control and not a formality.

### Task 5 — "step 5" names a section that is actually two steps

The plan and the design doc's Decision 3 both said to append the HTML to step 5.
The shipped templates split the output across two sections — `#### 5. Write the
Report Data` writes the JSON, `#### 6. Write the Report` renders the markdown — so
following that literally would have produced the written order `json → html → md`,
contradicting Decision 3's own ordering rule and making the block's opening word
("Last") false where it is read.

**The HTML paragraph is appended to the end of step 6.** Decision 3 in the design doc
has been corrected. `tests/test_template_contracts.py` now pins `json < md < html` in
all three hosts, so moving the block back fails the suite instead of passing quietly.

Step 6's closing sentence was also changed from "report both file paths" to "all
three file paths" in all three hosts. Not in the plan, and necessary — leaving it
would have made the step contradict itself.
